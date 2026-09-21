# SEP-C3 Definition Targeted Authorization Request v1

- Suite: `SEP-C3-DEFINITION-TARGETED-REFINEMENT-001`
- Provider/model: `openai_compatible` / `deepseek-v4-pro`
- Unique panel samples: **42**
- New calls: **84** (BASE=42, R_DEF=42, A=0)
- Retry: `0`
- Expected input tokens: `148341`; input cap: `296682`
- Max output tokens per call: `4096`; total output cap: `344064`
- Peak estimated USD: `1.55830356`; USD cap: `1.75411368`
- Panel SHA-256: `8ba4517f21402566d61364e86a5516e0ea89f1f82a32781b303eb7a53d97ec61`
- Schedule SHA-256: `ed4b12fe5de27ae9611759e0aedb292cfa633bc853b07df867e3fb4291aa355a`
- Budget SHA-256: `d135873ea3446a6093525ed0168f9e815f5435baeffec5417ccc38a31a58d909`
- Request-set SHA-256: `07be211b338764280daabfcc6189d236d31ebefa0bf846c065895f91443c8d39`
- Leakage audit status: `PASS`
- Leakage blocking checks: `[]`

## Exact one-sentence authorization request

I authorize exactly 84 real API calls for SEP-C3-DEFINITION-TARGETED-REFINEMENT-001, using openai_compatible/deepseek-v4-pro with retry=0, on the 42 frozen panel samples for BASE=42 and R_DEF=42, with input cap 296682, output cap 344064, USD cap 1.75411368, panel SHA-256 8ba4517f21402566d61364e86a5516e0ea89f1f82a32781b303eb7a53d97ec61, schedule SHA-256 ed4b12fe5de27ae9611759e0aedb292cfa633bc853b07df867e3fb4291aa355a, and request-set SHA-256 07be211b338764280daabfcc6189d236d31ebefa0bf846c065895f91443c8d39.

SHA-256 of sentence: `f4c030dee3be25ef80ff0428497692615b273a7a0a3b1f2fade90b27a86bea47`

## Decision

- Current decision: **AUTHORIZATION_REQUEST_READY**
- No blocking leakage checks remain.  The schema-required sample_id/source_id interface echo is documented as an allowed non-semantic interface-identifier exemption; substantive leakage checks continue to be enforced and no Gold labels, spans, modalities, or evaluation results are exposed.
