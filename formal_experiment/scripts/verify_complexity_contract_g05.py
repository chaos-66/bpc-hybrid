"""Verify the G0.5 pre-result text/BPMN complexity contract on fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.complexity import (  # noqa: E402
    ComplexityContractError,
    load_complexity_contract,
    profile_bpmn_complexity,
    profile_text_complexity,
    validate_complexity_profile,
)


DEFAULT_CONTRACT = ROOT / "configs" / "complexity_contract.json"
TEXT_FIXTURE = ROOT / "tests" / "fixtures" / "complexity" / "text_two_sentence_fixture.json"
BPMN_FIXTURE = ROOT / "tests" / "fixtures" / "complexity" / "bpmn_cycle_fixture.bpmn"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComplexityContractError(f"invalid fixture JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ComplexityContractError(f"fixture root must be an object: {path}")
    return value


def run(contract_path: Path) -> dict[str, Any]:
    contract = load_complexity_contract(contract_path)
    schema_path = ROOT / contract["profile_schema"]["path"]
    text_fixture = _load_object(TEXT_FIXTURE)
    text_profile = profile_text_complexity(text_fixture, contract)
    text_errors = validate_complexity_profile(text_profile, schema_path)
    if text_errors:
        raise ComplexityContractError("text profile schema failed: " + "; ".join(text_errors))
    for key, expected in text_fixture["expected"].items():
        actual = text_profile.get(key, text_profile["metrics"].get(key))
        if actual != expected:
            raise ComplexityContractError(f"text expected {key}={expected!r}, got {actual!r}")

    bpmn_profile = profile_bpmn_complexity(
        item_id="g05_bpmn_cycle_fixture_1",
        xml_text=BPMN_FIXTURE.read_text(encoding="utf-8"),
        source_role="synthetic_fixture",
        contract=contract,
    )
    bpmn_errors = validate_complexity_profile(bpmn_profile, schema_path)
    if bpmn_errors:
        raise ComplexityContractError("BPMN profile schema failed: " + "; ".join(bpmn_errors))
    expected_bpmn = {
        "flow_node_count": 5,
        "activity_count": 2,
        "event_count": 2,
        "gateway_count": 1,
        "lane_count": 1,
        "participant_count": 1,
        "sequence_flow_count": 5,
        "weak_component_count": 1,
        "cyclomatic_complexity": 2,
        "branching_node_count": 1,
        "joining_node_count": 1,
        "cycle_present": True,
        "condensation_dag_depth": 4,
    }
    for key, expected in expected_bpmn.items():
        if bpmn_profile["metrics"][key] != expected:
            raise ComplexityContractError(
                f"BPMN expected {key}={expected!r}, got {bpmn_profile['metrics'][key]!r}"
            )
    if bpmn_profile["complexity_score"] != 1 or bpmn_profile["complexity_stratum"] != "low":
        raise ComplexityContractError("BPMN fixed-indicator stratum changed")

    artifacts = {
        "contract": contract_path,
        "profile_schema": schema_path,
        "implementation": ROOT / "src" / "bpc_hybrid" / "complexity.py",
        "verifier": ROOT / "scripts" / "verify_complexity_contract_g05.py",
        "text_fixture": TEXT_FIXTURE,
        "bpmn_fixture": BPMN_FIXTURE,
    }
    return {
        "schema_version": "complexity_g05_verification_manifest@1.0.0",
        "task_id": "G0.5",
        "status": "succeeded",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": platform.python_version()},
        "artifacts": {
            name: {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": _sha256(path),
            }
            for name, path in artifacts.items()
        },
        "verification": {
            "text_profile_schema_valid": True,
            "bpmn_profile_schema_valid": True,
            "text_profile": text_profile,
            "bpmn_profile": bpmn_profile,
            "text_indicator_count": len(contract["text"]["score_indicators"]),
            "bpmn_indicator_count": len(contract["bpmn"]["score_indicators"]),
            "strata": ["low", "medium", "high"],
            "method_output_used": False,
            "test_result_used": False,
        },
        "safety": {
            "synthetic_fixtures_only": True,
            "complex_dataset_selected_or_read": False,
            "formal_profiles_generated": False,
            "gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "performance_evaluation": False,
        },
        "claim_boundary": contract["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--manifest-out", type=Path, required=True)
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    target = args.manifest_out.resolve()
    if target.exists():
        raise ComplexityContractError(f"refusing to overwrite: {target}")
    manifest = run(contract_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "succeeded", "manifest": str(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

