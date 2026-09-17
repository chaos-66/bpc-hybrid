# SEP-C2 Sun-predecessor run: bert_large_cased

- status: **completed_zero_api_predecessor_method_run**
- Sun role: Sun et al. local author manuscript Table 6, bert-large-cased comparison (directly verified); project-record final-version BERT-TextCNN architecture (not re-fetched/re-verified 2026-09-17)
- reproduction class: public pre-trained encoder plus project-record final-version BERT-TextCNN head, fine-tuned locally on the clean official EStG train split
- input field/language: `raw_text_de` / `de`
- records scored: 150 / 150
- missing / failed / unlabeled: 0 / 0 / 0
- accuracy: 0.6600
- macro-F1: 0.6024

| class | precision | recall | F1 | gold support | predicted count |
|---|---:|---:|---:|---:|---:|
| obligation | 0.7647 | 0.8814 | 0.8189 | 59 | 68 |
| permission | 0.6389 | 0.5476 | 0.5897 | 42 | 36 |
| prohibition | 0.6154 | 0.4000 | 0.4848 | 20 | 13 |
| definition | 0.4848 | 0.5517 | 0.5161 | 29 | 33 |

- encoder: bert hidden=1024 layers=24
- training rows: 1927 train / 414 dev
- best dev macro-F1: 0.8185 (epoch 4)
- device: cuda
- official clean test diagnostic: accuracy 0.8768, macro-F1 0.7862, n=414

- architecture evidence: Project record (2026-09-15) quotes Sun et al. (2024) final article Section 4.2.1 / Fig. 3: 'For each encoding layer, the vector of its first token (i.e., [CLS]) is extracted, and these vectors are concatenated together as the input of the TextCNN layer.' The figure labels CLS1..CLS12 and a TextCNN with kernel widths 3/4/5 and 256 filters per width.
- new LLM/API calls: 0
