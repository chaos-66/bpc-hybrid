# -*- coding: utf-8 -*-
"""Build the THREE cross-method result tables for the Barrientos D/E run.

The user contract (2026-08-26) forbids comparing F1 numbers from different
evaluators.  This builder therefore emits three SEPARATE tables:

* Table A — Barrientos-native (BARR-FULL):
    precondition/norm pooled P/R/F1, strict JSON validity, output coverage,
    failure rate and five-run pairwise distance<=2 self-consistency — all
    computed with the Barrientos artifact evaluator semantics only.
* Table B — Ours-native (OURS-FULL vs OURS-BARRIENTOS-MODULE):
    the SAME six-field Gold and the SAME evaluator for both arms; per-field
    and overall P/R/F1, valid rate, failure rate; five-run mean/SD/min/max
    and per-field delta (module-swap effect).  This is the core
    "is replacing the prompt module with Barrientos-style better?" ablation.
* Table C — Shared-target (BARR-FULL vs OURS-FULL vs
    OURS-BARRIENTOS-MODULE):
    deterministic adapters (barrientos_de_shared_target) to a pre-defined
    shared target (3-class modality; adapter-defined norm count/type) with
    the SAME gold and SAME metric function; fields that cannot be mapped
    (actor/action/definition/precondition) are marked
    not_expressible/not_strictly_alignable and are NEVER hard-computed as 0;
    NO overall F1 is synthesized across schemas.

Inputs: outputs/development/barrientos_ablation_suite_v2/<arm>/<repeat>/
        {evaluation.json, canonical_predictions.jsonl, manifest.json}
        + outputs/development/barrientos_ablation_suite_v2/execution_summary.json
Outputs: outputs/reports/barrientos_de_tables_v1.json / .md
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

OUT_DIR = ROOT / "outputs/development/barrientos_ablation_suite_v2"
REPORT_JSON = ROOT / "outputs/reports/barrientos_de_tables_v1.json"
REPORT_MD = ROOT / "outputs/reports/barrientos_de_tables_v1.md"

BARR_ARMS = ("BARR-FULL",)
OURS_ARMS = ("OURS-FULL", "OURS-BARRIENTOS-MODULE")
ALL_ARMS = BARR_ARMS + OURS_ARMS
REPEATS = (f"repeat-{i:02d}" for i in range(1, 6))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _summary(run_dir: Path) -> dict[str, Any]:
    """execution_summary.json (real run) or fixture_summary.json (fake)."""
    for name in ("execution_summary.json", "fixture_summary.json"):
        path = run_dir / name
        if path.is_file():
            return _load_json(path)
    raise RuntimeError(f"no execution/fixture summary in {run_dir}")


def _mean_std(vals: Sequence[float]) -> tuple[float, float]:
    if not vals:
        return float("nan"), float("nan")
    mean = sum(vals) / len(vals)
    std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
    return mean, std


def _round3(v: float) -> float:
    return round(v, 3)


# ---------------------------------------------------------------------------
# Table A: Barrientos-native
# ---------------------------------------------------------------------------


def table_a(run_dir: Path) -> dict[str, Any]:
    """BARR-FULL five-repeat Barrientos-native metrics."""
    rows: list[dict[str, Any]] = []
    for repeat in REPEATS:
        ev = _load_json(run_dir / "BARR-FULL" / repeat / "evaluation.json")
        e = ev["evaluation"]
        rows.append({
            "repeat_id": repeat,
            "precondition_p": e["precondition"]["precision"],
            "precondition_r": e["precondition"]["recall"],
            "precondition_f1": e["precondition"]["f1"],
            "norm_p": e["norm"]["precision"],
            "norm_r": e["norm"]["recall"],
            "norm_f1": e["norm"]["f1"],
            "strict_json_validity": e["strict_json_validity"],
            "output_coverage": e["output_coverage"],
            "failure_rate": e["failed_count"] / e["denominator"]
            if e["denominator"] else None,
        })
    summary = _summary(run_dir)
    stability = (summary.get("stability") or {}).get("BARR-FULL") or {}
    le2 = stability.get("pairwise_distance_le2_ratio")
    le2_detail = stability.get("pairwise_le2_detail") or {}

    def agg(key: str):
        vals = [r[key] for r in rows if r[key] is not None]
        mean, std = _mean_std(vals)
        return {"mean": _round3(mean), "sd": _round3(std),
                "min": _round3(min(vals)) if vals else None,
                "max": _round3(max(vals)) if vals else None}

    return {
        "table": "A",
        "title": "Barrientos-native (BARR-FULL, 36 requirements x 5 runs)",
        "evaluator": "barrientos_step1_artifact_evaluator",
        "note": ("pooled precondition/norm P/R/F1 vs step_1_baseline.json "
                 "(automated proxy of the paper's pooled TP/FP/FN; the paper "
                 "used expert annotation), strict JSON/schema validity, "
                 "output coverage, failure rate, and the paper's pairwise "
                 "distance<=2 self-consistency. F1 here is Barrientos-native "
                 "and MUST NOT be compared with Table B's six-field F1."),
        "per_repeat": rows,
        "aggregate": {k: agg(k) for k in (
            "precondition_p", "precondition_r", "precondition_f1",
            "norm_p", "norm_r", "norm_f1", "strict_json_validity",
            "output_coverage", "failure_rate")},
        "self_consistency": {
            "paper_distance_le2_ratio": le2,
            "pairwise_comparisons": le2_detail.get("pairwise_comparisons"),
            "per_requirement_mean_ratio": le2_detail.get(
                "per_requirement_mean_ratio"),
            "per_requirement_std_ratio": le2_detail.get(
                "per_requirement_std_ratio"),
            "definition": ("same-arm five-run output consistency on the same "
                           "36 inputs; NOT a cross-method accuracy metric"),
        },
    }


# ---------------------------------------------------------------------------
# Table B: Ours-native (same gold, same evaluator, both arms)
# ---------------------------------------------------------------------------


def _ours_row(arm: str, repeat: str, run_dir: Path) -> dict[str, Any]:
    ev = _load_json(run_dir / arm / repeat / "evaluation.json")
    e = ev["evaluation"]
    metrics = e["metrics"]
    overall = metrics["overall"] or {}
    span = overall.get("span_fields") or {}
    per_field = span.get("span_fields") or {}
    modality = overall.get("modality_labels") or {}
    denominator = e["denominator"]
    failed = e["failed_count"]
    row: dict[str, Any] = {
        "repeat_id": repeat,
        "valid_rate": round((denominator - failed) / denominator, 6)
        if denominator else None,
        "failure_rate": round(failed / denominator, 6) if denominator else None,
        "modality_label_accuracy": modality.get("accuracy"),
        "modality_label_macro_f1": modality.get("macro_f1"),
    }
    for field in ("actor", "action", "condition", "constraint", "exception"):
        f = per_field.get(field) or {}
        row[f"{field}_p"] = f.get("precision")
        row[f"{field}_r"] = f.get("recall")
        row[f"{field}_f1"] = f.get("f1")
    ov = span.get("overall") or {}
    row["overall_p"] = ov.get("precision")
    row["overall_r"] = ov.get("recall")
    row["overall_f1"] = ov.get("f1")
    return row


def table_b(run_dir: Path) -> dict[str, Any]:
    """OURS-FULL vs OURS-BARRIENTOS-MODULE — same evaluator, same gold."""
    metrics = ("actor_p", "actor_r", "actor_f1", "action_p", "action_r",
               "action_f1", "condition_p", "condition_r", "condition_f1",
               "constraint_p", "constraint_r", "constraint_f1",
               "exception_p", "exception_r", "exception_f1",
               "overall_p", "overall_r", "overall_f1",
               "valid_rate", "failure_rate",
               "modality_label_accuracy", "modality_label_macro_f1")
    arms: dict[str, Any] = {}
    for arm in OURS_ARMS:
        rows = [_ours_row(arm, rep, run_dir) for rep in REPEATS]
        agg: dict[str, Any] = {}
        for k in metrics:
            vals = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
            if not vals:
                agg[k] = None
                continue
            mean, std = _mean_std(vals)
            agg[k] = {"mean": _round3(mean), "sd": _round3(std),
                      "min": _round3(min(vals)), "max": _round3(max(vals))}
        arms[arm] = {"per_repeat": rows, "aggregate": agg}
    # per-field delta: OURS-BARRIENTOS-MODULE minus OURS-FULL (mean F1)
    delta: dict[str, Any] = {}
    for k in metrics:
        m_full = arms["OURS-FULL"]["aggregate"].get(k)
        m_swap = arms["OURS-BARRIENTOS-MODULE"]["aggregate"].get(k)
        if m_full and m_swap and m_full.get("mean") is not None \
                and m_swap.get("mean") is not None:
            delta[k] = _round3(m_swap["mean"] - m_full["mean"])
    return {
        "table": "B",
        "title": ("Ours-native (OURS-FULL vs OURS-BARRIENTOS-MODULE, "
                  "36 requirements x 5 runs; same six-field Gold, same "
                  "evaluator)"),
        "evaluator": "s2_12_stratified_evaluator_v2",
        "note": ("both arms scored with the SAME evaluator on the SAME "
                 "S2.11 six-field Gold; per-field and overall literal-"
                 "overlap P/R/F1; modality label accuracy/macro-F1; "
                 "five-run mean/SD/min/max; delta = module-swapped minus "
                 "full. This is the core module-replacement ablation. F1 "
                 "here is Ours-native and MUST NOT be compared with Table "
                 "A's Barrientos-native F1."),
        "arms": arms,
        "delta_swap_minus_full": delta,
    }


# ---------------------------------------------------------------------------
# Table C: Shared-target (deterministic adapters, same gold, same metric)
# ---------------------------------------------------------------------------


def table_c(run_dir: Path) -> dict[str, Any]:
    from bpc_hybrid.barrientos_de_shared_target import (
        barr_first_modality,
        ours_first_modality,
        shared_modality_report,
        norm_count_type_report,
        NOT_STRICTLY_ALIGNABLE,
    )

    # gold records from the frozen S2.11 gold (same gold for every arm)
    from run_barrientos_ablation_suite_v2 import _s211_gold_records
    gold = _s211_gold_records()
    gold_by_id = {g["sample_id"]: g for g in gold}
    sample_ids = sorted(gold_by_id)

    # baseline gold per sample (version-aware) for norm count/type
    baseline = _load_json(
        ROOT.parent / "references/barrientos_2026/evaluation/ground_truth"
        / "step_1_baseline.json")
    gold_by_base = {b["id"]: b for b in baseline}

    def baseline_for(sample_id: str) -> dict[str, Any] | None:
        rid = sample_id.split("/")[1] if "/" in sample_id else sample_id
        rid = rid[:-2] if rid.endswith(("v1", "v2")) else rid
        entry = gold_by_base.get(rid)
        if entry is None:
            return None
        if entry.get("both_versions") is True \
                or not isinstance(entry.get("versions"), dict):
            return entry
        version = sample_id.split("/")[2] if "/" in sample_id else ""
        key = {"v1": "version_1", "v2": "version_2"}.get(version)
        node = (entry.get("versions") or {}).get(key) if key else None
        return node if isinstance(node, dict) else entry

    # per-arm per-repeat predictions from canonical_predictions.jsonl
    arm_preds: dict[str, dict[str, Any]] = {}
    arm_trees: dict[str, dict[str, Any]] = {}
    for arm in ALL_ARMS:
        preds_by_repeat: dict[str, list[str | None]] = {}
        trees_by_repeat: dict[str, dict[str, Any]] = {}
        for rep in REPEATS:
            preds: dict[str, str | None] = {}
            trees: dict[str, Any] = {}
            path = run_dir / arm / rep / "canonical_predictions.jsonl"
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                sid = row.get("sample_id")
                if sid not in gold_by_id:
                    continue
                if row.get("request_status") != "ok":
                    preds[sid] = None
                    trees[sid] = None
                    continue
                if row.get("barrientos_record") is not None:
                    tree = (row.get("barrientos_record") or {}).get("record")
                    preds[sid] = barr_first_modality(tree)
                    trees[sid] = tree
                else:
                    rec = row.get("record") or {}
                    preds[sid] = ours_first_modality(rec)
                    trees[sid] = rec
            preds_by_repeat[rep] = [preds.get(s) for s in sample_ids]
            trees_by_repeat[rep] = {s: trees.get(s) for s in sample_ids}
        arm_preds[arm] = preds_by_repeat
        arm_trees[arm] = trees_by_repeat

    # shared modality P/R/F1 per repeat (same gold for all arms)
    modality_repeats: dict[str, dict[str, Any]] = {}
    for rep in REPEATS:
        modality_repeats[rep] = shared_modality_report(
            [gold_by_id[s] for s in sample_ids],
            {arm: arm_preds[arm][rep] for arm in ALL_ARMS})

    # aggregate per arm per class across repeats
    arms_agg: dict[str, Any] = {}
    for arm in ALL_ARMS:
        per_class_agg: dict[str, Any] = {}
        for cls in ("obligation", "permission", "prohibition"):
            vals_p = [modality_repeats[r]["arms"][arm]["per_class"][cls]["precision"]
                      for r in REPEATS]
            vals_r = [modality_repeats[r]["arms"][arm]["per_class"][cls]["recall"]
                      for r in REPEATS]
            vals_f = [modality_repeats[r]["arms"][arm]["per_class"][cls]["f1"]
                      for r in REPEATS]
            per_class_agg[cls] = {
                "precision": {"mean": _round3(_mean_std(vals_p)[0]),
                              "sd": _round3(_mean_std(vals_p)[1])},
                "recall": {"mean": _round3(_mean_std(vals_r)[0]),
                           "sd": _round3(_mean_std(vals_r)[1])},
                "f1": {"mean": _round3(_mean_std(vals_f)[0]),
                       "sd": _round3(_mean_std(vals_f)[1])},
            }
        macro_f1_vals = [modality_repeats[r]["arms"][arm]["macro"]["f1"]
                         for r in REPEATS]
        arms_agg[arm] = {
            "per_class": per_class_agg,
            "macro_f1": {"mean": _round3(_mean_std(macro_f1_vals)[0]),
                         "sd": _round3(_mean_std(macro_f1_vals)[1])},
        }

    # adapter-defined norm count/type (secondary; never merged)
    norm_repeats: dict[str, Any] = {}
    for rep in REPEATS:
        norm_repeats[rep] = norm_count_type_report(
            {s: baseline_for(s) or {} for s in sample_ids},
            {arm: arm_trees[arm][rep] for arm in ALL_ARMS},
            sample_ids)

    return {
        "table": "C",
        "title": ("Shared-target (deterministic adapters; same Gold; same "
                  "metric function per target)"),
        "adapters": {
            "modality": ("Barrientos: first norms[].modality; Ours: first "
                         "clauses[].modality.label projected to the shared "
                         "3 classes; gold: first clause label of the frozen "
                         "S2.11 gold; definition-gold samples excluded and "
                         "reported"),
            "norm_count_type": ("adapter-defined (disclosed): Barrientos "
                                "len(norms)/first modality; Ours count of "
                                "3-class-modal clauses/first label"),
        },
        "not_expressible": {
            "actor_action_exception": {
                "status": "not_expressible_in_barrientos_schema",
                "reason": "the Barrientos Step-1 schema has no actor/action/"
                          "exception fields at the same semantic level; "
                          "never hard-computed as 0"},
            "definition": {
                "status": "not_expressible_in_barrientos_schema",
                "reason": "3-class Barrientos modality cannot express "
                          "definition; excluded from shared modality "
                          "denominator, never counted as 0"},
            "precondition": {
                "status": NOT_STRICTLY_ALIGNABLE,
                "reason": "Barrientos precondition is an AND/OR/NOT action "
                          "list; Ours condition is a span-based field"},
        },
        "no_overall_f1_synthesized_across_schemas": True,
        "modality": {"per_repeat": modality_repeats, "arms": arms_agg},
        "norm_count_type": {
            "per_repeat": norm_repeats,
            "note": "adapter-defined secondary metric; reported separately",
        },
    }


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build_tables(run_dir: Path | None = None) -> dict[str, Any]:
    if run_dir is None:
        run_dir = OUT_DIR
    summary = _summary(run_dir)  # existence check (execution or fixture summary)
    if (run_dir / "execution_summary.json").is_file():
        # a REAL run must be complete before tables are produced
        if summary.get("aborted"):
            raise RuntimeError(
                "execution was ABORTED; tables are refused for aborted runs")
        if summary.get("complete") is False:
            raise RuntimeError(
                "execution is INCOMPLETE; tables are refused until all "
                "planned calls and artifacts are present")
        accounted = summary.get("total_calls_accounted",
                                summary.get("completed_samples"))
        if accounted != summary.get("planned_calls"):
            raise RuntimeError(
                f"execution incomplete: calls accounted {accounted} != "
                f"planned {summary.get('planned_calls')}; tables refused")
    missing = [a for a in ALL_ARMS
               if not (run_dir / a / "repeat-01" / "evaluation.json").is_file()]
    if missing:
        raise RuntimeError(f"missing arm evaluations: {missing}")
    return {
        "schema_version": "barrientos_de_tables@1.0.0",
        "tables": {
            "A_barrientos_native": table_a(run_dir),
            "B_ours_native": table_b(run_dir),
            "C_shared_target": table_c(run_dir),
        },
        "comparability_rule": (
            "Table A F1 (Barrientos-native) and Table B F1 (Ours-native) "
            "use different schemas/evaluators and MUST NOT be compared "
            "directly. Only Table C (same Gold, same metric function via "
            "deterministic adapters) is a legitimate cross-method "
            "comparison, and only on the pre-defined shared targets."),
    }


def _md(tables: dict[str, Any]) -> str:
    lines = ["# Barrientos D/E Result Tables v1 (three-table separation)", ""]
    t = tables["tables"]
    lines += ["## Table A — Barrientos-native (BARR-FULL)", "",
              "| repeat | pre P | pre R | pre F1 | norm P | norm R | norm F1 "
              "| validity | coverage | fail% |"]
    for r in t["A_barrientos_native"]["per_repeat"]:
        lines.append("| {} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | "
                     "{:.3f} | {:.3f} | {:.3f} | {:.3f} |".format(
                         r["repeat_id"], r["precondition_p"], r["precondition_r"],
                         r["precondition_f1"], r["norm_p"], r["norm_r"],
                         r["norm_f1"], r["strict_json_validity"],
                         r["output_coverage"], r["failure_rate"] or 0.0))
    sc = t["A_barrientos_native"]["self_consistency"]
    lines += ["", "self-consistency (paper distance<=2): {:.4f} "
              "(pairwise={})".format(
                  sc["paper_distance_le2_ratio"] or 0.0,
                  sc["pairwise_comparisons"]), ""]
    lines += ["## Table B — Ours-native (OURS-FULL vs OURS-BARRIENTOS-MODULE)",
              "", "| metric | OURS-FULL mean | OURS-FULL SD | swap mean | "
              "swap SD | delta |"]
    b = t["B_ours_native"]
    for k in ("overall_f1", "overall_p", "overall_r",
              "actor_f1", "action_f1", "condition_f1", "constraint_f1",
              "exception_f1", "valid_rate", "failure_rate",
              "modality_label_macro_f1"):
        mf = b["arms"]["OURS-FULL"]["aggregate"].get(k)
        ms = b["arms"]["OURS-BARRIENTOS-MODULE"]["aggregate"].get(k)
        delta = b["delta_swap_minus_full"].get(k)
        if not mf or not ms:
            continue
        lines.append("| {} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {} |".format(
            k, mf["mean"], mf["sd"], ms["mean"], ms["sd"],
            "{:+.3f}".format(delta) if delta is not None else "-"))
    c = t["C_shared_target"]
    lines += ["", "## Table C — Shared-target (same Gold, same metric)", "",
              "| arm | ob F1 | per F1 | pro F1 | macro F1 |"]
    for arm, agg in c["modality"]["arms"].items():
        lines.append("| {} | {:.3f} | {:.3f} | {:.3f} | {:.3f} |".format(
            arm,
            agg["per_class"]["obligation"]["f1"]["mean"],
            agg["per_class"]["permission"]["f1"]["mean"],
            agg["per_class"]["prohibition"]["f1"]["mean"],
            agg["macro_f1"]["mean"]))
    lines += ["", "not expressible: " + ", ".join(
        f"{k}={v['status']}" for k, v in c["not_expressible"].items()), ""]
    lines += ["---", "", "**" + tables["comparability_rule"] + "**", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=None,
                        help="execution output dir (default: the suite v2 "
                             "output dir)")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        if REPORT_JSON.exists() and not args.overwrite:
            raise RuntimeError(f"refusing to overwrite: {REPORT_JSON}")
        tables = build_tables(args.run_dir)
        REPORT_JSON.write_text(
            json.dumps(tables, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        REPORT_MD.write_text(_md(tables) + "\n", encoding="utf-8")
        print(f"tables written: {REPORT_JSON.relative_to(ROOT)} / "
              f"{REPORT_MD.relative_to(ROOT)}")
        return 0
    except (RuntimeError, FileNotFoundError, KeyError) as exc:
        print(f"refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
