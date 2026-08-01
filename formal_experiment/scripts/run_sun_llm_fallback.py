"""Run field-level selective H1 repair on an immutable B0 prediction batch.

H1 must consume the *same persisted B0 predictions* used by the B0 arm.  It
must never recreate B0 with a second extractor inside this runner.  The input
file is therefore mandatory and is bound into the manifest by SHA-256.

Three execution modes are supported:

* ``--plan-only``: detect and budget repair plans without evaluating patches;
* ``--offline-patches``: replay stored patch envelopes without network access;
* ``--offline-replay``: replay bound LLM responses (``--responses-jsonl``)
  through the exact real-API parse/validate/merge path, without network;
* ``--allow-llm``: explicitly authorize real API calls for selected plans.

``--prompt-variant`` selects the context policy shown to the model:
``full_b0_v4`` (default, historical prompt, byte-identical rendered
requests) or ``masked_selected_v5`` (the requested repair fields are
removed from the B0 clause context and replaced by a masking sentinel so
the model cannot anchor on B0's assignment).  A leak audit runs for every
selected plan in every mode, including ``--plan-only``.

Real runs (``--allow-llm``) are fail-closed on the model: ``--model`` is
required, overrides profile/.env selection, and the resolved value must
equal :data:`REAL_CALL_REQUIRED_MODEL`; otherwise the run aborts before
any API call.  The resolved model ID and its source are printed and
recorded in the manifest.

Every selected plan also carries an effective-patch audit (S2.8C):
``effective_patch=true`` only when the response was schema-valid, the
patch touched only the requested fields, the merged prediction is
canonical, at least one requested field's semantic hash differs from B0,
and the source/identity fields are unchanged.  JSON-equivalent no-op
patches are rejected as ``no_semantic_change`` and never counted as
effective.  The manifest reports the ``h1_non_identity_gate`` so a
plan-only run can never be mistaken for an effective fallback.

Every trigger and patch attempt is written to a telemetry sidecar.  Patch
application is atomic: an unauthorized, malformed, no-op, or canonical-invalid
patch is rejected in full and the exact B0 prediction is retained.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.b0_artifact import (  # noqa: E402
    B0ArtifactError,
    LoadedB0,
    clean_b0_entry,
    json_hash,
    load_b0_predictions,
    prediction_hash,
    read_json_values,
    sha256_bytes,
    sha256_file,
    verify_b0_manifest,
)
from bpc_hybrid.h1_context import (  # noqa: E402
    CONTEXT_POLICY_VERSION,
    audit_masked_context,
    build_masked_clause_context,
)
from bpc_hybrid.h1_transport import (  # noqa: E402
    DEEPSEEK_V4_FLASH_H1_POLICY,
    STATUS_OK,
    build_transport_capture_row,
    decode_chat_completion_envelope,
    describe_endpoint_safe,
)
from bpc_hybrid.h1_span_canonicalizer import (  # noqa: E402
    STATUS_FAILED,
    STATUS_REANCHORED,
    STATUS_UNCHANGED,
    canonicalize_patch_coordinates,
)
from bpc_hybrid.h1_pilot_plan import (  # noqa: E402
    EARLY_STOP_NOT_CALLED,
    EXPECTED_CONTINUATION_HARD_CALL_CAP,
    EXPECTED_HARD_CALL_CAP,
    continuation_plan_key,
    continuation_plan_key_str,
    continuation_plan_keys_sha256,
    evaluate_early_stop,
    load_continuation_plan,
    load_frozen_plan,
    plan_key_str,
    selected_plan_keys_sha256,
)
from bpc_hybrid.llm_config import LLMConfig
from bpc_hybrid.llm_client import (
    LLMClientError,
    LLMRequest,
    OpenAICompatibleRequestBuilder,
    RealAPITransport,
)
from bpc_hybrid.prompt_loader import build_manifest_entry, load_prompt
from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, validate_canonical
from formal_experiment.audit import collect_project_audit
from formal_experiment.paths import (
    FORMAL_PREDICTIONS_DIR,
    FORMAL_RESULTS_DIR,
    FROZEN_GOLD_DIR,
    FROZEN_INPUT_DIR,
)

# Backward-compatible aliases for the shared B0 binding helpers; the
# extraction into bpc_hybrid.b0_artifact preserves prior behavior exactly.
H1RunnerError = B0ArtifactError
_sha256_bytes = sha256_bytes
_sha256_file = sha256_file
_json_hash = json_hash
_prediction_hash = prediction_hash
_read_json_values = read_json_values
_clean_b0_entry = clean_b0_entry

PromptName = "rule_first_llm_fallback_prompt"
MaskedPromptName = "rule_first_llm_fallback_masked_prompt"

# S2.8B anchoring-ablation variants.  full_b0_v4 keeps the historical
# prompt and rendered request byte-for-byte; masked_selected_v5 masks the
# requested repair fields out of the B0 context before rendering.
DEFAULT_PROMPT_VARIANT = "full_b0_v4"
PROMPT_VARIANTS = ("full_b0_v4", "masked_selected_v5")
_PROMPT_NAME_BY_VARIANT = {
    "full_b0_v4": PromptName,
    "masked_selected_v5": MaskedPromptName,
}

# S2.8D fail-closed real-call model gate: real runs require an explicit
# --model whose resolved value (after the CLI override) must equal exactly
# this model ID; anything else aborts BEFORE any API call is made.
REAL_CALL_REQUIRED_MODEL = "deepseek-v4-flash"

_DEFAULT_OUTPUT = _PROJECT_ROOT / "data" / "predictions" / "sun_llm_fallback_predictions.jsonl"
_DEFAULT_MANIFEST = _PROJECT_ROOT / "data" / "predictions" / "sun_llm_fallback_manifest.json"

FORMAL_DIRS = (
    FROZEN_INPUT_DIR,
    FROZEN_GOLD_DIR,
    FORMAL_PREDICTIONS_DIR,
    FORMAL_RESULTS_DIR,
)

CANONICAL_CLAUSE_FIELDS = (
    "clause_id",
    "clause_span",
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
REPAIRABLE_FIELDS = ("modality",) + SPAN_FIELDS + RELATION_FIELDS
VALID_MODALITIES = {"obligation", "prohibition", "permission", "definition"}


@dataclass(frozen=True)
class RepairPlan:
    sample_id: str
    clause_id: str
    clause_index: int
    repair_fields: tuple[str, ...]
    reasons: tuple[str, ...]
    risk_score: int

    @property
    def key(self) -> tuple[str, str]:
        return self.sample_id, self.clause_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "clause_id": self.clause_id,
            "clause_index": self.clause_index,
            "repair_fields": list(self.repair_fields),
            "reasons": list(self.reasons),
            "risk_score": self.risk_score,
        }


def _ordered_fields(fields: Iterable[str]) -> tuple[str, ...]:
    selected = set(fields)
    return tuple(name for name in REPAIRABLE_FIELDS if name in selected)


def detect_repair_plan(
    record: Mapping[str, Any],
    telemetry: Mapping[str, Any],
    clause_index: int,
) -> RepairPlan | None:
    """Create a Gold-blind repair plan from inference-visible B0 diagnostics."""
    clause = record["clauses"][clause_index]
    clause_diagnostics = (telemetry.get("clauses") or [])[clause_index]
    fields: set[str] = set()
    reasons: list[str] = []
    risk = 0

    label = clause["modality"]["label"]
    if label != "definition" and not clause.get("actions"):
        fields.add("actions")
        reasons.append("non_definition_missing_action")
        risk += 100
    if label != "definition" and not clause.get("actors"):
        fields.add("actors")
        reasons.append("non_definition_missing_actor")
        risk += 50

    diagnostic = clause_diagnostics.get("modality_diagnostic") or {}
    classifier_label = diagnostic.get("clause_classifier_label")
    marker_label = diagnostic.get("marker_label")
    if (
        classifier_label in VALID_MODALITIES
        and marker_label in VALID_MODALITIES
        and classifier_label != marker_label
    ):
        fields.add("modality")
        reasons.append("classifier_marker_disagreement")
        risk += 80

    alignment = clause_diagnostics.get("alignment") or {}
    confidence = alignment.get("confidence")
    if isinstance(confidence, (int, float)) and confidence < 0.65:
        fields.add("modality")
        reasons.append("alignment_confidence_below_0_65")
        risk += 30

    scope_stats = clause_diagnostics.get("scope_stats") or {}
    if int(scope_stats.get("scope_rejected") or 0) > 0:
        fields.update(("conditions", "constraints", "exceptions"))
        reasons.append("scope_candidate_rejected")
        risk += 70

    if "actors" in fields or "actions" in fields:
        fields.add("actor_action_map")
    if "actions" in fields and clause.get("order_relations"):
        fields.add("order_relations")

    if not fields:
        return None
    return RepairPlan(
        sample_id=str(record["sample_id"]),
        clause_id=str(clause["clause_id"]),
        clause_index=clause_index,
        repair_fields=_ordered_fields(fields),
        reasons=tuple(reasons),
        risk_score=risk,
    )


def build_repair_plans(batch: Sequence[LoadedB0]) -> list[RepairPlan]:
    plans: list[RepairPlan] = []
    for item in batch:
        for clause_index in range(len(item.record["clauses"])):
            plan = detect_repair_plan(item.record, item.telemetry, clause_index)
            if plan is not None:
                plans.append(plan)
    return plans


def allocate_repair_calls(plans: Sequence[RepairPlan], max_calls: int) -> list[RepairPlan]:
    if max_calls < 0:
        raise H1RunnerError("max_calls must be non-negative")
    ranked = sorted(
        plans,
        key=lambda plan: (-plan.risk_score, plan.sample_id, plan.clause_index),
    )
    return ranked[:max_calls]


def _validate_span_patch(field_name: str, value: Any, clause: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return [f"{field_name} patch must be a list of supportedSpan objects"]
    seen: set[str] = set()
    other_ids = {
        span.get("id")
        for other_field in SPAN_FIELDS
        if other_field != field_name
        for span in clause.get(other_field, [])
        if isinstance(span, Mapping)
    }
    for index, span in enumerate(value):
        if not isinstance(span, Mapping):
            errors.append(f"{field_name}[{index}] must be an object")
            continue
        sid = span.get("id")
        if not isinstance(sid, str) or not sid:
            errors.append(f"{field_name}[{index}] has no non-empty id")
            continue
        if sid in seen:
            errors.append(f"{field_name} patch has duplicate id: {sid!r}")
        if sid in other_ids:
            errors.append(f"{field_name} patch id collides with another semantic field: {sid!r}")
        seen.add(sid)
    return errors


def apply_repair_patch(
    clause: dict[str, Any],
    patch: dict[str, Any],
    repair_fields: list[str] | tuple[str, ...],
) -> tuple[dict[str, Any], list[str]]:
    """Apply one field-level patch atomically; return original clause on error."""
    original = copy.deepcopy(clause)
    if not isinstance(patch, dict) or not patch:
        return original, ["patches must be a non-empty object"]
    authorized = set(repair_fields)
    unknown_authorizations = sorted(authorized - set(REPAIRABLE_FIELDS))
    errors: list[str] = []
    if unknown_authorizations:
        errors.append(f"repair_fields contains non-canonical names: {unknown_authorizations}")
    if set(patch) != authorized:
        missing = sorted(authorized - set(patch))
        unauthorized = sorted(set(patch) - authorized)
        if missing:
            errors.append(f"patch omitted requested fields: {missing}")
        if unauthorized:
            errors.append(f"patch tried to modify unauthorized fields: {unauthorized}")
    if errors:
        return original, errors

    candidate = copy.deepcopy(clause)
    for field_name in repair_fields:
        value = patch[field_name]
        if isinstance(value, Mapping) and value.get("absent") is True:
            if field_name == "modality":
                errors.append("modality cannot be absent")
            elif field_name in SPAN_FIELDS + RELATION_FIELDS:
                candidate[field_name] = []
            else:
                errors.append(f"unsupported absent patch for {field_name!r}")
            continue

        if field_name == "modality":
            if not isinstance(value, Mapping):
                errors.append("modality patch must be an object")
            elif value.get("label") not in VALID_MODALITIES:
                errors.append(f"modality label is not one of the four classes: {value.get('label')!r}")
            elif not isinstance(value.get("evidence"), list) or not value["evidence"]:
                errors.append("modality patch must contain non-empty evidence")
            else:
                candidate[field_name] = copy.deepcopy(dict(value))
        elif field_name in SPAN_FIELDS:
            span_errors = _validate_span_patch(field_name, value, clause)
            errors.extend(span_errors)
            if not span_errors:
                candidate[field_name] = copy.deepcopy(value)
        elif field_name in RELATION_FIELDS:
            if not isinstance(value, list):
                errors.append(f"{field_name} patch must be a list")
            else:
                candidate[field_name] = copy.deepcopy(value)

    if errors:
        return original, errors
    if candidate == original:
        return original, ["patch produced no semantic change"]
    return candidate, []


def _patch_event_base(plan: RepairPlan) -> dict[str, Any]:
    return {
        **plan.to_dict(),
        "selected_for_call": False,
        "llm_call_performed": False,
        "patch_proposed": False,
        "patch_accepted": False,
        "prediction_changed": False,
        "status": "triggered",
        "rejection_reasons": [],
        "field_diffs": [],
    }


def apply_patch_envelope(
    record: dict[str, Any],
    envelope: Mapping[str, Any],
    plan: RepairPlan,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate and atomically merge an envelope into an H1 record."""
    event = _patch_event_base(plan)
    event["patch_proposed"] = True
    event["status"] = "rejected"
    original = copy.deepcopy(record)
    expected_keys = {"sample_id", "clause_id", "repair_fields", "patches", "reason"}
    errors: list[str] = []
    if set(envelope) != expected_keys:
        errors.append(
            f"patch envelope keys must be exactly {sorted(expected_keys)}; got {sorted(envelope)}"
        )
    if envelope.get("sample_id") != plan.sample_id:
        errors.append(f"patch sample_id mismatch: {envelope.get('sample_id')!r}")
    if envelope.get("clause_id") != plan.clause_id:
        errors.append(f"patch clause_id mismatch: {envelope.get('clause_id')!r}")
    if envelope.get("repair_fields") != list(plan.repair_fields):
        errors.append("patch repair_fields do not exactly match the registered plan")
    if not isinstance(envelope.get("reason"), str) or not envelope.get("reason", "").strip():
        errors.append("patch reason must be a non-empty string")
    patches = envelope.get("patches")
    if not isinstance(patches, dict):
        errors.append("patches must be an object")
    if errors:
        event["rejection_reasons"] = errors
        return original, event

    clause_before = original["clauses"][plan.clause_index]
    clause_after, patch_errors = apply_repair_patch(
        clause_before,
        patches,
        plan.repair_fields,
    )
    if patch_errors:
        event["rejection_reasons"] = patch_errors
        return original, event

    candidate = copy.deepcopy(original)
    candidate["clauses"][plan.clause_index] = clause_after
    report = validate_canonical(candidate)
    if not (report.schema_valid and report.cross_field_valid):
        event["rejection_reasons"] = ["post-patch canonical validation failed"] + list(report.errors)
        return original, event

    field_diffs: list[dict[str, Any]] = []
    for field_name in plan.repair_fields:
        before = clause_before[field_name]
        after = clause_after[field_name]
        if before != after:
            field_diffs.append(
                {
                    "field": field_name,
                    "before": copy.deepcopy(before),
                    "after": copy.deepcopy(after),
                    "before_sha256": _json_hash(before),
                    "after_sha256": _json_hash(after),
                }
            )
    if not field_diffs:
        event["rejection_reasons"] = ["patch produced no semantic change"]
        return original, event

    event["patch_accepted"] = True
    event["prediction_changed"] = _prediction_hash(candidate) != _prediction_hash(original)
    event["status"] = "accepted"
    event["field_diffs"] = field_diffs
    event["before_prediction_sha256"] = _prediction_hash(original)
    event["after_prediction_sha256"] = _prediction_hash(candidate)
    return candidate, event


def _parse_patch_response(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            text = "\n".join(lines[1:-1]).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise H1RunnerError(f"LLM response is not a JSON patch envelope: {exc}") from exc
    if not isinstance(payload, dict):
        raise H1RunnerError("LLM response patch envelope is not an object")
    return payload


def load_offline_patches(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for item in _read_json_values(path):
        envelope = item.get("patch_envelope", item)
        if not isinstance(envelope, dict):
            raise H1RunnerError("offline patch row is not an envelope object")
        key = (str(envelope.get("sample_id", "")), str(envelope.get("clause_id", "")))
        if not all(key):
            raise H1RunnerError("offline patch envelope lacks sample_id or clause_id")
        if key in result:
            raise H1RunnerError(f"duplicate offline patch envelope: {key}")
        result[key] = envelope
    return result


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _gate_write(target: Path, development: bool) -> tuple[bool, str]:
    is_formal = any(_is_under(target, directory) for directory in FORMAL_DIRS)
    if not is_formal:
        if development:
            return True, "explicit development write"
        return False, "non-formal writes require --development"
    audit = collect_project_audit()
    if not audit["integrity_pass"]:
        return False, "formal write refused because integrity_pass is false"
    if audit["final_experiment_ready"]:
        return True, "formal route is final-ready"
    return False, "formal write refused because final_experiment_ready is false"


def _atomic_write_text(path: Path, text: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise H1RunnerError(f"refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _compact_event(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in event.items()
        if key != "field_diffs"
    } | {
        "changed_fields": [item["field"] for item in event.get("field_diffs", [])],
    }


def _derive_telemetry_path(output: Path) -> Path:
    suffix = output.suffix or ".jsonl"
    return output.with_suffix(".telemetry" + suffix)


def _rejection_codes(reasons: Sequence[str]) -> tuple[str, ...]:
    """Normalize human rejection messages into stable audit codes.

    Extraction failures from the transport decoder map to their stable
    status code (e.g. ``empty_final_content``), never a generic "other".
    """
    codes: list[str] = []
    for reason in reasons:
        lowered = reason.lower()
        if lowered.startswith("extraction_status:"):
            code = lowered[len("extraction_status:"):].split(":")[0].strip()
        elif lowered.startswith("coordinate_canonicalization_"):
            code = lowered.split(":", 1)[0].strip()
        elif "no semantic change" in lowered:
            code = "no_semantic_change"
        elif "canonical validation" in lowered or "post-patch" in lowered:
            code = "canonical_invalid"
        elif "unauthorized" in lowered or "not the registered plan" in lowered:
            code = "unauthorized_fields"
        elif "does not match" in lowered or "not in actors" in lowered or "not in actions" in lowered:
            code = "reference_mismatch"
        elif "duplicate" in lowered:
            code = "duplicate"
        elif "absent" in lowered and "modality" in lowered:
            code = "absent_modality"
        elif (
            "missing" in lowered
            or "must be" in lowered
            or "not an object" in lowered
            or "non-empty" in lowered
        ):
            code = "contract_violation"
        else:
            code = "other"
        if code not in codes:
            codes.append(code)
    return tuple(codes)


def _field_hashes(clause: Mapping[str, Any]) -> dict[str, str]:
    return {field: _json_hash(clause.get(field)) for field in REPAIRABLE_FIELDS}


def _effective_patch_audit(
    plan: RepairPlan,
    b0_record: Mapping[str, Any],
    record_before: Mapping[str, Any],
    record_after: Mapping[str, Any],
    event: Mapping[str, Any],
    envelope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """S2.8C effective-patch audit for one selected repair plan.

    effective_patch=true only when ALL of the following hold:

    1. the response envelope was schema-valid (merge path accepted it);
    2. the patch touched only the requested fields (merge path enforces
       the exact key set; the audit re-verifies it);
    3. the merged prediction is canonical (schema + cross-field);
    4. at least one requested field's canonical semantic hash differs
       from B0 (changed_fields is non-empty);
    5. source text and sample/clause identity are unchanged.

    A JSON-equivalent (no-op) patch is rejected as
    ``no_semantic_change`` and is NEVER counted as effective.
    """
    clause_before = record_before["clauses"][plan.clause_index]
    clause_after = record_after["clauses"][plan.clause_index]
    before_hashes = _field_hashes(clause_before)
    after_hashes = _field_hashes(clause_after)
    changed_fields = [
        field for field in REPAIRABLE_FIELDS
        if before_hashes[field] != after_hashes[field]
    ]
    proposed_fields = sorted(envelope.get("patches", {}).keys()) if envelope else []
    requested_fields = list(plan.repair_fields)
    accepted = bool(event.get("patch_accepted"))
    if accepted:
        accepted_fields = [f for f in requested_fields if f in changed_fields]
        rejected_fields = [f for f in requested_fields if f not in changed_fields]
    else:
        accepted_fields = []
        rejected_fields = list(requested_fields)

    semantic_changed = _prediction_hash(record_before) != _prediction_hash(record_after)
    merge_status = event.get("status")
    rejection_reasons = list(event.get("rejection_reasons", []) or [])
    fields_only_requested = set(proposed_fields) == set(requested_fields)
    identity_unchanged = (
        record_after.get("source_text") == record_before.get("source_text")
        and record_after.get("sample_id") == record_before.get("sample_id")
        and record_after.get("source_id") == record_before.get("source_id")
        and clause_after.get("clause_id") == clause_before.get("clause_id")
        and clause_after.get("clause_span") == clause_before.get("clause_span")
    )
    effective_patch = bool(
        accepted
        and semantic_changed
        and fields_only_requested
        and identity_unchanged
        and bool(changed_fields)
    )
    return {
        "b0_prediction_sha256": _prediction_hash(b0_record),
        "proposed_patch_sha256": _json_hash(envelope) if envelope else None,
        "merged_prediction_sha256": _prediction_hash(record_after),
        "requested_fields": requested_fields,
        "proposed_fields": proposed_fields,
        "accepted_fields": sorted(accepted_fields),
        "rejected_fields": sorted(rejected_fields),
        "merge_status": merge_status,
        "rejection_reasons": rejection_reasons,
        "rejection_codes": list(_rejection_codes(rejection_reasons)),
        "semantic_changed": semantic_changed,
        "changed_fields": sorted(changed_fields),
        "effective_patch": effective_patch,
    }


def load_replay_responses(
    path: Path,
    selected_plans: Sequence[RepairPlan],
    records: Mapping[str, Mapping[str, Any]],
    prompt_sha256: str,
    variant: str,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Load and bind an offline replay response file (S2.8C).

    Every line must be an object with EXACTLY the keys: request_id,
    sample_id, clause_id, clause_index, prompt_sha256, prompt_variant,
    b0_prediction_sha256, response_content.  The (sample_id, clause_id)
    set must EXACTLY match the selected plans (no missing, no extra),
    request_ids must be unique, and each response must bind to the plan's
    clause_index, the run's prompt SHA + variant, and the sample's B0
    prediction hash.  Any violation fails closed.
    """
    expected_keys = {
        "request_id",
        "sample_id",
        "clause_id",
        "clause_index",
        "prompt_sha256",
        "prompt_variant",
        "b0_prediction_sha256",
        "response_content",
    }
    responses: dict[tuple[str, str], dict[str, Any]] = {}
    request_ids: set[str] = set()
    for index, row in enumerate(_read_json_values(path)):
        if set(row) != expected_keys:
            raise H1RunnerError(
                f"replay response {index} keys must be exactly {sorted(expected_keys)}; "
                f"got {sorted(row)}"
            )
        request_id = row.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise H1RunnerError(f"replay response {index} request_id must be a non-empty string")
        if request_id in request_ids:
            raise H1RunnerError(f"duplicate replay request_id: {request_id!r}")
        request_ids.add(request_id)
        content = row.get("response_content")
        if not isinstance(content, str):
            raise H1RunnerError(f"replay response {index} response_content must be a string")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise H1RunnerError(
                f"replay response {index} response_content is not valid JSON: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise H1RunnerError(f"replay response {index} response_content must be a JSON object")
        key = (str(row.get("sample_id")), str(row.get("clause_id")))
        if not all(key):
            raise H1RunnerError(f"replay response {index} lacks sample_id or clause_id")
        if key in responses:
            raise H1RunnerError(f"duplicate replay response for sample/clause: {key}")
        responses[key] = row

    expected_plan_keys = {plan.key for plan in selected_plans}
    missing = sorted(expected_plan_keys - set(responses))
    extra = sorted(set(responses) - expected_plan_keys)
    if missing:
        raise H1RunnerError(f"replay responses missing for selected plans: {missing}")
    if extra:
        raise H1RunnerError(f"replay responses contain unselected plans: {extra}")

    for plan in selected_plans:
        row = responses[plan.key]
        if row.get("clause_index") != plan.clause_index:
            raise H1RunnerError(
                f"replay response for {plan.sample_id}/{plan.clause_id} clause_index "
                f"{row.get('clause_index')!r} != plan {plan.clause_index}"
            )
        if row.get("prompt_variant") != variant:
            raise H1RunnerError(
                f"replay response for {plan.sample_id}/{plan.clause_id} prompt_variant "
                f"{row.get('prompt_variant')!r} != run variant {variant!r}"
            )
        if row.get("prompt_sha256") != prompt_sha256:
            raise H1RunnerError(
                f"replay response for {plan.sample_id}/{plan.clause_id} prompt SHA mismatch: "
                f"expected {prompt_sha256}, got {row.get('prompt_sha256')!r}"
            )
        expected_b0 = _prediction_hash(records[plan.sample_id])
        if row.get("b0_prediction_sha256") != expected_b0:
            raise H1RunnerError(
                f"replay response for {plan.sample_id}/{plan.clause_id} B0 prediction hash "
                f"mismatch: expected {expected_b0}, got {row.get('b0_prediction_sha256')!r}"
            )
    return responses


def load_transport_replay_rows(
    path: Path,
    selected_plans: Sequence[RepairPlan],
    records: Mapping[str, Mapping[str, Any]],
    prompt_sha256: str,
    variant: str,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Load and bind an offline transport-replay row file (S2.8D-R1).

    Same strict binding as :func:`load_replay_responses` (request_id
    unique, (sample_id, clause_id) set exactly equal to the selected
    plans, clause_index / prompt_sha256 / prompt_variant /
    b0_prediction_sha256 each verified), plus a full response envelope in
    ``response_body`` with optional ``content_type`` / ``http_status``.
    Any missing, duplicate, extra, or mismatched row fails closed.
    """
    required_keys = {
        "request_id",
        "sample_id",
        "clause_id",
        "clause_index",
        "prompt_sha256",
        "prompt_variant",
        "b0_prediction_sha256",
        "response_body",
    }
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    request_ids: set[str] = set()
    for index, row in enumerate(_read_json_values(path)):
        if not required_keys.issubset(set(row)):
            raise H1RunnerError(
                f"transport replay row {index} must contain keys "
                f"{sorted(required_keys)}; got {sorted(row)}"
            )
        request_id = row.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise H1RunnerError(f"transport replay row {index} request_id must be a non-empty string")
        if request_id in request_ids:
            raise H1RunnerError(f"duplicate transport replay request_id: {request_id!r}")
        request_ids.add(request_id)
        body = row.get("response_body")
        if not isinstance(body, str):
            raise H1RunnerError(f"transport replay row {index} response_body must be a string")
        content_type = row.get("content_type")
        if content_type is not None and not isinstance(content_type, str):
            raise H1RunnerError(f"transport replay row {index} content_type must be a string or absent")
        http_status = row.get("http_status")
        if http_status is not None and (
            isinstance(http_status, bool) or not isinstance(http_status, int)
        ):
            raise H1RunnerError(f"transport replay row {index} http_status must be an int or absent")
        key = (str(row.get("sample_id")), str(row.get("clause_id")))
        if not all(key):
            raise H1RunnerError(f"transport replay row {index} lacks sample_id or clause_id")
        if key in rows:
            raise H1RunnerError(f"duplicate transport replay row for sample/clause: {key}")
        rows[key] = row

    expected_plan_keys = {plan.key for plan in selected_plans}
    missing = sorted(expected_plan_keys - set(rows))
    extra = sorted(set(rows) - expected_plan_keys)
    if missing:
        raise H1RunnerError(f"transport replay rows missing for selected plans: {missing}")
    if extra:
        raise H1RunnerError(f"transport replay rows contain unselected plans: {extra}")

    for plan in selected_plans:
        row = rows[plan.key]
        if row.get("clause_index") != plan.clause_index:
            raise H1RunnerError(
                f"transport replay row for {plan.sample_id}/{plan.clause_id} clause_index "
                f"{row.get('clause_index')!r} != plan {plan.clause_index}"
            )
        if row.get("prompt_variant") != variant:
            raise H1RunnerError(
                f"transport replay row for {plan.sample_id}/{plan.clause_id} prompt_variant "
                f"{row.get('prompt_variant')!r} != run variant {variant!r}"
            )
        if row.get("prompt_sha256") != prompt_sha256:
            raise H1RunnerError(
                f"transport replay row for {plan.sample_id}/{plan.clause_id} prompt SHA "
                f"mismatch: expected {prompt_sha256}, got {row.get('prompt_sha256')!r}"
            )
        expected_b0 = _prediction_hash(records[plan.sample_id])
        if row.get("b0_prediction_sha256") != expected_b0:
            raise H1RunnerError(
                f"transport replay row for {plan.sample_id}/{plan.clause_id} B0 prediction "
                f"hash mismatch: expected {expected_b0}, got {row.get('b0_prediction_sha256')!r}"
            )
    return rows


def load_frozen_transport_replay_rows(
    path: Path,
    selected_plans: Sequence[RepairPlan],
    records: Mapping[str, Mapping[str, Any]],
    prompt_sha256: str,
    variant: str,
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[tuple[str, str]]]:
    """S2.8D-R6: load offline transport replay rows for a frozen pilot that
    may have stopped early.

    Every provided row must bind exactly like :func:`load_transport_replay_rows`
    (request_id unique, sample/clause/index/prompt/B0 verified), and every row
    must belong to the frozen selection.  Rows are allowed to be a strict
    SUBSET of the frozen plans: the missing plans are returned as
    ``missing_keys`` so the caller can preserve them as
    ``pilot_early_stop_not_called`` (they are never replayed or fabricated).

    Raises :class:`H1RunnerError` on any structural/binding violation or on an
    extra (unfrozen) row.
    """
    required_keys = {
        "request_id",
        "sample_id",
        "clause_id",
        "clause_index",
        "prompt_sha256",
        "prompt_variant",
        "b0_prediction_sha256",
        "response_body",
    }
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    request_ids: set[str] = set()
    expected_keys = {plan.key for plan in selected_plans}
    for index, row in enumerate(_read_json_values(path)):
        if not required_keys.issubset(set(row)):
            raise H1RunnerError(
                f"frozen transport replay row {index} must contain keys "
                f"{sorted(required_keys)}; got {sorted(row)}"
            )
        request_id = row.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise H1RunnerError(f"frozen transport replay row {index} request_id must be a non-empty string")
        if request_id in request_ids:
            raise H1RunnerError(f"duplicate frozen transport replay request_id: {request_id!r}")
        request_ids.add(request_id)
        body = row.get("response_body")
        if not isinstance(body, str):
            raise H1RunnerError(f"frozen transport replay row {index} response_body must be a string")
        content_type = row.get("content_type")
        if content_type is not None and not isinstance(content_type, str):
            raise H1RunnerError(f"frozen transport replay row {index} content_type must be a string or absent")
        http_status = row.get("http_status")
        if http_status is not None and (isinstance(http_status, bool) or not isinstance(http_status, int)):
            raise H1RunnerError(f"frozen transport replay row {index} http_status must be an int or absent")
        key = (str(row.get("sample_id")), str(row.get("clause_id")))
        if not all(key):
            raise H1RunnerError(f"frozen transport replay row {index} lacks sample_id or clause_id")
        if key in rows:
            raise H1RunnerError(f"duplicate frozen transport replay row for sample/clause: {key}")
        if key not in expected_keys:
            raise H1RunnerError(
                f"frozen transport replay row for unselected plan: {key[0]}/{key[1]}"
            )
        rows[key] = row

    for plan in selected_plans:
        if plan.key not in rows:
            continue
        row = rows[plan.key]
        if row.get("clause_index") != plan.clause_index:
            raise H1RunnerError(
                f"frozen transport replay row for {plan.sample_id}/{plan.clause_id} clause_index "
                f"{row.get('clause_index')!r} != plan {plan.clause_index}"
            )
        if row.get("prompt_variant") != variant:
            raise H1RunnerError(
                f"frozen transport replay row for {plan.sample_id}/{plan.clause_id} prompt_variant "
                f"{row.get('prompt_variant')!r} != run variant {variant!r}"
            )
        if row.get("prompt_sha256") != prompt_sha256:
            raise H1RunnerError(
                f"frozen transport replay row for {plan.sample_id}/{plan.clause_id} prompt SHA "
                f"mismatch: expected {prompt_sha256}, got {row.get('prompt_sha256')!r}"
            )
        expected_b0 = _prediction_hash(records[plan.sample_id])
        if row.get("b0_prediction_sha256") != expected_b0:
            raise H1RunnerError(
                f"frozen transport replay row for {plan.sample_id}/{plan.clause_id} B0 prediction "
                f"hash mismatch: expected {expected_b0}, got {row.get('b0_prediction_sha256')!r}"
            )
    missing_keys = [plan.key for plan in selected_plans if plan.key not in rows]
    return rows, missing_keys


_TRANSPORT_EVENT_KEYS = (
    "response_body_sha256",
    "response_content_sha256",
    "response_id",
    "response_object",
    "finish_reason",
    "usage",
    "extraction_status",
    "extraction_source",
    "reasoning_present",
    "reasoning_utf8_length",
    "reasoning_sha256",
    "tool_call_count",
    "tool_call_summaries",
    "transport_http_status",
    "transport_request_policy",
    "safe_endpoint",
)


def _attach_transport_fields(
    event: dict[str, Any],
    decode: Mapping[str, Any],
    *,
    request_policy: Mapping[str, Any] | None,
    endpoint_descriptor: Mapping[str, Any] | None,
    http_status: int | None,
) -> None:
    """Attach the decoded transport audit fields to a plan event (S2.8D-R1).

    Only hashes, statuses, lengths, and booleans -- never reasoning text,
    tool-call arguments, headers, or credentials.
    """
    event["response_body_sha256"] = decode.get("response_body_sha256")
    event["response_content_sha256"] = decode.get("response_content_sha256")
    event["response_id"] = decode.get("response_id")
    event["response_object"] = decode.get("response_object")
    event["finish_reason"] = decode.get("finish_reason")
    event["usage"] = dict(decode.get("usage") or {})
    event["extraction_status"] = decode.get("status")
    event["extraction_source"] = decode.get("extraction_source")
    event["reasoning_present"] = decode.get("reasoning_present")
    event["reasoning_utf8_length"] = decode.get("reasoning_utf8_length")
    event["reasoning_sha256"] = decode.get("reasoning_sha256")
    event["tool_call_count"] = decode.get("tool_call_count")
    event["tool_call_summaries"] = list(decode.get("tool_call_summaries") or [])
    event["transport_http_status"] = http_status
    if request_policy is not None:
        event["transport_request_policy"] = dict(request_policy)
    if endpoint_descriptor is not None:
        event["safe_endpoint"] = dict(endpoint_descriptor)


def _build_user_prompt(
    prompt: Any,
    record: Mapping[str, Any],
    plan: RepairPlan,
    context_clause: Mapping[str, Any] | None = None,
) -> str:
    """Render the user prompt for one repair plan.

    ``context_clause`` is the (possibly masked) clause context shown to the
    model; when None, the plain B0 clause is used (full_b0_v4 behavior).
    """
    clause = (
        context_clause
        if context_clause is not None
        else record["clauses"][plan.clause_index]
    )
    return prompt.user_prompt_template.format(
        sample_id=plan.sample_id,
        source_id=record["source_id"],
        source_text=record["source_text"],
        clause_id=plan.clause_id,
        current_clause_json=json.dumps(clause, indent=2, ensure_ascii=False),
        repair_fields_csv=", ".join(plan.repair_fields),
        repair_reasons_csv=", ".join(plan.reasons),
    )


def _build_context_audit(
    clause: Mapping[str, Any],
    plan: RepairPlan,
    variant: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the (possibly masked) clause context and its leak audit.

    Returns ``(context_clause, audit)``.  For ``masked_selected_v5`` the
    requested repair fields are replaced by the masking sentinel; for
    ``full_b0_v4`` the context is the plain clause.  The audit records
    only hashes, field names, and booleans -- never source text, prompt
    text, or masked values.  A leak (selected IDs exposed through an
    unmasked relation) raises ``H1RunnerError`` so no request is built.
    """
    pre_hash = _json_hash(dict(clause))
    if variant == "masked_selected_v5":
        context_clause, masked_fields, dependency_fields = build_masked_clause_context(
            clause, plan.repair_fields
        )
    else:
        context_clause, masked_fields, dependency_fields = dict(clause), (), ()
    audit = audit_masked_context(
        clause, context_clause, masked_fields, dependency_fields
    )
    audit["original_record_unchanged"] = _json_hash(dict(clause)) == pre_hash
    audit["variant"] = variant
    if audit["selected_ids_exposed_in_unselected_relations"]:
        raise H1RunnerError(
            f"masked context leak for {plan.sample_id}/{plan.clause_id}: "
            f"selected IDs exposed in unselected relations: "
            f"{audit['exposed_relation_entries']}"
        )
    return context_clause, audit


def _summary_by_sample(
    batch: Sequence[LoadedB0],
    outputs: Mapping[str, dict[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_sample: dict[str, list[Mapping[str, Any]]] = {}
    for event in events:
        by_sample.setdefault(str(event["sample_id"]), []).append(event)
    rows: list[dict[str, Any]] = []
    for item in batch:
        sample_id = item.record["sample_id"]
        sample_events = by_sample.get(sample_id, [])
        rows.append(
            {
                "sample_id": sample_id,
                "b0_prediction_sha256": _prediction_hash(item.record),
                "h1_prediction_sha256": _prediction_hash(outputs[sample_id]),
                "triggered": bool(sample_events),
                "selected_for_call": any(bool(event.get("selected_for_call")) for event in sample_events),
                "llm_called": any(bool(event.get("llm_call_performed")) for event in sample_events),
                "patch_proposed": any(bool(event.get("patch_proposed")) for event in sample_events),
                "patch_accepted": any(bool(event.get("patch_accepted")) for event in sample_events),
                "prediction_changed": _prediction_hash(item.record) != _prediction_hash(outputs[sample_id]),
                "patch_events": [copy.deepcopy(event) for event in sample_events],
            }
        )
    return rows


def _bind_frozen_plan_keys(
    config: Mapping[str, Any],
    plans: Sequence[RepairPlan],
) -> list[RepairPlan]:
    """S2.8D-R5: resolve the frozen pilot selection against the CURRENT
    repair plans (fail closed on any mismatch).  Returns the ordered
    ``RepairPlan`` list for the frozen execution order."""
    entries = list(config["selected_plans"])
    by_key = {plan.key: plan for plan in plans}
    errors: list[str] = []
    selected: list[RepairPlan] = []
    for entry in sorted(entries, key=lambda e: e["execution_order"]):
        key = (str(entry["sample_id"]), str(entry["clause_id"]))
        plan = by_key.get(key)
        if plan is None:
            errors.append(f"frozen plan not in current triggered plans: {plan_key_str(entry)}")
            continue
        if plan.clause_index != int(entry["clause_index"]):
            errors.append(f"{plan_key_str(entry)} clause_index mismatch")
        if list(plan.repair_fields) != list(entry["repair_fields"]):
            errors.append(f"{plan_key_str(entry)} repair_fields mismatch")
        if list(plan.reasons) != list(entry["reasons"]):
            errors.append(f"{plan_key_str(entry)} reasons mismatch")
        if plan.risk_score != int(entry["risk_score"]):
            errors.append(f"{plan_key_str(entry)} risk_score mismatch")
        if entry.get("historical_called") is not False:
            errors.append(f"{plan_key_str(entry)} historical_called must be false")
        selected.append(plan)
    if len(selected) != len(entries):
        errors.append(f"frozen plan resolved {len(selected)} != {len(entries)} plans")
    if len({plan.key for plan in selected}) != len(selected):
        errors.append("duplicate plan keys in frozen selection")
    if len({plan.sample_id for plan in selected}) != len(selected):
        errors.append("duplicate samples in frozen selection")
    historical_keys = set(config.get("historical_calls", {}).get("plan_keys", []))
    overlap = sorted(
        f"{plan.sample_id}/{plan.clause_id}"
        for plan in selected
        if f"{plan.sample_id}/{plan.clause_id}" in historical_keys
    )
    if overlap:
        errors.append(f"selected plans overlap historical called keys: {overlap}")
    if errors:
        raise H1RunnerError("frozen plan binding failed: " + "; ".join(errors))
    return selected


def _bind_frozen_plan_hashes(
    config: Mapping[str, Any],
    selected: Sequence[RepairPlan],
    original_records: Mapping[str, Mapping[str, Any]],
    context_audits: Mapping[tuple[str, str], dict[str, Any]],
    prompt_sha256: str,
) -> None:
    """S2.8D-R5: verify per-plan record/context binding hashes.  Raises
    ``H1RunnerError`` on any mismatch (caller fails closed)."""
    entries_by_key = {
        (str(e["sample_id"]), str(e["clause_id"])): e for e in config["selected_plans"]
    }
    errors: list[str] = []
    for plan in selected:
        entry = entries_by_key[plan.key]
        record = original_records.get(plan.sample_id)
        if record is None:
            errors.append(f"frozen sample missing from B0: {plan.sample_id}")
            continue
        if _prediction_hash(record) != entry["b0_prediction_sha256"]:
            errors.append(f"{plan_key_str(entry)} b0_prediction_sha256 mismatch")
        clause = record["clauses"][plan.clause_index]
        identity_hash = _json_hash(
            {"clause_id": clause.get("clause_id"), "clause_span": clause.get("clause_span")}
        )
        if identity_hash != entry["clause_identity_hash"]:
            errors.append(f"{plan_key_str(entry)} clause_identity_hash mismatch")
        audit = context_audits.get(plan.key) or {}
        if audit.get("masked_context_sha256") != entry["rendered_masked_context_hash"]:
            errors.append(f"{plan_key_str(entry)} rendered_masked_context_hash mismatch")
        if entry.get("prompt_sha256") != prompt_sha256:
            errors.append(f"{plan_key_str(entry)} prompt_sha256 mismatch")
    if errors:
        raise H1RunnerError("frozen plan hash binding failed: " + "; ".join(errors))


def _verify_continuation_binding(
    config: Mapping[str, Any],
    args: argparse.Namespace,
    prompt_sha256: str,
) -> None:
    """S2.8D-R6C1: fail-closed verification of the continuation plan against
    the parent frozen plan, the prior R6 run evidence, B0, and prompt.

    Raises :class:`H1RunnerError` on any mismatch (caller aborts before any
    API call).  Reads only hashes/IDs/counts from the prior run artifacts.
    """
    errors: list[str] = []

    def fail(msg: str) -> None:
        errors.append(msg)

    # 1. Parent frozen plan file hash + selected keys hash + full 1..10 set.
    parent_path = Path(config["parent_frozen_plan_path"])
    if not parent_path.exists():
        fail(f"parent frozen plan missing: {parent_path}")
    else:
        parent_cfg = json.loads(parent_path.read_text(encoding="utf-8"))
        if _sha256_file(parent_path) != config["parent_frozen_plan_sha256"]:
            fail("parent frozen plan SHA-256 mismatch")
        if selected_plan_keys_sha256(parent_cfg.get("selected_plans") or []) != config["parent_selected_plan_keys_sha256"]:
            fail("parent selected plan keys SHA-256 mismatch")
        parent_entries = parent_cfg.get("selected_plans") or []
        parent_orders = sorted(e.get("execution_order") for e in parent_entries if isinstance(e, Mapping))
        if parent_orders != list(range(1, 11)):
            fail("parent frozen plan does not contain original orders 1..10")

    # 2-3. Prior run manifest + capture hashes.
    prior = config.get("prior_run") or {}
    prior_manifest = Path(prior.get("manifest_path", ""))
    if not prior_manifest.exists() or _sha256_file(prior_manifest) != prior.get("manifest_sha256"):
        fail("prior R6 manifest SHA-256 mismatch or missing")
    prior_capture = Path(prior.get("transport_capture_path", ""))
    if not prior_capture.exists() or _sha256_file(prior_capture) != prior.get("transport_capture_sha256"):
        fail("prior R6 transport capture SHA-256 mismatch or missing")
    prior_telemetry = Path(prior.get("telemetry_path", ""))
    if not prior_telemetry.exists():
        fail("prior R6 telemetry missing")

    # 4. Prior telemetry proves exactly orders 1..5 called, at most once each.
    if parent_path.exists():
        parent_cfg = json.loads(parent_path.read_text(encoding="utf-8"))
        parent_entries = parent_cfg.get("selected_plans") or []
        order_to_key = {
            e["execution_order"]: (str(e["sample_id"]), str(e["clause_id"]))
            for e in parent_entries
            if isinstance(e, Mapping) and "execution_order" in e
        }
        prior_called = set()
        if prior_telemetry.exists():
            for line in prior_telemetry.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                if row.get("llm_called"):
                    events = row.get("patch_events") or []
                    for ev in events:
                        if ev.get("llm_call_performed"):
                            prior_called.add((str(row.get("sample_id")), str(ev.get("clause_id"))))
        expected_first = {order_to_key.get(o) for o in (1, 2, 3, 4, 5)}
        if prior_called != expected_first:
            fail(
                f"prior R6 telemetry called set does not equal original orders 1..5: "
                f"got {sorted(prior_called)}"
            )
        # 5. Each order 1..5 called at most once (unique capture request ids).
        prior_request_ids = []
        if prior_capture.exists():
            for line in prior_capture.read_text(encoding="utf-8").splitlines():
                prior_request_ids.append(json.loads(line).get("request_id"))
        if len(prior_request_ids) != len(set(prior_request_ids)):
            fail("prior R6 capture contains duplicate request ids (a plan called more than once)")
        # 6. No order 6..10 in prior called set.
        expected_remaining = {order_to_key.get(o) for o in (6, 7, 8, 9, 10)}
        if prior_called & expected_remaining:
            fail("prior R6 evidence shows order 6..10 were already called")
        # prior called keys sha
        called_key_list = sorted(f"{s}/{c}" for s, c in prior_called)
        called_sha = hashlib.sha256("\n".join(called_key_list).encode("utf-8")).hexdigest()
        if called_sha != prior.get("called_plan_keys_sha256"):
            fail("prior called plan keys SHA-256 mismatch")

    # 7. Continuation exactly original orders 6..10; union == parent 10.
    entries = config.get("selected_plans") or []
    if sorted(e.get("original_execution_order") for e in entries if isinstance(e, Mapping)) != [6, 7, 8, 9, 10]:
        fail("continuation original orders must be exactly 6..10")
    remaining_keys = {continuation_plan_key(e) for e in entries if isinstance(e, Mapping)}
    if len(remaining_keys) != 5:
        fail("continuation must contain exactly 5 distinct plans")
    if len({s for s, _ in remaining_keys}) != 5:
        fail("continuation samples must be distinct")
    if parent_path.exists():
        parent_cfg = json.loads(parent_path.read_text(encoding="utf-8"))
        parent_keys = {
            (str(e["sample_id"]), str(e["clause_id"]))
            for e in parent_cfg.get("selected_plans", [])
            if isinstance(e, Mapping)
        }
        if remaining_keys & prior_called:
            fail("continuation overlaps prior called plans")
        if (remaining_keys | prior_called) != parent_keys:
            fail("continuation + prior called does not exactly cover the parent 10 plans")

    # 8. B0 / prompt / model.
    b0 = config.get("b0") or {}
    if _sha256_file(args.b0_predictions) != b0.get("attempts_sha256"):
        fail("continuation B0 attempts SHA-256 mismatch")
    if args.b0_manifest is None or _sha256_file(args.b0_manifest) != b0.get("manifest_sha256"):
        fail("continuation B0 manifest SHA-256 mismatch")
    if args.prompt_variant != config.get("prompt_variant"):
        fail("continuation prompt variant mismatch")
    if prompt_sha256 != config.get("prompt_sha256"):
        fail("continuation prompt SHA-256 mismatch")
    if config.get("model") != REAL_CALL_REQUIRED_MODEL:
        fail(f"continuation model must be {REAL_CALL_REQUIRED_MODEL!r}")

    if errors:
        raise H1RunnerError("continuation binding failed: " + "; ".join(errors))


def _bind_continuation_plan_keys(
    config: Mapping[str, Any],
    plans: Sequence[RepairPlan],
) -> list[RepairPlan]:
    """S2.8D-R6C1: resolve the continuation selection against the CURRENT
    repair plans (fail closed on any mismatch).  Returns the ordered
    ``RepairPlan`` list in continuation execution order."""
    entries = list(config["selected_plans"])
    by_key = {plan.key: plan for plan in plans}
    errors: list[str] = []
    selected: list[RepairPlan] = []
    for entry in sorted(entries, key=lambda e: e["continuation_execution_order"]):
        key = (str(entry["sample_id"]), str(entry["clause_id"]))
        plan = by_key.get(key)
        if plan is None:
            errors.append(f"continuation plan not in current triggered plans: {continuation_plan_key_str(entry)}")
            continue
        if plan.clause_index != int(entry["clause_index"]):
            errors.append(f"{continuation_plan_key_str(entry)} clause_index mismatch")
        if list(plan.repair_fields) != list(entry["repair_fields"]):
            errors.append(f"{continuation_plan_key_str(entry)} repair_fields mismatch")
        if list(plan.reasons) != list(entry["reasons"]):
            errors.append(f"{continuation_plan_key_str(entry)} reasons mismatch")
        if plan.risk_score != int(entry["risk_score"]):
            errors.append(f"{continuation_plan_key_str(entry)} risk_score mismatch")
        if entry.get("prior_called") is not False:
            errors.append(f"{continuation_plan_key_str(entry)} prior_called must be false")
        selected.append(plan)
    if len(selected) != len(entries):
        errors.append(f"continuation resolved {len(selected)} != {len(entries)} plans")
    if len({plan.key for plan in selected}) != len(selected):
        errors.append("duplicate continuation plan keys")
    if len({plan.sample_id for plan in selected}) != len(selected):
        errors.append("duplicate samples in continuation selection")
    if errors:
        raise H1RunnerError("continuation plan binding failed: " + "; ".join(errors))
    return selected


def _bind_continuation_plan_hashes(
    config: Mapping[str, Any],
    selected: Sequence[RepairPlan],
    original_records: Mapping[str, Mapping[str, Any]],
    context_audits: Mapping[tuple[str, str], dict[str, Any]],
    prompt_sha256: str,
) -> None:
    """S2.8D-R6C1: verify per-plan record/context binding hashes.  Raises
    ``H1RunnerError`` on any mismatch (caller fails closed)."""
    entries_by_key = {
        (str(e["sample_id"]), str(e["clause_id"])): e for e in config["selected_plans"]
    }
    errors: list[str] = []
    for plan in selected:
        entry = entries_by_key[plan.key]
        record = original_records.get(plan.sample_id)
        if record is None:
            errors.append(f"continuation sample missing from B0: {plan.sample_id}")
            continue
        if _prediction_hash(record) != entry["b0_prediction_sha256"]:
            errors.append(f"{continuation_plan_key_str(entry)} b0_prediction_sha256 mismatch")
        clause = record["clauses"][plan.clause_index]
        identity_hash = _json_hash(
            {"clause_id": clause.get("clause_id"), "clause_span": clause.get("clause_span")}
        )
        if identity_hash != entry["clause_identity_hash"]:
            errors.append(f"{continuation_plan_key_str(entry)} clause_identity_hash mismatch")
        audit = context_audits.get(plan.key) or {}
        if audit.get("masked_context_sha256") != entry["rendered_masked_context_hash"]:
            errors.append(f"{continuation_plan_key_str(entry)} rendered_masked_context_hash mismatch")
        if entry.get("prompt_sha256") != prompt_sha256:
            errors.append(f"{continuation_plan_key_str(entry)} prompt_sha256 mismatch")
    if errors:
        raise H1RunnerError("continuation hash binding failed: " + "; ".join(errors))


def _maybe_early_stop_events(
    *,
    plan: RepairPlan,
    llm_calls: int,
    consecutive_failures: int,
    provider_model: str | None,
    capture_bound: bool,
    required_model: str,
    hard_call_cap: int,
    frozen_order: Sequence[tuple[str, str]],
    frozen_order_set: set[tuple[str, str]],
    frozen_processed: int,
    selected_by_key: Mapping[tuple[str, str], RepairPlan],
    events: list[dict[str, Any]],
    not_called_keys: list[str],
) -> str | None:
    """S2.8D-R5: evaluate the frozen-pilot early-stop contract after one real
    call.  On a violation, append ``pilot_early_stop_not_called`` events for
    every remaining frozen plan and return the reason; otherwise ``None``."""
    if plan.key not in frozen_order_set:
        return None
    expected_key = (
        frozen_order[frozen_processed - 1]
        if 1 <= frozen_processed <= len(frozen_order)
        else None
    )
    reason = evaluate_early_stop(
        calls_made=llm_calls,
        consecutive_failures=consecutive_failures,
        provider_returned_model=provider_model,
        required_model=required_model,
        capture_bound=capture_bound,
        plan_key_ok=expected_key == plan.key,
        hard_call_cap=hard_call_cap,
    )
    if reason is None:
        return None
    index = frozen_order.index(plan.key)
    for remaining_key in frozen_order[index + 1:]:
        remaining_plan = selected_by_key[remaining_key]
        not_event = _patch_event_base(remaining_plan)
        not_event["selected_for_call"] = True
        not_event["status"] = EARLY_STOP_NOT_CALLED
        not_event["early_stop_reason"] = reason
        events.append(not_event)
        not_called_keys.append(f"{remaining_plan.sample_id}/{remaining_plan.clause_id}")
    return reason


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--b0-predictions",
        type=Path,
        required=True,
        help="Persisted B0 attempts/predictions JSON or JSONL; H1 never reruns B0.",
    )
    parser.add_argument("--b0-manifest", type=Path)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    parser.add_argument("--telemetry", type=Path)
    parser.add_argument(
        "--prompt-variant",
        choices=PROMPT_VARIANTS,
        default=DEFAULT_PROMPT_VARIANT,
        help="full_b0_v4 keeps the historical unmasked prompt; "
        "masked_selected_v5 masks the requested repair fields out of the "
        "B0 context before rendering (anchoring ablation).",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--offline-patches", type=Path)
    mode.add_argument("--offline-replay", action="store_true")
    mode.add_argument("--offline-transport-replay", action="store_true")
    mode.add_argument("--allow-llm", action="store_true")
    parser.add_argument(
        "--responses-jsonl",
        type=Path,
        help="Offline replay responses (required with --offline-replay); "
        "each response must bind request_id/sample_id/clause_id/clause_index/"
        "prompt_sha256/prompt_variant/b0_prediction_sha256/response_content.",
    )
    parser.add_argument(
        "--transport-responses-jsonl",
        type=Path,
        help="Offline transport replay rows (required with "
        "--offline-transport-replay): same strict binding as "
        "--responses-jsonl, plus a full response envelope in 'response_body' "
        "and optional 'content_type'/'http_status'. Decoded with the SAME "
        "pure decoder used by the real transport.",
    )
    parser.add_argument(
        "--transport-capture",
        type=Path,
        help="Sanitized transport capture JSONL (REQUIRED for --allow-llm "
        "real runs; refused before any call otherwise). Never contains "
        "headers, credentials, reasoning text, or tool arguments.",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Model ID for --allow-llm real runs. REQUIRED for real runs; "
        "overrides profile/.env model selection. The resolved value must "
        f"equal {REAL_CALL_REQUIRED_MODEL!r} or the run aborts before any call.",
    )
    parser.add_argument(
        "--exclude-plan",
        action="append",
        default=[],
        metavar="SAMPLE/CLAUSE",
        help="Drop a plan from the selected set (e.g. the canary plan) so a "
        "follow-up run covers the remaining frozen plans without re-calling "
        "it. Trigger/risk/budget allocation is unchanged; this only filters "
        "the final candidate set.",
    )
    parser.add_argument(
        "--frozen-plan",
        type=Path,
        help="S2.8D-R5 frozen small-pilot plan config path. When set, the "
        "selected plan set is EXACTLY the frozen 10 plans in execution "
        "order; --exclude-plan is forbidden, --max-calls must equal 10, and "
        "every frozen entry must match the current B0/plans/context binding.",
    )
    parser.add_argument(
        "--continuation-plan",
        type=Path,
        help="S2.8D-R6C1 continuation-plan config path. When set, the "
        "selected plan set is EXACTLY the remaining never-called plans of the "
        "parent frozen plan (original orders 6-10); --frozen-plan and "
        "--exclude-plan are forbidden, --max-calls must equal 5, and the "
        "parent frozen plan + prior-run evidence must bind exactly.",
    )
    parser.add_argument("--max-calls", type=int, default=50)
    parser.add_argument("--inter-call-delay", type=float, default=0.5)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--development", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _make_parser().parse_args(argv)
    if args.max_calls < 0:
        print("Refusing to run: --max-calls must be non-negative.")
        return 2
    if args.allow_llm and args.max_calls < 1:
        print("Refusing to run: real LLM mode requires --max-calls >= 1.")
        return 2
    if args.offline_replay and args.responses_jsonl is None:
        print("Refusing to run: --offline-replay requires --responses-jsonl.")
        return 2
    if not args.offline_replay and args.responses_jsonl is not None:
        print("Refusing to run: --responses-jsonl requires --offline-replay.")
        return 2
    if args.offline_transport_replay and args.transport_responses_jsonl is None:
        print("Refusing to run: --offline-transport-replay requires --transport-responses-jsonl.")
        return 2
    if not args.offline_transport_replay and args.transport_responses_jsonl is not None:
        print("Refusing to run: --transport-responses-jsonl requires --offline-transport-replay.")
        return 2
    if args.allow_llm and args.transport_capture is None:
        print("Refusing to run: --allow-llm requires --transport-capture (no call was made).")
        return 2
    if not args.allow_llm and args.transport_capture is not None:
        print("Refusing to run: --transport-capture requires --allow-llm.")
        return 2
    if args.frozen_plan is not None and args.exclude_plan:
        print("Refusing to run: --frozen-plan cannot be combined with --exclude-plan.")
        return 2
    if args.frozen_plan is not None and args.max_calls != EXPECTED_HARD_CALL_CAP:
        print(
            f"Refusing to run: --frozen-plan requires --max-calls "
            f"{EXPECTED_HARD_CALL_CAP} (no call was made)."
        )
        return 2
    if args.frozen_plan is not None and (args.offline_replay or args.offline_patches is not None):
        print(
            "Refusing to run: --frozen-plan is only supported with --plan-only, "
            "--allow-llm, or --offline-transport-replay."
        )
        return 2
    if args.continuation_plan is not None and (args.frozen_plan is not None or args.exclude_plan):
        print(
            "Refusing to run: --continuation-plan cannot be combined with "
            "--frozen-plan or --exclude-plan."
        )
        return 2
    if args.continuation_plan is not None and args.max_calls != EXPECTED_CONTINUATION_HARD_CALL_CAP:
        print(
            f"Refusing to run: --continuation-plan requires --max-calls "
            f"{EXPECTED_CONTINUATION_HARD_CALL_CAP} (no call was made)."
        )
        return 2
    if args.continuation_plan is not None and (args.offline_replay or args.offline_patches is not None):
        print(
            "Refusing to run: --continuation-plan is only supported with "
            "--plan-only, --allow-llm, or --offline-transport-replay."
        )
        return 2
    frozen_plan_config: dict[str, Any] | None = None
    if args.frozen_plan is not None:
        try:
            frozen_plan_config = load_frozen_plan(args.frozen_plan)
        except (OSError, ValueError) as exc:
            print(f"Refusing to run: invalid frozen plan config: {exc}")
            return 2
    continuation_plan_config: dict[str, Any] | None = None
    if args.continuation_plan is not None:
        try:
            continuation_plan_config = load_continuation_plan(args.continuation_plan)
        except (OSError, ValueError) as exc:
            print(f"Refusing to run: invalid continuation plan config: {exc}")
            return 2
    telemetry_path = args.telemetry or _derive_telemetry_path(args.output)
    targets = (args.output, telemetry_path, args.manifest)
    if args.transport_capture is not None:
        targets = (*targets, args.transport_capture)
    for target in targets:
        allowed, reason = _gate_write(target, args.development)
        if not allowed:
            print(f"Refusing to write {target}: {reason}")
            return 2
        if target.exists() and not args.overwrite:
            print(f"Refusing to overwrite existing artifact: {target}")
            return 2

    try:
        prompt = load_prompt(_PROMPT_NAME_BY_VARIANT[args.prompt_variant])
        b0_manifest = verify_b0_manifest(args.b0_predictions, args.b0_manifest)
        batch = load_b0_predictions(args.b0_predictions)
        offline_patches = load_offline_patches(args.offline_patches) if args.offline_patches else {}
    except (H1RunnerError, OSError, json.JSONDecodeError) as exc:
        print(f"Refusing to run: {exc}")
        return 2

    if frozen_plan_config is not None:
        b0_cfg = frozen_plan_config["b0"]
        if _sha256_file(args.b0_predictions) != b0_cfg["attempts_sha256"]:
            print("Refusing to run: frozen plan B0 attempts SHA-256 mismatch.")
            return 2
        if args.b0_manifest is None or _sha256_file(args.b0_manifest) != b0_cfg["manifest_sha256"]:
            print("Refusing to run: frozen plan B0 manifest SHA-256 mismatch.")
            return 2
        if args.prompt_variant != frozen_plan_config["prompt_variant"]:
            print("Refusing to run: frozen plan prompt variant mismatch.")
            return 2
        if prompt.sha256 != frozen_plan_config["prompt_sha256"]:
            print("Refusing to run: frozen plan prompt SHA-256 mismatch.")
            return 2

    if continuation_plan_config is not None:
        # S2.8D-R6C1: verify parent frozen plan, prior-run evidence, B0 and
        # prompt bindings BEFORE any selection/API call (fail closed).
        try:
            _verify_continuation_binding(
                continuation_plan_config,
                args,
                prompt.sha256,
            )
        except H1RunnerError as exc:
            print(f"Refusing to run: {exc}")
            return 2

    plans = build_repair_plans(batch)
    if args.frozen_plan is not None:
        # S2.8D-R5: the frozen pilot plan is the source of truth for the
        # selection.  Verified against the current repair plans below.
        try:
            selected = _bind_frozen_plan_keys(frozen_plan_config, plans)
        except H1RunnerError as exc:
            print(f"Refusing to run: {exc}")
            return 2
    elif args.continuation_plan is not None:
        # S2.8D-R6C1: the continuation plan selects exactly the remaining
        # never-called plans (original orders 6-10).
        try:
            selected = _bind_continuation_plan_keys(continuation_plan_config, plans)
        except H1RunnerError as exc:
            print(f"Refusing to run: {exc}")
            return 2
    else:
        selected = allocate_repair_calls(plans, args.max_calls)
    excluded_keys: set[tuple[str, str]] = set()
    for spec_key in args.exclude_plan:
        parts = spec_key.split("/", 1)
        if len(parts) != 2 or not all(parts):
            print(f"Refusing to run: invalid --exclude-plan {spec_key!r} (expected SAMPLE/CLAUSE).")
            return 2
        excluded_keys.add((parts[0], parts[1]))
    unknown_excludes = sorted(excluded_keys - {plan.key for plan in plans})
    if unknown_excludes:
        print(f"Refusing to run: --exclude-plan keys are not triggered plans: {unknown_excludes}")
        return 2
    if excluded_keys:
        selected = [plan for plan in selected if plan.key not in excluded_keys]
    selected_keys = {plan.key for plan in selected}
    records = {
        item.record["sample_id"]: copy.deepcopy(item.record)
        for item in batch
    }
    for record in records.values():
        record["method"] = {"name": "sun_llm_fallback", "schema_source": SCHEMA_SOURCE}
        validate_canonical(record)
    # Immutable B0 snapshot used by the effective-patch audit, so the
    # per-plan B0 hash never reflects earlier accepted patches.
    original_records = {
        sample_id: copy.deepcopy(record) for sample_id, record in records.items()
    }

    try:
        replay_responses = (
            load_replay_responses(
                args.responses_jsonl,
                selected,
                original_records,
                prompt.sha256,
                args.prompt_variant,
            )
            if args.offline_replay
            else {}
        )
        frozen_replay_missing: list[tuple[str, str]] = []
        if args.offline_transport_replay and (
            args.frozen_plan is not None or args.continuation_plan is not None
        ):
            # S2.8D-R6: a frozen pilot that stopped early only has captured
            # responses for the actually-called plans.  Rows may therefore be
            # a strict subset of the frozen selection; the missing plans are
            # preserved as pilot_early_stop_not_called (never replayed).
            transport_replay_rows, frozen_replay_missing = load_frozen_transport_replay_rows(
                args.transport_responses_jsonl,
                selected,
                original_records,
                prompt.sha256,
                args.prompt_variant,
            )
        elif args.offline_transport_replay:
            transport_replay_rows = load_transport_replay_rows(
                args.transport_responses_jsonl,
                selected,
                original_records,
                prompt.sha256,
                args.prompt_variant,
            )
        else:
            transport_replay_rows = {}
    except (B0ArtifactError, OSError, json.JSONDecodeError) as exc:
        print(f"Refusing to run: {exc}")
        return 2

    # S2.8B: build the (possibly masked) clause context and leak audit for
    # every selected plan, in ALL execution modes, so plan-only runs can be
    # verified fully offline.  A context leak refuses the whole run.
    context_clauses: dict[tuple[str, str], dict[str, Any]] = {}
    context_audits: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        for plan in selected:
            clause = records[plan.sample_id]["clauses"][plan.clause_index]
            context_clause, audit = _build_context_audit(
                clause, plan, args.prompt_variant
            )
            context_clauses[plan.key] = context_clause
            context_audits[plan.key] = audit
    except (B0ArtifactError, ValueError) as exc:
        print(f"Refusing to run: {exc}")
        return 2

    if args.continuation_plan is not None:
        # S2.8D-R6C1: semantic binding of every continuation plan against the
        # current B0 record hashes, clause identity, masked context, prompt.
        try:
            _bind_continuation_plan_hashes(
                continuation_plan_config,
                selected,
                original_records,
                context_audits,
                prompt.sha256,
            )
        except H1RunnerError as exc:
            print(f"Refusing to run: {exc}")
            return 2
        selected_keys = {plan.key for plan in selected}
        selected_by_key = {plan.key: plan for plan in selected}
        plans = list(selected) + [p for p in plans if p.key not in selected_keys]
    elif args.frozen_plan is not None:
        # S2.8D-R5: semantic binding of every frozen plan against the current
        # B0 record hashes, clause identity, masked context, and prompt.
        try:
            _bind_frozen_plan_hashes(
                frozen_plan_config,
                selected,
                original_records,
                context_audits,
                prompt.sha256,
            )
        except H1RunnerError as exc:
            print(f"Refusing to run: {exc}")
            return 2
        selected_keys = {plan.key for plan in selected}
        selected_by_key = {plan.key: plan for plan in selected}
        # Execute the frozen plans first in their frozen execution order; all
        # other triggered plans are budget_not_selected.
        plans = list(selected) + [p for p in plans if p.key not in selected_keys]

    llm_transport = None
    config = None
    sampling: dict[str, Any] = {}
    if args.allow_llm:
        if args.model is None:
            print("Refusing to run: --allow-llm requires --model.")
            return 2
        config = LLMConfig.from_env(project_root=_PROJECT_ROOT)
        if not config.enabled or config.provider == "mock":
            print("Refusing to run: real LLM configuration is not enabled.")
            return 3
        # CLI model pinning (S2.8D): the explicit --model overrides
        # profile/.env model selection BEFORE the fail-closed gate.
        config = replace(config, model=args.model)
        if config.model != REAL_CALL_REQUIRED_MODEL:
            print(
                f"Refusing to run: resolved real-call model {config.model!r} != "
                f"required {REAL_CALL_REQUIRED_MODEL!r}. No API call was made."
            )
            return 3
        llm_transport = RealAPITransport(
            config, timeout_seconds=60.0, policy=DEEPSEEK_V4_FLASH_H1_POLICY
        )
        sampling = OpenAICompatibleRequestBuilder(config).sent_sampling_params()
        print(
            f"Real LLM config: provider={config.provider}, "
            f"model={config.model}, model_source=cli_override"
        )

    execution_mode = (
        "real_llm"
        if args.allow_llm
        else "offline_transport_replay"
        if args.offline_transport_replay
        else "offline_replay"
        if args.offline_replay
        else "offline_patch_replay"
        if args.offline_patches
        else "plan_only"
    )
    events: list[dict[str, Any]] = []
    llm_errors: list[dict[str, Any]] = []
    llm_calls = 0
    capture_rows: list[dict[str, Any]] = []
    started = time.time()
    early_stop_reason: str | None = None
    not_called_keys: list[str] = []
    consecutive_failures = 0
    using_plan = args.frozen_plan is not None or args.continuation_plan is not None
    frozen_order: list[tuple[str, str]] = (
        [plan.key for plan in selected] if using_plan else []
    )
    frozen_order_set: set[tuple[str, str]] = set(frozen_order)
    frozen_processed = 0

    for plan in plans:
        event = _patch_event_base(plan)
        if plan.key not in selected_keys:
            event["status"] = "budget_not_selected"
            events.append(event)
            continue
        event["selected_for_call"] = True
        # S2.8D-R6: advance the frozen-order cursor for EVERY selected frozen
        # plan up front, so the defensive plan_key_ok check can never drift
        # when a later pipeline branch (e.g. coordinate-canonicalization
        # failure) short-circuits without running the early-stop evaluator.
        if args.allow_llm and using_plan:
            frozen_processed += 1
        event["context_audit"] = context_audits[plan.key]
        if args.plan_only:
            event["status"] = "planned_not_executed"
            event["effective_patch_audit"] = _effective_patch_audit(
                plan,
                original_records[plan.sample_id],
                records[plan.sample_id],
                records[plan.sample_id],
                event,
                None,
            )
            events.append(event)
            continue

        envelope: dict[str, Any] | None = None
        if args.offline_replay:
            response_row = replay_responses[plan.key]
            response_content = response_row["response_content"]
            llm_calls += 1
            event["llm_call_performed"] = True
            event["response_sha256"] = _sha256_bytes(response_content.encode("utf-8"))
            envelope = _parse_patch_response(response_content)
        elif args.offline_transport_replay:
            if plan.key not in transport_replay_rows:
                # S2.8D-R6: a frozen pilot that stopped early has no captured
                # response for the remaining plans; preserve the real run's
                # early-stop state instead of replaying (never fabricate).
                if not using_plan:
                    raise H1RunnerError(
                        f"missing transport replay row for selected plan: "
                        f"{plan.sample_id}/{plan.clause_id}"
                    )
                event["status"] = EARLY_STOP_NOT_CALLED
                event["early_stop_reason"] = "replay_preserves_real_early_stop"
                events.append(event)
                not_called_keys.append(f"{plan.sample_id}/{plan.clause_id}")
                continue
            row = transport_replay_rows[plan.key]
            body = row["response_body"]
            llm_calls += 1
            event["llm_call_performed"] = True
            event["response_sha256"] = _sha256_bytes(body.encode("utf-8"))
            decode = decode_chat_completion_envelope(body, row.get("content_type"))
            event["response_model"] = decode.get("model") or args.model or "offline_transport_replay"
            event["response_provider"] = "openai_compatible"
            _attach_transport_fields(
                event,
                decode,
                request_policy=DEEPSEEK_V4_FLASH_H1_POLICY.to_dict(),
                endpoint_descriptor={"offline": True, "network": False},
                http_status=row.get("http_status"),
            )
            if decode.get("status") != STATUS_OK:
                event["status"] = "llm_error"
                event["rejection_reasons"] = [
                    f"extraction_status:{decode.get('status')}: "
                    f"{decode.get('error_detail') or 'no usable message.content'}"
                ]
                llm_errors.append(
                    {
                        "sample_id": plan.sample_id,
                        "clause_id": plan.clause_id,
                        "error": event["rejection_reasons"][0],
                    }
                )
                event["effective_patch_audit"] = _effective_patch_audit(
                    plan,
                    original_records[plan.sample_id],
                    records[plan.sample_id],
                    records[plan.sample_id],
                    event,
                    None,
                )
                events.append(event)
                continue
            # Only non-empty message.content reaches the H1 JSON parser.
            envelope = _parse_patch_response(decode["content"])
        elif args.offline_patches:
            envelope = offline_patches.get(plan.key)
            if envelope is None:
                event["status"] = "offline_patch_missing"
                event["rejection_reasons"] = ["no stored patch envelope for selected plan"]
                event["effective_patch_audit"] = _effective_patch_audit(
                    plan,
                    original_records[plan.sample_id],
                    records[plan.sample_id],
                    records[plan.sample_id],
                    event,
                    None,
                )
                events.append(event)
                continue
        else:
            record = records[plan.sample_id]
            request = LLMRequest(
                source_id=record["source_id"],
                source_text=record["source_text"],
                system_prompt=prompt.system_prompt,
                user_prompt=_build_user_prompt(
                    prompt, record, plan, context_clauses.get(plan.key)
                ),
                schema_name="H1RepairPatchEnvelope",
            )
            try:
                response = llm_transport.send(request)
                llm_calls += 1
                event["llm_call_performed"] = True
                event["response_sha256"] = _sha256_bytes(response.content.encode("utf-8"))
                event["response_model"] = response.model
                event["response_provider"] = response.provider
                decode = llm_transport.last_decode or {}
                _attach_transport_fields(
                    event,
                    decode,
                    request_policy=llm_transport.last_request_policy,
                    endpoint_descriptor=llm_transport.last_endpoint_descriptor,
                    http_status=200,
                )
                if llm_transport.last_request_body_sha256 is not None:
                    capture_rows.append(
                        build_transport_capture_row(
                            request_id=f"{plan.sample_id}/{plan.clause_id}",
                            sample_id=plan.sample_id,
                            clause_id=plan.clause_id,
                            clause_index=plan.clause_index,
                            prompt_sha256=prompt.sha256,
                            prompt_variant=args.prompt_variant,
                            b0_prediction_sha256=_prediction_hash(
                                original_records[plan.sample_id]
                            ),
                            request_body_sha256=llm_transport.last_request_body_sha256,
                            request_policy=llm_transport.last_request_policy or {},
                            http_status=200,
                            endpoint_descriptor=llm_transport.last_endpoint_descriptor,
                            requested_model=args.model,
                            resolved_model=config.model,
                            decode=decode,
                            sanitized_response_envelope=dict(decode),
                        )
                    )
                if decode.get("status") != STATUS_OK:
                    event["status"] = "llm_error"
                    event["rejection_reasons"] = [
                        f"extraction_status:{decode.get('status')}: "
                        f"{decode.get('error_detail') or 'no usable message.content'}"
                    ]
                    llm_errors.append(
                        {
                            "sample_id": plan.sample_id,
                            "clause_id": plan.clause_id,
                            "error": event["rejection_reasons"][0],
                        }
                    )
                    event["effective_patch_audit"] = _effective_patch_audit(
                        plan,
                        original_records[plan.sample_id],
                        records[plan.sample_id],
                        records[plan.sample_id],
                        event,
                        None,
                    )
                    events.append(event)
                    if args.allow_llm and using_plan:
                        consecutive_failures += 1
                        _stop = _maybe_early_stop_events(
                            plan=plan,
                            llm_calls=llm_calls,
                            consecutive_failures=consecutive_failures,
                            provider_model=(llm_transport.last_decode or {}).get("model"),
                            capture_bound=llm_transport.last_request_body_sha256 is not None,
                            required_model=REAL_CALL_REQUIRED_MODEL,
                            hard_call_cap=EXPECTED_HARD_CALL_CAP,
                            frozen_order=frozen_order,
                            frozen_order_set=frozen_order_set,
                            frozen_processed=frozen_processed,
                            selected_by_key=selected_by_key,
                            events=events,
                            not_called_keys=not_called_keys,
                        )
                        if _stop is not None:
                            early_stop_reason = _stop
                            break
                    continue
                envelope = _parse_patch_response(response.content)
            except (LLMClientError, H1RunnerError) as exc:
                if not event["llm_call_performed"]:
                    llm_calls += 1
                    event["llm_call_performed"] = True
                event["status"] = "llm_error"
                event["rejection_reasons"] = [str(exc)]
                llm_errors.append({"sample_id": plan.sample_id, "clause_id": plan.clause_id, "error": str(exc)})
                event["effective_patch_audit"] = _effective_patch_audit(
                    plan,
                    original_records[plan.sample_id],
                    records[plan.sample_id],
                    records[plan.sample_id],
                    event,
                    None,
                )
                events.append(event)
                if args.allow_llm and using_plan:
                    consecutive_failures += 1
                    _stop = _maybe_early_stop_events(
                        plan=plan,
                        llm_calls=llm_calls,
                        consecutive_failures=consecutive_failures,
                        provider_model=(llm_transport.last_decode or {}).get("model"),
                        capture_bound=(
                            llm_transport.last_request_body_sha256 is not None
                            if llm_transport is not None
                            else False
                        ),
                        required_model=REAL_CALL_REQUIRED_MODEL,
                        hard_call_cap=EXPECTED_HARD_CALL_CAP,
                        frozen_order=frozen_order,
                        frozen_order_set=frozen_order_set,
                        frozen_processed=frozen_processed,
                        selected_by_key=selected_by_key,
                        events=events,
                        not_called_keys=not_called_keys,
                    )
                    if _stop is not None:
                        early_stop_reason = _stop
                        break
                continue

        record_before = records[plan.sample_id]
        # S2.8D-R3: fail-closed unique exact-text coordinate canonicalization.
        # Runs on the SINGLE shared path for every execution mode (real API,
        # offline patches, offline replay, offline transport replay) between
        # the parser and the existing validator/atomic merge.
        clause_for_plan = record_before["clauses"][plan.clause_index]
        canonicalized, canonicalization_audit = canonicalize_patch_coordinates(
            envelope,
            str(record_before.get("source_text", "")),
            clause_for_plan.get("clause_span"),
        )
        if canonicalization_audit.get("status") == STATUS_FAILED:
            merge_event = _patch_event_base(plan)
            merge_event["selected_for_call"] = True
            merge_event["llm_call_performed"] = event["llm_call_performed"]
            if "response_sha256" in event:
                merge_event["response_sha256"] = event["response_sha256"]
            if "response_model" in event:
                merge_event["response_model"] = event["response_model"]
                merge_event["response_provider"] = event["response_provider"]
            for transport_key in _TRANSPORT_EVENT_KEYS:
                if transport_key in event:
                    merge_event[transport_key] = event[transport_key]
            merge_event["patch_proposed"] = True
            merge_event["patch_envelope"] = copy.deepcopy(envelope)
            merge_event["status"] = "rejected"
            merge_event["coordinate_canonicalization"] = canonicalization_audit
            reason_codes = canonicalization_audit.get("reason_codes") or []
            merge_event["rejection_reasons"] = [
                "; ".join(reason_codes) or "coordinate_canonicalization_failed"
            ]
            record_after = records[plan.sample_id]
            merge_event["effective_patch_audit"] = _effective_patch_audit(
                plan,
                original_records[plan.sample_id],
                record_before,
                record_after,
                merge_event,
                envelope,
            )
            events.append(merge_event)
            continue
        envelope = canonicalized
        merged, merge_event = apply_patch_envelope(record_before, envelope, plan)
        merge_event["selected_for_call"] = True
        merge_event["llm_call_performed"] = event["llm_call_performed"]
        if "response_sha256" in event:
            merge_event["response_sha256"] = event["response_sha256"]
        if "response_model" in event:
            merge_event["response_model"] = event["response_model"]
            merge_event["response_provider"] = event["response_provider"]
        for transport_key in _TRANSPORT_EVENT_KEYS:
            if transport_key in event:
                merge_event[transport_key] = event[transport_key]
        merge_event["coordinate_canonicalization"] = canonicalization_audit
        merge_event["patch_envelope"] = copy.deepcopy(envelope)
        if merge_event["patch_accepted"]:
            records[plan.sample_id] = merged
        record_after = records[plan.sample_id]
        merge_event["effective_patch_audit"] = _effective_patch_audit(
            plan,
            original_records[plan.sample_id],
            record_before,
            record_after,
            merge_event,
            envelope,
        )
        events.append(merge_event)
        if args.allow_llm and using_plan:
            consecutive_failures = 0
            _stop = _maybe_early_stop_events(
                plan=plan,
                llm_calls=llm_calls,
                consecutive_failures=consecutive_failures,
                provider_model=(llm_transport.last_decode or {}).get("model"),
                capture_bound=llm_transport.last_request_body_sha256 is not None,
                required_model=REAL_CALL_REQUIRED_MODEL,
                hard_call_cap=EXPECTED_HARD_CALL_CAP,
                frozen_order=frozen_order,
                frozen_order_set=frozen_order_set,
                frozen_processed=frozen_processed,
                selected_by_key=selected_by_key,
                events=events,
                not_called_keys=not_called_keys,
            )
            if _stop is not None:
                early_stop_reason = _stop
                break
        if args.allow_llm and args.inter_call_delay > 0 and llm_calls < len(selected):
            time.sleep(args.inter_call_delay)

    final_records = [records[item.record["sample_id"]] for item in batch]
    for record in final_records:
        report = validate_canonical(record)
        if not (report.schema_valid and report.cross_field_valid):
            print(f"Internal error: final H1 record is invalid for {record['sample_id']}: {report.errors}")
            return 4

    sample_rows = _summary_by_sample(batch, records, events)
    output_text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in final_records)
    telemetry_text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in sample_rows)
    try:
        _atomic_write_text(args.output, output_text, args.overwrite)
        _atomic_write_text(telemetry_path, telemetry_text, args.overwrite)
        if capture_rows:
            capture_text = "".join(
                json.dumps(row, ensure_ascii=False) + "\n" for row in capture_rows
            )
            _atomic_write_text(args.transport_capture, capture_text, args.overwrite)
    except H1RunnerError as exc:
        print(f"Refusing to write output: {exc}")
        return 2

    elapsed = time.time() - started
    triggered_samples = {plan.sample_id for plan in plans}
    selected_samples = {plan.sample_id for plan in selected}
    changed_samples = {row["sample_id"] for row in sample_rows if row["prediction_changed"]}
    accepted_events = [event for event in events if event.get("patch_accepted")]
    proposed_events = [event for event in events if event.get("patch_proposed")]
    rejected_events = [event for event in proposed_events if not event.get("patch_accepted")]
    called_unchanged_samples = {
        row["sample_id"]
        for row in sample_rows
        if row["llm_called"] and not row["prediction_changed"]
    }
    # S2.8C effective-patch aggregates over the per-plan audits.
    effective_audits = [
        event.get("effective_patch_audit", {})
        for event in events
        if isinstance(event.get("effective_patch_audit"), dict)
    ]
    accepted_effective = [
        audit for audit in effective_audits if audit.get("effective_patch")
    ]
    no_semantic_change = [
        audit
        for audit in effective_audits
        if "no_semantic_change" in audit.get("rejection_codes", [])
    ]
    rejection_counts: dict[str, int] = {}
    for audit in effective_audits:
        for code in audit.get("rejection_codes", []):
            rejection_counts[code] = rejection_counts.get(code, 0) + 1
    valid_response_count = sum(
        1
        for audit in effective_audits
        if audit.get("merge_status") in ("accepted", "rejected")
    )
    changed_field_counts: dict[str, int] = {}
    for audit in accepted_effective:
        for field in audit.get("changed_fields", []):
            changed_field_counts[field] = changed_field_counts.get(field, 0) + 1
    h1_non_identity_gate = bool(
        llm_calls > 0
        and valid_response_count > 0
        and len(accepted_effective) > 0
        and len(changed_samples) > 0
    )
    # S2.8D-R1 transport section: request policy actually sent, safe
    # endpoint descriptor, capture binding, and extraction status counts.
    extraction_status_counts: dict[str, int] = {}
    for event in events:
        status = event.get("extraction_status")
        if status:
            extraction_status_counts[str(status)] = (
                extraction_status_counts.get(str(status), 0) + 1
            )
    # S2.8D-R3: aggregate coordinate-canonicalization audit statistics.
    canonicalization_summary: dict[str, int] = {
        "attempted_patch_count": 0,
        "unchanged_patch_count": 0,
        "reanchored_patch_count": 0,
        "failed_patch_count": 0,
        "already_valid_span_count": 0,
        "reanchored_span_count": 0,
        "zero_match_count": 0,
        "ambiguous_match_count": 0,
        "contract_violation_count": 0,
    }
    for event in events:
        audit = event.get("coordinate_canonicalization")
        if not isinstance(audit, dict) or not audit.get("attempted"):
            continue
        canonicalization_summary["attempted_patch_count"] += 1
        status = audit.get("status")
        if status in (STATUS_UNCHANGED, STATUS_REANCHORED, STATUS_FAILED):
            canonicalization_summary[f"{status}_patch_count"] += 1
        canonicalization_summary["already_valid_span_count"] += int(
            audit.get("already_valid_count") or 0
        )
        canonicalization_summary["reanchored_span_count"] += int(
            audit.get("reanchored_count") or 0
        )
        canonicalization_summary["zero_match_count"] += int(
            audit.get("zero_match_count") or 0
        )
        canonicalization_summary["ambiguous_match_count"] += int(
            audit.get("ambiguous_match_count") or 0
        )
        canonicalization_summary["contract_violation_count"] += int(
            audit.get("contract_violation_count") or 0
        )
    if args.offline_transport_replay:
        transport_request_policy = DEEPSEEK_V4_FLASH_H1_POLICY.to_dict()
        transport_endpoint = {"offline": True, "network": False}
    elif llm_transport is not None:
        transport_request_policy = llm_transport.last_request_policy
        transport_endpoint = llm_transport.last_endpoint_descriptor
    else:
        transport_request_policy = None
        transport_endpoint = None
    transport_section = {
        "request_policy_sent": transport_request_policy,
        "safe_endpoint": transport_endpoint,
        "capture_path": str(args.transport_capture) if args.transport_capture else None,
        "capture_sha256": (
            _sha256_file(args.transport_capture)
            if capture_rows and args.transport_capture is not None
            else None
        ),
        "raw_response_saved": False,
        "sanitized_transport_capture_saved": bool(capture_rows),
        "extraction_status_counts": extraction_status_counts,
        "historical_endpoint_unknown_not_captured": True,
    }
    manifest = {
        "schema_version": "h1_selective_manifest@2.0.0",
        "stage": "stage2",
        "method": "sun_llm_fallback",
        "status": "development_not_formal" if args.development else "formal",
        "execution_mode": execution_mode,
        "prompt_variant": args.prompt_variant,
        "context_policy": {
            "policy_version": CONTEXT_POLICY_VERSION,
            "masked_sentinel": {"masked_selected_field": True},
            "dependency_closure": [
                "actors|actions -> actor_action_map",
                "actions -> order_relations",
            ],
            "audits_computed": len(context_audits),
            "audits_passed": len(context_audits),
            "selected_ids_leak_count": 0,
        },
        "effective_patch": {
            "accepted_effective_patch_count": len(accepted_effective),
            "no_semantic_change_count": len(no_semantic_change),
            "rejection_reason_counts": rejection_counts,
            "changed_field_counts": changed_field_counts,
            "valid_response_count": valid_response_count,
        },
        "h1_non_identity_gate": h1_non_identity_gate,
        "coordinate_canonicalization": canonicalization_summary,
        "transport": transport_section,
        "frozen_plan": (
            {
                "path": str(args.frozen_plan),
                "sha256": _sha256_file(args.frozen_plan),
                "schema_version": frozen_plan_config["schema_version"],
                "selected_plan_keys_sha256": selected_plan_keys_sha256(
                    frozen_plan_config["selected_plans"]
                ),
                "hard_api_call_cap": frozen_plan_config["budget"]["hard_api_call_cap"],
                "retry_per_plan": frozen_plan_config["budget"]["retry_per_plan"],
            }
            if args.frozen_plan is not None
            else None
        ),
        "continuation_plan": (
            {
                "path": str(args.continuation_plan),
                "sha256": _sha256_file(args.continuation_plan),
                "schema_version": continuation_plan_config["schema_version"],
                "remaining_plan_keys_sha256": continuation_plan_keys_sha256(
                    continuation_plan_config["selected_plans"]
                ),
                "hard_api_call_cap": continuation_plan_config["budget"]["hard_api_call_cap"],
                "retry_per_plan": continuation_plan_config["budget"]["retry_per_plan"],
                "prior_run_manifest_sha256": continuation_plan_config["prior_run"]["manifest_sha256"],
                "prior_run_capture_sha256": continuation_plan_config["prior_run"]["transport_capture_sha256"],
            }
            if args.continuation_plan is not None
            else None
        ),
        "early_stop": {
            "triggered": early_stop_reason is not None,
            "reason": early_stop_reason,
            "not_called_plan_keys": sorted(not_called_keys),
            "replay_preserved_not_called_plan_keys": sorted(
                f"{s}/{c}" for s, c in frozen_replay_missing
            ),
        },
        "replayed_response_count": (
            len(replay_responses) if args.offline_replay else 0
        ),
        "b0_binding": {
            "path": str(args.b0_predictions),
            "sha256": _sha256_file(args.b0_predictions),
            "manifest": b0_manifest,
            "rerun_inside_h1": False,
        },
        "outputs": {
            "predictions": {"path": str(args.output), "sha256": _sha256_file(args.output)},
            "telemetry": {"path": str(telemetry_path), "sha256": _sha256_file(telemetry_path)},
        },
        "sample_count": len(batch),
        "clause_count": sum(len(item.record["clauses"]) for item in batch),
        "trigger_policy": {
            "gold_visible": False,
            "signals": [
                "non_definition_missing_action",
                "non_definition_missing_actor",
                "classifier_marker_disagreement",
                "alignment_confidence_below_0_65",
                "scope_candidate_rejected",
            ],
            "allocation": "descending risk_score, then sample_id and clause_index",
            "max_calls": args.max_calls,
        },
        "triggered_plan_count": len(plans),
        "triggered_sample_count": len(triggered_samples),
        "selected_plan_count": len(selected),
        "selected_sample_count": len(selected_samples),
        "selected_sample_rate": len(selected_samples) / len(batch),
        "excluded_plan_keys": sorted(f"{s}/{c}" for s, c in excluded_keys),
        "llm_calls": llm_calls,
        "llm_called_sample_count": sum(1 for row in sample_rows if row["llm_called"]),
        "llm_errors": llm_errors,
        "patch_proposed_count": len(proposed_events),
        "patch_accepted_count": len(accepted_events),
        "patch_rejected_count": len(rejected_events),
        "prediction_changed_sample_count": len(changed_samples),
        "effective_patch_rate_per_proposal": (
            len(accepted_events) / len(proposed_events) if proposed_events else 0.0
        ),
        "called_but_unchanged_sample_count": len(called_unchanged_samples),
        "patch_events": [_compact_event(event) for event in events],
        "patch_rejections": [_compact_event(event) for event in rejected_events],
        "prompts": [build_manifest_entry(prompt)],
        "sampling": sampling,
        "real_api": bool(args.allow_llm and llm_calls),
        "llm_used": bool(args.allow_llm and llm_calls),
        "llm_provider": config.provider if config else "none",
        "llm_model": config.model if config else "none",
        "llm_model_source": "cli_override" if config else "none",
        "real_call_model_gate": {
            "required_model": REAL_CALL_REQUIRED_MODEL,
            "resolved_model": config.model if config else "none",
            "passed": bool(config and config.model == REAL_CALL_REQUIRED_MODEL),
        },
        "elapsed_seconds": elapsed,
        "claim_boundary": "development mechanism verification; not a formal performance result",
    }
    frozen_plan_only = (
        (args.frozen_plan is not None or args.continuation_plan is not None)
        and args.plan_only
    )
    if execution_mode not in ("offline_replay", "offline_transport_replay") and not frozen_plan_only:
        # Offline replay and frozen plan-only manifests are intentionally
        # timestamp-free so identical inputs replay byte-identically.
        manifest["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    else:
        # Timing is non-deterministic and would break byte-identical replay.
        manifest.pop("elapsed_seconds", None)
    try:
        _atomic_write_text(
            args.manifest,
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            args.overwrite,
        )
    except H1RunnerError as exc:
        print(f"Refusing to write manifest: {exc}")
        return 2

    print(
        f"H1 {execution_mode} [{args.prompt_variant}]: samples={len(batch)}, "
        f"triggered={len(triggered_samples)}, "
        f"selected={len(selected_samples)}, calls={llm_calls}, changed={len(changed_samples)}, "
        f"accepted={len(accepted_events)}, rejected={len(rejected_events)}, "
        f"effective={len(accepted_effective)}, gate={h1_non_identity_gate}"
    )
    print(f"Predictions: {args.output}")
    print(f"Telemetry:   {telemetry_path}")
    print(f"Manifest:    {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
