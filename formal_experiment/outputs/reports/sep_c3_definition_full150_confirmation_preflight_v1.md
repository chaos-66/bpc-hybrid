# SEP-C3 Definition Full-150 R_DEF Confirmation Preflight

- Suite: `SEP-C3-DEFINITION-FULL150-CONFIRMATION-001`
- Status: **PASS_FROZEN_BEFORE_NEW_API**
- API calls made: **0**
- New R_DEF calls planned: **150**
- Arm: `R_DEF`
- Treatment package: E4 v2 replacement + R_DEF guidance

## Frozen inputs
- Input SHA-256: `52a73aa1109970b6c4fbc17214b0828ed0dd64b330001e884cdc803b1ce81dc2`
- Schedule SHA-256: `a7e2b818f773738854657cce887a848fd129d998a18ae8fd4e5f9f2bd1369e95`
- Sample membership/order SHA-256: `95b6ae7a206dec3b01985cdcdcbca09147f470b6988a209d7b5cd65bab413c6c`
- Prompt composition SHA-256: `585d9a81116d8fb1b1cf1858b55e4a67457ca9886dbd0487f7f0d7474f5e8b07`

## A current-contract baseline
- Rescored A five-field mean F1: `0.7080951816362215`
- Expected: `0.7080951816362215`
- Legacy score, separately labeled and not directly comparable: `0.7245765761849047`
- Freeze artifact: `outputs/development/sep_c3_definition_full150_confirmation_v1/A_current_contract/repeat-01/manifest.json`

## Evaluator dry check
- Status: `PASS`
- Full-150 denominator: `150`

## Execution command
```powershell
cd formal_experiment && python scripts/run_sep_c3_definition_full150_confirmation_v1.py --execute --allow-llm --project-env
```

The comparison is a full-corpus confirmation of the frozen package, not an independent held-out generalization test.
