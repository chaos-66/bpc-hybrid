# -*- coding: utf-8 -*-
"""SEP-C2 Stage 2B predecessor baseline: Winter clause regions on EStG-150.

This module implements only the frozen plan in
``configs/sep_c2_stage2b_predecessor_plan_v1.json``:

* run the transcribed Winter et al. (2020) regulation clause parser on the
  frozen EStG-150 English texts;
* preserve the native sentences / obligations / flows output;
* adapt only the native clause region (character envelope of native clause
  tokens) to the explicit common subtask ``estg150_clause_region_detection_v1``;
* reuse the matching historical Rules-Only and Direct-LLM predictions on the
  same input and Gold, ignoring their six-element fields for this metric.

It does not fabricate actor/action/condition/constraint/exception spans,
does not use an LLM, does not read or alter Gold during prediction, and does
not claim Sun's proprietary BPMN Table 12 task.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

FORMAL_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = FORMAL_ROOT.parent

DISPLAY = {
    "winter_2020_native_clause_regions": "Winter et al. (2020) native clause regions",
    "sun_rule_only_historical": "Rules-Only (historical B0 formal arm)",
    "direct_llm_historical": "Direct-LLM (historical D1 formal arm)",
}
UNSUPPORTED = [
    "actor", "action", "condition", "constraint", "exception",
    "modality", "six_element_extraction",
]


class BaselineFail(ValueError):
    """Fail-closed predecessor-baseline error."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    if not path.is_file():
        try:
            shown = path.relative_to(FORMAL_ROOT)
        except ValueError:
            shown = path.relative_to(REPO_ROOT)
        raise BaselineFail(f"missing file: {shown}")
    return json.loads(path.read_text(encoding="utf-8"))


def _binding(rel: str) -> dict[str, Any]:
    path = FORMAL_ROOT / rel
    if not path.is_file():
        raise BaselineFail(f"missing binding: {rel}")
    return {"path": rel, "sha256": sha256(path), "byte_size": path.stat().st_size}


def _require_sha(rel: str, expected: str) -> dict[str, Any]:
    binding = _binding(rel)
    if binding["sha256"] != expected:
        raise BaselineFail(f"frozen hash drift: {rel}")
    return binding


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BaselineFail(message)


def _regions_by_sample(gold_doc: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for record in gold_doc.get("records") or []:
        sample_id = str(record.get("sample_id"))
        regions = []
        for clause in record.get("clauses") or []:
            span = clause.get("clause_span") or {}
            start, end = span.get("start"), span.get("end")
            _require(isinstance(start, int) and isinstance(end, int)
                     and 0 <= start < end,
                     f"{sample_id}: invalid Gold clause_span")
            regions.append({
                "start": start,
                "end": end,
                "text": span.get("text"),
                "clause_id": clause.get("clause_id"),
                "modality": clause.get("modality"),
            })
        out[sample_id] = regions
    return out


def _native_clause_region(text: str, clause: Any) -> dict[str, Any] | None:
    tokens = list(getattr(clause, "clause", []) or [])
    if not tokens:
        return None
    start = min(int(token.idx) for token in tokens)
    end = max(int(token.idx) + len(token.text) for token in tokens)
    _require(0 <= start < end <= len(text),
             f"invalid Winter clause envelope: [{start},{end})")
    return {
        "clause_id": getattr(clause, "_id", None),
        "start": start,
        "end": end,
        "text": text[start:end],
    }


def _surface(tokens: Any) -> str | None:
    if not tokens:
        return None
    return " ".join(token.text for token in tokens)


def winter_native_parse(sample_id: str, text: str, nlp, stopwords: set[str],
                        signalwords: set[str],
                        sequencemarkers: set[str]) -> dict[str, Any]:
    from bpc_hybrid.winter_stage3.winter_clause import parse_regulation_paragraph
    paragraph = parse_regulation_paragraph(
        sample_id, text, nlp, stopwords, signalwords, sequencemarkers,
        only_constraints=True,
    )
    sentences = []
    for sentence in paragraph.sentences:
        sentences.append({
            "sentence_id": getattr(sentence, "_id", None),
            "text": sentence.original.text,
            "start": int(sentence.original.start_char),
            "end": int(sentence.original.end_char),
            "constraint": bool(sentence.constraint),
            "native_clause_ids": [getattr(c, "_id", None) for c in sentence.clauses],
        })
    obligations = []
    for clause in paragraph.obligations:
        region = _native_clause_region(text, clause)
        if region is None:
            continue
        obligations.append({
            **region,
            "lemmatized": clause.lemmatized,
            "subject_surface": _surface(clause.subject),
            "verb_surface": _surface(clause.verb),
            "object_surface": _surface(clause.object),
            "rest_surface": _surface(clause.rest),
        })
    flows = []
    for flow in paragraph.flows or []:
        flows.append({
            "flow_id": getattr(flow, "_id", None),
            "condition_clause_id": getattr(getattr(flow, "condition", None), "_id", None),
            "consequence_clause_id": getattr(getattr(flow, "consequence", None), "_id", None),
            "condition_lemmatized": flow.lemmatize_condition(),
            "consequence_lemmatized": flow.lemmatize_consequence(),
        })
    return {
        "sample_id": sample_id,
        "text_length": len(text),
        "sentences": sentences,
        "obligations": obligations,
        "flows": flows,
        "native_parser": "bpc_hybrid.winter_stage3.winter_clause.parse_regulation_paragraph",
        "native_parameters": {"only_constraints": True},
    }


def adapt_winter_row(native_row: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt native Winter obligations to the frozen clause-region subtask only."""
    return {
        "sample_id": native_row["sample_id"],
        "method_id": "winter_2020_native_clause_regions",
        "task_id": "estg150_clause_region_detection_v1",
        "clause_regions": [
            {"start": row["start"], "end": row["end"],
             "text": row["text"], "native_clause_id": row["clause_id"]}
            for row in native_row.get("obligations") or []
        ],
        "native_sentence_count": len(native_row.get("sentences") or []),
        "constraint_sentence_count": sum(
            1 for row in native_row.get("sentences") or [] if row["constraint"]),
        "native_flow_count": len(native_row.get("flows") or []),
        "action_span_claim": False,
        "unsupported_fields": list(UNSUPPORTED),
        "adaptation_note": ("native obligation clause is mapped only to its own "
                            "character region; it is never treated as an action span"),
    }


def historical_regions(predictions_doc: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in predictions_doc.get("records") or []:
        sample_id = str(row.get("sample_id"))
        regions: list[dict[str, Any]] = []
        if row.get("request_status") == "ok" and isinstance(row.get("record"), dict):
            for clause in row["record"].get("clauses") or []:
                span = clause.get("clause_span") or {}
                start, end = span.get("start"), span.get("end")
                if isinstance(start, int) and isinstance(end, int) and 0 <= start < end:
                    regions.append({
                        "start": start,
                        "end": end,
                        "text": span.get("text"),
                        "clause_id": clause.get("clause_id"),
                    })
        out[sample_id] = regions
    return out


def _intersects(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return max(int(left["start"]), int(right["start"])) < \
        min(int(left["end"]), int(right["end"]))


def _prf(*, ground_truth: int, predicted: int,
         matched_predictions: int, matched_ground_truth: int) -> dict[str, Any]:
    precision = matched_predictions / predicted if predicted else 0.0
    recall = matched_ground_truth / ground_truth if ground_truth else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if precision + recall else 0.0)
    return {
        "ground_truth_regions": ground_truth,
        "predicted_regions": predicted,
        "matched_predictions": matched_predictions,
        "matched_ground_truth": matched_ground_truth,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def evaluate_regions(gold_by_id: Mapping[str, Sequence[Mapping[str, Any]]],
                     predicted_by_id: Mapping[str, Sequence[Mapping[str, Any]]],
                     method_id: str) -> dict[str, Any]:
    _require(set(gold_by_id) == set(predicted_by_id),
             f"{method_id}: prediction sample membership differs from Gold")
    totals = {"ground_truth": 0, "predicted": 0, "matched_predictions": 0,
              "matched_ground_truth": 0}
    per_sample = []
    for sample_id in sorted(gold_by_id):
        gold = list(gold_by_id[sample_id])
        predicted = list(predicted_by_id.get(sample_id) or [])
        matched_predictions = sum(
            any(_intersects(pred, gold_region) for gold_region in gold)
            for pred in predicted)
        matched_ground_truth = sum(
            any(_intersects(gold_region, pred) for pred in predicted)
            for gold_region in gold)
        totals["ground_truth"] += len(gold)
        totals["predicted"] += len(predicted)
        totals["matched_predictions"] += matched_predictions
        totals["matched_ground_truth"] += matched_ground_truth
        sample = {
            "sample_id": sample_id,
            "gold_regions": len(gold),
            "predicted_regions": len(predicted),
            "matched_predictions": matched_predictions,
            "matched_ground_truth": matched_ground_truth,
        }
        sample.update(_prf(
            ground_truth=len(gold), predicted=len(predicted),
            matched_predictions=matched_predictions,
            matched_ground_truth=matched_ground_truth,
        ))
        per_sample.append(sample)
    overall = _prf(
        ground_truth=totals["ground_truth"], predicted=totals["predicted"],
        matched_predictions=totals["matched_predictions"],
        matched_ground_truth=totals["matched_ground_truth"],
    )
    n = len(per_sample)
    macro = {
        key: sum(row[key] for row in per_sample) / n if n else 0.0
        for key in ("precision", "recall", "f1")
    }
    full = [row["sample_id"] for row in per_sample
            if row["gold_regions"] > 0 and row["predicted_regions"] > 0
            and row["matched_ground_truth"] == row["gold_regions"]
            and row["matched_predictions"] == row["predicted_regions"]]
    misses = [row["sample_id"] for row in per_sample
              if row["gold_regions"] > 0 and row["matched_ground_truth"] == 0]
    zero = [row["sample_id"] for row in per_sample
            if row["predicted_regions"] == 0]
    return {
        "method_id": method_id,
        "display_name": DISPLAY.get(method_id, method_id),
        "overall": overall,
        "sample_macro": macro,
        "records": n,
        "records_with_prediction": sum(
            1 for row in per_sample if row["predicted_regions"] > 0),
        "records_with_full_gold_coverage": len(full),
        "records_with_full_region_match": len(full),
        "records_with_at_least_one_match": sum(
            1 for row in per_sample if row["matched_ground_truth"] > 0),
        "records_with_zero_prediction": len(zero),
        "records_with_complete_miss": len(misses),
        "per_sample": per_sample,
        "_full_sample_ids": full,
        "_miss_sample_ids": misses,
        "_zero_sample_ids": zero,
    }


def _examples(per_sample: Sequence[Mapping[str, Any]],
              ids: Sequence[str], limit: int = 3) -> list[dict[str, Any]]:
    by_id = {row["sample_id"]: row for row in per_sample}
    selected = sorted((by_id[sample_id] for sample_id in ids
                       if sample_id in by_id),
                      key=lambda row: (-row["gold_regions"], row["sample_id"]))
    return [dict(row) for row in selected[:limit]]


def _definition_only_samples(gold_by_id: Mapping[str, Sequence[Mapping[str, Any]]]
                             ) -> list[str]:
    return sorted(
        sample_id for sample_id, regions in gold_by_id.items()
        if regions and all(row.get("modality") == "definition" for row in regions)
    )


def audit_reference_packages() -> dict[str, Any]:
    mentor = REPO_ROOT / "references/合规性检查模型代码/model_check"
    winter = REPO_ROOT / "references/winter_2020_model_check/model_check"
    _require(mentor.is_dir() and winter.is_dir(),
             "reference Winter prototype directories missing")
    mentor_files = {
        path.relative_to(mentor).as_posix(): sha256(path)
        for path in mentor.rglob("*") if path.is_file()
    }
    winter_files = {
        path.relative_to(winter).as_posix(): sha256(path)
        for path in winter.rglob("*") if path.is_file()
    }
    common = sorted(set(mentor_files) & set(winter_files))
    mismatches = [rel for rel in common if mentor_files[rel] != winter_files[rel]]
    mentor_only = sorted(set(mentor_files) - set(winter_files))
    winter_only = sorted(set(winter_files) - set(mentor_files))
    cue_hits = []
    for root in (mentor, winter):
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".py", ".java", ".json", ".txt"}:
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if any(cue in text for cue in ("BERT", "TextCNN", "Tregex", "Tsurgeon")):
                    cue_hits.append(path.relative_to(REPO_ROOT).as_posix())
    return {
        "mentor_package_files": len(mentor_files),
        "winter_copy_files": len(winter_files),
        "common_files": len(common),
        "common_file_sha_mismatches": len(mismatches),
        "mentor_only_files": mentor_only,
        "winter_only_files": winter_only,
        "sun_stage2_code_cues_in_either_copy": sorted(set(cue_hits)),
        "conclusion": (
            "The mentor package's model_check subtree is the Winter et al. (2020) "
            "prototype: 112 non- cache files are byte-identical to the separate "
            "Winter copy; only local __pycache__/*.pyc files differ. No Sun "
            "BERT-TextCNN/CoreNLP/Tregex Stage 2 implementation is present. "
            "This run therefore executes the available Winter prototype "
            "transcription, not a misattributed Sun Stage 2 baseline."
        ),
    }


def check_historical_prediction(predictions_doc: Mapping[str, Any],
                                plan_entry: Mapping[str, Any],
                                input_by_id: Mapping[str, Mapping[str, Any]],
                                gold_by_id: Mapping[str, Sequence[Mapping[str, Any]]]
                                ) -> dict[str, Any]:
    rows = predictions_doc.get("records") or []
    _require(len(rows) == 150, f"{plan_entry['arm_id']}: record array != 150")
    ids = [row.get("sample_id") for row in rows]
    _require(len(set(ids)) == 150 and set(ids) == set(input_by_id),
             f"{plan_entry['arm_id']}: sample IDs differ from frozen input")
    text_mismatch = 0
    failures = 0
    for row in rows:
        sample_id = str(row["sample_id"])
        if row.get("request_status") != "ok" or not isinstance(row.get("record"), dict):
            failures += 1
            continue
        if row["record"].get("source_text") != input_by_id[sample_id]["approved_text_en"]:
            text_mismatch += 1
    _require(text_mismatch == 0,
             f"{plan_entry['arm_id']}: source_text differs from frozen input")
    return {
        "arm_id": plan_entry["arm_id"],
        "label": plan_entry["label"],
        "prediction_file": plan_entry["path"],
        "sha256": plan_entry["sha256"],
        "records": len(rows),
        "request_failures_retained": failures,
        "source_text_mismatches": text_mismatch,
        "historical_calls_declared_not_new": True,
    }


def build_report(plan_path: Path, nlp) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = _load_json(plan_path)
    _require(plan.get("schema_version") == "sep_c2_stage2b_predecessor_plan@1.0.0",
             "plan schema drift")
    _require(plan.get("registered_before_any_metric_view") is True,
             "plan is not marked pre-registered before metric view")
    _require(plan["adaptation"]["task_id"] == "estg150_clause_region_detection_v1",
             "task id drift")
    _require(plan["metric"]["metric_id"]
             == "global_statement_any_nonempty_character_intersection",
             "metric id drift")
    _require(plan["execution"]["new_llm_api_calls"] == 0
             and plan["execution"]["new_network_calls"] == 0,
             "zero-API plan drift")

    input_binding = _require_sha(plan["input"]["path"], plan["input"]["sha256"])
    gold_binding = _require_sha(plan["gold"]["path"], plan["gold"]["sha256"])
    input_doc = _load_json(FORMAL_ROOT / plan["input"]["path"])
    gold_doc = _load_json(FORMAL_ROOT / plan["gold"]["path"])
    _require(len(input_doc.get("records") or []) == 150, "input record count drift")
    _require(len(gold_doc.get("records") or []) == 150, "Gold record count drift")
    gold_by_id = _regions_by_sample(gold_doc)
    _require(sum(len(value) for value in gold_by_id.values()) == 231,
             "Gold clause count drift")
    input_by_id = {str(row["sample_id"]): row for row in input_doc["records"]}
    _require(set(input_by_id) == set(gold_by_id),
             "input/Gold sample membership drift")

    historical: dict[str, Any] = {}
    historical_regions_by_method: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for method_id, key in (
        ("sun_rule_only_historical", "sun_rule_only_historical"),
        ("direct_llm_historical", "direct_llm_historical"),
    ):
        entry = plan["historical_predictions"][key]
        _require_sha(entry["path"], entry["sha256"])
        manifest = _load_json(FORMAL_ROOT / entry["manifest_path"])
        _require(manifest.get("method_id") == (
            "sun_rule_only" if method_id == "sun_rule_only_historical" else "direct_llm"),
            f"{method_id}: manifest method_id drift")
        prediction_doc = _load_json(FORMAL_ROOT / entry["path"])
        historical[method_id] = check_historical_prediction(
            prediction_doc, entry, input_by_id, gold_by_id)
        historical[method_id]["manifest"] = _binding(entry["manifest_path"])
        historical_regions_by_method[method_id] = historical_regions(prediction_doc)

    # Winter native output and the single adapted field.
    lexicons = plan["source_audit"]["local_transcription"]
    _require_sha(lexicons["path"], lexicons["sha256"])
    ref_files = REPO_ROOT / "references/winter_2020_model_check/model_check/input/files"
    signalwords = set((ref_files / "signalwords.txt").read_text(encoding="utf-8").splitlines())
    sequencemarkers = set((ref_files / "sequencemarkers.txt").read_text(encoding="utf-8").splitlines())
    stopwords = set((ref_files / "stopwords.txt").read_text(encoding="utf-8").splitlines())
    native_rows: list[dict[str, Any]] = []
    adapted_rows: list[dict[str, Any]] = []
    winter_region_map: dict[str, list[dict[str, Any]]] = {}
    parse_failures: list[dict[str, str]] = []
    for sample_id in sorted(input_by_id):
        text = input_by_id[sample_id]["approved_text_en"]
        try:
            native = winter_native_parse(
                sample_id, text, nlp, stopwords, signalwords, sequencemarkers)
        except Exception as exc:
            parse_failures.append({"sample_id": sample_id,
                                   "error": f"{type(exc).__name__}: {exc}"})
            native = {
                "sample_id": sample_id, "text_length": len(text),
                "sentences": [], "obligations": [], "flows": [],
                "native_parser": "failed",
                "native_parameters": {"only_constraints": True},
            }
        native_rows.append(native)
        adapted = adapt_winter_row(native)
        adapted_rows.append(adapted)
        winter_region_map[sample_id] = adapted["clause_regions"]

    methods = {
        "winter_2020_native_clause_regions": evaluate_regions(
            gold_by_id, winter_region_map, "winter_2020_native_clause_regions"),
        "sun_rule_only_historical": evaluate_regions(
            gold_by_id, historical_regions_by_method["sun_rule_only_historical"],
            "sun_rule_only_historical"),
        "direct_llm_historical": evaluate_regions(
            gold_by_id, historical_regions_by_method["direct_llm_historical"],
            "direct_llm_historical"),
    }
    definition_only = _definition_only_samples(gold_by_id)
    for row in methods["winter_2020_native_clause_regions"]["per_sample"]:
        if row["sample_id"] in definition_only:
            row["gold_definition_only"] = True
    methods["winter_2020_native_clause_regions"]["definition_only_samples"] = len(definition_only)
    methods["winter_2020_native_clause_regions"]["definition_only_zero_prediction"] = sum(
        1 for row in methods["winter_2020_native_clause_regions"]["per_sample"]
        if row["sample_id"] in definition_only and row["predicted_regions"] == 0)

    delta = {}
    base = methods["winter_2020_native_clause_regions"]["overall"]
    for method_id in ("sun_rule_only_historical", "direct_llm_historical"):
        other = methods[method_id]["overall"]
        delta[method_id] = {
            key: round(other[key] - base[key], 6)
            for key in ("precision", "recall", "f1")
        }

    asset_audit = audit_reference_packages()
    report = {
        "schema_version": "sep_c2_stage2b_predecessor_baseline@1.0.0",
        "report_id": "sep_c2_stage2b_predecessor_baseline_v1",
        "status": "completed_zero_api_predecessor_clause_region_run",
        "plan": _binding(str(plan_path.relative_to(FORMAL_ROOT)).replace("\\", "/")),
        "task": {
            "task_id": plan["adaptation"]["task_id"],
            "definition": plan["adaptation"]["task_definition"],
            "metric": plan["metric"],
            "not_claimed": [
                "Sun et al. (2024) Table 12 BPMN violation detection",
                "Winter et al. (2020) BPMN-model matching/fitness/cost on EStG-150",
                "six-element extraction by Winter",
                "action span equivalence of Winter obligation clauses",
            ],
        },
        "bindings": {
            "input": input_binding,
            "gold": gold_binding,
            "local_transcription": {
                "path": lexicons["path"],
                "sha256": lexicons["sha256"],
            },
            "historical_predictions": historical,
        },
        "asset_audit": asset_audit,
        "native_output": {
            "rows": len(native_rows),
            "sentences": sum(len(row["sentences"]) for row in native_rows),
            "constraint_sentences": sum(
                1 for row in native_rows for sent in row["sentences"] if sent["constraint"]),
            "obligations": sum(len(row["obligations"]) for row in native_rows),
            "flows": sum(len(row["flows"]) for row in native_rows),
            "parse_failures": parse_failures,
            "source_component": "src/bpc_hybrid/winter_stage3/winter_clause.py",
            "unsupported_fields": list(UNSUPPORTED),
        },
        "methods": {key: {k: v for k, v in value.items()
                          if not k.startswith("_")}
                    for key, value in methods.items()},
        "comparison": {
            "metric_id": plan["metric"]["metric_id"],
            "winter_minus_historical": delta,
            "interpretation_boundary": plan["comparison_boundary"],
        },
        "cases": {
            "success_cases": {
                method_id: _examples(
                    value["per_sample"], value["_full_sample_ids"], limit=3)
                for method_id, value in methods.items()
            },
            "failure_cases": {
                method_id: _examples(
                    value["per_sample"], value["_miss_sample_ids"], limit=3)
                for method_id, value in methods.items()
            },
            "zero_prediction_cases": {
                method_id: _examples(
                    value["per_sample"], value["_zero_sample_ids"], limit=5)
                for method_id, value in methods.items()
            },
            "winter_definition_only_cases": sorted(definition_only)[:5],
        },
        "zero_api": {
            "new_llm_api_calls": 0,
            "new_network_calls": 0,
            "historical_predictions_reused": True,
            "gold_used_for_evaluation_only_after_winter_output_built": True,
            "post_result_rule_or_threshold_tuning": False,
        },
        "claim_boundary": (
            "This is a zero-API first predecessor-baseline result on the frozen "
            "EStG-150 Stage 2 corpus. Winter is evaluated only on the adapted "
            "clause-region subtask; its native match/cost task on proprietary "
            "BPMN models is not reproduced. Rules-Only and Direct-LLM numbers "
            "are historical capsules reused read-only, not new calls. Sun's "
            "published Table 12 cannot be compared directly to this task."
        ),
    }
    capsule = {
        "native_rows": native_rows,
        "adapted_rows": adapted_rows,
        "historical_region_rows": {
            method_id: [
                {"sample_id": sample_id, "clause_regions": regions}
                for sample_id, regions in sorted(regions_by_sample.items())
            ]
            for method_id, regions_by_sample in historical_regions_by_method.items()
        },
        "methods": methods,
        "gold_by_id": {sample_id: regions
                       for sample_id, regions in sorted(gold_by_id.items())},
    }
    return report, capsule


def render_markdown(report: Mapping[str, Any]) -> str:
    methods = report["methods"]
    lines = [
        "# SEP-C2 Stage 2B: Winter Predecessor Baseline (EStG-150)",
        "",
        f"- status: **{report['status']}**",
        "- input: `data/input/estg150_formal_inference_input_v2.json` (150 records)",
        "- Gold: `data/gold/stage2/estg150_formal_gold_v1.json` (231 clause regions)",
        "- task: **clause-region detection only** (`estg150_clause_region_detection_v1`)",
        "- metric: global statement-level any-non-empty-character-intersection P/R/F1",
        "- new LLM/API calls: **0**; historical Rules-Only / Direct-LLM predictions reused read-only",
        "",
        "## Results",
        "",
        "| method | Gold | Pred | matched GT | P | R | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for method_id in ("winter_2020_native_clause_regions",
                      "sun_rule_only_historical", "direct_llm_historical"):
        row = methods[method_id]
        ev = row["overall"]
        lines.append(
            f"| {row['display_name']} | {ev['ground_truth_regions']} | "
            f"{ev['predicted_regions']} | {ev['matched_ground_truth']} | "
            f"{ev['precision']:.4f} | {ev['recall']:.4f} | {ev['f1']:.4f} |")
    lines += [
        "",
        "## Native Winter output retained separately",
        "",
        f"- sentences: {report['native_output']['sentences']}",
        f"- signal-word constraint sentences: {report['native_output']['constraint_sentences']}",
        f"- native obligation clauses: {report['native_output']['obligations']}",
        f"- native flows: {report['native_output']['flows']}",
        f"- parse failures: {len(report['native_output']['parse_failures'])}",
        "- unsupported as extraction: " + ", ".join(report["native_output"]["unsupported_fields"]),
        "",
        "## Real cases (not synthetic)",
        "",
    ]
    for method_id in ("winter_2020_native_clause_regions",
                      "sun_rule_only_historical", "direct_llm_historical"):
        method = report["methods"][method_id]
        lines += [
            f"### {method['display_name']}",
            "",
            f"- full-region-match samples: {method['records_with_full_region_match']}/150",
            f"- records with >=1 matched Gold region: {method['records_with_at_least_one_match']}/150",
            f"- complete-miss samples: {method['records_with_complete_miss']}",
            f"- zero-prediction samples: {method['records_with_zero_prediction']}",
        ]
        successes = report["cases"]["success_cases"].get(method_id) or []
        failures = report["cases"]["failure_cases"].get(method_id) or []
        if successes:
            lines.append(f"- success example: {successes[0]}")
        if failures:
            lines.append(f"- failure example: {failures[0]}")
        lines.append("")
    lines += [
        "## Boundary",
        "",
        report["claim_boundary"],
    ]
    return "\n".join(lines) + "\n"
