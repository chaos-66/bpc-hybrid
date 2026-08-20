# S2.12 复杂语料真实 LLM/API 授权申请（精确版）

**版本**：v1（2026-08-20）
**状态**：REQUEST — 尚未获得授权；**不读取 `.env`、不调用真实 API、不改 Gold、
不启动 Oracle**。所有数字来自 `outputs/reports/s2_12_execution_readiness_v4.json`、
`outputs/reports/s2_12_api_preflight_v1.json` 与 `MASTER_PIPELINE.md` §12.0g
（2026-08-18 零 API 核账）。
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
- **USD cost cap（建议，待用户批准）**：`max_cost_usd = 27.63`
  （官方价格 2026-08-18：input cache-miss 0.435/M、input cache-hit
  0.003625/M、output 0.87/M）。**运行前必须重验官方价格**；若价格变动则
  重新计算 cap 并需用户再确认。
- **请求体字节**：单次 ≤ 17,493 UTF-8 bytes、总计 ≤ 749,805 bytes（锁定 payload）。
- **sampling/transport**：temperature=0、top_p=1、max_tokens=4096、seed
  policy=unsupported_or_omitted；Direct-LLM：stream=false、thinking.disabled、
  response_format=null；Rules+LLM-Repair：stream=false、thinking.disabled、
  response_format=json_object（均带 tools_sent=false）。
- **Gold 隔离**：两个 arm 运行时**不得读取** Gold/decisions/proposals/Oracle/
  Gold Rule Records；预测必须先锁定，之后 evaluator v2 才读 frozen Gold。

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

## 5. 运行命令（最终命令在授权后由配置生成并回填；此处给出既有入口与接口）

S2.12 主数据/评价使用 `s2_12_method_adapter.py`（`adapt_method_attempts`）把各
arm 输出适配到 evaluator v2 / G0.4 parity 口径。真实 LLM 调用复用既有 runner
入口（`run_direct_llm.py` / `run_sun_llm_fallback.py`），两者都 fail-closed 于
`--allow-llm` 与 `--max-calls`：

```powershell
# Direct-LLM arm（接口：--input/--output/--manifest/--allow-llm/--max-calls）
python formal_experiment/scripts/run_direct_llm.py `
  --input <S2.12 36-ID 输入> --output <预测> --manifest <manifest> `
  --max-calls 36 --allow-llm

# Rules+LLM-Repair arm（接口：--b0-manifest/--frozen-plan/--model/
#   --transport-capture/--allow-llm/--max-calls；real-run 还需 --transport-capture）
python formal_experiment/scripts/run_sun_llm_fallback.py `
  --b0-manifest <B0 manifest> --frozen-plan <trigger 子集计划> `
  --model deepseek-v4-pro --max-calls 72 --allow-llm --transport-capture <capture>
```

带 `<…>` 处的具体路径、冻结计划与 transport-capture 必须在获得授权后、运行前按
`configs/s2_12_api_arms_preflight_v1.json`（SHA 3b62ba66…）与 readiness v4
锁定的绑定生成，并在最终命令回填前再次经用户确认；本申请不替用户预先敲定这些
细节（防止“伪授权即跑”）。preflight 重建命令（只读、0 调用）：
`python formal_experiment/scripts/build_s2_12_api_preflight_v1.py --runtime-home
<CoreNLP> --tokenizer-snapshot <legal-bert> --check`。

## 6. Manifest 与产物路径（运行后登记）

- 预测：`data/predictions/s2_12_direct_llm_v1/`、
  `data/predictions/s2_12_sun_llm_fallback_v1/`（含 manifest，记录
  llm_calls/max_calls/model/sampling/transport/failure）。
- 评价：`data/results/` 同前缀目录（evaluator v2 / G0.4 parity 口径）。
- 三方法比较与 completion：`outputs/reports/s2_12_*_v*` + transition readiness
  v9（supersede v8）。
- 事件：`record_change.py --event-type experiment_run`（含成本、失败数、hash）。

## 7. 授权句模板（复制即可，用户按需改写后返回）

> 我授权在 S2.12 复杂语料上运行 Direct-LLM（`direct_llm`，36 次）和
> Rules+LLM-Repair（`sun_llm_fallback`，27 次触发）的真实 DeepSeek API，
> 模型仅限 `deepseek-v4-pro`，严格使用 `s2_12_api_preflight_v1.json` 锁定的
> 63 个请求体（单次 ≤ 17,493 bytes、总计 ≤ 749,805 bytes），`--max-calls`
> 硬上限为 108（实际 63），`retry = 0`；总 output tokens ≤ 258,048
> （单次 ≤ 4,096）；总计费 input tokens ≤ 63,000,000；总 USD 成本 ≤ 27.63；
> 运行前重验官方价格；任一模型/输入/source/prompt/config/payload/hash 漂移、
> Gold 隔离违背或任一 cap 将超时必须在调用前硬停止；不得调用 Oracle，不读取
> `.env`。我知晓实际 billing input tokens 与 cost 只能来自真实响应 usage。

## 8. 本申请之外的阻塞（如实记录）

- 本申请只涵盖 S2.12 两个 API arms；S2.13 freeze 与 Stage 3/9 个 GDPR Gold
  Rule Records、S3.7 Oracle 授权均为**独立**事项，不随本申请自动解锁。
- 未获授权前：0 calls、cost=null、不读取 `.env`。
