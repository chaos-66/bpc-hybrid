# -*- coding: utf-8 -*-
"""Render the SIM case annotated result figure from the run capsule.

The renderer is intentionally read-only over
``outputs/development/sim_case_c1/run_v1/capsule.json``.  It never recomputes a
score and never reads the reference file separately, so the figure cannot
diverge from the run report.  The diagram is a simplified lane-grouped view of
the Process Record activities; it is not a replacement for the BPMN source.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPSULE = ROOT / "outputs/development/sim_case_c1/run_v1/capsule.json"
OUT = ROOT / "outputs/reports/sim_case_c1_result_figure.svg"

W = 1800
M = 40
FONT = "Microsoft YaHei, Noto Sans CJK SC, Arial, sans-serif"
COLORS = {
    "bg": "#f5f7fa", "card": "#ffffff", "ink": "#17202a", "muted": "#5d6d7e",
    "header": "#12395b", "header_ink": "#ffffff",
    "alarm": "#b03a2e", "alarm_bg": "#fdecea",
    "corresponding": "#1e8449", "corresponding_bg": "#eafaf1",
    "missed": "#b9770e", "missed_bg": "#fef5e7",
    "undetermined": "#566573", "undetermined_bg": "#eef2f5",
    "limit": "#6c3483", "limit_bg": "#f4ecf7",
    "repair_excluded": "#873600", "repair_excluded_bg": "#fbeee6",
    "line": "#bdc3c7", "lane": "#e8eef3",
}


def esc(text) -> str:
    return html.escape("" if text is None else str(text), quote=False)


def text_width(text: str, size: float) -> float:
    return sum(size if ord(ch) > 0x2E80 else size * 0.56 for ch in text)


def wrap_text(text: str, max_width: float, size: float) -> list[str]:
    text = "" if text is None else str(text)
    if not text:
        return [""]
    tokens = re.findall(r"[A-Za-z0-9_\-./,@:%;=+]+|\s+|.", text)
    lines: list[str] = []
    current = ""
    for token in tokens:
        if token.isspace():
            if current:
                current += " "
            continue
        while text_width(token, size) > max_width:
            room = max(1, int(max_width / (size if ord(token[0]) > 0x2E80 else size * 0.56)))
            lines.append(token[:room])
            token = token[room:]
        if text_width(current + token, size) <= max_width:
            current += token
        else:
            if current.strip():
                lines.append(current.rstrip())
            current = token
    if current.strip():
        lines.append(current.rstrip())
    return lines or [""]


class Svg:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.y = 0

    def rect(self, x, y, w, h, rx=8, fill="#ffffff", stroke="none", sw=1,
             dash=None) -> None:
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dash_attr}/>'
        )

    def text(self, x, y, text, size=16, fill="#17202a", weight="normal",
             anchor="start", italic=False) -> None:
        style = f' font-style="italic"' if italic else ""
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{style}>'
            f'{esc(text)}</text>'
        )

    def paragraph(self, x, y, width, text, size=16, lh=22, fill="#17202a",
                  weight="normal") -> float:
        lines = wrap_text(text, width, size)
        for line in lines:
            self.text(x, y, line, size=size, fill=fill, weight=weight)
            y += lh
        return y

    def save(self, path: Path, height: float) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height:.0f}" '
            f'viewBox="0 0 {W} {height:.0f}" version="1.1">\n'
            f'<title>SIM 卡入网案例：A/B/C 开发性检测与参考问题对应图</title>\n'
            f'<desc>Read-only render from capsule.json. Machine alarms, evidence-checked reference correspondence, undetermined checks, and repair-control limits are shown separately.</desc>\n'
            + "\n".join(self.parts) + "\n</svg>\n"
        )
        path.write_text(payload, encoding="utf-8", newline="\n")


def status_text(checks: dict, name: str) -> str:
    item = (checks or {}).get(name)
    if not item:
        return "—"
    score = item.get("score")
    extra = f" ({score})" if score is not None else ""
    return f"{item.get('status')}{extra}"


def alarm_text(alarms: list[dict]) -> str:
    if not alarms:
        return "无 positive machine alarm"
    return "；".join(f"{a['check']}={a['machine_status']}/{a['score']}" for a in alarms)


def main() -> int:
    cap = json.loads(CAPSULE.read_text(encoding="utf-8"))
    svg = Svg()
    # background
    header_h = 265
    svg.rect(0, 0, W, header_h, rx=0, fill=COLORS["header"])
    svg.text(M, 62, "SIM 卡入网案例：A/B/C 开发性检测与参考问题对应图", size=34,
             fill=COLORS["header_ink"], weight="bold")
    svg.text(M, 96, f"run={cap['run_id']} · claim_scope={cap['claim_scope']} · 同一 capsule 渲染",
             size=16, fill="#d6eaf8")
    y = 126
    y = svg.paragraph(M, y, 1720,
                      "A 组=项目锁定非 LLM 基线 B0 v10a + 冻结 Sun 式三类；B 组=已有真实 LLM Stage 2 预测 + 与 A 同一三类；"
                      "C 组=与 B 相同 Stage 2/三类 + REPAIR-V2 四类扩展。主分母固定为 r8/v2、r9/v2、r10/v2、r11/v2、r13/v2。",
                      size=16, lh=22, fill="#eaf2f8")
    y = svg.paragraph(M, y, 1720,
                      "本图不把论文 Figure 10 的 Violation 标签当作本方法输出；图中所有状态、分数、报警和计数均来自同一 capsule。"
                      "红色=机器实际报警，绿色=有证据对应参考问题，橙色=参考问题未检出/报警未证实，灰色=undetermined，紫色=来源/表示限制。",
                      size=15, lh=21, fill="#d6eaf8")
    y = header_h + 28

    # legend
    legend = [
        ("machine_alarm", "机器报警（原始输出）", "alarm"),
        ("reference_corresponding", "有证据对应参考问题", "corresponding"),
        ("reference_miss", "参考问题未检出或报警未证实", "missed"),
        ("undetermined", "undetermined / 无法判断", "undetermined"),
        ("source_expression_limit", "来源、表达或解析限制", "limit"),
        ("repair_excluded", "修复件无效/部分/不可评价", "repair_excluded"),
    ]
    box_w = 275
    for i, (_, label, key) in enumerate(legend):
        x = M + i * (box_w + 8)
        svg.rect(x, y, box_w, 48, rx=6, fill=COLORS[key + "_bg"], stroke=COLORS[key], sw=2)
        svg.text(x + 12, y + 30, label, size=15, fill=COLORS[key], weight="bold")
    y += 78

    # simplified process diagram, grouped by lane
    proc = cap.get("process_facts") or {}
    activities = proc.get("activities") or []
    lane_order = ["Customer", "Phone company", "Another phone company"]
    grouped: dict[str, list[dict]] = {lane: [] for lane in lane_order}
    for act in activities:
        lanes = act.get("lanes") or ["未分配"]
        grouped.setdefault(lanes[0] if lanes else "未分配", []).append(act)
    for lane in grouped:
        if lane not in lane_order:
            lane_order.append(lane)
    needed = max([len(grouped.get(lane) or []) for lane in lane_order] + [4])
    diagram_h = 120 + needed * 58 + 90
    svg.rect(M, y, W - 2 * M, diagram_h, rx=10, fill=COLORS["card"], stroke=COLORS["line"])
    svg.text(M + 20, y + 34, "流程模型（按泳道分组；非完整 BPMN 布局）", size=22, weight="bold")
    svg.text(M + 20, y + 60, "ID 保留，坐标不重绘；虚线框 = 模型中不存在的活动。", size=14, fill=COLORS["muted"])
    col_w = (W - 2 * M - 80) / 3
    for idx, lane in enumerate(lane_order[:3]):
        x = M + 40 + idx * (col_w + 20)
        svg.rect(x, y + 78, col_w, diagram_h - 108, rx=8, fill=COLORS["lane"], stroke="none")
        svg.text(x + 12, y + 102, lane, size=17, weight="bold")
        yy = y + 128
        for act in grouped.get(lane, []):
            name = act.get("name") or act.get("id") or ""
            fill = "#ffffff"
            stroke = COLORS["line"]
            badge = ""
            if name == "Activate SIM card":
                fill, stroke = COLORS["alarm_bg"], COLORS["corresponding"]
                badge = "r10 incorrect_actor：有证据对应（执行者 Customer）"
            elif name == "Ask for consent":
                fill, stroke = COLORS["missed_bg"], COLORS["missed"]
                badge = "r11 参考问题=顺序错误；out_of_order 未检出"
            svg.rect(x + 10, yy, col_w - 20, 38, rx=6, fill=fill, stroke=stroke, sw=2)
            svg.text(x + 18, yy + 24, name, size=14, weight="bold")
            if badge:
                yy += 42
                yy = svg.paragraph(x + 18, yy, col_w - 36, badge, size=12, lh=15,
                                   fill=COLORS["muted"])
            yy += 18
        if lane == "Phone company":
            svg.rect(x + 10, yy, col_w - 20, 38, rx=6, fill="#ffffff",
                     stroke=COLORS["missed"], sw=2, dash="6 4")
            svg.text(x + 18, yy + 24, "缺失活动（模型中不存在）", size=14,
                     fill=COLORS["missed"], weight="bold")
            svg.text(x + 18, yy + 50, "r9：缺失活动占位符（不是模型节点）",
                     size=12, fill=COLORS["muted"])
    notes_y = y + diagram_h - 44
    svg.text(M + 20, notes_y, "r8：当前模型无 timerEventDefinition / boundaryEvent / terminateEventDefinition；过程级修复见下图，"
                              "但冻结 Stage 1 的 opaque event subprocess 表示不能把计时与终止作用域完整带入结构化检测链。",
             size=13, fill=COLORS["limit"])
    y += diagram_h + 28

    # per-rule cards
    by_rule = {c["rule_id"]: c for c in cap["comparison"]}
    repairs = {r["rule_id"]: r for r in cap["repairs"]}
    for rid in ["r8", "r9", "r10", "r11", "r13"]:
        item = by_rule[rid]
        entry = cap["rules"][rid]
        repair = repairs.get(rid)
        left_lines: list[tuple[str, str, str]] = []
        for group in ("A", "B", "C"):
            checks = (entry["sides"].get(group) or {}).get("checks") or {}
            left_lines.append((
                f"组 {group}",
                f"missing={status_text(checks, 'missing_action')} · actor={status_text(checks, 'incorrect_actor')} · "
                f"order={status_text(checks, 'out_of_order')} · condition={status_text(checks, 'required_condition_not_enforced')} · "
                f"constraint={status_text(checks, 'constraint_violated')}",
                COLORS["ink"],
            ))
        c_assess = item["groups"]["C"]
        right_parts = [
            ("参考问题", item.get("semantic_issue_zh") or "", COLORS["ink"]),
            ("C 机器报警", alarm_text(c_assess.get("machine_alarms") or []), COLORS["alarm"]),
            ("对应评价", f"{c_assess.get('correspondence_judgment')}；有证据对应={c_assess.get('found_corresponding_problem')}",
             COLORS["corresponding"] if c_assess.get("found_corresponding_problem") else COLORS["missed"]),
            ("证据链", " ".join(c_assess.get("evidence_chain_zh") or []), COLORS["muted"]),
        ]
        if repair:
            iv = repair.get("independent_verification") or {}
            right_parts.append((
                "修复对照",
                f"{repair['repair_id']}：语义有效={iv.get('repair_semantics_valid')}，进入检测链="
                f"{iv.get('semantics_entered_detection_chain')}，有效分母={repair.get('in_effective_repair_denominator')}，"
                f"排除={repair.get('effective_control_exclusion_reason') or '—'}；"
                f"B/C before={ (repair.get('before') or {}).get('status') } after="
                f"{(repair.get('after') or {}).get('status')}",
                COLORS["limit"] if not repair.get("in_effective_repair_denominator") else COLORS["corresponding"],
            ))
        # estimate card height
        left_h = sum(26 + 22 * len(wrap_text(txt, 820, 14)) for _, txt, _ in left_lines)
        right_h = 0
        for title, txt, _ in right_parts:
            right_h += 26 + 20 * len(wrap_text(txt, 720, 13))
        card_h = max(180, left_h + 80, right_h + 110)
        svg.rect(M, y, W - 2 * M, card_h, rx=10, fill=COLORS["card"], stroke=COLORS["line"])
        badge_color = COLORS["corresponding"] if c_assess.get("found_corresponding_problem") else COLORS["missed"]
        svg.rect(M, y, W - 2 * M, 44, rx=10, fill=badge_color, stroke="none")
        svg.text(M + 18, y + 30, f"{rid}/v2 · {item.get('reference_judgment')}", size=20,
                 fill="#ffffff", weight="bold")
        ly = y + 70
        for title, txt, color in left_lines:
            svg.text(M + 18, ly, title, size=15, weight="bold", fill=color)
            ly = svg.paragraph(M + 105, ly, 780, txt, size=13, lh=18, fill=COLORS["ink"]) + 8
        ry = y + 66
        for title, txt, color in right_parts:
            svg.text(M + 930, ry, title, size=15, weight="bold", fill=color)
            ry = svg.paragraph(M + 1010, ry, 700, txt, size=13, lh=18, fill=COLORS["ink"]) + 8
        y += card_h + 20

    # counts
    counts_h = 250
    svg.rect(M, y, W - 2 * M, counts_h, rx=10, fill=COLORS["card"], stroke=COLORS["line"])
    svg.text(M + 20, y + 34, "逐检测项计数（不是七类总 F1）", size=22, weight="bold")
    yy = y + 66
    headers = ["组", "checks", "violation", "satisfied", "undetermined", "not_applicable",
               "机器状态计数", "参考问题有证据对应", "报警未证实", "无 positive alarm"]
    xs = [M + 25, M + 105, M + 215, M + 335, M + 465, M + 625, M + 790, M + 1170, M + 1360, M + 1550]
    for x, h in zip(xs, headers):
        svg.text(x, yy, h, size=14, weight="bold", fill=COLORS["header"])
    yy += 26
    for group in ("A", "B", "C"):
        block = cap["summary"][group]
        c = block["status_counts"]
        ref = cap["reference_assessment_summary"][group]
        vals = [group, block["checks"], c.get("violation", 0), c.get("satisfied", 0),
                c.get("undetermined", 0), c.get("not_applicable", 0),
                ", ".join(f"{key}={value}" for key, value in
                         (block.get("machine_status_counts") or {}).items()),
                ref.get("found_with_reference_evidence", 0),
                ref.get("machine_alarm_but_reference_correspondence_unverified", 0),
                ref.get("no_positive_machine_alarm", 0)]
        for x, val in zip(xs, vals):
            svg.text(x, yy, str(val), size=14)
        yy += 26
    svg.text(M + 25, y + counts_h - 24,
             "counts = 评价状态（empty_rule_action→undetermined）；机器状态计数保留 not_applicable 等原始公式结果；"
             "参考问题对应为证据核对结果，不是检测器类型投票。",
             size=13, fill=COLORS["muted"])
    y += counts_h + 24

    # repair table
    repairs_list = cap["repairs"]
    rep_h = 130 + len(repairs_list) * 70
    svg.rect(M, y, W - 2 * M, rep_h, rx=10, fill=COLORS["card"], stroke=COLORS["line"])
    svg.text(M + 20, y + 34, "修复对照：有效、部分/无效与不可评价", size=22, weight="bold")
    yy = y + 66
    svg.text(M + 25, yy, "修复件", size=14, weight="bold")
    svg.text(M + 420, yy, "语义有效", size=14, weight="bold")
    svg.text(M + 540, yy, "进入检测链", size=14, weight="bold")
    svg.text(M + 700, yy, "有效分母", size=14, weight="bold")
    svg.text(M + 840, yy, "B→C", size=14, weight="bold")
    svg.text(M + 1090, yy, "排除/限制原因", size=14, weight="bold")
    yy += 26
    for row in repairs_list:
        iv = row.get("independent_verification") or {}
        before = row.get("before") or {}
        after = row.get("after") or {}
        svg.text(M + 25, yy, row["repair_id"], size=13)
        svg.text(M + 420, yy, str(iv.get("repair_semantics_valid")), size=13)
        svg.text(M + 540, yy, str(iv.get("semantics_entered_detection_chain")), size=13)
        svg.text(M + 700, yy, str(row.get("in_effective_repair_denominator")), size=13)
        svg.text(M + 840, yy, f"{before.get('status')} → {after.get('status')}", size=13)
        svg.text(M + 1090, yy, row.get("effective_control_exclusion_reason") or "—", size=12,
                 fill=COLORS["muted"])
        if row.get("legacy_partial_control"):
            yy += 22
            svg.text(M + 1090, yy, "legacy task-scoped control: invalid scope, excluded",
                     size=12, fill=COLORS["repair_excluded"])
        yy += 48
    y += rep_h + 24

    footer = [
        "边界：开发性单案例；不是正式 Gold，不是作者原始实验复现，不是企业验证；不合成七类总 F1。",
        "B 组复用已有 repeat-01 真实 LLM 预测；重复运行只作稳定性证据，不作为新增独立样本。",
        "原始 BPMN、需求、Gold、原始预测未修改；参考判断只在评价阶段读取。",
    ]
    foot_h = 40 + len(footer) * 26
    svg.rect(M, y, W - 2 * M, foot_h, rx=10, fill="#eef2f5", stroke=COLORS["line"])
    yy = y + 34
    for line in footer:
        svg.text(M + 20, yy, line, size=14, fill=COLORS["muted"])
        yy += 26
    y += foot_h + 30

    svg.save(OUT, y)
    print(f"wrote {OUT} height={y:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
