"""Build a deterministic, Gold-blind H1 clause/field diagnostics table.

The generator consumes the *same persisted B0 prediction artifact* and its
manifest that the H1 runner binds (shared ``bpc_hybrid.b0_artifact`` loader),
plus the inference-visible B0 telemetry embedded in the attempts (per-clause
alignment, scope stats, modality route, and modality diagnostics).  It emits
one JSONL row per clause, sorted by ``sample_id`` then ``clause_index``, with
only inference-visible features:

* identity and input/B0-prediction hashes (never the full source text or
  span texts);
* clause_span length and share of source_text;
* modality classifier / marker / alignment labels, status, confidence, and
  classifier-marker disagreement;
* span counts per semantic field, relation counts and reference validity;
* per-span integrity flags (inside clause_span, ``text == source[start:end]``,
  empty values, duplicate / cross-field-colliding IDs, extents);
* span lengths and clause coverage ratios, same-field and cross-field overlap;
* non-definition missing actor/action flags;
* scope raw/accepted/rejected telemetry;
* schema / cross-field / offline Stage 3 adapter validation status;
* a per-feature missing indicator map.

Data-cleaning discipline:

* source_text, clause_span, and B0 predictions are never modified;
* missing values are never auto-filled or coerced to 0;
* malformed input fails closed at the loader (no silent type casts);
* no rows are ever dropped: coverage accounting (expected attempts, loaded
  samples, written clause rows) is always emitted in the manifest;
* the output contains hashes, numbers, and flags only -- it is not a
  parallel copy of the prediction data.

Determinism: rows and the manifest contain no timestamps or randomness;
re-running on identical inputs yields byte-identical outputs.

This script is offline: it never calls an LLM/API, never reads Gold, Layer E,
paper_validation, or ``.env``, and never modifies B0.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.b0_artifact import (  # noqa: E402
    B0ArtifactError,
    LoadedB0,
    json_hash,
    load_b0_predictions,
    prediction_hash,
    read_json_values,
    sha256_bytes,
    sha256_file,
    verify_b0_manifest,
)
from bpc_hybrid.stage2_canonical import VALID_MODALITIES, validate_canonical  # noqa: E402
from formal_experiment.audit import collect_project_audit  # noqa: E402
from formal_experiment.paths import (  # noqa: E402
    FORMAL_PREDICTIONS_DIR,
    FORMAL_RESULTS_DIR,
    FROZEN_GOLD_DIR,
    FROZEN_INPUT_DIR,
)

FEATURE_VERSION = "h1_trigger_diagnostic_features@1.0.0"
MANIFEST_VERSION = "h1_trigger_diagnostics_manifest@1.0.0"
SPAN_FIELDS = ("actors", "actions", "conditions", "constraints", "exceptions")
RELATION_FIELDS = ("actor_action_map", "order_relations")
SPAN_TEXT_JOIN = "; "

_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "outputs" / "development" / "s28a_h1_trigger_diagnostics_v1"
_DEFAULT_OUTPUT = _DEFAULT_OUTPUT_DIR / "h1_trigger_diagnostics.jsonl"
_DEFAULT_MANIFEST = _DEFAULT_OUTPUT_DIR / "manifest.json"

FORMAL_DIRS = (
    FROZEN_INPUT_DIR,
    FROZEN_GOLD_DIR,
    FORMAL_PREDICTIONS_DIR,
    FORMAL_RESULTS_DIR,
)

# Offline Stage 3 adapter availability is resolved once per process.
_STAGE3_ADAPTER = None
_STAGE3_ADAPTER_AVAILABLE = False
_STAGE3_ADAPTER_ERROR: str | None = None
try:
    from bpc_hybrid.sun_compat.clause_adapter import ClauseAdapter as _ClauseAdapter

    _STAGE3_ADAPTER = _ClauseAdapter()
    _STAGE3_ADAPTER_AVAILABLE = True
except Exception as exc:  # noqa: BLE001 -- offline feature availability only
    _STAGE3_ADAPTER_ERROR = f"{type(exc).__name__}: {exc}"


class DiagnosticsError(ValueError):
    """Raised for a fail-closed diagnostics input or write violation."""


# ---------------------------------------------------------------------------
# Structural feature computation (inference-visible only)
# ---------------------------------------------------------------------------


def _span_key(span: Mapping[str, Any]) -> tuple[int, int] | None:
    start, end = span.get("start"), span.get("end")
    if not isinstance(start, int) or not isinstance(end, int):
        return None
    return (start, end)


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def analyze_clause_structure(clause: Mapping[str, Any], source_text: str) -> dict[str, Any]:
    """Compute per-span integrity flags, counts, lengths, and overlaps.

    Values are recomputed from the loaded (canonical) clause; anything the
    canonical validator guarantees is still re-verified here so the table is
    a tripwire for future B0 versions.
    """
    source_len = len(source_text)
    clause_span = clause.get("clause_span") or {}
    cs_start, cs_end = clause_span.get("start"), clause_span.get("end")
    clause_span_ok = (
        isinstance(cs_start, int)
        and isinstance(cs_end, int)
        and 0 <= cs_start < cs_end
        and cs_end <= source_len
    )

    per_field: dict[str, dict[str, Any]] = {}
    all_spans: list[tuple[str, Mapping[str, Any], tuple[int, int] | None]] = []
    id_usage: dict[str, list[str]] = {}
    for field in SPAN_FIELDS:
        items = clause.get(field)
        stats = {
            "total": 0,
            "empty_text": 0,
            "invalid_extent": 0,
            "outside_clause": 0,
            "text_mismatch": 0,
            "id_missing": 0,
            "normalized_missing": 0,
            "lengths": [],
        }
        if isinstance(items, list):
            for span in items:
                if not isinstance(span, Mapping):
                    continue
                stats["total"] += 1
                text = span.get("text")
                start, end = span.get("start"), span.get("end")
                if not isinstance(text, str) or text == "":
                    stats["empty_text"] += 1
                valid_extent = (
                    isinstance(start, int)
                    and isinstance(end, int)
                    and 0 <= start < end
                    and end <= source_len
                )
                if not valid_extent:
                    stats["invalid_extent"] += 1
                else:
                    if clause_span_ok and not (cs_start <= start and end <= cs_end):
                        stats["outside_clause"] += 1
                    if isinstance(text, str) and source_text[start:end] != text:
                        stats["text_mismatch"] += 1
                    stats["lengths"].append(end - start)
                sid = span.get("id")
                if not isinstance(sid, str) or sid == "":
                    stats["id_missing"] += 1
                if not isinstance(span.get("normalized"), str) or span.get("normalized") == "":
                    stats["normalized_missing"] += 1
                if isinstance(sid, str) and sid:
                    id_usage.setdefault(sid, []).append(field)
                all_spans.append((field, span, _span_key(span)))
        per_field[field] = stats

    lengths = [length for stats in per_field.values() for length in stats["lengths"]]
    n_spans = len(lengths)

    duplicate_ids = sum(
        len(fields) - 1 for fields in id_usage.values() if len(fields) > 1
    )
    collision_ids = sorted(
        sid for sid, fields in id_usage.items() if len(set(fields)) > 1
    )

    same_field_pairs: dict[str, int] = {}
    for field in SPAN_FIELDS:
        keys = [
            key for span_field, _, key in all_spans if span_field == field and key is not None
        ]
        same_field_pairs[field] = sum(
            1 for i in range(len(keys)) for j in range(i + 1, len(keys))
            if _overlap(keys[i], keys[j])
        )
    cross_field_pairs = 0
    for i in range(len(all_spans)):
        for j in range(i + 1, len(all_spans)):
            field_i, _, key_i = all_spans[i]
            field_j, _, key_j = all_spans[j]
            if field_i == field_j or key_i is None or key_j is None:
                continue
            if _overlap(key_i, key_j):
                cross_field_pairs += 1

    span_length_sum = sum(lengths)
    return {
        "per_field": per_field,
        "n_spans_total": n_spans,
        "span_text_empty_count": sum(s["empty_text"] for s in per_field.values()),
        "span_extent_invalid_count": sum(s["invalid_extent"] for s in per_field.values()),
        "span_outside_clause_count": sum(s["outside_clause"] for s in per_field.values()),
        "span_text_mismatch_count": sum(s["text_mismatch"] for s in per_field.values()),
        "span_id_missing_count": sum(s["id_missing"] for s in per_field.values()),
        "normalized_missing_count": sum(s["normalized_missing"] for s in per_field.values()),
        "span_id_duplicate_count": duplicate_ids,
        "span_id_cross_field_collision_count": len(collision_ids),
        "span_id_collision_fields": sorted({f for sid in collision_ids for f in id_usage[sid]}),
        "span_length_min": min(lengths) if lengths else None,
        "span_length_max": max(lengths) if lengths else None,
        "span_length_sum": span_length_sum,
        "span_length_mean": (span_length_sum / n_spans) if n_spans else None,
        "same_field_overlap_pairs": sum(same_field_pairs.values()),
        "same_field_overlap_by_field": same_field_pairs,
        "cross_field_overlap_pairs": cross_field_pairs,
    }


def analyze_relations(clause: Mapping[str, Any]) -> dict[str, Any]:
    actor_ids = {
        span.get("id")
        for span in clause.get("actors", [])
        if isinstance(span, Mapping) and isinstance(span.get("id"), str)
    }
    action_ids = {
        span.get("id")
        for span in clause.get("actions", [])
        if isinstance(span, Mapping) and isinstance(span.get("id"), str)
    }
    invalid: list[str] = []

    edges = clause.get("actor_action_map", [])
    if isinstance(edges, list):
        for index, edge in enumerate(edges):
            if not isinstance(edge, Mapping):
                invalid.append(f"actor_action_map[{index}] not an object")
                continue
            actor_id = edge.get("actor_id")
            action_id = edge.get("action_id")
            if actor_id is not None and actor_id not in actor_ids:
                invalid.append(f"actor_action_map[{index}].actor_id={actor_id!r}")
            if action_id not in action_ids:
                invalid.append(f"actor_action_map[{index}].action_id={action_id!r}")

    relations = clause.get("order_relations", [])
    if isinstance(relations, list):
        for index, rel in enumerate(relations):
            if not isinstance(rel, Mapping):
                invalid.append(f"order_relations[{index}] not an object")
                continue
            for key in ("before_action_id", "after_action_id"):
                rid = rel.get(key)
                if rid not in action_ids:
                    invalid.append(f"order_relations[{index}].{key}={rid!r}")

    return {
        "actor_action_map_count": len(edges) if isinstance(edges, list) else 0,
        "order_relations_count": len(relations) if isinstance(relations, list) else 0,
        "relation_invalid_reference_count": len(invalid),
        "relation_invalid_reference_fields": invalid,
    }


def _join_span_texts(clause: Mapping[str, Any], field: str) -> str | None:
    items = clause.get(field)
    if not isinstance(items, list):
        return None
    texts = [
        str(span["text"])
        for span in items
        if isinstance(span, Mapping) and isinstance(span.get("text"), str)
    ]
    return SPAN_TEXT_JOIN.join(texts)


def stage3_adapter_row_features(
    clause: Mapping[str, Any], source_text: str
) -> dict[str, Any]:
    """Offline Stage 3 adapter validation for one clause (best effort)."""
    if not _STAGE3_ADAPTER_AVAILABLE or _STAGE3_ADAPTER is None:
        return {
            "stage3_adapter_status": "not_available",
            "stage3_adapter_flags": None,
            "stage3_adapter_error": _STAGE3_ADAPTER_ERROR,
        }
    modality = clause.get("modality") or {}
    label = modality.get("label")
    try:
        record = _STAGE3_ADAPTER.convert(
            rule_id=str(clause.get("clause_id")),
            source_text=source_text,
            modality=label if label in VALID_MODALITIES else "unknown",
            actor=_join_span_texts(clause, "actors"),
            action=_join_span_texts(clause, "actions"),
            condition=_join_span_texts(clause, "conditions"),
            constraint=_join_span_texts(clause, "constraints"),
            exception=_join_span_texts(clause, "exceptions"),
            provenance="b0_diagnostics",
        )
        obligation = record.obligations[0] if record.obligations else None
        return {
            "stage3_adapter_status": "ok",
            "stage3_adapter_flags": (
                obligation.validation_flags if obligation is not None else {}
            ),
            "stage3_adapter_error": None,
        }
    except Exception as exc:  # noqa: BLE001 -- per-row adapter failure is a feature
        return {
            "stage3_adapter_status": "error",
            "stage3_adapter_flags": None,
            "stage3_adapter_error": f"{type(exc).__name__}: {exc}",
        }


# ---------------------------------------------------------------------------
# Row builder (flat feature table + per-feature missing indicators)
# ---------------------------------------------------------------------------


class _RowBuilder:
    def __init__(self) -> None:
        self.row: dict[str, Any] = {}
        self.missing: dict[str, bool] = {}

    def put(self, name: str, value: Any, missing: bool = False) -> None:
        self.row[name] = value
        self.missing[name] = bool(missing)


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def build_clause_row(
    item: LoadedB0,
    clause_index: int,
    attempts_sha256: str,
) -> dict[str, Any]:
    record = item.record
    clause = record["clauses"][clause_index]
    source_text = record.get("source_text")
    if not isinstance(source_text, str):
        source_text = ""
    source_len = len(source_text)

    telemetry_clauses = item.telemetry.get("clauses")
    if not isinstance(telemetry_clauses, list):
        telemetry_clauses = []
    clause_tel = (
        telemetry_clauses[clause_index]
        if clause_index < len(telemetry_clauses)
        else None
    )

    b = _RowBuilder()

    # -- identity -----------------------------------------------------------
    b.put("sample_id", record.get("sample_id"))
    b.put("source_id", record.get("source_id"))
    b.put("clause_id", clause.get("clause_id"))
    b.put("clause_index", clause_index)

    # -- hashes (never the full text) ---------------------------------------
    b.put("b0_attempts_sha256", attempts_sha256)
    b.put("b0_prediction_sha256", prediction_hash(record))
    b.put("source_text_sha256", sha256_bytes(source_text.encode("utf-8")))

    # -- clause span --------------------------------------------------------
    clause_span = clause.get("clause_span") or {}
    cs_start, cs_end = clause_span.get("start"), clause_span.get("end")
    span_ok = isinstance(cs_start, int) and isinstance(cs_end, int) and 0 <= cs_start < cs_end
    b.put("clause_span_start", cs_start)
    b.put("clause_span_end", cs_end)
    clause_span_length = (cs_end - cs_start) if span_ok else None
    b.put("clause_span_length", clause_span_length)
    ratio_missing = not span_ok or source_len == 0
    b.put(
        "clause_span_ratio",
        (clause_span_length / source_len) if (span_ok and source_len) else None,
        missing=ratio_missing,
    )

    # -- modality + alignment (telemetry) -----------------------------------
    modality = clause.get("modality") or {}
    b.put("modality_label", modality.get("label"))
    evidence = modality.get("evidence")
    b.put(
        "modality_evidence_count",
        len(evidence) if isinstance(evidence, list) else None,
        missing=not isinstance(evidence, list),
    )

    diagnostic = None
    diagnostic_missing = (
        clause_tel is None
        or not isinstance(clause_tel.get("modality_diagnostic"), Mapping)
        or not clause_tel.get("modality_diagnostic")
    )
    if not diagnostic_missing:
        diagnostic = clause_tel.get("modality_diagnostic")
    for feature, key in (
        ("modality_route", "modality_route"),
        ("classifier_label", "clause_classifier_label"),
        ("record_classifier_label", "record_classifier_label"),
        ("marker_label", "marker_label"),
        ("marker_surface", "marker_surface"),
        ("classifier_input_placeholder", "placeholder_classifier_input"),
        ("alignment_validated", "validated_alignment"),
    ):
        if feature == "modality_route":
            tel = clause_tel
            source_missing = (
                not isinstance(tel, Mapping)
                or "modality_route" not in tel
                or tel["modality_route"] is None
            )
            value = tel.get("modality_route") if isinstance(tel, Mapping) else None
        else:
            source_missing = diagnostic is None or key not in diagnostic
            value = diagnostic.get(key) if diagnostic is not None else None
        b.put(feature, value, missing=source_missing)

    alignment = None
    alignment_missing = (
        clause_tel is None
        or not isinstance(clause_tel.get("alignment"), Mapping)
        or not clause_tel.get("alignment")
    )
    if not alignment_missing:
        alignment = clause_tel.get("alignment")
    for feature, key in (
        ("alignment_status", "status"),
        ("alignment_confidence", "confidence"),
        ("alignment_supported", "supported"),
    ):
        source_missing = alignment is None or key not in alignment
        b.put(
            feature,
            alignment.get(key) if alignment is not None else None,
            missing=source_missing,
        )

    classifier = b.row.get("classifier_label")
    marker = b.row.get("marker_label")
    disagreement_missing = (
        b.missing["classifier_label"] or b.missing["marker_label"]
        or classifier not in VALID_MODALITIES or marker not in VALID_MODALITIES
    )
    b.put(
        "classifier_marker_disagreement",
        (classifier != marker) if not disagreement_missing else None,
        missing=disagreement_missing,
    )

    # -- span counts --------------------------------------------------------
    structure = analyze_clause_structure(clause, source_text)
    for field in SPAN_FIELDS:
        b.put(f"n_{field}", structure["per_field"][field]["total"])
    b.put("n_spans_total", structure["n_spans_total"])

    # -- relations ----------------------------------------------------------
    relations = analyze_relations(clause)
    b.put("actor_action_map_count", relations["actor_action_map_count"])
    b.put("order_relations_count", relations["order_relations_count"])
    b.put("relation_invalid_reference_count", relations["relation_invalid_reference_count"])
    b.put(
        "relation_invalid_reference_fields",
        relations["relation_invalid_reference_fields"],
    )

    # -- span integrity -----------------------------------------------------
    for feature in (
        "span_text_empty_count",
        "span_extent_invalid_count",
        "span_outside_clause_count",
        "span_text_mismatch_count",
        "span_id_missing_count",
        "normalized_missing_count",
        "span_id_duplicate_count",
        "span_id_cross_field_collision_count",
    ):
        b.put(feature, structure[feature])
    b.put("span_id_collision_fields", structure["span_id_collision_fields"])

    # -- lengths + coverage -------------------------------------------------
    n_spans = structure["n_spans_total"]
    span_length_sum = structure["span_length_sum"]
    b.put("span_length_min", structure["span_length_min"], missing=n_spans == 0)
    b.put("span_length_max", structure["span_length_max"], missing=n_spans == 0)
    b.put("span_length_sum", span_length_sum, missing=n_spans == 0)
    b.put("span_length_mean", structure["span_length_mean"], missing=n_spans == 0)
    coverage_missing = n_spans == 0 or not span_ok or clause_span_length == 0
    b.put(
        "total_span_clause_coverage_ratio",
        (span_length_sum / clause_span_length)
        if (n_spans and span_ok and clause_span_length)
        else None,
        missing=coverage_missing,
    )
    coverage_by_field: dict[str, float | None] = {}
    coverage_by_field_missing: dict[str, bool] = {}
    for field in SPAN_FIELDS:
        field_len = sum(structure["per_field"][field]["lengths"])
        if not span_ok or clause_span_length == 0:
            coverage_by_field[field] = None
            coverage_by_field_missing[field] = True
        else:
            coverage_by_field[field] = field_len / clause_span_length
            coverage_by_field_missing[field] = False
    b.put("span_coverage_by_field", coverage_by_field)
    b.put(
        "span_coverage_by_field_missing",
        coverage_by_field_missing,
    )

    # -- overlaps -----------------------------------------------------------
    b.put("same_field_overlap_pairs", structure["same_field_overlap_pairs"])
    b.put("same_field_overlap_by_field", structure["same_field_overlap_by_field"])
    b.put("cross_field_overlap_pairs", structure["cross_field_overlap_pairs"])

    # -- structure flags ----------------------------------------------------
    label = b.row["modality_label"]
    non_definition = label is not None and label != "definition"
    b.put(
        "non_definition_missing_actor",
        bool(non_definition and structure["per_field"]["actors"]["total"] == 0),
    )
    b.put(
        "non_definition_missing_action",
        bool(non_definition and structure["per_field"]["actions"]["total"] == 0),
    )

    # -- scope telemetry ----------------------------------------------------
    scope_stats = None
    scope_missing = (
        clause_tel is None
        or not isinstance(clause_tel.get("scope_stats"), Mapping)
        or not clause_tel.get("scope_stats")
    )
    if not scope_missing:
        scope_stats = clause_tel.get("scope_stats")
    for feature, key in (("scope_accepted", "scope_accepted"), ("scope_rejected", "scope_rejected")):
        source_missing = scope_stats is None or key not in scope_stats
        b.put(
            feature,
            scope_stats.get(key) if scope_stats is not None else None,
            missing=source_missing,
        )
    b.put("scope_stats", copy.deepcopy(scope_stats) if scope_stats is not None else None, missing=scope_missing)
    rejected = b.row.get("scope_rejected")
    b.put(
        "scope_rejected_present",
        (int(rejected) > 0) if isinstance(rejected, (int, float)) else None,
        missing=not isinstance(rejected, (int, float)),
    )

    # -- schema / cross-field validation ------------------------------------
    report = validate_canonical(record)
    b.put("schema_valid", report.schema_valid)
    b.put("cross_field_valid", report.cross_field_valid)
    b.put("validation_error_count", len(report.errors))
    b.put("validation_errors", list(report.errors))

    # -- Stage 3 adapter ----------------------------------------------------
    stage3 = stage3_adapter_row_features(clause, source_text)
    b.put("stage3_adapter_status", stage3["stage3_adapter_status"])
    b.put(
        "stage3_adapter_flags",
        stage3["stage3_adapter_flags"],
        missing=stage3["stage3_adapter_flags"] is None,
    )
    b.put("stage3_adapter_error", stage3["stage3_adapter_error"])

    b.row["missing"] = b.missing
    b.row["missing_features"] = sorted(name for name, flag in b.missing.items() if flag)
    return b.row


def signal_candidate_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Descriptive counts of current trigger-signal candidates.

    Purely descriptive: the next trigger policy and thresholds are registered
    separately on development data; this table does not select anything.
    """
    counts: dict[str, int] = {
        "non_definition_missing_action": 0,
        "non_definition_missing_actor": 0,
        "classifier_marker_disagreement": 0,
        "alignment_confidence_below_0_65": 0,
        "scope_candidate_rejected": 0,
        "schema_or_cross_field_invalid": 0,
        "span_integrity_issue": 0,
        "relation_invalid_reference": 0,
        "stage3_adapter_error_or_unavailable": 0,
    }
    for row in rows:
        if row.get("non_definition_missing_action"):
            counts["non_definition_missing_action"] += 1
        if row.get("non_definition_missing_actor"):
            counts["non_definition_missing_actor"] += 1
        if row.get("classifier_marker_disagreement"):
            counts["classifier_marker_disagreement"] += 1
        confidence = row.get("alignment_confidence")
        if isinstance(confidence, (int, float)) and confidence < 0.65:
            counts["alignment_confidence_below_0_65"] += 1
        if row.get("scope_rejected_present"):
            counts["scope_candidate_rejected"] += 1
        if not row.get("schema_valid") or not row.get("cross_field_valid"):
            counts["schema_or_cross_field_invalid"] += 1
        if any(
            row.get(feature)
            for feature in (
                "span_text_empty_count",
                "span_extent_invalid_count",
                "span_outside_clause_count",
                "span_text_mismatch_count",
                "span_id_missing_count",
                "normalized_missing_count",
                "span_id_duplicate_count",
                "span_id_cross_field_collision_count",
            )
        ):
            counts["span_integrity_issue"] += 1
        if row.get("relation_invalid_reference_count"):
            counts["relation_invalid_reference"] += 1
        if row.get("stage3_adapter_status") != "ok":
            counts["stage3_adapter_error_or_unavailable"] += 1
    counts["rows_with_any_signal_candidate"] = sum(
        1
        for row in rows
        if (
            row.get("non_definition_missing_action")
            or row.get("non_definition_missing_actor")
            or row.get("classifier_marker_disagreement")
            or (
                isinstance(row.get("alignment_confidence"), (int, float))
                and row["alignment_confidence"] < 0.65
            )
            or row.get("scope_rejected_present")
            or not row.get("schema_valid")
            or not row.get("cross_field_valid")
            or any(
                row.get(feature)
                for feature in (
                    "span_text_empty_count",
                    "span_extent_invalid_count",
                    "span_outside_clause_count",
                    "span_text_mismatch_count",
                    "span_id_missing_count",
                    "normalized_missing_count",
                    "span_id_duplicate_count",
                    "span_id_cross_field_collision_count",
                )
            )
            or row.get("relation_invalid_reference_count")
            or row.get("stage3_adapter_status") != "ok"
        )
    )
    return counts


# ---------------------------------------------------------------------------
# Write gating and deterministic serialization
# ---------------------------------------------------------------------------


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _gate_write(target: Path, development: bool) -> tuple[bool, str]:
    is_formal = any(_is_under(target, directory) for directory in FORMAL_DIRS)
    if not is_formal:
        if development:
            return True, "explicit development write"
        return False, "non-formal writes require --development"
    audit = collect_project_audit()
    if not audit["integrity_pass"]:
        return False, "formal write refused because integrity_pass is false"
    if audit["final_experiment_ready"]:
        return True, "formal route is final-ready"
    return False, "formal write refused because final_experiment_ready is false"


def _atomic_write_text(path: Path, text: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise DiagnosticsError(f"refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _row_text(rows: Sequence[Mapping[str, Any]]) -> str:
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        for row in rows
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--b0-predictions",
        type=Path,
        required=True,
        help="Persisted B0 attempts JSON/JSONL; diagnostics never rerun B0.",
    )
    parser.add_argument("--b0-manifest", type=Path)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--development", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _make_parser().parse_args(argv)
    targets = (args.output, args.manifest)
    for target in targets:
        allowed, reason = _gate_write(target, args.development)
        if not allowed:
            print(f"Refusing to write {target}: {reason}")
            return 2
        if target.exists() and not args.overwrite:
            print(f"Refusing to overwrite existing artifact: {target}")
            return 2

    try:
        b0_manifest = verify_b0_manifest(args.b0_predictions, args.b0_manifest)
        raw_rows = read_json_values(args.b0_predictions)
        batch = load_b0_predictions(args.b0_predictions)
    except (B0ArtifactError, OSError, json.JSONDecodeError) as exc:
        print(f"Refusing to run: {exc}")
        return 2

    attempts_sha256 = sha256_file(args.b0_predictions)
    rows = [
        build_clause_row(item, clause_index, attempts_sha256)
        for item in batch
        for clause_index in range(len(item.record["clauses"]))
    ]
    rows.sort(key=lambda row: (str(row["sample_id"]), int(row["clause_index"])))

    clause_rows_per_sample: dict[str, int] = {}
    for row in rows:
        clause_rows_per_sample[str(row["sample_id"])] = (
            clause_rows_per_sample.get(str(row["sample_id"]), 0) + 1
        )
    per_sample_counts = list(clause_rows_per_sample.values())

    output_text = _row_text(rows)
    try:
        _atomic_write_text(args.output, output_text, args.overwrite)
    except DiagnosticsError as exc:
        print(f"Refusing to write output: {exc}")
        return 2

    manifest = {
        "schema_version": MANIFEST_VERSION,
        "stage": "stage2",
        "method": "h1_trigger_diagnostics",
        "status": "development_not_formal",
        "b0_binding": {
            "path": str(args.b0_predictions),
            "sha256": attempts_sha256,
            "manifest": b0_manifest,
            "rerun_inside_diagnostics": False,
        },
        "outputs": {
            "diagnostics": {
                "path": str(args.output),
                "sha256": sha256_file(args.output),
                "row_count": len(rows),
            }
        },
        "config": {
            "feature_version": FEATURE_VERSION,
            "row_sort": "sample_id ascending, then clause_index ascending",
            "span_text_join": SPAN_TEXT_JOIN,
            "stage3_adapter": {
                "source": "bpc_hybrid.sun_compat.clause_adapter.ClauseAdapter",
                "spacy_model": "en_core_web_md",
                "available": _STAGE3_ADAPTER_AVAILABLE,
                "error": _STAGE3_ADAPTER_ERROR,
            },
            "contains_full_source_or_span_text": False,
        },
        "coverage": {
            "expected_attempts": len(raw_rows),
            "loaded_samples": len(batch),
            "clause_rows": len(rows),
            "clause_rows_per_sample": {
                "min": min(per_sample_counts) if per_sample_counts else 0,
                "max": max(per_sample_counts) if per_sample_counts else 0,
                "mean": (
                    sum(per_sample_counts) / len(per_sample_counts)
                    if per_sample_counts
                    else 0.0
                ),
            },
            "excluded_rows": 0,
            "coverage_complete": (
                len(raw_rows) == len(batch) and len(batch) == len(clause_rows_per_sample)
            ),
        },
        "signal_candidate_counts": signal_candidate_counts(rows),
        "safety": {
            "gold_visible": False,
            "layer_e_accessed": False,
            "evaluator_accessed": False,
            "paper_validation_accessed": False,
            "llm_api_called": False,
            "b0_modified": False,
        },
    }
    try:
        _atomic_write_text(
            args.manifest,
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            args.overwrite,
        )
    except DiagnosticsError as exc:
        print(f"Refusing to write manifest: {exc}")
        return 2

    print(
        f"H1 diagnostics: attempts={len(raw_rows)}, samples={len(batch)}, "
        f"clause_rows={len(rows)}"
    )
    print(f"Diagnostics: {args.output}")
    print(f"Manifest:    {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
