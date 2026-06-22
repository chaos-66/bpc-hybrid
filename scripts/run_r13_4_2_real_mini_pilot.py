"""R13.4.2 Authorized Bounded Real API Mini-pilot Runner.

Executes a bounded single-call-per-sample real API pilot over the
8 reviewed mini-gold samples from R13.3/R13.3.1. Each sample
produces a structured compliance-field prediction.

Usage::

    $env:BPC_HYBRID_DISABLE_PROJECT_ENV = "0"
    .\\.venv\\Scripts\\python.exe scripts\\run_r13_4_2_real_mini_pilot.py \\
        --candidates data/formal/processed/r13_3_candidate_samples.jsonl \\
        --gold data/formal/gold/r13_3_manual_gold_template.jsonl \\
        --predictions-out data/formal/predictions/r13_4_2_real_predictions.jsonl \\
        --max-calls 8 \\
        --execute-real-api

Safety constraints (R13.4.2):

* At most 8 real API calls (1 per sample).
* Sequential execution only — no concurrency, no batching.
* No retry, no repair call.
* No raw model response saved to disk.
* No benchmark claim, no accuracy claim, no method-validation claim.
* No Sun reproduction claim.
* Provider config read via safe ``LLMConfig.from_env()`` — never echoed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from bpc_hybrid.llm_client import (  # noqa: E402
    LLMClientError,
    LLMRequest,
    LLMResponse,
    OpenAICompatibleRequestBuilder,
    RealAPITransport,
    _extract_json_from_content,
)
from bpc_hybrid.llm_config import LLMConfig, LLMConfigError  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CALLS = 8
MAX_SAMPLES = 8

_DEFAULT_EXECUTION_CONTRACT = (
    _PROJECT_ROOT / "data" / "formal" / "metadata" / "r13_4_2_execution_contract.json"
)
_DEFAULT_AUTHORIZATION_CHECKLIST = (
    _PROJECT_ROOT / "data" / "formal" / "metadata" / "r13_4_2_authorization_checklist.json"
)

SYSTEM_PROMPT = (
    "You are extracting structured compliance fields from one legal sentence. "
    "Return JSON only. Do not include markdown. Do not include explanation. "
    "Fields: modality (obligation|prohibition|permission|definition|unknown), "
    "actor (string or null), action (string or null), condition (string or null), "
    "constraint (string or null), exception (string or null)."
)


# ---------------------------------------------------------------------------
# Authorization gate
# ---------------------------------------------------------------------------


def _check_authorization_gate(
    execution_contract_path: Path | None = None,
    authorization_checklist_path: Path | None = None,
) -> None:
    """Check the closed authorization gate before any API config load or API call.

    Raises SystemExit(1) with a JSON error if the gate is closed.

    Parameters are ONLY for internal unit testing. Production callers must
    pass ``None`` to enforce canonical tracked metadata paths.
    """
    # ---- Resolve canonical paths, with hard resolve check -----------------
    # Production: args are None → use canonical defaults → verify they resolve
    # Unit-test:  args are explicit fixture paths → skip resolve check
    _explicit_contract = execution_contract_path is not None
    _explicit_checklist = authorization_checklist_path is not None

    if execution_contract_path is None:
        execution_contract_path = _DEFAULT_EXECUTION_CONTRACT
    if authorization_checklist_path is None:
        authorization_checklist_path = _DEFAULT_AUTHORIZATION_CHECKLIST

    # Hard resolve check only when using canonical defaults (production guard)
    if not _explicit_contract:
        resolved_contract = execution_contract_path.resolve()
        canonical_contract = _DEFAULT_EXECUTION_CONTRACT.resolve()
        if resolved_contract != canonical_contract:
            raise SystemExit(
                json.dumps(
                    {
                        "status": "AUTHORIZATION_GATE_BLOCKED",
                        "error": (
                            "Execution contract path does not resolve to "
                            f"canonical tracked metadata: {canonical_contract}"
                        ),
                        "stage": "R13.4.2",
                        "real_api_call_performed": False,
                    },
                    indent=2,
                )
            )
    if not _explicit_checklist:
        resolved_checklist = authorization_checklist_path.resolve()
        canonical_checklist = _DEFAULT_AUTHORIZATION_CHECKLIST.resolve()
        if resolved_checklist != canonical_checklist:
            raise SystemExit(
                json.dumps(
                    {
                        "status": "AUTHORIZATION_GATE_BLOCKED",
                        "error": (
                            "Authorization checklist path does not resolve to "
                            f"canonical tracked metadata: {canonical_checklist}"
                        ),
                        "stage": "R13.4.2",
                        "real_api_call_performed": False,
                    },
                    indent=2,
                )
            )

    errors: list[str] = []

    # Load execution contract
    try:
        contract = json.loads(execution_contract_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        errors.append(f"Failed to load execution contract: {exc}")
        contract = {}

    # Load authorization checklist
    try:
        checklist = json.loads(authorization_checklist_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        errors.append(f"Failed to load authorization checklist: {exc}")
        checklist = {}

    if errors:
        print(
            json.dumps(
                {
                    "status": "AUTHORIZATION_GATE_BLOCKED",
                    "error": "Cannot read authorization metadata: " + "; ".join(errors),
                    "stage": "R13.4.2",
                    "real_api_call_performed": False,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)

    # ---- Check execution contract ---------------------------------------
    if contract.get("real_api_call_allowed_now") is not True:
        errors.append(
            "execution_contract.real_api_call_allowed_now is not true"
        )
    if contract.get("status") not in (
        "authorized_for_single_bounded_run",
        "executed_single_bounded_run",
    ):
        # Allow executed_single_bounded_run ONLY if re-authorized
        if contract.get("status") == "executed_single_bounded_run":
            if contract.get("real_api_call_allowed_now") is not True:
                errors.append(
                    "execution_contract previously executed — "
                    "fresh authorization required"
                )

    # ---- Check authorization checklist ----------------------------------
    if checklist.get("authorized_now") is not True:
        errors.append(
            "authorization_checklist.authorized_now is not true"
        )
    if checklist.get("authorization_status") not in (
        "authorized_for_single_bounded_run",
        "authorized_for_single_bounded_run_completed",
    ):
        if checklist.get("authorization_status") == "authorized_for_single_bounded_run_completed":
            errors.append(
                "authorization_checklist: previous authorization consumed — "
                "fresh explicit authorization required"
            )

    # ---- Check constraint alignment -------------------------------------
    contract_max = contract.get("max_real_api_calls", 0)
    if contract_max > MAX_CALLS:
        errors.append(
            f"execution_contract.max_real_api_calls {contract_max} exceeds {MAX_CALLS}"
        )
    if contract.get("retry_allowed") is not False:
        errors.append("execution_contract.retry_allowed must be false")
    if contract.get("repair_call_allowed") is not False:
        errors.append("execution_contract.repair_call_allowed must be false")
    if contract.get("batch_allowed") is not False:
        errors.append("execution_contract.batch_allowed must be false")
    if contract.get("raw_response_saved") is not False:
        errors.append("execution_contract.raw_response_saved must be false")
    if contract.get("benchmark") is not False:
        errors.append("execution_contract.benchmark must be false")
    if contract.get("method_validation") is not False:
        errors.append("execution_contract.method_validation must be false")
    if contract.get("sun_reproduction") is not False:
        errors.append("execution_contract.sun_reproduction must be false")

    # Future re-authorization requirement
    if (
        contract.get("requires_explicit_user_authorization_for_future_runs") is True
        and contract.get("real_api_call_allowed_now") is not True
    ):
        errors.append(
            "execution_contract requires fresh explicit user authorization for future runs"
        )
    if (
        checklist.get("future_real_api_runs_require_new_authorization") is True
        and checklist.get("authorized_now") is not True
    ):
        if "fresh explicit authorization required" not in " ".join(errors):
            errors.append(
                "authorization_checklist requires fresh explicit user authorization"
            )

    if errors:
        print(
            json.dumps(
                {
                    "status": "AUTHORIZATION_GATE_CLOSED",
                    "error": (
                        "Authorization gate is closed. Fresh explicit authorization "
                        "and updated execution contract are required before another "
                        "real API run. Reasons: " + "; ".join(errors)
                    ),
                    "stage": "R13.4.2",
                    "real_api_call_performed": False,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# JSON-safe ArgumentParser
# ---------------------------------------------------------------------------


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(
            json.dumps(
                {"error": f"CLI argument error: {message}", "stage": "R13.4.2"},
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)


# ---------------------------------------------------------------------------
# JSONL helpers
# ---------------------------------------------------------------------------


def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(json.loads(stripped))
    return records


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Parse and validate LLM compliance JSON
# ---------------------------------------------------------------------------

_VALID_MODALITIES = {"obligation", "prohibition", "permission", "definition", "unknown"}
_REQUIRED_PRED_KEYS = {"modality", "actor", "action", "condition", "constraint", "exception"}


def _parse_compliance_json(content: str) -> dict | None:
    """Parse LLM output as a compliance-field dict. Returns None if invalid."""
    clean = _extract_json_from_content(content)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    # Check all required keys present
    pred_keys = set(data.keys())
    if not _REQUIRED_PRED_KEYS.issubset(pred_keys):
        return None
    # Validate modality
    modality = data.get("modality")
    if not isinstance(modality, str) or modality.lower().strip() not in _VALID_MODALITIES:
        return None
    # Normalize: ensure all string fields are str or None
    result: dict = {}
    for key in _REQUIRED_PRED_KEYS:
        val = data.get(key)
        if val is None:
            result[key] = None
        elif isinstance(val, str) and val.strip() == "":
            result[key] = None
        elif isinstance(val, str):
            result[key] = val.strip()
        else:
            result[key] = str(val)
    return result


# ---------------------------------------------------------------------------
# Build a structured prediction record
# ---------------------------------------------------------------------------


def _empty_prediction(provider: str, model: str) -> dict:
    return {
        "modality": None,
        "actor": None,
        "action": None,
        "condition": None,
        "constraint": None,
        "exception": None,
    }


def _build_prediction_record(
    sample_id: str,
    source_id: str,
    predicted: dict | None,
    provider: str,
    model: str,
    real_api_call_performed: bool,
    attempt_count: int,
    duration_ms: float,
    error_category: str | None,
) -> dict:
    """Build a structured prediction record per R13.4.1 schema."""
    pred = predicted if predicted else _empty_prediction(provider, model)
    schema_valid = predicted is not None
    return {
        "sample_id": sample_id,
        "source_id": source_id,
        "predicted": pred,
        "runtime": {
            "provider": provider,
            "model": model,
            "real_api_call_performed": real_api_call_performed,
            "raw_response_saved": False,
            "attempt_count": attempt_count,
            "duration_ms": round(duration_ms, 3),
            "error_category": error_category,
        },
        "schema_valid": schema_valid,
    }


# ---------------------------------------------------------------------------
# Single sample execution
# ---------------------------------------------------------------------------


def _execute_one_sample(
    sample: dict,
    transport: RealAPITransport,
    provider: str,
    model: str,
    timeout_seconds: float,
) -> dict:
    """Execute one sample: build prompt, call LLM, parse, return prediction record."""
    sample_id = sample.get("sample_id", "unknown")
    source_id = sample.get("source_id", "unknown")
    text = sample.get("text", "")

    user_prompt = (
        f"Extract structured compliance fields from this legal sentence.\n\n"
        f"Sentence: {text}\n\n"
        f"Return ONLY a JSON object with keys: modality, actor, action, "
        f"condition, constraint, exception."
    )

    request = LLMRequest(
        source_id=source_id,
        source_text=text,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema_name="ComplianceFieldPrediction",
    )

    t0 = time.monotonic()
    try:
        response = transport.send(request)
        duration_ms = (time.monotonic() - t0) * 1000.0

        # Parse the LLM response
        predicted = _parse_compliance_json(response.content)
        if predicted is None:
            # LLM returned valid HTTP but non-parseable JSON
            return _build_prediction_record(
                sample_id=sample_id,
                source_id=source_id,
                predicted=None,
                provider=provider,
                model=model,
                real_api_call_performed=True,
                attempt_count=1,
                duration_ms=duration_ms,
                error_category="schema_invalid",
            )

        return _build_prediction_record(
            sample_id=sample_id,
            source_id=source_id,
            predicted=predicted,
            provider=provider,
            model=model,
            real_api_call_performed=True,
            attempt_count=1,
            duration_ms=duration_ms,
            error_category=None,
        )

    except LLMClientError as exc:
        duration_ms = (time.monotonic() - t0) * 1000.0
        err_msg = str(exc).lower()

        if "timeout" in err_msg:
            error_category = "api_timeout"
        elif "dns" in err_msg or "connection" in err_msg or "network" in err_msg:
            error_category = "api_error"
        elif "ssl" in err_msg:
            error_category = "api_error"
        elif "http status" in err_msg:
            error_category = "api_error"
        else:
            error_category = "api_error"

        return _build_prediction_record(
            sample_id=sample_id,
            source_id=source_id,
            predicted=None,
            provider=provider,
            model=model,
            real_api_call_performed=True,
            attempt_count=1,
            duration_ms=duration_ms,
            error_category=error_category,
        )

    except Exception:
        duration_ms = (time.monotonic() - t0) * 1000.0
        return _build_prediction_record(
            sample_id=sample_id,
            source_id=source_id,
            predicted=None,
            provider=provider,
            model=model,
            real_api_call_performed=True,
            attempt_count=1,
            duration_ms=duration_ms,
            error_category="api_error",
        )


# ---------------------------------------------------------------------------
# Pre-flight validation
# ---------------------------------------------------------------------------


def _validate_inputs(candidates: list[dict], gold: list[dict]) -> None:
    """Validate inputs before making any API call."""
    if len(candidates) > MAX_SAMPLES:
        raise ValueError(
            f"Candidate count {len(candidates)} exceeds max {MAX_SAMPLES}"
        )
    if len(gold) != len(candidates):
        raise ValueError(
            f"Gold count {len(gold)} != candidate count {len(candidates)}"
        )
    if len(candidates) == 0:
        raise ValueError("No samples to process")

    # Check duplicate sample_ids
    cand_ids = [c.get("sample_id", "") for c in candidates]
    if len(cand_ids) != len(set(cand_ids)):
        raise ValueError("Duplicate sample_id in candidates")

    gold_ids = [g.get("sample_id", "") for g in gold]
    if len(gold_ids) != len(set(gold_ids)):
        raise ValueError("Duplicate sample_id in gold")

    # Check sample_id match
    if set(cand_ids) != set(gold_ids):
        raise ValueError("Candidate and gold sample_ids do not match")

    # Check gold annotation_status
    for g in gold:
        if g.get("annotation_status", "") != "reviewed_gold":
            raise ValueError(
                f"Gold sample {g.get('sample_id')} is not reviewed_gold: "
                f"{g.get('annotation_status')}"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = _JsonArgumentParser(
        description="R13.4.2 Authorized Bounded Real API Mini-pilot Runner",
    )
    parser.add_argument(
        "--candidates",
        required=True,
        help="Path to candidate samples JSONL",
    )
    parser.add_argument(
        "--gold",
        required=True,
        help="Path to gold annotations JSONL",
    )
    parser.add_argument(
        "--predictions-out",
        required=True,
        help="Path for output prediction JSONL",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=8,
        help="Maximum real API calls (max 8)",
    )
    parser.add_argument(
        "--execute-real-api",
        action="store_true",
        default=False,
        help="Execute real API calls (required for real execution)",
    )
    args = parser.parse_args()

    # ---- Gate: max-calls ------------------------------------------------
    if args.max_calls > MAX_CALLS:
        print(
            json.dumps(
                {
                    "error": f"--max-calls {args.max_calls} exceeds maximum {MAX_CALLS}",
                    "stage": "R13.4.2",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)

    # ---- Gate: require --execute-real-api -------------------------------
    if not args.execute_real_api:
        print(
            json.dumps(
                {
                    "error": (
                        "R13.4.2 requires --execute-real-api for real API execution. "
                        "This stage must be explicitly authorized."
                    ),
                    "stage": "R13.4.2",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)

    # ---- Gate: authorization contract/checklist (canonical only) --------
    _check_authorization_gate()

    # ---- Load inputs ----------------------------------------------------
    candidates_path = Path(args.candidates)
    gold_path = Path(args.gold)
    predictions_path = Path(args.predictions_out)

    candidates = _read_jsonl(candidates_path)
    gold = _read_jsonl(gold_path)

    # ---- Validate inputs ------------------------------------------------
    try:
        _validate_inputs(candidates, gold)
    except ValueError as exc:
        print(
            json.dumps(
                {"error": str(exc), "stage": "R13.4.2"},
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)

    # ---- Load config ----------------------------------------------------
    try:
        config = LLMConfig.from_env(project_root=_PROJECT_ROOT)
    except LLMConfigError as exc:
        print(
            json.dumps(
                {
                    "status": "CONFIG_BLOCKED",
                    "error": f"LLMConfig.from_env() error: {exc}",
                    "stage": "R13.4.2",
                    "real_api_call_performed": False,
                },
                indent=2,
            )
        )
        raise SystemExit(1)

    if not config.enabled:
        print(
            json.dumps(
                {
                    "status": "CONFIG_BLOCKED",
                    "error": "LLM fallback is disabled (config.enabled=False)",
                    "stage": "R13.4.2",
                    "real_api_call_performed": False,
                },
                indent=2,
            )
        )
        raise SystemExit(1)

    if not config.api_key:
        print(
            json.dumps(
                {
                    "status": "CONFIG_BLOCKED",
                    "error": "LLM config missing api_key",
                    "stage": "R13.4.2",
                    "real_api_call_performed": False,
                },
                indent=2,
            )
        )
        raise SystemExit(1)

    # ---- Build transport ------------------------------------------------
    try:
        transport = RealAPITransport(config, timeout_seconds=config.timeout_seconds)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "CONFIG_BLOCKED",
                    "error": f"RealAPITransport init error: {exc}",
                    "stage": "R13.4.2",
                    "real_api_call_performed": False,
                },
                indent=2,
            )
        )
        raise SystemExit(1)

    provider = config.provider
    model = config.model

    print(
        f"R13.4.2 real mini-pilot: {len(candidates)} samples, "
        f"max {args.max_calls} calls, provider={provider}, model={model}"
    )

    # ---- Execute samples (sequential, one per sample) -------------------
    predictions: list[dict] = []
    call_count = 0
    t_start = time.monotonic()

    for i, sample in enumerate(candidates):
        if call_count >= args.max_calls:
            print(f"Stop: reached max calls limit ({args.max_calls})")
            break

        sample_id = sample.get("sample_id", f"unknown_{i}")
        print(f"  [{i+1}/{len(candidates)}] {sample_id} ... ", end="", flush=True)

        call_count += 1
        prediction = _execute_one_sample(
            sample=sample,
            transport=transport,
            provider=provider,
            model=model,
            timeout_seconds=config.timeout_seconds,
        )
        predictions.append(prediction)

        if prediction["schema_valid"]:
            print("OK")
        else:
            ec = prediction["runtime"].get("error_category", "unknown")
            print(f"FAILED ({ec})")

    t_end = time.monotonic()

    # ---- Write predictions ----------------------------------------------
    _write_jsonl(predictions_path, predictions)

    schema_valid_count = sum(1 for p in predictions if p["schema_valid"])

    print(
        f"\nR13.4.2 complete: {call_count} calls attempted, "
        f"{schema_valid_count} schema-valid, "
        f"{(t_end - t_start):.1f}s elapsed"
    )
    print(f"Predictions written to {predictions_path}")


if __name__ == "__main__":
    main()
