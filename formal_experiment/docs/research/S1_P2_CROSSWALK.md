# S1.3 P2 方法证据对照 — Sun/Leopold-style Stage 1 方法级独立重建

> 机器可读版本：`outputs/reports/s1_3_p2_crosswalk_v1.json`
> 状态：**locked_pending_formal_inference**（2026-08-13）
> 诚实标签：`post-Gold paper-derived method reconstruction with a locked
> implementation and prospective one-shot evaluation`

## 1. Sun/Leopold 公开证据明确要求的核心方法

| ID | 证据 | 位置 | 实现映射 |
|---|---|---|---|
| C1 | 流程模型标签解析提取语义组件：actions 与 business objects；labels 的语义组件是 actors/actions/business objects | Sun 2024 §4.1（Process Model Disassembly），Fig. 1 | P2 逐 activity 输出 actor/action/business_object |
| C2 | 采用 Leopold et al. (2013) 技术分解 activity/event labels：model context analysis + structural knowledge of labels | Sun 2024 §4.1，引文 [25]（Leopold 2013 博士论文） | P2 的 pool/lane 模型上下文 + 标签结构语言分析 |
| C3 | 三步：Label Style Recognition → Label Composition Analysis → Semantic Content Derivation（Fig. 3） | Sun 2024 §4.1 Fig. 3 | P2 管线镜像三步（风格识别 → 组成分析 → 语义推导） |
| C4 | 模型结构（Definition 1）显式包含 activities/events/gateways/control flow；actor 可从模型结构获得 | Sun 2024 §4.1 | P2 actor 来自 pool/lane 模型上下文（冻结结构 Process Record + BPMN lane-set 映射） |
| C5 | 语言分析范式：constituency + dependency parsing、root 动词、nsubjpass 被动、规则化概念提取 | Sun 2024 §4.2（同范式家族），Fig. 7 | P2 用离线 spaCy 依存分析 + 确定性依赖规则（root/xcomp/obj/nsubjpass/prep.pobj/conj） |

## 2. 原作者资产不可得的部分（unavailable_or_underspecified）

| ID | 项目 | 原因 | 项目适配 |
|---|---|---|---|
| D1 | Leopold 2013 精确标签风格分类法 | 博士论文本地不可得；Sun 因篇幅未展开 | 锁定最小三风格确定性分类器（verb/noun/degenerate，基于 POS） |
| D2 | action/object 精确句法规则 | Sun 明示 "will not be extensively discussed ... due to space limitation" | 锁定标准依存规则集（见 config `rules` 节） |
| D3 | tokenizer/parser/POS 配置 | 未公开、作者资产不可得 | 锁定离线 spaCy 3.8.13 + en_core_web_sm 3.8.0（dir sha256 `f5c9433c…`，26 文件，无下载） |
| D4 | actor 在空/歧义 lane 时的回退策略 | 论文未规定 | pool name 回退（XML participant），确定性并披露 |

## 3. 论文未明确规定的参数（统一默认值 = project adaptation）

- 归一化：collapse unicode whitespace（与锁定 P1 同策略）；无大小写归一化；输出保持原文 token
- 复合动作：root 动词 + xcomp 动词链（如 "Stop running" → `Stop running`）
- 介词短语：介词词元排除、pobj 名词短语并入（"Communication with data subject" → object=`data subject`）
- 从句（whether/if/that）：命题补语不并入 object（"Check whether …" → action=`Check`、object=null）
- 并列：conj 分支并入 object（"Review the report and the contract" → object=`the report and the contract`）
- 被动：nsubjpass 子树为 object
- 命令式复合名词判定：短语首 token 为 compound 且小写形式命中锁定通用英语动词表（`configs/resources/english_verb_roots_v1.json`，199 个通用动词）→ verb-object 风格

## 4. 为兼容现有 Process Record 所做的适配

- 输入为冻结结构 Process Record（process_record@1.0.0）+ BPMN XML（仅 lane→pool 映射）
- sidecar schema 独立版本 `stage1_label_semantics_p2@1.0.0`（不破坏 P0/P1 合同）
- actor status / label status 枚举为 P2 独立集合

## 5. 纯工程增强（不影响方法语义）

- 确定性排序与 canonical JSON 序列化、hash 绑定、fail-closed、Gold 隔离防护、独立 verifier、双跑 byte-identical

## 6. 明确禁止进入 P2 claim 的 P0/P1 机制

- P1 首词 whitespace 切分（P2 用依赖结构；"Communication with data subject" 在 P1 得 object=`with data subject`，P2 得 `data subject`）
- P0 raw label 直通
- 任何隐藏的 P0/P1 fallback（runtime 缺失时 fail-closed raise）

## 7. 证据来源与 hash

| 来源 | 路径 | SHA-256 |
|---|---|---|
| Sun 2024 全文提取 | `references/papers/extracted/sun_2024_full_text.txt` | `947140c3…eec47` |
| Sun 2024 结构化证据 | `references/papers/extracted/sun_2024_paper_evidence.json` | `65f03a46…86ac0` |
| Sun 2024 缺失资产清单 | `references/papers/extracted/sun_2024_missing_assets.md` | `ea624152…eb3a92` |

## 8. Claim boundary

方法级独立重建（非 exact reproduction、非 Sun original implementation、
非 P1 enhanced、非 novel Stage 1 method、非 blind preregistration）；
锁定发生在 Stage 1 Gold 形成之后；实现参数在第一次正式评价前完成 Git 锁定；
评价后不得调优。
