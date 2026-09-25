# Stage 3 temporal-scope candidate corrections R2

These are `candidate_not_benchmark` source records only; they are not in the 50-unit evaluation and no extraction or API was run.

## Article14(3)(a)

- source: `references/winter_2020_model_check/model_check/input/regulations/gdpr/article14.txt` span=[2469, 2731] sha256=bf9cb5977a41103664d4bce95f889ac6c5decc316f63af95826591e4134b4764
- exact excerpt: The controller shall provide the information referred to in paragraphs 1 and 2 within a reasonable period after obtaining the personal data, but at the latest within one month, having regard to the specific circumstances in which the personal data are processed.
- limits: {'conditions': ['personal data not obtained from the data subject', 'information referred to in paragraphs 1 and 2'], 'time_limits': ['within a reasonable period after obtaining the personal data', 'at the latest within one month', 'having regard to the specific circumstances'], 'exceptions': ['Article 14(5)(a)-(c) limits paragraphs 1-4, including (3)(a); this is an external applicability boundary.'], 'exception_boundary_preserved': True}

## Article33(2)

- source: `references/winter_2020_model_check/model_check/input/regulations/gdpr/article33.txt` span=[503, 612] sha256=cdafa0c9267f2078a7fc65bf8093c7f6a7f5717ae244b55f5088fff98daaa7f2
- exact excerpt: The processor shall notify the controller without undue delay after becoming aware of a personal data breach.
- limits: {'conditions': ['processor has become aware of a personal data breach'], 'time_limits': ['without undue delay'], 'exceptions': ['No explicit exception in Article 33(2); paragraph 1 72-hour context and Article 34 boundary remain separate.'], 'limitation_preserved': True}

## Article43(1) first sentence

- source: `references/winter_2020_model_check/model_check/input/regulations/gdpr/article43.txt` span=[0, 383] sha256=367392f6e377363ce4164c015f075d716c2a1e23e71386161eeba4042f535e30
- exact excerpt: Without prejudice to the tasks and powers of the competent supervisory authority under Articles 57 and 58, certification bodies which have an appropriate level of expertise in relation to data protection shall, after informing the supervisory authority in order to allow it to exercise its powers pursuant to point (h) of Article 58(2) where necessary, issue and renew certification.
- limits: {'conditions': ['after informing the supervisory authority where necessary'], 'time_limits': [], 'exceptions': ['Without prejudice to Articles 57 and 58 competences; later paragraphs impose accreditation requirements.']}
