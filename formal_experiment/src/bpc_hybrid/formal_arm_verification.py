# -*- coding: utf-8 -*-
"""Shared formal-arm / comparison-capsule verification (zero-API, fail-closed).

NO self-reported state is trusted:
- every arm manifest hash is RECOMPUTED from disk and compared against the
  comparison capsule's per_method records item by item;
- every manifest's method_id / claim_scope / is_formal_performance_result /
  artifacts (predictions + results files exist and hash-match) / input /
  Gold / G0.4 / new-calls declarations are re-verified from disk;
- the three independent verifiers are EXECUTED (subprocess) by the audit
  layer (``verify_all_with_verifiers``), never merely checked for existence;
- ``all_three_published_and_verified`` is DERIVED from the verification
  results, never read as an input.

Usage:
    from bpc_hybrid.formal_arm_verification import (
        verify_all_static,        # structural + hash checks (no subprocess)
        verify_all_with_verifiers,  # static + executes the 3 verifiers
    )
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]  # formal_experiment/

REPORTS = ROOT / "outputs" / "reports"
PREDICTIONS = ROOT / "data" / "predictions"
RESULTS = ROOT / "data" / "results"
EVIDENCE = ROOT / "outputs" / "evidence"

INPUT_V2 = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
GOLD = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
G04_CONTRACT = ROOT / "configs" / "evaluation" / "g04_evaluation_views_contract_v1.json"
G04_MANIFEST = EVIDENCE / "g04_formal_coarse_view_v1" / "manifest.json"
G04_DERIVED = EVIDENCE / "g04_formal_coarse_view_v1" / "coarse_view_derived.json"
COMPARISON_CAPSULE = EVIDENCE / "d1_h1_zero_api_reeval_v1" / "comparison_capsule.json"

ARM_REGISTRY = {
    "sun_rule_only": {
        "arm_tag": "b0_formal_arm_v1",
        "method_id": "sun_rule_only",
        "manifest": "outputs/reports/b0_formal_arm_v1.manifest.json",
        "manifest_schema": "b0_formal_arm_manifest@1.0.0",
        "verifier": "outputs/reports/verify_b0_formal_arm_v1.py",
    },
    "direct_llm": {
        "arm_tag": "direct_llm_formal_arm_v1",
        "method_id": "direct_llm",
        "manifest": "outputs/reports/direct_llm_formal_arm_v1.manifest.json",
        "manifest_schema": "snapshot_formal_arm_manifest@1.0.0",
        "verifier": "outputs/reports/verify_direct_llm_formal_arm_v1.py",
    },
    "sun_llm_fallback": {
        "arm_tag": "sun_llm_fallback_formal_arm_v1",
        "method_id": "sun_llm_fallback",
        "manifest": "outputs/reports/sun_llm_fallback_formal_arm_v1.manifest.json",
        "manifest_schema": "snapshot_formal_arm_manifest@1.0.0",
        "verifier": "outputs/reports/verify_sun_llm_fallback_formal_arm_v1.py",
    },
}

REQUIRED_RESULT_FILES = (
    "evaluation_fine.json", "evaluation_coarse.json", "modality_labels.json",
    "g04_view_declaration.json", "cost.json", "config_snapshot.json")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def verify_arm_static(method: str) -> dict[str, Any]:
    """Structural + hash verification of one formal arm (no subprocess)."""
    info = ARM_REGISTRY[method]
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    manifest_path = ROOT / info["manifest"]
    check("manifest exists", manifest_path.exists())
    manifest = _load_json(manifest_path)
    check("manifest schema", manifest.get("schema_version")
          == info["manifest_schema"])
    check("method_id exact", manifest.get("method_id") == info["method_id"],
          str(manifest.get("method_id")))
    check("claim_scope formal", manifest.get("claim_scope") == "formal")
    check("is_formal_performance_result",
          manifest.get("is_formal_performance_result") is True)
    check("verifier file exists", (ROOT / info["verifier"]).exists())

    # artifacts: predictions + results files exist and hash-match
    artifacts = manifest.get("artifacts", {})
    pred_info = artifacts.get("predictions/predictions.json", {})
    pred_path = ROOT / pred_info.get("path", "")
    check("predictions file exists", pred_path.exists())
    if pred_path.exists():
        check("predictions hash matches manifest",
              _sha256_file(pred_path) == pred_info.get("sha256"))
        try:
            pred = json.loads(pred_path.read_text(encoding="utf-8"))
            records = pred.get("records", [])
            check("predictions 150", len(records) == 150)
            check("predictions timing-free",
                  all("runtime" not in r and "latency" not in json.dumps(r)
                      for r in records))
        except (OSError, json.JSONDecodeError):
            check("predictions parseable", False)
    for name in REQUIRED_RESULT_FILES:
        rinfo = artifacts.get(f"results/{name}", {})
        rpath = ROOT / rinfo.get("path", "")
        check(f"result {name} exists", rpath.exists())
        if rpath.exists():
            check(f"result {name} hash matches manifest",
                  _sha256_file(rpath) == rinfo.get("sha256"))

    # input / Gold binding from the arm's config snapshot
    snap_path = ROOT / artifacts.get("results/config_snapshot.json", {}).get(
        "path", "")
    snap = _load_json(snap_path)
    input_sha = snap.get("input", {}).get("sha256")
    gold_sha = snap.get("gold", {}).get("sha256")
    check("input v2 binding hash",
          input_sha == _sha256_file(INPUT_V2) if INPUT_V2.exists() else False,
          str(input_sha)[:16] if input_sha else "missing")
    check("gold binding hash",
          gold_sha == _sha256_file(GOLD) if GOLD.exists() else False,
          str(gold_sha)[:16] if gold_sha else "missing")

    # new-calls declaration
    if method == "sun_rule_only":
        new_calls_ok = manifest.get("safety", {}).get("llm_api_called") is False
    else:
        new_calls_ok = manifest.get("zero_api", {}).get("new_llm_calls") == 0
    check("new llm calls = 0", new_calls_ok)

    ok = all(c["ok"] for c in checks)
    return {"method": method, "arm_tag": info["arm_tag"], "verified": ok,
            "checks": checks,
            "manifest_sha256": _sha256_file(manifest_path)
            if manifest_path.exists() else None}


def run_arm_verifier(method: str) -> dict[str, Any]:
    """Execute the arm's independent verifier (subprocess)."""
    info = ARM_REGISTRY[method]
    verifier = ROOT / info["verifier"]
    if not verifier.exists():
        return {"method": method, "executed": False, "verified": False,
                "detail": "verifier file missing"}
    result = subprocess.run([sys.executable, str(verifier)],
                            capture_output=True, text=True, timeout=300)
    verified = result.returncode == 0 and "VERIFIED" in result.stdout
    return {"method": method, "executed": True, "verified": verified,
            "returncode": result.returncode,
            "detail": (result.stdout.strip().splitlines() or [""])[-1]}


def verify_comparison_static() -> dict[str, Any]:
    """Re-derive the comparison capsule consistency from disk."""
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    cmp = _load_json(COMPARISON_CAPSULE)
    check("comparison capsule exists", COMPARISON_CAPSULE.exists())
    check("comparison schema",
          cmp.get("schema_version") == "shared_stage2_comparison_capsule@1.0.0")
    check("input v2 hash recomputed",
          cmp.get("formal_input_v2", {}).get("sha256")
          == _sha256_file(INPUT_V2) if INPUT_V2.exists() else False)
    check("gold hash recomputed",
          cmp.get("formal_gold", {}).get("sha256")
          == _sha256_file(GOLD) if GOLD.exists() else False)

    # G0.4 semantic hash: comparison vs g04 manifest vs derived recomputation
    g04_man = _load_json(G04_MANIFEST)
    g04_sha = g04_man.get("derived_view", {}).get("semantic_sha256")
    cmp_sha = cmp.get("coarse_view", {}).get("semantic_sha256")
    recomputed = None
    if G04_DERIVED.exists():
        from bpc_hybrid.g04_coarse_view import semantic_hash_json
        recomputed = semantic_hash_json(
            json.loads(G04_DERIVED.read_text(encoding="utf-8")))
    check("G0.4 semantic hash triple-consistent",
          bool(g04_sha) and g04_sha == cmp_sha and g04_sha == recomputed,
          f"manifest={str(g04_sha)[:16]} cmp={str(cmp_sha)[:16]} "
          f"recomputed={str(recomputed)[:16] if recomputed else None}")

    # G0.4 authorization + publishability agree with the contract/manifest
    g04_contract = _load_json(G04_CONTRACT)
    authorized = (g04_contract.get("authorization", {})
                  .get("authorized_by_user") is True)
    check("G0.4 authorized consistent",
          cmp.get("coarse_view", {}).get("g04_contract_authorized")
          is authorized)
    check("main_view_publishable consistent",
          cmp.get("coarse_view", {}).get("main_view_publishable")
          is (g04_man.get("main_view_publishable") is True))

    # three arm manifests: per_method records recomputed from disk
    per_method = cmp.get("formal_arm_capsules", {}).get("per_method", {})
    arm_results = {m: verify_arm_static(m) for m in ARM_REGISTRY}
    for method, info in ARM_REGISTRY.items():
        recorded = per_method.get(method, {})
        disk_sha = arm_results[method]["manifest_sha256"]
        check(f"{method} manifest hash == comparison record",
              disk_sha is not None and disk_sha == recorded.get("manifest_sha256"),
              f"disk={str(disk_sha)[:16] if disk_sha else None} "
              f"recorded={str(recorded.get('manifest_sha256'))[:16]}")
        check(f"{method} claim scope == comparison record",
              recorded.get("claim_scope") == "formal")
        check(f"{method} arm static verified", arm_results[method]["verified"])

    derived_all = all(
        c["ok"] for c in checks if c["name"].endswith("arm static verified"))
    derived_all = derived_all and all(
        c["ok"] for c in checks if c["name"].endswith(
            "manifest hash == comparison record"))
    # all_three_published_and_verified must be DERIVED, not trusted
    recorded_flag = cmp.get("formal_arm_capsules", {}).get(
        "all_three_published_and_verified")
    check("all_three_published derived (not trusted input)",
          derived_all is True,
          f"recorded_self_report={recorded_flag}")
    check("comparison claims all three formal",
          all(per_method.get(m, {}).get("claim_scope") == "formal"
              for m in ARM_REGISTRY))
    ok = all(c["ok"] for c in checks)
    return {"verified": ok, "checks": checks,
            "all_three_published_derived": derived_all}


def verify_all_static() -> dict[str, Any]:
    """Full static verification (no subprocess): three arms + comparison."""
    arms = {m: verify_arm_static(m) for m in ARM_REGISTRY}
    comparison = verify_comparison_static()
    g04_contract = _load_json(G04_CONTRACT)
    g04_authorized = (g04_contract.get("authorization", {})
                      .get("authorized_by_user") is True)
    arms_ok = all(v["verified"] for v in arms.values())
    capsule_complete = arms_ok
    comparison_consistent = comparison["verified"]
    reasons = []
    if not arms_ok:
        reasons.append("one or more formal arm capsules failed static "
                       "verification: " + ", ".join(
                           m for m, v in arms.items() if not v["verified"]))
    if not g04_authorized:
        reasons.append("G0.4 formal evaluation contract not user-authorized")
    if not comparison_consistent:
        reasons.append("shared comparison capsule not hash-consistent")
    return {
        "arms": arms,
        "comparison": comparison,
        "g04_contract_authorized": g04_authorized,
        "capsule_complete": capsule_complete,
        "comparison_consistent": comparison_consistent,
        "reasons": reasons,
        "verified": capsule_complete and g04_authorized
        and comparison_consistent,
    }


def verify_all_with_verifiers() -> dict[str, Any]:
    """Static verification PLUS execution of the three independent verifiers
    (this is what the audit uses; status uses verify_all_static)."""
    result = verify_all_static()
    verifier_results = {m: run_arm_verifier(m) for m in ARM_REGISTRY}
    verifiers_ok = all(v["verified"] for v in verifier_results.values())
    result["verifiers"] = verifier_results
    result["verifiers_executed_and_verified"] = verifiers_ok
    if not verifiers_ok:
        result["reasons"].append(
            "independent verifier execution failed for: " + ", ".join(
                m for m, v in verifier_results.items()
                if not v["verified"]))
    result["verified"] = (result["verified"] and verifiers_ok)
    return result
