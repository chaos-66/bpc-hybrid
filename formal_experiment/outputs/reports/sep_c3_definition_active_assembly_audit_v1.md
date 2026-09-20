# SEP-C3 Definition Active Assembly Audit v1

- Status: **audit complete; no active artifact modified**
- New API / LLM calls: **0**
- Active prompt files: **byte-identical**
- Active prompt registry/manifest: **byte-identical**
- Gold / predictions: **byte-identical**

## 1. Scope

This audit identifies the real active SEP-C3 A/B/C/D prompt assembly before any
candidate integration.  It addresses only the definition-specific overlay
question and does not activate a new prompt, module, registry entry, or model
call.

## 2. Active assembly path

The active SEP-C3 A/B/C/D family is the targeted-refinement family
`direct_llm_refinement_v1`.

| Layer | Exact repository path |
|---|---|
| Common system | `prompts/sun_compat/modular_v1/common_system.md` |
| User envelope | `prompts/sun_compat/modular_v1/user_envelope.md` |
| E examples | `prompts/sun_compat/modular_v1/examples_E.md` |
| R_A overlay | `prompts/sun_compat/modular_refinement_v1/R_A_actor_minimality.md` |
| R_C overlay | `prompts/sun_compat/modular_refinement_v1/R_C_constraint_recall.md` |
| Composer | `src/bpc_hybrid/modular_refinement_prompt.py` |
| Builder | `scripts/build_sep_c3_targeted_refinement_v1.py` |
| Active manifest / prompt registry | `prompts/sun_compat/modular_refinement_v1/generated/manifest.json` |
| Runtime loader path | `prompts/sun_compat/modular_refinement_v1/generated/direct_llm_refinement_{A,B,C,D}_v1.md` |
| Runtime | `scripts/run_sep_c3_targeted_refinement_v1.py` |
| Budget binding | `configs/sep_c3_targeted_refinement_budget_v1.json` |
| Schedule binding | `configs/sep_c3_targeted_refinement_schedule_v1.json` |
| Formal D1 active registry | `configs/models/estg150_d1_active_registry_v1.json` |

The active baseline is modular arm `100` (`E=1`, `S=0`, `J=0`).  The composer
appends optional `R_A` and/or `R_C` paragraphs to the common system prompt.
The E block is placed in the user prompt exactly once.  No S or J module is
included in any active A/B/C/D arm.

## 3. Why S2/S11/S8 are absent

`S=0` is part of the frozen `100` baseline.  The active composer only appends
the independent repair paragraphs `R_A` and `R_C`; it never inserts
`semantic_rules_S.md`.  Therefore:

- S2 definition-modality guidance is absent;
- S11 definition-action-presence guidance is absent;
- S8 field-partition guidance is absent;
- editing `semantic_rules_S.md` would not affect the active A/B/C/D prompts and
  would not be a valid candidate integration path for this study.

This is why the approved definition changes are implemented as a separate,
targeted internal overlay (`R_DEF`) rather than by re-enabling S.

## 4. Smallest existing mechanism for the targeted overlay

The repository already supports independent system-prompt overlay paragraphs
after the frozen common+E skeleton.  `R_A` and `R_C` are the existing examples
of this mechanism.  A targeted `R_DEF` paragraph can therefore be appended
without touching S, J, R_A, R_C, the common skeleton, or the active registry.

The only non-overlay part of the approved candidate is the E4 replacement.
Because the active E module is frozen and shared, the candidate does not edit
`examples_E.md`.  Instead it derives a candidate E block deterministically
from the active file by replacing exactly one E4 block.  That keeps the active
file byte-identical while allowing an offline candidate rendering with the
approved synthetic E4.

The existing `modular_prompt.render_modular_prompt(..., texts=...)` API accepts
alternative module text while preserving the common composition semantics.  The
candidate uses that existing API for the E4 data substitution (active common
skeleton + a deterministic candidate E text) and then appends `R_DEF` as a
system paragraph exactly like the existing `R_A` / `R_C` mechanism.  This is a
candidate-local data substitution plus overlay append, not a new assembly
architecture.

Conclusion: **targeted overlay integration is possible without architectural
modification to the active family.**  The candidate is non-active and separate
from the active A/B/C/D registry.

## 5. Active artifact hashes observed before and after

| Artifact | SHA-256 |
|---|---|
| Active A markdown | `d24c0c0d5150dd6382260f91614cc6d475ecdb68efb2cfe8d48347272d74a580` |
| Active B markdown | `c468c631b6e454522994d6839f6a4021a259daedea7f3a2852b7b4343cd22849` |
| Active C markdown | `d58163b677c6a7bda06f4de3ea8de743d8568e0d5e2c740bdea8af48ccfa4479` |
| Active D markdown | `b241126dcb04001872e3bfd60deb330ed884ccad50537cc2031017a66835c091` |
| Active manifest / prompt registry | `3d9ceb897b0582bf862a7d4c9ca130b07533a37c272e59b37c7323bededc9414` |
| `examples_E.md` raw bytes | `fa04d454914fd85ad422ed40b3e4d3f71027ad87e9a46b1f4808f0cb4e21aebd` |
| `R_A_actor_minimality.md` raw bytes | `0d1a0b131c88394304ac22d510740694fed5069f9cc8b4b9612fd33285e789c9` |
| `R_C_constraint_recall.md` raw bytes | `cfcbbc45e278ab3ad4fad8784c5a6bcc551c0b51a2e1833ac2c4e56d0571fcae` |
| `semantic_rules_S.md` raw bytes | `113037b73485adb071dbfeabc54dfe6906514279c3dd065f72b4eb019d3a0025` |

These hashes were unchanged after candidate generation.

## 6. Non-changes

The candidate generation did not modify:

- active A/B/C/D generated prompts;
- the active generated manifest / prompt registry;
- `common_system.md`, `user_envelope.md`, `examples_E.md`, `output_format_J.md`;
- `semantic_rules_S.md` or any S guidance;
- `R_A` or `R_C`;
- condition, constraint, or exception guidance;
- Gold;
- persisted predictions;
- parser/canonicalizer protocol;
- model configuration or sampling parameters.