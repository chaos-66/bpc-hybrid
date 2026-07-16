"""Security helpers for the EStG-150 Layer D real-LLM runner
(2026-07-14 hardened, third iteration).

This module is shared by:

  * `scripts/run_llm_zh_aid.py` (real-run gate)
  * `scripts/promote_layer_d_v2.py` (pre-flight on `base_url` lock)
  * `scripts/estg150_review_tool.py` (display of the locked base_url)

Hard rules:

  S1.  Default policy: HTTPS only. The runner REFUSES to call any
       `http://` endpoint.
  S2.  The URL MUST be parsable by `urllib.parse.urlparse`. The
       scheme MUST be `https`.
  S3.  The URL MUST NOT contain a username or password (the
       `userinfo` part). API keys are NEVER allowed to live in
       the URL.
  S4.  The URL MUST NOT contain a fragment. Fragments are
       silently dropped by HTTP, so a fragment is almost
       certainly a misconfiguration.
  S5.  Localhost / 127.0.0.1 are allowed ONLY if the user
       explicitly passes `--allow-insecure-localhost`. This is
       for self-hosted OpenAI-compatible servers; it must never
       be the default.
  S6.  The validated base_url is locked into `run_config.json` on
       first write. Any resume with a different base_url is
       refused (handled by `run_config.json`'s lock, not here).
  S7.  The runner NEVER accepts a `--api-key <value>` flag. The
       API key is read ONLY from
       (a) an env var named by `--api-key-env-name NAME` or
       (b) `getpass.getpass` (interactive hidden input).
       See `scripts/run_llm_zh_aid.py:acquire_api_key()`.
"""
from __future__ import annotations

import urllib.parse


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class BaseUrlValidationError(ValueError):
    """Raised when a base_url fails the security check."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_base_url(
    url: str,
    *,
    allow_insecure_localhost: bool = False,
) -> str:
    """Validate a base_url for safety and return a canonicalised
    version (no trailing slash).

    Parameters
    ----------
    url:
        The candidate base URL. e.g. "https://api.openai.com/v1"
    allow_insecure_localhost:
        Set to True ONLY for self-hosted OpenAI-compatible
        servers on the local machine. The default is False
        (HTTPS-only).

    Raises
    ------
    BaseUrlValidationError
        If the URL fails any of the security checks.
    """
    if not isinstance(url, str) or not url.strip():
        raise BaseUrlValidationError("base_url is empty")
    candidate = url.strip()
    parsed = urllib.parse.urlparse(candidate)
    if not parsed.scheme:
        raise BaseUrlValidationError(
            f"base_url {url!r} has no scheme (must be https:// or http://localhost/127.0.0.1)"
        )
    if parsed.scheme == "http":
        # Allow http only for localhost / 127.0.0.1, and only with
        # explicit permission.
        host = (parsed.hostname or "").lower()
        if host not in ("localhost", "127.0.0.1", "::1"):
            raise BaseUrlValidationError(
                f"base_url {url!r} uses http://, which is forbidden for "
                f"non-localhost hosts. Use https://."
            )
        if not allow_insecure_localhost:
            raise BaseUrlValidationError(
                f"base_url {url!r} uses http://, which is forbidden. "
                f"Pass --allow-insecure-localhost to permit a self-hosted "
                f"server on {host}."
            )
    elif parsed.scheme != "https":
        raise BaseUrlValidationError(
            f"base_url {url!r} has scheme {parsed.scheme!r}; only "
            f"https is allowed (or http://localhost with "
            f"--allow-insecure-localhost)."
        )
    if parsed.username is not None or parsed.password is not None:
        raise BaseUrlValidationError(
            f"base_url {url!r} contains a username or password in the "
            f"userinfo part. The runner NEVER sends the API key in the "
            f"URL. The key is only in the HTTP Authorization header."
        )
    if parsed.fragment:
        raise BaseUrlValidationError(
            f"base_url {url!r} contains a fragment. Fragments are silently "
            f"dropped by HTTP, so this is almost certainly a misconfiguration."
        )
    if not parsed.netloc:
        raise BaseUrlValidationError(f"base_url {url!r} has no host")
    # Canonicalise: strip a trailing slash from the path.
    canonical = urllib.parse.urlunparse((
        parsed.scheme, parsed.netloc, parsed.path.rstrip("/"),
        parsed.params, parsed.query, "",
    ))
    return canonical


__all__ = [
    "BaseUrlValidationError",
    "validate_base_url",
]
