"""Independent counterexamples for the three diagnosed Stage-3 defects."""
import copy
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from bpc_hybrid.sun_stage3.sun_scorer import SunScorer
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel
from bpc_hybrid.stage3_extended_violations import (
    EXTENDED_TYPES, ConstraintSurface, ExtendedViolationScorer,
    constraint_candidates, detect_exact_constraint_contradiction, evaluate_paired,
)
from bpc_hybrid.s3_extended_unified import unified_rows
from reevaluate_s3_extended_unified_v1 import confusion_matrix


def exact(a, b):
    return float(a == b)


def test_unrelated_actor_does_not_change_sun_def6():
    model = SimpleNamespace(
        actions=[{"id": "a", "name": "Review"}, {"id": "b", "name": "File"}],
        actors=["Manager", "Clerk"], business_objects=[],
        action_actor_names={"a": ["Manager"], "b": ["Clerk"]})
    scorer = SunScorer(SimpleNamespace(text_pair=exact), .8, .8, .8)
    assert scorer.incorrect_actor(["Review"], ["Manager"], model)["score"] == 0
    model.action_actor_names["a"].append("Clerk")
    # Sun's existential comparison is preserved for genuinely related actors.
    assert scorer.incorrect_actor(["Review"], ["Manager"], model)["score"] == 1


def test_rule_relation_is_required_and_filters_r():
    model = SimpleNamespace(actions=[{"id": "a", "name": "Review"}],
                            actors=["Manager"], business_objects=[],
                            action_actor_names={"a": ["Manager"]})
    scorer = SunScorer(SimpleNamespace(text_pair=exact), .8, .8, .8)
    assert not scorer.incorrect_actor(["Review", "File"], ["Manager", "Clerk"], model)["observable"]
    result = scorer.incorrect_actor(["Review", "File"], ["Manager", "Clerk"], model,
        [{"actor": "Manager", "action": "Review"}, {"actor": "Clerk", "action": "File"}])
    assert result["denominator"] == 1 and result["score"] == 0


def test_lane_ownership_and_unrelated_pool():
    record = {"process_id": "p", "activities": [{"id": "a", "name": "Review"},
              {"id": "b", "name": "File"}], "events": [],
              "pools": [{"name": "Other company", "process_ref": "other"}],
              "lanes": [{"name": "Manager", "flow_node_refs": ["a"]},
                        {"name": "Clerk", "flow_node_refs": ["b"]}]}
    model = SunProcessModel("p", record, lambda text: [])
    assert model.action_actor_names == {"a": ["Manager"], "b": ["Clerk"]}


def test_numeric_scope_upper_bound_and_mapping():
    scorer = ExtendedViolationScorer(exact, exact, .8)
    model = SimpleNamespace(actions=[{"id": "a", "name": "Notify"}])
    sentence = {"action": "Notify", "constraint": "within 72 hours"}
    bound = ConstraintSurface(["7 days"], ["7 days"], "a")
    assert scorer.constraint_violated(sentence, model, bound)["exact_contradiction"]["contradiction"]
    assert not scorer.constraint_violated(sentence, model, ["7 days"])["exact_contradiction"]["contradiction"]
    unmapped = scorer.constraint_violated(dict(sentence, action="Archive"), model, bound)
    assert not unmapped["observable"] and unmapped["score"] is None
    conditional = scorer.constraint_violated(dict(sentence,
        condition="Where notification is not made within 72 hours"), model, bound)
    assert conditional["exact_contradiction"]["reason"] == "time_bound_inside_condition"
    assert not detect_exact_constraint_contradiction("at least 72 hours", ["96 hours"])["contradiction"]
    assert not detect_exact_constraint_contradiction("within 72 hours", ["24 hours"])["contradiction"]


def test_numeric_surface_does_not_borrow_unrelated_timer():
    record = {"activities": [{"id": "a", "name": "Notify"}, {"id": "b", "name": "Archive"}]}
    xml = ET.fromstring('<process><boundaryEvent id="t" name="7 days" attachedToRef="b"/></process>')
    surface = constraint_candidates(record, xml, "a")
    assert "7 days" in surface and "7 days" not in surface.bound_texts


def _rows(value):
    panel = json.loads((ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json").read_text(encoding="utf-8"))
    rows = []
    for v in panel["variants"]:
        entry = {"score": value, "observable": value is not None, "reason": None}
        rows.append({"item_id": v["variant_id"], "expected_violation": v["expected_violation"],
            "predicted_violation_type": None, "scores": {t: value for t in EXTENDED_TYPES},
            "scores_detail": {t: {} for t in EXTENDED_TYPES},
            "observability": {t: copy.deepcopy(entry) for t in EXTENDED_TYPES},
            "control_scores": {t: copy.deepcopy(entry) for t in EXTENDED_TYPES}})
    return unified_rows(rows), panel


def test_all_false_compliant_answers_count_in_confusion():
    rows, panel = _rows(0)
    paired = evaluate_paired(rows, panel)
    none = paired["per_type"]["none"]
    assert (none["tp"], none["fp"], none["fn"]) == (40, 40, 0)
    assert none["precision"] == .5
    cm = confusion_matrix(rows, {}, .5, panel)
    assert cm["per_class"] == paired["per_type"]
    assert sum(sum(row.values()) for row in cm["matrix"].values()) == 80


def test_abstentions_stay_in_each_gold_class_denominator():
    rows, panel = _rows(None)
    cm = confusion_matrix(rows, {}, .5, panel)
    assert cm["per_class"]["none"]["fn"] == 40
    for t in EXTENDED_TYPES:
        assert cm["per_class"][t]["fn"] == 10
        assert cm["matrix"][t]["unobservable"] == 10


def test_capsule_preserves_actor_and_order_links():
    from bpc_hybrid.sun_stage3.gdpr_capsule_converter import build_rule_records, CAPSULE_SCHEMA
    capsule = {"schema_version": CAPSULE_SCHEMA, "records": [{
        "sample_id": "gdpr_article6_s001", "request_status": "ok", "record": {"clauses": [{
            "modality": {"label": "obligation"},
            "actors": [{"id": "r", "start": 0, "end": 7}],
            "actions": [{"id": "a", "start": 8, "end": 14}, {"id": "b", "start": 15, "end": 19}],
            "actor_action_map": [{"actor_id": "r", "action_id": "a"}],
            "order_relations": [{"before_action_id": "a", "after_action_id": "b"}]}]}}]}
    records, diag = build_rule_records(capsule, {"gdpr_article6_s001": "Manager Review File"}, ["article6"])
    assert records["article6"]["actor_action_pairs"] == [{"actor": "Manager", "action": "Review"}]
    assert records["article6"]["order_relations"] == [("Review", "File")]
    assert diag["total_invalid_spans"] == 0


# Declared implementation drift for the s3_formula_repair_v2 evidence capsule
# (2026-09-08 Task D / paper wind-down): the five paths below were changed by
# the authorized Direct-LLM Stage-3 linkage task (schema parameterization,
# third-source support, machine change-reason classifier, promotion chain).
# Capsule-lifecycle semantics: the historical evidence keeps its byte-exact
# artifacts and remains authoritative for its numbers; its implementation
# binding is superseded by the successor official repair run (to be executed
# with --sources ... direct_llm after the real API capsule is promoted), which
# will re-baseline this manifest and test.  Any drift OUTSIDE this declared
# set is still a hard failure.
_DECLARED_REPAIR_V2_IMPL_DRIFT = frozenset({
    "scripts/run_s3_formula_repair_v2.py",
    "src/bpc_hybrid/sun_stage3/gdpr_capsule_converter.py",
    "scripts/run_gdpr_3type_linkage_v1.py",
    "scripts/run_gdpr_s2_s3_linkage_v1.py",
    "scripts/reevaluate_s3_extended_unified_v1.py",
})


def test_repair_run_artifacts_and_sources_are_bound():
    manifest = json.loads((ROOT / "outputs/evidence/s3_formula_repair_v2/manifest.json").read_text(encoding="utf-8"))
    for section in ("inputs", "artifacts"):
        for name, expected in manifest[section].items():
            data = (ROOT / name).read_bytes()
            assert hashlib.sha256(data).hexdigest() == expected, name
    drifted = []
    for name, expected in manifest["implementation_hashes"].items():
        data = (ROOT / name).read_bytes()
        data = data.replace(b"\r\n", b"\n")
        if hashlib.sha256(data).hexdigest() != expected:
            drifted.append(str(Path(name)).replace("\\", "/"))
    expected_drift = {p.replace("\\", "/") for p in _DECLARED_REPAIR_V2_IMPL_DRIFT}
    unexpected = sorted(set(drifted) - expected_drift)
    assert not unexpected, f"undeclared implementation drift: {unexpected}"
    assert set(drifted) == expected_drift, (
        "expected exactly the declared Task-D drift set, got "
        f"{sorted(set(drifted))}"
    )
    report_info = manifest["report"]
    assert hashlib.sha256((ROOT / report_info["path"]).read_bytes()).hexdigest() == report_info["sha256"]
    assert manifest["safety"]["api_calls"] == 0
