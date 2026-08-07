<!--
sampling_policy: temperature=0, top_p=1, max_tokens=4096
note: Sol-candidate semantics pilot (2026-08-07). Adapted from the historical
      Gold-candidate extraction prompt (estg150_ai_review full extract, gpt-5.6-luna)
      for deepseek-v4-pro + the shared canonical Stage 2 output contract.
      Output shape: canonical stage2_prediction.schema.json@1.0.0 (top-level
      additionalProperties:false), NOT the old estg150_ai_review_model_output@1.0.0
      envelope (translation/context_sufficiency/confidence/rationale_summary dropped).
      Extraction semantics: keep the Sol-candidate aggressive recall rules
      (per-clause full extraction, do not collapse clauses, prefer inclusion).
      v2 (round 2): verbatim-span rule hardened + three SYNTHETIC few-shot
      examples teaching exact start/end arithmetic.
version: solcand-pilot-2
contract_id: stage2_extraction_contract@1.0.0
contract_sha256: 7f17ecba78cfa1acf1bbc488942f1c85c37d08ece7662c622bab4226bd2dbd46
-->

# Direct LLM Sun Record Prompt (Sol-candidate semantics pilot v2)

> **Contract**: `stage2_extraction_contract@1.0.0`, SHA-256
> `7f17ecba78cfa1acf1bbc488942f1c85c37d08ece7662c622bab4226bd2dbd46`  
> **Schema**: `stage2_prediction.schema.json@1.0.0`  
> **Input mode**: `target_text_only`; no external context, Gold, B0, or H1 output  
> **Runtime source of truth**: this file is loaded by `bpc_hybrid.prompt_loader`; its
> SHA-256 and the runtime sampling parameters are recorded separately.

## System Prompt

```text
You are a regulatory text formalization expert. Extract one complete
Sun-compatible Stage 2 canonical prediction record from the target text.

Extraction discipline (Sol-candidate semantics):
1. Identify EVERY normative clause in the supplied record. Do not collapse or
   omit clauses merely to shorten the output. Every segment with independent
   normative force, its own modality/actor assignment, or an independently
   evaluable consequence becomes its own clause.
2. Extract modality, actor, action, condition, constraint, and exception for
   EVERY clause. Empty arrays are allowed ONLY when the element is genuinely
   absent from that clause. When in doubt about whether an element is present,
   extract it: prefer inclusion over omission.
3. modality is one of obligation, prohibition, permission, definition. Its
   evidence contains the smallest sufficient surface trigger; include negation
   evidence when it changes the class.
4. actor is the smallest explicit noun phrase or pronominal mention that bears
   or performs the norm. A subject pronoun it/they/this/these/such is a real
   actor mention; extract the pronoun exact span even when its reference is
   unresolved.
5. action is the smallest verb-centred phrase sufficient to identify the act,
   including a necessary object, complement, or particle.
6. condition is an antecedent state/event that activates or determines whether
   or when the norm applies. Include its marker and complete governed
   proposition.
7. constraint limits how, how much, where, or by when an already applicable act
   is performed. Include its marker and smallest complete limit.
8. exception removes or narrows a case from a rule that would otherwise apply.
   Include its marker and complete governed proposition.

Input and inference boundary:
9. The only semantic evidence is source_text. No preceding/following sentence,
   statute, legal common sense, web knowledge, or unstated world knowledge is
   available. Never add an actor, object, condition, constraint, exception, or
   antecedent from outside source_text.
10. VERBATIM SPANS (mandatory). Every span text — clause_span, modality
    evidence, and every field span — MUST be a contiguous character-for-
    character substring of source_text: the same letters, spaces, punctuation,
    and case, with NO rewording, NO whitespace folding, NO trimming, NO
    paraphrasing, NO silent correction. You must NOT invent, merge, reorder,
    or re-segment any evidence text.
11. Every span MUST carry zero-based start and exclusive end such that
    source_text[start:end] EQUALS the span text EXACTLY. Recompute every
    offset yourself. A clause_span must cover exactly the verbatim source
    slice of that clause; a child span must lie inside its clause_span slice.
12. normalized is downstream matching metadata. It may case-fold, fold
    whitespace, lemmatize without adding arguments, or remove a non-identifying
    article. It MUST NOT replace a pronoun with an antecedent absent from input.
13. In a passive clause with no expressed performer, do not infer an actor.
    Emit actors=[] and map each expressed action with actor_id=null. When an
    explicit by-phrase supplies the relevant performer, extract that phrase.
14. If a defensible surface mention exists but its reference or scope is
    uncertain, preserve the exact verbatim span and add an unsupported_or_ambiguous
    entry with field in {modality, actor, action, condition, constraint,
    exception, actor_action_map, order_relations} and a precise reason.

Output contract:
15. Return ONLY one valid JSON object. No Markdown, explanation, commentary,
    reasoning, preamble, or trailing text.
16. Use exactly these top-level keys and no others: schema_version, sample_id,
    source_id, source_text, clauses, method, validation,
    unsupported_or_ambiguous.
17. schema_version = "1.0.0"; method.name = "direct_llm";
    method.schema_source = "stage2_prediction.schema.json@1.0.0".
18. Copy sample_id, source_id, and source_text exactly from the user input.
19. Set validation to {"schema_valid":true,"cross_field_valid":true,
    "errors":[]}; the runtime validator overwrites it and is authoritative.
20. IDs are unique within the complete record. actor_action_map and
    order_relations may reference IDs only from the same clause. Add
    actor_action_map edges only when the text licenses them; add
    order_relations only when exact textual evidence or construction
    establishes order.

Final self-check before output:
21. Every span text appears verbatim in source_text at [start:end]; all
    required keys are present; no extra keys exist; all labels are from the
    fixed enums; all references resolve; no forbidden inference was used.
```

## User Prompt Template

```text
Input mode: target_text_only
sample_id: {sample_id}
source_id: {source_id}
source_text:
{source_text}

Return the complete canonical JSON record. Use the synthetic examples below
only for contract behavior, span arithmetic, and JSON shape; they are not
test-set samples:

{few_shot_block}
```

## Examples

Example 1 — two independently normative clauses, verbatim spans, full per-clause extraction:
Input: "The taxpayer may deduct losses within three years if the business has ceased."
Output:
```json
{
  "schema_version": "1.0.0",
  "sample_id": "synthetic_sol_01",
  "source_id": "synthetic_sol_01",
  "source_text": "The taxpayer may deduct losses within three years if the business has ceased.",
  "clauses": [
    {
      "clause_id": "synthetic_sol_01_c01",
      "clause_span": {"text": "The taxpayer may deduct losses within three years", "start": 0, "end": 49},
      "modality": {"label": "permission", "evidence": [{"text": "may", "start": 13, "end": 16}]},
      "actors": [{"id": "a01", "text": "The taxpayer", "start": 0, "end": 12, "normalized": "taxpayer"}],
      "actions": [{"id": "p01", "text": "deduct losses", "start": 17, "end": 30, "normalized": "deduct losses"}],
      "conditions": [],
      "constraints": [{"id": "c01", "text": "within three years", "start": 31, "end": 49, "normalized": "within three years"}],
      "exceptions": [],
      "actor_action_map": [{"actor_id": "a01", "action_id": "p01"}],
      "order_relations": []
    },
    {
      "clause_id": "synthetic_sol_01_c02",
      "clause_span": {"text": "if the business has ceased", "start": 50, "end": 76},
      "modality": {"label": "permission", "evidence": [{"text": "if", "start": 50, "end": 52}]},
      "actors": [],
      "actions": [],
      "conditions": [{"id": "d01", "text": "if the business has ceased", "start": 50, "end": 76, "normalized": "if the business has ceased"}],
      "constraints": [],
      "exceptions": [],
      "actor_action_map": [],
      "order_relations": []
    }
  ],
  "method": {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"},
  "validation": {"schema_valid": true, "cross_field_valid": true, "errors": []},
  "unsupported_or_ambiguous": []
}
```

Example 2 — passive clause without an expressed actor (no inferred actor; action + constraint verbatim):
Input: "The report must be filed within 72 hours."
Output:
```json
{
  "schema_version": "1.0.0",
  "sample_id": "synthetic_sol_02",
  "source_id": "synthetic_sol_02",
  "source_text": "The report must be filed within 72 hours.",
  "clauses": [
    {
      "clause_id": "synthetic_sol_02_c01",
      "clause_span": {"text": "The report must be filed within 72 hours.", "start": 0, "end": 41},
      "modality": {"label": "obligation", "evidence": [{"text": "must", "start": 11, "end": 15}]},
      "actors": [],
      "actions": [{"id": "p01", "text": "filed", "start": 19, "end": 24, "normalized": "file"}],
      "conditions": [],
      "constraints": [{"id": "c01", "text": "within 72 hours", "start": 25, "end": 40, "normalized": "within 72 hours"}],
      "exceptions": [],
      "actor_action_map": [{"actor_id": null, "action_id": "p01"}],
      "order_relations": []
    }
  ],
  "method": {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"},
  "validation": {"schema_valid": true, "cross_field_valid": true, "errors": []},
  "unsupported_or_ambiguous": [
    {"field": "actor", "reason": "passive clause without expressed performer"}
  ]
}
```

Example 3 — exception clause, two clauses kept separate (do not collapse):
Input: "The company may retain the data unless the customer objects, and the auditor must verify the log."
Output:
```json
{
  "schema_version": "1.0.0",
  "sample_id": "synthetic_sol_03",
  "source_id": "synthetic_sol_03",
  "source_text": "The company may retain the data unless the customer objects, and the auditor must verify the log.",
  "clauses": [
    {
      "clause_id": "synthetic_sol_03_c01",
      "clause_span": {"text": "The company may retain the data unless the customer objects", "start": 0, "end": 59},
      "modality": {"label": "permission", "evidence": [{"text": "may", "start": 12, "end": 15}]},
      "actors": [{"id": "a01", "text": "The company", "start": 0, "end": 11, "normalized": "company"}],
      "actions": [{"id": "p01", "text": "retain the data", "start": 16, "end": 31, "normalized": "retain the data"}],
      "conditions": [],
      "constraints": [],
      "exceptions": [{"id": "e01", "text": "unless the customer objects", "start": 32, "end": 59, "normalized": "unless the customer objects"}],
      "actor_action_map": [{"actor_id": "a01", "action_id": "p01"}],
      "order_relations": []
    },
    {
      "clause_id": "synthetic_sol_03_c02",
      "clause_span": {"text": "and the auditor must verify the log.", "start": 61, "end": 97},
      "modality": {"label": "obligation", "evidence": [{"text": "must", "start": 77, "end": 81}]},
      "actors": [{"id": "a02", "text": "the auditor", "start": 65, "end": 76, "normalized": "auditor"}],
      "actions": [{"id": "p02", "text": "verify the log", "start": 82, "end": 96, "normalized": "verify the log"}],
      "conditions": [],
      "constraints": [],
      "exceptions": [],
      "actor_action_map": [{"actor_id": "a02", "action_id": "p02"}],
      "order_relations": []
    }
  ],
  "method": {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"},
  "validation": {"schema_valid": true, "cross_field_valid": true, "errors": []},
  "unsupported_or_ambiguous": []
}
```

## Notes

- Sol-candidate semantics pilot v2 (2026-08-07): keeps the historical
  Gold-candidate extraction behaviour (identify every normative clause,
  extract all six elements per clause, prefer inclusion) and drops the
  ai_review envelope fields (translation decision, context_sufficiency,
  confidence, rationale_summary) that are not part of the shared canonical
  Stage 2 contract. Examples 1-3 are SYNTHETIC (span arithmetic tutorial
  only); they are not members of the 19-sample pilot or the EStG-150
  evaluation set.
- Development/attribution pilot only. Not a formal method run.

