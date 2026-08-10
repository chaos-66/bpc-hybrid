# Formal Benchmark Release v2

- release status: input_v2_and_gold_published_and_verified
- executable input ready: True
- gold unchanged: True (Stage 2 / Stage 3 Gold byte-identical to v1 publication)
- formal predictions/results capsule: NOT produced
- final experiment ready: False

## v1 input limitation
- `data/input/estg150_formal_input_v1.json` is **membership-only; not sufficient as executable model input** (150 sample IDs + membership payload only).
- Preserved byte-identical; sidecar marker: `data/input/estg150_formal_input_v1.STATUS.md`.

## v2 executable Gold-blind input
- `data/input/estg150_formal_inference_input_v2.json` sha256=52a73aa1109970b6... (150 records)
- fields: sample_id, approved_text_en, raw_text_de, language, source_ref, input_text_sha256, provenance
- NO adjudication content: no Gold spans/labels, no decisions, no LLM drafts, no relation/order Gold, no review evidence

## Artifacts
- `data/input/estg150_formal_input_v1.json` sha256=95f66c3497cbdc6a... (150 records)
- `data/input/estg150_formal_input_v1.STATUS.md` sha256=7d0b087e3b70b176... (0 records)
- `data/input/estg150_formal_inference_input_v2.json` sha256=52a73aa1109970b6... (150 records)
- `data/gold/stage2/estg150_formal_gold_v1.json` sha256=c31a514a6b58b640... (150 records)
- `data/gold/stage3/stage3_matching_gold_v1.json` sha256=55dffbcaf7d6510c... (25 records)
- `data/gold/stage3/stage3_violation_gold_v1.json` sha256=54245ef0d102ae5e... (33 records)

## States
- Gold capsule published/verified: True
- Executable formal input ready: True
- Formal predictions/results capsule: NOT produced
- Final experiment ready: False

## Exclusions (unchanged)
- Modality dataset: NOT published (license unknown, redistribution forbidden)
- Gold Rule Records: DO NOT EXIST (blocked on human adjudication + freeze)
- Gold Process Records: DO NOT EXIST (blocked on S1.7)
