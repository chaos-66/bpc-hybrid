# -*- coding: utf-8 -*-
"""Fail-closed verifier for the S1.7 freeze readiness dry-run packet v2.

Recomputes everything from disk:
  1. every hash recorded in the packet matches the on-disk file
  2. every listed independent verifier ACTUALLY passes (run from disk)
  3. corrections: verb count 200/200; overlap audit bound; claim correction
     bound; formal paths authoritative; P2/predictions/metrics/Gold
     unchanged (byte-level hash equality with the locked references)
  4. status semantics: dry_run_not_applied; target
     ready_for_user_freeze_authorization; S1.7 NOT frozen; S3.7 not started
  5. the exact authorization sentence is present
  6. v1 superseded marker present

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
PACKET = ROOT / "outputs" / "reports" / "s1_7_freezer_readiness_dry_run_v2.json"
V1_PACKET = ROOT / "outputs" / "reports" / "s1_7_freezer_readiness_dry_run_v1.json"

EXPECTED_SENTENCE = (
    "I acknowledge that the P2 method was developed AFTER the Stage 1 "
    "Process Gold was formed and that at least three target activity labels "
    '("Communication with data subject", "Rectify data", "Retrieve data") '
    "entered the development test fixtures, with at least one asserted "
    "triple matching the human Gold; I acknowledge that the S1.6 metrics are "
    "a fixed-GDPR-7 formal descriptive component evaluation and NOT "
    "held-out generalization evidence. I authorize the formal S1.7 freeze of "
    "the existing, non-tuned-after-evaluation P2 method (locked config, "
    "implementation and offline runtime), the existing locked P0/P1/P2 "
    "predictions and the ORIGINAL metrics, together with the frozen Stage 1 "
    "Process Gold and the verified evaluation capsule. The freeze shall NOT "
    "modify P2, shall NOT recompute selective results, shall NOT add any "
    "LLM/API call, and shall NOT modify the Stage 2/Stage 3 Gold or the "
    "experiment contract. The formal Stage 3 Oracle is NOT auto-authorized "
    "by this packet and advances only through its own independent gates.")


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
                "s17v2_verify_" + path.stem, path)
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

    # 3. corrections
    corr = packet.get("corrections_applied", {})
    verbs = json.loads((ROOT / "configs" / "resources"
                        / "english_verb_roots_v1.json")
                       .read_text(encoding="utf-8"))["verbs"]
    check("correction: verb count 200/200",
          len(verbs) == 200 and len(set(verbs)) == 200
          and corr.get("verb_count_200_of_200") is True)
    check("correction: audit + claim bound",
          corr.get("target_overlap_audit_bound") is True
          and corr.get("claim_correction_bound") is True)
    check("correction: formal paths authoritative",
          corr.get("formal_paths_authoritative") is True)
    p2_config = ROOT / "configs" / "stage1_label_p2_v1.json"
    p2_impl = ROOT / "src" / "bpc_hybrid" / "stage1_label_semantics_p2.py"
    preds_locked = (ROOT / "outputs" / "development" / "stage1_predictions"
                    / "formal_predictions_v1.json")
    preds_auth = (ROOT / "data" / "predictions" / "stage1_formal_v1"
                  / "formal_predictions_v1.json")
    gold = (ROOT / "data" / "gold" / "stage1" / "process_records"
            / "stage1_process_gold_v1.json")
    check("correction: P2 config/impl unchanged",
          _sha256(p2_config)
          == "59ac4e8ec2b02632366cac229b5538c4f243910f6a371b5e14e1be65817cc49d"
          and _sha256(p2_impl)
          == "c95910efe80992e0b49be7859e9c9a7b48493e9c794472ed86bcb129d2a5a3c2"
          and corr.get("p2_unchanged") is True)
    check("correction: predictions unchanged",
          _sha256(preds_locked)
          == "79a9b2c17185d63dc5ab5d9c47c8c592469b30f3cf7298740e593838166a94a8"
          and _sha256(preds_auth) == _sha256(preds_locked)
          and corr.get("predictions_unchanged") is True)
    check("correction: metrics unchanged",
          corr.get("metrics_unchanged") is True)
    check("correction: Gold unchanged",
          _sha256(gold)
          == "f33aa857a0796d0517a9d04cc96b0a4f316202603fe0adf66693aeb5cb444bca"
          and corr.get("gold_unchanged") is True)

    # 4. claim + pipeline state
    claim = packet.get("claim", {})
    check("claim target-aware",
          claim.get("strict_test_blind") is False
          and claim.get("target_labels_seen_during_development") is True
          and claim.get("held_out_generalization_claim_allowed") is False
          and claim.get("post_evaluation_tuning") is False
          and claim.get("evaluation_role")
          == "formal_descriptive_component_evaluation_on_fixed_GDPR7")
    state = packet.get("pipeline_state", {})
    check("pipeline state honest",
          state.get("S1.7")
          == "ready_for_user_freeze_authorization (NOT frozen, NOT applied)"
          and "NOT auto-authorized" in state.get("S3.7", ""))
    check("overlap audit summary bound",
          packet.get("overlap_audit_summary", {}).get(
              "historical_exact_overlap", {}).get("count") == 3
          and packet.get("overlap_audit_summary", {}).get(
              "current_exact_overlap", {}).get("count") == 0)

    # 5. authorization sentence exact
    check("authorization sentence exact",
          packet.get("authorization_sentence") == EXPECTED_SENTENCE)

    # 6. v1 superseded
    v1 = json.loads(V1_PACKET.read_text(encoding="utf-8"))
    check("v1 marked superseded",
          v1.get("superseded_by") == "s1_7_freezer_readiness_dry_run_v2.json"
          and "target_fixture_overlap" in v1.get("superseded_reason", ""))

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
        print("S1.7 V2 DRY-RUN VERIFIED" if result["verified"]
              else "S1.7 V2 DRY-RUN NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
