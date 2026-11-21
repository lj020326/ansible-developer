#!/usr/bin/env python3
"""
scrambler.py – Replace sensitive values in an Ansible vault/YAML file
with same-length random strings so the structure can be shared safely.

Useful when preparing a clean split of a large vault.yml into:
  - group_vars/all/credentials.yml  (structure + non-secrets)
  - group_vars/all/vault.yml        (only real secrets)
  - vars/vault.yml                  (only real secrets)

Requires: ruamel.yaml
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import re
import secrets
import string
import sys
import subprocess
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import (
    LiteralScalarString,
    DoubleQuotedScalarString,
    SingleQuotedScalarString,
    PlainScalarString,
)

# ---------------------------------------------------------------------------
# Script metadata
# ---------------------------------------------------------------------------
__scriptName__ = os.path.basename(sys.argv[0])
__version__ = "2026.11.06"
__updated__ = "06 November 2026"

log = logging.getLogger(__scriptName__)

# ---------------------------------------------------------------------------
# Patterns & constants
# ---------------------------------------------------------------------------
PASSWORD_MIN_LENGTH = 22
PASSWORD_MAX_LENGTH = 32

PASSWORD_KEY_PATTERNS = {
    "password", "passwd", "pwd", "secret", "oauth"
}

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

# Any Jinja2 expression or statement: {{ ... }} or {% ... %}
JINJA_RE = re.compile(
    r"(\{\{.*?\}\}|\{%.*?%\})",
    re.DOTALL
)

# List of application/service identifiers to exclude
EXCLUDED_APPS = [
    "ansible_repo",
    "auth",
    "bitbucket",
    "cloudflare",
    "cloudstack",
    "dettonville",
    "github",
    "gluetun",
    "hardcover",
    "hugging_face",
    "isp",
    "james",
    "jenkins_bitbucket",
    "jetbrains",
    "keycloak",
    "lychee",
    "media",
    "minio",
    "nextcloud",
    "nordvpn",
    "openbao",
    "openvpn",
    "pfsense",
    "photoprism",
    "piwigo",
    "plane",
    "plex",
    "pydio",
    "smtp",
    "stepca",
    "vcenter",
    "vikunja",
    "vmware",
    "vsphere",
    "wireguard",
    "wordpress",
    "zoho",
]

# Key patterns whose entire key-value pair should be excluded/dropped from the final output
EXCLUDED_KEY_PATTERNS = {
    rf"vault__({'|'.join(EXCLUDED_APPS)})_.*"
}

# Pre-compile exclusion patterns for performance and regex matching
COMPILED_EXCLUDED_PATTERNS = [
    re.compile(pattern) for pattern in EXCLUDED_KEY_PATTERNS
]

PRESERVED_SPECIAL_CHARS = {"@", "-", ".", ",", "=", "/", "$", ":", "+", "{", "}"}

# Short values / booleans that should be left completely untouched
PRESERVE_TOKENS = {
    "yes", "no", "true", "false", "on", "off",
    "enable", "disable", "enabled", "disabled",
    "present", "absent", "smtp", "udp", "tcp",
    "free", "org", "com", "local",
    "bearer", "basic", "secure", "news",
    "465", "443", "8080",
    "0.0.0.0", "::/0", "/16", "/0", "S-1-5-21",
    "reader", "interface", "peer",
    "git", "gitea", "gitadmin",
    "keycloak", "pfsense", "vsphere",
    "vault", "ollama", "llm", "vllm", "llama",
    "gb10", "rtx", "gpu",
    "gpu01", "gpu02", "control01", "control02",
    "user", "users", "domain", "apps", "googleusercontent",
    "gmail", "bitbucket", "nordvpn", "datacenter",
    "zoho", "xsusenet", "thecubenet", "example",
    "ansible", "ansibledomain", "ansible-vm-provisioner",
    "pulp", "galaxy", "vcsa1", "vcsa2", "domainp1s1",
    "root", "admin", "admins", "administrator", "media", "osbuild",
    "dev", "test", "password", "ed25519", "rsa", "s."
}

# ---------------------------------------------------------------------------
# Preserved prefixes (order matters – longer / more specific first)
# ---------------------------------------------------------------------------
PRESERVED_PREFIX_PATTERNS = [
    # OpenSSH public key types
    r"^(ssh-rsa|ssh-ed25519|ecdsa-sha2-nistp256|ecdsa-sha2-nistp384|ecdsa-sha2-nistp521|ssh-dss)\s+",
    # LDAP / LDAPS URIs
    r"^(ldaps?://)",
    # HTTP/HTTPS URLs
    r"^(https://)",
    r"^(http://)",
    # Git / SSH URLs
    r"^(git@)",
    r"^(ssh://)",
    # Github
    r"^(github_pat_)",
    # SSHA password hash (case-insensitive)
    r"^(\{[Ss][Ss][Hh][Aa]\})",
    # Common LDAP DN attributes
    r"^(dc=)",
    r"^(ou=)",
    r"^(cn=)",
    r"^(uid=)",
    # OpenVPN static key header
    r"^(-----BEGIN OpenVPN Static key V1-----)",
    # Hugging face
    r"^(hf_)",
    # Vikunja
    r"^(tk_)",
]

PRESERVED_PREFIX_RE = re.compile(
    "|".join(f"(?:{p})" for p in PRESERVED_PREFIX_PATTERNS)
)

# ---------------------------------------------------------------------------
# Domain mapping & anonymization
# ---------------------------------------------------------------------------
DOMAIN_MAP = {
    "dettonville.int": "example.int",
    "dettonville.com": "example.com",
    "johnson.int": "qa-example.int",
}

# Collect all source and target domains for protection
ALL_TARGET_DOMAINS = set(DOMAIN_MAP.values()) | {"example.int", "example.com"}

TARGET_DOMAIN_RE = re.compile(
    r"\b(" + "|".join(re.escape(d) for d in sorted(ALL_TARGET_DOMAINS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE
)

# LDAP Keys whose values, keys, or entire subtrees should be skipped from scrambling / translation
SKIP_LDAP_KEYS = {
    "vault__ldap_domain_group_map",
    "uid_number",
    "gid_number",
    "cn",
    "parent_ou",
    "object_class_list",
    "memberuidlist",
    "memberdnlist",
    "samba",
}

# Global registry to map original usernames to consistent scrambled usernames
LDAP_USER_MAPPING: dict[str, str] = {}

# System usernames that should never be randomized
PRESERVED_LDAP_USERNAMES = {"netadmin", "admin", "smbguest", "media", "root"}

# Usernames outside of LDAP that should also be translated using the user info pool
TRANSLATE_USERNAME_LIST = {
    "lj020326",
    "lj73815",
    "ljohnson",
}

# Pool of realistic user profiles drawn from Harry Potter, Lord of the Rings, and Star Wars
LDAP_USER_INFO_POOL = [
    {
        "username": "harry",
        "cn": "Harry Potter",
        "given_name": "Harry",
        "sn": "Potter",
        "display_name": "Harry Potter",
        "initials": "HP",
        "mail": "harry.potter@example.int"
    },
    {
        "username": "hermione",
        "cn": "Hermione Granger",
        "given_name": "Hermione",
        "sn": "Granger",
        "display_name": "Hermione Granger",
        "initials": "HG",
        "mail": "hermione.granger@example.int"
    },
    {
        "username": "ron",
        "cn": "Ron Weasley",
        "given_name": "Ron",
        "sn": "Weasley",
        "display_name": "Ron Weasley",
        "initials": "RW",
        "mail": "ron.weasley@example.int"
    },
    {
        "username": "frodo",
        "cn": "Frodo Baggins",
        "given_name": "Frodo",
        "sn": "Baggins",
        "display_name": "Frodo Baggins",
        "initials": "FB",
        "mail": "frodo.baggins@example.int"
    },
    {
        "username": "aragorn",
        "cn": "Aragorn Elessar",
        "given_name": "Aragorn",
        "sn": "Elessar",
        "display_name": "Aragorn Elessar",
        "initials": "AE",
        "mail": "aragorn.elessar@example.int"
    },
    {
        "username": "legolas",
        "cn": "Legolas Greenleaf",
        "given_name": "Legolas",
        "sn": "Greenleaf",
        "display_name": "Legolas Greenleaf",
        "initials": "LG",
        "mail": "legolas.greenleaf@example.int"
    },
    {
        "username": "luke",
        "cn": "Luke Skywalker",
        "given_name": "Luke",
        "sn": "Skywalker",
        "display_name": "Luke Skywalker",
        "initials": "LS",
        "mail": "luke.skywalker@example.int"
    },
    {
        "username": "leia",
        "cn": "Leia Organa",
        "given_name": "Leia",
        "sn": "Organa",
        "display_name": "Leia Organa",
        "initials": "LO",
        "mail": "leia.organa@example.int"
    },
    {
        "username": "han",
        "cn": "Han Solo",
        "given_name": "Han",
        "sn": "Solo",
        "display_name": "Han Solo",
        "initials": "HS",
        "mail": "han.solo@example.int"
    },
    {
        "username": "obiwan",
        "cn": "Obi-Wan Kenobi",
        "given_name": "Obi-Wan",
        "sn": "Kenobi",
        "display_name": "Obi-Wan Kenobi",
        "initials": "OK",
        "mail": "obiwan.kenobi@example.int"
    }
]

# Extended mapping structure: original_username -> profile dict
LDAP_USER_PROFILE_MAP: dict[str, dict[str, str]] = {}


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


# ---------------------------------------------------------------------------
# Optional Ansible Vault support (lint-friendly)
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


def anonymize_domains(text: str) -> str:
    """Replace known sensitive domains using DOMAIN_MAP."""
    sensitive_re = re.compile(
        r"\b(" + "|".join(re.escape(d) for d in sorted(DOMAIN_MAP.keys(), key=len, reverse=True)) + r")\b",
        re.IGNORECASE
    )

    def _replace(match: re.Match) -> str:
        original = match.group(0).lower()
        return DOMAIN_MAP.get(original, original)

    return sensitive_re.sub(_replace, text)


def _anonymize_comment_slot(slot: Any) -> None:
    """Recursively anonymize domains in ruamel.yaml CommentToken objects."""
    if slot is None:
        return
    if isinstance(slot, list):
        for item in slot:
            _anonymize_comment_slot(item)
    elif hasattr(slot, "value") and isinstance(slot.value, str):
        slot.value = anonymize_domains(slot.value)


def anonymize_comments(obj: Any) -> None:
    """Recursively traverse YAML structures and anonymize domains in all comments."""
    if hasattr(obj, "ca") and obj.ca is not None:
        _anonymize_comment_slot(getattr(obj.ca, "comment", None))
        _anonymize_comment_slot(getattr(obj.ca, "end", None))
        items = getattr(obj.ca, "items", None)
        if isinstance(items, dict):
            for slot in items.values():
                _anonymize_comment_slot(slot)

    if isinstance(obj, CommentedMap):
        for val in obj.values():
            anonymize_comments(val)
    elif isinstance(obj, CommentedSeq):
        for item in obj:
            anonymize_comments(item)


def protect_target_domains(text: str) -> tuple[str, dict[str, str]]:
    """Temporarily replace mapped/target domains with placeholders so they
    survive scrambling as complete units (including prefixes like qa-example.int).
    """
    placeholders: dict[str, str] = {}

    def _protect(match: re.Match) -> str:
        key = f"__TARGET_DOMAIN_{len(placeholders)}__"
        placeholders[key] = match.group(0)
        return key

    protected = TARGET_DOMAIN_RE.sub(_protect, text)
    return protected, placeholders


def restore_target_domains(text: str, placeholders: dict[str, str]) -> str:
    for key, original in placeholders.items():
        text = text.replace(key, original)
    return text


def generate_strong_password() -> str:
    """Generate a strong random password containing letters, digits, and special characters."""
    length = random.randint(PASSWORD_MIN_LENGTH, PASSWORD_MAX_LENGTH)
    # Define alphabet: letters, digits, and common safe special characters
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    # Ensure at least a few symbols and numbers are present
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in pwd) and
            any(c.isupper() for c in pwd) and
            any(c.isdigit() for c in pwd) and
            any(c in "!@#$%^&*-_=+" for c in pwd)):
            return pwd


def generate_fake_email(original: str) -> str:
    """Generate a realistic-looking fake email of similar length."""
    local, _, domain = original.partition("@")
    local_len = max(5, len(local))
    domain_part = domain.split(".")[0] if "." in domain else domain
    domain_len = max(5, len(domain_part))

    fake_local = "".join(random.choice(string.ascii_lowercase) for _ in range(local_len))
    fake_domain = "".join(random.choice(string.ascii_lowercase) for _ in range(domain_len))
    tld = random.choice(["com", "org", "net", "io", "example"])
    return f"{fake_local}@{fake_domain}.{tld}"


def build_user_mapping(data: Any) -> None:
    """Scan vault__ldap_domain_user_map and TRANSLATE_USERNAME_LIST to build consistent user profile mappings."""
    pool = list(LDAP_USER_INFO_POOL)
    random.shuffle(pool)

    usernames_to_map = set(TRANSLATE_USERNAME_LIST)

    def _scan(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, val in obj.items():
                if key == "vault__ldap_domain_user_map" and isinstance(val, dict):
                    for username in val.keys():
                        usernames_to_map.add(username)
                elif isinstance(val, (dict, list)):
                    _scan(val)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    _scan(item)

    _scan(data)

    for username in sorted(usernames_to_map):
        if username not in LDAP_USER_MAPPING:
            if username.lower() in PRESERVED_LDAP_USERNAMES:
                profile = {
                    "username": username,
                    "cn": username.capitalize(),
                    "given_name": username.capitalize(),
                    "sn": "Admin" if username == "admin" else "User",
                    "display_name": username.capitalize(),
                    "initials": username[:2].upper(),
                    "mail": f"{username}@example.int"
                }
                LDAP_USER_PROFILE_MAP[username] = profile
                LDAP_USER_MAPPING[username] = username
            else:
                if pool:
                    profile = pool.pop(0)
                    fake_user = profile["username"]
                    LDAP_USER_PROFILE_MAP[username] = profile
                    LDAP_USER_MAPPING[username] = fake_user
                else:
                    fake_user = f"user_{len(LDAP_USER_MAPPING)}"
                    profile = {
                        "username": fake_user,
                        "cn": f"User {fake_user}",
                        "given_name": "User",
                        "sn": fake_user,
                        "display_name": f"User {fake_user}",
                        "initials": "U",
                        "mail": f"{fake_user}@example.int"
                    }
                    LDAP_USER_PROFILE_MAP[username] = profile
                    LDAP_USER_MAPPING[username] = fake_user


def scramble_char(c: str) -> str:
    """Replace a single character with one from the same category."""
    if c.islower():
        return random.choice(string.ascii_lowercase)
    if c.isupper():
        return random.choice(string.ascii_uppercase)
    if c.isdigit():
        return random.choice(string.digits)
    if c.isspace():
        return c

    # Preserve common structural special characters
    if c in PRESERVED_SPECIAL_CHARS:
        return c

    # Everything else → random special (excluding the ones we just preserved)
    return random.choice("!#$%^&*()_+[]{}|;:.<>?")


def scramble_chars(text: str) -> str:
    """Category-aware scramble, leaving placeholders and protected tokens intact."""
    if not text:
        return text

    # Combined pattern: placeholders OR protected tokens
    combined_re = re.compile(
        r"(__TARGET_DOMAIN_\d+__)|"
        r"(\b(?:" + "|".join(re.escape(t) for t in sorted(PRESERVE_TOKENS, key=len, reverse=True)) + r")\b)",
        re.IGNORECASE
    )

    # Protect placeholders so they survive scrambling
    parts = []
    last_end = 0
    for match in combined_re.finditer(text):
        before = text[last_end:match.start()]
        if before:
            parts.append("".join(scramble_char(c) for c in before))
        # keep the matched token / placeholder exactly
        parts.append(match.group(0))
        last_end = match.end()

    # scramble any remaining text after the last placeholder
    after = text[last_end:]
    if after:
        parts.append("".join(scramble_char(c) for c in after))

    return "".join(parts)


def replace_mapped_usernames(text: str) -> str:
    """Replace any original usernames with their mapped usernames across strings/templates."""
    if not LDAP_USER_MAPPING:
        return text
    # Sort usernames by length descending to prevent partial replacement issues
    sorted_usernames = sorted(LDAP_USER_MAPPING.keys(), key=len, reverse=True)
    for orig in sorted_usernames:
        mapped = LDAP_USER_MAPPING[orig]
        if orig == mapped:
            continue
        # Use regex word boundaries to safely replace whole username occurrences
        pattern = r'\b' + re.escape(orig) + r'\b'
        text = re.sub(pattern, mapped, text)
    return text


def scramble_string(value: str) -> str:
    """Scramble a string while preserving structure, prefixes, Jinja, domains, and translating usernames."""
    if not value:
        return value

    # Translate any mapped usernames anywhere in the string (including Jinja templates/lookups)
    value = replace_mapped_usernames(value)

    # 1. Anonymize known sensitive domains first
    value = anonymize_domains(value)

    # 2. Protect the resulting example.* domains from further scrambling
    value, domain_placeholders = protect_target_domains(value)

    def _finish(result: str) -> str:
        return restore_target_domains(result, domain_placeholders)

    # Exact short-value / boolean whitelist
    if value.strip().lower() in PRESERVE_TOKENS:
        return _finish(value)

    # ------------------------------------------------------------------
    # Multi-line handling
    # ------------------------------------------------------------------
    if "\n" in value:
        contains_jinja = ("{{" in value) or ("{%" in value)
        lines = value.splitlines(keepends=True)
        result_lines = []

        for line in lines:
            if line.endswith("\n"):
                content, nl = line[:-1], "\n"
            else:
                content, nl = line, ""

            stripped = content.strip()

            # Preserve PEM / OpenVPN headers/footers and INI-style section headers like [Interface]
            if (
                (stripped.startswith("-----BEGIN ") and
                 ("PRIVATE KEY-----" in stripped or "OpenVPN Static key" in stripped)) or
                (stripped.startswith("-----END ") and
                 ("PRIVATE KEY-----" in stripped or "OpenVPN Static key" in stripped)) or
                (stripped.startswith("[") and stripped.endswith("]"))
            ):
                result_lines.append(content + nl)
                continue

            # Blank / whitespace-only lines stay as-is
            if not stripped:
                result_lines.append(content + nl)
                continue

            # Aggressive Jinja protection
            if contains_jinja:
                # Line contains Jinja → leave completely untouched
                if "{{" in content or "{%" in content:
                    result_lines.append(content + nl)
                    continue
                # Pure structural bracket lines also left untouched
                if re.fullmatch(r"[\s\[\]\{\}]*", content):
                    result_lines.append(content + nl)
                    continue

            result_lines.append(scramble_string(content) + nl)

        return _finish("".join(result_lines))

    # ------------------------------------------------------------------
    # Single-line handling
    # ------------------------------------------------------------------

    # 1. Special preserved prefixes
    m = PRESERVED_PREFIX_RE.match(value)
    if m:
        prefix = next(g for g in m.groups() if g is not None)
        rest = value[len(prefix):]
        return _finish(prefix + scramble_string(rest))

    # 2. Protect Jinja2 expressions
    jinja_matches = list(JINJA_RE.finditer(value))
    if jinja_matches:
        parts = []
        last_end = len(value)

        for match in reversed(jinja_matches):
            start, end = match.span()

            # text after this expression → scramble
            after = value[end:last_end]
            if after:
                parts.append(scramble_chars(after))

            # keep the Jinja expression exactly
            parts.append(match.group(0))
            last_end = start

        # text before the first expression → scramble
        before = value[:last_end]
        if before:
            parts.append(scramble_chars(before))

        return _finish("".join(reversed(parts)))

    # 3. Email protection (translate local part if in LDAP_USER_MAPPING, anonymize domain)
    emails = list(EMAIL_RE.finditer(value))
    if emails:
        parts = []
        last_end = len(value)

        for match in reversed(emails):
            start, end = match.span()
            after = value[end:last_end]
            if after:
                parts.append(scramble_chars(after))

            email_str = match.group(0)
            local_part, _, domain_part = email_str.partition("@")

            # Translate local part if it matches a known mapped username
            new_local = LDAP_USER_MAPPING.get(local_part, local_part)
            new_domain = anonymize_domains(domain_part)
            parts.append(f"{new_local}@{new_domain}")

            ws_start = start
            while ws_start > 0 and value[ws_start - 1].isspace():
                ws_start -= 1
            if ws_start < start:
                parts.append(value[ws_start:start])
                start = ws_start

            last_end = start

        before = value[:last_end]
        if before:
            parts.append(scramble_chars(before))

        return _finish("".join(reversed(parts)))

    # 4. Fallback
    return _finish(scramble_chars(value))


def is_excluded(skip_exclusions: bool, k: Any) -> bool:
    return (
        not skip_exclusions
        and isinstance(k, str)
        and any(p.fullmatch(k) for p in COMPILED_EXCLUDED_PATTERNS)
    )


def scramble_value(obj: Any, path: str = "", key_name: str = "", skip_exclusions: bool = False) -> Any:
    """Recursively scramble string values and anonymize domains in keys and values in-place."""
    if isinstance(obj, CommentedMap):
        seen_keys: dict[str, str] = {}

        # Build a new map containing only the keys we keep.  Comments that
        # immediately precede a key are stored by ruamel.yaml as the post-comment
        # (index 2) on the *previous* key.  When the next key is excluded we must
        # therefore clear that post-comment on the kept key while transferring it;
        # otherwise the section header for the dropped key is re-attached to the
        # next surviving key.  Rebuilding the map also drops any start/end comments
        # that belonged solely to excluded keys.
        new_map = CommentedMap()
        first_key_kept = False

        keys_to_process = list(obj.keys())

        for idx, key in enumerate(keys_to_process):
            original_key = key

            # Skip/exclude keys matching any pattern in EXCLUDED_KEY_PATTERNS
            # (unless --no-exclude was supplied)
            if is_excluded(skip_exclusions, original_key):
                log.debug(
                    f"Excluding key '{original_key}' from scrambled output due to exclusion pattern."
                )
                continue

            # From here on the key is being kept
            if not first_key_kept:
                first_key_kept = True
                # Preserve the map/document start comment only when the very first
                # original key is kept.  Those comments document the first key
                # (e.g. "# ansible host credentials" before vault__ansible_host_credentials).
                # If leading keys were excluded, the start comment belonged to them
                # and must be dropped.
                if (
                    idx == 0
                    and hasattr(obj, "ca")
                    and obj.ca is not None
                    and obj.ca.comment
                ):
                    new_map.ca.comment = obj.ca.comment

            new_key = key
            if isinstance(key, str):
                new_key = anonymize_domains(key)
                # If the key is a known LDAP username, map it consistently
                if key in LDAP_USER_MAPPING:
                    new_key = LDAP_USER_MAPPING[key]

            if new_key in seen_keys and seen_keys[new_key] != original_key:
                log.warning(
                    "Key collision after domain anonymization/user mapping: "
                    f"'{seen_keys[new_key]}' and '{original_key}' "
                    f"both became '{new_key}'"
                )
            seen_keys[new_key] = original_key

            child_path = f"{path}.{original_key}" if path else str(original_key)

            # Will the next original key be excluded?  If so, the post-comment on
            # *this* key is the section header for that excluded key and must be
            # dropped when we transfer the comment artifact.
            next_is_excluded = False
            if idx + 1 < len(keys_to_process):
                next_is_excluded = is_excluded(skip_exclusions, keys_to_process[idx + 1])

            def _transfer_ca(src_key: Any, dst_key: Any, value: Any = None) -> None:
                if (
                    hasattr(obj, "ca")
                    and obj.ca is not None
                    and hasattr(obj.ca, "items")
                    and src_key in obj.ca.items
                ):
                    artifact = list(obj.ca.items[src_key])  # shallow copy of the 4-slot list
                    if next_is_excluded and len(artifact) > 2:
                        # Drop the post-comment that introduced the following excluded section
                        artifact[2] = None
                    new_map.ca.items[dst_key] = artifact

                # When the next key is excluded and this value is a nested map,
                # also clear trailing comments on the nested map (end comments and
                # post-comment of its last child).  Section headers that follow a
                # complex value are often attached there.
                if next_is_excluded and isinstance(value, CommentedMap) and hasattr(value, "ca") and value.ca is not None:
                    value.ca.end = None
                    value.ca.comment = None
                    if value.ca.items:
                        last_child = list(value.keys())[-1]
                        if last_child in value.ca.items:
                            child_art = list(value.ca.items[last_child])
                            if len(child_art) > 2:
                                child_art[2] = None
                            value.ca.items[last_child] = child_art

            # Check if we are directly inside a user block within vault__ldap_domain_user_map
            if original_key in LDAP_USER_PROFILE_MAP and path.endswith(
                "vault__ldap_domain_user_map"
            ):
                profile = LDAP_USER_PROFILE_MAP[original_key]
                # Override child map attributes cleanly with profile values
                sub_map = obj[original_key]
                if isinstance(sub_map, CommentedMap):
                    for sub_k, sub_v in list(sub_map.items()):
                        sub_k_lower = sub_k.lower()
                        if sub_k_lower == "cn":
                            sub_map[sub_k] = profile["cn"]
                        elif sub_k_lower in ("given_name", "givenname"):
                            sub_map[sub_k] = profile["given_name"]
                        elif sub_k_lower == "sn":
                            sub_map[sub_k] = profile["sn"]
                        elif sub_k_lower in ("display_name", "displayname"):
                            sub_map[sub_k] = profile["display_name"]
                        elif sub_k_lower == "initials":
                            sub_map[sub_k] = profile["initials"]
                        elif sub_k_lower == "mail":
                            sub_map[sub_k] = profile["mail"]
                        elif sub_k_lower == "username":
                            sub_map[sub_k] = profile["username"]
                        else:
                            sub_map[sub_k] = scramble_value(
                                sub_v,
                                path=f"{child_path}.{sub_k}",
                                key_name=str(sub_k),
                                skip_exclusions=skip_exclusions,
                            )
                new_map[new_key] = sub_map
                _transfer_ca(original_key, new_key, value=sub_map)
                continue

            # Process value recursively
            val = obj[original_key]
            scrambled_val = scramble_value(
                val,
                path=child_path,
                key_name=str(original_key),
                skip_exclusions=skip_exclusions,
            )

            new_map[new_key] = scrambled_val
            _transfer_ca(original_key, new_key, value=scrambled_val)

        # Replace the contents of the original map with the cleaned version so that
        # callers that hold a reference still see the updated data.
        # Capture start/end comments before clear() in case clear resets the Comment.
        preserved_start_comment = new_map.ca.comment if hasattr(new_map, "ca") and new_map.ca else None
        preserved_end_comment = getattr(new_map.ca, "end", None) if hasattr(new_map, "ca") and new_map.ca else None
        preserved_items = dict(new_map.ca.items) if hasattr(new_map, "ca") and new_map.ca and new_map.ca.items else {}

        obj.clear()
        if hasattr(obj, "ca") and obj.ca is not None:
            obj.ca.items.clear()
            obj.ca.comment = preserved_start_comment
            obj.ca.end = preserved_end_comment
        for k, v in new_map.items():
            obj[k] = v
            if k in preserved_items:
                obj.ca.items[k] = preserved_items[k]

        return obj

    if isinstance(obj, CommentedSeq):
        for i, item in enumerate(obj):
            obj[i] = scramble_value(
                item, path=f"{path}[{i}]", key_name=key_name, skip_exclusions=skip_exclusions
            )
        return obj

    if isinstance(
        obj,
        (
            LiteralScalarString,
            DoubleQuotedScalarString,
            SingleQuotedScalarString,
            PlainScalarString,
            str,
        ),
    ):
        val_str = str(obj)

        # Check if the key name indicates a sensitive credential pattern
        key_lower = key_name.lower()
        is_secret_key = any(term in key_lower for term in PASSWORD_KEY_PATTERNS)

        # Check if the scalar string itself is a known username (e.g. inside memberUidList or memberDnList)
        if val_str in LDAP_USER_MAPPING:
            scrambled = LDAP_USER_MAPPING[val_str]
        elif is_secret_key:
            # Smart guard: ensure structured blocks (SSH keys), prefixed strings, hashes, or templates
            # fall back to standard character-scrambling rather than getting overwritten by random passwords.
            is_structured_or_special = (
                "\n" in val_str
                or bool(PRESERVED_PREFIX_RE.match(val_str))
                or "{{" in val_str
                or "{%" in val_str
                or val_str.strip().startswith("{")
                or (val_str.strip().startswith("$") and val_str.count("$") >= 2)
            )
            if not is_structured_or_special:
                scrambled = generate_strong_password()
            else:
                scrambled = scramble_string(val_str)
        elif (
            key_name.lower() in SKIP_LDAP_KEYS
            or key_name.lower() in ("cn", "ou")
            or key_name.lower().endswith("_ou")
        ):
            # Preserve LDAP structural/class names and paths verbatim
            scrambled = val_str
        else:
            scrambled = scramble_string(val_str)

        # Try to preserve the original scalar style
        if isinstance(obj, LiteralScalarString):
            return LiteralScalarString(scrambled)
        if isinstance(obj, DoubleQuotedScalarString):
            return DoubleQuotedScalarString(scrambled)
        if isinstance(obj, SingleQuotedScalarString):
            # Prefer double quotes for simple Jinja
            if scrambled.strip().startswith("{{") and scrambled.strip().endswith("}}"):
                return DoubleQuotedScalarString(scrambled)
            return SingleQuotedScalarString(scrambled)

        # Plain string – decide style
        if "\n" in scrambled:
            return LiteralScalarString(scrambled)
        if scrambled.strip().startswith("{{") and scrambled.strip().endswith("}}"):
            return DoubleQuotedScalarString(scrambled)
        return scrambled

    return obj


def scramble_vault_file_data(obj: Any, skip_exclusions: bool = False) -> Any:
    """Recursively traverse YAML data and scramble Ansible Vault string bodies in-place."""
    if isinstance(obj, CommentedMap):
        # Rebuild with only kept keys so that comments belonging to excluded keys
        # are dropped cleanly (same approach as scramble_value).
        new_map = CommentedMap()
        first_key_kept = False
        keys_to_process = list(obj.keys())

        for idx, key in enumerate(keys_to_process):
            # Skip/exclude keys matching any pattern in EXCLUDED_KEY_PATTERNS
            # (unless --no-exclude was supplied)
            if is_excluded(skip_exclusions, key):
                continue

            if not first_key_kept:
                first_key_kept = True
                if idx == 0 and hasattr(obj, "ca") and obj.ca is not None and obj.ca.comment:
                    new_map.ca.comment = obj.ca.comment

            next_is_excluded = (
                idx + 1 < len(keys_to_process) and is_excluded(skip_exclusions, keys_to_process[idx + 1])
            )

            val = scramble_vault_file_data(obj[key], skip_exclusions=skip_exclusions)
            new_map[key] = val

            if (
                hasattr(obj, "ca")
                and obj.ca is not None
                and hasattr(obj.ca, "items")
                and key in obj.ca.items
            ):
                artifact = list(obj.ca.items[key])
                if next_is_excluded and len(artifact) > 2:
                    artifact[2] = None
                new_map.ca.items[key] = artifact

            if next_is_excluded and isinstance(val, CommentedMap) and hasattr(val, "ca") and val.ca is not None:
                val.ca.end = None
                val.ca.comment = None
                if val.ca.items:
                    last_child = list(val.keys())[-1]
                    if last_child in val.ca.items:
                        child_art = list(val.ca.items[last_child])
                        if len(child_art) > 2:
                            child_art[2] = None
                        val.ca.items[last_child] = child_art

        preserved_start_comment = new_map.ca.comment if hasattr(new_map, "ca") and new_map.ca else None
        preserved_end_comment = getattr(new_map.ca, "end", None) if hasattr(new_map, "ca") and new_map.ca else None
        preserved_items = dict(new_map.ca.items) if hasattr(new_map, "ca") and new_map.ca and new_map.ca.items else {}

        obj.clear()
        if hasattr(obj, "ca") and obj.ca is not None:
            obj.ca.items.clear()
            obj.ca.comment = preserved_start_comment
            obj.ca.end = preserved_end_comment
        for k, v in new_map.items():
            obj[k] = v
            if k in preserved_items:
                obj.ca.items[k] = preserved_items[k]
        return obj
    elif isinstance(obj, CommentedSeq):
        for i, item in enumerate(obj):
            obj[i] = scramble_vault_file_data(item, skip_exclusions=skip_exclusions)
        return obj
    elif isinstance(obj, str):
        if obj.startswith("$ANSIBLE_VAULT;"):
            lines = obj.splitlines(keepends=True)
            if lines:
                header = lines[0]
                body = "".join(lines[1:])
                scrambled_body = "".join(scramble_char(c) for c in body)
                return VaultString(header + scrambled_body)
        return obj
    return obj


def _is_blank(s: str) -> bool:
    return not s.strip()


def _is_pure_comment(s: str) -> bool:
    stripped = s.lstrip()
    return stripped.startswith("#") or _is_blank(s)


def _is_decorative(s: str) -> bool:
    """True for pure separator lines: ####, #-----, #=====, etc."""
    stripped = s.strip()
    return bool(re.fullmatch(r"#+[-=_*#]*", stripped)) and len(stripped) >= 3


def _is_title_line(s: str) -> bool:
    """True for short noun-phrase titles like '# vmware' or '## IDRAC'.

    Rejects instructional / command-like comments such as
    '# openssl rand -hex 32' or '# docker exec -it ...'.
    """
    stripped = s.strip()
    if not stripped.startswith("#") or _is_decorative(stripped) or len(stripped) >= 60:
        return False
    rest = re.sub(r"^#{1,3}\s*", "", stripped)
    # Title: only letters, digits, spaces, underscores, hyphens; no shell punctuation
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]*", rest):
        return False
    words = rest.split()
    if not (1 <= len(words) <= 4):
        return False
    # Reject command-style lines where a token looks like a flag (-hex, --help)
    if any(w.startswith("-") for w in words):
        return False
    return True


def _short_title_tokens(block: list[str]) -> list[str]:
    """Tokens from short '# title' lines only (ignore instructional comments)."""
    tokens: list[str] = []
    for ln in block:
        if not _is_title_line(ln):
            continue
        rest = re.sub(r"^#{1,3}\s*", "", ln.strip()).lower()
        tokens.extend(re.findall(r"[a-z0-9]+", rest))
    return tokens


def _looks_like_section_header(block: list[str]) -> bool:
    """True for section-header blocks that should be considered for stripping.

    A block is a section header when it has a decorative separator
    (``#----``, ``####``) or only short title lines.  Blocks that mix
    title-like lines with instructional/command comments (e.g. openssl
    howto, "Generate with" + docker run) are left alone unless they also
    have a decorative separator.
    """
    content_lines = [ln.strip() for ln in block if not _is_blank(ln)]
    if not content_lines:
        return False
    has_decorative = any(_is_decorative(ln) for ln in content_lines)
    has_title = any(_is_title_line(ln) for ln in content_lines)
    has_other = any(
        not _is_decorative(ln) and not _is_title_line(ln)
        for ln in content_lines
    )
    if has_decorative:
        return True
    if has_title and not has_other:
        return True
    return False


def _strip_orphaned_section_headers(text: str) -> str:
    """Remove comment-only section headers that belonged to excluded keys.

    After excluded keys are dropped, their preceding section headers (e.g.
    the whole openbao / vmware comment block) can remain as trailing whitespace
    of a previous key or nested map.  This text pass removes an entire
    pure-comment/blank block when it looks like a section header and does not
    clearly belong to the following key.

    The document-start comment block (comments before the first key) is never
    stripped, so headers for a kept first key are preserved.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    n = len(lines)

    # Track whether we have already emitted a real YAML key.  The comment block
    # that appears before the first key is the document-start comment; when the
    # first key was kept it documents that key and must never be stripped.
    seen_key = False

    while i < n:
        if _is_pure_comment(lines[i]):
            j = i
            while j < n and _is_pure_comment(lines[j]):
                j += 1
            block = lines[i:j]
            next_line = lines[j] if j < n else ""
            next_is_key = bool(re.match(r"^[A-Za-z0-9_.\"'-]+:", next_line.lstrip()))

            # Never strip the document-start comment block.
            if not seen_key:
                out.extend(block)
                i = j
                continue

            # Strip an entire section-header block when it does not own the
            # following key.  Ownership = a majority of short-title tokens
            # appear in the key name.  Decorative-only blocks (or blocks whose
            # only short title is unrelated to the key) are always dropped.
            if next_is_key and _looks_like_section_header(block):
                title_tokens = _short_title_tokens(block)
                key_name = ""
                m = re.match(r"^([A-Za-z0-9_.\"'-]+)\s*:", next_line.lstrip())
                if m:
                    key_name = m.group(1).strip("\"'").lower()
                significant = [tok for tok in title_tokens if len(tok) > 2]
                if significant:
                    matches = sum(1 for tok in significant if tok in key_name)
                    owned = matches >= max(1, (len(significant) + 1) // 2)
                else:
                    # Decorative separator with no short title → orphaned
                    owned = False
                if not owned:
                    if out and not _is_blank(out[-1]):
                        out.append("\n")
                    i = j
                    continue

            out.extend(block)
            i = j
            continue

        out.append(lines[i])
        i += 1

    return "".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    prog_usage = f"""
Examples of use:

  # Already-decrypted / simulated vault file (recommended for testing)
  {__scriptName__} --plaintext vault.example.yml > scrambled.yml

  # Live Ansible Vault file (uses ~/.vault_pass automatically)
  {__scriptName__} --vault inventory/group_vars/all/vault.yml > scrambled.yml

  # Explicit password file
  {__scriptName__} --vault --vault-password-file ~/.vault_pass vault.yml

  # Scramble encrypted vault strings directly without decrypting (preserving $ANSIBLE_VAULT headers)
  {__scriptName__} --scramble-vault vars/vault.yml > scrambled_vault.yml

  # Reproducible scrambling (useful when iterating)
  {__scriptName__} --seed 42 --plaintext vault.example.yml > scrambled.yml

  # Scramble every key (do not drop keys matching EXCLUDED_KEY_PATTERNS)
  {__scriptName__} --no-exclude --plaintext vault.example.yml > scrambled.yml

  # Debug logging
  {__scriptName__} -L DEBUG --plaintext vault.example.yml
"""

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "Scramble string values in a YAML / Ansible Vault file\n"
            "with same-length random strings so the structure can be\n"
            "shared safely when designing a credentials.yml + vault.yml split.\n\n"
            "Uses ruamel.yaml so comments and blank lines are preserved."
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
        help="YAML or vault-encrypted file to scramble",
    )

    # Mutually exclusive mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--vault",
        action="store_true",
        help="Treat the file as Ansible Vault encrypted (will attempt decryption)",
    )
    mode_group.add_argument(
        "--plaintext",
        action="store_true",
        help="Treat the file as plain-text / already-decrypted (useful for testing)",
    )
    mode_group.add_argument(
        "--scramble-vault",
        action="store_true",
        help="Scramble encrypted vault strings directly while preserving $ANSIBLE_VAULT headers and character types",
    )

    parser.add_argument(
        "--vault-password-file",
        help="Path to vault password file (default: ~/.vault_pass)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Optional random seed for reproducible scrambling",
    )
    parser.add_argument(
        "--no-exclude",
        action="store_true",
        help=(
            "Do not drop keys matching EXCLUDED_KEY_PATTERNS / COMPILED_EXCLUDED_PATTERNS; "
            "scramble all keys instead"
        ),
    )

    args = parser.parse_args()
    setup_logging(args.loglevel)

    log.debug("Started scrambler run")

    if args.seed is not None:
        random.seed(args.seed)
        log.debug(f"Random seed set to {args.seed}")

    if not args.file.is_file():
        log.error(f"File not found: {args.file}")
        sys.exit(1)

    raw = args.file.read_bytes()

    if args.scramble_vault:
        log.info(f"Treating {args.file} as vault text for ciphertext scrambling")
        content = raw.decode()
    else:
        # Determine processing mode for standard decryption/plaintext
        if args.plaintext:
            is_vault = False
            log.info(f"Forced plain-text mode for {args.file}")
        elif args.vault:
            is_vault = True
            log.info(f"Forced vault mode for {args.file}")
        else:
            # Auto-detect
            is_vault = raw.startswith(b"$ANSIBLE_VAULT")
            if is_vault:
                log.info(f"Auto-detected vault encryption on {args.file}")
            else:
                log.info(f"Treating {args.file} as plain YAML (auto-detect)")

        if is_vault:
            log.info(f"Detected / forced vault decryption on {args.file}")
            password = load_vault_password(args.vault_password_file)

            try:
                if password and HAS_ANSIBLE:
                    content = decrypt_with_ansible(raw, password)
                else:
                    # Fall back to ansible-vault CLI (it can discover the password)
                    content = decrypt_with_cli(args.file, args.vault_password_file)
            except Exception as e:
                log.error(f"Failed to decrypt vault file:\n{e}")
                sys.exit(1)
        else:
            log.info(f"Treating {args.file} as plain YAML")
            content = raw.decode()

    # ------------------------------------------------------------------
    # Load with ruamel.yaml (preserves comments & blank lines)
    # ------------------------------------------------------------------
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

    log.debug("Anonymizing domains in YAML comments...")
    anonymize_comments(data)

    if args.scramble_vault:
        log.info("Scrambling Ansible Vault encrypted strings while preserving headers...")
        scrambled = scramble_vault_file_data(data, skip_exclusions=args.no_exclude)
    else:
        log.debug("Build consistent mapping for LDAP usernames across user and group maps...")
        build_user_mapping(data)

        log.info("Scrambling string values (preserving length, structure, comments)...")
        scrambled = scramble_value(data, skip_exclusions=args.no_exclude)

    # Emit the scrambled YAML to a buffer first so we can strip orphaned section
    # headers that belonged to excluded keys.  ruamel.yaml sometimes retains
    # trailing whitespace/comments from nested maps in a way that is not exposed
    # via the public Comment API; a light text pass removes those cleanly.
    from io import StringIO
    buf = StringIO()
    yaml.dump(scrambled, buf)
    text = buf.getvalue()

    if not args.no_exclude:
        text = _strip_orphaned_section_headers(text)

    sys.stdout.write(text)

    log.debug("Finished scrambler run successfully")


if __name__ == "__main__":
    main()
