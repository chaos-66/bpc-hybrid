"""Coarse-grain gold experiment (sentence-level, full-field merge).

Purpose (2026-08-07, user-requested attribution experiment):
    Sun et al. (2024) annotates at SENTENCE level (~443 phrases across the
    150 sentences, ~2.95 spans/sentence).  Our Gold annotates at CLAUSE
    level (multi-clause sentences split per clause, 1055 spans, ~7.0
    spans/sentence).  The user asks: if we relax OUR annotation granularity
    to approximately Sun's sentence level (one merged span per field per
    sentence, text = the full extent of that field's annotation in the
    sentence), what do B0's P/R look like?

    The merge rule is documented and mechanical, not subjective:
      - every record collapses to a SINGLE synthetic clause covering the
        whole sentence [0, len(approved_text_en));
      - for each of the six fields, all spans annotated anywhere in the
        sentence are merged into ONE span [min(start), max(end)) whose text
        is the approved_text_en slice over that range;
      - a field absent from the sentence keeps no span (empty list), so the
        variant is never padded with fabricated content.

    B0-R3 attempts (final method + authorized lexicon) are evaluated in the
    SAME process against the fine-grained gold and the sentence-level
    variant, so the delta isolates the granularity effect.  The other two
    documented hardness factors of our setting (no sentence filtering: we
    include sentences Sun would exclude; OCR + LLM-translation noise) are
    NOT touched by this variant.

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
DEFAULT_OUTPUT_DIR = ROOT / "outputs/development/s27_b0_coarse_gold_sentence_granularity_v1"

SUN_150_SENTENCE_SPANS = 443  # Sun et al. (2024) Stage 2, 150 sentences

HISTORICAL_PATHS = {
    "layer_e": "formal_experiment/data/development/human_review/estg_150_human_correction_v1.json",
    "membership": "formal_experiment/data/development/estg/estg_150_membership_hashes.json",
}

FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")
PLURAL_KEYS = {
    "actor": "actors",
    "action": "actions",
    "condition": "conditions",
    "constraint": "constraints",
    "exception": "exceptions",
}


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


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _field_spans(record: Mapping[str, Any], field: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for clause in record.get("clauses") or []:
        if not isinstance(clause, Mapping):
            raise CoarseGoldError("clause is not an object")
        if field == "modality":
            modality = clause.get("modality") or {}
            items = modality.get("evidence") or []
        else:
            items = clause.get(PLURAL_KEYS[field]) or []
        for item in items:
            if not isinstance(item, Mapping) or not isinstance(item.get("start"), int) or not isinstance(item.get("end"), int):
                raise CoarseGoldError(f"{field} span lacks integer start/end")
            spans.append(dict(item))
    return spans


def coarse_gold_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Collapse a clause-level canonical record to ONE sentence-level clause
    with at most ONE merged span per field."""
    sample_id = record.get("sample_id")
    source_text = record.get("source_text")
    if not isinstance(sample_id, str) or not isinstance(source_text, str) or not source_text:
        raise CoarseGoldError("record lacks sample_id or source_text")

    merged: dict[str, list[dict[str, Any]]] = {}
    modality_label: str | None = None
    for clause in record.get("clauses") or []:
        label = (clause.get("modality") or {}).get("label")
        if modality_label is None and isinstance(label, str) and label:
            modality_label = label
    for field in FIELDS:
        spans = _field_spans(record, field)
        if not spans:
            merged[field] = []
            continue
        start = min(item["start"] for item in spans)
        end = max(item["end"] for item in spans)
        if not (0 <= start < end <= len(source_text)):
            raise CoarseGoldError(f"{sample_id} {field} merged span outside sentence")
        text = source_text[start:end]
        span: dict[str, Any] = {
            "id": f"{sample_id}_sent_{field}",
            "text": text,
            "start": start,
            "end": end,
        }
        if field != "modality":
            span["normalized"] = _normalized(text)
        merged[field] = [span]

    sentence_clause: dict[str, Any] = {
        "clause_id": f"{sample_id}_sentence",
        "clause_span": {
            "text": source_text,
            "start": 0,
            "end": len(source_text),
        },
        "modality": {
            "label": modality_label,
            "evidence": merged["modality"],
        },
        "actor_action_map": [],
        "order_relations": [],
    }
    for field in ("actor", "action", "condition", "constraint", "exception"):
        sentence_clause[PLURAL_KEYS[field]] = merged[field]

    return {
        "schema_version": record.get("schema_version"),
        "sample_id": sample_id,
        "source_id": record.get("source_id"),
        "source_text": source_text,
        "clauses": [sentence_clause],
        "method": {"name": "coarse_sentence_level_variant", "schema_source": "b0_coarse_gold_sentence@1.0.0"},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
    }


def count_gold_spans(gold: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {f: 0 for f in FIELDS}
    for record in gold:
        for field in FIELDS:
            counts[field] += len(_field_spans(record, field))
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

        coarse = [coarse_gold_record(r) for r in gold]

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
        coarse_total = sum(coarse_counts.values())

        report = {
            "schema_version": "b0_coarse_gold_sentence@1.0.0",
            "purpose": (
                "granularity attribution: clause-level Gold collapsed to "
                "sentence-level (one merged span per field per sentence, "
                "full extent of the field's annotation); B0-R3 evaluated on "
                "both gold variants in one process"
            ),
            "granularity_rule": {
                "source": "Sun et al. (2024) Stage 2 annotates at sentence level (~443 spans/150 sentences); our Gold is clause-level (1055 spans/150 sentences)",
                "rule": (
                    "one synthetic clause per sentence [0,len(approved_text_en)); "
                    "per field: one span [min(start), max(end)) over all annotated spans "
                    "in the sentence; absent fields stay absent; text = approved_text_en slice"
                ),
                "untouched_hardness_factors": [
                    "no sentence filtering (we keep sentences Sun would exclude)",
                    "OCR + LLM-translation noise",
                    "B0-R3 predictions unchanged",
                ],
                "sun_150_sentence_spans_reference": SUN_150_SENTENCE_SPANS,
            },
            "gold": {
                "source_commit": commit_sha,
                "records": 150,
                "fine_spans": fine_counts,
                "coarse_spans": coarse_counts,
                "fine_total": sum(fine_counts.values()),
                "coarse_total": coarse_total,
                "ratio_vs_sun_443": round(coarse_total / SUN_150_SENTENCE_SPANS, 3),
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
                "If B0 P/R both rise substantially at sentence-level granularity, "
                "the clause-level fine annotation is the dominant cost driver of "
                "B0's low P/R in our stricter setting; residual gap vs Sun's own "
                "reported numbers still contains the two untouched hardness "
                "factors (no sentence filtering, OCR+translation noise)."
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
        coarse_path = output_dir / "coarse_gold_sentence_level.json"
        with coarse_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(coarse, stream, ensure_ascii=False)
            stream.write("\n")

    print(
        json.dumps(
            {
                "fine_counts": fine_counts,
                "coarse_counts": coarse_counts,
                "fine_total": sum(fine_counts.values()),
                "coarse_total": coarse_total,
                "ratio_vs_sun_443": round(coarse_total / SUN_150_SENTENCE_SPANS, 3),
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
