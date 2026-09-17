# -*- coding: utf-8 -*-
"""SEP-C3 incremental full-factorial completion runner (missing E/S/J cells).

Combination order is E/S/J, as fixed by
``prompts/sun_compat/modular_v1/README.md`` and ``modular_prompt.py``:

  111 = E=1 S=1 J=1 (full modular prompt; already executed)
  011 = E=0 S=1 J=1 (delete examples; already executed)
  101 = E=1 S=0 J=1 (delete semantic rules; already executed)
  110 = E=1 S=1 J=0 (delete output organization; already executed)
  100 = E=1 S=0 J=0 (new)
  010 = E=0 S=1 J=0 (new)
  001 = E=0 S=0 J=1 (new)
  000 = E=0 S=0 J=0 (new)

This runner is an adapter over the existing
``run_sep_c3_modular_ablation_v1`` implementation.  It does not clone the
calling/parsing/evaluation stack.  The original v1 runner keeps its legacy
four-arm defaults and historical report paths unchanged.

ZERO network by default.  Real sends require ``--execute --allow-llm`` and the
v2 budget file.  No real request is made by an offline check or by the tests.
"""

from __future__ import annotations

import argparse
import json
import os
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


EXISTING_ARMS = ("111", "011", "101", "110")
NEW_ARMS = ("000", "001", "010", "100")
FULL_FACTORIAL_ARMS = EXISTING_ARMS + ("100", "010", "001", "000")

BUDGET_PATH = ROOT / "configs" / "sep_c3_modular_ablation_budget_v2.json"
OFFLINE_REPORT = (
    ROOT / "outputs" / "reports" / "sep_c3_modular_ablation_v2_offline_check.json"
)
RESULT_REPORT = ROOT / "outputs" / "reports" / "sep_c3_modular_ablation_v2.json"
RESULT_MD = ROOT / "outputs" / "reports" / "sep_c3_modular_ablation_v2.md"
OUT_DIR = ROOT / "outputs" / "development" / "sep_c3_modular_ablation_v2"
V1_EVIDENCE_DIR = (
    ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v1"
)
RUN_LOCK = OUT_DIR / ".sep_c3_modular_ablation_v2.run.lock"

PLANNED_CALLS = 600
CALL_CAP = 750
SAMPLES_PER_ARM = 150


class SepC3V2Error(RuntimeError):
    """One of the incremental full-factorial suite preconditions failed."""


def _read_json(path: Path) -> dict[str, Any]:
    return core._read_json(path)


def _write_json(path: Path, value: Any) -> None:
    core._write_json(path, value)


def _sha256_file(path: Path) -> str:
    return core._sha256_file(path)


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _count_jsonl(path: Path) -> int:
    return len(core._read_jsonl(path))


def validate_suite_config() -> dict[str, Any]:
    """Fail closed if the v2 budget or inherited code path drifts."""
    budget = _read_json(BUDGET_PATH)
    if budget.get("planned_arms_esj") != list(NEW_ARMS):
        raise SepC3V2Error("v2 budget planned_arms_esj mismatch")
    if budget.get("existing_arms_esj") != list(EXISTING_ARMS):
        raise SepC3V2Error("v2 budget existing_arms_esj mismatch")
    if budget.get("full_factorial_arms_esj") != list(FULL_FACTORIAL_ARMS):
        raise SepC3V2Error("v2 budget full_factorial_arms_esj mismatch")
    if int(budget.get("samples_per_arm", 0)) != SAMPLES_PER_ARM:
        raise SepC3V2Error("v2 budget samples_per_arm mismatch")
    if int(budget.get("planned_calls", 0)) != PLANNED_CALLS:
        raise SepC3V2Error("v2 budget planned_calls mismatch")
    if int(budget.get("call_cap", 0)) != CALL_CAP:
        raise SepC3V2Error("v2 budget call_cap mismatch")

    model = budget.get("model") or {}
    if model.get("id") != core.MODEL_ALIAS:
        raise SepC3V2Error("v2 budget model id differs from runner")
    inference = budget.get("inference") or {}
    expected_inference = {
        "temperature": core.TEMPERATURE,
        "top_p": core.TOP_P,
        "max_tokens": core.MAX_TOKENS,
        "retry": 0,
        "stream": False,
        "thinking": {"type": "disabled"},
        "response_format": None,
    }
    if inference != expected_inference:
        raise SepC3V2Error("v2 budget inference settings differ from runner")

    data = budget.get("data_binding") or {}
    if data.get("input_sha256") != _sha256_file(core.ESTG_INPUT):
        raise SepC3V2Error("v2 budget input hash no longer matches dataset")
    if data.get("gold_sha256") != _sha256_file(core.FORMAL_GOLD):
        raise SepC3V2Error("v2 budget gold hash no longer matches Gold")
    evaluator = budget.get("evaluator_binding") or {}
    coarse_module = ROOT / str(evaluator.get("coarse_metric_module") or "")
    if not coarse_module.is_file() or evaluator.get("coarse_metric_sha256") != _sha256_file(coarse_module):
        raise SepC3V2Error("v2 budget coarse evaluator binding mismatch")
    frozen_module = ROOT / str(evaluator.get("frozen_evaluator_module") or "")
    if not frozen_module.is_file() or evaluator.get("frozen_evaluator_sha256") != _sha256_file(frozen_module):
        raise SepC3V2Error("v2 budget frozen evaluator binding mismatch")

    for arm in FULL_FACTORIAL_ARMS:
        prompt = core._prompt(arm)
        for index, key in enumerate(("E", "S", "J")):
            if bool(prompt.flags[key]) != (arm[index] == "1"):
                raise SepC3V2Error(f"prompt flag mismatch for {arm}/{key}")
    return budget


def plan_summary() -> dict[str, Any]:
    """Return a zero-network, resume-aware cost/action summary."""
    validate_suite_config()
    rows = core.samples(SAMPLES_PER_ARM)
    per_arm: dict[str, Any] = {}
    for arm in NEW_ARMS:
        run_dir = OUT_DIR / arm / "repeat-01"
        raw = _count_jsonl(run_dir / "raw_responses.jsonl")
        ledger = _count_jsonl(run_dir / "calls_ledger.jsonl")
        per_arm[arm] = {
            "completed_rows": raw,
            "ledger_rows": ledger,
            "estimated_new_sends": max(0, len(rows) - raw),
            "in_doubt": max(0, ledger - raw),
        }
    return {
        "network_calls": 0,
        "suite_id": "SEP-C3-MODULAR-ESJ-002",
        "model": core.MODEL_ALIAS,
        "documented_release": core.MODEL_RELEASE,
        "planned_arms_esj": list(NEW_ARMS),
        "existing_arms_esj": list(EXISTING_ARMS),
        "records_per_arm": len(rows),
        "planned_records_total": len(NEW_ARMS) * len(rows),
        "planned_new_sends_total": sum(v["estimated_new_sends"] for v in per_arm.values()),
        "out_dir": _relative(OUT_DIR),
        "per_arm": per_arm,
    }


class SuiteRunLock:
    """Atomic same-directory lock to prevent duplicate parallel batches."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.acquired = False

    def __enter__(self) -> "SuiteRunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            existing = ""
            try:
                existing = self.path.read_text(encoding="utf-8").strip()
            except OSError:
                pass
            raise SepC3V2Error(
                f"run lock already exists: {_relative(self.path)}; "
                f"another batch may be running or the lock is stale. "
                f"Lock content: {existing!r}"
            ) from exc
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "pid": os.getpid(),
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "suite_id": "SEP-C3-MODULAR-ESJ-002",
                "planned_arms_esj": list(NEW_ARMS),
            }, ensure_ascii=False) + "\n")
        self.acquired = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.acquired:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
        self.acquired = False


def offline_check() -> dict[str, Any]:
    """Audit all eight prompts/request plans while planning four new cells."""
    validate_suite_config()
    report = core.offline_check(
        arms=FULL_FACTORIAL_ARMS,
        execution_arms=NEW_ARMS,
        planned_calls=PLANNED_CALLS,
        call_cap=CALL_CAP,
        samples_per_arm=SAMPLES_PER_ARM,
        output_path=OFFLINE_REPORT,
    )
    report["schema_version"] = "sep_c3_modular_ablation_offline_check@2.0.0"
    report["suite_id"] = "SEP-C3-MODULAR-ESJ-002"
    report["existing_arms_esj"] = list(EXISTING_ARMS)
    report["planned_arms_esj"] = list(NEW_ARMS)
    report["full_factorial_arms_esj"] = list(FULL_FACTORIAL_ARMS)
    _write_json(OFFLINE_REPORT, report)
    return report


def _load_arm_evaluation(arm: str, base_dir: Path) -> dict[str, Any]:
    eval_path = base_dir / arm / "repeat-01" / "evaluation.json"
    manifest_path = base_dir / arm / "repeat-01" / "manifest.json"
    evaluation_doc = _read_json(eval_path)
    manifest = _read_json(manifest_path)
    evaluation = evaluation_doc["evaluation"]
    return {
        "source": _relative(eval_path),
        "manifest": _relative(manifest_path),
        "actual_call_count": int(manifest.get("actual_call_count", 0)),
        "resumed_completed_count": int(manifest.get("resumed_completed_count", 0)),
        "failed_count": int(manifest.get("failed_count", 0)),
        "denominator": int(evaluation_doc.get("denominator", 0)),
        "coarse_five_field_mean_f1": evaluation.get("coarse_five_field_mean_f1"),
        "coarse_five_field_micro_f1": (
            (evaluation.get("coarse_five_field_micro") or {}).get("f1")
        ),
        "modality_label_macro_f1": (
            (evaluation.get("modality_labels") or {}).get("macro_f1")
        ),
        "five_fields": evaluation.get("five_fields") or {},
        "generated_prompt_sha256": (
            (manifest.get("prompt_hashes") or {}).get("generated_prompt_sha256")
        ),
        "composition_sha256": (
            (manifest.get("prompt_hashes") or {}).get("composition_sha256")
        ),
    }


def _metric_from_execute_result(arm: str, result: Mapping[str, Any]) -> dict[str, Any]:
    for run in result.get("runs", []):
        if run.get("arm") == arm:
            return {
                "source": f"{_relative(OUT_DIR)}/{arm}/repeat-01",
                "manifest": f"{_relative(OUT_DIR)}/{arm}/repeat-01/manifest.json",
                "actual_call_count": int(run.get("actual_call_count", 0)),
                "resumed_completed_count": int(run.get("resumed_completed_count", 0)),
                "failed_count": int(run.get("failed_count", 0)),
                "denominator": None,
                "coarse_five_field_mean_f1": run.get("coarse_five_field_mean_f1"),
                "coarse_five_field_micro_f1": run.get("coarse_five_field_micro_f1"),
                "modality_label_macro_f1": run.get("modality_label_macro_f1"),
            }
    raise SepC3V2Error(f"execute result has no run for arm {arm}")


def _new_arm_metric(arm: str, result: Mapping[str, Any] | None) -> dict[str, Any]:
    if result is not None:
        metric = _metric_from_execute_result(arm, result)
        # Fill denominator from the persisted evaluation if present.
        try:
            metric["denominator"] = int(
                _read_json(OUT_DIR / arm / "repeat-01" / "evaluation.json")
                .get("denominator", 0)
            )
        except Exception:
            metric["denominator"] = SAMPLES_PER_ARM
        return metric
    return _load_arm_evaluation(arm, OUT_DIR)


def _factorial_effects(metrics: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    cells: dict[str, float] = {}
    for arm in FULL_FACTORIAL_ARMS:
        value = metrics.get(arm, {}).get("coarse_five_field_mean_f1")
        if value is None:
            raise SepC3V2Error(f"cannot compute effects without metric for {arm}")
        cells[arm] = float(value)

    def level_mean(key: str, value: str) -> float:
        selected = [cells[arm] for arm in FULL_FACTORIAL_ARMS if arm[("E", "S", "J").index(key)] == value]
        return sum(selected) / len(selected)

    return {
        "E_main_effect": round(level_mean("E", "1") - level_mean("E", "0"), 8),
        "S_main_effect": round(level_mean("S", "1") - level_mean("S", "0"), 8),
        "J_main_effect": round(level_mean("J", "1") - level_mean("J", "0"), 8),
        "two_way_ES": round(
            (cells["111"] - cells["101"]) - (cells["011"] - cells["001"]), 8),
        "two_way_EJ": round(
            (cells["111"] - cells["011"]) - (cells["101"] - cells["001"]), 8),
        "two_way_SJ": round(
            (cells["111"] - cells["110"]) - (cells["011"] - cells["010"]), 8),
        "three_way_ESJ": round(
            (cells["111"] - cells["101"] - cells["011"] + cells["001"])
            - (cells["110"] - cells["100"] - cells["010"] + cells["000"]),
            8,
        ),
    }


def build_full8_report(result: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build the full eight-cell comparison without modifying v1 evidence."""
    metrics: dict[str, Any] = {}
    for arm in EXISTING_ARMS:
        metrics[arm] = _load_arm_evaluation(arm, V1_EVIDENCE_DIR)
        metrics[arm]["binding"] = "original_execution_binding"
    for arm in NEW_ARMS:
        metrics[arm] = _new_arm_metric(arm, result)
        metrics[arm]["binding"] = "current_implementation_binding"

    full = metrics["111"].get("coarse_five_field_mean_f1")
    deltas: dict[str, Any] = {}
    for arm in FULL_FACTORIAL_ARMS:
        value = metrics[arm].get("coarse_five_field_mean_f1")
        delta = {}
        if value is not None and full is not None:
            delta["vs_full_111"] = round(float(value) - float(full), 8)
        deltas[arm] = delta

    report = {
        "schema_version": "sep_c3_modular_ablation_full8_report@1.0.0",
        "run_status": "complete_full8" if all(
            metrics[arm].get("coarse_five_field_mean_f1") is not None
            for arm in FULL_FACTORIAL_ARMS
        ) else "partial",
        "suite_id": "SEP-C3-MODULAR-ESJ-002",
        "network_calls_in_this_report": 0,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": {
            "id": core.MODEL_ALIAS,
            "documented_release": core.MODEL_RELEASE,
            "temperature": core.TEMPERATURE,
            "top_p": core.TOP_P,
            "max_tokens": core.MAX_TOKENS,
            "retry": 0,
            "stream": False,
            "thinking": {"type": "disabled"},
        },
        "primary_metric": "coarse_five_field_mean_f1",
        "binding": {
            "existing_arms_esj": list(EXISTING_ARMS),
            "new_arms_esj": list(NEW_ARMS),
            "existing_metric_source": _relative(V1_EVIDENCE_DIR),
            "new_metric_source": _relative(OUT_DIR),
        },
        "metrics": metrics,
        "deltas": deltas,
        "factorial_effects": _factorial_effects(metrics),
        "interpretation": {
            "n_repeats_per_arm": 1,
            "warning": (
                "The original four cells came from the earlier "
                "SEP-C3-MODULAR-ESJ-001 API batch; the four new cells are an "
                "incremental later batch. Model/release/settings/prompt family "
                "are matched, but batch/time is not. Treat pooled eight-cell "
                "effects as descriptive unless this confound is explicitly "
                "modelled or all eight cells are rerun in one batch."
            ),
            "modality": (
                "Modality labels are reported separately and are not folded "
                "into the coarse five-field primary metric."
            ),
        },
    }
    _write_json(RESULT_REPORT, report)
    _write_full8_markdown(report)
    return report


def _write_full8_markdown(report: Mapping[str, Any]) -> None:
    lines = [
        "# SEP-C3 modular E/S/J full 2^3 ablation",
        "",
        f"- status: {report.get('run_status')}",
        f"- model: {report['model']['id']} ({report['model']['documented_release']})",
        f"- primary metric: `{report['primary_metric']}`",
        "- existing four cells: original execution binding",
        "- new four cells: current implementation binding",
        "- warning: batch/time is confounded between the original four cells and the new four cells.",
        "",
        "| E S J | mean F1 | micro F1 | modality macro-F1 | failed | delta vs 111 | binding |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for arm in FULL_FACTORIAL_ARMS:
        metric = report["metrics"][arm]
        delta = report["deltas"][arm].get("vs_full_111")
        lines.append(
            f"| {arm} | {metric.get('coarse_five_field_mean_f1')} | "
            f"{metric.get('coarse_five_field_micro_f1')} | "
            f"{metric.get('modality_label_macro_f1')} | "
            f"{metric.get('failed_count')} | {delta} | {metric.get('binding')} |"
        )
    lines += [
        "",
        "```json",
        json.dumps(report["factorial_effects"], ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    RESULT_MD.write_text(
        "\n".join(lines).rstrip("\n") + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_result_report_full8(result: Mapping[str, Any]) -> None:
    build_full8_report(result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline-check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument(
        "--project-env", action="store_true",
        help="load project .env through the existing LLMConfig fallback; "
             "secrets are never printed",
    )
    args = parser.parse_args()

    if args.offline_check:
        report = offline_check()
        print(json.dumps({
            "status": report["status"],
            "suite_id": report["suite_id"],
            "audit_arms": report["audit_arms"],
            "execution_arms": report["execution_arms"],
            "planned_calls": report["planned_calls"],
            "estimated_total_input_tokens_all8": report["estimated_total_input_tokens"],
            "estimated_execution_input_tokens_missing4": report["estimated_execution_input_tokens"],
            "checks": report["checks"],
        }, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "pass" else 1

    if not args.allow_llm:
        print("refusing real execution without --allow-llm", file=sys.stderr)
        return 2
    try:
        validate_suite_config()
        plan = plan_summary()
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        with SuiteRunLock(RUN_LOCK):
            result = core.execute(
                project_env=args.project_env,
                arms=NEW_ARMS,
                out_dir=OUT_DIR,
                budget_path=BUDGET_PATH,
                planned_calls=PLANNED_CALLS,
                call_cap=CALL_CAP,
                samples_per_arm=SAMPLES_PER_ARM,
                result_writer=_write_result_report_full8,
            )
    except Exception as exc:  # noqa: BLE001
        print(f"EXECUTION ABORTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

    if not result.get("complete"):
        print(f"INCOMPLETE: {result.get('abort_reason') or 'partial run'}",
              file=sys.stderr)
        return 3
    print(
        "SEP-C3 modular full-factorial completion finished: "
        f"{result['actual_calls']} new sends, "
        f"{result['completed_samples']}/600 durable completed samples"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
