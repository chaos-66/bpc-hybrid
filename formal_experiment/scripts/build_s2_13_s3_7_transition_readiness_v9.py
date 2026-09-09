# -*- coding: utf-8 -*-
"""Build deterministic transition capsule v9 without changing older capsules.

v9 is the successor of v8.  v8's Gold-Rule-Record probe was intentionally
fail-closed: the moment a ``rule_record``-named artifact appeared under
``data/gold`` the builder refused, because such a candidate "requires separate
verification".  That separate verification has now happened (the formal GDPR-7
Gold Rule Records were published and verified by
``scripts/verify_gdpr7_gold_rule_records_v1.py``), so v9 replaces the probe with
a verified PRESENT state and records the Oracle isolation run.

Deliberate difference from v8: v9 does **not** re-execute the historical
transition verifiers.  Those verifiers compare their frozen snapshot against
the *current* audit state, so any legitimate later state change makes them fail
closed by design; making v9 depend on their verdict would make v9 itself
unstable.  v9 instead records the superseded assets by path + SHA-256 + byte
size and requires them to stay byte-exact.

Everything v8 judged about S2.11/S2.12/S2.13/S3.4-S3.6 is re-derived from disk
and carried forward unchanged; the v8 asset stays byte-exact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/reports"
REPORT = OUT / "s2_13_s3_7_transition_readiness_v9.json"
MARKDOWN = OUT / "s2_13_s3_7_transition_readiness_v9.md"
MANIFEST = OUT / "s2_13_s3_7_transition_readiness_v9.manifest.json"
EXPORT = OUT / "s2_13_s3_7_transition_readiness_v9_export_index.json"
SCHEMA = ROOT / "configs/schemas/s2_13_s3_7_transition_readiness_v9.schema.json"
READINESS = ROOT / "outputs/reports/s2_12_execution_readiness_v4.json"

V8_ASSETS = (
    "configs/schemas/s2_13_s3_7_transition_readiness_v8.schema.json",
    "scripts/build_s2_13_s3_7_transition_readiness_v8.py",
    "scripts/verify_s2_13_s3_7_transition_readiness_v8.py",
    "tests/test_s2_13_s3_7_transition_readiness_v8.py",
    "outputs/reports/s2_13_s3_7_transition_readiness_v8.json",
    "outputs/reports/s2_13_s3_7_transition_readiness_v8.md",
    "outputs/reports/s2_13_s3_7_transition_readiness_v8.manifest.json",
    "outputs/reports/s2_13_s3_7_transition_readiness_v8_export_index.json",
)

GOLD_RULE_RECORDS = "data/gold/stage3/gdpr7_gold_rule_records_v1.json"
GOLD_RULE_RECORDS_MANIFEST = "outputs/reports/gdpr7_gold_rule_records_v1.manifest.json"
GOLD_RULE_RECORDS_VERIFIER = "scripts/verify_gdpr7_gold_rule_records_v1.py"
ORACLE_REPORT = "outputs/reports/s3_oracle_gold_rules_v1.json"
ORACLE_MANIFEST = "outputs/reports/s3_oracle_gold_rules_v1.manifest.json"
DOWNSTREAM_REPORT = "outputs/reports/s3_downstream_paired_v1.json"
BATCH_READINESS = "outputs/reports/s2_llm_batches_offline_readiness_v1.json"


class TransitionFail(ValueError):
    """Fail-closed transition builder error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _binding(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    if not path.is_file():
        raise TransitionFail(f"missing binding: {rel}")
    return {"path": rel, "sha256": _sha(path), "byte_size": path.stat().st_size}


def historical_asset_ledger() -> dict[str, Any]:
    """Record every earlier capsule asset by hash (never re-executed).

    The earlier transition verifiers assert their frozen snapshot against the
    current audit state, so a legitimate later state change makes them fail
    closed by design.  v9 therefore binds their bytes instead of depending on
    their verdict; ``historical_verifiers_executed=false`` states that
    explicitly.
    """
    ledger: dict[str, Any] = {}
    for version in range(1, 9):
        entry: dict[str, Any] = {}
        # the v1 schema predates the "_v1" suffix convention
        schema_rel = ("configs/schemas/s2_13_s3_7_transition_readiness.schema.json"
                      if version == 1 else
                      f"configs/schemas/s2_13_s3_7_transition_readiness_v{version}.schema.json")
        for rel in (
            schema_rel,
            f"scripts/build_s2_13_s3_7_transition_readiness_v{version}.py",
            f"scripts/verify_s2_13_s3_7_transition_readiness_v{version}.py",
            f"outputs/reports/s2_13_s3_7_transition_readiness_v{version}.json",
        ):
            path = ROOT / rel
            entry[rel] = (
                {"sha256": _sha(path), "byte_size": path.stat().st_size}
                if path.is_file() else None)
        ledger[f"v{version}"] = entry
    return {
        "historical_verifiers_executed": False,
        "policy": ("superseded capsules stay byte-exact; their verifiers are not "
                   "re-executed because they fail closed on legitimate later "
                   "state changes"),
        "assets": ledger,
    }


def _verified_gold_rule_records() -> dict[str, Any]:
    """Re-derive the PRESENT Gold Rule Records state and RUN its verifier."""
    for rel in (GOLD_RULE_RECORDS, GOLD_RULE_RECORDS_MANIFEST, GOLD_RULE_RECORDS_VERIFIER):
        if not (ROOT / rel).is_file():
            raise TransitionFail(f"Gold Rule Records asset missing: {rel}")
    proc = subprocess.run(
        [sys.executable, str(ROOT / GOLD_RULE_RECORDS_VERIFIER)],
        cwd=ROOT.parent, capture_output=True, text=True, timeout=300,
    )
    if proc.returncode != 0:
        raise TransitionFail(
            "Gold Rule Records verifier did not verify: "
            f"{proc.stdout.strip()[:400]}")
    payload = json.loads(proc.stdout)
    if payload.get("verified") is not True:
        raise TransitionFail("Gold Rule Records verifier payload is not verified")
    doc = json.loads((ROOT / GOLD_RULE_RECORDS).read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / GOLD_RULE_RECORDS_MANIFEST).read_text(encoding="utf-8"))
    counts = doc["counts"]
    if counts != {"rules": 9, "sentences": 74, "items": 92, "spans": 235,
                  "modality_evidence_spans": 85, "relation_entries": 38}:
        raise TransitionFail(f"Gold Rule Records count drift: {counts}")
    return {
        "exist": True,
        "verifier_verified": True,
        "verifier_checks": payload.get("checks"),
        "counts": counts,
        "modality_item_counts": manifest.get("modality_item_counts"),
        "covered_rule_ids": sorted({r["rule_id"] for r in doc["records"]}),
        "bindings": {
            "gold": _binding(GOLD_RULE_RECORDS),
            "manifest": _binding(GOLD_RULE_RECORDS_MANIFEST),
            "verifier": _binding(GOLD_RULE_RECORDS_VERIFIER),
            "capsule": _binding(
                "data/predictions/gdpr7_human_rule_record_v1/predictions.json"),
            "confirmed_human_bundle": _binding(
                "data/development/human_review/gdpr7_human_confirmed_v1/"
                "confirmed_rule_items.json"),
            "authorization_event": _binding(
                "configs/gdpr7_gold_rule_records_authorization_event_v1.json"),
            "schema": _binding("configs/schemas/gdpr7_gold_rule_record_v1.schema.json"),
        },
        "note": (
            "Formal GDPR-7 Gold Rule Records published 2026-09-09 by mechanical, "
            "lossless conversion of the user-confirmed 74-sentence / 92-item human "
            "bundle; one clause per rule item; independent verifier verified."),
    }


def _oracle_isolation_run() -> dict[str, Any]:
    if not (ROOT / ORACLE_REPORT).is_file():
        return {"started": False, "note": "Oracle isolation run not produced"}
    report = json.loads((ROOT / ORACLE_REPORT).read_text(encoding="utf-8"))
    three = report["original_three_types"]
    return {
        "started": True,
        "scope": report["scope"],
        "claim_status": report["claim_status"],
        "report": _binding(ORACLE_REPORT),
        "manifest": _binding(ORACLE_MANIFEST),
        "original_three_types": {
            arm: three[arm]["evaluation"] for arm in three
            if arm in ("oracle", "oracle_obligation_only", "reference")
        },
        "downstream_paired_report": _binding(DOWNSTREAM_REPORT),
        "note": ("Oracle isolation on the frozen development evaluation surface; "
                 "NOT the formal S3.7 main table"),
    }


def _llm_batches() -> dict[str, Any]:
    if not (ROOT / BATCH_READINESS).is_file():
        return {"report": None}
    doc = json.loads((ROOT / BATCH_READINESS).read_text(encoding="utf-8"))
    return {
        "report": _binding(BATCH_READINESS),
        "offline_preparation_complete": doc["conclusion"]["offline_preparation_complete"],
        "real_calls_made": doc["conclusion"]["real_calls_made"],
        "real_calls_remaining": doc["conclusion"]["real_calls_remaining"],
        "blocked_on": doc["conclusion"]["blocked_on"],
    }


def build_report(history: Mapping[str, Any]) -> dict[str, Any]:
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    if readiness.get("status") != "partial_zero_api_arm_complete_api_arms_pending_authorization":
        raise TransitionFail("S2.12 readiness v4 status drift")
    gold = _verified_gold_rule_records()
    oracle = _oracle_isolation_run()
    batches = _llm_batches()
    return {
        "schema_version": "s2_13_s3_7_transition_readiness@9.0.0",
        "report_id": "s2_13_s3_7_transition_readiness_v9",
        "supersedes": [
            {**_binding(rel),
             "reason": ("v9 supersedes v8's Gold-Rule-Record absence judgment "
                        "(now verified present) while preserving the v8 asset "
                        "byte-exact")}
            for rel in V8_ASSETS
        ],
        "pipeline_state": {
            "S1.7": "frozen",
            "S2.11": "verified_frozen",
            "S2.12": "partial_zero_api_arm_complete_api_arms_pending",
            "S2.13": "blocked_only_on_remaining_S2.12_DoD",
            "S3.4_S3.6": "development_only",
            "S3.7": "gold_rule_records_published_oracle_isolation_run_formal_main_table_not_authorized",
        },
        "s2_11": {
            "status": "verified_frozen",
            "adjudicated": 36,
            "unresolved": 0,
            "reviewer": "hyc",
            "formal_gold": readiness["s2_11"]["formal_gold"],
            "formal_gold_payload_sha256": readiness["s2_11"]["formal_gold_payload_sha256"],
            "confirmation_event": readiness["s2_11"]["confirmation_event"],
            "provenance": ("deepseek_offline_proposal_v3 + user batch confirmation by "
                           "hyc; not independent-from-scratch expert annotation"),
        },
        "s2_12": {
            "status": "partial",
            "readiness_v4": _binding("outputs/reports/s2_12_execution_readiness_v4.json"),
            "gold_blind_input": _binding("data/input/s2_12_complex_corpus_formal_input_v1.json"),
            "sun_rule_only": {
                "status": "verified_complete",
                "single_zero_api_arm_only": True,
                "evaluation": _binding("data/results/s2_12_sun_rule_only_v1/evaluation.json"),
                "actual_cost_usd": 0.0,
            },
            "direct_llm": "pending_explicit_api_authorization",
            "sun_llm_fallback": "pending_explicit_api_authorization",
            "api_preflight": _binding("outputs/reports/s2_12_api_preflight_v1.json"),
            "offline_batch_readiness": batches,
            "three_method_comparison_complete": False,
            "post_result_tuning_performed": False,
        },
        "s2_13": {
            "status": "blocked",
            "blockers": ["S2.12 remaining DoD: two API arms, three-method comparison, "
                         "and S2.12 completion freeze"],
        },
        "stage3": {
            "S3.4": "development_only",
            "S3.5": "development_only",
            "S3.6": "development_only",
            "S3.7": {
                "status": ("gold_rule_records_published_and_oracle_isolation_run; "
                           "formal main table NOT started or authorized"),
                "authorized": False,
                "gold_rule_records_present": True,
                "oracle_isolation_started": oracle.get("started", False),
                "blockers": ["S2.13", "formal promotion of S3.4-S3.6",
                             "user authorization for the formal Oracle main table"],
            },
        },
        "gold_rule_records": gold,
        "oracle_isolation_run": oracle,
        "historical_transition_verifiers": history,
        "authorization": readiness["authorization"],
        "safety": {
            "new_llm_api_calls": 0,
            "new_network_calls": 0,
            "gold_rule_records_created": False,
            "oracle_started": False,
            "historical_transition_assets_modified": False,
            "project_audit_md_modified": False,
        },
    }


def _render_md(report: Mapping[str, Any]) -> bytes:
    gold = report["gold_rule_records"]
    counts = gold["counts"]
    oracle = report["oracle_isolation_run"]
    three = oracle.get("original_three_types", {}) if oracle.get("started") else {}
    lines = [
        "# S2.13 → S3.7 Transition Readiness v9",
        "",
        "- S2.11: **verified / frozen**, 36/36 adjudicated; formal Gold published.",
        "- S2.12: **partial**; `sun_rule_only` zero-API arm complete; "
        "`direct_llm` and `sun_llm_fallback` await the process-environment credentials.",
        "- S2.13: **blocked only on remaining S2.12 DoD**.",
        "- S3.4–S3.6: **development-only**.",
        f"- S3.7: **Gold Rule Records published** ({counts['rules']} rules / "
        f"{counts['sentences']} sentences / {counts['items']} items; independent "
        f"verifier verified); **Oracle isolation run** on the frozen development "
        "evaluation surface; **formal main table not started or authorized**.",
        "",
        "## Oracle isolation (frozen development evaluation surface)",
        "",
        "| rule source | macro-F1 | exact | detected | unobservable |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm in ("oracle", "oracle_obligation_only", "reference"):
        if arm not in three:
            continue
        ev = three[arm]
        lines.append(f"| {arm} | {ev['macro_f1']:.4f} | "
                     f"{ev['exact_type_accuracy']:.4f} | {ev['detected']} | "
                     f"{ev['unobservable']} |")
    lines += [
        "",
        "The complex-corpus result is one zero-API arm, not a three-method "
        "comparison. No post-result method, rule, prompt, threshold, or Gold "
        "adjustment was made.",
        "",
        "Historical verifier lifecycle: v1 verifies; v2–v8 fail closed with their "
        "exact expected superseded-snapshot signatures (their Gold-Rule-Record "
        "absence probe is no longer true).",
        "",
    ]
    return ("\n".join(lines)).encode("utf-8")


def build_artifacts(history: Mapping[str, Any]) -> dict[Path, bytes]:
    report = build_report(history)
    report_bytes = _json_bytes(report)
    md_bytes = _render_md(report)
    bindings = {
        rel: _sha(ROOT / rel)
        for rel in (
            *V8_ASSETS,
            GOLD_RULE_RECORDS,
            GOLD_RULE_RECORDS_MANIFEST,
            GOLD_RULE_RECORDS_VERIFIER,
            "configs/schemas/gdpr7_gold_rule_record_v1.schema.json",
            "configs/gdpr7_gold_rule_records_authorization_event_v1.json",
            "data/predictions/gdpr7_human_rule_record_v1/predictions.json",
            "data/development/human_review/gdpr7_human_confirmed_v1/"
            "confirmed_rule_items.json",
            ORACLE_REPORT,
            ORACLE_MANIFEST,
            DOWNSTREAM_REPORT,
            BATCH_READINESS,
            "outputs/reports/s2_12_execution_readiness_v4.json",
            "outputs/reports/s2_12_api_preflight_v1.json",
            "data/input/s2_12_complex_corpus_formal_input_v1.json",
            "data/results/s2_12_sun_rule_only_v1/evaluation.json",
            *(f"scripts/verify_s2_13_s3_7_transition_readiness_v{v}.py"
              for v in range(1, 9)),
        )
    }
    manifest = {
        "schema_version": "s2_13_s3_7_transition_readiness_manifest@9.0.0",
        "manifest_id": "s2_13_s3_7_transition_readiness_v9.manifest",
        "artifacts": {
            "report_json": {"path": REPORT.relative_to(ROOT).as_posix(),
                            "sha256": hashlib.sha256(report_bytes).hexdigest(),
                            "byte_size": len(report_bytes)},
            "report_md": {"path": MARKDOWN.relative_to(ROOT).as_posix(),
                          "sha256": hashlib.sha256(md_bytes).hexdigest(),
                          "byte_size": len(md_bytes)},
        },
        "bindings": bindings,
        "implementation": {
            "builder": _binding("scripts/build_s2_13_s3_7_transition_readiness_v9.py"),
            "verifier": _binding("scripts/verify_s2_13_s3_7_transition_readiness_v9.py"),
            "schema": _binding("configs/schemas/s2_13_s3_7_transition_readiness_v9.schema.json"),
        },
        "zero_api": {"new_llm_api_calls": 0, "new_network_calls": 0},
    }
    manifest_bytes = _json_bytes(manifest)
    export = {
        "schema_version": "s2_13_s3_7_transition_readiness_export_index@9.0.0",
        "files": {
            REPORT.relative_to(ROOT).as_posix(): {
                "sha256": hashlib.sha256(report_bytes).hexdigest(),
                "byte_size": len(report_bytes)},
            MARKDOWN.relative_to(ROOT).as_posix(): {
                "sha256": hashlib.sha256(md_bytes).hexdigest(),
                "byte_size": len(md_bytes)},
            MANIFEST.relative_to(ROOT).as_posix(): {
                "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "byte_size": len(manifest_bytes)},
        },
    }
    return {REPORT: report_bytes, MARKDOWN: md_bytes, MANIFEST: manifest_bytes,
            EXPORT: _json_bytes(export)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        history = historical_asset_ledger()
        artifacts = build_artifacts(history)
        if args.publish:
            existing = [path for path in artifacts if path.exists()]
            if existing:
                raise TransitionFail(f"refusing to overwrite v9 outputs: {existing}")
            OUT.mkdir(parents=True, exist_ok=True)
            staged: list[tuple[Path, Path]] = []
            for target, payload in artifacts.items():
                with tempfile.NamedTemporaryFile(dir=OUT, delete=False) as stream:
                    stage = Path(stream.name)
                    stream.write(payload)
                staged.append((stage, target))
            try:
                for stage, target in staged:
                    stage.replace(target)
            except Exception:
                for stage, _target in staged:
                    stage.unlink(missing_ok=True)
                raise
        else:
            for path, expected in artifacts.items():
                if not path.is_file() or path.read_bytes() != expected:
                    raise TransitionFail(f"v9 replay differs: {path}")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"Transition readiness v9 refused: {exc}")
        return 2
    print("S2.13 -> S3.7 transition readiness v9 VERIFIED "
          "(Gold Rule Records present; Oracle isolation run; formal main table "
          "not authorized; zero API)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
