"""Build S3-TABLE3-R5.1 benchmark v2 (offline; zero real LLM calls).

Corrects the R5 v1 construction without rebuilding the project:
- per-type eligibility instead of all-or-nothing has_variants;
- source_family_id and no cross-split family;
- exposure-aware development/test assignment;
- six-element evidence annotations with separate source/context SHA;
- condition/exception separated semantic challenges with valid BPMN;
- A1-A6 targeted corrections.

Reads no predictions, Gold, or .env.  Writes only under the v2 paths.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_stage3_table3_r5_benchmark as v1  # noqa: E402

CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v2.json"
OUT = ROOT / "data/development/stage3_table3_r5_benchmark_v2"
REPORTS = ROOT / "outputs/reports"
BENCHMARK_ID = "stage3_table3_r5_benchmark_v2"
VARIANT_TYPES = ("missing_action", "incorrect_actor", "out_of_order")
ELIGIBILITY_KEY = {
    "missing_action": "eligible_missing_action",
    "incorrect_actor": "eligible_incorrect_actor",
    "out_of_order": "eligible_out_of_order",
}

sha_text = v1.sha_text
sha_bytes = v1.sha_bytes
stable_id = v1.stable_id
encoded = v1.encoded
load_json = v1.load_json
normalized_ws = v1.normalized_ws
relative_to_repo = v1.relative_to_repo
load_article = v1.load_article
excerpt_from_text = v1.excerpt_from_text
add_sequence_flow = v1.add_sequence_flow
NS = v1.NS


# ---------------------------------------------------------------------------
# Source extraction (v2)
# ---------------------------------------------------------------------------
def excerpt_from_span(text: str, start: int, end: int) -> str:
    excerpt = normalized_ws(text)[start:end]
    if not excerpt or normalized_ws(excerpt) != excerpt:
        raise ValueError("char_span excerpt is not normalised/contiguous")
    return excerpt


def find_span(text: str, literal: str) -> tuple[int, int]:
    norm_text = normalized_ws(text)
    norm_lit = normalized_ws(literal)
    pos = norm_text.find(norm_lit)
    if pos < 0:
        raise ValueError(f"literal excerpt not found in processed source: {norm_lit[:60]!r}")
    if norm_text.find(norm_lit, pos + 1) >= 0:
        raise ValueError("explicit excerpt literal is not unique in processed source")
    return pos, pos + len(norm_lit)


def build_source_record_v2(config: dict, spec: dict, gdpr7_index: dict, r4_index: dict) -> dict:
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
        ref = r4_index[spec["r4_rule_id"]]
        return {
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
            "source_status": "derived_via_r4_construction_reference_from_processed_local_snapshot",
        }
    if kind == "gdpr7_input":
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
            "source_status": "gdpr7_frozen_stage2_input_sentence",
        }
    if kind == "new_article":
        path, raw, text, _ = load_article(config, spec["article"])
        char_span = None
        if spec.get("excerpt_mode") == "char_span" and spec.get("excerpt_char_span_text"):
            start, end = find_span(text, spec["excerpt_char_span_text"])
            excerpt = excerpt_from_span(text, start, end)
            char_span = [start, end]
        else:
            excerpt = excerpt_from_text(text, spec["source_locator"], spec["excerpt_mode"])
        context_text, context_ref = extra_context_text_v2(config, spec)
        return {
            **common,
            "source_kind": kind,
            "excerpt_text": excerpt,
            "text_sha256": sha_text(excerpt),
            "source_file_path": relative_to_repo(path),
            "source_file_sha256": sha_bytes(raw),
            "source_dataset": relative_to_repo(path),
            "source_dataset_sha256": sha_bytes(raw),
            "char_span": char_span,
            "context_text": context_text,
            "context_sha256": sha_text(context_text) if context_text else None,
            "context_ref": context_ref,
            "source_status": spec.get(
                "excerpt_source_status",
                "processed_local_winter_snapshot_not_official_verbatim",
            ),
        }
    raise ValueError(f"unknown source kind: {kind}")


def extra_context_text_v2(config: dict, spec: dict) -> tuple[str, dict | None]:
    """Declared external context, only where the v1 builder already did so."""
    v1_mapping = {
        "R5-S1-T3": (14, "within a reasonable period after obtaining the personal data", "sentence"),
        "R5-S1-T4": (14, "within a reasonable period after obtaining the personal data", "sentence"),
        "R5-S3-T3": (21, "The data subject shall have the right to object, on grounds relating", "sentence"),
    }
    entry = v1_mapping.get(spec["requirement_id"])
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
        "scope": "declared_external_context_paragraph",
    }


# ---------------------------------------------------------------------------
# Exception cross-reference text (from the local processed snapshot)
# ---------------------------------------------------------------------------
EXCEPTION_CROSSREF_SPEC = {
    "R5-D-01": ("art13(4)", 13, "where and insofar as the data subject already has the information", "sentence"),
    "R5-D-02": ("art14(5)", 14, "Paragraphs 1 to 4 shall not apply where the data subject already has the information", "sentence"),
    "R5-D-10": ("art17(3)", 17, "processing is necessary for exercising the right of freedom of expression and information", "sentence"),
    "R5-D-11": ("art20(4)", 20, "shall not adversely affect the rights and freedoms of others", "sentence"),
    "R5-S1-T1": ("art13(4)", 13, "where and insofar as the data subject already has the information", "sentence"),
    "R5-S1-T2": ("art13(4)", 13, "where and insofar as the data subject already has the information", "sentence"),
    "R5-S1-T3": ("art14(5)", 14, "Paragraphs 1 to 4 shall not apply where the data subject already has the information", "sentence"),
    "R5-S1-T4": ("art14(5)", 14, "Paragraphs 1 to 4 shall not apply where the data subject already has the information", "sentence"),
    "R5-S3-T1": ("art12(3)-extension", 12, "That period may be extended by two further months", "sentence"),
    "R5-S5-T4": ("art36(2)-extension", 36, "That period may be extended by six weeks", "sentence"),
}


def exception_crossref(config: dict, rid: str) -> dict | None:
    entry = EXCEPTION_CROSSREF_SPEC.get(rid)
    if not entry:
        return None
    label, article, locator, mode = entry
    path, raw, text, _ = load_article(config, article)
    excerpt = excerpt_from_text(text, locator, mode)
    return {
        "paragraph_label": label,
        "text": excerpt,
        "text_sha256": sha_text(excerpt),
        "source_file_path": relative_to_repo(path),
        "source_file_sha256": sha_bytes(raw),
        "source_status": "processed_local_winter_snapshot_not_official_verbatim",
        "provided_to_task": True,
    }


# ---------------------------------------------------------------------------
# Six-element annotation with evidence binding
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

# Actor evidence that cannot be recovered as an exact case-insensitive span
# by the frozen actor-surface token sequence.  Values are exact substrings of
# the corresponding processed source excerpt; the builder asserts this.
ACTOR_EVIDENCE_OVERRIDES = {
    "R5-S6-T1": "the controller and the processor",
    "R5-S6-T2": "the controller and the processor",
    "R5-S7-T1": "the supervisory authority",
    "R5-S8-T1": "certification bodies",
}


def _norm_tokens(value: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", normalized_ws(value).lower()) if t]


def _token_offsets(value: str) -> list[tuple[str, int, int]]:
    text = normalized_ws(value)
    return [(m.group(0).lower(), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]


def _exact_span_for_token_match(excerpt: str, phrase: str, min_n: int = 2) -> str:
    """Return the exact source slice for the longest shared token n-gram.

    The returned value is a case-, punctuation- and whitespace-exact substring
    of ``excerpt``.  Matching is token-normalised only to locate the span; it
    is never returned as source text.
    """
    source_tokens = _token_offsets(excerpt)
    phrase_tokens = _norm_tokens(phrase)
    if not source_tokens or not phrase_tokens:
        return ""
    n = min(len(phrase_tokens), len(source_tokens))
    while n >= min_n:
        for i in range(len(phrase_tokens) - n + 1):
            for j in range(len(source_tokens) - n + 1):
                if [tok for tok, _start, _end in source_tokens[j:j + n]] == phrase_tokens[i:i + n]:
                    start = source_tokens[j][1]
                    end = source_tokens[j + n - 1][2]
                    return excerpt[start:end]
        n -= 1
    return ""


def best_ngram_evidence(excerpt: str, phrase: str, min_n: int = 2) -> str:
    """Longest shared token n-gram returned as exact source substring."""
    return _exact_span_for_token_match(excerpt, phrase, min_n=min_n)


def _action_evidence(excerpt: str, action: str) -> str:
    """Bind the mandatory task-model action to its full exact source sentence.

    Action values are frozen task-model paraphrases.  A single shared noun or
    verb must not stand in for the whole action, so the evidence is the exact
    source sentence that grounds the task.  This cannot alter the Stage2 input
    or the semantic value; it changes evidence.text/SHA only.
    """
    return excerpt


def annotate_elements(spec: dict, source: dict) -> dict:
    excerpt = source["excerpt_text"]
    context = source.get("context_text") or ""
    declared = bool(context)
    action = spec["tasks"][spec["mandatory_index"]]
    citation = spec["citation"]

    def _stage2_scope(scope: str) -> str:
        return {
            "source_excerpt": "stage2_model_input",
            "declared_external_context": "shared_public_task_context",
            "cross_reference_text_outside_stage2_input": "cross_reference_text_not_in_stage2_input",
            "not_present": "absent",
            "not_provided": "absent",
        }.get(scope, "other_not_stage2_input")

    def ev(scope: str, text: str, note: str, declared_source: dict | None = None) -> dict:
        payload = {
            "scope": scope,
            "stage2_input_scope": _stage2_scope(scope),
            "text": text,
            "sha256": sha_text(text) if text else None,
            "note": note,
            "in_input": scope == "source_excerpt",
            # Compatibility field: ONLY true for text actually placed in the
            # final Stage2 API payload.  Context/evaluator material is never
            # counted as Stage2 input.
            "counts_as_in_input": scope == "source_excerpt",
            "counts_as_stage2_input": scope == "source_excerpt",
        }
        if declared_source:
            payload["declared_source"] = declared_source
        return payload

    def external(note: str, text: str) -> dict:
        src = {"type": "common_context" if declared else "provision_citation",
               "text": context if declared else text,
               "citation": citation}
        payload = ev("declared_external_context", text or citation, note, src)
        payload["counts_as_in_input"] = False
        return payload

    # modality
    _etoks = _norm_tokens(excerpt)
    modal_phrase = ""
    for _phrase in ("no longer", "right to", "shall not", "shall", "may"):
        _parts = _phrase.split()
        for _i in range(len(_etoks) - len(_parts) + 1):
            if _etoks[_i:_i + len(_parts)] == _parts:
                modal_phrase = _phrase
                break
        if modal_phrase:
            break
    modal_token = _exact_span_for_token_match(excerpt, modal_phrase, min_n=1) if modal_phrase else ""
    modality = ev("source_excerpt", modal_token, "modal surface in excerpt") if modal_token else external(
        "modality taken from the provision type", spec["modality"])
    # actor
    actor_surface = spec["actor_required"]
    actor_override = ACTOR_EVIDENCE_OVERRIDES.get(spec["requirement_id"])
    actor_token = actor_override if actor_override and actor_override in excerpt else ""
    if not actor_token:
        _surface_norm = normalized_ws(actor_surface)
        _pos = normalized_ws(excerpt).lower().find(_surface_norm.lower())
        if _pos >= 0:
            actor_token = excerpt[_pos:_pos + len(_surface_norm)]
    if actor_token:
        actor = ev("source_excerpt", actor_token, "actor surface in excerpt")
    else:
        # The actor is supplied by the declared role model/common task context,
        # not by the frozen source sentence.  Keep the old external scope; do
        # not turn a missing role surface into a Stage2-input evidence claim.
        actor = external("actor role from provision/role model", actor_surface)
    # action
    a_match = _action_evidence(excerpt, action)
    if a_match:
        action_ev = ev("source_excerpt", a_match, "mandatory action verb matched in excerpt")
    else:
        action_ev = external("mandatory activity is a task-model paraphrase; literal surface not in excerpt", action)
    # condition
    cond = spec.get("condition_text", "")
    if spec.get("condition_present"):
        m = best_ngram_evidence(excerpt, cond, 2)
        if m:
            condition = ev("source_excerpt", m, "condition clause matched in excerpt")
        elif declared:
            condition = ev("declared_external_context", context, "condition supplied as declared external applicability context",
                           {"type": "context_text", "text": context, "citation": citation})
        else:
            condition = external("condition paraphrase; literal clause not in the retrieved excerpt", cond)
    else:
        condition = ev("not_present", "", "condition_present=false")
    # constraint
    cons = spec.get("constraint_text", "")
    if spec.get("constraint_present"):
        m = best_ngram_evidence(excerpt, cons, 2)
        if m:
            constraint = ev("source_excerpt", m, "constraint clause matched in excerpt")
        elif declared:
            constraint = ev("declared_external_context", context, "constraint supplied as declared external context",
                            {"type": "context_text", "text": context, "citation": citation})
        else:
            constraint = external("constraint paraphrase; underlying phrase available in the excerpt only partially", cons)
    else:
        constraint = ev("not_present", "", "constraint_present=false")
    # exception
    exc = spec.get("exception_text", "")
    if spec.get("exception_present"):
        full_match = bool(exc) and normalized_ws(exc).lower() in normalized_ws(excerpt).lower()
        if full_match:
            _full_exc_span = _exact_span_for_token_match(excerpt, exc, min_n=1)
            exception = ev("source_excerpt", _full_exc_span or excerpt,
                           "full exception semantic value present in excerpt, exact source span")
        else:
            cross = exception_crossref_source_cached(spec["requirement_id"])
            if cross:
                exception = ev(
                    "cross_reference_text_outside_stage2_input",
                    cross["text"],
                    (f"exception depends on {cross['paragraph_label']}; the cross-reference text is "
                     "available outside the final Stage2 model input and must not be counted as Stage2 input"),
                )
                exception["cross_reference"] = cross
                exception["cross_reference_only"] = True
                exception["fully_source_grounded_in_stage2_input"] = False
            else:
                # A short generic n-gram must never ground a cross-reference or
                # an otherwise unsupported legal exception.  Keep only a long
                # exact overlap; otherwise record it as external/unsupported.
                m = best_ngram_evidence(excerpt, exc, 4)
                if m and len(_norm_tokens(m)) >= 4:
                    exception = ev("source_excerpt", m, "long exception overlap matched in excerpt")
                else:
                    exception = external(
                        "exception is a cross-reference/paraphrase whose full text is not present in the Stage2 input; "
                        "must NOT be counted as Stage2 input", exc)
                    exception["fully_source_grounded_in_stage2_input"] = False
    else:
        exception = ev("not_present", "", "exception_present=false")

    elements = {
        "modality": {"present": True, "value": spec["modality"], "evidence": modality},
        "actor": {"present": True, "value": actor_surface, "evidence": actor},
        "action": {"present": True, "value": action, "evidence": action_ev},
        "condition": {"present": bool(spec.get("condition_present")), "value": cond, "evidence": condition},
        "constraint": {"present": bool(spec.get("constraint_present")), "value": cons, "evidence": constraint},
        "exception": {"present": bool(spec.get("exception_present")), "value": exc, "evidence": exception},
    }
    return elements


_CROSSREF_CACHE: dict[str, dict | None] = {}


def exception_crossref_source_cached(rid: str) -> dict | None:
    return _CROSSREF_CACHE.get(rid)


# ---------------------------------------------------------------------------
# Core / candidate case generation
# ---------------------------------------------------------------------------
def reference_states_v2(spec: dict, variant: str, observed: dict) -> dict:
    states = {}
    for vtype in VARIANT_TYPES:
        states[vtype] = "satisfied" if spec[ELIGIBILITY_KEY[vtype]] else "not_scored"
    mandatory_id = f"Activity_{spec['mandatory_index']}"
    present = mandatory_id in observed["activities"]
    actor_wrong = observed["actor"] != spec["actor_required"]
    before_id = f"Activity_{spec['order_pair'][0]}"
    after_id = f"Activity_{spec['order_pair'][1]}"
    if before_id in observed["sequence"] and after_id in observed["sequence"]:
        ordered = observed["sequence"].index(before_id) < observed["sequence"].index(after_id)
    else:
        ordered = False
    if states["missing_action"] != "not_scored":
        states["missing_action"] = "violated" if not present else "satisfied"
    if states["incorrect_actor"] != "not_scored":
        states["incorrect_actor"] = "violated" if actor_wrong else "satisfied"
    if states["out_of_order"] != "not_scored":
        states["out_of_order"] = "violated" if not ordered else "satisfied"
    if variant == "missing_action":
        for vt in ("incorrect_actor", "out_of_order"):
            if states.get(vt) != "not_scored":
                states[vt] = "not_applicable"
    return states


def build_bpmn_v2(spec: dict, variant: str) -> bytes:
    return v1.build_bpmn(spec, variant)


def build_candidate_bpmn(spec: dict) -> bytes:
    """A structurally valid baseline process for a non-core candidate asset."""
    actor = spec["actor_required"]
    definitions = ET.Element(f"{{{NS}}}definitions", {"id": "Definitions", "targetNamespace": "urn:bpc:table3:r5:v2:candidate"})
    collaboration = ET.SubElement(definitions, f"{{{NS}}}collaboration", {"id": "Collaboration"})
    ET.SubElement(collaboration, f"{{{NS}}}participant", {"id": "Participant", "name": actor, "processRef": "Process"})
    process = ET.SubElement(definitions, f"{{{NS}}}process", {"id": "Process", "name": actor, "isExecutable": "false"})
    lane_set = ET.SubElement(process, f"{{{NS}}}laneSet", {"id": "LaneSet"})
    lane = ET.SubElement(lane_set, f"{{{NS}}}lane", {"id": "Lane_Actor", "name": actor})
    nodes = ["Start"] + [f"Activity_{i}" for i in range(len(spec["tasks"]))] + ["End"]
    for nid in nodes:
        ET.SubElement(lane, f"{{{NS}}}flowNodeRef").text = nid
    ET.SubElement(process, f"{{{NS}}}startEvent", {"id": "Start", "name": spec["business_scenario_en"]})
    for i in range(len(spec["tasks"])):
        ET.SubElement(process, f"{{{NS}}}task", {"id": f"Activity_{i}", "name": spec["tasks"][i]})
    ET.SubElement(process, f"{{{NS}}}endEvent", {"id": "End"})
    for i, (source, target) in enumerate(zip(nodes, nodes[1:])):
        add_sequence_flow(process, f"Flow_{i}", source, target)
    ET.indent(definitions, space="  ")
    return ET.tostring(definitions, encoding="utf-8", xml_declaration=True) + b"\n"


# ---------------------------------------------------------------------------
# Semantic challenges (condition / exception separated)
# ---------------------------------------------------------------------------
CONDITION_PAIR_IDS = ["R5-S1-T1", "R5-S2-T2", "R5-S3-T1", "R5-S5-T2", "R5-S6-T4", "R5-D-04"]
EXCEPTION_PAIR_IDS = ["R5-D-01", "R5-S1-T3", "R5-D-10", "R5-D-11", "R5-D-12", "R5-S4-T4"]

# Concrete business facts per contrast pair.  Both cases share the same
# evaluated behaviour (the mandatory action is not performed); only these
# applicability facts change.  Each fact carries its provision source.
FACT_SPEC = {
    ("condition", "R5-S1-T1"): (
        {"data_collected_directly_from_data_subject": True, "collection_channel": "direct"},
        {"data_collected_directly_from_data_subject": False, "collection_channel": "indirect"},
    ),
    ("condition", "R5-S2-T2"): (
        {"child_age": 14, "parental_authorisation_given_or_authorised": True},
        {"child_age": 17, "parental_authorisation_given_or_authorised": False},
    ),
    ("condition", "R5-S3-T1"): (
        {"request_under_articles_15_to_22_received": True},
        {"request_under_articles_15_to_22_received": False},
    ),
    ("condition", "R5-S5-T2"): (
        {"seeking_views_of_data_subjects_is_appropriate": True},
        {"seeking_views_of_data_subjects_is_appropriate": False},
    ),
    ("condition", "R5-S6-T4"): (
        {"breach_likely_to_result_in_high_risk": True},
        {"breach_likely_to_result_in_high_risk": False},
    ),
    ("condition", "R5-D-04"): (
        {"processing_likely_to_result_in_high_risk": True},
        {"processing_likely_to_result_in_high_risk": False},
    ),
    ("exception", "R5-D-01"): (
        {"data_subject_already_has_the_information": False},
        {"data_subject_already_has_the_information": True},
    ),
    ("exception", "R5-S1-T3"): (
        {"data_subject_already_has_the_information": False},
        {"data_subject_already_has_the_information": True},
    ),
    ("exception", "R5-D-10"): (
        {"processing_necessary_for_exercise_of_freedom_of_expression_and_information": False},
        {"processing_necessary_for_exercise_of_freedom_of_expression_and_information": True},
    ),
    ("exception", "R5-D-11"): (
        {"article_20_4_exception_applies": False},
        {"article_20_4_exception_applies": True},
    ),
    ("exception", "R5-D-12"): (
        {"breach_unlikely_to_result_in_a_risk": False},
        {"breach_unlikely_to_result_in_a_risk": True},
    ),
    ("exception", "R5-S4-T4"): (
        {"communication_impossible_or_disproportionate_effort": False},
        {"communication_impossible_or_disproportionate_effort": True},
    ),
}


def build_challenge_bpmn_v2(spec: dict) -> bytes:
    """Structurally valid process in which the mandatory action is NOT performed.

    Both cases of a contrast pair share this exact behaviour; only the
    applicability facts differ (stored in the challenge record, not the BPMN).
    """
    actor = spec["actor_required"]
    keep = [i for i in range(len(spec["tasks"])) if i != spec["mandatory_index"]]
    if not keep:
        keep = [0]
    definitions = ET.Element(f"{{{NS}}}definitions", {"id": "Definitions", "targetNamespace": "urn:bpc:table3:r5:v2:challenge"})
    collaboration = ET.SubElement(definitions, f"{{{NS}}}collaboration", {"id": "Collaboration"})
    ET.SubElement(collaboration, f"{{{NS}}}participant", {"id": "Participant", "name": actor, "processRef": "Process"})
    process = ET.SubElement(definitions, f"{{{NS}}}process", {"id": "Process", "name": "Business process", "isExecutable": "false"})
    lane_set = ET.SubElement(process, f"{{{NS}}}laneSet", {"id": "LaneSet"})
    lane = ET.SubElement(lane_set, f"{{{NS}}}lane", {"id": "Lane_Actor", "name": actor})
    nodes = ["Start"] + [f"Activity_{i}" for i in keep] + ["End"]
    for nid in nodes:
        ET.SubElement(lane, f"{{{NS}}}flowNodeRef").text = nid
    ET.SubElement(process, f"{{{NS}}}startEvent", {"id": "Start", "name": "Request or event received"})
    for i in keep:
        ET.SubElement(process, f"{{{NS}}}task", {"id": f"Activity_{i}", "name": spec["tasks"][i]})
    ET.SubElement(process, f"{{{NS}}}endEvent", {"id": "End", "name": "Process ends"})
    for i, (source, target) in enumerate(zip(nodes, nodes[1:])):
        add_sequence_flow(process, f"Flow_{i}", source, target)
    ET.indent(definitions, space="  ")
    return ET.tostring(definitions, encoding="utf-8", xml_declaration=True) + b"\n"


def build_semantic_challenges_v2(config: dict, core_specs: dict, sources: dict) -> tuple[dict, dict[str, bytes]]:
    article_cache: dict[int, str] = {}

    def article_text(article: int) -> str:
        if article not in article_cache:
            _, _, _, text = load_article(config, article)
            article_cache[article] = text
        return article_cache[article]

    def fragment(fid, modality, article, locator, mode, citation, source_status="processed_local_winter_snapshot_not_official_verbatim"):
        text = excerpt_from_text(article_text(article), locator, mode)
        return {"fragment_id": fid, "modality": modality, "citation": citation, "article": article,
                "raw_text": text, "text_sha256": sha_text(text), "source_url": config["source_url"],
                "document_version": config["document_version"], "source_status": source_status}

    def fragment_literal(fid, modality, article, citation, text, source_status):
        return {"fragment_id": fid, "modality": modality, "citation": citation, "article": article,
                "raw_text": text, "text_sha256": sha_text(text), "source_url": config["source_url"],
                "document_version": config["document_version"], "source_status": source_status}

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

    pairs = []
    artifacts: dict[str, bytes] = {}
    for kind, ids in (("condition", CONDITION_PAIR_IDS), ("exception", EXCEPTION_PAIR_IDS)):
        for idx, rid in enumerate(ids, 1):
            spec = core_specs[rid]
            source = sources[rid]
            raw = build_challenge_bpmn_v2(spec)
            case_a = stable_id("challenge_case", BENCHMARK_ID, kind, rid, "a")
            case_b = stable_id("challenge_case", BENCHMARK_ID, kind, rid, "b")
            pa, pb = f"bpmn/challenges/{case_a}.bpmn", f"bpmn/challenges/{case_b}.bpmn"
            artifacts[pa] = raw
            artifacts[pb] = raw
            concrete = FACT_SPEC.get((kind, rid), (
                {"applicability_condition_holds": True}, {"applicability_condition_holds": False}))
            unsupported = (kind, rid) in {
                ("condition", "R5-S5-T2"),  # "where appropriate": no objective method-visible truth
                ("exception", "R5-D-11"),   # Article 20(4) is a legal limitation, not a core exception truth
            }
            semantics_a = (
                "condition_true_duty_in_force_and_action_absent"
                if kind == "condition"
                else "exception_not_applied_duty_in_force_and_action_absent"
            )
            semantics_b = (
                "condition_false_requirement_not_applicable"
                if kind == "condition"
                else "exception_applied_obligation_exempted"
            )
            if unsupported:
                visible_a = {}
                visible_b = {}
                truth_a = {
                    "outcome": "not_scored",
                    "duty_in_force": None,
                    "reference_semantics": "unsupported_no_objective_method_visible_fact",
                }
                truth_b = dict(truth_a)
            else:
                visible_a = dict(concrete[0])
                visible_b = dict(concrete[1])
                if kind == "condition":
                    truth_a = {
                        "condition_holds": True,
                        "duty_in_force": True,
                        "outcome": "violation",
                        "reference_semantics": semantics_a,
                    }
                    truth_b = {
                        "condition_holds": False,
                        "duty_in_force": False,
                        "outcome": "not_applicable",
                        "reference_semantics": semantics_b,
                    }
                else:
                    truth_a = {
                        "exception_applies": False,
                        "duty_in_force": True,
                        "outcome": "violation",
                        "reference_semantics": semantics_a,
                    }
                    truth_b = {
                        "exception_applies": True,
                        "duty_in_force": False,
                        "outcome": "exempted",
                        "reference_semantics": semantics_b,
                    }
            cross = None
            if kind == "exception":
                cross = (annotate_elements(spec, source)["exception"]["evidence"].get("cross_reference"))
            fact_source = {
                "citation": spec["citation"],
                "text": spec.get("condition_text") or spec.get("exception_text"),
                "provision_type": "condition" if kind == "condition" else "exception",
                "cross_reference": cross,
            }
            pair = {
                "pair_id": f"{kind.upper()}_PAIR_{idx:02d}",
                "pair_kind": kind,
                "requirement_id": rid,
                "citation": spec["citation"],
                "evaluated_behavior": "mandatory action not performed (identical in both cases)",
                "changed_factor": "method-visible applicability facts only",
                "source_evidence": {
                    "citation": spec["citation"],
                    "condition_text": spec.get("condition_text", ""),
                    "exception_text": spec.get("exception_text", ""),
                    "cross_reference": cross,
                },
                "scoring_disposition": (
                    "unsupported_not_scored" if unsupported else "scored_separate_from_core_f1"
                ),
                "unsupported_reason": (
                    "no_objective_source_grounded_method_visible_fact_can_decide_this_legal_judgment"
                    if unsupported else None
                ),
                "truth_separation": {
                    "method_visible_facts_key": "method_visible_facts",
                    "evaluator_only_truth_key": "evaluator_only_truth",
                    "evaluator_keys_present_in_method_visible": False,
                },
                "cases": [
                    {
                        "case_id": case_a,
                        "bpmn_path": pa,
                        "method_visible_facts": visible_a,
                        "evaluator_only_truth": truth_a,
                        "fact_source": fact_source,
                    },
                    {
                        "case_id": case_b,
                        "bpmn_path": pb,
                        "method_visible_facts": visible_b,
                        "evaluator_only_truth": truth_b,
                        "fact_source": fact_source,
                    },
                ],
            }
            pairs.append(pair)
    return {
        "schema_version": "stage3_table3_r5_semantic_challenges@2.0.0",
        "status": "constructed_separate_from_core_f1",
        "not_mixed_with_core_f1": True,
        "condition_exception_separately_modelled": True,
        "exception_true_means_obligation_exempted": True,
        "bpmn_has_no_direct_applicability_answer_text": True,
        "each_pair_same_evaluated_behavior": True,
        "modality_fragment_counts": {
            "prohibition": sum(1 for f in fragments if f["modality"] == "prohibition"),
            "permission": sum(1 for f in fragments if f["modality"] == "permission"),
            "definition": sum(1 for f in fragments if f["modality"] == "definition"),
        },
        "fragments": fragments,
        "pairs": pairs,
    }, artifacts


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build() -> dict[str, bytes]:
    config = load_json(CONFIG)
    gdpr7_index = v1.gdpr7_sentence_index()
    r4_index = v1.r4_reference_index()
    specs = config["requirements"]
    core_specs = {s["requirement_id"]: s for s in specs}

    global _CROSSREF_CACHE
    _CROSSREF_CACHE = {s["requirement_id"]: exception_crossref(config, s["requirement_id"]) for s in specs}

    artifacts: dict[str, bytes] = {}
    source_requirements = []
    sources: dict[str, dict] = {}
    inference_items = []
    reference_cases = []
    candidate_assets = []
    source_text_rows: dict[str, dict] = {}
    context_rows: dict[str, dict] = {}
    variant_counts = {v: 0 for v in VARIANT_TYPES}
    control_count = 0
    core_cases = 0

    for spec in specs:
        rid = spec["requirement_id"]
        source = build_source_record_v2(config, spec, gdpr7_index, r4_index)
        elements = annotate_elements(spec, source)
        source["elements"] = elements
        source["eligibility"] = {
            "missing_action": bool(spec["eligible_missing_action"]),
            "incorrect_actor": bool(spec["eligible_incorrect_actor"]),
            "out_of_order": bool(spec["eligible_out_of_order"]),
            "basis": spec["eligibility_basis"],
            "disposition": spec["disposition"],
            "review_issues": spec["review_issues"],
            "review_fixes": spec["review_fixes"],
        }
        source["source_family_id"] = spec["source_family_id"]
        source["split"] = spec["split"]
        source["exposure_status"] = spec["exposure_status"]
        source["core_eligible"] = bool(spec["core_eligible"])
        source["evidence_location"] = {
            "citation": spec["citation"],
            "article": spec["article"],
            "paragraph": spec["paragraph"],
            "locator": spec["source_locator"],
            "excerpt_mode": spec["excerpt_mode"],
            "char_span": source.get("char_span"),
            "source_file_path": source.get("source_file_path"),
            "source_file_sha256": source.get("source_file_sha256"),
            "source_dataset": source.get("source_dataset"),
            "source_dataset_sha256": source.get("source_dataset_sha256"),
            "excerpt_text_sha256": source["text_sha256"],
            "context_text_sha256": source.get("context_sha256"),
            "source_status": source.get("source_status"),
            "candidate_asset_reason": (
                "no eligible core violation type: " + "; ".join(spec["review_issues"])
                if not spec["core_eligible"] else None
            ),
        }
        source["unrepresented_business_facts"] = [
            k for k, payload in elements.items()
            if payload["present"] and payload["evidence"]["scope"] in ("declared_external_context", "not_provided")
        ]
        source_text_id = stable_id("src", source["text_sha256"])
        source_text_rows[source_text_id] = {
            "source_text_id": source_text_id,
            "text": source["excerpt_text"],
            "context_text": source.get("context_text") or "",
            "citation": source["citation"],
            "text_sha256": source["text_sha256"],
            "context_sha256": source.get("context_sha256"),
        }
        context_id = stable_id("ctx", BENCHMARK_ID, rid)
        context_rows[context_id] = {
            "common_context_id": context_id,
            "business_scenario_en": spec["business_scenario_en"],
            "business_scenario_zh": spec["business_scenario_zh"],
            "applicability_scope": source.get("context_text") or "source requirement applies to the modelled business scenario",
            "roles": {"actor_required": spec["actor_required"]},
        }
        source_requirements.append(source)
        sources[rid] = source

        if not spec["core_eligible"]:
            case_id = stable_id("candidate", BENCHMARK_ID, rid)
            bpmn_path = f"bpmn/candidate/{case_id}.bpmn"
            artifacts[bpmn_path] = build_candidate_bpmn(spec)
            candidate_assets.append({
                "case_id": case_id,
                "requirement_id": rid,
                "citation": spec["citation"],
                "source_text_id": source_text_id,
                "bpmn_path": bpmn_path,
                "disposition": "candidate_semantic_asset_not_scored",
                "reason": "; ".join(spec["review_issues"]),
                "legal_basis": spec["eligibility_basis"]["missing_action"],
                "applicability_condition": spec.get("condition_text", ""),
                "source_text_sha256": source["text_sha256"],
                "human_or_formal_gold": False,
            })
            continue

        # core: baseline + eligible variants
        variants = [("control", None)] + [(v, v) for v in VARIANT_TYPES if spec[ELIGIBILITY_KEY[v]]]
        for variant_label, _mutation in variants:
            case_id = stable_id("case", BENCHMARK_ID, rid, variant_label)
            bpmn_path = f"bpmn/{case_id}.bpmn"
            raw = build_bpmn_v2(spec, variant_label)
            observed = v1.linear_activity_sequence(raw)
            states = reference_states_v2(spec, variant_label, observed)
            if variant_label == "control":
                if any(v == "violated" for v in states.values()):
                    raise ValueError(f"control baseline has a violation: {rid}")
            else:
                if sum(1 for v in states.values() if v == "violated") != 1:
                    raise ValueError(f"variant is not single-factor: {rid}/{variant_label}/{states}")
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
                "source_family_id": spec["source_family_id"],
                "requirement_id": rid,
                "split": spec["split"],
                "variant": "baseline" if variant_label == "control" else variant_label,
                "reference_states": states,
                "scored_types": [v for v in VARIANT_TYPES if states[v] != "not_scored"],
                "ineligible_types": [v for v in VARIANT_TYPES if states[v] == "not_scored"],
                "target_node": f"Activity_{spec['mandatory_index']}" if variant_label != "missing_action" else None,
                "order_pair": [f"Activity_{spec['order_pair'][0]}", f"Activity_{spec['order_pair'][1]}"],
                "source_text_sha256": source["text_sha256"],
                "citation": spec["citation"],
                "mutation_observed": {
                    "mandatory_present": f"Activity_{spec['mandatory_index']}" in observed["activities"],
                    "actor": observed["actor"],
                    "sequence": observed["sequence"],
                },
            })
            if variant_label == "control":
                control_count += 1
            else:
                variant_counts[variant_label] += 1
            core_cases += 1

    artifacts["source_requirements.json"] = encoded({
        "schema_version": "stage3_table3_r5_source_requirements@2.0.0",
        "benchmark_id": BENCHMARK_ID,
        "source_url": config["source_url"],
        "document_version": config["document_version"],
        "source_family_rule": "same Article -> same source_family_id; ordinary cross-references do not merge families",
        "count": len(source_requirements),
        "requirements": source_requirements,
    })
    artifacts["inference/inference_view.json"] = encoded({
        "schema_version": "stage3_table3_r5_inference_view@2.0.0",
        "benchmark_id": BENCHMARK_ID,
        "gold_labels_present": False,
        "mutation_type_present": False,
        "requirement_id_present": False,
        "items": sorted(inference_items, key=lambda x: x["case_id"]),
    })
    artifacts["inference/source_texts.json"] = encoded({
        "schema_version": "stage3_table3_r5_inference_source_texts@2.0.0",
        "items": [source_text_rows[k] for k in sorted(source_text_rows)],
    })
    artifacts["inference/common_context.json"] = encoded({
        "schema_version": "stage3_table3_r5_inference_common_context@2.0.0",
        "items": [context_rows[k] for k in sorted(context_rows)],
    })
    artifacts["reference/reference_cases.json"] = encoded({
        "schema_version": "stage3_table3_r5_reference_cases@2.0.0",
        "reference_is_gold": False,
        "human_adjudicated": False,
        "cases": sorted(reference_cases, key=lambda x: x["case_id"]),
    })
    artifacts["reference/fairness_contract.json"] = encoded({
        "schema_version": "stage3_table3_r5_fairness_contract@2.0.0",
        "status": "frozen_before_method_run",
        "supersedes": "stage3_table3_r5_fairness_contract@1.0.0 (retained in v1)",
        "sun_and_ours": {
            "same_raw_regulation": True,
            "same_bpmn_and_public_context": True,
            "same_process_side_parsing": True,
            "same_stage2_to_stage3_interface": True,
            "same_stage3_implementation_parameters_and_candidate_rules": True,
            "same_rule_applicability_handling": True,
            "same_evaluation_scope_reference_labels_unknown_and_na_rules": True,
            "only_difference": "the respective Stage2 method and inherent output handling",
            "information_loss_must_be_reported_separately": True,
        },
        "semantic_vs_format_error": {
            "do_not_treat_ours_format_errors_as_a_complete_denial_of_semantic_content": True,
            "do_not_repair_ours_answers_from_reference": True,
            "report_semantic_prediction_errors_separately_from_coordinate_or_format_loss": True,
        },
        "winter": {
            "same_raw_input_public_business_information_and_evaluation_standard": True,
            "preserves_native_method_required_processing": True,
            "not_same_stage1_stage3_as_sun_ours": True,
            "not_replaced_by_sun_detector": True,
            "unsupported_capabilities_reported_as_unsupported_or_unknown": True,
        },
        "role_mapping": {
            "unified_frozen_dictionary_required_before_prediction": True,
            "dictionary_available_to_all_methods": True,
            "forbidden": ["derive_mapping_from_reference_labels", "reverse_map_from_mutated_wrong_actor",
                          "method_specific_favourable_dictionary", "merge_genuinely_distinct_roles"],
            "this_round": "per-type eligibility and split/family correction only; R4 actor formula is not changed",
        },
        "processed_source_note": "local Winter snapshot text is whitespace-normalised and split; excerpts are contiguous substrings of that processed text, not a claim of official OJ byte identity",
    })
    artifacts["reference/candidate_assets.json"] = encoded({
        "schema_version": "stage3_table3_r5_candidate_assets@2.0.0",
        "not_scored_in_core_f1": True,
        "assets": sorted(candidate_assets, key=lambda x: x["case_id"]),
    })
    artifacts["reference/evaluation_contract.json"] = encoded({
        "schema_version": "stage3_table3_r5_evaluation_contract@2.0.0",
        "status": "frozen_before_test_results",
        "positive_definition": "reference_states[type] == violated",
        "negative_definition": "reference_states[type] == satisfied",
        "not_scored_handling": "exclude from denominator (type not eligible for that requirement)",
        "not_applicable_handling": "exclude from denominator according to fixed reference states",
        "positive_unknown_counts_as_fn": True,
        "negative_unknown_recorded_separately_not_tn": True,
        "unrun_metric": None,
        "unrun_metric_policy": "null, never 0",
        "coverage_formula": "(scored_cells - unknown_positive - unknown_negative) / scored_cells",
        "per_violation_type_reporting": list(VARIANT_TYPES),
        "core_and_semantic_challenge_not_pooled": True,
        "candidate_assets_not_pooled": True,
        "ineligible_types_never_scored": True,
    })
    semantic, challenge_artifacts = build_semantic_challenges_v2(config, core_specs, sources)
    artifacts["semantic_challenges.json"] = encoded(semantic)
    for path, raw in challenge_artifacts.items():
        artifacts[path] = raw

    # split manifest
    family_split: dict[str, set[str]] = {}
    family_members: dict[str, list[str]] = {}
    for s in source_requirements:
        family_split.setdefault(s["source_family_id"], set()).add(s["split"])
        family_members.setdefault(s["source_family_id"], []).append(s["requirement_id"])
    cross = sorted(fid for fid, splits in family_split.items() if len(splits) != 1)
    split_manifest = {
        "schema_version": "stage3_table3_r5_split_manifest@2.0.0",
        "seed": config["split_seed"],
        "algorithm": config["split_algorithm"],
        "seed_actually_used_for": "deterministic ordering only; the split itself is a documented manual/evidence rule, not an emergent seed product",
        "family_id_equals_requirement_id": False,
        "groups": [
            {"source_family_id": fid, "split": sorted(family_split[fid])[0],
             "requirement_ids": sorted(family_members[fid]), "exposed": any(
                 s["exposure_status"] != "no_prior_exposure_found" for s in source_requirements if s["source_family_id"] == fid)}
            for fid in sorted(family_members)
        ],
        "cross_split_families": cross,
        "development_requirement_ids": sorted(s["requirement_id"] for s in source_requirements if s["split"] == "development"),
        "test_requirement_ids": sorted(s["requirement_id"] for s in source_requirements if s["split"] == "test"),
        "core_requirement_ids": sorted(s["requirement_id"] for s in source_requirements if s["core_eligible"]),
        "candidate_requirement_ids": sorted(s["requirement_id"] for s in source_requirements if not s["core_eligible"]),
        "exposed_source_family_ids": config["exposed_source_family_ids"],
        "independent_test_source_family_ids": sorted(
            {s["source_family_id"] for s in source_requirements
             if s["split"] == "test" and s["exposure_status"] == "no_prior_exposure_found"}),
        "exact_input_without_prediction_does_not_prove_family_independence": True,
    }
    artifacts["split_manifest.json"] = encoded(split_manifest)

    # disposition table with excerpt/context/SHA
    disposition_rows = []
    for s in source_requirements:
        spec = core_specs[s["requirement_id"]]
        disposition_rows.append({
            "requirement_id": s["requirement_id"],
            "excerpt_and_context": {
                "excerpt_text": s["excerpt_text"],
                "excerpt_text_sha256": s["text_sha256"],
                "context_text": s.get("context_text") or "",
                "context_text_sha256": s.get("context_sha256"),
                "source_status": s.get("source_status"),
                "char_span": s.get("char_span"),
            },
            "current_tasks": spec["tasks"],
            "current_order": {"order_pair": spec["order_pair"], "order_evidence": spec["order_evidence"]},
            "supported_violation_types": {
                "missing_action": bool(spec["eligible_missing_action"]),
                "incorrect_actor": bool(spec["eligible_incorrect_actor"]),
                "out_of_order": bool(spec["eligible_out_of_order"]),
            },
            "eligibility_basis": spec["eligibility_basis"],
            "problem_category": spec["review_issues"] or ["none_found"],
            "disposition": spec["disposition"],
            "fixes": spec["review_fixes"],
            "evidence_location": s["evidence_location"],
            "source_family_id": s["source_family_id"],
            "split": s["split"],
            "exposure_status": s["exposure_status"],
        })
    artifacts["requirement_disposition.json"] = encoded({
        "schema_version": "stage3_table3_r5_requirement_disposition@2.0.0",
        "benchmark_id": BENCHMARK_ID,
        "columns": ["requirement_id", "excerpt_and_context", "current_tasks", "current_order",
                    "supported_violation_types", "eligibility_basis", "problem_category",
                    "disposition", "fixes", "evidence_location", "source_family_id", "split", "exposure_status"],
        "count": len(disposition_rows),
        "rows": disposition_rows,
    })

    element_counts = {k: sum(1 for s in source_requirements if s["elements"][k]["present"])
                      for k in ["modality", "actor", "action", "condition", "constraint", "exception"]}
    evidence_scope_counts: dict[str, dict[str, int]] = {}
    stage2_input_scope_counts: dict[str, dict[str, int]] = {}
    for k in ["modality", "actor", "action", "condition", "constraint", "exception"]:
        evidence_scope_counts[k] = {}
        stage2_input_scope_counts[k] = {}
        for s in source_requirements:
            e = s["elements"][k]["evidence"]
            scope = e["scope"]
            evidence_scope_counts[k][scope] = evidence_scope_counts[k].get(scope, 0) + 1
            s2scope = e.get("stage2_input_scope", "other_not_stage2_input")
            stage2_input_scope_counts[k][s2scope] = stage2_input_scope_counts[k].get(s2scope, 0) + 1
    scenario_counts: dict[str, int] = {}
    for s in source_requirements:
        sc = next(x["scenario_id"] for x in specs if x["requirement_id"] == s["requirement_id"])
        scenario_counts[sc] = scenario_counts.get(sc, 0) + 1

    manifest = {
        "schema_version": "stage3_table3_r5_build_manifest@2.0.0",
        "benchmark_id": BENCHMARK_ID,
        "status": "constructed_offline_not_formal_gold_v2",
        "supersedes": "stage3_table3_r5_benchmark_v1",
        "config_path": relative_to_repo(CONFIG),
        "config_sha256": sha_bytes(CONFIG.read_bytes()),
        "builder_sha256": sha_bytes(Path(__file__).read_bytes()),
        "independent_requirements": len(source_requirements),
        "core_requirements": sum(1 for s in source_requirements if s["core_eligible"]),
        "candidate_requirements": sum(1 for s in source_requirements if not s["core_eligible"]),
        "core_cases": core_cases,
        "baseline_controls": control_count,
        "variants_per_type": variant_counts,
        "development_requirements": sum(1 for s in source_requirements if s["split"] == "development"),
        "test_requirements": sum(1 for s in source_requirements if s["split"] == "test"),
        "core_development_requirements": sum(1 for s in source_requirements if s["split"] == "development" and s["core_eligible"]),
        "core_test_requirements": sum(1 for s in source_requirements if s["split"] == "test" and s["core_eligible"]),
        "candidate_test_requirements": sum(1 for s in source_requirements if s["split"] == "test" and not s["core_eligible"]),
        "source_family_count": len(family_members),
        "source_family_count_by_split": {
            "development": len({s["source_family_id"] for s in source_requirements if s["split"] == "development"}),
            "test": len({s["source_family_id"] for s in source_requirements if s["split"] == "test"}),
        },
        "independent_test_source_family_ids": split_manifest["independent_test_source_family_ids"],
        "cross_split_families": cross,
        "element_coverage": element_counts,
        "element_evidence_scope_counts": evidence_scope_counts,
        "element_stage2_input_scope_counts": stage2_input_scope_counts,
        "scenario_counts": scenario_counts,
        "semantic_challenge_modality_fragment_counts": semantic["modality_fragment_counts"],
        "semantic_challenge_pair_counts": {
            "condition": sum(1 for p in semantic["pairs"] if p["pair_kind"] == "condition"),
            "exception": sum(1 for p in semantic["pairs"] if p["pair_kind"] == "exception"),
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
        "independent_requirements", "core_requirements", "candidate_requirements",
        "core_cases", "baseline_controls", "variants_per_type",
        "development_requirements", "test_requirements", "source_family_count",
        "cross_split_families", "element_coverage",
    ]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())





