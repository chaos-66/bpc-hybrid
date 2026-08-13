# -*- coding: utf-8 -*-
"""Fail-closed verifier for the S1.6 formal predictions (2026-08-13).

Recomputes everything from disk:
  1. payload hash and structure (schema, methods, process ids, 45
     activities, 7x3 attempt product)
  2. inputs_read manifest matches on-disk hashes of the whitelisted inputs
  3. safety declarations (gold_read=false, correction/adjudication/stage3
     not read, zero LLM/network, P2 double-run)
  4. every attempt re-rendered from the whitelisted inputs ONLY:
     P0/P1 via the locked label contract; P2 via the locked P2 module --
     must equal the stored attempt field-by-field (this also proves the
     predictions contain nothing that is not a deterministic function of
     the whitelisted inputs, i.e. no Gold leakage)
  5. P2 re-run twice: byte-identical
  6. no terminal errors in any attempt
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

PREDICTIONS = ROOT / "outputs" / "development" / "stage1_predictions" \
    / "formal_predictions_v1.json"
MEMBERSHIP_PATH = (ROOT / "configs" / "datasets"
                   / "stage1_stage3_gdpr7_v1.json")
RECORDS_PATH = (ROOT / "data" / "development" / "human_review"
                / "stage1_gdpr7_process_records_v1.json")
LABEL_CONTRACT_PATH = (ROOT / "configs" / "stage1_label_semantics_s13.json")
P2_CONFIG_PATH = ROOT / "configs" / "stage1_label_p2_v1.json"
BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"

METHODS = ("P0", "P1", "P2")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    checks = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    if not PREDICTIONS.exists():
        return {"verified": False, "checks": [
            {"name": "predictions exist", "ok": False, "detail": ""}]}
    payload = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    check("schema version",
          payload.get("schema_version") == "stage1_formal_predictions@1.0.0")
    check("methods exact", tuple(payload.get("methods", ())) == METHODS)
    membership = load_formal_membership_contract(MEMBERSHIP_PATH)
    check("membership payload hash",
          payload.get("membership_payload_sha256")
          == membership["membership"]["membership_payload_sha256"])
    records = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))["records"]
    records_by_id = {r["process_id"]: r for r in records}
    process_ids = sorted(records_by_id)
    check("process ids exact", payload.get("process_ids") == process_ids)
    check("activity count 45",
          payload.get("activity_count")
          == sum(len(records_by_id[p]["activities"]) for p in process_ids)
          == 45)

    # inputs_read must match disk hashes
    inputs_ok = True
    for rel, value in payload.get("inputs_read", {}).items():
        path = ROOT / rel
        if not path.exists() or _sha256(path) != value["sha256"] \
                or path.stat().st_size != value["byte_size"]:
            inputs_ok = False
    check("inputs_read matches disk", inputs_ok)

    # safety declarations
    safety = payload.get("safety", {})
    check("safety: no gold/correction/adjudication/stage3 read",
          safety.get("gold_read") is False
          and safety.get("human_correction_read") is False
          and safety.get("adjudication_assets_read") is False
          and safety.get("stage3_gold_read") is False)
    check("safety: zero LLM/network",
          safety.get("llm_api_calls") == 0
          and safety.get("network_calls") == 0)
    check("safety: P2 double-run declared",
          safety.get("p2_double_run")
          == "byte_identical_required_and_checked")

    # attempts: exact product + re-render equality (Gold-leakage proof)
    attempts = payload.get("attempts", [])
    keys = {(a["method"], a["process_id"]) for a in attempts}
    check("attempt product exact 7x3",
          keys == {(m, p) for m in METHODS for p in process_ids}
          and len(attempts) == 21)
    label_contract = json.loads(LABEL_CONTRACT_PATH.read_text(
        encoding="utf-8"))
    p2_config = json.loads(P2_CONFIG_PATH.read_text(encoding="utf-8"))
    structural_contract = load_stage1_contract(
        ROOT / membership["process_record_activation"][
            "structural_contract_path"])
    bpmn_by_id = {}
    for item in membership["membership"]["files"]:
        bpmn_by_id[item["input_id"]] = BPMN_DIR / item["filename"]
    re_render_ok = True
    p2_double_ok = True
    no_error_ok = True
    detail = ""
    for attempt in attempts:
        method = attempt["method"]
        pid = attempt["process_id"]
        if attempt["error"] is not None:
            no_error_ok = False
            continue
        if method not in METHODS or pid not in records_by_id:
            re_render_ok = False
            continue
        if attempt["process_record"] != records_by_id[pid]:
            re_render_ok = False
            detail = f"{pid} process_record mismatch"
            continue
        try:
            if method == "P2":
                expected = render_p2_label_semantics(
                    records_by_id[pid], bpmn_path=bpmn_by_id[pid],
                    config=p2_config)
                second = render_p2_label_semantics(
                    records_by_id[pid], bpmn_path=bpmn_by_id[pid],
                    config=p2_config)
                if json.dumps(expected, ensure_ascii=False, sort_keys=True) \
                        != json.dumps(second, ensure_ascii=False,
                                      sort_keys=True):
                    p2_double_ok = False
            else:
                expected = render_label_semantics(
                    records_by_id[pid], baseline=method,
                    contract=label_contract)
        except Exception as exc:  # pragma: no cover - defensive
            re_render_ok = False
            detail = f"{pid} re-render raised: {exc}"
            continue
        if attempt["label_record"] != expected:
            re_render_ok = False
            detail = f"{pid}/{method} label_record mismatch"
    check("attempts re-render from whitelisted inputs only (no Gold "
          "leakage)", re_render_ok, detail)
    check("P2 double-run byte-identical", p2_double_ok)
    check("no terminal errors", no_error_ok)

    return {"verified": all(c["ok"] for c in checks), "checks": checks,
            "payload_sha256": _sha256(PREDICTIONS)}


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
        print("PREDICTIONS VERIFIED" if result["verified"]
              else "PREDICTIONS NOT VERIFIED")
        print("payload sha256:", result.get("payload_sha256"))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
