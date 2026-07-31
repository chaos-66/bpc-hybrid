# S2.8D-R2: H1 Canary Span/Offset Offline Forensics

**Task**: S2.8D-R2 — Gold-blind、offline、forensic-only 分析单次 H1 canary 的
span/offset contract 失败。

**Git commit**: `4e4e655a520d47605522e83c973132f94e05871c`（任务开始时的 HEAD）

**Safety**: 0 real API calls；Gold 未读；Layer E 未读；真实 canary 证据未修改；
counterfactual 仅诊断用途，从未写入任何 prediction；P/R = not_computed。

---

## 1. 证据与绑定核验

| 项 | 值 |
|---|---|
| canary run_id | `s28d_r1_h1_canary_v1` |
| canary manifest SHA-256 | `022d31a16a4fc2c93e0d22bde43d92bd688964a9ab2fd57e4623afe5c3eeb0cc` |
| transport capture SHA-256 | `f880784114d41e76944a6c69948297301904bd1e6f86b3cdcb86c70efcd2ad1d` |
| 原始 response body SHA-256（仅记录） | `2917f41308e0845e0c0f94fa2f12b7d9c6dba60ec89a710e4e201f98d71970b9` |
| message.content SHA-256 | `0d076122c0d7367fe667ac2f1626e86a97e415fab89af886e015b1aa4590b779` |
| source_text SHA-256 / 长度 | `92b044cdc7b580cc5cd3f671d01a90f9c1ed0a402b87f43f236b6119cad9fd84` / 212 chars（纯 ASCII） |
| B0 prediction SHA-256 | `57f3564baa573735b55bc252554698236b3eb744a657090abe849cd772b4bcb4` |
| prompt SHA-256（masked_selected_v5） | `065005189ced3179ff4069d016c7d0ca892ce4992707834e09142efc0472c391` |
| 模型 requested/resolved/returned | deepseek-v4-flash / deepseek-v4-flash / deepseek-v4-flash |
| API 调用数 / retry | 1 / 0 |
| usage | prompt 1305 + completion 436 = 1741 tokens |

全部 13 项绑定检查通过（capture 行内 hash、manifest capture hash、调用数=1、
gate=false、模型身份、extraction status、reasoning/tools 缺失、B0 绑定、
prompt 绑定、envelope 绑定、usage、拒绝码、拒绝 span 交叉核对）。Capture 未含
凭据；raw response 按设计未保存。

诊断产物 `diagnostics.json` SHA-256：`01ead7a602d66fb48bdfdae76c9241d14a23b4daf6a0ab959fd1fed3bb8a5b69`
（跨输出目录 byte-identical，重复运行不变）。

## 2. 逐 span 脱敏诊断（sample `estg_000021`, clause `estg_000021.c1`, clause_span [0, 212]）

三个被拒绝 span 全部满足：**文本在 source_text 与 clause 窗口内均恰好出现一次
（exact match count = 1）**，即文本本身正确，只有坐标错误。

| field path | proposed [start, end] | text 长度 (char/utf8) | text SHA-256 | slice 相等 | 唯一 exact match | start Δ | end Δ |
|---|---|---|---|---|---|---|---|
| `modality.evidence[0]` | [0, 99] | 95 / 95 | `147907cf…e63ff` | false | [0, 95] | 0 | **+4** |
| `actors[0]` | [55, 99] | 46 / 46 | `381a79d8…275c` | false | [49, 95] | +6 | **+4** |
| `conditions[0]` | [100, 211] | 110 / 110 | `aa23d19d…5b95e` | false | [97, 207] | +3 | **+4** |

- 坐标验证：三个 span 的 `source_text[start:end]` 均不等于 proposed text
  （canonical `reference_mismatch` 的直接原因）。
- occurrence 分析：全部为唯一匹配（无 zero match、无 ambiguous match）。
- 错误分类（有证据、无猜测）：
  1. **正确文本，错误坐标**（三 span 一致；证据：唯一 exact match 存在）。
  2. 排除 Unicode/code-point 混淆（证据：source 与 proposed text 均为纯 ASCII，
     byte 长度 == char 长度）。
  3. 排除 clause-local/global frame 混淆作为可证明原因（证据：本样本
     clause_span.start == 0，两个 frame 重合；无法区分，标记为限制）。
  4. 观察：三 span 的 `end` 均恰好超出唯一匹配终点 **+4 字符**（尾部 4 字符
     均为非字母数字的定界/词尾片段）；`start` 偏移 +0/+6/+3。这一致模式指向
     **end 边界包含算术错误**，但 n=1 样本不能证明。

## 3. Strict replay（当前 decoder → parser → validator → atomic merge）

`--offline-transport-replay`，response_body 为围绕 byte-identical 的 captured
`message.content` 重建的 chat.completion envelope（原始 raw body 按设计从未保存）。

- 结果：**与真实 canary 完全一致** —
  `canonical_invalid=1, reference_mismatch=1`，accepted=0，effective_patch=0，
  changed=0，valid_response=1，`h1_non_identity_gate=false`，H1 == B0
  （prediction hash 与 identity 字段逐项核对不变）。
- 同一参数连续重放 byte-identical（manifest SHA-256
  `8f6459b75deb18750ab45df5f6555f9b4354750f5943240754945f2df34d9580`）。

## 4. Diagnostic-only counterfactual（仅诊断，非真实结果）

规则：仅当 proposed span text 在原始 clause 窗口内存在**唯一 exact match** 时，
只修正 start/end；其余（text、id、field、label、relation、absent 标记）一律不动；
任何 zero/ambiguous match 即 fail closed。修正后进入**同一个** canonical
validator 与同一个 atomic merge。

修正：[0,99]→[0,95]、[55,99]→[49,95]、[100,211]→[97,207]。

- 结果：**schema valid + cross-field valid**；merge status = `accepted`；
  `effective_patch=true`；changed_fields =
  actor_action_map/actors/conditions/constraints/modality；
  prediction_changed=1；`h1_non_identity_gate=true`；
  identity 字段（sample_id/source_id/source_text/clause_id/clause_span）全部不变。
- merged prediction SHA-256（截断）`5bcf26d7…`；manifest SHA-256
  `543d030f2ead50240f8c7f88274255050095d033ad69e5c98deea09344575746`。
- 该 counterfactual **不改变真实 canary 结果**（strict 原结果单独保留），
  不构成 canary 成功。

## 5. Prompt coordinate contract 审查（只读，未修改）

`rule_first_llm_fallback_masked_prompt`（v5）：

- **明确存在**：硬性要求 8 —— 每个 span 必须在既有 clause_span 内，且
  `text == source_text[start:end]`；evidence/span 文本必须逐字来自 source。
- **明确缺失**（仅由示例隐含）：坐标单位（Python/Unicode code point）、
  0-based、end-exclusive。
- **歧义**：坐标 frame 混用两种语言 —— “inside the existing clause_span”
  （clause-local 表述）与 `source_text[start:end]`（global frame）；从未说明
  offset 是相对完整 source_text 的全局值、而 membership 由 clause_span 界定，
  也未说明如何加上 clause_span.start。
- **缺失**：输出前逐 span 自检指令。
- **masked 字段隐藏信息**：未发现。source_text 与不可变 clause_span 始终未
  遮蔽；v5 只遮蔽 B0 自身 assignment（anti-anchoring 设计），不隐藏任何计算
  offset 所需信息。

## 6. 结论与下一步

**判断：情况 A。**

证据链：

1. 全部 3 个 invalid span 的文本在 clause 窗口内都有**唯一 exact reanchor**；
2. counterfactual（只修正坐标、其余不动）通过同一 canonical validator、
   原子 merge 成功、产生 effective patch、gate=true、identity 不变；
3. strict replay 证明当前 pipeline 对真实证据的拒绝行为与 canary 完全一致，
   拒绝来自 span 坐标而非 schema/transport/parser。

**唯一推荐下一任务（本轮不得实现）**：

> **S2.8D-R3：实现 fail-closed unique exact-text coordinate canonicalization** —
> 在 atomic merge 前，对被拒绝 span 尝试仅在 clause 窗口内唯一 exact-match 的
> 坐标重锚定；zero-match / ambiguous-match 仍照旧整体拒绝。prompt 本轮不改。

限制声明：n=1 sample/1 clause/3 spans；clause_span.start==0 使 frame 混淆在本
样本上不可区分；+4 end 越界模式支持 end-boundary 假设但不可证明；counterfactual
只证明 pipeline 接受修正坐标，不证明模型能生成正确坐标。

## 7. 产物索引（unversioned，`outputs/development/s28d_r2_forensics/`）

| 产物 | 用途 |
|---|---|
| `diagnostics.json` | 全部脱敏诊断 + 绑定核验 |
| `transport_replay_row.jsonl` | strict replay 输入（SHA-256 `96f8bbdc…`） |
| `counterfactual_responses.jsonl` | counterfactual replay 输入（SHA-256 `ddf8c54c…`） |
| `strict/manifest.json` | strict replay 结果 |
| `counterfactual/manifest.json` | counterfactual 结果 |
