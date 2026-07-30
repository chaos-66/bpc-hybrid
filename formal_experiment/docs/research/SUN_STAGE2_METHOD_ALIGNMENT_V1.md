# Sun Stage 2 方法级对齐审计（v1）

**日期**：2026-07-30

**范围**：EStG-150 development B0；不修改 Gold；不调用 LLM/API

**状态更正（2026-07-30）**：本文件最初给出的
`paper-specification-faithful reconstruction` 结论已撤回。逐字符复查后发现 v1 将
Actor/Constraint 的直接支配 `<` 操作化为任意后代 `<<`，并使用论文未公布的四类
上下文跨字段破坏性优先级。以下 v1 运行结果保留为历史 development 证据，不再作为
方法忠实性证明。当前方法对齐状态及 13 条 mini pipeline 阻断见 RWI-0035。

## 1. 原文依据

唯一方法依据为本地只读一手文献
`references/papers/Sun_2024_Design_time_BPC.pdf`：

| 方法项 | 原文位置 | 本地实现 |
|---|---|---|
| 六概念定义 | PDF p.10，Section 4.2.2，Table 2 | modality / actor / action / condition / constraint / exception |
| marker 例项 | PDF p.11，Table 4 | marker 作为显式版本参数；完整原作者清单未公开 |
| modality | PDF p.11，Section 4.2.2 “Modality” | 三类 `MD`-in-`VP` Tregex，命中后 Tsurgeon prune |
| actor | PDF pp.11–12，“Actor”及 Figure 7 | `NP + actor marker` 候选，再用 subject/object、主动/被动和 PP/IN 依存门控 |
| action | PDF pp.11–12，“Action” | 删除 modality/condition/constraint/exception 后，枚举每个剩余 `VP` |
| condition | PDF p.12，“Condition” | `SBAR/PP` 包含 condition marker，命中后 prune |
| constraint | PDF p.12，“Constraint” | `NP` marker 与 `PP-(IN, NP)` marker 结构，命中后 prune |
| exception | PDF p.12，“Exception” | `SBAR/PP/NP-IN` marker 结构，命中后 prune |
| 评价 | PDF p.17，Section 5.2.1；p.18 Table 8 | statement 内同类型 span 任意非空字符交集；无一对一、无 clause alignment、无比例阈值 |

PDF p.13 明确说明 Table 4 只是初始 marker 集，作者又扩展了 marker；但论文和官方包
没有发布完整扩展清单。因此本地使用 `public_marker_lexicon_en_v2` 作为**参数替代**，
不声称它是 Sun 原始 marker。

## 2. `v10a` 与论文方法的实质差异

旧比较输入 `s27_estg150_b0_enhanced_v10a` 的配置已经明确写有
`paper_faithful_b0=false`、`tsurgeon_enabled=false`，并叠加：

- typed-scope resolver；
- 德英 heuristic clause alignment；
- custom deontic-nucleus segmentation；
- definition resolver；
- custom actor-action ownership resolver。

这些都是本项目 development extension，不在 Sun Section 4.2.2 中。因此旧版本可
保留为增强方法开发证据，但不能再作为“除数据和参数外都与 Sun 相同”的 B0。

新版本 `b0_sun_paper_spec_v1` 完全不导入上述五个模块；使用 CoreNLP 4.5.10、真实
Tregex/Tsurgeon 和相同 Sun literal evaluator。随后复核确认其 `<`/`<<` 与跨字段
剪枝仍有实质偏差，所以本段只说明它与 `v10a` 的隔离，不再说明它已忠实实现论文。

## 3. 运行结果与数据口径

运行：`s27_estg150_b0_sun_paper_v1`，150/150 records，0 LLM/API calls，输出位于
`outputs/development/s27_estg150_b0_sun_paper_v1/`。

| 字段 | Gold | Extracted | P | R |
|---|---:|---:|---:|---:|
| Modality | 231 | 266 | 72.93% | 84.85% |
| Actor | 48 | 91 | 31.87% | 50.00% |
| Action | 247 | 655 | 67.33% | 86.23% |
| Condition | 214 | 193 | 69.95% | 70.09% |
| Constraint | 302 | 79 | 68.35% | 25.83% |
| Exception | 13 | 3 | 100.00% | 23.08% |
| Overall | 1055 | 1287 | 66.51% | 62.94% |

运行实际处理 150 个 benchmark records、266 个 CoreNLP sentences，执行 247 个展开后
Tregex patterns、439 次 Tsurgeon surgery。这里的“150”是记录数，不是 150 个只含一个
句子的 Sun 原测试样本：当前冻结英文在 CoreNLP 下为 266 句，人工 Gold 为 231 clauses、
1055 phrases；Sun Table 8 的原数据是 150 sentences、443 phrases，其中 Constraint
只有 35 个。两套绝对数量和 P/R 不能视为同测集复现值。

## 4. 可声明与不可声明

当前可以声明：

- 论文公开的 parser、Tregex/Tsurgeon 规则族、依存 actor、action 执行依赖和 Table 8
  评价规则已形成独立、可执行、版本化的对齐候选与回归流水线；该候选尚未通过六字段
  无回归门禁；
- 数据、classifier weights/训练参数和 marker 参数与作者原实验不同；
- 当前 development 结果证明 `v10a` 的 335 个 Constraint 不是 Sun 论文规则的直接输出。

不可声明：

- exact/original Sun reproduction；
- v1 或当前 mini v2 已是 paper-faithful reconstruction；
- 当前 150 records 等同于 Sun 原 150 sentences；
- 当前 1055 Gold phrases 与 Sun 原 443 phrases 标签分布相同；
- 仅凭当前 P/R 高低判断实现是否忠实，或反向修改 Gold/规则追论文数字。

exact reproduction 仍缺：作者完整 marker lexicon、完整 Stage 2 源码、训练权重和原
150-sentence phrase Gold。
