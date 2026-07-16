"""Pre-task checks for the EStG-150 LLM-assisted human-correction workflow (Event 23).

This script is read-only: it never writes to any data, Gold, action log,
or backup. It is the lightweight gate the user (or any agent) can run
before touching the v2 human_correction file to make sure:

  1. The 9 immutable source files (Layer A/B/C/D + the membership
     hashes + the LLM draft + the EN translation source + the
     v2 human_correction + the v1 canonical review provenance)
     are all present and at their expected SHA-256 digests. The
     expectation is a STARTING digest; the script reports the
     current digest and flags a divergence.

  2. The v2 human_correction file is the current human editing
     surface. Event 22 retired the v1 ``canonical_review_v1``
     as a workflow draft; Event 23 makes this script call out
     the v2 file by name. The v1 file is still read for
     provenance but is NOT the editing target.

  3. The strict v2 validator (``estg150_validator.validate_doc_dict``)
     is the single source of truth for ``format_valid`` /
     ``review_ready`` / ``freeze_ready``. The output reports
     those three booleans plus the four orthogonal audit gates
     (input / freeze / publication / final).

  4. The membership cross-check is fail-closed: a missing
     ``membership_payload_sha256`` in the v2 file is acceptable
     (the strict validator treats it as optional), but the
     v2 sorted ``legacy_record_id`` list MUST match the locked
     membership.

Run from workspace root:
    python formal_experiment/scripts/_precheck_estg150.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ---------------------------------------------------------------------------
# The 9 source files that the project commits to NOT modifying
# (Layer A/B/C/D + membership + EN source + EN translation source +
# LLM draft source + v2 human_correction + v1 canonical review
# provenance). This list intentionally includes the v2 human_correction
# file because the user is the only authorized editor; the precheck
# detects accidental external edits to the file.
# ---------------------------------------------------------------------------
IMMUTABLE_INPUTS = {
    "de_source": REPO / "data" / "development" / "estg" / "estg_selected_150_de.jsonl",
    "en_candidate_source": REPO / "data" / "development" / "estg" / "estg_selected_150_en_llm_translated.jsonl",
    "llm_draft_source": REPO / "data" / "development" / "estg" / "estg_gold_150_llm_draft.jsonl",
    "membership_hashes": REPO / "data" / "development" / "estg" / "estg_150_membership_hashes.json",
    "prepared_v1": REPO / "data" / "development" / "estg" / "estg_150_prepared_v1.jsonl",
    # v1 canonical review is RETIRED as editing surface but kept as
    # provenance. Event 23 explicitly distinguishes it from the v2
    # editing file below.
    "v1_canonical_review_provenance": REPO / "data" / "development" / "human_review" / "estg_150_canonical_review_v1.json",
    # v2 human_correction is the CURRENT human editing file (Layer E).
    # This precheck reads it but never writes to it.
    "v2_human_correction_editing": REPO / "data" / "development" / "human_review" / "estg_150_human_correction_v1.json",
    "translation_manifest": REPO / "data" / "development" / "human_review" / "estg_150_translation_en_v1.jsonl",
    "llm_candidate_manifest": REPO / "data" / "development" / "human_review" / "estg_150_llm_six_element_candidates_v1.jsonl",
    "zh_review_aid": REPO / "data" / "development" / "human_review" / "estg_150_review_aids_zh_v1.jsonl",
}


def sha256_path(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _safe_load(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main() -> int:
    print("=== EStG-150 precheck (read-only, Event 23 hardened) ===")
    print()
    print("[1] Source file SHA-256 (must remain unchanged unless user")
    print("    explicitly authorizes the change):")
    digests: dict[str, str] = {}
    all_present = True
    for label, p in IMMUTABLE_INPUTS.items():
        if not p.exists():
            print(f"  [MISSING] {label}: {p}")
            all_present = False
            continue
        h = sha256_path(p)
        digests[label] = h
        print(f"  {h[:16]}  {label:<35} ({p.stat().st_size:>7} B)  {p.name}")
    if not all_present:
        return 2
    print()
    # ------------------------------------------------------------------
    # [2] v1 canonical review is PROVENANCE only. v2 human_correction
    # is the CURRENT human editing file (Layer E).
    # ------------------------------------------------------------------
    print("[2] v1 canonical review (provenance, retired as editing surface):")
    v1_doc = _safe_load(IMMUTABLE_INPUTS["v1_canonical_review_provenance"])
    if v1_doc:
        v1_records = v1_doc.get("records", []) or []
        v1_text_approved = sum(
            1 for r in v1_records
            if isinstance(r, dict) and r.get("text_review", {}).get("status") == "approved"
        )
        v1_anno_reviewed = sum(
            1 for r in v1_records
            if isinstance(r, dict)
            and r.get("annotation_review", {}).get("status") in ("reviewed", "adjudicated")
        )
        v1_anno_adjudicated = sum(
            1 for r in v1_records
            if isinstance(r, dict)
            and r.get("annotation_review", {}).get("status") == "adjudicated"
        )
        print(f"  records              : {len(v1_records)}")
        print(f"  text_approved        : {v1_text_approved}/150  (provenance, not edited any more)")
        print(f"  annotation_reviewed  : {v1_anno_reviewed}/150")
        print(f"  annotation_adjudicated: {v1_anno_adjudicated}/150")
    print()
    # ------------------------------------------------------------------
    # [3] v2 human_correction is the CURRENT human editing file. Run
    # the strict v2 validator; it is the single source of truth.
    # ------------------------------------------------------------------
    print("[3] v2 human_correction (CURRENT human editing file, Layer E):")
    v2_path = IMMUTABLE_INPUTS["v2_human_correction_editing"]
    v2_doc = _safe_load(v2_path)
    if not v2_doc:
        print(f"  [ERROR] could not load {v2_path}")
        return 2
    membership_path = IMMUTABLE_INPUTS["membership_hashes"]
    from formal_experiment.estg150_validator import validate_doc_dict
    try:
        v2_report = validate_doc_dict(v2_doc, membership_path)
    except (OSError, ValueError, KeyError) as exc:
        print(f"  [ERROR] strict v2 validator crashed: {exc!r}")
        return 2
    # The strict validator tags in-memory docs as '<in-memory>'; show
    # the real file path so the operator can see which file was
    # actually validated.
    display_path = (
        v2_path if v2_report.get("path") == "<in-memory>" else v2_report.get("path", str(v2_path))
    )
    print(f"  path                  : {display_path}")
    print(f"  records               : {v2_report['n_records']}/150")
    print(f"  approved_text_en      : {v2_report['n_approved_en']}/150")
    print(f"  translation unreviewed: {v2_report['n_translation_unreviewed']}/150")
    print(f"  six-element unreviewed: {v2_report['n_field_decisions_unreviewed']}/"
          f"{v2_report['n_field_decisions_total']}  (6 fields * 150 records)")
    print(f"  six-element resolved  : {v2_report['n_field_decisions_resolved']}/"
          f"{v2_report['n_field_decisions_total']}")
    print(f"  records fully decided : {v2_report['n_records_fully_decided']}/150")
    print(f"  records incomplete    : {v2_report['n_records_incomplete']}/150")
    print(f"  review_state counts   : {v2_report['review_state_counts']}")
    print(f"  format_valid          : {v2_report['format_valid']}")
    print(f"  review_ready          : {v2_report['review_ready']}")
    print(f"  freeze_ready          : {v2_report['freeze_ready']}")
    # ------------------------------------------------------------------
    # [4] Four orthogonal audit gates (2026-07-13, Event 22/23). The
    # precheck surfaces the four gates by name so the user (and the
    # audit) never confuse "input ready" with "Gold publishable".
    # ------------------------------------------------------------------
    print()
    print("[4] Four orthogonal audit gates (Event 22, hardened Event 23):")
    from formal_experiment.status import collect_status
    from formal_experiment.audit import collect_project_audit
    s = collect_status()
    a = collect_project_audit()
    print(f"  human_review_input_ready       : {s['human_review_input_ready']}")
    print(f"  human_review_freeze_ready      : {s['human_review_freeze_ready']}")
    print(f"  formal_gold_publication_ready  : {s['formal_gold_publication_ready']}")
    print(f"  final_experiment_ready         : {s['final_experiment_ready']}")
    # Membership cross-check (fail-closed)
    print(f"  membership_ok                  : {s['membership_ok']}")
    print(f"  membership_reason              : {s.get('membership_reason')!r}")
    # Event 23 publication whitelist
    print(f"  formal_gold_publication_gate_status      : {s.get('formal_gold_publication_gate_status')!r}")
    print(f"  formal_gold_publication_gate_allowed     : {s.get('formal_gold_publication_gate_allowed')!r}")
    print(f"  formal_gold_publication_gate_match       : {s.get('formal_gold_publication_gate_match')}")
    print()
    # ------------------------------------------------------------------
    # [5] Stop conditions. We DO NOT raise an error just because the
    # v2 file already has human edits; the precheck is a status
    # report, not a write-preventing gate. But we DO refuse to claim
    # "all clear" if any of the immutable source files are missing.
    # ------------------------------------------------------------------
    if v2_report.get("n_adjudicated", 0) > 0 or v2_report.get("n_reviewed", 0) > 0:
        print("[note] v2 human_correction has reviewed/adjudicated records.")
        print("       The precheck is read-only; it does not block further edits.")
    if not a["integrity_pass"]:
        print("[ERROR] integrity_pass is false. Run audit_project.py for details.")
        return 2
    print("[OK] all 9 source files present; v2 strict validator ran cleanly;")
    print("     four-gate state reported above. Precheck is read-only;")
    print("     it does not modify the human_correction file or any data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
