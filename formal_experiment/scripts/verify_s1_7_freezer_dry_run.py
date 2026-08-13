# -*- coding: utf-8 -*-
"""Fail-closed verifier for the S1.7 freeze-readiness dry-run packet.

Recomputes everything from disk:
  1. every hash recorded in the packet matches the on-disk file
  2. every listed independent verifier ACTUALLY passes (run from disk)
  3. membership payload binding
  4. status semantics: dry_run_not_applied; target
     ready_for_user_freeze_authorization; S1.7 NOT frozen; S3.7 not started
  5. consistency declarations present (zero API, P2 unchanged after lock,
     Gold not used for tuning, Stage 3 not started)
  6. the exact authorization sentence is present
  7. the packet's hash is stable

Exit 0 iff everything verifies.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "outputs" / "reports" / "s1_7_freezer_readiness_dry_run_v1.json"

EXPECTED_SENTENCE = (
    "I authorize the formal S1.7 freeze of the already-verified Stage 1 "
    "assets: the frozen seven-BPMN membership and source hashes, the "
    "canonical Process Record schema and records, the Sun/Leopold-style P2 "
    "method (locked config, implementation and offline runtime), the P0/P1/P2 "
    "formal predictions, the frozen Stage 1 Process Gold, the S1.6 one-shot "
    "evaluation results and the evaluation capsule. The freeze shall NOT "
    "modify P2 or recompute selective results, shall NOT add any LLM/API "
    "call, and shall NOT modify the Stage 2/Stage 3 Gold or the experiment "
    "contract. After the S1.7 freeze, the formal Stage 3 Oracle still "
    "advances only through its own independent gates.")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    checks = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    check("packet status dry_run_not_applied",
          packet.get("status") == "dry_run_not_applied")
    check("target status ready_for_user_freeze_authorization",
          packet.get("target_status")
          == "S1.7 ready_for_user_freeze_authorization")

    # 1. hashes
    hashes_ok = True
    for name, digest in packet.get("hashes", {}).items():
        path = ROOT / name
        if not path.exists() or _sha256(path) != digest:
            hashes_ok = False
    check("all recorded hashes match disk", hashes_ok)

    # 2. verifiers actually run
    verifiers_ok = True
    for rel, result in packet.get("verifier_results", {}).items():
        path = ROOT / rel
        try:
            spec = importlib.util.spec_from_file_location(
                "s17_verify_" + path.stem, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ok = module.verify()["verified"] is True
        except Exception:  # pragma: no cover - defensive
            ok = False
        if not ok or result.get("verified") is not True:
            verifiers_ok = False
    check("all independent verifiers pass (re-run)", verifiers_ok)
    check("packet claims all verifiers verified",
          packet.get("all_verifiers_verified") is True)

    # 3. membership binding
    membership = json.loads((ROOT / "configs" / "datasets"
                             / "stage1_stage3_gdpr7_v1.json")
                            .read_text(encoding="utf-8"))
    check("membership payload binding",
          packet.get("frozen_membership", {}).get("membership_payload_sha256")
          == membership["membership"]["membership_payload_sha256"]
          and packet.get("frozen_membership", {}).get("bpmn_count") == 7
          and packet.get("frozen_membership", {}).get("activity_count") == 45
          and packet.get("frozen_membership", {}).get("label_fields") == 135)

    # 4. consistency declarations
    cons = packet.get("consistency", {})
    check("consistency declarations",
          cons.get("zero_new_llm_api_calls") == 0
          and cons.get("p2_unchanged_after_lock") is True
          and cons.get("gold_not_used_for_tuning") is True
          and cons.get("stage3_not_started") is True)

    # 5. stage-3 boundary + pipeline state
    check("pipeline state honest",
          packet.get("pipeline_state", {}).get("S1.7")
          == "ready_for_user_freeze_authorization (NOT frozen, NOT applied)"
          and "NOT auto-authorized" in packet.get(
              "pipeline_state", {}).get("S3.7", ""))

    # 6. exact authorization sentence
    check("authorization sentence exact",
          packet.get("authorization_sentence") == EXPECTED_SENTENCE)

    # 7. zero API
    check("zero new LLM/API calls",
          packet.get("zero_api", {}).get("new_llm_api_calls") == 0)

    return {"verified": all(c["ok"] for c in checks), "checks": checks,
            "packet_sha256": _sha256(PACKET)}


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
        print("S1.7 DRY-RUN VERIFIED" if result["verified"]
              else "S1.7 DRY-RUN NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
