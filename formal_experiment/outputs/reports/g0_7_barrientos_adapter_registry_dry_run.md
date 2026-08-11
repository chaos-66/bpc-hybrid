# G0.7 Barrientos Adapter Registry (DRY-RUN)

## schema
- source: references/barrientos_2026/artifact_input/formats/compliance_requirements_format.json
- local: True
- note: RC4PC schema (id/precondition/norms/temporal_validity); NOT Sun six-element compatible
## labels
- modality_classes_barrientos: ['obligation', 'permission', 'prohibition']
- modality_classes_sun: ['obligation', 'permission', 'prohibition', 'definition']
- mapping_boundary: 3->4 NOT directly mappable; 'definition' class absent; mapping table or adjudication required
## data
- source: references/barrientos_2026 (local, read-only)
- license: unknown_pending_confirmation
- activation: NOT authorized
## metrics
- barrientos: multi-dimensional (semantic coverage / structural encoding / deontic correctness)
- project: Sun literal-overlap six-element (five span fields + separate modality labels)
- comparability: only after adapter + qualification; cross-metric transfer NOT comparable
## license
- unknown_pending_confirmation (see license readiness v2)

## Adapter boundaries
- modality_3_to_4: needs explicit mapping table or human adjudication; never auto-extend
- precondition_to_span: precondition and/or/not triples -> span-based condition requires span alignment adapter (not implemented)
- norm_to_rule_record: norms[] -> rule record fields requires field mapping decision
- temporal_validity: start/end -> constraint handling requires mapping decision
- definition_class: Barrientos has no definition class; Sun definition sentences need separate adjudication
- span_alignment: external spans/offsets cannot be assumed to align with approved English text
- cross_reference: cross-article/process references need explicit provenance handling
- evidence_provenance: every mapped value must keep its source element/XPath provenance
- guard: external labels must NEVER be auto-promoted to project Gold

- S2-BARR-1: registry dry-run delivered; license evidence pending
- S2-BARR-2: blocked (adapter implementation requires mapping decision + license qualification)
