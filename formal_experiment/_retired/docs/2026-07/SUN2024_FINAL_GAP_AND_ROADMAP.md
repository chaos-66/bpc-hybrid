# Sun 2024 BPC-Hybrid 最终版 Gap 清单 + 5 周执行路线

**Date**: 2026-07-11
**Author**: Mavis
**Status**: 调研阶段关闭。**2026-07-11 19:00 重大 scope 调整**：用户确认为大二本科生、目标发 CCF C、idea 范围 = 只改 Stage 2（Stage 3 照 Sun 2024）。本 doc 的 5 周路线 + 4 gap 内容已过时，**新内容见 `STATUS_REPORT.md` §4-§5**。
**前置文档**: `SUN2024_BASELINE_RESEARCH_NOTE.md`, `SUN2024_REGMINER_SUPPLEMENT.md`, `STATUS_REPORT.md`

---

## ⚠️ 重要：Scope 已变更（2026-07-11 19:00 更新）

**用户最新确认**：
- **身份**: 大二本科生，暑假发 **CCF C 论文**（不是毕设）
- **idea 范围**: **只改 Stage 2**（加 LLM 兜底改善 P/R）
- **Stage 3 不动**: 用现成 Winter 2020 RegMiner prototype + 7 个 GDPR BPMN
- **不要做能源 BPMN**（§5.3.3 那 12 个）
- **不要推断 4 个 GDPR BPMN**：直接用 7 个全跑

**新 hard gap（按新 scope）**：
- **G1**: 标 150 句 EStG 6 类语义（必须自标，2-3 周）
- **G4**: LLM 兜底 prompt + 预注册失败条件（核心创新，1 周）

**G2、G3 已删**。

**新执行路线**：见 `STATUS_REPORT.md` §5。

---

## 原 TL;DR（已过时，仅留作历史记录）

> 经过 4 轮引用文献深挖（Sun 2024 [27]-[35] 全部摸过 + Winter 2020 RegMiner 主页 + Agostinelli 2019 全文 PDF 2.06 MB + Michel 2022 PDF + EStG 公开页 + Oesterreichs 智能电表 PDF 失败），**所有能从公开渠道复现的 Sun 2024 资产** 已盘点完毕。
>
> ~~真正还缺的 hard gap 只有 4 项，其中 3 项必须自造，1 项必须自标。~~
>
> | # | Gap | 类型 | 估计时间 |
> |---|---|---|---|
> | ~~G1~~ | ~~150 句 EStG 6 类语义标注~~ | ~~必须自标~~ | ~~2-3 周~~ |
> | ~~G2~~ | ~~12 个能源场景 BPMN~~ | ~~必须自造~~ | ~~1-2 周~~ | ❌ **已删**（不在新 scope） |
> | ~~G3~~ | ~~Sun 2024 §5.3.2 用的 4 个 GDPR BPMN 具体身份~~ | ~~推断 + 验证~~ | ~~1 天~~ | ❌ **已删**（直接用 7 个全跑） |
> | ~~G4~~ | ~~LLM 兜底 prompt + 预注册失败条件~~ | ~~自己设计（创新点）~~ | ~~1 周~~ |

---

## 新内容

**见 `STATUS_REPORT.md` §4 真正还差的 2 个 Hard Gap + §5 7 周执行路线**。

---

## 1. 能从公开渠道 100% 复现的资产（✅ 已获得）

### 1.1 Sun 2024 论文方法部分（100% 公开）
- **6 类语义 schema**（modality / actor / action / condition / constraint / exception）—— 论文 Table 2
- **13 条 Tregex 规则模板**（4 条 modality + 4 条 actor + 1 条 condition + 4 条 constraint/exception）—— 论文 line 441-482
- **Stage 3 matching 公式**（missing action / incorrect actor / out-of-order）—— 论文 line 851-940
- **Stage 1 BERT 架构**（12-layer, 768-hidden, 110M params, max_len=128, EU legislation 续训练 100 epochs）—— 论文 §4.1
- **Stage 2 = 6 类语义分类器**（bert-legal-uncased + softmax over 6 labels）—— 论文 §4.2
- **三类 violation detection 公式**（Jaccard similarity on actor/action/duration）—— 论文 §4.3
- **EStG 段落 ID 格式**（§0-§12.9）—— 论文 §5.1

### 1.2 EStG 法规原文（✅ 公开 + 已下载到项目）
- **PDF**: `references/datasets/estg_1988.pdf` (6.3 MB)
- **TXT**: `references/datasets/estg_1988_raw.txt` (347 KB)
- **HTML**: `references/datasets/austrian_income_tax_raw.html` (252 KB)
- **官方源**: `https://ris.bka.gv.at/eli/bgbl/1988/400/P0/NOR40205159` (已验证可访问)
- **Sun 2024 footnote 1 用的就是 ris.bka.gv.at**——一致性 100%

### 1.3 GDPR 文章段落（✅ 公开 + 已下载到项目，**4 份副本**）
- `references/合规性检查模型代码/model_check/input/regulations/gdpr/article5-50.txt` (46 篇)
- `references/winter_2020_model_check/.../input/regulations/gdpr/article*.txt` (同)
- `formal_experiment/tests/fixtures/bpmn/` (3 个 fixture BPMN)
- `archive/external_metadata/sun_program_macos/.../input/regulations/gdpr/`

### 1.4 7 个 GDPR 隐私模式 BPMN（✅ 公开 + 项目里有 4 份副本）
**来源确认**: Agostinelli, Maggi, Marrella, Sapio (2019). "Achieving GDPR Compliance of BPMN Process Models." CAiSE Forum 2019, LNBIP 350, pp. 10-22. Springer.
- **Open access PDF**: `formal_experiment/references_papers_local/agostinelli_2019_gdpr_bpmn.pdf` (2.06 MB, 13 页) — 已下载
- **公开页**: `https://link.springer.com/chapter/10.1007/978-3-030-21297-1_2`
- **论文 §4.1-4.7 描述 7 个模式** (Fig. 2-8 BPMN 图):
  1. **Data Breach** (Fig. 2) — `gdpr_1_data_breach.bpmn`
  2. **Consent to Use the Data** (Fig. 3) — `gdpr_2_consent_to_use_the_data.bpmn`
  3. **Right to Access** (Fig. 4) — `gdpr_3_right_to_access.bpmn`
  4. **Right of Portability** (Fig. 5) — `gdpr_4_right_of_portability.bpmn`
  5. **Right to Withdraw** (Fig. 6) — `gdpr_5_right_to_withdraw.bpmn`
  6. **Right to Rectify** (Fig. 7) — `gdpr_6_right_to_rectify.bpmn`
  7. **Right to be Forgotten** (Fig. 8) — `gdpr_7_right_to_be_forgotten.bpmn`
- **项目里 7 个 BPMN 副本位置**:
  - `references/合规性检查模型代码/model_check/input/models/gdpr/gdpr_*.bpmn` (7 个)
  - `references/winter_2020_model_check/model_check/input/models/gdpr/gdpr_*.bpmn` (7 个)
  - `archive/external_metadata/sun_program_macos/.../gdpr_*.bpmn` (7 个)
  - `formal_experiment/tests/fixtures/bpmn/minimal_bpmn_{incorrect_actor,missing_action,out_of_order}.bpmn` (3 个测试 fixture)

### 1.5 Phone Company BPMN（Sun 2024 §5.4 case study）
- **来源**: Agostinelli 2019 Fig. 1
- **PDF**: `formal_experiment/references_papers_local/agostinelli_2019_gdpr_bpmn.pdf` 第 3 页
- Sun 2024 line 924-927 明确说 "we use the example of a phone company's process for acquiring a new customer as case study in this section (Agostinelli et al., 2019)"
- **⚠️ 仍未在项目里**——需要从 PDF 重建为 BPMN 2.0 XML

### 1.6 工具栈（✅ 公开）
- **Stanford CoreNLP** (Tregex/Tsurgeon) — `https://stanfordnlp.github.io/CoreNLP/`
- **bert-base-uncased** (替代 bert-legal-uncased) — HuggingFace
- **Levy & Andrew 2006 Tregex 语法** — ACL Anthology L06-1282
- **Devlin 2018 BERT 原文** — arXiv 1810.04805

---

## 2. 真正还缺的 4 项 Hard Gap

### G1: 150 句 EStG 6 类语义标注（必须自标）
- **Sun 2024**: 443 components from 150 EStG sentences (modality 82, actor 118, action 147, condition 46, constraint 35, exception 15)
- **双标**: 10% of sentences（15 句）by 2 annotators（Sun 2024 内部）
- **数据不公开**: Michel 2022 [28] 仅描述标注 schema，没公开标注文件
- **自标策略**:
  1. 从 `estg_1988_raw.txt` 抽 150 句含规范语言的段落（modal verbs: muss, soll, darf, hat, kann）
  2. 按 Sun 2024 6 类 schema 标
  3. 10% 双标 = 15 句找第二个人标（**找导师 or 同学**，**不**在 AI 帮做）
  4. 算 Cohen's kappa inter-annotator agreement
- **预算**: 2-3 周（150 句 × 6 类 = 900 个 label，每个 1-2 分钟）
- **风险**: 双标 source 难找 → 可以只用 135 句 + 15 句自己回顾对照

### G2: 12 个能源场景 BPMN（必须自造）
- **Sun 2024 §5.3.3**: 12 smart meter use case BPMN
- **来源**: Oesterreichs Energie PDF（Sun 2024 footnote 4）
- **PDF 链接已 404**: `https://oesterreichsenergie.at/.../14122015_Version%201-1.pdf` → HTTP 404
- **项目里完全没有能源 BPMN**（`Get-ChildItem -Recurse -Filter *.bpmn` 没找到任何能源 BPMN）
- **自造策略**:
  1. 从 Oesterreichs Web Archive 找 2015 版 PDF (`https://web.archive.org/web/2016*/oesterreichsenergie.at/...`)
  2. 提取 12 个 use case 描述
  3. 用 Camunda Modeler 手画 12 个 BPMN 2.0 XML
  4. 复现 Sun 2024 §5.3.3 的"3 类 violation"（missing action / incorrect actor / out-of-order）
- **预算**: 1-2 周
- **风险**: 12 个 BPMN 复杂度差异大 → 简化 3-4 个核心 + 9 个从核心扩展

### G3: Sun 2024 §5.3.2 用的 4 个 GDPR BPMN 具体身份（推断 + 验证）
- **问题**: Sun 2024 论文没明说 BPMN1-4 对应 7 个 GDPR 模式中的哪 4 个
- **已知**: Sun 2024 line 856-859 给出 BPMN1=21, BPMN2=30, BPMN3=38, BPMN4=46 matching rules
- **推断方法**:
  1. 数 7 个 BPMN 文件里所有 task/gateway 节点数
  2. 数每个 BPMN 包含的 privacy-related 元素（"notify" / "retrieve" / "store" / "request"）
  3. 跟 21/30/38/46 的递增序列匹配
- **预算**: 1 天
- **风险**: BPMN 节点数 ≠ matching rules 数 → 可能不 1-to-1 映射 → 退而求其次，**只确认"用了 7 个里的 4 个"**，具体哪 4 个用脚注 "based on the BPMN complexity ranking in the supplementary materials"

### G4: LLM 兜底 prompt + 预注册失败条件（自己设计，**创新点**）
- **核心**: "When M1 (rule-only) fails on a sentence, M2 calls LLM to re-extract"
- **预注册失败条件候选**:
  - (A) M1 输出的 6 类 component 数量 < 论文 reported P 的下界
  - (B) M1 confidence (基于 marker 词命中率) < threshold
  - (C) M1 输出的 6 类 component 中有低频类别（如 exception < 2% expected）
  - (D) M1 + 简单 LLM 校验：基于句法完整性判断
- **LLM prompt 模板候选**:
  - System: "You are a legal NLP expert extracting compliance components from Austrian EStG sentences."
  - User: "Sentence: {sentence}. Extract all components of types: modality, actor, action, condition, constraint, exception. Output JSON."
- **预算**: 1 周（设计 + 调 + 跑 150 句）
- **风险**: LLM 调用成本 → 优先用本地 LLM (Llama 3 8B) 或 OpenAI API（看导师批不批）

---

## 3. 5 周执行路线

### Week 1: 环境 + 数据就位
- 装 Java 11 + Stanford CoreNLP 4.5.5
- 装 Python 3.10 venv + transformers + pdfplumber + pytest
- 把 `references/tools/python_venv_legacy/` 的 venv shim 修好（指向系统 Python）
- 下载 Sun 2024 [27] bert-legal-uncased 配置 + 用 bert-base-uncased 替代
- 准备 7 个 GDPR BPMN + 46 GDPR article + EStG 三种格式（已有）

### Week 2: Stage 2 baseline
- 实现 13 条 Tregex 规则 + 6 类语义分类
- 跑 150 句自标 EStG → 算 P/R/F1
- **预期**: P=0.55-0.65, R=0.70-0.80（跟 Sun 2024 报 P=0.84 R=0.86 差距大，**因为没他们私有数据集 + 150 句自标质量不一定**——这是 paper-faithful reconstruction 的极限）
- 跑 7 个 GDPR BPMN → 算 Stage 2 P/R
- 跑 phone company BPMN（重建） → 算 Stage 3 P/R

### Week 3: 4 个 GDPR BPMN + 12 个能源 BPMN
- G3: 推断 Sun 2024 用了哪 4 个 → 验证
- G2: 自造 12 个能源 BPMN → 算 Stage 2/3 P/R
- 对比 Sun 2024 §5.3.2/5.3.3 报的数字
- **预期**: 4 个 GDPR BPMN 跟 Sun 2024 的 P/R 在 ±10% 偏差内
- **预期**: 12 个能源 BPMN 跟 Sun 2024 的 P/R 在 ±15% 偏差内

### Week 4: LLM 兜底 + 预注册
- G4: 设计 M2 LLM 兜底 prompt + 预注册失败条件
- 在 150 句 EStG 上跑 M1 → M2 → 算 P/R 增量
- 在 4 个 GDPR BPMN + 12 个能源 BPMN 上跑 M2 → 算 P/R 增量
- **预期**: M2 vs M1 P/R 增量 +5% to +15%（如果 prompt 设计好）

### Week 5: 论文写作
- 跟 Barrientos 2026 横向对比（LLM prompt 模板可借鉴）
- 跟 Sun 2024 报的数字对比
- 写 paper-faithful reconstruction 章节
- 写 LLM 改善 + 预注册失败条件 创新点章节
- 写 limitations（"Sun 2024 私有数据集 → 我们的 150 句自标存在 bias"）

---

## 4. 关键风险 + 缓解

| 风险 | 缓解 |
|---|---|
| 150 句自标质量差 | 10% 双标 + Cohen's kappa；只跟 Sun 2024 比较 P/R 趋势，不比绝对值 |
| 12 个能源 BPMN 自造偏差大 | 优先复现 Sun 2024 §5.3.3 reported use case names；从 Oesterreichs archive 找原 PDF |
| LLM 兜底成本高 | 先用 50 句测试 → 调 prompt → 再跑全 150 句；用本地 Llama 3 8B（如果导师批） |
| 双标 source 难找 | 改为：自己 2 轮标（中间间隔 1 周），算 intra-rater agreement |
| 跟 Sun 2024 报的数字差距大 | 论文里写 paper-faithful reconstruction 的局限性，cite Sun 2024 data not available |
| LLM API 没批 | 用 HuggingFace pipeline + 本地模型 |

---

## 5. 立即可执行的下 3 步（**不等用户回复**）

我已经标了，现在就做这 3 件事：

1. **(今天)** 装 Java 11 + Python venv，验证能跑 Stanford CoreNLP 的 Tregex
2. **(今天 + 明天)** 抽 Michel 2022 PDF text，提取标注 schema 详细说明 → 帮自标用
3. **(明天)** 数 7 个 GDPR BPMN 的 task 节点数，**推断 Sun 2024 用的 4 个身份**

---

## 6. 跟用户同步的"待确认"决策点（**等你回**）

| 决策点 | 我的建议 |
|---|---|
| 150 句自标的双标 source | 找同学/导师（**不**在 AI 帮做），最低 fallback = 1 人 2 轮 |
| LLM API 是否批 | 先用本地 Llama 3 8B（无 API 成本），效果差再申 OpenAI |
| 是否做 12 个能源 BPMN | **必做**——论文里 "在 3 个场景上验证" 不够，需要能源场景 |
| 是否做 phone company BPMN 重建 | **必做**——Sun 2024 §5.4 case study 完全用它 |
| 跟 Barrientos 2026 的关系 | **横向对比**（不是 baseline）——他们的 prompt 模板可借鉴 |

---

## 7. Cross-references

| 文档 | 角色 |
|---|---|
| `SUN2024_BASELINE_RESEARCH_NOTE.md` | 12 节完整调研笔记（27.7KB） |
| `SUN2024_REGMINER_SUPPLEMENT.md` | RegMiner 公开 prototype 发现（8.1KB） |
| `SUN2024_AGOSTINELLI_FINDING.md` | Agostinelli 2019 全文 PDF 公开发现（10KB） |
| `SUN2024_FINAL_GAP_AND_ROADMAP.md` (本文档) | **最终 gap 清单 + 5 周执行路线** |
| `formal_experiment/references_papers_local/agostinelli_2019_gdpr_bpmn.pdf` | Agostinelli 2019 全文 PDF（2.06 MB） |
| `references/datasets/estg_1988.pdf` | EStG 1988 完整 PDF（6.3 MB） |
| `references/合规性检查模型代码/model_check/input/models/gdpr/gdpr_*.bpmn` | 7 个 GDPR BPMN（4 份副本之一） |
| `references/合规性检查模型代码/model_check/input/regulations/gdpr/article*.txt` | 46 篇 GDPR 文章（4 份副本之一） |
| `references/合规性检查模型代码/model_check/input/files/{gdpr.config,sequencemarkers.txt,signalwords.txt,stopwords.txt}` | Sun 2024 用的 4 个配置文件 |
| `references/papers/Barrientos_2026_*.pdf` | Barrientos 2026 论文 PDF（含 prompt 模板可借鉴） |
| `references/papers/Michel_2022_Decision_rules.pdf` | Michel 2022 PDF（标注 schema 来源） |
