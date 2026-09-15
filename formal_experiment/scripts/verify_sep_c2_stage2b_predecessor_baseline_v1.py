# -*- coding: utf-8 -*-
"""Independent verifier for the SEP-C2 Stage 2B predecessor baseline.

Recomputes the clause-region metric from the persisted adapted/native region
files and the published Gold, re-extracts historical clause regions from the
original frozen prediction files, and re-checks the reference-package audit.
It does not trust the baseline report's stored metrics and does not call an LLM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

FORMAL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = FORMAL_ROOT.parent
PLAN = FORMAL_ROOT / "configs/sep_c2_stage2b_predecessor_plan_v1.json"
CAPSULE = FORMAL_ROOT / "outputs/evidence/sep_c2_stage2b_predecessor_baseline_v1"
REPORT = FORMAL_ROOT / "outputs/reports/sep_c2_stage2b_predecessor_baseline_v1.json"
REPORT_MD = FORMAL_ROOT / "outputs/reports/sep_c2_stage2b_predecessor_baseline_v1.md"
MANIFEST = FORMAL_ROOT / "outputs/reports/sep_c2_stage2b_predecessor_baseline_v1.manifest.json"
GOLD = FORMAL_ROOT / "data/gold/stage2/estg150_formal_gold_v1.json"
INPUT = FORMAL_ROOT / "data/input/estg150_formal_inference_input_v2.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _intersects(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return max(int(left["start"]), int(right["start"])) < \
        min(int(left["end"]), int(right["end"]))


def _gold_regions() -> dict[str, list[dict[str, Any]]]:
    doc = _load(GOLD)
    return {
        str(record["sample_id"]): [
            {
                "start": clause["clause_span"]["start"],
                "end": clause["clause_span"]["end"],
                "clause_id": clause.get("clause_id"),
                "modality": clause.get("modality"),
            }
            for clause in record.get("clauses") or []
        ]
        for record in doc["records"]
    }


def _metric(gold: Mapping[str, Sequence[Mapping[str, Any]]],
            predicted: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    gt = pred = mp = mg = 0
    for sample_id in sorted(gold):
        gold_regions = list(gold[sample_id])
        pred_regions = list(predicted.get(sample_id) or [])
        gt += len(gold_regions)
        pred += len(pred_regions)
        mp += sum(any(_intersects(p, g) for g in gold_regions)
                  for p in pred_regions)
        mg += sum(any(_intersects(g, p) for p in pred_regions)
                  for g in gold_regions)
    precision = mp / pred if pred else 0.0
    recall = mg / gt if gt else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "ground_truth_regions": gt,
        "predicted_regions": pred,
        "matched_predictions": mp,
        "matched_ground_truth": mg,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _extract_historical(predictions_path: Path) -> dict[str, list[dict[str, Any]]]:
    doc = _load(predictions_path)
    out: dict[str, list[dict[str, Any]]] = {}
    for row in doc["records"]:
        regions = []
        if row.get("request_status") == "ok" and isinstance(row.get("record"), dict):
            for clause in row["record"].get("clauses") or []:
                span = clause.get("clause_span") or {}
                if all(key in span for key in ("start", "end")):
                    regions.append({
                        "start": span["start"], "end": span["end"],
                        "clause_id": clause.get("clause_id"),
                    })
        out[str(row["sample_id"])] = regions
    return out


def verify() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    required = [
        PLAN, GOLD, INPUT, REPORT, REPORT_MD, MANIFEST,
        CAPSULE / "winter_native.json",
        CAPSULE / "winter_adapted_clause_regions.json",
        CAPSULE / "historical_clause_regions.json",
        CAPSULE / "evaluation.json",
    ]
    check("all artifacts exist", all(path.is_file() for path in required))
    if not all(path.is_file() for path in required):
        return {"verified": False, "checks": checks}
    report = _load(REPORT)
    manifest = _load(MANIFEST)
    plan = _load(PLAN)
    gold = _gold_regions()

    check("report status/task/metric frozen",
          report["status"] == "completed_zero_api_predecessor_clause_region_run"
          and report["task"]["task_id"] == "estg150_clause_region_detection_v1"
          and report["task"]["metric"]["metric_id"]
          == "global_statement_any_nonempty_character_intersection")
    check("zero API", report["zero_api"]["new_llm_api_calls"] == 0
          and report["zero_api"]["new_network_calls"] == 0
          and report["zero_api"]["post_result_rule_or_threshold_tuning"] is False)
    check("plan pre-registered before metric view",
          plan.get("registered_before_any_metric_view") is True)
    check("input 150 and Gold 231",
          len(_load(INPUT)["records"]) == 150
          and sum(len(value) for value in gold.values()) == 231)

    native = _load(CAPSULE / "winter_native.json")["records"]
    adapted = _load(CAPSULE / "winter_adapted_clause_regions.json")["records"]
    check("native/adapted 150 rows",
          len(native) == 150 and len(adapted) == 150)
    normalized_native = {
        row["sample_id"]: [
            {"start": item["start"], "end": item["end"],
             "native_clause_id": item.get("clause_id")}
            for item in row.get("obligations") or []
        ]
        for row in native
    }
    normalized_adapted = {
        row["sample_id"]: [
            {"start": item["start"], "end": item["end"],
             "native_clause_id": item.get("native_clause_id")}
            for item in row.get("clause_regions") or []
        ]
        for row in adapted
    }
    check("adapted regions equal native obligations",
          normalized_native == normalized_adapted)
    check("no action-span claim / unsupported fields explicit",
          all(row.get("action_span_claim") is False
              and "action" in (row.get("unsupported_fields") or [])
              for row in adapted))
    winter_pred = {
        row["sample_id"]: [{"start": item["start"], "end": item["end"]}
                           for item in row.get("clause_regions") or []]
        for row in adapted
    }

    # Independent historical-region reconstruction from the frozen predictions.
    historical_capsule = _load(CAPSULE / "historical_clause_regions.json")["methods"]
    historical_pred: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for method_key, plan_key in (
        ("sun_rule_only_historical", "sun_rule_only_historical"),
        ("direct_llm_historical", "direct_llm_historical"),
    ):
        entry = plan["historical_predictions"][plan_key]
        prediction_path = FORMAL_ROOT / entry["path"]
        check(f"{method_key} prediction hash",
              _sha(prediction_path) == entry["sha256"])
        reconstructed = _extract_historical(prediction_path)
        expected = {row["sample_id"]: [
            {"start": item["start"], "end": item["end"], "clause_id": item.get("clause_id")}
            for item in row["clause_regions"]]
            for row in historical_capsule[method_key]}
        check(f"{method_key} capsule equals frozen predictions",
              reconstructed == expected)
        historical_pred[method_key] = reconstructed

    methods = {
        "winter_2020_native_clause_regions": winter_pred,
        "sun_rule_only_historical": historical_pred["sun_rule_only_historical"],
        "direct_llm_historical": historical_pred["direct_llm_historical"],
    }
    for method_id, predicted in methods.items():
        recomputed = _metric(gold, predicted)
        stored = report["methods"][method_id]["overall"]
        check(f"{method_id} metric independently recomputed",
              recomputed["ground_truth_regions"] == stored["ground_truth_regions"]
              and recomputed["predicted_regions"] == stored["predicted_regions"]
              and recomputed["matched_predictions"] == stored["matched_predictions"]
              and recomputed["matched_ground_truth"] == stored["matched_ground_truth"]
              and abs(recomputed["precision"] - stored["precision"]) < 1e-12
              and abs(recomputed["recall"] - stored["recall"]) < 1e-12
              and abs(recomputed["f1"] - stored["f1"]) < 1e-12)

    # Reference-package audit: recompute the decisive counts independently.
    mentor = REPO_ROOT / "references/合规性检查模型代码/model_check"
    winter_ref = REPO_ROOT / "references/winter_2020_model_check/model_check"
    mentor_files = {path.relative_to(mentor).as_posix(): _sha(path)
                    for path in mentor.rglob("*") if path.is_file()}
    winter_files = {path.relative_to(winter_ref).as_posix(): _sha(path)
                    for path in winter_ref.rglob("*") if path.is_file()}
    common = set(mentor_files) & set(winter_files)
    check("reference audit counts",
          len(mentor_files) == 123 and len(winter_files) == 112
          and len(common) == 112
          and all(mentor_files[rel] == winter_files[rel] for rel in common))
    cue_hits = []
    for root in (mentor, winter_ref):
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".py", ".java", ".json", ".txt"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                if any(cue in text for cue in ("BERT", "TextCNN", "Tregex", "Tsurgeon")):
                    cue_hits.append(path.relative_to(REPO_ROOT).as_posix())
    check("no Sun Stage 2 implementation cues in either Winter copy", not cue_hits)

    check("manifest binds report",
          manifest["report"]["sha256"] == _sha(REPORT)
          and manifest["report"]["byte_size"] == REPORT.stat().st_size)
    check("manifest binds report markdown",
          manifest["report_md"]["sha256"] == _sha(REPORT_MD)
          and manifest["report_md"]["byte_size"] == REPORT_MD.stat().st_size)
    for name, info in manifest["capsule"].items():
        path = FORMAL_ROOT / info["path"]
        check(f"manifest binds {name}",
              path.is_file() and _sha(path) == info["sha256"])
    for key, info in manifest["implementation"].items():
        path = REPO_ROOT / info["path"]
        check(f"manifest implementation {key}",
              path.is_file() and _sha(path) == info["sha256"])
    return {"verified": all(item["ok"] for item in checks), "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in result["checks"]:
            print(("PASS" if item["ok"] else "FAIL"), item["name"], item["detail"])
        print("SEP-C2 STAGE 2B PREDECESSOR BASELINE VERIFIED"
              if result["verified"] else
              "SEP-C2 STAGE 2B PREDECESSOR BASELINE NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
