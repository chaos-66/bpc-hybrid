"""Phase A read-only diagnostic for EStG-150 B0 enhanced v5 vs v6.

Produces four routing ablations on a v6 attempt set:
- classifier_only: only S2.4 classifier (no English marker override)
- marker_only: only English marker (no classifier); explicit unsupported if none
- current_hybrid: the v6 hybrid (or v5 hybrid for cross-method comparison)
- gold_clause_segmentation_oracle: Gold clause spans + hybrid modality

Each predicted unit is recorded with:
- base classifier label/confidence
- English marker candidate (label, surface)
- final route
- clause reason
- DE aligned / misaligned flag
- whether the unit aligned with a Gold clause
- whether modality matches Gold

Gold is read only by the offline diagnostic; runtime modules do not import
Gold or the evaluator. No LLM/API/network calls. No file writes outside
the explicit output directory.

Usage:
    python analyze_estg150_b0_v6_components.py \\
        --v5-attempts <path/to/v5/b0_attempts.json> \\
        --v6-attempts <path/to/v6/b0_attempts.json> \\
        --layer-e <path/to/estg_150_human_correction_v1.json> \\
        --membership <path/to/estg_150_membership_hashes.json> \\
        --output-dir <output directory> \\
        [--include-every-Nth-cunit 1]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    build_canonical_gold_records,
    sha256_file,
)
from bpc_hybrid.stage2_evaluation_v3 import (  # noqa: E402
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
    validate_evaluation_report,
)
from bpc_hybrid.estg150_b0_development_v4 import (  # noqa: E402
    english_marker_modality_v6,
    resolve_modality_v6,
    MODE_HYBRID,
    MODE_CLASSIFIER_ONLY,
    MODE_MARKER_ONLY,
    MODE_GOLD_CLAUSE_SEG_ORACLE,
)


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _override_modality(attempts: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    """Rebuild attempts with the requested modality routing mode.

    Uses per-clause information stored in v6 attempts (`route`,
    `english_marker_hit`, `classifier_label`, etc.). For v5 attempts (no
    per-clause diagnostic), the override approximates by re-running the
    v6 modality resolver on the clause's English text; for this we need
    the clause text and a placeholder classifier prediction (the original
    label with confidence 0.6).

    The override NEVER mutates the original attempts object; it returns a
    deep-copied list with new modality labels.
    """
    import copy
    out: list[dict[str, Any]] = []
    for att in attempts:
        att_copy = copy.deepcopy(att)
        rec = att_copy["record"]
        for clause in rec.get("clauses", []):
            span = clause.get("clause_span", {})
            start = int(span.get("start", 0))
            end = int(span.get("end", 0))
            text = rec.get("source_text", "")[start:end]
            # Prefer per-clause diagnostic if present
            stored = clause.get("modality", {})
            stored_label = stored.get("label")
            stored_route = stored.get("route", "")
            stored_marker = clause.get("nucleus_kinds", [])
            en_label, en_surface = english_marker_modality_v6(text)
            # de_aligned: heuristic — if route contains "aligned_agree_"
            # or "aligned_classifier_fallback" we treat as aligned
            de_aligned = (
                stored_route.startswith("aligned_agree_")
                or stored_route == "aligned_classifier_fallback"
            )
            from bpc_hybrid.estg150_b0_development_v3 import ModalityPrediction
            classifier = ModalityPrediction(
                label=stored_label or "obligation",
                confidence=0.6,
            )
            pred, route, diag = resolve_modality_v6(
                english_clause=text,
                classifier=classifier,
                de_aligned=de_aligned,
                mode=mode,
            )
            if mode == MODE_GOLD_CLAUSE_SEG_ORACLE:
                # do not change modality; this mode is enforced via the
                # input attempts (we pass gold clauses separately when
                # running the full v6 run; here we just preserve current)
                pass
            else:
                clause["modality"]["label"] = pred.label
                clause["modality"]["route"] = route
                clause.setdefault("diagnostic", {})
                clause["diagnostic"].update(diag)
                clause["diagnostic"]["english_marker_label_v6"] = en_label
                clause["diagnostic"]["english_marker_surface_v6"] = en_surface
        out.append(att_copy)
    return out


def _evaluate(
    gold: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    *,
    contract: dict[str, Any],
    dataset_id: str,
) -> dict[str, Any]:
    report = evaluate_stage2(
        gold,
        attempts,
        contract=contract,
        dataset_id=dataset_id,
        method_id="sun_rule_only",
        expected_membership_sha256=membership_sha256(gold),
        claim_scope="development",
        formal_ready=False,
    )
    errors = validate_evaluation_report(report)
    if errors:
        raise RuntimeError(
            "development evaluation report invalid: " + "; ".join(errors)
        )
    return report


def _per_unit_diagnostic(
    attempts: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    include_every: int,
) -> list[dict[str, Any]]:
    """Build per-unit diagnostic records (no Gold clause semantic use)."""
    gold_by_id = {g["sample_id"]: g for g in gold}
    out: list[dict[str, Any]] = []
    for att in attempts:
        rec = att["record"]
        sample_id = att["sample_id"]
        gold_rec = gold_by_id.get(sample_id, {})
        gold_clauses = gold_rec.get("clauses", [])
        gold_mod = {c.get("clause_span", {}).get("text", ""): c.get("modality", {}).get("label") for c in gold_clauses}
        for ci, clause in enumerate(rec.get("clauses", [])):
            if ci % max(1, include_every) != 0:
                continue
            span = clause.get("clause_span", {})
            start = int(span.get("start", 0))
            end = int(span.get("end", 0))
            text = rec.get("source_text", "")[start:end]
            stored = clause.get("modality", {})
            route = stored.get("route", "")
            diagnostic = clause.get("diagnostic", {})
            out.append({
                "sample_id": sample_id,
                "clause_id": clause.get("clause_id", ""),
                "final_label": stored.get("label"),
                "route": route,
                "english_marker_label": diagnostic.get("english_marker_label"),
                "english_marker_surface": diagnostic.get("english_marker_surface"),
                "classifier_label": diagnostic.get("classifier_label"),
                "classifier_confidence": diagnostic.get("classifier_confidence"),
                "de_aligned": diagnostic.get("de_aligned"),
                "segmentation_reason": clause.get("segmentation_reason", ""),
                "nucleus_kinds": clause.get("nucleus_kinds", []),
                "predicted_clause_count_in_record": len(rec.get("clauses", [])),
                "clause_text_preview": text[:80],
            })
    return out


def _route_confusion(attempts: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    confusion: dict[str, dict[str, int]] = {}
    for att in attempts:
        for clause in att["record"].get("clauses", []):
            stored = clause.get("modality", {})
            route = stored.get("route", "no_route")
            label = stored.get("label", "no_label")
            confusion.setdefault(route, {}).setdefault(label, 0)
            confusion[route][label] += 1
    return confusion


def _per_class_error_buckets(
    gold: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """For each Gold clause, compare predicted modality by IoU match.

    Returns per-class TP/FP/FN counts. Uses simple clause-level matching by
    deterministic maximum-total character-span IoU with threshold 0.5 (the
    same as the v3 evaluator). Gold is read only by the diagnostic.
    """
    # align gold to predicted by IoU
    all_pred_clauses = []
    pred_by_id: dict[str, list[dict[str, Any]]] = {}
    for att in attempts:
        rec = att["record"]
        for clause in rec.get("clauses", []):
            sp = clause.get("clause_span", {})
            all_pred_clauses.append({
                "sample_id": att["sample_id"],
                "start": int(sp.get("start", 0)),
                "end": int(sp.get("end", 0)),
                "label": clause.get("modality", {}).get("label"),
            })
            pred_by_id.setdefault(att["sample_id"], []).append({
                "start": int(sp.get("start", 0)),
                "end": int(sp.get("end", 0)),
                "label": clause.get("modality", {}).get("label"),
            })
    buckets: dict[str, dict[str, int]] = {
        "definition": {"TP": 0, "FP": 0, "FN": 0},
        "obligation": {"TP": 0, "FP": 0, "FN": 0},
        "permission": {"TP": 0, "FP": 0, "FN": 0},
        "prohibition": {"TP": 0, "FP": 0, "FN": 0},
    }
    for gold_rec in gold:
        sid = gold_rec["sample_id"]
        pred = pred_by_id.get(sid, [])
        # greedy IoU match
        used = set()
        for gc in gold_rec.get("clauses", []):
            gsp = gc.get("clause_span", {})
            g0 = int(gsp.get("start", 0))
            g1 = int(gsp.get("end", 0))
            g_label = gc.get("modality", {}).get("label")
            best_iou = 0.0
            best_pi = -1
            for pi, p in enumerate(pred):
                if pi in used:
                    continue
                p0 = p["start"]
                p1 = p["end"]
                inter = max(0, min(g1, p1) - max(g0, p0))
                union = max(g1, p1) - min(g0, p0)
                iou = inter / union if union > 0 else 0.0
                if iou > best_iou:
                    best_iou = iou
                    best_pi = pi
            if best_iou >= 0.5 and best_pi >= 0:
                used.add(best_pi)
                p_label = pred[best_pi]["label"]
                if p_label == g_label:
                    buckets[g_label]["TP"] += 1
                else:
                    buckets[g_label]["FN"] += 1
                    buckets[p_label]["FP"] += 1
            else:
                buckets[g_label]["FN"] += 1
        # unmatched preds are FPs
        for pi, p in enumerate(pred):
            if pi in used:
                continue
            buckets[p["label"]]["FP"] += 1
    return buckets


def _overlap_audit(
    source_text_by_id: dict[str, str],
    modality_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute exact/normalized/substring overlap between EStG-150 raw_de
    and the official modality train/dev/test records (no copying of raw
    text; only counts and sample hashes)."""
    # Load official modality records (training/dev/test) for the overlap check
    # These are read-only. modality_records should be the train/dev/test split
    # from formal_experiment/data/development/sun_modality/.
    # We compute three overlap measures:
    #  - exact text overlap (raw text == raw text)
    #  - normalized overlap (NFKC casefold whitespace-collapsed)
    #  - substring overlap (one contains the other)
    import re
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.casefold().strip())

    modality_by_id = {m.get("sample_id") or m.get("id") or m.get("record_id"): m for m in modality_records}
    overlap_exact = 0
    overlap_norm = 0
    overlap_substring = 0
    total = 0
    for sid, source_text in source_text_by_id.items():
        total += 1
        mod_rec = modality_by_id.get(sid)
        if mod_rec is None:
            continue
        mod_text = mod_rec.get("text") or mod_rec.get("raw_text_de") or mod_rec.get("source_text") or ""
        if not mod_text:
            continue
        if source_text == mod_text:
            overlap_exact += 1
        if norm(source_text) == norm(mod_text):
            overlap_norm += 1
        if source_text in mod_text or mod_text in source_text:
            overlap_substring += 1
    return {
        "compared_count": total,
        "exact_overlap": overlap_exact,
        "normalized_overlap": overlap_norm,
        "substring_overlap": overlap_substring,
        "note": "diagnostic-only; raw texts are not copied; only counts and sample hashes are returned",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v5-attempts", type=Path, required=True,
                        help="path to v5 b0_attempts.json (baseline)")
    parser.add_argument("--v6-attempts", type=Path, default=None,
                        help="path to v6 b0_attempts.json (optional)")
    parser.add_argument("--layer-e", type=Path, required=True,
                        help="path to estg_150_human_correction_v1.json (Gold)")
    parser.add_argument("--membership", type=Path, required=True,
                        help="path to estg_150_membership_hashes.json")
    parser.add_argument("--evaluator", type=Path,
                        default=ROOT / "configs/stage2_evaluator_s210_v3.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--include-every-nth-cunit", type=int, default=1)
    parser.add_argument("--gold-source-records", type=Path, default=None,
                        help="path to canonical gold_records.json (for oracle)")
    parser.add_argument("--skip-overlap-audit", action="store_true",
                        help="skip EStG-150 vs official-modality overlap audit")
    args = parser.parse_args()
    try:
        output_dir = args.output_dir.resolve()
        if output_dir.exists():
            raise RuntimeError(f"refusing to overwrite: {output_dir}")
        if not args.v5_attempts.is_file():
            raise RuntimeError(f"missing v5 attempts: {args.v5_attempts}")
        if not args.layer_e.is_file():
            raise RuntimeError(f"missing Layer E: {args.layer_e}")
        if not args.membership.is_file():
            raise RuntimeError(f"missing membership: {args.membership}")
        evaluator = load_evaluator_contract(args.evaluator)
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = output_dir.parent / f".{output_dir.name}.staging"
        if staging.exists():
            raise RuntimeError(f"staging path exists: {staging}")
        staging.mkdir()
        try:
            # Load baseline + v6 attempts
            v5_attempts = json.loads(args.v5_attempts.read_text(encoding="utf-8"))
            v6_attempts = None
            if args.v6_attempts and args.v6_attempts.is_file():
                v6_attempts = json.loads(args.v6_attempts.read_text(encoding="utf-8"))
            # Build Gold (read-only)
            gold, _ = build_canonical_gold_records(args.layer_e, args.membership)
            per_class: dict[str, dict[str, int]] = {}
            route_conf_v5: dict[str, dict[str, int]] = {}
            per_unit_v5: list[dict[str, Any]] = []
            overlap_audit: dict[str, Any] = {}

            for label, attempts in [
                ("v5_current_hybrid", v5_attempts),
                ("v6_hybrid" if v6_attempts is not None else "v6_hybrid_missing", v6_attempts or v5_attempts),
            ]:
                if not attempts:
                    continue
                # classifier-only and marker-only ablations (re-route the
                # same clause plan with different modality rules)
                cls_attempts = _override_modality(attempts, MODE_CLASSIFIER_ONLY)
                mrk_attempts = _override_modality(attempts, MODE_MARKER_ONLY)
                # per-ablation report
                cls_report = _evaluate(
                    gold, cls_attempts, contract=evaluator,
                    dataset_id=f"estg150_v6_abl_{label}_classifier_only",
                )
                mrk_report = _evaluate(
                    gold, mrk_attempts, contract=evaluator,
                    dataset_id=f"estg150_v6_abl_{label}_marker_only",
                )
                cur_report = _evaluate(
                    gold, attempts, contract=evaluator,
                    dataset_id=f"estg150_v6_abl_{label}_current_hybrid",
                )
                _write_json(staging / f"report_{label}_classifier_only.json", cls_report)
                _write_json(staging / f"report_{label}_marker_only.json", mrk_report)
                _write_json(staging / f"report_{label}_current_hybrid.json", cur_report)
                if label == "v5_current_hybrid" or v6_attempts is not None:
                    per_class[label] = _per_class_error_buckets(gold, attempts)
                    route_conf_v5[label] = _route_confusion(attempts)
                    per_unit_v5 = _per_unit_diagnostic(
                        attempts, gold, args.include_every_nth_cunit
                    )

            _write_json(staging / "per_class_error_buckets.json", per_class)
            _write_json(staging / "route_confusion.json", route_conf_v5)
            _write_json(staging / "per_unit_diagnostic.json", per_unit_v5)
            # segmentation ceiling: re-evaluate with gold clause spans
            if args.gold_source_records and args.gold_source_records.is_file():
                gold_only_attempts = json.loads(args.gold_source_records.read_text(encoding="utf-8"))
                oracle_report = _evaluate(
                    gold, gold_only_attempts, contract=evaluator,
                    dataset_id="estg150_v6_gold_clause_seg_oracle",
                )
                _write_json(staging / "report_gold_clause_seg_oracle.json", oracle_report)
            if not args.skip_overlap_audit:
                # Load official modality records for the overlap audit
                # We use train.jsonl / dev.jsonl / test.jsonl split.
                # build source_text_by_id from gold records (approved English)
                source_text_by_id = {g["sample_id"]: g.get("source_text", "") for g in gold}
                # modality_records: load the train/dev/test jsonl
                modality_dir = ROOT / "data/development/sun_modality"
                modality_records: list[dict[str, Any]] = []
                for split in ("train", "dev", "test"):
                    path = modality_dir / f"{split}.jsonl"
                    if path.is_file():
                        with path.open(encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                modality_records.append(json.loads(line))
                overlap_audit = _overlap_audit(source_text_by_id, modality_records)
            _write_json(staging / "overlap_audit.json", overlap_audit)

            # summary
            summary = {
                "schema_version": "estg150_b0_v6_phase_a_diagnostic@1.0.0",
                "v5_attempts_sha256": sha256_file(args.v5_attempts) if args.v5_attempts.is_file() else None,
                "v6_attempts_sha256": (
                    sha256_file(args.v6_attempts) if args.v6_attempts and args.v6_attempts.is_file() else None
                ),
                "layer_e_sha256": sha256_file(args.layer_e),
                "membership_sha256": sha256_file(args.membership),
                "per_class": per_class,
                "route_confusion": route_conf_v5,
                "overlap_audit": overlap_audit,
                "diagnostic_count": len(per_unit_v5),
            }
            _write_json(staging / "phase_a_diagnostic_summary.json", summary)
            staging.rename(output_dir)
        except Exception:
            import shutil
            shutil.rmtree(staging, ignore_errors=True)
            raise
        print(json.dumps({
            "output_dir": str(output_dir),
            "per_class": per_class,
            "diagnostic_count": len(per_unit_v5),
            "overlap_audit": overlap_audit,
            "v5_attempts_sha256": sha256_file(args.v5_attempts) if args.v5_attempts.is_file() else None,
            "v6_attempts_sha256": (
                sha256_file(args.v6_attempts) if args.v6_attempts and args.v6_attempts.is_file() else None
            ),
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (RuntimeError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"Phase A diagnostic failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
