#!/usr/bin/env python3
"""Unit tests for vault_scrambler.py."""

from __future__ import annotations

import importlib.util
import io
import random
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

# ---------------------------------------------------------------------------
# Dynamic module import (matches test_vault_organizer.py convention)
# ---------------------------------------------------------------------------
_CANDIDATE_PATHS = [
    Path(__file__).resolve().parents[2] / "vault_scrambler.py",
    Path(__file__).resolve().parent / "vault_scrambler.py",
    Path(__file__).resolve().parent / "vault_scrambler_7.py",
    Path(__file__).resolve().parent / "vault_scrambler_8.py",
]
MODULE_PATH = next((p for p in _CANDIDATE_PATHS if p.is_file()), _CANDIDATE_PATHS[0])

spec = importlib.util.spec_from_file_location("vault_scrambler", MODULE_PATH)
assert spec and spec.loader
vs = importlib.util.module_from_spec(spec)
sys.modules["vault_scrambler"] = vs
spec.loader.exec_module(vs)


def _make_yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 120
    y.indent(mapping=2, sequence=4, offset=2)
    y.explicit_start = True
    y.constructor.add_constructor(
        "!vault", lambda l, n: vs.VaultString(l.construct_scalar(n))
    )
    y.representer.add_representer(
        vs.VaultString, lambda r, d: r.represent_scalar("!vault", d, style="|")
    )
    return y


def _roundtrip(raw_yaml: str, skip_exclusions: bool = False) -> tuple[CommentedMap, str]:
    y = _make_yaml()
    data = y.load(raw_yaml)
    vs.anonymize_comments(data)
    vs.build_user_mapping(data)
    scrambled = vs.scramble_value(data, skip_exclusions=skip_exclusions)
    buf = io.StringIO()
    y.dump(scrambled, buf)
    text = buf.getvalue()
    if not skip_exclusions:
        text = vs._strip_orphaned_section_headers(text)
    return scrambled, text


@pytest.fixture(autouse=True)
def _reset_global_state() -> None:
    """Ensure deterministic RNG and clean global user mappings per test."""
    random.seed(42)
    vs.LDAP_USER_MAPPING.clear()
    vs.LDAP_USER_PROFILE_MAP.clear()


# ---------------------------------------------------------------------------
# Character & String Scrambling Tests
# ---------------------------------------------------------------------------
class TestCharacterAndStringScrambling:
    def test_scramble_char_preserves_category(self) -> None:
        assert vs.scramble_char("a").islower()
        assert vs.scramble_char("Z").isupper()
        assert vs.scramble_char("7").isdigit()
        assert vs.scramble_char(" ") == " "
        assert vs.scramble_char("\n") == "\n"
        for ch in vs.PRESERVED_SPECIAL_CHARS:
            assert vs.scramble_char(ch) == ch

    def test_scramble_string_preserves_length_and_structure(self) -> None:
        original = "MySecretValue_12345!"
        scrambled = vs.scramble_string(original)
        assert len(scrambled) == len(original)
        assert scrambled != original
        for orig_c, new_c in zip(original, scrambled):
            if orig_c.islower():
                assert new_c.islower()
            elif orig_c.isupper():
                assert new_c.isupper()
            elif orig_c.isdigit():
                assert new_c.isdigit()

    def test_preserves_tokens_and_prefixes(self) -> None:
        assert vs.scramble_string("true") == "true"
        assert vs.scramble_string("enabled") == "enabled"
        assert vs.scramble_string("gpu01") == "gpu01"

        ssh_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl user@host"
        scrambled_ssh = vs.scramble_string(ssh_key)
        assert scrambled_ssh.startswith("ssh-ed25519 ")
        assert len(scrambled_ssh) == len(ssh_key)

        github_pat = "github_pat_11ABCDEFG0123456789_xyz9876543210"
        scrambled_pat = vs.scramble_string(github_pat)
        assert scrambled_pat.startswith("github_pat_")
        assert len(scrambled_pat) == len(github_pat)

        ssha = "{SSHA}AbCdEfGhIjKlMnOpQrStUvWxYz012345"
        scrambled_ssha = vs.scramble_string(ssha)
        assert scrambled_ssha.startswith("{SSHA}")
        assert len(scrambled_ssha) == len(ssha)

    def test_preserves_jinja_expressions(self) -> None:
        tpl = "prefix_{{ vault__other_secret | default('abc') }}_suffix"
        scrambled = vs.scramble_string(tpl)
        assert "{{ vault__other_secret | default('abc') }}" in scrambled
        assert not scrambled.startswith("prefix_")
        assert not scrambled.endswith("_suffix")

    def test_multiline_pem_and_ini_headers_preserved(self) -> None:
        pem = (
            "-----BEGIN PRIVATE KEY-----\n"
            "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7\n"
            "-----END PRIVATE KEY-----\n"
        )
        scrambled_pem = vs.scramble_string(pem)
        lines = scrambled_pem.splitlines()
        assert lines[0] == "-----BEGIN PRIVATE KEY-----"
        assert lines[2] == "-----END PRIVATE KEY-----"
        assert lines[1] != "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7"
        assert len(lines[1]) == 52

        ini = "[Interface]\nPrivateKey = AbCdEfGhIjKlMnOpQrStUvWxYz123456=\n"
        scrambled_ini = vs.scramble_string(ini)
        assert scrambled_ini.startswith("[Interface]\n")


# ---------------------------------------------------------------------------
# Domain Anonymization & Comment Anonymization Tests
# ---------------------------------------------------------------------------
class TestDomainAnonymization:
    def test_anonymize_domains_in_values_and_keys(self) -> None:
        raw = """---
# Server endpoint for internal.dettonville.int and admin@dettonville.com
vault__custom_endpoint: "https://api.dettonville.int:8443/v1"
vault__secondary_host: "node01.johnson.int"
vault__contact_email: "ops@dettonville.com"
"""
        scrambled, rendered = _roundtrip(raw)
        assert "vault__custom_endpoint" in scrambled
        assert "vault__secondary_host" in scrambled
        assert "vault__contact_email" in scrambled
        assert "johnson.int" not in rendered.lower()
        assert "example.int" in rendered
        assert "example.com" in rendered
        assert "qa-example.int" in rendered


# ---------------------------------------------------------------------------
# LDAP User Mapping & Secret Key Generation Tests
# ---------------------------------------------------------------------------
class TestLdapAndSecrets:
    def test_ldap_user_profile_mapping_and_consistency(self) -> None:
        raw = """---
vault__ldap_domain_user_map:
  jdoe:
    cn: "John Doe"
    given_name: "John"
    sn: "Doe"
    display_name: "John Doe"
    initials: "JD"
    mail: "jdoe@dettonville.int"
    username: "jdoe"
  admin:
    cn: "Admin"
    username: "admin"
vault__ldap_domain_group_map:
  admins:
    cn: "admins"
    memberUidList:
      - "jdoe"
      - "admin"
vault__custom_ref: "jdoe@dettonville.com and {{ lookup('vars', 'jdoe') }}"
"""
        scrambled, _ = _roundtrip(raw)
        user_map = scrambled["vault__ldap_domain_user_map"]
        # Preserved system user stays intact
        assert "admin" in user_map
        # Non-system user 'jdoe' is mapped to a pool user
        assert "jdoe" not in user_map
        mapped_username = next(k for k in user_map.keys() if k != "admin")
        profile = user_map[mapped_username]
        assert profile["username"] == mapped_username
        assert profile["mail"].endswith("@example.int")

        # Group membership and Jinja references reflect the mapped username
        members = scrambled["vault__ldap_domain_group_map"]["admins"]["memberUidList"]
        assert mapped_username in members
        assert "admin" in members
        assert "@example.com" in scrambled["vault__custom_ref"]
        assert f"'{mapped_username}'" in scrambled["vault__custom_ref"]

    def test_password_keys_generate_strong_passwords(self) -> None:
        raw = """---
vault__custom_admin_password: "oldpassword"
vault__custom_structured_password: "{{ vault__other_password }}"
"""
        scrambled, _ = _roundtrip(raw)
        pwd = scrambled["vault__custom_admin_password"]
        assert vs.PASSWORD_MIN_LENGTH <= len(pwd) <= vs.PASSWORD_MAX_LENGTH
        assert any(c.islower() for c in pwd)
        assert any(c.isupper() for c in pwd)
        assert any(c.isdigit() for c in pwd)
        assert any(c in "!@#$%^&*-_=+" for c in pwd)
        # Jinja-templated password key is NOT overwritten by random password
        assert scrambled["vault__custom_structured_password"] == "{{ vault__other_password }}"


# ---------------------------------------------------------------------------
# Exclusions & Orphaned Section Header Stripping Tests
# ---------------------------------------------------------------------------
class TestExclusionsAndComments:
    def test_excludes_matching_apps_and_strips_orphaned_headers(self) -> None:
        raw = """---
# Custom kept first
vault__custom_kept_first: "value1"

# --------------------
# openbao
# --------------------
vault__openbao_root_token: "s.1234567890"

vault__custom_kept_second: "value2"
"""
        scrambled, rendered = _roundtrip(raw, skip_exclusions=False)
        assert "vault__openbao_root_token" not in scrambled
        assert "vault__custom_kept_first" in scrambled
        assert "vault__custom_kept_second" in scrambled
        assert "# Custom kept first" in rendered
        assert "openbao" not in rendered.lower()
        assert "vault__custom_kept_second:" in rendered

    def test_no_exclude_retains_all_keys(self) -> None:
        raw = """---
vault__openbao_root_token: "s.1234567890"
vault__custom_kept: "value1"
"""
        scrambled, _ = _roundtrip(raw, skip_exclusions=True)
        assert "vault__openbao_root_token" in scrambled
        assert "vault__custom_kept" in scrambled


# ---------------------------------------------------------------------------
# Direct Vault Ciphertext Scrambling (--scramble-vault) Tests
# ---------------------------------------------------------------------------
class TestScrambleVaultMode:
    def test_scramble_vault_preserves_header_and_scrambles_body(self) -> None:
        raw = """---
bootstrap_ansible_controller__vaulted_credentials_default:
  aap_project_git_deploy_key: !vault |
    $ANSIBLE_VAULT;1.1;AES256
    30353964323139343730353362613239353939303934663039393738636231336330616261366131
    3837653737623939666634653733366331353533616263300a623938643339656263643132333432

cyberark_test_safe_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  62333233633864353236383433393464636266633134396535386532326431623263626237386637
"""
        y = _make_yaml()
        data = y.load(raw)
        orig_nested = str(
            data["bootstrap_ansible_controller__vaulted_credentials_default"][
                "aap_project_git_deploy_key"
            ]
        )
        orig_top = str(data["cyberark_test_safe_password"])

        scrambled = vs.scramble_vault_file_data(data, skip_exclusions=False)
        buf = io.StringIO()
        y.dump(scrambled, buf)
        rendered = buf.getvalue()

        assert "!vault |" in rendered
        assert rendered.count("$ANSIBLE_VAULT;1.1;AES256") == 2

        new_nested = str(
            scrambled["bootstrap_ansible_controller__vaulted_credentials_default"][
                "aap_project_git_deploy_key"
            ]
        )
        new_top = str(scrambled["cyberark_test_safe_password"])

        assert new_nested.splitlines()[0] == "$ANSIBLE_VAULT;1.1;AES256"
        assert new_top.splitlines()[0] == "$ANSIBLE_VAULT;1.1;AES256"
        assert len(new_nested) == len(orig_nested)
        assert len(new_top) == len(orig_top)
        assert new_nested != orig_nested
        assert new_top != orig_top

        # Verify character categories (digits stay digits, lowercase hex stays lowercase)
        for orig_c, new_c in zip(orig_top, new_top):
            if orig_c.isdigit():
                assert new_c.isdigit()
            elif orig_c.islower():
                assert new_c.islower()


# ---------------------------------------------------------------------------
# Vault Password & Decryption Tests
# ---------------------------------------------------------------------------
class TestVaultDecryption:
    def test_load_vault_password_explicit_file(self, tmp_path: Path) -> None:
        pw_file = tmp_path / "vault_pass.txt"
        pw_file.write_text("  super_secret_pass\n")
        assert vs.load_vault_password(str(pw_file)) == b"super_secret_pass"

    def test_load_vault_password_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pw_file = tmp_path / "env_vault_pass.txt"
        pw_file.write_text("env_secret\n")
        monkeypatch.setenv("ANSIBLE_VAULT_PASSWORD_FILE", str(pw_file))
        monkeypatch.setattr(
            Path,
            "expanduser",
            lambda self: tmp_path / "nonexistent" if "~" in str(self) else self,
        )
        assert vs.load_vault_password(None) == b"env_secret"

    def test_decrypt_with_cli_success(self, tmp_path: Path) -> None:
        vault_file = tmp_path / "vault.yml"
        vault_file.write_text("$ANSIBLE_VAULT;1.1;AES256\n0000")
        mock_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="---\nvault__test: ok\n", stderr=""
        )
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            out = vs.decrypt_with_cli(vault_file, "/tmp/passfile")
        assert out == "---\nvault__test: ok\n"
        mock_run.assert_called_once_with(
            [
                "ansible-vault",
                "view",
                str(vault_file),
                "--vault-password-file",
                "/tmp/passfile",
            ],
            capture_output=True,
            text=True,
        )

    def test_decrypt_with_cli_failure_raises(self, tmp_path: Path) -> None:
        vault_file = tmp_path / "vault.yml"
        vault_file.write_text("$ANSIBLE_VAULT;1.1;AES256\n0000")
        mock_proc = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Decryption failed"
        )
        with patch("subprocess.run", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="Decryption failed"):
                vs.decrypt_with_cli(vault_file, None)


# ---------------------------------------------------------------------------
# CLI / main() End-to-End Tests
# ---------------------------------------------------------------------------
class TestCLI:
    def test_cli_plaintext_end_to_end(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        input_file = tmp_path / "vault.example.yml"
        input_file.write_text(
            "---\n"
            'vault__custom_domain: "host.dettonville.int"\n'
            'vault__openbao_secret: "should_be_dropped"\n'
        )
        monkeypatch.setattr(
            sys,
            "argv",
            ["vault_scrambler.py", "--seed", "42", "--plaintext", str(input_file)],
        )
        vs.main()

        captured = capsys.readouterr()
        assert "vault__custom_domain:" in captured.out
        assert "example.int" in captured.out
        assert "vault__openbao_secret" not in captured.out

    def test_cli_scramble_vault_end_to_end(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        input_file = tmp_path / "vault_encrypted_vars.yml"
        input_file.write_text(
            "---\n"
            "my_secret: !vault |\n"
            "  $ANSIBLE_VAULT;1.1;AES256\n"
            "  30353964323139343730353362613239\n"
        )
        monkeypatch.setattr(
            sys,
            "argv",
            ["vault_scrambler.py", "--seed", "42", "--scramble-vault", str(input_file)],
        )
        vs.main()

        captured = capsys.readouterr()
        assert "my_secret: !vault |" in captured.out
        assert "$ANSIBLE_VAULT;1.1;AES256" in captured.out
        assert "30353964323139343730353362613239" not in captured.out
        assert re.search(r"^\s+[0-9a-f]{32}$", captured.out, re.MULTILINE)

    def test_cli_missing_file_exits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing = tmp_path / "does_not_exist.yml"
        monkeypatch.setattr(sys, "argv", ["vault_scrambler.py", str(missing)])
        with pytest.raises(SystemExit) as exc:
            vs.main()
        assert exc.value.code == 1

    def test_cli_empty_yaml_exits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        empty_file = tmp_path / "empty.yml"
        empty_file.write_text("---\n")
        monkeypatch.setattr(
            sys, "argv", ["vault_scrambler.py", "--plaintext", str(empty_file)]
        )
        with pytest.raises(SystemExit) as exc:
            vs.main()
        assert exc.value.code == 1
