#!/usr/bin/env python3
"""
Repository Directory Packaging Tool
Packages source code within a directory into a unified, token-optimized YAML file
for AI/LLM context interactions. Handles symbolic links cleanly without content duplication.
"""

import argparse
import datetime
import fnmatch
import logging
import os
import re
import subprocess
import sys
import yaml

from argparse import RawTextHelpFormatter
from pathlib import Path

# Script metadata matching template structure
__scriptName__ = os.path.basename(sys.argv[0])
__version__ = "2026.11.06"
__updated__ = "7 November 2026"

# --- Configuration Defaults ---
BASE_EXCLUDE_DIRS = [
    ".git",
    ".idea",
    ".code_index",
    ".DS_Store",
    ".test",
    ".tmp",
    "vault",
    ".vault",
    "__pycache__",
    "output",
    "save",
    "assets",
    "build",
    "releases",
    "archive",
    "old",
]
FILE_EXT_EXCLUDES = r"\.(svg|png|jpg|jpeg|gif|ico|webp|pdf|zip|tar|gz|7z)$"
DEFAULT_OUTPUT_FILENAME = ".package_dir.context.yml"
DEFAULT_CONFIG_FILENAME = ".package_dir.yml"
DEFAULT_MAX_SUBDIR_LINES = 20000  # soft budget per first-level subdir
DEFAULT_MAX_SUBDIR_FILES = 200

log = logging.getLogger(__scriptName__)


def setup_logging(loglevel_str="INFO"):
    """Sets up the script logger and applies the requested logging level."""
    loglevel = getattr(logging, loglevel_str.upper(), logging.INFO)
    log.setLevel(loglevel)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if not log.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        log.addHandler(handler)
    else:
        log.handlers[0].setLevel(loglevel)


# Custom PyYAML Dumper to format multiline strings using block scalar '|'
class LiteralBlockYamlDumper(yaml.SafeDumper):
    pass


def _represent_multiline_str(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


LiteralBlockYamlDumper.add_representer(str, _represent_multiline_str)


def _rel_top_component(rel_path: str) -> str | None:
    """'roles/foo/tasks/main.yml' -> 'roles'; 'README.md' -> None."""
    parts = Path(rel_path).parts
    return parts[0] if len(parts) >= 2 else None


def matches_gitignore_pattern(rel_path: str, path_from_root: str, pattern: str) -> bool:
    """
    Checks if a relative path matches a gitignore-style pattern.
    - Anchored patterns (start with '/' or contain '/') are checked against `path_from_root`.
    - Unanchored patterns are checked against `rel_path` components or filename.
    """
    pat = pattern.strip()
    if not pat or pat.startswith("#"):
        return False

    clean_pat = pat.rstrip("/")
    is_anchored = clean_pat.startswith("/") or "/" in clean_pat
    if clean_pat.startswith("/"):
        clean_pat = clean_pat[1:]

    if is_anchored:
        if path_from_root == clean_pat or path_from_root.startswith(clean_pat + "/"):
            return True
        if fnmatch.fnmatch(path_from_root, clean_pat) or fnmatch.fnmatch(
            path_from_root, clean_pat + "/*"
        ):
            return True
    else:
        path_parts = Path(rel_path).parts
        if clean_pat in path_parts:
            return True
        if fnmatch.fnmatch(Path(rel_path).name, clean_pat):
            return True
        for part in path_parts:
            if fnmatch.fnmatch(part, clean_pat):
                return True

    return False


def should_exclude_path(
    rel_path: str, path_from_root: str, base_excludes: list[str], custom_ignores: list[str]
) -> bool:
    """Evaluates whether a relative path should be excluded based on base rules and gitignore patterns."""
    parts = Path(rel_path).parts
    for base in base_excludes:
        if base in parts:
            return True

    for pat in custom_ignores:
        if matches_gitignore_pattern(rel_path, path_from_root, pat):
            return True

    return False


def _summarize_directory(
    dir_path: Path,
    rel_dir: str,
    member_files: list[str],
    symlink_metadata: dict[str, str],
    line_count: int,
) -> str:
    """Compact summary when a subdir exceeds the threshold."""
    # Sample up to N leaf names for orientation
    sample = sorted(member_files)[:25]
    more = len(member_files) - len(sample)
    sample_block = "\n".join(f"  - {p}" for p in sample)
    if more > 0:
        sample_block += f"\n  - ... and {more} more files"

    file_count = sum(1 for m in member_files if m not in symlink_metadata)
    symlink_count = sum(1 for m in member_files if m in symlink_metadata)

    child_hint = ""
    abs_sub = dir_path / rel_dir
    if abs_sub.is_dir():
        children = sorted(
            p.name
            for p in abs_sub.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        )
        if children:
            child_hint = f"\nImmediate subdirectories ({len(children)}):\n" + "\n".join(
                f"  - {c}" for c in children[:40]
            )
            if len(children) > 40:
                child_hint += f"\n  - ... and {len(children) - 40} more"

    return (
        f"# OVERSIZED DIRECTORY SUMMARY — full content omitted\n"
        f"# path: {rel_dir}/\n"
        f"# files: {file_count}  symlinks: {symlink_count}  approx_lines: {line_count}\n"
        f"# ACTION: Re-run package_dir on this path for full context, e.g.:\n"
        f"#   python -m crewai_doc_agent.package_dir --strip-comments {rel_dir}\n"
        f"# Or for each child role under roles/:\n"
        f"#   python -m crewai_doc_agent.package_dir --strip-comments roles/<role_name>\n"
        f"{child_hint}\n"
        f"Sample paths:\n{sample_block}\n"
    )


# --- Code Stripping / Compression Helpers ---
def strip_comments_and_blanks(
    content: str, ext: str, strip_comments: bool, strip_blanks: bool
) -> str:
    """Strips comments and/or blank lines based on file extension."""
    if not content.strip():
        return content

    cleaned = content
    if strip_comments:
        # Python, Bash, Shell, YAML, TOML, Dockerfile
        if ext in {
            ".py",
            ".sh",
            ".bash",
            ".yaml",
            ".yml",
            ".toml",
            ".dockerfile",
            ".r",
            ".pl",
        }:
            cleaned = re.sub(r"^\s*#.*$", "", cleaned, flags=re.MULTILINE)
        # C, C++, Java, JS, TS, Go, Rust, PHP, C#
        elif ext in {
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".cs",
            ".go",
            ".rs",
            ".php",
            ".swift",
            ".kt",
        }:
            # Block comments
            cleaned = re.sub(r"/\*[\s\S]*?\*/", "", cleaned)
            # Line comments
            cleaned = re.sub(r"^\s*//.*$", "", cleaned, flags=re.MULTILINE)
        # HTML, XML
        elif ext in {".html", ".xml", ".htm"}:
            cleaned = re.sub(r"<!--[\s\S]*?-->", "", cleaned)

    if strip_blanks:
        lines = [line for line in cleaned.splitlines() if line.strip()]
        cleaned = "\n".join(lines)

    return cleaned


def is_binary_file(file_path: Path, chunk_size: int = 1024) -> bool:
    """Check if file is binary by mime-type or null byte inspection."""
    if file_path.stat().st_size == 0:
        return False

    # Try system 'file' command if available
    # noinspection broad-exception
    try:
        res = subprocess.run(
            ["file", "-L", "-b", "--mime", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if "charset=binary" in res.stdout:
            return True
    except Exception:
        pass

    # Fallback byte inspection
    # noinspection broad-exception
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(chunk_size)
            if b"\0" in chunk:
                return True
    except Exception:
        return True
    return False


def build_tree(files: list[str], symlink_metadata: dict[str, str] = {}) -> str:
    """Generates a text-based ASCII directory tree summary, explicitly marking symlinks."""
    tree = {}
    for path in sorted(files):
        parts = path.split("/")
        curr = tree
        for part in parts:
            curr = curr.setdefault(part, {})

    def render_tree(
        d: dict, prefix: str = "", current_path_parts: list[str] = []
    ) -> list[str]:
        lines = []
        keys = sorted(d.keys())
        for i, key in enumerate(keys):
            is_last = i == len(keys) - 1
            connector = "└── " if is_last else "├── "

            node_path = "/".join(current_path_parts + [key])
            display_key = key
            if node_path in symlink_metadata:
                target_ref = symlink_metadata[node_path]
                display_key = f"{key} -> {target_ref} [symlink]"

            lines.append(f"{prefix}{connector}{display_key}")
            if d[key]:
                extension = "    " if is_last else "│   "
                lines.extend(
                    render_tree(d[key], prefix + extension, current_path_parts + [key])
                )
        return lines

    return "\n".join(["."] + render_tree(tree))


def get_git_commit_info(dir_path: Path) -> tuple[str, str]:
    """Retrieves current Git commit hash and active branch if in a Git repo."""
    commit_hash = "N/A"
    branch_name = "N/A"
    # noinspection broad-exception
    try:
        res = subprocess.run(
            ["git", "-C", str(dir_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            commit_hash = res.stdout.strip()

        res_branch = subprocess.run(
            ["git", "-C", str(dir_path), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res_branch.returncode == 0:
            branch_name = res_branch.stdout.strip()
    except Exception:
        pass

    return commit_hash, branch_name


def find_config_file(target_dir: Path, explicit_config: str = None) -> Path | None:
    """Finds the configuration file following priority rules:
    1) Explicit argument path if provided.
    2) target_dir / '.package_dir.yml'
    3) Git repo top-level directory / '.package_dir.yml'
    """
    if explicit_config:
        p = Path(explicit_config).resolve()
        return p if p.exists() else None

    # 1) Check inside target directory
    candidate = target_dir / DEFAULT_CONFIG_FILENAME
    if candidate.exists():
        return candidate

    # 2) Check git repo top-level directory
    # noinspection broad-exception
    try:
        res = subprocess.run(
            ["git", "-C", str(target_dir), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            git_top = Path(res.stdout.strip())
            candidate_git = git_top / DEFAULT_CONFIG_FILENAME
            if candidate_git.exists():
                return candidate_git
    except Exception:
        pass

    return None


def load_config_ignores(config_path: Path | None) -> list[str]:
    """Loads custom_ignores patterns from the given YAML config file."""
    if not config_path or not config_path.exists():
        return []

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                ignores = data.get("custom_ignores", [])
                if isinstance(ignores, list):
                    return [str(item) for item in ignores if item]
    except Exception as e:
        log.warning(f"Failed to parse config file '{config_path}': {e}")

    return []


def main():
    prog_usage = f"""
Examples of use:
  {__scriptName__}
  {__scriptName__} my_project
  {__scriptName__} -c .package_dir.yml my_project
  {__scriptName__} -s 15 my_project
  {__scriptName__} -n my_project node_modules .venv
  {__scriptName__} -L DEBUG my_project
  {__scriptName__} --strip-comments --strip-blank-lines my_project
  {__scriptName__} -o /tmp/custom_context.yaml my_project
"""

    parser = argparse.ArgumentParser(
        formatter_class=RawTextHelpFormatter,
        description="Repository Directory Packaging Tool\n"
                    "Packages source code into a YAML file optimized for AI/LLM interactions.",
        epilog=prog_usage,
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__} ({__updated__})",
    )
    parser.add_argument(
        "-L",
        "--loglevel",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        default="INFO",
        help="Set log level (default: INFO)",
    )

    parser.add_argument(
        "directory_path",
        nargs="?",
        default=".",
        help="Path to the directory to package (default: current directory '.')",
    )
    parser.add_argument(
        "custom_ignores",
        nargs="*",
        help="Additional directory or file patterns to ignore via CLI",
    )
    parser.add_argument(
        "-c",
        "--config",
        dest="config_file_path",
        help="Path to config file (default: .package_dir.yml in target or git root)",
    )
    parser.add_argument(
        "-o", "--output", dest="output_file_custom", help="Custom output file path"
    )
    parser.add_argument(
        "-s",
        "--size-threshold",
        dest="size_threshold_mb",
        type=int,
        default=10,
        help="File size threshold warning in MB (default: 10)",
    )
    parser.add_argument(
        "-n",
        "--no-git",
        dest="no_git",
        action="store_true",
        help="Disable Git integration. Forces standard file search",
    )

    # Optimization options
    parser.add_argument(
        "--strip-comments",
        action="store_true",
        help="Remove code comments to save tokens",
    )
    parser.add_argument(
        "--strip-blank-lines",
        action="store_true",
        help="Remove empty lines to save tokens",
    )
    parser.add_argument(
        "--max-file-size-kb",
        type=int,
        default=500,
        help="Skip individual files exceeding this size in KB (default: 500)",
    )
    parser.add_argument(
        "--max-subdir-lines",
        type=int,
        default=DEFAULT_MAX_SUBDIR_LINES,
        help="If a top-level subdir exceeds this many lines, emit a summary + re-package hint instead of full content",
    )
    parser.add_argument(
        "--max-subdir-files",
        type=int,
        default=DEFAULT_MAX_SUBDIR_FILES,
        help="If a top-level subdir exceeds this many regular files, treat as oversized",
    )

    args = parser.parse_args()
    setup_logging(args.loglevel)

    log.debug("Starting directory packaging process")

    dir_path = Path(args.directory_path).resolve()
    if not dir_path.exists() or not dir_path.is_dir():
        log.error(
            f"Directory path '{args.directory_path}' does not exist or is not a directory."
        )
        sys.exit(1)

    directory_name = dir_path.name if dir_path.name else "root"

    # Target directory path for file output incorporating the directory name
    if args.output_file_custom:
        output_file = Path(args.output_file_custom).resolve()
    else:
        output_file = dir_path / f".package_dir.{directory_name}.yml"

    log.info(f"Target output path: {output_file}")

    # --- Load Configuration File ---
    config_file = find_config_file(dir_path, args.config_file_path)
    config_ignores = []
    if config_file:
        log.info(f"Loaded configuration from: {config_file}")
        config_ignores = load_config_ignores(config_file)
    else:
        log.debug("No configuration file (.package_dir.yml) found; using defaults.")

    # Combine CLI custom ignores and config file custom ignores
    combined_ignores = list(set(args.custom_ignores + config_ignores))
    file_ext_exclude_regex = re.compile(FILE_EXT_EXCLUDES)

    use_git = not args.no_git
    is_git_repo = False
    git_toplevel = dir_path

    if use_git:
        # noinspection broad-exception
        try:
            res = subprocess.run(
                ["git", "-C", str(dir_path), "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                is_git_repo = True
                git_toplevel = Path(res.stdout.strip())
        except Exception:
            is_git_repo = False

    log.info(f"Packaging directory: {directory_name}")

    candidate_paths: list[str] = []
    symlink_metadata: dict[str, str] = {}  # Tracks rel_path -> symlink target string

    if is_git_repo:
        log.debug("Strategy: Git tracking (observing .gitignore rules)")

        try:
            # Use --full-name so paths are always relative to the git repo root
            res = subprocess.run(
                [
                    "git",
                    "-C",
                    str(dir_path),
                    "ls-files",
                    "--full-name",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            raw_candidates = [
                line.strip() for line in res.stdout.splitlines() if line.strip()
            ]

            # Compute relative prefix from git root to dir_path
            rel_prefix = os.path.relpath(dir_path, git_toplevel)
            if rel_prefix == ".":
                rel_prefix = ""

            for rel_from_root in raw_candidates:
                # If packaging a subdirectory, filter candidates to only those inside dir_path
                if rel_prefix:
                    if not (
                        rel_from_root == rel_prefix
                        or rel_from_root.startswith(rel_prefix + "/")
                    ):
                        continue
                    # Make path relative to dir_path for consistency with standard search
                    rel = os.path.relpath(git_toplevel / rel_from_root, dir_path)
                else:
                    rel = rel_from_root

                path_from_root = rel_from_root

                if should_exclude_path(rel, path_from_root, BASE_EXCLUDE_DIRS, combined_ignores):
                    continue
                if file_ext_exclude_regex.search(rel):
                    log.debug(f"Skipping excluded extension: {rel}")
                    continue

                full_candidate = dir_path / rel
                # Explicit check for symlinks in Git repositories
                if full_candidate.is_symlink():
                    # noinspection broad-exception
                    try:
                        target = os.readlink(full_candidate)
                        symlink_metadata[rel] = target
                        candidate_paths.append(rel)
                        log.debug(f"Detected symlink entity: {rel} -> {target}")
                        continue
                    except Exception:
                        pass

                candidate_paths.append(rel)
        except Exception as e:
            log.error(f"Error executing git ls-files: {e}")
            sys.exit(1)
    else:
        log.debug("Strategy: Standard file search (ignoring Git tracking)")

        for root, dirs, files in os.walk(dir_path, followlinks=False):
            rel_root = os.path.relpath(root, dir_path)
            if rel_root == ".":
                rel_root = ""

            rel_prefix = os.path.relpath(dir_path, git_toplevel)
            if rel_prefix == ".":
                rel_prefix = ""

            # Prune excluded directories in-place
            dirs[:] = [
                d
                for d in dirs
                if not should_exclude_path(
                    os.path.join(rel_root, d) if rel_root else d,
                    os.path.join(rel_prefix, rel_root, d) if rel_prefix else (os.path.join(rel_root, d) if rel_root else d),
                    BASE_EXCLUDE_DIRS,
                    combined_ignores,
                )
            ]

            # Also check if any subdirectory itself is a symlink
            active_dirs = list(dirs)
            for d in active_dirs:
                d_path = Path(root) / d
                if d_path.is_symlink():
                    rel_d_path = os.path.join(rel_root, d) if rel_root else d
                    path_from_root_d = os.path.join(rel_prefix, rel_d_path) if rel_prefix else rel_d_path
                    if not should_exclude_path(
                        rel_d_path, path_from_root_d, BASE_EXCLUDE_DIRS, combined_ignores
                    ):
                        # noinspection broad-exception
                        try:
                            target = os.readlink(d_path)
                            symlink_metadata[rel_d_path] = target
                            candidate_paths.append(rel_d_path)
                            log.debug(
                                f"Detected symlink directory: {rel_d_path} -> {target}"
                            )
                        except Exception:
                            pass
                    # Remove from recursive walk traversal to prevent duplication
                    dirs.remove(d)

            for file in files:
                rel_file_path = os.path.join(rel_root, file) if rel_root else file
                path_from_root_f = os.path.join(rel_prefix, rel_file_path) if rel_prefix else rel_file_path

                if should_exclude_path(
                    rel_file_path, path_from_root_f, BASE_EXCLUDE_DIRS, combined_ignores
                ):
                    continue
                if file_ext_exclude_regex.search(rel_file_path):
                    continue

                full_file_path = Path(root) / file
                if full_file_path.is_symlink():
                    # noinspection broad-exception
                    try:
                        target = os.readlink(full_file_path)
                        symlink_metadata[rel_file_path] = target
                        candidate_paths.append(rel_file_path)
                        continue
                    except Exception:
                        pass

                candidate_paths.append(rel_file_path)

    # Pre-scan: group candidates by top-level component
    by_top: dict[str, list[str]] = {}
    root_files: list[str] = []
    for rel in candidate_paths:
        top = _rel_top_component(rel)
        if top is None:
            root_files.append(rel)
        else:
            by_top.setdefault(top, []).append(rel)

    # Cheap line estimate: count lines only for grouping decision
    oversized: dict[str, dict] = {}
    for top, members in by_top.items():
        regular_file_members = [m for m in members if m not in symlink_metadata]
        symlink_members = [m for m in members if m in symlink_metadata]

        file_count = len(regular_file_members)
        symlink_count = len(symlink_members)

        # Check thresholds based on regular files first, or evaluate lines
        if file_count <= args.max_subdir_files:
            lines = 0
            for m in regular_file_members:
                fp = dir_path / m
                if fp.is_file() and not is_binary_file(fp):
                    # noinspection broad-exception
                    try:
                        lines += sum(
                            1 for _ in open(fp, "r", encoding="utf-8", errors="replace")
                        )
                    except Exception:
                        pass
            if lines <= args.max_subdir_lines:
                continue
            line_count = lines
        else:
            line_count = -1

        oversized[top] = {
            "path": top,
            "file_count": file_count,
            "symlink_count": symlink_count,
            "approx_lines": line_count if line_count >= 0 else "unknown",
            "recommend_repackage": True,
            "repackage_command": f"python -m crewai_doc_agent.package_dir --strip-comments {top}",
            "note": (
                f"Directory '{top}/' exceeds threshold "
                f"(files>{args.max_subdir_files} or lines>{args.max_subdir_lines}). "
                "Full contents omitted; re-run package_dir on this path."
            ),
        }

    # When processing files: skip members of oversized tops; inject one summary entry each
    processed_files = {}
    file_list = []
    total_lines = 0
    skip_prefixes = set(oversized.keys())

    for rel_path in sorted(candidate_paths):
        top = _rel_top_component(rel_path)
        if top and top in skip_prefixes:
            continue
        full_path = dir_path / rel_path

        # Ignore output context dotfiles matching pattern
        if full_path.name.startswith(".package_dir."):
            continue

        # Prevent packaging the output file itself
        if full_path.resolve() == output_file.resolve():
            continue

        # Handle Symlinks explicitly as pointer stubs instead of expanding contents
        if rel_path in symlink_metadata:
            target_ref = symlink_metadata[rel_path]
            processed_files[rel_path] = f"[SYMBOLIC LINK -> {target_ref}]"
            file_list.append(rel_path)
            continue

        if not full_path.is_file():
            continue

        # Skip oversized files
        if full_path.stat().st_size > (args.max_file_size_kb * 1024):
            log.debug(
                f"Skipping file exceeding size limit ({args.max_file_size_kb} KB): {rel_path}"
            )
            continue

        # Skip binary files
        if is_binary_file(full_path):
            continue

        # noinspection broad-exception
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            ext = full_path.suffix.lower()
            cleaned_content = strip_comments_and_blanks(
                content, ext, args.strip_comments, args.strip_blank_lines
            )

            processed_files[rel_path] = cleaned_content
            file_list.append(rel_path)
            total_lines += len(cleaned_content.splitlines())
        except Exception:
            pass

    git_commit_hash, git_branch = (
        get_git_commit_info(dir_path) if is_git_repo else ("N/A", "N/A")
    )

    for top, meta in sorted(oversized.items()):
        members = by_top[top]
        # Optional: compute lines for summary if still unknown
        line_count = (
            meta["approx_lines"] if isinstance(meta["approx_lines"], int) else 0
        )
        if meta["approx_lines"] == "unknown":
            for m in members:
                if m in symlink_metadata:
                    continue
                fp = dir_path / m
                if fp.is_file() and not is_binary_file(fp):
                    # noinspection broad-exception
                    try:
                        line_count += sum(
                            1 for _ in open(fp, "r", encoding="utf-8", errors="replace")
                        )
                    except Exception:
                        pass
            meta["approx_lines"] = line_count

        summary_key = f"{top}/__OVERSIZED_SUMMARY__.md"
        processed_files[summary_key] = _summarize_directory(
            dir_path, top, members, symlink_metadata, line_count
        )
        file_list.append(summary_key)

    total_regular_files = sum(
        1
        for f in file_list
        if f not in symlink_metadata and not f.endswith("__OVERSIZED_SUMMARY__.md")
    )
    total_symlinks = sum(1 for f in file_list if f in symlink_metadata)

    # Build rich metadata for LLM contextual awareness
    yaml_data = {
        "__meta__": {
            "package_name": directory_name,
            "requested_target_dir": args.directory_path,
            "absolute_target_dir": str(dir_path),
            "execution_pwd": os.getcwd(),
            "config_file_used": str(config_file) if config_file else None,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "git_commit_hash": git_commit_hash,
            "git_branch": git_branch,
            "python_version": sys.version.split()[0],
            "total_files": total_regular_files,
            "total_symlinks": total_symlinks,
            "total_lines": total_lines,
            "directory_tree": build_tree(file_list, symlink_metadata),
            "oversized_directories": list(oversized.values()),
            "packaging_strategy": (
                "Full content for root + non-oversized dirs; "
                "symbolic links preserved as pointer references; "
                "summaries + repackage hints for oversized dirs; "
                f"(max_subdir_files={args.max_subdir_files}, "
                f"max_subdir_lines={args.max_subdir_lines})."
            ),
        },
        "files": processed_files,
    }

    # --- Write YAML Output ---
    try:
        with open(output_file, "w", encoding="utf-8") as out:
            out.write("# ==========================================================\n")
            out.write(f"# Repository Package: {directory_name}\n")
            out.write("# Format: YAML 1.2 (LLM Source Context)\n")
            out.write("# ==========================================================\n\n")

            yaml.dump(
                yaml_data,
                out,
                Dumper=LiteralBlockYamlDumper,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
    except Exception as e:
        log.error(f"Failed to write output file '{output_file}': {e}")
        sys.exit(1)

    log.info("---")
    log.info(f"Packaging complete! Saved in '{output_file}'.")

    # --- File Size Check ---
    output_bytes = output_file.stat().st_size
    threshold_bytes = args.size_threshold_mb * 1024 * 1024
    output_mb = output_bytes / (1024 * 1024)

    if output_bytes > threshold_bytes:
        log.warning(
            f"Output file size ({output_mb:.2f} MB) exceeds the threshold limit of {args.size_threshold_mb} MB!"
        )


if __name__ == "__main__":
    main()
