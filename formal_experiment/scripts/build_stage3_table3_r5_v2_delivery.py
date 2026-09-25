"""Write the S3-TABLE3-R5.1 v1->v2 mapping and the human-readable v2 report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
V1_CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v1.json"
V2_CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v2.json"
V1_DATA = ROOT / "data/development/stage3_table3_r5_benchmark_v1"
V2_DATA = ROOT / "data/development/stage3_table3_r5_benchmark_v2"
REPORTS = ROOT / "outputs/reports"
sys.path.insert(0, str(ROOT / "scripts"))
import r5_reuse_verification as rv  # noqa: E402

VARIANT_TYPES = ("missing_action", "incorrect_actor", "out_of_order")
ELIG = {"missing_action": "eligible_missing_action", "incorrect_actor": "eligible_incorrect_actor",
        "out_of_order": "eligible_out_of_order"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def build_mapping() -> dict:
    v1_config = load(V1_CONFIG)
    v2_config = load(V2_CONFIG)
    v1_specs = {s["requirement_id"]: s for s in v1_config["requirements"]}
    v2_specs = {s["requirement_id"]: s for s in v2_config["requirements"]}
    v1_manifest = load(V1_DATA / "manifest.json")
    v2_manifest = load(V2_DATA / "manifest.json")
    rows = []
    for rid in sorted(v1_specs):
        a, b = v1_specs[rid], v2_specs[rid]
        changes = []
        if a.get("split") != b.get("split"):
            changes.append(f"split {a.get('split')} -> {b.get('split')}")
        if a.get("has_variants") != any(b[ELIG[v]] for v in VARIANT_TYPES):
            changes.append(f"has_variants(all-or-nothing) -> per-type {[v for v in VARIANT_TYPES if b[ELIG[v]]]}")
        if a.get("condition_present") != b.get("condition_present"):
            changes.append(f"condition_present {a.get('condition_present')} -> {b.get('condition_present')}")
        if a.get("exception_present") != b.get("exception_present"):
            changes.append(f"exception_present {a.get('exception_present')} -> {b.get('exception_present')}")
        if a.get("excerpt_mode") != b.get("excerpt_mode"):
            changes.append(f"excerpt_mode {a.get('excerpt_mode')} -> {b.get('excerpt_mode')}")
        rows.append({
            "requirement_id": rid,
            "citation": b["citation"],
            "v1_split": a.get("split"),
            "v2_split": b.get("split"),
            "v1_has_variants": a.get("has_variants"),
            "v2_eligibility": {v: bool(b[ELIG[v]]) for v in VARIANT_TYPES},
            "v2_disposition": b["disposition"],
            "source_family_id": b["source_family_id"],
            "changes": changes or ["retained (excerpt/identity unchanged)"],
            "review_issues": b["review_issues"],
            "review_fixes": b["review_fixes"],
        })
    return {
        "schema_version": "stage3_table3_r5_v1_to_v2_mapping@2.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "preserves_v1": True,
        "v1_summary": {
            "independent_requirements": v1_manifest["independent_requirements"],
            "core_cases": v1_manifest["core_cases"],
            "baseline_controls": v1_manifest["baseline_controls"],
            "variants_per_type": v1_manifest["variants_per_type"],
            "development_requirements": v1_manifest["development_requirements"],
            "test_requirements": v1_manifest["test_requirements"],
        },
        "v2_summary": {
            "independent_requirements": v2_manifest["independent_requirements"],
            "core_cases": v2_manifest["core_cases"],
            "baseline_controls": v2_manifest["baseline_controls"],
            "variants_per_type": v2_manifest["variants_per_type"],
            "development_requirements": v2_manifest["development_requirements"],
            "test_requirements": v2_manifest["test_requirements"],
            "core_requirements": v2_manifest["core_requirements"],
            "candidate_requirements": v2_manifest["candidate_requirements"],
            "source_family_count": v2_manifest["source_family_count"],
        },
        "artifacts": {
            "config": {"v1": "configs/stage3_table3_r5_benchmark_v1.json", "v2": "configs/stage3_table3_r5_benchmark_v2.json"},
            "data_dir": {"v1": "data/development/stage3_table3_r5_benchmark_v1", "v2": "data/development/stage3_table3_r5_benchmark_v2"},
            "reports": {"v1": "outputs/reports/stage3_table3_r5_*_v1.json", "v2": "outputs/reports/stage3_table3_r5_*_v2.json"},
        },
        "rows": rows,
    }


def build_report() -> str:
    v1_manifest = load(V1_DATA / "manifest.json")
    m = load(V2_DATA / "manifest.json")
    source = load(V2_DATA / "source_requirements.json")
    cases = load(V2_DATA / "reference/reference_cases.json")["cases"]
    candidates = load(V2_DATA / "reference/candidate_assets.json")
    reuse = load(REPORTS / "stage3_table3_r5_prediction_reuse_v2.json")
    budget = load(REPORTS / "stage3_table3_r5_api_budget_v2.json")
    readiness = load(REPORTS / "stage3_table3_r5_readiness_v2.json")
    validation = load(REPORTS / "stage3_table3_r5_validation_v2.json") if (REPORTS / "stage3_table3_r5_validation_v2.json").exists() else None

    specs = {s["requirement_id"]: s for s in load(V2_CONFIG)["requirements"]}
    pos_neg = {v: {"positive_violated": 0, "negative_satisfied": 0, "not_applicable": 0, "not_scored": 0} for v in VARIANT_TYPES}
    for c in cases:
        for v in VARIANT_TYPES:
            st = c["reference_states"].get(v)
            if st == "violated":
                pos_neg[v]["positive_violated"] += 1
            elif st == "satisfied":
                pos_neg[v]["negative_satisfied"] += 1
            elif st == "not_applicable":
                pos_neg[v]["not_applicable"] += 1
            else:
                pos_neg[v]["not_scored"] += 1

    core_reqs = [s for s in source["requirements"] if s["core_eligible"]]
    candidate_reqs = [s for s in source["requirements"] if not s["core_eligible"]]
    used_elements = {}
    for name in ("modality", "actor", "action", "condition", "constraint", "exception"):
        used_elements[name] = {
            "present_records": m["element_coverage"].get(name, 0),
            "in_input_or_provided": sum(1 for s in source["requirements"]
                                        if s["elements"][name]["present"] and s["elements"][name]["evidence"].get("counts_as_in_input")),
            "declared_external_context": sum(1 for s in source["requirements"]
                                             if s["elements"][name]["present"] and s["elements"][name]["evidence"]["scope"] == "declared_external_context"),
        }

    lines = []
    A = lines.append
    A("# S3-TABLE3-R5.1 Benchmark v2 — Targeted Correction Report")
    A("")
    A("- status: **DATA_READY_FOR_FROZEN_SCOPE / METHODS_NOT_READY / API_AUTHORIZATION_PENDING / FORMAL_RELEASE_NOT_APPROVED**")
    A("- not formal Gold; no Table 3 score is claimed; real LLM/API calls = 0; `.env` not read.")
    A("")
    A("## 1. Assets retained directly")
    A("")
    A(f"- R5 v1 config/data/reports are preserved untouched (`{V1_DATA.as_posix()}`).")
    A(f"- {m['independent_requirements']} source requirements, the 5 R1-R4 historical rules, and all {v1_manifest['core_cases']} v1 BPMN are retained as provenance.")
    A("- Sun/Ours/Winter detection formulas, similarity backend and thresholds were not changed.")
    A("- Old predictions, raw answers, old Gold and R1-R4 results were not modified.")
    A("")
    A("## 2. Requirements/cases modified, migrated or exited core scoring")
    A("")
    A(f"- Core requirements: {m['core_requirements']}; candidate (out of core) requirements: {m['candidate_requirements']}.")
    A("- per-type eligibility replaced all-or-nothing `has_variants`.")
    A("- A1 R5-S1-T1/T2: the 'at the time when' simultaneity relation was removed from out_of_order scoring.")
    A("- A2 R5-S6-T1: risk-appropriateness is no longer treated as a strict two-activity order.")
    A("- A3 R5-S6-T4: 'without undue delay' no longer proves the invented 'assess high risk -> notify' order.")
    A("- A4 R5-S2-T3/T4 (and the same rule for R5-S2-T1): permission requirements left the frozen three-class scoring; no permission formula was added.")
    A("- A5 R5-S3-T3/T4: the invented Stop/Cease tasks were removed; prohibition/cessation cases left core scoring.")
    A("- A6 R5-S4-T3: the excerpt was narrowed to the 28(3)(a) sentence with an explicit char span; the local snapshot is flagged as processed, not official verbatim.")
    A("")
    A("| requirement | v1 split | v2 split | v2 eligibility (MA/IA/OO) | disposition | main issue |")
    A("|---|---|---|---|---|---|")
    for s in sorted(source["requirements"], key=lambda x: x["requirement_id"]):
        spec = specs[s["requirement_id"]]
        el = "/".join("Y" if spec[ELIG[v]] else "N" for v in VARIANT_TYPES)
        issue = "; ".join(spec["review_issues"]) or "none"
        A(f"| {s['requirement_id']} | {spec.get('split')} | {s['split']} | {el} | {spec['disposition']} | {issue} |")
    A("")
    A("## 3. Corrected real scale, positives/negatives and independent source families")
    A("")
    A(f"- unique inputs (requirements): {m['independent_requirements']} (core {m['core_requirements']} + candidate {m['candidate_requirements']})")
    A(f"- source families: {m['source_family_count']} (development {m['source_family_count_by_split']['development']}, test {m['source_family_count_by_split']['test']}); cross-split families: {m['cross_split_families']}")
    A(f"- core cases: {m['core_cases']} = {m['baseline_controls']} baselines + {m['variants_per_type']['missing_action']} missing_action + {m['variants_per_type']['incorrect_actor']} incorrect_actor + {m['variants_per_type']['out_of_order']} out_of_order")
    A(f"- development / test requirements: {m['development_requirements']} / {m['test_requirements']} (core test {m['core_test_requirements']}, candidate test {m['candidate_test_requirements']})")
    core_indep_fams = sorted({s["source_family_id"] for s in source["requirements"]
                              if s["split"] == "test" and s["core_eligible"] and s["exposure_status"] == "no_prior_exposure_found"})
    cand_test_fams = sorted({s["source_family_id"] for s in candidate_reqs if s["split"] == "test"})
    A(f"- independent core test source families: {core_indep_fams}")
    A(f"- candidate (non-core) test source families: {cand_test_fams}")
    A("- per-type positive/negative cells:")
    for v in VARIANT_TYPES:
        A(f"  - {v}: positive(violated)={pos_neg[v]['positive_violated']}, negative(satisfied)={pos_neg[v]['negative_satisfied']}, not_applicable={pos_neg[v]['not_applicable']}, not_scored={pos_neg[v]['not_scored']}")
    A("- no forced 12/24 or 108; the test split shrank because exposed families were moved to development.")
    A("")
    A("## 4. Six elements: present vs actually in the task input")
    A("")
    A("| element | present records | in input / provided | declared external context only |")
    A("|---|---|---|---|")
    for name, d in used_elements.items():
        A(f"| {name} | {d['present_records']} | {d['in_input_or_provided']} | {d['declared_external_context']} |")
    A("")
    A("- modality/actor/action are implemented and used by the frozen scorer.")
    A("- condition and exception truth remain **unsupported** by the frozen three-class scorer (recorded in the challenge layer).")
    A("- constraint is `indirect_only` (explicit source order pairs only).")
    A("- an exception whose cross-reference text was not provided is explicitly marked `counts_as_in_input=false` and is not counted as an in-input exception.")
    A("")
    A("## 5. Old predictions strictly verified as reusable")
    A("")
    A(f"- Ours verified reusable: {reuse['summary']['ours_verified_reusable']} / {reuse['summary']['unique_regulation_inputs']}")
    A(f"- Sun verified reusable: {reuse['summary']['sun_verified_reusable']}")
    A("- verified rows have a per-record evidence chain (record + manifest + frozen input, source SHA, prompt/model binding, schema/output binding).")
    A("- 5 D1 rows use an explicit per-record input_binding and an explicit output SHA-256.")
    A("- 9 GDPR7 rows have no inline input_binding; they are verified via manifest -> input file -> record, prompt SHA and capsule path/schema. Their output binding has no explicit SHA-256 and is marked weaker.")
    A("- rows whose input or context changed are NOT marked exact-input reuse.")
    A("")
    A("## 6. New requests and budget change")
    A("")
    A(f"- v1 budget: 22 calls, USD 1.18 cap (NOT inherited).")
    A(f"- v2 corrected core request list: {budget['new_requests']} new Ours Direct-LLM calls (one per unique regulation input; no per-BPMN calls), {budget['reused_existing_stage2_inputs']} reused.")
    A(f"- total input token cap: {budget['total_input_tokens_cap']}; output cap: {budget['total_output_tokens_cap']} (4096/call); retries: {budget['retry_cap']}.")
    A(f"- cost cap with 20% margin: USD {budget['cost_upper_bound_usd_with_20pct_margin']} (cap, not a predicted bill).")
    A("- the 5 non-core candidate requirements are NOT in the current request list; they would add 5 calls if a future permission/prohibition authorization exists.")
    A("- request material: each call is an independent `messages` request with no conversation history; the frozen extraction instruction belongs to that request only (no cross-request memory); no reference answer, variant class, target node or other case result is passed; prompt, full input, parameters and model identity are bindable.")
    A("")
    A("## 7. Remaining gaps before a Table 3 run")
    A("")
    A("- API authorization for the corrected request list is absent.")
    A("- METHODS_NOT_READY (not fixed this round): R4 actor-surface equivalence, action mis-matching, same-action-different-object, actor/business-object candidate scope, coordinate postprocessing.")
    A("- condition/exception/prohibition/permission truth is still unsupported; condition/exception challenges are assets, not detector capability.")
    A("- core test coverage is 9 requirements over 7 independent families, and only 2 test requirements are out_of_order eligible.")
    A("- no new Stage2/Stage3 main matrix, no parameter search and no full test suite were run this round.")
    if validation:
        A(f"- validator: structural={validation['structural_passed']}, content_qualification={validation['content_qualification_passed']} ({len(validation['structural_checks'])} structural + {len(validation['content_qualification_checks'])} content checks).")
    A("")
    A("## 8. v1 -> v2 artifact mapping")
    A("")
    A("| item | v1 | v2 | change |")
    A("|---|---|---|---|")
    A("| config | configs/stage3_table3_r5_benchmark_v1.json | configs/stage3_table3_r5_benchmark_v2.json | per-type eligibility + source_family_id + corrected conditions/excerpt |")
    A(f"| core cases | {v1_manifest['core_cases']} | {m['core_cases']} | eligible-only variants |")
    A(f"| baseline controls | {v1_manifest['baseline_controls']} | {m['baseline_controls']} | core-only baselines |")
    A(f"| variants/type | {v1_manifest['variants_per_type']} | {m['variants_per_type']} | no forced 24 |")
    A(f"| dev/test requirements | {v1_manifest['development_requirements']}/{v1_manifest['test_requirements']} | {m['development_requirements']}/{m['test_requirements']} | exposure-aware |")
    A("| semantic challenges | 6 condition + 6 exception pairs, answer-hinting BPMN | same count, condition/exception separated, neutral valid BPMN | rewritten |")
    A("| prediction reuse | v1 default-match | per-record evidence-chain verification | corrected |")
    A("| API budget | 22 / USD 1.18 | {0} / USD {1} | recomputed from actual request list |".format(budget["new_requests"], budget["cost_upper_bound_usd_with_20pct_margin"]))
    A("")
    A("## 9. Status")
    A("")
    A(f"- data: {readiness['statuses']['data']}")
    A(f"- methods: {readiness['statuses']['methods']}")
    A(f"- api: {readiness['statuses']['api']}")
    A(f"- formal_release: {readiness['statuses']['formal_release']}")
    A("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    mapping = build_mapping()
    report = build_report()
    if args.write:
        write_json(REPORTS / "stage3_table3_r5_v1_to_v2_mapping_v2.json", mapping)
        (REPORTS / "stage3_table3_r5_benchmark_v2.md").write_text(report, encoding="utf-8", newline="\n")
        request_materials = {
            "schema_version": "stage3_table3_r5_request_materials@2.0.0",
            "benchmark_id": "stage3_table3_r5_benchmark_v2",
            "status": "prepared_not_authorized",
            "api_unit": "one unique regulation input",
            "per_request": {
                "messages_is_independent": True,
                "no_conversation_history": True,
                "frozen_extraction_instruction_is_request_local": True,
                "no_cross_request_memory": True,
                "no_reference_answer": True,
                "no_variant_category": True,
                "no_target_node": True,
                "no_other_case_results": True,
            },
            "bindable_provenance": ["prompt_sha256", "full_input_sha256", "parameters", "model_alias"],
            "prompt_sha256_from_file": rv.sha_bytes((ROOT / rv.R5_PROMPT_REL).read_bytes()),
            "real_api_calls_made": 0,
        }
        write_json(REPORTS / "stage3_table3_r5_request_materials_v2.json", request_materials)
    print(json.dumps({"mapping_rows": len(mapping["rows"]), "v2_core_cases": mapping["v2_summary"]["core_cases"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

