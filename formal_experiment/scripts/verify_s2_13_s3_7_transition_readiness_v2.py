# -*- coding: utf-8 -*-
"""Fail-closed independent verifier for the S2.13 -> S3.7 transition
capsule v2.

Re-verifies the capsule WITHOUT trusting the builder's in-memory payloads:
  1. report JSON is readable and schema-valid
  2. the COMPLETE expected manifest is deterministically re-constructed in
     memory from the disk report JSON bytes, the disk Markdown bytes and
     the re-collected bindings, and must equal the on-disk manifest
     STRUCTURE EXACTLY (schema version, manifest ID, artifact type,
     determinism, report artifact path/hash/byte_size, the exact bindings
     key set and values, the exact implementation key set, safety,
     zero_api; no missing and no extra entries anywhere)
  3. the COMPLETE expected export index is deterministically re-constructed
     from the disk report JSON, Markdown and manifest bytes and must equal
     the on-disk export structure exactly (no missing or extra entries;
     recomputing outer hashes cannot bypass the structural comparison)
  4. every manifest binding SHA-256 is recomputed from disk (redundant
     with 2, kept for precise diagnostics)
  5. the Markdown report is re-rendered from the JSON and must be
     byte-identical AND end with exactly one EOF newline
  6. the dependency matrix is re-derived in memory from disk and compared
     item-by-item with the report
  7. Stage 1 Process Gold / Stage 3 decision Gold / the THREE-STATE
     Gold-Rule-Record probe (no candidate may exist; the checked Stage 2
     EStG-150 Gold must be bound) / Oracle control flags are re-derived
  8. Stage 3 development evidence is checked for existence, manifest/hash
     binding and development-only claim; it is NEVER promoted to formal
  9. every superseded historical report AND every v1 capsule file still
     exists byte-identical (precedence: the new ledger supersedes, never
     rewrites)
  10. the seven independent verifiers are actually executed; non-JSON
      verifiers require exit code 0 AND an explicit success verdict (the
      bare "VERIFIED" substring is rejected because "NOT VERIFIED" also
      contains it)
  11. collect_project_audit() is re-run: the recorded
      final_experiment_ready must match and the audit must be free of the
      stale true/false contradiction

Exit 0 iff everything verifies; any tampering of a dependency, a hash, the
rule-ID set, Gold identity, old/new report precedence, oracle_started, a
manifest/export omission or extra entry, or a candidate Gold Rule Record
fails closed with exit 1.

Also importable:
    from scripts.verify_s2_13_s3_7_transition_readiness_v2 import verify
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
    "s2_13_s3_7_transition_readiness_v2.json"
OUT_MD = ROOT / "outputs" / "reports" / \
    "s2_13_s3_7_transition_readiness_v2.md"
OUT_MANIFEST = ROOT / "outputs" / "reports" / \
    "s2_13_s3_7_transition_readiness_v2.manifest.json"
OUT_EXPORT = ROOT / "outputs" / "reports" / \
    "s2_13_s3_7_transition_readiness_v2_export_index.json"
SCHEMA = ROOT / "configs" / "schemas" / \
    "s2_13_s3_7_transition_readiness_v2.schema.json"

EXPECTED_RULE_IDS = [
    "article6", "article7", "article15", "article16", "article17",
    "article20", "article22", "article33", "article34",
]


def _load_builder() -> Any:
    """Load the builder module (shared pure derivation functions)."""
    spec = importlib.util.spec_from_file_location(
        "s2_13_s3_7_transition_readiness_builder_v2",
        ROOT / "scripts" / "build_s2_13_s3_7_transition_readiness_v2.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _display_rel(path: Path) -> str:
    """Path for display; falls back to the absolute path when the given
    path is outside the project root (e.g. pytest tmp_path fixtures)."""
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


def _matrix_diff(report_matrix: Any, derived: Any) -> str:
    if report_matrix == derived:
        return ""
    diffs: list[str] = []
    for stage_key in ("stage1", "stage2", "stage3"):
        rep = {i["task_id"]: i for i in report_matrix.get(stage_key, [])}
        der = {i["task_id"]: i for i in derived.get(stage_key, [])}
        for task_id in sorted(set(rep) | set(der)):
            if rep.get(task_id) != der.get(task_id):
                diffs.append(f"{stage_key}/{task_id}")
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

    # 1. report readable -------------------------------------------------
    report: dict[str, Any] = _load_json(report_path)
    check("report JSON readable", bool(report),
          _display_rel(report_path) if report_path.exists()
          else "missing report file")

    # 2. schema validation ------------------------------------------------
    schema = _load_json(SCHEMA)
    check("capsule schema readable", bool(schema))
    if report and schema:
        errors = builder._schema_errors(schema, report)
        check("report schema valid", not errors,
              "; ".join(errors[:5]))

    # 3. manifest EXACT reconstruction (v2) --------------------------------
    manifest = _load_json(manifest_path)
    check("manifest readable", bool(manifest))
    if report and manifest_path.is_file():
        try:
            report_bytes = report_path.read_bytes()
            md_bytes = md_path.read_bytes() if md_path.exists() else b""
            bindings = builder.collect_bindings(root, report)
            expected_manifest = builder.build_manifest(
                root, report_bytes, md_bytes, bindings)
            mismatch = []
            for key in sorted(set(expected_manifest) | set(manifest)):
                if expected_manifest.get(key) != manifest.get(key):
                    mismatch.append(key)
            check("manifest exact reconstruction matches disk (structure, "
                  "keys, values; no missing/extra entries)", not mismatch,
                  "; ".join(mismatch) or "manifest equals reconstruction")
        except Exception as exc:  # noqa: BLE001 - fail-closed reporting
            check("manifest exact reconstruction matches disk (structure, "
                  "keys, values; no missing/extra entries)", False,
                  f"reconstruction raised: {exc}")
    # 3b. manifest entry-level diagnostics (redundant, precise errors)
    if manifest:
        bad: list[str] = []
        for rel, want in sorted((manifest.get("bindings") or {}).items()):
            p = root / rel
            if not p.is_file() or _sha256_file(p) != want:
                bad.append(rel)
        check("manifest bindings match disk", not bad,
              "; ".join(bad[:10]))
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

    # 4. export index EXACT reconstruction (v2) -----------------------------
    export = _load_json(export_path)
    check("export index readable", bool(export))
    if report and manifest_path.is_file() and export_path.is_file():
        try:
            report_bytes = report_path.read_bytes()
            md_bytes = md_path.read_bytes() if md_path.exists() else b""
            manifest_bytes = manifest_path.read_bytes()
            expected_export = builder.build_export_index(
                root, report_bytes, md_bytes, manifest_bytes)
            mismatch = []
            for key in sorted(set(expected_export) | set(export)):
                if expected_export.get(key) != export.get(key):
                    mismatch.append(key)
            check("export index exact reconstruction matches disk "
                  "(structure, keys, values; recomputed hashes cannot "
                  "bypass)", not mismatch, "; ".join(mismatch))
        except Exception as exc:  # noqa: BLE001 - fail-closed reporting
            check("export index exact reconstruction matches disk "
                  "(structure, keys, values; recomputed hashes cannot "
                  "bypass)", False, f"reconstruction raised: {exc}")
    # 4b. export entry-level diagnostics (redundant, precise errors)
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
        man_info = export.get("manifest") or {}
        mpath = root / man_info.get("path", "")
        check("export index manifest entry matches disk",
              mpath.is_file() and _sha256_file(mpath)
              == man_info.get("sha256"))

    # 5. Markdown deterministic re-render + single EOF newline ---------------
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

    # 6. dependency matrix re-derivation ----------------------------------
    if report:
        try:
            derived_matrix = builder.derive_dependency_matrix(root)
            diff = _matrix_diff(report.get("dependency_matrix", {}),
                                derived_matrix)
            check("dependency matrix re-derived and compared item-by-item",
                  not diff, diff)
        except Exception as exc:  # noqa: BLE001 - fail-closed reporting
            check("dependency matrix re-derived and compared item-by-item",
                  False, f"derivation raised: {exc}")

    # 7. Stage 1 Process Gold / Stage 3 decision Gold ----------------------
    if report:
        try:
            pg = report.get("stage1_process_gold", {})
            pg_path = root / pg.get("path", "\0")
            check("Stage 1 Process Gold exists with recorded hash",
                  bool(pg.get("exists"))
                  and pg_path.is_file()
                  and _sha256_file(pg_path) == pg.get("sha256"))
            dg = report.get("stage3_decision_gold", {})
            corr_path = root / dg.get("frozen_correction", {}).get(
                "path", "\0")
            corr_sha = _sha256_file(corr_path) if corr_path.is_file() \
                else "missing"
            consistent = bool(
                dg.get("consistency_with_frozen_correction")
                and dg.get("matching", {}).get("count") == 25
                and dg.get("violation", {}).get("count") == 33
                and _load_json(root / dg["matching"]["path"]).get(
                    "sources", {}).get("correction_pack_sha256") == corr_sha
                and _load_json(root / dg["violation"]["path"]).get(
                    "sources", {}).get("correction_pack_sha256") == corr_sha)
            check("Stage 3 matching/violation Gold exist and consistent with "
                  "frozen correction", consistent)
        except Exception as exc:  # noqa: BLE001 - fail-closed reporting
            check("Stage 3 matching/violation Gold exist and consistent with "
                  "frozen correction", False,
                  f"check raised: {exc}")

    # 8. Gold Rule Records: three-state probe + checked EStG-150 Gold --------
    if report:
        try:
            derived_grr = builder.derive_gold_rule_records(root)
            grr = report.get("gold_rule_records", {})
            probe = grr.get("candidate_probe", {})
            checked = grr.get("checked_stage2_estg150_gold", {})
            checked_path = root / checked.get("path", "\0")
            same = bool(
                derived_grr.get("exist") == grr.get("exist")
                and derived_grr.get("covered_rule_ids")
                == grr.get("covered_rule_ids")
                and grr.get("exist") is False
                and len(grr.get("covered_rule_ids") or []) == 9
                and probe.get("found") == []
                and checked_path.is_file()
                and _sha256_file(checked_path) == checked.get("sha256")
                and checked.get("path")
                == "data/gold/stage2/estg150_formal_gold_v1.json")
            check("Gold Rule Records three-state probe: no candidate, "
                  "exist=false, 9 rule IDs, checked EStG-150 Gold bound",
                  same,
                  f"report={grr.get('exist')},"
                  f"{grr.get('covered_rule_ids')},probe={probe.get('found')}; "
                  f"derived={derived_grr.get('exist')},"
                  f"{derived_grr.get('covered_rule_ids')}")
            # verifier re-probes independently: any candidate must fail
            candidates = builder._probe_gold_rule_record_candidates(root)
            check("verifier re-probe finds no Gold Rule Record candidate",
                  candidates == [],
                  "; ".join(p.relative_to(root).as_posix()
                            for p, _ in candidates))
        except Exception as exc:  # noqa: BLE001 - fail-closed reporting
            check("Gold Rule Records three-state probe: no candidate, "
                  "exist=false, 9 rule IDs, checked EStG-150 Gold bound",
                  False, f"derivation raised: {exc}")

    # 9. Stage 3 development-only claim -------------------------------------
    if report:
        dev = report.get("stage3_development_only", {})
        dev_ok = True
        dev_detail: list[str] = []
        for key in ("s3_4", "s3_5", "s3_6"):
            item = dev.get(key, {})
            if item.get("status") != "development_only":
                dev_ok = False
                dev_detail.append(f"{key}:status={item.get('status')}")
            for ev in item.get("evidence", []):
                p = root / ev.get("path", "\0")
                if not p.is_file() or _sha256_file(p) != ev.get("sha256"):
                    dev_ok = False
                    dev_detail.append(f"{key}:evidence:{ev.get('path')}")
        check("Stage 3 development evidence exists, hash-bound and "
              "NOT promoted to formal", dev_ok, "; ".join(dev_detail[:5]))

    # 10. Oracle control -----------------------------------------------------
    if report:
        try:
            derived_orc = builder.derive_oracle_control(root)
            oc = report.get("oracle_control", {})
            flags = ("formal_oracle_started", "formal_oracle_authorized",
                     "ready_for_oracle_authorization")
            same = all(oc.get(k) == derived_orc.get(k) for k in flags)
            check("oracle control flags re-derived",
                  same and oc.get("no_pseudo_oracle") is True
                  and oc.get("authorization_sentence") is None,
                  f"report={ {k: oc.get(k) for k in flags} }; "
                  f"derived={ {k: derived_orc.get(k) for k in flags} }")
            check("formal Oracle NOT started and NOT authorized",
                  oc.get("formal_oracle_started") is False
                  and oc.get("formal_oracle_authorized") is False
                  and oc.get("ready_for_oracle_authorization") is False)
        except Exception as exc:  # noqa: BLE001 - fail-closed reporting
            check("oracle control flags re-derived", False,
                  f"derivation raised: {exc}")

    # 11. Supersedes precedence: historical reports + FULL v1 capsule --------
    if report:
        supers = report.get("supersedes", [])
        missing_or_changed = []
        for item in supers:
            p = root / item.get("path", "\0")
            if not p.is_file() or _sha256_file(p) != item.get("sha256"):
                missing_or_changed.append(item.get("path"))
        required_stale = [
            "outputs/reports/s2_13_stage2_freeze_gap_capsule.json",
            "outputs/reports/s2_13_stage2_freeze_gap_capsule.md",
            "outputs/reports/s3_7_oracle_readiness_v2.json",
            "outputs/reports/s37_oracle_readiness_v1.json",
            "outputs/reports/formal_benchmark_release_v2.manifest.json",
            "scripts/build_s1_5_s3_7_readiness_v1.py",
            "scripts/build_s3_7_oracle_readiness.py",
            "configs/schemas/s2_13_s3_7_transition_readiness.schema.json",
            "scripts/build_s2_13_s3_7_transition_readiness_v1.py",
            "scripts/verify_s2_13_s3_7_transition_readiness_v1.py",
            "tests/test_s2_13_s3_7_transition_readiness_v1.py",
            "outputs/reports/s2_13_s3_7_transition_readiness_v1.json",
            "outputs/reports/s2_13_s3_7_transition_readiness_v1.md",
            "outputs/reports/s2_13_s3_7_transition_readiness_v1.manifest.json",
            "outputs/reports/s2_13_s3_7_transition_readiness_v1_export_index.json",
        ]
        declared = {item.get("path") for item in supers}
        check("superseded historical reports + full v1 capsule present, "
              "byte-unchanged and declared", not missing_or_changed
              and set(required_stale) <= declared,
              "; ".join(missing_or_changed)
              or f"missing declarations: {sorted(set(required_stale) - declared)}")

    # 12. Verification scope flags ------------------------------------------
    if report:
        scope = report.get("verification_scope", {})
        check("verification_scope declares v2 fail-closed guarantees",
              all(scope.get(k) is True for k in (
                  "exact_manifest_reconstruction",
                  "exact_export_reconstruction",
                  "strict_verifier_verdict",
                  "gold_rule_record_three_state_probe",
                  "markdown_single_eof_newline")))

    # 13. External checks ----------------------------------------------------
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
            recorded_ready = report.get("audit_consistency", {}).get(
                "final_experiment_ready")
            actual_ready = bool(audit.get("final_experiment_ready"))
            check("audit final_experiment_ready matches recorded value",
                  recorded_ready == actual_ready,
                  f"recorded={recorded_ready}, actual={actual_ready}")
            claim_boundary = str(audit.get("claim_boundary", ""))
            warn_msgs = [
                item.get("message", "")
                for item in audit.get("findings", {}).get("warnings", [])
                if item.get("code") == "estg_reconstruction_development_only"]
            warn_text = "\n".join(warn_msgs)
            if actual_ready:
                check("audit claim_boundary free of stale false statements",
                      "remains false" not in claim_boundary
                      and "NOT produced yet" not in claim_boundary
                      and "capsule covers all three methods"
                      in claim_boundary)
                check("audit estg warning free of stale false statements",
                      "remains false" not in warn_text)
            else:
                check("audit false branch states only real computation "
                      "conditions", "Stage 3 completion" not in claim_boundary
                      and "says nothing about S2.13/S3.7/full-pipeline"
                      in claim_boundary)
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
                        help="skip the subprocess/audit re-checks "
                             "(static checks only)")
    args = parser.parse_args()
    result = verify(run_external=not args.skip_external)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        for c in result["checks"]:
            print(("PASS" if c["ok"] else "FAIL"), c["name"],
                  ("- " + c["detail"]) if c["detail"] else "")
        print("S2.13/S3.7 TRANSITION READINESS V2 VERIFIED"
              if result["verified"]
              else "S2.13/S3.7 TRANSITION READINESS V2 NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
