#!/usr/bin/env python3
"""
Extensible utility to systematically fix ShellCheck issues from a saved
ShellCheck log or live `shellcheck` runs.

Uses a handler registry keyed by ShellCheck rule ID (e.g., 'SC2086', 'SC2181', 'SC1091')
so additional rule handlers can be registered over time without changing the
core parsing, dry-run, or file-writing pipeline.
"""

from __future__ import annotations

import argparse
import fnmatch
import glob
import logging
import os
import posixpath
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

DEFAULT_ISSUES_LOG_PATH = Path(".shellcheck-issues.txt")
DEFAULT_SCRIPT_GLOB = "./**/*.sh"
DEFAULT_SHELL_EXTENSIONS: Tuple[str, ...] = (".sh", ".bash", ".ksh")
DEFAULT_TOP_DIRS = 10
DEFAULT_QUOTE_ALL_ON_LINE = True

# Used only when falling back outside a Git worktree.
# Intentionally excludes "save" while keeping "archive" included.
DEFAULT_FALLBACK_PRUNE_DIRS: Set[str] = {
    ".git",
    "save",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".agent_state",
    ".code_index",
    ".rsync",
}

# Variables commonly holding multiple CLI flags, options, or commands where
# word splitting may be intentional and should be inspected manually.
DEFAULT_SC2086_SKIP_VARS: Set[str] = {
    "COMMON_OPTS",
    "EXCLUDES",
    "DOCKER_HTTP_CURL_HEADERS",
    "SYSTEMD_CHECK_CMD",
    "OPTIONS",
}

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
FILE_HEADER_RE = re.compile(r"^In (.+?) line (\d+):\s*$")
CARET_LINE_RE = re.compile(
    r"^(\s*)(\^[-^~]*\^?)\s+(SC\d{4})(?:\s+\((error|warning|info|style)\))?\b"
)
# Supports named variables ($FOO, ${FOO}) and positional/numeric parameters ($1, ${1})
# noinspection RegExpRedundantEscape
VAR_EXPANSION_RE = re.compile(
    r"\$\{(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+)\}|\$(?:[A-Za-z_][A-Za-z0-9_]*|[0-9])"
)

_VAR_TOKEN_PAT = (
    r"(?:\$\{(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+)\}|\$(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]))"
)

ECHO_OR_PRINTF_SED_RE = re.compile(
    rf"""
    (?:
        echo\s+"?{_VAR_TOKEN_PAT}"?
        |
        printf\s+'%s\\n'\s+"?{_VAR_TOKEN_PAT}"?
    )
    \s*\|\s*
    sed\s+(?P<quote>['"])(?P<expr>.+?)(?P=quote)
    """,
    re.VERBOSE,
)

# noinspection RegExpRedundantEscape
SED_VAR_NAME_RE = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*|[0-9]+)\}|\$([A-Za-z_][A-Za-z0-9_]*|[0-9])"
)
SED_REGEX_META_RE = re.compile(r"[.*+?\[\](){}^$|\\]")
FIND_NAME_ARG_RE = re.compile(
    r"(?:-name|-iname|-path|-ipath|-wholename|-iwholename)\s+(?P<pattern>(?:[^\s|;&()]+)+)"
)
SOURCE_STMT_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<cmd>\.|source)(?P<sep>[ \t]+)(?P<target>.+?)\s*$"
)
DISABLE_DIRECTIVE_RE = re.compile(
    r"^(?P<indent>[ \t]*)#[ \t]*shellcheck[ \t]+disable=(?P<codes>[^\r\n#]+?)(?P<tail>[ \t]*(?:#.*)?)$"
)
SHELLCHECK_SOURCE_DIRECTIVE_RE = re.compile(
    r"^[ \t]*#[ \t]*shellcheck[ \t]+source="
)
SC_CODE_RE = re.compile(r"\bSC\d{4}\b", re.IGNORECASE)
DOLLAR_Q_RE = re.compile(r"\$\{\?\s*\}|\$\?")
SC2155_DECL_ASSIGN_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<decl>(?:local|export|readonly|declare)(?:\s+-[A-Za-z0-9_-]+)*)\s+(?P<var>[A-Za-z_][A-Za-z0-9_]*)=(?P<rhs>.+?)(?P<eol>\r?\n)?$"
)
SC2004_ARITH_BRACE_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_X_PREFIX_OPERAND_PAT = (
    r'(?:"x(?:\$\{[A-Za-z_][A-Za-z0-9_]*\}|\$[A-Za-z_][A-Za-z0-9_]*)"|"x")'
)
_SC2268_VAR_PAT = r"(?:\$\{[A-Za-z_][A-Za-z0-9_]*\}|\$[A-Za-z_][A-Za-z0-9_]*)"
_SC2268_TERM_PAT = (
    rf'(?:"x(?:{_SC2268_VAR_PAT})?"|\'x(?:{_SC2268_VAR_PAT})?\'|x(?:{_SC2268_VAR_PAT})?)'
)
SC2268_COMPARISON_RE = re.compile(
    rf"(?P<lhs>{_SC2268_TERM_PAT})\s+(?P<op>!=|==?)\s+(?P<rhs>{_SC2268_TERM_PAT})"
)


@dataclass(frozen=True)
class ShellCheckFinding:
    """Represents a single ShellCheck diagnostic for a source line."""

    filepath: str
    lineno: int
    src_line: str
    caret_offset: int
    caret_len: int
    rule: str
    message: str
    severity: str = ""


@dataclass(frozen=True)
class EditSpan:
    """Represents a single text replacement within a source line."""

    lineno: int
    start: int
    end: int
    replacement: str
    rule: str = ""
    expected_original: Optional[str] = None


# A rule handler inspects a ShellCheckFinding and returns zero or more EditSpans.
RuleHandler = Callable[[ShellCheckFinding], Iterable[EditSpan]]


class RuleHandlerRegistry:
    """Registry mapping ShellCheck rule codes (e.g., 'SC2086') to fixer handlers."""

    def __init__(self) -> None:
        self._handlers: Dict[str, RuleHandler] = {}

    def register(self, rule: str, handler: RuleHandler) -> None:
        normalized = rule.upper()
        self._handlers[normalized] = handler
        logger.debug("Registered ShellCheck handler for %s", normalized)

    def get(self, rule: str) -> Optional[RuleHandler]:
        return self._handlers.get(rule.upper())

    def supported_rules(self) -> List[str]:
        return sorted(self._handlers.keys())


def build_effective_skip_vars(
    no_default_skip: bool,
    extra_skip: Sequence[str],
    include_vars: Sequence[str],
) -> Set[str]:
    skip_set: Set[str] = set() if no_default_skip else set(DEFAULT_SC2086_SKIP_VARS)
    skip_set.update(extra_skip)
    skip_set.difference_update(include_vars)
    return skip_set


def _extract_sed_var_name(text: str) -> str:
    match = SED_VAR_NAME_RE.search(text)
    if not match:
        return ""
    return match.group(1) or match.group(2) or ""


def _parse_simple_sed_subst(expr: str) -> Tuple[Optional[Tuple[str, str, bool]], str]:
    """
    Parses a conservative `s<delim>search<delim>replace<delim>[g]` expression.
    Returns ((search, replace, is_global), "") on success, or (None, skip_reason).
    """
    if not expr.startswith("s") or len(expr) < 4:
        return None, "not a simple 's' substitution"

    delim = expr[1]
    if delim.isalnum() or delim.isspace() or delim == "\\":
        return None, f"unsupported delimiter '{delim}'"

    parts: List[str] = []
    buf: List[str] = []
    idx = 2
    while idx < len(expr):
        ch = expr[idx]
        if ch == "\\" and idx + 1 < len(expr):
            buf.append(ch)
            buf.append(expr[idx + 1])
            idx += 2
            continue
        if ch == delim:
            parts.append("".join(buf))
            buf = []
            idx += 1
            if len(parts) == 2:
                break
            continue
        buf.append(ch)
        idx += 1

    if len(parts) != 2:
        return None, "multiple or malformed sed substitution expressions"

    search, replace = parts[0], parts[1]
    flags = expr[idx:]
    if flags not in ("", "g"):
        return None, f"unsupported or multiple sed expressions/flags '{flags}'"

    if SED_REGEX_META_RE.search(search):
        return None, f"regex metacharacters in search pattern '{search}'"

    if "/" in search or "}" in search:
        return None, f"slash or brace in search pattern '{search}'"

    if "&" in replace or "\\" in replace or "/" in replace or "}" in replace:
        return (
            None,
            f"backreference, escape, slash, or brace in replacement '{replace}'",
        )

    return (search, replace, flags == "g"), ""


def _find_quoted_ranges(line: str) -> List[Tuple[int, int]]:
    """
    Returns [start, end) character spans that lie directly inside double-quoted
    strings on `line`, accounting for single quotes, backslash escapes, and
    nested `$(...)` command substitutions where outer double quotes do not
    automatically quote inner expansions.
    """
    in_single = False
    in_double = False
    double_start: Optional[int] = None
    # Stack of (cmd_paren_depth, was_in_double_before_cmd_sub)
    cmd_sub_stack: List[Tuple[int, bool]] = []
    quoted_spans: List[Tuple[int, int]] = []

    idx = 0
    length = len(line)
    while idx < length:
        ch = line[idx]

        if ch == "\\" and not in_single and idx + 1 < length:
            idx += 2
            continue

        if ch == "'" and not in_double:
            in_single = not in_single
            idx += 1
            continue

        if not in_single:
            # Enter a command substitution $(...)
            if ch == "$" and idx + 1 < length and line[idx + 1] == "(":
                if in_double and double_start is not None:
                    quoted_spans.append((double_start, idx))
                    double_start = None
                cmd_sub_stack.append((1, in_double))
                in_double = False
                idx += 2
                continue

            # Track nested parentheses inside an active $(...) command substitution
            if cmd_sub_stack:
                if ch == "(":
                    cur_depth, prev_double = cmd_sub_stack[-1]
                    cmd_sub_stack[-1] = (cur_depth + 1, prev_double)
                    idx += 1
                    continue
                if ch == ")":
                    cur_depth, prev_double = cmd_sub_stack[-1]
                    if cur_depth > 1:
                        cmd_sub_stack[-1] = (cur_depth - 1, prev_double)
                    else:
                        if in_double and double_start is not None:
                            quoted_spans.append((double_start, idx + 1))
                            double_start = None
                        cmd_sub_stack.pop()
                        in_double = prev_double
                        if in_double:
                            double_start = idx + 1
                    idx += 1
                    continue

            if ch == '"':
                if not in_double:
                    in_double = True
                    double_start = idx
                else:
                    in_double = False
                    if double_start is not None:
                        quoted_spans.append((double_start, idx + 1))
                        double_start = None
                idx += 1
                continue

        idx += 1

    if in_double and double_start is not None:
        quoted_spans.append((double_start, length))

    return quoted_spans


def _find_single_quoted_ranges(line: str) -> List[Tuple[int, int]]:
    """Returns [start, end) character spans inside single-quoted strings."""
    spans: List[Tuple[int, int]] = []
    in_single = False
    start = 0
    for idx, ch in enumerate(line):
        if ch == "'":
            if not in_single:
                in_single = True
                start = idx
            else:
                in_single = False
                spans.append((start, idx + 1))
    if in_single:
        spans.append((start, len(line)))
    return spans


def _find_arithmetic_expansion_ranges(line: str) -> List[Tuple[int, int]]:
    """Returns [start, end) spans for top-level `$((...))` arithmetic expansions."""
    ranges: List[Tuple[int, int]] = []
    idx = 0
    length = len(line)
    while idx + 2 < length:
        if line[idx : idx + 3] == "$((":
            depth = 1
            scan = idx + 3
            while scan < length and depth > 0:
                if line[scan : scan + 2] == "((" or line[scan] == "(":
                    depth += 1
                elif line[scan] == ")":
                    depth -= 1
                    if depth == 0:
                        ranges.append((idx, scan + 1))
                        idx = scan + 1
                        break
                scan += 1
            else:
                break
            continue
        idx += 1
    return ranges


def _find_unquoted_command_sub_ranges(line: str) -> List[Tuple[int, int]]:
    """
    Returns [start, end) spans for top-level `$(...)` command substitutions
    (excluding arithmetic `$((...))`) that are not enclosed in quotes.
    """
    single_spans = _find_single_quoted_ranges(line)
    double_spans = _find_quoted_ranges(line)
    spans: List[Tuple[int, int]] = []
    idx = 0
    length = len(line)

    while idx + 1 < length:
        if _is_inside_any_span(idx, idx + 2, single_spans):
            idx += 1
            continue

        if line[idx] == "$" and line[idx + 1] == "(":
            # Skip arithmetic expansion $((...))
            if idx + 2 < length and line[idx + 2] == "(":
                depth = 1
                scan = idx + 3
                while scan < length and depth > 0:
                    if line[scan] == "(":
                        depth += 1
                    elif line[scan] == ")":
                        depth -= 1
                    scan += 1
                idx = scan
                continue

            depth = 1
            scan = idx + 2
            in_sq = False
            in_dq = False
            while scan < length and depth > 0:
                ch = line[scan]
                if ch == "\\" and not in_sq and scan + 1 < length:
                    scan += 2
                    continue
                if ch == "'" and not in_dq:
                    in_sq = not in_sq
                elif ch == '"' and not in_sq:
                    in_dq = not in_dq
                elif not in_sq and not in_dq:
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                scan += 1

            cmd_start = idx
            cmd_end = scan
            already_quoted = (
                (cmd_start > 0 and line[cmd_start - 1] == '"' and cmd_end < length and line[cmd_end] == '"')
                or _is_inside_any_span(cmd_start, cmd_end, double_spans)
            )
            if not already_quoted:
                spans.append((cmd_start, cmd_end))
            idx = cmd_end
            continue

        idx += 1

    return spans


def _is_inside_any_span(start: int, end: int, spans: Sequence[Tuple[int, int]]) -> bool:
    """Returns True if [start, end) falls completely within any (span_start, span_end) range."""
    for span_start, span_end in spans:
        if start >= span_start and end <= span_end:
            return True
    return False


def make_sc2004_handler() -> RuleHandler:
    """
    Handler for SC2004 ("$ / ${} is unnecessary on arithmetic variables")
    that strips `${VAR}` to `VAR` inside `$((...))` arithmetic expansions.
    """

    def _handle_sc2004(finding: ShellCheckFinding) -> List[EditSpan]:
        src_line = finding.src_line
        arith_ranges = _find_arithmetic_expansion_ranges(src_line)
        if not arith_ranges:
            logger.debug(
                "Skipping SC2004 at %s:%d (no $((...)) arithmetic expansion found): %s",
                finding.filepath,
                finding.lineno,
                src_line.strip(),
            )
            return []

        edits: List[EditSpan] = []
        for match in SC2004_ARITH_BRACE_VAR_RE.finditer(src_line):
            start = match.start()
            end = match.end()
            if not _is_inside_any_span(start, end, arith_ranges):
                continue
            var_name = match.group(1)
            edits.append(
                EditSpan(
                    lineno=finding.lineno,
                    start=start,
                    end=end,
                    replacement=var_name,
                    rule=finding.rule,
                    expected_original=match.group(0),
                )
            )

        return edits

    return _handle_sc2004


def make_sc2268_handler() -> RuleHandler:
    """
    Handler for SC2268 ("Avoid x-prefix in comparisons as it no longer serves a purpose")
    that rewrites `"x$var" != "x"` (and `=` / `==` / reversed operands) to `"$var" != ""`.
    """

    def _rewrite_x_operand(operand: str) -> Tuple[str, bool]:
        stripped = operand.strip()
        quote = '"'
        inner = stripped
        if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in ('"', "'"):
            quote = stripped[0]
            inner = stripped[1:-1]

        if not inner.startswith("x"):
            return operand, False

        remainder = inner[1:]
        if not remainder:
            return f"{quote}{quote}", False

        return f"{quote}{remainder}{quote}", True

    def _handle_sc2268(finding: ShellCheckFinding) -> List[EditSpan]:
        src_line = finding.src_line
        edits: List[EditSpan] = []
        for match in SC2268_COMPARISON_RE.finditer(src_line):
            lhs = match.group("lhs")
            op = match.group("op")
            rhs = match.group("rhs")

            new_lhs, lhs_had_var = _rewrite_x_operand(lhs)
            new_rhs, rhs_had_var = _rewrite_x_operand(rhs)
            if new_lhs == lhs and new_rhs == rhs:
                continue
            if not (lhs_had_var or rhs_had_var):
                continue

            replacement = f"{new_lhs} {op} {new_rhs}"
            edits.append(
                EditSpan(
                    lineno=finding.lineno,
                    start=match.start(),
                    end=match.end(),
                    replacement=replacement,
                    rule=finding.rule,
                    expected_original=match.group(0),
                )
            )

        if not edits:
            logger.debug(
                "Skipping SC2268 at %s:%d (unrecognized x-prefix comparison): %s",
                finding.filepath,
                finding.lineno,
                src_line.strip(),
            )
        return edits

    return _handle_sc2268


def make_sc2046_handler() -> RuleHandler:
    """
    Handler for SC2046 ("Quote this to prevent word splitting")
    that wraps unquoted `$(...)` command substitutions in double quotes `"$(...)"`.
    """

    def _handle_sc2046(finding: ShellCheckFinding) -> List[EditSpan]:
        src_line = finding.src_line
        cmd_ranges = _find_unquoted_command_sub_ranges(src_line)
        if not cmd_ranges:
            logger.debug(
                "Skipping SC2046 at %s:%d (no unquoted $(...) found): %s",
                finding.filepath,
                finding.lineno,
                src_line.strip(),
            )
            return []

        edits: List[EditSpan] = []
        for start, end in cmd_ranges:
            token = src_line[start:end]
            edits.append(
                EditSpan(
                    lineno=finding.lineno,
                    start=start,
                    end=end,
                    replacement=f'"{token}"',
                    rule=finding.rule,
                    expected_original=token,
                )
            )
        return edits

    return _handle_sc2046


def make_sc2001_handler() -> RuleHandler:
    """
    Conservative handler for SC2001 that rewrites simple `echo`/`printf ... | sed`
    literal substitutions into `${VAR//search/replace}` or `${VAR/search/replace}`,
    while logging and skipping complex or ambiguous expressions.
    """

    def _handle_sc2001(finding: ShellCheckFinding) -> List[EditSpan]:
        src_line = finding.src_line
        matches = list(ECHO_OR_PRINTF_SED_RE.finditer(src_line))
        if not matches:
            logger.debug(
                "Skipping ambiguous SC2001 at %s:%d (unrecognized sed pipeline): %s",
                finding.filepath,
                finding.lineno,
                src_line.strip(),
            )
            return []

        edits: List[EditSpan] = []
        for match in matches:
            matched_text = match.group(0)
            var_name = _extract_sed_var_name(matched_text)
            if not var_name:
                logger.debug(
                    "Skipping ambiguous SC2001 at %s:%d (could not determine variable name)",
                    finding.filepath,
                    finding.lineno,
                )
                continue

            parsed, skip_reason = _parse_simple_sed_subst(match.group("expr"))
            if parsed is None:
                logger.debug(
                    "Skipping SC2001 at %s:%d (%s): %s",
                    finding.filepath,
                    finding.lineno,
                    skip_reason,
                    matched_text.strip(),
                )
                continue

            search, replace, is_global = parsed
            operator = "//" if is_global else "/"
            param_expr = f"${{{var_name}{operator}{search}/{replace}}}"

            start = match.start()
            end = match.end()
            # If wrapped directly as $(<pipeline>), replace the whole $(...) expansion
            if (
                start >= 2
                and src_line[start - 2 : start] == "$("
                and end < len(src_line)
                and src_line[end] == ")"
            ):
                start -= 2
                end += 1
                replacement = f'"{param_expr}"'
            else:
                replacement = param_expr

            edits.append(
                EditSpan(
                    lineno=finding.lineno,
                    start=start,
                    end=end,
                    replacement=replacement,
                    rule=finding.rule,
                    expected_original=src_line[start:end],
                )
            )

        return edits

    return _handle_sc2001


def make_sc2034_handler() -> RuleHandler:
    """
    Conservative handler for SC2034 ("... appears unused").
    Avoids removing assignments automatically due to indirect references,
    sourced scripts, exported/shared state, and command-substitution side effects.
    """

    def _handle_sc2034(finding: ShellCheckFinding) -> List[EditSpan]:
        logger.debug(
            "Skipping SC2034 at %s:%d (unused variable may be external/indirect/side-effecting): %s",
            finding.filepath,
            finding.lineno,
            finding.src_line.strip(),
        )
        return []

    return _handle_sc2034


def make_sc2061_handler() -> RuleHandler:
    """
    Handler for SC2061 ("Quote the parameter to -name so the shell won't interpret it")
    that wraps unquoted `-name` (or `-iname`/`-path`/etc.) glob arguments in double quotes.
    """

    def _handle_sc2061(finding: ShellCheckFinding) -> List[EditSpan]:
        src_line = finding.src_line
        matches = list(FIND_NAME_ARG_RE.finditer(src_line))
        if not matches:
            logger.debug(
                "Skipping SC2061 at %s:%d (could not locate -name pattern argument): %s",
                finding.filepath,
                finding.lineno,
                src_line.strip(),
            )
            return []

        caret_start = finding.caret_offset
        caret_end = finding.caret_offset + max(1, finding.caret_len)

        selected_match = None
        for m in matches:
            p_start, p_end = m.span("pattern")
            if p_start < caret_end and p_end > caret_start:
                selected_match = m
                break
        if selected_match is None:
            selected_match = matches[0]

        p_start, p_end = selected_match.span("pattern")
        raw_pattern = selected_match.group("pattern")

        # Skip if already enclosed as a single quote-delimited argument
        if len(raw_pattern) >= 2 and (
            (raw_pattern.startswith('"') and raw_pattern.endswith('"'))
            or (raw_pattern.startswith("'") and raw_pattern.endswith("'"))
        ):
            logger.debug(
                "Skipping SC2061 at %s:%d (pattern already quoted): %s",
                finding.filepath,
                finding.lineno,
                raw_pattern,
            )
            return []

        # Flatten inner quotes like cert*."${CACERT_TRUST_FORMAT}" -> "cert*.${CACERT_TRUST_FORMAT}"
        normalized_inner = raw_pattern.replace('"', "")
        replacement = f'"{normalized_inner}"'
        return [
            EditSpan(
                lineno=finding.lineno,
                start=p_start,
                end=p_end,
                replacement=replacement,
                rule=finding.rule,
                expected_original=raw_pattern,
            )
        ]

    return _handle_sc2061


def make_sc2086_handler(
    skip_vars: Optional[Set[str]] = None,
    quote_all_on_line: bool = DEFAULT_QUOTE_ALL_ON_LINE,
) -> RuleHandler:
    """
    Creates a handler for SC2086 that double-quotes unquoted variable expansions.

    When `quote_all_on_line` is True (default), scans all variable expansions on
    `finding.src_line` while tracking single/double quote spans and `$(...)`
    command substitutions so unquoted companion expansions are also quoted.
    When `quote_all_on_line` is False, falls back to quoting only the single
    expansion matching or nearest to the finding's caret.
    """
    effective_skip = skip_vars if skip_vars is not None else set()

    def _build_edit_for_match(
        finding: ShellCheckFinding,
        start: int,
        end: int,
        token: str,
        double_quoted_spans: Sequence[Tuple[int, int]],
    ) -> Optional[EditSpan]:
        src_line = finding.src_line
        var_name = token.lstrip("${").rstrip("}")

        if var_name in effective_skip:
            logger.debug(
                "Skipping SC2086 variable '%s' in %s:%d (in skip list)",
                var_name,
                finding.filepath,
                finding.lineno,
            )
            return None

        if _is_inside_any_span(start, end, double_quoted_spans):
            logger.debug(
                "Skipping already-quoted SC2086 token '%s' in %s:%d (inside double quotes)",
                token,
                finding.filepath,
                finding.lineno,
            )
            return None

        before_ch = src_line[start - 1] if start > 0 else ""
        after_ch = src_line[end] if end < len(src_line) else ""
        if before_ch == '"' and after_ch == '"':
            logger.debug(
                "Skipping already-quoted SC2086 token '%s' in %s:%d",
                token,
                finding.filepath,
                finding.lineno,
            )
            return None

        return EditSpan(
            lineno=finding.lineno,
            start=start,
            end=end,
            replacement=f'"{token}"',
            rule=finding.rule,
            expected_original=token,
        )

    def _handle_sc2086(finding: ShellCheckFinding) -> List[EditSpan]:
        src_line = finding.src_line
        double_quoted_spans = _find_quoted_ranges(src_line)

        if quote_all_on_line:
            edits: List[EditSpan] = []
            seen_spans: Set[Tuple[int, int, str]] = set()
            for match in VAR_EXPANSION_RE.finditer(src_line):
                start = match.start()
                end = match.end()
                token = match.group(0)
                key = (start, end, token)
                if key in seen_spans:
                    continue
                seen_spans.add(key)

                edit = _build_edit_for_match(
                    finding=finding,
                    start=start,
                    end=end,
                    token=token,
                    double_quoted_spans=double_quoted_spans,
                )
                if edit is not None:
                    edits.append(edit)
            return edits

        # Fallback mode: target only the single variable matching/closest to the caret
        win_start = max(0, finding.caret_offset - 2)
        win_end = min(
            len(src_line), finding.caret_offset + max(1, finding.caret_len) + 2
        )
        window = src_line[win_start:win_end]

        caret_start = finding.caret_offset
        caret_end = finding.caret_offset + max(1, finding.caret_len)
        caret_center = (caret_start + caret_end) / 2.0

        candidates: List[Tuple[int, float, int, int, str]] = []
        for match in VAR_EXPANSION_RE.finditer(window):
            abs_start = win_start + match.start()
            abs_end = win_start + match.end()
            overlaps_caret = abs_start < caret_end and abs_end > caret_start
            center_dist = abs(((abs_start + abs_end) / 2.0) - caret_center)
            candidates.append(
                (
                    0 if overlaps_caret else 1,
                    center_dist,
                    abs_start,
                    abs_end,
                    match.group(0),
                )
            )

        if not candidates:
            return []

        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        _, _, start, end, token = candidates[0]
        edit = _build_edit_for_match(
            finding=finding,
            start=start,
            end=end,
            token=token,
            double_quoted_spans=double_quoted_spans,
        )
        return [edit] if edit is not None else []

    return _handle_sc2086


def make_sc2155_handler() -> RuleHandler:
    """
    Handler for SC2155 ("Declare and assign separately to avoid masking return values")
    that splits single-variable `<decl> VAR=<rhs>` statements into a declaration line
    followed by `VAR=<rhs>` on the current line.
    """

    def _handle_sc2155(finding: ShellCheckFinding) -> List[EditSpan]:
        src_line = finding.src_line
        match = SC2155_DECL_ASSIGN_RE.match(src_line)
        if not match:
            logger.debug(
                "Skipping SC2155 at %s:%d (unrecognized declaration assignment): %s",
                finding.filepath,
                finding.lineno,
                src_line.strip(),
            )
            return []

        indent = match.group("indent")
        decl = match.group("decl")
        var_name = match.group("var")
        rhs = match.group("rhs")

        # Avoid splitting multi-assignment declarations like `local a=$(x) b=$(y)`
        if re.search(r"(?:^|\s)[A-Za-z_][A-Za-z0-9_]*=", rhs):
            logger.debug(
                "Skipping SC2155 at %s:%d (multiple variable assignments on line): %s",
                finding.filepath,
                finding.lineno,
                src_line.strip(),
            )
            return []

        decl_line = f"{indent}{decl} {var_name}\n"
        assign_start = len(indent)
        assign_end = assign_start + len(f"{decl} {var_name}=")
        assign_replacement = f"{var_name}="

        return [
            EditSpan(
                lineno=finding.lineno,
                start=0,
                end=0,
                replacement=decl_line,
                rule=finding.rule,
                expected_original="",
            ),
            EditSpan(
                lineno=finding.lineno,
                start=assign_start,
                end=assign_end,
                replacement=assign_replacement,
                rule=finding.rule,
                expected_original=f"{decl} {var_name}=",
            ),
        ]

    return _handle_sc2155


def make_sc2181_handler() -> RuleHandler:
    """
    Conservative handler for SC2181 ("Check exit code directly with e.g.
    'if mycmd;', not indirectly with $?").

    Because the command whose return code is tested precedes the `if` statement
    and is not present on the flagged line, automatic inline rewriting would
    guess an unknown command. Logs and skips safely so compound/indirect `$?`
    checks are reviewed manually or suppressed with `# shellcheck disable=SC2181`.
    """

    def _handle_sc2181(finding: ShellCheckFinding) -> List[EditSpan]:
        src_line = finding.src_line
        if not DOLLAR_Q_RE.search(src_line):
            logger.debug(
                "Skipping SC2181 at %s:%d (no $? reference found on line)",
                finding.filepath,
                finding.lineno,
            )
            return []

        is_compound = "&&" in src_line or "||" in src_line
        reason = (
            "compound condition with &&/|| requires manual review"
            if is_compound
            else "preceding command context is outside the line"
        )
        logger.debug(
            "Skipping SC2181 at %s:%d (%s): %s",
            finding.filepath,
            finding.lineno,
            reason,
            src_line.strip(),
        )
        return []

    return _handle_sc2181


def make_sc2317_handler() -> RuleHandler:
    """
    Conservative handler for SC2317 ("Command appears to be unreachable").
    Avoids deleting statements automatically because reachability after custom
    error/exit helpers or across branches/traps can be context-dependent.
    """

    def _handle_sc2317(finding: ShellCheckFinding) -> List[EditSpan]:
        logger.debug(
            "Skipping SC2317 at %s:%d (unreachable code requires manual review): %s",
            finding.filepath,
            finding.lineno,
            finding.src_line.strip(),
        )
        return []

    return _handle_sc2317


def make_sc2329_handler() -> RuleHandler:
    """
    Conservative handler for SC2329 ("This function is never invoked").
    Avoids deleting functions automatically because indirect calls (traps, hooks,
    dynamic dispatch, or sourced callers) are not always visible statically.
    """

    def _handle_sc2329(finding: ShellCheckFinding) -> List[EditSpan]:
        logger.debug(
            "Skipping SC2329 at %s:%d (function may be invoked indirectly or by callers): %s",
            finding.filepath,
            finding.lineno,
            finding.src_line.strip(),
        )
        return []

    return _handle_sc2329


def _strip_matching_quotes(raw_target: str) -> str:
    target = raw_target.strip()
    if len(target) >= 2 and (
        (target.startswith('"') and target.endswith('"'))
        or (target.startswith("'") and target.endswith("'"))
    ):
        return target[1:-1]
    return target


def make_sc1091_handler(
    base_dir: Optional[Path] = None,
    convert_dot_to_source: bool = True,
    insert_source_directive: bool = True,
) -> RuleHandler:
    """
    Handler for SC1091 ("Not following: ... was not specified as input") that:
    1) Optionally converts a leading `. <target>` command to `source <target>`.
    2) Optionally inserts a `# shellcheck source=...` directive immediately above
       the statement.
    """

    def _handle_sc1091(finding: ShellCheckFinding) -> List[EditSpan]:
        match = SOURCE_STMT_RE.match(finding.src_line)
        if not match:
            logger.debug(
                "Skipping SC1091 at %s:%d (unrecognized source statement): %s",
                finding.filepath,
                finding.lineno,
                finding.src_line.strip(),
            )
            return []

        indent = match.group("indent")
        cmd = match.group("cmd")
        raw_target = match.group("target")
        edits: List[EditSpan] = []

        if convert_dot_to_source and cmd == ".":
            cmd_start = len(indent)
            cmd_end = cmd_start + 1
            edits.append(
                EditSpan(
                    lineno=finding.lineno,
                    start=cmd_start,
                    end=cmd_end,
                    replacement="source",
                    rule=finding.rule,
                    expected_original=".",
                )
            )

        if insert_source_directive:
            unquoted = _strip_matching_quotes(raw_target)
            has_dynamic_ref = (
                "$" in unquoted
                or "`" in unquoted
                or "*" in unquoted
                or "?" in unquoted
            )
            source_target = "/dev/null"
            if not has_dynamic_ref and unquoted:
                script_path = (
                    (base_dir / finding.filepath)
                    if base_dir
                    else Path(finding.filepath)
                )
                resolved_candidate = script_path.parent / unquoted
                if resolved_candidate.is_file() or unquoted.startswith(".."):
                    source_target = unquoted

            directive_line = f"{indent}# shellcheck source={source_target}\n"
            edits.append(
                EditSpan(
                    lineno=finding.lineno,
                    start=0,
                    end=0,
                    replacement=directive_line,
                    rule=finding.rule,
                    expected_original="",
                )
            )

        return edits

    return _handle_sc1091


def create_default_registry(
    rules: Optional[Sequence[str]] = None,
    skip_vars: Optional[Set[str]] = None,
    quote_all_on_line: bool = DEFAULT_QUOTE_ALL_ON_LINE,
    base_dir: Optional[Path] = None,
    convert_dot_to_source: bool = True,
    insert_source_directive: bool = True,
) -> RuleHandlerRegistry:
    """Builds the default registry populated with currently implemented rule handlers."""
    available: Dict[str, RuleHandler] = {
        "SC1091": make_sc1091_handler(
            base_dir=base_dir,
            convert_dot_to_source=convert_dot_to_source,
            insert_source_directive=insert_source_directive,
        ),
        "SC2001": make_sc2001_handler(),
        "SC2004": make_sc2004_handler(),
        "SC2034": make_sc2034_handler(),
        "SC2046": make_sc2046_handler(),
        "SC2061": make_sc2061_handler(),
        "SC2086": make_sc2086_handler(
            skip_vars=skip_vars, quote_all_on_line=quote_all_on_line
        ),
        "SC2155": make_sc2155_handler(),
        "SC2181": make_sc2181_handler(),
        "SC2268": make_sc2268_handler(),
        "SC2317": make_sc2317_handler(),
        "SC2329": make_sc2329_handler(),
    }
    requested = [r.upper() for r in rules] if rules else sorted(available.keys())

    registry = RuleHandlerRegistry()
    for rule in requested:
        handler = available.get(rule)
        if handler is not None:
            registry.register(rule, handler)
        else:
            logger.debug("No automated handler implemented yet for rule %s", rule)
    return registry


def _normalize_rel_path_str(filepath: str) -> str:
    """Normalizes a relative file/dir path string using forward slashes without leading './'."""
    norm = posixpath.normpath(filepath.replace("\\", "/"))
    while norm.startswith("./"):
        norm = norm[2:]
    return norm


def _directory_path_key(filepath: str) -> str:
    """
    Returns the normalized relative directory path for a file path
    (e.g., 'files/archive/docker' for 'files/archive/docker/script.sh',
    or '.' when in the current/root directory).
    """
    norm_path = _normalize_rel_path_str(filepath)
    parent = posixpath.dirname(norm_path)
    if not parent or parent == ".":
        return "."
    return _normalize_rel_path_str(parent) or "."


def _path_matches_target_dirs(
    filepath: str,
    target_dirs: Sequence[Path],
    base_dir: Optional[Path] = None,
) -> bool:
    """
    Returns True if `filepath` resides inside (or equals) at least one directory in `target_dirs`.
    """
    if not target_dirs:
        return True

    root = (base_dir or Path.cwd()).resolve()
    candidate = Path(filepath)
    resolved_candidate = (
        candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    )

    for raw_dir in target_dirs:
        dir_path = Path(raw_dir)
        resolved_dir = (
            dir_path.resolve()
            if dir_path.is_absolute()
            else (root / dir_path).resolve()
        )
        try:
            resolved_candidate.relative_to(resolved_dir)
            return True
        except ValueError:
            continue

    return False


def filter_edits_by_directories(
    edits_by_file: Dict[str, List[EditSpan]],
    target_dirs: Optional[Sequence[Path]],
    base_dir: Optional[Path] = None,
) -> Dict[str, List[EditSpan]]:
    """Filters `edits_by_file` to only include files under `target_dirs`."""
    if not target_dirs:
        return edits_by_file

    return {
        filepath: spans
        for filepath, spans in edits_by_file.items()
        if _path_matches_target_dirs(
            filepath, target_dirs=target_dirs, base_dir=base_dir
        )
    }


def filter_findings_by_directories(
    findings: Sequence[ShellCheckFinding],
    target_dirs: Optional[Sequence[Path]],
    base_dir: Optional[Path] = None,
) -> List[ShellCheckFinding]:
    """Filters `findings` to only include files under `target_dirs`."""
    if not target_dirs:
        return list(findings)

    return [
        f
        for f in findings
        if _path_matches_target_dirs(
            f.filepath, target_dirs=target_dirs, base_dir=base_dir
        )
    ]


def _extract_disable_codes(raw: str) -> List[str]:
    codes: List[str] = []
    for match in SC_CODE_RE.finditer(raw):
        code = match.group(0).upper()
        if code not in codes:
            codes.append(code)
    return codes


def _filter_findings_for_suppression(
    findings: Iterable[ShellCheckFinding],
    suppress_rules: Optional[Sequence[str]] = None,
) -> List[ShellCheckFinding]:
    allowed = {r.upper() for r in suppress_rules} if suppress_rules else None
    seen: Set[Tuple[str, int, str]] = set()
    filtered: List[ShellCheckFinding] = []
    for finding in findings:
        rule_code = (finding.rule or "").upper()
        if not SC_CODE_RE.fullmatch(rule_code):
            continue
        if allowed is not None and rule_code not in allowed:
            continue
        key = (finding.filepath, finding.lineno, rule_code)
        if key in seen:
            continue
        seen.add(key)
        filtered.append(finding)
    return filtered


def build_disable_edits_for_findings(
    findings_to_suppress: Iterable[ShellCheckFinding],
    content_by_file: Dict[str, str],
    suppress_rules: Optional[Sequence[str]] = None,
) -> Dict[str, List[EditSpan]]:
    """
    Builds `EditSpan` entries that add or merge `# shellcheck disable=SCxxxx`
    immediately above findings that were skipped or left unhandled.
    """
    disable_edits_by_file: Dict[str, List[EditSpan]] = defaultdict(list)
    deduped_findings = _filter_findings_for_suppression(
        findings_to_suppress, suppress_rules=suppress_rules
    )

    for finding in deduped_findings:
        rule_code = (finding.rule or "").upper()
        if not SC_CODE_RE.fullmatch(rule_code):
            continue

        content = content_by_file.get(finding.filepath)
        if content is None:
            continue

        lines = content.splitlines(keepends=True)
        if not (1 <= finding.lineno <= len(lines)):
            continue

        target_line = lines[finding.lineno - 1]
        indent_match = re.match(r"^[ \t]*", target_line)
        indent = indent_match.group(0) if indent_match else ""

        # Check if the line immediately above is already a `# shellcheck disable=...`
        # (or walk past an immediately preceding `# shellcheck source=...` if present).
        check_idx = finding.lineno - 2
        if (
            check_idx >= 0
            and SHELLCHECK_SOURCE_DIRECTIVE_RE.match(lines[check_idx].rstrip("\r\n"))
            and check_idx - 1 >= 0
        ):
            check_idx -= 1

        if check_idx >= 0:
            prev_line = lines[check_idx]
            prev_no_nl = prev_line.rstrip("\r\n")
            m = DISABLE_DIRECTIVE_RE.match(prev_no_nl)
            if m:
                existing_codes = _extract_disable_codes(m.group("codes"))
                if rule_code in existing_codes:
                    continue
                merged_codes = existing_codes + [rule_code]
                prev_eol = (
                    "\r\n"
                    if prev_line.endswith("\r\n")
                    else ("\n" if prev_line.endswith("\n") else "\n")
                )
                d_indent = m.group("indent")
                tail = m.group("tail")
                replacement = (
                    f"{d_indent}# shellcheck disable={','.join(merged_codes)}{tail}{prev_eol}"
                )
                disable_edits_by_file[finding.filepath].append(
                    EditSpan(
                        lineno=check_idx + 1,
                        start=0,
                        end=len(prev_line),
                        replacement=replacement,
                        rule=rule_code,
                        expected_original=prev_line,
                    )
                )
                continue

        disable_edits_by_file[finding.filepath].append(
            EditSpan(
                lineno=finding.lineno,
                start=0,
                end=0,
                replacement=f"{indent}# shellcheck disable={rule_code}\n",
                rule=rule_code,
                expected_original="",
            )
        )

    return dict(disable_edits_by_file)


def build_handled_rule_dir_counts(
    rule_edit_records: Iterable[Tuple[str, str, int]],
    handled_rules: Optional[Sequence[str]] = None,
) -> Dict[str, Counter[str]]:
    """
    Aggregates edit counts by full relative directory path for each handled rule.

    `rule_edit_records` yields `(rule, filepath, edit_count)`.
    """
    counts_by_rule: Dict[str, Counter[str]] = {}
    if handled_rules:
        for rule in handled_rules:
            counts_by_rule[rule.upper()] = Counter()

    for rule, filepath, edit_count in rule_edit_records:
        if edit_count <= 0:
            continue
        norm_rule = (rule or "UNKNOWN").upper()
        if handled_rules is not None and norm_rule not in counts_by_rule:
            continue
        bucket = counts_by_rule.setdefault(norm_rule, Counter())
        dir_path = _directory_path_key(filepath)
        bucket[dir_path] += edit_count

    return counts_by_rule


def format_handled_rule_dir_report(
    counts_by_rule: Dict[str, Counter[str]],
    mode_label: str,
    top_n: int = DEFAULT_TOP_DIRS,
) -> str:
    """
    Formats a human-readable summary listing top relative directories (by aggregate
    edit count) for each handled rule.
    """
    if not counts_by_rule:
        return f"Top {top_n} directories by handled issue type ({mode_label}): none."

    lines: List[str] = [
        f"Top {top_n} directories by handled issue type ({mode_label} edits):"
    ]
    for rule in sorted(counts_by_rule.keys()):
        dir_counter = counts_by_rule[rule]
        rule_total = sum(dir_counter.values())
        lines.append(f"  [{rule}] (total: {rule_total})")
        ranked = sorted(dir_counter.items(), key=lambda item: (-item[1], item[0]))[
            :top_n
        ]
        if not ranked:
            lines.append("    (no edits)")
            continue
        for rank, (dir_path, count) in enumerate(ranked, start=1):
            lines.append(f"    {rank:2d}. {dir_path:<42} {count}")

    return "\n".join(lines)


def format_parsed_findings_summary(
    findings: Sequence[ShellCheckFinding],
    handled_rules: Sequence[str] = (),
    candidate_edits_by_file: Optional[Dict[str, List[EditSpan]]] = None,
) -> str:
    """
    Formats an overview of all parsed ShellCheck findings by rule code,
    severity (when present), and file count, indicating which rules are
    currently handled vs. unhandled.
    """
    total_findings = len(findings)
    unique_files = len({f.filepath for f in findings if f.filepath})

    code_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    for finding in findings:
        code = (finding.rule or "UNKNOWN").upper()
        code_counts[code] += 1
        if finding.severity:
            severity_counts[finding.severity.lower()] += 1

    candidate_edits_by_rule: Counter[str] = Counter()
    if candidate_edits_by_file:
        for spans in candidate_edits_by_file.values():
            for span in set(spans):
                candidate_edits_by_rule[(span.rule or "UNKNOWN").upper()] += 1

    handled_set = {r.upper() for r in handled_rules}
    sev_parts = [
        f"{severity_counts[sev]} {sev}"
        for sev in ("error", "warning", "info", "style")
        if severity_counts[sev] > 0
    ]
    sev_suffix = f" ({', '.join(sev_parts)})" if sev_parts else ""

    lines: List[str] = [
        f"Parsed {total_findings} ShellCheck finding(s){sev_suffix} across {unique_files} file(s):"
    ]
    if not code_counts:
        lines.append("  (no parsed findings)")
        return "\n".join(lines)

    for code, count in sorted(
        code_counts.items(), key=lambda item: (-item[1], item[0])
    ):
        if code in handled_set:
            edits_cnt = candidate_edits_by_rule[code]
            lines.append(
                f"  {code:<8} {count:4d}  (handled, {edits_cnt} candidate edit(s))"
            )
        else:
            lines.append(f"  {code:<8} {count:4d}  (unhandled)")

    return "\n".join(lines)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Systematically fix ShellCheck findings using registered rule handlers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # init/regenerate report
  %(prog)s -g
  %(prog)s -y .shellcheck-issues.txt
  # Preview SC2034 suppressions (dry-run, no file writes)
  %(prog)s -g --disable-unhandled --suppress-rules SC2034
  # Apply SC2034 # shellcheck disable=SC2034 directives in place
  %(prog)s -g --disable-unhandled --suppress-rules SC2034 -w
  # Scope to non-archive / active scripts only (using --exclude or --dir)
  %(prog)s -g --exclude "*/archive/*" --disable-unhandled --suppress-rules SC2034 -w
  # run in dry-run mode for a specific target directory
  %(prog)s --dir files/scripts/some_largest_dir
  # run a dry-run scoped to SC2181
  %(prog)s --rules SC2181
  # run a dry-run scoped to SC2004, SC2046 and SC2268
  %(prog)s --rules SC2004 SC2046 SC2268
  # applies fixes in-place for a specific target directory
  %(prog)s --dir files/scripts/some_largest_dir -w
  %(prog)s files/scripts/docker/ --run-shellcheck
  %(prog)s files/scripts/certs/*.sh --run-shellcheck -w --rules SC2086
  %(prog)s -w --skip-vars cmd OPTIONS
        """,
    )

    parser.add_argument(
        "targets",
        nargs="*",
        type=Path,
        default=None,
        help=(
            f"Path to a ShellCheck text output log (default: {DEFAULT_ISSUES_LOG_PATH}), "
            "or shell script(s)/directories when --run-shellcheck is set."
        ),
    )
    parser.add_argument(
        "--dir",
        "--dirs",
        dest="dirs",
        nargs="+",
        action="append",
        type=Path,
        default=None,
        metavar="DIR",
        help="Target directory (or directories) to restrict edits/scanning to "
             "(e.g., --dir files/scripts/some_largest_dir).",
    )
    parser.add_argument(
        "--scan-paths",
        nargs="+",
        type=Path,
        default=None,
        metavar="PATH",
        help="Script files or directories to scan with shellcheck when generating a missing log "
             "(overrides --script-glob and --dir).",
    )
    parser.add_argument(
        "--script-glob",
        default=DEFAULT_SCRIPT_GLOB,
        metavar="PATTERN",
        help=f"Glob pattern used to discover shell scripts when generating "
             f"a missing log (default: {DEFAULT_SCRIPT_GLOB}).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Additional path, directory, or glob pattern to exclude during discovery (repeatable).",
    )
    parser.add_argument(
        "--rules",
        nargs="+",
        default=None,
        metavar="RULE",
        help="ShellCheck rule codes to handle (default: all rules with a registered handler).",
    )
    parser.add_argument(
        "--suppress-rules",
        nargs="+",
        default=None,
        metavar="RULE",
        help=(
            "Rule codes to suppress with '# shellcheck disable=...' when "
            "--disable-unhandled is set (default: all skipped/unhandled rules, "
            "e.g., --disable-unhandled --suppress-rules SC2034)."
        ),
    )
    parser.add_argument(
        "-r",
        "--run-shellcheck",
        action="store_true",
        help="Run 'shellcheck -f tty' directly on target files/directories instead of parsing a log file.",
    )
    parser.add_argument(
        "-w",
        "--write",
        action="store_true",
        help="Write updated content back to source files in place (default: dry-run preview).",
    )
    parser.add_argument(
        "-g",
        "--regenerate",
        action="store_true",
        help="Regenerate the ShellCheck log file even if it already exists.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Automatically generate missing log files without prompting.",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not prompt interactively when a log file is missing; fail immediately instead.",
    )
    parser.add_argument(
        "--use-rc",
        action="store_true",
        default=False,
        help="Respect .shellcheckrc instead of passing --norc when running shellcheck or generating a log.",
    )
    parser.add_argument(
        "--enable-rule",
        action="append",
        dest="enable_rules",
        default=None,
        metavar="RULE_OR_CHECK",
        help="Optional rule/check to pass via --enable (repeatable; omitted by default).",
    )
    parser.add_argument(
        "--exclude-rule",
        action="append",
        dest="exclude_rules",
        default=None,
        metavar="RULE_OR_CHECK",
        help="Optional rule/check to ignore via -i/--exclude when invoking shellcheck (repeatable).",
    )
    parser.add_argument(
        "--no-enable-handled",
        action="store_true",
        help="Deprecated/no-op kept for CLI compatibility; --enable is omitted unless --enable-rule is specified.",
    )
    parser.add_argument(
        "--no-convert-dot-source",
        dest="convert_dot_to_source",
        action="store_false",
        default=True,
        help="For SC1091: keep leading '.' source commands rather than converting them to 'source'.",
    )
    parser.add_argument(
        "--no-source-directive",
        dest="insert_source_directive",
        action="store_false",
        default=True,
        help="For SC1091: do not insert '# shellcheck source=...' directives above source statements.",
    )
    parser.add_argument(
        "--disable-unhandled",
        action="store_true",
        default=False,
        help="Add or merge '# shellcheck disable=SC...' directives for skipped or unhandled findings.",
    )
    parser.add_argument(
        "--skip-vars",
        nargs="+",
        default=[],
        metavar="VAR",
        help="For SC2086: additional variable names to skip quoting.",
    )
    parser.add_argument(
        "--include-vars",
        nargs="+",
        default=[],
        metavar="VAR",
        help="For SC2086: variable names to remove from the skip list so they are quoted.",
    )
    parser.add_argument(
        "--no-default-skip",
        action="store_true",
        help="For SC2086: disable the built-in skip list of multi-flag variables.",
    )
    parser.add_argument(
        "--top-dirs",
        type=int,
        default=DEFAULT_TOP_DIRS,
        metavar="N",
        help=f"Number of top directories to show per handled rule in the summary report (default: {DEFAULT_TOP_DIRS}).",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging verbosity (default: INFO).",
    )
    quote_mode_group = parser.add_mutually_exclusive_group()
    quote_mode_group.add_argument(
        "--quote-all-on-line",
        dest="quote_all_on_line",
        action="store_true",
        default=DEFAULT_QUOTE_ALL_ON_LINE,
        help="For SC2086: quote all unquoted variable expansions on a flagged line (default).",
    )
    quote_mode_group.add_argument(
        "--no-quote-all-on-line",
        dest="quote_all_on_line",
        action="store_false",
        help="For SC2086: fall back to quoting only the single variable matching/nearest to the caret.",
    )

    parsed = parser.parse_args(argv)
    if not parsed.targets:
        parsed.targets = [DEFAULT_ISSUES_LOG_PATH]

    flat_dirs: List[Path] = []
    if parsed.dirs:
        for group in parsed.dirs:
            flat_dirs.extend(group)
    parsed.target_dirs = flat_dirs
    return parsed


def configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(levelname)s: %(message)s",
    )


def strip_ansi(text: str) -> str:
    """Removes ANSI color/style escape sequences from ShellCheck TTY output."""
    return ANSI_ESCAPE_RE.sub("", text)


def _is_excluded(rel_str: str, rel_path: Path, excludes: Sequence[str]) -> bool:
    """Returns True if a relative path matches any extra exclude pattern."""
    for pattern in excludes:
        norm_pat = pattern.strip("/")
        if not norm_pat:
            continue
        if (
            rel_str == norm_pat
            or rel_str.startswith(f"{norm_pat}/")
            or norm_pat in rel_path.parts
            or fnmatch.fnmatch(rel_str, norm_pat)
        ):
            return True
    return False


def _discover_via_git(
    repo_root: Path,
    excludes: Sequence[str],
    extensions: Tuple[str, ...] = DEFAULT_SHELL_EXTENSIONS,
) -> Optional[List[Path]]:
    """
    Discovers shell scripts inside a Git worktree using `git ls-files`,
    honoring `.gitignore` (such as `save/`) while keeping `archive/` in scope.
    Returns None if `repo_root` is not inside a Git worktree or `git` is unavailable.
    """
    cmd = [
        "git",
        "-C",
        str(repo_root),
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "-z",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=False, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    scripts: List[Path] = []
    for raw_entry in proc.stdout.decode("utf-8").split("\x00"):
        if not raw_entry:
            continue
        rel_path = Path(raw_entry)
        if rel_path.suffix not in extensions:
            continue
        if _is_excluded(raw_entry, rel_path, excludes):
            continue
        scripts.append(repo_root / rel_path)

    return sorted(scripts)


def _discover_via_walk(
    root_dir: Path,
    excludes: Sequence[str],
    prune_dirs: Optional[Set[str]] = None,
    extensions: Tuple[str, ...] = DEFAULT_SHELL_EXTENSIONS,
) -> List[Path]:
    """Fallback shell script discovery when outside a Git worktree."""
    pruned = prune_dirs if prune_dirs is not None else DEFAULT_FALLBACK_PRUNE_DIRS
    scripts: List[Path] = []

    for current_root, dirnames, filenames in os.walk(root_dir):
        current_path = Path(current_root)
        rel_dir = current_path.relative_to(root_dir)
        rel_dir_str = "" if str(rel_dir) == "." else rel_dir.as_posix()

        # Mutate dirnames in-place so os.walk does not descend into pruned/excluded dirs.
        kept_dirs: List[str] = []
        for dirname in sorted(dirnames):
            if dirname in pruned:
                continue
            child_rel_str = f"{rel_dir_str}/{dirname}" if rel_dir_str else dirname
            child_rel_path = Path(child_rel_str)
            if _is_excluded(child_rel_str, child_rel_path, excludes):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for fname in sorted(filenames):
            if not fname.endswith(extensions):
                continue
            full_path = current_path / fname
            rel_path = full_path.relative_to(root_dir)
            if _is_excluded(rel_path.as_posix(), rel_path, excludes):
                continue
            scripts.append(full_path)

    return sorted(scripts)


def discover_repo_shell_scripts(
    root_dir: Path = Path("."),
    extra_excludes: Optional[Sequence[str]] = None,
    fallback_prune_dirs: Optional[Set[str]] = None,
    extensions: Tuple[str, ...] = DEFAULT_SHELL_EXTENSIONS,
) -> List[Path]:
    """
    Discovers shell scripts honoring `.gitignore` inside Git worktrees, with an
    `os.walk` fallback outside Git. Skips `save/` while keeping `archive/` in scope.
    """
    resolved_root = root_dir.resolve()
    excludes = list(extra_excludes) if extra_excludes else []

    git_results = _discover_via_git(
        repo_root=resolved_root,
        excludes=excludes,
        extensions=extensions,
    )
    if git_results is not None:
        logger.debug(
            "Discovered %d shell script(s) via git ls-files in %s",
            len(git_results),
            resolved_root,
        )
        return git_results

    walk_results = _discover_via_walk(
        root_dir=resolved_root,
        excludes=excludes,
        prune_dirs=fallback_prune_dirs,
        extensions=extensions,
    )
    logger.debug(
        "Discovered %d shell script(s) via directory walk in %s",
        len(walk_results),
        resolved_root,
    )
    return walk_results


def collect_shell_files(
    targets: Sequence[Path],
    extra_excludes: Optional[Sequence[str]] = None,
) -> List[Path]:
    """Expands file and directory paths into a sorted list of shell scripts."""
    excludes = list(extra_excludes) if extra_excludes else []
    collected: Set[Path] = set()
    cwd = Path.cwd().resolve()

    for target in targets:
        if target.is_file():
            resolved = target.resolve()
            try:
                rel = resolved.relative_to(cwd)
                if _is_excluded(rel.as_posix(), rel, excludes):
                    continue
            except ValueError:
                pass
            collected.add(target)
        elif target.is_dir():
            for script in discover_repo_shell_scripts(
                root_dir=target,
                extra_excludes=excludes,
            ):
                collected.add(script)
        else:
            logger.warning("Target path does not exist: %s", target)

    return sorted(collected)


def discover_scripts(
    scan_paths: Optional[Sequence[Path]] = None,
    script_glob: str = DEFAULT_SCRIPT_GLOB,
    extra_excludes: Optional[Sequence[str]] = None,
) -> List[Path]:
    """Resolves explicit scan_paths or discovers shell scripts."""
    excludes = list(extra_excludes) if extra_excludes else []
    if scan_paths:
        return collect_shell_files(scan_paths, extra_excludes=excludes)

    if script_glob == DEFAULT_SCRIPT_GLOB:
        return discover_repo_shell_scripts(root_dir=Path("."), extra_excludes=excludes)

    cwd = Path.cwd().resolve()
    matches: List[Path] = []
    for match_str in sorted(glob.glob(script_glob, recursive=True)):
        match_path = Path(match_str)
        if not match_path.is_file():
            continue
        resolved = match_path.resolve()
        try:
            rel = resolved.relative_to(cwd)
            if _is_excluded(rel.as_posix(), rel, excludes):
                continue
        except ValueError:
            pass
        matches.append(match_path)
    return matches


def build_shellcheck_command(
    files: Sequence[Path],
    enable_rules: Optional[Sequence[str]] = None,
    exclude_rules: Optional[Sequence[str]] = None,
    use_rc: bool = False,
) -> List[str]:
    """Builds the shellcheck command list."""
    cmd = ["shellcheck", "-f", "tty"]
    if not use_rc:
        cmd.append("--norc")
    if enable_rules:
        cmd.extend(["--enable", ",".join(r.upper() for r in enable_rules)])
    if exclude_rules:
        cmd.extend(["-i", ",".join(r.upper() for r in exclude_rules)])
    cmd.extend(str(f) for f in files)
    return cmd


def run_shellcheck(
    targets: Sequence[Path],
    enable_rules: Optional[Sequence[str]] = None,
    exclude_rules: Optional[Sequence[str]] = None,
    use_rc: bool = False,
    extra_excludes: Optional[Sequence[str]] = None,
) -> str:
    """Invokes `shellcheck` on target files/directories and returns its stdout."""
    files = collect_shell_files(targets, extra_excludes=extra_excludes)
    if not files:
        logger.warning("No shell scripts found in targets: %s", targets)
        return ""

    cmd = build_shellcheck_command(
        files=files,
        enable_rules=enable_rules,
        exclude_rules=exclude_rules,
        use_rc=use_rc,
    )
    logger.debug("Executing command: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"shellcheck failed with exit code {proc.returncode}: {proc.stderr.strip()}"
        )
    return proc.stdout


def prompt_generate_log(
    log_path: Path, assume_yes: bool = False, no_prompt: bool = False
) -> bool:
    """Asks the user whether to generate a missing ShellCheck log file."""
    if no_prompt:
        return False
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        return False

    try:
        answer = (
            input(
                f"ShellCheck log '{log_path}' does not exist. Generate it now? [y/N]: "
            )
            .strip()
            .lower()
        )
    except EOFError:
        return False

    return answer in ("y", "yes")


def generate_shellcheck_log(
    log_path: Path,
    scan_paths: Optional[Sequence[Path]] = None,
    script_glob: str = DEFAULT_SCRIPT_GLOB,
    enable_rules: Optional[Sequence[str]] = None,
    exclude_rules: Optional[Sequence[str]] = None,
    use_rc: bool = False,
    extra_excludes: Optional[Sequence[str]] = None,
) -> str:
    """Runs shellcheck across discovered scripts, writes output to log_path, and returns it."""
    files = discover_scripts(
        scan_paths=scan_paths,
        script_glob=script_glob,
        extra_excludes=extra_excludes,
    )
    if not files:
        raise FileNotFoundError(
            f"No shell scripts matched discovery criteria (glob '{script_glob}')"
        )

    cmd = build_shellcheck_command(
        files=files,
        enable_rules=enable_rules,
        exclude_rules=exclude_rules,
        use_rc=use_rc,
    )
    logger.debug("Executing command: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"shellcheck failed with exit code {proc.returncode}: {proc.stderr.strip()}"
        )

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(proc.stdout, encoding="utf-8")
    logger.info("Generated ShellCheck log at '%s'.", log_path)
    return proc.stdout


def parse_shellcheck_findings(raw_output: str) -> List[ShellCheckFinding]:
    """Parses ShellCheck TTY output into structured ShellCheckFinding entries."""
    clean_output = strip_ansi(raw_output)
    lines = clean_output.splitlines()
    findings: List[ShellCheckFinding] = []

    idx = 0
    while idx < len(lines):
        hdr_match = FILE_HEADER_RE.match(lines[idx])
        if not hdr_match:
            idx += 1
            continue

        filepath = hdr_match.group(1).strip()
        lineno = int(hdr_match.group(2))

        if idx + 1 >= len(lines):
            break

        src_line = lines[idx + 1]
        idx += 2

        while idx < len(lines) and not FILE_HEADER_RE.match(lines[idx]):
            caret_match = CARET_LINE_RE.match(lines[idx])
            if caret_match:
                caret_offset = len(caret_match.group(1))
                caret_len = len(caret_match.group(2))
                rule = caret_match.group(3).upper()
                severity = (caret_match.group(4) or "").lower()
                message = lines[idx][caret_match.end():].lstrip(" :")

                findings.append(
                    ShellCheckFinding(
                        filepath=filepath,
                        lineno=lineno,
                        src_line=src_line,
                        caret_offset=caret_offset,
                        caret_len=caret_len,
                        rule=rule,
                        message=message,
                        severity=severity,
                    )
                )
            idx += 1

    return findings


def collect_edits_with_unhandled(
    findings: Iterable[ShellCheckFinding],
    registry: RuleHandlerRegistry,
) -> Tuple[Dict[str, List[EditSpan]], List[ShellCheckFinding]]:
    """
    Dispatches findings to registered rule handlers.
    Returns `(edits_by_file, unhandled_or_skipped_findings)`.
    """
    edits_by_file: Dict[str, List[EditSpan]] = defaultdict(list)
    unhandled_or_skipped: List[ShellCheckFinding] = []
    unhandled_rules: Set[str] = set()

    for finding in findings:
        handler = registry.get(finding.rule)
        if handler is None:
            unhandled_rules.add(finding.rule)
            unhandled_or_skipped.append(finding)
            continue

        produced = list(handler(finding))
        if not produced:
            unhandled_or_skipped.append(finding)
            continue

        edits_by_file[finding.filepath].extend(produced)

    if unhandled_rules:
        logger.debug(
            "No handler registered for rules in output: %s",
            ", ".join(sorted(unhandled_rules)),
        )

    return dict(edits_by_file), unhandled_or_skipped


def collect_edits_from_findings(
    findings: Iterable[ShellCheckFinding],
    registry: RuleHandlerRegistry,
) -> Dict[str, List[EditSpan]]:
    """Dispatches findings to registered rule handlers and groups edits by file path."""
    edits_by_file, _ = collect_edits_with_unhandled(findings, registry)
    return edits_by_file


def parse_shellcheck_output(
    raw_output: str,
    registry: Optional[RuleHandlerRegistry] = None,
    rules: Optional[Sequence[str]] = None,
    skip_vars: Optional[Set[str]] = None,
    quote_all_on_line: bool = DEFAULT_QUOTE_ALL_ON_LINE,
) -> Dict[str, List[EditSpan]]:
    """
    Parses ShellCheck TTY output and produces candidate EditSpans grouped by file path
    using the provided registry (or a default registry).
    """
    active_registry = (
        registry
        if registry is not None
        else create_default_registry(
            rules=rules, skip_vars=skip_vars, quote_all_on_line=quote_all_on_line
        )
    )
    findings = parse_shellcheck_findings(raw_output)
    if rules:
        allowed = {r.upper() for r in rules}
        findings = [f for f in findings if f.rule.upper() in allowed]
    return collect_edits_from_findings(findings, active_registry)


def _is_already_quoted_nearby(
    line: str, start: int, end: int, expected_token: str
) -> bool:
    """
    Returns True if `expected_token` already appears wrapped in double or single
    quotes on `line` (accounting for cumulative quote-offset shifts on long lines).
    """
    _ = (start, end)
    if not expected_token:
        return False
    return f'"{expected_token}"' in line or f"'{expected_token}'" in line


def apply_edits_to_content_detailed(
    content: str,
    edits: Iterable[EditSpan],
) -> Tuple[str, int, Counter[str]]:
    """
    Applies replacement spans to file text content and returns
    (updated_content, applied_edit_count, applied_count_by_rule).
    """
    file_lines = content.splitlines(keepends=True)
    by_line: Dict[int, List[EditSpan]] = defaultdict(list)
    for edit in edits:
        by_line[edit.lineno].append(edit)

    applied_count = 0
    by_rule: Counter[str] = Counter()

    for lineno, line_edits in sorted(by_line.items()):
        if not (1 <= lineno <= len(file_lines)):
            logger.warning(
                "Line %d out of range (max %d); skipping.", lineno, len(file_lines)
            )
            continue

        orig_line = file_lines[lineno - 1]
        # Deduplicate identical spans and apply right-to-left so character offsets stay valid;
        # apply span replacements (end > start) before zero-width insertions (end == start) at start=0.
        unique_edits = sorted(
            set(line_edits),
            key=lambda e: (e.start, 1 if e.end > e.start else 0),
            reverse=True,
        )
        updated_line = orig_line

        for edit in unique_edits:
            actual_slice = updated_line[edit.start: edit.end]
            if edit.expected_original is None or actual_slice == edit.expected_original:
                updated_line = (
                    updated_line[: edit.start]
                    + edit.replacement
                    + updated_line[edit.end:]
                )
                applied_count += 1
                by_rule[(edit.rule or "UNKNOWN").upper()] += 1
            elif edit.expected_original and _is_already_quoted_nearby(
                updated_line, edit.start, edit.end, edit.expected_original
            ):
                logger.debug(
                    "Already quoted near line %d col %d (%s): token '%s'",
                    lineno,
                    edit.start,
                    edit.rule or "UNKNOWN",
                    edit.expected_original,
                )
            else:
                logger.warning(
                    "Token mismatch at line %d col %d (%s): expected '%s', found '%s'",
                    lineno,
                    edit.start,
                    edit.rule or "UNKNOWN",
                    edit.expected_original,
                    actual_slice,
                )

        file_lines[lineno - 1] = updated_line

    return "".join(file_lines), applied_count, by_rule


def apply_edits_to_content(
    content: str,
    edits: Iterable[EditSpan],
) -> Tuple[str, int]:
    """
    Applies replacement spans to file text content and returns
    (updated_content, applied_edit_count).
    """
    updated_content, applied_count, _ = apply_edits_to_content_detailed(content, edits)
    return updated_content, applied_count


def process_edits_detailed(
    edits_by_file: Dict[str, List[EditSpan]],
    write: bool = False,
    base_dir: Optional[Path] = None,
    unhandled_findings: Optional[Sequence[ShellCheckFinding]] = None,
    add_disable_for_unhandled: bool = False,
    suppress_rules: Optional[Sequence[str]] = None,
) -> Tuple[int, int, List[Tuple[str, str, int]]]:
    """
    Processes parsed edits (and optional `# shellcheck disable=` directives for
    skipped/unhandled findings) across all matched files.
    Returns (files_changed, total_edits_applied, per_file_rule_counts).
    """
    files_changed = 0
    total_edits = 0
    rule_records: List[Tuple[str, str, int]] = []

    all_candidate_files: Set[str] = set(edits_by_file.keys())
    content_by_file: Dict[str, str] = {}
    if add_disable_for_unhandled and unhandled_findings:
        for f in unhandled_findings:
            if f.filepath:
                all_candidate_files.add(f.filepath)

    for rel_path in sorted(all_candidate_files):
        target_path = (base_dir / rel_path) if base_dir else Path(rel_path)
        if not target_path.is_file():
            logger.warning("Target file not found, skipping: %s", target_path)
            continue

        try:
            orig_content = target_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.error("Failed reading '%s': %s", target_path, exc)
            continue

        content_by_file[rel_path] = orig_content

    disable_edits_by_file: Dict[str, List[EditSpan]] = {}
    if add_disable_for_unhandled and unhandled_findings:
        disable_edits_by_file = build_disable_edits_for_findings(
            findings_to_suppress=unhandled_findings,
            content_by_file=content_by_file,
            suppress_rules=suppress_rules,
        )

    for rel_path in sorted(all_candidate_files):
        orig_content = content_by_file.get(rel_path)
        if orig_content is None:
            continue

        combined_edits: List[EditSpan] = list(edits_by_file.get(rel_path, []))
        combined_edits.extend(disable_edits_by_file.get(rel_path, []))
        if not combined_edits:
            continue

        target_path = (base_dir / rel_path) if base_dir else Path(rel_path)
        updated_content, count, file_rule_counts = apply_edits_to_content_detailed(
            orig_content, combined_edits
        )
        if count == 0 or updated_content == orig_content:
            continue

        files_changed += 1
        total_edits += count
        for rule, rule_cnt in file_rule_counts.items():
            rule_records.append((rule, rel_path, rule_cnt))

        if write:
            try:
                target_path.write_text(updated_content, encoding="utf-8")
                logger.info("[UPDATED] %s (%d edits)", target_path, count)
            except Exception as exc:
                logger.error("Failed writing '%s': %s", target_path, exc)
        else:
            logger.info("[DRY-RUN] %s (%d candidate edits)", target_path, count)

    return files_changed, total_edits, rule_records


def process_edits(
    edits_by_file: Dict[str, List[EditSpan]],
    write: bool = False,
    base_dir: Optional[Path] = None,
) -> Tuple[int, int]:
    """
    Processes parsed edits across all matched files.
    Returns (files_changed, total_edits_applied).
    """
    files_changed, total_edits, _ = process_edits_detailed(
        edits_by_file=edits_by_file,
        write=write,
        base_dir=base_dir,
    )
    return files_changed, total_edits


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)

    skip_vars = build_effective_skip_vars(
        no_default_skip=args.no_default_skip,
        extra_skip=args.skip_vars,
        include_vars=args.include_vars,
    )
    registry = create_default_registry(
        rules=args.rules,
        skip_vars=skip_vars,
        quote_all_on_line=args.quote_all_on_line,
        convert_dot_to_source=args.convert_dot_to_source,
        insert_source_directive=args.insert_source_directive,
    )
    effective_scan_paths = args.scan_paths or (
        args.target_dirs if args.target_dirs else None
    )
    log_generated = False

    if args.run_shellcheck:
        shellcheck_targets = args.target_dirs if args.target_dirs else args.targets
        try:
            raw_output = run_shellcheck(
                shellcheck_targets,
                enable_rules=args.enable_rules,
                exclude_rules=args.exclude_rules,
                use_rc=args.use_rc,
                extra_excludes=args.exclude,
            )
        except Exception as exc:
            logger.error("%s", exc)
            return 1
    else:
        chunks: List[str] = []
        for log_file in args.targets:
            if args.regenerate or not log_file.is_file():
                should_generate = args.regenerate or prompt_generate_log(
                    log_file,
                    assume_yes=args.yes,
                    no_prompt=args.no_prompt,
                )
                if should_generate:
                    try:
                        generated = generate_shellcheck_log(
                            log_path=log_file,
                            scan_paths=effective_scan_paths,
                            script_glob=args.script_glob,
                            enable_rules=args.enable_rules,
                            exclude_rules=args.exclude_rules,
                            use_rc=args.use_rc,
                            extra_excludes=args.exclude,
                        )
                    except Exception as exc:
                        logger.error("%s", exc)
                        return 1
                    log_generated = True
                    chunks.append(generated)
                else:
                    logger.error("ShellCheck log file not found: %s", log_file)
                    return 1
            else:
                chunks.append(log_file.read_text(encoding="utf-8", errors="replace"))
        raw_output = "\n".join(chunks)

    parsed_findings = parse_shellcheck_findings(raw_output)
    filtered_findings = (
        [
            f
            for f in parsed_findings
            if f.rule.upper() in {r.upper() for r in args.rules}
        ]
        if args.rules
        else parsed_findings
    )
    filtered_findings = filter_findings_by_directories(
        filtered_findings, target_dirs=args.target_dirs
    )

    edits_by_file, unhandled_findings = collect_edits_with_unhandled(
        filtered_findings, registry
    )
    if unhandled_findings:
        skipped_by_rule: Counter[str] = Counter(
            (f.rule or "UNKNOWN").upper() for f in unhandled_findings
        )
        skipped_summary = ", ".join(
            f"{rule}: {cnt}"
            for rule, cnt in sorted(skipped_by_rule.items(), key=lambda x: (-x[1], x[0]))
        )
        logger.info(
            "Skipped %d finding(s) without direct edits (%s).",
            len(unhandled_findings),
            skipped_summary,
        )

    edits_by_file = filter_edits_by_directories(
        edits_by_file, target_dirs=args.target_dirs
    )

    files_changed, total_edits, rule_records = process_edits_detailed(
        edits_by_file,
        write=args.write,
        unhandled_findings=unhandled_findings,
        add_disable_for_unhandled=args.disable_unhandled,
        suppress_rules=args.suppress_rules,
    )

    mode_label = "applied" if args.write else "candidate"
    logger.info(
        "Summary: %d %s edit(s) across %d file(s).",
        total_edits,
        mode_label,
        files_changed,
    )

    if log_generated:
        parsed_summary = format_parsed_findings_summary(
            findings=filtered_findings,
            handled_rules=registry.supported_rules(),
            candidate_edits_by_file=edits_by_file,
        )
        counts_by_rule = build_handled_rule_dir_counts(
            rule_edit_records=rule_records,
            handled_rules=registry.supported_rules(),
        )
        report = format_handled_rule_dir_report(
            counts_by_rule=counts_by_rule,
            mode_label=mode_label,
            top_n=max(1, args.top_dirs),
        )
        print(f"\n{parsed_summary}\n\n{report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
