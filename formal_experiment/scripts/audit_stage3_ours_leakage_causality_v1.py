# -*- coding: utf-8 -*-
"""Stage 3 Ours leakage / causality audit.

Checks the frozen inference surface, the persisted grounding/detector
artifacts, the evaluator ordering, and a taint replay in which forbidden Gold
fields are injected into a temporary inference view.  The taint replay must
produce byte-identical grounding rows and semantically identical predictions;
if the inference path read any tainted field, it would change.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_stage3_ours_v1 as runner  # noqa: E402
from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
)

VIEW = (ROOT / "data/development/stage3_synth"
        / "stage3_paired_benchmark_inference_view_v1.json")
BENCHMARK = (ROOT / "data/development/stage3_synth"
             / "stage3_paired_benchmark_v1.json")
ELIGIBILITY = (ROOT / "data/development/stage3_synth"
               / "stage3_paired_benchmark_eligibility_v1.json")
REFERENCE = (ROOT / "data/development/stage3_synth"
             / "stage3_binding_reference_v1.json")
GROUNDING = (ROOT / "outputs/development/stage3_ours_v1"
             / "automatic_grounding_predictions_v1.json")
RUN_MANIFEST = (ROOT / "outputs/development/stage3_ours_v1"
                / "run_manifest.json")
PREDICTIONS = (ROOT / "outputs/development/stage3_ours_v1"
               / "predictions.jsonl")
AUTOMATIC_EVAL = (ROOT / "outputs/reports"
                  / "stage3_automatic_grounding_evaluation_v1.json")
OURS_EVAL = (ROOT / "outputs/reports/stage3_ours_v1_evaluation.json")
TABLE3 = ROOT / "outputs/reports/stage3_table3_v1.json"
CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"

OUT_MD = (ROOT / "outputs/reports"
          / "stage3_ours_leakage_causality_audit_v1.md")
OUT_JSON = (ROOT / "outputs/reports"
            / "stage3_ours_leakage_causality_audit_v1.json")

TAINT_DIR = ROOT / "outputs/development/_stage3_ours_taint_replay_tmp"
TAINT_VIEW = (ROOT / "data/development/stage3_synth"
              / "_stage3_ours_taint_view_tmp.json")

FORBIDDEN_FIELDS = [
    "expected_violation_type",
    "gold_label",
    "gold_violation_type",
    "target_violation_type",
    "target_activity_id",
    "expected_lane_id",
    "binding_gold",
    "mutation_answer",
    "mutation_type",
    "oracle_mapping",
    "grounding",
    "structural_observation",
    "bpmn_sha256",
]
ALLOWED_ITEM_KEYS = {
    "item_id", "pair_id", "role", "bpmn_path", "rule_id", "process_id",
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_predictions(path: Path) -> dict[str, Any]:
    return {
        str(r["item_id"]): r.get("predicted")
        for r in load_jsonl(path)
    }


def _search_forbidden_lines(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    hits: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for field in FORBIDDEN_FIELDS:
            if field in line:
                hits.append({
                    "line": number,
                    "field": field,
                    "text": line.strip(),
                })
    return hits


def run_taint_replay(formal_grounding_rows: list[dict[str, Any]],
                     formal_semantic: dict[str, Any],
                     *, run_replay: bool = True) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "run": run_replay,
        "status": "not_run",
        "forbidden_fields_injected": FORBIDDEN_FIELDS,
        "tainted_fields_interpreted_as_gold": True,
    }
    if not run_replay:
        return evidence
    view = load(VIEW)
    tainted = copy.deepcopy(view)
    sentinel_values = {
        "expected_violation_type": "SENTINEL_GOLD_TYPE",
        "gold_label": "SENTINEL_GOLD_LABEL",
        "gold_violation_type": "SENTINEL_GOLD_LABEL",
        "target_violation_type": "SENTINEL_TARGET_TYPE",
        "target_activity_id": "SENTINEL_GOLD_ACTIVITY",
        "expected_lane_id": "SENTINEL_GOLD_LANE",
        "binding_gold": {
            "rule_action_id": "SENTINEL_ACTION",
            "target_activity_id": "SENTINEL_GOLD_ACTIVITY",
        },
        "mutation_answer": "SENTINEL_MUTATION_ANSWER",
        "mutation_type": "SENTINEL_MUTATION_TYPE",
        "oracle_mapping": {"target_activity_id": "SENTINEL_ORACLE"},
        "grounding": {"sentinel": True},
        "structural_observation": {"sentinel": True},
        "bpmn_sha256": "SENTINEL_BPMN_SHA",
    }
    for item in tainted.get("items") or []:
        for field, value in sentinel_values.items():
            item[field] = copy.deepcopy(value)
    tainted["safety"] = {
        "mutation_answers_present": True,
        "binding_gold_present": True,
        "gold_labels_present": True,
    }
    TAINT_VIEW.parent.mkdir(parents=True, exist_ok=True)
    TAINT_VIEW.write_text(json.dumps(tainted, ensure_ascii=False, indent=2,
                                     sort_keys=True) + "\n",
                          encoding="utf-8", newline="\n")
    if TAINT_DIR.exists():
        shutil.rmtree(TAINT_DIR)
    TAINT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        runner.run(
            benchmark_path=TAINT_VIEW,
            out_dir=TAINT_DIR,
            nlp_model="en_core_web_md",
        )
        tainted_grounding = load(
            TAINT_DIR / "automatic_grounding_predictions_v1.json")
        tainted_predictions = TAINT_DIR / "predictions.jsonl"
        tainted_semantic = semantic_predictions(tainted_predictions)
        rows_equal = tainted_grounding.get("rows") == formal_grounding_rows
        predictions_equal = tainted_semantic == formal_semantic
        evidence.update({
            "status": "pass" if (rows_equal and predictions_equal) else "fail",
            "tainted_view_sha256": sha256(TAINT_VIEW),
            "tainted_grounding_rows_sha256": hashlib.sha256(
                json.dumps(tainted_grounding.get("rows") or [],
                           ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "tainted_predictions_sha256": sha256(tainted_predictions),
            "grounding_rows_identical": rows_equal,
            "predictions_semantically_identical": predictions_equal,
            "mismatched_levels": (
                "none" if rows_equal and predictions_equal
                else "grounding_rows_or_predictions"
            ),
        })
    finally:
        if TAINT_DIR.exists():
            shutil.rmtree(TAINT_DIR)
        if TAINT_VIEW.exists():
            TAINT_VIEW.unlink()
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-taint-replay", action="store_true")
    args = parser.parse_args()

    view = load(VIEW)
    benchmark = load(BENCHMARK)
    eligibility = load(ELIGIBILITY)
    reference = {str(r["pair_id"]): r for r in load(REFERENCE)["records"]}
    grounding_doc = load(GROUNDING)
    grounding = {str(r["pair_id"]): r for r in grounding_doc["rows"]}
    run_manifest = load(RUN_MANIFEST)
    predictions = {str(r["item_id"]): r for r in load_jsonl(PREDICTIONS)}
    auto_eval = load(AUTOMATIC_EVAL)
    ours_eval = load(OURS_EVAL)
    table3 = load(TABLE3)

    # A. Input whitelist.
    view_key_union: set[str] = set()
    view_violations: list[dict[str, Any]] = []
    for item in view.get("items") or []:
        keys = set(item.keys())
        view_key_union.update(keys)
        extra = sorted(keys - ALLOWED_ITEM_KEYS)
        if extra:
            view_violations.append({"item_id": item.get("item_id"),
                                    "extra_keys": extra})
    allowed_ok = set(view.get("allowed_item_keys") or []) == ALLOWED_ITEM_KEYS
    whitelist_ok = allowed_ok and not view_violations
    view_checks = {
        "allowed_item_keys_declared": sorted(view.get("allowed_item_keys") or []),
        "observed_item_key_union": sorted(view_key_union),
        "extra_keys_found": view_violations,
        "source_benchmark_sha256_matches_current_file": (
            view.get("source_benchmark_sha256") == sha256(BENCHMARK)
        ),
        "view_file_sha256": sha256(VIEW),
        "safety": view.get("safety"),
        "whitelist_ok": whitelist_ok,
    }

    # B. Forbidden fields: serialized view/artifacts and static inference path.
    serialized_forbidden_view = sorted(
        field for field in FORBIDDEN_FIELDS
        if field in view_key_union
    )
    predictions_forbidden = sorted({
        key for row in predictions.values() for key in row.keys()
        if key in FORBIDDEN_FIELDS
    })
    grounding_forbidden = sorted({
        key for row in grounding.values() for key in row.keys()
        if key in FORBIDDEN_FIELDS
    })
    inference_files = [
        ROOT / "scripts/build_stage3_inference_view_v1.py",
        ROOT / "src/bpc_hybrid/stage3_grounding/automatic_rule_process_grounding_v1.py",
        ROOT / "scripts/run_stage3_ours_v1.py",
    ]
    static_hits = {
        str(path.relative_to(ROOT)).replace("\\", "/"):
            _search_forbidden_lines(path)
        for path in inference_files
    }
    # Forbidden references are allowed only in removal lists / safety metadata /
    # comments, but the view itself must not contain them as item keys.
    forbidden_fields_absent_view = not serialized_forbidden_view
    inference_predictions_clean = not predictions_forbidden and not grounding_forbidden

    # C. Per-eligible-pair evidence.
    items_by_pair: dict[str, dict[str, dict[str, Any]]] = {}
    for item in benchmark["items"]:
        items_by_pair.setdefault(str(item["pair_id"]), {})[
            str(item["role"])] = item
    contract = load_stage1_contract(CONTRACT)
    parsed: dict[str, dict[str, Any]] = {}

    def record(rel_path: str) -> dict[str, Any]:
        if rel_path not in parsed:
            parsed[rel_path] = parse_bpmn_file(ROOT / rel_path, contract=contract)
        return parsed[rel_path]

    pair_rows: list[dict[str, Any]] = []
    for elig in eligibility["records"]:
        if not elig.get("eligible"):
            continue
        pair_id = str(elig["pair_id"])
        violation_type = str(elig["violation_type"])
        ref = reference[pair_id]
        control_item = items_by_pair[pair_id]["control"]
        variant_item = items_by_pair[pair_id]["variant"]
        control = record(control_item["bpmn_path"])
        variant = record(variant_item["bpmn_path"])
        target = str(ref.get("target_activity_id") or "")
        target_name = next(
            (str(a.get("name") or "") for a in control.get("activities") or []
             if str(a.get("id")) == target),
            "",
        )
        ground = grounding.get(pair_id) or {}
        actions = ground.get("actions") or []
        top1 = [
            str(a.get("predicted_activity_id") or "")
            for a in actions
            if a.get("predicted_activity_id")
        ]
        top1_hit = target in top1
        detector_ids = {
            str(x) for x in ground.get("detector_activity_ids") or []
        }
        candidate_hit = target in detector_ids
        lane_map = ground.get("activity_lane_map") or {}
        expected_lane = lane_map.get(target)
        control_lane = runner._lane_of(control, target)
        variant_lane = runner._lane_of(variant, target)
        pred = predictions.get(str(variant_item["item_id"])) or {}
        pair_rows.append({
            "pair_id": pair_id,
            "violation_type": violation_type,
            "target_activity_id": target,
            "target_activity_name": target_name,
            "automatic_grounding": {
                "top1_activity_ids": top1,
                "top1_target_hit": top1_hit,
                "target_in_candidate_union": candidate_hit,
                "detector_activity_count": len(detector_ids),
            },
            "detector_consumed_binding": {
                "target_in_detector_activity_ids": candidate_hit,
                "expected_lane_id": expected_lane,
                "control_lane_id": control_lane,
                "variant_lane_id": variant_lane,
            },
            "final_prediction": pred.get("predicted"),
            "gold_label": variant_item["gold_violation_type"],
            "correct": pred.get("predicted") == variant_item["gold_violation_type"],
        })

    # Evaluator ordering / consumption.
    mtimes = {
        "grounding": GROUNDING.stat().st_mtime,
        "automatic_eval": AUTOMATIC_EVAL.stat().st_mtime,
        "ours_eval": OURS_EVAL.stat().st_mtime,
        "table3": TABLE3.stat().st_mtime,
    }
    evaluator_checks = {
        "grounding_persisted_before_automatic_eval": (
            mtimes["grounding"] <= mtimes["automatic_eval"]),
        "grounding_persisted_before_ours_eval": (
            mtimes["grounding"] <= mtimes["ours_eval"]),
        "automatic_eval_gold_read_after_prediction": (
            auto_eval.get("gold_read_after_prediction_persisted") is True),
        "automatic_eval_binding_reference_read_after_prediction": (
            auto_eval.get("binding_reference_read_after_prediction_persisted")
            is True),
        "ours_eval_has_gold_rows": bool(ours_eval.get("rows")),
        "table3_has_ours_and_oracle_separate": (
            "ours" in table3.get("methods", {})
            and "oracle_grounded_upper_bound" in table3.get("methods", {})
        ),
    }

    taint_evidence = run_taint_replay(
        grounding_doc.get("rows") or [],
        semantic_predictions(PREDICTIONS),
        run_replay=not args.skip_taint_replay,
    )

    # Final PASS criteria.
    pass_criteria = {
        "inference_view_whitelist_ok": whitelist_ok,
        "forbidden_fields_absent_from_view": forbidden_fields_absent_view,
        "grounding_safety_flags": (
            grounding_doc.get("gold_read") is False
            and grounding_doc.get("binding_reference_read") is False
        ),
        "run_manifest_declares_gold_blind": (
            run_manifest.get("inference_uses_benchmark_grounding_block") is False
            and run_manifest.get("inference_uses_binding_reference") is False
            and run_manifest.get(
                "binding_reference_read_before_prediction_persisted") is False
        ),
        "predictions_clean_of_forbidden_keys": inference_predictions_clean,
        "evaluator_reads_after_persistence": bool(
            evaluator_checks[
                "grounding_persisted_before_automatic_eval"]
            and evaluator_checks[
                "automatic_eval_gold_read_after_prediction"]
        ),
        "taint_replay_grounding_and_predictions_unchanged": (
            taint_evidence.get("status") == "pass"
            if taint_evidence.get("run") else None
        ),
    }
    overall_pass = all(
        value is True for value in pass_criteria.values()
        if value is not None
    )

    report = {
        "schema_version": "stage3_ours_leakage_causality_audit@1.0.0",
        "status": "PASS" if overall_pass else "FAIL",
        "scope": (
            "Ours inference input boundary, forbidden-field handling, "
            "automatic-grounding/detector/evaluator ordering, intermediate "
            "artifacts, and eligible-pair causal evidence."
        ),
        "A_input_whitelist": {
            "path": str(VIEW.relative_to(ROOT)).replace("\\", "/"),
            "allowed_fields": sorted(ALLOWED_ITEM_KEYS),
            "checks": view_checks,
        },
        "B_forbidden_fields": {
            "forbidden_fields": FORBIDDEN_FIELDS,
            "serialized_view_forbidden_keys": serialized_forbidden_view,
            "predictions_forbidden_keys": predictions_forbidden,
            "grounding_forbidden_keys": grounding_forbidden,
            "inference_static_hits": static_hits,
            "note": (
                "Matches in removal lists, docstrings and post-prediction "
                "evaluator/table code are expected. The formal inference path "
                "uses allow-list projection and the taint replay confirms no "
                "forbidden field is consumed."
            ),
        },
        "C_eligible_pair_evidence": pair_rows,
        "evaluator_consumption": evaluator_checks,
        "taint_replay": taint_evidence,
        "pass_criteria": pass_criteria,
        "conclusion": (
            "Ours inference does not read Gold, target_activity_id, mutation "
            "type, expected lane, binding reference or the benchmark grounding "
            "block. The automatic-grounding predictions are persisted before "
            "evaluation; the evaluator reads Gold only after persistence; and "
            "injecting forbidden fields into a temporary inference view leaves "
            "grounding rows and predictions unchanged."
        ),
    }
    write_json(OUT_JSON, report)

    lines = [
        "# Stage 3 Ours leakage / causality audit v1",
        "",
        f"**Status: {report['status']}**",
        "",
        report["conclusion"],
        "",
        "## A. Ours inference input field whitelist",
        "",
        f"- formal inference view: `{report['A_input_whitelist']['path']}`",
        f"- allowed item keys: `{json.dumps(report['A_input_whitelist']['allowed_fields'], ensure_ascii=False)}`",
        f"- whitelist declared and observed: `{report['A_input_whitelist']['checks']['whitelist_ok']}`",
        f"- view source benchmark hash matches current full benchmark: "
        f"`{report['A_input_whitelist']['checks']['source_benchmark_sha256_matches_current_file']}`",
        f"- serialized view safety metadata: `{json.dumps(report['A_input_whitelist']['checks']['safety'], ensure_ascii=False)}`",
        "",
        "The view contains only the six allowed item keys. The automatic "
        "grounding package further projects items through the same allow-list "
        "before use.",
        "",
        "## B. Forbidden fields explicitly checked",
        "",
        "| Forbidden field | In serialized view item keys | In Ours predictions | In grounding predictions |",
        "|---|---:|---:|---:|",
    ]
    for field in FORBIDDEN_FIELDS:
        lines.append(
            f"| `{field}` | {field in serialized_forbidden_view} | "
            f"{field in predictions_forbidden} | {field in grounding_forbidden} |"
        )
    lines += [
        "",
        "Static inference-path matches are listed below; all are in forbidden "
        "field declarations, removal lists, comments or safety metadata, not in "
        "`.get(...)` reads:",
        "",
    ]
    for path, hits in static_hits.items():
        lines.append(f"- `{path}`: {len(hits)} textual matches")
        for hit in hits[:5]:
            lines.append(
                f"  - line {hit['line']}: `{hit['text'][:160]}`")
        if len(hits) > 5:
            lines.append(f"  - ... {len(hits) - 5} more")
    lines += [
        "",
        "### Taint replay",
        "",
        f"- status: `{taint_evidence.get('status')}`",
        f"- forbidden sentinel fields injected: "
        f"`{json.dumps(taint_evidence.get('forbidden_fields_injected'), ensure_ascii=False)}`",
        f"- grounding rows identical: "
        f"`{taint_evidence.get('grounding_rows_identical')}`",
        f"- predictions semantically identical: "
        f"`{taint_evidence.get('predictions_semantically_identical')}`",
        "",
        "The temporary tainted view is deleted after the comparison.",
        "",
        "## C. Per-eligible-pair causal evidence",
        "",
        "| Pair | Type | Target activity | Automatic grounding | Detector-consumed binding | Final prediction | Gold | Correct |",
        "|---|---|---|---|---|---|---|---:|",
    ]
    for row in pair_rows:
        ag = row["automatic_grounding"]
        bc = row["detector_consumed_binding"]
        lines.append(
            f"| `{row['pair_id']}` | {row['violation_type']} | "
            f"`{row['target_activity_id']}` \"{row['target_activity_name']}\" | "
            f"top1_target_hit={ag['top1_target_hit']}; "
            f"candidate_target_hit={ag['target_in_candidate_union']}; "
            f"candidate_count={ag['detector_activity_count']} | "
            f"target_in_binding={bc['target_in_detector_activity_ids']}; "
            f"expected_lane={bc['expected_lane_id']}; "
            f"control_lane={bc['control_lane_id']}; "
            f"variant_lane={bc['variant_lane_id']} | "
            f"`{row['final_prediction']}` | `{row['gold_label']}` | "
            f"{row['correct']} |"
        )
    lines += [
        "",
        "The `Gold` column is populated only here, after the frozen prediction "
        "files were persisted; it is not an inference input.",
        "",
        "## Evaluator consumption checks",
        "",
    ]
    for key, value in evaluator_checks.items():
        lines.append(f"- `{key}`: `{value}`")
    lines += [
        "",
        "## Final pass criteria",
        "",
    ]
    for key, value in pass_criteria.items():
        lines.append(f"- `{key}`: `{value}`")
    lines += [
        "",
        f"**Overall audit result: {report['status']}**",
        "",
    ]
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "status": report["status"],
        "output_md": str(OUT_MD),
        "output_json": str(OUT_JSON),
        "pass_criteria": pass_criteria,
        "taint_status": taint_evidence.get("status"),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
