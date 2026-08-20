# -*- coding: utf-8 -*-
"""Build deterministic S2.12 readiness v4 after the zero-API arm."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/reports/s2_12_execution_readiness_v4.json"
GOLD = ROOT / "data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json"
GOLD_MANIFEST = ROOT / "outputs/reports/s2_11_formal_gold_v1.manifest.json"
CONFIRMATION = ROOT / "configs/s2_11_batch_import_confirmation_event_v3.json"
FREEZE = ROOT / "outputs/reports/s2_11_freeze_publication_capsule_v1.json"
ZERO_MANIFEST = ROOT / "data/predictions/s2_12_sun_rule_only_v1/manifest.json"
ZERO_EVAL = ROOT / "data/results/s2_12_sun_rule_only_v1/evaluation.json"
ZERO_EVAL_MANIFEST = ROOT / "data/results/s2_12_sun_rule_only_v1/manifest.json"
PREFLIGHT = ROOT / "outputs/reports/s2_12_api_preflight_v1.json"
PREFLIGHT_LOCK = ROOT / "configs/s2_12_api_arms_preflight_v1.json"

VERIFIERS = (
    ("s2_11_freeze_v3", "scripts/verify_s2_11_review_freeze_v3.py", "--json"),
    ("s2_11_formal_gold_v1", "scripts/verify_s2_11_formal_gold_v1.py", "--json"),
    ("s2_12_zero_api_v1", "scripts/verify_s2_12_sun_rule_only_v1.py", None),
    ("s2_12_api_preflight_v1", "scripts/verify_s2_12_api_preflight_v1.py", "--json"),
)


class ReadinessFail(ValueError):
    """Fail-closed readiness build error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _run_verifiers() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, rel, flag in VERIFIERS:
        cmd = [sys.executable, str(ROOT / rel)]
        if flag:
            cmd.append(flag)
        proc = subprocess.run(cmd, cwd=ROOT.parent, capture_output=True, text=True)
        if proc.returncode != 0:
            raise ReadinessFail(f"{name} verifier failed: {(proc.stderr or proc.stdout)[-600:]}")
        result[name] = {"path": rel, "sha256": _sha(ROOT / rel), "verified": True, "exit_code": 0}
    return result


def _binding(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": _sha(path),
        "byte_size": path.stat().st_size,
    }


def build() -> dict[str, Any]:
    required = (GOLD, GOLD_MANIFEST, CONFIRMATION, FREEZE, ZERO_MANIFEST,
                ZERO_EVAL, ZERO_EVAL_MANIFEST, PREFLIGHT, PREFLIGHT_LOCK)
    if not all(path.is_file() for path in required):
        raise ReadinessFail("required S2.11/S2.12 evidence is missing")
    verifiers = _run_verifiers()
    gold_manifest = json.loads(GOLD_MANIFEST.read_text(encoding="utf-8"))
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    evaluation = json.loads(ZERO_EVAL.read_text(encoding="utf-8"))
    preflight = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    if evaluation.get("status") != "verified_zero_api_arm_complete":
        raise ReadinessFail("zero-API evaluation is not complete")
    if preflight.get("status") != "payloads_locked_zero_api_authorization_pending":
        raise ReadinessFail("API preflight is not locked and pending authorization")
    limits = preflight["authorization"]["recommended_hard_limits"]
    sentence = (
        "我授权在 S2.12 复杂语料上运行 direct_llm（36 次）和 "
        "sun_llm_fallback（27 次）真实 DeepSeek API，模型仅限 "
        "deepseek-v4-pro，严格使用 preflight v1 锁定的 63 个请求体"
        f"（单次≤{limits['max_request_body_utf8_bytes_per_call']} 字节、"
        f"总计≤{limits['max_request_body_utf8_bytes_total']} 字节），最多 "
        f"{limits['max_calls']} 次调用、0 次重试、单次输出≤4096 tokens、"
        f"总输出≤{limits['max_output_tokens_total']} tokens、总计费输入≤"
        f"{limits['max_billed_input_tokens_total']} tokens、总费用≤US$"
        f"{limits['max_cost_usd']:.2f}；任一模型/返回模型、输入、source、"
        "prompt、config、payload/hash、官方价格、Gold 隔离或上限不匹配时"
        "必须在调用前硬停止，不得调用 Oracle。"
    )
    return {
        "schema_version": "s2_12_execution_readiness@4.0.0",
        "report_id": "s2_12_execution_readiness_v4",
        "status": "partial_zero_api_arm_complete_api_arms_pending_authorization",
        "s2_11": {
            "status": "verified_frozen",
            "adjudicated": 36,
            "unresolved": 0,
            "blocked": 0,
            "reviewer": "hyc",
            "formal_gold": _binding(GOLD),
            "formal_gold_manifest": _binding(GOLD_MANIFEST),
            "formal_gold_payload_sha256": gold_manifest["artifacts"][
                "data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json"
            ]["sha256"],
            "confirmation_event": _binding(CONFIRMATION),
            "freeze_publication_capsule": _binding(FREEZE),
            "frozen": freeze["status"] == "verified_frozen_published",
        },
        "s2_12": {
            "status": "partial",
            "gold_blind_input_records": 36,
            "sun_rule_only": {
                "status": "verified_complete",
                "single_zero_api_arm_only": True,
                "manifest": _binding(ZERO_MANIFEST),
                "evaluation": _binding(ZERO_EVAL),
                "evaluation_manifest": _binding(ZERO_EVAL_MANIFEST),
                "runtime_seconds": json.loads(ZERO_MANIFEST.read_text(encoding="utf-8"))["runtime_summary"]["total_seconds"],
                "actual_cost_usd": 0.0,
                "overall": evaluation["metrics"]["overall"],
                "strata": evaluation["metrics"]["strata"],
            },
            "direct_llm": "pending_explicit_api_authorization",
            "sun_llm_fallback": "pending_explicit_api_authorization",
            "three_method_comparison_complete": False,
            "post_result_tuning_performed": False,
        },
        "api_preflight": {
            "report": _binding(PREFLIGHT),
            "lock": _binding(PREFLIGHT_LOCK),
            "model": preflight["model"]["id"],
            "planned_calls": preflight["global"]["planned_calls"],
            "direct_llm_calls": preflight["arms"]["direct_llm"]["planned_calls"],
            "sun_llm_fallback_calls": preflight["arms"]["sun_llm_fallback"]["planned_calls"],
            "request_body_utf8_bytes": preflight["global"]["request_body_utf8_bytes"],
            "local_proxy_tokens": preflight["global"]["local_proxy_tokens"],
            "official_billing_input_tokens": None,
            "max_output_tokens": preflight["global"]["max_output_tokens_total"],
            "retry_count": 0,
            "actual_cost_usd": None,
            "official_price_source": preflight["pricing"]["official_source"],
        },
        "remaining_dod": [
            "explicit user API authorization with total billed input-token and USD caps",
            "locked direct_llm and sun_llm_fallback executions",
            "frozen three-method evaluation/comparison and S2.12 completion checkpoint",
        ],
        "downstream": {
            "S2.13": "blocked_only_on_remaining_S2.12_DoD",
            "S3.4_S3.6": "development_only",
            "S3.7": "formal_oracle_not_started",
            "gold_rule_records": "absent",
        },
        "verifiers": verifiers,
        "authorization": {
            "api_authorized": False,
            "suggested_copyable_sentence_is_not_itself_authorization": True,
            "suggested_copyable_sentence": sentence,
            "recommended_hard_limits": limits,
        },
        "safety": {
            "new_llm_api_calls": 0,
            "new_network_calls": 0,
            "gold_rule_records_created": False,
            "oracle_started": False,
            "project_audit_md_modified": False,
        },
        "reproduce_command": "python formal_experiment/scripts/s2_12_build_readiness_v4.py --check",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        payload = _json_bytes(build())
        if args.publish:
            if OUTPUT.exists():
                raise ReadinessFail(f"refusing to overwrite {OUTPUT}")
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=OUTPUT.parent, delete=False) as stream:
                stage = Path(stream.name)
                stream.write(payload)
            try:
                stage.replace(OUTPUT)
            except Exception:
                stage.unlink(missing_ok=True)
                raise
        elif not OUTPUT.is_file() or OUTPUT.read_bytes() != payload:
            raise ReadinessFail("published readiness v4 differs from replay")
    except (OSError, ValueError) as exc:
        print(f"S2.12 readiness v4 refused: {exc}")
        return 2
    print("S2.12 readiness v4 VERIFIED: partial, zero-API complete, API authorization pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
