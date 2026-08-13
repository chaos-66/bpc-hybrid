# -*- coding: utf-8 -*-
"""S1.6 ONE-SHOT formal evaluation (2026-08-13).

Reads ONLY:
  - the locked formal predictions (P0/P1/P2, 7x3 attempts)
  - the frozen Stage 1 Process Gold (data/gold/stage1/...)
  - the locked evaluator contract, label contract, P2 config

Produces the formal evaluation report + a self-contained capsule
(predictions copy, evaluation JSON, manifest, export index). No-overwrite.

Post-evaluation tuning is FORBIDDEN: P2 rules/parameters/config are never
touched by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_evaluation_formal import (  # noqa: E402
    evaluate_stage1_formal,
    load_formal_evaluator_contract,
)

PREDICTIONS = (ROOT / "outputs" / "development" / "stage1_predictions"
               / "formal_predictions_v1.json")
GOLD = (ROOT / "data" / "gold" / "stage1" / "process_records"
        / "stage1_process_gold_v1.json")
EVALUATOR_CONTRACT = ROOT / "configs" / "stage1_evaluator_s16_formal.json"
LABEL_CONTRACT = ROOT / "configs" / "stage1_label_semantics_s13.json"
P2_CONFIG = ROOT / "configs" / "stage1_label_p2_v1.json"

SEMANTIC_FIELDS = ("actor", "action", "business_object")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capsule", required=True,
                        help="output capsule directory (no overwrite)")
    args = parser.parse_args()

    capsule = ROOT / args.capsule
    if capsule.exists():
        raise SystemExit(f"refusing to overwrite existing capsule: {capsule}")
    capsule.mkdir(parents=True)

    predictions = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    evaluator_contract = load_formal_evaluator_contract(EVALUATOR_CONTRACT)
    label_contract = json.loads(LABEL_CONTRACT.read_text(encoding="utf-8"))
    p2_config = json.loads(P2_CONFIG.read_text(encoding="utf-8"))

    # gold references: structure records (gold_process_record) + semantic
    # values (label_annotations)
    gold_records = []
    gold_semantics: dict[str, dict[str, dict[str, str | None]]] = {}
    for record in gold["records"]:
        pid = record["process_id"]
        gold_records.append(record["structure_annotation"][
            "gold_process_record"])
        semantics: dict[str, dict[str, str | None]] = {}
        for la in record["label_annotations"]:
            values: dict[str, str | None] = {}
            for field in SEMANTIC_FIELDS:
                entry = la.get(field, {})
                if entry.get("status") == "present":
                    values[field] = entry.get("value")
                else:
                    values[field] = None
            semantics[la["activity_id"]] = values
        gold_semantics[pid] = semantics

    report = evaluate_stage1_formal(
        gold_process_records=gold_records,
        gold_semantics=gold_semantics,
        attempts=predictions["attempts"],
        label_contract=label_contract,
        evaluator_contract=evaluator_contract,
    )

    # per-process diagnostics + method deltas (report-level only)
    per_process: dict[str, dict[str, dict[str, float]]] = {}
    for attempt in predictions["attempts"]:
        pid = attempt["process_id"]
        method = attempt["method"]
        label = attempt["label_record"]
        exact = 0
        total = 0
        if label is not None:
            by_id = {a["activity_id"]: a for a in label["activities"]}
            for activity_id, gold_values in gold_semantics[pid].items():
                total += 1
                pred = by_id.get(activity_id, {})
                if all(
                    (pred.get(f + "_surface") if f + "_surface" in pred
                     else None) == gold_values[f]
                    for f in SEMANTIC_FIELDS
                ):
                    exact += 1
        per_process.setdefault(pid, {})[method] = {
            "triple_exact_accuracy": exact / total if total else 0.0,
            "activities": total,
        }

    deltas: dict[str, dict[str, float]] = {}
    for field in SEMANTIC_FIELDS:
        f1_p2 = report["methods"]["P2"]["semantics"]["by_field"][field]["f1"]
        f1_p1 = report["methods"]["P1"]["semantics"]["by_field"][field]["f1"]
        f1_p0 = report["methods"]["P0"]["semantics"]["by_field"][field]["f1"]
        deltas[field] = {
            "P2_minus_P1": round(f1_p2 - f1_p1, 6),
            "P2_minus_P0": round(f1_p2 - f1_p0, 6),
        }

    evaluation = {
        "schema_version": "stage1_formal_evaluation@1.0.0",
        "project_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "scope": "formal",
        "one_shot": True,
        "report": report,
        "per_process_triple_exact_accuracy": per_process,
        "method_deltas_f1": deltas,
        "inputs": {
            "predictions": {
                "path": "outputs/development/stage1_predictions/formal_predictions_v1.json",
                "sha256": _sha256(PREDICTIONS),
            },
            "gold": {
                "path": "data/gold/stage1/process_records/stage1_process_gold_v1.json",
                "sha256": _sha256(GOLD),
            },
            "evaluator_contract": {
                "path": "configs/stage1_evaluator_s16_formal.json",
                "sha256": _sha256(EVALUATOR_CONTRACT),
            },
            "label_contract": {
                "path": "configs/stage1_label_semantics_s13.json",
                "sha256": _sha256(LABEL_CONTRACT),
            },
            "p2_config": {
                "path": "configs/stage1_label_p2_v1.json",
                "sha256": _sha256(P2_CONFIG),
            },
        },
        "safety": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "p2_tuned_after_evaluation": False,
            "p2_unchanged_after_lock": True,
        },
        "limitations": [
            "structural Gold derives from human-confirmed parser candidates; a perfect structural score is NOT independent external generalization evidence",
            "Gold is candidate-assisted human adjudication, not double-independent from-scratch annotation",
            "only 7 processes / 45 activities / 135 semantic fields",
            "no significance inference",
            "no hard comparison with Sun's absolute scores on different datasets",
            "results validate the Stage 1 component reconstruction, not Stage 1 innovation",
            "P2 was locked after the Stage 1 Gold was formed: NOT strictly blind preregistered; the runner never read Gold and no post-evaluation tuning happened",
        ],
    }
    (capsule / "evaluation.json").write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    shutil.copy2(PREDICTIONS, capsule / "predictions_copy.json")

    # export index + capsule manifest
    export_index = {
        "schema_version": "stage1_formal_capsule_export_index@1.0.0",
        "entries": [
            {"path": "predictions_copy.json",
             "sha256": _sha256(capsule / "predictions_copy.json")},
            {"path": "evaluation.json",
             "sha256": _sha256(capsule / "evaluation.json")},
        ],
    }
    (capsule / "export_index.json").write_text(
        json.dumps(export_index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    manifest = {
        "schema_version": "stage1_formal_capsule_manifest@1.0.0",
        "project_date": evaluation["project_date"],
        "status": "evaluation_completed_no_tuning",
        "inputs": evaluation["inputs"],
        "evaluation_sha256": _sha256(capsule / "evaluation.json"),
        "predictions_sha256": export_index["entries"][0]["sha256"],
        "export_index_sha256": _sha256(capsule / "export_index.json"),
        "zero_api": {"new_llm_api_calls": 0},
    }
    (capsule / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    print(f"capsule written: {capsule.relative_to(ROOT)}")
    print(f"evaluation sha256: {manifest['evaluation_sha256']}")
    for method in ("P0", "P1", "P2"):
        sem = report["methods"][method]["semantics"]["micro"]
        print(f"{method}: semantic micro P={sem['precision']:.4f} "
              f"R={sem['recall']:.4f} F1={sem['f1']:.4f} "
              f"acc={sem['exact_value_accuracy']:.4f} | "
              f"triple={report['methods'][method]['semantic_triple_exact_accuracy']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
