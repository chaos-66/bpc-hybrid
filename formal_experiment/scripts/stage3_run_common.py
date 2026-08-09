# -*- coding: utf-8 -*-
"""Shared Stage 3 run closure helpers: export index and manifest finalisation.

Every development run must end with:
- export_index.json: path + sha256 for EVERY exported artifact (config
  snapshot, predictions, rule records, process records index, evaluation,
  threshold sensitivity, error analysis, comparison, manifest itself);
- manifest.json finalised: artifacts hashes complete, finalised=true.

The finalizer fails closed if any declared artifact file is missing.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finalise_run(run_dir: Path, declared: dict[str, str],
                 extra_manifest_fields: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build export_index.json and finalise manifest.json.

    ``declared`` maps artifact names to their file names inside the run dir
    (e.g. {"predictions": "predictions.jsonl"}). Every declared file must
    exist, otherwise the finalizer fails closed. The manifest keeps all its
    previous fields; the artifacts table is extended/overwritten for the
    declared files and ``finalised`` is set.
    """
    run_dir = run_dir.resolve()
    missing = [name for name, fname in declared.items() if not (run_dir / fname).exists()]
    if missing:
        raise RuntimeError(f"finalise failed closed, missing artifacts: {missing}")

    export_index = {
        "schema_version": "stage3_export_index@1.0.0",
        "artifacts": {
            name: {"path": fname, "sha256": _sha256(run_dir / fname),
                   "byte_size": (run_dir / fname).stat().st_size}
            for name, fname in declared.items()
        },
        "manifest": {"path": "manifest.json", "sha256": _sha256(run_dir / "manifest.json")},
    }
    (run_dir / "export_index.json").write_text(
        json.dumps(export_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("artifacts", {})
    for name, fname in declared.items():
        manifest["artifacts"][name] = {
            "path": fname, "sha256": _sha256(run_dir / fname),
            "byte_size": (run_dir / fname).stat().st_size,
        }
    manifest["export_index"] = {
        "path": "export_index.json",
        "sha256": _sha256(run_dir / "export_index.json"),
    }
    manifest["finalised"] = True
    if extra_manifest_fields:
        manifest.update(extra_manifest_fields)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return export_index
