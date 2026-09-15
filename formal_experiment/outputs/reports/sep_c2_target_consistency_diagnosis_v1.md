# SEP-C2 target-consistency diagnosis (10 evaluated methods, EStG-150)

- report_id: `sep_c2_target_consistency_diagnosis_v1`
- status: **completed_10_evaluated_one_source_pending**
- primary table source: `outputs/reports/sep_c2_sun_predecessors_comparison_v2.json`
- evaluator: `bpc_hybrid.formal_stage2_evaluation.evaluate_modality_labels`
- The full-150 first-clause table remains primary; this report adds target-structure and error-attribution analysis.

## 1. One-sentence conclusion

No prediction-code error was found in the 10 evaluated methods; the only confirmed reporting error was counting the not-run bert_legal_cased configuration as 150 failed model runs, now corrected. The full-150 first-clause table is valid under the frozen protocol, but 49/150 multi-clause records and 34/150 heterogeneous-label records make the full-text-vs-first-clause target construction an explicit interpretation limit.

## 2. Full-150 classification main table (10 evaluated methods)

| method | acc | macro-F1 | scored | missing | failed | unlabeled | input | status |
|---|---:|---:|---:|---:|---:|---:|---|---|
| cf_kw | 0.6200 | 0.5322 | 150 | 0 | 0 | 0 | `raw_text_de` | completed_zero_api |
| cf_rnn | 0.5667 | 0.4800 | 150 | 0 | 0 | 0 | `raw_text_de` | completed_zero_api |
| cf_cnn | 0.6733 | 0.6177 | 150 | 0 | 0 | 0 | `raw_text_de` | completed_zero_api |
| bert_base_uncased | 0.4467 | 0.3507 | 150 | 0 | 0 | 0 | `raw_text_de` | completed_zero_api |
| bert_base_cased | 0.5733 | 0.4529 | 150 | 0 | 0 | 0 | `raw_text_de` | completed_zero_api |
| bert_large_uncased | 0.5733 | 0.5245 | 150 | 0 | 0 | 0 | `raw_text_de` | completed_zero_api |
| bert_large_cased | 0.6600 | 0.6024 | 150 | 0 | 0 | 0 | `raw_text_de` | completed_zero_api |
| bert_legal_uncased | 0.4800 | 0.4057 | 150 | 0 | 0 | 0 | `raw_text_de` | completed_zero_api |
| sun_rule_only | 0.7400 | 0.7128 | 150 | 0 | 0 | 0 | `raw_text_de (classifier) + approved_text_en (phrases)` | existing_formal_arm_reused_zero_api |
| direct_llm | 0.8333 | 0.7695 | 150 | 0 | 0 | 1 | `approved_text_en` | existing_formal_arm_reused_zero_api |

**Source-pending row (not a failure, not in the 10-method denominator):** `bert_legal_cased` status=`not_run_source_pending_exact_checkpoint_unavailable`, records_failed=0, records_not_run=150, included_in_performance_denominator=False.

## 3. 150-record target structure

| group | n | definition |
|---|---:|---|
| A | 101 | exactly one valid Gold clause |
| B | 15 | multiple valid Gold clauses, same modality label |
| C | 34 | multiple valid Gold clauses, different modality labels |

- valid Gold records: 150/150; no valid label: 0
- clause-count distribution: `{'1': 101, '2': 27, '3': 14, '4': 7, '6': 1}`
- first-clause label support: `{'definition': 29, 'obligation': 59, 'permission': 42, 'prohibition': 20}`
- first clause starts at 0: 141/150; covers full sentence: 26/150
- first clause char length: `{'p50': 195, 'p90': 381, 'max': 906}`
- overlapping clause-span records: 9 (`['estg_000020', 'estg_000037', 'estg_000039', 'estg_000077', 'estg_000082', 'estg_000136', 'estg_000347', 'estg_000776', 'estg_000854']`)
- clause order not sorted by start: 1 (`['estg_000136']`)

### Group A/B/C first-label support

| group | n | first-label support | clause-count distribution | start=0 | covers full |
|---|---:|---|---|---:|---:|
| A | 101 | `{'definition': 14, 'obligation': 42, 'permission': 34, 'prohibition': 11}` | `{'1': 101}` | 96 | 25 |
| B | 15 | `{'definition': 3, 'obligation': 8, 'permission': 1, 'prohibition': 3}` | `{'2': 11, '3': 2, '4': 2}` | 14 | 0 |
| C | 34 | `{'definition': 12, 'obligation': 9, 'permission': 7, 'prohibition': 6}` | `{'2': 16, '3': 12, '4': 5, '6': 1}` | 31 | 1 |

## 4. Per-method group metrics

Macro-F1 is the frozen four-class macro over the subgroup.

| method | group | n | acc | macro-F1 | errors | unlabeled | first-wrong matches later | any-Gold-clause acc |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| cf_kw | A | 101 | 0.7228 | 0.5785 | 28 | 0 | 0 | 0.7228 |
| cf_kw | B | 15 | 0.5333 | 0.5169 | 7 | 0 | 0 | 0.5333 |
| cf_kw | C | 34 | 0.3529 | 0.3404 | 22 | 0 | 17 | 0.8529 |
| cf_rnn | A | 101 | 0.6238 | 0.5523 | 38 | 0 | 0 | 0.6238 |
| cf_rnn | B | 15 | 0.5333 | 0.4444 | 7 | 0 | 0 | 0.5333 |
| cf_rnn | C | 34 | 0.4118 | 0.2753 | 20 | 0 | 9 | 0.6765 |
| cf_cnn | A | 101 | 0.7327 | 0.6597 | 27 | 0 | 0 | 0.7327 |
| cf_cnn | B | 15 | 0.8667 | 0.8520 | 2 | 0 | 0 | 0.8667 |
| cf_cnn | C | 34 | 0.4118 | 0.3238 | 20 | 0 | 8 | 0.6471 |
| bert_base_uncased | A | 101 | 0.4455 | 0.3428 | 56 | 0 | 0 | 0.4455 |
| bert_base_uncased | B | 15 | 0.4000 | 0.2404 | 9 | 0 | 0 | 0.4000 |
| bert_base_uncased | C | 34 | 0.4706 | 0.3667 | 18 | 0 | 7 | 0.6765 |
| bert_base_cased | A | 101 | 0.5941 | 0.4457 | 41 | 0 | 0 | 0.5941 |
| bert_base_cased | B | 15 | 0.6667 | 0.5333 | 5 | 0 | 0 | 0.6667 |
| bert_base_cased | C | 34 | 0.4706 | 0.3794 | 18 | 0 | 6 | 0.6471 |
| bert_large_uncased | A | 101 | 0.5941 | 0.4910 | 41 | 0 | 0 | 0.5941 |
| bert_large_uncased | B | 15 | 0.5333 | 0.4167 | 7 | 0 | 0 | 0.5333 |
| bert_large_uncased | C | 34 | 0.5294 | 0.4721 | 16 | 0 | 10 | 0.8235 |
| bert_large_cased | A | 101 | 0.6931 | 0.6194 | 31 | 0 | 0 | 0.6931 |
| bert_large_cased | B | 15 | 0.6000 | 0.4554 | 6 | 0 | 0 | 0.6000 |
| bert_large_cased | C | 34 | 0.5882 | 0.5696 | 14 | 0 | 10 | 0.8824 |
| bert_legal_uncased | A | 101 | 0.4851 | 0.4208 | 52 | 0 | 0 | 0.4851 |
| bert_legal_uncased | B | 15 | 0.4000 | 0.2404 | 9 | 0 | 0 | 0.4000 |
| bert_legal_uncased | C | 34 | 0.5000 | 0.3650 | 17 | 0 | 7 | 0.7059 |
| sun_rule_only | A | 101 | 0.7921 | 0.7349 | 21 | 0 | 0 | 0.7921 |
| sun_rule_only | B | 15 | 0.6667 | 0.7397 | 5 | 0 | 0 | 0.6667 |
| sun_rule_only | C | 34 | 0.6176 | 0.6235 | 13 | 0 | 8 | 0.8529 |
| direct_llm | A | 101 | 0.9307 | 0.9030 | 7 | 1 | 0 | 0.9307 |
| direct_llm | B | 15 | 0.7333 | 0.6250 | 4 | 0 | 0 | 0.7333 |
| direct_llm | C | 34 | 0.5882 | 0.5623 | 14 | 0 | 8 | 0.8235 |

## 5. Target-misalignment quantification

- multi-clause records: 49/150; heterogeneous-label C: 34/150.
- A/B errors cannot be explained by matching a later different clause label. In C, later-match counts are an upper-bound clue, not proof of decoding a later clause.

| method | A errors | B errors | C errors | C first errors matching later | C exact-first acc | C any-Gold-clause acc |
|---|---:|---:|---:|---:|---:|---:|
| cf_kw | 28 | 7 | 22 | 17 | 0.3529 | 0.8529 |
| cf_rnn | 38 | 7 | 20 | 9 | 0.4118 | 0.6765 |
| cf_cnn | 27 | 2 | 20 | 8 | 0.4118 | 0.6471 |
| bert_base_uncased | 56 | 9 | 18 | 7 | 0.4706 | 0.6765 |
| bert_base_cased | 41 | 5 | 18 | 6 | 0.4706 | 0.6471 |
| bert_large_uncased | 41 | 7 | 16 | 10 | 0.5294 | 0.8235 |
| bert_large_cased | 31 | 6 | 14 | 10 | 0.5882 | 0.8824 |
| bert_legal_uncased | 52 | 9 | 17 | 7 | 0.5000 | 0.7059 |
| sun_rule_only | 21 | 5 | 13 | 8 | 0.6176 | 0.8529 |
| direct_llm | 7 | 4 | 14 | 8 | 0.5882 | 0.8235 |

## 6. Representative cases

Selection rule: Stratified purposeful cases fixed before report rendering in CASE_SPECS: wrong-but-later-match, same-label-group error, correct-first with later variation, and low-frequency-class error, across keyword/CF/BERT/project families.

### C_first_wrong_pred_matches_later | cf_kw | estg_000028

- group: `C`; Gold first/all: `obligation` / `['obligation', 'prohibition']`; predicted: `prohibition`
- interpretation: Prediction equals a later Gold clause label; this is a clue, not proof that the model decoded that later clause.

**Raw German excerpt:**

```text
Das Einkommen ist mit jenem Steuersatz zu besteuern, der sich unter Berücksichtigung der umgerechneten Einkünfte ergibt; die festzuset- zende Steuer darf jedoch nicht höher sein als jene, die sich bei Besteuerung sämtlicher Bezüge ergeben würde.
```

**Approved English excerpt:**

```text
The income shall be taxed at the tax rate that results when taking into account the converted income; however, the tax to be assessed may not be higher than that which would result from the taxation of all emoluments.
```

**Gold clauses:**
- `c1` [0,100) obligation: The income shall be taxed at the tax rate that results when taking into account the converted income
- `c2` [102,216) prohibition: however, the tax to be assessed may not be higher than that which would result from the taxation of all emoluments

**Code paths:**
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_gold`
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_attempt`
- `src/bpc_hybrid/formal_stage2_evaluation.py::evaluate_modality_labels`
- `outputs/evidence/sep_c2_sun_predecessors_v1/cf_kw/predictions.json`

### C_first_wrong_pred_matches_later | cf_cnn | estg_000046

- group: `C`; Gold first/all: `permission` / `['permission', 'definition', 'permission']`; predicted: `definition`
- interpretation: Prediction equals a later Gold clause label; this is a clue, not proof that the model decoded that later clause.

**Raw German excerpt:**

```text
Die Bescheinigung ist nicht erforderlich, wenn die Erfindung bereits patentrechtlich geschützt ist. — Der Forschungsfreibetrag beträgt grund- sätzlich bis zu 12% der Forschungsauf- wendungen. — Ein erhöhter Forschungsfreibetrag bis zu 18% kann geltend gemacht werden, wenn die Erfindungen nicht anderen Personen zur wesentlichen Verwertung überlassen werden.
```

**Approved English excerpt:**

```text
The certificate is not required if the invention is already protected by patent law. — The research allowance generally amounts to up to 12% of research expenditures. — An increased research allowance of up to 18% may be claimed if the inventions are not made available to other persons for substantial exploitation.
```

**Gold clauses:**
- `c1` [0,84) permission: The certificate is not required if the invention is already protected by patent law.
- `c2` [87,166) definition: The research allowance generally amounts to up to 12% of research expenditures.
- `c3` [169,316) permission: An increased research allowance of up to 18% may be claimed if the inventions are not made available to other persons for substantial exploitation.

**Code paths:**
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_gold`
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_attempt`
- `src/bpc_hybrid/formal_stage2_evaluation.py::evaluate_modality_labels`
- `outputs/evidence/sep_c2_sun_predecessors_v1/cf_cnn/predictions.json`

### C_first_wrong_pred_matches_later | bert_large_cased | estg_000039

- group: `C`; Gold first/all: `obligation` / `['obligation', 'permission', 'permission']`; predicted: `permission`
- interpretation: Prediction equals a later Gold clause label; this is a clue, not proof that the model decoded that later clause.

**Raw German excerpt:**

```text
Die Vereinbarung muß regeln, daß die laufenden Beitragslei- stungen des Steuerpflichtigen nur aus zwingenden wirtschaftlichen Grün- den und nur nach Beratung mit dem Betriebsrat ausgesetzt oder einge- schränkt werden können. dd) Die Beiträge sind abzugsfähig, soweit sie satzungsmäßig für Leistungsan- sprüche der Zugehörigen und frühe- ren Zugehörigen der Betriebe des Steuerpflichtigen vorgeschrieben sind.
```

**Approved English excerpt:**

```text
The agreement must provide that the taxpayer’s ongoing contribution payments may only be suspended or restricted for compelling economic reasons and only after consultation with the works council. dd) The contributions are deductible to the extent that they are required under the articles of association for benefit entitlements of current and former members of the taxpayer’s enterprises.
```

**Gold clauses:**
- `c1` [0,196) obligation: The agreement must provide that the taxpayer’s ongoing contribution payments may only be suspended or restricted for compelling economic reasons and only after consultation with the works council.
- `c2` [32,195) permission: the taxpayer’s ongoing contribution payments may only be suspended or restricted for compelling economic reasons and only after consultation with the works council
- `c3` [197,390) permission: dd) The contributions are deductible to the extent that they are required under the articles of association for benefit entitlements of current and former members of the taxpayer’s enterprises.

**Code paths:**
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_gold`
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_attempt`
- `src/bpc_hybrid/formal_stage2_evaluation.py::evaluate_modality_labels`
- `outputs/evidence/sep_c2_sun_predecessors_v1/bert_large_cased/predictions.json`

### C_first_wrong_pred_matches_later | sun_rule_only | estg_000020

- group: `C`; Gold first/all: `definition` / `['definition', 'prohibition', 'obligation']`; predicted: `prohibition`
- interpretation: Prediction equals a later Gold clause label; this is a clue, not proof that the model decoded that later clause.

**Raw German excerpt:**

```text
Voraussetzung für die Steuerbefreiung ist, daß der Haustrunk vom Arbeitnehmer nicht verkauft werden darf und daß er nur in einer solchen Menge gewährt wird, die einen Verkauf tatsächlich ausschließt. 20.
```

**Approved English excerpt:**

```text
A prerequisite for the tax exemption is that the free drink allowance may not be sold by the employee and that it is only granted in such quantity as to actually preclude a sale. 20.
```

**Gold clauses:**
- `c1` [0,177) definition: A prerequisite for the tax exemption is that the free drink allowance may not be sold by the employee and that it is only granted in such quantity as to actually preclude a sale
- `c2` [45,101) prohibition: the free drink allowance may not be sold by the employee
- `c3` [111,177) obligation: it is only granted in such quantity as to actually preclude a sale

**Code paths:**
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_gold`
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_attempt`
- `src/bpc_hybrid/formal_stage2_evaluation.py::evaluate_modality_labels`
- `data/predictions/b0_formal_arm_v1/predictions.json`

### C_first_wrong_pred_matches_later | direct_llm | estg_000020

- group: `C`; Gold first/all: `definition` / `['definition', 'prohibition', 'obligation']`; predicted: `prohibition`
- interpretation: Prediction equals a later Gold clause label; this is a clue, not proof that the model decoded that later clause.

**Raw German excerpt:**

```text
Voraussetzung für die Steuerbefreiung ist, daß der Haustrunk vom Arbeitnehmer nicht verkauft werden darf und daß er nur in einer solchen Menge gewährt wird, die einen Verkauf tatsächlich ausschließt. 20.
```

**Approved English excerpt:**

```text
A prerequisite for the tax exemption is that the free drink allowance may not be sold by the employee and that it is only granted in such quantity as to actually preclude a sale. 20.
```

**Gold clauses:**
- `c1` [0,177) definition: A prerequisite for the tax exemption is that the free drink allowance may not be sold by the employee and that it is only granted in such quantity as to actually preclude a sale
- `c2` [45,101) prohibition: the free drink allowance may not be sold by the employee
- `c3` [111,177) obligation: it is only granted in such quantity as to actually preclude a sale

**Code paths:**
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_gold`
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_attempt`
- `src/bpc_hybrid/formal_stage2_evaluation.py::evaluate_modality_labels`
- `data/predictions/direct_llm_formal_arm_v1/predictions.json`

### B_all_clauses_same_but_first_wrong | cf_kw | estg_000056

- group: `B`; Gold first/all: `obligation` / `['obligation', 'obligation', 'obligation', 'obligation']`; predicted: `prohibition`
- interpretation: All Gold clauses share one label, so a later different label cannot explain this error.

**Raw German excerpt:**

```text
(7) Bei Gebäuden, die zum Anlagevermögen gehören und Personen, die nicht betriebszugehö- rige Arbeitnehmer sind, für Wohnzwecke entgelt- lich überlassen werden, gilt hinsichtlich der Instandsetzungsaufwendungen folgendes: — Instandsetzungsaufwendungen, die unter Verwendung von entsprechend gewidmeten steuerfreien Subventionen aus öffentlichen Mitteln (§ 3 Abs. 1 Z 3, § 3 Abs. 1 Z 5 lit. d und e, § 3 Abs. 1 Z 6) aufgewendet werden, scheiden insoweit aus der Gewinnermittlung aus. — Sind nach Verrechnung der ohne Berücksich- tigung der Instandsetzungsaufwendungen ermittelten Verluste im Sinne des § 11 Abs. 1 Z 3 noch steuerfreie Rücklagen nach § 11 vorhanden, dann sind die nicht durch steuer- freie Subventionen abgedeckten Instandset- zungsaufwendungen mit diesen steuerfreien Rücklagen zu verrechnen. — Jene Instandsetzungsaufwendungen, die nicht durch steuerfreie Subventionen abge- deckt und nicht mit steuerfreien Rücklagen zu verrechnen waren, sind gleichmäßig auf zehn Jahre verteilt abzusetzen.
```

**Approved English excerpt:**

```text
(7) For buildings that form part of the fixed assets and are let for consideration for residential purposes to persons who are not employees of the enterprise, the following shall apply with regard to repair expenses:
— Repair expenses that are incurred using correspondingly earmarked tax-free subsidies from public funds (Section 3(1) item 3, Section 3(1) item 5 subitems d and e, Section 3(1) item 6) shall, to that extent, be excluded from the profit determination.
— If, after offsetting the losses within the meaning of Section 11(1) item 3 determined without taking into account the repair expenses, tax-free reserves under Section 11 still exist, the repair expenses not covered by tax-free subsidies shall be offset against these tax-free reserves.
— Those repair expenses that were not covered by tax-free subsidies and were not to be offset against tax-free reserves shall be deducted in equal installments over ten years.
```

**Gold clauses:**
- `c1` [0,217) obligation: (7) For buildings that form part of the fixed assets and are let for consideration for residential purposes to persons who are not employees of the enterprise, the following shall apply with regard to repair expenses:
- `c2` [220,469) obligation: Repair expenses that are incurred using correspondingly earmarked tax-free subsidies from public funds (Section 3(1) item 3, Section 3(1) item 5 subitems d and e, Section 3(1) item 6) shall, to that extent, be excluded f
- `c3` [472,757) obligation: If, after offsetting the losses within the meaning of Section 11(1) item 3 determined without taking into account the repair expenses, tax-free reserves under Section 11 still exist, the repair expenses not covered by ta
- `c4` [760,933) obligation: Those repair expenses that were not covered by tax-free subsidies and were not to be offset against tax-free reserves shall be deducted in equal installments over ten years.

**Code paths:**
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_gold`
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_attempt`
- `src/bpc_hybrid/formal_stage2_evaluation.py::evaluate_modality_labels`
- `outputs/evidence/sep_c2_sun_predecessors_v1/cf_kw/predictions.json`

### B_all_clauses_same_but_first_wrong | direct_llm | estg_000083

- group: `B`; Gold first/all: `definition` / `['definition', 'definition']`; predicted: `prohibition`
- interpretation: All Gold clauses share one label, so a later different label cannot explain this error.

**Raw German excerpt:**

```text
Dies gilt nicht, wenn die Vorsteuer nach §12 Abs. 10 und 11 des Umsatzsteuergesetzes 1972 berichtigt wird; in diesem Fall sind die Mehrbeträge als Betriebseinnahmen und die Minderbeträge als Betriebsausgaben zu behandeln. 13.
```

**Approved English excerpt:**

```text
This does not apply if the input tax is adjusted under Section 12(10) and (11) of the Turnover Tax Act 1972; in this case, the additional amounts shall be treated as business income and the reduced amounts as business expenses. 13.
```

**Gold clauses:**
- `c1` [0,107) definition: This does not apply if the input tax is adjusted under Section 12(10) and (11) of the Turnover Tax Act 1972
- `c2` [109,227) definition: in this case, the additional amounts shall be treated as business income and the reduced amounts as business expenses.

**Code paths:**
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_gold`
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_attempt`
- `src/bpc_hybrid/formal_stage2_evaluation.py::evaluate_modality_labels`
- `data/predictions/direct_llm_formal_arm_v1/predictions.json`

### C_first_correct_with_later_different | bert_large_cased | estg_000020

- group: `C`; Gold first/all: `definition` / `['definition', 'prohibition', 'obligation']`; predicted: `definition`
- interpretation: The first-clause label is correct even though later clauses have different labels.

**Raw German excerpt:**

```text
Voraussetzung für die Steuerbefreiung ist, daß der Haustrunk vom Arbeitnehmer nicht verkauft werden darf und daß er nur in einer solchen Menge gewährt wird, die einen Verkauf tatsächlich ausschließt. 20.
```

**Approved English excerpt:**

```text
A prerequisite for the tax exemption is that the free drink allowance may not be sold by the employee and that it is only granted in such quantity as to actually preclude a sale. 20.
```

**Gold clauses:**
- `c1` [0,177) definition: A prerequisite for the tax exemption is that the free drink allowance may not be sold by the employee and that it is only granted in such quantity as to actually preclude a sale
- `c2` [45,101) prohibition: the free drink allowance may not be sold by the employee
- `c3` [111,177) obligation: it is only granted in such quantity as to actually preclude a sale

**Code paths:**
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_gold`
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_attempt`
- `src/bpc_hybrid/formal_stage2_evaluation.py::evaluate_modality_labels`
- `outputs/evidence/sep_c2_sun_predecessors_v1/bert_large_cased/predictions.json`

### low_frequency_class_error | cf_cnn | estg_000003

- group: `A`; Gold first/all: `permission` / `['permission']`; predicted: `definition`
- interpretation: Low-frequency class error; report together with the official train prior shift, not as a code defect.

**Raw German excerpt:**

```text
Einen kürzeren Zeitraum darf es dann umfassen, wenn 1. ein Betrieb eröffnet oder aufgegeben wird oder 2. das Wirtschaftsjahr bei einem buchführenden Land- und Forstwirt oder einem protokollier- ten Gewerbetreibenden auf einen anderen Stichtag umgestellt wird.
```

**Approved English excerpt:**

```text
It may cover a shorter period if
1. a business is opened or closed, or
2. the business year of a bookkeeping farmer or forester or a registered trader is changed to a different closing date.
```

**Gold clauses:**
- `estg_000003_c01` [0,194) permission: It may cover a shorter period if
1. a business is opened or closed, or
2. the business year of a bookkeeping farmer or forester or a registered trader is changed to a different closing date.

**Code paths:**
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_gold`
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_attempt`
- `src/bpc_hybrid/formal_stage2_evaluation.py::evaluate_modality_labels`
- `outputs/evidence/sep_c2_sun_predecessors_v1/cf_cnn/predictions.json`

### low_frequency_class_error | sun_rule_only | estg_000004

- group: `A`; Gold first/all: `permission` / `['permission']`; predicted: `definition`
- interpretation: Low-frequency class error; report together with the official train prior shift, not as a code defect.

**Raw German excerpt:**

```text
(7) Die Umstellung des Wirtschaftsjahres auf einen anderen Stichtag ist nur zulässig, wenn gewichtige betriebliche Gründe vorliegen und das Finanzamt vorher bescheidmäßig zugestimmt hat.
```

**Approved English excerpt:**

```text
(7) A change of the fiscal year to a different closing date is only permissible if there are substantial business reasons and the tax office has given prior consent by official notice.
```

**Gold clauses:**
- `estg_000004_c01` [0,184) permission: (7) A change of the fiscal year to a different closing date is only permissible if there are substantial business reasons and the tax office has given prior consent by official notice.

**Code paths:**
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_gold`
- `src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_attempt`
- `src/bpc_hybrid/formal_stage2_evaluation.py::evaluate_modality_labels`
- `data/predictions/b0_formal_arm_v1/predictions.json`

## 7. Implementation audit

### source_pending_not_counted_as_failure

- status: `confirmed_reporting_error_corrected_in_this_report`
- action: Separate bert_legal_cased as source-pending; exclude it from the 10-method denominator and from failure counts.
- evidence: `{"action": "Separate bert_legal_cased as source-pending; exclude it from the 10-method denominator and from failure counts.", "corrected_records_failed": 0, "corrected_records_not_run": 150, "id": "source_pending_not_counted_as_failure", "included_in_10_method_performance_denominator": false, "status": "confirmed_reporting_error_corrected_in_this_report", "v2_records_failed": 150, "v2_records_missing": 150}`

### label_mapping_and_class_order

- status: `checked_no_model_code_error_found`
- action: No label-index inversion or class-order divergence found.
- evidence: `{"action": "No label-index inversion or class-order divergence found.", "bert_labels": ["definition", "obligation", "permission", "prohibition"], "formal_evaluator_classes": ["obligation", "permission", "prohibition", "definition"], "id": "label_mapping_and_class_order", "neural_labels": ["definition", "obligation", "permission", "prohibition"], "sets_equal": true, "status": "checked_no_model_code_error_found"}`

### first_clause_selection

- status: `checked_contract_consistent_but_target_construction_condition`
- action: Evaluator uses first non-empty label in record order, matching G0.4. The whole-text training vs first-clause target remains an interpretation limit.
- evidence: `{"action": "Evaluator uses first non-empty label in record order, matching G0.4. The whole-text training vs first-clause target remains an interpretation limit.", "gold_unsorted_sample_ids": ["estg_000136"], "id": "first_clause_selection", "prediction_nonzero_first_index": {"bert_base_cased": 0, "bert_base_uncased": 0, "bert_large_cased": 0, "bert_large_uncased": 0, "bert_legal_uncased": 0, "cf_cnn": 0, "cf_kw": 0, "cf_rnn": 0, "direct_llm": 0, "sun_rule_only": 0}, "status": "checked_contract_consistent_but_target_construction_condition"}`

### truncation_audit

- status: `checked_condition_not_code_error`
- action: CF_RNN/CF_CNN have max 188 word tokens (<192); BERT right-truncates 25-31/150 records at 192 subword tokens; exact German first-clause truncation cannot be mapped because Gold spans are English.
- evidence: `{"action": "CF_RNN/CF_CNN have max 188 word tokens (<192); BERT right-truncates 25-31/150 records at 192 subword tokens; exact German first-clause truncation cannot be mapped because Gold spans are English.", "id": "truncation_audit", "status": "checked_condition_not_code_error"}`

### missing_and_denominator

- status: `checked_no_model_code_error_found`
- action: Full 150 denominator preserved; the single Direct-LLM empty-clause prediction is counted as an error, not dropped.
- evidence: `{"action": "Full 150 denominator preserved; the single Direct-LLM empty-clause prediction is counted as an error, not dropped.", "id": "missing_and_denominator", "records_failed": {"bert_base_cased": 0, "bert_base_uncased": 0, "bert_large_cased": 0, "bert_large_uncased": 0, "bert_legal_uncased": 0, "cf_cnn": 0, "cf_kw": 0, "cf_rnn": 0, "direct_llm": 0, "sun_rule_only": 0}, "records_scored": {"bert_base_cased": 150, "bert_base_uncased": 150, "bert_large_cased": 150, "bert_large_uncased": 150, "bert_legal_uncased": 150, "cf_cnn": 150, "cf_kw": 150, "cf_rnn": 150, "direct_llm": 150, "sun_rule_only": 150}, "status": "checked_no_model_code_error_found", "unlabeled": {"bert_base_cased": 0, "bert_base_uncased": 0, "bert_large_cased": 0, "bert_large_uncased": 0, "bert_legal_uncased": 0, "cf_cnn": 0, "cf_kw": 0, "cf_rnn": 0, "direct_llm": 1, "sun_rule_only": 0}}`

### gold_used_for_prediction

- status: `checked_no_model_code_error_found`
- action: Runner code builds attempts before evaluation.evaluate_attempts; only evaluation loads Gold. No Gold leakage was found.
- evidence: `{"action": "Runner code builds attempts before evaluation.evaluate_attempts; only evaluation loads Gold. No Gold leakage was found.", "id": "gold_used_for_prediction", "prediction_entrypoints": ["src/bpc_hybrid/sun_predecessors/runner.py", "src/bpc_hybrid/sun_predecessors/runner_neural.py", "src/bpc_hybrid/sun_predecessors/runner_bert_full.py"], "status": "checked_no_model_code_error_found"}`

### language_and_class_prior_conditions

- status: `checked_experiment_condition_not_code_error`
- action: German/English and sentence-level vs first-clause differences remain confounded with architecture; report, do not claim a pure architecture effect.
- evidence: `{"action": "German/English and sentence-level vs first-clause differences remain confounded with architecture; report, do not claim a pure architecture effect.", "id": "language_and_class_prior_conditions", "language_effect_separable": false, "status": "checked_experiment_condition_not_code_error"}`

## 8. Paper-ready setting, interpretation and limitation

实验设置新增目标结构审计：150 条按有效 Gold clause 分成 A（单一有效 clause，101/150）、B（多个 clause 但标签相同，15/150）、C（多个 clause 且标签不同，34/150）。评价器固定读取每个 record 的首个非空 modality 标签，符合 G0.4 合同；但八种前人分类器都在句子级 EStG modality 数据上训练并输出单一整句标签，因此 C 组存在全文分类与首个 Gold clause 目标不对齐的问题。结果解释仍以完整 150 条 first-clause 主表为准，预测命中任意 Gold clause 的上界诊断，不能据此断言模型预测了后续 clause。限制：bert_legal_cased 记为 source-pending 而非失败；德/英输入、训练目标和类别先验差异尚不能分离，不能仅凭本表证明架构的纯粹优势。

## 9. Safety

- new_llm_api_calls: `0`
- new_paid_api_calls: `0`
- new_model_training_runs: `0`
- gold_used_for_prediction: `False`
- gold_used_for_evaluation_only: `True`
- post_result_tuning: `False`
- full_150_denominator_preserved: `True`
- source_pending_counted_as_failure: `False`
