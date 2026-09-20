# SEP-C3 Definition Targeted Development Panel v1

- Status: **frozen before new API output**
- API calls during construction: **0**
- Scope: targeted prompt-development panel, not a new formal test set
- Unique samples N: **42**
- Unique selected clauses: **45**
- New API calls: **BASE=42, R_DEF=42, total=84**
- Panel SHA-256: `8ba4517f21402566d61364e86a5516e0ea89f1f82a32781b303eb7a53d97ec61`

## Slice summary

| Slice | Clauses | Unique clauses | Samples | Modality counts |
|---|---:|---:|---:|---|
| `A_shall_definition` | 15 | 15 | 15 | definition:15 |
| `B_non_definition_shall_controls` | 15 | 15 | 14 | obligation:6, permission:3, prohibition:6 |
| `C_apply_applies_stress` | 12 | 12 | 12 | definition:7, obligation:4, permission:1 |
| `D_non_shall_definition_controls` | 6 | 6 | 6 | definition:6 |

## Deduplication accounting

- Unique samples: 42
- Unique selected clauses: 45
- Sum of slice clause counts before dedup: 48
- Definition cases: 25
- Non-definition cases: 20
- Clauses in selected samples (all, for diagnostics): 83

## Modality distribution

### Unique selected clauses

- definition: 25
- obligation: 10
- permission: 4
- prohibition: 6

### All clauses in selected samples

- definition: 28
- obligation: 34
- permission: 13
- prohibition: 8

## Prompt hashes

| Arm | System | User template | Composition |
|---|---|---|---|
| A | `9db8893c75af4c306f5f5142ea77b6c93b6a2bae79a72ba8dd0f2b3ca1985d4f` | `fb92bd110d33c22208f36816139871b6ec4f0f818e6fd731c60c5c321510abfb` | `f41d903bb86f8199499f3eb95d19042a5c321a5a06be3c38a0a04a8bfd8d2418` |
| BASE | `9db8893c75af4c306f5f5142ea77b6c93b6a2bae79a72ba8dd0f2b3ca1985d4f` | `ff181879858f08641b40a3e8799fa32e16235f70544b809cac7fddf9962797f5` | `3100c8521f3ad4a0a313293d4facdd37c92dccf8661e6021875750c58926da11` |
| R_DEF | `95c234ab44357411fb493f7b3ed46a29e76ada91f02ce3d2c1cd6b7af0496843` | `ff181879858f08641b40a3e8799fa32e16235f70544b809cac7fddf9962797f5` | `585d9a81116d8fb1b1cf1858b55e4a67457ca9886dbd0487f7f0d7474f5e8b07` |

## Ambiguity diagnostics

- Apply/applies cases: 12 retained with `NEEDS_GOLD_ADJUDICATION`; no lexical rule is inferred.
- Gold inconsistency pair:
  - `estg_000505 c2` modality=obligation in_panel=False status=POTENTIAL_GOLD_INCONSISTENCY
  - `estg_000509 c2` modality=definition in_panel=True status=POTENTIAL_GOLD_INCONSISTENCY

## Freeze note

This panel was frozen before any BASE/R_DEF model output was produced. Gold was used only for construction and later evaluation; no Gold labels or spans are included in the frozen inference request bodies.
