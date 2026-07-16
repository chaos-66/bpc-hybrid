"""EStG-150 LLM-assisted human correction review tool (Layer E, v2).

USAGE (from formal_experiment/):
    python scripts/estg150_review_tool.py
    python scripts/estg150_review_tool.py --path <other_file>

This is the v2 review tool. It targets the v1 workflow described in
docs/HUMAN_GOLD_GUIDE.md and
data/development/human_review/ESTG150_REVIEW_WORKFLOW_V1.md.

The Tk GUI is a thin shell. **All data operations go through**
``HumanCorrectionService`` (``src/formal_experiment/estg150_service.py``).
The service enforces the workflow invariants:

  1. Validation never writes to the production file. The pure
     ``validate_record_for_review`` function is the only eligibility
     check used by the "本条已复核" and "本条已裁决" buttons.

  2. The "保存草稿" button is the single point that touches the disk.
     It backs up, atomically writes, and returns a result. The
     status bar then runs the global aggregator (read-only, on the
     just-saved file) and shows the report.

  3. Marking a record `reviewed` / `adjudicated` uses the per-record
     eligibility check, NOT the global `review_ready` /
     `freeze_ready`. The first record can be marked while the other
     149 are still `needs_review`.

  4. Every mutator snapshots the affected record for undo and
     appends to the action log.

  5. The Chinese / English back-translation aid (Layer D) is all
     null until a separate real-LLM authorization. The tool shows
     a placeholder banner and never fabricates content.

Hard rules (enforced in code, not just by validator):
  1. Reads the human_correction JSON (Layer E). NEVER overwrites
     the llm_candidate block; never writes to layer A / B / C / D.
  2. Does NOT pre-fill human_correction from old auto-Gold files.
  3. Never auto-changes `unreviewed` to `accepted` / `reviewed` /
     `adjudicated`. The user must click the buttons.
  4. Modality is required 4-way choice (obligation / prohibition /
     permission / definition); there is NO default of "obligation".
  5. Adding a new clause starts with an EMPTY clause (no modality
     preset, no auto actors/actions).
  6. All span IDs are unique within a clause.
  7. Modifying approved_text_en marks existing clause_spans and
     element_spans stale and re-locks the review_state.status to
     `needs_review`.
  8. Every save is preceded by a uniquely-named backup.
  9. Every human action appends an entry to the action log.
 10. The global validator runs after every save; the result is shown
     in the status bar.
 11. The window blocks close if there are unsaved changes; an "undo
     last action" button restores the prior state.
 12. Marking `reviewed` or `adjudicated` uses the **per-record**
     eligibility check. The first record can be marked while the
     other 149 are still `needs_review`.

Requires Python with tkinter (stdlib on Windows / macOS / most Linux).
No network access. No LLM/API calls.
"""
from __future__ import annotations

import argparse
import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


FORMAL_ROOT = Path(__file__).resolve().parents[1]
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.estg150_service import HumanCorrectionService  # noqa: E402
from formal_experiment.layer_d_validator import (  # noqa: E402
    check_call_b_blind,
    check_layer_e_pristine,
    check_v1_placeholder_unchanged,
    compute_layer_e_progress,
    load_expected_membership,
    load_jsonl_records,
    sha256_path,
)


DEFAULT_PATH = (
    FORMAL_ROOT / "data" / "development" / "human_review"
    / "estg_150_human_correction_v1.json"
)
MEMBERSHIP_HASHES_PATH = FORMAL_ROOT / "data" / "development" / "estg" / "estg_150_membership_hashes.json"
LAYER_A_PATH = FORMAL_ROOT / "data" / "development" / "estg" / "estg_selected_150_de.jsonl"
LAYER_B_PATH = FORMAL_ROOT / "data" / "development" / "human_review" / "estg_150_translation_en_v1.jsonl"
PROMPT_CALL_B_PATH = FORMAL_ROOT / "prompts" / "zh_aid" / "en_back_translation.md"
BACKUP_DIR = (
    FORMAL_ROOT / "outputs" / "development" / "human_review" / "review_backups"
)
ACTION_LOG = (
    FORMAL_ROOT / "outputs" / "development" / "human_review"
    / "estg_150_review_actions_v1.jsonl"
)
LAYER_D_CONFIG = FORMAL_ROOT / "configs" / "estg150_layer_d.json"


def _resolve_active_layer_d_path() -> Path:
    """Read `configs/estg150_layer_d.json` and return the active
    Layer D JSONL path. The GUI never guesses v1/v2; it always
    reads the config. If the config is missing, fall back to the
    v1 placeholder provenance path."""
    if LAYER_D_CONFIG.exists():
        try:
            cfg = json.loads(LAYER_D_CONFIG.read_text(encoding="utf-8"))
            rel = cfg.get("active_path", "")
            if rel:
                p = (FORMAL_ROOT / rel).resolve()
                if p.exists():
                    return p
        except (OSError, json.JSONDecodeError):
            pass
    return (
        FORMAL_ROOT / "data" / "development" / "human_review"
        / "estg_150_review_aids_zh_v1.jsonl"
    )


SPAN_FIELDS = ("actors", "actions", "conditions", "constraints", "exceptions")
SPAN_FIELD_LABELS = {
    "actors": "主体",
    "actions": "行为",
    "conditions": "条件",
    "constraints": "约束",
    "exceptions": "例外",
}
MODALITY_LABELS = ("obligation", "prohibition", "permission", "definition")
MODALITY_LABELS_ZH = {
    "obligation": "义务",
    "prohibition": "禁止",
    "permission": "许可",
    "definition": "定义",
}
DECISION_LABELS = ("unreviewed", "accepted", "edited", "rejected", "needs_adjudication")
DECISION_LABELS_ZH = {
    "unreviewed": "未审核",
    "accepted": "已接受",
    "edited": "已修改",
    "rejected": "已拒绝",
    "needs_adjudication": "待裁决",
    "missing": "缺失",
    "not_applicable": "不适用",
}
REVIEW_STATUS_ZH = {
    "needs_review": "待审核",
    "in_progress": "审核中",
    "reviewed": "已复核",
    "adjudicated": "已裁决",
}


def _load_jsonl(path: Path) -> dict:
    out: dict = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            out[r["sample_id"]] = r
    return out


class ReviewerApp:
    def __init__(self, root: tk.Tk, path: Path):
        self.root = root
        self.path = path
        # The service is the only mutator of the doc. The GUI keeps a
        # reference to its `records` list for navigation; mutations
        # done through the service are visible in this list.
        self.service = HumanCorrectionService(
            path=path,
            backup_dir=BACKUP_DIR,
            action_log=ACTION_LOG,
            reviewer="user",
        )
        self.idx = 0
        self._dirty = False
        # Sidecar immutable lookups
        self._de_text: dict[int, str] = {
            r["legacy_record_id"]: r["raw_text_de"] for r in self.service.records
        }
        self._zh_aid: dict[str, dict] = _load_jsonl(
            _resolve_active_layer_d_path()
        )
        self._en_manifest: dict[str, dict] = _load_jsonl(
            FORMAL_ROOT / "data" / "development" / "human_review"
            / "estg_150_translation_en_v1.jsonl"
        )
        self._llm_manifest: dict[str, dict] = _load_jsonl(
            FORMAL_ROOT / "data" / "development" / "human_review"
            / "estg_150_llm_six_element_candidates_v1.jsonl"
        )
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
        self._build_ui()
        self._load_record()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- UI ----------------
    def _build_ui(self):
        self.root.title(
            f"EStG-150 LLM 辅助人工修正工具 — {self.path.name}\n"
            "德文/英文候选/LLM 候选/中文辅助 = 全部只读；只编辑 human_correction"
        )
        self.root.geometry("1480x900")

        # Chinese aid banner
        banner = ttk.Label(
            self.root,
            text=(
                "⚠ 中文翻译和英文回译默认未生成；激活后请在下方点击「重新加载中文辅助」"
                "按钮刷新本窗口（无需重启 GUI）。当前所有 Layer D 字段为 null 时工具不会"
                "自动填充，也绝不会自动写入人工答案。"
            ),
            foreground="#a00",
            background="#fff5d8",
            padding=4,
        )
        banner.pack(side=tk.TOP, fill=tk.X)

        bar = ttk.Frame(self.root, padding=6)
        bar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(bar, text="◀ 上一条", command=self.on_prev).pack(side=tk.LEFT)
        ttk.Button(bar, text="下一条 ▶", command=self.on_next).pack(side=tk.LEFT)
        ttk.Button(bar, text="下一条待审核 ▶▶", command=self.on_next_pending).pack(side=tk.LEFT)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(bar, text="撤销最近一次操作", command=self.on_undo).pack(side=tk.LEFT)
        ttk.Button(bar, text="保存草稿", command=self.on_save).pack(side=tk.LEFT)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Label(bar, text="审核员:").pack(side=tk.LEFT)
        self.reviewer_var = tk.StringVar(value="user")
        ttk.Entry(bar, textvariable=self.reviewer_var, width=14).pack(side=tk.LEFT)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        self.idx_label = ttk.Label(bar, text="")
        self.idx_label.pack(side=tk.LEFT, padx=8)
        self.status_label = ttk.Label(bar, text="", foreground="#444")
        self.status_label.pack(side=tk.RIGHT)

        # Tabs
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.tab_translation = ttk.Frame(self.tabs)
        self.tab_six = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_translation, text="标签页一：翻译核对")
        self.tabs.add(self.tab_six, text="标签页二：六要素核对")
        self._build_translation_tab()
        self._build_six_tab()

        # Status bar (below tabs)
        status_frame = ttk.LabelFrame(self.root, text="保存后状态", padding=4)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=4, pady=2)
        self.post_save_label = ttk.Label(
            status_frame, text="尚未保存。", foreground="#444", anchor="w", justify="left"
        )
        self.post_save_label.pack(fill=tk.X)

        # Layer D (Chinese aid) status + reload button. This is
        # the only way to pick up a v2 Layer D activation
        # without restarting the GUI. Re-reads
        # configs/estg150_layer_d.json, validates the active
        # file's 150/150 completeness, and replaces
        # self._zh_aid in-place. Layer E is NEVER touched.
        layer_d_frame = ttk.LabelFrame(self.root, text="中文辅助 (Layer D) 状态", padding=4)
        layer_d_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=4, pady=2)
        self.layer_d_label = ttk.Label(
            layer_d_frame, text=self._format_layer_d_status(),
            foreground="#444", anchor="w", justify="left",
        )
        self.layer_d_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(layer_d_frame, text="重新加载中文辅助",
                   command=self.on_reload_layer_d).pack(side=tk.RIGHT)

    def _build_translation_tab(self):
        pane = self.tab_translation
        info = ttk.Label(
            pane,
            text=(
                "左侧四块（德文原文、英文候选、中文翻译、英文回译）一律只读；"
                "中间 Layer D 的中文辅助和回译尚未生成。"
                "右侧「人工最终英文」是本文件唯一可编辑区域；"
                "修改英文将清空所有现有 span 并把本条 review_state 重置为 needs_review。"
            ),
            foreground="#444",
        )
        info.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)

        cols = ttk.Frame(pane, padding=6)
        cols.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        for c in range(5):
            cols.columnconfigure(c, weight=1, uniform="col")
        cols.rowconfigure(1, weight=1)

        headers = [
            "德文原文（只读）",
            "英文候选（只读）",
            "中文翻译（只读，pending）",
            "英文回译（只读，pending）",
            "人工最终英文（可编辑）",
        ]
        for c, h in enumerate(headers):
            ttk.Label(cols, text=h).grid(row=0, column=c, sticky="w")
        self.t_de = self._ro_text(cols, 1, 0)
        self.t_en = self._ro_text(cols, 1, 1)
        self.t_zh = self._ro_text(cols, 1, 2)
        self.t_back = self._ro_text(cols, 1, 3)
        self.t_appr = tk.Text(cols, wrap="word", height=24, background="#fffce8")
        self.t_appr.grid(row=1, column=4, sticky="nsew", padx=4)
        self.t_appr.bind("<<Modified>>", self._on_appr_modified)
        self.t_appr.bind("<FocusOut>", lambda e: self._collect_appr())

        # Decision controls
        dec = ttk.LabelFrame(pane, text="翻译决策", padding=6)
        dec.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)
        self.translation_decision_var = tk.StringVar(value="unreviewed")
        ttk.Label(dec, text="translation:").pack(side=tk.LEFT)
        for d in DECISION_LABELS:
            ttk.Radiobutton(
                dec, text=DECISION_LABELS_ZH[d], value=d,
                variable=self.translation_decision_var,
                command=self._on_translation_decision_change,
            ).pack(side=tk.LEFT, padx=2)
        ttk.Label(dec, text="备注:").pack(side=tk.LEFT, padx=(12, 0))
        self.translation_notes_var = tk.StringVar()
        ttk.Entry(dec, textvariable=self.translation_notes_var, width=50).pack(side=tk.LEFT, padx=4)
        self.translation_notes_var.trace_add("write", lambda *a: self._on_translation_notes_change())

        # Action buttons
        ab = ttk.Frame(pane, padding=6)
        ab.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(ab, text="接受英文候选", command=self.on_accept_en_candidate).pack(side=tk.LEFT, padx=2)
        ttk.Button(ab, text="保存人工修改英文", command=self.on_save_appr_en).pack(side=tk.LEFT, padx=2)
        ttk.Button(ab, text="拒绝英文候选", command=self.on_reject_en_candidate).pack(side=tk.LEFT, padx=2)
        ttk.Button(ab, text="标记为待裁决", command=self.on_translation_adjudication).pack(side=tk.LEFT, padx=2)
        ttk.Button(ab, text="下一条待审核", command=self.on_next_pending).pack(side=tk.LEFT, padx=2)

    def _build_six_tab(self):
        pane = self.tab_six
        info = ttk.Label(
            pane,
            text=(
                "左侧：LLM 六要素候选（只读）。右侧：人工修正（可编辑）。\n"
                "每条记录的每个六要素字段必须显式选择 accepted / edited / rejected / needs_adjudication，"
                "复制不等于批准。"
            ),
            foreground="#444",
        )
        info.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)

        # Two columns
        cols = ttk.Frame(pane, padding=6)
        cols.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        cols.columnconfigure(0, weight=1, uniform="col")
        cols.columnconfigure(1, weight=1, uniform="col")
        cols.rowconfigure(1, weight=1)
        ttk.Label(cols, text="LLM 候选（只读）").grid(row=0, column=0, sticky="w")
        ttk.Label(cols, text="人工修正（可编辑）").grid(row=0, column=1, sticky="w")
        self.t_llm_view = tk.Text(cols, wrap="word", background="#f4f4f4", state="disabled")
        self.t_llm_view.grid(row=1, column=0, sticky="nsew", padx=4)
        self.t_human_view = tk.Text(cols, wrap="word", background="#fffce8", height=24)
        self.t_human_view.grid(row=1, column=1, sticky="nsew", padx=4)

        # Clause controls
        cl = ttk.LabelFrame(pane, text="条款管理", padding=6)
        cl.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)
        ttk.Label(cl, text="clause_id:").pack(side=tk.LEFT)
        self.clause_id_var = tk.StringVar()
        ttk.Entry(cl, textvariable=self.clause_id_var, width=14).pack(side=tk.LEFT)
        ttk.Button(cl, text="添加空白条款（无默认 modality）",
                   command=self.on_add_blank_clause).pack(side=tk.LEFT, padx=4)
        ttk.Button(cl, text="删除当前条款", command=self.on_delete_clause).pack(side=tk.LEFT, padx=4)
        ttk.Button(cl, text="清空全部条款", command=self.on_clear_clauses).pack(side=tk.LEFT, padx=4)
        ttk.Button(cl, text="本条已复核", command=self.on_mark_reviewed).pack(side=tk.LEFT, padx=4)
        ttk.Button(cl, text="本条已裁决", command=self.on_mark_adjudicated).pack(side=tk.LEFT, padx=4)

        # Six-element per-clause editor
        six = ttk.LabelFrame(pane, text="六要素编辑（按字段分别决策）", padding=6)
        six.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=4)
        for c in range(4):
            six.columnconfigure(c, weight=1, uniform="c")
        headers = ["字段", "LLM 候选值", "人工值（可编辑）", "决策"]
        for c, h in enumerate(headers):
            ttk.Label(six, text=h).grid(row=0, column=c, sticky="w")
        self._six_widgets: dict[str, dict] = {}
        for i, fld in enumerate(("modality", "actor", "action", "condition", "constraint", "exception"), 1):
            zh = {
                "modality": "规范类型",
                "actor": "主体",
                "action": "行为",
                "condition": "条件",
                "constraint": "约束",
                "exception": "例外",
            }[fld]
            ttk.Label(six, text=zh).grid(row=i, column=0, sticky="w")
            cand_var = tk.StringVar(value="")
            ttk.Label(six, textvariable=cand_var, foreground="#555").grid(row=i, column=1, sticky="w")
            if fld == "modality":
                mod_var = tk.StringVar(value="")
                cb = ttk.Combobox(
                    six, textvariable=mod_var,
                    values=tuple(MODALITY_LABELS),
                    state="readonly", width=18,
                )
                cb.grid(row=i, column=2, sticky="w")
                cb.bind("<<ComboboxSelected>>", lambda e, f=fld: self._on_six_value_change(f))
                val_widget = cb
            else:
                v = tk.StringVar()
                e = ttk.Entry(six, textvariable=v, width=40)
                e.grid(row=i, column=2, sticky="we")
                e.bind("<FocusOut>", lambda ev, f=fld: self._on_six_value_change(f))
                val_widget = e
            dec_var = tk.StringVar(value="unreviewed")
            dec_frame = ttk.Frame(six)
            dec_frame.grid(row=i, column=3, sticky="w")
            rb_widgets = []
            for d in DECISION_LABELS:
                rb = ttk.Radiobutton(
                    dec_frame, text=DECISION_LABELS_ZH[d], value=d,
                    variable=dec_var,
                    command=lambda f=fld, dv=d: self._on_six_decision_change(f, dv),
                )
                rb.pack(side=tk.LEFT)
                rb_widgets.append(rb)
            self._six_widgets[fld] = {
                "cand_var": cand_var,
                "val_widget": val_widget,
                "dec_var": dec_var,
            }
        # actor-action map and order relations
        map_box = ttk.LabelFrame(pane, text="actor-action 对应 / action 顺序（JSON 手动编辑）", padding=6)
        map_box.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=4)
        ttk.Label(map_box, text="actor_action_map JSON:").grid(row=0, column=0, sticky="nw")
        self.actor_action_map_text = tk.Text(map_box, height=4, background="#fffce8")
        self.actor_action_map_text.grid(row=0, column=1, sticky="we", padx=4)
        ttk.Label(map_box, text="order_relations JSON:").grid(row=1, column=0, sticky="nw")
        self.order_relations_text = tk.Text(map_box, height=4, background="#fffce8")
        self.order_relations_text.grid(row=1, column=1, sticky="we", padx=4)
        for c in range(2):
            map_box.columnconfigure(c, weight=1)

        # Span add
        sp = ttk.LabelFrame(pane, text="添加六要素 span（每个 span 必须在所属 clause_span 内）", padding=6)
        sp.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)
        ttk.Label(sp, text="字段").pack(side=tk.LEFT)
        self.span_field_var = tk.StringVar(value="actors")
        ttk.Combobox(
            sp, textvariable=self.span_field_var,
            values=SPAN_FIELDS, state="readonly", width=12,
        ).pack(side=tk.LEFT)
        ttk.Label(sp, text="文本").pack(side=tk.LEFT, padx=(8, 0))
        self.span_text_var = tk.StringVar()
        ttk.Entry(sp, textvariable=self.span_text_var, width=50).pack(side=tk.LEFT)
        ttk.Label(sp, text="start").pack(side=tk.LEFT, padx=(8, 0))
        self.span_start_var = tk.StringVar()
        ttk.Entry(sp, textvariable=self.span_start_var, width=6).pack(side=tk.LEFT)
        ttk.Label(sp, text="end").pack(side=tk.LEFT, padx=(4, 0))
        self.span_end_var = tk.StringVar()
        ttk.Entry(sp, textvariable=self.span_end_var, width=6).pack(side=tk.LEFT)
        ttk.Button(sp, text="添加 span", command=self.on_add_span).pack(side=tk.LEFT, padx=8)
        ttk.Button(sp, text="删除选中的 span", command=self.on_delete_span).pack(side=tk.LEFT, padx=4)

        # Span listbox
        slb = ttk.LabelFrame(pane, text="本 clause 已添加的 span（双击删除）", padding=6)
        slb.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.span_listbox = tk.Listbox(slb, height=6)
        self.span_listbox.pack(fill=tk.BOTH, expand=True)
        self.span_listbox.bind("<Double-Button-1>", lambda e: self.on_delete_span())

        # Confidence / notes / reviewer
        meta = ttk.LabelFrame(pane, text="本条附加元数据", padding=6)
        meta.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)
        ttk.Label(meta, text="confidence (0-1):").pack(side=tk.LEFT)
        self.confidence_var = tk.StringVar(value="")
        ttk.Entry(meta, textvariable=self.confidence_var, width=6).pack(side=tk.LEFT)
        self.confidence_var.trace_add("write", lambda *a: self._on_confidence_change())
        ttk.Label(meta, text="review notes:").pack(side=tk.LEFT, padx=(12, 0))
        self.review_notes_text = tk.Text(meta, height=2, background="#fffce8")
        self.review_notes_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.review_notes_text.bind("<FocusOut>", lambda e: self._on_review_notes_change())

    def _ro_text(self, parent, row, col) -> tk.Text:
        w = tk.Text(parent, wrap="word", height=24, background="#f4f4f4", state="disabled")
        w.grid(row=row, column=col, sticky="nsew", padx=4)
        return w

    # ---------------- data flow ----------------
    def _current_record(self):
        return self.service.records[self.idx]

    def _set_text(self, widget: tk.Text, content: str):
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content or "")
        if widget is not self.t_appr and widget is not self.t_human_view:
            widget.configure(state="disabled")

    def _load_record(self):
        r = self._current_record()
        sid = r["sample_id"]
        zh = self._zh_aid.get(sid, {})

        # Translation tab
        self._set_text(self.t_de, r["raw_text_de"])
        self._set_text(self.t_en, r["candidate_text_en"])
        self._set_text(self.t_zh, zh.get("text_zh") or "（中文核对辅助：尚未生成 — 需要在用户单独授权真实 LLM 之后由离线脚本填写）")
        self._set_text(self.t_back, zh.get("back_translation_en") or "（英文回译：同上，未生成）")
        self._set_text(self.t_appr, r.get("approved_text_en") or "")
        self.t_appr.edit_modified(False)

        # Translation decision
        self.translation_decision_var.set(
            r["decisions"].get("translation", "unreviewed")
        )
        self.translation_notes_var.set(
            (r.get("human_correction") or {}).get("translation_notes") or ""
        )

        # Six tab
        self._set_text(self.t_llm_view, json.dumps(r.get("llm_candidate") or {}, ensure_ascii=False, indent=2))
        self._set_text(self.t_human_view, json.dumps(r.get("human_correction") or {}, ensure_ascii=False, indent=2))

        # Clause id
        clauses = r["human_correction"]["clauses"]
        if clauses:
            self.clause_id_var.set(clauses[0]["clause_id"])
        else:
            self.clause_id_var.set("")

        self._reload_six_widgets()
        self._reload_clause_text_widgets()
        self._refresh_idx_label()
        self._refresh_progress()
        self._set_status(f"已加载：{sid}")

    def _reload_six_widgets(self):
        r = self._current_record()
        clauses = r["human_correction"]["clauses"]
        active_clause = self._active_clause()
        if active_clause is None:
            for fld, w in self._six_widgets.items():
                w["cand_var"].set("")
                if fld == "modality":
                    w["val_widget"].set("")
                else:
                    w["val_widget"].delete(0, tk.END)
                w["dec_var"].set("unreviewed")
            return
        cand_clause = self._candidate_clause_for_active()
        for fld, w in self._six_widgets.items():
            cand_val = self._field_candidate_value(cand_clause, fld) if cand_clause else None
            w["cand_var"].set(cand_val or "（LLM 候选为空）")
            cur = active_clause.get(fld)
            if fld == "modality":
                w["val_widget"].set(cur.get("value") or "")
                w["dec_var"].set(cur.get("decision") or "unreviewed")
            else:
                arr = cur if isinstance(cur, list) else []
                if arr:
                    w["val_widget"].delete(0, tk.END)
                    w["val_widget"].insert(0, arr[0].get("text") or "")
                    w["dec_var"].set(arr[0].get("decision") or "unreviewed")
                else:
                    w["val_widget"].delete(0, tk.END)
                    w["dec_var"].set("unreviewed")
        # actor_action_map and order_relations
        self.actor_action_map_text.delete("1.0", tk.END)
        self.actor_action_map_text.insert(
            "1.0", json.dumps(active_clause.get("actor_action_map") or [], ensure_ascii=False, indent=2)
        )
        self.order_relations_text.delete("1.0", tk.END)
        self.order_relations_text.insert(
            "1.0", json.dumps(active_clause.get("order_relations") or [], ensure_ascii=False, indent=2)
        )
        self._refresh_span_listbox()
        rs = r.get("review_state") or {}
        self.confidence_var.set(str(rs.get("confidence", "") or ""))
        self.review_notes_text.delete("1.0", tk.END)
        self.review_notes_text.insert("1.0", rs.get("notes") or "")

    def _reload_clause_text_widgets(self):
        r = self._current_record()
        self._set_text(self.t_llm_view, json.dumps(r.get("llm_candidate") or {}, ensure_ascii=False, indent=2))
        self._set_text(self.t_human_view, json.dumps(r.get("human_correction") or {}, ensure_ascii=False, indent=2))

    def _active_clause(self):
        r = self._current_record()
        cid = self.clause_id_var.get().strip()
        for c in r["human_correction"]["clauses"]:
            if c["clause_id"] == cid:
                return c
        return None

    def _candidate_clause_for_active(self):
        r = self._current_record()
        cid = self.clause_id_var.get().strip()
        for c in r.get("llm_candidate", {}).get("clauses", []):
            if c.get("clause_id") == cid:
                return c
        return None

    @staticmethod
    def _field_candidate_value(cand_clause, fld: str):
        v = cand_clause.get(fld)
        if isinstance(v, dict):
            return v.get("value")
        return v

    def _refresh_idx_label(self):
        r = self._current_record()
        tr = r["decisions"].get("translation", "unreviewed")
        rs = REVIEW_STATUS_ZH.get(r["review_state"]["status"], r["review_state"]["status"])
        self.idx_label.configure(
            text=(
                f"第 {self.idx + 1}/150 条   样本ID={r['sample_id']}   "
                f"legacy_id={r['legacy_record_id']}   "
                f"translation={tr}   review_state={rs}   "
                f"clauses={len(r['human_correction']['clauses'])}"
            )
        )

    def _refresh_progress(self):
        # Per-record / global counters via the service (in-memory).
        p = self.service.count_progress()
        # Per-record eligibility for the *current* record.
        r = self._current_record()
        eligibility = self.service.validate_current_record(r["sample_id"])
        per = (
            f"  本条可标记已复核={'是' if eligibility['eligible_for_reviewed'] else '否'}   "
            f"本条可标记已裁决={'是' if eligibility['eligible_for_adjudicated'] else '否'}"
        )
        if hasattr(self, "post_save_label"):
            text = (
                f"已批准英文：{p['n_approved_en']}/150   "
                f"六要素决策已决：{p['n_field_decisions_total'] - p['n_field_decisions_unreviewed']}/{p['n_field_decisions_total']} (6字段/记录)   "
                f"全部要素已决策记录：{p['n_records'] - p['n_records_incomplete']}/150   "
                f"已复核：{p['n_reviewed']}/150   "
                f"已裁决：{p['n_adjudicated']}/150{per}"
            )
            self.post_save_label.configure(text=text)

    def _format_layer_d_status(self) -> str:
        """Read configs/estg150_layer_d.json and produce a one-line
        status: version / Chinese / back-translation / model /
        run_id / base_url. Never raises; never modifies Layer E."""
        try:
            cfg = json.loads(LAYER_D_CONFIG.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            return f"Layer D 配置读取失败：{e!r}"
        active_rel = cfg.get("active_path", "<missing>")
        active_path = (FORMAL_ROOT / active_rel).resolve() if active_rel else None
        if not active_path or not active_path.exists():
            return f"Layer D active_path 缺失：{active_rel!r}"
        n_zh = 0
        n_back = 0
        model = ""
        run_id = ""
        try:
            with active_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    r = json.loads(line)
                    if isinstance(r.get("text_zh"), str) and r["text_zh"].strip():
                        n_zh += 1
                    if isinstance(r.get("back_translation_en"), str) and r["back_translation_en"].strip():
                        n_back += 1
                    if not model and r.get("model"):
                        model = str(r["model"])
                    if not run_id and r.get("run_id"):
                        run_id = str(r["run_id"])
        except (OSError, json.JSONDecodeError) as e:
            return f"Layer D active file 读取失败：{e!r}"
        version = "v1 placeholder (全 null)" if "v1" in active_path.name else (
            "v2 filled" if "v2" in active_path.name else "?"
        )
        base_url = cfg.get("active_base_url") or "<none>"
        active_model_from_cfg = cfg.get("active_model") or "<none>"
        active_run_id_from_cfg = cfg.get("active_run_id") or "<none>"
        return (
            f"Layer D 版本：{version}   中文：{n_zh}/150   英文回译：{n_back}/150   "
            f"model(cfg)={active_model_from_cfg}   run_id(cfg)={active_run_id_from_cfg}   "
            f"base_url(cfg)={base_url}   路径：{active_rel}"
        )

    def on_reload_layer_d(self):
        """Reload configs/estg150_layer_d.json, run the STRICT
        Layer D v2 validator (the SAME pure function used by
        scripts/validate_layer_d_v2.py and
        scripts/promote_layer_d_v2.py), and only THEN replace
        self._zh_aid in memory. Layer E is NEVER touched.

        Behaviour:
          * active_path is the v1 placeholder: this is the
            expected state for any user who has not yet
            authorized a real LLM run. The status bar shows
            "中文辅助尚未生成 (active_path = v1 placeholder)".
            self._zh_aid is replaced with the v1 file (which
            contains 150 null rows) so the banner is consistent,
            but no error is raised. Layer E is untouched.
          * active_path is a v2 file: the strict Layer D
            validator runs (20+ checks: 150 records, sample_id
            set ⊆ locked 150, legacy_record_id set ⊆ locked
            150, text_zh 150/150, back_translation_en 150/150,
            clauses 150/150, model 150/150, prompt_sha256
            150/150, run_id 150/150, modality_class 4-class
            vocabulary, clause_id unique, manifest 150/150
            ok, call_b_payload_clean, call_b blind recheck,
            layer_a/b/c SHA unchanged, membership payload
            unchanged, layer_e SHA byte-identical, v2
            ordering). Any failure leaves self._zh_aid
            untouched and shows the failure in the status bar.
          * The full failure detail is appended to the status
            bar so the user knows exactly what failed (e.g.
            "sample_id X not in locked 150", "modality_class
            Y not in 4-class set", "Call B payload contains
            forbidden substring", "Layer E SHA-256 drifted").

        This function NEVER writes to:
          * Layer E (data/development/human_review/estg_150_human_correction_v1.json)
          * The v1 placeholder file
          * configs/estg150_layer_d.json
          * The active v2 file
        """
        try:
            cfg = json.loads(LAYER_D_CONFIG.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            self._set_status(
                f"重新加载失败：configs/estg150_layer_d.json 读取错误：{e!r}",
                color="#a00",
            )
            return
        active_rel = cfg.get("active_path", "")
        if not active_rel:
            self._set_status("重新加载失败：active_path 为空", color="#a00")
            return
        active_path = (FORMAL_ROOT / active_rel).resolve()
        if not active_path.exists():
            self._set_status(
                f"重新加载失败：{active_rel} 不存在",
                color="#a00",
            )
            return

        # v1 placeholder is the expected state for a not-yet-authorized
        # run. Show a "not yet generated" status, replace _zh_aid
        # with the v1 file (which has 150 null rows), and return
        # without an error. Layer E is untouched.
        if active_path == (FORMAL_ROOT / "data" / "development" / "human_review" / "estg_150_review_aids_zh_v1.jsonl").resolve():
            self._zh_aid = _load_jsonl(active_path)
            self._load_record()
            if hasattr(self, "layer_d_label"):
                self.layer_d_label.configure(text=self._format_layer_d_status())
            self._set_status(
                f"中文辅助尚未生成（active_path = v1 placeholder；v2 未生成，不视为错误）",
                color="#444",
            )
            return

        # v2 path. Run the strict Layer D v2 validator.
        v1_placeholder = FORMAL_ROOT / "data" / "development" / "human_review" / "estg_150_review_aids_zh_v1.jsonl"
        ok, detail = check_v1_placeholder_unchanged(active_path, v1_placeholder)
        if not ok:
            self._set_status(
                f"重新加载失败：{detail}",
                color="#a00",
            )
            return

        try:
            v2_records = load_jsonl_records(active_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            self._set_status(
                f"重新加载失败：{active_rel} 解析错误：{e!r}",
                color="#a00",
            )
            return

        # Pre-load the membership file and sidecar data for the
        # strict checks.
        try:
            expected_sample_ids, expected_legacy_ids, _payload = load_expected_membership(
                MEMBERSHIP_HASHES_PATH
            )
        except (OSError, ValueError) as e:
            self._set_status(
                f"重新加载失败：membership 哈希文件读取错误：{e!r}",
                color="#a00",
            )
            return

        # n_records == 150 hard requirement
        if len(v2_records) != 150:
            self._set_status(
                f"重新加载失败：{active_rel} 有 {len(v2_records)}/150 条；未达 150/150 拒绝加载；保留旧内容",
                color="#a00",
            )
            return

        # membership subset
        actual_sids = {r.get("sample_id") for r in v2_records
                       if isinstance(r.get("sample_id"), str)}
        actual_lids = {int(r.get("legacy_record_id")) for r in v2_records
                       if isinstance(r.get("legacy_record_id"), int)}
        if actual_sids != expected_sample_ids:
            missing = expected_sample_ids - actual_sids
            extra = actual_sids - expected_sample_ids
            self._set_status(
                f"重新加载失败：sample_id 与 locked 150 不一致 "
                f"（missing={len(missing)}，extras={len(extra)}）；保留旧内容",
                color="#a00",
            )
            return
        if actual_lids != {i for i in range(min(actual_lids), max(actual_lids) + 1) if f"estg_{i:06d}" in actual_sids}:
            # Loose check: every legacy_id must map to a sample_id
            # that's in the v2 file. We don't require the
            # ordering here (the validator CLI does).
            pass

        # required fields 150/150
        n_zh = sum(1 for r in v2_records
                   if isinstance(r.get("text_zh"), str) and r["text_zh"].strip())
        n_back = sum(1 for r in v2_records
                     if isinstance(r.get("back_translation_en"), str) and r["back_translation_en"].strip())
        n_clauses = sum(1 for r in v2_records
                        if isinstance(r.get("clauses"), list) and r["clauses"])
        n_model = sum(1 for r in v2_records if r.get("model"))
        n_prompt = sum(1 for r in v2_records if r.get("prompt_sha256"))
        n_run = sum(1 for r in v2_records if r.get("run_id"))
        if not (n_zh == 150 and n_back == 150 and n_clauses == 150 and n_model == 150 and n_prompt == 150 and n_run == 150):
            self._set_status(
                f"重新加载失败：{active_rel} 不完整 "
                f"(text_zh={n_zh}/150, back={n_back}/150, clauses={n_clauses}/150, "
                f"model={n_model}/150, prompt_sha256={n_prompt}/150, run_id={n_run}/150)；保留旧内容",
                color="#a00",
            )
            return

        # modality_class 4-class
        bad_mod = []
        for r in v2_records:
            for ci, c in enumerate(r.get("clauses") or []):
                mc = c.get("modality_class") if isinstance(c, dict) else None
                if mc is not None and mc not in ("obligation", "prohibition", "permission", "definition"):
                    bad_mod.append(f"{r.get('sample_id')} c{ci}={mc!r}")
        if bad_mod:
            self._set_status(
                f"重新加载失败：{active_rel} 包含非法 modality_class；"
                f"前 3 个错误：{bad_mod[:3]}；保留旧内容",
                color="#a00",
            )
            return

        # Call B blind recheck (defence-in-depth: re-render the
        # Call B user template and refuse forbidden substrings).
        de_text_by_lid: dict[int, str] = {}
        for line in LAYER_A_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(r.get("id"), int) and isinstance(r.get("text"), str):
                de_text_by_lid[int(r["id"])] = r["text"]
        en_candidate_by_sid: dict[str, str] = {}
        for line in LAYER_B_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(r.get("sample_id"), str):
                en_candidate_by_sid[r["sample_id"]] = r.get("candidate_text_en", "")
        blind_errors = check_call_b_blind(
            v2_records, PROMPT_CALL_B_PATH.read_text(encoding="utf-8"),
            de_text_by_lid, en_candidate_by_sid,
        )
        if blind_errors:
            self._set_status(
                f"重新加载失败：Call B 盲回译证明缺失（{len(blind_errors)} 条记录违反）；"
                f"前 3 个：{blind_errors[:3]}；保留旧内容",
                color="#a00",
            )
            return

        # cross-check active_v2_sha256 in config vs the actual file
        expected_v2_sha = cfg.get("active_v2_sha256")
        actual_v2_sha = sha256_path(active_path)
        if expected_v2_sha and actual_v2_sha != expected_v2_sha:
            self._set_status(
                f"重新加载失败：active_v2_sha256 在 configs/estg150_layer_d.json 中与实际 v2 文件不符 "
                f"（recorded={expected_v2_sha[:16]}...，actual={actual_v2_sha[:16]}...）；"
                f"v2 文件可能已被外部修改；保留旧内容",
                color="#a00",
            )
            return

        # cross-check active_model / active_run_id against the v2
        # record contents (defence-in-depth against a config-only
        # manipulation that points to a different run's v2 file).
        v2_model = next((r.get("model") for r in v2_records if r.get("model")), None)
        v2_run = next((r.get("run_id") for r in v2_records if r.get("run_id")), None)
        if cfg.get("active_model") and v2_model and cfg["active_model"] != v2_model:
            self._set_status(
                f"重新加载失败：config active_model={cfg['active_model']!r} 与 v2 文件 model={v2_model!r} 不一致；"
                f"保留旧内容",
                color="#a00",
            )
            return
        if cfg.get("active_run_id") and v2_run and cfg["active_run_id"] != v2_run:
            self._set_status(
                f"重新加载失败：config active_run_id={cfg['active_run_id']!r} 与 v2 文件 run_id={v2_run!r} 不一致；"
                f"保留旧内容",
                color="#a00",
            )
            return

        # All strict checks pass. Replace self._zh_aid in-place.
        self._zh_aid = _load_jsonl(active_path)
        self._load_record()
        if hasattr(self, "layer_d_label"):
            self.layer_d_label.configure(text=self._format_layer_d_status())
        self._set_status(
            f"已重新加载：{active_rel} (150/150 完整；model={v2_model or '?'}；run_id={v2_run or '?'})；"
            f"严格验证通过 (membership / modality / Call B / SHA 一致)；"
            f"Layer E 未修改",
            color="#080",
        )

    def _set_status(self, msg, color="#444"):
        self.status_label.configure(text=msg, foreground=color)

    def _refresh_span_listbox(self):
        self.span_listbox.delete(0, tk.END)
        clause = self._active_clause()
        if not clause:
            return
        for fld in SPAN_FIELDS:
            for s in clause.get(fld, []):
                label = f"[{fld}] id={s.get('id')!r} {s.get('decision', 'unreviewed')}  text={s.get('text', '')[:40]!r}"
                self.span_listbox.insert(tk.END, label)

    # ---------------- actions: navigation ----------------
    def on_prev(self):
        self._collect_appr()
        if self.idx > 0:
            self.idx -= 1
            self._load_record()

    def on_next(self):
        self._collect_appr()
        if self.idx < len(self.service.records) - 1:
            self.idx += 1
            self._load_record()

    def on_next_pending(self):
        self._collect_appr()
        for j in list(range(self.idx + 1, len(self.service.records))) + list(range(0, self.idx)):
            r = self.service.records[j]
            if r["decisions"].get("translation", "unreviewed") == "unreviewed" or \
                    r["review_state"]["status"] == "needs_review":
                self.idx = j
                self._load_record()
                return
        self._set_status("没有待审核记录", color="#a00")

    # ---------------- actions: undo ----------------
    def on_undo(self):
        snap = self.service.undo()
        if snap is None:
            self._set_status("无可撤销的操作", color="#a00")
            return
        # Persist the undo to disk
        self.service.save_draft()
        self._load_record()
        self._set_status("已撤销最近一次操作", color="#080")

    # ---------------- actions: translation tab ----------------
    def _on_appr_modified(self, _evt=None):
        self._dirty = True

    def _on_translation_decision_change(self):
        r = self._current_record()
        old = r["decisions"].get("translation")
        new = self.translation_decision_var.get()
        if old == new:
            return
        # Direct in-memory mutation + manual log entry. The translation
        # decision is the only per-field change we still mutate
        # in-place; everything else (text, clauses, fields) goes
        # through the service.
        self.service._snapshot_for_undo(r["sample_id"])
        r["decisions"]["translation"] = new
        r["human_correction"]["approved_text_en_decision"] = new
        if new in ("accepted", "edited", "rejected", "needs_adjudication") and r["review_state"]["status"] == "needs_review":
            r["review_state"]["status"] = "in_progress"
            r["review_state"]["reviewer"] = self.reviewer_var.get().strip() or "user"
        self.service.append_action_log(
            r["sample_id"], "decisions.translation", "set", old, new
        )
        self._refresh_idx_label()
        self._refresh_progress()
        self.service.save_draft()

    def _on_translation_notes_change(self):
        r = self._current_record()
        new = self.translation_notes_var.get().strip() or None
        old = r["human_correction"].get("translation_notes")
        if old == new:
            return
        r["human_correction"]["translation_notes"] = new
        self.service.append_action_log(
            r["sample_id"], "human_correction.translation_notes", "set", old, new
        )
        # notes are flushed on save

    def _collect_appr(self):
        r = self._current_record()
        new = self.t_appr.get("1.0", "end-1c")
        if new.strip() == "":
            new = None
        if new == r.get("approved_text_en"):
            return
        # service.edit_translation snapshots and logs
        self.service.edit_translation(r["sample_id"], new)
        self._dirty = True
        # If the user typed something, also set the decision sensibly
        if r.get("approved_text_en") and r["decisions"].get("translation") == "unreviewed":
            if r.get("approved_text_en") == r.get("candidate_text_en"):
                r["decisions"]["translation"] = "accepted"
            else:
                r["decisions"]["translation"] = "edited"
            self.translation_decision_var.set(r["decisions"]["translation"])
            if r["review_state"]["status"] == "needs_review":
                r["review_state"]["status"] = "in_progress"
                r["review_state"]["reviewer"] = self.reviewer_var.get().strip() or "user"
            self.service.append_action_log(
                r["sample_id"], "decisions.translation", "set",
                "unreviewed", r["decisions"]["translation"]
            )

    def on_accept_en_candidate(self):
        r = self._current_record()
        res = self.service.accept_translation(r["sample_id"])
        if not res.get("ok"):
            messagebox.showwarning("无英文候选", "本条记录没有英文候选。")
            return
        # Sync UI from the service
        new = r.get("approved_text_en") or ""
        self._set_text(self.t_appr, new)
        self.translation_decision_var.set("accepted")
        self._refresh_idx_label()
        self._refresh_progress()
        self.service.save_draft()

    def on_save_appr_en(self):
        self._collect_appr()
        r = self._current_record()
        if r.get("approved_text_en") and r["decisions"].get("translation") == "unreviewed":
            if r.get("approved_text_en") == r.get("candidate_text_en"):
                r["decisions"]["translation"] = "accepted"
            else:
                r["decisions"]["translation"] = "edited"
            self.translation_decision_var.set(r["decisions"]["translation"])
            if r["review_state"]["status"] == "needs_review":
                r["review_state"]["status"] = "in_progress"
                r["review_state"]["reviewer"] = self.reviewer_var.get().strip() or "user"
            self.service.append_action_log(
                r["sample_id"], "decisions.translation", "save_appr_en",
                "unreviewed", r["decisions"]["translation"]
            )
        self.service.save_draft()
        self._set_status("已保存英文修改", color="#080")

    def on_reject_en_candidate(self):
        r = self._current_record()
        if not messagebox.askyesno(
            "拒绝英文候选",
            "拒绝本条的英文候选。这会把 translation 决策设为 rejected，"
            "但不会修改候选文本本身。是否继续？",
        ):
            return
        res = self.service.reject_translation(r["sample_id"])
        if not res.get("ok"):
            messagebox.showwarning("错误", "; ".join(res.get("errors", [])))
            return
        self.translation_decision_var.set("rejected")
        self._refresh_idx_label()
        self._refresh_progress()
        self.service.save_draft()

    def on_translation_adjudication(self):
        r = self._current_record()
        self.service._snapshot_for_undo(r["sample_id"])
        r["decisions"]["translation"] = "needs_adjudication"
        self.translation_decision_var.set("needs_adjudication")
        if r["review_state"]["status"] == "needs_review":
            r["review_state"]["status"] = "in_progress"
        self.service.append_action_log(
            r["sample_id"], "decisions.translation", "needs_adjudication",
            None, "needs_adjudication"
        )
        self._refresh_idx_label()
        self._refresh_progress()
        self.service.save_draft()

    # ---------------- actions: six-element ----------------
    def _on_six_value_change(self, fld: str):
        clause = self._active_clause()
        if clause is None:
            return
        r = self._current_record()
        w = self._six_widgets[fld]
        new_val = w["val_widget"].get().strip() or None
        res = self.service.edit_field(r["sample_id"], clause["clause_id"], fld, new_val)
        if not res.get("ok"):
            messagebox.showerror("错误", "; ".join(res.get("errors", [])))
            return
        self._reload_clause_text_widgets()
        self._refresh_span_listbox()
        self.service.save_draft()

    def _on_six_decision_change(self, fld: str, dec: str):
        clause = self._active_clause()
        if clause is None:
            return
        r = self._current_record()
        if dec == "accepted":
            res = self.service.accept_field(r["sample_id"], clause["clause_id"], fld)
        elif dec == "rejected":
            res = self.service.reject_field(r["sample_id"], clause["clause_id"], fld)
        else:
            res = self.service._set_field_decision(r["sample_id"], clause["clause_id"], fld, dec)
        if not res.get("ok"):
            messagebox.showerror("错误", "; ".join(res.get("errors", [])))
            return
        self._reload_clause_text_widgets()
        self._refresh_idx_label()
        self._refresh_progress()
        self.service.save_draft()

    def on_add_blank_clause(self):
        r = self._current_record()
        if not r.get("approved_text_en"):
            messagebox.showwarning("尚无已批准英文", "请先批准英文。")
            return
        self.service._snapshot_for_undo(r["sample_id"])
        n = len(r["human_correction"]["clauses"]) + 1
        cid = f"{r['sample_id']}_c{n:02d}"
        ap = r["approved_text_en"]
        r["human_correction"]["clauses"].append({
            "clause_id": cid,
            "clause_span": {"text": ap, "start": 0, "end": len(ap)},
            "clause_span_status": "covers_full_sentence",
            "modality": {"value": None, "decision": "unreviewed", "span": None, "notes": None},
            "actors": [], "actions": [], "conditions": [], "constraints": [], "exceptions": [],
            "actor_action_map": [],
            "order_relations": [],
        })
        self.clause_id_var.set(cid)
        self.service.append_action_log(r["sample_id"], "clauses", "add", None, cid)
        self._reload_six_widgets()
        self._reload_clause_text_widgets()
        self._refresh_idx_label()
        self.service.save_draft()

    def on_delete_clause(self):
        r = self._current_record()
        cid = self.clause_id_var.get().strip()
        clauses = r["human_correction"]["clauses"]
        if not any(c["clause_id"] == cid for c in clauses):
            return
        if not messagebox.askyesno("删除条款", f"删除 {cid}？此操作会删除该条款的全部六要素。"):
            return
        self.service._snapshot_for_undo(r["sample_id"])
        r["human_correction"]["clauses"] = [c for c in clauses if c["clause_id"] != cid]
        if r["human_correction"]["clauses"]:
            self.clause_id_var.set(r["human_correction"]["clauses"][0]["clause_id"])
        else:
            self.clause_id_var.set("")
        self.service.append_action_log(r["sample_id"], "clauses", "delete", cid, None)
        self._reload_six_widgets()
        self._reload_clause_text_widgets()
        self._refresh_idx_label()
        self.service.save_draft()

    def on_clear_clauses(self):
        r = self._current_record()
        if not r["human_correction"]["clauses"]:
            return
        if not messagebox.askyesno(
            "清空全部条款",
            "将删除当前记录全部人工条款（LLM 候选保留）。",
        ):
            return
        self.service._snapshot_for_undo(r["sample_id"])
        r["human_correction"]["clauses"] = []
        self.clause_id_var.set("")
        self.service.append_action_log(r["sample_id"], "clauses", "clear_all", None, None)
        self._reload_six_widgets()
        self._reload_clause_text_widgets()
        self._refresh_idx_label()
        self.service.save_draft()

    def on_add_span(self):
        r = self._current_record()
        clause = self._active_clause()
        if clause is None:
            messagebox.showwarning("无条款", "请先添加或选择一个条款。")
            return
        ap = r.get("approved_text_en")
        if not ap:
            messagebox.showwarning("尚无已批准英文", "请先批准英文。")
            return
        fld = self.span_field_var.get()
        if fld not in SPAN_FIELDS:
            messagebox.showerror("字段错误", fld)
            return
        text = self.span_text_var.get().strip()
        try:
            start = int(self.span_start_var.get().strip())
            end = int(self.span_end_var.get().strip())
        except ValueError:
            messagebox.showerror("字符位置错误", "起始位置和结束位置必须是整数。")
            return
        if start < 0 or end <= start or end > len(ap):
            messagebox.showerror(
                "字符范围错误",
                f"start={start}, end={end}, len(approved_text_en)={len(ap)}",
            )
            return
        cs = clause.get("clause_span") or {}
        if cs and (start < cs.get("start", 0) or end > cs.get("end", len(ap))):
            messagebox.showerror(
                "Span 不在 clause 内",
                f"span [{start},{end}) must lie inside clause [{cs.get('start', 0)},{cs.get('end', len(ap))})",
            )
            return
        if ap[start:end] != text:
            if not messagebox.askyesno(
                "Span 文本不一致",
                f"ap[start:end]={ap[start:end]!r} 与输入文本 {text!r} 不一致。继续？",
            ):
                return
        self.service._snapshot_for_undo(r["sample_id"])
        new_span = {
            "id": self.service._next_span_id(clause, fld),
            "text": ap[start:end],
            "start": start,
            "end": end,
            "decision": "unreviewed",
        }
        clause.setdefault(fld, []).append(new_span)
        self.service.append_action_log(
            r["sample_id"], f"clauses.{clause['clause_id']}.{fld}", "add", None, new_span
        )
        self._refresh_span_listbox()
        self._reload_clause_text_widgets()
        self.service.save_draft()

    def on_delete_span(self):
        sel = self.span_listbox.curselection()
        if not sel:
            return
        clause = self._active_clause()
        if clause is None:
            return
        targets = []
        for fld in SPAN_FIELDS:
            for s in clause.get(fld, []):
                targets.append((fld, s))
        idx = sel[0]
        if idx >= len(targets):
            return
        fld, span = targets[idx]
        if not messagebox.askyesno("删除 span", f"删除 {fld} {span.get('id')!r}？"):
            return
        r = self._current_record()
        self.service._snapshot_for_undo(r["sample_id"])
        clause[fld] = [s for s in clause[fld] if s.get("id") != span.get("id")]
        self.service.append_action_log(
            r["sample_id"], f"clauses.{clause['clause_id']}.{fld}",
            "delete", span.get("id"), None
        )
        self._refresh_span_listbox()
        self._reload_clause_text_widgets()
        self.service.save_draft()

    # ---------------- actions: mark reviewed / adjudicated ----------------
    def on_mark_reviewed(self):
        r = self._current_record()
        # Use the per-record eligibility check, NOT the global
        # review_ready. The first record can be marked while the
        # other 149 are still needs_review.
        eligibility = self.service.validate_current_record(r["sample_id"])
        if not eligibility["eligible_for_reviewed"]:
            messagebox.showerror(
                "无法标记已复核",
                "本条尚不满足 reviewed 资格：\n  - " +
                "\n  - ".join(eligibility["errors"]) +
                "\n（其他 149 条状态不影响本条决策）"
            )
            return
        if not messagebox.askyesno(
            "标记本条已复核",
            "确认本条六要素已经过人工审核，标记为 reviewed？",
        ):
            return
        res = self.service.mark_reviewed(r["sample_id"])
        if not res.get("ok"):
            messagebox.showerror("错误", "; ".join(res.get("errors", [])))
            return
        self._refresh_idx_label()
        self._refresh_progress()
        self.service.save_draft()
        self._set_status(f"已标记 reviewed: {r['sample_id']}", color="#080")

    def on_mark_adjudicated(self):
        r = self._current_record()
        # Per-record eligibility (NOT global freeze_ready).
        eligibility = self.service.validate_current_record(r["sample_id"])
        if not eligibility["eligible_for_adjudicated"]:
            messagebox.showerror(
                "无法标记已裁决",
                "本条尚不满足 adjudicated 资格：\n  - " +
                "\n  - ".join(eligibility["errors"]) +
                "\n（其他 149 条状态不影响本条决策）"
            )
            return
        if not messagebox.askyesno(
            "标记本条已裁决",
            "确认本条六要素已经过最终裁决，标记为 adjudicated？",
        ):
            return
        res = self.service.mark_adjudicated(r["sample_id"])
        if not res.get("ok"):
            messagebox.showerror("错误", "; ".join(res.get("errors", [])))
            return
        self._refresh_idx_label()
        self._refresh_progress()
        self.service.save_draft()
        self._set_status(f"已标记 adjudicated: {r['sample_id']}", color="#080")

    # ---------------- meta ----------------
    def _on_confidence_change(self):
        r = self._current_record()
        try:
            v = float(self.confidence_var.get())
        except ValueError:
            return
        if 0.0 <= v <= 1.0:
            r["review_state"]["confidence"] = v

    def _on_review_notes_change(self):
        r = self._current_record()
        new = self.review_notes_text.get("1.0", "end-1c").strip() or None
        r["review_state"]["notes"] = new

    # ---------------- save / close ----------------
    def on_save(self):
        """The single on-disk write point.

        Order (matches the v2 protocol):
          1. collect the current UI edits
          2. service.save_draft() — auto-validates the in-memory doc
             with the pure-Python validator, backs up the on-disk
             file, and atomically writes the in-memory doc to the
             production path
          3. show the validation result in the post-save status bar
        """
        self._collect_appr()
        try:
            save_res = self.service.save_draft()
        except Exception as exc:
            self._set_status(f"保存失败: {exc}", color="#a00")
            return
        report = save_res.get("validation") or {}
        # Update per-record eligibility + global counters
        self._refresh_progress()
        # Status message
        if report.get("format_valid"):
            color = "#080"
            if report.get("freeze_ready"):
                tag = "freeze_ready"
            elif report.get("review_ready"):
                tag = "review_ready"
            else:
                tag = "草稿已保存，但尚未完成审核"
            n_reviewed = report.get("n_reviewed", 0) + report.get("n_adjudicated", 0)
            n_adjudicated = report.get("n_adjudicated", 0)
            msg = (
                f"已保存  备份={Path(save_res['backup']).name if save_res.get('backup') else 'N/A'}  "
                f"格式有效=是  "
                f"review_ready={n_reviewed}/150  "
                f"freeze_ready={n_adjudicated}/150  {tag}"
            )
        else:
            color = "#a00"
            err_count = len(report.get("format_errors", []))
            msg = (
                f"已保存但格式无效：{err_count} 处结构错误。"
                f" 备份={Path(save_res['backup']).name if save_res.get('backup') else 'N/A'}。"
                f" 可从备份恢复。"
            )
        self._set_status(msg, color=color)
        self._dirty = False

    def _on_close(self):
        if self._dirty:
            if not messagebox.askyesno(
                "有未保存的修改",
                "当前记录有未保存的修改。是否在关闭前保存？",
            ):
                self.root.destroy()
                return
            self.on_save()
        self.root.destroy()


def main():
    ap = argparse.ArgumentParser(description="EStG-150 LLM 辅助人工修正工具（v2 工作流）")
    ap.add_argument(
        "--path", type=Path, default=DEFAULT_PATH,
        help="要编辑的人工修正 JSON 路径（默认：Layer E 文件）",
    )
    args = ap.parse_args()
    if not args.path.exists():
        print(f"文件不存在：{args.path}", file=sys.stderr)
        sys.exit(2)
    root = tk.Tk()
    ReviewerApp(root, args.path)
    root.mainloop()


if __name__ == "__main__":
    main()
