# -*- coding: utf-8 -*-
"""Barrientos ablation suite focused tests (zero API).

Covers the real offline results: Experiment A conditions + deltas,
Experiment C projection counts, D/E prepared-status honesty, and the B
composition manifest (when present).  Nothing here calls the network or an
LLM.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

PY = sys.executable
SUITE_OUT = ROOT / "outputs/development/barrientos_ablation_suite_v1/results.json"
SUITE_REPORT = ROOT / "outputs/reports/barrientos_ablation_comparison_v1.json"
B_OUT = ROOT / "outputs/development/b0_module_removal_ablation_v1/results.json"
B_MANIFEST = ROOT / "outputs/development/b0_module_removal_ablation_v1/manifest.json"

A_FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")


def _run_cmd(args):
    proc = subprocess.run(
        [PY, *args], capture_output=True, text=True, cwd=ROOT.parent
    )
    return proc


def test_suite_config_is_locked():
    cfg = json.loads(
        (ROOT / "configs/ablations/barrientos_ablation_suite_v1.json")
        .read_text(encoding="utf-8"))
    assert cfg["schema_version"] == "barrientos_ablation_suite@1.0.0"
    assert cfg["zero_api"] is True
    assert cfg["safety"]["llm_api_calls"] == 0
    assert cfg["safety"]["formal_predictions_overwritten"] is False


def test_suite_run_exists_and_zero_api():
    assert SUITE_OUT.is_file(), "suite results.json missing"
    results = json.loads(SUITE_OUT.read_text(encoding="utf-8"))
    assert results["safety"]["llm_api_calls"] == 0
    assert results["safety"]["network_calls"] == 0
    assert results["safety"]["gold_modified"] is False


# ---------------------------------------------------------------------------
# Experiment A
# ---------------------------------------------------------------------------


def test_experiment_a_three_conditions_with_metrics():
    results = json.loads(SUITE_OUT.read_text(encoding="utf-8"))
    a = results["A"]
    assert set(a["conditions"]) == {"full", "schema_only", "raw_approximation"}
    for name, cond in a["conditions"].items():
        m = cond["metrics"]
        assert "overall" in m and "per_field" in m
        assert m["overall"]["f1"] > 0
        for f in A_FIELDS:
            assert f in m["per_field"]
    # full must reproduce the locked D1-R3 number (fine gold)
    assert abs(a["conditions"]["full"]["metrics"]["overall"]["f1"] - 0.7756) < 0.002


def test_experiment_a_full_beats_ablations_or_documents_equal():
    results = json.loads(SUITE_OUT.read_text(encoding="utf-8"))
    a = results["A"]
    full_f1 = a["conditions"]["full"]["metrics"]["overall"]["f1"]
    for name in ("schema_only", "raw_approximation"):
        f1 = a["conditions"][name]["metrics"]["overall"]["f1"]
        assert full_f1 >= f1 - 1e-9, f"full should not be worse than {name}"


def test_experiment_a_locked_stats():
    results = json.loads(SUITE_OUT.read_text(encoding="utf-8"))
    stats = results["A"]["locked_run_stats"]
    assert stats["legal_output_rate"] == 1.0
    assert stats["canonicalization_status_counts"].get("reanchored", 0) >= 100
    assert stats["samples_changed_by_canonicalizer"] >= 100
    assert stats["responses_count"] == 150 if "responses_count" in stats else True


def test_experiment_a_has_before_after_examples():
    results = json.loads(SUITE_OUT.read_text(encoding="utf-8"))
    examples = results["A"]["before_after_examples"]
    assert len(examples) >= 5
    for ex in examples:
        assert ex["sample_id"]
        assert ex["example_spans"], "example must show a re-anchored span"


def test_experiment_a_raw_limitation_documented():
    results = json.loads(SUITE_OUT.read_text(encoding="utf-8"))
    assert "raw model JSON is not persisted" in results["A"]["limitation"]


# ---------------------------------------------------------------------------
# Experiment C
# ---------------------------------------------------------------------------


def test_experiment_c_4_vs_3_projection():
    results = json.loads(SUITE_OUT.read_text(encoding="utf-8"))
    c = results["C"]
    four = c["four_class_counts"]
    assert set(four) == {"definition", "obligation", "permission", "prohibition"}
    shared = c["three_class_shared_counts"]
    assert set(shared) == {"obligation", "permission", "prohibition"}
    assert c["definition_excluded_count"] == four.get("definition", 0)
    assert 0 < c["definition_coverage_loss_ratio"] < 1
    assert "NOT a Barrientos-method performance comparison" in c["note"]


# ---------------------------------------------------------------------------
# Experiment D/E
# ---------------------------------------------------------------------------


def test_experiment_de_prepared_not_executed():
    results = json.loads(SUITE_OUT.read_text(encoding="utf-8"))
    de = results["D_E"]
    assert de["input_contract"]["nonempty_requirements"] >= 36
    assert de["status"]["D_no_fewshot"] == "prepared_not_executed_no_api"
    assert de["status"]["D_barrientos_style"] == "prepared_not_executed_no_api"
    assert de["status"]["D_minimal_prompt"] == "prepared_not_executed_no_api"
    assert de["status"]["E_arms"] == "prepared_not_executed_no_api"
    assert "NOT EXECUTED" in json.dumps(de["commands"], ensure_ascii=False)


def test_comparison_report_exists():
    assert SUITE_REPORT.is_file()
    report = json.loads(SUITE_REPORT.read_text(encoding="utf-8"))
    assert report["schema_version"] == "barrientos_ablation_comparison@1.0.0"
    assert report["generated_zero_api"] is True
    assert "A" in report["summary"] and "C" in report["summary"]


# ---------------------------------------------------------------------------
# Experiment B (when present)
# ---------------------------------------------------------------------------


def test_experiment_b_manifest_zero_api_and_no_overwrite():
    if not B_MANIFEST.is_file():
        return  # B not run in this batch; suite marks it prepared
    manifest = json.loads(B_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["safety"]["llm_api_calls"] == 0
    assert manifest["safety"]["formal_predictions_overwritten"] is False
    assert manifest["safety"]["formal_method_modified"] is False
    assert len(manifest["flags"]) == 6


def test_experiment_b_results_have_all_flags_and_deltas():
    if not B_OUT.is_file():
        return
    results = json.loads(B_OUT.read_text(encoding="utf-8"))
    assert set(results) >= {
        "full", "no_lexicon_extensions", "no_modality_classifier",
        "no_actor_action_ownership", "no_multi_match_guard",
        "no_de_en_alignment_validation"}
    full_f1 = results["full"]["metrics"]["overall"]["f1"]
    assert full_f1 > 0.5  # full v10a reproduces a usable fine F1
    # full per-field fine F1 must be close to the locked formal diagnostics
    locked_fine = {
        "actor": 0.8038834951456311, "action": 0.8554026399759472,
        "condition": 0.705423471848942, "constraint": 0.4913493402728364,
        "exception": 0.8148148148148148,
    }
    per_field = results["full"]["metrics"]["per_field"]
    for field, locked in locked_fine.items():
        assert abs(per_field[field]["f1"] - locked) < 0.05, \
            f"{field}: full {per_field[field]['f1']:.4f} vs locked {locked:.4f}"
    for flag in ("no_lexicon_extensions", "no_modality_classifier",
                 "no_actor_action_ownership", "no_multi_match_guard",
                 "no_de_en_alignment_validation"):
        assert "delta_vs_full_f1" in results[flag]
        assert results[flag]["metrics"]["overall"]["f1"] > 0


# ---------------------------------------------------------------------------
# Offline discipline
# ---------------------------------------------------------------------------


def test_ablation_scripts_are_offline():
    for name in ("run_barrientos_ablation_suite_v1.py",
                 "run_b0_module_removal_ablation_v1.py"):
        src = (SCRIPTS / name).read_text(encoding="utf-8")
        for token in ("import urllib.request", "from urllib.request",
                      "import requests", "import httpx", "import openai"):
            assert token not in src, f"{name} references {token}"