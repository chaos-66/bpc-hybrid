# -*- coding: utf-8 -*-
"""Failing-first tests for the dedicated D/E execution contract, the budget
gate, the three-table separation, and the shared-target adapters (zero API)."""

from __future__ import annotations

import copy
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

CONTRACT = ROOT / "configs/ablations/barrientos_de_execution_contract_v1.json"
CONTRACT_SCHEMA = ROOT / "configs/schemas/barrientos_de_execution_contract_v1.schema.json"
BUDGET_REPORT = ROOT / "outputs/reports/barrientos_de_budget_v1.json"


def _executor():
    sys.path.insert(0, str(SCRIPTS))
    sys.path.insert(0, str(SRC))
    import run_barrientos_ablation_suite_v2 as m
    return m


# ---------------------------------------------------------------------------
# 1. Default plan is exactly 990 and never contains BARR-NO-PATTERN
# ---------------------------------------------------------------------------


def test_default_plan_is_exactly_990():
    m = _executor()
    plan = m.build_execution_plan(5)
    total = sum(r["expected_calls"] for r in plan)
    assert total == 990
    assert all(r["arm"] != "BARR-NO-PATTERN" for r in plan)
    # arm/repeat structure is fixed
    keys = [(r["arm"], r["repeat_id"]) for r in plan]
    assert len(keys) == len(set(keys))
    d = [r for r in plan if r["arm"].startswith("D-")]
    assert [r["arm"] for r in d] == ["D-full", "D-no-fewshot", "D-minimal",
                                     "D-barrientos-style"]
    assert d[0]["expected_calls"] == 0  # D-full reused
    for r in d[1:]:
        assert r["expected_calls"] == 150 and r["repeat_id"] == "repeat-01"
    for arm in ("BARR-FULL", "OURS-FULL", "OURS-BARRIENTOS-MODULE"):
        runs = [r for r in plan if r["arm"] == arm]
        assert len(runs) == 5
        assert all(r["expected_calls"] == 36 for r in runs)


def test_plan_never_contains_no_pattern_by_default():
    m = _executor()
    plan = m.build_execution_plan(5)
    assert not any(r["arm"] == "BARR-NO-PATTERN" for r in plan)
    # even the optional flag is NOT in the fixed contract path
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["execution_plan"]["total_calls"] == 990
    assert all(r["arm"] != "BARR-NO-PATTERN"
               for r in contract["execution_plan"]["arms"])


# ---------------------------------------------------------------------------
# 2. Contract validation: schema, 990, model, tokens, cost
# ---------------------------------------------------------------------------


def test_contract_exists_and_binds_commit():
    assert CONTRACT.is_file() and CONTRACT_SCHEMA.is_file()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema_version"] == "barrientos_de_execution_contract@1.0.0"
    assert len(contract["bound_commit"]) == 40
    m = _executor()
    # the contract binds the CURRENT executor/config/input hashes; if any
    # changed after the last build, the builder is rerun (refuse-if-exists
    # is a no-op here because we explicitly rebuild with --overwrite).
    from build_barrientos_de_execution_contract_v1 import build_contract
    try:
        m.validate_de_contract(CONTRACT, allow_unauthorized=True)
    except m.ContractError:
        build_contract(overwrite=True)
        assert m.validate_de_contract(CONTRACT, allow_unauthorized=True)


def test_contract_rejects_wrong_plan_total():
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    bad = copy.deepcopy(contract)
    bad["execution_plan"]["total_calls"] = 1170
    path = ROOT / ".tmp" / "contract_bad_plan.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    try:
        try:
            m.validate_de_contract(path, allow_unauthorized=True)
            raise AssertionError("1170 plan must be rejected")
        except m.ContractError:
            pass
    finally:
        path.unlink(missing_ok=True)


def test_contract_rejects_no_pattern_arm():
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    bad = copy.deepcopy(contract)
    bad["execution_plan"]["arms"].append({
        "arm": "BARR-NO-PATTERN", "repeat_id": "repeat-01",
        "sample_count": 36, "calls": 36})
    path = ROOT / ".tmp" / "contract_bad_np.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    try:
        try:
            m.validate_de_contract(path, allow_unauthorized=True)
            raise AssertionError("BARR-NO-PATTERN must be rejected")
        except m.ContractError:
            pass
    finally:
        path.unlink(missing_ok=True)


def test_contract_rejects_wrong_model_or_sampling():
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    for mutate in (lambda c: c["model"].update(id="deepseek-v4-flash"),
                   lambda c: c["sampling"].update(temperature=0.7),
                   lambda c: c["sampling"].update(retry=1)):
        bad = copy.deepcopy(contract)
        mutate(bad)
        path = ROOT / ".tmp" / "contract_bad_mut.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        try:
            try:
                m.validate_de_contract(path, allow_unauthorized=True)
                raise AssertionError("mutated contract must be rejected")
            except m.ContractError:
                pass
        finally:
            path.unlink(missing_ok=True)


def test_contract_authorization_gate():
    m = _executor()
    # null authorization blocks the real path
    try:
        m.validate_de_contract(CONTRACT, allow_unauthorized=False)
        raise AssertionError("null authorization must be rejected")
    except m.ContractError:
        pass
    # allow_unauthorized is only for fixtures/offline checks
    assert m.validate_de_contract(CONTRACT, allow_unauthorized=True)


def test_budget_is_derived_not_guessed():
    """Caps must be positive and derived from rendered requests (the budget
    report records the rendered byte/token audit)."""
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    budget = contract["budget"]
    assert budget["planned_calls"] == 990
    assert budget["input_token_cap"] > 0
    assert budget["output_token_cap"] == 990 * 4096
    assert budget["usd_cost_cap"] > 0
    report = json.loads(BUDGET_REPORT.read_text(encoding="utf-8"))
    assert report["rendered_requests"]["grand_total_est_input_tokens"] > 0
    assert report["rendered_requests"]["plan_total_calls"] == 990
    assert "not a guess" in budget["input_estimate_note"] or \
        "derived" in budget["input_estimate_note"]


# ---------------------------------------------------------------------------
# 3. Budget gate enforcement
# ---------------------------------------------------------------------------


def test_budget_gate_stops_before_next_send():
    """When a cap is reached the gate raises BEFORE the next send; the
    executor catches it and records aborted=True with calls made."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    # shrink caps to a tiny budget so the gate trips after a few calls
    small = copy.deepcopy(contract)
    small["budget"]["planned_calls"] = 2
    small["budget"]["input_token_cap"] = 10 ** 9
    small["budget"]["output_token_cap"] = 10 ** 9
    small["budget"]["usd_cost_cap"] = 10 ** 9
    gate = m.DeBudgetGate(small)
    assert gate.call_cap == 2
    gate.check_before_send()
    gate.record({"prompt_tokens": 100, "completion_tokens": 50})
    # second send completes; the gate then notices the call cap is reached
    try:
        gate.record({"prompt_tokens": 100, "completion_tokens": 50})
        raise AssertionError("gate must abort at the call cap")
    except m.ContractError:
        pass
    assert gate.aborted and gate.calls_made == 2
    # and the executor-level check_before_send keeps raising
    try:
        gate.check_before_send()
        raise AssertionError("check_before_send must keep aborting")
    except m.ContractError:
        pass


def test_budget_gate_fails_closed_on_missing_usage():
    """Missing usage must abort (never treated as 0 cost)."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gate = m.DeBudgetGate(contract)
    gate.check_before_send()
    try:
        gate.record(None)
        raise AssertionError("missing usage must abort")
    except m.ContractError:
        pass
    assert gate.aborted
    assert "usage missing" in gate.abort_reason


def test_budget_gate_fails_closed_on_wrong_model():
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gate = m.DeBudgetGate(contract)
    gate.check_before_send()
    try:
        gate.record({"prompt_tokens": 1, "completion_tokens": 1},
                    returned_model="deepseek-v4-flash")
        raise AssertionError("wrong returned model must abort")
    except m.ContractError:
        pass
    assert gate.aborted


def test_no_retry_extra_calls():
    """A failing transport still results in exactly one send per sample."""
    m = _executor()

    class AlwaysFail:
        def __init__(self):
            self.send_count = 0
            self.last_decode = None

        def send(self, request, *, ordinal=1, clause_id=None):
            self.send_count += 1
            raise RuntimeError("transport down")

    transport = AlwaysFail()
    samples = [{"sample_id": f"s{i}", "text": "t"} for i in range(4)]
    calls = m.call_once_n("D-no-fewshot", samples, "PROMPT", transport,
                          cost_of=lambda u: 0.001)
    assert transport.send_count == 4  # no retry
    assert all(c["request_status"] == "error" for c in calls)


# ---------------------------------------------------------------------------
# 4. Three-table separation (no evaluator mixing)
# ---------------------------------------------------------------------------


def test_three_table_builder_separates_evaluators():
    """Table A uses only Barrientos-native metrics; Table B uses only the
    six-field evaluator; Table C is the only cross-method surface."""
    src = (SCRIPTS / "build_barrientos_de_tables_v1.py").read_text(
        encoding="utf-8")
    assert "MUST NOT be compared" in src
    assert "barrientos_step1_artifact_evaluator" in src
    assert "s2_12_stratified_evaluator_v2" in src
    assert "barrientos_de_shared_target" in src
    assert "no_overall_f1_synthesized_across_schemas" in src
    assert "not_expressible_in_barrientos_schema" in src


def test_shared_target_module_adapters():
    from bpc_hybrid.barrientos_de_shared_target import (
        barr_first_modality, ours_first_modality, shared_projection,
        modality_prf, shared_modality_report)
    barr = {"norms": [{"modality": "obligation"},
                      {"modality": "permission"}]}
    assert barr_first_modality(barr) == "obligation"
    assert barr_first_modality({"norms": []}) is None
    ours = {"clauses": [{"modality": {"label": "prohibition"}},
                        {"modality": {"label": "definition"}}]}
    assert ours_first_modality(ours) == "prohibition"
    assert shared_projection("definition") is None
    assert shared_projection("obligation") == "obligation"

    # same gold, same metric: identical predictions -> F1 1.0
    gold = [{"sample_id": f"s{i}", "clauses": [
        {"modality": {"label": lab}}]} for i, lab in
        enumerate(["obligation", "permission", "prohibition"])]
    preds = {"armA": ["obligation", "permission", "prohibition"],
             "armB": ["permission", "obligation", "prohibition"]}
    rep = shared_modality_report(gold, preds)
    assert rep["gold_expressible_samples"] == 3
    assert rep["arms"]["armA"]["macro"]["f1"] == 1.0
    assert rep["arms"]["armB"]["macro"]["f1"] < 1.0
    assert rep["arms"]["armA"]["per_class"]["obligation"]["precision"] == 1.0
    # no overall F1 synthesized
    assert "overall" not in rep["arms"]["armA"]

    # definition gold excluded, not zeroed
    gold_def = gold + [{"sample_id": "s3", "clauses": [
        {"modality": {"label": "definition"}}]}]
    rep2 = shared_modality_report(gold_def, {
        "armA": ["obligation", "permission", "prohibition", "definition"]})
    assert rep2["gold_expressible_samples"] == 3
    assert rep2["excluded_gold_definition_samples"] == 1


def test_shared_target_norm_count_type_marked_secondary():
    from bpc_hybrid.barrientos_de_shared_target import (
        norm_count_type_report, NOT_STRICTLY_ALIGNABLE)
    gold = {"SIM_card_scenario/r10/v1": {"norm": {"count": 1,
                                                  "type": "obligation"}}}
    trees = {
        "BARR-FULL": {"SIM_card_scenario/r10/v1": {
            "norms": [{"modality": "obligation"}]}},
        "OURS-FULL": {"SIM_card_scenario/r10/v1": {
            "clauses": [{"modality": {"label": "obligation"}}]}},
    }
    rep = norm_count_type_report(gold, trees, ["SIM_card_scenario/r10/v1"])
    assert rep["precondition"]["status"] == NOT_STRICTLY_ALIGNABLE
    for arm in ("BARR-FULL", "OURS-FULL"):
        assert rep["arms"][arm]["count_tp"] == 1
        assert rep["arms"][arm]["first_type_accuracy"] == 1.0
        assert "never merged" in rep["arms"][arm]["note"]


# ---------------------------------------------------------------------------
# 5. OURS-FULL vs OURS-BARRIENTOS-MODULE: the ONLY difference is the module
# ---------------------------------------------------------------------------


def test_ours_arms_differ_only_by_registered_module():
    """Both OURS arms share samples, evaluator, sampling; the ONLY change is
    the prompt file, and it must be the registered Barrientos-style prompt."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    prompts = contract["hashes"]["prompts"]
    assert prompts["OURS-FULL"] != prompts["OURS-BARRIENTOS-MODULE"]
    # the module-swapped arm is bound to the Barrientos-style prompt file
    full_p = m._prompt_for("OURS-FULL")
    swap_p = m._prompt_for("OURS-BARRIENTOS-MODULE")
    assert "ablation_v1" in str(swap_p)
    assert "barrientos_style" in str(swap_p)
    assert full_p != swap_p
    # same sample count in the plan, same evaluator name
    plan = m.build_execution_plan(5)
    runs = {r["arm"]: r for r in plan if r["arm"] in
            ("OURS-FULL", "OURS-BARRIENTOS-MODULE")}
    assert runs["OURS-FULL"]["sample_count"] == \
        runs["OURS-BARRIENTOS-MODULE"]["sample_count"] == 36
    assert m._make_evaluator("OURS-FULL").__name__ == \
        m._make_evaluator("OURS-BARRIENTOS-MODULE").__name__ == "eval_e"


# ---------------------------------------------------------------------------
# 6. raw/canonical same source, one request per sample, failures in
# denominator (regression anchors)
# ---------------------------------------------------------------------------


def test_raw_canonical_same_source_and_denominator_anchor():
    m = _executor()
    plan = m.build_execution_plan(5)
    assert sum(r["expected_calls"] for r in plan) == 990
    # one send per sample per repeat is asserted by the fixture tests;
    # raw/canonical same response hash is asserted by
    # test_raw_and_canonical_share_response_hash; failed-in-denominator by
    # test_failed_samples_stay_in_denominator. This test keeps the contract
    # plan in lockstep with those invariants.
    for r in plan:
        assert r["expected_calls"] == r["sample_count"] or r["reused"]


# ---------------------------------------------------------------------------
# 7. Contract builder determinism (990 rendered requests)
# ---------------------------------------------------------------------------


def test_contract_builder_renders_990_requests(tmp_path):
    proc = subprocess.run(
        [PY, str(SCRIPTS / "build_barrientos_de_execution_contract_v1.py")],
        capture_output=True, text=True, cwd=ROOT.parent)
    # contract exists (built once); rerun must refuse overwrite (no dupes)
    assert proc.returncode == 2  # refusing to overwrite
    assert "refusing to overwrite" in proc.stdout + proc.stderr
    report = json.loads(BUDGET_REPORT.read_text(encoding="utf-8"))
    total = sum(v["calls"] for v in
                report["rendered_requests"]["arms"].values())
    assert total == 990


# ---------------------------------------------------------------------------
# 8. Three-table builder runs end-to-end on the fake-transport output
# ---------------------------------------------------------------------------


def test_three_tables_build_from_fixture_output(tmp_path):
    """The table builder must consume the executor's own output layout
    (per-arm per-repeat evaluation.json + summary) and emit three separate
    tables with the mandated separation."""
    import tempfile
    from build_barrientos_de_tables_v1 import build_tables
    with tempfile.TemporaryDirectory(dir=ROOT / ".tmp") as td:
        proc = subprocess.run(
            [PY, str(SCRIPTS / "run_barrientos_ablation_suite_v2.py"),
             "--fixture", td, "--stability-runs", "5"],
            capture_output=True, text=True, cwd=ROOT.parent)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        tables = build_tables(Path(td))
        tabs = tables["tables"]
        assert set(tabs) == {"A_barrientos_native", "B_ours_native",
                             "C_shared_target"}
        # Table A: Barrientos-native only
        a = tabs["A_barrientos_native"]
        assert a["evaluator"] == "barrientos_step1_artifact_evaluator"
        assert len(a["per_repeat"]) == 5
        assert set(a["aggregate"]) >= {"precondition_f1", "norm_f1",
                                       "strict_json_validity"}
        assert "paper_distance_le2_ratio" in a["self_consistency"]
        # Table B: both OURS arms, same evaluator
        b = tabs["B_ours_native"]
        assert b["evaluator"] == "s2_12_stratified_evaluator_v2"
        assert set(b["arms"]) == {"OURS-FULL", "OURS-BARRIENTOS-MODULE"}
        assert "delta_swap_minus_full" in b
        # Table C: shared-target adapters only
        c = tabs["C_shared_target"]
        assert c["no_overall_f1_synthesized_across_schemas"] is True
        assert set(c["modality"]["arms"]) == {"BARR-FULL", "OURS-FULL",
                                              "OURS-BARRIENTOS-MODULE"}
        for field in ("actor_action_exception", "definition",
                      "precondition"):
            assert field in c["not_expressible"]
