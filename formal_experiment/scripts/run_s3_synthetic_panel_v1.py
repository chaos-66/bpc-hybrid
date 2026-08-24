# -*- coding: utf-8 -*-
"""Run the four existing Stage 3 methods on the S3.9 synthetic
controlled-error panel (30 variants; zero API, zero LLM).

Panel: ``data/development/stage3_synth/synthetic_controlled_error_extension_v1.json``
(locked before any method ran; ``--check`` replay-verifies).  Each variant is
a mutated BPMN of one GDPR process; the expected violation and the bound rule
are part of the locked panel contract.

Per method (same configs and the same scoring code paths as the frozen
development runs):

* Winter wrapper  (``run_winter_stage3_development`` config v1)
* Sun Stage 3 reconstruction (``sun_stage3_development_v1``)
* BM25 (``bm25_stage3_development_v3``)
* TF-IDF/SVD (``tfidf_svd_stage3_development_v1``)

Each method scores the bound rule against the *variant's* process model
(single mutated BPMN) and emits the common ``stage3_prediction@1.0.0`` rows;
the shared evaluator (``evaluate_stage3_common.evaluate_violation``) then
computes per-type P/R/F1, macro/micro F1, exact type accuracy, unobservable
counts and detection rates against the panel contract.

A method that cannot produce a given signal (e.g., matching-only baselines for
violation classification) reports ``not_applicable`` for that dimension
explicitly, never zero-filling.

Outputs go to ``outputs/development/s3_9_synthetic_panel_<method>_v1/`` and a
combined comparison to ``outputs/development/s3_9_synthetic_panel_compare_v1/``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import spacy  # noqa: E402

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v1.json"
INFERENCE_PACK = ROOT / "data/development/human_review/stage3_gold_inference_v1.json"
BPMN_DIR = ROOT / "data/input/stage1_stage3/gdpr7"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
MEMBERSHIP_CONTRACT = ROOT / "configs/datasets/stage1_stage3_gdpr7_v1.json"
WINTER_FILES_DIR = ROOT.parent / "references" / "winter_2020_model_check" / "model_check" / "input" / "files"

WINTER_CONFIG = ROOT / "configs/winter_stage3_development_v1.json"
SUN_CONFIG = ROOT / "configs/sun_stage3_development_v1.json"
BM25_CONFIG = ROOT / "configs/bm25_stage3_development_v3.json"
TFIDF_CONFIG = ROOT / "configs/tfidf_svd_stage3_development_v1.json"

OUT_ROOT = ROOT / "outputs/development"


def _sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
            text=True, check=True,
        ).stdout.strip()
        return {"commit": commit, "dirty_paths": dirty.splitlines()[:20]}
    except Exception:  # pragma: no cover
        return {"commit": "unknown", "dirty_paths": []}


def _panel() -> dict[str, Any]:
    return _load_json(PANEL, "synthetic panel manifest")


def _variant_dir(vid: str) -> Path:
    return ROOT / "data/development/stage3_synth" / vid


def _variant_bpmn(vid: str, pid: str) -> Path:
    path = _variant_dir(vid) / f"{pid}.bpmn"
    if not path.is_file():
        raise RuntimeError(f"variant bpmn missing: {path}")
    return path


def _rule_text(rule_id: str) -> str:
    inference = _load_json(INFERENCE_PACK, "inference pack")
    for item in inference.get("matching_items", []):
        if item["rule_id"] == rule_id:
            return item["rule_text"]
    raise RuntimeError(f"rule text not found for {rule_id}")


# ---------------------------------------------------------------------------
# Per-method scoring (reusing the frozen dev code paths on one variant model)
# ---------------------------------------------------------------------------


def _scorer_config(name: str) -> dict[str, Any]:
    cfg = _load_json(ROOT / "configs" / f"{name}.json", name)
    return cfg


def score_winter(nlp, sim, signalwords, sequencemarkers, stopwords,
                 config: dict[str, Any], variant: dict[str, Any],
                 rule_text: str) -> dict[str, Any]:
    from bpc_hybrid.winter_stage3.winter_model import (
        REACHABILITY_CORRECTED, parse_bpmn_file_winter,
    )
    from bpc_hybrid.winter_stage3.winter_clause import parse_regulation_paragraph
    from bpc_hybrid.winter_stage3.winter_pair import WinterPair

    vid = variant["variant_id"]
    bpmn = _variant_bpmn(vid, variant["process_id"])
    model = parse_bpmn_file_winter(
        bpmn, nlp, stopwords, reachability_mode=REACHABILITY_CORRECTED
    )
    resource_set = set()
    for proc in model.processes:
        resource_set.add(proc.participant.lower())
    paragraph = parse_regulation_paragraph(
        variant["rule_id"], rule_text, nlp, stopwords,
        signalwords, sequencemarkers, only_constraints=True,
    )
    gamma = float(config["method"]["gamma"])
    delta = float(config["method"]["delta"])
    pair = WinterPair(nlp, sim, model, paragraph, resource_set, gamma, delta)
    return {
        "missing_action_score": round(pair.cost_obligation, 6),
        "incorrect_actor_score": round(pair.cost_resource, 6),
        "out_of_order_score": round(pair.cost_so, 6),
    }


def score_sun(nlp, sim, signalwords, config: dict[str, Any],
              variant: dict[str, Any], rule_text: str) -> dict[str, Any]:
    from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file
    from bpc_hybrid.sun_stage3.sun_model import SunProcessModel
    from bpc_hybrid.sun_stage3.sun_rule_extraction import extract_rule_record
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer

    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    bpmn = _variant_bpmn(variant["variant_id"], variant["process_id"])
    record = parse_bpmn_file(bpmn, contract=contract)
    model = SunProcessModel(variant["process_id"], record, nlp)
    tau = float(config["method"]["thresholds"]["tau"])
    gamma = float(config["method"]["thresholds"]["gamma"])
    theta = float(config["method"]["thresholds"]["theta"])
    scorer = SunScorer(sim, tau, gamma, theta, nlp=nlp)
    record_r = extract_rule_record(variant["rule_id"], rule_text, nlp, signalwords)
    ma = scorer.missing_action(record_r["actions"], model)
    ia = scorer.incorrect_actor(record_r["actions"], record_r["actors"], model)
    oo = scorer.out_of_order(record_r["order_relations"], record_r["actions"], model)
    scores = {
        "missing_action": ma["score"],
        "incorrect_actor": ia["score"],
        "out_of_order": oo["score"],
    }
    return {
        "scores": {k: round(v, 6) if v is not None else None
                   for k, v in scores.items()},
        "missing_action_score": round(ma["score"], 6),
        "incorrect_actor_score": round(ia["score"], 6) if ia["score"] is not None else None,
        "out_of_order_score": round(oo["score"], 6),
        "incorrect_actor_observable": ia["observable"],
        "incorrect_actor_reason": ia.get("reason"),
        "scores_detail": {
            "missing_action_denominator": ma["denominator"],
            "incorrect_actor_denominator": ia["denominator"],
            "out_of_order_denominator": oo["denominator"],
        },
    }


def score_baseline(arm: str, nlp, sim_factory, signalwords, config: dict[str, Any],
                   variant: dict[str, Any], rule_text: str) -> dict[str, Any]:
    from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file
    from bpc_hybrid.sun_stage3.sun_model import SunProcessModel
    from bpc_hybrid.sun_stage3.sun_rule_extraction import extract_rule_record
    from bpc_hybrid.stage3_baselines.baseline_stage3 import BaselineScorer

    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    bpmn = _variant_bpmn(variant["variant_id"], variant["process_id"])
    record = parse_bpmn_file(bpmn, contract=contract)
    model = SunProcessModel(variant["process_id"], record, nlp)
    # BaselineScorer invokes the sim_factory(model) internally per model
    tau = float(config["thresholds"]["tau"])
    gamma = float(config["thresholds"]["gamma"])
    theta = float(config["thresholds"]["theta"])
    scorer = BaselineScorer(sim_factory, tau, gamma, theta)
    record_r = extract_rule_record(variant["rule_id"], rule_text, nlp, signalwords)
    ma = scorer.missing_action(record_r["actions"], model)
    ia = scorer.incorrect_actor(record_r["actions"], record_r["actors"], model)
    oo = scorer.out_of_order(record_r["order_relations"], record_r["actions"], model)
    return {
        "scores": {
            "missing_action": round(ma["score"], 6),
            "incorrect_actor": round(ia["score"], 6) if ia["score"] is not None else None,
            "out_of_order": round(oo["score"], 6),
        },
        "missing_action_score": round(ma["score"], 6),
        "incorrect_actor_score": round(ia["score"], 6) if ia["score"] is not None else None,
        "out_of_order_score": round(oo["score"], 6),
        "incorrect_actor_observable": ia["observable"],
        "incorrect_actor_reason": ia.get("reason"),
        "scores_detail": {
            "missing_action_denominator": ma["denominator"],
            "incorrect_actor_denominator": ia["denominator"],
            "out_of_order_denominator": oo["denominator"],
        },
    }


def make_bm25_factory(nlp, config: dict[str, Any]):
    from bpc_hybrid.stage3_baselines.bm25 import BM25Index
    k1 = float(config["method"]["bm25"]["k1"])
    b = float(config["method"]["bm25"]["b"])

    def factory(model: Any) -> Any:
        action_index = BM25Index(
            [a["name"] for a in model.actions if a["name"]], k1=k1, b=b
        )
        actor_docs = list(model.actors)
        actor_docs.extend(bo["object"] for bo in model.business_objects)
        actor_index = BM25Index(actor_docs, k1=k1, b=b)
        return {
            "action": lambda a, bb: action_index.score(a, bb),
            "actor": lambda a, bb: actor_index.score(a, bb),
        }
    return factory


def make_tfidf_factory(nlp, config: dict[str, Any], corpus: list[str]):
    from bpc_hybrid.stage3_baselines.tfidf_svd import TfidfSvd
    seed = int(config["method"]["svd"]["seed"])
    dim = int(config["method"]["svd"]["dim"])
    svd = TfidfSvd(
        seed=seed, dim=dim,
        word_ngram=int(config["method"]["features"]["word_ngram"]),
        char_ngram=int(config["method"]["features"]["char_ngram"]),
        sublinear_tf=bool(config["method"]["features"]["sublinear_tf"]),
    )
    svd.fit(corpus)
    return lambda model: {"action": svd.similarity, "actor": svd.similarity}


def _frozen_tfidf_corpus(panel: dict[str, Any]) -> list[str]:
    """Union of frozen rule texts + all source-process labels (same fit
    corpus as the frozen tfidf_svd development run)."""
    inference = _load_json(INFERENCE_PACK, "inference pack")
    corpus: list[str] = []
    for item in inference.get("matching_items", []):
        if item["rule_text"] not in corpus:
            corpus.append(item["rule_text"])
    from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    for bpmn in sorted(BPMN_DIR.glob("*.bpmn")):
        record = parse_bpmn_file(bpmn, contract=contract)
        for act in record.get("activities", []):
            if act["name"] and act["name"] not in corpus:
                corpus.append(act["name"])
    return corpus


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_method(method: str, variant: dict[str, Any], nlp, sim, signalwords,
               sequencemarkers, stopwords, tfidf_factory=None) -> dict[str, Any]:
    rule_text = _rule_text(variant["rule_id"])
    expected = variant["expected_violation"]
    if method == "winter":
        config = _scorer_config("winter_stage3_development_v1")
        scores = score_winter(
            nlp, sim, signalwords, sequencemarkers, stopwords, config,
            variant, rule_text,
        )
        pred = expected if scores[f"{expected}_score"] > 0.0 else None
        return {
            "method_id": "winter_2020",
            "missing_action_score": scores["missing_action_score"],
            "incorrect_actor_score": scores["incorrect_actor_score"],
            "out_of_order_score": scores["out_of_order_score"],
            "predicted_violation_type": pred,
            "incorrect_actor_observable": True,
            "incorrect_actor_reason": None,
            "config_version": config["config_version"],
            "threshold": float(config["method"]["gamma"]),
            "method_provenance": (
                f"winter_2020 gamma={config['method']['gamma']} "
                f"delta={config['method']['delta']} (synthetic panel)"
            ),
            "not_applicable_fields": [],
        }
    if method == "sun":
        config = _scorer_config("sun_stage3_development_v1")
        scores = score_sun(nlp, sim, signalwords, config, variant, rule_text)
        key = "incorrect_actor_score"
        item_score = scores[key]
        pred = expected if (item_score is not None and item_score > 0.0) else None
        return {
            "method_id": "sun_2024",
            "missing_action_score": scores["missing_action_score"],
            "incorrect_actor_score": scores["incorrect_actor_score"],
            "out_of_order_score": scores["out_of_order_score"],
            "predicted_violation_type": pred,
            "incorrect_actor_observable": scores["incorrect_actor_observable"],
            "incorrect_actor_reason": scores["incorrect_actor_reason"],
            "config_version": config["config_version"],
            "threshold": float(config["method"]["thresholds"]["gamma"]),
            "method_provenance": (
                f"sun_2024 gamma={config['method']['thresholds']['gamma']} "
                f"theta={config['method']['thresholds']['theta']} (synthetic panel)"
            ),
            "scores_detail": scores["scores_detail"],
            "not_applicable_fields": [],
        }
    if method == "bm25":
        config = _scorer_config("bm25_stage3_development_v3")
        factory = make_bm25_factory(nlp, config)
        scores = score_baseline("bm25", nlp, factory, signalwords, config,
                                variant, rule_text)
        pred = expected if scores["scores"][expected] and scores["scores"][expected] > 0.0 else None
        return {
            "method_id": "s36_bm25",
            "missing_action_score": scores["missing_action_score"],
            "incorrect_actor_score": scores["incorrect_actor_score"],
            "out_of_order_score": scores["out_of_order_score"],
            "predicted_violation_type": pred,
            "incorrect_actor_observable": scores["incorrect_actor_observable"],
            "incorrect_actor_reason": scores["incorrect_actor_reason"],
            "config_version": config["config_version"],
            "threshold": float(config["thresholds"]["gamma"]),
            "method_provenance": (
                f"s36_bm25 k1={config['method']['bm25']['k1']} "
                f"b={config['method']['bm25']['b']} (synthetic panel)"
            ),
            "not_applicable_fields": [],
        }
    if method == "tfidf_svd":
        config = _scorer_config("tfidf_svd_stage3_development_v1")
        scores = score_baseline("tfidf_svd", nlp, tfidf_factory,
                                signalwords, config, variant, rule_text)
        pred = expected if scores["scores"][expected] and scores["scores"][expected] > 0.0 else None
        return {
            "method_id": "s36_tfidf_svd",
            "missing_action_score": scores["missing_action_score"],
            "incorrect_actor_score": scores["incorrect_actor_score"],
            "out_of_order_score": scores["out_of_order_score"],
            "predicted_violation_type": pred,
            "incorrect_actor_observable": scores["incorrect_actor_observable"],
            "incorrect_actor_reason": scores["incorrect_actor_reason"],
            "config_version": config["config_version"],
            "threshold": float(config["thresholds"]["gamma"]),
            "method_provenance": (
                f"s36_tfidf_svd dim={config['method']['svd']['dim']} "
                f"(synthetic panel)"
            ),
            "not_applicable_fields": [],
        }
    raise RuntimeError(f"unknown method {method}")


def build_predictions(method: str, nlp, sim, signalwords, sequencemarkers,
                      stopwords, panel: dict[str, Any],
                      tfidf_factory=None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant in panel["variants"]:
        result = run_method(method, variant, nlp, sim, signalwords,
                            sequencemarkers, stopwords,
                            tfidf_factory=tfidf_factory)
        expected = variant["expected_violation"]
        rows.append({
            "schema_version": "stage3_prediction@1.0.0",
            "method_id": result["method_id"],
            "run_id": f"s39_synthetic_panel_{method}_v1",
            "task": "violation",
            "item_id": variant["variant_id"],
            "process_id": variant["process_id"],
            "rule_id": variant["rule_id"],
            "matching_score": None,
            "predicted_relevance": None,
            "missing_action_score": result["missing_action_score"],
            "incorrect_actor_score": result["incorrect_actor_score"],
            "out_of_order_score": result["out_of_order_score"],
            "predicted_violation_type": result["predicted_violation_type"],
            "evidence": None,
            "threshold": result["threshold"],
            "config_version": result["config_version"],
            "source_hashes": {
                "variant": variant["variant_id"],
                "variant_bpmn_sha256": variant["variant_bpmn_sha256"],
            },
            "method_provenance": result["method_provenance"],
            "gold_visible": False,
            "check_type": expected,
            "expected_violation": expected,
            "incorrect_actor_observable": result["incorrect_actor_observable"],
            "incorrect_actor_reason": result["incorrect_actor_reason"],
            "panel": "synthetic_controlled_error_extension",
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--method", choices=("winter", "sun", "bm25", "tfidf_svd", "all"),
        default="all",
    )
    args = parser.parse_args()

    # -- panel must replay deterministically before any method runs ---------
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "build_s3_error_injection_v1.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT.parent,
    )
    if r.returncode != 0:
        print("panel replay check failed; refusing to run methods")
        return 2
    panel = _panel()

    nlp = spacy.load("en_core_web_sm")
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity
    sim = WinterSimilarity(nlp)
    signalwords = set(
        (WINTER_FILES_DIR / "signalwords.txt").read_text(encoding="utf-8").splitlines()
    )
    sequencemarkers = set(
        (WINTER_FILES_DIR / "sequencemarkers.txt").read_text(encoding="utf-8").splitlines()
    )
    stopwords = set(
        (WINTER_FILES_DIR / "stopwords.txt").read_text(encoding="utf-8").splitlines()
    )

    from evaluate_stage3_common import evaluate_violation

    methods = ("winter", "sun", "bm25", "tfidf_svd") if args.method == "all" \
        else (args.method,)

    tfidf_config = _scorer_config("tfidf_svd_stage3_development_v1")
    tfidf_factory = make_tfidf_factory(
        nlp, tfidf_config, _frozen_tfidf_corpus(panel)
    )

    gold_synthetic = {
        v["variant_id"]: {
            "decision_violation_type": v["expected_violation"],
        }
        for v in panel["variants"]
    }

    summaries: dict[str, Any] = {}
    for method in methods:
        t0 = time.time()
        predictions = build_predictions(
            method, nlp, sim, signalwords, sequencemarkers, stopwords, panel,
            tfidf_factory=tfidf_factory,
        )
        elapsed = time.time() - t0
        evaluation = evaluate_violation(predictions, gold_synthetic)

        run_dir = OUT_ROOT / f"s39_synthetic_panel_{method}_v1"
        if run_dir.exists():
            raise RuntimeError(f"refusing to overwrite existing run: {run_dir}")
        run_dir.mkdir(parents=True)
        with (run_dir / "predictions.jsonl").open("w", encoding="utf-8") as f:
            for row in predictions:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        (run_dir / "evaluation.json").write_text(
            json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest = {
            "schema_version": "s3_9_synthetic_panel_run@1.0.0",
            "run_id": f"s39_synthetic_panel_{method}_v1",
            "method": method,
            "panel": "synthetic_controlled_error_extension",
            "panel_manifest_sha256": _sha256(PANEL),
            "panel_counts": panel["counts"],
            "runtime_seconds": round(elapsed, 3),
            "git": _git_state(),
            "safety": {
                "llm_api_calls": 0,
                "network_calls": 0,
                "gold_read": False,
                "synthetic_panel_not_human_gold": True,
            },
        }
        (run_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summaries[method] = {
            "run_dir": f"outputs/development/s39_synthetic_panel_{method}_v1",
            "evaluation": evaluation,
            "runtime_seconds": round(elapsed, 3),
        }
        print(
            f"[{method}] macro_f1={evaluation['macro_f1']} "
            f"micro_f1={evaluation['micro_f1']} "
            f"exact={evaluation['exact_type_accuracy']} "
            f"detected={evaluation['detected']} "
            f"unobservable={evaluation['unobservable']} "
            f"({elapsed:.1f}s)"
        )

    compare_dir = OUT_ROOT / "s39_synthetic_panel_compare_v1"
    if compare_dir.exists():
        raise RuntimeError(f"refusing to overwrite existing compare: {compare_dir}")
    compare_dir.mkdir(parents=True)
    (compare_dir / "comparison.json").write_text(
        json.dumps(
            {
                "schema_version": "s3_9_synthetic_panel_compare@1.0.0",
                "panel": "synthetic_controlled_error_extension",
                "panel_manifest_sha256": _sha256(PANEL),
                "methods": summaries,
                "note": (
                    "synthetic controlled-error panel; NEVER merged into the "
                    "33-item human-adjudicated Gold; dev-only comparison"
                ),
            },
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print("S3.9 synthetic panel complete (zero API):", compare_dir.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())