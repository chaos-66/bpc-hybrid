# -*- coding: utf-8 -*-
"""Build the Stage 3 development method freeze registry v2.

v2 changes vs v1:
- active method set points the BM25 arm at the corrected candidate-specific
  run (s36_bm25_stage3_development_v3); BM25 v1/v2 are moved into
  ``superseded_invalid_runs`` with reason ``superseded_invalid_candidate_agnostic_similarity``
  (their similarity function ignored the candidate text; not usable for
  comparison, registry active methods, or paper results);
- ``frozen_at_git_commit`` is never null: the registry records
  ``methods_built_from_clean_commit`` (the run's recorded clean git commit)
  and ``registry_generated_at_commit`` (the HEAD at generation time);
- hash triples are distinguished per method: run ``config_snapshot`` hash,
  run manifest ``implementation_hashes.config``, and the current worktree
  config hash (later config wording changes must NOT be passed off as the
  hash used by an older run);
- claim gates stay locked: formal_oracle_claim_allowed=false,
  confirmatory_claim_allowed=false; development Gold exposure is disclosed.

Usage:
    python scripts/build_stage3_method_registry_v2.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "outputs" / "evidence"
OUTPUT = ROOT / "configs" / "stage3_development_method_registry_v2.json"

ACTIVE_METHODS = [
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
        "run_dir": "s36_bm25_stage3_development_v3",
        "capsule": "s36_bm25_stage3_development_v3",
        "config_path": "configs/bm25_stage3_development_v3.json",
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

SUPERSEDED_INVALID_RUNS = {
    "s36_bm25_stage3_development_v1": {
        "reason": "superseded_invalid_candidate_agnostic_similarity",
        "detail": "sim(query, candidate) ignored the candidate text (best-document score of the action corpus for every candidate); not usable for comparison, registry active methods, or paper results",
        "superseded_by": "s36_bm25_stage3_development_v3",
    },
    "s36_bm25_stage3_development_v2": {
        "reason": "superseded_invalid_candidate_agnostic_similarity",
        "detail": "same candidate-agnostic defect as v1 (v2 only repaired the sensitivity sweep, not the similarity function)",
        "superseded_by": "s36_bm25_stage3_development_v3",
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, check=True).stdout.strip()
    except Exception:  # pragma: no cover
        return "unknown"


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite registry: {OUTPUT}")
    head = _git_head()
    entries = {}
    for m in ACTIVE_METHODS:
        run_dir = ROOT / "outputs" / "development" / m["run_dir"]
        manifest = _load_json(run_dir / "manifest.json")
        config_snapshot = _load_json(run_dir / "config_snapshot.json")
        capsule_manifest = _load_json(EVIDENCE_ROOT / m["capsule"] / "capsule_manifest.json")
        config_worktree_hash = _sha256(ROOT / m["config_path"])
        entries[m["method_id"]] = {
            "run_id": manifest["run_id"],
            "methods_built_from_clean_commit": manifest["git"]["commit"],
            "run_dirty_paths": len(manifest["git"]["dirty_paths"]),
            "finalised": manifest.get("finalised", False),
            "primary_thresholds": m["primary_thresholds"],
            "config_hashes": {
                "run_config_snapshot": config_snapshot.get("config_sha256"),
                "run_manifest_implementation": manifest.get("implementation_hashes", {}).get("config"),
                "current_worktree": config_worktree_hash,
                "note": "the run's config snapshot hash is authoritative for that run; a later worktree hash "
                        "change (e.g. wording edits) must not be attributed to the run",
            },
            "implementation_hashes": manifest.get("implementation_hashes", {}),
            "inputs": {
                "inference_pack_sha256": manifest.get("inputs", {}).get("inference_pack", {}).get("sha256"),
                "bpmn_dir_aggregate_sha256": manifest.get("inputs", {}).get("bpmn_dir_aggregate_sha256"),
            },
            "evidence_capsule": {
                "path": str((EVIDENCE_ROOT / m["capsule"]).relative_to(ROOT).as_posix()),
                "sha256": _sha256(EVIDENCE_ROOT / m["capsule"] / "capsule_manifest.json"),
                "files": sorted(capsule_manifest.get("files", {}).keys()),
            },
            "evaluator": {
                "path": "scripts/evaluate_stage3_common.py",
                "sha256": _sha256(ROOT / "scripts" / "evaluate_stage3_common.py"),
            },
            "gold_exposure": {
                "development_gold_seen_by_developer": True,
                "note": "the same 58 development Gold items were used to build and repair the methods before these runs; "
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
        "schema_version": "stage3_development_method_registry@2.0.0",
        "registry_version": "v2",
        "registry_generated_at_commit": head,
        "purpose": "freeze the active development method set so that no silent method change can happen after formal Gold publication; "
                   "any method/config/threshold change MUST produce a new registry version",
        "change_rule": "a new registry version (vN+1) is required for ANY change to method code, config, thresholds, evaluator, "
                       "inference pack or run inputs; silent in-place edits are forbidden",
        "active_methods": entries,
        "superseded_invalid_runs": SUPERSEDED_INVALID_RUNS,
        "note": "registry v1 (stage3_development_method_registry_v1.json) is retained as provenance; v2 is the authoritative freeze "
                "after the BM25 candidate-specific correction",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
