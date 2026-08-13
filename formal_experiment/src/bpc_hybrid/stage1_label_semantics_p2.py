"""Deterministic S1.3 P2 label semantics (Sun/Leopold-style reconstruction).

P2 is a method-level independent reconstruction of the Sun (2024) /
Leopold (2013) process-label analysis: model context analysis (pool/lane
context for the actor) + label style recognition + label composition
analysis + semantic content derivation (dependency-parsing rules for action
and business object). It runs on the frozen structural Process Record and
the BPMN XML lane-set mapping only; it NEVER reads any Gold (Stage 1/2/3),
human correction, or adjudication asset, and it NEVER falls back to P0/P1.

Project adaptations (locked in configs/stage1_label_p2_v1.json and the
method crosswalk): the exact per-step parameters of Sun/Leopold are not
published (unavailable_or_underspecified); this module locks a minimal
deterministic rule set + an offline spaCy en_core_web_sm dependency parse +
a generic English verb-root list. No Gold tuning, no per-sample rules.
"""

from __future__ import annotations

import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.stage1_process import sha256_file, validate_process_record
from bpc_hybrid.stage1_label_semantics import (
    ACTION_BOUNDARY_CHARACTERS,
    Stage1LabelError,
    canonical_process_record_sha256,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "stage1_label_semantics_p2@1.0.0"
CONFIG_VERSION = "stage1_label_p2_config@1.0.0"
P2_BASELINE = "P2"
METHOD_NAME = "stage1_label_p2_linguistic"
METHOD_VERSION = "stage1_label_p2@1.0.0"
BPMN_NS = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL"}

ACTOR_STATUSES = {
    "single_lane_label",
    "pool_fallback_empty_lane",
    "pool_fallback_ambiguous_lanes",
    "pool_fallback_single_lane",
    "no_actor",
}
LABEL_STATUSES = {
    "empty_label",
    "degenerate_label",
    "unparsed_label",
    "verb_style_action_object",
    "verb_style_action_only",
    "noun_style_action_object",
    "noun_style_action_only",
    "passive_style_action_object",
    "passive_style_action_only",
}
OBJECT_DEPENDENCIES = {"obj", "dobj", "dative", "attr"}
PASSIVE_SUBJECT_DEPENDENCIES = {"nsubjpass", "csubjpass"}
AUXILIARY_DEPENDENCIES = {"aux", "auxpass"}
PREPOSITION_DEPENDENCY = "prep"
PREP_OBJECT_DEPENDENCY = "pobj"


@dataclass(frozen=True)
class P2ValidationReport:
    schema_valid: bool
    cross_field_valid: bool
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return self.schema_valid and self.cross_field_valid

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_valid": self.schema_valid,
            "cross_field_valid": self.cross_field_valid,
            "errors": list(self.errors),
        }


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage1LabelError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Stage1LabelError(f"{label} root must be an object")
    return value


def load_p2_config(path: Path) -> dict[str, Any]:
    config = _load_json(path, "S1.3 P2 config")
    if (
        config.get("schema_version") != CONFIG_VERSION
        or config.get("task_ids") != ["S1.3"]
        or config.get("method", {}).get("baseline") != P2_BASELINE
        or config.get("method", {}).get("method_name") != METHOD_NAME
        or config.get("method", {}).get("method_version") != METHOD_VERSION
        or config.get("method", {}).get("claim_name")
        != "Sun/Leopold-style Stage 1 method-level independent reconstruction"
    ):
        raise Stage1LabelError("S1.3 P2 config identity changed")
    schema_path = _project_path(str(config["implementation"]["schema"]))
    if (
        not schema_path.is_file()
        or sha256_file(schema_path) != _schema_sha256()
    ):
        raise Stage1LabelError("S1.3 P2 schema binding changed")
    verb_path = ROOT / "configs" / "resources" / "english_verb_roots_v1.json"
    if not verb_path.is_file():
        raise Stage1LabelError("S1.3 P2 verb-root resource missing")
    _verbs()  # validate the resource loads
    return config


def _schema_sha256() -> str:
    path = ROOT / "configs" / "schemas" / "stage1_label_semantics_p2.schema.json"
    return sha256_file(path)


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _verbs() -> set[str]:
    path = ROOT / "configs" / "resources" / "english_verb_roots_v1.json"
    doc = _load_json(path, "P2 verb-root resource")
    verbs = set(doc.get("verbs", []))
    if not verbs:
        raise Stage1LabelError("P2 verb-root resource is empty")
    return verbs


# ---------------------------------------------------------------------------
# spaCy runtime (offline, locked)
# ---------------------------------------------------------------------------

_nlp = None


def _spacy() -> Any:
    global _nlp
    if _nlp is None:
        try:
            import spacy
        except ImportError as exc:
            raise Stage1LabelError(
                "P2 offline runtime (spaCy) is missing; fail closed, "
                "never fall back to P1") from exc
        try:
            _nlp = spacy.load("en_core_web_sm")
        except Exception as exc:  # pragma: no cover - defensive
            raise Stage1LabelError(
                "P2 offline model en_core_web_sm failed to load; fail "
                "closed, never fall back to P1") from exc
    return _nlp


# ---------------------------------------------------------------------------
# model context: lane -> pool mapping from the BPMN XML lane-set structure
# ---------------------------------------------------------------------------

def _lane_to_pool_name(bpmn_path: Path) -> dict[str, str | None]:
    """Map lane id -> pool (participant) name via the BPMN lane-set
    structure: lane in process P; participant with processRef==P carries the
    pool name. Pure XML read; the frozen Process Record pools are NOT used
    for this mapping (their process_ref is the dataset-level id)."""
    try:
        tree = ET.parse(bpmn_path)
    except (OSError, ET.ParseError) as exc:
        raise Stage1LabelError(f"P2 cannot parse BPMN source: {bpmn_path}") from exc
    root = tree.getroot()
    pool_name_by_process: dict[str, str | None] = {}
    for participant in root.findall(".//bpmn:participant", BPMN_NS):
        process_ref = participant.get("processRef")
        if process_ref:
            pool_name_by_process[process_ref] = participant.get("name") or None
    lane_to_process: dict[str, str] = {}
    for process in root.findall(".//bpmn:process", BPMN_NS):
        process_id = process.get("id")
        if not process_id:
            continue
        for lane in process.findall(".//bpmn:lane", BPMN_NS):
            lane_id = lane.get("id")
            if lane_id:
                lane_to_process[lane_id] = process_id
    return {
        lane_id: pool_name_by_process.get(process_id)
        for lane_id, process_id in lane_to_process.items()
    }


def _lane_labels(process_record: Mapping[str, Any], lane_ids: list[str]) -> list[str]:
    lane_names = {item["id"]: item["name"] for item in process_record["lanes"]}
    return sorted(
        {
            lane_names[lane_id]
            for lane_id in lane_ids
            if lane_names[lane_id].strip()
        }
    )


# ---------------------------------------------------------------------------
# label style recognition + composition analysis + semantic derivation
# ---------------------------------------------------------------------------

def _subtree_text(root_token: Any, doc: Any, *, skip_root: set[str]) -> str | None:
    """Deterministic subtree text: collect kept tokens ordered by position.

    - aux/auxpass/punct tokens are dropped (not part of the semantic object)
    - a preposition token is dropped itself but its children (pobj subtree)
      are kept (the preposition is an adjunct marker, not part of the object)
    - conj branches are naturally included (they are descendants)
    """
    kept: dict[int, str] = {}

    def walk(token: Any, inside_prep: bool) -> None:
        dep = token.dep_
        if dep in AUXILIARY_DEPENDENCIES or dep == "punct":
            return  # drop entirely (do not descend into aux subtrees)
        if dep == PREPOSITION_DEPENDENCY:
            for child in token.children:
                walk(child, inside_prep=True)
            return
        if token.text.strip() and dep not in skip_root:
            kept[token.i] = token.text
        for child in token.children:
            walk(child, inside_prep=inside_prep)

    walk(root_token, inside_prep=False)
    if not kept:
        return None
    return " ".join(kept[i] for i in sorted(kept))


def _analyze_label(raw_label: str, verbs: set[str]) -> dict[str, Any]:
    normalized = " ".join(raw_label.split())
    if not normalized:
        return {
            "action": None,
            "business_object": None,
            "label_status": "empty_label",
        }
    doc = _spacy()(normalized)
    roots = [token for token in doc if token.dep_ == "ROOT"]
    if not roots:
        return {
            "action": None,
            "business_object": None,
            "label_status": "unparsed_label",
        }
    root = roots[0]

    if root.pos_ == "VERB":
        # ---- verb style ---------------------------------------------------
        action_tokens = [root.text]
        object_source = root
        for child in root.children:
            if child.dep_ == "xcomp" and child.pos_ == "VERB":
                action_tokens.append(child.text)
                object_source = child
        action = " ".join(action_tokens)
        # object: direct-object dependency subtree of the (last) verb
        obj_tokens = [
            child
            for child in object_source.children
            if child.dep_ in OBJECT_DEPENDENCIES
        ]
        obj_text = None
        if obj_tokens:
            obj_text = _subtree_text(obj_tokens[0], doc, skip_root=set())
        if obj_text is None:
            # passive: subject of the passive verb
            passive = [
                child
                for child in object_source.children
                if child.dep_ in PASSIVE_SUBJECT_DEPENDENCIES
            ]
            if passive:
                obj_text = _subtree_text(passive[0], doc, skip_root=set())
                if obj_text is not None:
                    return {
                        "action": action,
                        "business_object": obj_text,
                        "label_status": "passive_style_action_object",
                    }
        if obj_text is not None:
            return {
                "action": action,
                "business_object": obj_text,
                "label_status": "verb_style_action_object",
            }
        return {
            "action": action,
            "business_object": None,
            "label_status": "verb_style_action_only",
        }

    if root.pos_ in ("NOUN", "PROPN"):
        # ---- noun style ---------------------------------------------------
        # imperative compound: phrase-initial compound token is a generic
        # English verb root -> Verb-Object style label ("Retrieve data")
        first = doc[0]
        if (
            first is not root
            and first.dep_ == "compound"
            and first.lower_ in verbs
            and first.text.strip(ACTION_BOUNDARY_CHARACTERS) == first.text
        ):
            action = first.text
            obj_text = _subtree_text(root, doc, skip_root={first.dep_})
            if obj_text is not None:
                return {
                    "action": action,
                    "business_object": obj_text,
                    "label_status": "verb_style_action_object",
                }
            return {
                "action": action,
                "business_object": None,
                "label_status": "verb_style_action_only",
            }
        # plain noun style: action = the root noun; object = prep objects
        action = root.text
        preps = sorted(
            (child for child in root.children if child.dep_ == PREPOSITION_DEPENDENCY),
            key=lambda token: token.i,
        )
        objects: list[str] = []
        for prep in preps:
            for child in prep.children:
                if child.dep_ == PREP_OBJECT_DEPENDENCY:
                    text = _subtree_text(child, doc, skip_root=set())
                    if text:
                        objects.append(text)
        if objects:
            return {
                "action": action,
                "business_object": " ".join(objects),
                "label_status": "noun_style_action_object",
            }
        return {
            "action": action,
            "business_object": None,
            "label_status": "noun_style_action_only",
        }

    # no verb, no noun -> degenerate (e.g. pure punctuation/symbols)
    return {
        "action": None,
        "business_object": None,
        "label_status": "degenerate_label",
    }


def render_p2_label_semantics(
    process_record: Mapping[str, Any],
    *,
    bpmn_path: Path,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    process_report = validate_process_record(process_record)
    if not process_report.valid:
        raise Stage1LabelError(
            "invalid upstream Process Record: " + "; ".join(process_report.errors)
        )
    if config.get("method", {}).get("baseline") != P2_BASELINE:
        raise Stage1LabelError("P2 config baseline changed")
    verbs = _verbs()
    lane_to_pool = _lane_to_pool_name(bpmn_path)
    pools = process_record.get("pools", [])
    activities: list[dict[str, Any]] = []
    for activity in sorted(
        process_record["activities"], key=lambda item: item["id"]
    ):
        lane_ids = activity.get("lane_ids", [])
        lane_labels = _lane_labels(process_record, lane_ids)
        # ---- actor: model context analysis -------------------------------
        if len(lane_labels) == 1:
            actor_surface = lane_labels[0]
            actor_status = "single_lane_label"
        elif lane_labels:
            # ambiguous: multiple distinct non-empty lane labels
            pool_name = (
                lane_to_pool.get(lane_ids[0]) if lane_ids else None
            )
            actor_surface = pool_name
            actor_status = (
                "pool_fallback_ambiguous_lanes"
                if pool_name
                else "no_actor"
            )
        elif lane_ids:
            pool_name = lane_to_pool.get(lane_ids[0])
            if pool_name:
                actor_surface = pool_name
                actor_status = "pool_fallback_empty_lane"
            else:
                actor_surface = None
                actor_status = "no_actor"
        else:
            # activity with no lane at all: single-pool context
            pool_name = pools[0].get("name") if len(pools) == 1 else None
            actor_surface = pool_name
            actor_status = (
                "pool_fallback_single_lane" if pool_name else "no_actor"
            )
        analysis = _analyze_label(activity["name"], verbs)
        activities.append(
            {
                "activity_id": activity["id"],
                "raw_label": activity["name"],
                "lane_labels": lane_labels,
                "actor_surface": actor_surface,
                "actor_status": actor_status,
                "action_surface": analysis["action"],
                "business_object_surface": analysis["business_object"],
                "label_status": analysis["label_status"],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "process_record": {
            "schema_version": process_record["schema_version"],
            "process_id": process_record["process_id"],
            "sha256": canonical_process_record_sha256(process_record),
        },
        "method": {
            "name": METHOD_NAME,
            "version": METHOD_VERSION,
            "baseline": P2_BASELINE,
            "language": "en",
            "learned_model": True,
            "runtime": {
                "package": "spacy",
                "version": _spacy_version(),
                "model": "en_core_web_sm",
                "model_version": _spacy_model_version(),
                "model_dir_sha256": _spacy_model_dir_sha256(),
            },
        },
        "activities": activities,
    }


def _spacy_version() -> str:
    import importlib.metadata
    return importlib.metadata.version("spacy")


def _spacy_model_version() -> str:
    meta = _spacy().meta
    return str(meta.get("version", ""))


def _spacy_model_dir_sha256() -> str:
    model_path = Path(_spacy().path)
    total = hashlib.sha256()
    for file in sorted(model_path.rglob("*")):
        if file.is_file() and file.name != "__init__.py":
            total.update(file.read_bytes())
    return total.hexdigest()


# ---------------------------------------------------------------------------
# validation (deterministic re-derivation, fail closed on tampering)
# ---------------------------------------------------------------------------

def _exact_keys(value: Any, expected: set[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, Mapping):
        errors.append(f"{label} must be an object")
        return False
    if set(value) != expected:
        errors.append(f"{label} properties changed")
        return False
    return True


def _manual_schema_errors(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not _exact_keys(
        record, {"schema_version", "process_record", "method", "activities"}, "record", errors
    ):
        return errors
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version changed")
    process = record.get("process_record")
    if _exact_keys(process, {"schema_version", "process_id", "sha256"}, "process_record", errors):
        if process.get("schema_version") != "process_record@1.0.0":
            errors.append("process_record.schema_version changed")
        digest = process.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(
            char not in "0123456789abcdef" for char in digest
        ):
            errors.append("process_record.sha256 must be lowercase SHA-256")
    method = record.get("method")
    method_keys = {
        "name", "version", "baseline", "language", "learned_model", "runtime",
    }
    if _exact_keys(method, method_keys, "method", errors):
        if (
            method.get("name") != METHOD_NAME
            or method.get("version") != METHOD_VERSION
            or method.get("baseline") != P2_BASELINE
            or method.get("language") != "en"
            or method.get("learned_model") is not True
        ):
            errors.append("method identity changed")
        runtime = method.get("runtime")
        if (
            not isinstance(runtime, Mapping)
            or runtime.get("package") != "spacy"
            or runtime.get("model") != "en_core_web_sm"
            or runtime.get("model_dir_sha256") != _spacy_model_dir_sha256()
        ):
            errors.append("method.runtime binding changed")
    activities = record.get("activities")
    if not isinstance(activities, list):
        errors.append("activities must be an array")
        return errors
    activity_keys = {
        "activity_id",
        "raw_label",
        "lane_labels",
        "actor_surface",
        "actor_status",
        "action_surface",
        "business_object_surface",
        "label_status",
    }
    for index, activity in enumerate(activities):
        label = f"activities[{index}]"
        if not _exact_keys(activity, activity_keys, label, errors):
            continue
        if not isinstance(activity.get("activity_id"), str) or not activity["activity_id"]:
            errors.append(f"{label}.activity_id must be non-empty")
        if not isinstance(activity.get("raw_label"), str):
            errors.append(f"{label}.raw_label must be a string")
        lanes = activity.get("lane_labels")
        if (
            not isinstance(lanes, list)
            or any(not isinstance(item, str) for item in lanes)
            or len(lanes) != len(set(lanes))
        ):
            errors.append(f"{label}.lane_labels must contain unique strings")
        for field in ("actor_surface", "action_surface", "business_object_surface"):
            if activity.get(field) is not None and not isinstance(activity.get(field), str):
                errors.append(f"{label}.{field} must be string or null")
        if activity.get("actor_status") not in ACTOR_STATUSES:
            errors.append(f"{label}.actor_status changed")
        if activity.get("label_status") not in LABEL_STATUSES:
            errors.append(f"{label}.label_status changed")
    return errors


def validate_p2_label_semantics(
    record: Mapping[str, Any],
    *,
    process_record: Mapping[str, Any],
    bpmn_path: Path,
    config: Mapping[str, Any],
) -> P2ValidationReport:
    if not isinstance(record, Mapping):
        return P2ValidationReport(False, False, ("record must be an object",))
    schema_errors = _manual_schema_errors(record)
    if schema_errors:
        return P2ValidationReport(False, False, tuple(schema_errors))
    try:
        expected = render_p2_label_semantics(
            process_record, bpmn_path=bpmn_path, config=config
        )
    except Stage1LabelError as exc:
        return P2ValidationReport(True, False, (str(exc),))
    if record != expected:
        return P2ValidationReport(
            True,
            False,
            ("P2 sidecar disagrees with deterministic re-derivation",),
        )
    return P2ValidationReport(True, True, ())


def clone_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep copy for callers that need isolated sidecars."""
    return copy.deepcopy(dict(record))
