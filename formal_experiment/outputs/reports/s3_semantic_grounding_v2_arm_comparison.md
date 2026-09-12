# s3_semantic_grounding_v2 arm comparison

- A: C36 similarity baseline (historical; old evaluation protocol)
- B: Semantic Grounding v2 deterministic — target-paired Macro-F1 **0.6737**, control target FP **0.0250**, pair success **0.5250**
- C: Semantic Grounding v2 + LLM fallback — **IMPLEMENTED_READY_FOR_AUTHORIZATION**

C was not real-run. See the authorization request for the exact scope/model/call/budget request.
