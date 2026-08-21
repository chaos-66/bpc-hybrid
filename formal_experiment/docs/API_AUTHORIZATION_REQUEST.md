# S2.12 复杂语料真实 LLM/API 授权申请（精确版 v3）

**版本**：v3（2026-08-22 runner wiring 完成后）
**状态**：**RUNNER READY / API NOT AUTHORIZED / ZERO CALLS**
**前版**：v2（2026-08-20 官方价格复核）；v1（2026-08-20 初版）
**边界**：不读取 `.env`、不调用真实 API、不改 Gold、不启动 Oracle。全部真实
调用的前置工程已在此前零 API 批次完成并提交；本批次（runner wiring）本身
**零 API 零网络**，未创建任何授权文件。

## 0. 状态摘要（v3 要求）

| 项目 | 状态 |
|---|---|
| `run_s2_12_direct_llm_v1.py` | ✅ 已实现（36 calls，payload-locked fake 验证通过） |
| `run_s2_12_sun_llm_fallback_v1.py` | ✅ 已实现（27 calls，frozen plan 绑定，capture 接线） |
| `configs/s2_12_fallback_trigger_plan_v1.json` | ✅ 已从锁定 preflight 触发集派生（27 条，replay byte-identical） |
| 63/63 request-body SHA 核验 | ✅ 重建即逐条比对（36/36 + 27/27），漂移即 fail-closed |
| 授权合同 schema | ✅ `configs/schemas/s2_12_api_authorization_v1.schema.json` |
| 真实 API calls | **0** |
| billed input/output tokens | **0** |
| USD cost | **$0** |
| 授权文件 | **未创建**（schema + 测试用合成 fixture 已提供） |

## 1. 待运行 arms（与 preflight 锁定一致）

| Arm | 机器方法 | 说明 | 计划调用数 | max-calls |
|---|---|---|---|---|
| A1 | `direct_llm`（Direct-LLM） | 端到端生成 Rule Record，v6 prompt（SHA 3aa64877…） | 36（每条 1 次） | 36 |
| A2 | `sun_llm_fallback`（Rules+LLM-Repair，comparison-only 对照） | 仅修复 frozen plan 锁定的 27 个 clause 触发子集 | 27（clause 级） | 72（配置值；实际 27） |

## 2. 最终运行命令（无占位符；尚未执行）

```powershell
# Arm 1 — Direct-LLM（36 calls）
python formal_experiment/scripts/run_s2_12_direct_llm_v1.py `
  --runtime-home D:/environment/stanford-corenlp-4.5.10 `
  --transport real --allow-llm `
  --auth-file <USER_PLACES_AUTHORIZATION_FILE_HERE> `
  --output-dir formal_experiment/data/predictions/s2_12_direct_llm_v1

# Arm 2 — Rules+LLM-Repair（27 calls；comparison-only）
python formal_experiment/scripts/run_s2_12_sun_llm_fallback_v1.py `
  --runtime-home D:/environment/stanford-corenlp-4.5.10 `
  --transport real --allow-llm `
  --auth-file <USER_PLACES_AUTHORIZATION_FILE_HERE> `
  --output-dir formal_experiment/data/predictions/s2_12_sun_llm_fallback_v1
```

`<USER_PLACES_AUTHORIZATION_FILE_HERE>` 是用户放置授权文件的路径（按 §4 schema
生成）；**该文件只能由用户创建**。runner 在缺少任何字段或 hash 不匹配时于第一次
transport 调用前拒绝。

> 说明：`--runtime-home` 只用于 preflight 诊断重放以验证 payload 契约（离线、
> 0 调用）；真实 transport 路径只经 `RealAPITransport` 发送已锁定的请求体。

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
| `schema_version` | `s2_12_api_authorization@1.0.0` |
| `authorization_sentence_utf8_sha256` | 用户授权句 UTF-8 的 SHA-256 |
| `authorization_event_file` / `_sha256` | 授权事件文件路径 + 原始字节 SHA-256 |
| `model` | `deepseek-v4-pro` |
| `calls` | `{direct_llm: 36, sun_llm_fallback: 27}` |
| `payload_hashes` | 恰好 63 个 request-body SHA-256（与 preflight 锁定集一致） |
| `retry` | `0` |
| `input_token_cap` / `output_token_cap` / `usd_cost_cap` | 正数上界 |
| `allowed_windows` | `any_time` 或 `off_peak_only` |
| `price_snapshot` / `price_checked_at_utc` | 官方价格快照标识 + 核验时间 |
| `runner_implementation_hashes` | `run_s2_12_direct_llm_v1` / `run_s2_12_sun_llm_fallback_v1` 各自身 SHA-256（与磁盘一致） |
| `input_config_prompt_hashes` | input / preflight-lock / direct-prompt / fallback-prompt 的 SHA-256 |
| `gold_isolation` | `api_arms_must_not_read_gold: true`（+ evaluation_only_after_predictions_are_locked） |

## 5. runner 与绑定资产 hash（v3，磁盘实际值）

| 资产 | SHA-256（完整） |
|---|---|
| `src/bpc_hybrid/s2_12_execution.py` | `d76655e2a53de745766694e6eab44f0fb6a052507de8dab6e899a9cbb5ccf64f` |
| `scripts/run_s2_12_direct_llm_v1.py` | `5dea8d00c5bd3622fbbc3219dc635e0ef574fb55b5ece6948f610fd1ad427f6e` |
| `scripts/run_s2_12_sun_llm_fallback_v1.py` | `ce7299f88cd42c1ecff62fb0fd49d680afab53499df0c31bb362607ad17c1ce9` |
| `scripts/build_s2_12_fallback_trigger_plan_v1.py` | `6089ea8f4ee1cd25a7a6de0e1135ba6abaab29ac3d23ce8042e2621aaab33e51` |
| `configs/s2_12_fallback_trigger_plan_v1.json` | `857149a6c5f4beb608969c2af119708f44db5f4575ac4d7f840bf2b58224cd72` |
| `configs/schemas/s2_12_api_authorization_v1.schema.json` | `3a499ffc743be7bb4965175add9dcda88f0e220c50247d585f3477f5a4d7f0a8` |
| `configs/s2_12_api_arms_preflight_v1.json`（锁） | `3b62ba6658531a09469c7ecdecacc5797674ed795d62c55f389600586b2f221c` |
| `outputs/reports/s2_12_api_preflight_v1.json` | `c7d33f956464f54b9b76145a1874d9111e3e41f1a904bc3751edc8b8e3c90314` |
| `data/input/s2_12_complex_corpus_formal_input_v1.json` | `892d4284ea70c38f82a47f821c13622f1b07744253429e466038ddb5db96660e` |
| direct prompt v6 | `3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895` |
| fallback prompt | `00fe02996914e17f30962147d7a9f2c71a92d2479ba4eff343583a139bb1537b` |

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

## 7. 已实现工程（runner wiring，零 API 零网络）

- 共享契约模块 `src/bpc_hybrid/s2_12_execution.py`：锁/输入/报告核验、63 payload
  逐条重建比对、授权合同校验、Beijing off-peak 时段、payload-locked fake
  transport、原子发布（拒绝覆盖）、文本/密钥 containment。
- `run_s2_12_direct_llm_v1.py`：36 calls；fake 默认；real 需 `--allow-llm` +
  `--auth-file`；canonical validator + span canonicalizer 链；正式输出
  `data/predictions/s2_12_direct_llm_v1/{predictions,manifest,telemetry,cost}.json`。
- `run_s2_12_sun_llm_fallback_v1.py`：27 calls；frozen plan 绑定 + transport
  capture；正式输出 `data/predictions/s2_12_sun_llm_fallback_v1/…`（含
  `transport_capture.jsonl`）。
- `configs/s2_12_fallback_trigger_plan_v1.json`：从锁定 preflight 触发集派生的
  27 条 frozen plan；`--check` 重放 byte-identical。
- 独立 verifier `verify_s2_12_runner_wiring.py`：资产、hash、计数、schema、
  零调用状态全查。
- focused tests `tests/test_s2_12_runner_wiring.py`（21 项，含 fail-closed
  场景；fake transport；零网络）。

## 8. 硬停止条件（与 v2 一致；补 runner 内置项）

1. 无逐条匹配的用户 API 授权（授权文件缺失/字段缺失/hash 不匹配）；
2. 返回 model ≠ deepseek-v4-pro；
3. input/source/prompt/config/implementation/payload hash 任何漂移；
4. call、request-body byte、input-token、output-token 或 USD cap 任一将超；
5. retry≠0；
6. Gold/decisions/proposals/Oracle/Gold Rule Records 对任一 arm 可见；
7. 官方价格无法在运行前重验；
8. 未预注册 runtime incident（lost/recovery/retry 记录并停顿）；
9. （v3 新增）off-peak-only 授权在 peak 时段（北京 09:00–12:00、14:00–18:00）
   拒绝调用。

## 9. 授权句模板（v3；复制即用，须用户亲自发出并创建授权文件）

> 我授权在 S2.12 复杂语料上运行 Direct-LLM（`direct_llm`，36 次）和
> Rules+LLM-Repair（`sun_llm_fallback`，27 次触发）的真实 DeepSeek API，
> 模型仅限 `deepseek-v4-pro`，严格使用 `s2_12_api_preflight_v1.json` 锁定的
> 63 个请求体（单次 ≤ 17,493 bytes、总计 ≤ 749,805 bytes），`--max-calls`
> 硬上限 108（实际 63），`retry = 0`；总 output tokens ≤ 258,048（单次 ≤
> 4,096）；总计费 input tokens ≤ 63,000,000；总 USD 成本 ≤ **84.18**（若仅
> off-peak 运行可改为 ≤ 42.09：北京 09:00–12:00、14:00–18:00 之外）；运行前
> 重验官方价格；任一模型/输入/source/prompt/config/payload/hash 漂移、Gold
> 隔离违背、cap 将超或 peak 时段（off-peak-only 时）均在调用前硬停止；不得调用
> Oracle，不读取 `.env`。我知晓实际 billing input tokens 与 cost 只能来自
> 真实响应 usage。

**用户还需按 §4 schema 创建授权文件**（含授权句 SHA-256、事件文件 SHA-256、
63 个 payload hashes、caps、runner implementation hashes 等），并把路径填入
§2 命令的 `--auth-file`。

## 10. 本申请之外的阻塞

- S2.13 freeze 与 Stage 3 / 9 个 GDPR Gold Rule Records / S3.7 Oracle 授权均为
  独立事项，不随本申请自动解锁。
- 未获授权前：0 calls、cost=null、不读取 `.env`；runner 默认 fake transport。