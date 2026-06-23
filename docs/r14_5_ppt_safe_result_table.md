# R14.5 PPT-safe Result Table

> **Claim boundary**: Descriptive small-scale observation on the same 24 draft mini-gold samples.
> This is not a formal benchmark, not method validation, not Sun reproduction. It does not prove generalized advantage of LLM assistance.

## Overall Metrics

| Metric | Rule-only R14.2 | Rule+LLM R14.4 | Descriptive Delta |
|---|---:|---:|---:|
| Overall field exact accuracy | 0.149 | 0.513 | +0.364 |
| Macro strict F1 | 0.141 | 0.577 | +0.437 |
| Micro strict F1 | 0.214 | 0.522 | +0.308 |
| Macro lenient F1 | 0.221 | 0.841 | +0.619 |
| Micro lenient F1 | 0.315 | 0.814 | +0.500 |

## Field-level Exact Accuracy

| Field | Rule-only exact | Rule+LLM exact | Descriptive Delta | Note |
|---|---:|---:|---:|---|
| modality | 0.667 | 0.875 | +0.208 | small observed delta; rule-only already had higher value here |
| actor | 0.042 | 0.708 | +0.667 | largest observed delta among non-exception fields |
| action | 0.000 | 0.417 | +0.417 | rule-only could not extract any action exactly |
| condition | 0.000 | 0.250 | +0.250 | rare field (16/24 applicable); partial matches drive lenient gain |
| constraint | 0.000 | 0.167 | +0.167 | partial matches common; exact matches rare for both sides |
| exception | 0.000 | 1.000 | +1.000 | only 3 applicable samples; n too small to generalize |

## Field-level Strict F1

| Field | Rule-only strict F1 | Rule+LLM strict F1 | Descriptive Delta | Note |
|---|---:|---:|---:|---|
| modality | 0.781 | 0.875 | +0.095 | smallest strict F1 delta |
| actor | 0.063 | 0.739 | +0.677 | highest strict F1 delta |
| action | 0.000 | 0.417 | +0.417 | rule-only had zero strict F1 |
| condition | 0.000 | 0.267 | +0.267 | rule-only had zero strict F1 |
| constraint | 0.000 | 0.167 | +0.167 | rule-only had zero strict F1 |
| exception | 0.000 | 1.000 | +1.000 | n=3; no generalization implied |

## Field-level Lenient F1

| Field | Rule-only lenient F1 | Rule+LLM lenient F1 | Descriptive Delta | Note |
|---|---:|---:|---:|---|
| modality | 0.781 | 0.875 | +0.095 | smallest lenient delta |
| actor | 0.375 | 0.826 | +0.451 | higher observed value in bounded pilot |
| action | 0.098 | 0.792 | +0.694 | highest lenient delta after condition |
| condition | 0.000 | 0.800 | +0.800 | largest lenient delta; partial overlap accounts for most of the gain |
| constraint | 0.074 | 0.750 | +0.676 | large lenient delta; partial overlap accounts for most of the gain |
| exception | 0.000 | 1.000 | +1.000 | n=3; no generalization implied |

---

**Key observation**: On the same 24 draft mini-gold samples, the Rule+LLM side showed higher observed values across all metrics and fields. The largest descriptive differences were in semantic fields (actor, action, condition, constraint). The modality field, where deterministic rules were already effective, showed the smallest observed delta. The exception field had too few applicable samples (n=3) for any descriptive generalization.
