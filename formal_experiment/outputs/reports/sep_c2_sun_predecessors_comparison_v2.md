# SEP-C2 corrected comparison v2 (EStG-150, same evaluator)

- status: **completed_with_one_exact_checkpoint_blocker**
- supersedes: `sep_c2_sun_predecessors_comparison_v1`
- classification table declares 11 rows: 10 evaluated (3 predecessor + 5 BERT-family + 2 project) and 1 explicitly blocked exact checkpoint (`bert-legal-cased`)
- semantic main table: project G0.4 coarse sentence-level view, five span fields only; modality evidence unavailable

## Classification: per-method summary

| method | Sun label | n | missing/failed/unlabeled | accuracy | macro P/R/F1 | input field / language | status |
|---|---|---:|---|---:|---|---|---|
| cf_kw | CF_KW | 150 | 0/0/0 | 0.6200 | 0.5583/0.5387/0.5322 | `raw_text_de` / de | completed_zero_api |
| cf_rnn | CF_RNN (BiLSTM) | 150 | 0/0/0 | 0.5667 | 0.6262/0.5107/0.4800 | `raw_text_de` / de | completed_zero_api |
| cf_cnn | CF_CNN | 150 | 0/0/0 | 0.6733 | 0.6893/0.6183/0.6177 | `raw_text_de` / de | completed_zero_api |
| bert_base_uncased | bert-base-uncased | 150 | 0/0/0 | 0.4467 | 0.4046/0.3878/0.3507 | `raw_text_de` / de | completed_zero_api |
| bert_base_cased | bert-base-cased | 150 | 0/0/0 | 0.5733 | 0.4440/0.4923/0.4529 | `raw_text_de` / de | completed_zero_api |
| bert_large_uncased | bert-large-uncased | 150 | 0/0/0 | 0.5733 | 0.7254/0.5238/0.5245 | `raw_text_de` / de | completed_zero_api |
| bert_large_cased | bert-large-cased | 150 | 0/0/0 | 0.6600 | 0.6260/0.5952/0.6024 | `raw_text_de` / de | completed_zero_api |
| bert_legal_uncased | bert-legal-uncased | 150 | 0/0/0 | 0.4800 | 0.5219/0.4426/0.4057 | `raw_text_de` / de | completed_zero_api |
| sun_rule_only | Sun/Rules-Only | 150 | 0/0/0 | 0.7400 | 0.7612/0.6879/0.7128 | `raw_text_de (classifier) + approved_text_en (phrases)` / de classifier / en phrase view | existing_formal_arm_reused_zero_api |
| direct_llm | Direct-LLM | 150 | 0/0/1 | 0.8333 | 0.8155/0.7826/0.7695 | `approved_text_en` / en | existing_formal_arm_reused_zero_api |
| bert_legal_cased | bert-legal-cased | 150 | 150/150/0 | N/A | N/A/N/A/N/A | `raw_text_de` / de | blocked_exact_public_checkpoint_unavailable |

### Classification: per-class P/R/F1 and support

| method | class | precision | recall | F1 | gold support | predicted count |
|---|---|---:|---:|---:|---:|---:|
| cf_kw | obligation | 0.7097 | 0.7458 | 0.7273 | 59 | 62 |
| cf_kw | permission | 0.6364 | 0.8333 | 0.7216 | 42 | 55 |
| cf_kw | prohibition | 0.3158 | 0.3000 | 0.3077 | 20 | 19 |
| cf_kw | definition | 0.5714 | 0.2759 | 0.3721 | 29 | 14 |
| cf_rnn | obligation | 0.8070 | 0.7797 | 0.7931 | 59 | 57 |
| cf_rnn | permission | 0.6000 | 0.2857 | 0.3871 | 42 | 20 |
| cf_rnn | prohibition | 0.7500 | 0.1500 | 0.2500 | 20 | 4 |
| cf_rnn | definition | 0.3478 | 0.8276 | 0.4898 | 29 | 69 |
| cf_cnn | obligation | 0.8793 | 0.8644 | 0.8718 | 59 | 58 |
| cf_cnn | permission | 0.7778 | 0.5000 | 0.6087 | 42 | 27 |
| cf_cnn | prohibition | 0.7000 | 0.3500 | 0.4667 | 20 | 10 |
| cf_cnn | definition | 0.4000 | 0.7586 | 0.5238 | 29 | 55 |
| bert_base_uncased | obligation | 0.7200 | 0.6102 | 0.6606 | 59 | 50 |
| bert_base_uncased | permission | 0.6667 | 0.2857 | 0.4000 | 42 | 18 |
| bert_base_uncased | prohibition | 0.0000 | 0.0000 | 0.0000 | 20 | 0 |
| bert_base_uncased | definition | 0.2317 | 0.6552 | 0.3423 | 29 | 82 |
| bert_base_cased | obligation | 0.8039 | 0.6949 | 0.7455 | 59 | 51 |
| bert_base_cased | permission | 0.6500 | 0.6190 | 0.6341 | 42 | 40 |
| bert_base_cased | prohibition | 0.0000 | 0.0000 | 0.0000 | 20 | 0 |
| bert_base_cased | definition | 0.3220 | 0.6552 | 0.4318 | 29 | 59 |
| bert_large_uncased | obligation | 0.7593 | 0.6949 | 0.7257 | 59 | 54 |
| bert_large_uncased | permission | 0.8333 | 0.4762 | 0.6061 | 42 | 24 |
| bert_large_uncased | prohibition | 1.0000 | 0.2000 | 0.3333 | 20 | 4 |
| bert_large_uncased | definition | 0.3088 | 0.7241 | 0.4330 | 29 | 68 |
| bert_large_cased | obligation | 0.7647 | 0.8814 | 0.8189 | 59 | 68 |
| bert_large_cased | permission | 0.6389 | 0.5476 | 0.5897 | 42 | 36 |
| bert_large_cased | prohibition | 0.6154 | 0.4000 | 0.4848 | 20 | 13 |
| bert_large_cased | definition | 0.4848 | 0.5517 | 0.5161 | 29 | 33 |
| bert_legal_uncased | obligation | 0.8250 | 0.5593 | 0.6667 | 59 | 40 |
| bert_legal_uncased | permission | 0.7368 | 0.3333 | 0.4590 | 42 | 19 |
| bert_legal_uncased | prohibition | 0.2500 | 0.0500 | 0.0833 | 20 | 4 |
| bert_legal_uncased | definition | 0.2759 | 0.8276 | 0.4138 | 29 | 87 |
| sun_rule_only | obligation | 0.7105 | 0.9153 | 0.8000 | 59 | 76 |
| sun_rule_only | permission | 0.8857 | 0.7381 | 0.8052 | 42 | 35 |
| sun_rule_only | prohibition | 0.9286 | 0.6500 | 0.7647 | 20 | 14 |
| sun_rule_only | definition | 0.5200 | 0.4483 | 0.4815 | 29 | 25 |
| direct_llm | obligation | 0.8657 | 0.9831 | 0.9206 | 59 | 67 |
| direct_llm | permission | 0.9091 | 0.9524 | 0.9302 | 42 | 44 |
| direct_llm | prohibition | 0.6538 | 0.8500 | 0.7391 | 20 | 26 |
| direct_llm | definition | 0.8333 | 0.3448 | 0.4878 | 29 | 12 |

### Classification: implementation / binding summary

| method | reproduction | training/weights | result file |
|---|---|---|---|
| cf_kw | deterministic German keyword rules reconstructed; paper publishes no keyword list | none (rule list frozen in configs/sep_c2_sun_predecessors_v1/cf_kw_v1.json) | `outputs/reports/sep_c2_sun_predecessor_cf_kw_v1.json` |
| cf_rnn | paper-described BiLSTM retrained on clean official EStG train split; unpublished hyperparameters disclosed | official 300-d EStG vectors + locally trained BiLSTM (1927 train / 414 dev clean rows) | `outputs/reports/sep_c2_sun_predecessor_cf_rnn_v1.json` |
| cf_cnn | paper-described CNN retrained on clean official EStG train split; unpublished hyperparameters disclosed | official 300-d EStG vectors + locally trained TextCNN (1927 train / 414 dev clean rows) | `outputs/reports/sep_c2_sun_predecessor_cf_cnn_v1.json` |
| bert_base_uncased | public google-bert/bert-base-uncased + final-paper per-layer [CLS] TextCNN head, fine-tuned jointly on clean official EStG train split | public pinned BERT base uncased encoder + locally trained final-paper BERT-TextCNN head (1927/414) | `outputs/reports/sep_c2_sun_predecessor_bert_base_uncased_v1.json` |
| bert_base_cased | public google-bert/bert-base-cased + final-paper per-layer [CLS] TextCNN head, fine-tuned jointly on clean official EStG train split | public pinned BERT base cased encoder + locally trained final-paper BERT-TextCNN head (1927/414) | `outputs/reports/sep_c2_sun_predecessor_bert_base_cased_v1.json` |
| bert_large_uncased | public google-bert/bert-large-uncased + final-paper per-layer [CLS] TextCNN head, fine-tuned jointly on clean official EStG train split | public pinned BERT large uncased encoder + locally trained final-paper BERT-TextCNN head (1927/414) | `outputs/reports/sep_c2_sun_predecessor_bert_large_uncased_v1.json` |
| bert_large_cased | public google-bert/bert-large-cased + final-paper per-layer [CLS] TextCNN head, fine-tuned jointly on clean official EStG train split | public pinned BERT large cased encoder + locally trained final-paper BERT-TextCNN head (1927/414) | `outputs/reports/sep_c2_sun_predecessor_bert_large_cased_v1.json` |
| bert_legal_uncased | public nlpaueb/legal-bert-base-uncased + final-paper per-layer [CLS] TextCNN head, fine-tuned jointly on clean official EStG train split | public pinned Legal-BERT base uncased encoder + locally trained final-paper BERT-TextCNN head (1927/414) | `outputs/reports/sep_c2_sun_predecessor_bert_legal_uncased_v1.json` |
| sun_rule_only | existing B0 formal arm reused read-only; no new training or LLM call | existing B0 checkpoint/config | `data/results/b0_formal_arm_v1/modality_labels.json` |
| direct_llm | existing Direct-LLM formal prediction snapshot reused read-only; no new LLM call | existing Direct-LLM prediction snapshot | `data/results/direct_llm_formal_arm_v1/modality_labels.json` |

## Supplementary BERT adaptations (not part of the 9 baseline completion table)

| method | diagnostic scope | accuracy | macro P/R/F1 | limitation |
|---|---|---:|---|---|
| bert_legal_uncased_probe | diagnostic supplement: encoder frozen, MLP head only | 0.4800 | 0.6150/0.3992/0.3897 | Not a replacement for full BERT-TextCNN fine-tuning; reported only to preserve the earlier probe evidence. |
| bert_legal_uncased_textcnn_existing | diagnostic reused checkpoint with known training/EStG-150 overlap | 0.6667 | 0.7232/0.6374/0.6535 | Not eligible as the clean main comparison because its training split overlaps EStG-150. |

## Semantic extraction main table (coarse sentence-level, five span fields)

Modality evidence is unavailable in the published decision-only Gold and is therefore not included. The values below are the project's authorized coarse main view, not a fine-grained five-field re-aggregation.

| method | ground truth | extracted | precision | recall | F1 | result file |
|---|---:|---:|---:|---:|---:|---|
| cf_kw | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_cf_kw_v1.json` |
| cf_rnn | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_cf_rnn_v1.json` |
| cf_cnn | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_cf_cnn_v1.json` |
| bert_base_uncased | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_bert_base_uncased_v1.json` |
| bert_base_cased | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_bert_base_cased_v1.json` |
| bert_large_uncased | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_bert_large_uncased_v1.json` |
| bert_large_cased | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_bert_large_cased_v1.json` |
| bert_legal_uncased | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_bert_legal_uncased_v1.json` |
| sun_rule_only | 459 | 892 | 0.6984 | 0.8410 | 0.7631 | `data/results/b0_formal_arm_v1/evaluation_coarse.json` |
| direct_llm | 459 | 590 | 0.8695 | 0.8083 | 0.8378 | `data/results/direct_llm_formal_arm_v1/evaluation_coarse.json` |

### Semantic extraction main table: per field

| method | field | ground truth | extracted | precision | recall | F1 |
|---|---|---:|---:|---:|---:|---:|
| sun_rule_only | actor | 41 | 65 | 0.7077 | 0.9756 | 0.8203 |
| sun_rule_only | action | 150 | 244 | 0.8730 | 0.9133 | 0.8927 |
| sun_rule_only | condition | 122 | 239 | 0.7029 | 0.8607 | 0.7738 |
| sun_rule_only | constraint | 135 | 330 | 0.5606 | 0.6889 | 0.6182 |
| sun_rule_only | exception | 11 | 14 | 0.7857 | 1.0000 | 0.8800 |
| direct_llm | actor | 41 | 60 | 0.6667 | 0.8780 | 0.7579 |
| direct_llm | action | 150 | 210 | 0.9762 | 0.9133 | 0.9437 |
| direct_llm | condition | 122 | 135 | 0.9185 | 0.7705 | 0.8380 |
| direct_llm | constraint | 135 | 175 | 0.7771 | 0.7111 | 0.7427 |
| direct_llm | exception | 11 | 10 | 0.8000 | 0.7273 | 0.7619 |

## Semantic extraction diagnostic table (fine clause-level, five span fields)

| method | ground truth | extracted | precision | recall | F1 | result file |
|---|---:|---:|---:|---:|---:|---|
| cf_kw | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_cf_kw_v1.json` |
| cf_rnn | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_cf_rnn_v1.json` |
| cf_cnn | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_cf_cnn_v1.json` |
| bert_base_uncased | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_bert_base_uncased_v1.json` |
| bert_base_cased | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_bert_base_cased_v1.json` |
| bert_large_uncased | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_bert_large_uncased_v1.json` |
| bert_large_cased | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_bert_large_cased_v1.json` |
| bert_legal_uncased | N/A | N/A | N/A | N/A | N/A | `outputs/reports/sep_c2_sun_predecessor_bert_legal_uncased_v1.json` |
| sun_rule_only | 824 | 892 | 0.6435 | 0.7160 | 0.6778 | `data/results/b0_formal_arm_v1/evaluation_fine.json` |
| direct_llm | 824 | 590 | 0.8424 | 0.6432 | 0.7294 | `data/results/direct_llm_formal_arm_v1/evaluation_fine.json` |

## Blocked rows

- **bert_legal_cased**: The exact cased EU-legislation legal-BERT checkpoint ('bert-legal-cased') is not published in the public nlpaueb Legal-BERT collection (only legal-bert-base-uncased and legal-bert-small-uncased exist), and no author checkpoint/code is present in the public paper repository or Archive.org supplement. A cased generic BERT or an uncased Legal-BERT is not allowed to occupy this exact configuration's completion position.
  - attempted/checked: https://huggingface.co/nlpaueb/legal-bert-base-cased (404; no such model)
  - attempted/checked: Hugging Face model search: legal-bert / eurlex / legal cased family (no exact cased EU-legislation model)
  - attempted/checked: GitHub repository title-matching the final paper: only README/LICENSE, no model or training code
  - attempted/checked: Archive.org Decision_Logic_data.zip: data members only (EStG_raw.txt, EStG_sent_vec.csv, estg.html), no checkpoint

## Input / target audit

- target: Project G0.4 coarse sentence-level view: one synthetic clause over approved_text_en; modality label = first non-empty Gold clause modality string. This is a statement-level target extracted from the first Gold clause, not a request to classify only the first clause span.
- Gold first-clause label support: `{'definition': 29, 'obligation': 59, 'permission': 42, 'prohibition': 20}`
- Gold clause-count distribution: `{'1': 101, '2': 27, '3': 14, '4': 7, '6': 1}`
- first clause starts at 0: 141/150; covers full sentence: 26/150
- language condition: Sun's official modality corpus is German and its archived sentence vectors are German. CF_KW/CF_RNN/CF_CNN and the six BERT-family rows therefore consume raw_text_de, which preserves the predecessor method's native language and available public training material. Direct-LLM uses approved_text_en because its prompt/snapshot was executed in English. The German/English difference is a method/design condition, not silently normalized away; no new paid LLM calls are made to translate it.
- granularity condition: The predecessor classifiers receive the full formal-input statement in their native language, matching the sentence-level official training data. The target is the project's first-Gold-clause modality label. Where a formal input contains multiple clauses, this remains a target-construction difference and is reported rather than hidden.
- class-prior shift: `{'eStG150_gold_first_clause': {'definition': 29, 'obligation': 59, 'permission': 42, 'prohibition': 20}, 'official_clean_train': {'definition': 811, 'obligation': 864, 'permission': 180, 'prohibition': 72}, 'official_clean_dev': {'definition': 175, 'obligation': 185, 'permission': 38, 'prohibition': 16}, 'official_clean_test': {'definition': 175, 'obligation': 186, 'permission': 38, 'prohibition': 15}}`

## Error examples for the modality task

| method | sample_id | gold | predicted |
|---|---|---|---|
| cf_kw | estg_000020 | definition | permission |
| cf_kw | estg_000021 | prohibition | permission |
| cf_kw | estg_000027 | obligation | definition |
| cf_kw | estg_000028 | obligation | prohibition |
| cf_kw | estg_000031 | definition | obligation |
| cf_rnn | estg_000002 | obligation | permission |
| cf_rnn | estg_000003 | permission | definition |
| cf_rnn | estg_000004 | permission | obligation |
| cf_rnn | estg_000021 | prohibition | definition |
| cf_rnn | estg_000027 | obligation | definition |
| cf_cnn | estg_000002 | obligation | permission |
| cf_cnn | estg_000003 | permission | definition |
| cf_cnn | estg_000004 | permission | definition |
| cf_cnn | estg_000021 | prohibition | definition |
| cf_cnn | estg_000028 | obligation | definition |
| bert_base_uncased | estg_000002 | obligation | definition |
| bert_base_uncased | estg_000003 | permission | definition |
| bert_base_uncased | estg_000004 | permission | obligation |
| bert_base_uncased | estg_000021 | prohibition | definition |
| bert_base_uncased | estg_000027 | obligation | definition |
| bert_base_cased | estg_000003 | permission | definition |
| bert_base_cased | estg_000004 | permission | obligation |
| bert_base_cased | estg_000021 | prohibition | definition |
| bert_base_cased | estg_000027 | obligation | definition |
| bert_base_cased | estg_000031 | definition | obligation |
| bert_large_uncased | estg_000002 | obligation | definition |
| bert_large_uncased | estg_000003 | permission | definition |
| bert_large_uncased | estg_000004 | permission | definition |
| bert_large_uncased | estg_000021 | prohibition | definition |
| bert_large_uncased | estg_000027 | obligation | definition |
| bert_large_cased | estg_000003 | permission | definition |
| bert_large_cased | estg_000004 | permission | definition |
| bert_large_cased | estg_000031 | definition | obligation |
| bert_large_cased | estg_000035 | permission | prohibition |
| bert_large_cased | estg_000036 | permission | definition |
| bert_legal_uncased | estg_000003 | permission | definition |
| bert_legal_uncased | estg_000004 | permission | definition |
| bert_legal_uncased | estg_000021 | prohibition | definition |
| bert_legal_uncased | estg_000033 | prohibition | definition |
| bert_legal_uncased | estg_000036 | permission | definition |
| sun_rule_only | estg_000002 | obligation | permission |
| sun_rule_only | estg_000004 | permission | definition |
| sun_rule_only | estg_000020 | definition | prohibition |
| sun_rule_only | estg_000031 | definition | obligation |
| sun_rule_only | estg_000037 | definition | obligation |
| direct_llm | estg_000002 | obligation | permission |
| direct_llm | estg_000020 | definition | prohibition |
| direct_llm | estg_000021 | prohibition | permission |
| direct_llm | estg_000037 | definition | obligation |
| direct_llm | estg_000046 | permission | prohibition |

## Safety and reproducibility

- zero new paid LLM/API calls; Direct-LLM and B0 predictions are reused read-only
- public model downloads only; BERT encoders are pinned in their method configs
- each method has predictions, evaluation, training/weights, config, and checkpoint bindings in its capsule
- `bert-legal-cased` remains blocked because the exact cased EU-legislation checkpoint is not public; no substitute is reported in its place
