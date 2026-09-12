# LLM fallback authorization request (S3-SEMANTIC-GROUNDING-V2-FALLBACK)

- Provider/model: `openai_compatible` / `deepseek-v4-pro`
- Fallback items / calls: **20 / 20**
- Retry: `0`; off-peak only: `True`
- Expected input tokens: `62333`; input cap: `124666`
- Max output tokens per call: `512`; total output cap: `10240`
- USD cap: `0.18`; RMB cap (at 7.2): `1.3`
- Request set hash: `1ac203ec1b2bc4e4a4ac3b057788abe79b9fbf143b981ea635dc238925bdaf04`
- Candidate pack hash: `512b06b8f847caac98e53059570e5473017cb8da2a9620ae394fd9fd02d5102e`
- Execution command: `python formal_experiment/scripts/run_s3_semantic_grounding_llm_v1.py --real --authorization outputs/reports/s3_semantic_grounding_v2_llm_authorization.json`

## Exact one-sentence authorization

我授权在 S3-SEMANTIC-GROUNDING-V2-FALLBACK 范围内使用 openai_compatible/deepseek-v4-pro 对已冻结的 20 个 fallback items 执行真实 API 调用；retry=0，仅低峰运行，总费用上限 USD 0.18 / RMB 1.30，输入 token 上限 124666，输出总 token 上限 10240，请求集 hash=1ac203ec1b2bc4e4a4ac3b057788abe79b9fbf143b981ea635dc238925bdaf04，候选 pack hash=512b06b8f847caac98e53059570e5473017cb8da2a9620ae394fd9fd02d5102e。

Sentence SHA-256: `fa6811de304ce81ddf620181721b28dd64a0cc26a32fd9aa01ca66a64602fa52`
