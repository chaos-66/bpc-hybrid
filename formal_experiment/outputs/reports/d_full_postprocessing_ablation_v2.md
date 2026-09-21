# Direct-LLM 后处理模块 2^3 全组合消融 v2

> 同一批 D-full-0813 原始响应离线重放；新增 API 调用为0。8 个条件枚举 output adapter、span canonicalizer、canonical validator 的全部开关组合；所有150条样本均进入分母。结果属于回顾性开发证据。

## 8 格全组合结果

| 条件 | adapter | canonicalizer | validator | P | R | F1 | ΔF1(vs full) | 成功记录 | 非空记录 | validator观察到无效数 | validator拒收数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `full_postprocessing` | ✅ | ✅ | ✅ | 0.8203 | 0.7289 | 0.7719 | +0.0000 | 150/150 | 148/150 | 0 | 0 |
| `no_output_adapter` | ❌ | ✅ | ✅ | 0.8203 | 0.7289 | 0.7719 | +0.0000 | 150/150 | 148/150 | 0 | 0 |
| `no_span_canonicalizer` | ✅ | ❌ | ✅ | 0.0000 | 0.0000 | 0.0000 | -0.7719 | 1/150 | 0/150 | 149 | 149 |
| `no_canonical_validator` | ✅ | ✅ | ❌ | 0.8203 | 0.7289 | 0.7719 | +0.0000 | 150/150 | 148/150 | 0 | 0 |
| `no_adapter_no_canonicalizer` | ❌ | ❌ | ✅ | 0.0000 | 0.0000 | 0.0000 | -0.7719 | 1/150 | 0/150 | 149 | 149 |
| `no_canonicalizer_no_validator` | ✅ | ❌ | ❌ | 0.6109 | 0.5820 | 0.5961 | -0.1758 | 150/150 | 149/150 | 149 | 0 |
| `no_adapter_no_validator` | ❌ | ✅ | ❌ | 0.8203 | 0.7289 | 0.7719 | +0.0000 | 150/150 | 148/150 | 0 | 0 |
| `no_adapter_no_canonicalizer_no_validator` | ❌ | ❌ | ❌ | 0.6107 | 0.5820 | 0.5960 | -0.1759 | 150/150 | 149/150 | 149 | 0 |

## 分层读法：有效性层 / 安全网层

**有效性层（adapter + canonicalizer；canonicalizer 是主责模块）**

- `full_postprocessing` 的 F1 为 0.7719，成功记录与非空记录分别为 150/150、148/150。
- 只去掉输出适配器时，F1 为 0.7719（ΔF1 +0.0000）；说明在这批固定响应上adapter 没有独立的 F1 增量，不能与 canonicalizer 并列成等价贡献。
- 去掉坐标重锚器但仍保留 validator 时，F1 为 0.0000（ΔF1 -0.7719）；validator 观察到 149 条无效记录并拒收 149 条。坐标有效性是这批完整后处理分数的决定性上游条件。
- 在 validator 关闭的情况下，只去掉坐标重锚器时 F1 为 0.5961；它高于validator 开启时的 0，但低于完整链，说明原始/未重锚记录仍可被评价器部分读出，却不能替代 canonicalizer 的确定性坐标恢复。

**安全网层（validator）**

- 在 canonicalizer 开启时，去掉 validator 的 F1 仍为 0.7719，batch 内观察到的无效记录为 0；分数不变只说明上游在这批响应上已产生合法记录，不能说明 validator 没有安全价值。
- 在 canonicalizer 关闭时，validator 开启的 `no_adapter_no_canonicalizer` 拒收 149 条记录并把 F1 压到 0.0000；validator 关闭的 `no_canonicalizer_no_validator` 保留原始记录并得到 0.5961。这说明 validator 与 canonicalizer 的角色不同：前者是拒收安全网，后者是坐标有效性层。
- 三模块全关时，原始模型输出直接交给评价器：F1 为 0.5960，成功记录 150/150，非空记录 149/150，validator 观察到 149 条无效记录；本批评价器未因形状抛错，若抛错则仅把对应样本记为失败并保留在同一分母，不对原始记录做修补或回填。

## 边界

这些实验只评价固定模型响应之后的模块贡献，不评价模块说明是否改变模型生成。完整链仍作为唯一对照，且必须逐位复现锁定结果。原始响应仍为本地受限证据，报告仅绑定其SHA-256。
