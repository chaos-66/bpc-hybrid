# -*- coding: utf-8 -*-
"""S3.9-EXT gap comparison table: six measured cells of the frozen 80-instance panel.

Read-only over the stored per-cell artefacts; writes the comparison artifact
(JSON + Markdown) under ``outputs/evidence/s3_extended_gap_v1/``.  The frozen
cells are referenced by path and sha256 and are never rewritten or re-derived
for the report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import run_s3_extended_violation_panel_v2 as panel_runner  # noqa: E402
from bpc_hybrid.s3_extended_arm_report import arm_metrics  # noqa: E402

TYPES = ("prohibited_action_present", "required_condition_not_enforced",
         "constraint_violated", "exception_not_handled")

OUT_DIR = ROOT / "outputs/evidence/s3_extended_gap_v1"
JSON_OUT = OUT_DIR / "comparison_v1.json"
MD_OUT = OUT_DIR / "comparison_v1.md"

FROZEN_REPORT = ROOT / "outputs/reports/s3_formula_repair_v2.json"

ARMS = (
    # key, kind, path, label, matching path, action gamma
    ("winter_frozen", "frozen_report_block",
     "outputs/reports/s3_formula_repair_v2.json", "Winter-style extension (frozen)",
     "original label argmax on raw label text", 0.4),
    ("sun_frozen", "frozen_report_block",
     "outputs/reports/s3_formula_repair_v2.json", "Sun-style extension (frozen)",
     "original label argmax on raw label text", 0.8),
    ("orig_04_rederived", "arm", "outputs/development/s3_extended_baseline_04_v1",
     "original path + 0.4 (re-derived)", "original label argmax on raw label text", 0.4),
    ("v3_08_existing", "arm", "outputs/development/s3_extended_v3_v1",
     "v3 matching path + 0.8 (existing)", "v3 structured action match", 0.8),
    ("v3_04_diagnostic", "arm", "outputs/development/s3_extended_v3_gamma04_v1",
     "v3 matching path + 0.4 (diagnostic)", "v3 structured action match", 0.4),
    ("v3_04_repaired", "arm", "outputs/development/s3_extended_v3_repair_v1",
     "v3 matching path + 0.4 repaired (final)", "v3 match + one action resolution", 0.4),
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def frozen_block(method: str) -> dict:
    report = read_json(FROZEN_REPORT)
    return report["extended_four_types"]["reference"][method]


def frozen_metrics(method: str) -> dict:
    """The frozen report's own numbers, reported exactly as stored.

    The frozen evaluator counts an explicitly compliant variant answer in the
    same ``unobservable`` field as an abstention, so the frozen block's
    ``abstained`` may include ``false_compliance``; the value is reported
    verbatim and the identity note says so.  The re-derived arms count the two
    apart.
    """
    block = frozen_block(method)
    ev = block["variant_evaluation"]
    pa = block["paired_evaluation"]
    total = pa["control_objects"]
    fp = len(pa["cases"]["control_false_positive"])
    abstained = pa["unobservable"]["control"]
    labels = ["none"] + list(TYPES)
    return {
        "A_variant_only_40": {
            "evaluation": ev,
            "partition": {
                "correct": ev["detected"], "wrong_type": ev["wrong_type"],
                "abstained": ev["unobservable"], "false_compliance": None,
                "objects": ev["support"],
                "identity": ("correct + wrong_type + abstained == objects in the frozen "
                             "evaluator's own fields; the frozen evaluator reports an "
                             "explicitly compliant variant prediction inside the "
                             "``unobservable`` field, so an exact "
                             "abstention/false-compliance split is not available from the "
                             "frozen table and the value is reported verbatim"),
            },
        },
        "B_control_40": {
            "objects": total, "explicitly_compliant": total - fp - abstained,
            "false_positives": fp, "abstained": abstained,
            "false_positive_rate": pa["control_false_positive_rate"],
        },
        "C_paired_40": {
            "pairs": pa["variant_objects"],
            "both_sides_correct": round(pa["paired_accuracy"] * pa["variant_objects"]),
            "paired_accuracy": pa["paired_accuracy"],
        },
        "D_merged_80": {
            "denominator": pa["total_objects"],
            "five_class_accuracy": pa["five_class_accuracy"],
            "macro_f1_four_violation_types": pa["macro_f1_four_violation_types"],
            "macro_f1_five_classes": pa["macro_f1_five_classes"],
            "per_class": {label: pa["per_type"][label] for label in labels},
        },
    }


def build() -> dict:
    panel = read_json(panel_runner.PANEL)
    gamma_ext = float(panel["config"]["gamma_ext"])
    gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}
    out_arms = {}
    for key, kind, path, label, matching, gamma in ARMS:
        if kind == "frozen_report_block":
            method = key.split("_")[0]
            metrics = frozen_metrics(method)
            source = {"path": FROZEN_REPORT.relative_to(ROOT).as_posix(),
                      "sha256": sha256_file(FROZEN_REPORT),
                      "block": f"extended_four_types.reference.{method}",
                      "read_only": True, "rerun": False}
            pred_path = (ROOT / "outputs/evidence/s3_formula_repair_v2/extended_four/"
                         "reference" / method / "predictions.jsonl")
        else:
            rows = read_jsonl(ROOT / path / "predictions.jsonl")
            metrics = arm_metrics(rows, panel, gold, gamma_ext)
            source = {"path": path, "sha256": sha256_file(ROOT / path / "predictions.jsonl"),
                      "manifest": f"{path}/manifest.json",
                      "manifest_sha256": sha256_file(ROOT / path / "manifest.json"),
                      "read_only": True, "rerun": False}
            pred_path = ROOT / path / "predictions.jsonl"
        ev = metrics["A_variant_only_40"]["evaluation"]
        out_arms[key] = {
            "label": label, "matching_path": matching, "action_gamma": gamma,
            "gamma_ext": gamma_ext, "source": source,
            "predictions_sha256": sha256_file(pred_path),
            "A_variant_only_40": {k: metrics["A_variant_only_40"][k] for k in
                                  ("evaluation", "partition")},
            "B_control_40": metrics["B_control_40"],
            "C_paired_40": metrics["C_paired_40"],
            "D_merged_80": metrics["D_merged_80"],
            "per_type_f1": {t: ev["per_type"][t]["f1"] for t in TYPES},
            "per_type_precision_recall": {
                t: {"precision": ev["per_type"][t]["precision"],
                    "recall": ev["per_type"][t]["recall"]} for t in TYPES},
        }
    return {
        "schema_version": "s3_extended_gap_comparison@1.0.0",
        "scope": ("development_only synthetic four-type panel v2 (40 controlled variants + "
                  "40 synthetic compliant controls); NOT human Gold; NOT the formal Oracle; "
                  "zero API"),
        "panel": {"path": panel_runner.PANEL.relative_to(ROOT).as_posix(),
                  "sha256": sha256_file(panel_runner.PANEL),
                  "variants": len(panel["variants"]),
                  "controls": len(panel["variants"]),
                  "gamma_ext": gamma_ext},
        "arms": out_arms,
        "notes": [
            "every arm is reported on the same 40 variants / 40 controls / 80 objects; "
            "no sample is dropped",
            "a control abstention is NOT counted as a correct rejection",
            "the frozen Winter-style and Sun-style blocks are read from the frozen report "
            "and never re-run",
            "the original path + 0.4 cell is re-derived in the current code state and "
            "reproduces the frozen Winter-style arm on every decision-relevant field",
            "the two v3 cells at 0.8 and 0.4 hold identical predictions; they differ only "
            "in the recorded action gamma",
            "the D view is not the A view: it mixes 40 violation objects with 40 compliant "
            "objects",
        ],
    }


def render_md(data: dict) -> str:
    arms = data["arms"]
    order = [k for k, *_ in ARMS]
    lines = [
        "# S3.9-EXT gap comparison v1 (development-only, frozen 80-instance panel)",
        "",
        f"Panel: `{data['panel']['path']}` "
        f"({data['panel']['variants']} variants + {data['panel']['controls']} controls), "
        f"`gamma_ext = {data['panel']['gamma_ext']}`. Zero API. Not human Gold, not the "
        "formal Oracle.",
        "",
        "## A. 40 mutated variants",
        "",
        "| arm | matching path | action gamma | correct | wrong type | abstained | "
        "explicitly compliant | 4-type macro-F1 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for key in order:
        a = arms[key]
        p = a["A_variant_only_40"]["partition"]
        lines.append(
            f"| {a['label']} | {a['matching_path']} | {a['action_gamma']} | {p['correct']} | "
            f"{p['wrong_type']} | {p['abstained']}"
            + ("*" if p["false_compliance"] is None else "")
            + f" | "
            f"{'n/a*' if p['false_compliance'] is None else p['false_compliance']} | "
            f"{a['A_variant_only_40']['evaluation']['macro_f1']:.4f} |")
    lines += ["",
              "`*` the frozen Winter-style and Sun-style blocks are reported verbatim from "
              "the frozen report; the frozen evaluator counts an explicitly compliant "
              "variant prediction inside its `unobservable` field, so those two rows have "
              "no separate false-compliance column. The re-derived and new arms split "
              "abstention from explicit compliance."]
    lines += ["", "### Per-type P/R/F1 (variants)", "",
              "| arm | prohibited | condition | constraint | exception |",
              "|---|---|---|---|---|"]
    for key in order:
        a = arms[key]
        cells = []
        for t in TYPES:
            pr = a["per_type_precision_recall"][t]
            cells.append(f"{pr['precision']:.3f}/{pr['recall']:.3f}/{a['per_type_f1'][t]:.3f}")
        lines.append(f"| {a['label']} | " + " | ".join(cells) + " |")
    lines += ["", "## B. 40 compliant controls", "",
              "| arm | false positives | explicitly compliant | abstained | FP rate |",
              "|---|---|---|---|---|"]
    for key in order:
        b = arms[key]["B_control_40"]
        lines.append(f"| {arms[key]['label']} | {b['false_positives']} | "
                     f"{b['explicitly_compliant']} | {b['abstained']} | "
                     f"{b['false_positive_rate']:.4f} |")
    lines += ["", "## C. 40 pairs", "",
              "| arm | both sides correct | paired accuracy |", "|---|---|---|"]
    for key in order:
        c = arms[key]["C_paired_40"]
        lines.append(f"| {arms[key]['label']} | {c['both_sides_correct']} | "
                     f"{c['paired_accuracy']:.4f} |")
    lines += ["", "## D. merged 80 objects (five classes, reported separately)", "",
              "| arm | 5-class accuracy | 4-type macro-F1 | 5-class macro-F1 |",
              "|---|---|---|---|"]
    for key in order:
        d = arms[key]["D_merged_80"]
        lines.append(f"| {arms[key]['label']} | {d['five_class_accuracy']:.4f} | "
                     f"{d['macro_f1_four_violation_types']:.4f} | "
                     f"{d['macro_f1_five_classes']:.4f} |")
    lines += ["", "## Count identities", ""]
    for key in order:
        a = arms[key]
        p = a["A_variant_only_40"]["partition"]
        b = a["B_control_40"]
        lines.append(f"- **{a['label']}**: variants {p['correct']} + {p['wrong_type']} + "
                     f"{p['abstained']}"
                     + (f" + {p['false_compliance']}" if p["false_compliance"] is not None
                        else " (incl. explicit compliance)")
                     + f" = {p['objects']}; controls {b['explicitly_compliant']} + "
                     f"{b['false_positives']} + {b['abstained']} = {b['objects']}.")
    lines += ["", "## Sources", ""]
    for key in order:
        a = arms[key]
        lines.append(f"- `{key}`: `{a['source']['path']}` "
                     f"`{a['predictions_sha256'][:16]}`")
    lines.append("")
    for note in data["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = build()
    if args.check:
        stored = read_json(JSON_OUT)
        if stored != data:
            raise RuntimeError("the stored comparison is not reproducible from the cells")
        md = render_md(data)
        if MD_OUT.read_text(encoding="utf-8") != md:
            raise RuntimeError("the stored comparison markdown is not reproducible")
        print("s3_extended_gap_v1 comparison VERIFIED")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    MD_OUT.write_text(render_md(data), encoding="utf-8", newline="\n")
    for key, arm in data["arms"].items():
        p = arm["A_variant_only_40"]["partition"]
        b = arm["B_control_40"]
        print(f"{key:20s} macro={arm['A_variant_only_40']['evaluation']['macro_f1']:.4f} "
              f"correct={p['correct']:2d} wrong={p['wrong_type']:2d} abst={p['abstained']:2d} "
              f"| ctrlFP={b['false_positives']:2d} compliant={b['explicitly_compliant']:2d} "
              f"abst={b['abstained']:2d} | paired={arm['C_paired_40']['both_sides_correct']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
