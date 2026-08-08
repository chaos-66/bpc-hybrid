"""S2.8D-R5: frozen Gold-blind small H1 pilot plan and early-stop contract.

Pure, offline, deterministic helpers for freezing and binding a
10-call H1 pilot.  The module never loads ``.env``, never calls any
LLM/API, never touches Gold or Layer E, and never contains source text,
prompt text, patch content, responses, or credentials -- only hashes,
IDs, offsets, counts, and booleans.

Two responsibilities:

1. Frozen-plan contract (``load_frozen_plan`` / ``validate_structure`` /
   ``verify_historical_keys_sha``): a machine-readable
   ``h1_small_pilot_plan@1.0.0`` config pins B0 hashes, prompt, model,
   budget, historical real-called plan keys, and exactly 10 selected
   plans with 10 distinct samples.  Any structural inconsistency is
   reported as a list of error strings and the caller must fail closed.

2. Early-stop contract (``evaluate_early_stop``): a pure decision
   function for the future real pilot.  Provider model mismatch,
   capture binding failure, budget/count violation, plan-key mismatch,
   or 3 consecutive transport/extraction failures abort the remaining
   calls; patch-level scientific rejections never abort the run.

The runner owns the semantic binding against the current B0 batch,
prompt, repair plans, and context audits; this module only checks
shapes, hashes, and the frozen decision data.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "h1_small_pilot_plan@1.0.0"
TASK_ID = "S2.8D-R5"
REQUIRED_MODEL = "deepseek-v4-pro"
EXPECTED_PLAN_COUNT = 10
EXPECTED_HARD_CALL_CAP = 10
EXPECTED_RETRY_PER_PLAN = 0
EXPECTED_MAX_CALLS_PER_PLAN = 1
CONSECUTIVE_FAILURE_LIMIT = 3

EARLY_STOP_NOT_CALLED = "pilot_early_stop_not_called"

EARLY_STOP_REASON_PROVIDER_MODEL = "provider_model_mismatch"
EARLY_STOP_REASON_CAPTURE = "capture_binding_failure"
EARLY_STOP_REASON_BUDGET = "authorization_or_call_count_violation"
EARLY_STOP_REASON_PLAN_KEY = "plan_key_mismatch"
EARLY_STOP_REASON_CONSECUTIVE = "consecutive_transport_or_extraction_failures"

EARLY_STOP_REASONS = frozenset(
    {
        EARLY_STOP_REASON_PROVIDER_MODEL,
        EARLY_STOP_REASON_CAPTURE,
        EARLY_STOP_REASON_BUDGET,
        EARLY_STOP_REASON_PLAN_KEY,
        EARLY_STOP_REASON_CONSECUTIVE,
    }
)

# Contracted early-stop policy (frozen in the config; the runner mirrors it).
DEFAULT_EARLY_STOP_POLICY: dict[str, Any] = {
    "provider_model_mismatch": "abort_remaining",
    "capture_binding_failure": "abort_remaining",
    "authorization_or_call_count_violation": "abort_remaining",
    "consecutive_transport_or_extraction_failures": 3,
    "patch_level_rejection": "record_and_continue",
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def json_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def plan_key(entry: Mapping[str, Any]) -> tuple[str, str]:
    return str(entry["sample_id"]), str(entry["clause_id"])


def plan_key_str(entry: Mapping[str, Any]) -> str:
    sample_id, clause_id = plan_key(entry)
    return f"{sample_id}/{clause_id}"


def selected_plan_keys_sha256(entries: Sequence[Mapping[str, Any]]) -> str:
    keys = sorted(plan_key_str(entry) for entry in entries)
    return sha256_text("\n".join(keys))


def historical_plan_keys_sha256(keys: Iterable[str]) -> str:
    return sha256_text("\n".join(sorted(set(keys))))


def _is_hex64(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _error_list(config: Mapping[str, Any]) -> list[str]:
    """Return structural validation errors (empty list == valid)."""
    errors: list[str] = []

    def need(path: str, cond: bool, message: str | None = None) -> None:
        if not cond:
            errors.append(message or f"missing/invalid field: {path}")

    if config.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}")
    need("task_id", isinstance(config.get("task_id"), str) and bool(config["task_id"]))
    need("development_only", config.get("development_only") is True)
    need("gold_visible", config.get("gold_visible") is False)
    need("model", config.get("model") == REQUIRED_MODEL)
    need("prompt_variant", isinstance(config.get("prompt_variant"), str) and bool(config["prompt_variant"]))
    need("prompt_sha256", _is_hex64(config.get("prompt_sha256")))

    b0 = config.get("b0")
    if not isinstance(b0, Mapping):
        errors.append("missing b0 section")
    else:
        for key in ("attempts_path", "attempts_sha256", "manifest_path", "manifest_sha256"):
            need(f"b0.{key}", _is_hex64(b0.get(key)) if key.endswith("_sha256") else (isinstance(b0.get(key), str) and bool(b0[key])))

    policy = config.get("selection_policy")
    if not isinstance(policy, Mapping):
        errors.append("missing selection_policy section")
    else:
        need("selection_policy.selected_plan_count", policy.get("selected_plan_count") == EXPECTED_PLAN_COUNT)
        need("selection_policy.exclude_any_historical_real_call", policy.get("exclude_any_historical_real_call") is True)
        need("selection_policy.max_one_plan_per_sample", policy.get("max_one_plan_per_sample") is True)

    budget = config.get("budget")
    if not isinstance(budget, Mapping):
        errors.append("missing budget section")
    else:
        need("budget.hard_api_call_cap", budget.get("hard_api_call_cap") == EXPECTED_HARD_CALL_CAP)
        need("budget.retry_per_plan", budget.get("retry_per_plan") == EXPECTED_RETRY_PER_PLAN)
        need("budget.max_calls_per_plan", budget.get("max_calls_per_plan") == EXPECTED_MAX_CALLS_PER_PLAN)
        need("budget.pilot_only", budget.get("pilot_only") is True)
        need("budget.full_pilot", budget.get("full_pilot") is False)

    early = config.get("early_stop_policy")
    if not isinstance(early, Mapping):
        errors.append("missing early_stop_policy section")
    else:
        for key, expected in DEFAULT_EARLY_STOP_POLICY.items():
            need(f"early_stop_policy.{key}", early.get(key) == expected)

    hist = config.get("historical_calls")
    if not isinstance(hist, Mapping):
        errors.append("missing historical_calls section")
    else:
        need("historical_calls.real_call_count", isinstance(hist.get("real_call_count"), int) and hist.get("real_call_count") >= 0)
        need("historical_calls.unique_plan_key_count", isinstance(hist.get("unique_plan_key_count"), int) and hist.get("unique_plan_key_count") >= 0)
        need("historical_calls.plan_keys_sha256", _is_hex64(hist.get("plan_keys_sha256")))
        keys = hist.get("plan_keys")
        if not isinstance(keys, list) or not all(isinstance(k, str) and k for k in keys):
            errors.append("historical_calls.plan_keys must be a non-empty list of sample/clause strings")
        elif len(set(keys)) != len(keys):
            errors.append("historical_calls.plan_keys contains duplicates")
        elif hist.get("plan_keys_sha256") != historical_plan_keys_sha256(keys):
            errors.append("historical_calls.plan_keys_sha256 does not match the embedded plan_keys list")

    entries = config.get("selected_plans")
    if not isinstance(entries, list):
        errors.append("selected_plans must be a list")
        return errors
    if len(entries) != EXPECTED_PLAN_COUNT:
        errors.append(f"selected_plans must contain exactly {EXPECTED_PLAN_COUNT} entries")
    for index, entry in enumerate(entries):
        prefix = f"selected_plans[{index}]"
        if not isinstance(entry, Mapping):
            errors.append(f"{prefix} must be an object")
            continue
        need(f"{prefix}.sample_id", isinstance(entry.get("sample_id"), str) and bool(entry["sample_id"]))
        need(f"{prefix}.clause_id", isinstance(entry.get("clause_id"), str) and bool(entry["clause_id"]))
        need(f"{prefix}.clause_index", isinstance(entry.get("clause_index"), int) and not isinstance(entry.get("clause_index"), bool))
        need(f"{prefix}.risk_score", isinstance(entry.get("risk_score"), int) and not isinstance(entry.get("risk_score"), bool))
        need(f"{prefix}.repair_fields", isinstance(entry.get("repair_fields"), list) and all(isinstance(f, str) for f in entry["repair_fields"]))
        need(f"{prefix}.reasons", isinstance(entry.get("reasons"), list) and all(isinstance(r, str) for r in entry["reasons"]))
        for hkey in ("b0_prediction_sha256", "clause_identity_hash", "rendered_masked_context_hash", "prompt_sha256"):
            need(f"{prefix}.{hkey}", _is_hex64(entry.get(hkey)))
        need(f"{prefix}.execution_order", isinstance(entry.get("execution_order"), int) and not isinstance(entry.get("execution_order"), bool))
        need(f"{prefix}.historical_called", entry.get("historical_called") is False)

    if not errors:
        orders = [e.get("execution_order") for e in entries if isinstance(e, Mapping)]
        if orders != list(range(1, EXPECTED_PLAN_COUNT + 1)):
            errors.append("execution_order must be exactly 1..10")
        keys = [plan_key(e) for e in entries if isinstance(e, Mapping)]
        if len(set(keys)) != len(keys):
            errors.append("duplicate selected plan keys")
        samples = [s for s, _ in keys]
        if len(set(samples)) != len(samples):
            errors.append("duplicate sample across selected plans")
        hist_keys = set(hist.get("plan_keys") or []) if isinstance(hist, Mapping) else set()
        overlap = sorted(set(plan_key_str(e) for e in entries if isinstance(e, Mapping)) & hist_keys)
        if overlap:
            errors.append(f"selected plans overlap historical called keys: {overlap}")
    return errors


def validate_structure(config: Mapping[str, Any]) -> list[str]:
    """Return structural validation errors (empty list == valid)."""
    return _error_list(config)


def verify_historical_keys_sha(config: Mapping[str, Any]) -> list[str]:
    """Recompute and verify the historical plan-keys SHA-256."""
    hist = config.get("historical_calls") or {}
    keys = hist.get("plan_keys") or []
    expected = hist.get("plan_keys_sha256")
    if not isinstance(keys, list) or not isinstance(expected, str):
        return ["historical_calls.plan_keys / plan_keys_sha256 missing"]
    actual = historical_plan_keys_sha256(keys)
    if actual != expected:
        return [f"historical plan_keys sha mismatch: config={expected} actual={actual}"]
    return []


def load_frozen_plan(path: str | Path) -> dict[str, Any]:
    """Load and structurally validate a frozen pilot-plan config.

    Raises :class:`ValueError` on JSON/structural failure.  The caller
    must fail closed (no API call) when this raises.
    """
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("frozen plan config must be a JSON object")
    errors = validate_structure(config)
    if errors:
        raise ValueError("invalid frozen plan config: " + "; ".join(errors))
    sha_errors = verify_historical_keys_sha(config)
    if sha_errors:
        raise ValueError("invalid frozen plan config: " + "; ".join(sha_errors))
    return config


def evaluate_early_stop(
    *,
    calls_made: int,
    consecutive_failures: int,
    provider_returned_model: str | None,
    required_model: str,
    capture_bound: bool,
    plan_key_ok: bool,
    hard_call_cap: int,
) -> str | None:
    """Return the first violating early-stop reason, else ``None``.

    Pure decision function; the runner calls it after each real call in
    frozen-plan mode.  ``consecutive_failures`` counts consecutive
    transport/extraction failures (patch-level rejections do not count).
    """
    if provider_returned_model != required_model:
        return EARLY_STOP_REASON_PROVIDER_MODEL
    if not capture_bound:
        return EARLY_STOP_REASON_CAPTURE
    if calls_made > hard_call_cap:
        return EARLY_STOP_REASON_BUDGET
    if not plan_key_ok:
        return EARLY_STOP_REASON_PLAN_KEY
    if consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT:
        return EARLY_STOP_REASON_CONSECUTIVE
    return None


# ---------------------------------------------------------------------------
# S2.8D-R6C1: frozen-pilot continuation contract
# ---------------------------------------------------------------------------

CONTINUATION_SCHEMA_VERSION = "h1_pilot_continuation@1.0.0"
EXPECTED_CONTINUATION_PLAN_COUNT = 5
EXPECTED_CONTINUATION_HARD_CALL_CAP = 5


def continuation_plan_key(entry: Mapping[str, Any]) -> tuple[str, str]:
    return str(entry["sample_id"]), str(entry["clause_id"])


def continuation_plan_key_str(entry: Mapping[str, Any]) -> str:
    sample_id, clause_id = continuation_plan_key(entry)
    return f"{sample_id}/{clause_id}"


def continuation_plan_keys_sha256(entries: Sequence[Mapping[str, Any]]) -> str:
    keys = sorted(continuation_plan_key_str(e) for e in entries)
    return sha256_text("\n".join(keys))


def _continuation_errors(config: Mapping[str, Any]) -> list[str]:
    """Structural validation errors for a continuation plan (empty == valid)."""
    errors: list[str] = []

    def need(path: str, cond: bool, message: str | None = None) -> None:
        if not cond:
            errors.append(message or f"missing/invalid field: {path}")

    if config.get("schema_version") != CONTINUATION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CONTINUATION_SCHEMA_VERSION!r}")
    need("task_id", isinstance(config.get("task_id"), str) and bool(config["task_id"]))
    need("parent_frozen_plan_path", isinstance(config.get("parent_frozen_plan_path"), str) and bool(config["parent_frozen_plan_path"]))
    need("parent_frozen_plan_sha256", _is_hex64(config.get("parent_frozen_plan_sha256")))
    need("parent_selected_plan_keys_sha256", _is_hex64(config.get("parent_selected_plan_keys_sha256")))
    need("model", config.get("model") == REQUIRED_MODEL)
    need("prompt_variant", isinstance(config.get("prompt_variant"), str) and bool(config["prompt_variant"]))
    need("prompt_sha256", _is_hex64(config.get("prompt_sha256")))
    need("remaining_original_orders", isinstance(config.get("remaining_original_orders"), list)
         and config.get("remaining_original_orders") == [6, 7, 8, 9, 10])
    need("remaining_plan_keys_sha256", _is_hex64(config.get("remaining_plan_keys_sha256")))

    prior = config.get("prior_run")
    if not isinstance(prior, Mapping):
        errors.append("missing prior_run section")
    else:
        need("prior_run.run_id", isinstance(prior.get("run_id"), str) and bool(prior["run_id"]))
        for key in ("manifest_path", "manifest_sha256", "transport_capture_path", "transport_capture_sha256", "telemetry_path"):
            if key.endswith("_sha256"):
                need(f"prior_run.{key}", _is_hex64(prior.get(key)))
            else:
                need(f"prior_run.{key}", isinstance(prior.get(key), str) and bool(prior[key]))
        need("prior_run.actual_api_calls", isinstance(prior.get("actual_api_calls"), int) and prior.get("actual_api_calls") >= 0)
        need("prior_run.called_original_orders", isinstance(prior.get("called_original_orders"), list)
             and prior.get("called_original_orders") == [1, 2, 3, 4, 5])
        need("prior_run.called_plan_keys_sha256", _is_hex64(prior.get("called_plan_keys_sha256")))

    b0 = config.get("b0")
    if not isinstance(b0, Mapping):
        errors.append("missing b0 section")
    else:
        for key in ("attempts_path", "attempts_sha256", "manifest_path", "manifest_sha256"):
            need(f"b0.{key}", _is_hex64(b0.get(key)) if key.endswith("_sha256") else (isinstance(b0.get(key), str) and bool(b0[key])))

    budget = config.get("budget")
    if not isinstance(budget, Mapping):
        errors.append("missing budget section")
    else:
        need("budget.hard_api_call_cap", budget.get("hard_api_call_cap") == EXPECTED_CONTINUATION_HARD_CALL_CAP)
        need("budget.retry_per_plan", budget.get("retry_per_plan") == EXPECTED_RETRY_PER_PLAN)
        need("budget.max_calls_per_plan", budget.get("max_calls_per_plan") == EXPECTED_MAX_CALLS_PER_PLAN)

    entries = config.get("selected_plans")
    if not isinstance(entries, list):
        errors.append("selected_plans must be a list")
        return errors
    if len(entries) != EXPECTED_CONTINUATION_PLAN_COUNT:
        errors.append(f"selected_plans must contain exactly {EXPECTED_CONTINUATION_PLAN_COUNT} entries")
    for index, entry in enumerate(entries):
        prefix = f"selected_plans[{index}]"
        if not isinstance(entry, Mapping):
            errors.append(f"{prefix} must be an object")
            continue
        need(f"{prefix}.sample_id", isinstance(entry.get("sample_id"), str) and bool(entry["sample_id"]))
        need(f"{prefix}.clause_id", isinstance(entry.get("clause_id"), str) and bool(entry["clause_id"]))
        need(f"{prefix}.clause_index", isinstance(entry.get("clause_index"), int) and not isinstance(entry.get("clause_index"), bool))
        need(f"{prefix}.risk_score", isinstance(entry.get("risk_score"), int) and not isinstance(entry.get("risk_score"), bool))
        need(f"{prefix}.repair_fields", isinstance(entry.get("repair_fields"), list) and all(isinstance(f, str) for f in entry["repair_fields"]))
        need(f"{prefix}.reasons", isinstance(entry.get("reasons"), list) and all(isinstance(r, str) for r in entry["reasons"]))
        for hkey in ("b0_prediction_sha256", "clause_identity_hash", "rendered_masked_context_hash", "prompt_sha256"):
            need(f"{prefix}.{hkey}", _is_hex64(entry.get(hkey)))
        need(f"{prefix}.original_execution_order", isinstance(entry.get("original_execution_order"), int) and not isinstance(entry.get("original_execution_order"), bool))
        need(f"{prefix}.continuation_execution_order", isinstance(entry.get("continuation_execution_order"), int) and not isinstance(entry.get("continuation_execution_order"), bool))
        need(f"{prefix}.prior_called", entry.get("prior_called") is False)

    if not errors:
        orig_orders = sorted(e.get("original_execution_order") for e in entries if isinstance(e, Mapping))
        if orig_orders != [6, 7, 8, 9, 10]:
            errors.append("original_execution_order must be exactly 6..10")
        cont_orders = sorted(e.get("continuation_execution_order") for e in entries if isinstance(e, Mapping))
        if cont_orders != [1, 2, 3, 4, 5]:
            errors.append("continuation_execution_order must be exactly 1..5")
        keys = [continuation_plan_key(e) for e in entries if isinstance(e, Mapping)]
        if len(set(keys)) != len(keys):
            errors.append("duplicate continuation plan keys")
        samples = [s for s, _ in keys]
        if len(set(samples)) != len(samples):
            errors.append("duplicate samples across continuation plans")
    return errors


def validate_continuation_structure(config: Mapping[str, Any]) -> list[str]:
    return _continuation_errors(config)


def load_continuation_plan(path: str | Path) -> dict[str, Any]:
    """Load and structurally validate a continuation plan config.

    Raises :class:`ValueError` on JSON/structural failure.  The caller must
    fail closed (no API call) when this raises.
    """
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("continuation plan config must be a JSON object")
    errors = validate_continuation_structure(config)
    if errors:
        raise ValueError("invalid continuation plan config: " + "; ".join(errors))
    return config


__all__ = [
    "SCHEMA_VERSION",
    "TASK_ID",
    "REQUIRED_MODEL",
    "EXPECTED_PLAN_COUNT",
    "EXPECTED_HARD_CALL_CAP",
    "EXPECTED_RETRY_PER_PLAN",
    "EXPECTED_MAX_CALLS_PER_PLAN",
    "CONSECUTIVE_FAILURE_LIMIT",
    "EARLY_STOP_NOT_CALLED",
    "EARLY_STOP_REASONS",
    "DEFAULT_EARLY_STOP_POLICY",
    "sha256_text",
    "json_hash",
    "plan_key",
    "plan_key_str",
    "selected_plan_keys_sha256",
    "historical_plan_keys_sha256",
    "validate_structure",
    "verify_historical_keys_sha",
    "load_frozen_plan",
    "evaluate_early_stop",
    "CONTINUATION_SCHEMA_VERSION",
    "EXPECTED_CONTINUATION_PLAN_COUNT",
    "EXPECTED_CONTINUATION_HARD_CALL_CAP",
    "continuation_plan_key",
    "continuation_plan_key_str",
    "continuation_plan_keys_sha256",
    "validate_continuation_structure",
    "load_continuation_plan",
]
