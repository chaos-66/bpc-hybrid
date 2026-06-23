"""R14.4 Bounded Rule+LLM-assisted Real API Pilot Runner.

Executes a bounded single-call-per-sample real API pilot over the
24 R14.1 draft mini-gold samples using Prompt B (few_shot_extraction).

Usage::

    $env:BPC_HYBRID_DISABLE_PROJECT_ENV = "0"
    .venv/Scripts/python.exe scripts/run_r14_4_rule_plus_llm_real_pilot.py \
        --execute-real-api --max-api-calls 24

Safety constraints (R14.4):
* At most 24 real API calls (1 per sample).
* Sequential execution only — no concurrency, no batching.
* No retry, no repair call.
* No raw model response saved to disk.
* No benchmark claim, no accuracy claim, no method-validation claim.
* No Sun reproduction claim, no LLM superiority claim.
* Provider config read via safe LLMConfig.from_env() — never echoed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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
    OpenAICompatibleRequestBuilder,
    RealAPITransport,
    _extract_json_from_content,
)
from bpc_hybrid.llm_config import LLMConfig, LLMConfigError  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
STAGE = "R14.4"
METHOD = "rule_plus_llm_assisted"
PROMPT_ID = "r13_6_prompt_B"
MAX_CALLS = 24
MAX_SAMPLES = 24

_CANDIDATES_PATH = _PROJECT_ROOT / "data" / "formal" / "r14_controlled" / "r14_1_candidate_samples.jsonl"
_PREDICTIONS_OUT = _PROJECT_ROOT / "data" / "formal" / "predictions" / "r14_4_rule_plus_llm_predictions.jsonl"
_PROMPT_B_PATH = _PROJECT_ROOT / "prompts" / "r13_6" / "few_shot_extraction_prompt.md"
_PROMPT_SNAPSHOT_PATH = _PROJECT_ROOT / "data" / "formal" / "metadata" / "r14_3_prompt_snapshot.json"

_REQUIRED_PRED_KEYS = {"modality", "actor", "action", "condition", "constraint", "exception"}
_VALID_MODALITIES = {"obligation", "prohibition", "permission", "definition", "unknown"}


def _load_prompt_b() -> str:
    """Load Prompt B (few_shot_extraction) from disk."""
    raw = _PROMPT_B_PATH.read_text(encoding="utf-8")
    lines = raw.splitlines()
    start_idx = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("## Instructions"):
            start_idx = i
            break
    prompt_body = "\n".join(lines[start_idx:])
    return prompt_body.strip()


# Cache the system prompt
SYSTEM_PROMPT = _load_prompt_b()


# ---------------------------------------------------------------------------
# Prompt snapshot verification
# ---------------------------------------------------------------------------

def _verify_prompt_snapshot() -> None:
    """Verify prompt SHA256 and size match R14.3 snapshot."""
    snapshot = json.loads(_PROMPT_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    prompt_bytes = _PROMPT_B_PATH.read_bytes()
    actual_sha256 = hashlib.sha256(prompt_bytes).hexdigest()
    actual_size = len(prompt_bytes)

    expected_sha256 = snapshot.get("prompt_sha256", "")
    expected_size = snapshot.get("prompt_size_bytes", 0)

    if actual_sha256 != expected_sha256:
        raise SystemExit(
            json.dumps({
                "status": "PROMPT_SNAPSHOT_MISMATCH",
                "error": f"Prompt SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}",
                "stage": STAGE,
                "real_api_call_performed": False,
            }, indent=2)
        )

    if actual_size != expected_size:
        raise SystemExit(
            json.dumps({
                "status": "PROMPT_SNAPSHOT_MISMATCH",
                "error": f"Prompt size mismatch: expected {expected_size}, got {actual_size}",
                "stage": STAGE,
                "real_api_call_performed": False,
            }, indent=2)
        )


# ---------------------------------------------------------------------------
# JSON helpers
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Parse LLM compliance JSON
# ---------------------------------------------------------------------------

def _parse_compliance_json(content: str) -> dict | None:
    """Parse LLM output as a compliance-field dict. Returns None if invalid."""
    clean = _extract_json_from_content(content)
    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    pred_keys = set(data.keys())
    if not _REQUIRED_PRED_KEYS.issubset(pred_keys):
        return None
    modality = data.get("modality")
    if not isinstance(modality, str) or modality.lower().strip() not in _VALID_MODALITIES:
        # Accept but flag; still parse other fields
        pass
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
# Build structured prediction record
# ---------------------------------------------------------------------------

def _empty_fields() -> dict:
    return {
        "modality": {"value": None},
        "actor": {"value": None},
        "action": {"value": None},
        "condition": {"value": None},
        "constraint": {"value": None},
        "exception": {"value": None},
    }


def _build_prediction_record(
    sample_id: str,
    predicted: dict | None,
    provider: str,
    model: str,
    error_category: str | None,
    duration_ms: float,
) -> dict:
    """Build a structured prediction record for R14.4."""
    if predicted:
        prediction_fields = {}
        for key in _REQUIRED_PRED_KEYS:
            prediction_fields[key] = {"value": predicted.get(key)}
    else:
        prediction_fields = _empty_fields()

    llm_used = error_category is None  # If no error, LLM was used successfully
    api_used = True  # API was attempted

    return {
        "sample_id": sample_id,
        "method": METHOD,
        "selected_prompt_id": PROMPT_ID,
        "prediction_fields": prediction_fields,
        "execution": {
            "llm_used": llm_used,
            "api_used": api_used,
            "network_used": True,
            "attempt_index": 1,
            "retry_used": False,
            "repair_call_used": False,
            "batch_used": False,
            "raw_response_saved": False,
            "error_category": error_category,
            "provider": provider,
            "model": model,
            "duration_ms": round(duration_ms, 3),
        },
    }


# ---------------------------------------------------------------------------
# Single sample execution
# ---------------------------------------------------------------------------

def _execute_one_sample(
    sample: dict,
    transport: RealAPITransport,
    provider: str,
    model: str,
) -> dict:
    """Execute one sample: build prompt, call LLM, parse, return prediction record."""
    sample_id = sample.get("sample_id", "unknown")
    text = sample.get("text", "")

    user_prompt = (
        f"Extract structured compliance fields from this legal sentence.\n\n"
        f"Sentence: {text}\n\n"
        f"Return ONLY a JSON object with keys: modality, actor, action, "
        f"condition, constraint, exception."
    )

    request = LLMRequest(
        source_id=sample_id,
        source_text=text,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema_name="ComplianceFieldPrediction",
    )

    t0 = time.monotonic()
    try:
        response = transport.send(request)
        duration_ms = (time.monotonic() - t0) * 1000.0

        predicted = _parse_compliance_json(response.content)
        if predicted is None:
            return _build_prediction_record(
                sample_id=sample_id,
                predicted=None,
                provider=provider,
                model=model,
                error_category="schema_invalid",
                duration_ms=duration_ms,
            )

        return _build_prediction_record(
            sample_id=sample_id,
            predicted=predicted,
            provider=provider,
            model=model,
            error_category=None,
            duration_ms=duration_ms,
        )

    except LLMClientError as exc:
        duration_ms = (time.monotonic() - t0) * 1000.0
        err_msg = str(exc).lower()
        if "timeout" in err_msg:
            error_category = "api_timeout"
        else:
            error_category = "api_error"
        return _build_prediction_record(
            sample_id=sample_id,
            predicted=None,
            provider=provider,
            model=model,
            error_category=error_category,
            duration_ms=duration_ms,
        )

    except Exception:
        duration_ms = (time.monotonic() - t0) * 1000.0
        return _build_prediction_record(
            sample_id=sample_id,
            predicted=None,
            provider=provider,
            model=model,
            error_category="api_error",
            duration_ms=duration_ms,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="R14.4 Rule+LLM real pilot runner")
    parser.add_argument(
        "--execute-real-api",
        action="store_true",
        help="Execute real API calls (required gate)",
    )
    parser.add_argument(
        "--max-api-calls",
        type=int,
        default=MAX_CALLS,
        help=f"Maximum API calls (default: {MAX_CALLS})",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=60.0,
        help="HTTP timeout per call in seconds (default: 60)",
    )
    args = parser.parse_args()

    # Gate: must explicitly opt in
    if not args.execute_real_api:
        sys.exit(json.dumps({
            "status": "REAL_API_NOT_ENABLED",
            "error": "Pass --execute-real-api to confirm you want real API calls.",
            "stage": STAGE,
            "real_api_call_performed": False,
        }, indent=2))

    if args.max_api_calls > MAX_CALLS:
        sys.exit(json.dumps({
            "status": "TOO_MANY_CALLS",
            "error": f"max-api-calls {args.max_api_calls} exceeds ceiling {MAX_CALLS}",
            "stage": STAGE,
            "real_api_call_performed": False,
        }, indent=2))

    # Verify prompt snapshot
    print("--- R14.4 Pre-flight ---")
    _verify_prompt_snapshot()
    print("  Prompt snapshot verified OK")

    # Load candidates
    candidates = _read_jsonl(_CANDIDATES_PATH)
    if len(candidates) != MAX_SAMPLES:
        sys.exit(json.dumps({
            "status": "BAD_INPUT",
            "error": f"Expected {MAX_SAMPLES} candidates, got {len(candidates)}",
            "stage": STAGE,
            "real_api_call_performed": False,
        }, indent=2))

    # Verify no duplicate IDs
    ids = [c["sample_id"] for c in candidates]
    if len(ids) != len(set(ids)):
        sys.exit(json.dumps({
            "status": "BAD_INPUT",
            "error": "Duplicate sample_id in candidates",
            "stage": STAGE,
            "real_api_call_performed": False,
        }, indent=2))

    # Load LLM config (pass project root so .env is loaded)
    try:
        config = LLMConfig.from_env(project_root=_PROJECT_ROOT)
    except LLMConfigError as exc:
        sys.exit(json.dumps({
            "status": "CONFIG_ERROR",
            "error": str(exc),
            "stage": STAGE,
            "real_api_call_performed": False,
        }, indent=2))

    if not config.enabled:
        sys.exit(json.dumps({
            "status": "LLM_NOT_ENABLED",
            "error": "BPC_HYBRID_LLM_ENABLED is not true",
            "stage": STAGE,
            "real_api_call_performed": False,
        }, indent=2))

    # Build transport
    transport = RealAPITransport(config, timeout_seconds=args.timeout_seconds)
    print(f"  Provider: {config.provider}")
    print(f"  Model: {config.model}")
    print(f"  Timeout: {args.timeout_seconds}s")
    print(f"  Max calls: {args.max_api_calls}")
    print(f"  Samples: {len(candidates)}")
    print("--- Starting R14.4 Rule+LLM pilot ---")

    predictions: list[dict] = []
    call_count = 0
    schema_valid_count = 0
    error_count = 0
    error_categories: dict[str, int] = {}

    for i, sample in enumerate(candidates):
        if call_count >= args.max_api_calls:
            print(f"  HALTED: reached max {args.max_api_calls} API calls")
            break

        sample_id = sample["sample_id"]
        print(f"  [{i+1}/{len(candidates)}] {sample_id} ... ", end="", flush=True)

        record = _execute_one_sample(sample, transport, config.provider, config.model)
        call_count += 1

        error_cat = record["execution"].get("error_category")
        if error_cat is None:
            schema_valid_count += 1
            print("OK")
        else:
            error_count += 1
            error_categories[error_cat] = error_categories.get(error_cat, 0) + 1
            print(f"FAILED ({error_cat})")

        predictions.append(record)

    # Write predictions
    _write_jsonl(_PREDICTIONS_OUT, predictions)

    print("--- R14.4 Complete ---")
    print(f"  API calls attempted: {call_count}")
    print(f"  Schema valid: {schema_valid_count}")
    print(f"  Errors: {error_count}")
    if error_categories:
        for cat, cnt in sorted(error_categories.items()):
            print(f"    {cat}: {cnt}")
    print(f"  Predictions written: {_PREDICTIONS_OUT}")


if __name__ == "__main__":
    main()
