"""Validate the EStG-150 human-review pack and report freeze readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/development/human_review/estg150_review_pack_v1.jsonl"
MODALITIES = {"obligation", "prohibition", "permission", "definition"}
TEXT_STATUSES = {"needs_review", "approved", "rejected"}
ANNOTATION_STATUSES = {"needs_review", "reviewed", "adjudicated", "rejected"}
SPAN_LISTS = ("actors", "actions", "conditions", "constraints", "exceptions")


def _issue(issues: list[dict], line: int, code: str, message: str) -> None:
    issues.append({"line": line, "code": code, "message": message})


def _validate_span(span: object, text: str, line: int, path: str, issues: list[dict]) -> None:
    if not isinstance(span, dict):
        _issue(issues, line, "span_not_object", path)
        return
    value, start, end = span.get("value"), span.get("start"), span.get("end")
    if not isinstance(value, str) or not isinstance(start, int) or not isinstance(end, int):
        _issue(issues, line, "span_type", path)
        return
    if start < 0 or end <= start or end > len(text):
        _issue(issues, line, "span_bounds", f"{path}: {start}:{end} for length {len(text)}")
        return
    if text[start:end] != value:
        _issue(issues, line, "span_text_mismatch", f"{path}: expected {text[start:end]!r}, got {value!r}")


def _validate_clauses(row: dict, text: str, line: int, issues: list[dict]) -> None:
    clauses = row.get("clauses")
    if not isinstance(clauses, list):
        _issue(issues, line, "clauses_not_array", "clauses must be an array")
        return
    clause_ids: set[str] = set()
    for ci, clause in enumerate(clauses):
        path = f"clauses[{ci}]"
        if not isinstance(clause, dict):
            _issue(issues, line, "clause_not_object", path)
            continue
        clause_id = clause.get("clause_id")
        if not isinstance(clause_id, str) or not clause_id:
            _issue(issues, line, "missing_clause_id", path)
        elif clause_id in clause_ids:
            _issue(issues, line, "duplicate_clause_id", clause_id)
        else:
            clause_ids.add(clause_id)
        _validate_span(clause.get("clause_span"), text, line, f"{path}.clause_span", issues)
        modality = clause.get("modality")
        if not isinstance(modality, dict) or modality.get("label") not in MODALITIES:
            _issue(issues, line, "invalid_modality", path)
        else:
            evidence = modality.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                _issue(issues, line, "missing_modality_evidence", path)
            else:
                for si, span in enumerate(evidence):
                    _validate_span(span, text, line, f"{path}.modality.evidence[{si}]", issues)
        known_ids: set[str] = set()
        for list_name in SPAN_LISTS:
            spans = clause.get(list_name)
            if not isinstance(spans, list):
                _issue(issues, line, "field_not_array", f"{path}.{list_name}")
                continue
            if list_name == "actions" and not spans:
                _issue(issues, line, "missing_action", path)
            for si, span in enumerate(spans):
                _validate_span(span, text, line, f"{path}.{list_name}[{si}]", issues)
                if isinstance(span, dict):
                    span_id = span.get("id")
                    if not isinstance(span_id, str) or not span_id:
                        _issue(issues, line, "missing_span_id", f"{path}.{list_name}[{si}]")
                    elif span_id in known_ids:
                        _issue(issues, line, "duplicate_span_id", span_id)
                    else:
                        known_ids.add(span_id)
        mapping = clause.get("actor_action_map")
        if not isinstance(mapping, list):
            _issue(issues, line, "map_not_array", path)
        else:
            for mi, pair in enumerate(mapping):
                if not isinstance(pair, dict):
                    _issue(issues, line, "map_not_object", f"{path}.actor_action_map[{mi}]")
                    continue
                actor_id, action_id = pair.get("actor_id"), pair.get("action_id")
                if actor_id is not None and actor_id not in known_ids:
                    _issue(issues, line, "unknown_actor_id", str(actor_id))
                if action_id not in known_ids:
                    _issue(issues, line, "unknown_action_id", str(action_id))
        relations = clause.get("order_relations")
        if not isinstance(relations, list):
            _issue(issues, line, "relations_not_array", path)
        else:
            for ri, relation in enumerate(relations):
                if not isinstance(relation, dict):
                    _issue(issues, line, "relation_not_object", f"{path}.order_relations[{ri}]")
                    continue
                for key in ("before_action_id", "after_action_id"):
                    if relation.get(key) not in known_ids:
                        _issue(issues, line, "unknown_order_action_id", f"{path}.{key}")
                evidence = relation.get("evidence")
                if not isinstance(evidence, list):
                    _issue(issues, line, "order_evidence_not_array", path)
                else:
                    for si, span in enumerate(evidence):
                        _validate_span(span, text, line, f"{path}.order_relations[{ri}].evidence[{si}]", issues)


def validate_pack(path: Path) -> dict:
    issues: list[dict] = []
    rows: list[dict] = []
    ids: set[str] = set()
    if not path.exists():
        return {"path": str(path), "record_count": 0, "format_valid": False, "human_review_ready": False, "freeze_ready": False, "issues": [{"line": 0, "code": "missing_file", "message": str(path)}]}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                _issue(issues, line_number, "invalid_json", str(exc))
                continue
            rows.append(row)
            sample_id = row.get("sample_id")
            if not isinstance(sample_id, str) or not sample_id:
                _issue(issues, line_number, "missing_sample_id", "sample_id")
            elif sample_id in ids:
                _issue(issues, line_number, "duplicate_sample_id", sample_id)
            else:
                ids.add(sample_id)
            if row.get("schema_version") != "1.0.0" or row.get("do_not_auto_score") is not True:
                _issue(issues, line_number, "contract_marker", "schema_version/do_not_auto_score")
            source = row.get("source")
            if not isinstance(source, dict) or not all(isinstance(source.get(k), str) and source.get(k) for k in ("source_text_de_ocr", "candidate_text_en")):
                _issue(issues, line_number, "invalid_source", "missing source texts")
                candidate_text = ""
            else:
                candidate_text = source["candidate_text_en"]
            text_review = row.get("text_review")
            if not isinstance(text_review, dict) or text_review.get("status") not in TEXT_STATUSES:
                _issue(issues, line_number, "invalid_text_review", "text_review")
                approved_text = candidate_text
            else:
                approved_text = text_review.get("approved_text_en") or candidate_text
                if text_review.get("status") == "approved":
                    for key in ("reviewer", "reviewed_at", "approved_text_en"):
                        if not text_review.get(key):
                            _issue(issues, line_number, "incomplete_text_approval", key)
            annotation = row.get("annotation_review")
            if not isinstance(annotation, dict) or annotation.get("status") not in ANNOTATION_STATUSES:
                _issue(issues, line_number, "invalid_annotation_review", "annotation_review")
                annotation_status = None
            else:
                annotation_status = annotation.get("status")
                if annotation_status in {"reviewed", "adjudicated"}:
                    for key in ("reviewer", "reviewed_at", "confidence"):
                        if annotation.get(key) in (None, ""):
                            _issue(issues, line_number, "incomplete_annotation_review", key)
            _validate_clauses(row, approved_text, line_number, issues)
            if annotation_status in {"reviewed", "adjudicated"} and not row.get("clauses") and not annotation.get("no_normative_clause_reason"):
                _issue(issues, line_number, "empty_review_without_reason", sample_id or "unknown")
    format_valid = not issues and len(rows) == 150 and len(ids) == 150
    if len(rows) != 150:
        _issue(issues, 0, "wrong_record_count", f"expected 150, found {len(rows)}")
        format_valid = False
    text_approved = sum(row.get("text_review", {}).get("status") == "approved" for row in rows)
    annotation_done = sum(row.get("annotation_review", {}).get("status") in {"reviewed", "adjudicated"} for row in rows)
    freeze_ready = format_valid and text_approved == 150 and annotation_done == 150
    return {
        "path": str(path),
        "record_count": len(rows),
        "unique_ids": len(ids),
        "text_approved": text_approved,
        "annotation_reviewed": annotation_done,
        "needs_text_review": len(rows) - text_approved,
        "needs_annotation_review": len(rows) - annotation_done,
        "format_valid": format_valid,
        "human_review_ready": format_valid and len(rows) == 150,
        "freeze_ready": freeze_ready,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, nargs="?", default=DEFAULT_INPUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-freeze-ready", action="store_true")
    args = parser.parse_args()
    result = validate_pack(args.path)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Records: {result['record_count']} (unique IDs: {result.get('unique_ids', 0)})")
        print(f"Format valid / ready for human review: {result['format_valid']}")
        print(f"Text approved: {result.get('text_approved', 0)}/150")
        print(f"Semantic annotation reviewed: {result.get('annotation_reviewed', 0)}/150")
        print(f"Ready to freeze: {result['freeze_ready']}")
        for issue in result["issues"][:20]:
            print(f"  line {issue['line']} [{issue['code']}] {issue['message']}")
    if not result["format_valid"]:
        return 1
    if args.require_freeze_ready and not result["freeze_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
