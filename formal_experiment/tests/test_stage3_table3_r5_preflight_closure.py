"""Focused R5.2 preflight-closure regression tests (zero API).

Covers the named checks requested for the formal Table-3 closure: benchmark
structure, Stage2-input separation, exception grounding, semantic-truth
separation, reuse strength, role normalization, D1 duplicate re-anchoring,
order eligibility, and frozen API payload reconstruction.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import build_stage3_table3_r5_api_payload_freeze_v2 as payload_freeze  # noqa: E402
import build_stage3_table3_r5_order_closure_v2 as order_closure  # noqa: E402
import r5_reuse_verification as reuse_verification  # noqa: E402
import validate_stage3_table3_r5_benchmark_v2 as benchmark_validator  # noqa: E402
from bpc_hybrid.d1_span_canonicalizer import canonicalize_record_coordinates  # noqa: E402
from bpc_hybrid.role_surface import normalize_role_surface  # noqa: E402
from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402

DATA = ROOT / "data/development/stage3_table3_r5_benchmark_v2"
REPORTS = ROOT / "outputs/reports"
CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v2.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_by_id() -> dict:
    doc = load_json(DATA / "source_requirements.json")
    return {row["requirement_id"]: row for row in doc["requirements"]}


def config_by_id() -> dict:
    doc = load_json(CONFIG)
    return {row["requirement_id"]: row for row in doc["requirements"]}


def test_current_benchmark_v2_structural_and_content_validation_passes():
    passed, report = benchmark_validator.validate()
    assert passed
    assert report["structural_passed"] is True
    assert report["content_qualification_passed"] is True


def test_family_split_and_order_closure_counts_are_current_assets():
    manifest = load_json(DATA / "manifest.json")
    split = load_json(DATA / "split_manifest.json")
    assert manifest["independent_requirements"] == 38
    assert manifest["core_requirements"] == 33
    assert manifest["candidate_requirements"] == 5
    assert manifest["core_cases"] == 113
    assert manifest["variants_per_type"] == {
        "missing_action": 33,
        "incorrect_actor": 33,
        "out_of_order": 14,
    }
    assert split["cross_split_families"] == []
    assert "gdpr_art40" in split["independent_test_source_family_ids"]
    assert "gdpr_art43" in split["independent_test_source_family_ids"]


def test_stage2_input_is_separated_from_context_and_cross_reference():
    manifest = load_json(DATA / "manifest.json")
    for row in source_by_id().values():
        for payload in row["elements"].values():
            evidence = payload["evidence"]
            if evidence["scope"] == "source_excerpt":
                assert evidence["counts_as_stage2_input"] is True
                assert evidence["stage2_input_scope"] == "stage2_model_input"
            else:
                assert evidence["counts_as_stage2_input"] is False
                assert evidence["stage2_input_scope"] != "stage2_model_input"
    counts = manifest["element_stage2_input_scope_counts"]
    for element in ("modality", "actor", "action", "condition", "constraint", "exception"):
        assert "stage2_model_input" in counts[element]


def test_article_13_4_and_14_5_exception_grounding_is_cross_reference_only():
    rows = source_by_id()
    for rid in ("R5-D-01", "R5-D-02"):
        evidence = rows[rid]["elements"]["exception"]["evidence"]
        assert rows[rid]["elements"]["exception"]["present"] is True
        assert evidence["scope"] == "cross_reference_text_outside_stage2_input"
        assert evidence["counts_as_stage2_input"] is False
        assert evidence["in_input"] is False
        assert evidence["text"] != "the data subject"
        assert evidence["cross_reference"]["provided_to_task"] is True


def test_article_20_4_semantic_value_matches_actual_source_text():
    row = source_by_id()["R5-D-11"]
    exception = row["elements"]["exception"]
    evidence = exception["evidence"]
    assert exception["present"] is True
    assert "public-interest" not in exception["value"].lower()
    assert exception["value"] == (
        "The right referred to in paragraph 1 shall not adversely affect the rights and freedoms of others."
    )
    assert evidence["scope"] == "cross_reference_text_outside_stage2_input"
    assert evidence["text"] == exception["value"]
    assert evidence["counts_as_stage2_input"] is False


def test_semantic_challenge_evaluator_truth_never_enters_method_visible_facts():
    doc = load_json(DATA / "semantic_challenges.json")
    evaluator_keys = {
        "condition_holds", "exception_applies", "duty_in_force", "outcome",
        "article_17_3_exception_applies", "article_20_4_exception_applies",
        "reference_semantics",
    }
    for pair in doc["pairs"]:
        for case in pair["cases"]:
            assert not (evaluator_keys & set(case["method_visible_facts"]))
        truth = pair["cases"][0]["evaluator_only_truth"]
        if pair["scoring_disposition"] == "unsupported_not_scored":
            assert truth["outcome"] == "not_scored"
        else:
            assert pair["scoring_disposition"] == "scored_separate_from_core_f1"


def test_ours_and_sun_reuse_strength_is_explicit_and_conservative():
    report = load_json(REPORTS / "stage3_table3_r5_prediction_reuse_v2.json")
    summary = report["summary"]
    assert summary["ours_verified_reusable"] == 14
    assert summary["ours_strong_reuse"] == 5
    assert summary["ours_historical_chain_reuse"] == 9
    assert summary["ours_new_requests_core"] == 19
    assert summary["sun_verified_reusable"] == 14
    assert summary["sun_strong_reuse"] == 0
    assert summary["sun_weak_reuse"] == 14


def test_shared_role_surface_normalization_and_controller_processor_distinction():
    assert normalize_role_surface("The Controller") == "controller"
    assert normalize_role_surface(" controller ") == "controller"
    assert normalize_role_surface("a controller") == "controller"
    assert normalize_role_surface("the data controller") == "data controller"
    assert normalize_role_surface("controller") != normalize_role_surface("processor")


def test_d1_raw_offset_unique_duplicate_reanchors_actor_and_relation():
    replay = load_json(REPORTS / "stage3_table3_r5_d1_duplicate_span_replay_v2.json")
    for row in replay["rows"]:
        assert row["status"] == "replayed"
        assert row["actor_recovered"] is True
        assert row["actor_action_relation_recovered"] is True
        assert row["remaining_ambiguity"] is False
        assert row["duplicate_spans"][0]["occurrence_count"] == 2
        assert row["duplicate_spans"][0]["span_id"] == "a01"


def test_d1_ambiguous_duplicate_without_unique_alignment_remains_dropped():
    src = "the taxpayer and the taxpayer file."
    record = {
        "schema_version": "1.0.0",
        "sample_id": "synthetic",
        "source_id": "synthetic",
        "source_text": src,
        "clauses": [
            {
                "clause_id": "c01",
                "clause_span": {"text": src, "start": 0, "end": len(src)},
                "modality": {"label": "obligation", "evidence": [{"text": "file", "start": src.index("file"), "end": src.index("file") + 4}]},
                "actors": [{"id": "a01", "text": "the taxpayer", "start": 99, "end": 111, "normalized": "taxpayer"}],
                "actions": [],
                "conditions": [],
                "constraints": [],
                "exceptions": [],
                "actor_action_map": [],
                "order_relations": [],
            }
        ],
        "method": {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
        "unsupported_or_ambiguous": [],
    }
    out, audit = canonicalize_record_coordinates(record, src)
    assert audit["dropped_spans"] == ["clauses[0].actors[0]"]
    assert out["clauses"][0]["actors"] == []


def test_payload_manifest_reconstructs_exactly_from_frozen_assets():
    frozen = load_json(REPORTS / "stage3_table3_r5_api_payload_freeze_v2.json")
    rebuilt = payload_freeze.build_payload_manifest()
    assert rebuilt == frozen
    assert frozen["new_request_count"] == 19
    assert frozen["real_api_calls_made"] == 0
    assert frozen["authorization_status"] == "PENDING"
    for row in frozen["requests"]:
        body = row["request_body"]
        body_sha = payload_freeze.sha_bytes(
            json.dumps(body).encode("utf-8")
        )
        assert body_sha == row["request_body_sha256"]


def test_payload_contains_no_forbidden_gold_or_reference_fields():
    frozen = load_json(REPORTS / "stage3_table3_r5_api_payload_freeze_v2.json")
    forbidden = {
        "variant", "mutation", "mutation_type", "reference_states", "reference",
        "target_node", "target_rule", "family_id", "requirement_id",
        "case_family", "answer", "gold", "label", "source_family_id", "split",
    }
    for row in frozen["requests"]:
        assert not (forbidden & payload_freeze._walk_keys(row["request_body"]))
        blob = json.dumps(row["request_body"], ensure_ascii=False).lower()
        for term in ("reference_states", "mutation_type", "target_node", "gold_label"):
            assert term not in blob


def test_order_eligibility_is_frozen_source_only_and_deadline_unsupported():
    report = load_json(REPORTS / "stage3_table3_r5_order_eligibility_v2.json")
    assert report["order_requirement_count"] == 14
    assert report["action_precedence_count"] == 7
    assert report["trigger_precedence_count"] == 6
    assert report["deadline_only_unsupported_count"] == 1
    assert report["test_independent_order_family_ids"] == ["gdpr_art12", "gdpr_art40", "gdpr_art43"]
    deadline = [r for r in report["rows"] if r["requirement_id"] == "R5-S5-T4"][0]
    assert deadline["order_type"] == "TYPE_C_deadline_arithmetic_only"
    assert deadline["scored_scope"] == "unsupported_not_scored"
    for row in report["rows"]:
        if row["order_type"] == "TYPE_B_trigger_precedence":
            assert "deadline" in row["scored_scope"] or "not claim" in row["scored_scope"]


class _ZeroSim:
    def text_pair(self, left: str, right: str) -> float:
        return 0.0


class _RoleModel:
    def __init__(self, actors):
        self.actors = actors
        self.business_objects = []
        self.actor_sources = {actor: "actor" for actor in actors}


def test_shared_sun_scorer_applies_approved_role_normalization_only():
    scorer = SunScorer(_ZeroSim(), tau=0.5, gamma=0.8, theta=0.8, nlp=None)
    match = scorer._best_actor_match("the controller", _RoleModel(["Controller"]))
    assert match == ("Controller", 1.0, "actor")
    # No synonym mapping: controller is not processor even with zero similarity.
    assert scorer._best_actor_match("Controller", _RoleModel(["Processor"]))[0] is None
    # Leading article/article case are the only surface transformations used.
    assert scorer._best_actor_match("a Controller", _RoleModel(["controller"])) == ("controller", 1.0, "actor")


def test_all_bpmn_artifacts_parse_and_match_manifest_sha256():
    import hashlib
    import xml.etree.ElementTree as ET

    manifest = load_json(DATA / "manifest.json")
    for rel, binding in manifest["artifacts"].items():
        if not rel.endswith(".bpmn"):
            continue
        raw = (DATA / rel).read_bytes()
        assert len(raw) == binding["bytes"]
        assert hashlib.sha256(raw).hexdigest() == binding["sha256"]
        ET.fromstring(raw)

def test_source_excerpt_evidence_is_exact_substring():
    for row in source_by_id().values():
        excerpt = row["excerpt_text"]
        for element_name, payload in row["elements"].items():
            evidence = payload["evidence"]
            if evidence["scope"] == "source_excerpt":
                assert evidence["text"], (row["requirement_id"], element_name, "empty")
                assert evidence["text"] in excerpt, (
                    row["requirement_id"], element_name, "not exact source substring"
                )


def test_source_excerpt_sha_matches_exact_text():
    for row in source_by_id().values():
        for element_name, payload in row["elements"].items():
            evidence = payload["evidence"]
            if evidence["scope"] == "source_excerpt":
                assert evidence["sha256"] == hashlib.sha256(evidence["text"].encode("utf-8")).hexdigest(), (
                    row["requirement_id"], element_name, "sha mismatch"
                )


def test_r5_s7_action_evidence_supports_submit():
    action = source_by_id()["R5-S7-T1"]["elements"]["action"]["evidence"]
    assert action["scope"] == "source_excerpt"
    lowered = action["text"].lower()
    assert "submit" in lowered
    assert "board" in lowered
    assert lowered != "approving"


def test_r5_s8_actor_evidence_supports_certification_body():
    actor = source_by_id()["R5-S8-T1"]["elements"]["actor"]["evidence"]
    assert actor["scope"] == "source_excerpt"
    lowered = actor["text"].lower()
    assert "certification bodies" in lowered
    assert lowered != "certification"


def test_r5_s8_action_evidence_supports_issue_or_renew():
    action = source_by_id()["R5-S8-T1"]["elements"]["action"]["evidence"]
    assert action["scope"] == "source_excerpt"
    lowered = action["text"].lower()
    assert "issue" in lowered
    assert "renew" in lowered
    assert "certification" in lowered
    assert lowered != "certification"

def test_gold_adjudication_packet_integrity():
    packet = load_json(REPORTS / "stage3_table3_r5_gold_adjudication_packet_v1.json")
    sources = source_by_id()
    manifest = load_json(DATA / "manifest.json")
    assert packet["GOLD_ADJUDICATION_STATUS"] == "AWAITING_USER_GPT_APPROVAL"
    assert packet["packet_status"] == "AWAITING_USER_GPT_APPROVAL"
    assert packet["human_adjudicated"] is False
    assert packet["reference_is_gold"] is False
    assert packet["formal_gold_released"] is False
    assert packet["prediction_blind"] is True
    assert packet["summary"]["total_core_requirements"] == 33
    assert packet["summary"]["total_cases"] == 113
    variants = {}
    case_ids = set()
    for req in packet["requirements"]:
        source = sources[req["requirement_id"]]
        assert req["exact_regulation_excerpt"] == source["excerpt_text"]
        assert req["source_sha256"] == source["text_sha256"]
        for case in req["cases"]:
            assert case["case_id"] not in case_ids
            case_ids.add(case["case_id"])
            variants[case["baseline_or_mutation_type"]] = variants.get(case["baseline_or_mutation_type"], 0) + 1
            assert case["bpmn_sha256"] == manifest["artifacts"][case["bpmn_path"]]["sha256"]
            assert set(case["expected_reference_state"]) == {"missing_action", "incorrect_actor", "out_of_order"}
            assert case["why_this_label_follows_from_source_and_controlled_mutation"]
            assert isinstance(case["unsupported_or_na_reason"], dict)
    assert len(case_ids) == 113
    assert variants == {"baseline": 33, "missing_action": 33, "incorrect_actor": 33, "out_of_order": 14}


def test_gold_packet_missing_action_targets_are_bound_to_frozen_mandatory_activity():
    packet = load_json(REPORTS / "stage3_table3_r5_gold_adjudication_packet_v1.json")
    specs = config_by_id()
    missing_action_cases = [
        case for case in packet["cases"]
        if case["baseline_or_mutation_type"] == "missing_action"
    ]

    blank_targets = 0
    binding_mismatches = 0
    description_misses = 0
    why_label_misses = 0
    for case in missing_action_cases:
        spec = specs[case["requirement_id"]]
        expected_id = f"Activity_{spec['mandatory_index']}"
        expected_name = spec["tasks"][spec["mandatory_index"]]
        relation = case["target_activity_role_or_order_relation"]
        target_id = relation["target_activity_id"]
        target_name = relation["target_activity_name"]

        if target_id is None or target_name == "":
            blank_targets += 1
        if target_id != expected_id or target_name != expected_name:
            binding_mismatches += 1
        if expected_name not in case["mutation_description"]:
            description_misses += 1
        if expected_name not in case["why_this_label_follows_from_source_and_controlled_mutation"]:
            why_label_misses += 1

    print(f"missing_action_cases = {len(missing_action_cases)}")
    print(f"missing_action_blank_target_names = {blank_targets}")
    print(f"missing_action_target_binding_mismatches = {binding_mismatches}")

    assert len(missing_action_cases) == 33
    assert blank_targets == 0
    assert binding_mismatches == 0
    assert description_misses == 0
    assert why_label_misses == 0


def test_gold_adjudication_packet_is_prediction_blind():
    packet = load_json(REPORTS / "stage3_table3_r5_gold_adjudication_packet_v1.json")
    evidence = packet["prediction_blind_evidence"]
    assert evidence["method_predictions_read"] is False
    assert evidence["method_scores_read"] is False
    assert evidence["allowed_inputs_only"] is True
    script = (ROOT / "scripts/build_stage3_table3_r5_gold_adjudication_packet_v1.py").read_text(encoding="utf-8")
    for forbidden_path in (
        "data/predictions",
        "stage3_table3_r5_prediction_reuse",
        "stage3_table3_r5_benchmark_v2_eval",
        "Table 3 P/R/F1",
    ):
        # The explicit forbidden list may name outcomes; only executable input
        # paths and import-like references are disallowed.
        assert f'ROOT / "{forbidden_path}"' not in script
