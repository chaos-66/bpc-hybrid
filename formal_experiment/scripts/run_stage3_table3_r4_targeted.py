# -*- coding: utf-8 -*-
"""R4 targeted Stage-3 runner.

This is a thin wrapper around the frozen R3 runner.  It changes exactly one
prediction input: all four action comparisons use the P2 ``action_surface``
field on both sides.  It also adds evidence-only order diagnostics and strict
backend validation.  No LLM/API call is made and Winter is reused from R2.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.stage3_r3_p2_adapter_v1 import (  # noqa: E402
    R3P2Model,
    frozen_lemma,
)
from bpc_hybrid.sun_stage3.r4_action_surface_scorer import (  # noqa: E402
    R4_ACTION_MATCH_POLICY,
    R4ActionSurfaceScorer,
)

DEFAULT_SIDECAR_INDEX = ROOT / "outputs/development/stage3_table3_r3_p2_sidecars/index.json"

_ALLOWED_BACKENDS = {
    "sm": "sm",
    "frozen_spacy_sm_text_similarity": "sm",
    "en_core_web_sm": "sm",
    "static_vector_lg": "static_vector_lg",
    "en_core_web_lg_static_vector_mean_cosine": "static_vector_lg",
    "m2_static_vector_lg": "static_vector_lg",
}


def _load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _sha_file(path: Path) -> str:
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical_backend(value: Any) -> str:
    text = "" if value is None else str(value).strip().lower()
    if not text:
        raise ValueError("backend must be explicitly provided and non-empty")
    if text not in _ALLOWED_BACKENDS:
        raise ValueError(
            f"unsupported backend {value!r}; allowed values: "
            f"{sorted(_ALLOWED_BACKENDS)}"
        )
    return _ALLOWED_BACKENDS[text]


def _load_r3_runner() -> Any:
    path = ROOT / "scripts/run_stage3_table3_r3.py"
    spec = importlib.util.spec_from_file_location("stage3_table3_r3_runner_for_r4", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load R3 runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def _view_field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _projection_rejections(projection: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    projection = projection or {}
    for clause in projection.get("clause_audits") or []:
        clause_id = clause.get("clause_id")
        for rejection in clause.get("rejections") or []:
            if isinstance(rejection, Mapping) and rejection.get("reason"):
                out.append({"clause_id": clause_id, "reason": str(rejection["reason"]),
                            "detail": dict(rejection)})
        for marker in clause.get("markers") or []:
            if not isinstance(marker, Mapping):
                continue
            if marker.get("reason"):
                out.append({"clause_id": clause_id, "reason": str(marker["reason"]),
                            "detail": dict(marker)})
            for rejection in marker.get("main_action_rejections") or []:
                if isinstance(rejection, Mapping) and rejection.get("reason"):
                    out.append({"clause_id": clause_id, "reason": str(rejection["reason"]),
                                "detail": dict(rejection)})
    return out


def _order_category_for_refs(reason: str) -> str:
    text = reason.lower()
    if "multiple" in text or "predicate" in text or "multi" in text:
        return "projection_rejected_multiple_predicate"
    return "projection_rejected_span_or_projection"


def _order_diagnostic(signal: Mapping[str, Any], record: Mapping[str, Any],
                      model: Any, scorer: Any) -> dict[str, Any]:
    relations = list(record.get("order_relations") or [])
    views = list(record.get("order_relation_views") or [])
    projections = _projection_rejections(record.get("order_relation_projection"))
    gamma = float(getattr(scorer, "gamma"))
    status = str(signal.get("status") or "unknown")
    denominator = int(signal.get("denominator") or 0)
    endpoint_diagnostics: list[dict[str, Any]] = []

    if not relations:
        if projections:
            categories = sorted({_order_category_for_refs(row["reason"]) for row in projections})
            category = (categories[0] if len(categories) == 1
                        else "projection_rejected_multiple_predicate"
                        if any(c == "projection_rejected_multiple_predicate" for c in categories)
                        else "projection_rejected_span_or_projection")
        else:
            category = "no_rule_order_relation"
        return {
            "category": category,
            "raw_reason": signal.get("reason"),
            "status": status,
            "denominator": denominator,
            "order_relation_count": 0,
            "projection_rejections": projections,
            "endpoint_diagnostics": endpoint_diagnostics,
            "evidence_only": True,
        }

    model_sources = [action for action in getattr(model, "actions", []) or []
                     if scorer._model_action_source(action)]
    for index, pair in enumerate(relations):
        view = views[index] if index < len(views) and isinstance(views[index], Mapping) else {}
        for side, pos in (("before", 0), ("after", 1)):
            endpoint = pair[pos] if isinstance(pair, (list, tuple)) and len(pair) > pos else None
            view_row = view.get(side) or {}
            action_surface = view_row.get("action_surface")
            parse_status = view_row.get("parse_status")
            best_id = None
            best_score = 0.0
            category = None
            if parse_status != "parsed" or not (isinstance(action_surface, str) and action_surface.strip()):
                category = "rule_endpoint_parse_failure"
            else:
                best_id, best_score = scorer._best_action_match(endpoint, model)
                if not model_sources:
                    category = "model_endpoint_missing_action_surface"
                elif best_id is None:
                    category = "model_endpoint_missing_action_surface"
                elif not (float(best_score) > gamma):
                    category = "candidate_below_gamma"
                else:
                    category = "mapped_above_gamma"
            endpoint_diagnostics.append({
                "relation_index": index,
                "side": side,
                "constraint": [str(x) for x in pair] if isinstance(pair, (list, tuple)) else [str(pair)],
                "rule_endpoint_original_text": str(endpoint) if endpoint is not None else None,
                "rule_endpoint_action_surface": action_surface,
                "rule_endpoint_parse_status": parse_status,
                "rule_endpoint_legacy_match_source_text": view_row.get("match_source_text"),
                "selected_model_node_id": best_id,
                "best_action_similarity_raw": float(best_score) if best_score is not None else None,
                "gamma": gamma,
                "category": category,
            })

    if denominator > 0 and status in ("violated", "satisfied"):
        category = f"reachability_{status}"
    else:
        priority = [
            "rule_endpoint_parse_failure",
            "model_endpoint_missing_action_surface",
            "candidate_below_gamma",
            "other_mapping_or_reachability",
        ]
        present = {row["category"] for row in endpoint_diagnostics}
        category = next((item for item in priority if item in present), "other_mapping_or_reachability")
    return {
        "category": category,
        "raw_reason": signal.get("reason"),
        "status": status,
        "denominator": denominator,
        "order_relation_count": len(relations),
        "projection_rejections": projections,
        "endpoint_diagnostics": endpoint_diagnostics,
        "evidence_only": True,
    }


def _model_action_table(model: Any, scorer: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for action in getattr(model, "actions", []) or []:
        source = scorer._model_action_source(action)
        rows.append({
            "node_id": str(action.get("id")),
            "node_type": action.get("kind"),
            "original_label": action.get("name"),
            "action_surface": action.get("action_surface"),
            "business_object_surface": action.get("business_object_surface"),
            "legacy_match_source_text": action.get("match_source_text"),
            "r4_action_match_source_text": source,
            "r4_action_matching_text": scorer._lemma(source) if source else None,
            "parse_status": action.get("parse_status"),
        })
    return rows


def _mapping_rows(rule_records: Mapping[str, Mapping[str, Any]], model: Any,
                  scorer: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rule_id, record in sorted(rule_records.items()):
        for action in (record.get("actions") or []):
            action_surface = _view_field(action, "action_surface")
            legacy_source = _view_field(action, "match_source_text")
            rows.append({
                "rule_id": str(rule_id),
                "kind": "action",
                "rule_original_text": _view_field(action, "original_text", str(action)),
                "rule_action_surface": action_surface,
                "rule_business_object_surface": _view_field(action, "business_object_surface"),
                "rule_legacy_match_source_text": legacy_source,
                "rule_legacy_matching_text": _view_field(action, "matching_text"),
                "r4_action_match_source_text": action_surface,
                "r4_action_matching_text": scorer._lemma(action_surface) if action_surface else None,
                "rule_parse_status": _view_field(action, "parse_status"),
                "candidates": scorer.action_candidate_evidence(action, model),
            })
        for pair in record.get("order_relations") or []:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            for endpoint in pair:
                action_surface = _view_field(endpoint, "action_surface")
                rows.append({
                    "rule_id": str(rule_id),
                    "kind": "order_endpoint",
                    "rule_original_text": _view_field(endpoint, "original_text", str(endpoint)),
                    "rule_action_surface": action_surface,
                    "rule_business_object_surface": _view_field(endpoint, "business_object_surface"),
                    "rule_legacy_match_source_text": _view_field(endpoint, "match_source_text"),
                    "rule_legacy_matching_text": _view_field(endpoint, "matching_text"),
                    "r4_action_match_source_text": action_surface,
                    "r4_action_matching_text": scorer._lemma(action_surface) if action_surface else None,
                    "rule_parse_status": _view_field(endpoint, "parse_status"),
                    "offsets": _view_field(endpoint, "offsets"),
                    "candidates": scorer.action_candidate_evidence(endpoint, model),
                })
    return rows


def _make_r4_sun_case_payload(sidecars: Mapping[str, Mapping[str, Any]], state: Mapping[str, Any]):
    def payload(item: Mapping[str, Any], rule_records: Mapping[str, Mapping[str, Any]],
                checker: Any, nlp: Any, contract: Any, model_cache: dict[str, Any]):
        case_id = str(item["case_id"])
        sidecar = sidecars.get(case_id)
        if sidecar is None:
            raise RuntimeError(f"missing R3 sidecar for {case_id}")
        model = R3P2Model(sidecar)
        model.actor_match_sources = {}
        result = dict(checker.check(model, rule_records))
        scorer = checker.scorer

        # Evidence-only precise order diagnostics; scores/denominators/status
        # are not changed.
        for rule_id, signal_block in (result.get("signals_by_rule") or {}).items():
            record = rule_records.get(rule_id) or {}
            signal = (signal_block or {}).get("out_of_order") or {}
            diagnostic = _order_diagnostic(signal, record, model, scorer)
            signal["r4_order_diagnostic"] = diagnostic
            # Alias used by the frozen evaluator's diagnostic reader.
            signal["order_diagnostic"] = diagnostic

        mapping = _mapping_rows(rule_records, model, scorer)
        result["method_evidence"] = {
            **dict(result.get("method_evidence") or {}),
            "r4_action_matching": {
                "policy": R4_ACTION_MATCH_POLICY,
                "rule_side_source": "existing R3 action view -> action_surface",
                "model_side_source": "frozen P2 sidecar -> action_surface",
                "order_endpoint_source": "R3 endpoint view -> action_surface",
                "lemma": "same frozen SunScorer._lemma",
                "legacy_join_field_retained": "match_source_text, business_object_surface",
                "def6_action_gate_uses_same_function": True,
                "source_data_not_modified": True,
            },
            "r4_representation": {
                "p2_activity_sidecar": "frozen_p2_activity + R3 named-event extension",
                "r4_matching_text_rule": "non-empty action_surface then frozen lemma",
                "legacy_matching_text_rule": "non-empty action_surface then business_object_surface then frozen lemma",
                "model_action_count": len(model.actions),
                "model_actor_count": len(model.actors),
                "model_business_object_count": len(model.business_objects),
                "node_id_tie_break": "ascending_node_id",
                "sidecar_sha256": _sha_file(ROOT / str(state["sidecar_paths"][case_id])),
                "p2_assets": sidecar.get("p2_assets"),
            },
            "model_action_table": _model_action_table(model, scorer),
            "mapping_table": mapping,
        }
        result["r4_wiring"] = {
            "case_id": case_id,
            "sidecar_path": str(state["sidecar_paths"][case_id]),
            "sidecar_sha256": _sha_file(ROOT / str(state["sidecar_paths"][case_id])),
            "bpmn_sha256": sidecar.get("bpmn_sha256"),
            "process_record_sha256": sidecar.get("process_record_sha256"),
            "p2_assets": sidecar.get("p2_assets"),
        }
        return result

    return payload


def _annotate_winter_order_diagnostics(predictions: dict[str, Any]) -> None:
    for row in predictions.get("records") or []:
        if str(row.get("row_method_id")) != "winter":
            continue
        for signal_block in (row.get("signals_by_rule") or {}).values():
            signal = (signal_block or {}).get("out_of_order") or {}
            reason = str(signal.get("reason") or "")
            if signal.get("status") == "unknown":
                diagnostic = {
                    "category": "winter_native_unsupported",
                    "raw_reason": reason or "winter_native_no_rule_side_flow",
                    "status": "unknown",
                    "denominator": int(signal.get("denominator") or 0),
                    "evidence_only": True,
                    "note": "Winter native result is reused from R2; do not re-score or repair here.",
                }
            else:
                diagnostic = {
                    "category": f"reachability_{signal.get('status')}",
                    "raw_reason": signal.get("reason"),
                    "status": signal.get("status"),
                    "denominator": int(signal.get("denominator") or 0),
                    "evidence_only": True,
                    "note": "Winter native result is reused from R2; diagnostics are descriptive only.",
                }
            signal["r4_order_diagnostic"] = diagnostic
            signal["order_diagnostic"] = diagnostic


def _postprocess(out_dir: Path, *, config_path: Path, sidecar_index: Path,
                 backend: str, backend_raw: str, r3_manifest: Mapping[str, Any]) -> dict[str, Any]:
    predictions_path = out_dir / "predictions.json"
    signals_path = out_dir / "signals_matrix.json"
    rule_records_path = out_dir / "rule_records.json"
    global_roles_path = out_dir / "global_role_candidates.json"

    predictions = _load_json(predictions_path)
    predictions["schema_version"] = f"stage3_table3_r4_targeted_{backend}_predictions@1.0.0"
    predictions["dataset_id"] = "stage3_scoped_gdpr_v4_r4_targeted"
    predictions["r4_config"] = {
        "config_path": config_path.relative_to(ROOT).as_posix(),
        "config_sha256": _sha_file(config_path),
        "requested_backend": backend_raw,
        "canonical_backend": backend,
        "action_match_policy": R4_ACTION_MATCH_POLICY,
        "p2_sidecar_index": sidecar_index.relative_to(ROOT).as_posix(),
        "p2_sidecar_index_sha256": _sha_file(sidecar_index),
        "development_status": "development_retrospective_not_independent_test",
        "winter_status": "reused_from_r2",
        "reused_from_r3_run_id": r3_manifest.get("run_id"),
    }
    _annotate_winter_order_diagnostics(predictions)
    _write_json(predictions_path, predictions)

    signals_doc = _load_json(signals_path)
    signals_doc["schema_version"] = f"stage3_table3_r4_targeted_{backend}_signals@1.0.0"
    _write_json(signals_path, signals_doc)

    rule_records = _load_json(rule_records_path)
    rule_records["r4_action_matching_policy"] = {
        "policy": R4_ACTION_MATCH_POLICY,
        "legacy_join_retained_for_business_object_evidence": True,
        "def6_candidate_scope_unchanged": True,
    }
    _write_json(rule_records_path, rule_records)

    outputs = {
        "predictions": {"path": predictions_path.relative_to(ROOT).as_posix(),
                        "sha256": _sha_file(predictions_path)},
        "signals_matrix": {"path": signals_path.relative_to(ROOT).as_posix(),
                           "sha256": _sha_file(signals_path)},
        "rule_records": {"path": rule_records_path.relative_to(ROOT).as_posix(),
                         "sha256": _sha_file(rule_records_path)},
        "global_role_candidates": {"path": global_roles_path.relative_to(ROOT).as_posix(),
                                   "sha256": _sha_file(global_roles_path)},
    }
    code_paths = [
        Path(__file__),
        ROOT / "scripts/run_stage3_table3_r3.py",
        ROOT / "scripts/build_stage3_r3_sidecars.py",
        ROOT / "src/bpc_hybrid/stage3_r3_p2_adapter_v1.py",
        ROOT / "src/bpc_hybrid/sun_stage3/r4_action_surface_scorer.py",
        ROOT / "src/bpc_hybrid/sun_stage3/r3_sun_scorer.py",
        ROOT / "src/bpc_hybrid/sun_stage3/temporal_projection_v4_r3.py",
        ROOT / "src/bpc_hybrid/sun_stage3/static_vector_similarity_v1.py",
        ROOT / "src/bpc_hybrid/sun_stage3/no_gate_checker_v1.py",
        ROOT / "src/bpc_hybrid/sun_stage3/sun_scorer.py",
        ROOT / "src/bpc_hybrid/sun_stage3/gdpr_capsule_converter.py",
        ROOT / "src/bpc_hybrid/stage1_label_semantics_p2.py",
    ]
    manifest = dict(r3_manifest)
    manifest.update({
        "schema_version": f"stage3_table3_r4_targeted_{backend}_run@1.0.0",
        "run_id": f"stage3_table3_r4_targeted_{backend}_v1",
        "task_id": "S3-TABLE3-R4-TARGETED-FIX",
        "status": "complete",
        "development_status": "development_retrospective_not_independent_test",
        "outputs": outputs,
        "configuration": {
            **(manifest.get("configuration") or {}),
            "action_match_policy": R4_ACTION_MATCH_POLICY,
            "similarity_backend": {
                **(dict((manifest.get("configuration") or {}).get("similarity_backend") or {})),
                "requested_backend": backend_raw,
                "canonical_backend": backend,
                "actual_loaded_backend": (
                    "en_core_web_sm_spacy_text_similarity"
                    if backend == "sm" else "static_vector_lg_mean_cosine"
                ),
            },
            "legacy_join_retained_for_business_object_evidence": True,
            "def6_candidate_scope_unchanged": True,
        },
        "methods": {
            **(manifest.get("methods") or {}),
            "sun": {**(dict((manifest.get("methods") or {}).get("sun") or {})),
                     "status": "available_r4", "action_match_policy": R4_ACTION_MATCH_POLICY},
            "ours": {**(dict((manifest.get("methods") or {}).get("ours") or {})),
                      "status": "available_r4", "action_match_policy": R4_ACTION_MATCH_POLICY},
            "winter": {**(dict((manifest.get("methods") or {}).get("winter") or {})),
                        "status": "available_native_reused_from_r2",
                        "r4_status": "reused_from_r2_not_rerun"},
        },
        "inputs": {
            **(manifest.get("inputs") or {}),
            "execution_config": {"path": config_path.relative_to(ROOT).as_posix(),
                                 "sha256": _sha_file(config_path)},
            "p2_sidecar_index": {"path": sidecar_index.relative_to(ROOT).as_posix(),
                                  "sha256": _sha_file(sidecar_index)},
        },
        "code_sha256": {
            path.relative_to(ROOT).as_posix(): _sha_file(path)
            for path in code_paths if path.is_file()
        },
        "dependency_versions": {
            **(manifest.get("dependency_versions") or {}),
            "similarity_backend": {
                "canonical_backend": backend,
                "requested_backend": backend_raw,
                "actual_loaded_backend": (
                    "en_core_web_sm_spacy_text_similarity"
                    if backend == "sm" else "static_vector_lg_mean_cosine"
                ),
            },
        },
        "r4_action_matching": {
            "policy": R4_ACTION_MATCH_POLICY,
            "changed_input": "Sun/Ours action comparison uses action_surface on both sides",
            "definitions_using_same_function": ["Def4", "Def5", "Def6_internal_action_gate", "Def7"],
            "business_object_surface_preserved": True,
            "legacy_join_preserved_in_evidence_only": True,
        },
        "order_diagnostic_policy": {
            "evidence_only": True,
            "does_not_change_denominator_or_score": True,
            "categories": [
                "no_rule_order_relation",
                "projection_rejected_multiple_predicate",
                "projection_rejected_span_or_projection",
                "rule_endpoint_parse_failure",
                "model_endpoint_missing_action_surface",
                "candidate_below_gamma",
                "other_mapping_or_reachability",
                "reachability_satisfied",
                "reachability_violated",
                "winter_native_unsupported",
            ],
        },
        "llm_api_calls": 0,
        "network_calls": 0,
        "gold_read_by_runner": False,
        "construction_reference_read_by_runner": False,
    })
    output_hashes = {
        "predictions": {"path": predictions_path.relative_to(ROOT).as_posix(),
                        "sha256": _sha_file(predictions_path)},
        "signals_matrix": {"path": signals_path.relative_to(ROOT).as_posix(),
                           "sha256": _sha_file(signals_path)},
        "rule_records": {"path": rule_records_path.relative_to(ROOT).as_posix(),
                         "sha256": _sha_file(rule_records_path)},
        "global_role_candidates": {"path": global_roles_path.relative_to(ROOT).as_posix(),
                                   "sha256": _sha_file(global_roles_path)},
    }
    manifest["outputs"] = output_hashes
    _write_json(out_dir / "run_manifest.json", manifest)
    return manifest


def run(*, config_path: Path, out_dir: Path, backend: str,
        sidecar_index: Path = DEFAULT_SIDECAR_INDEX,
        nlp_model: str = "en_core_web_sm", lg_model_path: str | None = None,
        lg_model_name: str = "en_core_web_lg", overwrite: bool = False) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    out_dir = Path(out_dir).resolve()
    sidecar_index = Path(sidecar_index).resolve()
    cfg = _load_json(config_path)
    cfg_backend_raw = ((cfg.get("similarity") or {}).get("backend"))
    if not str(cfg_backend_raw or "").strip():
        raise RuntimeError("R4 execution config must explicitly declare similarity.backend")
    canonical_cli = _canonical_backend(backend)
    canonical_cfg = _canonical_backend(cfg_backend_raw)
    if canonical_cli != canonical_cfg:
        raise RuntimeError(
            f"CLI backend {backend!r} does not match config backend {cfg_backend_raw!r}"
        )

    r3 = _load_r3_runner()
    r3.R3SunScorer = R4ActionSurfaceScorer
    r3._make_sun_case_payload = _make_r4_sun_case_payload

    r3_manifest = r3.run(
        config_path=config_path,
        out_dir=out_dir,
        sidecar_index=sidecar_index,
        nlp_model=nlp_model,
        lg_model_path=lg_model_path,
        lg_model_name=lg_model_name,
        overwrite=overwrite,
    )
    return _postprocess(
        out_dir,
        config_path=config_path,
        sidecar_index=sidecar_index,
        backend=canonical_cli,
        backend_raw=str(cfg_backend_raw),
        r3_manifest=r3_manifest,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--backend", type=str, required=True,
                        help="explicit backend name; no default is provided")
    parser.add_argument("--sidecar-index", type=Path, default=DEFAULT_SIDECAR_INDEX)
    parser.add_argument("--nlp-model", default="en_core_web_sm")
    parser.add_argument("--lg-model-path", default=None)
    parser.add_argument("--lg-model-name", default="en_core_web_lg")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        manifest = run(config_path=args.config, out_dir=args.out_dir, backend=args.backend,
                       sidecar_index=args.sidecar_index, nlp_model=args.nlp_model,
                       lg_model_path=args.lg_model_path, lg_model_name=args.lg_model_name,
                       overwrite=args.overwrite)
    except ValueError as exc:
        print(f"backend configuration error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "run_id": manifest.get("run_id"),
        "status": manifest.get("status"),
        "counts": manifest.get("counts"),
        "outputs": manifest.get("outputs"),
        "reused_winter": manifest.get("reused_winter"),
        "r4_action_matching": manifest.get("r4_action_matching"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
