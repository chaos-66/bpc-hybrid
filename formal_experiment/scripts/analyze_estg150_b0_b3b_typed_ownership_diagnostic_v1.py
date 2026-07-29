"""Read-only B3b typed condition/constraint ownership diagnostic.

The ownership rule below is frozen before Gold is loaded.  It may only move an
existing parent span between ``conditions`` and ``constraints`` using the
already-versioned lexicon and the already-versioned v10 typed scope resolver.
It never creates or trims a raw span and never changes modality or segmentation.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.b0_v10.scope import (  # noqa: E402
    ScopeTestError,
    apply_typed_scope,
    resolve_scope_fields_v10,
)
from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    build_canonical_gold_records,
    load_object,
    sha256_file,
)
from bpc_hybrid.estg150_b0_development_v2 import (  # noqa: E402
    sun_table8_any_overlap_diagnostic,
)
from bpc_hybrid.estg150_b0_development_v3 import plan_clause_units_v4  # noqa: E402
from bpc_hybrid.estg150_b0_development_v10 import (  # noqa: E402
    run_corenlp_batch_v10,
)
from bpc_hybrid.stage2_evaluation import _char_iou  # noqa: E402
from bpc_hybrid.stage2_evaluation_v3 import (  # noqa: E402
    CLAUSE_MINIMUM_IOU,
    clause_iou_pairs,
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
    validate_evaluation_report,
)
from bpc_hybrid.sun_style.lexicon_v2_runtime import (  # noqa: E402
    LexiconV2Runtime,
    MarkerEntry,
    load_lexicon_v2,
    match_field_markers,
)


RUN_ID = "s27_estg150_b0_b3b_typed_ownership_diagnostic_v1"
DEFAULT_OUTPUT = ROOT / "outputs/development" / RUN_ID
PARENT_DIR = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a"
PARENT_MANIFEST = PARENT_DIR / "manifest.json"
PARENT_ATTEMPTS = PARENT_DIR / "b0_attempts.json"
PARENT_TABLE8 = PARENT_DIR / "sun_table8_any_overlap_diagnostic.json"
PARENT_EVALUATION = PARENT_DIR / "evaluation_all150.json"
PARENT_CONFIG = ROOT / "configs/models/estg150_b0_enhanced_s27_v10a.json"
SCOPE_RESOLVER = ROOT / "src/bpc_hybrid/b0_v10/scope.py"
LEXICON_MANIFEST = ROOT / "resources/lexicon/public_marker_lexicon_en_v2.manifest.json"
EVALUATOR = ROOT / "configs/stage2_evaluator_s210_v3.json"
B3A_V2 = (
    ROOT
    / "outputs/development/s27_estg150_b0_b3a_constraint_tregex_diagnostic_v2/manifest.json"
)
ACTIVE_REGISTRY = ROOT / "configs/models/estg150_b0_active_registry_v4.json"
TREGEX_REGISTRY = ROOT / "resources/corenlp/sun_phrase_patterns_v3_enhanced.json"
PRODUCTION_BRIDGE = ROOT / "tools/corenlp/SunPhraseRuleBatchBridgeMulti.java"

EXPECTED_HASHES = {
    "parent_manifest": "88070fab4da3f7c708f055f6bc391b78cc888761c3d6fe117d17673c2c382315",
    "scope_resolver": "3c13d2d73d49476cd3449f50775c6b4b63ac68f5baa2f95a4b564e5ca8b30887",
    "lexicon_manifest": "3f7e6108c1e66de37377abc2e9b9f4d0344ff2d1eca20b49ebf90e38aff7b462",
    "evaluator": "28ce332564c5d10da08dea515aefe31cc2aacd91b6c6877aa1bfebe44f39ae7f",
    "b3a_v2": "ddcf26581d8dde61eb9b95fd015d5cbb34b17763c74db6888af7efffed6a4cc0",
    "active_registry": "1673188cd3aa8a75d4a99862ff9b8b2f6cfdc79e8c9710fba83c47ae7f1d3d00",
    "tregex_registry": "f49bad50fb6236137f1208aeef572d2a78c789726363897c637dc464c780e142",
    "production_bridge": "1a084befaf1a863889a26b58c5a049f2df846834e26c5643fe5a535c5c13f2a3",
}

# Frozen before reading Gold.  No result-dependent exceptions may be added.
ALGORITHM_NAME = "typed_condition_constraint_ownership"
ALGORITHM_VERSION = "b3b_typed_ownership@1.0.0"
CONDITION_STRONG_TYPES = frozenset(
    {"condition_subordinator", "applicability_condition"}
)
CONSTRAINT_STRONG_TYPES = frozenset(
    {
        "temporal_limit",
        "duration_limit",
        "quantitative_comparator",
        "legal_reference",
        "purpose_scope",
        "manner_scope",
        "definition_reference",
    }
)
EXCEPTION_TYPE = "exception_carveout"
TARGET_EQUIVALENCE_PRECEDENCE = (
    "exact_duplicate",
    "normalized_duplicate",
    "overlap_equivalent",
)
TARGET_CAPACITY = 6
DIRECTION_ORDER = ("constraint_to_condition", "condition_to_constraint")
RULE_SPEC = {
    "algorithm_name": ALGORITHM_NAME,
    "algorithm_version": ALGORITHM_VERSION,
    "condition_types": sorted(CONDITION_STRONG_TYPES),
    "constraint_types": sorted(CONSTRAINT_STRONG_TYPES),
    "exception_type": EXCEPTION_TYPE,
    "condition_evidence_scope": "current_span_or_current_clause",
    "constraint_to_condition_veto_scope": "current_span_or_current_clause",
    "condition_to_constraint_positive_scope": "current_span_only",
    "exception_veto_scope": "current_span_or_current_clause",
    "ambiguity_policy": "parent_field_unchanged",
    "target_equivalence_precedence": list(TARGET_EQUIVALENCE_PRECEDENCE),
    "overlap_equivalent_rule": "any_nonempty_character_intersection",
    "target_capacity": TARGET_CAPACITY,
    "direction_order": list(DIRECTION_ORDER),
    "span_mutation": "forbidden",
    "sample_specific_logic": False,
}
RULE_SPEC_SHA256 = hashlib.sha256(
    json.dumps(RULE_SPEC, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


class B3bDiagnosticError(ValueError):
    """Fail-closed B3b diagnostic contract error."""


@dataclass(frozen=True)
class TypedHit:
    field: str
    surface: str
    scope_type: str
    start: int
    end: int


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _opaque_hash(parts: Sequence[Any]) -> str:
    raw = json.dumps(list(parts), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _span_value_key(span: Mapping[str, Any]) -> tuple[int, int, str, str]:
    return (
        int(span["start"]),
        int(span["end"]),
        str(span["text"]),
        str(span.get("normalized") or _normalize(str(span["text"]))),
    )


def _span_instance_key(
    clause_index: int, field: str, span: Mapping[str, Any]
) -> tuple[int, str, int, int]:
    return (clause_index, field, int(span["start"]), int(span["end"]))


def _ranges_overlap(
    first: Mapping[str, Any] | TypedHit, second: Mapping[str, Any] | TypedHit
) -> bool:
    return int(first.start if isinstance(first, TypedHit) else first["start"]) < int(
        second.end if isinstance(second, TypedHit) else second["end"]
    ) and int(second.start if isinstance(second, TypedHit) else second["start"]) < int(
        first.end if isinstance(first, TypedHit) else first["end"]
    )


def _validate_span(span: Mapping[str, Any], source_text: str) -> str | None:
    try:
        start, end = int(span["start"]), int(span["end"])
        text = str(span["text"])
        normalized = str(span.get("normalized") or _normalize(text))
    except (KeyError, TypeError, ValueError):
        return "malformed_span_fields"
    if start < 0 or end <= start or end > len(source_text):
        return "invalid_span_offsets"
    if source_text[start:end] != text:
        return "span_source_slice_mismatch"
    if normalized != _normalize(text):
        return "span_normalized_mismatch"
    return None


def _entry_by_surface(
    lexicon: LexiconV2Runtime, field: str
) -> dict[str, MarkerEntry]:
    result: dict[str, MarkerEntry] = {}
    for entry in lexicon.entries_by_field.get(field, ()):
        if entry.activation:
            result[entry.surface.casefold()] = entry
    return result


def collect_clause_typed_hits(
    clause_text: str,
    clause_start: int,
    lexicon: LexiconV2Runtime,
) -> tuple[list[TypedHit], list[str]]:
    """Classify only existing lexicon hits through the frozen v10 resolver."""
    hits: list[TypedHit] = []
    errors: list[str] = []
    for field in ("condition", "constraint", "exception"):
        entries = _entry_by_surface(lexicon, field)
        for hit in match_field_markers(clause_text, field, lexicon):
            entry = entries.get(str(hit["surface"]).casefold())
            if entry is None:
                errors.append("missing_active_entry_metadata")
                continue
            try:
                decision = apply_typed_scope(
                    field=field,
                    surface=entry.surface,
                    scope_hint=entry.scope_test or entry.syntactic_scope,
                    clause_text=clause_text,
                    match_start=int(hit["start"]),
                    match_end=int(hit["end"]),
                    source="lexicon",
                )
            except (ScopeTestError, KeyError, TypeError, ValueError):
                errors.append("typed_scope_classification_error")
                continue
            hits.append(
                TypedHit(
                    field=field,
                    surface=entry.surface,
                    scope_type=decision.scope_type,
                    start=clause_start + int(hit["start"]),
                    end=clause_start + int(hit["end"]),
                )
            )
    hits.sort(key=lambda row: (row.start, row.end, row.field, row.surface.casefold()))
    return hits, errors


def _strong_evidence(
    span: Mapping[str, Any], typed_hits: Sequence[TypedHit]
) -> dict[str, list[TypedHit]]:
    condition_clause = [
        hit
        for hit in typed_hits
        if hit.field == "condition" and hit.scope_type in CONDITION_STRONG_TYPES
    ]
    constraint_clause = [
        hit
        for hit in typed_hits
        if hit.field == "constraint" and hit.scope_type in CONSTRAINT_STRONG_TYPES
    ]
    exception_clause = [
        hit
        for hit in typed_hits
        if hit.field == "exception" and hit.scope_type == EXCEPTION_TYPE
    ]
    return {
        "condition_clause": condition_clause,
        "condition_span": [hit for hit in condition_clause if _ranges_overlap(span, hit)],
        "constraint_clause": constraint_clause,
        "constraint_span": [hit for hit in constraint_clause if _ranges_overlap(span, hit)],
        "exception_clause": exception_clause,
        "exception_span": [hit for hit in exception_clause if _ranges_overlap(span, hit)],
    }


def _target_equivalence(
    span: Mapping[str, Any], targets: Sequence[Mapping[str, Any]]
) -> str | None:
    start, end, _text, normalized = _span_value_key(span)
    for target in targets:
        ts, te, _tt, tn = _span_value_key(target)
        if start == ts and end == te and normalized == tn:
            return "exact_duplicate"
    for target in targets:
        if normalized == _span_value_key(target)[3]:
            return "normalized_duplicate"
    for target in targets:
        if _ranges_overlap(span, target):
            return "overlap_equivalent"
    return None


def _reindex_ownership_ids(clause: dict[str, Any]) -> None:
    clause_id = str(clause.get("clause_id") or "clause")
    for plural, singular in (("conditions", "condition"), ("constraints", "constraint")):
        ordered = sorted(
            clause.get(plural) or [],
            key=lambda row: (int(row["start"]), int(row["end"]), str(row["text"])),
        )
        for rank, span in enumerate(ordered, start=1):
            span["id"] = f"{clause_id}.{singular}.{rank}"
        clause[plural] = ordered


def apply_typed_ownership_to_clause(
    clause: Mapping[str, Any],
    source_text: str,
    lexicon: LexiconV2Runtime,
    *,
    enabled_directions: Iterable[str] = DIRECTION_ORDER,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]]:
    """Pure production-shaped rule; deliberately has no Gold or record-ID input."""
    enabled = frozenset(enabled_directions)
    if not enabled.issubset(DIRECTION_ORDER):
        raise B3bDiagnosticError("unknown ownership direction")
    result = deepcopy(dict(clause))
    stats: Counter[str] = Counter()
    events: list[dict[str, Any]] = []
    clause_span = result.get("clause_span")
    if not isinstance(clause_span, Mapping):
        return result, events, {"malformed_clause": 1}
    try:
        clause_start, clause_end = int(clause_span["start"]), int(clause_span["end"])
        clause_text = str(clause_span["text"])
    except (KeyError, TypeError, ValueError):
        return result, events, {"malformed_clause": 1}
    if (
        clause_start < 0
        or clause_end <= clause_start
        or clause_end > len(source_text)
        or source_text[clause_start:clause_end] != clause_text
    ):
        return result, events, {"malformed_clause": 1}
    typed_hits, evidence_errors = collect_clause_typed_hits(
        clause_text, clause_start, lexicon
    )
    if evidence_errors:
        return result, events, {"malformed_evidence": len(evidence_errors)}

    plans: list[dict[str, Any]] = []
    for source_field, target_field, direction in (
        ("constraints", "conditions", "constraint_to_condition"),
        ("conditions", "constraints", "condition_to_constraint"),
    ):
        if direction not in enabled:
            continue
        for source_index, span in enumerate(result.get(source_field) or []):
            malformed = _validate_span(span, source_text)
            if malformed:
                stats[malformed] += 1
                continue
            evidence = _strong_evidence(span, typed_hits)
            condition_any = bool(evidence["condition_clause"])
            constraint_any = bool(evidence["constraint_clause"])
            condition_span = bool(evidence["condition_span"])
            constraint_span = bool(evidence["constraint_span"])
            exception_any = bool(evidence["exception_clause"])
            if condition_span and constraint_span:
                stats["same_span_dual_typed_evidence"] += 1
            if condition_any and constraint_any:
                stats["ambiguous_parent_unchanged"] += 1
                events.append(
                    {
                        "direction": direction,
                        "source_field": source_field,
                        "target_field": target_field,
                        "source_index": source_index,
                        "operation": "ambiguous_parent_unchanged",
                        "span": span,
                    }
                )
                continue
            if exception_any:
                stats["exception_parent_unchanged"] += 1
                continue
            should_fire = (
                condition_any and not constraint_any
                if direction == "constraint_to_condition"
                else constraint_span and not condition_any
            )
            if not should_fire:
                stats["no_typed_evidence_parent_unchanged"] += 1
                continue
            stats[f"{direction}_fired"] += 1
            plans.append(
                {
                    "direction": direction,
                    "source_field": source_field,
                    "target_field": target_field,
                    "source_index": source_index,
                    "span": span,
                }
            )

    # Apply only plans built from the immutable parent lists, in a fixed order.
    for direction in DIRECTION_ORDER:
        for plan in [row for row in plans if row["direction"] == direction]:
            source_rows = result[plan["source_field"]]
            target_rows = result[plan["target_field"]]
            signature = _span_value_key(plan["span"])
            current_index = next(
                (
                    index
                    for index, row in enumerate(source_rows)
                    if _span_value_key(row) == signature
                ),
                None,
            )
            if current_index is None:
                stats["source_missing_fail_closed"] += 1
                continue
            equivalence = _target_equivalence(plan["span"], target_rows)
            event = {**plan, "operation": "moved"}
            if equivalence:
                source_rows.pop(current_index)
                stats["target_duplicate_suppressed"] += 1
                stats[f"target_{equivalence}"] += 1
                event["operation"] = "target_duplicate_suppressed"
                event["equivalence"] = equivalence
            elif len(target_rows) >= TARGET_CAPACITY:
                stats["target_capacity_fail_closed"] += 1
                event["operation"] = "target_capacity_fail_closed"
            else:
                moved = source_rows.pop(current_index)
                target_rows.append(moved)
                stats[direction] += 1
            events.append(event)

    _reindex_ownership_ids(result)
    return result, events, dict(sorted(stats.items()))


def apply_typed_ownership_attempts(
    attempts: Sequence[Mapping[str, Any]],
    lexicon: LexiconV2Runtime,
    *,
    enabled_directions: Iterable[str] = DIRECTION_ORDER,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    changed_keys: set[tuple[str, int, str, int, int]] = set()
    changed_records: set[str] = set()
    aggregate: Counter[str] = Counter()
    result: list[dict[str, Any]] = []
    for attempt in attempts:
        candidate = deepcopy(dict(attempt))
        sample_id = str(candidate["sample_id"])
        record = candidate["record"]
        source_text = str(record["source_text"])
        for clause_index, clause in enumerate(record.get("clauses") or []):
            before = deepcopy(clause)
            after, events, stats = apply_typed_ownership_to_clause(
                clause,
                source_text,
                lexicon,
                enabled_directions=enabled_directions,
            )
            aggregate.update(stats)
            record["clauses"][clause_index] = after
            for event in events:
                if event["operation"] not in {
                    "moved",
                    "target_duplicate_suppressed",
                }:
                    continue
                span = event["span"]
                key = (
                    sample_id,
                    clause_index,
                    event["source_field"],
                    int(span["start"]),
                    int(span["end"]),
                )
                changed_keys.add(key)
                changed_records.add(sample_id)
            # Absolute non-target field lock.
            for key in before:
                if key not in {"conditions", "constraints"} and after.get(key) != before.get(key):
                    raise B3bDiagnosticError(f"non-target clause field changed: {key}")
        result.append(candidate)
    required_count_keys = (
        "constraint_to_condition_fired",
        "condition_to_constraint_fired",
        "constraint_to_condition",
        "condition_to_constraint",
        "ambiguous_parent_unchanged",
        "same_span_dual_typed_evidence",
        "exception_parent_unchanged",
        "no_typed_evidence_parent_unchanged",
        "target_duplicate_suppressed",
        "target_exact_duplicate",
        "target_normalized_duplicate",
        "target_overlap_equivalent",
        "target_capacity_fail_closed",
    )
    counts = {key: int(aggregate.get(key, 0)) for key in required_count_keys}
    counts.update(aggregate)
    return result, {
        "counts": dict(sorted(counts.items())),
        "changed_unique_spans": len(changed_keys),
        "changed_unique_records": len(changed_records),
        "ambiguous_parent_unchanged_rate": 1.0,
        "changed_span_opaque_hashes": sorted(_opaque_hash(key) for key in changed_keys),
    }


def _raw_span_multiset(attempts: Sequence[Mapping[str, Any]]) -> Counter[tuple[Any, ...]]:
    rows: Counter[tuple[Any, ...]] = Counter()
    for attempt in attempts:
        sample_id = str(attempt["sample_id"])
        for clause_index, clause in enumerate(attempt["record"].get("clauses") or []):
            for field in ("conditions", "constraints"):
                for span in clause.get(field) or []:
                    rows[(sample_id, clause_index, *_span_value_key(span))] += 1
    return rows


def _assert_route_purity(
    parent: Sequence[Mapping[str, Any]], candidate: Sequence[Mapping[str, Any]]
) -> dict[str, int | bool]:
    if len(parent) != len(candidate):
        raise B3bDiagnosticError("attempt count changed")
    boundary_changes = 0
    non_target_changes = 0
    for before, after in zip(parent, candidate, strict=True):
        if before["sample_id"] != after["sample_id"]:
            raise B3bDiagnosticError("attempt identity/order changed")
        br, ar = before["record"], after["record"]
        for key in br:
            if key != "clauses" and br.get(key) != ar.get(key):
                non_target_changes += 1
        if len(br.get("clauses") or []) != len(ar.get("clauses") or []):
            boundary_changes += 1
            continue
        for bc, ac in zip(br["clauses"], ar["clauses"], strict=True):
            if bc.get("clause_span") != ac.get("clause_span"):
                boundary_changes += 1
            for key in bc:
                if key not in {"conditions", "constraints"} and bc.get(key) != ac.get(key):
                    non_target_changes += 1
    before_raw = _raw_span_multiset(parent)
    after_raw = _raw_span_multiset(candidate)
    new_raw = sum((after_raw - before_raw).values())
    return {
        "span_boundary_changes": boundary_changes,
        "new_raw_spans": new_raw,
        "non_target_field_changes": non_target_changes,
        "other_fields_exact": non_target_changes == 0,
        "sample_specific_logic": False,
    }


def _metric_delta(parent: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: candidate[key] - parent[key]
        for key in ("tp", "fp", "fn", "precision", "recall", "f1")
    }


def _assignment_state(
    gold_records: Sequence[Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, set[tuple[Any, ...]]]]:
    state = {
        field: {"tp_gold": set(), "tp_pred": set(), "fp": set(), "fn": set()}
        for field in ("condition", "constraint")
    }
    plural = {"condition": "conditions", "constraint": "constraints"}
    gold_by_id = {str(row["sample_id"]): row for row in gold_records}
    for attempt in attempts:
        sample_id = str(attempt["sample_id"])
        gold = gold_by_id[sample_id]
        predicted = attempt["record"]
        pairs, extra_gold, extra_pred, _ = clause_iou_pairs(
            gold.get("clauses") or [],
            predicted.get("clauses") or [],
            minimum_iou=CLAUSE_MINIMUM_IOU,
        )
        for gold_clause_index, predicted_clause_index in pairs:
            for field in plural:
                gold_spans = list(gold["clauses"][gold_clause_index].get(plural[field]) or [])
                pred_spans = list(predicted["clauses"][predicted_clause_index].get(plural[field]) or [])
                used: set[int] = set()
                for gold_index, gold_span in enumerate(gold_spans):
                    hit = next(
                        (
                            pred_index
                            for pred_index, pred_span in enumerate(pred_spans)
                            if pred_index not in used and _char_iou(gold_span, pred_span) > 0.0
                        ),
                        None,
                    )
                    gold_key = (
                        sample_id,
                        gold_clause_index,
                        field,
                        int(gold_span["start"]),
                        int(gold_span["end"]),
                    )
                    if hit is None:
                        state[field]["fn"].add(gold_key)
                    else:
                        used.add(hit)
                        pred_span = pred_spans[hit]
                        pred_key = (
                            sample_id,
                            predicted_clause_index,
                            field,
                            int(pred_span["start"]),
                            int(pred_span["end"]),
                        )
                        state[field]["tp_gold"].add(gold_key)
                        state[field]["tp_pred"].add(pred_key)
                for pred_index, pred_span in enumerate(pred_spans):
                    if pred_index not in used:
                        state[field]["fp"].add(
                            (
                                sample_id,
                                predicted_clause_index,
                                field,
                                int(pred_span["start"]),
                                int(pred_span["end"]),
                            )
                        )
        for gold_clause_index in extra_gold:
            for field in plural:
                for span in gold["clauses"][gold_clause_index].get(plural[field]) or []:
                    state[field]["fn"].add(
                        (
                            sample_id,
                            gold_clause_index,
                            field,
                            int(span["start"]),
                            int(span["end"]),
                        )
                    )
        for predicted_clause_index in extra_pred:
            for field in plural:
                for span in predicted["clauses"][predicted_clause_index].get(plural[field]) or []:
                    state[field]["fp"].add(
                        (
                            sample_id,
                            predicted_clause_index,
                            field,
                            int(span["start"]),
                            int(span["end"]),
                        )
                    )
    return state


def _transition_counts(
    before: Mapping[str, Mapping[str, set[tuple[Any, ...]]]],
    after: Mapping[str, Mapping[str, set[tuple[Any, ...]]]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    totals: Counter[str] = Counter()
    for field in ("condition", "constraint"):
        row = {
            "tp_gain": len(after[field]["tp_gold"] - before[field]["tp_gold"]),
            "tp_loss": len(before[field]["tp_gold"] - after[field]["tp_gold"]),
            "fp_removed": len(before[field]["fp"] - after[field]["fp"]),
            "fp_added": len(after[field]["fp"] - before[field]["fp"]),
            "fn_removed": len(before[field]["fn"] - after[field]["fn"]),
            "fn_added": len(after[field]["fn"] - before[field]["fn"]),
        }
        result[field] = row
        totals.update(row)
    result["combined"] = dict(totals)
    return result


def _evaluate(
    gold: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    evaluator_contract: dict[str, Any],
) -> dict[str, Any]:
    report = evaluate_stage2(
        gold,
        attempts,
        contract=evaluator_contract,
        dataset_id="independently_reconstructed_estg_150_v1",
        method_id="sun_rule_only",
        expected_membership_sha256=membership_sha256(gold),
        claim_scope="development",
        formal_ready=False,
    )
    errors = validate_evaluation_report(report)
    if errors:
        raise B3bDiagnosticError("candidate evaluation invalid: " + "; ".join(errors))
    return report


def _replay_parent_sources(
    source_records: Sequence[Mapping[str, Any]],
    parent_attempts: Sequence[Mapping[str, Any]],
    lexicon: LexiconV2Runtime,
    runtime_home: Path,
    work_dir: Path,
) -> tuple[dict[str, Any], dict[tuple[str, int], list[TypedHit]]]:
    annotations, cases_by_id, runtime = run_corenlp_batch_v10(
        ROOT,
        source_records,
        runtime_home=runtime_home,
        work_dir=work_dir,
        patterns_rel="resources/corenlp/sun_phrase_patterns_v3_enhanced.json",
    )
    parent_by_id = {str(row["sample_id"]): row for row in parent_attempts}
    source_counts = {
        "condition": Counter({"tregex": 0, "lexicon": 0, "dependency_fallback": 0}),
        "constraint": Counter({"tregex": 0, "lexicon": 0, "dependency_fallback": 0}),
    }
    scope_distribution = {
        "condition": Counter(),
        "constraint": Counter(),
        "exception": Counter(),
    }
    typed_hits_by_clause: dict[tuple[str, int], list[TypedHit]] = {}
    replay_mismatches = 0
    replayed_span_count = 0
    for source in source_records:
        sample_id = str(source["sample_id"])
        source_text = str(source["approved_text_en"])
        annotation = annotations[sample_id]
        cases = cases_by_id[sample_id]
        cases_by_sentence = {int(row["sentence_index"]): row for row in cases}
        clause_units, _seg_stats = plan_clause_units_v4(annotation, source_text)
        parent_clauses = parent_by_id[sample_id]["record"]["clauses"]
        if len(clause_units) != len(parent_clauses):
            raise B3bDiagnosticError("parent clause replay count mismatch")
        for clause_index, unit in enumerate(clause_units):
            clause_start, clause_end = unit["clause_char_span"]
            clause_text = source_text[clause_start:clause_end]
            tregex_obs: dict[str, list[Any]] = {
                field: []
                for field in ("modality", "actor", "action", "condition", "constraint", "exception")
            }
            for sentence_index in unit["sentence_indexes"]:
                fields = cases_by_sentence.get(sentence_index, {}).get("fields", {})
                sentence = annotation["sentences"][sentence_index]
                for field in tregex_obs:
                    values = fields.get(field) or []
                    if isinstance(values, Mapping):
                        values = [values]
                    for observation in values:
                        if isinstance(observation, Mapping):
                            tregex_obs[field].append((sentence, observation))
            scope, _decisions, _stats = resolve_scope_fields_v10(
                clause_text=clause_text,
                clause_start=clause_start,
                source_text=source_text,
                lexicon=lexicon,
                tregex_obs=tregex_obs,
            )
            hits, errors = collect_clause_typed_hits(clause_text, clause_start, lexicon)
            if errors:
                raise B3bDiagnosticError("malformed lexicon evidence during parent replay")
            typed_hits_by_clause[(sample_id, clause_index)] = hits
            for hit in hits:
                scope_distribution[hit.field][hit.scope_type] += 1
            parent_clause = parent_clauses[clause_index]
            for singular, plural in (("condition", "conditions"), ("constraint", "constraints")):
                replay_spans = scope[singular]
                parent_spans = parent_clause.get(plural) or []
                replayed_span_count += len(replay_spans)
                if [_span_value_key(row) for row in replay_spans] != [
                    _span_value_key(row) for row in parent_spans
                ]:
                    replay_mismatches += 1
                    continue
                for row in replay_spans:
                    source = str(row.get("source") or "")
                    category = (
                        "tregex"
                        if source == "tregex"
                        else "lexicon"
                        if source == "lexicon_v2_typed_scope"
                        else "dependency_fallback"
                    )
                    source_counts[singular][category] += 1
    if replay_mismatches:
        raise B3bDiagnosticError(
            f"parent scope replay mismatch in {replay_mismatches} field/clauses"
        )
    return (
        {
            "runtime": runtime,
            "parent_scope_replay_exact": True,
            "replayed_condition_constraint_span_count": replayed_span_count,
            "source_counts": {
                field: dict(sorted(counts.items())) for field, counts in source_counts.items()
            },
            "typed_scope_hit_distribution": {
                field: dict(sorted(counts.items()))
                for field, counts in scope_distribution.items()
            },
        },
        typed_hits_by_clause,
    )


def _typed_span_distribution(
    attempts: Sequence[Mapping[str, Any]],
    hits_by_clause: Mapping[tuple[str, int], Sequence[TypedHit]],
) -> dict[str, Any]:
    distribution = {
        "condition": Counter(),
        "constraint": Counter(),
    }
    same_span_dual = 0
    for attempt in attempts:
        sample_id = str(attempt["sample_id"])
        for clause_index, clause in enumerate(attempt["record"].get("clauses") or []):
            typed_hits = hits_by_clause[(sample_id, clause_index)]
            for singular, plural in (("condition", "conditions"), ("constraint", "constraints")):
                for span in clause.get(plural) or []:
                    evidence = _strong_evidence(span, typed_hits)
                    types = {
                        hit.scope_type
                        for key in ("condition_span", "constraint_span", "exception_span")
                        for hit in evidence[key]
                    }
                    if not types:
                        distribution[singular]["no_typed_span_evidence"] += 1
                    for scope_type in types:
                        distribution[singular][scope_type] += 1
                    if evidence["condition_span"] and evidence["constraint_span"]:
                        same_span_dual += 1
    return {
        "parent_span_typed_distribution": {
            field: dict(sorted(counts.items())) for field, counts in distribution.items()
        },
        "same_span_condition_and_constraint_strong_evidence_count": same_span_dual,
    }


def _binding(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def _check_hashes() -> None:
    paths = {
        "parent_manifest": PARENT_MANIFEST,
        "scope_resolver": SCOPE_RESOLVER,
        "lexicon_manifest": LEXICON_MANIFEST,
        "evaluator": EVALUATOR,
        "b3a_v2": B3A_V2,
        "active_registry": ACTIVE_REGISTRY,
        "tregex_registry": TREGEX_REGISTRY,
        "production_bridge": PRODUCTION_BRIDGE,
    }
    for label, path in paths.items():
        actual = sha256_file(path)
        if actual != EXPECTED_HASHES[label]:
            raise B3bDiagnosticError(
                f"fixed hash mismatch for {label}: {actual} != {EXPECTED_HASHES[label]}"
            )


def _parent_exact(parent_table8: Mapping[str, Any]) -> None:
    expected = {
        "condition": (130, 115, 84),
        "constraint": (126, 209, 176),
    }
    for field, values in expected.items():
        row = parent_table8["per_field"][field]
        if (row["tp"], row["fp"], row["fn"]) != values:
            raise B3bDiagnosticError(f"fixed parent Table8 mismatch for {field}")
    overall = parent_table8["overall"]
    if (overall["tp"], overall["fp"], overall["fn"]) != (458, 415, 366):
        raise B3bDiagnosticError("fixed parent overall Table8 mismatch")


def _gate(name: str, observed: Any, passed: bool, requirement: str) -> dict[str, Any]:
    return {
        "gate": name,
        "observed": observed,
        "requirement": requirement,
        "passed": bool(passed),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-home", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        output_dir = args.output_dir.resolve()
        try:
            output_dir.relative_to((ROOT / "outputs/development").resolve())
        except ValueError as exc:
            raise B3bDiagnosticError("diagnostic output must remain under outputs/development") from exc
        if output_dir.exists():
            raise B3bDiagnosticError(f"refusing to overwrite: {output_dir}")
        _check_hashes()
        parent_manifest = load_object(PARENT_MANIFEST)
        parent_attempts = json.loads(PARENT_ATTEMPTS.read_text(encoding="utf-8"))
        if not isinstance(parent_attempts, list):
            raise B3bDiagnosticError("parent attempts root must be an array")
        parent_table8 = load_object(PARENT_TABLE8)
        parent_evaluation = load_object(PARENT_EVALUATION)
        _parent_exact(parent_table8)
        if sha256_file(PARENT_ATTEMPTS) != parent_manifest["artifacts"]["attempts"]["sha256"]:
            raise B3bDiagnosticError("parent attempts binding mismatch")
        config = load_object(PARENT_CONFIG)
        layer_e = ROOT / config["inputs"]["human_correction_layer_e"]["path"]
        membership = ROOT / config["inputs"]["membership_hashes"]["path"]
        if sha256_file(layer_e) != config["inputs"]["human_correction_layer_e"]["sha256"]:
            raise B3bDiagnosticError("Layer E binding mismatch")
        if sha256_file(membership) != config["inputs"]["membership_hashes"]["sha256"]:
            raise B3bDiagnosticError("membership binding mismatch")
        lexicon = load_lexicon_v2(ROOT)

        # Rule constants and hash above are fixed before this Gold load.
        gold, source_records = build_canonical_gold_records(layer_e, membership)
        evaluator_contract = load_evaluator_contract(EVALUATOR)
        ROOT.joinpath(".tmp").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"{RUN_ID}-", dir=ROOT / ".tmp") as raw_work:
            replay, typed_hits_by_clause = _replay_parent_sources(
                source_records,
                parent_attempts,
                lexicon,
                args.runtime_home.resolve(),
                Path(raw_work),
            )

        span_distribution = _typed_span_distribution(parent_attempts, typed_hits_by_clause)
        parent_assignment = _assignment_state(gold, parent_attempts)
        direction_reports: dict[str, Any] = {}
        for direction in DIRECTION_ORDER:
            directional, directional_trace = apply_typed_ownership_attempts(
                parent_attempts, lexicon, enabled_directions=(direction,)
            )
            directional_table8 = sun_table8_any_overlap_diagnostic(gold, directional)
            direction_reports[direction] = {
                "ownership": directional_trace,
                "table8": {
                    "condition": directional_table8["per_field"]["condition"],
                    "constraint": directional_table8["per_field"]["constraint"],
                    "overall": directional_table8["overall"],
                },
                "instance_transitions": _transition_counts(
                    parent_assignment, _assignment_state(gold, directional)
                ),
            }

        candidate_attempts, ownership = apply_typed_ownership_attempts(
            parent_attempts, lexicon
        )
        route_purity = _assert_route_purity(parent_attempts, candidate_attempts)
        candidate_table8 = sun_table8_any_overlap_diagnostic(gold, candidate_attempts)
        candidate_evaluation = _evaluate(gold, candidate_attempts, evaluator_contract)
        if sun_table8_any_overlap_diagnostic(gold, parent_attempts) != parent_table8:
            raise B3bDiagnosticError("parent Table8 reproduction mismatch")

        table8 = {
            "parent": {
                "condition": parent_table8["per_field"]["condition"],
                "constraint": parent_table8["per_field"]["constraint"],
                "overall": parent_table8["overall"],
            },
            "opportunity": {
                "condition": candidate_table8["per_field"]["condition"],
                "constraint": candidate_table8["per_field"]["constraint"],
                "overall": candidate_table8["overall"],
            },
            "delta": {
                "condition": _metric_delta(
                    parent_table8["per_field"]["condition"],
                    candidate_table8["per_field"]["condition"],
                ),
                "constraint": _metric_delta(
                    parent_table8["per_field"]["constraint"],
                    candidate_table8["per_field"]["constraint"],
                ),
                "overall": _metric_delta(
                    parent_table8["overall"], candidate_table8["overall"]
                ),
            },
        }
        parent_coverage = parent_evaluation["semantic_coverage"]
        opportunity_coverage = candidate_evaluation["semantic_coverage"]
        coverage = {
            "parent": {
                key: parent_coverage[key]
                for key in (
                    "hallucinated_field_rate",
                    "gold_required_presence_recall",
                    "complete_record_rate",
                    "schema_valid_rate",
                )
            },
            "opportunity": {
                key: opportunity_coverage[key]
                for key in (
                    "hallucinated_field_rate",
                    "gold_required_presence_recall",
                    "complete_record_rate",
                    "schema_valid_rate",
                )
            },
        }
        coverage["delta"] = {
            key: coverage["opportunity"][key] - coverage["parent"][key]
            for key in coverage["parent"]
        }

        condition_parent = table8["parent"]["condition"]
        condition_new = table8["opportunity"]["condition"]
        constraint_parent = table8["parent"]["constraint"]
        constraint_new = table8["opportunity"]["constraint"]
        overall_parent = table8["parent"]["overall"]
        overall_new = table8["opportunity"]["overall"]
        changed = ownership["changed_unique_spans"]
        counts = ownership["counts"]
        ambiguous_rate = ownership["ambiguous_parent_unchanged_rate"]
        gates = [
            _gate("changed_spans", changed, 10 <= changed <= 60, "10..60"),
            _gate("only_condition_constraint", route_purity["other_fields_exact"], route_purity["other_fields_exact"] is True, "true"),
            _gate("span_boundary_changes", route_purity["span_boundary_changes"], route_purity["span_boundary_changes"] == 0, "0"),
            _gate("new_raw_spans", route_purity["new_raw_spans"], route_purity["new_raw_spans"] == 0, "0"),
            _gate("sample_specific_logic", route_purity["sample_specific_logic"], route_purity["sample_specific_logic"] is False, "false"),
            _gate("ambiguous_parent_unchanged", ambiguous_rate, ambiguous_rate == 1.0, "100% unchanged"),
            _gate("constraint_fp_reduction", constraint_parent["fp"] - constraint_new["fp"], constraint_parent["fp"] - constraint_new["fp"] >= 15, ">=15"),
            _gate("constraint_tp_loss", max(constraint_parent["tp"] - constraint_new["tp"], 0), max(constraint_parent["tp"] - constraint_new["tp"], 0) <= 2, "<=2"),
            _gate("condition_tp_gain", condition_new["tp"] - condition_parent["tp"], condition_new["tp"] - condition_parent["tp"] >= 3, ">=3"),
            _gate("condition_fp_increase", max(condition_new["fp"] - condition_parent["fp"], 0), max(condition_new["fp"] - condition_parent["fp"], 0) <= 5, "<=5"),
            _gate("overall_tp_gain", overall_new["tp"] - overall_parent["tp"], overall_new["tp"] - overall_parent["tp"] >= 3, ">=3"),
            _gate("overall_fp_reduction", overall_parent["fp"] - overall_new["fp"], overall_parent["fp"] - overall_new["fp"] >= 12, ">=12"),
            _gate("overall_f1_lift", overall_new["f1"] - overall_parent["f1"], overall_new["f1"] - overall_parent["f1"] >= 0.008, ">=0.008"),
            _gate("condition_f1_non_decrease", condition_new["f1"] - condition_parent["f1"], condition_new["f1"] >= condition_parent["f1"], ">=0"),
            _gate("constraint_f1_lift", constraint_new["f1"] - constraint_parent["f1"], constraint_new["f1"] - constraint_parent["f1"] >= 0.008, ">=0.008"),
            _gate("hallucinated_field_rate_nonincrease", coverage["delta"]["hallucinated_field_rate"], coverage["delta"]["hallucinated_field_rate"] <= 0.0, "<=0"),
            _gate("presence_recall_drop", max(-coverage["delta"]["gold_required_presence_recall"], 0.0), max(-coverage["delta"]["gold_required_presence_recall"], 0.0) <= 0.005, "<=0.005"),
            _gate("complete_record_drop", max(-coverage["delta"]["complete_record_rate"], 0.0), max(-coverage["delta"]["complete_record_rate"], 0.0) <= 0.01, "<=0.01"),
        ]
        eligible = all(row["passed"] for row in gates)
        decision = "eligible_for_production_instantiation" if eligible else "not_instantiated"

        diagnostic = {
            "schema_version": "b3b_typed_ownership_diagnostic@1.0.0",
            "run_id": RUN_ID,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "complete",
            "claim_scope": "development_gold_opportunity_diagnostic_only",
            "is_independent_generalization_result": False,
            "is_formal_performance_result": False,
            "algorithm": RULE_SPEC,
            "rule_spec_sha256": RULE_SPEC_SHA256,
            "parent_source_replay": replay,
            "typed_evidence": span_distribution,
            "ownership": ownership,
            "route_purity": route_purity,
            "direction_reports": direction_reports,
            "table8": table8,
            "coverage": coverage,
            "instantiation_gates": gates,
            "all_instantiation_gates_passed": eligible,
            "decision": decision,
            "candidate_all150_run": False,
            "production_candidate_created": False,
            "safety": {
                "gold_read_only": True,
                "sample_id_allowlist_persisted": False,
                "independent82_read_or_used": False,
                "s2_4_test_read": False,
                "network_called": False,
                "llm_api_called": False,
                "modality_classifier_run": False,
                "tsurgeon_enabled": False,
                "b3a_candidate_patterns_used": False,
                "lexicon_modified": False,
                "tregex_modified": False,
                "production_bridge_modified": False,
                "active_registry_modified": False,
                "b3c_started": False,
                "actor_stage_started": False,
                "bert_stage_started": False,
            },
        }
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
        if staging.exists():
            raise B3bDiagnosticError(f"staging path exists: {staging}")
        staging.mkdir()
        try:
            diagnostic_path = staging / "diagnostic.json"
            diagnostic_path.write_text(
                json.dumps(diagnostic, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            manifest = {
                "schema_version": "b3b_typed_ownership_diagnostic_manifest@1.0.0",
                "run_id": RUN_ID,
                "status": "complete",
                "decision": decision,
                "all_instantiation_gates_passed": eligible,
                "claim_scope": diagnostic["claim_scope"],
                "is_formal_performance_result": False,
                "bindings": {
                    "parent_manifest": _binding(PARENT_MANIFEST),
                    "parent_attempts": _binding(PARENT_ATTEMPTS),
                    "parent_table8": _binding(PARENT_TABLE8),
                    "scope_resolver": _binding(SCOPE_RESOLVER),
                    "lexicon_manifest": _binding(LEXICON_MANIFEST),
                    "evaluator": _binding(EVALUATOR),
                    "b3a_correction_v2_diagnostic_evidence_only": _binding(B3A_V2),
                    "active_registry_read_only": _binding(ACTIVE_REGISTRY),
                    "tregex_registry": _binding(TREGEX_REGISTRY),
                    "production_bridge": _binding(PRODUCTION_BRIDGE),
                },
                "rule_spec_sha256": RULE_SPEC_SHA256,
                "artifact": {
                    "path": "diagnostic.json",
                    "sha256": sha256_file(diagnostic_path),
                    "bytes": diagnostic_path.stat().st_size,
                },
                "safety": diagnostic["safety"],
            }
            (staging / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            staging.rename(output_dir)
        except Exception:
            import shutil

            shutil.rmtree(staging, ignore_errors=True)
            raise
        _check_hashes()
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "decision": decision,
                    "changed_unique_spans": changed,
                    "changed_unique_records": ownership["changed_unique_records"],
                    "ownership_counts": counts,
                    "table8_delta": table8["delta"],
                    "coverage_delta": coverage["delta"],
                    "failed_gates": [row["gate"] for row in gates if not row["passed"]],
                    "manifest_sha256": sha256_file(output_dir / "manifest.json"),
                    "candidate_all150_run": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (B3bDiagnosticError, KeyError, TypeError, ValueError, OSError) as exc:
        print(f"B3b typed ownership diagnostic failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
