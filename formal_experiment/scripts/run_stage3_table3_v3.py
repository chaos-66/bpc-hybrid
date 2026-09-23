# -*- coding: utf-8 -*-
"""Run the full-rule-base Stage 3 Table 3 v3 pipeline (zero API/network).

The runner reads only the blinded v3 inference view: each item has
``case_id``, ``bpmn_path`` and ``process_id``. It never reads pair role,
target rule, target type, target activity, mutation description, case map, or
Gold. All predictions are persisted before the separate evaluator is allowed
to read labels.
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

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
)
from bpc_hybrid.stage3_sun_style_checker import (  # noqa: E402
    SunStyleChecker,
    violated_types,
    winter_signals,
)

DEFAULT_VIEW = (
    ROOT / "data/development/stage3_synth"
    / "stage3_sun_style_inference_view_v3.json"
)
DEFAULT_TEXT_VIEW = (
    ROOT / "data/development/stage3_synth/stage3_regulation_text_view_v2.json"
)
DEFAULT_STAGE2_INPUT = ROOT / "data/input/gdpr7_stage2_input_v1.json"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
SUN_CONFIG = ROOT / "configs/sun_stage3_development_v1.json"
WINTER_CONFIG = ROOT / "configs/winter_stage3_development_v1.json"
WINTER_LEXICON_DIR = (
    ROOT.parent / "references" / "winter_2020_model_check"
    / "model_check" / "input" / "files"
)
OUT_DIR = ROOT / "outputs/development/stage3_table3_v3"
SCHEMA_VERSION = "stage3_table3_v3_predictions@1.0.0"

METHODS: dict[str, dict[str, Any]] = {
    "sun_rules_only_full_sun_stage3": {
        "label": "Sun (Rules-Only Stage 2 + Sun Stage 3)",
        "paper_label": "Sun",
        "predictions_path": (
            "data/predictions/gdpr7_sun_rule_only_v1/predictions.json"
        ),
        "expected_schema": "gdpr7_sun_rule_only_predictions@1.0.0",
        "stage2_kind": "rules_only",
    },
    "ours_direct_llm_full_sun_stage3": {
        "label": "Ours (Direct-LLM Stage 2 + same Sun Stage 3)",
        "paper_label": "Ours",
        "predictions_path": (
            "data/predictions/gdpr7_direct_llm_v1/predictions.json"
        ),
        "expected_schema": "gdpr7_direct_llm_predictions@1.0.0",
        "stage2_kind": "direct_llm",
    },
    "winter_2020_native_full_pipeline": {
        "label": "Winter (native full pipeline)",
        "paper_label": "Winter",
        "predictions_path": None,
        "expected_schema": None,
        "stage2_kind": "native_regulation_text",
    },
}
ALLOWED_INFERENCE_ITEM_KEYS = ("case_id", "bpmn_path", "process_id")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _project_inference_items(doc: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw in doc.get("items") or []:
        item = {key: raw.get(key) for key in ALLOWED_INFERENCE_ITEM_KEYS}
        if not all(item.get(key) for key in ALLOWED_INFERENCE_ITEM_KEYS):
            raise ValueError(f"invalid inference item: {raw!r}")
        if set(raw) - set(ALLOWED_INFERENCE_ITEM_KEYS):
            raise ValueError(
                f"forbidden inference fields present: "
                f"{sorted(set(raw) - set(ALLOWED_INFERENCE_ITEM_KEYS))!r}")
        items.append(item)
    return items


def _load_regulation_text_index(path: Path) -> dict[str, str]:
    doc = _load_json(path)
    out: dict[str, str] = {}
    for row in doc.get("rule_texts") or []:
        rule_id = str(row.get("rule_id") or "")
        text = str(row.get("rule_text") or "")
        expected = str(row.get("rule_text_sha256") or "")
        if expected and expected != _sha256_text(text):
            raise ValueError(f"regulation text hash mismatch for {rule_id}")
        if rule_id:
            out[rule_id] = text
    return out


def _sentence_texts_by_sample(stage2_input: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for rule in stage2_input.get("rules") or []:
        for sentence in rule.get("sentences") or []:
            sid = str(sentence.get("sample_id") or "")
            text = sentence.get("approved_text_en")
            if not sid or not isinstance(text, str):
                raise ValueError(f"invalid stage2 sentence: {sentence!r}")
            out[sid] = text
    return out


def _load_lexicon(name: str) -> list[str]:
    return [
        line.strip()
        for line in (WINTER_LEXICON_DIR / name).read_text(
            encoding="utf-8", errors="replace").splitlines()
        if line.strip()
    ]


def _check_outputs(out_dir: Path, overwrite: bool) -> None:
    if out_dir.exists() and any(out_dir.iterdir()) and not overwrite:
        raise SystemExit(
            f"refusing to overwrite existing output directory {out_dir}; "
            "pass --overwrite only for a deliberate rerun"
        )


def run(*, view_path: Path = DEFAULT_VIEW,
        text_view_path: Path = DEFAULT_TEXT_VIEW,
        stage2_input_path: Path = DEFAULT_STAGE2_INPUT,
        out_dir: Path = OUT_DIR,
        nlp_model: str = "en_core_web_sm",
        overwrite: bool = False) -> dict[str, Any]:
    _check_outputs(out_dir, overwrite)
    view = _load_json(view_path)
    if view.get("safety", {}).get("gold_labels_present") is not False:
        raise ValueError("v3 inference view is not declared Gold-blind")
    if view.get("safety", {}).get("rule_id_present") is not False:
        raise ValueError("v3 inference view must not contain rule id")
    items = _project_inference_items(view)

    stage2_input = _load_json(stage2_input_path)
    rule_ids = sorted({
        str(rule.get("rule_id"))
        for rule in stage2_input.get("rules") or []
        if rule.get("rule_id")
    })
    if not rule_ids:
        raise ValueError("stage2 input contains no rule ids")
    regulation_texts = _load_regulation_text_index(text_view_path)
    missing_text = sorted(set(rule_ids) - set(regulation_texts))
    if missing_text:
        raise ValueError(f"missing regulation text for {missing_text}")

    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    sun_cfg = _load_json(SUN_CONFIG)
    winter_cfg = _load_json(WINTER_CONFIG)
    thresholds = sun_cfg["method"]["thresholds"]

    import spacy  # type: ignore

    nlp = spacy.load(nlp_model)

    from bpc_hybrid.sun_stage3.gdpr_capsule_converter import build_rule_records
    from bpc_hybrid.sun_stage3.sun_model import SunProcessModel
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer
    from bpc_hybrid.winter_stage3.winter_clause import parse_regulation_paragraph
    from bpc_hybrid.winter_stage3.winter_model import (
        REACHABILITY_CORRECTED,
        parse_bpmn_file_winter,
    )
    from bpc_hybrid.winter_stage3.winter_pair import WinterPair
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity

    sim = WinterSimilarity(nlp)
    scorer = SunScorer(
        sim,
        float(thresholds["tau"]),
        float(thresholds["gamma"]),
        float(thresholds["theta"]),
        nlp=nlp,
    )
    sun_checker = SunStyleChecker(scorer, float(thresholds["tau"]))

    sentence_texts = _sentence_texts_by_sample(stage2_input)
    rule_records_by_method: dict[str, dict[str, dict[str, Any]]] = {}
    converter_summaries: dict[str, Any] = {}
    for method_id, method in METHODS.items():
        if method["predictions_path"] is None:
            continue
        capsule = _load_json(ROOT / str(method["predictions_path"]))
        records, summary = build_rule_records(
            capsule,
            sentence_texts,
            rule_ids,
            expected_schema=str(method["expected_schema"]),
        )
        rule_records_by_method[method_id] = records
        converter_summaries[method_id] = summary

    signalwords = set(_load_lexicon("signalwords.txt"))
    sequencemarkers = set(_load_lexicon("sequencemarkers.txt"))
    stopwords = set(_load_lexicon("stopwords.txt"))

    bpmn_record_cache: dict[str, dict[str, Any]] = {}
    sun_model_cache: dict[str, Any] = {}
    winter_model_cache: dict[str, Any] = {}
    winter_paragraph_cache: dict[str, Any] = {}

    def bpmn_record(path: str) -> dict[str, Any]:
        if path not in bpmn_record_cache:
            bpmn_record_cache[path] = parse_bpmn_file(
                ROOT / path, contract=contract)
        return bpmn_record_cache[path]

    def sun_model(path: str, process_id: str) -> Any:
        if path not in sun_model_cache:
            sun_model_cache[path] = SunProcessModel(
                process_id, bpmn_record(path), nlp)
        return sun_model_cache[path]

    def winter_model(path: str) -> Any:
        if path not in winter_model_cache:
            winter_model_cache[path] = parse_bpmn_file_winter(
                ROOT / path, nlp, stopwords,
                reachability_mode=REACHABILITY_CORRECTED)
        return winter_model_cache[path]

    def winter_paragraph(rule_id: str) -> Any:
        if rule_id not in winter_paragraph_cache:
            winter_paragraph_cache[rule_id] = parse_regulation_paragraph(
                rule_id,
                regulation_texts[rule_id],
                nlp,
                stopwords,
                signalwords,
                sequencemarkers,
                only_constraints=True,
            )
        return winter_paragraph_cache[rule_id]

    case_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def case_payload(method_id: str, item: dict[str, Any]) -> dict[str, Any]:
        key = (method_id, str(item["bpmn_path"]))
        if key in case_cache:
            return case_cache[key]
        path = str(item["bpmn_path"])
        process_id = str(item["process_id"])
        if method_id == "winter_2020_native_full_pipeline":
            model_w = winter_model(path)
            resources = {
                str(process.participant).lower()
                for process in model_w.processes
                if str(process.participant or "").strip()
            }
            matching: list[dict[str, Any]] = []
            signals_by_rule: dict[str, dict[str, Any]] = {}
            violations: list[dict[str, Any]] = []
            for rule_id in rule_ids:
                paragraph = winter_paragraph(rule_id)
                pair = WinterPair(
                    nlp,
                    sim,
                    model_w,
                    paragraph,
                    resources,
                    float(winter_cfg["method"]["gamma"]),
                    float(winter_cfg["method"]["delta"]),
                )
                signals = winter_signals(
                    pair=pair,
                    model=model_w,
                    paragraph=paragraph,
                    resource_set=resources,
                )
                score = float(pair.fitness)
                matching.append({
                    "rule_id": rule_id,
                    "matching_score": score,
                    "action_ratio": None,
                    "actor_object_ratio": None,
                    "relevant": score > 0.0,
                    "rank": None,
                })
                signals_by_rule[rule_id] = signals
                for check_type, signal in signals.items():
                    if signal.get("status") == "violated":
                        violations.append({
                            "rule_id": rule_id,
                            "violation_type": check_type,
                            "raw_score": signal.get("raw_score"),
                            "denominator": signal.get("denominator"),
                            "observable": bool(signal.get("observable")),
                            "reason": signal.get("reason"),
                        })
            matching.sort(key=lambda row: (-row["matching_score"], row["rule_id"]))
            for rank, row in enumerate(matching, start=1):
                row["rank"] = rank
            payload = {
                "matching": matching,
                "signals_by_rule": signals_by_rule,
                "violations": violations,
                "method_evidence": {
                    "winter_config_version": winter_cfg.get("config_version"),
                    "reachability_mode": REACHABILITY_CORRECTED,
                    "resource_set": sorted(resources),
                },
            }
        else:
            records = rule_records_by_method[method_id]
            model = sun_model(path, process_id)
            payload = sun_checker.check(model, records)
            payload["method_evidence"] = {
                "rule_action_counts": {
                    rid: len(record.get("actions") or [])
                    for rid, record in records.items()
                },
                "rule_actor_counts": {
                    rid: len(record.get("actors") or [])
                    for rid, record in records.items()
                },
            }
        payload = dict(payload)
        payload["violated_types"] = sorted({
            str(v["violation_type"]) for v in payload["violations"]
        })
        case_cache[key] = payload
        return payload

    prediction_rows: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda row: str(row["case_id"])):
        for method_id, method in METHODS.items():
            payload = case_payload(method_id, item)
            prediction_rows.append({
                "schema_version": SCHEMA_VERSION,
                "method_id": method_id,
                "method_label": method["label"],
                "paper_label": method["paper_label"],
                "case_id": str(item["case_id"]),
                "bpmn_path": str(item["bpmn_path"]),
                "process_id": str(item["process_id"]),
                "matching": payload["matching"],
                "violations": payload["violations"],
                "violated_types": payload["violated_types"],
                "signals_by_rule": payload["signals_by_rule"],
                "method_evidence": payload["method_evidence"],
                "inference_inputs": {
                    "current_bpmn_only": True,
                    "full_rule_base": True,
                    "case_gold_read": False,
                    "pair_role_read": False,
                    "target_rule_id_read": False,
                    "target_violation_type_read": False,
                    "target_activity_id_read": False,
                    "mutation_type_read": False,
                    "control_reference_read": False,
                },
            })

    predictions_path = out_dir / "predictions.jsonl"
    _write_jsonl(predictions_path, prediction_rows)

    rule_record_paths: dict[str, str] = {}
    for method_id, records in rule_records_by_method.items():
        path = out_dir / f"rule_records_{method_id}.json"
        _write_json(path, {
            "method_id": method_id,
            "converter_summary": converter_summaries[method_id],
            "records": records,
        })
        rule_record_paths[method_id] = _display_path(path)

    manifest_path = out_dir / "run_manifest.json"
    manifest = {
        "schema_version": "stage3_table3_v3_run@1.0.0",
        "status": "complete",
        "run_id": "stage3_table3_v3_full_rule_base",
        "scope": "full 9-rule Rule Base matching and Def4-7 checking per BPMN case",
        "inference_boundary": {
            "allowed_item_keys": list(ALLOWED_INFERENCE_ITEM_KEYS),
            "current_bpmn_only": True,
            "full_rule_base": True,
            "pair_role_read": False,
            "target_rule_id_read": False,
            "target_violation_type_read": False,
            "target_activity_id_read": False,
            "mutation_type_read": False,
            "control_reference_read": False,
            "case_map_read": False,
            "gold_read_by_runner": False,
        },
        "inputs": {
            "inference_view": {
                "path": _display_path(view_path),
                "sha256": _sha256_file(view_path),
            },
            "regulation_text_view": {
                "path": _display_path(text_view_path),
                "sha256": _sha256_file(text_view_path),
            },
            "stage2_input": {
                "path": _display_path(stage2_input_path),
                "sha256": _sha256_file(stage2_input_path),
            },
            "stage2_predictions": {
                method_id: ({
                    "path": method["predictions_path"],
                    "sha256": _sha256_file(ROOT / method["predictions_path"]),
                } if method["predictions_path"] else None)
                for method_id, method in METHODS.items()
            },
        },
        "configuration": {
            "similarity_backend": {"package": "spacy", "model": nlp_model},
            "sun_frozen_thresholds": {
                key: float(thresholds[key]) for key in ("tau", "gamma", "theta")
            },
            "sun_scorer": "bpc_hybrid.sun_stage3.sun_scorer.SunScorer",
            "converter": "bpc_hybrid.sun_stage3.gdpr_capsule_converter",
            "winter_config": {
                "path": _display_path(WINTER_CONFIG),
                "sha256": _sha256_file(WINTER_CONFIG),
                "gamma": winter_cfg["method"]["gamma"],
                "delta": winter_cfg["method"]["delta"],
                "reachability_mode": REACHABILITY_CORRECTED,
            },
            "one_sun_checker_for_sun_and_ours": True,
            "same_thresholds_for_sun_and_ours": True,
        },
        "methods": {
            method_id: {
                **method,
                "rule_records_path": rule_record_paths.get(method_id),
                "rule_records_sha256": (
                    _sha256_file(ROOT / rule_record_paths[method_id])
                    if method_id in rule_record_paths else None),
            }
            for method_id, method in METHODS.items()
        },
        "counts": {
            "cases": len(items),
            "methods": len(METHODS),
            "prediction_rows": len(prediction_rows),
            "rule_base_size": len(rule_ids),
        },
        "outputs": {
            "predictions_jsonl": {
                "path": _display_path(predictions_path),
                "sha256": _sha256_file(predictions_path),
            },
            "run_manifest": _display_path(manifest_path),
        },
        "code_sha256": {
            _display_path(path): _sha256_file(path)
            for path in [
                ROOT / "scripts/run_stage3_table3_v3.py",
                ROOT / "scripts/evaluate_stage3_table3_v3.py",
                ROOT / "scripts/build_stage3_table3_v3_benchmark.py",
                SRC / "bpc_hybrid/stage3_sun_style_checker.py",
                SRC / "bpc_hybrid/stage1_process.py",
                SRC / "bpc_hybrid/sun_stage3/gdpr_capsule_converter.py",
                SRC / "bpc_hybrid/sun_stage3/sun_scorer.py",
                SRC / "bpc_hybrid/sun_stage3/sun_model.py",
                SRC / "bpc_hybrid/winter_stage3/winter_clause.py",
                SRC / "bpc_hybrid/winter_stage3/winter_model.py",
                SRC / "bpc_hybrid/winter_stage3/winter_pair.py",
                SRC / "bpc_hybrid/winter_stage3/winter_similarity.py",
            ] if path.is_file()
        },
        "llm_api_calls": 0,
        "network_calls": 0,
        "existing_stage2_predictions_reused": True,
    }
    _write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--view", type=Path, default=DEFAULT_VIEW)
    parser.add_argument("--text-view", type=Path, default=DEFAULT_TEXT_VIEW)
    parser.add_argument("--stage2-input", type=Path, default=DEFAULT_STAGE2_INPUT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--nlp-model", default="en_core_web_sm")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    manifest = run(
        view_path=args.view,
        text_view_path=args.text_view,
        stage2_input_path=args.stage2_input,
        out_dir=args.out_dir,
        nlp_model=args.nlp_model,
        overwrite=args.overwrite,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
