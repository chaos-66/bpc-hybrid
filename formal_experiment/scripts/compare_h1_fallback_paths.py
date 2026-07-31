"""Read-only H1 fallback-path comparison report (S2.8C).

Compares a persisted B0 artifact with one H1 run (predictions + telemetry
+ manifest) over the same sample/clause set and reports:

* changed prediction / sample / clause counts (IDs only, never text);
* proposed / valid / accepted / effective / rejected patch counts;
* rejection-reason counts (normalized codes) and per-field change counts;
* the ``h1_non_identity_gate``::

      h1_non_identity_gate =
          llm_calls > 0
          AND valid_responses > 0
          AND accepted_effective_patches > 0
          AND changed_predictions > 0

  Plan-only runs must report gate=false; a valid offline-replay run with
  effective patches must report gate=true.

* P/R/F1: NOT computed unless the user explicitly supplies a development
  reference via ``--reference`` that passes validation.  The script NEVER
  selects a reference itself, never reads Layer E, formal Gold,
  paper_validation results, ``.env``, and never calls any LLM/API.  With
  no reference the report states ``P/R not computed`` and labels
  harmful/no-op as ``unknown``.

The script is strictly read-only: it writes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.b0_artifact import load_b0_predictions, prediction_hash  # noqa: E402

_FORBIDDEN_REFERENCE_ROOTS = (
    "data/gold",
    "data/input",
    "data/development/human_review",
    "_retired",
    "references",
    "archive",
)
H1_NON_IDENTITY_GATE_FIELDS = (
    "llm_calls",
    "valid_response_count",
    "accepted_effective_patch_count",
    "prediction_changed_sample_count",
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"JSONL row {line_number} is not an object: {path}")
        rows.append(item)
    return rows


def _manifest_gate_value(manifest: dict[str, Any], field: str) -> bool:
    """Resolve a gate component from the H1 manifest.

    ``valid_response_count`` and ``accepted_effective_patch_count`` live
    under ``effective_patch``; the other components are top-level.
    """
    if field in ("valid_response_count", "accepted_effective_patch_count"):
        return bool(manifest.get("effective_patch", {}).get(field))
    return bool(manifest.get(field))


def _events_from_telemetry(telemetry_path: Path) -> list[dict[str, Any]]:
    return [
        event
        for row in _load_jsonl(telemetry_path)
        for event in row.get("patch_events", [])
        if isinstance(event, dict)
    ]


def _validate_reference(reference: Path) -> None:
    """Refuse any reference that is not an explicitly designated
    development file outside forbidden roots."""
    if not reference.is_file():
        raise ValueError(f"reference file does not exist: {reference}")
    resolved = reference.resolve()
    for root_name in _FORBIDDEN_REFERENCE_ROOTS:
        root = (_PROJECT_ROOT / root_name).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        raise ValueError(
            f"reference {reference} lies under forbidden root {root_name}; "
            "no label source is selected automatically"
        )
    if reference.name.startswith("paper_validation") or "paper_validation" in str(reference):
        raise ValueError(f"reference must not be a paper_validation artifact: {reference}")


def build_report(
    b0_predictions: Path,
    h1_predictions: Path,
    h1_telemetry: Path,
    h1_manifest: Path,
    reference: Path | None,
) -> dict[str, Any]:
    manifest = json.loads(h1_manifest.read_text(encoding="utf-8"))
    events = _events_from_telemetry(h1_telemetry)
    b0_batch = load_b0_predictions(b0_predictions)
    b0_by_sample = {item.record["sample_id"]: item.record for item in b0_batch}
    h1_rows = {row["sample_id"]: row for row in _load_jsonl(h1_predictions)}

    changed_samples: list[str] = []
    for sample_id, b0_record in b0_by_sample.items():
        h1_row = h1_rows.get(sample_id)
        if h1_row is None:
            changed_samples.append(sample_id)  # missing H1 row counts as a change
            continue
        if prediction_hash(h1_row) != prediction_hash(b0_record):
            changed_samples.append(sample_id)
    changed_samples.sort()

    audits = [
        event.get("effective_patch_audit", {})
        for event in events
        if isinstance(event.get("effective_patch_audit"), dict)
    ]
    proposed = sum(1 for audit in audits if audit.get("proposed_patch_sha256") is not None)
    valid = sum(
        1 for audit in audits if audit.get("merge_status") in ("accepted", "rejected")
    )
    accepted = sum(1 for audit in audits if audit.get("merge_status") == "accepted")
    effective = sum(1 for audit in audits if audit.get("effective_patch"))
    rejected = sum(1 for audit in audits if audit.get("merge_status") == "rejected")

    rejection_counts: dict[str, int] = {}
    changed_field_counts: dict[str, int] = {}
    for audit in audits:
        for code in audit.get("rejection_codes", []):
            rejection_counts[code] = rejection_counts.get(code, 0) + 1
        if audit.get("effective_patch"):
            for field in audit.get("changed_fields", []):
                changed_field_counts[field] = changed_field_counts.get(field, 0) + 1

    changed_clause_ids = sorted(
        {
            f"{event.get('sample_id')}/{event.get('clause_id')}"
            for event in events
            if event.get("effective_patch_audit", {}).get("semantic_changed")
        }
    )

    gate_components = {
        field: _manifest_gate_value(manifest, field)
        for field in H1_NON_IDENTITY_GATE_FIELDS
    }
    h1_non_identity_gate = all(gate_components.values())

    p_r_status = "not_computed"
    if reference is not None:
        _validate_reference(reference)
        p_r_status = (
            "reference_supplied_but_evaluator_not_implemented_in_this_checkpoint"
        )

    return {
        "schema_version": "h1_fallback_path_compare@1.0.0",
        "inputs": {
            "b0_predictions": str(b0_predictions),
            "h1_predictions": str(h1_predictions),
            "h1_telemetry": str(h1_telemetry),
            "h1_manifest": str(h1_manifest),
            "h1_execution_mode": manifest.get("execution_mode"),
            "h1_prompt_variant": manifest.get("prompt_variant"),
        },
        "b0_samples": len(b0_by_sample),
        "h1_samples": len(h1_rows),
        "changed_predictions": len(changed_samples),
        "changed_sample_ids": changed_samples,
        "changed_clause_ids": changed_clause_ids,
        "patch_counts": {
            "proposed": proposed,
            "valid": valid,
            "accepted": accepted,
            "effective": effective,
            "rejected": rejected,
        },
        "rejection_reason_counts": rejection_counts,
        "changed_field_counts": changed_field_counts,
        "harmful_or_noop": "unknown (no Gold-based judgement performed; "
        "only no_semantic_change is positively identified)",
        "pr_f1": {
            "status": p_r_status,
            "detail": (
                "no legitimate development reference was selected; refusing to read "
                "Layer E / formal Gold / paper_validation. Re-run with an explicit "
                "--reference to a user-designated development file to enable the "
                "same-evaluator B0/H1 P/R computation (evaluator wiring not yet "
                "implemented in this checkpoint)."
                if reference is None
                else "reference accepted but evaluator wiring is not implemented "
                "in this checkpoint; no P/R numbers are reported."
            ),
        },
        "h1_non_identity_gate": h1_non_identity_gate,
        "h1_non_identity_gate_components": gate_components,
        "safety": {
            "gold_read": False,
            "layer_e_read": False,
            "paper_validation_read": False,
            "llm_api_called": False,
            "reference_used": reference is not None,
            "read_only": True,
        },
    }


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--b0-predictions", type=Path, required=True)
    parser.add_argument("--h1-predictions", type=Path, required=True)
    parser.add_argument("--h1-telemetry", type=Path, required=True)
    parser.add_argument("--h1-manifest", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _make_parser().parse_args(argv)
    try:
        report = build_report(
            args.b0_predictions,
            args.h1_predictions,
            args.h1_telemetry,
            args.h1_manifest,
            args.reference,
        )
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Refusing to report: {exc}")
        return 2
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
