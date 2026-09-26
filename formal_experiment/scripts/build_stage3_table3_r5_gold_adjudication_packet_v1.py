"""Build the prediction-blind S3-TABLE3-R5 formal Gold adjudication packet.

The packet is constructed only from committed source requirements, the frozen
BPMN/reference construction, the split manifest, and the source-only order
eligibility report.  It never reads Ours/Sun/Winter predictions, method scores,
or downstream evaluation outputs.  It does not release Gold.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/development/stage3_table3_r5_benchmark_v2"
CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v2.json"
ORDER_REPORT = ROOT / "outputs/reports/stage3_table3_r5_order_eligibility_v2.json"
OUT_JSON = ROOT / "outputs/reports/stage3_table3_r5_gold_adjudication_packet_v1.json"
OUT_MD = ROOT / "outputs/reports/stage3_table3_r5_gold_adjudication_packet_v1.md"

# Official EUR-Lex provenance verified on 2026-09-26 against the English OJ
# HTML at the CELEX 32016R0679 landing/text URL.  The SHA-256 values below are
# the exact official sentences after HTML tag/entity normalisation.  The packet
# builder asserts that the local processed Winter snapshot excerpt is byte-exact
# for these two rows before writing them as official-source verified.
OFFICIAL_PROVENANCE = {
    "R5-S7-T1": {
        "citation": "GDPR Article 40(7)",
        "official_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32016R0679",
        "verified_date": "2026-09-26",
        "official_sentence_sha256": "91d1a82e534e9695c90d73d905e741f0e191d9251cb4532f7ab7cd66a5f8f0c6",
        "clause_text": (
            "Where a draft code of conduct relates to processing activities in several Member States, "
            "the supervisory authority which is competent pursuant to Article 55 shall, before approving "
            "the draft code, amendment or extension, submit it in the procedure referred to in Article 63 "
            "to the Board which shall provide an opinion on whether the draft code, amendment or extension "
            "complies with this Regulation or, in the situation referred to in paragraph 3 of this Article, "
            "provides appropriate safeguards."
        ),
        "action_precedence": "The supervisory authority shall submit the draft code/amendment/extension to the Board before approving it.",
        "local_snapshot_status": "local_processed_snapshot",
        "local_matches_official_verbatim": True,
    },
    "R5-S8-T1": {
        "citation": "GDPR Article 43(1)",
        "official_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32016R0679",
        "verified_date": "2026-09-26",
        "official_sentence_sha256": "367392f6e377363ce4164c015f075d716c2a1e23e71386161eeba4042f535e30",
        "clause_text": (
            "Without prejudice to the tasks and powers of the competent supervisory authority under "
            "Articles 57 and 58, certification bodies which have an appropriate level of expertise in "
            "relation to data protection shall, after informing the supervisory authority in order to "
            "allow it to exercise its powers pursuant to point (h) of Article 58(2) where necessary, "
            "issue and renew certification."
        ),
        "action_precedence": "Certification bodies shall issue and renew certification after informing the supervisory authority where necessary.",
        "local_snapshot_status": "local_processed_snapshot",
        "local_matches_official_verbatim": True,
    },
}

HUMAN_REVIEW_REQUIRED = [
    {
        "item_id": "OFFICIAL_SOURCE_IDENTITY_S7_S8",
        "requirements": ["R5-S7-T1", "R5-S8-T1"],
        "severity": "review_before_gold_freeze",
        "issue": (
            "R5-S7-T1 and R5-S8-T1 are new independent test rows. The local snapshot is a processed "
            "Winter file, but the two relevant sentences match the official EUR-Lex sentence SHA-256 exactly."
        ),
        "requested_action": "User/GPT confirms that the official EUR-Lex sentence is the experiment source identity before Gold freeze.",
        "disposition": "APPROVED_FOR_GOLD",
    },
    {
        "item_id": "R5_S2_T1_SEMANTIC_SOURCE_MISMATCH",
        "requirements": ["R5-S2-T1"],
        "severity": "candidate_asset_not_scored",
        "issue": (
            "The task-model action 'Verify that parental authorisation has been obtained where required' is not "
            "literal in the Article 8(1) excerpt; the verification duty appears in Article 8(2). The row is an "
            "excluded candidate/permission asset and is not scored in the three-class core F1."
        ),
        "requested_action": (
            "Confirm that R5-S2-T1 remains excluded, or provide explicit semantic disposition. Do not silently "
            "convert this row into a core missing-action label."
        ),
        "disposition": "KEEP_EXCLUDED_CANDIDATE",
        "status": "SEMANTIC_SOURCE_MISMATCH_REQUIRES_REVIEW",
    },
    {
        "item_id": "CANDIDATE_PERMISSION_PROHIBITION_ASSETS",
        "requirements": ["R5-S2-T1", "R5-S2-T3", "R5-S2-T4", "R5-S3-T3", "R5-S3-T4"],
        "severity": "candidate_assets_not_scored",
        "issue": (
            "Five permission/prohibition/cessation rows are retained as candidate semantic assets. Their task "
            "wording is a project adaptation for candidate BPMN construction, not a scored positive-duty Gold label."
        ),
        "requested_action": "Confirm the five candidate exclusions remain out of formal core F1.",
        "disposition": "KEEP_ALL_FIVE_EXCLUDED_FROM_CORE_F1",
    },
]


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def task_name(spec: dict, activity_id: str | None) -> str:
    if not activity_id or not activity_id.startswith("Activity_"):
        return ""
    try:
        index = int(activity_id.split("_", 1)[1])
    except (IndexError, ValueError):
        return ""
    tasks = spec.get("tasks") or []
    return tasks[index] if 0 <= index < len(tasks) else ""


def mandatory_activity_binding(spec: dict[str, Any]) -> tuple[str, str]:
    """Recover expected deleted target identity from the frozen construction spec.

    Missing-action BPMNs delete the target node, so reference_cases.target_node is
    null.  The expected target identity comes from mandatory_index/tasks only, never
    from the mutated BPMN, a prediction, or a Gold score.
    """
    index = spec.get("mandatory_index")
    tasks = spec.get("tasks") or []
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(tasks):
        raise RuntimeError(
            "invalid frozen mandatory_index/tasks for missing_action: "
            + repr(spec.get("requirement_id", "?"))
        )
    return f"Activity_{index}", tasks[index]


def case_target_identity(case: dict, spec: dict) -> tuple[str | None, str]:
    if case["variant"] == "missing_action":
        return mandatory_activity_binding(spec)
    target = case.get("target_node")
    return target, task_name(spec, target)


def bpmn_binding(manifest: dict, case_id: str) -> tuple[str, str]:
    suffix = f"/{case_id}.bpmn"
    matches = [key for key in manifest["artifacts"] if key.endswith(suffix)]
    if len(matches) != 1:
        raise RuntimeError(f"expected one BPMN artifact for {case_id}, found {matches}")
    key = matches[0]
    return key, manifest["artifacts"][key]["sha256"]


def mutation_description(case: dict, spec: dict) -> str:
    variant = case["variant"]
    observed = case.get("mutation_observed") or {}
    target, target_name = case_target_identity(case, spec)
    if variant == "baseline":
        return "No mutation; controlled-compliant construction for every eligible type."
    if variant == "missing_action":
        return f"Mandatory activity '{target_name}' is omitted from the process model."
    if variant == "incorrect_actor":
        return (
            f"Activity '{target_name}' is assigned to observed actor {observed.get('actor')!r} "
            f"instead of required actor {spec.get('actor_required')!r}."
        )
    if variant == "out_of_order":
        before, after = case.get("order_pair") or []
        return (
            f"Required precedence '{task_name(spec, before)}' before '{task_name(spec, after)}' is reversed; "
            f"observed sequence is {observed.get('sequence')}."
        )
    return f"Controlled mutation type {variant!r}."


def target_relation(case: dict, spec: dict) -> dict[str, Any]:
    variant = case["variant"]
    observed = case.get("mutation_observed") or {}
    target, target_name = case_target_identity(case, spec)
    result: dict[str, Any] = {
        "variant": variant,
        "target_activity_id": target,
        "target_activity_name": target_name,
    }
    if variant == "incorrect_actor":
        result["required_actor"] = spec.get("actor_required")
        result["observed_actor"] = observed.get("actor")
    if variant == "out_of_order":
        before, after = case.get("order_pair") or []
        result["required_order_pair"] = [before, after]
        result["required_order_names"] = [task_name(spec, before), task_name(spec, after)]
        result["observed_sequence"] = observed.get("sequence")
    if variant == "missing_action":
        result["required_presence"] = "mandatory activity present"
        result["observed_presence"] = "omitted"
    return result


def unsupported_reasons(case: dict, spec: dict) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for violation_type, state in case["reference_states"].items():
        if state == "not_scored":
            reasons[violation_type] = spec["eligibility_basis"].get(
                violation_type, "type not eligible for this requirement"
            )
        elif state == "not_applicable":
            reasons[violation_type] = (
                "not applicable under the single-mutation construction contract because another "
                "target mutation determines the case"
            )
    return reasons


def why_label(case: dict, spec: dict) -> str:
    variant = case["variant"]
    target, target_name = case_target_identity(case, spec)
    observed = case.get("mutation_observed") or {}
    if variant == "baseline":
        return (
            "The controlled baseline contains the mandatory activity, the required actor, and the "
            "source-required action precedence, so every eligible reference state is satisfied and "
            "ineligible types are not scored."
        )
    if variant == "missing_action":
        return (
            f"The source obligation requires the mandatory activity '{target_name}'. The controlled "
            "mutation omits it, so missing_action is violated; actor/order states follow the fixed "
            "single-mutation not_applicable contract."
        )
    if variant == "incorrect_actor":
        return (
            f"The source assigns the relevant action to actor {spec.get('actor_required')!r}. The "
            f"controlled mutation substitutes observed actor {observed.get('actor')!r} while preserving "
            "the action and order, so incorrect_actor is violated."
        )
    if variant == "out_of_order":
        before, after = case.get("order_pair") or []
        return (
            f"The source explicitly orders '{task_name(spec, before)}' before '{task_name(spec, after)}'. "
            "The controlled mutation reverses that order, so out_of_order is violated."
        )
    return "Controlled mutation follows the frozen single-error construction contract."


def element_evidence_payload(element: dict) -> dict[str, Any]:
    evidence = element.get("evidence") or {}
    return {
        "present": bool(element.get("present")),
        "value": element.get("value"),
        "evidence_scope": evidence.get("scope"),
        "evidence_text": evidence.get("text"),
        "evidence_sha256": evidence.get("sha256"),
        "counts_as_stage2_input": evidence.get("counts_as_stage2_input"),
        "note": evidence.get("note"),
    }


def build_packet() -> dict[str, Any]:
    config = load_json(CONFIG)
    sources_doc = load_json(DATA / "source_requirements.json")
    cases_doc = load_json(DATA / "reference/reference_cases.json")
    candidate_doc = load_json(DATA / "reference/candidate_assets.json")
    manifest = load_json(DATA / "manifest.json")
    split_manifest = load_json(DATA / "split_manifest.json")
    order_report = load_json(ORDER_REPORT)

    specs = {row["requirement_id"]: row for row in config["requirements"]}
    sources = {row["requirement_id"]: row for row in sources_doc["requirements"]}
    order_rows = {row["requirement_id"]: row for row in order_report["rows"]}
    cases_by_requirement: dict[str, list[dict]] = {}
    for case in cases_doc["cases"]:
        cases_by_requirement.setdefault(case["requirement_id"], []).append(case)

    core_ids = [row["requirement_id"] for row in sources_doc["requirements"] if row["core_eligible"]]
    core_cases = [case for case in cases_doc["cases"] if case["requirement_id"] in set(core_ids)]

    official_provenance: dict[str, Any] = {}
    for rid, payload in OFFICIAL_PROVENANCE.items():
        local_excerpt = sources[rid]["excerpt_text"]
        local_sha = sha_text(local_excerpt)
        if payload["official_sentence_sha256"] != local_sha or payload["clause_text"] != local_excerpt:
            raise RuntimeError(f"official/local provenance mismatch for {rid}")
        official_provenance[rid] = {
            **payload,
            "local_excerpt_sha256": local_sha,
            "local_excerpt_text": local_excerpt,
        }

    requirements = []
    cases = []
    for rid in core_ids:
        src = sources[rid]
        spec = specs[rid]
        order = order_rows.get(rid)
        requirement_cases = []
        for case in sorted(cases_by_requirement.get(rid, []), key=lambda c: (c["variant"], c["case_id"])):
            bpmn_path, bpmn_sha = bpmn_binding(manifest, case["case_id"])
            case_payload = {
                "case_id": case["case_id"],
                "requirement_id": rid,
                "source_family_id": case["source_family_id"],
                "split": case["split"],
                "citation": case["citation"],
                "baseline_or_mutation_type": case["variant"],
                "bpmn_path": bpmn_path,
                "bpmn_sha256": bpmn_sha,
                "mutation_description": mutation_description(case, spec),
                "target_activity_role_or_order_relation": target_relation(case, spec),
                "expected_reference_state": case["reference_states"],
                "scored_types": case["scored_types"],
                "ineligible_types": case["ineligible_types"],
                "why_this_label_follows_from_source_and_controlled_mutation": why_label(case, spec),
                "unsupported_or_na_reason": unsupported_reasons(case, spec),
                "source_excerpt_sha256": src["text_sha256"],
            }
            requirement_cases.append(case_payload)
            cases.append(case_payload)

        eligibility = src["eligibility"]
        eligible_types = {
            v: bool(eligibility.get(v))
            for v in ("missing_action", "incorrect_actor", "out_of_order")
        }
        unsupported_types = {
            v: spec["eligibility_basis"].get(v, "not eligible")
            for v, is_eligible in eligible_types.items() if not is_eligible
        }
        requirements.append({
            "requirement_id": rid,
            "source_family_id": src["source_family_id"],
            "split": src["split"],
            "citation": src["citation"],
            "exact_regulation_excerpt": src["excerpt_text"],
            "source_sha256": src["text_sha256"],
            "source_file_path": src.get("source_file_path"),
            "source_file_sha256": src.get("source_file_sha256"),
            "source_url": src.get("source_url"),
            "source_status": src.get("source_status"),
            "public_context_note": (
                "A shared public/task context is part of this row."
                if src.get("context_text")
                else "No external context; the exact source excerpt is the only regulation input for this row."
            ),
            "eligible_violation_types": eligible_types,
            "unsupported_types": unsupported_types,
            "order_eligibility": None if order is None else {
                "order_type": order["order_type"],
                "order_evidence": order["order_evidence"],
                "scored_scope": order["scored_scope"],
            },
            "six_element_evidence": {
                name: element_evidence_payload(src["elements"][name])
                for name in ("modality", "actor", "action", "condition", "constraint", "exception")
            },
            "cases": requirement_cases,
        })

    reference_state_counts: dict[str, int] = {}
    variant_counts: dict[str, int] = {}
    na_count = 0
    not_scored_count = 0
    for case in core_cases:
        variant_counts[case["variant"]] = variant_counts.get(case["variant"], 0) + 1
        for state in case["reference_states"].values():
            reference_state_counts[state] = reference_state_counts.get(state, 0) + 1
            if state == "not_applicable":
                na_count += 1
            if state == "not_scored":
                not_scored_count += 1

    all_source_families = sorted({row["source_family_id"] for row in sources_doc["requirements"]})
    test_source_families = sorted({row["source_family_id"] for row in sources_doc["requirements"] if row["split"] == "test"})
    candidate_exclusions = []
    for asset in candidate_doc["assets"]:
        candidate_exclusions.append({
            "requirement_id": asset["requirement_id"],
            "case_id": asset["case_id"],
            "citation": asset["citation"],
            "disposition": asset["disposition"],
            "reason": asset["reason"],
            "legal_basis": asset["legal_basis"],
            "bpmn_path": asset["bpmn_path"],
            "human_or_formal_gold": asset["human_or_formal_gold"],
        })

    packet = {
        "schema_version": "stage3_table3_r5_gold_adjudication_packet@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "packet_status": "AWAITING_USER_GPT_APPROVAL",
        "GOLD_ADJUDICATION_STATUS": "AWAITING_USER_GPT_APPROVAL",
        "human_adjudicated": False,
        "reference_is_gold": False,
        "formal_gold_released": False,
        "prediction_blind": True,
        "prediction_blind_evidence": {
            "method_predictions_read": False,
            "method_scores_read": False,
            "allowed_inputs_only": True,
            "inputs_read": [
                "data/development/stage3_table3_r5_benchmark_v2/source_requirements.json",
                "data/development/stage3_table3_r5_benchmark_v2/reference/reference_cases.json",
                "data/development/stage3_table3_r5_benchmark_v2/reference/candidate_assets.json",
                "data/development/stage3_table3_r5_benchmark_v2/manifest.json",
                "data/development/stage3_table3_r5_benchmark_v2/split_manifest.json",
                "outputs/reports/stage3_table3_r5_order_eligibility_v2.json",
                "configs/stage3_table3_r5_benchmark_v2.json",
            ],
            "forbidden_inputs_not_read": [
                "Ours predictions", "Sun predictions", "Winter predictions",
                "downstream method scores", "Table 3 P/R/F1 results",
            ],
        },
        "gold_derivation_statement": (
            "Gold derives from regulation semantics plus controlled BPMN construction, "
            "not from any method prediction. This packet awaits user/GPT approval and is not a Gold release."
        ),
        "official_provenance": official_provenance,
        "summary": {
            "total_core_requirements": len(core_ids),
            "total_cases": len(core_cases),
            "baseline": variant_counts.get("baseline", 0),
            "missing_action": variant_counts.get("missing_action", 0),
            "incorrect_actor": variant_counts.get("incorrect_actor", 0),
            "out_of_order": variant_counts.get("out_of_order", 0),
            "reference_state_counts": reference_state_counts,
            "not_applicable": na_count,
            "not_scored": not_scored_count,
            "order_counts": {
                "TYPE_A_explicit_action_precedence": order_report["action_precedence_count"],
                "TYPE_B_trigger_precedence": order_report["trigger_precedence_count"],
                "TYPE_C_deadline_arithmetic_only": order_report["deadline_only_unsupported_count"],
            },
            "all_source_family_ids": all_source_families,
            "independent_test_source_family_ids": split_manifest["independent_test_source_family_ids"],
            "candidate_exclusions": candidate_exclusions,
            "human_review_required": HUMAN_REVIEW_REQUIRED,
        },
        "requirements": sorted(requirements, key=lambda r: r["requirement_id"]),
        "cases": sorted(cases, key=lambda c: (c["requirement_id"], c["baseline_or_mutation_type"], c["case_id"])),
    }
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet["summary"]
    lines: list[str] = []
    lines.append("# S3-TABLE3-R5 Formal Gold Adjudication Packet v1")
    lines.append("")
    lines.append("**Status:** `AWAITING_USER_GPT_APPROVAL`")
    lines.append("")
    lines.append("**Gold derivation:** Gold derives from regulation semantics + controlled BPMN construction, not from any method prediction.")
    lines.append("")
    lines.append("**Prediction-blind:** true (no Ours/Sun/Winter predictions or method scores were read).")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Core requirements: {summary['total_core_requirements']}")
    lines.append(f"- Core cases: {summary['total_cases']}")
    lines.append(f"- Baseline / missing_action / incorrect_actor / out_of_order: "
                 f"{summary['baseline']} / {summary['missing_action']} / {summary['incorrect_actor']} / {summary['out_of_order']}")
    lines.append(f"- Reference-state counts: `{json.dumps(summary['reference_state_counts'], ensure_ascii=False, sort_keys=True)}`")
    lines.append(f"- not_applicable / not_scored cells: {summary['not_applicable']} / {summary['not_scored']}")
    lines.append(f"- Order types: `{json.dumps(summary['order_counts'], ensure_ascii=False, sort_keys=True)}`")
    lines.append("")
    lines.append("## Official provenance verification")
    lines.append("")
    lines.append("| Requirement | Citation | Official URL | Verified | Official sentence SHA-256 | Local match |")
    lines.append("|---|---|---|---|---|---|")
    for rid, payload in sorted(packet["official_provenance"].items()):
        lines.append(f"| {rid} | {payload['citation']} | {payload['official_url']} | {payload['verified_date']} | "
                     f"`{payload['official_sentence_sha256']}` | {payload['local_matches_official_verbatim']} |")
    lines.append("")
    lines.append("## HUMAN_REVIEW_REQUIRED")
    lines.append("")
    for item in summary["human_review_required"]:
        reqs = ", ".join(item["requirements"])
        lines.append(f"### {item['item_id']}")
        lines.append("")
        lines.append(f"- Requirements: {reqs}")
        lines.append(f"- Severity: `{item['severity']}`")
        lines.append(f"- Issue: {item['issue']}")
        lines.append(f"- Requested action: {item['requested_action']}")
        if item.get("status"):
            lines.append(f"- Status: `{item['status']}`")
        if item.get("disposition"):
            lines.append(f"- Disposition: `{item['disposition']}`")
        lines.append("")
    lines.append("## Candidate exclusions")
    lines.append("")
    lines.append("| Requirement | Case | Citation | Reason | Disposition |")
    lines.append("|---|---|---|---|---|")
    for row in summary["candidate_exclusions"]:
        lines.append(f"| {row['requirement_id']} | {row['case_id']} | {row['citation']} | {row['reason']} | {row['disposition']} |")
    lines.append("")
    lines.append("## Requirement index")
    lines.append("")
    lines.append("| Requirement | Family | Split | Citation | Eligible types | Order type |")
    lines.append("|---|---|---|---|---|---|")
    for req in packet["requirements"]:
        eligible = ", ".join(k for k, v in req["eligible_violation_types"].items() if v) or "none"
        order_type = req["order_eligibility"]["order_type"] if req["order_eligibility"] else "not_order_eligible"
        lines.append(f"| {req['requirement_id']} | {req['source_family_id']} | {req['split']} | {req['citation']} | {eligible} | {order_type} |")
    lines.append("")
    lines.append("## Case index (all core cases)")
    lines.append("")
    lines.append("| Case | Requirement | Variant | Expected states | BPMN SHA-256 |")
    lines.append("|---|---|---|---|---|")
    for case in packet["cases"]:
        expected = ", ".join(f"{k}={v}" for k, v in sorted(case["expected_reference_state"].items()))
        lines.append(f"| {case['case_id']} | {case['requirement_id']} | {case['baseline_or_mutation_type']} | {expected} | `{case['bpmn_sha256']}` |")
    lines.append("")
    lines.append("The full exact source excerpts, six-element evidence bindings, mutation descriptions, target relations, and unsupported/NA reasons are in the JSON packet.")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    packet = build_packet()
    write_json(OUT_JSON, packet)
    write_text(OUT_MD, render_markdown(packet))
    print(json.dumps({
        "packet_status": packet["packet_status"],
        "core_requirements": packet["summary"]["total_core_requirements"],
        "core_cases": packet["summary"]["total_cases"],
        "human_review_required": len(packet["summary"]["human_review_required"]),
        "prediction_blind": packet["prediction_blind"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
