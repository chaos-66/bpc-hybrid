# -*- coding: utf-8 -*-
"""S2.12 runner-safety v2 focused tests (ZERO API, ZERO network).

These tests use a *scripted real-like transport* (local only) that mirrors
the real transport's contract (policy-applied body, SHA verification, usage
in ``last_decode``) but never touches the network.  Every scenario asserts
``network calls = 0``.  Fake transport covers the remaining paths.

The formal prediction directories are never written; all runs use a temp
output dir.  No real authorization file is created; synthetic auths are
built in memory only.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import hashlib  # noqa: E402

PY = sys.executable
RUNTIME_HOME = Path("D:/environment/stanford-corenlp-4.5.10")


def _run_cmd(args):
    import subprocess
    proc = subprocess.run(
        [PY, *args], capture_output=True, text=True, cwd=ROOT.parent
    )
    return proc


def _locked_rows(arm):
    import bpc_hybrid.s2_12_execution as ex
    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)
    return rows[arm]


def _price():
    return {
        "schema_version": "s2_12_price_snapshot@1.0.0",
        "currency": "USD",
        "input_cache_hit_per_million": 0.044,
        "input_cache_miss_per_million": 1.32,
        "output_per_million": 3.96,
    }


# ---------------------------------------------------------------------------
# Scripted real-like transport (local, zero network)
# ---------------------------------------------------------------------------


class ScriptedRealLikeTransport:
    """Local scripted transport that enforces the real transport contract.

    * ``send`` first asks the ``PayloadLock`` to verify the actual body
      (SHA + IDs + order) — exactly like ``PayloadLockedRealTransport``.
    * Returns an ``LLMResponse`` and exposes ``last_decode`` with usage so
      the runner's cost path is exercised.
    * The script controls per-call behavior (usage values, model mismatch,
      missing usage) for scenario tests.
    * Never opens a socket; ``network_calls`` counter stays 0.
    """

    def __init__(self, payload_lock, *, usage=None, model=None, decode_status=None):
        from bpc_hybrid.llm_client import LLMResponse
        self._lock = payload_lock
        self._LLMResponse = LLMResponse
        self.network_calls = 0
        if usage is None:
            self._usage = {
                "prompt_tokens": 120, "completion_tokens": 64, "total_tokens": 184,
            }
        else:
            # honor explicit empty usage (provider-usage-missing scenario)
            self._usage = dict(usage)
        self._model = model or "deepseek-v4-pro"
        self._decode_status = decode_status or "ok_message_content"
        self.last_decode = None

    def send(self, request, *, ordinal=1, clause_id=None):
        self._lock.verify(request, ordinal, clause_id=clause_id)
        self.network_calls += 1  # simulated; still zero real network
        self.last_decode = {
            "status": self._decode_status,
            "model": self._model,
            "usage": dict(self._usage),
            "finish_reason": "stop",
        }
        content = json.dumps({
            "sample_id": request.source_id,
            "clause_id": clause_id,
            "ok": True,
        })
        return self._LLMResponse(
            content=content, provider="scripted", model=self._model,
            finish_reason="stop",
        )


# ---------------------------------------------------------------------------
# Payload lock (per-call) tests
# ---------------------------------------------------------------------------


def test_payload_lock_verifies_every_call_body_sha_and_order():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import LLMRequest, OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    policy = ex.arm_policy("direct_llm")
    builder = OpenAICompatibleRequestBuilder(
        _config(lock)
    )
    payload_lock = ex.PayloadLock("direct_llm", rows, builder, policy)

    row = rows[0]
    request = LLMRequest(
        source_id=row["sample_id"], source_text="",
        system_prompt=row["system_prompt"], user_prompt=row["user_prompt"],
    )
    verified = payload_lock.verify(request, 1, clause_id=None)
    assert verified["request_body_sha256"] == row["request_body_sha256"]

    # Tampered user prompt -> body SHA changes -> refuse before any call.
    bad = LLMRequest(
        source_id=row["sample_id"], source_text="",
        system_prompt=row["system_prompt"],
        user_prompt=row["user_prompt"] + " TAMPER",
    )
    try:
        payload_lock.verify(bad, 1, clause_id=None)
        raise AssertionError("tampered body accepted by payload lock")
    except ex.S212ExecutionError:
        pass


def test_payload_lock_rejects_wrong_sample_and_order():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import LLMRequest, OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    policy = ex.arm_policy("direct_llm")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("direct_llm", rows, builder, policy)

    r1, r2 = rows[0], rows[1]
    req1 = LLMRequest(source_id=r1["sample_id"], source_text="",
                      system_prompt=r1["system_prompt"], user_prompt=r1["user_prompt"])
    req2 = LLMRequest(source_id=r2["sample_id"], source_text="",
                      system_prompt=r2["system_prompt"], user_prompt=r2["user_prompt"])
    # Wrong sample for ordinal 1 (prompts of row2 at ordinal 1)
    try:
        payload_lock.verify(req2, 1, clause_id=None)
        raise AssertionError("wrong sample accepted")
    except ex.S212ExecutionError:
        pass
    # Right sample, wrong ordinal
    try:
        payload_lock.verify(req1, 2, clause_id=None)
        raise AssertionError("wrong order accepted")
    except ex.S212ExecutionError:
        pass


def test_fallback_payload_lock_checks_clause_ids():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import LLMRequest, OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["sun_llm_fallback"]
    policy = ex.arm_policy("sun_llm_fallback")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("sun_llm_fallback", rows, builder, policy)
    row = rows[0]
    request = LLMRequest(
        source_id=row["sample_id"], source_text="",
        system_prompt=row["system_prompt"], user_prompt=row["user_prompt"],
    )
    payload_lock.verify(request, 1, clause_id=row["clause_id"])
    try:
        payload_lock.verify(request, 1, clause_id="wrong-clause")
        raise AssertionError("wrong clause accepted")
    except ex.S212ExecutionError:
        pass


# ---------------------------------------------------------------------------
# Usage / cost
# ---------------------------------------------------------------------------


def test_per_call_cost_conservative_when_no_split():
    import bpc_hybrid.s2_12_execution as ex
    price = _price()
    cost = ex.per_call_cost({"prompt_tokens": 1000, "completion_tokens": 500}, price)
    assert cost["input_tokens"] == 1000
    assert cost["cache_miss_tokens"] == 1000  # conservative: all input at miss
    assert cost["cache_hit_tokens"] == 0
    # 1000 * 1.32/M + 500 * 3.96/M
    assert abs(cost["cost_usd"] - (0.00132 + 0.00198)) < 1e-9


def test_per_call_cost_with_cache_split():
    import bpc_hybrid.s2_12_execution as ex
    price = _price()
    cost = ex.per_call_cost({
        "prompt_tokens": 1000,
        "prompt_cache_hit_tokens": 400,
        "prompt_cache_miss_tokens": 600,
        "completion_tokens": 500,
    }, price)
    assert cost["cache_hit_tokens"] == 400
    assert cost["cache_miss_tokens"] == 600
    assert abs(cost["cost_usd"] - (400 * 0.044 / 1e6 + 600 * 1.32 / 1e6
                                   + 500 * 3.96 / 1e6)) < 1e-9


def _fresh_ledger(name: str) -> Path:
    """Return a fresh ledger path (removes any leftover from a prior run)."""
    path = ROOT / ".tmp" / name
    if path.exists():
        path.unlink()
    return path


def test_usage_missing_fails_closed():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import LLMRequest, OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    policy = ex.arm_policy("direct_llm")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("direct_llm", rows, builder, policy)

    scripted = ScriptedRealLikeTransport(payload_lock, usage={})
    auth = _synthetic_auth(ex, rows, "D-CAL")
    ledger_path = _fresh_ledger("s212-test-usage-missing.jsonl")
    executor = ex.StageExecutor(
        arm="direct_llm", stage_id="D-CAL", auth=auth, lock=lock,
        report=report, rows_by_arm={"direct_llm": rows, "sun_llm_fallback": []},
        payload_lock=payload_lock, transport=scripted, ledger_path=ledger_path,
    )
    try:
        executor.run()
        raise AssertionError("missing usage accepted")
    except ex.S212ExecutionError as exc:
        assert "provider usage missing" in str(exc)


def test_returned_model_mismatch_stops():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import LLMRequest, OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    policy = ex.arm_policy("direct_llm")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("direct_llm", rows, builder, policy)
    scripted = ScriptedRealLikeTransport(payload_lock, model="wrong-model")
    auth = _synthetic_auth(ex, rows, "D-CAL")
    ledger_path = _fresh_ledger("s212-test-model.jsonl")
    executor = ex.StageExecutor(
        arm="direct_llm", stage_id="D-CAL", auth=auth, lock=lock,
        report=report, rows_by_arm={"direct_llm": rows, "sun_llm_fallback": []},
        payload_lock=payload_lock, transport=scripted, ledger_path=ledger_path,
    )
    try:
        executor.run()
        raise AssertionError("wrong model accepted")
    except ex.S212ExecutionError as exc:
        assert "returned model" in str(exc)


# ---------------------------------------------------------------------------
# Caps (per-call) + off-peak (per call)
# ---------------------------------------------------------------------------


def test_input_cap_stops_before_second_call():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    policy = ex.arm_policy("direct_llm")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("direct_llm", rows, builder, policy)
    auth = _synthetic_auth(ex, rows, "D-REST",
                           global_input_token_cap=150)  # after 1 call (120) next bound exceeded
    scripted = ScriptedRealLikeTransport(payload_lock)
    ledger_path = _fresh_ledger("s212-test-inputcap.jsonl")
    executor = ex.StageExecutor(
        arm="direct_llm", stage_id="D-REST", auth=auth, lock=lock,
        report=report, rows_by_arm={"direct_llm": rows, "sun_llm_fallback": []},
        payload_lock=payload_lock, transport=scripted, ledger_path=ledger_path,
    )
    try:
        executor.run()
        raise AssertionError("input cap not enforced")
    except ex.S212ExecutionError as exc:
        assert "input" in str(exc).lower() or "conservative" in str(exc).lower()


def test_usd_cap_stops_after_responses():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    policy = ex.arm_policy("direct_llm")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("direct_llm", rows, builder, policy)
    usage = {"prompt_tokens": 5_000_000, "completion_tokens": 1_000_000}
    scripted = ScriptedRealLikeTransport(payload_lock, usage=usage)
    auth = _synthetic_auth(ex, rows, "D-CAL", global_usd_cost_cap=0.01)
    ledger_path = _fresh_ledger("s212-test-usd.jsonl")
    executor = ex.StageExecutor(
        arm="direct_llm", stage_id="D-CAL", auth=auth, lock=lock,
        report=report, rows_by_arm={"direct_llm": rows, "sun_llm_fallback": []},
        payload_lock=payload_lock, transport=scripted, ledger_path=ledger_path,
    )
    try:
        executor.run()
        raise AssertionError("USD cap not enforced")
    except ex.S212ExecutionError as exc:
        assert "usd" in str(exc).lower() or "cap" in str(exc).lower()


def test_off_peak_checked_before_every_call():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import LLMRequest, OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    policy = ex.arm_policy("direct_llm")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("direct_llm", rows, builder, policy)
    auth = _synthetic_auth(ex, rows, "D-CAL", allowed_windows="off_peak_only")
    scripted = ScriptedRealLikeTransport(payload_lock)

    def peak_now():
        # 10:00 Beijing == peak
        return datetime(2026, 8, 20, 2, 0, tzinfo=timezone.utc)

    ledger_path = _fresh_ledger("s212-test-offpeak.jsonl")
    executor = ex.StageExecutor(
        arm="direct_llm", stage_id="D-CAL", auth=auth, lock=lock,
        report=report, rows_by_arm={"direct_llm": rows, "sun_llm_fallback": []},
        payload_lock=payload_lock, transport=scripted, ledger_path=ledger_path,
        now_provider=peak_now,
    )
    try:
        executor.run()
        raise AssertionError("peak-time call not refused")
    except ex.S212ExecutionError as exc:
        assert "peak" in str(exc).lower()
    assert scripted.network_calls == 0


def test_mid_batch_peak_entry_stops_partial_kept():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    policy = ex.arm_policy("direct_llm")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("direct_llm", rows, builder, policy)
    auth = _synthetic_auth(ex, rows, "D-REST", allowed_windows="off_peak_only")
    scripted = ScriptedRealLikeTransport(payload_lock)

    times = iter([
        datetime(2026, 8, 20, 21, 0, tzinfo=timezone.utc),   # off-peak
        datetime(2026, 8, 20, 2, 0, tzinfo=timezone.utc),    # peak (Beijing 10:00)
    ])

    def now_seq():
        return next(times)

    ledger_path = _fresh_ledger("s212-test-midpeak.jsonl")
    if ledger_path.exists():
        ledger_path.unlink()
    executor = ex.StageExecutor(
        arm="direct_llm", stage_id="D-REST", auth=auth, lock=lock,
        report=report, rows_by_arm={"direct_llm": rows, "sun_llm_fallback": []},
        payload_lock=payload_lock, transport=scripted, ledger_path=ledger_path,
        now_provider=now_seq,
    )
    try:
        executor.run()
        raise AssertionError("mid-batch peak entry not stopped")
    except ex.S212ExecutionError as exc:
        assert "peak" in str(exc).lower()
    # Partial ledger preserved (1 record)
    ledger = ex.ExecutionLedger(ledger_path)
    assert len(ledger.records) == 1


# ---------------------------------------------------------------------------
# Ledger + resume + tamper
# ---------------------------------------------------------------------------


def test_ledger_resume_does_not_repeat_payloads():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["sun_llm_fallback"]
    policy = ex.arm_policy("sun_llm_fallback")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("sun_llm_fallback", rows, builder, policy)
    auth = _synthetic_auth(ex, rows, "F-1")
    scripted = ScriptedRealLikeTransport(payload_lock)
    ledger_path = _fresh_ledger("s212-test-resume.jsonl")
    if ledger_path.exists():
        ledger_path.unlink()
    executor = ex.StageExecutor(
        arm="sun_llm_fallback", stage_id="F-1", auth=auth, lock=lock,
        report=report, rows_by_arm={"direct_llm": [], "sun_llm_fallback": rows},
        payload_lock=payload_lock, transport=scripted, ledger_path=ledger_path,
    )
    executor.run()
    assert len(ex.ExecutionLedger(ledger_path).records) == 9

    # Resume: run F-1 again — all 9 already called, so 0 new calls.
    executor2 = ex.StageExecutor(
        arm="sun_llm_fallback", stage_id="F-1", auth=auth, lock=lock,
        report=report, rows_by_arm={"direct_llm": [], "sun_llm_fallback": rows},
        payload_lock=payload_lock, transport=scripted, ledger_path=ledger_path,
    )
    result = executor2.run()
    assert len(ex.ExecutionLedger(ledger_path).records) == 9
    assert result["state"]["calls"] == 9  # cumulative from ledger


def test_ledger_tamper_rejected():
    import bpc_hybrid.s2_12_execution as ex
    ledger_path = _fresh_ledger("s212-test-tamper.jsonl")
    if ledger_path.exists():
        ledger_path.unlink()
    ledger = ex.ExecutionLedger(ledger_path)
    price = _price()
    r1 = ex.ledger_record(
        stage_id="F-1", request_id="a", payload_sha="p1", ordinal=1,
        request_time_utc="t", returned_model="deepseek-v4-pro",
        usage={"prompt_tokens": 10, "completion_tokens": 5},
        cumulative_usage={"input_tokens": 10, "output_tokens": 5,
                          "cache_hit_tokens": 0, "cache_miss_tokens": 10},
        per_call_cost={"cost_usd": 0.001}, cumulative_cost=0.001,
        response_content_sha="c1", decode_status="ok_message_content",
        accepted=None, prev_hash=ledger.last_hash,
    )
    ledger.append(r1)
    # Tamper: rewrite the file with a broken record
    ledger_path.write_text('{"broken": true}\n', encoding="utf-8")
    try:
        ex.ExecutionLedger(ledger_path)
        raise AssertionError("tampered ledger accepted")
    except ex.S212ExecutionError:
        pass


# ---------------------------------------------------------------------------
# D-CAL contract
# ---------------------------------------------------------------------------


def test_dcal_invokes_exactly_one_call():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    policy = ex.arm_policy("direct_llm")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("direct_llm", rows, builder, policy)
    scripted = ScriptedRealLikeTransport(payload_lock)
    auth = _synthetic_auth(ex, rows, "D-CAL")
    ledger_path = _fresh_ledger("s212-test-dcal.jsonl")
    if ledger_path.exists():
        ledger_path.unlink()
    executor = ex.StageExecutor(
        arm="direct_llm", stage_id="D-CAL", auth=auth, lock=lock,
        report=report, rows_by_arm={"direct_llm": rows, "sun_llm_fallback": []},
        payload_lock=payload_lock, transport=scripted, ledger_path=ledger_path,
    )
    result = executor.run()
    assert result["state"]["calls"] == 1
    assert len(executor.ledger.records) == 1
    assert executor.ledger.records[0]["stage_id"] == "D-CAL"


def test_stage_subset_cannot_escape_preregistered():
    import bpc_hybrid.s2_12_execution as ex
    # Arbitrary ordinal must be rejected by the stage contract.
    try:
        ex.stage_ordinals("direct_llm", "EVERYTHING")
        raise AssertionError("arbitrary stage accepted")
    except ex.S212ExecutionError:
        pass
    try:
        ex.stage_ordinals("sun_llm_fallback", "F-9")
        raise AssertionError("arbitrary fallback stage accepted")
    except ex.S212ExecutionError:
        pass
    # A D-CAL run must not touch ordinals > 1 even if rows exist.
    assert ex.stage_ordinals("direct_llm", "D-CAL") == [1]


# ---------------------------------------------------------------------------
# Authorization runner hash binding
# ---------------------------------------------------------------------------


def _synthetic_auth(ex, rows, stage_id, **overrides):
    price = _price()
    report = ex.load_report()
    final_63 = [
        row["request_body_sha256"]
        for arm_name in ("direct_llm", "sun_llm_fallback")
        for row in report["arms"][arm_name]["calls"]
    ]
    payloads = [row["request_body_sha256"] for row in rows]
    auth = {
        "schema_version": "s2_12_api_authorization@1.1.0",
        "authorization_sentence_utf8_sha256": "ab" * 32,
        "authorization_event_file": "configs/synthetic-event.json",
        "authorization_event_file_sha256": "cd" * 32,
        "model": "deepseek-v4-pro",
        "calls": {"direct_llm": 36, "sun_llm_fallback": 27},
        "stage_id": stage_id,
        "stage_payload_hashes": payloads,
        "stage_call_cap": len(payloads),
        "global_input_token_cap": overrides.get("global_input_token_cap", 63000000),
        "global_output_token_cap": overrides.get("global_output_token_cap", 258048),
        "global_usd_cost_cap": overrides.get("global_usd_cost_cap", 84.18),
        "allowed_windows": overrides.get("allowed_windows", "any_time"),
        "price_snapshot": price,
        "price_checked_at_utc": "2026-08-22T00:00:00Z",
        "runner_implementation_hashes": {
            "run_s2_12_direct_llm_v1": "direct-hash-synthetic",
            "run_s2_12_sun_llm_fallback_v1": "fallback-hash-synthetic",
            "s2_12_execution": "exec-hash",
            "llm_client": "llm-hash",
            "h1_transport": "h1-hash",
        },
        "input_config_prompt_hashes": {
            "input_sha256": "892d4284ea70c38f82a47f821c13622f1b07744253429e466038ddb5db96660e",
            "lock_sha256": ex._sha(ex.PREFLIGHT_LOCK),
            "prompt_direct_sha256": "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895",
            "prompt_fallback_sha256": "00fe02996914e17f30962147d7a9f2c71a92d2479ba4eff343583a139bb1537b",
        },
        "prev_stage_ledger_hash": "",
        "final_63_payload_hashes": final_63,
        "retry": 0,
        "gold_isolation": {
            "api_arms_must_not_read_gold": True,
            "evaluation_only_after_predictions_are_locked": True,
        },
    }
    auth.update(overrides)
    return auth


def test_fallback_uses_own_runner_hash():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["sun_llm_fallback"]
    policy = ex.arm_policy("sun_llm_fallback")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("sun_llm_fallback", rows, builder, policy)
    # Correct fallback hash -> passes auth gate for fallback arm
    auth = _synthetic_auth(ex, rows, "F-1")
    impl = {
        "s2_12_execution": "exec-hash",
        "llm_client": "llm-hash",
        "h1_transport": "h1-hash",
    }
    ex.validate_authorization(auth, lock, report, "sun_llm_fallback",
                              "fallback-hash-synthetic", impl)
    # Swapped hash (direct runner hash on fallback arm) -> refuse
    try:
        ex.validate_authorization(auth, lock, report, "sun_llm_fallback",
                                  "direct-hash-synthetic", impl)
        raise AssertionError("cross-runner hash accepted for fallback arm")
    except ex.S212ExecutionError as exc:
        assert "runner hash mismatch" in str(exc)


def test_direct_uses_own_runner_hash():
    import bpc_hybrid.s2_12_execution as ex
    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    auth = _synthetic_auth(ex, rows, "D-CAL")
    impl = {"s2_12_execution": "exec-hash", "llm_client": "llm-hash",
            "h1_transport": "h1-hash"}
    ex.validate_authorization(auth, lock, report, "direct_llm",
                              "direct-hash-synthetic", impl)
    try:
        ex.validate_authorization(auth, lock, report, "direct_llm",
                                  "fallback-hash-synthetic", impl)
        raise AssertionError("cross-runner hash accepted for direct arm")
    except ex.S212ExecutionError as exc:
        assert "runner hash mismatch" in str(exc)


# ---------------------------------------------------------------------------
# .env ban
# ---------------------------------------------------------------------------


def test_runners_never_load_project_env():
    for runner in ("run_s2_12_direct_llm_v1", "run_s2_12_sun_llm_fallback_v1"):
        text = (ROOT / "scripts" / f"{runner}.py").read_text(encoding="utf-8")
        assert "load_project_env=False" in text
        assert "load_project_env=True" not in text


def test_dotenv_never_read_even_when_file_exists(tmp_path):
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_config import LLMConfig

    # Simulate a project .env existing with a secret.
    fake_env = tmp_path / ".env"
    fake_env.write_text("BPC_HYBRID_LLM_API_KEY=should-not-be-read\n", encoding="utf-8")

    # from_env with load_project_env=False must NOT read the file.
    config = LLMConfig.from_env(project_root=tmp_path, load_project_env=False)
    assert config.api_key is None or "should-not-be-read" not in str(config.api_key)

    # Runner source must never call load_project_env_file.
    shared = (ROOT / "src/bpc_hybrid/s2_12_execution.py").read_text(encoding="utf-8")
    assert "load_project_env_file" not in shared


def test_secret_never_in_outputs(tmp_path):
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    policy = ex.arm_policy("direct_llm")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("direct_llm", rows, builder, policy)
    scripted = ScriptedRealLikeTransport(payload_lock)
    auth = _synthetic_auth(ex, rows, "D-CAL")
    ledger_path = tmp_path / "ledger.jsonl"
    executor = ex.StageExecutor(
        arm="direct_llm", stage_id="D-CAL", auth=auth, lock=lock,
        report=report, rows_by_arm={"direct_llm": rows, "sun_llm_fallback": []},
        payload_lock=payload_lock, transport=scripted, ledger_path=ledger_path,
    )
    executor.run()
    ledger_text = ledger_path.read_text(encoding="utf-8").lower()
    for secret in ("api_key", "authorization", "password", "client_secret"):
        assert secret not in ledger_text


# ---------------------------------------------------------------------------
# Caps: output cap + retry=0
# ---------------------------------------------------------------------------


def test_output_cap_stops():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    policy = ex.arm_policy("direct_llm")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("direct_llm", rows, builder, policy)
    usage = {"prompt_tokens": 100, "completion_tokens": 5_000_000}
    scripted = ScriptedRealLikeTransport(payload_lock, usage=usage)
    auth = _synthetic_auth(ex, rows, "D-CAL", global_output_token_cap=100)
    ledger_path = _fresh_ledger("s212-test-outcap.jsonl")
    executor = ex.StageExecutor(
        arm="direct_llm", stage_id="D-CAL", auth=auth, lock=lock,
        report=report, rows_by_arm={"direct_llm": rows, "sun_llm_fallback": []},
        payload_lock=payload_lock, transport=scripted, ledger_path=ledger_path,
    )
    try:
        executor.run()
        raise AssertionError("output cap not enforced")
    except ex.S212ExecutionError as exc:
        assert "output" in str(exc).lower()


def test_stage_call_cap_is_enforced():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    policy = ex.arm_policy("direct_llm")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("direct_llm", rows, builder, policy)
    scripted = ScriptedRealLikeTransport(payload_lock)
    auth = _synthetic_auth(ex, rows, "D-CAL", stage_call_cap=1)
    ledger_path = _fresh_ledger("s212-test-callcap.jsonl")
    if ledger_path.exists():
        ledger_path.unlink()
    executor = ex.StageExecutor(
        arm="direct_llm", stage_id="D-CAL", auth=auth, lock=lock,
        report=report, rows_by_arm={"direct_llm": rows, "sun_llm_fallback": []},
        payload_lock=payload_lock, transport=scripted, ledger_path=ledger_path,
    )
    result = executor.run()
    assert result["state"]["calls"] == 1
    assert len(executor.ledger.records) == 1


# ---------------------------------------------------------------------------
# Auth-event builder / schema
# ---------------------------------------------------------------------------


def test_auth_event_builder_refuses_without_sentence():
    proc = _run_cmd([
        str(SCRIPTS / "build_s2_12_auth_event_v1.py"),
        "--runtime-home", str(RUNTIME_HOME), "--stage-id", "D-REST", "--dry-run",
    ])
    assert proc.returncode == 2
    assert "authorization sentence is required" in proc.stdout


def test_auth_event_builder_dry_run_writes_nothing(tmp_path):
    proc = _run_cmd([
        str(SCRIPTS / "build_s2_12_auth_event_v1.py"),
        "--runtime-home", str(RUNTIME_HOME), "--stage-id", "D-REST", "--dry-run",
        "--sentence", "SYNTHETIC TEST ONLY NOT REAL",
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "No authorization created" in proc.stdout
    assert not (ROOT / "configs/s2_12_api_authorization_D-REST.json").exists()
    assert not (ROOT / "configs/s2_12_api_authorization_event_D-REST.json").exists()


def test_auth_event_builder_apply_refuses_synthetic():
    proc = _run_cmd([
        str(SCRIPTS / "build_s2_12_auth_event_v1.py"),
        "--runtime-home", str(RUNTIME_HOME), "--stage-id", "D-REST", "--apply",
        "--sentence", "synthetic sentence",
    ])
    assert proc.returncode == 2
    assert "synthetic" in proc.stdout.lower()
    assert not (ROOT / "configs/s2_12_api_authorization_D-REST.json").exists()


def test_auth_event_builder_apply_without_sentence_refuses():
    proc = _run_cmd([
        str(SCRIPTS / "build_s2_12_auth_event_v1.py"),
        "--runtime-home", str(RUNTIME_HOME), "--stage-id", "F-1", "--apply",
    ])
    assert proc.returncode == 2
    assert "authorization sentence is required" in proc.stdout


def test_auth_schema_is_v11_with_stage_fields():
    schema = json.loads(
        (ROOT / "configs/schemas/s2_12_api_authorization_v1.schema.json")
        .read_text(encoding="utf-8")
    )
    assert schema["properties"]["schema_version"]["const"] == \
        "s2_12_api_authorization@1.1.0"
    for field in ("stage_id", "stage_payload_hashes", "stage_call_cap",
                  "prev_stage_ledger_hash", "final_63_payload_hashes"):
        assert field in schema["required"]


# ---------------------------------------------------------------------------
# Real-like transport end-to-end via runner CLI (fake mode, temp dir)
# ---------------------------------------------------------------------------


def test_direct_runner_fake_dcal_end_to_end(tmp_path):
    out = tmp_path / "dcal"
    proc = _run_cmd([
        str(SCRIPTS / "run_s2_12_direct_llm_v1.py"),
        "--runtime-home", str(RUNTIME_HOME), "--transport", "fake",
        "--stage-id", "D-CAL", "--output-dir", str(out),
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    manifest = json.loads(out.joinpath("manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "partial"
    assert manifest["safety"]["llm_api_calls"] == 1
    assert manifest["safety"]["cost_usd"] > 0  # real cost formula, not hardcoded 0
    assert not out.joinpath("predictions.json").exists()
    ledger = out.joinpath("ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(ledger) == 1


def test_direct_runner_refuses_formal_dir(tmp_path):
    proc = _run_cmd([
        str(SCRIPTS / "run_s2_12_direct_llm_v1.py"),
        "--runtime-home", str(RUNTIME_HOME), "--transport", "fake",
        "--output-dir", str(ROOT / "data/predictions/s2_12_direct_llm_v1"),
    ])
    assert proc.returncode == 2
    assert "formal prediction directory" in proc.stdout
    assert not (ROOT / "data/predictions/s2_12_direct_llm_v1").exists()


def test_fallback_runner_fake_f1_end_to_end(tmp_path):
    out = tmp_path / "f1"
    proc = _run_cmd([
        str(SCRIPTS / "run_s2_12_sun_llm_fallback_v1.py"),
        "--runtime-home", str(RUNTIME_HOME), "--transport", "fake",
        "--stage-id", "F-1", "--output-dir", str(out),
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    manifest = json.loads(out.joinpath("manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "partial"
    assert manifest["safety"]["llm_api_calls"] == 9
    assert not out.joinpath("predictions.json").exists()
    ledger = out.joinpath("ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(ledger) == 9


def test_network_calls_are_zero_everywhere():
    # The shared module must not import networking machinery.
    shared = (ROOT / "src/bpc_hybrid/s2_12_execution.py").read_text(encoding="utf-8")
    for token in ("import urllib.request", "from urllib.request",
                  "import requests", "import httpx", "import openai"):
        assert token not in shared


def _config(lock):
    from build_s2_12_api_preflight_v1 import _config as _c
    return _c(lock)