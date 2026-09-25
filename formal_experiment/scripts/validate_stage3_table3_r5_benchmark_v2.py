"""Validate S3-TABLE3-R5.1 benchmark v2.

Reports structural checks and content-qualification checks separately.  The
content checks encode the corrections from this round; a generic unit test must
not be advertised as proof that the legal semantics are correct.

Named checks only; no model/API/old-experiment run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/development/stage3_table3_r5_benchmark_v2"
REPORTS = ROOT / "outputs/reports"
CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v2.json"
NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
FORBIDDEN_INFERENCE_KEYS = {
    "variant", "mutation", "mutation_type", "reference_states", "reference",
    "target_node", "target_rule", "family_id", "requirement_id", "case_family",
    "answer", "gold", "label", "source_family_id", "split",
}
STRICT_ORDER_KEYWORDS = ("prior to", "before", "after", "of receipt", "having become aware")
CHALLENGE_FORBIDDEN_TEXT = (
    "applicability", "condition/exception", "condition true", "condition false",
    "exception true", "exception false", "not true", "violated", "satisfied",
)
VARIANT_TYPES = ("missing_action", "incorrect_actor", "out_of_order")
ELIG = {"missing_action": "eligible_missing_action", "incorrect_actor": "eligible_incorrect_actor",
        "out_of_order": "eligible_out_of_order"}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_text(value: str) -> str:
    return sha_bytes(value.encode("utf-8"))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _bpmn_bytes(bundle: dict, rel_path: str) -> bytes:
    """Read a BPMN file; tests may inject a reader for minimal counterexamples."""
    reader = bundle.get("_bpmn_reader")
    if reader is not None:
        return reader(rel_path)
    return (DATA / rel_path).read_bytes()


def norm_tokens(value: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", " ".join(value.split()).lower()) if t]


# ---------------------------------------------------------------------------
# generic BPMN structure helper (used by both core and challenge checks)
# ---------------------------------------------------------------------------
def bpmn_structure(raw: bytes) -> dict:
    root = ET.fromstring(raw)
    tasks = {e.get("id"): e.get("name") for e in root.findall(f".//{{{NS}}}task")}
    nodes = {e.get("id") for e in root.iter() if e.get("id") and (
        e.tag.endswith("task") or e.tag.endswith("Event") or e.tag.endswith("Gateway"))}
    edges = [(e.get("sourceRef"), e.get("targetRef")) for e in root.findall(f".//{{{NS}}}sequenceFlow")]
    lane_refs = [e.text for e in root.findall(f".//{{{NS}}}flowNodeRef")]
    incoming = {n: 0 for n in nodes}
    outgoing = {n: 0 for n in nodes}
    unknown_edge = []
    for s, t in edges:
        if s in outgoing:
            outgoing[s] += 1
        else:
            unknown_edge.append(s)
        if t in incoming:
            incoming[t] += 1
        else:
            unknown_edge.append(t)
    # reachability from a start event
    start = next((e.get("id") for e in root.findall(f".//{{{NS}}}startEvent")), None)
    succ: dict[str, list[str]] = {}
    for s, t in edges:
        succ.setdefault(s, []).append(t)
    seen = set()
    stack = [start] if start else []
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(succ.get(n, []))
    dangling = sorted((nodes - seen) | set(unknown_edge))
    return {"tasks": tasks, "nodes": nodes, "edges": edges, "lane_refs": lane_refs,
            "dangling": dangling, "unknown_edge": unknown_edge,
            "lane_unreferenced": sorted(n for n in nodes if n not in lane_refs)}


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------
def check_family_split(bundle: dict) -> dict:
    sources = bundle["source"]["requirements"]
    fam = {}
    for s in sources:
        fam.setdefault(s["source_family_id"], set()).add(s["split"])
    cross = sorted(f for f, v in fam.items() if len(v) != 1)
    return {"check_id": "V2-S-01-source-family-split", "group": "structure",
            "passed": not cross, "detail": f"cross_split_families={cross}", "evidence": {"cross": cross}}


def check_dev_positive_examples(bundle: dict) -> dict:
    cases = bundle["reference"]["cases"]
    specs = bundle["specs"]
    dev_pos = {v: 0 for v in VARIANT_TYPES}
    for c in cases:
        if c["split"] != "development":
            continue
        for v in VARIANT_TYPES:
            if c["reference_states"].get(v) == "violated" and specs[c["requirement_id"]][ELIG[v]]:
                dev_pos[v] += 1
    dev_baselines = sum(1 for c in cases if c["split"] == "development" and c["variant"] == "baseline")
    passed = all(dev_pos[v] > 0 for v in VARIANT_TYPES) and dev_baselines > 0
    return {"check_id": "V2-S-02-development-positive-examples", "group": "structure", "passed": passed,
            "detail": f"dev_violation_positives={dev_pos}, dev_baselines={dev_baselines}",
            "evidence": {"dev_positive": dev_pos, "dev_baselines": dev_baselines}}


def check_order_eligibility(bundle: dict) -> dict:
    specs = {r["requirement_id"]: r for r in bundle["config"]["requirements"]}
    bad = []
    for rid, s in specs.items():
        ev = " ".join(str(s.get("order_evidence", "")).lower().split())
        has_kw = any(k in ev for k in STRICT_ORDER_KEYWORDS)
        if s[ELIG["out_of_order"]] and not has_kw:
            bad.append((rid, "eligible_without_strict_order_evidence", s.get("order_evidence")))
    return {"check_id": "V2-Q-01-order-eligibility", "group": "content", "passed": not bad,
            "detail": f"order-eligible-without-basis={bad}", "evidence": {"bad": bad}}


def check_permission_prohibition_not_scored(bundle: dict) -> dict:
    specs = {r["requirement_id"]: r for r in bundle["config"]["requirements"]}
    cases = bundle["reference"]["cases"]
    bad = []
    for rid, s in specs.items():
        if s.get("modality") in ("permission", "prohibition"):
            if any(s[ELIG[v]] for v in VARIANT_TYPES):
                bad.append((rid, "permission_prohibition_has_core_eligibility"))
    # also: scored variant cells must not exist for ineligible types
    scored_types = {}
    for c in cases:
        scored_types.setdefault(c["requirement_id"], set()).update(
            v for v in VARIANT_TYPES if c["reference_states"].get(v) == "violated")
    for rid, types in scored_types.items():
        for v in types:
            if not specs[rid][ELIG[v]]:
                bad.append((rid, f"scored_ineligible_type:{v}"))
    return {"check_id": "V2-Q-02-permission-prohibition-core", "group": "content", "passed": not bad,
            "detail": f"violations={bad}", "evidence": {"bad": bad}}


def check_element_evidence(bundle: dict) -> dict:
    bad = []
    for s in bundle["source"]["requirements"]:
        for name, payload in s["elements"].items():
            if not payload["present"]:
                continue
            e = payload["evidence"]
            scope = e.get("scope")
            if scope == "not_provided":
                bad.append((s["requirement_id"], name, "present_but_not_provided"))
            elif scope == "source_excerpt":
                ev_tokens = set(norm_tokens(e.get("text") or ""))
                src_tokens = set(norm_tokens(s["excerpt_text"]))
                if not ev_tokens or not ev_tokens.issubset(src_tokens):
                    bad.append((s["requirement_id"], name, "source_excerpt_evidence_not_in_excerpt"))
            elif scope == "cross_reference_provided":
                if not e.get("cross_reference") or not e["cross_reference"].get("provided_to_task"):
                    bad.append((s["requirement_id"], name, "cross_reference_not_provided"))
            elif scope == "declared_external_context":
                if not e.get("declared_source"):
                    bad.append((s["requirement_id"], name, "declared_external_without_source"))
            else:
                bad.append((s["requirement_id"], name, f"unknown_scope:{scope}"))
    return {"check_id": "V2-Q-03-element-evidence-binding", "group": "content", "passed": not bad,
            "detail": f"bad={bad[:20]}", "evidence": {"bad": bad}}


def check_condition_flags(bundle: dict) -> dict:
    """Any excerpt with a Where/If/When applicability clause must flag condition."""
    bad = []
    for s in bundle["source"]["requirements"]:
        text = s["excerpt_text"]
        has_clause = bool(re.search(r"(?i)(^|\s)(where|if|when)\s+[a-z]", text))
        if has_clause and not s["elements"]["condition"]["present"]:
            bad.append((s["requirement_id"], "condition_clause_but_not_flagged"))
    return {"check_id": "V2-Q-04-condition-flags", "group": "content", "passed": not bad,
            "detail": f"bad={bad}", "evidence": {"bad": bad}}


def check_exception_polarity(bundle: dict) -> dict:
    bad = []
    for pair in bundle["semantic"]["pairs"]:
        kind = pair["pair_kind"]
        for c in pair["cases"]:
            facts = c["applicability_facts"]
            outcome = c["reference"]["outcome"]
            duty = c["reference"]["duty_in_force"]
            if kind == "condition":
                if "exception_applies" in facts:
                    bad.append((pair["pair_id"], "condition_pair_uses_exception_fact"))
                if facts.get("condition_holds") is True and outcome != "violation":
                    bad.append((pair["pair_id"], "condition_true_not_violation"))
                if facts.get("condition_holds") is False and outcome != "not_applicable":
                    bad.append((pair["pair_id"], "condition_false_not_na"))
            else:
                if facts.get("exception_applies") is True and outcome != "exempted":
                    bad.append((pair["pair_id"], "exception_true_not_exempted"))
                if facts.get("exception_applies") is False and outcome != "violation":
                    bad.append((pair["pair_id"], "exception_false_not_violation"))
                if facts.get("exception_applies") is True and duty is not False:
                    bad.append((pair["pair_id"], "exception_true_but_duty_in_force"))
    return {"check_id": "V2-Q-05-exception-polarity", "group": "content", "passed": not bad,
            "detail": f"bad={bad}", "evidence": {"bad": bad}}


def check_challenge_bpmn(bundle: dict) -> dict:
    bad = []
    pair_behavior = []
    for pair in bundle["semantic"]["pairs"]:
        raws = []
        for c in pair["cases"]:
            raw = _bpmn_bytes(bundle, c["bpmn_path"])
            raws.append(raw)
            text = raw.decode("utf-8").lower()
            for term in CHALLENGE_FORBIDDEN_TEXT:
                if term in text:
                    bad.append((c["case_id"], f"answer_hint_text:{term}"))
            st = bpmn_structure(raw)
            if st["dangling"]:
                bad.append((c["case_id"], f"dangling_nodes:{st['dangling']}"))
            if st["lane_unreferenced"]:
                bad.append((c["case_id"], f"lane_missing_nodes:{st['lane_unreferenced']}"))
        if len(raws) == 2 and raws[0] != raws[1]:
            pair_behavior.append((pair["pair_id"], "cases_do_not_share_identical_behaviour"))
    bad.extend(pair_behavior)
    return {"check_id": "V2-S-03-challenge-bpmn", "group": "structure", "passed": not bad,
            "detail": f"bad={bad[:20]}", "evidence": {"bad": bad}}


def check_inference_isolation(bundle: dict) -> dict:
    inf = bundle["inference"]
    text = json.dumps(inf, ensure_ascii=False).lower()
    forbidden_terms = ("missing_action", "incorrect_actor", "out_of_order", "violated", "reference_states", "family_id")
    bad = []
    for item in inf["items"]:
        if FORBIDDEN_INFERENCE_KEYS & set(item):
            bad.append((item.get("case_id"), "forbidden_key"))
    term_hits = [t for t in forbidden_terms if t in text]
    if term_hits:
        bad.append(("inference_view", f"forbidden_terms:{term_hits}"))
    # associated context / source texts must not carry answers either
    ctx = json.dumps(bundle["source_texts"], ensure_ascii=False).lower()
    ctx_hits = [t for t in forbidden_terms if t in ctx]
    if ctx_hits:
        bad.append(("source_texts", f"forbidden_terms:{ctx_hits}"))
    common = json.dumps(bundle["common_context"], ensure_ascii=False).lower()
    common_hits = [t for t in forbidden_terms if t in common]
    if common_hits:
        bad.append(("common_context", f"forbidden_terms:{common_hits}"))
    # BPMN associated with inference must not contain mutation labels
    for item in inf["items"]:
        raw = _bpmn_bytes(bundle, item["bpmn_path"]).lower().decode("utf-8", "ignore")
        hits = [t for t in ("missing_action", "incorrect_actor", "out_of_order", "violated", "reference_states") if t in raw]
        if hits:
            bad.append((item["case_id"], f"bpmn_leak:{hits}"))
    return {"check_id": "V2-S-04-inference-reference-isolation", "group": "structure", "passed": not bad,
            "detail": f"bad={bad[:20]}", "evidence": {"bad": bad}}


def check_core_structure(bundle: dict) -> dict:
    cases = bundle["reference"]["cases"]
    inf = {i["case_id"] for i in bundle["inference"]["items"]}
    bad = []
    for c in cases:
        if c["case_id"] not in inf:
            bad.append((c["case_id"], "missing_inference_item"))
        violated = [v for v in VARIANT_TYPES if c["reference_states"].get(v) == "violated"]
        if c["variant"] == "baseline":
            if violated:
                bad.append((c["case_id"], f"baseline_violation:{violated}"))
        else:
            if violated != [c["variant"]]:
                bad.append((c["case_id"], f"single_factor_violation_bad:{violated}"))
        for v in VARIANT_TYPES:
            if c["reference_states"].get(v) == "not_scored" and bundle["specs"][c["requirement_id"]][ELIG[v]]:
                bad.append((c["case_id"], f"eligible_type_marked_not_scored:{v}"))
    return {"check_id": "V2-S-05-core-reference-structure", "group": "structure", "passed": not bad,
            "detail": f"bad={bad[:20]}", "evidence": {"bad": bad}}


def check_source_integrity(bundle: dict) -> dict:
    bad = []
    hashes = [s["text_sha256"] for s in bundle["source"]["requirements"]]
    if len(hashes) != len(set(hashes)):
        bad.append(("duplicate_source_text_sha", [h for h in hashes if hashes.count(h) > 1]))
    for s in bundle["source"]["requirements"]:
        if s["text_sha256"] != sha_text(s["excerpt_text"]):
            bad.append((s["requirement_id"], "excerpt_sha_mismatch"))
        if s.get("context_text") and s.get("context_sha256") != sha_text(s["context_text"]):
            bad.append((s["requirement_id"], "context_sha_mismatch"))
    return {"check_id": "V2-S-06-source-integrity", "group": "structure", "passed": not bad,
            "detail": f"bad={bad}", "evidence": {"bad": bad}}


def check_budget_and_reuse(bundle: dict) -> dict:
    bad = []
    budget = bundle.get("budget")
    reuse = bundle.get("reuse")
    if not budget or not reuse:
        return {"check_id": "V2-S-07-budget-and-reuse", "group": "structure", "passed": False,
                "detail": "budget or reuse report absent", "evidence": {}}
    if budget["calls_cap_core_request_list"] != len(budget["request_rows"]):
        bad.append(("calls_cap_not_equal_request_rows", budget["calls_cap_core_request_list"]))
    if budget["calls_cap_core_request_list"] != budget["new_requests"]:
        bad.append(("calls_cap_not_equal_new_requests", budget["new_requests"]))
    # budget count must come from the actual request list, not a target quota
    if budget["calls_cap_core_request_list"] in (24, 36, 108):
        bad.append(("calls_cap_looks_like_target_quota", budget["calls_cap_core_request_list"]))
    for row in reuse["rows"]:
        if row["ours"]["status"] == "verified":
            failed = [k for k, c in (row["ours"].get("checks") or {}).items() if not c.get("passed")]
            if failed:
                bad.append((row["requirement_id"], f"verified_with_failed_checks:{failed}"))
    return {"check_id": "V2-S-07-budget-and-reuse", "group": "structure", "passed": not bad,
            "detail": f"bad={bad[:20]}", "evidence": {"bad": bad}}


def check_no_mutation_label_reference(bundle: dict) -> dict:
    """Reference states must be recomputable from the observed BPMN, not labels."""
    bad = []
    for c in bundle["reference"]["cases"]:
        raw = _bpmn_bytes(bundle, f"bpmn/{c['case_id']}.bpmn")
        st = bpmn_structure(raw)
        spec = bundle["specs"][c["requirement_id"]]
        mandatory = f"Activity_{spec['mandatory_index']}"
        present = mandatory in st["tasks"]
        expected_present = c["variant"] != "missing_action"
        if c["variant"] == "baseline":
            expected_present = True
        if present != expected_present:
            bad.append((c["case_id"], "reference_state_not_recomputable_from_bpmn"))
    return {"check_id": "V2-Q-06-reference-not-label-derived", "group": "content", "passed": not bad,
            "detail": f"bad={bad[:20]}", "evidence": {"bad": bad}}


# ---------------------------------------------------------------------------
# bundle + validate
# ---------------------------------------------------------------------------
def load_bundle(data_dir: Path = DATA, reports_dir: Path = REPORTS) -> dict:
    config = load_json(CONFIG)
    bundle = {
        "config": config,
        "specs": {r["requirement_id"]: r for r in config["requirements"]},
        "source": load_json(data_dir / "source_requirements.json"),
        "reference": load_json(data_dir / "reference/reference_cases.json"),
        "semantic": load_json(data_dir / "semantic_challenges.json"),
        "inference": load_json(data_dir / "inference/inference_view.json"),
        "source_texts": load_json(data_dir / "inference/source_texts.json"),
        "common_context": load_json(data_dir / "inference/common_context.json"),
        "manifest": load_json(data_dir / "manifest.json"),
        "candidates": load_json(data_dir / "reference/candidate_assets.json"),
    }
    for name, fname in (("reuse", "stage3_table3_r5_prediction_reuse_v2.json"),
                        ("budget", "stage3_table3_r5_api_budget_v2.json")):
        p = reports_dir / fname
        bundle[name] = load_json(p) if p.exists() else None
    return bundle


STRUCTURAL_CHECKS = [check_family_split, check_dev_positive_examples, check_challenge_bpmn,
                     check_inference_isolation, check_core_structure, check_source_integrity,
                     check_budget_and_reuse]
CONTENT_CHECKS = [check_order_eligibility, check_permission_prohibition_not_scored,
                  check_element_evidence, check_condition_flags, check_exception_polarity,
                  check_no_mutation_label_reference]


def validate(bundle: dict | None = None) -> tuple[bool, dict]:
    bundle = bundle or load_bundle()
    structural = [f(bundle) for f in STRUCTURAL_CHECKS]
    content = [f(bundle) for f in CONTENT_CHECKS]
    passed = all(c["passed"] for c in structural) and all(c["passed"] for c in content)
    report = {
        "schema_version": "stage3_table3_r5_validation@2.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "status": "pass" if passed else "fail",
        "structural_checks": structural,
        "content_qualification_checks": content,
        "structural_passed": all(c["passed"] for c in structural),
        "content_qualification_passed": all(c["passed"] for c in content),
        "claim_boundary": (
            "These are construction/structure checks plus scoped content-qualification checks. "
            "Passing them does NOT prove legal semantic correctness, formal Gold status, or Table 3 performance."
        ),
    }
    return passed, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    passed, report = validate()
    if args.write:
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "stage3_table3_r5_validation_v2.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": report["status"], "structural": report["structural_passed"],
                      "content": report["content_qualification_passed"],
                      "failed": [c["check_id"] for c in report["structural_checks"] + report["content_qualification_checks"] if not c["passed"]]},
                     ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())


