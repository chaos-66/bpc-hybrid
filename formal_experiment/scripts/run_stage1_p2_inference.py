# -*- coding: utf-8 -*-
"""S1.6 formal inference runner: P0/P1/P2 predictions for the frozen GDPR-7
seven BPMN processes.

GOLD ISOLATION: this runner reads ONLY the whitelisted inputs below. It
never reads the frozen gold directories (any stage), the human-correction
file, the adjudication asset files, or Stage 3 gold, and it never calls any
LLM/API. The output manifest records every input actually read and proves
gold_read=false (the independent prediction verifier recomputes this from
disk).

P2 is run TWICE; the canonical artifact must be byte-identical across runs.
No-overwrite: the output file is only created if it does not already exist.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_label_semantics import (  # noqa: E402
    render_label_semantics,
)
from bpc_hybrid.stage1_label_semantics_p2 import (  # noqa: E402
    render_p2_label_semantics,
)
from bpc_hybrid.stage1_formal_dataset import (  # noqa: E402
    load_formal_membership_contract,
    load_stage1_contract,
)

INPUTS = {
    "membership": ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json",
    "process_records": (ROOT / "data" / "development" / "human_review"
                        / "stage1_gdpr7_process_records_v1.json"),
    "structural_contract": None,  # resolved from membership below
    "label_contract": ROOT / "configs" / "stage1_label_semantics_s13.json",
    "p2_config": ROOT / "configs" / "stage1_label_p2_v1.json",
    "bpmn_dir": ROOT / "data" / "input" / "stage1_stage3" / "gdpr7",
}
METHODS = ("P0", "P1", "P2")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True,
                        help="output predictions JSON path (no overwrite)")
    args = parser.parse_args()

    out = ROOT / args.output
    if out.exists():
        raise SystemExit(f"refusing to overwrite existing output: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)

    membership = load_formal_membership_contract(INPUTS["membership"])
    structural_contract = load_stage1_contract(
        ROOT / membership["process_record_activation"][
            "structural_contract_path"])
    INPUTS["structural_contract"] = (
        ROOT / membership["process_record_activation"][
            "structural_contract_path"])
    label_contract = json.loads(
        INPUTS["label_contract"].read_text(encoding="utf-8"))
    p2_config = json.loads(INPUTS["p2_config"].read_text(encoding="utf-8"))
    records = json.loads(INPUTS["process_records"].read_text(
        encoding="utf-8"))["records"]
    records_by_id = {r["process_id"]: r for r in records}
    bpmn_by_id = {}
    for item in membership["membership"]["files"]:
        bpmn_by_id[item["input_id"]] = (
            INPUTS["bpmn_dir"] / item["filename"])

    process_ids = sorted(records_by_id)
    attempts: list[dict] = []
    inputs_read: dict[str, dict] = {}
    for path in [INPUTS["membership"], INPUTS["process_records"],
                 INPUTS["structural_contract"], INPUTS["label_contract"],
                 INPUTS["p2_config"]]:
        inputs_read[str(path.relative_to(ROOT))] = {
            "sha256": _sha256(path), "byte_size": path.stat().st_size}
    for pid in process_ids:
        bpmn_path = bpmn_by_id[pid]
        inputs_read[str(bpmn_path.relative_to(ROOT))] = {
            "sha256": _sha256(bpmn_path), "byte_size": bpmn_path.stat().st_size}
        record = records_by_id[pid]
        for method in METHODS:
            error = None
            process_record = None
            label_record = None
            try:
                if method == "P2":
                    # double-run determinism inside the runner
                    first = render_p2_label_semantics(
                        record, bpmn_path=bpmn_path, config=p2_config)
                    second = render_p2_label_semantics(
                        record, bpmn_path=bpmn_path, config=p2_config)
                    if json.dumps(first, ensure_ascii=False, sort_keys=True) \
                            != json.dumps(second, ensure_ascii=False,
                                          sort_keys=True):
                        raise RuntimeError(
                            "P2 double-run mismatch (non-deterministic)")
                    label_record = first
                else:
                    label_record = render_label_semantics(
                        record, baseline=method, contract=label_contract)
                process_record = record
            except Exception as exc:  # fail-closed: record the error
                error = f"{type(exc).__name__}: {exc}"
                process_record = None
                label_record = None
            attempts.append({
                "method": method,
                "process_id": pid,
                "process_record": process_record,
                "label_record": label_record,
                "error": error,
            })

    payload = {
        "schema_version": "stage1_formal_predictions@1.0.0",
        "project_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "membership_payload_sha256": membership["membership"][
            "membership_payload_sha256"],
        "methods": list(METHODS),
        "process_ids": process_ids,
        "activity_count": sum(
            len(records_by_id[p]["activities"]) for p in process_ids),
        "inputs_read": inputs_read,
        "safety": {
            "gold_read": False,
            "human_correction_read": False,
            "adjudication_assets_read": False,
            "stage3_gold_read": False,
            "llm_api_calls": 0,
            "network_calls": 0,
            "p2_double_run": "byte_identical_required_and_checked",
        },
        "attempts": attempts,
    }
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8")
    tmp = out.with_suffix(".tmp")
    tmp.write_bytes(data)
    out.write_bytes(data)
    tmp.unlink(missing_ok=True)
    print(f"predictions written: {out.relative_to(ROOT)}")
    print(f"processes: {len(process_ids)} | activities: "
          f"{payload['activity_count']} | attempts: {len(attempts)}")
    print(f"payload sha256: {_sha256_bytes(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
