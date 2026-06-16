"""LLM provider configuration gate with secret redaction (R7).

Provides a safety-gated configuration layer for later real LLM fallback
experiments.  R7 does **not** call any real LLM API, does not read
``.env`` files, and does not store raw responses.

The configuration defaults to ``enabled=False`` and ``provider="mock"``,
making real LLM calls opt-in only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Allowed provider values
# ---------------------------------------------------------------------------

ALLOWED_PROVIDERS: frozenset[str] = frozenset({"mock", "openai_compatible", "disabled"})


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class LLMConfigError(ValueError):
    """Raised when the LLM configuration is invalid or incomplete."""


# ---------------------------------------------------------------------------
# Provider enum
# ---------------------------------------------------------------------------

class LLMProvider:
    """Provider constants (string-based for easy env-var integration)."""

    MOCK = "mock"
    OPENAI_COMPATIBLE = "openai_compatible"
    DISABLED = "disabled"


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

_REDACTED = "***REDACTED***"


def redact_secret(value: str | None, *, visible: int = 4) -> str:
    """Return a redacted version of *value*.

    If *value* is ``None``, returns ``"None"``.  If the string is short,
    the whole value is replaced by ``***REDACTED***``.  Otherwise the
    first *visible* characters are shown followed by ``...``.
    """
    if value is None:
        return "None"
    if len(value) <= visible + 3:
        return _REDACTED
    return value[:visible] + "..." + _REDACTED


def redact_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of *mapping* with any value whose key
    contains ``'key'``, ``'secret'``, or ``'token'`` (case-insensitive)
    replaced by ``***REDACTED***``.
    """
    sensitive = {"key", "secret", "token"}
    result: dict[str, Any] = {}
    for k, v in mapping.items():
        if any(s in k.lower() for s in sensitive):
            result[k] = _REDACTED
        elif isinstance(v, str):
            lower = v.lower()
            if "sk-" in lower or "bearer" in lower:
                result[k] = _REDACTED
            else:
                result[k] = v
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# LLMConfig
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    """Safety-gated LLM provider configuration.

    All fields have secure defaults.  ``api_key`` is **never** printed
    in ``repr`` or ``str``.
    """

    enabled: bool = False
    provider: str = "mock"
    model: str = "mock"
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: float = 30.0
    max_tokens: int = 1024
    temperature: float = 0.0

    # -- validation ---------------------------------------------------------

    def validate(self) -> None:
        """Validate this configuration.

        Raises :class:`LLMConfigError` if the configuration is
        inconsistent (e.g. enabled with a real provider but no API key).
        """
        if not self.enabled:
            return  # nothing to validate when disabled

        if self.provider not in ALLOWED_PROVIDERS:
            raise LLMConfigError(
                f"Invalid provider {self.provider!r}. "
                f"Allowed: {sorted(ALLOWED_PROVIDERS)}"
            )

        if self.provider in ("mock", "disabled"):
            pass  # mock/disabled never needs an API key
        elif self.provider == "openai_compatible":
            if not self.api_key:
                raise LLMConfigError(
                    f"Provider {self.provider!r} requires an API key, "
                    f"but api_key is unset"
                )

        if self.timeout_seconds <= 0:
            raise LLMConfigError(
                f"timeout_seconds must be > 0, got {self.timeout_seconds}"
            )
        if self.max_tokens < 1:
            raise LLMConfigError(
                f"max_tokens must be >= 1, got {self.max_tokens}"
            )
        if not (0.0 <= self.temperature <= 2.0):
            raise LLMConfigError(
                f"temperature must be in [0.0, 2.0], got {self.temperature}"
            )

    def __post_init__(self) -> None:
        self.validate()

    # -- repr / str (redacted) ----------------------------------------------

    def __repr__(self) -> str:
        return (
            f"LLMConfig(enabled={self.enabled}, provider={self.provider!r}, "
            f"model={self.model!r}, api_key={redact_secret(self.api_key)}, "
            f"base_url={self.base_url!r}, timeout_seconds={self.timeout_seconds}, "
            f"max_tokens={self.max_tokens}, temperature={self.temperature})"
        )

    def __str__(self) -> str:
        return self.__repr__()

    # -- dict round-trip ----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "timeout_seconds": self.timeout_seconds,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LLMConfig:
        return cls(
            enabled=bool(d.get("enabled", False)),
            provider=str(d.get("provider", "mock")),
            model=str(d.get("model", "mock")),
            api_key=d.get("api_key"),
            base_url=d.get("base_url"),
            timeout_seconds=float(d.get("timeout_seconds", 30.0)),
            max_tokens=int(d.get("max_tokens", 1024)),
            temperature=float(d.get("temperature", 0.0)),
        )

    # -- from_env -----------------------------------------------------------

    @classmethod
    def from_env(cls) -> LLMConfig:
        """Build a configuration from environment variables.

        Reads from ``BPC_HYBRID_LLM_*`` variables **only**.  Does not
        read ``.env`` files or call ``dotenv``.  API key values are
        never echoed in logs.

        Environment variables read:

        * ``BPC_HYBRID_LLM_ENABLED``
        * ``BPC_HYBRID_LLM_PROVIDER``
        * ``BPC_HYBRID_LLM_MODEL``
        * ``BPC_HYBRID_LLM_API_KEY``
        * ``BPC_HYBRID_LLM_BASE_URL``
        * ``BPC_HYBRID_LLM_TIMEOUT_SECONDS``
        * ``BPC_HYBRID_LLM_MAX_TOKENS``
        * ``BPC_HYBRID_LLM_TEMPERATURE``
        """
        def _bool_env(name: str, default: bool = False) -> bool:
            v = os.environ.get(name, "").strip().lower()
            if not v:
                return default
            return v in ("1", "true", "yes", "on")

        enabled = _bool_env("BPC_HYBRID_LLM_ENABLED", False)
        provider = os.environ.get("BPC_HYBRID_LLM_PROVIDER", "mock").strip()
        model = os.environ.get("BPC_HYBRID_LLM_MODEL", "mock").strip()
        api_key = os.environ.get("BPC_HYBRID_LLM_API_KEY") or None
        base_url = os.environ.get("BPC_HYBRID_LLM_BASE_URL") or None

        timeout_raw = os.environ.get("BPC_HYBRID_LLM_TIMEOUT_SECONDS", "30.0")
        tokens_raw = os.environ.get("BPC_HYBRID_LLM_MAX_TOKENS", "1024")
        temp_raw = os.environ.get("BPC_HYBRID_LLM_TEMPERATURE", "0.0")

        try:
            timeout_seconds = float(timeout_raw)
        except ValueError:
            raise LLMConfigError(
                f"BPC_HYBRID_LLM_TIMEOUT_SECONDS must be a float, "
                f"got {timeout_raw!r}"
            )

        try:
            max_tokens = int(tokens_raw)
        except ValueError:
            raise LLMConfigError(
                f"BPC_HYBRID_LLM_MAX_TOKENS must be an int, "
                f"got {tokens_raw!r}"
            )

        try:
            temperature = float(temp_raw)
        except ValueError:
            raise LLMConfigError(
                f"BPC_HYBRID_LLM_TEMPERATURE must be a float, "
                f"got {temp_raw!r}"
            )

        return cls(
            enabled=enabled,
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            temperature=temperature,
        )
