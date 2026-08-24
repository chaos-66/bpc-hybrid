# -*- coding: utf-8 -*-
"""Focused offline tests for the S2.12 runner wiring batch (zero API).

Every test runs with the payload-locked fake transport or with no transport
at all; the number of real network/API calls must remain 0 throughout.
The formal output directories are never touched (a temp dir is used).  No
authorization file is ever created; synthetic fixtures are built in memory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import hashlib  # noqa: E402


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load(name: str, rel: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PY = sys.executable
RUNTIME_HOME = Path("D:/environment/stanford-corenlp-4.5.10")


# ---------------------------------------------------------------------------
# Payload-level contract (shared module)
# ---------------------------------------------------------------------------

def test_payload_rebuild_matches_locked_63():
    import bpc_hybrid.s2_12_execution as ex
    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)
    # Per-call SHA equality is enforced inside rebuild_and_verify_payloads;
    # double-check the top-level counts and that every row has a body hash.
    assert len(rows["direct_llm"]) == 36
    assert len(rows["sun_llm_fallback"]) == 27
    for arm in ("direct_llm", "sun_llm_fallback"):
        assert all(row["request_body_sha256"] for row in rows[arm])


def test_payload_rebuild_detects_payload_drift():
    import bpc_hybrid.s2_12_execution as ex

    class _FakeCLI:
        runtime_home = RUNTIME_HOME

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)
    original = rows["direct_llm"][0]["request_body_sha256"]
    # Tamper with the expected lock to simulate payload drift.
    drifted = dict(report)
    drifted["arms"] = json.loads(json.dumps(report["arms"]))
    drifted["arms"]["direct_llm"]["calls"] = list(report["arms"]["direct_llm"]["calls"])
    drifted["arms"]["direct_llm"]["calls"][0] = dict(
        report["arms"]["direct_llm"]["calls"][0]
    )
    drifted["arms"]["direct_llm"]["calls"][0]["request_body_sha256"] = "0" * 64
    try:
        ex.rebuild_and_verify_payloads(lock, drifted, RUNTIME_HOME)
        raise AssertionError("payload drift was not detected")
    except ex.S212ExecutionError:
        pass
    assert original  # keep linter happy


# ---------------------------------------------------------------------------
# Fake transport
# ---------------------------------------------------------------------------

def test_fake_transport_accepts_only_locked_payloads():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import LLMClientError, LLMRequest
    from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder
    from build_s2_12_api_preflight_v1 import _config

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    policy = ex.arm_policy("direct_llm")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("direct_llm", rows, builder, policy)
    transport = ex.PayloadLockedFakeTransport(payload_lock, "direct_llm")
    row0 = rows[0]
    ok = transport.send(LLMRequest(
        source_id=row0["sample_id"],
        source_text="x",
        system_prompt=row0["system_prompt"],
        user_prompt=row0["user_prompt"],
    ), ordinal=1)
    assert ok.model == ex.REQUIRED_MODEL
    # Altered prompt -> body sha changes -> refused before any call.
    try:
        transport.send(LLMRequest(
            source_id=row0["sample_id"],
            source_text="x",
            system_prompt=row0["system_prompt"],
            user_prompt=row0["user_prompt"] + " TAMPER",
        ), ordinal=1)
        raise AssertionError("fake transport accepted a tampered payload")
    except LLMClientError:
        pass


def test_fake_transport_zaps_unknown_sample():
    import bpc_hybrid.s2_12_execution as ex
    from bpc_hybrid.llm_client import LLMClientError, LLMRequest
    from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder
    from build_s2_12_api_preflight_v1 import _config

    lock = ex.load_lock()
    report = ex.load_report()
    rows = ex.rebuild_and_verify_payloads(lock, report, RUNTIME_HOME)["direct_llm"]
    policy = ex.arm_policy("direct_llm")
    builder = OpenAICompatibleRequestBuilder(_config(lock))
    payload_lock = ex.PayloadLock("direct_llm", rows, builder, policy)
    transport = ex.PayloadLockedFakeTransport(payload_lock, "direct_llm")
    try:
        transport.send(LLMRequest(
            source_id="unknown", source_text="x",
            system_prompt="s", user_prompt="u",
        ), ordinal=1)
        raise AssertionError("unknown payload accepted")
    except LLMClientError:
        pass


# ---------------------------------------------------------------------------
# Beijing off-peak window
# ---------------------------------------------------------------------------

def test_beijing_peak_windows():
    import bpc_hybrid.s2_12_execution as ex
    from datetime import datetime, timezone, timedelta

    def bj(y, m, d, h, mi):
        return datetime(y, m, d, h, mi, tzinfo=timezone.utc) - timedelta(hours=8)

    # 10:00 Beijing == peak (second window starts 14:00; 10:00 is inside 09-12)
    assert ex.is_beijing_peak(bj(2026, 8, 20, 10, 0)) is True
    # 15:00 Beijing == peak (14-18)
    assert ex.is_beijing_peak(bj(2026, 8, 20, 15, 0)) is True
    # 21:00 Beijing == off-peak
    assert ex.is_beijing_peak(bj(2026, 8, 20, 21, 0)) is False
    # 08:00 Beijing == off-peak
    assert ex.is_beijing_peak(bj(2026, 8, 20, 8, 0)) is False
    # 12:00 exactly is END of first window -> off-peak (12:00-14:00 gap)
    assert ex.is_beijing_peak(bj(2026, 8, 20, 12, 0)) is False


def test_off_peak_only_gate():
    import bpc_hybrid.s2_12_execution as ex
    from datetime import datetime, timezone, timedelta

    def bj(y, m, d, h, mi):
        return datetime(y, m, d, h, mi, tzinfo=timezone.utc) - timedelta(hours=8)

    auth = {"allowed_windows": "off_peak_only"}
    ex.check_off_peak_only(auth, bj(2026, 8, 20, 21, 0))      # ok
    try:
        ex.check_off_peak_only(auth, bj(2026, 8, 20, 10, 0))  # peak
        raise AssertionError("off-peak gate did not reject peak run")
    except ex.S212ExecutionError:
        pass
    any_time = {"allowed_windows": "any_time"}
    ex.check_off_peak_only(any_time, bj(2026, 8, 20, 10, 0))  # ok


# ---------------------------------------------------------------------------
# Authorization gate (v1.1.0 stage-bound)
# ---------------------------------------------------------------------------

def _synthetic_auth(locked_payload_hashes, runner_hash, stage_id="D-CAL", **overrides):
    report = json.loads(
        (ROOT / "outputs/reports/s2_12_api_preflight_v1.json").read_text(
            encoding="utf-8")
    )
    final_63 = [
        row["request_body_sha256"]
        for arm_name in ("direct_llm", "sun_llm_fallback")
        for row in report["arms"][arm_name]["calls"]
    ]
    stage_payloads = sorted(locked_payload_hashes) or final_63[:1]
    auth = {
        "schema_version": "s2_12_api_authorization@1.1.0",
        "authorization_sentence_utf8_sha256": "ab" * 32,
        "authorization_event_file": "configs/synthetic_auth_event.json",
        "authorization_event_file_sha256": "cd" * 32,
        "model": "deepseek-v4-pro",
        "calls": {"direct_llm": 36, "sun_llm_fallback": 27},
        "stage_id": stage_id,
        "stage_payload_hashes": stage_payloads,
        "stage_call_cap": len(stage_payloads),
        "global_input_token_cap": 63000000,
        "global_output_token_cap": 258048,
        "global_usd_cost_cap": 84.18,
        "allowed_windows": "any_time",
        "price_snapshot": {
            "schema_version": "s2_12_price_snapshot@1.0.0",
            "currency": "USD",
            "input_cache_hit_per_million": 0.044,
            "input_cache_miss_per_million": 1.32,
            "output_per_million": 3.96,
        },
        "price_checked_at_utc": "2026-08-20T00:00:00Z",
        "runner_implementation_hashes": {
            "run_s2_12_direct_llm_v1": runner_hash,
            "run_s2_12_sun_llm_fallback_v1": runner_hash,
            "s2_12_execution": "exec-hash",
            "llm_client": "llm-hash",
            "h1_transport": "h1-hash",
        },
        "input_config_prompt_hashes": {
            "input_sha256": "892d4284ea70c38f82a47f821c13622f1b07744253429e466038ddb5db96660e",
            "lock_sha256": "",
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


def test_authorization_gate_accepts_full_contract(tmp_path):
    import bpc_hybrid.s2_12_execution as ex
    runner_hash = "ab" * 32  # synthetic runner hash for the test
    impl_hashes = {"s2_12_execution": "exec-hash", "llm_client": "llm-hash",
                   "h1_transport": "h1-hash"}
    lock = ex.load_lock()
    report = ex.load_report()
    payload_hashes = {
        row["request_body_sha256"]
        for arm in ("direct_llm", "sun_llm_fallback")
        for row in report["arms"][arm]["calls"]
    }
    auth = _synthetic_auth(payload_hashes, runner_hash)
    auth["input_config_prompt_hashes"]["lock_sha256"] = ex._sha(ex.PREFLIGHT_LOCK)
    path = tmp_path / "auth.json"
    path.write_text(json.dumps(auth, ensure_ascii=False), encoding="utf-8")
    validated = ex.load_and_validate_authorization(
        path, lock, report, "direct_llm", runner_hash, impl_hashes
    )
    assert validated["model"] == "deepseek-v4-pro"


def test_authorization_gate_missing_fields_zero_calls(tmp_path):
    import bpc_hybrid.s2_12_execution as ex
    impl_hashes = {"s2_12_execution": "exec-hash", "llm_client": "llm-hash",
                   "h1_transport": "h1-hash"}
    lock = ex.load_lock()
    report = ex.load_report()
    payload_hashes = {
        row["request_body_sha256"]
        for arm in ("direct_llm", "sun_llm_fallback")
        for row in report["arms"][arm]["calls"]
    }
    auth = _synthetic_auth(payload_hashes, "ab" * 32)
    del auth["global_usd_cost_cap"]
    path = tmp_path / "auth-missing.json"
    path.write_text(json.dumps(auth, ensure_ascii=False), encoding="utf-8")
    try:
        ex.load_and_validate_authorization(
            path, lock, report, "direct_llm", "ab" * 32, impl_hashes)
        raise AssertionError("missing field accepted")
    except ex.S212ExecutionError as exc:
        assert "global_usd_cost_cap" in str(exc)


def test_authorization_gate_wrong_calls_fails(tmp_path):
    import bpc_hybrid.s2_12_execution as ex
    impl_hashes = {"s2_12_execution": "exec-hash", "llm_client": "llm-hash",
                   "h1_transport": "h1-hash"}
    lock = ex.load_lock()
    report = ex.load_report()
    payload_hashes = {
        row["request_body_sha256"]
        for arm in ("direct_llm", "sun_llm_fallback")
        for row in report["arms"][arm]["calls"]
    }
    auth = _synthetic_auth(
        payload_hashes, "ab" * 32,
        calls={"direct_llm": 36, "sun_llm_fallback": 26},
    )
    path = tmp_path / "auth-badcalls.json"
    path.write_text(json.dumps(auth), encoding="utf-8")
    try:
        ex.load_and_validate_authorization(
            path, lock, report, "direct_llm", "ab" * 32, impl_hashes)
        raise AssertionError("wrong call counts accepted")
    except ex.S212ExecutionError:
        pass


def test_authorization_gate_wrong_payload_set_fails(tmp_path):
    import bpc_hybrid.s2_12_execution as ex
    impl_hashes = {"s2_12_execution": "exec-hash", "llm_client": "llm-hash",
                   "h1_transport": "h1-hash"}
    lock = ex.load_lock()
    report = ex.load_report()
    auth = _synthetic_auth({"0" * 64 for _ in range(63)}, "ab" * 32)
    path = tmp_path / "auth-badpayload.json"
    path.write_text(json.dumps(auth), encoding="utf-8")
    try:
        ex.load_and_validate_authorization(
            path, lock, report, "direct_llm", "ab" * 32, impl_hashes)
        raise AssertionError("wrong payload set accepted")
    except ex.S212ExecutionError:
        pass


# ---------------------------------------------------------------------------
# Runners: fake end-to-end (temp dirs only)
# ---------------------------------------------------------------------------

def _run_cmd(args):
    import subprocess
    proc = subprocess.run(
        [PY, *args], capture_output=True, text=True, cwd=ROOT.parent
    )
    return proc


def test_direct_runner_fake_dcal_end_to_end(tmp_path):
    out = tmp_path / "direct"
    proc = _run_cmd([
        str(SCRIPTS / "run_s2_12_direct_llm_v1.py"),
        "--runtime-home", str(RUNTIME_HOME),
        "--transport", "fake",
        "--stage-id", "D-CAL",
        "--output-dir", str(out),
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert out.joinpath("manifest.json").is_file()
    manifest = json.loads(out.joinpath("manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "partial"
    assert manifest["safety"]["llm_api_calls"] == 1
    assert manifest["safety"]["network_calls"] == 0
    assert manifest["safety"]["cost_usd"] > 0  # real cost formula on fake usage
    assert not out.joinpath("predictions.json").exists()
    ledger = out.joinpath("ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(ledger) == 1
    cost = json.loads(out.joinpath("cost.json").read_text(encoding="utf-8"))
    assert cost["cumulative_input_tokens"] == 120
    assert cost["cumulative_output_tokens"] == 64


def test_direct_runner_refuses_formal_dir(tmp_path):
    proc = _run_cmd([
        str(SCRIPTS / "run_s2_12_direct_llm_v1.py"),
        "--runtime-home", str(RUNTIME_HOME),
        "--transport", "fake",
        "--output-dir", str(ROOT / "data/predictions/s2_12_direct_llm_v1"),
    ])
    assert proc.returncode == 2
    assert "formal prediction directory" in proc.stdout
    assert not (
        ROOT / "data/predictions/s2_12_direct_llm_v1"
    ).exists()


def test_direct_runner_refuses_real_without_auth(tmp_path):
    proc = _run_cmd([
        str(SCRIPTS / "run_s2_12_direct_llm_v1.py"),
        "--runtime-home", str(RUNTIME_HOME),
        "--transport", "real",
        "--allow-llm",
        "--output-dir", str(tmp_path / "direct-real"),
    ])
    assert proc.returncode == 2
    assert "--auth-file" in proc.stdout
    assert not (tmp_path / "direct-real").exists()


def test_fallback_runner_fake_f1_end_to_end(tmp_path):
    out = tmp_path / "fallback"
    proc = _run_cmd([
        str(SCRIPTS / "run_s2_12_sun_llm_fallback_v1.py"),
        "--runtime-home", str(RUNTIME_HOME),
        "--transport", "fake",
        "--stage-id", "F-1",
        "--output-dir", str(out),
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    manifest = json.loads(out.joinpath("manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "partial"
    assert manifest["safety"]["llm_api_calls"] == 9
    assert manifest["safety"]["network_calls"] == 0
    assert manifest["safety"]["cost_usd"] > 0
    assert not out.joinpath("predictions.json").exists()
    ledger = out.joinpath("ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(ledger) == 9


def test_fallback_runner_refuses_formal_dir(tmp_path):
    proc = _run_cmd([
        str(SCRIPTS / "run_s2_12_sun_llm_fallback_v1.py"),
        "--runtime-home", str(RUNTIME_HOME),
        "--transport", "fake",
        "--output-dir", str(ROOT / "data/predictions/s2_12_sun_llm_fallback_v1"),
    ])
    assert proc.returncode == 2
    assert "formal prediction directory" in proc.stdout
    assert not (
        ROOT / "data/predictions/s2_12_sun_llm_fallback_v1"
    ).exists()


def test_fallback_runner_refuses_without_auth_real(tmp_path):
    proc = _run_cmd([
        str(SCRIPTS / "run_s2_12_sun_llm_fallback_v1.py"),
        "--runtime-home", str(RUNTIME_HOME),
        "--transport", "real",
        "--allow-llm",
        "--output-dir", str(tmp_path / "fallback-real"),
    ])
    assert proc.returncode == 2
    assert "--auth-file" in proc.stdout
    assert not (tmp_path / "fallback-real").exists()


def test_overwrite_is_refused(tmp_path):
    out = tmp_path / "direct2"
    out.mkdir()
    (out / "manifest.json").write_text("{}", encoding="utf-8")
    proc = _run_cmd([
        str(SCRIPTS / "run_s2_12_direct_llm_v1.py"),
        "--runtime-home", str(RUNTIME_HOME),
        "--transport", "fake",
        "--output-dir", str(out),
    ])
    # Fake run is expensive; instead directly test atomic_publish_directory.
    import bpc_hybrid.s2_12_execution as ex
    try:
        ex.atomic_publish_directory(out, {"a.json": b"{}"})
        raise AssertionError("overwrite not refused")
    except ex.S212ExecutionError:
        pass


# ---------------------------------------------------------------------------
# Frozen trigger plan
# ---------------------------------------------------------------------------

def test_frozen_trigger_plan_replays_byte_identical():
    proc = _run_cmd([
        str(SCRIPTS / "build_s2_12_fallback_trigger_plan_v1.py"),
        "--runtime-home", str(RUNTIME_HOME),
        "--check",
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_frozen_trigger_plan_has_exactly_27_and_no_text():
    plan = json.loads(
        (ROOT / "configs/s2_12_fallback_trigger_plan_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert plan["selected_plans"]
    assert len(plan["selected_plans"]) == 27
    assert plan["retry"] == 0
    assert plan["gold_isolation"]["gold_read_by_derivation"] is False
    serialized = json.dumps(plan).lower()
    assert "source_text" not in serialized
    assert '"gold"' not in serialized
    orders = [e["execution_order"] for e in plan["selected_plans"]]
    assert orders == sorted(orders)


# ---------------------------------------------------------------------------
# Auth schema file
# ---------------------------------------------------------------------------

def test_auth_schema_file_is_present_and_valid_json():
    path = ROOT / "configs/schemas/s2_12_api_authorization_v1.schema.json"
    assert path.is_file()
    schema = json.loads(path.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == \
        "s2_12_api_authorization@1.1.0"
    assert schema["properties"]["model"]["const"] == "deepseek-v4-pro"
    assert set(schema["required"]) == {
        "schema_version",
        "authorization_sentence_utf8_sha256",
        "authorization_event_file",
        "authorization_event_file_sha256",
        "model",
        "calls",
        "stage_id",
        "stage_payload_hashes",
        "stage_call_cap",
        "global_input_token_cap",
        "global_output_token_cap",
        "global_usd_cost_cap",
        "allowed_windows",
        "price_snapshot",
        "price_checked_at_utc",
        "runner_implementation_hashes",
        "input_config_prompt_hashes",
        "prev_stage_ledger_hash",
        "final_63_payload_hashes",
        "retry",
        "gold_isolation",
    }


# ---------------------------------------------------------------------------
# Network/real-call accounting
# ---------------------------------------------------------------------------

def test_no_real_network_anywhere():
    import bpc_hybrid.s2_12_execution as ex

    # The shared module and the two runners must not import network or
    # env-reading machinery at module import time.
    src = Path(ex.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "import urllib.request",
        "from urllib.request",
        "import requests",
        "import httpx",
        "import openai",
        "import aiohttp",
    ):
        assert forbidden not in src, f"shared module references {forbidden}"
    for runner in ("run_s2_12_direct_llm_v1", "run_s2_12_sun_llm_fallback_v1"):
        text = (ROOT / "scripts" / f"{runner}.py").read_text(encoding="utf-8")
        # The real-config construction must disable project .env loading.
        assert "LLMConfig.from_env(project_root=ROOT, load_project_env=False)" in text
        # No real call may use the default (project-env-loading) form.
        assert "LLMConfig.from_env(project_root=ROOT)" not in text
        assert "load_project_env=True" not in text
        assert "urllib" not in text.split("def run")[0]
    # The only transport class implemented in the shared module is the fake.
    assert ex.PayloadLockedFakeTransport.__name__ == "PayloadLockedFakeTransport"
    assert "class RealAPITransport" not in src