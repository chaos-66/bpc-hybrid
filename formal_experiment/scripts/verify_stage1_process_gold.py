# -*- coding: utf-8 -*-
"""Fail-closed verifier for the published Stage 1 Process Gold (2026-08-13).

Recomputes everything from disk:
  1. gold artifact exists and its hash matches the publication manifest
  2. every published record is byte-equal to the adjudicated correction
     record (process_id/source/review_state/structure/gold/labels) -- NO
     added, inferred or rewritten decision
  3. every accepted_candidate gold_process_record is canonical-equal to the
     locked candidate
  4. the freeze-authorization manifest: exact user sentence, authorized,
     evidence hashes (correction/blank/membership/chain) match disk
  5. preserved hashes in the publication manifest (blank/correction/
     membership/chain) are recomputed and match
  6. the seven-batch adjudication chain still verifies
  7. data/gold/stage1 contains ONLY the published artifact + manifest
     (no other Gold created)

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
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_formal_dataset import canonical_sha256  # noqa: E402

CORR = ROOT / "data" / "development" / "human_review" / "stage1_gdpr7_human_correction_v1.json"
BLANK = ROOT / "data" / "development" / "human_review" / "stage1_gdpr7_annotation_blank_v1.json"
RECS = ROOT / "data" / "development" / "human_review" / "stage1_gdpr7_process_records_v1.json"
MEMBERSHIP = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
ADJ = ROOT / "outputs" / "development" / "human_review" / "stage1_adjudications"
GOLD = ROOT / "data" / "gold" / "stage1" / "process_records" / "stage1_process_gold_v1.json"
GOLD_MANIFEST = ROOT / "data" / "gold" / "stage1" / "manifest.json"
AUTH_MANIFEST = ROOT / "outputs" / "reports" / "s1_5_process_gold_freeze_authorization_v1.manifest.json"
CHAIN_VERIFIER = ROOT / "scripts" / "verify_stage1_human_adjudication.py"

BATCHES = ["gdpr_1_data_breach", "gdpr_2_consent_to_use_the_data",
           "gdpr_3_right_to_access", "gdpr_4_right_of_portability",
           "gdpr_5_right_to_withdraw", "gdpr_6_right_to_rectify",
           "gdpr_7_right_to_be_forgotten"]

EXPECTED_SENTENCE = (
    "I authorize the formal freeze of the seven (7/7) Stage 1 Process Record "
    "human adjudications as the formal Stage 1 Process Gold: publish ONLY "
    "the adjudicated data exactly as recorded, without adding, inferring, or "
    "rewriting any decision; preserve the source/candidate/correction/"
    "seven-batch chain hashes; after freezing, run the independent "
    "verification first and only then advance the Sun/Leopold-style P2 "
    "method-level independent reconstruction, the S1.6 formal evaluation "
    "and S1.7 per the Pipeline. Project adaptations for unavailable raw "
    "data and non-public paper parameters are allowed ONLY as pre-locked, "
    "fully disclosed adaptations: never tune with the formal Gold, never "
    "present P0/P1 as P2, never claim exact reproduction. This "
    "authorization does NOT include any LLM/API call, the Stage 3 Oracle, "
    "experiment contract modifications, or any other Gold change.")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_chain_verifier():
    spec = importlib.util.spec_from_file_location(
        "s1ad_gold_chain", CHAIN_VERIFIER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s1ad_gold_chain"] = module
    spec.loader.exec_module(module)
    return module


def verify() -> dict:
    checks = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    # 1. artifact + manifest hashes
    check("gold artifact exists", GOLD.exists())
    check("gold manifest exists", GOLD_MANIFEST.exists())
    check("authorization manifest exists", AUTH_MANIFEST.exists())
    if not (GOLD.exists() and GOLD_MANIFEST.exists()):
        return {"verified": False, "checks": checks}
    pub = json.loads(GOLD_MANIFEST.read_text(encoding="utf-8"))
    art = pub.get("artifacts", {}).get(
        "data/gold/stage1/process_records/stage1_process_gold_v1.json", {})
    check("gold artifact hash == manifest",
          art.get("sha256") == _sha256(GOLD)
          and art.get("byte_size") == GOLD.stat().st_size)

    # 2. gold records == correction records (byte-field equal, ordered)
    corr = json.loads(CORR.read_text(encoding="utf-8"))
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    corr_by_id = {r["process_id"]: r for r in corr["records"]}
    gold_by_id = {r["process_id"]: r for r in gold.get("records", [])}
    check("gold record set == correction set",
          sorted(gold_by_id) == sorted(corr_by_id) == BATCHES)
    rec_ok = True
    for pid in BATCHES:
        if gold_by_id.get(pid) != corr_by_id.get(pid):
            rec_ok = False
    check("every gold record == adjudicated correction record", rec_ok,
          "no added/inferred/rewritten decision")

    # 3. gold_process_record canonical == locked candidate (per process)
    locked = {r["process_id"]: r for r in json.loads(
        RECS.read_text(encoding="utf-8"))["records"]}
    gold_canon_ok = True
    for pid in BATCHES:
        rec = gold_by_id.get(pid)
        gpr = None
        if rec is not None:
            gpr = rec.get("structure_annotation", {}).get(
                "gold_process_record")
        if gpr is None or canonical_sha256(gpr) != canonical_sha256(locked[pid]):
            gold_canon_ok = False
    check("gold_process_record == locked candidate (canonical)",
          gold_canon_ok)

    # 4. authorization manifest exact
    auth = json.loads(AUTH_MANIFEST.read_text(encoding="utf-8"))
    check("authorized by user", auth.get("authorized_by_user") is True)
    check("authorization sentence exact",
          auth.get("authorization_sentence") == EXPECTED_SENTENCE)
    ev = auth.get("evidence", {})
    check("auth evidence: correction sha",
          ev.get("correction_sha256") == _sha256(CORR))
    check("auth evidence: blank sha",
          ev.get("blank_sha256") == _sha256(BLANK))
    check("auth evidence: chain hashes",
          ev.get("chain") == pub.get("preserved_hashes", {}).get("chain"))
    memb = json.loads(MEMBERSHIP.read_text(encoding="utf-8"))
    check("auth evidence: membership payload",
          ev.get("membership_payload_sha256")
          == memb["membership"]["membership_payload_sha256"]
          == pub.get("preserved_hashes", {}).get("membership_payload_sha256"))

    # 5. publication manifest preserved hashes recomputed
    check("pub manifest: correction sha",
          pub.get("preconditions_verified", {}).get("correction_sha256")
          == _sha256(CORR))
    check("pub manifest: blank sha",
          pub.get("preserved_hashes", {}).get("blank_sha256")
          == _sha256(BLANK))
    check("pub manifest: authorization bound",
          pub.get("authorization", {}).get("sha256") == _sha256(AUTH_MANIFEST))

    # 6. seven-batch chain still verifies
    try:
        chain_ok = _load_chain_verifier().verify()["verified"] is True
    except Exception as exc:  # pragma: no cover - defensive
        chain_ok = False
        check("seven-batch chain verifier runs", False, str(exc))
    check("seven-batch chain verifier passes", chain_ok)

    # 7. data/gold/stage1 contains only the published artifact + manifest
    stage1_dir = GOLD.parent.parent
    expected = {"manifest.json", "process_records"}
    check("data/gold/stage1 only published content",
          {p.name for p in stage1_dir.iterdir()} == expected)
    check("data/gold/stage1/process_records only one artifact",
          [p.name for p in GOLD.parent.iterdir()]
          == ["stage1_process_gold_v1.json"])

    # 8. zero API + boundaries
    check("zero new LLM/API calls",
          auth.get("zero_api", {}).get("new_llm_api_calls") == 0
          and pub.get("zero_api", {}).get("new_llm_api_calls") == 0)
    check("exact reproduction claim forbidden",
          auth.get("scope", {}).get("p2_adaptation_boundary", "").find(
              "exact reproduction") >= 0)

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
        print("PROCESS GOLD VERIFIED" if result["verified"]
              else "PROCESS GOLD NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
