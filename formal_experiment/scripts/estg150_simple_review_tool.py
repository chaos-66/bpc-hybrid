#!/usr/bin/env python3
"""极简 EStG-150 法规六要素修改工具。"""
from __future__ import annotations

import argparse
import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.estg150_service import HumanCorrectionService  # noqa: E402
from formal_experiment.estg150_simple_review import (  # noqa: E402
    MODALITIES,
    SPAN_FIELDS,
    SimpleReviewError,
    SimpleReviewSession,
    load_candidate_bundle,
)


DEFAULT_CANDIDATES = (
    ROOT
    / "data"
    / "development"
    / "estg"
    / "llm_candidate_runs"
    / "codex_internal_gpt56sol_full150_v1"
    / "ai_review_candidates.json"
)
DEFAULT_LAYER_E = (
    ROOT
    / "data"
    / "development"
    / "human_review"
    / "estg_150_human_correction_v1.json"
)
DEFAULT_BACKUPS = ROOT / "outputs" / "development" / "human_review" / "review_backups"
DEFAULT_ACTION_LOG = (
    ROOT
    / "outputs"
    / "development"
    / "human_review"
    / "estg_150_review_actions_v1.jsonl"
)

FIELD_LABELS = {
    "actors": "主体 Actor",
    "actions": "行为 Action",
    "conditions": "条件 Condition",
    "constraints": "约束 Constraint",
    "exceptions": "例外 Exception",
}
MODALITY_LABELS = {
    "obligation": "义务 obligation",
    "prohibition": "禁止 prohibition",
    "permission": "许可 permission",
    "definition": "定义 definition",
}
LABEL_TO_MODALITY = {value: key for key, value in MODALITY_LABELS.items()}


class SimpleReviewerApp:
    def __init__(self, root: tk.Tk, session: SimpleReviewSession):
        self.root = root
        self.session = session
        self.index = session.next_unfinished_index(-1)
        self.current_candidate: dict | None = None
        self.clause_widgets: list[dict] = []

        root.title("法规六要素快速修改")
        root.geometry("1180x860")
        root.minsize(920, 680)
        root.configure(background="#f4f1ea")

        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background="#f4f1ea")
        style.configure("TLabel", background="#f4f1ea", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("Progress.TLabel", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure(
            "Alert.TLabel",
            background="#fff3cd",
            foreground="#6b4700",
            font=("Microsoft YaHei UI", 9),
        )
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(10, 7))
        style.configure("Save.TButton", font=("Microsoft YaHei UI", 11, "bold"), padding=(16, 9))
        style.configure("TLabelframe.Label", font=("Microsoft YaHei UI", 11, "bold"))

        top = ttk.Frame(root, padding=(18, 14, 18, 8))
        top.pack(fill=tk.X)
        ttk.Label(top, text="法规六要素", style="Title.TLabel").pack(side=tk.LEFT)
        self.progress_var = tk.StringVar()
        ttk.Label(top, textvariable=self.progress_var, style="Progress.TLabel").pack(
            side=tk.RIGHT, padx=(12, 0)
        )

        nav = ttk.Frame(root, padding=(18, 0, 18, 10))
        nav.pack(fill=tk.X)
        ttk.Button(nav, text="← 上一条", command=self.previous).pack(side=tk.LEFT)
        ttk.Button(nav, text="稍后再看", command=self.defer).pack(side=tk.LEFT, padx=8)
        ttk.Button(nav, text="查看德文原文", command=self.show_german).pack(side=tk.LEFT)
        ttk.Button(
            nav,
            text="保存并下一条 →",
            command=self.save_and_next,
            style="Save.TButton",
        ).pack(side=tk.RIGHT)

        text_frame = ttk.LabelFrame(root, text="法规英文", padding=10)
        text_frame.pack(fill=tk.X, padx=18, pady=(0, 10))
        self.law_text = tk.Text(
            text_frame,
            height=7,
            wrap="word",
            relief="flat",
            background="#fffdf8",
            foreground="#222222",
            font=("Segoe UI", 11),
            padx=10,
            pady=8,
        )
        self.law_text.pack(fill=tk.X)
        self.law_text.configure(state="disabled")

        self.alert_var = tk.StringVar()
        self.alert_label = ttk.Label(
            root,
            textvariable=self.alert_var,
            style="Alert.TLabel",
            wraplength=1120,
            padding=(10, 6),
        )

        hint = ttk.Frame(root, padding=(20, 0, 20, 8))
        hint.pack(fill=tk.X)
        self.sample_var = tk.StringVar()
        ttk.Label(hint, textvariable=self.sample_var).pack(side=tk.LEFT)
        ttk.Label(
            hint,
            text="要素一行一个；删除一行就是删除该要素。span 会自动定位。",
        ).pack(side=tk.RIGHT)

        body = ttk.Frame(root)
        body.pack(fill=tk.BOTH, expand=True, padx=18)
        self.canvas = tk.Canvas(body, highlightthickness=0, background="#f4f1ea")
        scrollbar = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.clause_host = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.clause_host, anchor="nw"
        )
        self.clause_host.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfigure(self.canvas_window, width=event.width),
        )
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.status_var = tk.StringVar()
        ttk.Label(root, textvariable=self.status_var, padding=(18, 8, 18, 12)).pack(fill=tk.X)
        root.bind("<Control-s>", lambda _event: self.save_and_next())
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.load_current()

    def _on_mousewheel(self, event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _set_law_text(self, value: str) -> None:
        self.law_text.configure(state="normal")
        self.law_text.delete("1.0", tk.END)
        self.law_text.insert("1.0", value)
        self.law_text.configure(state="disabled")

    def _clear_clauses(self) -> None:
        for child in self.clause_host.winfo_children():
            child.destroy()
        self.clause_widgets.clear()

    def load_current(self) -> None:
        sample_id = self.session.sample_ids[self.index]
        candidate = self.session.candidate_for(sample_id)
        self.current_candidate = candidate
        self._set_law_text(candidate["translation"]["proposed_text_en"])
        warnings = list(candidate["translation"].get("issues") or [])
        warnings.extend(
            item.get("reason", "")
            for item in candidate.get("unsupported_or_ambiguous") or []
            if item.get("reason")
        )
        if warnings:
            warning_text = "；".join(dict.fromkeys(warnings))
            if len(warning_text) > 420:
                warning_text = warning_text[:417].rstrip() + "..."
            self.alert_var.set("AI 提醒：" + warning_text)
            self.alert_label.pack(fill=tk.X, padx=18, pady=(0, 8), before=self.canvas.master)
        else:
            self.alert_label.pack_forget()
        self._clear_clauses()

        done = self.session.is_done(sample_id)
        self.sample_var.set(
            f"{self.index + 1}/150 · {sample_id}" + (" · 已完成，可继续修改" if done else "")
        )
        for number, clause in enumerate(candidate["clauses"], 1):
            card = ttk.LabelFrame(self.clause_host, text=f"条款 {number}", padding=12)
            card.pack(fill=tk.X, pady=(0, 10))
            ttk.Label(
                card,
                text=clause["clause_span"]["text"],
                wraplength=1030,
                justify=tk.LEFT,
            ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
            card.columnconfigure(1, weight=1)

            ttk.Label(card, text="模态 Modality").grid(row=1, column=0, sticky="nw", padx=(0, 12))
            modality = ttk.Combobox(
                card,
                state="readonly",
                values=[MODALITY_LABELS[item] for item in MODALITIES],
                width=28,
            )
            modality.set(MODALITY_LABELS[clause["modality"]["label"]])
            modality.grid(row=1, column=1, sticky="w", pady=(0, 7))

            widgets = {"clause_id": clause["clause_id"], "modality": modality}
            for row, field in enumerate(SPAN_FIELDS, 2):
                ttk.Label(card, text=FIELD_LABELS[field]).grid(
                    row=row, column=0, sticky="nw", padx=(0, 12), pady=3
                )
                editor = tk.Text(
                    card,
                    height=max(2, min(4, len(clause[field]) + 1)),
                    wrap="word",
                    background="#fffdf8",
                    relief="solid",
                    borderwidth=1,
                    font=("Segoe UI", 10),
                    padx=7,
                    pady=5,
                )
                editor.insert("1.0", "\n".join(span["text"] for span in clause[field]))
                editor.grid(row=row, column=1, sticky="ew", pady=3)
                widgets[field] = editor
            self.clause_widgets.append(widgets)

        completed, total = self.session.progress()
        self.progress_var.set(f"完成 {completed}/{total}")
        self.status_var.set("没问题就直接点“保存并下一条”；有问题就在对应框里改。")
        self.canvas.yview_moveto(0)

    def _collect_edits(self) -> list[dict]:
        edits: list[dict] = []
        for widgets in self.clause_widgets:
            label = widgets["modality"].get()
            item = {
                "clause_id": widgets["clause_id"],
                "modality": LABEL_TO_MODALITY.get(label),
            }
            for field in SPAN_FIELDS:
                item[field] = widgets[field].get("1.0", tk.END).strip()
            edits.append(item)
        return edits

    @staticmethod
    def _candidate_edits(candidate: dict) -> list[dict]:
        return [
            {
                "clause_id": clause["clause_id"],
                "modality": clause["modality"]["label"],
                **{
                    field: "\n".join(span["text"] for span in clause[field])
                    for field in SPAN_FIELDS
                },
            }
            for clause in candidate["clauses"]
        ]

    def _may_leave(self) -> bool:
        if self.current_candidate is None:
            return True
        if self._collect_edits() == self._candidate_edits(self.current_candidate):
            return True
        return messagebox.askyesno(
            "有未保存修改",
            "这一条有未保存修改。要放弃这些修改并离开吗？",
            parent=self.root,
        )

    def save_and_next(self) -> None:
        sample_id = self.session.sample_ids[self.index]
        try:
            result = self.session.save_and_finish(sample_id, self._collect_edits())
        except SimpleReviewError as exc:
            messagebox.showerror("这条还不能保存", str(exc), parent=self.root)
            self.status_var.set(str(exc))
            return
        completed, total = self.session.progress()
        self.index = self.session.next_unfinished_index(self.index)
        self.load_current()
        self.status_var.set(
            f"已保存 {sample_id}（{result['clause_count']} 个条款），完成 {completed}/{total}。"
        )

    def defer(self) -> None:
        if not self._may_leave():
            return
        self.index = self.session.next_unfinished_index(self.index)
        self.load_current()

    def previous(self) -> None:
        if not self._may_leave():
            return
        self.index = (self.index - 1) % len(self.session.sample_ids)
        self.load_current()

    def close(self) -> None:
        if self._may_leave():
            self.root.destroy()

    def show_german(self) -> None:
        sample_id = self.session.sample_ids[self.index]
        record = self.session.service.get_record(sample_id) or {}
        popup = tk.Toplevel(self.root)
        popup.title(f"德文原文 · {sample_id}")
        popup.geometry("880x420")
        text = tk.Text(popup, wrap="word", font=("Segoe UI", 11), padx=12, pady=12)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert("1.0", record.get("raw_text_de") or "")
        text.configure(state="disabled")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-path", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--layer-e-path", type=Path, default=DEFAULT_LAYER_E)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUPS)
    parser.add_argument("--action-log", type=Path, default=DEFAULT_ACTION_LOG)
    parser.add_argument("--reviewer", default="user")
    parser.add_argument(
        "--check",
        action="store_true",
        help="只检查 150 条候选和当前进度，不打开窗口、不写文件",
    )
    return parser.parse_args()


def build_session(args: argparse.Namespace) -> SimpleReviewSession:
    bundle = load_candidate_bundle(args.candidate_path)
    service = HumanCorrectionService(
        path=args.layer_e_path,
        backup_dir=args.backup_dir,
        action_log=args.action_log,
        reviewer=args.reviewer,
    )
    return SimpleReviewSession(service, bundle)


def main() -> int:
    args = parse_args()
    try:
        session = build_session(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"无法启动：{exc}", file=sys.stderr)
        return 2
    if args.check:
        completed, total = session.progress()
        print(f"Sol 候选：{len(session.sample_ids)}/150；已完成：{completed}/{total}")
        print("检查模式未写文件。")
        return 0
    root = tk.Tk()
    SimpleReviewerApp(root, session)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
