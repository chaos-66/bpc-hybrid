"""Offline S2.5-A contract for a future Stanford CoreNLP runtime.

This module validates versioned JSON fixtures, discovers an explicitly supplied
local CoreNLP installation, and builds a deterministic command line.  It never
downloads software, starts Java, extracts production records, trains a model,
evaluates predictions, reads Gold, or calls an LLM/API.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


CONFIG_REL = "configs/sun_corenlp_runtime.json"
FIXTURE_REL = "tests/fixtures/corenlp/obligation_condition_constraint.json"
EXTRACTION_ORDER = (
    "modality",
    "condition",
    "constraint",
    "exception",
    "action",
    "actor",
)


class CoreNLPContractError(ValueError):
    """Raised when the S2.5-A runtime or fixture contract is invalid."""


@dataclass(frozen=True)
class CoreNLPRuntimeProbe:
    """Read-only discovery result for an external local CoreNLP runtime."""

    ready: bool
    home: str | None
    java_executable: str | None
    classpath_entries: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "home": self.home,
            "java_executable": self.java_executable,
            "classpath_entries": list(self.classpath_entries),
            "reasons": list(self.reasons),
        }


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CoreNLPContractError(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise CoreNLPContractError(f"JSON root must be an object: {path}")
    return value


def load_runtime_contract(project_root: Path | None = None) -> dict[str, Any]:
    """Load and validate the fixed CoreNLP 4.5.10 S2.5-A contract."""

    root = (
        Path(project_root).resolve()
        if project_root is not None
        else Path(__file__).resolve().parents[3]
    )
    contract = _load_object(root / CONFIG_REL)
    if contract.get("schema_version") != "sun_corenlp_runtime_contract@1.0.0":
        raise CoreNLPContractError("unexpected runtime schema_version")
    if contract.get("task_id") != "S2.5-A":
        raise CoreNLPContractError("runtime task_id must remain S2.5-A")
    runtime = contract.get("runtime")
    if not isinstance(runtime, Mapping):
        raise CoreNLPContractError("runtime section must be an object")
    if runtime.get("corenlp_version") != "4.5.10":
        raise CoreNLPContractError("CoreNLP version must remain pinned to 4.5.10")
    if runtime.get("minimum_java_major") != 8:
        raise CoreNLPContractError("minimum Java major must remain 8")
    if tuple(runtime.get("annotators", ())) != (
        "tokenize",
        "ssplit",
        "pos",
        "lemma",
        "parse",
        "depparse",
    ):
        raise CoreNLPContractError("annotator order changed")
    if runtime.get("output_format") != "json":
        raise CoreNLPContractError("CoreNLP output format must remain json")
    boundaries = contract.get("project_boundaries")
    if not isinstance(boundaries, Mapping):
        raise CoreNLPContractError("project_boundaries must be an object")
    locked_false = (
        "formal_use_allowed",
        "training_run",
        "evaluation_run",
        "gold_modified",
        "llm_api_called",
        "network_called_by_implementation",
    )
    if any(boundaries.get(key) is not False for key in locked_false):
        raise CoreNLPContractError("S2.5-A safety boundary was relaxed")
    if boundaries.get("sun_modality_dataset_license_dependency") != (
        "rights_unknown_local_research_use_ready_no_redistribution"
    ):
        raise CoreNLPContractError("Sun modality local-use boundary changed")
    if boundaries.get("s2_4_status") != (
        "verified_training_dev_selection_single_test_evaluation"
    ):
        raise CoreNLPContractError("S2.4 verified status changed")
    if (
        contract.get("status") != "external_runtime_and_live_smoke_verified"
        or boundaries.get("activation_authorized") is not True
        or boundaries.get("s2_5_overall_verified") is not True
        or boundaries.get("s2_6_component_composition_authorized") is not True
    ):
        raise CoreNLPContractError("S2.5-B runtime/live activation is not verified")
    distribution = contract.get("official_distribution")
    if not isinstance(distribution, Mapping) or (
        distribution.get("acquisition_status") != "verified_external_archive"
        or distribution.get("archive_bytes") != 508444875
        or distribution.get("archive_sha256")
        != "76a04089069dad21176c02881f46e07c19ca148b71c8581de2b5b2e2855e042e"
        or distribution.get("archive_entry_count") != 63
        or distribution.get("unsafe_archive_entry_count") != 0
        or distribution.get("vendored_in_formal_experiment") is not False
        or distribution.get("network_download_performed") is not True
    ):
        raise CoreNLPContractError("external runtime acquisition boundary changed")
    return contract


def validate_annotation(annotation: Mapping[str, Any], source_text: str) -> dict[str, int]:
    """Validate the CoreNLP-shaped JSON fields and character offsets."""

    sentences = annotation.get("sentences")
    if not isinstance(sentences, list) or not sentences:
        raise CoreNLPContractError("annotation.sentences must be non-empty")
    token_count = 0
    dependency_count = 0
    previous_end = 0
    for sentence_index, sentence in enumerate(sentences):
        if not isinstance(sentence, Mapping):
            raise CoreNLPContractError("sentence must be an object")
        if sentence.get("index") != sentence_index:
            raise CoreNLPContractError("sentence indexes must be zero-based and contiguous")
        parse = sentence.get("parse")
        normalized_parse = " ".join(parse.split()) if isinstance(parse, str) else ""
        if not normalized_parse.startswith("(ROOT "):
            raise CoreNLPContractError("sentence must include a ROOT constituency parse")
        tokens = sentence.get("tokens")
        if not isinstance(tokens, list) or not tokens:
            raise CoreNLPContractError("sentence tokens must be non-empty")
        for expected_index, token in enumerate(tokens, 1):
            if not isinstance(token, Mapping) or token.get("index") != expected_index:
                raise CoreNLPContractError("token indexes must be one-based and contiguous")
            begin = token.get("characterOffsetBegin")
            end = token.get("characterOffsetEnd")
            original = token.get("originalText")
            if (
                not isinstance(begin, int)
                or isinstance(begin, bool)
                or not isinstance(end, int)
                or isinstance(end, bool)
                or begin < previous_end
                or end <= begin
                or end > len(source_text)
            ):
                raise CoreNLPContractError("token character offsets are invalid or unordered")
            if source_text[begin:end] != original:
                raise CoreNLPContractError("token originalText disagrees with source offsets")
            if not token.get("word") or not token.get("lemma") or not token.get("pos"):
                raise CoreNLPContractError("token word/lemma/pos fields are required")
            previous_end = end
            token_count += 1
        dependencies = sentence.get("basicDependencies")
        if not isinstance(dependencies, list) or not dependencies:
            raise CoreNLPContractError("basicDependencies must be non-empty")
        for dependency in dependencies:
            if not isinstance(dependency, Mapping) or not dependency.get("dep"):
                raise CoreNLPContractError("dependency must contain a relation")
            governor = dependency.get("governor")
            dependent = dependency.get("dependent")
            if (
                not isinstance(governor, int)
                or isinstance(governor, bool)
                or not isinstance(dependent, int)
                or isinstance(dependent, bool)
                or governor < 0
                or dependent < 1
                or dependent > len(tokens)
            ):
                raise CoreNLPContractError("dependency token indexes are invalid")
            dependency_count += 1
    return {
        "sentences": len(sentences),
        "tokens": token_count,
        "dependencies": dependency_count,
    }


def validate_fixture_document(fixture: Mapping[str, Any]) -> dict[str, int]:
    """Validate a synthetic contract fixture without scoring extraction quality."""

    if fixture.get("schema_version") != "sun_corenlp_fixture@1.0.0":
        raise CoreNLPContractError("unexpected fixture schema_version")
    if fixture.get("boundary") != "synthetic_contract_fixture_not_gold_not_evaluation":
        raise CoreNLPContractError("fixture boundary must forbid Gold/evaluation claims")
    source_text = fixture.get("source_text")
    annotation = fixture.get("annotation")
    if not isinstance(source_text, str) or not isinstance(annotation, Mapping):
        raise CoreNLPContractError("fixture source_text/annotation is invalid")
    summary = validate_annotation(annotation, source_text)
    if tuple(fixture.get("extraction_order", ())) != EXTRACTION_ORDER:
        raise CoreNLPContractError("fixture extraction order changed")
    spans = fixture.get("expected_spans")
    if not isinstance(spans, Mapping) or set(spans) != set(EXTRACTION_ORDER):
        raise CoreNLPContractError("fixture must declare exactly six semantic fields")
    for field in EXTRACTION_ORDER:
        span = spans[field]
        if span is None:
            continue
        if not isinstance(span, Mapping):
            raise CoreNLPContractError(f"{field} span must be an object or null")
        begin = span.get("begin")
        end = span.get("end")
        text = span.get("text")
        if (
            not isinstance(begin, int)
            or isinstance(begin, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or not isinstance(text, str)
            or source_text[begin:end] != text
        ):
            raise CoreNLPContractError(f"{field} span disagrees with source offsets")
    return summary


def _resolve_java(java_executable: str | None) -> str | None:
    if java_executable:
        candidate = Path(java_executable)
        if candidate.is_file():
            return str(candidate.resolve())
        return shutil.which(java_executable)
    return shutil.which("java")


def resolve_corenlp_runtime(
    project_root: Path,
    *,
    home: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
    java_executable: str | None = None,
) -> CoreNLPRuntimeProbe:
    """Probe an external local runtime without starting Java or writing files."""

    contract = load_runtime_contract(project_root)
    runtime = contract["runtime"]
    environment = os.environ if environ is None else environ
    configured_home = home or environment.get(runtime["home_environment_variable"])
    reasons: list[str] = []
    resolved_java = _resolve_java(java_executable)
    if not resolved_java:
        reasons.append("java_executable_missing")
    if not configured_home:
        reasons.append("corenlp_home_not_configured")
        return CoreNLPRuntimeProbe(
            ready=False,
            home=None,
            java_executable=resolved_java,
            classpath_entries=(),
            reasons=tuple(reasons),
        )
    home_path = Path(configured_home).expanduser().resolve()
    if not home_path.is_dir():
        reasons.append("corenlp_home_not_directory")
    required = tuple(runtime["required_jars"])
    for jar_name in required:
        if not (home_path / jar_name).is_file():
            reasons.append(f"required_jar_missing:{jar_name}")
    classpath = tuple(str(path.resolve()) for path in sorted(home_path.rglob("*.jar")))
    if not classpath:
        reasons.append("corenlp_classpath_empty")
    return CoreNLPRuntimeProbe(
        ready=not reasons,
        home=str(home_path),
        java_executable=resolved_java,
        classpath_entries=classpath,
        reasons=tuple(reasons),
    )


def build_stanford_corenlp_command(
    project_root: Path,
    probe: CoreNLPRuntimeProbe,
    *,
    input_path: Path,
    output_directory: Path,
) -> list[str]:
    """Build, but do not run, the pinned offline CoreNLP JSON command."""

    if not probe.ready or not probe.java_executable or not probe.classpath_entries:
        raise CoreNLPContractError("CoreNLP runtime probe is not ready")
    contract = load_runtime_contract(project_root)
    runtime = contract["runtime"]
    annotators = ",".join(runtime["annotators"])
    return [
        probe.java_executable,
        f"-Xmx{runtime['heap_megabytes']}m",
        "-cp",
        os.pathsep.join(probe.classpath_entries),
        "edu.stanford.nlp.pipeline.StanfordCoreNLP",
        "-annotators",
        annotators,
        "-outputFormat",
        runtime["output_format"],
        "-file",
        str(input_path.resolve()),
        "-outputDirectory",
        str(output_directory.resolve()),
        "-replaceExtension",
    ]
