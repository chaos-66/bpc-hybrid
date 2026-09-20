# SEP-C3 Source Text Anomaly Audit v1

- 新增 API：0
- 原始 artifacts 不修改。
- 本文件只报告 source_text 追加 E 示例的 4 条 targeted outputs。

## Complete Targeted 4

| Arm | Sample | Canonical line | Original length | Actual length | Appended length | Appended SHA-256 |
|---|---|---:|---:|---:|---:|---|
| A | `estg_000044` | 18 | 161 | 2512 | 2351 | `771cf518d671923090a424fcc3a5e10385de74759158079faabc266889b0e607` |
| A | `estg_000720` | 141 | 215 | 2566 | 2351 | `771cf518d671923090a424fcc3a5e10385de74759158079faabc266889b0e607` |
| C | `estg_000035` | 11 | 172 | 2523 | 2351 | `771cf518d671923090a424fcc3a5e10385de74759158079faabc266889b0e607` |
| C | `estg_000044` | 18 | 161 | 2512 | 2351 | `771cf518d671923090a424fcc3a5e10385de74759158079faabc266889b0e607` |

## Pattern

- Occurs in arms A and C only within targeted A/B/C/D.
- Occurs in 3 unique samples; `estg_000044` appears in both A and C.
- The append block is identical in all four rows and begins with:

```text

### E — Synthetic worked examples
```

- It is the E module text, length 2351 bytes.

## Span / Source Integrity

- The original source prefix is unchanged in all four rows.
- Every predicted clause_span / field span remains inside the original regulation text length.
- For each span, `text == original_source[start:end]` holds.
- Therefore the anomaly does not change condition/constraint or other field coordinates in these four rows.

## Effect on Semantic Analysis

- No effect on this study's semantic coordinate analysis.
- However, the interface contract is violated because `source_text` no longer equals the formal input text.
- The saved validation flag remains true; validation did not catch this interface anomaly.
- Any future prediction or evaluator pipeline that slices source_text before prediction span analysis could be affected.

## Additional Same-Pattern Occurrence

- In earlier `sep_c3_modular_ablation_v2/100/repeat-01/canonical_predictions.jsonl`, `estg_000044` also has the same E append pattern.
- This is not counted in the targeted 4, but it shows the anomaly is not confined to the targeted-refinement family.

## Recommendation

- Do not modify raw JSONL artifacts.
- Before future API calls, add an input-binding check that `record.source_text` exactly equals the prepared input `approved_text_en`.
- This report does not implement that fix.
