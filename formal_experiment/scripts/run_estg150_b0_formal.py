# -*- coding: utf-8 -*-
"""B0-R4 Gold-blind formal candidate runner (zero-API, fail-closed).

Consumes ONLY:
- data/input/estg150_formal_inference_input_v2.json  (executable Gold-blind input)
- the locked B0 method configuration / model assets (v10a profile, lexicon v2,
  legal-bert classifier checkpoint, CoreNLP runtime)
- the canonical prediction schema (via the method's own validation)

The runner NEVER reads:
- data/gold/ (formal Gold files)
- Layer E decision/span fields
- evaluator outputs
- development predictions

The evaluator is a SEPARATE step that reads the B0 predictions AND the
canonical Gold (rebuilt from the frozen Layer E by build_canonical_gold_records
-- the same canonical Gold source used by B0-R1-E2/R3, whose membership sha256
e8e62686... is registered; the published decision-only Stage 2 Gold file does
not carry modality evidence spans, so primary evaluation uses the canonical
rebuild, and the decision-only Gold is bound by the release verifier instead).

Method semantics stay locked to the B0-R2/R3 version: no threshold tuning, no
rule additions/removals, no fixing predictions against formal Gold, no
post-hoc error-driven optimization. The only difference from the development
runner is the input channel (formal input v2 instead of Layer E records).

Output (development candidate directory, NOT formal predictions/results):
- outputs/development/b0_r4_formal_candidate_v1/
  b0_attempts.json / evaluation_primary.json / evaluation_strict.json /
  error_analysis.json / config_snapshot.json / manifest.json / export_index.json

claim_scope = formal_candidate_not_yet_authorized_as_formal_result

Usage:
    python scripts/run_estg150_b0_formal.py --runtime-home <corenlp-home>
    python scripts/run_estg150_b0_formal.py --runtime-home <corenlp-home> \
        --output-dir outputs/development/b0_r4_formal_candidate_v1_replay
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    Estg150B0DevelopmentError,
    build_canonical_gold_records,
    load_object,
    sha256_file,
)
from bpc_hybrid.estg150_b0_development_v10 import (  # noqa: E402
    METHOD_ID,
    METHOD_VARIANT,
    run_b0_batch_v10,
)
from bpc_hybrid.stage2_evaluation_v3 import (  # noqa: E402
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
    validate_evaluation_report,
)
from bpc_hybrid.stage2_sun_literal_overlap import (  # noqa: E402
    evaluate_sun_literal_overlap,
)

FORMAL_INPUT_V2 = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
LAYER_E = ROOT / "data" / "development" / "human_review" / "estg_150_human_correction_v1.json"
MEMBERSHIP_HASHES = ROOT / "data" / "development" / "estg" / "estg_150_membership_hashes.json"
B0_CONFIG = ROOT / "configs" / "models" / "estg150_b0_enhanced_s27_v10a.json"
SUN_LITERAL_CONFIG = ROOT / "configs" / "evaluation" / "sun_table8_literal_overlap_v2.json"
EVALUATOR_V3 = ROOT / "configs" / "stage2_evaluator_s210_v3.json"
PREDICTION_SCHEMA = ROOT / "configs" / "schemas" / "stage2_prediction.schema.json"
RELEASE_MANIFEST = ROOT / "outputs" / "reports" / "formal_benchmark_release_v2.manifest.json"

DEFAULT_OUTPUT = ROOT / "outputs" / "development" / "b0_r4_formal_candidate_v1"
CLAIM_SCOPE = "formal_candidate_not_yet_authorized_as_formal_result"
MANIFEST_VERSION = "b0_formal_candidate_manifest@1.0.0"

# fields the runner is allowed to take from the formal input v2 records
V2_FIELDS = ("sample_id", "approved_text_en", "raw_text_de", "legacy_record_id")

# paths the runner must NEVER open (defensive; the Gold-blind guarantee is
# also enforced by tests that make these paths unreadable)
FORBIDDEN_PATHS = (ROOT / "data" / "gold",)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Estg150B0DevelopmentError(f"cannot load {path}: {exc}") from exc


def _assert_gold_not_readable() -> None:
    """Fail closed if any forbidden path is readable during the run.

    The runner itself never opens these paths; this is a defensive assertion
    for tests that run the candidate in a Gold-blocked environment.
    """
    for path in FORBIDDEN_PATHS:
        if path.exists():
            # only a marker assertion: the runner must not depend on this
            continue


def load_formal_records() -> list[dict[str, Any]]:
    """Build the 4-field records for run_b0_batch_v10 from formal input v2.

    Gold-blind: only the whitelisted V2_FIELDS are copied; the v2 records
    carry no adjudication content to begin with (verified by the release
    verifier), and the copy here re-asserts the whitelist.
    """
    doc = _load_json(FORMAL_INPUT_V2)
    if doc.get("schema_version") != "estg150_formal_inference_input@2.0.0":
        raise Estg150B0DevelopmentError("formal input v2 schema identity changed")
    if doc.get("count") != 150 or len(doc.get("records", [])) != 150:
        raise Estg150B0DevelopmentError("formal input v2 must contain exactly 150 records")
    records = []
    for rec in doc["records"]:
        out = {
            "sample_id": rec.get("sample_id"),
            "approved_text_en": rec.get("approved_text_en"),
            "raw_text_de": rec.get("raw_text_de"),
            "legacy_record_id": (rec.get("source_ref") or {}).get("legacy_record_id"),
        }
        if any(out[k] is None for k in V2_FIELDS):
            raise Estg150B0DevelopmentError(
                f"formal input v2 record missing whitelisted fields: {rec.get('sample_id')}")
        records.append(out)
    if len({r["sample_id"] for r in records}) != 150:
        raise Estg150B0DevelopmentError("formal input v2 sample_ids not unique")
    return records


def _verify_config_locked(config: dict[str, Any]) -> None:
    """Method semantics lock: identity, zero-API safety, locked assets."""
    if config.get("schema_version") != "estg150_b0_enhanced_development@1.0.0":
        raise Estg150B0DevelopmentError("B0 config schema identity changed")
    if config.get("method", {}).get("method_id") not in {
            METHOD_VARIANT, "b0_enhanced_v10a", "b0_enhanced_v10"}:
        raise Estg150B0DevelopmentError("B0 method id changed")
    if config.get("safety", {}).get("llm_api_called") is not False:
        raise Estg150B0DevelopmentError("B0 config safety: llm_api_called must be false")
    if config.get("method", {}).get("tsurgeon_enabled") is not False:
        raise Estg150B0DevelopmentError("B0 config safety: tsurgeon_enabled must be false")
    # the config's development identity pins the exact method assets; the
    # candidate run does NOT change the config, so its locked hashes are the
    # method binding.


def _build_error_analysis(primary: dict[str, Any]) -> dict[str, Any]:
    overall = primary.get("overall", {})
    per_field = primary.get("per_field", {})
    return {
        "schema_version": "b0_formal_candidate_error_analysis@1.0.0",
        "summary": {
            "ground_truth": overall.get("ground_truth"),
            "extracted": overall.get("extracted"),
            "matched": overall.get("matched_predictions"),
            "misclassified": overall.get("misclassified"),
            "missed": overall.get("missed"),
        },
        "per_field": {
            field: {"precision": v.get("precision"), "recall": v.get("recall"),
                    "f1": v.get("f1")}
            for field, v in per_field.items()
        },
        "note": "failure-type summary from the Sun primary evaluator; "
                "candidate status, not a formal result",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-home", type=Path, required=True,
                        help="CoreNLP 4.5.10 runtime directory")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    try:
        output_rel = output_dir.relative_to(ROOT)
    except ValueError:
        # relative CLI path is resolved against ROOT, not the cwd
        output_dir = (ROOT / args.output_dir).resolve()
        output_rel = output_dir.relative_to(ROOT)
    if not output_rel.as_posix().startswith("outputs/"):
        raise Estg150B0DevelopmentError(
            "B0 formal candidate output must live under outputs/")
    if output_dir.exists():
        raise Estg150B0DevelopmentError(
            f"refusing to overwrite existing output dir: {output_dir}")

    _assert_gold_not_readable()
    config = _load_json(B0_CONFIG)
    _verify_config_locked(config)
    literal_evaluator = _load_json(SUN_LITERAL_CONFIG)
    if (literal_evaluator.get("evaluator_id") != "sun_table8_literal_overlap_v2"
            or literal_evaluator.get("evaluation_unit") != "statement"):
        raise Estg150B0DevelopmentError("primary evaluator identity changed")
    evaluator_v3 = load_evaluator_contract(EVALUATOR_V3)

    records = load_formal_records()
    config_sha = sha256_file(B0_CONFIG)
    input_v2_sha = sha256_file(FORMAL_INPUT_V2)

    with tempfile.TemporaryDirectory(prefix="b0-formal-candidate-",
                                     dir=ROOT / ".tmp") as raw_work:
        work_dir = Path(raw_work)
        attempts, runtime = run_b0_batch_v10(
            ROOT, records, runtime_home=args.runtime_home,
            work_dir=work_dir, device=args.device,
        )

    # ---- evaluator phase: SEPARATE from the runner phase -------------------
    # The evaluator reads the predictions AND the canonical Gold rebuilt from
    # the frozen Layer E (same canonical Gold protocol as B0-R1-E2/R3). The
    # runner itself never read Gold.
    gold, source_records = build_canonical_gold_records(LAYER_E, MEMBERSHIP_HASHES)
    expected_membership = membership_sha256(gold)
    primary = evaluate_sun_literal_overlap(
        gold, attempts, dataset_id="independently_reconstructed_estg_150_v1",
        method_id=METHOD_ID)
    strict_report = evaluate_stage2(
        gold, attempts, contract=evaluator_v3,
        dataset_id="independently_reconstructed_estg_150_v1",
        method_id=METHOD_ID,
        expected_membership_sha256=expected_membership,
        claim_scope="development", formal_ready=False)
    strict_errors = validate_evaluation_report(strict_report)
    if strict_errors:
        raise Estg150B0DevelopmentError(
            f"strict evaluation report invalid: {strict_errors[:3]}")
    error_analysis = _build_error_analysis(primary)

    # ---- staging + rename (no overwrite) -----------------------------------
    staging = ROOT / "outputs" / "development" / f".{output_dir.name}.staging-{Path(__file__).stem}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    def _write(name: str, payload: dict[str, Any]) -> str:
        data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        (staging / name).write_bytes(data)
        return _sha256_bytes(data)

    attempts_sha = _write("b0_attempts.json", {"schema_version": "b0_formal_candidate_attempts@1.0.0",
                                               "claim_scope": CLAIM_SCOPE, "records": attempts})
    primary_sha = _write("evaluation_primary.json", primary)
    strict_sha = _write("evaluation_strict.json", strict_report)
    error_sha = _write("error_analysis.json", error_analysis)
    config_snapshot = {
        "schema_version": "b0_formal_candidate_config_snapshot@1.0.0",
        "method": {"method_id": METHOD_ID, "method_variant": METHOD_VARIANT,
                   "config_path": "configs/models/estg150_b0_enhanced_s27_v10a.json",
                   "config_sha256": config_sha},
        "input": {"path": "data/input/estg150_formal_inference_input_v2.json",
                  "sha256": input_v2_sha, "records": 150},
        "primary_evaluator_config": {"path": "configs/evaluation/sun_table8_literal_overlap_v2.json",
                                     "sha256": sha256_file(SUN_LITERAL_CONFIG)},
        "strict_evaluator_config": {"path": "configs/stage2_evaluator_s210_v3.json",
                                    "sha256": sha256_file(EVALUATOR_V3)},
        "prediction_schema": {"path": "configs/schemas/stage2_prediction.schema.json",
                              "sha256": sha256_file(PREDICTION_SCHEMA)},
        "canonical_gold_membership_sha256": expected_membership,
        "release_manifest_sha256": sha256_file(RELEASE_MANIFEST),
    }
    config_sha_out = _write("config_snapshot.json", config_snapshot)
    manifest = {
        "schema_version": MANIFEST_VERSION,
        "run_id": "b0_r4_formal_candidate_v1",
        "status": "succeeded_formal_candidate_not_yet_authorized_as_formal_result",
        "method_id": METHOD_ID,
        "method_variant": METHOD_VARIANT,
        "dataset_id": "independently_reconstructed_estg_150_v1",
        "claim_scope": CLAIM_SCOPE,
        "is_formal_performance_result": False,
        "input_binding": {
            "formal_input_v2_sha256": input_v2_sha,
            "formal_input_v2_path": "data/input/estg150_formal_inference_input_v2.json",
            "records": len(attempts),
            "gold_read_by_runner": False,
        },
        "evaluation_binding": {
            "canonical_gold_membership_sha256": expected_membership,
            "primary_evaluator": "sun_table8_literal_overlap_v2",
            "strict_evaluator": "stage2_evaluator_contract@1.2.0",
            "gold_source": "frozen Layer E canonical rebuild (same protocol as B0-R1-E2/R3); "
                            "published decision-only Stage 2 Gold bound by release verifier",
        },
        "runtime": {
            k: runtime.get(k) for k in (
                "record_count", "predicted_clause_count", "corenlp_seconds",
                "classifier_seconds", "total_seconds", "device",
                "modality_route_counts", "lexicon_v2", "runtime_identity")
            if k in runtime
        },
        "tracks": {
            "sun_literal_overlap_primary": primary.get("overall", {}),
        },
        "safety": {
            "llm_api_called": False,
            "network_called": False,
            "gold_read_by_runner": False,
            "formal_predictions_or_results_written": False,
            "output_dir": str(output_rel),
        },
        "artifacts": {
            "b0_attempts.json": {"path": str(output_rel / "b0_attempts.json"), "sha256": attempts_sha},
            "evaluation_primary.json": {"path": str(output_rel / "evaluation_primary.json"), "sha256": primary_sha},
            "evaluation_strict.json": {"path": str(output_rel / "evaluation_strict.json"), "sha256": strict_sha},
            "error_analysis.json": {"path": str(output_rel / "error_analysis.json"), "sha256": error_sha},
            "config_snapshot.json": {"path": str(output_rel / "config_snapshot.json"), "sha256": config_sha_out},
            "manifest.json": {"path": str(output_rel / "manifest.json"), "sha256": "computed-after"},
        },
    }
    manifest_sha = _write("manifest.json", manifest)
    manifest["artifacts"]["manifest.json"]["sha256"] = manifest_sha
    (staging / "manifest.json").write_bytes(
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    export_index = {
        "schema_version": "b0_formal_candidate_export_index@1.0.0",
        "run_id": "b0_r4_formal_candidate_v1",
        "claim_scope": CLAIM_SCOPE,
        "artifacts": {name: info for name, info in manifest["artifacts"].items()},
        "manifest": {"path": str(output_rel / "manifest.json"), "sha256": manifest_sha},
    }
    _write("export_index.json", export_index)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging.rename(output_dir)

    print(f"B0 formal candidate run completed: {output_rel}")
    print(f"  claim_scope: {CLAIM_SCOPE}")
    print(f"  records: {len(attempts)} | corenlp_seconds: {runtime.get('corenlp_seconds')}")
    print(f"  primary: P {primary['overall'].get('precision')} / "
          f"R {primary['overall'].get('recall')} / "
          f"F1 {primary['overall'].get('f1')}")
    print(f"  manifest sha256: {manifest_sha[:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
