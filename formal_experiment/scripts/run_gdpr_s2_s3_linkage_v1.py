# -*- coding: utf-8 -*-
"""Stage 2 -> Stage 3 linkage: feed EXTERNAL Stage-2 predictions into the
frozen four-new-type Stage-3 detector (development-only, zero API).

Fixed components, single substitution
-------------------------------------
- Stage 1 output: fixed - each frozen panel BPMN copy is parsed with the
  frozen structural contract (``configs/stage1_structural_s11_s14.json``),
  exactly like the original S3.9-EXT panel runner.
- Stage 3: the SAME four method backends as the frozen panel run
  (Winter-style / Sun-style / BM25 / TF-IDF-SVD extensions), same scorer
  formulas, same ``gamma_ext`` (0.5) and the same per-method action-mapping
  gammas read from the same frozen dev configs.  The original panel
  runner's functions are imported and reused (no new detector).
- Stage 2: the ONLY substituted component.  Per variant the six-element
  sentence record is built from an EXTERNAL Stage-2 prediction capsule
  (``data/predictions/gdpr7_sun_rule_only_v1`` for ``rules_only``) via
  ``bpc_hybrid.gdpr_s2_s3_projection`` (first-valid-span projection).
  The detector NEVER falls back to the panel's locked deterministic
  six-element extraction: a missing/failed Stage-2 prediction yields an
  explicit ``stage2_prediction_failed`` row (counted, never back-filled).

Outputs
-------
- per method under
  ``outputs/development/gdpr_s2_s3_linkage_v1_<arm>/<method>/``:
  predictions.jsonl / evaluation.json / paired_evaluation.json /
  substitution_changes.json / manifest.json
- aggregate report ``outputs/reports/gdpr_s2_s3_linkage_v1_<arm>.{json,md}``
- zero LLM/API/network.  Gold-blind with respect to human gold: only the
  frozen dev panel's synthetic expected-violation labels are read (same as
  the original panel run).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for p in (SRC, SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import spacy  # noqa: E402

from bpc_hybrid.gdpr_s2_s3_projection import (  # noqa: E402
    PROJECTION_NAME,
    project_external_sentence,
    projection_summary,
)
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES,
    evaluate_extended,
    evaluate_paired,
)
from bpc_hybrid.sun_stage3.gdpr_change_classifier import (  # noqa: E402
    classify_extended_item,
)
from bpc_hybrid.winter_stage3.winter_similarity import (  # noqa: E402
    WinterSimilarity,
)
import run_s3_extended_violation_panel_v2 as pr  # noqa: E402

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
INPUT_PACK = ROOT / "data/input/gdpr7_stage2_input_v1.json"
ARM_PATHS = {
    "rules_only": ROOT / "data/predictions/gdpr7_sun_rule_only_v1/predictions.json",
    "direct_llm": ROOT / "data/predictions/gdpr7_direct_llm_v1/predictions.json",
}
ARM_PREDICTION_SCHEMAS = {
    "rules_only": "gdpr7_sun_rule_only_predictions@1.0.0",
    "direct_llm": "gdpr7_direct_llm_predictions@1.0.0",
}
METHOD_ORDER = ("winter", "sun", "bm25", "tfidf_svd")
REFERENCE_RUN_DIRS = {
    m: ROOT / f"outputs/development/s3_extended_violation_panel_v2_{m}"
    for m in METHOD_ORDER
}
ARM_LABELS = {
    "rules_only": "Rules-Only (locked B0 v10a, English pass-through)",
    "direct_llm": "Direct-LLM (locked D1 recipe, English sentences)",
}
RUN_SCHEMA = "gdpr_s2_s3_linkage_run@1.0.0"
GAMMA_EXT = 0.5


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _sample_id(rule_id: str, sentence_idx: int) -> str:
    return f"gdpr_{rule_id}_s{sentence_idx + 1:03d}"


def _sentence_text_by_sample(input_doc: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for rule in input_doc.get("rules", []):
        for s in rule.get("sentences", []):
            out[s["sample_id"]] = s["approved_text_en"]
    return out


def _pred_by_sample(pred_doc: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for rec in pred_doc.get("records", []):
        out[rec["sample_id"]] = rec
    return out


def _sims_factory_for(method: str, nlp) -> Callable[..., dict[str, Any]]:
    if method in ("winter", "sun"):
        sim = WinterSimilarity(nlp)
        return lambda record, xml_root: {"action": sim.text_pair,
                                         "text": sim.text_pair}
    if method == "bm25":
        config = _load_json(pr.BM25_CONFIG, "bm25 config")
        return pr._make_bm25_sims(nlp, config)
    config = _load_json(pr.TFIDF_CONFIG, "tfidf config")
    sims = pr._make_tfidf_sims(nlp, config, pr._frozen_tfidf_corpus())
    # _make_tfidf_sims returns a ready dict of sim functions; the original
    # runner wraps it per record.
    return lambda record, xml_root: sims


def _failed_row(method: str, variant: Mapping[str, Any], arm: str,
                sample_id: str, gamma: float, reason: str) -> dict[str, Any]:
    expected = variant["expected_violation"]
    unobs = {
        t: {"observable": False, "reason": reason}
        for t in EXTENDED_TYPES
    }
    return {
        "schema_version": "stage3_extended_prediction@1.0.0",
        "method_id": pr.METHOD_IDS[method],
        "method_display_name": pr.METHOD_DISPLAY[method],
        "run_id": f"gdpr_s2_s3_linkage_v1_{arm}_{method}",
        "task": "violation",
        "item_id": variant["variant_id"],
        "process_id": variant["process_id"],
        "rule_id": variant["rule_id"],
        "expected_violation": expected,
        "check_type": expected,
        "predicted_violation_type": None,
        "scores": {t: None for t in EXTENDED_TYPES},
        "scores_detail": {t: {} for t in EXTENDED_TYPES},
        "observability": unobs,
        "control_scores": {
            t: {"score": None, "observable": False, "reason": reason,
                "exact_contradiction": None}
            for t in EXTENDED_TYPES
        },
        "threshold": GAMMA_EXT,
        "action_mapping_gamma": gamma,
        "gamma_ext": GAMMA_EXT,
        "panel": "synthetic_controlled_error_extension_v2",
        "gold_visible": False,
        "source_hashes": {
            "variant": variant["variant_id"],
            "source_bpmn_sha256": variant["source_bpmn_sha256"],
            "variant_bpmn_sha256": variant["variant_bpmn_sha256"],
            "control_bpmn_sha256": variant["control_bpmn_sha256"],
        },
        "external_arm": arm,
        "external_sample_id": sample_id,
        "external_projection": PROJECTION_NAME,
        "external_failure": reason,
        "method_provenance": (
            f"{pr.METHOD_DISPLAY[method]} gamma_ext={GAMMA_EXT} "
            f"action_gamma={gamma}; external Stage-2 arm {arm} "
            "(development-only linkage; original papers define no such "
            "violation types)"
        ),
    }


def build_arm_predictions(method: str, arm: str, panel: Mapping[str, Any],
                          texts_by_sample: Mapping[str, str],
                          pred_by_sample: Mapping[str, Any],
                          nlp, gamma_ext: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    gamma = pr._gamma_for(method)
    sims_factory = _sims_factory_for(method, nlp)
    rows: list[dict[str, Any]] = []
    projections: list[dict[str, Any]] = []
    for variant in panel["variants"]:
        rid = variant["rule_id"]
        sidx = variant["rule_element"]["sentence_idx"]
        sample_id = _sample_id(rid, sidx)
        pred = pred_by_sample.get(sample_id)
        if pred is None:
            rows.append(_failed_row(method, variant, arm, sample_id, gamma,
                                    "stage2_prediction_missing"))
            projections.append({"ok": False, "error": "prediction_missing",
                                "sample_id": sample_id})
            continue
        text = texts_by_sample.get(sample_id)
        if text is None:
            raise RuntimeError(f"input pack lacks sentence text: {sample_id}")
        proj = project_external_sentence(pred, text, sample_id)
        projections.append({"sample_id": sample_id, **proj})
        if not proj["ok"]:
            rows.append(_failed_row(method, variant, arm, sample_id, gamma,
                                    f"stage2_projection_failed:{proj['error']}"))
            continue
        row = pr.run_method(method, variant, proj["sentence"], sims_factory,
                            gamma, gamma_ext, nlp, panel)
        row["external_arm"] = arm
        row["external_sample_id"] = sample_id
        row["external_projection"] = PROJECTION_NAME
        row["external_diagnostics"] = proj["diagnostics"]
        rows.append(row)
    return rows, projection_summary(projections)


def _reference_by_item(method: str) -> dict[str, Any]:
    path = REFERENCE_RUN_DIRS[method] / "predictions.jsonl"
    out: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[row["item_id"]] = row
    return out


def substitution_changes(rows: list[dict[str, Any]], method: str,
                         ref: Mapping[str, Any]) -> dict[str, Any]:
    """Compare this arm's per-variant prediction with the reference
    deterministic-extraction panel run (context row only, not an arm)."""
    changes: list[dict[str, Any]] = []
    same = 0
    for row in rows:
        item = row["item_id"]
        ref_row = ref.get(item)
        ref_pred = ref_row.get("predicted_violation_type") if ref_row else "unknown"
        arm_pred = row.get("predicted_violation_type")
        if ref_pred == arm_pred:
            same += 1
            continue
        ref_obs = (ref_row or {}).get("observability", {}).get(
            row["expected_violation"], {})
        arm_obs = row.get("observability", {}).get(row["expected_violation"], {})
        machine = classify_extended_item(ref_row or {}, row)
        changes.append({
            "item_id": item,
            "process_id": row["process_id"],
            "rule_id": row["rule_id"],
            "expected_violation": row["expected_violation"],
            "reference_prediction": ref_pred,
            "arm_prediction": arm_pred,
            "reference_observability": {
                "observable": ref_obs.get("observable"),
                "reason": ref_obs.get("reason"),
            },
            "arm_observability": {
                "observable": arm_obs.get("observable"),
                "reason": arm_obs.get("reason"),
            },
            "machine_change_reason": machine["reason"],
            "machine_change_detail": machine.get("detail"),
        })
    return {
        "method": method,
        "reference_source": str(REFERENCE_RUN_DIRS[method].relative_to(ROOT)),
        "same_count": same,
        "changed_count": len(changes),
        "total_items": len(rows),
        "changes": changes,
    }


def run_arm(arm: str, predictions_path: Path | None = None,
            overwrite: bool = False, methods: Sequence[str] = METHOD_ORDER,
            output_root: Path | None = None,
            report_root: Path | None = None) -> dict[str, Any]:
    if arm not in ARM_PATHS:
        raise ValueError(f"unknown arm {arm!r}; expected {sorted(ARM_PATHS)}")
    if any(m not in METHOD_ORDER for m in methods):
        raise ValueError(f"unknown method in {methods!r}")
    path = predictions_path or ARM_PATHS[arm]
    if not path.is_file():
        raise FileNotFoundError(
            f"arm predictions missing: {path} (a real Stage-2 prediction "
            f"capsule is required; dry runs are not results)")
    pred_doc = _load_json(path, "arm predictions")
    if pred_doc.get("schema_version") != ARM_PREDICTION_SCHEMAS[arm]:
        raise ValueError(
            f"arm prediction schema mismatch: got "
            f"{pred_doc.get('schema_version')!r}, expected "
            f"{ARM_PREDICTION_SCHEMAS[arm]!r}")
    panel = _load_json(PANEL, "panel")
    input_doc = _load_json(INPUT_PACK, "GDPR Stage-2 input")
    gamma_ext = float(panel["config"]["gamma_ext"])
    if gamma_ext != GAMMA_EXT:
        raise ValueError(f"gamma_ext drift: {gamma_ext}")
    nlp = spacy.load("en_core_web_sm")
    texts_by_sample = _sentence_text_by_sample(input_doc)
    pred_by_sample = _pred_by_sample(pred_doc)
    output_root = output_root or ROOT / "outputs/development"
    report_root = report_root or ROOT / "outputs/reports"

    started = time.perf_counter()
    methods_out: dict[str, Any] = {}
    for method in methods:
        rows, proj_summary = build_arm_predictions(
            method, arm, panel, texts_by_sample, pred_by_sample, nlp, gamma_ext)
        gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]}
                for v in panel["variants"]}
        evaluation = evaluate_extended(rows, gold)
        paired = evaluate_paired(rows, panel, gamma_ext)
        ref = _reference_by_item(method)
        sub = substitution_changes(rows, method, ref)
        run_dir = (output_root / f"gdpr_s2_s3_linkage_v1_{arm}" / method)
        if run_dir.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite existing run dir: {run_dir}")
        run_dir.mkdir(parents=True, exist_ok=True)
        run_manifest = {
            "schema_version": RUN_SCHEMA,
            "run_id": f"gdpr_s2_s3_linkage_v1_{arm}_{method}",
            "arm": arm,
            "arm_label": ARM_LABELS[arm],
            "method": method,
            "method_id": pr.METHOD_IDS[method],
            "claim_scope": "development_only_linkage",
            "status": "completed",
            "thresholds": {"gamma_ext": GAMMA_EXT,
                           "action_mapping_gamma": pr._gamma_for(method)},
            "bindings": {
                "panel": {"path": str(PANEL.relative_to(ROOT)), "sha256": _sha(PANEL)},
                "input_pack": {"path": str(INPUT_PACK.relative_to(ROOT)), "sha256": _sha(INPUT_PACK)},
                "arm_predictions": {"path": _rel(path), "sha256": _sha(path)},
                "runner": {"path": "scripts/run_gdpr_s2_s3_linkage_v1.py",
                           "sha256": _sha(ROOT / "scripts/run_gdpr_s2_s3_linkage_v1.py")},
                "projection_module": {
                    "path": "src/bpc_hybrid/gdpr_s2_s3_projection.py",
                    "sha256": _sha(ROOT / "src/bpc_hybrid/gdpr_s2_s3_projection.py")},
            },
            "safety": {"llm_api_calls": 0, "network_calls": 0,
                       "human_gold_read": False, "oracle_started": False},
            "external_substitution": {
                "strategy": "stage2_prediction_substitution",
                "projection": PROJECTION_NAME,
                "fallback_to_locked_reference_extraction": False,
                "sentence_coverage": {
                    "panel_variants": len(panel["variants"]),
                    "distinct_bound_sentences": len({
                        _sample_id(v["rule_id"], v["rule_element"]["sentence_idx"])
                        for v in panel["variants"]}),
                },
            },
        }
        (run_dir / "predictions.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                    for r in rows), encoding="utf-8")
        (run_dir / "evaluation.json").write_bytes(_json_bytes(evaluation))
        (run_dir / "paired_evaluation.json").write_bytes(_json_bytes(paired))
        (run_dir / "substitution_changes.json").write_bytes(_json_bytes(sub))
        (run_dir / "projection_summary.json").write_bytes(_json_bytes(proj_summary))
        (run_dir / "manifest.json").write_bytes(_json_bytes(run_manifest))
        methods_out[method] = {
            "method_id": pr.METHOD_IDS[method],
            "variant_only_evaluation": evaluation,
            "paired_evaluation": paired,
            "substitution_changes": sub,
            "projection_summary": proj_summary,
        }
    elapsed = time.perf_counter() - started

    aggregate = {
        "schema_version": "gdpr_s2_s3_linkage_comparison@1.0.0",
        "report_id": f"gdpr_s2_s3_linkage_v1_{arm}",
        "arm": arm,
        "arm_label": ARM_LABELS[arm],
        "claim_scope": "development_only_linkage",
        "generated_utc": _now_utc(),
        "stage2_input": {"path": _rel(INPUT_PACK), "sha256": _sha(INPUT_PACK)},
        "stage2_arm_predictions": {"path": _rel(path), "sha256": _sha(path)},
        "stage3_reference": {
            "note": "reference deterministic-extraction rows are the stored "
                    "original S3.9-EXT panel runs (context only, not an arm)",
            "directories": {m: str(REFERENCE_RUN_DIRS[m].relative_to(ROOT))
                            for m in METHOD_ORDER},
        },
        "thresholds": {"gamma_ext": GAMMA_EXT,
                       "action_mapping_gamma": {m: pr._gamma_for(m)
                                                for m in METHOD_ORDER}},
        "methods": methods_out,
        "runtime_seconds": elapsed,
        "safety": {"llm_api_calls": 0, "network_calls": 0,
                   "human_gold_read": False, "oracle_started": False,
                   "frozen_bpmn_modified": False},
    }
    report_root = report_root or ROOT / "outputs/reports"
    report_root.mkdir(parents=True, exist_ok=True)
    report_json = report_root / f"gdpr_s2_s3_linkage_v1_{arm}.json"
    if report_json.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing report: {report_json}")
    report_json.write_bytes(_json_bytes(aggregate))
    report_md = report_root / f"gdpr_s2_s3_linkage_v1_{arm}.md"
    report_md.write_text(render_markdown(aggregate, arm), encoding="utf-8")
    return aggregate


def _now_utc() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def render_markdown(agg: Mapping[str, Any], arm: str) -> str:
    lines: list[str] = []
    lines.append(f"# GDPR Stage-2 → Stage-3 linkage v1 — arm `{arm}` (development-only)")
    lines.append("")
    lines.append(f"- Stage-2 arm: {agg['arm_label']}")
    lines.append(f"- Stage-2 input: `{agg['stage2_input']['path']}` "
                 f"(sha256 {agg['stage2_input']['sha256'][:12]}…)")
    lines.append(f"- Arm predictions: `{agg['stage2_arm_predictions']['path']}` "
                 f"(sha256 {agg['stage2_arm_predictions']['sha256'][:12]}…)")
    lines.append("- Fixed Stage 1/3: frozen panel BPMN copies + frozen structural "
                 "contract + the original panel runner's four backends, scorer "
                 "formulas, gamma_ext 0.5 and per-method action gammas "
                 f"({', '.join(f'{m}={g}' for m, g in agg['thresholds']['action_mapping_gamma'].items())}).")
    lines.append("- Substitution: per-variant six-element sentence records come "
                 "ONLY from the external Stage-2 predictions "
                 "(first-valid-span projection); failures are counted, never "
                 "back-filled with the locked reference extraction.")
    lines.append("")
    lines.append("## Variant-only detection (40 synthetic variants) and paired control+variant (80 objects)")
    lines.append("")
    lines.append("| method | variant macro-F1 | variant exact | unobservable | 5-class acc (80) | control FP rate (40) | paired acc (40) |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for method, info in agg["methods"].items():
        ev = info["variant_only_evaluation"]
        pe = info["paired_evaluation"]
        lines.append(
            f"| {method} | {_fmt(ev['macro_f1'])} | {_fmt(ev['exact_type_accuracy'])} "
            f"| {ev['unobservable']} | {_fmt(pe['five_class_accuracy'])} "
            f"| {_fmt(pe['control_false_positive_rate'])} | {_fmt(pe['paired_accuracy'])} |")
    lines.append("")
    lines.append("### Per-type variant-only P/R/F1")
    lines.append("")
    lines.append("| method | prohibited | condition | constraint | exception |")
    lines.append("|---|---:|---:|---:|---:|")
    for method, info in agg["methods"].items():
        ev = info["variant_only_evaluation"]
        row = []
        for t in EXTENDED_TYPES:
            pt = ev["per_type"][t]
            row.append(f"{_fmt(pt['precision'])}/{_fmt(pt['recall'])}/{_fmt(pt['f1'])}")
        lines.append(f"| {method} | {' | '.join(row)} |")
    lines.append("")
    lines.append("## Substitution changes vs reference deterministic extraction")
    lines.append("")
    lines.append("| method | same | changed | total |")
    lines.append("|---|---:|---:|---:|")
    for method, info in agg["methods"].items():
        s = info["substitution_changes"]
        lines.append(f"| {method} | {s['same_count']} | {s['changed_count']} | {s['total_items']} |")
    lines.append("")
    lines.append("Per-item change details (reference prediction → arm prediction, "
                 "observability reasons) are in each method's "
                 "`substitution_changes.json`; per-sample rows in `predictions.jsonl`.")
    lines.append("")
    lines.append("## Stage-2 projection accounting")
    lines.append("")
    for method, info in agg["methods"].items():
        ps = info["projection_summary"]
        lines.append(f"- {method}: failed projections {len(ps['failed'])} "
                     f"({', '.join(ps['failed']) or 'none'}); "
                     f"empty-action sentences {ps['empty_action_sentences']}; "
                     f"empty-modality sentences {ps['empty_modality_sentences']}; "
                     f"invalid predicted spans {ps['total_invalid_spans']}.")
    lines.append("")
    lines.append("## Boundaries")
    lines.append("")
    lines.append("- DEV_ONLY controlled synthetic panel (40 variants + 40 controls); "
                 "NOT human Gold, NOT the formal Oracle; never merged with the "
                 "33-item human Gold.")
    if arm == "rules_only":
        lines.append("- Rules-Only modality labels come from the locked B0 v10a "
                     "pipeline with the disclosed English pass-through (German "
                     "classifier contract) — a descriptive Stage-2 arm.")
    elif arm == "direct_llm":
        lines.append("- Direct-LLM rows come from the promoted formal arm capsule "
                     "data/predictions/gdpr7_direct_llm_v1 (real authorized "
                     "executor output; coordinate-only, containment-scanned).")
    lines.append("- Zero LLM/API/network; frozen BPMN, thresholds and panel "
                 "bytes unchanged.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=sorted(ARM_PATHS), required=True)
    parser.add_argument("--predictions", type=Path, default=None)
    parser.add_argument("--methods", default=",".join(METHOD_ORDER))
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--report-root", type=Path, default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    methods = tuple(m.strip() for m in args.methods.split(",") if m.strip())
    try:
        summary = run_arm(args.arm, args.predictions, args.overwrite,
                          methods=methods, output_root=args.output_root,
                          report_root=args.report_root)
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
        print(f"linkage refused: {exc}")
        return 2
    print(f"arm={args.arm} methods={len(summary['methods'])} "
          f"runtime_seconds={summary['runtime_seconds']:.1f} "
          f"llm_api_calls=0 network_calls=0")
    for method, info in summary["methods"].items():
        ev = info["variant_only_evaluation"]
        pe = info["paired_evaluation"]
        print(f"  {method}: variant macro={ev['macro_f1']:.4f} exact="
              f"{ev['exact_type_accuracy']:.4f} unobs={ev['unobservable']} | "
              f"paired acc={pe['paired_accuracy']:.4f} control FP="
              f"{pe['control_false_positive_rate']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
