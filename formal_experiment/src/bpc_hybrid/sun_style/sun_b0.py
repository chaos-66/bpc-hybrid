"""S2.6 composition for the non-LLM Sun Stage 2 baseline.

This module joins the verified S2.4 Legal-BERT + TextCNN classifier with
the attested S2.5 CoreNLP/Tregex/Tsurgeon observations and emits the shared
canonical Stage 2 record.  The locked S2.6 smoke uses only a synthetic phrase
fixture; it does not read Gold, repeat the S2.4 test evaluation, call a network,
or call an LLM/API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, SCHEMA_VERSION, validate_canonical
from bpc_hybrid.sun_style.bert_textcnn import (
    LABELS,
    BertTextCNN,
    BertTextCNNError,
    load_training_config,
    sha256_file,
)
from bpc_hybrid.sun_style.corenlp_runtime import (
    CoreNLPContractError,
    validate_annotation,
)


S26_CONFIG_SCHEMA = "sun_b0_s26@1.0.0"
S24_MANIFEST_SCHEMA = "sun_bert_textcnn_run_manifest@1.0.0"
S24_CHECKPOINT_SCHEMA = "sun_bert_textcnn_checkpoint@1.0.0"


class SunB0CompositionError(ValueError):
    """Raised when an S2.6 component or cross-component mapping drifts."""


@dataclass(frozen=True)
class ModalityPrediction:
    label: str
    confidence: float

    def __post_init__(self) -> None:
        if self.label not in LABELS:
            raise SunB0CompositionError(f"unknown modality label: {self.label!r}")
        if not 0.0 <= self.confidence <= 1.0:
            raise SunB0CompositionError("modality confidence must be in [0, 1]")


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SunB0CompositionError(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise SunB0CompositionError(f"JSON root must be an object: {path}")
    return value


def load_s26_config(path: Path) -> dict[str, Any]:
    config = _load_object(path)
    if config.get("schema_version") != S26_CONFIG_SCHEMA:
        raise SunB0CompositionError("unexpected S2.6 config schema_version")
    if config.get("task_id") != "S2.6" or config.get("method_id") != "sun_rule_only":
        raise SunB0CompositionError("S2.6 task or method identity changed")
    extractor = config.get("phrase_extractor")
    output = config.get("canonical_output")
    safety = config.get("safety")
    if not all(isinstance(section, Mapping) for section in (extractor, output, safety)):
        raise SunB0CompositionError("S2.6 config sections are missing")
    if tuple(extractor.get("extraction_order", ())) != (
        "modality",
        "condition",
        "constraint",
        "exception",
        "action",
        "actor",
    ):
        raise SunB0CompositionError("S2.6 extraction order changed")
    if (
        output.get("schema", {}).get("schema_version") != SCHEMA_VERSION
        or output.get("modality_label_source") != "s2_4_classifier"
        or output.get("one_clause_per_corenlp_sentence") is not True
    ):
        raise SunB0CompositionError("S2.6 canonical mapping changed")
    classifier_inputs = config.get("verification", {}).get("classifier_input_texts_de")
    if (
        config.get("classifier", {}).get("inference_language") != "de"
        or extractor.get("inference_language") != "en"
        or not isinstance(classifier_inputs, list)
        or not classifier_inputs
        or any(not isinstance(text, str) or not text.strip() for text in classifier_inputs)
        or config.get("verification", {}).get(
            "classifier_and_phrase_inputs_are_language_aligned_parallel_synthetic_texts"
        )
        is not True
    ):
        raise SunB0CompositionError("S2.6 bilingual input routing changed")
    locked_false = (
        "gold_read_or_modified",
        "llm_api_called",
        "network_allowed",
        "test_split_read_or_evaluated",
        "row_level_real_data_predictions_persisted",
    )
    if any(safety.get(key) is not False for key in locked_false):
        raise SunB0CompositionError("S2.6 safety boundary was relaxed")
    if safety.get("no_overwrite") is not True:
        raise SunB0CompositionError("S2.6 no-overwrite boundary is required")
    return config


class LockedBertTextCNNInference:
    """Offline inference-only loader for the exact S2.4 checkpoint."""

    def __init__(self, model: BertTextCNN, tokenizer: Any, *, max_length: int, device: torch.device) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.device = device

    @classmethod
    def load(
        cls,
        project_root: Path,
        s26_config: Mapping[str, Any],
        *,
        device: str = "cpu",
    ) -> "LockedBertTextCNNInference":
        root = Path(project_root).resolve()
        if device == "cuda" and not torch.cuda.is_available():
            raise SunB0CompositionError("CUDA was requested but is unavailable")
        torch_device = torch.device(device)
        classifier = s26_config["classifier"]
        config_spec = classifier["config"]
        manifest_spec = classifier["run_manifest"]
        checkpoint_spec = classifier["checkpoint"]
        config_path = root / config_spec["path"]
        manifest_path = root / manifest_spec["path"]
        checkpoint_path = root / checkpoint_spec["path"]
        for path, spec, label in (
            (config_path, config_spec, "S2.4 config"),
            (manifest_path, manifest_spec, "S2.4 run manifest"),
            (checkpoint_path, checkpoint_spec, "S2.4 checkpoint"),
        ):
            if not path.is_file() or sha256_file(path) != spec["sha256"]:
                raise SunB0CompositionError(f"{label} is missing or hash-mismatched")
        if checkpoint_path.stat().st_size != checkpoint_spec["bytes"]:
            raise SunB0CompositionError("S2.4 checkpoint byte size changed")

        training_config = load_training_config(config_path)
        run_manifest = _load_object(manifest_path)
        if (
            run_manifest.get("schema_version") != S24_MANIFEST_SCHEMA
            or run_manifest.get("status") != "succeeded"
            or run_manifest.get("config", {}).get("sha256") != config_spec["sha256"]
            or run_manifest.get("checkpoint", {}).get("sha256") != checkpoint_spec["sha256"]
            or run_manifest.get("test", {}).get("evaluation_count") != 1
        ):
            raise SunB0CompositionError("S2.4 run manifest is not the locked successful run")

        try:
            from huggingface_hub import snapshot_download
            from transformers import AutoModel, AutoTokenizer

            pretrained = training_config["pretrained_model"]
            snapshot = Path(
                snapshot_download(
                    repo_id=pretrained["repository_id"],
                    revision=pretrained["revision"],
                    local_files_only=True,
                )
            )
            for name, expected in pretrained["required_files"].items():
                if sha256_file(snapshot / name) != expected:
                    raise SunB0CompositionError(f"cached Legal-BERT hash mismatch: {name}")
            tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
            encoder = AutoModel.from_pretrained(snapshot, local_files_only=True)
        except SunB0CompositionError:
            raise
        except Exception as exc:
            raise SunB0CompositionError("locked Legal-BERT cache is unavailable") from exc

        architecture = training_config["architecture"]
        model = BertTextCNN(
            encoder,
            kernel_sizes=architecture["kernel_sizes"],
            filters_per_kernel=architecture["filters_per_kernel"],
            dropout=architecture["dropout"],
            num_labels=architecture["num_labels"],
        ).to(torch_device)
        try:
            checkpoint = torch.load(checkpoint_path, map_location=torch_device, weights_only=True)
        except Exception as exc:
            raise SunB0CompositionError("locked S2.4 checkpoint cannot be loaded safely") from exc
        if (
            checkpoint.get("schema_version") != S24_CHECKPOINT_SCHEMA
            or checkpoint.get("config_sha256") != config_spec["sha256"]
            or tuple(checkpoint.get("labels", ())) != LABELS
        ):
            raise SunB0CompositionError("S2.4 checkpoint metadata changed")
        try:
            model.load_state_dict(checkpoint["model_state_dict"], strict=True)
        except (KeyError, RuntimeError) as exc:
            raise SunB0CompositionError("S2.4 checkpoint state is incompatible") from exc
        model.eval()
        return cls(
            model,
            tokenizer,
            max_length=training_config["tokenization"]["max_length"],
            device=torch_device,
        )

    @torch.no_grad()
    def predict(self, texts: Sequence[str]) -> list[ModalityPrediction]:
        if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise SunB0CompositionError("modality inference requires non-empty texts")
        encoded = self.tokenizer(
            list(texts),
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        logits = self.model(
            input_ids=encoded["input_ids"].to(self.device),
            attention_mask=encoded["attention_mask"].to(self.device),
        )
        probabilities = torch.softmax(logits, dim=1).cpu()
        result: list[ModalityPrediction] = []
        for row in probabilities:
            index = int(row.argmax().item())
            result.append(ModalityPrediction(LABELS[index], float(row[index].item())))
        return result


def _plain_span(source_text: str, start: int, end: int) -> dict[str, Any]:
    if start < 0 or end <= start or end > len(source_text):
        raise SunB0CompositionError(f"invalid character span [{start}:{end}]")
    return {"text": source_text[start:end], "start": start, "end": end}


def _token_span(
    source_text: str,
    sentence: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    tokens = sentence.get("tokens")
    begin = observation.get("begin")
    end = observation.get("end")
    if (
        not isinstance(tokens, list)
        or not isinstance(begin, int)
        or isinstance(begin, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
        or begin < 0
        or end <= begin
        or end > len(tokens)
    ):
        raise SunB0CompositionError("phrase observation token span is invalid")
    start_offset = tokens[begin]["characterOffsetBegin"]
    end_offset = tokens[end - 1]["characterOffsetEnd"]
    return _plain_span(source_text, start_offset, end_offset)


def _supported_span(
    source_text: str,
    sentence: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    span_id: str,
) -> dict[str, Any]:
    span = _token_span(source_text, sentence, observation)
    normalized = " ".join(span["text"].casefold().split())
    return {"id": span_id, **span, "normalized": normalized}


def build_canonical_record(
    *,
    sample_id: str,
    source_id: str,
    source_text: str,
    annotation: Mapping[str, Any],
    phrase_cases: Sequence[Mapping[str, Any]],
    predictions: Sequence[ModalityPrediction],
) -> dict[str, Any]:
    """Compose classifier labels and S2.5 token spans into one canonical record."""

    try:
        validate_annotation(annotation, source_text)
    except CoreNLPContractError as exc:
        raise SunB0CompositionError(str(exc)) from exc
    sentences = annotation["sentences"]
    if len(predictions) != len(sentences):
        raise SunB0CompositionError("one modality prediction is required per sentence")
    cases: dict[int, Mapping[str, Any]] = {}
    for case in phrase_cases:
        index = case.get("sentence_index")
        if not isinstance(index, int) or isinstance(index, bool) or index in cases:
            raise SunB0CompositionError("phrase case indexes must be unique integers")
        cases[index] = case

    clauses: list[dict[str, Any]] = []
    for index, (sentence, prediction) in enumerate(zip(sentences, predictions, strict=True)):
        tokens = sentence["tokens"]
        clause_span = _plain_span(
            source_text,
            tokens[0]["characterOffsetBegin"],
            tokens[-1]["characterOffsetEnd"],
        )
        fields = cases.get(index, {}).get("fields", {})
        if not isinstance(fields, Mapping):
            raise SunB0CompositionError("phrase case fields must be an object")
        modality_observation = fields.get("modality")
        modality_evidence = (
            _token_span(source_text, sentence, modality_observation)
            if isinstance(modality_observation, Mapping)
            else dict(clause_span)
        )
        clause_id = f"{sample_id}.c{index + 1}"

        mapped: dict[str, list[dict[str, Any]]] = {}
        for singular, plural in (
            ("actor", "actors"),
            ("action", "actions"),
            ("condition", "conditions"),
            ("constraint", "constraints"),
            ("exception", "exceptions"),
        ):
            observation = fields.get(singular)
            mapped[plural] = (
                [
                    _supported_span(
                        source_text,
                        sentence,
                        observation,
                        span_id=f"{clause_id}.{singular}.1",
                    )
                ]
                if isinstance(observation, Mapping)
                else []
            )
        actor_id = mapped["actors"][0]["id"] if mapped["actors"] else None
        actor_action_map = [
            {"actor_id": actor_id, "action_id": action["id"]}
            for action in mapped["actions"]
        ]
        clauses.append(
            {
                "clause_id": clause_id,
                "clause_span": clause_span,
                "modality": {
                    "label": prediction.label,
                    "evidence": [modality_evidence],
                },
                **mapped,
                "actor_action_map": actor_action_map,
                "order_relations": [],
            }
        )

    record = {
        "schema_version": SCHEMA_VERSION,
        "sample_id": sample_id,
        "source_id": source_id,
        "source_text": source_text,
        "clauses": clauses,
        "method": {"name": "sun_rule_only", "schema_source": SCHEMA_SOURCE},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
    }
    report = validate_canonical(record)
    if not (report.schema_valid and report.cross_field_valid):
        raise SunB0CompositionError(
            "composed canonical record is invalid: " + "; ".join(report.errors)
        )
    return record


def locked_synthetic_inputs(project_root: Path, s26_config: Mapping[str, Any]) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    """Load exact S2.5 synthetic annotation and attested live observations."""

    root = Path(project_root).resolve()
    extractor = s26_config["phrase_extractor"]
    fixture_spec = extractor["locked_fixture"]
    expected_spec = extractor["locked_live_observations"]
    fixture_path = root / fixture_spec["path"]
    expected_path = root / expected_spec["path"]
    for path, spec, label in (
        (fixture_path, fixture_spec, "S2.5 fixture"),
        (expected_path, expected_spec, "S2.5 live observations"),
    ):
        if not path.is_file() or sha256_file(path) != spec["sha256"]:
            raise SunB0CompositionError(f"{label} is missing or hash-mismatched")
    fixture = _load_object(fixture_path)
    expected = _load_object(expected_path)
    cases = [
        case
        for case in expected.get("cases", [])
        if case.get("sentence_index", -1) < len(fixture["annotation"]["sentences"])
    ]
    return fixture["source_text"], fixture["annotation"], cases


def compose_locked_synthetic_record(
    project_root: Path,
    s26_config: Mapping[str, Any],
    classifier: LockedBertTextCNNInference,
) -> tuple[dict[str, Any], list[ModalityPrediction]]:
    source_text, annotation, cases = locked_synthetic_inputs(project_root, s26_config)
    classifier_inputs = s26_config["verification"]["classifier_input_texts_de"]
    if len(classifier_inputs) != len(annotation["sentences"]):
        raise SunB0CompositionError(
            "locked German classifier inputs must align one-to-one with English phrase sentences"
        )
    predictions = classifier.predict(classifier_inputs)
    record = build_canonical_record(
        sample_id="s26_synthetic_obligation_condition_constraint_v1",
        source_id="s25_locked_live_fixture",
        source_text=source_text,
        annotation=annotation,
        phrase_cases=cases,
        predictions=predictions,
    )
    return record, predictions
