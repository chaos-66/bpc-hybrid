# -*- coding: utf-8 -*-
"""Gold-driven semantic-boundary analysis for SEP-C3 Stage 2.

Zero-API analysis.  Reads frozen Gold, formal input, and persisted canonical
predictions.  Writes only derived analysis artefacts under outputs/reports/.
It never modifies Gold, prompts, raw predictions, parser, canonicalizer, or
evaluator.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.g04_coarse_view import build_coarse_view  # noqa: E402
from bpc_hybrid.stage2_sun_literal_overlap import _field_spans  # noqa: E402
import analyze_sep_c3_modular_paired_errors_v1 as paired  # noqa: E402

GOLD_PATH = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
INPUT_PATH = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
REPORT_DIR = ROOT / "outputs" / "reports"
TARGETED_DIR = ROOT / "outputs" / "development" / "sep_c3_targeted_refinement_v1"
MODULAR_V2_100 = (
    ROOT / "outputs" / "development" / "sep_c3_modular_ablation_v2" / "100"
    / "repeat-01" / "canonical_predictions.jsonl"
)
ARMS = ("A", "B", "C", "D")
SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")
PLURAL = {
    "actor": "actors",
    "action": "actions",
    "condition": "conditions",
    "constraint": "constraints",
    "exception": "exceptions",
}

# Descriptive lexical features only.  They are never used as the final
# semantic decision; they are emitted so a human can inspect contrasts.
FEATURE_PATTERNS: dict[str, re.Pattern[str]] = {
    "factual_applicability_trigger": re.compile(
        r"\b(?:if|where|insofar as|to the extent|upon|provided that|subject to|"
        r"in the case|in such case|only under)\b", re.IGNORECASE),
    "threshold_eligibility": re.compile(
        r"\b(?:at least|at most|up to|not exceed|more than|less than|"
        r"minimum|maximum|eligible|eligibility|available)\b", re.IGNORECASE),
    "threshold_regulated_action": re.compile(
        r"\b(?:up to|at least|at most|not exceed|more than|less than|"
        r"maximum|minimum)\b", re.IGNORECASE),
    "duration": re.compile(
        r"\b(?:year|years|month|months|week|weeks|day|days|hour|hours)\b",
        re.IGNORECASE),
    "deadline": re.compile(
        r"\b(?:before|within|no later than|by the end|expiry|expiration|"
        r"deadline|remainder)\b", re.IGNORECASE),
    "frequency": re.compile(
        r"\b(?:per|each|every|annually|monthly|weekly|daily|once a year|"
        r"installments?)\b", re.IGNORECASE),
    "quantity": re.compile(r"\b\d+(?:[.,]\d+)?\b", re.IGNORECASE),
    "percentage": re.compile(r"\b\d+(?:[.,]\d+)?\s*%|percent", re.IGNORECASE),
    "purpose": re.compile(
        r"\b(?:for the purpose|in order to|serves?|intended for|to ensure|"
        r"for the benefit|for determining)\b", re.IGNORECASE),
    "legal_reference": re.compile(
        r"\b(?:Section|Act|lit\.|no\.|paragraph|subsection|BGBl)\b",
        re.IGNORECASE),
    "manner_restriction": re.compile(
        r"\b(?:in accordance with|through|by|in such a way|in such a manner|"
        r"exclusively|only|on the basis of|according to)\b", re.IGNORECASE),
    "exception_like": re.compile(
        r"\b(?:unless|except|excluding|does not apply|with the exception|"
        r"apart from|even if)\b", re.IGNORECASE),
    "exclusivity": re.compile(
        r"\b(?:only|solely|exclusively|merely|in particular)\b", re.IGNORECASE),
}

MATRIX_ROWS = [
    ("factual_applicability_trigger", "factual applicability trigger",
     "condition"),
    ("threshold_eligibility", "threshold on eligibility", "condition"),
    ("threshold_regulated_action", "threshold on regulated action",
     "constraint"),
    ("duration", "duration", "either"),
    ("deadline", "deadline", "either"),
    ("frequency", "frequency", "constraint"),
    ("quantity", "quantity threshold", "either"),
    ("percentage", "percentage", "either"),
    ("purpose", "purpose limitation", "either"),
    ("legal_reference", "legal reference", "either"),
    ("manner_restriction", "manner restriction", "constraint"),
    ("exception_like", "exception-like condition", "either"),
    ("exclusivity", "exclusivity / exemplification", "constraint"),
]

E_EXAMPLES = {
    "E1": {
        "label": "unresolved subject pronoun",
        "modality": "permission",
        "actor": "present unresolved pronoun",
        "action": "present",
        "condition": "present simple if-clause",
        "constraint": "empty",
        "exception": "empty",
        "overlap": "none",
    },
    "E2": {
        "label": "passive clause, coordinated actions, two constraints",
        "modality": "obligation",
        "actor": "empty",
        "action": "two simple past participles",
        "condition": "empty",
        "constraint": "two disjoint time constraints",
        "exception": "empty",
        "overlap": "none",
    },
    "E3": {
        "label": "prohibition with exception",
        "modality": "prohibition",
        "actor": "present",
        "action": "present",
        "condition": "empty",
        "constraint": "empty",
        "exception": "present",
        "overlap": "none",
    },
    "E4": {
        "label": "definition plus obligation",
        "modality": "definition + obligation",
        "actor": "definition clause actor empty; obligation actor present",
        "action": "definition clause action empty; obligation action present",
        "condition": "empty",
        "constraint": "empty",
        "exception": "empty",
        "overlap": "none",
    },
    "E5": {
        "label": "condition containing nested constraint",
        "modality": "obligation",
        "actor": "present",
        "action": "present",
        "condition": "present",
        "constraint": "one nested time phrase",
        "exception": "empty",
        "overlap": "condition contains constraint",
    },
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def span_relation(a: Mapping[str, Any], b: Mapping[str, Any]) -> str:
    """Return geometry relation, not a semantic adjudication."""
    start = max(int(a["start"]), int(b["start"]))
    end = min(int(a["end"]), int(b["end"]))
    if start >= end:
        return "disjoint"
    if int(a["start"]) == int(b["start"]) and int(a["end"]) == int(b["end"]):
        return "exact"
    if int(a["start"]) <= int(b["start"]) and int(b["end"]) <= int(a["end"]):
        return "contains"
    if int(b["start"]) <= int(a["start"]) and int(a["end"]) <= int(b["end"]):
        return "contained_by"
    return "partial_overlap"


def text_without_span(source_text: str, outer: Mapping[str, Any],
                      inner: Mapping[str, Any]) -> str:
    """Remove one absolute span from an outer span, preserving the rest."""
    pieces = []
    if int(outer["start"]) < int(inner["start"]):
        pieces.append(source_text[int(outer["start"]):int(inner["start"])])
    if int(inner["end"]) < int(outer["end"]):
        pieces.append(source_text[int(inner["end"]):int(outer["end"])])
    return "".join(pieces).strip()


def feature_flags(text: str) -> list[str]:
    return sorted(key for key, pattern in FEATURE_PATTERNS.items()
                  if pattern.search(text or ""))


def compact_span(span: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "text": span.get("text"),
        "start": span.get("start"),
        "end": span.get("end"),
        "normalized": span.get("normalized"),
        "descriptive_features": feature_flags(str(span.get("text") or "")),
    }


def build_gold_cases(gold_records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in gold_records:
        source_text = str(record.get("approved_text_en") or "")
        for clause_index, clause in enumerate(record.get("clauses") or []):
            conditions = list(clause.get("conditions") or [])
            constraints = list(clause.get("constraints") or [])
            exceptions = list(clause.get("exceptions") or [])
            actors = list(clause.get("actors") or [])
            actions = list(clause.get("actions") or [])

            nested_pairs: list[dict[str, Any]] = []
            for condition in conditions:
                for constraint in constraints:
                    relation = span_relation(condition, constraint)
                    if relation == "disjoint":
                        continue
                    if relation == "contains":
                        condition_remaining = text_without_span(
                            source_text, condition, constraint)
                        constraint_remaining = None
                    elif relation == "contained_by":
                        condition_remaining = None
                        constraint_remaining = text_without_span(
                            source_text, constraint, condition)
                    elif relation == "exact":
                        condition_remaining = ""
                        constraint_remaining = ""
                    else:
                        condition_remaining = text_without_span(
                            source_text, condition, constraint)
                        constraint_remaining = text_without_span(
                            source_text, constraint, condition)
                    nested_pairs.append({
                        "relation": relation,
                        "condition": compact_span(condition),
                        "constraint": compact_span(constraint),
                        "condition_remaining_text": condition_remaining,
                        "constraint_remaining_text": constraint_remaining,
                        "constraint_relative_to_condition": (
                            "inside" if relation in ("contains", "exact")
                            else "contains_condition" if relation == "contained_by"
                            else "partial_overlap"
                        ),
                        "manual_review_required": True,
                        "manual_review_reason": (
                            "Geometry proves co-labeling/nesting but cannot decide "
                            "whether the inner phrase has an independent restrictive "
                            "role or is a component of the applicability proposition."
                        ),
                    })

            condition_only = bool(conditions) and not nested_pairs
            outside_constraints = [
                c for c in constraints
                if not any(span_relation(c, co) != "disjoint"
                           for co in conditions)
            ]
            tags: list[str] = []
            if condition_only:
                tags.append("A")
            if nested_pairs:
                tags.append("B")
            if outside_constraints:
                tags.append("C")
            if ((len(conditions) >= 2 and len(constraints) >= 2)
                    or (nested_pairs and outside_constraints)
                    or (len(conditions) >= 2 and nested_pairs)
                    or (len(constraints) >= 2 and nested_pairs)):
                tags.append("D")
            partial = any(p["relation"] == "partial_overlap"
                          for p in nested_pairs)
            mixed = bool(nested_pairs and outside_constraints)
            if partial or mixed:
                tags.append("E")

            semantic_cues_in_condition_only = any(
                feature_flags(str(co.get("text") or ""))
                for co in conditions if condition_only
            )
            manual = bool(nested_pairs) or "E" in tags or (
                condition_only and semantic_cues_in_condition_only)
            reasons = []
            if nested_pairs:
                reasons.append(
                    "nested/overlapping condition-constraint pair: independent "
                    "restrictive role is a semantic judgment")
            if "E" in tags:
                reasons.append(
                    "partial overlap or mixed inside/outside relations: geometry "
                    "alone is insufficient")
            if condition_only and semantic_cues_in_condition_only:
                reasons.append(
                    "condition-only span contains descriptive threshold/time/"
                    "legal/purpose/manner/exclusivity cues; not a lexical decision")

            if not tags:
                continue

            rows.append({
                "sample_id": record.get("sample_id"),
                "clause_id": clause.get("clause_id"),
                "clause_index": clause_index,
                "source_text": source_text,
                "clause_span": compact_span(clause.get("clause_span") or {}),
                "modality": clause.get("modality"),
                "case_types": tags,
                "condition_only": condition_only,
                "nested_condition_constraint": bool(nested_pairs),
                "constraint_outside_condition": bool(outside_constraints),
                "multiple_conditions": len(conditions) >= 2,
                "multiple_constraints": len(constraints) >= 2,
                "actors": [compact_span(s) for s in actors],
                "actions": [compact_span(s) for s in actions],
                "conditions": [compact_span(s) for s in conditions],
                "constraints": [compact_span(s) for s in constraints],
                "exceptions": [compact_span(s) for s in exceptions],
                "nested_pairs": nested_pairs,
                "constraints_outside_condition": [
                    compact_span(s) for s in outside_constraints],
                "manual_review_required": manual,
                "manual_review_reasons": reasons,
            })
    return rows


def actual_overlap_summary(gold_records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    clause_pair_relations: Counter = Counter()
    clause_pair_samples: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    sample_pair_relations: Counter = Counter()
    sample_pair_samples: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    same_field: Counter = Counter()
    exact_cross_field: Counter = Counter()

    for record in gold_records:
        sample_id = str(record.get("sample_id"))
        all_spans: list[tuple[str, Mapping[str, Any]]] = []
        for clause in record.get("clauses") or []:
            spans: list[tuple[str, Mapping[str, Any]]] = []
            for field in SPAN_FIELDS:
                for span in clause.get(PLURAL[field]) or []:
                    spans.append((field, span))
                    all_spans.append((field, span))
            for i, (left_field, left) in enumerate(spans):
                for right_field, right in spans[i + 1:]:
                    relation = span_relation(left, right)
                    if relation == "disjoint":
                        continue
                    if left_field == right_field:
                        same_field[left_field] += 1
                        continue
                    key = tuple(sorted((left_field, right_field)))
                    clause_pair_relations[key] += 1
                    clause_pair_samples[key].add(sample_id)
                    if relation == "exact":
                        exact_cross_field[key] += 1
        for i, (left_field, left) in enumerate(all_spans):
            for right_field, right in all_spans[i + 1:]:
                if left_field == right_field:
                    continue
                if span_relation(left, right) == "disjoint":
                    continue
                key = tuple(sorted((left_field, right_field)))
                sample_pair_relations[key] += 1
                sample_pair_samples[key].add(sample_id)

    pair = tuple(sorted(("condition", "constraint")))
    return {
        "clause_level_pair_counts": {
            "::".join(k): v for k, v in sorted(clause_pair_relations.items())},
        "clause_level_pair_samples": {
            "::".join(k): sorted(v) for k, v in sorted(clause_pair_samples.items())},
        "sample_level_pair_counts": {
            "::".join(k): v for k, v in sorted(sample_pair_relations.items())},
        "sample_level_pair_samples": {
            "::".join(k): sorted(v) for k, v in sorted(sample_pair_samples.items())},
        "clause_level_condition_constraint_pairs": clause_pair_relations[pair],
        "clause_level_condition_constraint_samples": sorted(
            clause_pair_samples[pair]),
        "sample_level_condition_constraint_pairs": sample_pair_relations[pair],
        "sample_level_condition_constraint_samples": sorted(
            sample_pair_samples[pair]),
        "same_field_overlap_counts": dict(same_field),
        "exact_cross_field_overlap_counts": {
            "::".join(k): v for k, v in sorted(exact_cross_field.items())},
    }


def merged_span_overlap_summary(gold_records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts: Counter = Counter()
    samples: list[str] = []
    for record in gold_records:
        conditions: list[Mapping[str, Any]] = []
        constraints: list[Mapping[str, Any]] = []
        for clause in record.get("clauses") or []:
            conditions.extend(clause.get("conditions") or [])
            constraints.extend(clause.get("constraints") or [])
        if not conditions and not constraints:
            counts["neither"] += 1
            continue
        if conditions and not constraints:
            counts["condition_only_sample"] += 1
            continue
        if constraints and not conditions:
            counts["constraint_only_sample"] += 1
            continue
        condition_hull = {
            "start": min(int(s["start"]) for s in conditions),
            "end": max(int(s["end"]) for s in conditions),
        }
        constraint_hull = {
            "start": min(int(s["start"]) for s in constraints),
            "end": max(int(s["end"]) for s in constraints),
        }
        relation = span_relation(condition_hull, constraint_hull)
        if relation == "disjoint":
            counts["both_present_no_hull_overlap"] += 1
        else:
            counts["hull_overlap"] += 1
            counts[f"hull_{relation}"] += 1
            samples.append(str(record.get("sample_id")))
    return {"counts": dict(counts), "overlap_samples": samples}


def feature_matrix(gold_records: Sequence[Mapping[str, Any]],
                   cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    condition_span_samples: defaultdict[str, set[str]] = defaultdict(set)
    constraint_span_samples: defaultdict[str, set[str]] = defaultdict(set)
    nested_samples: defaultdict[str, set[str]] = defaultdict(set)
    outside_samples: defaultdict[str, set[str]] = defaultdict(set)
    condition_only_samples: defaultdict[str, set[str]] = defaultdict(set)
    feature_examples: defaultdict[str, list[str]] = defaultdict(list)
    opposite_examples: defaultdict[str, list[str]] = defaultdict(list)

    for record in gold_records:
        sid = str(record.get("sample_id"))
        conds: list[Mapping[str, Any]] = []
        cons: list[Mapping[str, Any]] = []
        for clause in record.get("clauses") or []:
            conds.extend(clause.get("conditions") or [])
            cons.extend(clause.get("constraints") or [])
        for condition in conds:
            for feature in feature_flags(str(condition.get("text") or "")):
                condition_span_samples[feature].add(sid)
                if len(feature_examples[feature]) < 4:
                    feature_examples[feature].append(sid)
        for constraint in cons:
            for feature in feature_flags(str(constraint.get("text") or "")):
                constraint_span_samples[feature].add(sid)
                if len(opposite_examples[feature]) < 4:
                    opposite_examples[feature].append(sid)

    for case in cases:
        sid = str(case["sample_id"])
        for pair in case.get("nested_pairs") or []:
            for feature in pair["constraint"].get("descriptive_features") or []:
                nested_samples[feature].add(sid)
        for constraint in case.get("constraints_outside_condition") or []:
            for feature in constraint.get("descriptive_features") or []:
                outside_samples[feature].add(sid)
        if case.get("condition_only"):
            for condition in case.get("conditions") or []:
                for feature in condition.get("descriptive_features") or []:
                    condition_only_samples[feature].add(sid)

    rows: list[dict[str, Any]] = []
    for feature, situation, expected_field in MATRIX_ROWS:
        support = sorted(nested_samples.get(feature, set()))
        counter = sorted(
            (condition_span_samples.get(feature, set())
             | constraint_span_samples.get(feature, set())) - set(support))
        rows.append({
            "semantic_situation": situation,
            "feature_key": feature,
            "gold_pattern": (
                "descriptive feature present in Gold spans; role is not fixed "
                "by the feature"),
            "condition_samples": len(condition_span_samples.get(feature, set())),
            "constraint_samples": len(constraint_span_samples.get(feature, set())),
            "nested_constraint_samples": len(support),
            "condition_only_samples": len(condition_only_samples.get(feature, set())),
            "constraint_outside_samples": len(outside_samples.get(feature, set())),
            "example_supporting_cases": ";".join(support[:5]),
            "example_counterexamples": ";".join(counter[:5]),
            "stable_principle": (
                "overlap_allowed_but_role_requires_manual_review"
                if feature == "nested_restriction"
                else "no_stable_lexical_or_topic_rule_identified"),
            "manual_review_required": True,
        })
    rows.append({
        "semantic_situation": "nested condition + constraint restriction",
        "feature_key": "nested_restriction",
        "gold_pattern": (
            "Gold condition and Gold constraint spans overlap in the same "
            "clause; both relations occur"),
        "condition_samples": len({
            c["sample_id"] for c in cases
            if c.get("nested_condition_constraint")}),
        "constraint_samples": len({
            c["sample_id"] for c in cases
            if c.get("nested_condition_constraint")}),
        "nested_constraint_samples": len({
            c["sample_id"] for c in cases
            if c.get("nested_condition_constraint")}),
        "condition_only_samples": len({
            c["sample_id"] for c in cases if c.get("condition_only")}),
        "constraint_outside_samples": len({
            c["sample_id"] for c in cases
            if c.get("constraint_outside_condition")}),
        "example_supporting_cases": ";".join(sorted({
            c["sample_id"] for c in cases
            if c.get("nested_condition_constraint")})[:8]),
        "example_counterexamples": "",
        "stable_principle": "condition_and_constraint_may_overlap",
        "manual_review_required": True,
    })
    return rows


def load_targeted_arms() -> dict[str, dict[str, dict[str, Any]]]:
    arms: dict[str, dict[str, dict[str, Any]]] = {}
    for arm in ARMS:
        path = TARGETED_DIR / arm / "repeat-01" / "canonical_predictions.jsonl"
        rows: dict[str, dict[str, Any]] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            rows[str(row.get("sample_id"))] = row
        arms[arm] = rows
    return arms


def load_input_texts() -> dict[str, str]:
    payload = read_json(INPUT_PATH)
    return {
        str(record["sample_id"]): str(record["approved_text_en"])
        for record in payload["records"]
    }


def source_text_anomaly_summary() -> dict[str, Any]:
    texts = load_input_texts()
    anomalies: list[dict[str, Any]] = []
    for arm in ARMS:
        path = TARGETED_DIR / arm / "repeat-01" / "canonical_predictions.jsonl"
        for line_no, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            sid = str(row.get("sample_id"))
            expected = texts.get(sid)
            record = row.get("record") or {}
            actual = record.get("source_text")
            if expected is None or actual == expected:
                continue
            if not isinstance(actual, str) or not actual.startswith(expected):
                continue
            appended = actual[len(expected):]
            if "### E — Synthetic worked examples" not in appended:
                continue
            spans_beyond = 0
            for clause in record.get("clauses") or []:
                for field in ("clause_span",):
                    span = clause.get(field) or {}
                    if int(span.get("end", 0)) > len(expected):
                        spans_beyond += 1
                for field in PLURAL.values():
                    for span in clause.get(field) or []:
                        if int(span.get("end", 0)) > len(expected):
                            spans_beyond += 1
            slice_ok = all(
                span.get("text") == expected[int(span.get("start", 0)):int(span.get("end", 0))]
                for clause in record.get("clauses") or []
                for span in (
                    [clause.get("clause_span") or {}]
                    + [s for f in PLURAL.values() for s in (clause.get(f) or [])]
                )
                if isinstance(span.get("start"), int)
                and isinstance(span.get("end"), int)
            )
            anomalies.append({
                "arm": arm,
                "sample_id": sid,
                "line_no": line_no,
                "expected_length": len(expected),
                "actual_length": len(actual),
                "appended_length": len(appended),
                "appended_prefix": appended[:120],
                "spans_beyond_original_source": spans_beyond,
                "original_slice_check_passed": slice_ok,
            })
    return {
        "targeted_arm_anomaly_count": len(anomalies),
        "targeted_arm_anomalies": anomalies,
        "additional_same_pattern": [],
    }


def prediction_summary(gold_records: Sequence[Mapping[str, Any]],
                       cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    coarse_gold = {
        str(record["sample_id"]): record
        for record in build_coarse_view({"records": list(gold_records)})
    }
    arms = load_targeted_arms()
    out: dict[str, Any] = {"arms": {}}

    for arm in ARMS:
        metrics: dict[str, Any] = {"fields": {}}
        for field in SPAN_FIELDS:
            total = Counter()
            for sid, gold_record in coarse_gold.items():
                score = paired.sample_field_score(
                    gold_record, arms[arm][sid], field)
                for key in (
                    "gold_count", "pred_count", "matched_pred",
                    "matched_gold", "unmatched_pred", "missed_gold",
                    "hallucinated_field", "missed_field",
                    "duplicate_overlap_pairs",
                ):
                    total[key] += int(score.get(key) or 0)
                for key, value in (score.get("boundary") or {}).items():
                    total[f"boundary_{key}"] += int(value)
            metrics["fields"][field] = dict(total)

        # Modality confusion and stability.
        gold_mod = {}
        for sid, gold_record in coarse_gold.items():
            gold_mod[sid] = None
            for clause in gold_record.get("clauses") or []:
                label = (clause.get("modality") or {}).get("label")
                if label:
                    gold_mod[sid] = label
                    break
        confusion: Counter = Counter()
        for sid, gold_record in coarse_gold.items():
            pred = paired.modality_label(arms[arm][sid])
            confusion[(gold_mod[sid], pred)] += 1
        metrics["modality_confusion"] = {
            f"{gold}->{pred}": count
            for (gold, pred), count in sorted(confusion.items(),
                                              key=lambda item: (str(item[0][0]),
                                                                str(item[0][1])))
        }
        out["arms"][arm] = metrics

    # Modality stability across A-D.
    modality_pattern: Counter = Counter()
    for sid, gold_record in coarse_gold.items():
        pattern = tuple(
            paired.modality_label(arms[arm][sid]) for arm in ARMS)
        modality_pattern[pattern] += 1
    out["modality_patterns"] = {
        "|".join(str(x) for x in key): value
        for key, value in modality_pattern.items()
    }

    # Empty-Gold actor false positives.
    out["empty_gold_actor_false_positive"] = {}
    for arm in ARMS:
        count = 0
        for sid, gold_record in coarse_gold.items():
            if _field_spans(gold_record, "actor"):
                continue
            if _field_spans(arms[arm][sid].get("record") or {}, "actor"):
                count += 1
        out["empty_gold_actor_false_positive"][arm] = count

    # Exception sample status across arms.
    exception_rows = []
    for sid, gold_record in coarse_gold.items():
        gold_hits = _field_spans(gold_record, "exception")
        if not gold_hits:
            continue
        statuses = {}
        for arm in ARMS:
            score = paired.sample_field_score(gold_record, arms[arm][sid],
                                              "exception")
            statuses[arm] = bool(score["evaluator_correct"])
        exception_rows.append({"sample_id": sid, "status": statuses})
    out["exception_samples"] = exception_rows

    # Gold-level structural facts used by the reports.
    out["gold_condition_only_clauses"] = sum(
        1 for case in cases if case.get("condition_only"))
    out["gold_nested_condition_constraint_pairs"] = sum(
        len(case.get("nested_pairs") or []) for case in cases)
    out["gold_nested_condition_constraint_clauses"] = sum(
        1 for case in cases if case.get("nested_condition_constraint"))
    out["gold_constraint_outside_condition_units"] = sum(
        len(case.get("constraints_outside_condition") or [])
        for case in cases)
    return out


def write_cases(cases: Sequence[Mapping[str, Any]]) -> Path:
    path = REPORT_DIR / "sep_c3_gold_semantic_boundary_cases.jsonl"
    write_jsonl(path, cases)
    return path


def write_matrix(rows: Sequence[Mapping[str, Any]]) -> Path:
    path = REPORT_DIR / "sep_c3_gold_condition_constraint_matrix.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "semantic_situation", "feature_key", "gold_pattern",
        "condition_samples", "constraint_samples", "nested_constraint_samples",
        "condition_only_samples", "constraint_outside_samples",
        "example_supporting_cases", "example_counterexamples",
        "stable_principle", "manual_review_required",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})
    return path


def main() -> None:
    gold = read_json(GOLD_PATH)
    gold_records = list(gold["records"])
    cases = build_gold_cases(gold_records)
    overlap = actual_overlap_summary(gold_records)
    merged_overlap = merged_span_overlap_summary(gold_records)
    matrix = feature_matrix(gold_records, cases)
    anomalies = source_text_anomaly_summary()
    predictions = prediction_summary(gold_records, cases)

    summary = {
        "schema_version": "sep_c3_gold_semantic_boundary_derived@1.0.0",
        "gold_path": str(GOLD_PATH.relative_to(ROOT)),
        "case_count": len(cases),
        "case_type_counts": dict(Counter(
            tag for case in cases for tag in case.get("case_types") or [])),
        "manual_review_required_cases": sum(
            1 for case in cases if case.get("manual_review_required")),
        "actual_overlap": overlap,
        "merged_span_overlap": merged_overlap,
        "matrix_rows": matrix,
        "source_text_anomaly": anomalies,
        "prediction_summary": predictions,
    }

    write_cases(cases)
    write_matrix(matrix)
    write_json(REPORT_DIR / "sep_c3_gold_semantic_boundary_derived_v1.json",
               summary)
    print(json.dumps({
        "cases": len(cases),
        "case_type_counts": summary["case_type_counts"],
        "manual_review_required_cases": summary["manual_review_required_cases"],
        "condition_constraint_clause_pairs": overlap[
            "clause_level_condition_constraint_pairs"],
        "condition_constraint_sample_level_pairs": overlap[
            "sample_level_condition_constraint_pairs"],
        "source_text_anomalies": anomalies["targeted_arm_anomaly_count"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
