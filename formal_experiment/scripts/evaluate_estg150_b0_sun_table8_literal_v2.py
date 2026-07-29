"""Evaluate immutable B0 v10a attempts with Sun's literal overlap rule."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    build_canonical_gold_records,
    load_object,
    sha256_file,
)
from bpc_hybrid.stage2_evaluation_v3 import membership_sha256  # noqa: E402
from bpc_hybrid.stage2_sun_table8_compatible import (  # noqa: E402
    evaluate_sun_table8_literal_overlap,
)


CONFIG = ROOT / "configs/models/estg150_b0_enhanced_s27_v10a.json"
EVALUATOR = ROOT / "configs/evaluation/sun_table8_literal_overlap_v2.json"
ATTEMPTS = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json"
SOURCE_MANIFEST = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/manifest.json"
OUTPUT = ROOT / "outputs/development/s27_estg150_b0_sun_table8_literal_v2"


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite existing output: {OUTPUT}")
    config = load_object(CONFIG)
    evaluator = load_object(EVALUATOR)
    if (
        evaluator.get("evaluator_id") != "sun_table8_literal_overlap_v2"
        or evaluator.get("evaluation_unit") != "statement"
        or evaluator.get("clause_alignment_required") is not False
        or evaluator.get("assignment") != "none_independent_overlap_coverage"
    ):
        raise RuntimeError("Sun Table 8 literal evaluator identity changed")
    layer_e = ROOT / config["inputs"]["human_correction_layer_e"]["path"]
    membership = ROOT / config["inputs"]["membership_hashes"]["path"]
    gold, source_records = build_canonical_gold_records(layer_e, membership)
    with ATTEMPTS.open("r", encoding="utf-8") as stream:
        attempts = json.load(stream)
    if not isinstance(attempts, list):
        raise RuntimeError("B0 attempts root must be an array")
    metrics = evaluate_sun_table8_literal_overlap(
        gold,
        attempts,
        dataset_id=config["dataset_id"],
        method_id="sun_rule_only:b0_enhanced_v10a",
    )
    fallback_count = sum(
        1
        for record in source_records
        for clause in (record.get("human_correction") or {}).get("clauses", [])
        if not isinstance((clause.get("modality") or {}).get("span"), dict)
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    staging = OUTPUT.parent / f".{OUTPUT.name}.staging-{os.getpid()}"
    if staging.exists():
        raise RuntimeError(f"staging path already exists: {staging}")
    staging.mkdir()
    try:
        metrics_path = staging / "metrics.json"
        _write_json(metrics_path, metrics)
        manifest = {
            "schema_version": "sun_table8_literal_run_manifest@2.0.0",
            "run_id": "s27_estg150_b0_sun_table8_literal_v2",
            "status": "succeeded_development_not_formal",
            "claim_scope": "development_sun_table8_literal_overlap_view",
            "dataset_id": config["dataset_id"],
            "method_id": "sun_rule_only",
            "method_variant": "b0_enhanced_v10a",
            "paper_faithful_b0": False,
            "network_called": False,
            "llm_call_count": 0,
            "gold_modified": False,
            "historical_attempts_modified": False,
            "supersedes_evaluation_view": "s27_estg150_b0_sun_table8_compatible_v1",
            "input_binding": {
                "layer_e_sha256": sha256_file(layer_e),
                "membership_sha256": sha256_file(membership),
                "canonical_gold_membership_sha256": membership_sha256(gold),
                "b0_attempts_sha256": sha256_file(ATTEMPTS),
                "b0_source_manifest_sha256": sha256_file(SOURCE_MANIFEST),
                "evaluator_config_sha256": sha256_file(EVALUATOR),
            },
            "evaluation": {
                "unit": evaluator["evaluation_unit"],
                "match_rule": evaluator["match_rule"],
                "assignment": evaluator["assignment"],
                "clause_alignment_required": False,
                "modality_policy": evaluator["modality_policy"],
                "gold_modality_clause_fallback_count": fallback_count,
            },
            "artifacts": {
                "metrics": {"path": "metrics.json", "sha256": sha256_file(metrics_path)}
            },
        }
        _write_json(staging / "manifest.json", manifest)
        staging.rename(OUTPUT)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
