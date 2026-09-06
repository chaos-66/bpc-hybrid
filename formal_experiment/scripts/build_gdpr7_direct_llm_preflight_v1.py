# -*- coding: utf-8 -*-
"""Build the GDPR Stage-2 sentence Direct-LLM API preflight (74 requests, zero API).

Purpose
-------
Render one frozen request per sentence of the Gold-blind GDPR Stage-2 input
pack ``data/input/gdpr7_stage2_input_v1.json`` (9 GDPR rule texts / 74
sentences, ``approved_text_en`` per sentence) using the SAME locked D1 recipe
that the S2.12 ``direct_llm`` arm uses:

* prompt ``direct_llm_sun_record_prompt_v6_d1r1_2026_08_05`` (SHA-256
  3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895) loaded via
  ``bpc_hybrid.prompt_loader``; the sentence text is the full
  ``approved_text_en`` of one sentence record and the envelope is the same
  single-text D1 envelope (``sample_id``/``source_id``/``source_text`` +
  ``few_shot_block``) that processes one sentence record per call;
* model ``deepseek-v4-pro`` (published alias ``DeepSeek-V4-Pro-0813``),
  temperature 0, top_p 1, max_tokens 4096, seed unsupported/omitted;
* transport: stream=False, thinking={"type": "disabled"},
  response_format=None (no json_object), no tools.

The report ``outputs/reports/gdpr7_direct_llm_preflight_v1.json`` mirrors the
structure and the budget formulas of the S2.12 API preflight
(``outputs/reports/s2_12_api_preflight_v1.json``):

* per-request body byte size = UTF-8 length of the final body serialized by
  default ``json.dumps`` (the exact convention of the S2.12 payload lock);
* estimated input tokens = local Legal-BERT WordPiece **proxy** count over
  ``system_prompt + "\\n" + user_prompt`` (``add_special_tokens=True``),
  clearly labelled a planning proxy, never a billing count (the official
  deepseek-v4-pro tokenizer is not available locally);
* input-token hard cap = calls x official 1M context per call =
  74 x 1,000,000 = 74,000,000 (same conservative caps formula as the S2.12
  63 x 1,000,000 = 63,000,000 bound);
* output cap = 74 x 4,096 = 303,104 (4096 per call);
* USD caps use the SAME official peak price the S2.12 v3 request used
  (input cache-miss 1.32 USD/M, output 3.96 USD/M -- see
  ``docs/API_AUTHORIZATION_REQUEST.md`` section 3) plus a 1.2x (20%) safety
  margin, consistent with earlier repo budget practice
  (``scripts/run_barrientos_paper_ablation_v1.py`` and
  ``scripts/build_d1_prompt_factorial_contract_v1.py``).

Zero LLM/API/network/.env.  No Gold is read.  Only hashes, byte sizes and
local proxy-token counts are committed (no raw sentence text, no prompt
text).  ``authorized: false`` and ``calls_made: 0`` are recorded: this
preparation creates NO authorization file and NO call is made until the user
authorizes a real batch.

Modes (like the S2.12 preflight builder):

* ``--publish`` writes the report; refuses to overwrite unless ``--overwrite``.
* ``--check`` recomputes the report from scratch and byte-compares it with the
  previously written file (fails closed on any drift).
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

from bpc_hybrid.h1_transport import H1RequestPolicy  # noqa: E402
from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder  # noqa: E402
from bpc_hybrid.llm_config import LLMConfig  # noqa: E402
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from run_direct_llm import _few_shot_block  # noqa: E402

INPUT = ROOT / "data/input/gdpr7_stage2_input_v1.json"
OUTPUT = ROOT / "outputs/reports/gdpr7_direct_llm_preflight_v1.json"

SCHEMA_VERSION = "gdpr7_direct_llm_preflight_report@1.0.0"
DATASET_ID = "gdpr7_stage2_sentences_v1"

EXPECTED_INPUT_SHA256 = "558b80131394c8ac349db42cc323ffcf7264b7ae7da796522d55bf5ff89eb109"
EXPECTED_SENTENCE_COUNT = 74
EXPECTED_RULE_COUNT = 9
EXPECTED_RULES = frozenset({
    "article6", "article7", "article15", "article16", "article17",
    "article20", "article22", "article33", "article34",
})

PROMPT_NAME = "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05"
EXPECTED_PROMPT_SHA256 = (
    "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"
)
REGISTRY = ROOT / "configs/models/estg150_d1_active_registry_v1.json"
EXPECTED_REGISTRY_SHA256 = (
    "31f3358d089611b85a4a50d36444a4c59f6d965abbf0b8770aeb73db13642749"
)

REQUIRED_MODEL = "deepseek-v4-pro"
PUBLISHED_ALIAS = "DeepSeek-V4-Pro-0813"
BASE_URL = "https://api.deepseek.com/v1"
MAX_OUTPUT_TOKENS_PER_CALL = 4096
# Mirror of the S2.12 preflight lock: official context per call used for the
# conservative input-token cap (``configs/s2_12_api_arms_preflight_v1.json``
# ``pricing.official_context_tokens_per_call`` = 1,000,000).
OFFICIAL_CONTEXT_TOKENS_PER_CALL = 1_000_000
SAFETY_MARGIN = 1.2

# USD per 1M tokens -- official 2026-08-19/20 peak prices recorded in
# ``docs/API_AUTHORIZATION_REQUEST.md`` section 3 (the S2.12 v3 request);
# verified again by the repo's own 2026-09-05 budget note in
# ``scripts/run_barrientos_paper_ablation_v1.py``.
PRICE_PEAK_PER_MILLION = {
    "input_cache_hit": 0.044,
    "input_cache_miss": 1.32,
    "output": 3.96,
}
# docs/API_AUTHORIZATION_REQUEST.md documents the off-peak alternative as half
# of the peak prices (input cache-miss 0.66, output 1.98 USD/M).
PRICE_OFF_PEAK_PER_MILLION = {
    "input_cache_hit": 0.022,
    "input_cache_miss": 0.66,
    "output": 1.98,
}
PRICING_URL = "https://api-docs.deepseek.com/quick_start/pricing/"

# Local Legal-BERT planning proxy (same model/revision/files as the S2.12
# preflight lock's ``local_tokenizer_proxy`` section).
TOKENIZER_PROXY = {
    "model_id": "nlpaueb/legal-bert-base-uncased",
    "revision": "15b570cbf88259610b082a167dacc190124f60f6",
    "kind": "Bert WordPiece local planning proxy",
    "is_deepseek_tokenizer": False,
    "is_billing_token_count": False,
    "add_special_tokens": True,
    "truncation": False,
    "file_sha256": {
        "vocab.txt": "3aaa02f2e3a397eee0f813caa567c87cddab1045a4a6b8ac6261f0cc799efb8f",
        "tokenizer_config.json": "a025160ef0431f1a392f6f050c1310f4c5d9fb6f275932dbccba73c4d214bf10",
        "special_tokens_map.json": "303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3",
        "config.json": "716ea70c3c3e74bfe8496cc04cba7cd52f4ca45401e74042bb1058fe0390a1b6",
    },
}
# Candidate local snapshot paths tried when --tokenizer-snapshot is omitted.
_TOKENIZER_SNAPSHOT_CANDIDATES = (
    Path.home() / ".cache" / "huggingface" / "hub"
    / "models--nlpaueb--legal-bert-base-uncased"
    / "snapshots" / TOKENIZER_PROXY["revision"],
    ROOT / ".tmp" / "nlpaueb-legal-bert-base-uncased-snapshot",
)

# Beijing-time peak window (UTC+8) used by the S2.12 execution contract;
# weekends are entirely off-peak.
PEAK_WINDOW_NOTE = (
    "off-peak-only: Beijing peak 09:00-12:00 and 14:00-18:00 (UTC+8) on "
    "Monday-Friday; weekends are entirely off-peak. Every call must check the "
    "window before sending (same discipline as the S2.12 executor)."
)

# Undesired keys that must never appear in the committed report.
_FORBIDDEN_TEXT_KEYS = ("text", "source_text", "approved_text_en", "normalized")


class PreflightFail(ValueError):
    """Fail-closed GDPR Direct-LLM preflight error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_text(value: str) -> str:
    return _sha_bytes(value.encode("utf-8"))


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _FORBIDDEN_TEXT_KEYS:
                return True
            if _contains_forbidden(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden(child) for child in value)
    return False


def _summary(values: Sequence[int]) -> dict[str, int]:
    if not values:
        return {"minimum": 0, "maximum": 0, "total": 0}
    return {"minimum": min(values), "maximum": max(values), "total": sum(values)}


def _usd_cap(
    input_tokens: int,
    output_tokens: int,
    price_miss: float,
    price_out: float,
    margin: float = SAFETY_MARGIN,
    decimals: int = 2,
) -> float:
    """Round-up USD cap at cache-miss peak/off-peak price plus the margin.

    Formula reused from ``run_barrientos_paper_ablation_v1.py`` and
    ``build_d1_prompt_factorial_contract_v1.py``:
    ceil((input*P_miss + output*P_out)/1e6 * margin * 10**d) / 10**d.
    """
    raw = (input_tokens * price_miss + output_tokens * price_out) / 1_000_000
    scale = 10 ** decimals
    return math.ceil(raw * margin * scale) / scale


# ---------------------------------------------------------------------------
# Fail-closed input / recipe verification
# ---------------------------------------------------------------------------


def _resolve_sentences(input_doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    if input_doc.get("schema_version") != "gdpr7_stage2_input@1.0.0":
        raise PreflightFail("GDPR Stage-2 input schema identity drift")
    if input_doc.get("gold_visible") is not False:
        raise PreflightFail("GDPR Stage-2 input must be Gold-blind")
    rules = input_doc.get("rules") or []
    if {r.get("rule_id") for r in rules} != set(EXPECTED_RULES):
        raise PreflightFail("GDPR Stage-2 input rule set drift")
    sentences: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rule in rules:
        rule_id = rule.get("rule_id")
        for s in rule.get("sentences") or []:
            sample_id = s.get("sample_id")
            text = s.get("approved_text_en")
            if not isinstance(sample_id, str) or sample_id in seen:
                raise PreflightFail("sentence sample IDs missing or duplicated")
            if not isinstance(text, str) or not text.strip():
                raise PreflightFail(f"empty sentence text: {sample_id}")
            if _sha_text(text) != s.get("text_sha256"):
                raise PreflightFail(f"sentence text hash drift: {sample_id}")
            seen.add(sample_id)
            sentences.append({
                "sample_id": sample_id,
                "rule_id": str(rule_id),
                "sentence_idx": int(s["sentence_idx"]),
                "char_span": [int(s["char_span"][0]), int(s["char_span"][1])],
                "text_sha256": s["text_sha256"],
                "approved_text_en": text,
            })
    if len(sentences) != EXPECTED_SENTENCE_COUNT:
        raise PreflightFail(
            f"expected {EXPECTED_SENTENCE_COUNT} sentences, got {len(sentences)}"
        )
    return sentences


def _verify_registry() -> dict[str, Any]:
    if not REGISTRY.is_file() or _sha(REGISTRY) != EXPECTED_REGISTRY_SHA256:
        raise PreflightFail("D1 active registry drift")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    recipe = registry.get("recipe_lock") or {}
    prompt = recipe.get("prompt") or {}
    model = recipe.get("model") or {}
    sampling = recipe.get("sampling") or {}
    transport = recipe.get("transport") or {}
    if model.get("id") != REQUIRED_MODEL:
        raise PreflightFail(f"registry model {model.get('id')!r} != {REQUIRED_MODEL!r}")
    if prompt.get("name") != PROMPT_NAME or prompt.get("sha256") != EXPECTED_PROMPT_SHA256:
        raise PreflightFail("registry prompt binding drift")
    if float(sampling.get("temperature", -1)) != 0.0:
        raise PreflightFail("registry temperature drift")
    if float(sampling.get("top_p", -1)) != 1.0:
        raise PreflightFail("registry top_p drift")
    if int(sampling.get("max_tokens", -1)) != MAX_OUTPUT_TOKENS_PER_CALL:
        raise PreflightFail("registry max_tokens drift")
    if transport.get("stream") is not False:
        raise PreflightFail("registry transport stream drift")
    if (transport.get("thinking") or {}).get("type") != "disabled":
        raise PreflightFail("registry transport thinking drift")
    if transport.get("response_format") is not None:
        raise PreflightFail("registry transport response_format drift")
    return dict(registry)


def _default_tokenizer_snapshot() -> Path:
    for candidate in _TOKENIZER_SNAPSHOT_CANDIDATES:
        if candidate.is_dir():
            return candidate
    raise PreflightFail(
        "no local Legal-BERT proxy snapshot found; pass --tokenizer-snapshot "
        f"(expected revision {TOKENIZER_PROXY['revision']})"
    )


def _load_proxy_tokenizer(snapshot: Path) -> Any:
    for name, expected in TOKENIZER_PROXY["file_sha256"].items():
        path = snapshot / name
        if not path.is_file() or _sha(path) != expected:
            raise PreflightFail(f"local tokenizer proxy binding drift: {name}")
    try:
        from tokenizers import BertWordPieceTokenizer
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise PreflightFail(
            "tokenizers is unavailable for local proxy counts"
        ) from exc
    return BertWordPieceTokenizer(str(snapshot / "vocab.txt"), lowercase=True)


# ---------------------------------------------------------------------------
# Report construction
# ---------------------------------------------------------------------------


def _config() -> LLMConfig:
    return LLMConfig(
        enabled=False,
        provider="openai_compatible",
        model=REQUIRED_MODEL,
        api_key=None,
        base_url=BASE_URL,
        max_tokens=MAX_OUTPUT_TOKENS_PER_CALL,
        temperature=0.0,
        top_p=1.0,
        seed=None,
        seed_supported=False,
    )


def _policy() -> H1RequestPolicy:
    return H1RequestPolicy(
        stream=False, thinking={"type": "disabled"}, response_format=None
    )


def _call_row(
    *,
    index: int,
    sentence: Mapping[str, Any],
    prompt: Any,
    few_shot: str,
    builder: OpenAICompatibleRequestBuilder,
    policy: H1RequestPolicy,
    tokenizer: Any,
) -> dict[str, Any]:
    text = sentence["approved_text_en"]
    sample_id = sentence["sample_id"]
    user_prompt = prompt.user_prompt_template.format(
        sample_id=sample_id,
        source_id=sample_id,
        source_text=text,
        few_shot_block=few_shot,
    )
    body = policy.apply_to_body(builder.build_body(prompt.system_prompt, user_prompt))
    # Exact convention of the S2.12 payload lock: default json.dumps, UTF-8.
    body_bytes = json.dumps(body).encode("utf-8")
    proxy_input = prompt.system_prompt + "\n" + user_prompt
    proxy_tokens = len(
        tokenizer.encode(proxy_input, add_special_tokens=True).ids
    )
    return {
        "call_index": index,
        "sample_id": sample_id,
        "rule_id": sentence["rule_id"],
        "sentence_idx": sentence["sentence_idx"],
        "clause_id": None,
        "sentence_text_sha256": sentence["text_sha256"],
        "sentence_text_utf8_bytes": len(text.encode("utf-8")),
        "request_body_sha256": _sha_bytes(body_bytes),
        "request_body_utf8_bytes": len(body_bytes),
        "system_prompt_utf8_bytes": len(prompt.system_prompt.encode("utf-8")),
        "user_prompt_utf8_bytes": len(user_prompt.encode("utf-8")),
        "local_proxy_tokens": proxy_tokens,
    }


def _implementation_bindings() -> dict[str, str]:
    prompt_path = ROOT / "prompts" / "sun_compat" / f"{PROMPT_NAME}.md"
    return {
        "scripts/build_gdpr7_direct_llm_preflight_v1.py": _sha(Path(__file__).resolve()),
        "src/bpc_hybrid/prompt_loader.py": _sha(ROOT / "src/bpc_hybrid/prompt_loader.py"),
        "src/bpc_hybrid/llm_client.py": _sha(ROOT / "src/bpc_hybrid/llm_client.py"),
        "src/bpc_hybrid/h1_transport.py": _sha(ROOT / "src/bpc_hybrid/h1_transport.py"),
        "src/bpc_hybrid/llm_config.py": _sha(ROOT / "src/bpc_hybrid/llm_config.py"),
        "scripts/run_direct_llm.py": _sha(ROOT / "scripts/run_direct_llm.py"),
        "configs/models/estg150_d1_active_registry_v1.json": EXPECTED_REGISTRY_SHA256,
        "prompts/sun_compat/direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md": EXPECTED_PROMPT_SHA256,
    }


def build(tokenizer: Any) -> dict[str, Any]:
    """Build the full preflight report dict (no file writes)."""
    input_doc = json.loads(INPUT.read_text(encoding="utf-8"))
    if _sha(INPUT) != EXPECTED_INPUT_SHA256:
        raise PreflightFail("GDPR Stage-2 input drift")
    if input_doc.get("counts") != {"rules": EXPECTED_RULE_COUNT,
                                   "sentences": EXPECTED_SENTENCE_COUNT}:
        raise PreflightFail("GDPR Stage-2 input counts drift")
    sentences = _resolve_sentences(input_doc)
    _verify_registry()
    prompt = load_prompt(PROMPT_NAME)
    if prompt.sha256 != EXPECTED_PROMPT_SHA256:
        raise PreflightFail("D1 direct prompt drift")
    few_shot = _few_shot_block(prompt)
    config = _config()
    builder = OpenAICompatibleRequestBuilder(config)
    policy = _policy()

    calls: list[dict[str, Any]] = []
    for index, sentence in enumerate(sentences, 1):
        calls.append(_call_row(
            index=index,
            sentence=sentence,
            prompt=prompt,
            few_shot=few_shot,
            builder=builder,
            policy=policy,
            tokenizer=tokenizer,
        ))
    if len(calls) != EXPECTED_SENTENCE_COUNT:
        raise PreflightFail(f"rendered {len(calls)} != {EXPECTED_SENTENCE_COUNT}")

    body_bytes = [row["request_body_utf8_bytes"] for row in calls]
    proxy_tokens = [row["local_proxy_tokens"] for row in calls]
    output_tokens = EXPECTED_SENTENCE_COUNT * MAX_OUTPUT_TOKENS_PER_CALL
    input_context_cap = EXPECTED_SENTENCE_COUNT * OFFICIAL_CONTEXT_TOKENS_PER_CALL

    # Same empirical planning upper bound documented in the S2.12 API
    # authorization request section 6: max(2 x proxy, bytes / 1.8).
    planning_bound = max(
        2 * sum(proxy_tokens),
        int(math.ceil(sum(body_bytes) / 1.8)),
    )
    # USD caps at the official PEAK price of the S2.12 v3 request, plus the
    # repo's 20% (1.2x) safety margin.
    recommended_usd_cap = _usd_cap(
        planning_bound, output_tokens,
        PRICE_PEAK_PER_MILLION["input_cache_miss"],
        PRICE_PEAK_PER_MILLION["output"],
    )
    recommended_usd_cap_off_peak = _usd_cap(
        planning_bound, output_tokens,
        PRICE_OFF_PEAK_PER_MILLION["input_cache_miss"],
        PRICE_OFF_PEAK_PER_MILLION["output"],
    )
    peak_planning_usd = (
        planning_bound * PRICE_PEAK_PER_MILLION["input_cache_miss"]
        + output_tokens * PRICE_PEAK_PER_MILLION["output"]
    ) / 1_000_000
    absolute_bound_usd = (
        input_context_cap * PRICE_PEAK_PER_MILLION["input_cache_miss"]
        + output_tokens * PRICE_PEAK_PER_MILLION["output"]
    ) / 1_000_000

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "payloads_locked_zero_api_authorization_pending",
        "dataset_id": DATASET_ID,
        "task": (
            "GDPR Stage-2 -> Stage-3 linkage, Direct-LLM arm only "
            "(direct_llm vs rules_only pairing); one request per sentence"
        ),
        "preflight_lock": {
            "created": False,
            "note": (
                "this preparation creates no config lock file; model/prompt/"
                "input/sampling bindings are recorded inline and bound by hash"
            ),
        },
        "input": {
            "path": "data/input/gdpr7_stage2_input_v1.json",
            "sha256": EXPECTED_INPUT_SHA256,
            "records": EXPECTED_SENTENCE_COUNT,
            "rules": EXPECTED_RULE_COUNT,
            "gold_visible": False,
            "raw_text_committed": False,
            "sentences_per_rule": {
                rule_id: sum(1 for s in sentences if s["rule_id"] == rule_id)
                for rule_id in sorted(EXPECTED_RULES)
            },
        },
        "model": {
            "provider": "openai_compatible",
            "base_url": BASE_URL,
            "id": REQUIRED_MODEL,
            "published_alias": PUBLISHED_ALIAS,
            "fail_closed": True,
            "recipe_registry": {
                "path": "configs/models/estg150_d1_active_registry_v1.json",
                "sha256": EXPECTED_REGISTRY_SHA256,
            },
            "prompt": {
                "name": PROMPT_NAME,
                "path": _rel(ROOT / "prompts" / "sun_compat" / f"{PROMPT_NAME}.md"),
                "sha256": prompt.sha256,
                "few_shot_example_count": len(prompt.few_shot_examples),
            },
            "common_sampling": {
                "temperature": 0.0,
                "top_p": 1.0,
                "max_output_tokens_per_call": MAX_OUTPUT_TOKENS_PER_CALL,
                "seed": None,
                "seed_supported": False,
                "retry_count": 0,
            },
            "transport_policy": policy.to_dict(),
            "implementation_bindings": _implementation_bindings(),
        },
        "gold_isolation": {
            "preflight_reads_gold": False,
            "preflight_reads_decisions": False,
            "preflight_reads_proposals": False,
            "api_arms_must_not_read_gold": True,
            "evaluation_only_after_predictions_are_locked": True,
            "no_real_d1_response_exists_for_gdpr_sentences": True,
        },
        "token_measurement": {
            "exact_measurement": "final request body serialized by default json.dumps then UTF-8",
            "official_deepseek_v4_pro_tokenizer_available_locally": False,
            "official_billing_input_tokens": None,
            "official_billing_input_tokens_status": (
                "available only from response usage after a real call"
            ),
            "estimation_formula": (
                "per-call local Legal-BERT WordPiece proxy count over "
                "system_prompt + '\\n' + user_prompt with add_special_tokens=True; "
                "planning proxy only, NOT a billing count"
            ),
            "local_proxy": {
                "model_id": TOKENIZER_PROXY["model_id"],
                "revision": TOKENIZER_PROXY["revision"],
                "kind": TOKENIZER_PROXY["kind"],
                "is_deepseek_tokenizer": False,
                "is_billing_token_count": False,
                "add_special_tokens": True,
                "truncation": False,
                "local_snapshot_used": True,
            },
        },
        "arms": {
            "direct_llm": {
                "prompt_name": PROMPT_NAME,
                "prompt_sha256": prompt.sha256,
                "transport_policy": policy.to_dict(),
                "planned_calls": EXPECTED_SENTENCE_COUNT,
                "max_calls": EXPECTED_SENTENCE_COUNT,
                "max_output_tokens_per_call": MAX_OUTPUT_TOKENS_PER_CALL,
                "max_output_tokens_total": output_tokens,
                "retry_count": 0,
                "request_body_utf8_bytes": _summary(body_bytes),
                "local_proxy_tokens": _summary(proxy_tokens),
                "calls": calls,
            }
        },
        "global": {
            "planned_calls": EXPECTED_SENTENCE_COUNT,
            "retry_count": 0,
            "request_body_utf8_bytes": {
                "maximum_per_call": max(body_bytes),
                "total": sum(body_bytes),
            },
            "local_proxy_tokens": {
                "maximum_per_call": max(proxy_tokens),
                "total": sum(proxy_tokens),
            },
            "max_output_tokens_per_call": MAX_OUTPUT_TOKENS_PER_CALL,
            "max_output_tokens_total": output_tokens,
            "max_billed_input_tokens_total": input_context_cap,
        },
        "pricing": {
            "currency": "USD",
            "checked_reference": (
                "same official peak price used by the S2.12 v3 request "
                "(docs/API_AUTHORIZATION_REQUEST.md section 3); repo budget note "
                "verified_date 2026-09-05 in run_barrientos_paper_ablation_v1.py"
            ),
            "official_source": PRICING_URL,
            "peak_price_per_million_tokens": PRICE_PEAK_PER_MILLION,
            "off_peak_documented_half_of_peak": PRICE_OFF_PEAK_PER_MILLION,
            "proxy_based_planning_only_not_billable_exact": {
                "planning_upper_bound_input_tokens": planning_bound,
                "planning_formula": "max(2 x local_proxy_tokens_total, request_body_utf8_bytes_total / 1.8)",
                "cache_miss_input_plus_max_output_peak_usd": round(peak_planning_usd, 8),
                "max_output_usd": round(
                    output_tokens * PRICE_PEAK_PER_MILLION["output"] / 1_000_000, 8),
            },
            "official_context_derived_absolute_bound": {
                "input_tokens": input_context_cap,
                "assumption": (
                    "each planned call consumes the full official 1M context as "
                    "cache-miss input, plus the configured 4096 output cap; "
                    "deliberately conservative (mirrors S2.12 63M / US$84.18 structure)"
                ),
                "cache_miss_input_plus_max_output_peak_usd": round(absolute_bound_usd, 8),
            },
            "recommended_usd_cap_with_1_2_safety_margin": {
                "margin": SAFETY_MARGIN,
                "formula": (
                    "ceil((planning_upper_bound_input_tokens x input_cache_miss_peak"
                    " + max_output_tokens_total x output_peak) / 1e6 x 1.2 x 100) / 100"
                ),
                "peak_price_usd": recommended_usd_cap,
                "off_peak_price_usd": recommended_usd_cap_off_peak,
                "prior_practice_refs": [
                    "scripts/run_barrientos_paper_ablation_v1.py (20% USD margin)",
                    "scripts/build_d1_prompt_factorial_contract_v1.py (usd_cap = ceil(peak_cost x 1.2))",
                ],
            },
            "actual_cost_usd": None,
            "actual_cost_status": "no API call made; exact billing requires response usage",
            "recheck_official_price_before_run": True,
        },
        "authorization": {
            "authorized": False,
            "calls_made": 0,
            "real_api_calls_made": 0,
            "real_api_calls_authorized": False,
            "pending": [
                "explicit total input-token cap",
                "explicit total USD cap",
                "exact user API authorization (no authorization file is created by this preparation)",
            ],
            "off_peak_only_note": PEAK_WINDOW_NOTE,
            "recommended_hard_limits": {
                "max_calls": EXPECTED_SENTENCE_COUNT,
                "max_request_body_utf8_bytes_per_call": max(body_bytes),
                "max_request_body_utf8_bytes_total": sum(body_bytes),
                "max_billed_input_tokens_total": input_context_cap,
                "max_output_tokens_per_call": MAX_OUTPUT_TOKENS_PER_CALL,
                "max_output_tokens_total": output_tokens,
                "max_cost_usd": recommended_usd_cap,
                "max_cost_usd_off_peak_alternative": recommended_usd_cap_off_peak,
                "retry_count": 0,
            },
            "template_sentence_placeholder": {
                "is_placeholder_not_authorization": True,
                "authorized": False,
                "calls_made": 0,
                "note": (
                    "user must issue the authorization sentence verbatim and an "
                    "authorization file must be created separately before any real "
                    "call; this report only prepares the locked payloads and caps"
                ),
                "template_zh": (
                    "我授权在 GDPR Stage-2→Stage-3 衔接的 Direct-LLM 臂上，对 "
                    "gdpr7_stage2_input_v1.json 的 74 个 approved_text_en 句子"
                    "（hash 558b8013…）每句调用 1 次 deepseek-v4-pro 真实 API，"
                    "共 74 次、retry=0、off-peak only（北京时间 09:00–12:00 / "
                    "14:00–18:00 之外，每次调用前检查）；输入仅限 "
                    "gdpr7_direct_llm_preflight_v1.json 锁定的 74 个请求体；"
                    "global input ≤74,000,000、output ≤303,104、USD ≤2.61"
                    "（peak 规划价 +20% margin；off-peak 折半 ≤1.31）；"
                    "运行前重验官方价格；任一 drift/cap/时段/Gold 隔离违背 → "
                    "调用前硬停止；不读取 .env、不调用 Oracle。"
                ),
                "template_en": (
                    "I authorize running the GDPR Stage-2->Stage-3 linkage "
                    "Direct-LLM arm: 74 real deepseek-v4-pro API calls (one per "
                    "approved_text_en sentence of gdpr7_stage2_input_v1.json, "
                    "sha256 558b8013…), retry=0, off-peak only (outside Beijing "
                    "09:00-12:00 / 14:00-18:00, checked before every call); input "
                    "text limited to the 74 locked request bodies of "
                    "gdpr7_direct_llm_preflight_v1.json; global input <=74,000,000, "
                    "output <=303,104, USD <=2.61 (peak planning price +20% margin; "
                    "off-peak half-price alternative <=1.31); official prices "
                    "re-verified before the run; any drift/cap/window/Gold-isolation "
                    "violation hard-stops before the call; no .env read, no Oracle."
                ),
            },
        },
        "safety": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "raw_payload_or_source_text_committed": False,
            "gold_rule_records_created": False,
            "oracle_started": False,
        },
        "reproduce_command": (
            "python formal_experiment/scripts/build_gdpr7_direct_llm_preflight_v1.py "
            "--tokenizer-snapshot <local-nlpaueb-legal-bert-snapshot> --check"
        ),
    }
    if _contains_forbidden(report):
        raise PreflightFail("raw text leaked into committed preflight report")
    return report


def publish(payload: bytes, output: Path = OUTPUT, overwrite: bool = False) -> None:
    """Atomically write the report payload; refuse an existing file unless
    ``overwrite`` is set (mirrors the S2.12 preflight builder's guard)."""
    if output.exists() and not overwrite:
        raise PreflightFail(
            f"refusing to overwrite existing report (use --overwrite): {output}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as stream:
        stage = Path(stream.name)
        stream.write(payload)
    try:
        stage.replace(output)
    except Exception:
        stage.unlink(missing_ok=True)
        raise


def check(payload: bytes, output: Path = OUTPUT) -> None:
    """Byte-compare ``payload`` with the previously published report; fail
    closed when the file is missing or drifts."""
    if not output.is_file():
        raise PreflightFail(f"no published report to check: {output}")
    if output.read_bytes() != payload:
        raise PreflightFail(
            "recomputed preflight report differs from the published file"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tokenizer-snapshot", type=Path, default=None,
        help="Directory containing the local nlpaueb/legal-bert proxy files "
             "(defaults to the HuggingFace cache snapshot when present).",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Allow --publish to replace an existing report.",
    )
    args = parser.parse_args()

    try:
        snapshot = args.tokenizer_snapshot or _default_tokenizer_snapshot()
        tokenizer = _load_proxy_tokenizer(snapshot)
        report = build(tokenizer)
        payload = _json_bytes(report)
        if args.check:
            check(payload)
        else:  # --publish
            publish(payload, overwrite=args.overwrite)
    except (OSError, ValueError) as exc:
        print(f"GDPR Direct-LLM preflight refused: {exc}")
        return 2

    global_ = report["global"]
    auth = report["authorization"]["recommended_hard_limits"]
    print("GDPR Direct-LLM preflight verified; zero API calls")
    print(
        f"calls={global_['planned_calls']} "
        f"body_bytes={global_['request_body_utf8_bytes']['total']} "
        f"proxy_tokens={global_['local_proxy_tokens']['total']}"
    )
    print(
        f"output_cap={global_['max_output_tokens_total']} "
        f"input_cap={global_['max_billed_input_tokens_total']} "
        f"recommended_usd_cap={auth['max_cost_usd']} "
        f"(off-peak alt {auth['max_cost_usd_off_peak_alternative']}) "
        f"authorized=false calls_made=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
