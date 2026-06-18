"""R11.3.1 Dedicated Single-call Real API Entrypoint Scaffold.

Provides a safety-gated, single-call CLI entrypoint for future R11.4
single-sentence real API schema-aligned smoke tests.  In R11.3.1, real
API execution is **refused by default** — only mock mode runs unless
the explicit future flag ``--execute-real-api`` is provided for
scaffold design validation.

Usage (mock, R11.3.1)::

    .\\.venv\\Scripts\\python.exe scripts\\run_single_call_schema_smoke.py \\
        --no-project-env \\
        --source-id r11_4_real_schema_smoke_001 \\
        --text "A controller shall record the decision."

**Safety constraints (R11.3.1 scaffold):**

* ``--no-project-env`` CLI flag — disables project-root ``.env`` loading.
* ``--batch`` CLI flag — explicitly rejected (single-call only).
* No ``.env`` read.
* No real API execution without ``--execute-real-api``.
* No raw response saved to disk.
* No batch mode — single call only.
* No benchmark, no accuracy claim, no method-validation claim.
* R11.4 will add the real execution path after Codex audit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from bpc_hybrid.fallback import FallbackRequest
from bpc_hybrid.llm_client import (
    LLMClientError,
    LLMFallbackAdapter,
    LLMResponse,
    MockLLMTransport,
    make_schema_valid_mock_response_json,
)
from bpc_hybrid.llm_config import LLMConfig, LLMConfigError, LLMProvider

# ---------------------------------------------------------------------------
# Metadata output builder
# ---------------------------------------------------------------------------

_METADATA_TEMPLATE: dict[str, object] = {
    "source_id": "",
    "input_text": "",
    "provider": "mock",
    "model": "mock",
    "entrypoint": "scripts/run_single_call_schema_smoke.py",
    "real_api_call_performed": False,
    "attempted_call_count": 0,
    "successful_call_count": 0,
    "fallback_status": "not_triggered",
    "schema_valid": False,
    "normalizer_used": True,
    "normalizer_status": "noop",
    "raw_response_saved": False,
    "secret_redacted": True,
    "batch": False,
    "error": None,
    "output": None,
}


def _build_metadata(**overrides: object) -> dict[str, object]:
    """Build a metadata dict from the template with overrides."""
    result = dict(_METADATA_TEMPLATE)
    result.update(overrides)
    return result


# ---------------------------------------------------------------------------
# Error / success emitters
# ---------------------------------------------------------------------------

def _emit_error(
    source_id: str,
    input_text: str,
    provider: str,
    model: str,
    error_message: str,
    **extra: object,
) -> str:
    """Emit a JSON error result (never contains raw secrets)."""
    meta = _build_metadata(
        source_id=source_id,
        input_text=input_text,
        provider=provider,
        model=model,
        error=error_message,
        **extra,
    )
    return json.dumps(meta, indent=2)


def _emit_success(
    source_id: str,
    input_text: str,
    provider: str,
    model: str,
    fallback_status: str,
    schema_valid: bool,
    normalizer_status: str,
    output: dict | None = None,
    **extra: object,
) -> str:
    """Emit a JSON success result (never contains raw secrets)."""
    meta = _build_metadata(
        source_id=source_id,
        input_text=input_text,
        provider=provider,
        model=model,
        fallback_status=fallback_status,
        schema_valid=schema_valid,
        normalizer_status=normalizer_status,
        output=output,
        **extra,
    )
    return json.dumps(meta, indent=2)


# ---------------------------------------------------------------------------
# JSON-safe ArgumentParser
# ---------------------------------------------------------------------------

class _JsonArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that emits JSON error envelopes instead of usage text."""

    def error(self, message: str) -> None:
        print(
            json.dumps(
                _build_metadata(error=f"CLI argument error: {message}"),
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)


# ---------------------------------------------------------------------------
# Gate: refuse real execution without explicit flag
# ---------------------------------------------------------------------------

_R11_3_REAL_REFUSAL_MSG = (
    "R11.3 scaffold does not execute real API calls. "
    "The --execute-real-api flag is accepted for scaffold design "
    "validation (R11.4 forward-compat) but the R11.3 scaffold "
    "still routes through mock transport. "
    "No network, no .env read, no raw response storage."
)


# ---------------------------------------------------------------------------
# Core: run single-call with metadata tracking
# ---------------------------------------------------------------------------

def run_single_call(
    source_id: str,
    text: str,
    provider: str = "mock",
    model: str = "mock",
    execute_real_api: bool = False,
    request_batch: bool = False,
) -> dict[str, object]:
    """Execute a single mock call and return metadata.

    This is the programmatic entrypoint — callable from tests without
    CLI or subprocess.

    Parameters
    ----------
    source_id : str
        Unique identifier for this single-call sample.
    text : str
        Source text to extract clauses from.
    provider : str
        LLM provider name (default ``"mock"``).
    model : str
        Model name (default ``"mock"``).
    execute_real_api : bool
        When ``True``, accepts the future flag (R11.4 forward-compat)
        but still routes through mock in R11.3.1.
    request_batch : bool
        When ``True``, the call is explicitly rejected — batch is not
        supported in this single-call entrypoint.

    Returns
    -------
    dict
        Full metadata dict per R11.3.1 spec.
    """
    # ---- Gate: explicit batch rejection ---------------------------------
    if request_batch:
        return _build_metadata(
            source_id=source_id,
            input_text=text,
            provider=provider,
            model=model,
            error="batch_not_supported — single-call entrypoint does not support batch execution",
            real_api_call_performed=False,
            attempted_call_count=0,
            successful_call_count=0,
            raw_response_saved=False,
            batch=False,
        )

    # ---- Gate: refuse non-mock provider without --execute-real-api ------
    if provider != "mock" and not execute_real_api:
        return _build_metadata(
            source_id=source_id,
            input_text=text,
            provider=provider,
            model=model,
            error=(
                f"Provider {provider!r} requires --execute-real-api for "
                f"real API execution. In R11.3, only --provider mock is "
                f"supported without --execute-real-api."
            ),
            real_api_call_performed=False,
            attempted_call_count=0,
            successful_call_count=0,
            raw_response_saved=False,
            batch=False,
        )

    # ---- Gate: --execute-real-api scaffold path (R11.3 still mock) ------
    if execute_real_api:
        # R11.3 scaffold: accept the flag but refuse real execution.
        # R11.4 will implement the actual real path here.
        return _build_metadata(
            source_id=source_id,
            input_text=text,
            provider=provider,
            model=model,
            error=_R11_3_REAL_REFUSAL_MSG,
            real_api_call_performed=False,
            attempted_call_count=0,
            successful_call_count=0,
            raw_response_saved=False,
            batch=False,
        )

    # ---- Build config and transport (mock-only in R11.3) ----------------
    try:
        config = LLMConfig(
            enabled=True,
            provider=provider,
            model=model,
        )
    except LLMConfigError as exc:
        return _build_metadata(
            source_id=source_id,
            input_text=text,
            provider=provider,
            model=model,
            error=f"LLMConfig error: {exc}",
            real_api_call_performed=False,
            attempted_call_count=0,
            successful_call_count=0,
            raw_response_saved=False,
            batch=False,
        )

    # Build schema-valid mock response
    mock_json_str = make_schema_valid_mock_response_json(text, source_id)
    mock_resp = LLMResponse(
        content=mock_json_str,
        provider=provider,
        model=model,
        finish_reason="stop",
    )
    transport = MockLLMTransport(fixed_response=mock_resp)

    # ---- Execute fallback ------------------------------------------------
    adapter = LLMFallbackAdapter(config=config, transport=transport)
    adapter.enable_schema_alignment = True

    request = FallbackRequest(
        source_text=text,
        source_id=source_id,
        rule_response=None,  # single-call entrypoint — no rule-first pre-extraction
    )

    attempted_call_count = 1
    successful_call_count = 0

    try:
        result = adapter.complete(request)
    except Exception as exc:
        return _build_metadata(
            source_id=source_id,
            input_text=text,
            provider=provider,
            model=model,
            error=f"LLM fallback execution failed: {exc}",
            fallback_status="error",
            attempted_call_count=attempted_call_count,
            successful_call_count=successful_call_count,
            real_api_call_performed=False,
            raw_response_saved=False,
            batch=False,
        )

    # ---- Determine fallback / schema / normalizer status ---------------
    if result.error is not None:
        return _build_metadata(
            source_id=source_id,
            input_text=text,
            provider=provider,
            model=model,
            error=result.error,
            fallback_status="error",
            schema_valid=result.is_valid,
            attempted_call_count=attempted_call_count,
            successful_call_count=successful_call_count,
            real_api_call_performed=False,
            raw_response_saved=False,
            batch=False,
        )

    if result.response is not None:
        successful_call_count = 1

    output_dict: dict | None = None
    if result.response is not None:
        output_dict = result.response.to_dict()

    return _build_metadata(
        source_id=source_id,
        input_text=text,
        provider=provider,
        model=model,
        fallback_status="success",
        schema_valid=result.is_valid,
        normalizer_status="accepted" if result.is_valid else "noop",
        output=output_dict,
        attempted_call_count=attempted_call_count,
        successful_call_count=successful_call_count,
        real_api_call_performed=False,
        raw_response_saved=False,
        batch=False,
        error=None,
    )


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = _JsonArgumentParser(
        description="R11.3.1 dedicated single-call real API entrypoint scaffold",
    )
    parser.add_argument(
        "--source-id",
        required=True,
        help="Unique source identifier for this single-call sample.",
    )
    parser.add_argument(
        "--text",
        required=True,
        help="Source text to extract clauses from.",
    )
    parser.add_argument(
        "--provider",
        default="mock",
        help="LLM provider (default: mock). Non-mock providers require --execute-real-api.",
    )
    parser.add_argument(
        "--model",
        default="mock",
        help="Model name (default: mock).",
    )
    parser.add_argument(
        "--no-project-env",
        action="store_true",
        default=False,
        help=(
            "Disable reading project-root .env file. "
            "This is a safety flag — it does NOT authorize real API execution. "
            "When set, BPC_HYBRID_DISABLE_PROJECT_ENV=1 is honored."
        ),
    )
    parser.add_argument(
        "--execute-real-api",
        action="store_true",
        default=False,
        help=(
            "Future real API execution flag (R11.4 forward-compat). "
            "In R11.3.1, this flag is accepted but routes through mock "
            "transport — no real API call is performed."
        ),
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        default=False,
        help=(
            "EXPLICITLY REJECTED — this single-call entrypoint does not "
            "support batch execution.  Passing --batch produces a refusal "
            "JSON with attempted_call_count=0."
        ),
    )

    args = parser.parse_args(argv)

    # ---- Honor --no-project-env -----------------------------------------
    if args.no_project_env:
        import os as _os_nope
        _os_nope.environ["BPC_HYBRID_DISABLE_PROJECT_ENV"] = "1"

    meta = run_single_call(
        source_id=args.source_id,
        text=args.text,
        provider=args.provider,
        model=args.model,
        execute_real_api=args.execute_real_api,
        request_batch=args.batch,
    )

    print(json.dumps(meta, indent=2))

    if meta.get("error") is not None:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
