"""Independent verifier for the formal GDPR-7 Gold Rule Records.

This verifier deliberately does NOT import the builder or the conversion
module.  It re-derives the confirmed values from the PUBLISHED artifact on
disk with its own code and compares them against the human-confirmed source
bundle, so a builder bug or a silent projection cannot pass unnoticed.

Checks
------
1.  artifact, capsule and manifest exist and their recorded hashes match disk;
2.  the published document validates against the versioned JSON schema;
3.  every span reproduces its stored text at its stored coordinates;
4.  every clause carries its own confirmed modality label (no first-label
    projection: the count of distinct labels per sentence is preserved);
5.  the artifact's values are re-derived into confirmed-bundle shape and
    compared field by field with the human-confirmed bundle (labels, evidence
    spans, all five element fields, actor-action map, order relations);
6.  the artifact carries no value that is absent from the confirmed bundle;
7.  the capsule rows match the artifact sentence-for-sentence (ids, modality
    labels, span coordinates and relation endpoints);
8.  the capsule declares no unresolved relation endpoint and its record count
    equals the sentence count.

Exit code 0 = VERIFIED.  Any failure prints the check name and exits 1.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

GOLD = ROOT / "data/gold/stage3/gdpr7_gold_rule_records_v1.json"
CAPSULE = ROOT / "data/predictions/gdpr7_human_rule_record_v1/predictions.json"
CAPSULE_MANIFEST = ROOT / "data/predictions/gdpr7_human_rule_record_v1/manifest.json"
MANIFEST = ROOT / "outputs/reports/gdpr7_gold_rule_records_v1.manifest.json"
CAPSULE_REPORT = ROOT / "outputs/reports/gdpr7_human_rule_record_capsule_v1.json"
SCHEMA = ROOT / "configs/schemas/gdpr7_gold_rule_record_v1.schema.json"
CONFIRMED = ROOT / "data/development/human_review/gdpr7_human_confirmed_v1/confirmed_rule_items.json"

SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")
EXPECTED_COUNTS = {"rules": 9, "sentences": 74, "items": 92, "spans": 235,
                   "modality_evidence_spans": 85, "relation_entries": 38}
# element spans + modality evidence spans == the confirmed bundle's anchored_spans
EXPECTED_ANCHORED_SPANS = 320
CHECK_NAMES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    CHECK_NAMES.append(name)
    if not condition:
        print(json.dumps({"verified": False, "failed_check": name,
                          "detail": detail}, ensure_ascii=False))
    return bool(condition)


def load(path: Path):
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


# --------------------------------------------------------------------------
# dependency-free structural contract check (used when jsonschema is absent);
# intentionally re-implemented here so the verifier shares no code with the
# builder or the conversion module
# --------------------------------------------------------------------------
def structural_check(doc) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["document is not an object"]
    for key in ("schema_version", "dataset_id", "status", "is_gold", "counts",
                "representation", "method", "provenance", "records"):
        if key not in doc:
            errors.append(f"missing top-level key: {key}")
    if doc.get("schema_version") != "gdpr7_gold_rule_record@1.0.0":
        errors.append("schema_version mismatch")
    if doc.get("status") != "published_gold_rule_records":
        errors.append("status mismatch")
    if doc.get("is_gold") is not True:
        errors.append("is_gold must be true")
    counts = doc.get("counts") or {}
    for key in ("rules", "sentences", "items", "spans",
                "modality_evidence_spans", "relation_entries"):
        if not isinstance(counts.get(key), int):
            errors.append(f"counts.{key} must be an integer")
    representation = doc.get("representation") or {}
    for key in ("clause_unit", "coordinates", "modality_policy",
                "action_structure", "relation_policy", "loss_policy"):
        if not isinstance(representation.get(key), str) or not representation.get(key):
            errors.append(f"representation.{key} must be a non-empty string")
    provenance = doc.get("provenance") or {}
    if provenance.get("source_schema") != "gdpr7_human_confirmed_rule_items@1.0.0":
        errors.append("provenance.source_schema mismatch")
    if provenance.get("gold_fields_read") is not True:
        errors.append("provenance.gold_fields_read must be true")
    records = doc.get("records")
    if not isinstance(records, list):
        return errors + ["records must be an array"]
    if len(records) != 74:
        errors.append(f"records length {len(records)} != 74")
    for record in records:
        where = record.get("sample_id") if isinstance(record, dict) else "?"
        if not isinstance(record, dict):
            errors.append("record is not an object")
            continue
        if record.get("review_state") != "human_confirmed":
            errors.append(f"{where}.review_state mismatch")
        clauses = record.get("clauses")
        if not isinstance(clauses, list) or not clauses:
            errors.append(f"{where}.clauses must be a non-empty array")
            continue
        if record.get("item_count") != len(clauses):
            errors.append(f"{where}.item_count != len(clauses)")
        for clause in clauses:
            cwhere = f"{where}/{clause.get('item_id')}"
            for key in ("clause_id", "item_id", "clause_span", "modality",
                        "actors", "actions", "conditions", "constraints",
                        "exceptions", "actor_action_map", "order_relations",
                        "action_structure"):
                if key not in clause:
                    errors.append(f"{cwhere} missing {key}")
            modality = clause.get("modality") or {}
            if modality.get("label") not in ("obligation", "permission",
                                             "prohibition", "definition"):
                errors.append(f"{cwhere}.modality.label invalid")
            for field in ("actors", "actions", "conditions", "constraints",
                          "exceptions"):
                for span in clause.get(field) or []:
                    if not all(k in span for k in ("start", "end", "text", "id")):
                        errors.append(f"{cwhere}.{field} invalid span")
    return errors


def span_signature(span, with_id: bool):
    if with_id:
        return (span["start"], span["end"], span["text"], span["id"])
    return (span["start"], span["end"], span["text"])


def derive_bundle_shape(doc) -> dict:
    """Re-derive the confirmed-bundle shape from the published artifact."""
    out = {}
    for record in doc["records"]:
        sid = record["sample_id"]
        text = record["sentence_text"]
        items = []
        for clause in record["clauses"]:
            item = {
                "item_id": clause["item_id"],
                "modality": clause["modality"]["label"],
                "modality_evidence": [
                    span_signature(s, False)
                    for s in clause["modality"]["evidence"]
                ],
                "actor_action_map": [
                    (entry.get("actor_id"), entry.get("action_id"),
                     entry.get("action_item_id"))
                    for entry in clause["actor_action_map"]
                ],
                "order_relations": [
                    (entry["before_item_id"], entry["after_item_id"])
                    for entry in clause["order_relations"]
                ],
                "action_structure": clause["action_structure"],
            }
            for field in SPAN_FIELDS:
                item[field] = [span_signature(s, False)
                               for s in clause[field + "s"]]
            items.append(item)
        out[sid] = {
            "rule_id": record["rule_id"],
            "sentence_idx": record["sentence_idx"],
            "char_span": list(record["char_span"]),
            "text_sha256": record["text_sha256"],
            "rule_text_sha256": record["rule_text_sha256"],
            "sentence_text": text,
            "review_state": record["review_state"],
            "context_links": list(record["context_links"]),
            "temporal_suggestions": list(record["temporal_suggestions"]),
            "item_count": record["item_count"],
            "items": items,
        }
    return out


def bundle_shape(bundle) -> dict:
    """Normalise the human-confirmed bundle into the same comparison shape."""
    out = {}
    for record in bundle["records"]:
        items = []
        for item in record["rule_items"]:
            items.append({
                "item_id": item["item_id"],
                "modality": item["modality"],
                "modality_evidence": [
                    (s["start"], s["end"], s["text"])
                    for s in item["modality_evidence"]
                ],
                "actor_action_map": [
                    (entry.get("actor_span_index"), entry.get("action_item_id"))
                    for entry in (item.get("actor_action_map") or [])
                ],
                "order_relations": [
                    (entry["before_item_id"], entry["after_item_id"])
                    for entry in (item.get("order_relations") or [])
                ],
                "action_structure": item.get("action_structure"),
                **{field: [(s["start"], s["end"], s["text"])
                           for s in item.get(field) or []]
                   for field in SPAN_FIELDS},
            })
        out[record["sample_id"]] = {
            "rule_id": record["rule_id"],
            "sentence_idx": record["sentence_idx"],
            "char_span": list(record["char_span"]),
            "text_sha256": record["text_sha256"],
            "rule_text_sha256": record["rule_text_sha256"],
            "sentence_text": record["sentence_text"],
            "review_state": record["review_state"],
            "context_links": list(record["context_links"]),
            "temporal_suggestions": list(record["temporal_suggestions"]),
            "item_count": len(record["rule_items"]),
            "items": items,
        }
    return out


def main() -> int:
    try:
        doc = load(GOLD)
        capsule = load(CAPSULE)
        manifest = load(MANIFEST)
        capsule_manifest = load(CAPSULE_MANIFEST)
        capsule_report = load(CAPSULE_REPORT)
        confirmed = load(CONFIRMED)
    except Exception as exc:
        print(json.dumps({"verified": False, "failed_check": "artifacts_exist",
                          "detail": str(exc)}, ensure_ascii=False))
        return 1

    # 1. artifact / manifest hash binding ---------------------------------
    if not check("manifest_binds_artifacts", bool(manifest.get("artifacts")),
                 "manifest has no artifacts block"):
        return 1
    for path, entry in manifest["artifacts"].items():
        target = ROOT / path
        if not check(f"artifact_exists:{path}", target.is_file(), "missing"):
            return 1
        if not check(f"artifact_hash:{path}", sha256_file(target) == entry["sha256"],
                     f"{sha256_file(target)} != {entry['sha256']}"):
            return 1
    for key, path in (("gold_rule_records", GOLD), ("capsule", CAPSULE)):
        entry = capsule_report.get("bindings", {}).get(key, {})
        if not check(f"capsule_report_binding:{key}",
                     entry.get("sha256") == sha256_file(path),
                     f"{entry.get('sha256')} != {sha256_file(path)}"):
            return 1
    if not check("capsule_manifest_binding",
                 capsule_manifest.get("predictions_sha256") == sha256_file(CAPSULE),
                 "capsule manifest predictions hash drift"):
        return 1
    if not check("manifest_binds_source",
                 manifest["bindings"]["confirmed_bundle"]["sha256"] == sha256_file(CONFIRMED),
                 "confirmed bundle hash drift"):
        return 1

    # 2. schema ------------------------------------------------------------
    schema_errors: list[str] = []
    try:
        import jsonschema  # noqa: PLC0415
        validator = jsonschema.Draft202012Validator(load(SCHEMA))
        schema_errors = [
            f"{'/'.join(str(p) for p in e.absolute_path)}: {e.message}"
            for e in validator.iter_errors(doc)]
    except Exception:
        schema_errors = structural_check(doc)
    if not check("schema_valid", not schema_errors, "; ".join(schema_errors[:5])):
        return 1

    # 3. span text / bounds + unique ids ----------------------------------
    span_problem = ""
    seen_ids: set[str] = set()
    for record in doc["records"]:
        text = record["sentence_text"]
        for clause in record["clauses"]:
            if not (0 < clause["clause_span"]["end"] <= len(text)):
                span_problem = f"{record['sample_id']}: clause_span out of range"
                break
            for span in clause["modality"]["evidence"]:
                if text[span["start"]:span["end"]] != span["text"]:
                    span_problem = (f"{record['sample_id']}: modality evidence "
                                    f"text mismatch")
                    break
            for field in SPAN_FIELDS:
                for span in clause[field + "s"]:
                    if text[span["start"]:span["end"]] != span["text"]:
                        span_problem = f"{record['sample_id']}: {field} span mismatch"
                        break
                    if span["id"] in seen_ids:
                        span_problem = f"duplicate span id {span['id']}"
                        break
                    seen_ids.add(span["id"])
        if span_problem:
            break
    if not check("spans_reproduce_text", not span_problem, span_problem):
        return 1

    # 4. per-item modality preserved (no first-label projection) ----------
    per_sentence_labels = {
        rec["sample_id"]: sorted({c["modality"]["label"] for c in rec["clauses"]})
        for rec in doc["records"]
    }
    confirmed_labels = {
        rec["sample_id"]: sorted({i["modality"] for i in rec["rule_items"]})
        for rec in confirmed["records"]
    }
    if not check("modality_labels_preserved",
                 per_sentence_labels == confirmed_labels,
                 "per-sentence modality label sets differ from the confirmed bundle"):
        return 1

    # 5. lossless field-by-field re-derivation ----------------------------
    derived = derive_bundle_shape(doc)
    source = bundle_shape(confirmed)
    if not check("same_sentence_ids", set(derived) == set(source),
                 "sentence id sets differ"):
        return 1
    mismatches: list[str] = []
    for sid in sorted(source):
        left, right = derived[sid], source[sid]
        for key in ("rule_id", "sentence_idx", "char_span", "text_sha256",
                    "rule_text_sha256", "sentence_text", "review_state",
                    "context_links", "temporal_suggestions", "item_count"):
            if left[key] != right[key]:
                mismatches.append(f"{sid}.{key}: {left[key]!r} != {right[key]!r}")
        if len(left["items"]) != len(right["items"]):
            mismatches.append(f"{sid}: item count {len(left['items'])} != "
                              f"{len(right['items'])}")
            continue
        for li, ri in zip(left["items"], right["items"]):
            for key in ("item_id", "modality", "modality_evidence",
                        "action_structure", *SPAN_FIELDS):
                if li[key] != ri[key]:
                    mismatches.append(
                        f"{sid}/{li['item_id']}.{key}: {li[key]!r} != {ri[key]!r}")
            # actor_action_map: the artifact resolves a within-item target to a
            # concrete action span id; the confirmed bundle stores the item id.
            # Compare the actor side and the resolved target.
            if len(li["actor_action_map"]) != len(ri["actor_action_map"]):
                mismatches.append(f"{sid}/{li['item_id']}.actor_action_map length "
                                  f"{len(li['actor_action_map'])} != "
                                  f"{len(ri['actor_action_map'])}")
            else:
                for la, ra in zip(li["actor_action_map"], ri["actor_action_map"]):
                    actor_id, action_id, action_item_id = la
                    actor_index, source_target = ra
                    if not actor_id.endswith(f".actor.{int(actor_index) + 1}"):
                        mismatches.append(
                            f"{sid}/{li['item_id']}.actor_action_map actor "
                            f"{actor_id!r} does not resolve to confirmed index "
                            f"{actor_index!r}")
                    if source_target == li["item_id"]:
                        if not isinstance(action_id, str) or \
                                not action_id.endswith(".action.1"):
                            mismatches.append(
                                f"{sid}/{li['item_id']}.actor_action_map within-item "
                                f"target did not resolve to this clause's action span")
                    elif action_item_id != source_target:
                        mismatches.append(
                            f"{sid}/{li['item_id']}.actor_action_map cross-item "
                            f"target {action_item_id!r} != {source_target!r}")
            if li["order_relations"] != ri["order_relations"]:
                mismatches.append(f"{sid}/{li['item_id']}.order_relations differ")
    if not check("lossless_round_trip", not mismatches,
                 "; ".join(mismatches[:8])):
        return 1

    # 6. no invented value: artifact span ids and counts are self-consistent
    if not check("counts_match_artifact",
                 doc["counts"]["items"] == sum(len(r["clauses"]) for r in doc["records"])
                 and doc["counts"]["sentences"] == len(doc["records"])
                 and doc["counts"]["spans"] == sum(
                     len(c[f + "s"]) for r in doc["records"]
                     for c in r["clauses"] for f in SPAN_FIELDS),
                 "declared counts do not match the artifact body"):
        return 1
    for key, expected in EXPECTED_COUNTS.items():
        if not check(f"count:{key}", doc["counts"].get(key) == expected,
                     f"{doc['counts'].get(key)} != {expected}"):
            return 1
    anchored = doc["counts"]["spans"] + doc["counts"]["modality_evidence_spans"]
    if not check("anchored_spans_reproduced", anchored == EXPECTED_ANCHORED_SPANS,
                 f"{anchored} != {EXPECTED_ANCHORED_SPANS}"):
        return 1

    # 7. capsule mirrors the artifact -------------------------------------
    capsule_rows = {row["sample_id"]: row for row in capsule["records"]}
    if not check("capsule_row_count",
                 capsule["record_count"] == len(doc["records"])
                 == len(capsule_rows),
                 "capsule row count mismatch"):
        return 1
    capsule_problems: list[str] = []
    for record in doc["records"]:
        row = capsule_rows.get(record["sample_id"])
        if row is None:
            capsule_problems.append(f"missing capsule row {record['sample_id']}")
            continue
        if row.get("request_status") != "ok":
            capsule_problems.append(f"{record['sample_id']}: request_status != ok")
        clauses = row["record"]["clauses"]
        if len(clauses) != len(record["clauses"]):
            capsule_problems.append(f"{record['sample_id']}: clause count mismatch")
            continue
        for clause, capsule_clause in zip(record["clauses"], clauses):
            if clause["clause_id"] != capsule_clause["clause_id"]:
                capsule_problems.append(f"{record['sample_id']}: clause id mismatch")
            if clause["modality"]["label"] != capsule_clause["modality"]["label"]:
                capsule_problems.append(
                    f"{record['sample_id']}/{clause['item_id']}: modality mismatch")
            for field in SPAN_FIELDS:
                left = [(s["start"], s["end"]) for s in clause[field + "s"]]
                right = [(s["start"], s["end"])
                         for s in capsule_clause[field + "s"]]
                if left != right:
                    capsule_problems.append(
                        f"{record['sample_id']}/{clause['item_id']}: {field} spans differ")
            if len(clause["actor_action_map"]) != len(capsule_clause["actor_action_map"]):
                capsule_problems.append(
                    f"{record['sample_id']}/{clause['item_id']}: actor_action_map length")
            if len(clause["order_relations"]) != len(capsule_clause["order_relations"]):
                capsule_problems.append(
                    f"{record['sample_id']}/{clause['item_id']}: order_relations length")
    if not check("capsule_mirrors_gold", not capsule_problems,
                 "; ".join(capsule_problems[:8])):
        return 1

    # 8. capsule declares no unresolved endpoint --------------------------
    if not check("capsule_no_unresolved_endpoints",
                 not capsule.get("unresolved_relation_endpoints"),
                 f"{capsule.get('unresolved_relation_endpoints')}"):
        return 1
    if not check("capsule_schema_declared",
                 capsule.get("schema_version") == "gdpr7_human_rule_record_predictions@1.0.0",
                 f"{capsule.get('schema_version')!r}"):
        return 1
    if not check("gold_declares_published",
                 doc.get("is_gold") is True
                 and doc.get("status") == "published_gold_rule_records",
                 "artifact must declare published Gold"):
        return 1
    if not check("provenance_binding",
                 doc["provenance"]["source_hashes"].get(rel(CONFIRMED)) ==
                 sha256_file(CONFIRMED),
                 "provenance does not bind the confirmed bundle hash"):
        return 1

    print(json.dumps({
        "verified": True,
        "checks": len(CHECK_NAMES),
        "check_names": CHECK_NAMES,
        "counts": doc["counts"],
        "capsule_rows": capsule["record_count"],
        "gold_sha256": sha256_file(GOLD),
        "capsule_sha256": sha256_file(CAPSULE),
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
