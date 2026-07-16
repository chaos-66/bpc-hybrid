# Sun 官方 Stage 2 Modality 数据集 S2.1-A 摄入与来源记录

**任务 ID**：S2.1-A（官方数据来源、许可与原始文件证据）
**文档状态**：**verified**（raw 字节已核验通过，许可仍 `unknown_pending_confirmation`）
**最后更新**：2026-07-16
**关联机器 manifest**：`data/development/sun_modality/source_manifest.json@1.0.0`
**字节级核验脚本**：`scripts/verify_sun_modality_zip.py`
**对应 Pipeline 任务**：`docs/MASTER_PIPELINE.md` §8.5 S2.1 + `docs/AGENT_RUNBOOK.md` §4.1
**对应审计底稿**：`docs/research/SUN_FINAL_VERSION_AND_DATA_AUDIT.md`、`docs/research/SUN_REFERENCE_SNOWBALL_AND_MARKER_AUDIT.md`

> 本文档与 `source_manifest.json` 必须保持一致；任何变更都要先改 manifest，再改本文，并在 `docs/EXPERIMENT_LOG.md` 追加一条 `change` 事件。

---

## 1. 唯一目标与边界（DoD 复述）

S2.1-A 的任务卡（`docs/AGENT_RUNBOOK.md` §4.1）原文要求：

1. 核对本地是否已有官方 `Decision_Logic_data.zip` / `EStG_sent_vec.csv` 与官方补充材料中与 Stage 2 modality 分类有关的文件；
2. 没有就明确记录 `missing`，**不得伪造数据或 schema**；
3. 只从权威官方页面核对下载身份、文件元数据和许可/再分发状态；许可无法确认时写 `unknown_pending_confirmation`，**不得推断**"可正式使用"；
4. 只有在工具权限和当前任务授权允许安全取得官方包时，才把原始开发副本放入 `data/development/sun_modality/raw/`；**绝不写** `references/` 或 formal 数据目录；
5. 对实际取得的包和成员计算 SHA-1/SHA-256；已知 SHA-1 不匹配立即停止；
6. 新建 `data/development/sun_modality/source_manifest.json`（机器可读）与本文档（人类可读），记录 URL、获取时间、文件名、大小、hash、许可原文/未知状态、当前缺口和下一步；
7. 增加只验证来源 manifest 与原始字节一致性的最小测试；
8. 不得宣布 S2.1 完成；DoD 全部满足后才把 S2.1-A 标 `verified`。

S2.1-A 在 2026-07-15 经用户授权后，原始 ZIP 已放入 `data/development/sun_modality/raw/Decision_Logic_data.zip`；本轮**剩余工作**：

9. 检查文件大小是否为 191,874,718 字节 ✓
10. 计算本地 SHA-1 并与 `0346f84a246b7049d5aef58bcb33471435bee106` 比对 ✓
11. 计算并记录本地 SHA-256 ✓
12. 安全检查 ZIP 成员（拒绝路径穿越与覆盖已有文件）✓
13. 核验三个预期成员（`EStG_raw.txt` / `EStG_sent_vec.csv` / `estg.html`）✓
14. 计算所有关键成员的 SHA-256 ✓
15. 核验 `EStG_raw.txt` 的 SHA-256 是否为 `185385186533FCDB...404817660F` ✓
16. 更新 source_manifest.json 与本文档
17. 修正 manifest 中"没有 raw 字节却称 raw 字节一致条件已满足"的旧表述
18. 为 `raw/` 增加目录级 `.gitignore`，确保 ZIP/CSV/解压文件不会进 Git
19. 运行字节一致性测试
20. 跑 `python formal_experiment/scripts/audit_project.py --with-tests`
21. 按 `AI_CHANGE_PROTOCOL.md` 追加中文实验日志

---

## 2. 官方来源与已记录的官方元数据

### 2.1 官方 Archive.org 入口

- 入口页：`https://archive.org/details/input-2`
- 元数据页：`https://archive.org/metadata/input-2`
- Archive.org identifier：`input-2`
- 类型：archive.org 单一 item 页；同时托管 `Decision_Logic_data.zip`（Stage 2 modality 数据集）与 `input 2.zip`（Stage 3 复现输入）
- 验证来源：`docs/research/SUN_FINAL_VERSION_AND_DATA_AUDIT.md` §1-§3（2026-07-11 内部审计）+ 2026-07-15 用户提供的 archive.org metadata
- 本地可达性：2026-07-15 任务内 `web_fetch` 调用 `https://archive.org/details/input-2` 返回 fetch failed；`web_search` 多次以 `archive.org "input-2"`、Sun EStG、Sun BERT TextCNN、Sun 2024 BPC 等关键词均**未**返回 archive.org 项目页 URL 与/或文件名直证。本地工作环境的 web 工具此刻**不能**独立确认 archive.org 项目页的可达性。byte-match（size / SHA-1 / 成员 SHA-256）即作为来源权威证据。

### 2.2 2026-07-15 用户提供的 archive.org 元数据（手动录入）

| 字段 | 值 |
|---|---|
| identifier | `input-2` |
| filename | `Decision_Logic_data.zip` |
| expected_size | `191874718` 字节 |
| expected_sha1 | `0346f84a246b7049d5aef58bcb33471435bee106` |
| licenseurl | `null` |
| rights | `null` |

> archive.org metadata 自报 `licenseurl=null` 与 `rights=null`，**并不能**确认为"自由再分发许可"；Springer 论文页脚也只说"数据集可向通讯作者索取 + 给出 Archive.org 链接"。在明确 license 完整文本前，许可保持 `unknown_pending_confirmation`。

### 2.3 官方 `Decision_Logic_data.zip` 元数据（最终核验态）

| 字段 | 值 | 出处 |
|---|---|---|
| 包名 | `Decision_Logic_data.zip` | Sun_FINAL audit §3 + archive.org metadata |
| 官方 SHA-1 | `0346f84a246b7049d5aef58bcb33471435bee106` | Sun_FINAL audit §3 + archive.org metadata |
| 官方 `EStG_raw.txt` SHA-256 | `185385186533FCDB8156D094782E3A3976C85460312EE9D48B424F404817660F` | Sun_FINAL audit §3 |
| 预期成员清单 | `EStG_raw.txt`、`EStG_sent_vec.csv`、`estg.html` | Sun_FINAL audit §3 + 本地 ZIP 实测 |
| 抽样确认内容 | CSV 含德文句子、one-hot 标签、向量列 | Sun_FINAL audit §3 |
| 论文层报告的句子数 | 2,833（definition 1,190 / obligation 1,274 / permission 265 / prohibition 104） | Michel et al. 2022；Sun 2024 final version 引用 |
| 候选下载 URL（待 archive.org 可达性复核） | `https://archive.org/download/input-2/Decision_Logic_data.zip` 或 `https://archive.org/download/input-2/Decision_Logic%20data.zip` | 由入口页 + 通用 archive.org 命名约定推断；**未在本会话独立验证** |

### 2.4 官方 `input 2.zip` 元数据（仅登记，非 S2.1 任务目标）

| 字段 | 值 | 出处 |
|---|---|---|
| 包名 | `input 2.zip` | Sun_FINAL audit §3 |
| 官方 SHA-1 | `a1a0ac8d57eb45698728722628a4c838c592c5bf` | Sun_FINAL audit §3 |
| 官方 ZIP SHA-256 | `A4E12BDBF1631F201A06BD6DDAA30C6423AA33F3BE99338ABFA6E39CFA786FE3` | Sun_FINAL audit §3 |
| 有效成员数 | 57 | Sun_FINAL audit §3 |
| 字节一致性 | 与导师包 / Winter 副本完全一致（去除 `.DS_Store` / `__MACOSX` 后） | Sun_FINAL audit §3 |

> 该包用于 Stage 3 复现，不属于 S2.1-A 的 modality 任务目标，但与 archive.org 同一 item 页绑定，本节只为防 S2.1-B 误用而登记。

---

## 3. 本地核对结果（2026-07-15 字节级核验）

### 3.1 旧轮（核验前）

执行了以下检查：

1. `Get-ChildItem` 列出 `data/`、`data/development/`、各子目录的递归文件清单；
2. `glob **/Decision_Logic_data*`、`glob **/*sent_vec*`、`glob **/input*2*.zip`、`glob **/*.zip`、`glob **/archive*/**/EStG*`：全部返回 `No files matched`；
3. `glob **/sun_modality/**`：仅返回空目录 `data/development/sun_modality/raw/`（本任务为预留 raw/ 目录而由本次会话新建）；
4. `glob **/archive*/**/EStG*`：返回 `No files matched`。

旧轮结论：本地**没有任何**官方包字节；`raw/` 是为预留 S2.1-B/C 落地而**新建**的空目录。

### 3.2 新轮（核验后）

用户在 2026-07-15 任务提示中把 `Decision_Logic_data.zip` 放入 `data/development/sun_modality/raw/`。本轮通过 `scripts/verify_sun_modality_zip.py` 做了**完整字节级核验**：

| 核验项 | 期望 | 实际 | 是否通过 |
|---|---|---|---|
| 文件存在 | 是 | 是 | ✓ |
| 文件大小 | `191874718` 字节 | `191874718` 字节 | ✓ |
| SHA-1 | `0346f84a246b7049d5aef58bcb33471435bee106` | `0346f84a246b7049d5aef58bcb33471435bee106` | ✓ |
| SHA-256（首次本地计算） | — | `ada231f092927813ba9f1cd32a44a3d30d96b57fc463d042dfd76c652b6d58f2` | 新增落档 |
| ZIP 完整性（`testzip()`） | 无 corrupt member | 无 corrupt member | ✓ |
| 成员总数 | 3 | 3 | ✓ |
| 成员 `EStG_raw.txt` | 存在 | 存在 | ✓ |
| 成员 `EStG_sent_vec.csv` | 存在 | 存在 | ✓ |
| 成员 `estg.html` | 存在 | 存在 | ✓ |
| 路径穿越（`..` / 绝对路径 / 盘符 / NUL / 反斜杠） | 无 | 无 | ✓ |
| `EStG_raw.txt` SHA-256 | `185385186533FCDB8156D094782E3A3976C85460312EE9D48B424F404817660F` | `185385186533fcdb8156d094782e3a3976c85460312ee9d48b424f404817660f`（小写，byte-equal） | ✓ |
| `raw/_extract/` 目标目录 | 必须为空或不存在 | 确实不存在 | ✓（S2.1-B 解压前禁止覆盖） |

### 3.3 本地计算的关键成员 SHA-256（首次记录）

| 成员 | SHA-256 | 解压后大小 | CRC-32 |
|---|---|---:|---|
| `EStG_raw.txt` | `185385186533fcdb8156d094782e3a3976c85460312ee9d48b424f404817660f` | 758,957 | `AA9BBBA0` |
| `EStG_sent_vec.csv` | `1e53eb1b7f88f57c63029385eafe5e6f269bb7878328c0c409c5e708250ad5c3` | 470,740,514 | `A9E74EF5` |
| `estg.html` | `bc385ce9acee1fd9289d5c0dc9c273bf0c7392e11783b6043032066c7ce80eb0` | 1,786,182 | `C0F18D9D` |

> 注意：`EStG_sent_vec.csv` 解压后约 470 MB。S2.1-B 决定是否实际解压时必须把"470 MB CSV 在 raw/ 内不进 Git"作为硬约束验证（已由 `.gitignore` 保证）。
>
> 三个成员都**没有** `..` 段、绝对路径、Windows 盘符、NUL 字节或反斜杠，路径安全。

### 3.4 raw/ 与 150 审核工作流的关系

> 注意：项目独立重建的 150 句 EStG 审核数据集在 `data/development/estg/estg_selected_150_de.jsonl`、`estg_150_human_correction_v1.json` 等文件里，**与** Sun 官方 `EStG_sent_vec.csv` 的 2,833 句 modality 训练数据**不是同一份数据**。AGENTS.md 已声明：项目 150 句是 `independently_reconstructed_estg_150_v1`，禁止用官方补充包重抽或替换 sample_ids。本文档与 source_manifest 不得混淆这两类资产。

### 3.5 S2.1-C 完整流式扫描结果与 fail-closed blocker

2026-07-15 的 S2.1-C 批次重新核验 ZIP/CSV 身份后，通过
`zipfile.ZipFile.open()` 对 `EStG_sent_vec.csv` 的全部 470,740,514 个解压字节和
2,833 行做了严格 UTF-8 流式扫描。聚合结果写入
`data/development/modality/sun_estg_modality_v1/schema_audit.json`；该文件不含原句
或向量值。

完整扫描证明早期有限头部观察中有三项错误：

- 第 0 列不是唯一 source ID：非空 2,833/2,833，但只有 164 个不同值，重复行
  2,669 条。因此正式 sample ID 只能显式记录 `row_index_fallback`；不得把第 0 列
  冒充唯一行 ID。
- 第 1 列不是 0–3 modality code：它是作者字段名未知的整数序位候选，完整取值为
  0–13。因此 `official_integer_code_mapping.mapping` 继续为 `null`，状态改为
  `not_applicable_verified_no_integer_modality_column`；generic integer adapter 对缺失
  mapping 或未知 code 仍 fail closed，但不用于本 CSV。
- 第 9 列不是单一 768 维 BERT 向量：每行是以逗号分隔的扁平有限浮点数列表，
  严格等于“空白分词数 × 300”。扁平长度从 900 到 18,900，共 61 种，0 行等于
  768；所有行都能解析、均为有限值、均为 300 的倍数，且与空白 token 数一致。
  这与 Michel et al. (2022) 第 5 页及 §3.3.2 的 300 维 word-vector 说明一致。

真实的 modality 标签是第 4–7 列的 positional strict one-hot：

| 位置 | 项目映射 | 完整计数 | 证据等级 |
|---:|---|---:|---|
| 4 | definition | 1,190 | `inferred_by_exact_distribution_match` |
| 5 | obligation | 1,274 | `inferred_by_exact_distribution_match` |
| 6 | permission | 265 | `inferred_by_exact_distribution_match` |
| 7 | prohibition | 104 | `inferred_by_exact_distribution_match` |

四个计数与 Michel et al. (2022) 第 5 页 Table 1 形成唯一一一对应；本地少量语义
抽样与该推断一致，但原句没有写入任何版本化文件。此映射是**项目按精确分布作出的
证据推断**，不是作者给出的原始 CSV codebook，不得称 `original mapping verified`。
Sun 本地论文第 15 页 §5.1.1 只列出四类名称，不提供 CSV 位置 codebook。

其余结构事实：UTF-8、逗号分隔、无 header、每行恰好 10 字段；无空行、短行、长行、
空文本或解码错误。第 2、8 列的作者字段名仍无本地一手证据，按 auxiliary metadata
处理且不参与标签。第 8 列为二元值（0: 2,720；1: 113）。

完整规范化后共有 2,788 个文本 group，其中 26 个 group 重复（首条以外 45 行），
25 个重复 group 标签一致；**1 个 group 的两条完全相同 normalized text 分别标为
permission 与 obligation**。审计文件只记录 normalized-text SHA-256、行号和冲突
类别，不记录原句。

按照 S2.1-B-R1 的默认 `label_conflict` 合同，2026-07-15 的首次真实 import 在写任何
派生文件前 fail closed。该历史行为保留为默认规则：不得静默删行、改标签、修改
normalization 或按多数类决定。2026-07-16 的用户预结果治理决定及其受限例外见下节。

### 3.6 S2.1-C-R1：精确 conflict-group quarantine

用户在任何模型训练、评价或结果产生前，明确选择
`pre_result_conflicting_label_group_quarantine`。这不是判断哪个标签正确，也不是通用
“遇到冲突就跳过”：

- raw source layer 始终保持 2,833 行，CSV 字节和所有原标签均未修改；
- 唯一冲突 group 的两行**原始文本 SHA-256 也完全相同**，所以冲突不是
  normalization artifact；两行来自不同的 section/reference 候选上下文；
- 两个原标签分别为 permission 与 obligation，不选择、合并或改写其中任何一个；
- 合同精确锁定 source asset、normalized/raw-text hash、row indices 616/1221、逐行
  label 和 section/reference hash；任一字段、数量或计算分布不匹配仍立即 fail closed；
- 该两行整个 group 只进入不可逆 hash 形式的 quarantine provenance，不进入
  `records.jsonl` 或任一 split；
- main analysis population 固定为 2,831，所有后续 baseline、LLM、Hybrid 主实验
  必须共享这同一 population。

程序从真实 2,833 行重新计算得到隔离后分布，而不是只接受合同中的预期数字：

| 类别 | raw source | main analysis |
|---|---:|---:|
| definition | 1,190 | 1,190 |
| obligation | 1,274 | 1,273 |
| permission | 265 | 264 |
| prohibition | 104 | 104 |
| **合计** | **2,833** | **2,831** |

固定 seed 20260715、比例 0.70/0.15/0.15 的 normalized-text group-aware allocator 生成
train 1,985 / dev 420 / test 426；25 个同标签重复文本 group 均保持不可分割，跨 split
normalized-text leakage 为 0，三个 split 两两无交集且并集为全部 2,831 行。该 split
明确是 `project_reconstructed_deterministic_split`，不是 Sun original split。

`quarantine_manifest.json`、`manifest.json` 和 `split_summary.json` 只保存 hash、策略、
population、分布与文件统计，不保存原句或向量。`records.jsonl` 与
`splits/{train,dev,test}.jsonl` 继续由目录 `.gitignore` 保护，禁止提交或再分发。相同
输入、合同、policy 和 seed 的独立重放已证明全部七个产物 byte-identical；默认再次
写入仍由 no-overwrite 拒绝。

同时预注册 `sensitivity_full_source_variant`：保留原始 2,833 行和两个原标签，把冲突
group 整体强制放入 train、禁止进入 dev/test，并尽可能保持其余 membership 与主数据
一致，用于未来衡量 source-label inconsistency 的影响。状态为 `planned_not_run`；本轮
没有训练、评价或生成任何 sensitivity result。

---

## 4. 许可与再分发状态

- `archive.org/details/input-2` 的 license/rights 元数据**未**在本地工作环境核实（archive.org fetch failed，web_search 也未返回 rights 页直证）。
- 2026-07-15 用户提供的 archive.org metadata 中 `licenseurl=null` 且 `rights=null`，**不能**解释为"自由再分发许可"。
- 论文页脚声明（`https://link.springer.com/article/10.1007/s11227-023-05626-0`）：数据集可向通讯作者索取 + 给出 Archive.org 链接。这条声明**不是**对自由再分发的许可。
- 因此，**许可状态**在 `source_manifest.json` 与本文档中均登记为 `unknown_pending_confirmation`。

### 4.1 2026-07-15 用户授权的本地使用范围

用户在任务提示中明确：

- **可**读取、校验、安全解压 raw 内的官方 ZIP，用于本地论文实验；
- **仅**允许本地科研使用；
- **不得**重新发布、上传或提交原始 ZIP/CSV；
- 许可状态**继续**记录为 `unknown_pending_confirmation`；
- 许可未知**只阻止**原始数据再分发和公开发布，**不阻止**本地 hash、schema 和数据结构核验；
- **不**调用任何 LLM/API。

具体动作清单：

| 允许 | 禁止 |
|---|---|
| 读取、计算 hash、做 ZIP 完整性 testzip | 重新发布、上传、提交原始 ZIP/CSV 到任何 Git remote / 公网云盘 / 公开数据集托管平台 |
| 在 `data/development/sun_modality/raw/` 范围内安全解压（路径穿越 + 覆盖保护） | 写入 `references/`、`paper/`、`data/{input,gold,predictions,results}/`、`outputs/`、`_retired/` 之外的任何非 `raw/` 路径 |
| 在 S2.1-C 中做本地流式 schema/hash/聚合统计，并在无数据冲突时生成 Git-ignored development records/splits（不训练、不评价） | 在论文中声称 "official license permits free use" / "已取得官方授权可直接发布" |
| 复现 `verify_sun_modality_zip.py` 做回归保护 | 调用任何 LLM/API 处理 raw/ 内的字节 |

### 4.2 在许可复核为 `redistribution_and_reuse_allowed` 之前

- 不得把 `EStG_sent_vec.csv` 复制到 `data/input/`、`data/gold/`、`data/predictions/`、`data/results/`、`references/`、`paper/`、`outputs/`；
- 不得把 raw/ 下的字节上传到任何外部仓库；
- 不得在论文主张里写"official license permits free use"、"已取得官方授权可直接发布"等；
- 不得用官方 CSV 直接训练 BERT-TextCNN，不得运行模型评价；
- 许可未知**不阻止**本地 hash、完整流式 schema、不可逆聚合统计和 Git-ignored
  development 导入；它继续阻止原始 ZIP/CSV、records/splits、文本、向量的公开
  再分发。版本化 audit/manifest 只能包含不可重建原始数据的 hash、schema 和聚合统计。

---

## 5. 已写入的活动资产（本轮 S2.1-A 全部动作）

| 路径 | 状态 | 说明 |
|---|---|---|
| `data/development/sun_modality/source_manifest.json` | 写入并更新 | 机器可读来源/许可 manifest；版本 `sun_modality_source_manifest@1.0.1`；来源路径已项目相对化，状态为 `manifest_verified_and_assets_byte_matched` |
| `data/development/sun_modality/raw/Decision_Logic_data.zip` | 用户提供；本会话**未**下载、**未**重发布 | 191,874,718 字节；SHA-1 已与 archive.org metadata byte-match |
| `data/development/sun_modality/raw/.gitignore` | 写入 | 目录级 ignore 策略；只保留 .gitignore 自身，ignore 其他所有文件 |
| `data/development/sun_modality/raw/_extract/` | 未创建 | S2.1-B 解压前禁止覆盖；当前为空或不存在 |
| `docs/research/SUN_MODALITY_DATASET_INGESTION.md` | 写入并更新 | 本文件；人类可读 ingestion 记录；状态从 in_progress 升级为 verified |
| `scripts/verify_sun_modality_zip.py` | 写入 | 字节级核验脚本；离线、本地、不读 .env、不调 LLM、不动 Gate |
| `tests/test_sun_modality_source_manifest.py` | 写入并更新 | 最小回归测试：原 28 个用例 + 新增 6 个核验用例（size/SHA-1/成员 hash/_extract 状态/.gitignore 内容/许可诚实）共 34 个 |
| `.gitignore`（仓库根） | 追加条目 | `formal_experiment/data/development/sun_modality/raw/**` + `formal_experiment/data/development/sun_modality/_extract/` 兜底忽略 |
| `docs/EXPERIMENT_LOG.md` + `docs/EXPERIMENT_EVENTS.jsonl` | 通过 `record_change.py` 追加 | S2.1-A 一次性 change 事件（中文人类日志 + 机器事件） |
| `docs/PROJECT_AUDIT.md` §4 S2.1-A 段 | 更新 | 把 S2.1-A 状态由"in_progress"明确写为"verified, S2.1-B 可解锁（仍不实际进入）" |
| `docs/FILE_CATALOG.md` | 重建 | 新增 / 变更文件后同步 |

> 没有写：任何 `data/input/`、`data/gold/`、`data/predictions/`、`data/results/`、`references/`、`_retired/`、`.env`、Gold、Gate 状态、训练脚本、真实 LLM 调用、当前 heuristic 跑分。

---

## 6. 当前 blocker 与解锁条件

| Blocker | 状态 | 解锁条件 |
|---|---|---|
| **B1**：本地无任何官方包字节；外部 archive.org 入口在本会话不可达 | **resolved**（2026-07-15） | 已在用户授权下提供 raw ZIP；size + SHA-1 + 3 成员 + EStG_raw.txt SHA-256 全部 byte-match |
| **B2**：官方 license / rights 元数据未核实 | **open** | 取得 `https://archive.org/details/input-2` 的完整 license / rights statement 文本（archive.org metadata 自报 licenseurl=null 与 rights=null 不足），留档到 `docs/research/SUN_OFFICIAL_LICENSE_RECORD.md`（S2.1-B 任务卡范围内） |
| **B3**：许可仍 unknown，原始及可重建数据不得公开再分发 | **open** | 本地 S2.1-C schema/hash/聚合审计与 Git-ignored development 运行已获用户授权；但 ZIP、CSV、records、splits、文本、向量仍不得上传、提交或公开。取得明确 rights statement 后再决定发布边界 |
| **B4**：一个 raw-text-identical group 存在 permission / obligation 源标签冲突 | **governed for main import；raw inconsistency retained**（2026-07-16） | 用户在任何模型结果前选择精确 group quarantine：不判断正确标签、不改 raw；2 行整体排除于 2,831 主数据。任意非锁定冲突仍 fail closed；未来 full-source sensitivity 仅预注册未运行 |

> B1 已解决；B2/B3 继续限制公开再分发但不阻止已授权的本地 development import。
> B4 没有从 raw source 消失，只通过用户预结果、精确锁定且可追溯的 quarantine 规则
> 解除主 analysis population 的导入阻塞；它不得被描述为“源标签已纠正”。

---

## 7. 是否解锁 S2.1-B

**可以解锁 S2.1-B 的派发，但仍受 B2/B3 限制。**

S2.1-B 的任务卡原文（`AGENT_RUNBOOK.md` §5）要求"依赖：S2.1-A 的来源事实已固定；真实 CSV 可以仍缺失"。本任务满足：

- 来源事实已固定（manifest + 本文档）✓
- 真实 CSV 已具备（raw/Decision_Logic_data.zip 内 EStG_sent_vec.csv 已 byte-match）✓
- raw 字节核验通过（size / SHA-1 / ZIP integrity / 3 members / EStG_raw.txt SHA-256 全部 ✓）✓
- 许可仍 `unknown_pending_confirmation` 但**用户已授权**本地科研使用范围（见 §4.1）✓
- raw/ 内字节不会进 Git（.gitignore 双层保险）✓
- `raw/_extract/` 解压前为空（覆盖保护）✓

因此 S2.1-A 在 `docs/PROJECT_AUDIT.md` 升级为 `verified`，**S2.1-B 可派发**。但：

- S2.1-B 仍不得把 raw/ 内字节写入 references/ / paper/ / data/{input,gold,predictions,results}/ / outputs/；
- S2.1-B 仍不得调用任何 LLM/API；
- S2.1-B 仍不得"用真实 CSV 直接训练/测试/评价"——只可做 schema 推断、列含义核验、确定性 split 构造、不可分发 fixture；
- 本轮**不实际进入** S2.1-B；解锁意味着协调 Agent 在下一个工作批次可以派发 S2.1-B，而不是本轮就推进。

---

## 8. S2.1-C / S2.1-D 当前状态

- 官方 schema：完整流式扫描已 verified；
- development import：真实 2,833→2,831 quarantine import 与独立重放均已成功；
- S2.1-C-R1：**verified**；精确 quarantine、真实导入、独立重放与最终验证已完成；
- S2.1-D：**verified**；official importer 只写项目相对路径，独立 machine gate 已对
  source ZIP、合同、schema audit、quarantine、records/splits、membership、artifact
  hash、ignore 与许可边界完成交叉验证；
- 当前版本化产物：aggregate-only `schema_audit.json`、`quarantine_manifest.json`、
  `manifest.json`、`split_summary.json`、目录 `.gitignore` 与 README；
- 本地 Git-ignored 产物：`records.jsonl` 2,831 行与 train/dev/test 1,985/420/426；
- 路径修复后的 records/train/dev/test SHA-256 与 S2.1-C-R1 完全一致；新 manifest
  SHA-256 为 `21a3390c8356053832041d626563910328952097f0c011ece0ec07a229dba534`，
  新 split summary SHA-256 为
  `a5b0a828d95eae21fb3ba57d9c59bc34f44a4e997cbb455a7d08ea4be4b08bbc`；
- 快速 audit 只流式计算 ZIP SHA-1/SHA-256、读取 ZIP 中央目录并扫描约 2.3 MB 的
  records/splits；不解压或重扫 470 MB CSV、不重建 split、不训练；
- `sun_modality_development_data_verified=true` 只代表本地 development 数据门禁通过。
  许可仍 `unknown_pending_confirmation`，B2/B3 均未解决，formal Gold、正式训练/评价、
  Stage 3 与 final experiment 仍未解锁；
- S2.1 整体 **verified**；下一工程任务建议为 S2.3，但本批次没有进入 S2.3/S2.4。
