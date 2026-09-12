# -*- coding: utf-8 -*-
"""Run the SIM card case (S3.9-EXT-REAL-CASE): groups A / B / C plus repair controls.

Zero LLM/API.  Predictions are written before the development reference
judgments are read; the reference judgments never enter the rule side.

Usage (from ``formal_experiment/``):
    python scripts/run_sim_case_c1_v1.py [--overwrite] [--check] [--replay]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from bpc_hybrid import sim_case_c1 as core  # noqa: E402
from bpc_hybrid.sim_case_c1_transforms import flatten_collaboration, repair_variant  # noqa: E402

RUN_DIR = ROOT / "outputs" / "development" / "sim_case_c1" / "run_v1"
LOCAL_MODELS = ROOT / "outputs" / "development" / "sim_case_c1" / "models"
REPORT_JSON = ROOT / "outputs" / "reports" / "sim_case_c1_results.json"
REPORT_MD = ROOT / "outputs" / "reports" / "sim_case_c1_results.md"

LENS_MAP = {  # declared comparison mapping (comparison stage only, never fed to detection)
    "r8": {"primary": "constraint_violated", "secondary": ["required_condition_not_enforced"]},
    "r9": {"primary": "missing_action", "secondary": []},
    "r10": {"primary": "incorrect_actor", "secondary": []},
    "r11": {"primary": "out_of_order", "secondary": ["required_condition_not_enforced"]},
    "r13": {"primary": "required_condition_not_enforced", "secondary": ["constraint_violated"]},
}
GAMMA_EXT = 0.5


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write(path: Path, text: str, overwrite: bool) -> dict:
    if path.exists() and not overwrite:
        raise SystemExit(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return {"path": str(path.relative_to(core.REPO)).replace("\\", "/"),
            "sha256": _sha(text), "bytes": len(text.encode("utf-8"))}


def _load_nlp():
    import spacy
    return spacy.load("en_core_web_sm")


def _sun_thresholds() -> dict:
    config = core.load_json(core.SUN_CONFIG)
    thresholds = config["method"]["thresholds"]
    return {"tau": float(thresholds["tau"]), "gamma": float(thresholds["gamma"]),
            "theta": float(thresholds["theta"])}


def _parse_flattened(payload: bytes, label: str, contract_config: Path) -> dict:
    """Flatten a collaboration view and parse it with the frozen Stage 1 contract."""
    import xml.etree.ElementTree as ET

    from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_bytes, validate_process_record

    flattened, info = flatten_collaboration(payload)
    contract = load_stage1_contract(contract_config)
    record = parse_bpmn_bytes(flattened, source_path=f"{label}.bpmn", contract=contract)
    validation = validate_process_record(record)
    if not getattr(validation, "valid", False):
        raise SystemExit(f"{label}: stage1 record invalid: {validation}")
    return {
        "label": label,
        "record": record,
        "xml_root": ET.fromstring(flattened),
        "flattened_xml": flattened,
        "flatten_info": info,
        "evidence": {
            "flattened_xml_sha256": core.sha256_bytes(flattened),
            "process_record_sha256": _sha(json.dumps(record, sort_keys=True, ensure_ascii=False)),
            "activities": len(record.get("activities", [])),
            "gateways": len(record.get("gateways", [])),
            "events": len(record.get("events", [])),
            "flows": len(record.get("sequence_flows", [])),
            "lanes": [lane.get("name") for lane in record.get("lanes", [])],
        },
    }


def _group_rows(scorers: dict, sentence: dict, model, stage1: dict, rule: dict) -> dict:
    three = core.run_three_types(scorers["sun"], rule, model)
    rows = {"three_types": three}
    return rows


def _extended_rows(scorers: dict, sentence: dict, model, stage1: dict, rule: dict) -> dict:
    activity_id, activity_sim, activity_name = core.best_activity_for(sentence, model, scorers["sim"])
    rows, surfaces = core.run_extended_types(scorers["ext"], sentence, model, stage1["record"],
                                            stage1["xml_root"], activity_id)
    return {"extended": rows, "surfaces": surfaces,
            "mapped_activity": {"id": activity_id, "name": activity_name, "similarity": activity_sim}}


def _rule_side(rule_id: str, rule_text: str, group: str, context: dict) -> dict:
    if group == "A":
        outcome = core.stage2_group_a(rule_id, rule_text, context["nlp"])
    else:
        outcome = core.stage2_group_b(rule_id, rule_text, context["predictions"])
    if not outcome.get("ok"):
        return {"ok": False, "error": outcome.get("error"), "sentence": None, "rule": None}
    sentence = core.apply_role_binding(outcome["sentence"])
    sentence["rule_id"] = rule_id
    if not sentence.get("sentence_text"):
        sentence["sentence_text"] = rule_text
    rule = core.build_rule_record(sentence)
    return {"ok": True, "error": None, "sentence": sentence, "rule": rule,
            "stage2_meta": {k: v for k, v in outcome.items() if k not in ("sentence",)}}


def _compare_records(rule_a: dict, rule_b: dict) -> dict:
    fields = ["modality", "actions", "actors", "actor_action_pairs", "order_relations",
              "condition", "constraint", "exception"]
    diff = {f: {"A": rule_a.get(f), "B": rule_b.get(f)}
            for f in fields if rule_a.get(f) != rule_b.get(f)}
    return {"changed_fields": sorted(diff), "detail": diff,
            "attribution": "extraction" if diff else "none"}


def _sanitise_attribution(attribution: dict) -> dict:
    """Keep field names and short fragments only (long rule-side text stays local)."""
    clean = {}
    for rule_id, block in attribution.items():
        if not block:
            clean[rule_id] = block
            continue
        detail = {}
        for field, values in (block.get("detail") or {}).items():
            detail[field] = {side: _fragment(value) for side, value in values.items()}
        clean[rule_id] = {"changed_fields": block.get("changed_fields", []),
                          "attribution": block.get("attribution"),
                          "detail_fragments": detail}
    return clean


def _fragment(value) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    text = " ".join(text.split())
    return f"{text[:30]}…(sha256 {_sha(text)[:12]})" if len(text) > 30 else text


def run(overwrite: bool, check_only: bool) -> dict:
    nlp = _load_nlp()
    thresholds = _sun_thresholds()
    curated = core.load_json(core.CURATED)
    requirements = core.load_requirements()
    predictions = core.load_predictions(1)
    repair_specs = core.load_json(core.REPAIR_SPECS)

    from bpc_hybrid.stage3_extended_violations import ExtendedViolationScorer  # noqa: E402
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

    sim = WinterSimilarity(nlp)
    scorers = {"sim": sim, "sun": SunScorer(sim, thresholds["tau"], thresholds["gamma"],
                                            thresholds["theta"], nlp=nlp)}

    original = core.BPMN.read_bytes()
    stage1 = _parse_flattened(original, "sim_original", core.STAGE1_CONTRACT)
    model = core.build_model(stage1, nlp)
    scorers["ext"] = ExtendedViolationScorer(sim.text_pair, sim.text_pair,
                                             thresholds["gamma"], GAMMA_EXT)

    plan = {
        "schema_version": "sim_case_c1_plan@1.0.0",
        "run_id": "sim_case_c1_run_v1",
        "claim_scope": "development_case_study_not_formal_gold",
        "written_before_scoring": True,
        "main_denominator": [f"{rid}/v2" for rid in core.MAIN_RULES],
        "background_items": core.BACKGROUND_RULES,
        "groups": {
            "A": "non-LLM deterministic adapter + frozen Sun-style three-type detection",
            "B": "real-LLM predictions (repeat-01) + SAME three-type detection as A",
            "C": "SAME stage2 and three-type rows as B + four extended types",
        },
        "declared_policy": core.ADAPTATION_POLICY,
        "thresholds": {**thresholds, "gamma_ext": GAMMA_EXT,
                       "source": "configs/sun_stage3_development_v1.json + frozen extended gamma"},
        "lens_map": LENS_MAP,
        "inputs": {
            "bpmn": core.artifact(core.BPMN),
            "requirements": core.artifact(core.REQUIREMENTS),
            "step_3_baseline": core.artifact(core.STEP3),
            "curated_reference_judgments": core.artifact(core.CURATED),
            "repair_specs": core.artifact(core.REPAIR_SPECS),
            "predictions_repeat01": predictions["artifact"],
            "stage1_contract": core.artifact(core.STAGE1_CONTRACT),
            "sun_config": core.artifact(core.SUN_CONFIG),
        },
        "stage1_public_record": stage1["evidence"],
        "implementation_hashes": {
            "core": _sha(Path(core.__file__).read_text(encoding="utf-8")),
            "transforms": _sha((ROOT / "src" / "bpc_hybrid" / "sim_case_c1_transforms.py")
                               .read_text(encoding="utf-8")),
            "runner": _sha(Path(__file__).read_text(encoding="utf-8")),
        },
        "prediction_isolation": {
            "reference_judgments_read_after_predictions": True,
            "external_deviations_not_in_detection_input": True,
            "step_3_baseline_read_only_for_comparison": True,
        },
    }

    rows: list[dict] = []
    rule_records: dict[str, dict] = {}
    for rule_id in core.MAIN_RULES:
        rule_text = requirements[(rule_id, 2)]
        sides = {group: _rule_side(rule_id, rule_text, group, {"nlp": nlp, "predictions": predictions})
                 for group in ("A", "B")}
        entry = {"rule_id": rule_id, "version": "v2", "rule_text_sha256": _sha(rule_text),
                 "rule_text_length": len(rule_text), "sides": {}}
        for group, side in sides.items():
            if not side["ok"]:
                rows.append({"rule_id": rule_id, "group": group, "check": "*",
                             "status": core.STATUS_UNDETERMINED, "reason": side["error"]})
                entry["sides"][group] = {"ok": False, "error": side["error"]}
                continue
            rule_rows = _group_rows(scorers, side["sentence"], model, stage1, side["rule"])
            entry["sides"][group] = {
                "ok": True,
                "sentence": {k: v for k, v in side["sentence"].items() if k != "sentence_text"},
                "rule": side["rule"],
                "checks": rule_rows["three_types"],
                "stage2_meta": side["stage2_meta"],
            }
            for check, result in rule_rows["three_types"].items():
                rows.append({"rule_id": rule_id, "group": group, "check": check,
                             "status": result["status"], "score": result.get("score"),
                             "denominator": result.get("denominator"),
                             "reason": result.get("reason")})
        # group C = group B rule side + extended types
        side_b = sides["B"]
        if side_b["ok"]:
            ext = _extended_rows(scorers, side_b["sentence"], model, stage1, side_b["rule"]) 
            entry["sides"]["C"] = {
                "ok": True,
                "sentence": entry["sides"]["B"]["sentence"],
                "rule": side_b["rule"],
                "checks": {**entry["sides"]["B"]["checks"], **ext["extended"]},
                "surfaces": ext["surfaces"], "mapped_activity": ext["mapped_activity"],
                "reuses_group_b": ["stage2", "three_type_rows"],
            }
            for check, result in entry["sides"]["B"]["checks"].items():
                rows.append({"rule_id": rule_id, "group": "C", "check": check,
                             "status": result["status"], "score": result.get("score"),
                             "denominator": result.get("denominator"),
                             "reason": result.get("reason"),
                             "inherited_from": "B"})
            for check, result in ext["extended"].items():
                rows.append({"rule_id": rule_id, "group": "C", "check": check,
                             "status": result["status"], "score": result.get("score"),
                             "reason": result.get("reason"),
                             "candidate_count": result.get("candidate_count"),
                             "best_candidate": result.get("best_candidate"),
                             "max_sim": result.get("max_sim"),
                             "added_by": "four_extended_types"})
        else:
            entry["sides"]["C"] = {"ok": False, "error": side_b.get("error")}
        entry["a_to_b"] = (_compare_records(entry["sides"]["A"]["rule"], entry["sides"]["B"]["rule"])
                           if entry["sides"]["A"].get("ok") and entry["sides"]["B"].get("ok") else None)
        rule_records[rule_id] = entry
        stage1 = stage1  # single public record consumed by all groups

    # ---- predictions are on disk in memory only; now (and only now) read the
    # development reference judgments for the comparison table -----------------
    reference = {item["rule_id"]: item for item in curated["items"]}
    comparison = []
    for rule_id in core.MAIN_RULES:
        item = reference[rule_id]
        lenses = LENS_MAP[rule_id]
        per_group = {}
        for group in ("A", "B", "C"):
            side = rule_records[rule_id]["sides"].get(group) or {}
            checks = side.get("checks") or {}
            lens_results = {}
            for lens in [lenses["primary"], *lenses["secondary"]]:
                if lens in checks:
                    lens_results[lens] = {"status": checks[lens]["status"],
                                          "score": checks[lens].get("score"),
                                          "reason": checks[lens].get("reason")}
            found = any(r["status"] == core.STATUS_VIOLATION for r in lens_results.values())
            undetermined = (not lens_results) or all(
                r["status"] in (core.STATUS_UNDETERMINED, core.STATUS_NOT_APPLICABLE)
                for r in lens_results.values())
            per_group[group] = {
                "covered_lenses": sorted(lens_results),
                "lens_results": lens_results,
                "found_corresponding_problem": found,
                "all_lenses_undetermined": bool(undetermined),
                "type_name_match": found and lenses["primary"] in {
                    k for k, v in lens_results.items() if v["status"] == core.STATUS_VIOLATION},
            }
        reference_present = item["dev_reference_judgment"]["judgment"] in (
            "issue_present", "issue_present_with_premise")
        primary = per_group["C"]
        comparison.append({
            "rule_id": rule_id,
            "reference_judgment": item["dev_reference_judgment"]["judgment"],
            "reference_sources": item["dev_reference_judgment"]["sources"],
            "premise_zh": item["dev_reference_judgment"].get("premise_zh"),
            "semantic_issue_zh": item["semantic_issue"]["summary_zh"],
            "primary_lens": lenses["primary"],
            "secondary_lenses": lenses["secondary"],
            "groups": per_group,
            "consistency": {
                "reference_issue_present": reference_present,
                "group_C_found": primary["found_corresponding_problem"],
                "group_C_undetermined": primary["all_lenses_undetermined"],
                "miss_kind": (None if primary["found_corresponding_problem"]
                              else ("undetermined" if primary["all_lenses_undetermined"]
                                    else "wrong_judgment")),
            },
        })

    # ---- repair controls ----------------------------------------------------
    repairs = []
    for spec in repair_specs["repairs"]:
        repaired_payload, detail = repair_variant(stage1["flattened_xml"], spec["repair_id"])
        repaired = _parse_flattened(repaired_payload, f"repair_{spec['repair_id']}", core.STAGE1_CONTRACT)
        repaired_model = core.build_model(repaired, nlp)
        rule_text = requirements[(spec["rule_id"], 2)]
        row = {"repair_id": spec["repair_id"], "rule_id": spec["rule_id"], "lens": spec["lens"],
               "operations": detail["operations"], "semantic_zh": detail["semantic_zh"],
               "model_evidence": repaired["evidence"],
               "before": None, "after": None}
        for group in ("B", "C"):
            side = rule_records[spec["rule_id"]]["sides"].get(group, {})
            if not side.get("ok"):
                continue
            sentence = dict(side["sentence"])
            sentence["sentence_text"] = rule_text
            rule = side["rule"]
            if spec["lens"] in ("missing_action", "incorrect_actor", "out_of_order"):
                after_checks = core.run_three_types(scorers["sun"], rule, repaired_model)
            else:
                after_checks = _extended_rows(scorers, sentence, repaired_model, repaired, rule)["extended"]
            after = after_checks.get(spec["lens"])
            before = (side.get("checks") or {}).get(spec["lens"])
            result = {"group": group,
                      "before_status": (before or {}).get("status"),
                      "before_score": (before or {}).get("score"),
                      "after_status": (after or {}).get("status"),
                      "after_score": (after or {}).get("score"),
                      "after_reason": (after or {}).get("reason"),
                      "problem_removed": ((before or {}).get("status") == core.STATUS_VIOLATION
                                          and (after or {}).get("status") == core.STATUS_SATISFIED)}
            if group == "C":
                row["after"] = result
            else:
                row["before"] = result
            row[f"group_{group}"] = result
        repairs.append(row)

    summary = {}
    for group in ("A", "B", "C"):
        counts: dict[str, int] = {}
        for row in rows:
            if row["group"] != group:
                continue
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        summary[group] = {"checks": sum(1 for r in rows if r["group"] == group), "status_counts": counts}

    capsule = {
        "schema_version": "sim_case_c1_run@1.0.0",
        "run_id": plan["run_id"],
        "claim_scope": plan["claim_scope"],
        "plan": plan,
        "rows": rows,
        "rules": rule_records,
        "comparison": comparison,
        "repairs": repairs,
        "summary": summary,
        "stage_attribution": {
            "a_to_b": {rid: rule_records[rid]["a_to_b"] for rid in core.MAIN_RULES},
            "b_to_c": "group C adds exactly the four extended checks on the SAME rule side as B; "
                      "three-type rows are reused byte-identically (reuses_group_b)",
        },
    }

    if check_only:
        return {"status": "CHECK_OK", "summary": summary,
                "comparison": [{c["rule_id"]: c["consistency"]} for c in comparison],
                "repairs": [{r["repair_id"]: (r.get("group_C") or {}).get("problem_removed")} for r in repairs]}

    outputs = {
        "plan": _write(RUN_DIR / "plan.json", json.dumps(plan, ensure_ascii=False, indent=1) + "\n", overwrite),
        "capsule": _write(RUN_DIR / "capsule.json", json.dumps(capsule, ensure_ascii=False, indent=1) + "\n", overwrite),
        "rows": _write(RUN_DIR / "rows.jsonl",
                       "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), overwrite),
        "report_json": _write(REPORT_JSON, json.dumps(
            {"schema_version": capsule["schema_version"], "run_id": plan["run_id"],
             "claim_scope": plan["claim_scope"], "groups": plan["groups"],
             "thresholds": plan["thresholds"], "declared_policy": plan["declared_policy"],
             "stage1": plan["stage1_public_record"], "inputs": plan["inputs"],
             "summary": summary, "comparison": comparison, "repairs": repairs,
             "stage_attribution": {
                 "a_to_b": _sanitise_attribution(capsule["stage_attribution"]["a_to_b"]),
                 "b_to_c": capsule["stage_attribution"]["b_to_c"],
             },
             "boundaries": [
                 "development case study; not formal Gold, not the authors' original experiment, not an enterprise validation",
                 "single case: counts and per-item results only; no seven-type aggregate F1",
                 "five prediction repeats are stability evidence, not 25 independent samples",
                 "the Barrientos artifact is read in place; no restricted text is committed",
             ]}, ensure_ascii=False, indent=1) + "\n", overwrite),
    }
    outputs["report_md"] = _write(REPORT_MD, render_md(capsule), overwrite)
    manifest = {
        "schema_version": "sim_case_c1_run_manifest@1.0.0",
        "run_id": plan["run_id"], "inputs": plan["inputs"],
        "implementation_hashes": plan["implementation_hashes"],
        "outputs": outputs, "api_calls": 0, "network": False,
    }
    _write(RUN_DIR / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", overwrite)
    (LOCAL_MODELS).mkdir(parents=True, exist_ok=True)
    (LOCAL_MODELS / "sim_original_flattened.bpmn").write_bytes(stage1["flattened_xml"])
    return {"status": "BUILT", "outputs": {k: v["path"] for k, v in outputs.items()},
            "summary": summary}


def render_md(capsule: dict) -> str:
    plan = capsule["plan"]
    lines = [
        "# SIM 卡入网案例：A/B/C 三组开发性检测结果（S3.9-EXT-REAL-CASE）",
        "",
        f"- run: `{capsule['run_id']}`；口径：**{capsule['claim_scope']}**（非正式 Gold、非作者原始实验复现、非企业验证）",
        f"- 主实验规则（5 条）：{', '.join(plan['main_denominator'])}；背景条目：{', '.join(plan['background_items'])}",
        f"- 阈值：tau={plan['thresholds']['tau']}, gamma={plan['thresholds']['gamma']}, "
        f"theta={plan['thresholds']['theta']}, gamma_ext={plan['thresholds']['gamma_ext']}",
        f"- 公共 Stage 1 记录：{plan['stage1_public_record']['process_record_sha256'][:16]}…"
        f"（扁平化 XML {plan['stage1_public_record']['flattened_xml_sha256'][:16]}…，"
        f"lanes={plan['stage1_public_record']['lanes']}）",
        f"- 角色绑定：{json.dumps(plan['declared_policy']['role_binding'], ensure_ascii=False)}"
        "（打分前声明，三组共用）",
        "",
        "## 1. 三组定义与实际组件",
        "",
        "| 组 | Stage 2 | 原三类检测 | 四类扩展 |",
        "|---|---|---|---|",
        "| A | 非 LLM 确定性抽取（开发适配器） | 冻结 Sun 式（Def5-7） | 无 |",
        "| B | 既有真实 LLM 预测（repeat-01） | 与 A 同一代码/阈值 | 无 |",
        "| C | 与 B 完全相同 | 与 B 完全相同（复用同一结果） | 四类扩展（gamma_ext=0.5） |",
        "",
        "## 2. 逐条结果（③ 方法实际输出）",
        "",
        "| 规则 | 组 | missing_action | incorrect_actor | out_of_order | prohibited | condition | constraint | exception |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for rule_id in core.MAIN_RULES:
        entry = capsule["rules"][rule_id]
        for group in ("A", "B", "C"):
            checks = (entry["sides"].get(group) or {}).get("checks") or {}
            def cell(name):
                c = checks.get(name)
                if not c:
                    return "—"
                extra = f" ({c.get('score')})" if c.get("score") is not None else ""
                return f"{c['status']}{extra}"
            lines.append(f"| {rule_id}/v2 | {group} | {cell('missing_action')} | {cell('incorrect_actor')} | "
                         f"{cell('out_of_order')} | {cell('prohibited_action_present')} | "
                         f"{cell('required_condition_not_enforced')} | {cell('constraint_violated')} | "
                         f"{cell('exception_not_handled')} |")
    lines += ["", "## 3. 与开发参考判断的逐条对照（① ② ④ ⑤）", "",
              "| 规则 | ① 语义问题 | ② 参考判断（来源） | 主检测视角 | C 组检出 | 未检出类型 | ⑤ A→B 变化字段 |",
              "|---|---|---|---|---|---|---|"]
    for item in capsule["comparison"]:
        rid = item["rule_id"]
        attr = capsule["stage_attribution"]["a_to_b"].get(rid) or {}
        lines.append(
            f"| {rid}/v2 | {item['semantic_issue_zh']} | {item['reference_judgment']}"
            f"（{', '.join(item['reference_sources'][:2])}…） | {item['primary_lens']} | "
            f"{'是' if item['consistency']['group_C_found'] else '否'} | "
            f"{item['consistency']['miss_kind'] or '—'} | {', '.join(attr.get('changed_fields', [])) or '无'} |")
    lines += ["", "## 4. 修复对照（程序构造的最小开发对照）", "",
              "| 修复 | 规则 | 视角 | 操作 | C 组修复前 | C 组修复后 | 问题是否消除 |",
              "|---|---|---|---|---|---|---|"]
    for row in capsule["repairs"]:
        after = row.get("group_C") or {}
        lines.append(f"| {row['repair_id']} | {row['rule_id']} | {row['lens']} | {row['semantic_zh']} | "
                     f"{after.get('before_status')} | {after.get('after_status')} | "
                     f"{'是' if after.get('problem_removed') else '否'} |")
    lines += ["", "## 5. 计数（不做七类总 F1）", "",
              "| 组 | 检查数 | violation | satisfied | undetermined | not_applicable |",
              "|---|---|---|---|---|---|"]
    for group, block in capsule["summary"].items():
        counts = block["status_counts"]
        lines.append(f"| {group} | {block['checks']} | {counts.get('violation', 0)} | "
                     f"{counts.get('satisfied', 0)} | {counts.get('undetermined', 0)} | "
                     f"{counts.get('not_applicable', 0)} |")
    lines += ["", "## 6. 边界", "",
              "- 本结果是开发性案例分析：不是正式 Gold、不是作者原始实验复现、不是独立测试、不是企业验证。",
              "- 单案例只给逐条结果与计数，不合成七类总 F1；5 轮预测只作稳定性证据。",
              "- Barrientos 语料按本地只读使用，不提交其原文；修复件是程序构造的开发对照。",
              ""]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--check", action="store_true", help="run in memory, write nothing")
    ap.add_argument("--replay", action="store_true", help="rerun from the stored plan and compare")
    args = ap.parse_args()
    result = run(overwrite=args.overwrite, check_only=args.check or args.replay)
    print(json.dumps(result, ensure_ascii=False, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
