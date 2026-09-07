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
