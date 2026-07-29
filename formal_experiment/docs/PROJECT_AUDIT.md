# 项目实时状态（兼容文件名 PROJECT_AUDIT.md）

**更新时间**：2026-07-29
**唯一活动目录**：`formal_experiment/`  
**完整路线**：`docs/MASTER_PIPELINE.md`  
**机器事实源**：`python formal_experiment/scripts/audit_project.py`（自动完整性检查）  
**执行制度**：实验日志为主、自动检查为辅、正式复核只在阶段冻结/最终运行/投稿前

本文是唯一实时状态页，只记录“现在做到哪里、下一步做什么”。研究目标、完整
Stage 1/2/3 工作分解、依赖和完成定义不在这里重复，统一见主 Pipeline。

## 1. 当前结论

项目目标是完整重建并改进 Sun 的三阶段流程，而不是只做一个 Stage 2 小实验：

1. 完成 Stage 1 流程模型结构与标签语义解析；
2. 在 Stage 2 完成 Sun、传统方法、直接 LLM 和 Hybrid 的同条件比较；
3. 用主数据和更复杂法律语料验证复杂度退化与 LLM 优势边界；
4. 在 Stage 3 完成多 baseline 的规则—流程匹配、违规检测和错误类型分类；
5. 分开报告 Oracle Stage 3 与端到端误差传播，并做 Stage 2/3 交叉消融。

实施顺序锁定为：**先完成 Stage 2，再补齐 Stage 1，最后复现并扩展 Stage 3**。
当前机器合同仍是 Stage 2 优先、Stage 3 固定的阶段性合同；启动 Stage 3 改进前
必须另行修改并审计合同。

根据导师最新要求，论文非结果章节从现在与实验并行：先写引言、相关工作、方法、
数据/标注流程和实验设计；结果、摘要结论和“LLM 优势”只保留显式 TODO，直到正式
manifest 解锁。论文工作稿位于 `paper/`，不能反向定义实验状态。

论文轨道 PW1–PW6 的当前可写部分已完成：引言/RQ、相关工作、方法、数据/Gold、评价
协议，以及只允许由 formal manifest 回填的空结果表、图规范与 provenance 登记。
Stage 2 统一六要素合同 v1 已冻结给人工、D1 v5 与 H1 v5；12 条 pilot 只完成
static/schema/local 覆盖，不是 Gold、few-shot 或性能评价。S2.10-E 统一 evaluator 已
冻结；S2.2 人工裁决现已完成并由 deterministic receipt 锁定为 150/150 approved、
900/900 六字段决策闭合、150/150 adjudicated、231 clauses。该状态是 annotation
freeze，不等于 formal Gold publication。下一项 PW7 是 Stage 2 正式结果，当前被
RWI-0001/RWI-0007 的 context/language route QA、正式 input/Gold publication、
S2.7、S2.10–S2.13 后续方法/评价和 formal manifest 门禁阻塞；S2.4 分类器、S2.5
extractor 与 S2.6 canonical B0 技术组合均已完成。另已在冻结 Layer E 上完成明确标注为
development 的 B0 sentence-only English 批处理：150/150 attempts、独立82敏感性子集、
LLM=0。该证据不发布 formal Gold，也不解除现有门禁。

全实验实际问题现统一登记在 `docs/REAL_WORLD_ISSUE_REGISTER.md`。当前共登记 31 项：
RWI-0001（句级抽样缺少跨句上下文）和 RWI-0007（德文来源、英语方法、非德语审核
之间的语言缺口）保持 `open`；RWI-0002–RWI-0006 与 RWI-0008 已带解决方法、验证
证据和实验事件标为 `resolved`；RWI-0009 修复了六要素人工值导航回显与提交断链，
RWI-0011 用单屏六要素工具消除了旧状态机与手工 span 负担，RWI-0012 修复了 Windows
实际落盘 hash 与内存 LF hash 不一致；RWI-0013 解决真实 B0 批处理中的 Tsurgeon
完整树删除终态，并在 266 句中保留 2 次显式诊断；RWI-0014 解决 evaluator 把
method-local ID 与 exact boundary 当共享身份造成的系统性漏计，并以 immutable attempts
完成 v1.2 重算。
RWI-0008 冻结了 sentence-only 六要素操作合同，但
没有替代 RWI-0001 的 context sidecar 决策或 RWI-0007 的语言 QA。RWI-0005 在
150/150 状态再次暴露两项 stale 零进度/未冻结断言，本批次已改为依据活动状态验证，
用户已完成的决定不会为通过测试而被回退。RWI-0001
已完成 150/150 句级独立性盘点：独立 82、需上下文核实 26、不独立 42；只读报告位于
`outputs/development/estg150_independence_audit_v1/`。后两类留作人工核实且未写入
Layer E；context sidecar、来源 hash 与 B0/H1/D1 公平输入合同仍须在 formal Gold
publication 与正式方法运行前闭合，因此 RWI-0001 保持 `open`，但不否定已完成的
sentence-only English annotation freeze。
RWI-0010 登记第三方中转的模型身份、参数透传、实时币种/阶梯计价和数据处理风险；
当前已用 development-only 双轮 Sol 候选、strict schema、隐藏密钥、硬预算、最多 5 条
pilot 和全量二次授权进行缓解，但在真实 pilot 前后都不能把中转声称的模型身份写成
独立验证事实。ChatAnywhere 外发被托管策略拒绝后，用户已明确授权改用 Codex 内置
Sol 子代理；经用户后续明确授权，固定 150 条现已全部生成并通过本地严格验证。AI
aggregate 不自动写 Layer E；用户只在极简工具点击“保存并下一条”时确认并写入当前条。
B2b 只读 prohibition↔permission 诊断进一步确认 v10-A 的 6 条对齐
prohibition→permission 错误中，严格允许的强否定白名单仅覆盖 1 条，低于至少 3 条的
实例化门槛；因此 B2b 为 `not_instantiated`，没有生产 resolver、预注册或 All150，
v10-A 与 active registry 均保持不变（RWI-0019）。
B3a v1 的 `not_instantiated` 安全结论仍保留，但其机会归因因六项方法缺陷已更正为
`inconclusive_not_instantiated_invalid_for_tregex_opportunity_attribution`。correction v2
真实运行 CoreNLP 4.5.10 和六条原样冻结 Tregex，重放 v10-A scope/normalization/dedup
及 Table8 一对一 any-overlap；106 个 raw match 经 98 个 accepted match 得到 76 个 final
unique spans，其中 genuinely new=10，add-only constraint TP/FP/FN delta=0/10/0。因此
v2 仅为 live-Tregex opportunity diagnostic，不是性能结果；没有生产候选、候选 All150
或 B3b。
B3b 随后在固定 v10-A span/Tregex/lexicon/segmentation 上完成 typed ownership 机会诊断：
父版 580 条 condition/constraint span 来源重放完全一致，constraint→condition / condition→constraint
firing=79/8，改变 87 spans/53 records，59 条为 target 去重抑制，268 条 ambiguous 全部保持。
opportunity overall TP/FP/FN=434/380/390、F1=0.529915，低于父版 458/415/366、
F1=0.539776；18 项实例化门槛失败 11 项，因此 `not_instantiated`。没有生产候选、prereg
或候选 All-150，active registry 与 v10-A 保持不变（RWI-0020）。
B5 随后完成 genuine sequential Tsurgeon 与 post-surgery Tregex actor/action consumption 的
结构实例化：29 条 v3 pattern 字符串/顺序精确保持，真实 CoreNLP 4.5.10 合成门 15/15。
唯一 All-150 的 raw/attempted/accepted/rejected 为 1103/338/336/2，post-surgery
action/actor matches=322/253，最终 Tregex action/actor spans=324/36，dependency
candidate/fallback=0/0；但 terminal tree removal=2，且 actor/action/overall Table8 F1
降至 0.428571/0.574431/0.505585，A/B/C/E/F 失败、仅 D 通过，所以不晋级。
运行期间另一个 Grok 会话覆盖了 prereg 和部分 B5 文件；启动前冻结 SHA 为
`2b3062da26a27bb40677b45ad2d38de73a2b56a726f52294bcd7916a7f1626ac`，manifest
结束时重读到 `38a11ea0b941f81c56b3f20362ca8ef537f7d998837e63ecf9585ce6669fac9a`。
冻结文件现已从本地会话历史逐字节恢复并通过全部绑定校验，但既有 manifest 不修改、
All-150 不重跑，因此该输出只保留为 diagnostic evidence，不作为严格可接受的
preregistered negative candidate。第二次命令调用在约 5 秒内 fail closed，未执行第二次
All-150；v10-A 与 active registry 保持不变，未启动 B6/BERT 阶段（RWI-0021）。
RWI-0022 记录历史内置 Sol 没有存档隐藏 system/developer transport 与内部 API envelope；
该不可追溯信息不能事后伪造。C0 已以 external canonical serializer v1 缓解：八项可见
资产、Layer-A 顺序、0–2 双轮/3–149 单轮、三角色消息、UTF-8/LF、strict schema 和
统一 validation 均 hash 锁定；四 provider adapter 只包 transport 外层。随后官方 DeepSeek
V4 Pro 与 ChatAnywhere 中转 gpt-4o 各完成一次获授权 C1 synthetic 调用，均返回 HTTP 400，
没有候选、评测、P/R 或 C2 转移，也没有读取 Layer D/E 或 Gold 派生材料。RWI-0023 记录
旧 runner 未保存 HTTP 错误正文的诊断盲区；未来失败现限长保存 raw body/hash/request ID，
且同一 gpt-4o transport SHA 与既有请求完全一致。旧两次 400 的具体字段根因仍未知。
获授权的七模型 C1 矩阵随后确认失败并非同一种“模型拒答”：ChatAnywhere 5.6-luna/5.4-nano
进入 strict schema 校验后拒绝 `schema_version` 缺少显式 `type`；4.1-nano/3.5-turbo 不识别
`reasoning_effort`；5-nano 以 503 和两次相同字节 retry 耗尽；gpt-4o 无 HTTP response 断连；
官方 DeepSeek V4 Pro 则拒绝 `developer` 消息角色。RWI-0024 修复了
`RemoteDisconnected` 未进入网络重试分支的问题，但没有越过授权重跑 gpt-4o。矩阵共 7 个
logical request、2 个 transport retry、0 候选、0 evaluation，P/R 不适用，C2 未启动。
RWI-0025 随后以版本化方式修复请求进入模型前的兼容性：canonical v1 schema/hash/serializer
完全保留，另建 strict transport schema adapter v1.1，只补 6 个字符串 const/enum 的显式
type；递归 Structured Outputs preflight 与恰好七模型 capability allowlist 在 key/network 前
fail closed。2026-07-26 获新授权后，ChatAnywhere `gpt-5.6-luna` 单条 synthetic 真实 C1
成功生成 1 个候选，原始 canonical schema、exact span 与 cue coverage 本地验证全部通过；无重试，
provider usage 为 1167 input + 829 output = 1996 tokens，按锁定价格记录 0.042987 CA。
`provider_reported_model=gpt-5.6-luna-2026-07-09` 只属于未独立验证的 relay report。C1 已通过，
但 evaluation 未开始，P/R=null，C2=false；其余不兼容模型仍不会自动删 reasoning、合并角色、
降级 json_object 或改 tool call。C2 的索引 0–2、Pass A/B 共六份离线 strict transport 请求
现已用不可覆盖的 dry-run ID 冻结并全部通过 preflight；三个 Pass-B hash 明确只绑定历史
validated Pass-A fixture，未来 live hash 必须在同次运行的 Pass A 后生成。预算护栏离线配置为
6 calls / 78,000 tokens / 1.92 CA，provider_authorized=false、API=0、C2=false（RWI-0026）。
另获授权的 `gpt-5.4-nano` 单条 C1 完成 1 call、0 retry，provider usage=2956 tokens、
0.01728755 CA；候选因 `clause_span.end=58` 超出 57 字符 proposed text 被 canonical validator
拒绝，0 valid candidates、C1=false、C2=false、P/R=null。原失败收据的零 usage 缺陷以
不可覆盖 accounting correction 修正，原始 response/failure 均保留（RWI-0027）。
RWI-0031 记录了长期未版本化资产与 C2 离线测试临时目录泄漏：测试临时父目录现固定为
`.tmp/`，根目录旧 Stage 2 草稿已迁入退役区，可访问的可再生缓存已清理；部分旧 `.tmp/`
条目因异常 ACL 保持 ignored/隔离。现有 Gold、预测、结果和 manifest 未移动、删除或覆盖，
完整活动状态已通过验证；458 个跨任务重要路径已由 checkpoint `56d2b03` 提交并推送到
`origin/experiment/paper-validation-r1`，ignored cache、restricted raw data 与 provenance stores 未提交。

## 2. 当前门禁

| 门禁 | 当前值 | 含义 |
|---|---:|---|
| `integrity_pass` | true | 可以继续受控开发，不代表实验完成 |
| `stage1_structural_verified` | true | S1.1/S1.2/S1.4 的 Process Record schema、BPMN 结构解析与控制流派生通过 two-fixture exact-hash synthetic gate；未做标签语义或性能评价 |
| `stage1_label_semantics_verified` | true | S1.3 P0 原标签无推断与 P1 固定表面切分通过 six-activity exact-hash synthetic gate；未读正式 BPMN/人工 Gold，未做性能评价 |
| `stage1_annotation_protocol_verified` / `stage1_formal_membership_ready` / `stage1_human_gold_freeze_ready` | true / true / false | S1.5 blank schema/source binding/freeze validator 已验证；7 个 GDPR BPMN 已 byte-exact 提升并与 Stage 3 共锁，7 records/45 activities/135 fields，Gold 仍为 0/7 |
| `stage1_evaluator_verified` / `stage1_formal_results_ready` | true / false | S1.6 结构/语义/coverage/error 指标合同已通过 synthetic exact-hash gate；formal scope 现只等 Stage 1 human Gold 与正式方法运行 |
| `formal_capsule_versioned` | true | `formal_experiment/` 已进入 Git checkpoint `bfb0b8a`；不代表 input/Gold/结果已冻结 |
| `sun_modality_development_data_verified` | true | 2,833→2,831 development 数据、quarantine 与重建 split 已通过独立机器门禁；不是 formal Gold |
| `public_marker_lexicon_verified` | true | S2.3 英文 public-source v1 的 64 个 marker 与 exact payload 已由 S2.5 live extractor 绑定 |
| `s2_4_license_evidence_verified` / `s2_4_ready` | true / true | 官方许可证据仍如实记录为 unknown；独立的项目决定 exact-hash 解锁本地非商业训练、dev 选择和评价，再分发仍禁止 |
| `s2_4_bert_textcnn_verified` | true | S2.4 离线训练、dev 选择与唯一一次 test 评价已由 versioned manifest/checkpoint hash 锁定；test n=426，accuracy=0.924883，macro-F1=0.851071 |
| `s2_5_contract_verified` | true | CoreNLP 4.5.10、规则 registry、六字段顺序和 synthetic fixtures 的精确 hash 已锁定 |
| `s2_5_runtime_ready` / `s2_5_verified` | true / true | 外部 ZIP/JAR hash 和 live manifest 已验证；12 patterns、11 fields、7 surgeries 通过 |
| `s2_6_verified` | true | exact S2.4 checkpoint 与 attested S2.5 live observations 已按德文分类/英文抽取路由生成 1 条 canonical record；schema/cross-field invalid=0；不是性能评价 |
| `stage2_extraction_contract_gate.ready` | true | `stage2_extraction_contract@1.0.0`、现有 canonical schema、人工协议、D1/H1 v5、12 条非 Gold pilot 与 hash bundle 已冻结；RWI-0001/RWI-0007 和正式 Gold 门禁仍开放 |
| `estg150_candidate_protocol_c0_verified` / `estg150_c1_transport_adapter_offline_ready` / `estg150_c1_runtime_verified` | true / true / true | canonical external serializer v1、八项历史资产、0–2/3–149 分流与 fixture 继续 hash 锁定；strict transport v1.1 为恰好六个 type addition。七模型旧矩阵仍保留 0 候选历史；新获授权 gpt-5.6-luna 单条 C1 为 1 候选、1996 tokens、0.042987 CA、canonical validation pass、C1=true。C2 六请求离线准备已冻结且全 preflight pass，API=0、evaluation=0、P/R=null、C2=false |
| `s2_7_modality_baselines_verified` / `s2_7_overall_ready` | true / false | 多数类、固定德文关键词和 word 1–2 gram Multinomial NB 已在同一重建 split 上 aggregate-only 运行；NB test accuracy=0.784038、macro-F1=0.568849；phrase/full Stage 2 仍等 formal route/input/Gold publication |
| `s2_8_verified` | true | H1 v5 prompt 已绑定统一合同；局部字段与 ambiguity metadata merge、确定性 45-call 分配、recovered-error 可计分 B0 回退及 46.08 万 token/1.5 USD 上限通过 v6 synthetic exact-hash gate；未调用真实 LLM |
| `s2_9_verified` | true | D1 v5 actual prompt 含 4 个手工 synthetic canonical few-shot；统一合同、`gpt-4.1-2025-04-14`、temperature=0、5 repeats、0 retry、750-call/37-USD 上限及 invalid/API 保留通过 v5 manifest exact-hash gate；未读 `.env`/Gold/B0/H1，未调用真实 LLM |
| `g05_complexity_verified` | true | 文本 11/BPMN 12 个预结果指标、固定 low/medium/high 分层、schema 与预测/结果泄漏 fail-closed gate 已通过；尚未选择复杂数据集 |
| `s2_10_evaluator_verified` / `s2_10_main_data_results_ready` | true / false | 统一 evaluator 的 membership、modality、span、coverage、edge、invalid/API、cost 与人工 style 模板已 exact-hash 验证；5 条 synthetic 常数不是正式性能结果 |
| `s2_10_evaluator_v3_verified` / `s2_7_b0_v3_development_verified` | true / true | v1.2 method-independent clause/entity alignment 与 immutable B0 重算均通过 exact-hash gate；旧 v1.1 低分报告保留但已被替代；没有重跑模型/API，不是 formal performance result |
| `review_aids_zh_v2_active` | true | EStG-150 Layer D 已由 `deepseek-v4-flash`、`thinking=disabled` 生成150/150中文辅助与150/150盲回译；25项严格校验和原子 promotion 通过 |
| `human_review_input_ready` | true | Layer E 输入门保持有效；该门与进度独立 |
| `human_review_freeze_ready` | true | strict validator 确认 150/150 adjudicated，annotation snapshot 已冻结 |
| `stage2_annotation_freeze_verified` | true | S2.2 receipt exact-hash gate 绑定 150 records、900 resolved decisions、231 clauses；不发布 formal Gold、不授权正式方法运行 |
| `formal_gold_publication_ready` | false | RWI-0001/RWI-0007、route/data/stage3/publication whitelist 尚未共同重锁 |
| `final_experiment_ready` | false | 正式方法、冻结数据与最终实验均未就绪 |

每次修改后的最新值以机器检查输出为准；若本表与机器检查冲突，以机器检查为准并
立即修正本页。

## 3. 已有资产与真实边界

| 资产 | 当前状态 | 允许的表述 |
|---|---|---|
| EStG-150 五层审核工作流 | 用户已完成 Layer E：approved English 150/150、六字段决策 900/900、adjudicated 150/150、最终 231 clauses；receipt 和 machine gate 已锁定 exact bytes。RWI-0001 句级盘点仍为独立82、需上下文核实26、不独立42 | 可称 `LLM-assisted, human-adjudicated annotation freeze`；当前不得称 formal Gold 已发布、Sun original 150、exact reproduction 或 human-verified German-to-English translation |
| GPT-5.6 Sol 全量 AI 候选 | 内置 Sol development run succeeded：150/150、232 clauses；翻译 accepted=138/edited=11/uncertain=1；context sufficient=51/insufficient=26/uncertain=73；confidence high=50/medium=89/low=11。root strict schema/sample/exact-span/关系/cue覆盖全通过；外部 API/费用为0，不读 Layer D，不由 Agent 写 Layer E | 只能称 Codex 内置 `gpt-5.6-sol` 生成的 development AI candidates；aggregate 本身不是人工 Gold，用户单击确认或修改后才进入 Layer E |
| EStG-150 canonical candidate protocol C0/C1 transport + C2 offline prep | C0 **verified-offline**：serializer `d20ae560...`、fixture `eb074081...`；strict transport v1.1 保留 canonical schema `fbbb628a...`，transport schema `ef8c684b...`。`gpt-5.6-luna` 单条 runtime 为 `succeeded_frozen`、1 canonical-valid 候选；低成本 `gpt-5.4-nano` 单条 runtime 为 canonical-invalid、0 候选（2956 tokens、0.01728755 CA）。C2 0–2 × Pass A/B 的六请求离线收据已冻结，全 preflight pass、无 downgrade，配置 6/78,000/1.92 CA 护栏 | 可称 gpt-5.6-luna C1 runtime 已验证、gpt-5.4-nano C1 fail-closed 且 C2 offline preparation 已冻结；历史隐藏 transport 未存档，relay 模型身份未独立验证；未评测、P/R=null；C2 未启动 |
| 旧 heuristic 产物/模块 | development provenance only | 不再是活动 `sun_rule_only` 命令，不能冒充 Sun 原始实现或正式结果 |
| B0（BERT-TextCNN + CoreNLP/Tregex/Tsurgeon） | technical verified；v1+v3+v4+**v5** development | v1 modality micro F1=0.423。v3=0.612；v4 欠分割回退=0.508（保留）；**v5**=modality micro P/R/F1=0.594/0.658/0.624。**v6=负向且 Phase A 诊断无效**（RWI-0016 resolved by `s27_estg150_b0_phase_a_correction_v1`：真实 classifier_only F1=0.439≠hybrid 0.632；Gold-seg hybrid F1=0.788；S2.4 1985/420/426 overlap exact=0）。v6 负向。**v7 promoted modestly as current best development**: modality micro P/R/F1=0.598/0.662/0.628 (+0.004 F1 vs v5), align F1=0.801 equal, Table8 F1=0.492 equal; uses candidate B invsqrt-weighted classifier + lexicon v2 runtime (161 active); tsurgeon_enabled=false (honest). RWI-0016 mitigated (residual Phase A v3); RWI-0015 mitigated; RWI-0017 open (S2.4 test exposed). v8-A/B/C preregistered and run: best v8a modality F1=0.63244 (+0.004 vs v7, only +1 TP) — **does not meet +0.010 promotion gate**; v8b/c Table8 F1 0.492→0.506 but hallu up. **No v8 promotion; provisional best remains v7; v10a passed scope gates (Table8 F1 0.540, cons 0.396, presence 0.703) but modality F1 still 0.6283 so not final best; v9a run F1=0.62834 (=v7, not promoted); placeholder=0; edgeFP 34; v9-B not_instantiated**. 、align F1=0.801、complete-record=0.347、Table8 any-overlap F1=0.492。`method_variant=b0_enhanced_v5`，非 paper-faithful。RWI-0015 mitigated。正式主表仍待 RWI-0001/0007 与 formal Gold publication |
| B0 B2a/B2a2 definition 增量 | development negative evidence；不晋级 | B2a 把 record fallback 从 20 增至 60；B2a2 以同子句四分类概率做三类受限解码，使 fallback 恢复 20、受支持新增 fallback=0，A/E 门槛全过；但 definition TP/FP/FN=2/13/37、F1=0.074，overall micro F1=0.583，B/C/D 失败。唯一 All150 已完成；active registry 不变，不调参、不重跑；RWI-0018 mitigated |
| B0 B2b prohibition 增量 | development diagnostic；`not_instantiated` | v10-A aligned prohibition→permission=6；严格白名单桶为 no-subject modal=1、no usable clause-local signal=5；预计触发/可恢复上限=1、permission TP loss=0，未达到至少 3 条实例化门槛。未建生产候选、未预注册、未跑 All150；active registry 不变；RWI-0019 open |
| B0 B3a constraint Tregex 诊断 | correction v2 complete；v1 opportunity attribution inconclusive | v1 的六项方法缺陷已逐项确认；v2 用真实实例键、CoreNLP 4.5.10 live Tregex、v10-A constraint scope/normalization/dedup 和冻结 Table8 一对一 matching。六条 compile 均成功；raw/accepted/final=106/98/76；exact/normalized/containment/partial/new=40/0/24/2/10；add-only TP/FP/FN delta=0/10/0。v1 `not_instantiated` 的安全意义仍成立，但不得再用 v1 判断 Tregex 可恢复上限。未创建生产候选、未跑候选 All150、未改 active registry、未启动 B3b |
| B0 B3b typed ownership 诊断 | development diagnostic；`not_instantiated` | 固定 v10-A 的 580 条 condition/constraint span 来源重放完全一致（condition Tregex/lexicon/fallback=134/111/0；constraint=308/27/0）。两向 firing=79/8，changed=87 spans/53 records，duplicate suppress=59、ambiguous unchanged=268、capacity=0；condition/constraint/overall F1 分别 0.566449→0.534447、0.395604→0.372760、0.539776→0.529915，coverage presence/complete 下降且 hallu 上升。11/18 实例化门槛失败；未创建生产文件、未预注册、未跑候选 All-150，RWI-0020 open |
| B0 B5 sequential Tsurgeon + post-surgery Tregex | structurally instantiated；not promoted；diagnostic-only due concurrent prereg drift | v3 pattern count/string/order=29/exact；synthetic 15/15；唯一 All-150 raw/attempted/accepted/rejected=1103/338/336/2，terminal removal=2，post action/actor matches=322/253，final spans=324/36，dependency candidate/fallback=0/0。actor/action/overall F1=0.428571/0.574431/0.505585；A/B/C/E/F fail、D pass。manifest prereg SHA `38a11e...` 与启动前/当前冻结 `2b3062...` 不一致，故不作为严格 preregistered candidate；不改 manifest、不重跑，v10-A/active registry 不变；RWI-0021 open |
| H1（Sun + LLM fallback） | S2.8 v6 offline preregistration + extraction-contract v1 + S2.10-E evaluator verified | 已绑定 verified B0 和统一六要素语义；runner 只做离线 plan；真实 LLM 未授权，正式 batch 仍待 route QA、正式 input/Gold publication 和总门禁 |
| D1（direct LLM） | S2.9 v5 offline preregistration + extraction-contract v1 + S2.10-E evaluator verified | v5 prompt/few-shot/统一语义/model/sampling/repeat/budget/失败分母已机器锁定；runner 只做离线 plan；真实 LLM 未授权 |
| S2.7-M 非 LLM modality baseline | aggregate component run verified | 多数类/固定关键词/NB 的 dev/test 聚合指标可报告为重建 split component 结果；不得称完整 Stage 2，也不得与尚未运行的 H1/D1 作性能比较 |
| Stage 1 | S1.1–S1.6 合同 verified；formal membership 7/7；S1.7 blocked | 结构/控制流、P0/P1、blank protocol、evaluator 和 all-seven 输入已锁；P2、7/7 人工 Gold/正式结果未完成 |
| Stage 3 | all-seven membership locked；其它仍为 fixture/scaffold | 扩展 7 文件/hash/claim 已固定；Sun 原 4 文件名、matching/violation Gold 和多 baseline 比较仍未完成 |
| 正式结果目录 | 未冻结 | 当前不得声称最终实验结果 |
| Sun modality development 数据 | verified；2,831 analysis rows | 只允许本地 development 使用；许可未知、禁止再分发，不是 Sun original split |
| public marker lexicon v1 | verified；7/25/19/5/8，共 64 个 | 英文 public-source reconstruction、development-only；不是 Sun original/full lexicon，不能据此训练或评价 |
| **Paper-level best-effort LLM pilot**（D1 + H1-naive + H1-selective，EStG-150，n=150）| **succeeded**；用户明确授权偏离 canonical strict protocol | D1（LLM direct）F1=**0.840** (P=0.864, R=0.818, TP=184, FP=29, FN=41)；H1-naive（B0 ∪ LLM union, IoU≥0.5 dedup）F1=0.668 (TP=165, FP=104, FN=60)；H1-selective（LLM as B0 verifier + completer）F1=0.796 (TP=185, FP=52, FN=43)；B0 baseline F1=0.669。LLM=DeepSeek V4 Pro via 官方 API（.env 只配 DeepSeek + Qwen，无 ChatAnywhere gpt-4o）；总 token 536K（206K D1/naive + 330K selective）；费用 ~$1.3；12 条 parse error（2 D1 + 10 H1s）fallback 到 B0。**不**走 canonical 协议：token-IoU ≥ 0.3 对齐（不是 exact span canonicalization）、无 SHA-bound receipt、json_object 模式。**H1 < D1 的根因是当前 B0 v10a 弱于 Sun 原版**，H1-selective 触发 LLM anchoring effect（FP 从 29 涨到 52）。**仅 paper-level，**不可**作 formal Gold publication 证据。事件 Event 2026-07-28 paper_pilot_d1_h1naive_h1selective_150_20260728 已入 `docs/EXPERIMENT_LOG.md` 与 `docs/EXPERIMENT_EVENTS.jsonl`。脚本 `scripts/run_d1_paper_pilot.py` / `run_h1_paper_pilot.py` / `run_h1_selective_pilot.py`；输出在 `outputs/paper_d1_pilot/`、`outputs/paper_h1_pilot/`、`outputs/paper_h1_selective_pilot/`。**Sun-strength H1 模拟（path 2）作为 future work 未跑** |
| **Sun-strength H1 controlled simulation**（n=150，pure computation, 0 LLM calls）| **succeeded**；supplementary material for paper | **CONTROLLED SIMULATION, NOT REAL BENCHMARK.** 用 Gold 模拟"理想 B0"按扰动率 p 在 {0.05, 0.10, 0.20, 0.30, 0.50, 0.67} 五个等级加噪声，每个 5 seed。扰动 mix 50% 错 modality + 30% 错 text + 20% 删除（匹配真实 B0 错误分布）。D1 候选来自先前 paper_pilot 实跑（DeepSeek V4 Pro, F1=0.8019）。**Crossover point ~ B0 F1 = 0.80**：B0_sim F1=0.82 时 H1=0.844 vs D1=0.802（+0.04）；F1=0.91 时 H1=0.905 vs 0.802（+0.10）；F1=0.95 时 H1=0.943 vs 0.802（+0.14）；低于 0.80 D1 胜。**我们真实 B0=0.674 处于 D1 主导区**——这从机制上解释了 H1<D1。脚本 `scripts/run_sun_strength_simulation.py`；输出在 `outputs/paper_sun_strength_simulation/`。事件 Event 2026-07-28 paper_sun_strength_simulation_150_20260728。Caveat：扰动模型是模拟不是真实 B0 错误分布，结论仅方向性，真实 Sun-strength 复现仍为 future work。**与 main H1/D1 严格隔离，不参与主表数字。** |
| **Paper Validation R1 modality-only 重复实验** | **partial paper-level；不得并入六要素主表** | 冻结运行 prompt 与聚合预测只支持 clause text + modality；8/9 repeats 有效，D1/H1-primed/H1-empty F1=0.8486/0.8156/0.8540。D1 repeat 02 缺 30 条为 invalid；repeat 04 有 5 个成功 batch 和 138,510 tokens，但尚无合并预测/指标且 provider host 与根 manifest 不一致，保持 partial。threshold/bootstrap 现有文件混入 invalid repeat 02，引用前必须过滤重算。完整隔离口径见 `docs/experiments/STAGE2_RUN_INVENTORY.md`。 |
| **目标 DeepSeek V4 Pro 六要素 B0/H1/D1 对比** | **not yet run as one canonical comparison** | B0 已有 150/150 canonical development attempts 和六要素指标；H1/D1 只有统一合同下的离线预注册，没有 DeepSeek canonical 全量预测/P/R。旧 paper pilot、Paper Validation R1 和 internal Sol 人工候选均不能替代该缺口。下一次运行必须使用同一 150 IDs、extraction contract、canonical schema、S2.10-E evaluator；H1 仅做预注册字段 fallback。 |

Sun 最终版、公开数据、引用链和代码来源证据统一放在 `docs/research/`；历史路线和
过期交接统一放在 `_retired/docs/2026-07/`，不得再作为实时指令。

## 4. 当前工作队列

| 顺序 | Pipeline 任务 | 当前动作 | 完成信号 |
|---:|---|---|---|
| 1 | P0 / G0.6 | **已完成**：主 Pipeline、日志/检查制度与 Git checkpoint 有回归测试保护 | Agent 入口、目录、日志字段和自动检查已固定；checkpoint `bfb0b8a` 可追踪 |
| 2 | S2.1-A | **verified**（2026-07-15 字节核验通过）| raw 字节已 byte-match：size 191,874,718、SHA-1 `0346f84a246b7049d5aef58bcb33471435bee106`、ZIP integrity testzip 通过、3 个预期成员全部存在且路径安全、EStG_raw.txt SHA-256 与 2026-07-11 审计记录一致；B1 已 resolved。2026-07-16 的 S2.4-L 进一步确认许可证据复核完成，但外部许可仍缺失 |
| 2.1 | S2.1-B | **verified**（2026-07-15；R1 contract repair） | 合同/schema/importer/CLI/15 个 synthetic fixtures 已修正：显式 source ID 重复 fail closed；无 ID 时显式 row-index fallback 并入 manifest；normalized-text group-aware split；标签冲突 `label_conflict` fail closed；唯一小类别阈值为 3 个 group；ZIP SHA-1/SHA-256 独立核验；5 个确定性文件含 manifest byte-identical；manifest 不含运行时、self-child 或 placeholder；synthetic one-hot 与 official pending schema 分离。R1 定向测试 54 passed；首次全量检查 840 passed, 22 skipped，0 integrity errors |
| 2.2 | S2.1-C | **verified — R1 pre-result conflict quarantine + development import**（2026-07-16） | raw 2,833 行、CSV 字节和原标签均未修改；只有精确匹配 source/normalized/raw-text hash、row 616/1221、逐行 permission/obligation 标签与 section hash 的唯一 group 被整体 quarantine。主 analysis population=2,831，分布 1190/1273/264/104；train/dev/test=1985/420/426，group-aware、无泄漏、并集完整；七个产物独立重放 byte-identical；sensitivity full-source variant 仅预注册未运行 |
| 3 | S2.1-B-R1 | **verified** | R1 合同与实现缺陷已修复并由后续真实数据与机器门禁回归保护 |
| 4 | S2.1-D / S2.1 | **verified / overall verified** | manifest 路径已项目相对化；独立 gate 交叉验证 ZIP、合同、schema、quarantine、records/splits、membership/artifact hash、ignore 与许可。records/split hash 未变；许可证据已复核但许可仍 unknown，formal Gold 与 final experiment 不解锁 |
| 5 | S2.2 | **verified annotation freeze**：用户完成 150/150；strict validator 与 deterministic receipt 锁定 150 approved English、900/900 resolved decisions、150 adjudicated、231 final clauses | annotation freeze 已完成；RWI-0001/RWI-0007 保持 open，进入 route/language/context QA 与 formal input/publication 重锁 |
| 6 | S2.3 | **verified**：`public_marker_lexicon_en_v1` 已离线锁定；64 个 marker、source/manifest/payload hash、空扩展表和机器门禁通过 | 来源、规则、语言、hash 与 dev-only 扩展策略固定 |
| 6.1 | S2.4-L / S2.4 | **verified / verified**：许可证据仍为 unknown；本地研究使用决定、Legal-BERT + TextCNN 配置、训练、dev 选择、唯一一次 test 评价、manifest/checkpoint 均已锁定 | `s24_legal_bert_textcnn_seed20260717_v1`：best epoch 5；test accuracy=0.924883、macro-F1=0.851071；不再分发数据 |
| 6.2 | S2.5 | **verified**：S2.5-A/B、外部 runtime 身份、12 patterns、六字段顺序和 7 live surgeries 全部通过 | 不再是 S2.6 blocker |
| 6.3 | S2.6 | **verified**：真实 checkpoint + attested extractor live output + canonical validator 组合通过；德文/英文双路由已修正并锁定 | v3 manifest 1 record/1 clause、schema invalid=0、cross-field invalid=0；synthetic only，不是性能评价 |
| 6.3a | S2.7-B0-DEV / S2.10 | **succeeded-development / strict + Sun Table 8 views verified** | 冻结 Layer E 只读适配为内存 Gold；150/150 immutable B0 attempts、schema-valid=100%、LLM/API=0。严格视图保留 clause alignment/token overlap；新增不要求 clause alignment 的 statement-level 同字段任意交集最大一对一视图。B0 Sun-view overall P/R=0.656333/0.702370，Action P/R=0.828571/0.821862。旧 attempts、Gold、RWI-0001/RWI-0007 与 formal publication 门禁均未改变 |
| 6.3b | EStG-150 candidate protocol C0/C1/C2 offline prep | **C0 verified；gpt-5.6-luna C1 passed；gpt-5.4-nano C1 failed closed；C2 offline prep frozen** | canonical serializer/fixture 不变。gpt-5.6-luna 为 1 valid candidate、1996 tokens、0.042987 CA；gpt-5.4-nano 为 0 valid candidate、2956 tokens、0.01728755 CA，exact-span 越界且无重试。C2 六个离线 request/preflight/hash 已锁定；evaluation=0、P/R=null、C2=false |
| 6.4 | S2.8 | **verified-offline** | H1 已重基到 verified B0；trigger、字段依赖 closure、strict merge、完整 Chat Completions 请求体、固定 gpt-4.1 快照、确定性分配、可计分 recovered-error 回退及 call/token/USD 预算由 v5 manifest 与机器门锁定；不是真实 LLM/性能运行 |
| 6.5 | G0.5 | **verified** | 文本/BPMN complexity profile、11/12 固定指标、low/medium/high 分层和禁止预测/结果泄漏已由 synthetic manifest 锁定 |
| 6.6 | S2.11 | **verified-input/protocol** | 官方 CELEX 32016R0679 Formex source 与 reuse 证据已锁定；Articles 5–50 解析 200 units，coverage-first 固定 50 条、覆盖 46 Articles，membership=`9a6a...28b9`；空白人工 Gold/schema/canonical adapter 通过，语义 Gold 仍 0/50 |
| 6.7 | S2.10-E | **strict v1.2 + Sun Table 8 comparison view verified / formal results blocked** | B0/H1/D1 future development 共享严格 v1.2 与 `sun_table8_compatible_v1`。后者以 statement 为单位、同字段任意非空字符交集、最大一对一匹配，Modality 只评 evidence span；6 项聚焦回归和 B0 150 条只读重算通过。它是在看到 B0 严格分数后由用户选择的论文同口径视图，不冒充预注册；没有正式性能比较 |
| 6.8 | S2.9 | **verified-offline** | v3 prompt 截断缺陷已修复为 v4；4 few-shot、dated model、5 repeats、750-call/37-USD 上限、0 retry 和失败保留由 synthetic manifest/exact-hash gate 锁定；真实 LLM 未授权 |
| 6.9 | S2.7-M | **modality component verified / overall partial** | 同一 1985/420/426 split 上 majority、German keyword、Multinomial NB 只保存聚合结果；已披露 1 次同配置未版本化 test smoke，无 test 选参；phrase/full Stage 2 仍等 route/language/context QA 与 formal input/Gold publication |
| 6.10 | S1.1/S1.2/S1.4 | **verified-offline structural** | Process Record v1、pool/lane/activity/event/gateway/flow、direct/reachable/order、branch/parallel/cycle/unreachable 均由 two-fixture v1 manifest 与 exact-hash gate 锁定；无正式 BPMN/Gold/性能评价 |
| 6.11 | S1.3 | **verified-offline P0/P1 label contract** | P0 raw-only/no inference；P1 单一 lane actor + fixed first-token/remainder surface split；6 个 edge cases、上游 Process Record hash、tamper rejection 与 exact-hash gate 已锁定；无 P2/Gold/性能评价 |
| 6.12 | S1.5 | **verified-offline blank annotation protocol** | 1 synthetic process、6 activities、18 label fields 全部 unreviewed/null；source/context/freeze fail-closed；正式 membership 由独立 GDPR7 gate 管理 |
| 6.13 | S1.6 | **verified-offline evaluator / formal results blocked** | exact membership；8 个 structure components；actor/action/object exact P/R/F1；triple accuracy；coverage 与 terminal/invalid 分母已锁；synthetic constants 不可作性能主张 |
| 6.14 | S1.5/S3.1 | **all-seven formal membership locked** | 用户批准后，从 Winter provenance byte-exact 提升 7 个 GDPR BPMN；文件/hash/claim 共锁，7 个唯一项目级 Process Record、45 activities、135 个空白人工字段通过门禁；Sun 原 4 文件名仍 unresolved，未生成 Gold/性能结果 |
| 7 | S2.7-S2.12 | 多 baseline、H1/D1、复杂语料和错误分析 | 同 IDs/Gold/evaluator 的完整比较 |
| 8 | S2.13 | 冻结 Stage 2 | 数据、方法、指标、成本、manifest 完整 |
| 9 | PW1 | **verified**：中文引言、RQ0–RQ4 与预期贡献初稿已完成；主张矩阵已同步 | 无结果性过度主张；Sun 原文三部分与项目 Stage 1/2/3 映射已明确区分 |
| 10 | PW2 | **verified**：Sun/Winter/Sleimi/Michel/Agostinelli/Barrientos 相关工作与边界已完成 | 文献主张已回到一手论文；不同任务、schema、代码身份和证据等级已分开 |
| 11 | PW3 | **verified**：统一合同与 B0/H1/D1 方法章节骨架 | 已验证、计划中和受门禁阻塞的组件已使用不同完成时态 |
| 12 | PW4 | **verified-current-draft**：官方 modality 数据、五层 Gold 与人工标注协议 | S2.1 统计已回填；S2.2 annotation receipt 已固定 150/900/231，formal Gold publication 表述待 route QA 后回填 |
| 13 | PW5 | **verified-design**：baseline、指标、统计与复现设计 | S2.10-E evaluator 与 S2.12-P 的 bootstrap/CI/randomization/Holm/error taxonomy 已在正式结果前冻结；formal runner 仍受门禁保护 |
| 14 | PW6 | **verified-template-only**：结果表格和作图模板 | 已建立 Stage 2/复杂度/Oracle/端到端/失败成本空表、图规范与 provenance 位；无数字 |
| 15 | PW7 | **blocked**：Stage 2 正式结果 | S2.2 annotation freeze 与 S2.4–S2.6 已完成；仍需 route/language/context QA、formal input/Gold publication、S2.7–S2.13 和对应 formal experiment manifests |

Stage 2 剩余正式任务的首个节点已转为 RWI-0001/RWI-0007 的 context/language 输入路线
闭合与 formal publication 重锁；不得从 annotation freeze 直接跳到方法运行。Stage 1
可自动完成的 membership、解析和空白审核输入已经闭合；Stage 3 的 all-seven membership
也已锁定，但其余工作仍等待 S1.7 与 S2.13。

## 5. 当前派工

| 角色 | 任务 | 状态 | 写入范围 | Prompt |
|---|---|---|---|---|
| 协调 Agent | 维护门禁、验收和日志 | in_progress | shared docs/log only | `docs/AGENT_RUNBOOK.md` §§1–3 |
| Agent-E1 | S2.1-A 官方数据来源证据 | **verified** (2026-07-15 字节级核验通过；B1 resolved) | `data/development/sun_modality/`、`docs/research/SUN_MODALITY_DATASET_INGESTION.md`、manifest、`scripts/verify_sun_modality_zip.py`、tests | §4.1 |
| 当前执行 Agent | S2.2 freeze receipt 与下一路由门禁 | **S2.2 verified；route QA in progress** | 维护 receipt/gate/docs；不得替用户修改 Layer E，不得绕过 RWI-0001/RWI-0007 或 formal publication gate | 下一步重锁 context/language/input route |
| Agent-P1 | PW1 引言与研究问题 | **verified** | `paper/THESIS_DRAFT.md`、主张矩阵 | 引言/RQ/预期贡献已形成可读初稿 |
| Agent-R1 | PW1 论文科学主张只读复核 | **verified** | 无写入 | 未发现 completed/formal/LLM 优势等越权主张；页码仍保留 TODO |
| Agent-P2 | PW2 相关工作 | **verified** | `paper/THESIS_DRAFT.md`、主张矩阵 | 一手来源、方法继承和 schema 边界已核验 |
| Agent-P3 | PW3 方法章节骨架 | **verified** | `paper/THESIS_DRAFT.md`、主张矩阵 | 已区分 verified implementation、planned method 与 blocker |
| Agent-P4 | PW4 数据与标注协议 | **verified-current-draft** | `paper/THESIS_DRAFT.md`、主张矩阵 | 已回填 S2.1 机器事实；未代填或推断 Layer E |
| Agent-P5 | PW5 评估与复现设计 | **verified-design** | `paper/THESIS_DRAFT.md`、主张矩阵 | S2.10-E evaluator 与 S2.12-P inference/error-analysis 参数已冻结；正式数字仍为空 |
| Agent-P6 | PW6 结果模板 | **verified-template-only** | `paper/THESIS_DRAFT.md`、主张矩阵 | 空表、图规范和 provenance 位已完成；未填任何数字 |
| Agent-P7 | PW7 Stage 2 正式结果 | blocked | 无写入 | 等待 route/language/context QA、formal input/Gold publication、S2.7–S2.13 和 formal manifests；S2.4/S2.6 仅解锁组件/技术验证主张 |
| 用户 | S2.2 Layer E 最终修改 | **complete：150 approved、900/900 resolved、150 adjudicated、231 clauses** | Layer E 已由 S2.2 receipt hash 冻结 | 后续如需修改必须视为新版本并重新出具 receipt；本批次不改人工决定 |

实验 Agent 默认串行；论文 Agent 可以与一个实验 Agent 并行，但不得编辑 shared
状态页。协调 Agent 在工作 Agent 交接后统一更新本页、Pipeline、catalog 和日志。

## 6. 当前禁止

- 不把旧 heuristic 产物或当前独立重建叫作 Sun 原始代码/exact reproduction；
- 不自动填写、修改或通过预测反推人工 Gold；
- 不运行真实 LLM/API，除非用户再次明确授权且预算、模型、prompt 已锁定；
- 不把 development 结果复制成 formal 结果；
- 不用不同 test IDs、Gold、schema 或 evaluator 制造 baseline 比较；
- 不新增第二份 pipeline、日期版 status 或 handoff；
- 不改动 `references/` 或根 `archive/`，也不恢复其中代码为活动实现。

## 7. 证据入口

- 文档地图：`docs/INDEX.md`
- 目录职责与逐文件清单：`docs/DIRECTORY_GUIDE.md`、`docs/FILE_CATALOG.md`
- 全实验实际问题与解决方法：`docs/REAL_WORLD_ISSUE_REGISTER.md`
- Sun 数据与最终版审计：`docs/research/SUN_FINAL_VERSION_AND_DATA_AUDIT.md`
- Sun modality 许可证据：`docs/research/SUN_OFFICIAL_LICENSE_RECORD.md`
- S2.3 public marker 重建：`docs/research/PUBLIC_MARKER_LEXICON_RECONSTRUCTION.md`
- Sun baseline 边界：`docs/research/SUN_BASELINE_AUDIT.md`
- Winter/Sun 代码分离：`docs/research/SUN_WINTER_CODE_SEPARATION_AUDIT.md`
- Barrientos 借用边界：`docs/research/BARRIENTOS_BORROWING_AUDIT_2026-07-12.md`
- 历史交接：`_retired/docs/2026-07/CURRENT_HANDOFF_2026-07-12.md`
- 追加式实验日志：`docs/EXPERIMENT_LOG.md`、`docs/EXPERIMENT_EVENTS.jsonl`
- Agent 派工与 Prompt：`docs/AGENT_RUNBOOK.md`
- 论文工作稿与主张矩阵：`paper/THESIS_DRAFT.md`、`paper/CLAIM_EVIDENCE_MATRIX.md`
