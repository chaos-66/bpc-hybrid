# -*- coding: utf-8 -*-
"""Run the SEP-C2 Stage 2B predecessor baseline from the frozen plan.

Usage:
    python formal_experiment/scripts/run_sep_c2_stage2b_predecessor_baseline_v1.py --publish
    python formal_experiment/scripts/run_sep_c2_stage2b_predecessor_baseline_v1.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

FORMAL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = FORMAL_ROOT.parent
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid import sep_c2_stage2b_winter_estg150 as baseline  # noqa: E402

PLAN = FORMAL_ROOT / "configs/sep_c2_stage2b_predecessor_plan_v1.json"
EVIDENCE_DIR = FORMAL_ROOT / "outputs/evidence/sep_c2_stage2b_predecessor_baseline_v1"
REPORT_JSON = FORMAL_ROOT / "outputs/reports/sep_c2_stage2b_predecessor_baseline_v1.json"
REPORT_MD = FORMAL_ROOT / "outputs/reports/sep_c2_stage2b_predecessor_baseline_v1.md"
REPORT_MANIFEST = FORMAL_ROOT / "outputs/reports/sep_c2_stage2b_predecessor_baseline_v1.manifest.json"


class RunFail(ValueError):
    """Fail-closed baseline-run error."""


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _binding(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RunFail(f"missing artifact: {path.relative_to(FORMAL_ROOT)}")
    return {
        "path": path.relative_to(FORMAL_ROOT).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "byte_size": path.stat().st_size,
    }


def _source_binding(rel: str) -> dict[str, Any]:
    path = REPO_ROOT / rel
    if not path.is_file():
        raise RunFail(f"missing source: {rel}")
    return {
        "path": rel,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "byte_size": path.stat().st_size,
    }


def build_artifacts() -> dict[Path, bytes]:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    report, capsule = baseline.build_report(PLAN, nlp)
    report["runtime"] = {
        "spacy_version": spacy.__version__,
        "spacy_model": "en_core_web_sm",
        "device": "cpu",
        "deterministic_replay": True,
    }
    report_bytes = _json_bytes(report)
    md_bytes = baseline.render_markdown(report).encode("utf-8")
    native_bytes = _json_bytes({
        "schema_version": "sep_c2_stage2b_winter_native_output@1.0.0",
        "records": capsule["native_rows"],
    })
    adapted_bytes = _json_bytes({
        "schema_version": "sep_c2_stage2b_winter_adapted_clause_regions@1.0.0",
        "records": capsule["adapted_rows"],
    })
    historical_bytes = _json_bytes({
        "schema_version": "sep_c2_stage2b_historical_clause_regions@1.0.0",
        "methods": capsule["historical_region_rows"],
    })
    evaluation_bytes = _json_bytes({
        "schema_version": "sep_c2_stage2b_evaluation@1.0.0",
        "task": report["task"],
        "metric": report["comparison"]["metric_id"],
        "methods": report["methods"],
        "comparison": report["comparison"],
        "cases": report["cases"],
        "zero_api": report["zero_api"],
        "claim_boundary": report["claim_boundary"],
    })
    capsule_files = {
        EVIDENCE_DIR / "winter_native.json": native_bytes,
        EVIDENCE_DIR / "winter_adapted_clause_regions.json": adapted_bytes,
        EVIDENCE_DIR / "historical_clause_regions.json": historical_bytes,
        EVIDENCE_DIR / "evaluation.json": evaluation_bytes,
    }
    capsule_bindings = {
        path.name: {
            "path": path.relative_to(FORMAL_ROOT).as_posix(),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_size": len(payload),
        }
        for path, payload in capsule_files.items()
    }
    manifest = {
        "schema_version": "sep_c2_stage2b_predecessor_baseline_manifest@1.0.0",
        "plan": _source_binding("formal_experiment/configs/sep_c2_stage2b_predecessor_plan_v1.json"),
        "report": {
            "path": REPORT_JSON.relative_to(FORMAL_ROOT).as_posix(),
            "sha256": hashlib.sha256(report_bytes).hexdigest(),
            "byte_size": len(report_bytes),
        },
        "report_md": {
            "path": REPORT_MD.relative_to(FORMAL_ROOT).as_posix(),
            "sha256": hashlib.sha256(md_bytes).hexdigest(),
            "byte_size": len(md_bytes),
        },
        "capsule": capsule_bindings,
        "implementation": {
            "module": _source_binding("formal_experiment/src/bpc_hybrid/sep_c2_stage2b_winter_estg150.py"),
            "runner": _source_binding("formal_experiment/scripts/run_sep_c2_stage2b_predecessor_baseline_v1.py"),
            "winter_transcription": _source_binding("formal_experiment/src/bpc_hybrid/winter_stage3/winter_clause.py"),
        },
        "safety": {
            "new_llm_api_calls": 0,
            "new_network_calls": 0,
            "gold_read_by_prediction_code": False,
            "gold_used_for_evaluation": True,
            "historical_predictions_reused": True,
        },
    }
    return {
        **capsule_files,
        REPORT_JSON: report_bytes,
        REPORT_MD: md_bytes,
        REPORT_MANIFEST: _json_bytes(manifest),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        artifacts = build_artifacts()
        if args.publish:
            existing = [path for path in artifacts if path.exists()]
            if existing:
                raise RunFail(f"refusing to overwrite: {existing}")
            for target, payload in artifacts.items():
                target.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                    stage = Path(stream.name)
                    stream.write(payload)
                try:
                    stage.replace(target)
                except Exception:
                    stage.unlink(missing_ok=True)
                    raise
        else:
            for path, expected in artifacts.items():
                if not path.is_file() or path.read_bytes() != expected:
                    raise RunFail(f"replay differs: {path.relative_to(FORMAL_ROOT)}")
        report = json.loads(artifacts[REPORT_JSON].decode("utf-8"))
        print("SEP-C2 Stage 2B predecessor baseline VERIFIED")
        print(f"task={report['task']['task_id']}")
        for method_id, row in report["methods"].items():
            ev = row["overall"]
            print(f"{method_id}: P={ev['precision']:.4f} R={ev['recall']:.4f} "
                  f"F1={ev['f1']:.4f} pred={ev['predicted_regions']} "
                  f"gt={ev['ground_truth_regions']}")
        print(f"new_llm_api_calls={report['zero_api']['new_llm_api_calls']}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"SEP-C2 Stage 2B predecessor baseline refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
