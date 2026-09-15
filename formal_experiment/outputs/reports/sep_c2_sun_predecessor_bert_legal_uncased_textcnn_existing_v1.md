# SEP-C2 Sun-predecessor run: bert_legal_uncased_textcnn_existing

- status: **completed_zero_api_predecessor_method_run**
- Sun role: Existing project S2.4/S2.6 BERT-TextCNN classifier (final-paper-style head), reused read-only
- reproduction class: existing locally trained checkpoint; reused without retraining
- input field/language: `raw_text_de` / `de`
- records scored: 150 / 150
- missing / failed / unlabeled: 0 / 0 / 0
- accuracy: 0.6667
- macro-F1: 0.6535

| class | precision | recall | F1 | gold support | predicted count |
|---|---:|---:|---:|---:|---:|
| obligation | 0.8103 | 0.7966 | 0.8034 | 59 | 58 |
| permission | 0.7931 | 0.5476 | 0.6479 | 42 | 29 |
| prohibition | 0.9167 | 0.5500 | 0.6875 | 20 | 12 |
| definition | 0.3725 | 0.6552 | 0.4750 | 29 | 51 |

- model: Legal-BERT base uncased + TextCNN head (existing project S2.4 reconstruction)
- checkpoint: `outputs/development/s24_candidate_B_invsqrt_weighted_seed20260717_v1/best_model.pt`
- EStG-150 overlap flagged in original train: 24 rows (4 exact normalized)
- official clean test diagnostic: accuracy 0.9300, macro-F1 0.8754, n=414

- version caveat: Built against the locally available earlier author manuscript; the final Springer version could not be checked. This row reuses an existing project checkpoint and is flagged for small EStG-150 training overlap; it is a diagnostic, not a clean trained-from-scratch run.
- new LLM/API calls: 0
