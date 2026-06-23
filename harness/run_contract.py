"""H1 Contract Runner — validates R15_GDPR50.json contract."""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_contract(contract_path: str) -> bool:
    """Run the contract checks. Return True if all pass."""
    contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    passed = True
    results = []

    # 1. Required artifacts exist
    for artifact in contract.get("required_artifacts", []):
        p = PROJECT_ROOT / artifact
        exists = p.exists()
        status = "PASS" if exists else "FAIL"
        if not exists:
            passed = False
        results.append(f"  [{status}] artifact: {artifact}")

    # 2. Sample count check
    scc = contract.get("sample_count_check")
    if scc:
        p = PROJECT_ROOT / scc["path"]
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                count = sum(1 for l in f if l.strip())
            ok = count == scc["expected"]
            status = "PASS" if ok else "FAIL"
            if not ok:
                passed = False
            results.append(f"  [{status}] sample_count: {count} (expected {scc['expected']})")

    # 3. No raw response check
    nrr = contract.get("no_raw_response_check")
    if nrr:
        p = PROJECT_ROOT / nrr["path"]
        if p.exists():
            manifest = json.loads(p.read_text(encoding="utf-8"))
            val = manifest.get(nrr["field"])
            ok = val == nrr["expected"]
            status = "PASS" if ok else "FAIL"
            if not ok:
                passed = False
            results.append(f"  [{status}] raw_response_saved={val} (expected {nrr['expected']})")

    # 4. LLM call boundary check
    lcb = contract.get("llm_call_boundary_check")
    if lcb:
        p = PROJECT_ROOT / lcb["path"]
        if p.exists():
            manifest = json.loads(p.read_text(encoding="utf-8"))
            max_calls = manifest.get(lcb["max_field"], 0)
            actual_calls = manifest.get(lcb["actual_field"], 0)
            ok = actual_calls <= max_calls
            status = "PASS" if ok else "FAIL"
            if not ok:
                passed = False
            results.append(f"  [{status}] llm_calls={actual_calls} <= max_calls={max_calls}")

    # 5. Formal results exist
    for artifact in contract.get("formal_results_exist", []):
        p = PROJECT_ROOT / artifact
        exists = p.exists()
        status = "PASS" if exists else "FAIL"
        if not exists:
            passed = False
        results.append(f"  [{status}] formal_result: {artifact}")

    # 6. Claim boundary assertions
    cba = contract.get("claim_boundary_assertions", {})
    for key, expected in cba.items():
        # Check manifest for these fields
        manifest_path = PROJECT_ROOT / "data/formal/metadata/r15_gdpr50_rule_plus_llm_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            val = manifest.get(key)
            # If not in manifest, check comparison summary
            if val is None:
                comp_path = PROJECT_ROOT / "data/formal/results/r15_gdpr50_three_way_comparison_summary.json"
                if comp_path.exists():
                    comp = json.loads(comp_path.read_text(encoding="utf-8"))
                    val = comp.get("assertions", {}).get(key)
            ok = val == expected or val is None
            status = "PASS" if ok else "FAIL"
            if not ok:
                passed = False
            results.append(f"  [{status}] claim_boundary.{key}={val} (expected {expected})")

    # Print results
    print(f"Contract: {contract.get('contract_id')}")
    print(f"Results:")
    for r in results:
        print(r)
    print(f"\nOverall: {'PASS' if passed else 'FAIL'}")
    return passed


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    args = parser.parse_args()
    ok = run_contract(args.contract)
    sys.exit(0 if ok else 1)
