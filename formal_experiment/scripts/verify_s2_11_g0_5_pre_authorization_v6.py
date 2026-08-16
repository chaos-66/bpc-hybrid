# -*- coding: utf-8 -*-
"""Fail-closed independent verifier for the S2.11 / G0.5 pre-authorization
capsule v6.

Re-verifies the capsule WITHOUT trusting the builder's in-memory payloads:
  1. report JSON is readable and schema-valid
  2. the COMPLETE expected manifest is deterministically re-constructed in
     memory and must equal the on-disk manifest structure exactly
  3. the COMPLETE expected export index is deterministically re-constructed
     and must equal the on-disk export structure exactly
  4. the Markdown is re-rendered byte-identically with exactly one EOF
     newline
  5. the license audit is re-derived read-only (article CC BY 4.0
     article-only; artifact code/data unknown_pending_confirmation)
  6. the state matrix, G0.5 candidate + promotion readiness (draft_not_
     frozen, raw-byte hash 61938c99…, not promotion-ready), the hardened
     adapter status and the six separated user gates are re-derived
  7. the v5 audit facts are recorded exactly (v5 audit WAS green with
     final receipt 2118 passed / 24 skipped / 19 warnings in 941.91s;
     NOT a red checkpoint; its hand-built validation-result protection
     was overturned by v6 counterexamples)
  8. every superseded v3/v4/v5 asset is declared; v3/v4/v5 CORE assets
     are byte-exact against their FIXED ORIGIN COMMIT anchors (hardcoded
     SHA-256 maps, independent of HEAD — a simultaneous HEAD+disk rewrite
     to the same wrong bytes still fails)
  9. the seven independent verifiers are actually executed (strict verdict)
 10. collect_project_audit() is re-run

Exit 0 iff everything verifies; any tampering fails closed with exit 1.

Also importable:
    from scripts.verify_s2_11_g0_5_pre_authorization_v6 import verify
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

OUT_JSON = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v6.json"
OUT_MD = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v6.md"
OUT_MANIFEST = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v6.manifest.json"
OUT_EXPORT = ROOT / "outputs" / "reports" / \
    "s2_11_g0_5_pre_authorization_v6_export_index.json"
SCHEMA = ROOT / "configs" / "schemas" / \
    "s2_11_g0_5_pre_authorization_v6.schema.json"

# v3/v4/v5 core assets that must be byte-exact; the v3/v4/v5 PYTEST files
# are the only historical files allowed to carry corrected lifecycle
# semantics.
HISTORICAL_CORE_REQUIRED = [
    "configs/schemas/s2_11_g0_5_pre_authorization_v3.schema.json",
    "scripts/build_s2_11_g0_5_pre_authorization_v3.py",
    "scripts/verify_s2_11_g0_5_pre_authorization_v3.py",
    "outputs/reports/s2_11_g0_5_pre_authorization_v3.json",
    "outputs/reports/s2_11_g0_5_pre_authorization_v3.md",
    "outputs/reports/s2_11_g0_5_pre_authorization_v3.manifest.json",
    "outputs/reports/s2_11_g0_5_pre_authorization_v3_export_index.json",
    "configs/schemas/s2_11_g0_5_pre_authorization_v4.schema.json",
    "scripts/build_s2_11_g0_5_pre_authorization_v4.py",
    "scripts/verify_s2_11_g0_5_pre_authorization_v4.py",
    "outputs/reports/s2_11_g0_5_pre_authorization_v4.json",
    "outputs/reports/s2_11_g0_5_pre_authorization_v4.md",
    "outputs/reports/s2_11_g0_5_pre_authorization_v4.manifest.json",
    "outputs/reports/s2_11_g0_5_pre_authorization_v4_export_index.json",
    "configs/schemas/s2_11_g0_5_pre_authorization_v5.schema.json",
    "scripts/build_s2_11_g0_5_pre_authorization_v5.py",
    "scripts/verify_s2_11_g0_5_pre_authorization_v5.py",
    "outputs/reports/s2_11_g0_5_pre_authorization_v5.json",
    "outputs/reports/s2_11_g0_5_pre_authorization_v5.md",
    "outputs/reports/s2_11_g0_5_pre_authorization_v5.manifest.json",
    "outputs/reports/s2_11_g0_5_pre_authorization_v5_export_index.json",
]

SUPERSEDED_DECLARED_REQUIRED = HISTORICAL_CORE_REQUIRED + [
    "outputs/reports/s2_11_license_adapter_readiness_v2.json",
    "outputs/reports/s2_11_data_qualification_mapping_dry_run.json",
    "outputs/reports/g0_7_barrientos_adapter_registry_dry_run.json",
    "outputs/reports/g0_7_barrientos_adapter_registry_dry_run.md",
    "tests/test_s2_11_g0_5_pre_authorization_v3.py",
    "tests/test_s2_11_g0_5_pre_authorization_v4.py",
    "tests/test_s2_11_g0_5_pre_authorization_v5.py",
]


def _load_builder() -> Any:
    spec = importlib.util.spec_from_file_location(
        "s2_11_g0_5_pre_authorization_builder_v6",
        ROOT / "scripts" / "build_s2_11_g0_5_pre_authorization_v6.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _display_rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def _binding_path(root: Path, rel: str) -> Path:
    """references/** bindings live under the repository root (root.parent);
    everything else lives under formal_experiment/ (root)."""
    if rel.startswith("references/"):
        return root.parent / rel
    return root / rel


def _matrix_diff(report_matrix: Any, derived: Any) -> str:
    if report_matrix == derived:
        return ""
    rep = {i["task_id"]: i for i in report_matrix}
    der = {i["task_id"]: i for i in derived}
    diffs = [t for t in sorted(set(rep) | set(der))
             if rep.get(t) != der.get(t)]
    return "; ".join(diffs) or "matrix differs"


def verify(report_path: Path = OUT_JSON,
           manifest_path: Path = OUT_MANIFEST,
           export_path: Path = OUT_EXPORT,
           md_path: Path = OUT_MD,
           root: Path = ROOT,
           run_external: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    builder = _load_builder()

    # 1. report readable + schema ------------------------------------------
    report: dict[str, Any] = _load_json(report_path)
    check("report JSON readable", bool(report),
          _display_rel(report_path) if report_path.exists()
          else "missing report file")
    schema = _load_json(SCHEMA)
    check("capsule schema readable", bool(schema))
    if report and schema:
        errors = builder._schema_errors(schema, report)
        check("report schema valid", not errors, "; ".join(errors[:5]))

    # 2. manifest EXACT reconstruction -------------------------------------
    manifest = _load_json(manifest_path)
    check("manifest readable", bool(manifest))
    if report and manifest_path.is_file():
        try:
            report_bytes = report_path.read_bytes()
            md_bytes = md_path.read_bytes() if md_path.exists() else b""
            bindings = builder.collect_bindings(root, report)
            expected_manifest = builder.build_manifest(
                root, report_bytes, md_bytes, bindings)
            mismatch = [k for k in sorted(set(expected_manifest) | set(manifest))
                        if expected_manifest.get(k) != manifest.get(k)]
            check("manifest exact reconstruction matches disk (structure, "
                  "keys, values; no missing/extra entries)", not mismatch,
                  "; ".join(mismatch))
        except Exception as exc:  # noqa: BLE001 - fail-closed reporting
            check("manifest exact reconstruction matches disk (structure, "
                  "keys, values; no missing/extra entries)", False,
                  f"reconstruction raised: {exc}")
    if manifest:
        bad: list[str] = []
        for rel, want in sorted((manifest.get("bindings") or {}).items()):
            p = _binding_path(root, rel)
            if not p.is_file() or _sha256_file(p) != want:
                bad.append(rel)
        check("manifest bindings match disk", not bad, "; ".join(bad[:10]))
        impl_bad = []
        for name, info in (manifest.get("implementation") or {}).items():
            p = root / info.get("path", "")
            if not p.is_file() or _sha256_file(p) != info.get("sha256"):
                impl_bad.append(name)
        check("manifest implementation hashes match disk", not impl_bad,
              "; ".join(impl_bad))
        art_bad = []
        for name, info in (manifest.get("artifacts") or {}).items():
            p = root / info.get("path", "")
            if not p.is_file():
                art_bad.append(f"{name}:missing")
                continue
            if _sha256_file(p) != info.get("sha256") or \
                    p.stat().st_size != info.get("byte_size"):
                art_bad.append(name)
        check("manifest artifact hashes match disk", not art_bad,
              "; ".join(art_bad))

    # 3. export index EXACT reconstruction ----------------------------------
    export = _load_json(export_path)
    check("export index readable", bool(export))
    if report and manifest_path.is_file() and export_path.is_file():
        try:
            report_bytes = report_path.read_bytes()
            md_bytes = md_path.read_bytes() if md_path.exists() else b""
            manifest_bytes = manifest_path.read_bytes()
            expected_export = builder.build_export_index(
                root, report_bytes, md_bytes, manifest_bytes)
            mismatch = [k for k in sorted(set(expected_export) | set(export))
                        if expected_export.get(k) != export.get(k)]
            check("export index exact reconstruction matches disk "
                  "(structure, keys, values; recomputed hashes cannot "
                  "bypass)", not mismatch, "; ".join(mismatch))
        except Exception as exc:  # noqa: BLE001 - fail-closed reporting
            check("export index exact reconstruction matches disk "
                  "(structure, keys, values; recomputed hashes cannot "
                  "bypass)", False, f"reconstruction raised: {exc}")
    if export:
        exp_bad = []
        for name, info in (export.get("artifacts") or {}).items():
            p = root / info.get("path", "")
            if not p.is_file():
                exp_bad.append(f"{name}:missing")
                continue
            if _sha256_file(p) != info.get("sha256") or \
                    p.stat().st_size != info.get("byte_size"):
                exp_bad.append(name)
        check("export index artifacts match disk", not exp_bad,
              "; ".join(exp_bad))

    # 4. Markdown deterministic re-render + single EOF newline ---------------
    if report:
        try:
            rerendered = builder.render_md(report).encode("utf-8")
            on_disk = md_path.read_bytes() if md_path.exists() else b""
            check("markdown re-render byte-identical",
                  rerendered == on_disk,
                  "md content diverges from the report JSON")
            check("markdown ends with exactly one EOF newline",
                  bool(on_disk) and on_disk.endswith(b"\n")
                  and not on_disk.endswith(b"\n\n"))
        except Exception as exc:  # pragma: no cover - defensive
            check("markdown re-render byte-identical", False, str(exc))

    # 5. license audit re-derivation (article vs artifact) -------------------
    if report:
        try:
            la = report.get("license_audit", {})
            ae = la.get("article_evidence", {})
            pdf = root.parent / ae.get("pdf_path", "\0")
            article_ok = bool(
                la.get("paper_readable") is True
                and la.get("article_license") == "CC-BY-4.0"
                and la.get("article_license_scope") == "article_only"
                and la.get("article_license_does_not_auto_cover_artifact")
                is True
                and pdf.is_file()
                and _sha256_file(pdf) == ae.get("pdf_sha256")
                and pdf.stat().st_size == ae.get("pdf_byte_size")
                and ae.get("doi") == "10.1016/j.infsof.2026.108079"
                and ae.get("ccby_url")
                == "http://creativecommons.org/licenses/by/4.0/"
                and ae.get("artifact_url").startswith(
                    "https://anonymous.4open.science/"))
            check("article evidence: PDF hash/size bound, CC BY 4.0 "
                  "article-only, DOI and artifact URL", article_ok)
            artifact_ok = bool(
                la.get("code_usable") == "unknown_pending_confirmation"
                and la.get("data_reusable") == "unknown_pending_confirmation"
                and la.get("project_activatable") is False
                and la.get("ready_for_data_activation") is False
                and la.get("activation_authorization_sentence") is None)
            check("artifact code/data license fail-closed fields", artifact_ok)
        except Exception as exc:  # noqa: BLE001 - fail-closed reporting
            check("license audit re-derivation", False,
                  f"check raised: {exc}")

    # 6. state matrix / G0.5 / adapter / gates re-derivation -----------------
    if report:
        try:
            derived = builder.derive_state_matrix(root)
            diff = _matrix_diff(report.get("state_matrix", []), derived)
            check("state matrix re-derived and compared item-by-item",
                  not diff, diff)
        except Exception as exc:  # noqa: BLE001 - fail-closed reporting
            check("state matrix re-derived and compared item-by-item",
                  False, f"derivation raised: {exc}")
        try:
            g5 = report.get("g0_5_candidate", {})
            derived_g5 = builder.derive_g0_5_candidate(root)
            check("G0.5 candidate stays draft_not_frozen, raw-byte hash "
                  "61938c99 bound",
                  g5.get("status") == "draft_not_frozen"
                  and g5.get("frozen") is False
                  and g5.get("config_sha256")
                  == "61938c99a012f36b2b3b3d66a346b31a6c33fdd3f14be0179291ef1982a97586"
                  and derived_g5 == g5)
        except Exception as exc:  # noqa: BLE001 - fail-closed reporting
            check("G0.5 candidate stays draft_not_frozen, raw-byte hash "
                  "61938c99 bound", False, f"derivation raised: {exc}")
        try:
            pr = report.get("g0_5_promotion_readiness", {})
            derived_pr = builder.derive_g0_5_promotion_readiness(root)
            check("G0.5 promotion readiness: draft_not_frozen, not "
                  "promotion-ready, no preregistration claim",
                  pr.get("g0_5_status") == "draft_not_frozen"
                  and pr.get("promotion_ready_for_application") is False
                  and pr.get("preregistration_claim_allowed") is False
                  and derived_pr == pr
                  and len(pr.get("missing", [])) >= 1)
        except Exception as exc:  # noqa: BLE001 - fail-closed reporting
            check("G0.5 promotion readiness re-derived", False,
                  f"derivation raised: {exc}")
        try:
            ad = report.get("adapter_status", {})
            src = root / ad.get("source_path", "\0")
            tst = root / ad.get("tests_path", "\0")
            check("adapter status hardened synthetic_shadow_only with bound "
                  "files",
                  ad.get("implementation") == "synthetic_shadow_only"
                  and ad.get("hardened") is True
                  and ad.get("verified") is True
                  and src.is_file() and tst.is_file()
                  and len(ad.get("formal_activation_blocked_on", [])) >= 5)
        except Exception as exc:  # noqa: BLE001 - fail-closed reporting
            check("adapter status hardened synthetic_shadow_only with bound "
                  "files", False, f"check raised: {exc}")
        gates = report.get("user_gates", [])
        by_id = {g.get("gate_id"): g for g in gates}
        check("user gates count and ids",
              len(gates) == 6
              and set(by_id) == {"G1", "G2", "G3", "G4", "G5", "G6"})
        g1, g2, g3, g4, g5, g6 = (by_id.get(k, {}) for k in
                                  ("G1", "G2", "G3", "G4", "G5", "G6"))
        check("G1/G2/G5/G6 ready=false with null sentences",
              g1.get("ready_for_authorization") is False
              and g1.get("authorization_sentence") is None
              and g2.get("ready_for_authorization") is False
              and g2.get("authorization_sentence") is None
              and g5.get("ready_for_authorization") is False
              and g5.get("authorization_sentence") is None
              and g6.get("ready_for_authorization") is False
              and g6.get("authorization_sentence") is None
              and len(g1.get("missing", [])) >= 1
              and len(g2.get("missing", [])) >= 1
              and len(g5.get("missing", [])) >= 4
              and len(g6.get("missing", [])) >= 1)
        check("G5 keeps only a CONDITIONAL future sentence",
              isinstance(g5.get(
                  "future_authorization_sentence_after_prerequisites"), str)
              and "Future sentence" in g5.get(
                  "future_authorization_sentence_after_prerequisites", ""))
        check("G3/G4 ready=true with the exact dry-run sentences",
              g3.get("ready_for_authorization") is True
              and g3.get("authorization_sentence") == builder.G3_SENTENCE
              and g4.get("ready_for_authorization") is True
              and g4.get("authorization_sentence")
              == builder.g4_sentence(
                  report.get("g0_5_candidate", {}).get("config_sha256", ""))
              and "RAW BYTE sha256" in g4.get("authorization_sentence", "")
              and "gate-application checkpoint" in g4.get(
                  "authorization_sentence", "")
              and "does NOT freeze G0.5 this round" in g4.get(
                  "authorization_sentence", ""))

    # 7. v5 audit facts ---------------------------------------------------------
    if report:
        facts = report.get("v5_audit_facts", {})
        check("v5 audit facts recorded exactly (green receipt; claim "
              "overturned; not a red checkpoint)",
              facts.get("v5_audit_green") is True
              and "2118 passed, 24 skipped, 19 warnings in 941.91s"
              in facts.get("v5_final_receipt", "")
              and facts.get("v5_handbuilt_validation_claim_overturned")
              is True
              and facts.get("v5_not_a_red_checkpoint") is True
              and facts.get("v5_historical_events_preserved") is True
              and len(facts.get("v6_counterexamples", [])) >= 6)

    # 8. supersedes precedence + FIXED ORIGIN anchors ---------------------------
    if report:
        supers = report.get("supersedes", [])
        missing_or_changed = []
        for item in supers:
            p = root / item.get("path", "\0")
            if not p.is_file() or _sha256_file(p) != item.get("sha256"):
                missing_or_changed.append(item.get("path"))
        declared = {item.get("path") for item in supers}
        check("superseded v3/v4/v5 assets declared and byte-unchanged",
              not missing_or_changed
              and set(SUPERSEDED_DECLARED_REQUIRED) <= declared,
              "; ".join(missing_or_changed)
              or f"missing declarations: "
                 f"{sorted(set(SUPERSEDED_DECLARED_REQUIRED) - declared)}")
        # v3/v4/v5 CORE assets must match the FIXED ORIGIN anchors: disk
        # bytes AND origin-commit git blobs must match the hardcoded SHA-256
        # maps (independent of HEAD). The report's recorded anchors must
        # equal the lifecycle module's fixed maps too.
        from bpc_hybrid.capsule_lifecycle import (
            FIXED_ORIGIN_COMMITS,
            fixed_core_asset_hashes,
            historical_core_assets_match_fixed_origin,
        )
        anchor_drifted = []
        for version in ("v3", "v4", "v5"):
            ok, detail = historical_core_assets_match_fixed_origin(
                root, version)
            if not ok:
                anchor_drifted.append(f"{version}:{detail}")
            recorded = (report.get("fixed_origin_anchors") or {}).get(
                version, {})
            if recorded.get("origin_commit") != \
                    FIXED_ORIGIN_COMMITS.get(version):
                anchor_drifted.append(f"{version}:commit-mismatch")
            recorded_assets = recorded.get("assets") or {}
            for key, want in fixed_core_asset_hashes(version).items():
                if (recorded_assets.get(key) or {}).get("sha256") != want:
                    anchor_drifted.append(f"{version}:{key}-mismatch")
        check("v3/v4/v5 CORE assets byte-exact against FIXED ORIGIN anchors "
              "(disk + origin blobs; HEAD-independent)",
              not anchor_drifted, "; ".join(anchor_drifted))

    # 9. safety / zero-api / oracle control ------------------------------------
    if report:
        safety = report.get("safety", {})
        check("safety flags: gates unchanged, no Gold, G0.5 not frozen, "
              "references read-only, no authorization applied",
              safety.get("gates_unchanged") is True
              and safety.get("gold_predictions_results_contract_methods_unchanged")
              is True
              and safety.get("g0_5_frozen") is False
              and safety.get("references_read_only_not_activated") is True
              and safety.get("no_authorization_applied") is True)
        oc = report.get("oracle_control", {})
        check("oracle control unstarted/unauthorized with null sentence",
              oc.get("formal_oracle_started") is False
              and oc.get("formal_oracle_authorized") is False
              and oc.get("ready_for_oracle_authorization") is False
              and oc.get("authorization_sentence") is None
              and oc.get("no_pseudo_oracle") is True)
        check("zero_api recorded", report.get("zero_api", {}).get(
            "new_llm_api_calls") == 0)

    # 10. external checks -------------------------------------------------------
    if report and run_external:
        mismatch = []
        all_verified = True
        for rel, has_json in builder.INDEPENDENT_VERIFIERS:
            result = builder.run_independent_verifier(root, rel, has_json)
            recorded = (report.get("verifiers_executed") or {}).get(rel, {})
            if result.get("verified") is not True:
                all_verified = False
                mismatch.append(f"{rel}:run_failed")
            elif recorded.get("verified") is not True:
                mismatch.append(f"{rel}:recorded_not_verified")
            if has_json and recorded.get("checks") not in (None, 0) and \
                    result.get("checks") != recorded.get("checks"):
                mismatch.append(f"{rel}:checks_mismatch")
        check("seven independent verifiers executed and recorded values "
              "match", all_verified and not mismatch, "; ".join(mismatch))
        try:
            from formal_experiment.audit import collect_project_audit
            audit = collect_project_audit()
            check("audit integrity pass holds",
                  audit.get("integrity_pass") is True)
            claim_boundary = str(audit.get("claim_boundary", ""))
            if bool(audit.get("final_experiment_ready")):
                check("audit claim_boundary free of stale false statements",
                      "remains false" not in claim_boundary
                      and "NOT produced yet" not in claim_boundary)
        except Exception as exc:  # noqa: BLE001 - fail-closed reporting
            check("audit consistency re-check", False,
                  f"collect_project_audit raised: {exc}")

    verified = all(c["ok"] for c in checks)
    return {"verified": verified, "checks": checks}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true",
                        help="print machine-readable JSON result")
    parser.add_argument("--skip-external", action="store_true",
                        help="skip subprocess/audit re-checks")
    args = parser.parse_args()
    result = verify(run_external=not args.skip_external)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        for c in result["checks"]:
            print(("PASS" if c["ok"] else "FAIL"), c["name"],
                  ("- " + c["detail"]) if c["detail"] else "")
        print("S2.11/G0.5 PRE-AUTHORIZATION V5 VERIFIED"
              if result["verified"]
              else "S2.11/G0.5 PRE-AUTHORIZATION V5 NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
