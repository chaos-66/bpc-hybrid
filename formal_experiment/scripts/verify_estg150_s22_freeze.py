"""Verify and receipt the completed EStG-150 S2.2 human annotation freeze.

This command is deliberately narrower than formal Gold publication.  It reads
the human-owned Layer E file, runs the canonical strict validator, and emits a
deterministic receipt only when all 150 records are adjudicated.  It does not
copy data into ``data/gold``, change a human decision, run a method, or call an
LLM/API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.estg150_validator import (  # noqa: E402
    SIX_ELEMENT_FIELDS,
    SPAN_FIELDS,
    validate_doc_dict,
)


DEFAULT_SOURCE = (
    ROOT / "data/development/human_review/estg_150_human_correction_v1.json"
)
DEFAULT_MEMBERSHIP = (
    ROOT / "data/development/estg/estg_150_membership_hashes.json"
)
DEFAULT_SCHEMA = ROOT / "configs/schemas/human_gold_review.schema.json"
DEFAULT_MANIFEST = (
    ROOT / "outputs/reports/s22_estg150_human_annotation_freeze_v1.manifest.json"
)


class AnnotationFreezeError(ValueError):
    """Raised when the S2.2 annotation freeze cannot be receipted safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnnotationFreezeError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise AnnotationFreezeError(f"{label} root must be an object: {path}")
    return value


def _artifact(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        display = resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        display = str(resolved)
    return {
        "path": display,
        "sha256": sha256_file(resolved),
        "byte_size": resolved.stat().st_size,
    }


def build_manifest(
    source_path: Path = DEFAULT_SOURCE,
    membership_path: Path = DEFAULT_MEMBERSHIP,
    schema_path: Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    source = Path(source_path).resolve()
    membership = Path(membership_path).resolve()
    schema = Path(schema_path).resolve()
    for label, path in (
        ("Layer E", source),
        ("membership hashes", membership),
        ("human-review schema", schema),
    ):
        if not path.is_file():
            raise AnnotationFreezeError(f"missing {label}: {path}")

    document = _load_object(source, "Layer E human correction")
    membership_doc = _load_object(membership, "EStG-150 membership hashes")
    _load_object(schema, "human-review schema")
    validation = validate_doc_dict(document, membership)
    if not validation.get("format_valid"):
        raise AnnotationFreezeError(
            "Layer E format validation failed: "
            + repr(validation.get("format_errors", [])[:8])
        )
    if not validation.get("review_ready") or not validation.get("freeze_ready"):
        raise AnnotationFreezeError(
            "Layer E is not freeze-ready: "
            f"review_blockers={validation.get('review_blockers', [])[:8]!r}; "
            f"freeze_blockers={validation.get('freeze_blockers', [])[:8]!r}"
        )

    selected = membership_doc.get("selected_membership") or {}
    member_ids = selected.get("sorted_legacy_record_ids")
    if (
        not isinstance(member_ids, list)
        or len(member_ids) != 150
        or len(set(member_ids)) != 150
        or not all(isinstance(item, int) and not isinstance(item, bool) for item in member_ids)
    ):
        raise AnnotationFreezeError("locked membership must contain 150 unique integer IDs")
    records = document.get("records") or []
    actual_ids = sorted(record.get("legacy_record_id") for record in records)
    if actual_ids != sorted(member_ids):
        raise AnnotationFreezeError("Layer E membership differs from the locked 150 IDs")

    top_level_decisions: dict[str, Counter[str]] = {
        field: Counter() for field in ("translation", *SIX_ELEMENT_FIELDS)
    }
    modality_values: Counter[str] = Counter()
    span_counts: Counter[str] = Counter()
    span_decisions: Counter[str] = Counter()
    clause_modality_decisions: Counter[str] = Counter()
    clause_count = 0
    for record in records:
        decisions = record.get("decisions") or {}
        for field in top_level_decisions:
            top_level_decisions[field][str(decisions.get(field))] += 1
        clauses = (record.get("human_correction") or {}).get("clauses") or []
        clause_count += len(clauses)
        for clause in clauses:
            modality = clause.get("modality") or {}
            modality_values[str(modality.get("value"))] += 1
            clause_modality_decisions[str(modality.get("decision"))] += 1
            for plural in SPAN_FIELDS:
                singular = plural[:-1] if plural != "exceptions" else "exception"
                values = clause.get(plural) or []
                span_counts[singular] += len(values)
                for value in values:
                    span_decisions[str(value.get("decision"))] += 1

    validation_receipt = {
        key: validation[key]
        for key in (
            "format_valid",
            "review_ready",
            "freeze_ready",
            "n_records",
            "n_approved_en",
            "n_translation_unreviewed",
            "n_field_decisions_total",
            "n_field_decisions_unreviewed",
            "n_field_decisions_resolved",
            "n_records_incomplete",
            "n_records_fully_decided",
            "n_reviewed",
            "n_adjudicated",
            "review_state_counts",
            "format_errors",
            "review_blockers",
            "freeze_blockers",
        )
    }
    return {
        "schema_version": "estg150_s22_annotation_freeze_receipt@1.0.0",
        "run_id": "s22_estg150_human_annotation_freeze_v1",
        "task_id": "S2.2",
        "status": "succeeded_annotation_frozen_not_formal_gold_published",
        "dataset": {
            "dataset_id": "independently_reconstructed_estg_150_v1",
            "claim_label": "LLM-assisted, human-adjudicated annotation freeze",
            "membership_count": 150,
            "membership_payload_sha256": selected.get("membership_payload_sha256"),
            "sun_original_150": False,
            "exact_reproduction": False,
        },
        "validation": validation_receipt,
        "annotation_summary": {
            "clause_count": clause_count,
            "modality_values": dict(sorted(modality_values.items())),
            "span_counts": dict(sorted(span_counts.items())),
            "top_level_decisions": {
                field: dict(sorted(counts.items()))
                for field, counts in top_level_decisions.items()
            },
            "clause_modality_decisions": dict(
                sorted(clause_modality_decisions.items())
            ),
            "span_decisions": dict(sorted(span_decisions.items())),
        },
        "artifacts": {
            "human_correction_layer_e": _artifact(source),
            "membership_hashes": _artifact(membership),
            "human_review_schema": _artifact(schema),
        },
        "route_boundaries": {
            "annotation_scope": "sentence_only_approved_english_working_text",
            "german_to_english_fidelity_human_verified": False,
            "context_sidecar_used": False,
            "open_issue_ids": ["RWI-0001", "RWI-0007"],
            "formal_gold_publication_ready": False,
            "formal_stage2_method_run_authorized": False,
            "next_required_task": (
                "re-lock the Stage 2 context/language/input route before formal "
                "Gold publication or method evaluation"
            ),
        },
        "safety": {
            "human_correction_read_only": True,
            "human_decisions_modified": False,
            "data_gold_written": False,
            "data_input_written": False,
            "method_predictions_or_results_written": False,
            "llm_api_called": False,
            "network_called": False,
            "performance_evaluation": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--membership", type=Path, default=DEFAULT_MEMBERSHIP)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Create the deterministic receipt; never overwrite different bytes",
    )
    args = parser.parse_args()
    try:
        manifest = build_manifest(args.source, args.membership, args.schema)
        payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        if args.write:
            output = args.manifest_out.resolve()
            if output.exists():
                existing = output.read_text(encoding="utf-8")
                if existing != payload:
                    raise AnnotationFreezeError(f"refusing to overwrite drifted receipt: {output}")
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(payload, encoding="utf-8", newline="\n")
        print(
            "S2.2 annotation freeze verified: "
            f"records={manifest['validation']['n_records']}, "
            f"adjudicated={manifest['validation']['n_adjudicated']}, "
            f"clauses={manifest['annotation_summary']['clause_count']}; "
            "formal Gold publication remains blocked"
        )
        return 0
    except AnnotationFreezeError as exc:
        print(f"S2.2 annotation freeze failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
