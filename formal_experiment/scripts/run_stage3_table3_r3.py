# -*- coding: utf-8 -*-
"""Run one frozen R3 diagnosis configuration (M1 or M2).

The actual D1/B0 frozen Stage-2 capsules and Winter R2 result are reused.  No
LLM/API call is made.  Sun and Ours are re-scored only through the frozen R3
adapter and projection; Winter is copied from the already-hashed R2 output and
is marked ``reused_from_r2``.
"""

from __future__ import annotations

import argparse
import importlib.util
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

from bpc_hybrid.stage3_r3_p2_adapter_v1 import (  # noqa: E402
    R3P2Model,
    build_endpoint_view,
    build_rule_action_views,
)
from bpc_hybrid.sun_stage3 import temporal_projection_v4_r3 as v4  # noqa: E402
from bpc_hybrid.sun_stage3.r3_sun_scorer import R3SunScorer  # noqa: E402
from bpc_hybrid.sun_stage3.static_vector_similarity_v1 import (  # noqa: E402
    StaticVectorSimilarity,
    directory_sha256,
)

DEFAULT_SIDECAR_INDEX = ROOT / "outputs/development/stage3_table3_r3_p2_sidecars/index.json"


def _sha_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def _load_r1_runner() -> Any:
    path = ROOT / "scripts/run_stage3_table3_v4_r1.py"
    spec = importlib.util.spec_from_file_location("stage3_table3_v4_r1_runner_for_r3", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load R1 runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _edge_detail_rows(audit: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for clause in audit.get("clause_audits") or []:
        for edge in clause.get("derived_edges") or []:
            rows.append(dict(edge))
        for edge in (clause.get("native") or {}).get("edges") or []:
            rows.append({"native": True, **dict(edge)})
    return rows


def _make_project_rule_records(nlp: Any, v4_module: Any, adapter: Any):
    from bpc_hybrid.sun_stage3.gdpr_capsule_converter import build_rule_records

    def project(capsule_path: Path, expected_schema: str,
                samples: Mapping[str, Mapping[str, Any]], nlp_arg: Any):
        capsule = _load_json(capsule_path)
        texts = {sid: sample["text"] for sid, sample in samples.items()}
        rule_ids = sorted({sample["rule_id"] for sample in samples.values()})
        records, converter_summary = build_rule_records(
            capsule, texts, rule_ids, expected_schema=expected_schema)
        projection_audits: dict[str, Any] = {}
        by_sample = {row.get("sample_id"): row for row in capsule.get("records") or []}
        sample_by_rule = {sample["rule_id"]: sample for sample in samples.values()}
        for rule_id, record in records.items():
            sample = sample_by_rule.get(rule_id)
            if sample is None:
                projection_audits[rule_id] = {"status": "missing_sample_mapping"}
                continue
            # Rule-side action matching views: only predicted action text is used.
            original_actions = list(record.get("actions") or [])
            action_views, action_evidence = build_rule_action_views(nlp_arg, original_actions)
            record["actions"] = action_views
            record["action_views"] = action_evidence
            view_by_text: dict[str, Any] = {}
            for view in action_views:
                view_by_text.setdefault(str(view), view)
            new_pairs: list[dict[str, Any]] = []
            for pair in record.get("actor_action_pairs") or []:
                row = dict(pair)
                raw_action = row.get("action")
                view = view_by_text.get(str(raw_action))
                if view is not None:
                    row["action"] = view
                    row.pop("r3_action_view_status", None)
                else:
                    row["r3_action_view_status"] = "unresolved_action_identity"
                new_pairs.append(row)
            record["actor_action_pairs"] = new_pairs

            env = by_sample.get(sample["sample_id"]) or {}
            canonical = env.get("record") if env.get("request_status") == "ok" else None
            if not isinstance(canonical, Mapping):
                projection_audits[rule_id] = {
                    "status": "skipped_no_canonical_record",
                    "request_status": env.get("request_status"),
                    "error_category": env.get("error_category"),
                }
                record["order_relations"] = []
                record["order_relation_views"] = []
                continue
            doc = nlp_arg(sample["text"])
            edges, audit = v4_module.project_record_order_relations(
                canonical, sample["text"], doc, nlp=nlp_arg)
            detail_rows = _edge_detail_rows(audit)
            used: set[int] = set()
            relation_views: list[dict[str, Any]] = []
            relation_pairs: list[tuple[Any, Any]] = []
            for before_text, after_text in edges:
                detail = None
                for idx, row in enumerate(detail_rows):
                    if idx in used:
                        continue
                    if str(row.get("before_text")) == str(before_text) and str(row.get("after_text")) == str(after_text):
                        detail = row
                        used.add(idx)
                        break
                before_offsets = detail.get("before_offsets") if detail else None
                after_offsets = detail.get("after_offsets") if detail else None
                before_view = build_endpoint_view(nlp_arg, str(before_text), offsets=before_offsets)
                after_view = build_endpoint_view(nlp_arg, str(after_text), offsets=after_offsets)
                relation_pairs.append((before_view, after_view))
                relation_views.append({
                    "before": before_view.to_dict(),
                    "after": after_view.to_dict(),
                    "branch": (detail or {}).get("second_endpoint_branch"),
                    "kind": (detail or {}).get("second_endpoint_kind"),
                    "predicate": (detail or {}).get("second_endpoint_predicate"),
                    "source": "native" if (detail or {}).get("native") else "derived",
                })
            record["order_relations"] = relation_pairs
            record["order_relation_views"] = relation_views
            record["order_relation_projection"] = audit
            projection_audits[rule_id] = audit
        return records, converter_summary, projection_audits

    return project


def _make_sun_case_payload(sidecars: Mapping[str, Mapping[str, Any]], state: Mapping[str, Any]):
    def payload(item: Mapping[str, Any], rule_records: Mapping[str, Mapping[str, Any]],
                checker: Any, nlp: Any, contract: Any, model_cache: dict[str, Any]):
        case_id = str(item["case_id"])
        sidecar = sidecars.get(case_id)
        if sidecar is None:
            raise RuntimeError(f"missing R3 sidecar for {case_id}")
        model = R3P2Model(sidecar)
        # Compatibility hook used by the R3 scorer for actor matching.
        model.actor_match_sources = {}
        result = checker.check(model, rule_records)
        result = dict(result)
        scorer = checker.scorer
        mapping_rows: list[dict[str, Any]] = []
        for rule_id, record in sorted(rule_records.items()):
            for action in (record.get("action_views") or []):
                pass
            action_views = list(record.get("actions") or [])
            for action in action_views:
                mapping_rows.append({
                    "rule_id": str(rule_id),
                    "kind": "action",
                    "rule_original_text": getattr(action, "original_text", str(action)),
                    "rule_action_surface": getattr(action, "action_surface", None),
                    "rule_business_object_surface": getattr(action, "business_object_surface", None),
                    "rule_match_source_text": getattr(action, "match_source_text", None),
                    "rule_matching_text": getattr(action, "matching_text", None),
                    "rule_parse_status": getattr(action, "parse_status", None),
                    "candidates": scorer.action_candidate_evidence(action, model),
                })
            for pair in record.get("order_relations") or []:
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    continue
                for endpoint in pair:
                    mapping_rows.append({
                        "rule_id": str(rule_id),
                        "kind": "order_endpoint",
                        "rule_original_text": getattr(endpoint, "original_text", str(endpoint)),
                        "rule_action_surface": getattr(endpoint, "action_surface", None),
                        "rule_business_object_surface": getattr(endpoint, "business_object_surface", None),
                        "rule_match_source_text": getattr(endpoint, "match_source_text", None),
                        "rule_matching_text": getattr(endpoint, "matching_text", None),
                        "rule_parse_status": getattr(endpoint, "parse_status", None),
                        "offsets": getattr(endpoint, "offsets", None),
                        "candidates": scorer.action_candidate_evidence(endpoint, model),
                    })
        result["method_evidence"] = {
            **dict(result.get("method_evidence") or {}),
            "r3_representation": {
                "p2_activity_sidecar": "frozen_p2_activity + R3 named-event extension",
                "matching_text_rule": "non-empty action_surface then business_object_surface, same frozen lemma",
                "model_action_count": len(model.actions),
                "model_actor_count": len(model.actors),
                "model_business_object_count": len(model.business_objects),
                "node_id_tie_break": "ascending_node_id",
                "sidecar_sha256": _sha_file(ROOT / sidecar_path_for_case(state, case_id)),
                "p2_assets": sidecar.get("p2_assets"),
            },
            "mapping_table": mapping_rows,
        }
        result["r3_wiring"] = {
            "case_id": case_id,
            "sidecar_path": sidecar_path_for_case(state, case_id),
            "sidecar_sha256": _sha_file(ROOT / sidecar_path_for_case(state, case_id)),
            "bpmn_sha256": sidecar.get("bpmn_sha256"),
            "process_record_sha256": sidecar.get("process_record_sha256"),
            "p2_assets": sidecar.get("p2_assets"),
        }
        return result

    return payload


def sidecar_path_for_case(state: Mapping[str, Any], case_id: str) -> str:
    return str(state["sidecar_paths"][case_id])


def _make_winter_reuse(winter_by_case: Mapping[str, Mapping[str, Any]], r2_manifest: Mapping[str, Any]):
    def payload(item: Mapping[str, Any], *args: Any, **kwargs: Any):
        case_id = str(item["case_id"])
        row = winter_by_case.get(case_id)
        if row is None:
            raise RuntimeError(f"missing R2 Winter row for {case_id}")
        result = {
            "matching": row.get("matching") or [],
            "signals_by_rule": row.get("signals_by_rule") or {},
            "violations": row.get("violations") or [],
            "violated_types": row.get("violated_types") or [],
            "method_evidence": {
                **dict(row.get("method_evidence") or {}),
                "r3_status": "reused_from_r2",
                "reused_source_manifest": r2_manifest.get("outputs"),
                "reused_source_predictions_run_id": r2_manifest.get("run_id"),
            },
        }
        return result

    return payload


def _load_sidecars(index_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    index = _load_json(index_path)
    sidecars: dict[str, Any] = {}
    paths: dict[str, str] = {}
    for row in index.get("cases") or []:
        case_id = str(row["case_id"])
        path = str(row["sidecar_path"])
        sidecars[case_id] = _load_json(ROOT / path)
        paths[case_id] = path
    return index, sidecars, paths


def _load_reused_winter(r2_out_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _load_json(r2_out_dir / "run_manifest.json")
    predictions = _load_json(r2_out_dir / "predictions.json")
    expected_sha = ((manifest.get("outputs") or {}).get("predictions") or {}).get("sha256")
    actual_sha = _sha_file(r2_out_dir / "predictions.json")
    if expected_sha and expected_sha != actual_sha:
        raise RuntimeError("R2 predictions SHA drift while reusing Winter")
    rows = {
        str(row["case_id"]): row
        for row in predictions.get("records") or []
        if str(row.get("row_method_id")) == "winter"
    }
    if len(rows) != 20:
        raise RuntimeError("R2 Winter reuse does not cover 20 cases")
    return rows, manifest


def _load_lg_model(lg_model_path: str | None, lg_model_name: str):
    import spacy  # type: ignore

    path = Path(lg_model_path) if lg_model_path else None
    if path and path.is_dir():
        nlp_lg = spacy.load(str(path))
        resource_sha = directory_sha256(path)
        model_path_record = path.as_posix()
    else:
        nlp_lg = spacy.load(lg_model_name)
        resource_sha = directory_sha256(Path(nlp_lg.path))
        model_path_record = str(nlp_lg.path)
    model_version = str(getattr(nlp_lg, "meta", {}).get("version", ""))
    return nlp_lg, model_path_record, model_version, resource_sha


def run(*, config_path: Path, out_dir: Path, sidecar_index: Path = DEFAULT_SIDECAR_INDEX,
        nlp_model: str = "en_core_web_sm", lg_model_path: str | None = None,
        lg_model_name: str = "en_core_web_lg", overwrite: bool = False) -> dict[str, Any]:
    cfg = _load_json(config_path)
    backend = str((cfg.get("similarity") or {}).get("backend") or "sm")
    r2_out_dir = ROOT / str(cfg["m0_reused_r2"]["out_dir"])
    sidecar_index_doc, sidecars, sidecar_paths = _load_sidecars(sidecar_index)
    if cfg.get("p2_sidecar_index", {}).get("sha256") not in (None, "", _sha_file(sidecar_index)):
        raise RuntimeError("R3 sidecar index SHA does not match config binding")
    winter_by_case, r2_manifest = _load_reused_winter(r2_out_dir)

    # Winter input/config binding check: the R2 manifest must declare the same
    # native Winter configuration and the same global-role candidate artifact.
    r2_methods = r2_manifest.get("methods") or {}
    if str((r2_methods.get("winter") or {}).get("status")) != "available_native":
        raise RuntimeError("R2 Winter status is not available_native; cannot reuse")
    if str(r2_manifest.get("dependency_versions", {}).get("spacy_model")) != "en_core_web_sm":
        raise RuntimeError("R2 Winter binding is not the frozen en_core_web_sm run")

    r1 = _load_r1_runner()
    r1.CONFIG = config_path
    r1.OUT_DIR = out_dir
    r1.SCHEMA_VERSION = f"stage3_table3_r3_{backend}_predictions@1.0.0"

    import bpc_hybrid.winter_stage3.winter_similarity as winter_similarity_module
    vector_model_info: dict[str, Any] = {"backend": "sm"}
    if backend == "static_vector_lg":
        nlp_lg, model_path_record, model_version, resource_sha = _load_lg_model(lg_model_path, lg_model_name)

        class _M2SimilarityFactory:
            def __new__(cls, nlp):
                return StaticVectorSimilarity(
                    nlp, nlp_lg,
                    model_path=model_path_record,
                    model_version=model_version,
                    resource_sha256=resource_sha,
                )

        winter_similarity_module.WinterSimilarity = _M2SimilarityFactory
        vector_model_info = {
            "backend": "static_vector_lg",
            "model_name": lg_model_name,
            "model_version": model_version,
            "model_path": model_path_record,
            "resource_sha256": resource_sha,
            "vector_dimension": int(getattr(nlp_lg, "vector_size", 0) or 0),
        }

    state = {"sidecar_paths": sidecar_paths}
    r1._project_rule_records = _make_project_rule_records(None, v4, None)
    r1.SunScorer = R3SunScorer
    r1._sun_case_payload = _make_sun_case_payload(sidecars, state)
    r1._winter_case_payload = _make_winter_reuse(winter_by_case, r2_manifest)

    started = time.perf_counter()
    manifest = r1.run(out_dir=out_dir, nlp_model=nlp_model, overwrite=overwrite)
    elapsed = round(time.perf_counter() - started, 3)

    # Postprocess version labels and R3 evidence.  The R1 writer has already
    # persisted the computed predictions but we rewrite only our R3 copies.
    predictions_path = out_dir / "predictions.json"
    signals_path = out_dir / "signals_matrix.json"
    rule_records_path = out_dir / "rule_records.json"
    global_roles_path = out_dir / "global_role_candidates.json"
    predictions = _load_json(predictions_path)
    predictions["schema_version"] = f"stage3_table3_r3_{backend}_predictions@1.0.0"
    predictions["dataset_id"] = f"stage3_scoped_gdpr_v4_r3_{backend}"
    predictions["r3_config"] = {
        "config_path": config_path.relative_to(ROOT).as_posix(),
        "config_sha256": _sha_file(config_path),
        "similarity_backend": vector_model_info,
        "p2_sidecar_index": sidecar_index.relative_to(ROOT).as_posix(),
        "p2_sidecar_index_sha256": _sha_file(sidecar_index),
        "frozen_development_status": "development_retrospective",
    }
    # Ensure all Winter rows explicitly expose reuse at top level.
    for row in predictions.get("records") or []:
        if str(row.get("row_method_id")) == "winter":
            row.setdefault("method_evidence", {})["r3_status"] = "reused_from_r2"
    _write_json(predictions_path, predictions)

    signals_doc = _load_json(signals_path)
    signals_doc["schema_version"] = f"stage3_table3_r3_{backend}_signals@1.0.0"
    _write_json(signals_path, signals_doc)

    actual_case_ids = sorted({str(row.get("case_id")) for row in predictions.get("records") or []})
    actual_rule_ids = sorted({str(rid) for row in predictions.get("records") or []
                              for rid in (row.get("signals_by_rule") or {})})
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
        ROOT / "scripts/run_stage3_table3_v4_r1.py",
        ROOT / "scripts/build_stage3_r3_sidecars.py",
        ROOT / "src/bpc_hybrid/stage3_r3_p2_adapter_v1.py",
        ROOT / "src/bpc_hybrid/sun_stage3/temporal_projection_v4_r3.py",
        ROOT / "src/bpc_hybrid/sun_stage3/r3_sun_scorer.py",
        ROOT / "src/bpc_hybrid/sun_stage3/static_vector_similarity_v1.py",
        ROOT / "src/bpc_hybrid/sun_stage3/temporal_projection_v1.py",
        ROOT / "src/bpc_hybrid/sun_stage3/temporal_projection_v2.py",
        ROOT / "src/bpc_hybrid/sun_stage3/temporal_projection_v3.py",
        ROOT / "src/bpc_hybrid/sun_stage3/no_gate_checker_v1.py",
        ROOT / "src/bpc_hybrid/sun_stage3/sun_scorer.py",
        ROOT / "src/bpc_hybrid/sun_stage3/gdpr_capsule_converter.py",
        ROOT / "src/bpc_hybrid/stage1_label_semantics_p2.py",
    ]
    r3_manifest: dict[str, Any] = {
        "schema_version": f"stage3_table3_r3_{backend}_run@1.0.0",
        "run_id": f"stage3_table3_r3_{backend}",
        "status": "complete",
        "development_status": "development_retrospective_not_independent_test",
        "scope": cfg.get("scope"),
        "outputs": outputs,
        "inputs": {
            "execution_config": {"path": config_path.relative_to(ROOT).as_posix(),
                                 "sha256": _sha_file(config_path)},
            "p2_sidecar_index": {"path": sidecar_index.relative_to(ROOT).as_posix(),
                                  "sha256": _sha_file(sidecar_index)},
            "r2_reused_predictions": (r2_manifest.get("outputs") or {}).get("predictions"),
            "r2_reused_manifest": {"path": (r2_out_dir / "run_manifest.json").relative_to(ROOT).as_posix(),
                                    "sha256": _sha_file(r2_out_dir / "run_manifest.json")},
            "sun_predictions": (r2_manifest.get("inputs") or {}).get("sun_predictions"),
            "ours_predictions": (r2_manifest.get("inputs") or {}).get("ours_predictions"),
        },
        "methods": {
            "sun": {"method_id": (cfg.get("methods") or {}).get("sun", {}).get("method_id", "sun_b0_frozen_v1"),
                    "status": "available_r3", "projection": "sun_stage3_temporal_projection_v4_r3@1.0.0"},
            "ours": {"method_id": (cfg.get("methods") or {}).get("ours", {}).get("method_id", "ours_d1_frozen_v1"),
                     "status": "available_r3", "projection": "sun_stage3_temporal_projection_v4_r3@1.0.0"},
            "winter": {"method_id": "winter_2020_native_full_pipeline",
                       "status": "available_native_reused_from_r2",
                       "reused_from": (r2_out_dir / "predictions.json").relative_to(ROOT).as_posix()},
        },
        "counts": {"cases": 20, "methods": 3, "prediction_rows": len(predictions.get("records") or []),
                   "signals": len(signals_doc.get("signals") or [])},
        "actual_output_case_ids": actual_case_ids,
        "actual_output_rule_ids": actual_rule_ids,
        "configuration": {
            "similarity_backend": vector_model_info,
            "sun_thresholds": (r2_manifest.get("configuration") or {}).get("sun_thresholds"),
            "outer_matching_gate_applied": False,
            "temporal_projection": cfg.get("temporal_projection"),
            "p2_adapter": "src/bpc_hybrid/stage3_r3_p2_adapter_v1.py",
            "p2_original_implementation": "src/bpc_hybrid/stage1_label_semantics_p2.py",
        },
        "reused_winter": {
            "status": "reused_not_rerun",
            "source_predictions": (r2_out_dir / "predictions.json").relative_to(ROOT).as_posix(),
            "source_predictions_sha256": _sha_file(r2_out_dir / "predictions.json"),
            "binding_note": "R2 native Winter config and global role-candidate input reused; not rerun in R3.",
        },
        "code_sha256": {
            path.relative_to(ROOT).as_posix(): _sha_file(path)
            for path in code_paths if path.is_file()
        },
        "dependency_versions": {
            "python": sys.version.split()[0],
            "spacy": __import__("spacy").__version__,
            "spacy_model": nlp_model,
            "similarity_backend": vector_model_info,
        },
        "git": r1._git_state(),
        "command": f"python formal_experiment/scripts/run_stage3_table3_r3.py --config {config_path.relative_to(ROOT).as_posix()} --out-dir {out_dir.relative_to(ROOT).as_posix()}",
        "elapsed_seconds": elapsed,
        "llm_api_calls": 0,
        "network_calls": 0,
        "gold_read_by_runner": False,
        "construction_reference_read_by_runner": False,
    }
    _write_json(out_dir / "run_manifest.json", r3_manifest)
    return r3_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--sidecar-index", type=Path, default=DEFAULT_SIDECAR_INDEX)
    parser.add_argument("--nlp-model", default="en_core_web_sm")
    parser.add_argument("--lg-model-path", default=None)
    parser.add_argument("--lg-model-name", default="en_core_web_lg")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    manifest = run(config_path=args.config, out_dir=args.out_dir,
                   sidecar_index=args.sidecar_index, nlp_model=args.nlp_model,
                   lg_model_path=args.lg_model_path, lg_model_name=args.lg_model_name,
                   overwrite=args.overwrite)
    print(json.dumps({k: manifest.get(k) for k in ("run_id", "status", "counts", "outputs", "reused_winter")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
