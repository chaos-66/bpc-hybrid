# -*- coding: utf-8 -*-
"""One-time legacy seen-test diagnostic replay for frozen Stage 3-v2.

This script refuses to run until the Stage 3-v2 semantic-backend and order
projection freeze manifests exist.  It is NOT a final unseen test and its
results are labelled ``LEGACY_SEEN_TEST_DIAGNOSTIC``.  It must not be used to
change the frozen backend, thresholds, projection, Gold, predictions, or metric
definitions.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from run_stage3_v2_development import (  # noqa: E402
    BENCHMARK,
    INFERENCE_VIEW,
    ORDER_SCOPE,
    SEM_BACKEND_FREEZE,
    ORDER_PROJECTION_FREEZE,
    SOURCE_REQUIREMENTS,
    SPACY_MD,
    SPACY_SM,
    build_case_index,
    build_converted_records,
    build_process_models,
    load_json,
    sha_file,
    write_json,
)
from bpc_hybrid.stage3_v2.checker_v2 import TYPES, SharedStage3CheckerV2  # noqa: E402
from bpc_hybrid.stage3_v2.evaluation_v2 import evaluate_dev_method  # noqa: E402
from bpc_hybrid.stage3_v2.semantic_matcher_v2 import SharedSemanticMatcherV2  # noqa: E402

REFERENCE_CASES = BENCHMARK / "reference/reference_cases.json"
OUT_JSON = ROOT / "outputs/reports/stage3_v2_legacy_test_diagnostic_v1.json"
OUT_MD = ROOT / "outputs/reports/stage3_v2_legacy_test_diagnostic_v1.md"
TAU = 0.8


def require_freeze() -> dict[str, Any]:
    if not SEM_BACKEND_FREEZE.exists() or not ORDER_PROJECTION_FREEZE.exists():
        raise RuntimeError("Stage 3-v2 freeze manifests are missing; refusing legacy replay")
    semantic = load_json(SEM_BACKEND_FREEZE)
    order = load_json(ORDER_PROJECTION_FREEZE)
    if semantic.get("status") != "SEMANTIC_BACKEND_FROZEN":
        raise RuntimeError("semantic backend is not frozen; refusing legacy replay")
    if order.get("status") != "ORDER_PROJECTION_FROZEN":
        raise RuntimeError("order projection is not frozen; refusing legacy replay")
    return {"semantic": semantic, "order": order}


def _md(report: dict[str, Any]) -> str:
    lines = [
        "# Stage 3-v2 Legacy Seen-Test Diagnostic v1",
        "",
        "- label: `LEGACY_SEEN_TEST_DIAGNOSTIC`",
        "- final unseen test: `false`",
        "- frozen backend: `%s`" % report["selected_backend"],
        "- frozen gamma/theta: `%s` / `%s`" % (report["selected_gamma"], report["selected_theta"]),
        "- no post-result modification: `true`",
        "",
        "## Overall",
        "",
        "| Method | Missing F1 | Actor F1 | TYPE-A Order F1 | Macro-F1 | Micro-F1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method in ("sun", "ours"):
        m = report["overall"][method]
        lines.append(
            "| %s | %s | %s | %s | %s | %s |" % (
                method.capitalize(),
                _fmt(m["per_type"]["missing_action"]["f1"]),
                _fmt(m["per_type"]["incorrect_actor"]["f1"]),
                _fmt(m["per_type"]["out_of_order"]["f1"]),
                _fmt(m["macro_f1"]),
                _fmt(m["micro_f1"]),
            )
        )
    lines.extend([
        "",
        "## Split Summary",
        "",
        "| Split | Method | Macro-F1 | Micro-F1 |",
        "|---|---|---:|---:|",
    ])
    for split in ("development", "test"):
        for method in ("sun", "ours"):
            m = report["splits"][split][method]
            lines.append("| %s | %s | %s | %s |" % (
                split, method, _fmt(m["macro_f1"]), _fmt(m["micro_f1"])
            ))
    lines.extend([
        "",
        "## Quarantine Statement",
        "",
        report["quarantine_statement"],
    ])
    return "\n".join(lines) + "\n"


def _fmt(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def main() -> None:
    started = time.perf_counter()
    require_freeze()
    semantic = load_json(SEM_BACKEND_FREEZE)
    backend_name = str(semantic["selected_backend"]["short_name"])
    gamma = float(semantic["gamma"])
    theta = float(semantic["theta"])
    if backend_name not in (SPACY_MD, SPACY_SM):
        raise RuntimeError(f"unsupported frozen backend {backend_name!r}")

    reference = load_json(REFERENCE_CASES)
    all_cases = []
    for case in reference["cases"]:
        row = {
            "case_id": str(case["case_id"]),
            "requirement_id": str(case["requirement_id"]),
            "source_family_id": str(case.get("source_family_id")),
            "split": str(case.get("split")),
            "variant": str(case.get("variant")),
            "reference_states": dict(case.get("reference_states") or {}),
        }
        all_cases.append(row)
    case_index = build_case_index()
    for case in all_cases:
        case.update(case_index[case["case_id"]])
    order_scope_doc = load_json(ORDER_SCOPE)
    order_scope = {
        rid: str(row.get("order_type") or "")
        for rid, row in order_scope_doc["requirements"].items()
    }
    source_doc = load_json(SOURCE_REQUIREMENTS)
    source_texts = {str(row["requirement_id"]): str(row["excerpt_text"])
                    for row in source_doc["requirements"]}

    matcher = SharedSemanticMatcherV2.for_backend(backend_name)
    nlp = matcher.backend.nlp
    requirement_ids = sorted({case["requirement_id"] for case in all_cases})
    converted = build_converted_records(case_index, source_doc["requirements"],
                                        source_texts, nlp, requirement_ids)
    models = build_process_models(case_index, nlp)
    checker = SharedStage3CheckerV2(matcher, nlp, tau=TAU, gamma=gamma, theta=theta)
    signals: dict[tuple[str, str, str], dict[str, Any]] = {}
    for case in all_cases:
        case_id = case["case_id"]
        requirement_id = case["requirement_id"]
        model = models[case_id]
        for method in ("sun", "ours"):
            checked = checker.check_rule_record(converted[method][requirement_id], model)
            for check_type in TYPES:
                signals[(method, case_id, check_type)] = checked[check_type]

    overall = {
        method: evaluate_dev_method(method, all_cases, signals, order_scope, fail_on_test=False)
        for method in ("sun", "ours")
    }
    splits: dict[str, dict[str, Any]] = {}
    for split in ("development", "test"):
        subset = [case for case in all_cases if case["split"] == split]
        splits[split] = {
            method: evaluate_dev_method(method, subset, signals, order_scope,
                                        fail_on_test=(split == "development"))
            for method in ("sun", "ours")
        }
    report = {
        "schema_version": "stage3_v2_legacy_test_diagnostic@1.0.0",
        "status": "LEGACY_SEEN_TEST_DIAGNOSTIC",
        "final_unseen_test": False,
        "selected_backend": backend_name,
        "selected_gamma": gamma,
        "selected_theta": theta,
        "benchmark_manifest_sha256": sha_file(BENCHMARK / "manifest.json"),
        "gold_packet_sha256": sha_file(ROOT / "outputs/reports/stage3_table3_r5_gold_adjudication_packet_v1.json"),
        "semantic_freeze_sha256": sha_file(SEM_BACKEND_FREEZE),
        "order_projection_freeze_sha256": sha_file(ORDER_PROJECTION_FREEZE),
        "overall": overall,
        "splits": splits,
        "quarantine_statement": (
            "This is ONE post-freeze replay on the legacy seen test split. It is not a "
            "blind final test and must not be cited as final Table 3. No backend, threshold, "
            "projection, Gold, prediction, or metric was changed after this diagnostic."
        ),
        "runtime_seconds": round(time.perf_counter() - started, 3),
        "real_api_calls": 0,
        "network_calls": 0,
    }
    write_json(OUT_JSON, report)
    OUT_MD.write_text(_md(report), encoding="utf-8", newline="\n")
    print("LEGACY_SEEN_TEST_DIAGNOSTIC complete:", OUT_JSON, OUT_MD)


if __name__ == "__main__":
    main()
