# -*- coding: utf-8 -*-
"""S1.1-S1.4 task matrix + status sync evidence (zero-API, 2026-08-11).

Per-task matrix: current code / schema / config / fixtures / tests /
manifest / met-DoD / real gaps / accurate status. Based on the verified
assets (parsers, schemas, gates, 37 stage-1 tests) plus the GDPR-7
double-run determinism verifier.

Statuses:
- S1.1 verified (Process Record schema + fixtures + validator met)
- S1.2 verified (deterministic parsing of test BPMNs + all 7 GDPR files)
- S1.3 partial (P0/P1 mechanical label semantics done; P2 not implemented)
- S1.4 verified (control-flow / reachability / branch / parallel / cycle
  tests pass)

Outputs:
- outputs/reports/s1_1_s1_4_matrix_v1.json
- outputs/reports/s1_1_s1_4_matrix_v1.md
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OUT_JSON = ROOT / "outputs" / "reports" / "s1_1_s1_4_matrix_v1.json"
OUT_MD = ROOT / "outputs" / "reports" / "s1_1_s1_4_matrix_v1.md"

DETERMINISM_MANIFEST = ROOT / "outputs" / "reports" / "s1_1_s1_4_determinism_v1.manifest.json"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_matrix() -> dict:
    determinism = json.loads(DETERMINISM_MANIFEST.read_text(encoding="utf-8"))
    rows = {
        "S1.1": {
            "task": "BPMN input + Process Record schema",
            "code": ["src/bpc_hybrid/stage1_process.py (parse + validate)"],
            "schema": "configs/schemas/process_record.schema.json (process_record@1.0.0)",
            "config": "configs/stage1_structural_s11_s14.json",
            "fixtures": ["tests/fixtures/stage1/s11_branch_parallel.bpmn",
                         "tests/fixtures/stage1/s14_cycle_unreachable.bpmn"],
            "tests": "tests/test_s1_1_s1_4_stage1_structural.py (contract freeze, malformed XML, duplicate id, DOCTYPE, fail-closed)",
            "manifest": "outputs/reports/s11_s14_stage1_structural_manifest.json",
            "met_doD": ["schema", "fixtures", "validator"],
            "gaps": [],
            "status": "verified",
        },
        "S1.2": {
            "task": "activity/event/gateway/flow/lane parsing",
            "code": ["src/bpc_hybrid/stage1_process.py (ACTIVITY_TYPES/EVENT_TYPES/GATEWAY_TYPES, pools/lanes/sequence flows)"],
            "schema": "process_record.schema.json (pools/lanes/activities/events/gateways/sequence_flows)",
            "config": "configs/stage1_structural_s11_s14.json",
            "fixtures": ["tests/fixtures/stage1/s11_branch_parallel.bpmn"],
            "tests": "test_s1_1_s1_4_stage1_structural.py (branch/parallel/condition/is_default)",
            "manifest": "s11_s14_stage1_structural_manifest.json",
            "met_doD": ["deterministic stable output on test BPMNs", "7/7 GDPR files double-run byte-identical (s1_1_s1_4_determinism_v1)"],
            "gaps": [],
            "status": "verified",
        },
        "S1.3": {
            "task": "actor/action/object label parsing",
            "code": ["src/bpc_hybrid/stage1_label_semantics.py (P0 raw-only; P1 surface split)"],
            "schema": "configs/schemas/stage1_label_semantics.schema.json",
            "config": "configs/stage1_label_semantics_s13.json",
            "fixtures": ["tests/fixtures/stage1/s13_label_edge_cases.bpmn"],
            "tests": "tests/test_s1_3_stage1_label_semantics.py (P0 no-inference, P1 edge cases, stable hash)",
            "manifest": "outputs/reports/s13_stage1_label_semantics_manifest.json",
            "met_doD": ["P0 raw-only sidecar", "P1 surface split sidecar"],
            "gaps": ["P2 label semantics not implemented (DoD 'P0/P1/P2 replaceable runs' partially met); actor/action/object remain machine candidates, never Gold"],
            "status": "partial",
        },
        "S1.4": {
            "task": "control flow and reachability",
            "code": ["src/bpc_hybrid/stage1_process.py (control_flow 12-key block)"],
            "schema": "process_record.schema.json control_flow (direct_edges/reachable_pairs/order_relations/branching/parallel/cycle/unreachable)",
            "config": "configs/stage1_structural_s11_s14.json",
            "fixtures": ["tests/fixtures/stage1/s14_cycle_unreachable.bpmn",
                         "tests/fixtures/stage1/s11_branch_parallel.bpmn"],
            "tests": "test_s1_1_s1_4_stage1_structural.py (cycle, unreachable, parallel split/join, order relations)",
            "manifest": "s11_s14_stage1_structural_manifest.json",
            "met_doD": ["branch/parallel/order tests pass", "reachability/cycle/unreachable fail-closed"],
            "gaps": [],
            "status": "verified",
        },
    }
    return {
        "schema_version": "s1_1_s1_4_matrix@1.0.0",
        "project_date": "2026-08-11",
        "scope": "7 GDPR BPMN (data/input/stage1_stage3/gdpr7) as the ONLY active input; references/archive not activated",
        "rows": rows,
        "determinism": {
            "path": "outputs/reports/s1_1_s1_4_determinism_v1.manifest.json",
            "sha256": _sha256_file(DETERMINISM_MANIFEST),
            "double_run_byte_identical": determinism["checks"]["double_run_byte_identical"],
            "matches_locked_process_records": determinism["checks"]["matches_locked_process_records"],
        },
        "boundaries": {
            "actor_action_object_are_machine_candidates_only": True,
            "stage3_gold_not_used_to_tune_stage1": True,
            "no_human_decision_inferred": True,
        },
        "zero_api": {"new_llm_api_calls": 0},
    }


def main() -> int:
    matrix = build_matrix()

    def _write(path: Path, data: bytes) -> None:
        if path.exists() and path.read_bytes() != data:
            raise RuntimeError(f"refusing to overwrite different content: {path}")
        path.write_bytes(data)

    _write(OUT_JSON, (json.dumps(matrix, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    md = [
        "# S1.1-S1.4 Task Matrix v1 (2026-08-11)",
        "",
        f"- scope: {matrix['scope']}",
        f"- determinism: double-run byte-identical="
        f"{matrix['determinism']['double_run_byte_identical']}, "
        f"matches locked process records="
        f"{matrix['determinism']['matches_locked_process_records']} "
        f"(manifest {matrix['determinism']['sha256'][:16]}...)",
        "",
    ]
    for sid, row in matrix["rows"].items():
        md.append(f"## {sid} ({row['status']})")
        md.append(f"- task: {row['task']}")
        md.append(f"- code: {', '.join(row['code'])}")
        md.append(f"- schema: {row['schema']}")
        md.append(f"- fixtures: {', '.join(row['fixtures'])}")
        md.append(f"- tests: {row['tests']}")
        md.append(f"- met DoD: {', '.join(row['met_doD'])}")
        if row["gaps"]:
            md.append(f"- gaps: {', '.join(row['gaps'])}")
        md.append("")
    md.append("## Boundaries")
    for k, v in matrix["boundaries"].items():
        md.append(f"- {k}: {v}")
    md.append("")
    _write(OUT_MD, ("\n".join(md)).encode("utf-8"))
    print(f"S1.1-S1.4 matrix written: {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
