"""Run the S1.6 evaluator on frozen synthetic contract evidence only."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_evaluation import (  # noqa: E402
    evaluate_stage1,
    load_evaluator_contract,
)
from bpc_hybrid.stage1_label_semantics import (  # noqa: E402
    load_label_contract,
    render_label_semantics,
)
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file  # noqa: E402


EVALUATOR_CONFIG = ROOT / "configs" / "stage1_evaluator_s16.json"
LABEL_CONFIG = ROOT / "configs" / "stage1_label_semantics_s13.json"
STRUCTURAL_CONFIG = ROOT / "configs" / "stage1_structural_s11_s14.json"
FIXTURE = ROOT / "tests" / "fixtures" / "stage1" / "s13_label_edge_cases.bpmn"
REFERENCE = ROOT / "tests" / "fixtures" / "stage1" / "s16_synthetic_semantic_reference.json"


def build_evidence() -> tuple[dict, dict, dict, list[dict]]:
    evaluator_contract = load_evaluator_contract(EVALUATOR_CONFIG)
    label_contract = load_label_contract(LABEL_CONFIG)
    structural_contract = load_stage1_contract(STRUCTURAL_CONFIG)
    process_record = parse_bpmn_file(FIXTURE, contract=structural_contract)
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    if (
        reference.get("scope") != "synthetic_contract_verification_only"
        or reference.get("process_id") != process_record["process_id"]
        or reference.get("human_gold") is not False
        or reference.get("performance_claim_allowed") is not False
    ):
        raise ValueError("S1.6 synthetic reference boundary changed")
    gold_semantics = {
        process_record["process_id"]: {
            item["activity_id"]: {
                "actor": item["actor"],
                "action": item["action"],
                "business_object": item["business_object"],
            }
            for item in reference["activities"]
        }
    }
    attempts = [
        {
            "method": method,
            "process_id": process_record["process_id"],
            "process_record": process_record,
            "label_record": render_label_semantics(
                process_record,
                baseline=method,
                contract=label_contract,
            ),
            "error": None,
        }
        for method in ("P0", "P1")
    ]
    return evaluator_contract, label_contract, process_record, [gold_semantics, attempts]


def main() -> int:
    evaluator_contract, label_contract, process_record, evidence = build_evidence()
    gold_semantics, attempts = evidence
    report = evaluate_stage1(
        gold_process_records=[process_record],
        gold_semantics=gold_semantics,
        attempts=attempts,
        label_contract=label_contract,
        evaluator_contract=evaluator_contract,
        scope="synthetic_contract_verification",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
