"""Experiment A: Sun sentence-selection criteria subset re-evaluation.

Purpose (2026-08-08, user-requested "relax what we can" experiment):
    Sun et al. (2024) selected their 150 sentences with criteria stated in
    the paper (line 730-731): "The selected sentences were typically
    complete, sequential, comprised a legal act, and were longer than 20
    words."  Our 150-sentence set is a historical fixed collection that was
    NOT filtered with these criteria.  This experiment measures, on top of
    the sentence-level coarse Gold (primary metric, sha 6e19cf3c), what
    B0-R3 / D1-R3 P/R/F1 become when evaluation is restricted to the subset
    of sentences that satisfy each Sun criterion (and their intersection).

    Criteria are operationalized as objectively as possible:
      - >20 words : English token count (whitespace split) > 20
      - complete  : sentence ends with a terminal punctuation mark
                    (. ? ! ; or a trailing ')') after stripping whitespace
      - legal act : sentence contains at least one modal-verb / legal-act
                    surface cue (shall/may/must/can/will/be entitled/be
                    obliged/be required/be deemed/has to/have to/not allowed/
                    is prohibited), a documented heuristic proxy
      - sequential: NOT applied (our collection has no usable source order)
    "typically" in the paper is respected: criteria are reported one by one
    AND as the full intersection, never as a hard requirement on the set.

    Safeguards: historical Layer E/membership read read-only via
    ``git show 56d2b03``; the coarse Gold variant is reconstructed with the
    same rule as ``coarse_gold_b0_sentence_granularity_v1.py`` (semantic
    sha256 asserted equal to 6e19cf3c); predictions are FIXED (B0-R3
    attempts / D1-R3 responses); nothing is written under data/, no LLM/
    API/network call; outputs go under outputs/development.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
DEFAULT_OUTPUT_DIR = ROOT / "outputs/development/s27_sun_selection_criteria_v1"

HISTORICAL_PATHS = {
    "layer_e": "formal_experiment/data/development/human_review/estg_150_human_correction_v1.json",
    "membership": "formal_experiment/data/development/estg/estg_150_membership_hashes.json",
}

# Sun et al. (2024) line 730-731 verbatim selection criteria.
SUN_SELECTION_CRITERIA_QUOTE = (
    "The selected sentences were typically complete, sequential, comprised "
    "a legal act, and were longer than 20 words."
)

TERMINAL_END = re.compile(r"[.?!;)]\s*$")
LEGAL_ACT_SURFACES = re.compile(
    r"\b(shall|may|must|can|will|has to|have to|not allowed|is prohibited|is forbidden)\b"
    r"|\b(is|are|be|was|were|been|being)\s+(obliged|required|entitled|deemed|authorized|permitted)\b",
    re.IGNORECASE,
)


class SunSelectionError(ValueError):
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
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib_sha256(payload)


def hashlib_sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def criterion_word_count(text: str) -> int:
    return len(text.split())


def criterion_complete(text: str) -> bool:
    return bool(TERMINAL_END.search(text.rstrip()))


def criterion_legal_act(text: str) -> bool:
    return bool(LEGAL_ACT_SURFACES.search(text))


def apply_criteria(text: str) -> dict[str, bool]:
    return {
        "word_count_gt_20": criterion_word_count(text) > 20,
        "complete": criterion_complete(text),
        "legal_act": criterion_legal_act(text),
    }


def load_responses_jsonl(path: Path, *, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SunSelectionError(f"{label} line {line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise SunSelectionError(f"{label} line {line_number}: not an object")
            rows.append(row)
    if not rows:
        raise SunSelectionError(f"{label} is empty")
    return rows


def subset_metrics(
    gold: Sequence[Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
    sample_ids: set[str],
    *,
    dataset_id: str,
    method_id: str,
) -> dict[str, Any]:
    gold_sub = [r for r in gold if r.get("sample_id") in sample_ids]
    att_sub = [r for r in attempts if r.get("sample_id") in sample_ids]
    return evaluate_sun_literal_overlap(
        gold_sub, att_sub, dataset_id=dataset_id, method_id=method_id
    )


def run(output_dir: Path, source_commit: str) -> int:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise SunSelectionError(f"refusing to overwrite: {output_dir}")
    try:
        output_dir.relative_to((ROOT / "outputs/development").resolve())
    except ValueError as exc:
        raise SunSelectionError(
            "output must remain under outputs/development"
        ) from exc

    commit_sha = git_full_sha(source_commit)
    with tempfile.TemporaryDirectory(
        prefix=f"sun-selection-{os.getpid()}-", dir=(ROOT / ".tmp")
    ) as raw_work:
        work_dir = Path(raw_work)
        for key, path in HISTORICAL_PATHS.items():
            (work_dir / key).write_bytes(git_show_bytes(source_commit, path))

        gold, _ = build_canonical_gold_records(
            work_dir / "layer_e", work_dir / "membership"
        )
        if len(gold) != 150:
            raise SunSelectionError("canonical Gold must contain 150 records")
        canonical_membership = membership_sha256(gold)
        if canonical_membership != DECLARED_MEMBERSHIP:
            raise SunSelectionError("canonical Gold membership hash mismatch")

        coarse = [coarse_gold_record(r) for r in gold]
        coarse_semantic = semantic_hash_json(coarse)
        if coarse_semantic != EXPECTED_COARSE_SEMANTIC_SHA256:
            raise SunSelectionError(
                "coarse Gold semantic sha256 mismatch vs registered 6e19cf3c: "
                f"{coarse_semantic}"
            )

        attempts = json.loads(B0_R3_ATTEMPTS.read_text(encoding="utf-8"))
        if not isinstance(attempts, list) or len(attempts) != 150:
            raise SunSelectionError("B0-R3 attempts must be a 150-row list")
        responses = load_responses_jsonl(D1_R3_RESPONSES, label="D1-R3 responses")
        if len(responses) != 150:
            raise SunSelectionError("D1-R3 responses must be 150 rows")
        non_ok = [r for r in responses if r.get("request_status") != "ok"]
        if non_ok:
            raise SunSelectionError(f"D1-R3 has {len(non_ok)} non-ok responses")

        # Per-record criteria flags (evaluated on the approved English text).
        flags: dict[str, dict[str, bool]] = {}
        for r in gold:
            sid = r.get("sample_id")
            text = r.get("source_text") or ""
            flags[sid] = apply_criteria(text)

        # Criterion subsets (each alone + intersection of all applied ones).
        groups: dict[str, set[str]] = {}
        all_true = [
            sid
            for sid, f in flags.items()
            if f["word_count_gt_20"] and f["complete"] and f["legal_act"]
        ]
        groups["word_count_gt_20"] = {
            sid for sid, f in flags.items() if f["word_count_gt_20"]
        }
        groups["complete"] = {sid for sid, f in flags.items() if f["complete"]}
        groups["legal_act"] = {sid for sid, f in flags.items() if f["legal_act"]}
        groups["all_three"] = set(all_true)

        # Sequential criterion: documented as NOT applied (no usable source
        # order in the historical collection).
        groups["sequential"] = set(flags)

        results: dict[str, Any] = {}
        for name, subset in groups.items():
            b0 = subset_metrics(
                coarse, attempts, subset, dataset_id=DATASET_ID, method_id="sun_rule_only"
            )["overall"]
            d1 = subset_metrics(
                coarse, responses, subset, dataset_id=DATASET_ID, method_id="direct_llm"
            )["overall"]
            results[name] = {
                "n_records": len(subset),
                "sample_ids": sorted(subset),
                "b0": b0,
                "d1": d1,
            }

        per_record_flags = [
            {"sample_id": sid, **f} for sid, f in sorted(flags.items())
        ]

        report = {
            "schema_version": "sun_selection_criteria@1.0.0",
            "purpose": (
                "Attribution: restrict evaluation to the Sun-selection-criteria "
                "subsets on top of the sentence-level coarse Gold (primary "
                "metric, sha 6e19cf3c); predictions untouched"
            ),
            "sun_criteria_quote": SUN_SELECTION_CRITERIA_QUOTE,
            "criteria_operationalization": {
                "word_count_gt_20": "English whitespace token count > 20 (proxy; Sun counted words on the German original)",
                "complete": "ends with terminal punctuation . ? ! ; or ')' (proxy)",
                "legal_act": "contains modal/legal-act surface cue (documented heuristic proxy; Sun used human judgment)",
                "sequential": "NOT applied - historical collection has no usable source order",
                "typically_note": "The paper says 'typically'; each criterion is reported alone AND as full intersection, never as a hard set requirement",
            },
            "gold": {
                "source_commit": commit_sha,
                "records": 150,
                "coarse_semantic_sha256": coarse_semantic,
                "fine_semantic_sha256": semantic_hash_json(gold),
            },
            "predictions": {
                "b0": {"path": str(B0_R3_ATTEMPTS), "sha256": sha256_file(B0_R3_ATTEMPTS)},
                "d1": {"path": str(D1_R3_RESPONSES), "sha256": sha256_file(D1_R3_RESPONSES)},
            },
            "evaluator": {
                "id": "sun_literal_overlap_evaluation@2.0.0",
                "match_rule": "independent_same_field_any_nonempty_character_span_intersection",
            },
            "baseline_all_150": {
                "b0": subset_metrics(
                    coarse, attempts, set(flags), dataset_id=DATASET_ID, method_id="sun_rule_only"
                )["overall"],
                "d1": subset_metrics(
                    coarse, responses, set(flags), dataset_id=DATASET_ID, method_id="direct_llm"
                )["overall"],
            },
            "subsets": results,
            "per_record_flags": per_record_flags,
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
                "baseline_all_150": report["baseline_all_150"],
                "subsets_summary": {
                    name: {
                        "n": v["n_records"],
                        "b0_f1": v["b0"]["f1"],
                        "d1_f1": v["d1"]["f1"],
                    }
                    for name, v in results.items()
                },
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
    except (SunSelectionError, Estg150B0DevelopmentError, OSError, KeyError, TypeError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"sun-selection experiment failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
