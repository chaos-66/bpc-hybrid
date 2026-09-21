# SEP-C3 Definition R_DEF Full-150 Confirmation Precheck

- Status: **BLOCKED_HISTORICAL_A_INCOMPATIBLE**
- API calls made: **0**
- R_DEF full-150 confirmation run launched: **no**

## Input freeze
- Input records: 150 unique=150
- Input SHA-256: `52a73aa1109970b6c4fbc17214b0828ed0dd64b330001e884cdc803b1ce81dc2`
- Matches frozen panel: True; matches targeted budget: True
- Gold SHA-256: `c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100` (panel match=True)

## R_DEF prompt freeze
- System SHA-256: `95c234ab44357411fb493f7b3ed46a29e76ada91f02ce3d2c1cd6b7af0496843`
- User SHA-256: `ff181879858f08641b40a3e8799fa32e16235f70544b809cac7fddf9962797f5`
- Composition SHA-256: `585d9a81116d8fb1b1cf1858b55e4a67457ca9886dbd0487f7f0d7474f5e8b07`
- Matches candidate manifest: True; matches targeted panel: True
- R_DEF guidance source matches approved constant: True

## Historical Arm A compatibility
- Path: `outputs/development/sep_c3_targeted_refinement_v1/A/repeat-01/canonical_predictions.jsonl`
- Rows: 150 unique=150; membership matches frozen 150: True
- Prompt hashes match active A/panel: True
- Legacy official five-field mean F1: 0.7245765762 (matches recorded=True)
- Legacy request_status=ok: 150/150; transport/provider errors: 0
- Current-contract input-binding failures: 2/150
- Current-contract canonical-validation failures: 10/150
- Union of current-contract failures: 12/150
- A rescored under current failure policy (failures empty): mean F1 0.7080951816 (-0.0164813945 vs legacy record view)

## Evaluator dry check
- Full-150 A attempts: denominator=150, status=pass
- Full-150 empty attempts: denominator=150, status=pass
- 42-subset attempt: SunLiteralOverlapError: attempt membership differs from Gold: missing=['estg_000002', 'estg_000003', 'estg_000004', 'estg_000020', 'estg_000021'], extra=[]

## Stop decision
Historical A is not directly comparable to a current-pipeline R_DEF run. The legacy A record view scores 0.7245765762, while enforcing the current input-binding/canonical-validation failure policy on the same stored outputs yields 0.7080951816. Running R_DEF under the current contract without a same-contract A baseline would confuse generation-validity with extraction quality; re-scoring A would change the historical arm. Per the task instruction, the run stops before any API call. Arm A remains the frozen final prompt, and R_DEF is not promoted.
