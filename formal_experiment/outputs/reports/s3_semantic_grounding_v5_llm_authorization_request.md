# V5 fallback authorization request (zero API preflight)

- Scope: `S3-SEMANTIC-GROUNDING-V5-FALLBACK`
- Provider/model: `openai_compatible` / `deepseek-v4-pro`
- Calls: **22**; retry=0; off-peak windows (UTC): `[[0.0, 1.0], [4.0, 6.0], [10.0, 24.0]]`
- Expected input tokens: `69032`; input cap: `138064`
- Output cap: `11264` (512 per call)
- USD cap: `0.2`; RMB cap at 7.2: `1.44`
- Candidate pack hash: `915750b068a45f98be56b0e48c6ef0722d95e8d5bda870cbcdb1f1f4e2ae54f2`
- Request-set hash: `fdd72c0191afdb24975550d9297951385aedca91d69c3722952a6f49eb123c53`
- Matching existing authorizations: `0`

## Exact authorization sentence

我授权在 S3-SEMANTIC-GROUNDING-V5-FALLBACK 范围内使用 openai_compatible/deepseek-v4-pro 对已冻结的 22 个 fallback items 执行真实 API 调用；retry=0；仅在低峰时段运行（UTC 00:00-01:00 / 04:00-06:00 / 10:00-24:00）；输入 token 上限 138064；输出总 token 上限 11264；总费用上限 USD 0.20 / RMB 1.44；请求集 hash=fdd72c0191afdb24975550d9297951385aedca91d69c3722952a6f49eb123c53；候选 pack hash=915750b068a45f98be56b0e48c6ef0722d95e8d5bda870cbcdb1f1f4e2ae54f2。

Sentence SHA-256: `f6eda1b245c078d3def5e3d0b736df5a60eb75b2de97ecc4da984471abfc38da`

Old v2 scope/hash authorizations are not reused.
