# -*- coding: utf-8 -*-
"""Sun Figure 10 reconstruction supplement (S3.9-EXT-REAL-CASE, supplementary case).

Scope: the reconstructed telecom process (our reconstruction from the published
Figure 10) against the four Table-13 rules, non-LLM baseline only.

The real-LLM group is reported as MISSING here: the historical predictions are
bound to the Barrientos requirement strings, and Table 13 differs from them in
case/punctuation (e.g. "sim card" vs "SIM card"), so span offsets cannot be
reused without re-running the extraction, which this round does not authorize.
The mismatch is measured and recorded rather than papered over.

Zero LLM/API.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from bpc_hybrid import sim_case_c1 as core  # noqa: E402
from bpc_hybrid.sim_case_c1_transforms import flatten_collaboration  # noqa: E402

RECON = ROOT / "data" / "development" / "sim_case_c1" / "sun_figure10_reconstruction.bpmn"
TABLE13 = ROOT / "data" / "development" / "sim_case_c1" / "sun_table13_rules_v1.json"
RUN_DIR = ROOT / "outputs" / "development" / "sim_case_c1" / "supplement_v1"
REPORT_JSON = ROOT / "outputs" / "reports" / "sim_case_c1_supplement.json"
REPORT_MD = ROOT / "outputs" / "reports" / "sim_case_c1_supplement.md"
GAMMA_EXT = 0.5


def _sha(text: str) -> str:
    return core.sha256_bytes(text.encode("utf-8"))


def _normalise(text: str) -> str:
    return re.sub(r"[\s]+", " ", (text or "").strip().lower()).rstrip(".")


def _parse(payload: bytes, label: str) -> dict:
    import xml.etree.ElementTree as ET

    from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_bytes, validate_process_record

    flattened, info = flatten_collaboration(payload)
    contract = load_stage1_contract(core.STAGE1_CONTRACT)
    record = parse_bpmn_bytes(flattened, source_path=f"{label}.bpmn", contract=contract)
    if not getattr(validate_process_record(record), "valid", False):
        raise SystemExit(f"{label}: invalid stage1 record")
    return {"record": record, "xml_root": ET.fromstring(flattened), "flattened_xml": flattened,
            "flatten_info": info,
            "evidence": {"flattened_xml_sha256": core.sha256_bytes(flattened),
                         "process_record_sha256": _sha(json.dumps(record, sort_keys=True, ensure_ascii=False)),
                         "activities": len(record.get("activities", [])),
                         "gateways": len(record.get("gateways", [])),
                         "events": len(record.get("events", [])),
                         "flows": len(record.get("sequence_flows", [])),
                         "lanes": [lane.get("name") for lane in record.get("lanes", [])],
                         "unreachable": len(record.get("control_flow", {}).get("unreachable_node_ids", []))}}


def _write(path: Path, text: str, overwrite: bool) -> dict:
    if path.exists() and not overwrite:
        raise SystemExit(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return {"path": str(path.relative_to(core.REPO)).replace("\\", "/"), "sha256": _sha(text),
            "bytes": len(text.encode("utf-8"))}


def run(overwrite: bool, check_only: bool) -> dict:
    import spacy
    from bpc_hybrid.stage3_extended_violations import ExtendedViolationScorer
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity

    nlp = spacy.load("en_core_web_sm")
    thresholds = json.loads(core.SUN_CONFIG.read_text(encoding="utf-8"))["method"]["thresholds"]
    tau, gamma, theta = float(thresholds["tau"]), float(thresholds["gamma"]), float(thresholds["theta"])
    sim = WinterSimilarity(nlp)
    sun = SunScorer(sim, tau, gamma, theta, nlp=nlp)
    ext = ExtendedViolationScorer(sim.text_pair, sim.text_pair, gamma, GAMMA_EXT)

    table13 = core.load_json(TABLE13)
    stage1 = _parse(RECON.read_bytes(), "sun10_reconstruction")
    model = core.build_model(stage1, nlp)

    predictions = core.load_predictions(1)
    reuse_audit = []
    barrientos_texts = core.load_requirements()
    for rule in table13["rules"]:
        mapped = rule["maps_to_barrientos"]
        rid, version = mapped.split("/")
        text = barrientos_texts.get((rid, int(version[1:])), "")
        sample_id = f"SIM_card_scenario/{rid}/{version}"
        exact = text == rule["text"]
        normalised = _normalise(text) == _normalise(rule["text"])
        reuse_audit.append({
            "table13_rule": rule["rule_id"], "mapped_prediction": sample_id,
            "exact_text_match": exact, "normalised_text_match": normalised,
            "reusable": bool(exact),
            "reason": ("exact match" if exact else
                       "case/punctuation differs; span offsets are bound to the original string"),
            "normalisation_used": "strip + casefold + whitespace collapse + trailing period",
        })

    plan = {
        "schema_version": "sim_case_c1_supplement_plan@1.0.0",
        "run_id": "sim_case_c1_supplement_v1",
        "claim_scope": "development_supplement_reconstructed_model_not_authors_model",
        "written_before_scoring": True,
        "model_identity": "our reconstruction from the published Figure 10 (not the authors' model)",
        "groups_run": {"A": "non-LLM deterministic adapter + Sun-style three types (+ four extended types reported as extension)"},
        "groups_missing": {"B": "real-LLM Stage 2 not run", "C": "depends on B"},
        "thresholds": {"tau": tau, "gamma": gamma, "theta": theta, "gamma_ext": GAMMA_EXT},
        "inputs": {"reconstruction": core.artifact(RECON), "table13": core.artifact(TABLE13),
                   "predictions_repeat01": predictions["artifact"]},
        "prediction_reuse_audit": reuse_audit,
        "paper_readings": {"text": table13["paper_reading_text"], "figure": table13["paper_reading_figure"],
                           "conflict_zh": table13["conflict_note_zh"]},
    }

    rows = []
    for rule in table13["rules"]:
        outcome = core.stage2_group_a(rule["rule_id"], rule["text"], nlp)
        if not outcome["ok"]:
            rows.append({"rule_id": rule["rule_id"], "check": "*", "status": core.STATUS_UNDETERMINED,
                         "reason": outcome["error"]})
            continue
        sentence = core.apply_role_binding(outcome["sentence"])
        sentence["rule_id"] = rule["rule_id"]
        sentence["sentence_text"] = rule["text"]
        record = core.build_rule_record(sentence)
        three = core.run_three_types(sun, record, model)
        activity_id, activity_sim, activity_name = core.best_activity_for(sentence, model, sim)
        four, surfaces = core.run_extended_types(ext, sentence, model, stage1["record"],
                                                stage1["xml_root"], activity_id)
        for name, result in {**three, **four}.items():
            rows.append({"rule_id": rule["rule_id"], "check": name, "status": result["status"],
                         "score": result.get("score"), "reason": result.get("reason"),
                         "group": "A",
                         "family": "three_types" if name in three else "four_extended_extension"})
        rule_entry = {"rule_id": rule["rule_id"], "source": rule["source"],
                      "rule_text_sha256": _sha(rule["text"]), "rule_text_length": len(rule["text"]),
                      "rule_record": record, "sentence": {k: v for k, v in sentence.items() if k != "sentence_text"},
                      "mapped_activity": {"id": activity_id, "name": activity_name, "similarity": activity_sim},
                      "surfaces": {k: (v if not isinstance(v, list) else v[:8]) for k, v in surfaces.items()}}
        rows.append({"rule_id": rule["rule_id"], "check": "_rule_record", "status": "info",
                     "group": "A", "detail": rule_entry})

    capsule = {"schema_version": "sim_case_c1_supplement@1.0.0", "run_id": plan["run_id"],
               "claim_scope": plan["claim_scope"], "plan": plan,
               "model_evidence": stage1["evidence"], "rows": rows,
               "summary": {"checks": sum(1 for r in rows if r["check"] != "_rule_record"),
                           "status_counts": {s: sum(1 for r in rows if r.get("status") == s)
                                             for s in ("violation", "satisfied", "undetermined", "not_applicable")}}}

    if check_only:
        return {"status": "CHECK_OK", "summary": capsule["summary"],
                "reuse_audit": reuse_audit, "model": stage1["evidence"]}

    outputs = {
        "plan": _write(RUN_DIR / "plan.json", json.dumps(plan, ensure_ascii=False, indent=1) + "\n", overwrite),
        "capsule": _write(RUN_DIR / "capsule.json", json.dumps(capsule, ensure_ascii=False, indent=1) + "\n", overwrite),
        "report_json": _write(REPORT_JSON, json.dumps(
            {"schema_version": capsule["schema_version"], "run_id": plan["run_id"],
             "claim_scope": plan["claim_scope"], "model_identity": plan["model_identity"],
             "groups_run": plan["groups_run"], "groups_missing": plan["groups_missing"],
             "thresholds": plan["thresholds"], "inputs": plan["inputs"],
             "model_evidence": stage1["evidence"], "prediction_reuse_audit": reuse_audit,
             "summary": capsule["summary"],
             "rows": [r for r in rows if r["check"] != "_rule_record"],
             "paper_readings": plan["paper_readings"]}, ensure_ascii=False, indent=1) + "\n", overwrite),
    }
    outputs["report_md"] = _write(REPORT_MD, render_md(capsule), overwrite)
    _write(RUN_DIR / "manifest.json", json.dumps(
        {"schema_version": "sim_case_c1_supplement_manifest@1.0.0", "run_id": plan["run_id"],
         "inputs": plan["inputs"], "outputs": outputs, "api_calls": 0, "network": False},
        ensure_ascii=False, indent=1) + "\n", overwrite)
    return {"status": "BUILT", "summary": capsule["summary"],
            "outputs": {k: v["path"] for k, v in outputs.items()}}


def render_md(capsule: dict) -> str:
    plan, rows = capsule["plan"], capsule["rows"]
    lines = [
        "# 补充案例：Sun Figure 10 重建模型上的非 LLM 基线（S3.9-EXT-REAL-CASE）",
        "",
        f"- run: `{capsule['run_id']}`；口径：**{capsule['claim_scope']}**",
        f"- 模型身份：**{plan['model_identity']}**（重建件，非作者原模型）",
        f"- 阈值：tau={plan['thresholds']['tau']}, gamma={plan['thresholds']['gamma']}, "
        f"theta={plan['thresholds']['theta']}, gamma_ext={plan['thresholds']['gamma_ext']}",
        f"- 模型证据：activities={capsule['model_evidence']['activities']}, "
        f"gateways={capsule['model_evidence']['gateways']}, events={capsule['model_evidence']['events']}, "
        f"flows={capsule['model_evidence']['flows']}, lanes={capsule['model_evidence']['lanes']}, "
        f"不可达节点={capsule['model_evidence']['unreachable']}",
        "",
        "## 1. 本轮实际运行的组与缺失的组",
        "",
        f"- 已运行：{json.dumps(plan['groups_run'], ensure_ascii=False)}",
        f"- **缺失**：{json.dumps(plan['groups_missing'], ensure_ascii=False)}",
        "",
        "## 2. 历史真实 LLM 预测复用审计（Table 13 文本 vs 既有预测输入）",
        "",
        "| Table 13 | 对应既有输入 | 完全相同 | 规范化后相同 | 可复用 | 原因 |",
        "|---|---|---|---|---|---|",
    ]
    for item in plan["prediction_reuse_audit"]:
        lines.append(f"| {item['table13_rule']} | `{item['mapped_prediction']}` | "
                     f"{item['exact_text_match']} | {item['normalised_text_match']} | "
                     f"{item['reusable']} | {item['reason']} |")
    lines += ["", "## 3. 逐条结果（非 LLM 基线，A 组）", "",
              "| 规则 | 检测项 | 族 | 状态 | 分数 | 原因 |", "|---|---|---|---|---|---|"]
    for row in rows:
        if row["check"] == "_rule_record":
            continue
        lines.append(f"| {row['rule_id']} | {row['check']} | {row.get('family')} | {row['status']} | "
                     f"{row.get('score')} | {row.get('reason') or '—'} |")
    lines += ["", "## 4. 规则记录与映射（证据）", ""]
    for row in rows:
        if row["check"] != "_rule_record":
            continue
        detail = row["detail"]
        lines.append(f"- **{detail['rule_id']}**（{detail['source']}）：actions={detail['rule_record']['actions']}，"
                     f"actors={detail['rule_record']['actors']}，order_relations={detail['rule_record']['order_relations']}，"
                     f"condition={detail['rule_record']['condition']!r}，best_activity={detail['mapped_activity']}")
    lines += ["", "## 5. 论文两种读法（仅作文献声明，不作 Gold）", "",
              f"- 正文：{plan['paper_readings']['text']['statement']}",
              f"- Figure 10：{plan['paper_readings']['figure']['statement']}",
              f"- 冲突：{plan['paper_readings']['conflict_zh']}",
              "",
              "## 6. 缺项与边界", "",
              "- 真实 LLM 组（B/C）在本补充案例中**未运行**：既有预测绑定 Barrientos 输入字符串，"
              "与 Table 13 存在大小写/标点差异，span 偏移不可直接复用，本轮不授权重新调用。",
              "- 重建件由我方按 Figure 10 重建，正式版未取得；18 项歧义见 provenance 文件。",
              "- 本结果是开发性补充案例，不构成对论文原始实验的复现。",
              ""]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    print(json.dumps(run(overwrite=args.overwrite, check_only=args.check), ensure_ascii=False, indent=1)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
