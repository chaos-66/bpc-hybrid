# -*- coding: utf-8 -*-
"""S3.9-EXT final repair arm: the four extension types with v3 localization plus
the evidence-backed D1/D2/D3 repairs, on the frozen 80-instance panel.

The arm runs the same panel, rule binding, candidate surfaces, formulas,
``gamma_ext`` decision rule and evaluators as every other cell; the only
replacement is the action-resolution entry points of the v3 adapter
(``src/bpc_hybrid/s3_extended_v3_repair.py``).  The action gamma stays Winter's
frozen 0.4 for exactly the same reason the diagnostic arm used it: it is the
pre-specified configuration of the own-method baseline, not a searched value.

Predictions are written to disk before any label is read.  Zero API, zero LLM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import run_s3_extended_violation_panel_v2 as panel_runner  # noqa: E402
from bpc_hybrid.s3_action_matching_v3 import EvidenceChecksV3  # noqa: E402
from bpc_hybrid.s3_extended_arm_report import arm_metrics, per_item_evidence  # noqa: E402
from bpc_hybrid.s3_extended_unified import unified_rows  # noqa: E402
from bpc_hybrid.s3_extended_v3_adapter import ADAPTER_ID  # noqa: E402
from bpc_hybrid.s3_extended_v3_repair import (  # noqa: E402
    REPAIR_ID, RESOLVED_BY_ACTION_GAMMA, RESOLVED_BY_V3_MATCH, RESOLVED_NONE,
    RepairedExtendedScorer, repair_policy,
)
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_bytes  # noqa: E402
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES, ConstraintSurface, condition_candidates, constraint_candidates,
    exception_candidates,
)
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

RUN_ID = "s3_extended_v3_repair_v1"
METHOD_ID = "v3_localization_repaired"
METHOD_DISPLAY = "v3 four-type extension with one action resolution and a coherent score scale"
ACTION_GAMMA = 0.4
REFERENCE_ARM = ROOT / "outputs/development/s3_extended_v3_gamma04_v1"
OUT_DIR = ROOT / "outputs/development" / RUN_ID
PREDICTIONS_FILE = OUT_DIR / "predictions.jsonl"
METRICS_FILE = OUT_DIR / "metrics.json"
DIAGNOSTICS_FILE = OUT_DIR / "diagnostics.json"
MANIFEST_FILE = OUT_DIR / "manifest.json"
OUT_FILES = ("predictions.jsonl", "metrics.json", "diagnostics.json", "manifest.json")


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
        ROOT / "src/bpc_hybrid/s3_extended_v3_adapter.py",
        ROOT / "src/bpc_hybrid/s3_action_matching_v3.py",
        ROOT / "src/bpc_hybrid/s3_action_matching_v2.py",
        ROOT / "src/bpc_hybrid/s3_evidence_checks_v1.py",
        ROOT / "src/bpc_hybrid/winter_stage3/winter_similarity.py",
        ROOT / "src/bpc_hybrid/sun_stage3/sun_model.py",
        ROOT / "outputs/development/s3_extended_v3_v1/predictions.jsonl",
        REFERENCE_ARM / "predictions.jsonl",
    ]
    paths += sorted((ROOT / "data/input/stage1_stage3/gdpr7").glob("*.bpmn"))
    for variant in read_json(panel_runner.PANEL)["variants"]:
        for side in ("control", "variant"):
            paths.append(ROOT / variant[f"{side}_bpmn"])
    return paths


def score_side(sentence: dict, bpmn_path: Path, process_id: str, v3, sim_text,
               gamma_action: float, gamma_ext: float, nlp, contract) -> dict:
    source_path = str(bpmn_path.relative_to(ROOT))
    raw_bytes = bpmn_path.read_bytes()
    record = parse_bpmn_bytes(raw_bytes, source_path=source_path, contract=contract)
    model = SunProcessModel(process_id, record, nlp)
    xml_root = ET.fromstring(raw_bytes)
    scorer = RepairedExtendedScorer(v3, sim_text, gamma_action, gamma_ext)

    resolution = scorer.resolve_action(sentence.get("action") or "", model)
    mapped_id = resolution["resolved_activity_id"]
    condition_surface = condition_candidates(record, xml_root, mapped_id)
    constraint_surface = constraint_candidates(record, xml_root, mapped_id)
    exception_surface = exception_candidates(record, xml_root, mapped_id)

    results = {
        "prohibited_action_present": scorer.prohibited_action(sentence, model),
        "required_condition_not_enforced": scorer.required_condition(
            sentence, model, condition_surface),
        "constraint_violated": scorer.constraint_violated(
            sentence, model, constraint_surface),
        "exception_not_handled": scorer.exception_not_handled(
            sentence, model, exception_surface),
    }
    scores = {t: (results[t].get("score") if results[t].get("observable") else None)
              for t in EXTENDED_TYPES}
    observability = {t: {"observable": bool(results[t].get("observable", False)),
                         "reason": results[t].get("reason")}
                     for t in EXTENDED_TYPES}
    clean = {t: {"score": scores[t], "observable": observability[t]["observable"],
                 "reason": observability[t]["reason"],
                 "exact_contradiction": results[t].get("exact_contradiction")}
             for t in EXTENDED_TYPES}
    surfaces = {
        "required_condition_not_enforced": condition_surface,
        "constraint_violated": constraint_surface,
        "exception_not_handled": exception_surface,
    }
    binding = {}
    for t in EXTENDED_TYPES:
        surface = surfaces.get(t)
        binding[t] = {
            "matched_activity_id": results[t].get("matched_activity_id"),
            "surface_activity_id": (surface.activity_id
                                    if isinstance(surface, ConstraintSurface) else None),
            "candidate_count": len(surface) if surface is not None else None,
            "consumed_candidate": results[t].get("best_candidate"),
            "consumed_score": scores[t],
            "consumed_similarity": results[t].get("max_sim"),
            "surface_activity_id_equals_resolution": (
                (surface.activity_id if isinstance(surface, ConstraintSurface) else None)
                == mapped_id),
            "same_activity_as_localization": (
                results[t].get("matched_activity_id") in (None, mapped_id)
                and (not isinstance(surface, ConstraintSurface)
                     or surface.activity_id in (None, mapped_id))),
        }
    return {
        "scores": scores,
        "scores_detail": {t: {k: v for k, v in results[t].items() if k != "score"}
                          for t in EXTENDED_TYPES},
        "observability": observability,
        "clean_scores": clean,
        "action_resolution": resolution,
        "localization": resolution,
        "evidence_binding": binding,
        "matched_activity_id": mapped_id,
    }


def build_row(variant: dict, sentence: dict, v3, sim_text, gamma_action: float,
              gamma_ext: float, nlp, contract) -> dict:
    pid = variant["process_id"]
    variant_side = score_side(sentence, ROOT / variant["variant_bpmn"], pid, v3, sim_text,
                              gamma_action, gamma_ext, nlp, contract)
    control_side = score_side(sentence, ROOT / variant["control_bpmn"], pid, v3, sim_text,
                              gamma_action, gamma_ext, nlp, contract)
    return {
        "schema_version": "stage3_extended_prediction@1.0.0",
        "method_id": METHOD_ID,
        "method_display_name": METHOD_DISPLAY,
        "run_id": f"{RUN_ID}_{METHOD_ID}",
        "task": "violation",
        "item_id": variant["variant_id"],
        "process_id": pid,
        "rule_id": variant["rule_id"],
        "expected_violation": variant["expected_violation"],
        "check_type": variant["expected_violation"],
        "predicted_violation_type": None,
        "scores": variant_side["scores"],
        "scores_detail": variant_side["scores_detail"],
        "observability": variant_side["observability"],
        "control_scores": control_side["clean_scores"],
        "action_localization": {
            "adapter": REPAIR_ID,
            "base_adapter": ADAPTER_ID,
            "variant": variant_side["action_resolution"],
            "control": control_side["action_resolution"],
        },
        "evidence_binding": {
            "variant": variant_side["evidence_binding"],
            "control": control_side["evidence_binding"],
        },
        "matched_activity": {
            "variant": variant_side["matched_activity_id"],
            "control": control_side["matched_activity_id"],
        },
        "thresholds": {
            "gamma_ext": gamma_ext,
            "action_gamma": gamma_action,
            "action_gate": "single_action_resolution_v1",
            "v3_method_id": getattr(v3, "method_id", None),
            "v3_thresholds": {"tau": v3.tau, "gamma": v3.gamma, "theta": v3.theta},
            "repair_id": REPAIR_ID,
        },
        "threshold": gamma_ext,
        "action_mapping_gamma": gamma_action,
        "gamma_ext": gamma_ext,
        "panel": "synthetic_controlled_error_extension_v2",
        "gold_visible": False,
        "source_hashes": {
            "variant": variant["variant_id"],
            "source_bpmn_sha256": variant["source_bpmn_sha256"],
            "variant_bpmn_sha256": variant["variant_bpmn_sha256"],
            "control_bpmn_sha256": variant["control_bpmn_sha256"],
        },
        "method_provenance": (
            f"{METHOD_DISPLAY}; inherits the frozen panel, extractor, candidate "
            "surfaces, four formulas, gamma_ext decision rule and evaluators, and "
            f"v3's structured action match ({ADAPTER_ID}); replaces only the action "
            f"resolution with {REPAIR_ID} (zero API, development-only arm)"),
    }


def build_all() -> dict:
    import spacy
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    panel = read_json(panel_runner.PANEL)
    gamma_ext = float(panel["config"]["gamma_ext"])
    sun_config = read_json(panel_runner.SUN_CONFIG)
    tau = float(sun_config["method"]["thresholds"]["tau"])
    gamma = float(sun_config["method"]["thresholds"]["gamma"])
    theta = float(sun_config["method"]["thresholds"]["theta"])
    winter_config = read_json(panel_runner.WINTER_CONFIG)
    if abs(float(winter_config["method"]["gamma"]) - ACTION_GAMMA) > 1e-12:
        raise RuntimeError("ACTION_GAMMA is no longer Winter's frozen gamma")
    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    v3 = EvidenceChecksV3(sim, tau, gamma, theta, nlp)
    contract = load_stage1_contract(panel_runner.STRUCTURAL_CONTRACT)
    rule_texts = panel_runner._rule_texts()

    rows = []
    for variant in panel["variants"]:
        sentence = panel_runner._locked_sentence(variant, rule_texts[variant["rule_id"]], nlp)
        rows.append(build_row(variant, sentence, v3, sim.text_pair, ACTION_GAMMA,
                              gamma_ext, nlp, contract))
    rows = unified_rows(rows, gamma_ext)
    write_rows(PREDICTIONS_FILE, rows)  # predictions fixed before any label is read

    gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}
    metrics = arm_metrics(rows, panel, gold, gamma_ext)
    resolved_by = {"variant": {}, "control": {}}
    for row in rows:
        for side in ("variant", "control"):
            key = row["action_localization"][side]["resolved_by"]
            resolved_by[side][key] = resolved_by[side].get(key, 0) + 1
    allowed = {RESOLVED_BY_V3_MATCH, RESOLVED_BY_ACTION_GAMMA, RESOLVED_NONE}
    unexpected = sorted((set(resolved_by["variant"]) | set(resolved_by["control"]))
                        - allowed)
    if unexpected:
        raise RuntimeError(f"unexpected action resolutions: {unexpected}")
    metrics.update({
        "run_id": RUN_ID, "method_id": METHOD_ID, "method_display_name": METHOD_DISPLAY,
        "generated_utc": started, "scope": "development_only",
        "arm": {
            "action_matching_path": "v3_structured_action_match_plus_repair",
            "base_adapter": ADAPTER_ID, "repair": REPAIR_ID,
            "action_gamma": ACTION_GAMMA,
            "action_gamma_source": ("configs/winter_stage3_development_v1.json "
                                    "method.gamma, migrated unchanged"),
            "gamma_ext": gamma_ext,
            "action_gate": "single_action_resolution_v1",
            "v3_thresholds": {"tau": tau, "gamma": gamma, "theta": theta},
            "repair_policy": repair_policy(),
        },
        "action_resolution_counts": resolved_by,
    })
    diagnostics = {
        "schema_version": "s3_extended_arm_diagnostics@1.0.0",
        "run_id": RUN_ID,
        "action_matching_path": "v3_structured_action_match_plus_repair",
        "action_gamma": ACTION_GAMMA,
        "gamma_ext": gamma_ext,
        "repair_policy": repair_policy(),
        "instances": [per_item_evidence(r, gold, rule_texts) for r in rows],
    }
    write_json(METRICS_FILE, metrics)
    write_json(DIAGNOSTICS_FILE, diagnostics)
    return {"rows": rows, "metrics": metrics, "diagnostics": diagnostics,
            "panel": panel, "runtime_seconds": round(time.time() - t0, 3),
            "started_utc": started}


def verify_outputs() -> dict:
    manifest = read_json(MANIFEST_FILE)
    mismatched = [f"{sec}:{rel}" for sec in ("inputs", "implementation")
                  for rel, digest in manifest[sec].items()
                  if sha256_file(ROOT / rel) != digest]
    mismatched += [f"results:{k}" for k, e in manifest["results"].items()
                   if sha256_file(ROOT / e["path"]) != e["sha256"]]
    for key, entry in manifest["reused_read_only_cells"].items():
        if entry["rerun"] is not False or entry["rewritten"] is not False:
            raise RuntimeError(f"the {key} cell must stay read-only")
        if sha256_file(ROOT / entry["path"]) != entry["sha256"]:
            raise RuntimeError(f"the {key} cell changed")
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
    # every observable evidence score must be bound to the resolved activity
    for row in rows:
        for side in ("variant", "control"):
            binding = row["evidence_binding"][side]
            for t in EXTENDED_TYPES:
                entry = binding[t]
                if entry["consumed_score"] is None:
                    continue
                if not entry["same_activity_as_localization"]:
                    raise RuntimeError(
                        f"{row['item_id']}:{side}:{t}: evidence is not bound to the "
                        "resolved activity")
    return {"rows": rows, "metrics": metrics, "manifest": manifest}


def main() -> int:
    global OUT_DIR, PREDICTIONS_FILE, METRICS_FILE, DIAGNOSTICS_FILE, MANIFEST_FILE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT_DIR,
                        help="output directory (a replay must use a new one)")
    args = parser.parse_args()
    if args.out != OUT_DIR:
        OUT_DIR = args.out
        PREDICTIONS_FILE = OUT_DIR / "predictions.jsonl"
        METRICS_FILE = OUT_DIR / "metrics.json"
        DIAGNOSTICS_FILE = OUT_DIR / "diagnostics.json"
        MANIFEST_FILE = OUT_DIR / "manifest.json"
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
            "src/bpc_hybrid/s3_extended_v3_repair.py":
                sha256_file(ROOT / "src/bpc_hybrid/s3_extended_v3_repair.py"),
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
        "reused_read_only_cells": {
            key: {"path": (path).relative_to(ROOT).as_posix(),
                  "sha256": sha256_file(path), "rerun": False, "rewritten": False}
            for key, path in (
                ("v3_gamma_0_8", ROOT / "outputs/development/s3_extended_v3_v1/predictions.jsonl"),
                ("v3_gamma_0_4_diagnostic", REFERENCE_ARM / "predictions.jsonl"),
                ("original_gamma_0_4",
                 ROOT / "outputs/development/s3_extended_baseline_04_v1/predictions.jsonl"),
                ("winter_frozen",
                 ROOT / "outputs/evidence/s3_formula_repair_v2/extended_four/reference/"
                         "winter/predictions.jsonl"),
                ("sun_frozen",
                 ROOT / "outputs/evidence/s3_formula_repair_v2/extended_four/reference/"
                         "sun/predictions.jsonl"),
            )},
        "safety": {"api_calls": 0, "llm_api_calls": 0, "gold_modified": False,
                   "threshold_searched": False, "per_item_threshold_used": False,
                   "sample_id_special_case": False, "existing_results_rewritten": False,
                   "panel_modified": False, "bpmn_modified": False,
                   "frozen_modules_modified": False},
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
        "action_resolution": built["metrics"]["action_resolution_counts"],
        "llm_api_calls": 0,
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
