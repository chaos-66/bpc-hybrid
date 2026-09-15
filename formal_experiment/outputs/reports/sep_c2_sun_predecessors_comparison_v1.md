# SEP-C2 Sun predecessor comparison (EStG-150, same evaluator)

- zero new LLM/API calls; existing B0/D1 formal predictions reused read-only
- local source version: earlier author manuscript; final Springer version was not accessible offline

## Modality classification (first-clause label, frozen evaluator)

| method | Sun source/role | reproduction | training/weights | language | n | missing/failed/unlabeled | accuracy | macro P/R/F1 | result file | status |
|---|---|---|---|---|---:|---|---:|---|---|---|
| cf_kw | Sun et al. (2024) author-manuscript Table 7, CF_KW | deterministic German keyword rules reconstructed because the paper omits the keyword list | none (rule list frozen in configs/sep_c2_sun_predecessors_v1/cf_kw_v1.json) | de (raw_text_de) | 150 | 0/0/0 | 0.6200 | 0.5583/0.5387/0.5322 | outputs/reports/sep_c2_sun_predecessor_cf_kw_v1.json | completed_zero_api |
| cf_rnn | Sun et al. (2024) author-manuscript Table 7, CF_RNN (BiLSTM) | BiLSTM retrained locally on clean official EStG train split; unpublished hyperparameters disclosed | official 300-d EStG vectors + locally trained BiLSTM (train 1927 / dev 414 clean rows) | de (raw_text_de) | 150 | 0/0/0 | 0.5667 | 0.6262/0.5107/0.4800 | outputs/reports/sep_c2_sun_predecessor_cf_rnn_v1.json | completed_zero_api |
| cf_cnn | Sun et al. (2024) author-manuscript Table 7, CF_CNN | 3/4/5-gram CNN retrained locally on clean official EStG train split; unpublished hyperparameters disclosed | official 300-d EStG vectors + locally trained TextCNN (train 1927 / dev 414 clean rows) | de (raw_text_de) | 150 | 0/0/0 | 0.6733 | 0.6893/0.6183/0.6177 | outputs/reports/sep_c2_sun_predecessor_cf_cnn_v1.json | completed_zero_api |
| bert_legal_uncased_probe | Sun et al. (2024) author-manuscript Table 6, bert-legal-uncased | closest local public encoder (nlpaueb/legal-bert-base-uncased) frozen + locally trained MLP probe; full CPU fine-tuning not attempted | public legal-BERT base uncased encoder + locally trained 256-unit MLP head on clean official train (1927/414) | de (raw_text_de) | 150 | 0/0/0 | 0.4800 | 0.6150/0.3992/0.3897 | outputs/reports/sep_c2_sun_predecessor_bert_legal_uncased_probe_v1.json | completed_zero_api_weaker_adaptation_disclosed |
| bert_legal_uncased_textcnn_existing | Sun et al. (2024) final-paper-style BERT-TextCNN component (author-manuscript Table 6 best encoder family; final version Figure 3 architecture) | reused existing project S2.4/S2.6 checkpoint; no retraining in this round | existing S2.4 Legal-BERT + TextCNN checkpoint; original train split has 24 flagged EStG-150 overlap rows (4 exact normalized) | de (raw_text_de) | 150 | 0/0/0 | 0.6667 | 0.7232/0.6374/0.6535 | outputs/reports/sep_c2_sun_predecessor_bert_legal_uncased_textcnn_existing_v1.json | completed_diagnostic_training_overlap_flagged |
| sun_rule_only | Sun et al. (2024) complete Stage 2 baseline as reconstructed by this project (B0 formal arm) | project paper-faithful independent reconstruction; existing formal B0 arm reused read-only | existing B0 checkpoint/config; no new training or LLM call in this comparison | de classifier input + en phrase input (existing B0 formal arm) | 150 | 0/0/0 | 0.7400 | 0.7612/0.6879/0.7128 | data/results/b0_formal_arm_v1/modality_labels.json | existing_formal_arm_reused_zero_api |
| direct_llm | not a Sun method; direct LLM replacement arm in the project comparison | existing Direct-LLM formal arm reused read-only; no new LLM call in this comparison | existing Direct-LLM formal prediction snapshot | en (approved_text_en) | 150 | 0/0/1 | 0.8333 | 0.8155/0.7826/0.7695 | data/results/direct_llm_formal_arm_v1/modality_labels.json | existing_formal_arm_reused_zero_api |

### Per-class modality metrics

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
| bert_legal_uncased_probe | obligation | 0.5114 | 0.7627 | 0.6122 | 59 | 88 |
| bert_legal_uncased_probe | permission | 0.6316 | 0.2857 | 0.3934 | 42 | 19 |
| bert_legal_uncased_probe | prohibition | 1.0000 | 0.1000 | 0.1818 | 20 | 2 |
| bert_legal_uncased_probe | definition | 0.3171 | 0.4483 | 0.3714 | 29 | 41 |
| bert_legal_uncased_textcnn_existing | obligation | 0.8103 | 0.7966 | 0.8034 | 59 | 58 |
| bert_legal_uncased_textcnn_existing | permission | 0.7931 | 0.5476 | 0.6479 | 42 | 29 |
| bert_legal_uncased_textcnn_existing | prohibition | 0.9167 | 0.5500 | 0.6875 | 20 | 12 |
| bert_legal_uncased_textcnn_existing | definition | 0.3725 | 0.6552 | 0.4750 | 29 | 51 |
| sun_rule_only | obligation | 0.7105 | 0.9153 | 0.8000 | 59 | 76 |
| sun_rule_only | permission | 0.8857 | 0.7381 | 0.8052 | 42 | 35 |
| sun_rule_only | prohibition | 0.9286 | 0.6500 | 0.7647 | 20 | 14 |
| sun_rule_only | definition | 0.5200 | 0.4483 | 0.4815 | 29 | 25 |
| direct_llm | obligation | 0.8657 | 0.9831 | 0.9206 | 59 | 67 |
| direct_llm | permission | 0.9091 | 0.9524 | 0.9302 | 42 | 44 |
| direct_llm | prohibition | 0.6538 | 0.8500 | 0.7391 | 20 | 26 |
| direct_llm | definition | 0.8333 | 0.3448 | 0.4878 | 29 | 12 |

## Semantic extraction

Sun's author manuscript §5.2 reports only Sun's own extraction with no external six-element method comparison. The rows below are the methods in this project that can actually produce semantic fields; modality classifiers are marked N/A.

| method | task | overall (published evaluator) P/R/F1 | five-span-only P/R/F1 | result file | status |
|---|---|---:|---:|---|---|
| cf_kw | not applicable | N/A | N/A | outputs/reports/sep_c2_sun_predecessor_cf_kw_v1.json | completed_zero_api |
| cf_rnn | not applicable | N/A | N/A | outputs/reports/sep_c2_sun_predecessor_cf_rnn_v1.json | completed_zero_api |
| cf_cnn | not applicable | N/A | N/A | outputs/reports/sep_c2_sun_predecessor_cf_cnn_v1.json | completed_zero_api |
| bert_legal_uncased_probe | not applicable | N/A | N/A | outputs/reports/sep_c2_sun_predecessor_bert_legal_uncased_probe_v1.json | completed_zero_api_weaker_adaptation_disclosed |
| bert_legal_uncased_textcnn_existing | not applicable | N/A | N/A | outputs/reports/sep_c2_sun_predecessor_bert_legal_uncased_textcnn_existing_v1.json | completed_diagnostic_training_overlap_flagged |
| sun_rule_only | Sun literal-overlap per-field span extraction (same evaluator as B0/D1) | 0.5031/0.7160/0.5909 | 0.6435/0.7160/0.6778 | data/results/b0_formal_arm_v1/modality_labels.json | existing_formal_arm_reused_zero_api |
| direct_llm | Sun literal-overlap per-field span extraction (same evaluator as B0/D1) | 0.6061/0.6432/0.6241 | 0.8424/0.6432/0.7294 | data/results/direct_llm_formal_arm_v1/modality_labels.json | existing_formal_arm_reused_zero_api |

### Per-field semantic metrics (same literal-overlap evaluator)

| method | field | ground truth | extracted | precision | recall | F1 |
|---|---|---:|---:|---:|---:|---:|
| sun_rule_only | actor | 48 | 65 | 0.6923 | 0.9583 | 0.8039 |
| sun_rule_only | action | 247 | 244 | 0.8566 | 0.8543 | 0.8554 |
| sun_rule_only | condition | 214 | 239 | 0.6569 | 0.7617 | 0.7054 |
| sun_rule_only | constraint | 302 | 330 | 0.4606 | 0.5265 | 0.4913 |
| sun_rule_only | exception | 13 | 14 | 0.7857 | 0.8462 | 0.8148 |
| direct_llm | actor | 48 | 60 | 0.6500 | 0.8125 | 0.7222 |
| direct_llm | action | 247 | 210 | 0.9524 | 0.8178 | 0.8800 |
| direct_llm | condition | 214 | 135 | 0.9111 | 0.6916 | 0.7863 |
| direct_llm | constraint | 302 | 175 | 0.7257 | 0.4404 | 0.5482 |
| direct_llm | exception | 13 | 10 | 0.8000 | 0.6154 | 0.6957 |

## Blocked/unsupported rows

- bert-base-uncased: no local public weights; offline environment cannot download (Table 6, bert-base-uncased)
- bert-base-cased: no local public weights; offline environment cannot download (Table 6, bert-base-cased)
- bert-large-uncased: no local public weights; offline environment cannot download (Table 6, bert-large-uncased)
- bert-large-cased: no local public weights; offline environment cannot download (Table 6, bert-large-cased)
- bert-legal-cased: no local public weights; offline environment cannot download (Table 6, bert-legal-cased)

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
| bert_legal_uncased_probe | estg_000003 | permission | definition |
| bert_legal_uncased_probe | estg_000004 | permission | obligation |
| bert_legal_uncased_probe | estg_000021 | prohibition | definition |
| bert_legal_uncased_probe | estg_000027 | obligation | definition |
| bert_legal_uncased_probe | estg_000031 | definition | obligation |
| bert_legal_uncased_textcnn_existing | estg_000002 | obligation | permission |
| bert_legal_uncased_textcnn_existing | estg_000003 | permission | definition |
| bert_legal_uncased_textcnn_existing | estg_000004 | permission | definition |
| bert_legal_uncased_textcnn_existing | estg_000021 | prohibition | definition |
| bert_legal_uncased_textcnn_existing | estg_000031 | definition | obligation |
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

Boundary: all values above are measured on the project's independently reconstructed EStG-150 with the frozen published Gold and the existing evaluators. They are not Sun's original 150-sentence phrase Gold and not the paper's reported numbers.
