# SEP-C3 Definition Gold Consistency Audit

- API calls: **0**.
- This audit checks internal consistency of Gold definition annotations. It does not modify Gold.

## 1. Modality-label consistency

- Definition clauses: 39 across 34 samples.
- `shall` definition clauses: 15.
- Definition clauses all four arms non-definition: 25.

### Same-trigger modality distribution

| Trigger | Hits | Gold modalities | Case ids |
| --- | --- | --- | --- |
| applies/apply | 12 | definition=7; obligation=4; permission=1 | estg_000056:c1, estg_000071:c1, estg_000083:c1, estg_000128:c2, estg_000145:c1, estg_000164:c1, estg_000208:c2, estg_000209:c2, estg_000218:c1, estg_000306:c1, estg_000664:c1, estg_000800:c1 |
| shall apply | 3 | definition=1; obligation=2 | estg_000056:c1, estg_000128:c2, estg_000664:c1 |
| shall be determined | 2 | definition=1; obligation=1 | estg_000136:c1, estg_000812:c1 |
| shall be assumed | 3 | definition=2; obligation=1 | estg_000505:c2, estg_000509:c2, estg_000776:c1 |

### Suspected / unresolved consistency issues

| Issue | Gold labels / relation | Evidence |
| --- | --- | --- |
| estg_000505 c2 vs estg_000509 c2 | obligation vs definition | near-identical surface text: `a monthly wage payment period shall be assumed` |
| applies / shall apply family | definition and obligation/permission | 7 definition clauses vs 5 non-definition clauses with the same apply/application lexeme |
| estg_000020 c1 | definition | the only definition action span that contains separately annotated condition spans |
| estg_000083 c2 | definition | the only definition action span that explicitly contains its subject and coordinated second predicate |
| estg_000031 c1 vs estg_000273 c1 | definition vs definition | copular action includes `is the difference` in one case and only `is` in another; complement granularity may be context-dependent |

The `estg_000505 c2` vs `estg_000509 c2` pair is the strongest apparent modality-label inconsistency: the surface construction and action overlap are near-identical, but one is Gold `obligation` and the other Gold `definition`. It is reported as an unresolved Gold-semantics case, not corrected.

## 2. Action-span consistency

- Definition clauses with action: 39/39.
- Definition action spans: 46.
- Definition clauses with actor: 2.
- Definition clauses with condition: 28.
- Definition clauses with constraint: 28.
- Definition clauses with exception: 5.

Action spans are mostly short, predicate-centred spans. Heterogeneity appears in complement inclusion and in two outlier spans:

1. `estg_000020 c1`: action includes two Gold condition spans; this is the only measured action-condition overlap in the definition corpus.
2. `estg_000083 c2`: action includes subject plus coordinated predicates; most legal-fiction actions are predicate-only.
3. `estg_000031 c1` (`is the difference`) and `estg_000273 c1` (`is`) show that copular complement inclusion is context-dependent.
4. `estg_000283 c1` uses bare `leaves`/`works` while object/adjunct material appears in other fields.

These are boundary-heterogeneity observations. Only the `estg_000020` action-condition overlap is a direct conflict with S rule 8. No Gold definition clause has an empty action span.

## 3. Manual review flags

| Sample / clause | Reason |
| --- | --- |
| estg_000020 c1 | Gold action span contains two separately annotated condition spans. |
| estg_000082 c1 | Negative part-whole predicate is classified as classification with low confidence. |
| estg_000083 c2 | Only definition action that includes a coordinated subject plus predicate. |
| estg_000112 c1 | Clause is a fragment; clause boundary and action are both uncertain. |
| estg_000136 c1 | Passive determination may be deeming or ordinary relational predicate. |
| estg_000164 c2 | Copular/passive classification boundary is uncertain. |
| estg_000232 c2 | Temporal relational predicate ('runs from') needs boundary review. |
| estg_000505 c2 | Near-identical to Gold definition estg_000509 c2, but Gold labels obligation. |
| estg_000509 c2 | Near-identical to estg_000505 c2, which Gold labels obligation. |

## 4. Conclusion

- Modality labels are broadly coherent in that Gold reserves `definition` for definitional, classification, legal-fiction, and scope-application clauses, but the `apply` family and the near-identical `shall be assumed` pair require annotation adjudication.
- Action presence is internally consistent: 39/39 definition clauses have actions.
- Action boundary granularity is not fully consistent; it requires annotation-level principles before becoming a prompt rule.
