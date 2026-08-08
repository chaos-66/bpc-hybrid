"""Experiment C: modality classifier alignment verification vs Sun.

Purpose (2026-08-08, user-requested "relax what we can" experiment; also
the registered TODO-2 from the closure brief and the honest-shortfall item
Q7 in docs/SUPERVISOR_Q_A_PREP_2026-08-06.md):
    Sun et al. (2024) Table 7 (line 708) reports their modality classifier
    (bert-legal-uncased fine-tune) at  P=92.1% / R=94.1% / F1=93.1%.
    We re-trained an independent BERT-TextCNN (S2.4, locked checkpoint
    s24_candidate_B, German, official Sun modality data split) but have
    never measured its P/R/F1 on the official TEST split.  This script loads
    the locked checkpoint through the S2.6 production path
    (LockedBertTextCNNInference) and evaluates it on the official test split
    (426 rows, data/development/modality/sun_estg_modality_v1/splits/
    test.jsonl), reporting per-class and macro P/R/F1 for comparison with
    Sun's 92.1/94.1/93.1.

    NOTE: Sun's Table 7 numbers come from their own train/dev/test protocol
    and their own checkpoint; ours is an independent reconstruction on the
    same official data.  The comparison is C2-level (same public data,
    different model) - directly comparable on the test split we share.

    Safeguards: reads the official split files (read-only) and the locked
    checkpoint via the S2.6 hash-bound loader; no training; no LLM/API/
    network call (Legal-BERT loaded local_files_only); outputs under
    outputs/development.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.sun_style.sun_b0 import (  # noqa: E402
    LockedBertTextCNNInference,
    SunB0CompositionError,
)

S26_CONFIG_PATH = ROOT / "configs/models/sun_b0_s26_candidate_B_v1.json"
TEST_SPLIT_PATH = (
    ROOT
    / "data/development/modality/sun_estg_modality_v1/splits/test.jsonl"
)
DEFAULT_OUTPUT_DIR = ROOT / "outputs/development/s27_modality_classifier_alignment_v1"

SUN_TABLE7 = {"precision": 92.1, "recall": 94.1, "f1": 93.1}

LABELS = ("definition", "obligation", "permission", "prohibition")


class ModalityAlignmentError(ValueError):
    """Raised when the experiment cannot proceed safely."""


def load_test_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ModalityAlignmentError(
                    f"test split line {line_number}: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise ModalityAlignmentError(
                    f"test split line {line_number}: not an object"
                )
            label = row.get("label")
            text = row.get("text")
            if label not in LABELS or not isinstance(text, str) or not text.strip():
                raise ModalityAlignmentError(
                    f"test split line {line_number}: missing label or text"
                )
            rows.append(row)
    if not rows:
        raise ModalityAlignmentError("test split is empty")
    return rows


def confusion_matrix(
    gold_labels: list[str], predicted_labels: list[str]
) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {g: {p: 0 for p in LABELS} for g in LABELS}
    for gold, pred in zip(gold_labels, predicted_labels):
        matrix[gold][pred] += 1
    return matrix


def macro_metrics(
    matrix: dict[str, dict[str, int]]
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    per_class: dict[str, dict[str, float]] = {}
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[g][label] for g in LABELS if g != label)
        fn = sum(matrix[label][p] for p in LABELS if p != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2.0 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1}
    n = len(LABELS)
    macro = {
        "precision": sum(v["precision"] for v in per_class.values()) / n,
        "recall": sum(v["recall"] for v in per_class.values()) / n,
        "f1": sum(v["f1"] for v in per_class.values()) / n,
    }
    return macro, per_class


def run(output_dir: Path) -> int:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise ModalityAlignmentError(f"refusing to overwrite: {output_dir}")
    try:
        output_dir.relative_to((ROOT / "outputs/development").resolve())
    except ValueError as exc:
        raise ModalityAlignmentError(
            "output must remain under outputs/development"
        ) from exc

    rows = load_test_rows(TEST_SPLIT_PATH)
    gold_labels = [row["label"] for row in rows]
    texts = [row["text"] for row in rows]

    with open(S26_CONFIG_PATH, "r", encoding="utf-8") as handle:
        s26_config = json.load(handle)

    try:
        inference = LockedBertTextCNNInference.load(
            ROOT, s26_config, device="cpu"
        )
    except SunB0CompositionError as exc:
        raise ModalityAlignmentError(
            f"locked classifier load failed closed: {exc}"
        ) from exc

    predictions = inference.predict(texts)
    predicted_labels = [p.label for p in predictions]

    matrix = confusion_matrix(gold_labels, predicted_labels)
    macro, per_class = macro_metrics(matrix)

    accuracy = sum(
        1 for g, p in zip(gold_labels, predicted_labels) if g == p
    ) / len(gold_labels)

    report = {
        "schema_version": "modality_classifier_alignment@1.0.0",
        "purpose": (
            "Align verification: locked S2.4 BERT-TextCNN checkpoint on the "
            "official Sun modality TEST split (426 rows) vs Sun Table 7 "
            "(P 92.1 / R 94.1 / F1 93.1).  Independent reconstruction on the "
            "same public data - C2-level comparison."
        ),
        "checkpoint": {
            "config": str(S26_CONFIG_PATH),
            "classifier": "s24_candidate_B (invsqrt weighted, locked via S2.6)",
            "inference_language": "de",
        },
        "test_split": {
            "path": str(TEST_SPLIT_PATH),
            "rows": len(rows),
            "label_distribution": dict(Counter(gold_labels)),
        },
        "sun_table7_reference": SUN_TABLE7,
        "results": {
            "accuracy": accuracy,
            "macro": macro,
            "per_class": per_class,
            "confusion_matrix": matrix,
        },
        "comparison": {
            "delta_precision_pp": round((macro["precision"] * 100) - SUN_TABLE7["precision"], 2),
            "delta_recall_pp": round((macro["recall"] * 100) - SUN_TABLE7["recall"], 2),
            "delta_f1_pp": round((macro["f1"] * 100) - SUN_TABLE7["f1"], 2),
            "interpretation": (
                "C2-level: same public data, independent reconstruction; "
                "direct comparison only on the shared test split; Sun's exact "
                "split protocol may differ (their split is not published in "
                "full detail)"
            ),
        },
        "safety": {
            "gold": "audit_read_only",
            "llm_api": "not_called",
            "network": "not_called",
            "training": "not_called",
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
                "rows": len(rows),
                "accuracy": accuracy,
                "macro": macro,
                "delta_pp": report["comparison"],
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
    args = parser.parse_args()
    try:
        return run(args.output_dir)
    except (ModalityAlignmentError, SunB0CompositionError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"modality alignment experiment failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
