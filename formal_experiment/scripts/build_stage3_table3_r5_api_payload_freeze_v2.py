"""Freeze exact Stage-2 API requests for non-reusable Ours requirements (zero API).

The script reconstructs the frozen Direct-LLM payload from committed assets:

``requirement -> excerpt_text -> prompt -> messages -> request body -> SHA256``

It never reads ``.env`` and never performs a network/API call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import r5_reuse_verification as rv  # noqa: E402
from bpc_hybrid.h1_transport import H1RequestPolicy  # noqa: E402
from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder  # noqa: E402
from bpc_hybrid.llm_config import LLMConfig  # noqa: E402
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402

CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v2.json"
SOURCE_REQ = ROOT / "data/development/stage3_table3_r5_benchmark_v2/source_requirements.json"
OUTPUT = ROOT / "outputs/reports/stage3_table3_r5_api_payload_freeze_v2.json"
BENCHMARK_ID = "stage3_table3_r5_benchmark_v2"
PROMPT_NAME = "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05"
MODEL_ID = "deepseek-v4-pro"
PUBLISHED_ALIAS = "DeepSeek-V4-Pro-0813"
BASE_URL = "https://api.deepseek.com/v1"
MAX_OUTPUT_TOKENS = 4096


def _few_shot_block(prompt: Any) -> str:
    """Return the raw Examples section exactly as sent by the frozen recipe."""
    raw = getattr(prompt, "raw_text", "")
    start = raw.find("## Examples")
    end = raw.find("## Notes", start)
    if start == -1 or end == -1:
        return ""
    return raw[start:end].strip()


FORBIDDEN_BODY_KEYS = {
    "variant", "mutation", "mutation_type", "reference_states", "reference",
    "target_node", "target_rule", "family_id", "requirement_id",
    "case_family", "answer", "gold", "label", "source_family_id", "split",
}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_text(value: str) -> str:
    return sha_bytes(value.encode("utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    # Preserve nested request-body key order: the frozen body SHA is computed
    # over default ``json.dumps(body)``; sorting the file would make that
    # reconstruction ambiguous after a load/dump round trip.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
                    encoding="utf-8", newline="\n")


def sample_id_for(spec: Mapping[str, Any]) -> str:
    if spec.get("sample_id"):
        return str(spec["sample_id"])
    if spec.get("r4_rule_id"):
        return f"gdpr_{spec['r4_rule_id']}_s001"
    return f"r5_{str(spec['requirement_id']).lower().replace('-', '_')}_s001"


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            keys.add(str(key))
            keys.update(_walk_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_walk_keys(item))
    return keys


def build_payload_manifest() -> dict[str, Any]:
    config = load_json(CONFIG)
    source_doc = load_json(SOURCE_REQ)
    reuse = rv.verify_reuse(config, source_doc)
    specs = {s["requirement_id"]: s for s in config["requirements"]}
    sources = {s["requirement_id"]: s for s in source_doc["requirements"]}
    prompt = load_prompt(PROMPT_NAME)
    prompt_sha = sha_text(prompt.raw_text)
    builder = OpenAICompatibleRequestBuilder(LLMConfig(
        enabled=False,
        provider="openai_compatible",
        model=MODEL_ID,
        api_key=None,
        base_url=BASE_URL,
        max_tokens=MAX_OUTPUT_TOKENS,
        temperature=0.0,
        top_p=1.0,
        seed=None,
        seed_supported=False,
    ))
    policy = H1RequestPolicy(
        stream=False,
        thinking={"type": "disabled"},
        response_format=None,
    )
    few_shot = _few_shot_block(prompt)
    request_rows: list[dict[str, Any]] = []
    ordinal = 0
    for reuse_row in reuse["rows"]:
        rid = reuse_row["requirement_id"]
        if not reuse_row["core_eligible"]:
            continue
        if reuse_row["ours"]["status"] == "verified":
            continue
        ordinal += 1
        spec = specs[rid]
        src = sources[rid]
        sample_id = sample_id_for(spec)
        source_text = src["excerpt_text"]
        user_prompt = prompt.user_prompt_template.format(
            sample_id=sample_id,
            source_id=sample_id,
            source_text=source_text,
            few_shot_block=few_shot,
        )
        body = policy.apply_to_body(builder.build_body(prompt.system_prompt, user_prompt))
        body_bytes = json.dumps(body).encode("utf-8")
        body_keys = _walk_keys(body)
        forbidden = sorted(FORBIDDEN_BODY_KEYS & body_keys)
        if forbidden:
            raise RuntimeError(f"forbidden body keys for {rid}: {forbidden}")
        request_rows.append({
            "request_ordinal": ordinal,
            "requirement_id": rid,
            "family_id": spec["source_family_id"],
            "split": spec["split"],
            "source_text": source_text,
            "source_text_sha256": sha_text(source_text),
            "source_id": sample_id,
            "sample_id": sample_id,
            "frozen_prompt_name": PROMPT_NAME,
            "prompt_sha256": prompt_sha,
            "exact_system_message": prompt.system_prompt,
            "system_message_sha256": sha_text(prompt.system_prompt),
            "exact_user_message": user_prompt,
            "user_message_sha256": sha_text(user_prompt),
            "request_body": body,
            "request_body_sha256": sha_bytes(body_bytes),
            "request_body_utf8_bytes": len(body_bytes),
            "model": MODEL_ID,
            "resolved_alias": PUBLISHED_ALIAS,
            "temperature": 0,
            "top_p": 1,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "retry_policy": "0",
            "stream": False,
            "thinking": {"type": "disabled"},
            "response_format": None,
            "predicted_output_destination": (
                f"outputs/development/stage3_table3_r5_ours_stage2_v2/{sample_id}.json"
            ),
            "reuse_status": reuse_row["ours"]["status"],
            "reuse_evidence_strength": reuse_row["ours"].get("reuse_evidence_strength"),
        })
    excluded_candidates = [
        row["requirement_id"] for row in reuse["rows"]
        if not row["core_eligible"]
    ]
    request_ids = [r["requirement_id"] for r in request_rows]
    manifest_core = {
        "schema_version": "stage3_table3_r5_api_payload_freeze@2.0.0",
        "benchmark_id": BENCHMARK_ID,
        "status": "API_PAYLOAD_FROZEN_AUTHORIZATION_PENDING",
        "real_api_calls_made": 0,
        "authorization_status": "PENDING",
        "authorization_consumed_this_round": False,
        "new_request_count": len(request_rows),
        "request_ids": request_ids,
        "candidate_assets_excluded_from_current_request_list": excluded_candidates,
        "api_unit": "one unique regulation input; all BPMN variants reuse the extraction",
        "protocol": {
            "model": MODEL_ID,
            "resolved_alias": PUBLISHED_ALIAS,
            "base_url": BASE_URL,
            "temperature": 0,
            "top_p": 1,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "retry": 0,
            "stream": False,
            "thinking": {"type": "disabled"},
            "response_format": None,
            "seed": None,
            "json_dumps_convention": "default json.dumps(body).encode('utf-8')",
        },
        "prompt": {
            "name": PROMPT_NAME,
            "sha256_text_normalized": prompt_sha,
            "few_shot_block_present": bool(few_shot),
            "system_message_sha256": sha_text(prompt.system_prompt),
        },
        "reconstruction_recipe": [
            "load prompt by frozen name via bpc_hybrid.prompt_loader",
            "render user_prompt_template with sample_id/source_id/source_text/few_shot_block",
            "build_body with frozen OpenAICompatibleRequestBuilder/LLMConfig",
            "apply H1RequestPolicy(stream=false, thinking disabled, response_format=None)",
            "serialize with default json.dumps(body).encode('utf-8') and SHA256",
        ],
        "requests": request_rows,
    }
    price_snapshot_path = ROOT / "data/predictions/stage3_v4_d1_frozen_v1/preflight_snapshot.json"
    if price_snapshot_path.exists():
        price_doc = load_json(price_snapshot_path)
        peak = price_doc["price_snapshot"]["per_million_peak"]
        price = {
            "source": price_doc["price_snapshot"].get("source"),
            "verified_date": price_doc["price_snapshot"].get("verified_date"),
            "off_peak_multiplier": price_doc["price_snapshot"].get("off_peak_multiplier", 0.5),
            "per_million_peak": peak,
            "reverify_before_authorized_execution": True,
        }
    else:
        gdpr_manifest = load_json(ROOT / "data/predictions/gdpr7_direct_llm_v1/manifest.json")
        pricing = gdpr_manifest["pricing"]
        peak = {
            "input_cache_hit": pricing["input_cache_hit_per_million"] * 2,
            "input_cache_miss": pricing["input_cache_miss_per_million"] * 2,
            "output": pricing["output_per_million"] * 2,
        }
        price = {
            "source": "data/predictions/gdpr7_direct_llm_v1/manifest.json::pricing (recorded snapshot)",
            "verified_date": None,
            "off_peak_multiplier": 0.5,
            "per_million_peak": peak,
            "reverify_before_authorized_execution": True,
        }
    total_input_upper = sum(int(r["request_body_utf8_bytes"]) for r in request_rows)
    total_output_upper = len(request_rows) * MAX_OUTPUT_TOKENS
    raw_cost = (
        total_input_upper * float(peak["input_cache_miss"])
        + total_output_upper * float(peak["output"])
    ) / 1_000_000
    margin_cost = __import__("math").ceil(raw_cost * 1.2 * 100) / 100
    manifest_core["budget_upper_bound"] = {
        "max_input_tokens": total_input_upper,
        "max_output_tokens": total_output_upper,
        "raw_cost_cap_usd": round(raw_cost, 6),
        "cost_cap_with_20pct_margin_usd": margin_cost,
        "price": price,
        "token_upper_bound_policy": "one UTF-8 body byte <= one token (conservative); output = 4096 max_tokens per call",
        "real_api_calls_made": 0,
        "authorization_status": "PENDING",
    }
    canonical = json.dumps(manifest_core, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest_core["payload_manifest_sha256"] = sha_bytes(canonical)
    return manifest_core


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = build_payload_manifest()
    if args.write:
        write_json(OUTPUT, manifest)
    if args.check:
        if not OUTPUT.exists():
            raise SystemExit("payload manifest missing; run --write first")
        existing = load_json(OUTPUT)
        if existing != manifest:
            raise SystemExit("payload manifest drift or non-reconstructible")
    print(json.dumps({
        "new_request_count": manifest["new_request_count"],
        "request_ids": manifest["request_ids"],
        "payload_manifest_sha256": manifest["payload_manifest_sha256"],
        "real_api_calls_made": 0,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
