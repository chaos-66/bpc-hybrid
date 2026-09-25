# -*- coding: utf-8 -*-
"""R3 Stage1-P2 -> Stage3 adapter.

This module is a *new* adapter over the frozen Stage 1 P2 implementation.  It
does not modify P2 and it does not claim that the original P2 formal run covered
the current 20 BPMN files.  It reads the original P2 module and config, builds
activity sidecars with the frozen P2 renderer, and extends the same frozen label
analysis to named events with an explicit R3 extension note.

It also builds a rule-side matching view for predicted actions and predicted
order endpoints.  The view is generated only from the predicted text fragment;
there is no fallback to a full label and no extraction of missing actions from
the full regulation text.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid import stage1_label_semantics_p2 as p2

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "stage3_r3_p2_adapter@1.0.0"
SIDECAR_SCHEMA_VERSION = "stage3_r3_p2_model_sidecar@1.0.0"
P2_CONFIG_PATH = ROOT / "configs" / "stage1_label_p2_v1.json"
P2_SCHEMA_PATH = ROOT / "configs" / "schemas" / "stage1_label_semantics_p2.schema.json"
P2_VERB_RESOURCE_PATH = ROOT / "configs" / "resources" / "english_verb_roots_v1.json"


class R3ActionView(str):
    """A rule-side action view that remains string-comparable/in JSON, but
    carries the R3 structural fields for the scorer.

    The string value is the *original predicted action text*.  Therefore an
    actor-action pair can still be joined by identity/equality, while the
    scorer uses ``match_source_text`` (never the full label) for similarity.
    """

    def __new__(cls, value: str, **fields: Any):
        obj = super().__new__(cls, value)
        obj.original_text = value
        for key, field_value in fields.items():
            setattr(obj, key, field_value)
        return obj

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": getattr(self, "index", None),
            "original_text": getattr(self, "original_text", self),
            "action_surface": getattr(self, "action_surface", None),
            "business_object_surface": getattr(self, "business_object_surface", None),
            "match_source_text": getattr(self, "match_source_text", None),
            "matching_text": getattr(self, "matching_text", None),
            "parse_status": getattr(self, "parse_status", None),
            "parse_source": getattr(self, "parse_source", None),
            "parse_error": getattr(self, "parse_error", None),
        }


class R3EndpointView(str):
    """Order-endpoint view built by the same P2 label analysis."""

    def __new__(cls, value: str, **fields: Any):
        obj = super().__new__(cls, value)
        obj.original_text = value
        for key, field_value in fields.items():
            setattr(obj, key, field_value)
        return obj

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_text": getattr(self, "original_text", self),
            "action_surface": getattr(self, "action_surface", None),
            "business_object_surface": getattr(self, "business_object_surface", None),
            "match_source_text": getattr(self, "match_source_text", None),
            "matching_text": getattr(self, "matching_text", None),
            "parse_status": getattr(self, "parse_status", None),
            "parse_source": getattr(self, "parse_source", None),
            "parse_error": getattr(self, "parse_error", None),
            "offsets": getattr(self, "offsets", None),
        }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def frozen_lemma(nlp: Any, text: str) -> str:
    """The frozen lemma rule used by ``SunScorer._lemma``."""
    if nlp is None:
        return text
    return " ".join(
        w.lemma_ if w.lemma_ != "-PRON-" else w.text
        for w in nlp(text)
        if not w.is_punct and not w.is_space
    )


def compose_match_source(action_surface: Any, business_object_surface: Any) -> str | None:
    """Join non-empty P2 action and object surfaces in fixed order."""
    parts: list[str] = []
    for value in (action_surface, business_object_surface):
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    if not parts:
        return None
    return " ".join(parts)


def analyze_label_text(nlp: Any, raw_text: str | None, *, source: str) -> dict[str, Any]:
    """Apply the frozen P2 label analysis to one predicted text fragment.

    This is deliberately *not* a fallback to the full label.  If P2 cannot
    derive an action/business-object surface, the result is recorded as a
    parse failure and the matching source is empty.
    """
    if raw_text is None or not isinstance(raw_text, str) or not raw_text.strip():
        return {
            "action_surface": None,
            "business_object_surface": None,
            "match_source_text": None,
            "matching_text": None,
            "parse_status": "empty_text",
            "parse_source": source,
            "parse_error": "empty_text",
            "label_status": "empty_label",
        }
    try:
        analysis = p2._analyze_label(raw_text, p2._verbs())
        label_status = str(analysis.get("label_status") or "unparsed_label")
        action_surface = analysis.get("action")
        object_surface = analysis.get("business_object")
        match_source = compose_match_source(action_surface, object_surface)
        if match_source is None:
            parse_status = "failed_no_surfaces"
            parse_error = f"p2_label_status={label_status}"
        else:
            parse_status = "parsed"
            parse_error = None
        return {
            "action_surface": action_surface,
            "business_object_surface": object_surface,
            "match_source_text": match_source,
            "matching_text": frozen_lemma(nlp, match_source) if match_source else None,
            "parse_status": parse_status,
            "parse_source": source,
            "parse_error": parse_error,
            "label_status": label_status,
        }
    except Exception as exc:  # noqa: BLE001 - fail closed with explicit evidence
        return {
            "action_surface": None,
            "business_object_surface": None,
            "match_source_text": None,
            "matching_text": None,
            "parse_status": "failed_exception",
            "parse_source": source,
            "parse_error": f"{type(exc).__name__}: {exc}",
            "label_status": "unparsed_label",
        }


def _derive_actor(record: Mapping[str, Any], node: Mapping[str, Any],
                  bpmn_path: Path) -> tuple[str | None, str]:
    """Mirror P2's frozen actor-context rule for a node.

    Activities use the frozen P2 renderer directly; this helper is used for the
    explicit R3 event-side extension.
    """
    lane_ids = [str(x) for x in (node.get("lane_ids") or [])]
    lanes = {str(l.get("id")): str(l.get("name") or "") for l in (record.get("lanes") or [])}
    lane_labels = sorted({lanes[lid].strip() for lid in lane_ids if lanes.get(lid, "").strip()})
    if len(lane_labels) == 1:
        return lane_labels[0], "single_lane_label"
    if lane_labels:
        lane_to_pool = p2._lane_to_pool_name(bpmn_path)
        pool_name = lane_to_pool.get(lane_ids[0]) if lane_ids else None
        return (pool_name, "pool_fallback_ambiguous_lanes") if pool_name else (None, "no_actor")
    if lane_ids:
        lane_to_pool = p2._lane_to_pool_name(bpmn_path)
        pool_name = lane_to_pool.get(lane_ids[0])
        if pool_name:
            return pool_name, "pool_fallback_empty_lane"
        return None, "no_actor"
    pools = list(record.get("pools") or [])
    pool_name = str(pools[0].get("name") or "").strip() if len(pools) == 1 else ""
    if pool_name:
        return pool_name, "pool_fallback_single_lane"
    return None, "no_actor"


def _node_from_activity(activity: Mapping[str, Any], nlp: Any) -> dict[str, Any]:
    source = "frozen_p2_activity"
    action_surface = activity.get("action_surface")
    object_surface = activity.get("business_object_surface")
    match_source = compose_match_source(action_surface, object_surface)
    parse_status = "parsed" if match_source else "failed_no_surfaces"
    return {
        "node_id": str(activity.get("activity_id")),
        "node_type": "activity",
        "raw_label": activity.get("raw_label"),
        "actor_surface": activity.get("actor_surface"),
        "actor_status": activity.get("actor_status"),
        "action_surface": action_surface,
        "business_object_surface": object_surface,
        "match_source_text": match_source,
        "matching_text": frozen_lemma(nlp, match_source) if match_source else None,
        "parse_status": parse_status,
        "parse_source": source,
        "parse_error": None if match_source else f"p2_label_status={activity.get('label_status')}",
        "label_status": activity.get("label_status"),
        "lane_labels": activity.get("lane_labels") or [],
    }


def _node_from_event(event: Mapping[str, Any], record: Mapping[str, Any],
                     bpmn_path: Path, nlp: Any) -> dict[str, Any]:
    raw_label = str(event.get("name") or "")
    actor_surface, actor_status = _derive_actor(record, event, bpmn_path)
    analysis = analyze_label_text(nlp, raw_label, source="r3_p2_event_extension")
    return {
        "node_id": str(event.get("id")),
        "node_type": "event",
        "raw_label": raw_label,
        "actor_surface": actor_surface,
        "actor_status": actor_status,
        "action_surface": analysis["action_surface"],
        "business_object_surface": analysis["business_object_surface"],
        "match_source_text": analysis["match_source_text"],
        "matching_text": analysis["matching_text"],
        "parse_status": analysis["parse_status"],
        "parse_source": analysis["parse_source"],
        "parse_error": analysis["parse_error"],
        "label_status": analysis["label_status"],
        "lane_labels": [],
    }


def build_model_sidecar(record: Mapping[str, Any], *, case_id: str, bpmn_path: Path,
                        nlp: Any, p2_config: Mapping[str, Any]) -> dict[str, Any]:
    """Build one per-model sidecar.  Original P2 activities + R3 event extension."""
    p2_output = p2.render_p2_label_semantics(record, bpmn_path=bpmn_path, config=p2_config)
    nodes: list[dict[str, Any]] = []
    for activity in p2_output.get("activities") or []:
        nodes.append(_node_from_activity(activity, nlp))
    for event in record.get("events") or []:
        nodes.append(_node_from_event(event, record, bpmn_path, nlp))

    # Stable node-id order for deterministic tie breaking.
    nodes.sort(key=lambda row: str(row["node_id"]))
    reachable: dict[str, list[str]] = {}
    for pair in (record.get("control_flow") or {}).get("reachable_pairs") or []:
        src = str(pair.get("source_ref"))
        tgt = str(pair.get("target_ref"))
        reachable.setdefault(src, [])
        if tgt not in reachable[src]:
            reachable[src].append(tgt)
    for src in reachable:
        reachable[src].sort()

    actors: list[str] = []
    actor_sources: dict[str, str] = {}
    action_actor_names: dict[str, list[str]] = {}
    for node in nodes:
        actor = node.get("actor_surface")
        node_id = str(node["node_id"])
        if isinstance(actor, str) and actor.strip():
            actor = actor.strip()
            if actor not in actors:
                actors.append(actor)
            actor_sources[actor] = str(node.get("actor_status") or "unknown")
            action_actor_names[node_id] = [actor]
        else:
            action_actor_names[node_id] = []

    business_objects: list[dict[str, Any]] = []
    for node in nodes:
        obj = node.get("business_object_surface")
        if isinstance(obj, str) and obj.strip():
            business_objects.append({
                "activity_id": str(node["node_id"]),
                "object": obj.strip(),
                "match_source_text": obj.strip(),
                "matching_text": frozen_lemma(nlp, obj.strip()),
                "source": node.get("parse_source"),
            })

    return {
        "schema_version": SIDECAR_SCHEMA_VERSION,
        "case_id": case_id,
        "process_id": record.get("process_id"),
        "bpmn_path": bpmn_path.as_posix(),
        "bpmn_sha256": sha256_file(bpmn_path),
        "process_record_sha256": p2.canonical_process_record_sha256(record),
        "extension_note": (
            "R3 extends the original P2 activity-only sidecar to named events. "
            "The event branch calls the same frozen P2 label analysis; it does "
            "not claim that the original P2 formal run covered these events."
        ),
        "p2_assets": {
            "code_path": Path(p2.__file__).relative_to(ROOT).as_posix(),
            "code_sha256": sha256_file(Path(p2.__file__)),
            "config_path": P2_CONFIG_PATH.relative_to(ROOT).as_posix(),
            "config_sha256": sha256_file(P2_CONFIG_PATH),
            "schema_path": P2_SCHEMA_PATH.relative_to(ROOT).as_posix(),
            "schema_sha256": sha256_file(P2_SCHEMA_PATH),
            "verb_resource_path": P2_VERB_RESOURCE_PATH.relative_to(ROOT).as_posix(),
            "verb_resource_sha256": sha256_file(P2_VERB_RESOURCE_PATH),
            "runtime": p2_output.get("method", {}).get("runtime") or {},
            "method": p2_output.get("method") or {},
        },
        "nodes": nodes,
        "actors": actors,
        "actor_sources": actor_sources,
        "action_actor_names": action_actor_names,
        "business_objects": business_objects,
        "reachable": reachable,
        "tie_break": "ascending_node_id",
        "safety": {
            "gold_read": False,
            "reference_read": False,
            "llm_api_called": False,
            "network_called": False,
        },
    }


class R3P2Model:
    """Stage-3 model view built from one frozen R3 sidecar."""

    def __init__(self, sidecar: Mapping[str, Any]):
        self.sidecar = dict(sidecar)
        self.process_id = sidecar.get("process_id")
        self.actions: list[dict[str, Any]] = []
        for node in sidecar.get("nodes") or []:
            self.actions.append({
                "id": str(node.get("node_id")),
                "name": node.get("raw_label") or "",
                "kind": node.get("node_type") or "node",
                "match_source_text": node.get("match_source_text"),
                "matching_text": node.get("matching_text"),
                "action_surface": node.get("action_surface"),
                "business_object_surface": node.get("business_object_surface"),
                "parse_status": node.get("parse_status"),
                "parse_source": node.get("parse_source"),
                "actor_surface": node.get("actor_surface"),
            })
        self.actors = list(sidecar.get("actors") or [])
        self.actor_sources = dict(sidecar.get("actor_sources") or {})
        self.action_actor_names = {
            str(k): list(v) for k, v in (sidecar.get("action_actor_names") or {}).items()
        }
        self.business_objects = [dict(x) for x in (sidecar.get("business_objects") or [])]
        self.reachable = {
            str(k): set(str(x) for x in (v or []))
            for k, v in (sidecar.get("reachable") or {}).items()
        }
        self.id_to_name = {str(a["id"]): str(a["name"]) for a in self.actions}

    def is_reachable(self, source_id: str, target_id: str) -> bool:
        return target_id in self.reachable.get(source_id, set())


def _edge_details_from_audit(audit: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for clause in audit.get("clause_audits") or []:
        for edge in clause.get("derived_edges") or []:
            rows.append(dict(edge))
        native = clause.get("native") or {}
        for edge in native.get("edges") or []:
            rows.append({"native": True, **dict(edge)})
    return rows


def build_rule_action_views(nlp: Any, actions: Sequence[str]) -> tuple[list[R3ActionView], list[dict[str, Any]]]:
    views: list[R3ActionView] = []
    evidence: list[dict[str, Any]] = []
    for index, raw in enumerate(actions):
        analysis = analyze_label_text(nlp, raw, source="predicted_action")
        view = R3ActionView(
            raw,
            index=index,
            action_surface=analysis["action_surface"],
            business_object_surface=analysis["business_object_surface"],
            match_source_text=analysis["match_source_text"],
            matching_text=analysis["matching_text"],
            parse_status=analysis["parse_status"],
            parse_source=analysis["parse_source"],
            parse_error=analysis["parse_error"],
        )
        views.append(view)
        evidence.append(view.to_dict())
    return views, evidence


def build_endpoint_view(nlp: Any, text: str, *, offsets: list[int] | None = None,
                        source: str = "predicted_order_endpoint") -> R3EndpointView:
    analysis = analyze_label_text(nlp, text, source=source)
    return R3EndpointView(
        text,
        action_surface=analysis["action_surface"],
        business_object_surface=analysis["business_object_surface"],
        match_source_text=analysis["match_source_text"],
        matching_text=analysis["matching_text"],
        parse_status=analysis["parse_status"],
        parse_source=analysis["parse_source"],
        parse_error=analysis["parse_error"],
        offsets=offsets,
    )


__all__ = [
    "SCHEMA_VERSION",
    "SIDECAR_SCHEMA_VERSION",
    "R3ActionView",
    "R3EndpointView",
    "R3P2Model",
    "analyze_label_text",
    "build_endpoint_view",
    "build_model_sidecar",
    "build_rule_action_views",
    "compose_match_source",
    "frozen_lemma",
    "sha256_file",
]
