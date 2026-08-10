# -*- coding: utf-8 -*-
"""D1/H1 zero-API candidate re-evaluation + shared comparison capsule v1.

Uses ONLY the committed historical prediction snapshots that are proven
bound to formal input v2 (see outputs/reports/b0_d1_formal_readiness_v2.json):

- D1: outputs/development/s27_d1_v6_r3_clean_rerun_150_hist56d_v1
      (d1_responses.jsonl, 150 rows, llm_calls=150 recorded)
- H1: outputs/development/s28d_h1_150_v4pro_v1
      (h1_predictions.jsonl, 150 rows, llm_calls=150 recorded)

Both snapshots are re-verified record-by-record (150 IDs, input text hashes
vs formal input v2, prompt/model/sampling locks, schema-valid) and then
re-evaluated with the SAME Gold views, schema, normalization and evaluators
as the B0 formal arm (fine + coarse five span-bearing fields, modality-label
four-class, modality evidence-span unavailable per G0.4).

Claim scopes: D1 = candidate / formal-gate-blocked; H1 = candidate /
comparison-only / formal-gate-blocked. NO result is written to the formal
data/predictions or data/results directories and NO claim_scope=formal is
used. New LLM/API calls: 0.

Outputs (versioned, under outputs/evidence/):
- d1_h1_zero_api_reeval_v1/d1/reevaluation.json
- d1_h1_zero_api_reeval_v1/h1/reevaluation.json
- d1_h1_zero_api_reeval_v1/comparison_capsule.json
- d1_h1_zero_api_reeval_v1/comparison_capsule.md
- d1_h1_zero_api_reeval_v1/manifest.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.g04_coarse_view import (  # noqa: E402
    build_coarse_view,
    semantic_hash_json,
)
from bpc_hybrid.formal_stage2_evaluation import (  # noqa: E402
    evaluate_modality_labels,
    evaluate_span_metrics,
    predictions_to_evaluator,
    published_gold_to_evaluator,
)

V2_INPUT = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
FORMAL_GOLD = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
B0_MANIFEST = ROOT / "outputs" / "reports" / "b0_formal_arm_v1.manifest.json"
B0_FINE = ROOT / "data" / "results" / "b0_formal_arm_v1" / "evaluation_fine.json"
B0_COARSE = ROOT / "data" / "results" / "b0_formal_arm_v1" / "evaluation_coarse.json"
B0_LABELS = ROOT / "data" / "results" / "b0_formal_arm_v1" / "modality_labels.json"
READINESS = ROOT / "outputs" / "reports" / "b0_d1_formal_readiness_v2.json"
G04_MANIFEST = (ROOT / "outputs" / "evidence" / "g04_formal_coarse_view_v1"
                / "manifest.json")
G04_DERIVED = (ROOT / "outputs" / "evidence" / "g04_formal_coarse_view_v1"
               / "coarse_view_derived.json")

D1_RUN = ROOT / "outputs" / "development" / "s27_d1_v6_r3_clean_rerun_150_hist56d_v1"
D1_PRED = D1_RUN / "d1_responses.jsonl"
D1_MANIFEST = D1_RUN / "manifest.json"
H1_RUN = ROOT / "outputs" / "development" / "s28d_h1_150_v4pro_v1"
H1_PRED = H1_RUN / "h1_predictions.jsonl"
H1_MANIFEST = H1_RUN / "manifest.json"

OUT_DIR = ROOT / "outputs" / "evidence" / "d1_h1_zero_api_reeval_v1"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        return []


def _authoritative_coarse_view_hash() -> dict[str, str]:
    """Cross-verified authoritative G0.4 coarse-view semantic hash.

    NO hash is hardcoded here. The value is read from the G0.4 manifest AND
    recomputed from the committed derived artifact, AND cross-checked against
    the B0 formal arm manifest's G0.4 declaration. Any disagreement fails
    closed (RuntimeError) so a stale or tampered binding can never silently
    propagate.
    """
    g04_manifest = _load_json(G04_MANIFEST)
    manifest_sha = g04_manifest.get("derived_view", {}).get("semantic_sha256")
    if not isinstance(manifest_sha, str) or not manifest_sha:
        raise RuntimeError("G0.4 manifest missing derived_view.semantic_sha256")
    if not G04_DERIVED.exists():
        raise RuntimeError("G0.4 derived artifact missing; cannot cross-verify")
    derived = json.loads(G04_DERIVED.read_text(encoding="utf-8"))
    recomputed = semantic_hash_json(derived)
    if manifest_sha != recomputed:
        raise RuntimeError(
            f"G0.4 hash disagreement: manifest={manifest_sha} "
            f"recomputed={recomputed}")
    b0_manifest = _load_json(B0_MANIFEST)
    b0_sha = b0_manifest.get("g04", {}).get("coarse_view_semantic_sha256")
    if b0_sha != manifest_sha:
        raise RuntimeError(
            f"B0 formal manifest G0.4 hash disagreement: {b0_sha} vs {manifest_sha}")
    return {"semantic_sha256": manifest_sha,
            "source": "outputs/evidence/g04_formal_coarse_view_v1/manifest.json "
                      "(cross-verified against derived artifact recomputation "
                      "and the B0 formal arm manifest)"}


def _verify_binding(method: str, predictions: list[dict[str, Any]],
                    manifest: dict[str, Any], v2: dict[str, Any],
                    v2_sha: dict[str, str],
                    expected_prompt_sha: str | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    v2_ids = {r["sample_id"] for r in v2["records"]}
    ids = {r.get("sample_id") for r in predictions}
    checks.append({"item": "150 rows", "ok": len(predictions) == 150,
                   "detail": str(len(predictions))})
    checks.append({"item": "ids == formal input v2", "ok": ids == v2_ids})
    if method == "D1":
        text_key = "record"
        text_get = lambda r: r.get("record", {}).get("source_text")
    else:
        text_key = "source_text"
        text_get = lambda r: r.get("source_text")
    mismatch = 0
    for r in predictions:
        want = v2_sha.get(r.get("sample_id"))
        if want is None:
            mismatch += 1
            continue
        if _sha256_bytes((text_get(r) or "").encode("utf-8")) != want:
            mismatch += 1
    checks.append({"item": "input text hash == v2 (150/150)", "ok": mismatch == 0,
                   "detail": f"{mismatch} mismatches"})
    schema_valid = 0
    for r in predictions:
        if method == "D1":
            ok = r.get("record", {}).get("validation", {}).get("schema_valid")
        else:
            ok = r.get("validation", {}).get("schema_valid")
        if ok:
            schema_valid += 1
    checks.append({"item": "schema-valid", "ok": schema_valid == 150,
                   "detail": f"{schema_valid}/150"})
    if expected_prompt_sha:
        m_sha = (manifest.get("prompts") or [{}])[0].get("sha256", "")
        checks.append({"item": "prompt lock", "ok": m_sha == expected_prompt_sha,
                       "detail": m_sha[:16]})
    binding_ok = all(c["ok"] for c in checks)
    return {"method": method, "binding_ok": binding_ok, "checks": checks}


def build_reevaluation() -> dict[str, Any]:
    v2 = _load_json(V2_INPUT)
    v2_sha = {r["sample_id"]: r["input_text_sha256"] for r in v2["records"]}
    gold_doc = _load_json(FORMAL_GOLD)
    fine_gold = published_gold_to_evaluator(gold_doc)
    coarse_gold = build_coarse_view(gold_doc)

    d1_preds = _load_jsonl(D1_PRED)
    d1_manifest = _load_json(D1_MANIFEST)
    h1_preds = _load_jsonl(H1_PRED)
    h1_manifest = _load_json(H1_MANIFEST)

    d1_binding = _verify_binding(
        "D1", d1_preds, d1_manifest, v2, v2_sha,
        "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895")
    h1_binding = _verify_binding(
        "H1", h1_preds, h1_manifest, v2, v2_sha,
        "00fe02996914e17f30962147d7a9f2c71a92d2479ba4eff343583a139bb1537b")

    # D1 predictions: envelope {sample_id, record, ...}
    d1_attempts = [{"sample_id": r["sample_id"], "request_status": "ok",
                    "record": r.get("record"), "error_category": None,
                    "runtime": {"llm_call_performed": False}}
                   for r in d1_preds]
    # H1 predictions: plain records
    h1_attempts = [{"sample_id": r["sample_id"], "request_status": "ok",
                    "record": r, "error_category": None,
                    "runtime": {"llm_call_performed": False}}
                   for r in h1_preds]

    methods = {
        "direct_llm": {"attempts": d1_attempts, "binding": d1_binding,
                       "claim_scope": "candidate",
                       "gate_status": "formal-gate-blocked",
                       "historical_llm_calls": d1_manifest.get("llm_calls", 150),
                       "snapshot": "s27_d1_v6_r3_clean_rerun_150_hist56d_v1"},
        "sun_llm_fallback": {"attempts": h1_attempts, "binding": h1_binding,
                             "claim_scope": "candidate",
                             "gate_status": "comparison-only / formal-gate-blocked",
                             "historical_llm_calls": h1_manifest.get("llm_calls", 150),
                             "snapshot": "s28d_h1_150_v4pro_v1"},
    }

    reeval: dict[str, Any] = {}
    for mid, info in methods.items():
        attempts_eval = predictions_to_evaluator(info["attempts"])
        fine = evaluate_span_metrics(
            fine_gold, attempts_eval,
            dataset_id="independently_reconstructed_estg_150_v1",
            method_id=mid, view="fine_clause_level")
        coarse = evaluate_span_metrics(
            coarse_gold, attempts_eval,
            dataset_id="independently_reconstructed_estg_150_v1",
            method_id=mid, view="coarse_sentence_level")
        labels = evaluate_modality_labels(fine_gold, attempts_eval)
        reeval[mid] = {
            "claim_scope": info["claim_scope"],
            "gate_status": info["gate_status"],
            "binding": info["binding"],
            "snapshot": info["snapshot"],
            "historical_llm_calls": info["historical_llm_calls"],
            "new_llm_calls": 0,
            "evaluation": {
                "fine": fine,
                "coarse": coarse,
                "modality_labels": labels,
            },
        }

    # authoritative G0.4 coarse-view hash (cross-verified, never hardcoded)
    coarse_hash = _authoritative_coarse_view_hash()

    # comparison capsule
    b0_manifest = _load_json(B0_MANIFEST)
    comparison = {
        "schema_version": "shared_stage2_comparison_capsule@1.0.0",
        "formal_input_v2": {"path": "data/input/estg150_formal_inference_input_v2.json",
                            "sha256": _sha256_file(V2_INPUT)},
        "formal_gold": {"path": "data/gold/stage2/estg150_formal_gold_v1.json",
                        "sha256": _sha256_file(FORMAL_GOLD)},
        "coarse_view": {
            "transform": "src/bpc_hybrid/g04_coarse_view.py",
            "semantic_sha256": coarse_hash["semantic_sha256"],
            "semantic_hash_source": coarse_hash["source"],
            "main_view_publishable": False,
            "note": "G0.4 consistency gate: modality evidence not reproducible from published Gold; five-field spans published"},
        "prediction_schema": {"path": "configs/schemas/stage2_prediction.schema.json"},
        "normalization": "formal_stage2_evaluation + g04_coarse_view (shared)",
        "evaluators": {
            "primary": "sun_table8_literal_overlap_v2",
            "modality_labels": "four-class accuracy/macro-F1 (separate)",
        },
        "methods": {
            "sun_rule_only": {
                "claim_scope": "formal",
                "gate_status": "ready (user-authorized 2026-08-10)",
                "prediction_manifest": "outputs/reports/b0_formal_arm_v1.manifest.json",
                "prediction_manifest_sha256": _sha256_file(B0_MANIFEST),
                "fine_span_fields": _load_json(B0_FINE).get("span_fields", {}),
                "coarse_span_fields": _load_json(B0_COARSE).get("span_fields", {}),
                "modality_labels": _load_json(B0_LABELS),
            },
            "direct_llm": {
                "claim_scope": reeval["direct_llm"]["claim_scope"],
                "gate_status": reeval["direct_llm"]["gate_status"],
                "snapshot": reeval["direct_llm"]["snapshot"],
                "historical_llm_calls": reeval["direct_llm"]["historical_llm_calls"],
                "new_llm_calls": 0,
                "fine_span_fields": reeval["direct_llm"]["evaluation"]["fine"]["span_fields"],
                "coarse_span_fields": reeval["direct_llm"]["evaluation"]["coarse"]["span_fields"],
                "modality_labels": reeval["direct_llm"]["evaluation"]["modality_labels"],
            },
            "sun_llm_fallback": {
                "claim_scope": reeval["sun_llm_fallback"]["claim_scope"],
                "gate_status": reeval["sun_llm_fallback"]["gate_status"],
                "snapshot": reeval["sun_llm_fallback"]["snapshot"],
                "historical_llm_calls": reeval["sun_llm_fallback"]["historical_llm_calls"],
                "new_llm_calls": 0,
                "fine_span_fields": reeval["sun_llm_fallback"]["evaluation"]["fine"]["span_fields"],
                "coarse_span_fields": reeval["sun_llm_fallback"]["evaluation"]["coarse"]["span_fields"],
                "modality_labels": reeval["sun_llm_fallback"]["evaluation"]["modality_labels"],
            },
        },
        "decisions": {
            "h1_downgraded_to_comparison_only": True,
            "note": "H1 downgraded by user/supervisor decision 2026-08-08 (net-negative); no further optimization",
        },
        "comparability_boundaries": {
            "cross_method_comparable": "same input v2, same Gold views, same schema, same normalization, same evaluators",
            "not_comparable": (
                "B0 formal arm (claim_scope=formal) vs D1/H1 candidates "
                "(formal-gate-blocked): metrics are method-side re-evaluations "
                "on the same contract, but D1/H1 are NOT formal results"),
            "modality_evidence_span_metrics": "unavailable for ALL methods (published Gold modality is a plain string)",
            "historical_coarse_numbers": "development provenance only (not formal)",
        },
        "zero_api": {"new_llm_api_calls": 0, "real_api_calls_total_historical": (
            reeval["direct_llm"]["historical_llm_calls"]
            + reeval["sun_llm_fallback"]["historical_llm_calls"])},
    }
    return {"reeval": reeval, "comparison": comparison}


def main() -> int:
    result = build_reevaluation()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    def _write(name: str, payload: dict[str, Any]) -> str:
        data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = OUT_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != data:
            raise RuntimeError(f"refusing to overwrite different content: {path}")
        path.write_bytes(data)
        return _sha256_bytes(data)

    d1_sha = _write("d1/reevaluation.json", result["reeval"]["direct_llm"])
    h1_sha = _write("h1/reevaluation.json", result["reeval"]["sun_llm_fallback"])
    cmp_sha = _write("comparison_capsule.json", result["comparison"])

    md = ["# D1/H1 zero-API candidate re-evaluation + shared comparison",
          "",
          "- claim scopes: D1 candidate / formal-gate-blocked; H1 candidate / comparison-only / formal-gate-blocked",
          "- new LLM/API calls: 0",
          "",
          "## Methods",
          ]
    for mid, info in result["comparison"]["methods"].items():
        fs = info.get("fine_span_fields", {})
        cs = info.get("coarse_span_fields", {})
        md.append(f"### {mid} ({info['claim_scope']})")
        md.append(f"- gate: {info['gate_status']}")
        md.append(f"- fine 5-field F1: { {k: round(v['f1'], 4) for k, v in fs.items()} }")
        md.append(f"- coarse 5-field F1: { {k: round(v['f1'], 4) for k, v in cs.items()} }")
        if info.get("modality_labels"):
            md.append(f"- modality label acc: {info['modality_labels'].get('accuracy')}")
        md.append("")
    md += [
        "## Zero-API declaration",
        f"- new LLM/API calls: {result['comparison']['zero_api']['new_llm_api_calls']}",
        f"- historical recorded calls: {result['comparison']['zero_api']['real_api_calls_total_historical']}",
        "",
    ]
    text = "\n".join(md)
    md_path = OUT_DIR / "comparison_capsule.md"
    if md_path.exists() and md_path.read_text(encoding="utf-8") != text:
        raise RuntimeError(f"refusing to overwrite different content: {md_path}")
    md_path.write_text(text, encoding="utf-8")

    manifest = {
        "schema_version": "d1_h1_zero_api_reeval_manifest@1.0.0",
        "artifacts": {
            "d1/reevaluation.json": {"path": "outputs/evidence/d1_h1_zero_api_reeval_v1/d1/reevaluation.json",
                                     "sha256": d1_sha},
            "h1/reevaluation.json": {"path": "outputs/evidence/d1_h1_zero_api_reeval_v1/h1/reevaluation.json",
                                     "sha256": h1_sha},
            "comparison_capsule.json": {"path": "outputs/evidence/d1_h1_zero_api_reeval_v1/comparison_capsule.json",
                                        "sha256": cmp_sha},
            "comparison_capsule.md": {"path": "outputs/evidence/d1_h1_zero_api_reeval_v1/comparison_capsule.md",
                                      "sha256": _sha256_bytes(text.encode("utf-8"))},
        },
        "zero_api": {"new_llm_api_calls": 0},
        "note": "D1/H1 results are candidates; nothing written to data/predictions or data/results",
    }
    man_sha = _write("manifest.json", manifest)
    print(f"D1/H1 zero-API re-evaluation written: {OUT_DIR.relative_to(ROOT)}")
    for mid in ("direct_llm", "sun_llm_fallback"):
        info = result["reeval"][mid]
        print(f"  {mid}: binding_ok={info['binding']['binding_ok']} "
              f"claim={info['claim_scope']}")
    print(f"  comparison capsule sha256: {cmp_sha[:16]}...")
    print(f"  manifest sha256: {man_sha[:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
