# -*- coding: utf-8 -*-
"""S3 semantic-grounding revision v1 (development-only, zero real API).

This module implements the deterministic-first Stage 3 repair requested for the
four development-only extended violation types:

* action grounding is a ranked, multi-signal, top-K decision
  (semantic similarity + label normalization + content-token coverage +
  lane/pool ownership context) with explicit resolved / ambiguous / unresolved
  statuses;
* condition, constraint, and exception checks consume finite, action-anchored
  local BPMN surfaces instead of a graph-wide text pool;
* "no candidate" is separated into observable absence and unobservable
  insufficiency: a negative structural verdict is emitted only for a fully
  enumerated local scope and only for rule kinds whose structural semantics are
  declared in the revision config;
* the explicit numeric time-limit contradiction path from the frozen
  ``stage3_extended_violations`` module is retained;
* a strict, fail-closed LLM semantic-grounding fallback is implemented and
  offline-testable but is NOT real-run without explicit API authorization.

The module never reads ``expected_violation``, ``mutation_type``,
``mutation_config``, ``target_activity_id``, synthetic file-path labels, or
human Gold.  It receives only the Rule Record sentence fields and the parsed
process model/XML.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict, deque
from typing import Any, Callable, Iterable, Mapping, Sequence

from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES,
    NONE_LABEL,
    _TIME_VALUE_RE,
    _UNIT_HOURS,
)

REVISION = "s3_semantic_grounding_v1"
SCORE_SCHEMA = "s3_semantic_grounding_score@1.0.0"
LLM_SCHEMA_VERSION = "s3_semantic_grounding_llm_response@1.0.0"

ACTION_STATUS_RESOLVED = "resolved"
ACTION_STATUS_AMBIGUOUS = "ambiguous"
ACTION_STATUS_UNRESOLVED = "unresolved"

CONDITION_ENFORCED = "enforced"
CONDITION_NOT_ENFORCED = "not_enforced"
CONDITION_AMBIGUOUS = "ambiguous"
CONDITION_NOT_APPLICABLE = "not_applicable"

CONSTRAINT_SATISFIED = "satisfied"
CONSTRAINT_VIOLATED = "violated"
CONSTRAINT_AMBIGUOUS = "ambiguous"
CONSTRAINT_NOT_APPLICABLE = "not_applicable"

EXCEPTION_HANDLED = "handled"
EXCEPTION_NOT_HANDLED = "not_handled"
EXCEPTION_AMBIGUOUS = "ambiguous"
EXCEPTION_NOT_APPLICABLE = "not_applicable"

PROHIBITED_PRESENT = "present"
PROHIBITED_ABSENT = "absent"
PROHIBITED_UNKNOWN = "unknown"
PROHIBITED_NOT_APPLICABLE = "not_applicable"

RULE_FIELDS = {
    "required_condition_not_enforced": "condition",
    "constraint_violated": "constraint",
    "exception_not_handled": "exception",
}

# ---------------------------------------------------------------------------
# text normalisation and lexical signals
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset("""
a an the of to and or in on for with by from as is are be been being was were
that this these those it its he she they them his her their our your we you i
not no nor shall must may should will would can could have has had do does did
where when if then than there here also such other others any all each both
more most some at any within without under over into onto about after before
""".split())


def fold_whitespace(text: Any) -> str:
    return " ".join(str(text or "").split())


def normalize_text(text: Any) -> str:
    """Lowercase, punctuation-fold, collapse whitespace.  No synonym edits."""
    folded = re.sub(r"[^a-z0-9]+", " ", str(text or "").lower())
    return " ".join(folded.split())


def _stem(token: str) -> str:
    """Small deterministic stem used only for lexical candidate ranking.

    It never rewrites the stored text; it only lets morphological variants such
    as ``rectify`` / ``rectification`` share a ranking feature.
    """
    token = token.lower()
    for suffix in ("ations", "ation", "ments", "ment", "ings", "ing", "edly",
                   "ed", "ies", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            token = token[: len(token) - len(suffix)]
            break
    if token.endswith("i") and len(token) > 3:
        token = token[:-1] + "y"
    return token or "_"


def content_tokens(text: Any) -> list[str]:
    return [
        _stem(token)
        for token in re.findall(r"[a-z0-9]+", str(text or "").lower())
        if token not in _STOPWORDS and len(token) >= 3
    ]


def token_coverage(required: Any, candidate: Any) -> float:
    """Share of required content stems present anywhere in the candidate."""
    required_tokens = Counter(content_tokens(required))
    if not required_tokens:
        return 0.0
    candidate_tokens = Counter(content_tokens(candidate))
    matched = sum((required_tokens & candidate_tokens).values())
    return matched / sum(required_tokens.values())


def token_jaccard(left: Any, right: Any) -> float:
    left_set = set(content_tokens(left))
    right_set = set(content_tokens(right))
    if not left_set and not right_set:
        return 0.0
    return len(left_set & right_set) / max(1, len(left_set | right_set))


def text_equivalent(required: Any, candidate: Any) -> bool:
    """Deterministic evidence match; no free-form similarity verdict.

    A match requires either the normalized full phrase to be contained in the
    candidate (for non-trivial phrases) or at least 80% of the required content
    stems to be present in the candidate.
    """
    required_norm = normalize_text(required)
    candidate_norm = normalize_text(candidate)
    if not required_norm or not candidate_norm:
        return False
    if required_norm == candidate_norm:
        return True
    if len(required_norm) >= 5 and (required_norm in candidate_norm
                                    or candidate_norm in required_norm):
        return True
    required_tokens = ContentSet(required)
    if not required_tokens:
        return False
    candidate_tokens = set(content_tokens(candidate))
    return len(required_tokens & candidate_tokens) / len(required_tokens) >= 0.8


def ContentSet(text: Any) -> set[str]:  # noqa: N802 - public test helper style
    return set(content_tokens(text))


def _action_rows(model: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for action in getattr(model, "actions", []) or []:
        if isinstance(action, Mapping):
            node = dict(action)
        else:
            node = {
                "id": getattr(action, "id", None) or getattr(action, "activity_id", None),
                "name": getattr(action, "name", "") or getattr(action, "label", ""),
                "kind": getattr(action, "kind", None),
            }
        if node.get("kind") and node.get("kind") != "activity":
            continue
        if not str(node.get("id") or "").strip() or not str(node.get("name") or "").strip():
            continue
        rows.append({"id": str(node["id"]), "name": fold_whitespace(node["name"]),
                     "kind": str(node.get("kind") or "activity")})
    return rows


def _owner_names(record: Mapping[str, Any], activity_id: str) -> list[str]:
    names: list[str] = []
    for lane in record.get("lanes", []) or []:
        if activity_id in (lane.get("flow_node_refs") or []):
            name = fold_whitespace(lane.get("name"))
            if name:
                names.append(name)
    process_id = record.get("process_id")
    for pool in record.get("pools", []) or []:
        if pool.get("process_ref") == process_id:
            name = fold_whitespace(pool.get("name"))
            if name:
                names.append(name)
    return list(dict.fromkeys(names))


def ground_action(action_text: Any, model: Any, record: Mapping[str, Any],
                  sim_action: Callable[[str, str], float], *,
                  gamma: float = 0.4,
                  top_k_similarity: int = 5,
                  top_k_lexical: int = 5,
                  lexical_strong: float = 0.5,
                  lexical_supported: float = 0.3,
                  similarity_supported: float = 0.3,
                  resolved_margin: float = 0.15) -> dict[str, Any]:
    """Deterministically ground one rule action to zero or more activities.

    The returned candidate set is the union of the top semantic-similarity
    candidates, top lexical-overlap candidates, exact normalized matches, and
    activities with strong lexical coverage.  A single candidate is *not*
    forced when the matcher is undecided: the checks may consume the candidate
    set if their local surfaces agree, or trigger the semantic fallback.
    """
    action_text = fold_whitespace(action_text)
    if not action_text:
        return {
            "schema": "s3_semantic_grounding_action@1.0.0",
            "status": ACTION_STATUS_UNRESOLVED,
            "reason": "empty_rule_action",
            "activity_id": None,
            "candidates": [],
            "candidate_activity_ids": [],
            "alternatives": [],
        }

    rows: list[dict[str, Any]] = []
    for action in _action_rows(model):
        try:
            similarity = float(sim_action(action_text, action["name"]))
        except Exception:
            similarity = 0.0
        coverage = token_coverage(action_text, action["name"])
        exact = normalize_text(action_text) == normalize_text(action["name"])
        owners = _owner_names(record, action["id"])
        actor_match = max(
            [token_jaccard(action_text, owner) for owner in owners] or [0.0]
        )
        rows.append({
            "activity_id": action["id"],
            "label": action["name"],
            "owners": owners,
            "similarity": round(similarity, 6),
            "lexical_coverage": round(coverage, 6),
            "token_jaccard": round(token_jaccard(action_text, action["name"]), 6),
            "actor_token_match": round(actor_match, 6),
            "exact_normalized": exact,
        })

    if not rows:
        return {
            "schema": "s3_semantic_grounding_action@1.0.0",
            "status": ACTION_STATUS_UNRESOLVED,
            "reason": "no_process_activities",
            "activity_id": None,
            "candidates": [],
            "candidate_activity_ids": [],
            "alternatives": [],
        }

    by_similarity = sorted(rows, key=lambda r: (-r["similarity"], r["activity_id"]))
    by_lexical = sorted(rows, key=lambda r: (-r["lexical_coverage"],
                                             -r["token_jaccard"],
                                             r["activity_id"]))
    exact_ids = [r["activity_id"] for r in rows if r["exact_normalized"]]
    strong_lexical_ids = [r["activity_id"] for r in by_lexical
                          if r["lexical_coverage"] >= lexical_strong]
    candidate_ids: list[str] = []
    for item in (by_similarity[:top_k_similarity] + by_lexical[:top_k_lexical]
                 + [r for r in rows if r["activity_id"] in exact_ids]
                 + [r for r in rows if r["activity_id"] in strong_lexical_ids]):
        activity_id = item["activity_id"]
        if activity_id not in candidate_ids:
            candidate_ids.append(activity_id)

    top_similarity = by_similarity[0]["similarity"]
    second_similarity = (by_similarity[1]["similarity"]
                         if len(by_similarity) > 1 else 0.0)
    similarity_margin = top_similarity - second_similarity
    top_coverage = by_lexical[0]["lexical_coverage"]
    second_coverage = (by_lexical[1]["lexical_coverage"]
                       if len(by_lexical) > 1 else 0.0)
    content_count = len(content_tokens(action_text))

    strong_ids: list[str] = []
    lexical_margin = top_coverage - second_coverage
    for row in rows:
        if row["exact_normalized"]:
            strong_ids.append(row["activity_id"])
        elif row["lexical_coverage"] >= lexical_strong:
            strong_ids.append(row["activity_id"])
        elif (row["lexical_coverage"] >= lexical_supported
              and lexical_margin >= 0.15):
            # A uniquely leading content-token overlap is a structured lexical
            # grounding signal even when the semantic backend scale is low.
            strong_ids.append(row["activity_id"])
        elif (row["lexical_coverage"] >= lexical_supported
              and row["similarity"] >= similarity_supported):
            strong_ids.append(row["activity_id"])
        elif (row["similarity"] >= gamma
              and similarity_margin >= resolved_margin
              and content_count >= 2):
            strong_ids.append(row["activity_id"])
        elif (row["similarity"] >= 0.5
              and similarity_margin >= 0.1
              and row["lexical_coverage"] >= 0.2):
            strong_ids.append(row["activity_id"])
    strong_ids = list(dict.fromkeys(strong_ids))

    any_signal = any(r["similarity"] >= 0.2 or r["lexical_coverage"] >= 0.2
                     for r in rows)
    if exact_ids and len(exact_ids) == 1:
        status = ACTION_STATUS_RESOLVED
        reason = "unique_exact_normalized_label"
        resolved_id = exact_ids[0]
    elif not any_signal:
        status = ACTION_STATUS_UNRESOLVED
        reason = "no_activity_with_semantic_or_lexical_signal"
        resolved_id = None
    elif strong_ids:
        status = ACTION_STATUS_RESOLVED
        reason = "strong_candidate_signal"
        strong_rows = [r for r in rows if r["activity_id"] in strong_ids]
        strong_rows.sort(key=lambda r: (-r["lexical_coverage"], -r["similarity"],
                                        r["activity_id"]))
        resolved_id = strong_rows[0]["activity_id"]
    else:
        status = ACTION_STATUS_AMBIGUOUS
        reason = "multiple_or_weak_activity_candidates"
        resolved_id = None

    by_id = {r["activity_id"]: r for r in rows}
    alternatives = [by_id[activity_id] for activity_id in candidate_ids]
    return {
        "schema": "s3_semantic_grounding_action@1.0.0",
        "status": status,
        "reason": reason,
        "activity_id": resolved_id,
        "candidate_activity_ids": candidate_ids,
        "candidates": alternatives,
        "alternatives": alternatives,
        "top_similarity": round(top_similarity, 6),
        "second_similarity": round(second_similarity, 6),
        "similarity_margin": round(similarity_margin, 6),
        "top_lexical_coverage": round(top_coverage, 6),
        "second_lexical_coverage": round(second_coverage, 6),
        "content_token_count": content_count,
        "strong_activity_ids": strong_ids,
        "no_forced_resolution": True,
    }


# ---------------------------------------------------------------------------
# local BPMN graph / XML context
# ---------------------------------------------------------------------------


def _local(tag: Any) -> str:
    text = str(tag)
    return text.rsplit("}", 1)[-1] if "}" in text else text


def _element_texts(element: Any) -> list[str]:
    """Name plus flattened text of one XML element, deduplicated."""
    values: list[str] = []
    name = fold_whitespace(element.get("name") if hasattr(element, "get") else "")
    if name:
        values.append(name)
    try:
        text = " ".join("".join(element.itertext()).split())
    except Exception:
        text = ""
    if text and text != name:
        values.append(fold_whitespace(text))
    return list(dict.fromkeys(v for v in values if v))


def _element_by_id(xml_root: Any) -> dict[str, Any]:
    return {
        str(element.get("id")): element
        for element in xml_root.iter()
        if element.get("id")
    }


def _parent_map(xml_root: Any) -> dict[Any, Any]:
    parents: dict[Any, Any] = {}
    for parent in xml_root.iter():
        for child in parent:
            parents[child] = parent
    return parents


def _node_maps(record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    for collection, kind in (("activities", "activity"),
                             ("events", "event"),
                             ("gateways", "gateway")):
        for node in record.get(collection, []) or []:
            nodes[str(node.get("id"))] = {
                "id": str(node.get("id")),
                "name": fold_whitespace(node.get("name")),
                "kind": kind,
            }
    return nodes


def _graph(record: Mapping[str, Any]) -> tuple[dict[str, list[dict[str, Any]]],
                                               dict[str, list[dict[str, Any]]]]:
    successors: dict[str, list[dict[str, Any]]] = defaultdict(list)
    predecessors: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for flow in record.get("sequence_flows", []) or []:
        source = str(flow.get("source_ref"))
        target = str(flow.get("target_ref"))
        successors[source].append(flow)
        predecessors[target].append(flow)
    return successors, predecessors


def _upstream_context(record: Mapping[str, Any], activity_id: str,
                      max_depth: int = 6) -> dict[str, Any]:
    successors, predecessors = _graph(record)
    nodes = _node_maps(record)
    visited_nodes: set[str] = set()
    visited_flows: dict[str, dict[str, Any]] = {}
    queue: deque[tuple[str, int]] = deque([(activity_id, 0)])
    truncated = False
    while queue:
        node_id, depth = queue.popleft()
        if node_id in visited_nodes:
            continue
        visited_nodes.add(node_id)
        if depth >= max_depth:
            if predecessors.get(node_id):
                truncated = True
            continue
        for flow in predecessors.get(node_id, []):
            flow_id = str(flow.get("id"))
            visited_flows[flow_id] = flow
            source = str(flow.get("source_ref"))
            if source not in visited_nodes:
                queue.append((source, depth + 1))
            if nodes.get(source, {}).get("kind") == "gateway":
                for sibling in successors.get(source, []):
                    visited_flows[str(sibling.get("id"))] = sibling
    return {
        "target_activity_id": activity_id,
        "nodes": sorted(visited_nodes),
        "flows": visited_flows,
        "has_incoming_flow": bool(predecessors.get(activity_id)),
        "scope_complete": not truncated,
        "max_depth": max_depth,
    }


def _downstream_context(record: Mapping[str, Any], activity_id: str,
                        max_depth: int = 8, max_nodes: int = 500) -> dict[str, Any]:
    successors, _ = _graph(record)
    visited_nodes: set[str] = set()
    visited_flows: dict[str, dict[str, Any]] = {}
    queue: deque[tuple[str, int]] = deque([(activity_id, 0)])
    budget_exceeded = False
    while queue:
        node_id, depth = queue.popleft()
        if node_id in visited_nodes:
            continue
        if len(visited_nodes) >= max_nodes:
            budget_exceeded = True
            break
        visited_nodes.add(node_id)
        if depth >= max_depth:
            if successors.get(node_id):
                budget_exceeded = True
            continue
        for flow in successors.get(node_id, []):
            visited_flows[str(flow.get("id"))] = flow
            target = str(flow.get("target_ref"))
            if target not in visited_nodes:
                queue.append((target, depth + 1))
    return {
        "target_activity_id": activity_id,
        "nodes": sorted(visited_nodes),
        "flows": visited_flows,
        "scope_complete": not budget_exceeded,
        "max_depth": max_depth,
        "max_nodes": max_nodes,
    }


def _boundary_handler_texts(record: Mapping[str, Any], xml_root: Any,
                            boundary_id: str) -> list[str]:
    successors, _ = _graph(record)
    texts: list[str] = []
    queue: deque[tuple[str, int]] = deque([(boundary_id, 0)])
    visited: set[str] = set()
    while queue:
        node_id, depth = queue.popleft()
        if node_id in visited or depth > 3:
            continue
        visited.add(node_id)
        if depth > 0:
            for node in _node_maps(record).values():
                if node["id"] == node_id and node["name"]:
                    texts.append(node["name"])
        for flow in successors.get(node_id, []):
            queue.append((str(flow.get("target_ref")), depth + 1))
    return list(dict.fromkeys(texts))


def _nested_time_texts(element: Any) -> list[str]:
    texts: list[str] = []
    for descendant in element.iter():
        if _local(descendant.tag) in {
            "timerEventDefinition", "timeDate", "timeDuration", "timeCycle",
            "startEvent", "intermediateCatchEvent", "boundaryEvent",
        }:
            texts.extend(_element_texts(descendant))
    return list(dict.fromkeys(texts))


def _time_values(text: Any) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for match in _TIME_VALUE_RE.finditer(str(text or "")):
        unit = match.group(2).lower()
        unit = unit[:-1] if unit.endswith("s") else unit
        if unit in ("month", "year"):
            values.append({"hours": None, "value": match.group(0),
                           "unit": unit, "unsupported_calendar_unit": True})
            continue
        values.append({
            "hours": int(match.group(1)) * _UNIT_HOURS.get(unit, 1),
            "value": match.group(0),
            "unit": unit,
            "unsupported_calendar_unit": False,
        })
    return values


_TIME_UPPER_BOUND_RE = re.compile(
    r"\s*(?:(?:not|no)\s+later\s+than|within|at\s+most)\s+"
    r"(\d+)\s*(hours?|hrs?|days?|weeks?)\s*[.,]?\s*",
    re.IGNORECASE,
)


def numeric_upper_bound(rule_constraint: Any) -> dict[str, Any] | None:
    text = fold_whitespace(rule_constraint)
    match = _TIME_UPPER_BOUND_RE.fullmatch(text)
    if not match:
        return None
    unit = match.group(2).lower()
    unit = unit[:-1] if unit.endswith("s") else unit
    return {"value": match.group(0), "hours": int(match.group(1)) * _UNIT_HOURS.get(unit, 1),
            "unit": unit}


def _constraint_kind(rule_constraint: str) -> str | None:
    # Imported lazily so the module remains usable in small focused tests.
    from bpc_hybrid.stage3_extended_violations import _extract_constraint
    return _extract_constraint(rule_constraint or "")[1]


def collect_condition_surface(record: Mapping[str, Any], activity_id: str, *,
                              max_depth: int = 6) -> dict[str, Any]:
    context = _upstream_context(record, activity_id, max_depth=max_depth)
    nodes = _node_maps(record)
    direct: list[dict[str, Any]] = []
    weak: list[dict[str, Any]] = []
    for flow_id, flow in sorted(context["flows"].items()):
        if (flow.get("condition_expression") or "").strip():
            direct.append({"id": flow_id, "text": fold_whitespace(flow["condition_expression"]),
                           "kind": "condition_expression"})
        if (flow.get("name") or "").strip():
            weak.append({"id": flow_id, "text": fold_whitespace(flow["name"]),
                         "kind": "flow_label"})
    for node_id in context["nodes"]:
        node = nodes.get(node_id)
        if node and node["kind"] == "gateway" and node["name"]:
            weak.append({"id": node_id, "text": node["name"], "kind": "gateway_label"})
    return {
        "activity_id": activity_id,
        "direct_evidence": direct,
        "weak_context": weak,
        "has_incoming_flow": context["has_incoming_flow"],
        "scope_complete": context["scope_complete"],
        "scope_statement": ("incoming sequence flows of the grounded activity, their "
                            "condition expressions, and the gateways and sibling "
                            "branches on the same upstream branch"),
    }


def collect_constraint_surface(record: Mapping[str, Any], xml_root: Any,
                               activity_ids: Sequence[str], *,
                               max_depth: int = 8) -> dict[str, Any]:
    nodes = _node_maps(record)
    relevant: set[str] = set(activity_ids)
    complete = True
    for activity_id in activity_ids:
        context = _downstream_context(record, activity_id, max_depth=max_depth)
        relevant.update(context["nodes"])
        complete = complete and context["scope_complete"]
    elements = _element_by_id(xml_root)
    parents = _parent_map(xml_root)
    bound: list[dict[str, Any]] = []
    bound_ids: set[str] = set()
    for node_id in sorted(relevant):
        element = elements.get(node_id)
        if element is None:
            continue
        kind = _local(element.tag)
        texts = _element_texts(element)
        if kind == "subProcess":
            texts = list(dict.fromkeys(texts + _nested_time_texts(element)))
        for text in texts:
            if _time_values(text):
                bound.append({"id": node_id, "text": text, "kind": kind,
                              "relation": "action_anchored_node_time"})
                bound_ids.add(node_id)
        if kind in {"boundaryEvent", "intermediateCatchEvent", "startEvent"}:
            for text in texts:
                if _time_values(text):
                    bound.append({"id": node_id, "text": text, "kind": kind,
                                  "relation": "bound_event_time"})
                    bound_ids.add(node_id)
    # boundary events attached to a locally reached activity
    for element in xml_root.iter():
        if _local(element.tag) != "boundaryEvent":
            continue
        attached = str(element.get("attachedToRef"))
        if attached in relevant:
            for text in _element_texts(element):
                bound.append({"id": str(element.get("id")), "text": text,
                              "kind": "boundaryEvent",
                              "relation": "attached_boundary_event"})
                bound_ids.add(str(element.get("id")))
    # annotations / data objects associated with locally reached nodes
    for element in xml_root.iter():
        kind = _local(element.tag)
        if kind == "association":
            ends = [str(element.get("sourceRef") or ""), str(element.get("targetRef") or "")]
            if any(one in relevant for one in ends):
                other = ends[1] if ends[0] in relevant else ends[0]
                target = elements.get(other)
                if target is not None and _local(target.tag) in {
                    "textAnnotation", "dataObject", "dataObjectReference",
                    "dataStore", "dataStoreReference",
                }:
                    for text in _element_texts(target):
                        bound.append({"id": other, "text": text,
                                      "kind": _local(target.tag),
                                      "relation": "associated_annotation_or_data"})
                        bound_ids.add(other)
        if kind in {"dataObjectReference", "dataStoreReference", "dataObject", "dataStore"}:
            refs = {str(element.get("sourceRef") or ""),
                    str(element.get("targetRef") or ""),
                    str(element.get("dataObjectRef") or ""),
                    str(element.get("dataStoreRef") or "")}
            if refs & relevant:
                for text in _element_texts(element):
                    bound.append({"id": str(element.get("id")), "text": text,
                                  "kind": kind, "relation": "action_associated_data"})
                    bound_ids.add(str(element.get("id")))
    # unbound evidence: relevant to detect a semantic equivalent outside scope
    unbound: list[dict[str, Any]] = []
    for element in xml_root.iter():
        element_id = str(element.get("id") or "")
        if element_id and element_id in bound_ids:
            continue
        kind = _local(element.tag)
        if kind not in {"dataObject", "dataObjectReference", "dataStore",
                        "dataStoreReference", "textAnnotation",
                        "timerEventDefinition", "timeDate", "timeDuration", "timeCycle"}:
            continue
        for text in _element_texts(element):
            if not _time_values(text) and kind not in {"dataObject", "dataObjectReference",
                                                        "dataStore", "dataStoreReference",
                                                        "textAnnotation"}:
                continue
            unbound.append({"id": element_id, "text": text, "kind": kind,
                            "relation": "unbound_global_candidate"})
    return {
        "activity_ids": list(activity_ids),
        "bound": bound,
        "bound_ids": sorted(bound_ids),
        "unbound": unbound,
        "scope_complete": complete,
        "scope_statement": ("local downstream control flow of the grounded candidate "
                            "activities, nested subProcess timers reached through it, "
                            "attached boundary timers, and annotations/data associated "
                            "with those locally reached nodes"),
    }


_EXCEPTION_CUE_RE = re.compile(
    r"\b(error|exception|handler|fallback|alternat|abort|cancel|reject|denied|"
    r"escalat|compensat|failure|fails?|not\s+possible|unable)\w*", re.IGNORECASE)


def _has_exception_cue(text: Any) -> bool:
    return bool(_EXCEPTION_CUE_RE.search(str(text or "")))


def collect_exception_surface(record: Mapping[str, Any], xml_root: Any,
                              activity_ids: Sequence[str], *,
                              max_depth: int = 8) -> dict[str, Any]:
    nodes = _node_maps(record)
    relevant: set[str] = set(activity_ids)
    complete = True
    for activity_id in activity_ids:
        context = _downstream_context(record, activity_id, max_depth=max_depth)
        relevant.update(context["nodes"])
        complete = complete and context["scope_complete"]
    elements = _element_by_id(xml_root)
    parents = _parent_map(xml_root)
    handler_candidates: list[dict[str, Any]] = []
    matched: list[dict[str, Any]] = []
    ids: set[str] = set()
    def add_candidate(evidence_id: str, text: str, kind: str,
                      dedicated: bool) -> None:
        if not text.strip():
            return
        ids.add(evidence_id)
        handler_candidates.append({"id": evidence_id, "text": text, "kind": kind,
                                   "dedicated_handler_structure": dedicated})
    # boundary events attached to a locally reached node
    for element in xml_root.iter():
        if _local(element.tag) != "boundaryEvent":
            continue
        boundary_id = str(element.get("id") or "")
        if str(element.get("attachedToRef")) not in relevant:
            continue
        texts = _element_texts(element)
        for text in texts:
            add_candidate(boundary_id, text, "boundary_event", True)
        # error/escalation definitions referenced by this boundary
        for child in element.iter():
            if _local(child.tag) in {"errorEventDefinition", "escalationEventDefinition"}:
                ref_id = str(child.get("errorRef") or child.get("escalationRef") or "")
                ref = elements.get(ref_id)
                if ref is not None:
                    for text in _element_texts(ref):
                        add_candidate(ref_id, text, _local(ref.tag), True)
        # handler tasks reachable from the boundary event
        for text in _boundary_handler_texts(record, xml_root, boundary_id):
            add_candidate(f"handler_of:{boundary_id}", text, "boundary_handler", True)
    # error / escalation definitions whose owning element is locally reached
    for element in xml_root.iter():
        if _local(element.tag) not in {"error", "escalation"}:
            continue
        owner = None
        current = parents.get(element)
        while current is not None:
            if current.get("id") and _local(current.tag) == "boundaryEvent":
                owner = str(current.get("id"))
                break
            current = parents.get(current)
        if owner in relevant:
            for text in _element_texts(element):
                add_candidate(str(element.get("id") or owner), text,
                              _local(element.tag), True)
    # any locally reached activity label may itself be the rule exception handler
    for node_id in sorted(relevant):
        node = nodes.get(node_id)
        if node and node["name"]:
            add_candidate(node_id, node["name"], "local_activity_label", False)
    # alternate branches out of locally reached branching gateways
    successors, _ = _graph(record)
    branch_ids: set[str] = set()
    for gateway_id in sorted(relevant):
        if nodes.get(gateway_id, {}).get("kind") != "gateway":
            continue
        branches = successors.get(gateway_id, [])
        if len(branches) <= 1:
            continue
        for flow in branches:
            target = str(flow.get("target_ref"))
            target_name = nodes.get(target, {}).get("name", "")
            flow_name = fold_whitespace(flow.get("name"))
            text = " ".join(v for v in (target_name, flow_name) if v)
            if text:
                add_candidate(
                    f"branch:{flow.get('id')}", text, "alternate_branch",
                    _has_exception_cue(text) or _has_exception_cue(target_name),
                )
                branch_ids.add(target)
    return {
        "activity_ids": list(activity_ids),
        "handler_candidates": handler_candidates,
        "candidate_ids": sorted(ids),
        "branch_target_ids": sorted(branch_ids),
        "scope_complete": complete,
        "scope_statement": ("boundary/error/escalation handlers attached to locally "
                            "reached activities and alternate branches of locally "
                            "reached branching gateways"),
    }


# ---------------------------------------------------------------------------
# deterministic checks
# ---------------------------------------------------------------------------


def _unknown(check: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {"check": check, "status": "unknown", "observable": False,
            "violation": None, "reason": reason, "score": None, **extra}


def _applicable(check: str, status: str, reason: str, *, violation: bool,
                **extra: Any) -> dict[str, Any]:
    return {"check": check, "status": status, "observable": True,
            "violation": violation, "reason": reason,
            "score": 1.0 if violation else 0.0, **extra}


def check_prohibited(sentence: Mapping[str, Any], ground: Mapping[str, Any]) -> dict[str, Any]:
    if sentence.get("modality") != "prohibition":
        return {"check": "prohibited_action_present", "status": PROHIBITED_NOT_APPLICABLE,
                "observable": True, "violation": False,
                "reason": "rule_modality_not_prohibition", "score": 0.0}
    action = fold_whitespace(sentence.get("action"))
    if not action:
        return _unknown("prohibited_action_present", "empty_rule_action")
    if ground.get("status") == ACTION_STATUS_UNRESOLVED:
        return _unknown("prohibited_action_present", "action_grounding_unresolved",
                        action_grounding=dict(ground))
    candidates = [c for c in ground.get("candidates", [])
                  if c.get("activity_id") in set(ground.get("candidate_activity_ids", []))]
    presence = [c for c in candidates
                if text_equivalent(action, c.get("label"))
                or (float(c.get("lexical_coverage") or 0.0) >= 0.8
                    and float(c.get("similarity") or 0.0) >= 0.6)]
    if presence:
        return _applicable("prohibited_action_present", PROHIBITED_PRESENT,
                           "prohibited_action_explicitly_present", violation=True,
                           evidence=[{"activity_id": c["activity_id"],
                                      "label": c.get("label")} for c in presence])
    return _applicable("prohibited_action_present", PROHIBITED_ABSENT,
                       "no_explicit_prohibited_action_activity", violation=False,
                       evidence=[])


def check_condition(sentence: Mapping[str, Any], record: Mapping[str, Any],
                    ground: Mapping[str, Any]) -> dict[str, Any]:
    rule = fold_whitespace(sentence.get("condition"))
    if not rule:
        return {"check": "required_condition_not_enforced",
                "status": CONDITION_NOT_APPLICABLE, "observable": True,
                "violation": False, "reason": "empty_rule_condition", "score": 0.0}
    if ground.get("status") == ACTION_STATUS_UNRESOLVED:
        return _unknown("required_condition_not_enforced",
                        "action_grounding_unresolved", action_grounding=dict(ground))
    candidates = list(ground.get("candidate_activity_ids") or [])
    if not candidates:
        return _unknown("required_condition_not_enforced", "no_candidate_activity")
    enforced: list[dict[str, Any]] = []
    absent: list[str] = []
    ambiguous: list[str] = []
    not_checkable: list[dict[str, str]] = []
    for activity_id in candidates:
        surface = collect_condition_surface(record, activity_id)
        hit = [evidence for evidence in surface["direct_evidence"] + surface["weak_context"]
               if text_equivalent(rule, evidence["text"])]
        if hit:
            enforced.append({"activity_id": activity_id, "evidence": hit})
            continue
        if not surface["scope_complete"]:
            ambiguous.append(activity_id)
            continue
        if not surface["has_incoming_flow"]:
            # An activity without an incoming sequence flow has no local slot on
            # which the rule condition could be observed.  It cannot support a
            # positive compliance verdict, but it must not veto a negative
            # verdict observed on the other, fully inspectable candidates.
            not_checkable.append({"activity_id": activity_id,
                                   "reason": "no_incoming_sequence_flow"})
            continue
        if surface["direct_evidence"]:
            ambiguous.append(activity_id)
            continue
        absent.append(activity_id)
    if enforced:
        return _applicable("required_condition_not_enforced", CONDITION_ENFORCED,
                           "condition_evidence_found_on_action_anchored_surface",
                           violation=False, evidence=enforced,
                           action_grounding_status=ground.get("status"))
    if ambiguous:
        return _unknown("required_condition_not_enforced",
                        "condition_surface_ambiguous_or_incomplete",
                        candidate_activity_ids=candidates,
                        ambiguous_candidate_activity_ids=ambiguous)
    if absent:
        return _applicable("required_condition_not_enforced", CONDITION_NOT_ENFORCED,
                           "condition_absent_from_fully_enumerated_action_anchored_surface",
                           violation=True, evidence=[],
                           candidate_activity_ids=candidates,
                           absent_candidate_activity_ids=absent,
                           not_checkable_candidates=not_checkable,
                           action_grounding_status=ground.get("status"))
    if not_checkable:
        return _unknown("required_condition_not_enforced",
                        "no_candidate_has_an_incoming_condition_surface",
                        candidate_activity_ids=candidates,
                        not_checkable_candidates=not_checkable)
    return _unknown("required_condition_not_enforced",
                    "condition_absence_not_consensual_across_candidates",
                    candidate_activity_ids=candidates)


def check_constraint(sentence: Mapping[str, Any], record: Mapping[str, Any],
                     xml_root: Any, ground: Mapping[str, Any]) -> dict[str, Any]:
    rule = fold_whitespace(sentence.get("constraint"))
    if not rule:
        return {"check": "constraint_violated", "status": CONSTRAINT_NOT_APPLICABLE,
                "observable": True, "violation": False,
                "reason": "empty_rule_constraint", "score": 0.0}
    if ground.get("status") == ACTION_STATUS_UNRESOLVED:
        return _unknown("constraint_violated", "action_grounding_unresolved",
                        action_grounding=dict(ground))
    candidates = list(ground.get("candidate_activity_ids") or [])
    if not candidates:
        return _unknown("constraint_violated", "no_candidate_activity")
    surface = collect_constraint_surface(record, xml_root, candidates)
    kind = _constraint_kind(rule)
    if kind != "time_limit":
        return _unknown("constraint_violated",
                        "unsupported_abstract_constraint_kind",
                        constraint_kind=kind,
                        bound_evidence=surface["bound"],
                        unbound_evidence=surface["unbound"],
                        action_grounding_status=ground.get("status"))
    bound = numeric_upper_bound(rule)
    if bound is None:
        return _unknown("constraint_violated", "rule_bound_not_explicit_upper_limit",
                        bound_evidence=surface["bound"])
    observed: list[dict[str, Any]] = []
    for evidence in surface["bound"]:
        for value in _time_values(evidence["text"]):
            if value["hours"] is None:
                return _unknown("constraint_violated",
                                "calendar_duration_not_deterministically_comparable",
                                evidence=evidence)
            observed.append({"evidence": evidence, "hours": value["hours"],
                             "value": value["value"]})
    violated = [item for item in observed if item["hours"] > bound["hours"]]
    satisfied = [item for item in observed if item["hours"] <= bound["hours"]]
    if (violated or satisfied) and ground.get("status") != ACTION_STATUS_RESOLVED:
        return _unknown(
            "constraint_violated",
            "numeric_time_evidence_found_but_action_grounding_ambiguous",
            bound_evidence=surface["bound"],
            observed_time_values=observed,
            action_grounding_status=ground.get("status"),
        )
    if violated:
        return _applicable("constraint_violated", CONSTRAINT_VIOLATED,
                           "explicit_numeric_time_bound_exceeds_rule_limit",
                           violation=True, evidence=violated,
                           rule_bound=bound)
    if satisfied:
        return _applicable("constraint_violated", CONSTRAINT_SATISFIED,
                           "explicit_numeric_time_bound_is_equal_or_tighter",
                           violation=False, evidence=satisfied, rule_bound=bound)
    if surface["unbound"]:
        return _unknown("constraint_violated",
                        "unbound_global_constraint_evidence_requires_semantic_grounding",
                        bound_evidence=surface["bound"],
                        unbound_evidence=surface["unbound"])
    if not surface["scope_complete"]:
        return _unknown("constraint_violated", "constraint_surface_incomplete",
                        bound_evidence=surface["bound"])
    if ground.get("status") == ACTION_STATUS_RESOLVED:
        return _applicable("constraint_violated", CONSTRAINT_VIOLATED,
                           "explicit_time_bound_absent_from_closed_action_scope",
                           violation=True, evidence=[], rule_bound=bound,
                           action_grounding_status=ground.get("status"))
    return _unknown("constraint_violated",
                    "time_bound_absence_not_decidable_from_ambiguous_grounding",
                    bound_evidence=surface["bound"])


def check_exception(sentence: Mapping[str, Any], record: Mapping[str, Any],
                    xml_root: Any, ground: Mapping[str, Any]) -> dict[str, Any]:
    rule = fold_whitespace(sentence.get("exception"))
    if not rule:
        return {"check": "exception_not_handled", "status": EXCEPTION_NOT_APPLICABLE,
                "observable": True, "violation": False,
                "reason": "empty_rule_exception", "score": 0.0}
    if ground.get("status") == ACTION_STATUS_UNRESOLVED:
        return _unknown("exception_not_handled", "action_grounding_unresolved",
                        action_grounding=dict(ground))
    candidates = list(ground.get("candidate_activity_ids") or [])
    if not candidates:
        return _unknown("exception_not_handled", "no_candidate_activity")
    surface = collect_exception_surface(record, xml_root, candidates)
    matched = [c for c in surface["handler_candidates"]
               if text_equivalent(rule, c["text"])]
    if matched:
        return _applicable("exception_not_handled", EXCEPTION_HANDLED,
                           "exception_handler_evidence_found",
                           violation=False, evidence=matched,
                           action_grounding_status=ground.get("status"))
    dedicated = [c for c in surface["handler_candidates"]
                 if c.get("dedicated_handler_structure")]
    if dedicated:
        return _unknown("exception_not_handled",
                        "dedicated_handler_candidate_exists_but_semantics_ambiguous",
                        handler_candidates=dedicated)
    if not surface["scope_complete"]:
        return _unknown("exception_not_handled", "exception_surface_incomplete")
    if ground.get("status") == ACTION_STATUS_RESOLVED:
        return _applicable("exception_not_handled", EXCEPTION_NOT_HANDLED,
                           "no_structurally_relevant_handler_in_closed_downstream_surface",
                           violation=True, evidence=[],
                           action_grounding_status=ground.get("status"))
    return _unknown("exception_not_handled",
                    "no_handler_and_action_grounding_ambiguous")


# ---------------------------------------------------------------------------
# programmatic aggregation
# ---------------------------------------------------------------------------


VIOLATION_PRIORITY = (
    # Explicit prohibition / explicit numeric contradiction / dedicated
    # structural handler absence are more specific than a condition absence on
    # the local control-flow surface.  The order is fixed in code and is not
    # changed per sample or per panel result.
    "prohibited_action_present",
    "constraint_violated",
    "exception_not_handled",
    "required_condition_not_enforced",
)


def decide(checks: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Final decision is made here, never by an LLM free-text answer."""
    for violation_type in VIOLATION_PRIORITY:
        check = checks.get(violation_type) or {}
        if check.get("violation") is True:
            return {"predicted": violation_type, "decision": "violation",
                    "reason": check.get("reason") or "programmatic_structural_violation",
                    "violation_type": violation_type,
                    "priority_policy": "explicit_structural_specificity_v1"}
    pending = [
        violation_type for violation_type in EXTENDED_TYPES
        if (checks.get(violation_type) or {}).get("status") in {
            "unknown", CONDITION_AMBIGUOUS, CONSTRAINT_AMBIGUOUS, EXCEPTION_AMBIGUOUS,
            ACTION_STATUS_UNRESOLVED,
        } and (checks.get(violation_type) or {}).get("status") != "not_applicable"
    ]
    if pending:
        return {"predicted": None, "decision": "abstention",
                "reason": "semantic_grounding_ambiguous",
                "pending_types": pending}
    applicable = [
        violation_type for violation_type in EXTENDED_TYPES
        if (checks.get(violation_type) or {}).get("observable") is True
    ]
    if applicable:
        return {"predicted": NONE_LABEL, "decision": "compliant",
                "reason": "all_applicable_checks_satisfied"}
    return {"predicted": None, "decision": "abstention",
            "reason": "no_applicable_check"}


class SemanticGroundingScorer:
    """Deterministic four-type scorer for one parsed process side.

    This class intentionally has no file-path, item-id, expected-label or
    mutation-metadata input.
    """

    def __init__(self, sim_action: Callable[[str, str], float],
                 gamma: float = 0.4, gamma_ext: float = 0.5,
                 config: Mapping[str, Any] | None = None):
        self.sim_action = sim_action
        self.gamma = float(gamma)
        self.gamma_ext = float(gamma_ext)
        config = config or {}
        thresholds = config.get("thresholds") or {}
        self.top_k_similarity = int(thresholds.get("action_top_k_similarity", 5))
        self.top_k_lexical = int(thresholds.get("action_top_k_lexical", 5))
        self.lexical_strong = float(thresholds.get("lexical_strong_coverage", 0.5))
        self.lexical_supported = float(thresholds.get("lexical_supported_coverage", 0.3))
        self.similarity_supported = float(thresholds.get("lexical_supported_similarity", 0.3))
        self.resolved_margin = float(thresholds.get("resolved_similarity_margin", 0.15))
        self.max_local_nodes = int(thresholds.get("max_local_nodes", 500))

    def score(self, sentence: Mapping[str, Any], model: Any,
              record: Mapping[str, Any], xml_root: Any) -> dict[str, Any]:
        ground = ground_action(
            sentence.get("action"), model, record, self.sim_action,
            gamma=self.gamma,
            top_k_similarity=self.top_k_similarity,
            top_k_lexical=self.top_k_lexical,
            lexical_strong=self.lexical_strong,
            lexical_supported=self.lexical_supported,
            similarity_supported=self.similarity_supported,
            resolved_margin=self.resolved_margin,
        )
        checks = {
            "prohibited_action_present": check_prohibited(sentence, ground),
            "required_condition_not_enforced": check_condition(sentence, record, ground),
            "constraint_violated": check_constraint(sentence, record, xml_root, ground),
            "exception_not_handled": check_exception(sentence, record, xml_root, ground),
        }
        decision = decide(checks)
        return {
            "schema_version": SCORE_SCHEMA,
            "revision": REVISION,
            "action_grounding": ground,
            "checks": checks,
            "decision": decision,
            "scores": {
                violation_type: (checks[violation_type].get("score")
                                 if checks[violation_type].get("observable") else None)
                for violation_type in EXTENDED_TYPES
            },
            "observability": {
                violation_type: {
                    "observable": bool(checks[violation_type].get("observable")),
                    "reason": checks[violation_type].get("reason"),
                    "status": checks[violation_type].get("status"),
                }
                for violation_type in EXTENDED_TYPES
            },
        }


# ---------------------------------------------------------------------------
# strict LLM semantic-grounding fallback (implementation + offline plumbing)
# ---------------------------------------------------------------------------


class LLMGroundingError(ValueError):
    """Raised for malformed, non-strict, or hallucinated fallback output."""


def build_llm_input(sentence: Mapping[str, Any], ground: Mapping[str, Any],
                    checks: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Build a compact structured fallback input; never send full XML/rule text."""
    candidates = []
    for row in (ground.get("alternatives") or [])[:5]:
        candidates.append({
            "activity_id": row.get("activity_id"),
            "label": row.get("label"),
            "owners": row.get("owners") or [],
            "local_similarity": row.get("similarity"),
            "local_lexical_coverage": row.get("lexical_coverage"),
        })
    evidence_ids: set[str] = set()
    for check in checks.values():
        for key in ("evidence", "handler_candidates", "bound_evidence",
                    "unbound_evidence"):
            values = check.get(key) or []
            if not isinstance(values, list):
                continue
            for item in values:
                if isinstance(item, Mapping):
                    for id_key in ("id", "activity_id"):
                        if item.get(id_key):
                            evidence_ids.add(str(item[id_key]))
    return {
        "schema_version": LLM_SCHEMA_VERSION,
        "rule_record": {
            "rule_id": sentence.get("rule_id"),
            "modality": sentence.get("modality"),
            "actor": sentence.get("actor"),
            "action": sentence.get("action"),
            "condition": sentence.get("condition"),
            "constraint": sentence.get("constraint"),
            "exception": sentence.get("exception"),
        },
        "candidate_activities": candidates,
        "candidate_activity_ids": [row.get("activity_id") for row in candidates
                                   if row.get("activity_id")],
        "local_context_evidence_ids": sorted(evidence_ids),
        "instruction": ("Return strict JSON only. Ground the rule semantics to the "
                        "provided local evidence ids; do not decide the final "
                        "violation. No markdown, no chain-of-thought, no new ids."),
    }


def _strict_json_object(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise LLMGroundingError("response is not text")
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        raise LLMGroundingError(f"invalid_json:{exc.msg}") from exc
    if not isinstance(value, dict):
        raise LLMGroundingError("response_root_not_object")
    return value


def _exact_keys(mapping: Mapping[str, Any], expected: set[str], label: str) -> None:
    got = set(mapping.keys())
    if got != expected:
        raise LLMGroundingError(
            f"{label}_keys:{sorted(got)} expected:{sorted(expected)}"
        )


def _confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LLMGroundingError("confidence_not_numeric")
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise LLMGroundingError("confidence_out_of_range")
    return number


def validate_llm_response(raw: Any, input_payload: Mapping[str, Any],
                          confidence_threshold: float = 0.8) -> dict[str, Any]:
    """Strict fail-closed validator for the fallback JSON contract.

    Returns ``{"status": "resolved", "response": ...}`` or
    ``{"status": "failed", "error": ...}``.  Any malformed field, unknown
    status, or hallucinated evidence id is a hard failure; the caller must then
    keep the item unknown.
    """
    try:
        data = _strict_json_object(raw)
        _exact_keys(data, {
            "schema_version", "action_grounding", "condition_grounding",
            "constraint_grounding", "exception_grounding",
        }, "top_level")
        if data["schema_version"] != LLM_SCHEMA_VERSION:
            raise LLMGroundingError("schema_version_mismatch")

        allowed_ids = {str(value) for value in
                       (input_payload.get("local_context_evidence_ids") or [])}
        candidate_ids = {str(value) for value in
                         (input_payload.get("candidate_activity_ids") or [])}
        fields = input_payload.get("rule_record") or {}

        action = data["action_grounding"]
        _exact_keys(action, {"status", "activity_id", "confidence"}, "action_grounding")
        if action["status"] not in {"matched", "ambiguous", "unmatched"}:
            raise LLMGroundingError("action_status_invalid")
        confidence = _confidence(action.get("confidence"))
        if confidence < float(confidence_threshold):
            raise LLMGroundingError("action_confidence_below_threshold")
        if action["status"] == "matched":
            if action.get("activity_id") not in candidate_ids:
                raise LLMGroundingError("action_activity_id_not_candidate")
        else:
            if action.get("activity_id") is not None:
                raise LLMGroundingError("nonmatched_action_must_have_null_activity_id")

        expected = {
            "condition_grounding": {
                "enforced", "not_enforced", "ambiguous", "not_applicable"},
            "constraint_grounding": {
                "satisfied", "violated", "ambiguous", "not_applicable"},
            "exception_grounding": {
                "handled", "not_handled", "ambiguous", "not_applicable"},
        }
        field_by_check = {
            "condition_grounding": "condition",
            "constraint_grounding": "constraint",
            "exception_grounding": "exception",
        }
        for key, statuses in expected.items():
            block = data[key]
            _exact_keys(block, {"status", "evidence_ids", "reason_code"}, key)
            if block["status"] not in statuses:
                raise LLMGroundingError(f"{key}_status_invalid")
            evidence_ids = block.get("evidence_ids")
            if not isinstance(evidence_ids, list) or not all(
                    isinstance(value, str) for value in evidence_ids):
                raise LLMGroundingError(f"{key}_evidence_ids_not_string_list")
            if any(value not in allowed_ids for value in evidence_ids):
                raise LLMGroundingError(f"{key}_hallucinated_evidence_id")
            reason_code = block.get("reason_code")
            if not isinstance(reason_code, str) or not re.fullmatch(
                    r"[a-z0-9_]{1,64}", reason_code):
                raise LLMGroundingError(f"{key}_reason_code_invalid")
            rule_present = bool(str(fields.get(field_by_check[key]) or "").strip())
            if block["status"] == "not_applicable" and rule_present:
                raise LLMGroundingError(f"{key}_not_applicable_but_rule_field_present")
            if block["status"] != "not_applicable" and not rule_present:
                raise LLMGroundingError(f"{key}_missing_rule_field_but_status_applicable")
            if block["status"] == "not_applicable" and evidence_ids:
                raise LLMGroundingError(f"{key}_not_applicable_with_evidence")
        return {"status": "resolved", "response": data}
    except LLMGroundingError as exc:
        return {"status": "failed", "error": str(exc)}


class SemanticGroundingLLMClient:
    """Minimal provider-independent protocol; no real network implementation."""

    def complete(self, prompt: str) -> str:  # pragma: no cover - protocol
        raise NotImplementedError


def run_llm_fallback(client: SemanticGroundingLLMClient,
                     input_payload: Mapping[str, Any],
                     confidence_threshold: float = 0.8) -> dict[str, Any]:
    """Call a semantic-grounding client under fail-closed policy.

    The runner never constructs a real client unless the user explicitly
    authorizes an API run.  Transport errors, invalid JSON, hallucinated ids,
    low confidence, and unresolved semantic statuses all fail closed to
    ``unknown``; the final violation decision remains programmatic.
    """
    prompt = json.dumps({
        "input": input_payload,
        "output_schema": {
            "schema_version": LLM_SCHEMA_VERSION,
            "action_grounding": {"status": "matched|ambiguous|unmatched",
                                 "activity_id": "candidate id or null",
                                 "confidence": "0.0-1.0"},
            "condition_grounding": {"status": "enforced|not_enforced|ambiguous|not_applicable",
                                    "evidence_ids": [], "reason_code": "short_code"},
            "constraint_grounding": {"status": "satisfied|violated|ambiguous|not_applicable",
                                     "evidence_ids": [], "reason_code": "short_code"},
            "exception_grounding": {"status": "handled|not_handled|ambiguous|not_applicable",
                                    "evidence_ids": [], "reason_code": "short_code"},
        },
    }, ensure_ascii=False, sort_keys=True)
    try:
        raw = client.complete(prompt)
    except Exception as exc:  # noqa: BLE001 - fail closed on any transport failure
        return {"status": "failed", "error": f"transport_failure:{type(exc).__name__}"}
    validated = validate_llm_response(raw, input_payload, confidence_threshold)
    if validated["status"] == "failed":
        return validated
    response = validated["response"]
    statuses = {
        "condition": response["condition_grounding"]["status"],
        "constraint": response["constraint_grounding"]["status"],
        "exception": response["exception_grounding"]["status"],
    }
    if any(status == "ambiguous" for status in statuses.values()):
        return {"status": "ambiguous", "response": response,
                "reason": "llm_returned_ambiguous_grounding"}
    return {"status": "resolved", "response": response}


__all__ = [
    "REVISION", "SCORE_SCHEMA", "LLM_SCHEMA_VERSION", "VIOLATION_PRIORITY",
    "ACTION_STATUS_RESOLVED", "ACTION_STATUS_AMBIGUOUS", "ACTION_STATUS_UNRESOLVED",
    "CONDITION_ENFORCED", "CONDITION_NOT_ENFORCED", "CONDITION_AMBIGUOUS",
    "CONSTRAINT_SATISFIED", "CONSTRAINT_VIOLATED", "CONSTRAINT_AMBIGUOUS",
    "EXCEPTION_HANDLED", "EXCEPTION_NOT_HANDLED", "EXCEPTION_AMBIGUOUS",
    "ground_action", "SemanticGroundingScorer", "check_prohibited", "check_condition",
    "check_constraint", "check_exception", "decide", "validate_llm_response",
    "run_llm_fallback", "build_llm_input", "fold_whitespace", "normalize_text",
    "content_tokens", "token_coverage", "text_equivalent",
]
