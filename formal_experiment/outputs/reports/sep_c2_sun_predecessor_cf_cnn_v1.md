# SEP-C2 Sun-predecessor run: cf_cnn

- status: **completed_zero_api_predecessor_method_run**
- Sun role: Table 7 CNN classification baseline (CF_CNN)
- reproduction class: paper-described architecture retrained locally on the official EStG modality train split
- input field/language: `raw_text_de` / `de`
- records scored: 150 / 150
- missing / failed / unlabeled: 0 / 0 / 0
- accuracy: 0.6733
- macro-F1: 0.6177

| class | precision | recall | F1 | gold support | predicted count |
|---|---:|---:|---:|---:|---:|
| obligation | 0.8793 | 0.8644 | 0.8718 | 59 | 58 |
| permission | 0.7778 | 0.5000 | 0.6087 | 42 | 27 |
| prohibition | 0.7000 | 0.3500 | 0.4667 | 20 | 10 |
| definition | 0.4000 | 0.7586 | 0.5238 | 29 | 55 |

- training rows: 1927 train / 414 dev
- best dev macro-F1: 0.8532 (epoch 5)
- official clean test diagnostic: accuracy 0.8647, macro-F1 0.7352, n=414
- OOV rate (train/dev/official test/EStG-150): 0.0000 / 0.0423 / 0.0406 / 0.2214

- version caveat: Built against the locally available earlier author manuscript; the final Springer version could not be checked in this offline environment. Hyperparameters not given by Sun are frozen in the method config and reported here.
- new LLM/API calls: 0
