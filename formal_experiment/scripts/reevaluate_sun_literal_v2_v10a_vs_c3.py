"""B0-R1-E2: offline Sun literal-overlap v2 re-evaluation of historical
v10a and R1-A-C3 attempts against the 56d2b03 historical Gold-equivalent.

This script is the real (non-dry-run) re-evaluation entry point.  It:

1. reads the historical Layer E / membership / freeze-receipt blobs from the
   pinned source commit ``56d2b03`` via ``git show`` (raw bytes, no EOL
   rewriting) into a temporary directory under ``formal_experiment/.tmp``;
2. builds one canonical Gold object with the current HEAD
   ``build_canonical_gold_records`` and evaluates BOTH attempt sets with the
   current HEAD ``evaluate_sun_literal_overlap`` in the same process;
3. writes v10a_metrics.json, c3_metrics.json, delta.json and manifest.json
   into a fresh, never-overwritten output directory.

No B0 prediction rerun, no CoreNLP, no LLM/API, no network, no Gold bytes
persisted in outputs.  Development-only, not formal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    Estg150B0DevelopmentError,
    build_canonical_gold_records,
    sha256_file,
)
from bpc_hybrid.stage2_evaluation_v3 import membership_sha256  # noqa: E402
from bpc_hybrid.stage2_sun_literal_overlap import (  # noqa: E402
    evaluate_sun_literal_overlap,
)

SOURCE_COMMIT = "56d2b03"
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "outputs/development/s27_estg150_b0_v10a_vs_r1a_c3_sun_literal_v2_hist56d_v1"
)
V10A_ATTEMPTS_PATH = (
    ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json"
)
C3_ATTEMPTS_PATH = (
    ROOT
    / "outputs/development/s27_estg150_b0_enhanced_v10a_r1a_c3_hist56d_v1"
    / "b0_attempts.json"
)
EVALUATOR_CONFIG_PATH = (
    ROOT / "configs/evaluation/sun_table8_literal_overlap_v2.json"
)
EVALUATOR_SOURCE_PATH = ROOT / "src/bpc_hybrid/stage2_sun_literal_overlap.py"
GOLD_BUILDER_SOURCE_PATH = ROOT / "src/bpc_hybrid/estg150_b0_development.py"
DATASET_ID = "independently_reconstructed_estg_150_v1"
METHOD_ID = "sun_rule_only"

HISTORICAL_PATHS = {
    "layer_e": "formal_experiment/data/development/human_review/estg_150_human_correction_v1.json",
    "membership": "formal_experiment/data/development/estg/estg_150_membership_hashes.json",
    "freeze_receipt": "formal_experiment/outputs/reports/s22_estg150_human_annotation_freeze_v1.manifest.json",
}

METRIC_KEYS = (
    "ground_truth",
    "extracted",
    "matched_predictions",
    "matched_ground_truth",
    "misclassified",
    "missed",
    "precision",
    "recall",
    "f1",
)


class ReevaluationError(ValueError):
    """Raised when the offline re-evaluation cannot proceed safely."""


def semantic_hash_json(value: Any) -> str:
    """Deterministic semantic hash of a JSON-serializable object."""
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd or _git_root(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


_GIT_ROOT: Path | None = None


def _git_root() -> Path:
    global _GIT_ROOT
    if _GIT_ROOT is None:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        _GIT_ROOT = Path(completed.stdout.decode("utf-8").strip())
    return _GIT_ROOT


def git_full_sha(commit: str) -> str:
    return _git("rev-parse", commit).stdout.decode("ascii").strip()


def git_show_bytes(commit: str, path: str) -> bytes:
    return _git("show", f"{commit}:{path}").stdout


def git_blob_oid(commit: str, path: str) -> str:
    line = _git("ls-tree", commit, "--", path).stdout.decode("ascii").strip()
    if not line:
        raise ReevaluationError(f"path {path!r} not present in {commit}")
    parts = line.split()
    if len(parts) < 3 or parts[1] != "blob":
        raise ReevaluationError(f"unexpected ls-tree entry for {path!r}: {line!r}")
    return parts[2]


def load_json_bytes(data: bytes, *, label: str) -> Any:
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReevaluationError(f"{label} is not valid UTF-8 JSON: {exc}") from exc


def validate_attempts(
    gold_by_id: dict[str, Any], attempts: Sequence[Mapping[str, Any]], *, label: str
) -> dict[str, Any]:
    attempt_by_id: dict[str, Any] = {}
    for row in attempts:
        if not isinstance(row, Mapping):
            raise ReevaluationError(f"{label} attempt rows must be objects")
        sample_id = row.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in attempt_by_id:
            raise ReevaluationError(f"{label} attempt sample_ids must be unique non-empty strings")
        attempt_by_id[sample_id] = row
    if set(attempt_by_id) != set(gold_by_id):
        missing = sorted(set(gold_by_id) - set(attempt_by_id))[:5]
        extra = sorted(set(attempt_by_id) - set(gold_by_id))[:5]
        raise ReevaluationError(
            f"{label} membership differs from Gold: missing={missing}, extra={extra}"
        )
    return attempt_by_id


def compute_delta(v10a: dict[str, Any], c3: dict[str, Any]) -> dict[str, Any]:
    """C3 minus v10a for overall and every per-field numeric metric."""

    def sub(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        delta: dict[str, Any] = {}
        for key in METRIC_KEYS:
            delta[key] = left[key] - right[key]
        return delta

    return {
        "basis": "c3_minus_v10a",
        "overall": sub(c3["overall"], v10a["overall"]),
        "per_field": {
            field: sub(c3["per_field"][field], v10a["per_field"][field])
            for field in v10a["per_field"]
        },
    }


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _evaluate(
    gold: list[dict[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
    *,
    method_variant: str,
) -> dict[str, Any]:
    report = evaluate_sun_literal_overlap(
        gold,
        attempts,
        dataset_id=DATASET_ID,
        method_id=METHOD_ID,
    )
    report["method_variant"] = method_variant
    return report


def run(output_dir: Path, source_commit: str) -> int:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise ReevaluationError(f"refusing to overwrite: {output_dir}")
    try:
        output_dir.relative_to((ROOT / "outputs/development").resolve())
    except ValueError as exc:
        raise ReevaluationError(
            "re-evaluation output must remain under outputs/development"
        ) from exc

    commit_sha = git_full_sha(source_commit)
    temp_root = ROOT / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    provenance: dict[str, Any] = {
        "source_commit": commit_sha,
        "source_commit_ref": source_commit,
        "git_blobs": {},
    }
    with tempfile.TemporaryDirectory(
        prefix=f"reeval-sun-lit-v2-{os.getpid()}-", dir=temp_root
    ) as raw_work:
        work_dir = Path(raw_work)
        for key, path in HISTORICAL_PATHS.items():
            blob_oid = git_blob_oid(source_commit, path)
            blob_bytes = git_show_bytes(source_commit, path)
            provenance["git_blobs"][key] = {
                "path": path,
                "blob_oid": blob_oid,
                "raw_sha256": sha256_bytes(blob_bytes),
                "size_bytes": len(blob_bytes),
            }
            (work_dir / key).write_bytes(blob_bytes)

        layer_e_path = work_dir / "layer_e"
        membership_path = work_dir / "membership"

        gold, source_records = build_canonical_gold_records(
            layer_e_path, membership_path
        )
        gold_by_id = {row["sample_id"]: row for row in gold}
        if len(gold) != 150 or len(gold_by_id) != 150:
            raise ReevaluationError("canonical Gold must contain 150 unique sample_ids")

        v10a_attempts = load_json_bytes(
            V10A_ATTEMPTS_PATH.read_bytes(), label="v10a attempts"
        )
        c3_attempts = load_json_bytes(C3_ATTEMPTS_PATH.read_bytes(), label="C3 attempts")
        if not isinstance(v10a_attempts, list) or not isinstance(c3_attempts, list):
            raise ReevaluationError("attempts files must be JSON arrays")
        validate_attempts(gold_by_id, v10a_attempts, label="v10a")
        validate_attempts(gold_by_id, c3_attempts, label="c3")

        v10a_metrics = _evaluate(gold, v10a_attempts, method_variant="b0_enhanced_v10a")
        c3_metrics = _evaluate(
            gold, c3_attempts, method_variant="b0_enhanced_v10a_r1a_c3"
        )
        delta = compute_delta(v10a_metrics, c3_metrics)

        canonical_membership = membership_sha256(gold)
        declared_membership = "e8e6268644cbc9b7ed42bef19f2e2e2432633a306eab9bf009725ef9571785d7"
        if canonical_membership != declared_membership:
            raise ReevaluationError(
                "canonical Gold membership hash does not match the registered v10a/C3 "
                f"binding: got {canonical_membership}, expected {declared_membership}"
            )

        evaluator_config = load_json_bytes(
            EVALUATOR_CONFIG_PATH.read_bytes(), label="evaluator config"
        )
        if (
            evaluator_config.get("evaluator_id") != "sun_table8_literal_overlap_v2"
            or evaluator_config.get("evaluation_unit") != "statement"
            or evaluator_config.get("clause_alignment_required") is not False
            or evaluator_config.get("assignment") != "none_independent_overlap_coverage"
        ):
            raise ReevaluationError("Sun literal-overlap primary evaluator identity changed")

        staging = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
        if staging.exists():
            raise ReevaluationError(f"staging path already exists: {staging}")
        staging.mkdir()
        try:
            v10a_metrics_path = staging / "v10a_metrics.json"
            c3_metrics_path = staging / "c3_metrics.json"
            delta_path = staging / "delta.json"
            manifest_path = staging / "manifest.json"
            _write_json(v10a_metrics_path, v10a_metrics)
            _write_json(c3_metrics_path, c3_metrics)
            _write_json(delta_path, delta)

            manifest = {
                "schema_version": "estg150_b0_v10a_vs_c3_sun_literal_reevaluation_manifest@1.0.0",
                "run_id": "s27_estg150_b0_v10a_vs_r1a_c3_sun_literal_v2_hist56d_v1",
                "task_id": "B0-R1-E2",
                "status": "succeeded_development_not_formal",
                "method_id": METHOD_ID,
                "paper_faithful_b0": False,
                "dataset_id": DATASET_ID,
                "claim_scope": "development",
                "is_formal_performance_result": False,
                "is_formal_gold": False,
                "llm_api_called": False,
                "network_called": False,
                "provenance": provenance,
                "gold": {
                    "source": f"56d2b03 (commit {commit_sha}) historical Layer E + membership, read-only via git show bytes",
                    "read_only": True,
                    "modified": False,
                    "persisted_copy": False,
                    "canonical_records": len(gold),
                    "canonical_gold_semantic_sha256": semantic_hash_json(gold),
                    "canonical_membership_sha256": canonical_membership,
                    "registered_binding_membership_sha256": declared_membership,
                    "registered_binding_layer_e_sha256": "7fd55f98a7dd6aeef58a93be825465c767f00feeab84c6d4215afc434a135b1c",
                    "registered_binding_freeze_receipt_sha256": "aa316ed71751192cada9c3077ab1ebbba76081b20d102e9873c66ac315146961",
                },
                "attempts": {
                    "v10a": {
                        "path": str(V10A_ATTEMPTS_PATH),
                        "raw_sha256": sha256_bytes(V10A_ATTEMPTS_PATH.read_bytes()),
                        "git_tracked": False,
                        "blob_oid": None,
                        "provenance_note": (
                            "original v10a baseline run output; NOT present in 56d2b03 "
                            "(git cat-file -e and narrow git ls-tree both negative) and "
                            "never versioned; survives only as a local ignored artifact; "
                            "its manifest is internally consistent (all 4 artifact hashes "
                            "self-match) and binds layer_e_sha256=7fd55f98 and "
                            "freeze_receipt_sha256=aa316ed7; diagnostic values match the "
                            "recorded R1-A baseline (TP458/FP415/FN366)"
                        ),
                    },
                    "c3": {
                        "path": str(C3_ATTEMPTS_PATH),
                        "raw_sha256": sha256_bytes(C3_ATTEMPTS_PATH.read_bytes()),
                        "git_tracked": True,
                        "blob_oid": git_blob_oid(
                            "HEAD", "formal_experiment/outputs/development/"
                            "s27_estg150_b0_enhanced_v10a_r1a_c3_hist56d_v1/b0_attempts.json"
                        ),
                        "registered_manifest_sha256": "c694f7cd1f7b218eff8327c2451ac9a3d8c923da245a407ebb09eafd5d0a8f8a",
                    },
                    "sample_id_sets": {
                        "gold_count": len(gold_by_id),
                        "v10a_count": len(v10a_attempts),
                        "c3_count": len(c3_attempts),
                        "v10a_matches_gold": set(a["sample_id"] for a in v10a_attempts) == set(gold_by_id),
                        "c3_matches_gold": set(a["sample_id"] for a in c3_attempts) == set(gold_by_id),
                    },
                },
                "evaluator": {
                    "evaluator_id": "sun_table8_literal_overlap_v2",
                    "schema_version": v10a_metrics["schema_version"],
                    "evaluation_unit": "statement",
                    "match_rule": "independent_same_field_any_nonempty_character_span_intersection",
                    "assignment": "none_independent_overlap_coverage",
                    "clause_alignment_required": False,
                    "overlap_threshold": "strictly_greater_than_zero_characters",
                    "modality_policy": "evidence_span_extraction_only_label_ignored",
                    "fields": ["modality", "actor", "action", "condition", "constraint", "exception"],
                    "config_sha256": sha256_file(EVALUATOR_CONFIG_PATH),
                    "source_sha256": sha256_file(EVALUATOR_SOURCE_PATH),
                    "gold_builder_source_sha256": sha256_file(GOLD_BUILDER_SOURCE_PATH),
                    "strict_diagnostics_not_primary": True,
                },
                "comparable": {
                    "value": True,
                    "basis": [
                        "same canonical Gold object built once from 56d2b03 Layer E and evaluated for both attempt sets in one process",
                        "same dataset_id / method_id / evaluator version for both sides",
                        "C3 attempts are the tracked registered artifact whose raw SHA-256 matches its own manifest",
                        "v10a attempts are the original baseline run's artifact, locally ignored and unversioned; residual provenance caveat documented above",
                    ],
                },
                "delta": {
                    "basis": "c3_minus_v10a",
                    "overall": delta["overall"],
                    "per_field": delta["per_field"],
                    "old_clause_aligned_hungarian_diagnostic_not_used": True,
                },
                "run_command": {
                    "argv": list(sys.argv),
                    "executable": sys.executable,
                },
                "safety": {
                    "gold": "audit_read_only",
                    "llm_api": "not_called",
                    "artifacts": "created_no_overwrite",
                    "network": "not_called",
                    "existing_attempts": "read_only",
                    "gold_bytes_in_outputs": False,
                },
                "artifacts": {},
            }
            for name, path in (
                ("v10a_metrics", v10a_metrics_path),
                ("c3_metrics", c3_metrics_path),
                ("delta", delta_path),
            ):
                manifest["artifacts"][name] = {
                    "path": path.name,
                    "sha256": sha256_file(path),
                }
            _write_json(manifest_path, manifest)
            staging.rename(output_dir)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    print(
        json.dumps(
            {
                "run_id": manifest["run_id"],
                "output_dir": str(output_dir),
                "canonical_gold_semantic_sha256": manifest["gold"]["canonical_gold_semantic_sha256"],
                "v10a_overall": v10a_metrics["overall"],
                "c3_overall": c3_metrics["overall"],
                "delta_overall": delta["overall"],
                "artifacts": manifest["artifacts"],
                "formal": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-commit", default=SOURCE_COMMIT)
    args = parser.parse_args()
    try:
        return run(args.output_dir, args.source_commit)
    except (ReevaluationError, Estg150B0DevelopmentError, OSError, KeyError, TypeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"B0-R1-E2 re-evaluation failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
