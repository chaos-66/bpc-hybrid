"""Validate the S3-TABLE3-R5 benchmark artifacts.

Named checks only: data/source leakage, BPMN variant structure, reference
labels, split integrity, inference isolation, and budget/reuse arithmetic.
No model, API, or old full experiment is run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v1.json"
DATA = ROOT / "data/development/stage3_table3_r5_benchmark_v1"
REPORTS = ROOT / "outputs/reports"
NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
FORBIDDEN_INFERENCE_KEYS = {
    "variant", "mutation", "mutation_type", "reference_states", "reference",
    "target_node", "target_rule", "family_id", "requirement_id", "case_family",
    "answer", "gold", "label",
}
FORBIDDEN_INFERENCE_TEXT = {
    "missing_action", "incorrect_actor", "out_of_order", "baseline",
    "violated", "satisfied", "not_applicable",
}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_text(value: str) -> str:
    return sha_bytes(value.encode("utf-8"))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_ws(value: str) -> str:
    return " ".join(value.split())


def parse_core_model(raw: bytes) -> dict:
    root = ET.fromstring(raw)
    participant = root.find(f".//{{{NS}}}participant")
    tasks = {e.get("id"): e.get("name") for e in root.findall(f".//{{{NS}}}task")}
    edges = [(e.get("sourceRef"), e.get("targetRef")) for e in root.findall(f".//{{{NS}}}sequenceFlow")]
    succ: dict[str, list[str]] = {}
    for src, dst in edges:
        succ.setdefault(src, []).append(dst)
    sequence: list[str] = []
    current = "Start"
    seen = set()
    while current and current in (set(tasks) | {"Start", "End", "Gateway_Applicability"}):
        if current in seen:
            raise AssertionError("cycle in BPMN")
        seen.add(current)
        if current in tasks:
            sequence.append(current)
        choices = succ.get(current, [])
        if not choices:
            break
        if len(choices) != 1:
            raise AssertionError(f"unexpected branching at {current}: {choices}")
        current = choices[0]
    if "End" not in seen:
        raise AssertionError("End not reached")
    return {"actor": participant.get("name") if participant is not None else None, "tasks": tasks, "sequence": sequence}


def validate() -> tuple[bool, list[dict]]:
    checks: list[dict] = []

    def add(check_id: str, passed: bool, detail: str, evidence: dict | None = None):
        checks.append({"check_id": check_id, "passed": bool(passed), "detail": detail, "evidence": evidence or {}})

    config = load_json(CONFIG)
    manifest = load_json(DATA / "manifest.json")
    source_doc = load_json(DATA / "source_requirements.json")
    ref_doc = load_json(DATA / "reference/reference_cases.json")
    inference_doc = load_json(DATA / "inference/inference_view.json")
    semantic = load_json(DATA / "semantic_challenges.json")
    split = load_json(DATA / "split_manifest.json")
    specs = {r["requirement_id"]: r for r in config["requirements"]}
    source = {r["requirement_id"]: r for r in source_doc["requirements"]}
    cases = {c["case_id"]: c for c in ref_doc["cases"]}
    inference = {i["case_id"]: i for i in inference_doc["items"]}

    add("V-01-requirement-count", 30 <= len(source_doc["requirements"]) <= 40,
        f"independent requirements={len(source_doc['requirements'])}")
    add("V-02-baseline-core-count", manifest["baseline_controls"] == len(source_doc["requirements"]) and manifest["core_cases"] == 108,
        f"baselines={manifest['baseline_controls']}, core_cases={manifest['core_cases']}")
    add("V-03-variant-counts", all(manifest["variants_per_type"].get(v) == 24 for v in ("missing_action", "incorrect_actor", "out_of_order")),
        json.dumps(manifest["variants_per_type"], ensure_ascii=False))
    add("V-04-scenario-minimum", all(manifest["scenario_counts"].get(s, 0) >= 4 for s in ["S1", "S2", "S3", "S4", "S5", "S6"]),
        json.dumps(manifest["scenario_counts"], ensure_ascii=False))
    add("V-05-element-minimum", manifest["element_coverage"]["actor"] == 36 and manifest["element_coverage"]["action"] == 36 and
        manifest["element_coverage"]["condition"] >= 12 and manifest["element_coverage"]["constraint"] >= 20 and manifest["element_coverage"]["exception"] >= 8,
        json.dumps(manifest["element_coverage"], ensure_ascii=False))
    add("V-06-split-integrity", manifest["development_requirements"] == 12 and manifest["test_requirements"] == 24 and
        split["test_independent_candidate_count"] >= 20,
        f"dev={manifest['development_requirements']}, test={manifest['test_requirements']}, independent_test={split['test_independent_candidate_count']}")
    add("V-07-historical-five-dev", all(source[rid]["split"] == "development" for rid in ["R5-D-01", "R5-D-02", "R5-D-03", "R5-D-04", "R5-D-05"]),
        "R5-D-01..05 are forced development")
    add("V-08-source-hashes", all(r.get("text_sha256") == sha_text(r["excerpt_text"]) for r in source_doc["requirements"]),
        "all source excerpt SHA-256 values recompute")
    add("V-09-source-unique", len({r["text_sha256"] for r in source_doc["requirements"]}) == len(source_doc["requirements"]),
        "no duplicated source text SHA across independent requirements")
    add("V-10-source-provenance", all(r.get("source_url") and r.get("document_version") and r.get("citation") and r.get("excerpt_text") for r in source_doc["requirements"]),
        "all records carry URL, document version, citation, and continuous text")
    add("V-11-reference-case-set", set(cases) == set(inference), f"reference={len(cases)} inference={len(inference)}")
    add("V-12-single-violation", all(sum(1 for v in c["reference_states"].values() if v == "violated") == (0 if c["variant"] == "baseline" else 1) for c in cases.values()),
        "each non-baseline case has exactly one violated check")
    add("V-13-missing-action-na", all(c["reference_states"]["incorrect_actor"] == "not_applicable" and c["reference_states"]["out_of_order"] == "not_applicable" for c in cases.values() if c["variant"] == "missing_action"),
        "missing_action variants mark actor/order checks not_applicable")
    add("V-14-inference-isolation", all(not (FORBIDDEN_INFERENCE_KEYS & set(i)) for i in inference.values()),
        "inference rows expose no answer-bearing keys")
    rendered_inference = json.dumps(inference_doc, ensure_ascii=False).lower()
    add("V-15-inference-text-isolation", not any(term in rendered_inference for term in ("missing_action", "incorrect_actor", "out_of_order", "violated", "reference_states")),
        "inference JSON does not contain mutation/answer vocabulary")
    add("V-16-case-id-isolation", not any(any(term in item["case_id"].lower() for term in ("missing", "actor", "order", "violated")) for item in inference.values()),
        "case ids are opaque")
    add("V-17-semantic-separate", semantic.get("not_mixed_with_core_f1") is True and semantic["modality_fragment_counts"] == {"definition": 4, "permission": 4, "prohibition": 4},
        json.dumps(semantic["modality_fragment_counts"], ensure_ascii=False))
    add("V-18-semantic-pairs", sum(1 for p in semantic["pairs"] if p["pair_kind"] == "condition") == 6 and sum(1 for p in semantic["pairs"] if p["pair_kind"] == "exception") == 6,
        "6 condition + 6 exception pairs")

    # Per-BPMN structural mutation validation.
    bad = []
    for cid, case in cases.items():
        spec = specs[case["requirement_id"]]
        bpmn = DATA / "bpmn" / f"{cid}.bpmn"
        if not bpmn.exists():
            bad.append((cid, "missing bpmn"))
            continue
        try:
            observed = parse_core_model(bpmn.read_bytes())
        except Exception as exc:
            bad.append((cid, f"parse: {exc}"))
            continue
        mandatory = f"Activity_{spec['mandatory_index']}"
        before = f"Activity_{spec['order_pair'][0]}"
        after = f"Activity_{spec['order_pair'][1]}"
        present = mandatory in observed["tasks"]
        actor_wrong = observed["actor"] != spec["actor_required"]
        ordered = observed["sequence"].index(before) < observed["sequence"].index(after) if before in observed["sequence"] and after in observed["sequence"] else False
        expected = case["variant"]
        ok = False
        if expected == "baseline":
            ok = present and not actor_wrong and ordered
        elif expected == "missing_action":
            ok = (not present)
        elif expected == "incorrect_actor":
            ok = present and actor_wrong and ordered
        elif expected == "out_of_order":
            ok = present and not actor_wrong and not ordered
        if not ok:
            bad.append((cid, f"observed mutation does not match {expected}"))
    add("V-19-bpmn-structural-mutation", not bad, f"bad={len(bad)}", {"bad_examples": bad[:10]})

    # Stage1 parser validity on all core and challenge BPMN.
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file
        contract = load_stage1_contract(ROOT / "configs/stage1_structural_s11_s14.json")
        parse_bad = []
        for p in sorted((DATA / "bpmn").rglob("*.bpmn")):
            try:
                parse_bpmn_file(p, contract=contract)
            except Exception as exc:
                parse_bad.append((str(p.relative_to(ROOT)), repr(exc)))
        add("V-20-stage1-bpmn-valid", not parse_bad, f"bad={len(parse_bad)}", {"bad_examples": parse_bad[:10]})
    except Exception as exc:
        add("V-20-stage1-bpmn-valid", False, f"validator import/run failed: {exc!r}")

    # Source family split consistency.
    family_splits: dict[str, set[str]] = {}
    for c in cases.values():
        family_splits.setdefault(c["family_id"], set()).add(c["split"])
    add("V-21-family-split-integrity", all(len(v) == 1 for v in family_splits.values()), f"cross-split families={sum(1 for v in family_splits.values() if len(v) != 1)}")

    # Existing prediction / budget arithmetic if reports have been prepared.
    reuse_path = REPORTS / "stage3_table3_r5_prediction_reuse_v1.json"
    budget_path = REPORTS / "stage3_table3_r5_api_budget_v1.json"
    if reuse_path.exists() and budget_path.exists():
        reuse = load_json(reuse_path)
        budget = load_json(budget_path)
        add("V-22-reuse-arithmetic", reuse["reused_unique_inputs"] + reuse["new_ours_requests"] == len(source_doc["requirements"]),
            f"reused={reuse['reused_unique_inputs']}, new={reuse['new_ours_requests']}")
        add("V-23-budget-unit-not-bpmn-count", budget["calls_cap"] == reuse["new_ours_requests"] and budget["calls_cap"] != manifest["core_cases"],
            f"calls_cap={budget['calls_cap']}, core_cases={manifest['core_cases']}")
        add("V-24-budget-cap", budget["retry_cap"] == 0 and budget["total_output_tokens_cap"] == budget["calls_cap"] * budget["max_output_tokens_per_call"] and budget["cost_upper_bound_usd_with_20pct_margin"] > 0,
            f"cost_cap={budget['cost_upper_bound_usd_with_20pct_margin']}")
    else:
        add("V-22-reuse-arithmetic", False, "reuse/budget reports absent (run prepare script)")
        add("V-23-budget-unit-not-bpmn-count", False, "reuse/budget reports absent")
        add("V-24-budget-cap", False, "reuse/budget reports absent")

    passed = all(c["passed"] for c in checks)
    return passed, checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    passed, checks = validate()
    report = {
        "schema_version": "stage3_table3_r5_validation@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v1",
        "status": "pass" if passed else "fail",
        "check_count": len(checks),
        "passed_count": sum(1 for c in checks if c["passed"]),
        "failed": [c for c in checks if not c["passed"]],
        "checks": checks,
    }
    if args.write:
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "stage3_table3_r5_validation_v1.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
