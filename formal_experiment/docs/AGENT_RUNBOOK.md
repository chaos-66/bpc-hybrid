# Agent 分阶段执行手册与 Prompt 库

本文是静态派工手册：规定怎样把主 Pipeline 的任务交给 Agent、怎样验收、什么时候
必须停止。实时状态和当前派工只写在 `PROJECT_AUDIT.md`，本文不建立第二份状态页，
也不改变 `MASTER_PIPELINE.md` 的权威性。

## 1. 调度原则

1. 实验轨道一次只推进一个最小任务 ID；默认串行，不因 Agent 空闲而越过依赖。
2. 论文轨道可以与实验轨道并行，但一次只有一个 Agent 编辑论文正文。
3. 协调 Agent 才能更新 `PROJECT_AUDIT.md`、主 Pipeline、文件目录和实验日志；工作
   Agent 只改自己的明确写入范围，交接后由协调 Agent 收口。
4. 人工审核 S2.2 由用户独占。Agent 只能验证格式、解释工具或导入用户明确提供的
   决定，不能自行接受、编辑、拒绝、标记 reviewed 或 adjudicated。
5. 任何数据缺失、许可不明、hash 不符、依赖未解锁，都应形成精确 blocker；不得
   为“完成任务”伪造数据、状态或论文结果。
6. `integrity_pass=true` 只表示可继续开发；只有相应任务的 Definition of Done 和
   上游门禁全部通过，协调 Agent 才能派发下一任务。

## 2. 当前双轨安排

```text
实验轨道（串行）
S2.1-A 来源/许可/原始文件证据
  → S2.1-B 数据合同、schema 与离线 importer
  → S2.1-C 真实 CSV 核查、canonicalization 与 split
  → S2.1-D 自动门禁与状态收口
  → S2.3 → S2.4 → S2.5 → S2.6（完整 B0）
  → S2.7/S2.8/S2.9 → S2.10
  → G0.5/S2.11 → S2.12 → S2.13
  → Stage 1 → Stage 3 → 端到端消融

论文轨道（与实验并行）
PW0 骨架/主张账本
  → PW1 引言与研究问题
  → PW2 相关工作
  → PW3 方法设计稿
  → PW4 数据与标注协议
  → PW5 实验设计
  → PW6 空结果表
  → PW7/PW8 正式结果回填
  → PW9 讨论、结论、摘要与终稿
```

当前事实：`Decision_Logic_data.zip` 已在本地通过来源身份核验；S2.1-A、
S2.1-B-R1、S2.1-C-R1 和 S2.1-D 均已 verified，2,831 行 development analysis
population 及其 project-reconstructed split 已由独立机器门禁锁定。许可仍为
`unknown_pending_confirmation`，因此不得再分发、提升为 formal Gold 或直接进入训练/
评价。S2.3 已 verified 并严格停在 public marker resource；S2.4 只有在另行派发且
单独收口许可未知与 ready 的现有矛盾后才能启动。论文 PW1 可以在不写任何结果性
主张的前提下开始。

## 3. 所有工作 Agent 共用的 Prompt 前缀

复制下面的前缀，再追加第 5—8 节对应任务卡。当前任务的完整可复制 Prompt 已在
第 4 节给出。

```text
你是 BPC-Hybrid 项目的工作 Agent。本轮只执行指定的一个 Pipeline 任务 ID，
不得顺手推进下游任务。

工作区：D:\Paper\experiment\bpc-hybrid
所有活动写入只能位于 formal_experiment/。

先完整阅读并服从：
1. formal_experiment/AGENTS.md
2. formal_experiment/docs/MASTER_PIPELINE.md
3. formal_experiment/docs/PROJECT_AUDIT.md
4. formal_experiment/docs/DIRECTORY_GUIDE.md
5. formal_experiment/docs/EXPERIMENT_LOG.md 最新事件
6. formal_experiment/docs/AI_CHANGE_PROTOCOL.md
7. formal_experiment/docs/ROUTE_LOCK.md
8. formal_experiment/configs/experiment_contract.json
9. formal_experiment/configs/methods.json
10. formal_experiment/docs/AGENT_RUNBOOK.md

修改前运行快速完整性检查。开发过程中只跑相关测试；完成一个连贯修改批次后才跑
一次全量检查，并按 AI_CHANGE_PROTOCOL 追加事件。不得读取或打印 .env；不得调用真实 LLM/API；
不得自动修改 Gold，不得覆盖正式产物，不得修改 references/、根
archive/ 或 _retired/。

开始前先复述：任务 ID、唯一目标、已满足依赖、输入、写入范围、禁止项和 DoD。
若依赖不满足，停止并给出证据，不得自行解锁。交付时列出：改动文件、相关测试、
全量验证、产物状态（development/pilot/formal）、仍存 blocker、建议的下一任务 ID。
```

## 4. 当前可直接派发的完整 Prompt

### 4.1 Agent-E1：S2.1-A 官方 modality 数据来源证据

```text
你是 Agent-E1，只执行 Pipeline S2.1-A：固定 Sun 官方 modality 数据的来源、许可
状态和原始文件身份。不要解析标签、生成 split、训练模型或进入 S2.1-B。

工作区：D:\Paper\experiment\bpc-hybrid
所有活动写入只能位于 formal_experiment/。

完整阅读 formal_experiment/AGENTS.md 及其 Required Reading，另外阅读：
- docs/research/SUN_FINAL_VERSION_AND_DATA_AUDIT.md
- docs/research/SUN_REFERENCE_SNOWBALL_AND_MARKER_AUDIT.md
- configs/paths.json

修改前运行 `python formal_experiment/scripts/audit_project.py`。

已知证据：
- 官方入口：https://archive.org/details/input-2
- 包名：Decision_Logic_data.zip
- 已记录官方 SHA-1：0346f84a246b7049d5aef58bcb33471435bee106
- 预期成员：EStG_raw.txt、EStG_sent_vec.csv、estg.html
- 当前工作区没有 ZIP 或 CSV 实体。

本轮目标：
1. 核对本地是否已有官方包；没有就明确记录 missing，不得伪造。
2. 只从权威官方页面核对下载身份、文件元数据和许可/再分发状态。许可无法确认时写
   `unknown_pending_confirmation`，不得推断“可正式使用”。
3. 只有在工具权限和当前任务授权允许安全取得官方包时，才把原始开发副本放入
   `data/development/sun_modality/raw/`；绝不写 references/ 或 formal 数据目录。
4. 对实际取得的包和成员计算 SHA-1/SHA-256；已知 SHA-1 不匹配立即停止。
5. 新建 `data/development/sun_modality/source_manifest.json` 和
   `docs/research/SUN_MODALITY_DATASET_INGESTION.md`，记录 URL、获取时间、文件名、
   大小、hash、许可原文/未知状态、当前缺口和下一步。
6. 增加只验证来源 manifest 与原始字节一致性的最小测试。

禁止：不接触 EStG-150 Layer A–E；不把论文的 2,833 条统计当作本地数据；不预设
CSV 列或标签含义；不训练；不调用 LLM；不修改任何 readiness/locked 状态；不宣布
S2.1 完成。

DoD：来源可定位；实际取得文件的 hash 可复核；许可状态诚实；原始数据只在
development；相关测试通过；只能把 S2.1-A 标为 verified。若没有取得官方包，交付
精确 blocker，并保持 S2.1-A 未完成。

完成连贯批次后按 AGENTS.md 运行一次全量检查、更新文件目录并记录中文变更事件。
```

### 4.2 Agent-P1：PW1 引言与研究问题

```text
你是 Agent-P1，只执行论文任务 PW1：完善中文引言和 RQ0–RQ4。只允许编辑
formal_experiment/paper/THESIS_DRAFT.md 与 CLAIM_EVIDENCE_MATRIX.md，不修改实验
代码、数据、Gold、配置、主 Pipeline 或实时状态页。

工作区：D:\Paper\experiment\bpc-hybrid
先完整阅读 formal_experiment/AGENTS.md、docs/AGENT_RUNBOOK.md、paper/README.md、
paper/THESIS_DRAFT.md、paper/CLAIM_EVIDENCE_MATRIX.md、MASTER_PIPELINE §§2–4、
PROJECT_AUDIT 和 docs/research/。内部研究审计只能作为证据导航；正式文献主张必须
回到本地可核验的原论文。无法核验页码或表号时写 TODO-SOURCE，禁止猜测。

引言必须覆盖：design-time BPC 问题；Stage 1/2/3 关系；Sun 方法的作用和不可得
资产；比较传统方法、paper-faithful Sun 重建、Direct LLM 和 selective Hybrid 的
动机；复杂法律语料是待检验问题而不是既定优势；RQ0–RQ4。

统一占位符：
- [[TODO-RESULT:任务ID：需要回填的结果]]
- [[TODO-SOURCE:文献键：需要核对的原始页码/表号]]
- [[TODO-STATUS:任务ID：完成后把设计时态改为实现时态]]
- [[TODO-DECISION:任务ID：需要冻结的研究决定]]

禁止：不得声称已经 exact reproduction；不得把当前 heuristic 称正式 Sun baseline；
不得声称正式 Gold、正式实验或 LLM 优势已经完成；不得把 EStG-150 写成 Sun 原始
150；不得把 LLM-assisted Gold 写成纯人工 Gold；不得跨数据或跨 Stage 比数字。

DoD：引言形成可读初稿；每个结果性句子都是待检验时态或显式 TODO；新增主张同步
登记到 CLAIM_EVIDENCE_MATRIX；不填任何实验数字。完成后交给只读主张审查 Agent，
由协调 Agent 统一验证和记录。
```

### 4.3 Agent-R1：只读论文主张审查

```text
你是 Agent-R1，只读审查，不编辑文件、不跑全量测试。阅读 AGENTS.md、机器合同、
PROJECT_AUDIT、paper/CLAIM_EVIDENCE_MATRIX.md 和待审章节。逐句检查 planned method
是否被写成 completed、development 是否被写成 formal、是否声称 exact/original
Sun、是否把 LLM-assisted Gold 写成纯人工、是否把 C2/C3/C4 写成 C1、是否提前
声称 LLM 优势、是否混淆 Stage 2/3。按严重度输出“原句—证据问题—安全替换句—
所需 TODO/解锁任务”。不得自行补数字、页码或来源。
```

## 5. S2.1 后续任务卡

以下任务默认串行。即使 S2.1-A 与 S2.1-B 技术上可在不重叠文件时并行，本项目为
降低冲突默认先完成 A，再派发 B。

### S2.1-B：合同、schema 与离线 importer

- 依赖：S2.1-A 的来源事实已固定；真实 CSV 可以仍缺失。
- 写入：`configs/datasets/`、`configs/schemas/dataset_manifest.schema.json`、
  `src/bpc_hybrid/datasets/`、`scripts/ingest_sun_modality.py`、合成 fixtures/tests。
- 目标：标准库 `csv/hashlib` 实现 ZIP/CSV inspect/import、默认拒绝覆盖、显式
  source ID 唯一性、稳定 ID、normalized-text group-aware split、标签冲突 fail closed、
  唯一小类别阈值、独立 SHA-1/SHA-256 核验、确定性 manifest 与 membership hash。
- adapter 边界：`strict_one_hot` 只属于 synthetic fixtures；官方 CSV schema、label
  mode 与整数 0–3 映射全部保持 `pending_s2_1_c`，不得猜测。实现只预留可注入
  label adapter seam，不在 B/R1 中增加官方 integer-code mapping。
- manifest 边界：不含运行时当前时间；`output_files` 只列实际派生数据 child，
  不自列 manifest，不允许 placeholder；manifest 自身 hash 由外部 receipt/日志记录。
- 小类别唯一公式：`active_nonzero_splits * min_per_class_in_smallest_split`，单位为
  normalized-text group；当前阈值 3，低于阈值全进 train 并 warning，不丢类别/样本。
- 边界：所有未知真实列写 pending；fixture 不能冒充官方数据；不改 Gold/readiness；不训练。
- DoD：`--inspect-only` 不写数据；train/dev/test 无交集且并集完整；相同 normalized
  text 不跨 split；同输入/合同/seed 的 records、三个 split 和 manifest 均字节一致。

### S2.1-C：真实官方 CSV 核查与 development 生成

- 依赖：A/B verified；官方 ZIP 已由用户提供或在 A 中合法取得。
- 输入：实际 `Decision_Logic_data.zip`，先核验已知 SHA-1。
- 输出：`data/development/modality/sun_estg_modality_v1/records.jsonl`、manifest、
  versioned splits；全部默认 no-overwrite。
- 必查：真实列、编码、行数、类别支持、向量列用途、许可和 split；任何不一致保留
  blocker，不写 formal 目录。
- DoD：真实 manifest、hash、schema、label count 和 split disjointness 全可复核。

### S2.1-D：机器门禁与状态收口

- 依赖：C verified。
- 写入：contract 的 modality 子状态、`audit.py`、相关测试、唯一实时状态页。
- 边界：顶层 Stage 2 数据路线仍保持 reopened；S2.2 仍由人工决定；不得解锁 B0、
  formal Gold、Stage 3 或 final-ready。
- DoD：机器检查验证 manifest/hash/row/label/split/license；S2.1 标 verified；全测和
  中文日志事件完成。
- 当前状态：**verified**。可移植 manifest、独立 gate、负测试、合同与实时状态已收口；
  `sun_modality_development_data_verified=true`，但 human freeze、formal Gold、Stage 3
  和 final experiment 门禁仍关闭。后续不得把本节作为进入 S2.3/S2.4 的隐式授权。

## 6. Stage 2 方法任务卡

每次只派发一个任务卡，工作 Agent 必须把第 3 节通用前缀一起复制进 Prompt。

| ID | 唯一目标 | 必须完成的产物 | 进入下一步的门禁 |
|---|---|---|---|
| S2.2-V | 只验证用户 Layer E 进度 | validator 报告；不得改记录 | 用户自行达到 150/150 |
| S2.3 | public marker 重建 | 来源表、生成规则、hash、版本化词表、fixtures | 来源/语言/扩展策略固定 |
| S2.4 | BERT-TextCNN | 可重建训练、dev 选择、test evaluator、manifest | S2.1 verified；无 test 调参 |
| S2.5 | CoreNLP/Tregex/Tsurgeon | 版本固定、规则、顺序约束、六字段 fixtures | S2.3 verified |
| S2.6 | 完整 B0 | 分类+抽取组合、canonical Rule Record、no-LLM 证明 | S2.4/S2.5 verified |
| S2.7 | 代表性非 LLM baseline | 简单规则 + 强监督代表，统一 evaluator | S2.1/S2.2 满足依赖 |
| S2.8 | H1 预注册 | trigger、merge、失败策略、硬预算；不看 test | S2.6 verified |
| S2.9 | D1 锁定 | prompt/few-shot/model/temperature/budget hash | S2.2 frozen；API另授权 |
| S2.10 | 主数据评价 | modality、六字段、完整记录分开报告 | B0/H1/D1 同 IDs/Gold/eval |
| G0.5 | 复杂度合同 | 结果前冻结文本/BPMN复杂度字段和 bins | 不得看复杂集 test 结果 |
| S2.11 | 复杂语料冻结 | 来源/许可/hash/标签映射/人工协议 | G0.5 verified |
| S2.12 | 复杂度与错误分析 | 退化曲线、预注册错误类型、覆盖/失败数 | S2.10/S2.11 verified |
| S2.13 | Stage 2 冻结 | 数据/Gold/方法/指标/成本/manifests | S2.1–S2.12 全部通过 |

补充边界：S2.8/S2.9 只是预注册不等于授权真实 LLM；真实运行必须另有用户明确
授权、模型和硬调用预算。S2.10/S2.12 的论文数字只能来自 `experiment_run` 事件和
formal manifest。不同数据、split、Gold 或 evaluator 的论文值只属于 C2/C3/C4，
不能写成 C1 严格优劣。

S2.3 当前状态（2026-07-16）：`public_marker_lexicon_en_v1` 已 verified，英文显式
public seed 共 64 个，development 扩展 count=0；source/manifest/combined payload
hash 已由机器门禁锁定。Wiktionary actor dump 未在本轮伪造或补取，旧 heuristic
词表未被当成 S2.3 产物。后续任务不得静默覆盖 v1 或用 test/Gold/结果补词。

## 7. Stage 1、Stage 3 与端到端 Prompt 卡

### Stage 1：S1.1—S1.7

```text
只执行协调 Agent 指定的一个 S1.x。Stage 1 只有在 Stage 2 core 达到主 Pipeline
门禁后开始。按 S1.1 schema → S1.2 结构解析 → S1.3 标签语义/S1.4 控制流 →
S1.5 人工 Gold → S1.6 baseline 评价 → S1.7 冻结串行推进。不得用历史资产冒充
冻结组件，不得在 S1.5 中自动产生人工 Gold。每个方法共享 Process Record schema、
fixtures、normalization 和 evaluator。
```

### Stage 3：S3.1—S3.11

```text
只执行协调 Agent 指定的一个 S3.x；必须先有 S1.7、S2.13，并显式更新机器合同后
才能启动扩展。先锁原4/扩展7 BPMN身份与 hash，再锁 matching/violation Gold，
随后分别实现 Winter、Sun 和代表性非 LLM baseline。Oracle Stage 3 先于 LLM/Hybrid，
Oracle 与 end-to-end 必须分表；matching 与 violation classification 也必须分开。
不得把 fixture scaffold 称完整复现，不得把 all-seven extension 写成 Sun 原4。
```

### 端到端归因：E00/E10/E01/E11

```text
只在 Stage 2 和 Stage 3 均冻结后执行。固定输入、Gold、Process/Rule Record schema、
normalization 和 evaluator，运行 E00、E10、E01、E11，分别回答 Stage 2、Stage 3
和交互贡献。不得只报告最佳组合；失败、invalid、成本和覆盖率必须进入 manifest。
```

## 8. 论文任务卡

| ID | 现在可做什么 | 解锁/验收条件 |
|---|---|---|
| PW0 | 目录、骨架、主张账本、TODO 和空表 | 本轮建立；不得含结果数字 |
| PW1 | 引言、背景、RQ0–RQ4 | 使用待检验时态 |
| PW2 | Sun/Winter/Sleimi/Michel/Barrientos 相关工作 | 原论文核验；无证据写 TODO-SOURCE |
| PW3 | 三阶段总体架构与 B0/H1/D1 设计稿 | 未完成组件写 TODO-STATUS |
| PW4 | 数据来源、五层 Gold 和人工协议 | S2.1/S2.2 后定向回填统计 |
| PW5 | baseline、指标、统计与复现设计 | 对应合同锁定后回填参数 |
| PW6 | 结果表/图空模板 | 只能是 TEMPLATE，不填数字 |
| PW7 | Stage 2 正式结果 | S2.10/S2.12/S2.13 + manifest |
| PW8 | Stage 1/3/端到端结果 | S1.7、S3.7–S3.10、P8 |
| PW9 | 讨论、局限、结论、摘要和终稿 | 主张账本全有正式证据 |

论文回填规则：每次正式实验只做一次定向回填；核对 `experiment_run` 与 manifest；
表格状态从 TEMPLATE 改为 FORMAL_VERIFIED；同时回填样本数、support、失败数、区间、
模型/evaluator 版本；再由 Agent-R1 只读复核。开发结果只能标 DEV_ONLY。

## 9. 工作 Agent 交接模板

```text
任务 ID：
结论：verified / partial / blocked（只用 Pipeline 允许状态）
实际改动：
输入及 hash：
输出及状态（development/pilot/formal）：
相关测试：
批次全量检查：
Gold：未改 / 用户明确授权导入
LLM/API：未调用 / 用户授权详情
仍存 blocker：
未触碰的并发文件：
建议下一任务 ID：
```
