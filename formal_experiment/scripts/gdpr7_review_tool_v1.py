# -*- coding: utf-8 -*-
"""Interactive human-adjudication tool for the GDPR7 six-element review (v1).

The ONLY interactive editing entry point of the workflow. It operates on the
editable document
(``data/development/human_review/gdpr7_six_element_review_decisions_v1.json``,
schema ``gdpr7_six_element_review_editable@1.0.0``) and NEVER touches the blank
surface file. Only a human reviewer may set decisions: the tool only displays
the sentence, the development-only candidate and the review state, then records
exactly what the reviewer types.

Commands (mutually exclusive actions):

    --file <path>        editable document to operate on (default above)
    --list               one-line summary of every sentence
    --progress           aggregate progress (total/reviewed/decided fields/...)
    --show <sample_id>   print one sentence with candidate and current review
    --edit <sample_id>   interactive adjudication of one sentence
    --next               interactive adjudication of the first unreviewed
                         sentence (document order)

Interactive editing rules:

* per field, the reviewer answers one of::

      a                 accept the candidate value ("无" accepted when the
                        candidate is null and the sentence indeed has none)
      r                 reject (the sentence has no such element)
      e:<value>         edited with an explicit new value
      (empty)           skip / leave as-is

* modality ``edited_value`` must be one of the four controlled labels
  (definition/obligation/permission/prohibition); the five text fields
  (actor/action/condition/constraint/exception) must be a verbatim contiguous
  substring of the sentence text — an invalid value is reported immediately and
  re-prompted, never stored;
* after the six fields the reviewer may add notes (empty line skips);
* then ``s`` saves and continues to the next unreviewed sentence, ``q`` saves
  the current progress and quits. Every save first re-validates every decided
  field of the edited sentence: if any decided field is illegal the save is
  REFUSED and nothing is written;
* saving automatically sets ``review_state`` to ``reviewed`` once all six
  fields of the sentence are decided (otherwise it stays ``unreviewed`` and the
  number of remaining fields is printed), recomputes the document status, and
  atomically replaces the file after copying the previous content to
  ``<file>.bak``.

Zero LLM/API/network. Console I/O: prompts via ``print``, answers via
``input()``; stdout/stderr are best-effort reconfigured to UTF-8 for Windows
consoles.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.gdpr7_review_rules_v1 import (  # noqa: E402
    ALL_FIELDS,
    DEFAULT_EDITABLE_PATH,
    DECISION_VALUES,
    MODALITY_LABELS,
    TEXT_FIELDS,
    atomic_save_json,
    collect_stats,
    doc_json_bytes,
    is_verbatim_substring,
    load_json,
    recompute_doc_status,
    recompute_sentence_review_state,
    validate_field_decision,
    validate_sentence_review,
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
    """Pure progress summary over ``doc`` (see :func:`collect_stats`)."""
    stats = collect_stats(doc)
    return {
        "sentences_total": stats["sentences_total"],
        "reviewed": stats["reviewed"],
        "unreviewed": stats["unreviewed"],
        "decisions_total": stats["decisions_total"],
        "fields_total": stats["fields_total"],
        "remaining_unreviewed": stats["unreviewed"],
        "per_field_decided": stats["per_field_decided"],
    }


def progress_lines(doc: dict[str, Any]) -> list[str]:
    """Human-readable Chinese progress lines (pure; used by ``--progress``)."""
    p = compute_progress(doc)
    return [
        f"总句数={p['sentences_total']}；"
        f"reviewed={p['reviewed']}；unreviewed={p['unreviewed']}；"
        f"已决字段={p['decisions_total']}/{p['fields_total']}；"
        f"剩余 unreviewed 句数={p['remaining_unreviewed']}",
    ]


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
        lines.append(
            f"[{idx}/{total}] {sentence.get('sample_id')} ({rid}) "
            f"state={review.get('review_state')} decided={decided}/6"
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
    return lines


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
    for field in ALL_FIELDS:
        cand_val = candidate.get(field)
        kind = None
        if field == "constraint":
            kind = candidate.get("constraint_kind")
        elif field == "exception":
            kind = candidate.get("exception_kind")
        hint = f"候选={candidate_display(cand_val, kind)}"
        if field == "modality":
            hint += f"  (修正值限 {MODALITY_LABELS})"
        else:
            hint += "  (修正值须为原句逐字连续片段)"
        entry = review[field]
        current = "未决"
        if entry.get("decision") in DECISION_VALUES:
            current = entry["decision"]
            if entry.get("edited_value") is not None:
                current += f": {entry['edited_value']!r}"
        print(f"[{field}] 当前={current} | {hint}")
        while True:
            answer = _prompt(
                f"  {FIELD_LABELS_ZH[field]} 决定: a=接受候选 / r=拒绝(句中无此要素) "
                f"/ e:<新值>=修正 / 回车=跳过 -> "
            )
            decision, edited_value, error_text = _parse_decision_answer(
                answer, field, sentence.get("sentence_text", ""), cand_val)
            if error_text:
                print(f"  !! {error_text}")
                continue
            if decision is None:
                break  # skip: keep the previous value
            ok, ferr = validate_field_decision(
                field, decision, edited_value, sentence.get("sentence_text", ""))
            if not ok:
                print("  !! " + "；".join(ferr))
                continue
            entry["decision"] = decision
            entry["edited_value"] = edited_value
            break
    notes_answer = _prompt("notes（回车跳过）: ")
    if notes_answer.strip():
        review["notes"] = notes_answer.strip()
    # state + decided-field legality
    state = recompute_sentence_review_state(sentence)
    decided = len([f for f in ALL_FIELDS if review[f].get("decision")
                   in DECISION_VALUES])
    remaining = len(ALL_FIELDS) - decided
    print(f"已录入完成：句内已决 {decided}/6，剩余字段 {remaining}；"
          f"保存时 review_state 将置为 {state}")
    if state != "reviewed" and remaining:
        print(f"（该句尚有 {remaining} 个字段未决，将保持 unreviewed）")


def _validate_before_save(doc: dict[str, Any]) -> list[str]:
    """Re-validate every sentence right before a save; empty list == saveable.

    A decided field that became illegal (or a reviewed state with an undecided
    field) is a hard error: the save is refused and nothing is written.
    """
    errors: list[str] = []
    for _idx, _rid, sentence in iter_sentences(doc):
        # recompute states from the current decisions first (the tool only
        # writes reviewed once all six fields of a sentence are decided)
        recompute_sentence_review_state(sentence)
        ok, errs, _warns = validate_sentence_review(sentence)
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
    recompute_doc_status(doc)
    try:
        backup = atomic_save_json(path, doc)
    except OSError as exc:
        print(f"写盘失败: {exc}")
        return False
    print(f"已保存: {path}" + (f" (backup: {backup})" if backup else ""))
    return True


def _run_interactive(path: Path, start_sample_id: Optional[str] = None) -> int:
    doc = _load_doc(path)
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
                print("保存被拒绝：请修正非法已决字段后重试 (s/q)，或按 Ctrl+C 放弃本次会话")
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
    parser.add_argument("--file", type=Path, default=DEFAULT_EDITABLE_PATH)
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
