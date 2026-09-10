# -*- coding: utf-8 -*-
"""Stage 3 action representation and matching successor (v3).

Scope: **action representation and candidate matching only**.  This module
subclasses ``EvidenceChecksV2`` (which subclasses the committed
``EvidenceChecks``) and overrides ``action_match`` plus its own helpers.  The
executor check, the order check, the unknown aggregation, the metric logic, the
frozen ``SunScorer``, the similarity backend, the thresholds and the installed
NLP model are inherited unchanged.  ``EvidenceChecks`` v1 and
``s3_action_matching_v2`` stay byte-identical.

Why v2 was not enough (all four confirmed on the stored per-item artefacts):

* **A - nested actions were dropped.**  ``Add "existence of the right to rectify
  of personal data"`` and its two distractors ``...right to access...`` /
  ``...right to erase...`` all reduced to ``predicate=add`` with objects
  ``{datum, existence, right}``: the words that decide the meaning (``rectify`` /
  ``access`` / ``erase``) are verbs in an ``acl`` slot and were filtered out, so
  two different candidates looked identical.
* **B - the relation between actions was flattened.**  ``Stop running BPs using
  withdrawn data`` and ``Stop using withdrawn data`` were compared as two word
  bags (``{bp, datum}`` vs ``{datum}``); the structure "stop -> running -> BPs ->
  using -> withdrawn data" was not represented.
* **C - one non-matching candidate vetoed the whole match.**  With
  ``Examine package`` alone, the requirement ``Inspect package`` matched through
  the frozen similarity path; adding the unrelated ``Inspect furniture`` turned
  the whole result into a conflict.
* **D - identical word sets hid reversed roles.**  ``Transfer money from Alice to
  Bob`` and ``Transfer money from Bob to Alice`` had the same object set and were
  reported as agreeing.

Structured action record (small, dependency based, with source spans):

* main predicate (head verb, or the first content token when no verb is tagged);
* object content (nominal tokens outside subject-like slots, verbs, stopwords and
  the predicate itself);
* **nested actions**: every non-head verb in ``xcomp/acl/advcl/ccomp/relcl/conj``
  with its own object content and its slot label - this is what keeps
  ``rectify`` / ``access`` / ``erase`` and ``running`` / ``using`` comparable;
* **roles**: every prepositional role marker with its bound filler content
  (``from: {alice}``, ``to: {bob}``), which is what detects reversed roles;
* negation, numerals and every content span, so each element is checkable in the
  original label.

Candidate verdicts (three-way, evidence recorded):

* ``satisfied``      - predicate agrees, closed-class content, roles, nested
  actions and object coverage all agree;
* ``not_satisfied``  - explicit structural difference: negation, numerals,
  a role marker bound to different content, a nested action slot filled by a
  different action, or object content that differs with no similarity support
  between the differing terms;
* ``undetermined``   - the requirement's own content is simply absent
  (omission), the differing terms are similar enough that lexical equivalence is
  possible, or a role marker is missing; the missing/unparsed component is named.

Global rules (frozen before the panel was scored):

1. one unique exact label match still wins over every approximate match; several
   activity ids with identical labels stay unknown (never picked by id);
2. a non-matching candidate excludes only itself - a satisfied candidate is
   never vetoed by another candidate, so an unrelated activity cannot break a
   match that has sufficient evidence;
3. a requirement counts as satisfied if at least one candidate satisfies it
   (existential, as in the frozen Definition 5);
4. explicit non-satisfaction is reported only when every predicate-agreeing
   candidate is an explicit non-satisfier; if any of them is undetermined the
   result stays unknown;
5. no GDPR vocabulary, no rectification/access/erasure rule, no BP special case,
   no sample-id or target-label whitelist, and no synonym list: differences are
   judged with the existing similarity backend and gamma.
"""

from __future__ import annotations

from bpc_hybrid.s3_action_matching_v2 import EvidenceChecksV2

METHOD = "s3_action_matching@3.0.0"
METHOD_ID = "evidence_checks_v3_action_structure"
BASE_METHOD = "s3_action_matching@2.0.0"
MODIFICATION_SCOPE = "action representation and candidate matching only"

_AMBIGUOUS_REASON = "ambiguous_action_mapping"

TIER_EXACT = "exact_label"
TIER_EXACT_TIE = "exact_label_tie"
TIER_STRUCTURE = "structure_satisfied"
TIER_SIMILARITY = "similarity_satisfied"
TIER_NOT_SATISFIED = "structure_not_satisfied"
TIER_UNDETERMINED = "structure_undetermined"
TIER_BELOW_GAMMA = "no_candidate_above_gamma"
TIER_NO_ACTIONS = "no_process_actions"

NESTED_DEPS = {"xcomp", "acl", "advcl", "ccomp", "relcl", "conj"}
OBJECT_RELATIONS = {"dobj", "pobj", "attr", "oprd"}
NOMINAL_POS = {"NOUN", "PROPN", "NUM"}

VERDICT_SATISFIED = "satisfied"
VERDICT_NOT_SATISFIED = "not_satisfied"
VERDICT_UNDETERMINED = "undetermined"


def match_policy() -> dict:
    """The frozen v3 policy, for the manifest and diagnostics."""
    return {
        "method": METHOD,
        "base_method": BASE_METHOD,
        "modification_scope": MODIFICATION_SCOPE,
        "representation": {
            "predicate": "head verb lemma, else first content token lemma",
            "objects": "nominal tokens outside subject-like slots, verbs, stopwords, "
                       "and the predicate itself",
            "nested_actions": "non-head verbs in " + "/".join(sorted(NESTED_DEPS)) +
                              " with their own object content and slot label",
            "roles": "prepositional role markers with the nominal content bound to them",
            "closed_class": "negation and numerals",
            "spans": "every element carries its character span in the source label",
        },
        "candidate_verdicts": {
            VERDICT_SATISFIED: "predicate agrees and closed-class content, roles, nested "
                               "actions and object coverage all agree",
            VERDICT_NOT_SATISFIED: "explicit structural difference: negation, numerals, a "
                                   "role bound to different content, a nested slot filled by "
                                   "a different action, or object content differing with no "
                                   "similarity support between the differing terms",
            VERDICT_UNDETERMINED: "the requirement's own content is absent, the differing "
                                  "terms are similar enough that equivalence is possible, or "
                                  "a role marker is missing; the missing component is named",
        },
        "global_rules": [
            "unique exact match wins; identical labels on several ids stay unknown",
            "a non-matching candidate excludes only itself and never vetoes a satisfied one",
            "a requirement is satisfied if at least one candidate satisfies it",
            "explicit non-satisfaction is reported only when every predicate-agreeing "
            "candidate is an explicit non-satisfier; any undetermined candidate keeps it unknown",
            "predicate identity is lexical (equal lemmas); verb variation between whole labels "
            "is decided by the frozen whole-label similarity path and gamma",
            "subordinate-clause subjects count as content; the subject-like exclusion only "
            "keeps a mis-tagged main action word out of the main clause objects",
            "the whole-label similarity path may satisfy a requirement only when the candidate "
            "describes an action (verb predicate), unless the requirement is not an action "
            "phrase either",
            "when the requirement's own content could not be parsed the comparison is "
            "undetermined, never satisfied",
        ],
        "forbidden": [
            "no GDPR vocabulary or object list",
            "no rectification/access/erasure rule and no BP special case",
            "no sample-id special cases or target-label whitelist",
            "no synonym list",
            "no ordering by activity id to settle identical labels",
            "no use of the frozen target id inside matching",
        ],
    }


class EvidenceChecksV3(EvidenceChecksV2):
    """v2 checker with a structured action representation and comparison."""

    method_id = METHOD_ID

    def __init__(self, sim, tau, gamma, theta, nlp):
        super().__init__(sim, tau, gamma, theta, nlp=nlp)
        self._structure_cache: dict[str, dict] = {}

    # ------------------------------------------------------------- structure
    def _structure(self, text: str) -> dict:
        cached = self._structure_cache.get(text)
        if cached is not None:
            return cached
        base = super()._label_evidence(text)
        doc = self.nlp(text)
        tokens = [token for token in doc if not token.is_punct and not token.is_space]
        head = self._head_token(tokens, base.get("predicate"))
        owner = self._nearest_verb_owner(tokens)
        clause_owner = self._nearest_clause_head(tokens)
        nested = []
        for token in tokens:
            if token is head or token.pos_ != "VERB" or token.dep_ not in NESTED_DEPS:
                continue
            nested.append({
                "verb": token.lemma_.casefold(),
                "objects": self._owned_objects(tokens, owner, token),
                "slot": token.dep_,
                "span": [token.idx, token.idx + len(token.text)],
                "surface": token.text,
            })
        nested.sort(key=lambda item: (item["verb"], item["slot"], item["span"][0]))
        roles: dict[str, set[str]] = {}
        role_spans: dict[str, list[list[int]]] = {}
        for token in tokens:
            if token.dep_ != "prep" or token.pos_ != "ADP":
                continue
            key = token.lemma_.casefold()
            fillers = self._role_fillers(token)
            if not fillers:
                continue
            roles.setdefault(key, set()).update(fillers)
            role_spans.setdefault(key, []).append([token.idx, token.idx + len(token.text)])
        objects = set(base["objects"])
        # Subordinate-clause subjects are content: the subject-like exclusion exists
        # only to keep a mis-tagged main action word out of the main clause objects.
        for token in tokens:
            if token.pos_ not in NOMINAL_POS or token.is_stop:
                continue
            if token.dep_ not in {"nsubj", "nsubjpass", "csubj"}:
                continue
            owner_index = clause_owner.get(token.i)
            if owner_index is None or (head is not None and owner_index == head.i):
                continue
            objects.add(token.lemma_.casefold())
        accounted = set(objects)
        for item in nested:
            accounted.update(item["objects"])
        for fillers in roles.values():
            accounted.update(fillers)
        unparsed = sorted(lemma for lemma in
                          {token.lemma_.casefold() for token in tokens
                           if token.pos_ in NOMINAL_POS and not token.is_stop}
                          - accounted)
        structure = {
            **base,
            "text": text,
            "nested": nested,
            "roles": {key: sorted(value) for key, value in sorted(roles.items())},
            "role_spans": role_spans,
            "unparsed_content": unparsed,
            "object_spans": self._object_spans(tokens, objects),
            "has_verb_predicate": bool(head is not None and head.pos_ == "VERB"),
        }
        self._structure_cache[text] = structure
        return structure

    def _head_token(self, tokens, predicate):
        if predicate:
            for token in tokens:
                if token.lemma_.casefold() == predicate:
                    return token
        return None

    @staticmethod
    def _nearest_clause_head(tokens) -> dict[int, int]:
        """Nearest verb or auxiliary above each nominal: its clause head."""
        owner: dict[int, int] = {}
        for token in tokens:
            if token.pos_ not in NOMINAL_POS or token.is_stop:
                continue
            for ancestor in token.ancestors:
                if ancestor.pos_ in {"VERB", "AUX"}:
                    owner[token.i] = ancestor.i
                    break
        return owner

    @staticmethod
    def _nearest_verb_owner(tokens) -> dict[int, int]:
        """Map each nominal token index to the index of the closest verb above it."""
        owner: dict[int, int] = {}
        for token in tokens:
            if token.pos_ not in NOMINAL_POS or token.is_stop:
                continue
            for ancestor in token.ancestors:
                if ancestor.pos_ == "VERB":
                    owner[token.i] = ancestor.i
                    break
        return owner

    @classmethod
    def _owned_objects(cls, tokens, owner, verb) -> list[str]:
        """Objects governed by one verb, excluding deeper nested actions."""
        found = []
        for token in tokens:
            if token.pos_ not in NOMINAL_POS or token.is_stop:
                continue
            if owner.get(token.i) != verb.i:
                continue
            if token.dep_ in {"nsubj", "nsubjpass", "csubj", "npadvmod"}:
                continue
            found.append(token.lemma_.casefold())
        return sorted(dict.fromkeys(found))

    @staticmethod
    def _role_fillers(prep_token) -> list[str]:
        """Content bound to one prepositional role marker.

        The filler is the complement of *this* preposition; content belonging to a
        deeper preposition (``from Alice to Bob`` -> ``to`` owns ``Bob``) is not
        absorbed by the outer marker.
        """
        complement = None
        for child in prep_token.children:
            if child.dep_ in OBJECT_RELATIONS:
                complement = child
                break
        if complement is None:
            return []
        found = []
        for token in complement.subtree:
            if token is complement:
                if token.pos_ in NOMINAL_POS and not token.is_stop:
                    found.append(token.lemma_.casefold())
                continue
            if token.pos_ not in NOMINAL_POS or token.is_stop:
                continue
            deeper_prep = False
            for ancestor in token.ancestors:
                if ancestor is complement:
                    break
                if ancestor.pos_ == "ADP" and ancestor.dep_ == "prep":
                    deeper_prep = True
                    break
            if deeper_prep:
                continue
            found.append(token.lemma_.casefold())
        return sorted(dict.fromkeys(found))

    @staticmethod
    def _object_spans(tokens, objects) -> dict[str, list[int]]:
        spans: dict[str, list[int]] = {}
        for token in tokens:
            lemma = token.lemma_.casefold()
            if lemma in objects and lemma not in spans:
                spans[lemma] = [token.idx, token.idx + len(token.text)]
        return spans

    # -------------------------------------------------------------- comparison
    def _verb_agrees(self, left: str, right: str) -> bool:
        """Predicate identity is lexical.

        A single verb lemma compared through the frozen backend is not a reliable
        equivalence signal (the backend has no static vectors), so verbs agree only
        when their lemmas are equal.  Lexical variation between whole labels is
        handled by the frozen whole-label similarity path and gamma, exactly as the
        previous releases did.
        """
        return left == right

    def _term_support(self, required_terms, candidate_terms) -> float:
        """Best similarity support between two differing term sets."""
        best = 0.0
        for left in required_terms:
            for right in candidate_terms:
                best = max(best, float(self.sim.text_pair(left, right)))
        return best

    def _compare(self, required: dict, candidate: dict) -> dict:
        reasons: list[dict] = []
        evidence: dict = {}
        predicate_agrees = (required["predicate"] is not None
                            and candidate["predicate"] is not None
                            and self._verb_agrees(required["predicate"], candidate["predicate"]))
        if not predicate_agrees:
            return {"verdict": VERDICT_UNDETERMINED, "predicate_agrees": False,
                    "reasons": [{"code": "predicate_not_equivalent"}], "evidence": {}}

        if not required["objects"] and required["unparsed_content"]:
            # The requirement's own content could not be parsed: no structure may be
            # fabricated for it, so the comparison is not decidable.
            return {"verdict": VERDICT_UNDETERMINED, "predicate_agrees": True,
                    "reasons": [{"code": "requirement_content_not_parsed",
                                 "unparsed_content": required["unparsed_content"]}],
                    "evidence": {}}

        if required["numerals"] != candidate["numerals"]:
            reasons.append({"code": "numeral_difference",
                            "required": sorted(required["numerals"]),
                            "candidate": sorted(candidate["numerals"])})
        if required["negated"] != candidate["negated"]:
            reasons.append({"code": "negation_difference",
                            "required": required["negated"], "candidate": candidate["negated"]})

        role_evidence = []
        for key, fillers in sorted(required["roles"].items()):
            if key in candidate["roles"]:
                candidate_fillers = set(candidate["roles"][key])
                missing = sorted(set(fillers) - candidate_fillers)
                entry = {"role": key, "required": fillers, "candidate": sorted(candidate_fillers),
                         "span": required["role_spans"].get(key)}
                if missing:
                    entry["missing_fillers"] = missing
                    role_evidence.append(entry)
                    reasons.append({"code": "role_content_difference", **entry})
                else:
                    entry["missing_fillers"] = []
                    role_evidence.append(entry)
            else:
                role_evidence.append({"role": key, "required": fillers, "candidate": [],
                                      "missing_fillers": fillers, "role_absent": True,
                                      "span": required["role_spans"].get(key)})
                reasons.append({"code": "role_absent", "role": key, "required": fillers})
        evidence["roles"] = role_evidence

        nested_evidence = []
        for item in required["nested"]:
            match = None
            for other in candidate["nested"]:
                if not self._verb_agrees(item["verb"], other["verb"]):
                    continue
                if set(item["objects"]) <= set(other["objects"]):
                    match = other
                    break
            entry = {"required_action": item, "matched": match is not None}
            if match is not None:
                entry["candidate_action"] = match
                nested_evidence.append(entry)
                continue
            contained = [other for other in candidate["nested"]
                         if self._nested_component_of(other, required["nested"])]
            if contained:
                entry["candidate_actions"] = contained
                entry["containment"] = True
                nested_evidence.append(entry)
                reasons.append({"code": "nested_action_component_containment",
                                "required_action": item,
                                "candidate_actions": contained})
            else:
                same_slot = [other for other in candidate["nested"] if other["slot"] == item["slot"]]
                entry["candidate_actions"] = same_slot or candidate["nested"]
                entry["substituted_in_slot"] = item["slot"]
                nested_evidence.append(entry)
                reasons.append({"code": "nested_action_substituted",
                                "required_action": item,
                                "candidate_actions": same_slot or candidate["nested"],
                                "slot": item["slot"]})
        evidence["nested"] = nested_evidence

        required_objects = set(required["objects"])
        candidate_objects = set(candidate["objects"])
        missing_objects = sorted(required_objects - candidate_objects)
        extra_objects = sorted(candidate_objects - required_objects)
        object_entry = {"required_objects": sorted(required_objects),
                        "candidate_objects": sorted(candidate_objects),
                        "required_only": missing_objects,
                        "candidate_only": extra_objects,
                        "required_object_spans": required.get("object_spans")}
        if missing_objects:
            if not extra_objects:
                object_entry["difference_kind"] = "required_content_absent"
                reasons.append({"code": "required_object_content_absent", **object_entry})
            else:
                support = self._term_support(missing_objects, extra_objects)
                object_entry["term_similarity_support"] = round(support, 4)
                if support >= self.gamma:
                    object_entry["difference_kind"] = "possibly_equivalent_terms"
                    reasons.append({"code": "object_terms_possibly_equivalent", **object_entry})
                else:
                    object_entry["difference_kind"] = "explicit_content_difference"
                    reasons.append({"code": "object_content_difference", **object_entry})
        evidence["objects"] = object_entry

        codes = {reason["code"] for reason in reasons}
        explicit = {"numeral_difference", "negation_difference", "role_content_difference",
                    "nested_action_substituted", "object_content_difference"}
        if codes & explicit:
            verdict = VERDICT_NOT_SATISFIED
        elif reasons:
            verdict = VERDICT_UNDETERMINED
        else:
            verdict = VERDICT_SATISFIED
        return {"verdict": verdict, "predicate_agrees": True,
                "reasons": reasons, "evidence": evidence}

    def _nested_component_of(self, candidate_action: dict, required_nested: list[dict]) -> bool:
        """True when a candidate action also appears inside the requirement."""
        for item in required_nested:
            if not self._verb_agrees(item["verb"], candidate_action["verb"]):
                continue
            if set(candidate_action["objects"]) <= set(item["objects"]):
                return True
        return False

    # ---------------------------------------------------------------- matching
    def action_match(self, rule_action, model):
        required = self._structure(rule_action)
        candidates = []
        for activity in model.actions:
            label = activity.get("name", "")
            if not label:
                continue
            candidate = self._structure(label)
            comparison = self._compare(required, candidate)
            similarity = float(self.sim.text_pair(self._lemma(rule_action), self._lemma(label)))
            candidates.append({
                "activity_id": activity["id"],
                "label": label,
                "predicate_agrees": comparison["predicate_agrees"],
                "verdict": comparison["verdict"],
                "reasons": comparison["reasons"],
                "evidence": comparison["evidence"],
                "raw_similarity": similarity,
                "normalized_equal": candidate["normalized"] == required["normalized"],
                "has_verb_predicate": candidate["has_verb_predicate"],
            })
        if not candidates:
            return {"mapped": False, "reason": TIER_NO_ACTIONS, "match_tier": TIER_NO_ACTIONS,
                    "tier_reason": "no labelled process activity",
                    "required": self._summary(required), "candidates": []}

        exact_ids = sorted({c["activity_id"] for c in candidates if c["normalized_equal"]})
        if len(exact_ids) > 1:
            return self._undetermined(candidates, exact_ids, TIER_EXACT_TIE,
                                      "identical normalised labels on several activities",
                                      required)
        exact = [c for c in candidates if c["normalized_equal"]]
        if exact:
            return self._mapped(exact[0], candidates, TIER_EXACT, required)

        structural = [c for c in candidates if c["predicate_agrees"]]
        satisfied = [c for c in structural if c["verdict"] == VERDICT_SATISFIED]
        # The whole-label similarity path may satisfy a requirement only when the
        # candidate actually describes an action (a verb predicate), unless the
        # requirement itself is not an action phrase either; a noun-phrase label
        # sharing a word is not evidence that the required action is performed.
        satisfied += [c for c in candidates
                      if not c["predicate_agrees"] and c["raw_similarity"] > self.gamma
                      and (c["has_verb_predicate"] or not required["has_verb_predicate"])]
        if satisfied:
            winner = self._strongest(satisfied)
            tier = TIER_STRUCTURE if winner["predicate_agrees"] else TIER_SIMILARITY
            return self._mapped(winner, candidates, tier, required,
                                satisfied_ids=sorted({c["activity_id"] for c in satisfied}))

        if structural:
            undetermined = [c for c in structural if c["verdict"] == VERDICT_UNDETERMINED]
            if undetermined:
                winner = self._strongest(undetermined)
                return self._undetermined(
                    candidates, sorted({c["activity_id"] for c in undetermined}),
                    TIER_UNDETERMINED,
                    "at least one predicate-agreeing candidate cannot be decided: "
                    + self._reason_summary(winner),
                    required, focus=winner)
            winner = self._strongest(structural)
            return {"mapped": False, "reason": "requirement_evidence_not_satisfied",
                    "match_tier": TIER_NOT_SATISFIED,
                    "tier_reason": "every predicate-agreeing candidate shows an explicit "
                                   "structural difference: " + self._reason_summary(winner),
                    "best": winner, "required": self._summary(required),
                    "candidates": self._ranked(candidates)[:3],
                    "checked_activity_ids": sorted({c["activity_id"] for c in structural})}

        best = max(candidates, key=lambda c: (c["raw_similarity"], c["activity_id"]))
        if best["raw_similarity"] <= self.gamma:
            return {"mapped": False, "reason": TIER_BELOW_GAMMA, "match_tier": TIER_BELOW_GAMMA,
                    "tier_reason": f"no candidate reaches gamma; best raw similarity "
                                   f"{best['raw_similarity']:.4f}",
                    "best": best, "required": self._summary(required),
                    "candidates": self._ranked(candidates)[:3]}
        return self._mapped(best, candidates, TIER_SIMILARITY, required,
                            satisfied_ids=[best["activity_id"]])

    # ----------------------------------------------------------------- helpers
    def _strongest(self, items: list[dict]) -> dict:
        order = {VERDICT_SATISFIED: 0, VERDICT_UNDETERMINED: 1, VERDICT_NOT_SATISFIED: 2}
        return sorted(items, key=lambda c: (order.get(c["verdict"], 3),
                                            -c["raw_similarity"], c["activity_id"]))[0]

    @staticmethod
    def _reason_summary(candidate: dict) -> str:
        parts = []
        for reason in candidate["reasons"][:4]:
            code = reason["code"]
            if code == "nested_action_substituted":
                parts.append(f"required nested action {reason['required_action']['verb']!r} "
                             f"replaced in slot {reason['slot']!r}")
            elif code == "nested_action_component_containment":
                parts.append(f"required nested action {reason['required_action']['verb']!r} "
                             f"absent; the candidate action is a component of the requirement")
            elif code == "object_content_difference":
                parts.append(f"object content differs without similarity support "
                             f"({reason['required_only']} vs {reason['candidate_only']}, "
                             f"support {reason.get('term_similarity_support')})")
            elif code == "required_object_content_absent":
                parts.append(f"required object content absent ({reason['required_only']})")
            elif code == "object_terms_possibly_equivalent":
                parts.append(f"object terms may be equivalent ({reason['required_only']} vs "
                             f"{reason['candidate_only']}, support "
                             f"{reason.get('term_similarity_support')})")
            elif code == "role_content_difference":
                parts.append(f"role {reason['role']!r} bound to different content "
                             f"({reason['required']} vs {reason['candidate']})")
            elif code == "role_absent":
                parts.append(f"role {reason['role']!r} absent in the candidate")
            elif code in {"numeral_difference", "negation_difference"}:
                parts.append(code.replace("_", " "))
            else:
                parts.append(code)
        return "; ".join(parts) if parts else "no structural difference recorded"

    @staticmethod
    def _ranked(candidates: list[dict]) -> list[dict]:
        return sorted(candidates, key=lambda c: (-c["raw_similarity"], c["activity_id"]))

    @staticmethod
    def _summary(required: dict) -> dict:
        return {"text": required.get("text", required["normalized"]),
                "normalized": required["normalized"],
                "predicate": required["predicate"],
                "objects": sorted(required["objects"]),
                "nested": required["nested"],
                "roles": required["roles"],
                "numerals": sorted(required["numerals"]),
                "negated": required["negated"],
                "unparsed_content": required["unparsed_content"],
                "has_verb_predicate": required.get("has_verb_predicate")}

    def _mapped(self, winner: dict, candidates: list[dict], tier: str, required: dict,
                satisfied_ids=None) -> dict:
        winner = {**winner, "match_tier": tier, "chosen_by": "match tier"}
        return {"mapped": True, "reason": None, "match_tier": tier,
                "tier_reason": match_policy()["candidate_verdicts"].get(
                    VERDICT_SATISFIED, tier) if tier == TIER_STRUCTURE else
                f"mapped through {tier}",
                "best": winner,
                "satisfying_activity_ids": satisfied_ids or [winner["activity_id"]],
                "required": self._summary(required),
                "candidates": self._ranked(candidates)[:3]}

    def _undetermined(self, candidates: list[dict], ids: list[str], tier: str,
                      tier_reason: str, required: dict, focus: dict | None = None) -> dict:
        selected = [c for c in candidates if c["activity_id"] in set(ids)]
        focus = focus or self._strongest(selected)
        return {"mapped": False, "reason": _AMBIGUOUS_REASON, "match_tier": tier,
                "tier_reason": tier_reason, "best": focus,
                "undetermined_activity_ids": sorted(ids),
                "required": self._summary(required),
                "candidates": self._ranked(selected)[:3]}
