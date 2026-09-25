# -*- coding: utf-8 -*-
"""Zero-API retrospective A/B of the D1 span-grounding repair.

Replays the exact frozen ``D-full-0813`` raw model responses through the SAME
relay-schema adapter and the SAME canonical validator / evaluator, changing
only the span-grounding policy:

* OLD arm -> ``policy="legacy"`` (pre-repair: repeated exact occurrence drops);
* NEW arm -> ``policy="repair_v1"`` (deterministic repeated-occurrence
  grounding via nearest offset / one-to-one minimum-cost assignment).

No model call is made.  The script also runs an automated semantic-invariance
audit (no invented spans, no text/id/field mutation), an actor-recovery
attribution, and a Gold-blind count of the repeated-occurrence cases.

This is development / retrospective evidence only.  It must not be read as a
formal result and it does not promote the repair to the production default.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in (SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from bpc_hybrid.d1_schema_adapter import adapt_relay_record  # noqa: E402
from bpc_hybrid.d1_span_canonicalizer import (  # noqa: E402
    COST_METRIC_START_END,
    COST_METRIC_START_ONLY,
    POLICY_LEGACY,
    POLICY_REPAIR,
    canonicalize_record_coordinates,
)
from bpc_hybrid.estg150_b0_development import build_canonical_gold_records  # noqa: E402
from bpc_hybrid.stage2_canonical import validate_canonical  # noqa: E402
from analyze_d_no_fewshot_interface_failure_v1 import (  # noqa: E402
    DiagnosisError,
    _load_jsonl,
    _parse_raw_content,
)
import run_barrientos_ablation_suite_v2 as runner  # noqa: E402

SOURCE_ARM = "D-full-0813"
SOURCE_RUN = "barrientos-de-0813-1140-v1"
SOURCE_DIR = ROOT / "outputs/development/barrientos_ablation_suite_v2" / SOURCE_ARM / "repeat-01"
RAW_PATH = SOURCE_DIR / "raw_responses.jsonl"
LOCKED_EVALUATION_PATH = SOURCE_DIR / "evaluation.json"
LOCKED_CANONICAL_PATH = SOURCE_DIR / "canonical_predictions.jsonl"

LOCAL_OUTPUT_DIR = ROOT / "outputs/development/d_span_grounding_repair_v1"
REPORT_JSON = ROOT / "outputs/reports/d_span_grounding_repair_v1.json"
REPORT_MD = ROOT / "outputs/reports/d_span_grounding_repair_v1.md"

ID_FIELDS = ("actors", "actions", "conditions", "constraints", "exceptions")
FIELD_OF_PATH = {
    "actors": "actor", "actions": "action", "conditions": "condition",
    "constraints": "constraint", "exceptions": "exception",
    "modality.evidence": "modality",
}
PRONOUNS = {"it", "this", "that", "they", "he", "she", "we", "you", "i",
            "them", "those", "these", "its", "their", "his", "her"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_by_id() -> dict[str, str]:
    return {row["sample_id"]: row["text"] for row in runner._estg_samples()}


def _prepare_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    source_by_id: Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse + adapter once; both arms then share the identical adapter output."""
    telemetry = {
        "sample_count": len(raw_rows),
        "json_parse_failures": 0,
        "adapter_failures": 0,
        "adapter_degraded_records": 0,
        "adapter_spans_adapted": 0,
        "adapter_spans_dropped": 0,
    }
    prepared: list[dict[str, Any]] = []
    for raw_row in raw_rows:
        sid = raw_row.get("sample_id")
        if not isinstance(sid, str) or sid not in source_by_id:
            raise DiagnosisError(f"unknown sample_id: {sid!r}")
        source_text = source_by_id[sid]
        try:
            payload = _parse_raw_content(raw_row.get("raw_response_content"))
        except (ValueError, json.JSONDecodeError) as exc:
            telemetry["json_parse_failures"] += 1
            prepared.append({"sample_id": sid, "adapter_record": None,
                             "failure": f"json_parse: {exc}"})
            continue
        adapted, audit = adapt_relay_record(payload, source_text)
        if audit.get("status") == "failed":
            telemetry["adapter_failures"] += 1
            prepared.append({"sample_id": sid, "adapter_record": None,
                             "failure": "adapter: " + "; ".join(audit.get("failed_reasons", []))})
            continue
        if audit.get("status") == "degraded":
            telemetry["adapter_degraded_records"] += 1
        telemetry["adapter_spans_adapted"] += int(audit.get("spans_adapted", 0))
        telemetry["adapter_spans_dropped"] += len(audit.get("dropped_spans", []))
        prepared.append({"sample_id": sid, "adapter_record": adapted,
                         "adapter_audit": audit, "failure": None})
    return prepared, telemetry


def _run_arm(
    prepared: Sequence[Mapping[str, Any]],
    source_by_id: Mapping[str, str],
    *,
    policy: str,
    cost_metric: str,
    evaluator,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    audits_by_id: dict[str, Any] = {}
    telemetry: dict[str, Any] = {
        "policy": policy,
        "cost_metric": cost_metric,
        "sample_count": len(prepared),
        "canonicalizer_failures": 0,
        "canonicalizer_reanchored": 0,
        "canonicalizer_spans_dropped": 0,
        "canonicalizer_clauses_dropped": 0,
        "canonicalizer_edges_dropped": 0,
        "unchanged_spans": 0,
        "unresolved_spans": 0,
        "reanchored_unique_exact": 0,
        "reanchored_repeated_exact": 0,
        "repeated_occurrence_cases": 0,
        "repeated_occurrence_recovered": 0,
        "repeated_occurrence_unresolved": 0,
        "tie_cases": 0,
        "one_to_one_assignment_cases": 0,
        "assignment_ambiguities": 0,
        "validator_invalid_records_observed": 0,
        "validator_rejected_records": 0,
        "failed_records": 0,
        "successful_records": 0,
        "nonempty_output_records": 0,
        "output_clause_count": 0,
        "dropped_by_field": defaultdict(int),
        "recovered_by_field": defaultdict(int),
        "dropped_actor_spans": 0,
    }
    audit_keys = (
        "unchanged_spans", "unresolved_spans",
        "reanchored_unique_exact", "reanchored_repeated_exact",
        "repeated_occurrence_cases", "repeated_occurrence_recovered",
        "repeated_occurrence_unresolved", "tie_cases",
        "one_to_one_assignment_cases", "assignment_ambiguities",
    )
    for item in prepared:
        sid = item["sample_id"]
        if item.get("adapter_record") is None:
            telemetry["failed_records"] += 1
            rows.append({"sample_id": sid, "request_status": "failed",
                         "error": item.get("failure") or "upstream_failure",
                         "record": {}})
            audits_by_id[sid] = {"sample_id": sid, "audit": None}
            continue
        record, audit = canonicalize_record_coordinates(
            copy.deepcopy(item["adapter_record"]), source_by_id[sid],
            policy=policy, cost_metric=cost_metric)
        audits_by_id[sid] = {"sample_id": sid, "audit": audit}
        if audit.get("status") == "failed":
            telemetry["canonicalizer_failures"] += 1
        telemetry["canonicalizer_reanchored"] += int(audit.get("reanchored_count", 0))
        for key in audit_keys:
            telemetry[key] += int(audit.get(key, 0))
        telemetry["canonicalizer_spans_dropped"] += len(audit.get("dropped_spans", []))
        telemetry["canonicalizer_clauses_dropped"] += len(audit.get("dropped_clauses", []))
        telemetry["canonicalizer_edges_dropped"] += len(audit.get("dropped_edges", []))
        for event in audit.get("resolution_events", []):
            field = FIELD_OF_PATH.get(event.get("field"), event.get("field"))
            if event.get("outcome") == "unresolved":
                telemetry["dropped_by_field"][field] += 1
                if field == "actor":
                    telemetry["dropped_actor_spans"] += 1
            elif event.get("outcome") == "reanchored_repeated_exact":
                telemetry["recovered_by_field"][field] += 1
        validation = validate_canonical(record)
        if not (validation.schema_valid and validation.cross_field_valid):
            telemetry["validator_invalid_records_observed"] += 1
            telemetry["validator_rejected_records"] += 1
            telemetry["failed_records"] += 1
            rows.append({"sample_id": sid, "request_status": "failed",
                         "error": "validator: " + "; ".join(validation.errors),
                         "record": record})
            continue
        clauses = record.get("clauses") if isinstance(record, Mapping) else []
        if isinstance(clauses, list) and clauses:
            telemetry["nonempty_output_records"] += 1
            telemetry["output_clause_count"] += len(clauses)
        rows.append({"sample_id": sid, "request_status": "ok", "record": record})
    telemetry["successful_records"] = sum(
        1 for row in rows if row["request_status"] == "ok")
    telemetry["failed_records"] = len(rows) - telemetry["successful_records"]
    telemetry["dropped_by_field"] = dict(sorted(telemetry["dropped_by_field"].items()))
    telemetry["recovered_by_field"] = dict(sorted(telemetry["recovered_by_field"].items()))
    evaluation = evaluator(rows)
    metrics = evaluation.get("metrics") or {}
    return rows, audits_by_id, {
        "telemetry": telemetry,
        "overall": metrics.get("overall") or {},
        "per_field": metrics.get("per_field") or {},
        "metric_schema_version": metrics.get("schema_version"),
        "invalid_attempt_count": metrics.get("invalid_attempt_count"),
    }


def _record_spans(record: Mapping[str, Any]) -> list[tuple[Any, str, Mapping[str, Any]]]:
    out: list[tuple[Any, str, Mapping[str, Any]]] = []
    for ci, clause in enumerate(record.get("clauses") or []):
        clause_id = clause.get("clause_id", ci)
        for field in ID_FIELDS:
            for span in clause.get(field) or []:
                out.append((clause_id, field, span))
        for span in (clause.get("modality") or {}).get("evidence") or []:
            out.append((clause_id, "modality.evidence", span))
    return out


def semantic_invariance_audit(
    prepared: Sequence[Mapping[str, Any]],
    old_rows: Sequence[Mapping[str, Any]],
    new_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    old_by_id = {row["sample_id"]: row for row in old_rows}
    new_by_id = {row["sample_id"]: row for row in new_rows}
    counts = {
        "samples_checked": 0,
        "invented_semantic_spans": 0,
        "field_reclassification": 0,
        "text_mutation": 0,
        "normalized_mutation": 0,
        "id_mutation": 0,
        "old_only_spans": 0,
        "new_only_spans": 0,
        "new_only_spans_explained_by_old_drops": 0,
        "clause_span_text_mutation": 0,
        "invented_modality_evidence": 0,
        "old_only_modality_evidence": 0,
        "modality_evidence_text_mutation": 0,
    }
    for item in prepared:
        sid = item["sample_id"]
        adapter = item.get("adapter_record")
        old = old_by_id[sid].get("record") or {}
        new = new_by_id[sid].get("record") or {}
        if adapter is None:
            continue
        counts["samples_checked"] += 1

        def index(record):
            by_key = {}
            by_id = {}
            evidence = Counter()
            for clause_id, field, span in _record_spans(record):
                if field == "modality.evidence":
                    evidence[(clause_id, str(span.get("text")))] += 1
                elif isinstance(span.get("id"), str):
                    by_key[(clause_id, field, span["id"])] = span
                    by_id[(clause_id, span["id"])] = field
            return by_key, by_id, evidence

        a_key, a_id, a_ev = index(adapter)
        o_key, o_id, o_ev = index(old)
        n_key, n_id, n_ev = index(new)

        for key, span in n_key.items():
            if key in a_key:
                if span.get("text") != a_key[key].get("text"):
                    counts["text_mutation"] += 1
                if span.get("normalized") != a_key[key].get("normalized"):
                    counts["normalized_mutation"] += 1
            elif (key[0], key[2]) in a_id:
                counts["field_reclassification"] += 1
            else:
                counts["invented_semantic_spans"] += 1
        for key, span in o_key.items():
            if key not in n_key:
                counts["old_only_spans"] += 1
            if key in n_key:
                if span.get("id") != n_key[key].get("id"):
                    counts["id_mutation"] += 1
                if span.get("text") != n_key[key].get("text"):
                    counts["text_mutation"] += 1
                if span.get("normalized") != n_key[key].get("normalized"):
                    counts["normalized_mutation"] += 1
        counts["new_only_spans"] += sum(1 for key in n_key if key not in o_key)
        counts["new_only_spans_explained_by_old_drops"] += sum(
            1 for key in n_key if key not in o_key and key in a_key)

        for key in n_ev:
            if key not in a_ev:
                counts["invented_modality_evidence"] += n_ev[key]
        for key in o_ev:
            if n_ev[key] < o_ev[key]:
                counts["old_only_modality_evidence"] += o_ev[key] - n_ev[key]

        old_clauses = {cl.get("clause_id", i): cl for i, cl in enumerate(old.get("clauses") or [])}
        new_clauses = {cl.get("clause_id", i): cl for i, cl in enumerate(new.get("clauses") or [])}
        for cid, new_clause in new_clauses.items():
            if cid in old_clauses:
                if (new_clause.get("clause_span") or {}).get("text") != (
                        old_clauses[cid].get("clause_span") or {}).get("text"):
                    counts["clause_span_text_mutation"] += 1
    return counts


def _flatten_field(record: Mapping[str, Any], field: str) -> list[Mapping[str, Any]]:
    values: list[Mapping[str, Any]] = []
    for clause in record.get("clauses") or []:
        if field == "modality.evidence":
            values.extend((clause.get("modality") or {}).get("evidence") or [])
        else:
            values.extend(clause.get(field) or [])
    return values


def _overlaps(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    try:
        return max(int(left["start"]), int(right["start"])) < min(int(left["end"]), int(right["end"]))
    except (KeyError, TypeError, ValueError):
        return False


def build_gold_by_id() -> dict[str, Any]:
    """Build the same Gold the development evaluator uses (layer E @ 56d2b03)."""
    with tempfile.TemporaryDirectory(dir=ROOT / ".tmp") as temp_dir:
        work = Path(temp_dir)
        for key, path in (
            ("layer_e", "formal_experiment/data/development/human_review/estg_150_human_correction_v1.json"),
            ("membership", "formal_experiment/data/development/estg/estg_150_membership_hashes.json"),
        ):
            blob = subprocess.run(
                ["git", "show", f"56d2b03:{path}"], cwd=ROOT.parent,
                capture_output=True, check=True).stdout
            (work / key).write_bytes(blob)
        gold, _ = build_canonical_gold_records(work / "layer_e", work / "membership")
    return {row["sample_id"]: row for row in gold}


def actor_attribution(
    gold_by_id: Mapping[str, Any],
    old_rows: Sequence[Mapping[str, Any]],
    new_rows: Sequence[Mapping[str, Any]],
    old_audits: Mapping[str, Any],
    new_audits: Mapping[str, Any],
) -> dict[str, Any]:
    """List every actor span recovered by the repair and measure Gold actor FN.

    ``recovered_actor_spans`` is Gold-independent: it is every NEW actor span
    whose resolution event is ``reanchored_repeated_exact``.  The Gold overlap
    annotation and the FN accounting are added afterwards, for evaluation only.
    """
    old_by_id = {row["sample_id"]: row for row in old_rows}
    new_by_id = {row["sample_id"]: row for row in new_rows}
    recovered_spans: list[dict[str, Any]] = []
    recovered_fn_keys: set[tuple[str, int]] = set()
    old_fn_total = 0
    new_fn_total = 0
    for sid, gold in gold_by_id.items():
        gold_actors = _flatten_field(gold, "actors")
        old_pred = _flatten_field(old_by_id[sid].get("record") or {}, "actors")
        new_pred = _flatten_field(new_by_id[sid].get("record") or {}, "actors")
        old_fn_indices = [i for i, g in enumerate(gold_actors)
                          if not any(_overlaps(g, p) for p in old_pred)]
        new_fn_indices = [i for i, g in enumerate(gold_actors)
                          if not any(_overlaps(g, p) for p in new_pred)]
        old_fn_total += len(old_fn_indices)
        new_fn_total += len(new_fn_indices)
        old_events = {e.get("span_id"): e
                      for e in ((old_audits[sid].get("audit") or {}).get("resolution_events") or [])}
        for event in ((new_audits[sid].get("audit") or {}).get("resolution_events") or []):
            if event.get("field") != "actors" or event.get("outcome") != "reanchored_repeated_exact":
                continue
            span_id = event.get("span_id")
            old_event = old_events.get(span_id)
            chosen = event.get("chosen") if isinstance(event.get("chosen"), Mapping) else {}
            match = next((p for p in new_pred if p.get("id") == span_id), None)
            gold_matches = [i for i, g in enumerate(gold_actors)
                            if match is not None and _overlaps(g, match)]
            for i in gold_matches:
                if i in old_fn_indices:
                    recovered_fn_keys.add((sid, i))
            recovered_spans.append({
                "sample_id": sid,
                "actor_id": span_id,
                "actor_text": event.get("text"),
                "old_predicted_start": old_event.get("original_start") if old_event else None,
                "old_predicted_end": old_event.get("original_end") if old_event else None,
                "old_outcome": (old_event or {}).get("outcome"),
                "old_reason": (old_event or {}).get("reason"),
                "candidate_occurrences": event.get("candidate_occurrences"),
                "new_predicted_start": chosen.get("start"),
                "new_predicted_end": chosen.get("end"),
                "resolution_strategy": event.get("strategy"),
                "new_outcome": event.get("outcome"),
                "new_distance": event.get("distance"),
                "gold_overlap_after_evaluation": bool(gold_matches),
            })
    recovered_spans.sort(key=lambda row: (row["sample_id"], row["actor_id"] or ""))
    return {
        "old_actor_fn": old_fn_total,
        "new_actor_fn": new_fn_total,
        "actor_fn_recovered_by_grounding_repair": len(recovered_fn_keys),
        "actor_fn_remaining": new_fn_total,
        "grounding_attributable_fn_share": (
            len(recovered_fn_keys) / old_fn_total if old_fn_total else None),
        "recovered_actor_spans": recovered_spans,
        "recovered_actor_fn_keys": sorted(f"{sid}#{i}" for sid, i in recovered_fn_keys),
    }


def remaining_actor_gap_analysis(
    gold_by_id: Mapping[str, Any],
    prepared: Sequence[Mapping[str, Any]],
    new_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Post-hoc error taxonomy for the actor FN that survive the repair."""
    prepared_by_id = {item["sample_id"]: item for item in prepared}
    new_by_id = {row["sample_id"]: row for row in new_rows}
    categories = Counter()
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sid, gold in gold_by_id.items():
        gold_actors = _flatten_field(gold, "actors")
        new_pred = _flatten_field(new_by_id[sid].get("record") or {}, "actors")
        adapter = (prepared_by_id.get(sid) or {}).get("adapter_record") or {}
        adapter_actors = _flatten_field(adapter, "actors")
        adapter_other = []
        for field in ("actions", "conditions", "constraints", "exceptions", "modality.evidence"):
            adapter_other.extend(_flatten_field(adapter, field))
        for gold_span in gold_actors:
            if any(_overlaps(gold_span, p) for p in new_pred):
                continue
            normalized = " ".join(str(gold_span.get("text", "")).casefold().split())
            if any(" ".join(str(s.get("text", "")).casefold().split()) == normalized
                   for s in adapter_actors):
                category = "emitted_as_actor_but_still_unresolved"
            elif any(" ".join(str(s.get("text", "")).casefold().split()) == normalized
                     for s in adapter_other):
                category = "emitted_in_another_field"
            else:
                category = "model_did_not_emit"
            categories[category] += 1
            if len(examples[category]) < 10:
                examples[category].append({"sample_id": sid, "text": gold_span.get("text"),
                                           "start": gold_span.get("start"), "end": gold_span.get("end")})
    return {"counts": dict(categories), "examples": dict(examples)}


def actor_false_positive_analysis(
    gold_by_id: Mapping[str, Any],
    new_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    new_by_id = {row["sample_id"]: row for row in new_rows}
    total = 0
    pronoun_fp = 0
    examples: list[dict[str, Any]] = []
    for sid, gold in gold_by_id.items():
        gold_actors = _flatten_field(gold, "actors")
        for span in _flatten_field(new_by_id[sid].get("record") or {}, "actors"):
            if any(_overlaps(span, g) for g in gold_actors):
                continue
            total += 1
            text = " ".join(str(span.get("text", "")).casefold().split())
            if text in PRONOUNS:
                pronoun_fp += 1
            if len(examples) < 20:
                examples.append({"sample_id": sid, "text": span.get("text"),
                                 "start": span.get("start"), "end": span.get("end")})
    return {"new_actor_false_positives": total,
            "new_actor_pronoun_false_positives": pronoun_fp,
            "examples": examples}


def _delta(new: Mapping[str, Any], old: Mapping[str, Any], key: str) -> float:
    return float(new.get(key, 0.0)) - float(old.get(key, 0.0))


def build_report(
    raw_path: Path = RAW_PATH,
    locked_evaluation_path: Path = LOCKED_EVALUATION_PATH,
    evaluator=None,
    run_sensitivity: bool = True,
) -> dict[str, Any]:
    if not raw_path.is_file():
        raise DiagnosisError("frozen D-full-0813 raw responses are unavailable")
    raw_rows = _load_jsonl(raw_path)
    if len(raw_rows) != 150:
        raise DiagnosisError("grounding repair experiment requires 150 raw rows")
    source_by_id = _source_by_id()
    if evaluator is None:
        evaluator = runner._make_evaluator(SOURCE_ARM)

    prepared, prepare_telemetry = _prepare_rows(raw_rows, source_by_id)

    old_rows, old_audits, old_result = _run_arm(
        prepared, source_by_id, policy=POLICY_LEGACY,
        cost_metric=COST_METRIC_START_END, evaluator=evaluator)
    if run_sensitivity:
        start_only_rows, start_only_audits, start_only_result = _run_arm(
            prepared, source_by_id, policy=POLICY_REPAIR,
            cost_metric=COST_METRIC_START_ONLY, evaluator=evaluator)
    else:
        start_only_result = None
    new_rows, new_audits, new_result = _run_arm(
        prepared, source_by_id, policy=POLICY_REPAIR,
        cost_metric=COST_METRIC_START_END, evaluator=evaluator)

    locked = json.loads(locked_evaluation_path.read_text(encoding="utf-8"))
    locked_overall = (locked.get("evaluation") or {}).get("metrics", {}).get("overall") or {}
    old_overall = old_result["overall"]
    if any(abs(float(old_overall.get(k, 0.0)) - float(locked_overall.get(k, 0.0))) > 1e-12
           for k in ("precision", "recall", "f1")):
        raise DiagnosisError(
            "legacy arm does not reproduce the locked D-full-0813 evaluation; "
            "the OLD baseline is not the frozen production chain")

    gold_by_id = build_gold_by_id()
    invariance = semantic_invariance_audit(prepared, old_rows, new_rows)
    attribution = actor_attribution(gold_by_id, old_rows, new_rows, old_audits, new_audits)
    remaining = remaining_actor_gap_analysis(gold_by_id, prepared, new_rows)
    actor_fp = actor_false_positive_analysis(gold_by_id, new_rows)

    per_field: dict[str, Any] = {}
    for field, new_metrics in (new_result["per_field"] or {}).items():
        old_metrics = (old_result["per_field"] or {}).get(field, {})
        per_field[field] = {
            "old": old_metrics,
            "new": new_metrics,
            "delta_precision": _delta(new_metrics, old_metrics, "precision"),
            "delta_recall": _delta(new_metrics, old_metrics, "recall"),
            "delta_f1": _delta(new_metrics, old_metrics, "f1"),
        }

    old_dropped = old_result["telemetry"]["dropped_by_field"]
    new_dropped = new_result["telemetry"]["dropped_by_field"]
    recovered = new_result["telemetry"]["recovered_by_field"]
    per_field_grounding = {}
    for field in sorted(set(old_dropped) | set(new_dropped) | set(recovered)):
        per_field_grounding[field] = {
            "old_dropped_spans": old_dropped.get(field, 0),
            "new_dropped_spans": new_dropped.get(field, 0),
            "recovered_spans": recovered.get(field, 0),
        }
        if old_dropped.get(field, 0) != new_dropped.get(field, 0) + recovered.get(field, 0):
            raise DiagnosisError(f"per-field grounding conservation failed for {field}")

    report = {
        "schema_version": "d_span_grounding_repair@1.0.0",
        "status": "retrospective_development_postprocessing_grounding_repair",
        "scope": {
            "source_arm": SOURCE_ARM,
            "source_run": SOURCE_RUN,
            "sample_count": len(raw_rows),
            "model_responses_fixed_across_arms": True,
            "new_api_calls": 0,
            "same_adapter": True,
            "same_gold_and_evaluator": True,
            "only_changed_factor": "span_grounding_policy",
            "measured_layer": "postprocessing_only",
            "model_generation_effect_claim_allowed": False,
            "formal_confirmatory_claim_allowed": False,
            "promotion_authorized": False,
        },
        "provenance": {
            "raw_responses_path": str(raw_path.relative_to(ROOT)),
            "raw_responses_sha256": _sha256(raw_path),
            "locked_evaluation_path": str(locked_evaluation_path.relative_to(ROOT)),
            "locked_evaluation_sha256": _sha256(locked_evaluation_path),
            "locked_canonical_predictions_path": str(LOCKED_CANONICAL_PATH.relative_to(ROOT)),
            "locked_canonical_predictions_sha256": (
                _sha256(LOCKED_CANONICAL_PATH) if LOCKED_CANONICAL_PATH.is_file() else None),
            "old_canonicalizer_policy": POLICY_LEGACY,
            "new_canonicalizer_policy": POLICY_REPAIR,
            "default_policy_unchanged": POLICY_LEGACY,
            "cost_metric": COST_METRIC_START_END,
            "old_arm_exactly_reproduces_locked_evaluation": True,
        },
        "prepare_telemetry": prepare_telemetry,
        "arms": {
            "old_canonicalizer": {"policy": POLICY_LEGACY,
                                  "cost_metric": COST_METRIC_START_END,
                                  "telemetry": old_result["telemetry"],
                                  "overall": old_result["overall"]},
            "new_canonicalizer": {"policy": POLICY_REPAIR,
                                  "cost_metric": COST_METRIC_START_END,
                                  "telemetry": new_result["telemetry"],
                                  "overall": new_result["overall"]},
        },
        "metric_comparison": {
            "overall": {
                "old": old_result["overall"],
                "new": new_result["overall"],
                "delta_precision": _delta(new_result["overall"], old_result["overall"], "precision"),
                "delta_recall": _delta(new_result["overall"], old_result["overall"], "recall"),
                "delta_f1": _delta(new_result["overall"], old_result["overall"], "f1"),
            },
            "per_field": per_field,
        },
        "grounding_telemetry": {
            "old_dropped_spans": old_result["telemetry"]["canonicalizer_spans_dropped"],
            "new_dropped_spans": new_result["telemetry"]["canonicalizer_spans_dropped"],
            "old_actor_dropped_spans": old_result["telemetry"]["dropped_actor_spans"],
            "new_actor_dropped_spans": new_result["telemetry"]["dropped_actor_spans"],
            "recovered_spans_total": sum(recovered.values()),
            "recovered_actor_spans": recovered.get("actor", 0),
            "repeated_occurrence_cases": new_result["telemetry"]["repeated_occurrence_cases"],
            "repeated_occurrence_recovered": new_result["telemetry"]["repeated_occurrence_recovered"],
            "repeated_occurrence_unresolved": new_result["telemetry"]["repeated_occurrence_unresolved"],
            "ties": new_result["telemetry"]["tie_cases"],
            "one_to_one_assignment_cases": new_result["telemetry"]["one_to_one_assignment_cases"],
            "assignment_ambiguities": new_result["telemetry"]["assignment_ambiguities"],
            "per_field": per_field_grounding,
        },
        "semantic_invariance_audit": invariance,
        "actor_attribution": {
            **{k: v for k, v in attribution.items() if k != "recovered_actor_spans"},
            "recovered_actor_spans": attribution["recovered_actor_spans"],
            "known_cases": {
                sid: {
                    "recovered_actor_spans": [r for r in attribution["recovered_actor_spans"]
                                              if r["sample_id"] == sid],
                }
                for sid in ("estg_000037", "estg_000103", "estg_000036",
                            "estg_000082", "estg_000286")
            },
            "known_case_notes": {
                "estg_000037": (
                    "Not recovered/needed in the fixed D-full-0813 responses: the OLD "
                    "canonicalizer already anchored both model-emitted 'the fund' actors "
                    "([456,464] and [507,515]) as unique in-clause exact occurrences, so "
                    "no grounding loss existed for them in this response file. The "
                    "historical R3 drop of these two actors is not reproduced by "
                    "D-full-0813."),
                "estg_000103": (
                    "Recovered exactly: OLD dropped the model-emitted actor at "
                    "predicted [176,190] as ambiguous_occurrence; NEW nearest-offset "
                    "grounding re-anchors it to [183,197], the second 'the tax office', "
                    "which overlaps Gold."),
                "estg_000036": (
                    "Not dropped in D-full-0813: the model actor was already exact."),
                "estg_000082": (
                    "Model-emitted pronoun 'it' was dropped by OLD (ambiguous) and is "
                    "recovered by NEW as a coordinate repair; it does not overlap Gold "
                    "and is annotated as an actor false positive."),
                "estg_000286": (
                    "Model-emitted pronoun 'it' was dropped by OLD (ambiguous) and is "
                    "recovered by NEW as a coordinate repair; it does not overlap Gold "
                    "and is annotated as an actor false positive."),
            },
            "remaining_fn_taxonomy": remaining,
            "new_actor_false_positive_analysis": actor_fp,
        },
        "safety": {
            "gold_used_for_algorithm": False,
            "rules_only_predictions_used_for_grounding": False,
            "llm_api_calls": 0,
            "prompt_modified": False,
            "semantic_actor_rules_added": False,
            "actor_inferred_from_condition": False,
            "model_output_text_modified": False,
        },
    }
    report["_artifacts"] = {
        "old_rows": old_rows,
        "old_audits": old_audits,
        "new_rows": new_rows,
        "new_audits": new_audits,
        "start_only_rows": start_only_rows if run_sensitivity else None,
        "start_only_audits": start_only_audits if run_sensitivity else None,
    }
    if start_only_result is not None:
        start_only_overall = start_only_result["overall"]
        report["sensitivity_start_only"] = {
            "role": "post_hoc_sensitivity_not_used_for_algorithm_selection",
            "policy": POLICY_REPAIR,
            "cost_metric": COST_METRIC_START_ONLY,
            "telemetry": start_only_result["telemetry"],
            "overall": start_only_overall,
            "delta_f1_vs_new_start_end": _delta(
                start_only_overall, new_result["overall"], "f1"),
            "note": (
                "The reported NEW arm uses the a-priori sum-of-absolute-endpoint "
                "distance because both model-provided endpoints are localisation "
                "evidence. This arm exists only as a transparency check."),
        }
    return report


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def to_markdown(report: Mapping[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Direct-LLM span-grounding repair (retrospective development A/B)")
    lines.append("")
    lines.append("Zero-API replay of the frozen `D-full-0813` responses; only the "
                 "span-grounding policy changes (OLD `legacy` vs NEW `repair_v1`).")
    lines.append("")
    lines.append("## Overall")
    lines.append("")
    lines.append("| arm | P | R | F1 |")
    lines.append("| --- | --- | --- | --- |")
    ov = report["metric_comparison"]["overall"]
    lines.append(f"| OLD | {_fmt(ov['old'].get('precision'))} | {_fmt(ov['old'].get('recall'))} | {_fmt(ov['old'].get('f1'))} |")
    lines.append(f"| NEW | {_fmt(ov['new'].get('precision'))} | {_fmt(ov['new'].get('recall'))} | {_fmt(ov['new'].get('f1'))} |")
    lines.append(f"| delta | {_fmt(ov['delta_precision'])} | {_fmt(ov['delta_recall'])} | {_fmt(ov['delta_f1'])} |")
    lines.append("")
    lines.append("## Per field")
    lines.append("")
    lines.append("| field | OLD P | OLD R | OLD F1 | NEW P | NEW R | NEW F1 | dF1 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for field, row in report["metric_comparison"]["per_field"].items():
        lines.append(
            f"| {field} | {_fmt(row['old'].get('precision'))} | {_fmt(row['old'].get('recall'))} "
            f"| {_fmt(row['old'].get('f1'))} | {_fmt(row['new'].get('precision'))} "
            f"| {_fmt(row['new'].get('recall'))} | {_fmt(row['new'].get('f1'))} | {_fmt(row['delta_f1'])} |")
    lines.append("")
    lines.append("## Grounding telemetry")
    lines.append("")
    gt = report["grounding_telemetry"]
    for key in (
            "old_dropped_spans", "new_dropped_spans", "old_actor_dropped_spans",
            "new_actor_dropped_spans", "recovered_spans_total", "recovered_actor_spans",
            "repeated_occurrence_cases", "repeated_occurrence_recovered",
            "repeated_occurrence_unresolved", "ties", "one_to_one_assignment_cases",
            "assignment_ambiguities"):
        lines.append(f"- {key}: {gt[key]}")
    lines.append("")
    lines.append("| field | old dropped | new dropped | recovered |")
    lines.append("| --- | --- | --- | --- |")
    for field, row in gt["per_field"].items():
        lines.append(f"| {field} | {row['old_dropped_spans']} | {row['new_dropped_spans']} | {row['recovered_spans']} |")
    lines.append("")
    attr = report["actor_attribution"]
    lines.append("## Actor attribution")
    lines.append("")
    lines.append(f"- old actor FN: {attr['old_actor_fn']}")
    lines.append(f"- new actor FN: {attr['new_actor_fn']}")
    lines.append(f"- recovered by grounding repair: {attr['actor_fn_recovered_by_grounding_repair']}")
    lines.append(f"- remaining: {attr['actor_fn_remaining']}")
    share = attr["grounding_attributable_fn_share"]
    lines.append(f"- grounding-attributable FN share: {_fmt(share) if share is not None else 'n/a'}")
    lines.append("")
    lines.append("| sample | actor | old pred | old outcome | candidates | new pred | strategy | gold overlap |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for row in attr["recovered_actor_spans"]:
        lines.append(
            f"| {row['sample_id']} | {row['actor_text']} | [{row['old_predicted_start']},{row['old_predicted_end']}] "
            f"| {row['old_outcome']} | {row['candidate_occurrences']} | [{row['new_predicted_start']},{row['new_predicted_end']}] "
            f"| {row['resolution_strategy']} | {row['gold_overlap_after_evaluation']} |")
    lines.append("")
    inv = report["semantic_invariance_audit"]
    lines.append("## Safety / invariance audit")
    lines.append("")
    for key in ("invented_semantic_spans", "field_reclassification", "text_mutation",
                "normalized_mutation", "id_mutation", "old_only_spans",
                "invented_modality_evidence", "old_only_modality_evidence",
                "clause_span_text_mutation"):
        lines.append(f"- {key}: {inv[key]}")
    lines.append("")
    lines.append("## Boundaries")
    lines.append("")
    lines.append("- Retrospective development post-processing ablation; no formal claim.")
    lines.append("- The repair is opt-in (`policy=repair_v1`); the production default stays `legacy`.")
    lines.append("- No Prompt / actor-semantics change, no LLM call, no Gold-guided recovery.")
    lines.append("")
    return "\n".join(lines)


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8")


def _write_arm_artifacts(base: Path, name: str, rows, audits) -> None:
    if rows is None:
        return
    arm_dir = base / name
    arm_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(arm_dir / "canonical_predictions.jsonl", rows)
    if audits:
        ordered = [audits[sid] for sid in sorted(audits)]
        _write_jsonl(arm_dir / "span_audits.jsonl", ordered)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-sensitivity", action="store_true")
    args = parser.parse_args()
    targets = [REPORT_JSON, REPORT_MD, LOCAL_OUTPUT_DIR / "manifest.json"]
    existing = [path for path in targets if path.exists()]
    if existing and not args.overwrite:
        print("refusing to overwrite existing artifacts: " + ", ".join(str(p) for p in existing))
        return 2
    report = build_report(run_sensitivity=not args.skip_sensitivity)
    artifacts = report.pop("_artifacts", {})
    LOCAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_arm_artifacts(LOCAL_OUTPUT_DIR, "old", artifacts.get("old_rows"),
                         artifacts.get("old_audits"))
    _write_arm_artifacts(LOCAL_OUTPUT_DIR, "new", artifacts.get("new_rows"),
                         artifacts.get("new_audits"))
    _write_arm_artifacts(LOCAL_OUTPUT_DIR, "new_start_only",
                         artifacts.get("start_only_rows"),
                         artifacts.get("start_only_audits"))
    (LOCAL_OUTPUT_DIR / "manifest.json").write_text(
        json.dumps({
            "schema_version": report["schema_version"],
            "status": report["status"],
            "raw_responses_sha256": report["provenance"]["raw_responses_sha256"],
            "old_policy": report["provenance"]["old_canonicalizer_policy"],
            "new_policy": report["provenance"]["new_canonicalizer_policy"],
            "cost_metric": report["provenance"]["cost_metric"],
            "new_api_calls": 0,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text(to_markdown(report), encoding="utf-8")
    print(json.dumps({
        "overall_old": report["metric_comparison"]["overall"]["old"],
        "overall_new": report["metric_comparison"]["overall"]["new"],
        "overall_delta_f1": report["metric_comparison"]["overall"]["delta_f1"],
        "actor_old_f1": report["metric_comparison"]["per_field"]["actor"]["old"]["f1"],
        "actor_new_f1": report["metric_comparison"]["per_field"]["actor"]["new"]["f1"],
        "actor_fn_recovered": report["actor_attribution"]["actor_fn_recovered_by_grounding_repair"],
        "invariance": report["semantic_invariance_audit"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())