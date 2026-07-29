"""EStG-150 B0 enhanced v9 batch (modular b0_v9 package).

Profile-driven. No global mutable mode. No placeholder classifier inputs.
Production lexicon + ownership-only edges. Tsurgeon disabled.
"""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.b0_v9.actor_action import extract_actors_actions_edges
from bpc_hybrid.b0_v9.alignment import AlignmentStatus, align_de_to_en_units
from bpc_hybrid.b0_v9.diagnostics import summarize_alignments
from bpc_hybrid.b0_v9.modality import ModalityRoute, resolve_modality_v9
from bpc_hybrid.b0_v9.pipeline import collect_classifier_inputs
from bpc_hybrid.b0_v9.profile import B0V9Profile, PROFILE_V9A
from bpc_hybrid.b0_v9.scope import resolve_scope_fields_v9
from bpc_hybrid.estg150_b0_development import Estg150B0DevelopmentError, load_object, sha256_file
from bpc_hybrid.estg150_b0_development_v2 import (
    _predict_in_batches,
    _run,
    _write_rule_plan,
    parse_bridge_output_multi,
    sun_table8_any_overlap_diagnostic,
)
from bpc_hybrid.estg150_b0_development_v3 import (
    _plain_span,
    _token_span,
    _verify_runtime_identity,
    plan_clause_units_v4,
)
from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, SCHEMA_VERSION, validate_canonical
from bpc_hybrid.sun_style.corenlp_runtime import (
    EXTRACTION_ORDER,
    CoreNLPContractError,
    resolve_corenlp_runtime,
    validate_annotation,
)
from bpc_hybrid.sun_style.lexicon_v2_runtime import load_lexicon_v2
from bpc_hybrid.sun_style.sun_b0 import (
    LockedBertTextCNNInference,
    ModalityPrediction,
    SunB0CompositionError,
    load_s26_config,
)

METHOD_ID = "sun_rule_only"
METHOD_VARIANT = "b0_enhanced_v9a"
BRIDGE_CLASS = "SunPhraseRuleBatchBridgeMulti"
BRIDGE_REL = "tools/corenlp/SunPhraseRuleBatchBridgeMulti.java"


def run_corenlp_batch_v9(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
    patterns_rel: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    root = Path(project_root).resolve()
    runtime_home = Path(runtime_home).resolve()
    runtime_identity = _verify_runtime_identity(root, runtime_home)
    probe = resolve_corenlp_runtime(root, home=runtime_home)
    if not probe.ready or not probe.java_executable:
        raise Estg150B0DevelopmentError(f"CoreNLP runtime unavailable: {probe.reasons}")
    javac = shutil.which("javac")
    if not javac:
        raise Estg150B0DevelopmentError("javac is required")

    input_dir = work_dir / "corenlp-input"
    output_dir = work_dir / "corenlp-output"
    classes_dir = work_dir / "bridge-classes"
    input_dir.mkdir(parents=True)
    output_dir.mkdir()
    classes_dir.mkdir()
    input_paths: list[Path] = []
    source_by_id: dict[str, str] = {}
    for record in source_records:
        sample_id = record["sample_id"]
        source_text = record["approved_text_en"]
        path = input_dir / f"{sample_id}.txt"
        path.write_text(source_text, encoding="utf-8", newline="\n")
        input_paths.append(path)
        source_by_id[sample_id] = source_text
    file_list = work_dir / "corenlp-filelist.txt"
    file_list.write_text(
        "\n".join(str(path.resolve()) for path in input_paths) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    runtime_contract = load_object(root / "configs/sun_corenlp_runtime.json")["runtime"]
    classpath = os.pathsep.join(probe.classpath_entries)
    corenlp_command = [
        probe.java_executable,
        f"-Xmx{runtime_contract['heap_megabytes']}m",
        "-cp",
        classpath,
        "edu.stanford.nlp.pipeline.StanfordCoreNLP",
        "-annotators",
        ",".join(runtime_contract["annotators"]),
        "-outputFormat",
        "json",
        "-filelist",
        str(file_list.resolve()),
        "-outputDirectory",
        str(output_dir.resolve()),
        "-replaceExtension",
    ]
    started = time.perf_counter()
    _run(corenlp_command, cwd=root, timeout=max(1800, 12 * len(source_records)))
    corenlp_seconds = time.perf_counter() - started

    annotations: dict[str, dict[str, Any]] = {}
    sentence_refs: list[tuple[str, int]] = []
    tree_lines: list[str] = []
    for record in source_records:
        sample_id = record["sample_id"]
        candidates = list(output_dir.rglob(f"{sample_id}.json"))
        if len(candidates) != 1:
            raise Estg150B0DevelopmentError(
                f"expected one CoreNLP JSON for {sample_id}, found {len(candidates)}"
            )
        annotation = load_object(candidates[0])
        try:
            validate_annotation(annotation, source_by_id[sample_id])
        except CoreNLPContractError as exc:
            raise Estg150B0DevelopmentError(f"{sample_id}: {exc}") from exc
        annotations[sample_id] = annotation
        for local_index, sentence in enumerate(annotation["sentences"]):
            sentence_refs.append((sample_id, local_index))
            tree_lines.append(" ".join(sentence["parse"].split()))

    registry = load_object(root / patterns_rel)
    plan_path = work_dir / "rule-plan.tsv"
    pattern_count = _write_rule_plan(registry, plan_path)
    bridge_path = root / BRIDGE_REL
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
        str(bridge_path),
    ]
    _run(compile_command, cwd=root, timeout=180)
    tree_path = work_dir / "trees.txt"
    tree_path.write_text("\n".join(tree_lines) + "\n", encoding="utf-8", newline="\n")
    bridge_classpath = os.pathsep.join((str(classes_dir), classpath))
    bridge_started = time.perf_counter()
    bridge = _run(
        [
            probe.java_executable,
            "-cp",
            bridge_classpath,
            BRIDGE_CLASS,
            str(plan_path),
            str(tree_path),
        ],
        cwd=root,
        timeout=600,
    )
    bridge_seconds = time.perf_counter() - bridge_started
    global_cases, bridge_summary = parse_bridge_output_multi(bridge.stdout)
    if bridge_summary["pattern_count"] != pattern_count:
        raise Estg150B0DevelopmentError("bridge pattern count mismatch")
    if bridge_summary["tree_count"] != len(sentence_refs) or len(global_cases) != len(sentence_refs):
        raise Estg150B0DevelopmentError("bridge sentence coverage mismatch")
    cases_by_id: dict[str, list[dict[str, Any]]] = {
        record["sample_id"]: [] for record in source_records
    }
    for global_case, (sample_id, local_index) in zip(global_cases, sentence_refs, strict=True):
        cases_by_id[sample_id].append(
            {"sentence_index": local_index, "fields": global_case["fields"]}
        )
    return annotations, cases_by_id, {
        "runtime_identity": runtime_identity,
        "corenlp_seconds": corenlp_seconds,
        "bridge_seconds": bridge_seconds,
        "sentence_count": len(sentence_refs),
        "pattern_count": pattern_count,
        "match_count": bridge_summary["match_count"],
        "surgery_count": bridge_summary["surgery_count"],
        "terminal_tree_removal_count": bridge_summary["terminal_tree_removal_count"],
        "bridge_class": BRIDGE_CLASS,
        "bridge_source": BRIDGE_REL,
        "patterns_path": patterns_rel,
        "tsurgeon_enabled": False,
    }


def build_canonical_record_v9(
    *,
    sample_id: str,
    source_id: str,
    source_text: str,
    annotation: Mapping[str, Any],
    phrase_cases: Sequence[Mapping[str, Any]],
    clause_units: Sequence[Mapping[str, Any]],
    alignments: Sequence[Any],
    modality_decisions: Sequence[Any],
    lexicon: Any,
) -> dict[str, Any]:
    try:
        validate_annotation(annotation, source_text)
    except CoreNLPContractError as exc:
        raise Estg150B0DevelopmentError(str(exc)) from exc
    sentences = annotation["sentences"]
    if len(modality_decisions) != len(clause_units):
        raise Estg150B0DevelopmentError("modality decisions must match clause units")
    cases_by_sentence: dict[int, Mapping[str, Any]] = {}
    for case in phrase_cases:
        index = case.get("sentence_index")
        if not isinstance(index, int) or isinstance(index, bool) or index in cases_by_sentence:
            raise Estg150B0DevelopmentError("phrase case indexes must be unique integers")
        cases_by_sentence[index] = case

    clauses: list[dict[str, Any]] = []
    for unit_index, (unit, al, decision) in enumerate(
        zip(clause_units, alignments, modality_decisions, strict=True)
    ):
        sentence_indexes = unit["sentence_indexes"]
        if "clause_char_span" in unit:
            clause_start, clause_end = unit["clause_char_span"]
        else:
            clause_start = sentences[sentence_indexes[0]]["tokens"][0]["characterOffsetBegin"]
            clause_end = sentences[sentence_indexes[-1]]["tokens"][-1]["characterOffsetEnd"]
        clause_span = _plain_span(source_text, clause_start, clause_end)
        clause_id = f"{sample_id}.c{unit_index + 1}"
        clause_text = source_text[clause_start:clause_end]

        # tregex obs bag
        tregex_obs: dict[str, list] = {f: [] for f in EXTRACTION_ORDER}
        for sidx in sentence_indexes:
            fields = cases_by_sentence.get(sidx, {}).get("fields", {})
            sent = sentences[sidx]
            for field in tregex_obs:
                values = fields.get(field) or []
                if isinstance(values, Mapping):
                    values = [values]
                for obs in values:
                    if isinstance(obs, Mapping):
                        tregex_obs[field].append((sent, obs))

        scope, scope_decisions, scope_stats = resolve_scope_fields_v9(
            clause_text, clause_start, source_text, lexicon, tregex_obs
        )

        actors: list[dict[str, Any]] = []
        actions: list[dict[str, Any]] = []
        edge_specs: list[dict[str, Any]] = []
        for sidx in sentence_indexes:
            a, act, edges, _st = extract_actors_actions_edges(
                sentence=sentences[sidx],
                source_text=source_text,
                clause_start=clause_start,
                clause_end=clause_end,
                sentence_index=sidx,
                lexicon=lexicon,
            )
            base_a, base_act = len(actors), len(actions)
            actors.extend(a)
            actions.extend(act)
            for e in edges:
                edge_specs.append(
                    {
                        **e,
                        "actor_index": base_a + e["actor_index"],
                        "action_index": base_act + e["action_index"],
                    }
                )

        def finalize(spans: list[dict[str, Any]], singular: str) -> list[dict[str, Any]]:
            out = []
            for rank, sp in enumerate(spans, start=1):
                out.append(
                    {
                        "id": f"{clause_id}.{singular}.{rank}",
                        "text": sp["text"],
                        "start": sp["start"],
                        "end": sp["end"],
                        "normalized": sp.get("normalized")
                        or " ".join(sp["text"].casefold().split()),
                    }
                )
            return out

        mapped = {
            "actors": finalize(actors, "actor"),
            "actions": finalize(actions, "action"),
            "conditions": finalize(scope["condition"], "condition"),
            "constraints": finalize(scope["constraint"], "constraint"),
            "exceptions": finalize(scope["exception"], "exception"),
        }
        actor_action_map = []
        edge_evidence = []
        for e in edge_specs:
            ai, aci = e["actor_index"], e["action_index"]
            if ai < len(mapped["actors"]) and aci < len(mapped["actions"]):
                actor_action_map.append(
                    {
                        "actor_id": mapped["actors"][ai]["id"],
                        "action_id": mapped["actions"][aci]["id"],
                    }
                )
                edge_evidence.append(
                    {
                        "ownership_relation": e.get("ownership_relation"),
                        "sentence_index": e.get("sentence_index"),
                        "confidence": e.get("confidence"),
                        "actor_id": mapped["actors"][ai]["id"],
                        "action_id": mapped["actions"][aci]["id"],
                    }
                )

        modality_evidence = [dict(clause_span)]
        for sent, obs in tregex_obs.get("modality") or []:
            try:
                sp = _token_span(source_text, sent, obs)
                if sp["end"] > clause_start and sp["start"] < clause_end:
                    modality_evidence = [sp]
                    break
            except Exception:
                pass

        clauses.append(
            {
                "clause_id": clause_id,
                "clause_span": clause_span,
                "modality": {
                    "label": decision.label,
                    "evidence": modality_evidence[:1],
                    "route": decision.route.value,
                    "diagnostic": decision.diagnostic,
                },
                **mapped,
                "actor_action_map": actor_action_map,
                "order_relations": [],
                "alignment": {
                    "status": al.status.value,
                    "supported": al.supported,
                    "confidence": al.confidence,
                    "evidence": al.evidence,
                },
                "edge_evidence": edge_evidence,
                "scope_stats": scope_stats,
            }
        )

    record = {
        "schema_version": SCHEMA_VERSION,
        "sample_id": sample_id,
        "source_id": source_id,
        "source_text": source_text,
        "clauses": clauses,
        "method": {"name": METHOD_ID, "schema_source": SCHEMA_SOURCE},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
    }
    report = validate_canonical(record)
    if not (report.schema_valid and report.cross_field_valid):
        raise Estg150B0DevelopmentError(
            "composed canonical record is invalid: " + "; ".join(report.errors)
        )
    return record


def run_b0_batch_v9(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
    device: str = "cpu",
    profile: B0V9Profile | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = Path(project_root).resolve()
    profile = profile or PROFILE_V9A
    if profile.tsurgeon_enabled:
        raise Estg150B0DevelopmentError("v9 profile forbids tsurgeon unless truly implemented")
    s26_config = load_s26_config(root / profile.s26_config_rel)
    annotations, cases_by_id, runtime = run_corenlp_batch_v9(
        root,
        source_records,
        runtime_home=runtime_home,
        work_dir=work_dir,
        patterns_rel=profile.tregex_registry_rel,
    )
    lexicon = load_lexicon_v2(root)
    classifier_started = time.perf_counter()
    try:
        classifier = LockedBertTextCNNInference.load(root, s26_config, device=device)
    except SunB0CompositionError as exc:
        raise Estg150B0DevelopmentError(str(exc)) from exc

    # Plan clauses + alignments; collect only supported DE clause texts + record-level DE
    planned: list[dict[str, Any]] = []
    all_clf_texts: list[str] = []
    # each entry maps a classifier text index to (plan_index, clause_index|None)
    clf_index_map: list[tuple[int, int | None]] = []
    for plan_i, record in enumerate(source_records):
        sample_id = record["sample_id"]
        annotation = annotations[sample_id]
        source_text = record["approved_text_en"]
        clause_units, seg_stats = plan_clause_units_v4(annotation, source_text)
        en_texts = []
        for unit in clause_units:
            s, e = unit["clause_char_span"]
            en_texts.append(source_text[s:e])
        alignments = align_de_to_en_units(record["raw_text_de"], en_texts)
        align_summary = summarize_alignments(alignments)
        texts, index_map = collect_classifier_inputs(
            alignments, record_level_de=record["raw_text_de"]
        )
        base = len(all_clf_texts)
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
                "clf_base": base,
                "clf_count": len(texts),
            }
        )

    # Safety: never classify placeholder
    if any(t.strip() in {".", ""} for t in all_clf_texts):
        raise Estg150B0DevelopmentError("placeholder/empty classifier input forbidden in v9")

    predictions = _predict_in_batches(classifier, all_clf_texts)
    classifier_seconds = time.perf_counter() - classifier_started
    if len(predictions) != len(all_clf_texts):
        raise Estg150B0DevelopmentError("classifier output size mismatch")

    # group predictions back
    pred_by_plan: dict[int, dict[str, Any]] = {}
    for (plan_i, clause_i), pred in zip(clf_index_map, predictions, strict=True):
        bucket = pred_by_plan.setdefault(plan_i, {"clauses": {}, "record": None})
        if clause_i is None:
            bucket["record"] = pred
        else:
            bucket["clauses"][clause_i] = pred

    compose_started = time.perf_counter()
    canonical_records: list[dict[str, Any]] = []
    route_counts: dict[str, int] = {}
    label_counts: dict[str, int] = {}
    confidence_sum = 0.0
    placeholder_count = 0
    lexicon_stats_agg = {
        "loaded_active_total": lexicon.active_total(),
        "active_counts": dict(lexicon.active_counts),
        "scope_invocations": 0,
        "scope_raw_matches": 0,
        "scope_accepted": 0,
        "scope_rejected": 0,
        "legacy_fallback": 0,
    }
    align_agg = {
        "total": 0,
        "supported": 0,
        "unsupported": 0,
        "by_status": {},
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
        for ci, (en, al) in enumerate(zip(item["en_texts"], item["alignments"], strict=True)):
            clause_pred = bucket["clauses"].get(ci) if al.supported else None
            # double-check: never pass clause pred when unsupported
            if not al.supported:
                clause_pred = None
            dec = resolve_modality_v9(
                english_clause=en,
                alignment=al,
                clause_classifier=clause_pred,
                record_classifier=record_pred,
                lexicon=lexicon,
            )
            decisions.append(dec)
            route_counts[dec.route.value] = route_counts.get(dec.route.value, 0) + 1
            label_counts[dec.label] = label_counts.get(dec.label, 0) + 1
            confidence_sum += dec.confidence
            if dec.diagnostic.get("placeholder_classifier_input"):
                placeholder_count += 1
        for st, n in item["align_summary"]["by_status"].items():
            align_agg["by_status"][st] = align_agg["by_status"].get(st, 0) + n
        align_agg["total"] += item["align_summary"]["total"]
        align_agg["supported"] += item["align_summary"]["supported"]
        align_agg["unsupported"] += item["align_summary"]["unsupported"]

        canonical = build_canonical_record_v9(
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
        for cl in canonical["clauses"]:
            edge_stats["edges"] += len(cl.get("actor_action_map") or [])
            ss = cl.get("scope_stats") or {}
            for k in ("lexicon_invocations", "raw_matches", "scope_accepted", "scope_rejected", "legacy_fallback"):
                key = {
                    "lexicon_invocations": "scope_invocations",
                    "raw_matches": "scope_raw_matches",
                    "scope_accepted": "scope_accepted",
                    "scope_rejected": "scope_rejected",
                    "legacy_fallback": "legacy_fallback",
                }[k]
                lexicon_stats_agg[key] += int(ss.get(k, 0))
        canonical_records.append(canonical)

    if placeholder_count != 0:
        raise Estg150B0DevelopmentError("v9 produced placeholder classifier diagnostics")

    compose_seconds = time.perf_counter() - compose_started
    total_seconds = (
        runtime["corenlp_seconds"]
        + runtime["bridge_seconds"]
        + classifier_seconds
        + compose_seconds
    )
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
    runtime.update(
        {
            "classifier_seconds": classifier_seconds,
            "compose_seconds": compose_seconds,
            "total_seconds": total_seconds,
            "device": device,
            "record_count": len(canonical_records),
            "predicted_clause_count": sum(len(r["clauses"]) for r in canonical_records),
            "classifier_label_counts_by_clause": dict(sorted(label_counts.items())),
            "classifier_mean_confidence": confidence_sum / max(sum(label_counts.values()), 1),
            "modality_route_counts": dict(sorted(route_counts.items())),
            "alignment_summary": align_agg,
            "lexicon_v2": {
                "lexicon_id": lexicon.lexicon_id,
                "manifest_sha256": lexicon.manifest_sha256,
                "category_file_sha256": dict(lexicon.category_file_sha256),
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
