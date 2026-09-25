"""Build the S3-TABLE3-R5 benchmark dataset (offline; zero real LLM calls).

This script constructs:
- source-grounded independent requirements (36; 30-40 accepted range);
- one compliant baseline process per requirement;
- 24 single-error variants for each of missing_action / incorrect_actor /
  out_of_order on the 24 test requirements;
- separate semantic-challenge records and BPMN (not mixed into core F1);
- inference/reference separation with opaque case ids;
- manifest, split manifest, and evaluation contract.

It does not read model predictions to choose or label cases.  It does not call
an API, run old experiments, or modify existing Gold, predictions, or manifests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v1.json"
OUT = ROOT / "data/development/stage3_table3_r5_benchmark_v1"
REPORTS = ROOT / "outputs/reports"
BENCHMARK_ID = "stage3_table3_r5_benchmark_v1"
NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
ET.register_namespace("", NS)
VARIANT_TYPES = ("missing_action", "incorrect_actor", "out_of_order")

ELEMENT_CAPABILITIES = {
    "modality": {
        "current_module": "src/bpc_hybrid/sun_stage3/r4_action_surface_scorer.py + Stage2 modality classifier input",
        "current_support": "implemented",
        "in_main_scoring": False,
        "reason": "modality is available to Stage2 but the frozen three-class violation formula does not score modality truth",
    },
    "actor": {
        "current_module": "src/bpc_hybrid/sun_stage3/r4_action_surface_scorer.py + BPMN participant/lane parsing",
        "current_support": "implemented",
        "in_main_scoring": True,
        "reason": "actor is one of the three frozen violation classes (incorrect_actor)",
    },
    "action": {
        "current_module": "src/bpc_hybrid/sun_stage3/r4_action_surface_scorer.py + Stage2 action extraction",
        "current_support": "implemented",
        "in_main_scoring": True,
        "reason": "action presence/absence is one of the three frozen violation classes (missing_action)",
    },
    "condition": {
        "current_module": "no active condition-truth consumer in the frozen three-class scorer",
        "current_support": "unsupported",
        "in_main_scoring": False,
        "reason": "condition truth and applicability must not be silently counted as a successful detector capability",
    },
    "constraint": {
        "current_module": "src/bpc_hybrid/sun_stage3/temporal_projection_v4_r3.py + stage1_process activity_order_relations",
        "current_support": "indirect_only",
        "in_main_scoring": True,
        "reason": "explicit source-order pairs enter out_of_order scoring; deadlines, quantities, and general temporal logic are not fully implemented",
    },
    "exception": {
        "current_module": "no active exception-truth consumer in the frozen three-class scorer",
        "current_support": "unsupported",
        "in_main_scoring": False,
        "reason": "exception effectiveness is not silently defaulted to compliant",
    },
}

CONDITION_PAIR_IDS = [
    "R5-S1-T1", "R5-S2-T1", "R5-S3-T3", "R5-S4-T3", "R5-S5-T2", "R5-S6-T4",
]
EXCEPTION_PAIR_IDS = [
    "R5-S1-T3", "R5-S2-T3", "R5-S3-T1", "R5-S4-T4", "R5-S5-T4", "R5-S6-T2",
]


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_text(value: str) -> str:
    return sha_bytes(value.encode("utf-8"))


def stable_id(prefix: str, *parts: object, length: int = 12) -> str:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:length]}"


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_ws(value: str) -> str:
    return " ".join(value.split())


def relative_to_repo(path: Path) -> str:
    return path.resolve().relative_to(ROOT.parent.resolve()).as_posix()


def article_path(config: dict, article: int) -> Path:
    return (ROOT.parent / config["source_directory"] / f"article{article}.txt").resolve()


def load_article(config: dict, article: int) -> tuple[Path, bytes, str, str]:
    path = article_path(config, article)
    raw = path.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    return path, raw, text, normalized_ws(text)


def split_sentences(text: str) -> list[str]:
    text = normalized_ws(text)
    # GDPR has enumerated items and abbreviations; this conservative splitter
    # is adequate for the selected official-English sentences.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text)
    return [p.strip() for p in parts if p.strip()]


def excerpt_from_text(text: str, locator: str, mode: str) -> str:
    loc = normalized_ws(locator).lower()
    if mode == "sentence":
        candidates = [s for s in split_sentences(text) if loc in s.lower()]
    elif mode == "paragraph":
        paragraphs = [normalized_ws(p) for p in re.split(r"\n\s*\n", text) if normalized_ws(p)]
        candidates = [p for p in paragraphs if loc in p.lower()]
    elif mode == "item":
        candidates = []
        normalized = normalized_ws(text)
        lowered = normalized.lower()
        pos = lowered.find(loc)
        if pos >= 0:
            left = max(normalized.rfind(";", 0, pos), normalized.rfind(": ", 0, pos))
            right = normalized.find(";", pos)
            if right < 0:
                right = len(normalized)
            candidates = [normalized[left + 1:right].strip()]
    else:
        raise ValueError(f"unknown excerpt mode: {mode}")
    if len(candidates) != 1:
        raise ValueError(f"source locator must match exactly one excerpt: {locator!r} matched {len(candidates)}")
    excerpt = candidates[0]
    if normalized_ws(excerpt) not in normalized_ws(text):
        raise ValueError("excerpt is not a contiguous normalized substring")
    return excerpt


def gdpr7_sentence_index() -> dict[str, dict]:
    doc = load_json(ROOT / "data/input/gdpr7_stage2_input_v1.json")
    out: dict[str, dict] = {}
    for rule in doc["rules"]:
        for sentence in rule["sentences"]:
            out[sentence["sample_id"]] = {
                "rule_id": rule["rule_id"],
                "sample_id": sentence["sample_id"],
                "text": sentence["approved_text_en"],
                "text_sha256": sentence["text_sha256"],
                "char_span": sentence.get("char_span"),
                "source_dataset": "data/input/gdpr7_stage2_input_v1.json",
                "source_dataset_sha256": sha_bytes((ROOT / "data/input/gdpr7_stage2_input_v1.json").read_bytes()),
            }
    if not out:
        raise ValueError("empty gdpr7 sentence index")
    return out


def r4_reference_index() -> dict[str, dict]:
    path = ROOT / "data/development/stage3_reconstruction_v4/construction_reference.json"
    doc = load_json(path)
    out: dict[str, dict] = {}
    for case in doc["cases"]:
        if case.get("variant") != "control":
            continue
        out[case["rule_id"]] = {
            "text": case["source"]["text"],
            "text_sha256": case["source"]["text_sha256"],
            "source_file_path": case["source"].get("source_path"),
            "source_file_sha256": case["source"].get("source_file_sha256"),
            "char_span": case["source"].get("char_span"),
            "context": case["source"].get("applicability_context", []),
            "source_dataset": "data/development/stage3_reconstruction_v4/construction_reference.json",
            "source_dataset_sha256": sha_bytes(path.read_bytes()),
        }
    if not out:
        raise ValueError("empty r4 reference index")
    return out


def extra_context_text(config: dict, spec: dict) -> tuple[str, dict | None]:
    mapping = {
        "R5-S1-T3": (14, "within a reasonable period after obtaining the personal data", "sentence"),
        "R5-S1-T4": (14, "within a reasonable period after obtaining the personal data", "sentence"),
        "R5-S3-T3": (21, "The data subject shall have the right to object, on grounds relating", "sentence"),
    }
    entry = mapping.get(spec["requirement_id"])
    if not entry:
        return "", None
    article, locator, mode = entry
    path, raw, text, _ = load_article(config, article)
    excerpt = excerpt_from_text(text, locator, mode)
    return excerpt, {
        "article": article,
        "locator": locator,
        "source_file_path": relative_to_repo(path),
        "source_file_sha256": sha_bytes(raw),
        "text_sha256": sha_text(excerpt),
    }


def build_source_record(config: dict, spec: dict, gdpr7_index: dict, r4_index: dict) -> dict:
    kind = spec["source_kind"]
    common = {
        "requirement_id": spec["requirement_id"],
        "citation": spec["citation"],
        "source_url": config["source_url"],
        "document_version": config["document_version"],
        "article": spec["article"],
        "paragraph": spec["paragraph"],
    }
    if kind == "r4_reference":
        if spec.get("r4_rule_id") not in r4_index:
            raise ValueError(f"missing R4 reference source for {spec['requirement_id']}")
        ref = r4_index[spec["r4_rule_id"]]
        source = {
            **common,
            "source_kind": kind,
            "excerpt_text": ref["text"],
            "text_sha256": ref["text_sha256"],
            "source_file_path": ref.get("source_file_path"),
            "source_file_sha256": ref.get("source_file_sha256"),
            "source_dataset": ref["source_dataset"],
            "source_dataset_sha256": ref["source_dataset_sha256"],
            "char_span": ref.get("char_span"),
            "context_text": "",
            "context_sha256": None,
            "context_ref": ref.get("context"),
        }
        return source
    if kind == "gdpr7_input":
        if spec.get("sample_id") not in gdpr7_index:
            raise ValueError(f"missing GDPR7 source for {spec['requirement_id']}")
        ref = gdpr7_index[spec["sample_id"]]
        return {
            **common,
            "source_kind": kind,
            "sample_id": ref["sample_id"],
            "excerpt_text": ref["text"],
            "text_sha256": ref["text_sha256"],
            "source_file_path": None,
            "source_file_sha256": None,
            "source_dataset": ref["source_dataset"],
            "source_dataset_sha256": ref["source_dataset_sha256"],
            "char_span": ref.get("char_span"),
            "context_text": "",
            "context_sha256": None,
            "context_ref": None,
        }
    if kind == "new_article":
        path, raw, text, _ = load_article(config, spec["article"])
        excerpt = excerpt_from_text(text, spec["source_locator"], spec["excerpt_mode"])
        context_text, context_ref = extra_context_text(config, spec)
        return {
            **common,
            "source_kind": kind,
            "excerpt_text": excerpt,
            "text_sha256": sha_text(excerpt),
            "source_file_path": relative_to_repo(path),
            "source_file_sha256": sha_bytes(raw),
            "source_dataset": relative_to_repo(path),
            "source_dataset_sha256": sha_bytes(raw),
            "char_span": None,
            "context_text": context_text,
            "context_sha256": sha_text(context_text) if context_text else None,
            "context_ref": context_ref,
        }
    raise ValueError(f"unknown source kind: {kind}")


def add_sequence_flow(parent, flow_id: str, source: str, target: str, condition: str | None = None):
    flow = ET.SubElement(parent, f"{{{NS}}}sequenceFlow", {"id": flow_id, "sourceRef": source, "targetRef": target})
    if condition:
        expr = ET.SubElement(flow, f"{{{NS}}}conditionExpression")
        expr.text = condition


def build_bpmn(spec: dict, variant: str) -> bytes:
    if variant not in ("control",) + VARIANT_TYPES:
        raise ValueError(f"unknown variant: {variant}")
    n_tasks = len(spec["tasks"])
    actor = spec["actor_wrong"] if variant == "incorrect_actor" else spec["actor_required"]
    order = list(range(n_tasks))
    if variant == "missing_action":
        order = [i for i in order if i != spec["mandatory_index"]]
    if variant == "out_of_order":
        a, b = spec["order_pair"]
        order[a], order[b] = order[b], order[a]
    # Rebuild from task order.  The mandatory deletion is safe because all order
    # pairs are adjacent source-ordered pairs on a linear true path.
    definitions = ET.Element(f"{{{NS}}}definitions", {"id": "Definitions", "targetNamespace": "urn:bpc:table3:r5:v1"})
    collaboration = ET.SubElement(definitions, f"{{{NS}}}collaboration", {"id": "Collaboration"})
    ET.SubElement(collaboration, f"{{{NS}}}participant", {"id": "Participant", "name": actor, "processRef": "Process"})
    process = ET.SubElement(definitions, f"{{{NS}}}process", {"id": "Process", "name": actor, "isExecutable": "false"})
    uses_gateway = bool(spec.get("condition_present") or spec.get("exception_present"))
    lane_set = ET.SubElement(process, f"{{{NS}}}laneSet", {"id": "LaneSet"})
    lane = ET.SubElement(lane_set, f"{{{NS}}}lane", {"id": "Lane_Actor", "name": actor})
    lane_nodes = ["Start"] + (["Gateway_Applicability"] if uses_gateway else []) + [f"Activity_{i}" for i in order] + ["End"]
    for node_id in lane_nodes:
        ET.SubElement(lane, f"{{{NS}}}flowNodeRef").text = node_id
    ET.SubElement(process, f"{{{NS}}}startEvent", {"id": "Start", "name": spec["business_scenario_en"]})
    if uses_gateway:
        ET.SubElement(process, f"{{{NS}}}exclusiveGateway", {"id": "Gateway_Applicability", "name": "Assess applicable condition"})
    for idx in order:
        ET.SubElement(process, f"{{{NS}}}task", {"id": f"Activity_{idx}", "name": spec["tasks"][idx]})
    ET.SubElement(process, f"{{{NS}}}endEvent", {"id": "End"})
    nodes = ["Start"]
    if uses_gateway:
        nodes.append("Gateway_Applicability")
    nodes.extend(f"Activity_{i}" for i in order)
    nodes.append("End")
    for i, (source, target) in enumerate(zip(nodes, nodes[1:])):
        condition = None
        if source == "Gateway_Applicability":
            condition = "applicability_condition == true"
        add_sequence_flow(process, f"Flow_{i}", source, target, condition)
    ET.indent(definitions, space="  ")
    return ET.tostring(definitions, encoding="utf-8", xml_declaration=True) + b"\n"


def linear_activity_sequence(raw: bytes) -> dict:
    root = ET.fromstring(raw)
    tasks = {e.get("id"): e.get("name") for e in root.findall(f".//{{{NS}}}task")}
    participant = root.find(f".//{{{NS}}}participant")
    lane = root.find(f".//{{{NS}}}lane")
    edges = [(e.get("sourceRef"), e.get("targetRef")) for e in root.findall(f".//{{{NS}}}sequenceFlow")]
    nodes = {e.get("id") for e in root.iter() if e.get("id") and (e.tag.endswith("Event") or e.tag.endswith("Gateway") or e.tag.endswith("task"))}
    succ: dict[str, list[str]] = {}
    for src, dst in edges:
        succ.setdefault(src, []).append(dst)
    seq: list[str] = []
    current = "Start"
    seen: set[str] = set()
    while current is not None and current in nodes:
        if current in seen:
            raise ValueError("cycle in linear benchmark construction")
        seen.add(current)
        if current.startswith("Activity_"):
            seq.append(current)
        choices = succ.get(current, [])
        if not choices:
            current = None
        elif len(choices) == 1:
            current = choices[0]
        else:
            raise ValueError("unexpected branching in core linear construction")
    if current is not None and current not in ("End",) and current not in nodes:
        raise ValueError("edge references unknown node")
    if "End" not in seen:
        raise ValueError("End not reachable")
    return {
        "activities": tasks,
        "actor": participant.get("name") if participant is not None else None,
        "lane_actor": lane.get("name") if lane is not None else None,
        "sequence": seq,
        "edges": edges,
    }


def reference_states_for(spec: dict, variant: str, observed: dict) -> dict:
    mandatory_id = f"Activity_{spec['mandatory_index']}"
    required_present = mandatory_id in observed["activities"]
    actor_wrong = observed["actor"] != spec["actor_required"]
    before_id = f"Activity_{spec['order_pair'][0]}"
    after_id = f"Activity_{spec['order_pair'][1]}"
    ordered = True
    if before_id in observed["sequence"] and after_id in observed["sequence"]:
        ordered = observed["sequence"].index(before_id) < observed["sequence"].index(after_id)
    else:
        ordered = False
    states = {
        "missing_action": "violated" if not required_present else "satisfied",
        "incorrect_actor": "violated" if actor_wrong else "satisfied",
        "out_of_order": "violated" if not ordered else "satisfied",
    }
    if variant == "missing_action":
        states["incorrect_actor"] = "not_applicable"
        states["out_of_order"] = "not_applicable"
    return states


def validate_expected(spec: dict, variant: str, observed: dict, states: dict) -> None:
    mandatory_id = f"Activity_{spec['mandatory_index']}"
    present = mandatory_id in observed["activities"]
    actor_wrong = observed["actor"] != spec["actor_required"]
    before_id = f"Activity_{spec['order_pair'][0]}"
    after_id = f"Activity_{spec['order_pair'][1]}"
    ordered = True
    if before_id in observed["sequence"] and after_id in observed["sequence"]:
        ordered = observed["sequence"].index(before_id) < observed["sequence"].index(after_id)
    if variant == "control":
        if not present or actor_wrong or not ordered:
            raise ValueError(f"control does not satisfy all checks: {spec['requirement_id']}")
    elif variant == "missing_action":
        if present:
            raise ValueError("missing_action mutation did not remove the mandatory task")
        if states != {"missing_action": "violated", "incorrect_actor": "not_applicable", "out_of_order": "not_applicable"}:
            raise ValueError("missing_action reference states wrong")
    elif variant == "incorrect_actor":
        if not present or not actor_wrong or not ordered:
            raise ValueError("incorrect_actor mutation is not single-factor")
        if states != {"missing_action": "satisfied", "incorrect_actor": "violated", "out_of_order": "satisfied"}:
            raise ValueError("incorrect_actor reference states wrong")
    elif variant == "out_of_order":
        if not present or actor_wrong or ordered:
            raise ValueError("out_of_order mutation is not a proper reversal")
        if states != {"missing_action": "satisfied", "incorrect_actor": "satisfied", "out_of_order": "violated"}:
            raise ValueError("out_of_order reference states wrong")
    if sum(1 for v in states.values() if v == "violated") != (0 if variant == "control" else 1):
        raise ValueError("exactly one or zero violation factor expected")


def build_challenge_bpmn(spec: dict, applicable: bool, kind: str) -> bytes:
    """A minimal contrast process for semantic-challenge tables.

    Applicable: the mandatory action remains in the true path.
    Not applicable: a gateway bypasses the mandatory action to End.
    """
    n_tasks = len(spec["tasks"])
    actor = spec["actor_required"]
    definitions = ET.Element(f"{{{NS}}}definitions", {"id": "Definitions", "targetNamespace": "urn:bpc:table3:r5:challenge"})
    collaboration = ET.SubElement(definitions, f"{{{NS}}}collaboration", {"id": "Collaboration"})
    ET.SubElement(collaboration, f"{{{NS}}}participant", {"id": "Participant", "name": actor, "processRef": "Process"})
    process = ET.SubElement(definitions, f"{{{NS}}}process", {"id": "Process", "name": actor, "isExecutable": "false"})
    lane_set = ET.SubElement(process, f"{{{NS}}}laneSet", {"id": "LaneSet"})
    lane = ET.SubElement(lane_set, f"{{{NS}}}lane", {"id": "Lane_Actor", "name": actor})
    ET.SubElement(lane, f"{{{NS}}}flowNodeRef").text = "Start"
    ET.SubElement(lane, f"{{{NS}}}flowNodeRef").text = "Gateway_Applicability"
    if applicable:
        for i in range(n_tasks):
            ET.SubElement(lane, f"{{{NS}}}flowNodeRef").text = f"Activity_{i}"
    else:
        ET.SubElement(lane, f"{{{NS}}}flowNodeRef").text = "Activity_0"
    ET.SubElement(lane, f"{{{NS}}}flowNodeRef").text = "End"
    ET.SubElement(process, f"{{{NS}}}startEvent", {"id": "Start", "name": spec["business_scenario_en"] + " (" + ("condition/exception true" if applicable else "condition/exception not true") + ")"})
    ET.SubElement(process, f"{{{NS}}}exclusiveGateway", {"id": "Gateway_Applicability", "name": kind})
    for i in range(n_tasks):
        if applicable or i != spec["mandatory_index"]:
            ET.SubElement(process, f"{{{NS}}}task", {"id": f"Activity_{i}", "name": spec["tasks"][i]})
    ET.SubElement(process, f"{{{NS}}}endEvent", {"id": "End"})
    add_sequence_flow(process, "Flow_Start_Gateway", "Start", "Gateway_Applicability")
    if applicable:
        for i in range(n_tasks - 1):
            add_sequence_flow(process, f"Flow_Activity_{i}_to_{i+1}", f"Activity_{i}", f"Activity_{i+1}")
        add_sequence_flow(process, f"Flow_Activity_{n_tasks-1}_End", f"Activity_{n_tasks-1}", "End")
        add_sequence_flow(process, "Flow_Gateway_Activity_0", "Gateway_Applicability", "Activity_0")
    else:
        add_sequence_flow(process, "Flow_Gateway_Activity_0", "Gateway_Applicability", "Activity_0")
        add_sequence_flow(process, "Flow_Activity_0_End", "Activity_0", "End")
    ET.indent(definitions, space="  ")
    return ET.tostring(definitions, encoding="utf-8", xml_declaration=True) + b"\n"


def build_semantic_challenges(config: dict, core_specs: dict) -> tuple[dict, dict[str, bytes]]:
    article_text_cache: dict[int, str] = {}
    def article_text(article: int) -> str:
        if article not in article_text_cache:
            _, _, _, text = load_article(config, article)
            article_text_cache[article] = text
        return article_text_cache[article]

    def fragment(fid: str, modality: str, article: int, locator: str, mode: str, citation: str) -> dict:
        text = excerpt_from_text(article_text(article), locator, mode)
        return {
            "fragment_id": fid,
            "modality": modality,
            "citation": citation,
            "article": article,
            "raw_text": text,
            "text_sha256": sha_text(text),
            "source_url": config["source_url"],
            "document_version": config["document_version"],
        }

    def fragment_literal(fid: str, modality: str, article: int, citation: str, text: str, source_status: str) -> dict:
        return {
            "fragment_id": fid,
            "modality": modality,
            "citation": citation,
            "article": article,
            "raw_text": text,
            "text_sha256": sha_text(text),
            "source_url": config["source_url"],
            "document_version": config["document_version"],
            "source_status": source_status,
        }

    fragments = [
        fragment("FR-PRO-01", "prohibition", 9, "Processing of personal data revealing racial or ethnic origin", "paragraph", "GDPR Article 9(1)"),
        fragment("FR-PRO-02", "prohibition", 28, "the processor shall not engage another processor without prior specific or general written authorisation", "sentence", "GDPR Article 28(2)"),
        fragment("FR-PRO-03", "prohibition", 22, "The data subject shall have the right not to be subject to a decision based solely on automated processing", "sentence", "GDPR Article 22(1)"),
        fragment("FR-PRO-04", "prohibition", 5, "Personal data shall be collected for specified, explicit and legitimate purposes and not further processed", "sentence", "GDPR Article 5(1)(b)"),
        fragment("FR-PER-01", "permission", 6, "Processing shall be lawful only if and to the extent that the data subject has given consent", "sentence", "GDPR Article 6(1)(a)"),
        fragment("FR-PER-02", "permission", 9, "The data subject has given explicit consent to the processing of those personal data", "item", "GDPR Article 9(2)(a)"),
        fragment("FR-PER-03", "permission", 46, "has provided appropriate safeguards", "sentence", "GDPR Article 46(1)"),
        fragment("FR-PER-04", "permission", 49, "the data subject has explicitly consented to the proposed transfer", "sentence", "GDPR Article 49(1)(a)"),
        fragment_literal("FR-DEF-01", "definition", 4, "GDPR Article 4(1)",
            "'Personal data' means any information relating to an identified or identifiable natural person ('data subject'); an identifiable natural person is one who can be identified, directly or indirectly, in particular by reference to an identifier such as a name, an identification number, location data, an online identifier or to one or more factors specific to the physical, physiological, genetic, mental, economic, cultural or social identity of that natural person.",
            "official_text_not_in_local_winter_snapshot; URL-level provenance; verify before formal Gold"),
        fragment_literal("FR-DEF-02", "definition", 4, "GDPR Article 4(2)",
            "'Processing' means any operation or set of operations which is performed on personal data or on sets of personal data, whether or not by automated means, such as collection, recording, organisation, structuring, storage, adaptation or alteration, retrieval, consultation, use, disclosure by transmission, dissemination or otherwise making available, alignment or combination, restriction, erasure or destruction.",
            "official_text_not_in_local_winter_snapshot; URL-level provenance; verify before formal Gold"),
        fragment_literal("FR-DEF-03", "definition", 4, "GDPR Article 4(7)",
            "'Controller' means the natural or legal person, public authority, agency or other body which, alone or jointly with others, determines the purposes and means of the processing of personal data; where the purposes and means of such processing are determined by Union or Member State law, the controller or the specific criteria for its nomination may be provided for by Union or Member State law.",
            "official_text_not_in_local_winter_snapshot; URL-level provenance; verify before formal Gold"),
        fragment_literal("FR-DEF-04", "definition", 4, "GDPR Article 4(8)",
            "'Processor' means a natural or legal person, public authority, agency or other body which processes personal data on behalf of the controller.",
            "official_text_not_in_local_winter_snapshot; URL-level provenance; verify before formal Gold"),
    ]

    pair_rows = []
    artifacts: dict[str, bytes] = {}
    for kind, ids in (("condition", CONDITION_PAIR_IDS), ("exception", EXCEPTION_PAIR_IDS)):
        for index, rid in enumerate(ids, 1):
            spec = core_specs[rid]
            applicable_raw = build_challenge_bpmn(spec, True, kind)
            not_applicable_raw = build_challenge_bpmn(spec, False, kind)
            app_id = stable_id("challenge_case", BENCHMARK_ID, kind, rid, "applicable")
            non_id = stable_id("challenge_case", BENCHMARK_ID, kind, rid, "not_applicable")
            app_path = f"bpmn/challenges/{app_id}.bpmn"
            non_path = f"bpmn/challenges/{non_id}.bpmn"
            artifacts[app_path] = applicable_raw
            artifacts[non_path] = not_applicable_raw
            pair_rows.append({
                "pair_id": f"{kind.upper()}_PAIR_{index:02d}",
                "pair_kind": kind,
                "requirement_id": rid,
                "observable_fact_difference": (
                    "applicable case satisfies the source condition and contains the mandatory action; "
                    "not-applicable case expresses the condition/exception as not true and routes to End"
                ),
                "source_evidence": spec["citation"],
                "applicable_case": {"case_id": app_id, "bpmn_path": app_path, "reference_semantics": "requirement_applicable=true"},
                "not_applicable_case": {"case_id": non_id, "bpmn_path": non_path, "reference_semantics": "requirement_applicable=false"},
            })
    return {
        "schema_version": "stage3_table3_r5_semantic_challenges@1.0.0",
        "status": "constructed_separate_from_core_f1",
        "not_mixed_with_core_f1": True,
        "modality_fragment_counts": {
            "prohibition": sum(1 for f in fragments if f["modality"] == "prohibition"),
            "permission": sum(1 for f in fragments if f["modality"] == "permission"),
            "definition": sum(1 for f in fragments if f["modality"] == "definition"),
        },
        "fragments": fragments,
        "pairs": pair_rows,
    }, artifacts


def build() -> dict[str, bytes]:
    config = load_json(CONFIG)
    gdpr7_index = gdpr7_sentence_index()
    r4_index = r4_reference_index()
    specs = config["requirements"]
    if len({s["requirement_id"] for s in specs}) != len(specs):
        raise ValueError("duplicate requirement_id")
    core_specs = {s["requirement_id"]: s for s in specs}

    artifacts: dict[str, bytes] = {}
    source_requirements = []
    inference_items = []
    reference_cases = []
    source_text_rows: dict[str, dict] = {}
    context_rows: dict[str, dict] = {}
    case_family_rows = []

    for spec in specs:
        source = build_source_record(config, spec, gdpr7_index, r4_index)
        source["elements"] = {
            "modality": {"value": spec["modality"], "present": True, "evidence": source["excerpt_text"]},
            "actor": {"value": spec["actor_required"], "present": True, "evidence": source["excerpt_text"]},
            "action": {"value": spec["tasks"][spec["mandatory_index"]], "present": True, "evidence": source["excerpt_text"]},
            "condition": {"present": bool(spec.get("condition_present")), "text": spec.get("condition_text", "")},
            "constraint": {"present": bool(spec.get("constraint_present")), "text": spec.get("constraint_text", ""), "order_evidence": spec.get("order_evidence", "")},
            "exception": {"present": bool(spec.get("exception_present")), "text": spec.get("exception_text", "")},
        }
        source["evidence_location"] = {
            "article": spec["article"],
            "paragraph": spec["paragraph"],
            "locator": spec["source_locator"],
            "excerpt_mode": spec["excerpt_mode"],
            "excerpt_text_sha256": source["text_sha256"],
        }
        source["split"] = spec["split"]
        source["scenario_id"] = spec["scenario_id"]
        source["scenario_zh"] = spec["scenario_zh"]
        source["business_scenario_zh"] = spec["business_scenario_zh"]
        source["business_scenario_en"] = spec["business_scenario_en"]
        source["normative_content"] = spec["normative_content"]
        source["task_model"] = {
            "tasks": spec["tasks"],
            "mandatory_index": spec["mandatory_index"],
            "order_pair": spec["order_pair"],
            "source_order_evidence": spec["order_evidence"],
        }
        for element_name, capability in ELEMENT_CAPABILITIES.items():
            source["elements"][element_name].update(capability)
            source["elements"][element_name]["scenario_fact"] = spec["business_scenario_en"]
        source["historical_development"] = bool(spec.get("historical_development"))
        source["exposure_status"] = "historical_development_reused" if spec.get("historical_development") else (
            "existing_stage2_prediction_reused" if spec["source_kind"] == "gdpr7_input" else "no_existing_stage2_prediction_found"
        )
        source["independent_test_candidate"] = (
            spec["split"] == "test" and spec["source_kind"] == "new_article"
        )
        source_requirements.append(source)
        source_text_id = stable_id("src", source["text_sha256"])
        source_text_rows[source_text_id] = {
            "source_text_id": source_text_id,
            "text": source["excerpt_text"],
            "context_text": source.get("context_text") or "",
            "citation": source["citation"],
            "text_sha256": source["text_sha256"],
        }
        context_id = stable_id("ctx", BENCHMARK_ID, spec["requirement_id"])
        context_rows[context_id] = {
            "common_context_id": context_id,
            "business_scenario_en": spec["business_scenario_en"],
            "business_scenario_zh": spec["business_scenario_zh"],
            "applicability_scope": source["context_text"] or "source requirement applies to the modelled business scenario",
            "roles": {"actor_required": spec["actor_required"]},
        }
        family_id = spec["requirement_id"]
        case_family_rows.append({"family_id": family_id, "requirement_id": family_id, "split": spec["split"], "variant_count": 4 if spec["has_variants"] else 1})

        variants = [("control", None)] if not spec["has_variants"] else [(v, v) for v in ("control",) + VARIANT_TYPES]
        for variant_label, mutation in variants:
            case_id = stable_id("case", BENCHMARK_ID, spec["requirement_id"], variant_label)
            bpmn_path = f"bpmn/{case_id}.bpmn"
            raw = build_bpmn(spec, variant_label)
            observed = linear_activity_sequence(raw)
            states = reference_states_for(spec, variant_label, observed)
            validate_expected(spec, variant_label, observed, states)
            artifacts[bpmn_path] = raw
            inference_items.append({
                "case_id": case_id,
                "bpmn_path": bpmn_path,
                "process_id": "Process",
                "source_text_id": source_text_id,
                "common_context_id": context_id,
            })
            reference_cases.append({
                "case_id": case_id,
                "family_id": family_id,
                "requirement_id": spec["requirement_id"],
                "split": spec["split"],
                "variant": "baseline" if variant_label == "control" else variant_label,
                "reference_states": states,
                "target_node": f"Activity_{spec['mandatory_index']}" if variant_label != "missing_action" else None,
                "order_pair": [f"Activity_{spec['order_pair'][0]}", f"Activity_{spec['order_pair'][1]}"],
                "applicable_checks": [k for k, v in states.items() if v != "not_applicable"],
                "reason_codes": {
                    "missing_action": "mandatory_activity_absent" if states["missing_action"] == "violated" else "mandatory_activity_present_or_na",
                    "incorrect_actor": "actor_surface_not_required" if states["incorrect_actor"] == "violated" else "actor_surface_matches_or_na",
                    "out_of_order": "source_order_pair_reversed" if states["out_of_order"] == "violated" else "source_order_pair_preserved_or_na",
                },
                "source_text_sha256": source["text_sha256"],
                "citation": source["citation"],
                "mutation_observed": {
                    "mandatory_present": f"Activity_{spec['mandatory_index']}" in observed["activities"],
                    "actor": observed["actor"],
                    "sequence": observed["sequence"],
                },
                "structural_validation": "passed",
            })

    # Core manifest.
    core_cases = len(reference_cases)
    variant_counts = {v: sum(1 for c in reference_cases if c["variant"] == v) for v in VARIANT_TYPES}
    control_count = sum(1 for c in reference_cases if c["variant"] == "baseline")
    element_counts = {
        "modality": sum(1 for s in source_requirements if s["elements"]["modality"]["present"]),
        "actor": sum(1 for s in source_requirements if s["elements"]["actor"]["present"]),
        "action": sum(1 for s in source_requirements if s["elements"]["action"]["present"]),
        "condition": sum(1 for s in source_requirements if s["elements"]["condition"]["present"]),
        "constraint": sum(1 for s in source_requirements if s["elements"]["constraint"]["present"]),
        "exception": sum(1 for s in source_requirements if s["elements"]["exception"]["present"]),
    }
    scenario_counts: dict[str, int] = {}
    for s in source_requirements:
        scenario_counts[s["scenario_id"]] = scenario_counts.get(s["scenario_id"], 0) + 1

    for rec in source_requirements:
        same_scope = [
            other["requirement_id"]
            for other in source_requirements
            if other["requirement_id"] != rec["requirement_id"]
            and other["article"] == rec["article"]
            and other["paragraph"] == rec["paragraph"]
        ]
        rec["relations"] = {"same_article_paragraph_requirements": sorted(same_scope), "citation": rec["citation"]}

    artifacts["source_requirements.json"] = encoded({
        "schema_version": "stage3_table3_r5_source_requirements@1.0.0",
        "benchmark_id": BENCHMARK_ID,
        "source_url": config["source_url"],
        "document_version": config["document_version"],
        "count": len(source_requirements),
        "requirements": source_requirements,
    })
    artifacts["inference/inference_view.json"] = encoded({
        "schema_version": "stage3_table3_r5_inference_view@1.0.0",
        "benchmark_id": BENCHMARK_ID,
        "gold_labels_present": False,
        "mutation_type_present": False,
        "requirement_id_present": False,
        "items": sorted(inference_items, key=lambda x: x["case_id"]),
    })
    artifacts["inference/source_texts.json"] = encoded({
        "schema_version": "stage3_table3_r5_inference_source_texts@1.0.0",
        "items": [source_text_rows[k] for k in sorted(source_text_rows)],
    })
    artifacts["inference/common_context.json"] = encoded({
        "schema_version": "stage3_table3_r5_inference_common_context@1.0.0",
        "items": [context_rows[k] for k in sorted(context_rows)],
    })
    artifacts["reference/reference_cases.json"] = encoded({
        "schema_version": "stage3_table3_r5_reference_cases@1.0.0",
        "reference_is_gold": False,
        "human_adjudicated": False,
        "cases": sorted(reference_cases, key=lambda x: x["case_id"]),
    })
    artifacts["reference/evaluation_contract.json"] = encoded({
        "schema_version": "stage3_table3_r5_evaluation_contract@1.0.0",
        "status": "frozen_before_test_results",
        "positive_definition": "reference_states == violated",
        "negative_definition": "reference_states == satisfied",
        "positive_unknown_counts_as_fn": True,
        "negative_unknown_recorded_separately_not_tn": True,
        "negative_unknown_counts_as": "unknown_separate_not_tn",
        "not_applicable_handling": "exclude from denominator according to fixed reference states",
        "unrun_metric": None,
        "unrun_metric_policy": "null, never 0",
        "coverage_formula": "(scored_cells - unknown_positive - unknown_negative) / scored_cells",
        "denominator": "all scorable reference cells, not only successfully mapped cells",
        "reporting_fields": ["precision", "recall", "f1", "tp", "fp", "fn", "tn", "coverage", "unknown", "not_applicable"],
        "per_violation_type_reporting": ["missing_action", "incorrect_actor", "out_of_order"],
        "core_and_semantic_challenge_not_pooled": True,
        "current_five_historical_development_not_in_new_test_total": True,
    })

    semantic_challenges, challenge_artifacts = build_semantic_challenges(config, core_specs)
    artifacts["semantic_challenges.json"] = encoded(semantic_challenges)
    for path, raw in challenge_artifacts.items():
        artifacts[path] = raw

    split_manifest = {
        "schema_version": "stage3_table3_r5_split_manifest@1.0.0",
        "seed": config["split_seed"],
        "algorithm": "group_by_requirement_family; force historical R1-R4 five to development; exact Stage2-prediction families to development; new-source families to test; no family crosses split; seed is recorded for deterministic group ordering and future re-derivation",
        "groups": case_family_rows,
        "development_requirement_ids": sorted(s["requirement_id"] for s in source_requirements if s["split"] == "development"),
        "test_requirement_ids": sorted(s["requirement_id"] for s in source_requirements if s["split"] == "test"),
        "test_independent_candidate_count": sum(1 for s in source_requirements if s["independent_test_candidate"]),
        "test_reused_or_exposed_count": sum(1 for s in source_requirements if s["split"] == "test" and not s["independent_test_candidate"]),
    }
    artifacts["split_manifest.json"] = encoded(split_manifest)

    manifest = {
        "schema_version": "stage3_table3_r5_build_manifest@1.0.0",
        "benchmark_id": BENCHMARK_ID,
        "status": "constructed_offline_not_formal_gold",
        "config_path": relative_to_repo(CONFIG),
        "config_sha256": sha_bytes(CONFIG.read_bytes()),
        "builder_sha256": sha_bytes(Path(__file__).read_bytes()),
        "independent_requirements": len(source_requirements),
        "core_cases": core_cases,
        "baseline_controls": control_count,
        "variants_per_type": variant_counts,
        "development_requirements": sum(1 for s in source_requirements if s["split"] == "development"),
        "test_requirements": sum(1 for s in source_requirements if s["split"] == "test"),
        "test_independent_candidate_count": split_manifest["test_independent_candidate_count"],
        "element_coverage": element_counts,
        "scenario_counts": scenario_counts,
        "semantic_challenge_modality_fragment_counts": semantic_challenges["modality_fragment_counts"],
        "semantic_challenge_pair_counts": {
            "condition": sum(1 for p in semantic_challenges["pairs"] if p["pair_kind"] == "condition"),
            "exception": sum(1 for p in semantic_challenges["pairs"] if p["pair_kind"] == "exception"),
        },
        "models_or_predictions_used_for_construction": False,
        "llm_api_calls": 0,
        "network_calls": 0,
        "gold_read": False,
        "artifacts": {name: {"sha256": sha_bytes(raw), "bytes": len(raw)} for name, raw in sorted(artifacts.items())},
    }
    artifacts["manifest.json"] = encoded(manifest)
    return artifacts


def write_artifacts(artifacts: dict[str, bytes], overwrite: bool = False) -> None:
    if OUT.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing {OUT}")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, raw in artifacts.items():
        target = OUT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite {target}")
        target.write_bytes(raw)
    REPORTS.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    summary = {
        "schema_version": "stage3_table3_r5_benchmark_report@1.0.0",
        "benchmark_id": BENCHMARK_ID,
        "status": "data_ready_methods_pending",
        "data_status": "DATA_READY",
        "methods_status": "METHODS_NOT_READY",
        "api_status": "API_AUTHORIZATION_PENDING",
        "formal_release_status": "FORMAL_RELEASE_NOT_APPROVED",
        "counts": {k: manifest[k] for k in [
            "independent_requirements", "core_cases", "baseline_controls", "variants_per_type",
            "development_requirements", "test_requirements", "test_independent_candidate_count",
            "element_coverage", "scenario_counts", "semantic_challenge_modality_fragment_counts",
            "semantic_challenge_pair_counts",
        ]},
        "known_boundaries": [
            "AI-constructed reference is not human Gold.",
            "Conditions, exceptions, prohibitions and deadlines are recorded in the challenge layer; the frozen three-class formula does not fully evaluate their truth.",
            "No real Stage2/Stage3 run is performed in this round.",
            "Any overall F1 must not pool core and semantic-challenge cases.",
        ],
    }
    (REPORTS / "stage3_table3_r5_benchmark_v1.json").write_bytes(encoded(summary))
    lines = [
        "# S3-TABLE3-R5 Benchmark and Readiness",
        "",
        f"- independent requirements: {manifest['independent_requirements']}",
        f"- core cases: {manifest['core_cases']}",
        f"- baseline controls: {manifest['baseline_controls']}",
        f"- variants per type: {manifest['variants_per_type']}",
        f"- development / test requirements: {manifest['development_requirements']} / {manifest['test_requirements']}",
        f"- test independent candidates: {manifest['test_independent_candidate_count']}",
        f"- element coverage: {manifest['element_coverage']}",
        f"- semantic challenge fragments: {manifest['semantic_challenge_modality_fragment_counts']}",
        f"- semantic challenge pairs: {manifest['semantic_challenge_pair_counts']}",
        "",
        "Status: DATA_READY / METHODS_NOT_READY / API_AUTHORIZATION_PENDING / FORMAL_RELEASE_NOT_APPROVED.",
        "",
        "This is an AI-constructed, source-grounded construction reference, not formal human Gold.",
    ]
    (REPORTS / "stage3_table3_r5_benchmark_v1.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    artifacts = build()
    if args.write:
        write_artifacts(artifacts, overwrite=args.overwrite)
    manifest = json.loads(artifacts["manifest.json"])
    print(json.dumps({k: manifest[k] for k in [
        "independent_requirements", "core_cases", "baseline_controls", "variants_per_type",
        "development_requirements", "test_requirements", "test_independent_candidate_count",
        "element_coverage", "semantic_challenge_modality_fragment_counts", "semantic_challenge_pair_counts",
    ]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
