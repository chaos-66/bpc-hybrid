"""Build the 5-layer EStG-150 data model for the LLM-assisted human
correction workflow.

Layers (all under formal_experiment/data/development/human_review/):

  A. German source            (immutable, already in estg/estg_selected_150_de.jsonl)
  B. English translation      -> estg_150_translation_en_v1.jsonl  (immutable)
  C. LLM six-element candidate -> estg_150_llm_six_element_candidates_v1.jsonl  (immutable)
  D. Chinese review aid       -> estg_150_review_aids_zh_v1.jsonl  (immutable, fields null until future authorized LLM call)
  E. Human correction         -> estg_150_human_correction_v1.json  (ONLY editable file)

The old estg_150_canonical_review_v1.json is NOT overwritten; this script
also produces docs/ESTG150_REVIEW_WORKFLOW_V1.md to explain the new layer
split and the retirement of the canonical-review schema.

Run from workspace root:
    python formal_experiment/scripts/build_estg150_review_layers.py
"""
from __future__ import annotations

import datetime
import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
HUMAN_REVIEW_DIR = REPO / "data" / "development" / "human_review"
ESTG_DIR = REPO / "data" / "development" / "estg"


DE_SOURCE = ESTG_DIR / "estg_selected_150_de.jsonl"
EN_SOURCE = ESTG_DIR / "estg_selected_150_en_llm_translated.jsonl"
LLM_DRAFT_SOURCE = ESTG_DIR / "estg_gold_150_llm_draft.jsonl"
CANONICAL_REVIEW_OLD = HUMAN_REVIEW_DIR / "estg_150_canonical_review_v1.json"


LAYER_B_OUT = HUMAN_REVIEW_DIR / "estg_150_translation_en_v1.jsonl"
LAYER_C_OUT = HUMAN_REVIEW_DIR / "estg_150_llm_six_element_candidates_v1.jsonl"
LAYER_D_OUT = HUMAN_REVIEW_DIR / "estg_150_review_aids_zh_v1.jsonl"
LAYER_E_OUT = HUMAN_REVIEW_DIR / "estg_150_human_correction_v1.json"

RETIRE_NOTE_OUT = HUMAN_REVIEW_DIR / "ESTG150_REVIEW_WORKFLOW_V1.md"


SCHEMA_VERSION = "estg_150_review_workflow@1.0.0"
SIX_ELEMENT_FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")
MODALITY_LABELS = ("obligation", "prohibition", "permission", "definition")
DECISION_VALUES = ("unreviewed", "accepted", "edited", "rejected", "needs_adjudication")
REVIEW_STATES = ("needs_review", "in_progress", "reviewed", "adjudicated")


def sha256_text(s: str | None) -> str | None:
    if s is None:
        return None
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def normalize_sample_id(legacy_id: int) -> str:
    """Canonical format: estg_000080 (6-digit zero-padded), matching the
    old canonical-review validator convention."""
    return f"estg_{legacy_id:06d}"


def load_de_source() -> dict[int, dict]:
    out: dict[int, dict] = {}
    with DE_SOURCE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            out[int(r["id"])] = r
    assert len(out) == 150, f"DE source must have 150 records, got {len(out)}"
    return out


def load_en_source() -> dict[int, dict]:
    out: dict[int, dict] = {}
    with EN_SOURCE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            out[int(r["id"])] = r
    assert len(out) == 150, f"EN source must have 150 records, got {len(out)}"
    return out


def load_llm_draft() -> dict[str, dict]:
    """Index by canonical sample_id (estg_000080)."""
    out: dict[str, dict] = {}
    with LLM_DRAFT_SOURCE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            sid = r["sample_id"]
            # Normalize short form (estg_080) to canonical (estg_000080).
            if sid.startswith("estg_") and not sid.startswith("estg_0000"):
                digits = sid[5:]
                if digits.isdigit():
                    sid = normalize_sample_id(int(digits))
            out[sid] = r
    return out


def find_unique_span(text: str, sub: str) -> tuple[int, int] | None:
    """Return (start, end) if `sub` appears exactly once in `text`, else None.
    The check is done on the full approved_text_en source; we never trim
    or normalize silently."""
    if sub is None:
        return None
    s = text.find(sub)
    if s < 0:
        return None
    e = text.find(sub, s + 1)
    if e >= 0:
        return None  # not unique
    return s, s + len(sub)


def derive_clause(llm_value: str | None, en_text: str, kind: str) -> dict:
    """Build one span dict for a six-element value."""
    if llm_value is None or str(llm_value).strip() == "":
        return {
            "value": None,
            "span": None,
            "span_status": "absent_in_llm_candidate",
            "derived_from_exact_unique_match": False,
        }
    value = str(llm_value)
    span = find_unique_span(en_text, value)
    if span is not None:
        start, end = span
        return {
            "value": value,
            "span": {"text": en_text[start:end], "start": start, "end": end},
            "span_status": "ok",
            "derived_from_exact_unique_match": True,
        }
    return {
        "value": value,
        "span": None,
        "span_status": "unresolved",
        "derived_from_exact_unique_match": False,
    }


def build_layer_b(en_source: dict[int, dict]) -> list[dict]:
    out = []
    for legacy_id in sorted(en_source.keys()):
        r = en_source[legacy_id]
        candidate_en = r.get("text_en")
        out.append({
            "sample_id": normalize_sample_id(legacy_id),
            "legacy_record_id": legacy_id,
            "raw_text_de_sha256": sha256_text(r.get("text_de")),
            "candidate_text_en": candidate_en,
            "candidate_text_en_sha256": sha256_text(candidate_en),
            "translation_source": "estg_selected_150_en_llm_translated.jsonl",
            "translation_model": "unknown_legacy",
            "immutable": True,
        })
    return out


def build_layer_c(llm_draft: dict[str, dict], en_source: dict[int, dict]) -> list[dict]:
    out = []
    for legacy_id in sorted(en_source.keys()):
        sid = normalize_sample_id(legacy_id)
        draft = llm_draft.get(sid)
        en_text = en_source[legacy_id].get("text_en") or ""
        if draft is None:
            # No LLM candidate for this sample — emit an empty candidate.
            out.append({
                "sample_id": sid,
                "legacy_record_id": legacy_id,
                "candidate_source": "estg_gold_150_llm_draft.jsonl",
                "candidate_sha256": None,
                "immutable": True,
                "human_approved": False,
                "clauses": [],
                "missing_in_llm_candidate": True,
            })
            continue
        gf = draft.get("gold_fields", {}) or {}
        # The legacy draft is single-clause; we still wrap it as one
        # clause object so the human_correction file can carry multi-clause.
        clause = {
            "clause_id": f"{sid}_c01",
            "clause_span": {
                "text": en_text,
                "start": 0,
                "end": len(en_text),
            },
            "clause_span_status": "covers_full_sentence",
            "modality": derive_clause(gf.get("modality", {}).get("value") if isinstance(gf.get("modality"), dict) else gf.get("modality"),
                                       en_text, "modality"),
            "actor": derive_clause(gf.get("actor", {}).get("value") if isinstance(gf.get("actor"), dict) else gf.get("actor"),
                                    en_text, "actor"),
            "action": derive_clause(gf.get("action", {}).get("value") if isinstance(gf.get("action"), dict) else gf.get("action"),
                                     en_text, "action"),
            "condition": derive_clause(gf.get("condition", {}).get("value") if isinstance(gf.get("condition"), dict) else gf.get("condition"),
                                        en_text, "condition"),
            "constraint": derive_clause(gf.get("constraint", {}).get("value") if isinstance(gf.get("constraint"), dict) else gf.get("constraint"),
                                         en_text, "constraint"),
            "exception": derive_clause(gf.get("exception", {}).get("value") if isinstance(gf.get("exception"), dict) else gf.get("exception"),
                                        en_text, "exception"),
            "actor_action_map": [],
            "order_relations": [],
        }
        out.append({
            "sample_id": sid,
            "legacy_record_id": legacy_id,
            "candidate_source": "estg_gold_150_llm_draft.jsonl",
            "candidate_sha256": sha256_text(json.dumps(draft, ensure_ascii=False, sort_keys=True)),
            "immutable": True,
            "human_approved": False,
            "missing_in_llm_candidate": False,
            "clauses": [clause],
        })
    return out


def build_layer_d(en_source: dict[int, dict]) -> list[dict]:
    """Chinese aid layer. All fields are null until the user authorizes
    a real LLM run; the schema is fixed so the review tool can render
    placeholders."""
    out = []
    for legacy_id in sorted(en_source.keys()):
        sid = normalize_sample_id(legacy_id)
        out.append({
            "sample_id": sid,
            "legacy_record_id": legacy_id,
            "text_zh": None,
            "back_translation_en": None,
            "clauses": [],
            "aid_source": "pending_authorized_llm_call",
            "model": None,
            "prompt_sha256": None,
            "immutable": True,
        })
    return out


def build_layer_e(
    en_source: dict[int, dict],
    de_source: dict[int, dict],
    layer_b: list[dict],
    layer_c: list[dict],
    layer_d: list[dict],
) -> dict:
    """The single editable file. llm_candidate is copied verbatim from
    layer C and is therefore immutable. human_correction starts as an
    unreviewed duplicate: same clauses, same fields, but every field's
    decision is unreviewed and review_state is needs_review."""
    layer_b_idx = {r["sample_id"]: r for r in layer_b}
    layer_c_idx = {r["sample_id"]: r for r in layer_c}
    layer_d_idx = {r["sample_id"]: r for r in layer_d}

    legacy_ids = sorted(en_source.keys())
    records = []
    for legacy_id in legacy_ids:
        sid = normalize_sample_id(legacy_id)
        de_row = de_source[legacy_id]
        en_row = en_source[legacy_id]
        b = layer_b_idx[sid]
        c = layer_c_idx[sid]
        d = layer_d_idx[sid]

        # Build the human_correction shell. We deep-copy the LLM clauses
        # but every field starts as unreviewed; the user later moves them
        # to accepted / edited / rejected / needs_adjudication.
        human_clauses = []
        for c_idx, lc in enumerate(c["clauses"], 1):
            new_clause = {
                "clause_id": f"{sid}_c{c_idx:02d}",
                "clause_span": dict(lc.get("clause_span", {})),
                "clause_span_status": lc.get("clause_span_status", "covers_full_sentence"),
                "modality": {
                    "value": None,
                    "decision": "unreviewed",
                    "span": None,
                    "notes": None,
                },
                "actors": [],
                "actions": [],
                "conditions": [],
                "constraints": [],
                "exceptions": [],
                "actor_action_map": [],
                "order_relations": [],
            }
            # IMPORTANT: copying = "is on the desk to be reviewed", not
            # "approved". Each span in human_correction starts with
            # decision=unreviewed and value=None, even if the LLM
            # candidate has a value. The reviewer must explicitly
            # accept / edit / reject each one.
            human_clauses.append(new_clause)

        record = {
            "sample_id": sid,
            "legacy_record_id": legacy_id,
            "source_refs": {
                "german_source": "data/development/estg/estg_selected_150_de.jsonl",
                "english_translation_source": "data/development/estg/estg_selected_150_en_llm_translated.jsonl",
                "llm_candidate_source": "data/development/estg/estg_gold_150_llm_draft.jsonl",
                "chinese_aid_source": "data/development/human_review/estg_150_review_aids_zh_v1.jsonl",
            },
            "raw_text_de": de_row.get("text"),
            "raw_text_de_sha256": sha256_text(de_row.get("text")),
            "candidate_text_en": b["candidate_text_en"],
            "candidate_text_en_sha256": b["candidate_text_en_sha256"],
            "approved_text_en": None,
            "approved_text_en_sha256": None,
            "approved_text_en_history": [],
            "llm_candidate": {
                "immutable": True,
                "candidate_source": c["candidate_source"],
                "candidate_sha256": c["candidate_sha256"],
                "missing_in_llm_candidate": c["missing_in_llm_candidate"],
                "clauses": c["clauses"],
            },
            "human_correction": {
                "approved_text_en": None,
                "approved_text_en_decision": "unreviewed",
                "translation_notes": None,
                "clauses": human_clauses,
            },
            "decisions": {
                "translation": "unreviewed",
                "modality": "unreviewed",
                "actor": "unreviewed",
                "action": "unreviewed",
                "condition": "unreviewed",
                "constraint": "unreviewed",
                "exception": "unreviewed",
            },
            "review_state": {
                "status": "needs_review",
                "reviewer": None,
                "reviewed_at": None,
                "adjudicated_at": None,
                "notes": None,
            },
        }
        records.append(record)
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": {
            "name": "independently_reconstructed_estg_150",
            "version": "v1",
            "workflow": "llm_assisted_human_adjudicated",
            "membership_count": 150,
            "membership_source": "data/development/estg/estg_selected_150_de.jsonl",
        },
        "records": records,
    }


def main() -> int:
    print("Loading source files ...")
    de_source = load_de_source()
    en_source = load_en_source()
    llm_draft = load_llm_draft()
    print(f"  DE source: {len(de_source)} records")
    print(f"  EN source: {len(en_source)} records")
    print(f"  LLM draft: {len(llm_draft)} records (legacy format, estg_080 form)")
    print()

    print("Building Layer B (English translation manifest, immutable) ...")
    layer_b = build_layer_b(en_source)
    with LAYER_B_OUT.open("w", encoding="utf-8") as f:
        for r in layer_b:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  Wrote {len(layer_b)} records -> {LAYER_B_OUT}")

    print("Building Layer C (LLM six-element candidate, immutable) ...")
    layer_c = build_layer_c(llm_draft, en_source)
    n_with_candidate = sum(1 for r in layer_c if not r["missing_in_llm_candidate"])
    n_unique = sum(
        1 for r in layer_c
        for c in r["clauses"]
        for f in [c["modality"], c["actor"], c["action"], c["condition"], c["constraint"], c["exception"]]
        if f.get("derived_from_exact_unique_match")
    )
    n_unresolved = sum(
        1 for r in layer_c
        for c in r["clauses"]
        for f in [c["modality"], c["actor"], c["action"], c["condition"], c["constraint"], c["exception"]]
        if f.get("span_status") == "unresolved"
    )
    with LAYER_C_OUT.open("w", encoding="utf-8") as f:
        for r in layer_c:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  Wrote {len(layer_c)} records -> {LAYER_C_OUT}")
    print(f"  records with LLM candidate: {n_with_candidate}/150")
    print(f"  spans derived by unique match: {n_unique}")
    print(f"  spans unresolved (no unique match): {n_unresolved}")

    print("Building Layer D (Chinese aid, all-null until authorized LLM) ...")
    layer_d = build_layer_d(en_source)
    with LAYER_D_OUT.open("w", encoding="utf-8") as f:
        for r in layer_d:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  Wrote {len(layer_d)} records -> {LAYER_D_OUT}")

    print("Building Layer E (human correction, only editable file) ...")
    layer_e_doc = build_layer_e(en_source, de_source, layer_b, layer_c, layer_d)
    LAYER_E_OUT.write_text(
        json.dumps(layer_e_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"  Wrote {len(layer_e_doc['records'])} records -> {LAYER_E_OUT}")
    # quick invariants
    assert len(layer_e_doc["records"]) == 150
    for r in layer_e_doc["records"]:
        for k, v in r["decisions"].items():
            assert v == "unreviewed", f"decision {k} on {r['sample_id']} is {v}"
        assert r["review_state"]["status"] == "needs_review"
        assert r["approved_text_en"] is None
        assert r["human_correction"]["approved_text_en"] is None
        for c in r["human_correction"]["clauses"]:
            assert c["modality"]["value"] is None
            assert c["modality"]["decision"] == "unreviewed"
    print("  Invariants: 150 records, all decisions=unreviewed, all review_state=needs_review, all approved_text_en=null")

    print()
    print("Writing workflow retirement note ...")
    note = f"""# EStG-150 Review Workflow v1 (LLM-assisted, human-adjudicated)

**Effective**: 2026-07-12. **Scope**: replaces the
`estg_150_canonical_review_v1.json` schema as the active editing surface
for EStG-150 v1. The old file is preserved as a retired workflow draft
and remains a valid read-only provenance artifact.

## 5 layers

| Layer | File | Role | Editable? |
|---|---|---|---|
| A. German source | `data/development/estg/estg_selected_150_de.jsonl` | original EStG clause text | **immutable** (no tool writes here) |
| B. English translation | `data/development/human_review/estg_150_translation_en_v1.jsonl` | LLM-produced English candidate + provenance | **immutable** (review tool cannot overwrite `candidate_text_en`) |
| C. LLM six-element candidate | `data/development/human_review/estg_150_llm_six_element_candidates_v1.jsonl` | per-clause modality/actor/action/condition/constraint/exception from legacy LLM draft | **immutable** |
| D. Chinese review aid | `data/development/human_review/estg_150_review_aids_zh_v1.jsonl` | Chinese gloss + English back-translation | **immutable, fields null until authorized LLM call** |
| E. Human correction | `data/development/human_review/estg_150_human_correction_v1.json` | LLM candidate is copied here as `llm_candidate` (immutable); the user edits `human_correction`, `decisions`, and `review_state` | **only editable file** |

## How "copy" works

`llm_candidate` in layer E is a verbatim copy of layer C for that
sample. The user does **not** edit it.

`human_correction.clauses[]` is a duplicate of the LLM clause list
with the same `clause_id` and `clause_span`, but **every** field starts
as `decision=unreviewed` and `value=null`. The user explicitly
moves each field to `accepted` / `edited` / `rejected` /
`needs_adjudication`. A copy on disk is **not** an approval.

## What this workflow does NOT do

- Does not call a real LLM/API in this build.
- Does not fabricate Chinese translations.
- Does not write to the old `estg_150_canonical_review_v1.json`.
- Does not pre-approve any field.
- Does not freeze the formal Gold; final Gold is
  `LLM-assisted, human-adjudicated Gold` and is only declared after
  the user finishes layer E and the validator confirms freeze_ready.

## Tooling

- Review tool: `python formal_experiment/scripts/estg150_review_tool.py`
  (default: opens layer E)
- Validator: `python formal_experiment/scripts/validate_human_correction.py`
- Action log: `outputs/development/human_review/estg_150_review_actions_v1.jsonl`
- Backups: `outputs/development/human_review/review_backups/`

## Retired files

- `estg_150_canonical_review_v1.json` is the previous workflow draft
  (single editing surface, three-pane UI). It is preserved for
  provenance and remains in the audit's read path. Any new editing
  must go through layer E.
- `estg_gold_150_v1_backup.jsonl` and
  `estg_gold_150_v2_distribution_targeted.jsonl` remain as
  development-only provenance; they are not mixed into layer C.
"""
    RETIRE_NOTE_OUT.write_text(note, encoding="utf-8")
    print(f"  Wrote {RETIRE_NOTE_OUT}")
    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
