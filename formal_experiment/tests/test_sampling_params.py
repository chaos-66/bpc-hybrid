"""Tests for LLM sampling parameters (Wave 1.1 \u00a74)."""

from __future__ import annotations

import json

import pytest

from bpc_hybrid.llm_config import LLMConfig, LLMConfigError
from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder


# ---------------------------------------------------------------------------
# LLMConfig sampling fields
# ---------------------------------------------------------------------------


def test_llm_config_default_top_p_is_1():
    c = LLMConfig()
    assert c.top_p == 1.0


def test_llm_config_default_seed_is_none_and_unsupported():
    c = LLMConfig()
    assert c.seed is None
    assert c.seed_supported is False


def test_llm_config_rejects_top_p_out_of_range():
    with pytest.raises(LLMConfigError):
        LLMConfig(top_p=1.5)
    with pytest.raises(LLMConfigError):
        LLMConfig(top_p=-0.1)


def test_llm_config_top_p_none_allowed():
    c = LLMConfig(top_p=None)
    assert c.top_p is None


def test_llm_config_seed_must_be_int_or_none():
    with pytest.raises(LLMConfigError):
        LLMConfig(seed="42")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# from_dict round-trip
# ---------------------------------------------------------------------------


def test_llm_config_from_dict_round_trip_sampling():
    c = LLMConfig(temperature=0.5, top_p=0.9, seed=42, seed_supported=True)
    c2 = LLMConfig.from_dict(c.to_dict())
    assert c2.temperature == 0.5
    assert c2.top_p == 0.9
    assert c2.seed == 42
    assert c2.seed_supported is True


def test_llm_config_from_dict_handles_null_top_p_and_seed():
    c2 = LLMConfig.from_dict({
        "enabled": False, "provider": "mock", "model": "mock",
        "timeout_seconds": 30.0, "max_tokens": 1024, "temperature": 0.0,
        "top_p": None, "seed": None, "seed_supported": False,
    })
    assert c2.top_p is None
    assert c2.seed is None
    assert c2.seed_supported is False


# ---------------------------------------------------------------------------
# OpenAICompatibleRequestBuilder body
# ---------------------------------------------------------------------------


def _builder(top_p=1.0, seed=None, seed_supported=False) -> OpenAICompatibleRequestBuilder:
    cfg = LLMConfig(
        provider="openai_compatible", model="m", api_key="sk-test",
        base_url="https://api.example.com/v1", temperature=0.0,
        top_p=top_p, seed=seed, seed_supported=seed_supported,
    )
    return OpenAICompatibleRequestBuilder(cfg)


def test_request_body_sends_top_p_when_set():
    b = _builder(top_p=0.95)
    body = b.build_body("s", "u")
    assert body["top_p"] == 0.95


def test_request_body_omits_top_p_when_none():
    b = _builder(top_p=None)
    body = b.build_body("s", "u")
    assert "top_p" not in body


def test_request_body_omits_seed_when_not_supported():
    b = _builder(seed=42, seed_supported=False)
    body = b.build_body("s", "u")
    assert "seed" not in body


def test_request_body_omits_seed_when_seed_none_even_if_supported():
    b = _builder(seed=None, seed_supported=True)
    body = b.build_body("s", "u")
    assert "seed" not in body


def test_request_body_sends_seed_only_when_both_supported_and_set():
    b = _builder(seed=42, seed_supported=True)
    body = b.build_body("s", "u")
    assert body["seed"] == 42


# ---------------------------------------------------------------------------
# sent_sampling_params manifest helper
# ---------------------------------------------------------------------------


def test_sent_sampling_params_omitted_top_p_when_none():
    b = _builder(top_p=None)
    sent = b.sent_sampling_params()
    assert sent["top_p"] == "omitted"


def test_sent_sampling_params_unsupported_seed_default():
    b = _builder(seed=42, seed_supported=False)
    sent = b.sent_sampling_params()
    assert sent["seed"] == "unsupported_or_omitted"


def test_sent_sampling_params_includes_seed_when_supported():
    b = _builder(seed=42, seed_supported=True)
    sent = b.sent_sampling_params()
    assert sent["seed"] == 42
