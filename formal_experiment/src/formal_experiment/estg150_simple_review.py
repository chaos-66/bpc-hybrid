"""Small, span-safe facade for the EStG-150 Sol review screen.

The reviewer edits only the six semantic elements.  Character offsets,
normalized placeholders, relation IDs, Layer-E decisions, backups, and the
legacy workflow states stay behind this facade.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from formal_experiment.estg150_service import HumanCorrectionService


SPAN_FIELDS = ("actors", "actions", "conditions", "constraints", "exceptions")
MODALITIES = ("obligation", "prohibition", "permission", "definition")
EXPECTED_MEMBERSHIP_SHA256 = (
    "8573e105d2bc167c6aa0a92c16f79a3aaf725baadfea86f0b5d2b1ea68b1e0d7"
)


class SimpleReviewError(ValueError):
    """A concise, user-correctable problem in the simple editor."""


def _span_is_exact(span: dict, text: str, start_bound: int, end_bound: int) -> bool:
    start = span.get("start")
    end = span.get("end")
    return (
        isinstance(start, int)
        and isinstance(end, int)
        and start_bound <= start < end <= end_bound <= len(text)
        and span.get("text") == text[start:end]
    )


def validate_simple_candidate(candidate: dict) -> None:
    """Validate the exact-span invariants needed before a Layer-E save."""
    if not isinstance(candidate, dict):
        raise SimpleReviewError("候选结果不是 JSON 对象")
    sample_id = candidate.get("sample_id")
    if not isinstance(sample_id, str) or not sample_id:
        raise SimpleReviewError("候选结果缺少 sample_id")
    translation = candidate.get("translation") or {}
    text = translation.get("proposed_text_en")
    if not isinstance(text, str) or not text.strip():
        raise SimpleReviewError(f"{sample_id} 缺少英文法规文本")
    clauses = candidate.get("clauses")
    if not isinstance(clauses, list) or not clauses:
        raise SimpleReviewError(f"{sample_id} 没有提取出任何条款")

    clause_ids: set[str] = set()
    for clause_index, clause in enumerate(clauses, 1):
        clause_id = clause.get("clause_id")
        if not isinstance(clause_id, str) or not clause_id:
            raise SimpleReviewError(f"第 {clause_index} 个条款缺少 clause_id")
        if clause_id in clause_ids:
            raise SimpleReviewError(f"条款 ID 重复：{clause_id}")
        clause_ids.add(clause_id)
        clause_span = clause.get("clause_span") or {}
        if not _span_is_exact(clause_span, text, 0, len(text)):
            raise SimpleReviewError(f"{clause_id} 的条款文字无法在英文正文中精确定位")
        c_start = clause_span["start"]
        c_end = clause_span["end"]

        modality = clause.get("modality") or {}
        if modality.get("label") not in MODALITIES:
            raise SimpleReviewError(f"{clause_id} 的模态无效")
        evidence = modality.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise SimpleReviewError(f"{clause_id} 缺少模态依据")
        for span in evidence:
            if not _span_is_exact(span, text, c_start, c_end):
                raise SimpleReviewError(f"{clause_id} 的模态依据无法精确定位")

        ids: set[str] = set()
        actors: set[str] = set()
        actions: set[str] = set()
        for field in SPAN_FIELDS:
            values = clause.get(field)
            if not isinstance(values, list):
                raise SimpleReviewError(f"{clause_id} 的 {field} 不是列表")
            for span in values:
                span_id = span.get("id")
                if not isinstance(span_id, str) or not span_id or span_id in ids:
                    raise SimpleReviewError(f"{clause_id} 的要素 ID 缺失或重复")
                if not _span_is_exact(span, text, c_start, c_end):
                    raise SimpleReviewError(
                        f"{clause_id} 的“{span.get('text', '')}”无法在条款原文中精确定位"
                    )
                ids.add(span_id)
                if field == "actors":
                    actors.add(span_id)
                elif field == "actions":
                    actions.add(span_id)
        for edge in clause.get("actor_action_map") or []:
            if edge.get("actor_id") is not None and edge.get("actor_id") not in actors:
                raise SimpleReviewError(f"{clause_id} 的主体—行为关系引用了未知主体")
            if edge.get("action_id") not in actions:
                raise SimpleReviewError(f"{clause_id} 的主体—行为关系引用了未知行为")
        for edge in clause.get("order_relations") or []:
            if edge.get("before_action_id") not in actions or edge.get("after_action_id") not in actions:
                raise SimpleReviewError(f"{clause_id} 的行为顺序引用了未知行为")


def load_candidate_bundle(path: Path, *, expected_count: int = 150) -> dict:
    """Load the immutable Sol candidate bundle and enforce membership shape."""
    path = Path(path)
    if not path.exists():
        raise SimpleReviewError(f"尚未生成完整 Sol 候选文件：{path}")
    bundle = json.loads(path.read_text(encoding="utf-8"))
    if bundle.get("model") != "gpt-5.6-sol":
        raise SimpleReviewError("候选文件不是锁定的 gpt-5.6-sol 输出")
    if expected_count == 150 and bundle.get("membership_payload_sha256") != EXPECTED_MEMBERSHIP_SHA256:
        raise SimpleReviewError("Sol 候选的 150 条 membership hash 不匹配")
    records = bundle.get("records") if isinstance(bundle, dict) else None
    if not isinstance(records, list) or len(records) != expected_count:
        count = len(records) if isinstance(records, list) else 0
        raise SimpleReviewError(f"Sol 候选应为 {expected_count} 条，当前只有 {count} 条")
    ids: set[str] = set()
    for candidate in records:
        validate_simple_candidate(candidate)
        sample_id = candidate["sample_id"]
        if sample_id in ids:
            raise SimpleReviewError(f"Sol 候选 sample_id 重复：{sample_id}")
        ids.add(sample_id)
    return bundle


def _lines(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = [str(item) for item in value]
    else:
        raw = str(value or "").splitlines()
    return [line.strip() for line in raw if line.strip()]


def _occurrences(text: str, needle: str, start: int, end: int) -> list[int]:
    output: list[int] = []
    position = text.find(needle, start, end)
    while position >= 0 and position + len(needle) <= end:
        output.append(position)
        position = text.find(needle, position + 1, end)
    return output


def _rebuild_spans(
    *,
    text: str,
    clause: dict,
    field: str,
    edited_lines: list[str],
) -> tuple[list[dict], dict[str, str]]:
    c_start = clause["clause_span"]["start"]
    c_end = clause["clause_span"]["end"]
    old_spans = list(clause.get(field) or [])
    rebuilt: list[dict] = []
    old_to_new: dict[str, str] = {}
    used_ids: set[str] = set()
    singular = field[:-1] if field.endswith("s") else field
    for index, phrase in enumerate(edited_lines, 1):
        positions = _occurrences(text, phrase, c_start, c_end)
        indexed_old = old_spans[index - 1] if index <= len(old_spans) else None
        matched_old = None
        if (
            indexed_old
            and indexed_old.get("text") == phrase
            and indexed_old.get("start") in positions
        ):
            matched_old = indexed_old
            start = matched_old["start"]
        elif len(positions) == 1:
            start = positions[0]
            matched_old = next(
                (
                    old
                    for old in old_spans
                    if old.get("text") == phrase and old.get("start") == start
                ),
                None,
            )
        elif not positions:
            raise SimpleReviewError(
                f"{clause['clause_id']} 的 {singular}：正文里找不到“{phrase}”"
            )
        else:
            raise SimpleReviewError(
                f"{clause['clause_id']} 的 {singular}：“{phrase}”出现多次，请填更长一点"
            )
        old_id = matched_old.get("id") if matched_old else None
        span_id = old_id if isinstance(old_id, str) and old_id not in used_ids else None
        serial = index
        while span_id is None or span_id in used_ids:
            proposed_id = f"{clause['clause_id']}_{singular}_{serial}"
            if proposed_id not in used_ids:
                span_id = proposed_id
                break
            serial += 1
        used_ids.add(span_id)
        normalized = (
            matched_old.get("normalized")
            if matched_old and matched_old.get("normalized")
            else phrase
        )
        rebuilt.append({
            "id": span_id,
            "text": phrase,
            "start": start,
            "end": start + len(phrase),
            "normalized": normalized,
        })
        if matched_old and isinstance(matched_old.get("id"), str):
            old_to_new[matched_old["id"]] = span_id
    return rebuilt, old_to_new


def _modality_evidence(text: str, clause: dict, label: str) -> list[dict]:
    old = clause.get("modality") or {}
    if old.get("label") == label and old.get("evidence"):
        return copy.deepcopy(old["evidence"])
    cues = {
        "obligation": ("shall", "must", "is required to", "are required to"),
        "prohibition": ("shall not", "must not", "may not", "prohibited"),
        "permission": ("may", "is entitled to", "are entitled to", "can"),
        "definition": ("shall be deemed", "is deemed", "means", "refers to"),
    }[label]
    c_start = clause["clause_span"]["start"]
    c_end = clause["clause_span"]["end"]
    lowered = text.lower()
    for cue in cues:
        start = lowered.find(cue.lower(), c_start, c_end)
        if start >= 0:
            end = start + len(cue)
            return [{"text": text[start:end], "start": start, "end": end}]
    return [copy.deepcopy(clause["clause_span"])]


def rebuild_candidate(base: dict, clause_edits: list[dict]) -> dict:
    """Apply visible six-element edits and regenerate hidden exact spans."""
    candidate = copy.deepcopy(base)
    text = candidate["translation"]["proposed_text_en"]
    base_clauses = candidate.get("clauses") or []
    if len(clause_edits) != len(base_clauses):
        raise SimpleReviewError("界面条款数量与 Sol 候选不一致，请重新打开工具")

    rebuilt_clauses: list[dict] = []
    for base_clause, edits in zip(base_clauses, clause_edits):
        if edits.get("clause_id") != base_clause.get("clause_id"):
            raise SimpleReviewError("界面条款顺序发生变化，请重新打开工具")
        clause = copy.deepcopy(base_clause)
        label = edits.get("modality")
        if label not in MODALITIES:
            raise SimpleReviewError(f"{clause['clause_id']} 尚未选择模态")
        clause["modality"] = {
            "label": label,
            "evidence": _modality_evidence(text, base_clause, label),
        }

        id_maps: dict[str, str] = {}
        for field in SPAN_FIELDS:
            spans, field_map = _rebuild_spans(
                text=text,
                clause=base_clause,
                field=field,
                edited_lines=_lines(edits.get(field, "")),
            )
            clause[field] = spans
            id_maps.update(field_map)

        action_ids = [item["id"] for item in clause["actions"]]
        actions = set(action_ids)
        actors = {item["id"] for item in clause["actors"]}
        actor_action_map: list[dict] = []
        mapped_actions: set[str] = set()
        for edge in base_clause.get("actor_action_map") or []:
            action_id = id_maps.get(edge.get("action_id"))
            actor_id = (
                None if edge.get("actor_id") is None else id_maps.get(edge.get("actor_id"))
            )
            if action_id in actions and (actor_id is None or actor_id in actors):
                actor_action_map.append({"actor_id": actor_id, "action_id": action_id})
                mapped_actions.add(action_id)
        for action_id in action_ids:
            if action_id in mapped_actions:
                continue
            actor_id = next(iter(actors)) if len(actors) == 1 else None
            actor_action_map.append({"actor_id": actor_id, "action_id": action_id})
        clause["actor_action_map"] = actor_action_map

        order_relations: list[dict] = []
        for relation in base_clause.get("order_relations") or []:
            before = id_maps.get(relation.get("before_action_id"))
            after = id_maps.get(relation.get("after_action_id"))
            if before in actions and after in actions:
                order_relations.append({
                    "before_action_id": before,
                    "after_action_id": after,
                    "evidence": copy.deepcopy(
                        relation.get("evidence") or [base_clause["clause_span"]]
                    ),
                })
        clause["order_relations"] = order_relations
        rebuilt_clauses.append(clause)

    candidate["clauses"] = rebuilt_clauses
    validate_simple_candidate(candidate)
    return candidate


def layer_e_record_to_candidate(record: dict) -> dict:
    """Show an already completed Layer-E record without replacing it by Sol."""
    text = record.get("approved_text_en") or record.get("candidate_text_en") or ""
    output_clauses: list[dict] = []
    for human_clause in (record.get("human_correction") or {}).get("clauses") or []:
        clause_span = copy.deepcopy(human_clause.get("clause_span") or {})
        modality = human_clause.get("modality") or {}
        evidence = modality.get("span")
        if not isinstance(evidence, dict) or not _span_is_exact(
            evidence,
            text,
            clause_span.get("start", 0),
            clause_span.get("end", len(text)),
        ):
            evidence = copy.deepcopy(clause_span)
        clause = {
            "clause_id": human_clause.get("clause_id"),
            "clause_span": clause_span,
            "modality": {"label": modality.get("value"), "evidence": [evidence]},
            "actors": [],
            "actions": [],
            "conditions": [],
            "constraints": [],
            "exceptions": [],
            "actor_action_map": copy.deepcopy(human_clause.get("actor_action_map") or []),
            "order_relations": [],
        }
        for field in SPAN_FIELDS:
            clause[field] = [
                {
                    "id": span["id"],
                    "text": span["text"],
                    "start": span["start"],
                    "end": span["end"],
                    "normalized": span["text"],
                }
                for span in human_clause.get(field) or []
            ]
        for relation in human_clause.get("order_relations") or []:
            copied = copy.deepcopy(relation)
            copied["evidence"] = copied.get("evidence") or [copy.deepcopy(clause_span)]
            clause["order_relations"].append(copied)
        output_clauses.append(clause)
    candidate = {
        "schema_version": "estg150_ai_review_model_output@1.0.0",
        "sample_id": record["sample_id"],
        "context_sufficiency": "uncertain",
        "translation": {
            "decision": "accepted" if text == record.get("candidate_text_en") else "edited",
            "proposed_text_en": text,
            "issues": [],
        },
        "clauses": output_clauses,
        "unsupported_or_ambiguous": [],
        "confidence": "high",
        "rationale_summary": "Previously saved user result.",
    }
    validate_simple_candidate(candidate)
    return candidate


class SimpleReviewSession:
    """Navigation and one-click persistence used by the Tk shell."""

    def __init__(self, service: HumanCorrectionService, candidate_bundle: dict):
        self.service = service
        self.bundle = candidate_bundle
        self.sol_candidates = {
            candidate["sample_id"]: candidate for candidate in candidate_bundle["records"]
        }
        self.sample_ids = [candidate["sample_id"] for candidate in candidate_bundle["records"]]
        layer_e_ids = {record["sample_id"] for record in service.records}
        if set(self.sample_ids) != layer_e_ids:
            raise SimpleReviewError("Sol 候选与现有 150 条 Layer E 成员不一致")

    def candidate_for(self, sample_id: str) -> dict:
        record = self.service.get_record(sample_id)
        if record is None:
            raise SimpleReviewError(f"Layer E 找不到 {sample_id}")
        status = (record.get("review_state") or {}).get("status")
        clauses = (record.get("human_correction") or {}).get("clauses") or []
        if status in ("reviewed", "adjudicated") and clauses:
            return layer_e_record_to_candidate(record)
        return copy.deepcopy(self.sol_candidates[sample_id])

    def is_done(self, sample_id: str) -> bool:
        record = self.service.get_record(sample_id) or {}
        return (record.get("review_state") or {}).get("status") == "adjudicated"

    def progress(self) -> tuple[int, int]:
        return sum(self.is_done(sample_id) for sample_id in self.sample_ids), len(self.sample_ids)

    def next_unfinished_index(self, current_index: int, *, include_current: bool = False) -> int:
        total = len(self.sample_ids)
        start = current_index if include_current else current_index + 1
        for offset in range(total):
            index = (start + offset) % total
            if not self.is_done(self.sample_ids[index]):
                return index
        return current_index

    def save_and_finish(self, sample_id: str, clause_edits: list[dict]) -> dict:
        base = self.candidate_for(sample_id)
        candidate = rebuild_candidate(base, clause_edits)
        result = self.service.apply_simple_review_candidate(
            sample_id,
            candidate,
            candidate_source=self.bundle.get("run_id", "codex_internal_gpt56sol_full150_v1"),
        )
        if not result.get("ok"):
            raise SimpleReviewError("；".join(result.get("errors") or ["保存失败"]))
        saved = self.service.save_draft()
        validation = saved.get("validation") or {}
        if validation.get("format_valid") is False:
            raise SimpleReviewError("文件已保存，但全局格式检查未通过；请查看项目日志")
        return {**result, "saved": saved}


__all__ = [
    "MODALITIES",
    "SPAN_FIELDS",
    "SimpleReviewError",
    "SimpleReviewSession",
    "layer_e_record_to_candidate",
    "load_candidate_bundle",
    "rebuild_candidate",
    "validate_simple_candidate",
]
