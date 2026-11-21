#!/usr/bin/env python3
"""
vault_organizer.py – Sort and organize Ansible Vault keys into logical groups
alpha-numerically while preserving key/group dependencies (Jinja references)
and maintaining all comments and formatting using ruamel.yaml.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

# ---------------------------------------------------------------------------
# Script metadata
# ---------------------------------------------------------------------------
__scriptName__ = os.path.basename(sys.argv[0])
__version__ = "2026.11.15"
__updated__ = "15 November 2026"

log = logging.getLogger(__scriptName__)

# ---------------------------------------------------------------------------
# Optional Ansible Vault support
# ---------------------------------------------------------------------------
try:
    from ansible.parsing.vault import VaultLib, VaultSecret
    from ansible.constants import DEFAULT_VAULT_ID_MATCH

    HAS_ANSIBLE = True
except ImportError:
    VaultLib = None  # type: ignore
    VaultSecret = None  # type: ignore
    DEFAULT_VAULT_ID_MATCH = None  # type: ignore
    HAS_ANSIBLE = False


class VaultString(str):
    """Custom string subclass to preserve !vault block scalar formatting during YAML dump."""
    pass


def setup_logging(loglevel_str: str = "INFO") -> None:
    """Configure the script logger."""
    loglevel = getattr(logging, loglevel_str.upper(), logging.INFO)
    log.setLevel(loglevel)

    if not log.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        log.addHandler(handler)
    else:
        log.handlers[0].setLevel(loglevel)


def load_vault_password(password_file: str | None) -> bytes | None:
    """Load vault password from the first available source."""
    candidates = []
    if password_file:
        candidates.append(Path(password_file).expanduser())
    candidates.append(Path("~/.vault_pass").expanduser())
    env_file = os.environ.get("ANSIBLE_VAULT_PASSWORD_FILE")
    if env_file:
        candidates.append(Path(env_file).expanduser())

    for p in candidates:
        if p and p.is_file():
            log.debug(f"Using vault password file: {p}")
            return p.read_text().strip().encode()
    return None


def decrypt_with_ansible(data: bytes, password: bytes) -> str:
    """Decrypt using Ansible's VaultLib."""
    secret = VaultSecret(password)
    vault = VaultLib([(DEFAULT_VAULT_ID_MATCH, secret)])
    return vault.decrypt(data).decode()


def decrypt_with_cli(path: Path, password_file: str | None) -> str:
    """Fallback: call ansible-vault view."""
    cmd = ["ansible-vault", "view", str(path)]
    if password_file:
        cmd.extend(["--vault-password-file", password_file])

    log.debug(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ansible-vault view failed")
    return result.stdout


def extract_text_content(obj: Any) -> str:
    """Recursively extract all string values from an object to search for variable references."""
    if isinstance(obj, str):
        return obj
    elif isinstance(obj, dict):
        return " ".join(f"{k} {extract_text_content(v)}" for k, v in obj.items())
    elif isinstance(obj, list):
        return " ".join(extract_text_content(item) for item in obj)
    return str(obj)


def get_vault_group(key: str) -> str:
    """Extract the logical group name for a vault__ variable.

    Examples:
      vault__ansible_ssh_password -> 'ansible'
      vault__authelia_jwt_secret  -> 'authelia'
      vault__gitea__tokens        -> 'gitea'
    """
    match = re.match(r"^vault__([a-zA-Z0-9]+)(?:_|__)", key)
    if match:
        return match.group(1).lower()
    return key.lower()


def _topo_sort_with_cycle_break(
    items: list[str],
    deps: dict[str, set[str]],
    dependents: dict[str, set[str]],
    label: str,
) -> list[str]:
    """Perform Kahn's topological sort with alpha-numeric tie-breaking.

    If a cycle prevents progress while items remain, break the cycle deterministically
    by picking the alpha-numerically first remaining item and clearing its remaining
    unmet prerequisite edges so downstream items can continue sorting cleanly.
    """
    remaining_set = set(items)
    in_degree = {
        item: len([d for d in deps.get(item, set()) if d in remaining_set])
        for item in items
    }
    sorted_items: list[str] = []
    cyclic_items: list[str] = []

    while remaining_set:
        available = sorted([item for item in remaining_set if in_degree[item] == 0])

        if not available:
            # Break cycle by choosing the alpha-numerically earliest blocked item
            # and dropping its remaining incoming edges from still-remaining nodes.
            chosen = sorted(remaining_set)[0]
            cyclic_items.append(chosen)
            for prereq in list(deps.get(chosen, set())):
                if prereq in remaining_set and chosen in dependents.get(prereq, set()):
                    dependents[prereq].discard(chosen)
            in_degree[chosen] = 0
            available = [chosen]

        curr = available[0]
        sorted_items.append(curr)
        remaining_set.remove(curr)

        for dep in sorted(dependents.get(curr, set())):
            if dep in remaining_set:
                in_degree[dep] = max(0, in_degree[dep] - 1)

    if cyclic_items:
        log.warning(
            f"Broke {label} dependency cycle at: {sorted(cyclic_items)} "
            "while preserving topological order where possible."
        )

    return sorted_items


def _reorder_map_preserving_comments(
    data: CommentedMap, ordered_keys: list[str]
) -> CommentedMap:
    """Rebuild CommentedMap in ordered_keys order while preserving comment artifacts."""
    if not isinstance(data, CommentedMap):
        return data

    ca = getattr(data, "ca", None)
    orig_values = {k: data[k] for k in ordered_keys if k in data}
    orig_items = dict(ca.items) if ca is not None and ca.items else {}
    orig_start_comment = ca.comment if ca is not None else None
    orig_end_comment = getattr(ca, "end", None) if ca is not None else None

    first_orig_key = next(iter(data.keys()), None)
    first_new_key = ordered_keys[0] if ordered_keys else None

    # If the original first key moved and carried a pre-key CommentToken (index 2),
    # move it onto the new first key so the header comment stays at the top.
    if (
        first_orig_key is not None
        and first_orig_key != first_new_key
        and first_orig_key in orig_items
    ):
        old_first_entry = orig_items[first_orig_key]
        if isinstance(old_first_entry, list) and len(old_first_entry) > 2 and old_first_entry[2] is not None:
            leading_token = old_first_entry[2]
            updated_old = list(old_first_entry)
            updated_old[2] = None
            orig_items[first_orig_key] = updated_old

            if first_new_key is not None:
                new_first_entry = list(orig_items.get(first_new_key) or [None, None, None, None])
                while len(new_first_entry) < 4:
                    new_first_entry.append(None)
                if new_first_entry[2] is None:
                    new_first_entry[2] = leading_token
                orig_items[first_new_key] = new_first_entry

    data.clear()
    if ca is not None:
        ca.items.clear()
        if orig_start_comment is not None:
            ca.comment = orig_start_comment
        if orig_end_comment is not None:
            ca.end = orig_end_comment

    for k in ordered_keys:
        if k in orig_values:
            data[k] = orig_values[k]
            if ca is not None and k in orig_items:
                entry = orig_items[k]
                ca.items[k] = list(entry) if isinstance(entry, list) else entry

    return data


def sort_vault_keys_with_dependencies(data: CommentedMap) -> CommentedMap:
    """Group vault__ keys by prefix, order dependent groups after prerequisite groups,
    and sort keys alpha-numerically (respecting intra-group key dependencies) while
    preserving comments.
    """
    if not isinstance(data, CommentedMap):
        return data

    root_keys = list(data.keys())
    # Filter for vault keys or general keys to sort
    vault_keys = [k for k in root_keys if isinstance(k, str) and k.startswith("vault__")]
    other_keys = [k for k in root_keys if k not in vault_keys]

    # Build dependency graph for vault_keys
    # graph[k] = set of keys that k depends on (i.e. k references dep_key)
    key_to_group = {k: get_vault_group(k) for k in vault_keys}
    groups_map: dict[str, list[str]] = defaultdict(list)
    for k in vault_keys:
        groups_map[key_to_group[k]].append(k)

    key_deps: dict[str, set[str]] = {k: set() for k in vault_keys}
    key_dependents: dict[str, set[str]] = {k: set() for k in vault_keys}

    all_groups = list(groups_map.keys())
    group_deps: dict[str, set[str]] = {g: set() for g in all_groups}
    group_dependents: dict[str, set[str]] = {g: set() for g in all_groups}

    # Helper regex to find vault variable mentions
    vault_var_re = re.compile(r"\b(vault__[a-zA-Z0-9_]+)\b")

    for k in vault_keys:
        val = data[k]
        text_blob = extract_text_content(val)
        found_refs = vault_var_re.findall(text_blob)
        k_group = key_to_group[k]

        for ref in found_refs:
            if ref in vault_keys and ref != k:
                key_deps[k].add(ref)
                key_dependents[ref].add(k)

                ref_group = key_to_group[ref]
                if ref_group != k_group:
                    group_deps[k_group].add(ref_group)
                    group_dependents[ref_group].add(k_group)

    # 1. Order groups topologically with alpha-numeric tie-breaking and cycle breaking
    ordered_groups = _topo_sort_with_cycle_break(
        all_groups, group_deps, group_dependents, label="group"
    )

    # 2. Within each group, sort keys topologically (within-group edges only)
    #    with alpha-numeric tie-breaking
    sorted_vault_keys: list[str] = []
    for grp in ordered_groups:
        grp_keys = groups_map[grp]
        grp_key_set = set(grp_keys)
        intra_deps = {k: (key_deps[k] & grp_key_set) for k in grp_keys}
        intra_dependents = {k: (key_dependents[k] & grp_key_set) for k in grp_keys}

        sorted_grp_keys = _topo_sort_with_cycle_break(
            grp_keys, intra_deps, intra_dependents, label=f"group '{grp}' key"
        )
        sorted_vault_keys.extend(sorted_grp_keys)

    # Sort non-vault keys alpha-numerically
    other_keys.sort(key=lambda x: str(x))
    final_key_order = sorted_vault_keys + other_keys

    return _reorder_map_preserving_comments(data, final_key_order)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    prog_usage = f"""
Examples of use:

  # Organize plaintext / simulated vault file
  {__scriptName__} --plaintext vault.example.yml > sorted_vault.yml

  # Organize live Ansible Vault file (uses ~/.vault_pass automatically)
  {__scriptName__} --vault inventory/group_vars/all/vault.yml > sorted_vault.yml

  # Explicit password file
  {__scriptName__} --vault --vault-password-file ~/.vault_pass vault.yml

  # Debug logging
  {__scriptName__} -L DEBUG --plaintext vault.example.yml
"""

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "Organize and sort Ansible Vault keys into logical groups\n"
            "alpha-numerically while maintaining dependency order\n"
            "and preserving comments and YAML formatting using ruamel.yaml."
        ),
        epilog=prog_usage,
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__} ({__updated__})",
    )
    parser.add_argument(
        "-L", "--loglevel",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        default="INFO",
        help="Set log level (default: INFO)",
    )
    parser.add_argument(
        "file",
        type=Path,
        help="YAML or vault-encrypted file to organize",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--vault",
        action="store_true",
        help="Treat the file as Ansible Vault encrypted (will attempt decryption)",
    )
    mode_group.add_argument(
        "--plaintext",
        action="store_true",
        help="Treat the file as plain-text / already-decrypted",
    )

    parser.add_argument(
        "--vault-password-file",
        help="Path to vault password file (default: ~/.vault_pass)",
    )

    args = parser.parse_args()
    setup_logging(args.loglevel)

    log.debug("Started vault organizer run")

    if not args.file.is_file():
        log.error(f"File not found: {args.file}")
        sys.exit(1)

    raw = args.file.read_bytes()

    # Determine decryption mode
    if args.plaintext:
        is_vault = False
        log.info(f"Forced plain-text mode for {args.file}")
    elif args.vault:
        is_vault = True
        log.info(f"Forced vault mode for {args.file}")
    else:
        is_vault = raw.startswith(b"$ANSIBLE_VAULT")
        if is_vault:
            log.info(f"Auto-detected vault encryption on {args.file}")
        else:
            log.info(f"Treating {args.file} as plain YAML (auto-detect)")

    if is_vault:
        password = load_vault_password(args.vault_password_file)
        try:
            if password and HAS_ANSIBLE:
                content = decrypt_with_ansible(raw, password)
            else:
                content = decrypt_with_cli(args.file, args.vault_password_file)
        except Exception as e:
            log.error(f"Failed to decrypt vault file:\n{e}")
            sys.exit(1)
    else:
        content = raw.decode()

    # Load with ruamel.yaml (preserves comments & blank lines)
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 120
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.explicit_start = True

    yaml.constructor.add_constructor('!vault', lambda l, n: VaultString(l.construct_scalar(n)))
    yaml.representer.add_representer(VaultString, lambda r, d: r.represent_scalar('!vault', d, style='|'))

    try:
        data = yaml.load(content)
    except Exception as e:
        log.error(f"YAML parse error:\n{e}")
        sys.exit(1)

    if data is None:
        log.error("Empty YAML document")
        sys.exit(1)

    if not isinstance(data, CommentedMap):
        log.error("Top-level YAML structure must be a mapping/dictionary.")
        sys.exit(1)

    log.info("Sorting vault keys into logical groups with dependency ordering...")
    organized_data = sort_vault_keys_with_dependencies(data)

    # Emit the sorted YAML to stdout
    yaml.dump(organized_data, sys.stdout)

    log.debug("Finished vault organizer run successfully")


if __name__ == "__main__":
    main()
