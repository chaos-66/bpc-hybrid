"""B0-R1-ERR: offline failure-type analysis of B0 predictions vs historical Gold.

Reads the historical 56d2b03 Gold-equivalent (Layer E + membership) via raw
``git show`` bytes into a temporary directory and classifies every Gold span
and every predicted span of the registered C3 attempts into failure types:

- matched quality (exact / containment / partial / one-character overlap);
- missed Gold spans: content exists in another field vs no overlap at all;
- extra predictions: overlaps Gold of another field vs no Gold overlap;
- modality evidence-matched clause label panel (4-class confusion);
- clause-planning diagnostic (Gold clause matched by IoU>=0.5, missed spans in
  unmatched clauses);
- actor lexicon coverage for missed actor spans.

Read-only; writes nothing to disk (stdout JSON only). Development analysis,
not a performance result.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.estg150_b0_development import build_canonical_gold_records  # noqa: E402
from bpc_hybrid.stage2_sun_literal_overlap import FIELDS  # noqa: E402

DEFAULT_ATTEMPTS = (
    ROOT
    / "outputs/development/s27_estg150_b0_enhanced_v10a_r1a_c3_hist56d_v1"
    / "b0_attempts.json"
)
HISTORICAL_PATHS = {
    "layer_e": "formal_experiment/data/development/human_review/estg_150_human_correction_v1.json",
    "membership": "formal_experiment/data/development/estg/estg_150_membership_hashes.json",
}


def _git(*args: str) -> bytes:
    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.decode("utf-8").strip()
    return subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout


def _span_intersects(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    return max(int(a["start"]), int(b["start"])) < min(int(a["end"]), int(b["end"]))


def _overlap_len(a: Mapping[str, Any], b: Mapping[str, Any]) -> int:
    return max(0, min(int(a["end"]), int(b["end"])) - max(int(a["start"]), int(b["start"])))


def _char_iou(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    inter = _overlap_len(a, b)
    union = (int(a["end"]) - int(a["start"])) + (int(b["end"]) - int(b["start"])) - inter
    return inter / union if union else 0.0


def clause_spans(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [clause["clause_span"] for clause in record.get("clauses") or []]


def all_field_spans(record: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    out: list[tuple[str, Mapping[str, Any]]] = []
    plural = {
        "actor": "actors",
        "action": "actions",
        "condition": "conditions",
        "constraint": "constraints",
        "exception": "exceptions",
    }
    for clause in record.get("clauses") or []:
        for field in FIELDS:
            if field == "modality":
                values = (clause.get("modality") or {}).get("evidence") or []
            else:
                values = clause.get(plural[field]) or []
            for span in values:
                out.append((field, span))
    return out


def classify_field(
    gold_spans: Sequence[Mapping[str, Any]],
    pred_spans: Sequence[Mapping[str, Any]],
    gold_other: Sequence[Mapping[str, Any]],
    pred_other: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    matched_gold = [g for g in gold_spans if any(_span_intersects(g, p) for p in pred_spans)]
    missed = [g for g in gold_spans if g not in matched_gold]
    matched_pred = [p for p in pred_spans if any(_span_intersects(p, g) for g in gold_spans)]
    extra = [p for p in pred_spans if p not in matched_pred]

    missed_other = [g for g in missed if any(_span_intersects(g, p) for p in pred_other)]
    missed_absent = [g for g in missed if g not in missed_other]
    extra_other = [p for p in extra if any(_span_intersects(p, g) for g in gold_other)]
    extra_none = [p for p in extra if p not in extra_other]

    quality = Counter({"exact": 0, "containment": 0, "partial": 0})
    one_char = 0
    for g in matched_gold:
        pairs = [(p, _overlap_len(g, p)) for p in pred_spans if _span_intersects(g, p)]
        if not pairs:
            continue
        p, best = max(pairs, key=lambda item: item[1])
        glen = int(g["end"]) - int(g["start"])
        plen = int(p["end"]) - int(p["start"])
        if g["start"] == p["start"] and g["end"] == p["end"]:
            quality["exact"] += 1
        elif best == min(glen, plen):
            quality["containment"] += 1
        else:
            quality["partial"] += 1
        if best == 1:
            one_char += 1

    return {
        "gold": len(gold_spans),
        "pred": len(pred_spans),
        "matched_gold": len(matched_gold),
        "missed": len(missed),
        "matched_pred": len(matched_pred),
        "misclassified": len(extra),
        "missed_subtypes": {
            "content_in_other_field": len(missed_other),
            "no_overlap": len(missed_absent),
        },
        "misclassified_subtypes": {
            "overlaps_other_field_gold": len(extra_other),
            "no_gold_overlap": len(extra_none),
        },
        "matched_quality": dict(quality),
        "matched_one_char_overlap": one_char,
    }


def modality_label_panel(
    gold: Mapping[str, Any], pred: Mapping[str, Any]
) -> dict[str, Any]:
    matched_pairs: list[tuple[str, str]] = []
    gold_clauses = gold.get("clauses") or []
    pred_clauses = pred.get("clauses") or []
    for g_clause in gold_clauses:
        g_ev = (g_clause.get("modality") or {}).get("evidence") or []
        for p_clause in pred_clauses:
            p_ev = (p_clause.get("modality") or {}).get("evidence") or []
            hit = any(_span_intersects(g, p) for g in g_ev for p in p_ev)
            if hit:
                matched_pairs.append(
                    ((g_clause.get("modality") or {}).get("label"),
                     (p_clause.get("modality") or {}).get("label"))
                )
                break
    labels = ("definition", "obligation", "permission", "prohibition")
    confusion: dict[str, dict[str, int]] = {g: {p: 0 for p in labels} for g in labels}
    correct = 0
    for g_label, p_label in matched_pairs:
        g_key = g_label if g_label in labels else "other"
        p_key = p_label if p_label in labels else "other"
        confusion.setdefault(g_key, {}).setdefault(p_key, 0)
        confusion[g_key][p_key] += 1
        if g_label == p_label and g_label in labels:
            correct += 1
    return {
        "evidence_matched_clauses": len(matched_pairs),
        "label_accuracy_matched": (correct / len(matched_pairs)) if matched_pairs else 0.0,
        "confusion": confusion,
    }


def clause_planning_diagnostic(
    gold: Mapping[str, Any], pred: Mapping[str, Any]
) -> dict[str, Any]:
    g_clauses = clause_spans(gold)
    p_clauses = clause_spans(pred)
    matched_gold_clauses = 0
    unmatched_gold_idx: set[int] = set()
    for gi, gc in enumerate(g_clauses):
        best = max((_char_iou(gc, pc) for pc in p_clauses), default=0.0)
        if best >= 0.5:
            matched_gold_clauses += 1
        else:
            unmatched_gold_idx.add(gi)
    return {
        "gold_clauses": len(g_clauses),
        "pred_clauses": len(p_clauses),
        "gold_clauses_matched_iou05": matched_gold_clauses,
        "gold_clauses_unmatched": len(unmatched_gold_idx),
        "unmatched_gold_clause_indexes": sorted(unmatched_gold_idx),
    }


def analyze(
    gold_records: Sequence[Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    attempts_by_id = {a["sample_id"]: a for a in attempts}
    per_field: dict[str, dict[str, Any]] = {
        field: {
            "gold": 0, "pred": 0, "matched_gold": 0, "missed": 0,
            "matched_pred": 0, "misclassified": 0,
            "missed_subtypes": {"content_in_other_field": 0, "no_overlap": 0},
            "misclassified_subtypes": {"overlaps_other_field_gold": 0, "no_gold_overlap": 0},
            "matched_quality": {"exact": 0, "containment": 0, "partial": 0},
            "matched_one_char_overlap": 0,
        }
        for field in FIELDS
    }
    per_sample_errors: dict[str, int] = {}
    modality_panels: list[dict[str, Any]] = []
    clause_diags: list[dict[str, Any]] = []
    actor_missed_spans: list[tuple[int, Mapping[str, Any]]] = []
    for row in gold_records:
        sample_id = row["sample_id"]
        attempt = attempts_by_id[sample_id]
        pred_record = attempt.get("record") or {}
        if attempt.get("request_status") != "ok" or not isinstance(pred_record, Mapping):
            pred_record = {"clauses": []}
        fielded_gold = all_field_spans(row)
        fielded_pred = all_field_spans(pred_record)
        for field in FIELDS:
            gold_spans = [s for f, s in fielded_gold if f == field]
            pred_spans = [s for f, s in fielded_pred if f == field]
            gold_other = [s for f, s in fielded_gold if f != field]
            pred_other = [s for f, s in fielded_pred if f != field]
            out = classify_field(gold_spans, pred_spans, gold_other, pred_other)
            for key, value in out.items():
                if key in ("missed_subtypes", "misclassified_subtypes", "matched_quality"):
                    for sub, count in value.items():
                        per_field[field][key][sub] += count
                elif key == "matched_one_char_overlap":
                    per_field[field][key] += value
                else:
                    per_field[field][key] += value
            if field == "actor":
                for g in gold_spans:
                    if not any(_span_intersects(g, p) for p in pred_spans):
                        actor_missed_spans.append((sample_id, g))
        sample_missed = 0
        sample_extra = 0
        for field in FIELDS:
            gold_spans = [s for f, s in fielded_gold if f == field]
            pred_spans = [s for f, s in fielded_pred if f == field]
            sample_missed += sum(
                1
                for g in gold_spans
                if not any(_span_intersects(g, p) for p in pred_spans)
            )
            sample_extra += sum(
                1
                for p in pred_spans
                if not any(_span_intersects(p, g) for g in gold_spans)
            )
        per_sample_errors[sample_id] = sample_missed + sample_extra
        modality_panels.append(modality_label_panel(row, pred_record))
        clause_diags.append(clause_planning_diagnostic(row, pred_record))

    label_total = sum(p["evidence_matched_clauses"] for p in modality_panels)
    label_correct = sum(
        int(round(p["label_accuracy_matched"] * p["evidence_matched_clauses"]))
        for p in modality_panels
    )
    confusion: dict[str, dict[str, int]] = {}
    for panel in modality_panels:
        for g_label, row_map in panel["confusion"].items():
            confusion.setdefault(g_label, {})
            for p_label, count in row_map.items():
                confusion[g_label][p_label] = (
                    confusion[g_label].get(p_label, 0) + count
                )

    total_gold_clauses = sum(d["gold_clauses"] for d in clause_diags)
    total_matched_clauses = sum(d["gold_clauses_matched_iou05"] for d in clause_diags)
    total_unmatched = sum(d["gold_clauses_unmatched"] for d in clause_diags)

    worst = sorted(per_sample_errors.items(), key=lambda item: -item[1])[:10]
    return {
        "per_field": per_field,
        "totals": {
            field: {
                "gold": per_field[field]["gold"],
                "pred": per_field[field]["pred"],
                "missed": per_field[field]["missed"],
                "misclassified": per_field[field]["misclassified"],
            }
            for field in FIELDS
        },
        "modality_label_panel": {
            "evidence_matched_clauses": label_total,
            "label_accuracy_matched": (label_correct / label_total) if label_total else 0.0,
            "confusion": confusion,
        },
        "clause_planning": {
            "gold_clauses": total_gold_clauses,
            "gold_clauses_matched_iou05": total_matched_clauses,
            "gold_clauses_unmatched": total_unmatched,
        },
        "actor_missed_count": len(actor_missed_spans),
        "actor_missed_samples": actor_missed_spans[:5],
        "worst_samples": worst,
        "sample_count": len(gold_records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempts", type=Path, default=DEFAULT_ATTEMPTS)
    parser.add_argument("--source-commit", default="56d2b03")
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(
            prefix=f"b0-err-{os.getpid()}-", dir=ROOT / ".tmp"
        ) as raw_work:
            work = Path(raw_work)
            for key, path in HISTORICAL_PATHS.items():
                (work / key).write_bytes(_git("show", f"{args.source_commit}:{path}"))
            gold, _ = build_canonical_gold_records(work / "layer_e", work / "membership")
        attempts = json.loads(args.attempts.read_bytes().decode("utf-8"))
        report = analyze(gold, attempts)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"B0 error-type analysis failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
