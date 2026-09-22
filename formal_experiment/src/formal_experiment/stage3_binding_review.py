"""Local human decisions over the AI-reviewed Stage 3 proposal; never Gold."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "outputs/reports/stage3_binding_annotation_agent_review_v1.json"
BLANK = ROOT / "data/development/stage3_synth/stage3_binding_annotation_blank_v1.json"
OUTPUT = ROOT / "data/development/human_review/stage3_binding_review_decisions_v1.json"
SCHEMA = "stage3_binding_human_review@1.0.0"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class BindingReviewStore:
    def __init__(self, source=SOURCE, blank=BLANK, output=OUTPUT):
        self.source, self.blank, self.output = map(lambda p: Path(p).resolve(), (source, blank, output))
        if self.output in {self.source, self.blank} or self.output.is_relative_to(ROOT / "data/gold"):
            raise ValueError("审核结果必须另存，不能覆盖来源或 Gold。")
        self.report, self.context = read_json(self.source), read_json(self.blank)
        if self.report.get("schema_version") != "stage3_binding_annotation_agent_review@1.0.0":
            raise ValueError("不是支持的 AI 审核稿。")
        self.source_hashes = {"proposal_sha256": digest(self.source), "blank_sha256": digest(self.blank)}
        self.items = self.report["items"]
        self.by_id = {row["pair_id"]: row for row in self.items}
        self.contexts = {row["pair_id"]: row["immutable_context"] for row in self.context["items"]}
        if len(self.by_id) != len(self.items) or set(self.by_id) != set(self.contexts):
            raise ValueError("审核稿与原始 30 项范围不一致。")
        self.document = {
            "schema_version": SCHEMA, "status": "in_progress", "is_gold": False,
            "source": dict(self.source_hashes), "reviewed_count": 0,
            "total_count": len(self.items), "last_pair_id": self.items[0]["pair_id"],
            "records": {},
        }
        self.loaded_output_hash = digest(self.output) if self.output.exists() else None
        if self.output.exists():
            self.document = read_json(self.output)
            if (self.document.get("schema_version") != SCHEMA
                    or self.document.get("source") != self.source_hashes
                    or self.document.get("is_gold") is not False):
                raise ValueError("已有进度与当前审核稿不匹配，请保留该文件并检查版本。")
            records = self.document.get("records")
            if not isinstance(records, dict) or not set(records).issubset(self.by_id):
                raise ValueError("进度含未知条目。")
            for pair, rec in records.items():
                if rec.get("choice") not in {"accept", "reject"} or rec.get("review_state") != "reviewed":
                    raise ValueError("进度中的人工决定无效。")
                self.validate(pair, rec["values"])
                if not isinstance(rec.get("note"), str):
                    raise ValueError("进度中的备注无效。")
            self._summarize(self.document)
        for row in self.items:
            self.validate(row["pair_id"], self.suggested(row["pair_id"]))

    def suggested(self, pair):
        row = self.by_id[pair]
        prop = row["recommended_proposal"]
        ends = row["agent_review"].get("order_endpoint_suggestions", {})
        return {
            "action_id": prop["action_binding_proposal"]["rule_action_id"],
            "actor_id": prop["actor_binding_proposal"]["rule_actor_id"],
            "process_actor": row["agent_review"]["suggested_process_actor"],
            "expected_lane_id": prop["actor_binding_proposal"]["candidate_lane"],
            "order_scope": "process_only" if row["target_violation_type"] == "out_of_order" else "not_applicable",
            "order_before_action_id": ends.get("before_rule_action_id"),
            "order_after_action_id": ends.get("after_rule_action_id"),
        }

    def current(self, pair):
        rec = self.document["records"].get(pair)
        return copy.deepcopy(rec["values"] if rec else self.suggested(pair))

    def validate(self, pair, values):
        if pair not in self.by_id:
            raise ValueError("未知条目。")
        expected = self.suggested(pair)
        if not isinstance(values, dict) or set(values) != set(expected):
            raise ValueError("审核字段不完整。")
        side = self.contexts[pair]["rule_side"]
        actions = {s["id"] for s in side["actions"]}
        actors = {s["id"] for s in side["actors"]}
        for field in ("action_id", "order_before_action_id", "order_after_action_id"):
            if values[field] is not None and values[field] not in actions:
                raise ValueError("动作必须选自本条法规，或者保留为空。")
        if values["actor_id"] is not None and values["actor_id"] not in actors:
            raise ValueError("执行者引用必须选自本条法规，或者保留为空。")
        if not isinstance(values["process_actor"], str) or len(values["process_actor"]) > 300:
            raise ValueError("执行者文字不能超过 300 字。")
        if values["expected_lane_id"] != expected["expected_lane_id"]:
            raise ValueError("原流程 lane 定位不能改变。")
        if expected["order_scope"] == "not_applicable":
            if values["order_scope"] != "not_applicable" or any(values[k] for k in ("order_before_action_id", "order_after_action_id")):
                raise ValueError("本条没有顺序审核。")
        elif values["order_scope"] not in {"process_only", "rule_order", "rejected"}:
            raise ValueError("顺序审核选项无效。")
        if values["order_scope"] == "rule_order":
            first, last = values["order_before_action_id"], values["order_after_action_id"]
            if not first or not last or first == last:
                raise ValueError("确认法规顺序时，需要两个不同且非空的规则动作。")

    @staticmethod
    def _summarize(doc):
        doc["reviewed_count"] = len(doc["records"])
        doc["status"] = "human_review_complete" if doc["reviewed_count"] == doc["total_count"] else "in_progress"
        doc["accepted_count"] = sum(r["choice"] == "accept" for r in doc["records"].values())
        doc["rejected_count"] = sum(r["choice"] == "reject" for r in doc["records"].values())
        # Completion is human review completion, not a claim of complete bindings.
        doc["accepted_missing_action_count"] = sum(r["choice"] == "accept" and r["values"]["action_id"] is None for r in doc["records"].values())
        doc["accepted_missing_actor_span_count"] = sum(r["choice"] == "accept" and r["values"]["actor_id"] is None for r in doc["records"].values())

    def resume_index(self):
        return next((i for i, row in enumerate(self.items) if row["pair_id"] not in self.document["records"]), 0)

    def next_pending(self, current):
        size = len(self.items)
        return next((i for step in range(1, size + 1)
                     if self.items[i := (current + step) % size]["pair_id"] not in self.document["records"]), None)

    def save(self, pair, choice, values, note=""):
        if choice not in {"accept", "reject"}:
            raise ValueError("必须明确选择确认或不接受。")
        self.validate(pair, values)
        if not isinstance(note, str) or len(note) > 10000:
            raise ValueError("备注过长。")
        if digest(self.source) != self.source_hashes["proposal_sha256"] or digest(self.blank) != self.source_hashes["blank_sha256"]:
            raise ValueError("来源已变化，未保存；请重新打开工具核对。")
        now_hash = digest(self.output) if self.output.exists() else None
        if now_hash != self.loaded_output_hash:
            raise ValueError("进度已被另一个窗口修改，未覆盖。请关闭本窗口后重新打开。")
        doc = copy.deepcopy(self.document)
        stamp = datetime.now(timezone.utc).isoformat()
        row = self.by_id[pair]
        action_text = next((s["text"] for s in self.contexts[pair]["rule_side"]["actions"] if s["id"] == values["action_id"]), None)
        actor_text = next((s["text"] for s in self.contexts[pair]["rule_side"]["actors"] if s["id"] == values["actor_id"]), None)
        doc["records"][pair] = {
            "pair_id": pair, "choice": choice,
            "decision": "rejected" if choice == "reject" else ("accepted" if values == self.suggested(pair) else "edited"),
            "review_state": "reviewed", "values": copy.deepcopy(values), "note": note,
            "action_text": action_text, "actor_span_text": actor_text,
            "process_id": row["process_id"], "rule_id": row["rule_id"],
            "target_activity_id": row["target_activity_id"], "target_activity_name": row["target_activity_name"],
            "process_order": copy.deepcopy(row["recommended_proposal"]["order_relation_proposal"]),
            "reviewed_at": stamp, "decision_source": "human_local_ui",
        }
        doc["last_pair_id"], doc["updated_at"] = pair, stamp
        self._summarize(doc)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        if self.output.exists():
            backup_dir = self.output.parent / "stage3_binding_review_backups"
            backup_dir.mkdir(exist_ok=True)
            backup = backup_dir / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid4().hex + ".json")
            backup.write_bytes(self.output.read_bytes())
        payload = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.output.parent, prefix=self.output.name + ".", suffix=".tmp", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                tmp.write(payload)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_path, self.output)
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()
        self.document, self.loaded_output_hash = doc, digest(self.output)
