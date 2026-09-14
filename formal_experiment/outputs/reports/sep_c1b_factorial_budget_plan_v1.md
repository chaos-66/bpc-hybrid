# SEP-C1-B 完整 E/S/J 2^3 Prompt 消融预算材料（2026-09-14）

**状态**：prepared_not_run；真实 LLM/API=0，网络调用=0，未运行任何组合。
**边界**：只准备因素、组合、分析协议与预算授权材料；未修改可执行 prompt、检查器
或 Gold，所有 000-111 真实结果保持待运行。
**上级文档**：`paper/ABLATION_MATRIX.md` SEP-C1-B 节；`docs/API_AUTHORIZATION_REQUEST.md`
第 14 节。

## 1. 因素与共同接口

- E＝语义输入输出示例：冻结 v6 prompt 的 `## Examples` 六个合成示例；E=0 用
  non-semantic structural template 替换，保留 JSON 输出形状。
- S＝详细六要素语义规则：system prompt 规则 9-14、15-19、25-27 及其标题；
  S=0 只删除这些文本。
- J＝显式 JSON/结构格式说明：合同介绍、`Output discipline` 与规则 1-5、规则 24
  schema-only 措辞、canonical JSON 措辞；J=0 只删除这些纪律。
- 共同最低接口 C（所有组合保留）：角色/任务句、规则 6-8、规则 20-23、规则 24
  语义部分、input envelope；E=1 的示例或 E=0 的结构模板始终提供可解析 JSON
  形状，因此移除 J 不破坏共同输出契约。

## 2. 已有证据与不可拼接原因

现有 2026-08-30 批次提供四条配置匹配的单因素臂：`111` D-full-0813、
`011` D-no-semantic-examples-0813、`101` D-no-semantic-guidance-0813、
`110` D-no-explicit-json-contract-0813，各 150 calls，共 600 calls。它们的
prompt/input/evaluator/model release 匹配，可作单因素历史证据和构造校验。

但旧四臂恰是四个至少两个因素为 1 的格子，且只来自一个旧批次、每臂 1 次；
把旧四格与缺失四格拼成 2^3 会让批次/时间与高阶层因子模式混杂。主推荐预算
因此不把它们扣为因子单元。若仅追求组合覆盖，非推荐复用变体会扣除这 600 calls
（配置与状态复核通过时），新增 1800 calls；本材料不作为主授权范围。

## 3. 推荐设计与样本

- 同一批次 8 组合 x 150 条固定 EStG-150 样本 x 2 repeats = **2400 新增 calls**。
- 输入：`data/input/estg150_formal_inference_input_v2.json`；SHA256
  `52a73aa1109970b6c4fbc17214b0828ed0dd64b330001e884cdc803b1ce81dc2`。
- Gold/evaluator：evaluator `sun_literal_overlap_evaluation@2.0.0`，配置 SHA256
  `352113b568c6075c8b01dafa5fdf2e5ab4a1454bb10933cd2f9c27f5c008cc3f`；真 Gold
  以冻结 commit `56d2b03` 的 Layer E + membership 构建，正式发布件
  `estg150_formal_gold_v1.json` SHA256
  `c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100`。
- 采样：`deepseek-v4-pro`（`DeepSeek-V4-Pro-0813`），temperature=0、top_p=1、
  max_tokens=4096、retry=0、stream=false、thinking disabled、response_format=null；
  仅 off-peak；API arm 不读 Gold。
- 重复：2 次 provider-level 复跑；主模型 16 个观测、8 参数、残差自由度 8。
- 可选第三重复不在本次授权内；若失败率或重复差异门控触发，再单独申请 +1200 calls。

## 4. 预算上限表

| 方案 | 新增 calls | 预计 input | input cap(x1.5) | output cap(4096/call) | USD cap(peak) | CNY off-peak envelope | 预期成本(外推参考) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 推荐：同批次 8x150x2 | 2400 | 8,687,550 | 13,031,325 | 9,830,400 | 67.36 | 229.63 | $16.11 / 54.92 元 |
| 非推荐复用变体（扣旧 600） | 1800 | 5,841,713 | 8,762,570 | 7,372,800 | 48.92 | 166.76 | $11.39 / 38.84 元 |
| 可选第三重复（全 8x150x1） | +1200 | 4,343,775 | 6,515,663 | 4,915,200 | +33.68 | +114.81 | +$8.05 / +27.46 元 |

单臂 input estimate（每 150 calls，UTF-8 body bytes/3）：
`111 880,149`、`011 432,849`、`101 703,149`、`110 829,690`、
`100 652,495`、`010 383,395`、`001 255,849`、`000 206,199`。
缺失四臂为确定性组合后的计划估算，创建 prompt 后必须重新渲染替换。

## 5. 计算依据、价格与扣除规则

- input = 渲染全部请求 JSON body 的 UTF-8 字节数/3 向上取整；
- input cap = 预计 input x 1.5；output cap = calls x 4096；
- USD/CNY 上限 = 按价格快照计算 caps，再 x 1.2 向上取整；
- 价格来源：`https://api-docs.deepseek.com/zh-cn/quick_start/pricing/`；
  peak：input cache-miss 1.32 USD/1M、output 3.96 USD/1M；off-peak CNY：
  input 4.5、output 13.5 每 1M。快照日期 2026-08-30（项目合同记录），
  **2026-09-14 本轮未联网复核**；执行前必须重新核验，价格或模型 release 变化
  则停止并重新授权。
- 预期成本使用既有 450-call 批次实际 usage 按 E/S/J 因子线性外推，只作参考，
  不是硬上限。
- 旧结果仅在状态完成且 prompt/input/evaluator/model release/采样参数全部匹配时
  才可扣除；主推荐不扣旧 600，因为设计状态不满足均衡 2^3；复用变体才扣 600。

## 6. 分析协议

主指标为 arm/repeat 的 `overall.f1`；次指标为六字段 P/R/F1、失败数、合法输出率。
失败包括 API error、空响应、非 JSON、schema/cross-field invalid、identity mismatch
和无法进入 canonical six-field record；失败保留在 150 分母中。按 E,S,J 编码拟合
全因子模型，主效应为边际均值差，交互为差中之差；按 150 个 sample_id 做整簇
bootstrap（B=10,000）报告 95% CI 和 repeat-level 离散度。若失败率 >5% 标记不稳定，
>10% 暂停该组合解释；不做未预注册的 p 值声明。

## 7. 授权草案与下一步

授权草案（用户亲自逐字发出后才创建授权事件；本轮不创建）：
`我明确授权执行 SEP-C1-B 完整 E/S/J 2^3 Prompt 消融实验：2400 calls，模型
deepseek-v4-pro（DeepSeek-V4-Pro-0813），temperature=0、top_p=1、max_tokens=4096、
retry=0；固定 EStG-150 v2 输入与冻结 Stage 2 Gold/evaluator；USD 硬上限 67.36
（peak）、off-peak 229.63 元；仅在北京时间闲时执行，超过任一上限立即停止，不自动续跑。`

下一实现批次（仍未执行）：新增缺失四臂、八臂 builder/manifest、runner 8x2 扩展、
重新渲染 token 预算、零 API dry-run；通过后等待用户授权。所有 000-111 结果在真实
manifest 和评价出现前保持待运行。

## 8. 主要来源

- `paper/ABLATION_MATRIX.md` SEP-C1-B 节；
- `configs/ablations/d1_prompt_factorial_execution_contract_v1.json`；
- `prompts/sun_compat/ablation_v2/manifest.json`；
- `outputs/reports/d1_prompt_factorial_budget_v1.json`；
- `outputs/development/d1_prompt_factorial_ablation_v2/execution_summary.json`；
- `outputs/reports/d1_prompt_factorial_results_v1.json`；
- `configs/winter_stage3_development_v1.json`（Winter 三层命名边界）；
- `outputs/reports/s3_c36_target_paired_v2.md`（Winter-style baseline 口径）。
