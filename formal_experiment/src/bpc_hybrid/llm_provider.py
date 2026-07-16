"""LLM provider factory with profile-based switching.

Usage in scripts::

    from bpc_hybrid.llm_provider import create_transport

    # Use default profile from .env (BPC_HYBRID_LLM_PROFILE)
    transport = create_transport()

    # Explicitly use DeepSeek for testing
    transport = create_transport("deepseek")

    # Explicitly use Qwen for production
    transport = create_transport("qwen")

    # Send a request
    response = transport.send(request)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bpc_hybrid.llm_client import RealAPITransport
from bpc_hybrid.llm_config import LLMConfig, get_llm_config

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def create_transport(
    profile: str | None = None,
    timeout_seconds: float = 120.0,
    max_tokens: int = 4096,
    project_root: Path | str | None = None,
) -> RealAPITransport:
    """Create a RealAPITransport for the given profile.

    Parameters:
        profile:
            ``"qwen"`` or ``"deepseek"``. If ``None``, reads
            ``BPC_HYBRID_LLM_PROFILE`` from .env (default: ``"deepseek"``).
        timeout_seconds:
            HTTP timeout in seconds.
        max_tokens:
            Maximum output tokens.
        project_root:
            Project root for .env loading. Auto-detected if None.

    Returns:
        A configured ``RealAPITransport`` instance.
    """
    if project_root is None:
        project_root = _PROJECT_ROOT

    config = get_llm_config(
        profile=profile,
        project_root=project_root,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
    )
    return RealAPITransport(config=config, timeout_seconds=timeout_seconds)


def get_active_profile() -> str:
    """Return the currently active profile name from .env."""
    from bpc_hybrid.llm_config import load_project_env_file
    dotenv = load_project_env_file(_PROJECT_ROOT)
    import os
    return os.environ.get(
        "BPC_HYBRID_LLM_PROFILE",
        dotenv.get("BPC_HYBRID_LLM_PROFILE", "deepseek"),
    ).strip().lower()
