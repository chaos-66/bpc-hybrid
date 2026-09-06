# -*- coding: utf-8 -*-
"""Focused tests for the GDPR Direct-LLM preflight builder.

Verifies, fully offline with zero API/network:
- exactly 74 locked requests are rendered, one per sentence of
  ``data/input/gdpr7_stage2_input_v1.json``, in deterministic pack order;
- every request embeds that sentence's ``approved_text_en`` bytes (bound by
  SHA-256 against the pack's own per-sentence hash and by re-render equality
  with the committed ``request_body_sha256``) and contains no gold/panel
  label material;
- deterministic rebuild equality (two in-process builds are byte-identical);
- the publish guard refuses to overwrite an existing report without
  ``--overwrite`` and ``--check`` fails closed on drift;
- caps are finite and cover the rendered estimates (output 74 x 4,096,
  input 74 x 1M context bound, USD cap >= planning peak cost);
- no transport/network import path executes (static AST scan + guarded
  subprocess run that blocks real HTTP modules at import time).
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import build_gdpr7_direct_llm_preflight_v1 as pre  # noqa: E402
from bpc_hybrid.h1_transport import H1RequestPolicy  # noqa: E402
from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder  # noqa: E402
from bpc_hybrid.llm_config import LLMConfig  # noqa: E402
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from run_direct_llm import _few_shot_block  # noqa: E402

INPUT = pre.INPUT
OUTPUT = pre.OUTPUT
EXPECTED_COUNT = pre.EXPECTED_SENTENCE_COUNT

# Gold / panel-label machinery that must never reach a rendered request.
_FORBIDDEN_LABEL_TERMS = (
    "gold", "expected_violation", "check_type", "mutation",
    "variant_id", "human_correction", "adjudicat", "gold_rule",
)
# Real transport / network imports that must never be executed.
_NETWORK_HTTP_CLIENT_ROOTS = {
    "urllib", "requests", "httpx", "http", "openai", "aiohttp", "boto3",
}
# Broader deny set used for the static source/AST scan of the preflight module
# itself (stdlib ``socket``/``urllib`` imports inside the shared llm_client are
# used only for URL parsing, never for I/O, but the preflight module must not
# import them either).
_FORBIDDEN_IMPORT_ROOTS = _NETWORK_HTTP_CLIENT_ROOTS | {"socket"}
_FORBIDDEN_TRANSPORT_NAMES = {"RealAPITransport", "PayloadLockedRealTransport"}


class _Encoding:
    def __init__(self, n: int) -> None:
        self.ids = list(range(1, n + 1))


class _FakeTokenizer:
    """Deterministic stand-in for the Legal-BERT proxy (count-only)."""

    def encode(self, text: str, add_special_tokens: bool = True) -> _Encoding:
        return _Encoding(len(text))


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pack_sentences() -> dict[str, dict]:
    doc = json.loads(INPUT.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for rule in doc["rules"]:
        for sentence in rule["sentences"]:
            entry = dict(sentence)
            entry["rule_id"] = rule["rule_id"]
            out[sentence["sample_id"]] = entry
    return out


def _render_bodies() -> list[tuple[str, bytes, int, str]]:
    """Re-render final bodies exactly as the builder does (no tokenizer).

    Returns ``(sample_id, body_bytes, body_bytes_len, user_prompt)`` in pack
    order.  Body bytes do not depend on the tokenizer, so this reproduces the
    committed ``request_body_sha256`` values exactly.
    """
    prompt = load_prompt(pre.PROMPT_NAME)
    if prompt.sha256 != pre.EXPECTED_PROMPT_SHA256:
        raise AssertionError("prompt drift while re-rendering test bodies")
    few_shot = _few_shot_block(prompt)
    config = LLMConfig(
        enabled=False, provider="openai_compatible", model=pre.REQUIRED_MODEL,
        api_key=None, base_url=pre.BASE_URL, max_tokens=pre.MAX_OUTPUT_TOKENS_PER_CALL,
        temperature=0.0, top_p=1.0, seed=None, seed_supported=False,
    )
    builder = OpenAICompatibleRequestBuilder(config)
    policy = H1RequestPolicy(
        stream=False, thinking={"type": "disabled"}, response_format=None
    )
    sentences = _pack_sentences()
    rows: list[tuple[str, bytes, int, str]] = []
    # Preserve pack order exactly like the builder (flatten rules in order).
    doc = json.loads(INPUT.read_text(encoding="utf-8"))
    for rule in doc["rules"]:
        for sentence in rule["sentences"]:
            sample_id = sentence["sample_id"]
            user_prompt = prompt.user_prompt_template.format(
                sample_id=sample_id,
                source_id=sample_id,
                source_text=sentence["approved_text_en"],
                few_shot_block=few_shot,
            )
            body = policy.apply_to_body(
                builder.build_body(prompt.system_prompt, user_prompt)
            )
            body_bytes = json.dumps(body).encode("utf-8")
            rows.append((sample_id, body_bytes, len(body_bytes), user_prompt))
    return rows


# ---------------------------------------------------------------------------
# Rendering: count, order, sentence-text bytes, gold blindness
# ---------------------------------------------------------------------------


def test_renders_exactly_74_requests_in_pack_order() -> None:
    report = pre.build(_FakeTokenizer())
    calls = report["arms"]["direct_llm"]["calls"]
    assert len(calls) == EXPECTED_COUNT == 74
    sentences = _pack_sentences()
    assert len(sentences) == 74
    # The 74 sample_ids equal the pack's sentence set exactly once each.
    assert [row["sample_id"] for row in calls] == list(sentences)
    assert [row["call_index"] for row in calls] == list(range(1, 75))
    # Pack order: article15 block first, article7 last.
    assert calls[0]["sample_id"] == "gdpr_article15_s001"
    assert calls[-1]["sample_id"] == "gdpr_article7_s008"


def test_every_request_binds_the_sentence_text_bytes_by_hash() -> None:
    report = pre.build(_FakeTokenizer())
    sentences = _pack_sentences()
    for row in report["arms"]["direct_llm"]["calls"]:
        pack = sentences[row["sample_id"]]
        text = pack["approved_text_en"]
        # The recorded per-sentence hash is the SHA-256 of the UTF-8 bytes of
        # the sentence text embedded in the request.
        assert _sha_text(text) == row["sentence_text_sha256"]
        assert _sha_text(text) == pack["text_sha256"]
        assert row["sentence_text_utf8_bytes"] == len(text.encode("utf-8"))
        assert row["rule_id"] == pack["rule_id"]
        assert row["sentence_idx"] == pack["sentence_idx"]
        assert row["clause_id"] is None


def test_rendered_bodies_are_deterministic_and_contain_the_sentence() -> None:
    """Re-rendered bodies byte-match the committed per-request hashes, which
    proves the exact sentence text (and only that text) drives the payload."""
    report = pre.build(_FakeTokenizer())
    committed = {
        row["sample_id"]: row for row in report["arms"]["direct_llm"]["calls"]
    }
    prompt = load_prompt(pre.PROMPT_NAME)
    sentences = _pack_sentences()
    for sample_id, body_bytes, body_len, user_prompt in _render_bodies():
        row = committed[sample_id]
        assert hashlib.sha256(body_bytes).hexdigest() == row["request_body_sha256"]
        assert body_len == row["request_body_utf8_bytes"]
        # The full sentence text is present verbatim in the user envelope.
        assert sentences[sample_id]["approved_text_en"] in user_prompt
        assert sentences[sample_id]["approved_text_en"] in json.loads(
            body_bytes.decode("utf-8"))["messages"][1]["content"]
        assert len(prompt.system_prompt.encode("utf-8")) == row["system_prompt_utf8_bytes"]


def test_no_gold_or_panel_labels_in_any_request() -> None:
    prompt = load_prompt(pre.PROMPT_NAME)
    for sample_id, body_bytes, _body_len, _user in _render_bodies():
        body = json.loads(body_bytes.decode("utf-8"))
        blob = json.dumps(body).lower()
        for term in _FORBIDDEN_LABEL_TERMS:
            assert term not in blob, f"{term!r} leaked into {sample_id}"
        # OpenAI-compatible envelope shape only.
        assert set(body) == {"model", "messages", "max_tokens", "temperature",
                             "top_p", "stream", "thinking"}
        assert body["model"] == pre.REQUIRED_MODEL
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["role"] == "user"
        assert body["temperature"] == 0.0
        assert body["top_p"] == 1.0
        assert body["max_tokens"] == 4096
        assert body["stream"] is False
        assert body["thinking"] == {"type": "disabled"}
        assert "response_format" not in body
        assert body["messages"][0]["content"] == prompt.system_prompt


# ---------------------------------------------------------------------------
# Published report structure, deterministic rebuild, caps
# ---------------------------------------------------------------------------


def test_published_report_exists_and_matches_pinned_numbers() -> None:
    assert OUTPUT.is_file()
    report = json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert report["schema_version"] == pre.SCHEMA_VERSION
    assert report["status"] == "payloads_locked_zero_api_authorization_pending"
    assert report["global"]["planned_calls"] == 74
    assert report["global"]["max_output_tokens_total"] == 74 * 4096 == 303104
    assert report["global"]["max_billed_input_tokens_total"] == 74_000_000
    assert report["global"]["retry_count"] == 0
    assert report["global"]["request_body_utf8_bytes"]["total"] == 1297742
    assert report["global"]["request_body_utf8_bytes"]["maximum_per_call"] == 18459
    assert report["global"]["local_proxy_tokens"]["total"] == 367333
    assert report["global"]["local_proxy_tokens"]["maximum_per_call"] == 5128
    auth = report["authorization"]
    assert auth["authorized"] is False
    assert auth["calls_made"] == 0
    assert auth["recommended_hard_limits"]["max_cost_usd"] == 2.61
    assert auth["recommended_hard_limits"]["max_cost_usd_off_peak_alternative"] == 1.31
    assert auth["recommended_hard_limits"]["retry_count"] == 0
    assert report["input"]["sha256"] == pre.EXPECTED_INPUT_SHA256
    assert report["input"]["records"] == 74
    assert len(report["arms"]["direct_llm"]["calls"]) == 74


def test_published_report_calls_carry_only_hashes_and_sizes() -> None:
    report = json.loads(OUTPUT.read_text(encoding="utf-8"))
    allowed_keys = {
        "call_index", "sample_id", "rule_id", "sentence_idx", "clause_id",
        "sentence_text_sha256", "sentence_text_utf8_bytes",
        "request_body_sha256", "request_body_utf8_bytes",
        "system_prompt_utf8_bytes", "user_prompt_utf8_bytes", "local_proxy_tokens",
    }
    for row in report["arms"]["direct_llm"]["calls"]:
        assert set(row) == allowed_keys
        assert len(row["request_body_sha256"]) == 64
        assert len(row["sentence_text_sha256"]) == 64
        assert row["request_body_utf8_bytes"] > 0
        assert row["local_proxy_tokens"] > 0


def test_deterministic_rebuild_equality() -> None:
    first = pre.build(_FakeTokenizer())
    second = pre.build(_FakeTokenizer())
    assert first == second
    a = (json.dumps(first, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    b = (json.dumps(second, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    assert a == b
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()


def test_caps_are_finite_and_cover_rendered_estimates() -> None:
    for report in (
        pre.build(_FakeTokenizer()),
        json.loads(OUTPUT.read_text(encoding="utf-8")),
    ):
        limits = report["authorization"]["recommended_hard_limits"]
        for key in ("max_billed_input_tokens_total", "max_output_tokens_total",
                    "max_cost_usd", "max_request_body_utf8_bytes_total",
                    "max_request_body_utf8_bytes_per_call"):
            assert math.isfinite(limits[key])
            assert limits[key] > 0
        glob = report["global"]
        # Input bound (74 x 1M context) covers the proxy estimate.
        assert glob["max_billed_input_tokens_total"] >= glob["local_proxy_tokens"]["total"]
        assert glob["max_billed_input_tokens_total"] == 74 * 1_000_000
        # Output cap equals 74 x 4096 and is >= the per-call bound.
        assert glob["max_output_tokens_total"] == 74 * 4096
        assert glob["max_output_tokens_per_call"] == 4096
        # The margin USD cap must be >= the raw planning peak cost.
        pricing = report["pricing"]
        peak_plan = pricing["proxy_based_planning_only_not_billable_exact"][
            "cache_miss_input_plus_max_output_peak_usd"]
        assert limits["max_cost_usd"] >= peak_plan
        assert math.isfinite(peak_plan)
        # Every per-call body is within the recorded caps.
        for row in report["arms"]["direct_llm"]["calls"]:
            assert 0 < row["request_body_utf8_bytes"] <= limits[
                "max_request_body_utf8_bytes_per_call"]


# ---------------------------------------------------------------------------
# Overwrite / check guards
# ---------------------------------------------------------------------------


def test_publish_refuses_overwrite_without_flag(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    out.write_bytes(b"existing-bytes")
    with pytest.raises(pre.PreflightFail):
        pre.publish(b"new-bytes", output=out, overwrite=False)
    assert out.read_bytes() == b"existing-bytes"  # untouched
    pre.publish(b"new-bytes", output=out, overwrite=True)
    assert out.read_bytes() == b"new-bytes"


def test_check_fails_closed_on_missing_or_drifted_report(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    with pytest.raises(pre.PreflightFail):
        pre.check(b"payload", output=out)  # missing
    out.write_bytes(b"other-bytes")
    with pytest.raises(pre.PreflightFail):
        pre.check(b"payload", output=out)  # drifted
    out.write_bytes(b"payload")
    pre.check(b"payload", output=out)  # byte-identical -> passes


# ---------------------------------------------------------------------------
# Zero network / API by construction
# ---------------------------------------------------------------------------


def test_module_imports_no_network_or_transport_code() -> None:
    source = (ROOT / "scripts" / "build_gdpr7_direct_llm_preflight_v1.py").read_text(
        encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_roots.add(node.module.split(".")[0])
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)
    assert not (imported_roots & _FORBIDDEN_IMPORT_ROOTS), sorted(
        imported_roots & _FORBIDDEN_IMPORT_ROOTS)
    assert not (imported_names & _FORBIDDEN_TRANSPORT_NAMES), sorted(
        imported_names & _FORBIDDEN_TRANSPORT_NAMES)
    # The module must only ever build requests, never a real transport.
    assert "RealAPITransport" not in source


def test_build_runs_with_http_modules_blocked_at_import_time() -> None:
    """Run the whole build in a subprocess where every real connection entry
    point (socket, HTTP(S)Connection, urlopen) raises and third-party HTTP
    client packages cannot be imported; success proves no transport path
    executes during a full render + budget build."""
    script = (
        "import builtins, sys, json\n"
        "from pathlib import Path\n"
        "# Block third-party HTTP client packages at import time.\n"
        "orig = builtins.__import__\n"
        "deny = " + repr(sorted({"requests", "httpx", "openai", "aiohttp", "boto3"})) + "\n"
        "def guard(name, *a, **k):\n"
        "    if name.split('.')[0] in deny:\n"
        "        raise RuntimeError('blocked-network-import:' + name)\n"
        "    return orig(name, *a, **k)\n"
        "builtins.__import__ = guard\n"
        "# Neutralise every real connection entry point AFTER the stdlib\n"
        "# modules are imported (ssl subclasses socket.socket at import time);\n"
        "# any later attempt to open a real connection dies.\n"
        "import socket\n"
        "import http.client\n"
        "import urllib.request\n"
        "def boom(*a, **k):\n"
        "    raise RuntimeError('network-attempt-executed')\n"
        "socket.socket = boom\n"
        "http.client.HTTPConnection = boom\n"
        "http.client.HTTPSConnection = boom\n"
        "urllib.request.urlopen = boom\n"
        "sys.path.insert(0, r'" + str(ROOT) + "')\n"
        "sys.path.insert(0, r'" + str(ROOT / "src") + "')\n"
        "sys.path.insert(0, r'" + str(ROOT / "scripts") + "')\n"
        "import build_gdpr7_direct_llm_preflight_v1 as pre\n"
        "class _Enc:\n"
        "    def __init__(self, n): self.ids = list(range(1, n + 1))\n"
        "class _Fake:\n"
        "    def encode(self, text, add_special_tokens=True): return _Enc(len(text))\n"
        "report = pre.build(_Fake())\n"
        "assert len(report['arms']['direct_llm']['calls']) == 74\n"
        "assert report['safety']['llm_api_calls'] == 0\n"
        "assert report['safety']['network_calls'] == 0\n"
        "assert report['authorization']['authorized'] is False\n"
        "print('offline-build-ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        cwd=str(ROOT), timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert "offline-build-ok" in result.stdout
