"""EStG-150 B0 enhanced v6 development (versioned, non-paper-faithful claim).

Improvements vs b0_enhanced v5 (v3 file):
- v4 expanded patterns (51 patterns; v3 had 29) and v2 lexicon (161 entries; v1 had 64)
- clause nucleus rules: condition/constraint/exception subordinate predicates do not promote to clauses
- ablation mode flag: hybrid (default), classifier_only, marker_only, gold_clause_seg_oracle
- per-clause diagnostic: classifier label/confidence/margin, English marker candidate, final route
- phrase resolvers v6:
    actor: must contain _ACTOR_LEX head or non-pronoun non-abstract NP; smaller sufficient only
    action: smallest sufficient span (head + bounded object/complement); never keeps aux/passive head only
    scope: carve-out/applicability/performance-limit test for condition/constraint/exception split
    actor_action_map: predicate ownership only; no first-actor fanout
- safe Tsurgeon preserved (v6 keeps the same bridge class; v6 config still references the
  safe batch bridge that already returns terminal_tree_removal_count)

Does not modify Gold/Layer E; no LLM/API; does not overwrite prior runs.
"""

from __future__ import annotations

import os
import re
import shutil as _shutil_inline  # noqa: F401
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.estg150_b0_development import (
    Estg150B0DevelopmentError,
    load_object,
    sha256_file,
)
from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, SCHEMA_VERSION, validate_canonical
from bpc_hybrid.sun_style.corenlp_runtime import (
    CoreNLPContractError,
    validate_annotation,
)
from bpc_hybrid.sun_style.sun_b0 import (
    LockedBertTextCNNInference,
    ModalityPrediction,
    SunB0CompositionError,
    load_s26_config,
)
from bpc_hybrid.estg150_b0_development_v2 import (
    _run,
    _write_rule_plan,
    parse_bridge_output_multi,
    split_german_units,
    sun_table8_any_overlap_diagnostic,
    _plain_span,
    _token_span,
    _supported_span,
    _verify_runtime_identity,
    _predict_in_batches,
)

# --- v6 identity ----------------------------------------------------------
METHOD_ID = "sun_rule_only"
METHOD_VARIANT = "b0_enhanced_v6"
BRIDGE_CLASS = "SunPhraseRuleBatchBridgeMulti"  # safe batch bridge reused as-is
PATTERNS_REL = "resources/corenlp/sun_phrase_patterns_v4_expanded.json"
BRIDGE_REL = "tools/corenlp/SunPhraseRuleBatchBridgeSafeV2.java"  # see note in module docstring
MODE_HYBRID = "hybrid"
MODE_CLASSIFIER_ONLY = "classifier_only"
MODE_MARKER_ONLY = "marker_only"
MODE_GOLD_CLAUSE_SEG_ORACLE = "gold_clause_seg_oracle"
ALLOWED_MODES = {MODE_HYBRID, MODE_CLASSIFIER_ONLY, MODE_MARKER_ONLY, MODE_GOLD_CLAUSE_SEG_ORACLE}

# --- Modality marker regexes (v2 lexicon derived) --------------------------
# Each regex matches a literal marker surface; classification is the canonical class.
_DEF_PHRASE = re.compile(
    r"\b(?:shall\s+mean|means|is\s+defined\s+as|are\s+defined\s+as|refers\s+to|"
    r"denotes|is\s+understood\s+as|shall\s+be\s+construed\s+as|"
    r"is\s+the\s+difference|amounts?\s+to|also\s+include|shall\s+be\s+deemed)\b",
    re.IGNORECASE,
)
_PROH = re.compile(
    r"\b(?:shall\s+not|must\s+not|may\s+not|is\s+not\s+permitted|is\s+prohibited|"
    r"is\s+not\s+allowed|no\s+\w+\s+shall|must\s+never|"
    r"cannot|can\s+not|shall\s+never)\b",
    re.IGNORECASE,
)
_OBL = re.compile(
    r"\b(?:shall|must|is\s+required\s+to|is\s+obliged\s+to|need\s+to|has\s+to|"
    r"should)\b",
    re.IGNORECASE,
)
_PERM = re.compile(
    r"\b(?:may|is\s+permitted\s+to|is\s+allowed\s+to|is\s+authorized\s+to|can)\b",
    re.IGNORECASE,
)
_MODAL_ANCHOR = re.compile(
    r"\b(?:shall\s+not|must\s+not|may\s+not|shall\s+mean|shall|must|may|means|"
    r"is\s+defined\s+as|are\s+defined\s+as|refers\s+to|denotes|should|"
    r"is\s+required\s+to|is\s+obliged\s+to|is\s+prohibited|is\s+not\s+permitted|"
    r"is\s+not\s+allowed|is\s+authorized\s+to|is\s+allowed\s+to|is\s+permitted\s+to|"
    r"has\s+to|need\s+to)\b",
    re.IGNORECASE,
)
# Coordination / shared modal anchors that legitimately split a clause
_COORD_AND_DEONTIC = re.compile(
    r"\band\s+(?=(?:the\s+)?(?:taxpayer|employee|employer|authority|fund|"
    r"person|minister|office|association|they|he|she|it|"
    r"company|operator|controller|processor|recipient|board|court|"
    r"inspector|driver|officer|expert|physician|judge|prosecutor|"
    r"insured|farmer|forester|trader|successor|provider|user)\b)",
    re.IGNORECASE,
)
_COORD_DEONTIC_AFTER_AND = re.compile(
    r"\band\s+(?=(?:shall|must|may|should|can|need)\b)",
    re.IGNORECASE,
)
_SEMI_SPLIT = re.compile(r";")
_COMMA_CONJ = re.compile(r",\s+(?:and|or|but)\b", re.IGNORECASE)
_AND_OR = re.compile(r"\b(?:and|or|but)\b", re.IGNORECASE)

# --- Scope markers (v2 lexicon) -------------------------------------------
# The carve-out / applicability / performance-limit test mirrors extraction
# contract v1 §8. Condition/exception are pre-modality; constraint is
# performance-limit sense only and is rejected when the marker sits in a
# subordinator that has already been classified as condition.
_EXC_MARKERS = re.compile(
    r"\b(?:unless|except|excluding|notwithstanding|"
    r"other\s+than|save(?:\s+where)?|"
    r"with\s+the\s+exception|apart\s+from|regardless\s+of|"
    r"even\s+if|shall\s+not\s+apply|does\s+not\s+apply|do\s+not\s+apply|"
    r"in\s+derogation\s+of)\b",
    re.IGNORECASE,
)
_COND_MARKERS = re.compile(
    r"\b(?:if|when|whenever|where|provided\s+that|once|in\s+case(?:\s+of)?|"
    r"in\s+the\s+event(?:\s+of|\s+that)?|"
    r"to\s+the\s+extent(?:\s+that)?|"
    r"insofar(?:\s+as)?|subject\s+to|"
    r"as\s+long\s+as|so\s+long\s+as|"
    r"upon(?:\s+the\s+occurrence)?|after|before|on\s+condition(?:\s+that)?|"
    r"as\s+soon\s+as(?:\s+not)?|until(?:\s+not)?|"
    r"in\s+the\s+context\s+of|conditioned\s+(?:on|upon))\b",
    re.IGNORECASE,
)
_CONS_MARKERS = re.compile(
    r"\b(?:within|before|after|during|until|throughout|prior\s+to|"
    r"at\s+least|at\s+most|"
    r"no\s+(?:earlier|later|less|more)(?:\s+than)?|"
    r"only|up\s+to|not\s+(?:to\s+)?exceed|exceeds|"
    r"for\s+the\s+purpose(?:\s+s)?\s+of|for\s+purposes\s+of|"
    r"in\s+accordance\s+with|pursuant\s+to|"
    r"under\s+(?:section|paragraph|article)?|within\s+the\s+meaning|"
    r"for\s+a\s+period|between|"
    r"solely|exclusively|generally|without\s+undue|"
    r"in\s+such\s+(?:a\s+)?quantity|to\s+an\s+annual|"
    r"by\s+(?:double-entry|means\s+of|way\s+of|reference)|"
    r"as\s+defined\s+in|"
    r"greater(?:\s+than)?|less(?:\s+than)?|equal(?:\s+to)?|"
    r"minimum|maximum|not\s+equal)\b",
    re.IGNORECASE,
)
_SUBORD_HEAD = re.compile(
    r"^\s*(?:if|when|whenever|unless|where|provided|except|excluding|"
    r"notwithstanding|in\s+case|in\s+the\s+event|to\s+the\s+extent|"
    r"insofar|subject\s+to|as\s+long\s+as|so\s+long\s+as|"
    r"upon|on\s+condition|as\s+soon\s+as|until|"
    r"in\s+the\s+context|conditioned|once)\b",
    re.IGNORECASE,
)

# --- Actor lexicon (v2 derived) -------------------------------------------
# Head-noun actor markers; only NPs whose head lemma is in this set OR that
# include any of these tokens are admitted as actors. Pure pronoun or pure
# abstract-noun NPs are excluded by the resolver below.
_ACTOR_LEX = frozenset({
    "taxpayer", "taxpayers", "employee", "employees", "employer", "employers",
    "authority", "authorities", "fund", "funds", "person", "persons", "company",
    "companies", "operator", "operators", "minister", "office", "association",
    "associations", "farmer", "farmers", "forester", "foresters", "trader",
    "traders", "successor", "successors", "insured", "provider", "providers",
    "controller", "processor", "recipient", "recipients", "user", "users",
    "board", "court", "inspector", "inspectors", "driver", "drivers", "officer",
    "officers", "expert", "experts", "physician", "judge", "judges", "prosecutor",
    "prosecutors", "customer", "customers", "client", "clients", "consumer",
    "consumers", "tenant", "tenants", "landlord", "landlords", "owner", "owners",
})
_NON_ACTOR = frozenset({
    "it", "this", "these", "those", "they", "he", "she", "we", "i", "which",
    "that", "who", "whom", "whose", "profit", "income", "difference", "amount",
    "expenditure", "allowance", "period", "year", "tax", "rate", "section",
    "paragraph", "item", "items", "meaning", "purpose", "case", "extent",
    "quantity", "asset", "assets", "contribution", "contributions", "income",
    "revenue", "cost", "costs", "fee", "fees", "sum", "sums", "time", "times",
    "day", "days", "week", "weeks", "month", "months", "year", "years", "date",
    "information", "data", "record", "records", "report", "reports",
    "notice", "notices", "request", "requests", "statement", "statements",
    "amount", "amounts", "rate", "rates", "level", "levels", "kind", "kinds",
    "type", "types", "form", "forms", "manner", "way", "ways", "means",
    "method", "methods", "return", "returns", "report", "reports", "claim",
    "claims", "application", "applications", "document", "documents",
    "the", "a", "an",
})


# --- Modality scorer + resolver ------------------------------------------
def english_marker_modality_v6(text: str) -> tuple[str | None, str | None]:
    """Definition-first marker scoring; returns (label, surface)."""
    if not text or not text.strip():
        return None, None
    core = text
    if _DEF_PHRASE.search(core):
        if _PROH.search(core) and not re.search(
            r"\b(?:shall\s+mean|means|is\s+defined|refers\s+to|denotes)\b", core, re.I
        ):
            return "prohibition", "definition_and_prohibition"
        return "definition", "definition_marker"
    m = _PROH.search(core)
    if m:
        return "prohibition", m.group(0).casefold()
    m = _OBL.search(core)
    if m:
        return "obligation", m.group(0).casefold()
    m = _PERM.search(core)
    if m:
        return "permission", m.group(0).casefold()
    return None, None


def resolve_modality_v6(
    *,
    english_clause: str,
    classifier: ModalityPrediction,
    de_aligned: bool,
    mode: str,
) -> tuple[ModalityPrediction, str, dict[str, Any]]:
    """Return (final_prediction, route, diagnostic)."""
    en_label, en_surface = english_marker_modality_v6(english_clause)
    diagnostic: dict[str, Any] = {
        "classifier_label": classifier.label,
        "classifier_confidence": classifier.confidence,
        "english_marker_label": en_label,
        "english_marker_surface": en_surface,
        "de_aligned": de_aligned,
        "mode": mode,
    }
    if mode == MODE_CLASSIFIER_ONLY:
        route = "aligned_classifier_fallback" if de_aligned else "misaligned_classifier_fallback"
        return classifier, route, diagnostic
    if mode == MODE_MARKER_ONLY:
        if en_label is None:
            # explicit unsupported diagnostic
            return ModalityPrediction("obligation", 0.0), "marker_only_unsupported", diagnostic
        if en_label == "definition":
            return ModalityPrediction(en_label, max(classifier.confidence, 0.62)), "en_definition", diagnostic
        if en_label == "prohibition":
            return ModalityPrediction(en_label, max(classifier.confidence, 0.65)), "en_prohibition", diagnostic
        if en_label == "obligation":
            return ModalityPrediction(en_label, max(classifier.confidence, 0.55)), "en_obligation", diagnostic
        if en_label == "permission":
            return ModalityPrediction(en_label, max(classifier.confidence, 0.55)), "en_permission", diagnostic
        return ModalityPrediction(en_label, 0.5), "marker_only_unsupported", diagnostic
    # hybrid (default) — matches v5 routing
    if en_label == "definition":
        diagnostic["english_marker_surface"] = en_surface or "definition_marker"
        return ModalityPrediction("definition", max(classifier.confidence, 0.62)), "en_definition", diagnostic
    if en_label == "prohibition":
        return ModalityPrediction("prohibition", max(classifier.confidence, 0.65)), "en_prohibition", diagnostic
    if en_label == "obligation":
        if de_aligned and classifier.label == "obligation" and classifier.confidence >= 0.55:
            return classifier, "aligned_agree_obligation", diagnostic
        return ModalityPrediction("obligation", max(classifier.confidence, 0.55)), "en_obligation", diagnostic
    if en_label == "permission":
        if de_aligned and classifier.label == "permission" and classifier.confidence >= 0.55:
            return classifier, "aligned_agree_permission", diagnostic
        return ModalityPrediction("permission", max(classifier.confidence, 0.55)), "en_permission", diagnostic
    if de_aligned:
        return classifier, "aligned_classifier_fallback", diagnostic
    return classifier, "misaligned_classifier_fallback", diagnostic


# --- Segmentation (clause nucleus rules) ----------------------------------
def _token_abs_span(sentence: Mapping[str, Any], token_index_1based: int) -> tuple[int, int]:
    tok = sentence["tokens"][token_index_1based - 1]
    return int(tok["characterOffsetBegin"]), int(tok["characterOffsetEnd"])


def _sentence_span(sentence: Mapping[str, Any]) -> tuple[int, int]:
    tokens = sentence["tokens"]
    return int(tokens[0]["characterOffsetBegin"]), int(tokens[-1]["characterOffsetEnd"])


def _deps(sentence: Mapping[str, Any]) -> list[dict[str, Any]]:
    deps = sentence.get("basicDependencies") or []
    return [d for d in deps if isinstance(d, Mapping)]


def _find_roots(sentence: Mapping[str, Any]) -> list[int]:
    roots = []
    for d in _deps(sentence):
        if d.get("dep") == "ROOT":
            roots.append(int(d["dependent"]))
    return roots


def _is_modal_token(sentence: Mapping[str, Any], idx: int) -> bool:
    tok = sentence["tokens"][idx - 1]
    w = (tok.get("word") or tok.get("originalText") or "").casefold()
    return w in {"shall", "must", "may", "can", "need", "should"}


def _nucleus_kinds_for(sentence: Mapping[str, Any], text: str) -> list[dict[str, Any]]:
    """Return a list of clause-nucleus candidates with kind, token, and span.

    A nucleus is created only for a top-level deontic / definition predicate
    whose governor is not inside a subordinate marker (if/when/unless/...).
    """
    tokens = sentence["tokens"]
    preds: list[dict[str, Any]] = []

    # definition predicates
    for m in _DEF_PHRASE.finditer(text):
        abs_start = _sentence_span(sentence)[0] + m.start()
        ti = None
        for t in tokens:
            if t["characterOffsetBegin"] <= abs_start < t["characterOffsetEnd"] or (
                abs_start <= t["characterOffsetBegin"] < _sentence_span(sentence)[0] + m.end()
            ):
                ti = int(t["index"])
                break
        if ti is not None:
            preds.append({"kind": "definition", "token": ti, "char": (_sentence_span(sentence)[0] + m.start(), _sentence_span(sentence)[0] + m.end())})

    # modal auxiliaries governing a main verb
    for d in _deps(sentence):
        dep = d.get("dep")
        if dep in {"aux", "aux:pass"}:
            gov = int(d["governor"])
            dep_i = int(d["dependent"])
            if _is_modal_token(sentence, dep_i):
                kind = "permission"
                w = tokens[dep_i - 1].get("word", "").casefold()
                has_not = any(
                    (tokens[int(c["dependent"]) - 1].get("word", "").casefold() == "not")
                    for c in _deps(sentence) if int(c.get("governor", -1)) == gov
                    if c.get("dep") in {"advmod", "neg"}
                ) or any(
                    (tokens[int(c["dependent"]) - 1].get("word", "").casefold() == "not")
                    for c in _deps(sentence) if int(c.get("governor", -1)) == dep_i
                    if c.get("dep") in {"advmod", "neg"}
                )
                if w in {"shall", "must"} and has_not:
                    kind = "prohibition"
                elif w in {"may"} and has_not:
                    kind = "prohibition"
                elif w in {"shall", "must", "need", "should"}:
                    kind = "obligation"
                elif w in {"may", "can"}:
                    kind = "permission"
                preds.append({"kind": kind, "token": gov, "modal": dep_i, "char": _token_abs_span(sentence, gov)})

    # ROOT verbs (lexical)
    for r in _find_roots(sentence):
        if not any(p["token"] == r for p in preds):
            w = tokens[r - 1].get("lemma", tokens[r - 1].get("word", "")).casefold()
            if w in {"mean", "means", "include", "amount"}:
                preds.append({"kind": "definition", "token": r, "char": _token_abs_span(sentence, r)})
    # dedupe by token
    by_tok: dict[int, dict[str, Any]] = {}
    for p in preds:
        by_tok[p["token"]] = p
    return [by_tok[k] for k in sorted(by_tok)]


def _subordinate_predicate(sentence: Mapping[str, Any], token_idx: int) -> bool:
    """True if token is governed under mark/advcl/relcl of another clause."""
    gov_map = {int(d["dependent"]): d for d in _deps(sentence) if d.get("dep") != "ROOT"}
    cur = token_idx
    seen = set()
    while cur in gov_map and cur not in seen:
        seen.add(cur)
        rel = gov_map[cur]
        dep = rel.get("dep")
        if dep in {"advcl", "relcl", "acl", "acl:relcl"}:
            return True
        if dep == "mark":
            return True
        cur = int(rel["governor"])
    return False


def _is_in_clause(sentence: Mapping[str, Any], idx: int, clause_start: int, clause_end: int) -> bool:
    a, b = _token_abs_span(sentence, idx)
    return not (b <= clause_start or a >= clause_end)


def _subtree_char_span(sentence: Mapping[str, Any], head_idx: int) -> tuple[int, int]:
    """Approx span of head + descendants via dependencies.

    Excludes `case` (preposition markers) so that by-phrase actors do not
    pull in the `by` token. Also excludes `punct`.
    """
    tokens = sentence["tokens"]
    kids = {head_idx}
    changed = True
    deps = _deps(sentence)
    while changed:
        changed = False
        for d in deps:
            g = int(d.get("governor", -1))
            dep = int(d.get("dependent", -1))
            rel = d.get("dep")
            if g in kids and dep not in kids and rel not in {"ROOT", "case", "punct"}:
                kids.add(dep)
                changed = True
    begins = [tokens[i - 1]["characterOffsetBegin"] for i in kids]
    ends = [tokens[i - 1]["characterOffsetEnd"] for i in kids]
    return min(begins), max(ends)


def _children(sentence: Mapping[str, Any], gov: int) -> list[dict[str, Any]]:
    return [d for d in _deps(sentence) if int(d.get("governor", -1)) == gov]


def plan_clause_units_v6(
    annotation: Mapping[str, Any],
    source_text: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """v6 segmentation: clause nucleus only.

    - merge CoreNLP sentence groups (stable)
    - identify nucleus predicates for the group
    - drop nuclei that live inside a subordinate advcl/relcl/mark
    - split only when the sentence has 2+ deontic nuclei separated by ;
      or by ", and" with a new deontic modal, OR a single shared-modal with
      a clearly different subject
    """
    from bpc_hybrid.estg150_b0_development_v2 import (
        merge_corenlp_sentence_groups,
    )
    stats = {
        "list_merges": 0,
        "multi_predicate_splits": 0,
        "subordinate_suppressed": 0,
        "sentence_groups": 0,
        "coord_splits": 0,
        "nucleus_predicates": 0,
    }
    sentences = list(annotation["sentences"])
    if not sentences:
        return [], stats
    groups = merge_corenlp_sentence_groups(annotation, source_text)
    stats["sentence_groups"] = len(groups)
    stats["list_merges"] = sum(max(0, len(g["sentence_indexes"]) - 1) for g in groups)

    units: list[dict[str, Any]] = []
    for group in groups:
        indexes = list(group["sentence_indexes"])
        start = sentences[indexes[0]]["tokens"][0]["characterOffsetBegin"]
        end = sentences[indexes[-1]]["tokens"][-1]["characterOffsetEnd"]
        text = source_text[start:end]

        # collect nucleus candidates for the whole group
        nuclei: list[dict[str, Any]] = []
        for sidx in indexes:
            sent = sentences[sidx]
            s0 = _sentence_span(sent)[0]
            sent_text = source_text[s0:_sentence_span(sent)[1]]
            for n in _nucleus_kinds_for(sent, sent_text):
                # reject nuclei inside a subordinate (advcl/relcl/mark)
                if _subordinate_predicate(sent, n["token"]):
                    stats["subordinate_suppressed"] += 1
                    continue
                # mark in absolute source_text span
                char0, char1 = n["char"]
                n_abs = (char0, char1)
                n["abs_char"] = n_abs
                n["sentence_index"] = sidx
                nuclei.append(n)
        stats["nucleus_predicates"] += len(nuclei)

        if not nuclei:
            units.append({
                "sentence_indexes": indexes,
                "primary_index": indexes[0],
                "clause_char_span": (start, end),
                "reason": "sentence_group",
                "nucleus_kinds": [],
            })
            continue

        # do not split a definition-only group that has more than one definition
        # nucleus; treat as one clause (the standard EStG §-style structure).
        deontic = [n for n in nuclei if n["kind"] != "definition"]
        if len(deontic) >= 2:
            # sort nuclei by their char position
            deontic.sort(key=lambda n: n["abs_char"][0])
            # only split when nuclei are clearly separated
            cuts: list[int] = []
            for n1, n2 in zip(deontic, deontic[1:]):
                a1, b1 = n1["abs_char"]
                a2, b2 = n2["abs_char"]
                # require at least 1 char gap
                if a2 - b1 > 0:
                    # cut at the boundary just before n2's modal/text
                    cuts.append((a1 + b2) // 2 if a2 - b1 < 30 else a2)
            if cuts and cuts[0] > start and cuts[0] < end:
                bounds = [start] + cuts + [end]
                for j in range(len(bounds) - 1):
                    a, b = bounds[j], bounds[j + 1]
                    while a < b and source_text[a].isspace():
                        a += 1
                    while b > a and source_text[b - 1].isspace():
                        b -= 1
                    if b > a:
                        units.append({
                            "sentence_indexes": indexes,
                            "primary_index": indexes[0],
                            "clause_char_span": (a, b),
                            "reason": "multi_modal_split_v6",
                            "nucleus_kinds": [n["kind"] for n in deontic],
                        })
                        stats["multi_predicate_splits"] += 1
                continue

        # default: one unit per sentence group
        units.append({
            "sentence_indexes": indexes,
            "primary_index": indexes[0],
            "clause_char_span": (start, end),
            "reason": "sentence_group",
            "nucleus_kinds": [n["kind"] for n in nuclei],
        })
    return units, stats


def plan_clause_units_from_gold_v6(
    gold_record: Mapping[str, Any],
    source_text: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Oracle clause plan: use Gold clause spans only (read-only diagnostic)."""
    stats = {
        "list_merges": 0,
        "multi_predicate_splits": 0,
        "subordinate_suppressed": 0,
        "sentence_groups": 0,
        "coord_splits": 0,
        "nucleus_predicates": 0,
        "gold_oracle": 1,
    }
    units: list[dict[str, Any]] = []
    for clause in gold_record.get("clauses", []):
        span = clause.get("clause_span", {})
        s = int(span.get("start", -1))
        e = int(span.get("end", -1))
        if s < 0 or e <= s:
            continue
        # ensure the span is within source_text
        s = max(0, s)
        e = min(len(source_text), e)
        if e <= s:
            continue
        units.append({
            "sentence_indexes": [],
            "primary_index": 0,
            "clause_char_span": (s, e),
            "reason": "gold_clause_oracle",
            "nucleus_kinds": [clause.get("modality", {}).get("label", "obligation")],
        })
    return units, stats


def align_german_to_english_units_v6(
    german_text: str,
    english_units: Sequence[str],
) -> list[str]:
    """Anchor-aware DE-EN packing, inherited from v5."""
    from bpc_hybrid.estg150_b0_development_v3 import align_german_to_english_units_v4
    return align_german_to_english_units_v4(german_text, english_units)


# --- Phrase resolvers ----------------------------------------------------
def resolve_actor_action_v6(
    sentence: Mapping[str, Any],
    source_text: str,
    clause_start: int,
    clause_end: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[int, int]]]:
    """v6 actor/action: stricter actor filter, smaller sufficient action span.

    - actor must have a head lemma in _ACTOR_LEX (or contain such a word)
      OR be a non-pronoun, non-abstract NP whose last token is an actor noun
    - action span = head + necessary object/complement, bounded to 8 tokens
    - excludes tokens that are condition/exception markers
    """
    tokens = sentence["tokens"]

    def in_clause(idx: int) -> bool:
        a, b = _token_abs_span(sentence, idx)
        return not (b <= clause_start or a >= clause_end)

    action_heads: list[int] = []
    for d in _deps(sentence):
        if d.get("dep") in {"aux", "aux:pass"} and _is_modal_token(sentence, int(d["dependent"])):
            gov = int(d["governor"])
            if in_clause(gov) and not _subordinate_predicate(sentence, gov):
                action_heads.append(gov)
    for r in _find_roots(sentence):
        if in_clause(r) and r not in action_heads:
            pos = tokens[r - 1].get("pos", "")
            if pos.startswith("VB"):
                action_heads.append(r)
    action_heads = sorted(set(action_heads))

    actors: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    pairs: list[tuple[int, int]] = []

    for head in action_heads:
        include: set[int] = {head}
        for d in _children(sentence, head):
            rel = d.get("dep")
            dep = int(d["dependent"])
            if rel in {"dobj", "obj", "iobj", "xcomp", "ccomp", "attr", "acomp", "compound:prt", "prt"}:
                st0, st1 = _subtree_char_span(sentence, dep)
                for t in tokens:
                    if (st0 <= t["characterOffsetBegin"] < st1) or (st0 < t["characterOffsetEnd"] <= st1):
                        include.add(int(t["index"]))
        # cap to head + 8 following tokens that are still in the clause
        head_pos = tokens[head - 1]["characterOffsetBegin"]
        capped = [head]
        for t in tokens:
            if int(t["index"]) == head:
                continue
            if not in_clause(int(t["index"])):
                continue
            if t["characterOffsetBegin"] < head_pos:
                continue
            if len(capped) >= 9:
                break
            capped.append(int(t["index"]))
        idxs = sorted(set(capped) | {head})
        idxs = [i for i in idxs if in_clause(i)]
        if not idxs:
            continue
        start = tokens[idxs[0] - 1]["characterOffsetBegin"]
        end = tokens[idxs[-1] - 1]["characterOffsetEnd"]
        start = max(start, clause_start)
        end = min(end, clause_end)
        if end <= start:
            continue
        text = source_text[start:end]
        text2 = re.sub(r"^(?:shall|must|may|can|not|should|need)\s+", "", text, flags=re.I)
        if text2 != text:
            pos = source_text.find(text2, start, end)
            if pos >= 0:
                start, end = pos, pos + len(text2)
                text = text2
        actions.append({
            "text": text,
            "start": start,
            "end": end,
            "normalized": " ".join(text.casefold().split()),
            "head": head,
        })

        # actor by dep: by-agent takes priority for passive (over nsubj:pass)
        actor_idx: int | None = None
        # first check for by-agent (case=by -> PP-attached NP, or nmod:agent)
        for d in _deps(sentence):
            if d.get("dep") == "case":
                dep = int(d["dependent"])
                gov = int(d["governor"])
                w = tokens[dep - 1].get("word", "").casefold()
                if w == "by" and in_clause(gov) and int(d.get("governor", -1)) > 0:
                    # the gov is the head of a by-phrase whose parent is the action head
                    # but the case relation doesn't tell us that directly;
                    # we look for a nmod/nmod:agent of `head` with gov=gov
                    pass
        for d in _deps(sentence):
            if int(d.get("governor", -1)) == head and d.get("dep") in {"obl:agent", "nmod:agent"}:
                actor_idx = int(d["dependent"])
                break
        # if no by-agent, look for nsubj/nsubj:pass
        if actor_idx is None:
            for d in _deps(sentence):
                if int(d.get("governor", -1)) == head and d.get("dep") in {"nsubj", "nsubj:pass"}:
                    actor_idx = int(d["dependent"])
                    break
        # fallback: by-phrase via case=by where the case's head is the action head
        if actor_idx is None:
            for d in _deps(sentence):
                if d.get("dep") == "case":
                    dep = int(d["dependent"])
                    gov = int(d["governor"])
                    w = tokens[dep - 1].get("word", "").casefold()
                    if w == "by" and gov == head and in_clause(gov):
                        # the head's governor is the head noun, and the head noun
                        # is the head of an nmod:agent relation
                        for d2 in _deps(sentence):
                            if int(d2.get("governor", -1)) == head and d2.get("dep") in {"nmod", "nmod:agent", "obl", "obl:agent"}:
                                actor_idx = int(d2["dependent"])
                                break
                        break
        if actor_idx is None or not in_clause(actor_idx):
            continue
        a0, a1 = _subtree_char_span(sentence, actor_idx)
        a0, a1 = max(a0, clause_start), min(a1, clause_end)
        if a1 <= a0:
            continue
        atext = source_text[a0:a1]
        words = re.findall(r"[A-Za-z\u00c0-\u024f]+", atext.casefold())
        if not words:
            continue
        # v6 stricter actor filter: must have an actor head or a recognized
        # actor word; pure pronoun / pure abstract non-entity NPs are dropped
        is_pronoun = all(w in _NON_ACTOR for w in words[:2])
        has_actor = any(w in _ACTOR_LEX for w in words)
        if is_pronoun and not has_actor:
            continue
        if not has_actor and len(words) > 6:
            # abstract / long NP without an actor head word
            continue
        # trim very long NPs
        if len(words) > 12:
            parts = atext.split()
            atext = " ".join(parts[-8:])
            pos = source_text.rfind(atext, a0, a1)
            if pos >= 0:
                a0, a1 = pos, pos + len(atext)
        actor_span = {
            "text": source_text[a0:a1],
            "start": a0,
            "end": a1,
            "normalized": " ".join(source_text[a0:a1].casefold().split()),
            "head": actor_idx,
        }
        # dedupe actors, keep smaller sufficient
        ai = None
        for j, existing in enumerate(actors):
            if not (actor_span["end"] <= existing["start"] or actor_span["start"] >= existing["end"]):
                if (actor_span["end"] - actor_span["start"]) < (existing["end"] - existing["start"]):
                    actors[j] = actor_span
                ai = j
                break
        if ai is None:
            actors.append(actor_span)
            ai = len(actors) - 1
        pairs.append((ai, len(actions) - 1))
    return actors, actions, pairs


def _regex_spans_v6(text: str, base: int, pattern: re.Pattern[str], max_len: int = 120) -> list[dict[str, Any]]:
    out = []
    for m in pattern.finditer(text):
        start = m.start()
        end = m.end()
        j = end
        while j < len(text) and j - start < max_len and text[j] not in ".;\n":
            j += 1
        frag = text[start:j].strip()
        if not frag:
            continue
        abs_s = base + start
        abs_e = abs_s + len(frag)
        out.append({
            "text": frag,
            "start": abs_s,
            "end": abs_e,
            "normalized": " ".join(frag.casefold().split()),
        })
    return out


def resolve_scope_fields_v6(
    source_text: str,
    clause_start: int,
    clause_end: int,
    tregex_obs: Mapping[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]],
) -> dict[str, list[dict[str, Any]]]:
    """v6 scope: carve-out / applicability / performance-limit test."""
    clause = source_text[clause_start:clause_end]
    result: dict[str, list[dict[str, Any]]] = {
        "condition": [],
        "constraint": [],
        "exception": [],
    }
    # from tregex (multi-match)
    for field in result:
        for sent, obs in tregex_obs.get(field, []):
            try:
                span = _token_span(source_text, sent, obs)
            except Exception:
                continue
            if span["end"] <= clause_start or span["start"] >= clause_end:
                continue
            s = max(span["start"], clause_start)
            e = min(span["end"], clause_end)
            if e <= s:
                continue
            result[field].append({
                "text": source_text[s:e],
                "start": s,
                "end": e,
                "normalized": " ".join(source_text[s:e].casefold().split()),
            })
    # regex boost
    for m in _regex_spans_v6(clause, clause_start, _EXC_MARKERS, 100):
        result["exception"].append(m)
    for m in _regex_spans_v6(clause, clause_start, _COND_MARKERS, 80):
        result["condition"].append(m)
    for m in _regex_spans_v6(clause, clause_start, _CONS_MARKERS, 60):
        # carve-out test: if the constraint marker sits inside a clause that is
        # itself an exception span, drop it (it is part of the carve-out, not
        # a performance limit). Reuse a simple "span contains exception span"
        # membership test against the exception list.
        if any(ex["start"] <= m["start"] < ex["end"] or ex["start"] < m["end"] <= ex["end"] for ex in result["exception"]):
            continue
        result["constraint"].append(m)

    def dedupe_smallest(spans: list[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
        spans = sorted(spans, key=lambda s: (s["start"], s["end"] - s["start"], s["text"]))
        kept: list[dict[str, Any]] = []
        for sp in spans:
            if sp["end"] - sp["start"] > 160:
                continue
            overlap = [k for k in kept if not (sp["end"] <= k["start"] or sp["start"] >= k["end"])]
            if not overlap:
                kept.append(sp)
                continue
            rival = min(overlap + [sp], key=lambda s: (s["end"] - s["start"], s["start"]))
            for o in overlap:
                kept.remove(o)
            kept.append(rival)
        kept.sort(key=lambda s: (s["start"], s["end"]))
        return kept[:cap]

    result["condition"] = dedupe_smallest(result["condition"], cap=4)
    result["constraint"] = dedupe_smallest(result["constraint"], cap=4)
    result["exception"] = dedupe_smallest(result["exception"], cap=3)
    return result


# --- Canonical record builder --------------------------------------------
def build_canonical_record_v6(
    *,
    sample_id: str,
    source_id: str,
    source_text: str,
    annotation: Mapping[str, Any],
    phrase_cases: Sequence[Mapping[str, Any]],
    clause_units: Sequence[Mapping[str, Any]],
    predictions: Sequence[tuple[ModalityPrediction, str, dict[str, Any]]],
) -> dict[str, Any]:
    try:
        validate_annotation(annotation, source_text)
    except CoreNLPContractError as exc:
        raise Estg150B0DevelopmentError(str(exc)) from exc
    sentences = annotation["sentences"]
    if len(predictions) != len(clause_units):
        raise Estg150B0DevelopmentError("one modality prediction required per clause unit")
    cases_by_sentence: dict[int, Mapping[str, Any]] = {}
    for case in phrase_cases:
        index = case.get("sentence_index")
        if not isinstance(index, int) or isinstance(index, bool) or index in cases_by_sentence:
            raise Estg150B0DevelopmentError("phrase case indexes must be unique integers")
        cases_by_sentence[index] = case

    clauses: list[dict[str, Any]] = []
    for unit_index, (unit, (prediction, route, _diag)) in enumerate(zip(clause_units, predictions, strict=True)):
        sentence_indexes = unit["sentence_indexes"] or list(range(len(sentences)))
        if "clause_char_span" in unit:
            clause_start, clause_end = unit["clause_char_span"]
        else:
            clause_start = sentences[sentence_indexes[0]]["tokens"][0]["characterOffsetBegin"]
            clause_end = sentences[sentence_indexes[-1]]["tokens"][-1]["characterOffsetEnd"]
        clause_span = _plain_span(source_text, clause_start, clause_end)
        clause_id = f"{sample_id}.c{unit_index + 1}"

        tregex_obs: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {
            f: [] for f in ("modality", "actor", "action", "condition", "constraint", "exception")
        }
        for sidx in sentence_indexes:
            fields = cases_by_sentence.get(sidx, {}).get("fields", {})
            sent = sentences[sidx]
            for field in tregex_obs:
                values = fields.get(field) or []
                if isinstance(values, Mapping):
                    values = [values]
                for obs in values:
                    if isinstance(obs, Mapping):
                        tregex_obs[field].append((sent, obs))

        modality_evidence: list[dict[str, Any]] = []
        for sent, obs in tregex_obs["modality"]:
            try:
                sp = _token_span(source_text, sent, obs)
                if sp["end"] > clause_start and sp["start"] < clause_end:
                    # clip to clause bounds
                    clipped = {
                        "text": source_text[max(sp["start"], clause_start):min(sp["end"], clause_end)],
                        "start": max(sp["start"], clause_start),
                        "end": min(sp["end"], clause_end),
                    }
                    if clipped["end"] > clipped["start"]:
                        modality_evidence.append(clipped)
            except Exception:
                pass
        if not modality_evidence:
            modality_evidence = [dict(clause_span)]

        actors: list[dict[str, Any]] = []
        actions: list[dict[str, Any]] = []
        owner_pairs: list[tuple[int, int]] = []
        for sidx in sentence_indexes:
            if sidx >= len(sentences):
                continue
            a, act, pairs = resolve_actor_action_v6(
                sentences[sidx], source_text, clause_start, clause_end
            )
            base_a, base_act = len(actors), len(actions)
            actors.extend(a)
            actions.extend(act)
            for ai, aci in pairs:
                owner_pairs.append((base_a + ai, base_act + aci))
        if not actions:
            for sent, obs in tregex_obs["action"]:
                try:
                    sp = _token_span(source_text, sent, obs)
                except Exception:
                    continue
                s = max(sp["start"], clause_start)
                e = min(sp["end"], clause_end)
                if e <= s:
                    continue
                text = source_text[s:e]
                if len(text.split()) > 12:
                    parts = re.findall(r"\S+|\s+", text)
                    kept: list[str] = []
                    words = 0
                    for part in parts:
                        kept.append(part)
                        if not part.isspace():
                            words += 1
                        if words >= 10:
                            break
                    frag = "".join(kept).rstrip()
                    e = s + len(frag)
                    text = source_text[s:e]
                actions.append({
                    "text": text,
                    "start": s,
                    "end": e,
                    "normalized": " ".join(text.casefold().split()),
                })

        # actor post-filter: head word must be in _ACTOR_LEX, or contain one,
        # and not be a pure abstract non-entity
        filtered_actors: list[dict[str, Any]] = []
        for a in actors:
            words = re.findall(r"[A-Za-z\u00c0-\u024f]+", a["text"].casefold())
            if not words:
                continue
            if all(w in _NON_ACTOR for w in words) and not any(w in _ACTOR_LEX for w in words):
                continue
            if len(words) > 12:
                continue
            filtered_actors.append(a)
        actors = filtered_actors

        scope = resolve_scope_fields_v6(source_text, clause_start, clause_end, tregex_obs)

        def finalize(spans: list[dict[str, Any]], singular: str) -> list[dict[str, Any]]:
            out = []
            for rank, sp in enumerate(spans, start=1):
                out.append({
                    "id": f"{clause_id}.{singular}.{rank}",
                    "text": sp["text"],
                    "start": sp["start"],
                    "end": sp["end"],
                    "normalized": sp.get("normalized") or " ".join(sp["text"].casefold().split()),
                })
            return out

        mapped = {
            "actors": finalize(actors, "actor"),
            "actions": finalize(actions, "action"),
            "conditions": finalize(scope["condition"], "condition"),
            "constraints": finalize(scope["constraint"], "constraint"),
            "exceptions": finalize(scope["exception"], "exception"),
        }

        # actor_action_map: predicate ownership only; no first-actor fanout;
        # never invent a zip if no ownership pair is available.
        actor_action_map: list[dict[str, Any]] = []
        if mapped["actors"] and mapped["actions"]:
            for ai, aci in owner_pairs:
                if ai < len(mapped["actors"]) and aci < len(mapped["actions"]):
                    actor_action_map.append({
                        "actor_id": mapped["actors"][ai]["id"],
                        "action_id": mapped["actions"][aci]["id"],
                    })
            # fallback: if exactly one actor and multiple actions, link
            # only when dep ownership is ambiguous but the actor is the
            # only nsubj/nsubj:pass in the clause
            if not actor_action_map and len(mapped["actors"]) == 1:
                for action in mapped["actions"]:
                    actor_action_map.append({
                        "actor_id": mapped["actors"][0]["id"],
                        "action_id": action["id"],
                    })

        clauses.append({
            "clause_id": clause_id,
            "clause_span": clause_span,
            "modality": {
                "label": prediction.label,
                "evidence": modality_evidence[:1],
                "route": route,
            },
            "nucleus_kinds": unit.get("nucleus_kinds", []),
            "segmentation_reason": unit.get("reason", "sentence_group"),
            **mapped,
            "actor_action_map": actor_action_map,
            "order_relations": [],
        })

    record = {
        "schema_version": SCHEMA_VERSION,
        "sample_id": sample_id,
        "source_id": source_id,
        "source_text": source_text,
        "clauses": clauses,
        "method": {"name": METHOD_ID, "schema_source": SCHEMA_SOURCE},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
    }
    report = validate_canonical(record)
    if not (report.schema_valid and report.cross_field_valid):
        raise Estg150B0DevelopmentError(
            "composed canonical record is invalid: " + "; ".join(report.errors)
        )
    return record


# --- CoreNLP batch wrapper (uses v4 patterns + v2 lexicon; safe bridge) ---
def run_corenlp_batch_v6(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    root = Path(project_root).resolve()
    runtime_home = Path(runtime_home).resolve()
    runtime_identity = _verify_runtime_identity(root, runtime_home)
    from bpc_hybrid.sun_style.corenlp_runtime import resolve_corenlp_runtime
    probe = resolve_corenlp_runtime(root, home=runtime_home)
    if not probe.ready or not probe.java_executable:
        raise Estg150B0DevelopmentError(f"CoreNLP runtime unavailable: {probe.reasons}")
    import shutil as _shutil
    javac = _shutil.which("javac")
    if not javac:
        raise Estg150B0DevelopmentError("javac is required")

    input_dir = work_dir / "corenlp-input"
    output_dir = work_dir / "corenlp-output"
    classes_dir = work_dir / "bridge-classes"
    input_dir.mkdir(parents=True)
    output_dir.mkdir()
    classes_dir.mkdir()
    input_paths: list[Path] = []
    source_by_id: dict[str, str] = {}
    for record in source_records:
        sample_id = record["sample_id"]
        source_text = record["approved_text_en"]
        path = input_dir / f"{sample_id}.txt"
        path.write_text(source_text, encoding="utf-8", newline="\n")
        input_paths.append(path)
        source_by_id[sample_id] = source_text
    file_list = work_dir / "corenlp-filelist.txt"
    file_list.write_text(
        "\n".join(str(path.resolve()) for path in input_paths) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    runtime_contract = load_object(root / "configs/sun_corenlp_runtime.json")["runtime"]
    classpath = os.pathsep.join(probe.classpath_entries)
    corenlp_command = [
        probe.java_executable,
        f"-Xmx{runtime_contract['heap_megabytes']}m",
        "-cp",
        classpath,
        "edu.stanford.nlp.pipeline.StanfordCoreNLP",
        "-annotators",
        ",".join(runtime_contract["annotators"]),
        "-outputFormat",
        "json",
        "-filelist",
        str(file_list.resolve()),
        "-outputDirectory",
        str(output_dir.resolve()),
        "-replaceExtension",
    ]
    started = time.perf_counter()
    _run(corenlp_command, cwd=root, timeout=max(1800, 12 * len(source_records)))
    corenlp_seconds = time.perf_counter() - started

    annotations: dict[str, dict[str, Any]] = {}
    sentence_refs: list[tuple[str, int]] = []
    tree_lines: list[str] = []
    for record in source_records:
        sample_id = record["sample_id"]
        candidates = list(output_dir.rglob(f"{sample_id}.json"))
        if len(candidates) != 1:
            raise Estg150B0DevelopmentError(
                f"expected one CoreNLP JSON for {sample_id}, found {len(candidates)}"
            )
        annotation = load_object(candidates[0])
        try:
            validate_annotation(annotation, source_by_id[sample_id])
        except CoreNLPContractError as exc:
            raise Estg150B0DevelopmentError(f"{sample_id}: {exc}") from exc
        annotations[sample_id] = annotation
        for local_index, sentence in enumerate(annotation["sentences"]):
            sentence_refs.append((sample_id, local_index))
            tree_lines.append(" ".join(sentence["parse"].split()))

    registry = load_object(root / PATTERNS_REL)
    plan_path = work_dir / "rule-plan.tsv"
    pattern_count = _write_rule_plan(registry, plan_path)
    # safe bridge: the v6 implementation uses the existing safe batch
    # bridge (SunPhraseRuleBatchBridgeMulti) directly. The SafeV2 file in
    # tools/corenlp/ is a provenance marker only (see its header) and is
    # not compiled, to avoid duplicate class definitions.
    bridge_path_multi = root / "tools/corenlp/SunPhraseRuleBatchBridgeMulti.java"
    if not bridge_path_multi.is_file():
        raise Estg150B0DevelopmentError(
            f"required bridge source missing: {bridge_path_multi}"
        )
    bridge_class_to_use = BRIDGE_CLASS
    bridge_path = bridge_path_multi
    # record the safe V2 file as a provenance marker if present
    safe_marker = root / BRIDGE_REL
    safe_marker_present = safe_marker.is_file()
    compile_command = [
        javac, "--release", "8", "-encoding", "UTF-8",
        "-cp", classpath, "-d", str(classes_dir), str(bridge_path),
    ]
    _run(compile_command, cwd=root, timeout=180)
    tree_path = work_dir / "trees.txt"
    tree_path.write_text("\n".join(tree_lines) + "\n", encoding="utf-8", newline="\n")
    bridge_classpath = os.pathsep.join((str(classes_dir), classpath))
    bridge_started = time.perf_counter()
    bridge = _run(
        [
            probe.java_executable, "-cp", bridge_classpath, bridge_class_to_use,
            str(plan_path), str(tree_path),
        ],
        cwd=root,
        timeout=600,
    )
    bridge_seconds = time.perf_counter() - bridge_started
    global_cases, bridge_summary = parse_bridge_output_multi(bridge.stdout)
    if bridge_summary["pattern_count"] != pattern_count:
        raise Estg150B0DevelopmentError("bridge pattern count mismatch")
    if bridge_summary["tree_count"] != len(sentence_refs) or len(global_cases) != len(sentence_refs):
        raise Estg150B0DevelopmentError("bridge sentence coverage mismatch")
    cases_by_id: dict[str, list[dict[str, Any]]] = {
        record["sample_id"]: [] for record in source_records
    }
    for global_case, (sample_id, local_index) in zip(global_cases, sentence_refs, strict=True):
        cases_by_id[sample_id].append(
            {"sentence_index": local_index, "fields": global_case["fields"]}
        )
    return annotations, cases_by_id, {
        "runtime_identity": runtime_identity,
        "corenlp_seconds": corenlp_seconds,
        "bridge_seconds": bridge_seconds,
        "sentence_count": len(sentence_refs),
        "pattern_count": pattern_count,
        "match_count": bridge_summary["match_count"],
        "surgery_count": bridge_summary["surgery_count"],
        "terminal_tree_removal_count": bridge_summary["terminal_tree_removal_count"],
        "bridge_class": bridge_class_to_use,
        "bridge_source": str(bridge_path.relative_to(root)),
        "safe_v2_marker_present": safe_marker_present,
        "patterns_path": PATTERNS_REL,
    }


# --- Main batch entry ----------------------------------------------------
def run_b0_batch_v6(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
    device: str = "cpu",
    mode: str = MODE_HYBRID,
    gold_records: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if mode not in ALLOWED_MODES:
        raise Estg150B0DevelopmentError(f"unknown mode: {mode}")
    root = Path(project_root).resolve()
    s26_config = load_s26_config(root / "configs/models/sun_b0_s26.json")
    annotations, cases_by_id, runtime = run_corenlp_batch_v6(
        root, source_records, runtime_home=runtime_home, work_dir=work_dir
    )
    classifier_started = time.perf_counter()
    try:
        classifier = LockedBertTextCNNInference.load(root, s26_config, device=device)
    except SunB0CompositionError as exc:
        raise Estg150B0DevelopmentError(str(exc)) from exc

    planned: list[tuple[Mapping[str, Any], list[dict[str, Any]], list[str], list[str], dict[str, int]]] = []
    all_de_texts: list[str] = []
    seg_stats_total: dict[str, int] = {
        "list_merges": 0,
        "multi_predicate_splits": 0,
        "subordinate_suppressed": 0,
        "sentence_groups": 0,
        "coord_splits": 0,
        "nucleus_predicates": 0,
        "gold_oracle": 0,
    }
    gold_by_id: dict[str, Mapping[str, Any]] = {
        r["sample_id"]: r for r in (gold_records or [])
    }
    for record in source_records:
        sample_id = record["sample_id"]
        annotation = annotations[sample_id]
        source_text = record["approved_text_en"]
        if mode == MODE_GOLD_CLAUSE_SEG_ORACLE:
            gold_record = gold_by_id.get(sample_id)
            if gold_record is None:
                raise Estg150B0DevelopmentError(
                    f"gold_clause_seg_oracle requires gold record for {sample_id}"
                )
            clause_units, seg_stats = plan_clause_units_from_gold_v6(gold_record, source_text)
        else:
            clause_units, seg_stats = plan_clause_units_v6(annotation, source_text)
        for k, v in seg_stats.items():
            seg_stats_total[k] = seg_stats_total.get(k, 0) + v
        en_texts = []
        for unit in clause_units:
            s, e = unit["clause_char_span"]
            en_texts.append(source_text[s:e])
        de_units = align_german_to_english_units_v6(record["raw_text_de"], en_texts)
        planned.append((record, clause_units, en_texts, de_units, seg_stats))
        all_de_texts.extend(de_units)

    de_predictions = _predict_in_batches(classifier, all_de_texts)
    classifier_seconds = time.perf_counter() - classifier_started

    compose_started = time.perf_counter()
    canonical_records: list[dict[str, Any]] = []
    label_counts: dict[str, int] = {}
    confidence_sum = 0.0
    pred_cursor = 0
    modality_route_counts: dict[str, int] = {}
    route_to_diagnostic: dict[str, int] = {}
    for record, clause_units, en_texts, de_units, _seg in planned:
        sample_id = record["sample_id"]
        unit_predictions: list[tuple[ModalityPrediction, str, dict[str, Any]]] = []
        de_n = len(split_german_units(record["raw_text_de"])) or 1
        en_n = len(en_texts)
        de_aligned = de_n == en_n
        for en_text, de_text in zip(en_texts, de_units, strict=True):
            base = de_predictions[pred_cursor]
            pred_cursor += 1
            final, route, diag = resolve_modality_v6(
                english_clause=en_text,
                classifier=base,
                de_aligned=de_aligned,
                mode=mode,
            )
            modality_route_counts[route] = modality_route_counts.get(route, 0) + 1
            route_to_diagnostic[diag.get("english_marker_label") or "no_marker"] = (
                route_to_diagnostic.get(diag.get("english_marker_label") or "no_marker", 0) + 1
            )
            unit_predictions.append((final, route, diag))
            label_counts[final.label] = label_counts.get(final.label, 0) + 1
            confidence_sum += final.confidence
        canonical = build_canonical_record_v6(
            sample_id=sample_id,
            source_id=f"estg_legacy_{record['legacy_record_id']}",
            source_text=record["approved_text_en"],
            annotation=annotations[sample_id],
            phrase_cases=cases_by_id[sample_id],
            clause_units=clause_units,
            predictions=unit_predictions,
        )
        canonical_records.append(canonical)
    if pred_cursor != len(de_predictions):
        raise Estg150B0DevelopmentError("classifier prediction cursor mismatch")
    compose_seconds = time.perf_counter() - compose_started
    total_seconds = (
        runtime["corenlp_seconds"]
        + runtime["bridge_seconds"]
        + classifier_seconds
        + compose_seconds
    )
    per_record_latency_ms = 1000.0 * total_seconds / max(len(canonical_records), 1)
    attempts = [
        {
            "sample_id": record["sample_id"],
            "request_status": "ok",
            "record": record,
            "error_category": None,
            "runtime": {
                "llm_call_performed": False,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "latency_ms": per_record_latency_ms,
            },
        }
        for record in canonical_records
    ]
    runtime.update({
        "classifier_seconds": classifier_seconds,
        "compose_seconds": compose_seconds,
        "total_seconds": total_seconds,
        "device": device,
        "record_count": len(canonical_records),
        "predicted_clause_count": sum(len(r["clauses"]) for r in canonical_records),
        "classifier_label_counts_by_clause": dict(sorted(label_counts.items())),
        "classifier_mean_confidence": confidence_sum / max(sum(label_counts.values()), 1),
        "modality_route_counts": dict(sorted(modality_route_counts.items())),
        "english_marker_hit_counts": dict(sorted(route_to_diagnostic.items())),
        "segmentation_stats": seg_stats_total,
        "method_id": METHOD_ID,
        "method_variant": METHOD_VARIANT,
        "method_mode": mode,
        "paper_faithful_b0": False,
    })
    return attempts, runtime
