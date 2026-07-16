"""LLM provider configuration gate with secret redaction (R7 + R9.0).

Provides a safety-gated configuration layer for later real LLM fallback
experiments.  R7 does **not** call any real LLM API and does not store
raw responses.

R9.0 adds project-root ``.env`` support as a **fallback** for
environment variables.  The ``.env`` file is **not** required; when
missing the loader returns an empty dict without error.  Only
whitelisted ``BPC_HYBRID_*`` keys are accepted, and values are never
echoed in logs.

The configuration defaults to ``enabled=False`` and ``provider="mock"``,
making real LLM calls opt-in only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Allowed provider values
# ---------------------------------------------------------------------------

ALLOWED_PROVIDERS: frozenset[str] = frozenset({"mock", "openai_compatible", "disabled"})

# ---------------------------------------------------------------------------
# Whitelist of keys accepted from project-root .env file
# ---------------------------------------------------------------------------

_ENV_WHITELIST: frozenset[str] = frozenset(
    {
        # Legacy flat keys (still supported as fallback)
        "BPC_HYBRID_LLM_PROVIDER",
        "BPC_HYBRID_LLM_MODEL",
        "BPC_HYBRID_LLM_BASE_URL",
        "BPC_HYBRID_LLM_API_KEY",
        "BPC_HYBRID_LLM_ENABLED",
        "BPC_HYBRID_LLM_TIMEOUT_SECONDS",
        "BPC_HYBRID_LLM_MAX_TOKENS",
        "BPC_HYBRID_LLM_TEMPERATURE",
        "BPC_HYBRID_LLM_TOP_P",
        "BPC_HYBRID_LLM_SEED",
        "BPC_HYBRID_LLM_SEED_SUPPORTED",
        "BPC_HYBRID_R9_REAL_RUN_CONFIRMED",
        # Profile selector
        "BPC_HYBRID_LLM_PROFILE",
        # Qwen profile keys
        "BPC_HYBRID_Qwen_PROVIDER",
        "BPC_HYBRID_Qwen_MODEL",
        "BPC_HYBRID_Qwen_BASE_URL",
        "BPC_HYBRID_Qwen_API_KEY",
        "BPC_HYBRID_Qwen_TOP_P",
        "BPC_HYBRID_Qwen_SEED",
        "BPC_HYBRID_Qwen_SEED_SUPPORTED",
        # DeepSeek profile keys
        "BPC_HYBRID_DeepSeek_PROVIDER",
        "BPC_HYBRID_DeepSeek_MODEL",
        "BPC_HYBRID_DeepSeek_BASE_URL",
        "BPC_HYBRID_DeepSeek_API_KEY",
        "BPC_HYBRID_DeepSeek_TOP_P",
        "BPC_HYBRID_DeepSeek_SEED",
        "BPC_HYBRID_DeepSeek_SEED_SUPPORTED",
    }
)

# ---------------------------------------------------------------------------
# .env loader (R9.0)
# ---------------------------------------------------------------------------

def project_env_disabled(environ: Mapping[str, str] | None = None) -> bool:
    """Return ``True`` if project ``.env`` loading is disabled via system env.

    Reads ``BPC_HYBRID_DISABLE_PROJECT_ENV`` from *environ* (defaults to
    ``os.environ``).  Recognised truthy values: ``1``, ``true``, ``yes``,
    ``on`` (case-insensitive).

    This control **must only** come from system environment variables —
    never from the ``.env`` file itself.
    """
    if environ is None:
        environ = os.environ
    val = environ.get("BPC_HYBRID_DISABLE_PROJECT_ENV", "").strip().lower()
    return val in ("1", "true", "yes", "on")


def load_project_env_file(project_root: Path | str) -> dict[str, str]:
    """Load whitelisted ``BPC_HYBRID_*`` keys from *project_root*/.env.

    Rules:

    * Only reads ``.env`` directly inside *project_root* (no recursion).
    * Only accepts keys listed in ``_ENV_WHITELIST``.
    * Ignores empty lines, ``#`` comments, and unknown keys.
    * Trims leading/trailing whitespace from values.
    * Does **not** print values — never call with an exception handler
      that echoes the full dict.
    * If the file is missing or unreadable, returns an empty dict
      **without** raising an error.

    Returns:
        dict[str, str]: Whitelisted key→value pairs from the file.
    """
    env_path = Path(project_root) / ".env"
    result: dict[str, str] = {}

    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, PermissionError, OSError):
        return result

    for raw_line in lines:
        line = raw_line.strip()
        # skip empty lines and comments
        if not line or line.startswith("#"):
            continue
        # must contain "="
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key in _ENV_WHITELIST:
            result[key] = value

    return result


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

# Query-parameter keys that indicate secret material in URLs
_SECRET_QUERY_KEYS: frozenset[str] = frozenset(
    {
        "api_key", "apikey", "key", "token", "secret", "password",
        "access_token", "authorization", "auth",
    }
)


def _base_url_has_secrets(url: str) -> bool:
    """Return True if *url* embeds secret-like material.

    Detects:

    * Query parameters named ``api_key``, ``key``, ``token``, ``secret``,
      ``password``, ``auth``, ``apikey`` (case-insensitive).
    * ``user:password@`` in the authority portion.
    """
    import re
    # user:password@host pattern
    if re.search(r"://[^/]*@", url):
        return True
    # query-string secret keys
    lower = url.lower()
    for qk in _SECRET_QUERY_KEYS:
        if f"?{qk}=" in lower or f"&{qk}=" in lower:
            return True
    return False


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

    Also redacts ``base_url`` values that contain secret-like query
    parameters or ``user:password@`` authorities.
    """
    sensitive = {"key", "secret", "token"}
    base_url_keys = {"base_url", "url", "endpoint", "api_url"}
    result: dict[str, Any] = {}
    for k, v in mapping.items():
        if any(s in k.lower() for s in sensitive):
            result[k] = _REDACTED
        elif isinstance(v, str):
            lower = v.lower()
            if "sk-" in lower or "bearer" in lower:
                result[k] = _REDACTED
            elif k.lower() in base_url_keys and _base_url_has_secrets(v):
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

    Sampling parameters (Wave 1.1 §4):

    * ``temperature``: in [0.0, 2.0]. Default 0.0.
    * ``top_p``: in [0.0, 1.0] or ``None`` (omit). Default 1.0.
    * ``seed``: integer or ``None``. Sent **only** when the
      ``seed_supported`` capability flag is ``True`` for the current
      profile. The provider may still ignore the seed; the manifest
      records the actual sent value, not the request.
    * ``max_tokens``: positive integer.

    The fixed-seed claim is **not** retroactively justified by the
    local Barrientos artifact: that artifact verifies ``temperature=0``
    in the prompt template but does not verify deterministic seed
    delivery. We therefore treat seed as a best-effort capability.
    """

    enabled: bool = False
    provider: str = "mock"
    model: str = "mock"
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: float = 30.0
    max_tokens: int = 1024
    temperature: float = 0.0
    top_p: float | None = 1.0
    seed: int | None = None
    seed_supported: bool = False

    # -- validation ---------------------------------------------------------

    def validate(self) -> None:
        """Validate this configuration.

        Raises :class:`LLMConfigError` if the configuration is
        inconsistent (e.g. invalid provider, bad numeric bounds,
        secret material in base_url, or enabled with a real provider
        but no API key).

        Provider whitelist and numeric bounds are **always** checked,
        regardless of ``enabled``.
        """
        # -- always: provider whitelist ------------------------------------
        if self.provider not in ALLOWED_PROVIDERS:
            raise LLMConfigError(
                f"Invalid provider {self.provider!r}. "
                f"Allowed: {sorted(ALLOWED_PROVIDERS)}"
            )

        # -- always: numeric bounds ----------------------------------------
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
        if self.top_p is not None and not (0.0 <= self.top_p <= 1.0):
            raise LLMConfigError(
                f"top_p must be in [0.0, 1.0] or None, got {self.top_p}"
            )
        if self.seed is not None and not isinstance(self.seed, int):
            raise LLMConfigError(
                f"seed must be an int or None, got {self.seed!r}"
            )

        # -- always: base_url must not embed secrets -----------------------
        if self.base_url and _base_url_has_secrets(self.base_url):
            raise LLMConfigError(
                "base_url contains secret material (query parameter or "
                "user:password@ authority). Use headers/Authorization "
                "for credentials instead."
            )

        # -- only when enabled: API key for real providers -----------------
        if not self.enabled:
            return  # disabled configs never need an API key

        if self.provider in ("mock", "disabled"):
            return  # mock/disabled never needs an API key

        if self.provider == "openai_compatible":
            if not self.api_key:
                raise LLMConfigError(
                    f"Provider {self.provider!r} requires an API key, "
                    f"but api_key is unset"
                )

    def __post_init__(self) -> None:
        self.validate()

    # -- repr / str (redacted) ----------------------------------------------

    def __repr__(self) -> str:
        # Redact base_url if it contains secret material
        if self.base_url and _base_url_has_secrets(self.base_url):
            base_display = "***REDACTED***"
        else:
            base_display = repr(self.base_url)
        return (
            f"LLMConfig(enabled={self.enabled}, provider={self.provider!r}, "
            f"model={self.model!r}, api_key={redact_secret(self.api_key)}, "
            f"base_url={base_display}, timeout_seconds={self.timeout_seconds}, "
            f"max_tokens={self.max_tokens}, temperature={self.temperature}, "
            f"top_p={self.top_p}, seed={self.seed}, seed_supported={self.seed_supported})"
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
            "top_p": self.top_p,
            "seed": self.seed,
            "seed_supported": self.seed_supported,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LLMConfig:
        top_p_raw = d.get("top_p", 1.0)
        top_p: float | None = None if top_p_raw is None else float(top_p_raw)
        seed_raw = d.get("seed")
        seed: int | None = None if seed_raw is None else int(seed_raw)
        return cls(
            enabled=bool(d.get("enabled", False)),
            provider=str(d.get("provider", "mock")),
            model=str(d.get("model", "mock")),
            api_key=d.get("api_key"),
            base_url=d.get("base_url"),
            timeout_seconds=float(d.get("timeout_seconds", 30.0)),
            max_tokens=int(d.get("max_tokens", 1024)),
            temperature=float(d.get("temperature", 0.0)),
            top_p=top_p,
            seed=seed,
            seed_supported=bool(d.get("seed_supported", False)),
        )

    # -- from_env -----------------------------------------------------------

    @classmethod
    def from_env(cls, project_root: Path | str | None = None, load_project_env: bool = True) -> LLMConfig:
        """Build a configuration from environment variables.

        Reads ``BPC_HYBRID_LLM_*`` environment variables with an
        optional project-root ``.env`` **fallback**.

        Priority: **system environment variables > .env file**.

        When *project_root* is provided **and** *load_project_env* is
        ``True`` **and** ``BPC_HYBRID_DISABLE_PROJECT_ENV`` is not set
        in the system environment, whitelisted keys from
        ``project_root/.env`` are loaded and used as defaults for any
        key that is **not** already set in the system environment.
        Missing ``.env`` is silent — no error is raised.

        Parameters:
            project_root:
                Path to the project root.  When provided (and loading
                is not disabled), ``project_root/.env`` is read as a
                fallback.
            load_project_env:
                Set to ``False`` to skip ``.env`` reading even when
                *project_root* is provided.  This is the audit/test
                override — it does **not** read the file at all.

        Environment variables read:

        * ``BPC_HYBRID_LLM_ENABLED``
        * ``BPC_HYBRID_LLM_PROVIDER``
        * ``BPC_HYBRID_LLM_MODEL``
        * ``BPC_HYBRID_LLM_API_KEY``
        * ``BPC_HYBRID_LLM_BASE_URL``
        * ``BPC_HYBRID_LLM_TIMEOUT_SECONDS``
        * ``BPC_HYBRID_LLM_MAX_TOKENS``
        * ``BPC_HYBRID_LLM_TEMPERATURE``

        API key values are never echoed in logs.
        """
        # -- load .env fallback (if enabled) -----------------------------
        dotenv: dict[str, str] = {}
        if project_root is not None and load_project_env and not project_env_disabled():
            dotenv = load_project_env_file(project_root)

        def _get(key: str, default: str) -> str:
            """System env var wins; .env is fallback."""
            env_val = os.environ.get(key)
            if env_val is not None:
                return env_val
            return dotenv.get(key, default)

        # -- profile-based lookup: if BPC_HYBRID_LLM_PROFILE is set,    --
        # -- use profile keys as fallback for missing flat keys          --
        profile_name = _get("BPC_HYBRID_LLM_PROFILE", "").strip().lower()
        profile_key_map = {
            "qwen": "Qwen",
            "deepseek": "DeepSeek",
        }
        profile_prefix = ""
        if profile_name in profile_key_map:
            profile_prefix = f"BPC_HYBRID_{profile_key_map[profile_name]}_"

        def _get_with_profile(flat_key: str, default: str) -> str:
            """When profile is set: profile key > flat key > default.

            When no profile is set: flat key > default (legacy behavior).
            """
            if profile_prefix:
                # Profile mode: check profile key first
                suffix = flat_key.replace("BPC_HYBRID_LLM_", "")
                profile_key = f"{profile_prefix}{suffix}"
                # 1. Profile key in system env
                env_val = os.environ.get(profile_key)
                if env_val is not None:
                    return env_val
                # 2. Profile key in .env
                if profile_key in dotenv:
                    return dotenv[profile_key]
            # 3. Flat key in system env
            env_val = os.environ.get(flat_key)
            if env_val is not None:
                return env_val
            # 4. Flat key in .env
            if flat_key in dotenv:
                return dotenv[flat_key]
            return default

        def _bool_env(name: str, default: bool = False) -> bool:
            v = os.environ.get(name)
            if v is None:
                v = dotenv.get(name, "")
            v = v.strip().lower()
            if not v:
                return default
            return v in ("1", "true", "yes", "on")

        enabled = _bool_env("BPC_HYBRID_LLM_ENABLED", False)
        provider = _get_with_profile("BPC_HYBRID_LLM_PROVIDER", "mock").strip()
        model = _get_with_profile("BPC_HYBRID_LLM_MODEL", "mock").strip()
        api_key = _get_with_profile("BPC_HYBRID_LLM_API_KEY", "") or None
        base_url = _get_with_profile("BPC_HYBRID_LLM_BASE_URL", "") or None

        timeout_raw = _get("BPC_HYBRID_LLM_TIMEOUT_SECONDS", "30.0")
        tokens_raw = _get("BPC_HYBRID_LLM_MAX_TOKENS", "1024")
        temp_raw = _get("BPC_HYBRID_LLM_TEMPERATURE", "0.0")
        top_p_raw = _get("BPC_HYBRID_LLM_TOP_P", "1.0")
        seed_raw = _get("BPC_HYBRID_LLM_SEED", "")
        seed_supported_raw = _get("BPC_HYBRID_LLM_SEED_SUPPORTED", "false")

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

        # top_p: empty string -> None (omit); otherwise float
        top_p: float | None
        if top_p_raw == "":
            top_p = None
        else:
            try:
                top_p = float(top_p_raw)
            except ValueError:
                raise LLMConfigError(
                    f"BPC_HYBRID_LLM_TOP_P must be a float or empty, got {top_p_raw!r}"
                )

        # seed: empty string -> None; otherwise int
        seed: int | None
        if seed_raw == "":
            seed = None
        else:
            try:
                seed = int(seed_raw)
            except ValueError:
                raise LLMConfigError(
                    f"BPC_HYBRID_LLM_SEED must be an int or empty, got {seed_raw!r}"
                )

        seed_supported = seed_supported_raw.strip().lower() in ("1", "true", "yes", "on")

        return cls(
            enabled=enabled,
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            seed_supported=seed_supported,
        )

    # -- from_env_profile --------------------------------------------------

    @classmethod
    def from_env_profile(
        cls,
        profile: str | None = None,
        project_root: Path | str | None = None,
        load_project_env: bool = True,
        timeout_seconds: float = 120.0,
        max_tokens: int = 4096,
    ) -> LLMConfig:
        """Build a configuration from a named profile in the .env file.

        Profiles allow switching between providers (e.g. ``"qwen"`` for
        production, ``"deepseek"`` for testing) without editing code.

        The .env file should contain keys like::

            BPC_HYBRID_LLM_PROFILE=deepseek
            BPC_HYBRID_DeepSeek_PROVIDER=openai_compatible
            BPC_HYBRID_DeepSeek_MODEL=deepseek-chat
            BPC_HYBRID_DeepSeek_BASE_URL=https://api.deepseek.com/v1
            BPC_HYBRID_DeepSeek_API_KEY=sk-xxx

        Parameters:
            profile:
                Profile name (``"qwen"``, ``"deepseek"``, etc.).
                If ``None``, reads ``BPC_HYBRID_LLM_PROFILE`` from
                env/.env. Defaults to ``"deepseek"`` if not set.
            project_root:
                Path to the project root for .env loading.
            load_project_env:
                Whether to load .env file.
            timeout_seconds:
                HTTP timeout (default 120s for LLM calls).
            max_tokens:
                Max output tokens (default 4096).

        Returns:
            LLMConfig configured for the specified profile.
        """
        dotenv: dict[str, str] = {}
        if project_root is not None and load_project_env and not project_env_disabled():
            dotenv = load_project_env_file(project_root)

        def _get(key: str, default: str = "") -> str:
            env_val = os.environ.get(key)
            if env_val is not None:
                return env_val
            return dotenv.get(key, default)

        # Determine profile name
        if profile is None:
            profile = _get("BPC_HYBRID_LLM_PROFILE", "deepseek").strip().lower()

        # Map profile name to env key prefix
        # "qwen" -> "BPC_HYBRID_Qwen_"
        # "deepseek" -> "BPC_HYBRID_DeepSeek_"
        profile_key_map = {
            "qwen": "Qwen",
            "deepseek": "DeepSeek",
        }
        key_prefix = profile_key_map.get(profile)
        if key_prefix is None:
            raise LLMConfigError(
                f"Unknown LLM profile {profile!r}. "
                f"Available: {sorted(profile_key_map.keys())}"
            )

        prefix = f"BPC_HYBRID_{key_prefix}_"

        provider = _get(f"{prefix}PROVIDER", "openai_compatible").strip()
        model = _get(f"{prefix}MODEL", "deepseek-chat").strip()
        api_key = _get(f"{prefix}API_KEY", "") or None
        base_url = _get(f"{prefix}BASE_URL", "") or None
        top_p_raw = _get(f"{prefix}TOP_P", "1.0")
        seed_raw = _get(f"{prefix}SEED", "")
        seed_supported_raw = _get(f"{prefix}SEED_SUPPORTED", "false")
        enabled = True  # profiles are always enabled

        if not api_key:
            raise LLMConfigError(
                f"Profile {profile!r} requires {prefix}API_KEY to be set "
                f"in .env or environment variables"
            )
        if api_key == "YOUR_DEEPSEEK_API_KEY_HERE":
            raise LLMConfigError(
                f"Profile {profile!r}: Please replace the placeholder "
                f"{prefix}API_KEY with your actual API key in .env"
            )

        top_p: float | None = None if top_p_raw == "" else float(top_p_raw)
        seed: int | None = None if seed_raw == "" else int(seed_raw)
        seed_supported = seed_supported_raw.strip().lower() in ("1", "true", "yes", "on")

        return cls(
            enabled=enabled,
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            temperature=0.0,
            top_p=top_p,
            seed=seed,
            seed_supported=seed_supported,
        )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def get_llm_config(
    profile: str | None = None,
    project_root: Path | str | None = None,
    **kwargs: Any,
) -> LLMConfig:
    """Get an LLMConfig for the given profile.

    This is the recommended entry point for scripts::

        from bpc_hybrid.llm_config import get_llm_config
        config = get_llm_config("deepseek")  # or "qwen"

    If *project_root* is ``None``, auto-detected from this file's
    location (two levels up from ``src/bpc_hybrid/``).
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parents[2]
    return LLMConfig.from_env_profile(
        profile=profile,
        project_root=project_root,
        **kwargs,
    )
