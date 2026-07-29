"""Exact-hash gate for the S2.7-M non-LLM modality component baselines."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.sun_style.non_llm_modality_baselines import (
    NonLLMBaselineError,
    load_config,
    verify_locked_inputs,
)
from formal_experiment.s2_4_license_gate import get_cached_s2_4_license_gate
from formal_experiment.sun_modality_gate import get_cached_sun_modality_gate


CONFIG_REL = "configs/models/s27_non_llm_baselines.json"
IMPLEMENTATION_REL = "src/bpc_hybrid/sun_style/non_llm_modality_baselines.py"
RUNNER_REL = "scripts/run_s27_modality_baselines.py"
MANIFEST_REL = "outputs/reports/s27_non_llm_modality_baselines_seed20260717_v1.manifest.json"
CONTRACT_REL = "configs/experiment_contract.json"


@dataclass(frozen=True)
class S27MExpectations:
    config_sha256: str = "32705a57fcba88cfcdf76d9ff3a2fb79b918ea77f2664ec52e4e2986c62ad676"
    implementation_sha256: str = "1982b8a7e263fc9d9fa57d9c3f2ce294a10146e51b0d1a5f6a142befe33109df"
    runner_sha256: str = "09b5754fd338e31eda69de88ab6f8e4731af68090e62d5fe8b19c4661f025a51"
    manifest_sha256: str = "171ba1e7074169c0b89f1a277d2330d24e0a9745387a8c400d50d271fa218638"


S27M_EXPECTATIONS = S27MExpectations()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NonLLMBaselineError(f"invalid S2.7-M JSON: {path}") from exc
    if not isinstance(value, dict):
        raise NonLLMBaselineError(f"S2.7-M JSON root must be an object: {path}")
    return value


def verify_s2_7_modality_gate(
    project_root: Path,
    *,
    expectations: S27MExpectations = S27M_EXPECTATIONS,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    errors: list[dict[str, str]] = []

    def require(condition: bool, code: str, message: str) -> None:
        if not condition and code not in {item["code"] for item in errors}:
            errors.append({"code": code, "message": message})

    paths = {
        "config": root / CONFIG_REL,
        "implementation": root / IMPLEMENTATION_REL,
        "runner": root / RUNNER_REL,
        "manifest": root / MANIFEST_REL,
        "contract": root / CONTRACT_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "s2_7m_artifact_missing", f"Missing S2.7-M {name}: {path}")
    if errors:
        return {"ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}
    hashes = {name: _sha256(path) for name, path in paths.items() if name != "contract"}
    for name, expected in (
        ("config", expectations.config_sha256),
        ("implementation", expectations.implementation_sha256),
        ("runner", expectations.runner_sha256),
        ("manifest", expectations.manifest_sha256),
    ):
        require(hashes[name] == expected, f"s2_7m_{name}_hash_mismatch", f"S2.7-M {name} SHA-256 changed")
    try:
        config = load_config(paths["config"])
        manifest = _load(paths["manifest"])
        contract = _load(paths["contract"])
        locked_input_hashes = verify_locked_inputs(root, config)
    except (NonLLMBaselineError, OSError, ValueError) as exc:
        require(False, "s2_7m_artifact_invalid", str(exc))
        config = {}
        manifest = {}
        contract = {}
        locked_input_hashes = {}

    require(
        manifest.get("schema_version") == "s27_non_llm_modality_baselines_manifest@1.0.0"
        and manifest.get("task_id") == "S2.7-M"
        and manifest.get("run_id") == "s27_non_llm_modality_baselines_seed20260717_v1"
        and manifest.get("status") == "succeeded"
        and all(
            manifest.get("artifacts", {}).get(name, {}).get("sha256") == hashes[name]
            for name in ("config", "implementation", "runner")
        ),
        "s2_7m_manifest_identity_mismatch",
        "S2.7-M manifest identity or artifact lock changed",
    )
    dataset = manifest.get("dataset", {})
    require(
        isinstance(dataset, Mapping)
        and dataset.get("dataset_id") == "sun_modality_v1"
        and dataset.get("split_origin") == "project_reconstructed_deterministic_split_not_sun_original"
        and dataset.get("input_hashes") == locked_input_hashes
        and dataset.get("split_counts") == {"train": 1985, "dev": 420, "test": 426}
        and dataset.get("split_ids_disjoint") is True
        and dataset.get("redistribution_forbidden") is True,
        "s2_7m_dataset_binding_mismatch",
        "S2.7-M dataset/split binding changed",
    )
    training = manifest.get("training", {})
    require(
        training == {
            "train_class_counts": {
                "definition": 836,
                "obligation": 891,
                "permission": 185,
                "prohibition": 73,
            },
            "train_majority_label": "obligation",
            "nb_vocabulary_size": 8257,
            "hyperparameter_search": False,
            "model_selection_on_test": False,
        },
        "s2_7m_training_contract_mismatch",
        "S2.7-M train-only feature/model contract changed",
    )
    expected_metrics = {
        "dev": {
            "train_majority": (0.4452380952380952, 0.15403624382207579),
            "german_keyword": (0.5547619047619048, 0.5086283054414611),
            "word_ngram_multinomial_nb": (0.7666666666666667, 0.5818579687448893),
        },
        "test": {
            "train_majority": (0.45774647887323944, 0.1570048309178744),
            "german_keyword": (0.4835680751173709, 0.4141535542543099),
            "word_ngram_multinomial_nb": (0.784037558685446, 0.5688485721495562),
        },
    }
    metrics = manifest.get("metrics", {})
    require(
        metrics.get("label_order") == ["definition", "obligation", "permission", "prohibition"]
        and metrics.get("primary") == "macro_f1",
        "s2_7m_metric_contract_mismatch",
        "S2.7-M label order or primary metric changed",
    )
    for split, methods in expected_metrics.items():
        for method, (accuracy, macro_f1) in methods.items():
            actual = metrics.get(split, {}).get(method, {})
            require(
                actual.get("sample_count") == (420 if split == "dev" else 426)
                and math.isclose(actual.get("accuracy", -1), accuracy, rel_tol=0, abs_tol=1e-15)
                and math.isclose(actual.get("macro_f1", -1), macro_f1, rel_tol=0, abs_tol=1e-15),
                f"s2_7m_{split}_{method}_metric_mismatch",
                f"S2.7-M {split}/{method} aggregate metrics changed",
            )
    disclosure = manifest.get("test_execution_disclosure", {})
    require(
        isinstance(disclosure, Mapping)
        and disclosure.get("development_smoke_accessed_test_labels_before_versioned_run") is True
        and disclosure.get("smoke_configuration_identical_to_locked_nb_contract") is True
        and disclosure.get("hyperparameter_or_model_selection_on_test") is False
        and disclosure.get("versioned_test_run_limit") == 1
        and disclosure.get("known_total_test_evaluations_after_versioned_run") == 2,
        "s2_7m_test_disclosure_mismatch",
        "S2.7-M transparent test-access disclosure changed",
    )
    phrase = manifest.get("phrase_track", {})
    require(
        isinstance(phrase, Mapping)
        and phrase.get("status") == "blocked_pending_s2_2_human_phrase_gold"
        and phrase.get("synthetic_fixture_performance_may_not_substitute_for_gold") is True,
        "s2_7m_phrase_boundary_mismatch",
        "S2.7-M incorrectly claims phrase/full-Stage-2 readiness",
    )
    require(
        manifest.get("safety") == {
            "s2_1_dataset_gate_ready": True,
            "local_research_use_gate_ready": True,
            "llm_api_called": False,
            "network_called": False,
            "env_file_read": False,
            "human_gold_read_or_modified": False,
            "formal_predictions_written": False,
            "row_level_predictions_persisted": False,
            "aggregate_component_result_only": True,
        },
        "s2_7m_safety_boundary_mismatch",
        "S2.7-M safety or aggregate-only boundary changed",
    )
    require(
        get_cached_sun_modality_gate(root).get("ready") is True
        and get_cached_s2_4_license_gate().get("ready") is True,
        "s2_7m_upstream_gate_mismatch",
        "S2.7-M upstream data/local-use gate is not ready",
    )

    gate = contract.get("sun_stage2_method", {}).get("s2_7_modality_baseline_gate", {})
    expected_lock = {
        "config": (CONFIG_REL, hashes["config"]),
        "implementation": (IMPLEMENTATION_REL, hashes["implementation"]),
        "runner": (RUNNER_REL, hashes["runner"]),
        "run_manifest": (MANIFEST_REL, hashes["manifest"]),
    }
    require(
        isinstance(gate, Mapping)
        and gate.get("task_id") == "S2.7-M"
        and gate.get("status") == "verified_modality_component_phrase_track_blocked"
        and gate.get("modality_component_ready") is True
        and gate.get("s2_7_overall_ready") is False
        and gate.get("phrase_track_ready") is False
        and gate.get("row_level_predictions_persisted") is False
        and gate.get("llm_api_called") is False
        and all(
            gate.get(name, {}).get("path") == path
            and gate.get(name, {}).get("sha256") == sha
            for name, (path, sha) in expected_lock.items()
        ),
        "s2_7m_experiment_contract_mismatch",
        "Experiment contract disagrees with S2.7-M artifacts or component boundary",
    )
    return {
        "ready": not errors,
        "modality_component_ready": not errors,
        "s2_7_overall_ready": False,
        "phrase_track_ready": False,
        "errors": errors,
        "blockers": [item["code"] for item in errors],
        "hashes": hashes,
        "test_nb_accuracy": metrics.get("test", {}).get("word_ngram_multinomial_nb", {}).get("accuracy"),
        "test_nb_macro_f1": metrics.get("test", {}).get("word_ngram_multinomial_nb", {}).get("macro_f1"),
        "llm_api_called": False,
    }


def _fingerprint(root: Path) -> tuple[tuple[str, int, int], ...]:
    result: list[tuple[str, int, int]] = []
    for relative in (CONFIG_REL, IMPLEMENTATION_REL, RUNNER_REL, MANIFEST_REL, CONTRACT_REL):
        path = root / relative
        try:
            stat = path.stat()
            result.append((relative, stat.st_size, stat.st_mtime_ns))
        except OSError:
            result.append((relative, -1, -1))
    return tuple(result)


@lru_cache(maxsize=8)
def _cached(root: str, fingerprint: tuple[tuple[str, int, int], ...]) -> dict[str, Any]:
    del fingerprint
    return verify_s2_7_modality_gate(Path(root))


def get_cached_s2_7_modality_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached(str(root), _fingerprint(root)))
