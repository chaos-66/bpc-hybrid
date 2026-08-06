"""Coarse-grain gold experiment (field-level): condition/constraint only.

Purpose (2026-08-06, user-requested attribution experiment):
    Verify whether B0's low P/R on condition/constraint is driven by
    annotation granularity rather than method deficiency.  We build a
    COARSE-GRAIN gold variant by keeping only condition/constraint spans
    whose text contains at least one marker from Sun et al. (2024)
    Table 4's publicly listed marker examples:

      condition : if, in case of, provided that, in the context of,
                  who, whose, which
      constraint: before, after, at least, at most, equal to, greatest,
                  smallest, last of, least of

    The marker standard is taken verbatim from the Sun paper (public
    definition, "initial sets" per the paper), NOT chosen subjectively.
    All other fields (modality/actor/action/exception) are left
    unchanged.  B0-R3 attempts (final method + authorized lexicon) are
    evaluated in the SAME process against the fine-grained gold and the
    coarse-grained variant, so the delta isolates the granularity effect.

    Safeguards: historical Layer E/membership read read-only via
    ``git show 56d2b03``; the coarse gold variant is a NEW artifact
    (never overwrites the original gold); outputs go under
    outputs/development; no LLM/API/network call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
DECLARED_MEMBERSHIP = "e8e6268644cbc9b7ed42bef19f2e2e2432633a306eab9bf009725ef9571785d7"
DATASET_ID = "independently_reconstructed_estg_150_v1"
METHOD_ID = "sun_rule_only"
B0_R3_ATTEMPTS = (
    ROOT
    / "outputs/development/s27_estg150_b0_enhanced_v10a_r2_r3_lex_hist56d_v1"
    / "b0_attempts.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "outputs/development/s27_b0_coarse_gold_cc_v1"

HISTORICAL_PATHS = {
    "layer_e": "formal_experiment/data/development/human_review/estg_150_human_correction_v1.json",
    "membership": "formal_experiment/data/development/estg/estg_150_membership_hashes.json",
}

# Sun et al. (2024) Table 4, "Examples of Markers" (verbatim initial sets).
SUN_TABLE4_MARKERS = {
    "condition": [
        "if", "in case of", "provided that", "in the context of",
        "who", "whose", "which",
    ],
    "constraint": [
        "before", "after", "at least", "at most", "equal to",
        "greatest", "smallest", "last of", "least of",
    ],
}

CONVERGED_FIELDS = ("condition", "constraint")


class CoarseGoldError(ValueError):
    """Raised when the coarse-gold experiment cannot proceed safely."""


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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def semantic_hash_json(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _marker_patterns(field: str) -> list[re.Pattern[str]]:
    return [
        re.compile(rf"\b{re.escape(m)}\b", re.IGNORECASE)
        for m in SUN_TABLE4_MARKERS[field]
    ]


def keep_span_by_sun_markers(text: str, field: str) -> bool:
    """True when *text* contains any Sun Table-4 marker for *field*.

    Word-boundary, case-insensitive matching; multi-word markers are
    matched as phrases (the leading/trailing word boundaries still
    apply).
    """
    if not text:
        return False
    return any(p.search(text) for p in _marker_patterns(field))


def converge_gold_record(
    record: Mapping[str, Any], *, fields: Sequence[str] = CONVERGED_FIELDS
) -> dict[str, Any]:
    """Return a deep copy of *record* with condition/constraint spans
    filtered to Sun-Table-4-marker-containing ones only.

    Raises CoarseGoldError when a span lacks ``text``.
    """
    from copy import deepcopy

    out = deepcopy(record)
    for clause in out.get("clauses", []):
        if not isinstance(clause, Mapping):
            continue
        for field in fields:
            key = f"{field}s" if field != "modality" else "modality"
            items = clause.get(key)
            if items is None:
                continue
            if not isinstance(items, list):
                raise CoarseGoldError(f"field {key!r} is not a list")
            kept = []
            for item in items:
                if not isinstance(item, Mapping) or not isinstance(item.get("text"), str):
                    raise CoarseGoldError(f"{key} span lacks text")
                if keep_span_by_sun_markers(item["text"], field):
                    kept.append(item)
            clause[key] = kept
    return out


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
        raise CoarseGoldError(f"refusing to overwrite: {output_dir}")
    try:
        output_dir.relative_to((ROOT / "outputs/development").resolve())
    except ValueError as exc:
        raise CoarseGoldError(
            "output must remain under outputs/development"
        ) from exc

    commit_sha = git_full_sha(source_commit)
    with tempfile.TemporaryDirectory(
        prefix=f"coarse-gold-{os.getpid()}-", dir=(ROOT / ".tmp")
    ) as raw_work:
        work_dir = Path(raw_work)
        for key, path in HISTORICAL_PATHS.items():
            (work_dir / key).write_bytes(git_show_bytes(source_commit, path))

        gold, _ = build_canonical_gold_records(
            work_dir / "layer_e", work_dir / "membership"
        )
        if len(gold) != 150:
            raise CoarseGoldError("canonical Gold must contain 150 records")
        canonical_membership = membership_sha256(gold)
        if canonical_membership != DECLARED_MEMBERSHIP:
            raise CoarseGoldError("canonical Gold membership hash mismatch")

        coarse = [converge_gold_record(r) for r in gold]

        attempts = json.loads(B0_R3_ATTEMPTS.read_text(encoding="utf-8"))
        if not isinstance(attempts, list) or len(attempts) != 150:
            raise CoarseGoldError("B0-R3 attempts must be a 150-row list")

        fine_metrics = evaluate_sun_literal_overlap(
            gold, attempts, dataset_id=DATASET_ID, method_id=METHOD_ID
        )
        coarse_metrics = evaluate_sun_literal_overlap(
            coarse, attempts, dataset_id=DATASET_ID, method_id=METHOD_ID
        )

        delta: dict[str, Any] = {}
        for scope in ("overall",):
            delta[scope] = {
                k: round(coarse_metrics[scope][k] - fine_metrics[scope][k], 6)
                for k in fine_metrics[scope]
            }
        delta["per_field"] = {
            f: {
                k: round(
                    coarse_metrics["per_field"][f][k] - fine_metrics["per_field"][f][k],
                    6,
                )
                for k in ("precision", "recall", "f1")
            }
            for f in fine_metrics["per_field"]
        }

        fine_counts = count_gold_spans(gold)
        coarse_counts = count_gold_spans(coarse)

        report = {
            "schema_version": "b0_coarse_gold_cc@1.0.0",
            "purpose": (
                "granularity attribution: condition/constraint gold converged "
                "to Sun Table-4 marker-containing spans; B0-R3 evaluated on both "
                "gold variants in one process"
            ),
            "convergence_rule": {
                "source": "Sun et al. (2024) Table 4 'Examples of Markers' (initial sets, verbatim)",
                "fields": list(CONVERGED_FIELDS),
                "markers": SUN_TABLE4_MARKERS,
                "match": "word-boundary, case-insensitive, any-marker",
                "untouched_fields": ["modality", "actor", "action", "exception"],
            },
            "gold": {
                "source_commit": commit_sha,
                "records": 150,
                "fine_spans": fine_counts,
                "coarse_spans": coarse_counts,
                "fine_semantic_sha256": semantic_hash_json(gold),
                "coarse_semantic_sha256": semantic_hash_json(coarse),
            },
            "attempts": {
                "path": str(B0_R3_ATTEMPTS),
                "sha256": sha256_file(B0_R3_ATTEMPTS),
                "method": "b0_final_r3 (r2_r3_lex)",
            },
            "evaluator": {
                "id": "sun_literal_overlap_evaluation@2.0.0",
                "match_rule": fine_metrics.get("match_rule"),
            },
            "fine_metrics": fine_metrics["overall"],
            "coarse_metrics": coarse_metrics["overall"],
            "per_field_fine": {
                f: {
                    k: fine_metrics["per_field"][f][k]
                    for k in ("precision", "recall", "f1")
                }
                for f in fine_metrics["per_field"]
            },
            "per_field_coarse": {
                f: {
                    k: coarse_metrics["per_field"][f][k]
                    for k in ("precision", "recall", "f1")
                }
                for f in coarse_metrics["per_field"]
            },
            "delta_coarse_minus_fine": delta,
            "interpretation_hint": (
                "A large positive condition/constraint delta supports the "
                "granularity attribution; overall delta is diluted by the four "
                "untouched fields."
            ),
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
        coarse_path = output_dir / "coarse_gold_cc.json"
        with coarse_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(coarse, stream, ensure_ascii=False)
            stream.write("\n")

    print(
        json.dumps(
            {
                "fine_counts": fine_counts,
                "coarse_counts": coarse_counts,
                "fine_overall": fine_metrics["overall"],
                "coarse_overall": coarse_metrics["overall"],
                "delta_overall": delta["overall"],
                "per_field_fine": report["per_field_fine"],
                "per_field_coarse": report["per_field_coarse"],
                "delta_per_field": delta["per_field"],
                "report": str(staging),
                "coarse_gold": str(coarse_path),
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
    except (CoarseGoldError, Estg150B0DevelopmentError, OSError, KeyError, TypeError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"coarse-gold experiment failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
