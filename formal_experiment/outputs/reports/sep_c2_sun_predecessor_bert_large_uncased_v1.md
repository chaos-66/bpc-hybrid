# SEP-C2 Sun-predecessor run: bert_large_uncased

- status: **completed_zero_api_predecessor_method_run**
- Sun role: Sun et al. local author manuscript Table 6, bert-large-uncased comparison (directly verified); project-record final-version BERT-TextCNN architecture (not re-fetched/re-verified 2026-09-17)
- reproduction class: public pre-trained encoder plus project-record final-version BERT-TextCNN head, fine-tuned locally on the clean official EStG train split
- input field/language: `raw_text_de` / `de`
- records scored: 150 / 150
- missing / failed / unlabeled: 0 / 0 / 0
- accuracy: 0.5733
- macro-F1: 0.5245

| class | precision | recall | F1 | gold support | predicted count |
|---|---:|---:|---:|---:|---:|
| obligation | 0.7593 | 0.6949 | 0.7257 | 59 | 54 |
| permission | 0.8333 | 0.4762 | 0.6061 | 42 | 24 |
| prohibition | 1.0000 | 0.2000 | 0.3333 | 20 | 4 |
| definition | 0.3088 | 0.7241 | 0.4330 | 29 | 68 |

- encoder: bert hidden=1024 layers=24
- training rows: 1927 train / 414 dev
- best dev macro-F1: 0.8517 (epoch 4)
- device: cuda
- official clean test diagnostic: accuracy 0.9227, macro-F1 0.8379, n=414

- architecture evidence: Project record (2026-09-15) quotes Sun et al. (2024) final article Section 4.2.1 / Fig. 3: 'For each encoding layer, the vector of its first token (i.e., [CLS]) is extracted, and these vectors are concatenated together as the input of the TextCNN layer.' The figure labels CLS1..CLS12 and a TextCNN with kernel widths 3/4/5 and 256 filters per width.
- new LLM/API calls: 0
