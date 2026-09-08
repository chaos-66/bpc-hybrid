# -*- coding: utf-8 -*-
"""Focused tests for the S2.12 authorization-files active verifier.

Zero network / zero API / zero .env.  These tests run the same validation
the runner performs before any transport call; they never call the API.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (SCRIPTS, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from verify_s2_12_authorization_files_v1 import (  # noqa: E402
    RECORDED_SENTENCE_SHA,
    USD_CAP_BY_STAGE,
    validate_all,
)


def test_validate_all_passes_for_every_stage():
    rows = validate_all()
    assert rows, "verifier must produce rows"
    failed = [r for r in rows if r["ok"] != "PASS"]
    assert not failed, f"unexpected failures: {failed[:5]}"
    stages = {r["stage"] for r in rows}
    assert stages == set(USD_CAP_BY_STAGE)


def test_sentence_anchor_is_the_recorded_authorization():
    assert len(RECORDED_SENTENCE_SHA) == 64
    # Anchor must equal the byte-exact hash of the recorded original
    # instruction (recorded 2026-09-07 in configs/paper_winddown_*).
    txt = (ROOT / "configs"
           / "paper_winddown_api_authorization_sentence_2026_09_07.txt")
    if txt.is_file():
        import hashlib
        text = txt.read_bytes()
        assert hashlib.sha256(text).hexdigest() == RECORDED_SENTENCE_SHA


def test_usd_caps_match_user_authorization():
    assert USD_CAP_BY_STAGE["D-CAL"] == 1.00
    for stage in ("D-REST", "F-1", "F-2", "F-3"):
        assert USD_CAP_BY_STAGE[stage] == 42.09


# Paths pinned to LF bytes in formal_experiment/.gitattributes because their
# raw LF bytes are bound inside the authorization files / recorded sentence
# hash.  A Windows checkout (core.autocrlf=true) must never flip them to
# CRLF again (2026-09-07 regression guard).
PINNED_LF_PATHS = (
    "scripts/run_s2_12_direct_llm_v1.py",
    "scripts/run_s2_12_sun_llm_fallback_v1.py",
    "src/bpc_hybrid/s2_12_execution.py",
    "configs/paper_winddown_api_authorization_sentence_2026_09_07.txt",
    "configs/paper_winddown_api_authorization_basis_2026_09_07.json",
)


def test_pinned_files_are_raw_lf_after_git_checkout():
    import hashlib
    for rel in PINNED_LF_PATHS:
        raw = (ROOT / rel).read_bytes()
        assert b"\r\n" not in raw, f"{rel} was converted to CRLF by checkout"
        assert hashlib.sha256(raw).hexdigest() == hashlib.sha256(
            raw.replace(b"\r\n", b"\n")).hexdigest(), rel


def test_sentence_txt_raw_bytes_equal_recorded_hash():
    import hashlib
    txt = ROOT / "configs/paper_winddown_api_authorization_sentence_2026_09_07.txt"
    if txt.is_file():
        raw = txt.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == RECORDED_SENTENCE_SHA
