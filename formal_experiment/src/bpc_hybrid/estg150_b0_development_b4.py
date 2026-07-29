"""Single-candidate EStG-150 B4 constraint-marker expansion.

This module appends one frozen set of literal constraint markers to the v10-A
lexicon runtime.  CoreNLP, Tregex, typed-scope resolution, span boundaries,
modality, segmentation, alignment, actor/action extraction, and edges are
imported unchanged from the fixed parent implementation.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.b0_v10.alignment import align_de_to_en_units, summarize_alignments
from bpc_hybrid.b0_v10.modality import resolve_modality_v10
from bpc_hybrid.b0_v10.pipeline import collect_classifier_inputs
from bpc_hybrid.b0_v10.profile import B0V10Profile, PROFILE_V10A
from bpc_hybrid.estg150_b0_development import Estg150B0DevelopmentError
from bpc_hybrid.estg150_b0_development_v2 import _predict_in_batches
from bpc_hybrid.estg150_b0_development_v3 import plan_clause_units_v4
from bpc_hybrid.estg150_b0_development_v10 import (
    build_canonical_record_v10,
    run_corenlp_batch_v10,
)
from bpc_hybrid.sun_style.lexicon_v2_runtime import (
    CATEGORY_ORDER,
    LexiconV2Error,
    LexiconV2Runtime,
    MarkerEntry,
    load_lexicon_v2,
    match_field_markers,
    normalize_surface,
    sha256_file,
)
from bpc_hybrid.sun_style.sun_b0 import (
    LockedBertTextCNNInference,
    SunB0CompositionError,
    load_s26_config,
)


METHOD_ID = "sun_rule_only"
METHOD_VARIANT = "b0_enhanced_b4_constraint_marker_expansion"
MANIFEST_REL = "resources/lexicon/public_marker_lexicon_en_v3_b4.manifest.json"
ALLOWED_SCOPE_TESTS = frozenset(
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
FORBIDDEN_BROAD_SURFACES = frozenset({"a", "an", "at", "by", "for", "in", "of", "on", "the", "to"})
PARENT_RELATIONS = frozenset({"none", "new_contains_parent", "parent_contains_new"})


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LexiconV2Error(f"expected JSON object: {path}")
    return value


def _word_contains(container: str, contained: str) -> bool:
    return f" {container} ".find(f" {contained} ") >= 0


def _expected_parent_relation(surface: str, parent_surfaces: set[str]) -> tuple[str, set[str]]:
    new_contains = {p for p in parent_surfaces if _word_contains(surface, p)}
    parent_contains = {p for p in parent_surfaces if _word_contains(p, surface)}
    if new_contains and parent_contains:
        raise LexiconV2Error(f"ambiguous parent containment for {surface!r}")
    if new_contains:
        return "new_contains_parent", new_contains
    if parent_contains:
        return "parent_contains_new", parent_contains
    return "none", set()


def _validate_extension_document(
    doc: Mapping[str, Any],
    *,
    parent_surfaces: set[str],
    source_ids: set[str],
) -> tuple[Mapping[str, Any], ...]:
    """Fail closed on B4 scope, evidence, activation, and literal safety."""
    if doc.get("schema_version") != "constraint_marker_extension_b4@1.0.0":
        raise LexiconV2Error("unexpected B4 extension schema")
    if doc.get("lexicon_id") != "constraint_markers_en_v3_b4" or doc.get("field") != "constraint":
        raise LexiconV2Error("B4 extension identity/field mismatch")
    rows = doc.get("entries")
    if not isinstance(rows, list) or not (25 <= len(rows) <= 60):
        raise LexiconV2Error("B4 requires 25-60 new constraint markers")
    normalized_seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise LexiconV2Error(f"B4 entry {index} is not an object")
        surface = row.get("surface")
        normalized = row.get("normalized")
        if not isinstance(surface, str) or not surface.strip():
            raise LexiconV2Error(f"B4 entry {index} has invalid surface")
        if len(surface.strip()) <= 1 or surface != surface.strip() or surface.casefold() != surface:
            raise LexiconV2Error(f"B4 surface is not a normalized lowercase literal: {surface!r}")
        if not re.fullmatch(r"[a-z]+(?:[ -][a-z]+)*", surface):
            raise LexiconV2Error(f"B4 surface contains regex/non-literal syntax: {surface!r}")
        if surface in FORBIDDEN_BROAD_SURFACES:
            raise LexiconV2Error(f"B4 broad preposition/stopword forbidden: {surface!r}")
        if normalized != normalize_surface(surface):
            raise LexiconV2Error(f"B4 normalized surface mismatch: {surface!r}")
        if normalized in normalized_seen or normalized in parent_surfaces:
            raise LexiconV2Error(f"B4 duplicate marker: {surface!r}")
        normalized_seen.add(normalized)
        if row.get("activation") is not True:
            raise LexiconV2Error(f"B4 marker is not explicitly active: {surface!r}")
        if row.get("scope_test") not in ALLOWED_SCOPE_TESTS:
            raise LexiconV2Error(f"B4 scope type is forbidden: {surface!r}")
        if not isinstance(row.get("syntactic_scope"), str) or not row["syntactic_scope"].strip():
            raise LexiconV2Error(f"B4 syntactic scope missing: {surface!r}")
        row_source_ids = row.get("source_ids")
        if not isinstance(row_source_ids, list) or not row_source_ids or not set(row_source_ids) <= source_ids:
            raise LexiconV2Error(f"B4 source binding invalid: {surface!r}")
        if not isinstance(row.get("provenance"), Mapping) or not row["provenance"]:
            raise LexiconV2Error(f"B4 provenance missing: {surface!r}")
        positives = row.get("synthetic_positive")
        negatives = row.get("synthetic_negative")
        if not isinstance(positives, list) or len(positives) < 2 or any(not isinstance(x, str) for x in positives):
            raise LexiconV2Error(f"B4 needs two synthetic positives: {surface!r}")
        if not isinstance(negatives, list) or len(negatives) < 2 or any(not isinstance(x, str) for x in negatives):
            raise LexiconV2Error(f"B4 needs two synthetic negatives: {surface!r}")
        literal = re.compile(rf"\b{re.escape(surface)}\b", re.IGNORECASE)
        if any(literal.search(text) is None for text in positives):
            raise LexiconV2Error(f"B4 positive does not exercise marker: {surface!r}")
        if any(literal.search(text) is not None for text in negatives):
            raise LexiconV2Error(f"B4 negative accidentally exercises marker: {surface!r}")
        expected_relation, expected_related = _expected_parent_relation(normalized, parent_surfaces)
        actual_related = row.get("parent_related_surfaces")
        if row.get("parent_relation") not in PARENT_RELATIONS or row.get("parent_relation") != expected_relation:
            raise LexiconV2Error(f"B4 parent relation mismatch: {surface!r}")
        if not isinstance(actual_related, list) or set(actual_related) != expected_related:
            raise LexiconV2Error(f"B4 parent related surfaces mismatch: {surface!r}")
    return tuple(rows)


def _verify_bound_file(root: Path, spec: Mapping[str, Any], label: str) -> Path:
    path = (root / str(spec.get("path"))).resolve()
    if not path.is_file() or sha256_file(path) != spec.get("sha256"):
        raise LexiconV2Error(f"B4 {label} missing or hash-mismatched")
    if "bytes" in spec and path.stat().st_size != int(spec["bytes"]):
        raise LexiconV2Error(f"B4 {label} byte-size mismatch")
    return path


def load_lexicon_b4(project_root: Path) -> LexiconV2Runtime:
    root = Path(project_root).resolve()
    manifest_path = root / MANIFEST_REL
    manifest = _load_json(manifest_path)
    if manifest.get("schema_version") != "public_marker_manifest_b4@1.0.0" or manifest.get("lexicon_id") != "public_marker_lexicon_en_v3_b4":
        raise LexiconV2Error("unexpected B4 manifest identity")
    parent_manifest_path = _verify_bound_file(root, manifest["parent_lexicon"], "parent manifest")
    extension_path = _verify_bound_file(root, manifest["constraint_extension"], "constraint extension")
    sources_path = _verify_bound_file(root, manifest["source_snapshot"], "source snapshot")
    parent = load_lexicon_v2(root)
    if parent.manifest_sha256 != manifest["parent_lexicon"]["sha256"]:
        raise LexiconV2Error("B4 parent runtime manifest mismatch")
    parent_manifest = _load_json(parent_manifest_path)
    unchanged = manifest.get("unchanged_parent_category_sha256")
    if not isinstance(unchanged, Mapping):
        raise LexiconV2Error("B4 unchanged category binding missing")
    for field in ("modality", "condition", "exception", "actor"):
        if parent.category_file_sha256[field] != unchanged.get(field):
            raise LexiconV2Error(f"B4 parent category drifted: {field}")
    parent_constraint = manifest.get("parent_constraint") or {}
    if parent.category_file_sha256["constraint"] != parent_constraint.get("sha256"):
        raise LexiconV2Error("B4 parent constraint drifted")
    sources = _load_json(sources_path)
    if sources.get("snapshot_id") != manifest["source_snapshot"].get("snapshot_id"):
        raise LexiconV2Error("B4 source snapshot identity mismatch")
    source_rows = sources.get("sources")
    if not isinstance(source_rows, list) or len(source_rows) != 2:
        raise LexiconV2Error("B4 source snapshot must bind exactly two allowed sources")
    source_ids: set[str] = set()
    for source in source_rows:
        if not isinstance(source, Mapping) or not isinstance(source.get("source_id"), str):
            raise LexiconV2Error("B4 source row invalid")
        source_ids.add(source["source_id"])
        _verify_bound_file(root, source, f"source {source['source_id']}")
    extension = _load_json(extension_path)
    parent_surfaces = {entry.normalized for entry in parent.entries_by_field["constraint"]}
    rows = _validate_extension_document(
        extension,
        parent_surfaces=parent_surfaces,
        source_ids=source_ids,
    )
    if len(rows) != int(manifest["constraint_extension"]["new_active_entry_count"]):
        raise LexiconV2Error("B4 extension entry count mismatch")
    extension_entries = tuple(
        MarkerEntry(
            field="constraint",
            surface=str(row["surface"]),
            normalized=str(row["normalized"]),
            source_ids=tuple(row["source_ids"]),
            source_tiers=tuple(row["source_tiers"]),
            ambiguity=str(row["ambiguity"]),
            syntactic_scope=str(row["syntactic_scope"]),
            activation=True,
            scope_test=str(row["scope_test"]),
        )
        for row in rows
    )
    entries_by_field = {field: tuple(parent.entries_by_field[field]) for field in CATEGORY_ORDER}
    entries_by_field["constraint"] = entries_by_field["constraint"] + extension_entries
    field_patterns = dict(parent.field_patterns)
    field_patterns["constraint"] = tuple(
        (
            re.compile(rf"\b{re.escape(entry.surface)}\b", re.IGNORECASE),
            entry.surface,
        )
        for entry in sorted(
            (e for e in entries_by_field["constraint"] if e.activation),
            key=lambda entry: (-len(entry.normalized), entry.normalized),
        )
    )
    active_counts = dict(parent.active_counts)
    active_counts["constraint"] += len(extension_entries)
    if active_counts["constraint"] != int(manifest["constraint_extension"]["combined_active_entry_count"]):
        raise LexiconV2Error("B4 combined constraint activation count mismatch")
    expected_combined = hashlib.sha256(
        (
            manifest["parent_lexicon"]["sha256"]
            + "\n"
            + manifest["constraint_extension"]["sha256"]
            + "\n"
            + manifest["source_snapshot"]["sha256"]
            + "\n"
        ).encode("utf-8")
    ).hexdigest()
    if expected_combined != manifest.get("combined_payload_sha256"):
        raise LexiconV2Error("B4 combined payload hash mismatch")
    if parent_manifest.get("lexicon_id") != manifest["parent_lexicon"].get("lexicon_id"):
        raise LexiconV2Error("B4 parent lexicon identity mismatch")
    return LexiconV2Runtime(
        lexicon_id="public_marker_lexicon_en_v3_b4",
        manifest_sha256=sha256_file(manifest_path),
        combined_payload_sha256=expected_combined,
        category_file_sha256=dict(parent.category_file_sha256),
        entries_by_field=entries_by_field,
        active_counts=active_counts,
        inactive_counts=dict(parent.inactive_counts),
        modality_patterns=parent.modality_patterns,
        field_patterns=field_patterns,
        actor_surfaces=parent.actor_surfaces,
    )


def new_marker_surfaces(project_root: Path) -> frozenset[str]:
    root = Path(project_root).resolve()
    manifest = _load_json(root / MANIFEST_REL)
    extension = _load_json(_verify_bound_file(root, manifest["constraint_extension"], "constraint extension"))
    return frozenset(str(row["surface"]) for row in extension["entries"])


def run_b0_batch_b4(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
    device: str = "cpu",
    profile: B0V10Profile | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the sole B4 candidate with only the lexicon loader changed."""
    root = Path(project_root).resolve()
    profile = profile or PROFILE_V10A
    if profile.tsurgeon_enabled:
        raise Estg150B0DevelopmentError("B4 forbids Tsurgeon")
    s26_config = load_s26_config(root / profile.s26_config_rel)
    annotations, cases_by_id, runtime = run_corenlp_batch_v10(
        root,
        source_records,
        runtime_home=runtime_home,
        work_dir=work_dir,
        patterns_rel=profile.tregex_registry_rel,
    )
    lexicon = load_lexicon_b4(root)
    new_surfaces = new_marker_surfaces(root)
    classifier_started = time.perf_counter()
    try:
        classifier = LockedBertTextCNNInference.load(root, s26_config, device=device)
    except SunB0CompositionError as exc:
        raise Estg150B0DevelopmentError(str(exc)) from exc

    planned: list[dict[str, Any]] = []
    all_clf_texts: list[str] = []
    clf_index_map: list[tuple[int, int | None]] = []
    for plan_i, record in enumerate(source_records):
        sample_id = record["sample_id"]
        annotation = annotations[sample_id]
        source_text = record["approved_text_en"]
        clause_units, seg_stats = plan_clause_units_v4(annotation, source_text)
        en_texts = [source_text[unit["clause_char_span"][0] : unit["clause_char_span"][1]] for unit in clause_units]
        alignments = align_de_to_en_units(record["raw_text_de"], en_texts)
        align_summary = summarize_alignments(alignments)
        texts, index_map = collect_classifier_inputs(alignments, record_level_de=record["raw_text_de"])
        for local_i, clause_i in enumerate(index_map):
            all_clf_texts.append(texts[local_i])
            clf_index_map.append((plan_i, clause_i))
        planned.append(
            {
                "record": record,
                "clause_units": clause_units,
                "en_texts": en_texts,
                "alignments": alignments,
                "align_summary": align_summary,
                "seg_stats": seg_stats,
            }
        )
    if any(text.strip() in {".", ""} for text in all_clf_texts):
        raise Estg150B0DevelopmentError("placeholder/empty classifier input forbidden in B4")
    predictions = _predict_in_batches(classifier, all_clf_texts)
    classifier_seconds = time.perf_counter() - classifier_started
    if len(predictions) != len(all_clf_texts):
        raise Estg150B0DevelopmentError("classifier output size mismatch")
    pred_by_plan: dict[int, dict[str, Any]] = {}
    for (plan_i, clause_i), prediction in zip(clf_index_map, predictions, strict=True):
        bucket = pred_by_plan.setdefault(plan_i, {"clauses": {}, "record": None})
        if clause_i is None:
            bucket["record"] = prediction
        else:
            bucket["clauses"][clause_i] = prediction

    compose_started = time.perf_counter()
    canonical_records: list[dict[str, Any]] = []
    route_counts: dict[str, int] = {}
    label_counts: dict[str, int] = {}
    confidence_sum = 0.0
    placeholder_count = 0
    invoked_new_surfaces: set[str] = set()
    new_marker_invocation_count = 0
    lexicon_stats_agg = {
        "loaded_active_total": lexicon.active_total(),
        "active_counts": dict(lexicon.active_counts),
        "scope_invocations": 0,
        "scope_raw_matches": 0,
        "scope_accepted": 0,
        "scope_rejected": 0,
        "tregex_candidates": 0,
        "tregex_accepted": 0,
        "tregex_final_affected": 0,
        "final_affected_spans": 0,
        "legacy_broken_only_label_ignored": 0,
    }
    align_agg = {
        "total": 0,
        "heuristic_supported": 0,
        "validated": 0,
        "unsupported": 0,
        "by_status": {},
        "note": "heuristic_supported is not verified alignment",
    }
    edge_stats = {"edges": 0}
    for plan_i, item in enumerate(planned):
        record = item["record"]
        sample_id = record["sample_id"]
        bucket = pred_by_plan[plan_i]
        record_pred = bucket["record"]
        if record_pred is None:
            raise Estg150B0DevelopmentError(f"missing record-level prediction for {sample_id}")
        decisions = []
        for clause_index, (english, alignment) in enumerate(zip(item["en_texts"], item["alignments"], strict=True)):
            for hit in match_field_markers(english, "constraint", lexicon):
                if hit["surface"] in new_surfaces:
                    invoked_new_surfaces.add(hit["surface"])
                    new_marker_invocation_count += 1
            clause_pred = bucket["clauses"].get(clause_index) if alignment.heuristic_supported else None
            if not alignment.heuristic_supported:
                clause_pred = None
            decision = resolve_modality_v10(
                english_clause=english,
                alignment=alignment,
                clause_classifier=clause_pred,
                record_classifier=record_pred,
                lexicon=lexicon,
            )
            decisions.append(decision)
            route_counts[decision.route.value] = route_counts.get(decision.route.value, 0) + 1
            label_counts[decision.label] = label_counts.get(decision.label, 0) + 1
            confidence_sum += decision.confidence
            if decision.diagnostic.get("placeholder_classifier_input"):
                placeholder_count += 1
        for status, count in item["align_summary"]["by_status"].items():
            align_agg["by_status"][status] = align_agg["by_status"].get(status, 0) + count
        align_agg["total"] += item["align_summary"]["total"]
        align_agg["heuristic_supported"] += item["align_summary"]["heuristic_supported_count"]
        align_agg["validated"] += item["align_summary"]["validated_count"]
        align_agg["unsupported"] += item["align_summary"]["unsupported_count"]
        canonical = build_canonical_record_v10(
            sample_id=sample_id,
            source_id=f"estg_legacy_{record['legacy_record_id']}",
            source_text=record["approved_text_en"],
            annotation=annotations[sample_id],
            phrase_cases=cases_by_id[sample_id],
            clause_units=item["clause_units"],
            alignments=item["alignments"],
            modality_decisions=decisions,
            lexicon=lexicon,
        )
        for clause in canonical["clauses"]:
            edge_stats["edges"] += len(clause.get("actor_action_map") or [])
            scope_stats = clause.get("scope_stats") or {}
            for source_key, aggregate_key in (
                ("lexicon_invoked", "scope_invocations"),
                ("lexicon_raw_matched", "scope_raw_matches"),
                ("scope_accepted", "scope_accepted"),
                ("scope_rejected", "scope_rejected"),
                ("tregex_candidates", "tregex_candidates"),
                ("tregex_accepted", "tregex_accepted"),
                ("tregex_final_affected", "tregex_final_affected"),
                ("final_affected_spans", "final_affected_spans"),
                ("legacy_broken_only_label_ignored", "legacy_broken_only_label_ignored"),
            ):
                lexicon_stats_agg[aggregate_key] += int(scope_stats.get(source_key, 0))
        canonical_records.append(canonical)
    if placeholder_count != 0:
        raise Estg150B0DevelopmentError("B4 produced placeholder classifier diagnostics")
    compose_seconds = time.perf_counter() - compose_started
    total_seconds = runtime["corenlp_seconds"] + runtime["bridge_seconds"] + classifier_seconds + compose_seconds
    per_record_latency_ms = 1000.0 * total_seconds / max(len(canonical_records), 1)
    attempts = [
        {
            "sample_id": record["sample_id"],
            "request_status": "ok",
            "record": record,
            "error_category": None,
            "runtime": {
                "llm_call_performed": False,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "latency_ms": per_record_latency_ms,
            },
        }
        for record in canonical_records
    ]
    manifest = _load_json(root / MANIFEST_REL)
    runtime.update(
        {
            "classifier_seconds": classifier_seconds,
            "compose_seconds": compose_seconds,
            "total_seconds": total_seconds,
            "device": device,
            "record_count": len(canonical_records),
            "predicted_clause_count": sum(len(record["clauses"]) for record in canonical_records),
            "final_hybrid_label_counts_by_clause": dict(sorted(label_counts.items())),
            "classifier_mean_confidence": confidence_sum / max(sum(label_counts.values()), 1),
            "modality_route_counts": dict(sorted(route_counts.items())),
            "alignment_summary": align_agg,
            "lexicon_b4": {
                "lexicon_id": lexicon.lexicon_id,
                "manifest_sha256": lexicon.manifest_sha256,
                "parent_manifest_sha256": manifest["parent_lexicon"]["sha256"],
                "constraint_extension_sha256": manifest["constraint_extension"]["sha256"],
                "source_snapshot_sha256": manifest["source_snapshot"]["sha256"],
                "category_file_sha256": dict(lexicon.category_file_sha256),
                "new_active_marker_count": len(new_surfaces),
                "invoked_unique_new_marker_count": len(invoked_new_surfaces),
                "invoked_unique_new_markers": sorted(invoked_new_surfaces),
                "new_marker_invocation_count": new_marker_invocation_count,
                **lexicon_stats_agg,
                "modality_patterns_compiled": len(lexicon.modality_patterns),
            },
            "edge_stats": edge_stats,
            "placeholder_classifier_count": placeholder_count,
            "method_id": METHOD_ID,
            "method_variant": METHOD_VARIANT,
            "profile_id": profile.profile_id,
            "paper_faithful_b0": False,
            "tsurgeon_enabled": False,
            "s26_config_rel": profile.s26_config_rel,
        }
    )
    return attempts, runtime

