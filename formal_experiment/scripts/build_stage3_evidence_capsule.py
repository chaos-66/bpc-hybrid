# -*- coding: utf-8 -*-
"""Build the versioned Stage 3 evidence capsule for a development run.

Copies the run's versionable evidence (manifest, config snapshot,
predictions, evaluation, threshold sensitivity, error analysis, export
index, and any comparison files) into ``outputs/evidence/<run_name>/`` so a
fresh clone can locate and verify them. Hash-verified: every copied file's
sha256 is recorded in the capsule's manifest. ``outputs/evidence/`` is NOT
git-ignored, so the capsule is committable.

Usage:
    python scripts/build_stage3_evidence_capsule.py --run-dir <run dir> [--name <name>] [--extra <path> ...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "outputs" / "evidence"

DEFAULT_FILES = [
    "manifest.json",
    "config_snapshot.json",
    "predictions.jsonl",
    "evaluation.json",
    "threshold_sensitivity.json",
    "error_analysis.md",
    "export_index.json",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--name", type=str, default=None)
    parser.add_argument("--extra", type=Path, action="append", default=[],
                        help="extra files to copy (e.g. comparison json, rule_records.jsonl)")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    name = args.name or run_dir.name
    capsule_dir = EVIDENCE_ROOT / name
    if capsule_dir.exists():
        raise RuntimeError(f"refusing to overwrite evidence capsule: {capsule_dir}")
    capsule_dir.mkdir(parents=True)

    copied: dict[str, Any] = {}
    missing = []
    for fname in DEFAULT_FILES + [str(e.relative_to(run_dir)) if e.is_relative_to(run_dir) else e.name
                                  for e in args.extra]:
        src = run_dir / fname
        if not src.exists():
            missing.append(fname)
            continue
        dst = capsule_dir / Path(fname).name
        shutil.copy2(src, dst)
        copied[Path(fname).name] = {
            "path": str(dst.relative_to(ROOT).as_posix()),
            "sha256": _sha256(dst),
            "byte_size": dst.stat().st_size,
        }
    if missing:
        # fail closed on required evidence, tolerate extras that are absent
        required_missing = [f for f in missing if f in DEFAULT_FILES]
        if required_missing:
            shutil.rmtree(capsule_dir, ignore_errors=True)
            raise RuntimeError(f"evidence capsule failed closed, missing: {required_missing}")

    capsule_manifest = {
        "schema_version": "stage3_evidence_capsule@1.0.0",
        "capsule_name": name,
        "source_run_dir": str(run_dir.relative_to(ROOT).as_posix()),
        "files": copied,
    }
    (capsule_dir / "capsule_manifest.json").write_text(
        json.dumps(capsule_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"evidence capsule: {capsule_dir.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
