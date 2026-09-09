# 真实 LLM 对照批次：离线就绪报告（零 API）

**报告**：`s2_llm_batches_offline_readiness_v1`

## 批次

| 批次 | 声明调用数 | 方法 | 授权 |
|---|---:|---|---|
| s2_12_batch_a | 63 | direct_llm 36 + sun_llm_fallback 27 | authorized 2026-09-07 (off-peak, retry=0) |
| gdpr7_batch_b | 74 | direct_llm (GDPR scope gdpr7_direct_llm_v1:74) | authorized 2026-09-07 (off-peak, retry=0) |

## 离线检查

| 检查 | 结果 |
|---|---|
| 授权/合同/预检资产齐备 | True |
| 声明调用数与预检一致 | True |
| GDPR 74 次假传输全流程 | True |
| 假传输零计费 | True |
| 无合同文件时真实运行被拒 | True |
| 假胶囊被 promotion 拒绝 | True |
| 无凭据时 S2.12 真实运行被拒 | True |

## 阻塞

- 是否阻塞：**True**
- 原因：process-environment credentials absent; both runners read only the process environment and never the project .env

缺失项：

- `FAIL provider is mock or not enabled (process env only)`
- `FAIL model 'mock' != 'deepseek-v4-pro'`
- `FAIL base_url None != 'https://api.deepseek.com/v1' (required by the GDPR executor and the locked payloads)`
- `FAIL API key absent (BPC_HYBRID_LLM_API_KEY or BPC_HYBRID_DeepSeek_API_KEY in the process environment)`
- `FAIL max_tokens 1024 != 4096 (locked recipe)`

## 结论

- 离线准备完成：**True**
- 真实调用已发生：0
- 剩余真实调用：137
- 阻塞于：process-environment credentials

> No S2.12 / GDPR real-LLM result exists yet; the Direct-LLM GDPR arm capsule data/predictions/gdpr7_direct_llm_v1 does not exist, so the downstream LLM-vs-rules Stage-3 comparison cannot be run on real Direct-LLM predictions.

零 LLM/API/网络；未写入 `data/`。
