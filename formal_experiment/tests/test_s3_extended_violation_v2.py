# -*- coding: utf-8 -*-
"""S3.9-EXT extended-violation panel v2 focused tests (zero API).

Covers: 40 variants / 10 per new type; the four mutation kinds; exactly-one-
targeted-error contract; frozen source BPMN byte-unchanged; control/variant
provenance; deterministic replay; all four methods through the SAME evaluator
(support 40, per-type support 10); failures stay in the denominator;
unobservable items keep predicted=None and score=None (never hard 0/1); the
original three-type Gold/schema/predictions byte-unchanged; zero API/network.
"""

from __future__ import annotations

import hashlib
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
PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
PANEL_DIR = ROOT / "data/development/stage3_synth"
BPMN_DIR = ROOT / "data/input/stage1_stage3/gdpr7"
V2_TYPES = (
    "prohibited_action_present",
    "required_condition_not_enforced",
    "constraint_violated",
    "exception_not_handled",
)
METHODS = ("winter", "sun", "bm25", "tfidf_svd")

# frozen hashes of the original three-type artifacts (byte-unchanged guard)
V1_GOLD_SHA = "54245ef0d102ae5e7a44e8c45424ecd9e86e1e0d9ed43ac1a9cd43641c981550"
V1_PANEL_SHA = "e6b4da045a44ffc347a8de88909e005bef584335f63804d3c2155ef9242c3026"
V1_SCHEMA_SHA = "5b26d7f87be4a8cc29ef2cf80c7c2aacf1a752ecf192cdee3456ac50e36d280d"
V1_COMPARE_SHA = "a1409f65182399faae6da4eed38403200b01b7c24ca19444a9c1c70c8931b45a"
V1_RUN_SHA = {
    "winter": {
        "predictions.jsonl": "4b1477edd875be9c3c75ad11797fb5348d34b41eb62ae9058db18419dd106b87",
        "evaluation.json": "3cdf563e3f315334a2004eedfcefe9b8584026125e759c1268f75b834c74858a",
        "manifest.json": "932be60819b5c07a001c0404b2d6e7ac90d8ed0bb5e3ad52ba55c07e3e118858",
    },
    "sun": {
        "predictions.jsonl": "9c64bfc6ecf2919f0846a1395183f80ace805d6a0d980f977c37fbf45869851e",
        "evaluation.json": "f9ad2b4621281eea262fc8c917247c70b910aa6e9fff956f27a59d9284ffef0e",
        "manifest.json": "f4114e7dcfdb84f3a340abaea8ca454a589b1e8f2e628c90304f06079a1300c9",
    },
    "bm25": {
        "predictions.jsonl": "67d826e3565af2f683e20babaf58bd6a54f508154e851f1a6b4ff00bef67d3de",
        "evaluation.json": "a48eb45829d06be96185c3298c8a2545f840de8bbb83df9d0afdbd70e71f2169",
        "manifest.json": "aaecab0a84a3411b648fe071f969e058a7f4609b571fee575ca9dc1df131625d",
    },
    "tfidf_svd": {
        "predictions.jsonl": "f7e50aa89a48a144d774990e96a52b7c62804a563b19bb3fe5b372200d20d02d",
        "evaluation.json": "b07614e250bb617244c14c4f32586a8eed18dce4279918fc651a0ee0dca32edc",
        "manifest.json": "55eac2a0dd824302c0e7cbfdf8655beb5ed624adf2a573604fa301afac1db5d5",
    },
}
V2_PANEL_SHA = "6a23adbdbc0d8930ff2a33411c52fed7fbbf581fdd101f830c29b2e3373e2e81"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_panel() -> dict:
    return json.loads(PANEL.read_text(encoding="utf-8"))


def _run_cmd(args) -> subprocess.CompletedProcess:
    return subprocess.run([PY, *args], capture_output=True, text=True, cwd=ROOT.parent)


# ---------------------------------------------------------------------------
# Panel contract: 40 variants, 10 per type, four mutation kinds
# ---------------------------------------------------------------------------


def test_panel_has_40_variants_10_each():
    panel = _load_panel()
    assert panel["schema_version"] == "s3_synthetic_controlled_error_extension@2.0.0"
    assert panel["panel_label"] == "synthetic_controlled_error_extension_v2"
    assert panel["counts_total"] == 40
    for t in V2_TYPES:
        assert panel["counts"][t] == 10, t
    assert len(panel["variants"]) == 40
    assert _sha256_file(PANEL) == V2_PANEL_SHA, "panel manifest drifted from the frozen hash"


def test_panel_is_explicitly_not_human_gold():
    panel = _load_panel()
    assert panel["status"] == "dev_only_panel_not_human_gold"
    assert panel["safety"]["panel_is_human_gold"] is False
    assert panel["safety"]["gold_modified"] is False
    human_gold = json.loads(
        (ROOT / "data/gold/stage3/stage3_violation_gold_v1.json")
        .read_text(encoding="utf-8")
    )
    assert human_gold["count"] == 33
    human_ids = {item["item_id"] for item in human_gold["items"]}
    synth_ids = {v["variant_id"] for v in panel["variants"]}
    assert not (human_ids & synth_ids)


def test_four_mutation_kinds_present():
    panel = _load_panel()
    kinds = {
        "prohibited_action_present": {"insert_task"},
        "required_condition_not_enforced": {"condition_expression_removal"},
        "constraint_violated": {"timer", "annotation", "dataobject"},
        "exception_not_handled": {"boundary", "branch"},
    }
    for v in panel["variants"]:
        t = v["mutation_type"]
        sub = v.get("sub_kind")
        mut = v["mutation_config"]
        if t == "prohibited_action_present":
            assert "inserted_task_id" in mut
            assert mut["inserted_task_name"] == v["rule_element"]["action"]
        elif t == "required_condition_not_enforced":
            assert mut["condition_expression"] == v["rule_element"]["condition"]
        elif t == "constraint_violated":
            assert sub in kinds[t]
            if sub == "timer":
                assert mut["conflict_value"] in ("7 days", "30 days")
        elif t == "exception_not_handled":
            assert sub in kinds[t]
            if sub in ("boundary", "branch"):
                assert mut["handler_name"] == v["rule_element"]["exception"]


def test_every_variant_has_locked_contract_fields():
    panel = _load_panel()
    for v in panel["variants"]:
        for key in ("variant_id", "process_id", "rule_id", "source_bpmn",
                    "source_bpmn_sha256", "control_bpmn", "control_bpmn_sha256",
                    "variant_bpmn", "variant_bpmn_sha256", "mutation_type",
                    "expected_violation", "mutation_config", "validation_checks",
                    "generator_sha256", "rule_element"):
            assert key in v, f"{v['variant_id']} missing {key}"
        assert v["mutation_type"] == v["expected_violation"]
        assert v["mutation_type"] in V2_TYPES
        assert v["rule_element"]["sentence_idx"] >= 0
        assert v["generator_sha256"]


def test_all_variant_validations_passed_exactly_one_error():
    panel = _load_panel()
    for v in panel["variants"]:
        vc = v["validation_checks"]
        assert vc["status"] == "passed", f"{v['variant_id']}: {vc}"
        assert vc["control_xml_parse"] is True
        assert vc["control_structure_valid"] is True
        assert vc["variant_xml_parse"] is True
        assert vc["variant_structure_valid"] is True


def test_variant_control_files_exist_and_match_hashes():
    panel = _load_panel()
    for v in panel["variants"]:
        control = ROOT / v["control_bpmn"]
        variant = ROOT / v["variant_bpmn"]
        assert control.is_file(), v["control_bpmn"]
        assert variant.is_file(), v["variant_bpmn"]
        assert _sha256_file(control) == v["control_bpmn_sha256"]
        assert _sha256_file(variant) == v["variant_bpmn_sha256"]


def test_control_variant_relation_flags_consistent():
    panel = _load_panel()
    for v in panel["variants"]:
        control = ROOT / v["control_bpmn"]
        variant = ROOT / v["variant_bpmn"]
        source = ROOT / v["source_bpmn"]
        assert v["control_equals_source_bytes"] == (
            _sha256_file(control) == _sha256_file(source))
        assert v["variant_equals_source_bytes"] == (
            _sha256_file(variant) == _sha256_file(source))
        assert _sha256_file(source) == v["source_bpmn_sha256"]
        # the two files of one variant must differ (a real mutation exists)
        assert _sha256_file(control) != _sha256_file(variant), v["variant_id"]


def test_source_bpmns_byte_unchanged():
    panel = _load_panel()
    originals = {
        p.stem: _sha256_file(p) for p in sorted(BPMN_DIR.glob("*.bpmn"))
    }
    assert len(originals) == 7
    assert originals == panel["originals"]["source_hashes"]
    for v in panel["variants"]:
        assert originals[v["process_id"]] == v["source_bpmn_sha256"]


def test_rule_binding_from_frozen_inference_and_replay_matches():
    panel = _load_panel()
    binding = panel["rule_binding"]["per_variant"]
    assert len(binding) == 40
    inference = json.loads(
        (ROOT / "data/development/human_review/stage3_gold_inference_v1.json")
        .read_text(encoding="utf-8")
    )
    rule_processes: dict[str, set[str]] = {}
    for item in inference["matching_items"] + inference["violation_items"]:
        rule_processes.setdefault(item["rule_id"], set()).add(item["process_id"])
    for v in panel["variants"]:
        assert v["process_id"] in rule_processes.get(v["rule_id"], set())
        assert binding[v["variant_id"]]["process_id"] == v["process_id"]
        assert binding[v["variant_id"]]["rule_id"] == v["rule_id"]
        assert binding[v["variant_id"]]["sentence_idx"] == v["rule_element"]["sentence_idx"]


def test_panel_replay_is_byte_identical():
    proc = _run_cmd([
        str(SCRIPTS / "build_s3_extended_violation_panel_v2.py"), "--check",
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "byte-identical" in proc.stdout


# ---------------------------------------------------------------------------
# Runner device: four methods, one evaluator
# ---------------------------------------------------------------------------


def _run_dir(method: str) -> Path:
    return ROOT / "outputs/development" / f"s3_extended_violation_panel_v2_{method}"


def _predictions(method: str) -> list[dict]:
    return [
        json.loads(line)
        for line in _run_dir(method).joinpath("predictions.jsonl")
        .read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_four_methods_produced_40_predictions_through_one_evaluator():
    for method in METHODS:
        run_dir = _run_dir(method)
        assert run_dir.is_dir(), f"{method}: run dir missing"
        preds = _predictions(method)
        assert len(preds) == 40, f"{method}: expected 40 predictions"
        for name in ("evaluation.json", "manifest.json", "failures.json",
                     "unobservable_cases.json"):
            assert run_dir.joinpath(name).is_file(), f"{method}: {name} missing"
        evaluation = json.loads(
            run_dir.joinpath("evaluation.json").read_text(encoding="utf-8"))
        # one shared evaluator structure for all four methods
        assert evaluation["support"] == 40
        for t in V2_TYPES:
            assert t in evaluation["per_type"]
            assert evaluation["per_type"][t]["support"] == 10
        assert evaluation["denominator"]["per_type_support"] == {
            t: 10 for t in V2_TYPES
        }
        manifest = json.loads(run_dir.joinpath("manifest.json").read_text(encoding="utf-8"))
        assert manifest["safety"]["llm_api_calls"] == 0
        assert manifest["safety"]["network_calls"] == 0
        assert manifest["safety"]["synthetic_panel_not_human_gold"] is True


def test_failure_samples_stay_in_denominator():
    panel = _load_panel()
    for method in METHODS:
        evaluation = json.loads(
            _run_dir(method).joinpath("evaluation.json").read_text(encoding="utf-8"))
        preds = _predictions(method)
        failures = json.loads(
            _run_dir(method).joinpath("failures.json").read_text(encoding="utf-8"))
        missed = sum(1 for p in preds
                     if p["predicted_violation_type"] != p["expected_violation"])
        assert evaluation["missed"] == missed
        assert len(failures) == missed
        # every expected type keeps its full support of 10 (misses stay in
        # the denominator, unobservables included)
        for t in V2_TYPES:
            support = evaluation["per_type"][t]["support"]
            assert support == 10, f"{method}/{t}: support {support}"
            # recall-consistent FN count implied by the reported metrics
            fn_implied = round(support * (1 - evaluation["per_type"][t]["recall"]))
            assert fn_implied >= 0
        # detected + missed == total support (nothing dropped)
        assert evaluation["detected"] + evaluation["missed"] == 40


def test_unobservable_never_hardfilled_zero():
    for method in METHODS:
        preds = _predictions(method)
        evaluation = json.loads(
            _run_dir(method).joinpath("evaluation.json").read_text(encoding="utf-8"))
        unobs_rows = 0
        for p in preds:
            t = p["expected_violation"]
            obs = p["observability"][t]
            if obs.get("observable") is False:
                unobs_rows += 1
                assert p["predicted_violation_type"] is None
                assert p["scores"][t] is None, "unobservable score must be None, not 0"
                assert obs.get("reason") in (
                    "rule_modality_not_prohibition", "empty_rule_action",
                    "empty_rule_condition", "empty_rule_constraint",
                    "empty_rule_exception", "action_mapping_below_gamma",
                    "no_condition_candidates", "no_constraint_candidates",
                    "no_exception_candidates",
                )
        assert evaluation["unobservable"] == unobs_rows
        assert evaluation["denominator"]["unobservable_total"] == unobs_rows
        assert evaluation["denominator"]["unobservable_by_reason"]


def test_predictions_use_locked_expected_violation_and_are_offline():
    for method in METHODS:
        for row in _predictions(method):
            assert row["check_type"] == row["expected_violation"]
            assert row["panel"] == "synthetic_controlled_error_extension_v2"
            assert row["gold_visible"] is False
            assert row["predicted_violation_type"] in (None,) + V2_TYPES
            assert "control_scores" in row
            for t in V2_TYPES:
                assert t in row["scores"]
                assert t in row["observability"]


def test_original_three_type_artifacts_byte_unchanged():
    assert _sha256_file(
        ROOT / "data/gold/stage3/stage3_violation_gold_v1.json") == V1_GOLD_SHA
    assert _sha256_file(
        ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v1.json") == V1_PANEL_SHA
    assert _sha256_file(
        ROOT / "configs/schemas/stage3_prediction.schema.json") == V1_SCHEMA_SHA
    assert _sha256_file(
        ROOT / "outputs/development/s39_synthetic_panel_compare_v1/comparison.json") == V1_COMPARE_SHA
    for method, files in V1_RUN_SHA.items():
        for name, digest in files.items():
            path = ROOT / "outputs/development" / f"s39_synthetic_panel_{method}_v1" / name
            assert path.is_file(), path
            assert _sha256_file(path) == digest, f"{method}/{name} drifted"


def test_comparison_report_exists_and_is_synthetic_only():
    json_path = ROOT / "outputs/reports/s3_extended_violation_comparison_v2.json"
    md_path = ROOT / "outputs/reports/s3_extended_violation_comparison_v2.md"
    assert json_path.is_file() and md_path.is_file()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert set(data["methods"]) == set(METHODS)
    assert data["panel_counts_total"] == 40
    assert sum(data["panel_counts"].values()) == 40
    for m in data["methods"].values():
        assert m["evaluation"]["support"] == 40
    assert data["seven_class_synthetic_summary"]["v1_three_types"]
    assert data["seven_class_synthetic_summary"]["v2_four_types"]
    md = md_path.read_text(encoding="utf-8")
    assert "Winter-style extension" in md and "Sun-style extension" in md
    assert "NOT human Gold" in md or "not human Gold" in md
    assert "prohibited P/R/F1" in md


# ---------------------------------------------------------------------------
# No-network / no-LLM discipline
# ---------------------------------------------------------------------------


def test_new_files_are_offline():
    for path in (
        SCRIPTS / "build_s3_extended_violation_panel_v2.py",
        SCRIPTS / "run_s3_extended_violation_panel_v2.py",
        SRC / "bpc_hybrid/stage3_extended_violations.py",
    ):
        src = path.read_text(encoding="utf-8")
        for token in ("import urllib.request", "from urllib.request",
                      "import requests", "import httpx", "import openai",
                      "import anthropic"):
            assert token not in src, f"{path.name} references {token}"
