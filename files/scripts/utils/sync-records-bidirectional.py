#!/usr/bin/env python3
"""
sync-records-bidirectional.py

Smart bidirectional incremental sync for personal records.
With support for preventing local updates from overwriting specific remote paths.
This effectively supports a "uni-directional" sync mode (remote -> local only) for the specified paths.
"""

import argparse
import hashlib
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required.", file=sys.stderr)
    print("Install with: python3 -m pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# Optional: Better git-style ignore patterns
try:
    import pathspec

    HAS_PATHSPEC = True
except ImportError:
    HAS_PATHSPEC = False
    logging.warning("pathspec not installed. Falling back to basic pattern matching.")
    logging.warning("Install with: python3 -m pip install pathspec")

# =============================================================================
# Configuration & Logging
# =============================================================================

SCRIPT_VERSION = "2026.06.04"
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_BASENAME = SCRIPT_PATH.name


def setup_logging(log_file: Path, log_level: str = "INFO"):
    """Setup logging with configurable level."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="[%(asctime)s] [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )


def load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """Load YAML config and validate required fields."""
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}", file=sys.stderr)
        print(f"Usage: Create a config file at {config_path} or specify with --config", file=sys.stderr)
        sys.exit(1)

    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"ERROR: Failed to parse YAML config {config_path}: {e}", file=sys.stderr)
        sys.exit(1)

    REQUIRED = {"local_dir", "remote_dir", "smb_url", "mount_point"}
    missing = [key for key in REQUIRED if key not in config]
    if missing:
        print(f"ERROR: Missing required keys: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # Optional settings with defaults
    defaults = {
        "lockfile": "/tmp/sync-records-bidirectional.lock",
        "log_file": "/tmp/rsync.records-bidir.stdout.log",
        "hash_db": "~/.sync-data/sync-hash-data.yml",
        "ignore_patterns": [
            ".DS_Store",
            "*.tmp",
            "Thumbs.db",
            "._*"
        ],
        "exclude_remote_update": []
    }

    for k, v in defaults.items():
        config.setdefault(k, v)

    # Expand ~ in paths
    for key in ["local_dir", "remote_dir", "hash_db", "lockfile", "log_file"]:
        if key in config:
            config[key] = Path(os.path.expanduser(config[key]))

    # smtp is optional
    if "smtp" in config and not isinstance(config.get("smtp"), dict):
        print("ERROR: 'smtp' must be a dictionary if present", file=sys.stderr)
        sys.exit(1)

    return config


def send_email(config: Dict, subject: str, body: str):
    """Send email via raw SMTP - only if smtp config exists."""
    if "smtp" not in config or not config["smtp"]:
        return

    smtp = config["smtp"]
    try:
        input_data = f"""HELO {os.uname().nodename}
MAIL FROM:<{smtp.get('sender')}>
RCPT TO:<{smtp.get('to')}>
DATA
Subject: {subject}
From: {smtp.get('sender')}
To: {smtp.get('to')}

Host: {os.uname().nodename}
Script: {SCRIPT_PATH}
Message: {body}
Timestamp: {datetime.now().isoformat()}

.
QUIT
"""
        proc = subprocess.run(["nc", smtp["server"], "25"],
                              input=input_data,
                              text=True,
                              capture_output=True,
                              timeout=30)
        if proc.returncode != 0:
            logging.warning("SMTP delivery failed")
    except Exception as e:
        logging.warning(f"Failed to send email: {e}")


def send_notifications(config: Dict, success: bool, warnings: int = 0, message: str = ""):
    """Send macOS notification and optional email."""
    title = "Sync Success" if success else "Sync Failure"
    subtitle = "Records Backup"
    sound = "Submarine" if success else "Basso"

    status = "Success" if success else "Failure"
    if warnings > 0 and success:
        status += f" ({warnings} warnings)"

    # email_subject = f"{SCRIPT_BASENAME}: {status}"
    email_subject = f"Sync(py): {status}"

    # macOS notification (short version)
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message[:250]}..." with title "{title}" subtitle "{subtitle}" sound name "{sound}"'
        ], check=False)
    except Exception:
        pass

    # Send message via email
    send_email(config, email_subject, message)


# =============================================================================
# Pattern Matching Logic (Ignore / Exclude Remote Update)
# =============================================================================

def build_pattern_spec(patterns: List[str]):
    """Build pathspec matcher if available."""
    if HAS_PATHSPEC and patterns:
        try:
            return pathspec.PathSpec.from_lines('gitwildmatch', patterns)
        except Exception:
            pass
    return None


def matches_pattern(rel_path: str, patterns: List[str], spec=None) -> bool:
    """Helper to check if a relative path matches git-style patterns or fallback rules."""
    if not patterns:
        return False

    if spec and spec.match_file(rel_path):
        return True

    # Fallback / additional checks
    name = os.path.basename(rel_path)
    for pattern in patterns:
        if pattern == name or Path(name).match(pattern) or (pattern.startswith("._") and name.startswith("._")):
            return True
        # Allow directory/path-based fallback checking
        if Path(rel_path).match(pattern):
            return True
    return False


def should_skip_file(rel_path: str, ignore_patterns: List[str], ignore_spec=None) -> bool:
    """Check if file should be ignored using git-style patterns."""
    return matches_pattern(rel_path, ignore_patterns, ignore_spec)


def is_remote_update_excluded(rel_path: str, exclude_patterns: List[str], exclude_spec=None) -> bool:
    """Check if a relative path is skipped from being updated on the remote side."""
    return matches_pattern(rel_path, exclude_patterns, exclude_spec)


# =============================================================================
# Helpers
# =============================================================================

def load_hash_db(db_path: Path) -> Dict:
    if db_path.exists():
        try:
            with open(db_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logging.warning(f"Failed to load hash DB: {e}")
    return {}


def save_hash_db(db_path: Path, data: Dict):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with open(db_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=True, default_flow_style=False)


def compute_file_info(path: Path, prev_info: Optional[Dict] = None, force_rehash: bool = False) -> Dict:
    """Compute file info, reusing previous hash if mtime hasn't changed."""
    stat = path.stat()
    current_mtime = int(stat.st_mtime)
    current_size = stat.st_size

    if not force_rehash and prev_info and prev_info.get("mtime") == current_mtime and prev_info.get(
            "size") == current_size:
        # Fast path: reuse cached hash
        return prev_info

    # Full hash computation
    hasher = hashlib.blake2b(digest_size=32)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            hasher.update(chunk)

    return {
        "mtime": current_mtime,
        "size": current_size,
        "hash": hasher.hexdigest()
    }


def get_file_key(path: Path, base: Path) -> str:
    return str(path.relative_to(base))


def scan_directory(base: Path, prev_hash_db: Dict, force_rehash: bool, label: str, ignore_patterns: List[str], ignore_spec) -> Dict[str, Dict]:
    """Scan directory with progress feedback."""
    files_dict: Dict[str, Dict] = {}
    file_count = 0
    last_log_time = time.time()

    logging.info(f"Scanning {label} directory: {base} ...")

    for root, _, filenames in os.walk(base):
        root_path = Path(root)
        for name in filenames:
            rel_path = get_file_key(root_path / name, base)
            if should_skip_file(rel_path, ignore_patterns, ignore_spec):
                logging.debug(f"   ⏭️  Ignored: {rel_path}")
                continue

            file_path = root_path / name
            key = rel_path
            prev_info = prev_hash_db.get(key) if label == "Local" else None
            info = compute_file_info(file_path, prev_info, force_rehash)

            files_dict[key] = info
            file_count += 1

            # Progress update every 500 files or every 10 seconds
            if file_count % 500 == 0 or (time.time() - last_log_time > 10):
                logging.info(f"  [{label}] Processed {file_count:,} files...")
                last_log_time = time.time()

    logging.info(f"Completed scanning {label}: {file_count:,} files processed.")
    return files_dict


# =============================================================================
# Core Logic
# =============================================================================

def bidirectional_sync(config: Dict, dry_run: bool = False, force_rehash: bool = False):
    start_time = time.time()

    local_base = Path(config["local_dir"]).resolve()
    remote_base = Path(config["remote_dir"]).resolve()
    hash_db_path = Path(config["hash_db"])

    ignore_patterns = config.get("ignore_patterns", [".DS_Store", "*.tmp", "Thumbs.db", "._*"])
    ignore_spec = build_pattern_spec(ignore_patterns)

    exclude_patterns = config.get("exclude_remote_update", [])
    exclude_spec = build_pattern_spec(exclude_patterns)

    mode = "DRY-RUN" if dry_run else "LIVE"
    logging.info(f"=== Starting smart bidirectional sync ({mode}) ===")
    logging.info(f"Local : {local_base}")
    logging.info(f"Remote: {remote_base}")
    logging.info(f"Ignore patterns: {ignore_patterns}")
    if exclude_patterns:
        logging.info(f"Exclude Remote Update patterns: {exclude_patterns}")

    prev_hash_db = load_hash_db(hash_db_path)
    current_hash_db: Dict[str, Dict] = {}

    # Scan Local
    local_files = scan_directory(local_base, prev_hash_db, force_rehash, "Local", ignore_patterns, ignore_spec)
    current_hash_db.update(local_files)

    # Scan Remote
    remote_files = scan_directory(remote_base, {}, force_rehash, "Remote", ignore_patterns, ignore_spec)

    to_local = []
    to_remote = []
    exceptions = []
    change_details = []
    skipped_remote_updates_count = 0

    all_keys = set(local_files.keys()) | set(remote_files.keys())
    logging.info(f"Comparing {len(all_keys):,} total unique files...")

    for key in sorted(all_keys):
        l_info = local_files.get(key)
        r_info = remote_files.get(key)
        local_path = local_base / key
        remote_path = remote_base / key

        if l_info and r_info:
            # Both sides exist → compare
            if l_info["mtime"] > r_info["mtime"] or l_info["hash"] != r_info["hash"]:
                if is_remote_update_excluded(key, exclude_patterns, exclude_spec):
                    logging.info(f"   🔒 [MUTED] Remote update excluded for: {key} (Remote -> Local only mode)")
                    skipped_remote_updates_count += 1
                    continue
                to_remote.append((local_path, remote_path))
                change_details.append(f"→ Remote modified (local wins): {key}")
            elif r_info["mtime"] > l_info["mtime"]:
                to_local.append((remote_path, local_path))
                change_details.append(f"→ Local modified (remote wins): {key}")
        elif l_info:
            if is_remote_update_excluded(key, exclude_patterns, exclude_spec):
                logging.info(f"   🔒 [MUTED] Remote allocation excluded for: {key} (Remote -> Local only mode)")
                skipped_remote_updates_count += 1
                continue
            to_remote.append((local_path, remote_path))
            change_details.append(f"+ Added to remote: {key}")
        elif r_info:
            to_local.append((remote_path, local_path))
            change_details.append(f"+ Added to local: {key}")

    # Execute actions
    success_count = 0
    if dry_run:
        logging.info("=== DRY-RUN MODE: No changes made ===")
    else:
        for src, dst in to_local + to_remote:
            try:
                sync_file(src, dst, "to-local" if dst.parent.is_relative_to(local_base) else "to-remote")
                success_count += 1
            except Exception as e:
                exceptions.append(str(e))
                logging.warning(f"Permission denied copying {src.name} → {dst}")

    # Always save hash DB
    save_hash_db(hash_db_path, current_hash_db)

    # Calculate duration
    elapsed_seconds = time.time() - start_time
    minutes = int(elapsed_seconds // 60)
    seconds = int(elapsed_seconds % 60)
    duration_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

    # Rich Summary by Direction
    to_local_count = len(to_local)
    to_remote_count = len(to_remote)

    summary = f"Sync {mode} completed at {datetime.now().isoformat()}\n\n"
    summary += f"Duration                 : {duration_str}\n"
    summary += f"Files synced successfully: {success_count}\n"
    summary += f"Exceptions occurred      : {len(exceptions)}\n"
    summary += f"Remote updates skipped   : {skipped_remote_updates_count}\n\n"

    summary += "=== Changes by Direction ===\n\n"
    summary += f"To Local:\n"
    summary += f"  Added    : {sum(1 for x in change_details if 'Added to local' in x)}\n"
    summary += f"  Modified : {sum(1 for x in change_details if 'Local modified' in x)}\n"
    summary += f"  Total    : {to_local_count}\n\n"

    summary += f"To Remote:\n"
    summary += f"  Added    : {sum(1 for x in change_details if 'Added to remote' in x)}\n"
    summary += f"  Modified : {sum(1 for x in change_details if 'Remote modified' in x)}\n"
    summary += f"  Deleted  : {sum(1 for x in change_details if 'Deleted' in x)}\n"
    summary += f"  Total    : {to_remote_count}\n"

    if exceptions:
        summary += "\nExceptions:\n" + "\n".join([f"- {e}" for e in exceptions[:10]])
        if len(exceptions) > 10:
            summary += f"\n... and {len(exceptions) - 10} more exceptions."

    logging.info(summary)

    # Build detailed changes for email
    detail_lines = change_details[:100]
    if len(change_details) > 200:
        detail_lines.append("...")
        detail_lines.extend(change_details[-100:])
    elif len(change_details) > 100:
        detail_lines.extend(change_details[100:])

    full_email_body = summary
    if detail_lines:
        full_email_body += "\n\nDetailed Changes:\n" + "\n".join(detail_lines)

    success = len(exceptions) == 0 or dry_run
    send_notifications(
        config,
        success=success,
        warnings=len(exceptions),
        message=full_email_body
    )


def sync_file(src: Path, dst: Path, direction: str):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    logging.info(f"[{direction.upper()}] {src.name}")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Smart bidirectional incremental sync for personal records.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Normal run
  python3 sync-records-bidirectional.py

  # Dry run (highly recommended)
  python3 sync-records-bidirectional.py --dry-run

  # Force full re-hashing
  python3 sync-records-bidirectional.py --force-rehash

  # Debug mode
  python3 sync-records-bidirectional.py --log-level DEBUG
        """
    )
    parser.add_argument("-c", "--config", type=Path,
                        default=Path.home() / ".sync-data.yml",
                        help="Path to YAML config file (default: ~/.sync-data.yml)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate sync without making any changes")
    parser.add_argument("--force-rehash", action="store_true",
                        help="Force full re-computation of all file hashes (ignore cache)")
    parser.add_argument("-L", "--log-level",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default="INFO",
                        help="Set logging level (default: INFO)")
    args = parser.parse_args()

    config = load_yaml_config(args.config)

    log_file = Path(config["log_file"])
    setup_logging(log_file, args.log_level)

    logging.info(
        f"{SCRIPT_BASENAME} v{SCRIPT_VERSION} started with config: {args.config} (log level: {args.log_level})")

    if args.dry_run:
        logging.info("DRY-RUN mode enabled - no files will be modified")
    if args.force_rehash:
        logging.info("Force rehash enabled - all files will be fully hashed")

    # Lockfile logic with improved messaging
    lockfile: Path = Path(config["lockfile"])
    if lockfile.exists() and not args.dry_run:
        try:
            other_pid = int(lockfile.read_text().strip())
            if subprocess.run(["ps", "-p", str(other_pid)], capture_output=True).returncode == 0:
                logging.info(f"Another instance (PID {other_pid}) is running. Exiting.")
                logging.info(f"   → Lock file: {lockfile}")
                logging.info(f"   → To remove stale lock: rm {lockfile}")
                sys.exit(0)
        except Exception:
            pass
        lockfile.unlink(missing_ok=True)

    if not args.dry_run:
        lockfile.write_text(str(os.getpid()))

    try:
        # Mount check
        remote_dir = Path(config["remote_dir"])
        if not remote_dir.exists() and not args.dry_run:
            logging.info(f"Attempting to mount SMB share: {config['smb_url']}")
            subprocess.run(["osascript", "-e", f'mount volume "{config["smb_url"]}"'],
                           check=True, timeout=30)
            time.sleep(3)

        bidirectional_sync(config, dry_run=args.dry_run, force_rehash=args.force_rehash)

    except Exception as e:
        logging.exception("Sync failed")
        if not args.dry_run:
            send_notifications(config, success=False, message=str(e))
        sys.exit(1)
    finally:
        if not args.dry_run:
            lockfile.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
