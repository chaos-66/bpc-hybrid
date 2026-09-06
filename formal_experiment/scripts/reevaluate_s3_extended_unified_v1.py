# -*- coding: utf-8 -*-
"""Offline unified-decision re-evaluation of the S3.9-EXT four new-type
extensions (reference deterministic extraction AND external Stage-2 arms).

What it does
------------
1. Loads PERSISTED per-sample rows (variant scores/scores_detail/
   observability + control_scores) — no re-scoring, no LLM, no Stage-2
   re-run, no Gold read while predictions are being formed.
2. Rebuilds each row's variant prediction with the SAME deterministic
   five-class rule that the paired evaluation has always used for the
   control side (``control_prediction_from_scores`` in fixed EXTENDED_TYPES
   priority; unobservable types skipped; all four unobservable -> None).
   The old "expected-type-conditional" prediction is preserved per row under
   ``predicted_conditional_old`` and the old style is labelled as
   conditional detection for the preset type (NOT classification).
3. Evaluates: 40-variant four-class view, 80-object paired five-class view
   (40 compliant controls + 40 variants), a 5x5 confusion matrix, per-class
   P/R/F1, control false-positive rate, unobservable counts and reasons,
   and an old-vs-new comparison (including a self-check that the stored
   old paired numbers are reproduced exactly from the persisted rows).
4. Writes new artifacts under
   ``outputs/development/s3_extended_unified_v1/<source>/<method>/`` and an
   aggregate report under ``outputs/reports/s3_extended_unified_v1.{json,md}``.
   Original run dirs and reports are never modified.

Sources
-------
- reference: the original S3.9-EXT panel runs
  ``outputs/development/s3_extended_violation_panel_v2_<method>/``
  (deterministic reference extraction; NOT human Gold);
- rules_only: the GDPR Stage-2 -> Stage-3 linkage Rules-Only arm
  ``outputs/development/gdpr_s2_s3_linkage_v1_rules_only/<method>/``
  (external B0 v10a predictions).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for p in (SRC, SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from bpc_hybrid.s3_extended_unified import (  # noqa: E402
    UNIFIED_DECISION_NAME,
    unified_prediction,
    unified_rows,
)
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES,
    NONE_LABEL,
    control_prediction_from_scores,
    evaluate_extended,
    evaluate_paired,
)

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
OUT_ROOT = ROOT / "outputs/development"
REPORT_ROOT = ROOT / "outputs/reports"
METHOD_ORDER = ("winter", "sun", "bm25", "tfidf_svd")
SOURCES: dict[str, dict[str, Path]] = {
    "reference": {
        m: OUT_ROOT / f"s3_extended_violation_panel_v2_{m}" for m in METHOD_ORDER
    },
    "rules_only": {
        m: OUT_ROOT / f"gdpr_s2_s3_linkage_v1_rules_only/{m}"
        for m in METHOD_ORDER
    },
}
SOURCE_LABELS = {
    "reference": "reference deterministic extraction (original S3.9-EXT run; NOT human Gold)",
    "rules_only": "external Stage-2 arm: Rules-Only (locked B0 v10a, English pass-through)",
}
REPORT_SCHEMA = "s3_extended_unified_comparison@1.0.0"


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _gold_synthetic(panel: Mapping[str, Any]) -> dict[str, Any]:
    return {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}


def confusion_matrix(rows: Sequence[Mapping[str, Any]],
                     gold: Mapping[str, Any], gamma_ext: float,
                     panel: Mapping[str, Any]) -> dict[str, Any]:
    """5x5 confusion over the 80 paired objects (controls gold=none).

    Predicted None is not a class: it is reported separately as
    ``predicted_none`` (errors never dropped, mirroring evaluate_paired).
    """
    labels = (NONE_LABEL,) + EXTENDED_TYPES
    matrix = {g: {p: 0 for p in labels} for g in labels}
    predicted_none = {"none_gold": 0, "violation_gold": 0,
                      "violation_gold_compliant_observable": 0}
    by_gold_unobservable: dict[str, int] = {}
    for row in rows:
        variant = next((v for v in panel["variants"]
                        if v["variant_id"] == row["item_id"]), None)
        if variant is None:
            raise ValueError(f"unknown item_id {row['item_id']}")
        expected = variant["expected_violation"]
        # control object
        ctl = control_prediction_from_scores(row["control_scores"], gamma_ext)
        cpred = ctl["predicted"]
        if cpred is None:
            predicted_none["none_gold"] += 1
        else:
            matrix[NONE_LABEL][cpred] += 1
        # variant object (raw unified decision; 'none' = observable
        # compliant, None = all four types unobservable)
        vpred = row["unified_predicted_raw"]
        if vpred == NONE_LABEL:
            predicted_none["violation_gold"] += 1
            predicted_none["violation_gold_compliant_observable"] = (
                predicted_none.get("violation_gold_compliant_observable", 0) + 1)
        elif vpred is None:
            predicted_none["violation_gold"] += 1
            obs = row.get("observability", {}).get(expected, {})
            reason = obs.get("reason") or "unspecified"
            by_gold_unobservable[reason] = by_gold_unobservable.get(reason, 0) + 1
        else:
            matrix[expected][vpred] += 1
    per_class: dict[str, Any] = {}
    for g in labels:
        tp = matrix[g][g]
        fp = sum(matrix[other][g] for other in labels if other != g)
        fn = sum(matrix[g][other] for other in labels if other != g)
        per_class[g] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(tp / (tp + fp), 4) if tp + fp else 0.0,
            "recall": round(tp / (tp + fn), 4) if tp + fn else 0.0,
            "f1": round(2 * tp / (2 * tp + fp + fn), 4) if (2 * tp + fp + fn) else 0.0,
        }
    return {
        "labels": list(labels),
        "matrix": matrix,
        "per_class": per_class,
        "predicted_none": predicted_none,
        "unobservable_by_reason_variants": by_gold_unobservable,
        "total_objects": 80,
    }


def run_source(source: str, methods: Sequence[str],
               overwrite: bool = False, output_root: Path | None = None,
               report_root: Path | None = None) -> dict[str, Any]:
    if source not in SOURCES:
        raise ValueError(f"unknown source {source!r}")
    panel = json.loads(PANEL.read_text(encoding="utf-8"))
    gamma_ext = float(panel["config"]["gamma_ext"])
    gold = _gold_synthetic(panel)
    out_base = output_root or OUT_ROOT
    rep_base = report_root or REPORT_ROOT
    started = time.perf_counter()
    methods_out: dict[str, Any] = {}
    for method in methods:
        src_dir = SOURCES[source][method]
        rows_path = src_dir / "predictions.jsonl"
        if not rows_path.is_file():
            raise FileNotFoundError(f"{source}/{method} predictions missing: {rows_path}")
        original = _load_rows(rows_path)
        unified = unified_rows(original, gamma_ext)
        # evaluation with gold AFTER predictions are fixed
        ev_unified = evaluate_extended(unified, gold)
        paired_unified = evaluate_paired(unified, panel, gamma_ext)
        cm = confusion_matrix(unified, gold, gamma_ext, panel)
        # old-conditional reproduction for comparison (persisted rows)
        old_rows = [dict(r) for r in original]
        ev_old = evaluate_extended(old_rows, gold)
        paired_old = evaluate_paired(old_rows, panel, gamma_ext)
        old_vs_new = {
            "method": method,
            "variant_only": {
                "macro_f1": {"old_conditional": ev_old["macro_f1"],
                             "new_unified": ev_unified["macro_f1"]},
                "exact_type_accuracy": {"old_conditional": ev_old["exact_type_accuracy"],
                                        "new_unified": ev_unified["exact_type_accuracy"]},
                "wrong_type": {"old_conditional": ev_old["wrong_type"],
                               "new_unified": ev_unified["wrong_type"]},
                "detected": {"old_conditional": ev_old["detected"],
                             "new_unified": ev_unified["detected"]},
                "unobservable": {"old_conditional": ev_old["unobservable"],
                                 "new_unified": ev_unified["unobservable"]},
            },
            "paired": {
                "five_class_accuracy": {
                    "old_conditional": paired_old["five_class_accuracy"],
                    "new_unified": paired_unified["five_class_accuracy"]},
                "variant_exact_type_accuracy": {
                    "old_conditional": paired_old["variant_exact_type_accuracy"],
                    "new_unified": paired_unified["variant_exact_type_accuracy"]},
                "control_false_positive_rate": paired_old["control_false_positive_rate"],
                "paired_accuracy": {
                    "old_conditional": paired_old["paired_accuracy"],
                    "new_unified": paired_unified["paired_accuracy"]},
            },
            "note": ("old_conditional = per-sample prediction 'preset expected "
                     "type or None' (original panel rule, NOT classification); "
                     "new_unified = one five-class rule on both sides"),
        }
        run_dir = (out_base / "s3_extended_unified_v1" / source / method)
        if run_dir.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite: {run_dir}")
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "predictions.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                    for r in unified), encoding="utf-8")
        (run_dir / "evaluation_variant_only.json").write_bytes(_json_bytes(ev_unified))
        (run_dir / "paired_evaluation.json").write_bytes(_json_bytes(paired_unified))
        (run_dir / "confusion_matrix.json").write_bytes(_json_bytes(cm))
        (run_dir / "old_vs_new.json").write_bytes(_json_bytes(old_vs_new))
        (run_dir / "manifest.json").write_bytes(_json_bytes({
            "schema_version": "s3_extended_unified_run@1.0.0",
            "source": source,
            "source_label": SOURCE_LABELS[source],
            "method": method,
            "decision": UNIFIED_DECISION_NAME,
            "gamma_ext": gamma_ext,
            "input_rows": {"path": str(rows_path.relative_to(ROOT)),
                           "sha256": _sha(rows_path), "rows": len(original)},
            "panel": {"path": str(PANEL.relative_to(ROOT)), "sha256": _sha(PANEL)},
            "runner": {"path": "scripts/reevaluate_s3_extended_unified_v1.py",
                       "sha256": _sha(ROOT / "scripts/reevaluate_s3_extended_unified_v1.py")},
            "gold_read_only_inside_evaluation": True,
            "safety": {"llm_api_calls": 0, "network_calls": 0,
                       "gold_modified": False, "original_run_dirs_modified": False},
        }))
        methods_out[method] = {
            "variant_only_evaluation_unified": ev_unified,
            "paired_evaluation_unified": paired_unified,
            "confusion_matrix": cm,
            "old_vs_new": old_vs_new,
        }
    aggregate = {
        "schema_version": REPORT_SCHEMA,
        "source": source,
        "source_label": SOURCE_LABELS[source],
        "decision": UNIFIED_DECISION_NAME,
        "gamma_ext": gamma_ext,
        "methods": methods_out,
        "runtime_seconds": time.perf_counter() - started,
        "safety": {"llm_api_calls": 0, "network_calls": 0},
    }
    rep_base.mkdir(parents=True, exist_ok=True)
    out_json = rep_base / f"s3_extended_unified_v1_{source}.json"
    if out_json.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite: {out_json}")
    out_json.write_bytes(_json_bytes(aggregate))
    md = rep_base / f"s3_extended_unified_v1_{source}.md"
    md.write_text(_render_markdown(aggregate, source), encoding="utf-8")
    return aggregate


def _fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def _render_markdown(agg: Mapping[str, Any], source: str) -> str:
    lines = [
        f"# S3.9-EXT unified five-class re-evaluation — source `{source}`",
        "",
        f"- {agg['source_label']}",
        f"- decision: {agg['decision']} (same rule on compliant controls and "
        "violation variants; unobservable -> skipped; all-unobservable -> None)",
        "- old per-sample predictions preserved as `predicted_conditional_old` "
        "(labelled conditional detection for the preset type, NOT classification)",
        "- reproduce: `python formal_experiment/scripts/reevaluate_s3_extended_"
        "unified_v1.py --source "
        + source + "` (deterministic offline re-evaluation from persisted rows; "
        "per-method run dirs under outputs/development/s3_extended_unified_v1/"
        + source + "/)",
        "",
        "## Variant-only view (40 variants) — unified vs old-conditional",
        "",
        "| method | macro (old/new) | exact (old/new) | wrong-type (old/new) | detected (old/new) | unobservable (old/new) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method, info in agg["methods"].items():
        o = info["old_vs_new"]["variant_only"]
        lines.append(
            f"| {method} | {_fmt(o['macro_f1']['old_conditional'])} / "
            f"{_fmt(o['macro_f1']['new_unified'])} | "
            f"{_fmt(o['exact_type_accuracy']['old_conditional'])} / "
            f"{_fmt(o['exact_type_accuracy']['new_unified'])} | "
            f"{o['wrong_type']['old_conditional']} / {o['wrong_type']['new_unified']} | "
            f"{o['detected']['old_conditional']} / {o['detected']['new_unified']} | "
            f"{o['unobservable']['old_conditional']} / {o['unobservable']['new_unified']} |")
    lines += [
        "",
        "## Paired view (40 compliant controls + 40 variants)",
        "",
        "| method | 5-class acc (old/new) | variant exact (old/new) | control FP | paired acc (old/new) |",
        "|---|---:|---:|---:|---:|",
    ]
    for method, info in agg["methods"].items():
        o = info["old_vs_new"]["paired"]
        lines.append(
            f"| {method} | {_fmt(o['five_class_accuracy']['old_conditional'])} / "
            f"{_fmt(o['five_class_accuracy']['new_unified'])} | "
            f"{_fmt(o['variant_exact_type_accuracy']['old_conditional'])} / "
            f"{_fmt(o['variant_exact_type_accuracy']['new_unified'])} | "
            f"{_fmt(o['control_false_positive_rate'])} | "
            f"{_fmt(o['paired_accuracy']['old_conditional'])} / "
            f"{_fmt(o['paired_accuracy']['new_unified'])} |")
    lines += [
        "",
        "## Per-class P/R/F1 (5 classes, unified)",
        "",
        "| method | none | prohibited | condition | constraint | exception |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method, info in agg["methods"].items():
        pc = info["confusion_matrix"]["per_class"]
        cells = []
        for t in ("none",) + EXTENDED_TYPES:
            v = pc[t]
            cells.append(f"{_fmt(v['precision'])}/{_fmt(v['recall'])}/{_fmt(v['f1'])}")
        lines.append(f"| {method} | {' | '.join(cells)} |")
    lines += [
        "",
        "Predicted-None counts and variant unobservable reasons are in each "
        "method's `confusion_matrix.json`; per-sample unified predictions in "
        "`predictions.jsonl`.  Full JSON aggregate: "
        f"`outputs/reports/s3_extended_unified_v1_{source}.json`.",
        "",
        "## Boundaries",
        "",
        "- DEV_ONLY controlled synthetic panel; NOT human Gold; NOT the formal "
        "Oracle; never merged with the 33-item human Gold.",
        "- Old conditional numbers are kept for comparison only and must be "
        "labelled accordingly (no P=1/no-wrong-type classification claims).",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=sorted(SOURCES), required=True)
    parser.add_argument("--methods", default=",".join(METHOD_ORDER))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--report-root", type=Path, default=None)
    args = parser.parse_args()
    methods = tuple(m.strip() for m in args.methods.split(",") if m.strip())
    try:
        agg = run_source(args.source, methods, args.overwrite,
                         output_root=args.output_root, report_root=args.report_root)
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        print(f"unified re-evaluation refused: {exc}")
        return 2
    print(f"source={args.source} methods={len(agg['methods'])} "
          f"runtime_seconds={agg['runtime_seconds']:.1f} llm_api_calls=0")
    for method, info in agg["methods"].items():
        o = info["old_vs_new"]
        print(f"  {method}: variant macro {o['variant_only']['macro_f1']} "
              f"| paired 5-class {o['paired']['five_class_accuracy']} "
              f"| control FP {o['paired']['control_false_positive_rate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
