"""Run field-level selective H1 repair on an immutable B0 prediction batch.

H1 must consume the *same persisted B0 predictions* used by the B0 arm.  It
must never recreate B0 with a second extractor inside this runner.  The input
file is therefore mandatory and is bound into the manifest by SHA-256.

Three execution modes are supported:

* ``--plan-only``: detect and budget repair plans without evaluating patches;
* ``--offline-patches``: replay stored patch envelopes without network access;
* ``--allow-llm``: explicitly authorize real API calls for selected plans.

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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

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

PromptName = "rule_first_llm_fallback_prompt"

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


class H1RunnerError(ValueError):
    """Raised for a fail-closed H1 input or patch-contract violation."""


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


@dataclass
class LoadedB0:
    record: dict[str, Any]
    telemetry: dict[str, Any]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256_bytes(payload.encode("utf-8"))


def _prediction_hash(record: Mapping[str, Any]) -> str:
    """Hash semantic prediction content, deliberately excluding method metadata."""
    return _json_hash({"clauses": record.get("clauses", [])})


def _read_json_values(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise H1RunnerError(f"input file does not exist: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise H1RunnerError(f"input file is empty: {path}")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        rows: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise H1RunnerError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
            if not isinstance(item, dict):
                raise H1RunnerError(f"JSONL row {line_number} is not an object")
            rows.append(item)
        return rows

    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        for key in ("attempts", "predictions", "records"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
        else:
            rows = [payload]
    else:
        raise H1RunnerError(f"JSON input must be an object or array: {path}")
    if not all(isinstance(item, dict) for item in rows):
        raise H1RunnerError(f"all input rows must be JSON objects: {path}")
    return list(rows)


def _clean_modality(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "label": raw.get("label"),
        "evidence": copy.deepcopy(raw.get("evidence", [])),
    }


def _clean_b0_entry(entry: Mapping[str, Any]) -> LoadedB0:
    request_status = entry.get("request_status")
    if request_status not in (None, "ok"):
        raise H1RunnerError(
            f"B0 attempt {entry.get('sample_id', '?')!r} is not successful: {request_status!r}"
        )
    raw = entry.get("record", entry)
    if not isinstance(raw, Mapping):
        raise H1RunnerError("B0 entry does not contain a record object")
    method = raw.get("method")
    if not isinstance(method, Mapping) or method.get("name") != "sun_rule_only":
        raise H1RunnerError(
            f"B0 record {raw.get('sample_id', '?')!r} method must be 'sun_rule_only'"
        )

    clauses: list[dict[str, Any]] = []
    clause_telemetry: list[dict[str, Any]] = []
    for index, raw_clause in enumerate(raw.get("clauses", [])):
        if not isinstance(raw_clause, Mapping):
            raise H1RunnerError(f"B0 clause {index} is not an object")
        modality = raw_clause.get("modality")
        if not isinstance(modality, Mapping):
            raise H1RunnerError(f"B0 clause {index} has no modality object")
        clause = {
            "clause_id": raw_clause.get("clause_id"),
            "clause_span": copy.deepcopy(raw_clause.get("clause_span")),
            "modality": _clean_modality(modality),
            "actors": copy.deepcopy(raw_clause.get("actors", [])),
            "actions": copy.deepcopy(raw_clause.get("actions", [])),
            "conditions": copy.deepcopy(raw_clause.get("conditions", [])),
            "constraints": copy.deepcopy(raw_clause.get("constraints", [])),
            "exceptions": copy.deepcopy(raw_clause.get("exceptions", [])),
            "actor_action_map": copy.deepcopy(raw_clause.get("actor_action_map", [])),
            "order_relations": copy.deepcopy(raw_clause.get("order_relations", [])),
        }
        clauses.append(clause)
        clause_telemetry.append(
            {
                "clause_id": clause["clause_id"],
                "alignment": copy.deepcopy(raw_clause.get("alignment", {})),
                "scope_stats": copy.deepcopy(raw_clause.get("scope_stats", {})),
                "modality_route": modality.get("route"),
                "modality_diagnostic": copy.deepcopy(modality.get("diagnostic", {})),
            }
        )

    record = {
        "schema_version": raw.get("schema_version"),
        "sample_id": raw.get("sample_id"),
        "source_id": raw.get("source_id"),
        "source_text": raw.get("source_text"),
        "clauses": clauses,
        "method": {"name": "sun_rule_only", "schema_source": SCHEMA_SOURCE},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
    }
    if "unsupported_or_ambiguous" in raw:
        record["unsupported_or_ambiguous"] = copy.deepcopy(raw["unsupported_or_ambiguous"])
    report = validate_canonical(record)
    if not (report.schema_valid and report.cross_field_valid):
        raise H1RunnerError(
            f"B0 record {record.get('sample_id', '?')!r} is not canonical after diagnostic "
            f"fields are removed: {report.errors}"
        )
    return LoadedB0(
        record=record,
        telemetry={
            "attempt_runtime": copy.deepcopy(entry.get("runtime", {})),
            "clauses": clause_telemetry,
        },
    )


def load_b0_predictions(path: Path) -> list[LoadedB0]:
    loaded = [_clean_b0_entry(item) for item in _read_json_values(path)]
    if not loaded:
        raise H1RunnerError("B0 prediction batch contains no records")
    sample_ids = [item.record["sample_id"] for item in loaded]
    duplicates = sorted({sid for sid in sample_ids if sample_ids.count(sid) > 1})
    if duplicates:
        raise H1RunnerError(f"duplicate B0 sample_id values: {duplicates}")
    return loaded


def verify_b0_manifest(b0_path: Path, manifest_path: Path | None) -> dict[str, Any]:
    if manifest_path is None:
        candidate = b0_path.parent / "manifest.json"
        manifest_path = candidate if candidate.exists() else None
    if manifest_path is None:
        raise H1RunnerError(
            "a B0 manifest is required (pass --b0-manifest or place manifest.json beside B0)"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = (((manifest.get("artifacts") or {}).get("attempts") or {}).get("sha256"))
    actual = _sha256_file(b0_path)
    if not isinstance(expected, str):
        raise H1RunnerError(f"B0 manifest has no artifacts.attempts.sha256: {manifest_path}")
    if actual.lower() != expected.lower():
        raise H1RunnerError(
            f"B0 prediction hash mismatch: manifest={expected.lower()} actual={actual.lower()}"
        )
    return {
        "verified": True,
        "path": str(manifest_path),
        "sha256": _sha256_file(manifest_path),
        "run_id": manifest.get("run_id"),
        "method_variant": manifest.get("method_variant"),
        "claim_scope": manifest.get("claim_scope"),
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


def _build_user_prompt(prompt: Any, record: Mapping[str, Any], plan: RepairPlan) -> str:
    clause = record["clauses"][plan.clause_index]
    return prompt.user_prompt_template.format(
        sample_id=plan.sample_id,
        source_id=record["source_id"],
        source_text=record["source_text"],
        clause_id=plan.clause_id,
        current_clause_json=json.dumps(clause, indent=2, ensure_ascii=False),
        repair_fields_csv=", ".join(plan.repair_fields),
        repair_reasons_csv=", ".join(plan.reasons),
    )


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
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--offline-patches", type=Path)
    mode.add_argument("--allow-llm", action="store_true")
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
    telemetry_path = args.telemetry or _derive_telemetry_path(args.output)
    targets = (args.output, telemetry_path, args.manifest)
    for target in targets:
        allowed, reason = _gate_write(target, args.development)
        if not allowed:
            print(f"Refusing to write {target}: {reason}")
            return 2
        if target.exists() and not args.overwrite:
            print(f"Refusing to overwrite existing artifact: {target}")
            return 2

    try:
        prompt = load_prompt(PromptName)
        b0_manifest = verify_b0_manifest(args.b0_predictions, args.b0_manifest)
        batch = load_b0_predictions(args.b0_predictions)
        offline_patches = load_offline_patches(args.offline_patches) if args.offline_patches else {}
    except (H1RunnerError, OSError, json.JSONDecodeError) as exc:
        print(f"Refusing to run: {exc}")
        return 2

    plans = build_repair_plans(batch)
    selected = allocate_repair_calls(plans, args.max_calls)
    selected_keys = {plan.key for plan in selected}
    records = {
        item.record["sample_id"]: copy.deepcopy(item.record)
        for item in batch
    }
    for record in records.values():
        record["method"] = {"name": "sun_llm_fallback", "schema_source": SCHEMA_SOURCE}
        validate_canonical(record)

    llm_transport = None
    config = None
    sampling: dict[str, Any] = {}
    if args.allow_llm:
        config = LLMConfig.from_env(project_root=_PROJECT_ROOT)
        if not config.enabled or config.provider == "mock":
            print("Refusing to run: real LLM configuration is not enabled.")
            return 3
        llm_transport = RealAPITransport(config, timeout_seconds=60.0)
        sampling = OpenAICompatibleRequestBuilder(config).sent_sampling_params()

    execution_mode = "real_llm" if args.allow_llm else "offline_replay" if args.offline_patches else "plan_only"
    events: list[dict[str, Any]] = []
    llm_errors: list[dict[str, Any]] = []
    llm_calls = 0
    started = time.time()

    for plan in plans:
        event = _patch_event_base(plan)
        if plan.key not in selected_keys:
            event["status"] = "budget_not_selected"
            events.append(event)
            continue
        event["selected_for_call"] = True
        if args.plan_only:
            event["status"] = "planned_not_executed"
            events.append(event)
            continue

        envelope: dict[str, Any] | None = None
        if args.offline_patches:
            envelope = offline_patches.get(plan.key)
            if envelope is None:
                event["status"] = "offline_patch_missing"
                event["rejection_reasons"] = ["no stored patch envelope for selected plan"]
                events.append(event)
                continue
        else:
            record = records[plan.sample_id]
            request = LLMRequest(
                source_id=record["source_id"],
                source_text=record["source_text"],
                system_prompt=prompt.system_prompt,
                user_prompt=_build_user_prompt(prompt, record, plan),
                schema_name="H1RepairPatchEnvelope",
            )
            try:
                response = llm_transport.send(request)
                llm_calls += 1
                event["llm_call_performed"] = True
                event["response_sha256"] = _sha256_bytes(response.content.encode("utf-8"))
                envelope = _parse_patch_response(response.content)
            except (LLMClientError, H1RunnerError) as exc:
                if not event["llm_call_performed"]:
                    llm_calls += 1
                    event["llm_call_performed"] = True
                event["status"] = "llm_error"
                event["rejection_reasons"] = [str(exc)]
                llm_errors.append({"sample_id": plan.sample_id, "clause_id": plan.clause_id, "error": str(exc)})
                events.append(event)
                continue

        merged, merge_event = apply_patch_envelope(records[plan.sample_id], envelope, plan)
        merge_event["selected_for_call"] = True
        merge_event["llm_call_performed"] = event["llm_call_performed"]
        if "response_sha256" in event:
            merge_event["response_sha256"] = event["response_sha256"]
        merge_event["patch_envelope"] = copy.deepcopy(envelope)
        if merge_event["patch_accepted"]:
            records[plan.sample_id] = merged
        events.append(merge_event)
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
    manifest = {
        "schema_version": "h1_selective_manifest@2.0.0",
        "stage": "stage2",
        "method": "sun_llm_fallback",
        "status": "development_not_formal" if args.development else "formal",
        "execution_mode": execution_mode,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
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
        "elapsed_seconds": elapsed,
        "claim_boundary": "development mechanism verification; not a formal performance result",
    }
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
        f"H1 {execution_mode}: samples={len(batch)}, triggered={len(triggered_samples)}, "
        f"selected={len(selected_samples)}, calls={llm_calls}, changed={len(changed_samples)}, "
        f"accepted={len(accepted_events)}, rejected={len(rejected_events)}"
    )
    print(f"Predictions: {args.output}")
    print(f"Telemetry:   {telemetry_path}")
    print(f"Manifest:    {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
