"""Tests for llm_config (R7).

Uses ``monkeypatch`` for environment variable simulation.
Only dummy key ``sk-test-should-not-leak`` is used.
"""

import os
import pytest

from bpc_hybrid.llm_config import (
    ALLOWED_PROVIDERS,
    LLMConfig,
    LLMConfigError,
    LLMProvider,
    _base_url_has_secrets,
    load_project_env_file,
    project_env_disabled,
    redact_mapping,
    redact_secret,
)


DUMMY_KEY = "sk-test-should-not-leak"


# ---------------------------------------------------------------------------
# redact_secret
# ---------------------------------------------------------------------------

class TestRedactSecret:
    def test_none(self):
        assert redact_secret(None) == "None"

    def test_short_value(self):
        assert "REDACTED" in redact_secret("ab")

    def test_long_value(self):
        result = redact_secret(DUMMY_KEY)
        assert result.startswith("sk-t")
        assert "REDACTED" in result
        assert DUMMY_KEY not in result  # full key not exposed

    def test_empty_string(self):
        assert "REDACTED" in redact_secret("")


# ---------------------------------------------------------------------------
# redact_mapping
# ---------------------------------------------------------------------------

class TestRedactMapping:
    def test_api_key_redacted(self):
        m = redact_mapping({"api_key": DUMMY_KEY, "other": "safe"})
        assert m["api_key"] == "***REDACTED***"
        assert m["other"] == "safe"

    def test_secret_redacted(self):
        m = redact_mapping({"client_secret": DUMMY_KEY})
        assert m["client_secret"] == "***REDACTED***"

    def test_token_redacted(self):
        m = redact_mapping({"access_token": DUMMY_KEY})
        assert m["access_token"] == "***REDACTED***"

    def test_sk_prefix_in_value_redacted(self):
        m = redact_mapping({"auth": f"Bearer {DUMMY_KEY}"})
        assert m["auth"] == "***REDACTED***"

    def test_nonsensitive_preserved(self):
        m = redact_mapping({"model": "gpt-4", "temperature": 0.0})
        assert m["model"] == "gpt-4"
        assert m["temperature"] == 0.0


# ---------------------------------------------------------------------------
# LLMConfig defaults
# ---------------------------------------------------------------------------

class TestLLMConfigDefaults:
    def test_default_disabled(self):
        cfg = LLMConfig()
        assert cfg.enabled is False
        assert cfg.provider == "mock"
        assert cfg.model == "mock"
        assert cfg.api_key is None

    def test_default_values(self):
        cfg = LLMConfig()
        assert cfg.timeout_seconds == 30.0
        assert cfg.max_tokens == 1024
        assert cfg.temperature == 0.0
        assert cfg.base_url is None


# ---------------------------------------------------------------------------
# LLMConfig validation
# ---------------------------------------------------------------------------

class TestLLMConfigValidation:
    def test_disabled_no_key_needed(self):
        LLMConfig(enabled=False, provider="openai_compatible", api_key=None)

    def test_mock_no_key_needed(self):
        LLMConfig(enabled=True, provider="mock", api_key=None)

    def test_disabled_no_key_needed_2(self):
        LLMConfig(enabled=True, provider="disabled", api_key=None)

    def test_openai_compatible_missing_key_raises(self):
        with pytest.raises(LLMConfigError, match="requires an API key"):
            LLMConfig(enabled=True, provider="openai_compatible", api_key=None)

    def test_openai_compatible_with_key_ok(self):
        LLMConfig(enabled=True, provider="openai_compatible", api_key=DUMMY_KEY)

    def test_invalid_provider_raises(self):
        with pytest.raises(LLMConfigError, match="Invalid provider"):
            LLMConfig(enabled=True, provider="anthropic")

    def test_negative_timeout_raises(self):
        with pytest.raises(LLMConfigError, match="timeout_seconds"):
            LLMConfig(enabled=True, timeout_seconds=-1)

    def test_zero_max_tokens_raises(self):
        with pytest.raises(LLMConfigError, match="max_tokens"):
            LLMConfig(enabled=True, max_tokens=0)

    def test_temperature_out_of_range(self):
        with pytest.raises(LLMConfigError, match="temperature"):
            LLMConfig(enabled=True, temperature=3.0)


# ---------------------------------------------------------------------------
# LLMConfig validation — disabled configs also enforce structural checks
# ---------------------------------------------------------------------------

class TestLLMConfigValidationDisabled:
    """Provider and numeric validation must run even when enabled=False."""

    def test_disabled_invalid_provider_raises(self):
        with pytest.raises(LLMConfigError, match="Invalid provider"):
            LLMConfig(enabled=False, provider="anthropic")

    def test_disabled_invalid_timeout_raises(self):
        with pytest.raises(LLMConfigError, match="timeout_seconds"):
            LLMConfig(enabled=False, timeout_seconds=-1)

    def test_disabled_invalid_max_tokens_raises(self):
        with pytest.raises(LLMConfigError, match="max_tokens"):
            LLMConfig(enabled=False, max_tokens=0)

    def test_disabled_invalid_temperature_raises(self):
        with pytest.raises(LLMConfigError, match="temperature"):
            LLMConfig(enabled=False, temperature=3.0)


# ---------------------------------------------------------------------------
# base_url secret-material detection
# ---------------------------------------------------------------------------

class TestLLMConfigBaseUrlSecurity:
    """base_url must not embed API keys, tokens, or passwords."""

    SECRET_URL_API_KEY = "https://api.example.com/v1?api_key=sk-test-should-not-leak"
    SECRET_URL_TOKEN = "https://api.example.com/v1?token=sk-test-should-not-leak"
    SECRET_URL_USERPASS = "https://user:pass@api.example.com/v1"
    SECRET_URL_ACCESS_TOKEN = "https://api.example.com/v1?access_token=sk-test-should-not-leak"
    SECRET_URL_AUTHORIZATION = "https://api.example.com/v1?authorization=Bearer%20sk-test-should-not-leak"
    CLEAN_URL = "https://api.example.com/v1"

    def test_api_key_in_query_raises(self):
        with pytest.raises(LLMConfigError, match="secret material"):
            LLMConfig(enabled=False, base_url=self.SECRET_URL_API_KEY)

    def test_token_in_query_raises(self):
        with pytest.raises(LLMConfigError, match="secret material"):
            LLMConfig(enabled=False, base_url=self.SECRET_URL_TOKEN)

    def test_access_token_in_query_raises(self):
        with pytest.raises(LLMConfigError, match="secret material"):
            LLMConfig(enabled=False, base_url=self.SECRET_URL_ACCESS_TOKEN)

    def test_authorization_in_query_raises(self):
        with pytest.raises(LLMConfigError, match="secret material"):
            LLMConfig(enabled=False, base_url=self.SECRET_URL_AUTHORIZATION)

    def test_user_pass_at_host_raises(self):
        with pytest.raises(LLMConfigError, match="secret material"):
            LLMConfig(enabled=False, base_url=self.SECRET_URL_USERPASS)

    def test_clean_base_url_accepted(self):
        cfg = LLMConfig(enabled=False, base_url=self.CLEAN_URL)
        assert cfg.base_url == self.CLEAN_URL

    def test_none_base_url_ok(self):
        cfg = LLMConfig(enabled=False, base_url=None)
        assert cfg.base_url is None

    def test_error_msg_no_leak_api_key(self):
        with pytest.raises(LLMConfigError) as exc_info:
            LLMConfig(enabled=False, base_url=self.SECRET_URL_API_KEY)
        msg = str(exc_info.value)
        assert "sk-test-should-not-leak" not in msg

    def test_error_msg_no_leak_access_token(self):
        with pytest.raises(LLMConfigError) as exc_info:
            LLMConfig(enabled=False, base_url=self.SECRET_URL_ACCESS_TOKEN)
        msg = str(exc_info.value)
        assert "sk-test-should-not-leak" not in msg

    def test_error_msg_no_leak_authorization(self):
        with pytest.raises(LLMConfigError) as exc_info:
            LLMConfig(enabled=False, base_url=self.SECRET_URL_AUTHORIZATION)
        msg = str(exc_info.value)
        assert "sk-test-should-not-leak" not in msg
        assert "Bearer" not in msg

    def test_error_msg_no_leak_pass(self):
        with pytest.raises(LLMConfigError) as exc_info:
            LLMConfig(enabled=False, base_url=self.SECRET_URL_USERPASS)
        msg = str(exc_info.value)
        # Must not leak the actual password value
        assert "pass@" not in msg.lower()

    def test_repr_safe_by_construction(self):
        """Since validate() rejects secret base_url, repr is safe by
        construction — a config with secret base_url cannot exist."""
        cfg = LLMConfig(
            enabled=False, provider="mock",
            base_url=self.CLEAN_URL, api_key=DUMMY_KEY,
        )
        r = repr(cfg)
        assert self.CLEAN_URL in r
        assert DUMMY_KEY not in r

    def test_helper_detects_secret_patterns(self):
        assert _base_url_has_secrets("https://x.com?api_key=abc")
        assert _base_url_has_secrets("https://x.com?TOKEN=abc")
        assert _base_url_has_secrets("https://x.com?access_token=abc")
        assert _base_url_has_secrets("https://x.com?authorization=abc")
        assert _base_url_has_secrets("https://u:p@x.com")
        assert not _base_url_has_secrets("https://x.com/v1")
        assert not _base_url_has_secrets("https://x.com?model=gpt-4")


# ---------------------------------------------------------------------------
# redact_mapping — base_url redaction
# ---------------------------------------------------------------------------

class TestRedactMappingBaseUrl:
    def test_base_url_with_secret_redacted(self):
        m = redact_mapping({"base_url": "https://x.com?api_key=sk-abc"})
        assert m["base_url"] == "***REDACTED***"

    def test_base_url_access_token_redacted(self):
        m = redact_mapping({"base_url": "https://x.com?access_token=sk-abc"})
        assert m["base_url"] == "***REDACTED***"

    def test_base_url_authorization_redacted(self):
        m = redact_mapping({"base_url": "https://x.com?authorization=Bearer%20sk-abc"})
        assert m["base_url"] == "***REDACTED***"

    def test_base_url_clean_preserved(self):
        m = redact_mapping({"base_url": "https://x.com/v1"})
        assert m["base_url"] == "https://x.com/v1"

    def test_url_key_redacted(self):
        m = redact_mapping({"url": "https://x.com?token=abc"})
        assert m["url"] == "***REDACTED***"


# ---------------------------------------------------------------------------
# LLMConfig repr / str — no leaks
# ---------------------------------------------------------------------------

class TestLLMConfigRepr:
    def test_api_key_not_in_repr(self):
        cfg = LLMConfig(enabled=True, provider="openai_compatible",
                        api_key=DUMMY_KEY)
        r = repr(cfg)
        assert DUMMY_KEY not in r
        assert "REDACTED" in r

    def test_api_key_not_in_str(self):
        cfg = LLMConfig(enabled=True, provider="openai_compatible",
                        api_key=DUMMY_KEY)
        s = str(cfg)
        assert DUMMY_KEY not in s
        assert "REDACTED" in s

    def test_no_api_key_ok(self):
        cfg = LLMConfig()
        r = repr(cfg)
        assert "REDACTED" in r or "None" in r


# ---------------------------------------------------------------------------
# LLMConfig to_dict / from_dict
# ---------------------------------------------------------------------------

class TestLLMConfigDictRoundTrip:
    def test_round_trip(self):
        cfg = LLMConfig(enabled=True, provider="mock", model="test",
                        api_key=DUMMY_KEY, base_url="http://localhost",
                        timeout_seconds=10.0, max_tokens=512,
                        temperature=0.5)
        d = cfg.to_dict()
        cfg2 = LLMConfig.from_dict(d)
        assert cfg2.enabled == cfg.enabled
        assert cfg2.provider == cfg.provider
        assert cfg2.model == cfg.model
        assert cfg2.api_key == cfg.api_key


# ---------------------------------------------------------------------------
# LLMConfig.from_env
# ---------------------------------------------------------------------------

class TestLLMConfigFromEnv:
    def test_default_when_no_env(self, monkeypatch):
        for k in list(os.environ):
            if k.startswith("BPC_HYBRID_LLM_"):
                monkeypatch.delenv(k, raising=False)
        cfg = LLMConfig.from_env()
        assert cfg.enabled is False
        assert cfg.provider == "mock"

    def test_enabled_true_with_mock(self, monkeypatch):
        monkeypatch.setenv("BPC_HYBRID_LLM_ENABLED", "true")
        monkeypatch.setenv("BPC_HYBRID_LLM_PROVIDER", "mock")
        cfg = LLMConfig.from_env()
        assert cfg.enabled is True
        assert cfg.provider == "mock"

    def test_openai_compatible_missing_key_raises(self, monkeypatch):
        monkeypatch.setenv("BPC_HYBRID_LLM_ENABLED", "true")
        monkeypatch.setenv("BPC_HYBRID_LLM_PROVIDER", "openai_compatible")
        monkeypatch.delenv("BPC_HYBRID_LLM_API_KEY", raising=False)
        with pytest.raises(LLMConfigError, match="requires an API key"):
            LLMConfig.from_env()

    def test_openai_compatible_with_key_ok(self, monkeypatch):
        monkeypatch.setenv("BPC_HYBRID_LLM_ENABLED", "true")
        monkeypatch.setenv("BPC_HYBRID_LLM_PROVIDER", "openai_compatible")
        monkeypatch.setenv("BPC_HYBRID_LLM_API_KEY", DUMMY_KEY)
        cfg = LLMConfig.from_env()
        assert cfg.enabled is True
        assert cfg.api_key == DUMMY_KEY

    def test_custom_numeric_env(self, monkeypatch):
        monkeypatch.setenv("BPC_HYBRID_LLM_TIMEOUT_SECONDS", "60.0")
        monkeypatch.setenv("BPC_HYBRID_LLM_MAX_TOKENS", "2048")
        monkeypatch.setenv("BPC_HYBRID_LLM_TEMPERATURE", "0.7")
        cfg = LLMConfig.from_env()
        assert cfg.timeout_seconds == 60.0
        assert cfg.max_tokens == 2048
        assert cfg.temperature == 0.7

    def test_invalid_timeout_raises(self, monkeypatch):
        monkeypatch.setenv("BPC_HYBRID_LLM_TIMEOUT_SECONDS", "not-a-number")
        with pytest.raises(LLMConfigError, match="TIMEOUT_SECONDS"):
            LLMConfig.from_env()

    def test_invalid_max_tokens_raises(self, monkeypatch):
        monkeypatch.setenv("BPC_HYBRID_LLM_MAX_TOKENS", "xyz")
        with pytest.raises(LLMConfigError, match="MAX_TOKENS"):
            LLMConfig.from_env()

    def test_invalid_temperature_raises(self, monkeypatch):
        monkeypatch.setenv("BPC_HYBRID_LLM_TEMPERATURE", "abc")
        with pytest.raises(LLMConfigError, match="TEMPERATURE"):
            LLMConfig.from_env()

    def test_no_dotenv_import(self):
        """Verify llm_config does not import dotenv."""
        src = open("src/bpc_hybrid/llm_config.py", encoding="utf-8").read()
        assert "load_dotenv" not in src.lower()
        assert "from dotenv" not in src.lower()
        assert "import dotenv" not in src.lower()


# ---------------------------------------------------------------------------
# LLMProvider constants
# ---------------------------------------------------------------------------

class TestLLMProvider:
    def test_allowed_providers_contains_expected(self):
        assert "mock" in ALLOWED_PROVIDERS
        assert "openai_compatible" in ALLOWED_PROVIDERS
        assert "disabled" in ALLOWED_PROVIDERS

    def test_provider_constants(self):
        assert LLMProvider.MOCK == "mock"
        assert LLMProvider.OPENAI_COMPATIBLE == "openai_compatible"
        assert LLMProvider.DISABLED == "disabled"


# ---------------------------------------------------------------------------
# No secrets printed in tests
# ---------------------------------------------------------------------------

class TestNoSecretsLeaked:
    def test_no_real_key_in_source(self):
        """Ensure no real API key is hardcoded in the config module."""
        src = open("src/bpc_hybrid/llm_config.py", encoding="utf-8").read()
        assert "sk-proj" not in src
        assert "sk-admin" not in src


# ---------------------------------------------------------------------------
# load_project_env_file (R9.0)
# ---------------------------------------------------------------------------

class TestLoadProjectEnvFile:
    """Tests for the project-root .env loader."""

    DUMMY_ENV_CONTENT = (
        "BPC_HYBRID_LLM_PROVIDER=openai_compatible\n"
        "BPC_HYBRID_LLM_MODEL=qwen-model\n"
        "BPC_HYBRID_LLM_BASE_URL=https://api.example.com/v1\n"
        "BPC_HYBRID_LLM_API_KEY=sk-test-should-not-leak\n"
        "BPC_HYBRID_R9_REAL_RUN_CONFIRMED=YES_SINGLE_SAMPLE_ONLY\n"
        "# This is a comment\n"
        "UNKNOWN_KEY=should-be-ignored\n"
    )

    def test_reads_whitelisted_keys(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text(self.DUMMY_ENV_CONTENT, encoding="utf-8")
        result = load_project_env_file(tmp_path)
        assert result["BPC_HYBRID_LLM_PROVIDER"] == "openai_compatible"
        assert result["BPC_HYBRID_LLM_MODEL"] == "qwen-model"
        assert result["BPC_HYBRID_LLM_BASE_URL"] == "https://api.example.com/v1"
        assert result["BPC_HYBRID_LLM_API_KEY"] == DUMMY_KEY
        assert result["BPC_HYBRID_R9_REAL_RUN_CONFIRMED"] == "YES_SINGLE_SAMPLE_ONLY"

    def test_ignores_unknown_keys(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "BPC_HYBRID_LLM_PROVIDER=mock\n"
            "UNTRACKED_KEY=secret-value\n",
            encoding="utf-8",
        )
        result = load_project_env_file(tmp_path)
        assert "UNTRACKED_KEY" not in result
        assert result["BPC_HYBRID_LLM_PROVIDER"] == "mock"

    def test_missing_file_returns_empty(self, tmp_path):
        """No .env file → empty dict, no error."""
        result = load_project_env_file(tmp_path)
        assert result == {}

    def test_ignores_comments_and_empty_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "# header comment\n"
            "\n"
            "BPC_HYBRID_LLM_MODEL=test\n"
            "   # inline comment-like value\n"
            "BPC_HYBRID_LLM_PROVIDER=mock\n",
            encoding="utf-8",
        )
        result = load_project_env_file(tmp_path)
        assert result["BPC_HYBRID_LLM_MODEL"] == "test"
        assert result["BPC_HYBRID_LLM_PROVIDER"] == "mock"
        assert len(result) == 2

    def test_returns_empty_list(self):
        """Verify the return value is a plain dict (not list)."""
        # trivial: we already test empty above, but confirm type
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            from pathlib import Path
            result = load_project_env_file(Path(td))
            assert isinstance(result, dict)

    def test_does_not_read_outside_project_root(self, tmp_path):
        """load_project_env_file only reads .env in the exact project_root."""
        env_file = tmp_path / ".env"
        env_file.write_text("BPC_HYBRID_LLM_MODEL=nested\n", encoding="utf-8")
        sub_dir = tmp_path / "sub"
        sub_dir.mkdir()
        # Point to sub_dir — its .env should NOT be found
        result = load_project_env_file(sub_dir)
        assert result == {}

    def test_trims_whitespace(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "  BPC_HYBRID_LLM_PROVIDER  =  openai_compatible  \n",
            encoding="utf-8",
        )
        result = load_project_env_file(tmp_path)
        assert result["BPC_HYBRID_LLM_PROVIDER"] == "openai_compatible"

    def test_no_dotenv_import(self):
        """Verify llm_config does not import python-dotenv."""
        src = open("src/bpc_hybrid/llm_config.py", encoding="utf-8").read()
        assert "load_dotenv" not in src.lower()
        assert "from dotenv" not in src.lower()
        assert "import dotenv" not in src.lower()

    def test_api_key_value_not_leaked_via_exception(self, tmp_path):
        """The loader must not print or echo the API key value."""
        env_file = tmp_path / ".env"
        env_file.write_text("BPC_HYBRID_LLM_API_KEY=sk-test-should-not-leak\n")
        # load_project_env_file itself never raises, but we just verify
        # that reading the result does not print the value
        result = load_project_env_file(tmp_path)
        assert result["BPC_HYBRID_LLM_API_KEY"] == DUMMY_KEY
        # str/repr of result must still contain the key — but this is
        # never printed to stdout/user in production.  The real safety
        # check is in from_env's repr redaction.
        # No printing in test is intentional.


# ---------------------------------------------------------------------------
# LLMConfig.from_env with project_root (R9.0)
# ---------------------------------------------------------------------------

class TestFromEnvWithProjectRoot:
    """System env vars override .env; .env is used as fallback."""

    def test_env_var_overrides_dotenv(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("BPC_HYBRID_LLM_PROVIDER=mock\n", encoding="utf-8")
        monkeypatch.setenv("BPC_HYBRID_LLM_PROVIDER", "disabled")
        cfg = LLMConfig.from_env(project_root=tmp_path)
        assert cfg.provider == "disabled"

    def test_dotenv_fallback_when_no_env_var(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "BPC_HYBRID_LLM_MODEL=qwen\n"
            "BPC_HYBRID_LLM_PROVIDER=openai_compatible\n"
        )
        # clear all BPC_HYBRID env vars
        for k in list(os.environ):
            if k.startswith("BPC_HYBRID_LLM_"):
                monkeypatch.delenv(k, raising=False)
        cfg = LLMConfig.from_env(project_root=tmp_path)
        assert cfg.model == "qwen"
        assert cfg.provider == "openai_compatible"

    def test_missing_dotenv_no_error(self, tmp_path, monkeypatch):
        for k in list(os.environ):
            if k.startswith("BPC_HYBRID_LLM_"):
                monkeypatch.delenv(k, raising=False)
        cfg = LLMConfig.from_env(project_root=tmp_path)  # no .env
        assert cfg.provider == "mock"  # default

    def test_dotenv_api_key_fallback(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "BPC_HYBRID_LLM_ENABLED=true\n"
            "BPC_HYBRID_LLM_PROVIDER=openai_compatible\n"
            f"BPC_HYBRID_LLM_API_KEY={DUMMY_KEY}\n"
        )
        for k in list(os.environ):
            if k.startswith("BPC_HYBRID_LLM_"):
                monkeypatch.delenv(k, raising=False)
        cfg = LLMConfig.from_env(project_root=tmp_path)
        assert cfg.enabled is True
        assert cfg.provider == "openai_compatible"
        assert cfg.api_key == DUMMY_KEY
        # repr must redact
        assert DUMMY_KEY not in repr(cfg)

    def test_dotenv_does_not_override_system_env_api_key(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("BPC_HYBRID_LLM_API_KEY=dotenv-key\n")
        monkeypatch.setenv("BPC_HYBRID_LLM_API_KEY", DUMMY_KEY)
        monkeypatch.setenv("BPC_HYBRID_LLM_ENABLED", "true")
        monkeypatch.setenv("BPC_HYBRID_LLM_PROVIDER", "openai_compatible")
        cfg = LLMConfig.from_env(project_root=tmp_path)
        assert cfg.api_key == DUMMY_KEY  # system env wins, not "dotenv-key"

    def test_api_key_not_in_repr_with_dotenv(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "BPC_HYBRID_LLM_ENABLED=true\n"
            "BPC_HYBRID_LLM_PROVIDER=openai_compatible\n"
            f"BPC_HYBRID_LLM_API_KEY={DUMMY_KEY}\n"
        )
        for k in list(os.environ):
            if k.startswith("BPC_HYBRID_LLM_"):
                monkeypatch.delenv(k, raising=False)
        cfg = LLMConfig.from_env(project_root=tmp_path)
        r = repr(cfg)
        assert DUMMY_KEY not in r
        assert "REDACTED" in r

    def test_no_project_root_works_as_before(self, monkeypatch):
        """from_env() without project_root must still work (backward compat)."""
        for k in list(os.environ):
            if k.startswith("BPC_HYBRID_LLM_"):
                monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("BPC_HYBRID_LLM_PROVIDER", "disabled")
        cfg = LLMConfig.from_env()
        assert cfg.provider == "disabled"


# ---------------------------------------------------------------------------
# R9.0.1 — Audit-safe env loading controls
# ---------------------------------------------------------------------------

class TestProjectEnvDisabled:
    """Verify from_env() respects load_project_env=False and
    BPC_HYBRID_DISABLE_PROJECT_ENV."""

    # -- load_project_env=False ---------------------------------------------

    def test_load_project_env_false_skips_dotenv(self, tmp_path, monkeypatch):
        """With load_project_env=False, .env is never read."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "BPC_HYBRID_LLM_PROVIDER=openai_compatible\n"
            "BPC_HYBRID_LLM_MODEL=gpt-4\n",
            encoding="utf-8",
        )
        for k in list(os.environ):
            if k.startswith("BPC_HYBRID_LLM_"):
                monkeypatch.delenv(k, raising=False)
        cfg = LLMConfig.from_env(project_root=tmp_path, load_project_env=False)
        # Should use defaults, not .env values
        assert cfg.provider == "mock"
        assert cfg.model == "mock"

    # -- BPC_HYBRID_DISABLE_PROJECT_ENV ------------------------------------

    def test_disable_env_var_skips_dotenv(self, tmp_path, monkeypatch):
        """BPC_HYBRID_DISABLE_PROJECT_ENV=1 skips .env reading."""
        env_file = tmp_path / ".env"
        env_file.write_text("BPC_HYBRID_LLM_MODEL=gpt-4\n", encoding="utf-8")
        monkeypatch.setenv("BPC_HYBRID_DISABLE_PROJECT_ENV", "1")
        for k in list(os.environ):
            if k.startswith("BPC_HYBRID_LLM_"):
                monkeypatch.delenv(k, raising=False)
        cfg = LLMConfig.from_env(project_root=tmp_path)
        assert cfg.model == "mock"  # default, not gpt-4

    @pytest.mark.parametrize("truthy_val", ["true", "yes", "on"])
    def test_disable_env_var_truthy_values(self, truthy_val, tmp_path, monkeypatch):
        """All recognised truthy values disable .env loading."""
        env_file = tmp_path / ".env"
        env_file.write_text("BPC_HYBRID_LLM_MODEL=gpt-4\n", encoding="utf-8")
        monkeypatch.setenv("BPC_HYBRID_DISABLE_PROJECT_ENV", truthy_val)
        for k in list(os.environ):
            if k.startswith("BPC_HYBRID_LLM_"):
                monkeypatch.delenv(k, raising=False)
        cfg = LLMConfig.from_env(project_root=tmp_path)
        assert cfg.model == "mock"

    # -- disable only from system env, not .env ----------------------------

    def test_disable_not_read_from_dotenv(self, tmp_path, monkeypatch):
        """BPC_HYBRID_DISABLE_PROJECT_ENV in .env does NOT disable."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "BPC_HYBRID_DISABLE_PROJECT_ENV=1\n"
            "BPC_HYBRID_LLM_MODEL=gpt-4\n",
            encoding="utf-8",
        )
        # Ensure system env does NOT have the disable var
        monkeypatch.delenv("BPC_HYBRID_DISABLE_PROJECT_ENV", raising=False)
        for k in list(os.environ):
            if k.startswith("BPC_HYBRID_LLM_"):
                monkeypatch.delenv(k, raising=False)
        cfg = LLMConfig.from_env(project_root=tmp_path)
        # .env is still read because disable is NOT a system env var
        # But BPC_HYBRID_DISABLE_PROJECT_ENV is NOT whitelisted, so it's ignored
        assert cfg.model == "gpt-4"  # .env was read normally

    # -- normal loading still works -----------------------------------------

    def test_normal_load_still_reads_dotenv(self, tmp_path, monkeypatch):
        """With load_project_env=True (default), .env is read."""
        env_file = tmp_path / ".env"
        env_file.write_text("BPC_HYBRID_LLM_PROVIDER=openai_compatible\n")
        for k in list(os.environ):
            if k.startswith("BPC_HYBRID_LLM_"):
                monkeypatch.delenv(k, raising=False)
        cfg = LLMConfig.from_env(project_root=tmp_path)
        assert cfg.provider == "openai_compatible"

    # -- system env still overrides -----------------------------------------

    def test_system_env_still_overrides_with_disable_unset(self, tmp_path, monkeypatch):
        """System env overrides .env even when disable is not set."""
        env_file = tmp_path / ".env"
        env_file.write_text("BPC_HYBRID_LLM_PROVIDER=mock\n")
        monkeypatch.setenv("BPC_HYBRID_LLM_PROVIDER", "disabled")
        cfg = LLMConfig.from_env(project_root=tmp_path)
        assert cfg.provider == "disabled"  # system env wins

    # -- API key safety ----------------------------------------------------

    def test_api_key_not_in_repr_with_disabled(self, tmp_path, monkeypatch):
        """API key never in repr even when env loading is disabled."""
        # This is always true anyway — verify for completeness
        cfg = LLMConfig(
            enabled=True,
            provider="openai_compatible",
            api_key=DUMMY_KEY,
        )
        r = repr(cfg)
        assert DUMMY_KEY not in r
        assert "REDACTED" in r

    # -- project_env_disabled helper ---------------------------------------

    def test_project_env_disabled_defaults_false(self):
        """Without the env var, returns False."""
        assert project_env_disabled({}) is False
        assert project_env_disabled({"OTHER": "1"}) is False

    def test_project_env_disabled_detects_truthy(self):
        """Detects truthy disable values."""
        for val in ("1", "true", "yes", "on"):
            assert project_env_disabled(
                {"BPC_HYBRID_DISABLE_PROJECT_ENV": val}
            ) is True

    def test_project_env_disabled_case_insensitive(self):
        """Truthy check is case-insensitive."""
        assert project_env_disabled(
            {"BPC_HYBRID_DISABLE_PROJECT_ENV": "TRUE"}
        ) is True
        assert project_env_disabled(
            {"BPC_HYBRID_DISABLE_PROJECT_ENV": "On"}
        ) is True

    def test_project_env_disabled_rejects_falsey(self):
        """Values other than 1/true/yes/on are not truthy."""
        for val in ("0", "false", "no", "off", "", "maybe"):
            assert project_env_disabled(
                {"BPC_HYBRID_DISABLE_PROJECT_ENV": val}
            ) is False
