# -*- coding: utf-8 -*-
"""Stage 3 action-matching successor (v2): exact-match priority + object evidence.

Scope of this module: **action matching only**.  It subclasses the committed
``EvidenceChecks`` (v1) and overrides ``action_match`` plus its private
helpers.  The executor check, the order check, the unknown aggregation, the
metric logic, the frozen ``SunScorer``, the similarity backend, the thresholds
and the installed NLP model are all inherited unchanged.  ``EvidenceChecks`` v1
stays byte-identical because historical manifests bind it.

Why (confirmed with per-item evidence on the frozen paired panel):

* v1 gave an exact label match 1.0 and a "same predicate + shared content word"
  match 1.0 as well.  Equal scores were then reported as indistinguishable
  candidates, so the unique exact match could not win.
* v1's content-word set came from the POS tagger.  On short activity labels the
  head verb is often tagged ``NOUN``, so the verb itself landed in the set and a
  *shared verb* masqueraded as a *shared business object* (observed shared set:
  ``['retrieve']``).
* With the true target deleted, a same-verb different-object activity still
  reached 1.0, was accepted as the required action and produced ``satisfied``.

Fixed matching policy (frozen before the panel was scored; no per-item rules):

1. One unique **exact** match wins over every approximate match.  Exactness uses
   an explicit, fixed normalisation: Unicode NFKC, case folding, whitespace
   collapsing and stripping.  Negations, numerals and distinguishing object
   words are never removed.
2. Two different activity IDs whose normalised labels are identical stay
   ambiguous (``unknown``).  No ordering by activity ID and no use of the frozen
   target ID may pick a winner.
3. Approximate candidates never reach the certainty of an exact match.  Object
   evidence excludes the head token, every token whose lemma equals the
   predicate and every verb/auxiliary, so the action word cannot fake an object
   agreement.
4. Equal predicate alone is not equivalence.  A candidate with the same predicate
   and *disjoint* object evidence (or different numerals / negation) is a
   conflict: the required action is not performed.  A high similarity score may
   not override that explicit difference.
5. Partial object overlap is genuinely under-determined and stays ``unknown`` --
   neither forced to ``satisfied`` nor forced to ``violation``.  When a side
   carries no object evidence the frozen similarity path decides, exactly as v1.
6. No GDPR-specific vocabulary, no sample-ID special cases, no target-label
   whitelist and no replacement table derived from this panel.

Every candidate records its match tier, the raw similarity, the object evidence
(shared / required-only / candidate-only), the numerals, the negation flag and
the accept/reject reason.  Tier and similarity are reported separately: no
fabricated "semantic probability".

Because the inherited checks branch on ``reason == "ambiguous_action_mapping"``
to mark a requirement unobservable, every under-determined tier keeps that
reason string for interface compatibility and additionally records the precise
cause in ``tier_reason``.  The check logic itself is not modified.
"""

from __future__ import annotations

import unicodedata

from bpc_hybrid.s3_evidence_checks_v1 import EvidenceChecks

METHOD = "s3_action_matching@2.0.0"
METHOD_ID = "evidence_checks_v2_action_matching"
BASE_METHOD = "s3_evidence_checks@1.0.0"
MODIFICATION_SCOPE = "action matching only"

_AMBIGUOUS_REASON = "ambiguous_action_mapping"
_OBJECT_POS = {"NOUN", "PROPN", "NUM"}
_OBJECT_RELATIONS = {"dobj", "pobj", "attr", "oprd"}
_SUBJECT_LIKE_RELATIONS = {"nsubj", "nsubjpass", "csubj", "npadvmod"}
_NON_OBJECT_POS = {"VERB", "AUX", "DET", "ADP", "PRON", "PART", "CCONJ", "SCONJ",
                   "PUNCT", "SPACE", "SYM", "INTJ", "ADV", "X"}
_NEGATION_TOKENS = frozenset({"not", "no", "never", "nor", "cannot", "without",
                              "none", "neither", "n't"})

TIER_EXACT = "exact_label"
TIER_EXACT_TIE = "exact_label_tie"
TIER_AGREEMENT = "predicate_object_agreement"
TIER_AGREEMENT_TIE = "predicate_object_agreement_tie"
TIER_CONFLICT = "object_conflict"
TIER_PARTIAL = "partial_object_overlap"
TIER_SIMILARITY = "frozen_similarity"
TIER_SIMILARITY_TIE = "frozen_similarity_tie"
TIER_BELOW_GAMMA = "similarity_below_gamma"
TIER_NO_ACTIONS = "no_process_actions"


def match_policy() -> dict:
    """The frozen matching policy, for the manifest and diagnostics."""
    return {
        "method": METHOD,
        "base_method": BASE_METHOD,
        "modification_scope": MODIFICATION_SCOPE,
        "exact_normalisation": "Unicode NFKC, casefold, collapse whitespace runs, strip",
        "exact_priority": "one unique exact match wins over every approximate match",
        "exact_tie": "different activity ids with identical normalised labels stay unknown",
        "object_evidence": "nominal tokens (NOUN/PROPN/NUM) minus the head token, minus any "
                           "token whose lemma equals the predicate, minus verbs and "
                           "auxiliaries, minus stopwords, and minus subject-like slots "
                           "(nsubj/nsubjpass/csubj/npadvmod) where a mis-tagged action word "
                           "lands; how many of the surviving tokens sit in an object relation "
                           "(dobj/pobj/attr/oprd) is recorded as relation support",
        "tiers": {
            TIER_EXACT: "mapped, certain",
            TIER_EXACT_TIE: "unknown (identical labels on several activities)",
            TIER_AGREEMENT: "mapped: same predicate, identical object evidence, numerals and "
                            "negation",
            TIER_AGREEMENT_TIE: "unknown (several indistinguishable equivalent candidates)",
            TIER_CONFLICT: "not mapped: same predicate with disjoint object evidence, or "
                           "different numerals / negation",
            TIER_PARTIAL: "unknown (partial object overlap: under-determined)",
            TIER_SIMILARITY: "mapped through the frozen similarity backend above gamma",
            TIER_SIMILARITY_TIE: "unknown (several equally similar candidates)",
            TIER_BELOW_GAMMA: "not mapped: best similarity at or below gamma",
            TIER_NO_ACTIONS: "no labelled process activity to match against",
        },
        "false": [
            "no GDPR vocabulary or object list",
            "no sample-id special cases",
            "no target-label whitelist",
            "no replacement table derived from panel results",
            "no ordering by activity id to settle identical labels",
            "no use of the frozen target id inside matching",
        ],
    }


class EvidenceChecksV2(EvidenceChecks):
    """v1 checker with the action matcher replaced; everything else inherited."""

    method_id = METHOD_ID

    def __init__(self, sim, tau, gamma, theta, nlp):
        super().__init__(sim, tau, gamma, theta, nlp=nlp)
        self._evidence_cache: dict[str, dict] = {}

    # ------------------------------------------------------------------ evidence
    @staticmethod
    def _normalize(text: str) -> str:
        value = unicodedata.normalize("NFKC", text).casefold()
        return " ".join(value.split())

    def _label_evidence(self, text: str) -> dict:
        """Deterministic evidence per label; never trusts the parser blindly."""
        cached = self._evidence_cache.get(text)
        if cached is not None:
            return cached
        doc = self.nlp(text)
        tokens = [token for token in doc if not token.is_punct and not token.is_space]
        head = None
        for token in tokens:
            if token.pos_ == "VERB" and token.dep_ == "ROOT":
                head = token
                break
        if head is None:
            for token in tokens:
                if token.pos_ == "VERB":
                    head = token
                    break
        predicate = head.lemma_.casefold() if head is not None else None
        if predicate is None:
            # The tagger found no verb: fall back to the first content token so a
            # mis-tagged action word still cannot enter the object evidence.
            for token in tokens:
                if not token.is_stop:
                    head = token
                    predicate = token.lemma_.casefold()
                    break
        objects: set[str] = set()
        relation_support = 0
        for token in tokens:
            lemma = token.lemma_.casefold()
            if token is head or lemma == predicate:
                continue
            if token.pos_ in _NON_OBJECT_POS or token.is_stop:
                continue
            if token.pos_ not in _OBJECT_POS:
                continue
            if token.dep_ in _SUBJECT_LIKE_RELATIONS:
                # Where a mis-tagged action word lands; never object evidence.
                continue
            objects.add(lemma)
            if token.dep_ in _OBJECT_RELATIONS and (head is None or token in head.subtree):
                relation_support += 1
        numerals: set[str] = set()
        for token in tokens:
            if token is head:
                continue
            if token.pos_ == "NUM" or token.like_num:
                numerals.add(token.lemma_.casefold())
        evidence = {
            "normalized": self._normalize(text),
            "predicate": predicate,
            "objects": frozenset(objects),
            "object_relation_support": relation_support,
            "numerals": frozenset(numerals),
            "negated": any(token.dep_ == "neg" or token.lower_ in _NEGATION_TOKENS
                           for token in tokens),
        }
        self._evidence_cache[text] = evidence
        return evidence

    def _candidate(self, activity, required: dict) -> dict:
        label = activity.get("name", "")
        evidence = self._label_evidence(label)
        required_objects = required["objects"]
        candidate_objects = evidence["objects"]
        shared = sorted(required_objects & candidate_objects)
        only_required = sorted(required_objects - candidate_objects)
        only_candidate = sorted(candidate_objects - required_objects)
        exact = evidence["normalized"] == required["normalized"]
        same_predicate = (required["predicate"] is not None
                          and evidence["predicate"] == required["predicate"])
        both_have_objects = bool(required_objects) and bool(candidate_objects)
        objects_equal = both_have_objects and required_objects == candidate_objects
        disjoint = both_have_objects and not shared
        partial = bool(shared) and bool(only_required or only_candidate)
        numerals_equal = required["numerals"] == evidence["numerals"]
        negation_equal = required["negated"] == evidence["negated"]
        if not same_predicate:
            tier = TIER_SIMILARITY
        elif exact:
            tier = TIER_EXACT
        elif objects_equal and numerals_equal and negation_equal:
            tier = TIER_AGREEMENT
        elif (not numerals_equal) or (not negation_equal) or disjoint:
            tier = TIER_CONFLICT
        elif partial:
            tier = TIER_PARTIAL
        else:
            # Same predicate but no usable object evidence on one side: the
            # frozen similarity path decides, exactly as v1 did.
            tier = TIER_SIMILARITY
        similarity = float(self.sim.text_pair(self._lemma(required["text"]),
                                              self._lemma(label)))
        return {
            "activity_id": activity["id"],
            "label": label,
            "match_tier": tier,
            "same_predicate": same_predicate,
            "exact_label": exact,
            "raw_similarity": similarity,
            "object_evidence": {
                "shared_objects": shared,
                "required_only_objects": only_required,
                "candidate_only_objects": only_candidate,
                "required_objects": sorted(required_objects),
                "candidate_objects": sorted(candidate_objects),
                "required_object_relation_support": required.get("object_relation_support"),
                "candidate_object_relation_support": evidence["object_relation_support"],
            },
            "numerals_equal": numerals_equal,
            "negation_equal": negation_equal,
        }

    # ------------------------------------------------------------------ matching
    def action_match(self, rule_action, model):
        required = dict(self._label_evidence(rule_action))
        required["text"] = rule_action
        candidates = [self._candidate(activity, required)
                      for activity in model.actions if activity.get("name", "")]
        for candidate in candidates:
            candidate["decision"] = self._decide_candidate(candidate, candidates, required)
        if not candidates:
            return {"mapped": False, "reason": TIER_NO_ACTIONS, "match_tier": TIER_NO_ACTIONS,
                    "tier_reason": "no labelled process activity", "candidates": [],
                    "required": self._required_summary(required)}

        exact_ids = sorted({c["activity_id"] for c in candidates if c["exact_label"]})
        if len(exact_ids) > 1:
            return self._undetermined(candidates, exact_ids, TIER_EXACT_TIE,
                                      "identical labels on several activities", required)
        exact = [c for c in candidates if c["exact_label"]]
        if exact:
            return self._mapped(exact[0], candidates, TIER_EXACT, required)

        agreeing = [c for c in candidates if c["match_tier"] == TIER_AGREEMENT]
        agreeing_ids = sorted({c["activity_id"] for c in agreeing})
        if len(agreeing_ids) == 1:
            winner = next(c for c in agreeing if c["activity_id"] == agreeing_ids[0])
            return self._mapped(winner, candidates, TIER_AGREEMENT, required)
        if len(agreeing_ids) > 1:
            return self._undetermined(candidates, agreeing_ids, TIER_AGREEMENT_TIE,
                                      "several activities carry identical required object "
                                      "evidence", required)

        conflicts = [c for c in candidates if c["match_tier"] == TIER_CONFLICT]
        if conflicts:
            winner = sorted(conflicts, key=lambda c: (-c["raw_similarity"], c["activity_id"]))[0]
            winner = {**winner, "chosen_by": "diagnostic_only: highest raw similarity, "
                                             "activities id as final deterministic tiebreak"}
            return {"mapped": False, "reason": "object_conflict_evidence",
                    "match_tier": TIER_CONFLICT,
                    "tier_reason": "same predicate with conflicting object/number/negation "
                                   "evidence",
                    "best": winner, "required": self._required_summary(required),
                    "candidates": self._ranked(candidates),
                    "conflicting_activity_ids": sorted(c["activity_id"] for c in conflicts)}

        partial = [c for c in candidates if c["match_tier"] == TIER_PARTIAL]
        partial_ids = sorted({c["activity_id"] for c in partial})
        if partial_ids:
            return self._undetermined(candidates, partial_ids, TIER_PARTIAL,
                                      "partial object overlap; the required action set is "
                                      "neither equalled nor excluded", required)

        ranked = self._ranked(candidates)
        best = max(candidates, key=lambda c: (c["raw_similarity"], c["activity_id"]))
        if best["raw_similarity"] <= self.gamma:
            return {"mapped": False, "reason": TIER_BELOW_GAMMA, "match_tier": TIER_BELOW_GAMMA,
                    "tier_reason": f"best raw similarity {best['raw_similarity']:.4f} <= gamma",
                    "best": best, "required": self._required_summary(required),
                    "candidates": ranked[:3]}
        tied = [c for c in candidates
                if abs(c["raw_similarity"] - best["raw_similarity"]) < 1e-10]
        tied_ids = sorted({c["activity_id"] for c in tied})
        if len(tied_ids) > 1:
            return self._undetermined(candidates, tied_ids, TIER_SIMILARITY_TIE,
                                      "several equally similar candidates", required)
        return {"mapped": True, "reason": None, "match_tier": TIER_SIMILARITY,
                "tier_reason": "above gamma through the frozen similarity backend",
                "best": {**best, "match_tier": TIER_SIMILARITY},
                "required": self._required_summary(required), "candidates": ranked[:3]}

    # ------------------------------------------------------------------ helpers
    def _best_action_match(self, rule_action, model):
        """Interface-compatible helper: label plus the raw similarity.

        The successor deliberately exposes the raw similarity here rather than a
        decision score, because in v2 the decision comes from the match tier.
        """
        best = self.action_match(rule_action, model).get("best")
        if not best:
            return (None, 0.0)
        return (best["label"], float(best["raw_similarity"]))

    @staticmethod
    def _required_summary(required: dict) -> dict:
        return {"text": required["text"], "normalized": required["normalized"],
                "predicate": required["predicate"],
                "objects": sorted(required["objects"]),
                "object_relation_support": required.get("object_relation_support"),
                "numerals": sorted(required["numerals"]),
                "negated": required["negated"]}

    @staticmethod
    def _ranked(candidates: list[dict]) -> list[dict]:
        return sorted(candidates, key=lambda c: (-c["raw_similarity"], c["activity_id"]))

    def _mapped(self, winner: dict, candidates: list[dict], tier: str, required: dict) -> dict:
        winner = {**winner, "match_tier": tier, "chosen_by": "match tier"}
        return {"mapped": True, "reason": None, "match_tier": tier,
                "tier_reason": match_policy()["tiers"][tier], "best": winner,
                "required": self._required_summary(required),
                "candidates": self._ranked(candidates)[:3]}

    def _undetermined(self, candidates: list[dict], ids: list[str], tier: str,
                      tier_reason: str, required: dict) -> dict:
        """Under-determined: keep v1's interface reason so the inherited checks
        treat the requirement as unobservable, and record the precise cause."""
        tied = [c for c in candidates if c["activity_id"] in set(ids)]
        return {"mapped": False, "reason": _AMBIGUOUS_REASON, "match_tier": tier,
                "tier_reason": tier_reason, "best": self._ranked(tied)[0],
                "undetermined_activity_ids": sorted(ids),
                "required": self._required_summary(required),
                "candidates": self._ranked(tied)[:3]}

    @staticmethod
    def _decide_candidate(candidate: dict, candidates: list[dict], required: dict) -> str:
        """Per-candidate accept/reject reason, recorded for traceability."""
        if candidate["exact_label"]:
            return "exact_label_match"
        if candidate["match_tier"] == TIER_AGREEMENT:
            return "same predicate with identical object evidence"
        if candidate["match_tier"] == TIER_CONFLICT:
            return "rejected: same predicate with conflicting object evidence"
        if candidate["match_tier"] == TIER_PARTIAL:
            return "undetermined: partial object overlap"
        return "below the evidence tiers: frozen similarity only"
