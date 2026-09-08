# -*- coding: utf-8 -*-
"""Explicit promotion step: development GDPR Direct-LLM capsule ->
the formal arm capsule ``data/predictions/gdpr7_direct_llm_v1``.

This script makes the promotion/validation hook of
``docs/API_AUTHORIZATION_REQUEST.md`` section 13.4 executable (the 2026-09-07
placeholder "GDPR 74 -> explicit promotion ... 见 Task D 批实现"): the real
executor (``scripts/run_gdpr7_direct_llm_v1.py``) is hard-coded to refuse
writing under ``data/predictions`` and only publishes a development capsule
(e.g. ``outputs/development/gdpr7_direct_llm_real_v1`` after the authorized
real run); this script is the ONLY path that publishes the formal arm
capsule home consumed by the linkage runners
(``run_gdpr_3type_linkage_v1.ARM_LABELS["direct_llm"]`` /
``run_gdpr_s2_s3_linkage_v1.ARM_PATHS["direct_llm"]`` /
``reevaluate_s3_extended_unified_v1.SOURCES["direct_llm"]``).

What it does
------------
- Validates the development capsule directory (predictions / telemetry /
  cost / manifest) fail-closed:
  * telemetry ``status == "complete"`` (``complete_with_explicit_failures`` /
    ``partial`` are rejected -> exit 2) and the per-call counts agree
    (74 completed, 0 in_doubt, 0 failed, 74 ok prediction rows);
  * the run is a REAL authorized run, never a fake-program-verification run
    (fake rehearsal capsules are refused: promoting them into the formal
    home would corrupt the experiment);
  * prediction doc: schema ``gdpr7_direct_llm_predictions@1.0.0``, 74/74
    rows, every row ``request_status == "ok"`` with ``error_category``
    null (any in_doubt/failed row is rejected and listed);
  * manifest / capsule-file consistency: the capsule manifest's
    ``input_binding.sha256`` equals the actual SHA-256 of
    ``data/input/gdpr7_stage2_input_v1.json`` and equals the preflight
    report's recorded input SHA-256; the manifest's ``preflight_binding``
    matches the on-disk preflight report; all four doc schemas are the
    executor's own;
  * containment scan (mirrors ``scripts/finalize_s2_12_arm_v1.py``'s
    ``_scan_forbidden``): no raw-text key and no decision/Gold key anywhere
    in the four documents (rows are coordinate-only by contract);
- ``--dry-run`` (default) prints the validation checklist and the would-be
  publish plan without writing anything;
- ``--apply`` publishes to the target atomically ONLY when the target does
  not exist (refusing any overwrite), byte-copying predictions/telemetry/
  cost/manifest and adding a promotion manifest
  (schema ``gdpr7_direct_llm_promotion@1.0.0``: source dev path/sha, target
  shas, validation checklist, reproduce/rollback commands,
  ``gold_rule_records_created=false``, ``oracle_started=false``);
- prints the "next step" linkage commands (3-type linkage, 4-type linkage,
  unified five-class re-evaluation, formula-repair re-run) so §13.4 is a
  closed executable loop.

Zero LLM/API/network/.env.  Reads only the development capsule, the GDPR
Stage-2 input pack and the preflight report; writes only the target capsule
(``--apply``) or nothing (``--dry-run``).  Promotion does NOT re-convert raw
responses: the executor already committed canonical coordinate-only rows to
the development capsule and this step publishes those bytes.

Usage (run from ``formal_experiment/``)::

    python scripts/promote_gdpr7_direct_llm_arm_v1.py \
        --capsule-dir outputs/development/gdpr7_direct_llm_real_v1 --dry-run
    python scripts/promote_gdpr7_direct_llm_arm_v1.py \
        --capsule-dir outputs/development/gdpr7_direct_llm_real_v1 --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]

# Doc schema identities.  These MUST equal the executor's own constants in
# ``scripts/run_gdpr7_direct_llm_v1.py`` (PREDICTION_SCHEMA / TELEMETRY_SCHEMA
# / COST_SCHEMA / MANIFEST_SCHEMA / ARM_CAPSULE_PATH); a drift is a contract
# error and is covered by a focused test comparing both modules.
PREDICTION_SCHEMA = "gdpr7_direct_llm_predictions@1.0.0"
TELEMETRY_SCHEMA = "gdpr7_direct_llm_telemetry@1.0.0"
COST_SCHEMA = "gdpr7_direct_llm_cost@1.0.0"
MANIFEST_SCHEMA = "gdpr7_direct_llm_manifest@1.0.0"
PROMOTION_SCHEMA = "gdpr7_direct_llm_promotion@1.0.0"
DATASET_ID = "gdpr7_stage2_sentences_v1"
EXPECTED_RECORDS = 74

DEFAULT_CAPSULE_DIR = ROOT / "outputs/development/gdpr7_direct_llm_real_v1"
DEFAULT_TARGET = ROOT / "data/predictions/gdpr7_direct_llm_v1"
DEFAULT_PREFLIGHT_REPORT = ROOT / "outputs/reports/gdpr7_direct_llm_preflight_v1.json"
INPUT_PACK = ROOT / "data/input/gdpr7_stage2_input_v1.json"
ARM_CAPSULE_REL = "data/predictions/gdpr7_direct_llm_v1"

# Raw-text keys that must never appear in committed capsule documents
# (mirror of ``finalize_s2_12_arm_v1`` / the executor's containment scan).
_FORBIDDEN_TEXT_KEYS = (
    "text", "source_text", "approved_text_en", "normalized", "marker_surface",
)
# Gold / decision keys that must never appear in committed capsule documents.
_FORBIDDEN_DECISION_KEYS = (
    "expected", "decision", "gold", "ground_truth", "oracle",
    "expected_violation", "human_correction", "adjudicat", "gold_rule",
)
_CAPSULE_FILES = ("predictions.json", "telemetry.json", "cost.json",
                  "manifest.json")


class PromotionError(ValueError):
    """Fail-closed promotion error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise PromotionError(f"{label} missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromotionError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise PromotionError(f"{label} root must be a JSON object")
    return value


def _scan_forbidden(name: str, value: Any) -> list[str]:
    """Return every forbidden text/Gold key path in one document (by key).

    Mirrors ``scripts/finalize_s2_12_arm_v1._scan_forbidden``.
    """
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _FORBIDDEN_TEXT_KEYS:
                hits.append(f"{name}.{key}")
            elif key in _FORBIDDEN_DECISION_KEYS:
                hits.append(f"{name}.{key}")
            hits.extend(_scan_forbidden(f"{name}.{key}", child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_scan_forbidden(f"{name}[{index}]", item))
    return hits


# ---------------------------------------------------------------------------
# Pure validation (unit-testable on synthetic capsule dirs)
# ---------------------------------------------------------------------------


def validate_capsule_dir(capsule_dir: Path,
                         preflight_report: Path) -> tuple[list[str], dict[str, Any]]:
    """Fail-closed validation of one development capsule directory.

    Returns ``(errors, checks)``.  ``errors`` is empty exactly when the
    capsule may be promoted.  ``checks`` is a JSON-able checklist suitable
    for the promotion manifest.  Never writes.
    """
    errors: list[str] = []
    checks: dict[str, Any] = {"capsule_dir": _rel(capsule_dir)}

    for name in _CAPSULE_FILES:
        if not (capsule_dir / name).is_file():
            errors.append(f"capsule file missing: {name}")
    if errors:
        return errors, checks
    docs: dict[str, dict[str, Any]] = {}
    try:
        for name in _CAPSULE_FILES:
            docs[name] = _load_json(capsule_dir / name, f"capsule {name}")
    except PromotionError as exc:
        return [str(exc)], checks
    checks["files"] = {
        name: {"sha256": _sha(capsule_dir / name),
               "byte_size": (capsule_dir / name).stat().st_size}
        for name in _CAPSULE_FILES
    }

    # ---- doc schema identities
    expected_schemas = {
        "predictions.json": PREDICTION_SCHEMA,
        "telemetry.json": TELEMETRY_SCHEMA,
        "cost.json": COST_SCHEMA,
        "manifest.json": MANIFEST_SCHEMA,
    }
    for name, schema in expected_schemas.items():
        if docs[name].get("schema_version") != schema:
            errors.append(
                f"{name} schema mismatch: got "
                f"{docs[name].get('schema_version')!r}, expected {schema!r}")

    # ---- telemetry completeness
    telemetry = docs["telemetry.json"]
    status = telemetry.get("status")
    checks["telemetry_status"] = status
    if status != "complete":
        errors.append(
            f"telemetry.status is {status!r}; promotion requires 'complete' "
            "(complete_with_explicit_failures / partial -> reject, exit 2)")
    if telemetry.get("records_expected") != EXPECTED_RECORDS:
        errors.append(f"telemetry.records_expected drift: "
                      f"{telemetry.get('records_expected')!r}")
    if telemetry.get("in_doubt_calls") not in (0, None):
        errors.append(f"telemetry.in_doubt_calls = {telemetry.get('in_doubt_calls')}")
    if telemetry.get("failed_calls") not in (0, None):
        errors.append(f"telemetry.failed_calls = {telemetry.get('failed_calls')}")
    if telemetry.get("completed_calls") != EXPECTED_RECORDS:
        errors.append(f"telemetry.completed_calls = "
                      f"{telemetry.get('completed_calls')}, expected "
                      f"{EXPECTED_RECORDS}")
    checks["telemetry"] = {
        "status": status,
        "records_expected": telemetry.get("records_expected"),
        "completed_calls": telemetry.get("completed_calls"),
        "in_doubt_calls": telemetry.get("in_doubt_calls"),
        "failed_calls": telemetry.get("failed_calls"),
        "ok_prediction_rows": telemetry.get("ok_prediction_rows"),
    }

    # ---- real-run gate (never promote a fake program-verification capsule)
    fake_flags = [
        telemetry.get("fake_run_program_verification_only"),
        telemetry.get("transport"),
        docs["manifest.json"].get("transport"),
        docs["cost.json"].get("transport"),
    ]
    manifest = docs["manifest.json"]
    checks["transport"] = {
        "telemetry": telemetry.get("transport"),
        "manifest": manifest.get("transport"),
        "cost": docs["cost.json"].get("transport"),
        "fake_run_program_verification_only": fake_flags[0],
    }
    if telemetry.get("fake_run_program_verification_only") is True:
        errors.append(
            "refusing to promote a fake program-verification capsule "
            "(telemetry.fake_run_program_verification_only is true); only a "
            "real authorized run may be promoted to the formal arm home")
    if telemetry.get("transport") != "real_authorized":
        errors.append(
            f"telemetry.transport = {telemetry.get('transport')!r}; promotion "
            "requires a real_authorized run")
    if manifest.get("transport") != "real_authorized":
        errors.append(
            f"manifest.transport = {manifest.get('transport')!r}; promotion "
            "requires a real_authorized run")
    auth = manifest.get("authorization") or {}
    if auth.get("real_authorized") is not True:
        errors.append("manifest.authorization.real_authorized is not True; "
                      "only a user-authorized real run may be promoted")
    safety = manifest.get("safety") or {}
    llm_calls = safety.get("llm_api_calls")
    if not isinstance(llm_calls, int) or llm_calls < EXPECTED_RECORDS:
        errors.append(
            f"manifest.safety.llm_api_calls = {llm_calls!r}; a real run must "
            f"report at least {EXPECTED_RECORDS} calls")
    checks["real_run"] = {
        "llm_api_calls": llm_calls,
        "gold_rule_records_created": safety.get("gold_rule_records_created"),
        "oracle_started": safety.get("oracle_started"),
    }
    if manifest.get("status") not in (None, "complete"):
        errors.append(f"manifest.status = {manifest.get('status')!r}")

    # ---- predictions completeness
    pred = docs["predictions.json"]
    records = pred.get("records") or []
    checks["predictions"] = {
        "record_count_declared": pred.get("record_count"),
        "record_rows": len(records),
        "dataset_id": pred.get("dataset_id"),
        "method_id": pred.get("method_id"),
    }
    if pred.get("record_count") != EXPECTED_RECORDS:
        errors.append(f"predictions.record_count = "
                      f"{pred.get('record_count')!r}, expected "
                      f"{EXPECTED_RECORDS}")
    if len(records) != EXPECTED_RECORDS:
        errors.append(f"predictions has {len(records)} rows, expected "
                      f"{EXPECTED_RECORDS}")
    bad_rows: list[str] = []
    sample_ids: list[str] = []
    for rec in records:
        sid = rec.get("sample_id")
        sample_ids.append(str(sid))
        if rec.get("request_status") != "ok":
            bad_rows.append(f"{sid}:request_status={rec.get('request_status')!r}")
        if rec.get("error_category") not in (None, ""):
            bad_rows.append(f"{sid}:error_category={rec.get('error_category')!r}")
    if bad_rows:
        errors.append("predictions contains in_doubt/failed rows "
                      f"({len(bad_rows)}): " + "; ".join(bad_rows[:20]))
    duplicate_ids = sorted({sid for sid in sample_ids if sample_ids.count(sid) > 1})
    if duplicate_ids:
        errors.append(f"predictions duplicate sample ids: {duplicate_ids}")

    # ---- containment scan (mirrors the S2.12 finalize scan)
    containment_hits: dict[str, list[str]] = {}
    for name in _CAPSULE_FILES:
        hits = _scan_forbidden(name, docs[name])
        if hits:
            containment_hits[name] = hits
            errors.append(f"containment scan failed for {name}: "
                          f"{hits[:10]}{' ...' if len(hits) > 10 else ''}")
    checks["containment"] = {"clean": not containment_hits,
                             "hits": containment_hits}

    # ---- manifest binding to the input pack + preflight report
    binding: dict[str, Any] = {}
    checks["binding"] = binding
    input_binding = manifest.get("input_binding") or {}
    binding["input_path_declared"] = input_binding.get("path")
    if input_binding.get("path") not in (None,
                                         "data/input/gdpr7_stage2_input_v1.json"):
        errors.append(f"manifest input_binding.path = "
                      f"{input_binding.get('path')!r}")
    actual_input_sha = _sha(INPUT_PACK) if INPUT_PACK.is_file() else None
    binding["input_sha256_actual"] = actual_input_sha
    binding["input_sha256_declared"] = input_binding.get("sha256")
    if actual_input_sha is None:
        errors.append(f"GDPR Stage-2 input missing: {INPUT_PACK}")
    elif input_binding.get("sha256") != actual_input_sha:
        errors.append("manifest input_binding.sha256 does not match "
                      "data/input/gdpr7_stage2_input_v1.json on disk")
    preflight_actual = None
    if preflight_report.is_file():
        preflight_actual = _sha(preflight_report)
        try:
            preflight_doc = _load_json(preflight_report, "preflight report")
            pre_input = (preflight_doc.get("input") or {}).get("sha256")
            binding["preflight_input_sha256"] = pre_input
            if pre_input is not None and pre_input != actual_input_sha:
                errors.append(
                    "preflight report input sha does not match the input pack "
                    "on disk (source binding drift)")
        except PromotionError as exc:
            errors.append(str(exc))
    preflight_binding = manifest.get("preflight_binding") or {}
    binding["preflight_report_sha256_actual"] = preflight_actual
    binding["preflight_report_sha256_declared"] = \
        preflight_binding.get("sha256")
    binding["preflight_report_path_declared"] = preflight_binding.get("path")
    if preflight_actual is None:
        errors.append(f"preflight report missing: {preflight_report}")
    elif preflight_binding.get("sha256") != preflight_actual:
        errors.append("manifest preflight_binding.sha256 does not match the "
                      "preflight report on disk")
    arm_capsule = manifest.get("arm_capsule") or {}
    if arm_capsule.get("path") != ARM_CAPSULE_REL:
        errors.append(f"manifest arm_capsule.path = "
                      f"{arm_capsule.get('path')!r}, expected "
                      f"{ARM_CAPSULE_REL!r}")
    if arm_capsule.get("schema") != PREDICTION_SCHEMA:
        errors.append(f"manifest arm_capsule.schema = "
                      f"{arm_capsule.get('schema')!r}")
    return errors, checks


def next_step_commands(capsule_dir: Path, target: Path) -> list[str]:
    """The §13.4 downstream commands printed after a successful promotion."""
    return [
        "python scripts/run_gdpr_3type_linkage_v1.py --arm direct_llm",
        "python scripts/run_gdpr_s2_s3_linkage_v1.py --arm direct_llm",
        "python scripts/reevaluate_s3_extended_unified_v1.py --source "
        "direct_llm",
        ("python scripts/run_s3_formula_repair_v2.py --sources "
         "reference,rules_only,direct_llm --output <NEW_OUTPUT_DIR> "
         "--report <NEW_REPORT_PATH>   # fresh dirs only; historical "
         "outputs/evidence/s3_formula_repair_v2 is preserved"),
    ]


def plan_promotion(capsule_dir: Path, target: Path,
                   preflight_report: Path) -> dict[str, Any]:
    """Validate + describe the promotion (no writes).

    Raises ``PromotionError`` on any validation failure (fail closed).
    """
    capsule_dir = Path(capsule_dir).resolve()
    target = Path(target).resolve()
    errors, checks = validate_capsule_dir(capsule_dir, preflight_report)
    if errors:
        raise PromotionError("; ".join(errors))
    dev_manifest = json.loads(
        (capsule_dir / "manifest.json").read_text(encoding="utf-8"))
    return {
        "schema_version": PROMOTION_SCHEMA,
        "promotion_id": "gdpr7_direct_llm_arm_promotion_v1",
        "status": "pending",
        "source": {
            "dev_capsule_dir": _rel(capsule_dir),
            "files": checks["files"],
            "dev_manifest_sha256": checks["files"]["manifest.json"]["sha256"],
        },
        "target": {"dir": _rel(target), "exists": target.exists()},
        "validation": {
            "checklist": checks,
            "errors": [],
            "reproduce_command_real":
                dev_manifest.get("reproduce_command_real"),
        },
        "next_steps": next_step_commands(capsule_dir, target),
    }


def publish_promotion(capsule_dir: Path, target: Path,
                      preflight_report: Path,
                      now_utc: datetime | None = None) -> dict[str, Any]:
    """Validate then atomically publish the formal arm capsule.

    Refuses when the target already exists (no overwrite).  On success the
    target directory contains predictions/telemetry/cost/manifest (byte
    copies of the development capsule) plus ``promotion_manifest.json``.
    """
    capsule_dir = Path(capsule_dir).resolve()
    target = Path(target).resolve()
    if target.exists():
        raise PromotionError(
            f"refusing to overwrite existing target capsule: {target} "
            "(promotion is one-shot; remove the target explicitly only with "
            "full user awareness)")
    plan = plan_promotion(capsule_dir, target, preflight_report)
    now_utc = now_utc or datetime.now(timezone.utc)
    files = {name: (capsule_dir / name).read_bytes() for name in _CAPSULE_FILES}
    promotion_manifest = {
        "schema_version": PROMOTION_SCHEMA,
        "promotion_id": "gdpr7_direct_llm_arm_promotion_v1",
        "status": "applied",
        "applied_utc": now_utc.isoformat(),
        "source": plan["source"],
        "target": {
            "dir": _rel(target),
            "files": {name: {"sha256": _sha_bytes(data),
                             "byte_size": len(data)}
                      for name, data in files.items()},
        },
        "validation": plan["validation"],
        "input_binding": {
            "path": "data/input/gdpr7_stage2_input_v1.json",
            "sha256": plan["validation"]["checklist"]["binding"][
                "input_sha256_actual"],
            "preflight_report_sha256": plan["validation"]["checklist"][
                "binding"]["preflight_report_sha256_actual"],
        },
        "reproduce_command_real": plan["validation"]["reproduce_command_real"],
        "rollback_command": (
            "rm -rf " + _rel(target).replace(os.sep, "/") +
            "   # only with full user awareness; the arm capsule is one-shot"),
        "next_steps": plan["next_steps"],
        "safety": {
            "gold_rule_records_created": False,
            "oracle_started": False,
            "raw_text_committed": False,
            "overwrote_existing_target": False,
        },
    }
    files["promotion_manifest.json"] = _json_bytes(promotion_manifest)

    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.parent / f".{target.name}.staging-{os.getpid()}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    try:
        for name, data in files.items():
            (stage / name).write_bytes(data)
        stage.rename(target)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    # Read-back verification of the four published files: on-disk shas must
    # equal the recorded ones (the promotion manifest is re-written with the
    # verification results; the published files themselves are unchanged).
    verified = {}
    for name in _CAPSULE_FILES:
        on_disk = _sha(target / name)
        recorded = promotion_manifest["target"]["files"][name]["sha256"]
        verified[name] = {"matches": on_disk == recorded, "sha256": on_disk}
    promotion_manifest["target"]["verified"] = verified
    promotion_manifest["status"] = "applied_verified"
    (target / "promotion_manifest.json").write_bytes(_json_bytes(
        promotion_manifest))
    return promotion_manifest


def _print_plan(plan: Mapping[str, Any]) -> None:
    print("gdpr7 direct-llm arm promotion -- DRY RUN (nothing written)")
    print(f"  source dev capsule: {plan['source']['dev_capsule_dir']}")
    print(f"  target:            {plan['target']['dir']} "
          f"(exists: {plan['target']['exists']})")
    print("  validation checklist:")
    checklist = plan["validation"]["checklist"]
    for key in ("telemetry", "predictions", "transport", "real_run",
                "containment", "binding"):
        if key in checklist:
            print(f"    - {key}: {json.dumps(checklist[key], ensure_ascii=False)}")
    print("  would publish (bytes from dev capsule, byte-identical):")
    for name, info in sorted(plan["source"]["files"].items()):
        print(f"    - {name}: sha256 {info['sha256'][:16]}... "
              f"({info['byte_size']} bytes)")
    print("  + promotion_manifest.json "
          f"(schema {PROMOTION_SCHEMA})")
    print("  reproduce (real): "
          f"{plan['validation']['reproduce_command_real']}")
    print("  next steps:")
    for step in plan["next_steps"]:
        print(f"    $ {step}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capsule-dir", type=Path, default=DEFAULT_CAPSULE_DIR,
                        help="development capsule directory (predictions/"
                             "telemetry/cost/manifest); default "
                             "outputs/development/gdpr7_direct_llm_real_v1")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET,
                        help="formal arm capsule home; default "
                             "data/predictions/gdpr7_direct_llm_v1")
    parser.add_argument("--preflight-report", type=Path,
                        default=DEFAULT_PREFLIGHT_REPORT,
                        help="locked preflight report (default "
                             "outputs/reports/gdpr7_direct_llm_preflight_v1.json)")
    parser.add_argument("--apply", action="store_true",
                        help="validate and atomically publish the arm capsule "
                             "(default is --dry-run: validate + print only)")
    args = parser.parse_args(argv)
    try:
        if not args.apply:
            plan = plan_promotion(args.capsule_dir, args.target,
                                  args.preflight_report)
            _print_plan(plan)
            return 0
        result = publish_promotion(args.capsule_dir, args.target,
                                   args.preflight_report)
    except PromotionError as exc:
        print(f"gdpr7 direct-llm arm promotion refused: {exc}", file=sys.stderr)
        return 2
    print("gdpr7 direct-llm arm promotion APPLIED")
    print(f"  target: {result['target']['dir']}")
    print(f"  promotion manifest: "
          f"{result['target']['dir']}/promotion_manifest.json")
    for name, info in sorted(result["target"]["files"].items()):
        print(f"    - {name}: sha256 {info['sha256'][:16]}... verified "
              f"{result['target']['verified'][name]['matches']}")
    print(f"  rollback: {result['rollback_command']}")
    print("  next steps (make §13.4 executable):")
    for step in result["next_steps"]:
        print(f"    $ {step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
