# -*- coding: utf-8 -*-
"""Build a zero-network machine-readable audit of the full 2^3 E/S/J suite.

The audit does not claim that the original four cells and the four new cells
were executed in one batch.  It binds both groups to the same model, dataset,
Gold, prompt skeleton, evaluator and denominator, and it records the remaining
batch/time confound explicitly.
"""

from __future__ import annotations

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

import run_sep_c3_modular_ablation_v1 as core  # noqa: E402
import run_sep_c3_modular_ablation_v2 as v2  # noqa: E402
from bpc_hybrid import modular_prompt as mp  # noqa: E402


REPORT_JSON = (
    ROOT / "outputs" / "reports" / "sep_c3_modular_full8_protocol_audit_v1.json"
)
REPORT_MD = (
    ROOT / "outputs" / "reports" / "sep_c3_modular_full8_protocol_audit_v1.md"
)


def _read_json(path: Path) -> dict[str, Any]:
    return core._read_json(path)


def _write_json(path: Path, value: Any) -> None:
    core._write_json(path, value)


def _sha256_file(path: Path) -> str:
    return core._sha256_file(path)


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _prompt_payload(arm: str, texts: Mapping[str, str]) -> dict[str, Any]:
    prompt = core._prompt(arm)
    loaded = core._load_generated_prompt(arm)
    generated_path = mp.generated_path(arm)
    expected = {
        "E": arm[0] == "1",
        "S": arm[1] == "1",
        "J": arm[2] == "1",
    }
    errors: list[str] = []
    if dict(prompt.flags) != expected:
        errors.append("flags do not match ESJ bit string")
    if loaded.system_prompt != prompt.system_prompt:
        errors.append("loader system prompt differs from composer")
    if loaded.user_prompt_template != prompt.user_prompt_template:
        errors.append("loader user prompt differs from composer")
    if generated_path.read_text(encoding="utf-8") != prompt.to_markdown():
        errors.append("generated prompt file differs from deterministic renderer")
    for marker in core.COMMON_BOUNDARY_MARKERS:
        if marker not in prompt.system_prompt:
            errors.append(f"missing common boundary marker: {marker}")
    combined = prompt.system_prompt + "\n" + prompt.user_prompt_template
    for marker in core.OLD_MARKERS:
        if marker in combined:
            errors.append(f"historical marker leaked: {marker}")

    module_location = {"E": prompt.user_prompt_template,
                       "S": prompt.system_prompt,
                       "J": prompt.system_prompt}
    for module, text in texts.items():
        if module not in module_location:
            continue
        present = text.strip() in module_location[module]
        if expected[module] and not present:
            errors.append(f"enabled module {module} source text missing")
        if not expected[module] and present:
            errors.append(f"disabled module {module} source text present")
        marker = core.MODULE_MARKERS[module]
        if not expected[module] and marker in combined:
            errors.append(f"disabled module {module} marker present")

    return {
        "variant": arm,
        "flags": expected,
        "prompt_family": "direct_llm_modular_v1",
        "generated_prompt_path": _relative(generated_path),
        "generated_prompt_sha256": _sha256_file(generated_path),
        "composition_sha256": prompt.composition_sha256,
        "common_source_sha256": prompt.source_hashes["common"],
        "module_source_hashes": {
            "E": prompt.source_hashes["E"],
            "S": prompt.source_hashes["S"],
            "J": prompt.source_hashes["J"],
        },
        "system_sha256": core._sha256_text(prompt.system_prompt),
        "user_sha256": core._sha256_text(prompt.user_prompt_template),
        "errors": errors,
    }


def _existing_arm_binding(arm: str) -> dict[str, Any]:
    manifest_path = v2.V1_EVIDENCE_DIR / "arms" / arm / "manifest.json"
    evaluation_path = v2.V1_EVIDENCE_DIR / "arms" / arm / "evaluation.json"
    row: dict[str, Any] = {
        "variant": arm,
        "status": "existing_executed",
        "binding": "original_execution_binding",
        "evidence_manifest_path": _relative(manifest_path),
        "evidence_evaluation_path": _relative(evaluation_path),
    }
    if not manifest_path.is_file() or not evaluation_path.is_file():
        row["status"] = "missing_evidence"
        return row
    manifest = _read_json(manifest_path)
    evaluation_doc = _read_json(evaluation_path)
    row.update({
        "manifest_sha256": _sha256_file(manifest_path),
        "evaluation_sha256": _sha256_file(evaluation_path),
        "actual_call_count": int(manifest.get("actual_call_count", 0)),
        "resumed_completed_count": int(manifest.get("resumed_completed_count", 0)),
        "failed_count": int(manifest.get("failed_count", 0)),
        "denominator": int(evaluation_doc.get("denominator", 0)),
        "prompt_hashes": manifest.get("prompt_hashes") or {},
    })
    return row


def _new_arm_binding(arm: str) -> dict[str, Any]:
    prompt = core._prompt(arm)
    return {
        "variant": arm,
        "status": "prepared_not_run",
        "binding": "current_implementation_binding",
        "planned_run_dir": _relative(v2.OUT_DIR / arm / "repeat-01"),
        "planned_raw_responses": _relative(
            v2.OUT_DIR / arm / "repeat-01" / "raw_responses.jsonl"),
        "planned_manifest": _relative(
            v2.OUT_DIR / arm / "repeat-01" / "manifest.json"),
        "denominator": v2.SAMPLES_PER_ARM,
        "prompt_sha256": core._sha256_text(prompt.to_markdown()),
        "composition_sha256": prompt.composition_sha256,
    }


def build_report() -> dict[str, Any]:
    budget = v2.validate_suite_config()
    texts = mp.load_module_texts()
    variants = [
        _prompt_payload(arm, texts) for arm in v2.FULL_FACTORIAL_ARMS
    ]
    existing = {
        arm: _existing_arm_binding(arm) for arm in v2.EXISTING_ARMS
    }
    new = {
        arm: _new_arm_binding(arm) for arm in v2.NEW_ARMS
    }

    common_hashes = {row["common_source_sha256"] for row in variants}
    composition_hashes = {row["composition_sha256"] for row in variants}
    prompt_hashes = {row["generated_prompt_sha256"] for row in variants}
    model = {
        "id": core.MODEL_ALIAS,
        "documented_release": core.MODEL_RELEASE,
        "provider": "openai_compatible",
    }
    inference = {
        "temperature": core.TEMPERATURE,
        "top_p": core.TOP_P,
        "max_tokens": core.MAX_TOKENS,
        "retry": 0,
        "stream": False,
        "thinking": {"type": "disabled"},
        "response_format": None,
    }
    evaluator = {
        "coarse_metric_module": "src/bpc_hybrid/sep_c3_modular_evaluation.py",
        "coarse_metric_sha256": _sha256_file(
            ROOT / "src" / "bpc_hybrid" / "sep_c3_modular_evaluation.py"),
        "frozen_evaluator_module": "src/bpc_hybrid/stage2_sun_literal_overlap.py",
        "frozen_evaluator_sha256": _sha256_file(
            ROOT / "src" / "bpc_hybrid" / "stage2_sun_literal_overlap.py"),
        "primary_metric": "coarse_five_field_mean_f1",
        "postprocessing_version": (
            "d1_schema_adapter + span_canonicalizer current implementation; "
            "same call path as the original four cells"
        ),
    }

    existing_prompt_match: dict[str, bool] = {}
    for arm, row in existing.items():
        ph = row.get("prompt_hashes") or {}
        payload = next(v for v in variants if v["variant"] == arm)
        existing_prompt_match[arm] = bool(
            row.get("status") == "existing_executed"
            and ph.get("generated_prompt_sha256") == payload["generated_prompt_sha256"]
            and ph.get("composition_sha256") == payload["composition_sha256"]
            and ph.get("system_sha256") == payload["system_sha256"]
            and ph.get("user_sha256") == payload["user_sha256"]
        )

    checks = {
        "eight_variants_present": len(variants) == 8,
        "all_prompt_audits_clean": all(not row["errors"] for row in variants),
        "flags_match_esj_bits": all(
            row["flags"] == {"E": row["variant"][0] == "1",
                             "S": row["variant"][1] == "1",
                             "J": row["variant"][2] == "1"}
            for row in variants
        ),
        "common_skeleton_identical": len(common_hashes) == 1,
        "eight_composition_hashes_distinct": len(composition_hashes) == 8,
        "eight_generated_prompt_hashes_distinct": len(prompt_hashes) == 8,
        "four_existing_prompt_bindings_match_current": all(
            existing_prompt_match.values()),
        "new_output_dir_differs_from_v1": v2.OUT_DIR != core.OUT_DIR,
        "new_report_paths_differ_from_v1": (
            v2.OFFLINE_REPORT != core.OFFLINE_REPORT
            and v2.RESULT_REPORT != core.RESULT_REPORT
            and v2.RESULT_MD != core.RESULT_MD
        ),
        "input_hash_bound": budget["data_binding"]["input_sha256"]
        == _sha256_file(core.ESTG_INPUT),
        "gold_hash_bound": budget["data_binding"]["gold_sha256"]
        == _sha256_file(core.FORMAL_GOLD),
        "evaluator_hash_bound": evaluator["coarse_metric_sha256"]
        == budget["evaluator_binding"]["coarse_metric_sha256"],
        "denominator_preserved": all(
            (row.get("denominator") == v2.SAMPLES_PER_ARM)
            for row in existing.values() if row.get("status") == "existing_executed"
        ) and all(row["denominator"] == v2.SAMPLES_PER_ARM for row in new.values()),
    }
    status = "pass" if all(checks.values()) else "fail"
    report = {
        "schema_version": "sep_c3_modular_full8_protocol_audit@1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "network_calls": 0,
        "status": status,
        "suite_id": "SEP-C3-MODULAR-ESJ-002",
        "combination_order": ["E", "S", "J"],
        "bit_semantics": {
            "E": "synthetic worked examples (user-prompt module)",
            "S": "semantic interpretation rules (system-prompt module)",
            "J": "output organization / JSON discipline (system-prompt module)",
        },
        "existing_arms_esj": list(v2.EXISTING_ARMS),
        "new_arms_esj": list(v2.NEW_ARMS),
        "full_factorial_arms_esj": list(v2.FULL_FACTORIAL_ARMS),
        "model": model,
        "inference_parameters": inference,
        "denominator": v2.SAMPLES_PER_ARM,
        "data_binding": {
            "input_path": _relative(core.ESTG_INPUT),
            "input_sha256": _sha256_file(core.ESTG_INPUT),
            "gold_path": _relative(core.FORMAL_GOLD),
            "gold_sha256": _sha256_file(core.FORMAL_GOLD),
            "reconstruction_dataset_id": "independently_reconstructed_estg_150_v1",
        },
        "prompt_binding": {
            "prompt_family": "direct_llm_modular_v1",
            "generated_manifest": _relative(mp.generated_manifest_path()),
            "generated_manifest_sha256": _sha256_file(mp.generated_manifest_path()),
            "common_source_sha256": next(iter(common_hashes)),
        },
        "evaluator_binding": evaluator,
        "variants": variants,
        "existing_arm_bindings": existing,
        "new_arm_bindings": new,
        "consistency": {
            "checks": checks,
            "existing_prompt_match": existing_prompt_match,
        },
        "warnings": [
            "The original 111/011/101/110 cells were executed in the earlier "
            "SEP-C3-MODULAR-ESJ-001 batch; 000/001/010/100 will be a later "
            "incremental batch. Model/release/prompt/evaluator settings are "
            "matched, but batch/time is confounded with the factorial cells if "
            "the eight cells are pooled without acknowledging this.",
            "The original 111 arm row was persisted across a process resume "
            "(59 durable rows reused, 91 new sends); the suite manifest records "
            "150/150 total attempts and zero duplicate sample sends.",
            "The four existing cells are original execution binding. The four "
            "new cells are current implementation binding. No historical result "
            "file was rewritten by this audit.",
        ],
    }
    return report


def main() -> int:
    report = build_report()
    _write_json(REPORT_JSON, report)
    lines = [
        "# SEP-C3 full 2^3 protocol audit (zero network)",
        "",
        f"- status: **{report['status']}**",
        f"- suite: `{report['suite_id']}`",
        "- existing cells: `111/011/101/110` (original execution binding)",
        "- new cells: `000/001/010/100` (prepared_not_run)",
        f"- model: `{report['model']['id']}` ({report['model']['documented_release']})",
        f"- denominator: {report['denominator']} per arm",
        "",
        "| variant | E | S | J | prompt SHA256 | status |",
        "|---|---:|---:|---:|---|---|",
    ]
    by_arm = {row["variant"]: row for row in report["variants"]}
    for arm in report["full_factorial_arms_esj"]:
        row = by_arm[arm]
        status = (
            report["existing_arm_bindings"][arm]["status"]
            if arm in report["existing_arm_bindings"]
            else report["new_arm_bindings"][arm]["status"]
        )
        lines.append(
            f"| {arm} | {int(row['flags']['E'])} | {int(row['flags']['S'])} | "
            f"{int(row['flags']['J'])} | `{row['generated_prompt_sha256']}` | {status} |"
        )
    lines += [
        "",
        "## Batch warning",
        "",
        report["warnings"][0],
        "",
    ]
    REPORT_MD.write_text(
        "\n".join(lines).rstrip("\n") + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "status": report["status"],
        "report": _relative(REPORT_JSON),
        "checks": report["consistency"]["checks"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
