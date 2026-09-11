# -*- coding: utf-8 -*-
"""S3.9-EXT gap analysis, control cell 1: the ORIGINAL label-argmax matching path
with the Winter action threshold gamma=0.4, on the frozen 80-instance panel.

Purpose
-------
The frozen evidence set already holds two cells of the same panel:

* original matching path + gamma 0.4   -> the stored Winter-style arm;
* original matching path + gamma 0.8   -> the stored Sun-style arm;
* v3 matching path       + gamma 0.8   -> ``outputs/development/s3_extended_v3_v1``.

The Winter-style arm is *also* the original path at gamma 0.4, but it is a
frozen published arm bound by the ``s3_formula_repair_v2`` manifest.  This
runner re-derives the SAME cell inside the CURRENT code state so that the three
cells and the new diagnostic arm are all measured by one runner, one evaluator
and one metric module.  It never rewrites a frozen artifact.

Self-check: scoring the panel with gamma 0.8 must reproduce the stored Sun-style
predictions byte for byte on every decision-relevant field.  If it does not, the
run aborts before writing anything.

Zero API, zero LLM.  Predictions are written before any label is read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import run_s3_extended_violation_panel_v2 as panel_runner  # noqa: E402
from bpc_hybrid.s3_extended_arm_report import arm_metrics, per_item_evidence  # noqa: E402
from bpc_hybrid.s3_extended_unified import unified_rows  # noqa: E402
from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES  # noqa: E402

RUN_ID = "s3_extended_baseline_04_v1"
METHOD_ID = "original_label_argmax_gamma_0_4"
METHOD_DISPLAY = "Original label-argmax matching path with the inherited Winter action gamma 0.4"
ACTION_GAMMA = 0.4
SELFCHECK_GAMMA = 0.8
FROZEN_SUN = (ROOT / "outputs/evidence/s3_formula_repair_v2/extended_four/"
              "reference/sun/predictions.jsonl")

OUT_DIR = ROOT / "outputs/development" / RUN_ID
PREDICTIONS_FILE = OUT_DIR / "predictions.jsonl"
METRICS_FILE = OUT_DIR / "metrics.json"
DIAGNOSTICS_FILE = OUT_DIR / "diagnostics.json"
MANIFEST_FILE = OUT_DIR / "manifest.json"
OUT_FILES = ("predictions.jsonl", "metrics.json", "diagnostics.json", "manifest.json")

_DECISION_FIELDS = ("scores", "observability", "control_scores", "unified_predicted_raw")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                            for r in rows), encoding="utf-8", newline="\n")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def frozen_paths() -> list[Path]:
    paths = [
        panel_runner.PANEL, panel_runner.EXTENSION_CONFIG, panel_runner.INFERENCE_PACK,
        panel_runner.STRUCTURAL_CONTRACT, panel_runner.WINTER_CONFIG,
        panel_runner.SUN_CONFIG,
        ROOT / "src/bpc_hybrid/stage3_extended_violations.py",
        ROOT / "src/bpc_hybrid/s3_extended_unified.py",
        ROOT / "src/bpc_hybrid/s3_extended_arm_report.py",
        ROOT / "src/bpc_hybrid/winter_stage3/winter_similarity.py",
        ROOT / "src/bpc_hybrid/sun_stage3/sun_model.py",
        FROZEN_SUN,
    ]
    paths += sorted((ROOT / "data/input/stage1_stage3/gdpr7").glob("*.bpmn"))
    for variant in read_json(panel_runner.PANEL)["variants"]:
        for side in ("control", "variant"):
            paths.append(ROOT / variant[f"{side}_bpmn"])
    return paths


def score_panel(gamma: float, nlp) -> list[dict]:
    """The original label-argmax path with the Winter backend and an explicit gamma.

    Identical to the frozen panel runner's ``winter`` cell (same panel, same rule
    texts, same ``WinterSimilarity.text_pair`` backend, same formulas, same
    frozen ``gamma_ext``, same candidates); only the action-mapping gamma differs.
    """
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity

    panel = read_json(panel_runner.PANEL)
    rule_texts = panel_runner._rule_texts()
    sim = WinterSimilarity(nlp)
    sims_factory = lambda record, xml_root: {"action": sim.text_pair,  # noqa: E731
                                             "text": sim.text_pair}
    gamma_ext = float(panel["config"]["gamma_ext"])
    return panel_runner.build_predictions("winter", panel, rule_texts, sims_factory,
                                          gamma, gamma_ext, nlp)


def selfcheck_original_path(nlp) -> dict:
    """The same runner + the same path at gamma 0.8 must reproduce the frozen arm."""
    rows = unified_rows(score_panel(SELFCHECK_GAMMA, nlp),
                        float(read_json(panel_runner.PANEL)["config"]["gamma_ext"]))
    frozen = {r["item_id"]: r for r in read_jsonl(FROZEN_SUN)}
    mismatches = []
    if set(frozen) != {r["item_id"] for r in rows}:
        mismatches.append("item_id membership")
    for row in rows:
        other = frozen.get(row["item_id"])
        if other is None:
            continue
        for field in _DECISION_FIELDS:
            if row.get(field) != other.get(field):
                mismatches.append(f"{row['item_id']}:{field}")
    if mismatches:
        raise RuntimeError(
            "the original matching path at gamma 0.8 no longer reproduces the stored "
            "Sun-style arm; refusing to run: " + ", ".join(sorted(set(mismatches))[:10]))
    return {"reproduced_items": len(rows), "fields": list(_DECISION_FIELDS)}


def build_all() -> dict:
    import spacy
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    panel = read_json(panel_runner.PANEL)
    gamma_ext = float(panel["config"]["gamma_ext"])
    nlp = spacy.load("en_core_web_sm")

    check = selfcheck_original_path(nlp)

    rows = unified_rows(score_panel(ACTION_GAMMA, nlp), gamma_ext)
    rows = [dict(r, arm=RUN_ID, method_id=METHOD_ID) for r in rows]
    # phase boundary: the decision is fixed on disk before any label is read
    write_rows(PREDICTIONS_FILE, rows)

    gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}
    rule_texts = panel_runner._rule_texts()
    metrics = arm_metrics(rows, panel, gold, gamma_ext)
    metrics.update({
        "run_id": RUN_ID, "method_id": METHOD_ID, "method_display_name": METHOD_DISPLAY,
        "generated_utc": started, "scope": "development_only",
        "arm": {"action_matching_path": "original_label_argmax",
                "action_gamma": ACTION_GAMMA, "gamma_ext": gamma_ext,
                "selfcheck_gamma_0_8_reproduces_frozen_sun": check},
    })
    diagnostics = {
        "schema_version": "s3_extended_arm_diagnostics@1.0.0",
        "run_id": RUN_ID,
        "action_matching_path": "original_label_argmax",
        "action_gamma": ACTION_GAMMA,
        "gamma_ext": gamma_ext,
        "instances": [per_item_evidence(r, gold, rule_texts) for r in rows],
    }
    write_json(METRICS_FILE, metrics)
    write_json(DIAGNOSTICS_FILE, diagnostics)
    return {"rows": rows, "metrics": metrics, "diagnostics": diagnostics,
            "panel": panel, "runtime_seconds": round(time.time() - t0, 3),
            "started_utc": started, "selfcheck": check}


def verify_outputs() -> dict:
    manifest = read_json(MANIFEST_FILE)
    mismatched = [f"{sec}:{rel}" for sec in ("inputs", "implementation")
                  for rel, digest in manifest[sec].items()
                  if sha256_file(ROOT / rel) != digest]
    mismatched += [f"results:{k}" for k, e in manifest["results"].items()
                   if sha256_file(ROOT / e["path"]) != e["sha256"]]
    if mismatched:
        raise RuntimeError("hash mismatch: " + ", ".join(sorted(set(mismatched))))
    if sorted(p.name for p in OUT_DIR.iterdir()) != sorted(OUT_FILES):
        raise RuntimeError("the run directory must hold exactly its four files")
    rows = read_jsonl(PREDICTIONS_FILE)
    if len(rows) != 40:
        raise RuntimeError("expected 40 panel rows (80 evaluation objects)")
    panel = read_json(panel_runner.PANEL)
    gamma_ext = float(panel["config"]["gamma_ext"])
    gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}
    metrics = read_json(METRICS_FILE)
    recomputed = arm_metrics(rows, panel, gold, gamma_ext)
    for key in ("A_variant_only_40", "B_control_40", "C_paired_40", "D_merged_80"):
        if recomputed[key] != metrics[key]:
            raise RuntimeError(f"view {key} is not reproducible from the stored rows")
    return {"rows": rows, "metrics": metrics, "manifest": manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        verify_outputs()
        print(f"{RUN_ID} VERIFIED")
        return 0
    if OUT_DIR.exists() and any(OUT_DIR.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing run directory: {OUT_DIR}")
    paths = frozen_paths()
    before = {str(p.relative_to(ROOT)): sha256_file(p) for p in paths}
    built = build_all()
    after = {str(p.relative_to(ROOT)): sha256_file(p) for p in paths}
    if before != after:
        raise RuntimeError("a frozen input or implementation file changed during the run")
    manifest = {
        "schema_version": "s3_extended_arm_manifest@1.0.0",
        "run_id": RUN_ID,
        "method_id": METHOD_ID,
        "started_utc": built["started_utc"],
        "runtime_seconds": built["runtime_seconds"],
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                              text=True).strip(),
        "command": f"python {Path(__file__).relative_to(ROOT)}",
        "arm": built["metrics"]["arm"],
        "inputs": before,
        "implementation": {
            str(Path(__file__).relative_to(ROOT)): sha256_file(Path(__file__)),
            "src/bpc_hybrid/s3_extended_arm_report.py":
                sha256_file(ROOT / "src/bpc_hybrid/s3_extended_arm_report.py"),
        },
        "results": {
            "predictions": {"path": PREDICTIONS_FILE.relative_to(ROOT).as_posix(),
                            "sha256": sha256_file(PREDICTIONS_FILE), "rows": len(built["rows"]),
                            "evaluation_objects": 2 * len(built["rows"])},
            "metrics": {"path": METRICS_FILE.relative_to(ROOT).as_posix(),
                        "sha256": sha256_file(METRICS_FILE)},
            "diagnostics": {"path": DIAGNOSTICS_FILE.relative_to(ROOT).as_posix(),
                            "sha256": sha256_file(DIAGNOSTICS_FILE)},
        },
        "frozen_arm_read_only": {
            "sun_prediction_path": FROZEN_SUN.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(FROZEN_SUN), "rerun": False, "rewritten": False},
        "safety": {"api_calls": 0, "llm_api_calls": 0, "gold_modified": False,
                   "thresholds_invented": False, "existing_results_rewritten": False,
                   "panel_modified": False, "bpmn_modified": False},
    }
    write_json(MANIFEST_FILE, manifest)
    verify_outputs()
    print(json.dumps({
        "run_id": RUN_ID, "rows": len(built["rows"]),
        "variant_macro_f1": built["metrics"]["A_variant_only_40"]["evaluation"]["macro_f1"],
        "variant_partition": {k: built["metrics"]["A_variant_only_40"]["partition"][k]
                              for k in ("correct", "wrong_type", "abstained",
                                        "false_compliance")},
        "control": {k: built["metrics"]["B_control_40"][k]
                    for k in ("explicitly_compliant", "false_positives", "abstained")},
        "paired_both_sides_correct": built["metrics"]["C_paired_40"]["both_sides_correct"],
        "llm_api_calls": 0,
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
