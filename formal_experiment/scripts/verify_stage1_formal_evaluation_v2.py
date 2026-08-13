# -*- coding: utf-8 -*-
"""Fail-closed verifier for the corrected Stage 1 formal v2 assets.

Recomputes everything from disk:
  1. authoritative predictions (data/predictions/stage1_formal_v1/) are
     byte-identical to the locked development predictions
  2. numeric body (data/results/stage1_formal_v1/) equals the v1 evaluation
     report numbers (report + per-process + deltas), byte- and
     canonical-identical; no claim metadata inside the numeric body
  3. v2 report claim is target-aware (strict_test_blind=false,
     held_out_generalization_claim_allowed=false,
     target_labels_seen_during_development=true, ...)
  4. v2 report bindings (membership, bpmn, P2 config/impl, Gold, evaluator,
     predictions, audit, claim) match disk
  5. the v2 report references the formal paths (NOT the development paths
     as authoritative)
  6. tamper invariants: changing any binding, reverting the claim to
     test-blind, deleting the overlap audit, or pointing the formal files
     back at the development paths must fail

Exit 0 iff everything verifies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

V2_REPORT = ROOT / "outputs" / "reports" / "stage1_formal_evaluation_v2.json"
AUTH_PRED = (ROOT / "data" / "predictions" / "stage1_formal_v1"
             / "formal_predictions_v1.json")
AUTH_RESULTS = (ROOT / "data" / "results" / "stage1_formal_v1"
                / "stage1_formal_evaluation_v1.json")
SRC_PRED = (ROOT / "outputs" / "development" / "stage1_predictions"
            / "formal_predictions_v1.json")
SRC_EVAL = (ROOT / "outputs" / "development" / "stage1_formal_capsule_v1"
            / "evaluation.json")
AUDIT = ROOT / "outputs" / "reports" / "s1_p2_target_overlap_audit_v1.json"
CLAIM = ROOT / "outputs" / "reports" / "s1_stage1_claim_correction_v2.json"
P2_CONFIG = ROOT / "configs" / "stage1_label_p2_v1.json"
P2_IMPL = ROOT / "src" / "bpc_hybrid" / "stage1_label_semantics_p2.py"
GOLD = (ROOT / "data" / "gold" / "stage1" / "process_records"
        / "stage1_process_gold_v1.json")
GOLD_MANIFEST = ROOT / "data" / "gold" / "stage1" / "manifest.json"
EVAL_CONFIG = ROOT / "configs" / "stage1_evaluator_s16_formal.json"
MEMBERSHIP = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "0" * 64


def verify() -> dict:
    checks = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    try:
        report = json.loads(V2_REPORT.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        check("v2 report readable", False, str(exc))
        return {"verified": False, "checks": checks}
    check("v2 report exists", V2_REPORT.exists())
    check("authoritative predictions exist", AUTH_PRED.exists())
    check("authoritative results exist", AUTH_RESULTS.exists())

    # 1. predictions byte-identical
    check("authoritative predictions == locked predictions",
          _sha256(AUTH_PRED) == _sha256(SRC_PRED))

    # 2. numeric body == v1 numbers
    body = json.loads(AUTH_RESULTS.read_text(encoding="utf-8"))
    src_eval = json.loads(SRC_EVAL.read_text(encoding="utf-8"))
    numbers_ok = (body.get("report") == src_eval.get("report")
                  and body.get("per_process_triple_exact_accuracy")
                  == src_eval.get("per_process_triple_exact_accuracy")
                  and body.get("method_deltas_f1")
                  == src_eval.get("method_deltas_f1"))
    check("numeric body equals v1 evaluation numbers", numbers_ok)
    check("numeric body has no claim metadata",
          "claim" not in body and "strict_test_blind" not in body
          and "limitations" not in body)
    # canonical hash of the numeric body
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    canonical_sha = hashlib.sha256(canonical).hexdigest()
    check("numeric body canonical hash matches report",
          report.get("numbers", {}).get("numeric_body_canonical_sha256")
          == canonical_sha)
    check("numeric body sha256 matches report",
          report.get("numbers", {}).get("numeric_body_sha256")
          == _sha256(AUTH_RESULTS))

    # 3. claim target-aware
    claim = report.get("claim", {})
    check("claim: target-aware fields",
          claim.get("strict_test_blind") is False
          and claim.get("developer_blind") is False
          and claim.get("held_out_generalization_claim_allowed") is False
          and claim.get("target_labels_seen_during_development") is True
          and claim.get("runtime_gold_read") is False
          and claim.get("implementation_locked_before_scoring") is True
          and claim.get("post_evaluation_tuning") is False)
    check("claim: evaluation role fixed-GDPR7 descriptive",
          claim.get("evaluation_role")
          == "formal_descriptive_component_evaluation_on_fixed_GDPR7")
    check("claim: accurate phrasing",
          "target-aware" in claim.get("accurate_claim", "")
          and "post-Gold" in claim.get("accurate_claim", ""))

    # 4. bindings match disk
    binds = report.get("bindings", {})
    check("binding: membership",
          binds.get("membership_payload_sha256")
          == json.loads(MEMBERSHIP.read_text(encoding="utf-8"))["membership"][
              "membership_payload_sha256"])
    check("binding: P2 config/impl",
          binds.get("p2_config", {}).get("sha256") == _sha256(P2_CONFIG)
          and binds.get("p2_implementation", {}).get("sha256")
          == _sha256(P2_IMPL))
    check("binding: Gold + gold manifest",
          binds.get("stage1_gold", {}).get("sha256") == _sha256(GOLD)
          and binds.get("gold_manifest", {}).get("sha256")
          == _sha256(GOLD_MANIFEST))
    check("binding: evaluator config",
          binds.get("evaluator_formal_config", {}).get("sha256")
          == _sha256(EVAL_CONFIG))
    check("binding: authoritative predictions",
          binds.get("predictions_authoritative", {}).get("sha256")
          == _sha256(AUTH_PRED) == _sha256(SRC_PRED))
    check("binding: overlap audit + claim correction",
          binds.get("overlap_audit", {}).get("sha256") == _sha256(AUDIT)
          and binds.get("claim_correction", {}).get("sha256")
          == _sha256(CLAIM))
    bpmn_ok = True
    for rel, digest in binds.get("bpmn_sources", {}).items():
        path = ROOT / rel
        if not path.exists() or _sha256(path) != digest:
            bpmn_ok = False
    check("binding: 7 BPMN source hashes", bpmn_ok)

    # 5. formal paths are authoritative (no development-path claims)
    text = json.dumps(report, ensure_ascii=False)
    check("v2 report does not use development path as authoritative",
          "outputs/development/stage1_predictions" not in
          report.get("numbers", {}).get("numeric_body_path", "")
          and "outputs/development" not in
          report.get("bindings", {}).get("predictions_authoritative", {}).get(
              "path", ""))
    check("v1 source referenced only as historical provenance",
          "v1_source" in report.get("numbers", {})
          and "outputs/development/stage1_formal_capsule_v1" in
          report.get("numbers", {}).get("v1_source", ""))

    # 6. metrics invariants
    metrics = report.get("metrics", {})
    check("metrics: P2 micro F1 0.8185328185328185",
          metrics.get("P2", {}).get("semantic_micro", {}).get("f1")
          == 0.8185328185328185
          and metrics.get("P2", {}).get("semantic_micro", {}).get(
              "precision") == 0.8548387096774194
          and metrics.get("P2", {}).get("semantic_micro", {}).get(
              "recall") == 0.7851851851851852
          and metrics.get("P2", {}).get("semantic_micro", {}).get(
              "exact_value_accuracy") == 0.6928104575163399
          and metrics.get("P2", {}).get("triple_exact_accuracy")
          == 0.4222222222222222)
    check("metrics: denominators",
          metrics.get("denominators")
          == {"processes": 7, "activities": 45, "semantic_fields": 135})

    # 7. zero API
    check("zero API", report.get("zero_api", {}).get("new_llm_api_calls") == 0)

    return {"verified": all(c["ok"] for c in checks), "checks": checks,
            "v2_report_sha256": _sha256(V2_REPORT)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        for c in result["checks"]:
            print(("PASS" if c["ok"] else "FAIL"), c["name"], c["detail"])
        print("V2 ASSETS VERIFIED" if result["verified"]
              else "V2 ASSETS NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
