# SEP-C2 Sun-predecessor run: cf_rnn

- status: **completed_zero_api_predecessor_method_run**
- Sun role: Table 7 bidirectional-LSTM classification baseline (CF_RNN)
- reproduction class: paper-described architecture retrained locally on the official EStG modality train split
- input field/language: `raw_text_de` / `de`
- records scored: 150 / 150
- missing / failed / unlabeled: 0 / 0 / 0
- accuracy: 0.5667
- macro-F1: 0.4800

| class | precision | recall | F1 | gold support | predicted count |
|---|---:|---:|---:|---:|---:|
| obligation | 0.8070 | 0.7797 | 0.7931 | 59 | 57 |
| permission | 0.6000 | 0.2857 | 0.3871 | 42 | 20 |
| prohibition | 0.7500 | 0.1500 | 0.2500 | 20 | 4 |
| definition | 0.3478 | 0.8276 | 0.4898 | 29 | 69 |

- training rows: 1927 train / 414 dev
- best dev macro-F1: 0.7885 (epoch 10)
- official clean test diagnostic: accuracy 0.8092, macro-F1 0.6762, n=414
- OOV rate (train/dev/official test/EStG-150): 0.0000 / 0.0423 / 0.0406 / 0.2214

- version caveat: Built against the locally available earlier author manuscript; the final Springer version could not be checked in this offline environment. Hyperparameters not given by Sun are frozen in the method config and reported here.
- new LLM/API calls: 0
