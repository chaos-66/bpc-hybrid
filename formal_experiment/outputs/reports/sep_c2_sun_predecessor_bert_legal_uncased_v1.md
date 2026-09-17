# SEP-C2 Sun-predecessor run: bert_legal_uncased

- status: **completed_zero_api_predecessor_method_run**
- Sun role: Sun et al. local author manuscript Table 6, bert-legal-uncased (nlpaueb/legal-bert-base-uncased) comparison (directly verified); project-record final-version BERT-TextCNN architecture (not re-fetched/re-verified 2026-09-17)
- reproduction class: public pre-trained encoder plus project-record final-version BERT-TextCNN head, fine-tuned locally on the clean official EStG train split
- input field/language: `raw_text_de` / `de`
- records scored: 150 / 150
- missing / failed / unlabeled: 0 / 0 / 0
- accuracy: 0.4800
- macro-F1: 0.4057

| class | precision | recall | F1 | gold support | predicted count |
|---|---:|---:|---:|---:|---:|
| obligation | 0.8250 | 0.5593 | 0.6667 | 59 | 40 |
| permission | 0.7368 | 0.3333 | 0.4590 | 42 | 19 |
| prohibition | 0.2500 | 0.0500 | 0.0833 | 20 | 4 |
| definition | 0.2759 | 0.8276 | 0.4138 | 29 | 87 |

- encoder: bert hidden=768 layers=12
- training rows: 1927 train / 414 dev
- best dev macro-F1: 0.7987 (epoch 4)
- device: cuda
- official clean test diagnostic: accuracy 0.8696, macro-F1 0.7615, n=414

- architecture evidence: Project record (2026-09-15) quotes Sun et al. (2024) final article Section 4.2.1 / Fig. 3: 'For each encoding layer, the vector of its first token (i.e., [CLS]) is extracted, and these vectors are concatenated together as the input of the TextCNN layer.' The figure labels CLS1..CLS12 and a TextCNN with kernel widths 3/4/5 and 256 filters per width.
- new LLM/API calls: 0
