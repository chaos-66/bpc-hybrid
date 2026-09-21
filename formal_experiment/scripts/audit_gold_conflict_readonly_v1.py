"""Read-only Gold conflict audit v1 (zero API, zero mutation).

Produces three human-review lists from FROZEN artifacts only:

  L1  Gold internal consistency: cue tokens whose Gold field assignment is
      non-uniform across clauses (same surface cue -> two different fields).
  L2  Consensus disagreements: clauses where several independent extraction
      methods fail in the SAME direction while Gold says otherwise, i.e.
      candidates for annotation review rather than method error.
  L3  Near-duplicate clause pairs with different Gold modality: the
      annotation-inconsistency pattern (e.g. two nearly identical sentences
      labelled differently).

This script never writes Gold, predictions, prompts, evaluator or any
historical report. It only reads frozen artifacts and writes one new report.

Usage:
    python formal_experiment/scripts/audit_gold_conflict_readonly_v1.py
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
FE = REPO / "formal_experiment"

GOLD = FE / "data/gold/stage2/estg150_formal_gold_v1.json"
PANEL = FE / "data/gold/stage3/stage3_violation_gold_v1.json"
OUT_JSON = FE / "outputs/reports/gold_conflict_audit_readonly_v1.json"
OUT_MD = FE / "outputs/reports/gold_conflict_audit_readonly_v1.md"

FIELDS = ("actor", "action", "condition", "constraint", "exception")

# Cue tokens that the project has already flagged as ambiguous
# (see docs/B0_ERROR_ANALYSIS.md: relationship pronouns and "only" are
# labelled inconsistently; "to the extent" is mostly condition with 2
# constraint cases).
CUE_PATTERNS: list[tuple[str, str]] = [
    ("to_the_extent", r"\bto the extent\b"),
    ("only", r"\bonly\b"),
    ("that_rel", r"\bthat\b"),
    ("which_rel", r"\bwhich\b"),
    ("who_rel", r"\bwho\b"),
    ("if", r"\bif\b"),
    ("when", r"\bwhen\b"),
    ("unless", r"\bunless\b"),
    ("where", r"\bwhere\b"),
    ("in_accordance_with", r"\bin accordance with\b"),
    ("pursuant_to", r"\bpursuant to\b"),
    ("within_N", r"\bwithin\b"),
    ("at_least", r"\bat least\b"),
    ("provided_that", r"\bprovided that\b"),
    ("in_the_event_of", r"\bin the event of\b"),
    ("without_undue_delay", r"\bwithout undue delay\b"),
]

NEGATIVE_MARKERS = ("not", "no ", "never", "neither", "nor ")


def load_gold() -> dict[str, Any]:
    return json.loads(GOLD.read_text(encoding="utf-8"))


def iter_clauses(gold: dict[str, Any]):
    for rec in gold["records"]:
        for cl in rec["clauses"]:
            yield rec, cl


def gold_field_texts(clause: dict[str, Any]) -> dict[str, list[str]]:
    return {f: [s["text"] for s in clause.get(f"{f}s", [])] for f in FIELDS}


# ---------------------------------------------------------------- L1
def build_l1(gold: dict[str, Any]) -> list[dict[str, Any]]:
    """Same cue token -> non-uniform Gold field assignment."""
    per_cue: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for rec, cl in iter_clauses(gold):
        text = rec["approved_text_en"]
        fields = gold_field_texts(cl)
        for cue, pat in CUE_PATTERNS:
            if not re.search(pat, text, flags=re.IGNORECASE):
                continue
            hit = [f for f in FIELDS if any(re.search(pat, t, re.IGNORECASE) for t in fields[f])]
            if len(hit) == 1:
                per_cue[cue][hit[0]] += 1
                if len(examples[(cue, hit[0])]) < 3:
                    span = next(t for f in hit for t in fields[f] if re.search(pat, t, re.IGNORECASE))
                    examples[(cue, hit[0])].append(
                        {"sample_id": rec["sample_id"], "clause_id": cl["clause_id"], "span_text": span}
                    )
            elif len(hit) > 1:
                per_cue[cue]["MULTI:" + "+".join(sorted(hit))] += 1
            else:  # cue present in sentence but not inside any field span
                per_cue[cue]["SENTENCE_ONLY"] += 1

    rows = []
    for cue, counter in per_cue.items():
        real = {k: v for k, v in counter.items() if not k.startswith("MULTI:") and k != "SENTENCE_ONLY"}
        if len(real) >= 2:
            rows.append(
                {
                    "cue": cue,
                    "distribution": dict(sorted(counter.items(), key=lambda kv: -kv[1])),
                    "conflicting_fields": sorted(real),
                    "examples": {
                        f"{cue}|{f}": examples.get((cue, f), []) for f in sorted(real)
                    },
                }
            )
    rows.sort(key=lambda r: (-len(r["conflicting_fields"]), r["cue"]))
    return rows


# ---------------------------------------------------------------- L2
def build_l2() -> list[dict[str, Any]]:
    """Stage 3 items where every available method misses the same Gold."""
    panel = json.loads(PANEL.read_text(encoding="utf-8"))
    gold_type = {it["item_id"]: it["decision_violation_type"] for it in panel["items"]}

    methods = ["s34_winter_stage3_development_v3_clean",
               "s35_sun_stage3_development_v2",
               "s36_bm25_stage3_development_v3",
               "s36_tfidf_svd_stage3_development_v2"]
    preds: dict[str, dict[str, str | None]] = {}
    for m in methods:
        p = FE / f"outputs/development/{m}/predictions.jsonl"
        if not p.exists():
            continue
        rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        preds[m] = {
            r["item_id"]: r.get("predicted_violation_type")
            for r in rows
            if r.get("task") == "violation"
        }

    out = []
    for item_id, gt in sorted(gold_type.items()):
        votes = {m: preds[m].get(item_id) for m in preds}
        if votes and all(v != gt for v in votes.values()):
            out.append(
                {
                    "item_id": item_id,
                    "gold_type": gt,
                    "method_predictions": votes,
                    "all_methods_agree_on": (
                        "abstain(none)" if all(v is None for v in votes.values()) else "not-gold"
                    ),
                }
            )
    return out


# ---------------------------------------------------------------- L3
def build_l3(gold: dict[str, Any], threshold: float = 0.90) -> list[dict[str, Any]]:
    """Near-identical clauses that carry different Gold modality."""
    clauses = []
    for rec, cl in iter_clauses(gold):
        clauses.append(
            {
                "sample_id": rec["sample_id"],
                "clause_id": cl["clause_id"],
                "modality": cl["modality"],
                "text": cl["clause_span"]["text"].strip(),
            }
        )

    out = []
    for a, b in combinations(clauses, 2):
        if a["text"] == b["text"]:
            ratio = 1.0
        else:
            if abs(len(a["text"]) - len(b["text"])) > 0.5 * max(len(a["text"]), len(b["text"])):
                continue
            ratio = SequenceMatcher(None, a["text"], b["text"]).ratio()
        if ratio >= threshold and a["modality"] != b["modality"]:
            out.append(
                {
                    "similarity": round(ratio, 4),
                    "a": {"sample_id": a["sample_id"], "clause_id": a["clause_id"],
                          "modality": a["modality"], "text": a["text"][:300]},
                    "b": {"sample_id": b["sample_id"], "clause_id": b["clause_id"],
                          "modality": b["modality"], "text": b["text"][:300]},
                }
            )
    out.sort(key=lambda r: -r["similarity"])
    return out


def to_md(l1, l2, l3, meta) -> str:
    lines = [
        "# Gold conflict audit (read-only, zero API)",
        "",
        f"- gold: `{meta['gold_path']}` sha256 `{meta['gold_sha256']}`",
        f"- panel: `{meta['panel_path']}` sha256 `{meta['panel_sha256']}`",
        f"- clauses scanned: {meta['n_clauses']}  ·  records: {meta['n_records']}",
        f"- new API calls: **0**  ·  artifacts modified: **0**",
        "",
        "> Purpose: produce human-review queues only. Nothing here changes Gold,",
        "> predictions, prompts or the evaluator. Every finding requires human",
        "> adjudication against the source text before any action is taken.",
        "",
        "## L1 — same cue, non-uniform Gold field assignment",
        "",
    ]
    if not l1:
        lines.append("_none found_")
    for row in l1:
        lines.append(f"### `{row['cue']}`  ->  " + ", ".join(row["conflicting_fields"]))
        lines.append("")
        lines.append("| field | count | example span |")
        lines.append("|---|---:|---|")
        for f, c in row["distribution"].items():
            if f.startswith("MULTI:") or f == "SENTENCE_ONLY":
                lines.append(f"| {f} | {c} | — |")
            else:
                ex = row["examples"].get(f"{row['cue']}|{f}", [])
                span = ex[0]["span_text"][:80] if ex else ""
                sid = ex[0]["sample_id"] if ex else ""
                lines.append(f"| {f} | {c} | `{span}` ({sid}) |")
        lines.append("")

    lines += ["## L2 — Stage 3 items all methods miss", "",
              f"total: **{len(l2)} / 33**", "",
              "| item | gold type | winter | sun | bm25 | tfidf | pattern |",
              "|---|---|---|---|---|---|---|"]
    for r in l2:
        v = r["method_predictions"]
        lines.append(
            f"| {r['item_id']} | {r['gold_type']} | {v.get('s34_winter_stage3_development_v3_clean')} "
            f"| {v.get('s35_sun_stage3_development_v2')} | {v.get('s36_bm25_stage3_development_v3')} "
            f"| {v.get('s36_tfidf_svd_stage3_development_v2')} | {r['all_methods_agree_on']} |"
        )

    lines += ["", "## L3 — near-identical clauses with different Gold modality", "",
              f"total: **{len(l3)}**  (similarity >= 0.90)", ""]
    for r in l3:
        lines.append(f"### similarity {r['similarity']}")
        lines.append(f"- A `{r['a']['sample_id']}` / `{r['a']['clause_id']}` -> **{r['a']['modality']}**: {r['a']['text']}")
        lines.append(f"- B `{r['b']['sample_id']}` / `{r['b']['clause_id']}` -> **{r['b']['modality']}**: {r['b']['text']}")
        lines.append("")

    lines += [
        "## Next step (human only)",
        "",
        "1. For each L1 cue: decide whether the two assignments are both legally",
        "   correct (context-dependent) or one is an annotation slip.",
        "2. For each L2 item: re-read the regulation article and the process model;",
        "   decide whether Gold, the input binding, or the detector is at fault.",
        "3. For each L3 pair: decide which label is right and whether a rule is missing.",
        "4. Only after human adjudication may a NEW Gold version be created; the old",
        "   version and all affected results are kept and reported side by side.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    import hashlib

    gold = load_gold()
    meta = {
        "gold_path": str(GOLD.relative_to(REPO)),
        "gold_sha256": hashlib.sha256(GOLD.read_bytes()).hexdigest(),
        "panel_path": str(PANEL.relative_to(REPO)),
        "panel_sha256": hashlib.sha256(PANEL.read_bytes()).hexdigest(),
        "n_records": len(gold["records"]),
        "n_clauses": sum(len(r["clauses"]) for r in gold["records"]),
    }

    l1 = build_l1(gold)
    l2 = build_l2()
    l3 = build_l3(gold)

    report = {
        "schema_version": "gold_conflict_audit_readonly@1.0.0",
        "status": "read_only_audit_zero_api",
        "network_calls": 0,
        "llm_calls": 0,
        "artifacts_modified": 0,
        "meta": meta,
        "L1_cue_field_conflicts": l1,
        "L2_consensus_disagreements": l2,
        "L3_near_duplicate_modality_conflicts": l3,
        "boundary": (
            "Findings are review candidates, not proven annotation errors. "
            "No Gold/prediction/prompt/evaluator was modified. Any correction "
            "requires human adjudication against the source text and a new "
            "versioned Gold; original results must remain reported."
        ),
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(to_md(l1, l2, l3, meta), encoding="utf-8")

    print(f"L1 cue conflicts : {len(l1)}")
    print(f"L2 all-miss items: {len(l2)}")
    print(f"L3 modality pairs: {len(l3)}")
    print(f"wrote {OUT_JSON.relative_to(REPO)}")
    print(f"wrote {OUT_MD.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
