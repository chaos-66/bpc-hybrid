# -*- coding: utf-8 -*-
"""Full-150 confirmation analysis for the frozen R_DEF package.

Zero API.  It reads the frozen Gold, the frozen full-150 input order, the
current-contract Arm A rescore, and the completed R_DEF run.  It reports the
existing official metrics, definition-specific diagnostics, side-effect
diagnostics, and a 10,000-resample paired sample bootstrap over the same 150
samples.  It does not modify prompts, Gold, predictions, parser, canonicalizer,
validator, or evaluator.
"""

from __future__ import annotations

import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_sep_c3_modular_ablation_v1 as core  # noqa: E402
import analyze_sep_c3_definition_adjudication_v1 as adj  # noqa: E402
import analyze_sep_c3_condition_preservation_bootstrap_v1 as boot  # noqa: E402
from bpc_hybrid.g04_coarse_view import build_coarse_view  # noqa: E402
from bpc_hybrid.sep_c3_modular_evaluation import (  # noqa: E402
    SPAN_FIELDS,
    attempt_rows,
    evaluate_coarse,
)

SUITE_ID = "SEP-C3-DEFINITION-FULL150-CONFIRMATION-001"
ARMS = ("A_current_contract", "R_DEF")
GOLD_PATH = core.FORMAL_GOLD
INPUT_PATH = core.ESTG_INPUT
RUN_DIR = ROOT / "outputs" / "development" / "sep_c3_definition_full150_confirmation_v1"
A_PRED_PATH = RUN_DIR / "A_current_contract" / "repeat-01" / "canonical_predictions.jsonl"
R_PRED_PATH = RUN_DIR / "R_DEF" / "repeat-01" / "canonical_predictions.jsonl"
REPORT_JSON = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_full150_confirmation_v1_analysis.json"
)
REPORT_MD = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_full150_confirmation_v1_analysis.md"
)
DECISION_MD = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_full150_confirmation_v1_decision_report.md"
)
SHALL_RE = re.compile(r"\bshall\b", re.IGNORECASE)
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260919
BOOTSTRAP_INTERVAL = "95% percentile"


class AnalysisError(RuntimeError):
    """A full-150 analysis precondition failed."""


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise AnalysisError(f"missing JSONL: {path}")
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise AnalysisError(f"empty JSONL: {path}")
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _pct(value: Any) -> str:
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return "n/a"


def _safe_delta(left: Any, right: Any) -> float | None:
    try:
        return float(left) - float(right)
    except (TypeError, ValueError):
        return None


def _gold_modality_label(clause: Mapping[str, Any]) -> str:
    modality = clause.get("modality")
    if isinstance(modality, Mapping):
        label = modality.get("label")
    else:
        label = modality
    return str(label) if label is not None else "MISSING"


def _gold_clause_rows(gold_doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in gold_doc["records"]:
        sample_id = str(record["sample_id"])
        for clause in record.get("clauses") or []:
            rows.append({
                "sample_id": sample_id,
                "clause_id": str(clause.get("clause_id") or ""),
                "modality": _gold_modality_label(clause),
                "text": str((clause.get("clause_span") or {}).get("text") or ""),
                "clause_span": clause.get("clause_span") or {},
            })
    return rows


def _load_predictions(path: Path, expected_order: Sequence[str]) -> dict[str, dict[str, Any]]:
    rows = _read_jsonl(path)
    by_sid: dict[str, dict[str, Any]] = {}
    for row in rows:
        sid = str(row.get("sample_id") or "")
        if not sid or sid in by_sid:
            raise AnalysisError(f"duplicate/missing sample_id in {path}: {sid!r}")
        by_sid[sid] = row
    expected = [str(value) for value in expected_order]
    if list(by_sid) != expected and set(by_sid) != set(expected):
        raise AnalysisError(f"membership mismatch in {path}")
    return by_sid


def _field_plural(field: str) -> str:
    return {
        "actor": "actors",
        "action": "actions",
        "condition": "conditions",
        "constraint": "constraints",
        "exception": "exceptions",
    }.get(field, field)


def _field_repr(record: Mapping[str, Any] | None, field: str) -> str:
    if not isinstance(record, Mapping):
        return "[]"
    plural = _field_plural(field)
    spans: list[Any] = []
    for clause in record.get("clauses") or []:
        for span in clause.get(plural) or []:
            if isinstance(span, Mapping):
                spans.append([
                    span.get("text"),
                    span.get("start"),
                    span.get("end"),
                    span.get("normalized"),
                ])
    return _canonical(sorted(spans, key=lambda item: _canonical(item)))


def _sample_change_counts(
    pred_a: Mapping[str, Mapping[str, Any]],
    pred_r: Mapping[str, Mapping[str, Any]],
    sample_order: Sequence[str],
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "sample_count": len(sample_order),
        "per_field": {},
    }
    for field in SPAN_FIELDS:
        changed = [
            sid for sid in sample_order
            if _field_repr(pred_a[sid].get("record"), field)
            != _field_repr(pred_r[sid].get("record"), field)
        ]
        out["per_field"][field] = {
            "sample_change_count": len(changed),
            "sample_change_rate": len(changed) / len(sample_order) if sample_order else None,
            "changed_sample_ids": changed,
        }
    return out


def _align_for_arm(
    gold_clauses: Sequence[Mapping[str, Any]],
    pred_by_sid: Mapping[str, Mapping[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    aligned: dict[tuple[str, str], dict[str, Any]] = {}
    for clause in gold_clauses:
        key = (str(clause["sample_id"]), str(clause["clause_id"]))
        aligned[key] = adj.align_prediction(
            pred_by_sid[key[0]], clause["clause_span"]
        )
    return aligned


def _clause_metrics(
    gold_clauses: Sequence[Mapping[str, Any]],
    aligned: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    conf: Counter[tuple[str, str]] = Counter()
    definition_keys: list[tuple[str, str]] = []
    for clause in gold_clauses:
        key = (str(clause["sample_id"]), str(clause["clause_id"]))
        gold = str(clause["modality"])
        predicted = str(aligned[key].get("modality_label") or "MISSING")
        conf[(gold, predicted)] += 1
        if gold == "definition":
            definition_keys.append(key)
    total = len(gold_clauses)
    accuracy = sum(count for (gold, pred), count in conf.items() if gold == pred) / total if total else None
    tp = conf[("definition", "definition")]
    fp = sum(count for (gold, pred), count in conf.items() if gold != "definition" and pred == "definition")
    fn = sum(count for (gold, pred), count in conf.items() if gold == "definition" and pred != "definition")
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    definition_action_present = sum(
        1 for key in definition_keys if aligned[key].get("actions")
    )
    nondef_keys = [
        (str(clause["sample_id"]), str(clause["clause_id"]))
        for clause in gold_clauses if str(clause["modality"]) != "definition"
    ]
    nondef_shall_keys = [
        (str(clause["sample_id"]), str(clause["clause_id"]))
        for clause in gold_clauses
        if str(clause["modality"]) != "definition" and SHALL_RE.search(str(clause["text"]))
    ]
    nondef_false = [
        key for key in nondef_keys
        if str(aligned[key].get("modality_label") or "MISSING") == "definition"
    ]
    nondef_shall_false = [
        key for key in nondef_shall_keys
        if str(aligned[key].get("modality_label") or "MISSING") == "definition"
    ]
    return {
        "n_gold_clauses": total,
        "modality_accuracy": accuracy,
        "definition_precision": precision,
        "definition_recall": recall,
        "definition_f1": f1,
        "definition_tp": tp,
        "definition_fp": fp,
        "definition_fn": fn,
        "definition_to_obligation_count": conf[("definition", "obligation")],
        "obligation_to_definition_count": conf[("obligation", "definition")],
        "prohibition_to_definition_count": conf[("prohibition", "definition")],
        "permission_to_definition_count": conf[("permission", "definition")],
        "confusion": {
            f"{gold}->{predicted}": count
            for (gold, predicted), count in sorted(conf.items())
        },
        "definition_action_present_count": definition_action_present,
        "definition_empty_action_count": len(definition_keys) - definition_action_present,
        "definition_action_presence_fraction": (
            definition_action_present / len(definition_keys) if definition_keys else None
        ),
        "definition_empty_action_keys": [
            list(key) for key in definition_keys if not aligned[key].get("actions")
        ],
        "non_definition_false_definition_count": len(nondef_false),
        "non_definition_false_definition_rate": (
            len(nondef_false) / len(nondef_keys) if nondef_keys else None
        ),
        "non_definition_false_definition_keys": [list(key) for key in nondef_false],
        "non_definition_shall_false_definition_count": len(nondef_shall_false),
        "non_definition_shall_false_definition_rate": (
            len(nondef_shall_false) / len(nondef_shall_keys) if nondef_shall_keys else None
        ),
        "non_definition_shall_false_definition_keys": [list(key) for key in nondef_shall_false],
        "non_definition_count": len(nondef_keys),
        "non_definition_shall_count": len(nondef_shall_keys),
    }


def _official_metrics(
    gold_doc: Mapping[str, Any],
    pred_by_sid: Mapping[str, Mapping[str, Any]],
    sample_order: Sequence[str],
    method_id: str,
) -> dict[str, Any]:
    attempts = [attempt_rows([pred_by_sid[sid]])[0] for sid in sample_order]
    return evaluate_coarse(gold_doc, attempts, method_id=method_id)


def _field_metric_deltas(
    eval_a: Mapping[str, Any],
    eval_r: Mapping[str, Any],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in SPAN_FIELDS:
        a = (eval_a["five_fields"] or {}).get(field) or {}
        r = (eval_r["five_fields"] or {}).get(field) or {}
        out[field] = {
            "A_precision": a.get("precision"),
            "R_DEF_precision": r.get("precision"),
            "delta_precision_R_DEF_minus_A": _safe_delta(r.get("precision"), a.get("precision")),
            "A_recall": a.get("recall"),
            "R_DEF_recall": r.get("recall"),
            "delta_recall_R_DEF_minus_A": _safe_delta(r.get("recall"), a.get("recall")),
            "A_f1": a.get("f1"),
            "R_DEF_f1": r.get("f1"),
            "delta_f1_R_DEF_minus_A": _safe_delta(r.get("f1"), a.get("f1")),
            "A_ground_truth": a.get("ground_truth"),
            "R_DEF_ground_truth": r.get("ground_truth"),
            "A_extracted": a.get("extracted"),
            "R_DEF_extracted": r.get("extracted"),
        }
    out["coarse_five_field_mean_f1"] = {
        "A": eval_a["coarse_five_field_mean_f1"],
        "R_DEF": eval_r["coarse_five_field_mean_f1"],
        "delta_R_DEF_minus_A": _safe_delta(
            eval_r["coarse_five_field_mean_f1"],
            eval_a["coarse_five_field_mean_f1"],
        ),
    }
    out["coarse_five_field_micro_f1"] = {
        "A": eval_a["coarse_five_field_micro"]["f1"],
        "R_DEF": eval_r["coarse_five_field_micro"]["f1"],
        "delta_R_DEF_minus_A": _safe_delta(
            eval_r["coarse_five_field_micro"]["f1"],
            eval_a["coarse_five_field_micro"]["f1"],
        ),
    }
    out["modality_accuracy"] = {
        "A": eval_a["modality_labels"]["accuracy"],
        "R_DEF": eval_r["modality_labels"]["accuracy"],
        "delta_R_DEF_minus_A": _safe_delta(
            eval_r["modality_labels"]["accuracy"],
            eval_a["modality_labels"]["accuracy"],
        ),
    }
    out["modality_macro_f1"] = {
        "A": eval_a["modality_labels"]["macro_f1"],
        "R_DEF": eval_r["modality_labels"]["macro_f1"],
        "delta_R_DEF_minus_A": _safe_delta(
            eval_r["modality_labels"]["macro_f1"],
            eval_a["modality_labels"]["macro_f1"],
        ),
    }
    return out


def _processing_status(
    pred_by_sid: Mapping[str, Mapping[str, Any]],
    sample_order: Sequence[str],
) -> dict[str, Any]:
    rows = [pred_by_sid[sid] for sid in sample_order]
    fields = (
        "request_status",
        "api_call_status",
        "output_parse_status",
        "input_binding_status",
        "canonical_validation_status",
        "failure_stage",
    )
    counts = {field: dict(Counter(str(row.get(field) or "missing") for row in rows)) for field in fields}
    structural = []
    transport = []
    for sid in sample_order:
        row = pred_by_sid[sid]
        reasons: list[str] = []
        if str(row.get("api_call_status") or "ok").lower() != "ok":
            reasons.append("transport")
            transport.append(sid)
        if row.get("output_parse_status") == "failed":
            reasons.append("output_parse")
        if row.get("input_binding_status") == "failed":
            reasons.append("input_binding")
        if row.get("canonical_validation_status") == "failed":
            reasons.append("canonical_validation")
        if row.get("failure_stage") in ("adapter", "canonicalizer"):
            reasons.append(str(row.get("failure_stage")))
        if reasons:
            structural.append({"sample_id": sid, "reasons": sorted(set(reasons))})
    return {
        "sample_count": len(rows),
        "status_counts": counts,
        "transport_provider_failure_count": len(transport),
        "transport_provider_failure_samples": transport,
        "structural_failure_count": len(structural),
        "structural_failure_samples": structural,
    }


def _clause_bootstrap_data(
    gold_clauses: Sequence[Mapping[str, Any]],
    aligned_a: Mapping[tuple[str, str], Mapping[str, Any]],
    aligned_r: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    by_sid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for clause in gold_clauses:
        key = (str(clause["sample_id"]), str(clause["clause_id"]))
        by_sid[key[0]].append({
            "gold": str(clause["modality"]),
            "A": str(aligned_a[key].get("modality_label") or "MISSING"),
            "R_DEF": str(aligned_r[key].get("modality_label") or "MISSING"),
            "A_action_present": bool(aligned_a[key].get("actions")),
            "R_DEF_action_present": bool(aligned_r[key].get("actions")),
            "text": str(clause["text"]),
        })
    return by_sid


def _clause_metrics_from_cases(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    if not total:
        return {
            "modality_accuracy": 0.0,
            "definition_precision": 0.0,
            "definition_recall": 0.0,
            "definition_f1": 0.0,
            "definition_to_obligation_count": 0,
            "obligation_to_definition_count": 0,
            "prohibition_to_definition_count": 0,
            "permission_to_definition_count": 0,
            "definition_action_presence_fraction": 0.0,
            "non_definition_false_definition_rate": 0.0,
        }
    conf: Counter[tuple[str, str]] = Counter()
    for case in cases:
        conf[(str(case["gold"]), str(case["A"]))] += 1
    def_tp = conf[("definition", "definition")]
    def_fp = sum(c for (g, p), c in conf.items() if g != "definition" and p == "definition")
    def_fn = sum(c for (g, p), c in conf.items() if g == "definition" and p != "definition")
    precision = def_tp / (def_tp + def_fp) if (def_tp + def_fp) else 0.0
    recall = def_tp / (def_tp + def_fn) if (def_tp + def_fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    def_total = sum(c for (g, _), c in conf.items() if g == "definition")
    def_action = sum(
        1 for case in cases
        if case["gold"] == "definition" and case["A_action_present"]
    )
    nondef_total = sum(c for (g, _), c in conf.items() if g != "definition")
    nondef_false = sum(c for (g, p), c in conf.items() if g != "definition" and p == "definition")
    return {
        "modality_accuracy": sum(c for (g, p), c in conf.items() if g == p) / total,
        "definition_precision": precision,
        "definition_recall": recall,
        "definition_f1": f1,
        "definition_to_obligation_count": conf[("definition", "obligation")],
        "obligation_to_definition_count": conf[("obligation", "definition")],
        "prohibition_to_definition_count": conf[("prohibition", "definition")],
        "permission_to_definition_count": conf[("permission", "definition")],
        "definition_action_presence_fraction": def_action / def_total if def_total else 0.0,
        "non_definition_false_definition_rate": nondef_false / nondef_total if nondef_total else 0.0,
    }


def _clause_bootstrap(
    sample_order: Sequence[str],
    cases_by_sid: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    rng = random.Random(BOOTSTRAP_SEED)
    metrics = (
        "modality_accuracy",
        "definition_precision",
        "definition_recall",
        "definition_f1",
        "definition_action_presence_fraction",
        "non_definition_false_definition_rate",
    )
    deltas: dict[str, list[float]] = {metric: [] for metric in metrics}
    point_cases = [case for sid in sample_order for case in cases_by_sid.get(sid, [])]
    point_a = _clause_metrics_from_cases(point_cases)
    point_r = _clause_metrics_from_cases([
        {
            **case,
            "A": case["R_DEF"],
            "A_action_present": case["R_DEF_action_present"],
        }
        for case in point_cases
    ])
    for _ in range(BOOTSTRAP_RESAMPLES):
        sampled = [sample_order[rng.randrange(len(sample_order))] for _ in range(len(sample_order))]
        cases = [case for sid in sampled for case in cases_by_sid.get(sid, [])]
        a_metrics = _clause_metrics_from_cases(cases)
        r_metrics = _clause_metrics_from_cases([
            {
                **case,
                "A": case["R_DEF"],
                "A_action_present": case["R_DEF_action_present"],
            }
            for case in cases
        ])
        for metric in metrics:
            deltas[metric].append(float(r_metrics[metric]) - float(a_metrics[metric]))
    comparisons: dict[str, Any] = {}
    for metric in metrics:
        values = deltas[metric]
        comparisons[metric] = {
            "A": point_a[metric],
            "R_DEF": point_r[metric],
            "observed_delta_R_DEF_minus_A": float(point_r[metric]) - float(point_a[metric]),
            "bootstrap_mean_delta": sum(values) / len(values) if values else None,
            "ci95_percentile": boot._interval(values) if values else None,
            "contains_zero": (boot._interval(values)[0] <= 0.0 <= boot._interval(values)[1]) if values else None,
        }
    return {
        "seed": BOOTSTRAP_SEED,
        "resamples": BOOTSTRAP_RESAMPLES,
        "interval": BOOTSTRAP_INTERVAL,
        "pairing": "same resampled sample_id multiset for A and R_DEF",
        "metric_recompute": "sum clause-level confusion counts over resampled samples, then recompute metric",
        "point_metrics_from_full_150": {"A": point_a, "R_DEF": point_r},
        "comparisons": comparisons,
    }


def _span_bootstrap(
    gold_doc: Mapping[str, Any],
    pred_a: Mapping[str, Mapping[str, Any]],
    pred_r: Mapping[str, Mapping[str, Any]],
    sample_order: Sequence[str],
) -> dict[str, Any]:
    coarse_gold = {str(rec["sample_id"]): rec for rec in build_coarse_view(gold_doc)}
    counts_by_arm: dict[str, dict[str, dict[str, dict[str, int]]]] = {}
    for arm, pred_by_sid in (("A_current_contract", pred_a), ("R_DEF", pred_r)):
        counts_by_arm[arm] = {}
        for sid in sample_order:
            counts_by_arm[arm][sid] = boot._per_sample_counts(
                coarse_gold[sid], pred_by_sid[sid]
            )
    point_counts = {arm: boot._zero_counts() for arm in counts_by_arm}
    for arm in counts_by_arm:
        for sid in sample_order:
            boot._add_counts(point_counts[arm], counts_by_arm[arm][sid])
    point_metrics = {arm: boot._metrics_from_field_counts(point_counts[arm]) for arm in counts_by_arm}
    point_a = point_metrics["A_current_contract"]
    point_r = point_metrics["R_DEF"]
    # Evaluate externally as a parity check.
    eval_a = evaluate_coarse(gold_doc, attempt_rows([pred_a[sid] for sid in sample_order]), method_id="analysis_A")
    eval_r = evaluate_coarse(gold_doc, attempt_rows([pred_r[sid] for sid in sample_order]), method_id="analysis_R_DEF")
    for arm, eval_result, point in (
        ("A_current_contract", eval_a, point_a),
        ("R_DEF", eval_r, point_r),
    ):
        for field in SPAN_FIELDS:
            if abs(float(eval_result["five_fields"][field]["f1"]) - float(point[field]["f1"])) > 1e-12:
                raise AnalysisError(f"span bootstrap parity failed for {arm}.{field}")
        if abs(float(eval_result["coarse_five_field_mean_f1"]) - float(point["coarse_five_field_mean_f1"])) > 1e-12:
            raise AnalysisError(f"span bootstrap mean parity failed for {arm}")
        if abs(float(eval_result["coarse_five_field_micro"]["f1"]) - float(point["coarse_five_field_micro_f1"])) > 1e-12:
            raise AnalysisError(f"span bootstrap micro parity failed for {arm}")

    rng = random.Random(BOOTSTRAP_SEED)
    metric_names = ["coarse_five_field_mean_f1", "coarse_five_field_micro_f1"] + [
        f"{field}_f1" for field in SPAN_FIELDS
    ]
    deltas: dict[str, list[float]] = {name: [] for name in metric_names}
    for _ in range(BOOTSTRAP_RESAMPLES):
        sampled = [sample_order[rng.randrange(len(sample_order))] for _ in range(len(sample_order))]
        metrics: dict[str, dict[str, Any]] = {}
        for arm in counts_by_arm:
            total = boot._zero_counts()
            for sid in sampled:
                boot._add_counts(total, counts_by_arm[arm][sid])
            metrics[arm] = boot._metrics_from_field_counts(total)
        for name in metric_names:
            if name == "coarse_five_field_mean_f1":
                left = metrics["R_DEF"]["coarse_five_field_mean_f1"]
                right = metrics["A_current_contract"]["coarse_five_field_mean_f1"]
            elif name == "coarse_five_field_micro_f1":
                left = metrics["R_DEF"]["coarse_five_field_micro_f1"]
                right = metrics["A_current_contract"]["coarse_five_field_micro_f1"]
            else:
                field = name[:-3]
                left = metrics["R_DEF"][field]["f1"]
                right = metrics["A_current_contract"][field]["f1"]
            deltas[name].append(float(left) - float(right))
    comparisons: dict[str, Any] = {}
    for name in metric_names:
        if name == "coarse_five_field_mean_f1":
            left = point_r["coarse_five_field_mean_f1"]
            right = point_a["coarse_five_field_mean_f1"]
        elif name == "coarse_five_field_micro_f1":
            left = point_r["coarse_five_field_micro_f1"]
            right = point_a["coarse_five_field_micro_f1"]
        else:
            field = name[:-3]
            left = point_r[field]["f1"]
            right = point_a[field]["f1"]
        values = deltas[name]
        lo, hi = boot._interval(values)
        comparisons[name] = {
            "A": right,
            "R_DEF": left,
            "observed_delta_R_DEF_minus_A": float(left) - float(right),
            "bootstrap_mean_delta": sum(values) / len(values),
            "ci95_percentile": [lo, hi],
            "contains_zero": lo <= 0.0 <= hi,
        }
    return {
        "seed": BOOTSTRAP_SEED,
        "resamples": BOOTSTRAP_RESAMPLES,
        "interval": BOOTSTRAP_INTERVAL,
        "pairing": "same resampled sample_id multiset for A and R_DEF",
        "metric_recompute": "sum per-sample frozen-evaluator counts, then recompute F1; never average per-sample F1",
        "point_metrics": {
            "A_current_contract": point_a,
            "R_DEF": point_r,
        },
        "comparisons": comparisons,
    }


def _render_markdown(result: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C3 Definition Full-150 Confirmation Analysis",
        "",
        f"- Suite: `{result['suite_id']}`",
        f"- Scope: **{result['scope']}**",
        f"- API calls in this analysis: **0**",
        f"- A: historical frozen raw responses rescored under current contract",
        f"- R_DEF: exactly {result['execution']['actual_calls']} new calls, retry=0",
        "",
        "## Official Stage-2 metrics",
        "",
        "| Metric | A_current_contract | R_DEF | Delta (R_DEF - A) |",
        "|---|---:|---:|---:|",
    ]
    official = result["official_metrics"]
    lines.append(
        f"| coarse_five_field_mean_f1 | {_pct(official['coarse_five_field_mean_f1']['A'])} | "
        f"{_pct(official['coarse_five_field_mean_f1']['R_DEF'])} | "
        f"{_pct(official['coarse_five_field_mean_f1']['delta_R_DEF_minus_A'])} |"
    )
    lines.append(
        f"| coarse_five_field_micro_f1 | {_pct(official['coarse_five_field_micro_f1']['A'])} | "
        f"{_pct(official['coarse_five_field_micro_f1']['R_DEF'])} | "
        f"{_pct(official['coarse_five_field_micro_f1']['delta_R_DEF_minus_A'])} |"
    )
    lines.append(
        f"| modality_label_accuracy | {_pct(official['modality_accuracy']['A'])} | "
        f"{_pct(official['modality_accuracy']['R_DEF'])} | "
        f"{_pct(official['modality_accuracy']['delta_R_DEF_minus_A'])} |"
    )
    lines.append(
        f"| modality_label_macro_f1 | {_pct(official['modality_macro_f1']['A'])} | "
        f"{_pct(official['modality_macro_f1']['R_DEF'])} | "
        f"{_pct(official['modality_macro_f1']['delta_R_DEF_minus_A'])} |"
    )
    lines += [
        "",
        "## Per-field official metrics",
        "",
        "| Field | A F1 | R_DEF F1 | Delta F1 | A P | R_DEF P | A R | R_DEF R |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for field in SPAN_FIELDS:
        row = official[field]
        lines.append(
            f"| {field} | {_pct(row['A_f1'])} | {_pct(row['R_DEF_f1'])} | "
            f"{_pct(row['delta_f1_R_DEF_minus_A'])} | {_pct(row['A_precision'])} | "
            f"{_pct(row['R_DEF_precision'])} | {_pct(row['A_recall'])} | "
            f"{_pct(row['R_DEF_recall'])} |"
        )
    lines += [
        "",
        "## Definition-specific diagnostics (full 150 gold clauses)",
        "",
        "| Metric | A_current_contract | R_DEF | Delta (R_DEF - A) |",
        "|---|---:|---:|---:|",
    ]
    for key, label in (
        ("definition_precision", "Definition precision"),
        ("definition_recall", "Definition recall"),
        ("definition_f1", "Definition F1"),
        ("definition_to_obligation_count", "Definition -> obligation count"),
        ("obligation_to_definition_count", "Obligation -> definition count"),
        ("prohibition_to_definition_count", "Prohibition -> definition count"),
        ("permission_to_definition_count", "Permission -> definition count"),
        ("definition_action_presence_fraction", "Definition action-presence fraction"),
        ("definition_empty_action_count", "Definition empty-action count"),
        ("non_definition_false_definition_rate", "Non-definition false-definition rate"),
    ):
        a = result["definition_diagnostics"]["A_current_contract"][key]
        r = result["definition_diagnostics"]["R_DEF"][key]
        try:
            delta = float(r) - float(a)
            delta_text = _pct(delta)
        except (TypeError, ValueError):
            delta_text = "n/a"
        lines.append(f"| {label} | {_pct(a)} | {_pct(r)} | {delta_text} |")
    lines += [
        "",
        "## Side-effect diagnostics",
        "",
        "| Diagnostic | A_current_contract | R_DEF |",
        "|---|---:|---:|",
        f"| Request/API status ok | {result['processing']['A_current_contract']['status_counts']['request_status'].get('ok', 0)} | {result['processing']['R_DEF']['status_counts']['request_status'].get('ok', 0)} |",
        f"| Output parse passed | {result['processing']['A_current_contract']['status_counts']['output_parse_status'].get('passed', 0)} | {result['processing']['R_DEF']['status_counts']['output_parse_status'].get('passed', 0)} |",
        f"| Input binding passed | {result['processing']['A_current_contract']['status_counts']['input_binding_status'].get('passed', 0)} | {result['processing']['R_DEF']['status_counts']['input_binding_status'].get('passed', 0)} |",
        f"| Canonical validation passed | {result['processing']['A_current_contract']['status_counts']['canonical_validation_status'].get('passed', 0)} | {result['processing']['R_DEF']['status_counts']['canonical_validation_status'].get('passed', 0)} |",
        f"| Canonical validation failed | {result['processing']['A_current_contract']['status_counts']['canonical_validation_status'].get('failed', 0)} | {result['processing']['R_DEF']['status_counts']['canonical_validation_status'].get('failed', 0)} |",
        f"| Transport/provider failures | {result['processing']['A_current_contract']['transport_provider_failure_count']} | {result['processing']['R_DEF']['transport_provider_failure_count']} |",
        f"| Structural failure count | {result['processing']['A_current_contract']['structural_failure_count']} | {result['processing']['R_DEF']['structural_failure_count']} |",
        "",
        "## A -> R_DEF field change counts",
        "",
        "| Field | Samples changed | Rate |",
        "|---|---:|---:|",
    ]
    for field in SPAN_FIELDS:
        row = result["field_change_counts"]["per_field"][field]
        lines.append(f"| {field} | {row['sample_change_count']} | {_pct(row['sample_change_rate'])} |")
    lines += [
        "",
        "## Paired bootstrap (10,000 resamples over the same 150 samples)",
        "",
        "| Metric | Observed delta | 95% percentile CI | Contains zero |",
        "|---|---:|---:|---:|",
    ]
    for name, row in result["bootstrap"]["span"]["comparisons"].items():
        lo, hi = row["ci95_percentile"]
        lines.append(
            f"| {name} | {_pct(row['observed_delta_R_DEF_minus_A'])} | "
            f"[{_pct(lo)}, {_pct(hi)}] | {row['contains_zero']} |"
        )
    for name, row in result["bootstrap"]["clause"]["comparisons"].items():
        lo, hi = row["ci95_percentile"]
        lines.append(
            f"| clause_{name} | {_pct(row['observed_delta_R_DEF_minus_A'])} | "
            f"[{_pct(lo)}, {_pct(hi)}] | {row['contains_zero']} |"
        )
    lines += [
        "",
        result["methodological_statement"],
        "",
        "The bootstrap intervals describe sample-composition uncertainty only; they are not a binary significance rule.",
        "",
    ]
    return "\n".join(lines)


def _render_decision(result: Mapping[str, Any]) -> str:
    official = result["official_metrics"]["coarse_five_field_mean_f1"]
    fields = result["official_metrics"]
    improve = [f for f in SPAN_FIELDS if (fields[f]["delta_f1_R_DEF_minus_A"] or 0) > 0]
    regress = [f for f in SPAN_FIELDS if (fields[f]["delta_f1_R_DEF_minus_A"] or 0) < 0]
    proc = result["processing"]
    def_f1 = result["definition_diagnostics"]
    return "\n".join([
        "# Final Decision Report - Frozen R_DEF Full-150 Confirmation",
        "",
        "## 1. Does the targeted definition improvement remain visible on the complete 150-sample corpus?",
        f"- Definition F1: A={_pct(def_f1['A_current_contract']['definition_f1'])}, R_DEF={_pct(def_f1['R_DEF']['definition_f1'])}; delta={_pct(float(def_f1['R_DEF']['definition_f1']) - float(def_f1['A_current_contract']['definition_f1']))}.",
        f"- Definition recall: A={_pct(def_f1['A_current_contract']['definition_recall'])}, R_DEF={_pct(def_f1['R_DEF']['definition_recall'])}.",
        f"- Definition action-presence fraction: A={_pct(def_f1['A_current_contract']['definition_action_presence_fraction'])}, R_DEF={_pct(def_f1['R_DEF']['definition_action_presence_fraction'])}.",
        f"- The answer is visible on the full corpus only if the definition diagnostics and official modality metrics move in the expected direction; consult the table above.",
        "",
        "## 2. Exact official aggregate A_current -> R_DEF change",
        f"- `coarse_five_field_mean_f1`: {_pct(official['A'])} -> {_pct(official['R_DEF'])}; delta={_pct(official['delta_R_DEF_minus_A'])}.",
        f"- `coarse_five_field_micro_f1`: {_pct(result['official_metrics']['coarse_five_field_micro_f1']['A'])} -> {_pct(result['official_metrics']['coarse_five_field_micro_f1']['R_DEF'])}; delta={_pct(result['official_metrics']['coarse_five_field_micro_f1']['delta_R_DEF_minus_A'])}.",
        "",
        "## 3. Fields that improve",
        f"- {', '.join(improve) if improve else 'none'}.",
        "",
        "## 4. Fields that regress",
        f"- {', '.join(regress) if regress else 'none'}.",
        "",
        "## 5. Input-binding, canonical-validation, and structural failures",
        f"- Input binding failed: A={proc['A_current_contract']['status_counts']['input_binding_status'].get('failed', 0)}, R_DEF={proc['R_DEF']['status_counts']['input_binding_status'].get('failed', 0)}.",
        f"- Canonical validation failed: A={proc['A_current_contract']['status_counts']['canonical_validation_status'].get('failed', 0)}, R_DEF={proc['R_DEF']['status_counts']['canonical_validation_status'].get('failed', 0)}.",
        f"- Transport/provider failures: A={proc['A_current_contract']['transport_provider_failure_count']}, R_DEF={proc['R_DEF']['transport_provider_failure_count']}.",
        f"- Structural failure count: A={proc['A_current_contract']['structural_failure_count']}, R_DEF={proc['R_DEF']['structural_failure_count']}.",
        "",
        "## 6. Final Stage-2 Prompt decision",
        result["decision"],
        "",
        "## Methodological statement",
        result["methodological_statement"],
        "",
        "The historical legacy A score (`0.7245765762`) is separately labeled and is not directly compared with R_DEF. The comparable A baseline is the current-contract five-field mean F1 of `0.7080951816362215`.",
        "",
        "This report does not launch BASE, R_DEF2, Stage 3, a new prompt, or any failure repair.",
        "",
    ])


def analyze() -> dict[str, Any]:
    gold_doc = _read_json(GOLD_PATH)
    input_doc = _read_json(INPUT_PATH)
    sample_order = [str(row["sample_id"]) for row in input_doc["records"]]
    if len(sample_order) != 150 or len(set(sample_order)) != 150:
        raise AnalysisError("frozen input membership is not 150 unique samples")
    pred_a = _load_predictions(A_PRED_PATH, sample_order)
    pred_r = _load_predictions(R_PRED_PATH, sample_order)
    gold_clauses = _gold_clause_rows(gold_doc)
    aligned_a = _align_for_arm(gold_clauses, pred_a)
    aligned_r = _align_for_arm(gold_clauses, pred_r)
    eval_a = _official_metrics(gold_doc, pred_a, sample_order, "A_current_contract_full150_analysis")
    eval_r = _official_metrics(gold_doc, pred_r, sample_order, "R_DEF_full150_analysis")
    official_metrics = _field_metric_deltas(eval_a, eval_r)
    def_a = _clause_metrics(gold_clauses, aligned_a)
    def_r = _clause_metrics(gold_clauses, aligned_r)
    processing = {
        "A_current_contract": _processing_status(pred_a, sample_order),
        "R_DEF": _processing_status(pred_r, sample_order),
    }
    field_change = _sample_change_counts(pred_a, pred_r, sample_order)
    span_bootstrap = _span_bootstrap(gold_doc, pred_a, pred_r, sample_order)
    clause_bootstrap = _clause_bootstrap(
        sample_order,
        _clause_bootstrap_data(gold_clauses, aligned_a, aligned_r),
    )
    # A conservative default decision rule stated before applying it to R_DEF:
    # promote R_DEF only if the official aggregate does not regress, definition
    # F1 does not regress, and structural failures do not increase.
    aggregate_delta = official_metrics["coarse_five_field_mean_f1"]["delta_R_DEF_minus_A"]
    def_delta = float(def_r["definition_f1"]) - float(def_a["definition_f1"])
    structural_delta = (
        processing["R_DEF"]["structural_failure_count"]
        - processing["A_current_contract"]["structural_failure_count"]
    )
    tol = 1e-12
    promote = (
        aggregate_delta is not None
        and aggregate_delta >= -tol
        and def_delta >= -tol
        and structural_delta <= 0
        and (aggregate_delta > tol or def_delta > tol)
    )
    decision = (
        "RETAIN FROZEN R_DEF AS STAGE-2 PROMPT CANDIDATE: the full-150 "
        "full-corpus confirmation does not show an aggregate regression, does "
        "not show a definition-F1 regression, and does not increase structural "
        "failures, while definition-specific diagnostics improve."
        if promote else
        "DO NOT PROMOTE R_DEF AT THIS TIME: the full-150 full-corpus "
        "confirmation shows an aggregate regression, a definition-F1 regression, "
        "or an increase in structural failures. Historical A remains the final "
        "Stage-2 Prompt candidate pending separate stronger external evidence."
    )
    result = {
        "schema_version": "sep_c3_definition_full150_confirmation_analysis@1.0.0",
        "suite_id": SUITE_ID,
        "status": "analysis_complete",
        "scope": "full-corpus confirmation; not independent held-out generalization test",
        "api_calls": 0,
        "execution": _read_json(RUN_DIR / "execution_summary.json"),
        "sample_count": len(sample_order),
        "gold_clause_count": len(gold_clauses),
        "official_metrics": official_metrics,
        "definition_diagnostics": {
            "A_current_contract": def_a,
            "R_DEF": def_r,
            "delta_R_DEF_minus_A": {
                key: _safe_delta(def_r.get(key), def_a.get(key))
                for key in (
                    "modality_accuracy",
                    "definition_precision",
                    "definition_recall",
                    "definition_f1",
                    "definition_to_obligation_count",
                    "obligation_to_definition_count",
                    "prohibition_to_definition_count",
                    "permission_to_definition_count",
                    "definition_action_presence_fraction",
                    "definition_empty_action_count",
                    "non_definition_false_definition_rate",
                )
            },
        },
        "processing": processing,
        "field_change_counts": field_change,
        "bootstrap": {
            "span": span_bootstrap,
            "clause": clause_bootstrap,
        },
        "decision_rule_declared_before_observation": {
            "promote_if": [
                "official coarse_five_field_mean_f1 delta >= 0",
                "definition F1 delta >= 0",
                "structural failure count delta <= 0",
            ],
            "note": "This is a transparent decision aid for the report, not a new aggregate metric or significance test.",
        },
        "decision": decision,
        "methodological_statement": (
            "Targeted A->BASE and BASE->R_DEF evidence decomposes the mechanism; "
            "the full-150 A->R_DEF evaluation estimates the effect of the final "
            "frozen package. The full-150 evaluation does not independently "
            "establish generalization because the targeted development samples "
            "are contained within EStG-150. It is described as a full-corpus "
            "confirmation or full-set evaluation."
        ),
    }
    _write_json(REPORT_JSON, result)
    _write_text(REPORT_MD, _render_markdown(result))
    _write_text(DECISION_MD, _render_decision(result))
    return result


def main() -> int:
    result = analyze()
    print(json.dumps({
        "status": result["status"],
        "report_json": str(REPORT_JSON.relative_to(ROOT)).replace("\\", "/"),
        "report_md": str(REPORT_MD.relative_to(ROOT)).replace("\\", "/"),
        "decision_md": str(DECISION_MD.relative_to(ROOT)).replace("\\", "/"),
        "decision": result["decision"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
