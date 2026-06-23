# R13.9 Resume and Interview Talking Points

## 1. Safe Resume Version

Use these bullet points when listing this project on a resume or CV. These
statements stay within the accepted evidence boundary.

### Project Title

**bpc-hybrid: Rule-first LLM-assisted Regulatory Semantic Extraction Prototype**

### Bullet Points

- Built an audit-gated prototype workflow for structured regulatory semantic
  extraction, combining rule-first design, schema-constrained LLM fallback,
  field-level mini-gold evaluation, and bounded real API mini-pilots.
- Implemented a deterministic multi-clause regulatory text pipeline: regex-based
  extractor → clause splitter → field-level evaluator with exact/partial/wrong/
  missing scoring across 6 semantic dimensions (modality, actor, action,
  condition, constraint, exception).
- Designed and executed a bounded prompt-iteration experiment chain: baseline
  mini-pilot → error analysis → prompt refinement design → few-shot Prompt B
  pilot → descriptive comparison — all under explicit user authorization and
  Codex audit checkpoints.
- Engineered production-style safety controls: JSON Schema validation gates,
  secret redaction, raw response suppression, authorization consumption,
  audit-safe environment isolation, and call-count tracking.
- 708 automated tests; all real API calls were single-attempt, non-batch, and
  raw-response-free.

### Technologies

Python, pytest, JSON Schema, regex, openai-compatible API, Git/GitHub, VS Code,
Codex audit workflow.

## 2. Stronger Resume Version With Boundaries

Use these if you have space to include explicit boundaries:

- Designed and evaluated a rule-first LLM-assisted regulatory extraction
  pipeline across a bounded 8-sample mini-pilot chain (GDPR EUR-Lex +
  Austrian Income Tax Code). **Note: This is a small-scale research prototype,
  not a benchmark or production system.**
- Implemented field-level evaluation with 6 semantic dimensions and a
  prompt-iteration workflow (baseline → few-shot) that shifted failure
  categories from 15 to 1 in an 8-sample descriptive comparison.
  **Note: 8 samples only — no statistical significance or method validation
  is claimed.**
- Built comprehensive safety infrastructure: authorization-gated real API
  execution, secret redaction, raw response suppression, and audit-safe
  environment isolation — enabling transparent, auditable LLM experimentation.

## 3. Interview 30-second Version

"I built a prototype pipeline for extracting structured semantic components
from regulatory text — things like modality, actor, action, condition, and
constraint. The pipeline uses a rule-first approach: deterministic regex
extraction as the primary path, with an LLM fallback that's constrained by
a strict JSON Schema. I ran a bounded experiment chain — a baseline mini-pilot
on 8 real legal samples, then an error analysis, then a refined prompt design,
then a second pilot with few-shot prompting — all under explicit authorization
gates. The whole workflow was audit-gated: no raw responses saved, no batch
execution, no unsupervised API calls. It's a small-scale research prototype,
not a production system, but it demonstrates how to do safe, auditable LLM
experimentation in a compliance-sensitive domain."

## 4. Interview 2-minute Version

"The project is called bpc-hybrid. The core idea is: can we extract structured
semantic information from regulatory text — modality, actor, action, condition,
constraint, exception — using a hybrid of deterministic rules and schema-constrained
LLMs?

The rule-first extractor is a regex-based pipeline that handles modality markers,
active/passive voice, unless-to-condition mapping, and constraint detection. It's
fast, deterministic, and interpretable — but it's brittle to linguistic variation,
especially passive voice and cross-lingual inputs.

So I added a controlled LLM fallback path — but with very strict constraints:
the LLM must return JSON matching our exact schema, with specific field names
and types. Schema-invalid responses are rejected. The output goes through a
normalizer and span repair before being accepted.

To test this, I ran a bounded mini-pilot chain on 8 real legal samples — 5 from
GDPR and 3 from Austrian tax code. I did a baseline run with an instruction-only
prompt, analyzed the error patterns, designed three prompt variants, selected a
few-shot prompt with 4 examples covering obligation, prohibition, definition, and
passive-voice inference, and ran a second pilot.

The descriptive comparison showed count-level differences — the few-shot prompt
shifted from German to English outputs, eliminated null actors, and reduced
failure categories from 15 to 1. But crucially, this is an 8-sample observation —
it is not a benchmark, it is not method validation, and it does not prove that
Prompt B is superior. It's descriptive evidence from a small-scale experiment.

The engineering side was also a focus: every real API call required explicit user
authorization, secrets were redacted in all logs, raw LLM responses were never
saved to disk, and the entire workflow was designed to pass Codex audit checkpoints."

## 5. Technical Deep-dive Talking Points

### 5.1 Why Rule-first?

- Deterministic, interpretable, and consistent — you get the same output for the
  same input every time.
- Zero cost per extraction — no API calls needed for cases the rules can handle.
- Provides a baseline: you can measure how much the LLM adds beyond what rules
  already capture.
- Safety: rules never hallucinate. In a compliance-sensitive domain, this matters.

### 5.2 Why LLM Only as Fallback / Structured Extraction?

- Not using LLM as a reasoning engine — only as a structured extraction tool.
- The LLM's job is to fill in fields that rules miss, constrained by the same
  JSON Schema that the rules produce.
- This constrains the LLM's degrees of freedom and makes output predictable.
- Schema-invalid outputs are rejected — the rule-first result is preserved.

### 5.3 Why JSON Schema?

- Without a schema, LLM outputs drift — field names change, types change,
  structure changes between calls.
- A strict JSON Schema acts as a contract: if the LLM doesn't produce valid
  output, the fallback is aborted and the rule result stands.
- Schema validation is fast, deterministic, and auditable.

### 5.4 Why Field-level Evaluation?

- End-to-end accuracy on regulatory extraction is misleading — a prediction
  might get 5 out of 6 fields right and still be counted as "wrong."
- Field-level exact/partial/wrong/missing scoring gives granular feedback on
  which semantic dimensions are challenging.
- This granularity directly informed the prompt refinement design.

### 5.5 Why Audit-gated API Execution?

- Real API calls in a research project create evidence — but also risk:
  cost, secret leakage, batch accidents, raw response exposure.
- An authorization gate means every real API call is an explicit decision,
  not an automated pipeline.
- Audit checkpoints (before and after each real-API stage) ensure that
  no overclaiming, secret leakage, or scope creep occurs.

### 5.6 The R13.4.2 → R13.7 Iteration Logic

1. R13.4.2 (baseline): Ran 8 real samples with instruction-only prompt.
   Found 7 systematic error patterns: null actors from passive voice,
   verbatim action fragments, wrong modality on German definitions,
   German-language outputs, wrong/missing conditions and constraints.

2. R13.5: Categorized the errors and identified prompt-design hypotheses.

3. R13.6: Designed 3 prompt variants. Selected Prompt B (few-shot extraction
   with 4 examples covering obligation, prohibition, definition, and
   passive-voice inference).

4. R13.7: Ran Prompt B on the same 8 samples under explicit authorization.
   All 8 schema-valid. Descriptive comparison showed count-level differences
   consistent with the few-shot design — but only for these 8 samples.

### 5.7 Why R13.8 Is Only a Descriptive Comparison

- 8 samples is too few for statistical conclusions.
- Both runs used the same samples — no held-out set.
- The gold was manually reviewed by a single person.
- Only one model (qwen3.7-max) was tested.
- Only 2 legal domains were covered.
- Therefore: descriptive comparison only. No benchmark. No method validation.

## 6. What Not To Say

During interviews or conversations, avoid these statements:

| Don't Say | Why Not |
|-----------|---------|
| "We validated a GDPR compliance detection method." | Not validated — 8-sample descriptive evidence only. |
| "We beat the Sun et al. baseline." | No Sun reproduction was performed. |
| "We built a production-ready GDPR checker." | Research prototype only — no deployment, no adversarial testing. |
| "Prompt B is proven better than the baseline." | Descriptive comparison of 8 samples — no causal claim. |
| "We achieved benchmark-level accuracy." | No benchmark protocol, no statistical testing. |
| "Our method outperforms existing approaches." | No comparison against published baselines. |
| "We solved regulatory semantic extraction." | Only 2 domains, 8 samples, significant remaining weaknesses. |

## 7. If Asked About Results

**Safe answer**: "We observed descriptive count differences between our baseline
and few-shot prompt on an 8-sample mini-pilot. The few-shot prompt produced
normalized English outputs, reduced null actors, and eliminated wrong condition/
constraint labels. But with only 8 samples from 2 legal domains, these are
observations — not statistically significant findings. The value of the project
is more in the workflow design and safety engineering than in the raw numbers."

## 8. If Asked About Limitations

**Safe answer**: "The main limitation is sample size and scope. We tested 8
samples from 2 legal domains with one model. There's no held-out test set,
no multi-annotator gold standard, no cross-domain coverage, and no adversarial
evaluation. The gold was reviewed by me, not by legal experts. Exception-field
evaluation is completely missing because none of our samples contain exceptions.
Any generalization beyond these 8 samples would be inappropriate."

## 9. If Asked About Next Steps

**Safe answer**: "The natural next step would be expanding the sample set to
get more domains, more exception-bearing samples, and enough data for statistical
analysis. Testing different prompt variants or different models would also add
descriptive evidence. But each next step requires a new authorization, planning,
and audit cycle — the project is designed to move carefully, not fast."
