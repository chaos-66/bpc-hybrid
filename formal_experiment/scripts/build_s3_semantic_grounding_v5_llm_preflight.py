# -*- coding: utf-8 -*-
"""Build the final v5 fallback preflight and authorization request (zero API).

The request bodies are rebuilt from the v5 candidate pack with the final
executor/prompt code.  No old v2 request-set hash or candidate-pack hash is
reused.  Existing authorizations are inventoried; an old scope/hash does not
authorize this payload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.s3_semantic_grounding_llm_v1 import (  # noqa: E402
    build_request_set,
    estimate_usd_cost,
)
from bpc_hybrid.s3_semantic_grounding_v2 import json_sha256  # noqa: E402

V5_EVIDENCE = ROOT / "outputs/evidence/s3_semantic_grounding_v5"
V5_PACK = V5_EVIDENCE / "llm_fallback_candidate_pack_v5.json"
REPORT_ROOT = ROOT / "outputs/reports"
PREFLIGHT_JSON = REPORT_ROOT / "s3_semantic_grounding_v5_llm_preflight.json"
AUTH_JSON = REPORT_ROOT / "s3_semantic_grounding_v5_llm_authorization_request.json"
AUTH_MD = REPORT_ROOT / "s3_semantic_grounding_v5_llm_authorization_request.md"
EVIDENCE_PREFLIGHT = V5_EVIDENCE / "llm_preflight_v2.json"
EVIDENCE_AUTH = V5_EVIDENCE / "llm_authorization_request_v2.json"
EVIDENCE_REQUEST_SET = V5_EVIDENCE / "llm_preflight_request_set_v2.json"
EVIDENCE_REQUESTS = V5_EVIDENCE / "llm_preflight_canonical_requests_v2.jsonl"
RUNNER_REVISION = "s3_semantic_grounding_llm_v2"
SCOPE = "S3-SEMANTIC-GROUNDING-V5-FALLBACK"
MODEL = "deepseek-v4-pro"
PROVIDER = "openai_compatible"
OFF_PEAK_WINDOWS_UTC = [[0.0, 1.0], [4.0, 6.0], [10.0, 24.0]]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                            for row in rows), encoding="utf-8", newline="\n")


def authorization_inventory() -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for root in (ROOT / "configs", ROOT / "outputs/reports", ROOT / "outputs/evidence"):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                data = read_json(path)
            except Exception:
                continue
            if not isinstance(data, Mapping):
                continue
            scope = data.get("scope") or data.get("authorization_scope")
            status = data.get("status") or data.get("authorization_status")
            if not scope and not status:
                continue
            inventory.append({
                "path": path.relative_to(ROOT).as_posix(),
                "scope": scope,
                "status": status,
                "model": data.get("model"),
                "candidate_pack_sha256": data.get("candidate_pack_sha256"),
                "request_set_sha256": data.get("request_set_sha256"),
            })
    return inventory


def _authorization_sentence(*, count: int, request_set_sha256: str,
                            candidate_pack_sha256: str, input_tokens: int,
                            input_cap: int, output_cap: int, usd_cap: float,
                            rmb_cap: float) -> str:
    return (
        "\u6211\u6388\u6743\u5728 " + SCOPE + " \u8303\u56f4\u5185\u4f7f\u7528 "
        + PROVIDER + "/" + MODEL + " \u5bf9\u5df2\u51bb\u7ed3\u7684 "
        + str(count) + " \u4e2a fallback items \u6267\u884c\u771f\u5b9e API "
        "\u8c03\u7528\uff1bretry=0\uff1b\u4ec5\u5728\u4f4e\u5cf0\u65f6\u6bb5\u8fd0"
        "\u884c\uff08UTC 00:00-01:00 / 04:00-06:00 / 10:00-24:00\uff09\uff1b"
        "\u8f93\u5165 token \u4e0a\u9650 " + str(input_cap) + "\uff1b"
        "\u8f93\u51fa\u603b token \u4e0a\u9650 " + str(output_cap) + "\uff1b"
        "\u603b\u8d39\u7528\u4e0a\u9650 USD " + f"{usd_cap:.2f}"
        + " / RMB " + f"{rmb_cap:.2f}" + "\uff1b\u8bf7\u6c42\u96c6 hash="
        + request_set_sha256 + "\uff1b\u5019\u9009 pack hash="
        + candidate_pack_sha256 + "\u3002")


def build() -> dict[str, Any]:
    pack = read_json(V5_PACK)
    item_count = int(pack.get("item_count") or 0)
    request_set = build_request_set(pack, {
        "model": MODEL,
        "max_output_tokens_per_call": 512,
        "temperature": 0.0,
        "top_p": 1.0,
    })
    total_input = int(request_set["total_input_tokens_estimate"])
    output_cap = int(request_set["total_output_token_cap"])
    input_cap = total_input * 2
    config = {
        "model": MODEL,
        "price_snapshot": {
            "peak": {"input_cache_miss_per_million": 1.32,
                     "output_per_million": 3.96},
            "off_peak": {"input_cache_miss_per_million": 0.66,
                         "output_per_million": 1.98},
        },
    }
    off_peak_estimate = estimate_usd_cost(total_input, output_cap, config,
                                          off_peak=True)
    peak_estimate = estimate_usd_cost(total_input, output_cap, config,
                                      off_peak=False)
    usd_cap = round(peak_estimate * 1.5, 2)
    if usd_cap < request_set["required_peak_usd_cap"]:
        usd_cap = float(request_set["required_peak_usd_cap"])
    rmb_cap = round(usd_cap * 7.2, 2)
    candidate_pack_sha = json_sha256(pack)
    request_set_sha = request_set["request_set_sha256"]
    sentence = _authorization_sentence(
        count=item_count, request_set_sha256=request_set_sha,
        candidate_pack_sha256=candidate_pack_sha, input_tokens=total_input,
        input_cap=input_cap, output_cap=output_cap, usd_cap=usd_cap,
        rmb_cap=rmb_cap)
    inventory = authorization_inventory()
    matching = [entry for entry in inventory
                if entry.get("scope") == SCOPE
                and entry.get("status") == "authorized_unconsumed"
                and entry.get("request_set_sha256") == request_set_sha
                and entry.get("candidate_pack_sha256") == candidate_pack_sha]
    old_scope = [entry for entry in inventory if entry.get("scope") == SCOPE]
    non_matching = [entry for entry in inventory if entry.get("scope") != SCOPE]
    auth_request = {
        "schema_version": "s3_semantic_grounding_llm_authorization_request@2.0.0",
        "revision": RUNNER_REVISION,
        "base_revision": "s3_semantic_grounding_v5",
        "scope": SCOPE,
        "provider": PROVIDER,
        "model": MODEL,
        "base_url_env_var": "BPC_HYBRID_DeepSeek_BASE_URL",
        "api_key_env_var": "BPC_HYBRID_DeepSeek_API_KEY",
        "fallback_item_count": item_count,
        "calls": item_count,
        "retry": 0,
        "off_peak_only": True,
        "off_peak_windows_utc": OFF_PEAK_WINDOWS_UTC,
        "expected_input_tokens": total_input,
        "max_input_tokens_cap": input_cap,
        "max_output_tokens_per_call": 512,
        "total_output_token_cap": output_cap,
        "peak_estimated_usd": peak_estimate,
        "off_peak_estimated_usd": off_peak_estimate,
        "peak_usd_cap": usd_cap,
        "required_peak_usd_cap": request_set["required_peak_usd_cap"],
        "usd_cap": usd_cap,
        "rmb_cap_at_7.2": rmb_cap,
        "candidate_pack_sha256": candidate_pack_sha,
        "request_set_sha256": request_set_sha,
        "canonical_request_count": len(request_set["requests"]),
        "suggested_authorization_sentence": sentence,
        "suggested_authorization_sentence_sha256": hashlib.sha256(
            sentence.encode("utf-8")).hexdigest(),
        "execution_command": (
            "cd formal_experiment && python scripts/"
            "run_s3_semantic_grounding_llm_v2.py --real "
            "--authorization outputs/reports/"
            "s3_semantic_grounding_v5_llm_authorization_event.json"),
        "matching_authorizations": matching,
        "old_v5_scope_authorizations": old_scope,
        "non_matching_authorization_count": len(non_matching),
        "existing_v2_pack_or_request_hash_reused": False,
        "decision": ("BLOCKED_NO_MATCHING_AUTHORIZATION"
                     if not matching else "MATCHING_AUTHORIZATION_FOUND"),
    }
    preflight = {
        "schema_version": "s3_semantic_grounding_llm_preflight@2.0.0",
        "revision": RUNNER_REVISION,
        "base_revision": "s3_semantic_grounding_v5",
        "status": ("READY_FOR_AUTHORIZATION_DECISION"
                   if not matching else "MATCHING_AUTHORIZATION_FOUND_NEEDS_MANUAL_REVIEW"),
        "real_api_calls": 0,
        "network_calls": 0,
        "candidate_pack_path": V5_PACK.relative_to(ROOT).as_posix(),
        "candidate_pack_sha256": candidate_pack_sha,
        "candidate_pack_item_count": item_count,
        "request_count": request_set["request_count"],
        "request_set_sha256": request_set_sha,
        "expected_input_tokens": total_input,
        "max_input_tokens_cap": input_cap,
        "total_output_token_cap": output_cap,
        "off_peak_windows_utc": OFF_PEAK_WINDOWS_UTC,
        "peak_estimated_usd": peak_estimate,
        "off_peak_estimated_usd": off_peak_estimate,
        "usd_cap_requested": usd_cap,
        "rmb_cap_requested": rmb_cap,
        "matching_authorization_files": matching,
        "matching_authorization_count": len(matching),
        "authorization_inventory_count": len(inventory),
        "non_matching_authorization_count": len(non_matching),
        "old_v2_pack_or_request_hash_reused": False,
        "authorization_request_path": AUTH_JSON.relative_to(ROOT).as_posix(),
        "authorization_request_md_path": AUTH_MD.relative_to(ROOT).as_posix(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(AUTH_JSON, auth_request)
    write_json(EVIDENCE_AUTH, auth_request)
    write_json(PREFLIGHT_JSON, preflight)
    write_json(EVIDENCE_PREFLIGHT, preflight)
    write_json(EVIDENCE_REQUEST_SET, request_set)
    write_jsonl(EVIDENCE_REQUESTS, request_set["requests"])
    lines = [
        "# V5 fallback authorization request (zero API preflight)",
        "",
        f"- Scope: `{SCOPE}`",
        f"- Provider/model: `{PROVIDER}` / `{MODEL}`",
        f"- Calls: **{item_count}**; retry=0; off-peak windows (UTC): "
        f"`{OFF_PEAK_WINDOWS_UTC}`",
        f"- Expected input tokens: `{total_input}`; input cap: `{input_cap}`",
        f"- Output cap: `{output_cap}` (512 per call)",
        f"- USD cap: `{usd_cap}`; RMB cap at 7.2: `{rmb_cap}`",
        f"- Candidate pack hash: `{candidate_pack_sha}`",
        f"- Request-set hash: `{request_set_sha}`",
        f"- Matching existing authorizations: `{len(matching)}`",
        "",
        "## Exact authorization sentence",
        "",
        sentence,
        "",
        f"Sentence SHA-256: `{auth_request['suggested_authorization_sentence_sha256']}`",
        "",
        "Old v2 scope/hash authorizations are not reused.",
        "",
    ]
    AUTH_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return {"auth_request": auth_request, "preflight": preflight}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()
    result = build()
    print(json.dumps({
        "scope": result["auth_request"]["scope"],
        "calls": result["auth_request"]["calls"],
        "request_set_sha256": result["auth_request"]["request_set_sha256"],
        "candidate_pack_sha256": result["auth_request"]["candidate_pack_sha256"],
        "matching_authorizations": len(result["auth_request"]["matching_authorizations"]),
        "decision": result["auth_request"]["decision"],
        "real_api_calls": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
