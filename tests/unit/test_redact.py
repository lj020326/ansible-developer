import yaml

from redact_key_values import (
    DEFAULT_REDACT_KEYS,
    process_env_ini,
    process_yaml,
)

# ---------------------------------------------------------------------------
# Test Data Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ENV_INI = """# Environment configuration
DB_HOST=localhost
DB_PORT=5432
API_KEY=sk-proj-1234567890abcdef
USER_PASSWORD=SuperSecretPass123! # inline comment
APP_SECRET="top_secret_token_val"
SESSION_TIMEOUT=3600
"""

SAMPLE_YAML = """
app:
  name: my-service
  environment: production
database:
  host: db.local
  port: 5432
  user_password: SuperSecretPass123!
auth:
  api_key: sk-proj-1234567890abcdef
  refresh_token: "refresh_987654321_xyz"
  settings:
    secret_key: "nested_secret_val"
"""

# ---------------------------------------------------------------------------
# 1. Tests for INI / Shell Variable Assignments
# ---------------------------------------------------------------------------


class TestEnvIniProcessing:
    def test_default_redaction(self):
        """Tests standard substring and case-insensitive redaction on INI/Shell files."""
        result = process_env_ini(
            content=SAMPLE_ENV_INI,
            keys=DEFAULT_REDACT_KEYS,
            exact_match=False,
            case_sensitive=False,
            peek_count=0,
        )

        assert "DB_HOST=localhost" in result
        assert "DB_PORT=5432" in result
        assert "SESSION_TIMEOUT=3600" in result

        # Sensitive keys should be masked
        assert "API_KEY=<redacted>" in result
        # Note: Match exact inline comment string output from regex processing
        assert "USER_PASSWORD=<redacted> # inline comment" in result
        assert 'APP_SECRET="<redacted>"' in result

        # Secrets should not leak
        assert "sk-proj-1234567890abcdef" not in result
        assert "SuperSecretPass123!" not in result

    def test_exact_match_only(self):
        """Tests that exact_match=True prevents partial key matches (e.g., API_KEY vs KEY)."""
        result = process_env_ini(
            content=SAMPLE_ENV_INI,
            keys=["key"],  # Only search for exact "key"
            exact_match=True,
            case_sensitive=False,
            peek_count=0,
        )

        # API_KEY should NOT be redacted because exact_match is True
        assert "API_KEY=sk-proj-1234567890abcdef" in result

    def test_case_sensitivity(self):
        """Tests that case_sensitive=True ignores keys with mismatched casing."""
        result = process_env_ini(
            content="api_key=secret123\nAPI_KEY=secret456",
            keys=["api_key"],
            exact_match=True,
            case_sensitive=True,
            peek_count=0,
        )

        assert "api_key=<redacted>" in result
        assert "API_KEY=secret456" in result

    def test_peek_feature(self):
        """Tests the -p/--peek character preservation feature on INI files."""
        result = process_env_ini(
            content="API_KEY=sk-proj-1234567890abcdef",
            keys=DEFAULT_REDACT_KEYS,
            exact_match=False,
            case_sensitive=False,
            peek_count=3,
        )

        # First 3 chars ('sk-') and last 3 chars ('def') should be visible
        assert "API_KEY=sk-...<redacted>...def" in result


# ---------------------------------------------------------------------------
# 2. Tests for YAML Content
# ---------------------------------------------------------------------------


class TestYamlProcessing:
    def test_yaml_tree_redaction(self):
        """Tests deep dictionary traversal and key redaction in structured YAML."""
        result = process_yaml(
            content=SAMPLE_YAML,
            keys=DEFAULT_REDACT_KEYS,
            exact_match=False,
            case_sensitive=False,
            peek_count=0,
        )

        parsed = yaml.safe_load(result)

        # Non-sensitive keys remain intact
        assert parsed["app"]["name"] == "my-service"
        assert parsed["database"]["port"] == 5432

        # Nested and substring matched sensitive keys are redacted
        assert parsed["database"]["user_password"] == "<redacted>"
        assert parsed["auth"]["api_key"] == "<redacted>"
        assert parsed["auth"]["refresh_token"] == "<redacted>"
        assert parsed["auth"]["settings"]["secret_key"] == "<redacted>"

    def test_yaml_peek_feature(self):
        """Tests peeking behavior inside nested YAML structures."""
        result = process_yaml(
            content=SAMPLE_YAML,
            keys=DEFAULT_REDACT_KEYS,
            exact_match=False,
            case_sensitive=False,
            peek_count=4,
        )

        parsed = yaml.safe_load(result)

        # api_key: "sk-proj-1234567890abcdef" -> "sk-p...<redacted>...cdef"
        assert parsed["auth"]["api_key"] == "sk-p...<redacted>...cdef"

    def test_yaml_short_value_peek_fallback(self):
        """Tests that peeking gracefully defaults to full redaction if string is too short."""
        short_secret_yaml = "secret_val: 123"
        result = process_yaml(
            content=short_secret_yaml,
            keys=DEFAULT_REDACT_KEYS,
            exact_match=False,
            case_sensitive=False,
            peek_count=5,  # 5 prefix + 5 suffix > total length of 3
        )

        parsed = yaml.safe_load(result)
        # Should fully redact instead of producing corrupted/overlapping peek strings
        assert parsed["secret_val"] == "<redacted>"

    def test_multiline_ssh_key_redaction(self):
        """Tests redaction of multiline SSH key assignments in shell scripts."""
        multiline_env = """export TEST_REPO_GIT_SSH_PRIVATE_KEY='-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEABBBBBG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZWQyNTUx
OQAAACDFkH0UgaOEEEEEEEEFGs7vwkYcHxTzAi5fYtGS7pSNKQAAAIgJYeXhCWHl4QAAAAtzc2gt
ZWQyNTUxOQAAACDFkH0UgaOOVJXslhgFGs7vwkYcHxTzAi5fYtGS7pSNKQAAAEAw9yjQ4RpRmeBG
Hqb+l69tDDDDDDDDJ7NV4thd/A0C5cWQfRSBo45UleyWGAUazu/CRhwfFPMCLl9i0ZLulI0pAAAA
AAECAwQF
-----END OPENSSH PRIVATE KEY-----'
OTHER_VAR=keep_me
"""
        result = process_env_ini(
            content=multiline_env,
            keys=DEFAULT_REDACT_KEYS,
            exact_match=False,
            case_sensitive=False,
            peek_count=15,
        )

        assert "OTHER_VAR=keep_me" in result
        # Adjusted suffix assertion to match 'RIVATE KEY-----'
        assert (
            "export TEST_REPO_GIT_SSH_PRIVATE_KEY='-----BEGIN OPEN...<redacted>...RIVATE KEY-----'"
            in result
        )
        assert "b3BlbnNzaC1rZXktdjEABBBBBG5vbm" not in result

    def test_semicolon_delimited_list_redaction(self):
        """Tests that semicolon-delimited lists mask each entry individually."""
        env_content = (
            "OPENAI_API_KEY=sk-first-key-12345;abd33949494af9 # inline comment"
        )
        result = process_env_ini(
            content=env_content,
            keys=DEFAULT_REDACT_KEYS,
            exact_match=False,
            case_sensitive=False,
            peek_count=0,
        )

        assert "OPENAI_API_KEY=<redacted>;<redacted> # inline comment" in result
        assert "sk-first-key-12345" not in result
        assert "abd33949494af9" not in result

    def test_semicolon_delimited_list_peek_redaction(self):
        """Tests that semicolon-delimited lists preserve peek characters for each item."""
        env_content = "OPENAI_API_KEY=sk-proj-firstkey123456789;abd33949494af987654321 # inline comment"
        result = process_env_ini(
            content=env_content,
            keys=DEFAULT_REDACT_KEYS,
            exact_match=False,
            case_sensitive=False,
            peek_count=4,
        )

        expected = "OPENAI_API_KEY=sk-p...<redacted>...6789;abd3...<redacted>...4321 # inline comment"
        assert expected in result
        assert "firstkey12345" not in result
        assert "33949494af987" not in result

    def test_empty_value_key_redaction(self):
        """Tests that sensitive keys with empty values do not swallow following lines."""
        env_content = (
            "LLAMA_ARG_PORT=8080\nLLAMA_ARG_API_KEY=\nLLAMA_ARG_MODELS_DIR=/models\n"
        )
        result = process_env_ini(
            content=env_content,
            keys=DEFAULT_REDACT_KEYS,
            exact_match=False,
            case_sensitive=False,
            peek_count=4,
        )

        assert "LLAMA_ARG_PORT=8080" in result
        assert "LLAMA_ARG_API_KEY=\n" in result
        assert "LLAMA_ARG_MODELS_DIR=/models" in result
        assert "<redacted>" not in result

    def test_yaml_empty_value_key_redaction(self):
        """Tests that sensitive keys with empty or null values in YAML do not swallow following keys."""
        yaml_content = (
            "LLAMA_ARG_PORT: 8080\n"
            "LLAMA_ARG_API_KEY:\n"
            "LLAMA_ARG_SECRET_TOKEN: ''\n"
            "LLAMA_ARG_MODELS_DIR: /models\n"
        )
        result = process_yaml(
            content=yaml_content,
            keys=DEFAULT_REDACT_KEYS,
            exact_match=False,
            case_sensitive=False,
            peek_count=4,
        )

        assert "LLAMA_ARG_PORT: 8080" in result or "LLAMA_ARG_PORT: '8080'" in result
        assert "LLAMA_ARG_API_KEY: null" in result or "LLAMA_ARG_API_KEY:" in result
        assert "LLAMA_ARG_SECRET_TOKEN: ''" in result or "LLAMA_ARG_SECRET_TOKEN: null" in result
        assert "LLAMA_ARG_MODELS_DIR: /models" in result
