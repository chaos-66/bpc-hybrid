# -*- coding: utf-8 -*-
"""Focused tests for S3.9-EXT-PC-V1.

The checker-specific tests are added with the Phase C implementation.  The
tests below freeze the Phase B data isolation and hash-binding contract.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_LEGACY = ROOT / "scripts/build_s3_ext_pc_v1.py"
BUILD_MECHANISM = ROOT / "scripts/build_s3_ext_pc_v1_mechanism.py"
MECH_DIR = ROOT / "data/development/stage3_ext_pc_v1"


def _run_check(script: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_legacy_disposition_is_reproducible() -> None:
    _run_check(BUILD_LEGACY)


def test_mechanism_freeze_hashes_are_reproducible() -> None:
    _run_check(BUILD_MECHANISM)


def _walk(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def test_inference_view_contains_no_expected_pair_side_or_mutation_metadata() -> None:
    view = json.loads((MECH_DIR / "inference_view_v1.json").read_text(encoding="utf-8"))
    forbidden = {
        "expected",
        "expected_label",
        "expected_decision",
        "target_type",
        "mutation_type",
        "pair_id",
        "side",
        "control",
        "variant",
        "gold",
        "case_id",
    }
    seen = {key for key, _ in _walk(view)}
    assert not (seen & forbidden)
    assert len(view["objects"]) == 26
    manifest = json.loads((MECH_DIR / "mechanism_case_manifest_v1.json").read_text(encoding="utf-8"))
    assert len(manifest["objects"]) == 26
    assert manifest["pair_success_denominators"] == {
        "prohibition": 5,
        "necessary_precondition": 5,
        "total": 10,
    }
