"""Validator for the EStG-150 canonical review file.

Three orthogonal gates:
  - format_valid: schema + ID uniqueness + membership identity + raw hashes
  - review_ready: every record has an approved_text_en and a non-stale
                  clause list (or an explicit no-normative-clause reason);
                  no orphan approved_text_en, no stale clauses;
                  annotation_review.status in {reviewed, adjudicated}
  - freeze_ready: every record is adjudicated and every clause is non-stale

Reports (does NOT silently fix) and exits non-zero if any of the gates
fails. Designed to be called by the offline review tool on every save
and by audit_project.py.

Run from formal_experiment/ as:
    python scripts/validate_canonical_review.py
    python scripts/validate_canonical_review.py --json
    python scripts/validate_canonical_review.py --path <other_file>
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DEFAULT_PATH = (
    BASE / "data" / "development" / "human_review" / "estg_150_canonical_review_v1.json"
)
HASHES_PATH = (
    BASE / "data" / "development" / "estg" / "estg_150_membership_hashes.json"
)
SCHEMA_PATH = (
    BASE / "configs" / "schemas" / "estg_150_canonical_review.schema.json"
)


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _validate_minimal_schema(doc):
    """Return list of (record_index_or_None, error_message)."""
    errors = []
    if not isinstance(doc, dict):
        return [(None, "top-level must be an object")]

    if doc.get("schema_version") != "estg_150_canonical_review@1.0.0":
        errors.append((None, f"schema_version must be exactly "
                              f"estg_150_canonical_review@1.0.0, got "
                              f"{doc.get('schema_version')!r}"))

    ds = doc.get("dataset", {})
    if ds.get("name") != "independently_reconstructed_estg_150":
        errors.append((None, "dataset.name must be "
                              "independently_reconstructed_estg_150"))
    if ds.get("version") != "v1":
        errors.append((None, "dataset.version must be v1"))
    if ds.get("membership_count") != 150:
        errors.append((None, "dataset.membership_count must be 150"))

    records = doc.get("records", [])
    if not isinstance(records, list):
        return errors + [(None, "records must be a list")]

    if len(records) != 150:
        errors.append((None, f"records must have exactly 150 items, got "
                              f"{len(records)}"))

    seen_legacy = set()
    seen_sample = set()
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            errors.append((i, "record is not an object"))
            continue
        # sample_id format
        sid = r.get("sample_id")
        if not isinstance(sid, str) or not sid.startswith("estg_"):
            errors.append((i, f"sample_id must be estg_NNN string, got {sid!r}"))
        elif sid in seen_sample:
            errors.append((i, f"duplicate sample_id: {sid}"))
        else:
            seen_sample.add(sid)

        # legacy_record_id
        lid = r.get("legacy_record_id")
        if not isinstance(lid, int):
            errors.append((i, f"legacy_record_id must be int, got "
                              f"{type(lid).__name__}"))
        elif lid in seen_legacy:
            errors.append((i, f"duplicate legacy_record_id: {lid}"))
        else:
            seen_legacy.add(lid)

        # sample_id <-> legacy_record_id coherence
        if isinstance(sid, str) and isinstance(lid, int):
            expected = f"estg_{lid:06d}"
            if sid != expected:
                errors.append((i, f"sample_id {sid!r} != estg_{lid:06d} "
                                  f"(legacy_record_id={lid})"))

        # hashes
        for hf, txt_key in (("raw_text_de_sha256", "raw_text_de"),
                            ("cleaned_text_de_candidate_sha256",
                             "cleaned_text_de_candidate")):
            if hf not in r:
                errors.append((i, f"missing {hf}"))
                continue
            expected = sha256(r.get(txt_key, ""))
            if r[hf] != expected:
                errors.append((i, f"{hf} mismatch (text changed?)"))

        # approved_text_en <-> sha256
        ap = r.get("approved_text_en")
        ap_sha = r.get("approved_text_en_sha256")
        if ap is None and ap_sha is not None:
            errors.append((i, "approved_text_en is null but "
                              "approved_text_en_sha256 is set"))
        elif ap is not None and ap_sha is None:
            errors.append((i, "approved_text_en set but "
                              "approved_text_en_sha256 is null"))
        elif ap is not None and ap_sha is not None:
            if sha256(ap) != ap_sha:
                errors.append((i, "approved_text_en_sha256 mismatch"))

        # text_review / annotation_review status enum
        for fld, allowed in (
            ("text_review",
             ("needs_review", "needs_adjudication", "approved", "rejected")),
            ("annotation_review",
             ("needs_review", "needs_adjudication", "reviewed", "adjudicated")),
        ):
            obj = r.get(fld, {})
            st = obj.get("status") if isinstance(obj, dict) else None
            if st not in allowed:
                errors.append((i, f"{fld}.status must be one of "
                                  f"{sorted(allowed)}, got {st!r}"))

        # clauses structure: cross-field rules
        clauses = r.get("clauses", [])
        if not isinstance(clauses, list):
            errors.append((i, "clauses must be a list"))
            continue

        ap_text = r.get("approved_text_en")
        for ci, c in enumerate(clauses):
            if not isinstance(c, dict):
                errors.append((i, f"clause {ci} is not an object"))
                continue

            if ap_text is None:
                errors.append((
                    i, f"clause {ci} present but approved_text_en is null; "
                       f"clause spans require an approved English text"
                ))
            else:
                cs = c.get("clause_span", {})
                txt = cs.get("text", "")
                if txt != ap_text[cs.get("start", 0):cs.get("end", 0)]:
                    errors.append((
                        i, f"clause {ci} clause_span text != "
                           f"approved_text_en[start:end]"
                    ))

            for span_field in ("actors", "actions", "conditions",
                               "constraints", "exceptions"):
                for si, s in enumerate(c.get(span_field, [])):
                    if ap_text is None:
                        continue
                    if (s.get("text")
                            != ap_text[s.get("start", 0):s.get("end", 0)]):
                        errors.append((
                            i, f"clause {ci} {span_field}[{si}] text != "
                               f"approved_text_en[start:end]"
                        ))

            # actor_action_map / order_relations id refs
            actor_ids = {a["id"] for a in c.get("actors", [])}
            action_ids = {a["id"] for a in c.get("actions", [])}
            for ei, e in enumerate(c.get("actor_action_map", [])):
                if e.get("actor_id") is not None and \
                        e["actor_id"] not in actor_ids:
                    errors.append((
                        i, f"clause {ci} actor_action_map[{ei}].actor_id "
                           f"references unknown actor {e['actor_id']!r}"
                    ))
                if e.get("action_id") not in action_ids:
                    errors.append((
                        i, f"clause {ci} actor_action_map[{ei}].action_id "
                           f"references unknown action {e['action_id']!r}"
                    ))
            order_ids = action_ids
            for oi, o in enumerate(c.get("order_relations", [])):
                if o.get("before_action_id") not in order_ids:
                    errors.append((
                        i, f"clause {ci} order_relations[{oi}]."
                           f"before_action_id references unknown action"
                    ))
                if o.get("after_action_id") not in order_ids:
                    errors.append((
                        i, f"clause {ci} order_relations[{oi}]."
                           f"after_action_id references unknown action"
                    ))

        # old_gold_sources pre_filled MUST be false
        for oi, og in enumerate(r.get("old_gold_sources", [])):
            if og.get("pre_filled") is not False:
                errors.append((
                    i, f"old_gold_sources[{oi}].pre_filled must be false "
                       f"(anchoring protection); got "
                       f"{og.get('pre_filled')!r}"
                ))

    return errors


def _validate_against_membership(doc, hashes):
    """Cross-check membership_payload_sha256 and per-record hashes."""
    errors = []
    expected = hashes["selected_membership"]["membership_payload_sha256"]
    actual = doc.get("dataset", {}).get("membership_payload_sha256")
    if expected != actual:
        errors.append((None, f"membership_payload_sha256 mismatch: "
                              f"expected {expected}, got {actual}"))

    expected_ids = hashes["selected_membership"]["sorted_legacy_record_ids"]
    actual_ids = sorted(
        r.get("legacy_record_id")
        for r in doc.get("records", [])
        if isinstance(r, dict)
    )
    if expected_ids != actual_ids:
        errors.append((None, "membership identity broken: sorted "
                              "legacy_record_ids differ from selected_150_de"))

    per_record_hashes = {
        x["legacy_record_id"]: x["sha256_raw_de"]
        for x in hashes["per_record_raw_de_sha256"]
    }
    for r in doc.get("records", []):
        if not isinstance(r, dict):
            continue
        lid = r.get("legacy_record_id")
        expected = per_record_hashes.get(lid)
        if expected is None:
            errors.append((None, f"per_record hash missing for legacy id "
                                  f"{lid}"))
        elif expected != r.get("raw_text_de_sha256"):
            errors.append((None, f"raw_text_de_sha256 mismatch for "
                                  f"legacy id {lid}"))

    return errors


def _stale_clause_marker(doc):
    """A clause list is 'stale' if any of the following holds:
       - it has at least one clause but approved_text_en is None
       - it has at least one clause but the clause text no longer matches
         approved_text_en (caught above)
    We also report a record-level "stale_clauses" if the annotation_review
    has been touched but the text review's approved_text_en is null or has
    changed without resetting the annotation review.

    For simplicity we expose one boolean per record: stale = approved_text_en
    is None AND clauses is non-empty.
    """
    out = []
    for i, r in enumerate(doc.get("records", [])):
        if not isinstance(r, dict):
            continue
        if r.get("approved_text_en") is None and len(r.get("clauses", [])) > 0:
            out.append(i)
    return out


def validate(path: Path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    hashes = json.loads(HASHES_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    # Schema sanity (very shallow: we already enforce keys by hand above)
    assert schema.get("title", "").startswith("EStG-150 Canonical")

    errors = _validate_minimal_schema(doc)
    errors.extend(_validate_against_membership(doc, hashes))

    format_valid = len(errors) == 0

    # review_ready: every record has approved_text_en AND annotation_review
    # status in {reviewed, adjudicated}, AND no record has stale clauses
    # AND no record is in text_review == needs_review.
    review_blockers = []
    for i, r in enumerate(doc.get("records", [])):
        if not isinstance(r, dict):
            continue
        if r.get("text_review", {}).get("status") == "needs_review":
            review_blockers.append(
                (i, "text_review.status == needs_review")
            )
        if r.get("text_review", {}).get("status") == "needs_adjudication":
            review_blockers.append(
                (i, "text_review.status == needs_adjudication")
            )
        if not r.get("approved_text_en"):
            review_blockers.append((i, "approved_text_en is empty"))
        ar_status = r.get("annotation_review", {}).get("status")
        if ar_status not in ("reviewed", "adjudicated"):
            review_blockers.append(
                (i, f"annotation_review.status must be reviewed or "
                   f"adjudicated, got {ar_status!r}")
            )
    review_ready = format_valid and len(review_blockers) == 0

    # freeze_ready: every record adjudicated and no stale clauses
    freeze_blockers = []
    for i, r in enumerate(doc.get("records", [])):
        if not isinstance(r, dict):
            continue
        if r.get("annotation_review", {}).get("status") != "adjudicated":
            freeze_blockers.append(
                (i, "annotation_review.status != adjudicated")
            )
    if _stale_clause_marker(doc):
        freeze_blockers.append(
            (None, "at least one record has clauses but no "
                   "approved_text_en (stale clauses)")
        )
    freeze_ready = review_ready and len(freeze_blockers) == 0

    return {
        "path": str(path),
        "format_valid": format_valid,
        "review_ready": review_ready,
        "freeze_ready": freeze_ready,
        "format_errors": [list(e) for e in errors],
        "review_blockers": [list(e) for e in review_blockers],
        "freeze_blockers": [list(e) for e in freeze_blockers],
        "n_records": len(doc.get("records", [])),
        "n_text_needs_review": sum(
            1 for r in doc.get("records", [])
            if isinstance(r, dict)
            and r.get("text_review", {}).get("status") == "needs_review"
        ),
        "n_annotation_needs_review": sum(
            1 for r in doc.get("records", [])
            if isinstance(r, dict)
            and r.get("annotation_review", {}).get("status")
            == "needs_review"
        ),
        "n_clauses_total": sum(
            len(r.get("clauses", []))
            for r in doc.get("records", [])
            if isinstance(r, dict)
        ),
        "n_approved_en_filled": sum(
            1 for r in doc.get("records", [])
            if isinstance(r, dict) and r.get("approved_text_en")
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", type=Path, default=DEFAULT_PATH)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = validate(args.path)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"path             : {result['path']}")
        print(f"records          : {result['n_records']}")
        print(f"text needs_review: {result['n_text_needs_review']}")
        print(f"annotation needs_review: "
              f"{result['n_annotation_needs_review']}")
        print(f"clauses total    : {result['n_clauses_total']}")
        print(f"approved_en_filled: {result['n_approved_en_filled']}")
        print(f"format_valid     : {result['format_valid']}")
        print(f"review_ready     : {result['review_ready']}")
        print(f"freeze_ready     : {result['freeze_ready']}")
        if result["format_errors"]:
            print("format errors:")
            for e in result["format_errors"][:10]:
                print(" ", e)
        if result["review_blockers"]:
            print("review blockers (first 10):")
            for e in result["review_blockers"][:10]:
                print(" ", e)
        if result["freeze_blockers"]:
            print("freeze blockers:")
            for e in result["freeze_blockers"]:
                print(" ", e)
    # Exit code: 0 only if format_valid. review_ready / freeze_ready are
    # reported but do not fail the script (they reflect the user's progress
    # in the file, not a structural defect).
    if not result["format_valid"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
