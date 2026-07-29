"""Exact-hash gate for the EStG-150 B0 development evaluation."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


CONFIG_REL = "configs/models/estg150_b0_development_s27.json"
IMPLEMENTATION_REL = "src/bpc_hybrid/estg150_b0_development.py"
RUNNER_REL = "scripts/run_estg150_b0_development.py"
BRIDGE_REL = "tools/corenlp/SunPhraseRuleBatchBridge.java"
OUTPUT_REL = "outputs/development/s27_estg150_b0_development_v1"
MANIFEST_REL = f"{OUTPUT_REL}/manifest.json"


@dataclass(frozen=True)
class S27B0DevelopmentExpectations:
    config_sha256: str = "bdd0f994b61f727f34e92bbcb8023c16985058e56905bb3583c60e83bbafeece"
    implementation_sha256: str = "2199d8cca4da25d05cf2e9635d571ca035683bc9217f692809878db3c116a580"
    runner_sha256: str = "1e1f3ae98d7368fd30ea672757bdec16f2be71b0f8bff7bea1ac600fc7c2136c"
    bridge_sha256: str = "f10133398b8b491cbae66386f6d128860065e9f6ed11faa5f73fc26c21703814"
    manifest_sha256: str = "7ab968a5da3fb482e8135977cc323828c8c682db0379bd95c1dacabdc6af8746"


S27_B0_DEVELOPMENT_EXPECTATIONS = S27B0DevelopmentExpectations()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_s2_7_b0_development_gate(
    project_root: Path,
    *,
    expectations: S27B0DevelopmentExpectations = S27_B0_DEVELOPMENT_EXPECTATIONS,
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
        "bridge": root / BRIDGE_REL,
        "manifest": root / MANIFEST_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "s2_7_b0_dev_artifact_missing", f"Missing {name}: {path}")
    if errors:
        return {"ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}

    hashes = {name: _sha256(path) for name, path in paths.items()}
    for name in paths:
        require(
            hashes[name] == getattr(expectations, f"{name}_sha256"),
            f"s2_7_b0_dev_{name}_hash_mismatch",
            f"S2.7 B0 development {name} SHA-256 changed",
        )

    try:
        config = _load(paths["config"])
        manifest = _load(paths["manifest"])
        attempts = _load(root / OUTPUT_REL / "b0_attempts.json")
        report_all = _load(root / OUTPUT_REL / "evaluation_all150.json")
        report_independent = _load(root / OUTPUT_REL / "evaluation_independent82.json")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        require(False, "s2_7_b0_dev_json_invalid", str(exc))
        config, manifest, attempts, report_all, report_independent = {}, {}, [], {}, {}

    require(
        config.get("schema_version") == "estg150_b0_development@1.0.0"
        and config.get("claim_scope") == "development"
        and config.get("safety", {}).get("llm_api_called") is False,
        "s2_7_b0_dev_config_boundary_mismatch",
        "Development config identity or safety boundary changed",
    )
    require(
        manifest.get("schema_version") == "estg150_b0_development_manifest@1.0.0"
        and manifest.get("run_id") == "s27_estg150_b0_development_v1"
        and manifest.get("status") == "succeeded_development_not_formal"
        and manifest.get("method_id") == "sun_rule_only"
        and manifest.get("claim_scope") == "development"
        and manifest.get("is_formal_performance_result") is False,
        "s2_7_b0_dev_manifest_identity_mismatch",
        "Development manifest identity or claim boundary changed",
    )

    artifact_specs = manifest.get("artifacts", {})
    artifact_paths = {
        "attempts": root / OUTPUT_REL / "b0_attempts.json",
        "evaluation_all150": root / OUTPUT_REL / "evaluation_all150.json",
        "evaluation_independent82": root / OUTPUT_REL / "evaluation_independent82.json",
    }
    for name, path in artifact_paths.items():
        require(
            path.is_file()
            and artifact_specs.get(name, {}).get("path") == path.name
            and artifact_specs.get(name, {}).get("sha256") == _sha256(path),
            f"s2_7_b0_dev_{name}_binding_mismatch",
            f"Development output binding changed for {name}",
        )

    attempt_ids = {
        item.get("sample_id") for item in attempts if isinstance(item, Mapping)
    }
    require(
        isinstance(attempts, list)
        and len(attempts) == 150
        and len(attempt_ids) == 150
        and all(item.get("request_status") == "ok" for item in attempts)
        and all(item.get("runtime", {}).get("llm_call_performed") is False for item in attempts),
        "s2_7_b0_dev_attempt_coverage_mismatch",
        "B0 attempts are not 150 unique successful no-LLM rows",
    )
    require(
        report_all.get("membership", {}).get("sample_count") == 150
        and report_all.get("membership", {}).get("gold_attempt_ids_exact_match") is True
        and report_independent.get("membership", {}).get("sample_count") == 82
        and report_independent.get("membership", {}).get("gold_attempt_ids_exact_match") is True,
        "s2_7_b0_dev_evaluation_membership_mismatch",
        "All-150 or independent-82 evaluator membership changed",
    )

    tracks = manifest.get("tracks", {})
    all150 = tracks.get("all150", {})
    independent82 = tracks.get("independent82_sensitivity", {})
    require(
        all150.get("sample_count") == 150
        and math.isclose(all150.get("modality_clause_accuracy", -1), 0.1038961038961039)
        and math.isclose(all150.get("modality_macro_f1", -1), 0.09058315621249324)
        and independent82.get("sample_count") == 82
        and math.isclose(independent82.get("modality_clause_accuracy", -1), 0.12844036697247707)
        and math.isclose(independent82.get("modality_macro_f1", -1), 0.11912442396313364),
        "s2_7_b0_dev_primary_metric_mismatch",
        "Locked B0 development primary metrics changed",
    )
    runtime = manifest.get("runtime", {})
    safety = manifest.get("safety", {})
    require(
        runtime.get("record_count") == 150
        and runtime.get("sentence_count") == 266
        and runtime.get("terminal_tree_removal_count") == 2
        and safety.get("llm_call_count") == 0
        and safety.get("estimated_cost_usd") == 0.0
        and safety.get("network_called") is False
        and safety.get("formal_predictions_or_results_written") is False,
        "s2_7_b0_dev_runtime_safety_mismatch",
        "B0 runtime diagnostics or no-LLM/development safety changed",
    )
    return {
        "ready": not errors,
        "development_only": True,
        "formal_performance_result": False,
        "errors": errors,
        "blockers": [item["code"] for item in errors],
        "hashes": hashes,
        "all150": {
            "sample_count": all150.get("sample_count"),
            "modality_clause_accuracy": all150.get("modality_clause_accuracy"),
            "modality_macro_f1": all150.get("modality_macro_f1"),
        },
        "independent82_sensitivity": {
            "sample_count": independent82.get("sample_count"),
            "modality_clause_accuracy": independent82.get("modality_clause_accuracy"),
            "modality_macro_f1": independent82.get("modality_macro_f1"),
        },
        "llm_call_count": safety.get("llm_call_count"),
    }
