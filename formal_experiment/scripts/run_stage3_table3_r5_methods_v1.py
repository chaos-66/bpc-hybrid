# -*- coding: utf-8 -*-
"""Run the frozen Stage-1 + Stage-3 method matrix for S3-TABLE3-R5.

No API, no Gold/reference read.  Loads only:
- the frozen R5 benchmark config/source/inference assets,
- the frozen fresh Sun B0 predictions,
- the frozen Ours Stage-2 predictions,
- the frozen Stage-1/BPMN and Sun/Winter method implementations.

Outputs method signals for all three methods without computing any metric.
The independent evaluator reads the Gold packet only after these outputs are
persisted and hashed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import spacy  # noqa: E402
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file  # noqa: E402
from bpc_hybrid.stage3_sun_style_checker import winter_signals  # noqa: E402
from bpc_hybrid.sun_stage3.no_gate_checker_v1 import NoGateSunChecker  # noqa: E402
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402
from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402
from bpc_hybrid.sun_stage3.temporal_projection_v3 import project_record_order_relations  # noqa: E402
from bpc_hybrid.winter_stage3.global_roles import collect_global_role_candidates  # noqa: E402
from bpc_hybrid.winter_stage3.winter_clause import parse_regulation_paragraph  # noqa: E402
from bpc_hybrid.winter_stage3.winter_model import (  # noqa: E402
    REACHABILITY_CORRECTED,
    parse_bpmn_file_winter,
)
from bpc_hybrid.winter_stage3.winter_pair import WinterPair  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v2.json"
BENCHMARK_DATA = ROOT / "data/development/stage3_table3_r5_benchmark_v2"
SOURCE_REQ = BENCHMARK_DATA / "source_requirements.json"
INFERENCE = BENCHMARK_DATA / "inference/inference_view.json"
SOURCE_TEXTS = BENCHMARK_DATA / "inference/source_texts.json"
STAGE1_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
SUN_PRED = ROOT / "data/predictions/stage3_table3_r5_sun_rule_only_v1/predictions.json"
SUN_MANIFEST = ROOT / "data/predictions/stage3_table3_r5_sun_rule_only_v1/manifest.json"
OURS_PRED = ROOT / "data/predictions/stage3_table3_r5_ours_stage2_formal_v1/predictions.json"
OURS_FREEZE = ROOT / "outputs/reports/stage3_table3_r5_ours_prediction_freeze_v1.json"
WINTER_CONFIG = ROOT / "configs/winter_stage3_development_v1.json"
SUN_CONFIG = ROOT / "configs/sun_stage3_development_v1.json"
WINTER_LEXICON_DIR = ROOT.parent / "references/winter_2020_model_check/model_check/input/files"
OUT_DIR = ROOT / "outputs/development/stage3_table3_r5_methods_v1"
REPORTS = ROOT / "outputs/reports"
STAGE1_MANIFEST = REPORTS / "stage1_table3_r5_formal_manifest_v1.json"
WINTER_MANIFEST = REPORTS / "stage3_table3_r5_winter_native_manifest_v1.json"
METHODS_REPORT = REPORTS / "stage3_table3_r5_methods_run_manifest_v1.json"
TYPES = ("missing_action", "incorrect_actor", "out_of_order")
SCHEMA_VERSION = "stage3_table3_r5_methods@1.0.0"


class MethodsRunError(RuntimeError):
    pass


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
    else:
        text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _git_state() -> dict[str, Any]:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout.strip()
        return {"commit": commit, "dirty_paths": dirty.splitlines()[:50]}
    except Exception as exc:  # noqa: BLE001
        return {"commit": "unknown", "dirty_paths": [str(exc)]}


def _load_core_sources() -> tuple[dict[str, Any], dict[str, Any], list[str], dict[str, str]]:
    config = _load_json(CONFIG)
    sources = {r["requirement_id"]: r for r in _load_json(SOURCE_REQ)["requirements"]}
    core_ids = [r["requirement_id"] for r in config["requirements"] if r.get("core_eligible")]
    if len(core_ids) != 33:
        raise MethodsRunError(f"expected 33 core requirements, got {len(core_ids)}")
    texts = {}
    for rid in core_ids:
        src = sources[rid]
        text = src["excerpt_text"]
        if _sha_text(text) != src["text_sha256"]:
            raise MethodsRunError(f"source text SHA drift: {rid}")
        texts[rid] = text
    return config, sources, core_ids, texts


def _load_cases() -> tuple[list[dict[str, Any]], dict[str, str]]:
    view = _load_json(INFERENCE)
    items = list(view.get("items") or [])
    if len(items) != 113:
        raise MethodsRunError(f"expected 113 inference cases, got {len(items)}")
    for item in items:
        if not all(item.get(k) for k in ("case_id", "bpmn_path", "process_id", "source_text_id", "common_context_id")):
            raise MethodsRunError(f"incomplete inference item: {item!r}")
    source_texts = {row["source_text_id"]: row for row in _load_json(SOURCE_TEXTS)["items"]}
    return items, source_texts


def _canonical_to_sun_record(record: Mapping[str, Any] | None, source_text: str,
                             rule_id: str, nlp: Any, doc: Any | None = None) -> dict[str, Any]:
    """Deterministic canonical-record -> Sun rule-record conversion.

    The same converter is used for Sun B0 and Ours Direct-LLM outputs.  It
    keeps obligation clauses, validates spans against the frozen source text,
    resolves actor-action links, and uses the frozen temporal_projection_v3
    for order relations.  It never repairs label semantics.
    """
    actions: list[str] = []
    actors: list[str] = []
    actor_action_pairs: list[dict[str, str]] = []
    dropped: list[str] = []
    included_clauses = 0
    if not isinstance(record, Mapping):
        return {
            "rule_id": rule_id, "actions": [], "actors": [], "actor_action_pairs": [],
            "order_relations": [], "failed": True,
            "failure_reasons": ["missing_or_invalid_record"],
            "conversion_audit": {"dropped_spans": [], "included_clauses": 0},
        }
    for ci, clause in enumerate(record.get("clauses") or []):
        if not isinstance(clause, Mapping):
            dropped.append(f"clauses[{ci}]")
            continue
        modality = (clause.get("modality") or {}).get("label")
        if modality != "obligation":
            continue
        included_clauses += 1
        action_by_id: dict[Any, str] = {}
        actor_by_id: dict[Any, str] = {}
        for field, target, id_map in (("actions", actions, action_by_id),
                                      ("actors", actors, actor_by_id)):
            for si, span in enumerate(clause.get(field) or []):
                if not isinstance(span, Mapping):
                    dropped.append(f"clauses[{ci}].{field}[{si}]")
                    continue
                start, end = span.get("start"), span.get("end")
                if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
                    dropped.append(f"clauses[{ci}].{field}[{si}]")
                    continue
                if not (0 <= start < end <= len(source_text)):
                    dropped.append(f"clauses[{ci}].{field}[{si}]")
                    continue
                text = source_text[start:end]
                if not text.strip():
                    dropped.append(f"clauses[{ci}].{field}[{si}]")
                    continue
                target.append(text)
                id_map[span.get("id")] = text
        for link in clause.get("actor_action_map") or []:
            if not isinstance(link, Mapping):
                continue
            actor = actor_by_id.get(link.get("actor_id"))
            action = action_by_id.get(link.get("action_id"))
            if actor and action:
                actor_action_pairs.append({"actor": actor, "action": action})
    order_relations: list[list[str]] = []
    projection_audit: dict[str, Any] = {"status": "not_attempted"}
    try:
        if doc is None:
            doc = nlp(source_text)
        edges, projection_audit = project_record_order_relations(record, source_text, doc)
        order_relations = [list(edge) for edge in edges]
    except Exception as exc:  # noqa: BLE001
        projection_audit = {"status": "failed", "failed_reasons": [f"{type(exc).__name__}: {exc}"]}
    return {
        "rule_id": rule_id,
        "actions": actions,
        "actors": actors,
        "actor_action_pairs": actor_action_pairs,
        "order_relations": order_relations,
        "failed": False,
        "failure_reasons": dropped,
        "conversion_audit": {
            "included_clauses": included_clauses,
            "dropped_spans": dropped,
            "order_projection": projection_audit,
        },
    }


def _load_rule_records(core_ids: list[str], texts: Mapping[str, str], nlp: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    ours_doc = _load_json(OURS_PRED)
    sun_doc = _load_json(SUN_PRED)
    freeze = _load_json(OURS_FREEZE)
    if freeze.get("combined_predictions", {}).get("sha256") != _sha_file(OURS_PRED):
        raise MethodsRunError("Ours prediction freeze SHA mismatch")
    if sun_doc.get("record_count") != 33:
        raise MethodsRunError("fresh Sun prediction count drift")
    ours_by_id = {r["requirement_id"]: r for r in ours_doc["records"]}
    sun_by_id = {r["requirement_id"]: r for r in sun_doc["records"]}
    docs = {rid: nlp(texts[rid]) for rid in core_ids}
    ours_records: dict[str, Any] = {}
    sun_records: dict[str, Any] = {}
    for rid in core_ids:
        ours_records[rid] = _canonical_to_sun_record(ours_by_id[rid].get("record"), texts[rid], rid, nlp, docs[rid])
        sun_records[rid] = _canonical_to_sun_record(sun_by_id[rid].get("record"), texts[rid], rid, nlp, docs[rid])
    audits = {
        "ours": {rid: ours_records[rid]["conversion_audit"] for rid in core_ids},
        "sun": {rid: sun_records[rid]["conversion_audit"] for rid in core_ids},
    }
    return ours_records, sun_records, audits


def _load_winter_lexicon() -> tuple[set[str], set[str], set[str]]:
    signalwords = set((WINTER_LEXICON_DIR / "signalwords.txt").read_text(encoding="utf-8").splitlines())
    sequencemarkers = set((WINTER_LEXICON_DIR / "sequencemarkers.txt").read_text(encoding="utf-8").splitlines())
    stopwords = set((WINTER_LEXICON_DIR / "stopwords.txt").read_text(encoding="utf-8").splitlines())
    return signalwords, sequencemarkers, stopwords


def _compact_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": signal.get("status"),
        "raw_score": signal.get("raw_score"),
        "denominator": signal.get("denominator"),
        "observable": signal.get("observable"),
        "reason": signal.get("reason"),
        "evidence": signal.get("evidence"),
    }


def run(nlp_model: str = "en_core_web_sm", overwrite: bool = False) -> dict[str, Any]:
    if OUT_DIR.exists() and any(OUT_DIR.iterdir()) and not overwrite:
        raise MethodsRunError(f"refusing to overwrite non-empty {OUT_DIR}")
    started = time.perf_counter()
    config, sources, core_ids, texts = _load_core_sources()
    items, source_texts = _load_cases()
    ours_rule_records, sun_rule_records, conversion_audits = _load_rule_records(core_ids, texts, None) if False else (None, None, None)
    # The line above is intentionally replaced before use; nlp is initialized below.
    nlp = spacy.load(nlp_model)
    ours_rule_records, sun_rule_records, conversion_audits = _load_rule_records(core_ids, texts, nlp)

    sim = WinterSimilarity(nlp)
    sun_cfg = _load_json(SUN_CONFIG)
    thresholds = sun_cfg["method"]["thresholds"]
    scorer = SunScorer(sim, float(thresholds["tau"]), float(thresholds["gamma"]),
                       float(thresholds["theta"]), nlp=nlp)
    checker = NoGateSunChecker(scorer)
    winter_cfg = _load_json(WINTER_CONFIG)
    signalwords, sequencemarkers, stopwords = _load_winter_lexicon()
    stage1_contract = load_stage1_contract(STAGE1_CONTRACT)

    global_roles = collect_global_role_candidates(_load_json(INFERENCE), BENCHMARK_DATA)
    resource_set = set(global_roles["roles"])
    if not resource_set:
        raise MethodsRunError("global role candidate set is empty")

    # Pre-parse rule-side Winter paragraphs once.
    paragraph_cache: dict[str, Any] = {}
    for rid in core_ids:
        paragraph_cache[rid] = parse_regulation_paragraph(
            rid, texts[rid], nlp, stopwords, signalwords, sequencemarkers,
            only_constraints=True,
        )

    predictions: list[dict[str, Any]] = []
    signals_matrix: list[dict[str, Any]] = []
    stage1_records: list[dict[str, Any]] = []
    winter_model_cache: dict[str, Any] = {}
    sun_model_cache: dict[str, Any] = {}
    winter_exception_count = 0
    for item in sorted(items, key=lambda row: str(row["case_id"])):
        case_id = str(item["case_id"])
        bpmn_path = str(item["bpmn_path"])
        process_id = str(item["process_id"])
        full_bpmn = BENCHMARK_DATA / bpmn_path
        if bpmn_path not in sun_model_cache:
            record = parse_bpmn_file(full_bpmn, contract=stage1_contract)
            sun_model_cache[bpmn_path] = {
                "record": record,
                "model": SunProcessModel(process_id, record, nlp),
            }
            stage1_records.append({
                "case_id": case_id,
                "bpmn_path": bpmn_path,
                "bpmn_sha256": record["source"]["sha256"],
                "process_id": record["process_id"],
                "process_record_sha256": _sha_text(json.dumps(record, ensure_ascii=False, sort_keys=True)),
                "stage1_parser": record["method"],
            })
        if bpmn_path not in winter_model_cache:
            winter_model_cache[bpmn_path] = parse_bpmn_file_winter(
                full_bpmn, nlp, stopwords, reachability_mode=REACHABILITY_CORRECTED,
            )
        model = sun_model_cache[bpmn_path]["model"]
        winter_model = winter_model_cache[bpmn_path]

        sun_payload = checker.check(model, sun_rule_records)
        ours_payload = checker.check(model, ours_rule_records)
        winter_signals_by_rule: dict[str, Any] = {}
        winter_matching: list[dict[str, Any]] = []
        for rid in core_ids:
            paragraph = paragraph_cache[rid]
            try:
                pair = WinterPair(nlp, sim, winter_model, paragraph, resource_set,
                                  float(winter_cfg["method"]["gamma"]),
                                  float(winter_cfg["method"]["delta"]))
                signals = winter_signals(pair=pair, model=winter_model, paragraph=paragraph,
                                         resource_set=resource_set)
                winter_matching.append({
                    "rule_id": rid,
                    "matching_score": float(pair.fitness),
                    "cost_obligation": float(pair.cost_obligation),
                    "cost_resource": float(pair.cost_resource),
                    "cost_so": float(pair.cost_so),
                })
            except Exception as exc:  # noqa: BLE001
                winter_exception_count += 1
                reason = f"native_exception:{type(exc).__name__}:{exc}"
                signals = {
                    t: {"status": "unknown", "raw_score": None, "denominator": 0,
                        "observable": False, "reason": reason, "evidence": {}}
                    for t in TYPES
                }
                winter_matching.append({"rule_id": rid, "matching_score": 0.0,
                                        "error": reason})
            winter_signals_by_rule[rid] = {t: _compact_signal(signals[t]) for t in TYPES}

        rows = {
            "sun": sun_payload,
            "ours": ours_payload,
            "winter": {
                "matching": winter_matching,
                "signals_by_rule": winter_signals_by_rule,
                "violations": [
                    {"rule_id": rid, "violation_type": t, "raw_score": sig.get("raw_score"),
                     "denominator": sig.get("denominator"), "observable": bool(sig.get("observable")),
                     "reason": sig.get("reason")}
                    for rid, by_type in winter_signals_by_rule.items()
                    for t, sig in by_type.items()
                    if sig.get("status") == "violated"
                ],
            },
        }
        for method_key, payload in rows.items():
            method_id = {"sun": "sun_b0_rules_only", "ours": "ours_direct_llm_stage2",
                         "winter": "winter_2020_native_full_pipeline"}[method_key]
            predictions.append({
                "case_id": case_id,
                "bpmn_path": bpmn_path,
                "process_id": process_id,
                "source_text_id": item.get("source_text_id"),
                "common_context_id": item.get("common_context_id"),
                "row_method_id": method_key,
                "method_id": method_id,
                "matching": payload.get("matching"),
                "signals_by_rule": payload.get("signals_by_rule"),
                "violations": payload.get("violations"),
                "checker_policy": {
                    "sun_ours": "no_gate_full_rule_base_v1" if method_key in ("sun", "ours") else None,
                    "winter_native": method_key == "winter",
                },
            })
            for rid in core_ids:
                signals = (payload.get("signals_by_rule") or {}).get(rid) or {}
                for check_type in TYPES:
                    signal = signals.get(check_type) or {}
                    signals_matrix.append({
                        "method": method_key,
                        "method_id": method_id,
                        "case_id": case_id,
                        "rule_id": rid,
                        "check_type": check_type,
                        "status": signal.get("status"),
                        "raw_score": signal.get("raw_score"),
                        "denominator": signal.get("denominator"),
                        "observable": signal.get("observable"),
                        "reason": signal.get("reason"),
                    })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    predictions_path = OUT_DIR / "predictions.json"
    signals_path = OUT_DIR / "signals_matrix.json"
    rule_records_path = OUT_DIR / "rule_records.json"
    stage1_path = OUT_DIR / "stage1_process_records.json"
    global_roles_path = OUT_DIR / "global_role_candidates.json"
    _write_json(predictions_path, {
        "schema_version": SCHEMA_VERSION,
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "gold_read_by_runner": False,
        "construction_reference_read": False,
        "counts": {"cases": len(items), "methods": 3, "prediction_rows": len(predictions),
                   "signals": len(signals_matrix)},
        "records": predictions,
    }, compact=True)
    _write_json(signals_path, {
        "schema_version": "stage3_table3_r5_signals@1.0.0",
        "count": len(signals_matrix),
        "signals": signals_matrix,
    }, compact=True)
    _write_json(rule_records_path, {
        "ours": {"method_id": "ours_direct_llm_stage2", "records": ours_rule_records,
                 "conversion_audit": conversion_audits["ours"]},
        "sun": {"method_id": "sun_b0_rules_only", "records": sun_rule_records,
                "conversion_audit": conversion_audits["sun"]},
    }, compact=True)
    _write_json(stage1_path, {
        "schema_version": "stage3_table3_r5_stage1_process_records@1.0.0",
        "count": len(stage1_records),
        "records": stage1_records,
    }, compact=True)
    _write_json(global_roles_path, global_roles)

    stage1_manifest = {
        "schema_version": "stage1_table3_r5_formal_manifest@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "status": "completed",
        "stage1_parser": {
            "method_name": "stage1_bpmn_xml_structural",
            "parser_version": "stage1_bpmn_parser@1.0.0",
            "contract_path": "configs/stage1_structural_s11_s14.json",
            "contract_sha256": _sha_file(STAGE1_CONTRACT),
        },
        "bpmns_parsed": len(stage1_records),
        "failures": [],
        "output": {"path": _rel(stage1_path), "sha256": _sha_file(stage1_path)},
        "records": stage1_records,
    }
    _write_json(STAGE1_MANIFEST, stage1_manifest)

    winter_manifest = {
        "schema_version": "stage3_table3_r5_winter_native_manifest@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "status": "completed",
        "method_id": "winter_2020_native_full_pipeline",
        "method_config": {"path": "configs/winter_stage3_development_v1.json", "sha256": _sha_file(WINTER_CONFIG)},
        "native_pipeline_preserved": True,
        "unsupported_kept_as_unknown": True,
        "forced_negative_conversion": False,
        "global_role_candidates": {"path": _rel(global_roles_path), "sha256": _sha_file(global_roles_path)},
        "signal_output": {"path": _rel(signals_path), "sha256": _sha_file(signals_path)},
        "counts": {"cases": len(items), "rule_records": len(core_ids), "signals": len(signals_matrix)},
        "native_exception_count": winter_exception_count,
        "reachability_mode": REACHABILITY_CORRECTED,
        "gamma": float(winter_cfg["method"]["gamma"]),
        "delta": float(winter_cfg["method"]["delta"]),
    }
    _write_json(WINTER_MANIFEST, winter_manifest)

    report = {
        "schema_version": "stage3_table3_r5_methods_run_manifest@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "status": "completed",
        "gold_read_by_methods": False,
        "inference_reference_forbidden": True,
        "counts": {"cases": len(items), "core_requirements": len(core_ids), "methods": 3,
                   "signals": len(signals_matrix)},
        "inputs": {
            "config": {"path": _rel(CONFIG), "sha256": _sha_file(CONFIG)},
            "source_requirements": {"path": _rel(SOURCE_REQ), "sha256": _sha_file(SOURCE_REQ)},
            "inference_view": {"path": _rel(INFERENCE), "sha256": _sha_file(INFERENCE)},
            "source_texts": {"path": _rel(SOURCE_TEXTS), "sha256": _sha_file(SOURCE_TEXTS)},
            "sun_predictions": {"path": _rel(SUN_PRED), "sha256": _sha_file(SUN_PRED)},
            "sun_manifest": {"path": _rel(SUN_MANIFEST), "sha256": _sha_file(SUN_MANIFEST)},
            "ours_predictions": {"path": _rel(OURS_PRED), "sha256": _sha_file(OURS_PRED)},
            "ours_freeze": {"path": _rel(OURS_FREEZE), "sha256": _sha_file(OURS_FREEZE)},
        },
        "outputs": {
            "predictions": {"path": _rel(predictions_path), "sha256": _sha_file(predictions_path)},
            "signals_matrix": {"path": _rel(signals_path), "sha256": _sha_file(signals_path)},
            "rule_records": {"path": _rel(rule_records_path), "sha256": _sha_file(rule_records_path)},
            "stage1_process_records": {"path": _rel(stage1_path), "sha256": _sha_file(stage1_path)},
            "global_role_candidates": {"path": _rel(global_roles_path), "sha256": _sha_file(global_roles_path)},
            "stage1_manifest": {"path": _rel(STAGE1_MANIFEST), "sha256": _sha_file(STAGE1_MANIFEST)},
            "winter_manifest": {"path": _rel(WINTER_MANIFEST), "sha256": _sha_file(WINTER_MANIFEST)},
        },
        "configuration": {
            "sun_thresholds": {k: float(thresholds[k]) for k in ("tau", "gamma", "theta")},
            "winter_gamma": float(winter_cfg["method"]["gamma"]),
            "winter_delta": float(winter_cfg["method"]["delta"]),
            "outer_matching_gate_applied": False,
            "one_sun_checker_for_sun_and_ours": True,
            "temporal_projection": "sun_stage3_temporal_projection_v3@1.0.0",
        },
        "dependency_versions": {"python": sys.version.split()[0], "spacy": spacy.__version__,
                                "spacy_model": nlp_model},
        "git": _git_state(),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "llm_api_calls": 0,
        "network_calls": 0,
        "timestamp_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    _write_json(METHODS_REPORT, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nlp-model", default="en_core_web_sm")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        report = run(nlp_model=args.nlp_model, overwrite=args.overwrite)
    except MethodsRunError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc), "llm_api_calls": 0}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
