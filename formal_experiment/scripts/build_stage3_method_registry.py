# -*- coding: utf-8 -*-
"""Build the Stage 3 development method freeze registry (v1).

Freezes, for every frozen development method, its run ID, primary thresholds,
implementation/config hashes (from the run manifests), evidence capsule path
and hash, development-Gold exposure status, and known limitations. The
registry's purpose is to prevent silent method changes after formal Gold
publication: any method change MUST produce a new registry version.

Claims are explicitly locked to development: formal_oracle_claim_allowed=false
and confirmatory_claim_allowed=false.

Usage:
    python scripts/build_stage3_method_registry.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "outputs" / "evidence"
OUTPUT = ROOT / "configs" / "stage3_development_method_registry_v1.json"

METHODS = [
    {
        "method_id": "winter_2020_corrected",
        "run_dir": "s34_winter_stage3_development_v3_clean",
        "capsule": "s34_winter_stage3_development_v3_clean",
        "config_path": "configs/winter_stage3_development_v1.json",
        "primary_thresholds": {"gamma": 0.4, "delta": 0.8},
    },
    {
        "method_id": "winter_2020_prototype_literal",
        "run_dir": "s34_winter_stage3_development_v3_prototype_literal",
        "capsule": "s34_winter_stage3_development_v3_prototype_literal",
        "config_path": "configs/winter_stage3_development_v1.json",
        "primary_thresholds": {"gamma": 0.4, "delta": 0.8},
    },
    {
        "method_id": "sun_2024",
        "run_dir": "s35_sun_stage3_development_v2",
        "capsule": "s35_sun_stage3_development_v2",
        "config_path": "configs/sun_stage3_development_v1.json",
        "primary_thresholds": {"tau": 0.8, "gamma": 0.8, "theta": 0.8},
    },
    {
        "method_id": "s36_bm25",
        "run_dir": "s36_bm25_stage3_development_v2",
        "capsule": "s36_bm25_stage3_development_v2",
        "config_path": "configs/bm25_stage3_development_v1.json",
        "primary_thresholds": {"tau": 0.5, "gamma": 0.5, "theta": 0.5},
    },
    {
        "method_id": "s36_tfidf_svd",
        "run_dir": "s36_tfidf_svd_stage3_development_v2",
        "capsule": "s36_tfidf_svd_stage3_development_v2",
        "config_path": "configs/tfidf_svd_stage3_development_v1.json",
        "primary_thresholds": {"tau": 0.5, "gamma": 0.5, "theta": 0.5},
    },
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite registry: {OUTPUT}")
    entries = {}
    for m in METHODS:
        run_dir = ROOT / "outputs" / "development" / m["run_dir"]
        manifest = _load_json(run_dir / "manifest.json")
        capsule_dir = EVIDENCE_ROOT / m["capsule"]
        capsule_manifest = _load_json(capsule_dir / "capsule_manifest.json")
        entries[m["method_id"]] = {
            "run_id": manifest["run_id"],
            "run_git_commit": manifest["git"]["commit"],
            "run_dirty_paths": len(manifest["git"]["dirty_paths"]),
            "finalised": manifest.get("finalised", False),
            "primary_thresholds": m["primary_thresholds"],
            "config": {
                "path": m["config_path"],
                "sha256": _sha256(ROOT / m["config_path"]),
            },
            "implementation_hashes": manifest.get("implementation_hashes", {}),
            "inputs": {
                "inference_pack_sha256": manifest.get("inputs", {}).get("inference_pack", {}).get("sha256"),
                "bpmn_dir_aggregate_sha256": manifest.get("inputs", {}).get("bpmn_dir_aggregate_sha256"),
            },
            "evidence_capsule": {
                "path": str(capsule_dir.relative_to(ROOT).as_posix()),
                "sha256": _sha256(capsule_dir / "capsule_manifest.json"),
                "files": sorted(capsule_manifest.get("files", {}).keys()),
            },
            "evaluator": {
                "path": "scripts/evaluate_stage3_common.py",
                "sha256": _sha256(ROOT / "scripts" / "evaluate_stage3_common.py"),
            },
            "gold_exposure": {
                "development_gold_seen_by_developer": True,
                "note": "the same 58 development Gold items were used to build and repair the methods before this run; "
                        "thresholds are fixed development settings, NOT blind/confirmatory preregistrations",
            },
            "known_limitations": [
                "spaCy en_core_web_sm has no word vectors (similarity from tagger/parser tensors)",
                "GDPR7 lane names are empty (pool names present); actor observability is limited",
                "frozen violation pack has no compliant (none) gold items: specificity N/A, missing-action F1 can be an all-positive artifact",
            ],
            "claim_gates": {
                "formal_oracle_claim_allowed": False,
                "confirmatory_claim_allowed": False,
                "dev_only": True,
            },
        }
    registry = {
        "schema_version": "stage3_development_method_registry@1.0.0",
        "registry_version": "v1",
        "frozen_at_git_commit": None,  # filled by the caller commit
        "purpose": "freeze the development method set so that no silent method change can happen after formal Gold publication; "
                   "any method/config/threshold change MUST produce a new registry version",
        "change_rule": "a new registry version (vN+1) is required for ANY change to method code, config, thresholds, evaluator, "
                       "inference pack or run inputs; silent in-place edits are forbidden",
        "methods": entries,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
