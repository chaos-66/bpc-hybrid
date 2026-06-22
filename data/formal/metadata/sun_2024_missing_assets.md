# Sun (2024) — Missing Assets for Reconstruction

**Generated**: R13.1, 2026-06-19

**Paper state**: PAPER_ONLY — PDF present, no datasets/code/annotations in workspace.

## Tables and Figures Missing (Need Author Data)

| Asset | Sun Section | Priority | Description |
|-------|------------|----------|-------------|
| Austrian Income Tax Code text | 5.1.1 | HIGH | Full text of Bundesgesetzblatt 1988/400, needed for modality classification and semantic extraction |
| Modality labels (4-class) | 5.1.1 | HIGH | Sentence-level labels: definition/obligation/prohibition/permission (0-3). 9:1 split. |
| 150 annotated sentences | 5.2 | HIGH | Phrase-level annotations: 6 concepts × span positions. 443 ground-truth components. |
| 12 BPMN models (energy supplier) | 5.3.1 | HIGH | BPMN process models for Austrian energy supplier smart meter scenarios. Expert-validated. |
| Rule base (energy supplier) | 5.3.1 | HIGH | Structured rule records parsed from smart meter regulatory documents. |
| 4 GDPR BPMN models | 5.3.2 | HIGH | Process models capturing GDPR privacy constraints. Reference [35]. |
| GDPR Articles 1–50 (processed) | 5.3.2 | MEDIUM | Article-level text with IDs. Public via EUR-Lex but needs processing. |
| bert-legal-uncased model | 5.1.2 | MEDIUM | Pre-trained on EU legislation documents. 12-layer, 768-hidden, 110M params. |
| Source code | — | LOW | Not publicly available. Full pipeline (classification→extraction→matching→checking). |
| Full original experimental dataset | all | HIGH | Complete original Sun experimental dataset including all splits, labels, and processed outputs. Not publicly released. |
| Constructed BPMN1-BPMN4 violation dataset | 5.3.2 | HIGH | The constructed violation dataset fed into Tables 10/11 (matching rules, missing actions, incorrect actors, out-of-order executions per model). Not separately downloadable. |
| Winter et al. baseline implementation | 5.4 | MEDIUM | Winter et al. (2020) baseline code and evaluation setup. Used in Table 12 comparison. Not publicly available or not located. |
| Inter-annotator agreement data | 5.2 | LOW | 10% double-annotated. Agreement statistics not reported. |
| Extended marker lists | 4.2 | LOW | Table 4 shows initial markers; paper states markers were extended. Full lists not provided. |
| Gold standard for matching | 5.3.1 | HIGH | Which model should match which rules. Needed for AP/MAP computation. |

## Figures Not Reproducible Without Data

| Figure | Description | Data Needed |
|--------|-------------|-------------|
| Fig 1 | BPC lifecycle overview | None (conceptual) |
| Fig 2 | Method overview framework | None (conceptual) |
| Fig 3 | Constituent parse tree example | Sample text |
| Fig 4 | Dependency tree example | Sample text |
| Fig 5 | Classification model construction | None (architecture diagram) |
| Fig 6 | Semantic extraction examples | Annotated sentences |
| Fig 7 | BPMN process model examples | BPMN models |
| Fig 8 | Precision vs γ threshold | Violation detection results |
| Fig 9 | Case study: phone company process model | BPMN model |
| Fig 10 | Visual violation representation | Process model + rule matches |

## Re-Creation Strategy (If Author Data Unavailable)

### Doable with Public Resources
1. **Austrian Income Tax Code text**: Download from https://ris.bka.gv.at/eli/bgbl/1988/400/P0/NOR40205159
2. **GDPR Articles 1–50**: Download from EUR-Lex (https://eur-lex.europa.eu/eli/reg/2016/679/oj)
3. **Phrase-level annotation**: Independently re-annotate subset of sentences using Sun's 6-concept taxonomy
4. **GDPR BPMN models**: Model GDPR privacy process flows from Article text

### Not Doable Without Author Cooperation
1. **Original 12 BPMN models**: Domain-expert-validated; not publicly released
2. **Original gold labels**: Exact train/test split and annotations unknown
3. **Exact rule base**: Not described in sufficient detail to replicate
4. **Source code**: Not publicly available

## Recommended Action
1. Email corresponding author (yudj@hdu.edu.cn) requesting datasets
2. If no response in 4 weeks, proceed with independent re-creation
3. Document all re-creation decisions in `data/formal/metadata/changelog.json`
