# -*- coding: utf-8 -*-
""""原三类衔接" -- Stage-2 -> Stage-3 offline error-propagation run (v1).

Substitutes the Rule-Record source of the FROZEN Sun-style Stage-3 detector
(S3.5 development pipeline, ``configs/sun_stage3_development_v1.json``
thresholds tau=gamma=theta=0.8, ``src/bpc_hybrid/sun_stage3/sun_scorer.py``)
with the EXTERNAL Rules-Only Stage-2 predictions capsule
(``data/predictions/gdpr7_sun_rule_only_v1``) over the same 9 GDPR rule
texts, and evaluates the three ORIGINAL violation types (missing_action /
incorrect_actor / out_of_order) on the frozen 33-item human-adjudicated
violation-decision Gold (``data/gold/stage3/stage3_violation_gold_v1.json``,
items v001..v033).

Two arms, run one at a time (``--arm``):
- ``reference`` : the original S3.5 development behavior -- the dev Rule
  Record adapter (``sun_rule_extraction.extract_rule_record``) is fed the
  frozen inference-pack rule texts. Reference rows replicate the S3.5 dev
  run on the same 33 violation items.
- ``rules_only`` : the deterministic capsule converter
  (``bpc_hybrid.sun_stage3.gdpr_capsule_converter``) builds the SAME
  rule-record shape (actions/actors/order_relations) from the external
  Rules-Only capsule. Failed/empty envelopes are counted with reasons and
  never back-filled; order relations are absent in the frozen capsule and
  are never fabricated.

Evaluation formulas and observability policy are the S3.5 common evaluator's
(``scripts/evaluate_stage3_common.evaluate_violation``), reused verbatim.
Gold decisions enter ONLY after the predictions rows are fixed and written.

Separations: the 33-item Gold, the 4-type synthetic panel and the formal
Oracle are separate datasets and are never merged.

Usage:
    python scripts/run_gdpr_3type_linkage_v1.py --arm {reference,rules_only}
    python scripts/run_gdpr_3type_linkage_v1.py --report-only <run_dir>
    python scripts/run_gdpr_3type_linkage_v1.py --compare
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for p in (SRC, SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import spacy  # noqa: E402

from bpc_hybrid.sun_stage3.gdpr_capsule_converter import (  # noqa: E402
    CONVERTER_NAME,
    build_rule_records,
)
from bpc_hybrid.sun_stage3.sun_model import build_sun_models  # noqa: E402
from bpc_hybrid.sun_stage3.sun_rule_extraction import extract_rule_record  # noqa: E402
from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402
from evaluate_stage3_common import evaluate_violation  # noqa: E402

RUN_ID_PREFIX = "gdpr_3type_linkage_v1"
ARM_LABELS = {
    "reference": "S3.5 development Rule Record adapter (deterministic spaCy + signalwords)",
    "rules_only": "EXTERNAL Rules-Only Stage-2 capsule (locked B0 v10a) via deterministic converter",
}
EXPECTED_INFERENCE_SHA = "4182c1f6ba8e28665c6dd14a2573b227e0c6b65c1df0041fcd1ae7dab5cf03c4"
CAPSULE_SCHEMA = "gdpr7_sun_rule_only_predictions@1.0.0"

CONFIG = ROOT / "configs" / "sun_stage3_development_v1.json"
STAGE1_CONTRACT = ROOT / "configs" / "stage1_structural_s11_s14.json"
BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"
INFERENCE_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_inference_v1.json"
INPUT_PACK = ROOT / "data" / "input" / "gdpr7_stage2_input_v1.json"
GOLD_VIOLATION = ROOT / "data" / "gold" / "stage3" / "stage3_violation_gold_v1.json"
CAPSULE_DIR = ROOT / "data" / "predictions" / "gdpr7_sun_rule_only_v1"
CAPSULE_PREDICTIONS = CAPSULE_DIR / "predictions.json"
CAPSULE_MANIFEST = CAPSULE_DIR / "manifest.json"
WINTER_FILES_DIR = ROOT.parent / "references" / "winter_2020_model_check" / "model_check" / "input" / "files"

OUTPUT_ROOT = ROOT / "outputs" / "development"
REPORT_ROOT = ROOT / "outputs" / "reports"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"{label} missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _git_state() -> dict[str, Any]:
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


def load_frozen(config: Mapping[str, Any]) -> dict[str, Any]:
    """Load the frozen run-time objects and inputs shared by both arms."""
    inference = _load_json(INFERENCE_PACK, "inference pack")
    if not isinstance(inference, dict):
        raise RuntimeError("inference pack root must be an object")
    inference_sha = _sha256(INFERENCE_PACK)
    if inference_sha != EXPECTED_INFERENCE_SHA:
        raise RuntimeError(
            f"inference pack hash drift: got {inference_sha}, "
            f"expected {EXPECTED_INFERENCE_SHA}")
    input_doc = _load_json(INPUT_PACK, "GDPR Stage-2 input")
    tau = float(config["method"]["thresholds"]["tau"])
    gamma = float(config["method"]["thresholds"]["gamma"])
    theta = float(config["method"]["thresholds"]["theta"])
    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    signalwords = set(
        (WINTER_FILES_DIR / "signalwords.txt").read_text(encoding="utf-8").splitlines())
    scorer = SunScorer(sim, tau, gamma, theta, nlp=nlp)
    models = build_sun_models(BPMN_DIR, STAGE1_CONTRACT, nlp)
    return {
        "inference": inference,
        "inference_sha": inference_sha,
        "input_doc": input_doc,
        "tau": tau,
        "gamma": gamma,
        "theta": theta,
        "nlp": nlp,
        "scorer": scorer,
        "models": models,
        "signalwords": signalwords,
    }


def rule_texts_of(inference: Mapping[str, Any]) -> dict[str, str]:
    """rule_id -> rule_text. Every rule's text is identical across items
    (verified at build time); a drift is a contract error."""
    per_rule: dict[str, set[str]] = {}
    for item in list(inference.get("matching_items", [])) + list(inference.get("violation_items", [])):
        per_rule.setdefault(item["rule_id"], set()).add(item["rule_text"])
    out: dict[str, str] = {}
    for rule_id, texts in per_rule.items():
        if len(texts) != 1:
            raise RuntimeError(f"rule_text drift inside rule_id {rule_id}: {len(texts)} unique texts")
        out[rule_id] = next(iter(texts))
    return out


def build_rule_records_for_arm(arm: str, frozen: Mapping[str, Any],
                               rule_ids: Sequence[str],
                               predictions_path: Path | None,
                               ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Arm-specific rule records + per-arm diagnostics (never reads Gold)."""
    rule_texts = rule_texts_of(frozen["inference"])
    if arm == "reference":
        records: dict[str, dict[str, Any]] = {}
        for rule_id in rule_ids:
            records[rule_id] = extract_rule_record(
                rule_id, rule_texts[rule_id], frozen["nlp"], frozen["signalwords"])
        diag: dict[str, Any] = {
            "rule_record_source": "development Sun Rule Record adapter "
                                  "(sun_rule_extraction.extract_rule_record)",
            "capsule_used": False,
            "failed_rules": [],
            "rule_action_counts": {rid: len(records[rid]["actions"]) for rid in rule_ids},
            "rule_actor_counts": {rid: len(records[rid]["actors"]) for rid in rule_ids},
            "rule_order_relation_counts": {rid: len(records[rid]["order_relations"]) for rid in rule_ids},
        }
        return records, diag

    # rules_only arm -----------------------------------------------------
    if predictions_path is None:
        predictions_path = CAPSULE_PREDICTIONS
    capsule = _load_json(predictions_path, "Rules-Only capsule predictions")
    if capsule.get("schema_version") != CAPSULE_SCHEMA:
        raise RuntimeError(
            f"Rules-Only capsule schema mismatch: got {capsule.get('schema_version')!r}, "
            f"expected {CAPSULE_SCHEMA!r}")
    if not CAPSULE_MANIFEST.is_file():
        raise FileNotFoundError(f"Rules-Only capsule manifest missing: {CAPSULE_MANIFEST}")
    from bpc_hybrid.sun_stage3.gdpr_capsule_converter import sentence_texts_by_sample
    texts = sentence_texts_by_sample(frozen["input_doc"])
    records, summary = build_rule_records(capsule, texts, rule_ids)
    diag = {
        "rule_record_source": f"EXTERNAL Rules-Only capsule converter ({CONVERTER_NAME})",
        "capsule_used": True,
        "capsule_path": _rel(predictions_path),
        "capsule_sha256": _sha256(predictions_path),
        "capsule_schema": capsule.get("schema_version"),
        "capsule_record_count": capsule.get("record_count"),
        "capsule_manifest_path": _rel(CAPSULE_MANIFEST),
        "capsule_manifest_exists": True,
        "conversion_summary": summary,
        "failed_rules": [rid for rid in rule_ids if records[rid].get("failed")],
    }
    return records, diag


def build_violation_rows(arm: str, frozen: Mapping[str, Any],
                         rule_records: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Frozen Sun scoring over the 33 violation items. Gold-blind: reads only
    inference-pack item ids/check_type/rule_text-free records plus the frozen
    process models. Predictions are fixed here before Gold is ever opened."""
    config = _load_json(CONFIG, "sun stage3 config")
    inference = frozen["inference"]
    violation_items = sorted(inference["violation_items"], key=lambda i: i["item_id"])
    rows: list[dict[str, Any]] = []
    for item in violation_items:
        process_id = item["process_id"]
        rule_id = item["rule_id"]
        check_type = item["check_type"]
        record = rule_records[rule_id]
        model = frozen["models"][process_id]
        scorer = frozen["scorer"]
        gamma = frozen["gamma"]
        theta = frozen["theta"]
        failed = bool(record.get("failed"))
        external_failure = ";".join(record.get("failure_reasons") or []) or None
        if failed:
            row = _failed_row(arm, item, rule_id, check_type, external_failure)
            rows.append(row)
            continue
        ma = scorer.missing_action(record["actions"], model)
        ia = scorer.incorrect_actor(record["actions"], record["actors"], model, record.get("actor_action_pairs"))
        oo = scorer.out_of_order(record["order_relations"], record["actions"], model)
        scores = {
            "missing_action": ma["score"],
            "incorrect_actor": ia["score"],
            "out_of_order": oo["score"],
        }
        item_score = scores[check_type]
        predicted = check_type if (item_score is not None and item_score > 0.0) else None
        rows.append({
            "schema_version": "stage3_prediction@1.0.0",
            "method_id": "sun_2024",
            "run_id": f"{RUN_ID_PREFIX}_{arm}",
            "task": "violation",
            "item_id": item["item_id"],
            "process_id": process_id,
            "rule_id": rule_id,
            "check_type": check_type,
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
            "method_provenance": (
                f"sun_2024 Def5-7 gamma={gamma} theta={theta}; arm={arm}; "
                f"rule_record_source={ARM_LABELS[arm]}"
            ),
            "gold_visible": False,
            "external_arm": arm,
            "external_failure": None,
            "rule_record_failed": False,
            "incorrect_actor_observable": ia["observable"],
            "incorrect_actor_reason": ia.get("reason"),
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
    return rows


def _failed_row(arm: str, item: Mapping[str, Any], rule_id: str, check_type: str,
                external_failure: str | None) -> dict[str, Any]:
    """Explicit failure row: nothing scored, nothing fabricated, item stays in
    the denominator (predicted=None counts as FN in the evaluator)."""
    return {
        "schema_version": "stage3_prediction@1.0.0",
        "method_id": "sun_2024",
        "run_id": f"{RUN_ID_PREFIX}_{arm}",
        "task": "violation",
        "item_id": item["item_id"],
        "process_id": item["process_id"],
        "rule_id": rule_id,
        "check_type": check_type,
        "matching_score": None,
        "predicted_relevance": None,
        "missing_action_score": None,
        "incorrect_actor_score": None,
        "out_of_order_score": None,
        "predicted_violation_type": None,
        "evidence": None,
        "threshold": None,
        "config_version": None,
        "source_hashes": {"rule_record": rule_id, "process_record": item["process_id"]},
        "method_provenance": (
            f"sun_2024 Def5-7 NOT SCORED: rule record failed; arm={arm}; "
            f"rule_record_source={ARM_LABELS[arm]}"
        ),
        "gold_visible": False,
        "external_arm": arm,
        "external_failure": external_failure,
        "rule_record_failed": True,
        "incorrect_actor_observable": False,
        "incorrect_actor_reason": f"external_stage2_failure:{external_failure}",
        "scores": {
            "missing_action": None,
            "incorrect_actor": None,
            "out_of_order": None,
            "missing_action_denominator": None,
            "incorrect_actor_denominator": None,
            "incorrect_actor_observable": False,
            "incorrect_actor_reason": f"external_stage2_failure:{external_failure}",
            "out_of_order_denominator": None,
        },
    }


def evaluate_rows(rows: Sequence[Mapping[str, Any]], gold_path: Path) -> dict[str, Any]:
    """Gold ONLY enters here, after predictions are fixed and persisted.
    Reuses the S3.5 common evaluator formulas verbatim."""
    gold_doc = _load_json(gold_path, "33-item violation Gold")
    gold = {i["item_id"]: {"decision_violation_type": i["decision_violation_type"]}
            for i in gold_doc["items"]}
    missing = sorted({r["item_id"] for r in rows} - set(gold))
    if missing:
        raise RuntimeError(f"gold lacks items present in predictions: {missing}")
    violation = evaluate_violation(list(rows), gold)
    item_rows = []
    for row in sorted(rows, key=lambda r: r["item_id"]):
        g = gold[row["item_id"]]["decision_violation_type"]
        pred = row.get("predicted_violation_type")
        raw_scores = row.get("scores") or {}
        item_rows.append({
            "item_id": row["item_id"],
            "process_id": row["process_id"],
            "rule_id": row["rule_id"],
            "check_type": row.get("check_type"),
            "gold_type": g,
            "predicted_type": pred,
            "correct": pred == g,
            "external_failure": row.get("external_failure"),
            "rule_record_failed": row.get("rule_record_failed", False),
            "incorrect_actor_observable": row.get("incorrect_actor_observable"),
            "incorrect_actor_reason": row.get("incorrect_actor_reason"),
            "scores": {k: raw_scores[k] for k in sorted(raw_scores)},
        })
    return {
        "schema_version": "gdpr_3type_linkage_evaluation@1.0.0",
        "gold": {"path": _rel(gold_path), "sha256": _sha256(gold_path),
                 "dataset_id": gold_doc.get("dataset_id"),
                 "count": gold_doc.get("count")},
        "violation": violation,
        "items": item_rows,
    }


def run_arm(arm: str, *, output_root: Path | None = None,
            report_root: Path | None = None, overwrite: bool = False,
            gold_path: Path | None = None,
            predictions_path: Path | None = None) -> dict[str, Any]:
    if arm not in ARM_LABELS:
        raise ValueError(f"unknown arm {arm!r}; expected {sorted(ARM_LABELS)}")
    config = _load_json(CONFIG, "sun stage3 config")
    frozen = load_frozen(config)
    inference = frozen["inference"]
    matching_items = sorted(inference["matching_items"], key=lambda i: i["item_id"])
    violation_items = sorted(inference["violation_items"], key=lambda i: i["item_id"])
    rule_ids = sorted({i["rule_id"] for i in violation_items})
    if len(matching_items) != 25 or len(violation_items) != 33:
        raise RuntimeError(
            f"inference pack size drift: matching={len(matching_items)} violation={len(violation_items)}")
    if len(rule_ids) != 9:
        raise RuntimeError(f"expected 9 distinct rules, got {rule_ids}")

    run_dir = (output_root or OUTPUT_ROOT) / f"{RUN_ID_PREFIX}_{arm}"
    if run_dir.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing run dir: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    rule_records, arm_diag = build_rule_records_for_arm(
        arm, frozen, rule_ids, predictions_path)
    rows = build_violation_rows(arm, frozen, rule_records)
    if len(rows) != 33:
        raise RuntimeError(f"expected 33 violation rows, got {len(rows)}")
    predictions_path_out = run_dir / "predictions.jsonl"
    predictions_path_out.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8")
    rule_records_path = run_dir / "rule_records.jsonl"
    rule_records_path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                for r in (rule_records[rid] for rid in rule_ids)),
        encoding="utf-8")

    # -------- evaluation (Gold now allowed: predictions are already fixed)
    gold = gold_path or GOLD_VIOLATION
    evaluation = evaluate_rows(rows, gold)
    evaluation["thresholds"] = {
        "tau": frozen["tau"], "gamma": frozen["gamma"], "theta": frozen["theta"],
        "source_config": str(CONFIG.relative_to(ROOT).as_posix()),
    }

    failed_rows = [r for r in rows if r.get("rule_record_failed")]
    capsule_failures = {
        "failed_row_count": len(failed_rows),
        "failed_item_ids": [r["item_id"] for r in failed_rows],
        "failure_reasons": sorted({r["external_failure"] for r in failed_rows if r.get("external_failure")}),
    }
    evaluation["external_diagnostics"] = arm_diag
    evaluation["capsule_failure_accounting"] = capsule_failures
    evaluation_path = run_dir / "evaluation.json"
    evaluation_path.write_bytes(_json_bytes(evaluation))

    manifest = _build_manifest(arm, config, run_dir, arm_diag, capsule_failures,
                               rows, matching_items, violation_items,
                               gold, frozen, predictions_path,
                               rule_records_path, evaluation_path,
                               predictions_path_out)
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_bytes(_json_bytes(manifest))
    finalise_manifest(run_dir)

    summary = {
        "run_id": f"{RUN_ID_PREFIX}_{arm}",
        "arm": arm,
        "arm_label": ARM_LABELS[arm],
        "run_dir": _rel(run_dir),
        "evaluation": evaluation,
        "manifest": json.loads(manifest_path.read_text(encoding="utf-8")),
    }
    report_json = write_report(arm, summary, report_root, overwrite=overwrite)
    summary["report_json"] = _rel(report_json)
    summary["report_md"] = _rel(report_json.with_suffix(".md"))
    return summary


def _build_manifest(arm, config, run_dir, arm_diag, capsule_failures,
                    rows, matching_items, violation_items, gold_path, frozen,
                    predictions_path, rule_records_path, evaluation_path,
                    predictions_path_out) -> dict[str, Any]:
    config_snapshot = {
        "config_path": str(CONFIG.relative_to(ROOT).as_posix()),
        "config_sha256": _sha256(CONFIG),
        "config": config,
    }
    (run_dir / "config_snapshot.json").write_bytes(_json_bytes(config_snapshot))
    module_hashes = {
        "runner": _sha256(Path(__file__)),
        "converter": _sha256(ROOT / "src" / "bpc_hybrid" / "sun_stage3" / "gdpr_capsule_converter.py"),
        "sun_scorer": _sha256(ROOT / "src" / "bpc_hybrid" / "sun_stage3" / "sun_scorer.py"),
        "sun_rule_extraction": _sha256(ROOT / "src" / "bpc_hybrid" / "sun_stage3" / "sun_rule_extraction.py"),
        "sun_model": _sha256(ROOT / "src" / "bpc_hybrid" / "sun_stage3" / "sun_model.py"),
        "shared_similarity": _sha256(ROOT / "src" / "bpc_hybrid" / "winter_stage3" / "winter_similarity.py"),
    }
    capsule_block = None
    if arm == "rules_only":
        capsule_block = {
            "path": _rel(predictions_path or CAPSULE_PREDICTIONS),
            "sha256": _sha256(predictions_path or CAPSULE_PREDICTIONS),
            "schema": CAPSULE_SCHEMA,
            "record_count": arm_diag.get("capsule_record_count"),
            "manifest_path": _rel(CAPSULE_MANIFEST),
            "manifest_sha256": _sha256(CAPSULE_MANIFEST),
            "manifest_exists": True,
            "note": "EXTERNAL Stage-2 predictions; produced offline by run_gdpr7_sun_rule_only_v1.py (locked B0 v10a); NOT rerun by this experiment",
        }
    manifest = {
        "schema_version": "gdpr_3type_linkage_run_manifest@1.0.0",
        "run_id": f"{RUN_ID_PREFIX}_{arm}",
        "task_id": "S2->S3 linkage (original three violation types, dev)",
        "status": "development_only",
        "command": "python scripts/run_gdpr_3type_linkage_v1.py --arm " + arm,
        "git": _git_state(),
        "arm": arm,
        "arm_label": ARM_LABELS[arm],
        "thresholds": {
            "tau": frozen["tau"],
            "gamma": frozen["gamma"],
            "theta": frozen["theta"],
            "source_config": str(CONFIG.relative_to(ROOT).as_posix()),
        },
        "inputs": {
            "inference_pack": {
                "path": str(INFERENCE_PACK.relative_to(ROOT).as_posix()),
                "sha256": frozen["inference_sha"],
                "expected_sha256": EXPECTED_INFERENCE_SHA,
                "hash_verified": frozen["inference_sha"] == EXPECTED_INFERENCE_SHA,
            },
            "input_pack": {"path": str(INPUT_PACK.relative_to(ROOT).as_posix()),
                           "sha256": _sha256(INPUT_PACK)},
            "violation_gold": {"path": _rel(gold_path), "sha256": _sha256(gold_path),
                               "read_only_evaluation_after_predictions_fixed": True},
            "stage1_structural_contract": {
                "path": str(STAGE1_CONTRACT.relative_to(ROOT).as_posix()),
                "sha256": _sha256(STAGE1_CONTRACT)},
            "bpmn_dir": str(BPMN_DIR.relative_to(ROOT).as_posix()),
            "bpmn_files": {_rel(p): _sha256(p) for p in sorted(BPMN_DIR.glob("*.bpmn"))},
            "signalwords": {"path": _rel(WINTER_FILES_DIR / "signalwords.txt"),
                            "sha256": _sha256(WINTER_FILES_DIR / "signalwords.txt")},
            "rule_record_source": arm_diag["rule_record_source"],
        },
        "external_stage2": capsule_block,
        "samples": {
            "loaded_matching_items": len(matching_items),
            "loaded_violation_items": len(violation_items),
            "scored_violation_rows": len(rows),
            "scored_item_ids": [r["item_id"] for r in rows],
        },
        "implementation_hashes": module_hashes,
        "rule_record_diagnostics": arm_diag,
        "capsule_failure_accounting": capsule_failures,
        "observability_policy": (
            "common evaluator policy: unobservable applies only to incorrect_actor "
            "check points; unobservable/missing/failed items keep predicted=None "
            "and count as FN in the primary macro/micro/exact denominators; "
            "failed external envelopes are counted with explicit reasons, never "
            "dropped and never treated as compliant"
        ),
        "safety": {
            "llm_api_called": False,
            "network_called": False,
            "env_read": False,
            "gold_decisions_read_during_prediction": False,
            "gold_read_only_for_evaluation": True,
            "gold_modified": False,
            "stage2_rerun": False,
            "no_overwrite_default": True,
        },
        "artifacts": {
            "predictions": {"path": "predictions.jsonl",
                            "sha256": _sha256(predictions_path_out)},
            "rule_records": {"path": "rule_records.jsonl",
                             "sha256": _sha256(rule_records_path)},
            "evaluation": {"path": "evaluation.json",
                           "sha256": _sha256(evaluation_path)},
            "config_snapshot": {"path": "config_snapshot.json",
                                "sha256": _sha256(run_dir / "config_snapshot.json")},
        },
        "finalised": False,
    }
    return manifest


def finalise_manifest(run_dir: Path) -> None:
    """Fill artifact byte sizes/hashes and mark the manifest finalised. Reads
    back the written manifest so the recorded hashes are the persisted ones."""
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in ("predictions", "rule_records", "evaluation", "config_snapshot"):
        fname = manifest["artifacts"][name]["path"]
        manifest["artifacts"][name]["sha256"] = _sha256(run_dir / fname)
        manifest["artifacts"][name]["byte_size"] = (run_dir / fname).stat().st_size
    manifest["finalised"] = True
    manifest_path.write_bytes(_json_bytes(manifest))


# --------------------------------------------------------------- reporting
def _fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def _fmt_thresholds(t: Any) -> str:
    if not t:
        return "n/a (replay without manifest)"
    return f"tau={t.get('tau')}, gamma={t.get('gamma')}, theta={t.get('theta')}"


def render_markdown(summary: Mapping[str, Any]) -> str:
    arm = summary["arm"]
    ev = summary["evaluation"]["violation"]
    lines = [
        f"# GDPR Stage-2 -> Stage-3 linkage v1 (original three violation types) — arm `{arm}` (development-only)",
        "",
        f"- Arm rule-record source: {ARM_LABELS[arm]}",
        f"- Scored: {ev['support']} violation items (v001..v033) from the frozen inference pack; "
        f"loaded matching items: 25; 33-item violation Gold is read ONLY after predictions were fixed.",
        f"- Frozen Sun-style thresholds: tau/gamma/theta = "
        f"{_fmt_thresholds(summary['evaluation'].get('thresholds'))}",
        "",
        "## Per-type P/R/F1 (primary denominator keeps every item)",
        "",
        "| type | support | precision | recall | F1 |",
        "|---|---:|---:|---:|---:|",
    ]
    for t in ("missing_action", "incorrect_actor", "out_of_order"):
        pt = ev["per_type"][t]
        lines.append(f"| {t} | {pt['support']} | {_fmt(pt['precision'])} | "
                     f"{_fmt(pt['recall'])} | {_fmt(pt['f1'])} |")
    lines += [
        "",
        f"- macro-F1 = {_fmt(ev['macro_f1'])}  ·  micro-F1 = {_fmt(ev['micro_f1'])}  ·  "
        f"exact type accuracy = {_fmt(ev['exact_type_accuracy'])}  "
        f"(detected {ev['detected']} / missed {ev['missed']} / wrong-type {ev['wrong_type']})",
        f"- unobservable = {ev['unobservable']} (by reason: "
        f"{ev['denominator'].get('unobservable_by_reason')})",
        f"- observable-only diagnostic macro-F1 = {_fmt(ev['observable_only_macro_f1'])} "
        f"(NOT the primary metric)",
        "",
        "## External Stage-2 accounting",
        "",
    ]
    ext = summary["evaluation"].get("external_diagnostics") or {}
    if summary["arm"] == "rules_only":
        cs = ext.get("conversion_summary") or {}
        lines.append(f"- capsule records: {cs.get('capsule_records')}; "
                     f"envelopes ok {cs.get('total_envelopes_ok')} / failed "
                     f"{cs.get('total_envelopes_failed')}; "
                     f"failure reasons {cs.get('failure_reasons') or 'none'}; "
                     f"invalid spans {cs.get('total_invalid_spans')}.")
        lines.append(f"- order relations absent in capsule for rules: "
                     f"{cs.get('order_relations_absent_rules') or 'none'} "
                     f"(Definition-7 input unavailable by contract; never fabricated).")
        cap = summary["evaluation"].get("capsule_failure_accounting") or {}
        lines.append(f"- item-level failure rows: {cap.get('failed_row_count')} "
                     f"({', '.join(cap.get('failed_item_ids') or []) or 'none'}).")
    else:
        lines.append("- Reference arm: no external capsule; the development Rule Record "
                     "adapter output is stored per rule in rule_records.jsonl.")
    lines += [
        "",
        "## Boundaries",
        "",
        "- DEV_ONLY linkage on the frozen 33-item human-adjudicated violation Gold "
        "(original three types). The 4-type synthetic panel and the formal Oracle "
        "are separate datasets and are never merged here.",
        "- External Rules-Only capsule = locked B0 v10a pipeline (English pass-through, "
        "classifier German-language contract); zero LLM/API/network in this experiment.",
        "- Out-of-order in the reference arm is also denominator-0 for all items "
        "(no rule endpoint maps to a process action above gamma 0.8); in the rules_only "
        "arm the capsule provides no order relations at all.",
        "- Item-level rows: predictions.jsonl; per-item evaluation detail in "
        "evaluation.json (items).",
    ]
    return "\n".join(lines) + "\n"


def write_report(arm: str, summary: Mapping[str, Any],
                 report_root: Path | None = None,
                 overwrite: bool = False) -> Path:
    report_root = report_root or REPORT_ROOT
    report_root.mkdir(parents=True, exist_ok=True)
    report_json = report_root / f"{RUN_ID_PREFIX}_{arm}.json"
    if report_json.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing report: {report_json}")
    report_payload = {
        "schema_version": "gdpr_3type_linkage_report@1.0.0",
        "report_id": f"{RUN_ID_PREFIX}_{arm}",
        "arm": arm,
        "arm_label": ARM_LABELS[arm],
        "thresholds": summary["evaluation"].get("thresholds"),
        "evaluation": summary["evaluation"]["violation"],
        "external_diagnostics": summary["evaluation"].get("external_diagnostics"),
        "capsule_failure_accounting": summary["evaluation"].get("capsule_failure_accounting"),
        "run_dir": summary["run_dir"],
        "generated_deterministic": True,
    }
    report_json.write_bytes(_json_bytes(report_payload))
    report_md = report_json.with_suffix(".md")
    report_md.write_text(render_markdown(summary), encoding="utf-8")
    return report_json


# ------------------------------------------------------- replay + compare
def report_only(run_dir: Path, report_root: Path | None = None,
                gold_path: Path | None = None,
                overwrite: bool = False) -> dict[str, Any]:
    """Replay evaluation + report from persisted prediction rows only (no
    scoring, no overwrite of predictions.jsonl)."""
    run_dir = Path(run_dir)
    predictions_path = run_dir / "predictions.jsonl"
    if not predictions_path.is_file():
        raise FileNotFoundError(f"no persisted rows in {run_dir}")
    rows = [json.loads(line) for line in
            predictions_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 33:
        raise RuntimeError(f"expected 33 rows, got {len(rows)}")
    arm = rows[0].get("external_arm")
    if arm not in ARM_LABELS:
        raise RuntimeError(f"cannot infer arm from rows: {arm}")
    gold = gold_path or GOLD_VIOLATION
    evaluation = evaluate_rows(rows, gold)
    manifest: dict[str, Any] = {}
    manifest_path = run_dir / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        evaluation["thresholds"] = {
            "tau": manifest["thresholds"]["tau"],
            "gamma": manifest["thresholds"]["gamma"],
            "theta": manifest["thresholds"]["theta"],
            "source_config": manifest["thresholds"].get("source_config"),
        }
        evaluation["external_diagnostics"] = manifest.get("rule_record_diagnostics")
        evaluation["capsule_failure_accounting"] = manifest.get("capsule_failure_accounting")
    (run_dir / "evaluation.json").write_bytes(_json_bytes(evaluation))
    summary = {
        "run_id": f"{RUN_ID_PREFIX}_{arm}",
        "arm": arm,
        "arm_label": ARM_LABELS[arm],
        "run_dir": _rel(run_dir),
        "evaluation": evaluation,
        "manifest": manifest,
    }
    report_json = write_report(arm, summary, report_root, overwrite=overwrite)
    summary["report_json"] = _rel(report_json)
    summary["report_md"] = _rel(report_json.with_suffix(".md"))
    return summary


def compare_arms(output_root: Path | None = None,
                 report_root: Path | None = None,
                 overwrite: bool = False) -> dict[str, Any]:
    """Per-item change list between the reference and rules_only arms."""
    output_root = output_root or OUTPUT_ROOT
    ref_dir = output_root / f"{RUN_ID_PREFIX}_reference"
    ro_dir = output_root / f"{RUN_ID_PREFIX}_rules_only"
    for d in (ref_dir, ro_dir):
        if not (d / "predictions.jsonl").is_file():
            raise FileNotFoundError(f"missing persisted arm rows for comparison: {d}")
    ref_rows = {r["item_id"]: r for r in _read_rows(ref_dir)}
    ro_rows = {r["item_id"]: r for r in _read_rows(ro_dir)}
    changes: list[dict[str, Any]] = []
    same_verdict = 0
    for item_id in sorted(ref_rows):
        ref = ref_rows[item_id]
        arm = ro_rows[item_id]
        verdict_change = ref["predicted_violation_type"] != arm["predicted_violation_type"]
        ref_ia_obs = (ref["incorrect_actor_observable"], ref.get("incorrect_actor_reason"))
        arm_ia_obs = (arm["incorrect_actor_observable"], arm.get("incorrect_actor_reason"))
        obs_change = ref_ia_obs != arm_ia_obs
        reasons: list[str] = []
        if verdict_change:
            reasons.append("verdict:" + _verdict_code(ref, arm))
        if obs_change:
            reasons.append("observability:" + _obs_code(ref, arm))
        for score_key in ("missing_action_score", "incorrect_actor_score", "out_of_order_score"):
            rs = ref.get(score_key)
            as_ = arm.get(score_key)
            if rs != as_:
                reasons.append(f"score:{score_key}:{rs}->{as_}")
        if arm.get("rule_record_failed"):
            reasons.append("external_failure:" + str(arm.get("external_failure")))
        if not verdict_change and not obs_change:
            same_verdict += 1
        if reasons or verdict_change or obs_change:
            changes.append({
                "item_id": item_id,
                "process_id": ref["process_id"],
                "rule_id": ref["rule_id"],
                "check_type": ref.get("check_type"),
                "gold_type": None,  # filled by compare report from gold only
                "reference_prediction": ref["predicted_violation_type"],
                "rules_only_prediction": arm["predicted_violation_type"],
                "reference_observability": {
                    "observable": ref["incorrect_actor_observable"],
                    "reason": ref.get("incorrect_actor_reason"),
                },
                "rules_only_observability": {
                    "observable": arm["incorrect_actor_observable"],
                    "reason": arm.get("incorrect_actor_reason"),
                },
                "reference_scores": {k: ref["scores"][k] for k in
                                     ("missing_action", "incorrect_actor", "out_of_order")},
                "rules_only_scores": {k: arm["scores"][k] for k in
                                      ("missing_action", "incorrect_actor", "out_of_order")},
                "change_reason_codes": reasons,
            })
    comparison = {
        "schema_version": "gdpr_3type_linkage_comparison@1.0.0",
        "report_id": f"{RUN_ID_PREFIX}_compare",
        "same_verdict_count": same_verdict,
        "changed_count": len(changes),
        "total_items": len(ref_rows),
        "changes": changes,
    }
    report_json = output_root / f"{RUN_ID_PREFIX}_compare.json"
    if report_json.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing compare file: {report_json}")
    report_json.write_bytes(_json_bytes(comparison))
    return comparison


def _read_rows(run_dir: Path) -> list[dict[str, Any]]:
    out = []
    for line in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _verdict_code(ref: Mapping[str, Any], arm: Mapping[str, Any]) -> str:
    return f"{ref['predicted_violation_type']}->{arm['predicted_violation_type']}"


def _obs_code(ref: Mapping[str, Any], arm: Mapping[str, Any]) -> str:
    return (f"ref({ref['incorrect_actor_observable']},{ref.get('incorrect_actor_reason')})"
            f"->arm({arm['incorrect_actor_observable']},{arm.get('incorrect_actor_reason')})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=sorted(ARM_LABELS), default=None)
    parser.add_argument("--report-only", type=Path, default=None,
                        help="replay evaluation+report from a persisted arm run dir")
    parser.add_argument("--compare", action="store_true",
                        help="write per-item change list between both arms (both dirs required)")
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--report-root", type=Path, default=None)
    parser.add_argument("--gold", type=Path, default=None)
    parser.add_argument("--predictions", type=Path, default=None,
                        help="override Rules-Only capsule predictions path (rules_only arm)")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        if args.compare:
            comparison = compare_arms(args.output_root, args.report_root, args.overwrite)
            print(f"compare: {comparison['changed_count']} changed / "
                  f"{comparison['total_items']} items")
            return 0
        if args.report_only is not None:
            summary = report_only(args.report_only, args.report_root, args.gold,
                                  overwrite=args.overwrite)
            ev = summary["evaluation"]["violation"]
            print(f"report-only replay arm={summary['arm']} macro="
                  f"{ev['macro_f1']:.4f} exact={ev['exact_type_accuracy']:.4f} "
                  f"unobs={ev['unobservable']}")
            return 0
        if args.arm is None:
            parser.error("one of --arm / --report-only / --compare is required")
        summary = run_arm(args.arm, output_root=args.output_root,
                          report_root=args.report_root, overwrite=args.overwrite,
                          gold_path=args.gold, predictions_path=args.predictions)
        ev = summary["evaluation"]["violation"]
        print(f"arm={summary['arm']} macro={ev['macro_f1']:.4f} "
              f"exact={ev['exact_type_accuracy']:.4f} unobs={ev['unobservable']}")
        print(f"  per-type: " + ", ".join(
            f"{t}:P{ev['per_type'][t]['precision']:.3f}/R{ev['per_type'][t]['recall']:.3f}"
            f"/F{ev['per_type'][t]['f1']:.3f}"
            for t in ("missing_action", "incorrect_actor", "out_of_order")))
        return 0
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
        print(f"gdpr 3type linkage refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
