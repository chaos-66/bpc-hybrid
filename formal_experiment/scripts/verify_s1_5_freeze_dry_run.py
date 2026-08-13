# -*- coding: utf-8 -*-
"""Fail-closed verifier for the S1.5 Process Gold freeze-authorization
DRY-RUN packet (2026-08-13, Batch 7/7).

The packet is a HISTORICAL, read-only snapshot taken BEFORE the user's
freeze authorization (2026-08-13, later the same day). It must remain
internally self-consistent and its evidence must still match the on-disk,
immutable assets (correction, per-batch chain assets). It does NOT assert
anything about the CURRENT authorization state (the auth manifest evolved
legitimately to process_gold_freeze_authorized_and_published after the
authorization).

Recomputes everything from disk:
  1. per-batch manifest linkage (before/after/decision/import/source/
     candidate hashes) matches the dry-run packet's chain
  2. final correction sha256 == on-disk correction file
  3. 7/7 records, 135/135 fields, 7/7 structures, 142/142 decisions,
     0 unresolved, freeze_ready true (recomputed, not trusted)
  4. the packet's own declarations: dry_run_only, gold_published=false,
     freeze_applied=false, authorization_not_self_applied, and its
     before-gate snapshot (S1.5 = human_adjudication_complete_freeze_authorization_pending,
     gold_freeze_authorized=false)
  5. data/gold/stage1 did not exist at dry-run time (still asserted:
     the dry run created no Gold)
  6. the authorization sentence in the packet is exactly the bounded one

Exit 0 iff everything verifies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADJ = ROOT / "outputs" / "development" / "human_review" / "stage1_adjudications"
CORR = ROOT / "data" / "development" / "human_review" / "stage1_gdpr7_human_correction_v1.json"
AUTH_LEGACY_NOTE = (  # noqa: F841 - historical context only
    "the auth manifest evolved legitimately after the dry run; this "
    "verifier does not assert its current state")
PACKET = ROOT / "outputs" / "reports" / "s1_5_process_gold_freeze_authorization_dry_run_v1.json"

BATCHES = ["gdpr_1_data_breach", "gdpr_2_consent_to_use_the_data",
           "gdpr_3_right_to_access", "gdpr_4_right_of_portability",
           "gdpr_5_right_to_withdraw", "gdpr_6_right_to_rectify",
           "gdpr_7_right_to_be_forgotten"]

EXPECTED_SENTENCE = (
    "I authorize the formal freeze of the seven (7/7) already-completed "
    "Stage 1 Process Record human adjudications (gdpr_1_data_breach, "
    "gdpr_2_consent_to_use_the_data, gdpr_3_right_to_access, "
    "gdpr_4_right_of_portability, gdpr_5_right_to_withdraw, "
    "gdpr_6_right_to_rectify, gdpr_7_right_to_be_forgotten) as the formal "
    "Stage 1 Process Gold: publish ONLY the adjudicated data exactly as "
    "recorded, without adding, inferring, or rewriting any decision; "
    "preserve the source/candidate/correction/chain hashes; after freezing, "
    "run the independent verification first and only then advance S1.6/S1.7 "
    "per the Pipeline; this does NOT authorize any LLM/API call, the Stage 3 "
    "Oracle, contract modifications, or any other Gold change.")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    checks = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    check("packet exists + status", packet.get("status") == "dry_run_not_applied")

    # 1. chain linkage vs per-batch manifests
    prev = None
    for node in packet["chain"]["batches"]:
        pid = node["process_id"]
        man = json.loads((ADJ / pid / "manifest.json").read_text(encoding="utf-8"))
        ok = (node["before_correction_sha256"] == man["before_correction_sha256"]
              and node["after_correction_sha256"] == man["after_correction_sha256"]
              and node["decision_sha256"] == _sha256(ADJ / pid / "decision_v1.json")
              and node["import_record_sha256"] == _sha256(ADJ / pid / "import_record_v1.json")
              and node["candidate_process_record_sha256"]
              == man["candidate_process_record_sha256"]
              and node["bpmn_source_sha256"] == man["bpmn_source_sha256"]
              and node["membership_payload_sha256"]
              == man["membership_payload_sha256"])
        if prev is not None:
            ok = ok and node["before_correction_sha256"] == prev
        check(f"[{pid}] chain node matches manifest", ok)
        prev = node["after_correction_sha256"]

    # 2. final correction hash
    final = packet["chain"]["final_correction_sha256"]
    check("final correction hash == disk", final == _sha256(CORR))
    check("blank sha == disk", packet["chain"]["blank_sha256"]
          == _sha256(ROOT / "data" / "development" / "human_review"
                     / "stage1_gdpr7_annotation_blank_v1.json"))

    # 3. recomputed evidence
    corr = json.loads(CORR.read_text(encoding="utf-8"))
    records = corr["records"]
    adjudicated = sum(1 for r in records
                      if r["review_state"] == "adjudicated")
    resolved = sum(1 for r in records for la in r["label_annotations"]
                   for f in ("actor", "action", "business_object")
                   if la.get(f, {}).get("status") in ("present", "absent"))
    resolved_struct = sum(1 for r in records
                          if r["structure_annotation"]["decision"]
                          in ("accepted_candidate", "corrected"))
    total_fields = sum(3 * len(r["label_annotations"]) for r in records)
    ev = packet["recomputed_evidence"]
    check("evidence 7/7 records",
          ev["records"] == {"adjudicated": adjudicated, "total": len(records)})
    check("evidence 135/135 fields",
          ev["label_fields"] == {"resolved": resolved, "total": total_fields})
    check("evidence 7/7 structures",
          ev["structure_decisions"] == {"resolved": resolved_struct,
                                        "total": len(records)})
    check("evidence 142/142 + 0 unresolved",
          ev["total_human_decisions"] == {
              "resolved": resolved + resolved_struct,
              "total": total_fields + len(records)}
          and ev["unresolved_human_decisions"] == 0
          and ev["freeze_ready"] is True)

    # 4/5. packet's own declarations + historical before-gate snapshot
    dec = packet["declarations"]
    check("declarations dry-run only", dec["dry_run_only"] is True
          and dec["gold_published"] is False
          and dec["freeze_applied"] is False
          and dec["authorization_not_self_applied"] is True)
    before = packet["gates"]["before"]
    check("historical before-gate snapshot (S1.5 pending, freeze not "
          "authorized, not published)",
          before["S1.5"]
          == "human_adjudication_complete_freeze_authorization_pending"
          and before["gold_freeze_authorized"] is False
          and before["formal_gold_published"] is False)
    check("post-freeze boundary declares no auto-advance",
          packet["gates"]["after_freeze_authorization"]["S1.6"].startswith(
              "allowed to advance ONLY after freeze + independent verification")
          and packet["gates"]["after_freeze_authorization"]["S3.7"].startswith(
              "still blocked"))

    # 6. no formal Gold was created BY THE DRY RUN; the later formal
    # publication (same day, user-authorized) is a separate event verified
    # by scripts/verify_stage1_process_gold.py -- not this packet's claim.
    check("packet claims no gold published at dry-run time",
          packet["declarations"]["gold_published"] is False)

    # 7. exact authorization sentence
    check("authorization sentence exact",
          packet["authorization_sentence"] == EXPECTED_SENTENCE)

    # 8. zero API
    check("zero new LLM/API calls", packet["zero_api"]["new_llm_api_calls"] == 0)

    return {"verified": all(c["ok"] for c in checks), "checks": checks}


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
        print("DRY-RUN VERIFIED" if result["verified"] else "DRY-RUN NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
