# SEP-C3 Definition Targeted Budget v1

- Status: **prepared_not_run**
- Suite: `SEP-C3-DEFINITION-TARGETED-REFINEMENT-001`
- Panel N: **42**
- Planned calls: **84** (BASE=42, R_DEF=42; A=0 new calls)
- Retry: **0**; failure policy: **One recorded send per scheduled sample/arm; transport and parse failures persist in the denominator; no result-dependent retry.**
- Estimated input tokens: **148341**
- Input token cap: **296682**
- Max output tokens per call: **4096**
- Total max output tokens: **344064**
- Peak estimated USD: **1.55830356**
- USD cap: **1.75411368**

## Model/config

- Model: `deepseek-v4-pro` / `DeepSeek-V4-Pro-0813`
- Inference: `{"temperature": 0.0, "top_p": 1.0, "max_tokens": 4096, "retry": 0, "stream": false, "thinking": {"type": "disabled"}, "response_format": null}`

## Prompt bindings

| Arm | System | User | Composition |
|---|---|---|---|
| BASE | `9db8893c75af4c306f5f5142ea77b6c93b6a2bae79a72ba8dd0f2b3ca1985d4f` | `ff181879858f08641b40a3e8799fa32e16235f70544b809cac7fddf9962797f5` | `3100c8521f3ad4a0a313293d4facdd37c92dccf8661e6021875750c58926da11` |
| R_DEF | `95c234ab44357411fb493f7b3ed46a29e76ada91f02ce3d2c1cd6b7af0496843` | `ff181879858f08641b40a3e8799fa32e16235f70544b809cac7fddf9962797f5` | `585d9a81116d8fb1b1cf1858b55e4a67457ca9886dbd0487f7f0d7474f5e8b07` |

## Price snapshot

- Input (cache miss): `1.32` USD/M
- Output: `3.96` USD/M
- Source/verified: `https://api-docs.deepseek.com/zh-cn/quick_start/pricing/` / `2026-08-30T00:00:00Z`

## Authorization

- Required: `True`
- Status: `NOT_AUTHORIZED`
