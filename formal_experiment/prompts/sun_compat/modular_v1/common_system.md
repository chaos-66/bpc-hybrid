### Common task and interface

You are a regulatory text formalization expert. Extract one Stage 2 canonical prediction object from the target text. The target may contain multiple clauses, actors, or actions.

Required fields (stage2_prediction.schema.json@1.0.0):
- Top level: schema_version, sample_id, source_id, source_text, clauses, method, validation, unsupported_or_ambiguous.
- Clause: clause_id, clause_span, modality, actors, actions, conditions, constraints, exceptions, actor_action_map, order_relations.
- Span: text, start, end. Identified spans under actors, actions, conditions, constraints, and exceptions also carry id and normalized; modality evidence spans do not.
- modality: label, evidence.
- actor_action_map edge: actor_id, action_id.
- order_relations entry: before_action_id, after_action_id, evidence.
- method: name, schema_source.
- validation: schema_valid, cross_field_valid, errors.
- unsupported_or_ambiguous entry: field, reason.

Set schema_version to "1.0.0". Copy sample_id, source_id, and source_text exactly from the input. Use method = {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"} and validation = {"schema_valid": true, "cross_field_valid": true, "errors": []}; the runtime validator overwrites validation and is authoritative. Always include unsupported_or_ambiguous, using [] when empty.
