# 实验项目大白话说明（写给大二的自己看）

> **谁该读这个**：第一次接触这个实验项目的同学。
> **不读这个的代价**：你会被一堆名词（P/R/F1、Stage 2、CoreNLP、Tregex、modality、actor、condition...）淹没。
> **读完这个的收获**：5 分钟理解整个项目在干嘛、我负责什么、接下来怎么动。

---

## 1. 一句话项目（30 秒懂）

**我们要做的事**：把"自动合规检查"中的"读法规"这一步做得更准。

- **合规检查**：工厂要查"我的业务流程有没有违反法规"（GDPR、税法等）。
- **读法规**：要把法规文本"翻译"成结构化的 6 个要素（后面会讲是哪 6 个），这样计算机才能拿去查。
- **做得更准**：用 LLM（GPT、Claude 这些）试试能不能让"读法规"这一步更准。

**实验目的**：**严格控制变量**地回答"加 LLM 涨多少、贵多少、值不值"。

---

## 2. 为什么"读法规"这么难（30 秒懂）

法规长这样（德文税法 EStG）：
> "Einlagen sind gemäß Z 5 zu bewerten, b) Bei entgeltlichem Erwerb..."

英文翻译：
> "Contributions shall be valued in accordance with item 5; b) In the case of acquisition of a business for consideration, the assets shall be recognized at acquisition cost."

要从中抽出：
- **modality**（情态）："shall" = 这是个**义务**
- **actor**（主体）："assets" = 主语
- **action**（动作）："shall be recognized" = 动作是"确认"
- **condition**（条件）："In the case of acquisition" = 在收购时
- **constraint**（约束）：隐含的"按 item 5"
- **exception**（例外）：没出现

抽出来后是结构化数据：
```json
{
  "modality": "obligation",
  "evidence": "shall",
  "actor": "assets",
  "action": "recognized at acquisition cost",
  "condition": "in the case of acquisition for consideration"
}
```

然后拿这结构化数据去查流程图，看业务流程有没有违反这条法规。

---

## 3. 三组方法对比（1 分钟懂）

**Sun 等人 2024 年发了篇论文**，是目前最强的方法。它**分两阶段**：

```
第 1 阶段（Stage 1）：预处理
        ↓
第 2 阶段（Stage 2）：读法规，抽 6 要素 ← 我们只改这个
        ↓
第 3 阶段（Stage 3）：拿 6 要素查流程图，输出违规定位
```

**我们只改 Stage 2**。Stage 1 和 Stage 3 三组都用**同一份**。

三组怎么改：

| 组名 | 通俗讲 | 正式叫 | LLM |
|---|---|---|---|
| 第 1 组 | 纯按 Sun 论文的"规则"自己重写 | **B0**（baseline） | ❌ 不用 |
| 第 2 组 | B0 + 实在搞不定的字段让 LLM 修一下 | **H1**（hybrid） | ✅ 用一点 |
| 第 3 组 | 完全让 LLM 抽 6 要素 | **D1**（direct LLM） | ✅ 全用 |

**对比什么**：三组都跑**同一批 150 条法规**，都进**同一份 Stage 3**，看**谁下游更准**。

---

## 4. P / R / F1 是什么（30 秒懂）

P = Precision（准不准）= 抽出来的 10 个里 8 个对 = 80%
R = Recall（全不全）= 应该抽 10 个，抽到了 8 个 = 80%
F1 = P 和 R 的"综合分"（都高 F1 才高）

**我们要的就是看三组的 F1 涨不涨**。

- B0 的 F1 = 0.70（baseline）
- H1 的 F1 = 0.75（+5%）
- D1 的 F1 = 0.73（+3%）

**就说明 H1 > D1 > B0**——H1 是性价比最高的。

---

## 5. 关键问题：为什么不能和 Sun 论文比绝对值？

Sun 论文报告：Winter 0.58/0.89/0.70、Sun 0.77/0.83/0.80。

**我们不能和这些绝对值比**，因为：
- Sun 用什么数据我们不知道（Sun 没公开 150 句的具体 ID）
- Sun 的词典是什么我们不知道
- Sun 的训练权重我们没有

**所以我们只能和自己比**：
- 不比"我是不是比 Sun 0.80 强"
- 比"我加 LLM 涨不涨"——**B0 vs H1 vs D1 的差值**

这就是为什么你导师让你"把脉络讲清楚"——**核心叙事是涨了多少，不是赢了前人**。

---

## 6. 我（用户）要做什么

**只有一件事 AI 干不了**：

> **审 150 条法规，人工找 6 要素作为"标准答案"（叫 Gold）**

为什么 AI 干不了？因为如果 AI 标了"标准答案"，然后 AI 又去对答案测 P/R，那就是**自己出题自己判**——结果不可信。

**这是体力活，5-10 小时**。每条法规要做：
1. 读德文原文 + 英文翻译
2. 标 6 要素的字符位置（哪个词是 actor、哪个词是 action...）
3. 标 modality 类别（obligation / prohibition / permission / definition）
4. 标 actor-action 对应关系（谁做什么）
5. 标顺序关系（如果有两个 action，哪个先哪个后）

**AI 帮你**：
- 准备审核包（每条法规 + 英文翻译 + 字段模板）
- 自动检查你标的对不对（字符位置对得上原文吗）
- 自动算 P/R/F1（你标的是"标准答案"，三组预测对比这个标准答案）
- 写代码（Sun 论文怎么写我们就怎么写）
- 写文档（怎么做的、为什么这样做）

**AI 不帮你**：
- 标 Gold（你自己标）
- 跑真实 LLM（要你授权 + 给钱）
- 任何"因为我没标就猜一个"的事

---

## 7. "Sun 没公开的东西我自己找" — 怎么找

| Sun 没公开 | 我们怎么办 |
|---|---|
| 150 句法规 ID | 按 Sun 论文 4 个标准自己抽（complete / sequential / 包含法律行为 / > 20 词） |
| 6 要素的"正确答案" | 你自己审 + 标 |
| 词典（marker） | 用公开的（LexNLP、Sleimi 论文方法、Wiktionary），记下来源 |
| 模型权重 | 自己按 Sun 论文描述的 BERT-TextCNN 结构训（不追原始 checkpoint） |
| 训练数据 | 用 Sun 官方 Archive.org 公开的 EStG 文本 |

**关键**：每一项都**记下来源 + 版本 + 日期**——这是我们的"资源贡献"（别人能照着复现）。

---

## 8. 怎么和前人比

**和前人比"相对趋势"**：
- 我们的 B0 跑出来 F1=0.65，Sun 论文报告 Sun 0.80
- 我们的 H1 跑出来 F1=0.72，Sun 论文报告 Sun 0.80
- **不直接比 0.65 vs 0.80**（数据不同）
- **报告**：我们的 H1 相对 B0 涨了 0.07（+11%），**说明加 LLM 真的有用**

**和前人比"绝对值"（小心）**：
- 如果一定要比，要在论文里**明确声明**：数据不同、词典不同、Gold 不同
- 这种比较 CCFC 审稿人能接受，但**不能**说"我们赢了 Sun"

---

## 9. 现在到底是什么情况（2026-07-12）

| 项 | 状态 |
|---|---|
| 三组方法的**设计** | ✅ 都写好了（4 个文档里） |
| B0 的**代码** | 🟡 文档批准后开始 |
| 150 条法规的**审核** | 🟡 你可以开始（在 override 副本上练手） |
| H1/D1 跑**真实 LLM** | ⛔ 需要你授权 + 给钱 |
| Stage 3 冻结 | ⛔ 等 B0 跑通 |

**整个项目预计 6 周（单人）**。你审 150 条要 5-10 小时。

---

## 10. 名词速查（看到不认识的查这里）

| 名词 | 意思 | 通俗 |
|---|---|---|
| BPMN | Business Process Model and Notation | 业务流程图 |
| EStG | Einkommensteuergesetz | 德国所得税法 |
| GDPR | General Data Protection Regulation | 欧盟数据保护法 |
| BPM | Business Process Management | 业务流程管理 |
| Stage 1 | 数据预处理 | 文本清洗、分句 |
| Stage 2 | 法规解析（抽 6 要素） | "读法规" |
| Stage 3 | 合规检查 | 拿 6 要素查流程图 |
| modality | 情态 | shall/may/must/means 之类 |
| actor | 主体 | 谁来做动作 |
| action | 动作 | 做什么 |
| condition | 条件 | 什么时候做 |
| constraint | 约束 | 怎么做、不能超过什么 |
| exception | 例外 | 什么时候不算 |
| BERT-TextCNN | 一种文本分类神经网络 | Sun 论文用这个判 modality |
| CoreNLP | Stanford 句法分析工具 | 分析句子结构的工具 |
| Tregex | 树模式匹配 | 在句法树里找模式的工具 |
| marker | 标记词 | shall、must、except 之类的提示词 |
| lexicon | 词典 | 收集所有 marker 的表 |
| baseline | 基线 | 起点，用来对比的"对照组" |
| P / R / F1 | Precision / Recall / F1-score | "准 / 全 / 综合" 三个指标 |
| paper-faithful | 论文级忠实 | 按论文方法做但代码自己写 |
| reconstruction | 重建 | 重新做一遍 |
| snapshot | 快照 | 某一时刻的全状态记录 |
| audit | 审计 | 检查有没有违规 |
| provenance | 来源 | 这东西从哪来、什么时候、什么版本 |
| route | 路线 | 整个实验的计划 |
| blocker | 卡点 | 让实验停下来的问题 |
| Stage 3 frozen | Stage 3 冻结 | Stage 3 跑确定版本不动 |

---

## 11. TL;DR（30 秒版）

> 我要做：自动合规检查的"读法规"那一步，看加 LLM 涨多少。
>
> 方法：自己重写 Sun 论文的 Stage 2，叫 B0；B0+LLM 叫 H1；纯 LLM 叫 D1。
>
> 测什么：三组在 150 条法规上跑同一份 Stage 3，比 F1 涨多少。
>
> 我做什么：审 150 条法规找 6 要素作为标准答案。
>
> AI 做什么：写代码、跑实验、写文档、算指标。
>
> 关键：不和 Sun 论文绝对值比，只比 B0 vs H1 vs D1 的**增量**。
>
> 接下来：审 4 个文档（每份 10-20 分钟），拿 override 副本练手 5-10 条。
