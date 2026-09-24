# Stage 3 R1 temporal scope source candidates

These three natural-after sources are **candidate_not_benchmark**. They were not added to the 50-cell current benchmark, were not extracted, and were not used for API/F1.

| Provision | Source | Natural relation | Status | Current-scope difference |
|---|---|---|---|---|
| Article14(3)(a) | `references/winter_2020_model_check/model_check/input/regulations/gdpr/article14.txt` | trigger_event -> obligation_event (natural after reading) | `candidate_not_benchmark` | Not among the five current v4 rules; current BPMN cases do not encode a separate obtained event and the current source set is before/prior-to only. |
| Article33(2) | `references/winter_2020_model_check/model_check/input/regulations/gdpr/article33.txt` | trigger_event -> obligation_event (natural after reading) | `candidate_not_benchmark` | Not among the five current v4 rules; requires a new processor-awareness/notification BPMN family. |
| Article43(1) | `references/winter_2020_model_check/model_check/input/regulations/gdpr/article43.txt` | trigger_event -> obligation_event (natural after reading) | `candidate_not_benchmark` | Not among the five current v4 rules; requires a new certification-body process family. |

## Evidence anchors

### Article14(3)(a)
- source: `references/winter_2020_model_check/model_check/input/regulations/gdpr/article14.txt`; span `[2469, 2731]`; sha256 `bf9cb5977a41103664d4bce95f889ac6c5decc316f63af95826591e4134b4764`
- sentence: The controller shall provide the information referred to in paragraphs 1 and 2 within a reasonable period after obtaining the personal data, but at the latest within one month, having regard to the specific circumstances in which the personal data are processed.
- marker: `after` at excerpt offsets `[106, 111]`
- earlier trigger: obtaining the personal data (`controller`)
- later obligation: provide the information referred to in paragraphs 1 and 2 (`controller`)
- exceptions/boundary: Article 14(5)(a)-(c) exceptions would need separate applicability handling.

### Article33(2)
- source: `references/winter_2020_model_check/model_check/input/regulations/gdpr/article33.txt`; span `[503, 612]`; sha256 `cdafa0c9267f2078a7fc65bf8093c7f6a7f5717ae244b55f5088fff98daaa7f2`
- sentence: The processor shall notify the controller without undue delay after becoming aware of a personal data breach.
- marker: `after` at excerpt offsets `[62, 67]`
- earlier trigger: becoming aware of a personal data breach (`processor`)
- later obligation: notify the controller (`processor`)
- exceptions/boundary: No explicit exception in Article 33(2); paragraph 1 72-hour context and Article 34 boundary remain.

### Article43(1)
- source: `references/winter_2020_model_check/model_check/input/regulations/gdpr/article43.txt`; span `[0, 869]`; sha256 `1ba03f81f60dbffa140d48108de13bc4ac7b2bdc9c7aa9fdd97364324e4c8fd7`
- sentence: Without prejudice to the tasks and powers of the competent supervisory authority under Articles 57 and 58, certification bodies which have an appropriate level of expertise in relation to data protection shall, after informing the supervisory authority in order to allow it to exercise its powers pursuant to point (h) of Article 58(2) where necessary, issue and renew certification. Member States shall ensure that those certification bodies are accredited by one or both of the following:
the supervisory authority which is competent pursuant to Article 55 or 56.
the national accreditation body named in accordance with Regulation (EC) No 765/2008 of the European Parliament and of the Council (20) in accordance with EN-ISO/IEC 17065/2012 and with the additional requirements established by the supervisory authority which is competent pursuant to Article 55 or 56.
- marker: `after` at excerpt offsets `[211, 216]`
- earlier trigger: informing the supervisory authority in order to allow it to exercise its powers pursuant to point (h) of Article 58(2) where necessary (`certification body`)
- later obligation: issue and renew certification (`certification body`)
- exceptions/boundary: The Without prejudice clause and where necessary condition are part of the source; later paragraphs impose accreditation conditions.

No candidate was added to the current benchmark. No API call or model output was used in this inventory.
