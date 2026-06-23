# Method Alignment Table

The agent must complete this table before claiming paper alignment.

| Paper Method Component | Evidence from Paper | Current Implementation File | Current Status | Required Fix | Verification Command |
|---|---|---|---|---|---|
| Dataset source | Sun uses Austrian Income Tax Code (Dataset A, B) and GDPR BPMN models (Dataset C, D). See Section 5.1. | `data/formal/r14_controlled/r14_1_candidate_samples.jsonl` (24 samples, GDPR + Austrian tax style). | Partially aligned: we have 24 samples, not 150. No BPMN models. | Expand to 50+ GDPR samples. Acquire BPMN models. | `python -c "import json; print(len(json.load(open('data/formal/r14_controlled/r14_1_candidate_samples.jsonl'))))"` |
| Preprocessing | BERT pre-training + fine-tuning for modality classification (Section 4.2.1). | `src/bpc_hybrid/sun_style/modality_classifier.py` (marker-based, no BERT). | Not aligned: uses marker-based heuristics, not BERT. | Implement BERT-based modality classifier or document divergence. | `python -c "from bpc_hybrid.sun_style.modality_classifier import ModalityClassifier; print('OK')"` |
| Rule dictionary / manual dictionary | Marker lexicon for actor, condition, constraint, exception, modality (Table 4). Extended via Wiktionary. | `src/bpc_hybrid/sun_style/marker_lexicon.py` (contains marker dictionaries). | Partially aligned: has marker lexicon, but may not be as comprehensive as Sun's. | Expand marker lexicon with more domain-specific terms. | `python -c "from bpc_hybrid.sun_style.marker_lexicon import MarkerLexicon; lex = MarkerLexicon.from_default(); print(len(lex.actor_markers), 'actor markers')"` |
| Compliance pattern extraction | Constituency parsing + dependency parsing + rule-based extraction (Section 4.2.2). Uses syntactic trees. | `src/bpc_hybrid/sun_style/syntactic_rules.py` (approximated rules, no full parser). | Partially aligned: uses heuristic rules, not full syntactic parsing. | Integrate spaCy or other parser for accurate syntactic analysis. | `python -c "from bpc_hybrid.sun_style.syntactic_rules import SyntacticRuleEngine; print('OK')"` |
| Matching logic | Matching score using text similarity with threshold τ (Definition 4). | Not implemented. | Not aligned: no matching logic between rules and process models. | Implement similarity-based matching with threshold. | N/A |
| Violation definition | Three violation types: missing action, incorrect actor, out-of-order execution (Definitions 5-7). | Not implemented. | Not aligned: no violation detection. | Implement violation detection logic. | N/A |
| Evaluation labels | Dataset B: 150 annotated sentences with phrase-level spans (Section 5.1). | `data/formal/r14_controlled/r14_1_mini_gold.jsonl` (24 gold annotations). | Partially aligned: small gold set, not 150 sentences. | Expand gold annotations to match dataset size. | `python -c "import json; print(len(json.load(open('data/formal/r14_controlled/r14_1_mini_gold.jsonl'))))"` |
| Precision calculation | Precision = TP / (TP + FP) per concept (Table 8). | `scripts/evaluate_r14_field_metrics.py` (computes precision). | Aligned: precision calculation exists. | None. | `python scripts/evaluate_r14_field_metrics.py --help` |
| Recall calculation | Recall = TP / (TP + FN) per concept (Table 8). | `scripts/evaluate_r14_field_metrics.py` (computes recall). | Aligned: recall calculation exists. | None. | `python scripts/evaluate_r14_field_metrics.py --help` |
| F1 calculation | F1 = 2 * (precision * recall) / (precision + recall) (Table 8). | `scripts/evaluate_r14_field_metrics.py` (computes F1). | Aligned: F1 calculation exists. | None. | `python scripts/evaluate_r14_field_metrics.py --help` |
| Baseline setup | Winter et al. (2020) textual baseline (Table 12). | Not implemented. | Not aligned: no Winter baseline. | Implement Winter-style baseline for comparison. | N/A |
| LLM usage, if any | Sun does not use LLMs; uses BERT for modality classification. | `src/bpc_hybrid/llm_client.py` (LLM fallback). | Divergent: we use LLM fallback, Sun does not. | Document as intentional hybrid extension. | N/A |

## Required Conclusion

The agent must conclude one of the following:

1. Fully aligned with the Sun paper.
2. Partially aligned, with documented differences.
3. Not aligned, with required fixes listed.

**Current Conclusion**: Partially aligned, with documented differences. The core semantic extraction is similar in spirit (marker-based rules), but diverges in implementation details (no BERT, no full syntactic parsing, smaller dataset). The hybrid LLM extension is an intentional addition beyond Sun's method.
