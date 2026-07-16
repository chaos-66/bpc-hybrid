# Sun Baseline Audit（v2）

正式 baseline 的含义是最终发表版 Sun Stage 2 的完整非 LLM 重建，而不是
“rule-only”简化方法。遗留 ID `sun_rule_only` 暂不改名，以避免无关文件/API
迁移，但其当前 runner 只实现 marker/heuristic approximation，正式状态为 blocked。

完整 baseline 至少包含：最终版 BERT-TextCNN 四类 modality；Stanford CoreNLP
preprocessing；Tregex/Tsurgeon + domain markers 的六概念抽取；论文规定的 action
抽取顺序和 rule record；以及官方 modality 数据与 phrase Gold 的统一评估。

官方补充包已找到，但完整 Stage 2 源码、trained model、150 句 ID/phrase Gold、
完整规则/marker 仍缺失，所以 exact/original reproduction 不可声明。

`sun_llm_fallback` 必须复用该完整 baseline，不能复用当前弱 heuristic runner 后
声称相对提升。详情见 `docs/research/SUN_FINAL_VERSION_AND_DATA_AUDIT.md`。
