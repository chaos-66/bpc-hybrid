"""Build / verify the formal GDPR-7 Gold Rule Records and the Stage-3 capsule.

The standard answer is a MECHANICAL, LOSSLESS derivation of the user's already
confirmed human bundle (9 rules / 74 sentences / 92 rule items).  This script
never invents, edits, re-orders or drops a value; it only reshapes confirmed
values into the formal Rule Record contract plus a Stage-2-shaped capsule that
the existing Stage-3 converter consumes unchanged.

Safety
------
* zero LLM / API / network;
* reads the confirmed human bundle read-only; never writes it;
* refuses to overwrite an existing artifact unless ``--overwrite`` is passed;
* ``--check`` rebuilds everything in memory and compares with the published
  bytes, so a deterministic replay is provable without writing anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.gdpr7_gold_rule_records import (  # noqa: E402
    CAPSULE_SCHEMA,
    CONVERTER_NAME,
    RULE_RECORD_METHOD,
    RULE_RECORD_METHOD_VARIANT,
    RULE_RECORD_SCHEMA,
    build_capsule,
    build_rule_records,
    summarize,
)

CONFIRMED_DIR = ROOT / "data/development/human_review/gdpr7_human_confirmed_v1"
CONFIRMED = CONFIRMED_DIR / "confirmed_rule_items.json"
CONFIRMED_MANIFEST = CONFIRMED_DIR / "manifest.json"
CONFIRMATION_EVENT = (
    ROOT / "data/development/human_review/gdpr7_prefill_confirmation_20260909.json")
AUTHORIZATION = ROOT / "configs/gdpr7_gold_rule_records_authorization_event_v1.json"
SCHEMA = ROOT / "configs/schemas/gdpr7_gold_rule_record_v1.schema.json"

GOLD_OUT = ROOT / "data/gold/stage3/gdpr7_gold_rule_records_v1.json"
CAPSULE_OUT = ROOT / "data/predictions/gdpr7_human_rule_record_v1/predictions.json"
CAPSULE_MANIFEST_OUT = (
    ROOT / "data/predictions/gdpr7_human_rule_record_v1/manifest.json")
MANIFEST_OUT = ROOT / "outputs/reports/gdpr7_gold_rule_records_v1.manifest.json"
CAPSULE_REPORT_OUT = (
    ROOT / "outputs/reports/gdpr7_human_rule_record_capsule_v1.json")
REPORT_MD_OUT = ROOT / "outputs/reports/gdpr7_gold_rule_records_v1.md"

EXPECTED_COUNTS = {"rules": 9, "sentences": 74, "items": 92, "spans": 235,
                   "modality_evidence_spans": 85}
# The confirmed bundle counts every anchored span (element spans + modality
# evidence spans) as ``anchored_spans``; the derivation must reproduce it.
EXPECTED_ANCHORED_SPANS = 320


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path, label: str):
    if not path.is_file():
        raise FileNotFoundError(f"{label} missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def git_state() -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout
        return {"commit": commit, "dirty_paths": dirty.splitlines()[:20]}
    except Exception as exc:  # pragma: no cover
        return {"commit": "unknown", "dirty_paths": [str(exc)]}


def validate_schema(document, schema_path: Path) -> list[str]:
    """Validate against the versioned JSON Schema.

    Uses ``jsonschema`` when available; otherwise falls back to an explicit
    in-process structural check that enforces the same contract (fail closed:
    every required key, every enum, every span shape).  The fallback is
    deliberately redundant with the JSON Schema.
    """
    try:
        import jsonschema  # noqa: PLC0415
    except Exception:
        return structural_check(document)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{'/'.join(str(p) for p in err.absolute_path)}: {err.message}"
            for err in sorted(validator.iter_errors(document), key=str)]


MODALITY_VALUES = ("obligation", "permission", "prohibition", "definition")
TOP_REQUIRED = ("schema_version", "dataset_id", "status", "is_gold", "counts",
                "representation", "method", "provenance", "records")
REPRESENTATION_KEYS = ("clause_unit", "coordinates", "modality_policy",
                       "action_structure", "relation_policy", "loss_policy")
CLAUSE_REQUIRED = ("clause_id", "item_id", "clause_span", "modality", "actors",
                   "actions", "conditions", "constraints", "exceptions",
                   "actor_action_map", "order_relations", "action_structure")
SPAN_KEYS = ("start", "end", "text", "id")


def structural_check(document) -> list[str]:
    """Dependency-free structural validation of the Gold Rule Record contract."""
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["document is not a JSON object"]
    for key in TOP_REQUIRED:
        if key not in document:
            errors.append(f"missing top-level key: {key}")
    if document.get("schema_version") != RULE_RECORD_SCHEMA:
        errors.append(f"schema_version must be {RULE_RECORD_SCHEMA!r}")
    if document.get("dataset_id") != "gdpr7_gold_rule_records_v1":
        errors.append("dataset_id must be 'gdpr7_gold_rule_records_v1'")
    if document.get("status") != "published_gold_rule_records":
        errors.append("status must be 'published_gold_rule_records'")
    if document.get("is_gold") is not True:
        errors.append("is_gold must be true")
    counts = document.get("counts")
    if not isinstance(counts, dict):
        errors.append("counts must be an object")
    else:
        for key in ("rules", "sentences", "items", "spans",
                    "modality_evidence_spans", "relation_entries"):
            if not isinstance(counts.get(key), int):
                errors.append(f"counts.{key} must be an integer")
    representation = document.get("representation")
    if not isinstance(representation, dict):
        errors.append("representation must be an object")
    else:
        for key in REPRESENTATION_KEYS:
            if not isinstance(representation.get(key), str) or \
                    not representation.get(key):
                errors.append(f"representation.{key} must be a non-empty string")
    method = document.get("method")
    if not isinstance(method, dict) or \
            method.get("name") != RULE_RECORD_METHOD or \
            method.get("method_variant") != RULE_RECORD_METHOD_VARIANT:
        errors.append("method block mismatch")
    provenance = document.get("provenance")
    if not isinstance(provenance, dict):
        errors.append("provenance must be an object")
    else:
        if provenance.get("source_schema") != "gdpr7_human_confirmed_rule_items@1.0.0":
            errors.append("provenance.source_schema mismatch")
        hashes = provenance.get("source_hashes")
        if not isinstance(hashes, dict) or not hashes:
            errors.append("provenance.source_hashes must be a non-empty object")
        elif any(not (isinstance(v, str) and len(v) == 64) for v in hashes.values()):
            errors.append("provenance.source_hashes values must be sha256 hex")
        if provenance.get("gold_fields_read") is not True:
            errors.append("provenance.gold_fields_read must be true")
    records = document.get("records")
    if not isinstance(records, list):
        return errors + ["records must be an array"]
    if len(records) != 74:
        errors.append(f"records must have 74 entries, got {len(records)}")
    for index, record in enumerate(records):
        where = f"records[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{where} must be an object")
            continue
        for key in ("sample_id", "rule_id", "sentence_idx", "char_span",
                    "text_sha256", "rule_text_sha256", "sentence_text",
                    "review_state", "context_links", "temporal_suggestions",
                    "item_count", "clauses"):
            if key not in record:
                errors.append(f"{where} missing key {key}")
        if record.get("review_state") != "human_confirmed":
            errors.append(f"{where}.review_state must be 'human_confirmed'")
        clauses = record.get("clauses")
        if not isinstance(clauses, list) or not clauses:
            errors.append(f"{where}.clauses must be a non-empty array")
            continue
        if record.get("item_count") != len(clauses):
            errors.append(f"{where}.item_count != len(clauses)")
        for clause in clauses:
            cwhere = f"{where}/{clause.get('item_id')}"
            for key in CLAUSE_REQUIRED:
                if key not in clause:
                    errors.append(f"{cwhere} missing key {key}")
            modality = clause.get("modality")
            if not isinstance(modality, dict) or \
                    modality.get("label") not in MODALITY_VALUES or \
                    not isinstance(modality.get("evidence"), list):
                errors.append(f"{cwhere}.modality invalid")
            for field in ("actors", "actions", "conditions", "constraints",
                          "exceptions"):
                spans = clause.get(field)
                if not isinstance(spans, list):
                    errors.append(f"{cwhere}.{field} must be an array")
                    continue
                for span in spans:
                    if not isinstance(span, dict) or \
                            any(k not in span for k in SPAN_KEYS) or \
                            not isinstance(span.get("start"), int) or \
                            not isinstance(span.get("end"), int) or \
                            not isinstance(span.get("text"), str) or \
                            not isinstance(span.get("id"), str):
                        errors.append(f"{cwhere}.{field} invalid span")
            if not isinstance(clause.get("actor_action_map"), list):
                errors.append(f"{cwhere}.actor_action_map must be an array")
            if not isinstance(clause.get("order_relations"), list):
                errors.append(f"{cwhere}.order_relations must be an array")
    return errors


def check_authorization() -> dict:
    event = load_json(AUTHORIZATION, "Gold Rule Record authorization event")
    if event.get("schema_version") != "gdpr7_gold_rule_records_authorization@1.0.0":
        raise RuntimeError("authorization event schema mismatch")
    if not event.get("user_instruction_verbatim"):
        raise RuntimeError("authorization event lacks the user instruction")
    if sha256_bytes(event["user_instruction_verbatim"].encode("utf-8")) != \
            event.get("user_instruction_utf8_sha256"):
        raise RuntimeError("authorization event user-instruction hash mismatch")
    scope = event.get("authorized_scope") or {}
    for flag in ("may_add_infer_rewrite_labels", "may_change_coordinates",
                 "may_change_modality", "may_publish_third_party_raw_text",
                 "may_call_llm_or_api"):
        if scope.get(flag) is not False:
            raise RuntimeError(f"authorization scope must set {flag}=false")
    if event.get("publication_gate_status") != "ready_for_formal_gold_publication":
        raise RuntimeError("authorization event publication gate status mismatch")
    basis = event.get("authorization_basis") or {}
    prior = basis.get("prior_confirmation_event") or {}
    if sha256_file(CONFIRMATION_EVENT) != prior.get("sha256"):
        raise RuntimeError("prior confirmation event hash drift")
    bundle = basis.get("confirmed_bundle") or {}
    if sha256_file(CONFIRMED) != bundle.get("sha256"):
        raise RuntimeError("confirmed bundle hash drift")
    return event


def build_all():
    doc = load_json(CONFIRMED, "confirmed human bundle")
    confirmed_manifest = load_json(CONFIRMED_MANIFEST, "confirmed bundle manifest")
    # The source must still be the human-confirmed (not yet published) bundle;
    # the Gold Rule Records are DERIVED from it, never copied from another Gold.
    if doc.get("status") != "human_confirmed_not_published_gold":
        raise RuntimeError(
            f"confirmed bundle status drift: {doc.get('status')!r}")
    if doc.get("is_gold") is not False:
        raise RuntimeError("confirmed bundle must still be is_gold=false")
    if not (doc.get("provenance") or {}).get("confirmation_event_id"):
        raise RuntimeError("confirmed bundle lacks a confirmation_event_id")
    source_hashes = {
        rel(CONFIRMED): sha256_file(CONFIRMED),
        rel(CONFIRMED_MANIFEST): sha256_file(CONFIRMED_MANIFEST),
        rel(CONFIRMATION_EVENT): sha256_file(CONFIRMATION_EVENT),
        rel(AUTHORIZATION): sha256_file(AUTHORIZATION),
    }
    rule_records = build_rule_records(doc, source_hashes=source_hashes)
    capsule = build_capsule(rule_records)

    counts = rule_records["counts"]
    for key, expected in EXPECTED_COUNTS.items():
        if counts.get(key) != expected:
            raise RuntimeError(
                f"count drift for {key}: got {counts.get(key)!r}, expected {expected}")
    anchored = counts["spans"] + counts["modality_evidence_spans"]
    if anchored != confirmed_manifest["counts"]["anchored_spans"] or \
            anchored != EXPECTED_ANCHORED_SPANS:
        raise RuntimeError(
            f"anchored span count drift: derived {anchored}, confirmed bundle "
            f"{confirmed_manifest['counts']['anchored_spans']}")
    if rule_records["provenance"]["confirmation_event_id"] != \
            doc["provenance"]["confirmation_event_id"]:
        raise RuntimeError("Gold Rule Records must carry the confirmation event id")
    if capsule["unresolved_relation_endpoints"]:
        raise RuntimeError(
            "unresolved relation endpoints: "
            f"{capsule['unresolved_relation_endpoints']}")
    if capsule["record_count"] != counts["sentences"]:
        raise RuntimeError("capsule row count must equal the sentence count")

    errors = validate_schema(rule_records, SCHEMA)
    if errors:
        raise RuntimeError("Gold Rule Record schema violations:\n  " +
                           "\n  ".join(errors[:20]))
    return rule_records, capsule, source_hashes, confirmed_manifest


def build_manifest(rule_records, capsule, source_hashes, confirmed_manifest,
                   authorization) -> dict:
    artifacts = {}
    # The Markdown report is rendered FROM this manifest (it lists the artifact
    # table), so it is recorded as a path without a self-referential hash.
    for path in (GOLD_OUT, CAPSULE_OUT, CAPSULE_MANIFEST_OUT, CAPSULE_REPORT_OUT):
        artifacts[rel(path)] = {
            "path": rel(path),
            "sha256": sha256_file(path),
            "byte_size": path.stat().st_size,
        }
    return {
        "schema_version": "gdpr7_gold_rule_records_manifest@1.0.0",
        "publication_status": "verified_published",
        "dataset_id": rule_records["dataset_id"],
        "task": "S3.7 dependency: formal GDPR-7 Gold Rule Records (Oracle standard answer)",
        "counts": rule_records["counts"],
        "modality_item_counts": summarize(rule_records, capsule)["modality_item_counts"],
        "source_provenance": {
            "annotation_origin": rule_records["provenance"]["annotation_origin"],
            "adjudication": "user_confirmation_of_the_delivered_prefill_documents",
            "reviewer": rule_records["provenance"]["reviewer"],
            "confirmation_event_id": rule_records["provenance"]["confirmation_event_id"],
            "revisions": "none",
            "independent_from_scratch_expert_annotation": False,
            "derivation": ("mechanical, lossless conversion of the confirmed human "
                           "values; no label, span, coordinate, mapping or "
                           "relation was added, inferred, normalised or dropped"),
            "authorization_event": rel(AUTHORIZATION),
            "authorization_instruction_sha256":
                authorization["user_instruction_utf8_sha256"],
        },
        "bindings": {
            "confirmed_bundle": {
                "path": rel(CONFIRMED),
                "sha256": source_hashes[rel(CONFIRMED)],
                "status": confirmed_manifest.get("status"),
                "counts": confirmed_manifest.get("counts"),
            },
            "confirmed_bundle_manifest": {
                "path": rel(CONFIRMED_MANIFEST),
                "sha256": source_hashes[rel(CONFIRMED_MANIFEST)],
            },
            "confirmation_event": {
                "path": rel(CONFIRMATION_EVENT),
                "sha256": source_hashes[rel(CONFIRMATION_EVENT)],
                "user_message_verbatim": (
                    (authorization.get("authorization_basis") or {})
                    .get("prior_confirmation_event", {}).get("user_message_verbatim")),
            },
            "schema": {"path": rel(SCHEMA), "sha256": sha256_file(SCHEMA)},
        },
        "implementation": {
            rel(Path(__file__)): {"path": rel(Path(__file__)),
                                  "sha256": sha256_file(Path(__file__))},
            "src/bpc_hybrid/gdpr7_gold_rule_records.py": {
                "path": "src/bpc_hybrid/gdpr7_gold_rule_records.py",
                "sha256": sha256_file(ROOT / "src/bpc_hybrid/gdpr7_gold_rule_records.py"),
            },
            "scripts/verify_gdpr7_gold_rule_records_v1.py": {
                "path": "scripts/verify_gdpr7_gold_rule_records_v1.py",
                "sha256": sha256_file(ROOT / "scripts/verify_gdpr7_gold_rule_records_v1.py"),
            },
        },
        "contracts": {
            "rule_record_schema": RULE_RECORD_SCHEMA,
            "capsule_schema": CAPSULE_SCHEMA,
            "converter": CONVERTER_NAME,
            "consumed_by_stage3": ("bpc_hybrid.sun_stage3.gdpr_capsule_converter"
                                   ".build_rule_records (schema pinned)"),
        },
        "artifacts": artifacts,
        "report": {"path": rel(REPORT_MD_OUT),
                   "note": "human-readable report rendered from this manifest "
                           "(listed without a self-referential hash)"},
        "replay_command": "python formal_experiment/scripts/build_gdpr7_gold_rule_records_v1.py --check",
        "verification_command": "python formal_experiment/scripts/verify_gdpr7_gold_rule_records_v1.py",
        "boundaries": {
            "raw_third_party_text_committed": False,
            "gold_changed": False,
            "existing_stage3_gold_modified": False,
            "stage3_oracle_started": False,
            "llm_or_api_called": False,
        },
        "zero_api": {"new_llm_api_calls": 0},
        "git": git_state(),
    }


def build_capsule_report(capsule, rule_records) -> dict:
    return {
        "schema_version": "gdpr7_human_rule_record_capsule@1.0.0",
        "status": "verified_published",
        "capsule_schema": capsule["schema_version"],
        "dataset_id": capsule["dataset_id"],
        "method_id": capsule["method_id"],
        "record_count": capsule["record_count"],
        "source_rule_record_schema": rule_records["schema_version"],
        "source_rule_record_dataset": rule_records["dataset_id"],
        "rule_ids": sorted({rec["rule_id"] for rec in rule_records["records"]}),
        "counts": rule_records["counts"],
        "modality_item_counts": summarize(rule_records, capsule)["modality_item_counts"],
        "unresolved_relation_endpoints": capsule["unresolved_relation_endpoints"],
        "order_relations_present_rules": sorted({
            rec["rule_id"] for rec in rule_records["records"]
            for clause in rec["clauses"] if clause["order_relations"]
        }),
        "bindings": {
            "gold_rule_records": {"path": rel(GOLD_OUT),
                                  "sha256": sha256_file(GOLD_OUT)},
            "capsule": {"path": rel(CAPSULE_OUT), "sha256": sha256_file(CAPSULE_OUT)},
        },
        "containment": {
            "gold_read_by_runner": False,
            "raw_text_committed": False,
        },
        "replay_command": "python formal_experiment/scripts/build_gdpr7_gold_rule_records_v1.py --check",
        "zero_api": {"new_llm_api_calls": 0},
    }


def render_markdown(rule_records, capsule, manifest) -> bytes:
    counts = rule_records["counts"]
    mods = summarize(rule_records, capsule)["modality_item_counts"]
    lines = [
        "# GDPR-7 正式 Gold Rule Records（Oracle 标准答案）",
        "",
        f"**状态**：{rule_records['status']}",
        "**来源**：用户 2026-09-09 已确认的人工核对包（9 条款 / 74 句 / 92 条规范 / 320 处原文锚点）",
        f"**转换**：`{CONVERTER_NAME}` —— 机械、无损，未新增/推断/改写/归一化/丢弃任何值",
        "",
        "## 计数",
        "",
        "| 项 | 值 |",
        "|---|---:|",
        f"| 条款 | {counts['rules']} |",
        f"| 句子 | {counts['sentences']} |",
        f"| 规范条目 | {counts['items']} |",
        f"| 要素 span | {counts['spans']} |",
        f"| 情态证据 span | {counts['modality_evidence_spans']} |",
        f"| 关联条目（actor-action + order） | {counts['relation_entries']} |",
        "",
        "## 情态分布（按条目）",
        "",
        "| 情态 | 条目数 |",
        "|---|---:|",
    ]
    for label in ("obligation", "permission", "prohibition", "definition"):
        lines.append(f"| {label} | {mods.get(label, 0)} |")
    lines += [
        "",
        "## 表示约定",
        "",
        "- **一条规范 = 一个 clause**（不是一句一个 clause）；多情态句保留每条规范自己的情态标签。",
        "- 坐标为**句内相对坐标** `0..len(sentence_text)`，与冻结输入 `data/input/gdpr7_stage2_input_v1.json` 一致。",
        "- `actor_action_map` 与 `order_relations` 逐字复制自人工确认条目：不推断、不增删任何边。",
        "- 第三阶段胶囊（`data/predictions/gdpr7_human_rule_record_v1/`）由本 Gold 派生，供现有 `gdpr_capsule_converter` 直接消费。",
        "",
        "## 产物",
        "",
        "| 路径 | sha256 |",
        "|---|---|",
    ]
    if manifest is None:
        lines.append(f"| `{rel(MANIFEST_OUT)}` | （manifest 见文件本身） |")
    else:
        for path, entry in sorted(manifest["artifacts"].items()):
            lines.append(f"| `{path}` | `{entry['sha256']}` |")
    lines += [
        "",
        "## 复现与验证",
        "",
        "```powershell",
        "python formal_experiment/scripts/build_gdpr7_gold_rule_records_v1.py --check",
        "python formal_experiment/scripts/verify_gdpr7_gold_rule_records_v1.py",
        "```",
        "",
        "## 边界",
        "",
        "- 第三方法规原文不提交（`raw_third_party_text_committed=false`）。",
        "- 不改动既有 Stage 3 matching/violation decision Gold。",
        "- 本轮不启动 Oracle、不调用 LLM/API。",
        "",
    ]
    return ("\n".join(lines)).encode("utf-8")


def write_atomic(path: Path, data: bytes, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        existing = path.read_bytes()
        if existing == data:
            return
        raise RuntimeError(
            f"refusing to overwrite existing artifact with different bytes: {rel(path)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="rebuild in memory and compare with the published bytes")
    parser.add_argument("--overwrite", action="store_true",
                        help="allow replacing artifacts with different bytes")
    args = parser.parse_args(argv)

    authorization = check_authorization()
    rule_records, capsule, source_hashes, confirmed_manifest = build_all()

    if args.check:
        checks = []
        for path, document in ((GOLD_OUT, rule_records), (CAPSULE_OUT, capsule)):
            if not path.is_file():
                checks.append(f"missing: {rel(path)}")
                continue
            if path.read_bytes() != json_bytes(document):
                checks.append(f"byte drift: {rel(path)}")
        if not MANIFEST_OUT.is_file():
            checks.append(f"missing: {rel(MANIFEST_OUT)}")
        else:
            manifest = json.loads(MANIFEST_OUT.read_text(encoding="utf-8"))
            for path, entry in manifest.get("artifacts", {}).items():
                actual = sha256_file(ROOT / path)
                if actual != entry.get("sha256"):
                    checks.append(f"artifact hash drift: {path}")
        payload = {"mode": "check", "valid": not checks, "problems": checks,
                   "counts": rule_records["counts"],
                   "capsule_rows": capsule["record_count"]}
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if not checks else 2

    write_atomic(GOLD_OUT, json_bytes(rule_records), args.overwrite)
    write_atomic(CAPSULE_OUT, json_bytes(capsule), args.overwrite)
    capsule_manifest = {
        "schema_version": "gdpr7_human_rule_record_capsule_manifest@1.0.0",
        "dataset_id": capsule["dataset_id"],
        "method_id": capsule["method_id"],
        "capsule_schema": capsule["schema_version"],
        "record_count": capsule["record_count"],
        "predictions_sha256": sha256_file(CAPSULE_OUT),
        "source_rule_records": {"path": rel(GOLD_OUT),
                                "sha256": sha256_file(GOLD_OUT)},
        "gold_read_by_runner": False,
        "raw_text_committed": False,
        "zero_api": {"new_llm_api_calls": 0},
    }
    write_atomic(CAPSULE_MANIFEST_OUT, json_bytes(capsule_manifest), args.overwrite)
    capsule_report = build_capsule_report(capsule, rule_records)
    write_atomic(CAPSULE_REPORT_OUT, json_bytes(capsule_report), args.overwrite)
    manifest = build_manifest(rule_records, capsule, source_hashes,
                              confirmed_manifest, authorization)
    write_atomic(MANIFEST_OUT, json_bytes(manifest), args.overwrite)
    write_atomic(REPORT_MD_OUT,
                 render_markdown(rule_records, capsule, manifest),
                 args.overwrite)
    print(json.dumps({
        "mode": "apply",
        "counts": rule_records["counts"],
        "capsule_rows": capsule["record_count"],
        "gold": rel(GOLD_OUT),
        "gold_sha256": sha256_file(GOLD_OUT),
        "capsule": rel(CAPSULE_OUT),
        "capsule_sha256": sha256_file(CAPSULE_OUT),
        "manifest": rel(MANIFEST_OUT),
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
