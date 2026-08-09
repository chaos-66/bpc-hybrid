# -*- coding: utf-8 -*-
"""Sun et al. (2024) Stage 3 development runner (S3.5).

Method-level independent reconstruction of Definitions 4-7 (matching score,
missing action, incorrect actor, out-of-order execution). Consumes the
frozen S3.1 GDPR7 Process Records (canonical stage1 parser) and the frozen
S3.2/S3.3 blank pack rule_text via the Gold-blind development Rule Record
adapter. Emits the common ``stage3_prediction@1.0.0`` schema and calls the
common evaluator (scripts/evaluate_stage3_common.py) with threshold sweep.

Gold-blind: no decision/candidate field is read by the runner. The
violation-item type alignment uses the frozen blank-pack build order
(config key ``violation_item_type_contract``): within each (process, rule)
group the three items are missing_action / incorrect_actor / out_of_order.

Usage:
    python scripts/run_sun_stage3_development.py [--variant v1]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import spacy  # noqa: E402

from bpc_hybrid.sun_stage3.sun_model import build_sun_models  # noqa: E402
from bpc_hybrid.sun_stage3.sun_rule_extraction import extract_rule_record  # noqa: E402
from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

CONFIG = ROOT / "configs" / "sun_stage3_development_v1.json"
MEMBERSHIP_CONTRACT = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
STAGE1_CONTRACT = ROOT / "configs" / "stage1_structural_s11_s14.json"
BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"
BLANK_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_blank_v1.json"
INFERENCE_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_inference_v1.json"
WINTER_FILES_DIR = ROOT.parent / "references" / "winter_2020_model_check" / "model_check" / "input" / "files"

# check_type comes from the explicit inference pack; no idx%3 / candidate routing


def _sha256(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} root must be an object")
    return value


def _git_state() -> dict[str, str]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        return {"commit": commit, "dirty_paths": dirty.splitlines()[:20]}
    except Exception as exc:  # pragma: no cover
        return {"commit": "unknown", "dirty_paths": [str(exc)]}


def run_id_of(config: dict[str, Any]) -> str:
    return f"s35_sun_stage3_development_{config['config_version']}"


def build_predictions(config: dict[str, Any], nlp, sim, signalwords: set[str],
                      inference: dict[str, Any], models: dict[str, Any],
                      scorer: SunScorer, tau: float, gamma: float,
                      theta: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Gold-blind Sun predictions over the inference pack. Reusable by the
    sensitivity script with different gamma/theta (mappings/denominators are
    re-derived; matching scores are recomputed too since Def 4 depends on tau
    only through the binary cutoff, but the score itself is tau-independent;
    we keep matching fixed by caller convention)."""
    rule_cache: dict[str, dict[str, Any]] = {}
    predictions: list[dict[str, Any]] = []
    rule_records: list[dict[str, Any]] = []

    # ------------------------------------------------------------- matching
    for item in sorted(inference["matching_items"], key=lambda i: i["item_id"]):
        process_id = item["process_id"]
        rule_id = item["rule_id"]
        record = rule_cache.get(rule_id)
        if record is None:
            record = extract_rule_record(rule_id, item["rule_text"], nlp, signalwords)
            rule_cache[rule_id] = record
            rule_records.append(record)
        model = models[process_id]
        m = scorer.matching_score(record["actions"], record["actors"], model)
        predictions.append({
            "schema_version": "stage3_prediction@1.0.0",
            "method_id": "sun_2024",
            "run_id": run_id_of(config),
            "task": "matching",
            "item_id": item["item_id"],
            "process_id": process_id,
            "rule_id": rule_id,
            "matching_score": round(m["matching_score"], 6),
            "predicted_relevance": m["matching_score"] > tau,
            "missing_action_score": None,
            "incorrect_actor_score": None,
            "out_of_order_score": None,
            "predicted_violation_type": None,
            "evidence": None,
            "threshold": tau,
            "config_version": config["config_version"],
            "source_hashes": {"rule_record": rule_id, "process_record": process_id},
            "method_provenance": f"sun_2024 Def4 tau={tau}",
            "gold_visible": False,
        })

    # ------------------------------------------------------------ violation
    # check_type comes from the explicit inference pack (routing metadata of
    # the frozen test point); no array-order / idx%3 / candidate-field logic
    v_items = sorted(inference["violation_items"], key=lambda i: i["item_id"])
    for item in v_items:
        process_id = item["process_id"]
        rule_id = item["rule_id"]
        check_type = item["check_type"]
        record = rule_cache.get(rule_id)
        if record is None:
            record = extract_rule_record(rule_id, item["rule_text"], nlp, signalwords)
            rule_cache[rule_id] = record
            rule_records.append(record)
        model = models[process_id]
        ma = scorer.missing_action(record["actions"], model)
        ia = scorer.incorrect_actor(record["actions"], record["actors"], model)
        oo = scorer.out_of_order(record["order_relations"], record["actions"], model)
        scores = {
            "missing_action": ma["score"],
            "incorrect_actor": ia["score"],
            "out_of_order": oo["score"],
        }
        item_score = scores[check_type]
        predicted = check_type if (item_score is not None and item_score > 0.0) else None
        predictions.append({
            "schema_version": "stage3_prediction@1.0.0",
            "method_id": "sun_2024",
            "run_id": run_id_of(config),
            "task": "violation",
            "item_id": item["item_id"],
            "process_id": process_id,
            "rule_id": rule_id,
            "matching_score": None,
            "predicted_relevance": None,
            "missing_action_score": round(ma["score"], 6),
            "incorrect_actor_score": round(ia["score"], 6) if ia["score"] is not None else None,
            "out_of_order_score": round(oo["score"], 6),
            "predicted_violation_type": predicted,
            "evidence": None,
            "threshold": gamma,
            "config_version": config["config_version"],
            "source_hashes": {"rule_record": rule_id, "process_record": process_id},
            "method_provenance": f"sun_2024 Def5-7 gamma={gamma} theta={theta}",
            "gold_visible": False,
            "check_type": check_type,
            "incorrect_actor_observable": ia["observable"],
            "incorrect_actor_reason": ia.get("reason"),
            # diagnostic detail (score components per type, not Gold-driven)
            "scores": {
                "missing_action": round(ma["score"], 6),
                "incorrect_actor": round(ia["score"], 6) if ia["score"] is not None else None,
                "out_of_order": round(oo["score"], 6),
                "missing_action_denominator": ma["denominator"],
                "incorrect_actor_denominator": ia["denominator"],
                "incorrect_actor_observable": ia["observable"],
                "incorrect_actor_reason": ia.get("reason"),
                "out_of_order_denominator": oo["denominator"],
            },
        })
    return predictions, rule_records


def write_run(config: dict[str, Any], variant: str) -> Path:
    run_dir = ROOT / "outputs" / "development" / f"s35_sun_stage3_development_{variant}"
    if run_dir.exists():
        raise RuntimeError(f"refusing to overwrite existing run dir: {run_dir}")
    run_dir.mkdir(parents=True)

    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    signalwords = set((WINTER_FILES_DIR / "signalwords.txt").read_text(encoding="utf-8").splitlines())
    blank = _load_json(BLANK_PACK, "blank pack")
    inference = _load_json(INFERENCE_PACK, "inference pack")

    # input binding check
    membership = _load_json(MEMBERSHIP_CONTRACT, "membership contract")
    frozen_ids = [item["input_id"] for item in membership["membership"]["files"]]
    bpmn_ids = sorted(p.stem for p in BPMN_DIR.glob("*.bpmn"))
    blank_ids = sorted({p["process_id"] for p in blank["processes"]})
    if frozen_ids != bpmn_ids or frozen_ids != blank_ids:
        raise RuntimeError("input binding mismatch: membership vs bpmn files vs blank pack")

    tau = float(config["method"]["thresholds"]["tau"])
    gamma = float(config["method"]["thresholds"]["gamma"])
    theta = float(config["method"]["thresholds"]["theta"])
    scorer = SunScorer(sim, tau, gamma, theta, nlp=nlp)
    models = build_sun_models(BPMN_DIR, STAGE1_CONTRACT, nlp)

    predictions, rule_records = build_predictions(
        config, nlp, sim, signalwords, inference, models, scorer, tau, gamma, theta
    )

    # ------------------------------------------------------------- artifacts
    config_snapshot = {
        "config_path": str(CONFIG.relative_to(ROOT).as_posix()),
        "config_sha256": _sha256(CONFIG),
        "config": config,
    }
    (run_dir / "config_snapshot.json").write_text(
        json.dumps(config_snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "rule_records.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rule_records),
        encoding="utf-8",
    )
    # process records binding index (hash + id list, not a copy of the records)
    process_index = {
        "source": "canonical Process Record via stage1_structural_s11_s14.json parser",
        "process_ids": sorted(models),
        "bpmn_dir": str(BPMN_DIR.relative_to(ROOT).as_posix()),
        "bpmn_dir_aggregate_sha256": _dir_aggregate_sha256(BPMN_DIR),
        "membership_payload_sha256": membership["membership"]["membership_payload_sha256"],
    }
    (run_dir / "process_records.jsonl").write_text(
        json.dumps(process_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    predictions_path = run_dir / "predictions.jsonl"
    with predictions_path.open("w", encoding="utf-8") as f:
        for p in predictions:
            f.write(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n")

    manifest = {
        "schema_version": "sun_stage3_run_manifest@1.0.0",
        "run_id": f"s35_sun_stage3_development_{variant}",
        "task_id": "S3.5",
        "status": "development_only",
        "command": "python scripts/run_sun_stage3_development.py"
                  + (f" --variant {variant}" if variant != "v1" else ""),
        "git": _git_state(),
        "inputs": {
            "bpmn_dir": str(BPMN_DIR.relative_to(ROOT).as_posix()),
            "bpmn_dir_membership_payload_sha256": membership["membership"]["membership_payload_sha256"],
            "bpmn_dir_aggregate_sha256": _dir_aggregate_sha256(BPMN_DIR),
            "membership_contract": {"path": str(MEMBERSHIP_CONTRACT.relative_to(ROOT).as_posix()),
                                    "sha256": _sha256(MEMBERSHIP_CONTRACT)},
            "stage1_structural_contract": {"path": str(STAGE1_CONTRACT.relative_to(ROOT).as_posix()),
                                           "sha256": _sha256(STAGE1_CONTRACT)},
            "blank_pack": {"path": str(BLANK_PACK.relative_to(ROOT).as_posix()),
                           "sha256": _sha256(BLANK_PACK),
                           "note": "no decisions in the blank pack; runner is gold-blind"},
            "inference_pack": {"path": str(INFERENCE_PACK.relative_to(ROOT).as_posix()),
                               "sha256": _sha256(INFERENCE_PACK),
                               "note": "gold-blind inference contract: item ids + rule_text + check_type only"},
            "signalwords": {"path": str((WINTER_FILES_DIR / "signalwords.txt").relative_to(ROOT.parent).as_posix()),
                            "sha256": _sha256(WINTER_FILES_DIR / "signalwords.txt"),
                            "self_contained": False},
        },
        "method": config["method"],
        "violation_item_type_contract": {
            "rule": "check_type read from the explicit gold-blind inference pack (stage3_inference@1.0.0); routing metadata of the frozen test point, not a Gold label",
            "note": "runner never reads candidate_violation_type, array order, idx%3, or any decision field",
        },
        "samples": {
            "matching_candidates": sum(1 for p in predictions if p["task"] == "matching"),
            "violation_candidates": sum(1 for p in predictions if p["task"] == "violation"),
            "excluded": [],
        },
        "implementation_hashes": {
            "config": _sha256(CONFIG),
            "runner": _sha256(Path(__file__)),
            "sun_model": _sha256(ROOT / "src" / "bpc_hybrid" / "sun_stage3" / "sun_model.py"),
            "sun_rule_extraction": _sha256(ROOT / "src" / "bpc_hybrid" / "sun_stage3" / "sun_rule_extraction.py"),
            "sun_scorer": _sha256(ROOT / "src" / "bpc_hybrid" / "sun_stage3" / "sun_scorer.py"),
            "shared_similarity": _sha256(ROOT / "src" / "bpc_hybrid" / "winter_stage3" / "winter_similarity.py"),
        },
        "dependency_index": {
            "python": sys.version.split()[0],
            "spacy": spacy.__version__,
            "spacy_model": "en_core_web_sm",
            "external_signalwords": {
                "dir": str(WINTER_FILES_DIR.relative_to(ROOT.parent).as_posix()),
                "self_contained": False,
            },
        },
        "external_runtime_prerequisites": [
            "spacy package + en_core_web_sm model",
            "references/winter_2020_model_check/model_check/input/files/signalwords.txt (read-only lexicon)",
        ],
        "export_index": {
            "schema": "configs/schemas/stage3_prediction.schema.json",
            "predictions": "predictions.jsonl",
            "rule_records": "rule_records.jsonl",
            "process_records_index": "process_records.jsonl",
            "evaluation": "evaluation.json",
            "threshold_sensitivity": "threshold_sensitivity.json",
            "error_analysis": "error_analysis.md",
        },
        "safety": {
            "llm_api_called": False,
            "network_called": False,
            "env_read": False,
            "gold_decisions_read": False,
            "correction_pack_read": False,
            "candidate_fields_read": False,
            "bpmn_modified": False,
            "no_overwrite": True,
        },
        "artifacts": {
            "config_snapshot": {"path": "config_snapshot.json",
                                "sha256": _sha256(run_dir / "config_snapshot.json")},
            "rule_records": {"path": "rule_records.jsonl",
                             "sha256": _sha256(run_dir / "rule_records.jsonl")},
            "process_records_index": {"path": "process_records.jsonl",
                                      "sha256": _sha256(run_dir / "process_records.jsonl")},
            "predictions": {"path": "predictions.jsonl",
                            "sha256": _sha256(predictions_path)},
        },
    }
    manifest["inputs"]["bpmn_files_sha256"] = {
        str(p.relative_to(ROOT).as_posix()): _sha256(p)
        for p in sorted(BPMN_DIR.glob("*.bpmn"))
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return run_dir


def _dir_aggregate_sha256(directory: Path) -> str:
    import hashlib
    entries = {
        str(p.relative_to(directory).as_posix()): _sha256(p)
        for p in sorted(directory.glob("*.bpmn"))
    }
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="v1", help="run dir variant suffix")
    args = parser.parse_args()
    config = _load_json(CONFIG, "sun stage3 config")
    try:
        run_dir = write_run(config, args.variant)
        # 1) common evaluator: evaluation.json + matching tau sweep +
        #    error_analysis.md (the only component allowed to read Gold)
        eval_script = ROOT / "scripts" / "evaluate_stage3_common.py"
        result = subprocess.run(
            [sys.executable, str(eval_script),
             "--predictions", str(run_dir / "predictions.jsonl"),
             "--run-dir", str(run_dir), "--sweep", "--error-analysis"],
            cwd=ROOT, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            raise RuntimeError("common evaluator failed:\n" + result.stdout[-800:])
        # 2) real gamma/theta sensitivity (scorer re-execution)
        sens_script = ROOT / "scripts" / "sun_stage3_sensitivity.py"
        result = subprocess.run(
            [sys.executable, str(sens_script), "--run-dir", str(run_dir)],
            cwd=ROOT, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            raise RuntimeError("sun sensitivity failed:\n" + result.stdout[-800:])
        # 3) finalise: export_index.json + manifest artifacts/finalised
        from stage3_run_common import finalise_run
        finalise_run(run_dir, {
            "config_snapshot": "config_snapshot.json",
            "predictions": "predictions.jsonl",
            "rule_records": "rule_records.jsonl",
            "process_records_index": "process_records.jsonl",
            "evaluation": "evaluation.json",
            "threshold_sensitivity": "threshold_sensitivity.json",
            "error_analysis": "error_analysis.md",
        })
        print(f"finalised run: {run_dir.relative_to(ROOT).as_posix()}")
        return 0
    except RuntimeError as exc:
        print(f"sun stage3 run failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
