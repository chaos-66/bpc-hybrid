"""Small Tk window for the 30 AI-reviewed binding proposals (standard library only)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from formal_experiment.stage3_binding_review import BindingReviewStore, OUTPUT

ORDER_CHOICES = {
    "仅确认流程先后，暂不新增法规顺序": "process_only",
    "我确认法规要求这个先后顺序": "rule_order",
    "不采用这组顺序": "rejected",
}


class ReviewWindow:
    def __init__(self, root, store):
        self.root, self.store = root, store
        self.index = store.resume_index()
        self.root.title("Stage 3 · 逐条审核")
        self.root.geometry("1080x850")
        self.root.minsize(850, 640)
        style = ttk.Style(root)
        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 19, "bold"))
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 11, "bold"), padding=(14, 8))
        outer = ttk.Frame(root, padding=18)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text="Stage 3 逐条审核", style="Title.TLabel").pack(side="left")
        self.progress = ttk.Label(header)
        self.progress.pack(side="right")
        ttk.Label(outer, text="看一条，确认一条。每次确认自动保存，关闭后可以继续。").pack(anchor="w", pady=(6, 10))
        self.bar = ttk.Progressbar(outer, maximum=len(store.items))
        self.bar.pack(fill="x", pady=(0, 10))
        # Scroll the content, keeping the navigation buttons visible.
        body_wrap = ttk.Frame(outer)
        body_wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body_wrap, highlightthickness=0)
        scroll = ttk.Scrollbar(body_wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.body = ttk.Frame(self.canvas)
        win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(win, width=event.width))
        self.canvas.bind_all("<MouseWheel>", self.wheel)
        self.title = ttk.Label(self.body, font=("Microsoft YaHei UI", 13, "bold"), wraplength=940)
        self.title.pack(anchor="w", pady=(0, 3))
        self.meta = ttk.Label(self.body, foreground="#526071")
        self.meta.pack(anchor="w", pady=(0, 8))
        self.advice = self.text_box("我的审核理由", 5)
        self.action_var, self.actor_var = tk.StringVar(), tk.StringVar()
        self.action = self.combo("推荐规则动作（需要时可修改）", self.action_var)
        self.action.bind("<<ComboboxSelected>>", lambda e: self.update_action_text())
        self.action_text = ttk.Label(self.body, wraplength=950, foreground="#334155")
        self.action_text.pack(anchor="w", pady=(0, 8))
        self.actor = self.combo("规则执行者引用（缺少对应 span 时可留空）", self.actor_var)
        line = ttk.Frame(self.body)
        line.pack(fill="x", pady=(2, 8))
        ttk.Label(line, text="流程执行者").pack(side="left")
        self.process_actor = tk.StringVar()
        ttk.Entry(line, textvariable=self.process_actor, width=28).pack(side="left", padx=(10, 20))
        ttk.Label(line, text="流程归属已核对；原 lane ID 自动保留。", foreground="#526071").pack(side="left")
        self.order_frame = ttk.LabelFrame(self.body, text="顺序", padding=10)
        self.order_label = ttk.Label(self.order_frame, wraplength=920)
        self.order_label.pack(anchor="w", pady=(0, 5))
        self.order_var = tk.StringVar()
        self.order_combo = ttk.Combobox(self.order_frame, textvariable=self.order_var, state="readonly", values=list(ORDER_CHOICES))
        self.order_combo.pack(fill="x")
        self.order_combo.bind("<<ComboboxSelected>>", lambda e: self.toggle_order())
        self.endpoints = ttk.Frame(self.order_frame)
        self.before_var, self.after_var = tk.StringVar(), tk.StringVar()
        ttk.Label(self.endpoints, text="先执行的规则动作").pack(anchor="w")
        self.before = ttk.Combobox(self.endpoints, textvariable=self.before_var, state="readonly")
        self.before.pack(fill="x")
        ttk.Label(self.endpoints, text="后执行的规则动作").pack(anchor="w")
        self.after = ttk.Combobox(self.endpoints, textvariable=self.after_var, state="readonly")
        self.after.pack(fill="x")
        self.note = self.text_box("备注（可不填）", 3)
        self.status = ttk.Label(outer, foreground="#176448", wraplength=1000)
        self.status.pack(anchor="w", pady=(8, 5))
        nav = ttk.Frame(outer)
        nav.pack(fill="x")
        ttk.Button(nav, text="上一条", command=lambda: self.move(-1)).pack(side="left")
        ttk.Button(nav, text="跳过 / 下一条", command=lambda: self.move(1)).pack(side="left", padx=6)
        ttk.Button(nav, text="不接受并下一条", command=lambda: self.save("reject")).pack(side="right")
        self.accept_button = ttk.Button(nav, text="确认并下一条", style="Accent.TButton", command=lambda: self.save("accept"))
        self.accept_button.pack(side="right", padx=10)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.show_item()

    def wheel(self, event):
        if isinstance(event.widget, (tk.Text, ttk.Combobox)):
            return
        self.canvas.yview_scroll(-int(event.delta / 120), "units")

    def text_box(self, title, height):
        frame = ttk.LabelFrame(self.body, text=title, padding=8)
        frame.pack(fill="x", pady=(0, 8))
        box = tk.Text(frame, height=height, wrap="word", font=("Microsoft YaHei UI", 10), undo=True, relief="flat", padx=4, pady=3)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=box.yview)
        box.configure(yscrollcommand=scrollbar.set)
        box.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return box

    def combo(self, title, variable):
        ttk.Label(self.body, text=title).pack(anchor="w", pady=(2, 3))
        combo = ttk.Combobox(self.body, textvariable=variable, state="readonly")
        combo.pack(fill="x", pady=(0, 5))
        return combo

    @staticmethod
    def options(spans):
        return {"（留空 / 无合适的现有引用）": None,
                **{s["text"].replace("\n", " ") + "  [" + s["id"] + "]": s["id"] for s in spans}}

    @staticmethod
    def set_id(variable, options, value):
        variable.set(next(label for label, ident in options.items() if ident == value))

    def show_item(self):
        row = self.store.items[self.index]
        self.pair = row["pair_id"]
        current = self.store.current(self.pair)
        rev = row["agent_review"]
        rec = self.store.document["records"].get(self.pair)
        done = len(self.store.document["records"])
        self.progress.configure(text=f"已审核 {done} / {len(self.store.items)}")
        self.bar["value"] = done
        self.title.configure(text=row["target_activity_name"].strip())
        state = "已确认" if rec and rec["choice"] == "accept" else ("已不接受" if rec else "待审核")
        types = {"incorrect_actor": "执行者", "missing_action": "动作缺失", "out_of_order": "顺序"}
        self.meta.configure(text=f"第 {self.index + 1} 条 · {self.pair} · {row['rule_id']} · {types[row['target_violation_type']]} · {state}")
        self.advice.configure(state="normal")
        self.advice.delete("1.0", "end")
        self.advice.insert("1.0", rev["action_note_zh"] + "\n\n" + rev["actor_note_zh"])
        self.advice.configure(state="disabled")
        side = self.store.contexts[self.pair]["rule_side"]
        self.action_options, self.actor_options = self.options(side["actions"]), self.options(side["actors"])
        for combo in (self.action, self.before, self.after):
            combo["values"] = list(self.action_options)
        self.actor["values"] = list(self.actor_options)
        self.set_id(self.action_var, self.action_options, current["action_id"])
        self.set_id(self.actor_var, self.actor_options, current["actor_id"])
        self.set_id(self.before_var, self.action_options, current["order_before_action_id"])
        self.set_id(self.after_var, self.action_options, current["order_after_action_id"])
        self.process_actor.set(current["process_actor"])
        self.order_frame.pack_forget()
        if row["target_violation_type"] == "out_of_order":
            self.order_frame.pack(fill="x", pady=(0, 8), before=self.note.master)
            order = row["recommended_proposal"]["order_relation_proposal"]
            self.order_label.configure(text=order["before_activity"]["name"].strip() + "  →  " + order["after_activity"]["name"].strip())
            self.order_var.set(next(k for k, v in ORDER_CHOICES.items() if v == current["order_scope"]))
        self.toggle_order()
        self.note.delete("1.0", "end")
        self.note.insert("1.0", rec["note"] if rec else "")
        self.update_action_text()
        self.initial = (self.values(), self.note.get("1.0", "end-1c"))
        self.canvas.yview_moveto(0)
        self.status.configure(text=self.completion_text() if done == len(self.store.items) else "修改下拉选项或备注后，点“确认并下一条”保存。空项也可确认。")

    def update_action_text(self):
        ident = self.action_options.get(self.action_var.get())
        spans = self.store.contexts[self.pair]["rule_side"]["actions"]
        text = next((s["text"] for s in spans if s["id"] == ident), "当前没有合适的规则动作，确认后保留空值。")
        self.action_text.configure(text=text)

    def toggle_order(self):
        self.endpoints.pack_forget()
        if self.order_var.get() and ORDER_CHOICES.get(self.order_var.get()) == "rule_order":
            self.endpoints.pack(fill="x", pady=(8, 0))

    def values(self):
        value = self.store.current(self.pair)
        value.update(action_id=self.action_options[self.action_var.get()],
                     actor_id=self.actor_options[self.actor_var.get()],
                     process_actor=self.process_actor.get().strip())
        if self.store.by_id[self.pair]["target_violation_type"] == "out_of_order":
            value.update(order_scope=ORDER_CHOICES[self.order_var.get()],
                         order_before_action_id=self.action_options[self.before_var.get()],
                         order_after_action_id=self.action_options[self.after_var.get()])
        return value

    def can_leave(self):
        if (self.values(), self.note.get("1.0", "end-1c")) == self.initial:
            return True
        return messagebox.askyesno("有未保存的修改", "这条修改尚未确认，放弃修改并离开吗？", parent=self.root)

    def move(self, delta):
        if self.can_leave():
            self.index = (self.index + delta) % len(self.store.items)
            self.show_item()

    def completion_text(self):
        return f"30 条审核完成，结果已保存。可以直接关闭窗口，也可以返回修改。\n{self.store.output}"

    def save(self, choice):
        try:
            self.store.save(self.pair, choice, self.values(), self.note.get("1.0", "end-1c"))
        except (OSError, ValueError) as exc:
            messagebox.showerror("没有保存", str(exc), parent=self.root)
            return
        next_index = self.store.next_pending(self.index)
        if next_index is not None:
            self.index = next_index
        self.show_item()
        if next_index is None:
            self.status.configure(text=self.completion_text())

    def close(self):
        if self.can_leave():
            self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    root = tk.Tk()
    root.withdraw()
    try:
        store = BindingReviewStore(output=args.output)
        ReviewWindow(root, store)
    except Exception as exc:
        messagebox.showerror("无法打开审核工具", str(exc), parent=root)
        root.destroy()
        return 1
    root.deiconify()
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
