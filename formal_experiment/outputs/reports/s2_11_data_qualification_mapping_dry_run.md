# S2.11 Data Qualification & Mapping Protocol (DRY-RUN, not applied)

- status: dry_run_not_applied
- candidate data: Barrientos 2026 (91 files, local read-only) + Stage1 GDPR-7 (7 BPMN)
- modality incompatibility: Barrientos 3 classes (obligation/permission/prohibition) vs Sun 4 classes (+ definition); labels must be mapped or human-adjudicated, never treated as Sun-compatible directly
- complexity definitions: candidates only (G0.5 not frozen): {'l1': 'single-clause sentence, one modality, no nested condition', 'l2': 'multi-clause sentence, nested condition/constraint, cross-references', 'l3': 'multi-sentence legal provision with exceptions and cross-article references', 'status': 'CANDIDATES ONLY - G0.5 complexity rules not frozen before results; any later use must be explicitly retrospective or re-frozen'}
- human Gold required: True
- authorization sentence: NOT EMITTED - qualification decision conditions NOT reached this round (license/mapping/adaptation details pending); no authorization sentence is emitted

## Guards
- external labels must never be treated as Sun-compatible Gold without mapping + adjudication
- references/archive/_retired remain read-only; nothing activated
