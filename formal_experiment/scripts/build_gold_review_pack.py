# -*- coding: utf-8 -*-
"""Build the legacy development review pack (never formal Gold).

Reads prediction files and audit summary, identifies samples that need
human review, and generates:
1. Gold review candidates (with all predictions + issue flags)
2. Gold review template (human-fillable, gold fields = null)
3. Review instructions (Chinese)
4. Pack report (Chinese)

Usage:
    python scripts/build_gold_review_pack.py --allow-legacy-schema

The current schema lacks phrase spans and full input coverage.  This command is
blocked by default and must never be used to start formal human annotation.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

# Input paths
_CANDIDATES_PATH = _PROJECT_ROOT / "data" / "development" / "gdpr50" / "r15_gdpr50_candidate_samples.jsonl"
_PREDICTION_FILES = {
    "sun_style": _PROJECT_ROOT / "data" / "development" / "predictions" / "sun_rule_only.jsonl",
    "spacy_enhanced": _PROJECT_ROOT / "data" / "development" / "predictions" / "exploratory_spacy.jsonl",
    "rule_plus_llm": _PROJECT_ROOT / "data" / "development" / "predictions" / "sun_llm_fallback.jsonl",
}
_AUDIT_SUMMARY_PATH = _PROJECT_ROOT / "outputs" / "development" / "stage2_to_stage3_compat_audit_summary.json"

# Output paths
_OUTPUT_DIR = _PROJECT_ROOT / "data" / "development" / "gold_review"
_CANDIDATES_OUT = _OUTPUT_DIR / "sun_stage2_gold_review_candidates.jsonl"
_TEMPLATE_OUT = _OUTPUT_DIR / "sun_stage2_gold_review_template.jsonl"
_INSTRUCTIONS_OUT = _PROJECT_ROOT / "outputs" / "development" / "legacy_gold_review_instructions.md"
_REPORT_OUT = _PROJECT_ROOT / "outputs" / "development" / "legacy_gold_review_pack_report.md"


def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file, skipping bad lines."""
    records = []
    if not path.exists():
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def load_source_texts() -> dict[str, str]:
    """Load source_text from candidate samples file."""
    texts = {}
    for rec in load_jsonl(_CANDIDATES_PATH):
        sid = rec.get("sample_id", "")
        texts[sid] = rec.get("text", "")
    return texts


def load_predictions_by_method() -> dict[str, dict[str, dict]]:
    """Load all prediction files, indexed by method -> sample_id -> record."""
    result = {}
    for method, path in _PREDICTION_FILES.items():
        method_map = {}
        for rec in load_jsonl(path):
            sid = rec.get("sample_id", "")
            if sid:
                method_map[sid] = rec
        result[method] = method_map
    return result


def load_audit_records() -> dict[str, dict[str, dict]]:
    """Load audit summary, indexed by filename -> sample_id -> audit record."""
    if not _AUDIT_SUMMARY_PATH.exists():
        return {}
    with open(_AUDIT_SUMMARY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    result = {}
    for file_result in data.get("results", []):
        fn = file_result["filename"]
        method_map = {}
        for rec in file_result.get("records", []):
            sid = rec.get("sample_id", "")
            if sid:
                method_map[sid] = rec
        result[fn] = method_map
    return result


def _get_field_value(pred: dict, field_name: str) -> str:
    """Extract field value from prediction."""
    pf = pred.get("prediction_fields", {})
    val = pf.get(field_name)
    if isinstance(val, dict):
        return val.get("value", "") or ""
    if isinstance(val, str):
        return val
    return ""


def identify_review_samples(
    audit_records: dict[str, dict[str, dict]],
    predictions: dict[str, dict[str, dict]],
) -> dict[str, list[str]]:
    """Identify sample_ids that need human review, grouped by issue type.

    Returns: {issue_type: [sample_ids]}
    """
    issues: dict[str, set[str]] = {
        "missing_action": set(),
        "missing_actor": set(),
        "no_actor_action_map": set(),
        "action_too_long": set(),
        "action_condition_leak": set(),
        "action_constraint_leak": set(),
        "exception_too_long": set(),
        "constraint_too_long": set(),
        "condition_too_long": set(),
        "bad_json_line": set(),
        "method_disagreement": set(),
    }

    # Check sun_style audit (primary source)
    sun_audit_key = "r15_gdpr50_sun_style_predictions.jsonl"
    sun_audit = audit_records.get(sun_audit_key, {})
    for sid, rec in sun_audit.items():
        for w in rec.get("warnings", []):
            t = w["type"]
            if t == "missing_actor":
                issues["missing_actor"].add(sid)
            elif t == "no_actor_action_map":
                issues["no_actor_action_map"].add(sid)
            elif t == "action_too_long":
                issues["action_too_long"].add(sid)
            elif t == "action_contains_condition_marker":
                issues["action_condition_leak"].add(sid)
            elif t == "action_contains_constraint_marker":
                issues["action_constraint_leak"].add(sid)
            elif t == "exception_too_long":
                issues["exception_too_long"].add(sid)
            elif t == "constraint_too_long":
                issues["constraint_too_long"].add(sid)
            elif t == "condition_too_long":
                issues["condition_too_long"].add(sid)
        for e in rec.get("errors", []):
            if e["type"] == "missing_action":
                issues["missing_action"].add(sid)

    # Also check other methods for additional issues
    for audit_key in audit_records:
        if audit_key == sun_audit_key:
            continue
        for sid, rec in audit_records[audit_key].items():
            for w in rec.get("warnings", []):
                t = w["type"]
                if t == "missing_actor":
                    issues["missing_actor"].add(sid)
                elif t == "action_too_long":
                    issues["action_too_long"].add(sid)
                elif t == "action_contains_condition_marker":
                    issues["action_condition_leak"].add(sid)
                elif t == "exception_too_long":
                    issues["exception_too_long"].add(sid)
                elif t == "constraint_too_long":
                    issues["constraint_too_long"].add(sid)
                elif t == "condition_too_long":
                    issues["condition_too_long"].add(sid)
            for e in rec.get("errors", []):
                if e["type"] == "missing_action":
                    issues["missing_action"].add(sid)

    # Method disagreement: check if predictions differ significantly
    all_sids = set()
    for method_map in predictions.values():
        all_sids.update(method_map.keys())

    for sid in sorted(all_sids):
        method_actions = {}
        for method, method_map in predictions.items():
            pred = method_map.get(sid)
            if pred:
                action = _get_field_value(pred, "action")
                method_actions[method] = action.strip() if action else ""

        # Check if some methods have action and some don't
        has_action = [m for m, a in method_actions.items() if a]
        no_action = [m for m, a in method_actions.items() if not a]
        if has_action and no_action:
            issues["method_disagreement"].add(sid)
            continue

        # Check if actions are very different (simple heuristic)
        actions = [a for a in method_actions.values() if a]
        if len(set(actions)) > 2:  # more than 2 distinct actions
            issues["method_disagreement"].add(sid)

    # sun_plus_winter bad JSON line 38 = sample r15_gdpr50_038
    issues["bad_json_line"].add("r15_gdpr50_038")

    return {k: sorted(v) for k, v in issues.items() if v}


def build_candidate_record(
    sample_id: str,
    source_text: str,
    issue_types: list[str],
    predictions: dict[str, dict[str, dict]],
    audit_records: dict[str, dict[str, dict]],
) -> dict:
    """Build a single candidate review record."""

    # Collect predictions by method
    preds_by_method = {}
    for method in ["sun_style", "spacy_enhanced", "rule_plus_llm", "sun_plus_winter"]:
        pred = predictions.get(method, {}).get(sample_id)
        if pred:
            pf = pred.get("prediction_fields", {})
            preds_by_method[method] = {
                "modality": _get_field_value(pred, "modality"),
                "actor": _get_field_value(pred, "actor"),
                "action": _get_field_value(pred, "action"),
                "condition": _get_field_value(pred, "condition"),
                "constraint": _get_field_value(pred, "constraint"),
                "exception": _get_field_value(pred, "exception"),
            }
        else:
            preds_by_method[method] = None  # e.g., bad JSON line

    # Stage3 compat flags from sun_style audit
    sun_audit_key = "r15_gdpr50_sun_style_predictions.jsonl"
    audit_rec = audit_records.get(sun_audit_key, {}).get(sample_id, {})
    compat_flags = audit_rec.get("structural_flags", {})

    # Build why_needs_review
    why_parts = []
    for issue in issue_types:
        if issue == "missing_action":
            why_parts.append("规则提取未能提取到 action 字段")
        elif issue == "missing_actor":
            why_parts.append("规则提取未能提取到 actor 字段")
        elif issue == "no_actor_action_map":
            why_parts.append("无法生成 actor→action 映射")
        elif issue == "action_too_long":
            why_parts.append("action 超过 200 字符，可能混入了 condition/constraint")
        elif issue == "action_condition_leak":
            why_parts.append("action 中包含 if/when/where 等条件标记，疑似 condition 泄漏")
        elif issue == "action_constraint_leak":
            why_parts.append("action 中包含 within/at least 等约束标记，疑似 constraint 泄漏")
        elif issue == "exception_too_long":
            why_parts.append("exception 字段过长，可能需要拆分")
        elif issue == "constraint_too_long":
            why_parts.append("constraint 字段过长，可能需要拆分")
        elif issue == "condition_too_long":
            why_parts.append("condition 字段过长，可能需要拆分")
        elif issue == "bad_json_line":
            why_parts.append("sun_plus_winter 方法的 JSON 行损坏，无法读取")
        elif issue == "method_disagreement":
            why_parts.append("不同方法对同一字段的提取结果分歧较大")

    return {
        "sample_id": sample_id,
        "source_text": source_text,
        "issue_types": issue_types,
        "why_needs_review": "; ".join(why_parts),
        "predictions_by_method": preds_by_method,
        "current_stage3_compat_flags": compat_flags,
        "suggested_review_fields": {
            "modality": None,
            "actor": None,
            "action": None,
            "condition": None,
            "constraint": None,
            "exception": None,
            "actor_action_map": None,
            "order_relations": None,
            "notes": None,
        },
        "review_status": "pending_human",
        "do_not_auto_score": True,
    }


def build_template_record(candidate: dict) -> dict:
    """Build a gold template record from a candidate (gold fields = null)."""
    return {
        "sample_id": candidate["sample_id"],
        "source_text": candidate["source_text"],
        "reference_predictions": candidate["predictions_by_method"],
        "gold_fields": {
            "modality": None,
            "actor": None,
            "action": None,
            "condition": None,
            "constraint": None,
            "exception": None,
        },
        "gold_sun_record": {
            "actions": [],
            "actors": [],
            "actor_action_map": [],
            "order_relations": [],
        },
        "human_review": {
            "reviewer": None,
            "reviewed_at": None,
            "confidence": None,
            "notes": None,
            "status": "needs_review",
        },
    }


def generate_instructions() -> str:
    """Generate the human review instructions in Chinese."""
    return """# Sun Stage 2 Gold 审核说明

## 一、审核目标

你的任务是为每条 GDPR 法规文本标注 **Sun-compatible rule record**。

这不是润色文本，也不是评判模型好坏。你的标注结果将直接用于 Stage 3 合规性检查。

**核心原则**：以原文为准，不以模型多数投票为准。

---

## 二、字段填写指南

### 1. modality（情态类型）

必选其一：
- `obligation` — 义务（"shall", "must", "is required to"）
- `prohibition` — 禁止（"shall not", "must not", "may not"）
- `permission` — 允许（"may", "is allowed to"）
- `definition` — 定义（"X means...", "X refers to..."）
- `unknown` — 无法判断

### 2. actor（执行者/角色）

填写执行动作的主体，用最短的名词短语：
- ✅ "the controller"
- ✅ "the processor"
- ✅ "a supervisory authority"
- ❌ "the controller shall process the data"（太长，包含了动作）
- ❌ "personal data"（这是数据，不是执行者）

**如果原文没有明确的执行者，留空 null。不要强行推断。**

### 3. action（动作）

填写最简短的规范动作短语（动词 + 宾语），**最多 30 个词**：
- ✅ "notify the supervisory authority"
- ✅ "obtain consent"
- ✅ "keep records"
- ❌ "notify the supervisory authority if there is a breach within 72 hours"（混入了 condition 和 constraint）

**关键**：action 必须适合和 BPMN activity 匹配。如果原文有多个步骤，提取主要动作。

**用动词原形**：用 "notify" 不用 "notifies" 或 "notified"。

### 4. condition（适用条件）

填写规则生效的触发条件：
- ✅ "if there is a personal data breach"
- ✅ "when the data subject requests"
- ✅ "where the controller has reasonable doubts"
- ❌ 留空（如果原文没有条件）

### 5. constraint（约束条件）

填写数量限制、时间限制、范围限制：
- ✅ "within 72 hours"
- ✅ "without undue delay"
- ✅ "at least annually"
- ❌ 留空（如果原文没有约束）

### 6. exception（例外情况）

填写规则不适用的例外：
- ✅ "unless required by Union law"
- ✅ "except where the data is public"
- ❌ 留空（如果原文没有例外）

### 7. actor_action_map（执行者→动作映射）

填写 actor 和 action 的关系：
```json
{"actor": "the controller", "action": "notify the supervisory authority"}
```
如果 actor 或 action 为空，留空数组 `[]`。

### 8. order_relations（顺序关系）

如果原文描述了多个步骤的先后顺序（使用 "then", "after", "before"），填写：
```json
[{"first_action": "assess risk", "second_action": "notify authority", "marker": "then"}]
```
如果没有顺序关系，留空数组 `[]`。

---

## 三、特殊情况处理

### 1. 原文没有明确 actor

不要强行补 actor。在 `notes` 中说明 "inferred" 或 "no explicit actor"。

### 2. 多个方法输出不同

以原文为准。例如：
- sun_style 说 actor 是 "the controller"
- spacy_enhanced 说 actor 是 "the processor"
- 原文写的是 "the controller"
- → 你填 "the controller"

### 3. 原文是定义型条款

例如 "Personal data means any information relating to an identified or identifiable natural person"
- modality = "definition"
- actor = null（定义没有执行者）
- action = null（定义没有动作）
- 在 notes 中说明 "definition clause, no obligation"

### 4. 原文有多个子句

例如 "The controller shall notify the authority and inform the data subject"
- 如果是同一执行者的连续动作，可以写一个主 action
- 如果是不同执行者的不同动作，需要分开标注（但本模板只支持单条标注）

### 5. 不确定时

在 `notes` 中说明不确定的原因和你的判断依据。`confidence` 填 1-5（5 = 非常确定）。

---

## 四、填写流程

1. 打开 `data/development/gold_review/sun_stage2_gold_review_template.jsonl`
2. 每行是一个 JSON 对象，对应一条法规文本
3. 阅读 `source_text`（原文）
4. 参考 `reference_predictions`（各方法的预测结果）
5. 填写 `gold_fields`（你的标注）
6. 填写 `gold_sun_record`（结构化记录）
7. 填写 `human_review`（审核信息）
8. 保存文件

---

## 五、质量检查

填写完成后，运行验证脚本：
```bash
python scripts/validate_legacy_gold_review.py
```

脚本会检查格式是否正确，但不会判断语义对错。

---

## 六、常见错误

| 错误 | 正确做法 |
|------|----------|
| action 太长（>30 词） | 只提取主要动词+宾语 |
| 把 condition 写进 action | condition 单独放 condition 字段 |
| 把 constraint 写进 action | constraint 单独放 constraint 字段 |
| 强行补 actor | 原文没有就留 null |
| 用模型多数投票 | 以原文为准 |
| modality 填错 | 看关键词：shall=obligation, shall not=prohibition, may=permission |
"""


def generate_report(
    candidates: list[dict],
    template: list[dict],
    issues_by_type: dict[str, list[str]],
) -> str:
    """Generate the pack report in Chinese."""
    total_unique = len(candidates)

    lines = [
        "# Sun Stage 2 Gold 审核包报告",
        "",
        f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**工具**: `scripts/build_gold_review_pack.py`（legacy development only）",
        "",
        "---",
        "",
        "## 一、审核包内容",
        "",
        f"| 文件 | 说明 |",
        f"|------|------|",
        f"| `sun_stage2_gold_review_candidates.jsonl` | 候选集（{total_unique} 条，含预测结果和问题标记） |",
        f"| `sun_stage2_gold_review_template.jsonl` | 人工填写模板（{len(template)} 条，gold 字段为空） |",
        f"| `sun_stage2_gold_review_instructions.md` | 审核说明（中文） |",
        "",
        "---",
        "",
        "## 二、需要审核的样本统计",
        "",
        "| 问题类型 | 样本数 | 说明 |",
        "|----------|--------|------|",
    ]

    issue_descriptions = {
        "missing_action": "规则提取未能提取到 action",
        "missing_actor": "规则提取未能提取到 actor",
        "no_actor_action_map": "无法生成 actor→action 映射",
        "action_too_long": "action 超过 200 字符",
        "action_condition_leak": "action 中包含条件标记",
        "action_constraint_leak": "action 中包含约束标记",
        "exception_too_long": "exception 过长",
        "constraint_too_long": "constraint 过长",
        "condition_too_long": "condition 过长",
        "bad_json_line": "sun_plus_winter JSON 损坏",
        "method_disagreement": "不同方法输出分歧大",
    }

    for issue_type, sids in sorted(issues_by_type.items(), key=lambda x: -len(x[1])):
        desc = issue_descriptions.get(issue_type, issue_type)
        lines.append(f"| `{issue_type}` | {len(sids)} | {desc} |")

    lines.extend([
        "",
        f"**总计去重后需要审核的样本**: {total_unique} 条（共 50 条中的 {total_unique} 条）",
        "",
        "---",
        "",
        "## 三、审核优先级建议",
        "",
        "### 高优先级（必须人工判断）",
        "",
        "1. **missing_action** — 规则完全无法提取 action，需要人工从原文判断",
        "2. **missing_actor** — 规则无法识别执行者，需要人工判断",
        "3. **method_disagreement** — 不同方法输出不一致，需要人工以原文为准",
        "",
        "### 中优先级（需要人工确认）",
        "",
        "4. **action_too_long** — action 可能混入了其他字段的内容",
        "5. **action_condition_leak** — action 中的 if/when 可能是 condition",
        "6. **action_constraint_leak** — action 中的 within/at least 可能是 constraint",
        "",
        "### 低优先级（建议检查）",
        "",
        "7. **exception/constraint/condition_too_long** — 字段可能需要拆分或精简",
        "8. **bad_json_line** — JSON 损坏，需要查看原始数据",
        "",
        "---",
        "",
        "## 四、为什么必须人工审核",
        "",
        "1. **语义正确性无法自动判断**：我们只能检查结构完整性（字段是否为空、格式是否正确），",
        "   但无法判断提取结果是否语义正确。",
        "",
        "2. **需要 gold 标注**：只有人工标注的 gold 才能作为评估基准，",
        "   计算 precision/recall/F1 等指标。",
        "",
        "3. **不能伪造 gold**：自动填充 gold 会导致评估结果不可信。",
        "",
        "4. **不能继续自动实验**：在没有 gold 的情况下，无法证明任何方法的语义准确率。",
        "",
        "---",
        "",
        "## 五、下一步",
        "",
        "1. 人工填写 `sun_stage2_gold_review_template.jsonl`",
        "2. 运行 `python scripts/validate_legacy_gold_review.py` 验证旧格式",
        "3. 使用 gold 评估各方法的语义准确率",
        "4. 基于评估结果选择最佳方法或改进方法",
    ])

    return "\n".join(lines)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Build gold review pack")
    parser.add_argument("--max-candidates", type=int, default=100,
                        help="Max candidates to include (default: all)")
    parser.add_argument(
        "--allow-legacy-schema",
        action="store_true",
        help="Acknowledge that this creates development-only, non-span review files",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly replace existing development review-pack files",
    )
    args = parser.parse_args()

    if not args.allow_legacy_schema:
        print(
            "Refusing to build: the legacy review schema lacks phrase spans and "
            "must not be used for formal human annotation."
        )
        return 2

    targets = (_CANDIDATES_OUT, _TEMPLATE_OUT, _INSTRUCTIONS_OUT, _REPORT_OUT)
    existing = [path for path in targets if path.exists()]
    if existing and not args.overwrite:
        print("Refusing to overwrite existing development review-pack files:")
        for path in existing:
            print(f"  - {path}")
        return 3

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Building Sun Stage 2 Gold Review Pack")
    print("=" * 60)

    # Load data
    print("\nLoading source texts...")
    source_texts = load_source_texts()
    print(f"  Loaded {len(source_texts)} source texts")

    print("Loading predictions...")
    predictions = load_predictions_by_method()
    for method, method_map in predictions.items():
        print(f"  {method}: {len(method_map)} records")

    print("Loading audit summary...")
    audit_records = load_audit_records()
    print(f"  Files: {list(audit_records.keys())}")

    # Identify samples needing review
    print("\nIdentifying samples needing review...")
    issues_by_type = identify_review_samples(audit_records, predictions)

    # Collect all unique sample_ids that need review
    all_review_sids = set()
    for sids in issues_by_type.values():
        all_review_sids.update(sids)
    all_review_sids = sorted(all_review_sids)

    print(f"  Total unique samples needing review: {len(all_review_sids)}")
    for issue_type, sids in sorted(issues_by_type.items(), key=lambda x: -len(x[1])):
        print(f"    {issue_type}: {len(sids)}")

    # Apply max_candidates limit
    if args.max_candidates and len(all_review_sids) > args.max_candidates:
        # Prioritize: missing_action > missing_actor > method_disagreement > others
        priority_order = [
            "missing_action", "missing_actor", "no_actor_action_map",
            "method_disagreement", "action_too_long", "action_condition_leak",
            "action_constraint_leak", "exception_too_long", "constraint_too_long",
            "condition_too_long", "bad_json_line",
        ]
        prioritized = []
        seen = set()
        for issue_type in priority_order:
            for sid in issues_by_type.get(issue_type, []):
                if sid not in seen:
                    prioritized.append(sid)
                    seen.add(sid)
        all_review_sids = prioritized[:args.max_candidates]
        print(f"  (Limited to {args.max_candidates} candidates)")

    # Build candidate records
    print("\nBuilding candidate records...")
    candidates = []
    for sid in all_review_sids:
        # Collect issue types for this sample
        sample_issues = []
        for issue_type, sids in issues_by_type.items():
            if sid in sids:
                sample_issues.append(issue_type)

        source_text = source_texts.get(sid, "")
        candidate = build_candidate_record(
            sample_id=sid,
            source_text=source_text,
            issue_types=sample_issues,
            predictions=predictions,
            audit_records=audit_records,
        )
        candidates.append(candidate)

    # Build template records
    print("Building template records...")
    template = [build_template_record(c) for c in candidates]

    # Write outputs
    print("\nWriting outputs...")

    with open(_CANDIDATES_OUT, "w", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"  {_CANDIDATES_OUT.name}: {len(candidates)} records")

    with open(_TEMPLATE_OUT, "w", encoding="utf-8") as f:
        for t in template:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"  {_TEMPLATE_OUT.name}: {len(template)} records")

    instructions = generate_instructions()
    with open(_INSTRUCTIONS_OUT, "w", encoding="utf-8") as f:
        f.write(instructions)
    print(f"  {_INSTRUCTIONS_OUT.name}")

    report = generate_report(candidates, template, issues_by_type)
    with open(_REPORT_OUT, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  {_REPORT_OUT.name}")

    print("\nGold review pack generation complete.")
    print(f"Total candidates: {len(candidates)}")
    print(f"Next step: Human review of {_TEMPLATE_OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
