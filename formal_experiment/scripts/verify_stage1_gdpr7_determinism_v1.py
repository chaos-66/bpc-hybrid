# -*- coding: utf-8 -*-
"""Stage 1 (S1.1-S1.4) GDPR-7 double-run determinism verifier v1 (zero-API).

Verifies:
1. parsing all 7 GDPR BPMN files twice produces byte-identical canonical
   Process Records (deterministic double-run);
2. the freshly parsed records equal the membership-locked
   stage1_gdpr7_process_records_v1.json (byte-identical, no drift);
3. input / schema / config / implementation hashes are recorded.

Output:
- outputs/reports/s1_1_s1_4_determinism_v1.manifest.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_formal_dataset import (  # noqa: E402
    load_formal_membership_contract,
    build_formal_process_records,
)

BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"
MEMBERSHIP_CONTRACT = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
PROCESS_RECORDS = ROOT / "data" / "development" / "human_review" / "stage1_gdpr7_process_records_v1.json"
PROCESS_SCHEMA = ROOT / "configs" / "schemas" / "process_record.schema.json"
PARSER = ROOT / "src" / "bpc_hybrid" / "stage1_process.py"
DATASET_MODULE = ROOT / "src" / "bpc_hybrid" / "stage1_formal_dataset.py"

OUT_MANIFEST = ROOT / "outputs" / "reports" / "s1_1_s1_4_determinism_v1.manifest.json"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(data: list[dict[str, Any]]) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)
            + "\n").encode("utf-8")


def main() -> int:
    membership = load_formal_membership_contract(MEMBERSHIP_CONTRACT)
    # double run
    run1 = build_formal_process_records(membership)
    run2 = build_formal_process_records(membership)
    b1 = _canonical(run1)
    b2 = _canonical(run2)
    deterministic = b1 == b2

    locked = json.loads(PROCESS_RECORDS.read_text(encoding="utf-8"))
    locked_records = locked.get("records", [])
    locked_bytes = _canonical(locked_records)
    matches_locked = b1 == locked_bytes

    bpmn_files = sorted(p.name for p in BPMN_DIR.glob("*.bpmn"))
    checks = {
        "seven_bpmn_files": len(bpmn_files) == 7,
        "double_run_byte_identical": deterministic,
        "matches_locked_process_records": matches_locked,
        "record_count": len(run1) == 7,
    }
    manifest = {
        "schema_version": "s1_1_s1_4_determinism_manifest@1.0.0",
        "project_date": "2026-08-11",
        "checks": checks,
        "bpmn_files": bpmn_files,
        "hashes": {
            "membership_contract": {"path": "configs/datasets/stage1_stage3_gdpr7_v1.json",
                                    "sha256": _sha256_file(MEMBERSHIP_CONTRACT)},
            "process_record_schema": {"path": "configs/schemas/process_record.schema.json",
                                      "sha256": _sha256_file(PROCESS_SCHEMA)},
            "parser_implementation": {"path": "src/bpc_hybrid/stage1_process.py",
                                      "sha256": _sha256_file(PARSER)},
            "dataset_implementation": {"path": "src/bpc_hybrid/stage1_formal_dataset.py",
                                       "sha256": _sha256_file(DATASET_MODULE)},
            "locked_process_records": {"path": "data/development/human_review/stage1_gdpr7_process_records_v1.json",
                                       "sha256": _sha256_file(PROCESS_RECORDS)},
        },
        "safety": {
            "llm_api_called": False,
            "stage3_gold_not_used_to_tune_stage1": True,
            "no_human_decision_inferred": True,
        },
        "zero_api": {"new_llm_api_calls": 0},
    }
    data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT_MANIFEST.exists() and OUT_MANIFEST.read_bytes() != data:
        raise RuntimeError(f"refusing to overwrite different content: {OUT_MANIFEST}")
    OUT_MANIFEST.write_bytes(data)

    print(f"double-run deterministic: {deterministic} | "
          f"matches locked process records: {matches_locked}")
    print(f"manifest: {OUT_MANIFEST.relative_to(ROOT)}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
