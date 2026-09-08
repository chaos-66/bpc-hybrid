# -*- coding: utf-8 -*-
"""Focused offline tests for the Task D Direct-LLM Stage-3 linkage work.

Scope (everything synthetic; zero network / zero API / zero .env):
  1. parameterized capsule converter: both allowed schemas convertible,
     unknown schema / explicit expected_schema mismatch fail loudly,
     malicious spans are counted and never fabricated;
  2. ``run_gdpr_3type_linkage_v1`` pure internals (``build_source_report`` /
     ``diff_arm_vs_reference`` / ``evaluate_rows_doc``): obligation-only
     gate, missing actions count, in_doubt envelopes are explicit failures
     (never compliant), reference-vs-direct per-item diff with the stable
     reason enum, and gold is consumed only in evaluation (injected after
     the rows are fixed);
  3. change-classifier enum unit tests (all seven reasons);
  4. four-new-type linkage: the first-valid-span projection consumes clean
     Direct-LLM rows and counts missing rows explicitly; the unified
     five-class decision function is deterministic and is the same code path
     on both sides;
  5. repair_v2 / reevaluate source parameterization: fail closed on a missing
     capsule (monkeypatched synthetic paths) and the default two-source
     behaviour is unchanged;
  6. promotion script: a legal synthetic development capsule passes dry-run
     and applies atomically to a tmp target with the full promotion manifest;
     partial/in_doubt telemetry, an existing target, text/Gold leakage and
     fake-run transport each refuse with exit 2 and zero writes.

Real frozen files (the 74-sentence input pack, the preflight report, the
33-item Gold, the direct dev capsule) are READ ONLY where hashes must match
(e.g. the promotion binding checks); nothing is written outside pytest
``tmp_path`` directories.
"""

from __future__ import annotations

import copy
import datetime
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.sun_stage3.gdpr_capsule_converter import (  # noqa: E402
    ALLOWED_CAPSULE_SCHEMAS,
    CAPSULE_SCHEMA,
    DIRECT_LLM_CAPSULE_SCHEMA,
    build_rule_records,
    sentence_texts_by_sample,
)
from bpc_hybrid.sun_stage3.gdpr_change_classifier import (  # noqa: E402
    CHANGE_REASONS,
    assert_reason,
    classify_extended_item,
    classify_three_type_item,
)
from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402

import run_gdpr_3type_linkage_v1 as linkage  # noqa: E402
import promote_gdpr7_direct_llm_arm_v1 as promo  # noqa: E402

INPUT_PACK = ROOT / "data/input/gdpr7_stage2_input_v1.json"
PREFLIGHT = ROOT / "outputs/reports/gdpr7_direct_llm_preflight_v1.json"

# ---------------------------------------------------------------------------
# Synthetic capsule / rule text helpers
# ---------------------------------------------------------------------------

TEXT6 = ("The controller shall review the file without undue delay and shall "
         "not keep the data longer than 72 hours after the breach.")
RULE6 = "article6"
SAMPLE6 = "gdpr_article6_s001"


def _capsule_doc(records, schema=DIRECT_LLM_CAPSULE_SCHEMA, record_count=74):
    return {
        "schema_version": schema,
        "dataset_id": "gdpr7_stage2_sentences_v1",
        "method_id": "direct_llm" if schema == DIRECT_LLM_CAPSULE_SCHEMA
        else "sun_rule_only",
        "record_count": len(records),
        "records": records,
    }


def _ok_record(sample_id, *, modality="obligation", action_span=None,
               actor_span=None, with_map=True, order=None, corrupt=False):
    """One envelope row; spans are coordinates into TEXT6."""
    clauses = []
    clause = {
        "clause_id": f"{sample_id}.c1",
        "clause_span": {"start": 0, "end": len(TEXT6)},
        "modality": {"label": modality, "evidence": [{"start": 15, "end": 21}]},
        "actors": [dict(actor_span)] if actor_span else [],
        "actions": [dict(action_span)] if action_span else [],
        "conditions": [],
        "constraints": [],
        "exceptions": [],
        "actor_action_map": ([{"actor_id": "a1", "action_id": "x1"}]
                             if with_map and actor_span and action_span else []),
        "order_relations": order or [],
    }
    if corrupt:
        # hidden raw-text key -> containment scan must reject at promotion
        clause["text"] = TEXT6
    clauses.append(clause)
    return {
        "sample_id": sample_id,
        "request_status": "ok",
        "record": {
            "schema_version": "1.0.0",
            "sample_id": sample_id,
            "source_id": sample_id,
            "clauses": clauses,
            "method": {"name": "direct_llm",
                       "schema_source": "stage2_prediction.schema.json@1.0.0"},
            "validation": {"schema_valid": True, "cross_field_valid": True,
                           "errors": []},
        },
        "error_category": None,
    }


def _in_doubt_row(sample_id, error_category="decode_or_usage_missing"):
    return {
        "sample_id": sample_id,
        "request_status": "in_doubt",
        "record": None,
        "error_category": error_category,
    }


def _sha256_text(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fmt_json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8")


# ---------------------------------------------------------------------------
# 1) parameterized converter
# ---------------------------------------------------------------------------


def _article6_capsule(schema):
    act = {"id": "x1", "start": 21, "end": 27}   # "review"
    actor = {"id": "a1", "start": 4, "end": 14}  # "controller"
    rec = _ok_record(SAMPLE6, action_span=act, actor_span=actor)
    return _capsule_doc([rec], schema=schema, record_count=1), {SAMPLE6: TEXT6}


def test_converter_accepts_both_schemas_with_identical_rows():
    for schema in ALLOWED_CAPSULE_SCHEMAS:
        capsule, texts = _article6_capsule(schema)
        records, summary = build_rule_records(capsule, texts, [RULE6])
        rec = records[RULE6]
        assert not rec["failed"]
        assert rec["actions"] == ["review"]
        assert rec["actors"] == ["controller"]
        assert rec["actor_action_pairs"] == [
            {"actor": "controller", "action": "review"}]
        assert summary["capsule_schema"] == schema
        assert summary["capsule_schema_ok"] is True
        assert summary["capsule_records"] == 1
        if schema == DIRECT_LLM_CAPSULE_SCHEMA:
            assert "Direct-LLM" in rec["provenance"]["source"]
        else:
            assert "Rules-Only" in rec["provenance"]["source"]
    # explicit expected_schema pinning works for both
    capsule, texts = _article6_capsule(DIRECT_LLM_CAPSULE_SCHEMA)
    build_rule_records(capsule, texts, [RULE6],
                       expected_schema=DIRECT_LLM_CAPSULE_SCHEMA)
    with pytest.raises(ValueError, match="schema mismatch"):
        build_rule_records(capsule, texts, [RULE6],
                           expected_schema=CAPSULE_SCHEMA)


def test_converter_unknown_schema_fails_loudly():
    capsule, texts = _article6_capsule("not_a_real_schema@9.9.9")
    with pytest.raises(ValueError, match="not in the allowed set"):
        build_rule_records(capsule, texts, [RULE6])
    # no silent conversion: a direct-style record under an unknown schema
    rec = _ok_record(SAMPLE6, action_span={"id": "x1", "start": 22, "end": 28},
                     actor_span={"id": "a1", "start": 4, "end": 14})
    capsule = _capsule_doc([rec], schema="gdpr7_sun_rule_only_predictions@0.9",
                           record_count=1)
    with pytest.raises(ValueError):
        build_rule_records(capsule, texts, [RULE6])


def test_converter_malicious_spans_fail_without_fabrication():
    # end beyond the text length -> invalid span, no action text ever built
    rec = _ok_record(SAMPLE6,
                     action_span={"id": "x1", "start": 22, "end": 999},
                     actor_span={"id": "a1", "start": 4, "end": 14})
    capsule = _capsule_doc([rec], schema=DIRECT_LLM_CAPSULE_SCHEMA,
                           record_count=1)
    records, summary = build_rule_records(capsule, {SAMPLE6: TEXT6}, [RULE6])
    assert records[RULE6]["actions"] == []
    assert records[RULE6]["actors"] == ["controller"]
    assert summary["total_invalid_spans"] >= 1
    # a record whose action slice lies inside the sentence is fine
    rec2 = _ok_record(SAMPLE6,
                      action_span={"id": "x1", "start": 0, "end": 9999})
    capsule2 = _capsule_doc([rec2], schema=DIRECT_LLM_CAPSULE_SCHEMA,
                            record_count=1)
    records2, _ = build_rule_records(capsule2, {SAMPLE6: TEXT6}, [RULE6])
    assert records2[RULE6]["actions"] == []
    # reverse span is invalid too
    rec3 = _ok_record(SAMPLE6,
                      action_span={"id": "x1", "start": 30, "end": 5})
    capsule3 = _capsule_doc([rec3], schema=DIRECT_LLM_CAPSULE_SCHEMA,
                            record_count=1)
    records3, summary3 = build_rule_records(capsule3, {SAMPLE6: TEXT6},
                                            [RULE6])
    assert records3[RULE6]["actions"] == []
    assert summary3["total_invalid_spans"] >= 1


def test_converter_obligation_only_gate():
    # permission clause carries an action but must be excluded and counted
    rec = _ok_record(SAMPLE6, modality="permission",
                     action_span={"id": "x1", "start": 22, "end": 28})
    capsule = _capsule_doc([rec], schema=DIRECT_LLM_CAPSULE_SCHEMA,
                           record_count=1)
    records, summary = build_rule_records(capsule, {SAMPLE6: TEXT6}, [RULE6])
    assert records[RULE6]["actions"] == []   # excluded by the obligation gate
    per_rule = summary["per_rule"][RULE6]
    assert per_rule["excluded_modality_counts"] == {"permission": 1}
    assert per_rule["included_clause_count"] == 0


def test_converter_missing_envelope_is_an_explicit_failure():
    capsule = _capsule_doc([], schema=DIRECT_LLM_CAPSULE_SCHEMA, record_count=0)
    records, summary = build_rule_records(capsule, {SAMPLE6: TEXT6}, [RULE6])
    assert records[RULE6]["failed"] is True
    assert any("stage2_prediction_missing" in r
               for r in records[RULE6]["failure_reasons"])
    assert summary["per_rule"][RULE6]["envelopes_failed"] == 1


# ---------------------------------------------------------------------------
# 2) 3-type pure internals (synthetic gold + rows; no real Gold read)
# ---------------------------------------------------------------------------

ALL_TYPES = ("missing_action", "incorrect_actor", "out_of_order")


def _synthetic_gold(decision_by_item):
    return {
        "dataset_id": "synthetic_33_gold_for_test",
        "count": len(decision_by_item),
        "items": [
            {"item_id": item_id,
             "decision_violation_type": decision_by_item[item_id]}
            for item_id in sorted(decision_by_item)
        ],
    }


def _simple_row(item_id, check, pred, observable=True, reason=None,
                failed=False, external_failure=None, rule_id=RULE6):
    scores = {
        "missing_action": None, "incorrect_actor": None, "out_of_order": None,
        "missing_action_denominator": 1, "incorrect_actor_denominator": 1,
        "incorrect_actor_observable": observable,
        "incorrect_actor_reason": reason,
        "out_of_order_denominator": 0,
    }
    return {
        "schema_version": "stage3_prediction@1.0.0",
        "method_id": "sun_2024",
        "run_id": "gdpr_3type_linkage_v1_test_direct",
        "task": "violation",
        "item_id": item_id,
        "process_id": "gdpr_1_data_breach",
        "rule_id": rule_id,
        "check_type": check,
        "matching_score": None,
        "predicted_relevance": None,
        "missing_action_score": None,
        "incorrect_actor_score": None,
        "out_of_order_score": None,
        "predicted_violation_type": pred,
        "evidence": None,
        "gold_visible": False,
        "external_arm": "direct_llm",
        "external_failure": external_failure,
        "rule_record_failed": failed,
        "incorrect_actor_observable": observable,
        "incorrect_actor_reason": reason,
        "scores": scores,
    }


def test_build_source_report_evaluates_with_injected_gold_only_after_rows():
    decision = {"v001": "missing_action", "v002": "incorrect_actor"}
    gold = _synthetic_gold(decision)
    ref_rows = [
        _simple_row("v001", "missing_action", "missing_action"),
        _simple_row("v002", "incorrect_actor", "incorrect_actor",
                    observable=True),
    ]
    direct_rows = [
        _simple_row("v001", "missing_action", "missing_action"),
        _simple_row("v002", "incorrect_actor", None, observable=False,
                    reason="missing_rule_actor_action_map"),
    ]
    summary = linkage.build_source_report(
        "direct_llm", rows=direct_rows, gold_doc=gold,
        thresholds={"tau": 0.8, "gamma": 0.8, "theta": 0.8},
        reference_rows=ref_rows,
        arm_diag={"rule_record_source": "direct_llm test",
                  "capsule_used": True, "conversion_summary": {}},
    )
    ev = summary["evaluation"]["violation"]
    assert ev["support"] == 2
    assert ev["detected"] == 1
    assert ev["missed"] == 1
    # per-item gold labels are present in the evaluation items (gold applied)
    items = {i["item_id"]: i for i in summary["evaluation"]["items"]}
    assert items["v002"]["gold_type"] == "incorrect_actor"
    # predictions themselves are gold-independent: flipping the gold labels
    # changes ONLY the evaluation, never the rows we pass in.
    flipped = _synthetic_gold({"v001": "incorrect_actor",
                               "v002": "out_of_order"})
    summary2 = linkage.build_source_report(
        "direct_llm", rows=direct_rows, gold_doc=flipped,
        thresholds={"tau": 0.8, "gamma": 0.8, "theta": 0.8})
    assert summary2["evaluation"]["violation"]["detected"] == 0
    assert [r["predicted_violation_type"] for r in direct_rows] == [
        "missing_action", None]   # rows untouched by the gold flip
    # reference diff produced and reasons are drawn from the stable enum
    diff = summary["reference_diff"]
    assert diff["changed_count"] == 1
    changed = diff["changes"][0]
    assert changed["item_id"] == "v002"
    assert changed["machine_change_reason"] in CHANGE_REASONS


def test_in_doubt_envelope_rows_are_explicit_failures_never_compliant():
    capsule = _capsule_doc([_in_doubt_row(SAMPLE6)], schema=DIRECT_LLM_CAPSULE_SCHEMA,
                           record_count=1)
    records, summary = build_rule_records(capsule, {SAMPLE6: TEXT6}, [RULE6])
    assert records[RULE6]["failed"] is True
    reason = records[RULE6]["failure_reasons"][0]
    assert "stage2_prediction_failed:in_doubt" in reason
    item = {"item_id": "v001", "process_id": "p1", "rule_id": RULE6,
            "check_type": "missing_action"}
    row = linkage._failed_row("direct_llm", item, RULE6, "missing_action",
                              reason)
    # not compliant: nothing scored, predicted None, explicit failure marker
    assert row["predicted_violation_type"] is None
    assert row["rule_record_failed"] is True
    assert row["scores"]["missing_action"] is None
    assert "stage2_prediction_failed:in_doubt" in row["external_failure"]


def test_missing_action_counting_and_reference_diff_reason_enum():
    # scorer-level formula: a rule action with no model match above gamma is
    # missing (denominator keeps it; score == 1/1)
    class _Exact:
        def text_pair(self, a, b):
            return float(a == b)
    model = type("M", (), {
        "actions": [{"id": "a1", "name": "Review"}], "actors": ["Manager"],
        "business_objects": [],
        "action_actor_names": {"a1": ["Manager"]},
    })()
    scorer = SunScorer(_Exact(), 0.8, 0.8, 0.8)
    assert scorer.missing_action(["Review"], model)["score"] == 0
    assert scorer.missing_action(["File"], model) == {
        "score": 1.0, "missing": 1, "denominator": 1,
        "details": [{"rule_action": "File", "best_model_action": None,
                     "similarity": 0.0, "missing": True}]}

    # reference-vs-direct diff: an item whose rule record lost all its actor
    # content through the obligation-only modality gate is classified
    ref_records = {RULE6: {"actions": ["review"], "actors": ["controller"],
                           "actor_action_pairs": [
                               {"actor": "controller", "action": "review"}],
                           "order_relations": []}}
    arm_records = {RULE6: {"actions": ["review"], "actors": [],
                           "actor_action_pairs": [], "order_relations": []}}
    arm_conversion = {"per_rule": {RULE6: {
        "envelopes_failed": 0, "included_clause_count": 0,
        "excluded_modality_counts": {"prohibition": 1},
        "invalid_span_count": 0}}}
    ref_rows = [_simple_row("v001", "incorrect_actor", "incorrect_actor",
                            observable=True, reason=None)]
    direct_rows = [_simple_row("v001", "incorrect_actor", None,
                               observable=False,
                               reason="empty_rule_actor_denominator")]
    diff = linkage.diff_arm_vs_reference(
        direct_rows, ref_rows, arm="direct_llm",
        reference_records=ref_records, arm_records=arm_records,
        arm_conversion=arm_conversion,
        gold_doc=_synthetic_gold({"v001": "incorrect_actor"}))
    assert diff["changed_count"] == 1
    assert diff["changes"][0]["machine_change_reason"] == \
        "modality_flip_to_unobservable"


# ---------------------------------------------------------------------------
# 3) change classifier unit tests
# ---------------------------------------------------------------------------


def _classifier_pair(**over):
    base_ref = _simple_row("v001", "incorrect_actor", "incorrect_actor",
                           observable=True, reason=None)
    base_arm = _simple_row("v001", "incorrect_actor", None,
                           observable=False, reason="other_reason")
    ref = dict(base_ref)
    arm = dict(base_arm)
    if over.get("ref_check"):
        ref["check_type"] = over["ref_check"]
    if over.get("arm_check"):
        arm["check_type"] = over["arm_check"]
    if over.get("arm_obs_reason") is not None:
        arm["incorrect_actor_reason"] = over["arm_obs_reason"]
        arm["scores"]["incorrect_actor_reason"] = over["arm_obs_reason"]
    if over.get("arm_failed"):
        arm["rule_record_failed"] = True
        arm["external_failure"] = "stage2_prediction_failed:in_doubt:x"
    if over.get("arm_pred") is not None:
        arm["predicted_violation_type"] = over["arm_pred"]
    return ref, arm


def test_change_reason_enum_is_stable_and_validated():
    assert CHANGE_REASONS == (
        "modality_flip_to_unobservable",
        "span_absent",
        "first_valid_projection_changed",
        "action_mapping_below_gamma",
        "time_constraint_applicability_changed",
        "order_relations_missing",
        "other",
    )
    assert assert_reason("other") == "other"
    with pytest.raises(ValueError, match="unknown change reason"):
        assert_reason("not_a_reason")


def test_classifier_external_failure_is_other():
    ref, arm = _classifier_pair(arm_failed=True)
    out = classify_three_type_item(ref, arm)
    assert out["reason"] == "other"
    assert out["detail"]["class"] == "external_envelope_failure"


def test_classifier_action_mapping_below_gamma():
    ref, arm = _classifier_pair(arm_obs_reason="action_mapping_below_gamma")
    out = classify_three_type_item(ref, arm)
    assert out["reason"] == "action_mapping_below_gamma"


def test_classifier_modality_flip_and_span_absent():
    ref = _simple_row("v001", "incorrect_actor", "incorrect_actor",
                      observable=True)
    arm = _simple_row("v001", "incorrect_actor", None, observable=False,
                      reason="empty_rule_actor_denominator")
    ref_records = {RULE6: {"actions": ["review"], "actors": ["controller"],
                           "actor_action_pairs": [
                               {"actor": "controller", "action": "review"}],
                           "order_relations": []}}
    # modality flip: capsule carried a prohibition clause (excluded) and no
    # further obligation clause -> content lost via the modality gate
    arm_records_flip = {RULE6: {"actions": [], "actors": [],
                                "actor_action_pairs": [],
                                "order_relations": []}}
    conv_flip = {"per_rule": {RULE6: {
        "envelopes_failed": 0, "included_clause_count": 0,
        "excluded_modality_counts": {"prohibition": 1},
        "invalid_span_count": 0}}}
    out = classify_three_type_item(
        ref, arm, reference_records=ref_records,
        arm_records=arm_records_flip, arm_conversion=conv_flip)
    assert out["reason"] == "modality_flip_to_unobservable"
    # span absence: no modality exclusion but invalid spans / gate-passing
    # clause carried no action spans -> content lost on the span level
    arm_records_span = {RULE6: {"actions": [], "actors": [],
                                "actor_action_pairs": [],
                                "order_relations": []}}
    conv_span = {"per_rule": {RULE6: {
        "envelopes_failed": 0, "included_clause_count": 1,
        "excluded_modality_counts": {}, "invalid_span_count": 1}}}
    out = classify_three_type_item(
        ref, arm, reference_records=ref_records,
        arm_records=arm_records_span, arm_conversion=conv_span)
    assert out["reason"] == "span_absent"


def test_classifier_order_relations_missing():
    ref = _simple_row("v001", "out_of_order", "out_of_order")
    arm = _simple_row("v001", "out_of_order", None)
    ref_records = {RULE6: {"actions": ["a"], "actors": [],
                           "actor_action_pairs": [],
                           "order_relations": [("a", "b")]}}
    arm_records = {RULE6: {"actions": ["a"], "actors": [],
                           "actor_action_pairs": [],
                           "order_relations": []}}
    out = classify_three_type_item(ref, arm, reference_records=ref_records,
                                   arm_records=arm_records)
    assert out["reason"] == "order_relations_missing"


def test_classifier_extended_reasons():
    def extended_row(pred=None, obs=True, obs_reason=None, expected="constraint_violated",
                     external_failure=None, exact=None, detail_exact=None):
        row = {
            "item_id": "v001", "expected_violation": expected,
            "predicted_violation_type": pred,
            "scores": {}, "scores_detail": {expected: {}},
            "observability": {expected: {"observable": obs,
                                         "reason": obs_reason}},
            "control_scores": {},
            "external_failure": external_failure,
        }
        if exact is not None or detail_exact is not None:
            row["scores_detail"][expected]["exact_contradiction"] = (
                detail_exact if detail_exact is not None else exact)
        return row

    # modality gate on the external side
    ref = extended_row(pred="constraint_violated", expected="prohibited_action_present",
                       obs_reason=None)
    arm = extended_row(pred=None, obs=False,
                       obs_reason="rule_modality_not_prohibition",
                       expected="prohibited_action_present")
    out = classify_extended_item(ref, arm)
    assert out["reason"] == "modality_flip_to_unobservable"

    # constraint applicability change
    ref = extended_row(pred="constraint_violated",
                       detail_exact={"contradiction": True,
                                     "reason": "candidate_time_limit_exceeds_rule_limit"})
    arm = extended_row(pred=None, detail_exact={"contradiction": False,
                                                "reason": "time_bound_inside_condition"})
    out = classify_extended_item(ref, arm)
    assert out["reason"] == "time_constraint_applicability_changed"

    # observable verdict flip -> projection default
    ref = extended_row(pred="prohibited_action_present",
                       expected="prohibited_action_present")
    arm = extended_row(pred=None, expected="prohibited_action_present")
    out = classify_extended_item(ref, arm)
    assert out["reason"] == "first_valid_projection_changed"

    # detection-side mapping loss
    ref = extended_row(pred="constraint_violated")
    arm = extended_row(pred=None, obs=False,
                       obs_reason="action_mapping_below_gamma")
    out = classify_extended_item(ref, arm)
    assert out["reason"] == "action_mapping_below_gamma"

    # envelope failure
    arm = extended_row(pred=None, external_failure="stage2_prediction_missing")
    out = classify_extended_item(ref, arm)
    assert out["reason"] == "other"


# ---------------------------------------------------------------------------
# 4) four-new-type linkage: clean direct rows are consumed, missing counted,
#    unified five-class decision is deterministic and shared
# ---------------------------------------------------------------------------

TEXT_SHORT = "The controller shall notify within 72 hours after the breach."


def test_four_type_projection_consumes_clean_direct_rows_and_counts_missing():
    from bpc_hybrid.gdpr_s2_s3_projection import (
        project_external_sentence,
        projection_summary,
    )
    s_ok = "gdpr_article33_s001"
    s_missing = "gdpr_article33_s002"
    act = {"id": "x1", "start": 21, "end": 27}   # "notify"
    actor = {"id": "a1", "start": 4, "end": 14}  # "controller"
    ok_row = _ok_record(s_ok, action_span=act, actor_span=actor)
    ok_proj = project_external_sentence(ok_row, TEXT_SHORT, s_ok)
    assert ok_proj["ok"] is True
    assert ok_proj["sentence"]["action"] == "notify"
    assert ok_proj["sentence"]["actor"] == "controller"
    # a missing sample -> explicit failure row, counted by projection_summary
    # (the runner wraps every projection with its sample id before summary)
    missing_proj = project_external_sentence({}, TEXT_SHORT, s_missing)
    assert missing_proj["ok"] is False
    summary = projection_summary([
        {"sample_id": s_ok, **ok_proj},
        {"sample_id": s_missing, **missing_proj},
    ])
    assert summary["total"] == 2
    assert summary["failed"] == [s_missing]
    # an in_doubt envelope (error_category set) is never consumed as content
    bad_row = _in_doubt_row(s_ok)
    assert project_external_sentence(bad_row, TEXT_SHORT, s_ok)["ok"] is False


def test_linkage_direct_arm_registered():
    import run_gdpr_s2_s3_linkage_v1 as linkage4
    assert "direct_llm" in linkage4.ARM_PATHS
    assert linkage4.ARM_PATHS["direct_llm"] == (
        ROOT / "data/predictions/gdpr7_direct_llm_v1/predictions.json")
    assert linkage4.ARM_PREDICTION_SCHEMAS["direct_llm"] == \
        DIRECT_LLM_CAPSULE_SCHEMA
    assert linkage4.ARM_LABELS["direct_llm"]


def test_unified_five_class_decision_is_deterministic_and_shared():
    from bpc_hybrid.s3_extended_unified import (
        UNIFIED_DECISION_NAME,
        side_scores_from_row,
        unified_prediction,
        unified_rows,
    )
    from bpc_hybrid.stage3_extended_violations import (
        EXTENDED_TYPES,
        control_prediction_from_scores,
    )
    scores = {t: (0.9 if t == "constraint_violated" else 0.1)
              for t in EXTENDED_TYPES}
    row = {
        "item_id": "v001",
        "expected_violation": "constraint_violated",
        "predicted_violation_type": "constraint_violated",
        "scores": dict(scores),
        "scores_detail": {t: {} for t in EXTENDED_TYPES},
        "observability": {t: {"observable": True, "reason": None}
                          for t in EXTENDED_TYPES},
        "control_scores": {
            t: {"score": scores[t], "observable": True, "reason": None,
                "exact_contradiction": None} for t in EXTENDED_TYPES},
    }
    first = unified_prediction(row, "variant", 0.5)
    second = unified_prediction(row, "variant", 0.5)
    assert first["predicted"] == second["predicted"]
    assert first["decision"] == UNIFIED_DECISION_NAME
    # the shared decision function path: unified_prediction('variant') ==
    # control_prediction_from_scores(side_scores_from_row(row,'variant'))
    direct = control_prediction_from_scores(
        side_scores_from_row(row, "variant"), 0.5)
    assert direct["predicted"] == first["predicted"]
    assert direct["all_unobservable"] == first["all_unobservable"]
    # unified_rows is deterministic for identical input
    a = unified_rows([copy.deepcopy(row)], 0.5)
    b = unified_rows([copy.deepcopy(row)], 0.5)
    assert a[0]["unified_predicted_raw"] == b[0]["unified_predicted_raw"]
    assert a[0]["predicted_conditional_old"] == b[0]["predicted_conditional_old"]


# ---------------------------------------------------------------------------
# 5) repair_v2 / reevaluate source parameterization
# ---------------------------------------------------------------------------


def test_reevaluate_direct_source_fails_closed_without_capsule(
        tmp_path, monkeypatch):
    import reevaluate_s3_extended_unified_v1 as runner
    missing = tmp_path / "capsule" / "predictions.json"
    assert not missing.exists()
    monkeypatch.setattr(runner, "DIRECT_LLM_CAPSULE_PREDICTIONS", missing)
    with pytest.raises(FileNotFoundError, match="direct_llm"):
        runner.check_source_capsule_ready("direct_llm")
    assert runner.check_source_capsule_ready("reference") is None
    assert runner.check_source_capsule_ready("rules_only") is None
    # a complete 74/74-ok synthetic capsule unlocks the source
    ok_rows = []
    for idx in range(74):
        sid = f"gdpr_article6_s{idx:03d}"
        act = {"id": "x1", "start": 22, "end": 28}
        rec = _ok_record(sid, action_span=act)
        ok_rows.append(rec)
    ok_doc = _capsule_doc(ok_rows, schema=DIRECT_LLM_CAPSULE_SCHEMA,
                          record_count=74)
    ok_path = tmp_path / "capsule" / "predictions.json"
    ok_path.parent.mkdir(parents=True, exist_ok=True)
    ok_path.write_bytes(_fmt_json_bytes(ok_doc))
    monkeypatch.setattr(runner, "DIRECT_LLM_CAPSULE_PREDICTIONS", ok_path)
    binding = runner.check_source_capsule_ready("direct_llm")
    assert binding["rows"] == 74
    assert binding["all_rows_ok"] is True
    # incomplete capsule (one non-ok row) still refuses
    bad_doc = _capsule_doc(ok_rows[:-1] + [_in_doubt_row("gdpr_article6_s999")],
                           schema=DIRECT_LLM_CAPSULE_SCHEMA, record_count=74)
    bad_path = tmp_path / "capsule" / "predictions_bad.json"
    bad_path.write_bytes(_fmt_json_bytes(bad_doc))
    monkeypatch.setattr(runner, "DIRECT_LLM_CAPSULE_PREDICTIONS", bad_path)
    with pytest.raises(RuntimeError, match="non-ok"):
        runner.check_source_capsule_ready("direct_llm")


def test_repair_v2_default_sources_and_missing_capsule_fail_closed(tmp_path):
    import run_s3_formula_repair_v2 as repair
    # default (historical) behaviour unchanged
    assert repair.DEFAULT_SOURCES == ("reference", "rules_only")
    paths = repair.resolve_capsule_paths(("reference", "rules_only"), None)
    assert paths["rules_only"] == linkage.CAPSULE_PREDICTIONS
    assert paths["rules_only"].is_file()
    # requesting direct_llm without a capsule fails closed BEFORE any write
    out = tmp_path / "out"
    report = tmp_path / "report.json"
    with pytest.raises(FileNotFoundError, match="direct_llm"):
        repair.run(out, report, sources=("reference", "rules_only",
                                         "direct_llm"))
    assert not out.exists()
    assert not report.exists()
    # explicit synthetic capsule path is resolved and validated upstream
    cap = tmp_path / "direct_capsule.json"
    cap.write_bytes(_fmt_json_bytes(_capsule_doc([], schema=DIRECT_LLM_CAPSULE_SCHEMA, record_count=0)))
    resolved = repair.resolve_capsule_paths(("reference", "direct_llm"),
                                            {"direct_llm": cap})
    assert resolved["direct_llm"] == cap


# ---------------------------------------------------------------------------
# 6) promotion script
# ---------------------------------------------------------------------------


def _sha_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _fake_dev_capsule(tmp_path: Path, *, status="complete", corrupt=None,
                      fake_transport=False, in_doubt_row=False,
                      rows=74) -> Path:
    """A synthetic legal development capsule (all files JSON, byte hashes
    bound to the REAL input pack + preflight report on disk)."""
    cap = tmp_path / "dev_capsule"
    cap.mkdir(parents=True, exist_ok=True)
    input_sha = _sha_file(INPUT_PACK)
    preflight_sha = _sha_file(PREFLIGHT)
    pred_rows = []
    for idx in range(rows):
        sid = f"gdpr_article6_s{idx:03d}"
        act = {"id": "x1", "start": 22, "end": 28}
        pred_rows.append(_ok_record(sid, action_span=act))
    if in_doubt_row:
        pred_rows[3] = _in_doubt_row("gdpr_article6_s003")
    if corrupt == "text":
        act = {"id": "x1", "start": 22, "end": 28}
        pred_rows[0] = _ok_record("gdpr_article6_s000", action_span=act,
                                  corrupt=True)
    if corrupt == "gold":
        pred_rows[0]["record"]["clauses"][0]["expected_violation"] = "x"
    pred_doc = _capsule_doc(pred_rows, schema=DIRECT_LLM_CAPSULE_SCHEMA,
                            record_count=rows)
    if rows != 74:
        pred_doc["record_count"] = rows
    transport = "fake_payload_locked" if fake_transport else "real_authorized"
    telemetry_status = status
    completed = rows if status == "complete" else 73
    telemetry = {
        "schema_version": "gdpr7_direct_llm_telemetry@1.0.0",
        "status": telemetry_status,
        "transport": transport,
        "records_attempted": rows, "records_expected": 74,
        "completed_calls": completed, "in_doubt_calls": 0, "failed_calls": 0,
        "ok_prediction_rows": completed,
        "ledger_path": str(tmp_path / "raw" / "ledger.jsonl"),
        "raw_responses_path": str(tmp_path / "raw" / "raw_responses.jsonl"),
        "text_or_gold_payload_committed": False,
        "fake_run_program_verification_only": fake_transport,
    }
    cost = {
        "schema_version": "gdpr7_direct_llm_cost@1.0.0",
        "status": telemetry_status,
        "llm_calls": rows, "network_calls": 0 if fake_transport else rows,
        "input_tokens_billed": 0, "output_tokens_billed": 0,
        "actual_cost_usd": 0.0, "transport": transport,
        "billing_source": "response_usage",
        "price_snapshot": {"schema_version":
                           "gdpr7_direct_llm_price_snapshot@1.0.0"},
        "caps": {}, "planning_tokens_are_proxy_not_billing": True,
    }
    manifest = {
        "schema_version": "gdpr7_direct_llm_manifest@1.0.0",
        "run_id": "gdpr7_direct_llm_v1", "arm": "direct_llm",
        "status": telemetry_status,
        "dataset_id": "gdpr7_stage2_sentences_v1",
        "arm_capsule": {"path": "data/predictions/gdpr7_direct_llm_v1",
                        "schema": "gdpr7_direct_llm_predictions@1.0.0"},
        "schema": "gdpr7_direct_llm_predictions@1.0.0",
        "input_binding": {"path": "data/input/gdpr7_stage2_input_v1.json",
                          "sha256": input_sha, "records": 74},
        "preflight_binding": {
            "path": str(PREFLIGHT.relative_to(ROOT)).replace("\\", "/"),
            "sha256": preflight_sha},
        "model": {"id": "deepseek-v4-pro",
                  "published_alias": "DeepSeek-V4-Pro-0813"},
        "per_call_status_counts": {"completed": completed,
                                   "in_doubt": 0, "failed": 0},
        "cost_usd": 0.0, "transport": transport,
        "authorization": {"required_event_scope": "gdpr7_direct_llm_v1:74",
                          "real_authorized": not fake_transport},
        "gold_isolation": {"gold_read_by_runner": False,
                           "predictions_locked_before_evaluation": True},
        "outputs": {"capsule_dir": str(cap)},
        "safety": {"llm_api_calls": 0 if fake_transport else rows,
                   "network_calls": 0 if fake_transport else rows,
                   "cost_usd": 0.0, "raw_text_committed": False,
                   "gold_rule_records_created": False,
                   "oracle_started": False},
        "reproduce_command_fake_verify": "python scripts/run_gdpr7_direct_llm_v1.py --fake-transport",
        "reproduce_command_real": "python scripts/run_gdpr7_direct_llm_v1.py --contract-file ... --authorization-file ...",
        "resume_command_fake": "python scripts/run_gdpr7_direct_llm_v1.py --fake-transport --resume",
        "resume_command_real": "python scripts/run_gdpr7_direct_llm_v1.py --contract-file ... --authorization-file ... --resume",
    }
    (cap / "predictions.json").write_bytes(_fmt_json_bytes(pred_doc))
    (cap / "telemetry.json").write_bytes(_fmt_json_bytes(telemetry))
    (cap / "cost.json").write_bytes(_fmt_json_bytes(cost))
    (cap / "manifest.json").write_bytes(_fmt_json_bytes(manifest))
    return cap


def test_promotion_schema_constants_match_executor():
    import run_gdpr7_direct_llm_v1 as ex
    assert promo.PREDICTION_SCHEMA == ex.PREDICTION_SCHEMA
    assert promo.TELEMETRY_SCHEMA == ex.TELEMETRY_SCHEMA
    assert promo.COST_SCHEMA == ex.COST_SCHEMA
    assert promo.MANIFEST_SCHEMA == ex.MANIFEST_SCHEMA
    assert promo.ARM_CAPSULE_REL == str(ex.ARM_CAPSULE_PATH.relative_to(ROOT)
                                        ).replace("\\", "/")


def test_promotion_dry_run_valid_and_apply_succeeds(tmp_path):
    cap = _fake_dev_capsule(tmp_path)
    target = tmp_path / "data_predictions" / "gdpr7_direct_llm_v1"
    plan = promo.plan_promotion(cap, target, PREFLIGHT)
    assert plan["status"] == "pending"
    assert plan["target"]["exists"] is False
    assert plan["validation"]["errors"] == []
    # dry-run wrote nothing
    assert not target.exists()
    applied = promo.publish_promotion(
        cap, target, PREFLIGHT,
        now_utc=datetime.datetime(2026, 9, 7, tzinfo=datetime.timezone.utc))
    assert applied["status"] == "applied_verified"
    for name in ("predictions.json", "telemetry.json", "cost.json",
                 "manifest.json"):
        assert (target / name).is_file()
        assert applied["target"]["verified"][name]["matches"] is True
    assert (target / "promotion_manifest.json").is_file()
    stored = json.loads((target / "promotion_manifest.json").read_text(
        encoding="utf-8"))
    assert stored["schema_version"] == promo.PROMOTION_SCHEMA
    assert stored["safety"]["gold_rule_records_created"] is False
    assert stored["safety"]["oracle_started"] is False
    assert stored["input_binding"]["sha256"] == _sha_file(INPUT_PACK)
    assert any("run_gdpr_3type_linkage_v1.py --arm direct_llm"
               in step for step in stored["next_steps"])
    assert stored["validation"]["checklist"]["telemetry_status"] == "complete"
    # target bytes are byte-identical to the dev capsule files
    for name in ("predictions.json", "telemetry.json", "cost.json",
                 "manifest.json"):
        assert (target / name).read_bytes() == (cap / name).read_bytes()


def test_promotion_rejects_partial_and_in_doubt_with_zero_writes(tmp_path):
    for status in ("partial", "complete_with_explicit_failures"):
        cap = _fake_dev_capsule(tmp_path / f"cap_{status}", status=status)
        target = tmp_path / f"target_{status}"
        with pytest.raises(promo.PromotionError, match="telemetry.status"):
            promo.plan_promotion(cap, target, PREFLIGHT)
        assert not target.exists()
    cap = _fake_dev_capsule(tmp_path / "cap_in_doubt", in_doubt_row=True)
    target = tmp_path / "target_in_doubt"
    with pytest.raises(promo.PromotionError, match="in_doubt/failed"):
        promo.plan_promotion(cap, target, PREFLIGHT)
    assert not target.exists()
    # CLI exit code 2 and no write
    rc = promo.main(["--capsule-dir", str(cap),
                     "--target", str(target), "--apply"])
    assert rc == 2
    assert not target.exists()


def test_promotion_rejects_existing_target(tmp_path):
    cap = _fake_dev_capsule(tmp_path)
    target = tmp_path / "existing"
    target.mkdir()
    (target / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(promo.PromotionError, match="refusing to overwrite"):
        promo.publish_promotion(cap, target, PREFLIGHT)
    assert (target / "keep.txt").read_text(encoding="utf-8") == "x"


def test_promotion_rejects_text_and_gold_leakage(tmp_path):
    for kind in ("text", "gold"):
        cap = _fake_dev_capsule(tmp_path / f"leak_{kind}", corrupt=kind)
        target = tmp_path / f"leak_target_{kind}"
        with pytest.raises(promo.PromotionError, match="containment"):
            promo.plan_promotion(cap, target, PREFLIGHT)
        assert not target.exists()


def test_promotion_rejects_fake_rehearsal_capsule(tmp_path):
    cap = _fake_dev_capsule(tmp_path / "cap_fake", fake_transport=True)
    target = tmp_path / "target_fake"
    with pytest.raises(promo.PromotionError, match="real_authorized"):
        promo.plan_promotion(cap, target, PREFLIGHT)
    assert not target.exists()


def test_promotion_uses_real_preflight_and_input_binding(tmp_path):
    cap = _fake_dev_capsule(tmp_path / "cap_binding")
    # tamper the input pack binding -> refusal (binding is against the real
    # file, so we simulate by rewriting the capsule manifest binding)
    manifest_path = cap / "manifest.json"
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    doc["input_binding"]["sha256"] = "0" * 64
    manifest_path.write_bytes(_fmt_json_bytes(doc))
    with pytest.raises(promo.PromotionError, match="input_binding"):
        promo.plan_promotion(cap, tmp_path / "binding_target", PREFLIGHT)
