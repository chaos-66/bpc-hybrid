# -*- coding: utf-8 -*-
"""Build the dedicated 450-call prompt-factor execution contract (offline)."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_d1_prompt_factorial_ablation_v2 as runner  # noqa: E402


OUT = runner.CONTRACT_PATH
BUDGET_REPORT = (
    ROOT / "outputs" / "reports" / "d1_prompt_factorial_budget_v1.json"
)
SOURCE_URL = "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/"
VERIFIED_AT_UTC = "2026-08-30T00:00:00Z"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _head() -> str:
    value = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    if len(value) != 40:
        raise RuntimeError("invalid git HEAD")
    return value


def build(*, overwrite: bool = False) -> dict:
    if OUT.exists() and not overwrite:
        raise RuntimeError(f"refusing to overwrite: {OUT}")
    estimated_input, per_arm = runner.estimate_rendered_input_tokens()
    input_cap = math.ceil(estimated_input * 1.5)
    output_cap = runner.PLANNED_CALLS * 4096
    peak_cost = input_cap * 1.32 / 1e6 + output_cap * 3.96 / 1e6
    usd_cap = math.ceil(peak_cost * 1.2 * 1000) / 1000
    off_peak_cny = (
        input_cap * 4.5 / 1e6 + output_cap * 13.5 / 1e6)
    cny_envelope = math.ceil(off_peak_cny * 1.2 * 100) / 100

    price = {
        "currency": "USD",
        "mode_used_for_gate": "peak",
        "input_cache_miss_per_million": 1.32,
        "output_per_million": 3.96,
        "off_peak_cny": {
            "input_cache_miss_per_million": 4.5,
            "output_per_million": 13.5,
        },
        "source_url": SOURCE_URL,
        "verified_at_utc": VERIFIED_AT_UTC,
    }
    budget = {
        "planned_calls": runner.PLANNED_CALLS,
        "estimated_input_tokens": estimated_input,
        "input_token_cap": input_cap,
        "output_token_cap": output_cap,
        "usd_cost_cap": usd_cap,
        "cny_off_peak_envelope": cny_envelope,
        "price_snapshot": price,
        "calculation": (
            "render all 450 requests; estimate each input as "
            "ceil(UTF-8 request bytes/3); input cap=estimate*1.5; output "
            "cap=450*4096; USD gate=(caps at peak USD rates)*1.2 rounded "
            "up; CNY envelope=(caps at off-peak CNY rates)*1.2 rounded up"
        ),
    }
    contract = {
        "schema_version": "d1_prompt_factorial_execution_contract@1.0.0",
        "suite_id": "S2-D1-PROMPT-FACTORIAL-001",
        "bound_commit": _head(),
        "execution_plan": {
            "total_calls": runner.PLANNED_CALLS,
            "arms": runner.build_execution_plan(),
        },
        "model": {
            "id": runner.MODEL_ALIAS,
            "provider": "openai_compatible",
            "documented_mapping": {
                "release": runner.MODEL_RELEASE,
                "source_url": SOURCE_URL,
                "verified_at_utc": VERIFIED_AT_UTC,
                "note": (
                    "API alias is mutable; this batch is compared only with "
                    "the completed D-full-0813 arm from the same documented "
                    "release window"
                ),
            },
        },
        "sampling": {
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 4096,
            "retry": 0,
            "stream": False,
            "thinking": {"type": "disabled"},
        },
        "hashes": {
            "estg_input_v2": _sha256(runner.ESTG_INPUT),
            "executor": _sha256(runner.EXECUTOR_FILE),
            "prompt_builder": _sha256(runner.BUILDER_FILE),
            "prompt_manifest": _sha256(runner.PROMPT_MANIFEST),
            "prompts": {
                arm: _sha256(runner.prompt_path(arm)) for arm in runner.ARMS
            },
        },
        "budget": budget,
        "authorization": None,
        "gold_isolation": {
            "api_arms_must_not_read_gold": True,
            "evaluation_only_after_predictions_are_locked": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    BUDGET_REPORT.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_REPORT.write_text(
        json.dumps({
            "schema_version": "d1_prompt_factorial_budget@1.0.0",
            "computed_at_utc": datetime.now(timezone.utc).isoformat(),
            "per_arm_estimated_input_tokens": per_arm,
            "budget": budget,
            "llm_api_calls": 0,
            "network_calls": 0,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    return contract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    contract = build(overwrite=args.overwrite)
    print(
        "Prepared 450-call contract (authorization=null, zero API): "
        f"USD cap {contract['budget']['usd_cost_cap']:.3f}; "
        f"off-peak CNY envelope "
        f"{contract['budget']['cny_off_peak_envelope']:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
