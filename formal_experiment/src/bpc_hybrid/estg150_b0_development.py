"""Development-only EStG-150 B0 batch and Gold adapter.

The module binds the frozen Layer E bytes to the locked S2.4/S2.5/S2.6
components, runs only local inference, and prepares S2.10-compatible attempts.
It deliberately does not publish formal Gold or write formal artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, SCHEMA_VERSION, validate_canonical
from bpc_hybrid.sun_style.corenlp_runtime import (
    EXTRACTION_ORDER,
    CoreNLPContractError,
    resolve_corenlp_runtime,
    validate_annotation,
)
from bpc_hybrid.sun_style.sun_b0 import (
    LockedBertTextCNNInference,
    ModalityPrediction,
    SunB0CompositionError,
    build_canonical_record,
    load_s26_config,
)
from formal_experiment.estg150_validator import validate_doc_dict


class Estg150B0DevelopmentError(ValueError):
    """Raised when the development batch cannot preserve its locked route."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Estg150B0DevelopmentError(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise Estg150B0DevelopmentError(f"JSON root must be an object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            for line_number, raw in enumerate(stream, 1):
                if not raw.strip():
                    continue
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise Estg150B0DevelopmentError(
                        f"JSONL line {line_number} is not an object: {path}"
                    )
                rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Estg150B0DevelopmentError(f"invalid JSONL: {path}") from exc
    return rows


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _plain_span(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "text": value["text"],
        "start": value["start"],
        "end": value["end"],
    }


def _supported_span(value: Mapping[str, Any]) -> dict[str, Any]:
    text = value["text"]
    return {
        "id": value["id"],
        "text": text,
        "start": value["start"],
        "end": value["end"],
        "normalized": _normalized(text),
    }


def canonical_gold_record(record: Mapping[str, Any]) -> dict[str, Any]:
    sample_id = record.get("sample_id")
    source_text = record.get("approved_text_en")
    legacy_record_id = record.get("legacy_record_id")
    if not isinstance(sample_id, str) or not isinstance(source_text, str) or not source_text:
        raise Estg150B0DevelopmentError("Layer E record lacks sample_id or approved_text_en")
    if not isinstance(legacy_record_id, int) or isinstance(legacy_record_id, bool):
        raise Estg150B0DevelopmentError(f"invalid legacy_record_id: {sample_id}")

    clauses: list[dict[str, Any]] = []
    human = record.get("human_correction") or {}
    for clause in human.get("clauses") or []:
        clause_span = _plain_span(clause["clause_span"])
        modality = clause["modality"]
        evidence_value = modality.get("span")
        evidence = (
            [_plain_span(evidence_value)]
            if isinstance(evidence_value, Mapping)
            else [dict(clause_span)]
        )
        mapped = {
            plural: [_supported_span(item) for item in clause.get(plural, [])]
            for plural in ("actors", "actions", "conditions", "constraints", "exceptions")
        }
        clauses.append(
            {
                "clause_id": clause["clause_id"],
                "clause_span": clause_span,
                "modality": {"label": modality["value"], "evidence": evidence},
                **mapped,
                "actor_action_map": [dict(item) for item in clause.get("actor_action_map", [])],
                "order_relations": [
                    {
                        "before_action_id": item["before_action_id"],
                        "after_action_id": item["after_action_id"],
                        "evidence": [_plain_span(span) for span in item["evidence"]],
                    }
                    for item in clause.get("order_relations", [])
                ],
            }
        )
    result = {
        "schema_version": SCHEMA_VERSION,
        "sample_id": sample_id,
        "source_id": f"estg_legacy_{legacy_record_id}",
        "source_text": source_text,
        "clauses": clauses,
        "method": {"name": "sun_rule_only", "schema_source": SCHEMA_SOURCE},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
    }
    report = validate_canonical(result)
    if not report.schema_valid or not report.cross_field_valid:
        raise Estg150B0DevelopmentError(
            f"canonical Gold adapter failed for {sample_id}: {'; '.join(report.errors)}"
        )
    return result


def build_canonical_gold_records(
    layer_e_path: Path,
    membership_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    layer_e = load_object(layer_e_path)
    validation = validate_doc_dict(layer_e, Path(membership_path))
    if not validation.get("freeze_ready"):
        raise Estg150B0DevelopmentError(
            f"Layer E is not freeze-ready: {validation.get('freeze_blockers', [])[:8]}"
        )
    source_records = layer_e.get("records") or []
    gold_records = [canonical_gold_record(record) for record in source_records]
    if len(gold_records) != 150 or len({row["sample_id"] for row in gold_records}) != 150:
        raise Estg150B0DevelopmentError("canonical Gold adapter must produce 150 unique records")
    return gold_records, source_records


def _run(command: Sequence[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stdout + "\n" + completed.stderr)[-5000:]
        raise Estg150B0DevelopmentError(
            f"offline command failed ({completed.returncode}): {command[0]}\n{detail}"
        )
    return completed


def _write_rule_plan(registry: Mapping[str, Any], target: Path) -> int:
    if tuple(registry.get("extraction_order", ())) != EXTRACTION_ORDER:
        raise Estg150B0DevelopmentError("CoreNLP extraction order changed")
    fields = registry.get("fields")
    if not isinstance(fields, list):
        raise Estg150B0DevelopmentError("CoreNLP rule registry fields missing")
    lines: list[str] = []
    for item in fields:
        operations = item.get("tsurgeon_operations")
        patterns = item.get("tregex_patterns")
        if not isinstance(operations, list) or len(operations) > 1:
            raise Estg150B0DevelopmentError("invalid Tsurgeon operation count")
        if not isinstance(patterns, list) or not patterns:
            raise Estg150B0DevelopmentError("Tregex pattern list missing")
        operation = operations[0] if operations else ""
        for pattern in patterns:
            if not isinstance(pattern, str) or "\t" in pattern or "\n" in pattern:
                raise Estg150B0DevelopmentError("Tregex pattern is not plan-safe")
            lines.append(f"{item['field']}\t{pattern}\t{operation}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return len(lines)


def _parse_bridge_output(output: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    cases: dict[int, dict[str, Any]] = {}
    summary: dict[str, int] | None = None
    for raw in output.splitlines():
        parts = raw.split("\t")
        if parts[0] == "MATCH" and len(parts) == 8:
            index = int(parts[1])
            fields = cases.setdefault(index, {field: None for field in EXTRACTION_ORDER})
            fields[parts[2]] = {
                "begin": int(parts[3]),
                "end": int(parts[4]),
                "text": parts[5],
                "pattern_index": int(parts[6]),
                "operation_applied": parts[7] == "true",
            }
        elif parts[0] == "MISS" and len(parts) == 3:
            index = int(parts[1])
            cases.setdefault(index, {field: None for field in EXTRACTION_ORDER})
        elif parts[0] == "TERMINAL_TREE_REMOVALS" and len(parts) == 2:
            if summary is None:
                summary = {}
            summary["terminal_tree_removal_count"] = int(parts[1])
        elif parts[0] == "SUMMARY" and len(parts) == 5:
            terminal_count = 0 if summary is None else summary.get(
                "terminal_tree_removal_count", 0
            )
            summary = {
                "tree_count": int(parts[1]),
                "pattern_count": int(parts[2]),
                "match_count": int(parts[3]),
                "surgery_count": int(parts[4]),
                "terminal_tree_removal_count": terminal_count,
            }
    if summary is None:
        raise Estg150B0DevelopmentError("Java bridge did not emit SUMMARY")
    ordered = [
        {"sentence_index": index, "fields": cases[index]}
        for index in sorted(cases)
    ]
    return ordered, summary


def _verify_runtime_identity(project_root: Path, runtime_home: Path) -> dict[str, Any]:
    config = load_object(project_root / "configs/sun_corenlp_runtime.json")
    identity = config["external_runtime_identity"]
    result: dict[str, Any] = {}
    for key in ("code_jar", "models_jar"):
        expected = identity[key]
        path = runtime_home / expected["name"]
        if not path.is_file():
            raise Estg150B0DevelopmentError(f"missing CoreNLP runtime JAR: {path}")
        actual = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        if actual != {"bytes": expected["bytes"], "sha256": expected["sha256"]}:
            raise Estg150B0DevelopmentError(f"CoreNLP runtime identity mismatch: {path.name}")
        result[key] = {"name": path.name, **actual}
    return result


def run_corenlp_batch(
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
        raise Estg150B0DevelopmentError("javac is required for the locked bridge")

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

    registry = load_object(root / "resources/corenlp/sun_phrase_patterns_v1.json")
    plan_path = work_dir / "rule-plan.tsv"
    pattern_count = _write_rule_plan(registry, plan_path)
    bridge_path = root / "tools/corenlp/SunPhraseRuleBatchBridge.java"
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
            "SunPhraseRuleBatchBridge",
            str(plan_path),
            str(tree_path),
        ],
        cwd=root,
        timeout=600,
    )
    bridge_seconds = time.perf_counter() - bridge_started
    global_cases, bridge_summary = _parse_bridge_output(bridge.stdout)
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
    }


def _predict_in_batches(
    classifier: LockedBertTextCNNInference,
    texts: Sequence[str],
    *,
    batch_size: int = 16,
) -> list[ModalityPrediction]:
    predictions: list[ModalityPrediction] = []
    for start in range(0, len(texts), batch_size):
        predictions.extend(classifier.predict(texts[start : start + batch_size]))
    return predictions


def run_b0_batch(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
    device: str = "cpu",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = Path(project_root).resolve()
    s26_config = load_s26_config(root / "configs/models/sun_b0_s26.json")
    annotations, cases_by_id, runtime = run_corenlp_batch(
        root, source_records, runtime_home=runtime_home, work_dir=work_dir
    )
    classifier_started = time.perf_counter()
    try:
        classifier = LockedBertTextCNNInference.load(root, s26_config, device=device)
        record_predictions = _predict_in_batches(
            classifier, [record["raw_text_de"] for record in source_records]
        )
    except SunB0CompositionError as exc:
        raise Estg150B0DevelopmentError(str(exc)) from exc
    classifier_seconds = time.perf_counter() - classifier_started

    compose_started = time.perf_counter()
    canonical_records: list[dict[str, Any]] = []
    label_counts: dict[str, int] = {}
    confidence_sum = 0.0
    for record, record_prediction in zip(source_records, record_predictions, strict=True):
        sample_id = record["sample_id"]
        annotation = annotations[sample_id]
        sentence_count = len(annotation["sentences"])
        predictions = [record_prediction] * sentence_count
        canonical = build_canonical_record(
            sample_id=sample_id,
            source_id=f"estg_legacy_{record['legacy_record_id']}",
            source_text=record["approved_text_en"],
            annotation=annotation,
            phrase_cases=cases_by_id[sample_id],
            predictions=predictions,
        )
        canonical_records.append(canonical)
        label_counts[record_prediction.label] = label_counts.get(record_prediction.label, 0) + 1
        confidence_sum += record_prediction.confidence
    compose_seconds = time.perf_counter() - compose_started
    total_seconds = (
        runtime["corenlp_seconds"]
        + runtime["bridge_seconds"]
        + classifier_seconds
        + compose_seconds
    )
    per_record_latency_ms = 1000.0 * total_seconds / len(canonical_records)
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
            "classifier_label_counts_by_record": dict(sorted(label_counts.items())),
            "classifier_mean_confidence": confidence_sum / len(record_predictions),
        }
    )
    return attempts, runtime


def summarize_evaluation(report: Mapping[str, Any]) -> dict[str, Any]:
    modality = report["primary_metrics"]["modality"]
    confusion = modality["confusion_matrix"]
    correct = sum(confusion[label][label] for label in modality["labels"])
    total = sum(
        sum(confusion[gold].values()) + modality["missing_prediction_by_gold_class"][gold]
        for gold in modality["labels"]
    )
    fields = report["primary_metrics"]["fields"]
    return {
        "sample_count": report["membership"]["sample_count"],
        "modality_clause_accuracy": correct / total if total else 0.0,
        "modality_macro_f1": modality["macro_f1"],
        "modality_per_class": modality["per_class"],
        "field_strict_exact": {
            field: {
                key: values["strict_exact"][key]
                for key in ("precision", "recall", "f1")
            }
            for field, values in fields.items()
        },
        "field_token_overlap_micro": {
            field: {
                key: values["token_overlap_micro"][key]
                for key in ("precision", "recall", "f1")
            }
            for field, values in fields.items()
        },
        "clause_segmentation": report["structural_encoding"]["clause_segmentation"],
        "semantic_coverage": report["semantic_coverage"],
    }
