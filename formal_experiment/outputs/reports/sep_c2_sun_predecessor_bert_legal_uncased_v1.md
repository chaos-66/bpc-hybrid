# SEP-C2 Sun-predecessor run: bert_legal_uncased

- status: **completed_zero_api_predecessor_method_run**
- Sun role: Sun et al. final version Table 6/7 bert-legal-uncased (nlpaueb/legal-bert-base-uncased) comparison; final-paper BERT-TextCNN architecture
- reproduction class: public pre-trained encoder plus final-paper BERT-TextCNN head, fine-tuned locally on the clean official EStG train split
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

- architecture evidence: Sun et al. (2024), final article, Section 4.2.1 / Fig. 3: 'For each encoding layer, the vector of its first token (i.e., [CLS]) is extracted, and these vectors are concatenated together as the input of the TextCNN layer.' The figure labels CLS1..CLS12 and a TextCNN with kernel widths 3/4/5 and 256 filters per width.
- new LLM/API calls: 0
