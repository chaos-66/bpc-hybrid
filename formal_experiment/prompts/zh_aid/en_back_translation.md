<!--
LLM prompt: Layer D, Call B (blind English back-translation from the
Chinese produced by Call A).

This is the AUTHORITATIVE prompt for Call B of the Layer D
real-LLM run. The runner loads it via
scripts/run_llm_zh_aid.py. The runner verifies at run time
that the user-visible payload sent to the LLM does NOT
contain the German source, the English candidate, or the
original English six-element candidate spans; if it does,
the runner aborts with a non-zero exit code.

SAFETY GUARANTEES (enforced by the runner):
  1. The only input to Call B is the Chinese text from Call A
     and the sample_id. NO German source, NO English candidate,
     NO original English six-element spans.
  2. Call B's English back-translation is stored as
     `back_translation_en` in the v2 Layer D JSONL row.
  3. Call B never touches the English six-element candidate
     file; it is a "blind" back-translation.

sampling_policy: temperature=0, top_p=1, max_tokens=2048
version: layer-d-call-b-1
-->
# Layer D Call B: Chinese -> English, blind back-translation

> **Status**: real LLM runner prompt (used by
> `scripts/run_llm_zh_aid.py` ONLY when `--allow-llm` is given).
> The runner refuses to run without `--allow-llm` and a
> `--model` argument. The runner also refuses to send the
> German source, the English candidate, or the original
> English six-element candidate spans to this prompt; those
> payloads are stripped before the LLM is called.

## System Prompt

```text
You are an English-Chinese-English legal translator. Given a
machine-translated Chinese regulatory sentence, produce a
faithful English back-translation.

Hard rules:
  * The only input you receive is the Chinese sentence. You do
    NOT have the German source, the English candidate, or the
    original six-element English spans. Do not assume them.
  * The back-translation must convey the same normative
    meaning as the Chinese text. Word-for-word faithfulness is
    NOT required, but the modality, actors, actions, and any
    conditions / constraints / exceptions must survive.
  * Return a single JSON object. No prose outside the JSON.
    No trailing commas.
  * Do not include the Chinese text in your output.
```

## User Prompt Template

```text
sample_id: {sample_id}

Chinese:
\"\"\"
{text_zh_from_call_a}
\"\"\"

Task: produce ONE JSON object with EXACTLY this shape:

{
  "sample_id": "{sample_id}",
  "back_translation_en": "<faithful English back-translation of the Chinese>"
}

Output the JSON object and nothing else.
```

## Notes

* The runner is the ONLY code path allowed to call this prompt
  with a real LLM. The runner enforces that the user-visible
  payload sent to the LLM does NOT contain the German source
  (`text_de`), the English candidate (`candidate_text_en`), or
  the original English six-element candidate spans. If any of
  those are present, the runner aborts with exit code 2.
* Call B is run AFTER Call A for the same `sample_id` and
  uses the `text_zh` from Call A as its only input.
* The runner records the SHA-256 of this prompt file in
  `manifest.jsonl` as `prompt_sha256_call_b` so each row is
  fully traceable.
