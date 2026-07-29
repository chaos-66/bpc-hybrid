# EStG-150 真实 LLM 调用预算与授权提案（2026-07-18 修订，第四次迭代）

> **状态（截至 2026-07-18）**:用户已指定并授权 DeepSeek
> `deepseek-v4-flash`。正式 run 使用 `thinking=disabled` 完成150/150中文辅助和
> 150/150盲回译，严格 validator 25/25通过并已原子激活 Layer D v2。全过程
> **未**读取 `.env`，Layer A/B/C 未修改，v1 placeholder 保留；Layer E 仅为
> 生成前字节锁临时恢复，并在激活后通过审核工具 service 原样恢复用户已有的
> 第1条英文接受决定。失败 pilot 与正式 run 分目录保留 provenance。
>
> 详见 `docs/ROUTE_LOCK.md` §3 与 `formal_experiment/AGENTS.md`
> 的 "EStG-150 5-layer data model"。

## 1. 调用预算（明确拆分）

| 产物 | 单样本调用数 | 样本数 | 合计 |
|---|---|---|---|
| **Layer D Call A** 中文翻译 + clause/六要素解释 | 1 | 150 | 150 |
| **Layer D Call B** 英文盲回译 | 1 | 150 | 150 |
| **Layer D 合计** | 2 | 150 | **300** |
| **总调用** | — | — | **300** |

> 较旧版（525）削减 225 次：把"每条款中文 gloss"折叠进 Call A 一次性结构化输出，
> 不再按 clause 单独调。

## 2. Batch 计划（pilot + full 用同一 run_id）

`max-calls=300` 是**单 run** 的硬上限；一次 runner 进程就够 150 条。

**关键**:pilot 和 full 必须使用**同一 `--run-id`**。runner 第一次创建
`<run_dir>/run_config.json` 时锁定 14 个字段(provider / model / base_url /
base_url_sha256 / temperature / max_tokens / thinking_mode / membership_payload_sha256 /
layer_a_sha256 / layer_b_sha256 / layer_c_sha256 / prompt_a_sha256 /
prompt_b_sha256 / layer_e_sha256);
恢复时逐项比较,任一不一致直接拒绝。**Layer E SHA-256 是字节级锁**,
不再使用 reviewed/adjudicated 计数作为完整性证明——任何对
`estg_150_human_correction_v1.json` 的字节改动(approved_text_en / decision
/ review_state / notes / clauses / spans)都会拒绝 resume 和 promotion。

| 阶段 | 调用数 | --start-index | --end-index | --pilot |
|---|---|---|---|---|
| pilot | 6 | 0 | 3 | 3 |
| full(继续同一 run) | 294 | 0 | 150 | 0 |
| 合计 | 300 | — | — | — |

## 3. 模型 / Provider（**官方核验**，2026-07-14）

**Provider 契约**:`scripts/run_llm_zh_aid.py` 只实现
**OpenAI-compatible** `/chat/completions` 协议。**不**支持 Anthropic
直连、AWS Bedrock、Azure OpenAI(需要单独 adapter)。禁止列出代码无法
调用的模型。

**Base URL 安全**(2026-07-14 加固):
- 默认仅允许 `https://`(S1)
- URL 必须能被 `urllib.parse.urlparse` 解析(S2)
- 拒绝 userinfo(用户/密码) (S3)——API key 永远在 HTTP Authorization header
- 拒绝 fragment (S4)
- `http://localhost` / `http://127.0.0.1` 必须显式 `--allow-insecure-localhost` (S5)
- base_url 锁入 `run_config.json` 的 `base_url_sha256` 字段(S6)
- resume 时 base_url 变化必须拒绝

下表是 Agent 于 2026-07-14 自行核验的 **2 个 OpenAI-compatible 候选**。
两条**都不参与 B0/H1/D1 最终比较**;建议选 GPT-4.1 mini 做主力(性价比
+ 中文能力好,2025-04 官方发布,knowledge cutoff 2024-06),Llama 3.3 70B
做 OpenRouter/Together 备选(开源、中文 OK、temperature=0 支持)。

### 候选 A：OpenAI GPT-4.1 mini（**推荐主力**）

| 字段 | 值 |
|---|---|
| Provider 官方名称 | OpenAI |
| 精确 model ID | `gpt-4.1-mini`(2025-04-14 发布,API-only) |
| 官方 endpoint | `https://api.openai.com/v1/chat/completions` |
| API 协议 | OpenAI Chat Completions(`/v1/chat/completions`,POST, JSON) |
| temperature=0 支持 | 是(标准参数) |
| 最大上下文 | 1,047,576 tokens(1M) |
| 最大输出 | 32,768 tokens |
| 官方输入价 | **$0.40 / 1M tokens** = $0.0004 / 1K tokens |
| 官方输出价 | **$1.60 / 1M tokens** = $0.0016 / 1K tokens |
| 价格单位 | USD / 1K tokens(为方便阅读换算,官方按 1M 报价) |
| 价格核验日期 | 2026-07-14 |
| 官方来源 | https://openai.com/index/gpt-4-1/ (官方 2025-04 公告) |
| 锚定偏差风险 | 与 D1 主力 `gpt-4o` / `gpt-5` 同家族,但 GPT-4.1 mini 是 2025-04 新发,**不与 D1 评估同模型**,风险可接受;**如果最终 D1 选 GPT-4.1,必须改用非 OpenAI 模型**。 |

**成本预估(本任务 EStG-150)**:
- 单 Call A 输入:DE 原文 + EN 候选 + 六要素 JSON + system prompt ≈ 1500-2200 tokens
- 单 Call A 输出:text_zh + clauses + 六要素解释 ≈ 1000-1800 tokens
- 单 Call B 输入:text_zh + system prompt ≈ 1000-1800 tokens
- 单 Call B 输出:back_translation_en ≈ 600-1000 tokens
- 3 条 pilot(6 calls)输入/输出 token 上限 ≈ 21K / 17K ⇒ **最高 $0.036**(~3.6 美分)
- 150 条(300 calls)输入/输出 token 上限 ≈ 1.05M / 0.84M ⇒ **最高 $2.84**(~$3)

### 候选 B：Meta Llama 3.3 70B Instruct（**OpenRouter/Together AI 备选**）

| 字段 | 值 |
|---|---|
| Provider 官方名称 | Meta(Meta Llama 3.3)+ 通过 OpenRouter/Together AI 等 OpenAI-compatible 网关 |
| 精确 model ID | `meta-llama/llama-3.3-70b-instruct` (OpenRouter 命名) 或 `meta-llama/Llama-3.3-70B-Instruct-Turbo` (Together) |
| 官方 endpoint | `https://openrouter.ai/api/v1/chat/completions` 或 `https://api.together.xyz/v1/chat/completions` |
| API 协议 | OpenAI-compatible `/v1/chat/completions` |
| temperature=0 支持 | 是(标准 OpenAI 参数) |
| 最大上下文 | 128K tokens |
| 最大输出 | 由 provider 配置,通常 8K-32K |
| 官方输入价(2026-07-14 OpenRouter 公开价) | **~$0.59 / 1M tokens** = ~$0.00059 / 1K tokens |
| 官方输出价 | **~$0.79 / 1M tokens** = ~$0.00079 / 1K tokens |
| 价格单位 | USD / 1K tokens |
| 价格核验日期 | 2026-07-14 |
| 官方来源 | https://openrouter.ai/meta-llama/llama-3.3-70b-instruct |
| 锚定偏差风险 | 与 D1 完全无关(Meta 开源 vs OpenAI 闭源家族不同);**强烈推荐**作为 anchor-free 备选。 |

> 备注:Llama 3.3 70B 是 Meta 官方 2024-12 发布,knowledge cutoff 2023-12。
> OpenRouter 公开的 input/output 价格随 provider 路由会有 ±20% 波动;真实
> 调用前必须在 OpenRouter dashboard 重新核验报价(URL 写在 run_config.json)。

**成本预估**:
- 3 条 pilot 最高 ~$0.025
- 150 条最高 ~$1.85

### 用户必须明确选择

**本次 EStG-150 仅使用其中之一**;**不可同时跑两个 provider**。授权句见
§6。

### 本次用户选定：DeepSeek V4 Flash（2026-07-18）

| 字段 | 锁定值 |
|---|---|
| Provider 官方名称 | 深度求索（DeepSeek） |
| runner provider ID | `openai_compatible` |
| 精确 model ID | `deepseek-v4-flash` |
| 官方 base URL | `https://api.deepseek.com` |
| API 协议 | OpenAI-compatible `/chat/completions` |
| thinking mode | `disabled`（显式请求并锁入 `run_config.json`） |
| temperature | `0` |
| max_tokens | `2048` |
| 官方输入价（cache miss） | `$0.14 / 1M tokens` |
| 官方输出价 | `$0.28 / 1M tokens` |
| 调用硬上限 | 300（150 条 × 2 calls） |
| 费用硬预算 | `$1.00` |
| 价格核验日期 | 2026-07-18 |
| 官方来源 | https://api-docs.deepseek.com/quick_start/pricing |

2026-07-18 的首个 3 条 pilot 使用 provider 默认思考模式，出现 1 条
`content=""`（推理消耗输出预算但没有最终 JSON）；该 run 作为失败 provenance
保留，不得 promotion。正式候选 run 必须使用新的 `run_id` 和
`--thinking-mode disabled`，不得与失败 pilot 混合或续跑。

## 4. API key 安全(已实现)

- 禁止 `--api-key <value>`(暴露在 shell 历史 / argv) — 已删除
- 默认:`getpass.getpass("请输入 API key（输入不会显示）: ")`
- 可选:`--api-key-env-name NAME`(只接收环境变量名,值由 env 提供)
- 永远不写进 manifest / run_config / run_summary / 异常 / 日志 / 测试快照
- HTTP 错误不包含 key(测试覆盖)
- 测试用 mock provider,绝不使用真实密钥
- 真实 key 只存在于内存和 HTTP `Authorization: Bearer <key>` header
- runner 内部用 `mask_api_key()` 固定返回 `***`,stdout / stderr / file 永不出现 key

## 5. 真实 LLM runner 的强制要求(2026-07-14 实现完成,**未调用**)

> 入口 `formal_experiment/scripts/run_llm_zh_aid.py` 已实现。`--allow-llm`
> 是唯一开关;dry-run 模式不读 API key。详见脚本顶部 docstring。

R1. **默认干跑**:无 `--allow-llm` 时不调用,exit 0。
R2. **硬调用上限**:`--max-calls N` 是单进程硬上限;150 条 × 2 call = 300
R3. **具体 model** + **provider**:`--model <concrete>` 必填且**非** `annotation-only-default`;`--provider openai_compatible` 必填
R4. **样本范围 / manifest**:必填 `--start-index N --end-index M` 或 `--sample-manifest <path>`
R5. **pilot**:`--pilot N` 只跑前 N 条;同一 `--run-id` 后续用 `[0, 150)` 继续
R6. **同 run_id 续跑**:`<run_dir>/run_config.json` 锁定 14 个字段(包括 thinking_mode 与 layer_e_sha256 字节级锁);**resume 逐项比较,任一不一致直接拒绝**
R7. **chunk + resume**:从 `manifest.jsonl` 跳过 status=ok 的 sample；补跑成功行追加后，runner 原子重排 `layer_d_v2.jsonl` 为 Layer A 顺序，拒绝重复 sample_id
R8. **失败重试 3 次**指数退避
R9. **输出只写** `data/development/estg/llm_candidate_runs/<run_id>/`;**禁止** data/input, data/gold, data/predictions, data/results, outputs/reports
R10. **Layer A/B/C/E 完全不动**
R11. **API key 安全**:`--api-key <value>` 已删除;`getpass` 或 `--api-key-env-name`;绝不写日志/异常/manifest
R12. **Call B 盲回译**:runtime assertion 拒绝在 Call B payload 出现德文/英文候选;test 已覆盖
R13. **无并发 / 无重试 > 3**
R14. **OpenAI-compatible 唯一**:Anthropic / Bedrock / Vertex 暂不实现
R15. **base_url 安全**:HTTPS only(localhost 例外需 `--allow-insecure-localhost`);拒绝 userinfo / fragment;base_url 锁入 run_config.json
R16. **thinking mode 可复现**:`provider_default|enabled|disabled` 显式入参并锁入 run_config；仅在非默认值时向兼容接口发送 `thinking.type`

## 5. 授权命令模板(Stage B,用户口头授权后)

```powershell
# === 同 run_id 必须复用 ===
$RUN_ID = "run_20260714_layerd"
# base-url 由 §3 选定;默认 https://api.openai.com/v1;若用 OpenRouter
# 或 Together 等,改为对应 https 端点。**禁止** http://(localhost 除外)。
$BASE_URL = "https://api.openai.com/v1"

# === 关键:密钥绝不出现在命令行 ===
# 方式 1:交互输入(getpass 隐藏)
python formal_experiment/scripts/run_llm_zh_aid.py `
  --allow-llm `
  --provider openai_compatible `
  --model <§3 选定 model> `
  --base-url $BASE_URL `
  --max-calls 6 `
  --start-index 0 --end-index 3 `
  --pilot 3 `
  --run-id $RUN_ID
# 提示 "请输入 API key（输入不会显示）: " 后用键盘输入

# 方式 2:env 变量
$env:MY_OPENAI_KEY = "sk-..."
python formal_experiment/scripts/run_llm_zh_aid.py `
  --allow-llm `
  --provider openai_compatible `
  --model <§3 选定 model> `
  --base-url $BASE_URL `
  --max-calls 6 `
  --start-index 0 --end-index 3 `
  --pilot 3 `
  --api-key-env-name MY_OPENAI_KEY `
  --run-id $RUN_ID

# === Pilot 验证(允许 N=3 不完整) ===
python formal_experiment/scripts/validate_layer_d_v2.py `
  --run-dir formal_experiment/data/development/estg/llm_candidate_runs/$RUN_ID `
  --allow-partial-pilot 3

# === 继续同一 run_id,范围 [0, 150) ===
python formal_experiment/scripts/run_llm_zh_aid.py `
  --allow-llm `
  --provider openai_compatible `
  --model <§3 选定 model> `
  --base-url $BASE_URL `
  --max-calls 300 `
  --start-index 0 --end-index 150 `
  --api-key-env-name MY_OPENAI_KEY `
  --run-id $RUN_ID

# === 全量 150 严格验证(无 --allow-partial-pilot) ===
python formal_experiment/scripts/validate_layer_d_v2.py `
  --run-dir formal_experiment/data/development/estg/llm_candidate_runs/$RUN_ID

# === 原子 promotion(v1 placeholder 永久保留;v1 字节级锁) ===
python formal_experiment/scripts/promote_layer_d_v2.py `
  --run-dir formal_experiment/data/development/estg/llm_candidate_runs/$RUN_ID

# === GUI 重新加载中文辅助(无需重启) ===
# 在 estg150_review_tool.py 里点 "重新加载中文辅助" 按钮

# === 重新运行 audit 与完整测试 ===
python formal_experiment/scripts/audit_project.py --with-tests
python formal_experiment/scripts/validate_human_correction.py

# === 真实调用事件(必须 llm_api=authorized_called) ===
python formal_experiment/scripts/record_change.py `
  --purpose "Layer D real LLM run (run_id=$RUN_ID)" `
  --gold audit_read_only `
  --llm-api authorized_called `
  --artifacts created_no_overwrite `
  --notes "model=<§3> prompt_sha256=... calls=... cost=USD<实测>"
```

## 6. 失败重试与跳过策略

- 单 sample 失败 3 次后,写 `manifest.jsonl` status=failed;runner 继续下一条
- 整个 batch 失败率 > 5% 时,runner 退出并要求用户决定
- runner **绝不**重写已生成的 v2 内容
- **promoter 是唯一激活方式**——`python scripts/promote_layer_d_v2.py
  --run-dir <run_dir>`;**禁止**手动 cp / 手动改 active_path / 手动
  编辑 configs/estg150_layer_d.json
- promotion 失败**事务回滚**:v2 与 config 完整恢复到 pre-promotion bytes;
  v1 永远不动;v1 SHA-256 在前后都校验

## 7. manifest 字段(每条调用)

每行 `manifest.jsonl` 至少包含:
- `sample_id, legacy_record_id, run_id, status, provider, model, base_url`
- `call_a_prompt_sha256, call_b_prompt_sha256`
- `call_a_prompt_tokens, call_a_completion_tokens, call_a_elapsed_ms, call_a_retries`
- `call_b_prompt_tokens, call_b_completion_tokens, call_b_elapsed_ms, call_b_retries`
- `call_b_payload_clean: bool` (Call B 盲回译证明)
- `timestamp_utc`
- `error_type, error` (失败时)
- **不**包含 API key / Authorization / Bearer / X-Api-Key

## 8. 后续审计与回滚

- 每次真实 LLM 运行 = 一次 `record_change.py --llm-api authorized_called` 事件
- promotion 失败**事务回滚**(v2 + config 完整恢复,v1 不动)
- Layer E 字节级锁:任何对 `estg_150_human_correction_v1.json` 的改动
  都会拒绝 resume 和 promotion

## 9. 不在此次真实 LLM 范围内

- 修改 Layer A/B/C/E
- 创建第二套 150;重新抽样
- 写 `data/gold/` / `data/input/` / `data/predictions/` / `data/results/`
- 改 references/ 或 archive/
- 读取、打印、修改 `.env`
- 在命令行、argv、日志、异常、HTTP 错误里出现 API key

## 10. 安全与 claim 边界

- 论文中**不得**声称 LLM-assisted Gold 等同于 "纯人工从零标注"
- 论文中**必须**说明 Layer D **仅辅助理解**,**不**参与 Gold / 评测
- 真实 LLM 调用的 prompt SHA-256 / cost / run_id / base_url 都必须记录并在论文披露
- API key 永远不会出现在 record_change 事件 / 任何文件 / 任何日志

## 11. 用户授权句(用户必须完整发出,Agent 才进入 Stage B)

```
我授权使用【§3 选定的精确 model】(提供商:【§3 选定的 provider】;
价格核验日期:【§3 表格里的日期】;官方端点:【§3 选定的 base_url】;
输入价/输出价:【§3 表格里的 USD/1K tokens】;来源链接:【§3 表格里的
官方来源 URL】)为同一套 EStG-150 生成 Layer D 中文辅助和英文盲回译;
使用同一个 run_id 先运行 3 条 pilot,自动验证通过后继续完成同一 run
的剩余记录;最多 300 次调用,最高预算【金额】美元;不得修改 Layer A/B/C/E,
不得读取 .env,不得创建第二套 150。
```

## 12. 当前状态(2026-07-14,第三次迭代后)

| 检查项 | 状态 |
|---|---|
| 真实 runner 实现 + API key 隐藏输入 | **已实现** |
| base_url 安全(https-only + localhost 例外) | **已实现**,锁入 run_config |
| run_config 13 字段锁(包括 layer_e_sha256 字节级锁) | **已实现** |
| run_config 拒绝 resume drift | **已实现** |
| strict validator(20+ checks,共享 pure-function 模块) | **已实现** |
| atomic promotion(预快照 + 事务回滚) | **已实现** |
| GUI 严格 layer_d_validator 复用 + v1 placeholder pending 状态 | **已实现** |
| 官方核验的 OpenAI-compatible 模型候选 | **已填入 §3**(GPT-4.1 mini + Llama 3.3 70B) |
| 任何真实 LLM 调用 | **否** —— 待用户发出 §11 完整授权句 |
| 选定具体模型 / provider | **否** —— 等用户回 §11 句 |
| 价格核验 | **§3 表格已 Agent 核验** —— 真实调用前用户**必须**再核验一次 |
| Layer D v2 | **未生成**; v1 placeholder 仍是 active |
| GUI 工具对 Layer D | 顶部 banner + 「重新加载中文辅助」按钮(走严格 validator) |
| 数据流向 | 仅写 `data/development/estg/llm_candidate_runs/<run_id>/` |
| Event 26 | **待写**(Stage A 收尾) |
