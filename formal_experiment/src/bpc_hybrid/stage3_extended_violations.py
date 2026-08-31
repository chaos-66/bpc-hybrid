# -*- coding: utf-8 -*-
"""Stage 3 extended violation extension (S3.9-EXT, development-only, zero API).

This module adds FOUR new violation categories to the existing Stage 3
synthetic controlled-error panel:

* ``prohibited_action_present``      — a regulation-prohibited action appears
  as a process activity (consumes the Rule Record ``modality`` + ``action``);
* ``required_condition_not_enforced`` — a required condition is not visible in
  any gateway / conditionExpression / sequence-flow label / adjacent control
  node (consumes ``condition`` + ``action``);
* ``constraint_violated``            — a time / quantity / usage constraint is
  missing from the model or explicitly contradicted (consumes ``constraint``
  + ``action``);
* ``exception_not_handled``          — a regulation exception has no boundary
  event / error event / alternate branch / handler activity (consumes
  ``exception`` + ``action``).

Naming boundary: Winter et al. (2020) and Sun et al. (2024) define no such
violation types.  The four methods below therefore run as **Winter-style
extension** / **Sun-style extension** / **BM25 extension** / **TF-IDF/SVD
extension**: they share the SAME new-type formulas and only swap the existing
similarity backend of each method.  Nothing here claims native capability of
the original papers.

Scoring (fixed, shared by all four methods; ``sim(x, y)`` = the method's own
similarity backend):

* ``score_prohibited = max sim(rule_action, process_activity)`` — violation iff
  rule modality == prohibition AND ``score_prohibited >= gamma_ext``;
* ``score_condition = 1 - max sim(rule_condition, condition_candidates)`` —
  violation iff condition non-empty AND action mappable (>= per-method gamma)
  AND ``score_condition > gamma_ext``;
* ``score_constraint = 1 - max sim(rule_constraint, constraint_candidates)`` —
  same gate; an explicit conflicting time/quantity value is recorded as an
  exact contradiction (never hard-coded to 0 or 1);
* ``score_exception = 1 - max sim(rule_exception, exception_candidates)`` —
  same gate.

Observability policy (mirrors the frozen Stage 3 evaluator): when a check
cannot run — empty rule element, action not mappable below gamma, or an empty
candidate surface — the score is ``None`` and the item is recorded as
``unobservable`` (reason attached); it is NEVER hard-filled with 0.0 or 1.0.
Unobservable items keep ``predicted_violation_type = None`` and therefore
count as FN in the primary macro/micro/exact denominators; an observable-only
diagnostic subset is reported separately.

The panel itself is a development-only synthetic controlled extension: it is
NOT human Gold and must never be merged into the 33-item human-adjudicated
violation Gold nor presented as the formal Oracle.
"""

from __future__ import annotations

import re
from typing import Any

from bpc_hybrid.sun_stage3.sun_rule_extraction import _extract_actor  # noqa: E402

# ---------------------------------------------------------------------------
# Deterministic six-element Rule Record extraction (development adapter)
# ---------------------------------------------------------------------------

# NOTE: the extended extractor intentionally improves two known limitations of
# the frozen development adapter (src/bpc_hybrid/sun_stage3/sun_rule_extraction.py)
# WITHOUT modifying it: (1) condition markers are matched at word boundaries
# ("if" must not match inside "rectification"); (2) when the sentence ROOT is a
# modal/copula/have-verb, the action descends to the main verb ("shall notify"
# -> "notify", "shall have the right to obtain" -> "obtain").  The frozen
# adapter stays untouched for the original three violation types; the extended
# extractor is used ONLY by the four new synthetic types.

CONDITION_MARKERS = (
    r"\bin\s+the\s+case\s+of\b",
    r"\bprovided\s+that\b",
    r"\bto\s+the\s+extent\s+that\b",
    r"\bonly\s+if\b",
    r"\bunless\b",
    r"\bwhere\b",
    r"\bwhen\b",
    r"\bif\b",
    r"\bafter\b",
    r"\bbefore\b",
)

_MODAL_ROOTS = {"shall", "must", "may", "should", "will", "would", "can",
                "could", "be", "is", "are", "was", "were", "been", "being",
                "have", "has", "had"}
_ACTION_CHILD_DEPS = ("dobj", "pobj", "attr", "oprd", "acomp", "xcomp",
                      "advmod")


def _extract_action_extended(sent: Any) -> str | None:
    """Action = main verb phrase; descends through modal/copula/have chains to
    the first verbal xcomp/acomp/advcl child, then mirrors the frozen adapter's
    verb + core-complement extraction.  Falls back to the first prepositional
    complement when the verb has no core object."""
    root = None
    for token in sent:
        if token.dep_ == "ROOT":
            root = token
            break
    if root is None:
        return None
    node = root
    for _ in range(4):
        if node.text.lower() not in _MODAL_ROOTS:
            break
        nxt = next(
            (c for c in node.children
             if c.dep_ in ("xcomp", "acomp", "advcl", "conj") and c.pos_ == "VERB"),
            None,
        )
        if nxt is None:
            break
        node = nxt
    parts = [node.text]
    for child in node.children:
        if child.dep_ in _ACTION_CHILD_DEPS:
            parts.extend(t.text for t in child.subtree)
    if len(parts) == 1:
        prep = next(
            (c for c in node.children if c.dep_ in ("prep", "agent", "dative")),
            None,
        )
        if prep is not None:
            parts.extend(t.text for t in prep.subtree)
    text = " ".join(parts).strip()
    return text or None

EXTENDED_TYPES = (
    "prohibited_action_present",
    "required_condition_not_enforced",
    "constraint_violated",
    "exception_not_handled",
)

EXTENDED_TYPES_SET = frozenset(EXTENDED_TYPES)

# (regex, kind) in priority order; the FIRST match is the locked constraint.
CONSTRAINT_PATTERNS = (
    (r"\b(?:not|no)\s+later\s+than\s+\d+\s+(?:hours?|days?|weeks?|months?|years?)\b", "time_limit"),
    (r"\bwithin\s+\d+\s+(?:hours?|days?|weeks?|months?|years?)\b", "time_limit"),
    (r"\bwithout\s+undue\s+delay\b", "timeliness"),
    (r"\bat\s+any\s+time\b", "timeliness"),
    (r"\bat\s+least\b", "minimum"),
    (r"\bimmediately\b", "timeliness"),
    (r"\bwithout\s+hindrance\b", "restriction"),
    (r"\bclear\s+and\s+plain\s+language\b", "form"),
    (r"\bclearly\s+distinguishable\b", "form"),
    (r"\bintelligible\s+and\s+easily\s+accessible\b", "form"),
    (r"\bstructured,\s+commonly\s+used\s+and\s+machine-readable\b", "form"),
)

# (regex, kind) in priority order; the FIRST match is the locked exception.
EXCEPTION_PATTERNS = (
    (r"\bwithout\s+prejudice\b[^.,;]*", "without_prejudice"),
    (r"\bunless\b[^.,;]*", "unless_clause"),
    (r"\bexcept\b[^.,;]*", "except_clause"),
    (r"\bshall\s+not\s+(?:be\s+)?(?:required|applied|applicable|apply)\b[^.,;]*", "not_required_clause"),
    (r"\bis\s+not\s+required\b[^.,;]*", "not_required_clause"),
    (r"\bnot\s+be\s+subject\b[^.,;]*", "not_subject_clause"),
    (r"\bwhere\s+technically\s+feasible\b", "feasibility_clause"),
)


def _sentence_modality(sentence_text: str) -> str | None:
    """Deterministic sentence-level modality: prohibition / obligation /
    permission / None (definition or descriptive sentence)."""
    lower = re.sub(r"\s+", " ", sentence_text).lower()
    if re.search(r"\b(shall|must|may)\s+not\b", lower) or re.search(
        r"\bright\s+not\s+to\b", lower
    ):
        return "prohibition"
    if re.search(r"\b(shall|must)\b", lower):
        return "obligation"
    if re.search(r"\bmay\b", lower):
        return "permission"
    return None


def _extract_condition(sentence_text: str) -> str | None:
    """Deterministic condition extraction: the clause introduced by the first
    condition marker (``where``/``when``/``if``/``unless``/``in the case
    of``/...), matched at word boundaries.  Marker at sentence start => leading
    clause up to the first comma; marker mid-sentence => span from the marker
    to the next comma/semicolon or sentence end."""
    text = re.sub(r"\s+", " ", sentence_text).strip()
    lower = text.lower()
    first: tuple[int, str] | None = None
    for marker in CONDITION_MARKERS:
        match = re.search(marker, lower)
        if match is None:
            continue
        if first is None or match.start() < first[0]:
            first = (match.start(), marker)
    if first is None:
        return None
    pos, marker = first
    if pos == 0:
        end = _clause_end(text, 0)
        return text[:end].strip() or None
    end = _clause_end(text, pos)
    return text[pos:end].strip() or None


def _clause_end(text: str, start: int) -> int:
    for sep in (",", ";", ".", ")"):
        idx = text.find(sep, start)
        if idx != -1:
            return idx
    return len(text)


def _extract_constraint(sentence_text: str) -> tuple[str | None, str | None]:
    """First constraint phrase match -> (phrase, kind)."""
    text = re.sub(r"\s+", " ", sentence_text)
    for pattern, kind in CONSTRAINT_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0).strip(), kind
    return None, None


def _extract_exception(sentence_text: str) -> tuple[str | None, str | None]:
    """First exception clause match -> (clause, kind)."""
    text = re.sub(r"\s+", " ", sentence_text)
    for pattern, kind in EXCEPTION_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0).strip(), kind
    return None, None


def extract_six_element_sentences(rule_id: str, rule_text: str, nlp) -> list[dict[str, Any]]:
    """Per-sentence six-element Rule Record extraction (development adapter).

    Deterministic (spaCy sentence split + dependency parsing + the fixed
    marker/pattern lists above).  Reads only ``rule_text`` — never Gold
    decision/candidate fields.
    """
    doc = nlp(rule_text)
    sentences: list[dict[str, Any]] = []
    for idx, sent in enumerate(doc.sents):
        text = re.sub(r"\s+", " ", sent.text).strip()
        constraint, constraint_kind = _extract_constraint(text)
        exception, exception_kind = _extract_exception(text)
        sentences.append({
            "rule_id": rule_id,
            "sentence_idx": idx,
            "sentence_text": text,
            "modality": _sentence_modality(text),
            "actor": _extract_actor(sent),
            "action": _extract_action_extended(sent),
            "condition": _extract_condition(text),
            "constraint": constraint,
            "constraint_kind": constraint_kind,
            "exception": exception,
            "exception_kind": exception_kind,
        })
    return sentences


def sentence_matches_locked(sentence: dict[str, Any], locked: dict[str, Any]) -> bool:
    """Replay guard: the runner's re-extraction must reproduce the locked
    element texts exactly (fail-closed otherwise)."""
    for field in ("sentence_idx", "modality", "action", "condition",
                  "constraint", "exception"):
        if sentence.get(field) != locked.get(field):
            return False
    return True


# ---------------------------------------------------------------------------
# Process candidate surfaces (canonical Process Record + raw XML)
# ---------------------------------------------------------------------------

_LOCAL = lambda tag: tag.rsplit("}", 1)[-1] if "}" in tag else tag  # noqa: E731

_EXCEPTION_CUES = (
    "delay", "error", "exception", "abort", "aborted", "cancel", "cancelled",
    "negation", "denied", "reject", "fallback", "alternative", "handler",
    "escalation", "compensation",
)

_TIME_VALUE_RE = re.compile(r"\b(\d+)\s*(hours?|hrs?|days?|weeks?|months?|years?)\b", re.IGNORECASE)
_UNIT_HOURS = {
    "hour": 1, "hr": 1, "day": 24, "week": 168, "month": 720, "year": 8760,
}


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = (item or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def action_candidates(record: dict[str, Any]) -> list[str]:
    """Action surface: activity + event labels (the same surface the frozen
    Sun scorer maps rule actions against)."""
    names = [a["name"] for a in record.get("activities", []) if (a.get("name") or "").strip()]
    names += [e["name"] for e in record.get("events", []) if (e.get("name") or "").strip()]
    return _dedup(names)


def _adjacent_control_nodes(record: dict[str, Any], activity_id: str) -> list[str]:
    """Adjacent control nodes of one activity: gateways and events directly
    connected by a sequence flow (deterministic, id-sorted)."""
    node_kind: dict[str, str] = {}
    for g in record.get("gateways", []):
        node_kind[g["id"]] = "gateway"
    for e in record.get("events", []):
        node_kind[e["id"]] = "event"
    names_by_id = {g["id"]: g["name"] for g in record.get("gateways", [])}
    names_by_id.update({e["id"]: e["name"] for e in record.get("events", [])})
    adjacent: list[str] = []
    for flow in record.get("sequence_flows", []):
        other = None
        if flow["source_ref"] == activity_id:
            other = flow["target_ref"]
        elif flow["target_ref"] == activity_id:
            other = flow["source_ref"]
        if other in node_kind:
            name = (names_by_id.get(other) or "").strip()
            if name:
                adjacent.append(name)
    return _dedup(adjacent)


def condition_candidates(record: dict[str, Any], xml_root: Any,
                         mapped_activity_id: str | None = None) -> list[str]:
    """condition candidates: sequence-flow labels, conditionExpression texts,
    gateway labels, and adjacent control nodes of the mapped activity."""
    cands: list[str] = []
    for flow in record.get("sequence_flows", []):
        if (flow.get("name") or "").strip():
            cands.append(flow["name"])
        if flow.get("condition_expression"):
            cands.append(flow["condition_expression"])
    for gateway in record.get("gateways", []):
        if (gateway.get("name") or "").strip():
            cands.append(gateway["name"])
    if mapped_activity_id:
        cands.extend(_adjacent_control_nodes(record, mapped_activity_id))
    return _dedup(cands)


def _xml_named_elements(xml_root: Any, local_names: tuple[str, ...]) -> list[str]:
    names: list[str] = []
    for el in xml_root.iter():
        if _LOCAL(el.tag) not in local_names:
            continue
        name = (el.get("name") or "").strip()
        if name:
            names.append(name)
        text = " ".join("".join(el.itertext()).split())
        if text and text != name:
            names.append(text)
    return names


def constraint_candidates(record: dict[str, Any], xml_root: Any,
                          mapped_activity_id: str | None = None) -> list[str]:
    """constraint candidates: activity labels, data object/data store labels,
    text annotations, timer/event labels, flow labels, and the mapped
    activity's adjacent node labels (visible time/quantity/restriction
    evidence)."""
    cands: list[str] = action_candidates(record)
    for flow in record.get("sequence_flows", []):
        if (flow.get("name") or "").strip():
            cands.append(flow["name"])
    cands.extend(_xml_named_elements(xml_root, (
        "dataObject", "dataObjectReference", "dataStore", "dataStoreReference",
        "textAnnotation", "timerEventDefinition", "timeDate", "timeDuration",
        "timeCycle", "startEvent", "endEvent", "intermediateCatchEvent",
        "intermediateThrowEvent", "boundaryEvent",
    )))
    if mapped_activity_id:
        cands.extend(_adjacent_control_nodes(record, mapped_activity_id))
    return _dedup(cands)


def exception_candidates(record: dict[str, Any], xml_root: Any,
                         mapped_activity_id: str | None = None) -> list[str]:
    """exception candidates: boundary events, error/escalation event
    definitions (raw XML), alternate outgoing branches (targets of branching
    gateways, excluding the default flow target when identifiable), and
    exception-cued activity/event labels."""
    cands: list[str] = []
    # boundary events (record events + raw XML names)
    for event in record.get("events", []):
        name = (event.get("name") or "").strip()
        if event.get("type") == "boundaryEvent" and name:
            cands.append(name)
    for el in xml_root.iter():
        if _LOCAL(el.tag) == "boundaryEvent":
            name = (el.get("name") or "").strip()
            if name:
                cands.append(name)
    # error / escalation definitions (raw XML; carry names when present)
    cands.extend(_xml_named_elements(xml_root, ("error", "escalation")))
    # alternate outgoing branches: targets of any gateway with outdegree > 1
    gateway_ids = {g["id"] for g in record.get("gateways", [])}
    out_degree: dict[str, int] = {}
    flow_targets: dict[str, list[str]] = {}
    for flow in record.get("sequence_flows", []):
        src = flow["source_ref"]
        out_degree[src] = out_degree.get(src, 0) + 1
        flow_targets.setdefault(src, []).append(flow["target_ref"])
    name_by_id = {a["id"]: a["name"] for a in record.get("activities", [])}
    name_by_id.update({e["id"]: e["name"] for e in record.get("events", [])})
    for gateway_id in gateway_ids:
        if out_degree.get(gateway_id, 0) > 1:
            for target in flow_targets.get(gateway_id, []):
                name = (name_by_id.get(target) or "").strip()
                if name:
                    cands.append(name)
    # exception-cued activity/event labels
    lower_cues = {cue.lower() for cue in _EXCEPTION_CUES}
    for node in list(record.get("activities", [])) + list(record.get("events", [])):
        name = (node.get("name") or "").strip()
        if name and any(cue in name.lower() for cue in lower_cues):
            cands.append(name)
    return _dedup(cands)


def detect_exact_constraint_contradiction(
    rule_constraint: str, candidate_texts: list[str]
) -> dict[str, Any]:
    """Deterministic time-limit contradiction record.

    Extracts (value, unit) time limits from the rule constraint and from every
    candidate text; a candidate value STRICTLY GREATER than the rule limit
    (time limits are treated as upper bounds, e.g. ``not later than 72
    hours``) is an exact contradiction.  Returns a record with
    ``contradiction`` bool; never guesses 0/1 scores."""
    def limits(text: str) -> list[tuple[int, str]]:
        result = []
        for match in _TIME_VALUE_RE.finditer(text):
            unit = match.group(2).lower()
            unit = unit[:-1] if unit.endswith("s") else unit
            hours = int(match.group(1)) * _UNIT_HOURS.get(unit, 1)
            result.append((hours, match.group(0)))
        return result

    rule_limits = limits(rule_constraint or "")
    if not rule_limits:
        return {"contradiction": False, "reason": "no_time_value_in_rule_constraint"}
    rule_hours, rule_raw = rule_limits[0]
    for candidate in candidate_texts or []:
        for cand_hours, cand_raw in limits(candidate):
            if cand_hours > rule_hours:
                return {
                    "contradiction": True,
                    "rule_value": rule_raw,
                    "rule_hours": rule_hours,
                    "candidate_value": cand_raw,
                    "candidate_hours": cand_hours,
                    "candidate_text": candidate,
                    "reason": "candidate_time_limit_exceeds_rule_limit",
                }
    return {"contradiction": False, "reason": "no_conflicting_value_found"}


# ---------------------------------------------------------------------------
# Shared scorer (one formula set, pluggable similarity backend)
# ---------------------------------------------------------------------------


class ExtendedViolationScorer:
    """Four new-type scores over one variant model.

    ``sim_action(query, candidate)`` is the method's action-domain similarity;
    ``sim_text(query, candidate)`` is the method's general text similarity
    (same backend; BM25 uses its per-domain candidate pools).  ``gamma`` is
    the method's own frozen action-mapping threshold; ``gamma_ext`` is the
    unified fixed decision threshold of this extension.
    """

    def __init__(self, sim_action, sim_text, gamma: float, gamma_ext: float = 0.5):
        self.sim_action = sim_action
        self.sim_text = sim_text
        self.gamma = gamma
        self.gamma_ext = gamma_ext

    def _best(self, query: str, candidates: list[str], sim_fn) -> tuple[float, str | None]:
        best = 0.0
        best_name: str | None = None
        for candidate in candidates:
            score = float(sim_fn(query, candidate))
            if score > best:
                best = score
                best_name = candidate
        return best, best_name

    def _best_action(self, action_text: str, model: Any) -> tuple[float, str | None, str | None]:
        candidates = [a["name"] for a in model.actions if (a.get("name") or "").strip()]
        best, best_name = self._best(action_text or "", candidates, self.sim_action)
        best_id = None
        for act in model.actions:
            if act["name"] == best_name:
                best_id = act["id"]
                break
        return best, best_name, best_id

    def prohibited_action(self, sentence: dict[str, Any], model: Any) -> dict[str, Any]:
        if sentence.get("modality") != "prohibition":
            return {"score": None, "observable": False,
                    "reason": "rule_modality_not_prohibition"}
        if not (sentence.get("action") or "").strip():
            return {"score": None, "observable": False,
                    "reason": "empty_rule_action"}
        best, best_name, _ = self._best_action(sentence["action"], model)
        return {
            "score": round(best, 6),
            "max_sim": round(best, 6),
            "best_candidate": best_name,
            "observable": True,
            "violation": best >= self.gamma_ext,
        }

    def required_condition(self, sentence: dict[str, Any], model: Any,
                           candidates: list[str]) -> dict[str, Any]:
        return self._missing_evidence(
            "condition", sentence, model, candidates,
            "required_condition_not_enforced",
        )

    def constraint_violated(self, sentence: dict[str, Any], model: Any,
                            candidates: list[str]) -> dict[str, Any]:
        """Constraint check: an explicit time-limit contradiction is recorded
        FIRST (it is a direct observation, independent of action mapping);
        otherwise fall back to the missing-evidence score with the standard
        observability gates."""
        contradiction = detect_exact_constraint_contradiction(
            sentence.get("constraint") or "", candidates
        )
        base = self._missing_evidence(
            "constraint", sentence, model, candidates,
            "constraint_violated",
        )
        base["exact_contradiction"] = contradiction
        if contradiction.get("contradiction"):
            base["observable"] = True
            base["reason"] = "exact_contradiction"
            base["score"] = 1.0
            base["violation"] = True
        return base

    def exception_not_handled(self, sentence: dict[str, Any], model: Any,
                              candidates: list[str]) -> dict[str, Any]:
        return self._missing_evidence(
            "exception", sentence, model, candidates,
            "exception_not_handled",
        )

    def _missing_evidence(self, field: str, sentence: dict[str, Any], model: Any,
                          candidates: list[str], violation_type: str) -> dict[str, Any]:
        rule_value = (sentence.get(field) or "").strip()
        if not rule_value:
            return {"score": None, "observable": False,
                    "reason": f"empty_rule_{field}"}
        action_text = (sentence.get("action") or "").strip()
        action_best, action_name, _ = self._best_action(action_text, model)
        if not action_text or action_best < self.gamma:
            return {
                "score": None, "observable": False,
                "reason": "action_mapping_below_gamma",
                "action_max_sim": round(action_best, 6),
                "action_best_candidate": action_name,
            }
        if not candidates:
            return {"score": None, "observable": False,
                    "reason": f"no_{field}_candidates"}
        best, best_name = self._best(rule_value, candidates, self.sim_text)
        score = 1.0 - best
        return {
            "score": round(score, 6),
            "max_sim": round(best, 6),
            "best_candidate": best_name,
            "action_max_sim": round(action_best, 6),
            "action_best_candidate": action_name,
            "observable": True,
            "violation": score > self.gamma_ext,
            "violation_type": violation_type,
        }


# ---------------------------------------------------------------------------
# Shared evaluator (one evaluator for all four methods)
# ---------------------------------------------------------------------------


def _p_r_f1(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4)}


def evaluate_extended(predictions: list[dict[str, Any]],
                      gold: dict[str, Any]) -> dict[str, Any]:
    """Shared evaluator for the four new types (same structure and
    observability policy as ``evaluate_stage3_common.evaluate_violation``).

    Unobservable items keep predicted=None and count as FN in the primary
    macro/micro/exact denominators; an observable-only diagnostic subset is
    reported separately and is not the primary metric.
    """
    per_type: dict[str, dict[str, int]] = {
        t: {"tp": 0, "fp": 0, "fn": 0} for t in EXTENDED_TYPES
    }
    per_type_obs: dict[str, dict[str, int]] = {
        t: {"tp": 0, "fp": 0, "fn": 0} for t in EXTENDED_TYPES
    }
    unobservable_by_reason: dict[str, int] = {}
    detected = missed = wrong_type = 0
    for p in predictions:
        g = gold[p["item_id"]]["expected_violation"]
        pred = p.get("predicted_violation_type")
        observability = p.get("observability", {})
        obs = observability.get(g, {"observable": True})
        is_unobservable = obs.get("observable") is False
        if is_unobservable:
            reason = obs.get("reason") or "unspecified"
            unobservable_by_reason[reason] = unobservable_by_reason.get(reason, 0) + 1
        if pred == g:
            detected += 1
            per_type[g]["tp"] += 1
            if not is_unobservable:
                per_type_obs[g]["tp"] += 1
        elif pred is not None:
            missed += 1
            wrong_type += 1
            per_type[g]["fn"] += 1
            per_type.setdefault(pred, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1
            if not is_unobservable:
                per_type_obs[g]["fn"] += 1
                per_type_obs.setdefault(pred, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1
        else:
            missed += 1
            per_type[g]["fn"] += 1
            if not is_unobservable:
                per_type_obs[g]["fn"] += 1
    per_type_results: dict[str, Any] = {}
    per_type_obs_results: dict[str, Any] = {}
    for t in EXTENDED_TYPES:
        per_type_results[t] = {
            "support": per_type[t]["tp"] + per_type[t]["fn"],
            **_p_r_f1(per_type[t]["tp"], per_type[t]["fp"], per_type[t]["fn"]),
        }
        per_type_obs_results[t] = {
            "support": per_type_obs[t]["tp"] + per_type_obs[t]["fn"],
            **_p_r_f1(per_type_obs[t]["tp"], per_type_obs[t]["fp"], per_type_obs[t]["fn"]),
        }
    total_tp = sum(per_type[t]["tp"] for t in EXTENDED_TYPES)
    total_fp = sum(per_type[t]["fp"] for t in EXTENDED_TYPES)
    total_fn = sum(per_type[t]["fn"] for t in EXTENDED_TYPES)
    micro = _p_r_f1(total_tp, total_fp, total_fn)
    obs_tp = sum(per_type_obs[t]["tp"] for t in EXTENDED_TYPES)
    obs_fp = sum(per_type_obs[t]["fp"] for t in EXTENDED_TYPES)
    obs_fn = sum(per_type_obs[t]["fn"] for t in EXTENDED_TYPES)
    micro_obs = _p_r_f1(obs_tp, obs_fp, obs_fn)
    per_type_support = {t: per_type[t]["tp"] + per_type[t]["fn"] for t in EXTENDED_TYPES}
    per_type_observable = {
        t: per_type_obs[t]["tp"] + per_type_obs[t]["fn"] for t in EXTENDED_TYPES
    }
    total_unobservable = sum(unobservable_by_reason.values())
    return {
        "support": len(predictions),
        "per_type": per_type_results,
        "observable_only_per_type": per_type_obs_results,
        "macro_f1": round(
            sum(v["f1"] for v in per_type_results.values()) / len(EXTENDED_TYPES), 4
        ),
        "micro_f1": micro["f1"],
        "observable_only_macro_f1": round(
            sum(v["f1"] for v in per_type_obs_results.values()) / len(EXTENDED_TYPES), 4
        ),
        "observable_only_micro_f1": micro_obs["f1"],
        "exact_type_accuracy": round(detected / len(predictions), 4) if predictions else 0.0,
        "detected": detected,
        "missed": missed,
        "wrong_type": wrong_type,
        "unobservable": total_unobservable,
        "denominator": {
            "total_items": len(predictions),
            "per_type_support": per_type_support,
            "per_type_observable": per_type_observable,
            "per_type_unobservable": {
                t: per_type_support[t] - per_type_observable[t] for t in EXTENDED_TYPES
            },
            "unobservable_total": total_unobservable,
            "unobservable_by_reason": unobservable_by_reason,
            "observability_policy": (
                "unobservable items keep predicted=None and count as FN in the "
                "primary macro/micro/exact denominators; an observable-only "
                "diagnostic subset is reported separately and is not the primary "
                "metric; unobservable scores are never hard-filled with 0.0 or 1.0"
            ),
        },
    }
