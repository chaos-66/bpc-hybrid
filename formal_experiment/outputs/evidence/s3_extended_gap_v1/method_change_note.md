# S3.9-EXT v3 gap analysis and repair — method change note (v1)

Scope: development-only synthetic four-type panel v2 (40 variants + 40 controls),
zero API. No Gold, panel label, frozen prediction or historical result is changed.

## 1. The measured cells

| cell | matching path | action gamma | variant correct/40 | 4-type macro-F1 | control FP/40 | both-sides-correct/40 |
|---|---|---|---|---|---|---|
| Winter-style (frozen) | label argmax on raw text | 0.4 | 17 | 0.4738 | 20 | 9 |
| orig+0.4 (re-derived, identical to the frozen arm) | label argmax on raw text | 0.4 | 17 | 0.4738 | 20 | 9 |
| Sun-style (frozen) | label argmax on raw text | 0.8 | 10 | 0.2381 | 5 | 7 |
| v3 (existing) | v3 structured match | 0.8 | 10 | 0.2273 | 8 | 4 |
| v3 + 0.4 (new diagnostic arm) | v3 structured match | 0.4 | 10 | 0.2273 | 8 | 4 |
| v3 + 0.4 repaired (new final arm) | v3 match + one action resolution | 0.4 | 19 | 0.5233 | 20 | 11 |

* The re-derived orig+0.4 arm reproduces the frozen Winter arm on every
  decision-relevant field, so the pre-existing cells and the two new arms are
  measured by one runner, one evaluator and one metric module.
* **The threshold is not the cause of the v3 gap — it is inert in the v3 path.**
  The 0.4 diagnostic arm differs from the existing 0.8 v3 arm in the recorded
  gamma only: every score, every observability flag, every action-localization
  record and every final prediction is identical (the two files differ only in
  the `action_mapping_gamma` provenance field). Migrating Winter's frozen 0.4
  into the v3 path therefore changes nothing at all.
* **The cause is v3's structured action match.** At the same 0.4, the
  label-argmax path maps 27/40 rule actions; v3 maps 10/40 (the ten exact-label
  prohibited insertions). v3 rejects 26 rows with `no_candidate_above_gamma` and
  4 with `structure_not_satisfied`, and — because `structure_not_satisfied` is
  decided by the structural comparison rather than by gamma — the same 30
  rejections occur at both gammas. The action gate of the condition /
  constraint / exception checks is that verdict, so those three types stay
  unobservable on the variant side and can never be detected.

## 2. Three confirmed defects

**D1 — a threshold applied to a score that is not on its scale.** The v3
adapter reports `candidate_max_similarity` as the `prohibited_action_present`
score. That value is a *lemmatised* similarity
(`EvidenceChecksV3.action_match` -> `self.sim.text_pair(self._lemma(...), self._lemma(...))`),
while the frozen formula (`configs/stage3_extended_violation_v2.json`) and the
frozen `gamma_ext = 0.5` were locked on the *raw* label similarity
`max sim(rule_action, process_activity)`. On this panel `syn_v2_prohibited_action_04`
scored 1.0000 raw and 0.5040 lemmatised, and `syn_v2_exception_not_handled_04`
scored 0.5080 raw and 0.5040 lemmatised: the same 0.5 cut lands on opposite
sides of the two scales.

**D2 — two different answers to "what does this action refer to".**
`prohibited_action` returned a score even when v3 did not localize — it fell
back to the raw candidate maximum and could report `violation = True` on a row
whose localization verdict was `not_satisfied`. That is how
`syn_v2_exception_not_handled_04` and `_05` became `prohibited_action_present`
predictions in the v3 arm. The same row's condition / constraint / exception
checks abstained, and the exact-contradiction gate compared the activity id of
one reference while the candidate surfaces had been built from another.

**D3 — a verification verdict used as a hard localization gate.** v3's
`structure_not_satisfied` answers "is the required action present". On this
panel it fires whenever the object content of a rule action differs from a
process label with term support below gamma, which is the normal case for a
legal sentence ("have the obligation to erase personal data without undue delay
where ...") against a process label ("Communication with data subject"). Used as
the anchor gate for the four-type evidence checks it removes every downstream
comparison.

## 3. What the repair inherits and what it changes

Inherited unchanged from the Winter/Sun-v3 lineage: the frozen panel and rule
binding, the six-element extractor, the four candidate surfaces
(`condition_candidates` / `constraint_candidates` / `exception_candidates` /
`action_candidates`), the four frozen formulas and their thresholds
(`gamma_ext = 0.5`; `score >= gamma_ext` for prohibition, `score > gamma_ext`
for the other three; the exact time-limit contradiction helper), the unified
five-class decision with its fixed type order, the evaluators, the observability
policy (unobservable is never hard-filled with 0.0/1.0), and v3's structured
action representation including its exact-label tier, nested actions, roles and
numeric/negation evidence.

Changed, one method per confirmed defect:

1. `prohibited_action_present` scores with the arm's declared raw-label formula
   `max sim(rule_action, process_activity)` (D1), and is observable exactly when
   at least one process activity exists to compare against. Its reported
   `violation` field is the score decision itself (D2 consistency).
2. One **action resolution** is used by every consumer — the score decision, the
   candidate surfaces, the evidence scores and the exact-contradiction gate
   (D2). It is v3's satisfying match when v3 has one, otherwise the arm's own
   label-argmax candidate, admitted only at or above the arm's action gamma
   (D3). When no activity can be resolved the row says so; it is never scored
   from an unresolvable action.
3. The numeric time-limit contradiction branch is reachable only through that
   same resolved activity and the same gamma (D2/D3).

The changes are general rules, not panel rules: no threshold was lowered or
searched (the diagnostic arm and the repair both use Winter's frozen 0.4 as the
action gamma; `gamma_ext` stays 0.5), no sample id, rule id, target activity id,
mutation description or expected label is read, and the repair adds no legal
vocabulary, no whitelist and no per-item switch. The unobservable /
not-satisfied / under-determined outcomes remain three distinct outcomes.

## 4. What the repair does not claim

* It does **not** show that v3's structured action match improves the four-type
  panel. At the same gamma and with the same evidence scope, the structural
  verdict no longer gates anything, and the per-type precision/recall of the
  repaired arm equals the Winter-style arm's. The measured contribution of the
  structured matcher on this panel is the exact-label tier it adds for
  prohibited-action insertions, plus the D2/D3 consistency it now has.
* The repaired arm's control false positives (20/40) are far above the old v3
  arm's (8/40). That is the D1 correction showing its cost: on the raw scale the
  four-type formula calls borderline label pairs violations, exactly as the
  Winter-style arm does. The false-positive level is a property of the frozen
  formula and `gamma_ext`, not of the repair; a different gamma_ext would be a
  new pre-registration, not a repair.
* Nothing here may be presented as native Winter or Sun capability. The four
  types remain project-defined, and this arm is a project extension arm.
