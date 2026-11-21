#!/usr/bin/env python3
"""Unit tests for vault_organizer.py."""

from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

# ---------------------------------------------------------------------------
# Dynamic module import (works regardless of filename/path)
# ---------------------------------------------------------------------------
_CANDIDATE_PATHS = [
    Path(__file__).resolve().parents[2] / "vault_organizer.py",
    Path(__file__).resolve().parent / "vault_organizer.py",
    Path(__file__).resolve().parent / "vault_organizer_2.py",
]
MODULE_PATH = next((p for p in _CANDIDATE_PATHS if p.is_file()), _CANDIDATE_PATHS[0])

spec = importlib.util.spec_from_file_location("vault_organizer", MODULE_PATH)
assert spec and spec.loader
vo = importlib.util.module_from_spec(spec)
sys.modules["vault_organizer"] = vo
spec.loader.exec_module(vo)


def _make_yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 120
    y.indent(mapping=2, sequence=4, offset=2)
    y.explicit_start = True
    y.constructor.add_constructor(
        "!vault", lambda l, n: vo.VaultString(l.construct_scalar(n))
    )
    y.representer.add_representer(
        vo.VaultString, lambda r, d: r.represent_scalar("!vault", d, style="|")
    )
    return y


def _roundtrip(raw_yaml: str) -> tuple[CommentedMap, str]:
    y = _make_yaml()
    data = y.load(raw_yaml)
    organized = vo.sort_vault_keys_with_dependencies(data)
    buf = io.StringIO()
    y.dump(organized, buf)
    return organized, buf.getvalue()


# ---------------------------------------------------------------------------
# Group Extraction & Helper Tests
# ---------------------------------------------------------------------------
class TestHelpers:
    @pytest.mark.parametrize(
        ("key", "expected_group"),
        [
            ("vault__ansible_ssh_password", "ansible"),
            ("vault__authelia_jwt_secret", "authelia"),
            ("vault__gitea__tokens", "gitea"),
            ("vault__ldap_domain_user_map", "ldap"),
            ("vault__APP_admin_password", "app"),
            ("vault__singleword", "vault__singleword"),
            ("non_vault_key", "non_vault_key"),
        ],
    )
    def test_get_vault_group(self, key: str, expected_group: str) -> None:
        assert vo.get_vault_group(key) == expected_group

    def test_extract_text_content_nested(self) -> None:
        nested = {
            "level1": [
                "item1",
                {"vault__inner_key": "{{ vault__other_var }}"},
                123,
            ]
        }
        extracted = vo.extract_text_content(nested)
        assert "level1" in extracted
        assert "item1" in extracted
        assert "vault__inner_key" in extracted
        assert "{{ vault__other_var }}" in extracted
        assert "123" in extracted


# ---------------------------------------------------------------------------
# Sorting, Grouping & Dependency Resolution Tests
# ---------------------------------------------------------------------------
class TestSortingAndDependencies:
    def test_alphanumeric_grouping_without_dependencies(self) -> None:
        raw = """---
vault__zoho_api_key: "z1"
vault__authelia_jwt_secret: "a2"
vault__ansible_vault_password: "a1"
vault__authelia_encryption_key: "a3"
vault__ansible_galaxy_token: "a0"
other_var: "plain"
"""
        organized, _ = _roundtrip(raw)
        assert list(organized.keys()) == [
            "vault__ansible_galaxy_token",
            "vault__ansible_vault_password",
            "vault__authelia_encryption_key",
            "vault__authelia_jwt_secret",
            "vault__zoho_api_key",
            "other_var",
        ]

    def test_cross_group_dependency_ordering(self) -> None:
        """Group referencing another group must appear after its prerequisite group."""
        raw = """---
vault__authelia_password_raw: "{{ vault__app_admin_password }}"
vault__authelia_jwt_secret: "secret"
vault__app_admin_password: "base_password"
vault__ansible_ssh_password: "ssh_password"
"""
        organized, _ = _roundtrip(raw)
        keys = list(organized.keys())
        # 'ansible' has no deps -> first
        # 'app' has no deps -> second (prerequisite for 'authelia')
        # 'authelia' depends on 'app' -> third
        assert keys == [
            "vault__ansible_ssh_password",
            "vault__app_admin_password",
            "vault__authelia_jwt_secret",
            "vault__authelia_password_raw",
        ]

    def test_intra_group_dependency_ordering(self) -> None:
        """Within a group, derived variables must follow the variables they reference."""
        raw = """---
vault__vllm_api_url: "{{ vault__vllm_api[vault__vllm_default_host]['url'] }}"
vault__vllm_default_host: "gpu01"
vault__vllm_api:
  gpu01:
    url: "https://vllm.example.int"
"""
        organized, _ = _roundtrip(raw)
        keys = list(organized.keys())
        assert keys.index("vault__vllm_api") < keys.index("vault__vllm_api_url")
        assert keys.index("vault__vllm_default_host") < keys.index("vault__vllm_api_url")

    def test_nested_dict_and_list_dependency_detection(self) -> None:
        """References inside nested lists/dicts should trigger cross-group ordering."""
        raw = """---
vault__registry_users: "{{ vault__http_auth_user_list }}"
vault__http_auth_user_list:
  - username: "admin"
    password: "{{ vault__admin_password }}"
vault__admin_password: "secret"
"""
        organized, _ = _roundtrip(raw)
        keys = list(organized.keys())
        assert keys == [
            "vault__admin_password",
            "vault__http_auth_user_list",
            "vault__registry_users",
        ]

    def test_cycle_breaking_does_not_stall_unrelated_groups(self, caplog: pytest.LogCaptureFixture) -> None:
        """Mutual references between two groups should break cleanly without
        blocking unrelated downstream or independent groups.
        """
        raw = """---
vault__user_passwd_hash_seed: "seed123"
vault__user_credentials:
  root:
    hashed_password: "{{ vault__admin_password_sha512 }}"
vault__admin_password: "secret"
vault__admin_password_sha512: "{{ vault__admin_password | password_hash('sha512', vault__user_passwd_hash_seed) }}"
vault__zoho_token: "zoho_secret"
vault__ansible_token: "ansible_secret"
"""
        with caplog.at_level("WARNING"):
            organized, _ = _roundtrip(raw)

        keys = list(organized.keys())
        # Independent 'ansible' comes first, 'zoho' comes last, and all keys are present
        assert keys[0] == "vault__ansible_token"
        assert "vault__zoho_token" in keys
        assert set(keys) == {
            "vault__ansible_token",
            "vault__admin_password",
            "vault__admin_password_sha512",
            "vault__user_credentials",
            "vault__user_passwd_hash_seed",
            "vault__zoho_token",
        }
        assert any("dependency cycle" in rec.message for rec in caplog.records)

    def test_non_commented_map_returns_unchanged(self) -> None:
        plain_dict = {"b": 1, "a": 2}
        result = vo.sort_vault_keys_with_dependencies(plain_dict)  # type: ignore[arg-type]
        assert result is plain_dict


# ---------------------------------------------------------------------------
# Comment, Quote & !vault Tag Preservation Tests
# ---------------------------------------------------------------------------
class TestFormattingAndComments:
    def test_preserves_quotes_and_vault_tags(self) -> None:
        raw = """---
vault__z_plain: unquoted_value
vault__b_single: 'single_quoted'
vault__a_double: "double_quoted"
vault__m_encrypted: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  31323334
"""
        _, rendered = _roundtrip(raw)
        assert 'vault__a_double: "double_quoted"' in rendered
        assert "vault__b_single: 'single_quoted'" in rendered
        assert "vault__m_encrypted: !vault |" in rendered
        assert "vault__z_plain: unquoted_value" in rendered

    def test_preserves_comments_when_reordering(self) -> None:
        raw = """---
# Top header comment
vault__z_var: "last"

# Middle comment
vault__a_var: "first"
"""
        _, rendered = _roundtrip(raw)
        assert "# Top header comment" in rendered
        assert "# Middle comment" in rendered
        assert rendered.index("vault__a_var") < rendered.index("vault__z_var")


# ---------------------------------------------------------------------------
# Vault Password & Decryption Tests
# ---------------------------------------------------------------------------
class TestVaultDecryption:
    def test_load_vault_password_explicit_file(self, tmp_path: Path) -> None:
        pw_file = tmp_path / "vault_pass.txt"
        pw_file.write_text("  super_secret_pass\n")
        assert vo.load_vault_password(str(pw_file)) == b"super_secret_pass"

    def test_load_vault_password_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pw_file = tmp_path / "env_vault_pass.txt"
        pw_file.write_text("env_secret\n")
        monkeypatch.setenv("ANSIBLE_VAULT_PASSWORD_FILE", str(pw_file))
        # Ensure ~/.vault_pass doesn't interfere if it exists
        monkeypatch.setattr(Path, "expanduser", lambda self: tmp_path / "nonexistent" if "~" in str(self) else self)
        assert vo.load_vault_password(None) == b"env_secret"

    def test_decrypt_with_cli_success(self, tmp_path: Path) -> None:
        vault_file = tmp_path / "vault.yml"
        vault_file.write_text("$ANSIBLE_VAULT;1.1;AES256\n0000")
        mock_proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="---\nvault__test: ok\n", stderr=""
        )
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            out = vo.decrypt_with_cli(vault_file, "/tmp/passfile")
        assert out == "---\nvault__test: ok\n"
        mock_run.assert_called_once_with(
            ["ansible-vault", "view", str(vault_file), "--vault-password-file", "/tmp/passfile"],
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
                vo.decrypt_with_cli(vault_file, None)


# ---------------------------------------------------------------------------
# CLI / main() End-to-End Tests
# ---------------------------------------------------------------------------
class TestCLI:
    def test_cli_plaintext_end_to_end(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        input_file = tmp_path / "vault.example.yml"
        input_file.write_text(
            "---\n"
            'vault__authelia_secret: "{{ vault__app_secret }}"\n'
            'vault__app_secret: "12345"\n'
            'vault__ansible_user: "admin"\n'
        )
        monkeypatch.setattr(sys, "argv", ["vault_organizer.py", "--plaintext", str(input_file)])
        vo.main()

        captured = capsys.readouterr()
        lines = [ln for ln in captured.out.splitlines() if ln.startswith("vault__")]
        assert lines == [
            'vault__ansible_user: "admin"',
            'vault__app_secret: "12345"',
            'vault__authelia_secret: "{{ vault__app_secret }}"',
        ]

    def test_cli_missing_file_exits(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        missing = tmp_path / "does_not_exist.yml"
        monkeypatch.setattr(sys, "argv", ["vault_organizer.py", str(missing)])
        with pytest.raises(SystemExit) as exc:
            vo.main()
        assert exc.value.code == 1

    def test_cli_empty_yaml_exits(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        empty_file = tmp_path / "empty.yml"
        empty_file.write_text("---\n")
        monkeypatch.setattr(sys, "argv", ["vault_organizer.py", "--plaintext", str(empty_file)])
        with pytest.raises(SystemExit) as exc:
            vo.main()
        assert exc.value.code == 1

    def test_cli_non_mapping_root_exits(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        list_file = tmp_path / "list.yml"
        list_file.write_text("---\n- item1\n- item2\n")
        monkeypatch.setattr(sys, "argv", ["vault_organizer.py", "--plaintext", str(list_file)])
        with pytest.raises(SystemExit) as exc:
            vo.main()
        assert exc.value.code == 1
