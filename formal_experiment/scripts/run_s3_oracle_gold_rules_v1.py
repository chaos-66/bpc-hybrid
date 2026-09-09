# -*- coding: utf-8 -*-
"""Oracle Stage 3: isolate the CHECKER by feeding it the CORRECT rules.

What this run answers
---------------------
RQ3 / EXP-S3-O: "with Gold Rule Records as input, how reliable are the Stage 3
baselines?"  Stage 2 error is removed by construction: the rule records come
from the formal, user-adjudicated GDPR-7 Gold Rule Records
(``data/gold/stage3/gdpr7_gold_rule_records_v1.json``, 9 rules / 74 sentences /
92 rule items) instead of a Stage-2 prediction capsule or the deterministic
development adapter.

Two evaluation surfaces are reported SEPARATELY and are never merged:

1. ``original_three_types`` -- the frozen 33-item human-adjudicated violation
   decision Gold (``stage3_violation_gold_v1.json``, 11 missing_action /
   11 incorrect_actor / 11 out_of_order) on the 7 frozen GDPR processes, using
   the frozen Sun-style detector (``configs/sun_stage3_development_v1.json``,
   tau=gamma=theta=0.8) and the frozen common evaluator.
2. ``extended_four_types`` -- the 40-variant synthetic controlled-error panel
   v2 (development-only; the original papers define no such violation types),
   run with each of the four frozen similarity backends and the shared
   extended/pair evaluator.  This surface is the only one that provides
   COMPLIANT controls, so it is where false-positive behaviour is measurable.

Oracle vs reference
-------------------
``oracle``    : rule records built from the Gold Rule Record capsule (correct
                rules; every confirmed modality included).
``reference`` : the S3.5 development deterministic Rule Record adapter on the
                same rule texts (the historical development baseline).
The pair isolates the Stage-3 contribution: any difference is attributable to
the rule records, because processes, thresholds, evaluator, and Gold are frozen
and shared.

Claim boundary
--------------
This is a Stage-3 ORACLE evaluation on the frozen evaluation surface.  It does
NOT by itself constitute the formal S3.7 main table, which additionally
requires the S2.13 freeze and the S3.4-S3.6 formal promotion; those
dependencies are recorded in ``dependencies`` and are never silently assumed.
Zero LLM/API/network.  Existing predictions, reports and Gold are never
overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
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

RUN_ID = "s3_oracle_gold_rules_v1"
OUT_ROOT = ROOT / "outputs" / "development" / RUN_ID
REPORT_JSON = ROOT / "outputs" / "reports" / f"{RUN_ID}.json"
REPORT_MD = ROOT / "outputs" / "reports" / f"{RUN_ID}.md"
MANIFEST = ROOT / "outputs" / "reports" / f"{RUN_ID}.manifest.json"

GOLD_RULE_RECORDS = ROOT / "data/gold/stage3/gdpr7_gold_rule_records_v1.json"
ORACLE_CAPSULE = (ROOT / "data/predictions/gdpr7_human_rule_record_v1"
                  / "predictions.json")
ORACLE_CAPSULE_MANIFEST = (ROOT / "data/predictions/gdpr7_human_rule_record_v1"
                           / "manifest.json")
CONFIRMED = (ROOT / "data/development/human_review/gdpr7_human_confirmed_v1"
             / "confirmed_rule_items.json")

#: rule_element.field -> the confirmed fields that variant actually exercises.
FIELD_TO_CONFIRMED = {
    "modality+action": ("modality", "action"),
    "action": ("action",),
    "condition": ("condition",),
    "constraint": ("constraint",),
    "exception": ("exception",),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {path}")
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n")
                     .encode("utf-8"))


def _write_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {path}")
    path.write_bytes(("".join(json.dumps(r, ensure_ascii=False) + "\n"
                              for r in rows)).encode("utf-8"))


def _rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


# ---------------------------------------------------------------------------
# Oracle rule records + per-sentence six-element projection
# ---------------------------------------------------------------------------
def build_oracle_rule_records(frozen: Mapping[str, Any],
                              include_modalities=None):
    """Gold-rule -> Sun rule records for the 9 rule ids."""
    rule_ids = sorted(linkage.rule_texts_of(frozen["inference"]))
    if include_modalities is None:
        records, diag = linkage.build_rule_records_for_arm(
            "human_rules", frozen, rule_ids, None)
    else:
        capsule = _read(ORACLE_CAPSULE)
        texts = panel_runner._sentence_text_by_sample(frozen["input_doc"])
        from bpc_hybrid.sun_stage3.gdpr_capsule_converter import (
            build_rule_records as convert,
        )
        records, summary = convert(
            capsule, texts, rule_ids, include_modalities,
            expected_schema=linkage.HUMAN_RULES_CAPSULE_SCHEMA)
        diag = {
            "rule_record_source": (f"EXTERNAL human_rules capsule converter "
                                   f"({summary['converter']})"),
            "arm": "human_rules",
            "capsule_used": True,
            "capsule_path": _rel(ORACLE_CAPSULE),
            "capsule_sha256": _sha(ORACLE_CAPSULE),
            "capsule_schema": capsule.get("schema_version"),
            "capsule_record_count": capsule.get("record_count"),
            "conversion_summary": summary,
            "failed_rules": [rid for rid in rule_ids if records[rid].get("failed")],
        }
    return records, diag


def oracle_sentence_for_variant(variant: Mapping[str, Any],
                                gold_doc: Mapping[str, Any],
                                text_by_sample: Mapping[str, str],
                                ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Select the CONFIRMED rule item a synthetic variant targets.

    The variant is bound to ``rule_id`` + ``sentence_idx`` (+ the mutated
    field).  The confirmed Gold Rule Records carry one clause per rule item, so
    the item is selected deterministically: the clause whose confirmed values
    cover the mutated field.  When several items cover it, the clause whose
    confirmed value equals the panel's locked value wins (exact evidence);
    otherwise the first covering clause in document order is used and the
    ambiguity is recorded.  Nothing is inferred beyond that.
    """
    rule_id = variant["rule_id"]
    sentence_idx = variant["rule_element"]["sentence_idx"]
    field = variant["rule_element"].get("field")
    fields = FIELD_TO_CONFIRMED.get(field)
    diagnostics: dict[str, Any] = {
        "rule_id": rule_id,
        "sentence_idx": sentence_idx,
        "field": field,
        "selection": None,
        "candidate_item_ids": [],
        "ambiguous": False,
    }
    if fields is None:
        diagnostics["selection"] = "unsupported_field"
        return None, diagnostics
    record = next((r for r in gold_doc["records"]
                   if r["rule_id"] == rule_id and r["sentence_idx"] == sentence_idx),
                  None)
    if record is None:
        diagnostics["selection"] = "no_confirmed_sentence"
        return None, diagnostics
    text = text_by_sample.get(record["sample_id"])
    if text is None:
        diagnostics["selection"] = "no_sentence_text"
        return None, diagnostics

    def _covers(clause: Mapping[str, Any]) -> bool:
        for name in fields:
            if name == "modality":
                if not clause["modality"]["label"]:
                    return False
            else:
                if not clause.get(name + "s"):
                    return False
        return True

    candidates = [c for c in record["clauses"] if _covers(c)]
    diagnostics["candidate_item_ids"] = [c["item_id"] for c in candidates]
    if not candidates:
        diagnostics["selection"] = "no_covering_item"
        return None, diagnostics
    if len(candidates) > 1:
        diagnostics["ambiguous"] = True
        locked_value = (variant["rule_element"].get("action")
                        if "action" in fields else None)
        if locked_value:
            exact = [c for c in candidates
                     if any(text[s["start"]:s["end"]] == locked_value
                            for s in c["actions"])]
            if len(exact) == 1:
                candidates = exact
                diagnostics["selection"] = "exact_value_match"
        if diagnostics["selection"] is None:
            diagnostics["selection"] = "first_covering_item"
    else:
        diagnostics["selection"] = "unique_covering_item"

    clause = candidates[0]
    sentence = {
        "sentence_text": text,
        "sentence_idx": sentence_idx,
        "modality": clause["modality"]["label"],
        "actor": (text[clause["actors"][0]["start"]:clause["actors"][0]["end"]]
                  if clause["actors"] else None),
        "action": (text[clause["actions"][0]["start"]:clause["actions"][0]["end"]]
                   if clause["actions"] else None),
        "condition": (text[clause["conditions"][0]["start"]:clause["conditions"][0]["end"]]
                      if clause["conditions"] else None),
        "constraint": (text[clause["constraints"][0]["start"]:clause["constraints"][0]["end"]]
                       if clause["constraints"] else None),
        "exception": (text[clause["exceptions"][0]["start"]:clause["exceptions"][0]["end"]]
                      if clause["exceptions"] else None),
        "oracle_item_id": clause["item_id"],
        "oracle_source": _rel(GOLD_RULE_RECORDS),
    }
    diagnostics["selected_item_id"] = clause["item_id"]
    return sentence, diagnostics


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------
def run_three_types(frozen, oracle_records, reference_records,
                    oracle_obligation_records=None,
                    write: bool = True) -> dict[str, Any]:
    """Frozen Sun detector on the 33 human-adjudicated items, all rule sources."""
    arms = [("oracle", "human_rules", oracle_records),
            ("reference", "reference", reference_records)]
    if oracle_obligation_records is not None:
        arms.append(("oracle_obligation_only", "human_rules",
                     oracle_obligation_records))
    out: dict[str, Any] = {}
    for label, arm, records in arms:
        rows = linkage.build_violation_rows(arm, frozen, records)
        folder = OUT_ROOT / "original_three" / label
        if write:
            _write_rows(folder / "predictions.jsonl", rows)  # fixed before Gold
            _write_json(folder / "rule_records.json", records)
        evaluation = linkage.evaluate_rows(rows, linkage.GOLD_VIOLATION)
        if write:
            _write_json(folder / "evaluation.json", evaluation)
        out[label] = {
            "arm": arm,
            "arm_label": linkage.ARM_LABELS[arm],
            "evaluation": evaluation["violation"],
            "items": evaluation["items"],
            "failed_rules": sorted({r["rule_id"] for r in rows
                                    if r["rule_record_failed"]}),
        }
    out["delta_oracle_minus_reference"] = _delta(
        out["oracle"]["evaluation"], out["reference"]["evaluation"])
    if oracle_obligation_records is not None:
        out["delta_oracle_obligation_minus_reference"] = _delta(
            out["oracle_obligation_only"]["evaluation"],
            out["reference"]["evaluation"])
    return out


def mapping_diagnostics(frozen, rule_records_by_policy,
                        ) -> dict[str, Any]:
    """Why the Definition-6 check is observable (or not), per rule and policy.

    Records, per rule and per policy, how many rule actions map to a process
    action above gamma and how many actor-action pairs survive; this is the
    mechanical explanation of the ``incorrect_actor`` observability.
    """
    out: dict[str, Any] = {}
    models = frozen["models"]
    scorer = frozen["scorer"]
    gamma = frozen["gamma"]
    for policy, records in rule_records_by_policy.items():
        per_rule: dict[str, Any] = {}
        for rule_id, record in records.items():
            actions = record.get("actions") or []
            actors = record.get("actors") or []
            pairs = record.get("actor_action_pairs") or []
            best: list[dict[str, Any]] = []
            mapped_actions = 0
            for action in actions:
                score = None
                best_process_action = None
                for process_id, model in models.items():
                    _, value = scorer._best_action_match(action, model)
                    if value is not None and (score is None or value > score):
                        score = value
                        best_process_action = process_id
                above = bool(score is not None and score > gamma)
                mapped_actions += int(above)
                best.append({"rule_action": action,
                             "best_similarity": round(score, 4) if score is not None else None,
                             "best_process_id": best_process_action,
                             "above_gamma": above})
            pair_above = 0
            for pair in pairs:
                score = None
                for _process_id, model in models.items():
                    _, value = scorer._best_action_match(pair["action"], model)
                    if value is not None and (score is None or value > score):
                        score = value
                if score is not None and score > gamma:
                    pair_above += 1
            per_rule[rule_id] = {
                "policy": policy,
                "action_count": len(actions),
                "actor_count": len(actors),
                "actor_action_pair_count": len(pairs),
                "actions_mapped_above_gamma": mapped_actions,
                "pairs_mapped_above_gamma": pair_above,
                "def6_observable": bool(pair_above),
                "best_action_matches": best,
            }
        out[policy] = per_rule
    return out


METHODS = ("winter", "sun", "bm25", "tfidf_svd")


def run_four_types(frozen, text_by_sample, oracle_records,
                   write: bool = True) -> dict[str, Any]:
    """Four frozen backends on the 40-variant synthetic panel with Gold rules."""
    panel = _read(ext.PANEL)
    gamma_ext = float(panel["config"]["gamma_ext"])
    gold_doc = _read(GOLD_RULE_RECORDS)
    gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}
    out: dict[str, Any] = {"gamma_ext": gamma_ext, "methods": {},
                           "selection_diagnostics": {}}
    for method in METHODS:
        rows: list[dict[str, Any]] = []
        selections: dict[str, Any] = {}
        for variant in panel["variants"]:
            sentence, diag = oracle_sentence_for_variant(
                variant, gold_doc, text_by_sample)
            selections[variant["variant_id"]] = diag
            if sentence is None:
                rows.append(panel_runner._failed_row(
                    method, variant, "oracle", variant["variant_id"],
                    ext._gamma_for(method),
                    f"oracle_item_selection_failed:{diag['selection']}"))
                continue
            row = ext.run_method(method, variant, sentence,
                                 panel_runner._sims_factory_for(method, frozen["nlp"]),
                                 ext._gamma_for(method), gamma_ext,
                                 frozen["nlp"], panel)
            row["external_arm"] = "oracle"
            row["oracle_item_id"] = sentence["oracle_item_id"]
            row["oracle_source"] = sentence["oracle_source"]
            rows.append(row)
        folder = OUT_ROOT / "extended_four" / method
        if write:
            _write_rows(folder / "predictions.jsonl", rows)
        evaluation = evaluate_extended(rows, gold)
        paired = evaluate_paired(rows, panel, gamma_ext)
        if write:
            _write_json(folder / "evaluation.json",
                        {"evaluation": evaluation, "paired": paired})
        out["methods"][method] = {
            "evaluation": evaluation,
            "paired": paired,
            "method_display": ext.METHOD_DISPLAY[method],
            "gamma_action": ext._gamma_for(method),
        }
        out["selection_diagnostics"][method] = selections
    out["selection_summary"] = _selection_summary(out["selection_diagnostics"])
    return out


def _selection_summary(selection_diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    """Counts of how each variant was bound to a confirmed rule item."""
    out: dict[str, Any] = {}
    for method, per_variant in selection_diagnostics.items():
        counts: dict[str, int] = {}
        ambiguous: list[str] = []
        uncovered: list[str] = []
        for variant_id, block in per_variant.items():
            selection = block.get("selection")
            counts[selection] = counts.get(selection, 0) + 1
            if block.get("ambiguous"):
                ambiguous.append(variant_id)
            if selection in ("no_covering_item", "no_confirmed_sentence",
                             "unsupported_field", "no_sentence_text"):
                uncovered.append(variant_id)
        out[method] = {
            "selection_counts": counts,
            "ambiguous_variant_ids": sorted(ambiguous),
            "uncovered_variant_ids": sorted(uncovered),
            "uncovered_count": len(uncovered),
        }
    return out


def _delta(oracle: Mapping[str, Any], reference: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("macro_f1", "exact_type_accuracy", "detected", "missed",
            "wrong_type", "unobservable")
    delta = {k: _num(oracle.get(k)) - _num(reference.get(k)) for k in keys}
    delta["per_type_f1"] = {
        t: round(_num(oracle["per_type"][t]["f1"])
                 - _num(reference["per_type"][t]["f1"]), 6)
        for t in oracle.get("per_type", {})
        if t in reference.get("per_type", {})
    }
    return delta


def _num(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def render_markdown(report: Mapping[str, Any]) -> str:
    three = report["original_three_types"]
    four = report["extended_four_types"]
    lines = [
        "# Stage 3 Oracle：正确规则下检查器能力（零 API）",
        "",
        f"**run_id**：`{report['run_id']}`",
        f"**状态**：`{report['claim_status']}`",
        "",
        "## 问题",
        "",
        "给检查器**正确的规则**（用户人工确认的 74 句 / 92 条规范 → 正式 Gold Rule "
        "Records），它能找出多少流程错误？本报告把 Stage 2 误差从链路中移除，只测 "
        "Stage 3 本身。",
        "",
        "## 规则来源",
        "",
        f"- Gold Rule Records：`{_rel(GOLD_RULE_RECORDS)}` "
        f"sha256 `{report['bindings']['gold_rule_records']['sha256']}`",
        f"- Oracle 胶囊：`{_rel(ORACLE_CAPSULE)}` "
        f"sha256 `{report['bindings']['oracle_capsule']['sha256']}`",
        "- 92 条规范全部进入检查器；每条规范保留自己的情态标签（不是 obligation-only 投影）。",
        "",
        "## 1. 原三类（33 条人工 violation Gold，7 个冻结流程）",
        "",
        "| 规则来源 | macro-F1 | exact | detected | missed | wrong-type | unobservable |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ("oracle", "oracle_obligation_only", "reference"):
        if arm not in three:
            continue
        ev = three[arm]["evaluation"]
        lines.append(
            f"| {arm} | {ev['macro_f1']:.4f} | {ev['exact_type_accuracy']:.4f} | "
            f"{ev['detected']} | {ev['missed']} | {ev['wrong_type']} | "
            f"{ev['unobservable']} |")
    lines += [
        "",
        "### 逐类型（oracle，全部情态）",
        "",
        "| 类型 | support | P | R | F1 |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, per in three["oracle"]["evaluation"]["per_type"].items():
        lines.append(f"| {name} | {per['support']} | {per['precision']:.3f} | "
                     f"{per['recall']:.3f} | {per['f1']:.3f} |")
    lines += [
        "",
        "### oracle − reference",
        "",
        "| 指标 | Δ |",
        "|---|---:|",
    ]
    for key, value in three["delta_oracle_minus_reference"].items():
        if key == "per_type_f1":
            for t, v in value.items():
                lines.append(f"| per_type_f1.{t} | {v:+.4f} |")
        else:
            lines.append(f"| {key} | {value:+.4f} |")
    lines += [
        "",
        "## 1b. 为什么 incorrect_actor 不可观察（Definition 6 动作映射诊断）",
        "",
        "| 规则 | 策略 | rule actions | 映射>gamma | actor-action 对 | 对映射>gamma | Def6 可观察 |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for policy, per_rule in report["mapping_diagnostics"].items():
        for rule_id, block in sorted(per_rule.items()):
            lines.append(
                f"| {rule_id} | {policy} | {block['action_count']} | "
                f"{block['actions_mapped_above_gamma']} | "
                f"{block['actor_action_pair_count']} | "
                f"{block['pairs_mapped_above_gamma']} | "
                f"{'yes' if block['def6_observable'] else 'no'} |")
    lines += [
        "",
        "> Definition 6（incorrect_actor）只有在“规则动作映射到流程动作且相似度 > gamma(0.8)”时"
        "才可观察。人工确认规则使用完整法律短语（例：`implement suitable measures to safeguard "
        "the data subject's rights and freedoms and legitimate interests`），其与流程活动标签的"
        "相似度低于阈值，因此该检查项在本数据上大多不可观察。这是**检查器输入口径**的局限"
        "（规则记录的动作粒度 vs 流程标签粒度），不是人工规则错误。",
        "",
        "## 2. 四类扩展（40 个受控合成变体 + 40 个合规对照）",
        "",
        "| 后端 | variant exact | macro | control FP rate | paired acc |",
        "|---|---:|---:|---:|---:|",
    ]
    for method, block in four["methods"].items():
        ev = block["evaluation"]
        paired = block["paired"]
        lines.append(
            f"| {block['method_display']} | "
            f"{_fmt(paired.get('variant_exact_type_accuracy'))} | "
            f"{_fmt(ev.get('macro_f1'))} | "
            f"{_fmt(paired.get('control_false_positive_rate'))} | "
            f"{_fmt(paired.get('paired_accuracy'))} |")
    lines += [
        "",
        "> 四类扩展是**合成受控面板**（development-only）；Winter/Sun 原论文未定义这四类，"
        "一律写 `Winter-style extension` / `Sun-style extension`。它提供合规对照，是唯一"
        "能测误报（FP）的面板。",
        "",
        "### 2b. 面板变体与人工规则的绑定覆盖",
        "",
        "| 后端 | 唯一命中 | 多义取首 | 人工规则未覆盖 | 未覆盖变体 |",
        "|---|---:|---:|---:|---|",
    ]
    for method, block in four.get("selection_summary", {}).items():
        counts = block["selection_counts"]
        lines.append(
            f"| {method} | {counts.get('unique_covering_item', 0)} | "
            f"{counts.get('first_covering_item', 0)} | "
            f"{block['uncovered_count']} | "
            f"{', '.join(block['uncovered_variant_ids'][:4])}"
            f"{' …' if block['uncovered_count'] > 4 else ''} |")
    lines += [
        "",
        "> 该面板按 **dev 抽取的六要素读法**构造变体，因此有变体作用于人工确认规则"
        "**并未标注**的字段（如某些句子的 constraint/exception 为空），此时 Oracle 臂"
        "不猜、不补，直接记为未覆盖并计入分母。这进一步说明：四类面板数字对人工规则臂"
        "是**偏差比较面**，不能用来判断人工规则的质量。",
        "",
        "## 3. 依赖与边界",
        "",
    ]
    for key, value in report["dependencies"].items():
        lines.append(f"- `{key}` = `{value}`")
    lines += [
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


def _fmt(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.4f}"
    return "-"


def build_manifest(report: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = {}
    for path in sorted(OUT_ROOT.rglob("*")):
        if path.is_file():
            artifacts[_rel(path)] = {"path": _rel(path), "sha256": _sha(path),
                                     "byte_size": path.stat().st_size}
    return {
        "schema_version": "s3_oracle_gold_rules_manifest@1.0.0",
        "run_id": RUN_ID,
        "claim_status": report["claim_status"],
        "task": "S3.7 (Oracle isolation) on the frozen development evaluation surface",
        "bindings": report["bindings"],
        "dependencies": report["dependencies"],
        "implementation": {
            _rel(Path(__file__)): {"path": _rel(Path(__file__)),
                                   "sha256": _sha(Path(__file__))},
            "src/bpc_hybrid/sun_stage3/gdpr_capsule_converter.py": {
                "path": "src/bpc_hybrid/sun_stage3/gdpr_capsule_converter.py",
                "sha256": _sha(ROOT / "src/bpc_hybrid/sun_stage3/gdpr_capsule_converter.py")},
            "src/bpc_hybrid/gdpr7_gold_rule_records.py": {
                "path": "src/bpc_hybrid/gdpr7_gold_rule_records.py",
                "sha256": _sha(ROOT / "src/bpc_hybrid/gdpr7_gold_rule_records.py")},
        },
        "artifacts": artifacts,
        "replay_command": report["run_command"] + " --check",
        "boundaries": report["boundaries"],
        "zero_api": {"new_llm_api_calls": 0},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="recompute in memory and compare with the published report")
    args = parser.parse_args(argv)

    for path in (GOLD_RULE_RECORDS, ORACLE_CAPSULE, ORACLE_CAPSULE_MANIFEST):
        if not path.is_file():
            raise FileNotFoundError(f"Oracle input missing: {path}")

    config = _read(linkage.CONFIG)
    frozen = linkage.load_frozen(config)
    text_by_sample = panel_runner._sentence_text_by_sample(_read(linkage.INPUT_PACK))
    oracle_records, oracle_diag = build_oracle_rule_records(frozen)
    oracle_obligation_records, oracle_obligation_diag = build_oracle_rule_records(
        frozen, include_modalities=("obligation",))
    reference_records, reference_diag = linkage.build_rule_records_for_arm(
        "reference", frozen, sorted(linkage.rule_texts_of(frozen["inference"])), None)

    three = run_three_types(frozen, oracle_records, reference_records,
                            oracle_obligation_records, write=not args.check)
    four = run_four_types(frozen, text_by_sample, oracle_records,
                          write=not args.check)
    diagnostics = mapping_diagnostics(frozen, {
        "oracle_all_modalities": oracle_records,
        "oracle_obligation_only": oracle_obligation_records,
        "reference": reference_records,
    })

    report = {
        "schema_version": "s3_oracle_gold_rules@1.0.0",
        "run_id": RUN_ID,
        "scope": "development_only_frozen_evaluation_surface",
        "claim_status": (
            "Oracle isolation run on the frozen development evaluation surface; "
            "NOT the formal S3.7 main table (S2.13 and S3.4-S3.6 formal promotion "
            "still pending)"),
        "question": ("With Gold Rule Records as input, how reliable are the frozen "
                     "Stage 3 backends? Stage 2 error is removed by construction."),
        "rule_source": {
            "arm": "oracle",
            "gold_rule_records": _rel(GOLD_RULE_RECORDS),
            "capsule": _rel(ORACLE_CAPSULE),
            "converter": oracle_diag["rule_record_source"],
            "include_modalities": oracle_diag["conversion_summary"]["include_modalities"],
            "failed_rules": oracle_diag["failed_rules"],
            "reference_adapter": reference_diag["rule_record_source"],
        },
        "bindings": {
            "gold_rule_records": {"path": _rel(GOLD_RULE_RECORDS),
                                  "sha256": _sha(GOLD_RULE_RECORDS)},
            "oracle_capsule": {"path": _rel(ORACLE_CAPSULE),
                               "sha256": _sha(ORACLE_CAPSULE)},
            "oracle_capsule_manifest": {"path": _rel(ORACLE_CAPSULE_MANIFEST),
                                        "sha256": _sha(ORACLE_CAPSULE_MANIFEST)},
            "confirmed_human_bundle": {"path": _rel(CONFIRMED),
                                       "sha256": _sha(CONFIRMED)},
            "violation_gold": {"path": _rel(linkage.GOLD_VIOLATION),
                               "sha256": _sha(linkage.GOLD_VIOLATION)},
            "inference_pack": {"path": _rel(linkage.INFERENCE_PACK),
                               "sha256": _sha(linkage.INFERENCE_PACK)},
            "stage3_config": {"path": _rel(linkage.CONFIG), "sha256": _sha(linkage.CONFIG)},
            "thresholds": {"tau": frozen["tau"], "gamma": frozen["gamma"],
                           "theta": frozen["theta"]},
        },
        "dependencies": {
            "s2_13_stage2_freeze": "blocked on S2.12 API arms (not required for this isolation run)",
            "s3_4_s3_6_formal_promotion": "pending",
            "gold_rule_records_published": True,
            "formal_s3_7_authorization": "not granted; this run is an isolation evaluation",
        },
        "original_three_types": three,
        "extended_four_types": four,
        "mapping_diagnostics": diagnostics,
        "oracle_modality_policies": {
            "all_modalities": {
                "include_modalities":
                    oracle_diag["conversion_summary"]["include_modalities"],
                "rule_record_source": oracle_diag["rule_record_source"],
            },
            "obligation_only": {
                "include_modalities":
                    oracle_obligation_diag["conversion_summary"]["include_modalities"],
                "rule_record_source": oracle_obligation_diag["rule_record_source"],
            },
        },
        "boundaries": {
            "gold_modified": False,
            "thresholds_changed": False,
            "processes_changed": False,
            "existing_predictions_overwritten": False,
            "llm_or_api_called": False,
            "synthetic_panel_merged_into_human_gold": False,
        },
        "run_command": "python formal_experiment/scripts/run_s3_oracle_gold_rules_v1.py",
        "zero_api": {"new_llm_api_calls": 0},
    }

    if args.check:
        existing = _read(REPORT_JSON)
        same = json.dumps(existing, ensure_ascii=False, sort_keys=True) == \
            json.dumps(report, ensure_ascii=False, sort_keys=True)
        print(json.dumps({"mode": "check", "valid": same}, ensure_ascii=False))
        return 0 if same else 2

    if REPORT_JSON.exists():
        raise FileExistsError(
            f"refusing to overwrite existing Oracle report: {REPORT_JSON}")
    _write_json(REPORT_JSON, report)
    REPORT_MD.write_text(render_markdown(report), encoding="utf-8")
    manifest = build_manifest(report)
    _write_json(MANIFEST, manifest)
    print(json.dumps({
        "run_id": RUN_ID,
        "three_type_oracle": three["oracle"]["evaluation"]["macro_f1"],
        "three_type_reference": three["reference"]["evaluation"]["macro_f1"],
        "report": _rel(REPORT_JSON),
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
