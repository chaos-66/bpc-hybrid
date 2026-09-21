# -*- coding: utf-8 -*-
"""Post-execution targeted analysis for SEP-C3 definition refinement.

This script performs no API calls and does not modify Gold, prompts, parser,
canonicalizer, evaluator, or predictions.  It reads the frozen panel, Gold,
historical A predictions, and recovered BASE/R_DEF canonical predictions.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SCRIPTS, SRC):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import analyze_sep_c3_definition_adjudication_v1 as adj  # noqa: E402
import postprocess_sep_c3_definition_targeted_refinement_v1 as pp  # noqa: E402

SUITE_ID = "SEP-C3-DEFINITION-TARGETED-REFINEMENT-001"
ARMS = ("A", "BASE", "R_DEF")
PANEL_PATH = ROOT / "configs" / "sep_c3_definition_targeted_panel_v1.json"
GOLD_PATH = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
TARGETED_DIR = ROOT / "outputs" / "development" / "sep_c3_definition_targeted_refinement_v1"
HISTORICAL_A = (
    ROOT / "outputs" / "development" / "sep_c3_targeted_refinement_v1"
    / "A" / "repeat-01" / "canonical_predictions.jsonl"
)
REPORT_JSON = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_refinement_v1_analysis.json"
)
REPORT_MD = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_refinement_v1_analysis.md"
)
SHALL_RE = re.compile(r"\bshall\b", re.IGNORECASE)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _load_panel_selected() -> dict[tuple[str, str], dict[str, Any]]:
    panel = _read_json(PANEL_PATH)
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for row in panel["selected_clauses"]:
        key = (str(row["sample_id"]), str(row["clause_id"]))
        if key not in selected:
            selected[key] = {
                "sample_id": key[0],
                "clause_id": key[1],
                "modality": str(row["modality"]),
                "text": str(row["text"]),
                "slices": set(),
            }
        selected[key]["slices"].update(str(value) for value in row.get("slices") or [])
    return selected


def _gold_clause_index(gold_doc: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    out: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in gold_doc["records"]:
        for clause in record.get("clauses") or []:
            out[(str(record["sample_id"]), str(clause["clause_id"]))] = clause
    return out


def _load_arm_predictions(panel_ids: set[str]) -> dict[str, dict[str, dict[str, Any]]]:
    arms: dict[str, dict[str, dict[str, Any]]] = {}
    for arm, path in (
        ("A", HISTORICAL_A),
        ("BASE", TARGETED_DIR / "BASE" / "repeat-01" / "canonical_predictions.jsonl"),
        ("R_DEF", TARGETED_DIR / "R_DEF" / "repeat-01" / "canonical_predictions.jsonl"),
    ):
        rows = _read_jsonl(path)
        if arm == "A":
            rows = [row for row in rows if str(row["sample_id"]) in panel_ids]
        arms[arm] = {str(row["sample_id"]): row for row in rows}
    return arms


def _align_all(
    selected: Mapping[tuple[str, str], Mapping[str, Any]],
    gold_clause_by_key: Mapping[tuple[str, str], Mapping[str, Any]],
    arms: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[tuple[str, str], dict[str, Mapping[str, Any]]]:
    aligned: dict[tuple[str, str], dict[str, Mapping[str, Any]]] = {}
    for key in selected:
        gold_clause = gold_clause_by_key[key]
        aligned[key] = {
            arm: adj.align_prediction(
                arms[arm].get(key[0], {}), gold_clause["clause_span"]
            )
            for arm in ARMS
        }
    return aligned


def _label(aligned: Mapping[str, Mapping[str, Any]], key: tuple[str, str], arm: str) -> str | None:
    return aligned[key][arm].get("modality_label")


def _compute_confusions(
    selected: Mapping[tuple[str, str], Mapping[str, Any]],
    aligned: Mapping[tuple[str, str], Mapping[str, Mapping[str, Any]]],
    arm: str,
) -> Counter:
    counter: Counter = Counter()
    for key, row in selected.items():
        gold = row["modality"]
        predicted = _label(aligned, key, arm) or "MISSING"
        counter[(gold, predicted)] += 1
    return counter


def _compute_arm_metrics(
    selected: Mapping[tuple[str, str], Mapping[str, Any]],
    aligned: Mapping[tuple[str, str], Mapping[str, Mapping[str, Any]]],
    arm: str,
) -> dict[str, Any]:
    counter = _compute_confusions(selected, aligned, arm)
    accuracy = sum(
        count for (gold, predicted), count in counter.items() if gold == predicted
    ) / len(selected)
    tp = counter[("definition", "definition")]
    fp = sum(
        count for (gold, predicted), count in counter.items()
        if gold != "definition" and predicted == "definition"
    )
    fn = sum(
        count for (gold, predicted), count in counter.items()
        if gold == "definition" and predicted != "definition"
    )
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    definition_keys = [key for key, row in selected.items() if row["modality"] == "definition"]
    definition_action_present = [
        key for key in definition_keys if aligned[key][arm].get("actions")
    ]
    definition_empty = [key for key in definition_keys if not aligned[key][arm].get("actions")]
    definition_missing = [
        key for key in definition_keys
        if _label(aligned, key, arm) is None
    ]

    b_keys = [key for key, row in selected.items() if "B" in row["slices"]]
    b_false_definition = [
        key for key in b_keys if _label(aligned, key, arm) == "definition"
    ]
    b_breakdown: dict[str, dict[str, Any]] = {}
    for gold_label in ("obligation", "prohibition", "permission"):
        keys = [key for key in b_keys if selected[key]["modality"] == gold_label]
        b_breakdown[gold_label] = {
            "n": len(keys),
            "correct": sum(1 for key in keys if _label(aligned, key, arm) == gold_label),
            "false_definition": sum(
                1 for key in keys if _label(aligned, key, arm) == "definition"
            ),
            "missing": sum(1 for key in keys if _label(aligned, key, arm) is None),
        }

    nondef_shall_keys = [
        key for key, row in selected.items()
        if row["modality"] != "definition" and SHALL_RE.search(row["text"])
    ]
    all_nondef_keys = [
        key for key, row in selected.items() if row["modality"] != "definition"
    ]
    nondef_shall_false_definition = [
        key for key in nondef_shall_keys if _label(aligned, key, arm) == "definition"
    ]
    all_nondef_false_definition = [
        key for key in all_nondef_keys if _label(aligned, key, arm) == "definition"
    ]

    by_slice: dict[str, dict[str, Any]] = {}
    for slice_name in ("A", "B", "C", "D"):
        keys = [key for key, row in selected.items() if slice_name in row["slices"]]
        if not keys:
            continue
        by_slice[slice_name] = {
            "n": len(keys),
            "modality_accuracy": sum(
                1 for key in keys
                if _label(aligned, key, arm) == selected[key]["modality"]
            ) / len(keys),
            "definition_n": sum(
                1 for key in keys if selected[key]["modality"] == "definition"
            ),
            "definition_recall": (
                sum(
                    1 for key in keys
                    if selected[key]["modality"] == "definition"
                    and _label(aligned, key, arm) == "definition"
                )
                / sum(
                    1 for key in keys if selected[key]["modality"] == "definition"
                )
                if any(selected[key]["modality"] == "definition" for key in keys)
                else None
            ),
        }

    return {
        "arm": arm,
        "n_clauses": len(selected),
        "modality_accuracy": accuracy,
        "definition_precision": precision,
        "definition_recall": recall,
        "definition_f1": f1,
        "confusion": {
            f"{gold}->{predicted}": count
            for (gold, predicted), count in sorted(counter.items())
        },
        "definition_to_obligation_count": counter[("definition", "obligation")],
        "obligation_to_definition_count": counter[("obligation", "definition")],
        "prohibition_to_definition_count": counter[("prohibition", "definition")],
        "permission_to_definition_count": counter[("permission", "definition")],
        "definition_action_present_count": len(definition_action_present),
        "definition_empty_action_count": len(definition_empty),
        "definition_action_presence_fraction": (
            len(definition_action_present) / len(definition_keys)
            if definition_keys else None
        ),
        "definition_missing_count": len(definition_missing),
        "definition_empty_action_keys": [list(key) for key in definition_empty],
        "definition_missing_keys": [list(key) for key in definition_missing],
        "b_controls": {
            "n": len(b_keys),
            "modality_accuracy": (
                sum(
                    1 for key in b_keys
                    if _label(aligned, key, arm) == selected[key]["modality"]
                ) / len(b_keys)
                if b_keys else None
            ),
            "false_definition_count": len(b_false_definition),
            "false_definition_rate": (
                len(b_false_definition) / len(b_keys) if b_keys else None
            ),
            "false_definition_keys": [list(key) for key in b_false_definition],
            "per_gold_label": b_breakdown,
        },
        "non_definition_shall": {
            "n": len(nondef_shall_keys),
            "false_definition_count": len(nondef_shall_false_definition),
            "false_definition_rate": (
                len(nondef_shall_false_definition) / len(nondef_shall_keys)
                if nondef_shall_keys else None
            ),
            "false_definition_keys": [list(key) for key in nondef_shall_false_definition],
        },
        "all_non_definition": {
            "n": len(all_nondef_keys),
            "false_definition_count": len(all_nondef_false_definition),
            "false_definition_rate": (
                len(all_nondef_false_definition) / len(all_nondef_keys)
                if all_nondef_keys else None
            ),
            "false_definition_keys": [list(key) for key in all_nondef_false_definition],
        },
        "by_slice": by_slice,
    }


def _compare_arms(
    selected: Mapping[tuple[str, str], Mapping[str, Any]],
    aligned: Mapping[tuple[str, str], Mapping[str, Mapping[str, Any]]],
    from_arm: str,
    to_arm: str,
) -> dict[str, Any]:
    corrected: list[dict[str, Any]] = []
    regressed: list[dict[str, Any]] = []
    for key, row in selected.items():
        gold = row["modality"]
        left = _label(aligned, key, from_arm)
        right = _label(aligned, key, to_arm)
        left_ok = left == gold
        right_ok = right == gold
        case = {
            "sample_id": key[0],
            "clause_id": key[1],
            "gold_modality": gold,
            "from_prediction": left,
            "to_prediction": right,
            "slices": sorted(row["slices"]),
        }
        if not left_ok and right_ok:
            corrected.append(case)
        elif left_ok and not right_ok:
            regressed.append(case)
    return {
        "from": from_arm,
        "to": to_arm,
        "corrected_count": len(corrected),
        "regressed_count": len(regressed),
        "corrected_cases": corrected,
        "regressed_cases": regressed,
    }


def _apply_applies_cases(
    selected: Mapping[tuple[str, str], Mapping[str, Any]],
    aligned: Mapping[tuple[str, str], Mapping[str, Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for key, row in selected.items():
        if "C" not in row["slices"]:
            continue
        case = {
            "sample_id": key[0],
            "clause_id": key[1],
            "gold_modality": row["modality"],
            "text": row["text"],
            "predictions": {},
        }
        for arm in ARMS:
            case["predictions"][arm] = {
                "modality": _label(aligned, key, arm),
                "alignment_quality": aligned[key][arm].get("alignment_quality"),
                "action_count": len(aligned[key][arm].get("actions") or []),
            }
        cases.append(case)
    return cases


def _processing_validity(arm: str, panel_ids: set[str]) -> dict[str, Any]:
    path = TARGETED_DIR / arm / "repeat-01" / "canonical_predictions.jsonl"
    rows = [
        row for row in _read_jsonl(path)
        if str(row["sample_id"]) in panel_ids
    ]
    counts: dict[str, dict[str, int]] = {}
    for field in (
        "request_status",
        "api_call_status",
        "output_parse_status",
        "input_binding_status",
        "canonical_validation_status",
    ):
        counts[field] = dict(Counter(str(row.get(field) or "missing") for row in rows))
    failures = [
        {
            "sample_id": str(row["sample_id"]),
            "failure_stage": row.get("failure_stage"),
            "failure_reason": row.get("failure_reason") or row.get("error"),
        }
        for row in rows
        if row.get("request_status") != "ok"
    ]
    return {
        "sample_count": len(rows),
        "status_counts": counts,
        "failed_samples": failures,
    }


def _transport_diagnostics(panel_ids: set[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm in ("BASE", "R_DEF"):
        raw_path = TARGETED_DIR / arm / "repeat-01" / "raw_responses.jsonl"
        rows = [
            row for row in _read_jsonl(raw_path)
            if str(row["sample_id"]) in panel_ids
        ]
        statuses = Counter(str(row.get("request_status") or "missing") for row in rows)
        errors = [
            {
                "sample_id": str(row["sample_id"]),
                "error": row.get("error"),
                "request_status": row.get("request_status"),
            }
            for row in rows
            if row.get("error")
        ]
        out[arm] = {
            "raw_response_count": len(rows),
            "request_status_counts": dict(statuses),
            "transport_error_count": len(errors),
            "transport_errors": errors,
        }
    return out


def _secondary_panel_slice() -> dict[str, Any]:
    panel = _read_json(PANEL_PATH)
    gold = _read_json(GOLD_PATH)
    panel_ids = {str(value) for value in panel["selected_sample_ids"]}
    panel_gold = {
        "schema_version": gold.get("schema_version"),
        "records": [record for record in gold["records"] if str(record["sample_id"]) in panel_ids],
    }
    arms = _load_arm_predictions(panel_ids)
    out: dict[str, Any] = {}
    for arm in ARMS:
        predictions = [arms[arm][sid] for sid in panel["selected_sample_ids"]]
        evaluation = pp._targeted_panel_slice_evaluation(
            panel_gold, predictions, arm=arm
        )
        out[arm] = {
            "coarse_five_field_mean_f1": evaluation["coarse_five_field_mean_f1"],
            "five_fields": evaluation["five_fields"],
            "coarse_five_field_micro": evaluation["coarse_five_field_micro"],
            "modality_labels": evaluation["modality_labels"],
            "failed_count": evaluation["failed_count"],
            "gold_scope": evaluation["gold_scope"],
        }
    return out


def _render_markdown(result: Mapping[str, Any]) -> str:
    lines: list[str] = [
        "# SEP-C3 Definition Targeted Refinement - Post-Execution Analysis",
        "",
        f"- Suite: `{result['suite_id']}`",
        f"- Scope: {result['scope']}",
        f"- API calls: {result['api_calls']['total']} "
        f"(A={result['api_calls']['A']}, BASE={result['api_calls']['BASE']}, "
        f"R_DEF={result['api_calls']['R_DEF']}); additional calls: 0",
        f"- Transport/provider failures: "
        f"{result['side_effects']['transport_provider_failures_total']}",
        f"- Retry protocol: `{result['retry_protocol']['policy']}`",
        "",
        "## Targeted clause set",
        "",
        f"- Unique clauses: {result['targeted_clause_set']['n_clauses']} "
        f"(definition={result['targeted_clause_set']['modality_counts']['definition']}, "
        f"non-definition={result['targeted_clause_set']['non_definition_count']})",
        f"- Slices: {json.dumps(result['targeted_clause_set']['slice_counts'], ensure_ascii=False)}",
        "",
        "## Arm metrics on the targeted clause set",
        "",
        "| Arm | Modality acc. | Def P | Def R | Def F1 | Def->Obl | Obl->Def | Proh->Def | Perm->Def | Def action present | Empty actions |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        row = result["arm_metrics"][arm]
        lines.append(
            f"| {arm} | {_pct(row['modality_accuracy'])} | "
            f"{_pct(row['definition_precision'])} | "
            f"{_pct(row['definition_recall'])} | "
            f"{_pct(row['definition_f1'])} | "
            f"{row['definition_to_obligation_count']} | "
            f"{row['obligation_to_definition_count']} | "
            f"{row['prohibition_to_definition_count']} | "
            f"{row['permission_to_definition_count']} | "
            f"{row['definition_action_present_count']}/25 "
            f"({_pct(row['definition_action_presence_fraction'])}) | "
            f"{row['definition_empty_action_count']} |"
        )
    lines += [
        "",
        "Note: definition action presence is over the 25 Gold definitions in the",
        "targeted clause set; a failed/missing canonical validation counts as no",
        "action.",
        "",
        "## A -> BASE",
        "",
        f"- Modality accuracy: {_pct(result['comparisons']['A_to_BASE']['arm_metrics']['A']['modality_accuracy'])} -> "
        f"{_pct(result['comparisons']['A_to_BASE']['arm_metrics']['BASE']['modality_accuracy'])}",
        f"- Definition recall: {_pct(result['comparisons']['A_to_BASE']['arm_metrics']['A']['definition_recall'])} -> "
        f"{_pct(result['comparisons']['A_to_BASE']['arm_metrics']['BASE']['definition_recall'])}",
        f"- Definition F1: {_pct(result['comparisons']['A_to_BASE']['arm_metrics']['A']['definition_f1'])} -> "
        f"{_pct(result['comparisons']['A_to_BASE']['arm_metrics']['BASE']['definition_f1'])}",
        f"- Definition->obligation: {result['comparisons']['A_to_BASE']['arm_metrics']['A']['definition_to_obligation_count']} -> "
        f"{result['comparisons']['A_to_BASE']['arm_metrics']['BASE']['definition_to_obligation_count']}",
        f"- Corrected relative to A: {result['comparisons']['A_to_BASE']['corrected_count']}; "
        f"regressed relative to A: {result['comparisons']['A_to_BASE']['regressed_count']}",
        "",
        "### A -> BASE corrected and regressed cases",
        "",
        "| Direction | Sample | Clause | Gold | A | BASE | Slices |",
        "|---|---|---|---|---|---|---|",
    ]
    for case in result["comparisons"]["A_to_BASE"]["corrected_cases"]:
        lines.append(
            f"| corrected | {case['sample_id']} | {case['clause_id']} | "
            f"{case['gold_modality']} | {case['from_prediction']} | "
            f"{case['to_prediction']} | {', '.join(case['slices'])} |"
        )
    for case in result["comparisons"]["A_to_BASE"]["regressed_cases"]:
        lines.append(
            f"| regressed | {case['sample_id']} | {case['clause_id']} | "
            f"{case['gold_modality']} | {case['from_prediction']} | "
            f"{case['to_prediction']} | {', '.join(case['slices'])} |"
        )
    lines += [
        "",
        "## BASE -> R_DEF",
        "",
        f"- Definition recall: {_pct(result['comparisons']['BASE_to_R_DEF']['arm_metrics']['BASE']['definition_recall'])} -> "
        f"{_pct(result['comparisons']['BASE_to_R_DEF']['arm_metrics']['R_DEF']['definition_recall'])}",
        f"- Definition->obligation: {result['comparisons']['BASE_to_R_DEF']['arm_metrics']['BASE']['definition_to_obligation_count']} -> "
        f"{result['comparisons']['BASE_to_R_DEF']['arm_metrics']['R_DEF']['definition_to_obligation_count']}",
        f"- Definition action presence: "
        f"{result['comparisons']['BASE_to_R_DEF']['arm_metrics']['BASE']['definition_action_present_count']}/25 -> "
        f"{result['comparisons']['BASE_to_R_DEF']['arm_metrics']['R_DEF']['definition_action_present_count']}/25",
        f"- B non-definition `shall` false-definition rate: "
        f"{_pct(result['arm_metrics']['BASE']['b_controls']['false_definition_rate'])} -> "
        f"{_pct(result['arm_metrics']['R_DEF']['b_controls']['false_definition_rate'])}",
        f"- All non-definition false-definition rate: "
        f"{_pct(result['arm_metrics']['BASE']['all_non_definition']['false_definition_rate'])} -> "
        f"{_pct(result['arm_metrics']['R_DEF']['all_non_definition']['false_definition_rate'])}",
        f"- Corrected relative to BASE: {result['comparisons']['BASE_to_R_DEF']['corrected_count']}; "
        f"regressed relative to BASE: {result['comparisons']['BASE_to_R_DEF']['regressed_count']}",
        "",
        "### BASE -> R_DEF corrected and regressed cases",
        "",
        "| Direction | Sample | Clause | Gold | BASE | R_DEF | Slices |",
        "|---|---|---|---|---|---|---|",
    ]
    for case in result["comparisons"]["BASE_to_R_DEF"]["corrected_cases"]:
        lines.append(
            f"| corrected | {case['sample_id']} | {case['clause_id']} | "
            f"{case['gold_modality']} | {case['from_prediction']} | "
            f"{case['to_prediction']} | {', '.join(case['slices'])} |"
        )
    for case in result["comparisons"]["BASE_to_R_DEF"]["regressed_cases"]:
        lines.append(
            f"| regressed | {case['sample_id']} | {case['clause_id']} | "
            f"{case['gold_modality']} | {case['from_prediction']} | "
            f"{case['to_prediction']} | {', '.join(case['slices'])} |"
        )
    lines += [
        "",
        "## Non-definition `shall` controls (slice B)",
        "",
        "| Arm | n | Modality accuracy | False definition | Rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        b = result["arm_metrics"][arm]["b_controls"]
        lines.append(
            f"| {arm} | {b['n']} | {_pct(b['modality_accuracy'])} | "
            f"{b['false_definition_count']} | {_pct(b['false_definition_rate'])} |"
        )
    lines += [
        "",
        "## Secondary field diagnostics (frozen evaluator, 42-sample coarse panel slice)",
        "",
        "| Arm | Mean five-field F1 | Micro F1 | Actor F1 | Action F1 | Condition F1 | Constraint F1 | Exception F1 | Sample-label acc. |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        sec = result["side_effects"]["secondary_panel_slice"][arm]
        fields = sec["five_fields"]
        lines.append(
            f"| {arm} | {_pct(sec['coarse_five_field_mean_f1'])} | "
            f"{_pct(sec['coarse_five_field_micro']['f1'])} | "
            f"{_pct(fields['actor'].get('f1'))} | "
            f"{_pct(fields['action'].get('f1'))} | "
            f"{_pct(fields['condition'].get('f1'))} | "
            f"{_pct(fields['constraint'].get('f1'))} | "
            f"{_pct(fields['exception'].get('f1'))} | "
            f"{_pct(sec['modality_labels']['accuracy'])} |"
        )
    lines += [
        "",
        "## Parse / schema validity and transport failures",
        "",
        "| Arm | Request OK | Parse passed | Binding passed | Canonical validation passed | Canonical validation failed |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        v = result["side_effects"]["processing_validity"].get(arm)
        if not v:
            lines.append(f"| {arm} | historical reuse | n/a | n/a | n/a | n/a |")
            continue
        counts = v["status_counts"]
        def _count(field: str, value: str) -> int:
            return int(counts[field].get(value, 0))
        lines.append(
            f"| {arm} | {_count('request_status','ok')} | "
            f"{_count('output_parse_status','passed')} | "
            f"{_count('input_binding_status','passed')} | "
            f"{_count('canonical_validation_status','passed')} | "
            f"{_count('canonical_validation_status','failed')} |"
        )
    lines += [
        "",
        "- Transport/provider failures: "
        f"{result['side_effects']['transport_provider_failures_total']}.",
        f"- Retry policy: `{result['retry_protocol']['policy']}` - "
        f"{result['retry_protocol']['rationale']}",
        "",
        "## `apply/applies` stress cases (descriptive only)",
        "",
        "| Sample | Clause | Gold | A | BASE | R_DEF |",
        "|---|---|---|---|---|---|",
    ]
    for case in result["apply_applies_cases"]:
        lines.append(
            f"| {case['sample_id']} | {case['clause_id']} | {case['gold_modality']} | "
            f"{case['predictions']['A']['modality']} | "
            f"{case['predictions']['BASE']['modality']} | "
            f"{case['predictions']['R_DEF']['modality']} |"
        )
    lines += [
        "",
        "No lexical `apply => definition` rule was introduced or used.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    panel = _read_json(PANEL_PATH)
    gold = _read_json(GOLD_PATH)
    panel_ids = {str(value) for value in panel["selected_sample_ids"]}
    selected = _load_panel_selected()
    gold_clause_by_key = _gold_clause_index(gold)
    arms = _load_arm_predictions(panel_ids)
    aligned = _align_all(selected, gold_clause_by_key, arms)

    arm_metrics = {arm: _compute_arm_metrics(selected, aligned, arm) for arm in ARMS}
    comparisons = {
        "A_to_BASE": _compare_arms(selected, aligned, "A", "BASE"),
        "A_to_R_DEF": _compare_arms(selected, aligned, "A", "R_DEF"),
        "BASE_to_R_DEF": _compare_arms(selected, aligned, "BASE", "R_DEF"),
    }
    for comparison in comparisons.values():
        comparison["arm_metrics"] = {
            comparison["from"]: arm_metrics[comparison["from"]],
            comparison["to"]: arm_metrics[comparison["to"]],
        }

    processing_validity = {
        arm: _processing_validity(arm, panel_ids) for arm in ("BASE", "R_DEF")
    }
    transport = _transport_diagnostics(panel_ids)
    transport_failures_total = sum(
        value["transport_error_count"]
        for value in transport.values()
    )
    secondary_panel_slice = _secondary_panel_slice()
    apply_applies = _apply_applies_cases(selected, aligned)

    result = {
        "schema_version": "sep_c3_definition_targeted_refinement_analysis@1.0.0",
        "suite_id": SUITE_ID,
        "status": "post_execution_analysis_complete",
        "scope": (
            "targeted development diagnostic; not an unbiased estimate of "
            "overall EStG performance"
        ),
        "api_calls": {"A": 0, "BASE": 42, "R_DEF": 42, "total": 84},
        "retry_protocol": {
            "policy": "retry=0, unchanged",
            "attempts_per_scheduled_request": 1,
            "rationale": (
                "Changing the frozen zero-retry runner would require separate "
                "attempt accounting and retryable-status classification; the "
                "real transport redacts HTTP status.  The frozen protocol was "
                "therefore left unchanged, and any infrastructure failures are "
                "reported separately from semantic model failures."
            ),
        },
        "targeted_clause_set": {
            "n_clauses": len(selected),
            "modality_counts": dict(Counter(row["modality"] for row in selected.values())),
            "non_definition_count": sum(
                1 for row in selected.values() if row["modality"] != "definition"
            ),
            "slice_counts": dict(Counter(
                slice_name
                for row in selected.values()
                for slice_name in row["slices"]
            )),
        },
        "arm_metrics": arm_metrics,
        "comparisons": comparisons,
        "side_effects": {
            "transport_provider_failures_total": transport_failures_total,
            "transport": transport,
            "processing_validity": processing_validity,
            "secondary_panel_slice": secondary_panel_slice,
        },
        "apply_applies_cases": apply_applies,
        "interpretation_constraints": [
            "No significance claims are made.",
            "No general improvement claim from this panel alone.",
            "R_DEF is not automatically promoted.",
            "The full-150 confirmation run is not launched.",
        ],
    }

    _write_json(REPORT_JSON, result)
    _write_text(REPORT_MD, _render_markdown(result))
    print(json.dumps({
        "status": result["status"],
        "report_json": str(REPORT_JSON.relative_to(ROOT)).replace("\\", "/"),
        "report_md": str(REPORT_MD.relative_to(ROOT)).replace("\\", "/"),
        "transport_provider_failures": transport_failures_total,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
