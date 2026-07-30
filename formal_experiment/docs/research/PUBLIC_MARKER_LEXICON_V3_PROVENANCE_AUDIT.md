# Public Marker Lexicon v3 Provenance Audit

> Status: source-only candidate frozen before evaluation; development use only.

## Construction boundary

- Source snapshot: `resources/lexicon/public_marker_sources_en_v3.json` (`94f98d01bc4e11877dbaf318d290c1fca86ef749f0d875200652c333c30041c7`)
- Selection: verbatim public-paper table items, or the intersection of pinned official LexNLP documentation and code.
- Forbidden during construction: EStG-150 text, Gold, predictions, FP/FN, evaluation metrics, LLM suggestions, and unrecorded derivation.
- Runtime boundary: Actor, Condition, Constraint, and Exception are bound by B0; Modality remains the fixed MD rule; Action remains syntax-only.
- Freeze: the manifest and all category hashes below were generated before paired evaluation.

## Verified primary sources

| Source | Type/version | Exact location | Hash | Rights/redistribution |
| --- | --- | --- | --- | --- |
| sun_2024_table4_explicit_markers | public_paper_explicit_marker_table; local publisher PDF | PDF page 11, Section 4.2.2, Table 4 'Markers for different concepts' | 08a26b7d4e6716eb2e07fce4f2a96420562a9eab6ecb12d8fb8ee351b297fcb2 | publisher article copyright; no open redistribution license identified in the inspected PDF; source_pdf_not_redistributed; short factual marker metadata only |
| sleimi_2020_table5_explicit_markers | public_paper_explicit_marker_table; arXiv:2001.11245v1 plus author-institution ORBilu Rev.3 visual cross-check | arXiv PDF pages 15-17, Section 5.1 and Table 5; ORBilu Rev.3 PDF pages 15-18, Section 5.1 and Table 5 | 3a598c1121ab29a382b2d9f3743c5c3b0a9cb4f8bc3a6a9ad22a02283dc6bd95 | publicly accessible preprint; no reusable content license identified in the inspected PDFs; source_pdfs_not_redistributed; short factual marker metadata only |
| lexnlp_conditions_2_3_0_330b4e11 | official_documentation_and_code_intersection; 2.3.0; commit 330b4e113c9bced0cc06f2c864c5015bb5ed2199 | conditions.rst lines 10-30; conditions.py CONDITION_PHRASES lines 25-28 | documentation/docs/source/modules/extract/en/conditions.rst: bb25e9164484867e36c12bb11cad90c2b6e15eb3eeda09914e85abe85b8f78db; lexnlp/extract/en/conditions.py: 5f063d6b7e38c6ed80a1c49388784a6e6858f6b6025d273f3ad680b2c1ee388b | LexNLP repository states AGPL-3.0 default dual licensing; upstream files not redistributed; short factual trigger list and hashes only |
| lexnlp_constraints_2_3_0_330b4e11 | official_documentation_and_code_intersection; 2.3.0; commit 330b4e113c9bced0cc06f2c864c5015bb5ed2199 | constraints.rst lines 10-49; constraints.py CONSTRAINT_PHRASES lines 26-31 | documentation/docs/source/modules/extract/en/constraints.rst: 1e37db97077c92348e4f910bb12c6afeee136ad504a43b1d424e6fa62e133b0f; lexnlp/extract/en/constraints.py: cbfe64b3462d52ed13dfeb58eb5cfb4589f06a951d93e36b8fdbb1795b0fc636 | LexNLP repository states AGPL-3.0 default dual licensing; upstream files not redistributed; short factual trigger list and hashes only |

## v2 provenance defects

All 161 v2 records fail at least one new per-marker provenance requirement. Of those, exactly 106 surfaces are not supported by the v3 source-only selection rule; the remaining 55 surfaces were independently reverified as new v3 records.

| Field | Finding | Count | Exact v2 surfaces |
| --- | --- | ---: | --- |
| actor | not_in_sleimi_table5_actor_row | 19 | `taxpayer`, `employee`, `employer`, `authority`, `person`, `operator`, `minister`, `office`, `association`, `fund`, `trader`, `farmer`, `forester`, `board`, `court`, `insured`, `recipient`, `controller`, `processor` |
| actor | unrecorded_plural_or_inflection_derivation | 10 | `taxpayers`, `employees`, `employers`, `authorities`, `persons`, `associations`, `funds`, `traders`, `farmers`, `foresters` |
| condition | not_in_sleimi_table5_condition_row | 9 | `in the event of`, `in the event that`, `to the extent`, `to the extent that`, `insofar as`, `as long as`, `so long as`, `on condition that`, `once` |
| condition | not_in_sun_table4_or_sleimi_table5_and_no_precise_source | 3 | `whenever`, `insofar`, `that` |
| constraint | sleimi_table5_has_no_constraint_row | 19 | `under`, `under section`, `by double-entry`, `by means of`, `in such quantity`, `to an annual`, `for a period`, `between`, `throughout`, `until`, `during`, `as defined in`, `within the meaning`, `only`, `solely`, `exclusively`, `generally`, `without undue`, `up to` |
| constraint | truncated_lexnlp_phrase_not_an_official_item | 5 | `no less`, `no more`, `less`, `equal`, `not equal` |
| constraint | not_in_sun_table4_constraint_row_and_no_precise_constraint_source | 5 | `for the purpose of`, `for the purposes of`, `for purposes of`, `in accordance with`, `pursuant to` |
| exception | not_in_sleimi_table5_exception_row | 8 | `except`, `excluding`, `notwithstanding`, `regardless of`, `even if`, `shall not apply`, `does not apply`, `do not apply` |
| exception | unrecorded_derivation_from_table_item_derogation | 1 | `in derogation of` |
| exception | wyner_peters_local_audit_lacks_required_exact_location_version_and_evidence | 3 | `save where`, `save`, `unless` |
| modality | not_an_exact_sleimi_table5_modality_item_or_is_a_truncated_form | 24 | `shall mean`, `means`, `is defined as`, `are defined as`, `refers to`, `denotes`, `is understood as`, `shall be construed as`, `amounts to`, `also include`, `is required to`, `is obliged to`, `has to`, `should`, `is prohibited`, `shall not`, `must not`, `may not`, `is not permitted`, `is not allowed`, `must never`, `is authorized`, `is allowed to`, `is permitted to` |

## Frozen candidate inventory

| Field | Count | Category SHA-256 |
| --- | ---: | --- |
| modality | 7 | `d678035faf41ae58da0a538746b4637e405a4acefc6db2876292aa77735656d2` |
| actor | 8 | `252133a5c2876325623317013089f0b39a5964ad19e74b6445e8486e4010060a` |
| action | 0 | `ec2fab94d3f75e4bcc000a0500c1e3a90e6712ac2abccea5cf27c989feb2ad43` |
| condition | 26 | `fe830314980d96eb2d9e1884e6e9faf9d74583ecee753392b93c8b88b17f7a4b` |
| constraint | 41 | `ae6d863afb2a83ecc444047bbafbfb53a9a6e7c5c85756cdc60cb15d9114cccc` |
| exception | 5 | `1e84bc3b401dc197beab638abc20bf968444b3a856208b2046058483be3d62f1` |
| **total** | **87** | combined payload `4c6b7737f6d11b6405e5b5375fa35f452a81920782a789507b7756d3fa881846` |

## Per-marker evidence

| Field | Surface | Class | Source ID(s) | Exact item location(s) | Derived |
| --- | --- | --- | --- | --- | --- |
| modality | `is prohibited from` | prohibition | sleimi_2020_table5_explicit_markers | Table 5 Modality row, item 'is prohibited from' | no |
| modality | `is authorized to` | permission | sleimi_2020_table5_explicit_markers | Table 5 Modality row, item 'is authorized to' | no |
| modality | `need to` | obligation | sleimi_2020_table5_explicit_markers | Table 5 Modality row, item 'need to' | no |
| modality | `shall` | obligation | sleimi_2020_table5_explicit_markers | Table 5 Modality row, item 'shall' | no |
| modality | `must` | obligation | sleimi_2020_table5_explicit_markers | Table 5 Modality row, item 'must' | no |
| modality | `can` | permission | sleimi_2020_table5_explicit_markers | Table 5 Modality row, item 'can' | no |
| modality | `may` | permission | sleimi_2020_table5_explicit_markers | Table 5 Modality row, item 'may' | no |
| actor | `prosecutor` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Actor row, item 'prosecutor'; Table 4 Actor row, item 'prosecutor' | no |
| actor | `inspector` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Actor row, item 'inspector'; Table 4 Actor row, item 'inspector' | no |
| actor | `physician` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Actor row, item 'physician'; Table 4 Actor row, item 'physician' | no |
| actor | `company` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Actor row, item 'company'; Table 4 Actor row, item 'company' | no |
| actor | `officer` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Actor row, item 'officer'; Table 4 Actor row, item 'officer' | no |
| actor | `driver` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Actor row, item 'driver'; Table 4 Actor row, item 'driver' | no |
| actor | `expert` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Actor row, item 'expert'; Table 4 Actor row, item 'expert' | no |
| actor | `judge` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Actor row, item 'judge'; Table 4 Actor row, item 'judge' | no |
| condition | `in the context of` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Condition row, item 'in the context of'; Table 4 Condition row, item 'in the context of' | no |
| condition | `as soon as not` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 22; conditions.py lines 25-28, item 'as soon as not' | no |
| condition | `upon the occurrence` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 27; conditions.py lines 25-28, item 'upon the occurrence' | no |
| condition | `provided that not` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 24; conditions.py lines 25-28, item 'provided that not' | no |
| condition | `unless and until` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 16; conditions.py lines 25-28, item 'unless and until' | no |
| condition | `not subject to` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 26; conditions.py lines 25-28, item 'not subject to' | no |
| condition | `as soon as` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 21; conditions.py lines 25-28, item 'as soon as' | no |
| condition | `in case of` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Condition row, item 'in case of'; Table 4 Condition row, item 'in case of' | no |
| condition | `conditioned upon` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 30; conditions.py lines 25-28, item 'conditioned  upon' | no |
| condition | `conditioned on` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 29; conditions.py lines 25-28, item 'conditioned  on' | no |
| condition | `provided that` | — | lexnlp_conditions_2_3_0_330b4e11; sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | conditions.rst line 23; conditions.py lines 25-28, item 'provided that'; Table 5 Condition row, item 'provided that'; Table 4 Condition row, item 'provided that' | no |
| condition | `subject to` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst lines 25 and 28; conditions.py lines 25-28, duplicated item 'subject to' | no |
| condition | `unless not` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 18; conditions.py lines 25-28, item 'unless not' | no |
| condition | `until not` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 20; conditions.py lines 25-28, item 'until not' | no |
| condition | `where not` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 15; conditions.py lines 25-28, item 'where not' | no |
| condition | `when not` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 13; conditions.py lines 25-28, item 'when not' | no |
| condition | `if not` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 11; conditions.py lines 25-28, item 'if not' | no |
| condition | `unless` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 17; conditions.py lines 25-28, item 'unless' | no |
| condition | `limit` | — | sleimi_2020_table5_explicit_markers | Table 5 Condition row, item 'limit' | no |
| condition | `until` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 19; conditions.py lines 25-28, item 'until' | no |
| condition | `where` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 14; conditions.py lines 25-28, item 'where' | no |
| condition | `which` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Condition row, item 'which'; Table 4 Condition row, item 'which' | no |
| condition | `whose` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Condition row, item 'whose'; Table 4 Condition row, item 'whose' | no |
| condition | `when` | — | lexnlp_conditions_2_3_0_330b4e11 | conditions.rst line 12; conditions.py lines 25-28, item 'when' | no |
| condition | `who` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Condition row, item 'who'; Table 4 Condition row, item 'who' | no |
| condition | `if` | — | lexnlp_conditions_2_3_0_330b4e11; sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | conditions.rst line 10; conditions.py lines 25-28, CONDITION_PHRASES item 'if'; Table 5 Condition row, item 'if'; Table 4 Condition row, item 'if' | no |
| constraint | `greater than or equal to` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 20; constraints.py lines 26-31, item 'greater than or equal to' | no |
| constraint | `less than or equal to` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 28; constraints.py lines 26-31, item 'less than or equal to' | no |
| constraint | `more than or equal to` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 34; constraints.py lines 26-31, item 'more than or equal to' | no |
| constraint | `no earlier than` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 35; constraints.py lines 26-31, item 'no earlier than' | no |
| constraint | `no later than` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 36; constraints.py lines 26-31, item 'no later than' | no |
| constraint | `not to exceed` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 40; constraints.py lines 26-31, item 'not to exceed' | no |
| constraint | `no less than` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 37; constraints.py lines 26-31, item 'no less than' | no |
| constraint | `no more than` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 38; constraints.py lines 26-31, item 'no more than' | no |
| constraint | `not equal to` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 39; constraints.py lines 26-31, item 'not equal to' | no |
| constraint | `earlier than` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 41; constraints.py lines 26-31, item 'earlier than' | no |
| constraint | `greater than` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 19; constraints.py lines 26-31, item 'greater than' | no |
| constraint | `greatest of` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 21; constraints.py lines 26-31, item 'greatest of' | no |
| constraint | `lesser than` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 26; constraints.py lines 26-31, item 'lesser than' | no |
| constraint | `greater of` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 18; constraints.py lines 26-31, item 'greater of' | no |
| constraint | `later than` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 42; constraints.py lines 26-31, item 'later than' | no |
| constraint | `maximum of` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 29; constraints.py lines 26-31, item 'maximum of' | no |
| constraint | `minimum of` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 31; constraints.py lines 26-31, item 'minimum of' | no |
| constraint | `less than` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 27; constraints.py lines 26-31, item 'less than' | no |
| constraint | `lesser of` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 25; constraints.py lines 26-31, item 'lesser of' | no |
| constraint | `more than` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 33; constraints.py lines 26-31, item 'more than' | no |
| constraint | `at least` | — | lexnlp_constraints_2_3_0_330b4e11; sun_2024_table4_explicit_markers | constraints.rst line 11; constraints.py lines 26-31, item 'at least'; Table 4 Constraint row, item 'at least' | no |
| constraint | `equal to` | — | lexnlp_constraints_2_3_0_330b4e11; sun_2024_table4_explicit_markers | constraints.rst line 14; constraints.py lines 26-31, item 'equal to'; Table 4 Constraint row, item 'equal to' | no |
| constraint | `first of` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 16; constraints.py lines 26-31, item 'first of' | no |
| constraint | `least of` | — | lexnlp_constraints_2_3_0_330b4e11; sun_2024_table4_explicit_markers | constraints.rst line 23; constraints.py lines 26-31, item 'least of'; Table 4 Constraint row, item 'least of' | no |
| constraint | `prior to` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 46; constraints.py lines 26-31, item 'prior to' | no |
| constraint | `at most` | — | lexnlp_constraints_2_3_0_330b4e11; sun_2024_table4_explicit_markers | constraints.rst line 12; constraints.py lines 26-31, item 'at most'; Table 4 Constraint row, item 'at most' | no |
| constraint | `last of` | — | lexnlp_constraints_2_3_0_330b4e11; sun_2024_table4_explicit_markers | constraints.rst line 22; constraints.py lines 26-31, item 'last of'; Table 4 Constraint row, item 'last of' | no |
| constraint | `greatest` | — | sun_2024_table4_explicit_markers | Table 4 Constraint row, item 'greatest' | no |
| constraint | `smallest` | — | sun_2024_table4_explicit_markers | Table 4 Constraint row, item 'smallest' | no |
| constraint | `exactly` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 15; constraints.py lines 26-31, item 'exactly' | no |
| constraint | `exceeds` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 45; constraints.py lines 26-31, item 'exceeds' | no |
| constraint | `greater` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 17; constraints.py lines 26-31, item 'greater' | no |
| constraint | `highest` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 47; constraints.py lines 26-31, item 'highest' | no |
| constraint | `maximum` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 30; constraints.py lines 26-31, item 'maximum' | no |
| constraint | `minimum` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 32; constraints.py lines 26-31, item 'minimum' | no |
| constraint | `before` | — | lexnlp_constraints_2_3_0_330b4e11; sun_2024_table4_explicit_markers | constraints.rst line 13; constraints.py lines 26-31, item 'before'; Table 4 Constraint row, item 'before' | no |
| constraint | `exceed` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 44; constraints.py lines 26-31, item 'exceed' | no |
| constraint | `lesser` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 24; constraints.py lines 26-31, item 'lesser' | no |
| constraint | `within` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 43; constraints.py lines 26-31, item 'within' | no |
| constraint | `after` | — | lexnlp_constraints_2_3_0_330b4e11; sun_2024_table4_explicit_markers | constraints.rst line 10; constraints.py lines 26-31, item 'after'; Table 4 Constraint row, item 'after' | no |
| constraint | `least` | — | lexnlp_constraints_2_3_0_330b4e11 | constraints.rst line 48; constraints.py lines 26-31, item 'least' | no |
| exception | `with the exception of` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Exception row, item 'with the exception of'; Table 4 Exception row, item 'with the exception of' | no |
| exception | `apart from` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Exception row, item 'apart from'; Table 4 Exception row, item 'apart from' | no |
| exception | `except for` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Exception row, item 'except for'; Table 4 Exception row, item 'except for' | no |
| exception | `other than` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Exception row, item 'other than'; Table 4 Exception row, item 'other than' | no |
| exception | `derogation` | — | sleimi_2020_table5_explicit_markers; sun_2024_table4_explicit_markers | Table 5 Exception row, item 'derogation'; Table 4 Exception row, item 'derogation' | no |

The report records selection and provenance only. It contains no corpus-derived or evaluation-derived marker decision.
