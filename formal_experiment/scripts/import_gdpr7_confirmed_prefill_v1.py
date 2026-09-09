"""Import a user's confirmed, unchanged GDPR draft without a lossy v2 export.

This writes a new human-confirmed review bundle, never a published Gold file.
The original proposals, blank/v1/v2 review files and experiment results stay
immutable. A content-bound conversation confirmation is mandatory for --apply.
Case acknowledgement preserves uncertainty; it cannot create compliant labels.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "data/development/human_review"
DRAFT = REVIEW / "gdpr7_ai_prefill_v1"
CASE = REVIEW / "gdpr7_case_ai_prefill_v1"
DEST = REVIEW / "gdpr7_human_confirmed_v1"
EVENT = REVIEW / "gdpr7_prefill_confirmation_20260909.json"
FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")
BOUND_PATHS = (
    "data/input/gdpr7_stage2_input_v1.json",
    "data/development/human_review/gdpr7_ai_prefill_v1/proposals.json",
    "data/development/human_review/gdpr7_ai_prefill_v1/请检查并修改这份预填稿.md",
    "data/development/human_review/gdpr7_ai_prefill_v1/manifest.json",
    "data/development/human_review/gdpr7_case_ai_prefill_v1/论文案例人工核对预填稿.md",
    "data/development/human_review/gdpr7_case_ai_prefill_v1/manifest.json",
)


def encode(doc):
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_proposals(doc, inputs):
    require(doc.get("schema_version") == "gdpr7_ai_annotation_proposals@1.0.0", "proposal schema")
    source = {s["sample_id"]: (r, s) for r in inputs["rules"] for s in r["sentences"]}
    rows = doc["records"]
    require(len(rows) == len(source) == 74, "expected 74 sentences")
    require(len({r["sample_id"] for r in rows}) == 74, "duplicate sample")
    spans_count = items_count = 0
    for row in rows:
        sid = row["sample_id"]
        require(sid in source, "unknown sample")
        rule, sentence = source[sid]
        text = row["sentence_text"]
        require(row["rule_id"] == rule["rule_id"], f"rule identity: {sid}")
        require(row["rule_text_sha256"] == rule["rule_text_sha256"], f"rule text hash: {sid}")
        require(text == sentence["approved_text_en"], f"source text: {sid}")
        require(sha(text.encode()) == row["text_sha256"], f"text hash: {sid}")
        for field in ("sentence_idx", "char_span", "text_sha256"):
            require(row[field] == sentence[field], f"source identity: {sid}/{field}")
        require(row["review_state"] == "unreviewed" and row["is_gold"] is False,
                "source draft state changed")
        require(all(v is None for v in row["human_review"].values()), "source human fields changed")
        require(set(row["context_links"]) <= set(source), "unknown context link")
        items = row["suggested_rule_items"]
        require(bool(items), "empty rule items")
        for pos, item in enumerate(items, 1):
            require(item["item_id"] == f"{sid}.p{pos}", "rule item identity")
            require(item["modality"] in {"obligation", "permission", "prohibition", "definition"}, "modality")
            for field in (*FIELDS[1:], "modality_evidence"):
                require(isinstance(item[field], list), "span list")
                for span in item[field]:
                    start, end = span["start"], span["end"]
                    require(type(start) is int and type(end) is int and 0 <= start < end <= len(text), "span bounds")
                    require(text[start:end] == span["text"], "span text mismatch")
                    spans_count += 1
            for edge in item["actor_action_map"]:
                idx = edge["actor_span_index"]
                require(type(idx) is int and 0 <= idx < len(item["actor"]), "actor endpoint")
                require(edge["action_item_id"] == item["item_id"] and item["action"], "action endpoint")
            items_count += 1
    require(doc["counts"] == {"rules": 9, "sentences": 74, "items": items_count,
                             "anchored_spans": spans_count, "human_confirmed": 0}, "counts mismatch")
    return items_count, spans_count


def build_confirmed(doc, inputs, event, source_hashes):
    require(event.get("schema_version") == "gdpr7_prefill_user_confirmation@1.0.0", "confirmation schema")
    require(event.get("human_confirmed") is True, "explicit human confirmation required")
    require(isinstance(event.get("event_id"), str) and event["event_id"].strip(), "event identity required")
    require(event.get("scope") == "accept_current_prefill_documents_without_edits", "confirmation scope")
    require(isinstance(event.get("user_message_verbatim"), str) and event["user_message_verbatim"].strip(), "confirmation message")
    require(isinstance(event.get("reviewer"), str) and event["reviewer"].strip(), "reviewer required")
    require(event.get("source_sha256") == source_hashes, "confirmation source hashes do not match")
    require(set(source_hashes) == set(BOUND_PATHS), "confirmation binding set incomplete")
    n_items, n_spans = validate_proposals(doc, inputs)
    rows = []
    for original in doc["records"]:
        row = copy.deepcopy(original)
        row["rule_items"] = row.pop("suggested_rule_items")
        for item in row["rule_items"]:
            item["decisions"] = {field: "accepted" for field in FIELDS}
        row["human_review"] = {
            "decision": "accepted", "reviewer": event["reviewer"],
            "confirmation_event_id": event["event_id"],
            "comment": "用户在会话中确认当前文件；本地稿件无内容修订。",
        }
        row["review_state"] = "human_confirmed"
        rows.append(row)
    confirmed = {
        "schema_version": "gdpr7_human_confirmed_rule_items@1.0.0",
        "status": "human_confirmed_not_published_gold", "is_gold": False,
        "publication_authorized": False,
        "provenance": {"annotation_origin": "AI-assisted, human-confirmed",
                       "reviewer": event["reviewer"], "recorded_by": "Codex assistant",
                       "confirmation_event_id": event["event_id"], "source_sha256": source_hashes},
        "counts": {"rules": 9, "sentences": 74, "items": n_items,
                   "anchored_spans": n_spans, "human_confirmed": 74,
                   "item_field_decisions": n_items * 6},
        "representation": {"span_unit": doc["annotation_policy"]["span_unit"],
                           "one_item_per_norm": True,
                           "action_arrays_are_evidence_fragments": True,
                           "context_and_temporal_notes_preserved_verbatim": True,
                           "not_exported_through_legacy_first_label_or_first_span_projection": True},
        "records": rows,
    }
    # Round trip must recover ALL authored semantic content, including notes,
    # repeated-string offsets, mixed modalities and non-contiguous evidence.
    for source, target in zip(doc["records"], rows):
        back = copy.deepcopy(target)
        back["suggested_rule_items"] = back.pop("rule_items")
        for item in back["suggested_rule_items"]:
            del item["decisions"]
        back["human_review"] = source["human_review"]
        back["review_state"] = source["review_state"]
        require(back == source, "lossless round trip failed")
    case = {
        "schema_version": "gdpr7_case_review_acknowledgement@1.0.0",
        "confirmation_event_id": event["event_id"], "reviewer": event["reviewer"],
        "document_content_acknowledged": True, "is_gold": False,
        "case_selection": {"primary": "gdpr_1_data_breach/article33+article34", "auxiliary": "gdpr_article22_s001"},
        "article22_s001_modality": next(r for r in rows if r["sample_id"] == "gdpr_article22_s001")["rule_items"][0]["modality"],
        "local_notification_structure": {"missing_notify_activity": False, "incorrect_notify_actor": False,
                                         "scope": "通知监管机构这一活动；不等于整条法规合规"},
        "whole_process_compliant": None,
        "control_gold_confirmed": False, "variant_timeout_gold_confirmed": False,
        "unresolved_as_acknowledged": ["既有v001/v002标签的检查范围与局部读图判断需核实",
                                      "延误说明计时器不能直接证明主通知期限满足或违反"],
        "existing_gold_modified": False,
    }
    return confirmed, case


def prepare(event_path=EVENT):
    event_bytes = event_path.read_bytes()
    event = json.loads(event_bytes)
    sources = {rel: sha((ROOT / rel).read_bytes()) for rel in BOUND_PATHS}
    # Require the exact two reviewed drafts, not just a re-hashed JSON source.
    for folder in (DRAFT, CASE):
        manifest = json.loads((folder / "manifest.json").read_bytes())
        for name, entry in manifest["artifacts"].items():
            expected = entry["sha256"] if isinstance(entry, dict) else entry
            require(sha((folder / name).read_bytes()) == expected, f"reviewed draft changed: {name}")
    doc = json.loads((DRAFT / "proposals.json").read_bytes())
    inputs = json.loads((ROOT / BOUND_PATHS[0]).read_bytes())
    confirmed, case = build_confirmed(doc, inputs, event, sources)
    files = {"confirmed_rule_items.json": encode(confirmed), "case_acknowledgement.json": encode(case),
             ".gitattributes": b"* text eol=lf\n"}
    files["人工确认结果.md"] = (
        "# GDPR 人工确认结果\n\n"
        "你已在会话中确认：**可以我已经进行人工确认完毕**。\n\n"
        "确认对象是已交付的74句预填稿和案例核对稿；本地文件没有另行修订。"
        "本次据此完成导入：**9条款、74/74句、92个规范条目、552个六要素决定、320处原文锚点**。\n\n"
        "逐句人工值见同目录 `confirmed_rule_items.json`。多情态、重复短语的具体位置、"
        "不连续片段、主体关联及跨句/顺序说明全部保留，没有经过旧格式的取首项转换。\n\n"
        "案例意见见 `case_acknowledgement.json`。主案例为泄露通知流程与第33/34条，"
        "第22条第1句按稿中建议确认 prohibition。整图合规性、计时器能否证明主通知超时"
        "仍按稿中结论保留为证据不足；本次没有将40个control批量标为合规，也没有修改既有三类Gold。\n\n"
        "两份原始预填稿保持当时字节，里面的‘待确认’是原稿历史状态；本目录和绑定的用户确认事件"
        "记录本次确认后的状态，不必回头逐个改原稿。\n\n"
        "这份已确认标注是后续规则记录构建的人工输入，**尚未发布为正式Gold，也不代表Oracle已运行**。"
        "旧v1/v2编辑文件保持原样，不再用其0/74统计来代表本次已确认的74句。\n\n"
        "复核命令：`python formal_experiment/scripts/import_gdpr7_confirmed_prefill_v1.py --check`。\n"
    ).encode("utf-8")
    manifest = {"schema_version": "gdpr7_confirmed_review_bundle@1.0.0",
                "status": confirmed["status"], "counts": confirmed["counts"],
                "confirmation_event_sha256": sha(event_bytes),
                "sources": sources, "lossless_round_trip_verified": True,
                "gold_published": False, "experimental_api_calls": 0,
                "artifacts": {name: sha(data) for name, data in files.items()}}
    files["manifest.json"] = encode(manifest)
    return files, manifest


def publish_new_bundle(dest, files):
    """Publish atomically from a normal sibling with inherited workspace ACLs.

    tempfile.TemporaryDirectory uses mkdir(mode=0o700). On Windows/Python 3.14
    that private ACL can survive a rename into the review directory, making
    the delivered files unreadable to the host/full-audit process. A normal
    sibling mkdir inherits the review directory's existing access rules.
    """
    require(not dest.exists(), "destination exists; refusing overwrite")
    stage = dest.parent / (".gdpr7-confirm-" + uuid.uuid4().hex)
    stage.mkdir()  # default mode, inherit the workspace ACL; never 0o700
    try:
        for name, data in files.items():
            require(Path(name).name == name, "artifact must be a basename")
            with (stage / name).open("xb") as handle:
                handle.write(data)
        require(not dest.exists(), "destination appeared; refusing overwrite")
        os.rename(stage, dest)
    finally:
        # Remove only our explicitly named files, never a recursive user path.
        if stage.exists():
            for name in files:
                if Path(name).name == name:
                    (stage / name).unlink(missing_ok=True)
            stage.rmdir()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    action = ap.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true")
    action.add_argument("--check", action="store_true")
    args = ap.parse_args()
    try:
        files, manifest = prepare()
        if args.check:
            for name, data in files.items():
                require((DEST / name).is_file() and (DEST / name).read_bytes() == data,
                        f"confirmed artifact missing or changed: {name}")
        elif args.apply:
            publish_new_bundle(DEST, files)
        print(json.dumps({"mode": "check" if args.check else "apply" if args.apply else "dry_run",
                          "valid": True, "counts": manifest["counts"], "is_gold": False,
                          "directory": str(DEST)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
