# S2.12 复杂语料真实 LLM/API 授权申请（精确版 v4）

**版本**：v4（2026-08-22 runner safety v2 完成后）
**状态**：**RUNNER SAFETY V2 VERIFIED / API NOT AUTHORIZED / ZERO CALLS**
**前版**：v3（2026-08-22 runner wiring）；v2（2026-08-20 价格复核）；v1（初版）
**边界**：不读取 `.env`、不调用真实 API、不改 Gold、不启动 Oracle。真实执行安全
修复（v2 批次）已实现、测试、审计并提交；真实调用仍 pending 用户授权句 +
授权文件。

## 0. 状态摘要（v4 要求）

| 项目 | 状态 |
|---|---|
| 真实 payload 锁（**每次调用前**重建最终 body → SHA-256 → 与锁定逐条比对 → ID/顺序核验） | ✅ `PayloadLock` + fake/real transport 通用 |
| Arm policy 与实际发送一致 | ✅ Direct（stream=false、thinking disabled、response_format=null、temp0/top_p1/4096）与 fallback（+json_object、tools_sent=false）由 `arm_policy` 强制 |
| usage 捕获（prompt/completion/returned model/finish reason/缺失状态） | ✅ 从 `transport.last_decode["usage"]` 读取；缺失即 fail-closed |
| 成本计算（cache hit/miss 拆分；缺失时保守 cache-miss；累积 USD） | ✅ `per_call_cost` + `CumulativeState`；`cost_usd` 不再硬编码 0 |
| 每次调用前/后 caps（input/output/USD + 保守上界 + call cap） | ✅ `check_pre_call` / `check_post_call` |
| off-peak **每次调用前**检查；运行中进入 peak 即停 | ✅ `check_off_peak_only` 在 StageExecutor 每轮调用 |
| 分阶段运行（D-CAL 1 / D-REST 35；F-1/F-2/F-3 9×3）+ resume | ✅ `--stage-id`/`--auth-file`/`--resume-from-ledger`；任意 `--start` 拒绝 |
| append-only hash-chained 账本 + resume 不重复 + 篡改拒绝 | ✅ `ExecutionLedger` |
| `.env` 禁读（仅进程环境） | ✅ 两个 runner 均 `LLMConfig.from_env(project_root=ROOT, load_project_env=False)` |
| 每 arm 独立 runner hash 绑定（fallback 不再与 direct 比较） | ✅ `validate_authorization(arm, runner_hash, impl_hashes)` |
| D-CAL 单请求计费校准（schema/builder/测试；不执行） | ✅ codec + 测试 |
| 授权事件 builder（无原句拒绝；dry-run 默认；本轮不 apply） | ✅ `scripts/build_s2_12_auth_event_v1.py` |
| 真实 API calls / billed tokens / USD | **0 / 0 / $0** |
| 授权文件 | **未创建** |

## 1. 待运行 arms（与 preflight 锁定一致）

| Arm | 机器方法 | 说明 | 计划调用数 | max-calls |
|---|---|---|---|---|
| A1 | `direct_llm`（Direct-LLM） | 端到端生成 Rule Record，v6 prompt（SHA 3aa64877…） | 36（每条 1 次） | 36 |
| A2 | `sun_llm_fallback`（Rules+LLM-Repair，comparison-only 对照） | 仅修复 frozen plan 锁定的 27 个 clause 触发子集 | 27（clause 级） | 72（配置值；实际 27） |

## 2. 最终运行命令（分阶段；无占位符；尚未执行）

所有命令均使用固定授权文件路径（由 §4 builder 未来创建）与预注册 stage；禁止
任意 `--start`/ID 列表。

**D-CAL（校准，未来授权后）** — Direct-LLM 第 1 个锁定 payload，1 次调用：
```powershell
python formal_experiment/scripts/build_s2_12_auth_event_v1.py `
  --runtime-home D:/environment/stanford-corenlp-4.5.10 `
  --stage-id D-CAL --dry-run --usd-cap 1.00 `
  --sentence "<你的授权原句，逐字>"

python formal_experiment/scripts/run_s2_12_direct_llm_v1.py `
  --runtime-home D:/environment/stanford-corenlp-4.5.10 `
  --transport real --allow-llm `
  --auth-file formal_experiment/configs/s2_12_api_authorization_D-CAL.json `
  --stage-id D-CAL `
  --output-dir formal_experiment/data/predictions/s2_12_direct_llm_v1
```
（D-CAL 固定授权文件路径：`formal_experiment/configs/s2_12_api_authorization_D-CAL.json`
+ 事件文件 `configs/s2_12_api_authorization_event_D-CAL.json`；off-peak-only；每次调用前
检查时段；input cap ≤1,000,000、output ≤4,096、USD ≤1.00；结果属于正式锁定 arm。）

**剩余调用分阶段（校准后）**：
```powershell
# Direct D-REST（35 次；resume 账本）
python formal_experiment/scripts/run_s2_12_direct_llm_v1.py `
  --runtime-home D:/environment/stanford-corenlp-4.5.10 --transport real --allow-llm `
  --auth-file formal_experiment/configs/s2_12_api_authorization_D-REST.json `
  --stage-id D-REST `
  --resume-from-ledger D:/Paper/experiment/bpc-hybrid/formal_experiment/data/predictions/s2_12_direct_llm_v1.ledger.jsonl `
  --output-dir formal_experiment/data/predictions/s2_12_direct_llm_v1

# Fallback F-1 / F-2 / F-3（9/9/9；每阶段各一份授权文件，链式 resume）
python formal_experiment/scripts/run_s2_12_sun_llm_fallback_v1.py `
  --runtime-home D:/environment/stanford-corenlp-4.5.10 --transport real --allow-llm `
  --auth-file formal_experiment/configs/s2_12_api_authorization_F-1.json `
  --stage-id F-1 --output-dir formal_experiment/data/predictions/s2_12_sun_llm_fallback_v1
```

**Stage 结构 / 每阶段 cap**：

| Stage | Arm | payloads | call cap | 时段 | 建议 USD cap |
|---|---|---|---|---|---|
| D-CAL | direct | 1 | 1 | off-peak only | ≤1.00 |
| D-REST | direct | 35 | 35 | any（授权决定） | 按剩余预算 |
| F-1/F-2/F-3 | fallback | 9/9/9 | 9/9/9 | any（授权决定） | 按剩余预算 |
| 全局（每份授权文件） | — | — | — | — | global caps：input ≤63,000,000、output ≤258,048、USD ≤84.18（或批准值） |

**成本计算方法（授权绑定价格快照）**：
`累计成本 = cache_hit_tokens×hit_price + cache_miss_tokens×miss_price +
output_tokens×output_price`（每 1M tokens 换算）；provider 不返回 cache hit/miss
拆分时，全部 input 按**保守 cache-miss 价格**计（授权合同规定）。`cost_usd`
由真实 response usage 累积，禁止硬编码 0。

**恢复合同**：每成功响应后立即 append-only hash-chained 账本
（`<output-dir>.ledger.jsonl`，位于 capsule 同目录外侧）；resume 校验 hash 链、
拒绝重复调用已记录 payload、从下一个预注册 payload 继续、retry 恒 0、
不得据已有输出修改后续请求；partial 账本必须标 partial，正式 final predictions
只在整 arm（36/27）完成后发布。

## 3. 请求参数、硬上限与价格（v2 → v3 保持一致，待用户批准）

- **模型**：`deepseek-v4-pro`（官方页面模型版本 `DeepSeek-V4-Pro-0813`；模型 ID
  钉死 deepseek-v4-pro，1M context、最大输出 384K；配方恒用 max_tokens=4096）。
- **请求数量**：63（direct 36 + fallback 27）；绝对配置硬上限 108；retry=**0**。
- **output-token cap**：单次 4,096；总计 **258,048**（direct 147,456 + fallback
  110,592）。
- **input-token cap（待批准）**：`max_billed_input_tokens_total = 63,000,000`
  （官方 1M context × 63 calls 的极端保守上界；**不是**预计消费，见 §6 分阶段建议）。
- **USD cap（待批准；v2 按官方新价重算）**：**84.18（peak）/ 42.09（off-peak）**
  ——官方价已于 2026-08-19/20 上调（v4-pro input cache-miss 0.435→0.66/1.32、
  output 0.87→1.98/3.96，每 1M tokens）；v1 的 27.63 已作废。
- **请求体字节**：单次 ≤ 17,493；总计 ≤ 749,805（锁定 payload）。
- **sampling/transport**：temperature=0、top_p=1、max_tokens=4096、
  seed=unsupported_or_omitted；Direct-LLM：stream=false、thinking.disabled、
  response_format=null；Fallback：stream=false、thinking.disabled、
  response_format=json_object（tools_sent=false）。
- **时段**：off-peak-only 授权时，调用前检查北京时间；peak=09:00–12:00、
  14:00–18:00（UTC+8），进入 peak 立即停止（runner 内置 `check_off_peak_only`）。
- **价格复核**：运行前必须再次重验官方价格；若再变动需重新批准 cap。

## 4. 授权文件 schema（`configs/schemas/s2_12_api_authorization_v1.schema.json`）

必需字段（任一缺失 → 第一次 transport 调用前拒绝）：

| 字段 | 含义 |
|---|---|
| `schema_version` | `s2_12_api_authorization@1.1.0` |
| `authorization_sentence_utf8_sha256` | 用户授权句 UTF-8 的 SHA-256 |
| `authorization_event_file` / `_sha256` | 授权事件文件路径 + 原始字节 SHA-256 |
| `model` | `deepseek-v4-pro` |
| `calls` | `{direct_llm: 36, sun_llm_fallback: 27}` |
| `stage_id` | `D-CAL` / `D-REST` / `F-1` / `F-2` / `F-3` |
| `stage_payload_hashes` | 本 stage 的 payload SHA-256（预注册 subset，任意子集拒绝） |
| `stage_call_cap` | 本 stage 调用上限 |
| `global_input_token_cap` / `global_output_token_cap` / `global_usd_cost_cap` | 累计全局上界 |
| `allowed_windows` | `any_time` 或 `off_peak_only`（每次调用前检查） |
| `price_snapshot` / `price_checked_at_utc` | 官方价格快照对象（schema `s2_12_price_snapshot@1.0.0`）＋核验时间 |
| `runner_implementation_hashes` | direct/fallback runner + `s2_12_execution` + `llm_client` + `h1_transport` 各自 SHA-256（按 arm 校验对应 runner） |
| `input_config_prompt_hashes` | input / preflight-lock / direct-prompt / fallback-prompt 的 SHA-256 |
| `prev_stage_ledger_hash` | 前一 stage 账本末条 hash（首 stage 为空串） |
| `final_63_payload_hashes` | 恰好 63 个 request-body SHA-256（最终 63 集合承诺） |
| `retry` | `0` |
| `gold_isolation` | `api_arms_must_not_read_gold: true`（+ evaluation_only_after_predictions_are_locked） |

授权事件 builder：`scripts/build_s2_12_auth_event_v1.py`（**无用户原句拒绝；
默认 dry-run；本轮不 apply**）。未来真实创建后固定路径为
`formal_experiment/configs/s2_12_api_authorization_<STAGE>.json` +
`configs/s2_12_api_authorization_event_<STAGE>.json`（无占位符）。

## 5. runner 与绑定资产 hash（v4，磁盘实际值；verifier 随时重取）

| 资产 | SHA-256（完整） |
|---|---|
| `src/bpc_hybrid/s2_12_execution.py` | `df391a03577111fe5efb35c21aaf9bc165a0f824c0cc1d39f7cb523befff9620` |
| `scripts/run_s2_12_direct_llm_v1.py` | `919444ec44a9789fc4d1304f9e8ebad5125a49d9a0bc0aa100ea03271da4fe00` |
| `scripts/run_s2_12_sun_llm_fallback_v1.py` | `13f7d77511d1ba1c1ae3a8edfd5878ca9f81d07b10f84be808a4d5116244f877` |
| `scripts/build_s2_12_auth_event_v1.py` | `c7f4f2644de0b854738f2e40a388c1316a726d5a3b30c48bbb1c241d495e1484` |
| `configs/s2_12_fallback_trigger_plan_v1.json` | `857149a6c5f4beb608969c2af119708f44db5f4575ac4d7f840bf2b58224cd72` |
| `configs/schemas/s2_12_api_authorization_v1.schema.json` | `524d9c48bae181adff292e2d08d946d2e89162e239a78ff3eb7732cdb5fe00f1` |
| `configs/s2_12_api_arms_preflight_v1.json`（锁） | `3b62ba6658531a09469c7ecdecacc5797674ed795d62c55f389600586b2f221c` |
| `outputs/reports/s2_12_api_preflight_v1.json` | `c7d33f956464f54b9b76145a1874d9111e3e41f1a904bc3751edc8b8e3c90314` |
| `data/input/s2_12_complex_corpus_formal_input_v1.json` | `892d4284ea70c38f82a47f821c13622f1b07744253429e466038ddb5db96660e` |
| direct prompt v6 | `3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895` |
| fallback prompt | `00fe02996914e17f30962147d7a9f2c71a92d2479ba4eff343583a139bb1537b` |
| `llm_client.py`（transport/policy 实现） | `232284dadc2b1f867ee885db1d111360f005b29a52662619af2dffee4f128e24` |
| `h1_transport.py`（policy 实现） | `f9efba42509eb85be522a45ee9ee4cf728ec1437945dfb4189bd7f4cc0d45b77` |

授权文件中的 `runner_implementation_hashes` 必须分别绑定 direct/fallback runner、
`s2_12_execution`、`llm_client`、`h1_transport` 的上表实际 SHA-256；校验时按当前
arm 只比较对应 runner hash（fallback 不再与 direct 比较）。任何不匹配 → 第一次
transport 调用前拒绝。运行 `verify_s2_12_runner_safety_v2.py` 可随时重取。

授权文件中的 `runner_implementation_hashes` 必须以 `run_s2_12_direct_llm_v1.py` /
`run_s2_12_sun_llm_fallback_v1.py` 的上表实际 SHA-256 填写（任何不匹配 → 第一次
transport 调用前拒绝；运行 `verify_s2_12_runner_wiring.py` 可随时重取）。

## 6. 分阶段成本建议（v3；零调用离线估计）

**现状**：63M input cap 是“每调用耗满 1M context”的极端上界，不是合理预计消费。
官方 `deepseek-v4-pro` tokenizer 本地不可用（无官方离线分词资产），**官方计费
input tokens 只能从真实响应 usage 获得**。本地 Legal-BERT WordPiece proxy 总计
207,468 tokens、UTF-8 请求体总计 749,805 bytes —— 两者都不是 billing count。

**离线可证明的保守规划上界**（planning only）：
- 按“max(2×proxy, bytes/1.8)”的经验上界，63 个请求体合计 ≈ **416,559 input
  tokens**（远小于 63M）；output 恒为 258,048。
- 若以该规划上界按官方新价（peak cache-miss input $1.32/M、output $3.96/M）：
  input ≈ $0.55 + output ≈ $1.02 ≈ **$1.57（peak）**；off-peak ≈ $0.28 + $0.51
  ≈ **$0.79**。**以上为规划估算，不是计费承诺。**

**建议的执行授权方案**：
1. **单请求计费校准（第 1 次调用）**：先只发 1 个已锁定请求体（direct_llm 第 1
   条），从真实响应的 `usage.prompt_tokens/completion_tokens` 拿到官方 tokenizer
   的精确换算比；据此把 63M / $84.18 换成“按真实 token 换算后的合理上界”。
2. **分阶段授权（剩余 62 次）**：校准后分 2–3 个小阶段（如 20+20+22 或按预算
   比例），每阶段结束核对累计 input/output tokens 与 USD；任一阶段超出按新比例
   折算的 cap 即硬停止。
3. **peak/off-peak 硬停止**：若只批准 off-peak（peak=北京时间 09:00–12:00、
   14:00–18:00），runner 在每次调用前检查时段，进入 peak 立即停止（已实现
   `check_off_peak_only`）。cap 取 42.09（off-peak）或 84.18（any_time）。
4. **官方价格重验**：每次真实运行前重验官方价格页，价格变动则重算并再次征得同意。

## 7. 已实现工程（runner safety v2，零 API 零网络）

- 共享契约 `src/bpc_hybrid/s2_12_execution.py`（v2）：锁/输入/报告核验、63 payload
  逐条重建比对、**per-call PayloadLock**（fake 与 real transport 共用）、usage/成本
  计算（`per_call_cost`/`CumulativeState`）、**per-call caps + off-peak**
  （`check_pre_call`/`check_post_call`）、**append-only hash-chained 账本**
  （`ExecutionLedger` + resume）、**StageExecutor**（含 stage subset、
  resume-from-ledger、partial 状态）、`publish_stage_capsule`（final predictions
  仅整 arm 完成后发布）、授权 v1.1.0 校验（每 arm 独立 runner hash）。
- `run_s2_12_direct_llm_v1.py`：`--stage-id D-CAL|D-REST`、`--auth-file`、
  `--resume-from-ledger`；real 路径 `LLMConfig.from_env(project_root=ROOT,
  load_project_env=False)`（不读项目 `.env`）。
- `run_s2_12_sun_llm_fallback_v1.py`：`--stage-id F-1|F-2|F-3`（9/9/9 分区）、
  comparison-only；同样禁读项目 `.env`，独立 runner hash 绑定。
- `scripts/build_s2_12_auth_event_v1.py`：离线授权事件 builder（无原句拒绝、
  默认 dry-run、本轮不 apply；未来固定输出路径见 §4）。
- 授权 schema v1.1.0（stage 绑定）；frozen plan（27 条）不变。
- 独立 verifier `verify_s2_12_runner_safety_v2.py`：**RUNNER SAFETY V2 VERIFIED /
  API NOT AUTHORIZED / ZERO CALLS**。
- focused tests：`test_s2_12_runner_safety_v2.py`（scripted real-like transport、
  30+ 场景、零网络）+ `test_s2_12_runner_wiring.py`（更新到 v2 接口）。

## 8. 硬停止条件（v4；含 v2 新增项）

1. 无逐条匹配的用户 API 授权（授权文件缺失/字段缺失/hash 不匹配）；
2. 返回 model ≠ deepseek-v4-pro；
3. input/source/prompt/config/implementation/payload hash 任何漂移
   （**每次真实调用前重算实际 body SHA**，非仅启动时）；
4. call、request-body byte、input-token、output-token 或 USD cap 任一将超
   （**调用前保守上界 + 响应后真实累积双重检查**）；
5. retry≠0；
6. Gold/decisions/proposals/Oracle/Gold Rule Records 对任一 arm 可见；
7. 官方价格无法在运行前重验；
8. 未预注册 runtime incident（lost/recovery/retry 记录并停顿）；
9. off-peak-only 授权在 **每次调用前** 检查北京时间；运行中进入 peak 立即停止；
10. provider usage 缺失/损坏 → fail closed（不猜测 token 数）。

## 9. 授权句模板（v4；复制即用，须用户亲自发出并创建授权文件）

> 我授权在 S2.12 复杂语料上按预注册 stage 运行
> Direct-LLM（`direct_llm`，D-CAL 1 次 / D-REST 35 次）和
> Rules+LLM-Repair（`sun_llm_fallback`，F-1/F-2/F-3 各 9 次）的真实 DeepSeek API，
> 模型仅限 `deepseek-v4-pro`，严格使用 `s2_12_api_preflight_v1.json` 锁定的
> 63 个请求体（单次 ≤ 17,493 bytes、总计 ≤ 749,805 bytes），`retry = 0`；全局
> output tokens ≤ 258,048（单次 ≤ 4,096）；总计费 input tokens ≤ 63,000,000；
> 总 USD 成本 ≤ **84.18**（若仅 off-peak 运行可改为 ≤ 42.09：北京 09:00–12:00、
> 14:00–18:00 之外，每次调用前检查）；D-CAL 单请求 USD ≤ 1.00、input ≤ 1,000,000、
> off-peak only；运行前重验官方价格；任一模型/输入/source/prompt/config/payload/
> hash 漂移、实际 body SHA 与锁定不符、Gold 隔离违背、cap 将超或 peak 时段
> （off-peak-only 时）均在调用前硬停止；不得调用 Oracle，不读取 `.env`。我知晓
> 实际 billing input tokens 与 cost 只能来自真实响应 usage；授权事件与授权文件
> 由 `build_s2_12_auth_event_v1.py` 在收到本句后生成（dry-run 先示）。

**用户还需**：(1) 逐字提供授权原句（builder 计算句 hash 与事件文件 hash）；
(2) 批准/调整每阶段 cap；然后执行 §2 命令（`--auth-file` 指向固定输出路径）。

## 10. 本申请之外的阻塞

- S2.13 freeze 与 Stage 3 / 9 个 GDPR Gold Rule Records / S3.7 Oracle 授权均为
  独立事项，不随本申请自动解锁。
- 未获授权前：0 calls、cost=null、不读取 `.env`；runner 默认 fake transport；
  API 状态保持 `API BLOCKED / ZERO CALLS`。