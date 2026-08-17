# -*- coding: utf-8 -*-
"""S2.11 canonical batch accept/revisions importer v2 (Checkpoint E2).

Imports the 36 canonical proposal v2 payloads into the v2 decisions file
("accept-all with listed revisions").

DRY-RUN (default, the ONLY mode executed this round):
  * binds the proposal v2 file SHA-256 (proposal_file_sha256 in the
    committed proposal report v2)
  * validates the 36-sample membership + all hashes
  * builds the would-be decisions v2 (canonical payloads with
    present/absent statuses; zero unresolved; spans as coordinates only;
    text re-verified slice-equal against the hash-bound source)
  * acceptance: blocked fields = 0, blocked samples = 0,
    unresolved fields = 0, adjudicable = 36/36, freeze-validator
    structure checks pass
  * writes a LOCAL would-be decisions file + a COMMITTED dry-run report
    (hashes/counts only)

APPLY (refused this round - no user confirmation event exists):
  * requires a user confirmation event that EXACTLY binds the proposal v2
    SHA, the optional revisions SHA and the reviewer name
  * atomic write with a pre-write backup of the decisions file
  * reviewer is taken ONLY from the confirmation event (never invented)
  * any hash drift / mismatch refuses with exit 2 and writes nothing

This round: dry-run only; no confirmation event is created; --apply is
never executed; no Gold is created or published; freeze stays false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.s2_11_canonical_v2 import (  # noqa: E402
    MODALITY_LABELS,
    ORDINARY_FIELDS,
    validate,
)

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
PROPOSAL_REPORT_V2_REL = "outputs/reports/s2_11_proposal_report_v2.json"
DECISIONS_V2_REL = "data/development/human_review/s2_11_review_decisions_v2.json"
BLANK_REVIEW_V2_REL = "data/development/human_review/s2_11_blank_review_v2.json"
CONFIRMATION_EVENT_REL = \
    "configs/s2_11_batch_import_confirmation_event_v2.json"
LOCAL_DIR = ROOT / "outputs" / "development" / "s2_11_local_working" / \
    "batch_import_v2_dry_run"
LOCAL_WOULD_BE_REL = "would_be_decisions_v2.json"
DRY_RUN_REPORT_REL = "outputs/reports/s2_11_batch_import_dry_run_v2.json"

ALL_FIELDS = ("modality",) + ORDINARY_FIELDS


class ImportFail(Exception):
    """Fail-closed import abort."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() == data:
            return
        raise ImportFail(
            f"refusing to overwrite different existing content: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _load_source_text(sample_id: str, rec: dict[str, Any]) -> str:
    src = ROOT.parent / rec["path"]
    raw = src.read_bytes()
    if _sha256_bytes(raw) != rec["file_sha256"]:
        raise ImportFail(f"source file hash drift for {sample_id}")
    scenario, rid, version = sample_id.split("/")
    doc = json.loads(raw.decode("utf-8"))
    for entry in doc:
        if str(entry.get("ID")) == rid and \
                str(entry.get("version")) == version.lstrip("v"):
            text = str(entry.get("text", ""))
            if _sha256_bytes(text.encode("utf-8")) != rec["text_sha256"]:
                raise ImportFail(f"text hash drift for {sample_id}")
            return text
    raise ImportFail(f"record {sample_id} not found in source")


def _strip_text(canonical: dict[str, Any]) -> dict[str, Any]:
    import copy
    out = copy.deepcopy(canonical)
    for clause in out.get("clauses", []):
        clause["clause_span"].pop("text", None)
        for ev in clause["modality"]["evidence"]:
            ev.pop("text", None)
            ev.pop("confidence", None)
        for field in ORDINARY_FIELDS:
            for span in clause[field]["spans"]:
                span.pop("text", None)
                span.pop("confidence", None)
    return out


def _load_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any],
                            dict[str, Any]]:
    membership = _load_json(ROOT / MEMBERSHIP_REL)
    report = _load_json(ROOT / PROPOSAL_REPORT_V2_REL)
    if int(membership["record_count"]) != 40 or \
            len(membership["quarantine"]) != 4 or \
            len(membership["records"]) != 36:
        raise ImportFail("membership must be 40/4/36")
    if report.get("coverage") != "36/36" or \
            int(report.get("proposal_count", 0)) != 36:
        raise ImportFail("proposal report v2 coverage must be 36/36")
    if set(report.get("entries") or {}) != set(membership["records"]):
        raise ImportFail("proposal report v2 sample set mismatch")
    local_rel = str(report.get("proposal_file"))
    local_path = ROOT / local_rel
    if not local_path.is_file():
        raise ImportFail(f"local proposals v2 file missing: {local_rel}")
    local_bytes = local_path.read_bytes()
    if _sha256_bytes(local_bytes) != report.get("proposal_file_sha256"):
        raise ImportFail("local proposals v2 SHA-256 does not match the "
                         "proposal report v2 binding")
    lines = [ln for ln in local_bytes.decode("utf-8").splitlines() if ln]
    if len(lines) != 36:
        raise ImportFail(f"local proposals v2 must have 36 lines, "
                         f"got {len(lines)}")
    proposals: dict[str, Any] = {}
    for ln in lines:
        entry = json.loads(ln)
        sid = entry.get("sample_id")
        rec = membership["records"].get(sid)
        if rec is None:
            raise ImportFail(f"local proposal for unknown sample {sid!r}")
        if entry.get("text_sha256") != rec["text_sha256"] or \
                entry.get("file_sha256") != rec["file_sha256"]:
            raise ImportFail(f"local proposal hash drift for {sid}")
        if entry.get("human_approved") is not False or \
                entry.get("gold") is not False or \
                entry.get("reviewer") is not None:
            raise ImportFail(f"local proposal {sid} must stay "
                             "human_approved=false, gold=false, "
                             "reviewer=null")
        proposals[sid] = entry
    return membership, report, proposals, local_path


def _apply_revisions(canonical: dict[str, Any], sample_id: str,
                     text: str, rev: dict[str, Any]) -> list[str]:
    """Apply per-field revisions; returns problems (empty == ok)."""
    problems: list[str] = []
    for field, spec in rev.items():
        if field not in ALL_FIELDS:
            problems.append(f"{sample_id}: revision for unknown field "
                            f"{field!r}")
            continue
        if spec == "absent" or (isinstance(spec, dict)
                                and spec.get("status") == "absent"):
            for clause in canonical["clauses"]:
                if field == "modality":
                    clause["modality"] = {"status": "absent", "label": None,
                                          "evidence": []}
                else:
                    clause[field] = {"status": "absent", "spans": []}
            continue
        if not isinstance(spec, dict) or spec.get("status") != "present":
            problems.append(f"{sample_id}:{field} revision must be "
                            "'absent' or {status: present, ...}")
            continue
        if field == "modality":
            label = spec.get("label")
            if label not in MODALITY_LABELS:
                problems.append(f"{sample_id}: bad modality label {label!r}")
                continue
            evidence = spec.get("evidence") or []
            spans = []
            for ei, ev_text in enumerate(evidence):
                start = 0
                found = False
                while True:
                    i = text.find(ev_text, start)
                    if i < 0:
                        break
                    assert text[i:i + len(ev_text)] == ev_text
                    spans.append({
                        "id": f"{sample_id.replace('/', '_')}_rev_modev_"
                              f"{ei}_{i}",
                        "start": i, "end": i + len(ev_text),
                    })
                    start = i + 1
                    found = True
                if not found:
                    problems.append(
                        f"{sample_id}: modality evidence {ev_text!r} not "
                        "in source text")
            if not problems:
                for clause in canonical["clauses"]:
                    clause["modality"] = {"status": "present", "label": label,
                                          "evidence": list(spans)}
            continue
        values = spec.get("values") or []
        spans = []
        for vi, value in enumerate(values):
            start = 0
            found = False
            while True:
                i = text.find(value, start)
                if i < 0:
                    break
                assert text[i:i + len(value)] == value
                spans.append({
                    "id": f"{sample_id.replace('/', '_')}_rev_{field}_{vi}_"
                          f"{i}",
                    "start": i, "end": i + len(value),
                })
                start = i + 1
                found = True
            if not found:
                problems.append(
                    f"{sample_id}:{field} revision {value!r} not an exact "
                    "substring of the source text")
        if spans:
            for clause in canonical["clauses"]:
                clause[field] = {"status": "present", "spans": list(spans)}
        elif not problems:
            problems.append(f"{sample_id}:{field} revision has no values")
    return problems


def build_would_be(revisions: dict[str, Any]) -> tuple[dict[str, Any],
                                                       dict[str, Any],
                                                       list[str]]:
    """Returns (would_be_doc, stats, problems). Fail-closed: any problem
    raises ImportFail instead of returning."""
    membership, report, proposals, local_path = _load_inputs()
    records: dict[str, Any] = {}
    stats = {"samples": 0, "blocked_fields": 0, "blocked_samples": 0,
             "unresolved_fields": 0, "adjudicable": 0}
    for sample_id in sorted(membership["records"]):
        rec = membership["records"][sample_id]
        text = _load_source_text(sample_id, rec)
        proposal = proposals[sample_id]
        canonical = _strip_text(proposal["canonical"])
        rev = revisions.get(sample_id) or {}
        if rev:
            problems = _apply_revisions(canonical, sample_id, text, rev)
            if problems:
                raise ImportFail(
                    "revisions invalid: " + "; ".join(problems))
        unresolved = 0
        for clause in canonical["clauses"]:
            if clause["modality"]["status"] == "unresolved":
                unresolved += 1
            for field in ORDINARY_FIELDS:
                if clause[field]["status"] == "unresolved":
                    unresolved += 1
        records[sample_id] = {
            "review_metadata": {
                "review_state": "reviewed",
                "reviewer": None,
                "confirmation_event": None,
            },
            "canonical": canonical,
        }
        stats["samples"] += 1
        stats["unresolved_fields"] += unresolved
        stats["adjudicable"] += 1 if unresolved == 0 else 0

    # canonical + freeze-validator structure checks over the would-be doc
    source_texts = {sid: _load_source_text(
        sid, membership["records"][sid]) for sid in records}
    payloads = {sid: {"canonical": r["canonical"]} for sid, r in
                records.items()}
    vres = validate(payloads, source_texts, allow_unresolved=True,
                    expected_ids=sorted(membership["records"]))
    if not vres["valid"]:
        raise ImportFail("would-be decisions canonical validation failed: " +
                         "; ".join(vres["problems"][:20]))
    if stats["unresolved_fields"] != 0:
        raise ImportFail("would-be decisions contain unresolved fields")
    if stats["adjudicable"] != 36:
        raise ImportFail(f"adjudicable != 36: {stats['adjudicable']}")

    would_be = {
        "schema_version": "s2_11_review_decisions@2.0.0",
        "surface_id": "s2-11-blank-review-v2",
        "batch_import": "accept_all_with_listed_revisions",
        "applied": False,
        "confirmation_event": None,
        "adjudication_pending_user_confirmation": True,
        "final_adjudication_by": "user_only",
        "records": records,
    }
    return would_be, stats, []


def run_dry_run(revisions_path: Path | None) -> dict[str, Any]:
    revisions: dict[str, Any] = {}
    revisions_sha256: str | None = None
    if revisions_path is not None:
        try:
            revisions = json.loads(
                revisions_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ImportFail(
                f"revisions file {revisions_path.name} is not valid "
                f"UTF-8 JSON: {exc}") from exc
        revisions_sha256 = _sha256_bytes(revisions_path.read_bytes())

    would_be, stats, _ = build_would_be(revisions)

    local_path = LOCAL_DIR / LOCAL_WOULD_BE_REL
    local_data = (json.dumps(would_be, ensure_ascii=False, indent=2) + "\n") \
        .encode("utf-8")
    _write(local_path, local_data)

    report = _load_json(ROOT / PROPOSAL_REPORT_V2_REL)
    membership = _load_json(ROOT / MEMBERSHIP_REL)
    confirmation_event = ROOT / CONFIRMATION_EVENT_REL
    dry_run_report = {
        "schema_version": "s2_11_batch_import_dry_run@2.0.0",
        "proposal_report": PROPOSAL_REPORT_V2_REL,
        "proposal_report_sha256": _sha256_bytes(
            (ROOT / PROPOSAL_REPORT_V2_REL).read_bytes()),
        "proposal_file": report["proposal_file"],
        "proposal_file_sha256": report["proposal_file_sha256"],
        "membership": MEMBERSHIP_REL,
        "population": {
            "inventory": 40, "objective_exclusions": 4,
            "nonempty_membership": 36, "review_population": 36,
        },
        "batch_import_mode": "accept_all_with_listed_revisions",
        "revisions_file": (_rel_or_abs(revisions_path)
                           if revisions_path is not None else None),
        "revisions_file_sha256": revisions_sha256,
        "would_be_decisions_file": _rel_or_abs(local_path),
        "would_be_decisions_sha256": _sha256_bytes(local_data),
        "would_be_decisions": {
            "records": 36,
            "review_state": "reviewed",
            "reviewer": "null (never the user)",
            "adjudication_pending_user_confirmation": True,
        },
        "import_stats": stats,
        "fail_closed": {
            "confirmation_event_present": confirmation_event.is_file(),
            "applied": False,
            "wrote_decisions": False,
            "reviewer_never_user": True,
            "gold_created": False,
            "human_approved": False,
        },
        "raw_text_committed": False,
        "zero_api": {"new_llm_api_calls": 0},
        "determinism": {"no_wall_clock": True, "byte_identical_rebuild": True,
                        "no_overwrite": True},
    }
    data = (json.dumps(dry_run_report, ensure_ascii=False, indent=2) + "\n") \
        .encode("utf-8")
    _write(ROOT / DRY_RUN_REPORT_REL, data)
    return dry_run_report


def run_apply(confirmation_event_path: Path, revisions_path: Path | None,
              dry_run_report_sha: str | None = None) -> dict[str, Any]:
    """APPLY path. Refused (exit 2) unless a matching user confirmation
    event exists that exactly binds the proposal v2 SHA, the optional
    revisions SHA and the reviewer name. NOT executed this round."""
    event_path = ROOT / CONFIRMATION_EVENT_REL
    if confirmation_event_path is not None:
        event_path = confirmation_event_path
    if not event_path.is_file():
        raise ImportFail(
            f"no user confirmation event found ({CONFIRMATION_EVENT_REL}); "
            "batch import is NOT applied; nothing was written")
    event = _load_json(event_path)
    if event.get("kind") != "s2_11_batch_import_confirmation":
        raise ImportFail("confirmation event has the wrong kind")
    report = _load_json(ROOT / PROPOSAL_REPORT_V2_REL)
    if event.get("proposal_file_sha256") != report["proposal_file_sha256"]:
        raise ImportFail(
            "confirmation event does not bind this proposal v2 SHA; "
            "refusing to apply")
    reviewer = event.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ImportFail("confirmation event must carry a reviewer name")
    if revisions_path is not None:
        rev_sha = _sha256_bytes(revisions_path.read_bytes())
        if event.get("revisions_file_sha256") != rev_sha:
            raise ImportFail("confirmation event does not bind the "
                             "revisions SHA; refusing to apply")

    would_be, stats, _ = build_would_be(
        json.loads(revisions_path.read_text(encoding="utf-8"))
        if revisions_path is not None else {})
    for sample_id in would_be["records"]:
        would_be["records"][sample_id]["review_metadata"] = {
            "review_state": "adjudicated",
            "reviewer": reviewer,
            "confirmation_event": _rel_or_abs(event_path),
        }
    would_be["applied"] = True
    would_be["confirmation_event"] = _rel_or_abs(event_path)
    would_be["adjudication_pending_user_confirmation"] = False

    # atomic write with pre-write backup (never touch the live file on
    # any failure path above)
    backup = ROOT / (DECISIONS_V2_REL + ".bak")
    shutil.copy2(ROOT / DECISIONS_V2_REL, backup)
    data = (json.dumps(would_be, ensure_ascii=False, indent=2) + "\n") \
        .encode("utf-8")
    tmp = ROOT / (DECISIONS_V2_REL + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(ROOT / DECISIONS_V2_REL)
    return {"applied": True, "reviewer": reviewer,
            "records": len(would_be["records"]),
            "decisions_file": DECISIONS_V2_REL,
            "backup": _rel_or_abs(backup)}


def _rel_or_abs(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revisions", metavar="FILE",
                        help="optional user revisions JSON")
    parser.add_argument("--apply", action="store_true",
                        help="apply path (refused without a matching user "
                             "confirmation event; NOT run this round)")
    parser.add_argument("--confirmation-event", metavar="FILE")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        if args.apply:
            report = run_apply(
                Path(args.confirmation_event).resolve()
                if args.confirmation_event else None,
                Path(args.revisions).resolve() if args.revisions else None)
        else:
            report = run_dry_run(
                Path(args.revisions).resolve() if args.revisions else None)
    except ImportFail as exc:
        print(f"BATCH IMPORT V2 FAILED (fail-closed): {exc}",
              file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"batch import v2 dry-run written: {DRY_RUN_REPORT_REL}")
        print(f"import_stats: {report['import_stats']}")
        print(f"applied: {report.get('applied', False)} | "
              f"wrote_decisions: {report['fail_closed']['wrote_decisions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
