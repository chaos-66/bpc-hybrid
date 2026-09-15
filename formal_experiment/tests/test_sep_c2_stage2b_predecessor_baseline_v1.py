# -*- coding: utf-8 -*-
"""Focused tests for the SEP-C2 Stage 2B predecessor baseline."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

FORMAL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = FORMAL_ROOT.parent
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PLAN = FORMAL_ROOT / "configs/sep_c2_stage2b_predecessor_plan_v1.json"
RUNNER = FORMAL_ROOT / "scripts/run_sep_c2_stage2b_predecessor_baseline_v1.py"
VERIFIER = FORMAL_ROOT / "scripts/verify_sep_c2_stage2b_predecessor_baseline_v1.py"
REPORT = FORMAL_ROOT / "outputs/reports/sep_c2_stage2b_predecessor_baseline_v1.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args],
                          cwd=REPO_ROOT, capture_output=True, text=True,
                          timeout=900)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "sep_c2_stage2b_module_test",
        FORMAL_ROOT / "src/bpc_hybrid/sep_c2_stage2b_winter_estg150.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_verifier_verifies():
    proc = _run(VERIFIER)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SEP-C2 STAGE 2B PREDECESSOR BASELINE VERIFIED" in proc.stdout


def test_runner_replay_is_byte_identical():
    proc = _run(RUNNER, "--check")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SEP-C2 Stage 2B predecessor baseline VERIFIED" in proc.stdout


def test_metric_any_intersection_counts():
    module = _load_module()
    gold = {"s1": [{"start": 0, "end": 10}, {"start": 20, "end": 30}]}
    predicted = {
        "s1": [
            {"start": 5, "end": 15},   # intersects Gold 0
            {"start": 40, "end": 50},  # no Gold intersection
        ]
    }
    metrics = module.evaluate_regions(gold, predicted, "test_method")
    overall = metrics["overall"]
    assert overall["ground_truth_regions"] == 2
    assert overall["predicted_regions"] == 2
    assert overall["matched_predictions"] == 1
    assert overall["matched_ground_truth"] == 1
    assert overall["precision"] == 0.5
    assert overall["recall"] == 0.5
    assert overall["f1"] == 0.5


def test_winter_adapter_is_region_only():
    module = _load_module()
    native = {
        "sample_id": "s1",
        "sentences": [{"constraint": True}],
        "flows": [],
        "obligations": [{
            "clause_id": "s1.c1", "start": 3, "end": 12,
            "text": "shall act",
        }],
    }
    adapted = module.adapt_winter_row(native)
    assert adapted["clause_regions"] == [{
        "start": 3, "end": 12, "text": "shall act",
        "native_clause_id": "s1.c1",
    }]
    assert adapted["action_span_claim"] is False
    assert "action" in adapted["unsupported_fields"]
    assert adapted["task_id"] == "estg150_clause_region_detection_v1"


def test_plan_freezes_task_metric_and_zero_api():
    plan = _read(PLAN)
    assert plan["registered_before_any_metric_view"] is True
    assert plan["adaptation"]["task_id"] == "estg150_clause_region_detection_v1"
    assert plan["metric"]["metric_id"] \
        == "global_statement_any_nonempty_character_intersection"
    assert plan["execution"]["new_llm_api_calls"] == 0
    assert plan["execution"]["new_network_calls"] == 0
    assert plan["comparison_boundary"]["not_same_condition_as_sun_final_paper_table_12"] is True


def test_published_result_has_real_cases_and_native_output():
    report = _read(REPORT)
    assert report["native_output"]["rows"] == 150
    assert report["native_output"]["obligations"] > 0
    assert report["bindings"]["gold"]["sha256"] == \
        "c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100"
    assert report["bindings"]["input"]["sha256"] == \
        "52a73aa1109970b6c4fbc17214b0828ed0dd64b330001e884cdc803b1ce81dc2"
    assert report["methods"]["winter_2020_native_clause_regions"]["overall"][
        "ground_truth_regions"] == 231
    assert report["cases"]["failure_cases"]["winter_2020_native_clause_regions"]
    assert report["cases"]["failure_cases"]["direct_llm_historical"]
    assert report["asset_audit"]["common_files"] == 112
    assert report["asset_audit"]["common_file_sha_mismatches"] == 0
