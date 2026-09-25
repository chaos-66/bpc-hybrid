# -*- coding: utf-8 -*-
"""Assemble R3 delivery evidence: M0/M1/M2 metrics, wiring, event-projection
before/after, and backend candidate changes.  Read-only over frozen outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
M0_REPORT = ROOT / "outputs/reports/stage3_table3_v4_r2.json"
M1_REPORT = ROOT / "outputs/reports/stage3_table3_r3_m1.json"
M2_REPORT = ROOT / "outputs/reports/stage3_table3_r3_m2.json"
M1_OUT = ROOT / "outputs/development/stage3_table3_r3_m1"
M2_OUT = ROOT / "outputs/development/stage3_table3_r3_m2"
R2_OUT = ROOT / "outputs/development/stage3_table3_v4_r2"
MECH_M1 = ROOT / "outputs/reports/stage3_table3_r3_mechanism_m1.json"
MECH_M2 = ROOT / "outputs/reports/stage3_table3_r3_mechanism_m2.json"
DELIVERY_JSON = ROOT / "outputs/reports/stage3_table3_r3_delivery_v1.json"
DELIVERY_MD = ROOT / "outputs/reports/stage3_table3_r3_delivery_v1.md"
WIRING_JSON = ROOT / "outputs/reports/stage3_table3_r3_wiring_evidence_v1.json"
PROJECTION_JSON = ROOT / "outputs/reports/stage3_table3_r3_projection_fix_v1.json"
BACKEND_DIFF_JSON = ROOT / "outputs/reports/stage3_table3_r3_backend_diff_v1.json"


def _load_json(path: Path):
    if not Path(path).is_file():
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _metrics(report: Mapping[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {}
    out: dict[str, Any] = {}
    for method, block in (report.get("methods") or {}).items():
        out[method] = {
            "status": block.get("method_status"),
            "per_type": block.get("per_type"),
            "overall": block.get("overall"),
        }
    return out


def _metric_row(metrics: Mapping[str, Any], config_id: str, method: str, check_type: str) -> dict[str, Any]:
    block = ((metrics.get(config_id) or {}).get(method) or {})
    source = block.get("overall") if check_type == "OVERALL" else ((block.get("per_type") or {}).get(check_type) or {})
    source = source or {}
    return {
        "config": config_id,
        "method": method,
        "type": check_type,
        "precision": source.get("precision"),
        "recall": source.get("recall"),
        "f1": source.get("f1"),
        "tp": source.get("tp"),
        "fp": source.get("fp"),
        "fn": source.get("fn"),
        "tn": source.get("tn"),
        "unknown_positive": source.get("unknown_positive"),
        "unknown_negative": source.get("unknown_negative"),
        "not_applicable": source.get("not_applicable_cells"),
        "coverage": source.get("observable_coverage"),
        "cells": source.get("cells"),
        "predicted_positive": source.get("predicted_positive"),
    }


def _model_rows() -> list[dict[str, Any]]:
    index = _load_json(ROOT / "outputs/development/stage3_table3_r3_p2_sidecars/index.json") or {}
    rows: list[dict[str, Any]] = []
    for case in index.get("cases") or []:
        sidecar = _load_json(ROOT / case["sidecar_path"])
        if not sidecar:
            continue
        for node in sidecar.get("nodes") or []:
            rows.append({
                "case_id": case["case_id"],
                "node_id": node.get("node_id"),
                "node_type": node.get("node_type"),
                "original_label": node.get("raw_label"),
                "actor_surface": node.get("actor_surface"),
                "action_surface": node.get("action_surface"),
                "business_object_surface": node.get("business_object_surface"),
                "match_source_text": node.get("match_source_text"),
                "matching_text": node.get("matching_text"),
                "parse_status": node.get("parse_status"),
                "parse_source": node.get("parse_source"),
            })
    return rows


def _rule_rows_out(out_dir: Path) -> dict[tuple[str, str], Mapping[str, Any]]:
    doc = _load_json(out_dir / "rule_records.json") or {}
    rows: dict[tuple[str, str], Mapping[str, Any]] = {}
    for method, block in (doc or {}).items():
        for rule_id, record in (block.get("records") or {}).items():
            rows[(method, rule_id)] = record
    return rows


def _projection_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    old = _rule_rows_out(R2_OUT)
    new = _rule_rows_out(M1_OUT)
    rows: list[dict[str, Any]] = []
    article18 = None
    for (method, rule_id), new_rec in sorted(new.items()):
        old_rec = old.get((method, rule_id)) or {}
        old_edges = old_rec.get("order_relations") or []
        new_edges = new_rec.get("order_relations") or []
        view_rows = new_rec.get("order_relation_views") or []
        predicates = [row.get("predicate") for row in view_rows if row.get("predicate")]
        changed = [list(map(str, x)) for x in old_edges] != [list(map(str, x)) for x in new_edges]
        row = {
            "method": method,
            "rule_id": rule_id,
            "old_projection": (old_rec.get("order_relation_projection") or {}).get("projection"),
            "new_projection": (new_rec.get("order_relation_projection") or {}).get("projection"),
            "old_edges": [list(map(str, x)) for x in old_edges],
            "new_edges": [list(map(str, x)) for x in new_edges],
            "changed": changed,
            "event_predicates_preserved": predicates,
            "new_order_relation_views": view_rows,
        }
        rows.append(row)
        if rule_id == "article18p3":
            article18 = row
    summary = {
        "changed_rule_method_pairs": sum(1 for row in rows if row["changed"]),
        "predicate_rows": [row for row in rows if row.get("event_predicates_preserved")],
        "article18p3": article18,
    }
    return rows, summary


def _rule_side_rows(out_dir: Path) -> list[dict[str, Any]]:
    predictions = _load_json(out_dir / "predictions.json") or {}
    rows: list[dict[str, Any]] = []
    for row in predictions.get("records") or []:
        if row.get("row_method_id") not in ("sun", "ours"):
            continue
        for mr in ((row.get("method_evidence") or {}).get("mapping_table") or []):
            candidates = mr.get("candidates") or []
            selected = next((c for c in candidates if c.get("selected")), None)
            tied = [c.get("node_id") for c in candidates if c.get("tied")]
            best = candidates[0] if candidates else {}
            rows.append({
                "method": row.get("row_method_id"),
                "case_id": row.get("case_id"),
                "rule_id": mr.get("rule_id"),
                "kind": mr.get("kind"),
                "offsets": mr.get("offsets"),
                "original_predicted_text": mr.get("rule_original_text"),
                "action_surface": mr.get("rule_action_surface"),
                "business_object_surface": mr.get("rule_business_object_surface"),
                "actual_match_source_text": mr.get("rule_match_source_text"),
                "normalized_matching_text": mr.get("rule_matching_text"),
                "parse_status": mr.get("rule_parse_status"),
                "selected_node_id": selected.get("node_id") if selected else None,
                "selected_similarity": selected.get("similarity") if selected else None,
                "best_similarity": best.get("similarity"),
                "tied_node_ids": tied,
                "candidate_count": len(candidates),
                "gamma_pass": bool(best.get("similarity") is not None and float(best.get("similarity")) > 0.8),
            })
    return rows


def _backend_diff() -> dict[str, Any]:
    m1 = _rule_side_rows(M1_OUT)
    m2 = _rule_side_rows(M2_OUT) if M2_OUT.is_dir() and (M2_OUT / "predictions.json").is_file() else None
    if m2 is None:
        return {"status": "m2_not_run", "changed": [], "counts": {"m1_rows": len(m1), "m2_rows": 0, "changed_rows": 0}}
    m1_by = {(r["method"], r["case_id"], r["rule_id"], r["kind"], r["original_predicted_text"]): r for r in m1}
    m2_by = {(r["method"], r["case_id"], r["rule_id"], r["kind"], r["original_predicted_text"]): r for r in m2}
    changed: list[dict[str, Any]] = []
    for key in sorted(set(m1_by) & set(m2_by)):
        a, b = m1_by[key], m2_by[key]
        if (a.get("selected_node_id") != b.get("selected_node_id")
                or a.get("best_similarity") != b.get("best_similarity")):
            changed.append({
                "method": key[0], "case_id": key[1], "rule_id": key[2],
                "kind": key[3], "original_predicted_text": key[4],
                "m1_selected_node_id": a.get("selected_node_id"),
                "m2_selected_node_id": b.get("selected_node_id"),
                "m1_best_similarity": a.get("best_similarity"),
                "m2_best_similarity": b.get("best_similarity"),
                "m1_actual_match_source": a.get("actual_match_source_text"),
                "m2_actual_match_source": b.get("actual_match_source_text"),
            })
    return {"status": "compared", "changed": changed,
            "counts": {"m1_rows": len(m1), "m2_rows": len(m2), "changed_rows": len(changed)}}


def _mechanism() -> dict[str, Any]:
    return {
        "m1": _load_json(MECH_M1),
        "m2": _load_json(MECH_M2),
        "m2_available": MECH_M2.is_file(),
    }


def _order_category_summary(out_dir: Path) -> dict[str, dict[str, int]]:
    if not out_dir.is_dir() or not (out_dir / "predictions.json").is_file():
        return {}
    predictions = _load_json(out_dir / "predictions.json") or {}
    summary: dict[str, dict[str, int]] = {}
    for row in predictions.get("records") or []:
        method = str(row.get("row_method_id"))
        if method not in ("sun", "ours"):
            continue
        summary.setdefault(method, {})
        for rule_id, signals in (row.get("signals_by_rule") or {}).items():
            signal = (signals or {}).get("out_of_order") or {}
            denom = int(signal.get("denominator") or 0)
            if denom > 0:
                category = str(signal.get("status"))
            else:
                details = ((signal.get("evidence") or {}).get("details") or [])
                reasons = [str(d.get("reason")) for d in details if isinstance(d, dict)]
                if any("similarity below gamma" in r for r in reasons):
                    category = "endpoint_similarity_below_gamma"
                elif not reasons:
                    category = "no_rule_order_relation_or_endpoint_rejected"
                else:
                    category = reasons[0]
            summary[method][category] = summary[method].get(category, 0) + 1
    return summary


def build() -> dict[str, Any]:
    m0_report = _load_json(M0_REPORT)
    m1_report = _load_json(M1_REPORT)
    m2_report = _load_json(M2_REPORT)
    metrics = {
        "M0_R2": _metrics(m0_report),
        "M1_P2_v4_sm": _metrics(m1_report),
        "M2_P2_v4_lg": _metrics(m2_report) if m2_report else {"status": "not_run"},
    }
    comparison_rows = []
    for cfg_id, methods in metrics.items():
        for method in ("sun", "ours", "winter"):
            for check_type in ("missing_action", "incorrect_actor", "out_of_order", "OVERALL"):
                comparison_rows.append(_metric_row(metrics, cfg_id, method, check_type))
    model_rows = _model_rows()
    projection_rows, projection_summary = _projection_rows()
    rule_rows = _rule_side_rows(M1_OUT)
    backend_diff = _backend_diff()
    mech = _mechanism()
    order_categories = {
        "M1_P2_v4_sm": _order_category_summary(M1_OUT),
        "M2_P2_v4_lg": _order_category_summary(M2_OUT) if M2_OUT.is_dir() else {},
    }
    wiring = {
        "schema_version": "stage3_table3_r3_wiring_evidence@1.0.0",
        "old_bypass_chain": [
            "scripts/run_stage3_table3_v4_r2.py",
            "scripts/run_stage3_table3_v4_r1.py::_sun_case_payload",
            "bpc_hybrid.sun_stage3.sun_model.SunProcessModel (reads full activity/event label names directly)",
            "bpc_hybrid.stage3_sun_style_checker/NoGateSunChecker",
        ],
        "new_wired_chain": [
            "scripts/run_stage3_table3_r3.py",
            "scripts/build_stage3_r3_sidecars.py -> bpc_hybrid.stage3_r3_p2_adapter_v1.build_model_sidecar",
            "frozen bpc_hybrid.stage1_label_semantics_p2.render_p2_label_semantics (activities)",
            "R3 named-event extension (same frozen label analysis, explicit provenance note)",
            "bpc_hybrid.sun_stage3.r3_sun_scorer.R3SunScorer (P2 matching views + stable node IDs)",
            "bpc_hybrid.sun_stage3.temporal_projection_v4_r3 (local event-predicate preservation)",
        ],
        "rule_side_wiring": "predicted action/endpoint text -> frozen P2 label analysis -> action_surface/business_object_surface -> fixed join -> frozen lemma -> R3 scorer",
        "model_rows": model_rows,
        "rule_rows": rule_rows,
    }
    projection_doc = {
        "schema_version": "stage3_table3_r3_projection_fix@1.0.0",
        "summary": projection_summary,
        "rows": projection_rows,
    }
    delivery = {
        "schema_version": "stage3_table3_r3_delivery@1.0.0",
        "task_id": "S3-TABLE3-R3-INTEGRATION",
        "development_status": "development_retrospective_not_independent_test",
        "status": ("complete_with_m2" if m2_report else "complete_m1_m2_blocked"),
        "metrics": metrics,
        "comparison_rows": comparison_rows,
        "wiring_evidence_path": WIRING_JSON.relative_to(ROOT).as_posix(),
        "projection_fix_path": PROJECTION_JSON.relative_to(ROOT).as_posix(),
        "backend_diff_path": BACKEND_DIFF_JSON.relative_to(ROOT).as_posix(),
        "backend_diff_counts": backend_diff.get("counts"),
        "order_category_summary": order_categories,
        "mechanism": {
            "m1": (mech.get("m1") or {}).get("summary"),
            "m2": (mech.get("m2") or {}).get("summary") if mech.get("m2") else None,
            "m2_available": mech.get("m2_available"),
        },
        "resolved": [
            "Stage1 P2 activity semantics are now explicitly wired into Stage3 model-side action/object/actor views.",
            "Named events receive an independently documented R3 extension of the same frozen P2 label analysis.",
            "Order projection v4 preserves a unique local event predicate in the selected complement; article18p3 now retains 'is lifted' / 'lifted' rather than truncating to 'the restriction of processing'.",
            "Action/order mapping returns stable node IDs and resolves equal scores by ascending node ID while retaining all tied candidates.",
            "M1/M2 share parser, P2 views, projection, candidates, formulas, and thresholds; only the Sun/Ours similarity backend differs.",
        ],
        "remaining": [
            "Stage2 prediction errors remain: some canonical actions/actors are missing or fragmented before Stage3; R3 does not repair them.",
            "Frozen P2 limitations remain: e.g. some capitalized imperative labels lose their business object because the frozen verb-root resource does not contain the verb (observed limitation fixture).",
            "Similarity-threshold limitations remain: the fixed gamma=0.8 still rejects the article18p3 after-endpoint mapping even after predicate preservation, because the M1 sm best score is below gamma.",
            "Winter remains native with before/prior-to unsupported; its R2 result is reused and is not rerun.",
            "M2 is development-retrospective and cannot be reported as an independent test or as proof that lg is generally better.",
        ],
    }
    _write_json(WIRING_JSON, wiring)
    _write_json(PROJECTION_JSON, projection_doc)
    _write_json(BACKEND_DIFF_JSON, backend_diff)
    _write_json(DELIVERY_JSON, delivery)

    lines = ["# S3-TABLE3-R3-INTEGRATION delivery (M0/M1/M2)", "",
             "Development/retrospective result. Reference is AI-constructed and is not formal Gold.", ""]
    lines += ["## Overall metrics", "", "| Config | Method | P | R | F1 | Coverage | Unknown+ | Unknown- | N/A |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for cfg_id, methods in metrics.items():
        for method in ("sun", "ours", "winter"):
            block = (methods.get(method) or {})
            overall = block.get("overall") or {}
            lines.append(
                f"| {cfg_id} | {method} | {overall.get('precision')} | {overall.get('recall')} | "
                f"{overall.get('f1')} | {overall.get('observable_coverage')} | "
                f"{overall.get('unknown_positive')} | {overall.get('unknown_negative')} | {overall.get('not_applicable_cells')} |")
    lines += ["", "## Event-projection fix", "",
              f"- changed rule/method pairs: `{projection_summary.get('changed_rule_method_pairs')}`",
              f"- predicate-bearing new rows: `{len(projection_summary.get('predicate_rows') or [])}`", ""]
    if projection_summary.get("article18p3"):
        row = projection_summary["article18p3"]
        lines += [f"- article18p3/{row.get('method')}: old `{row.get('old_edges')}` -> new `{row.get('new_edges')}`; predicates `{row.get('event_predicates_preserved')}`", ""]
    lines += ["## M1/M2 backend contrast", ""]
    lines.append(f"- status: `{backend_diff.get('status')}`; `{backend_diff.get('counts')}`")
    lines += ["", "## Mechanism/development samples", ""]
    for tag, summary in (("M1", (mech.get("m1") or {}).get("summary")), ("M2", (mech.get("m2") or {}).get("summary") if mech.get("m2") else None)):
        lines.append(f"- {tag}: `{summary}`")
    lines += ["", "## Order-signal categories", ""]
    for cfg_id, methods in order_categories.items():
        for method, counts in sorted(methods.items()):
            lines.append(f"- {cfg_id}/{method}: `{counts}`")
    lines += ["", "## Resolved", ""]
    for item in delivery["resolved"]:
        lines.append(f"- {item}")
    lines += ["", "## Remaining", ""]
    for item in delivery["remaining"]:
        lines.append(f"- {item}")
    lines += ["", "## Artifacts", "",
              f"- wiring: `{WIRING_JSON.relative_to(ROOT).as_posix()}`",
              f"- projection fix: `{PROJECTION_JSON.relative_to(ROOT).as_posix()}`",
              f"- backend diff: `{BACKEND_DIFF_JSON.relative_to(ROOT).as_posix()}`", ""]
    DELIVERY_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return delivery


if __name__ == "__main__":
    doc = build()
    print(json.dumps({k: doc.get(k) for k in ("status", "backend_diff_counts", "mechanism")}, ensure_ascii=False, indent=2))
