"""Source fidelity, failure accounting, and authorization/ledger boundaries."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "barrientos_paper_ablation", ROOT / "scripts/run_barrientos_paper_ablation_v1.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def tree(pattern="performed_by", dimension="resource"):
    return {"id": "fixture", "precondition": {"and": [], "or": [], "not": []},
            "norms": [{"modality": "obligation", "action": {
                "dimension": dimension, "compliance_pattern": pattern,
                "activities": ["synthetic action"], "resources": ["synthetic actor"]}}],
            "temporal_validity": {"start": "0000-01-01T00:00:00Z", "end": "9999-12-31T23:59:59Z"}}


def inspect(value):
    schema = runner.read(runner.SCHEMA)
    return runner.inspect_response(value, runner.vocabulary(), runner.expand_refs(schema, schema))


def test_source_diff_is_two_removed_sections_not_one():
    audit = runner.source_audit()
    assert audit["is_pure_whitelist_one_factor"] is False
    assert audit["artifact_removed_sections"] == ["Allowed Compliance Patterns", "Control-Flow Exclusivity Rule"]
    assert audit["step3"]["artifact_cells_zero_based"] == [6, 7]


def test_native_schema_accepts_unknown_pattern_but_diagnostic_catches_it():
    result = inspect(json.dumps(tree("invented_synthetic_pattern")))
    assert result["schema_valid"] and result["strict_json"]
    assert result["out_of_vocabulary"] == 1
    assert result["wrong_dimension"] == 0


def test_known_pattern_in_wrong_dimension_is_distinct_error():
    result = inspect(json.dumps(tree("performed_by", "time")))
    assert result["out_of_vocabulary"] == 0
    assert result["wrong_dimension"] == 1


def test_precondition_actions_are_also_evaluated():
    value = tree()
    value["precondition"]["not"] = [{"dimension": "data", "compliance_pattern": "invented"}]
    result = inspect(json.dumps(value))
    assert result["action_count"] == 2 and result["out_of_vocabulary"] == 1


def test_nested_native_schema_is_checked_not_only_top_level():
    value = tree()
    value["norms"][0]["action"]["resources"] = "not an array"
    assert not inspect(json.dumps(value))["schema_valid"]
    value = tree()
    value["precondition"]["and"] = [{"dimension": "resource"}]
    assert not inspect(json.dumps(value))["schema_valid"]


def test_literal_fallback_never_becomes_strict_json_success():
    result = inspect(repr(tree()))
    assert result["artifact_parseable"] and result["schema_valid"]
    assert not result["strict_json"]


@pytest.mark.parametrize("value", ["{'value': {1, 2}}", "{'value': b'bytes'}", '{"value": 1e999}'])
def test_non_json_literal_values_remain_reportable_failures(value):
    rows = [{"arm": "FULL", "sample_id": "fixture", "key": "1", "content": value}]
    report, cases = runner.summarize(rows, {"vocabulary": runner.vocabulary()})
    assert report["conditions"]["FULL"]["raw_schema_valid_rate"] == 0
    assert report["conditions"]["FULL"]["requests"] == 1
    json.dumps(cases, allow_nan=False)


@pytest.mark.parametrize("value", ["", "not-json", "[]", "null", '{"norms":[null]}'])
def test_bad_shapes_are_retained_as_failures(value):
    assert not inspect(value)["schema_valid"]


def test_empty_results_do_not_earn_perfect_stability():
    rows = [{"arm": "FULL", "sample_id": "fixture", "key": str(i), "content": ""} for i in range(5)]
    report, _ = runner.summarize(rows, {"vocabulary": runner.vocabulary()})
    full = report["conditions"]["FULL"]
    assert full["requests"] == 5 and full["stability_pair_count"] == 10
    assert full["valid_nonempty_exact_agreement"] == 0
    assert full["usable_nonempty_rate"] == 0
    assert full["out_of_vocabulary_action_rate"] is None


def test_authorization_is_required_and_hash_bound(tmp_path):
    contract = {"budget": {"usd_cost_cap": 9.0}}
    config, auth = tmp_path / "contract.json", tmp_path / "auth.json"
    runner.write_new(config, contract)
    with pytest.raises(runner.Refused, match="missing"):
        runner.verify_authorization(contract, None, config)
    runner.write_new(auth, {"contract_sha256": "0" * 64,
                            "user_authorization": runner.authorization_sentence(contract)})
    with pytest.raises(runner.Refused, match="does not match"):
        runner.verify_authorization(contract, auth, config)


def test_plan_matches_fixed_inputs_with_both_arms_per_sample_repeat():
    value = runner.plan()
    assert len(value) == 360 and len({r["key"] for r in value}) == 360
    for i in range(0, 360, 2):
        a, b = value[i:i + 2]
        assert {a["arm"], b["arm"]} == {"FULL", "NO-PATTERNS"}
        assert (a["sample_id"], a["repeat"]) == (b["sample_id"], b["repeat"])
        assert a["body_sha256"] != b["body_sha256"]


def test_in_doubt_request_never_resumes(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    step = {"key": "1/FULL/fixture", "body_sha256": "b" * 64}
    runner.append_event(ledger, {"state": "started", **step}, "0" * 64)
    with pytest.raises(runner.Refused, match="in-doubt"):
        runner.restore(ledger, {"plan": [step]})


def test_ledger_tampering_is_rejected(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    step = {"key": "1/FULL/fixture", "body_sha256": "b" * 64}
    runner.append_event(ledger, {"state": "started", **step}, "0" * 64)
    ledger.write_text(ledger.read_text().replace("fixture", "tampered"))
    with pytest.raises(runner.Refused, match="integrity"):
        runner.restore(ledger, {"plan": [step]})


def test_execute_rejects_before_any_transport(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(runner, "validate_contract", lambda p: {"budget": {"usd_cost_cap": 9.0}})
    with pytest.raises(runner.Refused, match="missing"):
        runner.execute(tmp_path / "c.json", None, sender=lambda body: called.append(body), local=tmp_path / "local")
    assert not called and not (tmp_path / "local").exists()


def test_same_argument_disagreement_is_labelled_proxy():
    value = tree()
    other = copy.deepcopy(value["norms"][0])
    other["action"]["compliance_pattern"] = "not_performed_by"
    value["norms"].append(other)
    assert inspect(json.dumps(value))["same_arguments_pattern_disagreement_proxy"] == 1


def test_full_fake_execution_uses_native_outputs_and_keeps_all_360(tmp_path, monkeypatch):
    contract = runner.build_contract()
    path, auth = tmp_path / "contract.json", tmp_path / "authorization.json"
    runner.write_new(path, contract)
    runner.write_new(auth, {"contract_sha256": runner.sha(path),
                            "user_authorization": runner.authorization_sentence(contract)})
    monkeypatch.setattr(runner, "REPORT", tmp_path / "aggregate.json")
    called = []

    def fake(body):
        called.append(body)
        full = "1. **Allowed Compliance Patterns**" in body["messages"][0]["content"]
        value = tree("performed_by" if full else "invented_fixture_pattern")
        return {"id": "fake", "model": runner.MODEL,
                "choices": [{"message": {"content": json.dumps(value)}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20}}

    report = runner.execute(path, auth, sender=fake, local=tmp_path / "local")
    assert len(called) == report["actual_calls"] == 360
    assert report["complete"]
    assert report["conditions"]["FULL"]["usable_nonempty_rate"] == 1
    assert report["conditions"]["NO-PATTERNS"]["out_of_vocabulary_action_rate"] == 1
    assert report["conditions"]["NO-PATTERNS"]["raw_schema_valid_rate"] == 1
    assert all(c["model"] == runner.MODEL for c in called)
    with pytest.raises(runner.Refused, match="already exists"):
        runner.execute(path, auth, sender=fake, local=tmp_path / "local")
    assert len(called) == 360
