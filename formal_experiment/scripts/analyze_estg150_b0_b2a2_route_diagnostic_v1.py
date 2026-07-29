"""Build the read-only B2a2 route diagnostic from frozen development evidence.

This script does not run CoreNLP, modify Gold, read the S2.4 test dataset, or
create method predictions.  It compares the immutable v10-A/B2a attempts,
uses frozen Layer E only for offline Gold alignment, and runs the already
locked checkpoint in inference-only mode to recover probability vectors for
the exact aligned German clause texts already used by the parent pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.b0_v10.alignment import align_de_to_en_units  # noqa: E402
from bpc_hybrid.b0_v10.clause_probability_adapter_b2a2 import (  # noqa: E402
    EXPECTED_LABELS,
    ClauseProbabilityVector,
    predict_clause_probability_vectors,
)
from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    Estg150B0DevelopmentError,
    build_canonical_gold_records,
    load_object,
    sha256_file,
)
from bpc_hybrid.stage2_evaluation_v3 import clause_iou_pairs  # noqa: E402
from bpc_hybrid.sun_style.sun_b0 import (  # noqa: E402
    LockedBertTextCNNInference,
    load_s26_config,
)


RUN_ID = "s27_estg150_b0_b2a2_route_diagnostic_v1"
DEFAULT_OUTPUT = ROOT / "outputs/development" / RUN_ID
V10_MANIFEST = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/manifest.json"
V10_ATTEMPTS = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json"
V10_EVALUATION = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/evaluation_all150.json"
B2A_MANIFEST = ROOT / "outputs/development/s27_estg150_b0_enhanced_b2a/manifest.json"
B2A_ATTEMPTS = ROOT / "outputs/development/s27_estg150_b0_enhanced_b2a/b0_attempts.json"
B2A_EVALUATION = ROOT / "outputs/development/s27_estg150_b0_enhanced_b2a/evaluation_all150.json"
B2A_PREREG = ROOT / "configs/models/estg150_b0_b2a_preregistration_v1.json"
LAYER_E = ROOT / "data/development/human_review/estg_150_human_correction_v1.json"
MEMBERSHIP = ROOT / "data/development/estg/estg_150_membership_hashes.json"
S26_CONFIG = ROOT / "configs/models/sun_b0_s26_candidate_B_v1.json"
CHECKPOINT = ROOT / "outputs/development/s24_candidate_B_invsqrt_weighted_seed20260717_v1/best_model.pt"
EVALUATOR = ROOT / "configs/stage2_evaluator_s210_v3.json"
ADAPTER = ROOT / "src/bpc_hybrid/b0_v10/clause_probability_adapter_b2a2.py"

EXPECTED_HASHES = {
    V10_MANIFEST: "88070fab4da3f7c708f055f6bc391b78cc888761c3d6fe117d17673c2c382315",
    B2A_MANIFEST: "60283d2309f01e3b93ea76bde6eabc97919ccd305d1e00e6115b0d80d9e564b1",
    B2A_PREREG: "58ed8b512917c7eb8466f73814b672e016134f2c58018e251eee905014ced94f",
}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _load_array(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise Estg150B0DevelopmentError(f"expected JSON object array: {path}")
    return value


def _verify_inputs() -> None:
    for path in (
        V10_MANIFEST,
        V10_ATTEMPTS,
        V10_EVALUATION,
        B2A_MANIFEST,
        B2A_ATTEMPTS,
        B2A_EVALUATION,
        B2A_PREREG,
        LAYER_E,
        MEMBERSHIP,
        S26_CONFIG,
        CHECKPOINT,
        EVALUATOR,
        ADAPTER,
        Path(__file__).resolve(),
    ):
        if not path.is_file():
            raise Estg150B0DevelopmentError(f"required diagnostic input missing: {path}")
    for path, expected in EXPECTED_HASHES.items():
        if sha256_file(path) != expected:
            raise Estg150B0DevelopmentError(f"baseline hash mismatch: {path}")


def _attempt_map(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for attempt in attempts:
        sample_id = attempt.get("sample_id")
        if (
            not isinstance(sample_id, str)
            or sample_id in out
            or attempt.get("request_status") != "ok"
            or not isinstance(attempt.get("record"), Mapping)
        ):
            raise Estg150B0DevelopmentError("attempt identity/status is invalid")
        out[sample_id] = attempt
    return out


def _clause_key(sample_id: str, clause: Mapping[str, Any]) -> tuple[str, str]:
    clause_id = clause.get("clause_id")
    if not isinstance(clause_id, str):
        raise Estg150B0DevelopmentError("clause_id is missing")
    return sample_id, clause_id


def _route_counts(attempts: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for attempt in attempts:
        for clause in attempt["record"].get("clauses") or []:
            route = clause.get("modality", {}).get("route")
            if not isinstance(route, str):
                raise Estg150B0DevelopmentError("modality route is missing")
            counts[route] += 1
    return dict(sorted(counts.items()))


def _fallback_keys(attempts: Sequence[Mapping[str, Any]]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for attempt in attempts:
        sample_id = attempt["sample_id"]
        for clause in attempt["record"].get("clauses") or []:
            if clause.get("modality", {}).get("route") == "record_level_classifier_fallback":
                keys.add(_clause_key(sample_id, clause))
    return keys


def _predict_batched(
    inference: LockedBertTextCNNInference,
    texts: Sequence[str],
    *,
    batch_size: int = 16,
) -> list[ClauseProbabilityVector]:
    result: list[ClauseProbabilityVector] = []
    for start in range(0, len(texts), batch_size):
        result.extend(predict_clause_probability_vectors(inference, texts[start : start + batch_size]))
    return result


def _gold_alignment_by_prediction(
    gold_clauses: Sequence[Mapping[str, Any]],
    predicted_clauses: Sequence[Mapping[str, Any]],
) -> dict[int, dict[str, Any]]:
    pairs, _, _, scores = clause_iou_pairs(gold_clauses, predicted_clauses, minimum_iou=0.5)
    return {
        pred_i: {
            "status": "matched",
            "gold_index": gold_i,
            "iou": float(scores[(gold_i, pred_i)]),
            "gold_label": gold_clauses[gold_i]["modality"]["label"],
        }
        for gold_i, pred_i in pairs
    }


def _counter(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _probability_payload(vector: ClauseProbabilityVector, input_kind: str) -> dict[str, Any]:
    return {
        "input_kind": input_kind,
        "input_text_sha256": _sha256_text(vector.text),
        "label": vector.top_label,
        "confidence": vector.top_confidence,
        "probabilities": dict(vector.probabilities),
        "probability_sum": math.fsum(vector.probabilities.values()),
    }


def build_diagnostic(*, device: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    v10_attempts = _load_array(V10_ATTEMPTS)
    b2a_attempts = _load_array(B2A_ATTEMPTS)
    v10_by_id = _attempt_map(v10_attempts)
    b2a_by_id = _attempt_map(b2a_attempts)
    if set(v10_by_id) != set(b2a_by_id) or len(v10_by_id) != 150:
        raise Estg150B0DevelopmentError("v10-A/B2a attempt membership differs")

    v10_routes = _route_counts(v10_attempts)
    b2a_routes = _route_counts(b2a_attempts)
    v10_manifest = load_object(V10_MANIFEST)
    b2a_manifest = load_object(B2A_MANIFEST)
    if v10_routes != v10_manifest["runtime"]["modality_route_counts"]:
        raise Estg150B0DevelopmentError("v10-A route counts disagree with manifest")
    if b2a_routes != b2a_manifest["runtime"]["modality_route_counts"]:
        raise Estg150B0DevelopmentError("B2a route counts disagree with manifest")

    v10_fallback = _fallback_keys(v10_attempts)
    b2a_fallback = _fallback_keys(b2a_attempts)
    new_fallback = sorted(b2a_fallback - v10_fallback)
    if len(v10_fallback) != 20 or len(b2a_fallback) != 60 or len(new_fallback) != 40:
        raise Estg150B0DevelopmentError("expected the preregistered 20 -> 60 fallback expansion")

    gold, source_records = build_canonical_gold_records(LAYER_E, MEMBERSHIP)
    gold_by_id = {record["sample_id"]: record for record in gold}
    source_by_id = {record["sample_id"]: record for record in source_records}
    if set(gold_by_id) != set(v10_by_id) or set(source_by_id) != set(v10_by_id):
        raise Estg150B0DevelopmentError("Gold/source membership differs from attempts")

    clause_inputs: list[str] = []
    record_inputs: list[str] = []
    prepared: list[dict[str, Any]] = []
    new_keys = set(new_fallback)
    for sample_id in sorted(v10_by_id):
        v10_clauses = v10_by_id[sample_id]["record"].get("clauses") or []
        b2a_clauses = b2a_by_id[sample_id]["record"].get("clauses") or []
        if len(v10_clauses) != len(b2a_clauses):
            raise Estg150B0DevelopmentError(f"clause count changed for {sample_id}")
        source_text = v10_by_id[sample_id]["record"]["source_text"]
        en_texts: list[str] = []
        for v_clause, b_clause in zip(v10_clauses, b2a_clauses, strict=True):
            if (
                v_clause.get("clause_id") != b_clause.get("clause_id")
                or v_clause.get("clause_span") != b_clause.get("clause_span")
            ):
                raise Estg150B0DevelopmentError(f"v10-A/B2a segmentation drift for {sample_id}")
            span = v_clause["clause_span"]
            text = source_text[int(span["start"]) : int(span["end"])]
            if text != span["text"]:
                raise Estg150B0DevelopmentError("predicted clause span text mismatch")
            en_texts.append(text)
        source_record = source_by_id[sample_id]
        alignments = align_de_to_en_units(source_record["raw_text_de"], en_texts)
        if len(alignments) != len(v10_clauses):
            raise Estg150B0DevelopmentError("reconstructed alignment size mismatch")
        gold_map = _gold_alignment_by_prediction(gold_by_id[sample_id]["clauses"], v10_clauses)
        for clause_i, (v_clause, b_clause, alignment) in enumerate(
            zip(v10_clauses, b2a_clauses, alignments, strict=True)
        ):
            key = _clause_key(sample_id, b_clause)
            if key not in new_keys:
                continue
            if (
                not alignment.heuristic_supported
                or not alignment.text
                or not alignment.text.strip()
                or alignment.text.strip() == "."
            ):
                raise Estg150B0DevelopmentError("new B2a fallback lacks legal clause-local text")
            stored_status = b_clause.get("alignment", {}).get("status")
            if stored_status != alignment.status.value:
                raise Estg150B0DevelopmentError("reconstructed alignment status drifted")
            prepared.append(
                {
                    "sample_id": sample_id,
                    "clause_id": key[1],
                    "clause_i": clause_i,
                    "v10": v_clause,
                    "b2a": b_clause,
                    "alignment": alignment,
                    "gold_alignment": gold_map.get(
                        clause_i,
                        {"status": "unmatched", "gold_index": None, "iou": 0.0, "gold_label": None},
                    ),
                }
            )
            clause_inputs.append(alignment.text)
            record_inputs.append(source_record["raw_text_de"])
    if len(prepared) != 40:
        raise Estg150B0DevelopmentError("could not reconstruct all 40 new fallback clauses")

    inference = LockedBertTextCNNInference.load(ROOT, load_s26_config(S26_CONFIG), device=device)
    clause_vectors = _predict_batched(inference, clause_inputs)
    record_vectors = _predict_batched(inference, record_inputs)
    rows: list[dict[str, Any]] = []
    for item, clause_vector, record_vector in zip(
        prepared, clause_vectors, record_vectors, strict=True
    ):
        bdiag = item["b2a"]["modality"].get("diagnostic") or {}
        if clause_vector.top_label != bdiag.get("clause_classifier_label"):
            raise Estg150B0DevelopmentError("clause classifier top label does not reproduce B2a")
        if record_vector.top_label != bdiag.get("record_classifier_label"):
            raise Estg150B0DevelopmentError("record classifier top label does not reproduce B2a")
        evidence = bdiag.get("b2a_definition_evidence") or {}
        gold_alignment = item["gold_alignment"]
        gold_label = gold_alignment["gold_label"]
        v10_label = item["v10"]["modality"]["label"]
        b2a_label = item["b2a"]["modality"]["label"]
        explicit_marker = (
            "prohibition"
            if evidence.get("en_proh")
            else "permission"
            if evidence.get("en_perm")
            else "obligation"
            if evidence.get("en_obl_not_mean")
            else None
        )
        rows.append(
            {
                "sample_id": item["sample_id"],
                "clause_id": item["clause_id"],
                "alignment": {
                    "de_en_status": item["alignment"].status.value,
                    "de_en_supported": item["alignment"].heuristic_supported,
                    "de_en_validated": item["alignment"].validated,
                    "gold_clause_status": gold_alignment["status"],
                    "gold_clause_iou": gold_alignment["iou"],
                },
                "v10a": {
                    "route": item["v10"]["modality"]["route"],
                    "label": v10_label,
                    "correct": bool(gold_label is not None and v10_label == gold_label),
                },
                "b2a": {
                    "route": item["b2a"]["modality"]["route"],
                    "label": b2a_label,
                    "correct": bool(gold_label is not None and b2a_label == gold_label),
                    "rule": bdiag.get("b2a_rule"),
                },
                "clause_classifier": _probability_payload(
                    clause_vector, "aligned_german_clause_text"
                ),
                "record_classifier": _probability_payload(
                    record_vector, "full_german_record_text_diagnostic_only"
                ),
                "evidence": {
                    "strong_definition": bool(evidence.get("en_strong_def")),
                    "copular_definition": bool(evidence.get("copular_def_syntax")),
                    "german_definition_anchor": bool(evidence.get("de_def")),
                    "explicit_non_definition_marker": explicit_marker,
                },
                "gold_label": gold_label,
                "gold_use": "offline_aggregate_diagnostic_only",
            }
        )

    contradiction_count = sum(
        row["b2a"]["rule"] == "reject_loose_definition_record_even_if_def" for row in rows
    )
    summary = {
        "schema_version": "b2a2_route_diagnostic_summary@1.0.0",
        "run_id": RUN_ID,
        "claim_scope": "development_read_only_diagnostic",
        "route_counts": {"v10a": v10_routes, "b2a": b2a_routes},
        "fallback_comparison": {
            "v10a_count": len(v10_fallback),
            "b2a_count": len(b2a_fallback),
            "new_in_b2a_count": len(new_fallback),
            "b2a_only_rows_written": len(rows),
        },
        "contradiction_path": {
            "name": "reject_loose_definition_record_even_if_def",
            "count_in_new_fallback_rows": contradiction_count,
            "count_in_all_b2a_clauses": sum(
                clause.get("modality", {}).get("diagnostic", {}).get("b2a_rule")
                == "reject_loose_definition_record_even_if_def"
                for attempt in b2a_attempts
                for clause in attempt["record"].get("clauses") or []
            ),
        },
        "probability_legality": {
            "available": True,
            "source": "locked_candidate_B_checkpoint_softmax_via_versioned_read_only_adapter",
            "labels_in_checkpoint_order": list(EXPECTED_LABELS),
            "input_unit": "same_aligned_german_clause_text_used_by_v10a_b2a_clause_classifier",
            "record_text_used_for_clause_vector": False,
            "all_clause_vectors_complete": all(
                set(row["clause_classifier"]["probabilities"]) == set(EXPECTED_LABELS)
                for row in rows
            ),
            "all_clause_probability_sums_valid": all(
                math.isclose(row["clause_classifier"]["probability_sum"], 1.0, abs_tol=1e-6)
                for row in rows
            ),
            "stored_clause_top_labels_reproduced": len(rows),
            "stored_record_top_labels_reproduced": len(rows),
            "placeholder_classifier_count": 0,
        },
        "aggregate_buckets": {
            "alignment_status": _counter(row["alignment"]["de_en_status"] for row in rows),
            "b2a_rule": _counter(str(row["b2a"]["rule"]) for row in rows),
            "classifier_record_label_pair": _counter(
                f"{row['clause_classifier']['label']}|{row['record_classifier']['label']}"
                for row in rows
            ),
            "evidence_signature": _counter(
                "strong_def={}|copular={}|de_def={}|explicit={}".format(
                    row["evidence"]["strong_definition"],
                    row["evidence"]["copular_definition"],
                    row["evidence"]["german_definition_anchor"],
                    row["evidence"]["explicit_non_definition_marker"],
                )
                for row in rows
            ),
            "gold_label": _counter(str(row["gold_label"] or "unmatched") for row in rows),
            "correctness_transition": _counter(
                f"v10a_{'correct' if row['v10a']['correct'] else 'wrong'}->"
                f"b2a_{'correct' if row['b2a']['correct'] else 'wrong'}"
                for row in rows
            ),
        },
        "safety": {
            "gold_read_only": True,
            "gold_visible_to_production_inference": False,
            "network_called": False,
            "llm_api_called": False,
            "s2_4_test_dataset_read": False,
            "s2_4_test_metrics_used": False,
            "independent82_read_or_used": False,
            "model_retrained": False,
            "shared_v10a_or_b2a_implementation_modified": False,
            "sample_id_rules_created": False,
        },
    }
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        _verify_inputs()
        output_dir = args.output_dir.resolve()
        output_dir.relative_to((ROOT / "outputs/development").resolve())
        if output_dir.exists():
            raise Estg150B0DevelopmentError(f"refusing to overwrite: {output_dir}")
        rows, summary = build_diagnostic(device=args.device)
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
        if staging.exists():
            raise Estg150B0DevelopmentError(f"staging path already exists: {staging}")
        staging.mkdir()
        try:
            rows_path = staging / "new_record_fallback_clauses.jsonl"
            summary_path = staging / "summary.json"
            _write_jsonl(rows_path, rows)
            _write_json(summary_path, summary)
            manifest = {
                "schema_version": "b2a2_route_diagnostic_manifest@1.0.0",
                "run_id": RUN_ID,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "status": "succeeded_read_only_diagnostic",
                "claim_scope": "development",
                "inputs": {
                    str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
                    for path in (
                        V10_MANIFEST,
                        V10_ATTEMPTS,
                        V10_EVALUATION,
                        B2A_MANIFEST,
                        B2A_ATTEMPTS,
                        B2A_EVALUATION,
                        B2A_PREREG,
                        LAYER_E,
                        MEMBERSHIP,
                        S26_CONFIG,
                        CHECKPOINT,
                        EVALUATOR,
                    )
                },
                "scripts": {
                    str(Path(__file__).resolve().relative_to(ROOT)).replace("\\", "/"): sha256_file(
                        Path(__file__).resolve()
                    ),
                    str(ADAPTER.relative_to(ROOT)).replace("\\", "/"): sha256_file(ADAPTER),
                },
                "results": {
                    "new_record_fallback_clauses.jsonl": {
                        "sha256": sha256_file(rows_path),
                        "rows": len(rows),
                    },
                    "summary.json": {"sha256": sha256_file(summary_path)},
                },
                "route_counts": summary["route_counts"],
                "probability_legality": summary["probability_legality"],
                "safety": summary["safety"],
            }
            _write_json(staging / "manifest.json", manifest)
            staging.rename(output_dir)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "output_dir": str(output_dir),
                    "new_record_fallback_rows": len(rows),
                    "contradiction_count": summary["contradiction_path"]["count_in_all_b2a_clauses"],
                    "probability_legality": summary["probability_legality"],
                    "network_calls": 0,
                    "llm_api_calls": 0,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (Estg150B0DevelopmentError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"B2a2 route diagnostic failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
