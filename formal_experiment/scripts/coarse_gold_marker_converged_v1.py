"""Experiment B: coarse Gold + Sun Table-4 marker convergence (double relaxation).

Purpose (2026-08-08, user-requested "relax what we can" experiment):
    The primary metric is already the sentence-level coarse Gold (609 spans,
    sha 6e19cf3c).  On TOP of that relaxation, this experiment additionally
    converges the condition/constraint fields to Sun et al. (2024) Table 4's
    publicly listed marker examples (word-boundary, case-insensitive),
    i.e. the same definition-scope convergence that was previously run on the
    FINE gold (s27_b0_coarse_gold_cc_v1) - now on the COARSE gold.  This
    measures how much of the residual P/R gap is definition-scope-driven on
    the current primary metric.

    Marker standard (verbatim from the Sun paper, "initial sets" per the
    paper, NOT chosen subjectively):
      condition : if, in case of, provided that, in the context of,
                  who, whose, which
      constraint: before, after, at least, at most, equal to, greatest,
                  smallest, last of, least of

    Design notes (same discipline as s27_b0_coarse_gold_cc_v1):
      - one-sided convergence: only the Gold is converged, predictions are
        NOT; P-side is therefore NOT interpretable (wide predictions all
        count as FP against the small converged Gold).  Only R-side
        conclusions are supported, and this is documented below.
      - both B0-R3 and D1-R3 fixed snapshots are evaluated on the same
        coarse+marker-converged Gold in one process.

    Safeguards: historical Layer E/membership read read-only via
    ``git show 56d2b03``; coarse Gold reconstructed with the same rule as
    coarse_gold_b0_sentence_granularity_v1.py (semantic sha256 asserted
    equal to 6e19cf3c); predictions fixed; outputs under outputs/development;
    no LLM/API/network call.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
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
from scripts.coarse_gold_b0_sentence_granularity_v1 import (  # noqa: E402
    coarse_gold_record,
)
from scripts.coarse_gold_b0_condition_constraint_v1 import (  # noqa: E402
    converge_gold_record,
)

SOURCE_COMMIT = "56d2b03"
DECLARED_MEMBERSHIP = "e8e6268644cbc9b7ed42bef19f2e2e2432633a306eab9bf009725ef9571785d7"
EXPECTED_COARSE_SEMANTIC_SHA256 = "6e19cf3c684a26aa9e9fdc9f76c3529b5a4232aecb085fad4c206ceb177bcb26"
DATASET_ID = "independently_reconstructed_estg_150_v1"
B0_R3_ATTEMPTS = (
    ROOT
    / "outputs/development/s27_estg150_b0_enhanced_v10a_r2_r3_lex_hist56d_v1"
    / "b0_attempts.json"
)
D1_R3_RESPONSES = (
    ROOT
    / "outputs/development/s27_d1_v6_r3_clean_rerun_150_hist56d_v1"
    / "d1_responses.jsonl"
)
DEFAULT_OUTPUT_DIR = ROOT / "outputs/development/s27_coarse_gold_marker_converged_v1"

HISTORICAL_PATHS = {
    "layer_e": "formal_experiment/data/development/human_review/estg_150_human_correction_v1.json",
    "membership": "formal_experiment/data/development/estg/estg_150_membership_hashes.json",
}


class MarkerConvergeError(ValueError):
    """Raised when the experiment cannot proceed safely."""


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


def git_show_bytes(commit: str, path: str) -> bytes:
    return _git("show", f"{commit}:{path}").stdout


def git_full_sha(commit: str) -> str:
    return _git("rev-parse", commit).stdout.decode("ascii").strip()


def semantic_hash_json(value: Any) -> str:
    import hashlib

    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_responses_jsonl(path: Path, *, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise MarkerConvergeError(f"{label} line {line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise MarkerConvergeError(f"{label} line {line_number}: not an object")
            rows.append(row)
    if not rows:
        raise MarkerConvergeError(f"{label} is empty")
    return rows


def count_gold_spans(gold: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {f: 0 for f in ("modality", "actor", "action", "condition", "constraint", "exception")}
    for record in gold:
        for clause in record.get("clauses", []):
            if not isinstance(clause, Mapping):
                continue
            for field in counts:
                if field == "modality":
                    counts[field] += len((clause.get("modality") or {}).get("evidence", []) or [])
                else:
                    counts[field] += len(clause.get(f"{field}s", []) or [])
    return counts


def run(output_dir: Path, source_commit: str) -> int:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise MarkerConvergeError(f"refusing to overwrite: {output_dir}")
    try:
        output_dir.relative_to((ROOT / "outputs/development").resolve())
    except ValueError as exc:
        raise MarkerConvergeError(
            "output must remain under outputs/development"
        ) from exc

    commit_sha = git_full_sha(source_commit)
    with tempfile.TemporaryDirectory(
        prefix=f"marker-converge-{os.getpid()}-", dir=(ROOT / ".tmp")
    ) as raw_work:
        work_dir = Path(raw_work)
        for key, path in HISTORICAL_PATHS.items():
            (work_dir / key).write_bytes(git_show_bytes(source_commit, path))

        gold, _ = build_canonical_gold_records(
            work_dir / "layer_e", work_dir / "membership"
        )
        if len(gold) != 150:
            raise MarkerConvergeError("canonical Gold must contain 150 records")
        canonical_membership = membership_sha256(gold)
        if canonical_membership != DECLARED_MEMBERSHIP:
            raise MarkerConvergeError("canonical Gold membership hash mismatch")

        coarse = [coarse_gold_record(r) for r in gold]
        coarse_semantic = semantic_hash_json(coarse)
        if coarse_semantic != EXPECTED_COARSE_SEMANTIC_SHA256:
            raise MarkerConvergeError(
                "coarse Gold semantic sha256 mismatch vs registered 6e19cf3c: "
                f"{coarse_semantic}"
            )
        converged = [converge_gold_record(r) for r in coarse]

        attempts = json.loads(B0_R3_ATTEMPTS.read_text(encoding="utf-8"))
        if not isinstance(attempts, list) or len(attempts) != 150:
            raise MarkerConvergeError("B0-R3 attempts must be a 150-row list")
        responses = load_responses_jsonl(D1_R3_RESPONSES, label="D1-R3 responses")
        if len(responses) != 150:
            raise MarkerConvergeError("D1-R3 responses must be 150 rows")
        non_ok = [r for r in responses if r.get("request_status") != "ok"]
        if non_ok:
            raise MarkerConvergeError(f"D1-R3 has {len(non_ok)} non-ok responses")

        def evaluate_pair(gold_target: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
            return {
                "b0": evaluate_sun_literal_overlap(
                    gold_target, attempts, dataset_id=DATASET_ID, method_id="sun_rule_only"
                )["overall"],
                "d1": evaluate_sun_literal_overlap(
                    gold_target, responses, dataset_id=DATASET_ID, method_id="direct_llm"
                )["overall"],
            }

        coarse_metrics = evaluate_pair(coarse)
        converged_metrics = evaluate_pair(converged)

        def per_field_of(
            gold_target: Sequence[Mapping[str, Any]], predictions: Sequence[Mapping[str, Any]], method_id: str
        ) -> dict[str, dict[str, float]]:
            raw = evaluate_sun_literal_overlap(
                gold_target, predictions, dataset_id=DATASET_ID, method_id=method_id
            )
            out: dict[str, dict[str, float]] = {}
            for f in ("modality", "actor", "action", "condition", "constraint", "exception"):
                out[f] = {
                    k: raw["per_field"][f][k]
                    for k in ("precision", "recall", "f1")
                }
            return out

        report = {
            "schema_version": "coarse_gold_marker_converged@1.0.0",
            "purpose": (
                "Attribution (double relaxation): sentence-level coarse Gold "
                "(primary metric) + Sun Table-4 marker convergence on "
                "condition/constraint only; predictions untouched; one-sided "
                "convergence - P-side NOT interpretable, only R-side "
                "conclusions are supported (same discipline as "
                "s27_b0_coarse_gold_cc_v1)"
            ),
            "marker_standard": {
                "source": "Sun et al. (2024) Table 4 'Examples of Markers' (verbatim initial sets)",
                "condition": ["if", "in case of", "provided that", "in the context of", "who", "whose", "which"],
                "constraint": ["before", "after", "at least", "at most", "equal to", "greatest", "smallest", "last of", "least of"],
                "matching": "word-boundary, case-insensitive, on span text",
                "disclosure": "Table 4 is the paper's 'initial sets'; 13 constraint spans is a LOWER BOUND of Sun's definition scope",
            },
            "gold": {
                "source_commit": commit_sha,
                "records": 150,
                "coarse_semantic_sha256": coarse_semantic,
                "coarse_spans": count_gold_spans(coarse),
                "coarse_total": sum(count_gold_spans(coarse).values()),
                "converged_spans": count_gold_spans(converged),
                "converged_total": sum(count_gold_spans(converged).values()),
            },
            "predictions": {
                "b0": {"path": str(B0_R3_ATTEMPTS), "sha256": sha256_file(B0_R3_ATTEMPTS)},
                "d1": {"path": str(D1_R3_RESPONSES), "sha256": sha256_file(D1_R3_RESPONSES)},
            },
            "evaluator": {
                "id": "sun_literal_overlap_evaluation@2.0.0",
                "match_rule": "independent_same_field_any_nonempty_character_span_intersection",
            },
            "coarse_metrics": coarse_metrics,
            "converged_metrics": converged_metrics,
            "per_field_coarse": {
                "b0": per_field_of(coarse, attempts, "sun_rule_only"),
                "d1": per_field_of(coarse, responses, "direct_llm"),
            },
            "per_field_converged": {
                "b0": per_field_of(converged, attempts, "sun_rule_only"),
                "d1": per_field_of(converged, responses, "direct_llm"),
            },
            "safety": {
                "gold": "audit_read_only",
                "llm_api": "not_called",
                "network": "not_called",
                "original_gold_modified": False,
                "artifacts": "created_no_overwrite",
            },
        }

        output_dir.mkdir(parents=True)
        staging = output_dir / "report.json"
        with staging.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")

    print(
        json.dumps(
            {
                "coarse_total": sum(count_gold_spans(coarse).values()),
                "converged_total": sum(count_gold_spans(converged).values()),
                "coarse_overall": coarse_metrics,
                "converged_overall": converged_metrics,
                "report": str(staging),
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
    except (MarkerConvergeError, Estg150B0DevelopmentError, OSError, KeyError, TypeError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"marker-convergence experiment failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
