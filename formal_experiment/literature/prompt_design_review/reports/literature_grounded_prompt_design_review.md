# Literature-Grounded Prompt Design Review

Task: BPC Stage 2 / SEP-C3 literature-grounded evidence collection for Prompt Design.

Role: literature researcher / evidence collector / engineering assistant. This report does not design a new prompt, does not modify the BPC prompt, and does not run any LLM API experiment. New Stage 2 API calls: **0**.

---

## 1. Scope

Reviewed required Papers A-E and optional Papers F-G, plus one supporting citation discovered during review (Sun X. et al. 2024, cited by LegalChanges4BPC for its concept taxonomy). The review focuses on:

- whether full papers and appendices are publicly available;
- whether exact prompts are public and where;
- how each paper defines near-overlapping semantic roles, especially actor/subject/object/antecedent/consequent/condition/constraint/exception;
- whether any paper specifies span boundary, minimal/complete span, overlap, nesting, or multi-role annotation rules;
- what error modes the authors report;
- what is directly compatible, what needs mapping, what is already covered, what is incompatible, and where evidence is insufficient.

Non-goals: designing a new prompt, proposing R_C v2, modifying current BPC prompts, starting new arms, or calling project LLMs.

---

## 2. Search methodology

For each paper, the following were searched in priority order:

1. Publisher/DOI landing page and Crossref metadata.
2. ACL Anthology or workshop proceedings page.
3. Author public preprint/PDF (arXiv or institutional repository).
4. GitHub repository and raw prompt files.
5. Supplementary/appendix material.
6. OpenAlex, Semantic Scholar, Unpaywall for OA locations.
7. Exact title + "prompt", "appendix", "github", "supplementary" via search engines where available.
8. For code/prompt repositories: GitHub API tree/raw endpoints; Anonymous GitHub API file/zip endpoints.

Methods used:

- Crossref REST API for bibliographic metadata, license, links, pages, and DOI.
- ACL Anthology BibTeX/landing pages and PDF downloads.
- arXiv API and PDF download.
- PyMuPDF text extraction from downloaded PDFs.
- `r.jina.ai` publisher reader as fallback where publisher anti-bot blocked direct access; this was cross-checked against original PDFs whenever a PDF was obtainable.
- GitHub API to enumerate files and raw content; commit history for one prompt file.
- Anonymous GitHub API to download the RC4PC repository zip and exact prompt file.

No project LLM API calls were made. All network calls were bibliographic, repository, or publisher retrieval.

---

## 3. Source verification

| Paper | Full text found? | Public prompt? | Code/supplement? |
|---|---|---|---|
| A LegalDiscourse | yes, ACL Anthology PDF | yes, Appendix F, pp. 8551-8555 | code release promised, URL not found |
| B Haque & Singh | yes, arXiv preprint; publisher paywalled | yes, Section 3.2 p. 7 (preprint) | no public code found |
| C Sun/Luo/Li COLING 2025 | yes, ACL Anthology PDF | yes, Appendix C, Figures 7/8, p. 2614 | no code/supplement found |
| D RC4PC | yes, TU/e repository PDF (CC BY) | yes, repo `formalize_requirements_prompt.txt` | anonymous repo with code/prompts/data |
| E LegalChanges4BPC | yes, Springer CC BY PDF | yes, GitHub prompt file + paper Section 6.2.2/Fig. 8 | GitHub repo |
| F Kölbel et al. | yes, Springer CC BY PDF | yes, GitHub prompt builders | GitHub repo |
| G DPLACC | yes via Jina reader; direct MDPI PDF blocked | partial, `[MASK]` prompt-learning template | no code repo found |
| Supporting Sun X. et al. 2024 | no, closed access | no | no |

Verification notes:

- Exact D prompt was verified from both the downloaded repository zip and the direct raw Anonymous GitHub endpoint.
- Exact E prompt was verified from GitHub raw and two commits of `data/input/prompts/prompt_review.txt`.
- Exact F prompt components were verified from raw `ISO27001/prompt.py` and `IEC62443/prompt.py`.
- C Chinese template text was extracted cleanly with PyMuPDF from the ACL PDF.
- G publisher PDF direct download was blocked (MDPI Access Denied); the publisher HTML/PDF text was read through `r.jina.ai`. The included direct PDF download is not treated as valid.
- B publisher full text was not accessible; the public arXiv preprint is the verified source.

---

## 4. RC4PC vs LegalChanges4BPC clarification

These are **not the same paper** and were kept separate.

| | RC4PC | LegalChanges4BPC |
|---|---|---|
| Title | Impact analysis of regulatory requirement changes on business process compliance | Taming the Complexity of Legal Change for Business Process Compliance |
| Authors | Marisol Barrientos, Karolin Winter, Stefanie Rinderle-Ma | Marisol Barrientos, Johannes Loebbecke, Karolin Winter, Stefanie Rinderle-Ma |
| Venue/year | Information and Software Technology, 2026, vol. 194, article 108079 | Business & Information Systems Engineering, 2026, vol. 68(5), 1147-1172 |
| DOI | 10.1016/j.infsof.2026.108079 | 10.1007/s12599-026-01008-x |
| Focus | Formalizes requirements, extracts atomic change operations, assesses impact on process compliance | Detects legal changes and analyzes relevance for BPC using LLM prompting |
| LLM | yes, GPT-4.1 in Step 1 | yes, GPT-5/Mistral/Phi/LLaMA etc. via OpenRouter |
| Prompt public? | yes, anonymous repo | yes, GitHub repo |
| Few-shot? | zero-shot, controlled vocabulary | second round adds one-shot input/output example |
| Key concepts for this review | `precondition`, deontic `norms`, action object with `dimension`/`compliance_pattern`, nested `temporal_constraints` | statement/concept taxonomy: actor, action, action_object, condition, constraint, exception |

Additional clarification: LegalChanges4BPC cites **Sun X., Yang, Zhao, and Yu (2024), "Design-time business process compliance assessment based on multi-granularity semantic information"**, J. Supercomputing, as the source of the six-concept BPC layer. That is a different paper from **Paper C (Jingyun Sun, Luo, Li, COLING 2025)**. The Sun X. 2024 full text is closed access and was not found publicly, so its definitions cannot be independently verified; only LegalChanges4BPC's reproduction of the concept list was verified.

---

## 5. LegalDiscourse (A)

- Full text found: yes, ACL Anthology PDF, pages 8536-8559.
- Public prompt: yes; Appendix F, pp. 8551-8555.
- Code/supplement: Appendix A-F in main PDF; no public code URL found. The paper says scraping and annotation code would be released.

Schema: SUBJECT, OBJECT, PROBE, TEST, CONSEQUENCE, EXCEPTION, DEFINITION, CLASS; 21 relation classes.

Condition/constraint relevance:
- TEST is the applicability condition: "an explicit condition applied to an entity ... that determines when a SUBJECT-CONSEQUENCE-OBJECT relation holds."
- EXCEPTION specifies when the law does not apply.
- CONSEQUENCE is "the specific power or restriction conferred by the law"; there is no separate `constraint` label.
- TEST examples include population thresholds, census references, and dates; these remain inside TEST and are not separately labeled as constraints.
- Overlap/nesting: the paper explicitly discusses recursive parsing and sub-span ambiguity; annotators were advised to parse to the lowest level. It says a single entity can be both SUBJECT and OBJECT, and in those cases it was annotated as OBJECT. There is no general overlap/multi-role annotation rule and no parent-child condition/constraint span rule.
- Few-shot: 0/1/2/3/5/8/10 shots tested; Appendix F shows 1-shot examples. No negative/contrastive examples.
- Reported errors: subject/object/probe role confusion, span-boundary ambiguity, same entity generated in different categories.

Most relevant 3-5 points:
1. TEST/EXCEPTION provide a clear applicability-condition taxonomy that is conceptually close to `condition`/`exception`, but no `constraint` role.
2. The paper openly documents sub-span/discourse granularity ambiguity and recommends lowest-level parsing; this does **not** map directly to our full-condition-plus-inner-constraint Gold.
3. Its prompt has explicit no-answer strings (`none`, `no entity`) and restriction to source text, but no minimal/complete span definition.
4. Its 1-shot prompt format shows positive examples; no negative or contrastive boundary examples.
5. Its role-confusion error report supports keeping actor/action boundaries explicit, which R_A already does.

---

## 6. Haque & Singh (B)

- Full text found: yes, arXiv:2404.02269; publisher Springer chapter is not open access.
- Public prompt: yes, in the preprint Section 3.2 p. 7; published version may show it as Figure 1 but that could not be verified.
- Code/supplement: no public code found.

Schema: norm type + subject + object + antecedent + consequent; four norm types (commitment, prohibition, authorization, power), with explicit directionality definitions.

Condition/constraint relevance:
- `antecedent` is the condition on which the subject's action depends.
- `consequent` is the outcome of the action.
- `object` is the counterparty party with respect to whom the norm applies; it is not our action object.
- There is no separate `constraint` role and no span-boundary rule. Examples are normalized/inferential and not exact original spans.
- Few-shot: zero-shot only; no prompt examples.
- Reported errors: incorrect norm type, incorrect norm elements, overlooked crucial details, hallucination, incorrect conjunction parsing, and empty norm elements. The authors note empty subject/object can mean "no party" or "all parties," which is ambiguous.

Most relevant 3-5 points:
1. Its subject definition is semantically close to actor, but its object is a counterparty and must not be mapped to action object.
2. Its antecedent/consequent are event-level norm roles, not text span labels; mapping them to condition/constraint is unsafe.
3. The paper directly reports role confusion and empty-element ambiguity, both relevant failure modes for actor and condition/constraint.
4. Adding explicit role directionality definitions improved its own subject/object assignment; that supports the general value of clear definitions but does not add anything beyond R_A/current S for our schema.
5. It is zero-shot and has no public negative examples.

---

## 7. Jingyun Sun, Luo & Li (COLING 2025) (C)

- Full text found: yes, ACL Anthology PDF, pp. 2603-2615.
- Public prompt: yes, Appendix C, Figure 7 (agent extraction) and Figure 8 (deontic-word prediction), printed p. 2614.
- Code/supplement: no public code/supplement found.

Prompts:
- Figure 7: "Please carefully read the regulatory document ... identify all subjects subject to deontic constraints." It names organizations, companies, government departments, non-profits, and individuals; points to words like "must comply", "is obligated", "should"; asks for a clear list and emphasizes accuracy/completeness/no omission.
- Figure 8: identify deontic words related to the constrained subject, with short explanation; examples include "must", "should", "prohibited", "responsibility".
- No JSON/schema, no absent-field handling, no span-boundary rule, no overlap/nesting rule.

Actor/R_A relevance:
- This paper is the strongest **conflict** source for our empty-Gold actor. Its "all subjects" plus "no omission" instruction could encourage object/resource/amount extraction when no responsible actor is explicit.
- Its subject definition is broader and less explicit-only than R_A.

Most relevant 3-5 points:
1. Confirms that legal deontic extraction requires identifying a subject constrained by a deontic word.
2. Its completeness instruction directly conflicts with empty-Gold actor and should not be copied.
3. It does not distinguish actor from action object/resource/amount.
4. It does not handle absent actor.
5. It provides no condition/constraint boundary evidence.

---

## 8. RC4PC (D)

- Full text found: yes, TU/e Pure repository PDF (CC BY).
- Public prompt: yes; anonymous repository exact `formalize_requirements_prompt.txt`, plus no-patterns ablation prompt.
- Code/supplement: yes, anonymous repository contains code, prompts, input formats, process models, requirements, and outputs.

Prompt/schema:
- The prompt is zero-shot, strict JSON, with mandatory keys: `id`, `precondition` (three keys: `and`, `or`, `not`, each a list of actions), `norms` (modality + action), `temporal_validity`.
- Each action object has `dimension` (control_flow, data, resource, time), a controlled `compliance_pattern`, and optional `activities`, `resources`, `data_values`, `temporal_constraints`.
- Negative constraints forbid inventing patterns; an exclusivity rule prevents some redundant control-flow patterns; label/structure consistency across versions is required.
- The paper states: preconditions are factual and do not carry deontic meaning; modalities are defined only over actions in norms.

Condition/constraint relevance:
- Formal precondition vs norm is conceptually useful, but this is not text-span annotation.
- Restrictions are encoded as typed action objects/patterns and nested `temporal_constraints` inside precondition or norms; there is no top-level `constraint`.
- The prompt gives no rule for deciding whether a phrase is precondition vs a norm action, nor for preserving a complete text condition alongside an inner constraint span.

Most relevant 3-5 points:
1. Supports the general distinction between factual applicability and deontic regulated action.
2. Shows that formal nested structure is possible (`temporal_constraints` inside action objects), but not span overlap.
3. Uses a controlled vocabulary and strict schema; current project already has a shared structured-output baseline/canonicalizer.
4. Its zero-shot design and pattern ablation are experimental-design context, not a condition/constraint boundary rule.
5. Do not directly rename its `dimension`/`compliance_pattern` labels to our `constraint`.

---

## 9. LegalChanges4BPC (E)

- Full text found: yes, Springer CC BY PDF.
- Public prompt: yes; GitHub `data/input/prompts/prompt_review.txt`, exact final one-shot prompt.
- Code/supplement: yes; GitHub repository with prompt, datasets, outputs, analysis.

Prompt design:
- Two-round iterative process. Round 1: goal + task/input/output specifications + controlled vocabulary; tested on GPT-4.1; output did not match JSON schema. Round 2: added a one-shot input/expected-output example.
- Final prompt uses a persona, statement-level change analysis, 12+ output keys, controlled statement types (obligation, prohibition, permission, definition) and six controlled concept types:
  - actor: role responsible for executing the action;
  - action: activity that is mandatory/prohibited/permitted;
  - action_object: item being acted upon;
  - condition: specifies when the statement applies;
  - constraint: a restriction limiting how or when the regulation is applicable;
  - exception: conditions under which the regulation does not apply.
- Output: JSON array only; no prose or markdown.
- One-shot example: a modified gluten-free labeling statement lists `"concepts_modified": "constraint, condition, action_object"` and explains that a threshold was tightened and a new disclosure condition was added.

Condition/constraint relevance:
- Closest terminology to our schema, and the only reviewed prompt with explicit `condition` and `constraint` definitions.
- `concepts_modified` is a list of changed concept types, not a span annotation rule. The paper does not specify overlapping/nested spans, minimal/complete spans, or a single span with multiple labels.
- The example suggests threshold/limit -> `constraint` and disclosure/applicability -> `condition`, but this cannot be turned into a strict rule from the public materials.

Most relevant 3-5 points:
1. Strong terminological alignment for actor, action, condition, constraint, exception.
2. It has no span boundary/overlap/nesting rule; the exact prompt cannot resolve our core condition/constraint overlap.
3. Its one-shot example was added to fix JSON schema output, not to disambiguate similar semantic labels.
4. It uses a controlled concept vocabulary; our S rules are already more operational for condition/constraint.
5. Do not add action_object to Stage 2 as a prompt-only change; that is a schema decision outside this task.

---

## 10. Optional papers and supporting citation

### F. Kölbel, Poss & Schönig (2026)

- Full text and GitHub prompt builder available.
- Modular prompt architecture with configurable role/few-shot/CoT/context/format components.
- Format instructions enforce "base your answer solely on the model" and use `Fully Met`/`Partially Met`/`Not Met`/`Cannot Determine`.
- Four-part error typology: Reasoning Failure, Input Interpretation Failure, Context Retrieval Failure, Hallucination.
- No condition/constraint/actor extraction and no span annotation. Use only as experiment-design reference; do not migrate to Stage 2.

### G. DPLACC (2026)

- Full text via Jina reader; direct MDPI PDF blocked.
- Prompt learning with `[MASK]` template: `Does x1 meet the requirements of x2? [MASK]`; verbalizer labels `yes`/`no`; first-order-logic vector fused with mask representation; Prolog used for interpretability.
- It is conceptually different from instruction-based LLM prompting. Do not treat it as a Stage 2 prompt reference.

### Supporting citation: Sun X. et al. 2024

- Closed-access paper cited by LegalChanges4BPC as the source of the six-concept BPC taxonomy (actor, action, action_object, condition, constraint, exception).
- Full text not publicly found; no prompt or definitions independently verified.
- It is not Paper C (Jingyun Sun et al., COLING 2025).

---

## 11. Semantic mapping

See `semantic_mapping.md` for the full table. Key points:

- `actor` has a compatible core across LegalChanges4BPC, Haque & Singh's subject, and R_A; LegalDiscourse and COLING 2025 are broader and conflict with explicit-only/no-actor behavior.
- `condition` maps most closely to LegalDiscourse TEST, Haque & Singh antecedent, RC4PC precondition, and LegalChanges4BPC condition, but none provides a span-boundary rule.
- `constraint` exists explicitly only in LegalChanges4BPC; LegalDiscourse bundles restrictions into CONSEQUENCE, Haque & Singh has none, and RC4PC encodes restrictions as action patterns/nested temporal constraints.
- `exception` is the most compatible concept across LegalDiscourse, LegalChanges4BPC, and our schema; span policy is still unspecified.
- `action_object` exists only in LegalChanges4BPC; our schema has no separate field. Do not smuggle it in by relabeling.

---

## 12. Condition / constraint boundary evidence

See `condition_constraint_boundary_review.md` for Q1-Q5 per paper and the full synthesis.

Summary:
- **Q1 distinction:** LegalDiscourse distinguishes TEST/EXCEPTION vs CONSEQUENCE, but has no separate constraint. RC4PC distinguishes formal precondition vs norm action, with restrictions as patterns. LegalChanges4BPC explicitly defines condition and constraint. Haque & Singh and COLING 2025 do not.
- **Q2 overlap/nesting:** not specified in any paper as a span annotation policy. LegalDiscourse discusses recursive span ambiguity and lowest-level parsing; RC4PC allows nested formal structures (`temporal_constraints` inside action objects); neither is a public span-overlap rule.
- **Q3 full condition with quantity/time/threshold:** LegalDiscourse keeps thresholds inside TEST; RC4PC puts them into typed/nested action structures; LegalChanges4BPC's example treats a threshold as `constraint` and disclosure as `condition`. None defines span boundaries.
- **Q4 inclusion/exclusion, contrastive examples, minimal/complete span:** no paper has contrastive examples or an explicit complete-vs-minimal span rule. LegalDiscourse discusses lowest-level parsing but as a source of ambiguity.
- **Q5 can it explain full condition + inner constraint?** No. LegalDiscourse has no separate constraint role; RC4PC has no text spans; LegalChanges4BPC has no overlap/nesting rule.

**Key result:** no reviewed public source provides a stronger or safer rule than the project's current S rule 8 and E5 worked example. Literature does not justify a new condition/constraint boundary prompt.

---

## 13. Actor / R_A comparison

See `actor_prompt_review.md` for the full matrix.

Summary:
- A's SUBJECT definition and B's subject definition overlap conceptually with R_A, but A permits passive implied subjects and enumerates all mentions; B has ambiguous empty subject semantics.
- C's agent prompt asks for all deontic-constrained subjects and emphasizes no omission, which is the opposite of R_A for empty-Gold cases.
- R_A already covers the compatible core: explicit responsible entity, no objects/resources/amounts as actors, no actor if none explicitly stated.
- A's `"passive voice entity"`, B's "empty subject may mean all parties," and C's no-omission guidance are potential conflicts and should not be copied.
- No duplicate actor instruction should be added.

---

## 14. Few-shot / example design evidence

| Paper | Setting | Examples | Negative cases? | Used to disambiguate roles? | Overlap/nesting shown? |
|---|---|---|---|---|---|
| A | 0/1/2/3/5/8/10-shot | one positive example per span prompt; dataset-derived | no; uses `none`/`no entity` | relation definitions with one example; no contrastive pair | no |
| B | zero-shot | none in prompt; examples only as paper findings | no | no | no |
| C | zero-shot with one illustrative sentence | one example per template | no | no | no |
| D | zero-shot | none in prompt | no | no | formal nested structures only |
| E | round 1 no example; round 2 one-shot | one positive input/output example; added after JSON schema mismatch | no | no; example lists changed concept types | no span overlap/nesting rule |
| F | configurable 0/few-shot | 2 sampled examples from catalog | no explicit negative | no | no |
| G | prompt learning, not few-shot instruction | [MASK] template | no | no | no |

No public contrastive-example design for distinguishing condition vs constraint was found. E's one-shot example and A's relation examples are positive only. Current project E already has strong positive evidence, including E5 nested condition/constraint. Do not design new E here.

---

## 15. Output-format evidence

- A: plain text spans, semicolon-joined; no JSON.
- B: list of norm fields; no JSON.
- C: clear list; no JSON.
- D: strict JSON, mandatory keys, controlled patterns, no prose/code fences.
- E: JSON array only, validated against a predefined JSON schema.
- F: modular format prompting, but Q&A over BPMN/external standards.
- G: `[MASK]` classification and verbalizer; not free-form JSON.

Current project already has a shared structured-output baseline and canonicalizer. The literature's JSON use is therefore **practice evidence**, not a reason to restore J. Do not treat JSON strictness as a fix for condition/constraint semantic errors.

---

## 16. Literature error analysis

| Literature-reported error | Source | Similar current failure? | Evidence |
|---|---|---|---|
| Subject/object/probe role confusion | A | yes, actor/action/role boundary | A Section 5.1 |
| Span boundary/sub-span ambiguity | A | yes, condition/constraint boundary | A Section 3.2 and 10.1 |
| Same entity generated in different categories | A | partial: multiple roles/nesting | A Section 4.3/5.1 |
| Incorrect norm types | B | modality confusion | B Section 4 |
| Incorrect norm elements | B | actor/condition/constraint extraction errors | B Section 4 |
| Overlooked crucial details | B | missing condition/constraint details | B Section 4 |
| Hallucination | B, F | unsupported content | B Section 4; F error typology |
| Incorrect conjunction parsing | B | coordinated conditions/constraints | B Section 4 |
| Empty norm elements | B | empty-Gold actor; absent fields | B Section 4 |
| Over-extraction/no omission | C | empty-Gold actor over-extraction | C Figure 7 prompt |
| JSON schema mismatch fixed by one-shot example | E | output serialization, not semantic boundary | E Section 6.2.2 |
| Misclassifying concept type as definition/exception; type of change as condition-constrained | E | role/concept confusion | E Section 6.3.2 |
| Reasoning failure / input interpretation / context retrieval / hallucination | F | some analogies but different task | F Section 6.3/7 |
| Sentence-level compliance classification errors | G | not the same as field extraction | G evaluation |

No paper reports the exact failure "applicability condition content predicted as constraint while whole condition also belongs to condition." E's threshold/condition example is suggestive but not an error analysis of nested spans.

---

## 17. Directly transferable ideas

There are no high-value new prompt instructions that are both directly compatible and not already covered.

Conceptually transferable, but already present:
- exception semantics;
- actor responsibility criterion;
- action vs modality distinction;
- structured output discipline;
- controlled vocabularies.

No recommendation for new prompt text is made.

---

## 18. Already-covered ideas

- Condition definition: current S rule 5.
- Constraint definition: current S rule 6 and R_C.
- Exception definition: current S rule 7.
- Field partition and no folding into action: current S rule 8.
- Constraint nested inside condition reported in both arrays: S rule 8 plus E5 example ("within two years").
- Explicit-only actor and no-actor handling: R_A.
- Synthetic worked examples: E, including E5.
- Shared structured-output baseline and canonicalizer: current project already has it; literature JSON practice does not justify restoring J.

---

## 19. Incompatible ideas

- LegalDiscourse `"passive voice entity"` / implied passive subjects: conflicts with empty-Gold actor.
- COLING 2025 broad all-subjects + no-omission completeness: conflicts with explicit-only R_A.
- Haque & Singh empty subject "all parties" or "no party" ambiguity: not a safe rule.
- Haque & Singh `object` as counterparty: cannot be renamed to our action object.
- LegalDiscourse same entity as both SUBJECT and OBJECT -> annotate as OBJECT: conflicts with our possible multi-role/nested arrays and different schema.
- DPLACC `[MASK]` prompt learning: conceptually different from instruction-based prompting.
- Kölbel BPMN/external-standard question answering: different task and unit; no condition/constraint roles.
- RC4PC pattern labels: not our span semantics; do not rename into `constraint`.

---

## 20. Open questions

1. Does our Gold actually contain cases where a threshold/time phrase is **both** a full condition child and a separate constraint? Current E5 and S rule 8 say yes structurally, but the literature review cannot validate the Gold policy.
2. Should condition/constraint be evaluated with overlap-aware metrics? Literature does not provide a public metric for this.
3. Would a contrastive example pair (otherwise similar sentence with and without nested constraint) improve boundary learning? No public example design was found; current E has only positive worked examples.
4. Are there other legal-NLP schemas (outside A-G) that explicitly define `condition` vs `constraint` with overlap rules? Not covered by this review.
5. Would a schema-level `action_object` field clarify actor/action/constraint boundaries? E suggests it, but this is a schema decision, not a prompt-design decision.
6. Does the current complete-condition + nested-constraint S rule have enough positive Gold evidence? This is a project dataset question, not a literature question.

---

## 21. Sources / links

### Paper A
- DOI: https://doi.org/10.18653/v1/2024.naacl-long.472
- ACL page: https://aclanthology.org/2024.naacl-long.472/
- PDF: https://aclanthology.org/2024.naacl-long.472.pdf

### Paper B
- DOI: https://doi.org/10.1007/978-3-031-82039-7_8
- arXiv: https://arxiv.org/abs/2404.02269
- arXiv PDF: https://arxiv.org/pdf/2404.02269v1
- Publisher: https://link.springer.com/chapter/10.1007/978-3-031-82039-7_8

### Paper C
- ACL page: https://aclanthology.org/2025.coling-main.178/
- PDF: https://aclanthology.org/2025.coling-main.178.pdf
- BibTeX: https://aclanthology.org/2025.coling-main.178.bib

### Paper D
- DOI: https://doi.org/10.1016/j.infsof.2026.108079
- Publisher: https://www.sciencedirect.com/science/article/pii/S0950584926000686
- Repository copy PDF: https://pure.tue.nl/ws/files/390845624/1-s2.0-S0950584926000686-main.pdf
- TU/e landing: https://research.tue.nl/en/publications/62c8c550-3618-402a-9a69-ba150e9f62cf
- Code/prompt repo: https://anonymous.4open.science/r/Requirements_Change_for_Business_Process_Compliance
- Exact prompt: https://anonymous.4open.science/api/repo/Requirements_Change_for_Business_Process_Compliance/file/data/input/prompts/formalize_requirements_prompt.txt

### Paper E
- DOI: https://doi.org/10.1007/s12599-026-01008-x
- PDF: https://link.springer.com/content/pdf/10.1007/s12599-026-01008-x.pdf
- GitHub: https://github.com/marisol-barrientos/LegalChanges4BPC
- Exact prompt: https://raw.githubusercontent.com/marisol-barrientos/LegalChanges4BPC/main/data/input/prompts/prompt_review.txt

### Paper F
- DOI: https://doi.org/10.1007/s10207-026-01245-x
- PDF: https://link.springer.com/content/pdf/10.1007/s10207-026-01245-x.pdf
- GitHub: https://github.com/LeoPoss/contextIsKey
- ISO prompt builder: https://raw.githubusercontent.com/LeoPoss/contextIsKey/main/ISO27001/prompt.py
- IEC prompt builder: https://raw.githubusercontent.com/LeoPoss/contextIsKey/main/IEC62443/prompt.py

### Paper G
- DOI: https://doi.org/10.3390/bdcc10030095
- MDPI page: https://www.mdpi.com/2504-2289/10/3/95
- PDF (direct download blocked in this environment): https://www.mdpi.com/2504-2289/10/3/95/pdf

### Supporting citation
- Sun, X., Yang, S., Zhao, C., & Yu, D. (2024). Design-time business process compliance assessment based on multi-granularity semantic information. The Journal of Supercomputing, 80(4), 4943-4971.
- DOI: https://doi.org/10.1007/s11227-023-05626-0

### Project internal files referenced
- `formal_experiment/prompts/sun_compat/modular_v1/common_system.md`
- `formal_experiment/prompts/sun_compat/modular_v1/semantic_rules_S.md`
- `formal_experiment/prompts/sun_compat/modular_v1/examples_E.md`
- `formal_experiment/src/bpc_hybrid/modular_refinement_prompt.py`

---

## Repository status

No new BPC prompt was designed or modified. No Stage 2 API calls were made. Git commit/push status is reported in the final user-facing summary after the scoped commit.
