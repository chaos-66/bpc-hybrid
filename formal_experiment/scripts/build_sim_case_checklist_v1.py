# -*- coding: utf-8 -*-
"""Build the Case C (SIM card scenario) per-item checklist capsule (S3.9-EXT-REAL-CASE, C0).

This builder is MECHANICAL and answer-independent:

* it binds every input by path + sha256 (Barrientos SIM artifact, ground-truth
  baselines, the existing real-LLM predictions, and the curated proposal file);
* it re-parses the process model and the requirement file so the checklist rows
  rest on evidence read from disk, not on prose copied from a report;
* it merges the curated per-item proposals (rule meaning, conflicts, proposed
  expectation, confirmation flags) supplied by
  ``data/development/sim_case_c1/case_items_v1.json``;
* it validates coverage (every requirement id, every external deviation, every
  empty-text exclusion) and fails closed on any gap;
* it writes TWO artifacts:
    - local-only full capsule under ``outputs/development/sim_case_c1/``
      (gitignored; may contain restricted corpus text), and
    - a committable summary under ``outputs/reports/`` that is asserted to
      contain NO substring of >= 40 characters from the restricted corpus text.

It performs NO inference, loads no model, calls no API and never writes the
answer key into any prediction input.  Zero LLM/API, offline, deterministic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
REF = REPO / "references" / "barrientos_2026"

BPMN = REF / "artifact_input" / "process_models" / "SIM_card_scenario" / "SIM_card_scenario.bpmn"
REQUIREMENTS = REF / "artifact_input" / "requirements" / "SIM_card_scenario" / "SIM_card_scenario.json"
GT_DIR = REF / "evaluation" / "ground_truth"
STEP1 = GT_DIR / "step_1_baseline.json"
STEP2 = GT_DIR / "step_2_baseline.json"
STEP3 = GT_DIR / "step_3_baseline.json"
SUN_PDF = REPO / "references" / "papers" / "Sun_2024_Design_time_BPC.pdf"

PRED_DIR = ROOT / "outputs" / "development" / "barrientos_ablation_suite_v2" / "OURS-FULL"
PRED_REPEATS = [PRED_DIR / f"repeat-{i:02d}" / "canonical_predictions.jsonl" for i in range(1, 6)]

CURATED = ROOT / "data" / "development" / "sim_case_c1" / "case_items_v1.json"
LOCAL_DIR = ROOT / "outputs" / "development" / "sim_case_c1"
REPORT_JSON = ROOT / "outputs" / "reports" / "sim_case_c1_checklist.json"
REPORT_MD = ROOT / "outputs" / "reports" / "sim_case_c1_checklist.md"

SIM_IDS = ["r8", "r9", "r10", "r11", "r12", "r13"]
SHORT_FRAGMENT_LEN = 30
RESTRICTED_MIN_LEN = 40

# Keys allowed into the committable summary (short fragments, counts, hashes,
# verdicts only — never full corpus text).
COMMITTABLE_KEYS = (
    "schema_version", "case", "claim_scope", "is_gold", "performance_claim_ready",
    "inputs", "binding_policy", "process_structure", "prediction_reuse", "coverage",
    "taxonomy_reading_aid", "taxonomy_reading_aid_boundary", "items",
    "paper_conflict_record", "capability_probes", "open_questions",
)

# Fields of our own taxonomy, reported for transparency only.  Per the v4 task
# spec this table is a READING AID: it is never used for scoring and never used
# to synthesise an expected result.
TAXONOMY_READING_AID = {
    "missing_activity": "missing_action（活动存在性）",
    "wrong_role": "incorrect_actor（执行者）",
    "sequence_constraint_removal": "out_of_order（顺序）",
    "missing_timer": "constraint_violated（时限约束）",
    "time_constraint_removal": "constraint_violated（时限约束）",
    "time_constraint_relaxation": "constraint_violated（时限约束）",
    "XOR_condition_modification": "required_condition_not_enforced（条件）",
    "missing_XOR": "required_condition_not_enforced（条件）",
    "XOR_removal": "required_condition_not_enforced（条件）",
    "redundant_activity": "不在本分类体系（过度合规）",
    "unexpected_activity": "不在本分类体系（过度合规）",
    "redundant_constraint": "不在本分类体系（过度合规）",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def artifact(path: Path) -> dict:
    payload = path.read_bytes()
    return {
        "path": rel(path),
        "sha256": sha256_bytes(payload),
        "bytes": len(payload),
    }


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def tag(elem) -> str:
    return elem.tag.split("}")[1]


# ---------------------------------------------------------------------------
# process model
# ---------------------------------------------------------------------------

def parse_process_model(path: Path) -> dict:
    root = ET.fromstring(path.read_bytes())
    named = {e.get("id"): e.get("name") for e in root.iter() if e.get("id") and e.get("name")}
    tasks, subprocesses, gateways, events = [], [], [], []
    for e in root.iter():
        kind = tag(e)
        if kind in ("task", "userTask", "serviceTask", "manualTask", "sendTask", "receiveTask", "scriptTask"):
            tasks.append({"id": e.get("id"), "label": e.get("name")})
        elif kind in ("subProcess", "callActivity"):
            subprocesses.append({"id": e.get("id"), "label": e.get("name")})
        elif kind.endswith("Gateway"):
            gateways.append({"id": e.get("id"), "kind": kind, "label": e.get("name")})
        elif kind.endswith("Event"):
            events.append({"id": e.get("id"), "kind": kind, "label": e.get("name")})

    lanes = []
    for process in [e for e in root.iter() if tag(e) == "process"]:
        for lane_set in [c for c in process if tag(c) == "laneSet"]:
            for lane in [x for x in lane_set if tag(x) == "lane"]:
                refs = [named.get(r.text, r.text) for r in lane if tag(r) == "flowNodeRef"]
                lanes.append({"process": process.get("name"), "lane_id": lane.get("id"), "elements": refs})

    flows = []
    for sf in [e for e in root.iter() if tag(e) == "sequenceFlow"]:
        conditions = [c for c in sf if tag(c) == "conditionExpression"]
        flows.append({
            "id": sf.get("id"),
            "source": named.get(sf.get("sourceRef"), sf.get("sourceRef")),
            "target": named.get(sf.get("targetRef"), sf.get("targetRef")),
            "label": sf.get("name"),
            "condition_expression": conditions[0].text if conditions else None,
        })

    timer_defs = sum(1 for e in root.iter() if tag(e) == "timerEventDefinition")
    boundary_defs = sum(1 for e in root.iter() if tag(e) == "boundaryEvent")
    condition_expressions = sum(1 for e in root.iter() if tag(e) == "conditionExpression")

    order_pairs = [(f["source"], f["target"]) for f in flows]
    return {
        "artifact": artifact(path),
        "participants": [e.get("name") for e in root.iter() if tag(e) == "participant"],
        "lanes": lanes,
        "tasks": tasks,
        "subprocesses": subprocesses,
        "gateways": gateways,
        "events": events,
        "flows": flows,
        "counts": {
            "processes": sum(1 for e in root.iter() if tag(e) == "process"),
            "tasks": len(tasks),
            "subprocesses": len(subprocesses),
            "gateways": len(gateways),
            "events": len(events),
            "flows": len(flows),
            "timer_event_definitions": timer_defs,
            "boundary_events": boundary_defs,
            "condition_expressions": condition_expressions,
            "labelled_flows": sum(1 for f in flows if f["label"]),
        },
        "order_edges": order_pairs,
    }


# ---------------------------------------------------------------------------
# requirements / ground truth
# ---------------------------------------------------------------------------

def parse_requirements(path: Path) -> dict:
    entries = load_json(path)
    rows = []
    for e in entries:
        text = e.get("text") or ""
        rows.append({
            "rule_id": e.get("ID"),
            "version": int(e.get("version")),
            "text_sha256": sha256_bytes(text.encode("utf-8")),
            "text_length": len(text),
            "empty": len(text.strip()) == 0,
            "text": text,
            "fragment": collapse(text)[:SHORT_FRAGMENT_LEN],
        })
    return {"artifact": artifact(path), "rows": rows}


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_step3(path: Path) -> dict:
    entries = load_json(path)
    rows = {}
    for e in entries:
        devs = []
        for d in e.get("deviations") or []:
            devs.append({
                "type": d.get("type"),
                "bpmn_element": d.get("bpmn_element"),
                "element_label": d.get("element_label"),
                "reading_aid": TAXONOMY_READING_AID.get(d.get("bpmn_element"), "未映射"),
            })
        mitigation = e.get("mitigation_action")
        rows[e["id"]] = {
            "deviations": devs,
            "mitigation": mitigation,
            "mitigation_sha256": sha256_bytes((mitigation or "").encode("utf-8")),
            "mitigation_fragment": collapse(mitigation)[:SHORT_FRAGMENT_LEN],
        }
    return {"artifact": artifact(path), "rows": rows}


def parse_step2(path: Path) -> dict:
    entries = load_json(path)
    rows = {}
    for e in entries:
        changes = [{"type": c.get("type"), "from": c.get("from"), "to": c.get("to")}
                   for c in (e.get("changes") or [])]
        rows[e["id"]] = changes
    return {"artifact": artifact(path), "rows": rows}


def parse_step1(path: Path) -> dict:
    entries = load_json(path)
    rows = {}
    for e in entries:
        versions = e.get("versions") or {}
        rows[e["id"]] = {
            "both_versions": bool(e.get("both_versions")),
            "versions": {
                key: {
                    "norm_length": len((val or {}).get("norm") or ""),
                    "precondition_length": len((val or {}).get("precondition") or ""),
                }
                for key, val in versions.items()
            },
        }
    return {"artifact": artifact(path), "rows": rows}


# ---------------------------------------------------------------------------
# existing real-LLM predictions (reuse audit)
# ---------------------------------------------------------------------------

def parse_predictions(paths: list[Path]) -> dict:
    repeats = []
    for path in paths:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        sim = [r for r in rows if str(r.get("sample_id", "")).startswith("SIM_card_scenario/")]
        per_sample = {}
        for r in sim:
            clause = (r.get("record") or {}).get("clauses") or [{}]
            c0 = clause[0] if clause else {}
            per_sample[r["sample_id"]] = {
                "modality": (c0.get("modality") or {}).get("label"),
                "actions": len(c0.get("actions") or []),
                "actors": len(c0.get("actors") or []),
                "conditions": len(c0.get("conditions") or []),
                "constraints": len(c0.get("constraints") or []),
                "exceptions": len(c0.get("exceptions") or []),
                "order_relations": len(c0.get("order_relations") or []),
                "actor_texts": [collapse((a or {}).get("text"))[:SHORT_FRAGMENT_LEN]
                                for a in (c0.get("actors") or [])],
                "action_texts": [collapse((a or {}).get("text"))[:SHORT_FRAGMENT_LEN]
                                 for a in (c0.get("actions") or [])],
            }
        repeats.append({"artifact": artifact(path), "sim_rows": len(sim), "per_sample": per_sample})

    ids = sorted({sid for rep in repeats for sid in rep["per_sample"]})
    return {
        "repeats": repeats,
        "independent_inputs": len(ids),
        "sample_ids": ids,
        "repeat_count": len(repeats),
        "total_rows": sum(rep["sim_rows"] for rep in repeats),
        "order_relations_total": sum(v["order_relations"] for rep in repeats for v in rep["per_sample"].values()),
        "observed_repeat_agreement": all(
            rep["per_sample"] == repeats[0]["per_sample"] for rep in repeats
        ),
    }


# ---------------------------------------------------------------------------
# coverage + restricted-text guard
# ---------------------------------------------------------------------------

def build_restricted_corpus(req: dict, step3: dict) -> list[str]:
    texts = [r["text"] for r in req["rows"] if r["text"].strip()]
    texts += [v["mitigation"] for v in step3["rows"].values() if v["mitigation"]]
    return texts


def assert_no_restricted_text(payload: str, corpus: list[str]) -> dict:
    hits = []
    for text in corpus:
        norm = collapse(text)
        for i in range(0, max(0, len(norm) - RESTRICTED_MIN_LEN) + 1):
            window = norm[i:i + RESTRICTED_MIN_LEN]
            if window and window in payload:
                hits.append(window)
                break
    return {"restricted_windows_checked": len(corpus), "min_window": RESTRICTED_MIN_LEN, "hits": hits}


def check_coverage(req: dict, step3: dict, curated: dict) -> dict:
    curated_ids = [i["rule_id"] for i in curated["items"]]
    missing = [rid for rid in SIM_IDS if rid not in curated_ids]
    extra = [rid for rid in curated_ids if rid not in SIM_IDS]
    empty = [f"{r['rule_id']}/v{r['version']}" for r in req["rows"] if r["empty"]]
    deviations = {rid: len(step3["rows"][rid]["deviations"]) for rid in SIM_IDS}
    return {
        "curated_items": len(curated_ids),
        "missing_curated_items": missing,
        "unexpected_curated_items": extra,
        "empty_text_entries": sorted(empty),
        "external_deviations_per_rule": deviations,
        "external_deviations_total": sum(deviations.values()),
    }


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def build() -> dict:
    curated = load_json(CURATED)
    req = parse_requirements(REQUIREMENTS)
    step1 = parse_step1(STEP1)
    step2 = parse_step2(STEP2)
    step3 = parse_step3(STEP3)
    process = parse_process_model(BPMN)
    preds = parse_predictions(PRED_REPEATS)

    coverage = check_coverage(req, step3, curated)
    if coverage["missing_curated_items"] or coverage["unexpected_curated_items"]:
        raise SystemExit(f"coverage failure: {coverage}")

    req_by_key = {(r["rule_id"], r["version"]): r for r in req["rows"]}
    rows = []
    for item in curated["items"]:
        rid = item["rule_id"]
        row = dict(item)
        row["external_annotation_source"] = {
            "deviations": step3["rows"][rid]["deviations"],
            "mitigation_fragment": step3["rows"][rid]["mitigation_fragment"],
            "mitigation_sha256": step3["rows"][rid]["mitigation_sha256"],
        }
        row["change_context"] = step2["rows"].get(rid)
        row["version_metadata"] = step1["rows"].get(rid)
        row["requirement_versions"] = [
            {
                "version": f"v{v}",
                "empty": req_by_key[(rid, v)]["empty"],
                "text_length": req_by_key[(rid, v)]["text_length"],
                "text_sha256": req_by_key[(rid, v)]["text_sha256"],
                "fragment": req_by_key[(rid, v)]["fragment"],
                "text": req_by_key[(rid, v)]["text"],
            }
            for v in (1, 2)
        ]
        row["prediction_evidence"] = {
            sid: preds["repeats"][0]["per_sample"][sid]
            for sid in preds["sample_ids"] if sid.startswith(f"SIM_card_scenario/{rid}/")
        }
        rows.append(row)

    doc = {
        "schema_version": "sim_case_c1_checklist@1.0.0",
        "case": "Case C - Barrientos Sun-derived SIM_card_scenario (derived case, not the authors' original model)",
        "claim_scope": "development_case_checklist_pending_user_confirmation",
        "is_gold": False,
        "performance_claim_ready": False,
        "inputs": {
            "process_model": process["artifact"],
            "requirements": req["artifact"],
            "step_1_baseline": step1["artifact"],
            "step_2_baseline": step2["artifact"],
            "step_3_baseline": step3["artifact"],
            "sun_2024_local_pdf": artifact(SUN_PDF),
            "curated_items": artifact(CURATED),
            "predictions_repeats": [rep["artifact"] for rep in preds["repeats"]],
        },
        "binding_policy": curated["binding_policy"],
        "process_structure": {
            "counts": process["counts"],
            "participants": process["participants"],
            "lanes": process["lanes"],
            "tasks": process["tasks"],
            "subprocesses": process["subprocesses"],
            "labelled_flows": [f for f in process["flows"] if f["label"]],
            "consent_position_evidence": consent_evidence(process),
        },
        "prediction_reuse": {
            "independent_inputs": preds["independent_inputs"],
            "repeat_count": preds["repeat_count"],
            "total_rows": preds["total_rows"],
            "sample_ids": preds["sample_ids"],
            "order_relations_total_all_rows": preds["order_relations_total"],
            "repeats_identical": preds["observed_repeat_agreement"],
        },
        "coverage": coverage,
        "taxonomy_reading_aid": TAXONOMY_READING_AID,
        "taxonomy_reading_aid_boundary": (
            "READING AID ONLY. It is not a scoring key, is not used to synthesise expected results, "
            "and must not be used to backfill missing fields."
        ),
        "items": rows,
        "paper_conflict_record": curated["paper_conflict_record"],
        "capability_probes": capability_probes(process, preds),
        "open_questions": [q for item in rows for q in item["proposed_expected"]["needs_confirmation"]],
    }
    return doc


def consent_evidence(process: dict) -> dict:
    edges = process["order_edges"]
    consent = "Ask for consent"
    preds = [s for s, t in edges if t == consent]
    succs = [t for s, t in edges if s == consent]
    return {
        "activity_present": any(t["label"] == consent for t in process["tasks"]),
        "predecessors": preds,
        "successors": succs,
        "preceded_by_store_data": "Store Data" in preds,
        "note_zh": "consent exists but follows Store Data (personal data already retrieved and stored)",
    }


def capability_probes(process: dict, preds: dict) -> dict:
    counts = process["counts"]
    return {
        "condition_triggered_termination": {
            "probe": "rule r8 requires a conditional process-termination branch",
            "model_surface": {"timer_event_definitions": counts["timer_event_definitions"],
                              "boundary_events": counts["boundary_events"]},
            "verdict": "unsupported_by_current_checks",
            "reason_zh": "现有时限比较判断数值边界是否满足，不判断“终止分支是否存在”；不得把两者等同",
        },
        "numeric_boundary_condition": {
            "probe": "rule r13 requires a numeric debt threshold on a gateway branch",
            "model_surface": {"condition_expressions": counts["condition_expressions"],
                              "labelled_flow_count": counts["labelled_flows"],
                              "labelled_flows": [f["label"] for f in process["flows"] if f["label"]]},
            "verdict": "partial",
            "reason_zh": "4 条带标签 flow 中只有一条是数值条件，其余为状态标签；现有条件检查针对“条件未被落实”，"
                         "不针对“条件数值与规则不一致”，故本探针只部分支持",
        },
        "consent_before_retrieval_order": {
            "probe": "rule r11 requires consent before any personal-data retrieval",
            "model_surface": consent_evidence(process),
            "extraction_surface": {"order_relations_all_rows": preds["order_relations_total"]},
            "verdict": "partial",
            "reason_zh": "模型顺序可读；但现有 LLM 抽取全部 0 条 order_relations，顺序检查在 B/C 组缺少规则侧关系",
        },
        "cross_participant_attribution": {
            "probe": "rule r10 requires the phone company (not the customer) to activate the SIM card",
            "model_surface": {
                "lanes": [{"process": l["process"], "elements": l["elements"]} for l in process["lanes"]],
                "target_activity": "Activate SIM card",
            },
            "verdict": "supported_if_actor_resolution_holds",
            "reason_zh": "活动归属可由参与者/泳道解析；需在运行报告给出解析证据",
        },
    }


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def render_local_md(doc: dict) -> str:
    lines = [
        "# Case C（SIM 卡入网）逐条核对表 —— local-only 全量版",
        "",
        f"- schema: `{doc['schema_version']}`；状态：**{doc['claim_scope']}**（非 Gold、未确认）",
        f"- 流程模型：`{doc['inputs']['process_model']['path']}` sha256 `{doc['inputs']['process_model']['sha256'][:16]}…`",
        f"- 需求文件：`{doc['inputs']['requirements']['path']}` sha256 `{doc['inputs']['requirements']['sha256'][:16]}…`",
        f"- 外部答案键：`{doc['inputs']['step_3_baseline']['path']}` sha256 `{doc['inputs']['step_3_baseline']['sha256'][:16]}…`",
        "",
        "## 流程结构（实测）",
        "",
        f"- task {doc['process_structure']['counts']['tasks']}、subProcess {doc['process_structure']['counts']['subprocesses']}、"
        f"gateway {doc['process_structure']['counts']['gateways']}、event {doc['process_structure']['counts']['events']}、"
        f"flow {doc['process_structure']['counts']['flows']}",
        f"- timer 定义 {doc['process_structure']['counts']['timer_event_definitions']}、"
        f"boundary event {doc['process_structure']['counts']['boundary_events']}、"
        f"conditionExpression {doc['process_structure']['counts']['condition_expressions']}、"
        f"带标签 flow {doc['process_structure']['counts']['labelled_flows']}",
        f"- 带标签 flow 明细：{doc['process_structure']['labelled_flows']}",
        f"- consent 位置证据：{doc['process_structure']['consent_position_evidence']}",
        "",
        "## 逐条",
        "",
    ]
    for item in doc["items"]:
        lines += [
            f"### {item['rule_id']} / {item['version']}",
            "",
            f"- 规则含义（我方转述）：{item['rule_meaning_zh']}",
            f"- 需求文本（local only）：" + " ｜ ".join(
                f"v{r['version']}: " + (r["text"] if r["text"] else "（空）") for r in item["requirement_versions"]),
            f"- 变更语境：{item['change_context']}",
            f"- 流程证据：{item['process_evidence']}",
            f"- 外部原始标注：{item['external_annotation_source']}",
            f"- 冲突：{item['conflicts']}",
            f"- 建议预期：{item['proposed_expected']}",
            f"- 预测证据（repeat-01，短片段）：{item['prediction_evidence']}",
            "",
        ]
    lines += ["## 能力核实", "", f"```json\n{json.dumps(doc['capability_probes'], ensure_ascii=False, indent=1)}\n```", ""]
    lines += ["## 论文冲突记录", "", f"```json\n{json.dumps(doc['paper_conflict_record'], ensure_ascii=False, indent=1)}\n```", ""]
    return "\n".join(lines) + "\n"


def render_report_md(doc: dict) -> str:
    counts = doc["process_structure"]["counts"]
    reuse = doc["prediction_reuse"]
    lines = [
        "# Case C（SIM 卡入网）逐条核对表（可提交摘要）",
        "",
        f"- 状态：**{doc['claim_scope']}**；`is_gold=false`；未运行比较；零 LLM/API。",
        "- 本文件只含 ID / 标签 / 短片段（<40 字符）/ 计数 / 哈希 / 判定；完整文本在 gitignored 的 local-only 目录。",
        "",
        "## 1. 输入绑定（sha256 前 16 位）",
        "",
        "| 输入 | 路径 | sha256 |",
        "|---|---|---|",
    ]
    for key, meta in doc["inputs"].items():
        if key == "predictions_repeats":
            for rep in meta:
                lines.append(f"| predictions | `{rep['path']}` | `{rep['sha256'][:16]}…` |")
        else:
            lines.append(f"| {key} | `{meta['path']}` | `{meta['sha256'][:16]}…` |")
    lines += [
        "",
        "## 2. 绑定政策",
        "",
        f"```json\n{json.dumps(doc['binding_policy'], ensure_ascii=False, indent=1)}\n```",
        "",
        "## 3. 流程结构事实（实测）",
        "",
        f"- task {counts['tasks']} / subProcess {counts['subprocesses']} / gateway {counts['gateways']} / event {counts['events']} / flow {counts['flows']}",
        f"- timer 定义 **{counts['timer_event_definitions']}**、boundary event **{counts['boundary_events']}**、"
        f"conditionExpression **{counts['condition_expressions']}**、带标签 flow **{counts['labelled_flows']}**",
        f"- 带标签 flow：{doc['process_structure']['labelled_flows']}",
        f"- consent：存在={doc['process_structure']['consent_position_evidence']['activity_present']}，"
        f"前驱={doc['process_structure']['consent_position_evidence']['predecessors']}，"
        f"紧跟 Store Data={doc['process_structure']['consent_position_evidence']['preceded_by_store_data']}",
        "",
        "## 4. 预测复用审计",
        "",
        f"- 独立输入 **{reuse['independent_inputs']}** 条；重复轮次 **{reuse['repeat_count']}**；总行数 **{reuse['total_rows']}**",
        f"- 全部行的 order_relations 合计：**{reuse['order_relations_total_all_rows']}**",
        f"- 5 轮抽取结果完全一致：**{reuse['repeats_identical']}**（重复不作独立样本）",
        f"- 独立输入 ID：{reuse['sample_ids']}",
        "",
        "## 5. 逐条核对表",
        "",
        "| 规则 | 版本 | 规则含义（我方转述） | 流程证据要点 | 外部原始标注 | 冲突 | 建议预期 | 需确认 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in doc["items"]:
        ev = item["process_evidence"]
        ev_brief = ev.get("note_zh") or ev.get("model_label") or ""
        ann = item["external_annotation_source"]
        dev = ann["deviations"][0] if ann["deviations"] else {}
        ann_brief = f"{dev.get('type')} / `{dev.get('bpmn_element')}` / {dev.get('element_label')}"
        conflict = "；".join(c["detail_zh"] for c in item["conflicts"]) or "—"
        q = ",".join(item["proposed_expected"]["needs_confirmation"]) or "—"
        lines.append(
            f"| {item['rule_id']} | {item['version']} | {item['rule_meaning_zh']} | {ev_brief} | {ann_brief} | "
            f"{conflict} | {item['proposed_expected']['status_proposal']}（{item['proposed_expected']['capability']}） | {q} |"
        )
    lines += [
        "",
        "## 6. 能力核实（§5.6）",
        "",
        "| 探针 | 结论 | 说明 |",
        "|---|---|---|",
    ]
    for name, probe in doc["capability_probes"].items():
        lines.append(f"| {name} | {probe['verdict']} | {probe['reason_zh']} |")
    lines += [
        "",
        "## 7. Sun 论文图文冲突",
        "",
        f"```json\n{json.dumps(doc['paper_conflict_record'], ensure_ascii=False, indent=1)}\n```",
        "",
        "## 8. 边界",
        "",
        "- 本核对表是**提案**，未经用户确认；不含 Gold，不构成性能结论。",
        "- 外部 `bpmn_element → 我们七类` 的映射表仅为**阅读辅助**，不作评分键、不用于合成预期结果。",
        "- Barrientos 语料许可为 `unknown_pending_confirmation`；本文件不含其长文本。",
        "",
    ]
    return "\n".join(lines) + "\n"


def to_committable(doc: dict) -> dict:
    """Copy the committable subset and strip every full-text corpus field.

    Full requirement sentences and full mitigation strings stay in the
    gitignored local capsule only; the committable summary keeps ids, versions,
    hashes, counts, short fragments (<40 chars) and our own verdicts.
    """
    out = {k: doc[k] for k in COMMITTABLE_KEYS}
    items = []
    for item in out["items"]:
        clean = {k: v for k, v in item.items() if k != "requirement_versions"}
        clean["requirement_versions"] = [
            {k: v for k, v in rv.items() if k != "text"} for rv in item["requirement_versions"]
        ]
        items.append(clean)
    out["items"] = items
    return out


def write(path: Path, text: str, overwrite: bool) -> dict:
    if path.exists() and not overwrite:
        raise SystemExit(f"refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return {"path": rel(path),
            "sha256": sha256_bytes(text.encode("utf-8")), "bytes": len(text.encode("utf-8"))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--overwrite", action="store_true", help="replace existing outputs")
    ap.add_argument("--check", action="store_true",
                    help="rebuild in memory, verify hash binding and the restricted-text guard, write nothing")
    args = ap.parse_args()

    doc = build()
    local_md = render_local_md(doc)
    report_md = render_report_md(doc)
    committable = to_committable(doc)
    report_json = json.dumps(committable, ensure_ascii=False, indent=1) + "\n"

    corpus = build_restricted_corpus(parse_requirements(REQUIREMENTS), parse_step3(STEP3))
    guard = assert_no_restricted_text(report_md + report_json, corpus)
    if guard["hits"]:
        raise SystemExit(f"restricted-text guard failed: {guard['hits']}")

    if args.check:
        print(json.dumps({
            "status": "CHECK_OK",
            "coverage": doc["coverage"],
            "restricted_guard": guard,
            "prediction_reuse": {k: v for k, v in doc["prediction_reuse"].items() if k != "sample_ids"},
            "items": len(doc["items"]),
            "open_questions": doc["open_questions"],
        }, ensure_ascii=False, indent=1))
        return 0

    outputs = {
        "local_checklist_json": write(LOCAL_DIR / "checklist.json",
                                      json.dumps(doc, ensure_ascii=False, indent=1) + "\n", args.overwrite),
        "local_checklist_md": write(LOCAL_DIR / "checklist.md", local_md, args.overwrite),
        "report_json": write(REPORT_JSON, report_json, args.overwrite),
        "report_md": write(REPORT_MD, report_md, args.overwrite),
    }
    manifest = {
        "schema_version": "sim_case_c1_checklist_manifest@1.0.0",
        "run_id": "sim_case_c1_checklist_v1",
        "claim_scope": "development_case_checklist_pending_user_confirmation",
        "inputs": doc["inputs"],
        "outputs": outputs,
        "coverage": doc["coverage"],
        "restricted_text_guard": guard,
        "prediction_reuse": {k: v for k, v in doc["prediction_reuse"].items() if k != "sample_ids"},
        "api_calls": 0,
        "network": False,
    }
    write(LOCAL_DIR / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", args.overwrite)
    print(json.dumps({"status": "BUILT", "outputs": {k: v["path"] for k, v in outputs.items()},
                      "coverage": doc["coverage"], "restricted_guard_hits": len(guard["hits"])},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
