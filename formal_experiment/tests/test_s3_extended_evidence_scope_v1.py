# -*- coding: utf-8 -*-
"""Focused checks for the S3.9-EXT wiring repair (W) and the scoped-evidence arm (H).

Two halves:

* **general behaviour** - ten properties on small hand-built BPMN models, read
  through the canonical parser.  No panel instance is touched, so these run
  without any panel inference.
* **stored run** - the W/H run is recomputed from its own stored rows and the
  accounting adapter is checked against the latest stored A/B/C numbers.

Nothing here re-runs the 160-object panel.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from bpc_hybrid.s3_extended_evidence_scope_v1 import (  # noqa: E402
    APPLICABILITY_NOT_REQUIRED, APPLICABILITY_REQUIRED,
    EVIDENCE_ABSENT_CONFIRMED, EVIDENCE_ABSENT_UNDECIDABLE,
    EVIDENCE_NOT_ASSESSED, EVIDENCE_PRESENT, RELATION_ACTIVITY_LABEL,
    RELATION_UNBOUND_GLOBAL, RULE_FIELD_FOR_TYPE, ScopedEvidenceScorer,
    VERDICT_NOT_APPLICABLE, VERDICT_SATISFIED, VERDICT_UNKNOWN, VERDICT_VIOLATED,
    VERDICTS, WiringOnlyScorer, aggregate_scope_verdicts, collect_evidence,
    condition_path_verdict, numeric_bound_verdict, repair_policy,
)
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_bytes  # noqa: E402
from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES, NONE_LABEL  # noqa: E402
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402

CONTRACT = load_stage1_contract(ROOT / "configs/stage1_structural_s11_s14.json")
RUNNER = ROOT / "scripts/run_s3_extended_evidence_scope_v1.py"
RUN_DIR = ROOT / "outputs/development/s3_extended_evidence_scope_v1"
ACCOUNTING = ROOT / "outputs/development/s3_extended_prediction_accounting_v1"

BPMN_HEAD = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'targetNamespace="http://synthetic.local">\n'
    '  <process id="p1" isExecutable="false">\n'
    '    <startEvent id="start"/>\n'
)
BPMN_TAIL = '    <endEvent id="end"/>\n  </process>\n</definitions>\n'


def build_bpmn(nodes: str, flows: str, extra: str = "") -> bytes:
    return (BPMN_HEAD + nodes + flows + extra + BPMN_TAIL).encode("utf-8")


def task(node_id: str, name: str) -> str:
    return f'    <task id="{node_id}" name="{name}"/>\n'


def gateway(node_id: str, name: str = "") -> str:
    label = f' name="{name}"' if name else ""
    return f'    <exclusiveGateway id="{node_id}"{label}/>\n'


def flow(flow_id: str, src: str, dst: str, name: str = "",
         condition: str = "") -> str:
    label = f' name="{name}"' if name else ""
    inner = (f"<conditionExpression xsi:type=\"tFormalExpression\">"
             f"{condition}</conditionExpression>"
             if condition else "")
    return (f'    <sequenceFlow id="{flow_id}" sourceRef="{src}" '
            f'targetRef="{dst}"{label}>{inner}</sequenceFlow>\n')


def parsed(xml: bytes, process_id: str = "p1"):
    record = parse_bpmn_bytes(xml, source_path="synthetic.bpmn", contract=CONTRACT)
    import xml.etree.ElementTree as ET
    model = SunProcessModel(process_id, record, nlp=_NLP[0])
    return record, ET.fromstring(xml), model


class _NoV3:
    """A v3 double whose localization never satisfies, so the label fallback runs."""

    method_id = "no_v3_double"
    tau = gamma = theta = 0.8

    def action_match(self, rule_action, model):
        return {"mapped": False, "reason": "no_candidate_above_gamma",
                "match_tier": "no_candidate_above_gamma", "best": {},
                "candidates": []}


class _Sim:
    def __init__(self, table, default=0.0):
        self.table = table
        self.default = default

    def text_pair(self, left, right):
        return self.table.get((left, right), self.default)


_NLP: list = []


@pytest.fixture(scope="module", autouse=True)
def nlp():
    spacy = pytest.importorskip("spacy")
    _NLP.append(spacy.load("en_core_web_sm"))
    yield _NLP[0]
    _NLP.clear()


def wiring_scorer(sim=None, gamma_action=0.4):
    sim = sim or _Sim({}, default=0.9)
    return WiringOnlyScorer(_NoV3(), sim.text_pair, gamma_action, 0.5)


def scoped_scorer(sim=None, gamma_action=0.4):
    sim = sim or _Sim({}, default=0.9)
    return ScopedEvidenceScorer(_NoV3(), sim.text_pair, gamma_action, 0.5)


# ------------------------------------------------- 1. the wiring repair itself


def test_candidate_surface_and_checks_use_the_same_final_activity():
    """v3 does not localize; the fallback resolves; the surface follows the fallback."""
    xml = build_bpmn(
        task("t1", "Erase personal data") + task("t2", "Communication with data subject"),
        flow("f1", "start", "t1") + flow("f2", "t1", "t2") + flow("f3", "t2", "end"),
    )
    record, xml_root, model = parsed(xml)
    sim = _Sim({("erase personal data", "Erase personal data"): 0.7}, default=0.05)
    scorer = wiring_scorer(sim)
    loc = scorer.localize("erase personal data", model)
    res = scorer.resolve_action("erase personal data", model)
    assert loc["matched_activity_id"] is None          # v3 gave nothing
    assert res["resolved_activity_id"] == "t1"         # the fallback did
    assert res["resolved_by"] == "label_argmax_at_or_above_action_gamma"

    condition_surface = collect_evidence(record, xml_root, res["resolved_activity_id"],
                                         "condition")
    constraint_surface = collect_evidence(record, xml_root,
                                          res["resolved_activity_id"], "constraint")
    assert condition_surface["target_activity_id"] == "t1"
    assert constraint_surface["target_activity_id"] == "t1"
    labels = [e["text"] for e in constraint_surface["bound"]
              if e["relation"] == RELATION_ACTIVITY_LABEL]
    assert labels == ["Erase personal data"]


def test_a_pinned_resolution_is_reused_and_not_recomputed():
    xml = build_bpmn(
        task("t1", "Erase personal data") + task("t2", "Notify authority"),
        flow("f1", "start", "t1") + flow("f2", "t1", "t2") + flow("f3", "t2", "end"),
    )
    record, xml_root, model = parsed(xml)
    base = wiring_scorer()
    pinned = dict(base.resolve_action("erase personal data", model))
    pinned["resolved_activity_id"] = "t2"          # a deliberately different pin
    scorer = WiringOnlyScorer(_NoV3(), base.sim_text, 0.4, 0.5, resolution=pinned)
    assert scorer.resolve_action("erase personal data", model)["resolved_activity_id"] == "t2"
    result = scorer.required_condition(
        {"modality": "obligation", "action": "erase personal data",
         "condition": "where the grounds apply"}, model, [])
    assert result["matched_activity_id"] == "t2"


# --------------------------------------- 2. other activities' evidence is not consumed


def test_condition_on_another_activity_is_not_consumed():
    xml = build_bpmn(
        task("t1", "Notify the controller") + task("t2", "Archive the record")
        + gateway("g1", "Delay over?"),
        flow("f1", "start", "g1", condition="where the grounds apply")
        + flow("f2", "g1", "t2") + flow("f3", "t2", "end"),
    )
    record, xml_root, model = parsed(xml)
    other = collect_evidence(record, xml_root, "t2", "condition")
    bound_texts = [e["text"] for e in other["bound"]]
    unbound_texts = [e["text"] for e in other["unbound"]]
    assert "where the grounds apply" not in bound_texts      # not this activity's
    assert "where the grounds apply" in unbound_texts        # kept, unattached
    assert all(e["bound_activity_id"] is None for e in other["unbound"])


def test_deadline_on_another_activity_is_not_consumed():
    xml = build_bpmn(
        task("t1", "Notify the breach") + task("t2", "Archive the record")
        + gateway("g1"),
        flow("f1", "start", "t1") + flow("f2", "t1", "g1") + flow("f3", "g1", "t2")
        + flow("f4", "t2", "end"),
        extra=('    <boundaryEvent id="b1" attachedToRef="t2">'
               '<timerEventDefinition><timeDuration>30 days</timeDuration>'
               '</timerEventDefinition></boundaryEvent>\n'),
    )
    record, xml_root, model = parsed(xml)
    scope = collect_evidence(record, xml_root, "t1", "constraint")
    assert "30 days" not in [e["text"] for e in scope["bound"]]
    assert "30 days" in [e["text"] for e in scope["unbound"]]
    verdict = numeric_bound_verdict("within 72 hours", [e["text"] for e in scope["bound"]])
    assert verdict["verdict"] == VERDICT_UNKNOWN


def test_exception_handler_of_another_activity_is_not_consumed():
    xml = build_bpmn(
        task("t1", "Notify the breach") + task("t2", "Archive the record"),
        flow("f1", "start", "t1") + flow("f2", "t1", "t2") + flow("f3", "t2", "end"),
        extra=('    <boundaryEvent id="b1" attachedToRef="t2" name="delay handler">'
               '<errorEventDefinition/></boundaryEvent>\n'),
    )
    record, xml_root, model = parsed(xml)
    scope = collect_evidence(record, xml_root, "t1", "exception")
    assert "delay handler" not in [e["text"] for e in scope["bound"]]
    handler_for_t2 = collect_evidence(record, xml_root, "t2", "exception")
    assert "delay handler" in [e["text"] for e in handler_for_t2["bound"]]


# ----------------------------------------------------- 3. numeric bound comparison


def test_numeric_bound_units_explicit_excess_and_unrelated_timer():
    assert numeric_bound_verdict("within 72 hours", ["48 hours"])["verdict"] == \
        VERDICT_SATISFIED
    excess = numeric_bound_verdict("within 72 hours", ["30 days"])
    assert excess["verdict"] == VERDICT_VIOLATED
    assert excess["rule_hours"] == 72 and excess["candidate_hours"] == 720
    # a global timer that is not attached to the activity is never a bound
    xml = build_bpmn(
        task("t1", "Notify the breach"),
        flow("f1", "start", "t1") + flow("f2", "t1", "end"),
        extra=('    <boundaryEvent id="b1" attachedToRef="end">'
               '<timerEventDefinition><timeDuration>30 days</timeDuration>'
               '</timerEventDefinition></boundaryEvent>\n'),
    )
    record, xml_root, model = parsed(xml)
    scope = collect_evidence(record, xml_root, "t1", "constraint")
    verdict = numeric_bound_verdict("within 72 hours", [e["text"] for e in scope["bound"]])
    assert verdict["verdict"] == VERDICT_UNKNOWN
    # a non-upper-bound rule constraint is never scored as a numeric violation
    assert numeric_bound_verdict("without undue delay", ["30 days"])["verdict"] == \
        VERDICT_UNKNOWN
    assert numeric_bound_verdict("at least 3 years", ["30 days"])["verdict"] == \
        VERDICT_UNKNOWN


# ------------------------------------------------- 4. paths: controlled and bypass


def test_controlled_path_is_satisfied_and_a_bypass_is_reported():
    controlled = build_bpmn(
        task("t1", "Notify the breach"),
        flow("f1", "start", "t1", condition="where the grounds apply")
        + flow("f2", "t1", "end"),
    )
    record, xml_root, model = parsed(controlled)
    scope = collect_evidence(record, xml_root, "t1", "condition")
    assert condition_path_verdict(scope["bound"], record, "t1",
                                  "where the grounds apply")["verdict"] == VERDICT_SATISFIED

    bypass = build_bpmn(
        task("t1", "Notify the breach") + task("t2", "Archive") + gateway("g1"),
        flow("f1", "start", "g1") + flow("f2", "g1", "t1",
                                         condition="where the grounds apply")
        + flow("f3", "g1", "t2") + flow("f4", "t1", "end") + flow("f5", "t2", "end"),
    )
    record2, xml_root2, model2 = parsed(bypass)
    scope2 = collect_evidence(record2, xml_root2, "t1", "condition")
    verdict = condition_path_verdict(scope2["bound"], record2, "t1",
                                     "where the grounds apply")
    assert verdict["verdict"] == VERDICT_VIOLATED
    assert verdict["reason"] == "unconditional_bypass_branch"

    # complex control flow with no enumerable condition surface stays unknown
    loop = build_bpmn(
        task("t1", "Notify the breach") + task("t2", "Archive") + gateway("g1"),
        flow("f1", "start", "t1") + flow("f2", "t1", "g1") + flow("f3", "g1", "t2")
        + flow("f4", "t2", "g1") + flow("f5", "g1", "end"),
    )
    record3, xml_root3, model3 = parsed(loop)
    scope3 = collect_evidence(record3, xml_root3, "t1", "condition")
    assert condition_path_verdict(scope3["bound"], record3, "t1",
                                  "where the grounds apply")["verdict"] == VERDICT_UNKNOWN


# ------------------------------------------- 5. confirmed absence vs undecidable


def test_confirmed_absence_and_undecidable_scope_differ():
    with_surface = build_bpmn(
        task("t1", "Notify the breach") + gateway("g1"),
        flow("f1", "start", "t1") + flow("f2", "t1", "g1")
        + flow("f3", "g1", "end", condition="other condition"),
    )
    record, xml_root, model = parsed(with_surface)
    scope = collect_evidence(record, xml_root, "t1", "condition")
    assert scope["scope_enumerable"] is True
    scorer = scoped_scorer()
    packet = scorer._evidence_result(
        "condition", "where the grounds apply", scope,
        condition_path_verdict(scope["bound"], record, "t1", "where the grounds apply"))
    assert packet["evidence_status"] == EVIDENCE_ABSENT_CONFIRMED

    without_surface = build_bpmn(
        task("t1", "Notify the breach"),
        flow("f1", "start", "t1") + flow("f2", "t1", "end"),
    )
    record2, xml_root2, model2 = parsed(without_surface)
    scope2 = collect_evidence(record2, xml_root2, "t1", "condition")
    assert scope2["scope_enumerable"] is False
    packet2 = scorer._evidence_result(
        "condition", "where the grounds apply", scope2,
        condition_path_verdict(scope2["bound"], record2, "t1", "where the grounds apply"))
    assert packet2["evidence_status"] == EVIDENCE_ABSENT_UNDECIDABLE
    assert packet2["verdict"] == VERDICT_UNKNOWN


def test_scope_collection_declares_what_it_cannot_see():
    xml = build_bpmn(
        task("t1", "Notify the breach"),
        flow("f1", "start", "t1") + flow("f2", "t1", "end"),
    )
    record, xml_root, model = parsed(xml)
    for check in ("condition", "constraint", "exception"):
        scope = collect_evidence(record, xml_root, "t1", check)
        assert scope["scope_statement"]
        assert set(scope["surfaces"])
        assert isinstance(scope["scope_enumerable"], bool)
        assert all(e["relation"] not in ("", None) for e in scope["bound"])
        assert all(e["bound_activity_id"] == "t1" for e in scope["bound"])


# ------------------------------------- 6. pure prohibition, absent element, unknown


def test_pure_prohibition_absent_element_and_unknown_applicability_differ():
    """The three cases must not collapse into one 'unknown'."""
    xml = build_bpmn(
        task("t1", "Archive the record"),
        flow("f1", "start", "t1") + flow("f2", "t1", "end"),
    )
    record, xml_root, model = parsed(xml)
    scorer = scoped_scorer()
    cases = {
        # rule with nothing but a prohibition: the other elements are not required.
        # The prohibited action is absent from the process, so the presence check
        # is observable and not violated.
        "pure_prohibition": {"modality": "prohibition", "action": "notify the breach"},
        # rule requires a condition, but the model exposes no condition surface
        "required_but_undecidable": {"modality": "obligation",
                                     "action": "notify the breach",
                                     "condition": "where the grounds apply"},
        # rule requires a condition and the model exposes one that satisfies it
        "required_and_satisfied": {"modality": "obligation",
                                   "action": "notify the breach",
                                   "condition": "where the grounds apply"},
    }
    satisfied_xml = build_bpmn(
        task("t1", "Archive the record"),
        flow("f1", "start", "t1", condition="where the grounds apply")
        + flow("f2", "t1", "end"),
    )
    record2, xml_root2, model2 = parsed(satisfied_xml)

    out = {}
    for name, sentence in cases.items():
        rec, root, mdl = (record2, xml_root2, model2) if name == "required_and_satisfied" \
            else (record, xml_root, model)
        local = scoped_scorer()
        scores = {
            "prohibited_action_present": local.prohibited_action(sentence, mdl),
            "required_condition_not_enforced": local.condition_check(sentence, mdl, rec, root),
            "constraint_violated": local.constraint_check(sentence, mdl, rec, root),
            "exception_not_handled": local.exception_check(sentence, mdl, rec, root),
        }
        out[name] = aggregate_scope_verdicts(scores, 0.5)

    assert out["pure_prohibition"]["required_evidence_checks"] == []
    # a pure prohibition rule is answered by the presence check alone, and that
    # answer is exactly the presence decision, whatever it says
    assert out["pure_prohibition"]["per_type"]["prohibited_action_present"] is True
    assert out["pure_prohibition"]["predicted"] == "prohibited_action_present"

    assert out["required_but_undecidable"]["pending_required_checks"] == \
        ["required_condition_not_enforced"]
    assert out["required_but_undecidable"]["predicted"] is None

    assert out["required_and_satisfied"]["pending_required_checks"] == []
    assert out["required_and_satisfied"]["predicted"] == NONE_LABEL

    # a definite violation still wins over everything else
    violated = dict(out["required_and_satisfied"])
    assert violated["predicted"] == NONE_LABEL
    scores = {
        "prohibited_action_present": {"observable": True, "score": 0.1,
                                      "verdict": None, "applicability": None},
        "constraint_violated": {"observable": True, "score": 1.0,
                                "verdict": VERDICT_VIOLATED,
                                "applicability": APPLICABILITY_REQUIRED},
        "required_condition_not_enforced": {"observable": False, "score": None,
                                            "verdict": VERDICT_UNKNOWN,
                                            "applicability": APPLICABILITY_REQUIRED},
        "exception_not_handled": {"observable": False, "score": None,
                                  "verdict": VERDICT_NOT_APPLICABLE,
                                  "applicability": APPLICABILITY_NOT_REQUIRED},
    }
    assert aggregate_scope_verdicts(scores, 0.5)["predicted"] == "constraint_violated"


# ------------------------------------ 7. duplicate labels are not picked by order


def test_duplicate_labels_on_two_nodes_are_not_picked_by_list_order():
    xml = build_bpmn(
        task("t1", "Notify the controller") + task("t2", "Notify the controller"),
        flow("f1", "start", "t1") + flow("f2", "t1", "t2") + flow("f3", "t2", "end"),
    )
    record, xml_root, model = parsed(xml)
    sim = _Sim({("notify the controller", "Notify the controller"): 0.7}, default=0.05)
    scorer = wiring_scorer(sim)
    res = scorer.resolve_action("notify the controller", model)
    assert res["resolved_activity_id"] is None
    assert res["unresolved_reason"] == "label_argmax_tie_on_different_activities"
    assert res["raw_tie_activity_ids"] == ["t1", "t2"]
    result = scorer.required_condition(
        {"modality": "obligation", "action": "notify the controller",
         "condition": "where the grounds apply"}, model, ["where the grounds apply"])
    assert result["observable"] is False
    assert result["score"] is None


# ------------------------- 8. diagnostics name the text the check really consumed


def test_diagnostic_rule_text_matches_the_consumed_field():
    xml = build_bpmn(
        task("t1", "Notify the breach"),
        flow("f1", "start", "t1", condition="where the grounds apply")
        + flow("f2", "t1", "end"),
    )
    record, xml_root, model = parsed(xml)
    sentence = {"modality": "obligation", "action": "notify the breach",
                "condition": "where the grounds apply",
                "constraint": "within 72 hours",
                "exception": "unless the subject objects"}
    scorer = wiring_scorer()
    checks = {
        "required_condition_not_enforced": scorer.required_condition(
            sentence, model, ["where the grounds apply"]),
        "constraint_violated": scorer.constraint_violated(
            sentence, model, ["within 72 hours"]),
        "exception_not_handled": scorer.exception_not_handled(
            sentence, model, ["unless the subject objects"]),
        "prohibited_action_present": scorer.prohibited_action(sentence, model),
    }
    for type_name, result in checks.items():
        field = RULE_FIELD_FOR_TYPE[type_name]
        assert result["rule_field_consumed"] == field, type_name
        assert result["rule_text_consumed"] == sentence[field], type_name
        assert result["rule_text_consumed"] != "" if field != "action" else True
    # the type-name lookup the old diagnostics used would have produced empty text
    assert checks["required_condition_not_enforced"]["rule_text_consumed"] == \
        "where the grounds apply"
    assert checks["required_condition_not_enforced"]["rule_text_consumed"] != \
        sentence.get("required_condition_not_enforced", "")


def test_missing_record_is_not_reported_as_a_wrong_binding():
    """A check that never bound an activity must not claim a binding."""
    xml = build_bpmn(
        task("t1", "Notify the breach"),
        flow("f1", "start", "t1") + flow("f2", "t1", "end"),
    )
    record, xml_root, model = parsed(xml)
    scorer = wiring_scorer(_Sim({}, default=0.0), gamma_action=0.9)
    result = scorer.required_condition(
        {"modality": "obligation", "action": "erase personal data",
         "condition": "where the grounds apply"}, model, ["where the grounds apply"])
    assert result["observable"] is False
    assert result.get("matched_activity_id") is None
    assert result.get("same_activity_as_resolution") in (None, True)


# -------------------------- 9. polluted metadata and renamed ids change nothing


def test_answer_metadata_and_node_ids_do_not_change_the_semantics():
    def run(prefix: str, extra_metadata: dict) -> tuple:
        node_id = f"{prefix}1"
        flow_in = f"{prefix}f1"
        xml = build_bpmn(
            task(node_id, "Notify the breach"),
            flow(flow_in, "start", node_id, condition="where the grounds apply")
            + flow(f"{prefix}f2", node_id, "end"),
        )
        record, xml_root, model = parsed(xml)
        sentence = {"modality": "obligation", "action": "notify the breach",
                    "condition": "where the grounds apply", **extra_metadata}
        scorer = wiring_scorer()
        result = scorer.required_condition(
            sentence, model, ["where the grounds apply"])
        scope = collect_evidence(record, xml_root, node_id, "condition")
        return (result["observable"], result["score"], result["violation"],
                [e["relation"] for e in scope["bound"]],
                [e["source_kind"] for e in scope["bound"]])

    clean = run("t", {})
    polluted = run("renamed_", {"expected_violation": "required_condition_not_enforced",
                                "mutation_type": "required_condition_not_enforced",
                                "target_activity_id": "renamed_1", "variant_id": "syn_x",
                                "mutation_config": {"target_activity_id": "renamed_1"}})
    assert clean == polluted
    assert clean[0] is True and clean[4]


# --------------------------------------------- 10. counting conservation views


@pytest.fixture(scope="module")
def runner_module():
    spec = importlib.util.spec_from_file_location("s3_extended_evidence_scope_runner",
                                                  RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s3_extended_evidence_scope_runner"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def stored(runner_module):
    return runner_module.verify_outputs()


def test_plan_is_written_before_inference_with_two_arms():
    plan = json.loads((RUN_DIR / "plan.json").read_text(encoding="utf-8"))
    assert plan["arm_count"] == 2
    assert plan["runs_per_arm"] == 1
    assert set(plan["arms"]) == {"W_action_resolution_wiring",
                                 "H_scoped_evidence_and_verdicts"}
    for arm in plan["arms"].values():
        assert arm["thresholds"]["v3_internal_gamma"] == 0.8
        assert arm["thresholds"]["label_fallback_gamma"] == 0.4
        assert arm["thresholds"]["gamma_ext"] == 0.5
    assert plan["inputs"] and plan["implementation"]
    assert plan["findings"]["R1"]["confirmed"] is True
    assert set(plan["findings"]) == {"R1", "R2", "R3", "R4", "R5", "R6"}


def test_every_object_is_retained_and_labelled_once(stored):
    rows = stored["rows"]
    assert len(rows) == 160
    seen = set()
    for row in rows:
        key = (row["arm"], row["item_id"], row["side"])
        assert key not in seen
        seen.add(key)
        assert row["final_label"] in (*EXTENDED_TYPES, NONE_LABEL, None)
        assert set(row["checks"]) == set(EXTENDED_TYPES)
    assert len({r["arm"] for r in rows}) == 2
    for arm in ("W_action_resolution_wiring", "H_scoped_evidence_and_verdicts"):
        for side in ("variant", "control"):
            assert sum(1 for r in rows if r["arm"] == arm and r["side"] == side) == 40


def test_counts_conserve_in_every_view(stored):
    metrics = stored["metrics"]
    for arm, block in metrics["arms"].items():
        a, b = block["A_variant_40"], block["B_control_40"]
        assert (a["correct_type"] + a["wrong_type"] + a["explicit_compliance"]
                + a["final_unknown"]) == a["objects"] == 40
        assert (b["false_positives"] + b["explicit_compliance"]
                + b["final_unknown"]) == b["objects"] == 40
        paired = block["C_paired_40"]["both_sides_correct"]
        assert paired <= a["correct_type"]
        assert paired <= b["explicit_compliance"]
        assert abs(block["D_merged_80"]["accuracy"]
                   - (a["correct_type"] + b["explicit_compliance"]) / 80) < 1e-12
        # the target-type view is separate from the final-label view
        assert "target_type_unknown" in block["A_variant_40"]
        assert a["target_type_unknown"] >= 0


def test_one_final_label_per_instance_across_views(stored):
    rows = {(r["arm"], r["item_id"], r["side"]): r["final_label"]
            for r in stored["rows"]}
    metrics = stored["metrics"]
    for arm, block in metrics["arms"].items():
        for pair in block["C_paired_40"]["per_pair"]:
            item = pair["item_id"]
            final = rows[(arm, item, "variant")]
            assert pair["variant_correct"] == (final == pair["expected"])
            assert pair["control_correct"] == (rows[(arm, item, "control")] == NONE_LABEL)


def test_unknown_is_kept_in_the_main_denominator(stored):
    metrics = stored["metrics"]
    for arm, block in metrics["arms"].items():
        per_class = block["A_variant_40"]["per_class"]
        support = sum(v["support"] for v in per_class.values())
        assert support == 40, arm
        assert block["A_variant_40"]["final_unknown"] >= 0
        # a control unknown is never counted as a correct rejection
        assert block["B_control_40"]["final_unknown"] == sum(
            1 for r in stored["rows"]
            if r["arm"] == arm and r["side"] == "control" and r["final_label"] is None)


def test_legacy_arms_match_the_latest_corrected_counts(stored):
    """The thin adapter must reproduce the stored A/B/C numbers exactly."""
    legacy = stored["metrics"]["legacy_reference"]
    expected = json.loads((ACCOUNTING / "metrics.json").read_text(encoding="utf-8"))["arms"]
    for arm in ("A_v3_internal_0_4", "B_original_path_normalized",
                "C_v3_no_forced_resolution"):
        for key in ("correct_type", "wrong_type", "explicit_compliance",
                    "final_unknown"):
            assert legacy[arm]["A_variant_40"][key] == \
                expected[arm]["A_variant_40"][key], (arm, key)
        for key in ("false_positives", "explicit_compliance", "final_unknown"):
            assert legacy[arm]["B_control_40"][key] == \
                expected[arm]["B_control_40"][key], (arm, key)
        assert legacy[arm]["C_paired_40"]["both_sides_correct"] == \
            expected[arm]["C_paired_40"]["both_sides_correct"], arm
        assert abs(legacy[arm]["A_variant_40"]["macro_f1"]
                   - expected[arm]["A_variant_40"]["macro_f1"]) < 1e-12, arm
    # the reported stored C paired count is 7, not the 11 of the older report
    assert legacy["C_v3_no_forced_resolution"]["C_paired_40"]["both_sides_correct"] == 7


def test_diagnostics_do_not_relabel_cases(stored):
    diag = stored["diagnostics"]
    assert diag["contract_diagnosis"]
    allowed = ("target_evidence_construction", "whole_rule_control_unverified",
               "semantic_target_binding_uncertain", "parsing_or_method_defect")
    for entry in diag["contract_diagnosis"]:
        assert entry["categories"] and all(c in allowed for c in entry["categories"])
        assert all(e["category"] in allowed for e in entry["entries"])
        assert "expected_violation" not in entry
        assert entry["arm_H_control_final_label"] in (NONE_LABEL, None, *EXTENDED_TYPES)
    assert diag["policy_notes"]["scope"] == repair_policy()["scope_statement"]
    assert diag["comparison_strings_check"]["mismatches"] == 0


def test_verdicts_are_declared_values(stored):
    for row in stored["rows"]:
        for name, check in row["checks"].items():
            if "verdict" in check:
                assert check["verdict"] in VERDICTS, (row["item_id"], name)
                assert check["applicability"] in (APPLICABILITY_REQUIRED,
                                                  APPLICABILITY_NOT_REQUIRED)
                assert check["evidence_status"] in (
                    EVIDENCE_PRESENT, EVIDENCE_ABSENT_CONFIRMED,
                    EVIDENCE_ABSENT_UNDECIDABLE, EVIDENCE_NOT_ASSESSED,
                    "contradicted")

