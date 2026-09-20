# SEP-C3 Definition Offline Patch Preparation v1

- Status: **candidate prepared; not active; not executed**
- New API / LLM calls: **0**
- Active prompt changes: **none**
- Active prompt registry/manifest changes: **none**
- Gold changes: **none**
- Prediction changes: **none**
- R_A / R_C changes: **none**
- S8 / condition / constraint / exception guidance changes: **none**

## 1. Design decision implemented

The approved definition-specific refinement is implemented as a small,
internal, non-active overlay:

- `R_DEF` definition-modality semantic guidance;
- `R_DEF` definition action-presence guidance;
- synthetic E4 v2 replacement.

The historical `semantic_rules_S.md` module was **not** edited or re-enabled.
S2, S11, and S8 remain absent from the candidate and active prompts.

## 2. Active assembly path discovered

The real active SEP-C3 A/B/C/D assembly is `direct_llm_refinement_v1`:

`common_system.md + user_envelope.md + examples_E.md + optional R_A + optional R_C`

with the generated prompt files under
`prompts/sun_compat/modular_refinement_v1/generated/`.  The full component map
and absence explanation are in
`outputs/reports/sep_c3_definition_active_assembly_audit_v1.md`.

Targeted overlay integration is possible using the existing refinement
mechanism: append an independent system-prompt paragraph after the frozen
common+E skeleton.  The active composer, active prompts, and active registry
were not edited.

## 3. Candidate files created

### 3.1 Prompt sources and candidate renders

- `prompts/sun_compat/modular_refinement_v1/R_DEF_definition_guidance.md`
- `prompts/sun_compat/modular_definition_refinement_v1/README.md`
- `prompts/sun_compat/modular_definition_refinement_v1/E_examples_E4_v2.md`
- `prompts/sun_compat/modular_definition_refinement_v1/generated/direct_llm_definition_BASE_v1.md`
- `prompts/sun_compat/modular_definition_refinement_v1/generated/direct_llm_definition_R_DEF_v1.md`
- `prompts/sun_compat/modular_definition_refinement_v1/generated/manifest.json`

Compatibility-only offline renderings (not candidate arms):

- `prompts/sun_compat/modular_definition_refinement_v1/generated/compatibility/direct_llm_definition_COMPAT_R_A_R_DEF_v1.md`
- `prompts/sun_compat/modular_definition_refinement_v1/generated/compatibility/direct_llm_definition_COMPAT_R_C_R_DEF_v1.md`
- `prompts/sun_compat/modular_definition_refinement_v1/generated/compatibility/direct_llm_definition_COMPAT_R_A_R_C_R_DEF_v1.md`

### 3.2 Implementation and audit

- `src/bpc_hybrid/sep_c3_definition_refinement_prompt.py`
- `scripts/build_sep_c3_definition_refinement_v1.py`
- `tests/test_sep_c3_definition_refinement_v1.py`
- `tests/fixtures/sep_c3_definition_synthetic_cases_v1.json`
- `outputs/reports/sep_c3_definition_candidate_prompt_diff_v1.md`
- `outputs/reports/sep_c3_definition_candidate_E4_v2.json`
- `outputs/reports/sep_c3_definition_candidate_prompt_audit_v1.json`

No currently active prompt file was overwritten.

## 4. Candidate composition

| Candidate arm | Composition |
|---|---|
| `BASE` | frozen common + existing E examples with only E4 replaced |
| `R_DEF` | `BASE` + approved `R_DEF` system-prompt paragraph(s) |

Compatibility-only renderings show `BASE` plus frozen `R_A`, `R_C`, or
`R_A + R_C`, with the candidate E4.  They were generated for offline assembly
inspection only and are not active arms.

The candidate E module differs from the active `examples_E.md` only by the
single approved E4 replacement.  This is enforced by the builder and tests.

## 5. Exact E4 v2 record

Synthetic sentence:

```text
A digitally signed copy shall be treated as an original document.
```

Derived spans:

- `clause_span`: `[0,64)`, text
  `A digitally signed copy shall be treated as an original document`
  (terminal period excluded, consistent with existing E examples)
- `modality`: `definition`
- `modality.evidence`: `shall [24,29)`
- `actors`: `[]`
- `actions`: one action, `be treated as an original document [30,64)`,
  normalized `be treated as an original document`
- `conditions`: `[]`
- `constraints`: `[]`
- `exceptions`: `[]`
- `actor_action_map`: `[]`
- `order_relations`: `[]`

The E4 markdown block intentionally says `no other field populated` rather
than listing condition/constraint/exception labels; the canonical record has
their empty arrays.

The full valid canonical record and wrapper are in
`outputs/reports/sep_c3_definition_candidate_E4_v2.json`.

This example teaches only: `shall` can occur in a definition; a definition can
have no actor; a definition still receives an action.  It adds no condition,
constraint, or exception supervision.

## 6. Candidate prompt diff

Full diff: `outputs/reports/sep_c3_definition_candidate_prompt_diff_v1.md`.

The diff contains exactly two candidate-relevant changes:

1. Active arm A to candidate `BASE`: the old E4 block is replaced by the
   synthetic E4 v2 block.  No other E example or common text changes.
2. Candidate `BASE` to candidate `R_DEF`: the approved `R_DEF` definition
   guidance is appended.  No other system text changes.

No S, J, R_A, or R_C text is introduced into the candidate arms.

## 7. Hash audit before and after

All before/after values below are identical.

| Artifact | SHA-256 |
|---|---|
| Active prompt A markdown | `d24c0c0d5150dd6382260f91614cc6d475ecdb68efb2cfe8d48347272d74a580` |
| Active prompt B markdown | `c468c631b6e454522994d6839f6a4021a259daedea7f3a2852b7b4343cd22849` |
| Active prompt C markdown | `d58163b677c6a7bda06f4de3ea8de743d8568e0d5e2c740bdea8af48ccfa4479` |
| Active prompt D markdown | `b241126dcb04001872e3bfd60deb330ed884ccad50537cc2031017a66835c091` |
| Active generated manifest / SEP-C3 prompt registry | `3d9ceb897b0582bf862a7d4c9ca130b07533a37c272e59b37c7323bededc9414` |
| Formal D1 active registry | `31f3358d089611b85a4a50d36444a4c59f6d965abbf0b8770aeb73db13642749` |
| Gold file | `c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100` |
| Prediction A canonical JSONL | `79a5ee8fcbf1e2a0b9e5ed4494cd68caa8fc886903cf5c67286cb1746b5e2072` |
| Prediction B canonical JSONL | `b8e17d1df134d290954f435e3af470223fc073d73f700c4bfab4470e78ef594a` |
| Prediction C canonical JSONL | `ecf81425de36a0c58cb74faa38a7bff69d5be85d73f56c733a77cb329e3e4a20` |
| Prediction D canonical JSONL | `380a15968d141ae5dbef6fe789c231c729c1f46e047f403e9c6a3fa66bab4ac0` |
| `examples_E.md` raw bytes | `fa04d454914fd85ad422ed40b3e4d3f71027ad87e9a46b1f4808f0cb4e21aebd` |
| `R_A_actor_minimality.md` raw bytes | `0d1a0b131c88394304ac22d510740694fed5069f9cc8b4b9612fd33285e789c9` |
| `R_C_constraint_recall.md` raw bytes | `cfcbbc45e278ab3ad4fad8784c5a6bcc551c0b51a2e1833ac2c4e56d0571fcae` |
| `semantic_rules_S.md` raw bytes | `113037b73485adb071dbfeabc54dfe6906514279c3dd065f72b4eb019d3a0025` |

## 8. Focused offline tests

Command run:

```powershell
python -m pytest formal_experiment/tests/test_sep_c3_definition_refinement_v1.py -q
```

Result: **10 passed**.

The focused tests cover the six requested synthetic categories (explicit
`means` definition, synthetic shall-definition, ordinary actor-directed
`shall` obligation, `may` permission, `may not` prohibition, and ambiguous
applicability), plus guidance occurrence, lexical-shortcut absence, E4 span
validity, non-empty E4 action, empty E4 condition/constraint/exception arrays,
unrelated component hashes, and loader/parser contract assembly.  No model was
invoked.

## 9. Future experiment plan

The prepared plan is in
`outputs/reports/sep_c3_definition_future_experiment_plan_v1.md`.  No sample
size or API budget is selected there until the candidate counts are reported;
the plan lists available counts separately.

## 10. Blockers and unresolved issues

There is no blocker to the offline candidate integration.

Unresolved research issues are retained and must not be turned into lexical
rules:

- apply/applies family: 12 clauses, 7 definition and 5 non-definition;
- potential Gold inconsistency: `estg_000505 c2` vs `estg_000509 c2`;
- exact action-span boundary remains evidence-bound, not universal;
- S8 boundary issue remains outside this patch and untouched;
- condition/constraint boundary supervision remains outside this patch.

## 11. Git and commit/push status

- HEAD remains `9ae8c25ba6d0a6f7ed6a324eceef03220526d783`.
- No commit or push was performed.
- The candidate artifacts are new untracked files.
- No tracked active prompt, registry, Gold, prediction, parser, or model
  configuration file was changed by this task.
- The working tree already contained unrelated pre-existing modifications
  before this task; they were left untouched.