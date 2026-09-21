# Gold conflict audit (read-only, zero API)

- gold: `formal_experiment\data\gold\stage2\estg150_formal_gold_v1.json` sha256 `c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100`
- panel: `formal_experiment\data\gold\stage3\stage3_violation_gold_v1.json` sha256 `54245ef0d102ae5e7a44e8c45424ecd9e86e1e0d9ed43ac1a9cd43641c981550`
- clauses scanned: 231  ·  records: 150
- new API calls: **0**  ·  artifacts modified: **0**

> Purpose: produce human-review queues only. Nothing here changes Gold,
> predictions, prompts or the evaluator. Every finding requires human
> adjudication against the source text before any action is taken.

## L1 — same cue, non-uniform Gold field assignment

### `only`  ->  action, condition, constraint, exception

| field | count | example span |
|---|---:|---|
| SENTENCE_ONLY | 21 | — |
| constraint | 5 | `that the taxpayer’s ongoing contribution payments may only be suspended or restr` (estg_000039) |
| action | 4 | `is only granted` (estg_000020) |
| condition | 2 | `only if the management or the registered office is located in the domestic terri` (estg_000131) |
| MULTI:action+condition | 1 | — |
| exception | 1 | `unless they relate only to the current and the following year` (estg_000055) |

### `pursuant_to`  ->  action, condition, constraint, exception

| field | count | example span |
|---|---:|---|
| condition | 13 | `When transitioning to profit determination pursuant to Section 5` (estg_000061) |
| SENTENCE_ONLY | 8 | — |
| constraint | 4 | `that other changes in the profit determination principles (e.g., regarding the c` (estg_000061) |
| exception | 1 | `to the extent that they are not to be taxed pursuant to subsection (6) at the ta` (estg_000507) |
| MULTI:condition+constraint | 1 | — |
| action | 1 | `permit that the tax-exempt income components pursuant to Section 3 and the incom` (estg_000569) |

### `that_rel`  ->  action, condition, constraint, exception

| field | count | example span |
|---|---:|---|
| SENTENCE_ONLY | 41 | — |
| condition | 27 | `to the extent that they are required under the articles of association for benef` (estg_000039) |
| constraint | 15 | `in such a quantity that actually precludes a sale` (estg_000021) |
| action | 6 | `the profit shall be taken into account in determining the income for that calend` (estg_000002) |
| MULTI:condition+constraint | 4 | — |
| MULTI:action+constraint | 2 | — |
| exception | 1 | `to the extent that they are not to be taxed pursuant to subsection (6) at the ta` (estg_000507) |

### `if`  ->  condition, constraint, exception

| field | count | example span |
|---|---:|---|
| condition | 64 | `if there are substantial business reasons and the tax office has given prior con` (estg_000004) |
| SENTENCE_ONLY | 46 | — |
| exception | 2 | `if the input tax is adjusted under Section 12(10) and (11) of the Turnover Tax A` (estg_000083) |
| constraint | 1 | `even if that value is higher than the last book value` (estg_000070) |
| MULTI:condition+constraint | 1 | — |
| MULTI:condition+exception | 1 | — |

### `to_the_extent`  ->  condition, constraint, exception

| field | count | example span |
|---|---:|---|
| condition | 13 | `to the extent that they are required under the articles of association for benef` (estg_000039) |
| SENTENCE_ONLY | 11 | — |
| constraint | 2 | `to the extent that no partial write-down under subparagraph a was claimed for th` (estg_000071) |
| MULTI:condition+constraint | 1 | — |
| exception | 1 | `to the extent that they are not to be taxed pursuant to subsection (6) at the ta` (estg_000507) |

### `which_rel`  ->  action, condition, constraint

| field | count | example span |
|---|---:|---|
| SENTENCE_ONLY | 17 | — |
| condition | 16 | `All institutions to which such a notice has been issued` (estg_000051) |
| constraint | 4 | `of the acquisition or production costs of the asset on the acquisition or produc` (estg_000082) |
| MULTI:action+constraint | 2 | — |
| action | 1 | `the profit shall be taken into account in determining the income for that calend` (estg_000002) |
| MULTI:constraint+exception | 1 | — |
| MULTI:condition+constraint | 1 | — |

### `who_rel`  ->  actor, condition, constraint

| field | count | example span |
|---|---:|---|
| SENTENCE_ONLY | 8 | — |
| condition | 6 | `For buildings that form part of the fixed assets and are let for consideration f` (estg_000056) |
| constraint | 2 | `emoluments and benefits of persons who are not substantially interested in corpo` (estg_000273) |
| actor | 1 | `Taxpayers who are required to keep books under commercial law provisions` (estg_000816) |

### `at_least`  ->  condition, constraint

| field | count | example span |
|---|---:|---|
| SENTENCE_ONLY | 4 | — |
| condition | 2 | `the disposed-of asset at the time of disposal has belonged to the fixed assets o` (estg_000128) |
| constraint | 2 | `with a nominal amount of at least 50% of the provision amount shown in the balan` (estg_000143) |
| MULTI:condition+constraint | 1 | — |

### `in_accordance_with`  ->  condition, constraint

| field | count | example span |
|---|---:|---|
| constraint | 10 | `in accordance with the Annex to this Federal Act` (estg_000043) |
| SENTENCE_ONLY | 8 | — |
| condition | 5 | `who determine profit in accordance with Section 4(3)` (estg_000091) |

### `in_the_event_of`  ->  condition, constraint

| field | count | example span |
|---|---:|---|
| condition | 2 | `whether the housing applicant has a claim to full reimbursement of the amount in` (estg_000195) |
| constraint | 1 | `allowances and supplementary payments included in wages continued to be paid to ` (estg_000522) |
| SENTENCE_ONLY | 1 | — |

### `when`  ->  condition, constraint

| field | count | example span |
|---|---:|---|
| SENTENCE_ONLY | 4 | — |
| condition | 2 | `when determining the tax for the employee's other income` (estg_000030) |
| constraint | 2 | `that other changes in the profit determination principles (e.g., regarding the c` (estg_000061) |
| MULTI:condition+constraint | 1 | — |

### `where`  ->  condition, exception

| field | count | example span |
|---|---:|---|
| SENTENCE_ONLY | 5 | — |
| condition | 2 | `Where the acquisition or construction of fixed assets extends beyond a balance s` (estg_000114) |
| exception | 1 | `also in cases where they are not granted alongside current wages from the same e` (estg_000507) |

### `within_N`  ->  condition, constraint

| field | count | example span |
|---|---:|---|
| SENTENCE_ONLY | 23 | — |
| constraint | 17 | `within the meaning of paragraph 1 items 10 and 11` (estg_000030) |
| condition | 14 | `insofar as they, together with contributions within the meaning of item 6, do no` (estg_000052) |
| MULTI:condition+constraint | 3 | — |

## L2 — Stage 3 items all methods miss

total: **16 / 33**

| item | gold type | winter | sun | bm25 | tfidf | pattern |
|---|---|---|---|---|---|---|
| v006 | out_of_order | None | None | None | None | abstain(none) |
| v009 | out_of_order | None | None | None | None | abstain(none) |
| v012 | out_of_order | None | None | None | None | abstain(none) |
| v015 | out_of_order | None | None | None | None | abstain(none) |
| v017 | incorrect_actor | None | None | None | None | abstain(none) |
| v018 | out_of_order | None | None | None | None | abstain(none) |
| v020 | incorrect_actor | None | None | None | None | abstain(none) |
| v021 | out_of_order | None | None | None | None | abstain(none) |
| v023 | incorrect_actor | None | None | None | None | abstain(none) |
| v024 | out_of_order | None | None | None | None | abstain(none) |
| v026 | incorrect_actor | None | None | None | None | abstain(none) |
| v027 | out_of_order | None | None | None | None | abstain(none) |
| v029 | incorrect_actor | None | None | None | None | abstain(none) |
| v030 | out_of_order | None | None | None | None | abstain(none) |
| v032 | incorrect_actor | None | None | None | None | abstain(none) |
| v033 | out_of_order | None | None | None | None | abstain(none) |

## L3 — near-identical clauses with different Gold modality

total: **2**  (similarity >= 0.90)

### similarity 0.9194
- A `estg_000082` / `c1` -> **definition**: To the extent that the input tax can be deducted (Section 12(1) of the Value Added Tax Act 1972), it does not form part of the acquisition or production costs of the asset on the acquisition or production of which it is incurred
- B `estg_000082` / `c2` -> **obligation**: To the extent that the input tax can be deducted (Section 12(1) of the Value Added Tax Act 1972), it does not form part of the acquisition or production costs of the asset on the acquisition or production of which it is incurred, and shall be reported as a receivable.

### similarity 0.9081
- A `estg_000039` / `c1` -> **obligation**: The agreement must provide that the taxpayer’s ongoing contribution payments may only be suspended or restricted for compelling economic reasons and only after consultation with the works council.
- B `estg_000039` / `c2` -> **permission**: the taxpayer’s ongoing contribution payments may only be suspended or restricted for compelling economic reasons and only after consultation with the works council

## Next step (human only)

1. For each L1 cue: decide whether the two assignments are both legally
   correct (context-dependent) or one is an annotation slip.
2. For each L2 item: re-read the regulation article and the process model;
   decide whether Gold, the input binding, or the detector is at fault.
3. For each L3 pair: decide which label is right and whether a rule is missing.
4. Only after human adjudication may a NEW Gold version be created; the old
   version and all affected results are kept and reported side by side.
