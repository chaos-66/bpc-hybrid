"""Freeze five D1 requests or run the existing B0 locally; no real API entry.

Uses the existing prompt, B0 implementation, and coordinate capsule adapters.
This file does not implement a new temporal extractor or change a detector.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_gdpr7_direct_llm_preflight_v1 as d1_recipe
import run_gdpr7_sun_rule_only_v1 as b0_recipe
from bpc_hybrid.s2_12_method_adapter import adapt_method_attempts
from bpc_hybrid.sun_stage3.gdpr_capsule_converter import build_rule_records

PACK = ROOT / "data/development/stage3_reconstruction_v4"
INPUT = PACK / "stage2_input.json"
PREFLIGHT = ROOT / "outputs/reports/stage3_d1_preflight_v4.json"
B0_OUT = ROOT / "data/predictions/stage3_v4_b0_frozen_v1"
RUNTIME = Path("D:/environment/stanford-corenlp-4.5.10")
EXPECTED_INPUT_SHA = "4c934712d4e85316167136a46861084165c75969c113eca7d995de5ddaabd1f2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load_inputs() -> tuple[dict, list[dict]]:
    if sha(INPUT) != EXPECTED_INPUT_SHA:
        raise ValueError("v4 source input hash drift")
    doc = json.loads(INPUT.read_text(encoding="utf-8"))
    if doc.get("gold_visible") is not False or doc.get("counts") != {"rules": 5, "sentences": 5}:
        raise ValueError("input scope drift")
    sentences = []
    for rule in doc["rules"]:
        for sentence in rule["sentences"]:
            text = sentence["approved_text_en"]
            if hashlib.sha256(text.encode("utf-8")).hexdigest() != sentence["text_sha256"]:
                raise ValueError("source text hash drift")
            if sentence["sample_id"] != f"gdpr_{rule['rule_id']}_s001":
                raise ValueError("input identity drift")
            sentences.append({**sentence, "rule_id": rule["rule_id"]})
    if len({s["sample_id"] for s in sentences}) != 5:
        raise ValueError("duplicate/missing input")
    return doc, sentences


def request_bodies() -> list[tuple[dict, dict]]:
    _, sentences = load_inputs()
    d1_recipe._verify_registry()
    prompt = d1_recipe.load_prompt(d1_recipe.PROMPT_NAME)
    if prompt.sha256 != d1_recipe.EXPECTED_PROMPT_SHA256:
        raise ValueError("frozen D1 prompt drift")
    few_shot = d1_recipe._few_shot_block(prompt)
    builder = d1_recipe.OpenAICompatibleRequestBuilder(d1_recipe._config())
    policy = d1_recipe._policy()
    rows = []
    for sentence in sentences:
        sid = sentence["sample_id"]
        user = prompt.user_prompt_template.format(sample_id=sid, source_id=sid,
            source_text=sentence["approved_text_en"], few_shot_block=few_shot)
        body = policy.apply_to_body(builder.build_body(prompt.system_prompt, user))
        rows.append((sentence, body))
    return rows


def build_preflight() -> dict:
    tokenizer = d1_recipe._load_proxy_tokenizer(d1_recipe._default_tokenizer_snapshot())
    calls = []
    for index, (sentence, body) in enumerate(request_bodies(), 1):
        raw = json.dumps(body).encode("utf-8")
        content = "\n".join(m["content"] for m in body["messages"])
        calls.append({"index": index, "sample_id": sentence["sample_id"],
                      "source_text_sha256": sentence["text_sha256"],
                      "body_sha256": hashlib.sha256(raw).hexdigest(), "body_bytes": len(raw),
                      "local_proxy_input_tokens": len(tokenizer.encode(content, add_special_tokens=True).ids),
                      "max_output_tokens": 4096})
    proxy = sum(c["local_proxy_input_tokens"] for c in calls)
    output = 5 * 4096
    # Conservative provider-context bound, not the much smaller token proxy.
    context_input_cap = 5 * 1_000_000
    raw_cap = (context_input_cap * 1.32 + output * 3.96) / 1_000_000
    return {"schema_version": "stage3_d1_preflight_v4@1.0.0", "authorized": False,
        "calls_made": 0, "planned_calls": 5, "retry_cap": 0,
        "scope": "Five scoped GDPR excerpts, independent Direct-LLM extraction only; no old 74-input rerun",
        "method": {"model": "deepseek-v4-pro", "documented_release": "DeepSeek-V4-Pro-0813",
                   "temperature": 0, "top_p": 1, "max_tokens": 4096, "thinking": "disabled",
                   "stream": False, "response_format": None, "seed": "omitted"},
        "input_sha256": sha(INPUT), "prompt_sha256": d1_recipe.EXPECTED_PROMPT_SHA256,
        "registry_sha256": d1_recipe.EXPECTED_REGISTRY_SHA256,
        "preparer_sha256": sha(Path(__file__)), "calls": calls,
        "price_snapshot": {"source": "https://api-docs.deepseek.com/quick_start/pricing/",
            "verified_date": "2026-09-23", "currency": "USD", "per_million_peak": {
                "input_cache_hit": 0.044, "input_cache_miss": 1.32, "output": 3.96},
            "off_peak_multiplier": 0.5, "reverify_before_authorized_execution": True},
        "planning_estimate": {"proxy": d1_recipe.TOKENIZER_PROXY, "input_proxy_tokens": proxy,
            "output_cap_tokens": output,
            "cost_using_proxy_input_and_max_output_usd": round((proxy * 1.32 + output * 3.96) / 1_000_000, 6),
            "not_actual_bill_or_provider_tokenizer": True},
        "recommended_authorization_hard_caps": {"calls": 5, "retries": 0, "total_input_tokens": context_input_cap,
            "total_output_tokens": output, "usd_peak_including_20_percent_margin": math.ceil(raw_cap * 1.2 * 100) / 100},
        "execution_blockers": ["explicit user authorization for these five requests and cap absent",
            "scoped benchmark not yet accepted as final Table 3 scope",
            "Sun reconstruction has no implemented rule-order extraction path"],
        "gold_read": False, "env_read": False, "network_calls": 0}


def run_b0(runtime: Path = RUNTIME) -> dict:
    if B0_OUT.exists():
        raise FileExistsError(f"refusing to overwrite {B0_OUT}")
    # Existing recipe bindings, including weights, remain authoritative.
    lock = b0_recipe._verify_lock()
    doc, sentences = load_inputs()
    records = [{"sample_id": s["sample_id"], "legacy_record_id": s["sample_id"],
                "approved_text_en": s["approved_text_en"], "raw_text_de": s["approved_text_en"]}
               for s in sentences]
    started = time.perf_counter()
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    (ROOT / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="s3-v4-b0-", dir=ROOT / ".tmp") as work:
        attempts, telemetry = b0_recipe.run_b0_batch_v10(ROOT, records,
            runtime_home=runtime, work_dir=Path(work), device="cpu")
    adapted = adapt_method_attempts(attempts, "sun_rule_only")
    if {r["sample_id"] for r in adapted} != {s["sample_id"] for s in sentences} or len(adapted) != 5:
        raise ValueError("B0 returned wrong input population")
    predictions = [b0_recipe._sanitize_attempt(a) for a in adapted]
    if b0_recipe._contains_raw_text(predictions):
        raise ValueError("coordinate capsule contains raw text")
    capsule = {"schema_version": b0_recipe.PREDICTION_SCHEMA, "dataset_id": doc["dataset_id"],
               "method_id": "sun_rule_only", "record_count": 5, "gold_read_by_runner": False,
               "raw_text_committed": False, "records": predictions}
    rule_records, conversion = build_rule_records(capsule,
        {s["sample_id"]: s["approved_text_en"] for s in sentences}, [r["rule_id"] for r in doc["rules"]])
    inventory = {}
    for prediction in predictions:
        clauses = (prediction.get("record") or {}).get("clauses") or []
        inventory[prediction["sample_id"]] = {"clause_count": len(clauses),
            "modality_labels": [(c.get("modality") or {}).get("label") for c in clauses],
            **{k: sum(len(c.get(k) or []) for c in clauses) for k in
               ("actions", "actors", "conditions", "constraints", "actor_action_map", "order_relations")}}
    files = {"predictions.json": data_bytes(capsule), "telemetry.json": data_bytes(telemetry),
             "extraction_inventory.json": data_bytes({"sample_inventory": inventory,
                "converter": conversion, "performance_evaluation_run": False,
                "rule_records_order_counts": {r: len(v["order_relations"]) for r, v in rule_records.items()}})}
    manifest = {"schema_version": "stage3_v4_b0_run@1.0.0", "run_id": "stage3_v4_b0_frozen_v1",
        "status": "predictions_persisted_not_stage3_performance", "method": "b0_enhanced_v10a",
        "input_sha256": sha(INPUT), "runner_sha256": sha(Path(__file__)),
        "original_method_bindings": lock["bindings"], "language_boundary": lock["method"]["language_boundary"],
        "calls": 0, "cost_usd": 0, "gold_read": False, "control_or_case_map_read": False,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "artifacts": {k: {"sha256": hashlib.sha256(v).hexdigest(), "bytes": len(v)} for k, v in files.items()},
        "command": "python formal_experiment/scripts/prepare_stage3_execution_v4.py --run-b0"}
    files["manifest.json"] = data_bytes(manifest)
    B0_OUT.mkdir(parents=True)
    for name, raw in files.items():
        with (B0_OUT / name).open("xb") as handle:
            handle.write(raw)
    return {"status": manifest["status"], "output": str(B0_OUT), "elapsed_seconds": manifest["elapsed_seconds"],
            "sample_inventory": inventory}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--run-b0", action="store_true")
    args = parser.parse_args()
    if args.run_b0:
        result = run_b0()
    else:
        result = build_preflight()
        with PREFLIGHT.open("xb") as handle:
            handle.write(data_bytes(result))
        result = {k: result[k] for k in ("planned_calls", "planning_estimate", "recommended_authorization_hard_caps")}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
