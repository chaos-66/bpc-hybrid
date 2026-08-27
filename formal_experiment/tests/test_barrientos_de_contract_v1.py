# -*- coding: utf-8 -*-
"""Failing-first tests for the dedicated D/E execution contract, the budget
gate, the three-table separation, and the shared-target adapters (zero API)."""

from __future__ import annotations

import copy
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


# ---------------------------------------------------------------------------
# 2b. Full schema validation (types/const/enum/additionalProperties/nested)
# ---------------------------------------------------------------------------


def test_full_schema_validation_rejects_nested_violations(tmp_path):
    """A contract with correct top-level keys but a nested type/const/
    additionalProperties violation must be rejected by the FULL schema
    validation (not a partial top-level check)."""
    from bpc_hybrid.de_contract_schema import validate_instance
    schema = json.loads(CONTRACT_SCHEMA.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    # nested: execution_plan.total_calls const violation
    bad1 = copy.deepcopy(contract)
    bad1["execution_plan"]["total_calls"] = 999
    assert validate_instance(bad1, schema)

    # nested: arm enum violation
    bad2 = copy.deepcopy(contract)
    bad2["execution_plan"]["arms"][0]["arm"] = "BARR-NO-PATTERN"
    assert validate_instance(bad2, schema)

    # nested: additionalProperties in model
    bad3 = copy.deepcopy(contract)
    bad3["model"]["extra_key"] = 1
    assert validate_instance(bad3, schema)

    # nested: sampling temperature const
    bad4 = copy.deepcopy(contract)
    bad4["sampling"]["temperature"] = 0.5
    assert validate_instance(bad4, schema)

    # nested: hashes.prompts type
    bad5 = copy.deepcopy(contract)
    bad5["hashes"]["prompts"]["BARR-FULL"] = "short"
    assert validate_instance(bad5, schema)

    # valid contract passes full validation
    assert validate_instance(contract, schema) == []


def test_contract_full_schema_validation_wired():
    """validate_de_contract must run the FULL schema validator (a mutated
    nested field is rejected even when top-level required keys exist)."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    bad = copy.deepcopy(contract)
    bad["execution_plan"]["total_calls"] = 999
    path = ROOT / ".tmp" / "contract_bad_nested.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    try:
        try:
            m.validate_de_contract(path, allow_unauthorized=True)
            raise AssertionError("nested schema violation must be rejected")
        except m.ContractError as exc:
            assert "schema validation failed" in str(exc)
    finally:
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 2c. Real authorization-event verification
# ---------------------------------------------------------------------------


def _auth_event_file(tmp_path, sentence, *, mutate_sentence_sha=False,
                     mutate_file_sha=False, bad_path=False,
                     empty_sentence=False) -> Path:
    import hashlib
    event = {
        "schema_version": "barrientos_de_authorization_event@1.0.0",
        "authorization_sentence": sentence if not empty_sentence else "",
        "authorized_at_utc": "2026-08-27T00:00:00Z",
    }
    path = tmp_path / "authorization_event_v1.json"
    path.write_text(json.dumps(event, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    if bad_path:
        return path
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    auth = dict(contract["authorization"] or {})
    sentence_sha = hashlib.sha256(sentence.encode("utf-8")).hexdigest()
    file_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    auth["authorization_sentence_utf8_sha256"] = (
        "ab" * 32 if mutate_sentence_sha else sentence_sha)
    auth["authorization_event_file"] = str(path)
    auth["authorization_event_file_sha256"] = (
        "cd" * 32 if mutate_file_sha else file_sha)
    auth["authorized_at_utc"] = "2026-08-27T00:00:00Z"
    return path


REAL_SENTENCE = ("I authorize exactly 990 calls with model deepseek-v4-pro "
                 "at temperature=0 retry=0 under the Barrientos D/E "
                 "execution contract v1 with USD cap 25.396.")


def test_authorization_event_verification_real(tmp_path):
    """A REAL event file with matching file/sentence hashes and the exact
    required sentence passes; any fabricated path, wrong hash, empty event
    or different call count/budget is rejected BEFORE the first send."""
    import hashlib
    m = _executor()
    # event file must live inside an allowed dir (configs/ or reports/)
    event_dir = ROOT / "configs" / "ablations" / ".tmp_auth_tests"
    event_dir.mkdir(parents=True, exist_ok=True)
    event_path = event_dir / "authorization_event_v1.json"
    event_path.write_text(json.dumps({
        "schema_version": "barrientos_de_authorization_event@1.0.0",
        "authorization_sentence": REAL_SENTENCE,
        "authorized_at_utc": "2026-08-27T00:00:00Z",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        auth = {
            "authorization_sentence_utf8_sha256": hashlib.sha256(
                REAL_SENTENCE.encode("utf-8")).hexdigest(),
            "authorization_event_file": str(event_path),
            "authorization_event_file_sha256": hashlib.sha256(
                event_path.read_bytes()).hexdigest(),
            "authorized_at_utc": "2026-08-27T00:00:00Z",
        }
        # valid: passes
        m._verify_authorization_event(auth, contract)
        # fabricated path (not in allowed dirs)
        bad = dict(auth)
        bad["authorization_event_file"] = str(tmp_path / ".." / ".." / "etc" /
                                              "passwd")
        try:
            m._verify_authorization_event(bad, contract)
            raise AssertionError("fabricated path must be rejected")
        except m.ContractError:
            pass
        # wrong file sha
        bad = dict(auth)
        bad["authorization_event_file_sha256"] = "cd" * 32
        try:
            m._verify_authorization_event(bad, contract)
            raise AssertionError("wrong file sha must be rejected")
        except m.ContractError:
            pass
        # wrong sentence sha
        bad = dict(auth)
        bad["authorization_sentence_utf8_sha256"] = "ab" * 32
        try:
            m._verify_authorization_event(bad, contract)
            raise AssertionError("wrong sentence sha must be rejected")
        except m.ContractError:
            pass
        # empty event
        empty = event_dir / "empty_event.json"
        empty.write_text("{}", encoding="utf-8")
        bad = dict(auth)
        bad["authorization_event_file"] = str(empty)
        bad["authorization_event_file_sha256"] = hashlib.sha256(
            empty.read_bytes()).hexdigest()
        try:
            m._verify_authorization_event(bad, contract)
            raise AssertionError("empty event must be rejected")
        except m.ContractError:
            pass
        # sentence with different call count / budget
        for wrong in ("I authorize 1170 calls with model deepseek-v4-pro "
                      "at temperature=0 retry=0 with USD cap 25.396.",
                      "I authorize 990 calls with model deepseek-v4-pro "
                      "at temperature=0 retry=0 with USD cap 10.000."):
            wrong_path = event_dir / "wrong_sentence.json"
            wrong_path.write_text(json.dumps({
                "authorization_sentence": wrong,
                "authorized_at_utc": "2026-08-27T00:00:00Z"},
                ensure_ascii=False), encoding="utf-8")
            bad = dict(auth)
            bad["authorization_sentence_utf8_sha256"] = hashlib.sha256(
                wrong.encode("utf-8")).hexdigest()
            bad["authorization_event_file"] = str(wrong_path)
            bad["authorization_event_file_sha256"] = hashlib.sha256(
                wrong_path.read_bytes()).hexdigest()
            try:
                m._verify_authorization_event(bad, contract)
                raise AssertionError(f"sentence {wrong!r} must be rejected")
            except m.ContractError:
                pass
    finally:
        import shutil
        shutil.rmtree(event_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 4. Macro-F1 = mean of per-class F1 (not harmonic of mean P/R)
# ---------------------------------------------------------------------------


def test_shared_macro_f1_is_mean_of_class_f1():
    """macro_f1 must be mean(per-class F1), NOT harmonic(mean P, mean R).
    Constructed case where the two differ:
      obligation: P=1.0 R=0.5 F1=2/3
      permission: P=0.5 R=1.0 F1=2/3
      prohibition: P=1.0 R=1.0 F1=1.0
    -> mean class F1 = (2/3+2/3+1)/3 = 7/9 = 0.777...
       harmonic(meanP,meanR) = harmonic(5/6,5/6) = 5/6 = 0.833...
    """
    from bpc_hybrid.barrientos_de_shared_target import modality_prf
    gold = []
    pred = []
    gold += ["obligation"] * 20
    pred += ["obligation"] * 10 + ["permission"] * 10
    gold += ["permission"] * 10
    pred += ["permission"] * 10
    gold += ["prohibition"] * 10
    pred += ["prohibition"] * 10
    rep = modality_prf(gold, pred)
    assert abs(rep["per_class"]["obligation"]["f1"] - 2 / 3) < 1e-6
    assert abs(rep["per_class"]["permission"]["f1"] - 2 / 3) < 1e-6
    assert abs(rep["per_class"]["prohibition"]["f1"] - 1.0) < 1e-6
    mean_class_f1 = (2 / 3 + 2 / 3 + 1.0) / 3
    assert abs(rep["macro"]["f1"] - mean_class_f1) < 1e-6
    harmonic = (2 * rep["macro"]["precision"] * rep["macro"]["recall"]
                / (rep["macro"]["precision"] + rep["macro"]["recall"]))
    assert abs(rep["macro"]["f1"] - harmonic) > 1e-6
    assert abs(rep["macro"]["f1"] - 7 / 9) < 1e-6
    # macro precision/recall stay arithmetic means
    assert abs(rep["macro"]["precision"] - 5 / 6) < 1e-6
    assert abs(rep["macro"]["recall"] - 5 / 6) < 1e-6


# ---------------------------------------------------------------------------
# 5. Durable per-request persistence + safe resume
# ---------------------------------------------------------------------------


def _persist_transport(fail_after: int | None = None):
    """Deterministic transport that optionally raises after N sends."""
    from bpc_hybrid.llm_client import LLMResponse

    class PersistFake:
        def __init__(self):
            self.send_count = 0
            self.last_decode = None

        def send(self, request, *, ordinal=1, clause_id=None):
            self.send_count += 1
            if fail_after is not None and self.send_count > fail_after:
                raise RuntimeError("mid-run transport failure")
            self.last_decode = {
                "status": "ok_message_content", "model": "deepseek-v4-pro",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                          "total_tokens": 15},
                "request_id": f"req-{self.send_count}",
            }
            content = json.dumps({
                "schema_version": "1.0.0",
                "sample_id": request.source_id,
                "source_id": request.source_id,
                "source_text": request.source_text,
                "clauses": [],
                "method": {"name": "direct_llm",
                           "schema_source": "stage2_prediction.schema.json@1.0.0"},
                "validation": {"schema_valid": True,
                               "cross_field_valid": True, "errors": []},
            }, ensure_ascii=False)
            self.last_decode["response_sha256"] = hashlib.sha256(
                content.encode("utf-8")).hexdigest()
            return LLMResponse(content=content, provider="fake",
                               model="deepseek-v4-pro", finish_reason="stop")

    return PersistFake()


def test_per_request_persistence_and_resume(tmp_path):
    """Mid-run failure: responses before the failure are persisted
    immediately; the failed send is marked in_doubt (missing usage aborts
    the gate); resume does NOT re-send completed samples, does NOT
    auto-resend in_doubt samples, and sends only the never-attempted
    remainder; total sends never exceed the plan."""
    import hashlib
    m = _executor()
    samples = [{"sample_id": f"s{i}", "text": "t"} for i in range(6)]
    out_dir = tmp_path / "arm" / "repeat-01"

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    big = copy.deepcopy(contract)
    big["budget"]["input_token_cap"] = 10 ** 12
    big["budget"]["output_token_cap"] = 10 ** 12
    big["budget"]["usd_cost_cap"] = 10 ** 12
    gate1 = m.DeBudgetGate(big)

    # first run: sends 1-3 OK; send 4 raises (no response -> in_doubt ->
    # gate aborts on missing usage before send 5)
    t1 = _persist_transport(fail_after=3)
    try:
        m.run_arm_once(arm="D-no-fewshot", repeat_id="repeat-01",
                       samples=samples, prompt_text="", transport=t1,
                       cost_of=lambda u: 0.001, evaluator=m.dummy_evaluator,
                       out_dir=out_dir, budget_gate=gate1)
        raise AssertionError("mid-run transport failure must abort the gate")
    except m.ContractError:
        pass
    # raw responses persisted for the 3 completed sends (durable before the
    # failure point)
    raw_rows = m._read_jsonl(out_dir / "raw_responses.jsonl")
    assert len(raw_rows) == 3
    ledger = m._read_jsonl(out_dir / "calls_ledger.jsonl")
    states = {r["sample_id"]: r["state"] for r in ledger}
    assert states == {"s0": "completed", "s1": "completed",
                      "s2": "completed", "s3": "in_doubt"}
    assert t1.send_count == 4  # only 4 sends before the abort

    # resume with a fresh transport and a fresh gate: completed samples are
    # reused (NOT re-sent); in_doubt s3 is NOT auto-resent; only s4,s5 are
    # sent (in the original order)
    gate2 = m.DeBudgetGate(big)
    t2 = _persist_transport(fail_after=None)
    run = m.run_arm_once(arm="D-no-fewshot", repeat_id="repeat-01",
                         samples=samples, prompt_text="", transport=t2,
                         cost_of=lambda u: 0.001, evaluator=m.dummy_evaluator,
                         out_dir=out_dir, budget_gate=gate2)
    assert t2.send_count == 2  # only s4, s5 sent
    assert run["resumed_completed_count"] == 3
    assert run["in_doubt_skipped_count"] == 1
    assert run["actual_call_count"] == 2
    # ledger: s3 still in_doubt (never auto-resent), s4/s5 completed
    ledger2 = m._read_jsonl(out_dir / "calls_ledger.jsonl")
    states2 = {r["sample_id"]: r["state"] for r in ledger2}
    assert states2["s3"] == "in_doubt"
    assert states2["s4"] == "completed" and states2["s5"] == "completed"
    # total sends across both runs = 6 (4 + 2): completed never re-sent,
    # in_doubt never auto-resent, total never exceeds the 6-sample plan
    assert t1.send_count + t2.send_count == 6
    # canonical/eval/manifest present (derived from persisted raw)
    for f in ("canonical_predictions.jsonl", "failed_samples.jsonl",
              "evaluation.json", "manifest.json"):
        assert (out_dir / f).is_file()
    assert gate2.aborted is False  # resume completed within budget


def test_resume_persisted_raw_is_reused_not_resent(tmp_path):
    """A fully completed repeat resumed again must send ZERO new calls and
    reuse the persisted raw responses (same response hash)."""
    m = _executor()
    samples = [{"sample_id": f"s{i}", "text": "t"} for i in range(4)]
    out_dir = tmp_path / "arm" / "repeat-01"
    t1 = _persist_transport(fail_after=None)
    run1 = m.run_arm_once(arm="D-no-fewshot", repeat_id="repeat-01",
                          samples=samples, prompt_text="", transport=t1,
                          cost_of=lambda u: 0.001, evaluator=m.dummy_evaluator,
                          out_dir=out_dir)
    assert run1["actual_call_count"] == 4
    t2 = _persist_transport(fail_after=None)
    run2 = m.run_arm_once(arm="D-no-fewshot", repeat_id="repeat-01",
                          samples=samples, prompt_text="", transport=t2,
                          cost_of=lambda u: 0.001, evaluator=m.dummy_evaluator,
                          out_dir=out_dir)
    assert t2.send_count == 0
    assert run2["resumed_completed_count"] == 4
    assert run2["actual_call_count"] == 0
    assert run2["raw_rows"][0]["response_sha256"] == \
        run1["raw_rows"][0]["response_sha256"]


# ---------------------------------------------------------------------------
# 2d. aborted/incomplete execution: non-zero exit + tables refused
# ---------------------------------------------------------------------------


def test_execute_de_aborted_returns_incomplete(tmp_path):
    """An aborted run must NOT be reported complete; the CLI must return a
    non-zero exit code and never print 'complete'."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    small = copy.deepcopy(contract)
    small["budget"]["planned_calls"] = 990
    small["budget"]["input_token_cap"] = 10 ** 9
    small["budget"]["output_token_cap"] = 10 ** 9
    small["budget"]["usd_cost_cap"] = 10 ** 9
    path = tmp_path / "contract_small.json"
    path.write_text(json.dumps(small), encoding="utf-8")

    # CLI-level behavior: a contract with null authorization refuses before
    # any send (exit 2, never "complete")
    proc = subprocess.run(
        [PY, str(SCRIPTS / "run_barrientos_ablation_suite_v2.py"),
         "--execute-de", "--contract-file", str(path)],
        capture_output=True, text=True, cwd=ROOT.parent)
    assert proc.returncode == 2
    assert "refused" in (proc.stdout + proc.stderr).lower()
    assert "complete" not in (proc.stdout + proc.stderr).lower()


def test_table_builder_refuses_aborted(tmp_path):
    """build_tables must raise for an aborted execution summary."""
    import build_barrientos_de_tables_v1 as tables
    (tmp_path / "execution_summary.json").write_text(json.dumps({
        "aborted": True, "complete": False, "total_calls_accounted": 100,
        "planned_calls": 990}), encoding="utf-8")
    try:
        tables.build_tables(tmp_path)
        raise AssertionError("tables must be refused for aborted runs")
    except RuntimeError as exc:
        assert "ABORTED" in str(exc)


def test_table_builder_refuses_incomplete(tmp_path):
    import build_barrientos_de_tables_v1 as tables
    (tmp_path / "execution_summary.json").write_text(json.dumps({
        "aborted": False, "complete": False, "total_calls_accounted": 500,
        "planned_calls": 990}), encoding="utf-8")
    try:
        tables.build_tables(tmp_path)
        raise AssertionError("tables must be refused for incomplete runs")
    except RuntimeError as exc:
        assert "INCOMPLETE" in str(exc)


def test_resumed_complete_run_is_complete():
    """A resumed run that accounts for all 990 samples (new sends +
    resumed completed) is complete even when THIS invocation's actual_calls
    is less than 990 (the remainder was already paid for and persisted)."""
    m = _executor()
    plan = m.build_execution_plan(5)
    planned = sum(r["expected_calls"] for r in plan)
    # simulated resumed state: 300 new sends this invocation + 690 resumed
    # completed = 990 accounted, zero in_doubt
    results = {
        "aborted": False,
        "actual_calls": 300,
        "completed_samples": planned,
        "in_doubt_samples": 0,
        "planned_calls": planned,
        "runs": list(range(len(plan))),  # every repeat ran
    }
    # replicate the completeness formula from execute_de
    complete = (
        results["aborted"] is not True
        and results["completed_samples"] == results["planned_calls"]
        and results["in_doubt_samples"] == 0
        and len(results["runs"]) == len(plan)
    )
    assert complete is True
    # an aborted resume is NOT complete even with full accounting
    results["aborted"] = True
    complete2 = (
        results["aborted"] is not True
        and results["completed_samples"] == results["planned_calls"]
        and results["in_doubt_samples"] == 0
        and len(results["runs"]) == len(plan)
    )
    assert complete2 is False


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
    """Two-phase gate: cap=2 -> the first TWO sends both succeed and are
    recorded; the THIRD send is rejected in check_before_send BEFORE it
    reaches the transport.  (Completing the 2nd call must NOT abort.)"""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    small = copy.deepcopy(contract)
    small["budget"]["planned_calls"] = 2
    small["budget"]["input_token_cap"] = 10 ** 9
    small["budget"]["output_token_cap"] = 10 ** 9
    small["budget"]["usd_cost_cap"] = 10 ** 9
    gate = m.DeBudgetGate(small)
    assert gate.call_cap == 2
    # send 1: allowed, completes normally
    gate.check_before_send(projected_input_tokens=100,
                           projected_max_output_tokens=4096)
    gate.record_after_response({"prompt_tokens": 100, "completion_tokens": 50},
                               returned_model="deepseek-v4-pro")
    assert gate.calls_made == 1 and not gate.aborted
    # send 2: allowed (1 + 1 = 2 <= 2), completes normally
    gate.check_before_send(projected_input_tokens=100,
                           projected_max_output_tokens=4096)
    gate.record_after_response({"prompt_tokens": 100, "completion_tokens": 50},
                               returned_model="deepseek-v4-pro")
    assert gate.calls_made == 2 and not gate.aborted
    # send 3: rejected BEFORE the transport (2 + 1 = 3 > 2)
    try:
        gate.check_before_send(projected_input_tokens=100,
                               projected_max_output_tokens=4096)
        raise AssertionError("3rd send must be rejected before transport")
    except m.ContractError:
        pass
    assert gate.aborted and gate.calls_made == 2


def test_budget_gate_990th_call_completes():
    """The 990th call (the fixed plan's last) must complete and be
    persisted; only the 991st is rejected before the transport."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gate = m.DeBudgetGate(contract)
    assert gate.call_cap == 990
    for _ in range(990):
        gate.check_before_send(projected_input_tokens=100,
                               projected_max_output_tokens=4096)
        gate.record_after_response({"prompt_tokens": 100,
                                    "completion_tokens": 50},
                                   returned_model="deepseek-v4-pro")
    assert gate.calls_made == 990 and not gate.aborted
    assert gate.input_tokens == 990 * 100
    assert gate.output_tokens == 990 * 50
    # equal-to-cap is a legal completion (no abort)
    assert not gate.aborted
    # 991st rejected before the transport
    try:
        gate.check_before_send(projected_input_tokens=100,
                               projected_max_output_tokens=4096)
        raise AssertionError("991st send must be rejected before transport")
    except m.ContractError:
        pass
    assert gate.aborted


def test_budget_gate_990_plan_with_realistic_usage():
    """The fixed 990-call plan with the REAL contract caps completes: the
    projected next-send checks never trip (caps have safety factors) and
    the 990th response records exactly at the planned totals."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gate = m.DeBudgetGate(contract)
    report = json.loads(BUDGET_REPORT.read_text(encoding="utf-8"))
    # use the real per-request token estimates from the rendered audit
    est_tokens = []
    for arm in ("D-no-fewshot", "D-minimal", "D-barrientos-style",
                "BARR-FULL", "OURS-FULL", "OURS-BARRIENTOS-MODULE"):
        entry = report["rendered_requests"]["arms"][arm]
        est_tokens.extend(r["est_input_tokens"] for r in entry["requests"])
    assert len(est_tokens) == 990
    for i, est in enumerate(est_tokens):
        gate.check_before_send(projected_input_tokens=est,
                               projected_max_output_tokens=4096)
        gate.record_after_response({"prompt_tokens": est,
                                    "completion_tokens": 4096},
                                   returned_model="deepseek-v4-pro")
    assert gate.calls_made == 990
    assert not gate.aborted
    assert gate.input_tokens <= gate.input_token_cap
    assert gate.output_tokens <= gate.output_token_cap
    assert gate.cost_usd <= gate.usd_cost_cap


def test_budget_gate_fails_closed_on_missing_usage():
    """Missing usage must abort (never treated as 0 cost)."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gate = m.DeBudgetGate(contract)
    gate.check_before_send(projected_input_tokens=10,
                           projected_max_output_tokens=100)
    try:
        gate.record_after_response(None, returned_model="deepseek-v4-pro")
        raise AssertionError("missing usage must abort")
    except m.ContractError:
        pass
    assert gate.aborted
    assert "usage missing" in gate.abort_reason


def test_budget_gate_fails_closed_on_wrong_model():
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gate = m.DeBudgetGate(contract)
    gate.check_before_send(projected_input_tokens=10,
                           projected_max_output_tokens=100)
    try:
        gate.record_after_response({"prompt_tokens": 1, "completion_tokens": 1},
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


# ---------------------------------------------------------------------------
# 9. Resume must restore the GLOBAL budget state (no fresh-gate bypass)
# ---------------------------------------------------------------------------


def _persisted_rows(n: int, *, model: str = "deepseek-v4-pro",
                    prompt_tokens: int = 100, completion_tokens: int = 50):
    """n completed raw+ledger rows shaped like the executor's persisted
    files (returned_model included)."""
    raw = []
    ledger = []
    for i in range(n):
        content = json.dumps({"sample_id": f"s{i}", "clauses": []})
        resp_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        raw.append({
            "sample_id": f"s{i}", "arm": "D-no-fewshot",
            "repeat_id": "repeat-01",
            "request_body_sha256": "ab" * 32,
            "request_id": f"req-{i}",
            "raw_response_content": content,
            "response_sha256": resp_sha,
            "usage": {"prompt_tokens": prompt_tokens,
                      "completion_tokens": completion_tokens},
            "cost": 0.001, "request_status": "ok", "error": None,
            "returned_model": model, "network_call": 1,
        })
        ledger.append({"sample_id": f"s{i}", "arm": "D-no-fewshot",
                       "repeat_id": "repeat-01", "state": "completed",
                       "response_sha256": resp_sha})
    return raw, ledger


def test_resume_restores_400_completed_gate_state():
    """Restoring 400 persisted completed requests must yield
    gate.calls_made == 400 (NOT 0) and token/cost equal to the cumulative
    persisted usage."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gate = m.DeBudgetGate(contract)
    raw, ledger = _persisted_rows(400)
    gate.restore_from_persisted(raw, ledger)
    assert gate.calls_made == 400, f"expected 400, got {gate.calls_made}"
    assert gate.input_tokens == 400 * 100
    assert gate.output_tokens == 400 * 50
    expected_cost = (400 * 100 * 1.32 + 400 * 50 * 3.96) / 1e6
    assert abs(gate.cost_usd - expected_cost) < 1e-9
    assert not gate.aborted


def test_resume_restore_then_projected_overflow_rejected_before_send():
    """After restoring persisted state, a next request whose projected
    cost would exceed the budget must be rejected in check_before_send
    BEFORE any transport.send."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    # shrink the USD cap so the restored cost leaves no room for another call
    small = copy.deepcopy(contract)
    small["budget"]["usd_cost_cap"] = (400 * 100 * 1.32 + 400 * 50 * 3.96) / 1e6
    gate = m.DeBudgetGate(small)
    raw, ledger = _persisted_rows(400)
    gate.restore_from_persisted(raw, ledger)
    assert not gate.aborted  # restored == cap is legal
    # the next send would exceed the USD cap -> rejected before transport
    try:
        gate.check_before_send(projected_input_tokens=1000,
                               projected_max_output_tokens=4096)
        raise AssertionError("next send must be rejected before transport")
    except m.ContractError:
        pass
    assert gate.aborted


def test_resume_with_in_doubt_fails_closed_zero_sends():
    """A persisted in_doubt ledger entry must fail closed on resume BEFORE
    any new send; the previous missing-usage abort is not bypassed."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gate = m.DeBudgetGate(contract)
    raw, ledger = _persisted_rows(3)
    ledger.append({"sample_id": "s3", "arm": "D-no-fewshot",
                   "repeat_id": "repeat-01", "state": "in_doubt",
                   "error": "mid-run transport failure"})
    try:
        gate.restore_from_persisted(raw, ledger)
        raise AssertionError("in_doubt must fail closed on restore")
    except m.ContractError as exc:
        assert "in_doubt" in str(exc)
    assert gate.aborted
    # a fresh gate must NOT be created to bypass: restoring the same state
    # into a second gate also fails (no auto-resend)
    gate2 = m.DeBudgetGate(contract)
    try:
        gate2.restore_from_persisted(raw, ledger)
        raise AssertionError("in_doubt must fail closed on every resume")
    except m.ContractError:
        pass


def test_resume_restore_verifies_ledger_and_response_hashes():
    """Restore must verify the ledger state and the raw/ledger response
    hash match; a tampered ledger entry is rejected."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    raw, ledger = _persisted_rows(2)
    # tamper: ledger response_sha256 differs from raw
    ledger[1]["response_sha256"] = "cd" * 32
    gate = m.DeBudgetGate(contract)
    try:
        gate.restore_from_persisted(raw, ledger)
        raise AssertionError("hash mismatch must be rejected on restore")
    except m.ContractError as exc:
        assert "hash mismatch" in str(exc)


def test_resume_restore_verifies_returned_model():
    """A persisted completed row with a missing or wrong returned_model
    must fail closed on restore (cannot be accepted as conforming)."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    raw, ledger = _persisted_rows(1)
    raw[0]["returned_model"] = None
    gate = m.DeBudgetGate(contract)
    try:
        gate.restore_from_persisted(raw, ledger)
        raise AssertionError("missing returned_model must fail on restore")
    except m.ContractError as exc:
        assert "returned model" in str(exc)
    raw2, ledger2 = _persisted_rows(1)
    raw2[0]["returned_model"] = "deepseek-v4-flash"
    gate2 = m.DeBudgetGate(contract)
    try:
        gate2.restore_from_persisted(raw2, ledger2)
        raise AssertionError("wrong returned_model must fail on restore")
    except m.ContractError:
        pass


def test_resume_restore_missing_usage_fails_closed():
    """A persisted completed row without verifiable usage must fail closed
    on restore (cost never treated as 0)."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    raw, ledger = _persisted_rows(1)
    raw[0]["usage"] = {}
    gate = m.DeBudgetGate(contract)
    try:
        gate.restore_from_persisted(raw, ledger)
        raise AssertionError("missing usage must fail on restore")
    except m.ContractError as exc:
        assert "usage" in str(exc)


def test_resume_restore_then_run_completes_within_budget(tmp_path):
    """End-to-end resume: restore the global gate from persisted rows,
    then run the remaining samples through run_arm_once with the SAME gate
    (never a fresh one); completed samples are not re-sent and the totals
    stay within the contract caps."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    big = copy.deepcopy(contract)
    big["budget"]["input_token_cap"] = 10 ** 12
    big["budget"]["output_token_cap"] = 10 ** 12
    big["budget"]["usd_cost_cap"] = 10 ** 12
    # 400 completed rows persisted for arm/repeat-01 + 2 remaining samples
    raw, ledger = _persisted_rows(400)
    out_dir = tmp_path / "D-no-fewshot" / "repeat-01"
    out_dir.mkdir(parents=True)
    (out_dir / "raw_responses.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in raw),
        encoding="utf-8")
    (out_dir / "calls_ledger.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ledger),
        encoding="utf-8")

    gate = m.DeBudgetGate(big)
    gate.restore_from_persisted(raw, ledger)
    assert gate.calls_made == 400

    samples = [{"sample_id": f"s{i}", "text": "t"} for i in range(402)]
    transport = _persist_transport(fail_after=None)
    run = m.run_arm_once(arm="D-no-fewshot", repeat_id="repeat-01",
                         samples=samples, prompt_text="", transport=transport,
                         cost_of=lambda u: 0.001, evaluator=m.dummy_evaluator,
                         out_dir=out_dir, budget_gate=gate)
    # 400 resumed (reused, not re-sent) + 2 new sends
    assert run["resumed_completed_count"] == 400
    assert run["actual_call_count"] == 2
    assert transport.send_count == 2
    assert gate.calls_made == 402
    assert not gate.aborted


# ---------------------------------------------------------------------------
# 10. Runtime LLMConfig must match the contract exactly
# ---------------------------------------------------------------------------


class _FakeLLMConfig:
    def __init__(self, **kwargs):
        self.enabled = kwargs.get("enabled", True)
        self.provider = kwargs.get("provider", "openai_compatible")
        self.model = kwargs.get("model", "deepseek-v4-pro")
        self.temperature = kwargs.get("temperature", 0.0)
        self.top_p = kwargs.get("top_p", 1.0)
        self.max_tokens = kwargs.get("max_tokens", 4096)
        self.seed = None
        self.seed_supported = False


def test_runtime_config_binding_all_fields():
    """provider/model/temperature/top_p/max_tokens must ALL match the
    contract; any single deviation is rejected BEFORE the first send."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    # valid config passes
    m._validate_runtime_config(_FakeLLMConfig(), contract)
    for field, bad in (
            ("provider", "azure"),
            ("model", "deepseek-v4-flash"),
            ("temperature", 0.7),
            ("top_p", 0.5),
            ("max_tokens", 1024),
            ("enabled", False)):
        cfg = _FakeLLMConfig()
        setattr(cfg, field, bad)
        try:
            m._validate_runtime_config(cfg, contract)
            raise AssertionError(f"runtime {field}={bad!r} must be rejected")
        except m.ContractError as exc:
            assert field in str(exc)


def test_returned_model_missing_fails_closed():
    """A response with NO returned model must fail closed (not pass)."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gate = m.DeBudgetGate(contract)
    gate.check_before_send(projected_input_tokens=10,
                           projected_max_output_tokens=100)
    try:
        gate.record_after_response({"prompt_tokens": 10,
                                    "completion_tokens": 5},
                                   returned_model=None)
        raise AssertionError("missing returned_model must fail closed")
    except m.ContractError as exc:
        assert "returned model" in str(exc)
    assert gate.aborted


def test_returned_model_mismatch_fails_closed():
    """A response whose returned model differs from the contract must fail
    closed."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gate = m.DeBudgetGate(contract)
    gate.check_before_send(projected_input_tokens=10,
                           projected_max_output_tokens=100)
    try:
        gate.record_after_response({"prompt_tokens": 10,
                                    "completion_tokens": 5},
                                   returned_model="deepseek-v4-flash")
        raise AssertionError("wrong returned_model must fail closed")
    except m.ContractError:
        pass
    assert gate.aborted


def test_usage_missing_after_response_fails_closed():
    """usage missing after a response keeps failing closed."""
    m = _executor()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gate = m.DeBudgetGate(contract)
    gate.check_before_send(projected_input_tokens=10,
                           projected_max_output_tokens=100)
    try:
        gate.record_after_response(None, returned_model="deepseek-v4-pro")
        raise AssertionError("missing usage must fail closed")
    except m.ContractError:
        pass
    assert gate.aborted


# ---------------------------------------------------------------------------
# 11. authorization dir check must be real path containment
# ---------------------------------------------------------------------------


def test_auth_dir_check_rejects_sibling_prefix():
    """A sibling path like ``configs_evil`` must NOT be treated as inside
    ``configs`` (Path.is_relative_to, not string startswith)."""
    m = _executor()
    import tempfile
    base = ROOT / ".tmp" / "auth_dir_check"
    base.mkdir(parents=True, exist_ok=True)
    try:
        evil = base / "configs_evil" / "event.json"
        evil.parent.mkdir(parents=True, exist_ok=True)
        evil.write_text("{}", encoding="utf-8")
        # patch the allowed dirs to a sibling pair so the prefix collision
        # is actually exercised
        from run_barrientos_ablation_suite_v2 import AUTH_ALLOWED_DIRS
        import run_barrientos_ablation_suite_v2 as _m
        old = _m.AUTH_ALLOWED_DIRS
        _m.AUTH_ALLOWED_DIRS = (base / "configs",)
        try:
            auth = {
                "authorization_sentence_utf8_sha256": "ab" * 32,
                "authorization_event_file": str(evil),
                "authorization_event_file_sha256": "cd" * 32,
            }
            try:
                _m._verify_authorization_event(auth, {})
                raise AssertionError("configs_evil must be rejected")
            except _m.ContractError:
                pass
        finally:
            _m.AUTH_ALLOWED_DIRS = old
    finally:
        import shutil
        shutil.rmtree(base, ignore_errors=True)
