# EStG-150 原始候选生成协议：canonical external v1 + strict transport v1.1

## 1. 状态与边界

本规范是 EStG-150 后续中转站、DeepSeek、Qwen 与 xAI 官方 Grok 调用的唯一候选
协议入口。C0 已完成离线锁定。C1 先完成一次获授权的七模型 transport 兼容性矩阵，随后
ChatAnywhere `gpt-5.6-luna` 在新授权下完成单条 strict transport v1.1 runtime 并生成一个
canonical-valid 候选。没有评测/P/R。C2 的六请求离线准备随后冻结；真实 C2 在独立授权下
启动，但第一个 Pass A 因 `finish_reason=length` fail closed，其余五条未调用，C2 未完成，
C3–C4 尚未开始。

2026-07-26 已完成只针对请求进入模型前兼容性的版本化修复：canonical v1 schema、prompt、
messages、synthetic、serializer 和 semantic fixture 均保持原字节；另建
`estg150_openai_strict_transport_schema_adapter@1.1.0`，只在 ChatAnywhere 三个现代
profile 的 transport body 中给 6 个字符串 const/enum 节点补显式 `type:string`。递归
Structured Outputs 预检和七模型 capability preflight 均在 run 目录、API key 和网络之前
执行。随后在新的明确授权下，ChatAnywhere `gpt-5.6-luna` 单条 synthetic 生成 1 个候选，
并通过原始 canonical schema、exact span 和 normative-cue coverage 验证；0 retry，provider
usage 为 1167 input + 829 output = 1996 tokens，记录费用 0.042987 CA。因此 **C1 已通过**。
后续 C2 首条真实 Pass A 失败不撤销 C1，但 C2 没有形成冻结候选；evaluation 未开始，P/R
仍为 null。relay 报告的具体模型身份未独立验证。

历史内置 Sol 运行保存了 A/B/C、membership、三份 prompt、output schema、样本分流、
最终候选与聚合 manifest，但没有保存 Codex 内部隐藏 system prompt 或 API envelope。
因此机器合同如实记录：

```text
historical_hidden_transport_payload_not_archived=true
```

`estg150_canonical_external_candidate_protocol@1.0.0` 只复现可核验的历史可见资产与
分流，并从现在起冻结统一的外部 serializer。不得将它表述为隐藏 Codex transport 的
exact reproduction。

## 2. 锁定资产

| 资产 | SHA-256 |
|---|---|
| membership payload | `8573e105d2bc167c6aa0a92c16f79a3aaf725baadfea86f0b5d2b1ea68b1e0d7` |
| Layer A | `55b64598dedfa0c0038084ee62c0928bddfa4bf17f19db80d461da2cb7bf26a3` |
| Layer B | `f65e929bf1fe498ffce6f08d30f95d1c4de53592457352cce915cfbf8ee91da3` |
| Layer C | `9476945ca387fb7efad5c1405cca59a6ef24ff50a23e22ba2c46ad6847290b8b` |
| canonical v1 output schema | `fbbb628ad0f25639958c6d02db9bac90ed06865e634bd4e8eeb7b50ac7108ca9` |
| OpenAI strict transport schema v1.1 | `ef8c684b2456196eac14cc7748bb687aef5ef32fd8a405c3003bd831ad380af7` |
| full extraction prompt | `9ad65ce8921d76afc3cc3bfe50b1c2f447cae8155cc40041fc32d60f6a63ae0b` |
| Pass A prompt | `9d6127e3457c05d96d52d339701e41d104b11f1128a98853a4a24b650c4d1fec` |
| Pass B prompt | `3ff3c8fd4e22c62ed5e0fedb656a3c290c64e5969b1cc85faea61008449e9fcd` |

代码逐字节读取 canonical 活动文件并在反序列化前核验 hash；prompt 没有复制、改写、
补例或按 provider 分叉。transport schema 不是第二个输出语义来源：加载器从 canonical
对象深拷贝并只执行锁定的 6 个 `type:string` addition，再要求结果与版本化 transport
schema 完全相等；模型输出始终回到 canonical schema 做本地验证。

## 3. 唯一 serializer

serializer 版本为 `estg150_canonical_external_serializer@1.0.0`：

- 消息固定为 `system → developer → user`；system 是固定的 provider-neutral 执行边界，
  developer 是当前 route 的原 prompt 全字节 UTF-8 文本，user 是固定字段顺序的紧凑
  JSON；
- canonical schema 原文仍作为 semantic request 的 `output_schema_text` 保存，字节和
  semantic hash 不变；transport adapter 只替换出站 `response_format` 内的 schema 副本，
  不删除 `$schema`/`$id`，也不改变输出对象的
  `schema_version=estg150_ai_review_model_output@1.0.0`；
- JSON 使用 insertion order、`ensure_ascii=false`、分隔符 `,`/`:`、UTF-8、末尾 LF，
  不做 Unicode 或换行归一化；
- schema、响应提取、exact `[start,end)` span、ID/关系、obvious normative cue coverage
  和禁止内容修复都属于同一 semantic request；
- serializer identity SHA-256：
  `d20ae560a627c4d3faa88439908c517e7726aabb1121128af7b9013f5512edef`；
- 合成 UTF-8/换行 fixture SHA-256：
  `eb074081cc52d22025e263e3f94b2165f95493f511ddc454b9ea5f5923c085e1`；
- config SHA-256：
  `e10c7df222a8a3880fa8cdd11c29a03e606808fa7449d4f91970ce15ae414706`。

## 4. 历史分流与可见字段

sample 顺序严格使用 Layer A 文件字节顺序，再按 `legacy_record_id` 连接 B，并按
`sample_id` 连接 C。

- 索引 0–2：Pass A 只能看到 `sample_id/raw_text_de/frozen_candidate_text_en`；
  Pass B 看到这三个字段、完整且已验证的 Pass-A 输出、以及 Layer C 的冻结六要素
  projection。每条恰好两次内容调用。
- 索引 3–149：每条恰好一次 `full_extract`；看到 A/B 与同条 Layer C projection，
  不得增加修复轮。
- All-150 固定逻辑调用数为 `3×2 + 147×1 = 153`。

Layer D、Layer E、Gold、Gold 派生错误、Independent-82、S2.4 test 与 sample 特例表没有
loader、字段或 CLI 入口，生成期不可见。评测仍是输出全部完成并冻结后的独立阶段。

## 5. Adapter 与失败语义

唯一 runner 内含 `relay_openai_compatible`、`deepseek_official`、`qwen_official`、
`xai_official` 四个 adapter。它们只能改变 endpoint、鉴权、model ID、provider 必需的
外层 envelope 与响应外层解析；semantic request 不含 provider/model，因而同一输入的
semantic bytes 完全一致。

所有 adapter 都必须接受 strict schema、三角色消息、固定 high reasoning 字段与同一
输出 token 上限。provider 拒绝任何一项时写 `protocol_incompatible`，不得删字段、改
prompt、转自由文本或用 LLM/规则修 JSON。只有 network disconnect/timeout、HTTP 429 和明确的 5xx 可在
固定上限内重发完全相同的 request bytes；内容/schema/span 失败不重试。

v1.1 capability allowlist 恰好锁定已观察的 7 个 provider/endpoint/model 组合：

- ChatAnywhere `gpt-5.6-luna`、`gpt-5.4-nano` 为 strict transport schema
  `offline_ready`；`gpt-5-nano` 仅为
  `offline_request_ready_runtime_503_unresolved`，不把 503 写成 schema 成功；
- `gpt-4.1-nano` 因 `reasoning_effort` 不兼容而在发送前停止；`gpt-4o` 的既有断连不能
  证明参数接受，如需删除 reasoning 字段，必须另建并由用户明确批准版本化 provider
  profile，本版不启用；
- `gpt-3.5-turbo` 标为 canonical protocol incompatible，不得用 `json_object` 冒充 strict
  Structured Outputs；
- official `deepseek-v4-pro` 因 `developer` role 和 strict response-format 能力不兼容而
  在发送前停止，不合并消息、不降级 `json_object`、不用 tool call 替代。

终态 HTTP 错误最多读取并原样保存 1 MiB provider response body；`failure.json` 同时记录
HTTP status、保存字节数/hash、是否截断、白名单 request ID 与先前 retry reasons。若正文
回显实际 API key，则正文不落盘。此诊断路径不解析或修复内容，也不改变任何出站 request
bytes。早期两次 C1 在该诊断加入前运行，其 HTTP body 未保存，故不得倒推单一失败字段。

中转 adapter 的身份一律记录
`provider_identity_attestation=unverified_relay_report`，不得把中转声称的模型写成
官方 OpenAI 身份。官方 adapter 还会校验官方 endpoint host，但 provider 返回的 model
仍作为 report 保存，不替代用户预注册的 model ID。

## 6. 输出与 preregistration

每次真实调用必须使用新的不可覆盖 `run_id`，并在取得密钥和发送请求前写入固定
preregistration。模板为 `configs/estg150_candidate_preregistration_template_v1.json`。
运行保存：sanitized endpoint host、canonical protocol/schema path+SHA、transport adapter
ID/version/config SHA、transport schema path+SHA、canonical serializer SHA、逐请求 semantic
与实际 transport bytes/hash、capability/profile/preflight、是否发生请求降级、成功时的原始
响应/hash、provider reported model、usage、retry、canonical 本地验证、cost、
API/Layer-D/Layer-E/Gold 声明、generation 完成时间和空的 evaluation 开始时间；终态 HTTP
失败另保存上述限长原始错误正文与诊断 metadata。没有有效候选或独立 evaluation 时，
`precision`/`recall` 必须保持 JSON `null`，不能写 0。

历史 ChatAnywhere 专用 `run_estg150_ai_review.py` 的真实执行已经 fail closed 退役，只
保留历史 helper 与回归测试。唯一活动命令是：

```powershell
python formal_experiment/scripts/run_estg150_candidate_protocol.py --stage c0
```

该命令只做离线 hash/fixture/dry-run，不创建 run 目录、不读取密钥、不调用网络。

## 7. C1–C4 门禁

- C1：每个获得单独预算授权的 model 恰好一条 synthetic、一次逻辑内容调用，只验
  transport/model/schema/UTF-8；网络 429/5xx/timeout 可在锁定上限内重发相同 bytes；
- C2：只跑索引 0–2，恰好 6 次内容调用；
- C3：DeepSeek 或 Qwen，同一 runner 的一次 All-150 development run；
- C4：xAI 官方 endpoint + 用户提供的官方 model ID，一次 All-150；formal-ready 为 false
  时只能称 development/provisional。

任何真实调用都必须先有一条同时明确 provider/model、最大调用数、最大总 token 和最大
费用/币种的用户授权。没有该授权时停在 API 前。

### 7.1 2026-07-25 C1 transport 兼容性矩阵

| Provider / model | 终态 | 首个可证实的不兼容点 |
|---|---|---|
| ChatAnywhere `gpt-5.6-luna` | HTTP 400 | strict `response_format` schema 中 `properties.schema_version` 只有 `const`、缺显式 `type` |
| ChatAnywhere `gpt-5.4-nano` | HTTP 400 | 与 5.6-luna 相同的 schema strict-subset 错误，error body hash 也相同 |
| ChatAnywhere `gpt-5-nano` | HTTP 503，2 次 retry 后停止 | 中转未返回模型结果；无法判断 schema 兼容性 |
| ChatAnywhere `gpt-4.1-nano` | HTTP 400 | 不识别 `reasoning_effort` request argument |
| ChatAnywhere `gpt-4o` | 无 HTTP response 的断连 | 无法判断 schema；该 run 暴露并触发 RWI-0024 transport 分类修复，但未获额外重跑授权 |
| ChatAnywhere `gpt-3.5-turbo` | HTTP 400 | 不识别 `reasoning_effort` request argument |
| DeepSeek official `deepseek-v4-pro` | HTTP 400 | `messages[1].role=developer` 不在 endpoint 接受的角色集合中 |

机器汇总为
`data/development/estg/llm_candidate_runs/c1_transport_compatibility_matrix_20260725_v1/manifest.json`。
七个 logical request、2 个相同字节 transport retry、0 个有效候选、0 次 evaluation；provider
未报告 usage，实际账单增量未由本项目观测，因此不得把失败调用写成零成本。上述均为 API
参数/Schema/relay transport 结果，没有观察到模型内容安全拒答。canonical v1 按约定 fail
closed，未为任何 provider 删除字段或改写 schema。

在该 manifest 冻结后，用户另行核对供应商后台并确认七次逻辑调用的 token 用量为 0、余额
变化为 0、未计费；这是用户后台确认，不改写旧 provider-response manifest。它只支持
`billed tokens=0`，不产生候选或 evaluation，因而 P/R 仍必须为 `null`。

### 7.2 2026-07-26 strict transport v1.1 离线修复

canonical schema 的递归预检首错固定为
`$.properties.schema_version: const/enum schema requires a determinable explicit type`。派生 schema
只在以下 6 个 JSON Pointer 增加 `type:string`：

1. `/properties/schema_version`
2. `/properties/context_sufficiency`
3. `/properties/translation/properties/decision`
4. `/$defs/modality/properties/label`
5. `/properties/confidence`
6. `/$defs/ambiguity/properties/field`

adapter 预检确认根为 object、根无 `anyOf`、每个 object 的 properties 与 required 完全相等、
`additionalProperties=false`、const/enum 有显式可确定类型，并递归处理本地 `$ref`、合法嵌套
`anyOf`、`minLength`、`minimum`、`minItems`。gpt-5.6-luna C1 dry-run 的 canonical semantic
SHA 仍为 `eb074081cc52d22025e263e3f94b2165f95493f511ddc454b9ea5f5923c085e1`，新 transport
request SHA 为 `ac24297d027074b147bc41ddc08bbbaa55b232be337838a6d6180aa47fbc282f`；二者明确分开，
修复后请求不得冒充原始 v1 transport。该 dry-run 没有读取 API key、没有发网络请求、没有
产生候选或账单；它只证明了发网前状态，后续真实验证单独记录如下。

### 7.3 2026-07-26 gpt-5.6-luna 单条 C1 runtime

用户明确授权 ChatAnywhere `gpt-5.6-luna` 仅调用 1 条 synthetic，最大总 token 13,000、
最大费用 0.32 CA，验证后停止且不得自动进入 C2。冻结运行目录为
`data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_strict_v1_1_pilot_v1/`。

唯一 transport request SHA 保持 dry-run 预注册值
`ac24297d027074b147bc41ddc08bbbaa55b232be337838a6d6180aa47fbc282f`。provider 返回
`finish_reason=stop`，无 retry；报告模型为 `gpt-5.6-luna-2026-07-09`，但该身份只属于
`unverified_relay_report`。候选通过原始 canonical schema、exact half-open spans、关系引用与
normative-cue coverage 验证。usage 为 1167 input、829 output（其中 reasoning 512）、总计
1996 tokens；按授权命令锁定的输入/输出价格 7/42 CA per million tokens 计算并记录
0.042987 CA，低于 0.32 CA 上限。

运行 manifest 为 `succeeded_frozen`、candidate_count=1、C1 passed=true；没有读取 Layer D/E/
Gold，没有 evaluation，precision/recall 仍为 null，C2 started=false。该成功只解锁“C1 transport
兼容性已验证”的表述，不授权 C2–C4，也不补全历史隐藏 Codex transport provenance。

### 7.4 2026-07-26 C2 六请求离线准备

在没有扩展 C1 API 授权的前提下，C2 仅完成离线 dry-run。冻结目录为
`data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/`；
该 ID 只标识不可覆盖的离线收据，未来真实 C2 必须使用新的 run ID 和新的明确授权。

固定索引 0、1、2，分别生成 Pass A 与 Pass B 的六份离线 transport bytes。全部通过
`estg150_chatanywhere_modern_strict_profile@1.0.0` 与递归 strict transport preflight，且
`request_downgrade_applied=false`：

| 顺序 | sample | route | transport request SHA-256 | 锁定范围 |
|---:|---|---|---|---|
| 1 | `estg_000080` | Pass A | `9add2487dd36233b3e258ae451a27cebaa5de6b10de70a18b08ef7d527960aac` | 同一锁定输入/model/profile 的 exact bytes |
| 2 | `estg_000080` | Pass B | `77f44523a16a8dd2024d6dd95029d9de018533c44c67b9a80e9372c0a9cce511` | 仅离线 validated historical Pass-A fixture |
| 3 | `estg_000070` | Pass A | `2db4e6b17f1fa229a821fdd7dba14ed686bf9e946041f2b5ae6e8cc466628e91` | 同一锁定输入/model/profile 的 exact bytes |
| 4 | `estg_000070` | Pass B | `4bc0054766bc521e9f488fb3fc78581630ae3f572641d3ab63384999fb6b394e` | 仅离线 validated historical Pass-A fixture |
| 5 | `estg_000062` | Pass A | `5d5391d63d1e332af6828eb2a1955e4f68ada9791e51f1bf1ad4b048ad4f4498` | 同一锁定输入/model/profile 的 exact bytes |
| 6 | `estg_000062` | Pass B | `e13252e3948130c4ceb07c01491074d72a6809b8bc5a59eca2c76fbd790b6040` | 仅离线 validated historical Pass-A fixture |

Pass B 的真实请求语义上必须包含同一次运行中新生成且验证通过的 Pass A 输出，因此未来
真实 C2 的三个 Pass-B request SHA 只能在各自 Pass A 完成后记录；不得把上述历史 fixture
hash 冒充未来 live request hash。三个 Pass-A hash 不依赖模型输出，可按同一锁定输入、模型
和 capability profile 精确复现。

离线预注册把 fail-closed 上限配置为 6 个内容调用、78,000 total tokens、1.92 CA；输入/
输出价格分别为 7/42 CA per million tokens，每调用 6,500 completion-token 上限与总 token
上限的组合最坏费用为 1.911 CA。约 12,000 tokens、约 0.26 CA 只作规划估计，不是硬上限。
canonical schema、serializer、adapter config 与 transport schema SHA 分别保持
`fbbb628ad0f25639958c6d02db9bac90ed06865e634bd4e8eeb7b50ac7108ca9`、
`d20ae560a627c4d3faa88439908c517e7726aabb1121128af7b9013f5512edef`、
`91d16393016693be622f09e9f7012094b488eecff60e8f0611dd9db7101ac8d7`、
`ef8c684b2456196eac14cc7748bb687aef5ef32fd8a405c3003bd831ad380af7`。

该准备不读取 Layer D、Layer E 或 Gold，不产生候选/评价/P/R，不进入 C3/C4。收据明确
`provider_authorized=false`、`real_api_call=false`、`billed_tokens=0`、`C2 started=false`。

### 7.5 2026-07-26 gpt-5.4-nano 单条 C1 runtime

用户另行明确授权 ChatAnywhere `gpt-5.4-nano` 仅调用 1 条 synthetic，最大 13,000 tokens、
最大 0.07 CA，输入/输出价格 1.4/8.75 CA per million tokens，运行后停止且不进入 C2。
离线 strict v1.1 preflight 通过，唯一 transport request SHA 为
`85ef4b632ddeba1e15e4309c3859302b1ae736965dce92f7b7671f7387b67cff`，无 downgrade。

运行实际完成 1 次内容调用、0 retry。relay 报告模型为
`gpt-5.4-nano-2026-03-17`（仍为 `unverified_relay_report`），provider usage 为 1167 input +
1789 output = 2956 tokens，其中 reasoning 1307；按锁定价格计算 0.01728755 CA，低于授权上限。
模型返回 `finish_reason=stop` 和 schema-shaped JSON，但把长度为 57 的
`translation.proposed_text_en` 的整句 `clause_span.end` 写成 58，原始 canonical exact-span
validator 因越界 fail closed。没有修复输出、没有内容重试、没有有效候选，C1=false、C2=false，
evaluation=0、P/R=null。

原 `failure.json` 在候选校验前尚未提取 usage，因而错误记录 tokens/cost 为 0；该不可变失败
证据不改写。新增 `accounting_correction.json` 逐 hash 绑定原 failure/preregistration/raw response，
从 provider response 恢复 2956 tokens 与 0.01728755 CA，并登记 RWI-0027。runner 已改为先
保存/计入 provider envelope usage，再执行 canonical candidate validation；没有为修复而重跑 API。

### 7.6 2026-07-26 gpt-5.6-luna C2 首条 Pass A fail-closed runtime

用户以独立授权允许 ChatAnywhere `gpt-5.6-luna` 执行 C2，护栏为恰好六个计划内容调用、
最多 78,000 tokens、最多 1.92 CA，输入/输出价格 7/42 CA per million tokens；候选冻结后
停止且不评价。真实运行使用新的不可覆盖 ID
`c2_relay_gpt56_luna_strict_v1_1_pilot3_live_v1`。canonical schema、serializer、strict adapter
与 transport schema SHA 均未漂移，首条 transport request SHA 与离线预注册一致：
`9add2487dd36233b3e258ae451a27cebaa5de6b10de70a18b08ef7d527960aac`；无 downgrade。

runner 只发送索引 0 的 Pass A 一次，0 retry。relay 报告模型
`gpt-5.6-luna-2026-07-09`（仍为 `unverified_relay_report`），返回
`finish_reason=length`、1339 input + 6500 output/reasoning = 7839 tokens，正文 0 字符；按锁定
价格为 0.282373 CA。由于冻结协议只接受 `finish_reason=stop`，运行立即 fail closed，没有调用
其余五条，没有 Pass B，没有有效候选，也没有修复或内容重试。C2 started=true 但未完成；
C3/C4=false，evaluation=0，P/R=null。

原 `failure.json` 在 envelope 返回 usage 前先拒绝了非 `stop` completion，因而错误记录
tokens/cost 为 0；原 preregistration/request/raw response/failure 均保持不改写。新增
`accounting_correction.json` 逐 SHA 绑定原证据并恢复 7839 tokens、0.282373 CA；RWI-0027
据此重开并再次解决。runner 的 envelope 解析现在先返回 usage，随后才检查 finish reason 和
candidate；mocked `length` 回归锁定该顺序。没有为账务更正再次调用 API。

### 7.7 2026-07-26 portable transport adapter v1.2 correction

This section supersedes the universal-envelope rule in section 5 for all new
dry-runs and separately authorized API calls. Frozen v1.1 requests, receipts,
manifests, and Event 121 remain immutable and continue to be audited with the
v1.1 loader.

The defect was in the transport boundary, not in the Barrientos-style semantic
prompting approach. Adapter v1.1 incorrectly treated `reasoning_effort=high`, a
three-role message envelope, and strict Structured Outputs as universal model
requirements. Adapter v1.2 keeps the following bytes and meanings unchanged:

- B0 and D1/H1 prompts;
- all three EStG-150 candidate prompt assets;
- the canonical semantic request and serializer;
- the canonical six-element output schema;
- exact-span, entity/relation, cue-coverage, and no-repair validation;
- the prohibition on generation-time Layer D, Layer E, and Gold reads.

Only provider/model transport packaging is profile-specific:

| Profiles | Message packaging | Reasoning field | Token field | Server output mode | Final acceptance |
|---|---|---|---|---|---|
| ChatAnywhere GPT-5 profiles | preserve `system/developer/user` | preserve | `max_completion_tokens` | strict `json_schema` | canonical local validation |
| ChatAnywhere `gpt-4o`, `gpt-4.1-nano` | merge system + developer text into one system message | omit | `max_tokens` | strict `json_schema` | canonical local validation |
| ChatAnywhere `gpt-3.5-turbo` | merge system + developer and inject the exact canonical schema | omit | `max_tokens` | `json_object` | mandatory canonical local validation |
| DeepSeek official `deepseek-v4-pro` | merge system + developer and inject the exact canonical schema | omit | `max_tokens` | `json_object` | mandatory canonical local validation |

For `gpt-4o` and `gpt-4.1-nano`, server-side strict schema enforcement is
preserved, so `request_downgrade_applied=false`. For JSON-mode profiles, the
receipt honestly records `request_downgrade_applied=true` because the provider
enforces JSON syntax rather than the full schema; the semantic contract is not
downgraded because an output is never accepted or frozen unless the unchanged
canonical local validator passes. Content repair and content retry remain
forbidden in every profile.

All seven registered provider/model profiles pass runner-level offline
preflight under adapter `estg150_openai_strict_transport_schema_adapter@1.2.0`.
The canonical schema, serializer, semantic fixture, and transport schema hashes
remain, respectively:

- `fbbb628ad0f25639958c6d02db9bac90ed06865e634bd4e8eeb7b50ac7108ca9`
- `d20ae560a627c4d3faa88439908c517e7726aabb1121128af7b9013f5512edef`
- `eb074081cc52d22025e263e3f94b2165f95493f511ddc454b9ea5f5923c085e1`
- `ef8c684b2456196eac14cc7748bb687aef5ef32fd8a405c3003bd831ad380af7`

The GPT-4o synthetic transport request SHA-256 is
`08c7c1fc345688b3070a644bec452c23aa2e5c7d2831d966c94ba046e21c201a`.
This is an offline preflight receipt only: no API was called, billed tokens and
cost are zero, and it does not claim that GPT-4o runtime generation has passed.
A real GPT-4o C1 call still requires a new run ID and explicit provider, model,
call, total-token, cost/currency, and price authorization.
