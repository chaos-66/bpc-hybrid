# SEP-C3 targeted refinement v1 — Phase 2 evidence

Status: **complete zero-API analysis of the persisted A/B/C/D run**.

## 1. Execution integrity

- Planned calls: 600; attempted: 600; successful: 600; failed: 0; resumed: 0.
- All four arms have all 150 samples: `True`.
- Per-arm successful calls: A=150, B=150, C=150, D=150.
- Schedule deviations: 0; config deviations: 0.
- No missing sample/arm, extra sample, or failed call was observed.

## 2. Frozen experiment identity

- Suite: `SEP-C3-TARGETED-REFINEMENT-001`; repeat: `repeat-01`.
- Arms: A, B, C, D.
- Schedule: `configs/sep_c3_targeted_refinement_schedule_v1.json` SHA-256 `63cd957f9ff4d3261dfcf407fac207fad910ca67b521f9b0b549737b80ac94ca` scheme `sample_level_random_permutation`.
- Model alias: `deepseek-v4-pro`; documented release: `DeepSeek-V4-Pro-0813`.
- Returned model counts: `{'deepseek-v4-pro': 600}`.
- Temperature/top_p/max_tokens: 0.0/1.0/4096; retry=0; stream=false; thinking=disabled.

## 3. Overall results

| Arm | Mean F1 | Micro P | Micro R | Micro F1 |
| --- | ------: | ------: | ------: | -------: |
| A | 0.7246 | 0.8025 | 0.7800 | 0.7911 |
| B | 0.7806 | 0.8550 | 0.7996 | 0.8264 |
| C | 0.7558 | 0.8088 | 0.8126 | 0.8107 |
| D | 0.7858 | 0.8271 | 0.8192 | 0.8231 |

## 4. Per-field results

| Field | A P/R/F1 | B P/R/F1 | C P/R/F1 | D P/R/F1 |
| --- | --- | --- | --- | --- |
| modality | 0.7967/0.7590/0.7451 | 0.7869/0.7531/0.7359 | 0.7903/0.7638/0.7500 | 0.8052/0.7822/0.7656 |
| actor | 0.4725/0.9512/0.6314 | 0.6429/0.9512/0.7672 | 0.5227/0.9756/0.6807 | 0.6000/0.9268/0.7284 |
| action | 0.8755/0.9333/0.9035 | 0.9286/0.9533/0.9408 | 0.9056/0.9333/0.9192 | 0.9174/0.9267/0.9220 |
| condition | 0.8782/0.8115/0.8435 | 0.8774/0.7951/0.8342 | 0.9084/0.7459/0.8192 | 0.9141/0.7213/0.8063 |
| constraint | 0.8015/0.5556/0.6562 | 0.8102/0.6074/0.6943 | 0.7525/0.7185/0.7351 | 0.7553/0.7778/0.7664 |
| exception | 0.8333/0.4545/0.5882 | 0.8571/0.5455/0.6667 | 1.0000/0.4545/0.6250 | 1.0000/0.5455/0.7059 |

*Modality is reported as a macro average over the evaluator's four label classes; it is separate from the five span fields.*

## 5. A vs B actor analysis

- Actor F1: A=0.6314, B=0.7672, delta=0.1358.
- Actor corrected sample-fields: 22; regressed: 3.
- Unmatched actor predictions: A=48, B=25.
- Empty-Gold actor false-positive sample-fields: A=36, B=19.
- Actor over-extraction candidate regressions: 2; under-extraction/newly-missed candidate regressions: 1.

## 6. C vs D actor analysis

- Actor F1: C=0.6807, D=0.7284, delta=0.0477.
- Actor corrected sample-fields: 17; regressed: 6.
- Unmatched actor predictions: C=42, D=28.
- Empty-Gold actor false-positive sample-fields: C=33, D=23.
- Actor over-extraction candidate regressions: 5; under-extraction/newly-missed candidate regressions: 2.

## 7. A vs C constraint analysis

- Constraint F1: A=0.6562, C=0.7351, delta=0.0789.
- Constraint corrected sample-fields: 23; regressed: 12.
- Constraint missed Gold: A=60, C=38.
- Constraint unmatched predictions: A=27, C=50.
- Exact isolated `only` constraints: A=5, C=9.
- Over-extraction candidate regressions: 9; under-extraction candidate regressions: 4.

## 8. B vs D constraint analysis

- Constraint F1: B=0.6943, D=0.7664, delta=0.0721.
- Constraint corrected sample-fields: 20; regressed: 14.
- Constraint missed Gold: B=53, D=30.
- Constraint unmatched predictions: B=26, D=58.
- Exact isolated `only` constraints: B=5, D=11.
- Over-extraction candidate regressions: 12; under-extraction candidate regressions: 2.

Constraint lexical-marker candidates for manual review:

These are deterministic lexical-marker candidates, not a semantic category classifier; the frozen evaluator is unchanged.
- A_to_C: 10 selected corrected/regressed cases with at least one lexical marker.
  - estg_000028 (fixed, A->C): time_candidate, purpose_candidate
  - estg_000031 (fixed, A->C): time_candidate, purpose_candidate
  - estg_000033 (fixed, A->C): time_candidate
- B_to_D: 10 selected corrected/regressed cases with at least one lexical marker.
  - estg_000030 (fixed, B->D): time_candidate, legal_reference_candidate
  - estg_000031 (fixed, B->D): time_candidate, purpose_candidate
  - estg_000033 (fixed, B->D): time_candidate

## 9. Combined arm analysis

Pair-level primary deltas:

| Comparison | Baseline mean F1 | Variant mean F1 | Delta |
| --- | ------: | ------: | ------: |
| A vs B | 0.7246 | 0.7806 | 0.0561 |
| A vs C | 0.7246 | 0.7558 | 0.0313 |
| A vs D | 0.7246 | 0.7858 | 0.0612 |
| B vs D | 0.7806 | 0.7858 | 0.0052 |
| C vs D | 0.7558 | 0.7858 | 0.0300 |
| B vs C | 0.7806 | 0.7558 | -0.0248 |

Pair-level overall sample overlay (all five span fields evaluator-correct):

| Comparison | Corrected | Regressed | Both correct | Both wrong | Unchanged total |
| --- | ------: | ------: | ------: | ------: | ------: |
| A vs B | 16 | 11 | 34 | 89 | 123 |
| A vs C | 11 | 12 | 33 | 94 | 127 |
| A vs D | 20 | 14 | 31 | 85 | 116 |
| B vs D | 13 | 12 | 38 | 87 | 125 |
| C vs D | 14 | 7 | 37 | 92 | 129 |
| B vs C | 13 | 19 | 31 | 87 | 118 |

Per-field paired fixed/regressed counts (fixed = baseline wrong -> variant correct):

| Comparison | actor F/R | action F/R | condition F/R | constraint F/R | exception F/R |
| --- | --- | --- | --- | --- | --- |
| A vs B | 22/3 | 9/4 | 2/5 | 13/9 | 1/0 |
| A vs C | 8/4 | 6/2 | 4/10 | 23/12 | 2/1 |
| A vs D | 17/2 | 6/2 | 5/12 | 25/15 | 3/1 |
| B vs D | 2/6 | 4/5 | 4/8 | 20/14 | 2/1 |
| C vs D | 17/6 | 3/3 | 2/3 | 9/10 | 2/1 |
| B vs C | 5/20 | 3/4 | 5/8 | 22/15 | 2/2 |

Observable D-related paired facts (descriptive only):
- B->D actor fixed/regressed: 2/6; C->D actor: 17/6.
- B->D constraint fixed/regressed: 20/14; C->D constraint: 9/10.
- Exact isolated `only` constraints: B=5, C=9, D=11.
- Overall sample corrected/regressed: B->D=13/12; C->D=14/7.

## 10. Descriptive interaction

$I_M = M_D - M_B - M_C + M_A$ (descriptive / observed only).

| Metric | A | B | C | D | I_M |
| --- | ------: | ------: | ------: | ------: | ------: |
| primary_mean_f1 | 0.7246 | 0.7806 | 0.7558 | 0.7858 | -0.0261 |
| actor_f1 | 0.6314 | 0.7672 | 0.6807 | 0.7284 | -0.0881 |
| constraint_f1 | 0.6562 | 0.6943 | 0.7351 | 0.7664 | -0.0068 |
| actor_precision | 0.4725 | 0.6429 | 0.5227 | 0.6000 | -0.0931 |
| actor_recall | 0.9512 | 0.9512 | 0.9756 | 0.9268 | -0.0488 |
| constraint_precision | 0.8015 | 0.8102 | 0.7525 | 0.7553 | -0.0059 |
| constraint_recall | 0.5556 | 0.6074 | 0.7185 | 0.7778 | 0.0074 |

No validated paired bootstrap utility was found in the repository for this experiment; only descriptive paired evidence is reported here. No new significance-testing procedure was added.

## 11. Raw JSON / canonical reliability

| Arm | Raw rows | Bare JSON object | Parsable JSON | Request OK | Canonical valid | Parser warning rows | Canonicalizer warning rows |
| --- | ------: | ------: | ------: | ------: | ------: | ------: | ------: |
| A | 150 | 147 (0.9800) | 147 (0.9800) | 150 | 150 (1.0000) | 0 | 28 |
| B | 150 | 150 (1.0000) | 150 (1.0000) | 150 | 150 (1.0000) | 0 | 23 |
| C | 150 | 149 (0.9933) | 149 (0.9933) | 150 | 150 (1.0000) | 2 | 21 |
| D | 150 | 147 (0.9800) | 147 (0.9800) | 150 | 150 (1.0000) | 3 | 25 |

## 12. Representative corrected cases

### Actor corrected by R_A: A -> B

- **estg_000664** (A→B, actor)
  - Source: `The following shall apply to this provision:

— Certain income, in particular foreign income, may be wholly or partially excluded from the tax base or taxed at a reduced tax rate, or

— taxation may be based solely on the amount corresponding to domestic consumption, or

— the tax base or the tax may also be fixed as a lump sum.`
  - Gold: []
  - Baseline: `Certain income, in particular foreign income` [48,92]; `taxation` [186,194]; `the tax base or the tax` [274,297]
  - Variant: []
  - Observation: A: 3 predicted span(s), 3 unmatched, 0 missed Gold span(s); B: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000004** (A→B, actor)
  - Source: `(7) A change of the fiscal year to a different closing date is only permissible if there are substantial business reasons and the tax office has given prior consent by official notice.`
  - Gold: []
  - Baseline: `A change of the fiscal year to a different closing date` [4,59]; `the tax office` [126,140]
  - Variant: []
  - Observation: A: 2 predicted span(s), 2 unmatched, 0 missed Gold span(s); B: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000046** (A→B, actor)
  - Source: `The certificate is not required if the invention is already protected by patent law. — The research allowance generally amounts to up to 12% of research expenditures. — An increased research allowance of up to 18% may be claimed if the inventions are not made available to other persons for substantial exploitation.`
  - Gold: []
  - Baseline: `The certificate` [0,15]; `The research allowance` [87,109]
  - Variant: []
  - Observation: A: 2 predicted span(s), 2 unmatched, 0 missed Gold span(s); B: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000209** (A→B, actor)
  - Source: `Shares issued as a result of a capital increase are not eligible if the resolution on the increase of the share capital (Section 149(1) of the Stock Corporation Act 1965) was adopted within two years after the registration of the resolution on the reduction of the share capital for the purpose of repaying parts of the share capital (Section 177 of the Stock Corporation Act 1965); this also applies to capital reductions by a stock corporation or a limited liability company as the legal predecessor of the stock corporation (Sections 219 and 245 of the Stock Corporation Act 1965, Section 2 of the Federal Act on the Transformation of Commercial Companies, Federal Law Gazette).`
  - Gold: []
  - Baseline: `Shares issued as a result of a capital increase` [0,47]; `capital reductions by a stock corporation or a limited liability company as the legal predecessor of the stock corporation` [404,526]
  - Variant: []
  - Observation: A: 2 predicted span(s), 2 unmatched, 0 missed Gold span(s); B: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000210** (A→B, actor)
  - Source: `Shares for which guarantees regarding value or dividend claims are provided are not eligible.
b) Stock corporations within the meaning of paragraph 1 item 4 are stock corporations having their registered seat and place of management in the country,
aa) which belong to the "Trade" or "Industry" sections of a chamber of commerce and whose main business focus, according to the articles of association and the preparatory acts or the actual management, is demonstrably the industrial manufacture of tangible assets in the country, excluding the generation of electrical energy, gas or heat, and
bb) for which no general deficiency guarantees for the event of insolvency have been assumed.
c) A stock corporation whose 152.`
  - Gold: []
  - Baseline: `Stock corporations within the meaning of paragraph 1 item 4` [97,156]; `A stock corporation whose 152.` [691,721]
  - Variant: []
  - Observation: A: 2 predicted span(s), 2 unmatched, 0 missed Gold span(s); B: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s).

### Actor corrected by R_A: C -> D

- **estg_000028** (C→D, actor)
  - Source: `The income shall be taxed at the tax rate that results when taking into account the converted income; however, the tax to be assessed may not be higher than that which would result from the taxation of all emoluments.`
  - Gold: []
  - Baseline: `The income` [0,10]; `the tax to be assessed` [111,133]
  - Variant: []
  - Observation: C: 2 predicted span(s), 2 unmatched, 0 missed Gold span(s); D: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000664** (C→D, actor)
  - Source: `The following shall apply to this provision:

— Certain income, in particular foreign income, may be wholly or partially excluded from the tax base or taxed at a reduced tax rate, or

— taxation may be based solely on the amount corresponding to domestic consumption, or

— the tax base or the tax may also be fixed as a lump sum.`
  - Gold: []
  - Baseline: `Certain income, in particular foreign income` [48,92]; `the tax base or the tax` [274,297]
  - Variant: []
  - Observation: C: 2 predicted span(s), 2 unmatched, 0 missed Gold span(s); D: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000800** (C→D, actor)
  - Source: `This does not apply as long as the sponsoring undertaking suspends the contribution payments (Section 4(4) no. 2 of the Income Tax Act 1988).
d) The pension commitments of the fund may not exceed 80% of the last current active remuneration.
e) The beneficiary must also have a legal entitlement to the pension upon termination of the employment relationship (vesting) if he/she has been a beneficiary for more than five years.
f) Upon termination of the employment relationship before the insured event occurs, the beneficiary's entitlements from own contributions and from employer contributions that have become vested may be settled or transferred to another pension fund.
g) After the insured event has occurred, the following may be settled:
— minor benefits and
— benefits for survivors' provision.
h) The entitled employees must have the right to participate in the administration of all amounts that flow to the fund.
2.`
  - Gold: `The beneficiary must also have a legal entitlement to the pension upon termination of the employment relationship (vesting) if he/she has been a beneficiary for more than five years.
f) Upon termination of the employment relationship before the insured event occurs, the beneficiary's entitlements from own contributions and from employer contributions that have become vested may be settled or transferred to another pension fund.
g) After the insured event has occurred, the following may be settled:
— minor benefits and
— benefits for survivors' provision.
h) The entitled employees` [244,830]
  - Baseline: `This` [0,4]; `The pension commitments of the fund` [145,180]; `The beneficiary` [244,259]; `The entitled employees` [808,830]
  - Variant: `The beneficiary` [244,259]; `The entitled employees` [808,830]
  - Observation: C: 4 predicted span(s), 2 unmatched, 0 missed Gold span(s); D: 2 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000812** (C→D, actor)
  - Source: `For commercial enterprises (Section 2) that are required to keep books under commercial law provisions, and for trading and business cooperatives, the profit shall be determined in accordance with Section 5 of the Income Tax Act 1988.`
  - Gold: []
  - Baseline: `commercial enterprises (Section 2) that are required to keep books under commercial law provisions` [4,102]; `trading and business cooperatives` [112,145]
  - Variant: []
  - Observation: C: 2 predicted span(s), 2 unmatched, 0 missed Gold span(s); D: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000035** (C→D, actor)
  - Source: `(3) The excess of business receipts over business expenses may be recognised as profit if there is no statutory obligation to keep books and books are not kept voluntarily.`
  - Gold: []
  - Baseline: `The excess of business receipts over business expenses` [4,58]
  - Variant: []
  - Observation: C: 1 predicted span(s), 1 unmatched, 0 missed Gold span(s); D: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s).

### Constraint corrected by R_C: A -> C

- **estg_000028** (A→C, constraint)
  - Source: `The income shall be taxed at the tax rate that results when taking into account the converted income; however, the tax to be assessed may not be higher than that which would result from the taxation of all emoluments.`
  - Gold: `at the tax rate that results when taking into account the converted income; however, the tax to be assessed may not be higher than that which would result from the taxation of all emoluments` [26,216]
  - Baseline: []
  - Variant: `at the tax rate that results when taking into account the converted income` [26,100]
  - Observation: A: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); C: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000031** (A→C, constraint)
  - Source: `(1) Profit is the difference, to be determined by double-entry bookkeeping, between the business assets at the end of the financial year and the business assets at the end of the preceding financial year.`
  - Gold: `to be determined by double-entry bookkeeping, between the business assets at the end of the financial year and the business assets at the end of the preceding financial year` [30,203]
  - Baseline: []
  - Variant: `to be determined by double-entry bookkeeping` [30,74]
  - Observation: A: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); C: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000033** (A→C, constraint)
  - Source: `Gains or losses from the disposal or withdrawal and other changes in value of land that is part of the fixed assets are not to be taken into account.`
  - Gold: `that is part of the fixed assets` [83,115]
  - Baseline: []
  - Variant: `from the disposal or withdrawal and other changes in value of land that is part of the fixed assets` [16,115]
  - Observation: A: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); C: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000040** (A→C, constraint)
  - Source: `Dependants also include spouses and children (Section 106). (ee) The contributions, together with direct benefits within the meaning of Section 3(1) item 15, must not exceed 10% of the total wages and salaries of the beneficiaries.`
  - Gold: `spouses and children (Section 106). (ee) The contributions, together with direct benefits within the meaning of Section 3(1) item 15, must not exceed 10% of the total wages and salaries of the beneficiaries` [24,230]
  - Baseline: []
  - Variant: `10% of the total wages and salaries of the beneficiaries` [174,230]
  - Observation: A: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); C: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000061** (A→C, constraint)
  - Source: `Furthermore, it must be ensured through additions or deductions and through appropriate balance sheet items that other changes in the profit determination principles (e.g., regarding the commercial law principles of orderly bookkeeping when transitioning from profit determination pursuant to Section 4(1) or (3) to Section 5, or regarding the consideration of diminutions in the value of business assets when transitioning to bookkeeping) are taken into account upon the change in the profit determination method. 3. a) When transitioning to profit determination pursuant to Section 5, land must be revalued on a tax-neutral basis to the higher going-concern value.`
  - Gold: `through additions or deductions and through appropriate balance sheet items that other changes in the profit determination principles (e.g., regarding the commercial law principles of orderly bookkeeping when transitioning from profit determination pursuant to Section 4(1) or (3) to Section 5, or regarding the consideration of diminutions in the value of business assets when transitioning to bookkeeping) are taken into account upon the change in the profit determination method. 3. a) When transitioning to profit determination pursuant to Section 5, land must be revalued on a tax-neutral basis to the higher going-concern value` [32,665]
  - Baseline: []
  - Variant: `through additions or deductions and through appropriate balance sheet items` [32,107]; `upon the change in the profit determination method` [463,513]; `on a tax-neutral basis` [609,631]; `to the higher going-concern value` [632,665]
  - Observation: A: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); C: 4 predicted span(s), 0 unmatched, 0 missed Gold span(s).

### Constraint corrected by R_C: B -> D

- **estg_000030** (B→D, constraint)
  - Source: `(3) Income within the meaning of paragraph 1 items 10 and 11 shall be taken into account when determining the tax for the employee's other income.`
  - Gold: `within the meaning of paragraph 1 items 10 and 11` [11,60]
  - Baseline: []
  - Variant: `within the meaning of paragraph 1 items 10 and 11` [11,60]
  - Observation: B: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); D: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000031** (B→D, constraint)
  - Source: `(1) Profit is the difference, to be determined by double-entry bookkeeping, between the business assets at the end of the financial year and the business assets at the end of the preceding financial year.`
  - Gold: `to be determined by double-entry bookkeeping, between the business assets at the end of the financial year and the business assets at the end of the preceding financial year` [30,203]
  - Baseline: []
  - Variant: `to be determined by double-entry bookkeeping` [30,74]; `between the business assets at the end of the financial year and the business assets at the end of the preceding financial year` [76,203]
  - Observation: B: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); D: 2 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000033** (B→D, constraint)
  - Source: `Gains or losses from the disposal or withdrawal and other changes in value of land that is part of the fixed assets are not to be taken into account.`
  - Gold: `that is part of the fixed assets` [83,115]
  - Baseline: []
  - Variant: `from the disposal or withdrawal and other changes in value of land that is part of the fixed assets` [16,115]
  - Observation: B: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); D: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000040** (B→D, constraint)
  - Source: `Dependants also include spouses and children (Section 106). (ee) The contributions, together with direct benefits within the meaning of Section 3(1) item 15, must not exceed 10% of the total wages and salaries of the beneficiaries.`
  - Gold: `spouses and children (Section 106). (ee) The contributions, together with direct benefits within the meaning of Section 3(1) item 15, must not exceed 10% of the total wages and salaries of the beneficiaries` [24,230]
  - Baseline: []
  - Variant: `together with direct benefits within the meaning of Section 3(1) item 15` [84,156]
  - Observation: B: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); D: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s).
- **estg_000046** (B→D, constraint)
  - Source: `The certificate is not required if the invention is already protected by patent law. — The research allowance generally amounts to up to 12% of research expenditures. — An increased research allowance of up to 18% may be claimed if the inventions are not made available to other persons for substantial exploitation.`
  - Gold: `generally amounts to up to 12% of research expenditures. — An increased research allowance of up to 18%` [110,213]
  - Baseline: []
  - Variant: `up to 12% of research expenditures` [131,165]; `of up to 18%` [201,213]
  - Observation: B: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s); D: 2 predicted span(s), 0 unmatched, 0 missed Gold span(s).

## 13. Representative regressed cases

### Actor regressed by R_A: A -> B

- **estg_000285** (A→B, actor)
  - Source: `If a wage-structuring provision within the meaning of Section 68(5) items 1 to 6 contains a special rule on the definition of the term “business trip,” that rule shall be applied. 
a) The mileage allowance shall be taken into account at most at the rates applicable to federal employees. 
b) The daily allowance for domestic business trips may amount to up to ATS 240 per day.`
  - Gold: []
  - Baseline: []
  - Variant: `that rule` [152,161]; `The mileage allowance` [184,205]; `The daily allowance for domestic business trips` [292,339]
  - Observation: A: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s); B: 3 predicted span(s), 3 unmatched, 0 missed Gold span(s).
- **estg_000061** (A→B, actor)
  - Source: `Furthermore, it must be ensured through additions or deductions and through appropriate balance sheet items that other changes in the profit determination principles (e.g., regarding the commercial law principles of orderly bookkeeping when transitioning from profit determination pursuant to Section 4(1) or (3) to Section 5, or regarding the consideration of diminutions in the value of business assets when transitioning to bookkeeping) are taken into account upon the change in the profit determination method. 3. a) When transitioning to profit determination pursuant to Section 5, land must be revalued on a tax-neutral basis to the higher going-concern value.`
  - Gold: []
  - Baseline: []
  - Variant: `it` [13,15]
  - Observation: A: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s); B: 1 predicted span(s), 1 unmatched, 0 missed Gold span(s).
- **estg_000776** (A→B, actor)
  - Source: `An exercise of public authority shall be assumed in particular where services are involved the acceptance of which the recipient is obliged to accept by virtue of a statutory or official order.`
  - Gold: `the recipient` [115,128]
  - Baseline: `the recipient` [115,128]
  - Variant: []
  - Observation: A: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s); B: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s).

### Actor regressed by R_A: C -> D

- **estg_000037** (C→D, actor)
  - Source: `In any event, business expenses shall include:
1. a) contributions by the insured person to compulsory insurance in the statutory health, accident and pension insurance, and
b) compulsory contributions to welfare and support institutions of the chambers of self-employed persons, to the extent that these institutions serve health, old-age, invalidity and survivors’ provision.
2. a) contributions to pension funds subject to the following conditions:
aa) the fund must be subject to state supervision;
bb) the fund must grant a legal entitlement to benefits for the purpose of old-age and survivors’ provision.`
  - Gold: `the fund must be subject to state supervision;
bb) the fund` [456,515]
  - Baseline: `the fund` [456,464]; `the fund` [507,515]
  - Variant: `business expenses` [14,31]
  - Observation: C: 2 predicted span(s), 0 unmatched, 0 missed Gold span(s); D: 1 predicted span(s), 1 unmatched, 1 missed Gold span(s).
- **estg_000209** (C→D, actor)
  - Source: `Shares issued as a result of a capital increase are not eligible if the resolution on the increase of the share capital (Section 149(1) of the Stock Corporation Act 1965) was adopted within two years after the registration of the resolution on the reduction of the share capital for the purpose of repaying parts of the share capital (Section 177 of the Stock Corporation Act 1965); this also applies to capital reductions by a stock corporation or a limited liability company as the legal predecessor of the stock corporation (Sections 219 and 245 of the Stock Corporation Act 1965, Section 2 of the Federal Act on the Transformation of Commercial Companies, Federal Law Gazette).`
  - Gold: []
  - Baseline: []
  - Variant: `Shares issued as a result of a capital increase` [0,47]; `capital reductions by a stock corporation or a limited liability company as the legal predecessor of the stock corporation` [404,526]
  - Observation: C: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s); D: 2 predicted span(s), 2 unmatched, 0 missed Gold span(s).
- **estg_000285** (C→D, actor)
  - Source: `If a wage-structuring provision within the meaning of Section 68(5) items 1 to 6 contains a special rule on the definition of the term “business trip,” that rule shall be applied. 
a) The mileage allowance shall be taken into account at most at the rates applicable to federal employees. 
b) The daily allowance for domestic business trips may amount to up to ATS 240 per day.`
  - Gold: []
  - Baseline: []
  - Variant: `that rule` [152,161]; `The daily allowance for domestic business trips` [292,339]
  - Observation: C: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s); D: 2 predicted span(s), 2 unmatched, 0 missed Gold span(s).
- **estg_000004** (C→D, actor)
  - Source: `(7) A change of the fiscal year to a different closing date is only permissible if there are substantial business reasons and the tax office has given prior consent by official notice.`
  - Gold: []
  - Baseline: []
  - Variant: `the tax office` [126,140]
  - Observation: C: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s); D: 1 predicted span(s), 1 unmatched, 0 missed Gold span(s).
- **estg_000103** (C→D, actor)
  - Source: `If this list was not submitted to the tax office with the tax return, but it appears from the return or the annexes attached thereto that the taxpayer is forming a tax-exempt amount, the tax office shall set the taxpayer a grace period of two weeks for submission of the list.`
  - Gold: `the tax office` [183,197]
  - Baseline: `the tax office` [183,197]
  - Variant: []
  - Observation: C: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s); D: 0 predicted span(s), 0 unmatched, 1 missed Gold span(s).

### Constraint regressed by R_C: A -> C

- **estg_000393** (A→C, constraint)
  - Source: `(2) If the other income in total does not exceed the amount of 10,000 S, the carrying out of an assessment may be applied for if
1. the sum of the other income results in a loss (loss assessment), or
2. a loss deduction pursuant to Section 18(6) and (7) is available, or
3. in order to avoid double taxation, a foreign income tax paid is to be credited against the domestic income tax, or
4. the income includes income within the meaning of Section 3(1) item 10 or 11, or
5. the income includes income from capital subject to withholding tax.`
  - Gold: []
  - Baseline: []
  - Variant: `in total` [24,32]; `does not exceed the amount of 10,000 S` [33,71]; `pursuant to Section 18(6) and (7)` [220,253]; `in order to avoid double taxation` [274,307]; `within the meaning of Section 3(1) item 10 or 11` [419,467]; `subject to withholding tax` [515,541]
  - Observation: A: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s); C: 6 predicted span(s), 6 unmatched, 0 missed Gold span(s).
- **estg_000539** (A→C, constraint)
  - Source: `(2) If the conditions for carrying out an ex officio annual adjustment (paragraph 3) are not met, the tax office shall carry out an annual adjustment upon application of the employee if
1. the employer is not responsible pursuant to paragraph 1 or the employer issued a wage tax statement (Section 84) before carrying out an annual adjustment, or
2. the employee did not claim the sole earner deduction in due time, or
3. an allowance notice was issued or the employee claims income-related expenses, special expenses or extraordinary burdens, or
4. the child supplements to the sole earner deduction were not taken into account or not taken into full account.`
  - Gold: []
  - Baseline: []
  - Variant: `upon application of the employee` [150,182]; `before carrying out an annual adjustment` [302,342]; `in due time` [403,414]
  - Observation: A: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s); C: 3 predicted span(s), 3 unmatched, 0 missed Gold span(s).
- **estg_000109** (A→C, constraint)
  - Source: `For buildings intended for lease for consideration to third parties (excluding employees of the business), an investment allowance is only available if the exclusive business object is the commercial leasing of assets.`
  - Gold: `For buildings intended for lease for consideration to third parties` [0,67]
  - Baseline: `For buildings intended for lease for consideration to third parties (excluding employees of the business)` [0,105]
  - Variant: `only` [134,138]
  - Observation: A: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s); C: 1 predicted span(s), 1 unmatched, 1 missed Gold span(s).
- **estg_000004** (A→C, constraint)
  - Source: `(7) A change of the fiscal year to a different closing date is only permissible if there are substantial business reasons and the tax office has given prior consent by official notice.`
  - Gold: []
  - Baseline: []
  - Variant: `only` [63,67]
  - Observation: A: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s); C: 1 predicted span(s), 1 unmatched, 0 missed Gold span(s).
- **estg_000027** (A→C, constraint)
  - Source: `Section 25(1) items 7, 8, 8a, 9 of the Civilian Service Act 1986) only for part of the calendar year, the income as defined in Section 2(3) items 1 to 3 earned in the remainder of the calendar year and current income from employment as defined in Section 41(4) shall be converted to an annual amount for the purpose of determining the tax rate.`
  - Gold: `the income as defined in Section 2(3) items 1 to 3 earned in the remainder of the calendar year and current income from employment as defined in Section 41(4) shall be converted to an annual amount for the purpose of determining the tax rate` [102,343]
  - Baseline: `for the purpose of determining the tax rate` [300,343]
  - Variant: `only for part of the calendar year` [66,100]; `for the purpose of determining the tax rate` [300,343]
  - Observation: A: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s); C: 2 predicted span(s), 1 unmatched, 0 missed Gold span(s).

### Constraint regressed by R_C: B -> D

- **estg_000004** (B→D, constraint)
  - Source: `(7) A change of the fiscal year to a different closing date is only permissible if there are substantial business reasons and the tax office has given prior consent by official notice.`
  - Gold: []
  - Baseline: []
  - Variant: `only` [63,67]; `prior` [151,156]; `by official notice` [165,183]
  - Observation: B: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s); D: 3 predicted span(s), 3 unmatched, 0 missed Gold span(s).
- **estg_000786** (B→D, constraint)
  - Source: `Administrative expenses that are unrelated to the purpose of the bank and do not benefit any board member, managing director, or supervisory board member through disproportionately high remuneration. d) In the event of the dissolution of the bank, the owners or shareholders may not recover those capital contributions that are needed to cover losses from obligations arising from guarantees and other liabilities existing at the time of dissolution; the remaining assets of the bank may only be used within the scope of the approved business purpose. 4.`
  - Gold: `that are needed to cover losses from obligations arising from guarantees and other liabilities existing at the time of dissolution; the remaining assets of the bank may only be used within the scope of the approved business purpose` [319,550]
  - Baseline: `within the scope of the approved business purpose` [501,550]
  - Variant: `that are unrelated to the purpose of the bank` [24,69]; `do not benefit any board member, managing director, or supervisory board member through disproportionately high remuneration` [74,198]; `only` [488,492]; `within the scope of the approved business purpose` [501,550]
  - Observation: B: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s); D: 4 predicted span(s), 2 unmatched, 0 missed Gold span(s).
- **estg_000002** (B→D, constraint)
  - Source: `Bookkeeping farmers and foresters and registered traders (Section 5) may, however, have a business year deviating from the calendar year; in this case, the profit shall be taken into account in determining the income for that calendar year in which the business year ends.`
  - Gold: []
  - Baseline: []
  - Variant: `for that calendar year in which the business year ends` [217,271]
  - Observation: B: 0 predicted span(s), 0 unmatched, 0 missed Gold span(s); D: 1 predicted span(s), 1 unmatched, 0 missed Gold span(s).
- **estg_000027** (B→D, constraint)
  - Source: `Section 25(1) items 7, 8, 8a, 9 of the Civilian Service Act 1986) only for part of the calendar year, the income as defined in Section 2(3) items 1 to 3 earned in the remainder of the calendar year and current income from employment as defined in Section 41(4) shall be converted to an annual amount for the purpose of determining the tax rate.`
  - Gold: `the income as defined in Section 2(3) items 1 to 3 earned in the remainder of the calendar year and current income from employment as defined in Section 41(4) shall be converted to an annual amount for the purpose of determining the tax rate` [102,343]
  - Baseline: `for the purpose of determining the tax rate` [300,343]
  - Variant: `only for part of the calendar year` [66,100]; `for the purpose of determining the tax rate` [300,343]
  - Observation: B: 1 predicted span(s), 0 unmatched, 0 missed Gold span(s); D: 2 predicted span(s), 1 unmatched, 0 missed Gold span(s).
- **estg_000039** (B→D, constraint)
  - Source: `The agreement must provide that the taxpayer’s ongoing contribution payments may only be suspended or restricted for compelling economic reasons and only after consultation with the works council. dd) The contributions are deductible to the extent that they are required under the articles of association for benefit entitlements of current and former members of the taxpayer’s enterprises.`
  - Gold: `that the taxpayer’s ongoing contribution payments may only be suspended or restricted for compelling economic reasons and only after consultation with the works council` [27,195]
  - Baseline: `for compelling economic reasons` [113,144]; `only after consultation with the works council` [149,195]
  - Variant: `for compelling economic reasons` [113,144]; `only after consultation with the works council` [149,195]; `to the extent that they are required under the articles of association for benefit entitlements of current and former members of the taxpayer’s enterprises` [234,389]
  - Observation: B: 2 predicted span(s), 0 unmatched, 0 missed Gold span(s); D: 3 predicted span(s), 1 unmatched, 0 missed Gold span(s).

## 14. Failures / anomalies

- Failed calls: 0.
- Schedule deviations: 0.
- Config deviations: 0.
- Execution summary aborted: `False`; complete: `True`.

## 15. Artifact locations

- Run root: `outputs/development/sep_c3_targeted_refinement_v1`.
- A/B/C/D arm directories: `{'A': 'outputs/development/sep_c3_targeted_refinement_v1/A/repeat-01', 'B': 'outputs/development/sep_c3_targeted_refinement_v1/B/repeat-01', 'C': 'outputs/development/sep_c3_targeted_refinement_v1/C/repeat-01', 'D': 'outputs/development/sep_c3_targeted_refinement_v1/D/repeat-01'}`.
- Raw responses: `{'A': 'outputs/development/sep_c3_targeted_refinement_v1/A/repeat-01/raw_responses.jsonl', 'B': 'outputs/development/sep_c3_targeted_refinement_v1/B/repeat-01/raw_responses.jsonl', 'C': 'outputs/development/sep_c3_targeted_refinement_v1/C/repeat-01/raw_responses.jsonl', 'D': 'outputs/development/sep_c3_targeted_refinement_v1/D/repeat-01/raw_responses.jsonl'}`.
- Global execution ledger / final order: `outputs/development/sep_c3_targeted_refinement_v1/calls_ledger.jsonl`.
- Canonical predictions: `{'A': 'outputs/development/sep_c3_targeted_refinement_v1/A/repeat-01/canonical_predictions.jsonl', 'B': 'outputs/development/sep_c3_targeted_refinement_v1/B/repeat-01/canonical_predictions.jsonl', 'C': 'outputs/development/sep_c3_targeted_refinement_v1/C/repeat-01/canonical_predictions.jsonl', 'D': 'outputs/development/sep_c3_targeted_refinement_v1/D/repeat-01/canonical_predictions.jsonl'}`.
- Evaluation artifacts: `{'A': 'outputs/development/sep_c3_targeted_refinement_v1/A/repeat-01/evaluation.json', 'B': 'outputs/development/sep_c3_targeted_refinement_v1/B/repeat-01/evaluation.json', 'C': 'outputs/development/sep_c3_targeted_refinement_v1/C/repeat-01/evaluation.json', 'D': 'outputs/development/sep_c3_targeted_refinement_v1/D/repeat-01/evaluation.json'}`.
- Manifests: `{'A': 'outputs/development/sep_c3_targeted_refinement_v1/A/repeat-01/manifest.json', 'B': 'outputs/development/sep_c3_targeted_refinement_v1/B/repeat-01/manifest.json', 'C': 'outputs/development/sep_c3_targeted_refinement_v1/C/repeat-01/manifest.json', 'D': 'outputs/development/sep_c3_targeted_refinement_v1/D/repeat-01/manifest.json'}`.
- Full analysis JSON: `outputs/reports/sep_c3_targeted_refinement_v1_phase2_analysis.json`.
- Summary JSON: `outputs/reports/sep_c3_targeted_refinement_v1_phase2_summary.json`.

## 16. Git status / commit information

- Branch: `codex/b0-r1-a-span-boundaries`; pre-run HEAD: `009ca09f7c473c79a673fbd09a4e386236d0aac7`; post-run HEAD: `009ca09f7c473c79a673fbd09a4e386236d0aac7`.
- New commits: `[]`.
- `git status --short --branch` lines: 28.
- Working tree lines (first 30):
  - `## codex/b0-r1-a-span-boundaries...origin/codex/b0-r1-a-span-boundaries`
  - ` M formal_experiment/data/development/human_review/stage1_gdpr7_human_correction_v1.json`
  - ` M formal_experiment/outputs/evidence/s3_semantic_grounding_v2/llm_authorization_request_v1.json`
  - ` M formal_experiment/outputs/evidence/s3_semantic_grounding_v2/llm_preflight.json`
  - ` M formal_experiment/outputs/reports/s3_semantic_grounding_v2_arm_comparison.json`
  - ` M formal_experiment/outputs/reports/s3_semantic_grounding_v2_llm_authorization_request.json`
  - ` M formal_experiment/outputs/reports/s3_semantic_grounding_v2_llm_authorization_request.md`
  - ` M formal_experiment/outputs/reports/s3_semantic_grounding_v2_llm_preflight.json`
  - ` M formal_experiment/src/bpc_hybrid/s3_semantic_grounding_llm_v1.py`
  - `?? .codex_worktree_c36sep/`
  - `?? .patch_exec_cmd.py`
  - `?? .run_patch_exec_cmd.cmd`
  - `?? .tmp_probe/`
  - `?? "bpc_hybrid - 副本 (2).pptx"`
  - `?? formal_experiment/data/development/human_review/s2_11_review_decisions_v2.json.bak`
  - `?? formal_experiment/docs/research/THESIS_SUMMARY_AND_8_QUESTIONS_2026-09-12.md`
  - `?? formal_experiment/outputs/reports/s2_11_batch_import_dry_run_v3.json.bak`
  - `?? formal_experiment/outputs/reports/s2_12_execution_readiness_v3.json.bak`
  - `?? formal_experiment/outputs/reports/s2_13_s3_7_transition_readiness_v7.json.bak`
  - `?? formal_experiment/outputs/reports/s2_13_s3_7_transition_readiness_v7.manifest.json.bak`
  - `?? formal_experiment/outputs/reports/s2_13_s3_7_transition_readiness_v7.md.bak`
  - `?? formal_experiment/outputs/reports/s2_13_s3_7_transition_readiness_v7_export_index.json.bak`
  - `?? formal_experiment/outputs/reports/sep_c3_targeted_refinement_v1_execution.json`
  - `?? formal_experiment/outputs/reports/sep_c3_targeted_refinement_v1_phase2_analysis.json`
  - `?? formal_experiment/outputs/reports/sep_c3_targeted_refinement_v1_phase2_evidence.md`
  - `?? formal_experiment/outputs/reports/sep_c3_targeted_refinement_v1_phase2_summary.json`
  - `?? formal_experiment/paper/presentations/bpc_hybrid_revised_20260912.pptx`
  - `?? formal_experiment/scripts/analyze_sep_c3_targeted_refinement_v1.py`

*This report is descriptive. It does not modify the frozen prompts, Gold, evaluator, parser, canonicalizer, or dataset and does not state a research conclusion.*
