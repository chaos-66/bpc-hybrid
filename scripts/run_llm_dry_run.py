"""R9 Controlled Single-Sample LLM Dry-Run Harness.

Provides a safety-gated CLI for single-sample LLM dry-runs.  In R9,
real API execution is **opt-in only** via explicit flags.  Mock
provider runs require ``--allow-llm`` and ``--single-sample``.  Real
API runs additionally require ``--execute-real-api``,
``--confirm-real-api-single-sample``, and
``BPC_HYBRID_R9_REAL_RUN_CONFIRMED=YES_SINGLE_SAMPLE_ONLY`` in the
environment.  All output is JSON.  No raw secrets, no raw response
storage, no batch mode.

Usage (mock)::

    .\\.venv\\Scripts\\python.exe scripts\\run_llm_dry_run.py \\
        --allow-llm --single-sample \\
        --source-id dry001 \\
        --text "A controller shall record the decision."

Usage (real API smoke, R9)::

    .\\.venv\\Scripts\\python.exe scripts\\run_llm_dry_run.py \\
        --allow-llm --single-sample \\
        --execute-real-api --confirm-real-api-single-sample \\
        --provider openai_compatible \\
        --source-id r9_real_smoke_001 \\
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
    RealAPITransport,
    make_schema_valid_mock_response_json,
)
from bpc_hybrid.llm_config import (
    ALLOWED_PROVIDERS,
    LLMConfig,
    LLMConfigError,
    load_project_env_file,
    project_env_disabled,
)


# ---------------------------------------------------------------------------
# status classification helper (R9.7.1 — extractable pure function for testing)
# ---------------------------------------------------------------------------

_SINGLE_SAMPLE_API_RETURNED_SCHEMA_INVALID = "SINGLE_SAMPLE_API_RETURNED_SCHEMA_INVALID"
_SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED = "SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED"


def classify_real_api_error_status(error_message: str) -> str:
    """Classify a real-API error message into a status string.

    This is a pure function with no side effects — safe to test without
    network, subprocess, or real API access.

    Returns:
        ``SINGLE_SAMPLE_API_RETURNED_SCHEMA_INVALID`` if the error
        indicates a parse/schema/conversion failure (e.g. LLM returned
        fields not matching ``MultiClauseExtractionResponse``).

        ``SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED`` for all
        transport/network/timeout/HTTP/DNS errors.
    """
    _lower = error_message.lower()
    # Schema-invalid indicators: "parse error", "schema", "cannot convert"
    if ("parse error" in _lower
            or "cannot convert" in _lower
            or ("schema" in _lower and ("invalid" in _lower or "mismatch" in _lower or "unknown" in _lower))):
        return _SINGLE_SAMPLE_API_RETURNED_SCHEMA_INVALID
    return _SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED


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
    status: str | None = None,
) -> str:
    """Return a JSON error line (does **not** print raw secrets)."""
    result: dict[str, object] = {
        "error": True,
        "error_type": error_type,
        "message": message,
        "real_api_call_performed": real_api_call_performed,
        "raw_response_saved": raw_response_saved,
        "secret_redacted": secret_redacted,
    }
    if status is not None:
        result["status"] = status
    return json.dumps(result)


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
    real_api_call_performed: bool = False,
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
            "real_api_call_performed": real_api_call_performed,
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
        description="R9 controlled single-sample LLM dry-run harness",
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
        help="LLM provider (mock, openai_compatible, or disabled).",
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
    parser.add_argument(
        "--execute-real-api",
        action="store_true",
        default=False,
        help="Execute a real API call (R9 gate — requires all confirm flags).",
    )
    parser.add_argument(
        "--confirm-real-api-single-sample",
        action="store_true",
        default=False,
        help="Confirm real API single-sample execution (R9 gate).",
    )
    parser.add_argument(
        "--no-project-env",
        action="store_true",
        default=False,
        help="Disable reading project-root .env (for audits/tests).",
    )

    args = parser.parse_args(argv)

    # --- load project .env (R9.0) ----------------------------------------
    # System environment variables always take priority over .env.
    # Missing .env is silent — no error.
    # Skip when --no-project-env is passed or BPC_HYBRID_DISABLE_PROJECT_ENV
    # is set in the system environment.
    if not args.no_project_env and not project_env_disabled():
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

    # --- gate: R9 real API gates for openai_compatible -------------------
    real_api_requested = False
    if args.provider == "openai_compatible":
        # R9.0 gate: --execute-real-api required
        if not args.execute_real_api:
            print(
                _error(
                    "R9GateError",
                    "openai_compatible provider requires --execute-real-api "
                    "for real API execution. Use --provider mock for "
                    "dry-run testing without network.",
                )
            )
            return 1

        # R9.0 gate: --confirm-real-api-single-sample required
        if not args.confirm_real_api_single_sample:
            print(
                _error(
                    "R9GateError",
                    "Real API execution requires "
                    "--confirm-real-api-single-sample to confirm "
                    "single-sample mode.",
                )
            )
            return 1

        # R9.0 gate: BPC_HYBRID_R9_REAL_RUN_CONFIRMED env var
        import os as _os_r9
        r9_confirmed = _os_r9.environ.get(
            "BPC_HYBRID_R9_REAL_RUN_CONFIRMED", ""
        ).strip()
        if r9_confirmed != "YES_SINGLE_SAMPLE_ONLY":
            print(
                _error(
                    "R9GateError",
                    "BPC_HYBRID_R9_REAL_RUN_CONFIRMED must be set to "
                    "YES_SINGLE_SAMPLE_ONLY in the environment.",
                )
            )
            return 1

        # R9.0: build config from env (--no-project-env still respected)
        from bpc_hybrid.llm_config import LLMConfig as _LC
        try:
            config = _LC.from_env(
                project_root=_PROJECT_ROOT if not args.no_project_env else None,
            )
        except LLMConfigError as exc:
            print(
                _error(
                    "R9RealAPIConfigError",
                    f"Real API config error: {exc}",
                )
            )
            return 1

        # R9.0 gate: must have API key, base_url, model
        # Diagnostic existence checks: presence yes/no only — never print values
        missing: list[str] = []
        diag: dict[str, str] = {}

        diag["BPC_HYBRID_LLM_API_KEY"] = (
            "present" if config.api_key else "missing"
        )
        if not config.api_key:
            missing.append("BPC_HYBRID_LLM_API_KEY")

        diag["BPC_HYBRID_LLM_BASE_URL"] = (
            "present" if config.base_url else "missing"
        )
        if not config.base_url:
            missing.append("BPC_HYBRID_LLM_BASE_URL")

        diag["BPC_HYBRID_LLM_MODEL"] = (
            "present" if (config.model and config.model != "mock") else "missing_or_mock"
        )
        if not config.model or config.model == "mock":
            missing.append("BPC_HYBRID_LLM_MODEL")

        if missing:
            print(
                _error(
                    "R9RealAPIConfigError",
                    f"Missing required config: {', '.join(sorted(missing))}.",
                    status="SKIPPED_NO_API_KEY_OR_CONFIG",
                )
            )
            return 1

        # R9.0 gate: provider must be openai_compatible in config
        if config.provider != "openai_compatible":
            print(
                _error(
                    "R9RealAPIConfigError",
                    f"Config provider is {config.provider!r}, expected "
                    f"'openai_compatible'. Set BPC_HYBRID_LLM_PROVIDER="
                    f"openai_compatible in .env.",
                )
            )
            return 1

        config.enabled = True
        real_api_requested = True

    else:
        # --- mock / disabled path (same as R8) ---------------------------
        try:
            config = LLMConfig(
                enabled=True,
                provider=args.provider,
                model=args.model,
            )
        except LLMConfigError as exc:
            print(_error("ConfigError", str(exc)))
            return 1

    # --- build transport -------------------------------------------------
    transport: MockLLMTransport | RealAPITransport
    if real_api_requested:
        transport = RealAPITransport(config, timeout_seconds=config.timeout_seconds)
    else:
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
        print(
            _error(
                "DryRunError",
                f"LLM fallback execution failed: {exc}",
                real_api_call_performed=real_api_requested,
                status=(
                    "SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED"
                    if real_api_requested
                    else None
                ),
            )
        )
        return 1

    # --- check for LLM-level errors ---------------------------------------
    if result.error is not None:
        # R9.7.1: use extracted helper for safe offline testing
        _status = classify_real_api_error_status(result.error)
        print(
            _error(
                "DryRunError",
                f"LLM fallback did not produce a valid response: {result.error}",
                real_api_call_performed=real_api_requested,
                status=_status if real_api_requested else None,
            )
        )
        return 1

    # --- emit success ----------------------------------------------------
    output_dict: dict | None = None
    if result.response is not None:
        output_dict = result.response.to_dict()
    else:
        output_dict = {}

    model_used = args.model
    if real_api_requested and result.response is not None:
        model_used = config.model

    print(
        _success(
            source_id=args.source_id,
            provider=args.provider,
            model=model_used,
            fallback_triggered=result.response is not None,
            schema_valid=result.is_valid,
            output=output_dict,
            real_api_call_performed=real_api_requested,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
