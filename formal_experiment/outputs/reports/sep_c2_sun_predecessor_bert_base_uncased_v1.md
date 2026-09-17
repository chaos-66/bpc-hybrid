# SEP-C2 Sun-predecessor run: bert_base_uncased

- status: **completed_zero_api_predecessor_method_run**
- Sun role: Sun et al. final version Table 6/7 bert-base-uncased comparison; final-paper BERT-TextCNN architecture
- reproduction class: public pre-trained encoder plus final-paper BERT-TextCNN head, fine-tuned locally on the clean official EStG train split
- input field/language: `raw_text_de` / `de`
- records scored: 150 / 150
- missing / failed / unlabeled: 0 / 0 / 0
- accuracy: 0.4467
- macro-F1: 0.3507

| class | precision | recall | F1 | gold support | predicted count |
|---|---:|---:|---:|---:|---:|
| obligation | 0.7200 | 0.6102 | 0.6606 | 59 | 50 |
| permission | 0.6667 | 0.2857 | 0.4000 | 42 | 18 |
| prohibition | 0.0000 | 0.0000 | 0.0000 | 20 | 0 |
| definition | 0.2317 | 0.6552 | 0.3423 | 29 | 82 |

- encoder: bert hidden=768 layers=12
- training rows: 1927 train / 414 dev
- best dev macro-F1: 0.7524 (epoch 5)
- device: cuda
- official clean test diagnostic: accuracy 0.8647, macro-F1 0.7007, n=414

- architecture evidence: Sun et al. (2024), final article, Section 4.2.1 / Fig. 3: 'For each encoding layer, the vector of its first token (i.e., [CLS]) is extracted, and these vectors are concatenated together as the input of the TextCNN layer.' The figure labels CLS1..CLS12 and a TextCNN with kernel widths 3/4/5 and 256 filters per width.
- new LLM/API calls: 0
