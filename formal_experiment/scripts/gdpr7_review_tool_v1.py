# -*- coding: utf-8 -*-
"""Interactive human-adjudication tool for the GDPR7 six-element review (v2).

The ONLY interactive editing entry point of the workflow.  It operates on the
editable document — by default the v2 file
(``data/development/human_review/gdpr7_six_element_review_decisions_v2.json``,
schema ``gdpr7_six_element_review_editable@1.1.0``) — and NEVER touches the
blank surface file.  Only a human reviewer may set decisions: the tool only
displays the sentence, the development-only candidate and the review state,
then records exactly what the reviewer types.

Commands (mutually exclusive actions):

    --file <path>        editable document to operate on (default above)
    --list               one-line summary of every sentence
    --progress           aggregate progress (total/reviewed/decided fields/...)
    --show <sample_id>   print one sentence with candidate and current review
    --edit <sample_id>   interactive adjudication of one sentence
    --next               interactive adjudication of the first unreviewed
                         sentence (document order)

v1 editable files (schema ``gdpr7_six_element_review_editable@1.0.0``) can be
opened read-only (``--list`` / ``--progress`` / ``--show``); editing commands
on a v1 file are refused with an upgrade hint.

Interactive editing rules (v2):

* per legacy field, the reviewer answers one of::

      a                 accept the candidate value ("无" accepted when the
                        candidate is null and the sentence indeed has none)
      r                 reject (the sentence has no such element)
      e:<value>         edited with an explicit new value
      (empty)           skip / leave as-is

* modality ``edited_value`` must be one of the four controlled labels
  (definition/obligation/permission/prohibition); the five text fields
  (actor/action/condition/constraint/exception) must be a verbatim contiguous
  substring of the sentence text — an invalid value is reported immediately
  and re-prompted, never stored;
* after the six legacy fields, when the legacy six are fully decided, the tool
  asks whether the sentence contains ADDITIONAL normative elements (multiple
  actions / multiple actors) or needs explicit actor-action bindings / action
  ordering.  On ``y`` the sentence becomes *structured*:
  - ``rule_items[0]`` mirrors the legacy six blocks (exact copy, item_id
    ``<sample_id>.i1``) and is kept in sync by the tool;
  - further items (i2, i3, ...) are added one at a time; each item carries its
    own six blocks: modality must be one of the four labels (``e:<label>``);
    the five text fields accept ``e:<verbatim value>`` / ``r`` (该元素在本项
    不存在/不适用) / empty (暂未决定 — the block stays null and the sentence
    remains unreviewed until every block of every item is decided);
  - an item with NO decided block at all is not appended (an empty placeholder
    is meaningless);
  - after the items the reviewer may enter explicit ``actor_action_map`` lines
    (format ``i1.actor>i2.action``, empty line ends; the within-item 1:1
    binding is implicit and needs no entry) and ``order_relations`` lines
    (format ``i1>i2`` = item i1's action precedes item i2's action; empty line
    = none);
* re-editing the same sentence (``--edit`` again) lets the reviewer change the
  legacy six blocks (the i1 mirror is re-synchronised automatically), add more
  items, edit an existing item's blocks (``e<n>``), delete the last item
  (``di``) or re-enter the relations (``rr``);
* then ``s`` saves and continues to the next unreviewed sentence, ``q`` saves
  the current progress and quits.  Every save first re-validates every
  sentence with the shared v2 rules: if anything is illegal the save is
  REFUSED and nothing is written;
* saving automatically recomputes ``review_state`` (reviewed only when the
  sentence is v2-complete: every legacy field AND every rule_item block is
  decided and legal), recomputes the document status, and atomically replaces
  the file after copying the previous content to ``<file>.bak``.

Zero LLM/API/network.  Console I/O: prompts via ``print``, answers via
``input()``; stdout/stderr are best-effort reconfigured to UTF-8 for Windows
consoles.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.gdpr7_review_rules_v1 import (  # noqa: E402
    ALL_FIELDS,
    DEFAULT_EDITABLE_V2_PATH,
    DECISION_VALUES,
    MODALITY_LABELS,
    SCHEMA_EDITABLE,
    SCHEMA_EDITABLE_V2,
    TEXT_FIELDS,
    atomic_save_json,
    collect_stats,
    collect_stats_v2,
    is_verbatim_substring,
    load_json,
    recompute_doc_status_v2,
    recompute_sentence_review_state_v2,
    validate_field_decision,
    validate_sentence_review_v2,
)

FIELD_LABELS_ZH = {
    "modality": "规范力(modality)",
    "actor": "主体(actor)",
    "action": "行为(action)",
    "condition": "条件(condition)",
    "constraint": "约束(constraint)",
    "exception": "例外(exception)",
}


def _setup_console() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover - non-reconfigurable stream
        pass


def _load_doc(path: Path) -> dict[str, Any]:
    try:
        doc = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法加载文件 {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise SystemExit(f"文件不是对象: {path}")
    return doc


def _schema_of(doc: dict[str, Any]) -> Any:
    return doc.get("schema_version") if isinstance(doc, dict) else None


def _is_v2(doc: dict[str, Any]) -> bool:
    return _schema_of(doc) == SCHEMA_EDITABLE_V2


# ---------------------------------------------------------------------------
# Pure presentation helpers (unit-testable, no console I/O)
# ---------------------------------------------------------------------------


def iter_sentences(doc: dict[str, Any]):
    """Yield ``(one_based_index, rule_id, sentence)`` in document order."""
    idx = 0
    for rule in doc.get("rules", []) or []:
        if not isinstance(rule, dict):
            continue
        rid = rule.get("rule_id")
        for sentence in rule.get("sentences", []) or []:
            if not isinstance(sentence, dict):
                continue
            idx += 1
            yield idx, rid, sentence


def find_sentence(doc: dict[str, Any], sample_id: str):
    """Return ``(one_based_index, rule_id, sentence)`` or None."""
    for idx, rid, sentence in iter_sentences(doc):
        if sentence.get("sample_id") == sample_id:
            return idx, rid, sentence
    return None


def compute_progress(doc: dict[str, Any]) -> dict[str, Any]:
    """Pure progress summary over ``doc`` (see :func:`collect_stats_v2`)."""
    stats = collect_stats_v2(doc)
    return {
        "sentences_total": stats["sentences_total"],
        "reviewed": stats["reviewed"],
        "unreviewed": stats["unreviewed"],
        "decisions_total": stats["decisions_total"],
        "fields_total": stats["fields_total"],
        "remaining_unreviewed": stats["unreviewed"],
        "per_field_decided": stats["per_field_decided"],
        "items_total": stats["items_total"],
        "structured_sentences": stats["structured_sentences"],
        "actor_action_map_total": stats["actor_action_map_total"],
        "order_relations_total": stats["order_relations_total"],
    }


def progress_lines(doc: dict[str, Any]) -> list[str]:
    """Human-readable Chinese progress lines (pure; used by ``--progress``)."""
    p = compute_progress(doc)
    line = (
        f"总句数={p['sentences_total']}；"
        f"reviewed={p['reviewed']}；unreviewed={p['unreviewed']}；"
        f"已决字段={p['decisions_total']}/{p['fields_total']}；"
        f"剩余 unreviewed 句数={p['remaining_unreviewed']}"
    )
    if p.get("items_total"):
        line += (
            f"；结构化句={p['structured_sentences']} "
            f"rule_items={p['items_total']} "
            f"aam={p['actor_action_map_total']} "
            f"orders={p['order_relations_total']}"
        )
    return [line]


def list_lines(doc: dict[str, Any]) -> list[str]:
    """One line per sentence (pure; used by ``--list``)."""
    total = len(list(iter_sentences(doc)))
    lines = [f"schema={doc.get('schema_version')} dataset_id={doc.get('dataset_id')} "
             f"status={doc.get('status')}"]
    for idx, rid, sentence in iter_sentences(doc):
        review = sentence.get("review", {})
        decided = sum(
            1 for f in ALL_FIELDS
            if isinstance(review.get(f), dict)
            and review.get(f, {}).get("decision") in DECISION_VALUES
        )
        item_note = ""
        if isinstance(review.get("rule_items"), list):
            item_note = f" items={len(review['rule_items'])}"
        lines.append(
            f"[{idx}/{total}] {sentence.get('sample_id')} ({rid}) "
            f"state={review.get('review_state')} decided={decided}/6{item_note}"
        )
    return lines


def candidate_display(value: Any, kind: Any = None) -> str:
    """Candidate value display: None -> 「无」; kind appended when present."""
    if value is None:
        text = "「无」"
    else:
        text = str(value)
    if kind is not None:
        text += f" (kind={kind})"
    return text


def show_lines(doc: dict[str, Any], sample_id: str) -> Optional[list[str]]:
    """Detailed display of one sentence (pure; used by ``--show``)."""
    found = find_sentence(doc, sample_id)
    if found is None:
        return None
    idx, rid, sentence = found
    review = sentence.get("review", {})
    candidate = sentence.get("candidate", {})
    lines = [
        f"[{idx}/{len(list(iter_sentences(doc)))}] {sample_id} (规则 {rid})",
        f"review_state={review.get('review_state')} notes={review.get('notes')!r}",
        f"原文: {sentence.get('sentence_text')}",
        f"candidate_source={candidate.get('candidate_source')} "
        f"is_gold={candidate.get('is_gold')}",
    ]
    for field in ALL_FIELDS:
        cand_val = candidate.get(field)
        kind = None
        if field == "constraint":
            kind = candidate.get("constraint_kind")
        elif field == "exception":
            kind = candidate.get("exception_kind")
        entry = review.get(field, {}) if isinstance(review, dict) else {}
        decision = entry.get("decision")
        edited = entry.get("edited_value")
        current = "未决"
        if decision in DECISION_VALUES:
            current = decision if edited is None else f"{decision}: {edited!r}"
        lines.append(
            f"  {FIELD_LABELS_ZH[field]}: 候选={candidate_display(cand_val, kind)} "
            f"| 当前={current}"
        )
    items = review.get("rule_items") if isinstance(review, dict) else None
    if isinstance(items, list):
        lines.append(f"  rule_items: {len(items)} 项")
        for item in items:
            if not isinstance(item, dict):
                continue
            parts = []
            for field in ALL_FIELDS:
                entry = item.get(field)
                if not isinstance(entry, dict):
                    parts.append(f"{field}=?")
                    continue
                decision = entry.get("decision")
                edited = entry.get("edited_value")
                if decision in DECISION_VALUES:
                    parts.append(f"{field}={decision}"
                                 if edited is None
                                 else f"{field}={decision}:{edited!r}")
                else:
                    parts.append(f"{field}=未决")
            lines.append(f"    {item.get('item_id')}: " + " | ".join(parts))
    aam = review.get("actor_action_map") if isinstance(review, dict) else None
    if isinstance(aam, list) and aam:
        lines.append("  actor_action_map: " + ", ".join(
            f"{e.get('actor_item_id')}.actor>{e.get('action_item_id')}.action"
            for e in aam if isinstance(e, dict)))
    orders = review.get("order_relations") if isinstance(review, dict) else None
    if isinstance(orders, list) and orders:
        lines.append("  order_relations: " + ", ".join(
            f"{e.get('before_item_id')}>{e.get('after_item_id')}"
            for e in orders if isinstance(e, dict)))
    return lines


# ---------------------------------------------------------------------------
# Pure input parsers (unit-testable, no console I/O)
# ---------------------------------------------------------------------------

# accepted shorthand for one relation line: 'i1.actor>i2.action'
_RELATION_AAM_RE = re.compile(r"^i([1-9][0-9]*)\.actor\s*>\s*i([1-9][0-9]*)\.action$")
# order relation line: 'i1>i2'
_RELATION_ORDER_RE = re.compile(r"^i([1-9][0-9]*)\s*>\s*i([1-9][0-9]*)$")


def parse_aam_line(line: str, sample_id: str) -> tuple[Optional[dict], Optional[str]]:
    """Parse one explicit actor_action_map answer.

    Expected format ``i1.actor>i2.action`` (references the rule_item ids of
    the current sentence; only the ``i<n>`` part is typed).  Returns
    ``(entry, None)`` with ``entry = {"actor_item_id": "<sample_id>.i1",
    "action_item_id": "<sample_id>.i2"}`` or ``(None, error_text)``.
    """
    stripped = (line or "").strip()
    if not stripped:
        return (None, "空行：无输入")
    m = _RELATION_AAM_RE.match(stripped)
    if not m:
        return (None, "无法识别的 actor_action_map：格式应为 i1.actor>i2.action")
    left, right = int(m.group(1)), int(m.group(2))
    if left == right:
        return (None, "actor 与 action 指向同一项（自环）；项内 1:1 为隐含默认，"
                      "无需显式声明")
    return (
        {"actor_item_id": f"{sample_id}.i{left}",
         "action_item_id": f"{sample_id}.i{right}"},
        None,
    )


def parse_order_line(line: str, sample_id: str) -> tuple[Optional[dict], Optional[str]]:
    """Parse one order_relations answer (format ``i1>i2``).

    Returns ``(entry, None)`` with ``entry = {"before_item_id":
    "<sample_id>.i1", "after_item_id": "<sample_id>.i2"}`` or
    ``(None, error_text)``.
    """
    stripped = (line or "").strip()
    if not stripped:
        return (None, "空行：无输入")
    m = _RELATION_ORDER_RE.match(stripped)
    if not m:
        return (None, "无法识别的 order_relations：格式应为 i1>i2")
    left, right = int(m.group(1)), int(m.group(2))
    if left == right:
        return (None, "before 与 after 指向同一项（自环）")
    return (
        {"before_item_id": f"{sample_id}.i{left}",
         "after_item_id": f"{sample_id}.i{right}"},
        None,
    )


# ---------------------------------------------------------------------------
# Interactive editing
# ---------------------------------------------------------------------------


def _prompt(prompt_text: str) -> str:
    return input(prompt_text)


def _parse_decision_answer(answer: str, field: str, sentence_text: str,
                           candidate_value: Any) -> Optional[tuple[str, Any, str]]:
    """Interpret one field answer -> ``(decision, edited_value, error_text)``.

    Returns ``(None, None, "")`` for an empty (skip) answer; on invalid input
    returns ``(None, None, error_text)`` so the caller can re-prompt.
    """
    stripped = answer.strip()
    if not stripped:
        return (None, None, "")
    lowered = stripped.casefold()
    if lowered in ("a", "accepted", "accept"):
        return ("accepted", None, "")
    if lowered in ("r", "rejected", "reject"):
        return ("rejected", None, "")
    edited_value: Optional[str] = None
    if lowered in ("e", "edited"):
        edited_value = _prompt(f"  请输入 {field} 的修正值（原句逐字连续片段）: ")
    elif ":" in stripped:
        prefix, _, value = stripped.partition(":")
        if prefix.casefold() in ("e", "edited"):
            edited_value = value.lstrip(" ")
    if edited_value is not None:
        if not edited_value:
            return (None, None, "edited 需要非空值；已忽略本次输入，请重新输入")
        if field == "modality":
            if edited_value not in MODALITY_LABELS:
                return (None, None,
                        f"modality 修正值必须属于 {MODALITY_LABELS}；已忽略本次输入，"
                        f"请重新输入")
        else:
            if not is_verbatim_substring(edited_value, sentence_text):
                return (None, None,
                        f"{edited_value!r} 不是原句的逐字连续子串；已忽略本次输入，"
                        f"请重新输入")
        return ("edited", edited_value, "")
    return (None, None, "无法识别的输入：请输入 a / r / e:<新值>，或直接回车跳过")


def _ask_one_block(sentence: dict[str, Any], field: str, entry: dict[str, Any],
                   mode: str, item_label: str = "") -> Optional[str]:
    """Ask ONE six-element block.

    ``mode``:

    * ``"legacy"`` — accepts a / r / e:<value> / empty (skip = keep as-is);
    * ``"item"`` — a new rule_item block must be EXPLICITLY decided
      (modality: ``e:<label>``; text fields: ``e:<verbatim>`` / ``r``);
      empty input aborts adding the current item (returns ``"abort"``).  Item
      blocks never accept the sentence candidate verbatim because the
      candidate value describes the whole sentence (the i1 mirror covers it).

    Mutates ``entry`` in place.  Returns ``None`` on success (or a legitimate
    skip), ``"abort"`` to abandon the whole item, otherwise an error text to
    re-prompt with.
    """
    sentence_text = sentence.get("sentence_text", "") or ""
    candidate = sentence.get("candidate", {}) or {}
    cand_val = candidate.get(field)
    label = FIELD_LABELS_ZH[field]
    tag = f"{item_label}{label}" if item_label else label
    hint = f"候选={candidate_display(cand_val)}"
    if field == "modality":
        hint += f"  (修正值限 {MODALITY_LABELS})"
    else:
        hint += "  (修正值须为原句逐字连续片段)"
    current = "未决"
    if entry.get("decision") in DECISION_VALUES:
        current = entry["decision"]
        if entry.get("edited_value") is not None:
            current += f": {entry['edited_value']!r}"
    print(f"[{tag}] 当前={current} | {hint}")

    while True:
        if mode == "legacy":
            usage = "a=接受候选 / r=拒绝(句中无此要素) / e:<新值> / 回车=跳过"
        elif mode == "item":
            if field == "modality":
                usage = "e:<标签>(4类之一) / 回车=取消添加该项"
            else:
                usage = "e:<逐字值> / r=本项无此要素 / 回车=取消添加该项"
        else:  # item_review (re-edit an existing block)
            if field == "modality":
                usage = "e:<标签>(4类之一) / 回车=保持原值"
            else:
                usage = "e:<逐字值> / r=本项无此要素 / 回车=保持原值"
        answer = _prompt(f"  {tag} 决定: {usage} -> ")
        if not answer.strip():
            if mode == "item":
                return "abort"  # 未决 -> 不写入半成品项
            return None  # legacy / item_review skip: keep the previous value
        decision, edited_value, error_text = _parse_decision_answer(
            answer, field, sentence_text, cand_val)
        if error_text:
            print(f"  !! {error_text}")
            continue
        if decision is None and mode == "legacy":
            return None
        if decision is None:  # item mode empty was handled above
            print("  !! 该项块必须显式给出决定（e:<值> 或 r）；"
                  "如想放弃该项请直接回车")
            continue
        if mode == "item":
            if decision == "accepted":
                print("  !! 新 rule_item 的块不能 a=接受候选（候选值属整句/legacy）"
                      "；请输入 e:<逐字值> 或 r")
                continue
            if field == "modality" and decision != "edited":
                print("  !! 新 rule_item 的 modality 必须为四类标签之一"
                      "（e:<标签>）")
                continue
        ok, ferr = validate_field_decision(
            field, decision, edited_value, sentence_text)
        if not ok:
            print("  !! " + "；".join(ferr))
            continue
        entry["decision"] = decision
        entry["edited_value"] = edited_value
        return None


def _item_id_list(sentence: dict[str, Any]) -> list[str]:
    review = sentence.get("review", {})
    items = review.get("rule_items")
    if not isinstance(items, list):
        return []
    return [it.get("item_id") for it in items if isinstance(it, dict)]


def _new_blank_block() -> dict[str, Any]:
    return {"decision": None, "edited_value": None}


def _mirror_legacy_as_i1(sentence: dict[str, Any]) -> dict[str, Any]:
    """Build the rule_items[0] mirror of the legacy six blocks."""
    review = sentence.get("review", {})
    item: dict[str, Any] = {"item_id": f"{sentence.get('sample_id')}.i1"}
    for field in ALL_FIELDS:
        legacy = review.get(field)
        if isinstance(legacy, dict):
            item[field] = {
                "decision": legacy.get("decision"),
                "edited_value": legacy.get("edited_value"),
            }
        else:
            item[field] = _new_blank_block()
    return item


def _sync_mirror(sentence: dict[str, Any]) -> None:
    """Re-sync rule_items[0] (if present) with the legacy six blocks."""
    review = sentence.get("review")
    if not isinstance(review, dict):
        return
    items = review.get("rule_items")
    if not isinstance(items, list) or not items:
        return
    if not isinstance(items[0], dict):
        return
    items[0] = _mirror_legacy_as_i1(sentence)
    review["rule_items"] = items


def _enter_relations(sentence: dict[str, Any]) -> None:
    """Interactively (re-)enter explicit actor_action_map / order_relations."""
    review = sentence.get("review", {})
    valid_ids = set(_item_id_list(sentence))
    sample_id = sentence.get("sample_id", "")
    print("\n显式执行者-动作关联（actor_action_map）—— 空行结束：")
    print("  格式: i1.actor>i2.action（actor 项 > action 项；项内 1:1 为隐含默认，"
          "无需填写）")
    aam: list[dict[str, Any]] = []
    while True:
        line = _prompt("  aam> ")
        if not line.strip():
            break
        entry, err = parse_aam_line(line, sample_id)
        if err:
            print(f"  !! {err}")
            continue
        if entry["actor_item_id"] not in valid_ids \
                or entry["action_item_id"] not in valid_ids:
            print("  !! 引用不存在的 rule_item id；当前 ids = "
                  f"{sorted(valid_ids)}")
            continue
        aam.append(entry)
    review["actor_action_map"] = aam if aam else None

    print("\n动作先后（order_relations）—— 空行结束（=无顺序声明）：")
    print("  格式: i1>i2（i1 的动作先于 i2）")
    orders: list[dict[str, Any]] = []
    while True:
        line = _prompt("  order> ")
        if not line.strip():
            break
        entry, err = parse_order_line(line, sample_id)
        if err:
            print(f"  !! {err}")
            continue
        if entry["before_item_id"] not in valid_ids \
                or entry["after_item_id"] not in valid_ids:
            print("  !! 引用不存在的 rule_item id；当前 ids = "
                  f"{sorted(valid_ids)}")
            continue
        orders.append(entry)
    review["order_relations"] = orders if orders else None


def _add_rule_item(sentence: dict[str, Any]) -> None:
    """Interactively add ONE additional rule_item (iN+1).

    Every one of the six blocks must be explicitly decided (modality via
    ``e:<label>``; text fields via ``e:<verbatim value>`` or ``r``).  Pressing
    Enter on any block aborts adding the whole item (a partially decided item
    is never persisted: entering structured mode means the item is fully
    decided).
    """
    review = sentence.get("review", {})
    items = review.get("rule_items")
    if not isinstance(items, list):
        items = [_mirror_legacy_as_i1(sentence)]
        review["rule_items"] = items
    n = len(items) + 1
    item_id = f"{sentence.get('sample_id')}.i{n}"
    print(f"\n新增 rule_item {item_id}（六块全部显式决定；modality 用 "
          f"e:<标签>，文本块用 e:<逐字值> 或 r=本项无此要素；任一块回车=取消本项）")
    item: dict[str, Any] = {"item_id": item_id}
    for field in ALL_FIELDS:
        block = _new_blank_block()
        result = _ask_one_block(sentence, field, block, mode="item",
                                item_label=f"{item_id} ")
        if result == "abort":
            print(f"  已取消添加 {item_id}（未决块不写入）。")
            return
        item[field] = block
    items.append(item)
    review["rule_items"] = items
    print(f"已添加 {item_id}（六块全决）。")


def _edit_one_item(sentence: dict[str, Any]) -> None:
    """Re-answer one existing rule_item's six blocks."""
    review = sentence.get("review", {})
    items = review.get("rule_items")
    if not isinstance(items, list) or not items:
        print("没有可编辑的 rule_item。")
        return
    ids = _item_id_list(sentence)
    print("当前 rule_item ids: " + (", ".join(ids) if ids else "无"))
    answer = _prompt("要编辑的项（如 i2，回车取消）: ").strip()
    if not answer:
        return
    sample_id = sentence.get("sample_id")
    target = None
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("item_id")
        if item_id == answer or item_id == f"{sample_id}.{answer}":
            target = item
            break
    if target is None:
        print(f"未知 item_id: {answer}")
        return
    item_id = target.get("item_id")
    if item_id == f"{sample_id}.i1":
        print("i1 是 legacy 六块的镜像，请在 legacy 六块中编辑（保存时自动同步）。")
        return
    for field in ALL_FIELDS:
        block = target.get(field)
        if not isinstance(block, dict):
            block = _new_blank_block()
            target[field] = block
        _ask_one_block(sentence, field, block, mode="item_review",
                       item_label=f"{item_id} ")


def _structured_menu(sentence: dict[str, Any]) -> None:
    """Loop: add/edit/delete rule_items and relations."""
    review = sentence.setdefault("review", {})
    while True:
        ids = _item_id_list(sentence)
        state = sentence.get("review", {}).get("review_state", "?")
        print(f"\n[结构化] 当前 rule_items={ids or '无'} review_state={state}")
        cmd = _prompt(
            "命令: a=新增项 / e=编辑某项 / di=删除最后一项 / rr=重输关系 "
            "/ 回车=结束 -> ").strip().casefold()
        if not cmd:
            return
        if cmd == "a":
            _add_rule_item(sentence)
        elif cmd == "e":
            _edit_one_item(sentence)
        elif cmd == "di":
            items = review.get("rule_items")
            if isinstance(items, list) and items:
                removed = items.pop()
                if not items:
                    review["rule_items"] = None
                    review["actor_action_map"] = None
                    review["order_relations"] = None
                print(f"已删除 {removed.get('item_id')}")
            else:
                print("没有可删除的项（legacy 快路径无结构化项）。")
        elif cmd == "rr":
            if len(_item_id_list(sentence)) >= 2:
                _enter_relations(sentence)
            else:
                print("rule_items 少于 2 项：显式映射/顺序无意义。")
                review["actor_action_map"] = None
                review["order_relations"] = None
        else:
            print("未知命令。")
    # _sync_mirror is handled by the caller after the legacy pass / on save.


def _edit_one_sentence(doc: dict[str, Any], sentence: dict[str, Any],
                       idx: int, rid: str) -> None:
    """Interactive adjudication session over ONE sentence (mutates in place)."""
    total = len(list(iter_sentences(doc)))
    sample_id = sentence["sample_id"]
    candidate = sentence.get("candidate", {}) or {}
    review = sentence["review"]
    print(f"\n[{idx}/{total}] {sample_id} (规则 {rid})")
    print(f"原文: {sentence.get('sentence_text')}")
    print(f"candidate_source={candidate.get('candidate_source')} "
          f"is_gold={candidate.get('is_gold')}")

    already_structured = isinstance(review.get("rule_items"), list)

    # -- legacy six blocks ------------------------------------------------
    for field in ALL_FIELDS:
        _ask_one_block(sentence, field, review[field], mode="legacy")

    # -- keep rule_items[0] == legacy mirror ------------------------------
    _sync_mirror(sentence)

    # -- structured extension question (only when legacy six are decided) --
    legacy_done = all(
        isinstance(review.get(f), dict)
        and review[f].get("decision") in DECISION_VALUES
        for f in ALL_FIELDS)
    if already_structured:
        print("该句已含结构化 rule_items（i1 已与 legacy 镜像同步）。")
        _structured_menu(sentence)
    elif legacy_done:
        answer = _prompt(
            "legacy 六块已全决。本句是否还有其他规范元素（多动作/多执行者）"
            "或需要声明执行者-动作关联/动作顺序？(y/n) -> ").strip().casefold()
        if answer in ("y", "yes"):
            review["rule_items"] = [_mirror_legacy_as_i1(sentence)]
            _structured_menu(sentence)
        else:
            review["rule_items"] = None
            review["actor_action_map"] = None
            review["order_relations"] = None
    else:
        print("（legacy 六块未全决：结构化扩展留待下次编辑；句子保持 unreviewed）")

    notes_answer = _prompt("notes（回车跳过）: ")
    if notes_answer.strip():
        review["notes"] = notes_answer.strip()

    state = recompute_sentence_review_state_v2(sentence)
    decided = len([f for f in ALL_FIELDS if review[f].get("decision")
                   in DECISION_VALUES])
    remaining = len(ALL_FIELDS) - decided
    print(f"已录入完成：legacy 已决 {decided}/6，剩余字段 {remaining}；"
          f"保存时 review_state 将置为 {state}")
    if state != "reviewed":
        print("（该句尚未 v2 全决，将保持 unreviewed）")


def _validate_before_save(doc: dict[str, Any]) -> list[str]:
    """Re-validate every sentence right before a save; empty list == saveable.

    A decided field that became illegal (or a reviewed state with an undecided
    field/item) is a hard error: the save is refused and nothing is written.
    """
    errors: list[str] = []
    for _idx, _rid, sentence in iter_sentences(doc):
        recompute_sentence_review_state_v2(sentence)
        ok, errs, _warns = validate_sentence_review_v2(sentence)
        errors.extend(errs)
    return errors


def _save_doc(path: Path, doc: dict[str, Any]) -> bool:
    """Validate then atomically save. Returns True when written."""
    errors = _validate_before_save(doc)
    if errors:
        print("保存被拒绝：已决字段存在非法状态，未写盘：")
        for msg in errors:
            print(f"  - {msg}")
        return False
    recompute_doc_status_v2(doc)
    try:
        backup = atomic_save_json(path, doc)
    except OSError as exc:
        print(f"写盘失败: {exc}")
        return False
    print(f"已保存: {path}" + (f" (backup: {backup})" if backup else ""))
    return True


def _run_interactive(path: Path, start_sample_id: Optional[str] = None) -> int:
    doc = _load_doc(path)
    if not _is_v2(doc):
        schema = _schema_of(doc)
        raise SystemExit(
            f"编辑命令只允许在 v2 editable（{SCHEMA_EDITABLE_V2}）文件上执行；"
            f"当前文件 schema={schema!r}。v1 文件仅支持只读命令 "
            f"(--list/--progress/--show)，并建议用 builder/import 先升级到 v2。"
        )
    sentences = list(iter_sentences(doc))
    if start_sample_id is not None:
        found = find_sentence(doc, start_sample_id)
        if found is None:
            raise SystemExit(f"未知 sample_id: {start_sample_id}")
        queue = [found]
    else:
        first_unreviewed = next(
            ((i, r, s) for i, r, s in sentences
             if s.get("review", {}).get("review_state") != "reviewed"),
            None)
        if first_unreviewed is None:
            print("所有句子均已 reviewed，无需继续编辑。")
            return 0
        queue = [first_unreviewed]

    while queue:
        idx, rid, sentence = queue.pop(0)
        _edit_one_sentence(doc, sentence, idx, rid)
        while True:
            action = _prompt("[s]ave & next / [q]uit: ").strip().casefold()
            if action not in ("s", "q"):
                print("请输入 s=保存并继续下一句 / q=保存并退出")
                continue
            if not _save_doc(path, doc):
                print("保存被拒绝：请修正非法已决字段后重试 (s/q)，或按 Ctrl+C "
                      "放弃本次会话")
                continue
            break
        if action == "q":
            return 0
        if start_sample_id is not None:
            return 0  # single-sentence --edit: save then stop
        next_unreviewed = next(
            ((i, r, s) for i, r, s in sentences
             if s.get("review", {}).get("review_state") != "reviewed"),
            None)
        if next_unreviewed is None:
            print("全部句子均已 reviewed。工作流完成。")
            return 0
        queue.append(next_unreviewed)
    return 0


def main() -> int:
    _setup_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_EDITABLE_V2_PATH)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="打印每句摘要")
    group.add_argument("--progress", action="store_true", help="打印总体进度")
    group.add_argument("--show", metavar="SAMPLE_ID", default=None,
                       help="打印单句详情")
    group.add_argument("--edit", metavar="SAMPLE_ID", default=None,
                       help="交互编辑指定句子")
    group.add_argument("--next", action="store_true",
                       help="从第一句未 reviewed 的句子开始交互编辑")
    args = parser.parse_args()

    if args.show is not None:
        doc = _load_doc(args.file)
        lines = show_lines(doc, args.show)
        if lines is None:
            raise SystemExit(f"未知 sample_id: {args.show}")
        print("\n".join(lines))
        return 0
    if args.list:
        print("\n".join(list_lines(_load_doc(args.file))))
        return 0
    if args.progress:
        print("\n".join(progress_lines(_load_doc(args.file))))
        return 0
    return _run_interactive(args.file, start_sample_id=args.edit)


if __name__ == "__main__":
    raise SystemExit(main())
