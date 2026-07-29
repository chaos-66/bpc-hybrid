"""Correct B3a v1 with live CoreNLP/Tregex opportunity attribution.

This is a diagnostic-only, add-only simulation on immutable v10-A attempts.
It does not run the modality classifier, create a production candidate, write
candidate attempts, change a registry, enable Tsurgeon, or make a performance
claim.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.b0_v10.scope import resolve_scope_fields_v10  # noqa: E402
from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    Estg150B0DevelopmentError,
    build_canonical_gold_records,
    load_object,
    sha256_file,
)
from bpc_hybrid.estg150_b0_development_v2 import (  # noqa: E402
    _run,
    _write_rule_plan,
    parse_bridge_output_multi,
    sun_table8_any_overlap_diagnostic,
)
from bpc_hybrid.estg150_b0_development_v3 import (  # noqa: E402
    _token_span,
    _verify_runtime_identity,
    plan_clause_units_v4,
)
from bpc_hybrid.stage2_evaluation import _char_iou  # noqa: E402
from bpc_hybrid.stage2_evaluation_v3 import (  # noqa: E402
    CLAUSE_MINIMUM_IOU,
    clause_iou_pairs,
)
from bpc_hybrid.sun_style.corenlp_runtime import (  # noqa: E402
    CoreNLPContractError,
    resolve_corenlp_runtime,
    validate_annotation,
)
from bpc_hybrid.sun_style.lexicon_v2_runtime import (  # noqa: E402
    LexiconV2Runtime,
    load_lexicon_v2,
)


RUN_ID = "s27_estg150_b0_b3a_constraint_tregex_diagnostic_v2"
STATUS_ID = "s27_estg150_b0_b3a_status_correction_v2"
CORRECTED_V1_STATUS = (
    "inconclusive_not_instantiated_invalid_for_tregex_opportunity_attribution"
)
DEFAULT_OUTPUT = ROOT / "outputs/development" / RUN_ID
DEFAULT_STATUS = ROOT / "outputs/reports/s27_estg150_b0_b3a_status_correction_v2.manifest.json"

PARENT_DIR = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a"
PARENT_MANIFEST = PARENT_DIR / "manifest.json"
PARENT_ATTEMPTS = PARENT_DIR / "b0_attempts.json"
PARENT_TABLE8 = PARENT_DIR / "sun_table8_any_overlap_diagnostic.json"
V1_SCRIPT = ROOT / "scripts/analyze_estg150_b0_b3a_constraint_tregex_v1.py"
V1_DIAGNOSTIC = (
    ROOT / "outputs/development/s27_estg150_b0_b3a_constraint_tregex_diagnostic_v1/manifest.json"
)
V1_DECISION = ROOT / "outputs/reports/s27_estg150_b0_b3a_not_instantiated_v1.manifest.json"
LAYER_E = ROOT / "data/development/human_review/estg_150_human_correction_v1.json"
MEMBERSHIP = ROOT / "data/development/estg/estg_150_membership_hashes.json"
EVALUATOR = ROOT / "configs/stage2_evaluator_s210_v3.json"
V3_REGISTRY = ROOT / "resources/corenlp/sun_phrase_patterns_v3_enhanced.json"
LEXICON_MANIFEST = ROOT / "resources/lexicon/public_marker_lexicon_en_v2.manifest.json"
PRODUCTION_BRIDGE = ROOT / "tools/corenlp/SunPhraseRuleBatchBridgeMulti.java"
DIAGNOSTIC_BRIDGE = ROOT / "tools/corenlp/SunPhraseRuleDiagnosticB3aV2.java"
SCOPE_RESOLVER = ROOT / "src/bpc_hybrid/b0_v10/scope.py"
ACTIVE_REGISTRY = ROOT / "configs/models/estg150_b0_active_registry_v4.json"
RUNTIME_CONTRACT = ROOT / "configs/sun_corenlp_runtime.json"

EXPECTED_HASHES = {
    "parent_manifest": "88070fab4da3f7c708f055f6bc391b78cc888761c3d6fe117d17673c2c382315",
    "v1_diagnostic": "bf1c81808c6c919d19e64048d95831ab7c0bd5a090a58311904f2d6db7976f35",
    "v1_decision": "08ab34fc6fd3ad387ddfb2d07e4cc5167b94dc2e053bf0b4a5141629285440ef",
    "layer_e": "7fd55f98a7dd6aeef58a93be825465c767f00feeab84c6d4215afc434a135b1c",
    "membership": "0f9065523a57900b22a8a04ae9109d37c72abbe514f3cde60bcd7652cfa1417b",
    "evaluator": "28ce332564c5d10da08dea515aefe31cc2aacd91b6c6877aa1bfebe44f39ae7f",
    "v3_registry": "f49bad50fb6236137f1208aeef572d2a78c789726363897c637dc464c780e142",
    "lexicon_manifest": "3f7e6108c1e66de37377abc2e9b9f4d0344ff2d1eca20b49ebf90e38aff7b462",
    "production_bridge": "1a084befaf1a863889a26b58c5a049f2df846834e26c5643fe5a535c5c13f2a3",
    "scope_resolver": "3c13d2d73d49476cd3449f50775c6b4b63ac68f5baa2f95a4b564e5ca8b30887",
    "active_registry": "1673188cd3aa8a75d4a99862ff9b8b2f6cfdc79e8c9710fba83c47ae7f1d3d00",
}

EXPECTED_PATTERN_IDS = (
    "b3a_c_temp_within_pp",
    "b3a_c_temp_before_after_pp",
    "b3a_c_temp_no_later_than",
    "b3a_c_quant_at_least",
    "b3a_c_quant_no_more_than",
    "b3a_c_legal_pursuant_accordance",
)

V1_METHOD_DEFECTS = (
    "surface regex proxy is not live Tregex",
    "clause text hash merges identical text from different records",
    "Gold text hash merges repeated Gold spans",
    "FP counts only clauses without Gold constraint",
    "union new spans are summed without real pipeline deduplication",
    "FN/FP primary buckets and overlapping facets are not separated",
)

_PLURAL_FIELDS = {
    "condition": "conditions",
    "constraint": "constraints",
    "exception": "exceptions",
    "actor": "actors",
    "action": "actions",
}


class B3aCorrectionError(ValueError):
    """Fail-closed diagnostic contract violation."""


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _binding(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def predicted_clause_key(sample_id: str, predicted_clause_index: int) -> tuple[str, int]:
    return (sample_id, predicted_clause_index)


def gold_span_key(
    sample_id: str,
    gold_clause_index: int,
    field: str,
    span: Mapping[str, Any],
) -> tuple[str, int, str, int, int]:
    return (
        sample_id,
        gold_clause_index,
        field,
        int(span["start"]),
        int(span["end"]),
    )


def predicted_span_key(
    sample_id: str,
    predicted_clause_index: int,
    field: str,
    span: Mapping[str, Any],
) -> tuple[str, int, str, int, int]:
    return (
        sample_id,
        predicted_clause_index,
        field,
        int(span["start"]),
        int(span["end"]),
    )


def opaque_instance_hash(key: Sequence[Any]) -> str:
    payload = json.dumps(list(key), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_frozen_patterns(v1_manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = v1_manifest.get("candidate_patterns_evaluated")
    if not isinstance(rows, list) or len(rows) != 6:
        raise B3aCorrectionError("B3a v1 must contain exactly six candidates")
    patterns: list[dict[str, Any]] = []
    for expected_id, row in zip(EXPECTED_PATTERN_IDS, rows, strict=True):
        if not isinstance(row, Mapping) or row.get("pattern_id") != expected_id:
            raise B3aCorrectionError("B3a v1 candidate order/identity changed")
        tregex = row.get("tregex")
        if not isinstance(tregex, str) or not tregex.strip():
            raise B3aCorrectionError(f"missing frozen Tregex for {expected_id}")
        patterns.append(
            {
                "pattern_id": expected_id,
                "tregex": tregex,
                "family": str(row.get("family")),
                "anchors": list(row.get("anchors") or []),
            }
        )
    return patterns


def parse_candidate_bridge_output(
    stdout: str,
    *,
    patterns: Sequence[Mapping[str, Any]],
    expected_tree_count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    expected = {str(row["pattern_id"]): index for index, row in enumerate(patterns)}
    compile_rows: dict[str, dict[str, Any]] = {}
    matches: list[dict[str, Any]] = []
    summary: dict[str, int] | None = None
    for raw in stdout.splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if parts[0] == "COMPILE":
            if len(parts) != 5:
                raise B3aCorrectionError("malformed diagnostic COMPILE output")
            index = int(parts[1])
            pattern_id = parts[2]
            if pattern_id not in expected or expected[pattern_id] != index:
                raise B3aCorrectionError("diagnostic compile identity mismatch")
            if pattern_id in compile_rows or parts[3] not in {"true", "false"}:
                raise B3aCorrectionError("duplicate/invalid diagnostic compile result")
            compile_rows[pattern_id] = {
                "pattern_id": pattern_id,
                "pattern_index": index,
                "live_compile": parts[3] == "true",
                "compile_error_type": None if parts[3] == "true" else parts[4],
            }
        elif parts[0] == "MATCH":
            if len(parts) != 6:
                raise B3aCorrectionError("malformed diagnostic MATCH output")
            tree_index, pattern_index = int(parts[1]), int(parts[2])
            pattern_id = parts[3]
            begin, end = int(parts[4]), int(parts[5])
            if (
                pattern_id not in expected
                or expected[pattern_id] != pattern_index
                or tree_index < 0
                or tree_index >= expected_tree_count
                or begin < 0
                or end <= begin
            ):
                raise B3aCorrectionError("invalid diagnostic match identity/span")
            matches.append(
                {
                    "tree_index": tree_index,
                    "pattern_index": pattern_index,
                    "pattern_id": pattern_id,
                    "begin": begin,
                    "end": end,
                }
            )
        elif parts[0] == "SUMMARY":
            if len(parts) != 5 or summary is not None:
                raise B3aCorrectionError("malformed/duplicate diagnostic SUMMARY")
            summary = {
                "tree_count": int(parts[1]),
                "pattern_count": int(parts[2]),
                "compiled_count": int(parts[3]),
                "match_count": int(parts[4]),
            }
        else:
            raise B3aCorrectionError("unknown diagnostic bridge output record")
    if summary is None:
        raise B3aCorrectionError("diagnostic bridge SUMMARY missing")
    if set(compile_rows) != set(expected):
        raise B3aCorrectionError("diagnostic bridge compile coverage mismatch")
    if (
        summary["tree_count"] != expected_tree_count
        or summary["pattern_count"] != len(patterns)
        or summary["compiled_count"]
        != sum(row["live_compile"] for row in compile_rows.values())
        or summary["match_count"] != len(matches)
    ):
        raise B3aCorrectionError("diagnostic bridge summary mismatch")
    ordered_compile = [compile_rows[str(row["pattern_id"])] for row in patterns]
    return ordered_compile, matches, summary


def _empty_lexicon(parent: LexiconV2Runtime) -> LexiconV2Runtime:
    return LexiconV2Runtime(
        lexicon_id=parent.lexicon_id + "-diagnostic-empty",
        manifest_sha256=parent.manifest_sha256,
        combined_payload_sha256=parent.combined_payload_sha256,
        category_file_sha256=dict(parent.category_file_sha256),
        entries_by_field={
            "modality": (),
            "condition": (),
            "constraint": (),
            "exception": (),
            "actor": (),
        },
        active_counts={key: 0 for key in parent.active_counts},
        inactive_counts={key: 0 for key in parent.inactive_counts},
        modality_patterns=(),
        field_patterns={"condition": (), "constraint": (), "exception": ()},
        actor_surfaces=frozenset(),
    )


def _span_signature(span: Mapping[str, Any]) -> tuple[int, int, str, str]:
    return (
        int(span["start"]),
        int(span["end"]),
        str(span["text"]),
        str(span.get("normalized") or _normalize(str(span["text"]))),
    )


def classify_parent_relation(
    candidate: Mapping[str, Any], parent_spans: Sequence[Mapping[str, Any]]
) -> str:
    cs, ce = int(candidate["start"]), int(candidate["end"])
    cn = str(candidate.get("normalized") or _normalize(str(candidate["text"])))
    relation_rank = {
        "exact_duplicate": 0,
        "normalized_duplicate": 1,
        "containment": 2,
        "partial_overlap": 3,
        "genuinely_new": 4,
    }
    best = "genuinely_new"
    for parent in parent_spans:
        ps, pe = int(parent["start"]), int(parent["end"])
        pn = str(parent.get("normalized") or _normalize(str(parent["text"])))
        if cs == ps and ce == pe and cn == pn:
            relation = "exact_duplicate"
        elif cn == pn:
            relation = "normalized_duplicate"
        elif cs < pe and ps < ce and ((cs <= ps and ce >= pe) or (ps <= cs and pe >= ce)):
            relation = "containment"
        elif cs < pe and ps < ce:
            relation = "partial_overlap"
        else:
            relation = "genuinely_new"
        if relation_rank[relation] < relation_rank[best]:
            best = relation
    return best


def dedupe_candidate_spans_like_v10(
    accepted: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int, str], dict[str, Any]] = {}
    for row in accepted:
        key = (
            int(row["start"]),
            int(row["end"]),
            str(row.get("normalized") or _normalize(str(row["text"]))),
        )
        current = grouped.get(key)
        if current is None:
            current = {
                **dict(row),
                "pattern_ids": set(row.get("pattern_ids") or [row["pattern_id"]]),
                "raw_contributors": 1,
            }
            grouped[key] = current
        else:
            current["pattern_ids"].update(
                row.get("pattern_ids") or [row["pattern_id"]]
            )
            current["raw_contributors"] += 1
    ordered = sorted(
        grouped.values(),
        key=lambda span: (int(span["start"]), int(span["end"]) - int(span["start"])),
    )
    kept: list[dict[str, Any]] = []
    for span in ordered:
        if int(span["end"]) - int(span["start"]) > 160:
            continue
        if any(
            int(span["start"]) < int(other["end"])
            and int(other["start"]) < int(span["end"])
            for other in kept
        ):
            continue
        span = dict(span)
        span["pattern_ids"] = sorted(span["pattern_ids"])
        kept.append(span)
    return kept[:6]


def compose_add_only_constraints(
    parent_spans: Sequence[Mapping[str, Any]],
    accepted_candidates: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    candidate_final = dedupe_candidate_spans_like_v10(accepted_candidates)
    relations: Counter[str] = Counter()
    additions: list[dict[str, Any]] = []
    for candidate in candidate_final:
        relation = classify_parent_relation(candidate, parent_spans)
        candidate["parent_relation"] = relation
        relations[relation] += 1
        if relation != "genuinely_new":
            continue
        if len(parent_spans) + len(additions) >= 6:
            candidate["parent_relation"] = "capacity_rejected"
            relations["genuinely_new"] -= 1
            relations["capacity_rejected"] += 1
            continue
        additions.append(candidate)
    combined = [dict(span) for span in parent_spans] + [dict(span) for span in additions]
    return combined, candidate_final, relations


def greedy_span_matches(
    gold_spans: Sequence[Mapping[str, Any]],
    predicted_spans: Sequence[Mapping[str, Any]],
) -> tuple[list[tuple[int, int]], set[int], set[int]]:
    used_predicted: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for gold_index, gold_span in enumerate(gold_spans):
        hit = next(
            (
                predicted_index
                for predicted_index, predicted_span in enumerate(predicted_spans)
                if predicted_index not in used_predicted
                and _char_iou(gold_span, predicted_span) > 0.0
            ),
            None,
        )
        if hit is not None:
            used_predicted.add(hit)
            pairs.append((gold_index, hit))
    return (
        pairs,
        set(range(len(gold_spans))) - {gold_index for gold_index, _ in pairs},
        set(range(len(predicted_spans))) - used_predicted,
    )


def _family_facets(text: str) -> set[str]:
    lowered = text.casefold()
    facets: set[str] = set()
    if any(word in lowered for word in ("within", "before", "after", "until", "later", "period", "duration")):
        facets.add("temporal")
    if any(word in lowered for word in ("least", "most", "more", "less", "exceed", "minimum", "maximum", "percent")):
        facets.add("quantitative")
    if any(word in lowered for word in ("pursuant", "accordance", "section", "purpose", "meaning", "under")):
        facets.add("legal_scope")
    return facets


def parent_constraint_error_buckets(
    gold_records: Sequence[Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
    *,
    anchor_surfaces: Sequence[str],
) -> dict[str, Any]:
    gold_by_id = {str(row["sample_id"]): row for row in gold_records}
    fn_primary: Counter[str] = Counter()
    fp_primary: Counter[str] = Counter()
    fn_facets: Counter[str] = Counter()
    fp_facets: Counter[str] = Counter()
    fn_keys: set[tuple[str, int, str, int, int]] = set()
    fp_keys: set[tuple[str, int, str, int, int]] = set()

    for attempt in attempts:
        sample_id = str(attempt["sample_id"])
        gold = gold_by_id[sample_id]
        predicted = attempt["record"]
        clause_pairs, unmatched_gold_clauses, unmatched_predicted_clauses, _ = clause_iou_pairs(
            gold.get("clauses") or [],
            predicted.get("clauses") or [],
            minimum_iou=CLAUSE_MINIMUM_IOU,
        )
        for gold_clause_index in unmatched_gold_clauses:
            gold_clause = gold["clauses"][gold_clause_index]
            for span in gold_clause.get("constraints") or []:
                fn_primary["clause_unaligned"] += 1
                fn_facets["clause_unaligned"] += 1
                for facet in _family_facets(str(span.get("text") or "")):
                    fn_facets[facet] += 1
                fn_keys.add(gold_span_key(sample_id, gold_clause_index, "constraint", span))

        for gold_clause_index, predicted_clause_index in clause_pairs:
            gold_clause = gold["clauses"][gold_clause_index]
            predicted_clause = predicted["clauses"][predicted_clause_index]
            gold_spans = list(gold_clause.get("constraints") or [])
            predicted_spans = list(predicted_clause.get("constraints") or [])
            pairs, unmatched_gold, unmatched_predicted = greedy_span_matches(
                gold_spans, predicted_spans
            )
            del pairs
            for gold_index in unmatched_gold:
                span = gold_spans[gold_index]
                if not predicted_spans:
                    primary = "aligned_no_parent_constraint"
                elif any(_char_iou(span, row) > 0 for row in predicted_clause.get("conditions") or []):
                    primary = "extracted_as_condition"
                elif any(_char_iou(span, row) > 0 for row in predicted_clause.get("exceptions") or []):
                    primary = "extracted_as_exception"
                elif any(
                    _char_iou(span, row) > 0
                    for field in ("actors", "actions")
                    for row in predicted_clause.get(field) or []
                ):
                    primary = "extracted_as_actor_or_action"
                elif predicted_spans:
                    primary = "parent_constraint_no_overlap"
                else:
                    primary = "other_aligned_fn"
                fn_primary[primary] += 1
                clause_text = str(predicted_clause["clause_span"]["text"])
                lowered = (str(span.get("text") or "") + " " + clause_text).casefold()
                if any(surface.casefold() in lowered for surface in anchor_surfaces):
                    fn_facets["has_parent_anchor"] += 1
                if predicted_spans:
                    fn_facets["has_parent_constraint"] += 1
                for name, field in (
                    ("overlaps_condition", "conditions"),
                    ("overlaps_exception", "exceptions"),
                    ("overlaps_actor", "actors"),
                    ("overlaps_action", "actions"),
                ):
                    if any(_char_iou(span, row) > 0 for row in predicted_clause.get(field) or []):
                        fn_facets[name] += 1
                for facet in _family_facets(str(span.get("text") or "")):
                    fn_facets[facet] += 1
                fn_keys.add(gold_span_key(sample_id, gold_clause_index, "constraint", span))

            gold_conditions = list(gold_clause.get("conditions") or [])
            gold_exceptions = list(gold_clause.get("exceptions") or [])
            gold_actor_actions = list(gold_clause.get("actors") or []) + list(
                gold_clause.get("actions") or []
            )
            for predicted_index in unmatched_predicted:
                span = predicted_spans[predicted_index]
                text = str(span.get("text") or "").strip()
                if not gold_spans:
                    primary = "matched_clause_no_gold_constraint"
                elif any(_char_iou(span, row) > 0 for row in gold_conditions):
                    primary = "overlaps_gold_condition"
                elif any(_char_iou(span, row) > 0 for row in gold_exceptions):
                    primary = "overlaps_gold_exception"
                elif any(_char_iou(span, row) > 0 for row in gold_actor_actions):
                    primary = "overlaps_gold_actor_or_action"
                elif len(text.split()) <= 2 and any(
                    surface.casefold() in text.casefold() for surface in anchor_surfaces
                ):
                    primary = "marker_only_fragment"
                else:
                    clause_span = predicted_clause["clause_span"]
                    if (
                        abs(int(span["start"]) - int(clause_span["start"])) <= 1
                        and abs(int(span["end"]) - int(clause_span["end"])) <= 1
                    ):
                        primary = "full_clause_overcapture"
                    elif text.casefold().startswith(("in ", "for ", "by ", "to ", "with ")):
                        primary = "generic_pp"
                    else:
                        primary = "boundary_or_other"
                fp_primary[primary] += 1
                if not gold_spans:
                    fp_facets["no_gold_constraint"] += 1
                for name, rows in (
                    ("overlaps_gold_condition", gold_conditions),
                    ("overlaps_gold_exception", gold_exceptions),
                    ("overlaps_gold_actor_or_action", gold_actor_actions),
                ):
                    if any(_char_iou(span, row) > 0 for row in rows):
                        fp_facets[name] += 1
                for facet in _family_facets(text):
                    fp_facets[facet] += 1
                fp_keys.add(
                    predicted_span_key(
                        sample_id, predicted_clause_index, "constraint", span
                    )
                )

        for predicted_clause_index in unmatched_predicted_clauses:
            predicted_clause = predicted["clauses"][predicted_clause_index]
            for span in predicted_clause.get("constraints") or []:
                fp_primary["predicted_clause_unaligned"] += 1
                fp_facets["clause_unaligned"] += 1
                for facet in _family_facets(str(span.get("text") or "")):
                    fp_facets[facet] += 1
                fp_keys.add(
                    predicted_span_key(
                        sample_id, predicted_clause_index, "constraint", span
                    )
                )

    return {
        "fn": {
            "primary_buckets": dict(sorted(fn_primary.items())),
            "primary_bucket_total": sum(fn_primary.values()),
            "facets": dict(sorted(fn_facets.items())),
            "facet_counts_are_nonexclusive": True,
            "opaque_instance_hashes": sorted(opaque_instance_hash(key) for key in fn_keys),
        },
        "fp": {
            "primary_buckets": dict(sorted(fp_primary.items())),
            "primary_bucket_total": sum(fp_primary.values()),
            "facets": dict(sorted(fp_facets.items())),
            "facet_counts_are_nonexclusive": True,
            "opaque_instance_hashes": sorted(opaque_instance_hash(key) for key in fp_keys),
        },
    }


def _constraint_assignments(
    gold_records: Sequence[Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, int, str, int, int], tuple[str, int, str, int, int]]:
    gold_by_id = {str(row["sample_id"]): row for row in gold_records}
    assignments: dict[
        tuple[str, int, str, int, int], tuple[str, int, str, int, int]
    ] = {}
    for attempt in attempts:
        sample_id = str(attempt["sample_id"])
        gold = gold_by_id[sample_id]
        predicted = attempt["record"]
        clause_pairs, _, _, _ = clause_iou_pairs(
            gold.get("clauses") or [],
            predicted.get("clauses") or [],
            minimum_iou=CLAUSE_MINIMUM_IOU,
        )
        for gold_clause_index, predicted_clause_index in clause_pairs:
            gold_spans = list(gold["clauses"][gold_clause_index].get("constraints") or [])
            predicted_spans = list(
                predicted["clauses"][predicted_clause_index].get("constraints") or []
            )
            pairs, _, _ = greedy_span_matches(gold_spans, predicted_spans)
            for gold_index, predicted_index in pairs:
                assignments[
                    gold_span_key(
                        sample_id,
                        gold_clause_index,
                        "constraint",
                        gold_spans[gold_index],
                    )
                ] = predicted_span_key(
                    sample_id,
                    predicted_clause_index,
                    "constraint",
                    predicted_spans[predicted_index],
                )
    return assignments


def run_live_tregex(
    *,
    source_records: Sequence[Mapping[str, Any]],
    runtime_home: Path,
    work_dir: Path,
    patterns: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    runtime_home = runtime_home.resolve()
    runtime_identity = _verify_runtime_identity(ROOT, runtime_home)
    probe = resolve_corenlp_runtime(ROOT, home=runtime_home)
    if not probe.ready or not probe.java_executable:
        raise B3aCorrectionError(f"CoreNLP runtime unavailable: {probe.reasons}")
    javac = shutil.which("javac")
    if not javac:
        raise B3aCorrectionError("javac is required for live B3a diagnostic")

    input_dir = work_dir / "corenlp-input"
    output_dir = work_dir / "corenlp-output"
    classes_dir = work_dir / "bridge-classes"
    input_dir.mkdir(parents=True)
    output_dir.mkdir()
    classes_dir.mkdir()
    numeric_paths: list[Path] = []
    source_texts: list[str] = []
    for record_index, record in enumerate(source_records):
        source_text = str(record["approved_text_en"])
        path = input_dir / f"record_{record_index:04d}.txt"
        path.write_text(source_text, encoding="utf-8", newline="\n")
        numeric_paths.append(path)
        source_texts.append(source_text)
    file_list = work_dir / "corenlp-filelist.txt"
    file_list.write_text(
        "\n".join(str(path.resolve()) for path in numeric_paths) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    runtime = load_object(RUNTIME_CONTRACT)["runtime"]
    classpath = os.pathsep.join(probe.classpath_entries)
    corenlp_command = [
        probe.java_executable,
        f"-Xmx{runtime['heap_megabytes']}m",
        "-cp",
        classpath,
        "edu.stanford.nlp.pipeline.StanfordCoreNLP",
        "-annotators",
        ",".join(runtime["annotators"]),
        "-outputFormat",
        "json",
        "-filelist",
        str(file_list.resolve()),
        "-outputDirectory",
        str(output_dir.resolve()),
        "-replaceExtension",
    ]
    started = time.perf_counter()
    _run(corenlp_command, cwd=ROOT, timeout=max(1800, 12 * len(source_records)))
    corenlp_seconds = time.perf_counter() - started

    annotations: list[dict[str, Any]] = []
    sentence_refs: list[tuple[int, int]] = []
    tree_lines: list[str] = []
    for record_index, source_text in enumerate(source_texts):
        candidates = list(output_dir.rglob(f"record_{record_index:04d}.json"))
        if len(candidates) != 1:
            raise B3aCorrectionError("numeric CoreNLP output coverage mismatch")
        annotation = load_object(candidates[0])
        try:
            validate_annotation(annotation, source_text)
        except CoreNLPContractError as exc:
            raise B3aCorrectionError(str(exc)) from exc
        annotations.append(annotation)
        for sentence_index, sentence in enumerate(annotation["sentences"]):
            sentence_refs.append((record_index, sentence_index))
            tree_lines.append(" ".join(str(sentence["parse"]).split()))

    compile_command = [
        javac,
        "--release",
        "8",
        "-encoding",
        "UTF-8",
        "-cp",
        classpath,
        "-d",
        str(classes_dir),
        str(PRODUCTION_BRIDGE),
        str(DIAGNOSTIC_BRIDGE),
    ]
    _run(compile_command, cwd=ROOT, timeout=180)
    tree_path = work_dir / "trees.txt"
    tree_path.write_text("\n".join(tree_lines) + "\n", encoding="utf-8", newline="\n")
    bridge_classpath = os.pathsep.join((str(classes_dir), classpath))

    parent_plan = work_dir / "parent-v3-plan.tsv"
    parent_pattern_count = _write_rule_plan(load_object(V3_REGISTRY), parent_plan)
    parent_bridge_started = time.perf_counter()
    parent_completed = _run(
        [
            probe.java_executable,
            "-cp",
            bridge_classpath,
            "SunPhraseRuleBatchBridgeMulti",
            str(parent_plan),
            str(tree_path),
        ],
        cwd=ROOT,
        timeout=600,
    )
    parent_bridge_seconds = time.perf_counter() - parent_bridge_started
    parent_global_cases, parent_summary = parse_bridge_output_multi(parent_completed.stdout)
    if (
        parent_summary["pattern_count"] != parent_pattern_count
        or parent_summary["tree_count"] != len(sentence_refs)
        or len(parent_global_cases) != len(sentence_refs)
        or parent_summary["surgery_count"] != 0
        or parent_summary["terminal_tree_removal_count"] != 0
    ):
        raise B3aCorrectionError("v3 parent bridge coverage/safety mismatch")

    candidate_plan = work_dir / "candidate-plan.tsv"
    candidate_plan.write_text(
        "".join(f"{row['pattern_id']}\t{row['tregex']}\n" for row in patterns),
        encoding="utf-8",
        newline="\n",
    )
    diagnostic_started = time.perf_counter()
    candidate_completed = _run(
        [
            probe.java_executable,
            "-cp",
            bridge_classpath,
            "SunPhraseRuleDiagnosticB3aV2",
            str(candidate_plan),
            str(tree_path),
        ],
        cwd=ROOT,
        timeout=600,
    )
    diagnostic_seconds = time.perf_counter() - diagnostic_started
    compile_rows, matches, candidate_summary = parse_candidate_bridge_output(
        candidate_completed.stdout,
        patterns=patterns,
        expected_tree_count=len(sentence_refs),
    )

    parent_cases: list[list[dict[str, Any]]] = [[] for _ in source_records]
    for global_case, (record_index, sentence_index) in zip(
        parent_global_cases, sentence_refs, strict=True
    ):
        parent_cases[record_index].append(
            {"sentence_index": sentence_index, "fields": global_case["fields"]}
        )

    candidate_by_sentence: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    offset_validation_failures = 0
    for match in matches:
        record_index, sentence_index = sentence_refs[int(match["tree_index"])]
        sentence = annotations[record_index]["sentences"][sentence_index]
        if int(match["end"]) > len(sentence["tokens"]):
            raise B3aCorrectionError("live candidate token span exceeds sentence")
        span = _token_span(source_texts[record_index], sentence, match)
        if source_texts[record_index][span["start"] : span["end"]] != span["text"]:
            offset_validation_failures += 1
        candidate_by_sentence[(record_index, sentence_index)].append(dict(match))
    if offset_validation_failures:
        raise B3aCorrectionError("live token/character/source offset validation failed")

    return {
        "annotations": annotations,
        "parent_cases": parent_cases,
        "candidate_by_sentence": candidate_by_sentence,
        "compile_rows": compile_rows,
        "matches": matches,
        "runtime": {
            "runtime_identity": runtime_identity,
            "corenlp_version": "4.5.10",
            "record_count": len(source_records),
            "sentence_count": len(sentence_refs),
            "parent_v3_pattern_count": parent_pattern_count,
            "parent_v3_match_count": parent_summary["match_count"],
            "candidate_pattern_count": len(patterns),
            "candidate_compiled_count": candidate_summary["compiled_count"],
            "candidate_raw_match_count": candidate_summary["match_count"],
            "offset_validated_match_count": len(matches),
            "offset_validation_failures": offset_validation_failures,
            "corenlp_seconds": corenlp_seconds,
            "parent_bridge_seconds": parent_bridge_seconds,
            "candidate_bridge_seconds": diagnostic_seconds,
            "tsurgeon_enabled": False,
            "modality_classifier_run": False,
            "numeric_temporary_file_names_only": True,
        },
    }


def build_live_opportunity(
    *,
    gold: Sequence[Mapping[str, Any]],
    source_records: Sequence[Mapping[str, Any]],
    parent_attempts: Sequence[Mapping[str, Any]],
    patterns: Sequence[Mapping[str, Any]],
    live: Mapping[str, Any],
) -> dict[str, Any]:
    parent_by_id = {str(row["sample_id"]): row for row in parent_attempts}
    lexicon = load_lexicon_v2(ROOT)
    empty_lexicon = _empty_lexicon(lexicon)
    raw_counts = Counter(str(row["pattern_id"]) for row in live["matches"])
    accepted_counts: Counter[str] = Counter()
    final_counts: Counter[str] = Counter()
    new_counts: Counter[str] = Counter()
    accepted_records: dict[str, set[str]] = defaultdict(set)
    new_records: dict[str, set[str]] = defaultdict(set)
    relation_counts: Counter[str] = Counter()
    additions_by_clause: dict[tuple[str, int], list[dict[str, Any]]] = {}
    candidate_final_total = 0
    accepted_total = 0
    exact_unique_before_overlap: set[tuple[str, int, int, int, str]] = set()
    baseline_mismatch_count = 0

    for record_index, source_record in enumerate(source_records):
        sample_id = str(source_record["sample_id"])
        source_text = str(source_record["approved_text_en"])
        annotation = live["annotations"][record_index]
        units, _ = plan_clause_units_v4(annotation, source_text)
        parent_record = parent_by_id[sample_id]["record"]
        parent_clauses = list(parent_record.get("clauses") or [])
        if len(units) != len(parent_clauses):
            raise B3aCorrectionError("v10-A clause count drift during live diagnostic")
        parent_cases_by_sentence = {
            int(case["sentence_index"]): case for case in live["parent_cases"][record_index]
        }
        for predicted_clause_index, (unit, parent_clause) in enumerate(
            zip(units, parent_clauses, strict=True)
        ):
            clause_start, clause_end = map(int, unit["clause_char_span"])
            if (
                clause_start != int(parent_clause["clause_span"]["start"])
                or clause_end != int(parent_clause["clause_span"]["end"])
            ):
                raise B3aCorrectionError("v10-A clause boundary drift during live diagnostic")
            clause_text = source_text[clause_start:clause_end]
            parent_obs: dict[str, list[tuple[Any, Mapping[str, Any]]]] = {
                "condition": [],
                "constraint": [],
                "exception": [],
            }
            raw_candidate_obs: list[tuple[Any, Mapping[str, Any]]] = []
            for sentence_index in unit["sentence_indexes"]:
                sentence = annotation["sentences"][sentence_index]
                fields = parent_cases_by_sentence.get(sentence_index, {}).get("fields", {})
                for field in parent_obs:
                    values = fields.get(field) or []
                    if isinstance(values, Mapping):
                        values = [values]
                    for observation in values:
                        parent_obs[field].append((sentence, observation))
                for observation in live["candidate_by_sentence"].get(
                    (record_index, sentence_index), []
                ):
                    raw_candidate_obs.append((sentence, observation))

            parent_scope, _, _ = resolve_scope_fields_v10(
                clause_text=clause_text,
                clause_start=clause_start,
                source_text=source_text,
                lexicon=lexicon,
                tregex_obs=parent_obs,
            )
            expected_parent = [
                _span_signature(span) for span in parent_clause.get("constraints") or []
            ]
            reconstructed_parent = [
                _span_signature(span) for span in parent_scope["constraint"]
            ]
            if reconstructed_parent != expected_parent:
                baseline_mismatch_count += 1
                raise B3aCorrectionError("live v3 pipeline does not reconstruct v10-A constraints")

            accepted_candidates: list[dict[str, Any]] = []
            for sentence, observation in raw_candidate_obs:
                scope, _, stats = resolve_scope_fields_v10(
                    clause_text=clause_text,
                    clause_start=clause_start,
                    source_text=source_text,
                    lexicon=empty_lexicon,
                    tregex_obs={"constraint": [(sentence, observation)]},
                )
                if stats["tregex_accepted"] != len(scope["constraint"]):
                    if stats["tregex_accepted"] != 0 or scope["constraint"]:
                        raise B3aCorrectionError("single candidate acceptance/final mismatch")
                    continue
                if not scope["constraint"]:
                    continue
                span = dict(scope["constraint"][0])
                if source_text[int(span["start"]) : int(span["end"])] != span["text"]:
                    raise B3aCorrectionError("accepted candidate source slice mismatch")
                pattern_id = str(observation["pattern_id"])
                span["pattern_id"] = pattern_id
                span["pattern_ids"] = [pattern_id]
                accepted_candidates.append(span)
                accepted_counts[pattern_id] += 1
                accepted_records[pattern_id].add(sample_id)
                accepted_total += 1
                exact_unique_before_overlap.add(
                    (
                        sample_id,
                        predicted_clause_index,
                        int(span["start"]),
                        int(span["end"]),
                        str(span["normalized"]),
                    )
                )

            combined, candidate_final, clause_relations = compose_add_only_constraints(
                parent_clause.get("constraints") or [], accepted_candidates
            )
            del combined
            relation_counts.update(clause_relations)
            candidate_final_total += len(candidate_final)
            clause_additions = [
                row for row in candidate_final if row.get("parent_relation") == "genuinely_new"
            ]
            if len(parent_clause.get("constraints") or []) + len(clause_additions) > 6:
                raise B3aCorrectionError("add-only constraint cap violation")
            additions_by_clause[predicted_clause_key(sample_id, predicted_clause_index)] = (
                clause_additions
            )
            for row in candidate_final:
                for pattern_id in row["pattern_ids"]:
                    final_counts[pattern_id] += 1
            for row in clause_additions:
                for pattern_id in row["pattern_ids"]:
                    new_counts[pattern_id] += 1
                    new_records[pattern_id].add(sample_id)

    if baseline_mismatch_count:
        raise B3aCorrectionError("parent reconstruction mismatch")

    candidate_attempts = copy.deepcopy(list(parent_attempts))
    addition_keys: set[tuple[str, int, str, int, int]] = set()
    for attempt in candidate_attempts:
        sample_id = str(attempt["sample_id"])
        for predicted_clause_index, clause in enumerate(attempt["record"].get("clauses") or []):
            additions = additions_by_clause[(sample_id, predicted_clause_index)]
            for rank, row in enumerate(additions, start=1):
                span = {
                    "id": f"diagnostic.constraint.{rank}",
                    "text": row["text"],
                    "start": int(row["start"]),
                    "end": int(row["end"]),
                    "normalized": row["normalized"],
                }
                clause.setdefault("constraints", []).append(span)
                addition_keys.add(
                    predicted_span_key(
                        sample_id, predicted_clause_index, "constraint", span
                    )
                )

    parent_table8 = sun_table8_any_overlap_diagnostic(gold, parent_attempts)
    frozen_table8 = load_object(PARENT_TABLE8)
    if parent_table8 != frozen_table8:
        raise B3aCorrectionError("recomputed parent Table8 differs from frozen v10-A")
    candidate_table8 = sun_table8_any_overlap_diagnostic(gold, candidate_attempts)
    for field in ("actor", "action", "condition", "exception"):
        if candidate_table8["per_field"][field] != parent_table8["per_field"][field]:
            raise B3aCorrectionError("B3a diagnostic changed a non-constraint field")
    parent_constraint = parent_table8["per_field"]["constraint"]
    candidate_constraint = candidate_table8["per_field"]["constraint"]
    constraint_delta = {
        metric: candidate_constraint[metric] - parent_constraint[metric]
        for metric in ("tp", "fp", "fn", "gold", "pred")
    }
    overall_delta = {
        metric: candidate_table8["overall"][metric] - parent_table8["overall"][metric]
        for metric in ("tp", "fp", "fn")
    }
    delta_precision = (
        constraint_delta["tp"] / (constraint_delta["tp"] + constraint_delta["fp"])
        if constraint_delta["tp"] + constraint_delta["fp"]
        else 0.0
    )

    parent_assignments = _constraint_assignments(gold, parent_attempts)
    candidate_assignments = _constraint_assignments(gold, candidate_attempts)
    recovered_gold = {
        key: predicted_key
        for key, predicted_key in candidate_assignments.items()
        if key not in parent_assignments and predicted_key in addition_keys
    }
    if len(recovered_gold) != constraint_delta["tp"]:
        raise B3aCorrectionError("direct recovered Gold count differs from TP delta")
    candidate_assigned_predicted = set(candidate_assignments.values())
    new_fp_keys = addition_keys - candidate_assigned_predicted
    if len(new_fp_keys) != constraint_delta["fp"]:
        raise B3aCorrectionError("new unmatched addition count differs from FP delta")

    anchor_surfaces = [
        str(anchor)
        for pattern in patterns
        for anchor in pattern.get("anchors") or []
    ]
    buckets = parent_constraint_error_buckets(
        gold, parent_attempts, anchor_surfaces=anchor_surfaces
    )
    if buckets["fn"]["primary_bucket_total"] != 176:
        raise B3aCorrectionError("mutually exclusive FN primary buckets must total 176")
    if buckets["fp"]["primary_bucket_total"] != 209:
        raise B3aCorrectionError("mutually exclusive FP primary buckets must total 209")

    compile_by_id = {row["pattern_id"]: row for row in live["compile_rows"]}
    pattern_results = []
    for pattern in patterns:
        pattern_id = str(pattern["pattern_id"])
        pattern_results.append(
            {
                **pattern,
                **compile_by_id[pattern_id],
                "raw_match_count": raw_counts[pattern_id],
                "clause_scope_accepted_count": accepted_counts[pattern_id],
                "final_unique_span_participation_count": final_counts[pattern_id],
                "genuinely_new_span_participation_count": new_counts[pattern_id],
                "accepted_unique_record_count": len(accepted_records[pattern_id]),
                "genuinely_new_unique_record_count": len(new_records[pattern_id]),
            }
        )

    all_new_records = {
        sample_id
        for sample_id, predicted_clause_index in additions_by_clause
        if additions_by_clause[(sample_id, predicted_clause_index)]
    }
    return {
        "pattern_results": pattern_results,
        "funnel": {
            "raw_live_constituent_matches": len(live["matches"]),
            "clause_scope_accepted_match_events": accepted_total,
            "exact_unique_candidates_before_overlap_dedup": len(exact_unique_before_overlap),
            "final_unique_candidate_spans": candidate_final_total,
            "final_add_only_genuinely_new_spans": len(addition_keys),
            "unique_records_with_genuinely_new_spans": len(all_new_records),
        },
        "parent_relation_counts": {
            key: int(relation_counts.get(key, 0))
            for key in (
                "exact_duplicate",
                "normalized_duplicate",
                "containment",
                "partial_overlap",
                "genuinely_new",
                "capacity_rejected",
            )
        },
        "table8_opportunity": {
            "parent_constraint": parent_constraint,
            "diagnostic_add_only_constraint": candidate_constraint,
            "constraint_delta": constraint_delta,
            "delta_precision": delta_precision,
            "parent_overall": parent_table8["overall"],
            "diagnostic_add_only_overall": candidate_table8["overall"],
            "overall_delta": overall_delta,
            "recovered_fn_count": len(recovered_gold),
            "new_fp_count": len(new_fp_keys),
            "remaining_fn_count": candidate_constraint["fn"],
            "recovered_gold_opaque_hashes": sorted(
                opaque_instance_hash(key) for key in recovered_gold
            ),
            "new_fp_opaque_hashes": sorted(
                opaque_instance_hash(key) for key in new_fp_keys
            ),
        },
        "parent_error_analysis": buckets,
        "baseline_reconstruction": {
            "v10_constraint_clause_mismatch_count": baseline_mismatch_count,
            "frozen_parent_table8_exact": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-home", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--status-manifest", type=Path, default=DEFAULT_STATUS)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    status_path = args.status_manifest.resolve()
    try:
        output_dir.relative_to((ROOT / "outputs/development").resolve())
        status_path.relative_to((ROOT / "outputs/reports").resolve())
        if output_dir.exists() or status_path.exists():
            raise B3aCorrectionError("refusing to overwrite B3a correction output")

        hash_paths = {
            "parent_manifest": PARENT_MANIFEST,
            "v1_diagnostic": V1_DIAGNOSTIC,
            "v1_decision": V1_DECISION,
            "layer_e": LAYER_E,
            "membership": MEMBERSHIP,
            "evaluator": EVALUATOR,
            "v3_registry": V3_REGISTRY,
            "lexicon_manifest": LEXICON_MANIFEST,
            "production_bridge": PRODUCTION_BRIDGE,
            "scope_resolver": SCOPE_RESOLVER,
            "active_registry": ACTIVE_REGISTRY,
        }
        for name, expected in EXPECTED_HASHES.items():
            actual = sha256_file(hash_paths[name])
            if actual != expected:
                raise B3aCorrectionError(f"fixed hash mismatch: {name}")

        v1_manifest = load_object(V1_DIAGNOSTIC)
        v1_decision = load_object(V1_DECISION)
        if (
            v1_manifest.get("decision") != "not_instantiated"
            or v1_decision.get("decision") != "not_instantiated"
        ):
            raise B3aCorrectionError("B3a v1 safe not_instantiated decision changed")
        patterns = load_frozen_patterns(v1_manifest)
        gold, source_records = build_canonical_gold_records(LAYER_E, MEMBERSHIP)
        parent_attempts = json.loads(PARENT_ATTEMPTS.read_text(encoding="utf-8"))
        if not isinstance(parent_attempts, list) or len(parent_attempts) != 150:
            raise B3aCorrectionError("v10-A parent attempts must contain 150 records")

        (ROOT / ".tmp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="b3a-diagnostic-v2-", dir=ROOT / ".tmp"
        ) as raw_work_dir:
            live = run_live_tregex(
                source_records=source_records,
                runtime_home=args.runtime_home,
                work_dir=Path(raw_work_dir),
                patterns=patterns,
            )
            opportunity = build_live_opportunity(
                gold=gold,
                source_records=source_records,
                parent_attempts=parent_attempts,
                patterns=patterns,
                live=live,
            )

        created_at = datetime.now(timezone.utc).isoformat()
        diagnostic = {
            "schema_version": "b3a_constraint_tregex_live_opportunity_diagnostic@2.0.0",
            "run_id": RUN_ID,
            "created_at_utc": created_at,
            "claim_scope": "development_live_tregex_opportunity_diagnostic_only",
            "is_formal_performance_result": False,
            "parent_run": "s27_estg150_b0_enhanced_v10a",
            "v1_status_correction": {
                "corrected_status": CORRECTED_V1_STATUS,
                "safe_not_instantiated_decision_remains_valid": True,
                "valid_for_live_tregex_opportunity_attribution": False,
                "method_defects": list(V1_METHOD_DEFECTS),
            },
            "identity_contract": {
                "predicted_clause_key": ["sample_id", "predicted_clause_index"],
                "gold_span_key": [
                    "sample_id",
                    "gold_clause_index",
                    "field",
                    "start",
                    "end",
                ],
                "predicted_span_key": [
                    "sample_id",
                    "predicted_clause_index",
                    "field",
                    "start",
                    "end",
                ],
                "keys_used_in_memory_only": True,
                "persisted_instance_traces": "sha256_of_complete_instance_key_only",
                "clause_or_gold_text_hash_used_as_identity": False,
                "sample_id_allowlist_persisted": False,
            },
            "live_runtime": live["runtime"],
            **opportunity,
            "interpretation": {
                "v2_is_live_tregex_opportunity_diagnostic": True,
                "v2_is_candidate_all150": False,
                "v2_is_formal_performance": False,
                "instantiation_decision_deferred_to_future_user_prompt": True,
                "no_pattern_selection_or_threshold_sweep": True,
            },
            "safety": {
                "gold_read_only": True,
                "layer_e_modified": False,
                "evaluator_modified": False,
                "independent82_read_or_used": False,
                "s2_4_test_read": False,
                "network_called": False,
                "llm_api_called": False,
                "modality_classifier_run": False,
                "tsurgeon_enabled": False,
                "production_bridge_modified": False,
                "candidate_all150_run": False,
                "production_candidate_created": False,
                "active_registry_modified": False,
                "b3b_started": False,
            },
        }

        staging = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
        if staging.exists():
            raise B3aCorrectionError("diagnostic staging path already exists")
        staging.mkdir(parents=True)
        try:
            diagnostic_path = staging / "diagnostic.json"
            _write_json(diagnostic_path, diagnostic)
            bindings = {
                **hash_paths,
                "parent_attempts": PARENT_ATTEMPTS,
                "parent_table8": PARENT_TABLE8,
                "v1_script": V1_SCRIPT,
                "correction_script": Path(__file__).resolve(),
                "diagnostic_bridge": DIAGNOSTIC_BRIDGE,
                "runtime_contract": RUNTIME_CONTRACT,
            }
            manifest = {
                "schema_version": "b3a_constraint_tregex_diagnostic_manifest@2.0.0",
                "run_id": RUN_ID,
                "status": "succeeded_diagnostic_only_no_candidate",
                "created_at_utc": created_at,
                "claim_scope": diagnostic["claim_scope"],
                "input_bindings": {
                    name: _binding(path) for name, path in sorted(bindings.items())
                },
                "artifact": {
                    "path": "diagnostic.json",
                    "sha256": sha256_file(diagnostic_path),
                    "bytes": diagnostic_path.stat().st_size,
                },
                "v1_corrected_status": CORRECTED_V1_STATUS,
                "live_compiled_patterns": sum(
                    row["live_compile"] for row in opportunity["pattern_results"]
                ),
                "raw_match_count": opportunity["funnel"]["raw_live_constituent_matches"],
                "final_add_only_span_count": opportunity["funnel"][
                    "final_add_only_genuinely_new_spans"
                ],
                "constraint_delta": opportunity["table8_opportunity"]["constraint_delta"],
                "safety": diagnostic["safety"],
            }
            _write_json(staging / "manifest.json", manifest)
            staging.rename(output_dir)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

        status = {
            "schema_version": "b3a_diagnostic_status_correction@2.0.0",
            "correction_id": STATUS_ID,
            "created_at_utc": created_at,
            "corrected_v1_status": CORRECTED_V1_STATUS,
            "v1_not_instantiated_safe_meaning_remains_valid": True,
            "v1_invalid_for_live_tregex_opportunity_attribution": True,
            "v1_method_defects": list(V1_METHOD_DEFECTS),
            "v2_is_live_tregex_opportunity_diagnostic": True,
            "v2_is_formal_performance_result": False,
            "v2_instantiation_decision": "deferred_not_authorized_in_this_round",
            "v2_diagnostic_manifest": {
                "path": str((output_dir / "manifest.json").relative_to(ROOT)).replace(
                    "\\", "/"
                ),
                "sha256": sha256_file(output_dir / "manifest.json"),
                "bytes": (output_dir / "manifest.json").stat().st_size,
            },
            "v1_bindings": {
                "diagnostic": _binding(V1_DIAGNOSTIC),
                "decision": _binding(V1_DECISION),
            },
            "actions_not_taken": [
                "no production registry/config/runner/preregistration created",
                "no candidate All-150 run",
                "no candidate pattern edited/added/removed",
                "no active registry change",
                "B3b not started",
            ],
            "safety": diagnostic["safety"],
        }
        status_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(status_path, status)
        if sha256_file(PRODUCTION_BRIDGE) != EXPECTED_HASHES["production_bridge"]:
            raise B3aCorrectionError("production bridge changed after diagnostic")
        if sha256_file(ACTIVE_REGISTRY) != EXPECTED_HASHES["active_registry"]:
            raise B3aCorrectionError("active registry changed after diagnostic")

        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": "diagnostic_correction_v2_complete",
                    "v1_corrected_status": CORRECTED_V1_STATUS,
                    "compile": [
                        {
                            "pattern_id": row["pattern_id"],
                            "live_compile": row["live_compile"],
                            "raw_match_count": row["raw_match_count"],
                        }
                        for row in opportunity["pattern_results"]
                    ],
                    "funnel": opportunity["funnel"],
                    "relations": opportunity["parent_relation_counts"],
                    "constraint_delta": opportunity["table8_opportunity"][
                        "constraint_delta"
                    ],
                    "output_manifest_sha256": sha256_file(output_dir / "manifest.json"),
                    "status_manifest_sha256": sha256_file(status_path),
                    "candidate_all150_run": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (
        B3aCorrectionError,
        Estg150B0DevelopmentError,
        CoreNLPContractError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"B3a diagnostic correction v2 failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
