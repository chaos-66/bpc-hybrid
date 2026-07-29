"""B3a Phase-1 readonly constraint FN/FP diagnostic (development construction only).

Does not produce a performance candidate run. Does not modify Gold/predictions.
Optional CoreNLP offline parse uses frozen runtime and approved English only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.estg150_b0_development import (
    build_canonical_gold_records,
    load_object,
    sha256_file,
)
from bpc_hybrid.stage2_evaluation import _char_iou
from bpc_hybrid.stage2_evaluation_v3 import CLAUSE_MINIMUM_IOU, clause_iou_pairs

PARENT_MAN = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/manifest.json"
PARENT_ATT = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json"
PAT_V3 = ROOT / "resources/corenlp/sun_phrase_patterns_v3_enhanced.json"
LEX_CONS = ROOT / "resources/lexicon/constraint_markers_en_v2.json"
LEX_MAN = ROOT / "resources/lexicon/public_marker_lexicon_en_v2.manifest.json"
BRIDGE = ROOT / "tools/corenlp/SunPhraseRuleBatchBridgeMulti.java"
EVAL = ROOT / "configs/stage2_evaluator_s210_v3.json"

EXPECTED = {
    "parent_man": "88070fab4da3f7c708f055f6bc391b78cc888761c3d6fe117d17673c2c382315",
    "pat_v3": "f49bad50fb6236137f1208aeef572d2a78c789726363897c637dc464c780e142",
    "bridge": "1a084befaf1a863889a26b58c5a049f2df846834e26c5643fe5a535c5c13f2a3",
    "lex_man": "3f7e6108c1e66de37377abc2e9b9f4d0344ff2d1eca20b49ebf90e38aff7b462",
    "eval": "28ce332564c5d10da08dea515aefe31cc2aacd91b6c6877aa1bfebe44f39ae7f",
}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _write(path: Path, obj: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


TEMPORAL = {
    "within", "before", "after", "until", "prior to", "no later than",
    "no earlier than", "during", "throughout", "for a period", "for the duration",
}
QUANT = {
    "at least", "at most", "no more", "no less", "no more than", "no less than",
    "not to exceed", "exceeds", "minimum", "maximum", "exactly", "up to",
    "greater", "less", "equal", "not equal",
}
LEGAL = {
    "pursuant to", "in accordance with", "subject to", "under", "under section",
    "for the purpose of", "for the purposes of", "for purposes of",
    "as defined in", "within the meaning",
}


def classify_family(text: str, anchors: list[str]) -> str:
    t = text.casefold()
    for a in sorted(anchors, key=len, reverse=True):
        if a.casefold() in t:
            ac = a.casefold()
            if ac in TEMPORAL or any(x in ac for x in ("within", "before", "after", "until", "prior", "later", "period", "duration")):
                return "temporal"
            if ac in QUANT or any(x in ac for x in ("least", "most", "more", "less", "exceed", "minimum", "maximum", "exactly", "equal")):
                return "quantitative"
            if ac in LEGAL or any(x in ac for x in ("pursuant", "accordance", "purpose", "under", "section", "defined", "meaning", "subject")):
                return "legal_scope_purpose"
    # fallback lexical
    if re.search(r"\b(?:within|before|after|until|prior|during)\b", t):
        return "temporal"
    if re.search(r"\b(?:at least|no more|exceed|minimum|maximum)\b", t):
        return "quantitative"
    if re.search(r"\b(?:pursuant|accordance|purpose|under section|subject to)\b", t):
        return "legal_scope_purpose"
    return "other"


def marker_hits(text: str, surfaces: list[str]) -> list[str]:
    t = text.casefold()
    hits = []
    for s in sorted(surfaces, key=len, reverse=True):
        if s.casefold() in t:
            hits.append(s)
    return hits


def any_overlap(a: dict, b: dict) -> bool:
    return _char_iou(a, b) > 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime-home", type=Path, default=None)
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs/development/s27_estg150_b0_b3a_constraint_tregex_diagnostic_v1",
    )
    args = ap.parse_args()
    out = args.output_dir.resolve()
    if out.exists():
        print(f"refusing overwrite: {out}", file=sys.stderr)
        return 2

    # hash lock
    got = {
        "parent_man": _sha(PARENT_MAN),
        "pat_v3": _sha(PAT_V3),
        "bridge": _sha(BRIDGE),
        "lex_man": _sha(LEX_MAN),
        "eval": _sha(EVAL),
    }
    for k, exp in EXPECTED.items():
        if got[k] != exp:
            print(f"hash mismatch {k}: {got[k]} != {exp}", file=sys.stderr)
            return 2

    gold, sources = build_canonical_gold_records(
        ROOT / "data/development/human_review/estg_150_human_correction_v1.json",
        ROOT / "data/development/estg/estg_150_membership_hashes.json",
    )
    attempts = json.loads(PARENT_ATT.read_text(encoding="utf-8"))
    pred_by = {a["sample_id"]: a["record"] for a in attempts}
    cons_lex = json.loads(LEX_CONS.read_text(encoding="utf-8"))
    surfaces = [e["surface"] for e in cons_lex["entries"] if e.get("surface")]

    fn_buckets = Counter()
    fp_buckets = Counter()
    fn_examples_meta = []  # aggregate only, no sample_id in final export of texts
    # recoverable-by-anchor stats
    fn_with_parent_anchor = 0
    fn_without_parent_anchor = 0
    family_fn = Counter()
    family_fp = Counter()

    # collect gold FN spans with hash only
    recoverable_candidates = []  # for pattern estimation: {en_text, gold_span_rel, family, anchors}

    for g in gold:
        sid = g["sample_id"]
        p = pred_by[sid]
        pairs, miss_g, extra_p, _ = clause_iou_pairs(
            g.get("clauses") or [], p.get("clauses") or [], minimum_iou=CLAUSE_MINIMUM_IOU
        )
        p_to_g = {pi: gi for gi, pi in pairs}
        # FN: gold constraints not hit by any pred constraint in matched clause
        matched_g = {gi for gi, _ in pairs}
        for gi, gcl in enumerate(g.get("clauses") or []):
            g_cons = list(gcl.get("constraints") or [])
            if not g_cons:
                continue
            if gi not in matched_g:
                for gs in g_cons:
                    fn_buckets["1_clause_unaligned_unrecoverable"] += 1
                    family_fn[classify_family(gs.get("text") or "", surfaces)] += 1
                continue
            # find pred clause
            pi = next(p for g2, p in pairs if g2 == gi)
            pcl = p["clauses"][pi]
            p_cons = list(pcl.get("constraints") or [])
            p_cond = list(pcl.get("conditions") or [])
            p_exc = list(pcl.get("exceptions") or [])
            p_act = list(pcl.get("actions") or [])
            p_actor = list(pcl.get("actors") or [])
            en = p["source_text"][int(pcl["clause_span"]["start"]) : int(pcl["clause_span"]["end"])]
            used_p = set()
            for gs in g_cons:
                hit = None
                for j, ps in enumerate(p_cons):
                    if j in used_p:
                        continue
                    if any_overlap(gs, ps):
                        hit = j
                        break
                if hit is not None:
                    used_p.add(hit)
                    continue
                # FN
                fam = classify_family(gs.get("text") or "", surfaces)
                family_fn[fam] += 1
                anchors = marker_hits(gs.get("text") or "", surfaces)
                anchors_en = marker_hits(en, surfaces)
                has_anchor = bool(anchors or anchors_en)
                if has_anchor:
                    fn_with_parent_anchor += 1
                else:
                    fn_without_parent_anchor += 1
                # classify fn type
                if not p_cons and not p_cond and not p_exc:
                    key = "2_aligned_no_constraint_candidate"
                elif any(any_overlap(gs, x) for x in p_cond):
                    key = "4_extracted_as_condition"
                elif any(any_overlap(gs, x) for x in p_exc):
                    key = "5_extracted_as_exception"
                elif any(any_overlap(gs, x) for x in p_act) or any(any_overlap(gs, x) for x in p_actor):
                    key = "6_extracted_as_action_or_actor"
                elif p_cons and not any(any_overlap(gs, x) for x in p_cons):
                    key = "3_candidate_exists_but_no_overlap"
                else:
                    key = "2_aligned_no_constraint_candidate"
                if has_anchor and key in {
                    "2_aligned_no_constraint_candidate",
                    "3_candidate_exists_but_no_overlap",
                }:
                    fn_buckets["7_has_parent_anchor_but_tregex_undercover"] += 1
                if not has_anchor:
                    fn_buckets["8_no_parent_lexicon_anchor_out_of_scope"] += 1
                fn_buckets[key] += 1
                # family subtype buckets
                if fam == "temporal":
                    fn_buckets["9_temporal"] += 1
                elif fam == "quantitative":
                    fn_buckets["10_quantitative"] += 1
                elif fam == "legal_scope_purpose":
                    fn_buckets["11_legal_scope_purpose"] += 1
                else:
                    fn_buckets["12_other_non_generalizable"] += 1
                # for pattern estimation: use gold constraint surface text as recovery target
                recoverable_candidates.append(
                    {
                        "en_clause_sha256": hashlib.sha256(en.encode()).hexdigest()[:16],
                        "gold_text_sha256": hashlib.sha256((gs.get("text") or "").encode()).hexdigest()[:16],
                        "gold_text_len": len(gs.get("text") or ""),
                        "family": fam,
                        "anchors": anchors or anchors_en,
                        "gold_start": int(gs.get("start", 0)),
                        "gold_end": int(gs.get("end", 0)),
                        "clause_start": int(pcl["clause_span"]["start"]),
                        "clause_end": int(pcl["clause_span"]["end"]),
                        "en_clause": en,  # kept only in staging for pattern sim; stripped from public export
                    }
                )

        # FP: pred constraints not hitting gold
        for pi, pcl in enumerate(p.get("clauses") or []):
            p_cons = list(pcl.get("constraints") or [])
            if not p_cons:
                continue
            gi = p_to_g.get(pi)
            g_cons = list((g["clauses"][gi].get("constraints") or []) if gi is not None else [])
            g_cond = list((g["clauses"][gi].get("conditions") or []) if gi is not None else [])
            g_exc = list((g["clauses"][gi].get("exceptions") or []) if gi is not None else [])
            g_act = list((g["clauses"][gi].get("actions") or []) if gi is not None else [])
            g_actor = list((g["clauses"][gi].get("actors") or []) if gi is not None else [])
            used_g = set()
            for ps in p_cons:
                hit = None
                for j, gs in enumerate(g_cons):
                    if j in used_g:
                        continue
                    if any_overlap(ps, gs):
                        hit = j
                        break
                if hit is not None:
                    used_g.add(hit)
                    continue
                # FP
                fam = classify_family(ps.get("text") or "", surfaces)
                family_fp[fam] += 1
                ptxt = (ps.get("text") or "").strip()
                if gi is None:
                    fp_buckets["8_clause_no_gold_constraint_context"] += 1
                elif not g_cons:
                    fp_buckets["8_clause_no_gold_constraint"] += 1
                if any(any_overlap(ps, x) for x in g_cond):
                    fp_buckets["1_overlaps_gold_condition"] += 1
                elif any(any_overlap(ps, x) for x in g_exc):
                    fp_buckets["2_overlaps_gold_exception"] += 1
                elif any(any_overlap(ps, x) for x in g_act) or any(any_overlap(ps, x) for x in g_actor):
                    fp_buckets["3_overlaps_gold_action_or_actor"] += 1
                elif len(ptxt.split()) <= 2 and marker_hits(ptxt, surfaces):
                    fp_buckets["5_marker_only_fragment"] += 1
                elif gi is not None:
                    cspan = pcl["clause_span"]
                    if abs(int(ps.get("start", 0)) - int(cspan["start"])) <= 1 and abs(
                        int(ps.get("end", 0)) - int(cspan["end"])
                    ) <= 1:
                        fp_buckets["6_full_clause_overcapture"] += 1
                    elif ptxt.lower().startswith(("in ", "for ", "by ", "to ", "with ")):
                        fp_buckets["4_generic_pp"] += 1
                    else:
                        fp_buckets["9_boundary_or_other"] += 1
                else:
                    fp_buckets["10_other"] += 1

    # --- Candidate pattern proposals (construction only) ---
    # Patterns use only parent lexicon anchors, constituency-friendly Tregex.
    # Estimate recovery by simple surface/heuristic constituency proxy on EN clause text:
    # We use regex span approximation for diagnostic precision estimate, then live CoreNLP
    # will validate patterns in tests. This is development construction, not independent eval.
    candidate_patterns = [
        {
            "pattern_id": "b3a_c_temp_within_pp",
            "field": "constraint",
            "tregex": "PP=constraint < (IN < /(?i)^(within)$/) < NP",
            "anchors": ["within"],
            "family": "temporal",
            "parse_template": "PP → IN=within NP",
            "positives": [
                "The return must be filed within 30 days of the assessment.",
                "Payment is due within two months after the end of the year.",
            ],
            "negatives": [
                "If the taxpayer files late, a surcharge applies.",
                "The authority may inspect the books.",
            ],
        },
        {
            "pattern_id": "b3a_c_temp_before_after_pp",
            "field": "constraint",
            "tregex": "PP=constraint < (IN < /(?i)^(before|after|until)$/) < NP",
            "anchors": ["before", "after", "until"],
            "family": "temporal",
            "parse_template": "PP → IN=before|after|until NP",
            "positives": [
                "The election must be made before the end of the calendar year.",
                "No distribution may be made until the reserve is filled.",
            ],
            "negatives": [
                "Unless the office objects, the plan continues.",
                "The company shall prepare annual accounts.",
            ],
        },
        {
            "pattern_id": "b3a_c_temp_no_later_than",
            "field": "constraint",
            "tregex": "PP=constraint << /(?i)^(no)$/ << /(?i)^(later)$/ << /(?i)^(than)$/",
            "anchors": ["no later than"],
            "family": "temporal",
            "parse_template": "PP containing no later than",
            "positives": [
                "Notice shall be given no later than three months after receipt.",
                "The application must arrive no later than 31 December.",
            ],
            "negatives": [
                "The taxpayer may not sell the asset.",
                "Subject to section 5, the rule applies.",
            ],
        },
        {
            "pattern_id": "b3a_c_quant_at_least",
            "field": "constraint",
            "tregex": "NP=constraint << /(?i)^(at)$/ << /(?i)^(least|most)$/",
            "anchors": ["at least", "at most"],
            "family": "quantitative",
            "parse_template": "NP containing at least/most",
            "positives": [
                "The reserve shall amount to at least 10 percent of profits.",
                "The holding must be at most one quarter of the capital.",
            ],
            "negatives": [
                "At least the company filed on time, which is good.",  # discourse, not constraint - may FP
                "If profits increase, the rate may change.",
            ],
        },
        {
            "pattern_id": "b3a_c_quant_no_more_than",
            "field": "constraint",
            "tregex": "NP=constraint << /(?i)^(no)$/ << /(?i)^(more|less)$/ << /(?i)^(than)$/",
            "anchors": ["no more than", "no less than", "no more", "no less"],
            "family": "quantitative",
            "parse_template": "NP containing no more/less than",
            "positives": [
                "The deduction shall not exceed no more than the documented costs.",
                "The shareholding may amount to no less than one tenth.",
            ],
            "negatives": [
                "No more applications were received this year.",
                "Unless more capital is contributed, voting rights stay.",
            ],
        },
        {
            "pattern_id": "b3a_c_legal_pursuant_accordance",
            "field": "constraint",
            "tregex": "PP=constraint < (IN < /(?i)^(pursuant|in)$/) << /(?i)^(to|accordance|with)$/",
            "anchors": ["pursuant to", "in accordance with"],
            "family": "legal_scope_purpose",
            "parse_template": "PP pursuant to / in accordance with",
            "positives": [
                "Valuation shall be made pursuant to section 6 of this Act.",
                "Records must be kept in accordance with commercial law.",
            ],
            "negatives": [
                "In case of doubt, the authority decides.",
                "The taxpayer who files late shall pay a surcharge.",
            ],
        },
    ]

    def approx_match_spans(en: str, pattern_id: str) -> list[tuple[int, int, str]]:
        """Surface approximation of constituency span for diagnostic only."""
        spans = []
        t = en
        if pattern_id == "b3a_c_temp_within_pp":
            for m in re.finditer(r"\bwithin\b[\w\s,-]{0,40}", t, re.I):
                spans.append((m.start(), m.end(), m.group(0)))
        elif pattern_id == "b3a_c_temp_before_after_pp":
            for m in re.finditer(r"\b(?:before|after|until)\b[\w\s,-]{0,40}", t, re.I):
                spans.append((m.start(), m.end(), m.group(0)))
        elif pattern_id == "b3a_c_temp_no_later_than":
            for m in re.finditer(r"\bno\s+later\s+than\b[\w\s,-]{0,40}", t, re.I):
                spans.append((m.start(), m.end(), m.group(0)))
        elif pattern_id == "b3a_c_quant_at_least":
            for m in re.finditer(r"\bat\s+(?:least|most)\b[\w\s,%.-]{0,30}", t, re.I):
                spans.append((m.start(), m.end(), m.group(0)))
        elif pattern_id == "b3a_c_quant_no_more_than":
            for m in re.finditer(r"\bno\s+(?:more|less)(?:\s+than)?\b[\w\s,%.-]{0,30}", t, re.I):
                spans.append((m.start(), m.end(), m.group(0)))
        elif pattern_id == "b3a_c_legal_pursuant_accordance":
            for m in re.finditer(
                r"\b(?:pursuant\s+to|in\s+accordance\s+with)\b[\w\s,.-]{0,40}", t, re.I
            ):
                spans.append((m.start(), m.end(), m.group(0)))
        return spans

    # Build parent pred constraint set per clause text hash for novelty
    parent_pred_spans_by_clause = {}
    for a in attempts:
        rec = a["record"]
        for cl in rec.get("clauses") or []:
            c0, c1 = int(cl["clause_span"]["start"]), int(cl["clause_span"]["end"])
            en = rec["source_text"][c0:c1]
            key = hashlib.sha256(en.encode()).hexdigest()
            parent_pred_spans_by_clause.setdefault(key, [])
            for ps in cl.get("constraints") or []:
                parent_pred_spans_by_clause[key].append(
                    {
                        "start": int(ps["start"]) - c0,
                        "end": int(ps["end"]) - c0,
                        "text": ps.get("text") or "",
                    }
                )

    # Evaluate each pattern against recoverable FN list (construction estimate)
    # Also estimate FP: matches on clauses with no gold constraint
    gold_cons_by_clause_en = defaultdict(list)
    gold_has_cons = set()
    for g in gold:
        p = pred_by[g["sample_id"]]
        pairs, _, _, _ = clause_iou_pairs(
            g.get("clauses") or [], p.get("clauses") or [], minimum_iou=CLAUSE_MINIMUM_IOU
        )
        for gi, pi in pairs:
            en = p["source_text"][
                int(p["clauses"][pi]["clause_span"]["start"]) : int(
                    p["clauses"][pi]["clause_span"]["end"]
                )
            ]
            key = hashlib.sha256(en.encode()).hexdigest()
            for gs in g["clauses"][gi].get("constraints") or []:
                gold_cons_by_clause_en[key].append(
                    {
                        "start": int(gs["start"]) - int(p["clauses"][pi]["clause_span"]["start"]),
                        "end": int(gs["end"]) - int(p["clauses"][pi]["clause_span"]["start"]),
                        "text": gs.get("text") or "",
                    }
                )
                gold_has_cons.add(key)

    pattern_stats = []
    for pat in candidate_patterns:
        rec_fn = 0
        rec_records = set()
        hit_spans = 0
        new_spans = 0
        dup_parent = 0
        fp_new = 0
        # FN recovery
        for item in recoverable_candidates:
            en = item["en_clause"]
            key = item["en_clause_sha256"]  # short - rebuild
            key_full = hashlib.sha256(en.encode()).hexdigest()
            spans = approx_match_spans(en, pat["pattern_id"])
            if not spans:
                continue
            # only count if pattern anchors present
            if not any(a.casefold() in en.casefold() for a in pat["anchors"]):
                continue
            gspan = {
                "start": item["gold_start"] - item["clause_start"],
                "end": item["gold_end"] - item["clause_start"],
            }
            for s, e, txt in spans:
                hit_spans += 1
                psp = {"start": s, "end": e, "text": txt}
                # novelty vs parent
                parent_list = parent_pred_spans_by_clause.get(key_full, [])
                if any(any_overlap(psp, pp) for pp in parent_list):
                    dup_parent += 1
                else:
                    new_spans += 1
                if any_overlap(psp, gspan):
                    rec_fn += 1
                    rec_records.add(key_full)
                    break
        # FP estimate: apply to all pred clauses without gold constraint
        for a in attempts:
            rec = a["record"]
            for cl in rec.get("clauses") or []:
                c0, c1 = int(cl["clause_span"]["start"]), int(cl["clause_span"]["end"])
                en = rec["source_text"][c0:c1]
                key_full = hashlib.sha256(en.encode()).hexdigest()
                if key_full in gold_has_cons:
                    continue
                spans = approx_match_spans(en, pat["pattern_id"])
                parent_list = parent_pred_spans_by_clause.get(key_full, [])
                for s, e, txt in spans:
                    psp = {"start": s, "end": e, "text": txt}
                    if any(any_overlap(psp, pp) for pp in parent_list):
                        continue
                    fp_new += 1
        prec = rec_fn / (rec_fn + fp_new) if (rec_fn + fp_new) else 0.0
        pattern_stats.append(
            {
                **{k: pat[k] for k in (
                    "pattern_id", "field", "tregex", "anchors", "family",
                    "parse_template", "positives", "negatives",
                )},
                "diagnostic_estimated_fn_recovered": rec_fn,
                "diagnostic_estimated_unique_records": len(rec_records),
                "diagnostic_hit_span_events": hit_spans,
                "diagnostic_new_spans_vs_parent": new_spans,
                "diagnostic_duplicate_parent_overlaps": dup_parent,
                "diagnostic_estimated_new_fp_on_no_gold_constraint_clauses": fp_new,
                "diagnostic_estimated_precision": prec,
                "meets_per_pattern_instantiation_floor": (
                    rec_fn >= 3
                    and len(rec_records) >= 3
                    and prec >= 0.60
                ),
                "estimation_method": "surface_regex_proxy_for_tregex_construction_not_independent_eval",
            }
        )

    # Select patterns meeting floor, max 6, prefer high FN recovery then precision
    selected = [p for p in pattern_stats if p["meets_per_pattern_instantiation_floor"]]
    selected.sort(
        key=lambda p: (
            -p["diagnostic_estimated_fn_recovered"],
            -p["diagnostic_estimated_precision"],
            p["pattern_id"],
        )
    )
    selected = selected[:6]

    # Union estimate (approximate, may double-count FN across patterns)
    union_fn_keys = set()
    union_fp = 0
    union_new_spans = 0
    for pat in selected:
        # recompute recoverable set membership
        for item in recoverable_candidates:
            en = item["en_clause"]
            key_full = hashlib.sha256(en.encode()).hexdigest()
            spans = approx_match_spans(en, pat["pattern_id"])
            gspan = {
                "start": item["gold_start"] - item["clause_start"],
                "end": item["gold_end"] - item["clause_start"],
            }
            for s, e, txt in spans:
                if any_overlap({"start": s, "end": e}, gspan):
                    union_fn_keys.add(item["gold_text_sha256"])
                    break
        union_fp += pat["diagnostic_estimated_new_fp_on_no_gold_constraint_clauses"]
        union_new_spans += pat["diagnostic_new_spans_vs_parent"]

    union_fn = len(union_fn_keys)
    union_prec = union_fn / (union_fn + union_fp) if (union_fn + union_fp) else 0.0
    instantiate = (
        1 <= len(selected) <= 6
        and union_fn >= 8
        and union_fp <= 10
        and union_prec >= 0.55
        and 8 <= union_new_spans <= 20
    )

    # strip en_clause from recoverable export
    recoverable_public = [
        {k: v for k, v in item.items() if k != "en_clause"}
        for item in recoverable_candidates
    ]

    report = {
        "schema_version": "b3a_constraint_tregex_diagnostic@1.0.0",
        "run_id": "s27_estg150_b0_b3a_constraint_tregex_diagnostic_v1",
        "claim_scope": "development_rule_construction_only_not_independent_validation",
        "parent_run": "s27_estg150_b0_enhanced_v10a",
        "hashes_verified": got,
        "parent_constraint_table8": {
            "gold": 302,
            "pred": 335,
            "tp": 126,
            "fp": 209,
            "fn": 176,
            "precision": 0.3761194029850746,
            "recall": 0.41721854304635764,
            "f1": 0.39560439560439564,
        },
        "fn_bucket_counts": dict(fn_buckets),
        "fp_bucket_counts": dict(fp_buckets),
        "fn_family": dict(family_fn),
        "fp_family": dict(family_fp),
        "fn_with_parent_anchor": fn_with_parent_anchor,
        "fn_without_parent_anchor": fn_without_parent_anchor,
        "recoverable_fn_items_count": len(recoverable_public),
        "candidate_patterns_evaluated": pattern_stats,
        "selected_patterns": selected,
        "union_instantiation": {
            "selected_count": len(selected),
            "estimated_fn_recovered_unique_gold_spans": union_fn,
            "estimated_new_fp": union_fp,
            "estimated_precision": union_prec,
            "estimated_new_unique_spans": union_new_spans,
            "thresholds": {
                "fn_recovered_min": 8,
                "new_fp_max": 10,
                "precision_min": 0.55,
                "new_spans_range": [8, 20],
                "patterns_range": [1, 6],
            },
            "instantiate": instantiate,
        },
        "decision": "instantiate" if instantiate else "not_instantiated",
        "decision_reason": (
            "union and per-pattern floors met"
            if instantiate
            else "union/per-pattern floors not met; no production candidate authorized"
        ),
        "safety": {
            "gold_read_only": True,
            "llm_api_called": False,
            "network_called": False,
            "no_sample_id_whitelist_persisted": True,
            "surface_proxy_not_live_tregex": True,
        },
    }

    out.mkdir(parents=True)
    # do not write full en clauses
    public = dict(report)
    _write(out / "manifest.json", public)
    print(
        json.dumps(
            {
                "output": str(out),
                "fn_buckets": dict(fn_buckets),
                "fp_buckets": dict(fp_buckets),
                "selected": [
                    {
                        "id": p["pattern_id"],
                        "fn": p["diagnostic_estimated_fn_recovered"],
                        "fp": p["diagnostic_estimated_new_fp_on_no_gold_constraint_clauses"],
                        "prec": p["diagnostic_estimated_precision"],
                        "records": p["diagnostic_estimated_unique_records"],
                        "floor": p["meets_per_pattern_instantiation_floor"],
                    }
                    for p in pattern_stats
                ],
                "union": report["union_instantiation"],
                "decision": report["decision"],
                "sha256": _sha(out / "manifest.json"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
