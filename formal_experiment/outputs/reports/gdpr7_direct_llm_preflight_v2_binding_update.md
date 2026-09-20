# GDPR Direct-74 preflight binding update (v1 -> v2)

- Classification: `ACCEPTED_NON_SEMANTIC_IMPLEMENTATION_BINDING_UPDATE`
- Scope: `gdpr7_direct_llm_v1:74`
- Changed binding: `src/bpc_hybrid/h1_transport.py`
- Old SHA-256: `f9efba42509eb85be522a45ee9ee4cf728ec1437945dfb4189bd7f4cc0d45b77`
- New SHA-256: `5e54a41fa48c01377295b2ac6422e27852a40dc4fbd5cb7df90d6651ddfe8be9`
- Reason: post-freeze `_extract_usage` cache-token accounting support only.

## Verified non-effects

- Request construction: unchanged.
- Request serialization: unchanged.
- Endpoint/model/configuration selection: unchanged.
- Retry/send behavior: unchanged.
- Response-content extraction used by the parser: unchanged.
- Only token-usage/accounting instrumentation changed.

## Request-body recheck

- 74/74 sample membership/order unchanged.
- 74/74 request-body SHA-256 unchanged.
- 74/74 request-body UTF-8 byte counts unchanged.
- 74/74 local proxy token counts unchanged.
- Prompt SHA-256 unchanged.
- Model/decoding configuration unchanged.

## Versioned artifacts

- Historical preflight v1 preserved: `outputs/reports/gdpr7_direct_llm_preflight_v1.json` SHA-256 `602bfdfb4adbf7f2c401689ed25e3d4226bc0fdb82a7bc65b4fbc6baf8f8c56d`
- New preflight v2: `outputs/reports/gdpr7_direct_llm_preflight_v2.json` SHA-256 `f8e827aaac004fb363fbc905b7d51fc2f4d30c7bb93095ed9b187ed2a2329ef7`
- Historical contract v1 preserved: `configs/ablations/gdpr7_direct_llm_execution_contract_v1.json` SHA-256 `281e4874e6487434de6e48f40bc830cda960c53a5fc650b8984e5e132d3989eb`
- New contract v2: `configs/ablations/gdpr7_direct_llm_execution_contract_v2.json` SHA-256 `7c1b168d5d1a5a2223d3ce2c2ff9664b7c39c4c879e8501df77e2227568ab4a1`
- Historical authorization event v1 preserved: `configs/gdpr7_direct_llm_authorization_event_v1.json` SHA-256 `d6689c0ef2fcc6336a29a88b9d7bc172299a771a751b75de9af5d6e71df0bde5`
- New authorization event v2: `configs/gdpr7_direct_llm_authorization_event_v2.json` SHA-256 `8a3fc6ec67f96004054b0f6d262bcf22048b222a04b298af314215feee61e972`
- Authorization sentence SHA-256 preserved: `27426de7a03cc8c75eae5d57ebbd11860b2ce229f7afdd55bce4fa9a08bc0dd6`

## Validator result

- `load_report` v2: pass
- `validate_contract` v2: pass
- `validate_authorization_event` v2: pass

No API call was made. No raw text, Gold, prompt, or Stage-3 artifact was modified.
