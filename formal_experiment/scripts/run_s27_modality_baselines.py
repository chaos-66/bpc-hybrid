"""Run the locked S2.7-M non-LLM modality baselines once, aggregate-only."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.sun_style.non_llm_modality_baselines import (  # noqa: E402
    NonLLMBaselineError,
    load_config,
    run_locked_baselines,
    sha256_file,
)
from formal_experiment.s2_4_license_gate import get_cached_s2_4_license_gate  # noqa: E402
from formal_experiment.sun_modality_gate import get_cached_sun_modality_gate  # noqa: E402


DEFAULT_CONFIG = ROOT / "configs" / "models" / "s27_non_llm_baselines.json"
DEFAULT_RUN_ID = "s27_non_llm_modality_baselines_seed20260717_v1"
REPORTS_DIR = ROOT / "outputs" / "reports"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--manifest-out", type=Path, required=True)
    parser.add_argument(
        "--allow-test-evaluation",
        action="store_true",
        help="Required explicit CLI acknowledgement for the single versioned test evaluation.",
    )
    args = parser.parse_args()
    if not args.allow_test_evaluation:
        print("Refusing test evaluation without --allow-test-evaluation.")
        return 2
    if args.run_id != DEFAULT_RUN_ID:
        print(f"Refusing unregistered run_id: {args.run_id}")
        return 2
    target = args.manifest_out.resolve()
    try:
        target.relative_to(REPORTS_DIR.resolve())
    except ValueError:
        print("S2.7-M aggregate manifest must be written under outputs/reports.")
        return 2
    if target.exists():
        print(f"Refusing to overwrite: {target}")
        return 2
    try:
        config_path = args.config.resolve()
        config = load_config(config_path)
        modality_gate = get_cached_sun_modality_gate(ROOT)
        if modality_gate.get("ready") is not True:
            raise NonLLMBaselineError("locked S2.1 modality dataset gate is not ready")
        license_gate = get_cached_s2_4_license_gate()
        if license_gate.get("ready") is not True:
            raise NonLLMBaselineError("local research-use decision gate is not ready")
        run = run_locked_baselines(ROOT, config)
        manifest = {
            "schema_version": "s27_non_llm_modality_baselines_manifest@1.0.0",
            "task_id": "S2.7-M",
            "run_id": args.run_id,
            "status": "succeeded",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "runtime": {"python": platform.python_version(), "external_ml_dependency": False},
            "claim_boundary": config["claim_boundary"],
            "artifacts": {
                "config": {
                    "path": config_path.relative_to(ROOT).as_posix(),
                    "sha256": sha256_file(config_path),
                },
                "implementation": {
                    "path": "src/bpc_hybrid/sun_style/non_llm_modality_baselines.py",
                    "sha256": sha256_file(
                        ROOT / "src" / "bpc_hybrid" / "sun_style" / "non_llm_modality_baselines.py"
                    ),
                },
                "runner": {
                    "path": "scripts/run_s27_modality_baselines.py",
                    "sha256": sha256_file(ROOT / "scripts" / "run_s27_modality_baselines.py"),
                },
            },
            "dataset": {
                "dataset_id": config["dataset_binding"]["dataset_id"],
                "split_origin": "project_reconstructed_deterministic_split_not_sun_original",
                "input_hashes": run["input_hashes"],
                "split_counts": run["split_counts"],
                "split_ids_disjoint": run["split_ids_disjoint"],
                "redistribution_forbidden": True,
            },
            "training": {
                "train_class_counts": run["train_class_counts"],
                "train_majority_label": run["train_majority_label"],
                "nb_vocabulary_size": run["nb_vocabulary_size"],
                "hyperparameter_search": False,
                "model_selection_on_test": False,
            },
            "test_execution_disclosure": config["test_execution_disclosure"],
            "metrics": {
                "label_order": config["labels"],
                "primary": "macro_f1",
                "dev": run["results"]["dev"],
                "test": run["results"]["test"],
            },
            "phrase_track": config["phrase_track"],
            "safety": {
                "s2_1_dataset_gate_ready": True,
                "local_research_use_gate_ready": True,
                "llm_api_called": False,
                "network_called": False,
                "env_file_read": False,
                "human_gold_read_or_modified": False,
                "formal_predictions_written": False,
                "row_level_predictions_persisted": run["row_level_predictions_persisted"],
                "aggregate_component_result_only": True,
            },
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except NonLLMBaselineError as exc:
        print(f"S2.7-M failed closed: {exc}")
        return 2
    print(json.dumps({"status": "succeeded", "manifest": str(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
