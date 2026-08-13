# -*- coding: utf-8 -*-
"""Fail-closed verifier for the S1.6 formal evaluation capsule (2026-08-13).

Recomputes everything from disk:
  1. capsule structure (predictions_copy, evaluation, manifest,
     export_index) and their hashes
  2. the evaluation report is RE-RUN from the on-disk predictions + Gold +
     contracts and must equal the stored report (no trusted booleans)
  3. input bindings (predictions/Gold/evaluator contract/label contract/P2
     config) match the on-disk hashes
  4. P2 is still byte-locked to the Checkpoint-A lock manifest
  5. safety declarations: zero LLM/network, no post-evaluation tuning,
     P2 unchanged after lock
  6. limitations block present (candidate-assisted Gold, no significance,
     no Sun absolute comparison, post-Gold lock disclosure)

Exit 0 iff everything verifies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_evaluation_formal import (  # noqa: E402
    evaluate_stage1_formal,
    load_formal_evaluator_contract,
)

CAPSULE = ROOT / "outputs" / "development" / "stage1_formal_capsule_v1"
PREDICTIONS = (ROOT / "outputs" / "development" / "stage1_predictions"
               / "formal_predictions_v1.json")
GOLD = (ROOT / "data" / "gold" / "stage1" / "process_records"
        / "stage1_process_gold_v1.json")
EVALUATOR_CONTRACT = ROOT / "configs" / "stage1_evaluator_s16_formal.json"
LABEL_CONTRACT = ROOT / "configs" / "stage1_label_semantics_s13.json"
P2_CONFIG = ROOT / "configs" / "stage1_label_p2_v1.json"
P2_LOCK = ROOT / "outputs" / "reports" / "s1_3_p2_locked_v1.manifest.json"

SEMANTIC_FIELDS = ("actor", "action", "business_object")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_evaluator() -> dict:
    predictions = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    evaluator_contract = load_formal_evaluator_contract(EVALUATOR_CONTRACT)
    label_contract = json.loads(LABEL_CONTRACT.read_text(encoding="utf-8"))
    gold_records = []
    gold_semantics = {}
    for record in gold["records"]:
        pid = record["process_id"]
        gold_records.append(record["structure_annotation"][
            "gold_process_record"])
        semantics = {}
        for la in record["label_annotations"]:
            values = {}
            for field in SEMANTIC_FIELDS:
                entry = la.get(field, {})
                values[field] = (entry.get("value")
                                 if entry.get("status") == "present"
                                 else None)
            semantics[la["activity_id"]] = values
        gold_semantics[pid] = semantics
    return evaluate_stage1_formal(
        gold_process_records=gold_records,
        gold_semantics=gold_semantics,
        attempts=predictions["attempts"],
        label_contract=label_contract,
        evaluator_contract=evaluator_contract,
    )


def verify() -> dict:
    checks = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    if not CAPSULE.exists():
        return {"verified": False, "checks": [
            {"name": "capsule exists", "ok": False, "detail": ""}]}
    for name in ("predictions_copy.json", "evaluation.json", "manifest.json",
                 "export_index.json"):
        check(f"capsule file {name}", (CAPSULE / name).exists())
    evaluation = json.loads((CAPSULE / "evaluation.json").read_text(
        encoding="utf-8"))
    manifest = json.loads((CAPSULE / "manifest.json").read_text(
        encoding="utf-8"))
    export_index = json.loads((CAPSULE / "export_index.json").read_text(
        encoding="utf-8"))

    # 1. capsule hashes
    check("evaluation hash == manifest",
          _sha256(CAPSULE / "evaluation.json")
          == manifest.get("evaluation_sha256"))
    check("predictions copy hash == manifest",
          _sha256(CAPSULE / "predictions_copy.json")
          == manifest.get("predictions_sha256")
          == export_index["entries"][0]["sha256"])
    check("export index hash == manifest",
          _sha256(CAPSULE / "export_index.json")
          == manifest.get("export_index_sha256"))

    # 2. report re-run equality
    try:
        report = _run_evaluator()
        check("report re-run equals stored report",
              report == evaluation["report"])
    except Exception as exc:  # pragma: no cover - defensive
        check("report re-run equals stored report", False, str(exc))

    # 3. input bindings
    inputs = evaluation.get("inputs", {})
    bind_ok = (inputs.get("predictions", {}).get("sha256")
               == _sha256(PREDICTIONS)
               and inputs.get("gold", {}).get("sha256") == _sha256(GOLD)
               and inputs.get("evaluator_contract", {}).get("sha256")
               == _sha256(EVALUATOR_CONTRACT)
               and inputs.get("label_contract", {}).get("sha256")
               == _sha256(LABEL_CONTRACT)
               and inputs.get("p2_config", {}).get("sha256")
               == _sha256(P2_CONFIG))
    check("input bindings match disk", bind_ok)
    check("predictions copy == on-disk predictions",
          _sha256(CAPSULE / "predictions_copy.json") == _sha256(PREDICTIONS))

    # 4. P2 still locked to Checkpoint A
    lock = json.loads(P2_LOCK.read_text(encoding="utf-8"))
    artifacts = lock.get("artifacts", {})
    lock_ok = (_sha256(P2_CONFIG) == artifacts.get(
        "configs/stage1_label_p2_v1.json")
        and _sha256(ROOT / "src/bpc_hybrid/stage1_label_semantics_p2.py")
        == artifacts.get("src/bpc_hybrid/stage1_label_semantics_p2.py"))
    check("P2 unchanged after lock (config + implementation)", lock_ok)

    # 5. safety declarations
    safety = evaluation.get("safety", {})
    check("zero LLM/network + no tuning",
          safety.get("llm_api_calls") == 0
          and safety.get("network_calls") == 0
          and safety.get("p2_tuned_after_evaluation") is False
          and safety.get("p2_unchanged_after_lock") is True)

    # 6. limitations disclosure
    limitations = evaluation.get("limitations", [])
    text = " ".join(limitations)
    check("limitations: candidate-assisted Gold disclosed",
          "candidate-assisted human adjudication" in text
          and "parser candidates" in text)
    check("limitations: no significance / no Sun absolute comparison",
          "no significance inference" in text
          and "Sun" in text)
    check("limitations: post-Gold lock disclosed",
          "P2 was locked after the Stage 1 Gold was formed" in text
          and "NOT strictly blind preregistered" in text)

    # 7. zero API in capsule manifest
    check("capsule manifest zero API",
          manifest.get("zero_api", {}).get("new_llm_api_calls") == 0)

    return {"verified": all(c["ok"] for c in checks), "checks": checks,
            "evaluation_sha256": _sha256(CAPSULE / "evaluation.json")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        for c in result["checks"]:
            print(("PASS" if c["ok"] else "FAIL"), c["name"], c["detail"])
        print("CAPSULE VERIFIED" if result["verified"]
              else "CAPSULE NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
