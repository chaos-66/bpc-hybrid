# -*- coding: utf-8 -*-
"""Zero-API definition-clause adjudication and Prompt Design Gate analysis.

This script reads only frozen Gold, persisted SEP-C3 A/B/C/D canonical
predictions, and the existing E/S prompt modules.  It writes new analysis
artefacts under outputs/reports and never modifies Gold, predictions, prompts,
schemas, evaluators, or source data.
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
    "E4": ROOT / "prompts" / "sun_compat" / "modular_v1" / "examples_E.md",
    "S": ROOT / "prompts" / "sun_compat" / "modular_v1" / "semantic_rules_S.md",
    "common": ROOT / "prompts" / "sun_compat" / "modular_v1" / "common_system.md",
}

APPLY_RE = re.compile(r"\bappl(?:y|ies)\b", re.IGNORECASE)
SHALL_RE = re.compile(r"\bshall\b", re.IGNORECASE)

SHALL_FAMILY_PATTERNS: dict[str, re.Pattern[str]] = {
    "shall_include": re.compile(r"\bshall\s+include\b", re.IGNORECASE),
    "shall_be_deemed": re.compile(
        r"\bshall\s+(?:also\s+)?be\s+deemed\b", re.IGNORECASE),
    "shall_be_treated": re.compile(
        r"\bshall\s+(?:also\s+)?be\s+treated\b", re.IGNORECASE),
    "shall_constitute": re.compile(r"\bshall\s+constitute\b", re.IGNORECASE),
    "shall_be_assumed": re.compile(
        r"\bshall\s+be\s+assumed\b", re.IGNORECASE),
    "shall_apply": re.compile(r"\bshall\s+(?:also\s+)?apply\b", re.IGNORECASE),
    "shall_be_determined": re.compile(
        r"\bshall\s+be\s+determined\b", re.IGNORECASE),
    "shall_be_income": re.compile(
        r"\bshall\b.{0,140}\bbe\s+income\b", re.IGNORECASE | re.DOTALL),
}

PREDICATE_MARKER_RE = re.compile(
    r"\b(?:is|are|be|was|were|include|includes|included|means|amounts?|"
    r"appl(?:y|ies)|deem(?:ed|s)?|treat(?:ed|s)?|form(?:s|ed)?|"
    r"determin(?:e|ed|es|ing)?|compensat(?:e|ed|es)?|irrelevant|shares?|"
    r"acquir(?:e|ed|es)?|issue(?:d|s)?|declare(?:d|s)?|eligible|stock|"
    r"runs?|occur(?:s|red)?|leav(?:e|es|ing)?|work(?:s|ed)?|"
    r"constitut(?:e|es|ed)?|assum(?:e|ed|es)?|subject|obligat(?:ed|e)|"
    r"secure)\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8").splitlines() if line.strip()]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _csv_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = "\n".join(line.rstrip() for line in value.splitlines())
    return text.replace("\r", " ").replace("\n", " ")


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]],
              fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def span_overlap(a: Mapping[str, Any], b: Mapping[str, Any]) -> int:
    if not a or not b:
        return 0
    return max(0, min(int(a.get("end", 0)), int(b.get("end", 0)))
               - max(int(a.get("start", 0)), int(b.get("start", 0))))


def span_contains(outer: Mapping[str, Any], inner: Mapping[str, Any]) -> bool:
    return (int(outer.get("start", 0)) <= int(inner.get("start", 0))
            and int(inner.get("end", 0)) <= int(outer.get("end", 0)))


def span_ratio(span: Mapping[str, Any], container: Mapping[str, Any]) -> float:
    if not span or not container:
        return 0.0
    length = max(1, int(container.get("end", 0)) - int(container.get("start", 0)))
    return span_overlap(span, container) / length


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


def span_texts(spans: Sequence[Mapping[str, Any]] | None) -> list[str]:
    return [str(span.get("text", "")) for span in (spans or [])]


def md_escape(value: Any, limit: int | None = None) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").replace("\n", " ")
    text = text.replace("|", "\\|")
    if limit is not None and len(text) > limit:
        text = text[: max(0, limit - 1)].rstrip() + "…"
    return text


def md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    out = ["| " + " | ".join(md_escape(h) for h in headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join(md_escape(cell) for cell in row) + " |")
    return "\n".join(out)


def json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Loading and alignment
# ---------------------------------------------------------------------------

def load_gold_records() -> list[dict[str, Any]]:
    return list(read_json(GOLD_PATH)["records"])


def load_arms() -> dict[str, dict[str, dict[str, Any]]]:
    arms: dict[str, dict[str, dict[str, Any]]] = {}
    for arm in ARMS:
        path = TARGETED_DIR / arm / "repeat-01" / "canonical_predictions.jsonl"
        arms[arm] = {row["sample_id"]: row for row in read_jsonl(path)}
    return arms


def align_prediction(arm_record: Mapping[str, Any],
                     gold_span: Mapping[str, Any]) -> dict[str, Any]:
    clauses = ((arm_record or {}).get("record") or {}).get("clauses") or []
    best = None
    best_overlap = 0
    for clause in clauses:
        overlap = span_overlap(gold_span, clause.get("clause_span") or {})
        if overlap > best_overlap:
            best_overlap = overlap
            best = clause
    ratio = span_ratio(gold_span, best.get("clause_span") or {}) if best else 0.0
    aligned = bool(best) and ratio >= 0.5
    return {
        "available": bool(best),
        "alignment_quality": ("aligned" if aligned
                              else "low_overlap" if best else "no_overlapping_clause"),
        "overlap_chars": best_overlap,
        "overlap_ratio": round(ratio, 4),
        "clause_id": (best or {}).get("clause_id"),
        "clause_span": compact_span((best or {}).get("clause_span") or {}),
        "modality_label": ((best or {}).get("modality") or {}).get("label"),
        "modality_evidence": compact_spans(
            ((best or {}).get("modality") or {}).get("evidence") or []),
        "actors": compact_spans((best or {}).get("actors") or []),
        "actions": compact_spans((best or {}).get("actions") or []),
        "conditions": compact_spans((best or {}).get("conditions") or []),
        "constraints": compact_spans((best or {}).get("constraints") or []),
        "exceptions": compact_spans((best or {}).get("exceptions") or []),
    }


def predictions_for_span(arms: Mapping[str, Mapping[str, Any]],
                         sample_id: str,
                         gold_span: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {arm: align_prediction(arms[arm].get(sample_id, {}), gold_span)
            for arm in ARMS}


def predicted_labels(predictions: Mapping[str, Mapping[str, Any]]) -> dict[str, str | None]:
    return {arm: predictions[arm].get("modality_label") for arm in ARMS}


def all_four_wrong_for_gold(predictions: Mapping[str, Mapping[str, Any]],
                            gold_label: str) -> bool:
    return all(predictions[arm].get("modality_label") != gold_label for arm in ARMS)


# ---------------------------------------------------------------------------
# Manual adjudication annotations (analysis only; no prompt wording)
# ---------------------------------------------------------------------------

APPLY_REVIEW: dict[tuple[str, str], dict[str, str]] = {
    ("estg_000071", "c1"): {
        "judgment": "DEFINITIONAL_SCOPE_APPLICATION",
        "why": "The clause says which item governs a class of traders; no duty-bearer or regulated conduct is expressed.",
        "confidence": "medium-high",
        "dimension": "scope/application statement",
    },
    ("estg_000083", "c1"): {
        "judgment": "DEFINITIONAL_SCOPE_EXCEPTION",
        "why": "The clause defines a non-application case and carries the exception; no command to an actor is expressed.",
        "confidence": "high",
        "dimension": "scope/application plus exception",
    },
    ("estg_000164", "c1"): {
        "judgment": "DEFINITIONAL_SCOPE_INTRODUCTION",
        "why": "An introductory applicability statement for the following computation rules; no actor or duty is expressed.",
        "confidence": "medium",
        "dimension": "scope/application statement",
    },
    ("estg_000209", "c2"): {
        "judgment": "DEFINITIONAL_SCOPE_EXTENSION",
        "why": "The clause extends a classification/eligibility rule to capital reductions; it does not impose a new behavioural duty.",
        "confidence": "medium",
        "dimension": "classification-scope extension",
    },
    ("estg_000218", "c1"): {
        "judgment": "DEFINITIONAL_SCOPE_EXCEPTION",
        "why": "The clause defines when the notification obligation does not apply; it is a scope/exception statement.",
        "confidence": "high",
        "dimension": "scope/application plus exception",
    },
    ("estg_000664", "c1"): {
        "judgment": "DEFINITIONAL_SCOPE_INTRODUCTION",
        "why": "The clause introduces the applicability of a provision and contains no actor/duty-bearing predicate.",
        "confidence": "medium-high",
        "dimension": "scope/application statement",
    },
    ("estg_000800", "c1"): {
        "judgment": "DEFINITIONAL_SCOPE_EXCEPTION",
        "why": "The clause defines a non-application condition/exception; no deontic actor is expressed.",
        "confidence": "high",
        "dimension": "scope/application plus exception",
    },
    ("estg_000056", "c1"): {
        "judgment": "DEONTIC_APPLICATION_DIRECTIVE",
        "why": "Gold treats the clause as an obligation imposing that repair-expense rules apply; it is not merely a definition of scope.",
        "confidence": "medium",
        "dimension": "application command",
    },
    ("estg_000128", "c2"): {
        "judgment": "DEONTIC_CROSS_REFERENCE_APPLICATION",
        "why": "Gold reads the cross-reference as a mandatory application of Section 10(2), not as a definition.",
        "confidence": "high",
        "dimension": "cross-reference command",
    },
    ("estg_000145", "c1"): {
        "judgment": "DIFFERENT_VERB_SENSE_PERMISSION",
        "why": "'apply' here means to make/submit an application; it is an actor action and not the applicability predicate under review.",
        "confidence": "high",
        "dimension": "false friend; verb sense",
    },
    ("estg_000208", "c2"): {
        "judgment": "DEONTIC_APPLICATION_DIRECTIVE",
        "why": "Gold treats the extension of subsection (1)(3) as a normative application requirement in this context.",
        "confidence": "medium",
        "dimension": "application command",
    },
    ("estg_000306", "c1"): {
        "judgment": "DEONTIC_SCOPE_INTRODUCTION",
        "why": "Surface-parallel to definitional introductory 'applies', but Gold labels this obligation; no stable Gold discriminator is visible.",
        "confidence": "low-medium",
        "dimension": "unresolved near-identical contrast",
    },
}

PAIR_505_509_NOTES = {
    "question_1": "No. The two c2 propositions are essentially the same: 'a monthly wage payment period shall be assumed'. Both have no actor, the same action 'be assumed', and 'a monthly wage payment period' as a Gold constraint. The difference is not sufficient to explain a Gold modality shift from obligation to definition.",
    "question_2": "Only surface/deictic differences exist: 000505 uses 'in this respect', while 000509 uses 'for this purpose'; 000509 c2 ends with a period and Gold annotates 'for this purpose' as a condition, whereas 000505 does not annotate that condition. These are two renderings of the same legal-fiction/computational-basis statement; they do not establish a deontic-vs-definition semantic boundary.",
    "question_3": "POTENTIAL_GOLD_INCONSISTENCY",
}

PAIR_DETERMINED_NOTES = {
    "interpretation": "The difference is contextually explainable. 'X shall be determined by Y' defines the identity/content of X (Y supplies the determinant), while 'profit shall be determined in accordance with Section 5' imposes a method obligation on an identified taxpayer class.",
    "caveat": "This interpretation comes from one pair only and rests on argument structure/context, not on a surface trigger that can be applied from 'shall be determined' alone; it is not written as a Prompt rule in this round.",
    "gold_inconsistency": "NO",
}

E4_COMPONENT_ROWS = [
    {
        "component": "definition modality label",
        "gold_support": "39/39 Gold definition clauses support the label definition.",
        "counterexamples": "0",
        "status": "KEEP",
        "note": "The label itself is correct; the problem is later action/field guidance.",
    },
    {
        "component": "evidence \"means\"",
        "gold_support": "1/39 Gold definition clauses use explicit means (estg_000057 c1).",
        "counterexamples": "0",
        "status": "KEEP",
        "note": "Valid trigger but not representative of the 39-clause distribution.",
    },
    {
        "component": "actors empty",
        "gold_support": "37/39 Gold definition clauses have empty actors.",
        "counterexamples": "estg_000283 c1; estg_000417 c1",
        "status": "KEEP",
        "note": "Majority-compatible; not universal because embedded relational definitions name an actor.",
    },
    {
        "component": "actions empty",
        "gold_support": "0/39 Gold definition clauses have empty actions.",
        "counterexamples": "39/39 Gold definition clauses (46 action spans total)",
        "status": "CONFLICTING",
        "note": "Direct Prompt-Gold conflict on action presence.",
    },
    {
        "component": "conditions empty",
        "gold_support": "11/39 Gold definition clauses have no condition.",
        "counterexamples": "28/39 Gold definition clauses have at least one condition",
        "status": "UNDER-REPRESENTATIVE",
        "note": "Empty condition is a minority pattern.",
    },
    {
        "component": "constraints empty",
        "gold_support": "11/39 Gold definition clauses have no constraint.",
        "counterexamples": "28/39 Gold definition clauses have at least one constraint",
        "status": "UNDER-REPRESENTATIVE",
        "note": "Empty constraint is a minority pattern.",
    },
    {
        "component": "exceptions empty",
        "gold_support": "34/39 Gold definition clauses have no exception.",
        "counterexamples": "5/39 Gold definition clauses have an exception",
        "status": "KEEP",
        "note": "Empty exceptions is the majority pattern, but not universal.",
    },
]

S_DIAGNOSIS = [
    {
        "rule": "S2",
        "diagnosis": "MISSING_DEFINITION_MODALITY_GUIDANCE",
        "supporting": "20/29 first-definition samples and 25/39 definition clauses are non-definition in all four arms; 15/15 shall-definition clauses fail all four arms; two-arm confusions are definition -> obligation/prohibition.",
        "counterexamples": "None direct: S2 does list definition as a label, but it supplies no class semantics or shall ambiguity guidance.",
        "confidence": "high",
        "details": "The failure is not absence of the word definition but absence of annotation-level semantics for legal fiction, classification, and scope application.",
    },
    {
        "rule": "S11",
        "diagnosis": "MISLEADING_PERMISSIVE_GUIDANCE",
        "supporting": "39/39 definition clauses have action; 0 empty-action clauses. Aligned predicted empty-action counts over 39 definitions are A=10, B=13, C=12, D=12.",
        "counterexamples": "If 'may' is read only as logical possibility, no direct Gold contradiction exists; as a design cue it is unsupported and locally misleading because every Gold definition has a definitional predicate action.",
        "confidence": "high",
        "details": "The problem is permissiveness relative to the observed Gold distribution, not a strict logical impossibility.",
    },
    {
        "rule": "S8",
        "diagnosis": "LOCALLY_CONFLICTING_ACTION_BOUNDARY_GUIDANCE",
        "supporting": "44/46 definition action spans do not overlap any Gold condition/constraint/exception span.",
        "counterexamples": "estg_000020 c1: one Gold action span contains two separately annotated Gold condition spans.",
        "confidence": "high (local conflict); medium for any generalized boundary repair",
        "details": "Only a local direct counterexample is established; exact complement/subordinate boundary remains unresolved and is intentionally not solved in this round.",
    },
]

# ---------------------------------------------------------------------------
# Case construction
# ---------------------------------------------------------------------------

def make_case(record: Mapping[str, Any], clause_index: int,
              clause: Mapping[str, Any],
              arms: Mapping[str, Mapping[str, Any]],
              case_scopes: Iterable[str]) -> dict[str, Any]:
    sample_id = str(record["sample_id"])
    clause_span = compact_span(clause.get("clause_span") or {})
    actions = clause.get("actions") or []
    action_presence = {
        "has_action": bool(actions),
        "action_count": len(actions),
        "all_actions_within_clause": all(
            span_contains(clause_span, action) for action in actions),
        "predicate_markers": sorted({
            m.group(0).lower()
            for action in actions
            for m in [PREDICATE_MARKER_RE.search(str(action.get("text", "")))]
            if m
        }),
        "action_texts": span_texts(actions),
    }
    prev_clause = (record["clauses"][clause_index - 1]
                   if clause_index > 0 else None)
    next_clause = (record["clauses"][clause_index + 1]
                   if clause_index + 1 < len(record["clauses"]) else None)
    return {
        "case_id": f"{sample_id}:{clause.get('clause_id')}",
        "case_scopes": sorted(set(case_scopes)),
        "sample_id": sample_id,
        "clause_id": clause.get("clause_id"),
        "clause_index": clause_index,
        "source_text": record.get("approved_text_en", ""),
        "clause_span": clause_span,
        "clause_text": clause_span.get("text", ""),
        "context": {
            "prev_clause_id": (prev_clause or {}).get("clause_id"),
            "prev_clause_text": ((prev_clause or {}).get("clause_span") or {}).get("text", ""),
            "next_clause_id": (next_clause or {}).get("clause_id"),
            "next_clause_text": ((next_clause or {}).get("clause_span") or {}).get("text", ""),
        },
        "clause_segmentation": [
            {
                "clause_id": c.get("clause_id"),
                "clause_span": compact_span(c.get("clause_span") or {}),
                "modality": c.get("modality"),
                "action_texts": span_texts(c.get("actions") or []),
                "condition_texts": span_texts(c.get("conditions") or []),
                "constraint_texts": span_texts(c.get("constraints") or []),
                "exception_texts": span_texts(c.get("exceptions") or []),
            }
            for c in record.get("clauses") or []
        ],
        "gold": {
            "modality": clause.get("modality"),
            "actors": compact_spans(clause.get("actors") or []),
            "actions": compact_spans(actions),
            "conditions": compact_spans(clause.get("conditions") or []),
            "constraints": compact_spans(clause.get("constraints") or []),
            "exceptions": compact_spans(clause.get("exceptions") or []),
        },
        "gold_action_presence": action_presence,
        "predictions": predictions_for_span(arms, sample_id, clause_span),
    }


def build_case_map(gold_records: Sequence[Mapping[str, Any]],
                   arms: Mapping[str, Mapping[str, Any]]) -> tuple[
                       dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    case_map: dict[tuple[str, str], dict[str, Any]] = {}
    definition_cases: list[dict[str, Any]] = []

    def add(record: Mapping[str, Any], idx: int, clause: Mapping[str, Any],
            scopes: Iterable[str]) -> dict[str, Any]:
        case = make_case(record, idx, clause, arms, scopes)
        key = (str(record["sample_id"]), str(clause.get("clause_id")))
        if key not in case_map:
            case_map[key] = case
        else:
            existing = set(case_map[key].get("case_scopes") or [])
            existing.update(scopes)
            case_map[key]["case_scopes"] = sorted(existing)
        return case_map[key]

    for record in gold_records:
        for idx, clause in enumerate(record.get("clauses") or []):
            text = str((clause.get("clause_span") or {}).get("text", ""))
            if clause.get("modality") == "definition":
                case = add(record, idx, clause, {"definition_action_presence"})
                definition_cases.append(case)
                if SHALL_RE.search(text):
                    case["case_scopes"] = sorted(set(case["case_scopes"]) |
                                                 {"shall_definition_family"})
                if APPLY_RE.search(text):
                    case["case_scopes"] = sorted(set(case["case_scopes"]) |
                                                 {"apply_family_core"})
            # Add all active apply/applies comparison clauses.
            if APPLY_RE.search(text):
                add(record, idx, clause, {"apply_family_core"})
            # Add similar non-definition clauses for shall families.
            if clause.get("modality") != "definition" and SHALL_RE.search(text):
                for family, pattern in SHALL_FAMILY_PATTERNS.items():
                    if pattern.search(text):
                        add(record, idx, clause,
                            {"shall_family_similar_nondefinition", family})
                        break
    # Explicit target pairs / named contrast cases.
    for sample_id in ("estg_000505", "estg_000509"):
        record = next(r for r in gold_records if r["sample_id"] == sample_id)
        for idx, clause in enumerate(record["clauses"]):
            if clause.get("clause_id") == "c2":
                add(record, idx, clause, {"pair_estg_000505_vs_estg_000509"})
    for sample_id in ("estg_000136", "estg_000812"):
        record = next(r for r in gold_records if r["sample_id"] == sample_id)
        for idx, clause in enumerate(record["clauses"]):
            if clause.get("clause_id") == "c1":
                add(record, idx, clause, {"pair_shall_be_determined"})
    return case_map, definition_cases


# ---------------------------------------------------------------------------
# Summary computation
# ---------------------------------------------------------------------------

def classify_shall_family(text: str) -> str | None:
    for family, pattern in SHALL_FAMILY_PATTERNS.items():
        if pattern.search(text):
            return family
    return None


def build_summary(gold_records: Sequence[Mapping[str, Any]],
                  arms: Mapping[str, Mapping[str, Any]],
                  case_map: Mapping[tuple[str, str], Mapping[str, Any]],
                  definition_cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    all_defs = list(definition_cases)
    first_def = [
        record for record in gold_records
        if (record.get("clauses") or [])
        and (record["clauses"][0].get("modality") == "definition")
    ]
    action_count = sum(len(c["gold"]["actions"]) for c in all_defs)
    empty_action = sum(1 for c in all_defs if not c["gold"]["actions"])
    actor_nonempty = sum(1 for c in all_defs if c["gold"]["actors"])
    condition_count = sum(1 for c in all_defs if c["gold"]["conditions"])
    constraint_count = sum(1 for c in all_defs if c["gold"]["constraints"])
    exception_count = sum(1 for c in all_defs if c["gold"]["exceptions"])
    all_three_empty = sum(
        1 for c in all_defs
        if not c["gold"]["conditions"]
        and not c["gold"]["constraints"]
        and not c["gold"]["exceptions"])

    clause_all_wrong = [
        c for c in all_defs
        if all_four_wrong_for_gold(c["predictions"], "definition")
    ]
    first_all_wrong = []
    for record in first_def:
        clause = record["clauses"][0]
        key = (record["sample_id"], clause.get("clause_id"))
        case = case_map.get(key)
        if case and all_four_wrong_for_gold(case["predictions"], "definition"):
            first_all_wrong.append(case)

    shall_defs = [c for c in all_defs
                  if SHALL_RE.search(c["clause_text"])]
    shall_all_wrong = [
        c for c in shall_defs
        if all_four_wrong_for_gold(c["predictions"], "definition")
    ]

    apply_core = [c for c in case_map.values()
                  if "apply_family_core" in c.get("case_scopes", [])]
    apply_def = [c for c in apply_core if c["gold"]["modality"] == "definition"]
    apply_nondef = [c for c in apply_core if c["gold"]["modality"] != "definition"]

    overlapping_def_cases = []
    for case in all_defs:
        record = next(r for r in gold_records if r["sample_id"] == case["sample_id"])
        for other in record.get("clauses") or []:
            if other.get("clause_id") == case["clause_id"]:
                continue
            if span_overlap(case["clause_span"], other.get("clause_span") or {}) > 0:
                overlapping_def_cases.append(case)
                break

    predicate_marked = [
        c for c in all_defs
        if c["gold_action_presence"]["has_action"]
        and bool(c["gold_action_presence"]["predicate_markers"])
        and c["gold_action_presence"]["all_actions_within_clause"]
    ]

    per_arm_empty_action = {}
    for arm in ARMS:
        per_arm_empty_action[arm] = sum(
            1 for c in all_defs if not c["predictions"][arm].get("actions"))

    family_summary: dict[str, dict[str, Any]] = {}
    for family, pattern in SHALL_FAMILY_PATTERNS.items():
        members = [
            c for c in all_defs
            if c["gold"]["modality"] == "definition"
            and pattern.search(c["clause_text"])
        ]
        similar = [
            c for c in case_map.values()
            if c["gold"]["modality"] != "definition"
            and pattern.search(c["clause_text"])
        ]
        family_summary[family] = {
            "family": family,
            "definition_count": len(members),
            "definition_cases": members,
            "all_four_wrong_definition_count": sum(
                1 for c in members
                if all_four_wrong_for_gold(c["predictions"], "definition")),
            "similar_nondefinition": similar,
        }

    triggered_families = [k for k, v in family_summary.items()
                          if v["definition_count"] > 0]
    family_summary["_triggered_families"] = triggered_families

    return {
        "definition_clause_count": len(all_defs),
        "definition_sample_count": len({c["sample_id"] for c in all_defs}),
        "first_definition_sample_count": len(first_def),
        "definition_action_span_count": action_count,
        "definition_empty_action_count": empty_action,
        "definition_actor_count": actor_nonempty,
        "definition_condition_count": condition_count,
        "definition_constraint_count": constraint_count,
        "definition_exception_count": exception_count,
        "definition_all_three_empty_count": all_three_empty,
        "definition_all_four_wrong_count": len(clause_all_wrong),
        "first_definition_all_four_wrong_count": len(first_all_wrong),
        "shall_definition_count": len(shall_defs),
        "shall_definition_all_four_wrong_count": len(shall_all_wrong),
        "apply_core_count": len(apply_core),
        "apply_definition_count": len(apply_def),
        "apply_nondefinition_count": len(apply_nondef),
        "overlapping_definition_case_count": len(overlapping_def_cases),
        "predicate_marked_definition_count": len(predicate_marked),
        "per_arm_empty_action_count": per_arm_empty_action,
        "family_summary": family_summary,
        "definition_cases": all_defs,
        "apply_core_cases": apply_core,
        "apply_definition_cases": apply_def,
        "apply_nondefinition_cases": apply_nondef,
        "shall_definition_cases": shall_defs,
        "shall_all_four_wrong_cases": shall_all_wrong,
        "first_definition_all_four_wrong_cases": first_all_wrong,
        "overlapping_definition_cases": overlapping_def_cases,
    }


# ---------------------------------------------------------------------------
# Matrix rows
# ---------------------------------------------------------------------------

def case_row(case: Mapping[str, Any], analysis_group: str,
             row_role: str, adjudication_label: str = "",
             confidence: str = "", notes: str = "") -> dict[str, Any]:
    gold = case["gold"]
    preds = case["predictions"]
    return {
        "analysis_group": analysis_group,
        "row_role": row_role,
        "sample_id": case["sample_id"],
        "clause_id": case["clause_id"],
        "gold_modality": gold["modality"],
        "clause_text": case["clause_text"],
        "gold_action_count": len(gold["actions"]),
        "gold_action_texts": " || ".join(span_texts(gold["actions"])),
        "gold_condition_count": len(gold["conditions"]),
        "gold_constraint_count": len(gold["constraints"]),
        "gold_exception_count": len(gold["exceptions"]),
        "pred_A_modality": preds["A"].get("modality_label"),
        "pred_B_modality": preds["B"].get("modality_label"),
        "pred_C_modality": preds["C"].get("modality_label"),
        "pred_D_modality": preds["D"].get("modality_label"),
        "pred_A_action_count": len(preds["A"].get("actions") or []),
        "pred_B_action_count": len(preds["B"].get("actions") or []),
        "pred_C_action_count": len(preds["C"].get("actions") or []),
        "pred_D_action_count": len(preds["D"].get("actions") or []),
        "all_actions_within_clause": case["gold_action_presence"]["all_actions_within_clause"],
        "predicate_markers": ";".join(case["gold_action_presence"]["predicate_markers"]),
        "adjudication_label": adjudication_label,
        "confidence": confidence,
        "notes": notes,
    }


def build_matrix_rows(summary: Mapping[str, Any],
                      case_map: Mapping[tuple[str, str], Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # Primary target pairs.
    for sid in ("estg_000505", "estg_000509"):
        case = case_map.get((sid, "c2"))
        if case:
            rows.append(case_row(case, "pair_estg_000505_vs_estg_000509",
                                 "target", "POTENTIAL_GOLD_INCONSISTENCY",
                                 "high", PAIR_505_509_NOTES["question_3"]))
    for sid in ("estg_000136", "estg_000812"):
        case = case_map.get((sid, "c1"))
        if case:
            rows.append(case_row(case, "pair_shall_be_determined",
                                 "target", "CONTEXTUALLY_EXPLAINABLE",
                                 "medium-high", PAIR_DETERMINED_NOTES["interpretation"]))
    for case in summary["apply_core_cases"]:
        review = APPLY_REVIEW.get((case["sample_id"], case["clause_id"]), {})
        rows.append(case_row(
            case, "apply_family_core", "target",
            review.get("judgment", "UNCLASSIFIED"),
            review.get("confidence", ""),
            f"{review.get('dimension', '')}; {review.get('why', '')}".strip("; ")))
    for case in summary["shall_definition_cases"]:
        family = classify_shall_family(case["clause_text"]) or "other"
        rows.append(case_row(
            case, "shall_definition_family", family,
            "DEFINITIONAL_SHALL", "high",
            "Gold definition containing shall; all four arms predicted non-definition."))
    for family, info in summary["family_summary"].items():
        if family.startswith("_"):
            continue
        for case in info["similar_nondefinition"]:
            rows.append(case_row(
                case, "shall_family_similar_nondefinition", family,
                "NON_DEFINITION_SURFACE_PARALLEL", "medium",
                "Non-definition clause matching the same shall-family surface pattern."))
    for case in summary["definition_cases"]:
        rows.append(case_row(
            case, "definition_action_presence", "gold_definition",
            "STABLE_ACTION_PRESENCE" if case["gold_action_presence"]["has_action"] else "EMPTY",
            "high" if case["gold_action_presence"]["has_action"] else "low",
            "Gold definition action-presence audit."))
    return rows


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def render_case_detail(case: Mapping[str, Any]) -> str:
    lines = [
        f"### `{case['sample_id']}` {case['clause_id']}",
        "",
        f"- Source text: `{md_escape(case['source_text'])}`",
        f"- Clause text: `{md_escape(case['clause_text'])}`",
        f"- Context previous: `{md_escape(case['context']['prev_clause_text'])}`",
        f"- Context next: `{md_escape(case['context']['next_clause_text'])}`",
        "",
        "Gold six fields:",
        "",
        json_block(case["gold"]),
        "",
        "Clause segmentation:",
        "",
        md_table(
            ["clause_id", "modality", "clause_span", "action_texts"],
            [[c.get("clause_id"), c.get("modality"),
              c.get("clause_span", {}).get("text", ""),
              " || ".join(c.get("action_texts") or [])]
             for c in case["clause_segmentation"]]),
        "",
        "A/B/C/D predictions:",
        "",
        md_table(
            ["Arm", "modality", "modality_evidence", "actions",
             "conditions", "constraints", "exceptions"],
            [[arm,
              case["predictions"][arm].get("modality_label"),
              " || ".join(span_texts(case["predictions"][arm].get("modality_evidence"))),
              " || ".join(span_texts(case["predictions"][arm].get("actions"))),
              " || ".join(span_texts(case["predictions"][arm].get("conditions"))),
              " || ".join(span_texts(case["predictions"][arm].get("constraints"))),
              " || ".join(span_texts(case["predictions"][arm].get("exceptions")))]
             for arm in ARMS]),
        "",
    ]
    return "\n".join(lines)


def render_adjudication_report(data: Mapping[str, Any]) -> str:
    summary = data["summary"]
    case_map = data["case_map"]
    lines: list[str] = []
    lines.append("# SEP-C3 Definition-Clause Adjudication v1")
    lines.append("")
    lines.append("- Task: Definition-Clause Adjudication & Prompt-Design Gate")
    lines.append("- Role: evidence analyst / annotation-semantics reviewer / engineering assistant")
    lines.append("- New BPC / LLM / API calls: **0**")
    lines.append("- Prompt modifications: **none**")
    lines.append("- Gold modifications: **none**")
    lines.append("- Action: adjudicate modality/action presence only; no Prompt design.")
    lines.append("")
    lines.append("## 1. Executive summary")
    lines.append("")
    lines.append(
        f"Gold contains **{summary['definition_clause_count']} definition clauses** "
        f"across **{summary['definition_sample_count']} samples**; "
        f"**{summary['first_definition_sample_count']} samples** have a definition as first clause. "
        f"All **{summary['definition_action_span_count']} action spans** occur in definition clauses; "
        f"empty-action definition clauses = **{summary['definition_empty_action_count']}**. "
        f"The four-arm non-definition errors remain **{summary['definition_all_four_wrong_count']}/39** "
        f"at clause level and **{summary['first_definition_all_four_wrong_count']}/29** at first-definition sample level. "
        f"All **{summary['shall_definition_count']}** definition clauses containing `shall` are non-definition in all four arms.")
    lines.append("")
    lines.append("The adjudication has two distinct outcomes:")
    lines.append("")
    lines.append("- **Definition action presence is stable.** All 39 definition clauses receive an action span, all 46 spans lie inside their clause spans, and every span contains a predicate marker. No exception or segmentation artefact changes presence.")
    lines.append("- **Definition modality is broad but not surface-decidable.** Legal fiction, classification, and scope/application are genuine Gold definition patterns. However, the `apply` family and the near-identical `shall be assumed` pair show that `shall` cannot be interpreted as definition or deontic from surface form alone. The strongest unresolved case is `estg_000505 c2` vs `estg_000509 c2`.")
    lines.append("")
    lines.append("## 2. Corpus and method")
    lines.append("")
    lines.append(md_table(
        ["Item", "Value"],
        [["Gold definition clauses", summary["definition_clause_count"]],
         ["Definition samples (any position)", summary["definition_sample_count"]],
         ["First-definition samples", summary["first_definition_sample_count"]],
         ["Definition action spans", summary["definition_action_span_count"]],
         ["Definition clauses with empty action", summary["definition_empty_action_count"]],
         ["Definition clauses with actor", summary["definition_actor_count"]],
         ["Definition clauses with condition", summary["definition_condition_count"]],
         ["Definition clauses with constraint", summary["definition_constraint_count"]],
         ["Definition clauses with exception", summary["definition_exception_count"]],
         ["Definition clauses with condition/constraint/exception all empty",
          summary["definition_all_three_empty_count"]],
         ["Definition clauses non-definition in all four arms",
          summary["definition_all_four_wrong_count"]],
         ["First-definition samples non-definition in all four arms",
          summary["first_definition_all_four_wrong_count"]],
         ["Definition clauses containing shall", summary["shall_definition_count"]],
         ["Shall-definition clauses non-definition in all four arms",
          summary["shall_definition_all_four_wrong_count"]]]))
    lines.append("")
    lines.append("Sources: frozen Gold, persisted A/B/C/D `sep_c3_targeted_refinement_v1` canonical predictions, and the existing E/S prompt modules. No API was called and no new experiment was started.")
    lines.append("")
    lines.append("## 3. `estg_000505 c2` vs `estg_000509 c2`")
    lines.append("")
    for sid in ("estg_000505", "estg_000509"):
        case = case_map[(sid, "c2")]
        lines.append(render_case_detail(case))
    lines.append("### Q1-Q3 adjudication")
    lines.append("")
    lines.append(f"**Q1 — Is there enough semantic/contextual difference?** {PAIR_505_509_NOTES['question_1']}")
    lines.append("")
    lines.append(f"**Q2 — If yes, what is the difference?** {PAIR_505_509_NOTES['question_2']}")
    lines.append("")
    lines.append(f"**Q3 — Marking.** `{PAIR_505_509_NOTES['question_3']}`. Gold is not modified.")
    lines.append("")
    lines.append("## 4. Apply / applies family")
    lines.append("")
    apply_rows = summary["apply_core_cases"]
    lines.append(
        f"Core active `apply/applies` family: **{summary['apply_core_count']} clauses**, "
        f"**{summary['apply_definition_count']} definition** and "
        f"**{summary['apply_nondefinition_count']} non-definition**. "
        "The table below keeps the full clause and Gold action; the analytical question is whether a stable semantic difference exists.")
    lines.append("")
    table_rows = []
    for case in sorted(apply_rows, key=lambda c: (c["gold"]["modality"] != "definition", c["sample_id"], c["clause_id"])):
        review = APPLY_REVIEW.get((case["sample_id"], case["clause_id"]), {})
        context_bits = []
        if case["context"]["prev_clause_text"]:
            context_bits.append("prev: " + md_escape(case["context"]["prev_clause_text"], 70))
        if case["context"]["next_clause_text"]:
            context_bits.append("next: " + md_escape(case["context"]["next_clause_text"], 70))
        table_rows.append([
            case["sample_id"], case["clause_id"], case["clause_text"],
            " || ".join(context_bits) or "—",
            case["gold"]["modality"],
            " || ".join(span_texts(case["gold"]["actions"])),
            review.get("why", ""), review.get("confidence", ""),
        ])
    lines.append(md_table(
        ["Sample", "Clause", "Full clause", "Context (prev / next)", "Gold modality",
         "Gold action", "Why definition/non-definition?", "Confidence"],
        table_rows))
    lines.append("")
    lines.append("Observations that are merely analytical dimensions, not Prompt rules:")
    lines.append("")
    lines.append("- `may apply` in `estg_000145 c1` is a **different verb sense** (submit an application); it is not the applicability predicate and should not be used as a contrastive definition/obligation case.")
    lines.append("- `does not apply` is definitional in all Gold examples (`estg_000083 c1`, `estg_000218 c1`, `estg_000800 c1`): it defines scope/exception, not conduct.")
    lines.append("- `applies/applies to` is definitional in `estg_000071 c1`, `estg_000164 c1`, and `estg_000209 c2`.")
    lines.append("- `shall apply` is definitional in `estg_000664 c1` but obligation in `estg_000056 c1`, `estg_000128 c2`, and `estg_000208 c2`.")
    lines.append("- `the following applies` is definitional in `estg_000164 c1` but obligation in `estg_000306 c1`; this near-identical pair prevents a stable surface or introductory statement rule.")
    lines.append("")
    lines.append("**Conclusion:** a semantic distinction can be *described* (scope/classification statement vs deontic application command), but it is **not stably operationalized by Gold** in the current apply family. Mark the apply-family modality boundary `NEEDS_GOLD_ADJUDICATION`.")
    lines.append("")
    lines.append("## 5. `shall be determined`: `estg_000136` vs `estg_000812`")
    lines.append("")
    for sid in ("estg_000136", "estg_000812"):
        case = case_map[(sid, "c1")]
        lines.append(render_case_detail(case))
    lines.append("### Adjudication")
    lines.append("")
    lines.append(f"{PAIR_DETERMINED_NOTES['interpretation']}")
    lines.append("")
    lines.append(f"Caveat: {PAIR_DETERMINED_NOTES['caveat']}")
    lines.append("")
    lines.append(f"Gold inconsistency: **{PAIR_DETERMINED_NOTES['gold_inconsistency']}**. The modality difference can be explained by argument structure/context, but only as a single-pair interpretation.")
    lines.append("")
    lines.append("## 6. The 15 Gold-definition clauses containing `shall`")
    lines.append("")
    lines.append(md_table(
        ["Family", "Gold def count", "All-four-arm wrong", "Sample IDs", "Action spans", "Superficially similar non-definition"],
        [[family,
          info["definition_count"],
          info["all_four_wrong_definition_count"],
          ", ".join(f"{c['sample_id']} {c['clause_id']}" for c in info["definition_cases"]),
          " || ".join(text for c in info["definition_cases"] for text in span_texts(c["gold"]["actions"])) or "—",
          ", ".join(f"{c['sample_id']} {c['clause_id']} ({c['gold']['modality']})"
                    for c in info["similar_nondefinition"]) or "none in Gold corpus"]
         for family, info in summary["family_summary"].items()
         if not family.startswith("_") and info["definition_count"] > 0]))
    lines.append("")
    lines.append("### Common semantics of the 15 `shall` definitions")
    lines.append("")
    lines.append("The 15 clauses share a common annotation semantics: **`shall` marks legal status, identity, classification, membership, scope, or a computational/legal fiction rather than a required act of a duty-bearer.**")
    lines.append("")
    lines.append("- All 15 have `actors = []` in Gold: no explicit duty-bearer is annotated.")
    lines.append("- The action is a stative/copular/legal-fiction predicate (`include`, `be deemed`, `be treated`, `constitute`, `apply`, `be assumed`, `be determined`, `be income`), not an action performed by an actor.")
    lines.append("- The clause typically equates X with Y, classifies X as Y, or extends the scope of an existing classification/rule.")
    lines.append("- `shall` can be inside the action span (`shall include`, `shall be deemed`) or immediately before it; Gold action semantics consistently treats the definitional predicate as the action.")
    lines.append("")
    lines.append("This is a semantic commonality, not a lexical test: `shall + verb` also occurs in deontic clauses.")
    lines.append("")
    lines.append("### Is there an annotation-level principle separating definitional `shall` from deontic `shall`?")
    lines.append("")
    lines.append("A **directional** principle exists: definitional `shall` is stative/classificatory/legal-fictional and lacks an actor/duty-bearer; deontic `shall` imposes required conduct or a required method of application on a duty-bearer. But it is **not yet stable for `shall apply`, `shall be assumed`, and `shall be determined`**, because these surfaces occur in both Gold classes. The apply family is the clearest blocker.")
    lines.append("")
    lines.append("## 7. Definition modality candidate principle review")
    lines.append("")
    lines.append("Candidate principle: *Gold definition modality is broader than explicit `means`; it includes legal fiction, classification, and some scope/application statements.*")
    lines.append("")
    lines.append(md_table(
        ["Review dimension", "Evidence"],
        [["Supporting cases",
          "39 definition clauses; explicit `means` = 1; `shall` definitions = 15; legal-fiction/deeming in 6 `shall be deemed` + 2 `shall be treated`; classification/constitution; 7 apply-family definitions."],
         ["Counterexamples / limits",
          "`shall` is overwhelmingly deontic elsewhere; active apply family is 7 definition vs 5 non-definition; `shall be assumed` pair is mixed; `shall be determined` pair is mixed."],
         ["Unresolved pairs",
          "`estg_000505 c2` vs `estg_000509 c2`; `the following applies` `estg_000164 c1` vs `estg_000306 c1`; `shall apply` `estg_000664 c1` vs `estg_000056/128/208`; `shall be determined` `estg_000136` vs `estg_000812`."],
         ["Consistency",
          "Descriptive coverage of definition is internally consistent; a surface-based classifier is not. The apply family and the 505/509 pair require Gold adjudication before a clean Prompt rule could be written."]],
        ))
    lines.append("")
    lines.append("**Status:** `MOSTLY_STABLE_WITH_EXCEPTIONS` for descriptive coverage of Gold definition; the apply-family boundary itself is `GOLD_ADJUDICATION_REQUIRED`.")
    lines.append("")
    lines.append("## 8. Definition action presence: final confirmation")
    lines.append("")
    lines.append(md_table(
        ["Question", "Result", "Evidence / caveat"],
        [["Any exception to 39/39?",
          f"No: empty-action definition clauses = {summary['definition_empty_action_count']}/39.",
          f"{summary['definition_action_span_count']} Gold action spans; all definition clauses have at least one."],
         ["Could segmentation create the appearance?",
          "No for presence; yes for exact boundaries.",
          f"{summary['overlapping_definition_case_count']} definition cases have an overlapping sibling clause span, so Gold segmentation is not always a strict partition; however every definition action remains inside its own clause span and is recorded in that clause's action array."],
         ["Do action spans contain a definitional predicate?",
          f"Yes: {summary['predicate_marked_definition_count']}/39 definition cases have action spans with predicate markers and all actions inside the clause span.",
          "Markers include is/are/be, means, include, apply/applies, deemed, treated, determined, constitute, assumed, eligible, occurs, runs, leaves, works, etc."],
         ["Do actor/condition/constraint affect action presence?",
          "No.",
          f"Actors non-empty in {summary['definition_actor_count']}/39; conditions non-empty in {summary['definition_condition_count']}/39; constraints non-empty in {summary['definition_constraint_count']}/39; none removes the action."],
         ["Any suspected forced annotation?",
          "No forced empty-to-nonempty case found.",
          "Boundary outliers remain (`estg_000020`, `estg_000083 c2`, `estg_000112`, `estg_000283`), but each still contains a predicate; they affect exact boundary, not presence."]],
        ))
    lines.append("")
    lines.append("**Upgrade:** `Definition clauses still receive an action span representing the definitional predicate.`")
    lines.append("")
    lines.append("Status: **`STABLE_ANNOTATION_PRINCIPLE`** (presence only; exact boundary remains unresolved).")
    lines.append("")
    lines.append("## 9. Gold inconsistency findings")
    lines.append("")
    lines.append(md_table(
        ["Case", "Finding", "Status"],
        [["`estg_000505 c2` vs `estg_000509 c2`",
          "Near-identical deeming/computational fiction; Gold labels obligation vs definition with no sufficient contextual semantic difference.",
          "`POTENTIAL_GOLD_INCONSISTENCY`"],
         ["apply family",
          "Same active predicate (`apply/applies`) receives both definition and obligation labels; `the following applies` is mixed across near-identical clauses.",
          "`GOLD_SEMANTICS_UNCLEAR` / `NEEDS_GOLD_ADJUDICATION`"],
         ["`estg_000136` vs `estg_000812`",
          "Same `shall be determined` surface; argument structure supports a context-based distinction (`by` identity vs `in accordance with` method).",
          "Contextually explainable; no inconsistency marked"],
         ["Other definition-like lexical candidates",
          "14 broad candidates were previously surfaced, but not asserted to be missed definitions.",
          "Not treated as Gold inconsistency in this round"]],
        ))
    lines.append("")
    lines.append("No new confirmed Gold inconsistency beyond the previously suspected `estg_000505 c2` / `estg_000509 c2` pair was found. The apply family remains an adjudication issue, not an automatically corrected annotation.")
    lines.append("")
    lines.append("## 10. Preserved limitations")
    lines.append("")
    lines.append("- Exact action complement/subordinate-clause boundaries are not solved.")
    lines.append("- Condition/constraint boundary semantics are only summarized, not adjudicated.")
    lines.append("- No Prompt wording, example wording, schema, Gold annotation, or experiment arm is changed.")
    lines.append("- The analysis remains zero-API.")
    lines.append("")
    return "\n".join(lines)


def render_gate_report(data: Mapping[str, Any]) -> str:
    summary = data["summary"]
    rows = [
        ["definition modality missing guidance",
         "Stable: 20/29 first-def and 25/39 clauses all-four-arm wrong; 15/15 shall definitions wrong.",
         "Mostly clear for semantic coverage; not clear at apply-family boundary.",
         "S2 missing definition semantics; E4 only explicit means.",
         "READY_FOR_PROMPT_DESIGN (core semantic coverage only; not apply-family boundary)"],
        ["E4 empty-action conflict",
         "Stable: 0/39 Gold definitions have empty action.",
         "Clear.",
         "E4 explicitly says actions empty; direct conflict.",
         "READY_FOR_PROMPT_DESIGN (design must not teach empty definition action)"],
        ["S11 action-empty permissiveness",
         "Stable: 39/39 Gold definitions have action; aligned predicted empty-action counts A=10, B=13, C=12, D=12.",
         "Clear.",
         "S11 says a definition clause may have no actions; unsupported as a design cue.",
         "READY_FOR_PROMPT_DESIGN (remove/repair permissive cue)"],
        ["S8 action-boundary conflict",
         "Locally stable: 44/46 spans no condition/constraint/exception overlap; one direct counterexample.",
         "Not clear at exact boundary; estg_000020 is an outlier.",
         "S8 says action ends where condition/constraint begins; direct local conflict at estg_000020 c1.",
         "NEEDS_GOLD_ADJUDICATION (preserve outlier; do not redesign boundary now)"],
        ["apply-family modality ambiguity",
         "Stable as an ambiguity: 7 definition vs 5 non-definition active apply/applies clauses.",
         "No stable Gold discriminator; near-identical `the following applies` mixed.",
         "S2 has no definition semantics; same surface receives both labels.",
         "NEEDS_GOLD_ADJUDICATION"],
        ["condition/constraint boundary",
         "Partial: 28/39 definitions have each; E4 empty fields are under-representative.",
         "Exact boundary not clear in this round.",
         "Separate S5/S6/R_C boundary work exists but is not adjudicated here.",
         "DO_NOT_TOUCH (out of scope; no boundary conclusion)"],
        ["actor R_A",
         "Stable for ordinary definitions: 37/39 definitions have empty actors; only 2 relational definitions name an actor.",
         "Mostly clear; exception pattern visible.",
         "E4 empty-actor pattern is mostly compatible; no new conflict.",
         "DO_NOT_TOUCH (R_A not modified this round)"],
        ["exception",
         "Partial: 5/39 definitions have an exception; 34/39 empty.",
         "No definition-specific exception conflict established.",
         "E3/E4 not directly contradicted by the definition corpus.",
         "DO_NOT_TOUCH (no new evidence requiring prompt change)"],
    ]
    lines = [
        "# SEP-C3 Definition Prompt Design Gate",
        "",
        "- New API / LLM calls: **0**",
        "- Prompt changes: **none**",
        "- Gold changes: **none**",
        "- This is a gate, not a Prompt design.",
        "",
        "## Gate matrix",
        "",
        md_table(
            ["Candidate issue", "Evidence stable?", "Gold clear?",
             "Existing guidance conflict/missing?", "Ready for GPT design?"],
            rows),
        "",
        "## Interpretation of statuses",
        "",
        "- `READY_FOR_PROMPT_DESIGN`: the evidence is stable and clear enough for a later Prompt design review. It does **not** authorize wording in this round.",
        "- `NEEDS_GOLD_ADJUDICATION`: Prompt design should not resolve the boundary; Gold/annotation semantics need a separate human decision first.",
        "- `DO_NOT_TOUCH`: no Prompt change should be made from the current evidence; this is not a judgment that current wording is perfect.",
        "- `INSUFFICIENT_EVIDENCE`: not used in this matrix.",
        "",
        "## Gate conclusions",
        "",
        "- The definition modality *coverage* problem is ready for a later design review at the semantic level: legal fiction, classification, and scope/application are genuine definition patterns, and 15/15 `shall` definitions fail all four arms.",
        "- The action-presence problem is ready: E4 and S11 both mislead toward empty definition actions while Gold has 39/39 non-empty actions.",
        "- The apply-family and exact-boundary issues are not ready. In particular, `estg_000505 c2` / `estg_000509 c2` remains a `POTENTIAL_GOLD_INCONSISTENCY`, and `the following applies` is mixed across near-identical clauses.",
        "- This gate deliberately leaves condition/constraint boundary, actor R_A, and exception untouched.",
        "",
    ]
    return "\n".join(lines)


def render_e4_report(data: Mapping[str, Any]) -> str:
    summary = data["summary"]
    lines = [
        "# SEP-C3 E4 Final Diagnosis",
        "",
        "- New API / LLM calls: **0**",
        "- E4 was **not modified**.",
        "- This diagnosis is evidence-only; no replacement example is proposed.",
        "",
        "Current E4 definition component: `definition; evidence \"means\"; actors and actions empty`.",
        "",
        "## Component table",
        "",
        md_table(
            ["E4 component", "Gold support", "Counterexamples", "Status"],
            [[row["component"], row["gold_support"], row["counterexamples"], row["status"]]
             for row in E4_COMPONENT_ROWS]),
        "",
        "## E4 whole-example diagnosis",
        "",
        f"- Empty-action component compatibility with Gold: **0/{summary['definition_clause_count']}**.",
        "- The label `definition` itself is correct.",
        "- `means` is a valid but narrow trigger: only 1/39 definition clauses use it.",
        "- Empty actors is broadly compatible (37/39) but not universal.",
        "- Empty conditions and constraints are under-representative: 28/39 definitions have each.",
        "- Empty exceptions is the majority pattern (34/39).",
        "",
        "**Overall status:** `CONFLICTS_WITH_GOLD` because the example teaches an empty definition action while Gold gives every definition an action span.",
        "",
        "No alternative E4 example is supplied in this round.",
        "",
    ]
    return "\n".join(lines)


def render_s_report(data: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C3 S Definition-Guidance Diagnosis",
        "",
        "- New API / LLM calls: **0**",
        "- S rules were **not modified**.",
        "- This is an evidence diagnosis, not a rewrite.",
        "",
        md_table(
            ["Rule", "Diagnosis", "Supporting samples / evidence",
             "Counterexamples", "Confidence", "Details"],
            [[row["rule"], row["diagnosis"], row["supporting"],
              row["counterexamples"], row["confidence"], row["details"]]
             for row in S_DIAGNOSIS]),
        "",
        "## Status summary",
        "",
        "- **S2:** `MISSING_DEFINITION_MODALITY_GUIDANCE` — confirmed.",
        "- **S11:** `MISLEADING_PERMISSIVE_GUIDANCE` — confirmed as an unsupported permissive design cue, while noting the logical-possibility caveat.",
        "- **S8:** `LOCALLY_CONFLICTING_ACTION_BOUNDARY_GUIDANCE` — confirmed locally by `estg_000020 c1`; exact boundary repair remains unresolved.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_analysis() -> dict[str, Any]:
    gold_records = load_gold_records()
    arms = load_arms()
    case_map, definition_cases = build_case_map(gold_records, arms)
    summary = build_summary(gold_records, arms, case_map, definition_cases)
    matrix_rows = build_matrix_rows(summary, case_map)
    return {
        "gold_records": gold_records,
        "arms": arms,
        "case_map": case_map,
        "definition_cases": definition_cases,
        "summary": summary,
        "matrix_rows": matrix_rows,
    }


def write_analysis(data: Mapping[str, Any]) -> list[Path]:
    summary = data["summary"]
    case_map = data["case_map"]
    outputs: list[Path] = []
    outputs.append(REPORT_DIR / "sep_c3_definition_adjudication_v1.md")
    write_text(outputs[-1], render_adjudication_report(data))
    outputs.append(REPORT_DIR / "sep_c3_definition_adjudication_cases.jsonl")
    write_jsonl(outputs[-1], sorted(
        case_map.values(), key=lambda c: (c["sample_id"], str(c["clause_id"]))))
    outputs.append(REPORT_DIR / "sep_c3_definition_modality_contrastive_matrix.csv")
    matrix_fields = [
        "analysis_group", "row_role", "sample_id", "clause_id", "gold_modality",
        "clause_text", "gold_action_count", "gold_action_texts",
        "gold_condition_count", "gold_constraint_count", "gold_exception_count",
        "pred_A_modality", "pred_B_modality", "pred_C_modality", "pred_D_modality",
        "pred_A_action_count", "pred_B_action_count", "pred_C_action_count",
        "pred_D_action_count", "all_actions_within_clause", "predicate_markers",
        "adjudication_label", "confidence", "notes",
    ]
    write_csv(outputs[-1], data["matrix_rows"], matrix_fields)
    outputs.append(REPORT_DIR / "sep_c3_definition_prompt_design_gate.md")
    write_text(outputs[-1], render_gate_report(data))
    outputs.append(REPORT_DIR / "sep_c3_E4_final_diagnosis.md")
    write_text(outputs[-1], render_e4_report(data))
    outputs.append(REPORT_DIR / "sep_c3_S_definition_guidance_diagnosis.md")
    write_text(outputs[-1], render_s_report(data))
    return outputs


def main() -> int:
    data = build_analysis()
    outputs = write_analysis(data)
    for path in outputs:
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
