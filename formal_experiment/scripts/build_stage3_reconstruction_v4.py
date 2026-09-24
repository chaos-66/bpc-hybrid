"""Build source-grounded, scoped controls and single-error variants; zero models/API.

This creates a new AI-authored construction reference, never edits human Gold.
No checking prediction is read to choose or validate a control. XML validation
only proves the intended construction, not an independent legal adjudication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/stage3_reconstruction_v4.json"
OUT = ROOT / "data/development/stage3_reconstruction_v4"
NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
TYPES = ("missing_action", "incorrect_actor", "out_of_order")
VARIANTS = ("control",) + TYPES
ET.register_namespace("", NS)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def extract_source(spec: dict, source_dir: Path) -> dict:
    source = source_dir / f"article{spec['article']}.txt"
    raw = source.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    lines = text.splitlines(keepends=True)
    candidates, context, offset = [], [], 0
    for line in lines:
        stripped = line.strip()
        start = offset + len(line) - len(line.lstrip())
        if stripped.startswith(spec["locator_prefix"]):
            if spec.get("first_sentence_only"):
                stripped = stripped.split(". ", 1)[0] + "."
            candidates.append((start, stripped))
        if any(stripped.startswith(p) for p in spec["exception_context_prefixes"]):
            context.append({"char_span": [start, start + len(stripped)], "text": stripped})
        offset += len(line)
    if len(candidates) != 1:
        raise ValueError(f"ambiguous/missing source locator: {spec['rule_id']}")
    start, excerpt = candidates[0]
    if text[start:start + len(excerpt)] != excerpt:
        raise ValueError("source offset mismatch")
    evidence = {}
    for name in ("order_marker", "obligation_evidence", "executor_evidence"):
        phrase = spec[name]
        if excerpt.count(phrase) != 1:
            raise ValueError(f"evidence must occur exactly once: {name}")
        pos = excerpt.index(phrase)
        evidence[name] = {"text": phrase, "span_in_excerpt": [pos, pos + len(phrase)]}
    return {"source_path": source.relative_to(ROOT.parent).as_posix(),
            "source_file_sha256": sha(raw), "offset_convention": "UTF-8 decoded; CRLF normalized to LF",
            "char_span": [start, start + len(excerpt)], "text": excerpt,
            "text_sha256": sha(excerpt.encode("utf-8")), "evidence": evidence,
            "applicability_context": context}


def create_bpmn(spec: dict, variant: str) -> bytes:
    if variant not in VARIANTS:
        raise ValueError("unknown mutation")
    # The inherited minidom Winter parser expects unprefixed tag names, just
    # like the official GDPR BPMN files. The default namespace preserves URI.
    ET.register_namespace("", NS)
    defs = ET.Element(f"{{{NS}}}definitions", {"id": "Definitions", "targetNamespace": "urn:bpc:reconstruction:v4"})
    collab = ET.SubElement(defs, f"{{{NS}}}collaboration", {"id": "Collaboration"})
    actor = spec["wrong_executor"] if variant == "incorrect_actor" else spec["required_executor"]
    ET.SubElement(collab, f"{{{NS}}}participant", {"id": "Participant", "name": actor, "processRef": "Process"})
    # Winter reads process.name; Sun reads the collaboration participant.
    # Give both representations the same executor, including actor mutations.
    process = ET.SubElement(defs, f"{{{NS}}}process", {"id": "Process", "name": actor, "isExecutable": "false"})
    ET.SubElement(process, f"{{{NS}}}startEvent", {"id": "Start", "name": spec["start_label"]})
    indexes = list(range(len(spec["tasks"])))
    required, later = spec["mandatory_task_index"], spec["later_task_index"]
    if variant == "missing_action":
        indexes.remove(required)
    elif variant == "out_of_order":
        indexes[required], indexes[later] = indexes[later], indexes[required]
    for idx in sorted(indexes):
        ET.SubElement(process, f"{{{NS}}}task", {"id": f"Activity_{idx}", "name": spec["tasks"][idx]})
    ET.SubElement(process, f"{{{NS}}}endEvent", {"id": "End"})
    nodes = ["Start"] + [f"Activity_{i}" for i in indexes] + ["End"]
    for i, (a, b) in enumerate(zip(nodes, nodes[1:])):
        ET.SubElement(process, f"{{{NS}}}sequenceFlow", {"id": f"Flow_{i}", "sourceRef": a, "targetRef": b})
    ET.indent(defs, space="  ")
    return ET.tostring(defs, encoding="utf-8", xml_declaration=True) + b"\n"


def inspect_model(raw: bytes) -> dict:
    root = ET.fromstring(raw)
    ns = {"b": NS}
    tasks = {x.get("id"): x.get("name") for x in root.findall(".//b:task", ns)}
    owner = root.find(".//b:participant", ns).get("name")
    edges = [(x.get("sourceRef"), x.get("targetRef")) for x in root.findall(".//b:sequenceFlow", ns)]
    nodes = set(tasks) | {"Start", "End"}
    if len(edges) != len(nodes) - 1 or any(a not in nodes or b not in nodes for a, b in edges):
        raise ValueError("invalid node/edge population")
    chain, current = [], "Start"
    while current != "End":
        if current in chain:
            raise ValueError("cycle in sequential construction")
        chain.append(current)
        outgoing = [b for a, b in edges if a == current]
        if len(outgoing) != 1:
            raise ValueError("disconnected/branching construction")
        current = outgoing[0]
    if set(chain) | {"End"} != nodes:
        raise ValueError("unreachable nodes")
    return {"tasks": tasks, "executor": owner, "sequence": chain + ["End"]}


def validate_construction(spec: dict, raw: bytes, variant: str) -> dict:
    observed = inspect_model(raw)
    required = f"Activity_{spec['mandatory_task_index']}"
    later = f"Activity_{spec['later_task_index']}"
    missing = required not in observed["tasks"]
    actor = None if missing else observed["executor"] != spec["required_executor"]
    order = None if missing else observed["sequence"].index(required) > observed["sequence"].index(later)
    flags = dict(zip(TYPES, (missing, actor, order)))
    expected = {t: t == variant for t in TYPES}
    if variant == "missing_action":
        expected.update(incorrect_actor=None, out_of_order=None)
    if flags != expected:
        raise ValueError(f"construction differs from specified single mutation: {flags}")
    if sum(v is True for v in flags.values()) != (variant != "control"):
        raise ValueError("not exactly one scoped semantic error")
    return {t: "not_applicable" if v is None else "violated" if v else "satisfied" for t, v in flags.items()}


def build(config: dict | None = None) -> dict[str, bytes]:
    config = config or json.loads(CONFIG.read_text(encoding="utf-8"))
    specs = config["rules"]
    if len({s["rule_id"] for s in specs}) != len(specs):
        raise ValueError("duplicate source requirements")
    source_dir = ROOT.parent / config["source_directory"]
    artifacts, input_rules, references, inference = {}, [], [], []
    counter = 0
    # IDs are opaque to downstream inference: deterministic hash, not mutation names.
    for spec in specs:
        source = extract_source(spec, source_dir)
        rule_id = spec["rule_id"]
        input_rules.append({"rule_id": rule_id, "sentences": [{
            "sample_id": f"gdpr_{rule_id}_s001", "source_id": f"gdpr_{rule_id}_s001",
            "sentence_idx": 1, "approved_text_en": source["text"],
            "text_sha256": source["text_sha256"], "char_span": source["char_span"]}],
            "source_file_sha256": source["source_file_sha256"], "citation": spec["citation"]})
        for variant in VARIANTS:
            counter += 1
            case_id = "case_" + sha(f"s3-v4:{rule_id}:{variant}".encode())[:12]
            bpmn_name = f"bpmn/{case_id}.bpmn"
            raw = create_bpmn(spec, variant)
            states = validate_construction(spec, raw, variant)
            artifacts[bpmn_name] = raw
            inference.append({"case_id": case_id, "bpmn_path": f"data/development/stage3_reconstruction_v4/{bpmn_name}", "process_id": "Process"})
            references.append({"case_id": case_id, "family_id": rule_id, "rule_id": rule_id,
                               "variant": variant, "reference_states": states,
                               "applicability_zh": spec["applicability_zh"],
                               "source": source, "mandatory_activity": f"Activity_{spec['mandatory_task_index']}",
                               "later_activity": f"Activity_{spec['later_task_index']}",
                               "required_executor": spec["required_executor"],
                               "reference_origin": "AI source interpretation + deterministic mutation construction"})
    artifacts["stage2_input.json"] = encoded({"schema_version": "stage3_reconstruction_stage2_input@1.0.0",
        "dataset_id": "stage3_scoped_gdpr_v4", "gold_visible": False,
        "counts": {"rules": len(specs), "sentences": len(specs)}, "rules": input_rules})
    artifacts["inference_view.json"] = encoded({"schema_version": "stage3_reconstruction_inference@1.0.0",
        "safety": {"gold_labels_present": False, "rule_id_present": False},
        "items": sorted(inference, key=lambda x: x["case_id"])})
    artifacts["construction_reference.json"] = encoded({"schema_version": "stage3_construction_reference@1.0.0",
        "is_gold": False, "human_adjudicated": False, "release_gate": config["release_gate"],
        "evaluation_scope": config["evaluation_scope"], "cases": references})
    artifacts["manifest.json"] = encoded({"schema_version": "stage3_reconstruction_build@1.0.0",
        "status": "constructed_before_predictions_not_formal_gold", "config_sha256": sha(CONFIG.read_bytes()),
        "builder_sha256": sha(Path(__file__).read_bytes()), "case_count": counter,
        "independent_source_requirements": len(specs), "control_count": len(specs),
        "violation_count_by_type": {t: len(specs) for t in TYPES},
        "scored_reference_cells": sum(s != "not_applicable" for r in references for s in r["reference_states"].values()),
        "reference_not_applicable_cells": sum(s == "not_applicable" for r in references for s in r["reference_states"].values()),
        "models_or_predictions_used_for_construction": False, "llm_api_calls": 0,
        "artifacts": {name: {"sha256": sha(raw), "bytes": len(raw)} for name, raw in artifacts.items()}})
    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--refresh-unscored-models", action="store_true")
    args = parser.parse_args()
    artifacts = build()
    if args.refresh_unscored_models:
        if args.write:
            raise ValueError("choose build or refresh, not both")
        old = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
        if old["status"] != "constructed_before_predictions_not_formal_gold":
            raise ValueError("not an unreleased construction draft")
        if (ROOT / "outputs/development/stage3_table3_v4").exists():
            raise ValueError("Stage 3 output exists: use a new benchmark version")
        for name, binding in old["artifacts"].items():
            if sha((OUT / name).read_bytes()) != binding["sha256"]:
                raise ValueError(f"draft already modified: {name}")
        if set(old["artifacts"]) != set(artifacts) - {"manifest.json"}:
            raise ValueError("model refresh cannot change membership")
        for name, raw in artifacts.items():
            if not name.startswith("bpmn/") and name != "manifest.json":
                if (OUT / name).read_bytes() != raw:
                    raise ValueError("refresh cannot change source/reference/inference view")
        for name, raw in artifacts.items():
            if name.startswith("bpmn/") or name == "manifest.json":
                (OUT / name).write_bytes(raw)
    if args.write:
        if OUT.exists():
            raise FileExistsError(f"refusing to overwrite {OUT}")
        OUT.mkdir(parents=True)
        for name, raw in artifacts.items():
            target = OUT / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(raw)
    print(json.dumps({"written": args.write or args.refresh_unscored_models, **{k: v for k, v in json.loads(artifacts["manifest.json"]).items() if k != "artifacts"}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
