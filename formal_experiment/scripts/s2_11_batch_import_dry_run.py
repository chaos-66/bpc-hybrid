# -*- coding: utf-8 -*-
"""S2.11 batch accept/revise import tool — DRY-RUN ONLY (Checkpoint C).

Simulates importing the 36 offline AI proposals into the S2.11 review
decisions file ("accept-all with listed revisions") WITHOUT touching the
live decisions file and WITHOUT any confirmation event this round.

FAIL-CLOSED invariants (any violation aborts with exit 2, nothing written):
  * membership must be 40 inventory / 4 objective exclusions / 36 nonempty
    and review_population == nonempty_membership == inventory - exclusions
  * the committed proposal report must cover exactly the 36 nonempty
    membership records (no missing / no extra sample ids)
  * the LOCAL proposals file must exist and its SHA-256 must equal the
    report's proposal_file_sha256 (proposal artifact binding)
  * every local proposal entry must hash-match the membership
    (text_sha256 / file_sha256) and must be human_approved=false,
    gold=false, reviewer=null
  * revision values (user-supplied) must be exact substrings of the
    hash-verified source text (byte-verified) or null — nothing invented
  * decision import rules (fail-closed, nothing ungrounded):
      - modality: controlled vocabulary (obligation/permission/prohibition/
        definition); imported as a class label even when no span exists
      - actor/action/condition/constraint/exception: imported ONLY when the
        value is an exact substring of the source text; a proposed value
        not found in the text, or a multi-value proposal, becomes
        decision=null with an import_blocked note (user must revise)
  * the would-be decisions file marks every record review_state=reviewed
    (NOT adjudicated) with reviewer=null: final adjudication stays
    user-only and requires a future user confirmation event; this tool
    NEVER writes reviewer="user" and NEVER fabricates Gold
  * --apply is refused (exit 2) because no matching user confirmation
    event exists this round; the tool never creates one

Outputs:
  LOCAL (gitignored, never committed):
    outputs/development/s2_11_local_working/batch_import_dry_run_v1/
      would_be_decisions.json
  COMMITTED (hashes/counts/ids ONLY — no reconstructable raw third-party
    text):
    outputs/reports/s2_11_batch_import_dry_run_v1.json

Usage:
  python scripts/s2_11_batch_import_dry_run.py [--revisions FILE] [--json]
  python scripts/s2_11_batch_import_dry_run.py --apply   # refuses (no event)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
PROPOSAL_REPORT_REL = "outputs/reports/s2_11_proposal_report_v1.json"
LOCAL_DIR = ROOT / "outputs" / "development" / "s2_11_local_working" / \
    "batch_import_dry_run_v1"
LOCAL_WOULD_BE_REL = "would_be_decisions.json"
DRY_RUN_REPORT_REL = "outputs/reports/s2_11_batch_import_dry_run_v1.json"
CONFIRMATION_EVENT_REL = "configs/s2_11_batch_import_confirmation_event_v1.json"

DECISION_FIELDS = ("modality", "actor", "action", "condition",
                   "constraint", "exception")
MODALITY_VOCAB = ("obligation", "permission", "prohibition", "definition")
SPAN_BOUND_FIELDS = DECISION_FIELDS[1:]  # modality is a class label


class ImportFail(Exception):
    """Fail-closed abort."""


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
    """Hash-verified raw text for one record (read-only from references)."""
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


def _locate(text: str, value: str) -> bool:
    i = text.find(value)
    if i < 0:
        return False
    assert text[i:i + len(value)] == value, "byte-slice verification"
    return True


def _rel_or_abs(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _validate_revisions(revisions: dict[str, Any], membership: dict[str, Any],
                        proposal_entries: dict[str, Any]) -> list[str]:
    """Validate user-supplied revisions; returns problems (empty == OK)."""
    problems: list[str] = []
    expected = set(membership["records"])
    for sid, rev in revisions.items():
        if sid not in expected:
            problems.append(f"revision for unknown sample {sid!r}")
            continue
        if not isinstance(rev, dict):
            problems.append(f"{sid}: revision must be an object")
            continue
        text = _load_source_text(sid, membership["records"][sid])
        for field, value in rev.items():
            if field not in DECISION_FIELDS:
                problems.append(f"{sid}: revision for unknown field "
                                f"{field!r}")
                continue
            if value is None:
                continue
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{sid}:{field} revision must be a "
                                "non-empty string or null")
                continue
            if field == "modality":
                if value not in MODALITY_VOCAB:
                    problems.append(
                        f"{sid}:{field} modality must be one of "
                        f"{'/'.join(MODALITY_VOCAB)}")
                continue
            if not _locate(text, value):
                problems.append(
                    f"{sid}:{field} revision {value!r} is not an exact "
                    "substring of the source text")
    return problems


def _build_would_be(membership: dict[str, Any],
                    report: dict[str, Any],
                    local_entries: dict[str, Any],
                    revisions: dict[str, Any]) -> tuple[dict[str, Any],
                                                        list[dict[str, Any]]]:
    """Build the would-be decisions doc. Returns (doc, import_blocked)."""
    import_blocked: list[dict[str, Any]] = []
    records: dict[str, Any] = {}
    for sample_id in sorted(membership["records"]):
        rec = membership["records"][sample_id]
        proposal = local_entries[sample_id]
        rev = revisions.get(sample_id) or {}
        decision: dict[str, Any] = {}
        for field in DECISION_FIELDS:
            if field in rev:
                decision[field] = rev[field]
                continue
            fi = proposal["fields"][field]
            if not fi["present"]:
                decision[field] = None
                continue
            value = fi.get("value")
            if field == "modality":
                if value not in MODALITY_VOCAB:
                    raise ImportFail(
                        f"{sample_id}: modality {value!r} outside the "
                        "controlled vocabulary")
                decision[field] = value
                continue
            if isinstance(value, list):
                decision[field] = None
                import_blocked.append({
                    "sample_id": sample_id, "field": field,
                    "reason": "multi_value_proposal_requires_user_selection",
                })
                continue
            text = _load_source_text(sample_id, rec)
            if not _locate(text, value):
                decision[field] = None
                import_blocked.append({
                    "sample_id": sample_id, "field": field,
                    "reason": "proposed_value_not_found_in_text",
                })
                continue
            decision[field] = value
        records[sample_id] = {
            "decision": decision,
            "review_state": "reviewed",
            "reviewer": None,
        }
    doc = {
        "schema_version": "s2_11_review_decisions_dry_run@1.0.0",
        "surface_id": "s2-11-blank-review-v1",
        "batch_import": "accept_all_with_listed_revisions",
        "applied": False,
        "confirmation_event": None,
        "adjudication_pending_user_confirmation": True,
        "final_adjudication_by": "user_only",
        "records": records,
    }
    return doc, import_blocked


def _validate_would_be(doc: dict[str, Any]) -> list[str]:
    """Structural validation of the would-be decisions doc."""
    from scripts.review_s2_11_candidates import verify_decisions  # type: ignore
    problems = verify_decisions(doc)
    for sample_id, entry in doc["records"].items():
        if entry["review_state"] != "reviewed":
            problems.append(f"{sample_id}: dry-run state must be reviewed")
        if entry.get("reviewer") is not None:
            problems.append(f"{sample_id}: dry-run reviewer must be null")
    return problems


def run_dry_run(revisions_path: Path | None) -> dict[str, Any]:
    membership = _load_json(ROOT / MEMBERSHIP_REL)
    report = _load_json(ROOT / PROPOSAL_REPORT_REL)

    # 1. membership closure invariants
    if int(membership["record_count"]) != 40 or \
            len(membership["quarantine"]) != 4 or \
            len(membership["records"]) != 36:
        raise ImportFail("membership must be 40/4/36, got "
                         f"{membership['record_count']}/"
                         f"{len(membership['quarantine'])}/"
                         f"{len(membership['records'])}")

    # 2. proposal report coverage == nonempty membership
    if report.get("coverage") != "36/36" or \
            int(report.get("proposal_count", 0)) != 36:
        raise ImportFail("proposal report coverage must be 36/36")
    report_ids = set(report.get("entries") or {})
    member_ids = set(membership["records"])
    if report_ids != member_ids:
        raise ImportFail(
            "proposal report sample set mismatch: missing=" +
            str(sorted(member_ids - report_ids)) +
            " extra=" + str(sorted(report_ids - member_ids)))

    # 3. local proposals file binding (SHA-256 == report field)
    local_rel = str(report.get("proposal_file"))
    local_path = ROOT / local_rel
    if not local_path.is_file():
        raise ImportFail(f"local proposals file missing: {local_rel}")
    local_bytes = local_path.read_bytes()
    if _sha256_bytes(local_bytes) != report.get("proposal_file_sha256"):
        raise ImportFail("local proposals file SHA-256 does not match the "
                         "proposal report binding")
    lines = [ln for ln in local_bytes.decode("utf-8").splitlines() if ln]
    if len(lines) != 36:
        raise ImportFail(f"local proposals file must have 36 lines, "
                         f"got {len(lines)}")
    local_entries: dict[str, Any] = {}
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
        local_entries[sid] = entry
    if set(local_entries) != member_ids:
        raise ImportFail("local proposals sample set mismatch")

    # 4. revisions validation (user-supplied values, exact substrings)
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
        problems = _validate_revisions(revisions, membership, local_entries)
        if problems:
            raise ImportFail("revisions invalid: " + "; ".join(problems))
        revisions_sha256 = _sha256_bytes(
            revisions_path.read_bytes())

    # 5. build + validate the would-be decisions doc
    would_be, import_blocked = _build_would_be(
        membership, report, local_entries, revisions)
    problems = _validate_would_be(would_be)
    if problems:
        raise ImportFail("would-be decisions invalid: " + "; ".join(problems))

    # 6. write LOCAL would-be file, then the committed dry-run report
    local_rel_path = LOCAL_DIR / LOCAL_WOULD_BE_REL
    local_data = (json.dumps(would_be, ensure_ascii=False, indent=2) + "\n") \
        .encode("utf-8")
    _write(local_rel_path, local_data)

    confirmation_event = ROOT / CONFIRMATION_EVENT_REL
    dry_run_report = {
        "schema_version": "s2_11_batch_import_dry_run@1.0.0",
        "proposal_report": PROPOSAL_REPORT_REL,
        "proposal_report_sha256": _sha256_bytes(
            (ROOT / PROPOSAL_REPORT_REL).read_bytes()),
        "proposal_file": local_rel,
        "proposal_file_sha256": report["proposal_file_sha256"],
        "membership": MEMBERSHIP_REL,
        "population": {
            "inventory": 40,
            "objective_exclusions": 4,
            "nonempty_membership": 36,
            "review_population": 36,
            "closure_invariant": (
                "review_population == nonempty_membership == "
                "inventory - objective_exclusions"),
        },
        "batch_import_mode": "accept_all_with_listed_revisions",
        "revisions_file": (_rel_or_abs(revisions_path)
                           if revisions_path is not None else None),
        "revisions_file_sha256": revisions_sha256,
        "would_be_decisions_file": _rel_or_abs(local_rel_path),
        "would_be_decisions_sha256": _sha256_bytes(local_data),
        "would_be_decisions": {
            "records": 36,
            "review_state": "reviewed",
            "reviewer": "null (never the user)",
            "adjudication_pending_user_confirmation": True,
        },
        "import_stats": {
            "samples": 36,
            "import_blocked_fields": len(import_blocked),
            "import_blocked_samples": len(
                {b["sample_id"] for b in import_blocked}),
        },
        "import_blocked": import_blocked,
        "recommended_for_user_revision": sorted(
            report.get("needs_attention_ids") or []),
        "fail_closed": {
            "confirmation_event_present": confirmation_event.is_file(),
            "applied": False,
            "wrote_decisions": False,
            "reviewer_never_user": True,
            "gold_created": False,
            "human_approved": False,
        },
        "determinism": {
            "no_wall_clock": True,
            "byte_identical_rebuild": True,
            "no_overwrite": True,
        },
        "raw_text_committed": False,
        "zero_api": {"new_llm_api_calls": 0},
    }
    data = (json.dumps(dry_run_report, ensure_ascii=False, indent=2) + "\n") \
        .encode("utf-8")
    _write(ROOT / DRY_RUN_REPORT_REL, data)
    return dry_run_report


def run_apply() -> dict[str, Any]:
    """Apply path — REFUSED without a matching user confirmation event."""
    event = ROOT / CONFIRMATION_EVENT_REL
    if not event.is_file():
        raise ImportFail(
            "no user confirmation event found "
            f"({CONFIRMATION_EVENT_REL}); batch import is NOT applied; "
            "nothing was written to the decisions file")
    raise ImportFail(
        "apply path not implemented for this round: the confirmation "
        "event must be validated against the proposal report and "
        "revisions bindings before any write; refusing")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revisions", metavar="FILE",
                        help="optional user revisions JSON "
                             "{sample_id: {field: value|null}}")
    parser.add_argument("--apply", action="store_true",
                        help="apply path (refused without a confirmation "
                             "event)")
    parser.add_argument("--json", action="store_true",
                        help="print the dry-run report as JSON")
    args = parser.parse_args()
    try:
        revisions_arg = Path(args.revisions).resolve() \
            if args.revisions else None
        report = run_apply() if args.apply else \
            run_dry_run(revisions_arg)
    except ImportFail as exc:
        print(f"BATCH IMPORT FAILED (fail-closed): {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"batch import dry-run written: {DRY_RUN_REPORT_REL}")
        print(f"would-be decisions: {report['would_be_decisions_file']}")
        print(f"import_blocked_fields: "
              f"{report['import_stats']['import_blocked_fields']} "
              f"({report['import_stats']['import_blocked_samples']} "
              "samples)")
        print(f"applied: {report['fail_closed']['applied']} | "
              f"wrote_decisions: {report['fail_closed']['wrote_decisions']} | "
              f"confirmation_event_present: "
              f"{report['fail_closed']['confirmation_event_present']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
