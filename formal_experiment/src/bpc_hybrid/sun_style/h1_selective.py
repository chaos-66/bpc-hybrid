"""Locked S2.8 selection and field-level merge contract for H1.

This module never opens an API configuration and never sends a request.  It
accepts only a verified canonical B0 record plus explicitly enumerated
inference-time telemetry, produces a repair plan, and validates a supplied
repair-patch envelope.  Real transport remains a later, separately authorized
step.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.prompt_loader import LoadedPrompt, render_user_prompt
from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, validate_canonical


S28_CONFIG_SCHEMA = "sun_h1_s28@1.2.0"
EXTRACTION_CONTRACT_ID = "stage2_extraction_contract@1.0.0"
EXTRACTION_CONTRACT_SHA256 = "7f17ecba78cfa1acf1bbc488942f1c85c37d08ece7662c622bab4226bd2dbd46"
CANONICAL_FIELDS = (
    "modality",
    "actors",
    "actions",
    "conditions",
    "constraints",
    "exceptions",
    "actor_action_map",
    "order_relations",
)
SPAN_FIELDS = ("actors", "actions", "conditions", "constraints", "exceptions")
RELATION_FIELDS = ("actor_action_map", "order_relations")
MARKER_SCOPE_FIELDS = ("conditions", "constraints", "exceptions")
EXPECTED_TELEMETRY_FIELDS = {
    "parser_status",
    "tregex_conflict_fields",
    "canonical_invalid_fields",
    "modality_confidence",
    "modality_margin",
    "marker_scope_missing_fields",
    "unresolved_actor_candidate_count",
    "stage3_adapter_rejected_fields",
}


class H1ContractError(ValueError):
    """Raised when the preregistered H1 boundary is violated."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_s28_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise H1ContractError(f"invalid S2.8 config: {path}") from exc
    if not isinstance(config, dict):
        raise H1ContractError("S2.8 config root must be an object")
    if (
        config.get("schema_version") != S28_CONFIG_SCHEMA
        or config.get("task_id") != "S2.8"
        or config.get("method_id") != "sun_llm_fallback"
    ):
        raise H1ContractError("S2.8 config identity mismatch")
    baseline = config.get("baseline_binding", {})
    if baseline.get("task_id") != "S2.6" or baseline.get("legacy_front_end_allowed") is not False:
        raise H1ContractError("H1 must bind the verified S2.6 B0 and forbid the legacy front end")
    trigger = config.get("trigger_policy", {})
    if set(trigger.get("telemetry_fields", ())) != EXPECTED_TELEMETRY_FIELDS:
        raise H1ContractError("S2.8 telemetry field whitelist changed")
    if trigger.get("evidence_boundary") != "inference_time_observations_only_no_gold_or_test_distribution":
        raise H1ContractError("S2.8 trigger evidence boundary changed")
    repair = config.get("repair_policy", {})
    if tuple(repair.get("canonical_field_order", ())) != CANONICAL_FIELDS:
        raise H1ContractError("S2.8 canonical repair field order changed")
    if tuple(repair.get("repairable_fields", ())) != CANONICAL_FIELDS:
        raise H1ContractError("S2.8 repairable field set changed")
    extraction = config.get("extraction_contract", {})
    if (
        extraction.get("contract_id") != EXTRACTION_CONTRACT_ID
        or extraction.get("sha256") != EXTRACTION_CONTRACT_SHA256
        or extraction.get("input_policy") != "target_text_plus_current_b0_record_only"
    ):
        raise H1ContractError("H1 Stage 2 extraction contract binding changed")
    model = config.get("model", {})
    if (
        model.get("provider") != "openai_compatible"
        or model.get("api_family") != "chat_completions"
        or model.get("exact_model_id") != "gpt-4.1-2025-04-14"
        or model.get("pin_type") != "dated_snapshot"
        or model.get("real_api_authorized") is not False
    ):
        raise H1ContractError("S2.8 model snapshot changed or real API was enabled")
    sampling = config.get("sampling", {})
    if sampling != {
        "temperature": 0,
        "top_p": 1,
        "seed": None,
        "seed_policy": "unsupported_or_omitted",
        "max_output_tokens": 2048,
        "response_format": "json_object",
        "max_retries": 0,
    }:
        raise H1ContractError("S2.8 sampling contract changed")
    budget = config.get("budget", {})
    derived = math.floor(budget.get("target_dataset_size", -1) * budget.get("max_call_fraction", -1))
    derived_calls = min(derived, 45)
    derived_input = derived_calls * budget.get("input_token_ceiling_per_request", -1)
    derived_output = derived_calls * budget.get("output_token_ceiling_per_request", -1)
    price = budget.get("price_snapshot_usd_per_million", {})
    derived_cost = (
        derived_input * price.get("input", math.nan)
        + derived_output * price.get("output", math.nan)
    ) / 1_000_000
    if (
        budget.get("target_dataset_size") != 150
        or budget.get("max_call_fraction") != 0.3
        or budget.get("absolute_max_calls") != 45
        or budget.get("derived_max_calls") != derived_calls
        or budget.get("max_requests_per_sample") != 1
        or budget.get("max_retries") != 0
        or budget.get("total_input_token_ceiling") != derived_input
        or budget.get("total_output_token_ceiling") != derived_output
        or budget.get("total_token_ceiling") != derived_input + derived_output
        or not math.isclose(budget.get("estimated_worst_case_cost_usd", -1), derived_cost)
        or budget.get("hard_cost_ceiling_usd", -1) < derived_cost
        or budget.get("real_api_authorized") is not False
    ):
        raise H1ContractError("S2.8 call/token/cost budget changed or real API was enabled")
    allocation = config.get("allocation_policy", {})
    if (
        allocation.get("candidate_order") != "ascending_sample_id_then_clause_id"
        or allocation.get("one_request_per_sample") is not True
        or allocation.get("global_limit") != 45
        or allocation.get("confidence_reranking_allowed") is not False
        or allocation.get("gold_or_test_reranking_allowed") is not False
        or allocation.get("input_array_order_affects_allocation") is not False
    ):
        raise H1ContractError("S2.8 deterministic allocation policy changed")
    envelope = config.get("attempt_envelope", {})
    if (
        envelope.get("terminal_api_error_record_null_for_provider_recovery") is not False
        or envelope.get("failed_or_untriggered_samples_may_not_be_dropped") is not True
    ):
        raise H1ContractError("S2.8 fallback attempt semantics changed")
    evaluator = config.get("evaluator_binding", {})
    if (
        evaluator.get("task_id") != "S2.10-E"
        or evaluator.get("recovered_provider_error_keeps_fallback_record_scorable") is not True
    ):
        raise H1ContractError("S2.8 evaluator binding changed")
    return config


def _field_list(value: Any, *, allowed: Sequence[str], label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise H1ContractError(f"{label} must be a list of canonical field names")
    unknown = set(value) - set(allowed)
    if unknown:
        raise H1ContractError(f"{label} contains forbidden fields: {sorted(unknown)}")
    if len(value) != len(set(value)):
        raise H1ContractError(f"{label} contains duplicate fields")
    return tuple(value)


def _probability(value: Any, *, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise H1ContractError(f"{label} must be a number between 0 and 1")
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise H1ContractError(f"{label} must be between 0 and 1")
    return result


def _ordered_fields(fields: set[str]) -> tuple[str, ...]:
    return tuple(field for field in CANONICAL_FIELDS if field in fields)


def _add_dependency_closure(fields: set[str]) -> None:
    if "actors" in fields:
        fields.add("actor_action_map")
    if "actions" in fields:
        fields.update(("actor_action_map", "order_relations"))


@dataclass(frozen=True)
class RepairPlan:
    sample_id: str
    clause_id: str
    trigger_codes: tuple[str, ...]
    repair_fields: tuple[str, ...]

    @property
    def fallback_triggered(self) -> bool:
        return bool(self.trigger_codes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "clause_id": self.clause_id,
            "fallback_triggered": self.fallback_triggered,
            "trigger_codes": list(self.trigger_codes),
            "repair_fields": list(self.repair_fields),
        }


def detect_repair_plan(
    b0_record: Mapping[str, Any],
    telemetry: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    clause_index: int = 0,
) -> RepairPlan:
    """Create an H1 plan from B0 output and inference-visible telemetry only."""

    if not isinstance(telemetry, Mapping):
        raise H1ContractError("telemetry must be an object")
    trigger_config = config["trigger_policy"]
    forbidden = set(trigger_config["forbidden_inputs"]) & set(telemetry)
    if forbidden:
        raise H1ContractError(f"Gold/test-derived telemetry is forbidden: {sorted(forbidden)}")
    unknown = set(telemetry) - EXPECTED_TELEMETRY_FIELDS
    if unknown:
        raise H1ContractError(f"unregistered telemetry fields: {sorted(unknown)}")
    if b0_record.get("method", {}).get("name") != "sun_rule_only":
        raise H1ContractError("H1 input must be a verified sun_rule_only B0 record")
    clauses = b0_record.get("clauses")
    if not isinstance(clauses, list) or not (0 <= clause_index < len(clauses)):
        raise H1ContractError("requested B0 clause does not exist")
    clause = clauses[clause_index]
    sample_id = b0_record.get("sample_id")
    clause_id = clause.get("clause_id")
    if not isinstance(sample_id, str) or not isinstance(clause_id, str):
        raise H1ContractError("B0 record identifiers are invalid")

    parser_status = telemetry.get("parser_status", "ok")
    if parser_status not in {"ok", "timeout", "failure"}:
        raise H1ContractError("parser_status must be ok, timeout, or failure")
    tregex_fields = _field_list(
        telemetry.get("tregex_conflict_fields", []),
        allowed=SPAN_FIELDS,
        label="tregex_conflict_fields",
    )
    invalid_fields = _field_list(
        telemetry.get("canonical_invalid_fields", []),
        allowed=CANONICAL_FIELDS,
        label="canonical_invalid_fields",
    )
    marker_fields = _field_list(
        telemetry.get("marker_scope_missing_fields", []),
        allowed=MARKER_SCOPE_FIELDS,
        label="marker_scope_missing_fields",
    )
    adapter_fields = _field_list(
        telemetry.get("stage3_adapter_rejected_fields", []),
        allowed=CANONICAL_FIELDS,
        label="stage3_adapter_rejected_fields",
    )
    confidence = _probability(telemetry.get("modality_confidence"), label="modality_confidence")
    margin = _probability(telemetry.get("modality_margin"), label="modality_margin")
    actor_candidates = telemetry.get("unresolved_actor_candidate_count", 0)
    if isinstance(actor_candidates, bool) or not isinstance(actor_candidates, int) or actor_candidates < 0:
        raise H1ContractError("unresolved_actor_candidate_count must be a non-negative integer")

    reasons: set[str] = set()
    fields: set[str] = set()
    if parser_status in {"timeout", "failure"}:
        reasons.add(f"parser_{parser_status}")
        fields.update((*SPAN_FIELDS, *RELATION_FIELDS))
    if tregex_fields:
        reasons.add("tregex_field_conflict")
        fields.update(tregex_fields)
    if invalid_fields:
        reasons.add("canonical_invalid_field")
        fields.update(invalid_fields)
    if clause.get("modality", {}).get("label") != "definition" and not clause.get("actions"):
        reasons.add("non_definition_missing_action")
        fields.add("actions")
    if confidence is not None and confidence < trigger_config["modality_confidence_below"]:
        reasons.add("low_modality_confidence")
        fields.add("modality")
    if margin is not None and margin < trigger_config["modality_margin_below"]:
        reasons.add("low_modality_margin")
        fields.add("modality")
    if marker_fields:
        reasons.add("marker_scope_missing")
        fields.update(marker_fields)
    if actor_candidates > 1:
        reasons.add("unresolved_actor_candidates")
        fields.add("actors")
    if adapter_fields:
        reasons.add("stage3_adapter_rejection")
        fields.update(adapter_fields)
    _add_dependency_closure(fields)

    allowed_code_order = tuple(trigger_config["allowed_codes"])
    if not reasons.issubset(set(allowed_code_order)):
        raise H1ContractError("runtime produced an unregistered trigger code")
    return RepairPlan(
        sample_id=sample_id,
        clause_id=clause_id,
        trigger_codes=tuple(code for code in allowed_code_order if code in reasons),
        repair_fields=_ordered_fields(fields),
    )


class CallBudget:
    """One-request-per-sample, fail-closed reservation ledger."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        budget = config["budget"]
        self.limit = int(budget["derived_max_calls"])
        self._sample_ids: set[str] = set()

    @property
    def used(self) -> int:
        return len(self._sample_ids)

    @property
    def remaining(self) -> int:
        return self.limit - self.used

    def reserve(self, sample_id: str) -> tuple[bool, str]:
        if not isinstance(sample_id, str) or not sample_id:
            return False, "invalid_sample_id"
        if sample_id in self._sample_ids:
            return False, "per_sample_limit_reached"
        if self.used >= self.limit:
            return False, "global_budget_exhausted"
        self._sample_ids.add(sample_id)
        return True, "reserved"


def allocate_repair_calls(
    plans: Sequence[RepairPlan], config: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Allocate the fixed H1 budget independently of input array order."""

    if not isinstance(plans, Sequence) or isinstance(plans, (str, bytes)):
        raise H1ContractError("repair plans must be a sequence")
    seen: set[tuple[str, str]] = set()
    ordered: list[RepairPlan] = []
    for plan in plans:
        if not isinstance(plan, RepairPlan):
            raise H1ContractError("allocation accepts RepairPlan values only")
        key = (plan.sample_id, plan.clause_id)
        if key in seen:
            raise H1ContractError(f"duplicate repair plan: {key}")
        seen.add(key)
        ordered.append(plan)
    budget = CallBudget(config)
    decisions: list[dict[str, Any]] = []
    for plan in sorted(ordered, key=lambda item: (item.sample_id, item.clause_id)):
        if not plan.fallback_triggered:
            accepted, status = False, "not_triggered"
        else:
            accepted, status = budget.reserve(plan.sample_id)
        decisions.append(
            {
                "sample_id": plan.sample_id,
                "clause_id": plan.clause_id,
                "fallback_triggered": plan.fallback_triggered,
                "call_reserved": accepted,
                "allocation_status": status,
                "trigger_codes": list(plan.trigger_codes),
                "repair_fields": list(plan.repair_fields),
            }
        )
    return decisions


def render_h1_request(
    b0_record: Mapping[str, Any],
    repair_plan: RepairPlan,
    prompt: LoadedPrompt,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Render and hash the exact future authorized H1 repair request."""

    if not repair_plan.fallback_triggered:
        raise H1ContractError("H1 request requires a triggered repair plan")
    if prompt.sha256 != config.get("prompt", {}).get("sha256"):
        raise H1ContractError("H1 prompt SHA-256 changed")
    if b0_record.get("sample_id") != repair_plan.sample_id:
        raise H1ContractError("repair-plan sample_id does not match B0 record")
    clauses = b0_record.get("clauses")
    if not isinstance(clauses, list):
        raise H1ContractError("B0 record has no clause list")
    matching = [item for item in clauses if item.get("clause_id") == repair_plan.clause_id]
    if len(matching) != 1:
        raise H1ContractError("repair-plan clause_id is not unique in B0 record")
    user_prompt = render_user_prompt(
        prompt.user_prompt_template,
        sample_id=repair_plan.sample_id,
        source_id=b0_record.get("source_id"),
        source_text=b0_record.get("source_text"),
        clause_id=repair_plan.clause_id,
        current_clause_json=json.dumps(matching[0], ensure_ascii=False, indent=2),
        current_unsupported_json=json.dumps(
            b0_record.get("unsupported_or_ambiguous", []),
            ensure_ascii=False,
            indent=2,
        ),
        repair_fields_csv=", ".join(repair_plan.repair_fields),
        repair_reasons_csv=", ".join(repair_plan.trigger_codes),
    )
    if any(
        token in user_prompt
        for token in (
            "{sample_id}",
            "{source_text}",
            "{repair_fields_csv}",
            "{current_unsupported_json}",
        )
    ):
        raise H1ContractError("H1 user prompt contains an unrendered placeholder")
    sampling = config["sampling"]
    api_request = {
        "model": config["model"]["exact_model_id"],
        "messages": [
            {"role": "system", "content": prompt.system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": sampling["temperature"],
        "top_p": sampling["top_p"],
        "max_completion_tokens": sampling["max_output_tokens"],
        "response_format": {"type": sampling["response_format"]},
    }
    return {
        "model": config["model"]["exact_model_id"],
        "sampling_contract": copy.deepcopy(sampling),
        "api_request": api_request,
        "system_prompt_sha256": sha256_text(prompt.system_prompt),
        "user_prompt_sha256": sha256_text(user_prompt),
        "system_prompt_char_count": len(prompt.system_prompt),
        "user_prompt_char_count": len(user_prompt),
        "repair_fields": list(repair_plan.repair_fields),
    }


def finalize_h1_record(
    record: Mapping[str, Any],
    *,
    original_b0: Mapping[str, Any] | None = None,
    fallback_to_b0: bool = False,
) -> dict[str, Any]:
    """Attach H1 method identity without changing fallback semantic content."""

    final = copy.deepcopy(dict(record))
    if fallback_to_b0:
        if original_b0 is None or final != dict(original_b0):
            raise H1ContractError("H1 fallback must start from the exact original B0 record")
    final["method"] = {"name": "sun_llm_fallback", "schema_source": SCHEMA_SOURCE}
    validation = validate_canonical(final)
    if not validation.schema_valid or not validation.cross_field_valid:
        raise H1ContractError("final H1 record is not canonical-valid")
    if fallback_to_b0:
        semantic_final = copy.deepcopy(final)
        semantic_original = copy.deepcopy(dict(original_b0))
        semantic_final.pop("method", None)
        semantic_original.pop("method", None)
        if semantic_final != semantic_original:
            raise H1ContractError("H1 fallback changed B0 semantic content")
    return final


def make_h1_attempt(
    b0_record: Mapping[str, Any],
    *,
    runtime: Mapping[str, Any],
    recovered_runtime_error_category: str | None = None,
) -> dict[str, Any]:
    """Build an S2.10-E envelope for a scorable H1 B0 fallback."""

    required_runtime = (
        "llm_call_performed",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "estimated_cost_usd",
        "latency_ms",
    )
    if not isinstance(runtime, Mapping) or any(key not in runtime for key in required_runtime):
        raise H1ContractError("H1 runtime accounting is incomplete")
    runtime_copy = {key: runtime[key] for key in required_runtime}
    if runtime_copy["llm_call_performed"] not in (True, False):
        raise H1ContractError("runtime.llm_call_performed must be boolean")
    for key in required_runtime[1:]:
        value = runtime_copy[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise H1ContractError(f"runtime.{key} must be a non-negative number")
    if runtime_copy["total_tokens"] != runtime_copy["prompt_tokens"] + runtime_copy["completion_tokens"]:
        raise H1ContractError("H1 runtime token totals disagree")
    if recovered_runtime_error_category is not None and (
        not isinstance(recovered_runtime_error_category, str)
        or not recovered_runtime_error_category.strip()
        or runtime_copy["llm_call_performed"] is not True
    ):
        raise H1ContractError("recovered provider error requires a performed LLM call and category")
    attempt = {
        "sample_id": b0_record.get("sample_id"),
        "request_status": "ok",
        "record": finalize_h1_record(
            b0_record, original_b0=b0_record, fallback_to_b0=True
        ),
        "error_category": None,
        "runtime": runtime_copy,
    }
    if recovered_runtime_error_category is not None:
        attempt["recovered_runtime_error_category"] = recovered_runtime_error_category.strip()
    return attempt


@dataclass(frozen=True)
class MergeResult:
    accepted: bool
    status: str
    errors: tuple[str, ...]
    record: dict[str, Any]

    def to_summary(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "status": self.status,
            "errors": list(self.errors),
        }


def _reject(original: dict[str, Any], status: str, *errors: str) -> MergeResult:
    return MergeResult(False, status, tuple(errors), copy.deepcopy(original))


def apply_repair_patch(
    b0_record: Mapping[str, Any],
    patch_envelope: Mapping[str, Any],
    repair_plan: RepairPlan,
) -> MergeResult:
    """Apply one strict patch or return the original B0 record unchanged."""

    original = copy.deepcopy(dict(b0_record))
    if not isinstance(patch_envelope, Mapping):
        return _reject(original, "rejected_non_object", "patch envelope must be an object")
    expected_keys = {
        "sample_id",
        "clause_id",
        "repair_fields",
        "patches",
        "unsupported_or_ambiguous",
        "reason",
    }
    if set(patch_envelope) != expected_keys:
        return _reject(original, "rejected_envelope", "patch envelope keys are not exact")
    if patch_envelope.get("sample_id") != repair_plan.sample_id:
        return _reject(original, "rejected_envelope", "sample_id mismatch")
    if patch_envelope.get("clause_id") != repair_plan.clause_id:
        return _reject(original, "rejected_envelope", "clause_id mismatch")
    if patch_envelope.get("repair_fields") != list(repair_plan.repair_fields):
        return _reject(original, "rejected_envelope", "repair_fields mismatch")
    if not isinstance(patch_envelope.get("reason"), str) or not patch_envelope["reason"].strip():
        return _reject(original, "rejected_envelope", "reason must be non-empty")
    unsupported = patch_envelope.get("unsupported_or_ambiguous")
    if not isinstance(unsupported, list):
        return _reject(
            original,
            "rejected_envelope",
            "unsupported_or_ambiguous must be a complete replacement list",
        )
    patches = patch_envelope.get("patches")
    if not isinstance(patches, Mapping) or not patches:
        return _reject(original, "rejected_envelope", "patches must be a non-empty object")
    unauthorized = set(patches) - set(repair_plan.repair_fields)
    if unauthorized:
        return _reject(
            original,
            "rejected_unauthorized_field",
            f"unauthorized fields: {sorted(unauthorized)}",
        )

    clauses = original.get("clauses", [])
    clause_indexes = [
        index for index, clause in enumerate(clauses)
        if isinstance(clause, Mapping) and clause.get("clause_id") == repair_plan.clause_id
    ]
    if len(clause_indexes) != 1:
        return _reject(original, "rejected_envelope", "target clause is missing or duplicated")
    clause_index = clause_indexes[0]
    candidate = copy.deepcopy(original)
    candidate["unsupported_or_ambiguous"] = copy.deepcopy(unsupported)
    target = candidate["clauses"][clause_index]
    original_clause = original["clauses"][clause_index]

    unpatched_span_ids = {
        span.get("id")
        for field in SPAN_FIELDS
        if field not in patches
        for span in original_clause.get(field, [])
        if isinstance(span, Mapping) and isinstance(span.get("id"), str)
    }
    for field, value in patches.items():
        if field not in CANONICAL_FIELDS:
            return _reject(original, "rejected_unauthorized_field", f"unknown field: {field}")
        if isinstance(value, Mapping) and value.get("absent") is True:
            if set(value) != {"absent"} or field == "modality":
                return _reject(original, "rejected_value", f"invalid absent marker for {field}")
            target[field] = []
            continue
        if field == "modality":
            if not isinstance(value, Mapping) or set(value) != {"label", "evidence"}:
                return _reject(original, "rejected_value", "modality patch must contain label and evidence")
            target[field] = copy.deepcopy(dict(value))
            continue
        if field in SPAN_FIELDS:
            if not isinstance(value, list):
                return _reject(original, "rejected_value", f"{field} patch must be a list")
            ids: list[str] = []
            for span in value:
                if not isinstance(span, Mapping) or not isinstance(span.get("id"), str) or not span["id"]:
                    return _reject(original, "rejected_value", f"{field} contains an invalid id")
                ids.append(span["id"])
            if len(ids) != len(set(ids)):
                return _reject(original, "rejected_value", f"{field} contains duplicate ids")
            collisions = set(ids) & unpatched_span_ids
            if collisions:
                return _reject(
                    original,
                    "rejected_value",
                    f"{field} ids collide with unpatched span fields: {sorted(collisions)}",
                )
            target[field] = copy.deepcopy(value)
            continue
        if field in RELATION_FIELDS:
            if not isinstance(value, list):
                return _reject(original, "rejected_value", f"{field} patch must be a list")
            target[field] = copy.deepcopy(value)
            continue

    for field in CANONICAL_FIELDS:
        if field not in patches and target.get(field) != original_clause.get(field):
            return _reject(original, "rejected_preservation", f"unpatched field changed: {field}")
    candidate["method"] = {
        "name": "sun_llm_fallback",
        "schema_source": SCHEMA_SOURCE,
    }
    report = validate_canonical(candidate)
    if not (report.schema_valid and report.cross_field_valid):
        return _reject(
            original,
            "rejected_post_merge_validation",
            *report.errors,
        )
    return MergeResult(True, "accepted", (), candidate)
