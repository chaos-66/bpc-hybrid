"""EStG-150 B0 enhanced v4 development (versioned).

Improvements vs b0_enhanced v3:
- definition-first English marker modality (shall mean != obligation)
- dependency-aware clause planning (deontic predicates, list merge, no subclause promotion)
- DE-EN alignment by punctuation/list/modal anchors when possible
- phrase: collect-all candidates + field resolvers (actor nsubj, action head, expanded cond/constraint)
- actor_action_map by ownership, not first-actor fanout
- multi-match without destructive Tsurgeon on context fields

Does not modify Gold/Layer E; no LLM/API; does not overwrite prior runs.
"""

from __future__ import annotations

import os
import re
import shutil
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
    EXTRACTION_ORDER,
    CoreNLPContractError,
    resolve_corenlp_runtime,
    validate_annotation,
)
from bpc_hybrid.sun_style.lexicon_v2_runtime import (
    load_lexicon_v2,
    match_modality_from_lexicon,
    match_field_markers,
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

METHOD_ID = "sun_rule_only"
METHOD_VARIANT = "b0_enhanced_v7"
S26_CONFIG_REL = "configs/models/sun_b0_s26_candidate_B_v1.json"
TSURGEON_ENABLED = False
LEXICON_V2_ENABLED = True
BRIDGE_CLASS = "SunPhraseRuleBatchBridgeMulti"
PATTERNS_REL = "resources/corenlp/sun_phrase_patterns_v3_enhanced.json"
BRIDGE_REL = "tools/corenlp/SunPhraseRuleBatchBridgeMulti.java"

# --- Modality: definition-first, then prohibition, obligation, permission ---
_DEF_PHRASE = re.compile(
    r"\b(?:shall\s+mean|means|is\s+defined\s+as|are\s+defined\s+as|refers\s+to|"
    r"denotes|is\s+understood\s+as|shall\s+be\s+construed\s+as|is\s+the\s+difference|"
    r"amounts?\s+to|also\s+include)\b",
    re.IGNORECASE,
)
_PROH = re.compile(
    r"\b(?:shall\s+not|must\s+not|may\s+not|is\s+not\s+permitted|is\s+prohibited|"
    r"is\s+not\s+allowed|no\s+\w+\s+shall|must\s+never)\b",
    re.IGNORECASE,
)
_OBL = re.compile(
    r"\b(?:shall|must|is\s+required\s+to|is\s+obliged\s+to|need\s+to|has\s+to)\b",
    re.IGNORECASE,
)
_PERM = re.compile(
    r"\b(?:may|is\s+permitted\s+to|is\s+allowed\s+to|is\s+authorized\s+to)\b",
    re.IGNORECASE,
)
_MODAL_ANCHOR = re.compile(
    r"\b(?:shall\s+not|must\s+not|may\s+not|shall\s+mean|shall|must|may|means|"
    r"is\s+defined\s+as|are\s+defined\s+as)\b",
    re.IGNORECASE,
)
_SUBORD_START = re.compile(
    r"^\s*(?:if|when|whenever|unless|where|provided|except|excluding|notwithstanding|"
    r"in\s+case|to\s+the\s+extent|insofar|subject\s+to)\b",
    re.IGNORECASE,
)
_LIST_HEAD = re.compile(r"^\s*(?:\d+[\.\)]|[a-z]\)|—|-)\s*", re.IGNORECASE)
_DE_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u00c4\u00d6\u00dc\"(0-9])")
_COORD_SPLIT = re.compile(
    r"(?:;|\band\s+(?=(?:the\s+)?(?:taxpayer|employee|employer|authority|fund|"
    r"person|minister|office|association|they|he|she)\b)|"
    r"\band\s+(?=that\s+(?:the|it|he|she)\b)|"
    r"\band\s+(?=(?:shall|must|may)\b))",
    re.IGNORECASE,
)

_ACTOR_LEX = frozenset({
    "taxpayer", "taxpayers", "employee", "employees", "employer", "employers",
    "authority", "authorities", "fund", "funds", "person", "persons", "company",
    "companies", "operator", "minister", "office", "association", "associations",
    "farmer", "farmers", "forester", "foresters", "trader", "traders", "successor",
    "successors", "insured", "provider", "controller", "processor", "recipient",
    "user", "users", "board", "court", "inspector", "driver", "officer",
})
_NON_ACTOR = frozenset({
    "it", "this", "these", "those", "they", "he", "she", "we", "i", "which", "that",
    "profit", "income", "difference", "amount", "expenditure", "allowance", "period",
    "year", "tax", "rate", "section", "paragraph", "item", "items", "meaning",
    "purpose", "case", "extent", "quantity", "asset", "assets", "contribution",
})
_CONSTRAINT_MARKERS = re.compile(
    r"\b(?:within|before|after|during|until|throughout|prior\s+to|at\s+least|"
    r"no\s+later\s+than|only|up\s+to|not\s+exceeding|for\s+the\s+purpose|"
    r"in\s+accordance\s+with|pursuant\s+to|under\s+section|within\s+the\s+meaning|"
    r"for\s+a\s+period|between|at\s+most|no\s+more\s+than|solely|exclusively|"
    r"generally|without\s+undue|in\s+such\s+(?:a\s+)?quantity|to\s+an\s+annual|"
    r"by\s+double-entry|as\s+defined\s+in)\b",
    re.IGNORECASE,
)
_EXCEPTION_MARKERS = re.compile(
    r"\b(?:unless|except|excluding|notwithstanding|other\s+than|save\s+where|"
    r"with\s+the\s+exception|apart\s+from|regardless\s+of|even\s+if|"
    r"shall\s+not\s+apply|does\s+not\s+apply)\b",
    re.IGNORECASE,
)
_CONDITION_MARKERS = re.compile(
    r"\b(?:if|when|whenever|where|provided\s+that|once|in\s+case|in\s+the\s+event|"
    r"to\s+the\s+extent|insofar\s+as|subject\s+to|as\s+long\s+as|so\s+long\s+as|"
    r"upon|after|before|on\s+condition)\b",
    re.IGNORECASE,
)


_LEXICON_V2 = None

def _get_lexicon_v2(project_root: Path | None = None):
    global _LEXICON_V2
    if not LEXICON_V2_ENABLED:
        return None
    if _LEXICON_V2 is None:
        root = project_root or Path(__file__).resolve().parents[3]
        # file is formal_experiment/src/bpc_hybrid/... -> parents[2]=formal_experiment? 
        # Path(__file__)=.../src/bpc_hybrid/estg150_b0_development_v5.py
        # parents[0]=bpc_hybrid, [1]=src, [2]=formal_experiment
        root = Path(__file__).resolve().parents[2]
        _LEXICON_V2 = load_lexicon_v2(root)
    return _LEXICON_V2


def english_marker_modality_v4(text: str) -> str | None:
    """Definition-first marker scoring; prefers activated lexicon v2 surfaces."""
    if not text or not text.strip():
        return None
    try:
        rt = _get_lexicon_v2()
        if rt is not None:
            lab, _surf = match_modality_from_lexicon(text, rt)
            if lab is not None:
                return lab
    except Exception:
        pass
    core = text
    if _DEF_PHRASE.search(core):
        if _PROH.search(core) and not re.search(
            r"\b(?:shall\s+mean|means|is\s+defined|refers\s+to|denotes)\b", core, re.I
        ):
            return "prohibition"
        return "definition"
    if _PROH.search(core):
        return "prohibition"
    if _OBL.search(core):
        return "obligation"
    if _PERM.search(core):
        return "permission"
    return None


def resolve_modality_v4(
    *,
    english_clause: str,
    classifier: ModalityPrediction,
    de_aligned: bool,
) -> tuple[ModalityPrediction, str]:
    en = english_marker_modality_v4(english_clause)
    # High-precision English cues preferred on approved EN surface
    if en == "definition":
        return ModalityPrediction("definition", max(classifier.confidence, 0.62)), "en_definition"
    if en == "prohibition":
        return ModalityPrediction("prohibition", max(classifier.confidence, 0.65)), "en_prohibition"
    if en == "obligation":
        if de_aligned and classifier.label == "obligation" and classifier.confidence >= 0.55:
            return classifier, "aligned_agree_obligation"
        return ModalityPrediction("obligation", max(classifier.confidence, 0.55)), "en_obligation"
    if en == "permission":
        if de_aligned and classifier.label == "permission" and classifier.confidence >= 0.55:
            return classifier, "aligned_agree_permission"
        return ModalityPrediction("permission", max(classifier.confidence, 0.55)), "en_permission"
    # No English marker: use classifier
    if de_aligned:
        return classifier, "aligned_classifier_fallback"
    return classifier, "misaligned_classifier_fallback"


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


def _children(sentence: Mapping[str, Any], gov: int) -> list[dict[str, Any]]:
    return [d for d in _deps(sentence) if int(d.get("governor", -1)) == gov]


def _is_modal_token(sentence: Mapping[str, Any], idx: int) -> bool:
    tok = sentence["tokens"][idx - 1]
    w = (tok.get("word") or tok.get("originalText") or "").casefold()
    return w in {"shall", "must", "may", "can", "need"}


def _clause_predicates(sentence: Mapping[str, Any], source_text: str) -> list[dict[str, Any]]:
    """Identify top-level deontic/definition predicates suitable as clause nuclei."""
    tokens = sentence["tokens"]
    preds: list[dict[str, Any]] = []
    s0, s1 = _sentence_span(sentence)
    text = source_text[s0:s1]

    # definition predicates
    for m in _DEF_PHRASE.finditer(text):
        abs_start = s0 + m.start()
        # map to token
        ti = None
        for t in tokens:
            if t["characterOffsetBegin"] <= abs_start < t["characterOffsetEnd"] or (
                abs_start <= t["characterOffsetBegin"] < s0 + m.end()
            ):
                ti = int(t["index"])
                break
        if ti is not None:
            preds.append({"kind": "definition", "token": ti, "char": (s0 + m.start(), s0 + m.end())})

    # modal auxiliaries governing a main verb
    for d in _deps(sentence):
        dep = d.get("dep")
        if dep in {"aux", "aux:pass"}:
            gov = int(d["governor"])
            dep_i = int(d["dependent"])
            if _is_modal_token(sentence, dep_i):
                kind = "permission"
                w = tokens[dep_i - 1].get("word", "").casefold()
                # look for not
                has_not = any(
                    (tokens[int(c["dependent"]) - 1].get("word", "").casefold() == "not")
                    for c in _children(sentence, gov)
                    if c.get("dep") in {"advmod", "neg"}
                ) or any(
                    (tokens[int(c["dependent"]) - 1].get("word", "").casefold() == "not")
                    for c in _children(sentence, dep_i)
                    if c.get("dep") in {"advmod", "neg"}
                )
                if w in {"shall", "must"} and has_not:
                    kind = "prohibition"
                elif w in {"may"} and has_not:
                    kind = "prohibition"
                elif w in {"shall", "must", "need"}:
                    kind = "obligation"
                elif w in {"may", "can"}:
                    kind = "permission"
                # skip if governor is inside advcl/mark-if of another clause without being rootish
                preds.append({"kind": kind, "token": gov, "modal": dep_i, "char": _token_abs_span(sentence, gov)})

    # ROOT verbs without modal that look definitional already handled
    for r in _find_roots(sentence):
        if not any(p["token"] == r for p in preds):
            w = tokens[r - 1].get("lemma", tokens[r - 1].get("word", "")).casefold()
            if w in {"mean", "means", "include", "amount"}:
                preds.append({"kind": "definition", "token": r, "char": _token_abs_span(sentence, r)})

    # dedupe by token
    by_tok: dict[int, dict[str, Any]] = {}
    for p in preds:
        by_tok[p["token"]] = p
    ordered = [by_tok[k] for k in sorted(by_tok)]
    return ordered


def _token_in_subordinate(sentence: Mapping[str, Any], token_idx: int) -> bool:
    """True if token is governed under mark/advcl/relcl that is not the main matrix."""
    # climb governors
    gov_map = {int(d["dependent"]): d for d in _deps(sentence) if d.get("dep") != "ROOT"}
    cur = token_idx
    seen = set()
    while cur in gov_map and cur not in seen:
        seen.add(cur)
        rel = gov_map[cur]
        dep = rel.get("dep")
        if dep in {"advcl", "relcl", "acl", "acl:relcl"}:
            # if this advcl is attached to root, it is subordinate
            return True
        if dep == "mark":
            return True
        cur = int(rel["governor"])
    return False


def _subtree_char_span(sentence: Mapping[str, Any], head_idx: int) -> tuple[int, int]:
    """Approx span of head + descendants via dependencies."""
    tokens = sentence["tokens"]
    kids = {head_idx}
    changed = True
    deps = _deps(sentence)
    while changed:
        changed = False
        for d in deps:
            g = int(d.get("governor", -1))
            dep = int(d.get("dependent", -1))
            if g in kids and dep not in kids and d.get("dep") != "ROOT":
                kids.add(dep)
                changed = True
    begins = [tokens[i - 1]["characterOffsetBegin"] for i in kids]
    ends = [tokens[i - 1]["characterOffsetEnd"] for i in kids]
    return min(begins), max(ends)


def plan_clause_units_v4(
    annotation: Mapping[str, Any],
    source_text: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Hybrid planner: stable sentence merge + conservative multi-modal split.

    Avoids aggressive under-segmentation that collapsed v4 recall.
    """
    from bpc_hybrid.estg150_b0_development_v2 import (
        merge_corenlp_sentence_groups,
        english_marker_modality,
    )

    stats = {
        "list_merges": 0,
        "multi_predicate_splits": 0,
        "subordinate_suppressed": 0,
        "sentence_groups": 0,
        "coord_splits": 0,
    }
    sentences = list(annotation["sentences"])
    if not sentences:
        return [], stats

    groups = merge_corenlp_sentence_groups(annotation, source_text)
    stats["sentence_groups"] = len(groups)
    # count merges roughly
    stats["list_merges"] = sum(max(0, len(g["sentence_indexes"]) - 1) for g in groups)

    units: list[dict[str, Any]] = []
    for group in groups:
        indexes = list(group["sentence_indexes"])
        start = sentences[indexes[0]]["tokens"][0]["characterOffsetBegin"]
        end = sentences[indexes[-1]]["tokens"][-1]["characterOffsetEnd"]
        text = source_text[start:end]

        # Conservative multi-modal split: only explicit modal anchors not in leading subordinate
        markers = list(_MODAL_ANCHOR.finditer(text))
        # drop definition nested in obligation? keep all anchors
        main_markers = []
        for m in markers:
            # skip markers inside leading if/when clause before first comma? simple: skip if preceded by unless/if without finite main
            prefix = text[: m.start()]
            # if marker is 'means' / shall mean treat as definition nucleus
            main_markers.append(m)
        # Split when >=2 obligation/permission/prohibition markers of independent force
        forces = []
        for m in main_markers:
            lab = english_marker_modality_v4(m.group(0)) or english_marker_modality(m.group(0))
            # for bare shall/must/may
            if lab is None:
                g = m.group(0).casefold()
                if "not" in g:
                    lab = "prohibition"
                elif g in {"shall", "must"}:
                    lab = "obligation"
                elif g == "may":
                    lab = "permission"
                elif "mean" in g:
                    lab = "definition"
            if lab:
                forces.append((m, lab))
        # only split on 2+ non-definition forces OR definition+deontic that are far apart
        deontic = [(m, lab) for m, lab in forces if lab != "definition"]
        if len(indexes) == 1 and len(deontic) >= 2:
            cuts = []
            for (m1, _), (m2, _) in zip(deontic, deontic[1:]):
                window = text[m1.end() : m2.start()]
                cut = None
                for cm in re.finditer(r";|\band\b|\bor\b|\bbut\b", window, re.I):
                    cut = m1.end() + cm.start()
                if cut is None:
                    cut = (m1.end() + m2.start()) // 2
                cuts.append(cut)
            bounds = [0] + cuts + [len(text)]
            for j in range(len(bounds) - 1):
                a = start + bounds[j]
                b = start + bounds[j + 1]
                while a < b and source_text[a].isspace():
                    a += 1
                while b > a and source_text[b - 1].isspace():
                    b -= 1
                if b > a:
                    units.append(
                        {
                            "sentence_indexes": indexes,
                            "primary_index": indexes[0],
                            "clause_char_span": (a, b),
                            "reason": "multi_modal_split",
                        }
                    )
            stats["multi_predicate_splits"] += max(0, len(deontic) - 1)
            continue

        units.append(
            {
                "sentence_indexes": indexes,
                "primary_index": indexes[0],
                "clause_char_span": (start, end),
                "reason": "sentence_group",
            }
        )
    return units, stats

def align_german_to_english_units_v4(
    german_text: str,
    english_units: Sequence[str],
) -> list[str]:
    """Anchor-aware DE-EN packing; falls back to length packing."""
    de_units = split_german_units(german_text)
    n_en = len(english_units)
    if n_en == 0:
        return []
    if not de_units:
        return [german_text.strip() or german_text] * n_en
    if len(de_units) == n_en:
        return de_units
    if len(de_units) == 1:
        return [de_units[0]] * n_en
    if n_en == 1:
        return [" ".join(de_units)]

    # score de units by modal/definition anchors and list numbers
    def anchors(text: str) -> set[str]:
        found = set()
        for m in _MODAL_ANCHOR.finditer(text):
            found.add(m.group(0).casefold())
        for m in re.finditer(r"\b\d+[\.\)]", text):
            found.add(m.group(0))
        return found

    en_anchors = [anchors(u) for u in english_units]
    de_anchors = [anchors(u) for u in de_units]
    # greedy monotone assign de blocks to en
    assigned: list[list[str]] = [[] for _ in range(n_en)]
    di = 0
    for ei in range(n_en):
        remaining_en = n_en - ei
        remaining_de = len(de_units) - di
        take = max(1, remaining_de // remaining_en)
        # extend take if next de shares anchor with this en
        end = min(len(de_units), di + take)
        while end < len(de_units) and remaining_de - (end - di) >= remaining_en - 1:
            if en_anchors[ei] and de_anchors[end] & en_anchors[ei]:
                end += 1
            else:
                break
        # ensure last en gets rest
        if ei == n_en - 1:
            end = len(de_units)
        assigned[ei] = de_units[di:end] or [de_units[min(di, len(de_units) - 1)]]
        di = end
        if di >= len(de_units) and ei < n_en - 1:
            # pad
            for k in range(ei + 1, n_en):
                assigned[k] = [de_units[-1]]
            break
    return [" ".join(chunk) for chunk in assigned]


def _char_of_tokens(sentence: Mapping[str, Any], begin_0: int, end_0_excl: int) -> dict[str, Any]:
    tokens = sentence["tokens"]
    start = tokens[begin_0]["characterOffsetBegin"]
    end = tokens[end_0_excl - 1]["characterOffsetEnd"]
    return {"begin": begin_0, "end": end_0_excl, "start": start, "end_char": end}


def resolve_actor_action_deps(
    sentence: Mapping[str, Any],
    source_text: str,
    clause_start: int,
    clause_end: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[int, int]]]:
    """Return actor spans, action spans, and (actor_i, action_i) ownership pairs."""
    tokens = sentence["tokens"]
    actors: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    pairs: list[tuple[int, int]] = []

    def in_clause(idx: int) -> bool:
        a, b = _token_abs_span(sentence, idx)
        return not (b <= clause_start or a >= clause_end)

    # action heads: verbs with modal aux or ROOT verbs inside clause
    action_heads: list[int] = []
    for d in _deps(sentence):
        if d.get("dep") in {"aux", "aux:pass"} and _is_modal_token(sentence, int(d["dependent"])):
            gov = int(d["governor"])
            if in_clause(gov) and not _token_in_subordinate(sentence, gov):
                action_heads.append(gov)
    for r in _find_roots(sentence):
        if in_clause(r) and r not in action_heads:
            # only if lexical content verb
            pos = tokens[r - 1].get("pos", "")
            if pos.startswith("VB"):
                action_heads.append(r)
    action_heads = sorted(set(action_heads))

    for head in action_heads:
        # action span: head + objects/complements, exclude modal/advcl/mark
        include = {head}
        for d in _children(sentence, head):
            rel = d.get("dep")
            dep = int(d["dependent"])
            if rel in {"dobj", "obj", "iobj", "xcomp", "ccomp", "attr", "acomp", "compound:prt", "prt"}:
                # add subtree
                st0, st1 = _subtree_char_span(sentence, dep)
                for t in tokens:
                    if st0 <= t["characterOffsetBegin"] < st1 or st0 < t["characterOffsetEnd"] <= st1:
                        include.add(int(t["index"]))
            if rel in {"nmod", "obl"} and not _CONDITION_MARKERS.search(
                source_text[tokens[dep - 1]["characterOffsetBegin"] : tokens[dep - 1]["characterOffsetEnd"]]
            ):
                # keep short obl as part of action if not constraint-like
                w = tokens[dep - 1].get("word", "")
                if len(w) < 20:
                    include.add(dep)
        # also include particle verbs head only if span too wide later trim
        idxs = sorted(i for i in include if in_clause(i))
        if not idxs:
            continue
        # prefer compact: head to last object
        start = tokens[idxs[0] - 1]["characterOffsetBegin"]
        end = tokens[idxs[-1] - 1]["characterOffsetEnd"]
        start = max(start, clause_start)
        end = min(end, clause_end)
        if end <= start:
            continue
        text = source_text[start:end]
        # strip leading modals/not
        text2 = re.sub(r"^(?:shall|must|may|can|not)\s+", "", text, flags=re.I)
        if text2 != text:
            delta = len(text) - len(text2)
            # adjust if prefix removed from start
            if text.startswith(text[:delta]):
                # find text2 in source
                pos = source_text.find(text2, start, end)
                if pos >= 0:
                    start, end = pos, pos + len(text2)
                    text = text2
        if len(text.split()) > 15:
            # keep head token + following up to 8 tokens
            head_pos = tokens[head - 1]["characterOffsetBegin"]
            end = min(clause_end, head_pos + 80)
            # snap to token end
            for t in tokens:
                if t["characterOffsetBegin"] >= head_pos and t["characterOffsetEnd"] <= clause_end:
                    if t["index"] <= head + 8:
                        end = t["characterOffsetEnd"]
            start = tokens[head - 1]["characterOffsetBegin"]
            text = source_text[start:end]
        actions.append(
            {
                "text": text,
                "start": start,
                "end": end,
                "normalized": " ".join(text.casefold().split()),
                "head": head,
            }
        )

        # actor for this action
        actor_idx = None
        for d in _deps(sentence):
            if int(d.get("governor", -1)) == head and d.get("dep") in {"nsubj", "nsubj:pass"}:
                actor_idx = int(d["dependent"])
                break
        # passive by-agent
        if actor_idx is None:
            for d in _deps(sentence):
                if int(d.get("governor", -1)) == head and d.get("dep") in {"obl:agent", "nmod:agent"}:
                    actor_idx = int(d["dependent"])
                    break
            if actor_idx is None:
                for d in _deps(sentence):
                    if d.get("dep") == "case":
                        dep = int(d["dependent"])
                        gov = int(d["governor"])
                        w = tokens[dep - 1].get("word", "").casefold()
                        if w == "by" and in_clause(gov):
                            actor_idx = gov
                            break
        if actor_idx is None or not in_clause(actor_idx):
            continue
        a0, a1 = _subtree_char_span(sentence, actor_idx)
        a0, a1 = max(a0, clause_start), min(a1, clause_end)
        if a1 <= a0:
            continue
        atext = source_text[a0:a1].strip()
        words = re.findall(r"[A-Za-z\u00c0-\u024f]+", atext.casefold())
        if not words:
            continue
        if words[0] in _NON_ACTOR and not any(w in _ACTOR_LEX for w in words):
            continue
        if all(w in _NON_ACTOR for w in words):
            continue
        # trim leading det only kept
        if len(words) > 10:
            # keep last 8 content tokens approx
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
        # dedupe actors
        ai = None
        for j, existing in enumerate(actors):
            if not (actor_span["end"] <= existing["start"] or actor_span["start"] >= existing["end"]):
                # keep smaller sufficient
                if (actor_span["end"] - actor_span["start"]) < (existing["end"] - existing["start"]):
                    actors[j] = actor_span
                ai = j
                break
        if ai is None:
            actors.append(actor_span)
            ai = len(actors) - 1
        pairs.append((ai, len(actions) - 1))

    return actors, actions, pairs


def _regex_spans(text: str, base: int, pattern: re.Pattern[str], max_len: int = 120) -> list[dict[str, Any]]:
    out = []
    for m in pattern.finditer(text):
        # expand to a short phrase window
        start = m.start()
        end = m.end()
        # extend right to next punctuation/comma boundary
        j = end
        while j < len(text) and j - start < max_len and text[j] not in ".;\n":
            j += 1
        # include a bit after marker
        frag = text[start:j].strip()
        if not frag:
            continue
        abs_s = base + start
        abs_e = abs_s + len(text[start : start + len(frag)])
        # re-find exact
        abs_e = base + start + len(frag)
        out.append(
            {
                "text": frag,
                "start": abs_s,
                "end": abs_e,
                "normalized": " ".join(frag.casefold().split()),
            }
        )
    return out


def resolve_scope_fields(
    source_text: str,
    clause_start: int,
    clause_end: int,
    tregex_obs: Mapping[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]],
) -> dict[str, list[dict[str, Any]]]:
    """Merge tregex candidates with marker regex; prefer smaller sufficient spans."""
    clause = source_text[clause_start:clause_end]
    result: dict[str, list[dict[str, Any]]] = {
        "condition": [],
        "constraint": [],
        "exception": [],
    }
    # from tregex
    for field in result:
        for sent, obs in tregex_obs.get(field, []):
            try:
                span = _token_span(source_text, sent, obs)
            except Exception:
                continue
            if span["end"] <= clause_start or span["start"] >= clause_end:
                continue
            # clip
            s = max(span["start"], clause_start)
            e = min(span["end"], clause_end)
            if e <= s:
                continue
            result[field].append(
                {
                    "text": source_text[s:e],
                    "start": s,
                    "end": e,
                    "normalized": " ".join(source_text[s:e].casefold().split()),
                }
            )
    # regex boost for recall
    result["condition"].extend(_regex_spans(clause, clause_start, _CONDITION_MARKERS, 80))
    result["constraint"].extend(_regex_spans(clause, clause_start, _CONSTRAINT_MARKERS, 60))
    result["exception"].extend(_regex_spans(clause, clause_start, _EXCEPTION_MARKERS, 100))

    def dedupe_smallest(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
        spans = sorted(spans, key=lambda s: (s["start"], s["end"] - s["start"], s["text"]))
        kept: list[dict[str, Any]] = []
        for sp in spans:
            if sp["end"] - sp["start"] > 160:
                continue
            overlap = [k for k in kept if not (sp["end"] <= k["start"] or sp["start"] >= k["end"])]
            if not overlap:
                kept.append(sp)
                continue
            # keep smaller sufficient (shorter) among overlaps
            rival = min(overlap + [sp], key=lambda s: (s["end"] - s["start"], s["start"]))
            for o in overlap:
                kept.remove(o)
            kept.append(rival)
        kept.sort(key=lambda s: (s["start"], s["end"]))
        # cap per field
        return kept[:4]

    for field in result:
        result[field] = dedupe_smallest(result[field])
    return result


def build_canonical_record_v4(
    *,
    sample_id: str,
    source_id: str,
    source_text: str,
    annotation: Mapping[str, Any],
    phrase_cases: Sequence[Mapping[str, Any]],
    clause_units: Sequence[Mapping[str, Any]],
    predictions: Sequence[ModalityPrediction],
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
    for unit_index, (unit, prediction) in enumerate(zip(clause_units, predictions, strict=True)):
        sentence_indexes = unit["sentence_indexes"]
        if "clause_char_span" in unit:
            clause_start, clause_end = unit["clause_char_span"]
        else:
            clause_start = sentences[sentence_indexes[0]]["tokens"][0]["characterOffsetBegin"]
            clause_end = sentences[sentence_indexes[-1]]["tokens"][-1]["characterOffsetEnd"]
        clause_span = _plain_span(source_text, clause_start, clause_end)
        clause_id = f"{sample_id}.c{unit_index + 1}"

        # collect tregex obs
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

        # modality evidence
        modality_evidence = []
        for sent, obs in tregex_obs["modality"]:
            try:
                sp = _token_span(source_text, sent, obs)
                if sp["end"] > clause_start and sp["start"] < clause_end:
                    modality_evidence.append(sp)
            except Exception:
                pass
        if not modality_evidence:
            modality_evidence = [dict(clause_span)]

        # dep-based actors/actions for primary sentence, fall back to all in unit
        actors: list[dict[str, Any]] = []
        actions: list[dict[str, Any]] = []
        owner_pairs: list[tuple[int, int]] = []
        for sidx in sentence_indexes:
            a, act, pairs = resolve_actor_action_deps(
                sentences[sidx], source_text, clause_start, clause_end
            )
            base_a, base_act = len(actors), len(actions)
            actors.extend(a)
            actions.extend(act)
            for ai, aci in pairs:
                owner_pairs.append((base_a + ai, base_act + aci))
        # if no dep actions, use trimmed tregex actions
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
                    kept = []
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
                actions.append(
                    {
                        "text": text,
                        "start": s,
                        "end": e,
                        "normalized": " ".join(text.casefold().split()),
                    }
                )
        # filter actors again
        filtered_actors = []
        for a in actors:
            words = re.findall(r"[A-Za-z\u00c0-\u024f]+", a["text"].casefold())
            if not words:
                continue
            # drop pure pronouns / pure abstract non-entities
            if len(words) == 1 and words[0] in _NON_ACTOR:
                continue
            if all(w in _NON_ACTOR for w in words) and not any(w in _ACTOR_LEX for w in words):
                continue
            if len(a["text"].split()) > 14:
                continue
            filtered_actors.append(a)
        actors = filtered_actors

        scope = resolve_scope_fields(source_text, clause_start, clause_end, tregex_obs)

        def finalize(spans: list[dict[str, Any]], singular: str) -> list[dict[str, Any]]:
            out = []
            for rank, sp in enumerate(spans, start=1):
                out.append(
                    {
                        "id": f"{clause_id}.{singular}.{rank}",
                        "text": sp["text"],
                        "start": sp["start"],
                        "end": sp["end"],
                        "normalized": sp.get("normalized")
                        or " ".join(sp["text"].casefold().split()),
                    }
                )
            return out

        mapped = {
            "actors": finalize(actors, "actor"),
            "actions": finalize(actions, "action"),
            "conditions": finalize(scope["condition"], "condition"),
            "constraints": finalize(scope["constraint"], "constraint"),
            "exceptions": finalize(scope["exception"], "exception"),
        }

        actor_action_map = []
        if mapped["actors"] and mapped["actions"]:
            if owner_pairs:
                for ai, aci in owner_pairs:
                    if ai < len(mapped["actors"]) and aci < len(mapped["actions"]):
                        actor_action_map.append(
                            {
                                "actor_id": mapped["actors"][ai]["id"],
                                "action_id": mapped["actions"][aci]["id"],
                            }
                        )
            # No evidence-free fanout: only 1-1 when both singleton and ownership empty.
            if not actor_action_map and len(mapped["actors"]) == 1 and len(mapped["actions"]) == 1:
                actor_action_map.append(
                    {
                        "actor_id": mapped["actors"][0]["id"],
                        "action_id": mapped["actions"][0]["id"],
                    }
                )

        clauses.append(
            {
                "clause_id": clause_id,
                "clause_span": clause_span,
                "modality": {
                    "label": prediction.label,
                    "evidence": modality_evidence[:1],
                },
                **mapped,
                "actor_action_map": actor_action_map,
                "order_relations": [],
            }
        )

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


def run_corenlp_batch_v4(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    root = Path(project_root).resolve()
    runtime_home = Path(runtime_home).resolve()
    runtime_identity = _verify_runtime_identity(root, runtime_home)
    probe = resolve_corenlp_runtime(root, home=runtime_home)
    if not probe.ready or not probe.java_executable:
        raise Estg150B0DevelopmentError(f"CoreNLP runtime unavailable: {probe.reasons}")
    javac = shutil.which("javac")
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
    bridge_path = root / BRIDGE_REL
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
            probe.java_executable, "-cp", bridge_classpath, BRIDGE_CLASS,
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
        "bridge_class": BRIDGE_CLASS,
        "patterns_path": PATTERNS_REL,
    }


def run_b0_batch_v4(
    project_root: Path,
    source_records: Sequence[Mapping[str, Any]],
    *,
    runtime_home: Path,
    work_dir: Path,
    device: str = "cpu",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = Path(project_root).resolve()
    s26_config = load_s26_config(root / S26_CONFIG_REL)
    annotations, cases_by_id, runtime = run_corenlp_batch_v4(
        root, source_records, runtime_home=runtime_home, work_dir=work_dir
    )
    classifier_started = time.perf_counter()
    try:
        classifier = LockedBertTextCNNInference.load(root, s26_config, device=device)
    except SunB0CompositionError as exc:
        raise Estg150B0DevelopmentError(str(exc)) from exc
    lexicon_runtime = _get_lexicon_v2(root)
    lexicon_stats = (
        {
            "lexicon_id": lexicon_runtime.lexicon_id,
            "active_counts": dict(lexicon_runtime.active_counts),
            "active_total": lexicon_runtime.active_total(),
            "manifest_sha256": lexicon_runtime.manifest_sha256,
            "category_file_sha256": dict(lexicon_runtime.category_file_sha256),
            "modality_patterns_compiled": len(lexicon_runtime.modality_patterns),
        }
        if lexicon_runtime is not None
        else None
    )

    planned: list[tuple[Mapping[str, Any], list[dict[str, Any]], list[str], list[str], dict[str, int]]] = []
    all_de_texts: list[str] = []
    seg_stats_total = {
        "list_merges": 0,
        "multi_predicate_splits": 0,
        "subordinate_suppressed": 0,
        "sentence_groups": 0,
    }
    for record in source_records:
        sample_id = record["sample_id"]
        annotation = annotations[sample_id]
        source_text = record["approved_text_en"]
        clause_units, seg_stats = plan_clause_units_v4(annotation, source_text)
        for k, v in seg_stats.items():
            seg_stats_total[k] = seg_stats_total.get(k, 0) + v
        en_texts = []
        for unit in clause_units:
            s, e = unit["clause_char_span"]
            en_texts.append(source_text[s:e])
        de_units = align_german_to_english_units_v4(record["raw_text_de"], en_texts)
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
    for record, clause_units, en_texts, de_units, _seg in planned:
        sample_id = record["sample_id"]
        unit_predictions: list[ModalityPrediction] = []
        de_n = len(split_german_units(record["raw_text_de"])) or 1
        en_n = len(en_texts)
        de_aligned = de_n == en_n
        for en_text, de_text in zip(en_texts, de_units, strict=True):
            base = de_predictions[pred_cursor]
            pred_cursor += 1
            final, route = resolve_modality_v4(
                english_clause=en_text,
                classifier=base,
                de_aligned=de_aligned,
            )
            modality_route_counts[route] = modality_route_counts.get(route, 0) + 1
            unit_predictions.append(final)
            label_counts[final.label] = label_counts.get(final.label, 0) + 1
            confidence_sum += final.confidence
        canonical = build_canonical_record_v4(
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
    runtime.update(
        {
            "classifier_seconds": classifier_seconds,
            "compose_seconds": compose_seconds,
            "total_seconds": total_seconds,
            "device": device,
            "record_count": len(canonical_records),
            "predicted_clause_count": sum(len(r["clauses"]) for r in canonical_records),
            "classifier_label_counts_by_clause": dict(sorted(label_counts.items())),
            "classifier_mean_confidence": confidence_sum / max(sum(label_counts.values()), 1),
            "modality_route_counts": dict(sorted(modality_route_counts.items())),
            "segmentation_stats": seg_stats_total,
            "method_id": METHOD_ID,
            "method_variant": METHOD_VARIANT,
            "paper_faithful_b0": False,
            "tsurgeon_enabled": TSURGEON_ENABLED,
            "lexicon_v2_enabled": LEXICON_V2_ENABLED,
            "s26_config_rel": S26_CONFIG_REL,
            "lexicon_v2": lexicon_stats,
        }
    )
    return attempts, runtime


def run_b0_batch_v7(*args, **kwargs):
    return run_b0_batch_v4(*args, **kwargs)
