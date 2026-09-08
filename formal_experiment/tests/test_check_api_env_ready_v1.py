# -*- coding: utf-8 -*-
"""Focused tests for the offline API-env precheck tool.

Zero network / zero API / zero .env.  Only process-environment variables are
used; secret VALUES never appear in stdout (the tool prints presence
booleans only, and these tests assert the dummy value is not echoed).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts/check_api_env_ready_v1.py"

DUMMY_KEY = "sk-dummy-offline-test-value-7f3a"

FLAT_ENV = {
    "BPC_HYBRID_LLM_ENABLED": "true",
    "BPC_HYBRID_LLM_PROVIDER": "openai_compatible",
    "BPC_HYBRID_LLM_MODEL": "deepseek-v4-pro",
    "BPC_HYBRID_LLM_BASE_URL": "https://api.deepseek.com/v1",
    "BPC_HYBRID_LLM_API_KEY": DUMMY_KEY,
    "BPC_HYBRID_LLM_MAX_TOKENS": "4096",
    "BPC_HYBRID_LLM_TEMPERATURE": "0",
    "BPC_HYBRID_LLM_TOP_P": "1",
}


def _run_with(env_overrides: dict[str, str] | None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    # Drop any BPC_HYBRID_* keys present in the parent so each run starts
    # from the same clean base.
    for key in list(env):
        if key.startswith("BPC_HYBRID_"):
            del env[key]
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(TOOL)], cwd=ROOT, capture_output=True,
        text=True, env=env, timeout=120,
    )


def test_default_environment_reports_not_ready():
    proc = _run_with(None)
    assert proc.returncode == 2
    assert "NOT READY" in proc.stdout
    assert "mock" in proc.stdout


def test_flat_env_with_dummy_key_reports_ready_without_leaking_secret():
    proc = _run_with(FLAT_ENV)
    assert proc.returncode == 0
    assert "API ENV READY" in proc.stdout
    assert DUMMY_KEY not in proc.stdout
    assert DUMMY_KEY not in proc.stderr


def test_wrong_provider_reports_not_ready():
    env = dict(FLAT_ENV)
    env["BPC_HYBRID_LLM_PROVIDER"] = "deepseek"
    proc = _run_with(env)
    assert proc.returncode == 2
    assert "NOT READY" in proc.stdout


def test_missing_api_key_reports_not_ready():
    env = dict(FLAT_ENV)
    del env["BPC_HYBRID_LLM_API_KEY"]
    proc = _run_with(env)
    assert proc.returncode == 2
    assert "NOT READY" in proc.stdout
    assert "api_key" in proc.stdout
