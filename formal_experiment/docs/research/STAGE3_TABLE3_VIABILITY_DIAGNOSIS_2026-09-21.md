# Stage 3 Table 3 viability diagnosis (2026-09-21)

**Status:** read-only diagnostic. Zero LLM/API calls. Zero writes to Gold,
panels, predictions or results. All three probes are tracked under
`formal_experiment/scripts/`.

**Purpose:** decide whether the paper's Table 3 can be built from the artifacts
that already exist, before spending any further effort on it.

**Bottom line:** the mutation benchmark is **sound** (30/30 mutations are
structurally detectable), the 33-item gold is **not a benchmark**, and the
reason current per-type scores are degenerate is the **detector's similarity
grounding**, not the data. See §5 for the layer separation and §8 for the
options.

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

**Important distinction.** The 0.8733 figure comes from
`outputs/reports/s35_sun_stage3_threshold_sensitivity_v1` and was measured on
the **33-item human violation gold**, not on the 30-item mutation panel. At
gamma=0.6 the best-observed setting there gives Missing 1.0 /
Incorrect-actor 0.7778 / Out-of-order 0.8421 with 4 unobservable. That result
therefore shows the *scorer* can discriminate on the 33-item set at a tuned
threshold; it does **not** show that the mutation panel is measurable. On the
mutation panel the same scorer yields 0/30 separable at every gamma in the
grid. The two panels must not be conflated, and the gamma=0.6 setting is
recorded in the project's own config as a *tested value*, not as a
pre-registered or transferable operating point.

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

## 5. The two failure layers must be separated (corrected finding)

An earlier reading of this diagnosis concluded the mutation panel itself was
defective. **That was wrong, and the correction matters.** The panel mutations
are genuine and every one of them is detectable from the BPMN alone:

`scripts/diagnose_stage3_mutation_detectability_v1.py` compares each mutated
BPMN against its unmutated original using the canonical Stage 1 Process Record,
with **no detector and no lexical similarity involved**:

| target type | structurally detectable |
|---|---|
| missing_action | **10/10** (target activity removed, no activity added) |
| incorrect_actor | **10/10** (target activity's lane membership changes) |
| out_of_order | **10/10** (direct edges and reachability change; the manifest node pair's ordering genuinely reverses) |

So the correct decomposition of the "0/30 separable" result in §3 is:

| Layer | Question | Verdict |
|---|---|---|
| **Structural** | does the mutation actually change the process? | **yes, 30/30** |
| **Lexical grounding** | can a similarity baseline map the rule's actions onto the process activities? | **no** — similarity falls below gamma |
| **Measurability with the frozen scorer** | therefore, is the benchmark usable *with that scorer*? | **no, 0/30** |

The defect is in the **detector's grounding path**, not in the benchmark. This
is a materially better position for the paper: the benchmark can be used as
soon as a correctly grounded detector exists.

## 6. Why the grounding fails, in one sentence

The frozen Sun reconstruction grounds rule actions onto BPMN activities by
embedding similarity with a high threshold. GDPR article wording ("notify the
supervisory authority without undue delay") and BPMN activity labels ("Send
notification") share almost no surface vocabulary, so the mapping never clears
gamma — which is why the originals scored as violating and why out_of_order
had a zero denominator. A detector that consumes the Stage 2 Rule Record's
already-extracted `actor_action_map` / `order_relations` **by identity**
instead of re-deriving them by similarity does not have this failure mode.



## 7. The relation annotations are still incomplete (separate issue)

Independently of the above, the published Gold Stage 3 Rule Records
(`data/gold/stage3/gdpr7_gold_rule_records_v1.json`, 9 rules / 74 sentences /
92 normative items) carry both relation fields but:

- `actor_action_map`: non-empty on only **38 of 92** nodes;
- `order_relations`: non-empty on **0 of 92** nodes.

The project's central mechanism is that a better Stage 2 Rule Record carries
`actor_action_map` and `order_relations` that improve Stage 3 compliance
checking. For `out_of_order` the Gold currently holds **no ordering
annotation at all** to compare against, and the development adapter that does
extract relations produces 200 of them that never ground. This matches the
recorded formal Oracle result (out_of_order item denominator 0;
incorrect_actor unobservable on 11/11).

Note the distinction: this is a **Gold evidence gap for one field**, not a
defect in the mutation panel.

## 8. Options (decision required)

| # | Option | Cost | What the paper may claim |
|---|---|---|---|
| A | Build a correctly grounded three-type detector that consumes `actor_action_map` / `order_relations` by identity from the Stage 2 Rule Record, and add the missing order-relation annotation. The benchmark itself is already sound (30/30 structurally detectable), so no new BPMN work is needed. | Medium-high (new detector + one field of annotation) | "Our method outperforms predecessors on three-type compliance checking." |
| B | Keep Table 3 as a **framework + feasibility** table: report that the similarity-based predecessors' per-type F1 is degenerate on this corpus, present the two-layer diagnostic as the explanation, and report the three-type results as exploratory. | Low | "We show why existing detection is degenerate here and what a measurable benchmark requires." Honest, publishable, no superiority claim. |
| C | Drop three-type detection from the paper's claims; report Stage 3 only as a linkage/feasibility study and point to future work. | Lowest | Stage 1 + Stage 2 contributions only. |

**Do not** select a threshold or a backend in order to make one method look
better; the sweep above shows no such setting exists anyway, and choosing one
post hoc would be result-driven selection.

## 9. Reproduction

```powershell
cd formal_experiment
python -W ignore scripts/diagnose_stage3_table3_viability_v1.py        # scorer separability
python -W ignore scripts/diagnose_stage3_table3_threshold_rootcause_v1.py  # sweep + root cause
python -W ignore scripts/diagnose_stage3_mutation_detectability_v1.py  # structural detectability
```

All three read only `data/development/stage3_synth/`,
`data/development/human_review/stage3_gold_inference_v1.json`,
`configs/sun_stage3_development_v1.json` and the frozen GDPR7 BPMN files.
