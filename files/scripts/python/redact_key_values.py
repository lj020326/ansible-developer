#!/usr/bin/env python3
"""
Utility to redact sensitive key values from INI/Shell scripts and YAML files.
Supports single-line and multiline shell/INI variable assignments.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional

# Default patterns to trigger redaction
DEFAULT_REDACT_KEYS = [
    "key",
    "password",
    "pwd",
    "secret",
    "token",
]

# Supported formats
FORMAT_AUTO = "auto"
FORMAT_ENV_INI = "ini"
FORMAT_YAML = "yaml"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Redact sensitive fields from config/shell/yaml files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s config.yaml
  %(prog)s -w input.env
  %(prog)s -p 2 -w credentials.ini
  %(prog)s -m exact -w input.env
  %(prog)s -m boundary -p 2 -w credentials.ini
  %(prog)s --match-type boundary --case-sensitive -w input.yml output.yml
        """,
    )

    parser.add_argument(
        "source_file",
        type=Path,
        help="Path to the source file to redact.",
    )
    parser.add_argument(
        "output_file",
        type=Path,
        nargs="?",
        default=None,
        help="Optional path to output file (used with -w/--write).",
    )
    parser.add_argument(
        "-m",
        "--match-type",
        choices=["exact", "boundary", "substring"],
        default="boundary",
        help="Matching mode: 'exact' (full key match), 'boundary' (delimited/word-boundary match), 'none' (pure substring match). Default: boundary.",
    )
    parser.add_argument(
        "-c",
        "--case-sensitive",
        action="store_true",
        help="Enable case-sensitive key matching.",
    )
    parser.add_argument(
        "-w",
        "--write",
        action="store_true",
        help="Save redacted output to a file instead of only displaying it.",
    )
    parser.add_argument(
        "-p",
        "--peek",
        type=int,
        metavar="N",
        default=0,
        help="Peek/show the first and last N characters of sensitive values.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=[FORMAT_AUTO, FORMAT_ENV_INI, FORMAT_YAML],
        default=FORMAT_AUTO,
        help="Force file parsing format (default: auto-detect by extension).",
    )

    return parser.parse_args()


def redact_value(val: str, peek_count: int) -> str:
    """Masks a string value, optionally preserving 'peek_count' characters at start/end."""
    clean_val = val.strip()
    length = len(clean_val)

    if not clean_val:
        return ""

    if peek_count <= 0 or length <= (peek_count * 2):
        return "<redacted>"

    first_n = clean_val[:peek_count]
    last_n = clean_val[-peek_count:]
    return f"{first_n}...<redacted>...{last_n}"


def build_key_regex(
    keys: List[str], match_type: Optional[str], case_sensitive: bool
) -> re.Pattern:
    """
    Compiles a multiline-aware regex pattern that captures single or multi-line assignments.

    match_type choices:
      - 'exact': Matches exact key name (e.g. 'key').
      - 'boundary': Matches keys delimited by word boundaries/underscores/dashes (e.g. 'API_KEY', 'SECRET_PWD').
      - 'substring': Unrestricted substring match (e.g. 'KEYCLOAK_USER').
    """
    flags = re.MULTILINE if case_sensitive else (re.MULTILINE | re.IGNORECASE)
    escaped_keys = [re.escape(k) for k in keys]

    if match_type == "exact":
        key_pattern = r"(?P<key>" + "|".join(escaped_keys) + r")"
    elif match_type == "boundary":
        # Match keys bounded by start/end of key, word boundaries, or delimiters (_, -, .)
        boundary_pattern = "|".join(
            [r"(?:^|[\b_.-]|\b)" + k + r"(?:[\b_.-]|\b|$)" for k in escaped_keys]
        )
        # Target whole variable names containing the boundary match
        key_pattern = r"(?P<key>[A-Za-z0-9_.-]*?(?:" + boundary_pattern + r")[A-Za-z0-9_.-]*?)"
    elif match_type == "substring":
        key_pattern = r"(?P<key>\S*?(" + "|".join(escaped_keys) + r")\S*?)"
    else:
        raise ValueError(f"Got an invalid match_type ({match_type}).")

    # Restrict whitespace to [ \t]* so prefix/suffix never consume \n
    pattern = (
        r"^(?P<prefix>[ \t]*(?:export[ \t]+)?)"
        + key_pattern
        + r"(?P<suffix>[ \t]*[:=][ \t]*)"
        + r"(?P<val>'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|[^\r\n]*)"
    )

    return re.compile(pattern, flags)


def process_env_ini(
    content: str,
    keys: List[str],
    match_type: Optional[str],
    case_sensitive: bool,
    peek_count: int,
) -> str:
    """Processes INI/Shell variables, handling single-line and multiline quoted values."""
    regex = build_key_regex(keys, match_type, case_sensitive)

    def _replace_match(match: re.Match) -> str:
        prefix = match.group("prefix") or ""
        key = match.group("key")
        suffix = match.group("suffix")
        raw_val = match.group("val")

        # Preliminary check for empty value
        if not raw_val or not raw_val.strip():
            return f"{prefix}{key}{suffix}"

        # Detect quote wrapping
        quote_char = ""
        unquoted = raw_val.strip()
        if (unquoted.startswith("'") and unquoted.endswith("'")) or (
            unquoted.startswith('"') and unquoted.endswith('"')
        ):
            quote_char = unquoted[0]
            unquoted = unquoted[1:-1]

        # Handle trailing comments on unquoted assignments
        comment_space = ""
        comment = ""
        if not quote_char:
            comment_match = re.search(r"(\s+)(#.*|\;.*)$", unquoted)
            if comment_match:
                comment_space = comment_match.group(1)
                comment = comment_match.group(2)
                unquoted = unquoted[: comment_match.start()]

        if not unquoted.strip():
            return f"{prefix}{key}{suffix}{comment_space}{comment}"

        # Check for list delimiters (semicolons or commas)
        delimiter = None
        if ";" in unquoted:
            delimiter = ";"
        elif "," in unquoted:
            delimiter = ","

        if delimiter:
            # Split items, redact each non-empty entry, and rejoin with the original delimiter
            items = unquoted.split(delimiter)
            redacted_items = [
                redact_value(" ".join(item.split()), peek_count) if item.strip() else ""
                for item in items
            ]
            new_val = delimiter.join(redacted_items)
        else:
            cleaned_str = " ".join(unquoted.split())
            new_val = redact_value(cleaned_str, peek_count)

        return f"{prefix}{key}{suffix}{quote_char}{new_val}{quote_char}{comment_space}{comment}"

    return regex.sub(_replace_match, content)


def matches_key(
    key_name: str, keys: List[str], match_type: Optional[str], case_sensitive: bool
) -> bool:
    """Helper to evaluate key names for YAML dictionary traversal based on match_type."""
    if not case_sensitive:
        key_name = key_name.lower()
        keys = [k.lower() for k in keys]

    if match_type == "exact":
        return key_name in keys
    elif match_type == "boundary":
        for k in keys:
            pattern = r"(?:^|[_\b.-]|\b)" + re.escape(k) + r"(?:[_\b.-]|\b|$)"
            if re.search(pattern, key_name):
                return True
        return False
    elif match_type == "substring":
        # Substring search
        return any(k in key_name for k in keys)
    else:
        raise ValueError(f"Got an invalid match_type ({match_type}).")


def process_yaml(
    content: str,
    keys: List[str],
    match_type: Optional[str],
    case_sensitive: bool,
    peek_count: int,
) -> str:
    """Redacts YAML structures safely using PyYAML if available, falling back to Regex."""
    try:
        import yaml
    except ImportError:
        # Fallback to line regex processing if PyYAML is not installed
        return process_env_ini(content, keys, match_type, case_sensitive, peek_count)

    def _walk_and_redact(data):
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(k, str) and matches_key(k, keys, match_type, case_sensitive):
                    if isinstance(v, (str, int, float)) and str(v).strip():
                        data[k] = redact_value(str(v), peek_count)
                else:
                    _walk_and_redact(v)
        elif isinstance(data, list):
            for item in data:
                _walk_and_redact(item)

    try:
        parsed = yaml.safe_load(content)
        if parsed is not None:
            _walk_and_redact(parsed)
            return yaml.dump(parsed, sort_keys=False, default_flow_style=False)
    except Exception:
        # Fallback to line regex if YAML parsing fails (e.g., template tokens present)
        pass

    return process_env_ini(content, keys, match_type, case_sensitive, peek_count)


def determine_target_path(source_path: Path, output_arg: Optional[Path]) -> Path:
    if output_arg:
        return output_arg

    stem = source_path.stem
    suffixes = "".join(source_path.suffixes)

    if not suffixes:
        return source_path.parent / f"{stem}.redacted"

    return source_path.parent / f"{stem}.redacted{suffixes}"


def main():
    args = parse_args()

    if not args.source_file.is_file():
        print(
            f"Error: Source file '{args.source_file}' missing or not found.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Detect format
    fmt = args.format
    if fmt == FORMAT_AUTO:
        ext = args.source_file.suffix.lower()
        if ext in [".yaml", ".yml"]:
            fmt = FORMAT_YAML
        else:
            fmt = FORMAT_ENV_INI

    try:
        content = args.source_file.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading source file: {e}", file=sys.stderr)
        sys.exit(1)

    # Process content
    if fmt == FORMAT_YAML:
        redacted_content = process_yaml(
            content,
            DEFAULT_REDACT_KEYS,
            args.match_type,
            args.case_sensitive,
            args.peek,
        )
    else:
        redacted_content = process_env_ini(
            content,
            DEFAULT_REDACT_KEYS,
            args.match_type,
            args.case_sensitive,
            args.peek,
        )

    # Print output
    print("--- REDACTED CONTENT START ---")
    print(redacted_content)
    print("--- REDACTED CONTENT END ---")

    # Write output if requested
    if args.write:
        target_path = determine_target_path(args.source_file, args.output_file)
        try:
            target_path.write_text(redacted_content, encoding="utf-8")
            print(f"\nSuccess! Redacted file saved to: {target_path}")
        except Exception as e:
            print(f"\nError writing to file '{target_path}': {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
