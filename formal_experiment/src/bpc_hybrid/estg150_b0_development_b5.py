"""B5: genuine sequential Tsurgeon with post-surgery Tregex consumption.

The bridge emits condition/constraint/exception observations before pruning.
Tsurgeon therefore does not directly repair B4 constraint false positives.  Its
direct purpose in this isolated development candidate is to prevent those
context subtrees from polluting later action/actor matches on the same working
constituency tree.  The attributable targets are actor/action and overall
precision; constraint movement is reported only as a side effect.

Actor/action candidates in this module come exclusively from explicit
``phase=post_surgery`` B5 bridge observations.  Dependency information may
choose an action-head run and connect already-existing actor/action spans, but
it cannot create or expand a candidate.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.b0_v10.actor_action_tregex_b5 import (
    extract_actors_actions_edges_b5,
)
from bpc_hybrid.b0_v10.alignment import align_de_to_en_units, summarize_alignments
from bpc_hybrid.b0_v10.modality import resolve_modality_v10
from bpc_hybrid.b0_v10.pipeline import collect_classifier_inputs
from bpc_hybrid.b0_v10.profile import B0V10Profile, PROFILE_V10A
from bpc_hybrid.b0_v10.scope import resolve_scope_fields_v10
from bpc_hybrid.estg150_b0_development import (
    Estg150B0DevelopmentError,
    load_object,
    sha256_file,
)
from bpc_hybrid.estg150_b0_development_v2 import _predict_in_batches, _run
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
    SunB0CompositionError,
    load_s26_config,
)


METHOD_ID = "sun_rule_only"
METHOD_VARIANT = "b0_enhanced_b5_tsurgeon_post_surgery_tregex_consumed"
BRIDGE_CLASS = "SunPhraseRuleBatchBridgeTsurgeonB5"
BRIDGE_REL = "tools/corenlp/SunPhraseRuleBatchBridgeTsurgeonB5.java"
REGISTRY_REL = "resources/corenlp/sun_phrase_patterns_v5_b5_tsurgeon.json"
PARENT_REGISTRY_REL = "resources/corenlp/sun_phrase_patterns_v3_enhanced.json"
PARENT_REGISTRY_SHA256 = (
    "f49bad50fb6236137f1208aeef572d2a78c789726363897c637dc464c780e142"
)


def _flatten_patterns(registry: Mapping[str, Any]) -> list[tuple[str, str]]:
    flattened: list[tuple[str, str]] = []
    for field in registry.get("fields") or []:
        name = field.get("field")
        patterns = field.get("tregex_patterns")
        if not isinstance(name, str) or not isinstance(patterns, list):
            raise Estg150B0DevelopmentError("malformed Tregex field registry")
        for pattern in patterns:
            if not isinstance(pattern, str):
                raise Estg150B0DevelopmentError("non-string Tregex pattern")
            flattened.append((name, pattern))
    return flattened


def validate_b5_registry(project_root: Path) -> dict[str, Any]:
    """Prove exact v3 pattern identity/order and the fixed per-pattern mapping."""
    root = Path(project_root).resolve()
    parent_path = root / PARENT_REGISTRY_REL
    candidate_path = root / REGISTRY_REL
    if sha256_file(parent_path) != PARENT_REGISTRY_SHA256:
        raise Estg150B0DevelopmentError("v3 parent Tregex registry hash drifted")
    parent = load_object(parent_path)
    candidate = load_object(candidate_path)
    if tuple(parent.get("extraction_order") or ()) != EXTRACTION_ORDER:
        raise Estg150B0DevelopmentError("v3 extraction order drifted")
    if tuple(candidate.get("extraction_order") or ()) != EXTRACTION_ORDER:
        raise Estg150B0DevelopmentError("B5 extraction order drifted")
    parent_flat = _flatten_patterns(parent)
    candidate_flat = _flatten_patterns(candidate)
    if len(parent_flat) != 29 or candidate_flat != parent_flat:
        raise Estg150B0DevelopmentError("B5 patterns are not exact ordered v3 identity")

    entries: list[dict[str, Any]] = []
    for field in candidate.get("fields") or []:
        patterns = field["tregex_patterns"]
        pattern_entries = field.get("pattern_entries")
        if not isinstance(pattern_entries, list) or len(pattern_entries) != len(patterns):
            raise Estg150B0DevelopmentError("B5 requires one operation entry per pattern")
        if field.get("tsurgeon_operations") != []:
            raise Estg150B0DevelopmentError("ambiguous field-level B5 operation is forbidden")
        for index, (pattern, entry) in enumerate(zip(patterns, pattern_entries, strict=True)):
            if (
                not isinstance(entry, Mapping)
                or entry.get("pattern_index") != index
                or entry.get("tregex") != pattern
                or entry.get("global_pattern_index") != len(entries)
            ):
                raise Estg150B0DevelopmentError("B5 per-pattern identity metadata drifted")
            field_name = field["field"]
            expected_operation: str | None = None
            if field_name == "condition":
                expected_operation = "prune condition"
            elif field_name == "constraint":
                expected_operation = "prune constraint"
            elif field_name == "exception" and index <= 3:
                expected_operation = "prune exception"
            if entry.get("tsurgeon_operation") != expected_operation:
                raise Estg150B0DevelopmentError("B5 fixed operation mapping drifted")
            if entry.get("surgery_enabled") is not (expected_operation is not None):
                raise Estg150B0DevelopmentError("B5 surgery_enabled metadata drifted")
            entries.append(dict(entry, field=field_name))
    if len(entries) != 29:
        raise Estg150B0DevelopmentError("B5 candidate pattern count must be 29")
    declared = {
        "parent_pattern_count": 29,
        "candidate_pattern_count": 29,
        "pattern_strings_exact_parent": True,
        "pattern_order_exact_parent": True,
        "only_operation_metadata_changed": True,
    }
    if any(candidate.get(key) != value for key, value in declared.items()):
        raise Estg150B0DevelopmentError("B5 registry proof metadata drifted")
    return {
        **declared,
        "parent_registry_sha256": sha256_file(parent_path),
        "candidate_registry_sha256": sha256_file(candidate_path),
        "entries": entries,
    }


def write_b5_rule_plan(project_root: Path, target: Path) -> dict[str, Any]:
    proof = validate_b5_registry(project_root)
    lines: list[str] = []
    for entry in proof["entries"]:
        pattern = entry["tregex"]
        operation = entry.get("tsurgeon_operation") or ""
        if any(char in pattern for char in ("\t", "\n", "\r")):
            raise Estg150B0DevelopmentError("B5 Tregex pattern is not TSV-safe")
        if any(char in operation for char in ("\t", "\n", "\r")):
            raise Estg150B0DevelopmentError("B5 Tsurgeon operation is not TSV-safe")
        lines.append(f"{entry['field']}\t{pattern}\t{operation}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    proof["plan_pattern_count"] = len(lines)
    return proof


def _parse_token_runs(raw: str) -> list[tuple[int, int]]:
    if not raw:
        raise Estg150B0DevelopmentError("B5 bridge match omitted original-token runs")
    runs: list[tuple[int, int]] = []
    for part in raw.split(","):
        pieces = part.split("-", 1)
        if len(pieces) != 2:
            raise Estg150B0DevelopmentError("malformed B5 original-token run")
        try:
            begin, end = int(pieces[0]), int(pieces[1])
        except ValueError as exc:
            raise Estg150B0DevelopmentError("non-integer B5 original-token run") from exc
        if begin < 0 or end <= begin:
            raise Estg150B0DevelopmentError("invalid B5 original-token run bounds")
        runs.append((begin, end))
    if runs != sorted(runs) or any(a[1] > b[0] for a, b in zip(runs, runs[1:])):
        raise Estg150B0DevelopmentError("B5 original-token runs overlap or are unordered")
    return runs


def parse_bridge_output_b5(output: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Strictly parse the versioned bridge; any malformed line fails closed."""
    cases: dict[int, dict[str, list[dict[str, Any]]]] = {}
    final_indexes: set[int] = set()
    scalar: dict[str, int] = {}
    per_field: dict[str, dict[str, int]] = {
        field: {"attempted": 0, "accepted": 0, "rejected": 0, "matches": 0}
        for field in EXTRACTION_ORDER
    }
    seen_field_summaries: set[tuple[str, str]] = set()
    summary_values: tuple[int, int, int, int] | None = None
    scalar_names = {
        "RAW_MATCH_COUNT": "raw_match_count",
        "TERMINAL_TREE_REMOVALS": "terminal_tree_removal_count",
        "SURGERY_ATTEMPTED": "surgery_attempted",
        "SURGERY_ACCEPTED": "surgery_accepted",
        "SURGERY_REJECTED": "surgery_rejected",
        "SOURCE_SLICE_FAILURES": "source_slice_failures",
        "POST_SURGERY_ACTION_MATCHES": "post_surgery_action_matches",
        "POST_SURGERY_ACTOR_MATCHES": "post_surgery_actor_matches",
    }
    field_line_names = {
        "FIELD_SURGERY_ATTEMPTED": "attempted",
        "FIELD_SURGERY_ACCEPTED": "accepted",
        "FIELD_SURGERY_REJECTED": "rejected",
        "FIELD_MATCH": "matches",
    }
    for line_number, raw in enumerate(output.splitlines(), start=1):
        if not raw:
            continue
        parts = raw.split("\t")
        tag = parts[0]
        try:
            if tag == "MATCH" and len(parts) == 11:
                index = int(parts[1])
                field = parts[2]
                begin, end = int(parts[3]), int(parts[4])
                pattern_index = int(parts[6])
                if index < 0 or field not in EXTRACTION_ORDER or begin < 0 or end <= begin:
                    raise ValueError("invalid B5 MATCH identity or bounds")
                phase = parts[8]
                expected_phase = "post_surgery" if field in {"action", "actor"} else "pre_surgery"
                if phase != expected_phase or parts[7] not in {"true", "false"}:
                    raise ValueError("invalid B5 MATCH provenance")
                runs = _parse_token_runs(parts[10])
                if runs[0][0] != begin or runs[-1][1] != end:
                    raise ValueError("B5 run envelope disagrees with diagnostic bounds")
                fields = cases.setdefault(index, {name: [] for name in EXTRACTION_ORDER})
                fields[field].append(
                    {
                        "begin": begin,
                        "end": end,
                        "text": parts[5],
                        "pattern_index": pattern_index,
                        "operation_applied": parts[7] == "true",
                        "phase": phase,
                        "surgery_status": parts[9],
                        "token_runs": parts[10],
                    }
                )
            elif tag == "MISS" and len(parts) == 3:
                index = int(parts[1])
                if index < 0 or parts[2] not in EXTRACTION_ORDER:
                    raise ValueError("invalid B5 MISS")
                cases.setdefault(index, {name: [] for name in EXTRACTION_ORDER})
            elif tag == "FINAL" and len(parts) == 3:
                index = int(parts[1])
                if index < 0 or index in final_indexes or not parts[2]:
                    raise ValueError("invalid or duplicate B5 FINAL")
                final_indexes.add(index)
            elif tag in scalar_names and len(parts) == 2:
                key = scalar_names[tag]
                if key in scalar:
                    raise ValueError("duplicate B5 scalar summary")
                scalar[key] = int(parts[1])
            elif tag in field_line_names and len(parts) == 3:
                field = parts[1]
                if field not in per_field:
                    raise ValueError("unknown B5 field summary")
                metric = field_line_names[tag]
                if (field, metric) in seen_field_summaries:
                    raise ValueError("duplicate B5 per-field summary")
                seen_field_summaries.add((field, metric))
                per_field[field][metric] = int(parts[2])
            elif tag == "SUMMARY" and len(parts) == 5:
                if summary_values is not None:
                    raise ValueError("duplicate B5 SUMMARY")
                summary_values = tuple(int(value) for value in parts[1:])  # type: ignore[assignment]
            else:
                raise ValueError(f"unrecognized B5 bridge line {line_number}")
        except (TypeError, ValueError) as exc:
            raise Estg150B0DevelopmentError(
                f"malformed B5 bridge output at line {line_number}: {raw!r}"
            ) from exc
    required_scalars = set(scalar_names.values())
    if summary_values is None or set(scalar) != required_scalars:
        raise Estg150B0DevelopmentError("B5 bridge summary is incomplete")
    if len(seen_field_summaries) != len(EXTRACTION_ORDER) * len(field_line_names):
        raise Estg150B0DevelopmentError("B5 per-field summary is incomplete")
    tree_count, pattern_count, match_count, accepted_count = summary_values
    if tree_count < 0 or pattern_count != 29 or sorted(cases) != list(range(tree_count)):
        raise Estg150B0DevelopmentError("B5 bridge tree/pattern coverage mismatch")
    if final_indexes != set(range(tree_count)):
        raise Estg150B0DevelopmentError("B5 bridge FINAL coverage mismatch")
    emitted_match_count = sum(
        len(values) for fields in cases.values() for values in fields.values()
    )
    if match_count != emitted_match_count or scalar["raw_match_count"] != match_count:
        raise Estg150B0DevelopmentError("B5 raw match summary mismatch")
    for field in EXTRACTION_ORDER:
        emitted_for_field = sum(len(fields[field]) for fields in cases.values())
        if per_field[field]["matches"] != emitted_for_field:
            raise Estg150B0DevelopmentError("B5 per-field match summary mismatch")
    if scalar["surgery_attempted"] != scalar["surgery_accepted"] + scalar["surgery_rejected"]:
        raise Estg150B0DevelopmentError("B5 surgery accounting mismatch")
    if accepted_count != scalar["surgery_accepted"]:
        raise Estg150B0DevelopmentError("B5 SUMMARY accepted count mismatch")
    applied_count = sum(
        int(observation["operation_applied"])
        for fields in cases.values()
        for values in fields.values()
        for observation in values
    )
    if applied_count != scalar["surgery_accepted"]:
        raise Estg150B0DevelopmentError("B5 operation_applied accounting mismatch")
    if sum(v["attempted"] for v in per_field.values()) != scalar["surgery_attempted"]:
        raise Estg150B0DevelopmentError("B5 per-field attempted count mismatch")
    if sum(v["accepted"] for v in per_field.values()) != scalar["surgery_accepted"]:
        raise Estg150B0DevelopmentError("B5 per-field accepted count mismatch")
    if sum(v["rejected"] for v in per_field.values()) != scalar["surgery_rejected"]:
        raise Estg150B0DevelopmentError("B5 per-field rejected count mismatch")
    if scalar["post_surgery_action_matches"] != sum(
        len(fields["action"]) for fields in cases.values()
    ) or scalar["post_surgery_actor_matches"] != sum(
        len(fields["actor"]) for fields in cases.values()
    ):
        raise Estg150B0DevelopmentError("B5 post-surgery match funnel mismatch")
    ordered = [
        {"sentence_index": index, "fields": cases[index]}
        for index in range(tree_count)
    ]
    return ordered, {
        "tree_count": tree_count,
        "pattern_count": pattern_count,
        **scalar,
        "per_field": per_field,
    }


def run_corenlp_batch_b5(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
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

    plan_path = work_dir / "rule-plan.tsv"
    registry_proof = write_b5_rule_plan(root, plan_path)
    bridge_path = root / BRIDGE_REL
    _run(
        [
            javac,
            "--release",
            "8",
            "-Xlint:-options",
            "-encoding",
            "UTF-8",
            "-cp",
            classpath,
            "-d",
            str(classes_dir),
            str(bridge_path),
        ],
        cwd=root,
        timeout=180,
    )
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
    global_cases, bridge_summary = parse_bridge_output_b5(bridge.stdout)
    if len(global_cases) != len(sentence_refs):
        raise Estg150B0DevelopmentError("B5 bridge sentence coverage mismatch")
    if bridge_summary["source_slice_failures"] != 0:
        raise Estg150B0DevelopmentError("B5 bridge original-token identity drifted")
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
        **bridge_summary,
        "match_count": bridge_summary["raw_match_count"],
        "surgery_count": bridge_summary["surgery_accepted"],
        "bridge_class": BRIDGE_CLASS,
        "bridge_source": BRIDGE_REL,
        "patterns_path": REGISTRY_REL,
        "registry_proof": {k: v for k, v in registry_proof.items() if k != "entries"},
        "tsurgeon_enabled": True,
    }


def build_canonical_record_b5(
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
) -> tuple[dict[str, Any], dict[str, int]]:
    """Compose one record while consuming only post-surgery actor/action matches."""
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

    aggregate = {
        "dependency_candidate_span_count": 0,
        "dependency_fallback_count": 0,
        "post_surgery_action_obs": 0,
        "post_surgery_actor_obs": 0,
        "final_tregex_action_spans": 0,
        "final_tregex_actor_spans": 0,
        "source_slice_failures": 0,
        "discontinuous_actor_rejected": 0,
        "edges_emitted": 0,
    }
    clauses: list[dict[str, Any]] = []
    for unit_index, (unit, alignment, decision) in enumerate(
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

        tregex_obs: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {
            field: [] for field in EXTRACTION_ORDER
        }
        for sentence_index in sentence_indexes:
            fields = cases_by_sentence.get(sentence_index, {}).get("fields", {})
            sentence = sentences[sentence_index]
            for field in tregex_obs:
                values = fields.get(field) or []
                if isinstance(values, Mapping):
                    values = [values]
                for observation in values:
                    if isinstance(observation, Mapping):
                        tregex_obs[field].append((sentence, observation))

        # Context spans intentionally consume the pre-surgery observations.
        scope, _scope_decisions, scope_stats = resolve_scope_fields_v10(
            clause_text=clause_text,
            clause_start=clause_start,
            source_text=source_text,
            lexicon=lexicon,
            tregex_obs=tregex_obs,
        )

        actors: list[dict[str, Any]] = []
        actions: list[dict[str, Any]] = []
        edge_specs: list[dict[str, Any]] = []
        clause_consumer_stats = {key: 0 for key in aggregate}
        for sentence_index in sentence_indexes:
            fields = cases_by_sentence.get(sentence_index, {}).get("fields", {})
            action_observations = fields.get("action") or []
            actor_observations = fields.get("actor") or []
            if isinstance(action_observations, Mapping):
                action_observations = [action_observations]
            if isinstance(actor_observations, Mapping):
                actor_observations = [actor_observations]
            try:
                new_actors, new_actions, new_edges, stats = extract_actors_actions_edges_b5(
                    sentence=sentences[sentence_index],
                    source_text=source_text,
                    clause_start=clause_start,
                    clause_end=clause_end,
                    sentence_index=sentence_index,
                    lexicon=lexicon,
                    action_observations=action_observations,
                    actor_observations=actor_observations,
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise Estg150B0DevelopmentError(
                    f"{sample_id}: malformed post-surgery actor/action observation"
                ) from exc
            base_actor = len(actors)
            base_action = len(actions)
            actors.extend(new_actors)
            actions.extend(new_actions)
            for edge in new_edges:
                edge_specs.append(
                    {
                        **edge,
                        "actor_index": base_actor + edge["actor_index"],
                        "action_index": base_action + edge["action_index"],
                    }
                )
            for key in aggregate:
                value = int(stats.get(key, 0))
                clause_consumer_stats[key] += value
                aggregate[key] += value

        if clause_consumer_stats["source_slice_failures"] != 0:
            raise Estg150B0DevelopmentError("B5 source-slice failure must fail closed")
        if clause_consumer_stats["dependency_candidate_span_count"] != 0:
            raise Estg150B0DevelopmentError("B5 dependency candidate span is forbidden")
        if clause_consumer_stats["dependency_fallback_count"] != 0:
            raise Estg150B0DevelopmentError("B5 dependency fallback is forbidden")

        def finalize(spans: list[dict[str, Any]], singular: str) -> list[dict[str, Any]]:
            finalized: list[dict[str, Any]] = []
            for rank, span in enumerate(spans, start=1):
                if source_text[int(span["start"]) : int(span["end"])] != span["text"]:
                    raise Estg150B0DevelopmentError("B5 final span failed source-slice identity")
                finalized.append(
                    {
                        "id": f"{clause_id}.{singular}.{rank}",
                        "text": span["text"],
                        "start": span["start"],
                        "end": span["end"],
                        "normalized": span.get("normalized")
                        or " ".join(span["text"].casefold().split()),
                    }
                )
            return finalized

        mapped = {
            "actors": finalize(actors, "actor"),
            "actions": finalize(actions, "action"),
            "conditions": finalize(scope["condition"], "condition"),
            "constraints": finalize(scope["constraint"], "constraint"),
            "exceptions": finalize(scope["exception"], "exception"),
        }
        actor_action_map: list[dict[str, str]] = []
        edge_evidence: list[dict[str, Any]] = []
        for edge in edge_specs:
            actor_index = int(edge["actor_index"])
            action_index = int(edge["action_index"])
            if actor_index >= len(mapped["actors"]) or action_index >= len(mapped["actions"]):
                raise Estg150B0DevelopmentError("B5 ownership edge references a missing span")
            actor_id = mapped["actors"][actor_index]["id"]
            action_id = mapped["actions"][action_index]["id"]
            actor_action_map.append({"actor_id": actor_id, "action_id": action_id})
            edge_evidence.append(
                {
                    "ownership_relation": edge.get("ownership_relation"),
                    "sentence_index": edge.get("sentence_index"),
                    "confidence": edge.get("confidence"),
                    "actor_id": actor_id,
                    "action_id": action_id,
                }
            )

        modality_evidence = [dict(clause_span)]
        for sentence, observation in tregex_obs.get("modality") or []:
            try:
                evidence = _token_span(source_text, sentence, observation)
            except Exception:
                continue
            if evidence["end"] > clause_start and evidence["start"] < clause_end:
                modality_evidence = [evidence]
                break
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
                    "status": alignment.status.value,
                    "supported": alignment.heuristic_supported,
                    "confidence": alignment.confidence,
                    "evidence": alignment.evidence,
                },
                "edge_evidence": edge_evidence,
                "scope_stats": scope_stats,
                "actor_action_b5_stats": {
                    **clause_consumer_stats,
                    "candidate_route": "post_surgery_tregex_only",
                },
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
            "B5 canonical record is invalid: " + "; ".join(report.errors)
        )
    return record, aggregate


def run_b0_batch_b5(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
    device: str = "cpu",
    profile: B0V10Profile | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the isolated B5 candidate with v10-A modality/segmentation routes."""
    root = Path(project_root).resolve()
    profile = profile or PROFILE_V10A
    if profile.profile_id != PROFILE_V10A.profile_id:
        raise Estg150B0DevelopmentError("B5 is bound to the exact v10-A profile")
    s26_config = load_s26_config(root / profile.s26_config_rel)
    annotations, cases_by_id, runtime = run_corenlp_batch_b5(
        root,
        source_records,
        runtime_home=runtime_home,
        work_dir=work_dir,
    )
    # Explicitly load only the frozen v2 runtime.  B4's v3 lexicon is excluded.
    lexicon = load_lexicon_v2(root)
    classifier_started = time.perf_counter()
    try:
        classifier = LockedBertTextCNNInference.load(root, s26_config, device=device)
    except SunB0CompositionError as exc:
        raise Estg150B0DevelopmentError(str(exc)) from exc

    planned: list[dict[str, Any]] = []
    all_classifier_texts: list[str] = []
    classifier_index_map: list[tuple[int, int | None]] = []
    for plan_index, source_record in enumerate(source_records):
        sample_id = source_record["sample_id"]
        annotation = annotations[sample_id]
        source_text = source_record["approved_text_en"]
        clause_units, segmentation_stats = plan_clause_units_v4(annotation, source_text)
        english_texts = [
            source_text[unit["clause_char_span"][0] : unit["clause_char_span"][1]]
            for unit in clause_units
        ]
        alignments = align_de_to_en_units(source_record["raw_text_de"], english_texts)
        alignment_summary = summarize_alignments(alignments)
        texts, index_map = collect_classifier_inputs(
            alignments, record_level_de=source_record["raw_text_de"]
        )
        for local_index, clause_index in enumerate(index_map):
            all_classifier_texts.append(texts[local_index])
            classifier_index_map.append((plan_index, clause_index))
        planned.append(
            {
                "record": source_record,
                "clause_units": clause_units,
                "english_texts": english_texts,
                "alignments": alignments,
                "alignment_summary": alignment_summary,
                "segmentation_stats": segmentation_stats,
            }
        )
    if any(text.strip() in {"", "."} for text in all_classifier_texts):
        raise Estg150B0DevelopmentError("placeholder/empty classifier input forbidden in B5")
    predictions = _predict_in_batches(classifier, all_classifier_texts)
    classifier_seconds = time.perf_counter() - classifier_started
    if len(predictions) != len(all_classifier_texts):
        raise Estg150B0DevelopmentError("B5 classifier output size mismatch")

    prediction_by_plan: dict[int, dict[str, Any]] = {}
    for (plan_index, clause_index), prediction in zip(
        classifier_index_map, predictions, strict=True
    ):
        bucket = prediction_by_plan.setdefault(plan_index, {"clauses": {}, "record": None})
        if clause_index is None:
            bucket["record"] = prediction
        else:
            bucket["clauses"][clause_index] = prediction

    compose_started = time.perf_counter()
    canonical_records: list[dict[str, Any]] = []
    route_counts: dict[str, int] = {}
    label_counts: dict[str, int] = {}
    confidence_sum = 0.0
    placeholder_count = 0
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
    alignment_aggregate: dict[str, Any] = {
        "total": 0,
        "heuristic_supported": 0,
        "validated": 0,
        "unsupported": 0,
        "by_status": {},
        "note": "heuristic_supported is not verified alignment",
    }
    actor_action_aggregate = {
        "dependency_candidate_span_count": 0,
        "dependency_fallback_count": 0,
        "post_surgery_action_obs": 0,
        "post_surgery_actor_obs": 0,
        "final_tregex_action_spans": 0,
        "final_tregex_actor_spans": 0,
        "source_slice_failures": 0,
        "discontinuous_actor_rejected": 0,
        "edges_emitted": 0,
    }
    edge_stats = {"edges": 0}

    for plan_index, item in enumerate(planned):
        source_record = item["record"]
        sample_id = source_record["sample_id"]
        bucket = prediction_by_plan[plan_index]
        record_prediction = bucket["record"]
        if record_prediction is None:
            raise Estg150B0DevelopmentError(f"missing record prediction for {sample_id}")
        decisions = []
        for clause_index, (english_text, alignment) in enumerate(
            zip(item["english_texts"], item["alignments"], strict=True)
        ):
            clause_prediction = (
                bucket["clauses"].get(clause_index)
                if alignment.heuristic_supported
                else None
            )
            decision = resolve_modality_v10(
                english_clause=english_text,
                alignment=alignment,
                clause_classifier=clause_prediction,
                record_classifier=record_prediction,
                lexicon=lexicon,
            )
            decisions.append(decision)
            route_counts[decision.route.value] = route_counts.get(decision.route.value, 0) + 1
            label_counts[decision.label] = label_counts.get(decision.label, 0) + 1
            confidence_sum += decision.confidence
            if decision.diagnostic.get("placeholder_classifier_input"):
                placeholder_count += 1
        for status, count in item["alignment_summary"]["by_status"].items():
            alignment_aggregate["by_status"][status] = (
                alignment_aggregate["by_status"].get(status, 0) + count
            )
        alignment_aggregate["total"] += item["alignment_summary"]["total"]
        alignment_aggregate["heuristic_supported"] += item["alignment_summary"][
            "heuristic_supported_count"
        ]
        alignment_aggregate["validated"] += item["alignment_summary"]["validated_count"]
        alignment_aggregate["unsupported"] += item["alignment_summary"]["unsupported_count"]

        canonical, consumer_stats = build_canonical_record_b5(
            sample_id=sample_id,
            source_id=f"estg_legacy_{source_record['legacy_record_id']}",
            source_text=source_record["approved_text_en"],
            annotation=annotations[sample_id],
            phrase_cases=cases_by_id[sample_id],
            clause_units=item["clause_units"],
            alignments=item["alignments"],
            modality_decisions=decisions,
            lexicon=lexicon,
        )
        for key in actor_action_aggregate:
            actor_action_aggregate[key] += int(consumer_stats.get(key, 0))
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
                lexicon_stats_aggregate[aggregate_key] += int(scope_stats.get(source_key, 0))
        canonical_records.append(canonical)

    if placeholder_count != 0:
        raise Estg150B0DevelopmentError("B5 produced placeholder classifier diagnostics")
    if actor_action_aggregate["dependency_candidate_span_count"] != 0:
        raise Estg150B0DevelopmentError("B5 dependency candidates must remain zero")
    if actor_action_aggregate["dependency_fallback_count"] != 0:
        raise Estg150B0DevelopmentError("B5 dependency fallback must remain zero")
    if actor_action_aggregate["source_slice_failures"] != 0:
        raise Estg150B0DevelopmentError("B5 source-slice failures must remain zero")

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
            "alignment_summary": alignment_aggregate,
            "lexicon_v2": {
                "lexicon_id": lexicon.lexicon_id,
                "manifest_sha256": lexicon.manifest_sha256,
                "category_file_sha256": dict(lexicon.category_file_sha256),
                **lexicon_stats_aggregate,
                "modality_patterns_compiled": len(lexicon.modality_patterns),
            },
            "actor_action_b5": {
                **actor_action_aggregate,
                "candidate_route": "post_surgery_tregex_only",
            },
            "edge_stats": edge_stats,
            "placeholder_classifier_count": placeholder_count,
            "method_id": METHOD_ID,
            "method_variant": METHOD_VARIANT,
            "profile_id": profile.profile_id,
            "paper_faithful_b0": False,
            "b4_lexicon_loaded": False,
            "s26_config_rel": profile.s26_config_rel,
        }
    )
    return attempts, runtime
