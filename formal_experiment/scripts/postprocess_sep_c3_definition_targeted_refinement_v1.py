# -*- coding: utf-8 -*-
"""Recover canonical outputs from the already-sent 84 SEP-C3 definition-targeted calls.

No network call is made.  The live runner completed all scheduled API sends,
then aborted inside the full-150 Gold evaluator because this targeted suite
sent only the frozen 42-sample panel.  This script reparses the persisted raw
responses with the same frozen parser/canonicalizer and runs the same frozen
span and modality-label evaluators on an explicit 42-sample coarse panel-slice
view using the frozen G0.4 coarse transform.  The full-150 evaluator wrapper is
not used because it hard-requires 150 Gold records; the underlying frozen
evaluator is used unchanged.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SCRIPTS, SRC):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_sep_c3_definition_targeted_refinement_v1 as defrunner  # noqa: E402,F401
import run_sep_c3_targeted_refinement_v1 as tr  # noqa: E402
import run_sep_c3_modular_ablation_v1 as core  # noqa: E402
from bpc_hybrid.formal_stage2_evaluation import (  # noqa: E402
    evaluate_modality_labels,
    evaluate_span_metrics,
    published_gold_to_evaluator,
)
from bpc_hybrid.g04_coarse_view import coarse_record  # noqa: E402
from bpc_hybrid.sep_c3_modular_evaluation import (  # noqa: E402
    SPAN_FIELDS,
    _micro_prf,
    attempt_rows,
)
from bpc_hybrid.stage2_sun_literal_overlap import (  # noqa: E402
    evaluate_sun_literal_overlap,
)

PANEL_PATH = ROOT / "configs" / "sep_c3_definition_targeted_panel_v1.json"
GOLD_PATH = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
SUITE_ID = "SEP-C3-DEFINITION-TARGETED-REFINEMENT-001"
RUN_DIR = ROOT / "outputs" / "development" / "sep_c3_definition_targeted_refinement_v1"
SUMMARY_PATH = RUN_DIR / "postprocess_recovery_summary.json"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _targeted_panel_slice_evaluation(
    panel_gold: dict[str, Any],
    predictions: list[dict[str, Any]],
    *,
    arm: str,
) -> dict[str, Any]:
    coarse_gold = [coarse_record(record) for record in panel_gold["records"]]
    attempts = attempt_rows(predictions)
    method_id = f"direct_llm_definition_targeted_panel_slice_{arm}"
    raw = evaluate_sun_literal_overlap(
        coarse_gold,
        attempts,
        dataset_id="sep_c3_definition_targeted_panel_42_sample_slice",
        method_id=method_id,
    )
    official = evaluate_span_metrics(
        coarse_gold,
        attempts,
        dataset_id="sep_c3_definition_targeted_panel_42_sample_slice",
        method_id=method_id,
        view="coarse_sentence_level_targeted_panel_slice",
    )
    per_field = raw.get("per_field") or {}
    five = {field: dict(per_field.get(field) or {}) for field in SPAN_FIELDS}
    for field in SPAN_FIELDS:
        official_field = (official.get("span_fields") or {}).get(field) or {}
        for key in ("ground_truth", "extracted", "precision", "recall", "f1"):
            if official_field.get(key) != five[field].get(key):
                raise RuntimeError(
                    f"frozen evaluator parity mismatch for {field}.{key}: "
                    f"official={official_field.get(key)!r} raw={five[field].get(key)!r}"
                )
    mean_f1 = sum(float(value.get("f1") or 0.0) for value in five.values()) / len(
        SPAN_FIELDS
    )
    labels = evaluate_modality_labels(
        published_gold_to_evaluator(panel_gold),
        attempts,
    )
    return {
        "schema_version": "sep_c3_definition_targeted_panel_slice_evaluation@1.0.0",
        "suite_id": SUITE_ID,
        "arm": arm,
        "method_id": method_id,
        "status": "postprocessed_from_persisted_raw_responses",
        "evaluation_unit": "coarse_sentence_level_panel_slice",
        "gold_scope": {
            "sample_count": len(panel_gold["records"]),
            "clause_count": sum(
                len(record.get("clauses") or [])
                for record in panel_gold["records"]
            ),
            "description": "all clauses in the frozen 42 panel samples",
            "full_150_evaluator_wrapper_used": False,
            "reason_full_wrapper_not_used": (
                "the frozen full-150 coarse wrapper hard-requires 150 Gold "
                "records; this targeted suite sent only the 42 panel samples"
            ),
        },
        "primary_metric": "coarse_five_field_mean_f1",
        "five_fields": five,
        "coarse_five_field_mean_f1": mean_f1,
        "coarse_five_field_micro": _micro_prf(five),
        "modality_labels": labels,
        "official_formal_view": official,
        "denominator": len(attempts),
        "failed_count": sum(
            1 for attempt in attempts
            if attempt.get("request_status") != "ok"
        ),
    }


def main() -> int:
    panel = _read_json(PANEL_PATH)
    full_gold = _read_json(GOLD_PATH)
    panel_ids = {str(value) for value in panel["selected_sample_ids"]}
    panel_gold = {
        "schema_version": full_gold.get("schema_version"),
        "records": [
            record for record in full_gold["records"]
            if str(record["sample_id"]) in panel_ids
        ],
    }
    if {str(record["sample_id"]) for record in panel_gold["records"]} != panel_ids:
        raise SystemExit("panel Gold subset membership mismatch")

    all_samples = core.samples(core.SAMPLES_PER_ARM)
    sample_by_id = {str(row["sample_id"]): row for row in all_samples}
    panel_rows = [sample_by_id[sid] for sid in panel["selected_sample_ids"]]

    arms: dict[str, dict[str, Any]] = {}
    for arm in ("BASE", "R_DEF"):
        run_dir = RUN_DIR / arm / "repeat-01"
        raw_rows = _read_jsonl(run_dir / "raw_responses.jsonl")
        raw_by_sid = {str(row["sample_id"]): row for row in raw_rows}
        if set(raw_by_sid) != panel_ids:
            raise SystemExit(f"{arm}: raw response membership mismatch")
        predictions = [
            tr._prediction_with_provenance(
                raw_by_sid[str(row["sample_id"])], arm, str(row["text"])
            )
            for row in panel_rows
        ]
        failed = [
            row for row in predictions
            if row.get("request_status") != "ok"
        ]
        (run_dir / "canonical_predictions.jsonl").write_text(
            "".join(
                json.dumps(row, ensure_ascii=False) + "\n"
                for row in predictions
            ),
            encoding="utf-8",
            newline="\n",
        )
        (run_dir / "failed_samples.jsonl").write_text(
            "".join(
                json.dumps(row, ensure_ascii=False) + "\n"
                for row in failed
            ),
            encoding="utf-8",
            newline="\n",
        )
        evaluation = _targeted_panel_slice_evaluation(
            panel_gold, predictions, arm=arm
        )
        _write_json(run_dir / "targeted_panel_slice_evaluation.json", evaluation)
        status_counts = {
            key: dict(Counter(str(row.get(key)) for row in predictions))
            for key in (
                "request_status",
                "output_parse_status",
                "input_binding_status",
                "canonical_validation_status",
            )
        }
        manifest = {
            "schema_version": "sep_c3_definition_targeted_manifest@1.0.1",
            "suite_id": SUITE_ID,
            "arm": arm,
            "repeat_id": "repeat-01",
            "status": "recovered_from_raw_without_new_api_calls",
            "sample_count": len(panel_ids),
            "actual_call_count": len(raw_rows),
            "failed_count": len(failed),
            "processing_status_counts": status_counts,
            "evaluation_artifact": (
                "targeted_panel_slice_evaluation.json"
            ),
            "gold_scope": evaluation["gold_scope"],
            "raw_responses_sha256": __import__("hashlib").sha256(
                (run_dir / "raw_responses.jsonl").read_bytes()
            ).hexdigest(),
            "canonical_predictions_sha256": __import__("hashlib").sha256(
                (run_dir / "canonical_predictions.jsonl").read_bytes()
            ).hexdigest(),
        }
        _write_json(run_dir / "manifest.json", manifest)
        arms[arm] = {
            "raw_response_count": len(raw_rows),
            "prediction_count": len(predictions),
            "failed_count": len(failed),
            "status_counts": status_counts,
            "manifest": str(
                (run_dir / "manifest.json").relative_to(ROOT)
            ).replace("\\", "/"),
            "canonical_predictions_jsonl": str(
                (run_dir / "canonical_predictions.jsonl").relative_to(ROOT)
            ).replace("\\", "/"),
            "targeted_panel_slice_evaluation": str(
                (run_dir / "targeted_panel_slice_evaluation.json").relative_to(ROOT)
            ).replace("\\", "/"),
        }

    summary = {
        "schema_version": "sep_c3_definition_targeted_postprocess_recovery@1.0.1",
        "suite_id": SUITE_ID,
        "status": "postprocessed_without_new_api_calls",
        "api_calls_sent": 84,
        "additional_api_calls": 0,
        "explanation": (
            "All 84 scheduled API sends completed and were persisted.  The live "
            "runner then aborted in the frozen full-150 coarse evaluator because "
            "the targeted panel supplies 42 of 150 Gold sample IDs.  This "
            "recovery reparsed the persisted raw responses with the same parser "
            "and canonicalizer and ran the underlying frozen span and "
            "modality-label evaluators on a 42-sample coarse panel slice built "
            "with the frozen G0.4 transform; no Gold labels were altered."
        ),
        "gold_scope_used_for_recovered_coarse_evaluation": {
            "sample_count": len(panel_ids),
            "clause_count": sum(
                len(record.get("clauses") or [])
                for record in panel_gold["records"]
            ),
            "rule": "all clauses in the 42 frozen panel samples",
        },
        "arms": arms,
    }
    _write_json(SUMMARY_PATH, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
