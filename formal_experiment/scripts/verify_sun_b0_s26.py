"""Run the locked S2.6 no-LLM classifier/extractor/canonical smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import torch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.sun_style.bert_textcnn import sha256_file  # noqa: E402
from bpc_hybrid.sun_style.sun_b0 import (  # noqa: E402
    LockedBertTextCNNInference,
    SunB0CompositionError,
    compose_locked_synthetic_record,
    load_s26_config,
)
from formal_experiment.corenlp_gate import verify_corenlp_contract  # noqa: E402
from formal_experiment.s2_4_license_gate import verify_s2_4_license_gate  # noqa: E402


DEFAULT_CONFIG = ROOT / "configs" / "models" / "sun_b0_s26.json"


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _verify_component_hashes(config: Mapping[str, Any]) -> dict[str, Any]:
    verified: dict[str, Any] = {}
    for component, specs in (
        ("classifier", config["classifier"]),
        ("phrase_extractor", config["phrase_extractor"]),
    ):
        verified[component] = {}
        for name, spec in specs.items():
            if not isinstance(spec, Mapping) or "path" not in spec or "sha256" not in spec:
                continue
            path = _project_path(spec["path"])
            actual = sha256_file(path)
            if actual != spec["sha256"]:
                raise SunB0CompositionError(f"{component}.{name} SHA-256 mismatch")
            verified[component][name] = {"path": spec["path"], "sha256": actual}
    schema_spec = config["canonical_output"]["schema"]
    schema_path = _project_path(schema_spec["path"])
    schema_hash = sha256_file(schema_path)
    if schema_hash != schema_spec["sha256"]:
        raise SunB0CompositionError("canonical schema SHA-256 mismatch")
    verified["canonical_schema"] = {"path": schema_spec["path"], "sha256": schema_hash}
    return verified


def run(config_path: Path, *, device: str) -> dict[str, Any]:
    config = load_s26_config(config_path)
    component_hashes = _verify_component_hashes(config)
    s24_gate = verify_s2_4_license_gate(ROOT)
    s25_gate = verify_corenlp_contract(ROOT)
    if s24_gate.get("training_completed") is not True:
        raise SunB0CompositionError("S2.4 verified training gate is not ready")
    if s25_gate.get("ready") is not True:
        raise SunB0CompositionError("S2.5 verified extractor gate is not ready")
    classifier = LockedBertTextCNNInference.load(ROOT, config, device=device)
    record, predictions = compose_locked_synthetic_record(ROOT, config, classifier)
    return {
        "schema_version": "sun_b0_s26_verification_manifest@1.0.0",
        "task_id": "S2.6",
        "status": "succeeded",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "method": "sun_rule_only",
        "claim_boundary": config["claim_boundary"],
        "config": {
            "path": config_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(config_path),
            "schema_version": config["schema_version"],
        },
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "device": device,
        },
        "components": component_hashes,
        "composition": {
            "actual_s2_4_checkpoint_loaded": True,
            "s2_4_test_re_evaluated": False,
            "s2_5_attested_live_observation_consumed": True,
            "classifier_input_language": "de",
            "phrase_and_canonical_source_language": "en",
            "parallel_synthetic_text_alignment": True,
            "classifier_input_sha256": [
                hashlib.sha256(text.encode("utf-8")).hexdigest()
                for text in config["verification"]["classifier_input_texts_de"]
            ],
            "record_count": 1,
            "clause_count": len(record["clauses"]),
            "schema_invalid": 0,
            "cross_field_invalid": 0,
            "predicted_modalities": [
                {"label": item.label, "confidence": item.confidence}
                for item in predictions
            ],
            "synthetic_canonical_record": record,
        },
        "safety": {
            "synthetic_fixture_only": True,
            "performance_evaluation": False,
            "gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "test_split_read_or_evaluated": False,
            "row_level_real_data_predictions_persisted": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--manifest-out", type=Path, required=True)
    args = parser.parse_args()
    config_path = args.config.resolve()
    manifest_out = args.manifest_out.resolve()
    if manifest_out.exists():
        raise SunB0CompositionError(f"refusing to overwrite: {manifest_out}")
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest = run(config_path, device=args.device)
    manifest_out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "succeeded", "manifest": str(manifest_out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
