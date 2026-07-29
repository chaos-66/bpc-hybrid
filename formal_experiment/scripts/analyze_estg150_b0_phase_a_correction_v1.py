"""Corrected Phase A diagnostic for invalid Minimax v6 ablations.

Fixes real S2.4 classifier inference, Gold clause segmentation oracle,
and DE vs S2.4 text-hash overlap audit. Does not overwrite v1-v6 artifacts.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.estg150_b0_development import (
    Estg150B0DevelopmentError,
    build_canonical_gold_records,
    load_object,
    sha256_file,
)
from bpc_hybrid.estg150_b0_development_v3 import (
    align_german_to_english_units_v4,
    split_german_units,
)
from bpc_hybrid.estg150_b0_development_v4 import (
    MODE_CLASSIFIER_ONLY,
    MODE_HYBRID,
    MODE_MARKER_ONLY,
    english_marker_modality_v6,
    resolve_modality_v6,
)
from bpc_hybrid.stage2_evaluation_v3 import (
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
    validate_evaluation_report,
)
from bpc_hybrid.sun_style.bert_textcnn import LABELS
from bpc_hybrid.sun_style.sun_b0 import (
    LockedBertTextCNNInference,
    ModalityPrediction,
    load_s26_config,
)



def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", " ", s.casefold().strip())


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def predict_with_details(
    classifier: LockedBertTextCNNInference,
    texts: Sequence[str],
    *,
    batch_size: int = 16,
) -> list[dict[str, Any]]:
    if not texts:
        return []
    out: list[dict[str, Any]] = []
    for start in range(0, len(texts), batch_size):
        batch = list(texts[start : start + batch_size])
        if any(not isinstance(t, str) or not t.strip() for t in batch):
            raise Estg150B0DevelopmentError("empty DE classifier input")
        encoded = classifier.tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=classifier.max_length,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = classifier.model(
                input_ids=encoded["input_ids"].to(classifier.device),
                attention_mask=encoded["attention_mask"].to(classifier.device),
            )
            probs = torch.softmax(logits, dim=1).cpu()
            logits_cpu = logits.cpu()
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
                    "top2_confidence": p2,
                    "margin_top1_top2": p1 - p2,
                    "probabilities": {
                        LABELS[j]: float(row[j].item()) for j in range(len(LABELS))
                    },
                    "logits": {
                        LABELS[j]: float(logits_cpu[i, j].item()) for j in range(len(LABELS))
                    },
                    "prediction": ModalityPrediction(LABELS[top1], p1),
                }
            )
    return out


def _layer_e_raw_de_by_id(layer_e_path: Path) -> dict[str, str]:
    doc = load_object(layer_e_path)
    out: dict[str, str] = {}
    for rec in doc.get("records") or []:
        sid = rec.get("sample_id")
        de = rec.get("raw_text_de")
        if isinstance(sid, str) and isinstance(de, str) and de.strip():
            out[sid] = de
    if len(out) != 150:
        raise RuntimeError(f"expected 150 raw_text_de, got {len(out)}")
    return out


def _attach_real_classifier_to_attempts(
    attempts: list[dict[str, Any]],
    raw_de_by_id: Mapping[str, str],
    classifier: LockedBertTextCNNInference,
    *,
    checkpoint_meta: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prepared: list[tuple[int, int, str, bool, int, int]] = []
    de_texts: list[str] = []
    unsupported = 0
    for ai, att in enumerate(attempts):
        sid = att["sample_id"]
        rec = att["record"]
        de_full = raw_de_by_id.get(sid)
        if not de_full:
            raise RuntimeError(f"missing raw_text_de for {sid}")
        clauses = rec.get("clauses") or []
        en_texts = [
            rec["source_text"][int(cl["clause_span"]["start"]) : int(cl["clause_span"]["end"])]
            for cl in clauses
        ]
        de_units = align_german_to_english_units_v4(de_full, en_texts)
        de_n = len(split_german_units(de_full)) or 1
        en_n = len(en_texts)
        de_aligned = de_n == en_n
        if len(de_units) != len(clauses):
            raise RuntimeError(f"DE/EN unit mismatch for {sid}")
        for ci, (cl, de_text) in enumerate(zip(clauses, de_units, strict=True)):
            if not de_text.strip():
                unsupported += 1
                prepared.append((ai, ci, de_full, False, de_n, en_n))
                de_texts.append(de_full)
            else:
                prepared.append((ai, ci, de_text, de_aligned, de_n, en_n))
                de_texts.append(de_text)
    t0 = time.perf_counter()
    details = predict_with_details(classifier, de_texts)
    infer_s = time.perf_counter() - t0
    if len(details) != len(prepared):
        raise RuntimeError("classifier detail count mismatch")
    out = copy.deepcopy(attempts)
    for (ai, ci, de_text, de_aligned, de_n, en_n), det in zip(prepared, details, strict=True):
        cl = out[ai]["record"]["clauses"][ci]
        en_text = out[ai]["record"]["source_text"][
            int(cl["clause_span"]["start"]) : int(cl["clause_span"]["end"])
        ]
        en_label, en_surface = english_marker_modality_v6(en_text)
        cl["classifier_inference"] = {
            "label": det["label"],
            "confidence": det["confidence"],
            "top2_label": det["top2_label"],
            "top2_confidence": det["top2_confidence"],
            "margin_top1_top2": det["margin_top1_top2"],
            "probabilities": det["probabilities"],
            "logits": det["logits"],
            "de_input_sha256": _sha256_text(de_text),
            "de_input_char_len": len(de_text),
            "de_unit_count": de_n,
            "en_unit_count": en_n,
            "de_aligned": de_aligned,
            "english_marker_label": en_label,
            "english_marker_surface": en_surface,
            "stored_hybrid_label": cl.get("modality", {}).get("label"),
            "stored_hybrid_route": cl.get("modality", {}).get("route"),
            **checkpoint_meta,
        }
    stats = {
        "clause_inference_count": len(details),
        "unsupported_empty_de_units": unsupported,
        "classifier_seconds": infer_s,
        "checkpoint": dict(checkpoint_meta),
    }
    return out, stats


def _reroute_attempts(
    attempts_with_clf: list[dict[str, Any]],
    mode: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    out = copy.deepcopy(attempts_with_clf)
    route_counts: dict[str, int] = {}
    unsupported_marker = 0
    for att in out:
        for cl in att["record"]["clauses"]:
            info = cl["classifier_inference"]
            pred = ModalityPrediction(info["label"], float(info["confidence"]))
            en_text = att["record"]["source_text"][
                int(cl["clause_span"]["start"]) : int(cl["clause_span"]["end"])
            ]
            # Hybrid on predicted segmentation: keep original stored labels so
            # current_hybrid matches the frozen run, not a re-implementation.
            if mode == MODE_HYBRID and info.get("stored_hybrid_label"):
                final = ModalityPrediction(
                    info["stored_hybrid_label"], float(info["confidence"])
                )
                route = info.get("stored_hybrid_route") or "stored_hybrid"
                diag = {
                    "classifier_label": info["label"],
                    "classifier_confidence": info["confidence"],
                    "english_marker_label": info.get("english_marker_label"),
                    "english_marker_surface": info.get("english_marker_surface"),
                    "de_aligned": info["de_aligned"],
                    "mode": mode,
                    "used_stored_hybrid_label": True,
                }
            else:
                final, route, diag = resolve_modality_v6(
                    english_clause=en_text,
                    classifier=pred,
                    de_aligned=bool(info["de_aligned"]),
                    mode=mode,
                )
            if mode == MODE_MARKER_ONLY and diag.get("english_marker_label") is None:
                unsupported_marker += 1
                cl["modality"]["label"] = final.label
                cl["modality"]["route"] = "marker_only_unsupported"
                cl["modality"]["unsupported"] = True
            else:
                cl["modality"]["label"] = final.label
                cl["modality"]["route"] = route
                cl["modality"]["unsupported"] = False
            cl["modality"]["diagnostic"] = {
                **diag,
                "real_classifier_label": info["label"],
                "real_classifier_confidence": info["confidence"],
                "real_classifier_margin": info["margin_top1_top2"],
                "differs_from_stored_hybrid": info["label"] != info.get("stored_hybrid_label"),
            }
            route_counts[cl["modality"]["route"]] = route_counts.get(cl["modality"]["route"], 0) + 1
    route_counts["marker_only_unsupported_count"] = unsupported_marker
    return out, route_counts


def _gold_clause_oracle_attempts(
    gold_records: list[dict[str, Any]],
    raw_de_by_id: Mapping[str, str],
    classifier: LockedBertTextCNNInference,
    *,
    mode: str,
    checkpoint_meta: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    de_texts: list[str] = []
    plan: list[tuple[int, int, bool, int, int, str]] = []
    for gi, gold in enumerate(gold_records):
        sid = gold["sample_id"]
        source_text = gold["source_text"]
        de_full = raw_de_by_id[sid]
        en_texts = [
            source_text[int(c["clause_span"]["start"]) : int(c["clause_span"]["end"])]
            for c in gold["clauses"]
        ]
        de_units = align_german_to_english_units_v4(de_full, en_texts)
        de_n = len(split_german_units(de_full)) or 1
        en_n = len(en_texts)
        de_aligned = de_n == en_n
        clauses_out = []
        for ci, (gcl, de_text, en_text) in enumerate(
            zip(gold["clauses"], de_units, en_texts, strict=True)
        ):
            clauses_out.append(
                {
                    "clause_id": gcl["clause_id"],
                    "clause_span": dict(gcl["clause_span"]),
                    "modality": {
                        "label": "obligation",
                        "evidence": [dict(gcl["clause_span"])],
                    },
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
            plan.append((gi, ci, de_aligned, de_n, en_n, en_text))
        attempts.append(
            {
                "sample_id": sid,
                "request_status": "ok",
                "record": {
                    "schema_version": gold["schema_version"],
                    "sample_id": sid,
                    "source_id": gold["source_id"],
                    "source_text": source_text,
                    "clauses": clauses_out,
                    "method": {
                        "name": "sun_rule_only",
                        "schema_source": gold["method"]["schema_source"],
                    },
                    "validation": {
                        "schema_valid": True,
                        "cross_field_valid": True,
                        "errors": [],
                    },
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
    details = predict_with_details(classifier, de_texts)
    for (gi, ci, de_aligned, de_n, en_n, en_text), det in zip(plan, details, strict=True):
        cl = attempts[gi]["record"]["clauses"][ci]
        pred = det["prediction"]
        final, route, diag = resolve_modality_v6(
            english_clause=en_text,
            classifier=pred,
            de_aligned=de_aligned,
            mode=mode,
        )
        cl["modality"]["label"] = final.label
        cl["modality"]["route"] = route
        cl["classifier_inference"] = {
            "label": det["label"],
            "confidence": det["confidence"],
            "top2_label": det["top2_label"],
            "top2_confidence": det["top2_confidence"],
            "margin_top1_top2": det["margin_top1_top2"],
            "probabilities": det["probabilities"],
            "logits": det["logits"],
            "de_aligned": de_aligned,
            "de_unit_count": de_n,
            "en_unit_count": en_n,
            "english_marker_label": diag.get("english_marker_label"),
            "english_marker_surface": diag.get("english_marker_surface"),
            **checkpoint_meta,
        }
        cl["modality"]["diagnostic"] = diag
    stats = {
        "gold_clause_count": sum(len(g["clauses"]) for g in gold_records),
        "oracle_mode": mode,
        "attempt_count": len(attempts),
    }
    return attempts, stats


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
        raise RuntimeError("evaluation report invalid: " + "; ".join(errors))
    return report


def _modality_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    m = report["primary_metrics"]["modality"]
    cs = report["structural_encoding"]["clause_segmentation"]
    return {
        "modality_micro": m["micro"],
        "modality_macro_f1": m["macro_f1"],
        "modality_per_class": m["per_class"],
        "clause_alignment": {
            "precision": cs["alignment_precision"],
            "recall": cs["alignment_recall"],
            "f1": cs["alignment_f1"],
            "exact_f1": cs["exact_f1"],
            "predicted_count": cs["predicted_count"],
            "gold_count": cs["gold_count"],
            "aligned_match_count": cs["aligned_match_count"],
        },
    }


def _aligned_label_accuracy(
    gold: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    from bpc_hybrid.stage2_evaluation_v3 import clause_iou_pairs

    pred_by = {a["sample_id"]: a["record"] for a in attempts}
    aligned = correct = 0
    conf: dict[str, int] = {}
    for g in gold:
        p = pred_by[g["sample_id"]]
        pairs, _, _, _ = clause_iou_pairs(g["clauses"], p["clauses"], minimum_iou=0.5)
        for gi, pi in pairs:
            aligned += 1
            gl = g["clauses"][gi]["modality"]["label"]
            pl = p["clauses"][pi]["modality"]["label"]
            if gl == pl:
                correct += 1
            else:
                key = f"{gl}->{pl}"
                conf[key] = conf.get(key, 0) + 1
    return {
        "aligned": aligned,
        "correct": correct,
        "accuracy": correct / aligned if aligned else 0.0,
        "confusion_top": dict(sorted(conf.items(), key=lambda kv: (-kv[1], kv[0]))[:12]),
    }


def _load_s24_splits(root: Path) -> dict[str, Any]:
    cfg = load_object(root / "configs/models/sun_bert_textcnn_s24.json")
    ds = cfg["dataset"]
    splits: dict[str, list[dict[str, Any]]] = {}
    hashes: dict[str, str] = {}
    counts: dict[str, int] = {}
    for name in ("train", "dev", "test"):
        rel = ds[name]["path"]
        path = root / rel
        if not path.is_file():
            raise RuntimeError(f"missing S2.4 {name} split: {path}")
        expected = ds[name]["sha256"]
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"S2.4 {name} split hash mismatch: {actual} != {expected}")
        rows = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        if len(rows) == 0:
            raise RuntimeError(f"S2.4 {name} split loaded 0 rows; refusing false overlap=0")
        if len(rows) != int(ds[name]["rows"]):
            raise RuntimeError(
                f"S2.4 {name} row count {len(rows)} != config {ds[name]['rows']}"
            )
        splits[name] = rows
        hashes[name] = actual
        counts[name] = len(rows)
    return {
        "splits": splits,
        "hashes": hashes,
        "counts": counts,
        "config_path": "configs/models/sun_bert_textcnn_s24.json",
        "config_sha256": sha256_file(root / "configs/models/sun_bert_textcnn_s24.json"),
    }


def _overlap_audit_de(
    raw_de_by_id: Mapping[str, str],
    split_pack: Mapping[str, Any],
) -> dict[str, Any]:
    estg_exact = {_sha256_text(t): sid for sid, t in raw_de_by_id.items()}
    estg_norm = {_sha256_text(_norm_text(t)): sid for sid, t in raw_de_by_id.items()}
    estg_norm_text = {_norm_text(t): sid for sid, t in raw_de_by_id.items()}
    per_split: dict[str, Any] = {}
    total_rows = exact_hits = norm_hits = containment_hits = near_dup_hits = 0
    for split_name, rows in split_pack["splits"].items():
        ex = nm = cont = near = 0
        hit_ids_exact: set[str] = set()
        hit_ids_norm: set[str] = set()
        for row in rows:
            total_rows += 1
            text = row.get("text") or ""
            if not isinstance(text, str) or not text.strip():
                continue
            eh = _sha256_text(text)
            nh = _sha256_text(_norm_text(text))
            nt = _norm_text(text)
            if eh in estg_exact:
                ex += 1
                hit_ids_exact.add(estg_exact[eh])
            if nh in estg_norm:
                nm += 1
                hit_ids_norm.add(estg_norm[nh])
            contained = False
            for et, sid in estg_norm_text.items():
                if nt == et:
                    continue
                if (nt in et or et in nt) and min(len(nt), len(et)) >= 40:
                    cont += 1
                    contained = True
                    break
            if not contained and nh not in estg_norm:
                a = re.sub(r"[^a-z0-9]", "", nt)
                for et, sid in estg_norm_text.items():
                    b = re.sub(r"[^a-z0-9]", "", et)
                    if not a or not b:
                        continue
                    if a == b:
                        near += 1
                        break
                    if len(a) >= 60 and len(b) >= 60 and (a[:60] == b[:60] or a[-60:] == b[-60:]):
                        near += 1
                        break
        exact_hits += ex
        norm_hits += nm
        containment_hits += cont
        near_dup_hits += near
        per_split[split_name] = {
            "loaded_rows": len(rows),
            "file_sha256": split_pack["hashes"][split_name],
            "exact_text_hash_hits": ex,
            "normalized_exact_hits": nm,
            "containment_hits_min40": cont,
            "near_duplicate_hits": near,
            "unique_estg_ids_exact": len(hit_ids_exact),
            "unique_estg_ids_normalized": len(hit_ids_norm),
        }
    if total_rows == 0:
        raise RuntimeError("overlap audit loaded 0 modality rows; fail-closed")
    return {
        "schema_version": "estg150_s24_overlap_audit@1.0.0",
        "method": "unicode_sha256_and_normalized_text_compare_no_sample_id_join",
        "estg150_raw_de_count": len(raw_de_by_id),
        "s24_total_loaded_rows": total_rows,
        "s24_split_counts": split_pack["counts"],
        "s24_split_hashes": split_pack["hashes"],
        "s24_config_sha256": split_pack["config_sha256"],
        "totals": {
            "exact_text_hash_hits": exact_hits,
            "normalized_exact_hits": norm_hits,
            "containment_hits_min40": containment_hits,
            "near_duplicate_hits": near_dup_hits,
        },
        "per_split": per_split,
        "note": "No full texts persisted; only counts and anonymous hashes.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--v5-attempts",
        type=Path,
        default=ROOT / "outputs/development/s27_estg150_b0_enhanced_v5/b0_attempts.json",
    )
    parser.add_argument(
        "--v6-attempts",
        type=Path,
        default=ROOT / "outputs/development/s27_estg150_b0_enhanced_v6/b0_attempts.json",
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
        default=ROOT / "outputs/development/s27_estg150_b0_phase_a_correction_v1",
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    try:
        out = args.output_dir.resolve()
        if out.exists():
            raise RuntimeError(f"refusing to overwrite: {out}")
        for path, name in (
            (args.v5_attempts, "v5 attempts"),
            (args.v6_attempts, "v6 attempts"),
            (args.layer_e, "Layer E"),
            (args.membership, "membership"),
            (args.evaluator, "evaluator"),
            (args.s26_config, "s26 config"),
        ):
            if not path.is_file():
                raise RuntimeError(f"missing {name}: {path}")

        v5_sha = sha256_file(args.v5_attempts)
        v6_sha = sha256_file(args.v6_attempts)
        layer_sha = sha256_file(args.layer_e)
        memb_sha = sha256_file(args.membership)
        if v5_sha != "42fe341d45e80b2cd0af8328654af5984d738fe2d9f8767acb2c24c2d4446308":
            raise RuntimeError(f"v5 attempts hash drift: {v5_sha}")
        if layer_sha != "7fd55f98a7dd6aeef58a93be825465c767f00feeab84c6d4215afc434a135b1c":
            raise RuntimeError(f"Layer E hash drift: {layer_sha}")

        contract = load_evaluator_contract(args.evaluator)
        gold, _source = build_canonical_gold_records(args.layer_e, args.membership)
        raw_de = _layer_e_raw_de_by_id(args.layer_e)
        s26 = load_s26_config(args.s26_config)
        clf_meta = {
            "checkpoint_path": s26["classifier"]["checkpoint"]["path"],
            "checkpoint_sha256": s26["classifier"]["checkpoint"]["sha256"],
            "checkpoint_bytes": s26["classifier"]["checkpoint"]["bytes"],
            "run_manifest_path": s26["classifier"]["run_manifest"]["path"],
            "run_manifest_sha256": s26["classifier"]["run_manifest"]["sha256"],
            "s24_config_path": s26["classifier"]["config"]["path"],
            "s24_config_sha256": s26["classifier"]["config"]["sha256"],
            "inference_language": "de",
        }
        ckpt = ROOT / clf_meta["checkpoint_path"]
        if sha256_file(ckpt) != clf_meta["checkpoint_sha256"]:
            raise RuntimeError("S2.4 checkpoint hash mismatch")
        if ckpt.stat().st_size != clf_meta["checkpoint_bytes"]:
            raise RuntimeError("S2.4 checkpoint size mismatch")

        classifier = LockedBertTextCNNInference.load(ROOT, s26, device=args.device)
        v5_attempts = json.loads(args.v5_attempts.read_text(encoding="utf-8"))
        v6_attempts = json.loads(args.v6_attempts.read_text(encoding="utf-8"))

        staging = out.parent / f".{out.name}.staging"
        if staging.exists():
            raise RuntimeError(f"staging exists: {staging}")
        staging.mkdir(parents=True)
        try:
            v5_enriched, v5_clf_stats = _attach_real_classifier_to_attempts(
                v5_attempts, raw_de, classifier, checkpoint_meta=clf_meta
            )
            v6_enriched, v6_clf_stats = _attach_real_classifier_to_attempts(
                v6_attempts, raw_de, classifier, checkpoint_meta=clf_meta
            )
            _write_json(staging / "v5_attempts_with_real_classifier.json", v5_enriched)
            _write_json(staging / "v6_attempts_with_real_classifier.json", v6_enriched)

            summaries: dict[str, Any] = {}
            route_tables: dict[str, Any] = {}
            for tag, enriched in (("v5", v5_enriched), ("v6", v6_enriched)):
                for mode in (MODE_CLASSIFIER_ONLY, MODE_MARKER_ONLY, MODE_HYBRID):
                    rerouted, routes = _reroute_attempts(enriched, mode)
                    report = _evaluate(
                        gold,
                        rerouted,
                        contract=contract,
                        dataset_id=f"estg150_phase_a_corr_{tag}_{mode}",
                    )
                    name = f"{tag}_{mode}"
                    _write_json(staging / f"report_{name}.json", report)
                    _write_json(staging / f"attempts_{name}.json", rerouted)
                    summaries[name] = _modality_summary(report)
                    summaries[name]["aligned_label"] = _aligned_label_accuracy(gold, rerouted)
                    route_tables[name] = routes
                    if mode == MODE_CLASSIFIER_ONLY:
                        hybrid_labels = [
                            cl["modality"]["label"]
                            for att in _reroute_attempts(enriched, MODE_HYBRID)[0]
                            for cl in att["record"]["clauses"]
                        ]
                        clf_labels = [
                            cl["modality"]["label"]
                            for att in rerouted
                            for cl in att["record"]["clauses"]
                        ]
                        summaries[name]["differs_from_hybrid_clause_count"] = sum(
                            a != b for a, b in zip(clf_labels, hybrid_labels, strict=True)
                        )

            oracle_summaries: dict[str, Any] = {}
            for mode, key in (
                (MODE_CLASSIFIER_ONLY, "gold_seg_real_classifier"),
                (MODE_MARKER_ONLY, "gold_seg_marker"),
                (MODE_HYBRID, "gold_seg_hybrid"),
            ):
                ora_attempts, ora_stats = _gold_clause_oracle_attempts(
                    gold, raw_de, classifier, mode=mode, checkpoint_meta=clf_meta
                )
                report = _evaluate(
                    gold,
                    ora_attempts,
                    contract=contract,
                    dataset_id=f"estg150_phase_a_corr_{key}",
                )
                _write_json(staging / f"report_{key}.json", report)
                _write_json(staging / f"attempts_{key}.json", ora_attempts)
                oracle_summaries[key] = {
                    **_modality_summary(report),
                    "aligned_label": _aligned_label_accuracy(gold, ora_attempts),
                    "oracle_stats": ora_stats,
                    "gold_input": {
                        "layer_e_sha256": layer_sha,
                        "membership_sha256": memb_sha,
                        "canonical_gold_membership_sha256": membership_sha256(gold),
                        "gold_clause_count": sum(len(g["clauses"]) for g in gold),
                        "gold_record_count": len(gold),
                    },
                }

            split_pack = _load_s24_splits(ROOT)
            overlap = _overlap_audit_de(raw_de, split_pack)
            _write_json(staging / "overlap_audit_de_s24.json", overlap)

            invalid_v6_notes = {
                "invalid_script": "scripts/analyze_estg150_b0_v6_components.py",
                "invalid_outputs_preserved": [
                    "outputs/development/s27_estg150_b0_v6_phase_a_diagnostic",
                    "outputs/development/s27_estg150_b0_v6_phase_a_diagnostic_v5",
                ],
                "bugs": [
                    {
                        "id": "A_fake_classifier_only",
                        "detail": (
                            "classifier_only used ModalityPrediction(stored hybrid label, 0.6), "
                            "so classifier_only metrics equaled hybrid by construction."
                        ),
                    },
                    {
                        "id": "B_gold_oracle_not_run",
                        "detail": (
                            "oracle path required --gold-source-records; default runs never "
                            "generated report_gold_clause_seg_oracle.json."
                        ),
                    },
                    {
                        "id": "C_overlap_wrong_language_and_path",
                        "detail": (
                            "overlap used gold source_text (approved English) and loaded "
                            "data/development/sun_modality/{train,dev,test}.jsonl which do not "
                            "exist (0 rows) while still reporting overlap=0 via sample_id join."
                        ),
                    },
                ],
                "v6_full_run_status": "same_metric_regression_negative_evidence",
                "v6_phase_a_status": "invalid_for_causal_attribution",
                "safe_tsurgeon_v2_status": "not_implemented_as_claimed",
                "current_best": "s27_estg150_b0_enhanced_v5",
            }
            _write_json(staging / "invalid_v6_phase_a_autopsy.json", invalid_v6_notes)

            manifest = {
                "schema_version": "estg150_b0_phase_a_correction@1.0.0",
                "run_id": "s27_estg150_b0_phase_a_correction_v1",
                "claim_scope": "development_diagnostic_only",
                "is_formal_performance_result": False,
                "paper_faithful_b0": False,
                "current_best_remains": "s27_estg150_b0_enhanced_v5",
                "inputs": {
                    "v5_attempts_sha256": v5_sha,
                    "v6_attempts_sha256": v6_sha,
                    "layer_e_sha256": layer_sha,
                    "membership_sha256": memb_sha,
                    "evaluator_sha256": sha256_file(args.evaluator),
                    "s26_config_sha256": sha256_file(args.s26_config),
                    **clf_meta,
                },
                "classifier_inference_stats": {"v5": v5_clf_stats, "v6": v6_clf_stats},
                "ablation_summaries": summaries,
                "route_tables": route_tables,
                "gold_segmentation_oracle": oracle_summaries,
                "overlap_audit": overlap,
                "invalid_v6_autopsy": invalid_v6_notes,
                "safety": {
                    "gold_read_only": True,
                    "layer_e_read_only": True,
                    "layer_e_modified": False,
                    "llm_api_called": False,
                    "network_called": False,
                    "evaluator_unchanged": True,
                    "v1_to_v6_artifacts_not_overwritten": True,
                },
            }
            if "v5_hybrid" in summaries and "gold_seg_hybrid" in oracle_summaries:
                manifest["oracle_minus_predicted_seg_hybrid"] = {
                    "modality_micro_f1_delta": (
                        oracle_summaries["gold_seg_hybrid"]["modality_micro"]["f1"]
                        - summaries["v5_hybrid"]["modality_micro"]["f1"]
                    ),
                    "aligned_accuracy_oracle": oracle_summaries["gold_seg_hybrid"][
                        "aligned_label"
                    ]["accuracy"],
                    "aligned_accuracy_predicted": summaries["v5_hybrid"]["aligned_label"][
                        "accuracy"
                    ],
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
                    "ablation_keys": sorted(summaries),
                    "oracle_keys": sorted(oracle_summaries),
                    "overlap_totals": overlap["totals"],
                    "s24_loaded": overlap["s24_split_counts"],
                    "v5_classifier_only_differs_from_hybrid": summaries.get(
                        "v5_classifier_only", {}
                    ).get("differs_from_hybrid_clause_count"),
                    "v5_classifier_only_f1": summaries.get("v5_classifier_only", {})
                    .get("modality_micro", {})
                    .get("f1"),
                    "v5_hybrid_f1": summaries.get("v5_hybrid", {})
                    .get("modality_micro", {})
                    .get("f1"),
                    "gold_seg_hybrid_f1": oracle_summaries.get("gold_seg_hybrid", {})
                    .get("modality_micro", {})
                    .get("f1"),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except (
        RuntimeError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
        Estg150B0DevelopmentError,
    ) as exc:
        print(f"Phase A correction failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
