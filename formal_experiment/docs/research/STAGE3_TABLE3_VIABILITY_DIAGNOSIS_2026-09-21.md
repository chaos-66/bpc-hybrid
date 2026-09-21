# Stage 3 Table 3 viability diagnosis (2026-09-21)

**Status:** read-only diagnostic. Zero LLM/API calls. Zero writes to Gold,
panels, predictions or results. Both probes are scratch scripts under
`formal_experiment/.tmp/`.

**Purpose:** decide whether the paper's Table 3 can be built from the artifacts
that already exist, before spending any further effort on it.

---

## 1. What Table 3 needs

A per-type violation-detection comparison (missing_action / incorrect_actor /
out_of_order) between predecessor methods (Winter et al. 2020, Sun et al. 2024)
and this project's method, on a benchmark where the Ground Truth is the
consequence of a real structural BPMN mutation, with compliant controls so
that precision / specificity has a denominator.

## 2. The 33-item gold cannot support this (confirmed)

`data/gold/stage3/stage3_violation_gold_v1.json` contains 33 items constructed
as 11 rule-process pairs x 3 check types. For all 33 items
`decision_violation_type` is a verbatim copy of `check_type`, and
`decision_evidence` is a prose template of the form
`"<article citation> ... candidate: <question>?"`. No BPMN was mutated; the
file records no mutation, no variant path and no target activity.

This reproduces the earlier analysis: **check type != ground-truth violation
type**. The file is a *check-point decision set*, not a performance benchmark.
It is therefore retired from the Table 3 role in the active documents and kept
as development provenance.

## 3. The 30-item mutation panel is real but NOT measurable

`synthetic_controlled_error_extension_v1.json` is a genuine artifact: 30
variants (10 per type) built by `scripts/build_s3_error_injection_v1.py` using
real XML edits (delete task + rewire flows; move task to an injected lane;
swap sequence-flow ends), each with `validation_checks.status == "passed"` and
per-item `mutation_config.diff`. All four predecessor methods already have
predictions on it.

It nonetheless **cannot** support Table 3, for a reason that no method
comparison can fix. Using the frozen Sun reconstruction (`SunScorer`) at its
config primary thresholds (tau=0.8, gamma=0.8, theta=0.8), scoring **both** the
mutated BPMN and its **unmutated original**:

| target type | mutated observable | cleanly separable | original already violates |
|---|---|---|---|
| missing_action | 10/10 | **0/10** | 10/10 |
| incorrect_actor | **2/10** | **0/10** | 2/2 observable |
| out_of_order | 10/10 | **0/10** | 10/10 |

A benchmark item is only usable when the detector can *observe* the type, the
original process is *compliant*, and the mutation makes it *violate*. **Zero of
30 items satisfy that.** Every item is already scored as a violation before any
mutation is applied, so the panel measures nothing about the mutation.

Reported method differences on this panel are therefore not method skill. This
is consistent with the frozen comparison's own numbers, where
incorrect_actor and out_of_order F1 are 0.0 for Winter and BM25 and the
"easiest type" is simply the one whose violation fraction saturates at 1.0.

## 4. This is structural, not a threshold artifact

Sweeping gamma over the config's own declared sweep grid (tau=0.8, theta=0.8):

| gamma | missing_action | incorrect_actor | out_of_order | total |
|---|---|---|---|---|
| 0.2 | 0/10 | 0/10 | 0/10 | 0/30 |
| 0.4 | 1/10 | 0/10 | 0/10 | 1/30 |
| 0.6 | 0/10 | 0/10 | 0/10 | 0/30 |
| 0.8 | 0/10 | 0/10 | 0/10 | 0/30 |
| 0.9 | 0/10 | 0/10 | 0/10 | 0/30 |

No threshold setting makes the panel separable. The user's own earlier note
that Sun reaches Macro-F1 0.8733 at gamma=0.6 does not transfer to this panel:
at gamma=0.6 the separable count here is still 0/30.

**Root causes, measured:**

- **out_of_order is structurally unobservable.** The detector's denominator on
  the mutated BPMN is **0 for all 10 items**. The development rule adapter does
  extract order relations (200 over the 25 matching pairs), but *none of them
  maps to a process action pair* above gamma. A reversal that never maps cannot
  be detected. This is exactly why every method reports out_of_order F1 = 0.0.
- **missing_action is dominated by rule/process vocabulary mismatch.** The
  mutation *does* change the model (action count drops by exactly one in 10/10
  items), but the rule side demands 2-13 actions whose similarity to the BPMN
  activity labels falls below gamma regardless, so the violation fraction is
  already 0.833-1.000 on the original.
- **incorrect_actor is mostly unobservable.** 8 of 10 mutated items fail the
  precondition with reason `action_mapping_below_gamma`; the 2 that are
  observable are already violations on the original.

## 5. The deeper blocker: the relation annotations are empty

The published Gold Stage 3 Rule Records
(`data/gold/stage3/gdpr7_gold_rule_records_v1.json`, 9 rules / 74 sentences /
92 normative items) carry both relation fields, but:

- `actor_action_map`: non-empty on only **38 of 92** nodes;
- `order_relations`: non-empty on **0 of 92** nodes.

The paper's central mechanism is that a better Stage 2 Rule Record carries
`actor_action_map` and `order_relations` that improve Stage 3 compliance
checking. For `out_of_order` the Gold *evidence for that mechanism does not
exist*: there is no ordering annotation anywhere to compare against. This also
explains the recorded formal Oracle result, where out_of_order is
"aggregate-observable but item denominator 0" and incorrect_actor is
unobservable on 11/11 items.

## 6. What this means for the paper

1. Table 3 as specified (three-type F1, predecessors vs ours, real mutations
   plus compliant controls) **cannot be produced from existing artifacts.**
2. The obstruction is not method quality. It is that the rule-to-process
   grounding path — lexical/embedding similarity between rule text and BPMN
   activity labels — does not establish the relations the three types need on
   this corpus.
3. Fixing it requires either (a) annotating order relations and actor-action
   bindings in the Stage 3 Gold, which is a new human-annotation task, or
   (b) changing the grounding so that relations are consumed by identity from
   the Rule Record instead of being re-derived by similarity. Option (b) is
   also the only version in which "our Stage 2 Rule Record improves Stage 3"
   is a genuine mechanism rather than a correlation.

## 7. Recommended options (decision required)

| # | Option | Cost | What the paper may claim |
|---|---|---|---|
| A | Build a gold-referenced grounding layer: consume `actor_action_map` / `order_relations` by identity from the Rule Record, then detect the three types; re-annotate the missing order relations. | Highest (new annotation + new detector) | "Our method outperforms predecessors on three-type compliance checking." Requires the benchmark to first pass the separability test above. |
| B | Keep Table 3 as a **framework + feasibility** table: report that predecessors' per-type F1 is degenerate on this corpus, present the separability diagnostic as the explanation, and report the three-type results as exploratory. | Low | "We show why existing detection is degenerate here and what a measurable benchmark requires." Honest, publishable, no superiority claim. |
| C | Drop three-type detection from the paper's claims; report Stage 3 only as a linkage/feasibility study and point to future work. | Lowest | Stage 1 + Stage 2 contributions only. |

**Do not** select a threshold or a backend in order to make one method look
better; the sweep above shows no such setting exists anyway, and choosing one
post hoc would be result-driven selection.

## 8. Reproduction

```powershell
cd formal_experiment
python -W ignore scripts/diagnose_stage3_table3_viability_v1.py      # separability
python -W ignore scripts/diagnose_stage3_table3_threshold_rootcause_v1.py  # sweep + root cause
```

Both read only `data/development/stage3_synth/`,
`data/development/human_review/stage3_gold_inference_v1.json`,
`configs/sun_stage3_development_v1.json` and the frozen GDPR7 BPMN files.
