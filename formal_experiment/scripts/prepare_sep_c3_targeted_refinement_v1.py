# -*- coding: utf-8 -*-
"""Zero-network preparation for the SEP-C3 targeted-refinement run.

Writes the frozen schedule (sample-level A/B/C/D permutation) and the budget
contract before any model call.  The schedule is generated once and hashed;
the runner refuses to start without a valid, matching file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_sep_c3_modular_ablation_v1 as core  # noqa: E402
import bpc_hybrid.modular_refinement_prompt as rp  # noqa: E402


SUITE_ID = "SEP-C3-TARGETED-REFINEMENT-001"
ARM_ORDER = list(rp.ARMS)
SAMPLES_PER_ARM = 150
PLANNED_CALLS = 600
CALL_CAP = 750
INPUT_TOKEN_CAP = 2_800_000
OUTPUT_TOKEN_CAP = 2_500_000
USD_COST_CAP = 16.0
PRICE_SNAPSHOT = {
    "currency": "USD",
    "mode_used_for_gate": "peak_conservative",
    "input_cache_miss_per_million": 1.32,
    "output_per_million": 3.96,
    "source_url": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
    "verified_at_utc": "2026-08-30T00:00:00Z",
    "note": (
        "Reuses the project price snapshot from the SEP-C3 modular budget; "
        "no online re-check during this zero-network preparation step."
    ),
}
SCHEDULE_SCHEME = "sample_level_random_permutation"
SCHEDULE_SEED_MATERIAL = (
    "SEP-C3-TARGETED-REFINEMENT-001|samples=150|arms=A,B,C,D|"
    "scheme=sample_level_random_permutation|version=1"
)

BUDGET_PATH = ROOT / "configs" / "sep_c3_targeted_refinement_budget_v1.json"
SCHEDULE_PATH = ROOT / "configs" / "sep_c3_targeted_refinement_schedule_v1.json"
PREPARE_REPORT_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_targeted_refinement_v1_prepare_audit.json"
)
CONFIG_DIFF_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_targeted_refinement_v1_config_diff.json"
)
PROMPT_AUDIT_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_targeted_refinement_v1_prompt_audit.json"
)
EVALUATOR_COARSE = ROOT / "src" / "bpc_hybrid" / "sep_c3_modular_evaluation.py"
EVALUATOR_FROZEN = ROOT / "src" / "bpc_hybrid" / "stage2_sun_literal_overlap.py"
PARSER_ADAPTER = ROOT / "src" / "bpc_hybrid" / "d1_schema_adapter.py"
PARSER_CANONICALIZER = ROOT / "src" / "bpc_hybrid" / "d1_span_canonicalizer.py"
PROMPT_MANIFEST = rp.generated_manifest_path()


class PrepareError(RuntimeError):
    """A zero-network preparation precondition failed."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PrepareError(f"expected JSON object: {path}")
    return value


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _request_body(arm: str, sample_id: str, source_text: str) -> dict[str, Any]:
    prompt = rp.render_refinement_prompt(arm)
    return {
        "model": core.MODEL_ALIAS,
        "messages": prompt.request_messages(sample_id, source_text),
        "temperature": core.TEMPERATURE,
        "top_p": core.TOP_P,
        "max_tokens": core.MAX_TOKENS,
        "stream": False,
        "thinking": {"type": "disabled"},
    }


def build_schedule(input_rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    rng = random.Random(SCHEDULE_SEED_MATERIAL)
    entries: list[dict[str, Any]] = []
    for sample_order_index, row in enumerate(input_rows):
        arm_order = list(ARM_ORDER)
        rng.shuffle(arm_order)
        for arm_position, arm in enumerate(arm_order):
            entries.append({
                "execution_index": len(entries),
                "sample_order_index": sample_order_index,
                "sample_id": str(row["sample_id"]),
                "arm": arm,
                "arm_order_within_sample": arm_position,
            })
    canonical = json.dumps(
        entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    schedule_sha256 = _sha256_text(canonical)
    return {
        "schema_version": "sep_c3_targeted_refinement_schedule@1.0.0",
        "suite_id": SUITE_ID,
        "scheme": SCHEDULE_SCHEME,
        "seed_material": SCHEDULE_SEED_MATERIAL,
        "interleaving": {
            "level": "sample_level",
            "arms_per_block": len(ARM_ORDER),
            "block_count": len(input_rows),
            "arm_order_regenerated_per_sample": True,
        },
        "arms": ARM_ORDER,
        "samples_per_arm": len(input_rows),
        "planned_calls": len(input_rows) * len(ARM_ORDER),
        "input_path": _relative(core.ESTG_INPUT),
        "input_sha256": _sha256_file(core.ESTG_INPUT),
        "entries": entries,
        "schedule_sha256": schedule_sha256,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def _estimate_input_tokens(
    input_rows: Sequence[Mapping[str, str]],
) -> dict[str, int]:
    per_arm: dict[str, int] = {}
    for arm in ARM_ORDER:
        total = 0
        prompt = rp.render_refinement_prompt(arm)
        for row in input_rows:
            body = {
                "model": core.MODEL_ALIAS,
                "messages": prompt.request_messages(
                    str(row["sample_id"]), str(row["text"])
                ),
                "temperature": core.TEMPERATURE,
                "top_p": core.TOP_P,
                "max_tokens": core.MAX_TOKENS,
                "stream": False,
                "thinking": {"type": "disabled"},
            }
            body_bytes = json.dumps(
                body, ensure_ascii=False, sort_keys=True
            ).encode("utf-8")
            total += math.ceil(len(body_bytes) / 3)
        per_arm[arm] = total
    return per_arm


def build_budget(
    schedule: Mapping[str, Any],
    *,
    input_rows: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    prompt_manifest = _read_json(PROMPT_MANIFEST)
    arm_compositions = {
        arm: prompt_manifest["arms"][arm]["composition_sha256"]
        for arm in ARM_ORDER
    }
    estimated = _estimate_input_tokens(input_rows)
    return {
        "schema_version": "sep_c3_targeted_refinement_budget@1.0.0",
        "suite_id": SUITE_ID,
        "status": "prepared_not_run",
        "purpose": (
            "Development/mechanism-oriented targeted refinement on the frozen "
            "EStG-150: common+E baseline A plus independently switchable R_A, "
            "R_C, and R_A+R_C."
        ),
        "base_suite_id": "SEP-C3-MODULAR-ESJ-001",
        "arms": ARM_ORDER,
        "arm_definitions": {
            "A": "common + E (frozen 100 baseline)",
            "B": "common + E + R_A",
            "C": "common + E + R_C",
            "D": "common + E + R_A + R_C",
        },
        "samples_per_arm": schedule["samples_per_arm"],
        "planned_calls": schedule["planned_calls"],
        "call_cap": CALL_CAP,
        "estimated_input_tokens": sum(estimated.values()),
        "estimated_input_tokens_per_arm": estimated,
        "input_token_cap": INPUT_TOKEN_CAP,
        "output_token_cap": OUTPUT_TOKEN_CAP,
        "usd_cost_cap": USD_COST_CAP,
        "repeat_strategy": {
            "repeat_id": "repeat-01",
            "repeats_per_arm": 1,
            "note": "One repeat per arm as specified for this refinement round.",
        },
        "model": {
            "id": core.MODEL_ALIAS,
            "documented_release": core.MODEL_RELEASE,
            "provider": "openai_compatible",
        },
        "inference": {
            "temperature": core.TEMPERATURE,
            "top_p": core.TOP_P,
            "max_tokens": core.MAX_TOKENS,
            "retry": 0,
            "stream": False,
            "thinking": {"type": "disabled"},
            "response_format": None,
        },
        "data_binding": {
            "input_path": _relative(core.ESTG_INPUT),
            "input_sha256": _sha256_file(core.ESTG_INPUT),
            "gold_path": _relative(core.FORMAL_GOLD),
            "gold_sha256": _sha256_file(core.FORMAL_GOLD),
        },
        "prompt_binding": {
            "prompt_family": "direct_llm_refinement_v1",
            "generated_manifest": _relative(PROMPT_MANIFEST),
            "generated_manifest_sha256": _sha256_file(PROMPT_MANIFEST),
            "baseline_100_composition_sha256": prompt_manifest[
                "baseline_100"
            ]["composition_sha256"],
            "arm_composition_sha256": arm_compositions,
        },
        "schedule_binding": {
            "path": _relative(SCHEDULE_PATH),
            "sha256": schedule["schedule_sha256"],
            "scheme": schedule["scheme"],
            "level": schedule["interleaving"]["level"],
        },
        "parser_binding": {
            "schema_adapter_module": _relative(PARSER_ADAPTER),
            "schema_adapter_sha256": _sha256_file(PARSER_ADAPTER),
            "span_canonicalizer_module": _relative(PARSER_CANONICALIZER),
            "span_canonicalizer_sha256": _sha256_file(PARSER_CANONICALIZER),
        },
        "evaluator_binding": {
            "coarse_metric_module": _relative(EVALUATOR_COARSE),
            "coarse_metric_sha256": _sha256_file(EVALUATOR_COARSE),
            "frozen_evaluator_module": _relative(EVALUATOR_FROZEN),
            "frozen_evaluator_sha256": _sha256_file(EVALUATOR_FROZEN),
            "primary_metric": "coarse_five_field_mean_f1",
            "method_id_prefix": "direct_llm_refinement_",
        },
        "failure_policy": (
            "Persist failed attempts in the 150-sample denominator; one recorded "
            "send per scheduled sample/arm; no result-dependent retry."
        ),
        "price_snapshot": dict(PRICE_SNAPSHOT),
        "actuals": None,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def _baseline_config() -> dict[str, Any]:
    return {
        "runner": "scripts/run_sep_c3_modular_ablation_v1.py",
        "prompt_family": "direct_llm_modular_v1",
        "baseline_arm_esj": "100",
        "model": {
            "id": core.MODEL_ALIAS,
            "documented_release": core.MODEL_RELEASE,
            "provider": "openai_compatible",
        },
        "sampling": {
            "temperature": core.TEMPERATURE,
            "top_p": core.TOP_P,
            "max_tokens": core.MAX_TOKENS,
            "retry": 0,
            "stream": False,
            "thinking": {"type": "disabled"},
            "response_format": None,
        },
        "data_binding": {
            "input_path": _relative(core.ESTG_INPUT),
            "input_sha256": _sha256_file(core.ESTG_INPUT),
            "gold_path": _relative(core.FORMAL_GOLD),
            "gold_sha256": _sha256_file(core.FORMAL_GOLD),
        },
        "parser_binding": {
            "schema_adapter_module": _relative(PARSER_ADAPTER),
            "schema_adapter_sha256": _sha256_file(PARSER_ADAPTER),
            "span_canonicalizer_module": _relative(PARSER_CANONICALIZER),
            "span_canonicalizer_sha256": _sha256_file(PARSER_CANONICALIZER),
        },
        "evaluator_binding": {
            "coarse_metric_module": _relative(EVALUATOR_COARSE),
            "coarse_metric_sha256": _sha256_file(EVALUATOR_COARSE),
            "frozen_evaluator_module": _relative(EVALUATOR_FROZEN),
            "frozen_evaluator_sha256": _sha256_file(EVALUATOR_FROZEN),
            "primary_metric": "coarse_five_field_mean_f1",
        },
    }


def build_config_diff(
    budget: Mapping[str, Any],
    schedule: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = _baseline_config()
    refinement_evaluator = dict(budget["evaluator_binding"])
    refinement_evaluator.pop("method_id_prefix", None)
    refinement = {
        "runner": "scripts/run_sep_c3_targeted_refinement_v1.py",
        "prompt_family": "direct_llm_refinement_v1",
        "arms": ARM_ORDER,
        "model": dict(budget["model"]),
        "sampling": dict(budget["inference"]),
        "data_binding": dict(budget["data_binding"]),
        "parser_binding": dict(budget["parser_binding"]),
        "evaluator_binding": refinement_evaluator,
        "schedule": {
            "path": _relative(SCHEDULE_PATH),
            "sha256": schedule["schedule_sha256"],
            "scheme": schedule["scheme"],
            "level": schedule["interleaving"]["level"],
        },
    }
    identity_checks = {
        "model_identical": baseline["model"] == refinement["model"],
        "sampling_identical": baseline["sampling"] == refinement["sampling"],
        "data_binding_identical": (
            baseline["data_binding"] == refinement["data_binding"]
        ),
        "parser_binding_identical": (
            baseline["parser_binding"] == refinement["parser_binding"]
        ),
        "evaluator_binding_identical": (
            baseline["evaluator_binding"] == refinement["evaluator_binding"]
        ),
    }
    non_prompt_differences = [
        key for key, value in identity_checks.items() if not value
    ]
    return {
        "schema_version": "sep_c3_targeted_refinement_config_diff@1.0.0",
        "status": "pass" if not non_prompt_differences else "fail",
        "baseline": baseline,
        "refinement": refinement,
        "identity_checks": identity_checks,
        "non_prompt_differences": non_prompt_differences,
        "prompt_only_changes": {
            "prompt_family": "direct_llm_modular_v1 -> direct_llm_refinement_v1",
            "baseline_arm": "100 -> A",
            "repair_arms_added": ["B (R_A)", "C (R_C)", "D (R_A+R_C)"],
            "s_included": False,
            "j_included": False,
        },
    }


def prepare(*, overwrite: bool = False) -> dict[str, Any]:
    prompt_audit = _read_json(PROMPT_AUDIT_PATH)
    if prompt_audit.get("status") != "pass":
        raise PrepareError("prompt audit is not pass; refusing to prepare run")
    input_rows = core.samples(SAMPLES_PER_ARM)
    schedule = build_schedule(input_rows)
    budget = build_budget(schedule, input_rows=input_rows)
    config_diff = build_config_diff(budget, schedule)

    def stable(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: stable(item)
                for key, item in value.items()
                if key != "generated_at_utc"
            }
        if isinstance(value, list):
            return [stable(item) for item in value]
        return value

    for path, value in (
        (SCHEDULE_PATH, schedule),
        (BUDGET_PATH, budget),
        (CONFIG_DIFF_PATH, config_diff),
    ):
        if path.exists():
            existing = _read_json(path)
            if stable(existing) == stable(value):
                continue
            if not overwrite:
                raise PrepareError(
                    f"{path} exists with different contents; use --overwrite "
                    "only if no run has started"
                )
        _write_json(path, value)

    report = {
        "schema_version": "sep_c3_targeted_refinement_prepare_audit@1.0.0",
        "status": (
            "pass" if config_diff["status"] == "pass" else "fail"
        ),
        "network_calls": 0,
        "suite_id": SUITE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "prompt_audit": _relative(PROMPT_AUDIT_PATH),
        "schedule_path": _relative(SCHEDULE_PATH),
        "schedule_sha256": schedule["schedule_sha256"],
        "budget_path": _relative(BUDGET_PATH),
        "config_diff_path": _relative(CONFIG_DIFF_PATH),
        "estimated_input_tokens": budget["estimated_input_tokens"],
        "interleaving": schedule["interleaving"],
        "statuses": {
            "prompt_audit_pass": prompt_audit.get("status") == "pass",
            "config_diff_pass": config_diff["status"] == "pass",
            "schedule_call_count_600": schedule["planned_calls"] == PLANNED_CALLS,
            "budget_call_count_600": budget["planned_calls"] == PLANNED_CALLS,
        },
    }
    _write_json(PREPARE_REPORT_PATH, report)
    return report


def validate() -> dict[str, Any]:
    schedule = _read_json(SCHEDULE_PATH)
    budget = _read_json(BUDGET_PATH)
    config_diff = _read_json(CONFIG_DIFF_PATH)
    errors: list[str] = []
    if schedule.get("planned_calls") != PLANNED_CALLS:
        errors.append("schedule planned_calls != 600")
    if budget.get("planned_calls") != PLANNED_CALLS:
        errors.append("budget planned_calls != 600")
    if sorted((e.get("arm") for e in schedule.get("entries") or [])) != sorted(
        ARM_ORDER * SAMPLES_PER_ARM
    ):
        errors.append("schedule does not contain 150 entries for each arm")
    if schedule.get("schedule_sha256") != (
        _sha256_text(json.dumps(
            schedule.get("entries") or [],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ))
    ):
        errors.append("schedule_sha256 invalid")
    if config_diff.get("status") != "pass":
        errors.append("config diff status != pass")
    if budget.get("schedule_binding", {}).get("sha256") != schedule.get(
        "schedule_sha256"
    ):
        errors.append("budget schedule_binding mismatch")
    prompt_manifest_sha = _sha256_file(PROMPT_MANIFEST)
    if budget.get("prompt_binding", {}).get(
        "generated_manifest_sha256"
    ) != prompt_manifest_sha:
        errors.append("budget prompt manifest hash mismatch")
    if budget.get("data_binding", {}).get("input_sha256") != _sha256_file(
        core.ESTG_INPUT
    ):
        errors.append("budget input hash mismatch")
    if budget.get("data_binding", {}).get("gold_sha256") != _sha256_file(
        core.FORMAL_GOLD
    ):
        errors.append("budget Gold hash mismatch")
    return {"status": "pass" if not errors else "fail", "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare and validate SEP-C3 targeted-refinement schedule/budget."
    )
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.prepare and not args.check:
        args.prepare = True
        args.check = True
    if args.prepare:
        report = prepare(overwrite=args.overwrite)
        print(json.dumps({
            "status": report["status"],
            "schedule": report["schedule_path"],
            "budget": report["budget_path"],
            "interleaving": report["interleaving"],
            "errors": [],
        }, ensure_ascii=False, indent=2))
        if report["status"] != "pass":
            return 1
    if args.check:
        result = validate()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "pass" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
