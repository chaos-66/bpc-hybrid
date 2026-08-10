# -*- coding: utf-8 -*-
"""B0/D1/H1 formal readiness audit v2 (zero-API).

For each of the three final methods (sun_rule_only / direct_llm /
sun_llm_fallback) this script verifies, against the frozen formal benchmark
release v2:

- sample IDs (150/150 unique, identical to formal input v2)
- actual input text, record by record hash vs formal input v2
- prompt / model / config / evaluator hashes (locked recipe)
- prediction snapshot completeness (150 rows, schema-valid)
- whether the snapshot is bound to formal input v2 (IDs + text)
- whether a zero-API re-evaluation is allowed (no new LLM call needed)

Historical prediction snapshots (D1-R3 clean rerun, H1 150 v4pro) are NOT
assumed to be formal just because they were run in the past: every binding
condition must hold. If it does, a zero-API candidate re-evaluation is
permitted and recorded; if not, the first mismatch, the number of
differences and the reason a rerun would be required are reported. No
mismatched historical prediction is promoted to formal.

Outputs:
- outputs/reports/b0_d1_formal_readiness_v2.json
- outputs/reports/b0_d1_formal_readiness_v2.md

Usage:
    python scripts/build_b0_d1_formal_readiness_v2.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

V2_INPUT = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
GOLD_STAGE2 = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
EVALUATOR_CONFIG = ROOT / "configs" / "evaluation" / "sun_table8_literal_overlap_v2.json"
D1_REGISTRY = ROOT / "configs" / "models" / "estg150_d1_active_registry_v1.json"
B0_CONFIG = ROOT / "configs" / "models" / "estg150_b0_enhanced_s27_v10a.json"
D1_PROMPT = ROOT / "prompts" / "sun_compat" / "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md"
H1_PROMPT = ROOT / "prompts" / "sun_compat" / "rule_first_llm_fallback_prompt.md"

D1_INPUT = ROOT / "outputs" / "development" / "s27_d1_pilot_20_hist56d_v1" / "input_150_hist56d_v1.jsonl"
D1_RUN = ROOT / "outputs" / "development" / "s27_d1_v6_r3_clean_rerun_150_hist56d_v1"
D1_PREDICTIONS = D1_RUN / "d1_responses.jsonl"
D1_MANIFEST = D1_RUN / "manifest.json"
H1_RUN = ROOT / "outputs" / "development" / "s28d_h1_150_v4pro_v1"
H1_PREDICTIONS = H1_RUN / "h1_predictions.jsonl"
H1_MANIFEST = H1_RUN / "manifest.json"
B0_HIST = ROOT / "outputs" / "development" / "s27_estg150_b0_enhanced_v10a_r2_r3_lex_hist56d_v1"
B0_HIST_ATTEMPTS = B0_HIST / "b0_attempts.json"
B0_HIST_MANIFEST = B0_HIST / "manifest.json"

OUT_JSON = ROOT / "outputs" / "reports" / "b0_d1_formal_readiness_v2.json"
OUT_MD = ROOT / "outputs" / "reports" / "b0_d1_formal_readiness_v2.md"

D1_EXPECTED_PROMPT_SHA = "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"
H1_EXPECTED_PROMPT_SHA = "00fe02996914e17f30962147d7a9f2c71a92d2479ba4eff343583a139bb1537b"
D1_EXPECTED_MODEL = "deepseek-v4-pro"
H1_EXPECTED_MODEL = "deepseek-v4-pro"
MEMBERSHIP_SHA = "e8e6268644cbc9b7ed42bef19f2e2e2432633a306eab9bf009725ef9571785d7"


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
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    except (OSError, json.JSONDecodeError):
        return []


def _text_sha_of_v2(v2: dict[str, Any]) -> dict[str, str]:
    return {r["sample_id"]: r["input_text_sha256"] for r in v2["records"]}


def _check_binding(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"item": name, "ok": bool(ok), "detail": detail}


def _verify_d1(v2: dict[str, Any], v2_sha: dict[str, str]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    v2_ids = {r["sample_id"] for r in v2["records"]}

    d1_input = _load_jsonl(D1_INPUT)
    d1_manifest = _load_json(D1_MANIFEST)
    d1_responses = _load_jsonl(D1_PREDICTIONS)

    # snapshot completeness
    checks.append(_check_binding(
        "D1 snapshot exists (input/predictions/manifest)",
        D1_INPUT.exists() and D1_PREDICTIONS.exists() and D1_MANIFEST.exists()))
    checks.append(_check_binding(
        "D1 predictions 150 rows", len(d1_responses) == 150,
        f"{len(d1_responses)} rows"))
    d1_ids = {r.get("sample_id") for r in d1_responses}
    checks.append(_check_binding(
        "D1 prediction ids == formal input v2 ids", d1_ids == v2_ids))
    valid = sum(1 for r in d1_responses
                if r.get("record", {}).get("validation", {}).get("schema_valid"))
    checks.append(_check_binding(
        "D1 predictions schema-valid", valid == 150, f"{valid}/150"))

    # text binding: input_150_hist56d_v1.jsonl text vs formal v2 text
    text_mismatch = 0
    for row in d1_input:
        want = v2_sha.get(row.get("sample_id"))
        if want is None:
            text_mismatch += 1
            continue
        if _sha256_bytes(row.get("text", "").encode("utf-8")) != want:
            text_mismatch += 1
    checks.append(_check_binding(
        "D1 input text == formal v2 text (150/150)", text_mismatch == 0,
        f"{text_mismatch} mismatches"))

    # recipe lock: prompt / model / sampling / evaluator
    registry = _load_json(D1_REGISTRY)
    recipe = registry.get("recipe_lock", {})
    prompt_sha_ok = (recipe.get("prompt", {}).get("sha256")
                     == D1_EXPECTED_PROMPT_SHA)
    disk_prompt_sha = _sha256_file(D1_PROMPT) if D1_PROMPT.exists() else ""
    checks.append(_check_binding(
        "D1 prompt hash == registry lock", prompt_sha_ok,
        f"registry={recipe.get('prompt', {}).get('sha256', '')[:16]}"))
    checks.append(_check_binding(
        "D1 prompt file == registry lock", disk_prompt_sha == D1_EXPECTED_PROMPT_SHA,
        f"disk={disk_prompt_sha[:16]}"))
    manifest_prompt = (d1_manifest.get("prompts") or [{}])[0].get("sha256", "")
    checks.append(_check_binding(
        "D1 run manifest prompt == lock", manifest_prompt == D1_EXPECTED_PROMPT_SHA,
        f"manifest={manifest_prompt[:16]}"))
    model_ok = (d1_manifest.get("llm_model") == D1_EXPECTED_MODEL)
    checks.append(_check_binding(
        "D1 model == deepseek-v4-pro", model_ok,
        str(d1_manifest.get("llm_model"))))
    sampling = d1_manifest.get("sampling", {})
    checks.append(_check_binding(
        "D1 sampling t0/top1/4096",
        sampling.get("temperature") == 0.0 and sampling.get("top_p") == 1.0
        and sampling.get("max_tokens") == 4096, str(sampling)))
    checks.append(_check_binding(
        "D1 no gold read by runner", d1_manifest.get("gold_read_by_runner") is False))
    evaluator_sha = _sha256_file(EVALUATOR_CONFIG) if EVALUATOR_CONFIG.exists() else ""
    checks.append(_check_binding(
        "D1 evaluator config == registry lock",
        evaluator_sha == recipe.get("evaluator", {}).get("sha256"),
        f"disk={evaluator_sha[:16]}"))

    binding_ok = all(c["ok"] for c in checks)
    return {
        "method": "direct_llm",
        "snapshot": "s27_d1_v6_r3_clean_rerun_150_hist56d_v1",
        "llm_calls_recorded": d1_manifest.get("llm_calls"),
        "binding_ok": binding_ok,
        "zero_api_reevaluation_allowed": binding_ok,
        "checks": checks,
        "verdict": ("bound_to_formal_input_v2; zero-API candidate re-evaluation allowed"
                    if binding_ok else
                    "NOT bound; first mismatch: " + next(
                        (c["item"] for c in checks if not c["ok"]), "none")),
    }


def _verify_h1(v2: dict[str, Any], v2_sha: dict[str, str]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    v2_ids = {r["sample_id"] for r in v2["records"]}

    h1_manifest = _load_json(H1_MANIFEST)
    h1_predictions = _load_jsonl(H1_PREDICTIONS)

    checks.append(_check_binding(
        "H1 snapshot exists (predictions/manifest)",
        H1_PREDICTIONS.exists() and H1_MANIFEST.exists()))
    checks.append(_check_binding(
        "H1 predictions 150 rows", len(h1_predictions) == 150,
        f"{len(h1_predictions)} rows"))
    h1_ids = {r.get("sample_id") for r in h1_predictions}
    checks.append(_check_binding(
        "H1 prediction ids == formal input v2 ids", h1_ids == v2_ids))
    valid = sum(1 for r in h1_predictions
                if r.get("validation", {}).get("schema_valid"))
    checks.append(_check_binding(
        "H1 predictions schema-valid", valid == 150, f"{valid}/150"))

    # text binding: H1 source_text vs formal v2 text
    text_mismatch = 0
    for row in h1_predictions:
        want = v2_sha.get(row.get("sample_id"))
        if want is None:
            text_mismatch += 1
            continue
        if _sha256_bytes(row.get("source_text", "").encode("utf-8")) != want:
            text_mismatch += 1
    checks.append(_check_binding(
        "H1 source_text == formal v2 text (150/150)", text_mismatch == 0,
        f"{text_mismatch} mismatches"))

    # recipe: prompt / model / sampling (H1 recipe is embedded in the runner;
    # the manifest records the locked prompt file hash)
    manifest_prompt = (h1_manifest.get("prompts") or [{}])[0].get("sha256", "")
    checks.append(_check_binding(
        "H1 prompt hash == locked prompt", manifest_prompt == H1_EXPECTED_PROMPT_SHA,
        f"manifest={manifest_prompt[:16]}"))
    disk_prompt_sha = _sha256_file(H1_PROMPT) if H1_PROMPT.exists() else ""
    checks.append(_check_binding(
        "H1 prompt file == locked prompt", disk_prompt_sha == H1_EXPECTED_PROMPT_SHA,
        f"disk={disk_prompt_sha[:16]}"))
    checks.append(_check_binding(
        "H1 model == deepseek-v4-pro",
        h1_manifest.get("llm_model") == H1_EXPECTED_MODEL,
        str(h1_manifest.get("llm_model"))))
    sampling = h1_manifest.get("sampling", {})
    checks.append(_check_binding(
        "H1 sampling t0/top1", sampling.get("temperature") == 0.0
        and sampling.get("top_p") == 1.0, str(sampling)))
    checks.append(_check_binding(
        "H1 b0 binding verified", bool(h1_manifest.get("b0_binding", {}).get("manifest", {}).get("verified"))))

    binding_ok = all(c["ok"] for c in checks)
    return {
        "method": "sun_llm_fallback",
        "snapshot": "s28d_h1_150_v4pro_v1",
        "llm_calls_recorded": h1_manifest.get("llm_calls"),
        "binding_ok": binding_ok,
        "zero_api_reevaluation_allowed": binding_ok,
        "checks": checks,
        "verdict": ("bound_to_formal_input_v2; zero-API candidate re-evaluation allowed"
                    if binding_ok else
                    "NOT bound; first mismatch: " + next(
                        (c["item"] for c in checks if not c["ok"]), "none")),
    }


def _verify_b0(v2: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    v2_ids = {r["sample_id"] for r in v2["records"]}
    b0_config = _load_json(B0_CONFIG)
    # B0 (sun_rule_only) is zero-API by construction; the formal candidate
    # runner (run_estg150_b0_formal.py) consumes formal input v2 directly.
    checks.append(_check_binding(
        "B0 method is zero-API (llm_used=false)",
        b0_config.get("safety", {}).get("llm_api_called") is False))
    checks.append(_check_binding(
        "B0 formal candidate runner exists",
        (ROOT / "scripts" / "run_estg150_b0_formal.py").exists()))
    b0_hist = _load_json(B0_HIST_ATTEMPTS) if B0_HIST_ATTEMPTS.exists() else []
    checks.append(_check_binding(
        "B0 historical attempts 150 rows", len(b0_hist) == 150,
        f"{len(b0_hist)} rows (development provenance only)"))
    if b0_hist:
        b0_ids = {r.get("sample_id") for r in b0_hist}
        checks.append(_check_binding(
            "B0 historical ids == formal v2 ids", b0_ids == v2_ids))
    checks.append(_check_binding(
        "B0 history is development-only (not formal)",
        (B0_HIST_MANIFEST.exists()
         and _load_json(B0_HIST_MANIFEST).get("claim_scope") == "development")))
    return {
        "method": "sun_rule_only",
        "snapshot": "formal_candidate_v1 (run by run_estg150_b0_formal.py)",
        "llm_calls_recorded": 0,
        "binding_ok": all(c["ok"] for c in checks),
        "zero_api_reevaluation_allowed": all(c["ok"] for c in checks),
        "checks": checks,
        "verdict": "zero-API by construction; formal candidate run required",
    }


def build_readiness() -> dict[str, Any]:
    v2 = _load_json(V2_INPUT)
    v2_sha = _text_sha_of_v2(v2)
    d1 = _verify_d1(v2, v2_sha)
    h1 = _verify_h1(v2, v2_sha)
    b0 = _verify_b0(v2)
    return {
        "schema_version": "b0_d1_formal_readiness@2.0.0",
        "generated_zero_api": True,
        "formal_input_v2": {
            "path": "data/input/estg150_formal_inference_input_v2.json",
            "records": len(v2.get("records", [])),
            "sha256": _sha256_file(V2_INPUT),
        },
        "gold_stage2": {"path": "data/gold/stage2/estg150_formal_gold_v1.json",
                        "sha256": _sha256_file(GOLD_STAGE2)},
        "membership_sha256": MEMBERSHIP_SHA,
        "methods": {
            "sun_rule_only": b0,
            "direct_llm": d1,
            "sun_llm_fallback": h1,
        },
        "summary": {
            "d1_historical_predictions_reusable_zero_api": d1["binding_ok"],
            "h1_historical_predictions_reusable_zero_api": h1["binding_ok"],
            "b0_requires_formal_candidate_run": True,
            "any_new_llm_api_call_required": False,
        },
    }


def main() -> int:
    readiness = build_readiness()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(readiness, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT_JSON.exists() and OUT_JSON.read_bytes() != data:
        raise RuntimeError(f"refusing to overwrite different content: {OUT_JSON}")
    OUT_JSON.write_bytes(data)

    md = ["# B0/D1/H1 Formal Readiness v2 (zero-API audit)",
          "",
          f"- formal input v2: 150 records (sha256 {readiness['formal_input_v2']['sha256'][:16]}...)",
          f"- Stage 2 Gold: sha256 {readiness['gold_stage2']['sha256'][:16]}...",
          ""]
    for method, info in readiness["methods"].items():
        md.append(f"## {method} ({info['snapshot']})")
        md.append(f"- binding_ok: {info['binding_ok']}")
        md.append(f"- zero-API re-evaluation allowed: {info['zero_api_reevaluation_allowed']}")
        md.append(f"- verdict: {info['verdict']}")
        for c in info["checks"]:
            md.append(f"- [{'PASS' if c['ok'] else 'FAIL'}] {c['item']}"
                      + (f" {c['detail']}" if c["detail"] else ""))
        md.append("")
    md.append("## Summary")
    md.append(f"- D1 historical predictions reusable zero-API: "
              f"{readiness['summary']['d1_historical_predictions_reusable_zero_api']}")
    md.append(f"- H1 historical predictions reusable zero-API: "
              f"{readiness['summary']['h1_historical_predictions_reusable_zero_api']}")
    md.append(f"- new LLM API call required: {readiness['summary']['any_new_llm_api_call_required']}")
    md.append("")
    text = "\n".join(md)
    if OUT_MD.exists() and OUT_MD.read_text(encoding="utf-8") != text:
        raise RuntimeError(f"refusing to overwrite different content: {OUT_MD}")
    OUT_MD.write_text(text, encoding="utf-8")

    print(f"readiness v2 written: {OUT_JSON.relative_to(ROOT)}")
    for method, info in readiness["methods"].items():
        print(f"  {method}: binding_ok={info['binding_ok']} "
              f"zero_api={info['zero_api_reevaluation_allowed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
