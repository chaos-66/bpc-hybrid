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

SYSTEM_PROMPT = (
    "You are extracting structured compliance fields from one legal sentence. "
    "Return JSON only. Do not include markdown. Do not include explanation. "
    "Fields: modality (obligation|prohibition|permission|definition|unknown), "
    "actor (string or null), action (string or null), condition (string or null), "
    "constraint (string or null), exception (string or null)."
)

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
