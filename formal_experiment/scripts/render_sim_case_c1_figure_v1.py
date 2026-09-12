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
import sys
import xml.etree.ElementTree as ET
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

    def raw(self, markup: str) -> None:
        self.parts.append(markup)

    def polyline(self, points, stroke="#17202a", sw=1.5, dash=None,
                 marker=True) -> None:
        if not points:
            return
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        marker_attr = ' marker-end="url(#arrow)"' if marker else ""
        self.parts.append(
            f'<polyline points="{pts}" fill="none" stroke="{stroke}" '
            f'stroke-width="{sw}"{dash_attr}{marker_attr}/>'
        )
        if marker and len(points) >= 2:
            x1, y1 = points[-2]
            x2, y2 = points[-1]
            dx, dy = x2 - x1, y2 - y1
            length = max((dx * dx + dy * dy) ** 0.5, 0.001)
            ux, uy = dx / length, dy / length
            px, py = -uy, ux
            size = 6.0
            bx, by = x2 - ux * size, y2 - uy * size
            self.parts.append(
                f'<polygon points="{x2:.1f},{y2:.1f} '
                f'{bx + px * size * 0.55:.1f},{by + py * size * 0.55:.1f} '
                f'{bx - px * size * 0.55:.1f},{by - py * size * 0.55:.1f}" '
                f'fill="{stroke}" stroke="none"/>'
            )

    def polygon(self, points, fill="#ffffff", stroke="#17202a", sw=1.5,
                dash=None) -> None:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}"{dash_attr}/>'
        )

    def save(self, path: Path, height: float) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height:.0f}" '
            f'viewBox="0 0 {W} {height:.0f}" version="1.1">\n'
            f'<title>SIM 卡入网案例：A/B/C 开发性检测与参考问题对应图</title>\n'
            f'<desc>Read-only render from capsule.json. Machine alarms, evidence-checked reference correspondence, undetermined checks, and repair-control limits are shown separately.</desc>\n'
            + '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#17202a"/></marker></defs>'
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


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _load_bpmn_root():
    model = ROOT / "outputs" / "development" / "sim_case_c1" / "models" / "sim_original_flattened.bpmn"
    if model.exists():
        return ET.fromstring(model.read_bytes())
    # Fallback: reconstruct the same flattened view from the read-only source.
    sys.path[:0] = [str(ROOT / "src")]
    from bpc_hybrid.sim_case_c1 import BPMN
    from bpc_hybrid.sim_case_c1_transforms import flatten_collaboration
    payload, _ = flatten_collaboration(BPMN.read_bytes())
    return ET.fromstring(payload)


def _diagram_geometry(root, node_info: dict) -> tuple[dict, dict, tuple]:
    shapes = {}
    edges = {}
    xs = []
    ys = []
    for elem in root.iter():
        name = _local_name(elem.tag)
        if name == "BPMNShape":
            bpmn_id = elem.get("bpmnElement")
            bounds = None
            for child in elem:
                if _local_name(child.tag) == "Bounds":
                    bounds = {
                        "x": float(child.get("x", 0)),
                        "y": float(child.get("y", 0)),
                        "width": float(child.get("width", 0)),
                        "height": float(child.get("height", 0)),
                    }
            if bpmn_id and bounds:
                shapes[bpmn_id] = bounds
        elif name == "BPMNEdge":
            bpmn_id = elem.get("bpmnElement")
            points = []
            for child in elem:
                if _local_name(child.tag) == "waypoint":
                    points.append((float(child.get("x", 0)), float(child.get("y", 0))))
            if bpmn_id is not None:
                edges[bpmn_id] = points
    for node_id in node_info:
        bounds = shapes.get(node_id)
        if bounds:
            xs.extend([bounds["x"], bounds["x"] + bounds["width"]])
            ys.extend([bounds["y"], bounds["y"] + bounds["height"]])
    for points in edges.values():
        for x, y in points:
            xs.append(x)
            ys.append(y)
    if not xs or not ys:
        xs, ys = [0.0, 1000.0], [0.0, 500.0]
    return shapes, edges, (min(xs), min(ys), max(xs), max(ys))


def _find_node_id(node_info: dict, needle: str) -> str | None:
    lowered = (needle or "").lower()
    for node_id, info in node_info.items():
        if lowered in (info.get("name") or "").lower():
            return node_id
    return None


def _rule_block(cap: dict, rule_id: str, group: str = "C") -> dict:
    for item in cap.get("comparison") or []:
        if item.get("rule_id") == rule_id:
            return (item.get("groups") or {}).get(group) or {}
    return {}


def _rule_check(cap: dict, rule_id: str, lens: str, group: str = "C") -> dict:
    return ((((cap.get("rules") or {}).get(rule_id) or {}).get("sides") or {}).get(group) or {}).get("checks", {}).get(lens) or {}


def _point_along(points: list[tuple[float, float]], fraction: float) -> tuple[float, float]:
    if not points:
        return (0.0, 0.0)
    if len(points) == 1:
        return points[0]
    lengths = []
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        lengths.append(length)
        total += length
    if total <= 0:
        return points[0]
    target = total * fraction
    travelled = 0.0
    for (x1, y1), (x2, y2), length in zip(points, points[1:], lengths):
        if travelled + length >= target:
            ratio = (target - travelled) / max(length, 0.001)
            return (x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio)
        travelled += length
    return points[-1]


def _boxes_intersect(a, b, pad=2.0) -> bool:
    return not (a[0] - pad > b[0] + b[2] or a[0] + a[2] + pad < b[0] or
                a[1] - pad > b[1] + b[3] or a[1] + a[3] + pad < b[1])


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

    # actual BPMN flow view from the read-only flattened model coordinates
    proc = cap.get("process_facts") or {}
    node_info = {}
    for key, kind in (("activities", "activity"), ("events", "event"), ("gateways", "gateway")):
        for item in proc.get(key) or []:
            node_info[item["id"]] = {
                "kind": kind,
                "name": item.get("name") or "",
                "lanes": item.get("lanes") or [],
            }
    bpmn_root = _load_bpmn_root()
    shapes, di_edges, bbox = _diagram_geometry(bpmn_root, node_info)
    minx, miny, maxx, maxy = bbox
    inner_w = W - 2 * M - 40
    inner_h = 660
    scale = min(inner_w / max(maxx - minx, 1), inner_h / max(maxy - miny, 1))
    ox = M + 20
    oy = y + 78

    def tx(value: float) -> float:
        return ox + (value - minx) * scale

    def ty(value: float) -> float:
        return oy + (value - miny) * scale

    diagram_h = inner_h + 190
    svg.rect(M, y, W - 2 * M, diagram_h, rx=10, fill=COLORS["card"], stroke=COLORS["line"])
    svg.text(M + 20, y + 34, "流程模型：实际 BPMN 节点、网关、连线和条件标签（只读坐标）", size=22, weight="bold")
    svg.text(M + 20, y + 58, "节点与连线来自 sim_original_flattened.bpmn 的 BPMNDI；颜色和标注读取本轮 capsule 结果。", size=13, fill=COLORS["muted"])

    # lane/pool backgrounds from DI, without changing BPMN labels
    for shape_id, bounds in shapes.items():
        if shape_id in node_info:
            continue
        x1, y1 = tx(bounds["x"]), ty(bounds["y"])
        w = max((bounds["width"]) * scale, 2)
        h = max((bounds["height"]) * scale, 2)
        if w > 60 and h > 25:
            svg.rect(x1, y1, w, h, rx=7, fill="#f2f6f9", stroke="#dde5ea", sw=1)

    annotations: dict[str, list[dict]] = {}
    def add_annotation(node_id: str | None, lines: list[str], color: str) -> None:
        if node_id:
            annotations.setdefault(node_id, []).append({"lines": lines, "color": color})

    r10_node = _find_node_id(node_info, "Activate SIM card")
    r10_check = _rule_check(cap, "r10", "incorrect_actor")
    r10_assess = _rule_block(cap, "r10")
    if r10_node:
        add_annotation(r10_node, [
            "r10 incorrect_actor={} score={}".format(r10_check.get("status"), r10_check.get("score")),
            "owner={} evidence={}".format(
                ",".join(node_info[r10_node].get("lanes") or []) or "?",
                r10_assess.get("correspondence_judgment")),
        ], COLORS["corresponding"] if r10_assess.get("found_corresponding_problem") else COLORS["missed"])

    r11_check = _rule_check(cap, "r11", "out_of_order")
    r11_assess = _rule_block(cap, "r11")
    consent_node = _find_node_id(node_info, "Ask for consent")
    if consent_node:
        add_annotation(consent_node, [
            "r11 out_of_order={}".format(r11_check.get("status")),
        ], COLORS["missed"])

    # edges first (under nodes)
    r11_node_ids = set()
    for node_id, info in node_info.items():
        name = (info.get("name") or "").lower()
        if any(key in name for key in ("consent", "request personal data", "store data")):
            r11_node_ids.add(node_id)
    occupied_boxes = []
    for node_id, bounds in shapes.items():
        if node_id in node_info and node_id in shapes:
            bx, by = tx(bounds["x"]), ty(bounds["y"])
            bw = max(tx(bounds["x"] + bounds["width"]) - bx, 30)
            bh = max(ty(bounds["y"] + bounds["height"]) - by, 26)
            occupied_boxes.append((bx, by, bw, bh))
    label_boxes = []
    flow_by_id = {flow.get("id"): flow for flow in (proc.get("sequence_flows") or [])}
    for flow_id, flow in flow_by_id.items():
        points = list(di_edges.get(flow_id) or [])
        if not points:
            source = shapes.get(flow.get("source_ref"))
            target = shapes.get(flow.get("target_ref"))
            if source and target:
                points = [
                    (source["x"] + source["width"] / 2, source["y"] + source["height"] / 2),
                    (target["x"] + target["width"] / 2, target["y"] + target["height"] / 2),
                ]
        if not points:
            continue
        transformed = [(tx(x), ty(y)) for x, y in points]
        label = flow.get("name") or ""
        color = COLORS["line"]
        sw = 1.5
        dash = None
        if "debt" in label.lower():
            color = COLORS["limit"]
            sw = 2.8
        elif flow.get("source_ref") in r11_node_ids or flow.get("target_ref") in r11_node_ids:
            color = COLORS["missed"]
            dash = "5 4"
        svg.polyline(transformed, stroke=color, sw=sw, dash=dash)
        if label in {"Requested", "Granted", "Not requested"}:
            label = ""
        if label:
            tw = text_width(label, 11) + 8
            chosen = None
            for fraction in (0.5, 0.32, 0.68, 0.2, 0.8):
                mx, my = _point_along(transformed, fraction)
                candidate_box = (mx - tw / 2, my - 13, tw, 17)
                if any(_boxes_intersect(candidate_box, box) for box in occupied_boxes):
                    continue
                if any(_boxes_intersect(candidate_box, box, pad=1.0) for box in label_boxes):
                    continue
                chosen = (mx, my, candidate_box)
                break
            if chosen is None:
                mx, my = _point_along(transformed, 0.5)
                chosen = (mx, my, (mx - tw / 2, my - 13, tw, 17))
            mx, my, label_box = chosen
            label_boxes.append(label_box)
            svg.rect(mx - tw / 2, my - 13, tw, 17, rx=3, fill="#ffffff",
                     stroke="#dfe6ea", sw=0.6)
            svg.text(mx, my, label, size=11, anchor="middle", fill=color,
                     weight="bold" if "debt" in label.lower() else "normal")

    # nodes
    for node_id, info in node_info.items():
        bounds = shapes.get(node_id)
        if not bounds:
            continue
        x1, y1 = tx(bounds["x"]), ty(bounds["y"])
        w = max(tx(bounds["x"] + bounds["width"]) - x1, 30)
        h = max(ty(bounds["y"] + bounds["height"]) - y1, 26)
        anns = annotations.get(node_id) or []
        stroke = anns[0]["color"] if anns else COLORS["line"]
        sw = 2.4 if anns else 1.2
        fill = {"activity": "#ffffff", "event": "#eafaf1", "gateway": "#fff4e6"}.get(info["kind"], "#ffffff")
        if info["kind"] == "gateway":
            cx, cy = x1 + w / 2, y1 + h / 2
            svg.polygon([(cx, y1), (x1 + w, cy), (cx, y1 + h), (x1, cy)],
                        fill=fill, stroke=stroke, sw=sw)
        else:
            svg.rect(x1, y1, w, h, rx=8 if info["kind"] == "activity" else h / 2,
                     fill=fill, stroke=stroke, sw=sw)
        display_name = (info.get("name") or "").strip()
        lines = wrap_text(display_name, max(w - 8, 24), 10)[:3] if display_name else []
        start_y = y1 + max(9, (h - len(lines) * 12) / 2 + 9)
        for i, line in enumerate(lines):
            svg.text(x1 + w / 2, start_y + i * 12, line, size=10,
                     anchor="middle", fill=COLORS["ink"], weight="bold")
        if info.get("lanes"):
            svg.text(x1 + w / 2, y1 + h - 3, ",".join(info["lanes"])[:28],
                     size=8, anchor="middle", fill=COLORS["muted"])
        yy = y1 + h + 11
        for ann in anns:
            for line in ann["lines"]:
                ax = min(x1, W - M - text_width(line, 9) - 6)
                ax = max(M + 4, ax)
                svg.text(ax, yy, line, size=9, fill=ann["color"], weight="bold")
                yy += 11

    # reserved bottom band: r8 scope note, r9 missing placeholder, r11/r13 evidence notes
    sign_id = _find_node_id(node_info, "Sign contract")
    sign_bounds = shapes.get(sign_id) if sign_id else None
    band_y = y + diagram_h - 82
    xml_counts = proc.get("xml_counts") or {}
    r8_repair = next((row for row in (cap.get("repairs") or []) if row.get("rule_id") == "r8"), {})
    r8_note = ("r8 process scope: timer={}, boundary={}, terminate={}, event_subprocess={}; "
               "repair effective={}, exclusion={}").format(
        xml_counts.get("timer_event_definitions", 0),
        xml_counts.get("boundary_events", 0),
        xml_counts.get("terminate_event_definitions", 0),
        xml_counts.get("event_subprocesses", 0),
        r8_repair.get("in_effective_repair_denominator"),
        r8_repair.get("effective_control_exclusion_reason"))
    r13_check = _rule_check(cap, "r13", "required_condition_not_enforced")
    r11_note = ("r11 order evidence: out_of_order={} reason={}; consent/retrieval nodes are "
                "connected by actual BPMN sequence flows; missing_action is not substituted.").format(
        r11_check.get("status"), r11_check.get("reason"))
    r13_note = ("r13 field attribution: model flow label Debt < 100; required_condition={} "
                "reason={}; condition/constraint fields are empty.").format(
        r13_check.get("status"), r13_check.get("reason"))
    svg.text(M + 20, band_y, r8_note, size=10, fill=COLORS["limit"])
    svg.text(M + 20, band_y + 16, r11_note, size=10, fill=COLORS["missed"])
    svg.text(M + 20, band_y + 32, r13_note, size=10, fill=COLORS["limit"])
    r9_check = _rule_check(cap, "r9", "missing_action")
    ph_x = M + 1040
    ph_y = band_y - 36
    ph_w, ph_h = 260, 52
    svg.rect(ph_x, ph_y, ph_w, ph_h, rx=8, fill="#ffffff",
             stroke=COLORS["missed"], sw=2, dash="7 5")
    svg.text(ph_x + 10, ph_y + 20, "缺失活动（模型中不存在）", size=12,
             fill=COLORS["missed"], weight="bold")
    svg.text(ph_x + 10, ph_y + 38,
             "r9 missing_action={} reason={}".format(r9_check.get("status"), r9_check.get("reason")),
             size=9, fill=COLORS["muted"])
    if sign_bounds:
        target_x = tx(sign_bounds["x"]) + sign_bounds["width"] * scale / 2
        target_y = ty(sign_bounds["y"]) + sign_bounds["height"] * scale / 2
        svg.polyline([(ph_x, ph_y + ph_h / 2), (target_x, target_y)],
                     stroke=COLORS["missed"], sw=1.2, dash="4 4")
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
                f"C_original={ (repair.get('before') or {}).get('status') } -> C_repaired="
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
    svg.text(M + 840, yy, "C_original->C_repaired", size=13, weight="bold")
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
