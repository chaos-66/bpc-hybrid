# -*- coding: utf-8 -*-
"""Build the S2.12 API-arm preflight without reading Gold or calling an API.

The script reconstructs the exact final OpenAI-compatible request bodies for
``direct_llm`` and ``sun_llm_fallback``.  H1 diagnostics are regenerated with
the locked local B0 implementation and must sanitize to the already locked
zero-API predictions before a payload can be counted.  Only hashes, byte
sizes, local proxy-token counts, and aggregate cost planning data are
committed; prompts and third-party source text remain local-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.b0_artifact import clean_b0_entry  # noqa: E402
from bpc_hybrid.estg150_b0_development_v10 import run_b0_batch_v10  # noqa: E402
from bpc_hybrid.h1_transport import (  # noqa: E402
    DEEPSEEK_V4_PRO_H1_POLICY,
    H1RequestPolicy,
)
from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder  # noqa: E402
from bpc_hybrid.llm_config import LLMConfig  # noqa: E402
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from bpc_hybrid.s2_12_method_adapter import adapt_method_attempts  # noqa: E402
from run_direct_llm import _few_shot_block  # noqa: E402
from run_s2_12_sun_rule_only_v1 import (  # noqa: E402
    _resolve_records,
    _sanitize_attempt,
    _verify_lock,
)
from run_sun_llm_fallback import (  # noqa: E402
    _build_context_audit,
    _build_user_prompt,
    allocate_repair_calls,
    build_repair_plans,
)

LOCK = ROOT / "configs/s2_12_api_arms_preflight_v1.json"
INPUT = ROOT / "data/input/s2_12_complex_corpus_formal_input_v1.json"
LOCKED_PREDICTIONS = ROOT / "data/predictions/s2_12_sun_rule_only_v1/predictions.json"
OUTPUT = ROOT / "outputs/reports/s2_12_api_preflight_v1.json"


class PreflightFail(ValueError):
    """Fail-closed preflight error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _verify_file_bindings(bindings: Mapping[str, str]) -> None:
    for rel, expected in bindings.items():
        path = ROOT / Path(rel.replace("/", os.sep))
        if not path.is_file() or _sha(path) != expected:
            raise PreflightFail(f"implementation binding drift: {rel}")


def _load_proxy_tokenizer(snapshot: Path, spec: Mapping[str, Any]) -> Any:
    for name, expected in spec["file_sha256"].items():
        path = snapshot / name
        if not path.is_file() or _sha(path) != expected:
            raise PreflightFail(f"local tokenizer proxy binding drift: {name}")
    try:
        from tokenizers import BertWordPieceTokenizer
    except ImportError as exc:
        raise PreflightFail("tokenizers is unavailable for local proxy counts") from exc
    return BertWordPieceTokenizer(str(snapshot / "vocab.txt"), lowercase=True)


def _rerun_b0(runtime_home: Path) -> tuple[list[dict[str, Any]], list[Any]]:
    # Verifies every method/source/input binding and contains no Gold path.
    _verify_lock()
    input_doc = json.loads(INPUT.read_text(encoding="utf-8"))
    source_records, runtime_to_formal = _resolve_records(input_doc)
    (ROOT / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="s212-preflight-b0-", dir=ROOT / ".tmp") as work:
        attempts, _runtime = run_b0_batch_v10(
            ROOT,
            source_records,
            runtime_home=runtime_home,
            work_dir=Path(work),
            device="cpu",
        )
    for attempt in attempts:
        runtime_id = str(attempt.get("sample_id"))
        formal_id = runtime_to_formal.get(runtime_id)
        if formal_id is None:
            raise PreflightFail(f"unknown B0 runtime sample ID: {runtime_id}")
        attempt["sample_id"] = formal_id
        record = attempt.get("record") or {}
        record["sample_id"] = formal_id
    adapted = adapt_method_attempts(attempts, "sun_rule_only")
    if len(adapted) != 36 or {row.get("request_status") for row in adapted} != {"ok"}:
        raise PreflightFail("diagnostic B0 replay did not produce 36 successful records")
    locked = json.loads(LOCKED_PREDICTIONS.read_text(encoding="utf-8"))
    sanitized = [_sanitize_attempt(row) for row in adapted]
    if sanitized != locked.get("records"):
        raise PreflightFail("diagnostic B0 replay differs from locked predictions")
    return adapted, [clean_b0_entry(row) for row in adapted]


def _config(lock: Mapping[str, Any]) -> LLMConfig:
    common = lock["common_sampling"]
    provider = lock["provider"]
    return LLMConfig(
        enabled=False,
        provider=provider["kind"],
        model=provider["model"],
        api_key=None,
        base_url=provider["base_url"],
        max_tokens=common["max_output_tokens_per_call"],
        temperature=common["temperature"],
        top_p=common["top_p"],
        seed=common["seed"],
        seed_supported=common["seed_supported"],
    )


def _call_row(
    *,
    index: int,
    sample_id: str,
    clause_id: str | None,
    system_prompt: str,
    user_prompt: str,
    policy: H1RequestPolicy,
    builder: OpenAICompatibleRequestBuilder,
    tokenizer: Any,
) -> dict[str, Any]:
    body = policy.apply_to_body(builder.build_body(system_prompt, user_prompt))
    # This exactly mirrors RealAPITransport.send: default json.dumps, UTF-8.
    body_bytes = json.dumps(body).encode("utf-8")
    proxy_input = system_prompt + "\n" + user_prompt
    proxy_tokens = len(tokenizer.encode(proxy_input, add_special_tokens=True).ids)
    return {
        "call_index": index,
        "sample_id": sample_id,
        "clause_id": clause_id,
        "request_body_sha256": _sha_bytes(body_bytes),
        "request_body_utf8_bytes": len(body_bytes),
        "system_prompt_utf8_bytes": len(system_prompt.encode("utf-8")),
        "user_prompt_utf8_bytes": len(user_prompt.encode("utf-8")),
        "local_proxy_tokens": proxy_tokens,
    }


def _summary(values: Sequence[int]) -> dict[str, int]:
    if not values:
        return {"minimum": 0, "maximum": 0, "total": 0}
    return {"minimum": min(values), "maximum": max(values), "total": sum(values)}


def _arm_report(
    spec: Mapping[str, Any], prompt: Any, calls: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "prompt_name": spec["prompt_name"],
        "prompt_sha256": prompt.sha256,
        "transport_policy": spec["transport_policy"],
        "planned_calls": len(calls),
        "max_calls": spec["max_calls"],
        "max_output_tokens_per_call": 4096,
        "max_output_tokens_total": len(calls) * 4096,
        "retry_count": 0,
        "request_body_utf8_bytes": _summary(
            [row["request_body_utf8_bytes"] for row in calls]
        ),
        "local_proxy_tokens": _summary([row["local_proxy_tokens"] for row in calls]),
        "calls": calls,
    }


def build(runtime_home: Path, tokenizer_snapshot: Path) -> dict[str, Any]:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if lock.get("status") != "locked_without_api_authorization":
        raise PreflightFail("API preflight lock status drift")
    if lock.get("authorization", {}).get("real_api_calls_allowed_by_this_lock") is not False:
        raise PreflightFail("preflight lock must not authorize API calls")
    _verify_file_bindings(lock["implementation_bindings"])
    if _sha(INPUT) != lock["input"]["sha256"]:
        raise PreflightFail("Gold-blind input drift")
    if _sha(LOCKED_PREDICTIONS) != lock["locked_b0_predictions"]["sha256"]:
        raise PreflightFail("locked B0 prediction drift")
    tokenizer = _load_proxy_tokenizer(tokenizer_snapshot, lock["local_tokenizer_proxy"])
    adapted, batch = _rerun_b0(runtime_home)

    config = _config(lock)
    builder = OpenAICompatibleRequestBuilder(config)

    direct_spec = lock["arms"]["direct_llm"]
    direct_prompt = load_prompt(direct_spec["prompt_name"])
    if direct_prompt.sha256 != direct_spec["prompt_sha256"]:
        raise PreflightFail("direct prompt drift")
    direct_policy = H1RequestPolicy(
        stream=False, thinking={"type": "disabled"}, response_format=None
    )
    few_shot = _few_shot_block(direct_prompt)
    direct_calls: list[dict[str, Any]] = []
    for index, item in enumerate(batch, 1):
        record = item.record
        user_prompt = direct_prompt.user_prompt_template.format(
            sample_id=record["sample_id"],
            source_id=record["sample_id"],
            source_text=record["source_text"],
            few_shot_block=few_shot,
        )
        direct_calls.append(_call_row(
            index=index,
            sample_id=record["sample_id"],
            clause_id=None,
            system_prompt=direct_prompt.system_prompt,
            user_prompt=user_prompt,
            policy=direct_policy,
            builder=builder,
            tokenizer=tokenizer,
        ))
    if len(direct_calls) != direct_spec["max_calls"]:
        raise PreflightFail("direct call count does not equal the 36-record lock")

    h1_spec = lock["arms"]["sun_llm_fallback"]
    h1_prompt = load_prompt(h1_spec["prompt_name"])
    if h1_prompt.sha256 != h1_spec["prompt_sha256"]:
        raise PreflightFail("H1 prompt drift")
    plans = allocate_repair_calls(build_repair_plans(batch), h1_spec["max_calls"])
    records = {item.record["sample_id"]: item.record for item in batch}
    h1_calls: list[dict[str, Any]] = []
    for index, plan in enumerate(plans, 1):
        record = records[plan.sample_id]
        clause = record["clauses"][plan.clause_index]
        context_clause, audit = _build_context_audit(clause, plan, "full_b0_v4")
        if not audit.get("original_record_unchanged"):
            raise PreflightFail(f"H1 context mutated B0 record: {plan.sample_id}/{plan.clause_id}")
        user_prompt = _build_user_prompt(h1_prompt, record, plan, context_clause)
        h1_calls.append(_call_row(
            index=index,
            sample_id=plan.sample_id,
            clause_id=plan.clause_id,
            system_prompt=h1_prompt.system_prompt,
            user_prompt=user_prompt,
            policy=DEEPSEEK_V4_PRO_H1_POLICY,
            builder=builder,
            tokenizer=tokenizer,
        ))
    if len(h1_calls) > h1_spec["max_calls"]:
        raise PreflightFail("H1 call selection exceeds its hard cap")

    arms = {
        "direct_llm": _arm_report(direct_spec, direct_prompt, direct_calls),
        "sun_llm_fallback": _arm_report(h1_spec, h1_prompt, h1_calls),
    }
    planned_calls = sum(arm["planned_calls"] for arm in arms.values())
    body_total = sum(arm["request_body_utf8_bytes"]["total"] for arm in arms.values())
    body_max = max(arm["request_body_utf8_bytes"]["maximum"] for arm in arms.values())
    proxy_total = sum(arm["local_proxy_tokens"]["total"] for arm in arms.values())
    proxy_max = max(arm["local_proxy_tokens"]["maximum"] for arm in arms.values())
    output_cap = planned_calls * lock["common_sampling"]["max_output_tokens_per_call"]
    price = lock["pricing"]["per_million_tokens"]
    proxy_input_miss_cost = proxy_total * price["input_cache_miss"] / 1_000_000
    proxy_input_hit_cost = proxy_total * price["input_cache_hit"] / 1_000_000
    max_output_cost = output_cap * price["output"] / 1_000_000
    context_input_cap = planned_calls * lock["pricing"]["official_context_tokens_per_call"]
    conservative_context_cost = (
        context_input_cap * price["input_cache_miss"] / 1_000_000
        + max_output_cost
    )
    recommended_usd_cap = math.ceil(conservative_context_cost * 100) / 100

    return {
        "schema_version": "s2_12_api_preflight_report@1.0.0",
        "status": "payloads_locked_zero_api_authorization_pending",
        "dataset_id": lock["dataset_id"],
        "preflight_lock": {
            "path": "configs/s2_12_api_arms_preflight_v1.json",
            "sha256": _sha(LOCK),
        },
        "input": {
            "path": lock["input"]["path"],
            "sha256": lock["input"]["sha256"],
            "records": 36,
            "raw_text_committed": False,
        },
        "model": {
            "provider": lock["provider"]["kind"],
            "base_url": lock["provider"]["base_url"],
            "id": lock["provider"]["model"],
            "fail_closed": True,
            "common_sampling": lock["common_sampling"],
            "implementation_bindings": lock["implementation_bindings"],
        },
        "gold_isolation": {
            **lock["gold_isolation"],
            "diagnostic_replay_equal_to_locked_predictions": True,
        },
        "token_measurement": {
            "exact_measurement": "final request body serialized by default json.dumps then UTF-8",
            "official_deepseek_v4_pro_tokenizer_available_locally": False,
            "official_billing_input_tokens": None,
            "official_billing_input_tokens_status": "available only from response usage after a real call",
            "local_proxy": {
                "model_id": lock["local_tokenizer_proxy"]["model_id"],
                "revision": lock["local_tokenizer_proxy"]["revision"],
                "kind": lock["local_tokenizer_proxy"]["kind"],
                "is_deepseek_tokenizer": False,
                "is_billing_token_count": False,
                "add_special_tokens": True,
                "truncation": False,
            },
        },
        "arms": arms,
        "global": {
            "planned_calls": planned_calls,
            "configured_hard_call_cap": lock["global_caps"]["max_calls"],
            "retry_count": 0,
            "request_body_utf8_bytes": {"maximum_per_call": body_max, "total": body_total},
            "local_proxy_tokens": {"maximum_per_call": proxy_max, "total": proxy_total},
            "max_output_tokens_per_call": 4096,
            "max_output_tokens_total": output_cap,
        },
        "pricing": {
            "checked_date": lock["pricing"]["checked_date"],
            "official_source": lock["pricing"]["official_models_and_pricing_url"],
            "official_token_usage_source": lock["pricing"]["official_token_usage_url"],
            "currency": "USD",
            "per_million_tokens": price,
            "proxy_based_planning_only_not_billable_exact": {
                "all_input_cache_hit_usd": proxy_input_hit_cost,
                "all_input_cache_miss_usd": proxy_input_miss_cost,
                "max_output_usd": max_output_cost,
                "cache_miss_input_plus_max_output_usd": proxy_input_miss_cost + max_output_cost,
            },
            "official_context_derived_absolute_bound": {
                "input_tokens": context_input_cap,
                "assumption": "each planned call consumes the full official 1M context as cache-miss input, plus the configured 4096 output cap; deliberately conservative",
                "cache_miss_input_plus_max_output_usd": conservative_context_cost,
                "recommended_rounded_hard_cost_cap_usd": recommended_usd_cap,
            },
            "actual_cost_usd": None,
            "actual_cost_status": "no API call made; exact billing requires response usage",
            "recheck_official_price_before_run": True,
        },
        "authorization": {
            "real_api_calls_made": 0,
            "real_api_calls_authorized": False,
            "pending": ["explicit total input-token cap", "explicit total USD cap", "exact user API authorization"],
            "recommended_hard_limits": {
                "max_calls": planned_calls,
                "max_request_body_utf8_bytes_per_call": body_max,
                "max_request_body_utf8_bytes_total": body_total,
                "max_billed_input_tokens_total": context_input_cap,
                "max_output_tokens_per_call": 4096,
                "max_output_tokens_total": output_cap,
                "max_cost_usd": recommended_usd_cap,
                "retry_count": 0,
            },
            "hard_stops": lock["hard_stops"],
        },
        "safety": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "raw_payload_or_source_text_committed": False,
            "gold_rule_records_created": False,
            "oracle_started": False,
        },
        "reproduce_command": (
            "python formal_experiment/scripts/build_s2_12_api_preflight_v1.py "
            "--runtime-home D:/environment/stanford-corenlp-4.5.10 "
            "--tokenizer-snapshot <local-nlpaueb-legal-bert-snapshot> --check"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-home", type=Path, required=True)
    parser.add_argument("--tokenizer-snapshot", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        report = build(args.runtime_home, args.tokenizer_snapshot)
        payload = _json_bytes(report)
        if args.publish:
            if OUTPUT.exists():
                raise PreflightFail(f"refusing to overwrite existing report: {OUTPUT}")
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=OUTPUT.parent, delete=False) as stream:
                stage = Path(stream.name)
                stream.write(payload)
            try:
                stage.replace(OUTPUT)
            except Exception:
                stage.unlink(missing_ok=True)
                raise
        else:
            if not OUTPUT.is_file() or OUTPUT.read_bytes() != payload:
                raise PreflightFail("published preflight report differs from replay")
    except (OSError, ValueError) as exc:
        print(f"S2.12 API preflight refused: {exc}")
        return 2
    print("S2.12 API preflight verified; zero API calls")
    print(
        f"calls={report['global']['planned_calls']} "
        f"body_bytes={report['global']['request_body_utf8_bytes']['total']} "
        f"proxy_tokens={report['global']['local_proxy_tokens']['total']}"
    )
    print(
        "official_deepseek_input_tokens=unavailable_until_response_usage "
        f"recommended_absolute_cost_cap_usd="
        f"{report['authorization']['recommended_hard_limits']['max_cost_usd']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
