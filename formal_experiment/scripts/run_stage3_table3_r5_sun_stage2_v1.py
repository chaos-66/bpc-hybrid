# -*- coding: utf-8 -*-
"""Run the frozen Sun Rules-Only (B0 v10a) Stage-2 method for R5 core inputs.

Zero API/network.  This is the fresh formal Sun run required before Table 3:
all 33 core R5 sources are passed through the locked B0 v10a implementation;
no historical Sun prediction is reused as a formal source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.estg150_b0_development_v10 import (  # noqa: E402
    Estg150B0DevelopmentError,
    run_b0_batch_v10,
)

CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v2.json"
SOURCE_REQ = ROOT / "data/development/stage3_table3_r5_benchmark_v2/source_requirements.json"
OUT_DIR = ROOT / "data/predictions/stage3_table3_r5_sun_rule_only_v1"
OUT_PRED = OUT_DIR / "predictions.json"
OUT_ATTEMPTS = OUT_DIR / "attempts.json"
OUT_MANIFEST = OUT_DIR / "manifest.json"
RUNTIME_HOME = Path("D:/environment/stanford-corenlp-4.5.10")


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _core_sources() -> list[dict[str, Any]]:
    config = _load_json(CONFIG)
    sources = {r["requirement_id"]: r for r in _load_json(SOURCE_REQ)["requirements"]}
    rows = []
    for spec in config["requirements"]:
        if not spec.get("core_eligible"):
            continue
        src = sources[spec["requirement_id"]]
        text = src["excerpt_text"]
        if _sha_text(text) != src["text_sha256"]:
            raise SystemExit(f"source text SHA drift: {spec['requirement_id']}")
        rows.append({
            "requirement_id": spec["requirement_id"],
            "source_text": text,
            "source_text_sha256": src["text_sha256"],
            "source_family_id": spec["source_family_id"],
            "split": spec["split"],
        })
    if len(rows) != 33:
        raise SystemExit(f"expected 33 core sources, got {len(rows)}")
    return rows


def run(device: str = "cpu") -> dict[str, Any]:
    if OUT_DIR.exists() and any(OUT_DIR.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty {OUT_DIR}")
    if not RUNTIME_HOME.is_dir():
        raise SystemExit(f"CoreNLP runtime missing: {RUNTIME_HOME}")
    records = _core_sources()
    source_records = [
        {
            "sample_id": row["requirement_id"],
            "approved_text_en": row["source_text"],
            "raw_text_de": row["source_text"],
            "legacy_record_id": row["requirement_id"],
        }
        for row in records
    ]
    (ROOT / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="r5-sun-b0-", dir=ROOT / ".tmp") as raw_work:
        attempts, runtime = run_b0_batch_v10(
            ROOT,
            source_records,
            runtime_home=RUNTIME_HOME,
            work_dir=Path(raw_work),
            device=device,
        )
    by_id = {str(a.get("sample_id")): a for a in attempts}
    predictions = []
    for row in records:
        rid = row["requirement_id"]
        attempt = by_id.get(rid)
        if attempt is None:
            predictions.append({
                "requirement_id": rid,
                "prediction_source_type": "NEW_FRESH_SUN_B0_RUN",
                "prediction_sample_id": rid,
                "request_status": "failed",
                "error_category": "missing_attempt_after_b0_batch",
                "record": None,
                "source_text_sha256": row["source_text_sha256"],
                "source_text": row["source_text"],
                "method_id": "sun_rule_only",
                "method_variant": "b0_enhanced_v10a",
            })
            continue
        predictions.append({
            "requirement_id": rid,
            "prediction_source_type": "NEW_FRESH_SUN_B0_RUN",
            "prediction_sample_id": rid,
            "request_status": attempt.get("request_status"),
            "error_category": attempt.get("error_category"),
            "record": attempt.get("record"),
            "source_text_sha256": row["source_text_sha256"],
            "source_text": row["source_text"],
            "method_id": "sun_rule_only",
            "method_variant": "b0_enhanced_v10a",
        })
    failures = [p for p in predictions if p.get("request_status") != "ok"]
    empty = [p for p in predictions if p.get("request_status") == "ok" and not ((p.get("record") or {}).get("clauses") or [])]
    capsule = {
        "schema_version": "stage3_table3_r5_sun_rule_only_predictions@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "method_id": "sun_rule_only",
        "method_variant": "b0_enhanced_v10a",
        "record_count": len(predictions),
        "gold_read_by_runner": False,
        "historical_sun_outputs_used": False,
        "raw_text_committed": False,
        "records": predictions,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(OUT_PRED, capsule)
    _write_json(OUT_ATTEMPTS, {
        "schema_version": "stage3_table3_r5_sun_raw_local_attempts@1.0.0",
        "record_count": len(attempts),
        "attempts": attempts,
        "runtime": runtime,
    })
    method_bindings = {
        "config_stage2": {"path": "configs/models/estg150_b0_enhanced_s27_v10a.json",
                          "sha256": _sha_file(ROOT / "configs/models/estg150_b0_enhanced_s27_v10a.json")},
        "config_s26": {"path": "configs/models/sun_b0_s26_candidate_B_v1.json",
                       "sha256": _sha_file(ROOT / "configs/models/sun_b0_s26_candidate_B_v1.json")},
        "corenlp_runtime_config": {"path": "configs/sun_corenlp_runtime.json",
                                   "sha256": _sha_file(ROOT / "configs/sun_corenlp_runtime.json")},
        "implementation": {"path": "src/bpc_hybrid/estg150_b0_development_v10.py",
                           "sha256": _sha_file(ROOT / "src/bpc_hybrid/estg150_b0_development_v10.py")},
        "checkpoint": {
            "path": "outputs/development/s24_candidate_B_invsqrt_weighted_seed20260717_v1/best_model.pt",
            "sha256": _sha_file(ROOT / "outputs/development/s24_candidate_B_invsqrt_weighted_seed20260717_v1/best_model.pt"),
        },
    }
    manifest = {
        "schema_version": "stage3_table3_r5_sun_stage2_manifest@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "status": "fresh_sun_stage2_completed" if not failures else "fresh_sun_stage2_partial_or_failed",
        "method_id": "sun_rule_only",
        "method_variant": "b0_enhanced_v10a",
        "api_calls": 0,
        "network_calls": 0,
        "gold_read": False,
        "historical_sun_outputs_used": False,
        "input": {
            "config": {"path": "configs/stage3_table3_r5_benchmark_v2.json", "sha256": _sha_file(CONFIG)},
            "source_requirements": {"path": "data/development/stage3_table3_r5_benchmark_v2/source_requirements.json",
                                    "sha256": _sha_file(SOURCE_REQ)},
            "core_record_count": len(records),
        },
        "runtime_home": str(RUNTIME_HOME),
        "device": device,
        "method_bindings": method_bindings,
        "outputs": {
            "predictions": {"path": str(OUT_PRED.relative_to(ROOT)).replace("\\", "/"),
                            "sha256": _sha_file(OUT_PRED), "record_count": len(predictions)},
            "attempts": {"path": str(OUT_ATTEMPTS.relative_to(ROOT)).replace("\\", "/"),
                         "sha256": _sha_file(OUT_ATTEMPTS)},
        },
        "counts": {
            "records": len(predictions),
            "ok": len(predictions) - len(failures),
            "failed": len(failures),
            "empty": len(empty),
        },
        "failures": [{"requirement_id": p["requirement_id"], "error_category": p.get("error_category")} for p in failures],
        "runtime_summary": runtime,
        "timestamp_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    _write_json(OUT_MANIFEST, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    try:
        manifest = run(args.device)
    except (Estg150B0DevelopmentError, OSError, ValueError) as exc:
        print(json.dumps({"status": "sun_stage2_failed", "error": f"{type(exc).__name__}: {exc}",
                          "api_calls": 0}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["status"] == "fresh_sun_stage2_completed" else 4


if __name__ == "__main__":
    raise SystemExit(main())
