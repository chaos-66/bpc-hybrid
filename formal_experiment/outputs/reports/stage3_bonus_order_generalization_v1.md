# Stage 3 BONUS Development: Order Generalization v1

- Status: `BONUS_DEV_ONLY_ORDER_GENERALIZATION_DIAGNOSTIC`
- `DEV_ONLY = true`; `FINAL_TABLE3_ELIGIBLE = false`
- `REAL_LLM_API_CALLS = 0`
- Endpoint policy: dev-only synthetic endpoint stub, not a real Stage-2 prediction.
- Adapter: `SharedRuleOrderAdapterV3` (unchanged).
- Frozen backend and thresholds: MPNet / gamma `0.55` / theta `0.45` / tau `0.8`.

## Per-Requirement Diagnostic

| Requirement | Citation | Eligibility | Sun endpoint | Ours endpoint | Sun U_r | Ours U_r | Baseline order | Mutant order | Failure |
|---|---|---|---|---|---|---|---|---|---|
| BONUS-ORD-01 | GDPR Article 7(4) | STRICT_ELIGIBLE | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | [['informed', 'giving consent']] | [['informed', 'giving consent']] | satisfied | violated |  |
| BONUS-ORD-02 | GDPR Article 35(3) | STRICT_ELIGIBLE | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | [['apply the consistency mechanism referred to in Article 63', 'adoption of the lists referred to in paragraphs 4 and 5']] | [['apply the consistency mechanism referred to in Article 63', 'adoption of the lists referred to in paragraphs 4 and 5']] | satisfied | violated |  |
| BONUS-ORD-03 | GDPR Article 40(7) | STRICT_ELIGIBLE_ADAPTER_FAILURE | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | [] | [] | unknown | unknown | OERR_TEMPORAL_MARKER_UNRESOLVED |
| BONUS-ORD-04 | GDPR Article 43(1) | STRICT_ELIGIBLE | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | [] | [] | unknown | unknown | OERR_TEMPORAL_MARKER_UNRESOLVED |
| BONUS-ORD-05 | GDPR Article 49(1)(a) | STRICT_ELIGIBLE_ADAPTER_FAILURE | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | [] | [] | unknown | unknown | OERR_TEMPORAL_MARKER_UNRESOLVED |
| BONUS-ORD-06 | GDPR Article 45(1) | STRICT_ELIGIBLE | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | [['assessing the adequacy of the level of protection', 'decide']] | [['assessing the adequacy of the level of protection', 'decide']] | satisfied | violated |  |
| BONUS-ORD-07 | GDPR Article 6(1)(b) | DIAGNOSTIC_BORDERLINE_NOT_OBLIGATION | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | [['take steps at the request of the data subject', 'entering into a contract']] | [['take steps at the request of the data subject', 'entering into a contract']] | satisfied | violated |  |
| BONUS-ORD-08 | GDPR Article 18(3) | DIAGNOSTIC_BORDERLINE_PASSIVE_STATE_ENDPOINT | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | [] | [] | unknown | unknown | OERR_SEMANTIC_ENDPOINT_BINDING_FAIL |
| BONUS-ORD-09 | GDPR Article 36(2) | DIAGNOSTIC_BORDERLINE_NOMINAL_ENDPOINT | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_REAL_STAGE2_PREDICTION | [['consult the supervisory authority', 'processing']] | [['consult the supervisory authority', 'processing']] | satisfied | violated |  |

## Source and Action Boundaries

| Requirement | Source text | Before action | After action |
|---|---|---|---|
| BONUS-ORD-01 | Prior to giving consent, the data subject shall be informed thereof. | informed | giving consent |
| BONUS-ORD-02 | Prior to the adoption of the lists referred to in paragraphs 4 and 5, the competent supervisory authority shall apply the consistency mechanism referred to in Article 63 where such lists involve processing activities which are related to the offering of goods or services to data subjects or to the monitoring of their behaviour in several Member States, or may substantially affect the free movement of personal data within the Union. | apply the consistency mechanism referred to in Article 63 | adoption of the lists referred to in paragraphs 4 and 5 |
| BONUS-ORD-03 | Where a draft code of conduct relates to processing activities in several Member States, the supervisory authority which is competent pursuant to Article 55 shall, before approving the draft code, amendment or extension, submit it in the procedure referred to in Article 63 to the Board which shall provide an opinion on whether the draft code, amendment or extension complies with this Regulation or, in the situation referred to in paragraph 3 of this Article, provides appropriate safeguards. | submit it in the procedure referred to in Article 63 to the Board | approving the draft code, amendment or extension |
| BONUS-ORD-04 | Without prejudice to the tasks and powers of the competent supervisory authority under Articles 57 and 58, certification bodies which have an appropriate level of expertise in relation to data protection shall, after informing the supervisory authority in order to allow it to exercise its powers pursuant to point (h) of Article 58(2) where necessary, issue and renew certification. | informing the supervisory authority | issue and renew certification |
| BONUS-ORD-05 | In the absence of an adequacy decision pursuant to Article 45(3), or of appropriate safeguards pursuant to Article 46, including binding corporate rules, a transfer or a set of transfers of personal data to a third country or an international organisation shall take place only if the data subject has explicitly consented to the proposed transfer, after having been informed of the possible risks of such transfers for the data subject due to the absence of an adequacy decision and appropriate safeguards. | informed of the possible risks | consented to the proposed transfer |
| BONUS-ORD-06 | The Commission, after assessing the adequacy of the level of protection, may decide, by means of implementing act, that a third country, a territory or one or more specified sectors within a third country, or an international organisation ensures an adequate level of protection within the meaning of paragraph 2 of this Article. | assessing the adequacy of the level of protection | decide |
| BONUS-ORD-07 | Processing shall be lawful only if and to the extent that processing is necessary for the performance of a contract to which the data subject is party or in order to take steps at the request of the data subject prior to entering into a contract; | take steps at the request of the data subject | entering into a contract |
| BONUS-ORD-08 | A data subject who has obtained restriction of processing pursuant to paragraph 1 shall be informed by the controller before the restriction of processing is lifted. | informed by the controller | lifted |
| BONUS-ORD-09 | The controller shall consult the supervisory authority prior to processing where a data protection impact assessment under Article 35 indicates that the processing would result in a high risk in the absence of measures taken by the controller to mitigate the risk. | consult the supervisory authority | processing |

## Complete Order Metrics

| Method | Eligible requirements | Generated U_r | Missing U_r | Observable cells | Unknown cells | TP | FP | FN | TN | Precision | Recall | F1 | Coverage | Unknown rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Sun | 12 | 8 | 4 | 12 | 14 | 6 | 0 | 6 | 6 | 1.0000 | 0.5000 | 0.6667 | 0.4615 | 0.5385 |
| Ours | 12 | 6 | 6 | 12 | 14 | 6 | 0 | 6 | 6 | 1.0000 | 0.5000 | 0.6667 | 0.4615 | 0.5385 |

## Failure Taxonomy Counts

| Failure category | Count |
|---|---:|
| NO_FAILURE | 5 |
| OERR_SEMANTIC_ENDPOINT_BINDING_FAIL | 1 |
| OERR_TEMPORAL_MARKER_UNRESOLVED | 3 |

## Interpretation

- Five of nine bonus requirements produced a unique adapter edge and a correct baseline/mutant order signal.
- Four requirements failed at projection or endpoint binding; they are retained as negative evidence, not repaired with sample-specific rules.
- The supplement is a diagnostic only and cannot replace the paper-facing Table 3.
