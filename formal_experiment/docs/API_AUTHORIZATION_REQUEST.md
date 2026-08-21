# S2.12 复杂语料真实 LLM/API 授权申请（精确版）

**版本**：v2（2026-08-20 价格复核；v1 为 2026-08-20 初版）
**状态**：REQUEST — 尚未获得授权；**不读取 `.env`、不调用真实 API、不改 Gold、
不启动 Oracle**。零 API 基础数字来自 `outputs/reports/s2_12_execution_readiness_v4.json`、
`outputs/reports/s2_12_api_preflight_v1.json` 与 `MASTER_PIPELINE.md` §12.0g
（2026-08-18 零 API 核账）；**v2 修正点见 §3b 官方价格复核（2026-08-20 生效价）**。
**对应 Pipeline**：S2.12 full DoD 的剩余两个 API arms →
三方法比较 → S2.13 freeze。

## 1. 目的与背景

S2.11 复杂语料（Barrientos 3 场景、36 条固定 IDs）已冻结正式 Gold（SHA
`039ae8b2…`）。Rules-Only 零 API arm 已完成（modality acc/macro-F1
0.638889/0.535461；span P/R/F1 0.862319/0.802721/0.831453；L1=31、L2=5、
L3=0 no samples；cost=$0）。剩余两个任务是让 **Direct-LLM** 与
**Rules+LLM-Repair** 在同一冻结输入/Gold/合同/evaluator 上运行，完成三方法
比较与 S2.12 completion freeze。Gold-blind 正式输入
`data/input/s2_12_complex_corpus_formal_input_v1.json`（36 IDs、仅 locator/
hashes）已锁定；predictions 必须先于 Gold 评价锁定。

## 2. 待运行 arms

| Arm | 机器方法 | 说明 | 计划调用数 | 实际应运行数 |
|---|---|---|---|---|
| A1 | `direct_llm`（Direct-LLM） | 端到端生成 Rule Record，同一 v6 prompt（SHA 3aa64877…） | 36（每条 1 次，clause 级按 preflight） | 36 |
| A2 | `sun_llm_fallback`（Rules+LLM-Repair，comparison-only 对照） | 仅修复 B0 触发子集 | 27（preflight 锁定的触发子集） | 27 |

## 3. 请求参数与硬上限（已锁定于 preflight，待用户确认）

- **模型**：`deepseek-v4-pro`（OpenAI-compatible，base_url
  `https://api.deepseek.com/v1`），fail_closed_pin=true，返回模型必须逐次核对。
  官方页面模型版本现为 `DeepSeek-V4-Pro-0813`（模型 ID 仍为 deepseek-v4-pro，
  1M context、最大输出 384K；我们的配方恒用 max_tokens=4096）。
- **请求数量**：计划 63 次（direct 36 + fallback 27）；**绝对配置硬上限 108
  calls**（`configured_hard_call_cap`）。实际以 preflight 列出的 63 个请求体为准，
  不新增、不改动、不重排。
- **retry**：**0**（不允许任何重试；retry 需另行授权）。
- **input-token cap（建议，待用户批准）**：`max_billed_input_tokens_total =
  63,000,000`（官方 1M context × 63 calls 的极端保守上界；实际计费 input
  tokens 只能从真实响应 usage 获得；本地 Legal-BERT WordPiece proxy 4,960/
  207,468 tokens 仅是规划代理，**不是** billing count，不用于计费）。
- **output-token cap**：每调用 `max_output_tokens_per_call = 4096`；总计
  `max_output_tokens_total = 258,048`（direct 147,456 + fallback 110,592）。
- **USD cost cap（★已按官方新价重算，须用户重新批准）**：见 §3b。
- **请求体字节**：单次 ≤ 17,493 UTF-8 bytes、总计 ≤ 749,805 bytes（锁定 payload）。
- **sampling/transport**：temperature=0、top_p=1、max_tokens=4096、seed
  policy=unsupported_or_omitted；Direct-LLM：stream=false、thinking.disabled、
  response_format=null；Rules+LLM-Repair：stream=false、thinking.disabled、
  response_format=json_object（均带 tools_sent=false）。
- **Gold 隔离**：两个 arm 运行时**不得读取** Gold/decisions/proposals/Oracle/
  Gold Rule Records；预测必须先锁定，之后 evaluator v2 才读 frozen Gold。

## 3b. 官方价格复核（v2 修正，2026-08-20 生效）

**结论：官方价格较 preflight 锁定的 2026-08-18 价格已显著上涨 → 必须重算 USD
cap 并要求用户重新批准。** 复核来源为官方
[Models & Pricing | DeepSeek API Docs](https://api-docs.deepseek.com/quick_start/pricing/)
（2026-08-20 直接抓取 200 OK）。`deepseek-v4-pro` 现行费率（每 1M tokens）：

| 费率维度 | preflight 锁定价（2026-08-18） | 官方现价 OFF-PEAK | 官方现价 PEAK |
|---|---:|---:|---:|
| 1M input (cache hit) | 0.003625 | 0.022 | 0.044 |
| 1M input (cache miss) | 0.435 | 0.66 | 1.32 |
| 1M output | 0.87 | 1.98 | 3.96 |

- 峰值时段（UTC）：01:00–04:00 与 06:00–10:00；其余为 off-peak（off-peak 为
  peak 的 1/2）。
- **保守绝对上限（按 peak + cache-miss 最坏情形重算）**：
  input 63,000,000 × $1.32/M = $83.16；output 258,048 × $3.96/M ≈ $1.02；
  **$84.18**（原 27.63）。
- **off-peak 上限（若在 off-peak 运行）**：
  input 63,000,000 × $0.66/M = $41.58；output 258,048 × $1.98/M ≈ $0.51；
  **$42.09**。
- **申请建议 cap**：`max_cost_usd = 84.18`（无条件保守）；若用户要求并在
  off-peak 时段运行可设为 `42.09`。两者都高于 v1 的 27.63，**必须用户重新确认**。
- 本地 Legal-BERT proxy 计得的 207,468 tokens 与实际 billing input tokens 无关
  （非 DeepSeek tokenizer），真实计费仅能来自响应 usage。
- **运行前必须再次重验官方价格**；若再次变动则重新计算 cap 并再次征得同意。

## 4. 硬停止条件（fail-closed）

任一以下条件成立时，调用前必须硬停止并报告，不得继续：
1. 没有与本节逐条匹配的**用户明确 API 授权**；
2. 返回 model 或期望 model 不匹配；
3. input/source/prompt/config/implementation/payload/hash 任何漂移
   （preflight 锁定的 request body SHA-256 逐条核验）；
4. call、request-body byte、input-token、output-token 或 USD cap 任一将被超出；
5. 发现 retry 请求或 retry_count≠0；
6. Gold/decisions/proposals/Oracle/Gold Rule Records 对任一 arm 可见；
7. 官方价格无法在运行前立即重验；
8. 出现未经预注册的 runtime incident（lost/recovery/retry 必须记录并停顿）。

## 5. 运行命令（2026-08-20 核账：**S2.12 专属 arm runner 尚未实现**）

**核账结论（重要 blocker）**：现有零 API 资产只有 (1) Rules-Only 零 API arm
（`run_s2_12_sun_rule_only_v1.py`，已完成）、(2) API preflight payload 构建器
（`build_s2_12_api_preflight_v1.py`，只算请求体、不调用）。仓库中**没有**：
`run_s2_12_direct_llm_v1.py`、`run_s2_12_sun_llm_fallback_v1.py`、S2.12 专属
frozen H1 trigger plan、transport-capture 接线。现有通用 runner
（`run_direct_llm.py` 期望 `{sample_id, text}` JSONL 的 150-ID 输入格式；
`run_sun_llm_fallback.py` 期望 150-ID 输入 + `--frozen-plan` +
`--transport-capture`）**不能直接消费 36-ID hash-bound 输入**。因此：

- 在获得 API 授权**之前**必须先完成一个零 API 工程批次：实现 S2.12 专属
  执行接线（Gold-blind 输入解析 → 36 个锁定请求体 → `--allow-llm` 调用 →
  predictions/manifest/telemetry/transport-capture 落盘），并使其对 preflight
  锁定的 63 个 request-body SHA-256 逐条 fail-closed 核对；该批次需要 focused
  tests + `audit_project.py --with-tests` + `record_change.py` + commit/push。
- **在接线实现并提交之前，无法给出“无占位符、可直接复制”的最终运行命令**——
  本申请拒绝伪造指向不存在 runner 的命令。接线完成后的命令形态如下
  （路径已解析为真实路径，脚本名以最终实现为准）：

```powershell
# Direct-LLM arm（36 calls、输出/清单路径已解析；脚本名 s2_12 实现后确认）
python formal_experiment/scripts/run_s2_12_direct_llm_v1.py `
  --input data/input/s2_12_complex_corpus_formal_input_v1.json `
  --output data/predictions/s2_12_direct_llm_v1/predictions.json `
  --manifest data/predictions/s2_12_direct_llm_v1/manifest.json `
  --telemetry data/predictions/s2_12_direct_llm_v1/telemetry.json `
  --model deepseek-v4-pro --max-calls 36 --allow-llm

# Rules+LLM-Repair arm（27 触发 calls；B0 manifest=frozen 零 API arm 产物）
python formal_experiment/scripts/run_s2_12_sun_llm_fallback_v1.py `
  --input data/input/s2_12_complex_corpus_formal_input_v1.json `
  --b0-manifest data/predictions/s2_12_sun_rule_only_v1/manifest.json `
  --frozen-plan configs/s2_12_api_arms_preflight_v1.json `
  --model deepseek-v4-pro --max-calls 72 --allow-llm `
  --transport-capture data/predictions/s2_12_sun_llm_fallback_v1/transport_capture.jsonl `
  --output data/predictions/s2_12_sun_llm_fallback_v1/predictions.json `
  --manifest data/predictions/s2_12_sun_llm_fallback_v1/manifest.json `
  --telemetry data/predictions/s2_12_sun_llm_fallback_v1/telemetry.json
```

已解析真实路径（供最终命令回填）：

| 占位符 | 真实路径 |
|---|---|
| S2.12 36-ID 输入 | `data/input/s2_12_complex_corpus_formal_input_v1.json`（SHA 892d4284…，36 records，仅 sample_id+source locator/hashes） |
| Direct-LLM 输出/清单/遥测 | `data/predictions/s2_12_direct_llm_v1/{predictions,manifest,telemetry}.json` |
| Rules+LLM-Repair B0 manifest | `data/predictions/s2_12_sun_rule_only_v1/manifest.json`（零 API arm，已完成） |
| frozen trigger plan | 尚无 S2.12 专属 plan 文件（`configs/s28d_r5_h1_small_pilot_plan_v1.json` 是 150-ID 历史计划，**不可**用于 36-ID）→ 需在接线批次从 preflight 锁定 payload 派生并注册 |
| transport capture | `data/predictions/s2_12_sun_llm_fallback_v1/transport_capture.jsonl`（由接线创建） |
| 评价（evaluator v2 / G0.4 parity） | `src/bpc_hybrid/s2_12_stratified_evaluator_v2.py`（已锁定）；评价在预测锁定后执行 |
| 三方法比较/完成报告 | `outputs/reports/s2_12_three_method_comparison_v1.json`（待创建）+ transition readiness v9 |

preflight 重建命令（只读、0 调用，已在本轮实际运行通过）：
`python formal_experiment/scripts/build_s2_12_api_preflight_v1.py --runtime-home
D:/environment/stanford-corenlp-4.5.10 --tokenizer-snapshot
C:/Users/hyc/.cache/huggingface/hub/models--nlpaueb--legal-bert-base-uncased/
snapshots/15b570cbf88259610b082a167dacc190124f60f6 --check`

## 6. Manifest 与产物路径（运行后登记）

- 预测：`data/predictions/s2_12_direct_llm_v1/`、
  `data/predictions/s2_12_sun_llm_fallback_v1/`（含 manifest，记录
  llm_calls/max_calls/model/sampling/transport/failure）。
- 评价：`data/results/` 同前缀目录（evaluator v2 / G0.4 parity 口径）。
- 三方法比较与 completion：`outputs/reports/s2_12_*_v*` + transition readiness
  v9（supersede v8）。
- 事件：`record_change.py --event-type experiment_run`（含成本、失败数、hash）。

## 7. 授权句模板（v2；复制即可，用户按需改写后返回）

> 我授权在 S2.12 复杂语料上运行 Direct-LLM（`direct_llm`，36 次）和
> Rules+LLM-Repair（`sun_llm_fallback`，27 次触发）的真实 DeepSeek API，
> 模型仅限 `deepseek-v4-pro`，严格使用 `s2_12_api_preflight_v1.json` 锁定的
> 63 个请求体（单次 ≤ 17,493 bytes、总计 ≤ 749,805 bytes），`--max-calls`
> 硬上限为 108（实际 63），`retry = 0`；总 output tokens ≤ 258,048
> （单次 ≤ 4,096）；总计费 input tokens ≤ 63,000,000；总 USD 成本 ≤ **84.18**
> （已按 2026-08-20 官方 peak 价重算；若以 off-peak 运行可改为 ≤ 42.09）；
> 运行前重验官方价格；任一模型/输入/source/prompt/config/payload/hash 漂移、
> Gold 隔离违背或任一 cap 将超时必须在调用前硬停止；不得调用 Oracle，不读取
> `.env`。我知晓实际 billing input tokens 与 cost 只能来自真实响应 usage，
> 且**执行前必须先完成 S2.12 专属 runner 接线批次并通过全量审计与提交**。

## 8. 本申请之外的阻塞与前置工作（如实记录）

- **前置（未完成）**：S2.12 专属 arm runner／H1 frozen trigger plan／transport
  capture 接线尚未实现并提交（见 §5）。该批次是零 API 工程，必须先完成。
- 本申请只涵盖 S2.12 两个 API arms；S2.13 freeze 与 Stage 3/9 个 GDPR Gold
  Rule Records、S3.7 Oracle 授权均为**独立**事项，不随本申请自动解锁。
- **价格变更**：官方价已于 2026-08-19/20 上调（≥3×）；v1 的 27.63 cap 作废，
  需以 §3b 重算值（84.18 peak / 42.09 off-peak）重新批准。
- 未获授权前：0 calls、cost=null、不读取 `.env`。
