# Research Idea: Rule-First LLM-Assisted Hybrid Framework for Design-Time Business Process Compliance Assessment

## 1. Project Positioning

`bpc-hybrid` is a rule-first LLM-assisted hybrid framework for design-time business process compliance assessment.

The framework uses Sun-style rule-template / marker-based regulatory semantic extraction as its primary path, and introduces LLM structured formalization as a controlled fallback. The goal is to combine the consistency and interpretability of rule-based methods with the flexibility of LLMs for handling complex regulatory text, while keeping hallucination and representation inconsistency under control.

**Current status**: R1 completes a runnable minimal Python scaffold / MVP skeleton. This is not a validated system. It does not contain real GDPR data, BPMN models, Sun-aligned benchmark data, LLM API calls, compliance checking logic, or benchmark results.

## 2. Relation to Prior Work

### 2.1 Sun-style Rule-template / Marker-based Extraction

Sun et al. demonstrated that rule-template and marker-based extraction from regulatory text achieves high consistency, low cost, interpretability, and deterministic traceability. The method extracts six categories of regulatory elements:

1. **Modality** — obligation, permission, prohibition (shall / may / must not)
2. **Actor** — the subject bound by the rule
3. **Action** — the required, permitted, or prohibited activity
4. **Condition** — triggering or qualifying conditions
5. **Constraint** — temporal, spatial, or scope constraints
6. **Exception** — exemptions and special cases

**Strengths**: high consistency, low computational cost, interpretable results, deterministic traceability from source text to structured output.

**Limitations**: struggles with compound normative sentences containing multiple modalities (e.g., may + shall in the same sentence), long sentences with ambiguous element boundaries, missing actor or action in implicit constructions, and parser failure on cross-referencing clauses.

This project retains Sun-style extraction as the primary path.

### 2.2 LLM Structured Formalization

Work by RC4PC and Barrientos et al. introduced LLM-based structured formalization of regulatory text, with key contributions including:

- Controlled vocabulary to constrain LLM output space
- Strict JSON schema to enforce output structure
- Span normalization to reduce representation inconsistency

This project incorporates these ideas as a controlled fallback mechanism. LLMs are invoked only when the rule-based extractor triggers specific failure conditions (multi-modality, missing actor/action, parser failure, low-confidence matching). All LLM outputs must pass schema validation, span normalization, and deterministic post-processing.

### 2.3 Winter-style Textual Baseline

Winter-style methods represent a pure LLM / pure text approach to regulatory formalization, where the LLM performs end-to-end conversion from natural language to structured representation without rule templates.

**Strengths**: high flexibility, generalization to unseen sentence patterns.

**Weaknesses**: limited interpretability, representation inconsistency (same semantics expressed differently across outputs), hallucination risk, lack of deterministic traceability.

This project uses Winter-style methods as a comparison baseline in future formal benchmarking.

## 3. Why Rule-first + LLM-assisted Hybrid

| Dimension | Pure Rule (Sun) | Pure LLM (Winter) | Hybrid (this project) |
|-----------|----------------|-------------------|----------------------|
| Consistency | High | Low | High (rule-dominant) |
| Coverage | Limited by templates | High | Complementary |
| Interpretability | High | Low | High (rule path traceable) |
| Cost | Low | High | Medium (LLM fallback only) |
| Long sentence handling | Weak | Strong | Complementary |
| Hallucination risk | None | High | Controlled (schema + normalization) |

The hybrid architecture ensures that the majority of regulatory text is handled by the deterministic rule path, while LLMs are reserved for cases where rules fail. This preserves the interpretability and consistency advantages of rule-based methods while extending coverage through controlled LLM assistance.

## 4. Planned Multi-clause Schema

Sun-style single-record representation maps one regulatory sentence to one structured record. This assumption breaks when a single sentence contains multiple normative clauses with different modalities (e.g., compound sentences with may + shall).

The planned multi-clause schema addresses this by:

1. Allowing one regulatory sentence to be decomposed into multiple **normative clauses**
2. Each clause independently carries modality, actor, action, condition, constraint, and exception
3. Clauses preserve hierarchical relationships (parent-child, conjunctive, disjunctive)
4. The schema degrades to Sun-style flat representation when only a single clause is present

This is a **planned core architectural change**, not yet implemented.

## 5. Planned Deterministic Normalization

LLM outputs, even under strict JSON schema constraints, exhibit representation inconsistency:

- **Synonym variation**: "data controller" vs "controller" vs "the controller"
- **Preposition variation**: "in accordance with" vs "pursuant to" vs "under"
- **Tense variation**: "processes" vs "processing" vs "to process"
- **Conditional patterns**: "if X, then Y" vs "Y, provided that X" vs "where X, Y"

Planned deterministic normalization will address this through:

1. **Span normalization**: mapping LLM output text spans to controlled vocabulary
2. **Pattern canonicalization**: converting conditional constructions to standard forms
3. **Modality resolution**: resolving ambiguous modality expressions to standard labels
4. **Fully deterministic post-processing**: no additional LLM calls, avoiding second-order inconsistency

This is **planned**, not yet implemented.

## 6. Prototype vs Formal Benchmark Boundary

| Level | Definition | Current Status |
|-------|-----------|----------------|
| **Prototype (MVP skeleton)** | Runnable code scaffold validating architecture feasibility | ✅ R1 completed |
| **Synthetic prototype** | Small-scale artificial data for pipeline sanity checks | 🔲 Planned (R5+) |
| **Formal benchmark** | Sun-aligned GDPR + BPMN dataset, compared against baselines on precision / recall / F1 / AP / MAP | 🔲 Future phase |

**Current R1 completes a runnable minimal Python scaffold / MVP skeleton.** It does not constitute method validation. Synthetic prototype evaluation, if introduced at R5 or later, will be used for pipeline sanity checks only — not for benchmark claims. Formal benchmark results require Sun-aligned GDPR + BPMN data and are not available in the current phase.

## 7. Dataset Boundary

| Dataset | Role | Current Status |
|---------|------|----------------|
| **Sun-aligned GDPR + BPMN** | Primary formal benchmark dataset | 🔲 To be introduced |
| **EStG / Austrian Income Tax Act** | Optional generalization corpus | 🔲 Future phase |

**EStG positioning**: EStG (Austrian Income Tax Act) may only be used as an optional generalization corpus to validate framework portability to non-GDPR regulations. It **cannot replace** the Sun-aligned GDPR + BPMN dataset because:

1. Sun baseline results are based on GDPR; comparison requires the same dataset
2. EStG has different regulatory structure and semantic characteristics
3. Using EStG would not allow apples-to-apples comparison with Sun

## 8. Forbidden Claims

The following claims must **not** be made in the current phase:

- ❌ "Outperforms Sun"
- ❌ "Validated on Sun's original dataset"
- ❌ "Qwen surpasses rule baseline"
- ❌ "Synthetic prototype is a benchmark"
- ❌ "EStG can replace Sun dataset"
- ❌ "LLM automatically updates the rule base"
- ❌ "BPMN compliance checking is complete"
- ❌ "Over-compliance detection is complete"
- ❌ "Method validation is complete" (requires R5+)

The following statements are **permitted**:

- ✅ "Current phase completes a runnable MVP skeleton"
- ✅ "Rule-first + LLM-assisted is the research framework"
- ✅ "Multi-clause schema is a planned core architectural change"
- ✅ "Deterministic normalization is planned to reduce LLM representation inconsistency"
- ✅ "Sun-aligned GDPR + BPMN is the future formal benchmark target"
- ✅ "No benchmark results are claimed in the current phase"
