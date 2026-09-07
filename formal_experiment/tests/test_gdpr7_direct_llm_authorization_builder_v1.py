# -*- coding: utf-8 -*-
"""Focused tests for the GDPR Direct-LLM authorization-event builder.

Zero network / zero API / zero .env: the builder only reads committed files
and computes hashes.  ``--apply`` is tested against a temporary copy of the
fixed event path semantics; the real ``configs/`` event file is never created
or modified here.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CONFIG = ROOT / "configs"
sys.path.insert(0, str(SCRIPTS))

REAL_SENTENCE = (
    "我授权在 GDPR Stage-2→Stage-3 衔接的 Direct-LLM 臂上（scope "
    "gdpr7_direct_llm_v1:74）对 gdpr7_stage2_input_v1.json 的 74 个 "
    "approved_text_en 句子每句调用 1 次 deepseek-v4-pro 真实 API，共 74 次、"
    "retry=0、off-peak only；输入仅限 gdpr7_direct_llm_preflight_v1.json 锁定的 "
    "74 个请求体；USD ≤1.31。"
)
CONTRACT = CONFIG / "ablations/gdpr7_direct_llm_execution_contract_v1.json"
REPORT = ROOT / "outputs/reports/gdpr7_direct_llm_preflight_v1.json"
BUILDER = SCRIPTS / "build_gdpr7_direct_llm_authorization_event_v1.py"

from build_gdpr7_direct_llm_authorization_event_v1 import (  # noqa: E402
    Gdpr7AuthBuilderError,
    build_event,
)
from run_gdpr7_direct_llm_v1 import (  # noqa: E402
    AUTHORIZATION_EVENT_SCHEMA,
    AUTHORIZATION_SCOPE,
    Gdpr7ExecutionError,
    validate_authorization_event,
)


def _write_event(tmp_path: Path, event: dict) -> Path:
    path = tmp_path / "event.json"
    path.write_bytes((json.dumps(event, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return path


def test_builder_refuses_without_sentence():
    with pytest.raises(Gdpr7AuthBuilderError):
        build_event(sentence="", contract_path=CONTRACT, report_path=REPORT)


def test_builder_event_has_required_shape(tmp_path):
    event = build_event(sentence=REAL_SENTENCE, contract_path=CONTRACT,
                        report_path=REPORT)
    assert event["schema_version"] == AUTHORIZATION_EVENT_SCHEMA
    assert event["scope"] == AUTHORIZATION_SCOPE
    assert event["calls"] == 74
    assert event["retry"] == 0
    assert event["allowed_windows"] == "off_peak_only"
    assert event["model"] == "deepseek-v4-pro"
    assert event["published_alias"] == "DeepSeek-V4-Pro-0813"
    assert event["caps"]["global_usd_cost_cap"] == 1.31
    assert event["caps"]["global_input_token_cap"] == 74_000_000
    assert event["caps"]["global_output_token_cap"] == 303_104
    assert event["price_snapshot"]["schema_version"] == "gdpr7_direct_llm_price_snapshot@1.0.0"
    assert float(event["price_snapshot"]["input_cache_miss_per_million"]) == 0.66
    assert float(event["price_snapshot"]["output_per_million"]) == 1.98
    assert event["official_price_reverified_at_utc"]
    assert event["hash_set"]["contract_sha256"]
    assert event["gold_isolation"]["api_arms_must_not_read_gold"] is True
    # The sentence hash must equal the recorded one (byte-exact text binding).
    expected = hashlib.sha256(REAL_SENTENCE.encode("utf-8")).hexdigest()
    assert event["authorization_sentence_utf8_sha256"] == expected


def test_executor_validates_builder_event(tmp_path):
    event = build_event(sentence=REAL_SENTENCE, contract_path=CONTRACT,
                        report_path=REPORT)
    path = _write_event(tmp_path, event)
    validated = validate_authorization_event(path, CONTRACT, REPORT)
    assert validated["scope"] == AUTHORIZATION_SCOPE


def test_executor_rejects_tampered_hash(tmp_path):
    event = build_event(sentence=REAL_SENTENCE, contract_path=CONTRACT,
                        report_path=REPORT)
    key = "data/input/gdpr7_stage2_input_v1.json"
    event["hash_set"][key] = "0" * 64
    path = _write_event(tmp_path, event)
    with pytest.raises(Gdpr7ExecutionError):
        validate_authorization_event(path, CONTRACT, REPORT)


def test_executor_rejects_peak_usd_cap(tmp_path):
    event = build_event(sentence=REAL_SENTENCE, contract_path=CONTRACT,
                        report_path=REPORT)
    event["caps"]["global_usd_cost_cap"] = 2.61
    path = _write_event(tmp_path, event)
    with pytest.raises(Gdpr7ExecutionError):
        validate_authorization_event(path, CONTRACT, REPORT)


def test_cli_dry_run_writes_nothing():
    proc = subprocess.run(
        [sys.executable, str(BUILDER), "--sentence", REAL_SENTENCE,
         "--contract-file", str(CONTRACT), "--report-file", str(REPORT),
         "--dry-run"],
        capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == 0
    assert "DRY RUN" in proc.stdout


def test_cli_apply_refuses_without_sentence():
    proc = subprocess.run(
        [sys.executable, str(BUILDER), "--apply"],
        capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == 2


def test_cli_apply_refuses_synthetic(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(BUILDER), "--sentence",
         "synthetic sentence is not real", "--apply"],
        capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == 2
