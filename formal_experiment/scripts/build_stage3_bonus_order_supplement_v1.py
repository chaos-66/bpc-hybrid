# -*- coding: utf-8 -*-
"""Build the BONUS development-only order supplement.

The supplement contains GDPR requirements with two action endpoints and an
explicit action-action temporal marker.  No real Stage-2/API prediction is
created.  Endpoints are a documented development-only synthetic stub used to
exercise the frozen SharedRuleOrderAdapterV3 and the shared checker.  The
supplement is never eligible for the paper-facing Table 3.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
GDPR = ROOT.parent / "references/winter_2020_model_check/model_check/input/regulations/gdpr"
OUT = ROOT / "data/development/stage3_bonus_order_supplement_v1"
BPMN = OUT / "bpmn"
MANIFEST = OUT / "manifest.json"

REQS = [
    {
        "num": 1, "rid": "BONUS-ORD-01", "citation": "GDPR Article 7(4)",
        "article_file": "article7.txt", "anchor": "Prior to giving consent",
        "before_action": "informed",
        "after_action": "giving consent",
        "eligibility_class": "STRICT_ELIGIBLE",
        "relation": "The data subject is informed before giving consent.",
        "o_flags": {"O1": True, "O2": True, "O3": True, "O4": True, "O5": True, "O6": True, "O7": True},
    },
    {
        "num": 2, "rid": "BONUS-ORD-02", "citation": "GDPR Article 35(3)",
        "article_file": "article35.txt", "anchor": "Prior to the adoption of the lists",
        "before_action": "apply the consistency mechanism referred to in Article 63",
        "after_action": "adoption of the lists referred to in paragraphs 4 and 5",
        "eligibility_class": "STRICT_ELIGIBLE",
        "relation": "The authority applies the consistency mechanism before adoption of the lists.",
        "o_flags": {"O1": True, "O2": True, "O3": True, "O4": True, "O5": True, "O6": True, "O7": True},
    },
    {
        "num": 3, "rid": "BONUS-ORD-03", "citation": "GDPR Article 40(7)",
        "article_file": "article40.txt", "anchor": "before approving the draft code",
        "before_action": "submit it in the procedure referred to in Article 63 to the Board",
        "after_action": "approving the draft code, amendment or extension",
        "eligibility_class": "STRICT_ELIGIBLE_ADAPTER_FAILURE",
        "relation": "The supervisory authority submits the draft code before approving it.",
        "o_flags": {"O1": True, "O2": True, "O3": True, "O4": True, "O5": True, "O6": True, "O7": True},
    },
    {
        "num": 4, "rid": "BONUS-ORD-04", "citation": "GDPR Article 43(1)",
        "article_file": "article43.txt", "anchor": "after informing the supervisory authority",
        "before_action": "informing the supervisory authority",
        "after_action": "issue and renew certification",
        "eligibility_class": "STRICT_ELIGIBLE",
        "relation": "Certification bodies issue/renew certification after informing the authority.",
        "o_flags": {"O1": True, "O2": True, "O3": True, "O4": True, "O5": True, "O6": True, "O7": True},
    },
    {
        "num": 5, "rid": "BONUS-ORD-05", "citation": "GDPR Article 49(1)(a)",
        "article_file": "article49.txt", "anchor": "after having been informed of the possible risks",
        "before_action": "informed of the possible risks",
        "after_action": "consented to the proposed transfer",
        "eligibility_class": "STRICT_ELIGIBLE_ADAPTER_FAILURE",
        "relation": "The data subject consents after being informed of the risks.",
        "o_flags": {"O1": True, "O2": True, "O3": True, "O4": True, "O5": True, "O6": True, "O7": True},
    },
    {
        "num": 6, "rid": "BONUS-ORD-06", "citation": "GDPR Article 45(1)",
        "article_file": "article45.txt", "anchor": "after assessing the adequacy",
        "before_action": "assessing the adequacy of the level of protection",
        "after_action": "decide",
        "eligibility_class": "STRICT_ELIGIBLE",
        "relation": "The Commission decides after assessing adequacy.",
        "o_flags": {"O1": True, "O2": True, "O3": True, "O4": True, "O5": True, "O6": True, "O7": True},
    },
    {
        "num": 7, "rid": "BONUS-ORD-07", "citation": "GDPR Article 6(1)(b)",
        "article_file": "article6.txt", "anchor": "prior to entering into a contract",
        "before_action": "take steps at the request of the data subject",
        "after_action": "entering into a contract",
        "eligibility_class": "DIAGNOSTIC_BORDERLINE_NOT_OBLIGATION",
        "relation": "Steps requested by the data subject precede entering into the contract.",
        "o_flags": {"O1": True, "O2": True, "O3": True, "O4": True, "O5": True, "O6": True, "O7": True},
    },
    {
        "num": 8, "rid": "BONUS-ORD-08", "citation": "GDPR Article 18(3)",
        "article_file": "article18.txt", "anchor": "before the restriction of processing is lifted",
        "before_action": "informed by the controller",
        "after_action": "lifted",
        "eligibility_class": "DIAGNOSTIC_BORDERLINE_PASSIVE_STATE_ENDPOINT",
        "relation": "The data subject is informed before the restriction is lifted.",
        "o_flags": {"O1": True, "O2": True, "O3": True, "O4": True, "O5": True, "O6": True, "O7": True},
    },
    {
        "num": 9, "rid": "BONUS-ORD-09", "citation": "GDPR Article 36(2)",
        "article_file": "article36.txt", "anchor": "prior to processing",
        "before_action": "consult the supervisory authority",
        "after_action": "processing",
        "eligibility_class": "DIAGNOSTIC_BORDERLINE_NOMINAL_ENDPOINT",
        "relation": "The controller consults the authority before processing.",
        "o_flags": {"O1": True, "O2": True, "O3": True, "O4": True, "O5": True, "O6": True, "O7": True},
    },
]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_sentence(article_file: str, anchor: str) -> str:
    text = (GDPR / article_file).read_text(encoding="utf-8").replace("\n", " ")
    idx = text.casefold().find(anchor.casefold())
    if idx < 0:
        raise RuntimeError(f"anchor not found: {article_file}: {anchor}")
    starts = [text.rfind(ch, 0, idx) for ch in ".!?;:"]
    start = (max(starts) if starts else -1) + 1
    ends = [text.find(ch, idx) for ch in ".!?;"]
    ends = [e for e in ends if e >= 0]
    end = (min(ends) if ends else len(text) - 1) + 1
    return text[start:end].strip()


def _bpmn_xml(process_name: str, before_label: str, after_label: str, *, reverse: bool) -> str:
    before_id = "Activity_Before"
    after_id = "Activity_After"
    order = [(after_id, after_label), (before_id, before_label)] if reverse else [(before_id, before_label), (after_id, after_label)]
    flows = ["Start", *[x[0] for x in order], "End"]
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Definitions" targetNamespace="urn:bpc:stage3-bonus-order-supplement:v1">',
        '  <collaboration id="Collaboration">',
        f'    <participant id="Participant" name="Process Actor" processRef="Process" />',
        '  </collaboration>',
        f'  <process id="Process" name="{escape(process_name)}" isExecutable="false">',
        '    <laneSet id="LaneSet">',
        '      <lane id="Lane_Actor" name="Process Actor">',
        '        <flowNodeRef>Start</flowNodeRef>',
        '        <flowNodeRef>Activity_Before</flowNodeRef>',
        '        <flowNodeRef>Activity_After</flowNodeRef>',
        '        <flowNodeRef>End</flowNodeRef>',
        '      </lane>',
        '    </laneSet>',
        '    <startEvent id="Start" name="Start" />',
        f'    <task id="{before_id}" name="{escape(before_label)}" />',
        f'    <task id="{after_id}" name="{escape(after_label)}" />',
        '    <endEvent id="End" />',
    ]
    for i, (src, tgt) in enumerate(zip(flows, flows[1:])):
        lines.append(f'    <sequenceFlow id="Flow_{i}" sourceRef="{src}" targetRef="{tgt}" />')
    lines += ['  </process>', '</definitions>', '']
    return "\n".join(lines)




def _stub_for_spec(spec: dict) -> dict:
    source_text = _extract_sentence(spec["article_file"], spec["anchor"])
    before = spec["before_action"]
    after = spec["after_action"]
    b0 = source_text.find(before)
    a0 = source_text.find(after)
    return {
        "source_text": source_text,
        "clause_id": f"{spec['rid']}.c1",
        "actions": [
            {"id": f"{spec['rid']}.a1", "text": before, "start": b0, "end": b0 + len(before)},
            {"id": f"{spec['rid']}.a2", "text": after, "start": a0, "end": a0 + len(after)},
        ],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    BPMN.mkdir(parents=True, exist_ok=True)
    rows = []
    items = []
    for spec in REQS:
        source_text = _extract_sentence(spec["article_file"], spec["anchor"])
        before_action = spec["before_action"]
        after_action = spec["after_action"]
        b_start = source_text.find(before_action)
        a_start = source_text.find(after_action)
        if b_start < 0 or a_start < 0:
            raise RuntimeError(f"action span not found for {spec['rid']}: {before_action!r} {after_action!r} in {source_text!r}")
        actions = [
            {"action_id": f"{spec['rid']}.a1", "text": before_action, "start": b_start, "end": b_start + len(before_action), "clause_id": f"{spec['rid']}.c1"},
            {"action_id": f"{spec['rid']}.a2", "text": after_action, "start": a_start, "end": a_start + len(after_action), "clause_id": f"{spec['rid']}.c1"},
        ]
        for variant, reverse, expected in (("baseline", False, "satisfied"), ("out_of_order", True, "violated")):
            case_id = f"case_bonus_ord_{spec['num']:02d}_{variant}"
            rel_path = f"bpmn/{case_id}.bpmn"
            (OUT / rel_path).write_text(
                _bpmn_xml(spec["rid"], before_action, after_action, reverse=reverse),
                encoding="utf-8", newline="\n",
            )
            case = {
                "case_id": case_id,
                "requirement_id": spec["rid"],
                "variant": variant,
                "split": "development",
                "source_family_id": f"gdpr_bonus_order_art_{spec['num']:02d}",
                "source_text_sha256": _sha256(source_text),
                "citation": spec["citation"],
                "reference_states": {
                    "missing_action": "not_applicable",
                    "incorrect_actor": "not_applicable",
                    "out_of_order": expected,
                },
                "scored_types": ["out_of_order"],
                "ineligible_types": ["missing_action", "incorrect_actor"],
                "bpmn_path": rel_path,
                "process_id": "Process",
                "dev_only": True,
                "seen_during_method_development": True,
                "final_table3_eligible": False,
                "mutation_observed": {"sequence": ["Activity_After", "Activity_Before"] if reverse else ["Activity_Before", "Activity_After"]},
                "order_pair": ["Activity_Before", "Activity_After"],
                "target_node": None,
            }
            rows.append(case)
            items.append({"case_id": case_id, "bpmn_path": rel_path, "process_id": "Process"})
    manifest = {
        "schema_version": "stage3_bonus_order_supplement@1.0.0",
        "status": "BONUS_DEVELOPMENT_ONLY_ORDER_SUPPLEMENT",
        "dev_only": True,
        "seen_during_method_development": True,
        "final_table3_eligible": False,
        "real_llm_api_calls": 0,
        "endpoint_policy": "DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_STAGE2_PREDICTION",
        "bpmn_label_policy": "task labels equal the endpoint action surface to isolate order projection/reachability from semantic BPMN-label mapping",
        "requirements": {
            spec["rid"]: {
                "citation": spec["citation"],
                "source_text": _extract_sentence(spec["article_file"], spec["anchor"]),
                "source_text_sha256": _sha256(_extract_sentence(spec["article_file"], spec["anchor"])),
                "before_action": spec["before_action"],
                "after_action": spec["after_action"],
                "relation": spec["relation"],
                "eligibility_class": spec["eligibility_class"],
                "o_flags": spec["o_flags"],
                "endpoint_availability": {
                    "sun": "DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION",
                    "ours": "DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION",
                },
                "endpoint_stub": _stub_for_spec(spec),
            }
            for spec in REQS
        },
        "cases": rows,
        "items": items,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {MANIFEST} with {len(rows)} cases / {len(REQS)} requirements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
