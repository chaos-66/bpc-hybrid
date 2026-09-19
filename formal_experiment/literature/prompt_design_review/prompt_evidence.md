# Prompt Evidence

This file records what was actually found, where it came from, and how it was verified. Exact prompt excerpts are stored in `prompt_excerpts/` when the source is small enough. Large paper excerpts are not committed as PDFs; local paths are recorded in `sources_manifest.json`.

Evidence labels:
- **Verified**: directly supported by the cited paper, appendix, repository file, or code.
- **Strongly suggested**: supported consistently by multiple verified statements, without one explicit rule sentence.
- **Interpretation**: our mapping, not a claim made by the paper.

---

## A. LegalDiscourse (NAACL 2024)

Source of prompt evidence: ACL Anthology PDF `https://aclanthology.org/2024.naacl-long.472.pdf`, Appendix F, printed pp. 8551-8555. Raw extracted Appendix F block: `prompt_excerpts/legal_discourse_appendix_F_raw.txt` (PyMuPDF extraction from local PDF).

Public prompt: **yes**. Appendix F gives one-shot span tagging prompts for SUBJECT, EXCEPTION, TEST, OBJECT, PROBE, CONSEQUENCE, plus relation identification and relation classification prompts with and without definitions.

Key exact components (Verified):
- All span prompts begin: "You are a legal assistant. I will show you a paragraph of law."
- SUBJECT prompt asks which entities "gains powers, restrictions or responsibilities under this law"; explicitly says NOT which entities are used to test the law or which entities are affected.
- EXCEPTION prompt asks "What are exception cases when this law does not apply?" and says to say "none" if none.
- TEST prompt asks "Under what conditions does this law apply? In other words, what test is implied by the law?" and says to say "none" if there are no explicitly stated conditions.
- OBJECT prompt asks which entities are affected by the powers of the law; PROBE prompt asks which entities are used to determine when the law applies.
- CONSEQUENCE prompt asks "What are the powers or obligations granted by this law?"
- Output discipline: "Restrict your answer to text in the law. Join non-contiguous segments of text with a semi-colon. ... The order of text spans does NOT matter. Do NOT say anything else."
- Few-shot setup: each span prompt is shown as 1-shot; the paper states it tested 0, 1, 2, 3, 5, 8 and 10 shots.

No-answer handling: SUBJECT, OBJECT, PROBE say "no entity"; EXCEPTION, TEST, CONSEQUENCE say "none".

Span/boundary rules: the prompt says to restrict to the law text and join non-contiguous segments with semicolons, but does not define minimal/complete span boundaries or overlap/nesting. The paper itself discusses recursive parse ambiguity and says annotators were advised "to parse to the lowest-level" (Section 3.2, around Figure 4), and later says there is no single correct parse (Section 10.1). It also says a single entity can be both SUBJECT and OBJECT, and in those cases it was annotated as OBJECT (Section 5.1).

Relation prompts: F.2.1/F.2.2 identification ("yes"/"no" for direct relation); F.2.4/F.2.5 classification with labels `[Same Entity, Or, Continuation, And, Followed By, No Relation]`; F.2.5 includes short label definitions, e.g. `Same Entity`, `Or`, `Continuation`, `And`, `No Relation`.

Error analysis reported by the authors (Verified): GPT was especially challenged at distinguishing entity roles SUBJECT, OBJECT, PROBE; the paper says SUBJECT and OBJECT can be particularly ambiguous and that a single entity can occupy both roles; the generative setup could "generate the same entity for different categories." Span-level errors mostly concerned where to split spans into sub-spans.

Transfer warning: this schema has no separate `constraint` label. Restriction-like content belongs under CONSEQUENCE; applicability belongs under TEST/EXCEPTION. Mapping TEST directly to our `condition` is an **Interpretation** and carries risk.

---

## B. Haque & Singh (COINE 2024 / arXiv 2404.02269)

Source of prompt evidence: arXiv:2404.02269v1, Section 3.2, PDF p. 7. Exact prompt file: `prompt_excerpts/haque_singh_prompt_exact.md` (transcribed from public arXiv PDF).

Public prompt: **yes in public preprint**. The publisher Springer chapter is not open access; no public code/supplement found.

Exact component (Verified):
- The prompt states a norm is represented by "four elements subject, object, antecedent, and consequent."
- `subject` = "the party on whom the norm applies."
- `object` = "the party with respect to whom the norm applies."
- `antecedent` = "which brings the norm into force, i.e., the condition on which the action of the subject depends."
- `consequent` = "which brings the norm to satisfaction, i.e., the outcomes of the action."
- Four norm types: commitment, prohibition, authorization, power, each with directionality definitions.
- Output fields: Norm type, Subject, Object, Antecedent, Consequent.
- Zero-shot: no examples in the prompt; no negative examples.

Span/boundary rules: not specified. The prompt asks for elements and the examples are normalized/inferential strings (e.g., "Rogers providing sixty (60) days' prior written notice"), not exact source spans. Thus it does **not** provide span-boundary or overlap/nesting rules.

Reported errors (Verified): incorrect norm type, incorrect norm elements, overlooking crucial details, hallucination, incorrect parsing of conjunctions, and empty norm elements. The authors say empty subject/object might mean "no party" or "all parties," which is ambiguous. They state that adding explicit subject/object directionality to the prompt reduced role mismatches.

Transfer warning: `object` is a counterparty/party, not our action object; `antecedent` and `consequent` are event-level norm elements, not span labels. This prompts no direct mapping to our `condition`/`constraint` boundary.

---

## C. Jingyun Sun, Luo & Li (COLING 2025)

Source of prompt evidence: ACL Anthology PDF `https://aclanthology.org/2025.coling-main.178.pdf`, Appendix C, Figure 7 and Figure 8, printed p. 2614 (PDF page 12). Exact raw Chinese page block: `prompt_excerpts/coling2025_templates_exact.md`.

Public prompt: **yes**. It is a template embedded in the paper, not a separate prompt repo. No public code/supplement found after search.

Figure 7 (Verified): asks the model to read a regulatory document and identify **all subjects constrained by deontic norms**. It says subjects may include but are not limited to organizations, companies, government departments, non-profit organizations, and individuals; it points to words such as "must comply", "is obligated", and "should"; it asks for a clear list of subjects and their related deontic constraints; it emphasizes accuracy and completeness and says not to miss any relevant information. It includes one illustrative example: "The company must protect customers' personal information" -> subject "company", deontic constraint "protect customers' personal information".

Figure 8 (Verified): asks the model to read a paragraph, identify deontic words related to the constrained subject, and give a short explanation for each. It defines deontic words as words expressing moral/legal obligation, responsibility, or norm (e.g., "must", "should", "prohibited", "responsibility") and includes one illustrative example.

No-answer handling: not addressed. Completeness guidance: very strong ("accuracy and completeness are very important ... do not omit any relevant information"). No explicit span/boundary rule, no overlap/nesting rule, no object/resource/amount exclusion.

Transfer warning for R_A: this is the clearest **conflict** source. Its broad "all constrained subjects" plus "do not omit relevant information" could encourage extraction of objects/resources/amounts when no responsible entity is explicit, which is exactly the empty-Gold actor failure that R_A was designed to suppress.

---

## D. RC4PC (IST 2026)

Source of prompt evidence: paper Section 5.1 and footnote 2; exact prompt file in the public anonymous repository:
`https://anonymous.4open.science/api/repo/Requirements_Change_for_Business_Process_Compliance/file/data/input/prompts/formalize_requirements_prompt.txt`
Local copy: `prompt_excerpts/rc4pc_formalize_requirements_prompt_exact.txt` (from repository zip).

Public prompt: **yes**. The paper states "The full implementation and prompts are available online."

Exact prompt components (Verified):
- System role: "You are an expert in formalizing procedural and compliance requirements, later used to verify business process compliance."
- Strict output: "Do not include any explanation, commentary, reasoning steps, or thinking - only return the JSON object as valid JSON"; "no code fences, explanations, or additional text."
- Mandatory JSON structure: `id`, `precondition` (object with exactly `and`, `or`, `not`, each a list of actions), `norms` (modality one of ["obligation", "permission", "prohibition"], action object), `temporal_validity` (`start`, `end`).
- Each action object has `dimension` in ["control_flow", "data", "resource", "time"] and `compliance_pattern` from a controlled list; optional `activities`, `resources`, `data_values`, `temporal_constraints`.
- Controlled vocabulary lists all allowed compliance patterns (e.g., `data_in_range`, `duration`, `validity_period`).
- Negative constraints: "do NOT invent new patterns"; control-flow exclusivity rule; label/structure consistency across versions; temporal validity defaults; semantics of norms ("what is not obligated is by default considered permitted but not prohibited; only actions explicitly indicated as prohibited are treated as 'prohibition'").
- The prompt is zero-shot (no worked examples). The no-patterns variant (`formalize_requirements_prompt_no_patterns.txt`) is an ablation control.

Condition/constraint relevance (Interpretation): the schema separates a factual `precondition` from deontic `norms`, but `constraint` is not a separate top-level semantic role. Restrictions become typed action objects/compliance patterns with optional nested `temporal_constraints` in either the precondition or a norm. This is a formal representation of nesting, not a span-annotation overlap rule.

---

## E. LegalChanges4BPC (BISE 2026)

Source of prompt evidence: paper Section 6.2.2 and Figure 8 (simplified prompt); exact final one-shot prompt at
`https://raw.githubusercontent.com/marisol-barrientos/LegalChanges4BPC/main/data/input/prompts/prompt_review.txt`
Local copy: `prompt_excerpts/legalchanges4bpc_prompt_review_exact.txt`. Commit history inspected: `4f3291c2afb306a89314f6a08f9a7ac8cc2d0378` and `0a6df8379108f48f5f565df4a124e644dc391bd8`.

Public prompt: **yes**. The final prompt includes one input/output example. The paper says the prompt was created by a two-round process: the initial version had goal + task/input/output specifications + controlled vocabulary; after JSON-schema mismatch, round 2 added one-shot input/expected-output example. An exact public snapshot of the pre-example round-1 prompt was **not found** in the repository history; only the paper's description is verified.

Exact prompt components (Verified):
- Role/context: "As a business process compliance expert..."
- Task: analyze two versions of a legal provision and return one or more entries, one per statement-level change.
- 13 output keys include `evolution_id`, `old_statement`, `new_statement`, `type_of_statement`, `type_of_statement_change`, `concepts_modified`, `is_potentially_relevant_for_bpc`, `justification_of_relevance`, `example_bpmn_elements`, `example_business_process`, and cross-reference change keys.
- Statement types: obligation, prohibition, permission, definition.
- Controlled concept vocabulary (the key evidence for our fields):
  - `actor`: "The role responsible for executing the action."
  - `action`: "The activity that is mandatory, prohibited, or permitted."
  - `action_object`: "The item being acted upon."
  - `condition`: "Specifies when the statement applies."
  - `constraint`: "A restriction limiting how or when the regulation is applicable."
  - `exception`: "Conditions under which the regulation does not apply."
- Output discipline: "Return only a JSON array of objects using the field names above. No prose, no markdown, no explanation."
- One-shot example: gluten-free labeling; for one modified statement the example sets `"concepts_modified": "constraint, condition, action_object"` and justification "threshold ... was tightened and a new disclosure condition was added"; another added prohibition sets `"concepts_modified": "action_object, condition"`.

Condition/constraint relevance (Verified + Interpretation):
- Verified: the prompt defines `condition`, `constraint`, and `exception` separately, with `constraint` as a restriction on how/when the regulation is applicable.
- Verified: the example labels a numeric threshold change as `constraint` and a new disclosure clause as `condition` in the same modified statement.
- Not specified: span boundaries, minimal/complete spans, overlapping spans, nested spans, or multi-role spans. `concepts_modified` is a comma-separated list of changed concept types, not a per-span multi-label annotation rule.

---

## F. Kölbel, Poss & Schönig (2026, optional experimental-design reference)

Source: Springer PDF `https://link.springer.com/content/pdf/10.1007/s10207-026-01245-x.pdf`, Section 5.1.4 and Section 5.2; exact prompt builder in `https://github.com/LeoPoss/contextIsKey` (`ISO27001/prompt.py`, `IEC62443/prompt.py`).

Public prompt: **yes**. It is a modular prompt builder, not a semantic-role extraction prompt. It includes configurable `include_role`, `include_few_shot`, `include_chain_of_thought`, `include_context`, and `include_format` flags. The prompt is assembled dynamically from:
1. role instruction if enabled,
2. `**Question:** {question}`,
3. format instructions if enabled,
4. few-shot examples if enabled,
5. chain-of-thought instructions if enabled,
6. external standard/context if enabled,
7. process model XML,
8. repeated `**Now, answer the question:** {question}`.

Verified prompt components:
- Role example: "You are an expert in Information Security and ISO/IEC 27001 compliance..."
- Zero-shot example: "Answer the following question: [Question]"
- Format instructions include "base your entire analysis ... SOLELY on the information explicitly modeled in the provided BPMN process model"; "Do NOT make assumptions"; and labels `Fully Met`, `Partially Met`, `Not Met`, `Cannot Determine`.
- Missing-information handling: state exactly what modeled information is needed; "Do NOT infer non-compliance simply because an aspect is not modeled."
- Error typology from the paper: Reasoning Failure, Input Interpretation Failure, Context Retrieval Failure, Hallucination.

Transfer boundary: this is an experimental-design reference for modular composition and control experiments. It does **not** define condition/constraint span roles and should not be auto-migrated into Stage 2.

---

## G. DPLACC (2026, optional)

Source: MDPI HTML/PDF text via `r.jina.ai`; metadata from Crossref: DOI `10.3390/bdcc10030095`. Local extracted text: `.tmp/lit/text/dplacc_2026_jina.md`. Direct MDPI PDF download was blocked.

Public prompt: **partial / conceptually different**. The paper is grounded in **prompt learning**, not instruction-based LLM prompting.

Verified components:
- Definition: "prompt learning reconstructs the downstream task to masked language modeling, which aligns with the pre-training objective of PLM."
- Template: `Does x1 meet the requirements of x2? [MASK]`
- Label words: `"yes"` means x1 satisfies x2, `"no"` means it does not.
- The model predicts the `[MASK]` token from the contextualized representation; the first-order-logic semantic vector is fused with the mask-token representation, e.g. `h_tilde_m = (h_m + r) / 2`.
- It uses Prolog for interpretable logical reasoning.
- It uses an LLM (Qwen3) for syntactic parsing with a system message, but the core compliance decision is masked-token prompt learning, not an instruction-following extraction prompt.

Transfer boundary: **conceptually different from current instruction Prompt design**. Do not treat this as a prompt-engineering reference for Stage 2 field extraction.

---

## Source-verification summary

| Paper | Full text found | Public prompt | Prompt location | Code/supplement |
|---|---|---|---|---|
| LegalDiscourse | yes, ACL Anthology PDF | yes | Appendix F, pp. 8551-8555 | code release promised; URL not found |
| Haque & Singh | yes, arXiv preprint; publisher paywalled | yes | Section 3.2, p. 7 | not found |
| Sun/Luo/Li COLING 2025 | yes, ACL Anthology PDF | yes | Appendix C, Figure 7/8, p. 2614 | not found |
| RC4PC | yes, TU/e repository PDF | yes | repo `formalize_requirements_prompt.txt` + Section 5.1 | anonymous repo with code/prompts/data |
| LegalChanges4BPC | yes, Springer CC BY PDF | yes | GitHub prompt_review.txt + Section 6.2.2/Fig. 8 | GitHub repo |
| Kölbel et al. | yes, Springer PDF | yes | GitHub prompt.py + Section 5.1.4 | GitHub repo |
| DPLACC | yes via Jina reader; direct MDPI PDF blocked | partial (prompt-learning template) | Section 4.4.2, [MASK] template | no code repo found |
