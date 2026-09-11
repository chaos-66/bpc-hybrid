# -*- coding: utf-8 -*-
"""S3.9-EXT limited repair (v3): one action resolution, sourced evidence, four verdicts.

This module implements exactly two pre-declared arms of the current batch.  It
changes **only** the evidence handling of the four-type extension; the rule
input, the action resolution rule, the thresholds and the type priority are the
ones already measured in ``s3_extended_repair_v2_v1``.

W - wiring only
---------------
The batch that produced ``outputs/development/s3_extended_repair_v2_v1`` built
its candidate surfaces in the runner from ``localize().matched_activity_id``
while the checks themselves called ``resolve_action()`` internally.  The two can
disagree: whenever v3 does not return a satisfying match, the first is ``None``
while the second may fall back to the label argmax.  Measured read-only on that
arm's own scorer over the 80 side-instances: **45 of 80** side-instances built
their surfaces with ``None`` while the checks consumed an activity
(19 variant + 26 control).  W removes that split: one ``resolve_action()`` result
is computed once and is the single source for the candidate surfaces, the
evidence checks, the numeric-contradiction gate and the recorded fields.  No
semantic gate, no scope restriction, no change to the empty-candidate meaning
and no change to the aggregation.

H - evidence scope and evidence judgement (on top of W)
-------------------------------------------------------
Only the following is added; the rule input, the action resolution rule and every
threshold are identical to W:

* candidates carry their **source** (node / flow id, text, relation type, bound
  activity id) instead of a deduplicated string list;
* evidence is **scoped**: condition evidence comes from the target activity's
  incoming flows, flow conditions and control gateways; constraint evidence from
  data / annotations / boundary timers associated with the target activity;
  exception evidence from handlers that are structurally attached to the target
  activity.  Un-associated data objects and globally owned timers stay unbound
  candidates and are never attached to a target activity;
* every check reports ``applicability``, ``evidence_status``, ``verdict`` and
  ``reason`` with the four outcomes ``satisfied / violated / unknown /
  not_applicable``.  "The rule does not require this element" and "the rule
  requires it but it cannot be checked" are different outcomes;
* the finite structural checks below are the only ones that may return a
  definite verdict; everything else stays ``unknown``.

What this module does not do: it does not rewrite the frozen six-element
extractor, so a frozen ``shall not apply ...`` reading stays as extracted and is
recorded as an upstream-input problem; it adds no article numbers, sample ids,
synonym lists or case whitelists; it never derives the expected answer from
``mutation_type``, ``expected_violation`` or ``target_activity_id``.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence

from bpc_hybrid.s3_extended_v3_repair_v2 import (  # noqa: E402
    RESOLVED_BY_ACTION_GAMMA, RESOLVED_BY_V3_MATCH, RepairedExtendedScorerV2,
    fold_whitespace,
)
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES, NONE_LABEL, _LOCAL, _TIME_VALUE_RE, _UNIT_HOURS,
)

WIRING_REPAIR_ID = "s3_extended_evidence_wiring@1.0.0"
EVIDENCE_SCOPE_ID = "s3_extended_evidence_scope@1.0.0"

# one rule element per check; the diagnostic mapping is NOT the type name
RULE_FIELD_FOR_TYPE = {
    "prohibited_action_present": "action",
    "required_condition_not_enforced": "condition",
    "constraint_violated": "constraint",
    "exception_not_handled": "exception",
}

VERDICT_SATISFIED = "satisfied"
VERDICT_VIOLATED = "violated"
VERDICT_UNKNOWN = "unknown"
VERDICT_NOT_APPLICABLE = "not_applicable"
VERDICTS = (VERDICT_SATISFIED, VERDICT_VIOLATED, VERDICT_UNKNOWN,
            VERDICT_NOT_APPLICABLE)

APPLICABILITY_REQUIRED = "required"
APPLICABILITY_NOT_REQUIRED = "not_required"

EVIDENCE_PRESENT = "present"
EVIDENCE_ABSENT_CONFIRMED = "absent_in_declared_scope"
EVIDENCE_ABSENT_UNDECIDABLE = "absent_and_undecidable"
EVIDENCE_NOT_ASSESSED = "not_assessed"
EVIDENCE_CONTRADICTED = "contradicted"

# relation of one candidate to the target activity
RELATION_ACTIVITY_LABEL = "activity_label"
RELATION_INCOMING_FLOW = "incoming_flow"
RELATION_OUTGOING_FLOW = "outgoing_flow"
RELATION_SAME_BRANCH_FLOW = "same_branch_flow"
RELATION_GATEWAY = "control_gateway"
RELATION_BOUND_BOUNDARY_EVENT = "bound_boundary_event"
RELATION_BOUND_ANNOTATION = "bound_boundary_annotation"
RELATION_ASSOCIATED_DATA = "associated_data"
RELATION_UNBOUND_GLOBAL = "unbound_global"

UNBOUND_RELATIONS = frozenset({RELATION_UNBOUND_GLOBAL})


def repair_policy() -> dict[str, Any]:
    """The frozen policy of this batch, for plan.json and the manifest."""
    return {
        "arms": {
            "W_action_resolution_wiring": {
                "id": WIRING_REPAIR_ID,
                "base": "outputs/development/s3_extended_repair_v2_v1 arm C",
                "thresholds": {"v3_internal_gamma": 0.8, "tau": 0.8, "theta": 0.8,
                               "label_fallback_gamma": 0.4, "gamma_ext": 0.5},
                "change": ("one resolve_action() result is consumed by the candidate "
                           "surfaces, the evidence checks, the numeric gate and the "
                           "recorded fields"),
                "unchanged": ["formulas", "action interpretation", "type priority",
                              "comparison gate aggregation", "empty-candidate meaning",
                              "candidate scope (still graph-wide)"],
                "diagnostics_fix": ("comparison_strings uses the element-to-field "
                                    "mapping; it does not affect any prediction"),
            },
            "H_scoped_evidence_and_verdicts": {
                "id": EVIDENCE_SCOPE_ID,
                "base": "arm W",
                "thresholds": {"v3_internal_gamma": 0.8, "tau": 0.8, "theta": 0.8,
                               "label_fallback_gamma": 0.4, "gamma_ext": 0.5},
                "added": [
                    "candidates carry source id, text, relation type and bound activity",
                    "evidence is scoped to the target activity; unbound evidence is not "
                    "attached",
                    "four outcomes satisfied / violated / unknown / not_applicable with "
                    "separate applicability and evidence_status",
                    "finite structural checks only for definite verdicts",
                ],
                "not_done": [
                    "no rewrite of the frozen six-element extractor (a frozen "
                    "'shall not apply' reading stays as extracted)",
                    "no article number, sample id, synonym list or whitelist",
                    "no change to the rule input, the action resolution rule or any "
                    "threshold",
                ],
                "aggregation": ("violated wins by the unchanged type priority; otherwise "
                                "'none' only when every check that is required and "
                                "checkable is satisfied; any required check still unknown "
                                "keeps the row unknown.  The prohibition presence check is "
                                "not required to have run for a pure prohibition rule.  "
                                "'none' means compliant within the declared evidence "
                                "scope, not that the whole process passed every legal "
                                "requirement."),
            },
        },
        "scope_statement": ("development regression on a panel already used for repeated "
                            "development; not an independent validation, not the formal "
                            "Oracle and not real legal compliance performance"),
    }


# --------------------------------------------------------------------------- evidence


class Evidence(dict):
    """One candidate piece of evidence with its provenance."""

    __slots__ = ()


def _evidence(text: str, relation: str, source_id: str | None,
              bound_activity_id: str | None, source_kind: str) -> Evidence:
    return Evidence(text=text, text_folded=fold_whitespace(text), relation=relation,
                    source_id=source_id, bound_activity_id=bound_activity_id,
                    source_kind=source_kind, bound=relation not in UNBOUND_RELATIONS)


def _dedup_evidence(items: Iterable[Evidence]) -> list[Evidence]:
    seen, out = set(), []
    for item in items:
        key = (item["relation"], item["source_id"], item["text"])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _activity_by_id(record: Mapping[str, Any], activity_id: str | None):
    if activity_id is None:
        return None
    for act in record.get("activities", []):
        if act["id"] == activity_id:
            return act
    return None


def _flow_endpoint_names(record: Mapping[str, Any], flow: Mapping[str, Any],
                         other: str) -> str:
    for node in list(record.get("activities", [])) + list(record.get("events", [])) \
            + list(record.get("gateways", [])):
        if node["id"] == other:
            return (node.get("name") or "").strip()
    return ""


def collect_evidence(record: Mapping[str, Any], xml_root: Any,
                     activity_id: str | None, check: str) -> dict[str, Any]:
    """Sourced evidence for one check, with an explicit scope statement.

    ``check`` is one of ``condition``, ``constraint``, ``exception``.  The
    returned dict separates bound candidates (structurally tied to the target
    activity) from unbound candidates (graph-wide text that cannot be attributed
    to it), and states whether the declared scope could be enumerated at all.
    """
    bound: list[Evidence] = []
    unbound: list[Evidence] = []
    surfaces = {"gateways": 0, "flows_with_condition": 0, "boundary_events": 0,
                "bound_annotations": 0, "associated_data": 0, "attached_handlers": 0,
                "same_branch_tasks": 0, "global_timers": 0}
    target = _activity_by_id(record, activity_id)

    if target is not None and (target.get("name") or "").strip():
        bound.append(_evidence(target["name"].strip(), RELATION_ACTIVITY_LABEL,
                               activity_id, activity_id, "activity"))

    flows = list(record.get("sequence_flows", []))
    gateway_ids = {g["id"] for g in record.get("gateways", [])}
    incoming = [f for f in flows if f["target_ref"] == activity_id]
    outgoing = [f for f in flows if f["source_ref"] == activity_id]

    if check == "condition":
        for flow in incoming:
            if (flow.get("condition_expression") or "").strip():
                surfaces["flows_with_condition"] += 1
                bound.append(_evidence(flow["condition_expression"],
                                       RELATION_INCOMING_FLOW, flow["id"], activity_id,
                                       "sequence_flow_condition"))
            for endpoint in (flow["source_ref"],):
                if endpoint in gateway_ids:
                    name = _flow_endpoint_names(record, flow, endpoint)
                    if name:
                        surfaces["gateways"] += 1
                        bound.append(_evidence(name, RELATION_GATEWAY, endpoint,
                                               activity_id, "gateway"))
        # same-branch control flow: targets reachable through a branch gateway that
        # the activity itself enters
        branch_sources = {f["source_ref"] for f in incoming if f["source_ref"] in gateway_ids}
        for flow in flows:
            if flow["source_ref"] in branch_sources and flow["target_ref"] != activity_id:
                if (flow.get("condition_expression") or "").strip():
                    bound.append(_evidence(flow["condition_expression"],
                                           RELATION_SAME_BRANCH_FLOW, flow["id"],
                                           activity_id, "sequence_flow_condition"))
                if (flow.get("name") or "").strip():
                    bound.append(_evidence(flow["name"], RELATION_SAME_BRANCH_FLOW,
                                           flow["id"], activity_id, "sequence_flow_label"))
        for flow in flows:
            if flow["id"] in {f["id"] for f in incoming + outgoing}:
                continue
            if (flow.get("condition_expression") or "").strip():
                surfaces["flows_with_condition"] += 1
                unbound.append(_evidence(flow["condition_expression"],
                                         RELATION_UNBOUND_GLOBAL, flow["id"], None,
                                         "sequence_flow_condition"))
        for gateway in record.get("gateways", []):
            name = (gateway.get("name") or "").strip()
            if name:
                unbound.append(_evidence(name, RELATION_UNBOUND_GLOBAL, gateway["id"],
                                         None, "gateway"))
        enumerable = surfaces["gateways"] + surfaces["flows_with_condition"] > 0

    elif check == "constraint":
        elements = {e.get("id"): e for e in xml_root.iter() if e.get("id")}
        for el in xml_root.iter():
            kind = _LOCAL(el.tag)
            if kind == "boundaryEvent" and el.get("attachedToRef") == activity_id:
                surfaces["boundary_events"] += 1
                for name in _named(el):
                    bound.append(_evidence(name, RELATION_BOUND_BOUNDARY_EVENT,
                                           el.get("id"), activity_id, "boundary_event"))
            if kind == "association":
                ends = (el.get("sourceRef"), el.get("targetRef"))
                if activity_id in ends:
                    other = ends[1] if ends[0] == activity_id else ends[0]
                    node = elements.get(other)
                    if node is not None and _LOCAL(node.tag) == "textAnnotation":
                        surfaces["bound_annotations"] += 1
                        for name in _named(node):
                            bound.append(_evidence(name, RELATION_BOUND_ANNOTATION,
                                                   node.get("id"), activity_id,
                                                   "text_annotation"))
            if kind in ("dataObjectReference", "dataStoreReference", "dataObject",
                        "dataStore"):
                refs = {el.get("sourceRef"), el.get("targetRef"),
                        el.get("dataObjectRef"), el.get("dataStoreRef")}
                if activity_id in refs:
                    surfaces["associated_data"] += 1
                    for name in _named(el):
                        bound.append(_evidence(name, RELATION_ASSOCIATED_DATA,
                                               el.get("id"), activity_id, "data_object"))
        for el in xml_root.iter():
            if _LOCAL(el.tag) in ("timerEventDefinition", "timeDate", "timeDuration",
                                  "timeCycle"):
                owner = _owning_node_id(xml_root, el)
                texts = _named(el)
                if owner == activity_id:
                    surfaces["boundary_events"] += 1
                    for name in texts:
                        bound.append(_evidence(name, RELATION_BOUND_BOUNDARY_EVENT,
                                               owner, activity_id, "timer_definition"))
                else:
                    surfaces["global_timers"] += 1
                    for name in texts:
                        unbound.append(_evidence(name, RELATION_UNBOUND_GLOBAL, owner,
                                                 None, "timer_definition"))
        enumerable = (surfaces["boundary_events"] + surfaces["bound_annotations"]
                      + surfaces["associated_data"]) > 0

    elif check == "exception":
        for el in xml_root.iter():
            kind = _LOCAL(el.tag)
            if kind == "boundaryEvent" and el.get("attachedToRef") == activity_id:
                surfaces["boundary_events"] += 1
                surfaces["attached_handlers"] += 1
                for name in _named(el):
                    bound.append(_evidence(name, RELATION_BOUND_BOUNDARY_EVENT,
                                           el.get("id"), activity_id, "boundary_event"))
            if kind in ("error", "escalation"):
                owner = _owning_node_id(xml_root, el)
                if owner == activity_id:
                    bound.append(_evidence(f"{kind} {el.get('errorCode') or ''}".strip(),
                                           RELATION_BOUND_BOUNDARY_EVENT, owner,
                                           activity_id, kind))
                else:
                    texts = _named(el) or [kind]
                    for name in texts:
                        unbound.append(_evidence(name, RELATION_UNBOUND_GLOBAL, owner,
                                                 None, kind))
        # an alternate branch out of a gateway the target activity's outgoing flow reaches
        gateway_out: dict[str, list[dict]] = {}
        for flow in flows:
            if flow["source_ref"] in gateway_ids:
                gateway_out.setdefault(flow["source_ref"], []).append(flow)
        reachable_gateways = {f["target_ref"] for f in outgoing if f["target_ref"] in gateway_ids}
        for gateway_id in reachable_gateways:
            branches = gateway_out.get(gateway_id, [])
            if len(branches) <= 1:
                continue
            for flow in branches:
                name = (flow.get("name") or "").strip()
                if not name:
                    continue
                surfaces["same_branch_tasks"] += 1
                bound.append(_evidence(name, RELATION_SAME_BRANCH_FLOW, flow["id"],
                                       activity_id, "alternate_branch"))
        enumerable = (surfaces["boundary_events"] + surfaces["attached_handlers"]
                      + surfaces["same_branch_tasks"]) > 0
    else:
        raise ValueError(f"unknown check: {check}")

    return {
        "check": check,
        "target_activity_id": activity_id,
        "target_activity_found": target is not None,
        "bound": _dedup_evidence(bound),
        "unbound": _dedup_evidence(unbound),
        "surfaces": surfaces,
        "scope_enumerable": bool(enumerable),
        "scope_statement": _scope_statement(check),
    }


def _scope_statement(check: str) -> str:
    return {
        "condition": ("control-flow surfaces of the model: incoming sequence flows of the "
                      "target activity, their condition expressions, the gateways they "
                      "come from, and the other branches of those gateways"),
        "constraint": ("data objects, text annotations and boundary timer events that are "
                       "structurally associated with the target activity"),
        "exception": ("boundary events attached to the target activity and the alternate "
                      "branches of the gateways its outgoing flows reach"),
    }[check]


def _named(element: Any) -> list[str]:
    out = []
    name = (element.get("name") or "").strip()
    if name:
        out.append(name)
    text = " ".join("".join(element.itertext()).split())
    if text and text != name:
        out.append(text)
    return out


def _owning_node_id(xml_root: Any, element: Any) -> str | None:
    """The nearest ancestor flow node id of one XML element."""
    parents = {child: parent for parent in xml_root.iter() for child in parent}
    node_tags = {"task", "userTask", "serviceTask", "scriptTask", "manualTask",
                 "businessRuleTask", "sendTask", "receiveTask", "callActivity",
                 "subProcess", "boundaryEvent", "startEvent", "endEvent",
                 "intermediateCatchEvent", "intermediateThrowEvent", "exclusiveGateway",
                 "parallelGateway", "inclusiveGateway", "eventBasedGateway"}
    current = parents.get(element)
    while current is not None:
        if _LOCAL(current.tag) in node_tags and current.get("id"):
            return current.get("id")
        current = parents.get(current)
    return None


def _time_limits(text: str) -> list[tuple[int, str]]:
    """(hours, raw) for the explicit time values of one text, reusing the frozen units."""
    out = []
    for match in _TIME_VALUE_RE.finditer(text or ""):
        unit = match.group(2).lower()
        unit = unit[:-1] if unit.endswith("s") else unit
        if unit in ("month", "year"):
            continue
        out.append((int(match.group(1)) * _UNIT_HOURS.get(unit, 1), match.group(0)))
    return out


_UPPER_BOUND_RE = re.compile(
    r"\s*(?:(?:not|no)\s+later\s+than|within|at\s+most)\s+"
    r"\d+\s*(?:hours?|hrs?|days?|weeks?)\s*[.,]?\s*", re.IGNORECASE)


def numeric_bound_verdict(rule_constraint: str, bound_texts: Sequence[str]) -> dict[str, Any]:
    """Compare only explicit upper bounds whose unit and direction are unambiguous."""
    rule_text = fold_whitespace(rule_constraint or "")
    if not _UPPER_BOUND_RE.fullmatch(rule_text):
        return {"verdict": VERDICT_UNKNOWN,
                "reason": "rule_bound_not_an_explicit_upper_limit",
                "comparisons": []}
    rule_limits = _time_limits(rule_text)
    if not rule_limits:
        return {"verdict": VERDICT_UNKNOWN, "reason": "no_time_value_in_rule_bound",
                "comparisons": []}
    rule_hours, rule_raw = rule_limits[0]
    comparisons, tighter = [], []
    for text in bound_texts:
        for cand_hours, cand_raw in _time_limits(text):
            comparisons.append({"candidate_text": text, "rule_value": rule_raw,
                                "rule_hours": rule_hours, "candidate_value": cand_raw,
                                "candidate_hours": cand_hours})
            if cand_hours > rule_hours:
                return {"verdict": VERDICT_VIOLATED,
                        "reason": "bound_candidate_exceeds_rule_limit",
                        "rule_value": rule_raw, "rule_hours": rule_hours,
                        "candidate_value": cand_raw, "candidate_hours": cand_hours,
                        "candidate_text": text, "comparisons": comparisons}
            if cand_hours < rule_hours:
                tighter.append(text)
    base = {"rule_value": rule_raw, "rule_hours": rule_hours,
            "comparisons": comparisons}
    if tighter:
        return {**base, "verdict": VERDICT_SATISFIED,
                "reason": "bound_limit_is_at_least_as_strict"}
    if comparisons:
        return {**base, "verdict": VERDICT_SATISFIED,
                "reason": "bound_limit_matches_rule_limit"}
    return {**base, "verdict": VERDICT_UNKNOWN,
            "reason": "no_numeric_bound_in_bound_evidence"}


def condition_path_verdict(bound: Sequence[Evidence], record: Mapping[str, Any],
                           activity_id: str | None, rule_condition: str) -> dict[str, Any]:
    """A finite structural check on the target activity's control flow.

    Order matters: an unconditional sibling branch out of a gateway the activity
    is reached through is reported as a bypass even when the activity's own flow
    carries the rule's condition, because the process can then reach the activity
    without the condition holding.  Topology alone never establishes an
    executable bypass - only a sibling branch that carries no condition on a
    branching gateway does - and everything else stays unknown.
    """
    rule_text = fold_whitespace(rule_condition).lower()
    if not rule_text:
        return {"verdict": VERDICT_UNKNOWN, "reason": "empty_rule_condition"}
    matching = [e for e in bound
                if e["relation"] in (RELATION_INCOMING_FLOW, RELATION_SAME_BRANCH_FLOW)
                and rule_text in e["text_folded"].lower()]
    if activity_id is None:
        return {"verdict": VERDICT_UNKNOWN, "reason": "no_target_activity"}
    gateway_ids = {g["id"] for g in record.get("gateways", [])}
    flows = list(record.get("sequence_flows", []))
    incoming = [f for f in flows if f["target_ref"] == activity_id]
    sources = {f["source_ref"] for f in incoming}
    bypass = []
    for flow in flows:
        if flow["source_ref"] not in sources or flow["target_ref"] == activity_id:
            continue
        if (flow.get("condition_expression") or "").strip():
            continue
        if flow["source_ref"] in gateway_ids:
            bypass.append({"flow_id": flow["id"], "from": flow["source_ref"],
                           "to": flow["target_ref"]})
    if bypass:
        return {"verdict": VERDICT_VIOLATED, "reason": "unconditional_bypass_branch",
                "bypass": bypass}
    if matching:
        return {"verdict": VERDICT_SATISFIED, "reason": "condition_text_on_control_flow",
                "evidence": matching}
    return {"verdict": VERDICT_UNKNOWN,
            "reason": "no_condition_text_on_the_control_flow_scope"}


def exception_handler_verdict(bound: Sequence[Evidence], record: Mapping[str, Any],
                              activity_id: str | None, rule_exception: str) -> dict[str, Any]:
    """Satisfied only by a handler structure attached to the target activity."""
    rule_text = fold_whitespace(rule_exception).lower()
    if not rule_text:
        return {"verdict": VERDICT_UNKNOWN, "reason": "empty_rule_exception"}
    handlers = [e for e in bound
                if e["relation"] == RELATION_BOUND_BOUNDARY_EVENT]
    if not handlers:
        return {"verdict": VERDICT_UNKNOWN, "reason": "no_handler_attached_to_activity"}
    for handler in handlers:
        if rule_text in handler["text_folded"].lower():
            return {"verdict": VERDICT_SATISFIED, "reason": "attached_handler_matches",
                    "evidence": [handler]}
    handler_tokens = set()
    for handler in handlers:
        handler_tokens.update(handler["text_folded"].lower().split())
    rule_tokens = {t for t in rule_text.split() if len(t) > 2}
    shared = sorted(rule_tokens & handler_tokens)
    return {"verdict": VERDICT_UNKNOWN, "reason": "attached_handler_does_not_express_"
                                                  "the_rule_exception",
            "evidence": handlers, "shared_tokens": shared}


# --------------------------------------------------------------------------- scorers


class WiringOnlyScorer(RepairedExtendedScorerV2):
    """Arm W: the measured arm C behaviour with ONE action resolution.

    The only behavioural change against arm C is that the candidate surfaces, the
    evidence checks, the numeric gate and the recorded fields all consume the same
    ``resolve_action()`` result.  The formulas, thresholds, action interpretation,
    candidate scope, empty-candidate meaning and aggregation are untouched.
    """

    method_id = WIRING_REPAIR_ID

    def __init__(self, v3, sim_text, gamma_action: float, gamma_ext: float = 0.5,
                 resolution: Mapping[str, Any] | None = None):
        super().__init__(v3, sim_text, gamma_action, gamma_ext)
        self._pinned_resolution = dict(resolution) if resolution is not None else None

    def resolve_action(self, action_text: str, model: Any) -> dict[str, Any]:
        if self._pinned_resolution is not None:
            return self._pinned_resolution
        return super().resolve_action(action_text, model)

    def required_condition(self, sentence: dict[str, Any], model: Any,
                           candidates: list[str]) -> dict[str, Any]:
        result = super().required_condition(sentence, model, candidates)
        result["rule_field_consumed"] = "condition"
        result["rule_text_consumed"] = (sentence.get("condition") or "").strip()
        return result

    def exception_not_handled(self, sentence: dict[str, Any], model: Any,
                              candidates: list[str]) -> dict[str, Any]:
        result = super().exception_not_handled(sentence, model, candidates)
        result["rule_field_consumed"] = "exception"
        result["rule_text_consumed"] = (sentence.get("exception") or "").strip()
        return result

    def prohibited_action(self, sentence: dict[str, Any], model: Any) -> dict[str, Any]:
        result = super().prohibited_action(sentence, model)
        result["rule_field_consumed"] = "action"
        result["rule_text_consumed"] = (sentence.get("action") or "").strip()
        return result

    def constraint_violated(self, sentence: dict[str, Any], model: Any,
                            candidates: list[str]) -> dict[str, Any]:
        result = super().constraint_violated(sentence, model, candidates)
        result["rule_field_consumed"] = "constraint"
        result["rule_text_consumed"] = (sentence.get("constraint") or "").strip()
        return result


class ScopedEvidenceScorer(WiringOnlyScorer):
    """Arm H: W plus sourced, scoped evidence and four-outcome verdicts.

    The scoped checks take the parsed record and the raw XML root explicitly, so
    no state is smuggled through the scorer and the same objects the runner
    already parsed are the ones examined.
    """

    method_id = EVIDENCE_SCOPE_ID

    def __init__(self, v3, sim_text, gamma_action: float, gamma_ext: float = 0.5,
                 resolution: Mapping[str, Any] | None = None):
        super().__init__(v3, sim_text, gamma_action, gamma_ext, resolution)
        self._scope_cache: dict[tuple, dict[str, Any]] = {}

    # ------------------------------------------------------------ scope plumbing
    def scope(self, record: Mapping[str, Any], xml_root: Any, activity_id: str | None,
              check: str) -> dict[str, Any]:
        key = (id(record), activity_id, check)
        cached = self._scope_cache.get(key)
        if cached is None:
            cached = collect_evidence(record, xml_root, activity_id, check)
            self._scope_cache[key] = cached
        return cached

    @staticmethod
    def _surface_texts(scope: Mapping[str, Any]) -> list[str]:
        return [e["text"] for e in scope["bound"]]

    def _evidence_result(self, check: str, rule_text: str, scope: Mapping[str, Any],
                         verdict: Mapping[str, Any]) -> dict[str, Any]:
        """Package one check outcome under the four-outcome contract."""
        outcome = verdict["verdict"]
        if not rule_text.strip():
            applicability, outcome = APPLICABILITY_NOT_REQUIRED, VERDICT_NOT_APPLICABLE
            evidence_status = EVIDENCE_NOT_ASSESSED
            reason = f"rule_has_no_{check}"
        else:
            applicability = APPLICABILITY_REQUIRED
            if outcome == VERDICT_VIOLATED:
                evidence_status = EVIDENCE_CONTRADICTED
            elif outcome == VERDICT_SATISFIED:
                evidence_status = EVIDENCE_PRESENT
            elif scope["scope_enumerable"]:
                evidence_status = EVIDENCE_ABSENT_CONFIRMED
            else:
                evidence_status = EVIDENCE_ABSENT_UNDECIDABLE
            reason = verdict.get("reason")
        return {
            "check": check,
            "applicability": applicability,
            "evidence_status": evidence_status,
            "verdict": outcome,
            "reason": reason,
            "scope_statement": scope["scope_statement"],
            "scope_enumerable": scope["scope_enumerable"],
            "target_activity_id": scope["target_activity_id"],
            "bound_evidence": [dict(e) for e in scope["bound"]],
            "unbound_evidence": [dict(e) for e in scope["unbound"]],
            "detail": {k: v for k, v in verdict.items() if k != "verdict"},
        }

    def _as_score_fields(self, packet: Mapping[str, Any],
                         violation_type: str) -> dict[str, Any]:
        """Map a verdict onto the shared decision fields without inventing a score."""
        verdict = packet["verdict"]
        base = {
            "applicability": packet["applicability"],
            "evidence_status": packet["evidence_status"],
            "verdict": verdict,
            "violation_type": violation_type,
            "reason": packet["reason"],
        }
        if verdict in (VERDICT_NOT_APPLICABLE, VERDICT_UNKNOWN):
            return {**base, "score": None, "observable": False,
                    "comparison_performed": False}
        score = 1.0 if verdict == VERDICT_VIOLATED else 0.0
        return {**base, "score": score, "observable": True,
                "violation": verdict == VERDICT_VIOLATED,
                "comparison_performed": True,
                "best_candidate": _first_text(packet.get("detail", {}).get("evidence"))}

    # --------------------------------------------------------------- the 4 checks
    def prohibited_action(self, sentence: dict[str, Any], model: Any) -> dict[str, Any]:
        """Presence check: unchanged formula and scale; no single activity needed."""
        return super().prohibited_action(sentence, model)

    def condition_check(self, sentence: dict[str, Any], model: Any,
                        record: Mapping[str, Any], xml_root: Any) -> dict[str, Any]:
        rule_text = (sentence.get("condition") or "").strip()
        res = self.resolve_action(sentence.get("action") or "", model)
        scope = self.scope(record, xml_root, res["resolved_activity_id"], "condition")
        verdict = condition_path_verdict(scope["bound"], record,
                                         res["resolved_activity_id"], rule_text)
        packet = self._evidence_result("condition", rule_text, scope, verdict)
        result = self._as_score_fields(packet, "required_condition_not_enforced")
        result.update({"rule_field_consumed": "condition",
                       "rule_text_consumed": rule_text,
                       "evidence_scope": scope,
                       "action_resolution": res["action_resolution"],
                       "matched_activity_id": res["resolved_activity_id"]})
        return result

    def constraint_check(self, sentence: dict[str, Any], model: Any,
                         record: Mapping[str, Any], xml_root: Any) -> dict[str, Any]:
        rule_text = (sentence.get("constraint") or "").strip()
        condition_text = fold_whitespace((sentence.get("condition") or "").lower())
        res = self.resolve_action(sentence.get("action") or "", model)
        scope = self.scope(record, xml_root, res["resolved_activity_id"], "constraint")
        if not rule_text:
            verdict = {"verdict": VERDICT_UNKNOWN, "reason": "empty_rule_constraint"}
        elif rule_text.lower() in condition_text:
            verdict = {"verdict": VERDICT_UNKNOWN,
                       "reason": "time_bound_inside_condition"}
        else:
            verdict = numeric_bound_verdict(rule_text, self._surface_texts(scope))
        packet = self._evidence_result("constraint", rule_text, scope, verdict)
        result = self._as_score_fields(packet, "constraint_violated")
        result.update({"rule_field_consumed": "constraint",
                       "rule_text_consumed": rule_text,
                       "evidence_scope": scope,
                       "action_resolution": res["action_resolution"],
                       "matched_activity_id": res["resolved_activity_id"]})
        return result

    def exception_check(self, sentence: dict[str, Any], model: Any,
                        record: Mapping[str, Any], xml_root: Any) -> dict[str, Any]:
        rule_text = (sentence.get("exception") or "").strip()
        res = self.resolve_action(sentence.get("action") or "", model)
        scope = self.scope(record, xml_root, res["resolved_activity_id"], "exception")
        verdict = exception_handler_verdict(scope["bound"], record,
                                            res["resolved_activity_id"], rule_text)
        packet = self._evidence_result("exception", rule_text, scope, verdict)
        result = self._as_score_fields(packet, "exception_not_handled")
        result.update({"rule_field_consumed": "exception",
                       "rule_text_consumed": rule_text,
                       "evidence_scope": scope,
                       "action_resolution": res["action_resolution"],
                       "matched_activity_id": res["resolved_activity_id"]})
        return result


def _first_text(evidence: Any) -> str | None:
    if isinstance(evidence, Sequence) and evidence:
        first = evidence[0]
        if isinstance(first, Mapping):
            return first.get("text")
    return None


def aggregate_scope_verdicts(side_scores: Mapping[str, Any],
                             gamma_ext: float) -> dict[str, Any]:
    """Arm H aggregation.

    Unchanged type priority for violations.  ``none`` is issued only when every
    *required* evidence check is satisfied: a required check that stays unknown
    keeps the row unknown, and a check the rule does not require
    (``not_applicable``) neither blocks nor licenses compliance.  The prohibition
    presence check is not required to have run, so a pure prohibition rule can
    still be answered.  ``none`` means compliant inside the declared evidence
    scope, never that the whole process passed every legal requirement.
    """
    per_type: dict[str, Any] = {}
    verdicts: dict[str, str] = {}
    for t in EXTENDED_TYPES:
        entry = dict(side_scores.get(t) or {})
        verdict = entry.get("verdict")
        verdicts[t] = verdict
        if verdict is None:  # a check that does not use the four-outcome contract
            if not entry.get("observable"):
                per_type[t] = None
                continue
            score = entry.get("score")
            if t == "prohibited_action_present":
                per_type[t] = score is not None and score >= gamma_ext
            else:
                per_type[t] = score is not None and score > gamma_ext
            continue
        if verdict == VERDICT_NOT_APPLICABLE:
            per_type[t] = None
        elif verdict == VERDICT_UNKNOWN:
            per_type[t] = None
        elif verdict == VERDICT_VIOLATED:
            per_type[t] = True
        else:
            per_type[t] = False
    violated = next((t for t in EXTENDED_TYPES if per_type.get(t) is True), None)
    evidence_types = tuple(t for t in EXTENDED_TYPES
                           if t != "prohibited_action_present")
    # applicability is carried by the verdict itself: ``not_applicable`` means the
    # rule does not require the element, so it neither blocks nor licenses
    # compliance; a check without the four-outcome contract does not enter the gate
    required = [t for t in evidence_types
                if verdicts.get(t) in (VERDICT_SATISFIED, VERDICT_VIOLATED,
                                       VERDICT_UNKNOWN)]
    pending = [t for t in required if verdicts.get(t) == VERDICT_UNKNOWN]
    any_observable = any(v is not None for v in per_type.values())
    if violated is not None:
        predicted = violated
    elif pending:
        predicted = None
    elif required:
        predicted = NONE_LABEL
    elif any_observable:
        predicted = NONE_LABEL
    else:
        predicted = None
    declared = {t: side_scores.get(t, {}).get("applicability") for t in evidence_types}
    for t, value in declared.items():
        if value is None:
            continue
        expected_value = (APPLICABILITY_NOT_REQUIRED
                          if verdicts.get(t) == VERDICT_NOT_APPLICABLE
                          else APPLICABILITY_REQUIRED)
        if value != expected_value:
            raise ValueError(f"applicability disagrees with the verdict for {t}")
    return {
        "predicted": predicted,
        "per_type": per_type,
        "verdicts": verdicts,
        "all_unobservable": not any_observable,
        "required_evidence_checks": required,
        "pending_required_checks": pending,
        "policy": ("violated wins by the unchanged type priority; 'none' requires every "
                   "required evidence check to be satisfied; a required check that stays "
                   "unknown keeps the row unknown; 'not_applicable' neither blocks nor "
                   "licenses compliance; 'none' is scoped compliance, not whole-process "
                   "legal compliance"),
    }
