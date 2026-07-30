"""Paper-specification reconstruction of Sun et al. Stage 2 on EStG-150.

The implementation follows the published Section 4.2.2 rule families and
execution dependency.  It deliberately excludes the later project-specific
v10 scope, alignment, segmentation, definition, and ownership resolvers.
The authors' complete marker inventory and original source are unavailable;
the marker files supplied by the caller are therefore an explicit parameter
substitution and never an exact-original claim.
"""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.estg150_b0_development import (
    Estg150B0DevelopmentError,
    _predict_in_batches,
    _run,
    _verify_runtime_identity,
    load_object,
    sha256_file,
)
from bpc_hybrid.estg150_b0_development_v2 import (
    _token_span,
    parse_bridge_output_multi,
)
from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, SCHEMA_VERSION, validate_canonical
from bpc_hybrid.sun_style.corenlp_runtime import (
    CoreNLPContractError,
    resolve_corenlp_runtime,
    validate_annotation,
)
from bpc_hybrid.sun_style.sun_b0 import (
    LockedBertTextCNNInference,
    ModalityPrediction,
    SunB0CompositionError,
    load_s26_config,
)


METHOD_ID = "sun_rule_only"
METHOD_VARIANT = "b0_sun_paper_spec_v1"
BRIDGE_CLASS = "SunPaperPhraseRuleBatchBridge"
BRIDGE_REL = "tools/corenlp/SunPaperPhraseRuleBatchBridge.java"
PAPER_ORDER = (
    "modality",
    "condition",
    "constraint",
    "exception",
    "actor",
    "action",
)
MARKER_FIELDS = ("actor", "condition", "constraint", "exception")
_WORD = re.compile(r"[A-Za-z0-9]+")


def _marker_tokens(surface: str) -> tuple[str, ...]:
    tokens = tuple(token.casefold() for token in _WORD.findall(surface))
    if not tokens:
        raise Estg150B0DevelopmentError(f"marker has no plan-safe tokens: {surface!r}")
    return tokens


def _token_predicate(token: str, relation: str = "<<") -> str:
    escaped = re.escape(token).replace("/", r"\/")
    return f" {relation} /(?i)^{escaped}$/"


def _all_descendants(tokens: Sequence[str]) -> str:
    return "".join(_token_predicate(token) for token in tokens)


def load_marker_parameter(
    project_root: Path,
    marker_specs: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, tuple[str, ...]], dict[str, str]]:
    root = Path(project_root).resolve()
    surfaces: dict[str, tuple[str, ...]] = {}
    hashes: dict[str, str] = {}
    if set(marker_specs) != set(MARKER_FIELDS):
        raise Estg150B0DevelopmentError("paper marker parameter must bind four fields")
    for field in MARKER_FIELDS:
        spec = marker_specs[field]
        path = root / str(spec.get("path", ""))
        expected = spec.get("sha256")
        if not path.is_file() or not isinstance(expected, str) or sha256_file(path) != expected:
            raise Estg150B0DevelopmentError(f"{field} marker parameter is missing or hash-mismatched")
        payload = load_object(path)
        entries = payload.get("entries")
        if not isinstance(entries, list) or not entries:
            raise Estg150B0DevelopmentError(f"{field} marker parameter has no entries")
        values: list[str] = []
        for entry in entries:
            surface = entry.get("surface") if isinstance(entry, Mapping) else None
            if not isinstance(surface, str) or not surface.strip():
                raise Estg150B0DevelopmentError(f"{field} marker entry is invalid")
            values.append(" ".join(surface.casefold().split()))
        surfaces[field] = tuple(dict.fromkeys(values))
        hashes[field] = expected
    return surfaces, hashes


def write_paper_rule_plan(
    registry: Mapping[str, Any],
    markers: Mapping[str, Sequence[str]],
    target: Path,
) -> int:
    """Expand the published rule templates and substituted marker parameter."""

    if tuple(registry.get("extraction_order", ())) != PAPER_ORDER:
        raise Estg150B0DevelopmentError("Sun paper extraction dependency changed")
    fields = registry.get("fields")
    if not isinstance(fields, Mapping):
        raise Estg150B0DevelopmentError("Sun paper rule registry fields missing")
    lines: list[str] = []

    def add(field: str, pattern: str, operation: str | None) -> None:
        if "\t" in pattern or "\n" in pattern:
            raise Estg150B0DevelopmentError("Tregex pattern is not plan-safe")
        lines.append(f"{field}\t{pattern}\t{operation or ''}")

    modality = fields["modality"]
    for pattern in modality["tregex_patterns"]:
        add("modality", pattern, modality["tsurgeon_operation"])

    condition = fields["condition"]
    for surface in markers["condition"]:
        predicates = _all_descendants(_marker_tokens(surface))
        for template in condition["tregex_templates"]:
            add(
                "condition",
                template.replace("{marker_predicates}", predicates),
                condition["tsurgeon_operation"],
            )

    constraint = fields["constraint"]
    for surface in markers["constraint"]:
        tokens = _marker_tokens(surface)
        add(
            "constraint",
            constraint["tregex_templates"][0].replace(
                "{marker_predicates}", _all_descendants(tokens)
            ),
            constraint["tsurgeon_operation"],
        )
        add(
            "constraint",
            constraint["tregex_templates"][1]
            .replace("{first_marker_predicate}", _token_predicate(tokens[0]))
            .replace("{remaining_marker_predicates}", _all_descendants(tokens[1:])),
            constraint["tsurgeon_operation"],
        )

    exception = fields["exception"]
    for surface in markers["exception"]:
        tokens = _marker_tokens(surface)
        predicates = _all_descendants(tokens)
        add(
            "exception",
            exception["tregex_templates"][0].replace("{marker_predicates}", predicates),
            exception["tsurgeon_operation"],
        )
        add(
            "exception",
            exception["tregex_templates"][1].replace("{marker_predicates}", predicates),
            exception["tsurgeon_operation"],
        )
        add(
            "exception",
            exception["tregex_templates"][2]
            .replace("{first_marker_predicate}", _token_predicate(tokens[0]))
            .replace("{remaining_marker_predicates}", _all_descendants(tokens[1:])),
            exception["tsurgeon_operation"],
        )

    actor = fields["actor"]
    for surface in markers["actor"]:
        add(
            "actor",
            actor["candidate_template"].replace(
                "{marker_predicates}", _all_descendants(_marker_tokens(surface))
            ),
            None,
        )

    action = fields["action"]
    for pattern in action["tregex_patterns"]:
        add("action", pattern, None)

    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return len(lines)


def _actor_dependency_supported(
    sentence: Mapping[str, Any], observation: Mapping[str, Any]
) -> bool:
    """Apply the three published dependency/voice gates to an actor NP."""

    begin = observation.get("begin")
    end = observation.get("end")
    tokens = sentence.get("tokens")
    dependencies = sentence.get("basicDependencies")
    if (
        not isinstance(begin, int)
        or not isinstance(end, int)
        or not isinstance(tokens, list)
        or not isinstance(dependencies, list)
    ):
        return False
    passive = any(
        str(dep.get("dep", "")).casefold() in {"auxpass", "aux:pass"}
        or str(dep.get("dep", "")).casefold().startswith("nsubj:pass")
        or str(dep.get("dep", "")).casefold() == "nsubjpass"
        for dep in dependencies
        if isinstance(dep, Mapping)
    )
    in_pp = begin > 0 and str(tokens[begin - 1].get("pos", "")).upper() == "IN"
    for dep in dependencies:
        if not isinstance(dep, Mapping):
            continue
        relation = str(dep.get("dep", "")).casefold()
        dependent = dep.get("dependent")
        if not isinstance(dependent, int) or not (begin <= dependent - 1 < end):
            continue
        if relation.startswith("nsubj"):
            return True
        if passive and in_pp and (
            relation.startswith("obl")
            or relation.startswith("nmod")
            or "obj" in relation
            or relation == "agent"
        ):
            return True
        if not passive and relation in {"obj", "dobj", "iobj"}:
            return True
    return False


def _span_from_observation(
    source_text: str,
    sentence: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    span = _token_span(source_text, sentence, observation)
    return {
        **span,
        "normalized": " ".join(span["text"].casefold().split()),
    }


def _dedupe_spans(spans: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for span in sorted(spans, key=lambda item: (int(item["start"]), int(item["end"]))):
        key = (int(span["start"]), int(span["end"]))
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(span))
    return result


def build_canonical_record_sun_paper(
    *,
    sample_id: str,
    source_id: str,
    source_text: str,
    annotation: Mapping[str, Any],
    phrase_cases: Sequence[Mapping[str, Any]],
    predictions: Sequence[ModalityPrediction],
) -> dict[str, Any]:
    try:
        validate_annotation(annotation, source_text)
    except CoreNLPContractError as exc:
        raise Estg150B0DevelopmentError(str(exc)) from exc
    sentences = annotation["sentences"]
    if len(predictions) != len(sentences):
        raise Estg150B0DevelopmentError("one modality prediction is required per sentence")
    cases = {case["sentence_index"]: case for case in phrase_cases}
    clauses: list[dict[str, Any]] = []
    for sentence_index, (sentence, prediction) in enumerate(
        zip(sentences, predictions, strict=True)
    ):
        tokens = sentence["tokens"]
        clause_start = tokens[0]["characterOffsetBegin"]
        clause_end = tokens[-1]["characterOffsetEnd"]
        clause_span = {
            "text": source_text[clause_start:clause_end],
            "start": clause_start,
            "end": clause_end,
        }
        fields = cases.get(sentence_index, {}).get("fields", {})
        raw_spans: dict[str, list[dict[str, Any]]] = {
            field: [] for field in PAPER_ORDER
        }
        for field in PAPER_ORDER:
            observations = fields.get(field, []) if isinstance(fields, Mapping) else []
            if isinstance(observations, Mapping):
                observations = [observations]
            for observation in observations:
                if not isinstance(observation, Mapping):
                    continue
                if field == "actor" and not _actor_dependency_supported(sentence, observation):
                    continue
                raw_spans[field].append(
                    _span_from_observation(source_text, sentence, observation)
                )
            raw_spans[field] = _dedupe_spans(raw_spans[field])

        clause_id = f"{sample_id}.c{sentence_index + 1}"

        def finalize(field: str, singular: str) -> list[dict[str, Any]]:
            return [
                {"id": f"{clause_id}.{singular}.{rank}", **span}
                for rank, span in enumerate(raw_spans[field], start=1)
            ]

        actors = finalize("actor", "actor")
        actions = finalize("action", "action")
        modality_evidence = [
            {key: value for key, value in span.items() if key != "normalized"}
            for span in raw_spans["modality"]
        ] or [dict(clause_span)]
        clauses.append(
            {
                "clause_id": clause_id,
                "clause_span": clause_span,
                "modality": {"label": prediction.label, "evidence": modality_evidence},
                "actors": actors,
                "actions": actions,
                "conditions": finalize("condition", "condition"),
                "constraints": finalize("constraint", "constraint"),
                "exceptions": finalize("exception", "exception"),
                "actor_action_map": [
                    {
                        "actor_id": actors[0]["id"] if actors else None,
                        "action_id": action["id"],
                    }
                    for action in actions
                ],
                "order_relations": [],
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
            "Sun paper canonical record is invalid: " + "; ".join(report.errors)
        )
    return record


def run_corenlp_batch_sun_paper(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
    registry_rel: str,
    marker_specs: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    root = Path(project_root).resolve()
    runtime_home = Path(runtime_home).resolve()
    runtime_identity = _verify_runtime_identity(root, runtime_home)
    probe = resolve_corenlp_runtime(root, home=runtime_home)
    if not probe.ready or not probe.java_executable:
        raise Estg150B0DevelopmentError(f"CoreNLP runtime unavailable: {probe.reasons}")
    javac = shutil.which("javac")
    if not javac:
        raise Estg150B0DevelopmentError("javac is required for the paper-spec bridge")
    markers, marker_hashes = load_marker_parameter(root, marker_specs)

    input_dir = work_dir / "corenlp-input"
    output_dir = work_dir / "corenlp-output"
    classes_dir = work_dir / "bridge-classes"
    input_dir.mkdir(parents=True)
    output_dir.mkdir()
    classes_dir.mkdir()
    input_paths: list[Path] = []
    source_by_id: dict[str, str] = {}
    for record in source_records:
        sample_id = str(record["sample_id"])
        source_text = str(record["approved_text_en"])
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
    started = time.perf_counter()
    _run(
        [
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
        ],
        cwd=root,
        timeout=max(1800, 12 * len(source_records)),
    )
    corenlp_seconds = time.perf_counter() - started

    annotations: dict[str, dict[str, Any]] = {}
    sentence_refs: list[tuple[str, int]] = []
    tree_lines: list[str] = []
    for record in source_records:
        sample_id = str(record["sample_id"])
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

    registry_path = root / registry_rel
    registry = load_object(registry_path)
    plan_path = work_dir / "paper-rule-plan.tsv"
    pattern_count = write_paper_rule_plan(registry, markers, plan_path)
    bridge_path = root / BRIDGE_REL
    _run(
        [
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
        timeout=900,
    )
    bridge_seconds = time.perf_counter() - bridge_started
    global_cases, bridge_summary = parse_bridge_output_multi(bridge.stdout)
    if bridge_summary["pattern_count"] != pattern_count:
        raise Estg150B0DevelopmentError("paper bridge pattern count mismatch")
    if bridge_summary["tree_count"] != len(sentence_refs) or len(global_cases) != len(sentence_refs):
        raise Estg150B0DevelopmentError("paper bridge sentence coverage mismatch")
    cases_by_id: dict[str, list[dict[str, Any]]] = {
        str(record["sample_id"]): [] for record in source_records
    }
    for global_case, (sample_id, local_index) in zip(
        global_cases, sentence_refs, strict=True
    ):
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
        "patterns_path": registry_rel,
        "patterns_sha256": sha256_file(registry_path),
        "marker_parameter_sha256": marker_hashes,
        "tsurgeon_enabled": True,
        "paper_order": list(PAPER_ORDER),
    }


def run_b0_batch_sun_paper(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
    s26_config_rel: str,
    registry_rel: str,
    marker_specs: Mapping[str, Mapping[str, Any]],
    device: str = "cpu",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = Path(project_root).resolve()
    s26_config = load_s26_config(root / s26_config_rel)
    annotations, cases_by_id, runtime = run_corenlp_batch_sun_paper(
        root,
        source_records,
        runtime_home=runtime_home,
        work_dir=work_dir,
        registry_rel=registry_rel,
        marker_specs=marker_specs,
    )
    classifier_started = time.perf_counter()
    try:
        classifier = LockedBertTextCNNInference.load(root, s26_config, device=device)
        record_predictions = _predict_in_batches(
            classifier, [str(record["raw_text_de"]) for record in source_records]
        )
    except SunB0CompositionError as exc:
        raise Estg150B0DevelopmentError(str(exc)) from exc
    classifier_seconds = time.perf_counter() - classifier_started

    compose_started = time.perf_counter()
    canonical_records: list[dict[str, Any]] = []
    label_counts: dict[str, int] = {}
    confidence_sum = 0.0
    for record, record_prediction in zip(source_records, record_predictions, strict=True):
        sample_id = str(record["sample_id"])
        annotation = annotations[sample_id]
        predictions = [record_prediction] * len(annotation["sentences"])
        canonical = build_canonical_record_sun_paper(
            sample_id=sample_id,
            source_id=f"estg_legacy_{record['legacy_record_id']}",
            source_text=str(record["approved_text_en"]),
            annotation=annotation,
            phrase_cases=cases_by_id[sample_id],
            predictions=predictions,
        )
        canonical_records.append(canonical)
        label_counts[record_prediction.label] = label_counts.get(record_prediction.label, 0) + 1
        confidence_sum += record_prediction.confidence
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
    runtime.update(
        {
            "classifier_seconds": classifier_seconds,
            "compose_seconds": compose_seconds,
            "total_seconds": total_seconds,
            "device": device,
            "record_count": len(canonical_records),
            "predicted_clause_count": sum(len(record["clauses"]) for record in canonical_records),
            "classifier_label_counts_by_record": dict(sorted(label_counts.items())),
            "classifier_mean_confidence": confidence_sum / max(len(record_predictions), 1),
            "method_id": METHOD_ID,
            "method_variant": METHOD_VARIANT,
            "paper_faithful_reconstruction": True,
            "exact_original_reproduction": False,
            "custom_v10_modules_used": [],
        }
    )
    return attempts, runtime
