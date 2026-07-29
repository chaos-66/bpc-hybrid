"""Verify the frozen S2.12-P analysis protocol on synthetic counts only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.s212_analysis import (  # noqa: E402
    S212AnalysisError,
    analyze_primary_family,
    assign_error_categories,
    load_analysis_protocol,
    select_qualitative_cases,
    sha256_file,
    summarize_strata,
)


PROTOCOL = ROOT / "configs" / "s212_analysis_protocol.json"
IMPLEMENTATION = ROOT / "src" / "bpc_hybrid" / "s212_analysis.py"
VERIFIER = Path(__file__).resolve()
FIXTURE = ROOT / "tests" / "fixtures" / "s212_analysis" / "s212_synthetic_counts.json"
DEFAULT_MANIFEST = ROOT / "outputs" / "reports" / "s212_analysis_protocol_synthetic_v2.manifest.json"


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise S212AnalysisError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise S212AnalysisError(f"JSON root must be an object: {path}")
    return value


def build_manifest() -> dict[str, Any]:
    protocol = load_analysis_protocol(PROTOCOL)
    fixture = _load_object(FIXTURE)
    if fixture.get("schema_version") != "s212_synthetic_counts@1.0.0":
        raise S212AnalysisError("synthetic fixture version changed")
    if any(
        marker in json.dumps(fixture, ensure_ascii=False).upper()
        for marker in ("GDPR", "ESTG", "REGULATION (EU)", "ARTICLE 5")
    ):
        raise S212AnalysisError("synthetic fixture contains formal legal text")
    for binding in protocol["upstream_bindings"].values():
        path = ROOT / binding["path"]
        if not path.is_file() or sha256_file(path) != binding["sha256"]:
            raise S212AnalysisError(f"upstream binding changed: {binding['path']}")

    analysis = analyze_primary_family(
        fixture["observations"], protocol, dataset_id=fixture["dataset_id"]
    )
    reversed_analysis = analyze_primary_family(
        list(reversed(fixture["observations"])),
        protocol,
        dataset_id=fixture["dataset_id"],
    )
    if analysis != reversed_analysis:
        raise S212AnalysisError("sample array order changed the paired analysis")
    stratum_summary = summarize_strata(
        fixture["observations"],
        protocol,
        method="direct_llm",
        endpoint_id="action_strict_exact_f1",
    )
    primary_assignment = assign_error_categories(
        ["exception_scope_or_omission", "runtime_api_error"], protocol
    )
    selected_cases = select_qualitative_cases(fixture["error_cases"], protocol)
    action_hypothesis = analysis["hypotheses"]["d1_minus_b0::action_strict_exact_f1"]
    if analysis["hypothesis_count"] != 12 or analysis["holm_family_size"] != 12:
        raise S212AnalysisError("primary Holm family size changed")
    if action_hypothesis["candidate_point"] != 1.0 or action_hypothesis["reference_point"] != 0.25:
        raise S212AnalysisError("synthetic action point estimates changed")
    if primary_assignment["primary"] != "runtime_api_error":
        raise S212AnalysisError("error priority changed")
    if len(selected_cases) != 3:
        raise S212AnalysisError("deterministic qualitative case cap changed")
    if any(item["interval_estimable"] for item in stratum_summary.values()):
        raise S212AnalysisError("small synthetic strata must not receive intervals")

    artifacts = {
        "protocol": {"path": PROTOCOL.relative_to(ROOT).as_posix(), "sha256": sha256_file(PROTOCOL)},
        "implementation": {
            "path": IMPLEMENTATION.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(IMPLEMENTATION),
        },
        "verifier": {"path": VERIFIER.relative_to(ROOT).as_posix(), "sha256": sha256_file(VERIFIER)},
        "synthetic_fixture": {
            "path": FIXTURE.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(FIXTURE),
        },
    }
    return {
        "schema_version": "s212_analysis_verification_manifest@1.1.0",
        "task_id": "S2.12-P",
        "run_id": "s212_analysis_protocol_synthetic_v2",
        "status": "succeeded",
        "artifacts": artifacts,
        "upstream_bindings": protocol["upstream_bindings"],
        "verification": {
            "synthetic_sample_count": analysis["sample_count"],
            "primary_endpoint_count": len(protocol["primary_endpoints"]),
            "contrast_count": len(protocol["methods"]["contrasts"]),
            "hypotheses_per_dataset_family": analysis["hypothesis_count"],
            "bootstrap_iterations": protocol["statistics"]["confidence_interval"]["iterations"],
            "randomization_iterations": protocol["statistics"]["hypothesis_test"]["iterations"],
            "holm_family_size": analysis["holm_family_size"],
            "sample_array_order_invariant": True,
            "small_stratum_interval_suppressed": True,
            "unknown_error_category_fails_closed": True,
            "qualitative_case_cap_verified": len(selected_cases),
            "primary_error_priority_verified": primary_assignment,
            "d1_minus_b0_action_synthetic": action_hypothesis,
        },
        "safety": {
            "synthetic_fixture_only": True,
            "formal_gold_read_or_modified": False,
            "formal_predictions_read_or_created": False,
            "formal_complexity_profiles_generated": False,
            "formal_performance_evaluation": False,
            "method_comparison_claim_generated": False,
            "llm_api_called": False,
            "network_called": False,
        },
        "claim_boundary": protocol["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    try:
        manifest = build_manifest()
        if args.check_only:
            existing = _load_object(args.manifest_out)
            if existing != manifest:
                raise S212AnalysisError("stored S2.12-P manifest differs from deterministic rebuild")
        else:
            if args.manifest_out.exists():
                raise S212AnalysisError(f"refusing to overwrite manifest: {args.manifest_out}")
            args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
            args.manifest_out.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    except S212AnalysisError as exc:
        print(f"S2.12-P verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest["verification"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
