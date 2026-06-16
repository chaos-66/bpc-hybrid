"""R8 Controlled Single-Sample LLM Dry-Run Harness.

Provides a safety-gated CLI for single-sample LLM dry-runs.  In R8,
real API execution is **disabled** — only ``mock`` provider runs are
allowed.  Explicit ``--allow-llm`` and ``--single-sample`` flags are
required.  All output is JSON.  No raw secrets, no network, no file
writes.

Usage::

    .\\.venv\\Scripts\\python.exe scripts\\run_llm_dry_run.py \\
        --allow-llm --single-sample \\
        --source-id dry001 \\
        --text "A controller shall record the decision."
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

from bpc_hybrid.extractor import extract_rule_first
from bpc_hybrid.fallback import FallbackRequest
from bpc_hybrid.llm_client import (
    LLMClientError,
    LLMFallbackAdapter,
    LLMResponse,
    MockLLMTransport,
    make_schema_valid_mock_response_json,
)
from bpc_hybrid.llm_config import ALLOWED_PROVIDERS, LLMConfig, LLMConfigError, load_project_env_file


# ---------------------------------------------------------------------------
# error helper
# ---------------------------------------------------------------------------

def _error(
    error_type: str,
    message: str,
    *,
    real_api_call_performed: bool = False,
    raw_response_saved: bool = False,
    secret_redacted: bool = True,
) -> str:
    """Return a JSON error line (does **not** print raw secrets)."""
    return json.dumps(
        {
            "error": True,
            "error_type": error_type,
            "message": message,
            "real_api_call_performed": real_api_call_performed,
            "raw_response_saved": raw_response_saved,
            "secret_redacted": secret_redacted,
        }
    )


# ---------------------------------------------------------------------------
# success helper
# ---------------------------------------------------------------------------

def _success(
    *,
    source_id: str,
    provider: str,
    model: str,
    fallback_triggered: bool,
    schema_valid: bool,
    output: dict | None,
) -> str:
    """Return a JSON success line (no raw secrets)."""
    return json.dumps(
        {
            "run_type": "single_sample_llm_dry_run",
            "dataset_type": "synthetic_or_user_provided_single_sample",
            "source_id": source_id,
            "provider": provider,
            "model": model,
            "fallback_triggered": fallback_triggered,
            "schema_valid": schema_valid,
            "real_api_call_performed": False,
            "raw_response_saved": False,
            "secret_redacted": True,
            "output": output if output is not None else {},
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# JSON-safe ArgumentParser
# ---------------------------------------------------------------------------

class JsonArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that emits JSON error envelopes instead of usage text."""

    def error(self, message: str) -> None:
        print(
            _error(
                "DryRunError",
                f"CLI argument error: {message}",
            ),
            file=self._get_stderr(),
        )
        raise SystemExit(2)

    def _get_stderr(self):
        """Return sys.stderr (avoids private-access warnings)."""
        return sys.stderr


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = JsonArgumentParser(
        description="R8 controlled single-sample LLM dry-run harness",
    )
    parser.add_argument(
        "--allow-llm",
        action="store_true",
        default=False,
        help="Explicitly allow LLM fallback (required).",
    )
    parser.add_argument(
        "--single-sample",
        action="store_true",
        default=False,
        help="Confirms single-sample mode (required).",
    )
    parser.add_argument(
        "--source-id",
        default="dry-run-sample",
        help="Source identifier for the sample.",
    )
    parser.add_argument(
        "--text",
        default=None,
        help="Source text to extract clauses from (required).",
    )
    parser.add_argument(
        "--provider",
        default="mock",
        help="LLM provider (default: mock; openai_compatible is disabled in R8).",
    )
    parser.add_argument(
        "--model",
        default="mock",
        help="Model name (default: mock).",
    )
    parser.add_argument(
        "--mock-response",
        default=None,
        help=(
            "JSON string to use as mock LLM response. "
            "If omitted, a schema-valid default is generated."
        ),
    )

    args = parser.parse_args(argv)

    # --- load project .env (R9.0) ----------------------------------------
    # System environment variables always take priority over .env.
    # Missing .env is silent — no error.
    _project_env = load_project_env_file(_PROJECT_ROOT)
    del _project_env  # not used in R8; staged for R9 real API smoke

    # --- gate: invalid provider ------------------------------------------
    if args.provider not in ALLOWED_PROVIDERS:
        print(
            _error(
                "DryRunError",
                (
                    f"Invalid provider {args.provider!r}. "
                    f"Allowed: {sorted(ALLOWED_PROVIDERS)}"
                ),
            )
        )
        return 1

    # --- gate: --allow-llm -----------------------------------------------
    if not args.allow_llm:
        print(_error("GateError", "LLM dry-run requires --allow-llm."))
        return 1

    # --- gate: --single-sample -------------------------------------------
    if not args.single_sample:
        print(_error("GateError", "LLM dry-run requires --single-sample."))
        return 1

    # --- gate: --text ----------------------------------------------------
    if not args.text:
        print(_error("GateError", "LLM dry-run requires --text with source text."))
        return 1

    # --- gate: real provider blocked in R8 -------------------------------
    if args.provider not in ("mock", "disabled"):
        print(
            _error(
                "R8GateError",
                (
                    f"Provider {args.provider!r} is not allowed in R8. "
                    f"Real LLM API execution is disabled in this stage. "
                    f"Use --provider mock for dry-run testing."
                ),
            )
        )
        return 1

    # --- build config ----------------------------------------------------
    try:
        config = LLMConfig(
            enabled=True,
            provider=args.provider,
            model=args.model,
        )
    except LLMConfigError as exc:
        print(_error("ConfigError", str(exc)))
        return 1

    # --- build mock response ---------------------------------------------
    mock_json_str: str
    if args.mock_response is not None:
        mock_json_str = args.mock_response
    else:
        mock_json_str = make_schema_valid_mock_response_json(
            args.text, args.source_id
        )

    mock_resp = LLMResponse(
        content=mock_json_str,
        provider=args.provider,
        model=args.model,
        finish_reason="stop",
    )
    transport = MockLLMTransport(fixed_response=mock_resp)

    # --- run rule-first extraction ---------------------------------------
    rule_response = extract_rule_first(args.text, source_id=args.source_id)

    # --- run LLM fallback ------------------------------------------------
    adapter = LLMFallbackAdapter(config=config, transport=transport)
    request = FallbackRequest(
        source_text=args.text,
        source_id=args.source_id,
        rule_response=rule_response,
    )

    try:
        result = adapter.complete(request)
    except Exception as exc:
        print(_error("DryRunError", f"LLM fallback execution failed: {exc}"))
        return 1

    # --- check for LLM-level errors ---------------------------------------
    if result.error is not None:
        print(
            _error(
                "DryRunError",
                f"LLM fallback did not produce a valid response: {result.error}",
            )
        )
        return 1

    # --- emit success ----------------------------------------------------
    output_dict: dict | None = None
    if result.response is not None:
        output_dict = result.response.to_dict()
    else:
        output_dict = {}

    print(
        _success(
            source_id=args.source_id,
            provider=args.provider,
            model=args.model,
            fallback_triggered=result.response is not None,
            schema_valid=result.is_valid,
            output=output_dict,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
