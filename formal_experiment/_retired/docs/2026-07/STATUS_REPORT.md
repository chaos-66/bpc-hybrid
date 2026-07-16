# BPC-Hybrid 当前状态

**日期**：2026-07-11  
**状态**：研究目标已重新校准；正式路线处于 final-version/data alignment 阶段

## 目标

只改 Sun 2024 Stage 2，做三方对比：最终发表版 Sun Stage 2 非 LLM baseline、
同一 baseline + 受控 LLM fallback、纯 LLM 替换整个 Stage 2。Stage 3 不作为
创新点，三组使用完全相同的冻结实现与输入。

## 新发现

- 本地 Sun PDF 是较早作者稿；最终版使用 BERT-TextCNN 表述，必须重新对齐。
- Sun 官方 Archive.org 补充包存在，句子级 EStG 数据并非全部缺失。
- 官方 Stage 3 的 57 个输入文件与导师包/Winter 副本逐字节一致。
- 导师包来源是 Sun 作者；其中 `model_check` 内容与 Winter prototype 的 112 个
  非缓存文件逐字节一致，不含 Sun 新 Stage 2 实现。来源与代码身份不矛盾。
- 原 150 句 phrase Gold、完整 marker、训练模型/代码仍缺失。
- 旧 Sun 稿引用的 Sleimi 法律语义抽取框架是短语规则和 marker 的关键方法谱系；
  最终版参考文献表删除了该引用。
- marker 障碍可部分解除：condition/constraint 有 LexNLP 公共表，actor 可按
  Sleimi 的 Wiktionary 定义规则自动生成；exception 完整表和正式 phrase Gold
  仍缺失。
- Barrientos/RC4PC 并不直接输出 Sun 六要素；可借鉴 strict schema、controlled
  vocabulary、多次运行稳定性和确定性 normalization，并显式适配为 Sun spans。
- 用户已接受公开 marker 重建、论文级独立实现和重新训练权重，并将工作语言锁定为
  经人工核对的英文译文；用户本人负责正式六要素 Gold 判断。
- Sun 作者稿 Stage 3 确实与 Winter 比较 violation detection：Winter
  P/R/F1=0.58/0.89/0.70，Sun=0.77/0.83/0.80。我们的必做比较是同一冻结
  Stage 3 下 B0/H1/D1 的端到端比较；Sun 数字在数据不同时只作参考。

## 状态值

- `integrity_pass = true`
- `human_review_input_ready = true`（输入已就绪，可以开始人工审核；
  authoritative `experiment_contract.human_review_gate.status` 已
  显式允许；membership + schema + tool + 150 sample_id 全部就位）
- `human_review_freeze_ready = false`（150/150 尚未全部 adjudicated）
- `formal_gold_publication_ready = false`（route v2 仍 reopened；
  formal_gold_publication_gate.status=blocked_pending_route_data_stage3_re_lock）
- `final_experiment_ready = false`（同上 + 三方法 + 冻结 input/gold）
- 真实 LLM/API 未调用

> 该快照由 2026-07-13 11:30 之前的 v1 状态机写成；2026-07-13 11:30
> 路线锁已升级为 4 门禁：input / freeze / formal-gold / final-experiment。
> 含义变化以 Event 21/22 为准；本快照历史内容保留以便追溯。

## 不再执行的旧计划

- 不把 marker-enriched/OCR/LLM-translated EStG-150 直接冻结为正式数据；
- 不把当前关键词/启发式 `sun_rule_only` 称为完整 Sun baseline；
- 不把 Winter prototype 直接当成 Sun 新实现；
- 不伪造 12 个 proprietary 智能电表 BPMN。

## 下一步

设计并冻结德文到英文的翻译与人工审核协议 → 生成用户审核的正式六要素 Gold →
冻结 public-source reconstructed lexicon → 独立实现完整 baseline → 预注册
field-level LLM trigger 与 direct-LLM dual-view prompt → 锁定不变 Stage 3 →
正式运行三组端到端比较。

完整说明：`ROUTE_LOCK.md`、`SUN_FINAL_VERSION_AND_DATA_AUDIT.md`、
`SUN_REFERENCE_SNOWBALL_AND_MARKER_AUDIT.md` 与
`STAGE2_LLM_INNOVATION_DESIGN.md`、`USER_DECISION_LOCK_2026-07-12.md`。
