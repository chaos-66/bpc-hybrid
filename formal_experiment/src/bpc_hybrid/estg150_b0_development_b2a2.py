"""EStG-150 B2a2 development batch on the unchanged v10-A parent.

Only definition rejection for a supported clause is changed.  Segmentation,
alignment, CoreNLP/Tregex, lexicon, scope, actor/action/edges, checkpoint, and
record-level fallback behavior for unsupported clauses are inherited intact.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.b0_v10.alignment import align_de_to_en_units, summarize_alignments
from bpc_hybrid.b0_v10.clause_probability_adapter_b2a2 import (
    ClauseProbabilityVector,
    predict_clause_probability_vectors,
)
from bpc_hybrid.b0_v10.definition_resolver_b2a2 import resolve_modality_b2a2
from bpc_hybrid.b0_v10.pipeline import collect_classifier_inputs
from bpc_hybrid.b0_v10.profile import B0V10Profile, PROFILE_V10A
from bpc_hybrid.estg150_b0_development import Estg150B0DevelopmentError
from bpc_hybrid.estg150_b0_development_v2 import sun_table8_any_overlap_diagnostic
from bpc_hybrid.estg150_b0_development_v3 import plan_clause_units_v4
from bpc_hybrid.estg150_b0_development_v10 import (
    build_canonical_record_v10,
    run_corenlp_batch_v10,
)
from bpc_hybrid.sun_style.lexicon_v2_runtime import load_lexicon_v2
from bpc_hybrid.sun_style.sun_b0 import (
    LockedBertTextCNNInference,
    ModalityPrediction,
    SunB0CompositionError,
    load_s26_config,
)


METHOD_ID = "sun_rule_only"
METHOD_VARIANT = "b0_enhanced_b2a2"


def _predict_vectors_batched(
    inference: LockedBertTextCNNInference,
    texts: Sequence[str],
    *,
    batch_size: int = 16,
) -> list[ClauseProbabilityVector]:
    result: list[ClauseProbabilityVector] = []
    for start in range(0, len(texts), batch_size):
        result.extend(
            predict_clause_probability_vectors(inference, texts[start : start + batch_size])
        )
    return result


def _as_prediction(vector: ClauseProbabilityVector) -> ModalityPrediction:
    return ModalityPrediction(vector.top_label, vector.top_confidence)


def run_b0_batch_b2a2(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
    device: str = "cpu",
    profile: B0V10Profile | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = Path(project_root).resolve()
    profile = profile or PROFILE_V10A
    if profile.tsurgeon_enabled:
        raise Estg150B0DevelopmentError("B2a2 inherits the v10-A Tsurgeon-disabled profile")
    s26_config = load_s26_config(root / profile.s26_config_rel)
    annotations, cases_by_id, runtime = run_corenlp_batch_v10(
        root,
        source_records,
        runtime_home=runtime_home,
        work_dir=work_dir,
        patterns_rel=profile.tregex_registry_rel,
    )
    lexicon = load_lexicon_v2(root)
    classifier_started = time.perf_counter()
    try:
        inference = LockedBertTextCNNInference.load(root, s26_config, device=device)
    except SunB0CompositionError as exc:
        raise Estg150B0DevelopmentError(str(exc)) from exc

    planned: list[dict[str, Any]] = []
    all_classifier_texts: list[str] = []
    classifier_index_map: list[tuple[int, int | None]] = []
    for plan_i, record in enumerate(source_records):
        sample_id = record["sample_id"]
        annotation = annotations[sample_id]
        source_text = record["approved_text_en"]
        clause_units, segmentation_stats = plan_clause_units_v4(annotation, source_text)
        english_texts = [
            source_text[unit["clause_char_span"][0] : unit["clause_char_span"][1]]
            for unit in clause_units
        ]
        alignments = align_de_to_en_units(record["raw_text_de"], english_texts)
        alignment_summary = summarize_alignments(alignments)
        texts, index_map = collect_classifier_inputs(
            alignments,
            record_level_de=record["raw_text_de"],
        )
        for text, clause_i in zip(texts, index_map, strict=True):
            all_classifier_texts.append(text)
            classifier_index_map.append((plan_i, clause_i))
        planned.append(
            {
                "record": record,
                "clause_units": clause_units,
                "english_texts": english_texts,
                "alignments": alignments,
                "alignment_summary": alignment_summary,
                "segmentation_stats": segmentation_stats,
            }
        )

    if any(not text.strip() or text.strip() == "." for text in all_classifier_texts):
        raise Estg150B0DevelopmentError("placeholder/empty classifier input forbidden in B2a2")
    vectors = _predict_vectors_batched(inference, all_classifier_texts)
    classifier_seconds = time.perf_counter() - classifier_started
    if len(vectors) != len(all_classifier_texts):
        raise Estg150B0DevelopmentError("clause probability output size mismatch")

    probabilities_by_plan: dict[int, dict[str, Any]] = {}
    for (plan_i, clause_i), vector in zip(classifier_index_map, vectors, strict=True):
        bucket = probabilities_by_plan.setdefault(plan_i, {"clauses": {}, "record": None})
        if clause_i is None:
            bucket["record"] = vector
        else:
            bucket["clauses"][clause_i] = vector

    compose_started = time.perf_counter()
    canonical_records: list[dict[str, Any]] = []
    route_counts: dict[str, int] = {}
    label_counts: dict[str, int] = {}
    b2a2_rule_counts: dict[str, int] = {}
    confidence_sum = 0.0
    placeholder_count = 0
    supported_record_fallback_count = 0
    constrained_count = 0
    lexicon_stats_aggregate = {
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
    alignment_aggregate = {
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
        bucket = probabilities_by_plan[plan_i]
        record_vector = bucket["record"]
        if not isinstance(record_vector, ClauseProbabilityVector):
            raise Estg150B0DevelopmentError(f"missing record-level prediction for {sample_id}")
        record_prediction = _as_prediction(record_vector)
        decisions = []
        for clause_i, (english, alignment) in enumerate(
            zip(item["english_texts"], item["alignments"], strict=True)
        ):
            clause_vector = bucket["clauses"].get(clause_i) if alignment.heuristic_supported else None
            if alignment.heuristic_supported and not isinstance(
                clause_vector, ClauseProbabilityVector
            ):
                raise Estg150B0DevelopmentError(
                    f"supported clause lacks probability vector: {sample_id}:{clause_i}"
                )
            if not alignment.heuristic_supported and clause_vector is not None:
                raise Estg150B0DevelopmentError("unsupported clause received a probability vector")
            clause_prediction = _as_prediction(clause_vector) if clause_vector is not None else None
            decision = resolve_modality_b2a2(
                english_clause=english,
                german_clause=alignment.text if alignment.heuristic_supported else None,
                alignment=alignment,
                clause_classifier=clause_prediction,
                clause_probabilities=None
                if clause_vector is None
                else clause_vector.probabilities,
                record_classifier=record_prediction,
                lexicon=lexicon,
            )
            decisions.append(decision)
            route = decision.route.value
            route_counts[route] = route_counts.get(route, 0) + 1
            label_counts[decision.label] = label_counts.get(decision.label, 0) + 1
            rule = str(decision.diagnostic.get("b2a2_rule"))
            b2a2_rule_counts[rule] = b2a2_rule_counts.get(rule, 0) + 1
            confidence_sum += decision.confidence
            if decision.diagnostic.get("placeholder_classifier_input"):
                placeholder_count += 1
            if alignment.heuristic_supported and route == "record_level_classifier_fallback":
                supported_record_fallback_count += 1
            if route == "definition_rejected_clause_local_constrained":
                constrained_count += 1

        summary = item["alignment_summary"]
        for status, count in summary["by_status"].items():
            alignment_aggregate["by_status"][status] = (
                alignment_aggregate["by_status"].get(status, 0) + count
            )
        alignment_aggregate["total"] += summary["total"]
        alignment_aggregate["heuristic_supported"] += summary["heuristic_supported_count"]
        alignment_aggregate["validated"] += summary["validated_count"]
        alignment_aggregate["unsupported"] += summary["unsupported_count"]

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
            for source_key, target_key in (
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
                lexicon_stats_aggregate[target_key] += int(scope_stats.get(source_key, 0))
        canonical_records.append(canonical)

    if placeholder_count != 0:
        raise Estg150B0DevelopmentError("B2a2 produced placeholder classifier diagnostics")
    if supported_record_fallback_count != 0:
        raise Estg150B0DevelopmentError("B2a2 introduced record fallback for supported clauses")
    if any("reject_loose_definition_record_even_if_def" in key for key in b2a2_rule_counts):
        raise Estg150B0DevelopmentError("B2a contradictory record fallback path reappeared")

    compose_seconds = time.perf_counter() - compose_started
    total_seconds = (
        runtime["corenlp_seconds"]
        + runtime["bridge_seconds"]
        + classifier_seconds
        + compose_seconds
    )
    latency_ms = 1000.0 * total_seconds / max(len(canonical_records), 1)
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
                "latency_ms": latency_ms,
            },
        }
        for record in canonical_records
    ]
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
            "b2a2_rule_counts": dict(sorted(b2a2_rule_counts.items())),
            "alignment_summary": alignment_aggregate,
            "lexicon_v2": {
                "lexicon_id": lexicon.lexicon_id,
                "manifest_sha256": lexicon.manifest_sha256,
                "category_file_sha256": dict(lexicon.category_file_sha256),
                **lexicon_stats_aggregate,
                "modality_patterns_compiled": len(lexicon.modality_patterns),
            },
            "edge_stats": edge_stats,
            "placeholder_classifier_count": placeholder_count,
            "supported_record_fallback_count": supported_record_fallback_count,
            "definition_rejected_clause_local_constrained_count": constrained_count,
            "probability_input_unit": "same_aligned_german_clause_text",
            "record_text_used_for_clause_probability": False,
            "method_id": METHOD_ID,
            "method_variant": METHOD_VARIANT,
            "profile_id": profile.profile_id,
            "paper_faithful_b0": False,
            "tsurgeon_enabled": False,
            "s26_config_rel": profile.s26_config_rel,
        }
    )
    return attempts, runtime


__all__ = [
    "METHOD_ID",
    "METHOD_VARIANT",
    "run_b0_batch_b2a2",
    "sun_table8_any_overlap_diagnostic",
]
