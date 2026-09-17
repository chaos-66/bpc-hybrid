# SEP-C2 Sun-predecessor run: cf_kw

- status: **completed_zero_api_predecessor_method_run**
- Sun role: Table 7 keyword classification baseline (CF_KW)
- reproduction class: paper-described rule baseline; keyword list reconstructed because the paper does not publish it
- input field/language: `raw_text_de` / `de`
- records scored: 150 / 150
- missing / failed / unlabeled: 0 / 0 / 0
- accuracy: 0.6200
- macro-F1: 0.5322

| class | precision | recall | F1 | gold support | predicted count |
|---|---:|---:|---:|---:|---:|
| obligation | 0.7097 | 0.7458 | 0.7273 | 59 | 62 |
| permission | 0.6364 | 0.8333 | 0.7216 | 42 | 55 |
| prohibition | 0.3158 | 0.3000 | 0.3077 | 20 | 19 |
| definition | 0.5714 | 0.2759 | 0.3721 | 29 | 14 |

- version caveat: Built against the locally available earlier author manuscript; the final Springer version could not be checked in this offline environment. No exact-original claim is made.
- new LLM/API calls: 0
