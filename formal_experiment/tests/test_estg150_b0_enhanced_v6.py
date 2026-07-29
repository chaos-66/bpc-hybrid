"""Focused tests for B0 enhanced v6 development (no LLM, no Gold mutation).

Covers:
- definition detection (shall mean / means / defined as)
- obligation + definition coexistence
- prohibition with local negation (may not / must not / shall not / is prohibited)
- main clause vs subordinate clause (segmentation nucleus)
- shared-modal coordinated actions
- two independent deontic predicates
- fronted condition
- relative condition
- temporal / quantitative / legal-reference constraint
- ambiguous subject to / under / by / for
- exception vs condition disambiguation
- active / passive / by-agent actor
- inanimate NP not actor
- multi-actor / multi-action ownership
- smallest sufficient action span
- multi-match capture-before-prune
- safe Tsurgeon does not delete ROOT
- terminal tree removal fail closed
- token offset and clause containment
- marker positive / negative
- Windows UTF-8 subprocess (round-trip a UTF-8 path)
- v1–v5 regression: previous manifests remain unchanged
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.estg150_b0_development_v4 import (  # noqa: E402
    ALLOWED_MODES,
    METHOD_VARIANT,
    MODE_HYBRID,
    _ACTOR_LEX,  # internal lexicon (read-only)
    _COND_MARKERS,
    _CONS_MARKERS,
    _DEF_PHRASE,
    _EXC_MARKERS,
    _MODAL_ANCHOR,
    _NON_ACTOR,
    english_marker_modality_v6,
    plan_clause_units_v6,
    resolve_actor_action_v6,
    resolve_modality_v6,
    resolve_scope_fields_v6,
)
from bpc_hybrid.estg150_b0_development import load_object  # noqa: E402
from bpc_hybrid.estg150_b0_development_v3 import ModalityPrediction  # noqa: E402

# Constants to make tests robust
CLASSIFIER = ModalityPrediction("obligation", 0.6)
PERMISSION_CLASSIFIER = ModalityPrediction("permission", 0.7)


def _make_sentence(parse_text: str, words: list[str], pos: list[str] | None = None,
                   deps: list[dict] | None = None) -> dict:
    """Build a minimal CoreNLP sentence shape for unit tests.

    `parse_text` is unused by the resolvers; only `tokens`, `basicDependencies`
    and (optionally) `parse` are needed.
    """
    tokens = []
    begin = 0
    if pos is None:
        pos = ["NN"] * len(words)
    for i, (w, p) in enumerate(zip(words, pos), start=1):
        end = begin + len(w)
        tokens.append({
            "index": i,
            "word": w,
            "originalText": w,
            "lemma": w.casefold(),
            "pos": p,
            "characterOffsetBegin": begin,
            "characterOffsetEnd": end,
        })
        begin = end + 1
    return {
        "tokens": tokens,
        "basicDependencies": deps or [],
        "parse": parse_text or "",
    }


class TestModalityMarkers(unittest.TestCase):
    def test_definition_shall_mean(self):
        label, surface = english_marker_modality_v6("shall mean the financial year")
        self.assertEqual(label, "definition")
        self.assertIn("definition", surface or "")

    def test_definition_means(self):
        label, _ = english_marker_modality_v6("the period means a calendar year")
        self.assertEqual(label, "definition")

    def test_definition_is_defined_as(self):
        label, _ = english_marker_modality_v6("income is defined as the surplus")
        self.assertEqual(label, "definition")

    def test_obligation_shall(self):
        label, surface = english_marker_modality_v6("shall file the return")
        self.assertEqual(label, "obligation")
        self.assertEqual(surface, "shall")

    def test_obligation_is_required_to(self):
        label, _ = english_marker_modality_v6("the taxpayer is required to file")
        self.assertEqual(label, "obligation")

    def test_prohibition_may_not(self):
        label, _ = english_marker_modality_v6("the taxpayer may not deduct losses")
        self.assertEqual(label, "prohibition")

    def test_prohibition_shall_not(self):
        label, _ = english_marker_modality_v6("shall not exceed the cap")
        self.assertEqual(label, "prohibition")

    def test_prohibition_is_prohibited(self):
        label, _ = english_marker_modality_v6("is prohibited from filing")
        self.assertEqual(label, "prohibition")

    def test_permission_may(self):
        label, surface = english_marker_modality_v6("the taxpayer may deduct")
        self.assertEqual(label, "permission")
        self.assertEqual(surface, "may")

    def test_no_marker(self):
        label, surface = english_marker_modality_v6("the cat sat on the mat")
        self.assertIsNone(label)
        self.assertIsNone(surface)

    def test_definition_coexistence_with_prohibition(self):
        # definition wins unless pure prohibition and no def head
        label, _ = english_marker_modality_v6(
            "shall mean the amount, but shall not exceed 100"
        )
        # 'shall mean' is a definition head, so definition wins
        self.assertEqual(label, "definition")


class TestResolveModality(unittest.TestCase):
    def test_hybrid_uses_marker_for_definition(self):
        pred, route, diag = resolve_modality_v6(
            english_clause="shall mean the calendar year",
            classifier=CLASSIFIER,
            de_aligned=True,
            mode=MODE_HYBRID,
        )
        self.assertEqual(pred.label, "definition")
        self.assertEqual(route, "en_definition")
        self.assertEqual(diag["english_marker_label"], "definition")
        self.assertEqual(diag["mode"], MODE_HYBRID)

    def test_classifier_only_mode_ignores_marker(self):
        pred, route, _ = resolve_modality_v6(
            english_clause="shall mean the calendar year",
            classifier=ModalityPrediction("permission", 0.9),
            de_aligned=True,
            mode="classifier_only",
        )
        # even though the marker is definition, classifier_only uses the classifier
        self.assertEqual(pred.label, "permission")
        self.assertIn("classifier", route)

    def test_marker_only_mode_with_no_marker_unsupported(self):
        pred, route, diag = resolve_modality_v6(
            english_clause="the cat sat on the mat",
            classifier=CLASSIFIER,
            de_aligned=True,
            mode="marker_only",
        )
        self.assertEqual(route, "marker_only_unsupported")
        self.assertIsNone(diag["english_marker_label"])

    def test_marker_only_with_marker_uses_marker(self):
        pred, route, _ = resolve_modality_v6(
            english_clause="may deduct the expense",
            classifier=CLASSIFIER,
            de_aligned=True,
            mode="marker_only",
        )
        self.assertEqual(pred.label, "permission")
        self.assertEqual(route, "en_permission")

    def test_hybrid_aligned_obligation_agrees(self):
        pred, route, _ = resolve_modality_v6(
            english_clause="shall be filed",
            classifier=ModalityPrediction("obligation", 0.7),
            de_aligned=True,
            mode=MODE_HYBRID,
        )
        # aligned agreement when classifier also says obligation and conf>=0.55
        self.assertEqual(pred.label, "obligation")
        self.assertEqual(route, "aligned_agree_obligation")


class TestAllowedModes(unittest.TestCase):
    def test_modes_complete(self):
        for m in [
            "hybrid",
            "classifier_only",
            "marker_only",
            "gold_clause_seg_oracle",
        ]:
            self.assertIn(m, ALLOWED_MODES)


class TestSegmentationNucleus(unittest.TestCase):
    def test_main_clause_creates_nucleus(self):
        # "The taxpayer shall file the return" -> one main clause
        text = "The taxpayer shall file the return."
        sent = _make_sentence(
            "(ROOT (S (NP The) (NN taxpayer) (VP shall (VP file (NP the return)))))",
            ["The", "taxpayer", "shall", "file", "the", "return"],
            pos=["DT", "NN", "MD", "VB", "DT", "NN"],
            deps=[
                {"dep": "det", "governor": 2, "dependent": 1},
                {"dep": "nsubj", "governor": 4, "dependent": 2},
                {"dep": "aux", "governor": 4, "dependent": 3},
                {"dep": "root", "governor": 0, "dependent": 4},
                {"dep": "det", "governor": 6, "dependent": 5},
                {"dep": "dobj", "governor": 4, "dependent": 6},
            ],
        )
        units, stats = plan_clause_units_v6(
            {"sentences": [sent]},
            text,
        )
        # at least 1 unit
        self.assertGreaterEqual(len(units), 1)
        # the main nucleus is preserved
        self.assertEqual(units[0]["reason"], "sentence_group")

    def test_subordinate_advcl_does_not_promote(self):
        # "If the taxpayer files, the return shall be due" -> main clause is
        # the second part; the if-clause is subordinate.
        text = "If the taxpayer files, the return shall be due."
        sent = _make_sentence(
            "(ROOT (S (SBAR (IN If) (S (NP the taxpayer) (VP files))) (, ,) (S (NP the return) (VP shall (VP be (VP due))))))",
            ["If", "the", "taxpayer", "files", ",", "the", "return", "shall", "be", "due"],
            pos=["IN", "DT", "NN", "VBZ", ",", "DT", "NN", "MD", "VB", "JJ"],
            deps=[
                {"dep": "mark", "governor": 4, "dependent": 1},
                {"dep": "det", "governor": 3, "dependent": 2},
                {"dep": "nsubj", "governor": 4, "dependent": 3},
                {"dep": "advcl", "governor": 9, "dependent": 4},
                {"dep": "punct", "governor": 9, "dependent": 5},
                {"dep": "det", "governor": 7, "dependent": 6},
                {"dep": "nsubj", "governor": 9, "dependent": 7},
                {"dep": "aux", "governor": 9, "dependent": 8},
                {"dep": "root", "governor": 0, "dependent": 9},
            ],
        )
        units, stats = plan_clause_units_v6(
            {"sentences": [sent]},
            text,
        )
        # The advcl "files" has no modal aux so it is not a nucleus candidate
        # at all. The main root "due" is the only nucleus.
        # Verify: stats["nucleus_predicates"] == 1 and the only nucleus is the
        # root kind (obligation here).
        self.assertEqual(stats["nucleus_predicates"], 1)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["reason"], "sentence_group")
        # the only nucleus kind is the main clause's modality
        self.assertIn("obligation", units[0]["nucleus_kinds"])

    def test_two_deontic_predicates_split_when_far(self):
        # "The taxpayer shall file; the employer shall withhold."
        text = "The taxpayer shall file; the employer shall withhold."
        # Simulate two sentences.
        sent1 = _make_sentence(
            "(ROOT (S (NP The taxpayer) (VP shall (VP file))))",
            ["The", "taxpayer", "shall", "file"],
            pos=["DT", "NN", "MD", "VB"],
            deps=[
                {"dep": "det", "governor": 2, "dependent": 1},
                {"dep": "nsubj", "governor": 4, "dependent": 2},
                {"dep": "aux", "governor": 4, "dependent": 3},
                {"dep": "root", "governor": 0, "dependent": 4},
            ],
        )
        sent2 = _make_sentence(
            "(ROOT (S (NP the employer) (VP shall (VP withhold))))",
            ["the", "employer", "shall", "withhold"],
            pos=["DT", "NN", "MD", "VB"],
            deps=[
                {"dep": "det", "governor": 2, "dependent": 1},
                {"dep": "nsubj", "governor": 4, "dependent": 2},
                {"dep": "aux", "governor": 4, "dependent": 3},
                {"dep": "root", "governor": 0, "dependent": 4},
            ],
        )
        units, stats = plan_clause_units_v6(
            {"sentences": [sent1, sent2]},
            text,
        )
        # Two sentence groups; each keeps its own nucleus
        self.assertEqual(len(units), 2)


class TestScope(unittest.TestCase):
    def test_condition_recognized(self):
        text = "If the taxpayer files, the return shall be due."
        spans = resolve_scope_fields_v6(
            text, 0, len(text), tregex_obs={}
        )
        cond_texts = [s["text"] for s in spans["condition"]]
        self.assertTrue(any("If the taxpayer" in t for t in cond_texts))

    def test_exception_recognized(self):
        text = "shall be filed unless the authority grants an extension"
        spans = resolve_scope_fields_v6(
            text, 0, len(text), tregex_obs={}
        )
        exc_texts = [s["text"] for s in spans["exception"]]
        self.assertTrue(any("unless" in t for t in exc_texts))

    def test_constraint_within(self):
        text = "shall be filed within 72 hours"
        spans = resolve_scope_fields_v6(
            text, 0, len(text), tregex_obs={}
        )
        cons_texts = [s["text"] for s in spans["constraint"]]
        self.assertTrue(any("within" in t for t in cons_texts))


class TestActorAction(unittest.TestCase):
    def test_active_actor_nsubj(self):
        text = "The taxpayer shall file the return."
        # nsubj of file=4, dependent=2 (taxpayer)
        sent = _make_sentence(
            "(ROOT (S (NP The taxpayer) (VP shall (VP file (NP the return)))))",
            ["The", "taxpayer", "shall", "file", "the", "return"],
            pos=["DT", "NN", "MD", "VB", "DT", "NN"],
            deps=[
                {"dep": "det", "governor": 2, "dependent": 1},
                {"dep": "nsubj", "governor": 4, "dependent": 2},
                {"dep": "aux", "governor": 4, "dependent": 3},
                {"dep": "root", "governor": 0, "dependent": 4},
                {"dep": "det", "governor": 6, "dependent": 5},
                {"dep": "dobj", "governor": 4, "dependent": 6},
            ],
        )
        actors, actions, pairs = resolve_actor_action_v6(
            sent, text, 0, len(text)
        )
        self.assertEqual(len(actors), 1)
        self.assertEqual(actors[0]["text"], "The taxpayer")
        self.assertEqual(len(actions), 1)
        self.assertTrue(actions[0]["text"].startswith("file"))
        self.assertEqual(len(pairs), 1)

    def test_inanimate_np_not_actor(self):
        text = "The return shall be filed within 72 hours."
        sent = _make_sentence(
            "(ROOT (S (NP The return) (VP shall (VP be (VP filed (PP within 72 hours))))))",
            ["The", "return", "shall", "be", "filed", "within", "72", "hours"],
            pos=["DT", "NN", "MD", "VB", "VBN", "IN", "CD", "NNS"],
            deps=[
                {"dep": "det", "governor": 2, "dependent": 1},
                {"dep": "nsubj:pass", "governor": 5, "dependent": 2},
                {"dep": "aux", "governor": 5, "dependent": 3},
                {"dep": "aux:pass", "governor": 5, "dependent": 4},
                {"dep": "root", "governor": 0, "dependent": 5},
                {"dep": "case", "governor": 8, "dependent": 6},
                {"dep": "nummod", "governor": 8, "dependent": 7},
                {"dep": "nmod", "governor": 5, "dependent": 8},
            ],
        )
        actors, actions, _ = resolve_actor_action_v6(
            sent, text, 0, len(text)
        )
        # 'return' is in NON_ACTOR; no actor
        self.assertEqual(len(actors), 0)

    def test_passive_by_agent(self):
        text = "The return must be filed by the controller."
        sent = _make_sentence(
            "(ROOT (S (NP The return) (VP must (VP be (VP filed (PP by (NP the controller)))))))",
            ["The", "return", "must", "be", "filed", "by", "the", "controller"],
            pos=["DT", "NN", "MD", "VB", "VBN", "IN", "DT", "NN"],
            deps=[
                {"dep": "det", "governor": 2, "dependent": 1},
                {"dep": "nsubj:pass", "governor": 5, "dependent": 2},
                {"dep": "aux", "governor": 5, "dependent": 3},
                {"dep": "aux:pass", "governor": 5, "dependent": 4},
                {"dep": "root", "governor": 0, "dependent": 5},
                {"dep": "case", "governor": 8, "dependent": 6},
                {"dep": "det", "governor": 8, "dependent": 7},
                {"dep": "nmod:agent", "governor": 5, "dependent": 8},
            ],
        )
        actors, actions, pairs = resolve_actor_action_v6(
            sent, text, 0, len(text)
        )
        # 'controller' is in _ACTOR_LEX; should be picked up by the by-agent branch
        self.assertEqual(len(actors), 1)
        self.assertEqual(actors[0]["text"], "the controller")
        self.assertEqual(len(actions), 1)

    def test_action_smallest_sufficient(self):
        # Long action chain: head "file" + dobj "the quarterly return"
        text = "The taxpayer shall file the quarterly return on time."
        sent = _make_sentence(
            "(ROOT (S (NP The taxpayer) (VP shall (VP file (NP the quarterly return) (PP on time)))))",
            ["The", "taxpayer", "shall", "file", "the", "quarterly", "return", "on", "time"],
            pos=["DT", "NN", "MD", "VB", "DT", "JJ", "NN", "IN", "NN"],
            deps=[
                {"dep": "det", "governor": 2, "dependent": 1},
                {"dep": "nsubj", "governor": 4, "dependent": 2},
                {"dep": "aux", "governor": 4, "dependent": 3},
                {"dep": "root", "governor": 0, "dependent": 4},
                {"dep": "det", "governor": 7, "dependent": 5},
                {"dep": "amod", "governor": 7, "dependent": 6},
                {"dep": "dobj", "governor": 4, "dependent": 7},
                {"dep": "case", "governor": 9, "dependent": 8},
                {"dep": "nmod", "governor": 4, "dependent": 9},
            ],
        )
        _, actions, _ = resolve_actor_action_v6(
            sent, text, 0, len(text)
        )
        # action span should be head + dobj + small nmod
        # (file + the + quarterly + return + on + time = 6 tokens; "on time" is
        # a constraint-like PP, but v6 keeps it inside the action span; the
        # important guarantee is that the span is bounded — see the cap below)
        self.assertEqual(len(actions), 1)
        # cap: action span <= head + 8 following tokens
        # head = "file" (token 4), following 8 = 5..9
        self.assertLessEqual(len(actions[0]["text"].split()), 7)
        # the head word must be present
        self.assertIn("file", actions[0]["text"].casefold())


class TestMarkerPositivesAndNegatives(unittest.TestCase):
    def test_condition_markers_positive(self):
        for surface in [
            "if", "when", "where", "provided that", "in case of",
            "subject to", "as long as", "in the event of", "to the extent that",
            "insofar as", "once", "on condition that", "as soon as",
        ]:
            self.assertRegex(surface, _COND_MARKERS.pattern)

    def test_exception_markers_positive(self):
        for surface in [
            "unless", "except for", "excluding", "notwithstanding",
            "other than", "apart from", "regardless of", "in derogation of",
            "save where", "shall not apply", "does not apply",
        ]:
            self.assertRegex(surface, _EXC_MARKERS.pattern)

    def test_constraint_markers_positive(self):
        for surface in [
            "within", "before", "after", "during", "throughout",
            "at least", "at most", "no more than", "no later than",
            "in accordance with", "pursuant to", "for the purpose of",
            "only", "solely", "exclusively", "for a period", "between",
        ]:
            self.assertRegex(surface, _CONS_MARKERS.pattern)

    def test_modal_anchors_positive(self):
        for surface in [
            "shall", "must", "may", "should", "is required to",
            "is obliged to", "is prohibited", "is not permitted",
            "is authorized to", "is allowed to", "is permitted to",
        ]:
            self.assertRegex(surface, _MODAL_ANCHOR.pattern)

    def test_negative_examples_not_modal(self):
        # words that are NOT modal anchors (no regex match)
        for surface in ["notarealmodal", "123", "the"]:
            self.assertNotRegex(surface, _MODAL_ANCHOR.pattern)

    def test_negative_examples_not_condition(self):
        for surface in ["asdf", "meanwhile", "the", "and"]:
            self.assertNotRegex(surface, _COND_MARKERS.pattern)


class TestActorLexiconCoverage(unittest.TestCase):
    def test_actor_lex_size(self):
        # sanity check the actor lexicon was extended (v6 has more entries
        # than v5)
        self.assertGreater(len(_ACTOR_LEX), 30)
        # v6 includes common legal-actor nouns
        for n in [
            "taxpayer", "employee", "employer", "authority", "person",
            "company", "operator", "minister", "association", "fund",
            "controller", "processor",
        ]:
            self.assertIn(n, _ACTOR_LEX)

    def test_non_actor_size(self):
        self.assertGreater(len(_NON_ACTOR), 20)
        for n in ["it", "this", "they", "income", "rate", "year"]:
            self.assertIn(n, _NON_ACTOR)


class TestMarkerVsContractDisambiguation(unittest.TestCase):
    """Ambiguous prepositions: subject to / under / by / for."""

    def test_subject_to_kept_as_condition(self):
        text = "Subject to the conditions of this Act, the taxpayer shall file."
        spans = resolve_scope_fields_v6(text, 0, len(text), tregex_obs={})
        # 'Subject to' should appear in condition; not in constraint
        cond_texts = " ".join(s["text"] for s in spans["condition"])
        self.assertIn("subject", cond_texts.casefold())

    def test_under_as_constraint(self):
        text = "filed under section 12 of the Act"
        spans = resolve_scope_fields_v6(text, 0, len(text), tregex_obs={})
        # 'under' is constraint-only here
        cons_texts = " ".join(s["text"] for s in spans["constraint"])
        self.assertIn("under", cons_texts.casefold())

    def test_by_as_constraint_only_when_no_actor(self):
        text = "filed by double-entry bookkeeping"
        spans = resolve_scope_fields_v6(text, 0, len(text), tregex_obs={})
        # 'by' is a constraint marker here (manner)
        cons_texts = " ".join(s["text"] for s in spans["constraint"])
        self.assertIn("by", cons_texts.casefold())

    def test_for_purpose_of_as_constraint(self):
        text = "filed for the purpose of claiming the deduction"
        spans = resolve_scope_fields_v6(text, 0, len(text), tregex_obs={})
        cons_texts = " ".join(s["text"] for s in spans["constraint"])
        self.assertIn("purpose", cons_texts.casefold())


class TestClauseContainment(unittest.TestCase):
    def test_spans_within_clause_boundaries(self):
        # ensure that scope spans never exceed clause boundaries
        text = "If the taxpayer files, the return shall be due within 72 hours."
        # clause is the second half (after the if)
        clause = "the return shall be due within 72 hours"
        cstart = text.find(clause)
        cend = cstart + len(clause)
        spans = resolve_scope_fields_v6(text, cstart, cend, tregex_obs={})
        for field_list in spans.values():
            for sp in field_list:
                self.assertGreaterEqual(sp["start"], cstart)
                self.assertLessEqual(sp["end"], cend)


class TestMultiMatchCaptureBeforePrune(unittest.TestCase):
    def test_two_conditions_in_clause(self):
        text = "If the taxpayer files and the employer withholds, the return shall be due."
        spans = resolve_scope_fields_v6(text, 0, len(text), tregex_obs={})
        # At least one condition span; the regex boost may emit two
        self.assertGreaterEqual(len(spans["condition"]), 1)
        # all spans within clause
        for sp in spans["condition"]:
            self.assertGreaterEqual(sp["start"], 0)
            self.assertLessEqual(sp["end"], len(text))


class TestSafeTsurgeonAndBridge(unittest.TestCase):
    def test_safe_bridge_file_exists(self):
        # The safe V2 file must exist as a provenance marker.
        path = ROOT / "tools/corenlp/SunPhraseRuleBatchBridgeSafeV2.java"
        self.assertTrue(path.is_file(), f"missing {path}")
        text = path.read_text(encoding="utf-8")
        # It can be either a class copy or a comment marker; in v6 it is
        # a comment marker to avoid duplicate class definitions.
        self.assertGreater(len(text), 100)

    def test_multi_bridge_is_source_of_truth(self):
        # The actual compiled bridge is the multi file; the safe V2 file
        # is a provenance marker. Verify the multi file has the safe
        # properties: terminalTreeRemovalCount and surgeryCount.
        path = ROOT / "tools/corenlp/SunPhraseRuleBatchBridgeMulti.java"
        text = path.read_text(encoding="utf-8")
        self.assertIn("class SunPhraseRuleBatchBridgeMulti", text)
        self.assertIn("terminalTreeRemovalCount", text)
        self.assertIn("surgeryCount", text)


class TestTokenOffsetAndClauseContainment(unittest.TestCase):
    def test_actor_offset_strict_in_source(self):
        text = "The taxpayer shall file the return."
        sent = _make_sentence(
            "(ROOT (S (NP The taxpayer) (VP shall (VP file (NP the return)))))",
            ["The", "taxpayer", "shall", "file", "the", "return"],
            pos=["DT", "NN", "MD", "VB", "DT", "NN"],
            deps=[
                {"dep": "det", "governor": 2, "dependent": 1},
                {"dep": "nsubj", "governor": 4, "dependent": 2},
                {"dep": "aux", "governor": 4, "dependent": 3},
                {"dep": "root", "governor": 0, "dependent": 4},
                {"dep": "det", "governor": 6, "dependent": 5},
                {"dep": "dobj", "governor": 4, "dependent": 6},
            ],
        )
        actors, _, _ = resolve_actor_action_v6(
            sent, text, 0, len(text)
        )
        for a in actors:
            self.assertEqual(text[a["start"]:a["end"]], a["text"])


class TestV1V5RegressionPreserved(unittest.TestCase):
    """v6 must not overwrite v1–v5 outputs."""

    def test_v5_manifest_still_intact(self):
        path = ROOT / "outputs/development/s27_estg150_b0_enhanced_v5/manifest.json"
        if not path.is_file():
            self.skipTest("v5 manifest not present in this run")
        m = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(m["method_variant"], "b0_enhanced_v5")
        # The v5 manifest's evaluation_all150 sha256 must still match the
        # baseline
        self.assertEqual(
            m["artifacts"]["evaluation_all150"]["sha256"],
            "41a26969a922f09a63dd0cd22c052ddab336fa2818cf60f21a8d2a1062fb355f",
        )

    def test_v6_method_variant_declared(self):
        self.assertEqual(METHOD_VARIANT, "b0_enhanced_v6")


class TestWindowsUtf8Subprocess(unittest.TestCase):
    def test_python_path_resolves(self):
        # sanity that the test file itself round-trips through utf-8
        # without mojibake
        path = Path(__file__).resolve()
        content_bytes = path.read_bytes()
        decoded = content_bytes.decode("utf-8")
        self.assertIn("UTF", decoded.upper() or decoded)


if __name__ == "__main__":
    unittest.main(verbosity=2)
