# -*- coding: utf-8 -*-
"""Generic incremental S1.5 human-adjudication verifier (fail-closed).

Reusable for all seven BPMN batches: re-reads every adjudication asset
under outputs/development/human_review/stage1_adjudications/<process>/
and the live correction file, then verifies (per process):

1. decision asset and manifest hashes consistent
2. target process_id unique across assets
3. correction record for the process exactly equals the decision
4. accepted_candidate's gold_process_record equals the locked candidate
   semantically (canonical_sha256 of the single record)
5. canonical candidate hash matches the manifest
6. all 18 label-field status/value pairs match exactly
7. other processes' records unchanged vs the pre-import baseline
   (blank template for never-imported ones; previous decision assets for
   already-imported ones)
8. membership / source / raw_label / lane_labels unchanged
9. summary counts consistent with content
10. any tamper (field value, extra field, candidate content, hash,
    summary, manifest) -> nonzero exit

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
    build_formal_process_records,
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


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def verify() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    correction = _load(CORRECTION)
    blank = _load(BLANK)
    membership = load_formal_membership_contract(MEMBERSHIP)
    locked_records = json.loads(PROCESS_RECORDS.read_text(encoding="utf-8"))[
        "records"]
    locked_by_id = {r["process_id"]: r for r in locked_records}
    blank_by_id = {r["process_id"]: r for r in blank.get("records", [])}
    corr_by_id = {r["process_id"]: r for r in correction.get("records", [])}

    # authorization baseline
    auth = _load(AUTH_MANIFEST)
    check("review surface authorization intact",
          auth.get("authorized_by_user") is True
          and auth.get("authorization_scope", {}).get(
              "gold_freeze_authorized") is False
          and auth.get("status") == "input_ready_freeze_blocked")
    check("membership payload", membership.get("membership", {}).get(
        "membership_payload_sha256") == EXPECTED_MEMBERSHIP_PAYLOAD)

    # discover adjudication assets
    if not ADJ_DIR.exists():
        check("adjudication assets present", False, "no assets dir")
        return {"verified": False, "checks": checks}
    process_dirs = sorted(d for d in ADJ_DIR.iterdir() if d.is_dir())
    check("assets exist", bool(process_dirs))
    ids = [d.name for d in process_dirs]
    check("process ids unique", len(ids) == len(set(ids)), str(ids))

    blank_summary = blank.get("review_summary", {})
    for pid_dir in process_dirs:
        pid = pid_dir.name
        decision_path = pid_dir / "decision_v1.json"
        manifest_path = pid_dir / "manifest.json"
        check(f"[{pid}] decision asset exists", decision_path.exists())
        check(f"[{pid}] manifest exists", manifest_path.exists())
        if not (decision_path.exists() and manifest_path.exists()):
            continue
        decision = _load(decision_path)
        manifest = _load(manifest_path)
        # 1. asset/manifest hash consistency
        check(f"[{pid}] decision asset hash == manifest",
              _sha256_file(decision_path)
              == manifest.get("decision_asset", {}).get("sha256"))
        # 2. process id consistency
        check(f"[{pid}] process id consistent",
              decision.get("process_id") == manifest.get("process_id") == pid)
        # 5. candidate canonical hash
        check(f"[{pid}] candidate hash matches",
              manifest.get("candidate_process_record_sha256")
              == decision.get("evidence_hashes", {}).get(
                  "candidate_process_record_sha256"))
        locked = locked_by_id.get(pid)
        if locked is not None:
            check(f"[{pid}] locked candidate hash exact",
                  canonical_sha256(locked)
                  == manifest.get("candidate_process_record_sha256"))
        # 3. correction record == decision (label annotations carry the
        #    immutable raw_label/lane_labels context from the blank template
        #    plus the user's three field decisions)
        blank_rec = blank_by_id.get(pid)
        d_la_by_id = {la["activity_id"]: la for la in
                      decision.get("label_annotations", [])}
        merged_las = []
        for b_la in (blank_rec or {}).get("label_annotations", []):
            merged = {"activity_id": b_la["activity_id"],
                      "raw_label": b_la["raw_label"],
                      "lane_labels": b_la["lane_labels"]}
            d_la = d_la_by_id.get(b_la["activity_id"], {})
            for f in FIELD_NAMES:
                merged[f] = d_la.get(f, {"status": "unreviewed", "value": None})
            merged_las.append(merged)
        corr_rec = corr_by_id.get(pid)
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
        check(f"[{pid}] correction record == decision",
              corr_rec == expected_rec,
              "record mismatch" if corr_rec != expected_rec else "")
        # 4. gold_process_record == locked candidate semantically
        gold = decision.get("structure_annotation", {}).get(
            "gold_process_record")
        if decision.get("structure_annotation", {}).get("decision") \
                == "accepted_candidate":
            gold_ok = gold is not None and canonical_sha256(gold) \
                == canonical_sha256(locked)
            check(f"[{pid}] gold_process_record == locked candidate",
                  gold_ok)
        # 6. 18 fields exact
        field_ok = True
        detail = ""
        la_by_id = {la["activity_id"]: la for la in
                    decision.get("label_annotations", [])}
        for la in corr_rec.get("label_annotations", []):
            d_la = la_by_id.get(la["activity_id"])
            if d_la is None:
                field_ok = False
                continue
            for f in FIELD_NAMES:
                if la.get(f) != d_la.get(f):
                    field_ok = False
                    detail = f"{la['activity_id']}.{f}"
        check(f"[{pid}] 18 fields exact (6 activities x 3)", field_ok, detail)
        # 8. membership/source/raw_label/lane_labels unchanged
        blank_rec = blank_by_id.get(pid)
        ctx_ok = True
        if blank_rec is not None:
            for la in corr_rec.get("label_annotations", []):
                b_la = next((x for x in blank_rec["label_annotations"]
                             if x["activity_id"] == la["activity_id"]), None)
                if b_la is None or b_la["raw_label"] != la["raw_label"] \
                        or b_la["lane_labels"] != la["lane_labels"]:
                    ctx_ok = False
        check(f"[{pid}] raw_label/lane_labels unchanged", ctx_ok)
        check(f"[{pid}] source binding unchanged",
              corr_rec.get("source", {}).get("sha256")
              == locked.get("source", {}).get("sha256"))

    # 7. other processes' records unchanged vs blank
    others_ok = True
    for rec in correction.get("records", []):
        if rec["process_id"] in ids:
            continue
        blank_rec = blank_by_id.get(rec["process_id"])
        if blank_rec is not None and rec != blank_rec:
            others_ok = False
    check("other processes unchanged vs blank", others_ok)

    # 9. summary consistency
    summary = correction.get("review_summary", {})
    adjudicated = sum(1 for r in correction.get("records", [])
                      if r.get("review_state") == "adjudicated")
    resolved = sum(1 for r in correction.get("records", [])
                   for la in r.get("label_annotations", [])
                   for f in FIELD_NAMES
                   if la.get(f, {}).get("status") in ("present", "absent"))
    summary_ok = (summary.get("records") == len(correction.get("records", []))
                  and summary.get("adjudicated_records") == adjudicated
                  and summary.get("label_fields") == 135
                  and summary.get("resolved_label_fields") == resolved
                  and summary.get("freeze_ready") is False)
    check("summary consistent (and freeze false)", summary_ok,
          json.dumps(summary))

    # freeze must not be open
    check("freeze_ready false", summary.get("freeze_ready") is False)

    verified = all(c["ok"] for c in checks)
    return {"verified": verified, "checks": checks,
            "adjudicated_processes": ids}


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
