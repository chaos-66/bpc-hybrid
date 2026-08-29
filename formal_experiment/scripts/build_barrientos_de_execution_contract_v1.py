# -*- coding: utf-8 -*-
"""Build the dedicated Barrientos D/E execution contract v1 (zero API).

Renders ALL 1140 requests offline (exactly as the executor will send them:
per-arm system/user prompts over the frozen inputs), measures the real
UTF-8 byte size and a conservative token estimate of every request, and
writes:

* ``configs/ablations/barrientos_de_execution_contract_v1.json`` — the
  executable contract bound to the current commit, the fixed 1140-call plan
  (D four arms x 150 + E three arms x 36 x 5, ALL under the SAME
  ``DeepSeek-V4-Pro-0813`` release window), model/sampling pins, hash set,
  and hard input/output-token + USD caps;
* ``outputs/reports/barrientos_de_budget_v1.json`` — the per-arm rendered
  request size audit (bytes/tokens per arm) that justifies the caps.

The contract does NOT reuse the S2.12 36+27 authorization schema.  The
``authorization`` block stays ``null`` until the user authorizes; the
executor refuses a real run while it is null.

MODEL-CONSISTENCY (2026-08-27): the old D-full (2026-08-06, alias
``deepseek-v4-pro`` -> ``DeepSeek-V4-Pro Preview``) is a HISTORICAL result;
the alias now maps to the official ``DeepSeek-V4-Pro-0813`` release.  Every
D and E arm in this contract runs under the 0813 window so module deltas
are model-consistent.  The request still uses the official alias
``deepseek-v4-pro`` (no dated endpoint exists); the contract records the
documented mapping with source URL and verification time.

Token estimate (conservative, no tokenizer dependency): tokens ≈
ceil(utf8_bytes / 3).  Real deepseek-v4-pro tokenizers average well above
3 bytes/token for these English legal/process texts, so this over-estimates
token counts and therefore the USD cap (a conservative bound, not a guess).
Input cap = 1.5 x estimated input tokens; output cap = 1140 x 4096 (every
call may emit the full max_tokens); USD cap uses the PEAK price (the
fail-closed conservative choice) with an additional 1.2x safety factor.
Peak/off-peak prices (DeepSeek V4 series, effective 2026-08-17, re-verified
against the official pricing page on 2026-08-29): input cache-miss 1.32 peak / 0.66 off-peak
USD per M; output 3.96 peak / 1.98 off-peak USD per M.  All numbers are
derived, never hand-written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from run_barrientos_ablation_suite_v2 import (  # noqa: E402
    D_ARMS,
    ESTG_INPUT,
    E_CONTRACT,
    CONFIG,
    S36_PAPER_ARMS,
    MODEL_ALIAS,
    MODEL_RELEASE_0813,
    MODEL_RELEASE_PREVIEW,
    MODEL_RELEASE_SOURCE_URL,
    MODEL_MAPPING_VERIFIED_UTC,
    OLD_D_FULL_DATE,
    _estg_samples,
    _e_samples,
    _prompt_for,
    _render_prompt,
    build_execution_plan,
)

CONTRACT_PATH = ROOT / "configs/ablations/barrientos_de_execution_contract_v1.json"
SCHEMA_PATH = ROOT / "configs/schemas/barrientos_de_execution_contract_v1.schema.json"
BUDGET_REPORT = ROOT / "outputs/reports/barrientos_de_budget_v1.json"

# DeepSeek V4 series peak/off-peak pricing (effective 2026-08-17;
# re-verified against the official pricing page immediately before the
# authorized run on 2026-08-29).
PRICE_VERSION = "deepseek_v4_peak_off_peak@2026-08-17"
INPUT_PRICE_PEAK_PER_M = 1.32    # USD per 1M input tokens (cache miss, peak)
INPUT_PRICE_OFFPEAK_PER_M = 0.66  # USD per 1M input tokens (cache miss, off)
OUTPUT_PRICE_PEAK_PER_M = 3.96   # USD per 1M output tokens (peak)
OUTPUT_PRICE_OFFPEAK_PER_M = 1.98  # USD per 1M output tokens (off-peak)
PRICE_SOURCE_URL = "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/"
PRICE_VERIFIED_UTC = "2026-08-29T02:19:45Z"
INPUT_SAFETY_FACTOR = 1.5
USD_SAFETY_FACTOR = 1.2
BYTES_PER_TOKEN = 3  # conservative: real tokenizers average > 3 bytes/token


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_head() -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT.parent,
                          capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def render_all_requests() -> dict[str, Any]:
    """Render every request the executor will send (1140 real calls: D 600
    + E 540; no reuse)."""
    plan = build_execution_plan(5, include_no_pattern=False)
    total = sum(r["expected_calls"] for r in plan)
    if total != 1140:
        raise RuntimeError(f"plan must be exactly 1140, got {total}")
    samples_by_arm = {
        "D-full-0813": _estg_samples(),
        "D-no-fewshot-0813": _estg_samples(),
        "D-minimal-0813": _estg_samples(),
        "D-barrientos-style-0813": _estg_samples(),
        "OURS-FULL": _e_samples(),
        "BARR-FULL": _e_samples(),
        "OURS-BARRIENTOS-MODULE": _e_samples(),
    }
    rendered: dict[str, Any] = {
        "plan_total_calls": total,
        "arms": {},
        "grand_total_bytes": 0,
        "grand_total_est_input_tokens": 0,
    }
    for planned in plan:
        arm = planned["arm"]
        entry = rendered["arms"].setdefault(arm, {
            "calls": 0, "requests": [], "bytes": 0, "est_tokens": 0})
        entry["calls"] += planned["expected_calls"]
        arm_bytes = 0
        arm_tokens = 0
        requests = []
        for sample in samples_by_arm[arm]:
            sid = sample.get("sample_id") or sample.get("id")
            text = sample.get("text") or sample.get("approved_text_en") or ""
            system_prompt, user_prompt = _render_prompt(arm, sid, text, sample)
            body = json.dumps({
                "model": MODEL_ALIAS,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.0, "top_p": 1.0, "max_tokens": 4096,
                "stream": False, "thinking": {"type": "disabled"},
            }, ensure_ascii=False, sort_keys=True).encode("utf-8")
            nbytes = len(body)
            est_tokens = math.ceil(nbytes / BYTES_PER_TOKEN)
            arm_bytes += nbytes
            arm_tokens += est_tokens
            requests.append({"sample_id": sid, "utf8_bytes": nbytes,
                             "est_input_tokens": est_tokens})
        entry["requests"].extend(requests)
        entry["bytes"] += arm_bytes
        entry["est_tokens"] += arm_tokens
        rendered["grand_total_bytes"] += arm_bytes
        rendered["grand_total_est_input_tokens"] += arm_tokens
    return rendered


def build_contract(overwrite: bool = False) -> dict[str, Any]:
    if CONTRACT_PATH.exists() and not overwrite:
        raise RuntimeError(f"refusing to overwrite: {CONTRACT_PATH}")
    if BUDGET_REPORT.exists() and not overwrite:
        raise RuntimeError(f"refusing to overwrite: {BUDGET_REPORT}")

    rendered = render_all_requests()
    est_input_tokens = rendered["grand_total_est_input_tokens"]
    input_token_cap = math.ceil(est_input_tokens * INPUT_SAFETY_FACTOR)
    output_token_cap = 1140 * 4096
    # fail-closed USD cap uses the PEAK price (conservative)
    usd_cost_cap = math.ceil(
        (input_token_cap * INPUT_PRICE_PEAK_PER_M
         + output_token_cap * OUTPUT_PRICE_PEAK_PER_M) / 1e6
        * USD_SAFETY_FACTOR * 1000) / 1000  # round up to 3 decimals

    plan = build_execution_plan(5, include_no_pattern=False)
    plan_rows = []
    for p in plan:
        plan_rows.append({
            "arm": p["arm"], "repeat_id": p["repeat_id"],
            "sample_count": p["sample_count"], "calls": p["expected_calls"],
            "reused": bool(p.get("reused", False)),
        })

    contract = {
        "schema_version": "barrientos_de_execution_contract@1.0.0",
        "suite_id": "S2-BARRIENTOS-DE-001",
        "bound_commit": _git_head(),
        "execution_plan": {"total_calls": 1140, "arms": plan_rows},
        "model": {
            "id": MODEL_ALIAS,
            "provider": "openai_compatible",
            "documented_mapping": {
                "release": MODEL_RELEASE_0813,
                "historical_release": MODEL_RELEASE_PREVIEW,
                "historical_execution_date": OLD_D_FULL_DATE,
                "source_url": MODEL_RELEASE_SOURCE_URL,
                "verified_at_utc": MODEL_MAPPING_VERIFIED_UTC,
                "note": ("requested alias deepseek-v4-pro maps to the "
                         "official DeepSeek-V4-Pro-0813 release since "
                         "2026-08-13; no immutable dated endpoint is "
                         "claimed; the old Preview D-full (2026-08-06) is "
                         "a historical result, never an ablation baseline"),
            },
        },
        "sampling": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 4096,
                     "retry": 0, "stream": False,
                     "thinking": {"type": "disabled"}},
        "hashes": {
            "estg_input_v2": _sha256_file(ESTG_INPUT),
            "e_contract_v2": _sha256_file(E_CONTRACT),
            "executor": _sha256_file(
                ROOT / "scripts/run_barrientos_ablation_suite_v2.py"),
            "config": _sha256_file(CONFIG),
            "prompts": {
                arm: _sha256_file(_prompt_for(arm)) for arm in D_ARMS
            } | {arm: _sha256_file(_prompt_for(arm)) for arm in S36_PAPER_ARMS},
        },
        "budget": {
            "planned_calls": 1140,
            "input_token_cap": input_token_cap,
            "output_token_cap": output_token_cap,
            "usd_cost_cap": usd_cost_cap,
            "price_snapshot": {
                "schema_version": "barrientos_de_price@1.0.0",
                "version": PRICE_VERSION,
                "currency": "USD",
                "mode_used_for_cap": "peak",
                "input_cache_miss_per_million": INPUT_PRICE_PEAK_PER_M,
                "output_per_million": OUTPUT_PRICE_PEAK_PER_M,
                "peak": {
                    "input_cache_miss_per_million": INPUT_PRICE_PEAK_PER_M,
                    "output_per_million": OUTPUT_PRICE_PEAK_PER_M,
                },
                "off_peak": {
                    "input_cache_miss_per_million": INPUT_PRICE_OFFPEAK_PER_M,
                    "output_per_million": OUTPUT_PRICE_OFFPEAK_PER_M,
                },
                "source_url": PRICE_SOURCE_URL,
                "verified_at_utc": PRICE_VERIFIED_UTC,
                "note": ("DeepSeek V4 series peak/off-peak pricing effective "
                         "2026-08-17; PEAK price is used for the fail-closed "
                         "USD cap (conservative); actual runs should prefer "
                         "off-peak hours; the old 990-contract snapshot is "
                         "NOT reused without this documentation"),
            },
            "input_estimate_note": (
                f"estimated input tokens={est_input_tokens} over 1140 "
                f"rendered requests (ceil(utf8_bytes/{BYTES_PER_TOKEN}), "
                f"conservative over-estimate); input cap = x"
                f"{INPUT_SAFETY_FACTOR}; output cap = 1140*4096; USD cap = "
                f"(input_cap*{INPUT_PRICE_PEAK_PER_M}/1M + "
                f"output_cap*{OUTPUT_PRICE_PEAK_PER_M}/1M)*"
                f"{USD_SAFETY_FACTOR} (PEAK price) rounded up; not a guess, "
                f"derived from rendered requests"),
            "computed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                             time.gmtime()),
        },
        "authorization": None,
        "gold_isolation": {
            "api_arms_must_not_read_gold": True,
            "evaluation_only_after_predictions_are_locked": True,
        },
    }

    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    report = {
        "schema_version": "barrientos_de_budget@2.0.0",
        "contract_path": str(CONTRACT_PATH.relative_to(ROOT)),
        "contract_sha256": _sha256_file(CONTRACT_PATH),
        "rendered_requests": rendered,
        "budget": contract["budget"],
        "note": ("all request bodies rendered offline with the exact "
                 "executor prompt rendering; zero network; zero API; "
                 "1140 calls = D 600 + E 540 under DeepSeek-V4-Pro-0813"),
    }
    BUDGET_REPORT.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"contract: {CONTRACT_PATH.relative_to(ROOT)}")
    print(f"budget:   {BUDGET_REPORT.relative_to(ROOT)}")
    print(f"estimated input tokens: {est_input_tokens}")
    print(f"input cap: {input_token_cap} | output cap: {output_token_cap} "
          f"| USD cap (peak): {usd_cost_cap}")
    return contract


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true",
                        help="allow replacing an existing contract/schema")
    args = parser.parse_args()
    try:
        build_contract(overwrite=args.overwrite)
        return 0
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
