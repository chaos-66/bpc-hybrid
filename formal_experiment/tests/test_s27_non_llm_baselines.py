"""Synthetic contract tests for S2.7-M non-LLM modality baselines."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.sun_style.non_llm_modality_baselines import (  # noqa: E402
    NonLLMBaselineError,
    compile_keyword_patterns,
    evaluate,
    load_config,
    predict_keyword,
    train_majority,
    train_multinomial_nb,
    verify_locked_inputs,
)
from formal_experiment.audit import collect_project_audit  # noqa: E402
from formal_experiment.s2_7_modality_gate import (  # noqa: E402
    S27M_EXPECTATIONS,
    verify_s2_7_modality_gate,
)
from formal_experiment.status import collect_status  # noqa: E402


CONFIG_PATH = ROOT / "configs" / "models" / "s27_non_llm_baselines.json"
RUNNER_PATH = ROOT / "scripts" / "run_s27_modality_baselines.py"


def _config() -> dict:
    return load_config(CONFIG_PATH)


def _rows() -> list[dict[str, str]]:
    return [
        {"sample_id": "d1", "text": "dies gilt als einkommen", "label": "definition"},
        {"sample_id": "d2", "text": "dies gilt im sinne des gesetzes", "label": "definition"},
        {"sample_id": "o1", "text": "der steuerpflichtige muss zahlen", "label": "obligation"},
        {"sample_id": "o2", "text": "die person muss die erklärung abgeben", "label": "obligation"},
        {"sample_id": "p1", "text": "die behörde darf prüfen", "label": "permission"},
        {"sample_id": "p2", "text": "der antragsteller kann wählen", "label": "permission"},
        {"sample_id": "x1", "text": "die person darf nicht offenlegen", "label": "prohibition"},
        {"sample_id": "x2", "text": "dies ist unzulässig", "label": "prohibition"},
    ]


def test_s27_config_and_locked_input_hashes_are_valid() -> None:
    config = _config()
    assert config["labels"] == ["definition", "obligation", "permission", "prohibition"]
    assert config["methods"]["word_ngram_multinomial_nb"]["hyperparameter_search"] is False
    assert config["test_execution_disclosure"]["development_smoke_accessed_test_labels_before_versioned_run"] is True
    assert config["phrase_track"]["status"] == "blocked_pending_s2_2_human_phrase_gold"
    hashes = verify_locked_inputs(ROOT, config)
    assert set(hashes) == {
        "dataset_contract",
        "dataset_manifest",
        "split_summary",
        "local_research_use_decision",
        "train",
        "dev",
        "test",
    }


def test_s27_majority_uses_train_only_counts_and_stable_tie_break() -> None:
    labels = _config()["labels"]
    majority, counts = train_majority(_rows(), labels)
    assert majority == "definition"
    assert counts == {label: 2 for label in labels}
    extended = _rows() + [{"sample_id": "o3", "text": "muss", "label": "obligation"}]
    assert train_majority(extended, labels)[0] == "obligation"


def test_s27_keyword_precedence_handles_prohibition_before_permission() -> None:
    config = _config()
    method = config["methods"]["german_keyword"]
    patterns = compile_keyword_patterns(config)
    predict = lambda text: predict_keyword(
        text,
        patterns=patterns,
        precedence=method["precedence"],
        default_label="obligation",
    )
    assert predict("Die Person darf nicht offenlegen.") == "prohibition"
    assert predict("Die Person darf wählen.") == "permission"
    assert predict("Die Person muss zahlen.") == "obligation"
    assert predict("Dies gilt im Sinne des Gesetzes.") == "definition"
    assert predict("Ohne erkennbaren Marker") == "obligation"


def test_s27_multinomial_nb_is_deterministic_and_dependency_free() -> None:
    config = _config()
    labels = config["labels"]
    first = train_multinomial_nb(_rows(), labels, min_document_frequency=1, alpha=1.0)
    second = train_multinomial_nb(_rows(), labels, min_document_frequency=1, alpha=1.0)
    texts = [row["text"] for row in _rows()]
    assert [first.predict(text) for text in texts] == [second.predict(text) for text in texts]
    assert len(first.vocabulary) > 0
    source = (ROOT / "src" / "bpc_hybrid" / "sun_style" / "non_llm_modality_baselines.py").read_text(encoding="utf-8")
    for forbidden in ("sklearn", "torch", "tensorflow", "openai", "requests"):
        assert forbidden not in source


def test_s27_metric_macro_includes_zero_for_missing_prediction_class() -> None:
    labels = _config()["labels"]
    rows = _rows()
    report = evaluate(rows, ("obligation" for _ in rows), labels)
    assert report["sample_count"] == 8
    assert report["accuracy"] == 0.25
    assert report["per_class"]["definition"]["f1"] == 0.0
    assert report["per_class"]["obligation"]["recall"] == 1.0
    assert report["macro_f1"] == pytest.approx((2 * 0.25 * 1 / 1.25) / 4)
    assert sum(sum(row.values()) for row in report["confusion_matrix"].values()) == 8


def test_s27_invalid_hyperparameters_and_prediction_count_fail_closed() -> None:
    labels = _config()["labels"]
    with pytest.raises(NonLLMBaselineError, match="hyperparameters"):
        train_multinomial_nb(_rows(), labels, min_document_frequency=0, alpha=1.0)
    with pytest.raises(ValueError):
        evaluate(_rows(), ["definition"], labels)


def test_s27_runner_refuses_test_without_explicit_cli_acknowledgement() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER_PATH),
            "--manifest-out",
            str(ROOT / "outputs" / "reports" / "must_not_exist_s27.json"),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "--allow-test-evaluation" in completed.stdout
    assert not (ROOT / "outputs" / "reports" / "must_not_exist_s27.json").exists()


def test_s27_config_is_json_and_contains_no_raw_or_row_output_permission() -> None:
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert raw["metrics"]["row_level_predictions_may_be_persisted"] is False
    assert raw["safety"]["raw_or_row_level_derived_data_persisted"] is False
    assert raw["safety"]["llm_api_called"] is False


def test_s27_exact_gate_status_and_audit_expose_component_not_overall_readiness() -> None:
    gate = verify_s2_7_modality_gate(ROOT)
    assert gate["ready"] is True
    assert gate["modality_component_ready"] is True
    assert gate["s2_7_overall_ready"] is False
    assert gate["phrase_track_ready"] is False
    assert gate["hashes"]["manifest"] == S27M_EXPECTATIONS.manifest_sha256
    assert gate["test_nb_accuracy"] == pytest.approx(0.784037558685446)
    assert gate["test_nb_macro_f1"] == pytest.approx(0.5688485721495562)
    status = collect_status()
    assert status["s2_7_modality_baselines_verified"] is True
    assert status["s2_7_overall_ready"] is False
    audit = collect_project_audit()
    assert audit["s2_7_modality_baselines_verified"] is True
    assert audit["s2_7_overall_ready"] is False
    pass_codes = {item["code"] for item in audit["findings"]["passes"]}
    assert "s2_7_modality_component_baselines_verified" in pass_codes
