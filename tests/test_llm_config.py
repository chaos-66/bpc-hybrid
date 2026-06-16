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
