# Sun 引用链、二阶文献与 marker 资源审计

**审计日期**：2026-07-12  
**对象**：Sun et al. 最终版 44 条参考文献、较早作者稿中被最终版删除的
方法引用，以及与 Stage 2 六要素抽取直接相关的二阶文献、代码和数据。  
**结论级别**：文献定位与资源可用性审计；不是对缺失 Sun 原始资产的替代声明。

## 1. 结论先行

1. Sun 的六要素短语抽取不是一个没有来源的独立规则体系。较早作者稿明确引用
   Sleimi et al. 的法律语义元数据抽取工作；两者在 actor 的 Tregex 结构、marker
   示例、基于 constituency/dependency parse 的提取流程上高度一致。最终发表版的
   44 条参考文献删除了 Sleimi 等若干方法来源，因此只看最终参考文献表会漏掉最
   重要的 marker 谱系。
2. Sun 原始完整 marker lexicon 仍未公开，但“不人工从零造词典”是可行的：
   condition 和 constraint 有公开机器可读词表；actor 可按 Sleimi 的 Wiktionary
   定义规则自动生成；modality 有论文示例和公开 deontic 数据；exception 可用
   Sleimi/Wyner 等公开种子扩展。必须把它称为
   **public-source reconstructed lexicon**，不能称为 Sun original lexicon。
3. 词典缺失与 Gold 缺失是两个不同障碍。重建 marker 可以运行 baseline，却不能
   产生可信的 150 句、443 span 正式 Gold。没有原 Gold 或独立人工 Gold，就不能
   报告与 Sun phrase-level 数值直接可比的 P/R/F1。
4. 官方 EStG 句子是德文，而旧 Sun 稿给出的模型和 marker 示例均为英文，且没有
   发现翻译流程说明。这是复现中的真实语言缺口。若坚持方法相同而允许数据不同，
   最干净的主路线是用英文法律/合规文本；若坚持 EStG，则必须公开记录德文模型、
   parser、marker 生成和可能的翻译适配，不能称 exact implementation。

## 2. 审读协议和边界

本轮采用三层审读，而不是把“搜索到标题”等同于“读过论文”：

- **L1 全覆盖**：核对最终版全部 44 条题名、作者、年份及其在 Sun 方法中的作用。
- **L2 方法细读**：细读直接决定 Stage 2、数据、marker、Stage 3 或评价设计的文献。
- **L3 资产核验**：打开论文配套代码、数据、prompt/schema 或公开词表，检查实际
  文件内容，而不只采信论文中的 availability 声明。

本轮对 44/44 条完成 L1。对方法核心链（18--24、29--44 中与实现/数据直接相关
者）完成 L2；对 Sleimi、LexNLP、Wiktionary/Wiktextract、MGTC、ATDP、PET、
LEXDEMOD、Winter、Barrientos 配套资产完成 L3。概念性综述、Petri net/UML/EPC
教科性引用只做 L1/L2 定位，因为继续向它们的全部引用无限递归不会新增 Stage 2
可用 marker、Gold 或实现资产。

停止规则是：连续两轮 backward/forward snowball 不再产生新的、可合法获取且能
直接用于六要素抽取的词表、span Gold、代码或 prompt/schema。后续若获得 Sun 最终
PDF、作者回复或新的资产链接，应重新打开本审计。

## 3. Sun 最终版 44 条直接引用逐项作用表

| # | 文献（缩写题名） | 在 Sun 中的作用 | 对本实验的可用产物 | 深度 |
|---:|---|---|---|---|
| 1 | van der Aalst 2003, *BPM Demystified* | BPM 背景 | 术语边界，无 Stage 2 资产 | L1 |
| 2 | Kharbili et al. 2008, *BPC Checking: Current State...* | 合规研究背景 | 问题分类，无 marker | L1 |
| 3 | Hashmi et al. 2018, *Are We Done with BPC?* | 综述/研究缺口 | taxonomy，可支撑相关工作 | L2 |
| 4 | Abdullah et al. 2010, *Emerging Challenges...* | 合规管理挑战 | 研究动机 | L1 |
| 5 | Ly et al. 2015, *Compliance Monitoring...* | 运行时监控综述 | 功能 taxonomy，不是 Stage 2 | L2 |
| 6 | Rinderle-Ma & Kabicher-Fuchs 2016, indexing | 大规则库检索 | Stage 3 检索思路 | L1 |
| 7 | Governatori & Sadiq 2009, *Journey to BPC* | 合规生命周期 | 概念框架 | L1 |
| 8 | Brunello et al. 2019, NL-to-LTL survey | NL 形式化 | 纯 LLM 路线的形式化背景 | L2 |
| 9 | Awad et al. 2008, BPMN-Q + temporal logic | 形式合规检查 | Stage 3 对照，不提供六要素 | L2 |
| 10 | Elgammal et al. 2016, compliance patterns | 合规模式 | constraint 规范化词汇来源 | L2 |
| 11 | Meth et al. 2013, requirements elicitation review | NLP 需求抽取综述 | 方法背景 | L1 |
| 12 | Governatori & Rotolo 2010, norm compliance | 规范/道义逻辑 | modality 与规范语义 | L2 |
| 13 | Montali et al. 2014, Event Calculus | 约束监控 | 下游形式语义 | L2 |
| 14 | González & Delgado 2021 | 政务协同合规 | 外部应用场景 | L1 |
| 15 | González et al. 2022 | generic controls + mining | 合规控制 | 外部 Stage 3 对照 | L1 |
| 16 | Governatori et al. 2016, LegalRuleML | 法规形式化 | 结构 schema 参考 | L2 |
| 17 | Cabanillas et al. 2020, mashup framework | 合规框架 | 工程背景 | L1 |
| 18 | Sinha & Paradkar 2010, use cases to BPMN | 文本到流程 | actor/action/control-flow 规则线索 | L2 |
| 19 | Sánchez-Ferreres et al. 2019, formal reasoning on process text | 依存树到形式约束 | ATDP/Reasoner 方法链 | L2/L3 |
| 20 | Delicado Alcántara et al. 2017, NLP4BPM | NLP 工具 | ATDP 公开工具入口 | L2/L3 |
| 21 | Sánchez-Ferreres et al. 2021, *Unleashing Textual Descriptions...* | 文本流程抽取 | extractor/reasoner、模式库 | L2/L3 |
| 22 | Feng et al. 2018, action sequence extraction | 动作序列 | action/order 辅助方法 | L2 |
| 23 | Qian et al. 2020, MGTC | 多粒度文本分类 | 公开 COR/MAM 数据和代码；actor/action 辅助 | L2/L3 |
| 24 | Winter et al. 2020, compliance assessment | Sun 直接 baseline | 公开 GDPR prototype/Stage 3 输入；不是 Sun Stage 2 | L2/L3 |
| 25 | Peterson 1977, Petri nets | 流程形式基础 | 无 Stage 2 资产 | L1 |
| 26 | Filho & Braga 2017, UML | 建模背景 | 无 Stage 2 资产 | L1 |
| 27 | Amjad et al. 2018, EPC SLR | 建模语言背景 | 无 Stage 2 资产 | L1 |
| 28 | Compagnucci et al. 2021, BPMN repositories | BPMN 数据来源背景 | 可扩展 BPMN，但无法律 span | L1 |
| 29 | Leopold 2013, *Natural Language in BPM* | 语言与流程模型 | actor/action 文本规范化依据 | L2 |
| 30 | McNamara 2006, Deontic Logic | modality 理论 | obligation/permission/prohibition 语义 | L2 |
| 31 | Devlin et al. 2018, BERT | 句子级表示 | 最终 baseline 模型基础 | L2 |
| 32 | Chen 2015, CNN sentence classification | TextCNN | 最终 BERT-TextCNN 分类头依据 | L2 |
| 33 | Wiktionary | actor marker 来源 | 可自动重建 actor lexicon | L3 |
| 34 | Honnibal & Montani 2017, spaCy 2 | NLP 工具 | Winter/辅助 parser；非 Sun CoreNLP | L2/L3 |
| 35 | Levy & Andrew 2006, Tregex/Tsurgeon | 树查询/变换 | Sun 短语规则的直接实现技术 | L2/L3 |
| 36 | Manning et al. 2014, Stanford CoreNLP | constituency/dependency parse | Sun Stage 2 parser | L2/L3 |
| 37 | Michel et al. 2022, EStG decision rules | 句子级四分类数据 | 2,833 德文句子；Sun 官方包含 CSV | L2/L3 |
| 38 | Goldberg & Levy 2014, word2vec | embedding baseline | 句子分类比较项 | L2 |
| 39 | Zhou et al. 2016, attention BiLSTM | 分类 baseline | 比较项，不决定六要素 | L2 |
| 40 | Lai et al. 2015, RCNN | 分类 baseline | 比较项 | L2 |
| 41 | Johnson & Zhang 2017, DPCNN | 分类 baseline | 比较项 | L2 |
| 42 | Böhmer & Rinderle-Ma 2016, anomaly detection | 智能电表案例 | 12 对 matching 数据仍不可公开恢复 | L2 |
| 43 | Agostinelli et al. 2019, GDPR BPMN patterns | GDPR 测试模型 | 7 个 BPMN patterns；官方包可核验 | L2/L3 |
| 44 | Schröder et al. 2011, recommender metrics | AP/MAP | Stage 3 matching 评价定义 | L2 |

官方参考文献表：<https://link.springer.com/article/10.1007/s11227-023-05626-0>。

## 4. 最终版漏掉但方法上不可漏掉的引用链

### 4.1 Sleimi 是 phrase-level 方法的关键祖先

Sleimi et al., *An Automated Framework for the Extraction of Semantic Legal
Metadata*（RE 2018，后续扩展稿 arXiv:2001.11245）定义了 statement-level 与
phrase-level 法律概念，使用 CoreNLP 风格的 constituency/dependency 分析、
Tregex 规则和 marker：

- actor 的结构规则与 Sun 给出的主语/宾语树模式相同；
- action 在移除 modality、condition、exception、reason 等成分后得到；
- actor marker 不是逐条人工标注，而是从 Wiktionary 中筛选定义含
  `person`、`organization` 或 `body` 的名词；
- condition/exception/modality 等 marker 来自 200 条卢森堡交通法规的人工观察，
  再由领域专家给出表达变体；论文 Table 5 只列 non-exhaustive examples。

Sleimi 的 2018 实验在 150 条陈述上包含 1,177 个短语、1,202 个标注，报告
κ=0.815；扩展稿在六个法律领域的 350 条测试陈述上检验跨域表现。这个数据规模、
规则形式和 Sun 的 150 句 phrase 实验非常接近，因此它是重建 Sun marker 的首要
来源，而不是一般性的“相似工作”。

论文：<https://arxiv.org/pdf/2001.11245>。

### 4.2 二阶 marker 文献

- Wyner & Peters 2011, *On Rule Extraction from Regulations*：提供 exception、
  condition、deontic 规则的 gazetteer/JAPE 思路；材料声明可向作者索取。
- LexNLP：公开可执行的 English condition/constraint trigger 模块，适合作为
  冻结词典种子，而不是冒充 Sun 原词典。
- ATDP/NLP4BPM：公开 dependency-tree query patterns，可补充 actor/action 和
  control-flow 关系提取。
- MGTC：公开 action sentence、statement semantics 及 aRole/aName/aObject 的
  多粒度标注，可用于 actor/action 子任务预训练或辅助评估。
- PET：公开 actor、activity、activity data、condition/gateway span 与关系标注，
  可用于非法律领域的结构泛化测试。
- LEXDEMOD：公开英文合同中的 agent-specific deontic modality 和 trigger spans，
  可独立检验 modality/actor 组合，不可替代 Sun 六要素 Gold。

## 5. 可立即使用的 marker 资源

### 5.1 论文直接给出的种子

- modality：`may`, `must`, `shall`, `can`, `need to`, `is authorized`,
  `is prohibited`；
- condition：`if`, `in case of`, `provided that`, `in the context of`,
  relative-clause markers `who/whose/which`；
- exception：`with the exception of`, `except for`, `in derogation of`,
  `apart from`, `other than`；
- actor 示例：`physician`, `expert`, `company`, `judge`, `prosecutor`,
  `driver`, `officer`, `inspector`。

这些只是论文示例，单独使用会造成低召回，不应叫 complete lexicon。

### 5.2 LexNLP 的公开 condition 表

可冻结的触发短语包括：`if`, `if not`, `when`, `when not`, `where`,
`where not`, `unless and until`, `unless`, `unless not`, `until`, `until not`,
`as soon as`, `as soon as not`, `provided that`, `provided that not`,
`subject to`, `not subject to`, `upon the occurrence`, `conditioned on`,
`conditioned upon`。

来源：<https://lexpredict-lexnlp.readthedocs.io/en/latest/modules/extract/en/conditions.html>。

### 5.3 LexNLP 的公开 constraint 表

公开表覆盖 `after/before/within/prior to`、`at least/at most/exactly`、
`greater/less/equal`、`minimum/maximum`、`no earlier/no later/no less/no more`、
`not equal/not to exceed/exceeds` 等 40 个比较和时序触发模式。

来源：<https://lexpredict-lexnlp.readthedocs.io/en/latest/modules/extract/en/constraints.html>。

### 5.4 actor 词典自动生成，不做逐条人工 marker 标注

按 Sleimi 描述实现一条可复现生成管线：

1. 固定某日 English Wiktionary dump，记录 URL、日期、SHA-256 和许可证；
2. 用 Wiktextract 解析为 JSONL，只保留 English noun senses；
3. 在 gloss 中用词边界匹配 `person|organization|organisation|body`；
4. 规范化 lemma、大小写、连字符和复数，保留 sense/gloss 作为 provenance；
5. 只在 dependency subject/object 或 Sun Tregex 候选节点上查词典，避免把普通
   名词仅因词典命中就判为 actor；
6. 在 development split 上确定过滤规则后冻结版本和哈希，test split 不再增词。

实现工具：<https://github.com/tatuylonen/wiktextract>。可做消融的替代层级包括
Wiktionary-gloss、WordNet `person/organization` hyponyms，以及 parser-only actor。

### 5.5 exception 仍是最薄弱的 marker

当前可公开复核的起点是 Sleimi Table 5 和 Wyner 的 exception gazetteer 思路。
完整 Sun/Sleimi 原始 exception 清单仍未找到。推荐的非人工扩展方式是：先从公开
法规训练集检索种子左右窗口，按依存结构聚类候选连接词，只在 development 数据上
由一次小规模审核接受/拒绝候选；冻结后再跑 test。这个审核是词典质量控制，不是
对每条测试句逐句人工标注。

## 6. 可用代码和数据账本

| 资源 | 地址 | 可用于什么 | 不能声称什么 |
|---|---|---|---|
| Sun 官方补充包 | <https://archive.org/details/input-2> | EStG 句子分类、57 个 Stage 3 输入 | 不含完整 Stage 2/phrase Gold/marker |
| Sleimi 扩展稿 | <https://arxiv.org/pdf/2001.11245> | 六类附近的规则和 marker 谱系 | 未公开完整 marker/Ground Truth 文件 |
| LexNLP | <https://github.com/LexPredict/lexpredict-lexnlp> | condition/constraint 公共种子 | 不是 Sun 原词典 |
| Wiktextract | <https://github.com/tatuylonen/wiktextract> | 自动生成 actor 词典 | 需固定 dump，且英语词典不适配德语 |
| MGTC | <https://github.com/qianc62/MGTC> | action/statement/SRL 辅助训练 | 不是法律六要素 Gold |
| ATDP extractor | <https://github.com/PADS-UPC/atdp-extractor> | actor/action/control-flow 树模式 | 不是 Sun 原实现 |
| PET | <https://huggingface.co/datasets/patriziobellan/PET> | actor/activity/condition span 外部测试 | 非法律语料 |
| LEXDEMOD | <https://arxiv.org/abs/2211.12752> | modality+agent+trigger span 外部测试 | 不含 Sun 全六要素 |
| Winter prototype | Winter 2020 配套代码/当前导师包 | Stage 3 与 GDPR BPMN | 不是 Sun 新 Stage 2 |
| Barrientos RC4PC | 本地 prompt/schema/expert material | LLM 结构化、controlled vocabulary、稳定性设计 | 不直接输出 Sun 六要素 |

## 7. 对 baseline 的可复现定义

若原作者仍不提供 marker，正式名称应为
`sun_stage2_public_lexicon_reconstruction`，包含：

1. 与最终论文一致的四类 BERT-TextCNN 句子分类；
2. CoreNLP constituency/dependency parse；
3. Sun/Sleimi 同源的 Tregex/Tsurgeon 结构规则；
4. 明确分层的 marker：paper examples、LexNLP public list、auto-generated actor、
   development-only exception expansion；
5. 输出 modality、actor、action、condition、constraint、exception 的原文 span；
6. 固定 parser/model/dump/lexicon/version/hash；
7. 报告与 Sun original 的不可复现差异，不使用 `exact reproduction` 字样。

## 8. 尚未解决且必须诚实报告的事项

- 原作者 150 个句子 ID、443 个 phrase annotations 和完整 marker；
- 最终 BERT-TextCNN 的 split、超参数、seed、checkpoint；
- 英文 marker/English BERT 与德文 EStG 的语言处理解释；
- 智能电表 12 对 proprietary process-model/paragraph matching 数据；
- Sun 最终版删除旧稿方法引用造成的版本间 reference drift。

在这些资产缺失时，可以完成**方法相同、资产公开可重建**的实验，但不能宣称数值
等同于作者原始复现。
