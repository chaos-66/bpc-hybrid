"""Phase A residual diagnostics v3 (alignment coverage, marker abstention, dual oracle).

Does not overwrite phase_a_correction_v1/v2. Uses real S2.4 inference already in
v5/v7 attempts when present, else re-infers. Gold/Layer E read-only.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    build_canonical_gold_records,
    load_object,
    sha256_file,
)
from bpc_hybrid.estg150_b0_development_v3 import (  # noqa: E402
    align_german_to_english_units_v4,
    split_german_units,
)
from bpc_hybrid.estg150_b0_development_v4 import (  # noqa: E402
    MODE_CLASSIFIER_ONLY,
    MODE_HYBRID,
    MODE_MARKER_ONLY,
    english_marker_modality_v6,
    resolve_modality_v6,
)
from bpc_hybrid.estg150_b0_development_v5 import (  # noqa: E402
    english_marker_modality_v4,
)
from bpc_hybrid.stage2_evaluation_v3 import (  # noqa: E402
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
    validate_evaluation_report,
    clause_iou_pairs,
)
from bpc_hybrid.sun_style.sun_b0 import (  # noqa: E402
    LockedBertTextCNNInference,
    ModalityPrediction,
    load_s26_config,
)
from bpc_hybrid.sun_style.bert_textcnn import LABELS  # noqa: E402
import torch  # noqa: E402


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(_json_sanitize(value), stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _json_sanitize(value: Any) -> Any:
    if isinstance(value, ModalityPrediction):
        return {"label": value.label, "confidence": value.confidence}
    if isinstance(value, dict):
        return {k: _json_sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_sanitize(v) for v in value]
    if isinstance(value, tuple):
        return [_json_sanitize(v) for v in value]
    return value




def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", " ", s.casefold().strip())


def predict_details(classifier: LockedBertTextCNNInference, texts: Sequence[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for start in range(0, len(texts), 16):
        batch = list(texts[start : start + 16])
        encoded = classifier.tokenizer(
            batch, padding=True, truncation=True, max_length=classifier.max_length, return_tensors="pt"
        )
        with torch.no_grad():
            logits = classifier.model(
                input_ids=encoded["input_ids"].to(classifier.device),
                attention_mask=encoded["attention_mask"].to(classifier.device),
            )
            probs = torch.softmax(logits, dim=1).cpu()
        for i in range(probs.shape[0]):
            row = probs[i]
            order = torch.argsort(row, descending=True)
            top1 = int(order[0].item())
            top2 = int(order[1].item())
            p1 = float(row[top1].item())
            p2 = float(row[top2].item())
            out.append(
                {
                    "label": LABELS[top1],
                    "confidence": p1,
                    "top2_label": LABELS[top2],
                    "margin": p1 - p2,
                    "prediction": ModalityPrediction(LABELS[top1], p1),
                }
            )
    return out


def _layer_e_raw_de(path: Path) -> dict[str, str]:
    doc = load_object(path)
    out = {}
    for rec in doc["records"]:
        out[rec["sample_id"]] = rec["raw_text_de"]
    return out


def attach_alignment_and_classifier(
    attempts: list[dict[str, Any]],
    raw_de: Mapping[str, str],
    classifier: LockedBertTextCNNInference,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prepared = []
    de_texts = []
    for ai, att in enumerate(attempts):
        sid = att["sample_id"]
        rec = att["record"]
        de_full = raw_de[sid]
        clauses = rec["clauses"]
        en_texts = [
            rec["source_text"][int(c["clause_span"]["start"]) : int(c["clause_span"]["end"])]
            for c in clauses
        ]
        de_units = align_german_to_english_units_v4(de_full, en_texts)
        de_n = len(split_german_units(de_full)) or 1
        en_n = len(en_texts)
        de_aligned = de_n == en_n
        # detect 1->N full-copy
        full_copy = (len(de_units) == en_n and len(set(de_units)) == 1 and en_n > 1 and de_n == 1)
        for ci, de_text in enumerate(de_units):
            prepared.append((ai, ci, de_text, de_aligned, de_n, en_n, full_copy))
            de_texts.append(de_text if de_text.strip() else de_full)
    details = predict_details(classifier, de_texts)
    out = copy.deepcopy(attempts)
    sha_counts: Counter[str] = Counter()
    for (ai, ci, de_text, de_aligned, de_n, en_n, full_copy), det in zip(prepared, details, strict=True):
        cl = out[ai]["record"]["clauses"][ci]
        en_text = out[ai]["record"]["source_text"][
            int(cl["clause_span"]["start"]) : int(cl["clause_span"]["end"])
        ]
        de_sha = _sha256_text(de_text)
        sha_counts[de_sha] += 1
        unsupported = (not de_aligned) or full_copy or (not de_text.strip())
        cl["alignment_diag"] = {
            "de_aligned": de_aligned,
            "de_unit_count": de_n,
            "en_unit_count": en_n,
            "de_input_sha256": de_sha,
            "de_input_char_len": len(de_text),
            "full_record_copied_to_multiple_en": full_copy,
            "alignment_unsupported": unsupported,
            "english_marker_label": english_marker_modality_v6(en_text)[0],
            "classifier_label": det["label"],
            "classifier_confidence": det["confidence"],
            "classifier_margin": det["margin"],
            "stored_hybrid_label": cl.get("modality", {}).get("label"),
        }
        cl["_clf_label"] = det["label"]
        cl["_clf_confidence"] = det["confidence"]
    dup_multi = sum(1 for s, c in sha_counts.items() if c > 1)
    stats = {
        "clause_count": len(details),
        "aligned_true_count": sum(
            1
            for att in out
            for cl in att["record"]["clauses"]
            if cl["alignment_diag"]["de_aligned"] and not cl["alignment_diag"]["full_record_copied_to_multiple_en"]
        ),
        "alignment_unsupported_count": sum(
            1
            for att in out
            for cl in att["record"]["clauses"]
            if cl["alignment_diag"]["alignment_unsupported"]
        ),
        "full_copy_1_to_n_clause_count": sum(
            1
            for att in out
            for cl in att["record"]["clauses"]
            if cl["alignment_diag"]["full_record_copied_to_multiple_en"]
        ),
        "unique_de_input_hashes": len(sha_counts),
        "de_hashes_used_more_than_once": dup_multi,
    }
    stats["alignment_coverage"] = stats["aligned_true_count"] / max(stats["clause_count"], 1)
    return out, stats


def _evaluate(gold, attempts, contract, dataset_id):
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
        raise RuntimeError("; ".join(errors))
    return report


def _mod_summary(report):
    m = report["primary_metrics"]["modality"]
    cs = report["structural_encoding"]["clause_segmentation"]
    return {
        "modality_micro": m["micro"],
        "modality_macro_f1": m["macro_f1"],
        "modality_per_class": m["per_class"],
        "clause_alignment": {
            "p": cs["alignment_precision"],
            "r": cs["alignment_recall"],
            "f1": cs["alignment_f1"],
            "exact_f1": cs["exact_f1"],
            "pred": cs["predicted_count"],
            "gold": cs["gold_count"],
            "aligned": cs["aligned_match_count"],
        },
    }


def _aligned_acc(gold, attempts):
    pred_by = {a["sample_id"]: a["record"] for a in attempts}
    aligned = correct = 0
    for g in gold:
        p = pred_by[g["sample_id"]]
        pairs, _, _, _ = clause_iou_pairs(g["clauses"], p["clauses"], minimum_iou=0.5)
        for gi, pi in pairs:
            aligned += 1
            if g["clauses"][gi]["modality"]["label"] == p["clauses"][pi]["modality"]["label"]:
                correct += 1
    return {"aligned": aligned, "correct": correct, "accuracy": correct / aligned if aligned else 0.0}


def classifier_only_aligned_subset(attempts_enriched):
    """Keep only alignment-supported clauses for classifier-only scoring via filter metrics."""
    # Build attempts where unsupported clauses get a sentinel that won't match any gold label...
    # Better: compute manual P/R only on supported clauses against gold matches.
    return attempts_enriched


def score_classifier_aligned_only(gold, attempts_enriched):
    pred_by = {a["sample_id"]: a["record"] for a in attempts_enriched}
    tp = fp = fn = 0
    supported = unsupported = 0
    conf = Counter()
    for g in gold:
        p = pred_by[g["sample_id"]]
        pairs, miss, extra, _ = clause_iou_pairs(g["clauses"], p["clauses"], minimum_iou=0.5)
        # matched pairs
        for gi, pi in pairs:
            ad = p["clauses"][pi]["alignment_diag"]
            gl = g["clauses"][gi]["modality"]["label"]
            if ad["alignment_unsupported"]:
                unsupported += 1
                fn += 1  # gold clause not covered by supported classifier prediction
                continue
            supported += 1
            pl = ad["classifier_label"]
            if gl == pl:
                tp += 1
            else:
                fp += 1
                fn += 1
                conf[f"{gl}->{pl}"] += 1
        # unmatched gold always fn for this diagnostic of coverage-aware scoring
        for gi in miss:
            fn += 1
        # extra pred supported that don't match: already handled via fp on wrong matches;
        # unsupported extras ignored for classifier-only supported scoring
        for pi in extra:
            if not p["clauses"][pi]["alignment_diag"]["alignment_unsupported"]:
                fp += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "supported_matched_pairs": supported,
        "unsupported_matched_pairs": unsupported,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_top": dict(conf.most_common(12)),
    }


def score_marker_supported_and_abstention(gold, attempts_enriched):
    pred_by = {a["sample_id"]: a["record"] for a in attempts_enriched}
    # supported-only
    tp = fp = fn = 0
    supported = abstained = 0
    conf = Counter()
    for g in gold:
        p = pred_by[g["sample_id"]]
        pairs, miss, extra, _ = clause_iou_pairs(g["clauses"], p["clauses"], minimum_iou=0.5)
        for gi, pi in pairs:
            text = p["source_text"][
                int(p["clauses"][pi]["clause_span"]["start"]) : int(p["clauses"][pi]["clause_span"]["end"])
            ]
            lab, surf = english_marker_modality_v6(text)
            gl = g["clauses"][gi]["modality"]["label"]
            if lab is None:
                abstained += 1
                # abstention: not a class prediction; gold clause not recalled by marker
                fn += 1
            else:
                supported += 1
                if lab == gl:
                    tp += 1
                else:
                    fp += 1
                    fn += 1
                    conf[f"{gl}->{lab}"] += 1
        for gi in miss:
            fn += 1
        for pi in extra:
            text = p["source_text"][
                int(p["clauses"][pi]["clause_span"]["start"]) : int(p["clauses"][pi]["clause_span"]["end"])
            ]
            lab, _ = english_marker_modality_v6(text)
            if lab is not None:
                fp += 1
            else:
                abstained += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    total_pred_clauses = sum(len(a["record"]["clauses"]) for a in attempts_enriched)
    return {
        "supported_predictions_or_matches": supported,
        "abstained_count": abstained,
        "coverage_on_matched_pairs_approx": supported / max(supported + abstained, 1),
        "supported_tp_fp_fn": {"tp": tp, "fp": fp, "fn": fn},
        "supported_precision": precision,
        "supported_recall": recall,
        "supported_f1": f1,
        "confusion_top": dict(conf.most_common(12)),
        "note": "Unsupported/no-marker is abstention; not forced into obligation class matrix.",
        "total_pred_clauses": total_pred_clauses,
    }


def gold_seg_oracle_v5_routing_fixed(gold, raw_de, classifier):
    """Gold spans + v5-style resolve_modality_v4/v5 hybrid logic using real classifier."""
    from bpc_hybrid.estg150_b0_development_v3 import resolve_modality_v4

    attempts = []
    de_texts = []
    plan = []
    for gi, g in enumerate(gold):
        sid = g["sample_id"]
        src = g["source_text"]
        de_full = raw_de[sid]
        en_texts = [src[int(c["clause_span"]["start"]) : int(c["clause_span"]["end"])] for c in g["clauses"]]
        de_units = align_german_to_english_units_v4(de_full, en_texts)
        de_n = len(split_german_units(de_full)) or 1
        en_n = len(en_texts)
        de_aligned = de_n == en_n
        clauses = []
        for ci, (gcl, de_text, en_text) in enumerate(zip(g["clauses"], de_units, en_texts, strict=True)):
            clauses.append(
                {
                    "clause_id": gcl["clause_id"],
                    "clause_span": dict(gcl["clause_span"]),
                    "modality": {"label": "obligation", "evidence": [dict(gcl["clause_span"])]},
                    "actors": [],
                    "actions": [],
                    "conditions": [],
                    "constraints": [],
                    "exceptions": [],
                    "actor_action_map": [],
                    "order_relations": [],
                }
            )
            de_texts.append(de_text if de_text.strip() else de_full)
            plan.append((gi, ci, de_aligned, en_text))
        attempts.append(
            {
                "sample_id": sid,
                "request_status": "ok",
                "record": {
                    "schema_version": g["schema_version"],
                    "sample_id": sid,
                    "source_id": g["source_id"],
                    "source_text": src,
                    "clauses": clauses,
                    "method": {"name": "sun_rule_only", "schema_source": g["method"]["schema_source"]},
                    "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
                },
                "error_category": None,
                "runtime": {
                    "llm_call_performed": False,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost_usd": 0.0,
                    "latency_ms": 0.0,
                },
            }
        )
    details = predict_details(classifier, de_texts)
    for (gi, ci, de_aligned, en_text), det in zip(plan, details, strict=True):
        final, route = resolve_modality_v4(
            english_clause=en_text, classifier=det["prediction"], de_aligned=de_aligned
        )
        attempts[gi]["record"]["clauses"][ci]["modality"]["label"] = final.label
        attempts[gi]["record"]["clauses"][ci]["modality"]["route"] = route
    return attempts


def gold_seg_oracle_v8_hypothetical(gold, raw_de, classifier):
    """Gold spans + v6/v7 hybrid resolve_modality_v6 (hypothetical upper bound)."""
    attempts = []
    de_texts = []
    plan = []
    for gi, g in enumerate(gold):
        sid = g["sample_id"]
        src = g["source_text"]
        de_full = raw_de[sid]
        en_texts = [src[int(c["clause_span"]["start"]) : int(c["clause_span"]["end"])] for c in g["clauses"]]
        de_units = align_german_to_english_units_v4(de_full, en_texts)
        de_n = len(split_german_units(de_full)) or 1
        en_n = len(en_texts)
        de_aligned = de_n == en_n
        clauses = []
        for ci, (gcl, de_text, en_text) in enumerate(zip(g["clauses"], de_units, en_texts, strict=True)):
            clauses.append(
                {
                    "clause_id": gcl["clause_id"],
                    "clause_span": dict(gcl["clause_span"]),
                    "modality": {"label": "obligation", "evidence": [dict(gcl["clause_span"])]},
                    "actors": [],
                    "actions": [],
                    "conditions": [],
                    "constraints": [],
                    "exceptions": [],
                    "actor_action_map": [],
                    "order_relations": [],
                }
            )
            de_texts.append(de_text if de_text.strip() else de_full)
            plan.append((gi, ci, de_aligned, en_text))
        attempts.append(
            {
                "sample_id": sid,
                "request_status": "ok",
                "record": {
                    "schema_version": g["schema_version"],
                    "sample_id": sid,
                    "source_id": g["source_id"],
                    "source_text": src,
                    "clauses": clauses,
                    "method": {"name": "sun_rule_only", "schema_source": g["method"]["schema_source"]},
                    "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
                },
                "error_category": None,
                "runtime": {
                    "llm_call_performed": False,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost_usd": 0.0,
                    "latency_ms": 0.0,
                },
            }
        )
    details = predict_details(classifier, de_texts)
    for (gi, ci, de_aligned, en_text), det in zip(plan, details, strict=True):
        final, route, diag = resolve_modality_v6(
            english_clause=en_text,
            classifier=det["prediction"],
            de_aligned=de_aligned,
            mode=MODE_HYBRID,
        )
        attempts[gi]["record"]["clauses"][ci]["modality"]["label"] = final.label
        attempts[gi]["record"]["clauses"][ci]["modality"]["route"] = route
    return attempts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--attempts",
        type=Path,
        default=ROOT / "outputs/development/s27_estg150_b0_enhanced_v5/b0_attempts.json",
    )
    parser.add_argument(
        "--layer-e",
        type=Path,
        default=ROOT / "data/development/human_review/estg_150_human_correction_v1.json",
    )
    parser.add_argument(
        "--membership",
        type=Path,
        default=ROOT / "data/development/estg/estg_150_membership_hashes.json",
    )
    parser.add_argument(
        "--evaluator",
        type=Path,
        default=ROOT / "configs/stage2_evaluator_s210_v3.json",
    )
    parser.add_argument(
        "--s26-config",
        type=Path,
        default=ROOT / "configs/models/sun_b0_s26.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs/development/s27_estg150_b0_phase_a_residual_v3",
    )
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    try:
        out = args.output_dir.resolve()
        if out.exists():
            raise RuntimeError(f"refusing overwrite: {out}")
        gold, _ = build_canonical_gold_records(args.layer_e, args.membership)
        raw_de = _layer_e_raw_de(args.layer_e)
        contract = load_evaluator_contract(args.evaluator)
        s26 = load_s26_config(args.s26_config)
        classifier = LockedBertTextCNNInference.load(ROOT, s26, device=args.device)
        attempts = json.loads(args.attempts.read_text(encoding="utf-8"))
        enriched, align_stats = attach_alignment_and_classifier(attempts, raw_de, classifier)
        clf_aligned = score_classifier_aligned_only(gold, enriched)
        marker_scores = score_marker_supported_and_abstention(gold, enriched)

        # hybrid full re-eval using stored labels (should match baseline if v5 attempts)
        hybrid_attempts = copy.deepcopy(attempts)
        hybrid_report = _evaluate(gold, hybrid_attempts, contract, "phase_a_res_v5_hybrid_stored")

        # classifier_only all clauses (including misaligned duplicates) - for contrast only
        clf_all = copy.deepcopy(enriched)
        for att in clf_all:
            for cl in att["record"]["clauses"]:
                cl["modality"]["label"] = cl["alignment_diag"]["classifier_label"]
        clf_all_report = _evaluate(gold, clf_all, contract, "phase_a_res_classifier_all")

        # dual gold oracles
        ora_v5 = gold_seg_oracle_v5_routing_fixed(gold, raw_de, classifier)
        ora_v5_report = _evaluate(gold, ora_v5, contract, "phase_a_res_gold_v5_routing_fixed")
        ora_v8 = gold_seg_oracle_v8_hypothetical(gold, raw_de, classifier)
        ora_v8_report = _evaluate(gold, ora_v8, contract, "phase_a_res_gold_v8_hypothetical")

        staging = out.parent / f".{out.name}.staging"
        if staging.exists():
            raise RuntimeError("staging exists")
        staging.mkdir(parents=True)
        try:
            _write_json(staging / "alignment_stats.json", align_stats)
            _write_json(staging / "classifier_aligned_only_metrics.json", clf_aligned)
            _write_json(staging / "marker_supported_and_abstention.json", marker_scores)
            _write_json(staging / "report_hybrid_stored.json", hybrid_report)
            _write_json(staging / "report_classifier_all_including_misaligned.json", clf_all_report)
            _write_json(staging / "report_gold_seg_v5_routing_fixed.json", ora_v5_report)
            _write_json(staging / "report_gold_seg_v8_hypothetical.json", ora_v8_report)
            # strip non-JSON private fields
            for att in enriched:
                for cl in att["record"]["clauses"]:
                    cl.pop("_clf_label", None)
                    cl.pop("_clf_confidence", None)
            _write_json(staging / "attempts_enriched_alignment.json", enriched)
            manifest = {
                "schema_version": "estg150_phase_a_residual_v3@1.0.0",
                "run_id": "s27_estg150_b0_phase_a_residual_v3",
                "claim_scope": "development_diagnostic_only",
                "inputs": {
                    "attempts_sha256": sha256_file(args.attempts),
                    "layer_e_sha256": sha256_file(args.layer_e),
                    "membership_sha256": sha256_file(args.membership),
                    "evaluator_sha256": sha256_file(args.evaluator),
                },
                "alignment_stats": align_stats,
                "classifier_aligned_only": clf_aligned,
                "marker_supported_and_abstention": marker_scores,
                "hybrid_stored": _mod_summary(hybrid_report),
                "classifier_all_including_misaligned": _mod_summary(clf_all_report),
                "gold_seg_v5_routing_fixed": {
                    **_mod_summary(ora_v5_report),
                    "aligned_label": _aligned_acc(gold, ora_v5),
                    "definition": "Gold spans + resolve_modality_v4 (v5 hybrid routing)",
                },
                "gold_seg_v8_hypothetical": {
                    **_mod_summary(ora_v8_report),
                    "aligned_label": _aligned_acc(gold, ora_v8),
                    "definition": "Gold spans + resolve_modality_v6 hybrid (hypothetical, not single-variable ceiling)",
                },
                "oracle_difference_note": (
                    "Do not subtract these two oracles to isolate pure segmentation; "
                    "v5-routing-fixed is the single-variable segmentation effect under v5 routing."
                ),
                "safety": {
                    "gold_read_only": True,
                    "llm_api_called": False,
                    "network_called": False,
                },
            }
            _write_json(staging / "manifest.json", manifest)
            staging.rename(out)
        except Exception:
            import shutil

            shutil.rmtree(staging, ignore_errors=True)
            raise
        print(
            json.dumps(
                {
                    "output_dir": str(out),
                    "manifest_sha256": sha256_file(out / "manifest.json"),
                    "alignment_coverage": align_stats["alignment_coverage"],
                    "aligned_true": align_stats["aligned_true_count"],
                    "unsupported": align_stats["alignment_unsupported_count"],
                    "full_copy_1_to_n": align_stats["full_copy_1_to_n_clause_count"],
                    "clf_aligned_only_f1": clf_aligned["f1"],
                    "marker_supported_f1": marker_scores["supported_f1"],
                    "gold_v5_routing_f1": manifest["gold_seg_v5_routing_fixed"]["modality_micro"]["f1"],
                    "gold_v8_hyp_f1": manifest["gold_seg_v8_hypothetical"]["modality_micro"]["f1"],
                    "hybrid_stored_f1": manifest["hybrid_stored"]["modality_micro"]["f1"],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        print(f"residual Phase A failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
