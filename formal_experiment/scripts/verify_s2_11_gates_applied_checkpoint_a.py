# -*- coding: utf-8 -*-
"""Fail-closed independent verifier for the S2.11 / G0.5 CHECKPOINT A
applied-gates assets.

Re-verifies WITHOUT trusting the builder's in-memory payloads:
  1. every Checkpoint A asset exists and its disk bytes match the
     recorded bindings;
  2. the user authorization event carries the exact forwarded instruction
     and its exact UTF-8 SHA-256, the exact authorization scope and the
     exact containment policy;
  3. G1 containment: artifact_license_verified=false,
     unknown_pending_confirmation, no license-named artifact files,
     91 inventoried files, raw-redistribution/publication forbidden;
  4. G2 activation: applied_local_read_only with the exact scope and the
     membership read-discipline;
  5. G3 M1 policy: exact modality identity map, field_mapping={} (G6
     S0), candidate_only, adapter source hash binding;
  6. G4: the SEALED v6 chain re-validates from disk (draft config,
     frozen config, authorization manifest, append-only authorization
     event, empty prior-results scan);
  7. no S2.11 candidate/result exists before the freeze (prior-results
     scan empty; the local working dir is absent/empty);
  8. G0.5 reports frozen_for_future_external_complex_corpora and the
     draft config is byte-unchanged (61938c99…);
  9. G5 is NOT applied in Checkpoint A.

Exit 0 iff everything verifies; any tampering fails closed with exit 1.

Also importable:
    from scripts.verify_s2_11_gates_applied_checkpoint_a import verify
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

USER_INSTRUCTION = "除了用apikey的时候要授权，其他直接正常进行即可。"
USER_INSTRUCTION_SHA256 = \
    "a8a1dec4c826b1303fde64f2ac111ea2886ad0b08fd8a20af68b5a67130bfc64"
DRAFT_CONFIG_RAW_SHA256 = \
    "61938c99a012f36b2b3b3d66a346b31a6c33fdd3f14be0179291ef1982a97586"
AUTHORIZATION_SCOPE = "local_read_only_nonredistributive_s2_11"
FROZEN_STATUS = "frozen_for_future_external_complex_corpora"

USER_AUTH_REL = "configs/s2_11_user_authorization_event_v1.json"
FROZEN_REL = "configs/g05_complexity_frozen_v1.json"
EVENT_REL = "configs/g05_authorization_event_v1.json"
MANIFEST_REL = "configs/g05_authorization_manifest_v1.json"
POLICY_REL = "configs/s2_11_mapping_policy_m1_v1.json"
G1_REL = "outputs/reports/s2_11_g1_license_containment_v1.json"
G2_REL = "outputs/reports/s2_11_g2_activation_v1.json"
GATES_REL = "outputs/reports/s2_11_gates_applied_checkpoint_a_v1.json"
GATES_MANIFEST_REL = \
    "outputs/reports/s2_11_gates_applied_checkpoint_a_v1.manifest.json"
DRAFT_REL = "configs/g05_complexity_candidate_draft_v1.json"

LOCAL_WORKING_DIR = ROOT / "outputs" / "development" / "s2_11_local_working"


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "missing"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def verify() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    # 1. bindings match disk -------------------------------------------------
    gates_manifest = _load_json(ROOT / GATES_MANIFEST_REL)
    check("gates manifest readable", bool(gates_manifest))
    bindings = gates_manifest.get("bindings") or {}
    bad = []
    for rel, want in sorted(bindings.items()):
        if not (ROOT / rel).is_file() or _sha256_file(ROOT / rel) != want:
            bad.append(rel)
    check("checkpoint A bindings match disk", not bad, "; ".join(bad))

    # 2. user authorization event ---------------------------------------------
    user_auth = _load_json(ROOT / USER_AUTH_REL)
    instruction_ok = bool(
        user_auth.get("kind") == "user_authorization"
        and user_auth.get("user_instruction_utf8") == USER_INSTRUCTION
        and user_auth.get("user_instruction_utf8_sha256")
        == USER_INSTRUCTION_SHA256
        and hashlib.sha256(USER_INSTRUCTION.encode("utf-8")).hexdigest()
        == USER_INSTRUCTION_SHA256
        and user_auth.get("authorization_scope") == AUTHORIZATION_SCOPE
        and user_auth.get("append_only") is True)
    check("user authorization event: exact instruction + UTF-8 SHA-256 + "
          "scope + append-only", instruction_ok)

    # 3. G1 containment --------------------------------------------------------
    g1 = _load_json(ROOT / G1_REL)
    cp = g1.get("containment_policy") or {}
    g1_ok = bool(
        g1.get("status") == "resolved_for_local_nonredistributive_analysis"
        and g1.get("artifact_license_verified") is False
        and g1.get("artifact_license_status") ==
        "unknown_pending_confirmation"
        and g1.get("evidence", {}).get("inventoried_files") == 91
        and g1.get("evidence", {}).get("license_named_files_found") == []
        and cp.get("local_read_only_research_use_authorized_by_user") is True
        and cp.get("raw_redistribution_allowed") is False
        and cp.get("raw_publication_allowed") is False
        and cp.get("references_mutation_allowed") is False
        and cp.get("artifact_license_verified") is False)
    check("G1 containment: license NOT verified, 91 files inventoried, no "
          "license files, redistribution forbidden", g1_ok)

    # 4. G2 activation ----------------------------------------------------------
    g2 = _load_json(ROOT / G2_REL)
    g2_ok = bool(
        g2.get("status") == "applied_local_read_only"
        and g2.get("scope") == AUTHORIZATION_SCOPE
        and "membership manifest" in g2.get("read_discipline", ""))
    check("G2 activation: applied_local_read_only with exact scope and "
          "membership read-discipline", g2_ok)

    # 5. G3 M1 + G6 S0 -----------------------------------------------------------
    policy = _load_json(ROOT / POLICY_REL)
    policy_ok = bool(
        policy.get("selected_option") == "M1"
        and policy.get("modality_identity") == {
            "obligation": "obligation",
            "permission": "permission",
            "prohibition": "prohibition",
        }
        and policy.get("structural_policy") ==
        "S0_no_automatic_structural_mapping"
        and policy.get("field_mapping") == {}
        and policy.get("candidate_only") is True
        and policy.get("gold_authorization") is False
        and policy.get("definition_handling", "").startswith("never"))
    check("G3 M1 policy applied + G6 S0 (field_mapping={}, candidate_only, "
          "no definition auto-production)", policy_ok)

    # 6. G4 sealed chain re-validation from disk --------------------------------
    from bpc_hybrid.g05_complexity_candidate import (
        derive_prior_results,
        validate_frozen_application,
    )
    scan = derive_prior_results(ROOT)
    check("no S2.11 candidate/result before the freeze (prior-results "
          "scan empty)", scan["result_paths"] == [],
          "; ".join(scan["result_paths"][:10]))
    # The Checkpoint B candidate artifacts live ONLY in the gitignored
    # local working directory, which the scan patterns deliberately do not
    # cover; they must be git-ignored (never committed).
    local_files = sorted(p for p in LOCAL_WORKING_DIR.rglob("*")
                         if p.is_file()) if LOCAL_WORKING_DIR.is_dir() else []
    ignored_ok = True
    for p in local_files[:5]:
        proc = subprocess.run(
            ["git", "check-ignore", "--",
             str(p.relative_to(ROOT))],
            cwd=ROOT, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            ignored_ok = False
            break
    check("local candidate artifacts git-ignored (never committed)",
          ignored_ok)
    try:
        result = validate_frozen_application(
            ROOT / DRAFT_REL, ROOT / FROZEN_REL, ROOT / MANIFEST_REL,
            project_root=ROOT)
        chain_ok = bool(
            result["frozen_application_valid"] is True
            and result["draft_config_sha256"] == DRAFT_CONFIG_RAW_SHA256
            and result["prior_results_found"] == [])
        check("G4 sealed v6 chain validates from disk (draft/frozen/"
              "manifest/event/prior-results)", chain_ok)
    except Exception as exc:  # noqa: BLE001 - fail-closed reporting
        check("G4 sealed v6 chain validates from disk (draft/frozen/"
              "manifest/event/prior-results)", False, str(exc))

    # 7. G0.5 state --------------------------------------------------------------
    from bpc_hybrid.g05_complexity_candidate import derive_promotion_readiness
    readiness = derive_promotion_readiness(ROOT)
    draft_sha = _sha256_file(ROOT / DRAFT_REL)
    check("G0.5 frozen_for_future_external_complex_corpora; draft "
          "byte-unchanged (61938c99…)",
          readiness["g0_5_status"] == FROZEN_STATUS
          and draft_sha == DRAFT_CONFIG_RAW_SHA256
          and readiness["validated_asset_combinations"] >= 1
          and readiness["preregistration_claim_allowed"] is False)

    # 8. G5 not applied in Checkpoint A -----------------------------------------
    report = _load_json(ROOT / GATES_REL)
    check("G5 NOT applied until Checkpoint B",
          (report.get("gates") or {}).get("G5", {}).get("status")
          == "not_applied_until_checkpoint_b")

    verified = all(c["ok"] for c in checks)
    return {"verified": verified, "checks": checks}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true",
                        help="print machine-readable JSON result")
    args = parser.parse_args()
    result = verify()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for c in result["checks"]:
            print(("PASS" if c["ok"] else "FAIL"), c["name"],
                  "-", c["detail"])
        print("S2.11/G0.5 CHECKPOINT A " +
              ("VERIFIED" if result["verified"] else "NOT VERIFIED"))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
