# -*- coding: utf-8 -*-
"""Winter et al. (2020) Stage 3 development wrapper - single entry point.

Runs the Winter baseline on the frozen S3.1 GDPR7 BPMN set and the frozen
S3.2/S3.3 candidate pack (25 matching pairs + 33 violation points), writing
a complete, deterministic, development-only run directory:

    outputs/development/s34_winter_stage3_development_<variant>/
        config_snapshot.json
        predictions.jsonl
        evaluation.json
        error_analysis.md
        manifest.json

Gold-blind: the runner reads only the BLANK pack (candidates + rule_text,
no decisions); the correction pack is read only by the evaluator.

Usage:
    python scripts/run_winter_stage3_development.py
    python scripts/run_winter_stage3_development.py --variant v1
    python scripts/run_winter_stage3_development.py --evaluate-only <run_dir>
"""

from __future__ import annotations

import argparse
import hashlib
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

from bpc_hybrid.winter_stage3.winter_clause import parse_regulation_paragraph  # noqa: E402
from bpc_hybrid.winter_stage3.winter_model import parse_bpmn_file_winter  # noqa: E402
from bpc_hybrid.winter_stage3.winter_pair import WinterPair  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

CONFIG = ROOT / "configs" / "winter_stage3_development_v1.json"
MEMBERSHIP_CONTRACT = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"
BLANK_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_blank_v1.json"
CORRECTION_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"
WINTER_FILES_DIR = ROOT.parent / "references" / "winter_2020_model_check" / "model_check" / "input" / "files"


def _sha256(path: Path) -> str:
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
    except Exception as exc:  # pragma: no cover - git availability
        return {"commit": "unknown", "dirty_paths": [str(exc)]}


def load_winter_lexicon() -> tuple[set[str], set[str], set[str]]:
    signalwords = set((WINTER_FILES_DIR / "signalwords.txt").read_text(encoding="utf-8").splitlines())
    sequencemarkers = set((WINTER_FILES_DIR / "sequencemarkers.txt").read_text(encoding="utf-8").splitlines())
    stopwords = set((WINTER_FILES_DIR / "stopwords.txt").read_text(encoding="utf-8").splitlines())
    return signalwords, sequencemarkers, stopwords


def build_predictions(config: dict[str, Any], nlp, sim: WinterSimilarity,
                      signalwords, sequencemarkers, stopwords,
                      blank: dict[str, Any]) -> list[dict[str, Any]]:
    gamma = float(config["method"]["gamma"])
    delta = float(config["method"]["delta"])

    # load the 7 frozen BPMN models the Winter way
    models: dict[str, Any] = {}
    for bpmn in sorted(BPMN_DIR.glob("*.bpmn")):
        models[bpmn.stem] = parse_bpmn_file_winter(bpmn, nlp, stopwords)

    # candidate process-rule pairs from the frozen blank pack
    rule_texts: dict[str, str] = {}
    pair_ids: dict[tuple[str, str], str] = {}   # (process, rule) -> first matching item_id
    for item in blank["matching_items"]:
        rule_texts.setdefault(item["rule_id"], item["rule_text"])
        pair_ids.setdefault((item["process_id"], item["rule_id"]), item["item_id"])

    # resource set = model participants (prototype semantics)
    resource_set = set()
    for model in models.values():
        for proc in model.processes:
            resource_set.add(proc.participant.lower())

    predictions: list[dict[str, Any]] = []

    # -------- matching predictions (25) ---------------------------------
    for item in sorted(blank["matching_items"], key=lambda i: i["item_id"]):
        process_id = item["process_id"]
        rule_id = item["rule_id"]
        model = models[process_id]
        paragraph = parse_regulation_paragraph(
            rule_id, rule_texts[rule_id], nlp, stopwords,
            signalwords, sequencemarkers, only_constraints=True,
        )
        pair = WinterPair(nlp, sim, model, paragraph, resource_set, gamma, delta)
        predictions.append({
            "task": "matching",
            "item_id": item["item_id"],
            "process_id": process_id,
            "rule_id": rule_id,
            "fitness": round(pair.fitness, 6),
            "cost_obligation": round(pair.cost_obligation, 6),
            "cost_resource": round(pair.cost_resource, 6),
            "cost_so": round(pair.cost_so, 6),
            "cost": round(pair.cost, 6),
            "threshold_gamma": gamma,
            "predicted_relevant": pair.fitness > 0.0,
            "gold_visible": False,
        })

    # -------- violation predictions (33) --------------------------------
    for item in sorted(blank["violation_items"], key=lambda i: i["item_id"]):
        process_id = item["process_id"]
        rule_id = item["rule_id"]
        model = models[process_id]
        paragraph = parse_regulation_paragraph(
            rule_id, rule_texts[rule_id], nlp, stopwords,
            signalwords, sequencemarkers, only_constraints=True,
        )
        pair = WinterPair(nlp, sim, model, paragraph, resource_set, gamma, delta)
        costs = {
            "missing_action": pair.cost_obligation,
            "incorrect_actor": pair.cost_resource,
            "out_of_order": pair.cost_so,
        }
        candidate_type = item["candidate_violation_type"]
        # each violation item targets exactly one type; predict that type when
        # the corresponding Winter cost is > 0, otherwise none (compliant)
        predicted = candidate_type if costs[candidate_type] > 0.0 else None
        predictions.append({
            "task": "violation",
            "item_id": item["item_id"],
            "process_id": process_id,
            "rule_id": rule_id,
            "candidate_violation_type": candidate_type,
            "predicted_violation_type": predicted,
            "cost_obligation": round(pair.cost_obligation, 6),
            "cost_resource": round(pair.cost_resource, 6),
            "cost_so": round(pair.cost_so, 6),
            "threshold_gamma": gamma,
            "gold_visible": False,
        })
    return predictions


def write_run(config: dict[str, Any], variant: str) -> Path:
    run_dir = ROOT / "outputs" / "development" / f"s34_winter_stage3_development_{variant}"
    if run_dir.exists():
        raise RuntimeError(f"refusing to overwrite existing run dir: {run_dir}")
    run_dir.mkdir(parents=True)

    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    signalwords, sequencemarkers, stopwords = load_winter_lexicon()
    blank = _load_json(BLANK_PACK, "blank pack")

    # input binding check: membership contract process ids == bpmn files == blank pack
    membership = _load_json(MEMBERSHIP_CONTRACT, "membership contract")
    frozen_ids = [item["input_id"] for item in membership["membership"]["files"]]
    bpmn_ids = sorted(p.stem for p in BPMN_DIR.glob("*.bpmn"))
    blank_ids = sorted({p["process_id"] for p in blank["processes"]})
    if frozen_ids != bpmn_ids or frozen_ids != blank_ids:
        raise RuntimeError(
            "input binding mismatch: membership vs bpmn files vs blank pack"
        )

    predictions = build_predictions(
        config, nlp, sim, signalwords, sequencemarkers, stopwords, blank
    )

    # -------- write artifacts -------------------------------------------
    config_snapshot = {
        "config_path": str(CONFIG.relative_to(ROOT).as_posix()),
        "config_sha256": _sha256(CONFIG),
        "config": config,
    }
    (run_dir / "config_snapshot.json").write_text(
        json.dumps(config_snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    predictions_path = run_dir / "predictions.jsonl"
    with predictions_path.open("w", encoding="utf-8") as f:
        for p in predictions:
            f.write(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n")

    manifest = {
        "schema_version": "winter_stage3_run_manifest@1.0.0",
        "run_id": f"s34_winter_stage3_development_{variant}",
        "task_id": "S3.4",
        "status": "development_only",
        "command": "python scripts/run_winter_stage3_development.py" + (f" --variant {variant}" if variant != "v1" else ""),
        "git": _git_state(),
        "inputs": {
            "bpmn_dir": str(BPMN_DIR.relative_to(ROOT).as_posix()),
            "bpmn_files": [str(p.relative_to(ROOT).as_posix()) for p in sorted(BPMN_DIR.glob("*.bpmn"))],
            "bpmn_dir_sha256": None,
            "membership_contract": {
                "path": str(MEMBERSHIP_CONTRACT.relative_to(ROOT).as_posix()),
                "sha256": _sha256(MEMBERSHIP_CONTRACT),
            },
            "blank_pack": {
                "path": str(BLANK_PACK.relative_to(ROOT).as_posix()),
                "sha256": _sha256(BLANK_PACK),
                "note": "no decisions in the blank pack; runner is gold-blind",
            },
            "winter_lexicon": {
                "dir": str(WINTER_FILES_DIR.relative_to(ROOT.parent).as_posix()),
                "signalwords_sha256": _sha256(WINTER_FILES_DIR / "signalwords.txt"),
                "sequencemarkers_sha256": _sha256(WINTER_FILES_DIR / "sequencemarkers.txt"),
                "stopwords_sha256": _sha256(WINTER_FILES_DIR / "stopwords.txt"),
            },
        },
        "method": config["method"],
        "samples": {
            "matching_candidates": sum(1 for p in predictions if p["task"] == "matching"),
            "violation_candidates": sum(1 for p in predictions if p["task"] == "violation"),
            "excluded": [],
        },
        "safety": {
            "llm_api_called": False,
            "network_called": False,
            "env_read": False,
            "gold_decisions_read": False,
            "correction_pack_read": False,
            "bpmn_modified": False,
            "no_overwrite": True,
        },
        "artifacts": {
            "config_snapshot": {
                "path": "config_snapshot.json",
                "sha256": _sha256(run_dir / "config_snapshot.json"),
            },
            "predictions": {
                "path": "predictions.jsonl",
                "sha256": _sha256(predictions_path),
            },
        },
    }
    # per-file bpmn hashes
    manifest["inputs"]["bpmn_files_sha256"] = {
        str(p.relative_to(ROOT).as_posix()): _sha256(p)
        for p in sorted(BPMN_DIR.glob("*.bpmn"))
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="v1", help="run dir variant suffix")
    args = parser.parse_args()
    config = _load_json(CONFIG, "winter stage3 config")
    try:
        run_dir = write_run(config, args.variant)
    except RuntimeError as exc:
        print(f"winter stage3 run failed closed: {exc}", file=sys.stderr)
        return 2
    print(f"run dir: {run_dir.relative_to(ROOT).as_posix()}")
    # evaluation happens in the evaluator script (gold read allowed there)
    eval_script = ROOT / "scripts" / "evaluate_winter_stage3_development.py"
    result = subprocess.run(
        [sys.executable, str(eval_script), "--run-dir", str(run_dir)],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    print(result.stdout)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
