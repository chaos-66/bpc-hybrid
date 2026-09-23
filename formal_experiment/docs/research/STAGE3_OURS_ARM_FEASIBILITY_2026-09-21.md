# Stage 3 "Ours" arm feasibility: what the evidence now requires (2026-09-21)

**Status:** read-only analysis. Zero LLM/API calls. Zero writes to Gold, panels,
predictions or results.

**Question:** can a three-type Stage 3 detector be built that derives its
rule-to-process bindings from the **published Stage 2 Rule Record**, so the
paper can report an "Ours" row on the paired benchmark?

**Answer: not yet, and the missing piece is a human annotation — not code.**
The reasoning is a chain of four verified facts.

---

## 1. The benchmark carries no rule-action → activity annotation

`synthetic_controlled_error_extension_v1.json` gives each variant exactly these
fields:

```
variant_id, process_id, rule_id, mutation_type, expected_violation,
source_bpmn(+sha), variant_bpmn(+sha), target_activity_id,
mutation_config, validation_checks, generator_sha256
```

There is **no field naming the rule-side action that `target_activity_id`
realizes**, and both the rule text and the activity names are several spans
long, so the correspondence is not recoverable by construction. A detector
cannot prove "this BPMN activity discharges that rule action" — it can only
guess, and guessing is precisely the similarity path that fails (§3).

## 2. The Gold Rule Records hold actor-action links but no order relations

Read directly from the published Gold
(`data/gold/stage3/gdpr7_gold_rule_records_v1.json`, 9 rules / 74 sentences):

| Quantity | Value |
|---|---|
| clauses | 92 |
| clauses carrying actions | 70 (75 action spans) |
| clauses with a non-empty `actor_action_map` | **38** (38 links) |
| clauses with a non-empty `order_relations` | **0** (0 links) |

So `actor_action_map` exists for a minority of clauses, and
`order_relations` exists for none.

## 3. Lexical grounding is the thing that fails — measured

On the 60-item paired benchmark, with each arm's own frozen rule:

| Arm | Macro-F1 | Specificity | Exact type | Unobservable |
|---|---:|---:|---:|---:|
| `sun_reconstruction` | 0.3175 | 0.3333 | 12/30 | 16 |
| `winter_wrapper` | 0.2222 | 0.6000 | 10/30 | 0 |
| grounded reference (declared bindings) | 1.0000 | 1.0000 | 30/30 | 0 |

`out_of_order` F1 is **0.0 for both predecessors**. The gap is a *grounding*
effect, not algorithm quality.

## 4. The project's own formal pipeline already records this blocker

`outputs/reports/gdpr_3type_linkage_v1_direct_llm.md` (the real, promoted
Direct-LLM Stage 2 arm, 74 records), states verbatim:

- "order relations absent in capsule for rules: all nine ... (Definition-7
  input unavailable by contract; **never fabricated**)"
- "unobservable = 11 (by reason: `action_mapping_below_gamma`: 8,
  `stage2_empty_envelope`: 1, `incomplete_rule_actor_action_map`: 2)"
- `out_of_order` precision/recall/F1 = 0.0000

This is not a hypothesis about the new benchmark. It is what the **actual
Direct-LLM Stage 2 output** did on the original three-type evaluation: eight of
eleven incorrect-actor items were unobservable because the rule action could
not be mapped to a process action above gamma, and every item had no order
relation to check.

## 5. What this means

A real "Ours" detector needs, as **input**, a binding from each rule action to
the BPMN activity that discharges it. Today:

- the benchmark does not annotate it (§1);
- the Gold Rule Records partially annotate the actor side but not the order
  side (§2);
- deriving it lexically is the failing step (§3, §4).

Therefore the remaining work for the Table 3 "Ours" row is **authoring that
annotation**, not writing more detector code. Any attempt to fill it in
automatically would be the agent authoring its own Ground Truth — exactly what
the objective forbids ("no fabricated results").

## 5b. The mechanism itself works — measured (added 2026-09-21, round 5)

To make sure the conclusion above is not dodging solvable work, the detector
mechanism was tested directly
(`scripts/diagnose_stage3_binding_selfcheck_v1.py`, read-only):

| Check | Result |
|---|---|
| `out_of_order` pairs whose **control** is forward-ordered only | **10/10** |
| `out_of_order` pairs whose **variant** is the inversion | **10/10** |
| order relations available from the **Gold** Rule Records | **0** (0 of 92 clauses) |
| order relations available from the **real Direct-LLM capsule** | **0** (0 of 78 clauses) |

So `out_of_order` is decidable **from the process side alone** — the control is
ordered one way and the variant is its exact inversion. What is missing is
purely the **rule-side endpoint binding**: the rules carry no ordering
information anywhere, in either the Gold or the promoted Direct-LLM arm.

This is the tightest form of the argument. The detector needs exactly one
input that the evidence above does not supply. At this report's original date,
a blank 30-pair annotation surface was prepared. Update 2026-09-23: the user
completed candidate review; the retained result is
`data/development/stage3_synth/stage3_binding_human_decisions_v1.json`.
It still has 5 null actions, 8 null actors and 10 process-only order decisions,
and is not Binding Gold. The old annotation batch is archived; no old review
task should be resumed from this historical report. The detector still needs
complete, explicitly supplied bindings before those claims can be tested.

## 6. The three honest paths

| # | Path | What it needs | What the paper may claim |
|---|---|---|---|
| A1 | Annotate rule-action → BPMN-activity bindings (and rule order relations) for the 30 paired items, then build the grounded detector that consumes them. | Human annotation of 30 items × 3 types, plus the order relations for the 9 rules. | "Ours outperforms predecessors on three-type compliance checking." |
| A2 | Same annotation work, but restrict the claim to the types that are actually annotatable now: `missing_action` and `incorrect_actor` (both 10/10 structurally detectable and both fully grounded once actions are bound). Keep `out_of_order` explicitly out of scope. | Human annotation of the action bindings only. | "Ours outperforms predecessors on missing-action and incorrect-actor detection." |
| B | Publish Table 3 as a **framework + feasibility** table: the paired benchmark, the anti-degeneracy guarantee, the grounded upper bound, and the predecessor results, with the grounding requirement stated as the finding. | Nothing new. | "We show why existing detection is degenerate on this corpus and exactly what a measurable benchmark requires." |

Path B is fully supported by evidence that already exists and is committed.
Paths A1/A2 are the only routes to a superiority claim, and both are gated on
human annotation.

## 7. Reproduction

```powershell
cd formal_experiment
python -W ignore scripts/build_stage3_paired_benchmark_v1.py       # 60-item benchmark
python -W ignore scripts/run_stage3_grounded_checker_v1.py          # upper bound
python -W ignore scripts/run_stage3_predecessors_paired_v1.py       # predecessor sanity run
python -W ignore scripts/diagnose_stage3_mutation_detectability_v1.py  # 30/30 structural
```

All read-only over frozen artifacts; no LLM/API; no network.
