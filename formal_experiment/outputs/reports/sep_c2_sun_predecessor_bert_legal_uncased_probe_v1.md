# SEP-C2 Sun-predecessor run: bert_legal_uncased_probe

- status: **completed_zero_api_predecessor_method_run**
- Sun role: Table 6 bert-legal-uncased comparison; closest locally available public legal-BERT encoder
- reproduction class: matched public encoder frozen; classification head trained locally on the clean official train split
- input field/language: `raw_text_de` / `de`
- records scored: 150 / 150
- missing / failed / unlabeled: 0 / 0 / 0
- accuracy: 0.4800
- macro-F1: 0.3897

| class | precision | recall | F1 | gold support | predicted count |
|---|---:|---:|---:|---:|---:|
| obligation | 0.5114 | 0.7627 | 0.6122 | 59 | 88 |
| permission | 0.6316 | 0.2857 | 0.3934 | 42 | 19 |
| prohibition | 1.0000 | 0.1000 | 0.1818 | 20 | 2 |
| definition | 0.3171 | 0.4483 | 0.3714 | 29 | 41 |

- encoder: nlpaueb/legal-bert-base-uncased @ 15b570cbf88259610b082a167dacc190124f60f6 (frozen)
- training rows: 1927 train / 414 dev
- best dev macro-F1: 0.5534 (epoch 44)
- official clean test diagnostic: accuracy 0.7077, macro-F1 0.5217, n=414

- version caveat: Built against the locally available earlier author manuscript; the final Springer version could not be checked in this offline environment. The encoder is a public EU-legislation legal-BERT base uncased model, not Sun's unpublished checkpoint.
- new LLM/API calls: 0
