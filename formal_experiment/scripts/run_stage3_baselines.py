# -*- coding: utf-8 -*-
"""S3.6 non-LLM baseline runner (BM25 lexical arm + TF-IDF/SVD dense arm).

One entry point, two arms (``--arm bm25`` / ``--arm tfidf_svd``). Both arms
consume the SAME Gold-blind inference pack and the SAME canonical Process
Records, produce the common ``stage3_prediction@1.0.0`` schema, and are
evaluated by the SAME common evaluator on the SAME 58 item IDs.

Gold-blind: the runner reads only the inference pack (item ids + rule_text +
check_type); rule records come from the shared Gold-blind development
adapter; no decision/candidate/evidence field is read.

Usage:
    python scripts/run_stage3_baselines.py --arm bm25
    python scripts/run_stage3_baselines.py --arm tfidf_svd
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
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import spacy  # noqa: E402

from bpc_hybrid.stage3_baselines.baseline_stage3 import BaselineScorer  # noqa: E402
from bpc_hybrid.stage3_baselines.bm25 import BM25Index  # noqa: E402
from bpc_hybrid.stage3_baselines.tfidf_svd import TfidfSvd  # noqa: E402
from bpc_hybrid.sun_stage3.sun_model import build_sun_models  # noqa: E402
from bpc_hybrid.sun_stage3.sun_rule_extraction import extract_rule_record  # noqa: E402

CONFIGS = {
    "bm25": ROOT / "configs" / "bm25_stage3_development_v1.json",
    "tfidf_svd": ROOT / "configs" / "tfidf_svd_stage3_development_v1.json",
}
MEMBERSHIP_CONTRACT = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
STAGE1_CONTRACT = ROOT / "configs" / "stage1_structural_s11_s14.json"
BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"
INFERENCE_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_inference_v1.json"
WINTER_FILES_DIR = ROOT.parent / "references" / "winter_2020_model_check" / "model_check" / "input" / "files"


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


def _run_id(arm: str, config: dict[str, Any]) -> str:
    return f"s36_{arm}_stage3_development_{config['config_version']}"


def build_similarity(arm: str, config: dict[str, Any], models, nlp):
    """Build a per-model similarity factory. TF-IDF/SVD fits once on
    unlabeled rule texts + process labels only; BM25 builds one index per
    process model (query vs that model's action labels)."""
    if arm == "bm25":
        k1 = float(config["method"]["bm25"]["k1"])
        b = float(config["method"]["bm25"]["b"])
        indices: dict[str, BM25Index] = {}
        for pid, model in models.items():
            docs = [a["name"] for a in model.actions if a["name"]]
            indices[pid] = BM25Index(docs, k1=k1, b=b)

        def factory(model: Any) -> Any:
            index = indices[model.process_id]

            def sim(a: str, b: str) -> float:
                return index.query(a)[0]
            return sim
        return factory
    if arm == "tfidf_svd":
        seed = int(config["method"]["svd"]["seed"])
        dim = int(config["method"]["svd"]["dim"])
        svd = TfidfSvd(seed=seed, dim=dim,
                       word_ngram=int(config["method"]["features"]["word_ngram"]),
                       char_ngram=int(config["method"]["features"]["char_ngram"]),
                       sublinear_tf=bool(config["method"]["features"]["sublinear_tf"]))
        # unlabeled fit corpus: distinct rule texts + all process labels
        inference = _load_json(INFERENCE_PACK, "inference pack")
        corpus = list(dict.fromkeys(i["rule_text"] for i in inference["matching_items"]))
        for model in models.values():
            corpus.extend(a["name"] for a in model.actions if a["name"])
            corpus.extend(model.actors)
        svd.fit(corpus)

        def factory(model: Any) -> Any:
            return svd.similarity
        return factory
    raise RuntimeError(f"unknown arm: {arm}")


def build_predictions(arm: str, config: dict[str, Any], sim_factory, nlp, signalwords,
                      inference: dict[str, Any], models, scorer: BaselineScorer,
                      tau: float, gamma: float, theta: float):
    rule_cache: dict[str, dict[str, Any]] = {}
    predictions: list[dict[str, Any]] = []
    rule_records: list[dict[str, Any]] = []

    def record_for(rule_id: str, rule_text: str):
        if rule_id not in rule_cache:
            rec = extract_rule_record(rule_id, rule_text, nlp, signalwords)
            rule_cache[rule_id] = rec
            rule_records.append(rec)
        return rule_cache[rule_id]

    for item in sorted(inference["matching_items"], key=lambda i: i["item_id"]):
        record = record_for(item["rule_id"], item["rule_text"])
        model = models[item["process_id"]]
        m = scorer.matching_score(record["actions"], record["actors"], model)
        predictions.append({
            "schema_version": "stage3_prediction@1.0.0",
            "method_id": f"s36_{arm}",
            "run_id": _run_id(arm, config),
            "task": "matching",
            "item_id": item["item_id"],
            "process_id": item["process_id"],
            "rule_id": item["rule_id"],
            "matching_score": round(m["matching_score"], 6),
            "predicted_relevance": m["predicted_relevance"],
            "missing_action_score": None,
            "incorrect_actor_score": None,
            "out_of_order_score": None,
            "predicted_violation_type": None,
            "evidence": None,
            "threshold": tau,
            "config_version": config["config_version"],
            "source_hashes": {"rule_record": item["rule_id"], "process_record": item["process_id"]},
            "method_provenance": f"s36_{arm} tau={tau}",
            "gold_visible": False,
        })

    for item in sorted(inference["violation_items"], key=lambda i: i["item_id"]):
        record = record_for(item["rule_id"], item["rule_text"])
        model = models[item["process_id"]]
        ma = scorer.missing_action(record["actions"], model)
        ia = scorer.incorrect_actor(record["actions"], record["actors"], model)
        oo = scorer.out_of_order(record["order_relations"], record["actions"], model)
        scores = {"missing_action": ma["score"], "incorrect_actor": ia["score"],
                  "out_of_order": oo["score"]}
        item_score = scores[item["check_type"]]
        predicted = item["check_type"] if (item_score is not None and item_score > 0.0) else None
        predictions.append({
            "schema_version": "stage3_prediction@1.0.0",
            "method_id": f"s36_{arm}",
            "run_id": _run_id(arm, config),
            "task": "violation",
            "item_id": item["item_id"],
            "process_id": item["process_id"],
            "rule_id": item["rule_id"],
            "matching_score": None,
            "predicted_relevance": None,
            "missing_action_score": round(ma["score"], 6),
            "incorrect_actor_score": round(ia["score"], 6) if ia["score"] is not None else None,
            "out_of_order_score": round(oo["score"], 6),
            "predicted_violation_type": predicted,
            "evidence": None,
            "threshold": gamma,
            "config_version": config["config_version"],
            "source_hashes": {"rule_record": item["rule_id"], "process_record": item["process_id"]},
            "method_provenance": f"s36_{arm} gamma={gamma} theta={theta}",
            "gold_visible": False,
            "check_type": item["check_type"],
            "incorrect_actor_observable": ia["observable"],
            "incorrect_actor_reason": ia.get("reason"),
        })
    return predictions, rule_records


def write_run(arm: str, config: dict[str, Any], variant: str) -> Path:
    run_dir = ROOT / "outputs" / "development" / f"s36_{arm}_stage3_development_{variant}"
    if run_dir.exists():
        raise RuntimeError(f"refusing to overwrite existing run dir: {run_dir}")
    run_dir.mkdir(parents=True)

    nlp = spacy.load("en_core_web_sm")
    signalwords = set((WINTER_FILES_DIR / "signalwords.txt").read_text(encoding="utf-8").splitlines())
    inference = _load_json(INFERENCE_PACK, "inference pack")
    membership = _load_json(MEMBERSHIP_CONTRACT, "membership contract")
    frozen_ids = [item["input_id"] for item in membership["membership"]["files"]]
    bpmn_ids = sorted(p.stem for p in BPMN_DIR.glob("*.bpmn"))
    inf_ids = sorted({i["process_id"] for i in inference["matching_items"]})
    if frozen_ids != bpmn_ids or frozen_ids != inf_ids:
        raise RuntimeError("input binding mismatch: membership vs bpmn files vs inference pack")

    models = build_sun_models(BPMN_DIR, STAGE1_CONTRACT, nlp)
    sim_factory = build_similarity(arm, config, models, nlp)
    tau = float(config["thresholds"]["tau"])
    gamma = float(config["thresholds"]["gamma"])
    theta = float(config["thresholds"]["theta"])
    scorer = BaselineScorer(sim_factory, tau, gamma, theta)
    predictions, rule_records = build_predictions(
        arm, config, sim_factory, nlp, signalwords, inference, models, scorer, tau, gamma, theta)

    config_snapshot = {
        "config_path": str(CONFIGS[arm].relative_to(ROOT).as_posix()),
        "config_sha256": _sha256(CONFIGS[arm]),
        "config": config,
    }
    (run_dir / "config_snapshot.json").write_text(
        json.dumps(config_snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "rule_records.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rule_records),
        encoding="utf-8")
    process_index = {
        "source": "canonical Process Record via stage1_structural_s11_s14.json parser",
        "process_ids": sorted(models),
        "bpmn_dir_aggregate_sha256": _dir_aggregate_sha256(BPMN_DIR),
        "membership_payload_sha256": membership["membership"]["membership_payload_sha256"],
    }
    (run_dir / "process_records.jsonl").write_text(
        json.dumps(process_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    predictions_path = run_dir / "predictions.jsonl"
    with predictions_path.open("w", encoding="utf-8") as f:
        for p in predictions:
            f.write(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n")

    manifest = {
        "schema_version": "stage3_baseline_run_manifest@1.0.0",
        "run_id": f"s36_{arm}_stage3_development_{variant}",
        "task_id": "S3.6",
        "arm": arm,
        "status": "development_only",
        "command": f"python scripts/run_stage3_baselines.py --arm {arm}"
                  + (f" --variant {variant}" if variant != "v1" else ""),
        "git": _git_state(),
        "inputs": {
            "inference_pack": {"path": str(INFERENCE_PACK.relative_to(ROOT).as_posix()),
                               "sha256": _sha256(INFERENCE_PACK),
                               "note": "gold-blind inference contract; runner never reads decisions/candidates"},
            "bpmn_dir": str(BPMN_DIR.relative_to(ROOT).as_posix()),
            "bpmn_dir_membership_payload_sha256": membership["membership"]["membership_payload_sha256"],
            "bpmn_dir_aggregate_sha256": _dir_aggregate_sha256(BPMN_DIR),
            "stage1_structural_contract": {"path": str(STAGE1_CONTRACT.relative_to(ROOT).as_posix()),
                                           "sha256": _sha256(STAGE1_CONTRACT)},
        },
        "method": config["method"],
        "thresholds": config["thresholds"],
        "samples": {
            "matching_candidates": sum(1 for p in predictions if p["task"] == "matching"),
            "violation_candidates": sum(1 for p in predictions if p["task"] == "violation"),
            "excluded": [],
        },
        "implementation_hashes": {
            "config": _sha256(CONFIGS[arm]),
            "runner": _sha256(Path(__file__)),
            "baseline_stage3": _sha256(ROOT / "src" / "bpc_hybrid" / "stage3_baselines" / "baseline_stage3.py"),
            "bm25": _sha256(ROOT / "src" / "bpc_hybrid" / "stage3_baselines" / "bm25.py"),
            "tfidf_svd": _sha256(ROOT / "src" / "bpc_hybrid" / "stage3_baselines" / "tfidf_svd.py"),
            "rule_adapter": _sha256(ROOT / "src" / "bpc_hybrid" / "sun_stage3" / "sun_rule_extraction.py"),
        },
        "dependency_index": {
            "python": sys.version.split()[0],
            "spacy": spacy.__version__,
            "spacy_model": "en_core_web_sm",
            "numpy": __import__("numpy").__version__,
            "sklearn": "unavailable (deterministic local implementations used)",
        },
        "external_runtime_prerequisites": [
            "spacy package + en_core_web_sm model (rule adapter only)",
            "references/winter_2020_model_check/model_check/input/files/signalwords.txt (read-only)",
        ],
        "safety": {
            "llm_api_called": False, "network_called": False, "env_read": False,
            "gold_decisions_read": False, "correction_pack_read": False,
            "candidate_fields_read": False, "bpmn_modified": False, "no_overwrite": True,
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
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return run_dir


def _dir_aggregate_sha256(directory: Path) -> str:
    import hashlib
    entries = {str(p.relative_to(directory).as_posix()): _sha256(p)
               for p in sorted(directory.glob("*.bpmn"))}
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True, choices=sorted(CONFIGS))
    parser.add_argument("--variant", default="v1")
    args = parser.parse_args()
    config = _load_json(CONFIGS[args.arm], f"{args.arm} config")
    try:
        run_dir = write_run(args.arm, config, args.variant)
        # common evaluator (matching tau sweep over fixed scores + error analysis)
        eval_script = ROOT / "scripts" / "evaluate_stage3_common.py"
        result = subprocess.run(
            [sys.executable, str(eval_script),
             "--predictions", str(run_dir / "predictions.jsonl"),
             "--run-dir", str(run_dir), "--sweep", "--error-analysis"],
            cwd=ROOT, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode != 0:
            raise RuntimeError("common evaluator failed:\n" + result.stdout[-600:])
        # baseline gamma/theta cutoff sweep (evaluation-side script reads Gold; runner does not)
        sens_script = ROOT / "scripts" / "baseline_stage3_sensitivity.py"
        result = subprocess.run(
            [sys.executable, str(sens_script), "--run-dir", str(run_dir)],
            cwd=ROOT, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode != 0:
            raise RuntimeError("baseline sensitivity failed:\n" + result.stdout[-600:])
        # finalise
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
        print(f"baseline run failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
