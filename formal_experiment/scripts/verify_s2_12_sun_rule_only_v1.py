# -*- coding: utf-8 -*-
"""Independent verifier for the S2.12 ``sun_rule_only`` zero-API arm."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "scripts/evaluate_s2_12_sun_rule_only_v1.py"
INPUT = ROOT / "data/input/s2_12_complex_corpus_formal_input_v1.json"
PRED_DIR = ROOT / "data/predictions/s2_12_sun_rule_only_v1"
RESULT_DIR = ROOT / "data/results/s2_12_sun_rule_only_v1"
FORBIDDEN_TEXT_KEYS = {"text", "source_text", "normalized", "marker_surface"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_evaluator() -> Any:
    spec = importlib.util.spec_from_file_location("s212_eval_replay", EVALUATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _has_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in FORBIDDEN_TEXT_KEYS or _has_forbidden_key(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_has_forbidden_key(item) for item in value)
    return False


def verify() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    required = [
        INPUT,
        PRED_DIR / "predictions.json",
        PRED_DIR / "telemetry.json",
        PRED_DIR / "cost.json",
        PRED_DIR / "manifest.json",
        RESULT_DIR / "evaluation.json",
        RESULT_DIR / "manifest.json",
    ]
    check("all capsule files exist", all(path.is_file() for path in required))
    if not all(path.is_file() for path in required):
        return {"verified": False, "checks": checks}
    input_doc = json.loads(INPUT.read_text(encoding="utf-8"))
    predictions = json.loads((PRED_DIR / "predictions.json").read_text(encoding="utf-8"))
    run_manifest = json.loads((PRED_DIR / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((RESULT_DIR / "evaluation.json").read_text(encoding="utf-8"))
    manifest = json.loads((RESULT_DIR / "manifest.json").read_text(encoding="utf-8"))

    check("Gold-blind input fixed membership", input_doc.get("gold_blind") is True and input_doc.get("record_count") == 36)
    input_keys = {key for row in input_doc.get("records", []) for key in row}
    check("input contains only sample_id/source", input_keys == {"sample_id", "source"}, str(sorted(input_keys)))
    check("predictions 36 and text-free", predictions.get("record_count") == 36 and not _has_forbidden_key(predictions))
    check("predictions locked before Gold", run_manifest.get("status") == "predictions_locked_before_gold_evaluation" and run_manifest.get("gold_isolation", {}).get("gold_read_by_runner") is False)
    check("zero API cost exact", run_manifest.get("safety", {}).get("llm_api_calls") == 0 and run_manifest.get("safety", {}).get("cost_usd") == 0.0)
    for name, info in run_manifest.get("artifacts", {}).items():
        path = PRED_DIR / name
        check(f"run artifact {name} hash/size", path.is_file() and _sha(path) == info.get("sha256") and path.stat().st_size == info.get("byte_size"))

    check("evaluation single-arm boundary", report.get("scope_boundary", {}).get("single_zero_api_arm_only") is True and report.get("scope_boundary", {}).get("three_method_comparison_complete") is False)
    check("no post-result tuning", report.get("scope_boundary", {}).get("post_result_tuning_performed") is False and report.get("scope_boundary", {}).get("no_method_rule_prompt_threshold_adjustment_from_gold_or_results") is True)
    strata = report.get("metrics", {}).get("strata", {})
    check("strata counts L1/L2/L3", [strata.get(level, {}).get("samples") for level in ("L1", "L2", "L3")] == [31, 5, 0])
    check("L3 no-samples semantics", strata.get("L3", {}).get("span_fields") is None and strata.get("L3", {}).get("modality_labels") is None and "no samples" in strata.get("L3", {}).get("note", ""))
    check("overall 36", report.get("metrics", {}).get("overall", {}).get("samples") == 36)
    check("API arms remain pending", report.get("scope_boundary", {}).get("direct_llm_pending_api_authorization") is True and report.get("scope_boundary", {}).get("sun_llm_fallback_pending_api_authorization") is True)

    report_info = manifest.get("report", {})
    report_path = ROOT / str(report_info.get("path", ""))
    check("evaluation report hash/size", report_path.is_file() and _sha(report_path) == report_info.get("sha256") and report_path.stat().st_size == report_info.get("byte_size"))
    for name, info in manifest.get("bindings", {}).items():
        path = ROOT / str(info.get("path", ""))
        check(f"evaluation binding {name}", path.is_file() and _sha(path) == info.get("sha256"))
    for rel, expected in manifest.get("implementation", {}).items():
        path = ROOT / rel
        check(f"implementation {rel}", path.is_file() and _sha(path) == expected)

    module = _load_evaluator()
    expected_report = module._json_bytes(module.build_report())
    expected_manifest = module._json_bytes(module.build_manifest(expected_report))
    check("evaluation replay byte-identical", (RESULT_DIR / "evaluation.json").read_bytes() == expected_report and (RESULT_DIR / "manifest.json").read_bytes() == expected_manifest)
    check("no Gold Rule Records / Oracle", report.get("cost", {}).get("llm_api_calls") == 0 and manifest.get("safety", {}).get("gold_rule_records_created") is False and manifest.get("safety", {}).get("oracle_started") is False)
    return {"verified": all(c["ok"] for c in checks), "checks": checks}


def main() -> int:
    result = verify()
    for item in result["checks"]:
        print(("PASS" if item["ok"] else "FAIL"), item["name"], item["detail"])
    print("S2.12 SUN_RULE_ONLY VERIFIED" if result["verified"] else "S2.12 SUN_RULE_ONLY NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
