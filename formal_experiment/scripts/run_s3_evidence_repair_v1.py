"""Offline S3.7 root-cause repair and diagnostic replay, never formal promotion."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.s3_evidence_checks_v1 import (  # noqa: E402
    EvidenceChecks, METHOD, evaluate_items, project_confirmed_temporal_notes, score_items,
)
from bpc_hybrid.sun_stage3.gdpr_capsule_converter import (  # noqa: E402
    ALL_MODALITIES, build_rule_records, sentence_texts_by_sample,
)
from bpc_hybrid.sun_stage3.sun_model import build_sun_models  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

RUN_ID = "s3_evidence_repair_v1"
REPORT = ROOT / "outputs/reports" / f"{RUN_ID}.json"
MARKDOWN = REPORT.with_suffix(".md")
MANIFEST = REPORT.with_suffix(".manifest.json")
INPUTS = [
    "data/input/gdpr7_stage2_input_v1.json",
    "data/gold/stage3/gdpr7_gold_rule_records_v1.json",
    "data/gold/stage3/stage3_violation_gold_v1.json",
    "data/development/human_review/stage3_gold_inference_v1.json",
    "data/development/human_review/gdpr7_human_confirmed_v1/case_acknowledgement.json",
    "data/predictions/gdpr7_human_rule_record_v1/predictions.json",
    "data/predictions/gdpr7_sun_rule_only_v1/predictions.json",
    "configs/sun_stage3_development_v1.json",
    "configs/stage1_structural_s11_s14.json",
    "outputs/reports/s3_oracle_gold_rules_v1.json",
    "outputs/reports/s3_downstream_paired_v1.json",
]
IMPLEMENTATION = [
    "src/bpc_hybrid/s3_evidence_checks_v1.py", "scripts/run_s3_evidence_repair_v1.py",
    "tests/test_s3_evidence_repair_v1.py",
    "src/bpc_hybrid/sun_stage3/gdpr_capsule_converter.py",
    "src/bpc_hybrid/sun_stage3/sun_scorer.py",
    "src/bpc_hybrid/sun_stage3/sun_model.py",
    "src/bpc_hybrid/winter_stage3/winter_similarity.py",
    "src/bpc_hybrid/stage1_process.py",
]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_hashes():
    paths = INPUTS + [p.relative_to(ROOT).as_posix()
                      for p in sorted((ROOT / "data/input/stage1_stage3/gdpr7").glob("*.bpmn"))]
    return {p: sha(ROOT / p) for p in paths}


def audit_scope(inference, violation_gold, gold_rules, case_ack):
    """Read annotation evidence ONLY in the post-prediction diagnostic step."""
    available = {r["rule_id"] for r in gold_rules["records"]}
    rows = []
    for item in violation_gold["items"]:
        references = {"article" + x for x in re.findall(r"\bArt(?:icle)?\s+(\d+)", item["decision_evidence"])}
        rows.append({"item_id": item["item_id"], "check_type": item["check_type"],
                     "process_id": item["process_id"], "rule_id": item["rule_id"],
                     "decision_violation_type": item["decision_violation_type"],
                     "decision_evidence": item["decision_evidence"],
                     "referenced_articles_absent_from_input": sorted(references - available)})
    return {
        "items": rows,
        "count": len(rows),
        "negative_control_count": sum(x["decision_violation_type"] is None for x in rows),
        "all_labels_equal_requested_check": all(x["decision_violation_type"] == x["check_type"] for x in rows),
        "unbound_target_count": sum(not any(k in x for k in
            ("target_action_id", "target_clause_id", "variant_path")) for x in inference["violation_items"]),
        "out_of_input_reference_items": [x["item_id"] for x in rows if x["referenced_articles_absent_from_input"]],
        "confirmed_local_case": case_ack,
        "requires_human_scope_resolution": True,
        "may_relabel_gold_automatically": False,
        "performance_claim_ready": False,
        "explanation_zh": "33条均为指定检查类型的正标签，推断输入未绑定目标活动/条款片段或变体。已确认的局部通知判断与v001/v002的检查范围尚未对齐。原表不足以证明自由违规分类能力或实际误报水平。",
    }


def build_report():
    import spacy
    before = input_hashes()
    nlp = spacy.load("en_core_web_sm")
    config = read("configs/sun_stage3_development_v1.json")
    thresholds = {k: config["method"]["thresholds"][k] for k in ("tau", "gamma", "theta")}
    scorer = EvidenceChecks(WinterSimilarity(nlp), **thresholds, nlp=nlp)
    models = build_sun_models(ROOT / "data/input/stage1_stage3/gdpr7",
                             ROOT / "configs/stage1_structural_s11_s14.json", nlp)
    input_doc = read("data/input/gdpr7_stage2_input_v1.json")
    texts = sentence_texts_by_sample(input_doc)
    inference = read("data/development/human_review/stage3_gold_inference_v1.json")
    gold_rules = read("data/gold/stage3/gdpr7_gold_rule_records_v1.json")
    rule_ids = sorted({x["rule_id"] for x in inference["violation_items"]})
    arms = {}
    for arm, folder, modalities, notes in [
        ("rules_only", "gdpr7_sun_rule_only_v1", ("obligation",), False),
        ("human_all_modalities_diagnostic", "gdpr7_human_rule_record_v1", ALL_MODALITIES, True),
        ("human_obligations", "gdpr7_human_rule_record_v1", ("obligation",), True),
    ]:
        capsule = read(f"data/predictions/{folder}/predictions.json")
        records, conversion = build_rule_records(capsule, texts, rule_ids, modalities)
        if notes:
            records, temporal = project_confirmed_temporal_notes(records, gold_rules)
        else:
            temporal = {"accepted": [], "rejected": [], "note": "Human annotations never enter the Rules-Only arm."}
        predictions = score_items(inference["violation_items"], records, models, scorer)
        arms[arm] = {"include_modalities": list(modalities), "conversion": conversion,
                     "temporal_projection": temporal, "rule_records": records, "predictions": predictions}
    # Scoped mechanism check, separate from the 33-item article-level table.
    source = next(r for r in gold_rules["records"] if r["sample_id"] == "gdpr_article33_s001")
    clause = source["clauses"][0]
    local_actions = [x["text"] for x in clause["actions"]]
    local_actors = [x["text"] for x in clause["actors"]]
    local_pairs = [{"actor": local_actors[0], "action": local_actions[0]}]
    model = models["gdpr_1_data_breach"]
    local = {"scope": "article33_s001 notification activity only; not full Article 33 compliance",
             "missing_action": scorer.missing_action(local_actions, model),
             "incorrect_actor": scorer.incorrect_actor(local_actions, local_actors, model, local_pairs)}
    # Predictions above use no violation labels, evidence, or candidate answers.
    violation_gold = read("data/gold/stage3/stage3_violation_gold_v1.json")
    for arm in arms.values():
        arm["evaluation_against_legacy_gold"] = evaluate_items(arm["predictions"], violation_gold["items"])
    case_ack = read("data/development/human_review/gdpr7_human_confirmed_v1/case_acknowledgement.json")
    scope = audit_scope(inference, violation_gold, gold_rules, case_ack)
    if input_hashes() != before:
        raise RuntimeError("read-only input binding changed during run")
    return {
        "schema_version": "s3_evidence_repair@1.0.0", "run_id": RUN_ID, "method": METHOD,
        "claim_scope": "development_diagnostic_not_formal_oracle",
        "performance_claim_ready": False, "thresholds": thresholds,
        "input_hashes": before, "arms": arms, "scope_audit": scope,
        "local_notification_check": local,
        "nlp": {"model": "en_core_web_sm", "version": nlp.meta.get("version"),
                "static_vector_shape": list(nlp.vocab.vectors.shape),
                "note": "The frozen backend has no static vocabulary vectors. Its contextual similarity is not a calibrated semantic entailment score."},
        "repairs": ["explicit confirmed temporal notes compiled to uniquely anchored runtime edges",
                    "empty/unmapped/ambiguous order inputs produce unknown, never numeric zero",
                    "same predicate plus shared content can bridge full phrases and short labels",
                    "executor checked per matched activity; business objects do not become actors",
                    "partial evidence, negative controls, and missing outputs retain denominators",
                    "same obligation modality policy available for both rule sources"],
        "remaining_blockers": ["33-item target scope and original/variant bindings require human resolution",
                               "missing external article inputs and additional confirmed temporal anchors",
                               "predicate paraphrases and unresolved pronouns remain unmapped",
                               "new method has not been validated on a held-out dataset"],
        "safety": {"gold_modified": False, "old_results_modified": False, "thresholds_changed": False,
                   "new_llm_api_calls": 0, "formal_promotion": False},
    }


def markdown(report):
    lines = ["# Stage 3 零分根因与证据修复", "",
             "本报告是开发诊断，旧33条标签的检查范围仍待核实，不是正式Oracle或性能提升结论。", "",
             "## 已确认的根因", "",
             "- 法条与活动标签表达粒度不同，执行者检查在动作匹配处被挡住。",
             "- 已确认材料含3条文字顺序说明，但旧转换器只读空的结构化关系字段。",
             "- 旧顺序检查把无关系/无映射的分母0返回为0分，应区分无法判断和满足。",
             "- 原执行者候选混入活动业务对象，且跨动作聚合，可能制造误报。",
             "- 人工规则全情态混入义务检查，权利主体可能被误当成活动执行者。",
             "- 33条全为正标签，检查目标未绑定具体活动/规范/变体，部分证据还依赖未输入的法条。", "",
             "## 修复后逐来源核账", "",
             "以下F1仅对旧标签作诊断复算。低分不自动证明实现错误，高分也不能解除标签范围冲突。", "",
             "| 来源 | 漏做动作F1 | 执行者F1 | 顺序F1 | 宏F1 | 无法判断 |", "|---|---:|---:|---:|---:|---:|"]
    for name, arm in report["arms"].items():
        ev = arm["evaluation_against_legacy_gold"]
        vals = [ev["per_type"][t]["f1"] for t in ("missing_action", "incorrect_actor", "out_of_order")]
        lines.append(f"| {name} | {vals[0]:.4f} | {vals[1]:.4f} | {vals[2]:.4f} | {ev['macro_f1']:.4f} | {ev['unknown_total']} |")
    temporal = report["arms"]["human_obligations"]["temporal_projection"]
    lines += ["", "## 恢复的人工文字顺序说明", ""]
    for relation in temporal["accepted"]:
        lines.append(f"- `{relation['sample_id']}`：`{relation['before']['text']}` 先于 `{relation['after']['text']}`。端点仅作顺序锚点，不新增必须执行的义务。")
    local = report["local_notification_check"]
    lines += ["", "## 直接核实的通知活动", "",
              "原BPMN中有 Notify national authority，位于 Data Controller 的流程。",
              f"修复后的局部动作检查：{local['missing_action']['status']}；执行者检查：{local['incorrect_actor']['status']}。",
              "这与用户已确认的局部读图意见一致。v001/v002的旧标签检查范围仍待核实，不据此改Gold，也不据此断言整条法规合规。", "",
              "## 需要补齐的评价契约", "",
              "| 条目 | 检查类型 | 证据引用但输入不存在的法条 |", "|---|---|---|"]
    for item in report["scope_audit"]["items"]:
        if item["referenced_articles_absent_from_input"]:
            lines.append(f"| {item['item_id']} | {item['check_type']} | {', '.join(item['referenced_articles_absent_from_input'])} |")
    lines += ["", "每条样本需明确原图还是变体、目标规范与活动、预期状态及证据。保留33条旧标签，复核完成后才发布新的评价集。", "",
              "## 验证边界", "",
              "独立合成回归测试覆盖正确/错误执行者、正序/倒序、空关系、歧义映射和业务对象误报。它们是程序验证，不是GDPR性能结果。",
              "冻结Sun实现、阈值、Gold、原报告均保留。新检查器是独立的开发版本。零LLM/API。", ""]
    return "\n".join(lines)


def verify_manifest():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for section in ("inputs", "implementation", "artifacts"):
        for name, expected in manifest[section].items():
            if sha(ROOT / name) != expected:
                raise RuntimeError(f"{section} hash mismatch: {name}")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    if report["performance_claim_ready"] or report["safety"]["gold_modified"]:
        raise RuntimeError("diagnostic / Gold boundary violated")
    for arm in report["arms"].values():
        if len(arm["predictions"]) != 33 or arm["evaluation_against_legacy_gold"]["dropped_items"]:
            raise RuntimeError("diagnostic denominator mismatch")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    if args.check or args.replay:
        stored = verify_manifest()
        # JSON serializes runtime relation tuples as arrays. Compare the wire
        # representation so a tuple/list difference is not reported as drift.
        if args.replay and json.dumps(build_report(), sort_keys=True) != json.dumps(stored, sort_keys=True):
            raise RuntimeError("deterministic replay mismatch")
        print("S3 EVIDENCE REPAIR VERIFIED")
        return 0
    if any(p.exists() for p in (REPORT, MARKDOWN, MANIFEST)):
        raise FileExistsError("refusing to overwrite diagnostic report")
    report = build_report()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    MARKDOWN.write_bytes(markdown(report).encode("utf-8"))
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest = {"schema_version": "s3_evidence_repair_manifest@1.0.0", "run_id": RUN_ID,
                "git_commit_before_checkpoint": commit, "inputs": report["input_hashes"],
                "implementation": {p: sha(ROOT / p) for p in IMPLEMENTATION},
                "artifacts": {p.relative_to(ROOT).as_posix(): sha(p) for p in (REPORT, MARKDOWN)},
                "claim_scope": report["claim_scope"], "safety": report["safety"]}
    MANIFEST.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    verify_manifest()
    print(json.dumps({"run_id": RUN_ID, "report": REPORT.relative_to(ROOT).as_posix(),
                      "performance_claim_ready": False, "new_llm_api_calls": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
