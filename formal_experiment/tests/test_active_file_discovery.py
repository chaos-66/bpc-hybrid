"""Default discovery must not revive completed review batches."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import generate_file_catalog as catalog

ROOT = Path(__file__).resolve().parents[1]


def test_catalog_excludes_tracked_archives_and_keeps_active_files(tmp_path, monkeypatch):
    root = tmp_path / "formal_experiment"
    names = (
        "scripts/active.py",
        "data/development/completed_result.json",
        "_retired/review_batches/closed.zip",
        "_retired/old_review.json",
        ".tmp/session.json",
        "data/backup.json.bak",
    )
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic fixture", encoding="utf-8")
    monkeypatch.setattr(catalog, "ROOT", root)
    monkeypatch.setattr(catalog.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        stdout="".join(f"formal_experiment/{name}\n" for name in names)))
    assert catalog.collect_files() == [
        Path("data/development/completed_result.json"), Path("scripts/active.py")]


@pytest.mark.parametrize("script", [
    "validate_binding_gold_v1.py",
    "run_stage3_binding_oracle_v1.py",
])
def test_binding_commands_require_explicit_input_before_reading_or_writing(script, tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script)],
        cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert "--binding-gold" in result.stderr
    assert "required" in result.stderr
    assert "Traceback" not in result.stderr
    assert list(tmp_path.iterdir()) == []
