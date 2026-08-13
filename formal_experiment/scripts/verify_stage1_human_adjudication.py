# -*- coding: utf-8 -*-
"""Generic incremental S1.5 human-adjudication CHAIN verifier (fail-closed).

Reusable for all seven BPMN batches. Rebuilds the adjudication state chain
from the immutable blank baseline and verifies (per process, in stable
order gdpr_1..gdpr_7):

1. decision asset and manifest hashes consistent (from disk)
2. process_id unique; activity ID set == locked candidate (no missing /
   duplicate / extra activity)
3. field count DERIVED from the candidate (3 x activities; never hardcoded)
4. correction record for the process exactly equals the replay of the
   decision (mechanical, field by field)
5. accepted_candidate's gold_process_record == locked candidate (canonical)
6. candidate hash == manifest == decision evidence hash
7. all field status/value pairs match the decision; values schema-valid
8. other (not yet adjudicated) processes unchanged vs the blank template
9. chain integrity: batch N's before_correction_sha256 == previous state
   hash; replay(before + import) == after_correction_sha256; the final
   after hash == the on-disk correction file hash; no fork/broken/cyclic
   chain
10. import_record bound (hash recorded in the manifest and recomputed)
11. summary counts consistent; freeze_ready true only at 7/7 + 135/135;
    formal Gold freeze stays unauthorized (gold_freeze_authorized=false,
    authorization status human_adjudication_complete_freeze_authorization_pending)
12. any tamper -> nonzero exit

Exit 0 iff everything verifies.
"""

from __future__ import annotations

import argparse
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
    canonical_sha256,
    load_formal_membership_contract,
)

MEMBERSHIP = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
PROCESS_RECORDS = (ROOT / "data" / "development" / "human_review"
                   / "stage1_gdpr7_process_records_v1.json")
CORRECTION = (ROOT / "data" / "development" / "human_review"
              / "stage1_gdpr7_human_correction_v1.json")
BLANK = (ROOT / "data" / "development" / "human_review"
         / "stage1_gdpr7_annotation_blank_v1.json")
ADJ_DIR = (ROOT / "outputs" / "development" / "human_review"
           / "stage1_adjudications")
AUTH_MANIFEST = (ROOT / "outputs" / "reports"
                 / "s1_5_review_surface_authorization_v1.manifest.json")

EXPECTED_MEMBERSHIP_PAYLOAD = (
    "e88caf8157c4e6e5c2d789ed0f2b6bbac2aac2e89d2384db7762549751a1663d")
FIELD_NAMES = ("actor", "action", "business_object")
# stable adjudication order for the chain
STABLE_ORDER = (
    "gdpr_1_data_breach", "gdpr_2_consent_to_use_the_data",
    "gdpr_3_right_to_access", "gdpr_4_right_of_portability",
    "gdpr_5_right_to_withdraw", "gdpr_6_right_to_rectify",
    "gdpr_7_right_to_be_forgotten")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _canonical_doc_bytes(doc: dict[str, Any]) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _apply_record(base: dict[str, Any], record: dict[str, Any],
                  blank_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Apply one adjudicated record onto a correction doc and recompute the
    summary (pure function matching the review tool's import semantics:
    the immutable raw_label/lane_labels context from the blank template is
    merged in, exactly like stage1_review_tool.py does)."""
    doc = json.loads(json.dumps(base, ensure_ascii=False))
    records = doc.get("records", [])
    blank_rec = blank_by_id.get(record["process_id"], {})
    blank_las = {la["activity_id"]: la for la in
                 blank_rec.get("label_annotations", [])}
    applied = json.loads(json.dumps(record, ensure_ascii=False))
    merged_las = []
    for la in applied.get("label_annotations", []):
        merged = {"activity_id": la["activity_id"]}
        b_la = blank_las.get(la["activity_id"], {})
        merged["raw_label"] = b_la.get("raw_label")
        merged["lane_labels"] = b_la.get("lane_labels", [])
        for f in FIELD_NAMES:
            merged[f] = la.get(f, {"status": "unreviewed", "value": None})
        merged_las.append(merged)
    applied["label_annotations"] = merged_las
    for i, r in enumerate(records):
        if r["process_id"] == record["process_id"]:
            records[i] = applied
            break
    label_fields = 0
    resolved = 0
    adjudicated = 0
    for r in records:
        if r.get("review_state") == "adjudicated":
            adjudicated += 1
        for la in r.get("label_annotations", []):
            label_fields += 3
            for f in FIELD_NAMES:
                if la.get(f, {}).get("status") in ("present", "absent"):
                    resolved += 1
    doc["review_summary"] = {
        "records": len(records),
        "adjudicated_records": adjudicated,
        "label_fields": label_fields,
        "resolved_label_fields": resolved,
        "freeze_ready": bool(adjudicated == len(records)
                             and resolved == label_fields and len(records) > 0),
    }
    return doc


def verify() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    blank = _load(BLANK)
    correction = _load(CORRECTION)
    correction_bytes = CORRECTION.read_bytes()
    blank_bytes = BLANK.read_bytes()
    membership = load_formal_membership_contract(MEMBERSHIP)
    locked_records = json.loads(PROCESS_RECORDS.read_text(encoding="utf-8"))[
        "records"]
    locked_by_id = {r["process_id"]: r for r in locked_records}
    blank_by_id = {r["process_id"]: r for r in blank.get("records", [])}
    corr_by_id = {r["process_id"]: r for r in correction.get("records", [])}

    auth = _load(AUTH_MANIFEST)
    check("review surface authorization intact",
          auth.get("authorized_by_user") is True
          and auth.get("authorization_scope", {}).get(
              "gold_freeze_authorized") is False
          and auth.get("status")
          == "human_adjudication_complete_freeze_authorization_pending")
    check("membership payload", membership.get("membership", {}).get(
        "membership_payload_sha256") == EXPECTED_MEMBERSHIP_PAYLOAD)

    # discover adjudicated processes (stable order)
    if not ADJ_DIR.exists():
        check("adjudication assets present", False, "no assets dir")
        return {"verified": False, "checks": checks}
    process_dirs = {d.name: d for d in ADJ_DIR.iterdir() if d.is_dir()}
    adjudicated_pids = [p for p in STABLE_ORDER if p in process_dirs]
    check("adjudicated processes unique+ordered",
          adjudicated_pids == sorted(adjudicated_pids), str(adjudicated_pids))
    check("assets exist", bool(adjudicated_pids))

    # ---- chain replay ---------------------------------------------------
    replay_base = json.loads(blank_bytes.decode("utf-8"))
    prev_sha = _sha256_bytes(blank_bytes)
    final_replay_sha = None
    seen_before: set[str] = set()
    for pid in adjudicated_pids:
        d = process_dirs[pid]
        decision_path = d / "decision_v1.json"
        manifest_path = d / "manifest.json"
        import_path = d / "import_record_v1.json"
        check(f"[{pid}] decision asset exists", decision_path.exists())
        check(f"[{pid}] manifest exists", manifest_path.exists())
        check(f"[{pid}] import record exists", import_path.exists())
        if not (decision_path.exists() and manifest_path.exists()
                and import_path.exists()):
            continue
        decision = _load(decision_path)
        manifest = _load(manifest_path)
        import_record = _load(import_path)

        # 1. hashes from disk
        check(f"[{pid}] decision hash == manifest",
              _sha256_file(decision_path)
              == manifest.get("decision_asset", {}).get("sha256"))
        check(f"[{pid}] import record hash bound",
              _sha256_file(import_path)
              == manifest.get("import_record_sha256"))
        check(f"[{pid}] membership payload hash == expected",
              manifest.get("membership_payload_sha256")
              == EXPECTED_MEMBERSHIP_PAYLOAD)
        check(f"[{pid}] process id consistent",
              decision.get("process_id") == manifest.get("process_id") == pid)
        check(f"[{pid}] candidate hash matches",
              manifest.get("candidate_process_record_sha256")
              == decision.get("evidence_hashes", {}).get(
                  "candidate_process_record_sha256"))
        locked = locked_by_id.get(pid)
        if locked is not None:
            check(f"[{pid}] locked candidate hash exact",
                  canonical_sha256(locked)
                  == manifest.get("candidate_process_record_sha256"))
            check(f"[{pid}] bpmn source hash == locked",
                  manifest.get("bpmn_source_sha256")
                  == locked.get("source", {}).get("sha256"))

        # 2. chain: before == prev state hash
        before_ok = manifest.get("before_correction_sha256") == prev_sha
        check(f"[{pid}] chain before == previous state", before_ok,
              f"manifest={str(manifest.get('before_correction_sha256'))[:12]} "
              f"prev={prev_sha[:12]}")
        if manifest.get("before_correction_sha256") in seen_before:
            check(f"[{pid}] chain no shared predecessor", False,
                  "duplicate before hash (fork)")
        seen_before.add(manifest.get("before_correction_sha256"))

        # 3. activity set == candidate
        cand_ids = [a["id"] for a in (locked or {}).get("activities", [])]
        imp_ids = [la["activity_id"] for la in
                   import_record.get("records", [{}])[0].get(
                       "label_annotations", [])]
        dec_ids = [la["activity_id"] for la in
                   decision.get("label_annotations", [])]
        check(f"[{pid}] activity ids == candidate",
              sorted(imp_ids) == sorted(cand_ids)
              and sorted(dec_ids) == sorted(cand_ids),
              f"cand={len(cand_ids)} imp={len(imp_ids)} dec={len(dec_ids)}")
        field_count = 3 * len(cand_ids)
        check(f"[{pid}] field count derived ({field_count})",
              len(import_record.get("records", [{}])[0].get(
                  "label_annotations", [])) * 3 == field_count)

        # 4. replay application -> after hash
        rec = import_record.get("records", [{}])[0]
        replay_base = _apply_record(replay_base, rec, blank_by_id)
        after_sha = _sha256_bytes(_canonical_doc_bytes(replay_base))
        after_ok = manifest.get("after_correction_sha256") == after_sha
        check(f"[{pid}] replay(before+import) == after hash", after_ok,
              f"replay={after_sha[:12]}")
        prev_sha = after_sha

        # 5. correction record == replay record
        corr_rec = corr_by_id.get(pid)
        blank_rec = blank_by_id.get(pid)
        merged_las = []
        d_la_by_id = {la["activity_id"]: la for la in
                      decision.get("label_annotations", [])}
        for b_la in (blank_rec or {}).get("label_annotations", []):
            merged = {"activity_id": b_la["activity_id"],
                      "raw_label": b_la["raw_label"],
                      "lane_labels": b_la["lane_labels"]}
            d_la = d_la_by_id.get(b_la["activity_id"], {})
            for f in FIELD_NAMES:
                merged[f] = d_la.get(f, {"status": "unreviewed", "value": None})
            merged_las.append(merged)
        expected_rec = {
            "process_id": pid,
            "source": {"path": locked["source"]["path"],
                       "sha256": locked["source"]["sha256"],
                       "process_record_sha256":
                           manifest.get("candidate_process_record_sha256")},
            "review_state": decision["review_state"],
            "structure_annotation": decision["structure_annotation"],
            "label_annotations": merged_las,
        }
        check(f"[{pid}] correction record == decision", corr_rec == expected_rec)
        if corr_rec is None:
            check(f"[{pid}] correction record present", False,
                  "record missing from correction (cross-process tamper?)")
            continue

        # 6. gold == locked candidate (accepted_candidate)
        gold = decision.get("structure_annotation", {}).get(
            "gold_process_record")
        if decision.get("structure_annotation", {}).get("decision") \
                == "accepted_candidate":
            check(f"[{pid}] gold == locked candidate",
                  gold is not None and canonical_sha256(gold)
                  == canonical_sha256(locked))

        # 7. fields exact + schema-valid
        field_ok = True
        detail = ""
        for la in corr_rec.get("label_annotations", []):
            d_la = d_la_by_id.get(la["activity_id"])
            if d_la is None:
                field_ok = False
                continue
            for f in FIELD_NAMES:
                st = la.get(f, {}).get("status")
                val = la.get(f, {}).get("value")
                if la.get(f) != d_la.get(f):
                    field_ok = False
                    detail = f"{la['activity_id']}.{f}"
                if st not in ("unreviewed", "present", "absent",
                              "needs_adjudication"):
                    field_ok = False
                if st == "present" and (not isinstance(val, str) or not val):
                    field_ok = False
                if st in ("absent", "unreviewed") and val is not None:
                    field_ok = False
        check(f"[{pid}] fields exact + schema-valid", field_ok, detail)

        # 8. context unchanged
        ctx_ok = True
        for la in corr_rec.get("label_annotations", []):
            b_la = next((x for x in (blank_rec or {}).get(
                "label_annotations", [])
                if x["activity_id"] == la["activity_id"]), None)
            if b_la is None or b_la["raw_label"] != la["raw_label"] \
                    or b_la["lane_labels"] != la["lane_labels"]:
                ctx_ok = False
        check(f"[{pid}] raw_label/lane_labels unchanged", ctx_ok)
        check(f"[{pid}] source binding unchanged",
              corr_rec.get("source", {}).get("sha256")
              == locked.get("source", {}).get("sha256"))

    # ---- final replay state == on-disk correction ------------------------
    final_replay_sha = prev_sha
    disk_sha = _sha256_bytes(correction_bytes)
    check("final replay == on-disk correction hash",
          final_replay_sha == disk_sha,
          f"replay={final_replay_sha[:12]} disk={disk_sha[:12]}")
    check("final replay == on-disk correction content",
          _canonical_doc_bytes(replay_base) == correction_bytes)

    # ---- unadjudicated processes unchanged vs blank ----------------------
    others_ok = True
    for rec in correction.get("records", []):
        if rec["process_id"] in adjudicated_pids:
            continue
        blank_rec = blank_by_id.get(rec["process_id"])
        if blank_rec is not None and rec != blank_rec:
            others_ok = False
    check("unadjudicated processes unchanged vs blank", others_ok)

    # ---- summary ----------------------------------------------------------
    summary = correction.get("review_summary", {})
    adjudicated = sum(1 for r in correction.get("records", [])
                      if r.get("review_state") == "adjudicated")
    resolved = sum(1 for r in correction.get("records", [])
                   for la in r.get("label_annotations", [])
                   for f in FIELD_NAMES
                   if la.get(f, {}).get("status") in ("present", "absent"))
    resolved_struct = sum(
        1 for r in correction.get("records", [])
        if r.get("structure_annotation", {}).get("decision")
        in ("accepted_candidate", "corrected"))
    summary_ok = (summary.get("records") == len(correction.get("records", []))
                  and summary.get("adjudicated_records") == adjudicated
                  and summary.get("label_fields") == 135
                  and summary.get("resolved_label_fields") == resolved)
    check("summary consistent", summary_ok, json.dumps(summary))
    # Adjudication-completeness fact: in a world where ALL records are
    # adjudicated and ALL fields resolved (7/7 + 135/135 in the real
    # dataset), freeze_ready must be true and 0 decisions unresolved; in a
    # partially adjudicated world (e.g. synthetic replay worlds with 2/7)
    # freeze_ready must be false. Either way the fact is DERIVED from the
    # records, never trusted from the summary. Formal Gold freeze still
    # requires explicit user authorization (checked separately below).
    total_fields = sum(3 * len(r.get("label_annotations", []))
                       for r in correction.get("records", []))
    world_complete = (adjudicated == len(correction.get("records", []))
                      and resolved == total_fields
                      and len(correction.get("records", [])) > 0)
    if world_complete:
        complete_ok = (summary.get("freeze_ready") is True
                       and resolved_struct == len(correction.get(
                           "records", [])))
        detail = "complete world: freeze_ready must be true"
    else:
        complete_ok = summary.get("freeze_ready") is False
        detail = "partial world: freeze_ready must be false"
    check("adjudication completeness fact consistent (freeze_ready "
          "derived)", complete_ok, detail + " " + json.dumps(summary))
    check("formal gold freeze NOT authorized",
          auth.get("authorization_scope", {}).get(
              "gold_freeze_authorized") is False
          and auth.get("status")
          == "human_adjudication_complete_freeze_authorization_pending")

    verified = all(c["ok"] for c in checks)
    return {"verified": verified, "checks": checks,
            "adjudicated_processes": adjudicated_pids,
            "chain": {"start_sha": _sha256_bytes(blank_bytes),
                      "final_replay_sha": final_replay_sha}}


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
        print("VERIFIED" if result["verified"] else "NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
