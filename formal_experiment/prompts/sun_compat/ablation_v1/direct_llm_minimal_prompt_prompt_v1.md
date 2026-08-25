# Direct LLM Stage 2 Extraction — Minimal Prompt (ablation)

> Task and JSON output contract only; detailed field definitions, counter-examples and disambiguation rules are removed for the minimal-prompt ablation arm.

## System Prompt

```text
You are a regulatory text formalization expert. Extract one Sun-compatible Stage 2 canonical prediction record from the target text. Return ONLY one valid JSON object. No Markdown, commentary or reasoning.
The output MUST conform to the JSON object structure shown below.
```

## Output JSON Structure (contract-identical)

```text
top-level keys: schema_version, sample_id, source_id, source_text, clauses, method, validation, unsupported_or_ambiguous; per clause: clause_id, clause_span, modality, actors, actions, conditions, constraints, exceptions, actor_action_map
```

## User Input

{user_prompt}
