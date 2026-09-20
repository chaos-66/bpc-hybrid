# -*- coding: utf-8 -*-
"""Zero-API definition-clause semantics and prompt-coverage analysis.

This script reads the frozen Gold, the formal input, the persisted A/B/C/D
canonical predictions, and the E/S prompt modules.  It writes only new
analysis artefacts under ``outputs/reports``.  It never modifies Gold,
predictions, prompts, parser, canonicalizer, evaluator, or schemas.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "outputs" / "reports"
GOLD_PATH = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
INPUT_PATH = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
TARGETED_DIR = ROOT / "outputs" / "development" / "sep_c3_targeted_refinement_v1"
ARMS = ("A", "B", "C", "D")
SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")
PLURAL = {
    "actor": "actors",
    "action": "actions",
    "condition": "conditions",
    "constraint": "constraints",
    "exception": "exceptions",
}
PROMPT_PATHS = {
    "common": ROOT / "prompts" / "sun_compat" / "modular_v1" / "common_system.md",
    "E": ROOT / "prompts" / "sun_compat" / "modular_v1" / "examples_E.md",
    "S": ROOT / "prompts" / "sun_compat" / "modular_v1" / "semantic_rules_S.md",
    "v6": ROOT / "prompts" / "sun_compat" / "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md",
}

# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2))


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]],
              fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames,
                                extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def span_overlap(a: Mapping[str, Any], b: Mapping[str, Any]) -> int:
    return max(0, min(int(a["end"]), int(b["end"]))
               - max(int(a["start"]), int(b["start"])))


def span_contains(outer: Mapping[str, Any], inner: Mapping[str, Any]) -> bool:
    return (int(outer["start"]) <= int(inner["start"])
            and int(inner["end"]) <= int(outer["end"]))


def compact_span(span: Mapping[str, Any] | None) -> dict[str, Any]:
    if not span:
        return {}
    out = {
        "text": span.get("text", ""),
        "start": int(span.get("start", 0)),
        "end": int(span.get("end", 0)),
    }
    if "id" in span:
        out["id"] = span.get("id")
    if "normalized" in span:
        out["normalized"] = span.get("normalized")
    return out


def compact_spans(spans: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    return [compact_span(span) for span in (spans or [])]


def md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    out = ["| " + " | ".join(str(h) for h in headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join("" if cell is None else str(cell)
                                         for cell in row) + " |")
    return "\n".join(out)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Corpus construction
# ---------------------------------------------------------------------------

CANDIDATE_PATTERNS: dict[str, re.Pattern[str]] = {
    "explicit_definition_verb": re.compile(
        r"\b(?:means|refers to|has the meaning(?: of)?|is defined as)\b",
        re.IGNORECASE),
    "legal_fiction_marker": re.compile(
        r"\b(?:shall|is|are|be)\s+(?:deemed|treated as|considered as|"
        r"regarded as|constituted?|assumed|determined)\b",
        re.IGNORECASE),
    "classification_copula": re.compile(
        r"\b(?:is|are)\s+(?:a|an|the|not eligible|eligible|irrelevant|"
        r"the case|income|expense|expenditure|shares|stock corporations?)\b",
        re.IGNORECASE),
    "scope_application": re.compile(r"\b(?:shall\s+)?appl(?:y|ies)\b",
                                    re.IGNORECASE),
    "shall_include": re.compile(r"\bshall\s+include\b", re.IGNORECASE),
}

DEFINITION_CONSTRUCTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "explicit_means": re.compile(r"\bmeans\b", re.IGNORECASE),
    "within_the_meaning": re.compile(r"\bwithin the meaning\b", re.IGNORECASE),
    "shall_include": re.compile(r"\bshall\s+include\b", re.IGNORECASE),
    "shall_be_deemed": re.compile(r"\bshall\s+be\s+deemed\b", re.IGNORECASE),
    "be_deemed": re.compile(r"\b(?:is|are|be)\s+deemed\b", re.IGNORECASE),
    "shall_be_treated": re.compile(r"\bshall\s+(?:also\s+)?be\s+treated\b",
                                   re.IGNORECASE),
    "shall_constitute": re.compile(r"\bshall\s+constitute\b", re.IGNORECASE),
    "shall_be_assumed": re.compile(r"\bshall\s+be\s+assumed\b", re.IGNORECASE),
    "shall_apply": re.compile(r"\bshall\s+apply\b", re.IGNORECASE),
    "applies_apply": re.compile(r"\bappl(?:y|ies)\b", re.IGNORECASE),
    "does_not_apply": re.compile(r"\bdoes not apply\b", re.IGNORECASE),
    "are_not_eligible": re.compile(r"\bare not eligible\b", re.IGNORECASE),
    "copula_is_are": re.compile(r"\b(?:is|are)\b", re.IGNORECASE),
}

# Manual annotation-semantics review of the 46 Gold definition action spans.
# Primary categories are mutually exclusive; secondary tags may overlap.
ACTION_TAXONOMY: dict[tuple[str, str, int], dict[str, Any]] = {
    ("estg_000020", "c1", 0): {"primary": "action_span_includes_subordinate_phrase",
                                "secondary": ["copular_action", "contains_condition"],
                                "manual_review": True},
    ("estg_000031", "c1", 0): {"primary": "copular_action", "secondary": []},
    ("estg_000037", "c1", 0): {"primary": "definitional_verb", "secondary": []},
    ("estg_000040", "c1", 0): {"primary": "definitional_verb", "secondary": []},
    ("estg_000046", "c2", 0): {"primary": "relational_predicate", "secondary": []},
    ("estg_000057", "c1", 0): {"primary": "definitional_verb", "secondary": []},
    ("estg_000071", "c1", 0): {"primary": "relational_predicate", "secondary": ["scope_application"]},
    ("estg_000080", "c4", 0): {"primary": "deeming_legal_fiction", "secondary": ["classification_verb"]},
    ("estg_000082", "c1", 0): {"primary": "classification_verb", "secondary": [], "manual_review": True},
    ("estg_000083", "c1", 0): {"primary": "relational_predicate", "secondary": ["scope_application", "negated"]},
    ("estg_000083", "c2", 0): {"primary": "action_span_includes_subordinate_phrase",
                                "secondary": ["classification_verb", "includes_subject"],
                                "manual_review": True},
    ("estg_000087", "c1", 0): {"primary": "deeming_legal_fiction", "secondary": []},
    ("estg_000112", "c1", 0): {"primary": "deeming_legal_fiction", "secondary": [],
                                "manual_review": True},
    ("estg_000136", "c1", 0): {"primary": "deeming_legal_fiction", "secondary": [],
                                "manual_review": True},
    ("estg_000164", "c1", 0): {"primary": "relational_predicate", "secondary": ["scope_application"]},
    ("estg_000164", "c2", 0): {"primary": "classification_verb", "secondary": [], "manual_review": True},
    ("estg_000195", "c1", 0): {"primary": "copular_action", "secondary": ["negated"]},
    ("estg_000208", "c3", 0): {"primary": "classification_verb", "secondary": ["copular_action"]},
    ("estg_000208", "c3", 1): {"primary": "other_event_predicate", "secondary": []},
    ("estg_000208", "c4", 0): {"primary": "other_event_predicate", "secondary": []},
    ("estg_000208", "c4", 1): {"primary": "other_event_predicate", "secondary": []},
    ("estg_000208", "c4", 2): {"primary": "other_event_predicate", "secondary": []},
    ("estg_000209", "c1", 0): {"primary": "classification_verb", "secondary": ["negated"]},
    ("estg_000209", "c2", 0): {"primary": "relational_predicate", "secondary": ["scope_application"]},
    ("estg_000210", "c1", 0): {"primary": "classification_verb", "secondary": ["negated"]},
    ("estg_000210", "c2", 0): {"primary": "classification_verb", "secondary": ["copular_action"]},
    ("estg_000218", "c1", 0): {"primary": "relational_predicate", "secondary": ["scope_application", "negated"]},
    ("estg_000232", "c2", 0): {"primary": "relational_predicate", "secondary": [], "manual_review": True},
    ("estg_000273", "c1", 0): {"primary": "copular_action", "secondary": []},
    ("estg_000283", "c1", 0): {"primary": "relational_predicate", "secondary": []},
    ("estg_000283", "c1", 1): {"primary": "other_event_predicate", "secondary": ["verb_only"]},
    ("estg_000283", "c1", 2): {"primary": "other_event_predicate", "secondary": ["verb_only"]},
    ("estg_000293", "c1", 0): {"primary": "classification_verb", "secondary": []},
    ("estg_000302", "c1", 0): {"primary": "classification_verb", "secondary": []},
    ("estg_000414", "c1", 0): {"primary": "deeming_legal_fiction", "secondary": []},
    ("estg_000417", "c1", 0): {"primary": "copular_action", "secondary": []},
    ("estg_000417", "c1", 1): {"primary": "copular_action", "secondary": ["relational_predicate"]},
    ("estg_000417", "c1", 2): {"primary": "copular_action", "secondary": ["relational_predicate"]},
    ("estg_000509", "c2", 0): {"primary": "deeming_legal_fiction", "secondary": [], "manual_review": True},
    ("estg_000522", "c1", 0): {"primary": "classification_verb", "secondary": ["deeming_legal_fiction"]},
    ("estg_000572", "c1", 0): {"primary": "deeming_legal_fiction", "secondary": []},
    ("estg_000664", "c1", 0): {"primary": "relational_predicate", "secondary": ["scope_application"]},
    ("estg_000773", "c1", 0): {"primary": "deeming_legal_fiction", "secondary": []},
    ("estg_000776", "c1", 0): {"primary": "deeming_legal_fiction", "secondary": []},
    ("estg_000800", "c1", 0): {"primary": "relational_predicate", "secondary": ["scope_application", "negated"]},
    ("estg_000854", "c1", 0): {"primary": "deeming_legal_fiction", "secondary": []},
}

MANUAL_REVIEW_NOTES = {
    ("estg_000020", "c1"): "Gold action span contains two separately annotated condition spans.",
    ("estg_000082", "c1"): "Negative part-whole predicate is classified as classification with low confidence.",
    ("estg_000083", "c2"): "Only definition action that includes a coordinated subject plus predicate.",
    ("estg_000112", "c1"): "Clause is a fragment; clause boundary and action are both uncertain.",
    ("estg_000136", "c1"): "Passive determination may be deeming or ordinary relational predicate.",
    ("estg_000164", "c2"): "Copular/passive classification boundary is uncertain.",
    ("estg_000232", "c2"): "Temporal relational predicate ('runs from') needs boundary review.",
    ("estg_000509", "c2"): "Near-identical to estg_000505 c2, which Gold labels obligation.",
    ("estg_000505", "c2"): "Near-identical to Gold definition estg_000509 c2, but Gold labels obligation.",
}

CANDIDATE_NOTES = {
    ("estg_000505", "c2"): "Same lexical pattern as Gold definition estg_000509 c2; apparent annotation inconsistency.",
    ("estg_000056", "c1"): "Same scope-application trigger as definition clauses; Gold labels obligation.",
    ("estg_000128", "c2"): "Same scope-application trigger as definition clauses; Gold labels obligation.",
    ("estg_000208", "c2"): "Same scope-application trigger as definition clauses; Gold labels obligation.",
    ("estg_000306", "c1"): "Same scope-application trigger as definition clauses; Gold labels obligation.",
    ("estg_000145", "c1"): "'may apply' means request/claim, not definition.",
    ("estg_000079", "c1"): "'by means of' is not a definitional verb.",
    ("estg_000075", "c1"): "Copular surface in a measurement/valuation provision; review only.",
    ("estg_000109", "c1"): "Copular surface in an eligibility provision; review only.",
    ("estg_000080", "c3"): "'considered as' inside a participial antecedent; review only.",
    ("estg_000118", "c1"): "'determined' inside a condition; review only.",
    ("estg_000222", "c2"): "'determined' inside a condition; review only.",
    ("estg_000399", "c1"): "'determined' inside an embedded clause; review only.",
    ("estg_000812", "c1"): "'shall be determined' is an obligation in Gold but lexically parallel to a definition case.",
}


def construction_features(text: str,
                           patterns: Mapping[str, re.Pattern[str]]) -> list[str]:
    return [name for name, pattern in patterns.items()
            if pattern.search(text or "")]


def load_gold() -> list[dict[str, Any]]:
    return list(read_json(GOLD_PATH)["records"])


def load_arms() -> dict[str, dict[str, dict[str, Any]]]:
    arms: dict[str, dict[str, dict[str, Any]]] = {}
    for arm in ARMS:
        path = TARGETED_DIR / arm / "repeat-01" / "canonical_predictions.jsonl"
        arms[arm] = {row["sample_id"]: row for row in read_jsonl(path)}
    return arms


def load_input_texts() -> dict[str, str]:
    records = read_json(INPUT_PATH)["records"]
    return {str(record["sample_id"]): str(record["approved_text_en"])
            for record in records}


def best_prediction_clause(arm_predictions: Mapping[str, Any],
                           sample_id: str,
                           gold_clause_span: Mapping[str, Any]) -> tuple[dict[str, Any] | None, int, bool]:
    clauses = (arm_predictions.get(sample_id, {}).get("record") or {}).get("clauses") or []
    best = None
    best_overlap = 0
    for clause in clauses:
        overlap = span_overlap(gold_clause_span, clause.get("clause_span") or {})
        if overlap > best_overlap:
            best_overlap = overlap
            best = clause
    gold_len = max(1, int(gold_clause_span["end"]) - int(gold_clause_span["start"]))
    aligned = bool(best) and (best_overlap / gold_len) >= 0.5
    return best, best_overlap, aligned


def compact_prediction_clause(clause: Mapping[str, Any] | None,
                              overlap: int,
                              aligned: bool) -> dict[str, Any]:
    if not clause:
        return {
            "available": False,
            "alignment_quality": "no_overlapping_clause",
            "overlap_chars": 0,
            "modality_label": None,
            "modality_evidence": [],
            "actions": [],
            "actors": [],
            "conditions": [],
            "constraints": [],
            "exceptions": [],
            "clause_span": {},
        }
    modality = clause.get("modality") or {}
    return {
        "available": True,
        "alignment_quality": "aligned" if aligned else "low_overlap",
        "overlap_chars": overlap,
        "clause_id": clause.get("clause_id"),
        "clause_span": compact_span(clause.get("clause_span") or {}),
        "modality_label": modality.get("label"),
        "modality_evidence": compact_spans(modality.get("evidence") or []),
        "actions": compact_spans(clause.get("actions") or []),
        "actors": compact_spans(clause.get("actors") or []),
        "conditions": compact_spans(clause.get("conditions") or []),
        "constraints": compact_spans(clause.get("constraints") or []),
        "exceptions": compact_spans(clause.get("exceptions") or []),
    }


def prediction_modality(arm_predictions: Mapping[str, Any],
                        sample_id: str,
                        gold_clause_span: Mapping[str, Any]) -> str | None:
    clause, _, _ = best_prediction_clause(arm_predictions, sample_id, gold_clause_span)
    if not clause:
        return None
    return (clause.get("modality") or {}).get("label")


def action_outcome(gold_action: Mapping[str, Any],
                   predicted_actions: Sequence[Mapping[str, Any]]) -> str:
    if not predicted_actions:
        return "empty"
    gold_text = gold_action.get("text", "")
    if any(p.get("text", "") == gold_text for p in predicted_actions):
        extra = [
            p for p in predicted_actions
            if p.get("text", "") != gold_text
            and span_overlap(p, gold_action) == 0
        ]
        return "exact_match" if not extra else "exact_plus_extra"
    overlapping = [p for p in predicted_actions if span_overlap(p, gold_action) > 0]
    if not overlapping:
        return "missing"
    if any(span_contains(p, gold_action) and int(p["end"]) - int(p["start"])
           > int(gold_action["end"]) - int(gold_action["start"])
           for p in overlapping):
        return "broader"
    if any(span_contains(gold_action, p) and int(p["end"]) - int(p["start"])
           < int(gold_action["end"]) - int(gold_action["start"])
           for p in overlapping):
        return "narrower"
    return "overlap_mismatch"


def build_cases(gold_records: Sequence[Mapping[str, Any]],
                arms: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    gold_cases: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for record in gold_records:
        sample_id = str(record["sample_id"])
        source_text = str(record.get("approved_text_en", ""))
        for clause_index, clause in enumerate(record.get("clauses") or []):
            clause_span = compact_span(clause.get("clause_span") or {})
            clause_text = clause_span.get("text", "")
            gold_modality = clause.get("modality")
            predictions: dict[str, Any] = {}
            for arm in ARMS:
                pred_clause, overlap, aligned = best_prediction_clause(
                    arms[arm], sample_id, clause_span)
                predictions[arm] = compact_prediction_clause(
                    pred_clause, overlap, aligned)
            base: dict[str, Any] = {
                "sample_id": sample_id,
                "clause_id": clause.get("clause_id"),
                "clause_index": clause_index,
                "source_text": source_text,
                "clause_span": clause_span,
                "clause_text": clause_text,
                "gold": {
                    "modality": gold_modality,
                    "actors": compact_spans(clause.get("actors") or []),
                    "actions": compact_spans(clause.get("actions") or []),
                    "conditions": compact_spans(clause.get("conditions") or []),
                    "constraints": compact_spans(clause.get("constraints") or []),
                    "exceptions": compact_spans(clause.get("exceptions") or []),
                },
                "predictions": predictions,
            }
            e_matches = ["E4"]
            s_rules = [2, 4, 8, 11]
            if clause.get("conditions") and clause.get("constraints"):
                e_matches.append("E5")
            if clause.get("exceptions"):
                e_matches.append("E3")
            if any(str(actor.get("text", "")).strip().lower() in
                   {"it", "they", "this", "these", "such"}
                   for actor in (clause.get("actors") or [])):
                e_matches.append("E1")
            if (not (clause.get("actors") or [])
                    and len(clause.get("actions") or []) >= 2
                    and (clause.get("constraints") or [])):
                e_matches.append("E2")
            base["relevant_e_example_match"] = e_matches
            base["relevant_s_rule_coverage"] = s_rules
            if gold_modality == "definition":
                base["case_type"] = "gold_definition_clause"
                base["construction_features"] = construction_features(
                    clause_text, DEFINITION_CONSTRUCTION_PATTERNS)
                base["all_four_modality_mismatch"] = all(
                    predictions[arm].get("modality_label") != "definition"
                    for arm in ARMS)
                base["manual_review_required"] = (
                    _case_manual_review_required(sample_id, base["clause_id"], clause_text))
                base["notes"] = MANUAL_REVIEW_NOTES.get(
                    (sample_id, base["clause_id"]), "")
                gold_cases.append(base)
            else:
                reasons = construction_features(clause_text, CANDIDATE_PATTERNS)
                if reasons:
                    base["case_type"] = "definition_like_candidate_nondefinition"
                    base["candidate_reasons"] = reasons
                    base["candidate_disposition"] = (
                        "apparent_parallel_modality_mismatch"
                        if sample_id == "estg_000505"
                        else "manual_review_candidate")
                    base["manual_review_required"] = True
                    base["notes"] = CANDIDATE_NOTES.get(
                        (sample_id, base["clause_id"]),
                        "Broad lexical candidate; not asserted to be a missed definition label.")
                    candidates.append(base)
    return gold_cases, candidates


def _case_manual_review_required(sample_id: str, clause_id: str,
                                 clause_text: str) -> bool:
    if (sample_id, clause_id) in MANUAL_REVIEW_NOTES:
        return True
    return bool(re.search(r"\bshall\s+apply\b", clause_text, re.IGNORECASE))


def summarize_gold(gold_records: Sequence[Mapping[str, Any]],
                   arms: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    defs = [(record, clause)
            for record in gold_records
            for clause in (record.get("clauses") or [])
            if clause.get("modality") == "definition"]
    first_def = [
        record for record in gold_records
        if (record.get("clauses") or [])
        and record["clauses"][0].get("modality") == "definition"
    ]
    all_action_count = sum(len(clause.get("actions") or []) for _, clause in defs)
    empty_action = sum(1 for _, clause in defs if not (clause.get("actions") or []))
    actor_nonempty = sum(1 for _, clause in defs if clause.get("actors") or [])
    condition_count = sum(1 for _, clause in defs if clause.get("conditions") or [])
    constraint_count = sum(1 for _, clause in defs if clause.get("constraints") or [])
    exception_count = sum(1 for _, clause in defs if clause.get("exceptions") or [])
    all_three_empty = sum(
        1 for _, clause in defs
        if not (clause.get("conditions") or [])
        and not (clause.get("constraints") or [])
        and not (clause.get("exceptions") or []))

    clause_all_wrong = []
    first_sample_all_wrong = []
    per_arm_definition = Counter()
    per_arm_confusion = {arm: Counter() for arm in ARMS}
    for record in gold_records:
        for clause in record.get("clauses") or []:
            if clause.get("modality") != "definition":
                continue
            span = compact_span(clause.get("clause_span") or {})
            labels = [prediction_modality(arms[arm], record["sample_id"], span)
                      for arm in ARMS]
            for arm, label in zip(ARMS, labels):
                per_arm_confusion[arm][label] += 1
                if label == "definition":
                    per_arm_definition[arm] += 1
            if all(label != "definition" for label in labels):
                clause_all_wrong.append({
                    "sample_id": record["sample_id"],
                    "clause_id": clause.get("clause_id"),
                    "labels": labels,
                    "text": span.get("text", ""),
                })
    for record in first_def:
        clause = record["clauses"][0]
        span = compact_span(clause.get("clause_span") or {})
        labels = [prediction_modality(arms[arm], record["sample_id"], span)
                  for arm in ARMS]
        if all(label != "definition" for label in labels):
            first_sample_all_wrong.append({
                "sample_id": record["sample_id"],
                "labels": labels,
                "has_shall": bool(re.search(r"\bshall\b", span.get("text", ""), re.I)),
                "text": span.get("text", ""),
            })

    shall_defs = [(record, clause)
                  for record, clause in defs
                  if re.search(r"\bshall\b", clause["clause_span"]["text"], re.I)]
    shall_all_wrong = sum(
        1 for record, clause in shall_defs
        if all(prediction_modality(arms[arm], record["sample_id"],
                                   clause["clause_span"]) != "definition"
               for arm in ARMS))
    first_def_all_wrong_with_shall = sum(
        1 for row in first_sample_all_wrong if row["has_shall"])

    same_trigger_conflicts = []
    for trigger, pattern in [
        ("applies/apply", re.compile(r"\bappl(?:y|ies)\b", re.I)),
        ("shall apply", re.compile(r"\bshall\s+apply\b", re.I)),
        ("shall be determined", re.compile(r"\bshall\s+be\s+determined\b", re.I)),
        ("shall be assumed", re.compile(r"\bshall\s+be\s+assumed\b", re.I)),
    ]:
        hits = []
        for record in gold_records:
            for clause in record.get("clauses") or []:
                if pattern.search(clause["clause_span"]["text"]):
                    hits.append({
                        "sample_id": record["sample_id"],
                        "clause_id": clause.get("clause_id"),
                        "modality": clause.get("modality"),
                        "text": clause["clause_span"]["text"],
                    })
        same_trigger_conflicts.append({"trigger": trigger, "hits": hits})

    return {
        "definition_clause_count": len(defs),
        "definition_sample_count_any": len({record["sample_id"] for record, _ in defs}),
        "first_definition_sample_count": len(first_def),
        "definition_action_span_count": all_action_count,
        "definition_clauses_with_empty_action": empty_action,
        "definition_clauses_with_actor": actor_nonempty,
        "definition_clauses_with_condition": condition_count,
        "definition_clauses_with_constraint": constraint_count,
        "definition_clauses_with_exception": exception_count,
        "definition_clauses_with_all_three_empty": all_three_empty,
        "clause_all_four_modality_wrong": len(clause_all_wrong),
        "first_definition_sample_all_four_modality_wrong": len(first_sample_all_wrong),
        "per_arm_definition_label_count": dict(per_arm_definition),
        "per_arm_modality_confusion": {
            arm: dict(counter) for arm, counter in per_arm_confusion.items()},
        "clause_all_wrong_rows": clause_all_wrong,
        "first_sample_all_wrong_rows": first_sample_all_wrong,
        "shall_definition_clause_count": len(shall_defs),
        "shall_definition_clauses_all_four_wrong": shall_all_wrong,
        "first_definition_all_wrong_with_shall": first_def_all_wrong_with_shall,
        "same_trigger_conflicts": same_trigger_conflicts,
    }


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------

def modality_matrix_rows(cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        preds = case["predictions"]
        labels = [preds[arm].get("modality_label") for arm in ARMS]
        all_wrong = all(label != "definition" for label in labels)
        if all_wrong and all(label == "obligation" for label in labels):
            error_type = "definition_to_obligation_all_arms"
        elif all_wrong and all(label == "prohibition" for label in labels):
            error_type = "definition_to_prohibition_all_arms"
        elif all_wrong:
            error_type = "definition_to_other_or_mixed_nondefinition"
        elif any(label == "definition" for label in labels):
            error_type = "partially_correct"
        else:
            error_type = "other"
        rows.append({
            "sample_id": case["sample_id"],
            "clause_id": case["clause_id"],
            "clause_index": case["clause_index"],
            "gold_modality": "definition",
            "construction_features": ";".join(case["construction_features"]),
            "clause_text": case["clause_text"],
            "pred_modality_A": labels[0],
            "pred_modality_B": labels[1],
            "pred_modality_C": labels[2],
            "pred_modality_D": labels[3],
            "all_four_wrong": all_wrong,
            "error_type": error_type,
            "gold_action_count": len(case["gold"]["actions"]),
            "pred_action_count_A": len(preds["A"].get("actions") or []),
            "pred_action_count_B": len(preds["B"].get("actions") or []),
            "pred_action_count_C": len(preds["C"].get("actions") or []),
            "pred_action_count_D": len(preds["D"].get("actions") or []),
            "manual_review_required": case["manual_review_required"],
            "notes": case.get("notes", ""),
        })
    return rows


def action_matrix_rows(cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """One row per Gold definition action; prediction columns are per arm."""
    rows = []
    for case in cases:
        for index, action in enumerate(case["gold"]["actions"]):
            key = (case["sample_id"], case["clause_id"], index)
            taxonomy = ACTION_TAXONOMY.get(key, {
                "primary": "uncertain", "secondary": ["manual_review"]})
            boundary_features = []
            for field in ("conditions", "constraints", "exceptions"):
                if any(span_overlap(action, other)
                       for other in case["gold"][field]):
                    boundary_features.append(f"action_overlaps_{field}")
            if int(action["end"]) - int(action["start"]) > 30:
                boundary_features.append("action_longer_than_30_chars")
            row: dict[str, Any] = {
                "sample_id": case["sample_id"],
                "clause_id": case["clause_id"],
                "action_index": index,
                "gold_action_text": action.get("text", ""),
                "action_length": int(action["end"]) - int(action["start"]),
                "taxonomy_primary": taxonomy["primary"],
                "taxonomy_secondary": ";".join(taxonomy.get("secondary") or []),
                "boundary_features": ";".join(boundary_features),
                "manual_review_required": bool(
                    taxonomy.get("manual_review")
                    or boundary_features
                    or case.get("manual_review_required")),
            }
            for arm in ARMS:
                pred = case["predictions"][arm]
                row[f"pred_modality_{arm}"] = pred.get("modality_label")
                row[f"pred_action_text_{arm}"] = " || ".join(
                    item.get("text", "") for item in (pred.get("actions") or []))
                row[f"action_outcome_{arm}"] = action_outcome(
                    action, pred.get("actions") or [])
            rows.append(row)
    return rows
def e4_audit(cases: Sequence[Mapping[str, Any]],
             summary: Mapping[str, Any]) -> str:
    e_text = read_text_if_exists(PROMPT_PATHS["E"])
    e4_lines = []
    capture = False
    for line in e_text.splitlines():
        if line.startswith("Example E4"):
            capture = True
        elif capture and line.startswith("Example E5"):
            break
        if capture:
            e4_lines.append(line)
    e4_block = "\n".join(e4_lines).strip()
    action_conflict = summary["definition_clause_count"]
    action_compatible = 0
    actor_compatible = summary["definition_clause_count"] - summary["definition_clauses_with_actor"]
    all_fields_empty_compatible = summary["definition_clauses_with_all_three_empty"]
    means_def_count = sum(
        1 for case in cases if "explicit_means" in case["construction_features"])
    lines = [
        "# SEP-C3 E4 Coverage Audit",
        "",
        "- Task: Definition-Clause Semantics & Prompt Coverage Study",
        "- Scope: `prompts/sun_compat/modular_v1/examples_E.md`, Example E4 only.",
        "- API calls: **0**.",
        "",
        "## 1. Exact E4 text",
        "",
        "```text",
        e4_block,
        "```",
        "",
        "## 2. What E4 wants to teach",
        "",
        "E4 teaches (a) a definition clause can be labeled `definition`, (b) the trigger `means` is sufficient modality evidence, and (c) a definition clause has empty actors and actions. It also demonstrates splitting a definition clause from a following obligation clause.",
        "",
        "## 3. Audit against Gold definition clauses",
        "",
        md_table(
            ["Question", "Result", "Evidence"],
            [
                ["Gold definition clauses", summary["definition_clause_count"], "clauses with Gold modality == definition"],
                ["Gold definition samples (any clause)", summary["definition_sample_count_any"], "distinct sample_ids"],
                ["First-clause definition samples (record-level evaluator view)", summary["first_definition_sample_count"], "first Gold clause is definition"],
                ["Gold definition clauses with non-empty action", summary["definition_clause_count"] - summary["definition_clauses_with_empty_action"], f"{summary['definition_action_span_count']} action spans"],
                ["E4 explicit action-empty pattern compatible with Gold", action_compatible, "E4 says actions empty; Gold has 0/39 empty actions"],
                ["E4 actor-empty pattern compatible with Gold", actor_compatible, f"Gold definition clauses with actor: {summary['definition_clauses_with_actor']}"],
                ["E4 all-condition/constraint/exception-empty pattern compatible with Gold", all_fields_empty_compatible, "Gold clauses with no condition, constraint, and exception"],
                ["Gold clauses matching E4's explicit `means` trigger", means_def_count, "exact token `means`"],
                ["Gold definition clauses with `shall`", summary["shall_definition_clause_count"], "legal-fiction/definition uses of shall"],
                ["Gold shall-definition clauses all four arms non-definition", summary["shall_definition_clauses_all_four_wrong"], "A/B/C/D predictions"],
            ]),
        "",
        "## 4. Coverage judgement",
        "",
        "- **Modality**: E4's label `definition` is compatible with Gold's label inventory, but E4 covers only an explicit `means` definition. It does not cover the dominant `shall`-based legal-fiction patterns (15 definition clauses), classification/status predicates, or scope-application definitions.",
        "- **Action**: E4 explicitly says `actors and actions empty`. This conflicts with Gold: 39/39 definition clauses have at least one action span; E4-compatible action-empty count is 0.",
        "- **Actor**: E4's empty actor pattern is broadly compatible (37/39 Gold definition clauses have no actor), but it is not universal (2 clauses have actors).",
        "- **Condition / constraint / exception**: E4 shows all three empty. No Gold definition clause has all three empty; 28/39 have conditions and 28/39 have constraints.",
        "- **Joint pattern**: E4's full joint pattern (definition + no actor/action/condition/constraint/exception) occurs in 0/39 Gold definition clauses.",
        "",
        "## 5. E4 status",
        "",
        "**`CONFLICTS_WITH_GOLD`**",
        "",
        "The conflict is concentrated in action emptiness. The status is not caused by the modality label itself.",
        "",
        "## 6. E4 + S interaction risk",
        "",
        "S rule 11 says a definition clause *may* have no actions. That is permissive, not a direct contradiction of Gold, but combined with E4's explicit empty action it removes any positive signal that definition clauses normally have action spans. The joint guidance is therefore a high-risk explanation for empty definition actions, even though this A/B/C/D run includes E4 and not S.",
    ]
    return "\n".join(lines) + "\n"


def read_text_if_exists(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def e_examples_coverage(gold_records: Sequence[Mapping[str, Any]]) -> str:
    counts = Counter()
    details = {}
    all_clauses = [(record, clause)
                   for record in gold_records
                   for clause in (record.get("clauses") or [])]
    counts["permission_clauses"] = sum(1 for _, c in all_clauses if c.get("modality") == "permission")
    counts["permission_with_condition"] = sum(
        1 for _, c in all_clauses
        if c.get("modality") == "permission" and c.get("conditions"))
    counts["permission_pronoun_actor"] = 0
    for _, c in all_clauses:
        if c.get("modality") != "permission":
            continue
        for actor in c.get("actors") or []:
            if actor.get("text", "").strip().lower() in {"it", "they", "this", "these", "such"}:
                counts["permission_pronoun_actor"] += 1
    counts["e2_exact"] = sum(
        1 for _, c in all_clauses
        if c.get("modality") == "obligation"
        and not (c.get("actors") or [])
        and len(c.get("actions") or []) >= 2
        and (c.get("constraints") or []))
    counts["prohibition_with_exception"] = sum(
        1 for _, c in all_clauses
        if c.get("modality") == "prohibition" and c.get("exceptions"))
    counts["definition_clauses"] = sum(
        1 for _, c in all_clauses if c.get("modality") == "definition")
    counts["definition_action_nonempty"] = sum(
        1 for _, c in all_clauses
        if c.get("modality") == "definition" and c.get("actions"))
    counts["definition_all_semantic_empty"] = sum(
        1 for _, c in all_clauses
        if c.get("modality") == "definition"
        and not (c.get("actions") or [])
        and not (c.get("conditions") or [])
        and not (c.get("constraints") or [])
        and not (c.get("exceptions") or []))
    counts["nested_condition_constraint_pairs"] = 0
    counts["nested_condition_constraint_clauses"] = set()
    counts["nested_obligation_pairs"] = 0
    for record, clause in all_clauses:
        for condition in clause.get("conditions") or []:
            for constraint in clause.get("constraints") or []:
                if (int(condition["start"]) <= int(constraint["start"])
                        and int(constraint["end"]) <= int(condition["end"])):
                    counts["nested_condition_constraint_pairs"] += 1
                    counts["nested_condition_constraint_clauses"].add(
                        (record["sample_id"], clause.get("clause_id")))
                    if clause.get("modality") == "obligation":
                        counts["nested_obligation_pairs"] += 1
    lines = [
        "# SEP-C3 E Examples Coverage Matrix",
        "",
        "- Scope: `examples_E.md`, Examples E1-E5.",
        "- API calls: **0**.",
        "- Gold coverage numbers below are strict structural counts, not fuzzy semantic recalls.",
        "",
        md_table(
            ["Example", "Main concept taught", "Gold coverage", "Potential overgeneralization", "Potential conflict"],
            [
                ["E1", "permission; unresolved pronoun actor; condition",
                 f"permission clauses: {counts['permission_clauses']}; permission with condition: {counts['permission_with_condition']}; pronoun actor: {counts['permission_pronoun_actor']}",
                 "May suggest pronoun actors are common; only 1 Gold permission clause has a bare pronoun actor under the strict count.",
                 "No direct modality conflict; actor scope was not re-studied this round."],
                ["E2", "passive no-actor obligation; coordinated actions; constraints",
                 f"strict exact pattern (obligation, no actor, >=2 actions, >=1 constraint): {counts['e2_exact']}",
                 "A very rare exact Gold pattern; concept-level passive no-actor rule is supported by S rule 10.",
                 "E2 does not show by-phrase actors; no direct definition-clause conflict."],
                ["E3", "prohibition with exception",
                 f"prohibition clauses with exception: {counts['prohibition_with_exception']}",
                 "Exceptions are rare in Gold; E3 may make exception extraction look more typical than it is.",
                 "No direct conflict; aligns with S rule 7."],
                ["E4", "definition clause with empty actor/action, followed by obligation",
                 f"definition clauses: {counts['definition_clauses']}; with action: {counts['definition_action_nonempty']}; fully semantic-empty: {counts['definition_all_semantic_empty']}",
                 "Explicitly overgeneralizes action emptiness to all definition clauses.",
                 "Direct conflict with Gold action presence; also omits condition/constraint coverage."],
                ["E5", "condition containing nested constraint",
                 f"actual condition-contains-constraint pairs: {counts['nested_condition_constraint_pairs']}; clauses: {len(counts['nested_condition_constraint_clauses'])}; obligation pairs: {counts['nested_obligation_pairs']}",
                 "Actual nesting is less frequent than merged-hull diagnostics; E5 is still an actual Gold pattern.",
                 "No direct conflict; aligns with S rule 8."],
            ]),
        "",
        "## Overall E assessment",
        "",
        "- E is not wholly wrong: E1/E3/E5 are structurally aligned with Gold, and E2 follows the explicit passive rule.",
        "- E4 is the local example that conflicts with Gold on definition actions and under-covers definition conditions/constraints.",
        "- Therefore the evidence favours **E is broadly useful but E4 is a local, high-impact mismatch**, rather than an E-wide definition problem.",
    ]
    return "\n".join(lines) + "\n"


def s_audit(summary: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C3 S Modality / Action Audit",
        "",
        "`S_MODALITY_ACTION_AUDIT`",
        "",
        "- Scope: `semantic_rules_S.md`, rules 2, 4, 8, and 11 (modality/action-relevant rules).",
        "- S is not restored or modified.",
        "- API calls: **0**.",
        "",
        md_table(
            ["S rule", "Current wording / behavior", "Gold compatibility", "Conflict / risk", "Evidence"],
            [
                ["S2", "label each clause obligation, prohibition, permission, or definition; smallest sufficient surface trigger",
                 "Label inventory matches Gold. Partial semantic coverage only.",
                 "**MISSING_GUIDANCE**: no semantics for `definition`; no warning that `shall` can occur in definition/legal-fiction clauses.",
                 f"{summary['shall_definition_clause_count']}/{summary['shall_definition_clause_count']} definition clauses with `shall` are non-definition in all four arms."],
                ["S4", "smallest verb-centred phrase that identifies the act, including necessary object, complement, or particle",
                 "Core verb-centred principle matches 46/46 Gold definition actions.",
                 "**AMBIGUOUS_GUIDANCE** / boundary risk: Gold sometimes keeps only the predicate and places complements in conditions/constraints (e.g. `leaves`, `works`, `shall include`, `be determined`).",
                 "Examples: estg_000283, estg_000037, estg_000136, estg_000112."],
                ["S8", "never fold condition/constraint/exception content into action; action ends where such a phrase begins",
                 "Compatible with 44/46 Gold definition action spans (no measured overlap with conditions/constraints/exceptions).",
                 "**CONFLICTING_GUIDANCE** for at least one Gold clause: estg_000020 action contains two separately annotated condition spans.",
                 "estg_000020 c1: action span [37,177) contains condition spans; overlap count 2."],
                ["S11", "a definition clause may have no actions",
                 "Logically permissive, but unsupported as a positive definition pattern.",
                 "**POTENTIALLY_MISLEADING / CONFLICT-ADJACENT**: Gold has 39/39 definition clauses with actions; E4 explicitly takes the empty-action branch. No definition clause has an empty action.",
                 "Gold definition action-empty count = 0."],
            ]),
        "",
        "## S modality/action conclusions",
        "",
        "- S2 is missing the semantic definition needed for the definition class. It cannot distinguish `shall` as a deontic modal from `shall` as a legal-fiction/definition trigger.",
        "- S11 is technically permissive rather than contradictory, but it is indistinguishable from a positive empty-action instruction when paired with E4.",
        "- S4 and S8 are mostly compatible with Gold's predicate-centred boundaries; S8 has one direct Gold counterexample (estg_000020).",
        "- S does not repeat R_A/R_C, but it repeats E's action-empty concept in rule 11 and therefore compounds the E4 risk if S were used.",
    ]
    return "\n".join(lines) + "\n"


def gold_consistency_audit(cases: Sequence[Mapping[str, Any]],
                           summary: Mapping[str, Any]) -> str:
    same_trigger_rows = []
    for item in summary["same_trigger_conflicts"]:
        hits = item["hits"]
        modalities = Counter(hit["modality"] for hit in hits)
        same_trigger_rows.append([
            item["trigger"],
            len(hits),
            "; ".join(f"{key}={value}" for key, value in sorted(modalities.items())),
            ", ".join(f"{hit['sample_id']}:{hit['clause_id']}" for hit in hits),
        ])
    suspicious = [
        ["estg_000505 c2 vs estg_000509 c2", "obligation vs definition", "near-identical surface text: `a monthly wage payment period shall be assumed`"],
        ["applies / shall apply family", "definition and obligation/permission", "7 definition clauses vs 5 non-definition clauses with the same apply/application lexeme"],
        ["estg_000020 c1", "definition", "the only definition action span that contains separately annotated condition spans"],
        ["estg_000083 c2", "definition", "the only definition action span that explicitly contains its subject and coordinated second predicate"],
        ["estg_000031 c1 vs estg_000273 c1", "definition vs definition", "copular action includes `is the difference` in one case and only `is` in another; complement granularity may be context-dependent"],
    ]
    lines = [
        "# SEP-C3 Definition Gold Consistency Audit",
        "",
        "- API calls: **0**.",
        "- This audit checks internal consistency of Gold definition annotations. It does not modify Gold.",
        "",
        "## 1. Modality-label consistency",
        "",
        f"- Definition clauses: {summary['definition_clause_count']} across {summary['definition_sample_count_any']} samples.",
        f"- `shall` definition clauses: {summary['shall_definition_clause_count']}.",
        f"- Definition clauses all four arms non-definition: {summary['clause_all_four_modality_wrong']}.",
        "",
        "### Same-trigger modality distribution",
        "",
        md_table(["Trigger", "Hits", "Gold modalities", "Case ids"], same_trigger_rows),
        "",
        "### Suspected / unresolved consistency issues",
        "",
        md_table(["Issue", "Gold labels / relation", "Evidence"], suspicious),
        "",
        "The `estg_000505 c2` vs `estg_000509 c2` pair is the strongest apparent modality-label inconsistency: the surface construction and action overlap are near-identical, but one is Gold `obligation` and the other Gold `definition`. It is reported as an unresolved Gold-semantics case, not corrected.",
        "",
        "## 2. Action-span consistency",
        "",
        f"- Definition clauses with action: {summary['definition_clause_count']}/{summary['definition_clause_count']}.",
        f"- Definition action spans: {summary['definition_action_span_count']}.",
        f"- Definition clauses with actor: {summary['definition_clauses_with_actor']}.",
        f"- Definition clauses with condition: {summary['definition_clauses_with_condition']}.",
        f"- Definition clauses with constraint: {summary['definition_clauses_with_constraint']}.",
        f"- Definition clauses with exception: {summary['definition_clauses_with_exception']}.",
        "",
        "Action spans are mostly short, predicate-centred spans. Heterogeneity appears in complement inclusion and in two outlier spans:",
        "",
        "1. `estg_000020 c1`: action includes two Gold condition spans; this is the only measured action-condition overlap in the definition corpus.",
        "2. `estg_000083 c2`: action includes subject plus coordinated predicates; most legal-fiction actions are predicate-only.",
        "3. `estg_000031 c1` (`is the difference`) and `estg_000273 c1` (`is`) show that copular complement inclusion is context-dependent.",
        "4. `estg_000283 c1` uses bare `leaves`/`works` while object/adjunct material appears in other fields.",
        "",
        "These are boundary-heterogeneity observations. Only the `estg_000020` action-condition overlap is a direct conflict with S rule 8. No Gold definition clause has an empty action span.",
        "",
        "## 3. Manual review flags",
        "",
        md_table(
            ["Sample / clause", "Reason"],
            [[f"{key[0]} {key[1]}", value]
             for key, value in sorted(MANUAL_REVIEW_NOTES.items())]),
        "",
        "## 4. Conclusion",
        "",
        "- Modality labels are broadly coherent in that Gold reserves `definition` for definitional, classification, legal-fiction, and scope-application clauses, but the `apply` family and the near-identical `shall be assumed` pair require annotation adjudication.",
        "- Action presence is internally consistent: 39/39 definition clauses have actions.",
        "- Action boundary granularity is not fully consistent; it requires annotation-level principles before becoming a prompt rule.",
    ]
    return "\n".join(lines) + "\n"


def contrastive_pairs(arms_summary: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C3 Definition Contrastive Pairs",
        "",
        "- API calls: **0**.",
        "- Pairs are evidence contrasts, not Prompt rules.",
        "",
        "## Pair A: definition clause vs superficially similar obligation clause",
        "",
        "| Case | Gold modality | Gold action | A/B/C/D predicted modality | Why it matters |",
        "| --- | --- | --- | --- | --- |",
        "| estg_000071 c1: `For registered traders, Item 13 applies` | definition | `applies` | obligation / obligation / obligation / obligation | Same `applies` lexeme as `estg_000128 c2`, but Gold separates definition from legal-reference application. |",
        "| estg_000128 c2: `Section 10(2) last sentence shall apply.` | obligation | `apply` | permission / permission / permission / permission in aligned records | Same lexeme, different Gold role; model does not use the distinction. |",
        "",
        "## Pair B: definition action span vs non-definition action span",
        "",
        "| Case | Gold modality | Gold action | Predicted action behaviour | Boundary lesson |",
        "| --- | --- | --- | --- | --- |",
        "| estg_000136 c1: `... shall be determined ...` | definition | `be determined` | obligation; actions `be determined` / `determined` / `be determined` / `be determined` | Definition action can be a passive predicate; model still labels modality obligation. |",
        "| estg_000812 c1: `... profit shall be determined ...` | obligation | `be determined` | obligation; action includes subject + modal in all arms | Same lexical verb, different Gold modality. |",
        "| estg_000080 c4: `... shall be deemed as the acquisition cost` | definition | `shall be deemed as the acquisition cost` | obligation; action variants add/remove `be`, `shall`, and parenthetical material | Gold action includes `shall` here, unlike most bare-infinitive deeming actions. |",
        "",
        "## Pair C: same lexical trigger, different Gold modality",
        "",
        "| Trigger | Definition example | Non-definition example | Gold contrast |",
        "| --- | --- | --- | --- |",
        "| `shall be assumed` / `be assumed` | estg_000509 c2 `a monthly wage payment period shall be assumed` | estg_000505 c2 same construction | definition vs obligation; strongest apparent inconsistency |",
        "| `applies` / `apply` | estg_000071 c1 `Item 13 applies` | estg_000128 c2 `Section 10(2) last sentence shall apply` | definition vs obligation |",
        "| `shall be determined` | estg_000136 c1 | estg_000812 c1 | definition vs obligation |",
        "| `does not apply` | estg_000083 c1 | no non-definition match found in this Gold | definition-only family |",
        "",
        "## Pair D: definition action with condition vs E4 empty-action definition",
        "",
        "| Signal | Gold | E4 | Contrast |",
        "| --- | --- | --- | --- |",
        "| Definition action | 39/39 clauses have >=1 action | actions empty | direct conflict |",
        "| Condition coverage | 28/39 clauses have conditions | empty | E4 under-covers |",
        "| Constraint coverage | 28/39 clauses have constraints | empty | E4 under-covers |",
        "| Legal fiction / shall | 15 definition clauses use `shall` | no shall-based definition example | missing coverage |",
    ]
    return "\n".join(lines) + "\n"


def field_priority_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C3 Definition Field Priority Re-evaluation",
        "",
        "- API calls: **0**.",
        "- This is an evidence status only; it does not authorize Prompt design or modification.",
        "",
        md_table(
            ["Field", "Current evidence status", "Rationale", "Remaining unresolved issue"],
            [
                ["modality", "READY_FOR_PROMPT_DESIGN_REVIEW",
                 "Stable, corpus-wide confusion: 20/29 first-definition samples and 25/39 definition clauses are non-definition in all four arms; 15/15 definition clauses containing `shall` are all four arms wrong.",
                 "`apply`/`shall apply` family and the near-identical estg_000505 c2 vs estg_000509 c2 pair need annotation adjudication."],
                ["action", "READY_FOR_PROMPT_DESIGN_REVIEW (presence); NEEDS_MORE_GOLD_ANALYSIS (exact boundary)",
                 "Gold definition action presence is unambiguous: 39/39 clauses; E4 explicit empty-action example conflicts with Gold and gives a high-risk local explanation for empty definition actions.",
                 "Action complement/boundary granularity is heterogeneous; taxonomy is partly manual-review."],
                ["condition", "NEEDS_MORE_GOLD_ANALYSIS",
                 "28/39 definition clauses have conditions, so definition-context condition coverage is real but was secondary in this round.",
                 "Interaction with definition action boundaries and E4 emptiness is unresolved."],
                ["constraint", "NEEDS_MORE_GOLD_ANALYSIS",
                 "28/39 definition clauses have constraints; prior condition/constraint boundary work remains relevant.",
                 "Definition-specific constraint interaction and R_C scope are unresolved."],
            ]),
        "",
        "`READY_FOR_PROMPT_DESIGN_REVIEW` means the evidence is sufficient for a Prompt design review, not that a Prompt should be changed or written by this study.",
    ]
    return "\n".join(lines) + "\n"


def candidate_principles(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Candidate Annotation Principles (NOT YET PROMPT RULES)",
        "",
        "- Status: **`NOT YET A PROMPT RULE`**",
        "- API calls: **0**.",
        "",
        "## Candidate principle 1: Definition clauses receive an action span",
        "",
        "> Definition clauses still receive an action span representing the definitional predicate.",
        "",
        f"- Support: {summary['definition_clause_count']}/{summary['definition_clause_count']} definition clauses have at least one Gold action; {summary['definition_action_span_count']} action spans.",
        "- Counterexamples: 0 empty-action definition clauses.",
        "- Unresolved cases: estg_000020 action contains condition material; estg_000083 c2 includes subject + coordination; estg_000112 is a fragment.",
        "- Confidence: high for action presence, medium for exact boundary.",
        "",
        "## Candidate principle 2: `definition` modality is broader than `means`",
        "",
        "> Gold `definition` covers explicit definitions, legal fictions/classification (`shall be deemed`, `shall be treated`, `shall constitute`, `shall include`), status predicates (`are not eligible`), and scope-application predicates (`applies`, `does not apply`). Surface `shall` does not by itself imply obligation.",
        "",
        f"- Support: {summary['definition_clause_count']} definition clauses; {summary['shall_definition_clause_count']} with `shall`; 7 with apply/application; 7 within-the-meaning/copular classification.",
        "- Counterexamples / unresolved: 5 non-definition apply clauses; 2 obligation `shall apply`; estg_000505 c2 vs estg_000509 c2 near-identical pair.",
        "- Confidence: medium-high for the broad coverage; medium because Gold modality semantics still has unresolved same-trigger cases.",
        "",
        "## Candidate principle 3: Definition action boundaries are predicate-centred, but not uniformly complement-free",
        "",
        "> Definition action spans are predicate-centred; complements that are conditions, constraints, or exception material are generally kept out, but short predicative complements may be included depending on construction.",
        "",
        "- Support: 44/46 action spans have no measured overlap with condition/constraint/exception; most spans are short predicates.",
        "- Counterexamples / unresolved: estg_000020 action contains two condition spans; estg_000083 c2 contains subject + coordination; copular complement inclusion varies.",
        "- Confidence: medium-low; requires annotation adjudication before Prompt use.",
        "",
        "These candidate principles are annotation-level observations only. They must not be rewritten as Prompt instructions in this round.",
    ]
    return "\n".join(lines) + "\n"


def main_report(gold_cases: Sequence[Mapping[str, Any]],
                candidates: Sequence[Mapping[str, Any]],
                summary: Mapping[str, Any],
                modality_rows: Sequence[Mapping[str, Any]],
                action_rows: Sequence[Mapping[str, Any]]) -> str:
    first_def_rows = summary["first_sample_all_wrong_rows"]
    all_clause_rows = summary["clause_all_wrong_rows"]
    shall_rows = [row for row in modality_rows if "shall" in row["construction_features"].lower() or "shall" in row["clause_text"].lower()]
    # Build a compact sample-level decision table from modality and action rows.
    action_by_clause = defaultdict(list)
    for row in action_rows:
        action_by_clause[(row["sample_id"], row["clause_id"])].append(row)
    decision_rows = []
    for row in modality_rows:
        first_action = (action_by_clause.get((row["sample_id"], row["clause_id"])) or [{}])[0]
        s_conflict = (
            "S8 direct"
            if "action_overlaps_conditions" in (first_action.get("boundary_features") or "")
            else "S11 risk"
        )
        decision_rows.append([
            f"{row['sample_id']} {row['clause_id']}",
            "definition",
            f"{row['pred_modality_A']}/{row['pred_modality_B']}/{row['pred_modality_C']}/{row['pred_modality_D']}",
            first_action.get("gold_action_text", ""),
            first_action.get("pred_action_text_A", ""),
            "E4 yes",
            s_conflict,
            row["error_type"],
        ])
    lines = [
        "# SEP-C3 Definition-Clause Semantics & Prompt Coverage Study v1",
        "",
        "- Task: Definition-Clause Semantics & Prompt Coverage Study",
        "- Role: evidence analyst / annotation-semantics researcher / engineering assistant",
        "- New BPC / LLM / API calls: **0**",
        "- Gold: `data/gold/stage2/estg150_formal_gold_v1.json`",
        "- Predictions: persisted `sep_c3_targeted_refinement_v1` A/B/C/D canonical outputs",
        "- Prompt material audited: `common_system.md`, `examples_E.md`, `semantic_rules_S.md`",
        "- No Prompt was designed, modified, or tested in this round.",
        "",
        "## 0. Executive summary",
        "",
        "The definition-clause corpus contains **39 Gold definition clauses across 34 samples**; **29 samples** have a definition as their first clause and therefore are the record-level evaluator view. All **39/39 definition clauses have at least one Gold action span** (46 action spans total). The prior count of 20 all-arm modality failures is reproduced exactly at first-definition-sample level; at definition-clause level the count is **25/39** because later definition clauses also fail.",
        "",
        "The dominant modality confusion is **definition -> obligation**, followed by definition -> prohibition. `shall` is the largest single confusion source: 15/15 definition clauses containing `shall` are non-definition in all four arms, and 12/20 first-definition all-wrong samples contain `shall` in the first clause. The second clear problem is **action emptiness**: E4 explicitly teaches that a definition clause has empty actions, and S rule 11 says a definition clause may have no actions; Gold instead gives action spans to 39/39 definition clauses.",
        "",
        "E4 is therefore **`CONFLICTS_WITH_GOLD`** on action presence and under-covers definition conditions/constraints, though its `definition` modality label and its mostly-empty actor pattern are not the primary problem.",
        "",
        "## 1. Corpus construction",
        "",
        md_table(
            ["Corpus view", "Count", "Definition"],
            [
                ["Gold clauses with modality == definition", summary["definition_clause_count"], "clause-level corpus"],
                ["Distinct samples with any definition clause", summary["definition_sample_count_any"], "any-position corpus"],
                ["First-clause definition samples", summary["first_definition_sample_count"], "record-level evaluator view / prior report count"],
                ["Definition action spans", summary["definition_action_span_count"], "all definitions"],
                ["Definition clauses with empty action", summary["definition_clauses_with_empty_action"], "Gold action occurrence"],
                ["Definition clauses with actor", summary["definition_clauses_with_actor"], "actor occurrence"],
                ["Definition clauses with condition", summary["definition_clauses_with_condition"], "condition occurrence"],
                ["Definition clauses with constraint", summary["definition_clauses_with_constraint"], "constraint occurrence"],
                ["Definition clauses with exception", summary["definition_clauses_with_exception"], "exception occurrence"],
                ["Broad definition-like candidates outside Gold definition label", len(candidates), "manual-review lexical candidates"],
            ]),
        "",
        "The broad candidate set is deliberately recall-oriented and is not asserted to be a set of missed Gold definitions. It contains **14 clauses** with definition-like surface triggers but non-definition Gold labels. The strongest candidate is `estg_000505 c2`, which is near-identical to Gold definition `estg_000509 c2`.",
        "",
        "## 2. Modality findings",
        "",
        "### 2.1 Gold semantics of `definition` (Q1)",
        "",
        "Gold `definition` is not limited to lexical definitions such as `X means Y`. The 39 clauses show at least six recurring semantic shapes:",
        "",
        "1. Explicit definition / copular classification: `Profit is the difference`; `Income from employment (wages) is`; `Expenditure on repairs means`; `Dependants also include`.",
        "2. Legal fiction / deeming: `shall be deemed`, `is deemed`, `shall be treated as`, `be deemed to be`.",
        "3. Classification / membership: `shall constitute income from capital`, `be income from letting and leasing`, `are not eligible`, `are stock corporations`.",
        "4. Scope / application: `Item 13 applies`, `the following applies`, `does not apply`, `also applies`.",
        "5. Event/relational definitions: `occurs when`, `runs from`, `amounts to`, `is the case when`.",
        "6. Enumerated definitions: `shall include:` followed by lists.",
        "",
        "`shall` in a definition clause is therefore not deontic obligation. It functions as a definitional/legal-fictional marker in `shall include`, `shall be deemed`, `shall be treated`, `shall constitute`, `shall be assumed`, and `shall apply`.",
        "",
        "### 2.2 Current Prompt modality coverage (Q2)",
        "",
        md_table(
            ["Source", "Current wording / behavior", "Compatible with Gold?", "Risk"],
            [
                ["Common", "`- modality: label, evidence.` Required field only; no class semantics.", "Partial", "MISSING_GUIDANCE: no definition-class semantics."],
                ["E4", "`definition; evidence \"means\"; actors and actions empty`", "Modality label yes; action/fields no", "Conflict on action emptiness; narrow trigger coverage."],
                ["S2", "`label each clause obligation, prohibition, permission, or definition`; smallest sufficient trigger", "Partial", "MISSING_GUIDANCE: no definition semantics or `shall` ambiguity."],
                ["S11", "`a definition clause may have no actions`", "Unsupported by Gold action distribution", "POTENTIALLY_MISLEADING / conflict-adjacent."],
                ["R_A / R_C (A-D targeted arms)", "No modality rule; R_A actor, R_C constraint recall", "No direct effect", "Do not correct definition modality/action."],
                ["Default v6 rule 19 (context)", "same `actions may be empty` concept", "Conflicts with Gold", "May reinforce E4/S11 behaviour if v6 is used."],
            ]),
        "",
        "### 2.3 Definition modality error patterns (Q3)",
        "",
        f"- First-definition samples: {summary['first_definition_sample_count']}; all-four-arm non-definition: **{summary['first_definition_sample_all_four_modality_wrong']}**.",
        f"- Definition clauses: {summary['definition_clause_count']}; all-four-arm non-definition: **{summary['clause_all_four_modality_wrong']}**.",
        f"- `shall` definition clauses: {summary['shall_definition_clause_count']}; all-four-arm non-definition: **{summary['shall_definition_clauses_all_four_wrong']}**.",
        "",
        "The 20 first-definition failures decompose as follows: 12 are obligation in all four arms, 6 are prohibition in all four arms, and 2 are mixed non-definition patterns. Thus the most common confusion is **definition -> obligation**; the second is **definition -> prohibition**.",
        "",
        "Example ids:",
        "",
        "```text",
        "definition -> obligation: estg_000037 c1, estg_000071 c1, estg_000080 c4, estg_000082 c1, estg_000136 c1, estg_000293 c1, estg_000302 c1, estg_000414 c1, estg_000509 c2, estg_000522 c1, estg_000572 c1, estg_000664 c1, estg_000773 c1, estg_000776 c1",
        "definition -> prohibition: estg_000020 c1, estg_000083 c1/c2, estg_000087 c1, estg_000209 c1/c2, estg_000210 c1, estg_000800 c1",
        "mixed/non-standard: estg_000218 c1 (non_obligation/prohibition), estg_000232 c2 (obligation/assertion), estg_000854 c1 (obligation/permission)",
        "```",
        "",
        "### 2.4 Syntactic concentration (Q4)",
        "",
        md_table(
            ["Construction family", "Definition support", "All-four-arm failure", "Interpretation"],
            [
                ["`shall` + definitional/legal-fiction verb", summary["shall_definition_clause_count"], summary["shall_definition_clauses_all_four_wrong"], "Strongest concentration; model follows `shall` -> obligation."],
                ["explicit `means`", 1, 0, "E4's own pattern is not the dominant failure."],
                ["`within the meaning` / copular classification", 7, "mixed", "Model often labels definition but drops action; fewer modality errors."],
                ["deeming / legal fiction", 9, "most fail", "`shall be deemed` is read as obligation; `is deemed` often is definition."],
                ["scope/application (`applies`, `does not apply`)", 7, "most fail", "`applies` is read as obligation, `does not apply` as prohibition."],
                ["negative eligibility / status (`are not eligible`)", 2, "all fail", "Model reads status as prohibition."],
            ]),
        "",
        "## 3. `shall` specific audit (Q9 / section 9)",
        "",
        md_table(
            ["Construction", "Definition count", "Predicted modality pattern", "Action pattern"],
            [
                ["`shall include`", 1, "obligation x4", "action present; `include`"],
                ["`shall be deemed`", 5, "mostly obligation; one prohibition association", "`be deemed...` present but often boundary-shifted"],
                ["`shall be treated`", 1, "obligation/prohibition x4", "predicate action present"],
                ["`shall constitute`", 1, "obligation x4", "action present"],
                ["`shall be assumed`", 2, "obligation x4", "action present/merged"],
                ["`shall apply`", 1, "obligation x4", "action empty in A/B/C/D aligned clause"],
                ["other `shall be ...`", 4, "obligation x4 mostly", "mixed"],
            ]),
        "",
        "All 15 `shall` definition clauses are non-definition in all four arms. `shall` is therefore the largest single confusion source, but it is not the only one: `does not apply`, `applies`, and `are not eligible` also fail without `shall`.",
        "",
        "## 4. Action findings",
        "",
        "### 4.1 Why every definition clause has an action (Q1)",
        "",
        "Gold treats the definitional predicate itself as the action. This includes copulas (`is`, `are shares`), definitional verbs (`means`, `include`), legal fictions (`be deemed`), classifications (`constitute`, `be income`), and scope predicates (`applies`, `does not apply`). The action is therefore not the regulated conduct: it is the definitional/classification predicate.",
        "",
        "Gold action taxonomy by primary category:",
        "",
    ]
    taxonomy_counts = Counter(row["taxonomy_primary"] for row in action_rows)
    lines.extend([
        md_table(
            ["Primary taxonomy", "Gold action spans", "Examples"],
            [
                [key, value, "; ".join(row["gold_action_text"] for row in action_rows
                                        if row["taxonomy_primary"] == key)[:180]]
                for key, value in sorted(taxonomy_counts.items())
            ]),
        "",
        "Multiple actions are present in 4 definition clauses (one with 2 actions, three with 3 actions). The 46 spans are predominantly short predicate-centred units.",
        "",
        "### 4.2 E4's definition action demonstration (Q2)",
        "",
        "E4 explicitly states `actors and actions empty` for its definition clause. Therefore the earlier suspicion is confirmed: **E4 does demonstrate definition action = empty**. The action-empty count is 0/39 in Gold. This is a direct prompt-Gold mismatch on action presence.",
        "",
        "### 4.3 S action guidance (Q3)",
        "",
        "See `sep_c3_S_modality_action_audit.md`. Core result: S4 is broadly compatible with the 46 Gold actions as verb-centred units, S8 is compatible except estg_000020, and S11 is unsupported by the Gold action distribution.",
        "",
        "## 5. Definition action boundary taxonomy",
        "",
        md_table(
            ["Taxonomy", "Primary count", "Gold evidence", "Boundary note"],
            [
                ["copular action", taxonomy_counts.get("copular_action", 0), "is, are shares, are stock corporations, is the case", "Short predicative complements may be included."],
                ["definitional verb", taxonomy_counts.get("definitional_verb", 0), "means, include, shall include", "Object/enumerated complements often move to constraints."],
                ["classification verb", taxonomy_counts.get("classification_verb", 0), "constitute, be income, are not eligible, be treated", "Status/classification predicate is still action."],
                ["deeming / legal fiction", taxonomy_counts.get("deeming_legal_fiction", 0), "shall be deemed, is deemed, be assumed", "`shall` can be inside the definition action."],
                ["relational predicate", taxonomy_counts.get("relational_predicate", 0), "applies, does not apply, runs, amounts to", "Scope/application counts as definition here."],
                ["noun-phrase predicate", taxonomy_counts.get("noun_phrase_predicate", 0), "none in definition corpus", "No support."],
                ["action span includes subordinate phrase", taxonomy_counts.get("action_span_includes_subordinate_phrase", 0), "estg_000020, estg_000083 c2", "Small outlier family."],
                ["other event predicate", taxonomy_counts.get("other_event_predicate", 0), "are acquired, are newly issued, leaves, works", "Needs manual boundary review."],
                ["uncertain", taxonomy_counts.get("uncertain", 0), "manual flags", "Not forced into a category."],
            ]),
        "",
        "## 6. Condition / constraint in definition clauses (secondary)",
        "",
        f"- Conditions: {summary['definition_clauses_with_condition']}/39 definition clauses.",
        f"- Constraints: {summary['definition_clauses_with_constraint']}/39 definition clauses.",
        f"- Exceptions: {summary['definition_clauses_with_exception']}/39 definition clauses.",
        f"- All three empty: {summary['definition_clauses_with_all_three_empty']}/39.",
        "- Only estg_000020 has action-condition span overlap in the definition corpus; it has 2 overlapping condition spans.",
        "- No definition action span overlaps a Gold constraint or exception span.",
        "",
        "This does not justify a new R_C study in this round, but it shows that E4's empty condition/constraint pattern is not representative of definition clauses.",
        "",
        "## 7. Gold consistency audit pointer",
        "",
        "See `sep_c3_definition_gold_consistency_audit.md`.",
        "",
        "## 8. E4 coverage audit pointer",
        "",
        "See `sep_c3_E4_coverage_audit.md`. Status: **`CONFLICTS_WITH_GOLD`**.",
        "",
        "## 9. E examples coverage matrix pointer",
        "",
        "See `sep_c3_E_examples_coverage_matrix.md`.",
        "",
        "## 10. S modality/action audit pointer",
        "",
        "See `sep_c3_S_modality_action_audit.md`.",
        "",
        "## 11. Instruction missing vs conflict diagnosis",
        "",
        md_table(
            ["Stable failure", "Diagnosis", "Sample evidence"],
            [
                ["`shall` definition -> obligation/prohibition", "`MISSING_GUIDANCE`", "15/15 shall definition clauses fail all four arms"],
                ["negative scope/status (`does not apply`, `are not eligible`) -> prohibition", "`MISSING_GUIDANCE` + `AMBIGUOUS_GUIDANCE`", "estg_000083 c1, estg_000209 c1, estg_000210 c1, estg_000800 c1"],
                ["definition -> non-definition for `applies`", "`AMBIGUOUS_GUIDANCE`", "estg_000071 c1 vs estg_000128 c2; 7 definition vs 5 non-definition apply clauses"],
                ["definition action empty", "`CONFLICTING_GUIDANCE`", "E4 says empty; Gold has 39/39 non-empty"],
                ["definition action boundary shift (be/deemed/determined/assumed)", "`GUIDANCE_PRESENT_BUT_EXECUTION_UNSTABLE`", "estg_000080, estg_000136, estg_000509 etc."],
                ["exact action complement inclusion", "`GOLD_SEMANTICS_UNCLEAR`", "estg_000020, estg_000031 vs estg_000273, estg_000083 c2"],
                ["same `shall be assumed` text -> two Gold modalities", "`GOLD_SEMANTICS_UNCLEAR`", "estg_000505 c2 vs estg_000509 c2"],
            ]),
        "",
        "Approximate stable-failure accounting this round:",
        "",
        "- `MISSING_GUIDANCE`: modality class semantics and `shall`-in-definition coverage; at least 15/25 all-wrong clauses are directly `shall`-driven.",
        "- `CONFLICTING_GUIDANCE`: action emptiness from E4/S11 (39/39 Gold counterexamples).",
        "- `AMBIGUOUS_GUIDANCE`: S4 vs S11 for definition action; apply-family modality.",
        "- `GUIDANCE_PRESENT_BUT_EXECUTION_UNSTABLE`: definition action boundary variants across arms.",
        "- `GOLD_SEMANTICS_UNCLEAR`: estg_000505/509 pair; apply family; action complement granularity.",
        "",
        "## 12. Candidate annotation principles",
        "",
        candidate_principles(summary),
        "",
        "## 13. Sample-level decision table (all 39 definition clauses)",
        "",
        md_table(
            ["Sample", "Gold modality", "Pred modality A/B/C/D", "Gold action", "Pred action", "E4-like?", "S conflict?", "Error type"],
            decision_rows),
        "",
        "## 14. Field priority re-evaluation",
        "",
        field_priority_report(summary),
        "",
        "## 15. Final answers",
        "",
        f"1. Definition clause corpus: **{summary['definition_clause_count']} clauses / {summary['definition_sample_count_any']} samples**; **{summary['first_definition_sample_count']}** first-definition samples.",
        f"2. Modality four-arm all-wrong: **{summary['first_definition_sample_all_four_modality_wrong']}/29** first-definition samples; **{summary['clause_all_four_modality_wrong']}/39** definition clauses.",
        "3. Most common modality confusion: **definition -> obligation**, then **definition -> prohibition**.",
        f"4. `shall` as main confusion source: **yes, largest single source**; {summary['shall_definition_clause_count']} definition clauses contain `shall`, and all {summary['shall_definition_clauses_all_four_wrong']} fail all four arms; {summary['first_definition_all_wrong_with_shall']}/20 first-definition all-wrong samples contain `shall`.",
        f"5. Gold definition action pattern: **{summary['definition_action_span_count']} predicate-centred action spans** across {summary['definition_clause_count']} clauses; copular, definitional, classification, deeming, relational, and event predicates.",
        f"6. 39/39 action check: **confirmed**; empty-action definition clauses = {summary['definition_clauses_with_empty_action']}.",
        "7. E4 vs Gold: **conflicts on action emptiness**; E4 status `CONFLICTS_WITH_GOLD`.",
        "8. E4 misleading modality/action: modality label itself is not the conflict; **action emptiness is directly misleading**; condition/constraint emptiness is under-representative.",
        "9. Current S modality/action rules: **S2 missing definition semantics; S11 conflict-adjacent/unsupported; S8 has one direct Gold counterexample (estg_000020); S4 is mostly compatible but boundary-ambiguous**.",
        "10. Main stable action-boundary pattern: definitional predicate gets an action; conditions/constraints/exceptions are generally separate, with a small subordinate/complement outlier family.",
        f"11. Gold inconsistency: **suspected**; strongest case is estg_000505 c2 vs estg_000509 c2; apply family also needs adjudication. No Gold was modified.",
        "12. Instruction diagnosis counts: `MISSING_GUIDANCE` (shall/class semantics), `CONFLICTING_GUIDANCE` (action empty), `AMBIGUOUS_GUIDANCE` (S4/S11; apply family), `GUIDANCE_PRESENT_BUT_EXECUTION_UNSTABLE` (action boundary), `GOLD_SEMANTICS_UNCLEAR` (same-text modality pair).",
        "13. Stable candidate annotation principle: **yes**; strongest is definition clauses still receive an action span (39/39 support, 0 counterexamples).",
        "14. Counterexamples: **0** for action presence; **1 clause / 2 condition spans** for the no-action-condition-overlap boundary principle; **1 near-identical pair** for modality uniformity.",
        "15. Modality status: **`READY_FOR_PROMPT_DESIGN_REVIEW`**, with unresolved same-trigger annotation cases.",
        "16. Action status: **`READY_FOR_PROMPT_DESIGN_REVIEW` for presence; `NEEDS_MORE_GOLD_ANALYSIS` for exact boundary**.",
        "17. Condition/constraint new evidence: definition clauses frequently contain both (28/39 each), but this round did not extend R_C.",
        "18. Reports path: `formal_experiment/outputs/reports/sep_c3_definition_*`.",
        "19. Script/test: `formal_experiment/scripts/analyze_sep_c3_definition_clause_v1.py`, `formal_experiment/tests/test_sep_c3_definition_clause_v1.py`.",
        "20. Git commit/push status: scoped commit and normal push were performed after report generation; see final task response.",
        "21. Unresolved issues: apply-family modality, estg_000505/509 inconsistency, action-boundary taxonomy, E4 wording (not modified).",
        "",
        "## 16. Stop condition",
        "",
        "No Prompt design, no API calls, no new experiment arms. This report stops at annotation semantics and evidence.",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    gold_records = load_gold()
    arms = load_arms()
    gold_cases, candidates = build_cases(gold_records, arms)
    summary = summarize_gold(gold_records, arms)
    modality_rows = modality_matrix_rows(gold_cases)
    action_rows = action_matrix_rows(gold_cases)

    write_jsonl(REPORT_DIR / "sep_c3_definition_clause_cases.jsonl",
                list(gold_cases) + list(candidates))
    write_csv(REPORT_DIR / "sep_c3_definition_modality_matrix.csv",
              modality_rows, [
                  "sample_id", "clause_id", "clause_index", "gold_modality",
                  "construction_features", "clause_text",
                  "pred_modality_A", "pred_modality_B", "pred_modality_C",
                  "pred_modality_D", "all_four_wrong", "error_type",
                  "gold_action_count", "pred_action_count_A",
                  "pred_action_count_B", "pred_action_count_C",
                  "pred_action_count_D", "manual_review_required", "notes",
              ])
    action_fieldnames = [
        "sample_id", "clause_id", "action_index", "gold_action_text",
        "action_length", "taxonomy_primary", "taxonomy_secondary",
        "boundary_features", "manual_review_required",
    ]
    for arm in ARMS:
        action_fieldnames.extend([
            f"pred_modality_{arm}", f"pred_action_text_{arm}",
            f"action_outcome_{arm}",
        ])
    write_csv(REPORT_DIR / "sep_c3_definition_action_matrix.csv",
              action_rows, action_fieldnames)
    write_text(REPORT_DIR / "sep_c3_definition_clause_semantics_v1.md",
               main_report(gold_cases, candidates, summary, modality_rows,
                           action_rows))
    write_text(REPORT_DIR / "sep_c3_definition_contrastive_pairs.md",
               contrastive_pairs(summary))
    write_text(REPORT_DIR / "sep_c3_E4_coverage_audit.md",
               e4_audit(gold_cases, summary))
    write_text(REPORT_DIR / "sep_c3_E_examples_coverage_matrix.md",
               e_examples_coverage(gold_records))
    write_text(REPORT_DIR / "sep_c3_S_modality_action_audit.md",
               s_audit(summary))
    write_text(REPORT_DIR / "sep_c3_definition_gold_consistency_audit.md",
               gold_consistency_audit(gold_cases, summary))
    write_text(REPORT_DIR / "sep_c3_definition_field_priority.md",
               field_priority_report(summary))

    print(json.dumps({
        "definition_clauses": summary["definition_clause_count"],
        "definition_samples_any": summary["definition_sample_count_any"],
        "first_definition_samples": summary["first_definition_sample_count"],
        "definition_action_spans": summary["definition_action_span_count"],
        "first_definition_all_four_wrong": summary["first_definition_sample_all_four_modality_wrong"],
        "definition_clause_all_four_wrong": summary["clause_all_four_modality_wrong"],
        "shall_definition_clauses": summary["shall_definition_clause_count"],
        "shall_all_four_wrong": summary["shall_definition_clauses_all_four_wrong"],
        "definition_like_candidates": len(candidates),
        "modality_rows": len(modality_rows),
        "action_rows": len(action_rows),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()




