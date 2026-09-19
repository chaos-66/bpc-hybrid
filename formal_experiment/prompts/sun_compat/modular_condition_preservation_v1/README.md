# SEP-C3 condition-preservation prompt v1

This family is a zero-API preparation artefact. It does **not** replace the
frozen formal default v6 prompt and it does not reuse any old paid-run
authorization.

## Fixed arms

| Arm | Composition | Old-arm equivalence |
|---|---|---|
| `BASE` | common + E + frozen `R_A` | same actual sent prompt as old `B` |
| `RC1` | `BASE` + frozen old `R_C` | same actual sent prompt as old `D` |
| `RC_KEEP` | `RC1` + one fixed preservation sentence | new candidate only |

The one new sentence is:

```text
Keep each applicability condition as a complete proposition in conditions; extracting an overlapping or nested constraint must not replace or remove that condition.
```

It is appended after the frozen old `R_C` as a separate system-prompt
paragraph. No other prompt source, user-envelope, model, or sampling parameter
is changed.

## Source hashes

The composer is `src/bpc_hybrid/sep_c3_condition_preservation_prompt.py`.
It loads the frozen common/E baseline and old B/D wording through
`bpc_hybrid.modular_refinement_prompt`, and fails closed if the old sources
drift. The generated prompts and their hashes are in `generated/`.

## Commands

```powershell
python formal_experiment/scripts/prepare_sep_c3_condition_preservation_v1.py --prepare --overwrite
python formal_experiment/scripts/prepare_sep_c3_condition_preservation_v1.py --check
```

Both commands are zero-network and must be run from the repository root or the
`formal_experiment/` directory with adjusted paths. Real execution is not
implemented in this round and remains unauthorized.