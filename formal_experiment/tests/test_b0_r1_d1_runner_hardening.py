"""D1-R1 runner hardening tests: model pin, prompt-name allowlist, v3 snapshot.

The D1 pilot must run on the pinned model (deepseek-v4-flash) with a
fail-closed model check and a prompt-version switch for the paired
v3-vs-v4 comparison.  These tests verify the allowlist, the snapshot
identity, and the fail-closed decision logic without making any LLM call.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from scripts.run_direct_llm import ALLOWED_PROMPT_NAMES, PROMPT_V3_SNAPSHOT  # noqa: E402

V4_MARKER = "MUST NOT be folded into the action span"


def test_prompt_name_allowlist_contains_active_and_snapshot() -> None:
    assert "direct_llm_sun_record_prompt" in ALLOWED_PROMPT_NAMES
    assert PROMPT_V3_SNAPSHOT in ALLOWED_PROMPT_NAMES


def test_v3_snapshot_is_the_old_prompt() -> None:
    p = load_prompt(PROMPT_V3_SNAPSHOT)
    assert len(p.sha256) == 64
    assert V4_MARKER not in p.system_prompt
    assert "within 72 hours" in p.user_prompt_template
    # the snapshot must contain exactly the four original few-shot examples
    assert len(p.few_shot_examples) == 4


def test_v4_active_prompt_has_the_new_rules() -> None:
    p = load_prompt("direct_llm_sun_record_prompt")
    assert V4_MARKER in p.system_prompt
    assert len(p.few_shot_examples) == 6


def test_unknown_prompt_name_is_rejected_by_cli() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.run_direct_llm",
            "--prompt-name",
            "does_not_exist",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert completed.returncode == 2
    assert "invalid choice" in completed.stderr


def test_model_pin_mismatch_fails_closed_before_calls(tmp_path: Path) -> None:
    # Request a model that can never match the resolved provider model; the
    # fail-closed pin must abort before any LLM call (outputs point to
    # non-formal paths so the formal-write gate cannot shadow it).
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.run_direct_llm",
            "--model",
            "definitely-not-the-resolved-model",
            "--allow-llm",
            "--output",
            str(tmp_path / "out.jsonl"),
            "--manifest",
            str(tmp_path / "manifest.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert completed.returncode == 2
    assert "resolved model" in completed.stdout and "fail-closed model pin" in completed.stdout
