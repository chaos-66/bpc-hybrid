# -*- coding: utf-8 -*-
"""Stage 2 -> Stage 3 downstream paired comparison (S3.10 core).

One frozen Stage 3, several Stage 2 rule sources.  This is the experiment that
supports the paper's central claim shape: "does a Stage 2 improvement change
what the downstream compliance checker finds?"

Arms
----
``rules_only``   the locked non-LLM Stage-2 capsule
                 (``data/predictions/gdpr7_sun_rule_only_v1``).
``human_rules``  the formal GDPR-7 Gold Rule Records capsule
                 (user-confirmed 74 sentences / 92 items) -- the Oracle
                 standard answer, i.e. the upper bound of Stage 2 quality.
``direct_llm``   the Direct-LLM Stage-2 capsule
                 (``data/predictions/gdpr7_direct_llm_v1``); only exists after
                 the authorized real run + explicit promotion, so it is
                 reported as ``blocked`` until then (never fabricated).

Surfaces (never merged)
-----------------------
1. the frozen 33-item human-adjudicated violation decision Gold on the 7 frozen
   GDPR processes, with the frozen Sun-style detector;
2. the 40-variant synthetic controlled-error panel v2 (development-only) with
   each of the four frozen similarity backends and the paired control/variant
   evaluation.

Everything is shared and frozen: processes, thresholds, evaluator, Gold.  Only
the rule source changes, so any difference is attributable to Stage 2.

Zero LLM/API/network.  Existing predictions and reports are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_gdpr_3type_linkage_v1 as linkage  # noqa: E402
import run_gdpr_s2_s3_linkage_v1 as panel_runner  # noqa: E402
import run_s3_extended_violation_panel_v2 as ext  # noqa: E402
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    evaluate_extended,
    evaluate_paired,
)

RUN_ID = "s3_downstream_paired_v1"
OUT_ROOT = ROOT / "outputs" / "development" / RUN_ID
REPORT_JSON = ROOT / "outputs" / "reports" / f"{RUN_ID}.json"
REPORT_MD = ROOT / "outputs" / "reports" / f"{RUN_ID}.md"
MANIFEST = ROOT / "outputs" / "reports" / f"{RUN_ID}.manifest.json"

ARM_ORDER = ("rules_only", "human_rules", "direct_llm")
METHODS = ("winter", "sun", "bm25", "tfidf_svd")
CAPSULE_DIRS = {
    "rules_only": ROOT / "data/predictions/gdpr7_sun_rule_only_v1",
    "human_rules": ROOT / "data/predictions/gdpr7_human_rule_record_v1",
    "direct_llm": ROOT / "data/predictions/gdpr7_direct_llm_v1",
}
ARM_NOTES = {
    "rules_only": ("locked non-LLM Stage-2 capsule (B0 v10a); the project's "
                   "non-LLM baseline rule source"),
    "human_rules": ("formal GDPR-7 Gold Rule Records (user-confirmed human "
                    "adjudication); the Stage-2 quality ceiling"),
    "direct_llm": ("Direct-LLM Stage-2 capsule; requires the authorized real run "
                   "and explicit promotion (absent -> reported as blocked)"),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, value: Any, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing artifact: {path}")
    path.write_bytes(data)


def _write_rows(path: Path, rows: Sequence[Mapping[str, Any]],
                overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing artifact: {path}")
    path.write_bytes(("".join(json.dumps(r, ensure_ascii=False) + "\n"
                              for r in rows)).encode("utf-8"))


def arm_availability() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm in ARM_ORDER:
        folder = CAPSULE_DIRS[arm]
        predictions = folder / "predictions.json"
        manifest = folder / "manifest.json"
        available = predictions.is_file() and manifest.is_file()
        out[arm] = {
            "note": ARM_NOTES[arm],
            "capsule_dir": _rel(folder),
            "available": available,
            "predictions_sha256": _sha(predictions) if predictions.is_file() else None,
            "manifest_sha256": _sha(manifest) if manifest.is_file() else None,
            "status": "available" if available else "blocked",
            "blocked_reason": None if available else (
                "capsule not published; the authorized real LLM run and its "
                "explicit promotion have not happened yet"),
        }
    return out


def run_three_types(frozen, rule_ids, arms, write: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm in ARM_ORDER:
        if not arms[arm]["available"]:
            out[arm] = {"status": "blocked",
                        "blocked_reason": arms[arm]["blocked_reason"]}
            continue
        records, diag = linkage.build_rule_records_for_arm(arm, frozen, rule_ids, None)
        rows = linkage.build_violation_rows(arm, frozen, records)
        folder = OUT_ROOT / "original_three" / arm
        if write:
            _write_rows(folder / "predictions.jsonl", rows)
            _write_json(folder / "rule_records.json", records)
        evaluation = linkage.evaluate_rows(rows, linkage.GOLD_VIOLATION)
        if write:
            _write_json(folder / "evaluation.json", evaluation)
        out[arm] = {
            "status": "evaluated",
            "arm_label": linkage.ARM_LABELS[arm],
            "rule_record_source": diag["rule_record_source"],
            "failed_rules": sorted({r["rule_id"] for r in rows
                                    if r["rule_record_failed"]}),
            "evaluation": evaluation["violation"],
            "items": evaluation["items"],
        }
    return out


def run_four_types(frozen, text_by_sample, arms, write: bool) -> dict[str, Any]:
    panel = _read(ext.PANEL)
    gamma_ext = float(panel["config"]["gamma_ext"])
    gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}
    out: dict[str, Any] = {"gamma_ext": gamma_ext, "arms": {}}
    for arm in ARM_ORDER:
        if not arms[arm]["available"]:
            out["arms"][arm] = {"status": "blocked",
                                "blocked_reason": arms[arm]["blocked_reason"]}
            continue
        capsule_doc = _read(CAPSULE_DIRS[arm] / "predictions.json")
        capsule = panel_runner._pred_by_sample(capsule_doc)
        per_method: dict[str, Any] = {}
        for method in METHODS:
            rows, projection = panel_runner.build_arm_predictions(
                method, arm, panel, text_by_sample, capsule, frozen["nlp"], gamma_ext)
            folder = OUT_ROOT / "extended_four" / arm / method
            if write:
                _write_rows(folder / "predictions.jsonl", rows)
            evaluation = evaluate_extended(rows, gold)
            paired = evaluate_paired(rows, panel, gamma_ext)
            if write:
                _write_json(folder / "evaluation.json",
                            {"evaluation": evaluation, "paired": paired,
                             "projection": projection})
            per_method[method] = {
                "evaluation": evaluation,
                "paired": paired,
                "projection": projection,
                "method_display": ext.METHOD_DISPLAY[method],
            }
        out["arms"][arm] = {"status": "evaluated", "methods": per_method}
    return out


def _fmt(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.4f}"
    return "-"


def _delta(new: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("macro_f1", "exact_type_accuracy", "detected", "missed",
            "wrong_type", "unobservable")
    out = {}
    for key in keys:
        a, b = new.get(key), base.get(key)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            out[key] = round(a - b, 6)
    out["per_type_f1"] = {
        t: round(new["per_type"][t]["f1"] - base["per_type"][t]["f1"], 6)
        for t in new.get("per_type", {})
        if t in base.get("per_type", {})
    }
    return out


def build_report(report_body: Mapping[str, Any]) -> dict[str, Any]:
    three = report_body["original_three_types"]
    comparisons: dict[str, Any] = {}
    if three.get("rules_only", {}).get("status") == "evaluated" and \
            three.get("human_rules", {}).get("status") == "evaluated":
        comparisons["human_rules_minus_rules_only"] = _delta(
            three["human_rules"]["evaluation"], three["rules_only"]["evaluation"])
    if three.get("direct_llm", {}).get("status") == "evaluated" and \
            three.get("rules_only", {}).get("status") == "evaluated":
        comparisons["direct_llm_minus_rules_only"] = _delta(
            three["direct_llm"]["evaluation"], three["rules_only"]["evaluation"])
    return {**report_body, "deltas": comparisons}


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Stage 2 → Stage 3 下游配对比较（S3.10 核心，零 API）",
        "",
        f"**run_id**：`{report['run_id']}`",
        f"**状态**：`{report['claim_status']}`",
        "",
        "## 问题",
        "",
        "**同一个冻结的 Stage 3 检查器**，只更换 Stage 2 的规则来源，最终检查结果如何变化？"
        "这是“Stage 2 改进能否传导到最终合规检查”的直接证据。",
        "",
        "## 规则来源（只有这一项变化）",
        "",
        "| 臂 | 状态 | 说明 | 胶囊 sha256 |",
        "|---|---|---|---|",
    ]
    for arm in ARM_ORDER:
        block = report["arms"][arm]
        lines.append(f"| {arm} | {block['status']} | {block['note']} | "
                     f"`{(block['predictions_sha256'] or '-')[:16]}` |")
    lines += [
        "",
        "共享且冻结：7 个 GDPR 流程、阈值（tau/gamma/theta=0.8）、evaluator、Gold。",
        "",
        "## 1. 原三类（33 条人工 violation Gold）",
        "",
        "| 规则来源 | macro-F1 | exact | detected | missed | wrong-type | unobservable |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ARM_ORDER:
        block = report["original_three_types"].get(arm, {})
        if block.get("status") != "evaluated":
            lines.append(f"| {arm} | - | - | - | - | - | - |")
            continue
        ev = block["evaluation"]
        lines.append(f"| {arm} | {ev['macro_f1']:.4f} | {ev['exact_type_accuracy']:.4f} | "
                     f"{ev['detected']} | {ev['missed']} | {ev['wrong_type']} | "
                     f"{ev['unobservable']} |")
    lines += [
        "",
        "### 逐类型 F1",
        "",
        "| 类型 | rules_only | human_rules | direct_llm |",
        "|---|---:|---:|---:|",
    ]
    for check in ("missing_action", "incorrect_actor", "out_of_order"):
        row = [f"| {check} "]
        for arm in ARM_ORDER:
            block = report["original_three_types"].get(arm, {})
            if block.get("status") != "evaluated":
                row.append("| - ")
            else:
                row.append(f"| {block['evaluation']['per_type'][check]['f1']:.3f} ")
        lines.append("".join(row) + "|")
    lines += [
        "",
        "### 变化量（相对 rules_only）",
        "",
        "| 指标 | Δ |",
        "|---|---:|",
    ]
    for name, delta in report["deltas"].items():
        for key, value in delta.items():
            if key == "per_type_f1":
                for check, v in value.items():
                    lines.append(f"| {name}.{check} | {v:+.4f} |")
            else:
                lines.append(f"| {name}.{key} | {value:+.4f} |")
    lines += [
        "",
        "## 2. 四类扩展面板（40 变体 + 40 合规对照）",
        "",
        "| 规则来源 | 后端 | variant exact | macro | control FP rate | paired acc |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for arm in ARM_ORDER:
        block = report["extended_four_types"]["arms"].get(arm, {})
        if block.get("status") != "evaluated":
            lines.append(f"| {arm} | - | - | - | - | - |")
            continue
        for method in METHODS:
            entry = block["methods"][method]
            lines.append(
                f"| {arm} | {entry['method_display']} | "
                f"{_fmt(entry['paired'].get('variant_exact_type_accuracy'))} | "
                f"{_fmt(entry['evaluation'].get('macro_f1'))} | "
                f"{_fmt(entry['paired'].get('control_false_positive_rate'))} | "
                f"{_fmt(entry['paired'].get('paired_accuracy'))} |")
    lines += [
        "",
        "> 四类扩展为 development-only 合成受控面板；Winter/Sun 原论文未定义这四类，"
        "一律写 `Winter-style extension` / `Sun-style extension`。",
        "",
        f"> **面板偏差提示**：{report['conclusion']['panel_bias_note']}",
        "",
        "## 3. 结论边界",
        "",
        f"- {report['conclusion']['statement']}",
        f"- {report['conclusion']['blocked_statement']}",
        f"- {report['conclusion']['panel_bias_note']}",
        "- 合成面板与 33 条人工 Gold 分表，从不合并。",
        "",
        "## 4. 复现",
        "",
        "```powershell",
        report["run_command"],
        "```",
        "",
        "零 LLM/API/网络；未修改 Gold、阈值、流程或既有预测。",
        "",
    ]
    return "\n".join(lines)


def build_manifest(report: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = {}
    for path in sorted(OUT_ROOT.rglob("*")):
        if path.is_file():
            artifacts[_rel(path)] = {"path": _rel(path), "sha256": _sha(path),
                                     "byte_size": path.stat().st_size}
    return {
        "schema_version": "s3_downstream_paired_manifest@1.0.0",
        "run_id": RUN_ID,
        "claim_status": report["claim_status"],
        "task": "S3.10 core: one frozen Stage 3, several Stage 2 rule sources",
        "arms": {arm: {"status": report["arms"][arm]["status"],
                       "predictions_sha256":
                           report["arms"][arm]["predictions_sha256"]}
                 for arm in ARM_ORDER},
        "bindings": report["bindings"],
        "artifacts": artifacts,
        "replay_command": report["run_command"],
        "boundaries": report["boundaries"],
        "zero_api": {"new_llm_api_calls": 0},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    config = _read(linkage.CONFIG)
    frozen = linkage.load_frozen(config)
    text_by_sample = panel_runner._sentence_text_by_sample(_read(linkage.INPUT_PACK))
    rule_ids = sorted(linkage.rule_texts_of(frozen["inference"]))
    arms = arm_availability()
    write = not args.check

    three = run_three_types(frozen, rule_ids, arms, write)
    four = run_four_types(frozen, text_by_sample, arms, write)

    body = {
        "schema_version": "s3_downstream_paired@1.0.0",
        "run_id": RUN_ID,
        "scope": "development_only_frozen_evaluation_surface",
        "claim_status": (
            "Stage-2-source paired comparison on the frozen Stage-3 evaluation "
            "surface; NOT a formal end-to-end result (S2.13 freeze and the "
            "authorized real Direct-LLM batch are still pending)"),
        "question": ("Holding the Stage 3 checker, processes, thresholds, "
                     "evaluator and Gold fixed, does the Stage 2 rule source "
                     "change what the compliance checker finds?"),
        "arms": arms,
        "bindings": {
            "violation_gold": {"path": _rel(linkage.GOLD_VIOLATION),
                               "sha256": _sha(linkage.GOLD_VIOLATION)},
            "inference_pack": {"path": _rel(linkage.INFERENCE_PACK),
                               "sha256": _sha(linkage.INFERENCE_PACK)},
            "stage3_config": {"path": _rel(linkage.CONFIG),
                              "sha256": _sha(linkage.CONFIG)},
            "panel": {"path": _rel(ext.PANEL), "sha256": _sha(ext.PANEL)},
            "thresholds": {"tau": frozen["tau"], "gamma": frozen["gamma"],
                           "theta": frozen["theta"]},
        },
        "original_three_types": three,
        "extended_four_types": four,
        "boundaries": {
            "gold_modified": False,
            "thresholds_changed": False,
            "processes_changed": False,
            "existing_predictions_overwritten": False,
            "llm_or_api_called": False,
            "synthetic_panel_merged_into_human_gold": False,
            "missing_arm_fabricated": False,
        },
        "conclusion": {
            "statement": (
                "Reported per arm; the human-rule arm is the Stage-2 quality "
                "ceiling and the Rules-Only arm is the non-LLM baseline, so the "
                "delta isolates the effect of the rule source on the frozen "
                "checker."),
            "blocked_statement": (
                "The Direct-LLM arm stays blocked until the authorized real "
                "batch runs and its capsule is promoted; no value is imputed."),
            "panel_bias_note": (
                "The 40-variant synthetic panel binds its locked rule elements "
                "to data/development/human_review/stage3_gold_inference_v1.json "
                "(the S3.5 development extraction).  The panel was therefore "
                "built around the development adapter's own six-element reading "
                "and its first-valid-span projection keeps only the FIRST "
                "confirmed item of a multi-item sentence (11/40 variants sit on "
                "multi-item sentences).  Panel numbers are consequently a "
                "biased-comparison surface for the human-rule arm; the unbiased "
                "Oracle surface is the 33-item human Gold reported in section 1 "
                "and in outputs/reports/s3_oracle_gold_rules_v1.json."),
        },
        "run_command": "python formal_experiment/scripts/run_s3_downstream_paired_v1.py",
        "zero_api": {"new_llm_api_calls": 0},
    }
    report = build_report(body)

    if args.check:
        if not REPORT_JSON.is_file():
            print(json.dumps({"mode": "check", "valid": False,
                              "reason": "report missing"}, ensure_ascii=False))
            return 2
        same = json.dumps(_read(REPORT_JSON), ensure_ascii=False, sort_keys=True) == \
            json.dumps(report, ensure_ascii=False, sort_keys=True)
        print(json.dumps({"mode": "check", "valid": same}, ensure_ascii=False))
        return 0 if same else 2

    _write_json(REPORT_JSON, report, overwrite=args.overwrite)
    REPORT_MD.write_text(render_markdown(report), encoding="utf-8")
    _write_json(MANIFEST, build_manifest(report), overwrite=args.overwrite)
    print(json.dumps({
        "run_id": RUN_ID,
        "arms": {arm: arms[arm]["status"] for arm in ARM_ORDER},
        "three_type": {
            arm: (three[arm]["evaluation"]["macro_f1"]
                  if three[arm].get("status") == "evaluated" else None)
            for arm in ARM_ORDER},
        "report": _rel(REPORT_JSON),
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
