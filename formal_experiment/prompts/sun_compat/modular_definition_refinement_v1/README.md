# SEP-C3 definition-refinement candidate v1

This directory is an **offline, non-active candidate** created for the
approved definition-modality and definition-action guidance.  It does not
replace the active `modular_refinement_v1` A/B/C/D prompts and it does not
activate a new prompt registry entry.

## Candidate composition

- `../modular_v1/common_system.md` and `../modular_v1/user_envelope.md` are
  reused unchanged.
- `E_examples_E4_v2.md` is the frozen existing E module with exactly one
  approved replacement: old E4 becomes the synthetic one-clause
  shall-definition.
- `../modular_refinement_v1/R_DEF_definition_guidance.md` is appended as an
  independent system-prompt paragraph.
- `S`, `J`, `R_A`, and `R_C` are not active in the candidate arms.

## Render arms

| Arm | Composition |
|---|---|
| `BASE` | common + candidate E (E4 v2) |
| `R_DEF` | common + candidate E (E4 v2) + `R_DEF` |

`generated/compatibility/` contains non-active offline renderings that append
`R_DEF` to the frozen old `R_A`, `R_C`, or `R_A + R_C` system prompts.  These
exist only for compatibility inspection and are not candidate arms.

## Zero-network command

```powershell
python formal_experiment/scripts/build_sep_c3_definition_refinement_v1.py --check
```

Real model execution is not implemented for this candidate and is not
authorized by this patch-preparation task.