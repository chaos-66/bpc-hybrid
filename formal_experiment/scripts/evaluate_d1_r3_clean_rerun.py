"""D1-R3: same-process double evaluation of the D1-R1 VERIFY-PASS run and the
D1-R3 fixed-snapshot clean rerun against one canonical Gold object built from
the 56d2b03 historical Layer E, using sun_literal_overlap@2.0.0.

Also computes a failure-type analysis of every missed Gold span:
``wrong_field`` (the content was extracted but landed in another field) vs
``not_extracted`` (no overlapping prediction anywhere in the sample).

The script mirrors the B0-R1-E2 re-evaluation precedent
(``reevaluate_sun_literal_v2_v10a_vs_c3.py``): historical blobs are read via
``git show 56d2b03:<path>`` raw bytes into a temporary directory; no Gold bytes
are persisted in outputs; output files are created with no-overwrite semantics.

No LLM/API call, no network, no Gold modification.  Development-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
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
RUN_DIR = ROOT / "outputs/development/s27_d1_v6_r3_clean_rerun_150_hist56d_v1"
R1_RUN_DIR = ROOT / "outputs/development/s27_d1_v6_verify_pass_150_hist56d_v1"
DEFAULT_OUTPUT = RUN_DIR / "evaluation_d1_r3_20260806.json"
EVALUATOR_CONFIG_PATH = ROOT / "configs/evaluation/sun_table8_literal_overlap_v2.json"
EVALUATOR_SOURCE_PATH = ROOT / "src/bpc_hybrid/stage2_sun_literal_overlap.py"
GOLD_BUILDER_SOURCE_PATH = ROOT / "src/bpc_hybrid/estg150_b0_development.py"
DATASET_ID = "independently_reconstructed_estg_150_v1"
METHOD_ID = "direct_llm"
DECLARED_MEMBERSHIP = "e8e6268644cbc9b7ed42bef19f2e2e2432633a306eab9bf009725ef9571785d7"

HISTORICAL_PATHS = {
    "layer_e": "formal_experiment/data/development/human_review/estg_150_human_correction_v1.json",
    "membership": "formal_experiment/data/development/estg/estg_150_membership_hashes.json",
}

FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")
PLURAL_KEYS = {
    "modality": "modality",
    "actor": "actors",
    "action": "actions",
    "condition": "conditions",
    "constraint": "constraints",
    "exception": "exceptions",
}


class EvaluationError(ValueError):
    """Raised when the D1-R3 evaluation cannot proceed safely."""


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
        raise EvaluationError(f"path {path!r} not present in {commit}")
    parts = line.split()
    if len(parts) < 3 or parts[1] != "blob":
        raise EvaluationError(f"unexpected ls-tree entry for {path!r}: {line!r}")
    return parts[2]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def semantic_hash_json(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_responses_jsonl(path: Path, *, label: str) -> list[dict[str, Any]]:
    """Load d1_responses.jsonl rows (request_status + record envelope)."""
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise EvaluationError(f"{label} line {line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise EvaluationError(f"{label} line {line_number}: not an object")
            rows.append(row)
    if not rows:
        raise EvaluationError(f"{label} is empty")
    return rows


def validate_attempts(
    gold_by_id: dict[str, Any], attempts: Sequence[Mapping[str, Any]], *, label: str
) -> dict[str, Any]:
    attempt_by_id: dict[str, Any] = {}
    for row in attempts:
        sample_id = row.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in attempt_by_id:
            raise EvaluationError(f"{label} sample_ids must be unique non-empty strings")
        attempt_by_id[sample_id] = row
    if set(attempt_by_id) != set(gold_by_id):
        missing = sorted(set(gold_by_id) - set(attempt_by_id))[:5]
        extra = sorted(set(attempt_by_id) - set(gold_by_id))[:5]
        raise EvaluationError(
            f"{label} membership differs from Gold: missing={missing}, extra={extra}"
        )
    return attempt_by_id


def collect_spans(record: Mapping[str, Any], *, field: str) -> list[dict[str, Any]]:
    """Collect (field-label-aware) spans from a canonical record.

    Clause-level spans are flattened; modality uses its evidence list.
    Field names map through PLURAL_KEYS to the canonical clause keys.
    """
    spans: list[dict[str, Any]] = []
    for clause in record.get("clauses", []):
        if not isinstance(clause, Mapping):
            continue
        if field == "modality":
            modality = clause.get("modality") or {}
            for ev in modality.get("evidence", []) or []:
                if isinstance(ev, Mapping) and isinstance(ev.get("start"), int) and isinstance(ev.get("end"), int):
                    spans.append({"start": ev["start"], "end": ev["end"]})
        else:
            for item in clause.get(PLURAL_KEYS[field], []) or []:
                if isinstance(item, Mapping) and isinstance(item.get("start"), int) and isinstance(item.get("end"), int):
                    spans.append({"start": item["start"], "end": item["end"]})
    return spans


def _overlaps(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    return max(0, min(a["end"], b["end"]) - max(a["start"], b["start"])) > 0


def analyze_failures(
    gold_by_id: dict[str, Any], attempts: dict[str, Any]
) -> dict[str, Any]:
    """Classify every unmatched Gold span: wrong_field vs not_extracted.

    A Gold span is matched when any prediction span in the SAME field overlaps
    it (statement level, mirroring the primary evaluator's field semantics).
    Otherwise, if a prediction span in ANOTHER field overlaps it, it counts as
    ``wrong_field`` (content extracted, wrong field); else ``not_extracted``.
    """
    stats: dict[str, Any] = {
        "total_gold_spans": 0,
        "matched": 0,
        "unmatched": 0,
        "wrong_field": 0,
        "not_extracted": 0,
        "by_field": {},
        "sample_examples": [],
    }
    for sample_id, gold_row in gold_by_id.items():
        pred_row = attempts[sample_id]
        record = pred_row.get("record") if isinstance(pred_row, Mapping) else None
        if not isinstance(record, Mapping):
            record = {}
        pred_spans: dict[str, list[dict[str, Any]]] = {
            f: collect_spans(record, field=f) for f in FIELDS
        }
        for field in FIELDS:
            gold_spans = collect_spans(gold_row, field=field)
            if field not in stats["by_field"]:
                stats["by_field"][field] = {
                    "gold_spans": 0,
                    "matched": 0,
                    "wrong_field": 0,
                    "not_extracted": 0,
                }
            for gs in gold_spans:
                stats["total_gold_spans"] += 1
                stats["by_field"][field]["gold_spans"] += 1
                if any(_overlaps(gs, ps) for ps in pred_spans[field]):
                    stats["matched"] += 1
                    stats["by_field"][field]["matched"] += 1
                    continue
                stats["unmatched"] += 1
                landed: list[str] = []
                for other in FIELDS:
                    if other == field:
                        continue
                    if any(_overlaps(gs, ps) for ps in pred_spans[other]):
                        landed.append(other)
                if landed:
                    stats["wrong_field"] += 1
                    stats["by_field"][field]["wrong_field"] += 1
                else:
                    stats["not_extracted"] += 1
                    stats["by_field"][field]["not_extracted"] += 1
                if len(stats["sample_examples"]) < 10:
                    stats["sample_examples"].append(
                        {
                            "sample_id": sample_id,
                            "field": field,
                            "start": gs["start"],
                            "end": gs["end"],
                            "landed_in": landed or None,
                        }
                    )
    return stats


def run(output_path: Path, source_commit: str) -> int:
    output_path = output_path.resolve()
    if output_path.exists():
        raise EvaluationError(f"refusing to overwrite: {output_path}")
    try:
        output_path.relative_to((ROOT / "outputs/development").resolve())
    except ValueError as exc:
        raise EvaluationError(
            "evaluation output must remain under outputs/development"
        ) from exc

    commit_sha = git_full_sha(source_commit)
    temp_root = ROOT / ".tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    provenance: dict[str, Any] = {
        "source_commit": commit_sha,
        "source_commit_ref": source_commit,
        "git_blobs": {},
    }
    with __import__("tempfile").TemporaryDirectory(
        prefix=f"d1-r3-eval-{os.getpid()}-", dir=temp_root
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

        gold, source_records = build_canonical_gold_records(
            work_dir / "layer_e", work_dir / "membership"
        )
        gold_by_id = {row["sample_id"]: row for row in gold}
        if len(gold) != 150 or len(gold_by_id) != 150:
            raise EvaluationError("canonical Gold must contain 150 unique sample_ids")
        canonical_membership = membership_sha256(gold)
        if canonical_membership != DECLARED_MEMBERSHIP:
            raise EvaluationError(
                "canonical Gold membership hash mismatch: "
                f"got {canonical_membership}, expected {DECLARED_MEMBERSHIP}"
            )

        r1_predictions = load_responses_jsonl(
            R1_RUN_DIR / "d1_responses.jsonl", label="R1 responses"
        )
        r3_predictions = load_responses_jsonl(
            RUN_DIR / "d1_responses.jsonl", label="R3 responses"
        )
        validate_attempts(gold_by_id, r1_predictions, label="R1")
        validate_attempts(gold_by_id, r3_predictions, label="R3")
        r1_by_id = {row["sample_id"]: row for row in r1_predictions}
        r3_by_id = {row["sample_id"]: row for row in r3_predictions}

        r1_metrics = evaluate_sun_literal_overlap(
            gold, r1_predictions, dataset_id=DATASET_ID, method_id=METHOD_ID
        )
        r3_metrics = evaluate_sun_literal_overlap(
            gold, r3_predictions, dataset_id=DATASET_ID, method_id=METHOD_ID
        )

        delta: dict[str, Any] = {}
        for scope in ("overall",):
            delta[scope] = {
                k: round(r3_metrics[scope][k] - r1_metrics[scope][k], 6)
                for k in r1_metrics[scope]
            }
        delta["per_field_f1"] = {
            f: round(r3_metrics["per_field"][f]["f1"] - r1_metrics["per_field"][f]["f1"], 6)
            for f in FIELDS
        }
        delta["basis"] = "r3_minus_r1"

        failure_r1 = analyze_failures(gold_by_id, r1_by_id)
        failure_r3 = analyze_failures(gold_by_id, r3_by_id)

        evaluator_config = json.loads(EVALUATOR_CONFIG_PATH.read_text(encoding="utf-8"))
        if (
            evaluator_config.get("evaluator_id") != "sun_table8_literal_overlap_v2"
            or evaluator_config.get("evaluation_unit") != "statement"
            or evaluator_config.get("clause_alignment_required") is not False
            or evaluator_config.get("assignment") != "none_independent_overlap_coverage"
        ):
            raise EvaluationError("Sun literal-overlap primary evaluator identity changed")

        report = {
            "schema_version": "d1_r3_clean_rerun_evaluation@1.0.0",
            "run_date_utc": "2026-08-06",
            "pipeline_task": "D1-R3 (fixed-snapshot clean rerun, 150 calls, locked recipe)",
            "gold": {
                "source_commit": "56d2b03",
                "dataset_id": DATASET_ID,
                "records": 150,
                "build": "build_canonical_gold_records(layer_e@56d2b03, membership@56d2b03)",
                "canonical_gold_semantic_sha256": semantic_hash_json(gold),
                "canonical_membership_sha256": canonical_membership,
            },
            "evaluator": {
                "id": "sun_literal_overlap_evaluation@2.0.0",
                "config_sha256": sha256_file(EVALUATOR_CONFIG_PATH),
                "source_sha256": sha256_file(EVALUATOR_SOURCE_PATH),
                "gold_builder_source_sha256": sha256_file(GOLD_BUILDER_SOURCE_PATH),
                "match_rule": r3_metrics.get("match_rule"),
            },
            "runs": {
                "r1_verify_pass": {
                    "run_id": "s27_d1_v6_verify_pass_150_hist56d_v1",
                    "output_sha256": sha256_file(R1_RUN_DIR / "output.jsonl"),
                    "responses_sha256": sha256_file(R1_RUN_DIR / "d1_responses.jsonl"),
                    "manifest_sha256": sha256_file(R1_RUN_DIR / "manifest.json"),
                    "metrics": r1_metrics["overall"],
                    "per_field": {
                        f: {k: r1_metrics["per_field"][f][k] for k in ("precision", "recall", "f1")}
                        for f in FIELDS
                    },
                },
                "r3_clean_rerun": {
                    "run_id": "s27_d1_v6_r3_clean_rerun_150_hist56d_v1",
                    "output_sha256": sha256_file(RUN_DIR / "output.jsonl"),
                    "responses_sha256": sha256_file(RUN_DIR / "d1_responses.jsonl"),
                    "manifest_sha256": sha256_file(RUN_DIR / "manifest.json"),
                    "metrics": r3_metrics["overall"],
                    "per_field": {
                        f: {k: r3_metrics["per_field"][f][k] for k in ("precision", "recall", "f1")}
                        for f in FIELDS
                    },
                },
            },
            "delta_r3_minus_r1": delta,
            "failure_analysis": {
                "r1": failure_r1,
                "r3": failure_r3,
                "note": (
                    "wrong_field = Gold span unmatched in its own field but overlapped "
                    "by a prediction span in another field; not_extracted = no overlapping "
                    "prediction anywhere in the sample"
                ),
            },
            "provenance": provenance,
            "safety": {
                "gold": "audit_read_only",
                "llm_api": "not_called",
                "network": "not_called",
                "artifacts": "created_no_overwrite",
                "gold_bytes_in_outputs": False,
            },
            "claim_scope": "development_only_not_formal",
        }
        staging = output_path.parent / f".{output_path.name}.staging-{os.getpid()}"
        if staging.exists():
            raise EvaluationError(f"staging path already exists: {staging}")
        with staging.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        staging.rename(output_path)

    print(
        json.dumps(
            {
                "output": str(output_path),
                "r1_overall": r1_metrics["overall"],
                "r3_overall": r3_metrics["overall"],
                "delta": delta,
                "failure_r3": {k: v for k, v in failure_r3.items() if k != "sample_examples"},
                "formal": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-commit", default=SOURCE_COMMIT)
    args = parser.parse_args()
    try:
        return run(args.output, args.source_commit)
    except (EvaluationError, Estg150B0DevelopmentError, OSError, KeyError, TypeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"D1-R3 evaluation failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
