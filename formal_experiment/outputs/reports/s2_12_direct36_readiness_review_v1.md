# S2.12 Direct-36 零调用就绪核验报告 v1

- 报告日期：2026-09-19
- 范围：SEP-C2 / S2.12 复杂语料 Rules-Only 与 Direct-LLM 两方法合同下的 Direct-36 执行准备
- 本轮真实 LLM/API 调用：0；网络调用：0；未执行 Direct-36，未运行新 prompt 实验
- 结论：**BLOCKED（不能进入真实执行准备完成态）**；执行对象和验收设计基本锁定，但 successor 两方法授权、总输入 token 与 USD 硬上限、当前价格复核及外部发送审批未满足
- 性质：证据/就绪核验报告，不是新的项目状态页；不修改代码、Gold、prompt、评价器、正式配置或授权文件

## 0. 核验依据

本报告只使用当前工作树中的合同、预检、授权事件、账本路径、runner/evaluator 代码和只读哈希核对，不读取 `.env`，不打印凭据，不构造真实传输。

关键绑定：

| 对象 | 路径 | SHA-256 / 结果 |
|---|---|---|
| S2.12 输入 | `data/input/s2_12_complex_corpus_formal_input_v1.json` | `892d4284ea70c38f82a47f821c13622f1b07744253429e466038ddb5db96660e`；36 条唯一 ID |
| Direct prompt v6 | `prompts/sun_compat/direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md` | `3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895` |
| 活动方法范围 | `configs/s2_12_active_method_scope_v1.json` | `47c13f8160b3062e115d1b9867e99acf35cf505ca86c5a5594c1542ff55354e0` |
| 活动 Direct 预检 lock | `configs/s2_12_active_preflight_v2.json` | `5c495839ef292d1c6ec083184941e5f2ebb7d8bba656ba377dd75da686388663` |
| 活动 Direct 预检 report | `outputs/reports/s2_12_active_preflight_v2.json` | `cbec18d103b3c151ccd3225588f9998bbf001cb555473bded970803063aca764`；36 个 payload |
| 两方法合同 | `outputs/reports/s2_12_two_method_contract_v1.json` | `61d23a39c2fa2d27bd33af28acd0f26328fcb6b904a2fecc6dd960b289f3096f` |
| 冻结 S2.11 Gold | `data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json` | `039ae8b2429826ae2b320667fb4a0dff96de6408b0a9637c1d9911565129c804`；36 条 |
| Gold manifest | `outputs/reports/s2_11_formal_gold_v1.manifest.json` | `12ab299d98468401745fe300cb8bbf9c0fd91c4ca9b295fb6a57fcb4446d2101` |
| evaluator v2 合同 | `configs/stage2_evaluator_s210_v3.json` | `28ce332564c5d10da08dea515aefe31cc2aacd91b6c6877aa1bfebe44f39ae7f` |
| 分层来源 | `outputs/reports/s2_11_proposal_report_v3.json` | `0cd725b4e7e14c88a97ca005ec10dac3f7fc77c2ebf3955eb746abdc9479616a` |
| 模型 registry | `configs/models/estg150_d1_active_registry_v1.json` | `31f3358d089611b85a4a50d36444a4c59f6d965abbf0b8770aeb73db13642749` |
| Rules-Only 预测 | `data/predictions/s2_12_sun_rule_only_v1/predictions.json` | `f1e88ac5167ec1d3f0644dfcbeac60ead18932f766231baf3cb8e86b4af77006`；36 条 |
| Rules-Only 评价 | `data/results/s2_12_sun_rule_only_v1/evaluation.json` | `1696dbf9dcf85ef30f6056fc109c9952f0465ac21ac080314e57f7fa33799e16` |

预检状态为 `locked_two_method_without_api_authorization`；预检报告状态为 `payloads_locked_two_method_no_api_authorization`。两者均明确 `real_api_calls_authorized=false`，且报告记录 `llm_api_calls=0`、`network_calls=0`。


## 1. 真实缺口是什么

### 1.1 Rules-Only 是否已有完整、可验证的 36 条结果

有。Rules-Only 臂是零 API 臂，当前证据完整：

- 预测目录 `data/predictions/s2_12_sun_rule_only_v1/` 的 predictions、manifest、telemetry、cost 均存在；预测 SHA-256 为 `f1e88ac5167ec1d3f0644dfcbeac60ead18932f766231baf3cb8e86b4af77006`。
- 评价目录 `data/results/s2_12_sun_rule_only_v1/` 的 evaluation 与 manifest 均存在；评价 SHA-256 为 `1696dbf9dcf85ef30f6056fc109c9952f0465ac21ac080314e57f7fa33799e16`。
- 两方法合同中的 `comparison.evidence.sun_rule_only` 记录 `verified=true`、`input_binding_ok=true`、`all_36_rows=true`、`prediction_row_ids=36`、`metrics_valid=true`。
- 预测行 ID 与输入、Gold、Direct 预检的 36 个 sample_id 完全一致，无缺失、无重复。

### 1.2 Direct 是否存在 raw、部分预测、失败记录或 in_doubt 调用

在当前工作树、已提交文档、`EXPERIMENT_EVENTS.jsonl`、预期 raw/ledger 路径和所有可读 `*.ledger.jsonl` 中，没有找到 S2.12 Direct-36 的真实 raw、部分预测、失败记录、in_doubt 记录或已完成调用账本。

- 预期 raw 目录 `outputs/development/s2_12_direct_llm_raw_dcal_v1`、`outputs/development/s2_12_direct_llm_raw_drest_v1` 不存在。
- 预期 live ledger `outputs/development/s2_12_direct_llm_stage_dcal_v1.ledger.jsonl`、`outputs/development/s2_12_direct_llm_stage_drest_v1.ledger.jsonl` 不存在。
- 预期 stage capsule `outputs/development/s2_12_direct_llm_stage_dcal_v1`、`outputs/development/s2_12_direct_llm_stage_drest_v1` 不存在。
- `data/predictions/s2_12_direct_llm_v1` 与 `data/results/s2_12_direct_llm_v1` 不存在。
- 历史记录中 D-CAL 第一条发送曾在创建进程前被自动审批阻止；该次为 0 发送、0 费用、未重试，不是已消耗调用。
- 本核验没有仅凭最终输出目录不存在下结论；同时检查了预检/合同中的 `s2_12_direct_real_calls_observed=null`、`call_plan.s2_12_direct_completed_observed=0`、旧授权文件、runner 代码中的 ledger 路径和已记录的 experiment events。

边界：当前证据支持的结论是当前工作树和可核验记录中没有发现 Direct-36 已发送的持久化记录，不能扩展为绝对证明过去任何进程从未尝试过传输；因此实际执行前仍须以新授权和空/合法账本进行 fail-closed 启动检查。

### 1.3 哪些记录可以复用，哪些绝不能自动重发

可以复用（只读）：

- 36 条冻结输入、S2.11 冻结 Gold、evaluator v2、分层来源。
- Rules-Only 36 条预测与评价，用于两方法比较的既有零 API 臂。
- 活动预检中已经 locked 的 36 个 Direct 请求体/hash/采样参数；这是请求级复用，不是响应复用。
- 两方法合同、预检 lock/report 和输出路径定义。

不能复用为 S2.12 Direct-36 正式预测：

- `data/predictions/direct_llm_formal_arm_v1` 是 EStG-150 的另一任务/数据集，不是 S2.12 复杂语料 36 条。
- Barrientos D/E 1140-call、D1/C3 prompt 消融、GDPR fake 74 条等历史 raw/predictions，模型、prompt、输入或协议不同，不能填入 Direct-36。
- 旧 137 次授权范围及其 D-CAL/D-REST 文件绑定旧 runner 和已取消 `sun_llm_fallback`，不能作为当前两方法 Direct-36 授权。

绝不能自动重发：

- 任何未来账本中状态为 `completed`、`in_doubt`、`usage_missing`、`transport_error` 或等价终态的 payload；重试政策为 0，失败/未知必须落账并中止。
- 旧 D-CAL 被审批阻止的尝试也不自动重发；恢复执行必须由新的明确授权和新的执行条件驱动。

## 2. 执行对象是否锁定

结论：输入、prompt、模型、Gold/evaluator 锁定通过；当前活动预检锁定 36 个请求体；未把 v6 换成研究候选 B。

- 36 条 `sample_id` 在输入、Gold、Rules-Only 预测和 Direct 预检 `calls` 中四者一致；每条唯一，无重复。
- 输入 SHA-256 `892d...660e`；Direct prompt SHA-256 `3aa64877...e895`；模型 registry SHA-256 `31f3358d...2749`。
- 模型为 `deepseek-v4-pro`，登记 release `DeepSeek-V4-Pro-0813`；预检 fail-closed 要求 returned_model 匹配；temperature=0、top_p=1、max_output_tokens=4096、retry=0、stream=false、thinking.type=disabled。
- 活动预检报告含 36 个 direct calls，D-CAL 取第 1 条、D-REST 取第 2-36 条；请求体最大 17,493 UTF-8 bytes、总计 626,848 bytes；本地 proxy token 总计 177,967（非 DeepSeek billing token）。
- Gold 为已发布 S2.11 complex corpus formal Gold，SHA-256 `039ae8...c804`；evaluator v2 合同 SHA-256 `28ce33...ae7f`；分层来源 `s2_11_proposal_report_v3.json` SHA-256 `0cd725...616a`。evaluator 模块在预测 capsule 锁定后才读取这些绑定。
- 合同绑定的是当前 Direct prompt v6 及当前活动预检，不是研究候选 B；B 只保留为 SEP-C3 研究参照，不得替换本轮 S2.12 Direct-36。


## 3. 授权是否适用

结论：**不通过。当前没有适用于两方法 Direct-36 的实际授权记录。**

已核查的现有授权文件：

- `configs/s2_12_api_authorization_D-CAL.json` 与 `configs/s2_12_api_authorization_D-REST.json` 存在，事件文件也存在；它们记录 `direct_llm:36 + sun_llm_fallback:27`、D-CAL cap 1、D-REST cap 35、`off_peak_only`、价格快照 `2026-08-22`，并绑定旧 runner 哈希（例如 `run_s2_12_direct_llm_v1=57c7cb9b...`）。
- 这些文件属于旧 137 次三方法范围；包含已取消的 27 次 Rules+LLM-Repair 预算，且旧 runner/锁版本已与当前活动实现不同。
- 活动 scope `configs/s2_12_active_method_scope_v1.json` 明确记录旧 137 次范围已被取代、27 次取消预算不得挪用、当前取消不构成外部发送授权。
- `configs/s2_12_active_preflight_v2.json` 要求 `real_api_calls_allowed_by_this_lock=false`；活动 report 要求 `real_api_calls_authorized=false`。
- 当前没有 `s2_12_api_authorization@2.0.0` successor 文件，也没有按活动 scope 重新签发的授权事件。runner 的 active 路径会拒绝旧 v1.1.0 授权。
- 进程环境里存在密钥或临时非秘密配置的既有离线记录，不等于调用许可；本报告没有读取或打印凭据值。

因此旧 D-CAL/D-REST 授权不能复用，当前唯一合理状态是等待用户/授权方重新签发两方法 Direct-36 授权事件。GDPR-74 授权是另一独立范围，不并入本次最小任务。

## 4. 调用与成本边界是否清楚

结论：**部分清楚，整体不足以执行。**

已清楚：

- 调用结构：D-CAL 1 次 + D-REST 35 次，合计最多 36 次。
- 已发送数量：当前可核验证据为 0；剩余最多发送 36 次。
- 重试：0 次；runner 对 transport_error、usage_missing、失败/未知响应立即落账并中止，不自动重发。
- 调用上限：活动预检配置 36 次硬上限；请求体最大 17,493 bytes/call、总 626,848 bytes；output cap 4,096 tokens/call、总 147,456 tokens。
- 输出路径：raw 为 `outputs/development/s2_12_direct_llm_raw_dcal_v1` 和 `..._drest_v1`；live ledger 为 `outputs/development/s2_12_direct_llm_stage_dcal_v1.ledger.jsonl` 和 `..._stage_drest_v1.ledger.jsonl`；stage capsule 为对应 `_stage_dcal_v1` / `_stage_drest_v1`；最终预测为 `data/predictions/s2_12_direct_llm_v1`；最终评价为 `data/results/s2_12_direct_llm_v1`。
- 失败中止条件：模型或 returned_model 不匹配、输入/prompt/config/payload/hash 漂移、调用/输出/USD cap 将超限、Gold/decision/proposal/Oracle 可见、价格不能核验、重试不为 0、已取消修复组进入等都会 fail-closed。
- 时间窗口：D-CAL 在当前 stage contract 中强制 off-peak；D-REST 必须由 successor 授权明确 `allowed_windows`，当前活动 lock 未给出该字段。

未清楚/未满足：

- 总 billed input-token cap 未给。
- 总 USD cost cap 未给。
- 活动预检的 `pricing.planning_only=true`，来源是旧价格快照；不能把过期价格当作已核实的当前价格。执行前必须联网重核官方价格和峰谷时段；本轮没有联网，因此未核实。
- 外部发送审批阻塞未解除；历史 D-CAL 第一条请求在创建进程前被自动审批拒绝，文件内历史授权未被审批系统接受。
- 旧授权的 63M input tokens、258,048 output tokens、USD 1.00/42.09 等上限属于旧三方法范围，不能挪用为当前两方法 Direct-36 的 successor 授权。


## 5. 真正执行后应如何验收

设计层面已经明确，当前只是无数据可验：

- 预测总体固定为 36 条；失败、in_doubt、usage_missing 等记录不得删除，必须保留在分母中。
- finalize 将非 ok 行编码为空 canonical record，评价器 `_evaluation_attempts` 保留全部 36 行并设置 `success_only_subset_used=false`。
- 预测在 Gold 评价前锁定；评价器校验 prediction capsule manifest、artifact hash/size、`prediction_locked_before_gold_evaluation`、Gold SHA、分层来源 SHA、evaluator v2 模块合同。
- 评价输出 `data/results/s2_12_direct_llm_v1/evaluation.json` 与 manifest，独立 verifier 重放并检查固定 36 行总体、失败保留、prediction lock、Gold/evaluator/track 绑定和实现哈希。
- 完成后进入 S2.13 检查时，仍须满足两方法完整证据链和其他既有冻结条件；不得因为 Direct-36 跑完就自动宣布 SEP-C2/S2.13 正式冻结完成。
- GDPR-74 是 S2.12 Direct-36 之外的独立范围；若下游 GDPR Direct-LLM 比较主张仍需要真实证据，则它不能被笼统当作可选增强，但也不是本轮 Direct-36 的执行前置。

## 6. Direct-36 就绪表

| 项目 | 状态 | 依据 |
|---|---|---|
| 输入 36 条 | 通过 | 输入、Gold、Rules-Only、预检四者 sample_id 一致；每者 36 唯一；输入 SHA `892d...660e` |
| prompt | 通过 | Direct prompt v6 SHA `3aa64877...e895`；活动预检与 registry 指向同一版本；未切换研究候选 B |
| 模型 | 通过 | `deepseek-v4-pro` / `DeepSeek-V4-Pro-0813`；fail-closed returned_model 检查；temp=0、top_p=1、max_tokens=4096、retry=0、stream=false、thinking disabled |
| Gold/evaluator | 通过 | Gold SHA `039ae8...c804`；Gold manifest `12ab...`；evaluator v2 合同 `28ce33...`；分层来源 `0cd725...`；evaluation script 常量与磁盘一致 |
| 账本 | 不通过/缺失 | 预期 D-CAL/D-REST raw、live ledger、stage capsule、predictions、results 均不存在；未发现可复用的 Direct raw/partial/failed/in_doubt 记录；历史 D-CAL 首条被外部审批阻止，发送 0 |
| 授权 | 不通过 | 当前无 successor `s2_12_api_authorization@2.0.0`；旧 D-CAL/D-REST 为旧 137 三方法范围，绑定旧 runner 和已取消 fallback，不能复用；活动 report/lock 明确未授权 |
| 预算 | 不通过 | 调用数/重试/output cap/请求体字节上限清楚；但总 billed input-token cap、total USD cap 缺失；价格仅 planning snapshot，需执行前联网复核；时间窗口 D-REST 未在 active lock 中明确 |
| 输出 | 通过（定义） | raw、ledger、stage capsule、predictions、results 路径均已定义，runner 拒绝覆盖既有输出；当前无输出用于验证 |
| 验收 | 通过（设计） | 固定 36 分母、失败保留、predictions 先锁定后读 Gold、evaluator v2、独立 verifier；完成后再按 S2.13 其余条件检查，不自动宣布冻结 |
| 进程环境 | 未核实 | 历史报告记录凭据前置曾在离线检查中出现，但本轮不读 `.env`/密钥；远程认证未独立测试；即使凭据存在也不构成调用许可 |

**总体判定：BLOCKED。** 这不是对 SEP-C3 或其他实验的完成声明，也不是授权；本轮没有执行 Direct-36。

## 7. 精确阻塞

1. **缺 successor 两方法 Direct-36 授权事件。** 影响：runner 在构造 transport/发送前拒绝执行。可离线解决：否（需要用户/授权方重新签发精确授权句和授权事件）。需要谁做：用户或授权负责人核对 `configs/s2_12_active_method_scope_v1.json`、`configs/s2_12_active_preflight_v2.json`、当前 runner 哈希和 36 payload 后签发。
2. **缺总 billed input-token cap 与 total USD cost cap。** 影响：runner 无法通过 active authorization 校验，也无法验证预算边界。可离线解决：部分可以（用户给出 caps），但当前价格必须重新联网核验。需要谁做：用户/执行负责人给出两个硬上限，并重新核验 DeepSeek 官方价格与峰谷时段；无法联网时不能把旧价格当当前价格。
3. **外部发送审批阻塞未解除。** 影响：历史 D-CAL 第一条在创建进程前即被拒绝；即使文件授权存在也可能无法真实发送。可离线解决：否。需要谁做：当前任务/审批机制明确确认目的地、模型、数据范围和 36 条锁定文本。
4. **远程认证未独立测试。** 影响：授权和预算满足后，实际 transport 可能仍失败；不是当前首要阻塞，但执行前必须做一次不打印秘密的安全连通性/配置检查。可离线解决：可以只读检查环境变量名和非秘密配置，但不能验证远端。需要谁做：执行操作者。
5. **GDPR-74 的依赖不是 S2.12 Direct-36 阻塞。** 影响：不阻塞本轮 36 条；如果论文下游 GDPR Direct-LLM 比较主张仍依赖真实 74 条证据，则它是该下游主张的必要缺口，不能作为可选增强删除。需要谁做：按该主张的依赖单独安排授权与预算，不并入本轮最小任务。

## 8. 安全与备份

- 本轮新增真实 LLM/API 调用=0；网络调用=0；未执行 Direct-36。
- 未修改实验代码、Gold、prompt、评价器、正式配置或授权文件。
- 本报告和 SEP-C3 文档纠正按文档/只读核验范围提交；不运行全量测试和项目审计。
- 当前旧的 S2.12 Direct 账本/raw/in_doubt 证据不存在；历史 D-CAL 审批阻止记录仍是 blocker，不应被隐藏或冒充为 success。
