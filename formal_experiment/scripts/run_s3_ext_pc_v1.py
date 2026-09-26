# -*- coding: utf-8 -*-
"""One-shot offline runner for bounded S3.9-EXT-PC-V1 mechanism objects.

The runner reads only ``inference_view_v1.json`` plus the referenced BPMN bytes.
It never reads the evaluation manifest, expected labels, pair ids, side labels,
or mutation metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.s3_ext_pc_v1 import check_object  # noqa: E402

REVISION = "s3_ext_pc_v1"
MECH_DIR = ROOT / "data/development/stage3_ext_pc_v1"
INFERENCE_VIEW = MECH_DIR / "inference_view_v1.json"
FREEZE = MECH_DIR / "mechanism_freeze_v1.json"
OUT_DIR = ROOT / "outputs/development/s3_ext_pc_v1"
EVIDENCE_DIR = ROOT / "outputs/evidence/s3_ext_pc_v1"
PREDICTIONS = OUT_DIR / "predictions.jsonl"
PREDICTION_FREEZE = OUT_DIR / "prediction_freeze_v1.json"
CASE_EVIDENCE = EVIDENCE_DIR / "per_case_evidence.jsonl"
EVIDENCE_MANIFEST = EVIDENCE_DIR / "manifest.json"

_FORBIDDEN_KEYS = {
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


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _walk_keys(value: Any, path: str = "$"):
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield key, f"{path}.{key}"
            yield from _walk_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, f"{path}[{index}]")


def validate_inference_view(view: Mapping[str, Any]) -> None:
    leaked = [(key, where) for key, where in _walk_keys(view) if key in _FORBIDDEN_KEYS]
    if leaked:
        raise ValueError(f"inference view leaks forbidden metadata: {leaked[:5]}")
    objects = view.get("objects")
    if not isinstance(objects, list) or len(objects) != 26:
        raise ValueError("inference view must contain exactly 26 objects")


def build_prediction_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    view = _load_json(INFERENCE_VIEW)
    validate_inference_view(view)
    rows: list[dict[str, Any]] = []
    for obj in view["objects"]:
        object_id = obj["object_id"]
        bpmn_path = MECH_DIR / obj["bpmn_path"]
        bpmn_sha = _sha256_file(bpmn_path)
        if bpmn_sha != obj["bpmn_sha256"]:
            raise ValueError(f"BPMN hash mismatch for {object_id}")
        result = check_object(obj["rule_spec"], obj["process_record"])
        row = {
            "schema_version": "s3_ext_pc_v1_prediction@1.0.0",
            "revision": REVISION,
            "object_id": object_id,
            **result,
            "input_binding": {
                "bpmn_path": obj["bpmn_path"],
                "bpmn_sha256": bpmn_sha,
                "rule_relation_type": obj["rule_spec"].get("relation_type"),
            },
        }
        rows.append(row)
    hashes = {
        "inference_view_sha256": _sha256_file(INFERENCE_VIEW),
        "mechanism_freeze_sha256": _sha256_file(FREEZE),
        "bpmn_sha256": {obj["object_id"]: obj["bpmn_sha256"] for obj in view["objects"]},
    }
    return rows, hashes


def _write_lines(path: Path, rows: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(_dumps(row) for row in rows).encode("utf-8")
    path.write_bytes(payload)
    return _sha256_bytes(payload)


def _code_bundle_sha256() -> str:
    paths = [
        Path(__file__).resolve(),
        ROOT / "src/bpc_hybrid/s3_ext_pc_v1.py",
    ]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run(*, check_only: bool = False, overwrite: bool = False) -> dict[str, Any]:
    rows, hashes = build_prediction_rows()
    if check_only:
        if not PREDICTIONS.exists() or not PREDICTION_FREEZE.exists():
            raise SystemExit("predictions/freeze missing; run without --check")
        freeze = _load_json(PREDICTION_FREEZE)
        actual_sha = _sha256_file(PREDICTIONS)
        if actual_sha != freeze["prediction_sha256"]:
            raise SystemExit("prediction freeze hash mismatch")
        recomputed = "".join(_dumps(row) for row in rows).encode("utf-8")
        if recomputed != PREDICTIONS.read_bytes():
            raise SystemExit("deterministic replay mismatch")
        print(f"prediction replay check: OK sha256={actual_sha}")
        return {"prediction_sha256": actual_sha, "objects": len(rows)}

    if PREDICTIONS.exists() and not overwrite:
        raise SystemExit("predictions already exist; refusing to overwrite without --overwrite")
    if FREEZE.exists() and not overwrite:
        raise SystemExit("prediction freeze already exists; refusing to overwrite without --overwrite")

    prediction_sha = _write_lines(PREDICTIONS, rows)
    evidence_sha = _write_lines(CASE_EVIDENCE, rows)
    freeze = {
        "schema_version": "s3_ext_pc_v1_prediction_freeze@1.0.0",
        "revision": REVISION,
        "status": "PREDICTIONS_FROZEN_BEFORE_EVALUATION",
        "object_count": len(rows),
        "prediction_path": PREDICTIONS.relative_to(ROOT).as_posix(),
        "prediction_sha256": prediction_sha,
        "case_evidence_path": CASE_EVIDENCE.relative_to(ROOT).as_posix(),
        "case_evidence_sha256": evidence_sha,
        "input_binding": hashes,
        "code_bundle_sha256": _code_bundle_sha256(),
        "run_command": "python formal_experiment/scripts/run_s3_ext_pc_v1.py --overwrite",
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "real_api_calls": 0,
        "network_experiment_calls": 0,
        "gold_status": "AI_constructed_development_not_gold",
    }
    PREDICTION_FREEZE.parent.mkdir(parents=True, exist_ok=True)
    PREDICTION_FREEZE.write_text(json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    evidence_manifest = {
        "schema_version": "s3_ext_pc_v1_evidence_manifest@1.0.0",
        "revision": REVISION,
        "status": "development_only_mechanism_diagnosis",
        "prediction_freeze_path": PREDICTION_FREEZE.relative_to(ROOT).as_posix(),
        "prediction_freeze_sha256": _sha256_file(PREDICTION_FREEZE),
        "prediction_path": PREDICTIONS.relative_to(ROOT).as_posix(),
        "prediction_sha256": prediction_sha,
        "per_case_evidence_path": CASE_EVIDENCE.relative_to(ROOT).as_posix(),
        "per_case_evidence_sha256": evidence_sha,
        "input_binding": hashes,
        "code_bundle_sha256": _code_bundle_sha256(),
        "run_command": freeze["run_command"],
        "python_version": freeze["python_version"],
        "real_api_calls": 0,
        "network_experiment_calls": 0,
        "gold_status": "AI_constructed_development_not_gold",
    }
    EVIDENCE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_MANIFEST.write_text(json.dumps(evidence_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        "prediction_sha256": prediction_sha,
        "object_count": len(rows),
        "prediction_freeze": PREDICTION_FREEZE.relative_to(ROOT).as_posix(),
        "evidence_manifest": EVIDENCE_MANIFEST.relative_to(ROOT).as_posix(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify frozen predictions by deterministic replay")
    parser.add_argument("--overwrite", action="store_true", help="allow first-time or explicit overwrite")
    args = parser.parse_args(argv)
    result = run(check_only=args.check, overwrite=args.overwrite)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
