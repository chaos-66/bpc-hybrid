# SEP-C3 Direct-LLM E/S/J 模块精简与离线拼装检查（零 API）

**状态**：prompt 资产已修改并通过八组合离线检查；未运行真实 API，未重跑消融，未新增性能结论。

**边界**：本轮只处理 Direct-LLM 的 E/S/J 提示模块。历史 v6 prompt、`ablation_v1/v2`、已完成的 450-call 单因素结果与 runner 均保留不变。

## 1. 精简后的职责划分

| 模块 | 现在唯一承担的职责 | 删除或移出的重复指导 |
|---|---|---|
| 公共部分 | 最小任务、输入 envelope、字段名称、固定 `method`/`validation` 值和最低输出接口 | 原公共部分中承载的语义与作用范围规则移入 S；不在公共部分复述 S/E/J 的详细规则。 |
| S：语义判读规则 | 各要素定义、归属、作用范围、歧义、空值语义、clause/coordination/relation 与 ID 规则 | 合并旧规则 13 与 25 的 constraint 定义；合并旧规则 11、26、27 的 action 排除规则；合并旧规则 12 与 27 的 condition 定义；合并旧规则 17 到统一歧义规则；合并旧规则 15/18 的空数组约定；删除旧规则 7 与 24 对精确坐标的重复强调；把 `to the extent` 等 cue 改为按功能判断，避免旧规则 27 的冲突。 |
| E：示例 | 用少量合成边界例子展示语义规则如何应用 | 六个完整 JSON 示例改成五个紧凑语义选择示例；删除示例 5 与旧规则 25 重复示范的 legal-reference constraint；删除每个示例重复的顶层键、`method`、`validation`、枚举和坐标自检文字；不重复 S 的规则解释，也不从正式测试集或 Gold 选取例子。 |
| J：输出组织 | 只负责序列化表达：裸 JSON、无 Markdown/说明文字、无空结果散文拒绝 | 删除与公共接口重复的键集合、固定值、schema-only 自检、枚举与类型强调；这些信息已由公共接口和固定 schema 承担。 |

## 2. 长度变化（Unicode 字符数，非 token）

- 历史 v6 prompt 文件：17,038 chars。
- 历史实际发送内容（system 6,172 + user template 296 + examples block 9,332，不含样本正文）：15,800 chars。
- 新 `E=1,S=1,J=1` 实际拼装内容：system 5,376 + user 2,452 = 7,828 chars。
- 新 `111` 文件（含 XML 注释、标题和 fence）：8,478 chars。
- 相对历史实际发送内容减少约 50.5%。
- 模块长度：S 3,743 chars；E 2,349 chars；J 263 chars；公共 system 1,366 chars；公共 user envelope 101 chars。

需注意：字符数下降不等于性能提升；真正效果只能由后续授权运行判断。

## 3. 八组合离线检查

组合编码为 `ESJ`。检查脚本：`scripts/build_modular_prompt_v1.py --check`；报告：`outputs/reports/sep_c3_modular_prompt_v1_offline_check.json`。

| 组合 | system chars | user chars | 合计 chars | 模块拼装 | 最低接口 | `prompt_loader` |
|---|---:|---:|---:|---|---|---|
| 000 | 1,366 | 101 | 1,467 | 通过 | 通过 | 通过 |
| 001 | 1,631 | 101 | 1,732 | 通过 | 通过 | 通过 |
| 010 | 5,111 | 101 | 5,212 | 通过 | 通过 | 通过 |
| 011 | 5,376 | 101 | 5,477 | 通过 | 通过 | 通过 |
| 100 | 1,366 | 2,452 | 3,818 | 通过 | 通过 | 通过 |
| 101 | 1,631 | 2,452 | 4,083 | 通过 | 通过 | 通过 |
| 110 | 5,111 | 2,452 | 7,563 | 通过 | 通过 | 通过 |
| 111 | 5,376 | 2,452 | 7,828 | 通过 | 通过 | 通过 |

检查项全部为 true：八组合渲染、公共最低接口标记、关闭模块文本不残留、生成文件与 renderer 一致、manifest 有效、user template 可渲染、无悬空 `{few_shot_block}`、`prompt_loader` 抽取与 renderer 一致。全程零 API、零网络。

## 4. 仍无法完全分离的语义联系

1. E 的紧凑示例仍会展示少量字段形态与坐标表示；它不再承担格式规则，但作为示例无法完全不触及输出组织。
2. 公共部分、S、E、J 共用同一套字段词汇（clause、actor、action、condition 等），这是任务接口本身，不是重复指导。
3. 固定 schema 和运行时 validator 会共同校验坐标、ID、枚举和顶层结构；任何模块若破坏坐标，都可能被 fail-closed 拒绝。这种计算耦合不能靠文本拆分消除。
4. 公共部分的固定 `method`/`validation` 接口不随开关变化，因此三个模块关闭后仍会保留最低可解析对象骨架。
5. 旧单因素效应仍只能作为历史描述；本轮没有证明 E/S/J 中的哪一个是消融不显著的原因。

## 5. 主要文件

- `prompts/sun_compat/modular_v1/common_system.md`
- `prompts/sun_compat/modular_v1/user_envelope.md`
- `prompts/sun_compat/modular_v1/semantic_rules_S.md`
- `prompts/sun_compat/modular_v1/examples_E.md`
- `prompts/sun_compat/modular_v1/output_format_J.md`
- `prompts/sun_compat/modular_v1/generated/direct_llm_modular_*.md`
- `prompts/sun_compat/modular_v1/generated/manifest.json`
- `src/bpc_hybrid/modular_prompt.py`
- `scripts/build_modular_prompt_v1.py`
- `tests/test_modular_prompt_v1.py`

## Post-run update (2026-09-15)

Before the real four-arm run, the basic output conventions (zero-based start / exclusive end, ID uniqueness, same-clause reference legality) were moved to `common_system.md`; S keeps element semantics, scope, ambiguity, and normative-relation guidance. The generated prompts and offline check were regenerated. The real 111/011/101/110 validation is reported in `sep_c3_modular_ablation_analysis_v1.md`; the modular v1 full prompt was rejected and the old v6 prompt remains the default.
