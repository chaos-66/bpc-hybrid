"""R15.3 Rule + LLM Fallback extraction on GDPR-50.

Hybrid approach:
  1. Run spaCy-enhanced Sun-style extraction first
  2. For samples with missing fields, call LLM to fill gaps
  3. Merge results

Usage:
    python scripts/run_r15_gdpr50_rule_plus_llm.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.llm_config import LLMConfig
from bpc_hybrid.llm_client import (
    LLMClientError,
    LLMRequest,
    LLMResponse,
    RealAPITransport,
)
from bpc_hybrid.sun_style.spacy_semantic_extractor import SpacySemanticExtractor
from bpc_hybrid.sun_style.semantic_extractor import SemanticExtraction

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_CANDIDATE_PATH = (
    _PROJECT_ROOT / "data" / "formal" / "r15_gdpr50"
    / "r15_gdpr50_candidate_samples.jsonl"
)
_PREDICTIONS_OUT = (
    _PROJECT_ROOT / "data" / "formal" / "predictions"
    / "r15_gdpr50_rule_plus_llm_predictions.jsonl"
)
_MANIFEST_OUT = (
    _PROJECT_ROOT / "data" / "formal" / "metadata"
    / "r15_gdpr50_rule_plus_llm_manifest.json"
)

# LLM prompt for filling missing fields
SYSTEM_PROMPT = """You are a legal text analyst specializing in GDPR compliance.
Your task is to extract structured semantic information from regulatory sentences.

For each sentence, extract these 6 fields:
1. modality: one of "obligation", "prohibition", "permission", "definition"
2. actor: the role/entity responsible (e.g., "controller", "processor", "data subject")
3. action: what is mandatory/prohibited/permitted
4. condition: when the rule applies (null if none)
5. constraint: restrictions on applicability (null if none)
6. exception: when the provision does not apply (null if none)

Respond ONLY with valid JSON in this exact format:
{
  "modality": "obligation",
  "actor": "controller",
  "action": "notify the supervisory authority",
  "condition": "In the case of a personal data breach",
  "constraint": "without undue delay and, where feasible, not later than 72 hours",
  "exception": null
}"""


def build_user_prompt(text: str, missing_fields: list[str]) -> str:
    """Build the user prompt for LLM fallback."""
    fields_str = ", ".join(missing_fields)
    return (
        f"Extract the following missing fields from this GDPR sentence: {fields_str}\n\n"
        f"Sentence: {text}\n\n"
        f"Respond with JSON only."
    )


def parse_llm_response(content: str) -> dict | None:
    """Parse LLM response JSON."""
    try:
        # Try to extract JSON from the response
        content = content.strip()
        if content.startswith("```"):
            # Remove markdown code blocks
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])
        return json.loads(content)
    except (json.JSONDecodeError, IndexError):
        return None


def merge_results(
    rule_result: SemanticExtraction,
    llm_fields: dict | None,
    missing_fields: list[str],
) -> dict:
    """Merge rule-based and LLM results."""
    # Start with rule-based result
    merged = {
        "modality": rule_result.modality,
        "actor": rule_result.actor,
        "action": rule_result.action,
        "condition": rule_result.condition,
        "constraint": rule_result.constraint,
        "exception": rule_result.exception,
    }

    # Fill missing fields from LLM
    if llm_fields:
        for field in missing_fields:
            if field in llm_fields and llm_fields[field] is not None:
                merged[field] = llm_fields[field]

    return merged


def main() -> None:
    print("=== R15.3 Rule + LLM Fallback on GDPR-50 ===", flush=True)
    print(f"Input:  {_CANDIDATE_PATH}", flush=True)
    print(f"Output: {_PREDICTIONS_OUT}", flush=True)
    print(flush=True)

    # Load samples
    samples: list[dict] = []
    with _CANDIDATE_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    print(f"Loaded {len(samples)} candidate samples", flush=True)

    # Initialize spaCy-enhanced extractor
    print("Loading spaCy model and initializing extractor...", flush=True)
    rule_extractor = SpacySemanticExtractor()

    # Initialize LLM transport
    print("Initializing LLM transport...", flush=True)
    config = LLMConfig.from_env(project_root=_PROJECT_ROOT)
    if not config.enabled or config.provider == "mock":
        print("WARNING: LLM not enabled or provider is mock. Falling back to rule-only mode.")
        llm_transport = None
    else:
        llm_transport = RealAPITransport(config, timeout_seconds=60.0)
        print(f"  LLM provider: {config.provider}", flush=True)
        print(f"  LLM model: {config.model}", flush=True)

    # Process samples
    results = []
    llm_calls = 0
    llm_errors = 0
    start_time = time.time()

    for i, sample in enumerate(samples):
        sid = sample["sample_id"]
        text = sample["text"]

        # Step 1: Rule-based extraction
        rule_result = rule_extractor.extract(sid, text)

        # Step 2: Check for missing fields
        missing_fields = []
        for field_name in ["modality", "actor", "action", "condition", "constraint", "exception"]:
            value = getattr(rule_result, field_name, None)
            if value is None or value == "":
                missing_fields.append(field_name)

        # Step 3: LLM fallback if needed
        llm_fields = None
        if missing_fields and llm_transport:
            try:
                print(f"  [{i+1}/{len(samples)}] {sid}: LLM filling {missing_fields}...", flush=True)
                user_prompt = build_user_prompt(text, missing_fields)
                request = LLMRequest(
                    source_id=sid,
                    source_text=text,
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                )
                response = llm_transport.send(request)
                llm_fields = parse_llm_response(response.content)
                llm_calls += 1
                print(f"  [{i+1}/{len(samples)}] {sid}: LLM OK -> {llm_fields}", flush=True)

                # Rate limiting: wait between calls
                if llm_calls < len(samples):
                    time.sleep(0.5)

            except (LLMClientError, Exception) as e:
                llm_errors += 1
                print(f"  LLM error for {sid}: {type(e).__name__}: {str(e)[:100]}", flush=True)

        # Step 4: Merge results
        merged = merge_results(rule_result, llm_fields, missing_fields)

        # Build output record
        record = {
            "sample_id": sid,
            "source_text": text,
            "method": "rule_plus_llm_fallback",
            "sun_alignment": {
                "bert_modality": rule_result.sun_alignment.bert_modality,
                "syntactic_tree_rules": "spacy_dependency_parsing",
                "domain_marker_lexicon": True,
                "rule_template_extraction": True,
            },
            "prediction_fields": {
                "modality": {"value": merged["modality"] or ""},
                "actor": {"value": merged["actor"] or ""},
                "action": {"value": merged["action"] or ""},
                "condition": {"value": merged["condition"] or ""},
                "constraint": {"value": merged["constraint"] or ""},
                "exception": {"value": merged["exception"] or ""},
            },
            "llm_fallback_used": len(missing_fields) > 0 and llm_transport is not None,
            "missing_fields": missing_fields,
            "llm_fields_filled": list(llm_fields.keys()) if llm_fields else [],
        }
        results.append(record)

        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            print(f"  Processed {i + 1}/{len(samples)}... ({llm_calls} LLM calls, {elapsed:.1f}s)", flush=True)

    elapsed = time.time() - start_time
    print(f"  Processed {len(samples)}/{len(samples)} in {elapsed:.1f}s", flush=True)
    print(f"  LLM calls: {llm_calls}, LLM errors: {llm_errors}", flush=True)

    # Write predictions
    _PREDICTIONS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with _PREDICTIONS_OUT.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nPredictions written: {_PREDICTIONS_OUT}", flush=True)

    # Write manifest
    manifest = {
        "stage": "R15.3",
        "method": "rule_plus_llm_fallback_gdpr50",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_path": str(_CANDIDATE_PATH),
        "output_path": str(_PREDICTIONS_OUT),
        "sample_count": len(samples),
        "llm_calls": llm_calls,
        "llm_errors": llm_errors,
        "elapsed_seconds": elapsed,
        "real_api": True,
        "llm_used": llm_calls > 0,
        "llm_provider": config.provider if llm_transport else "none",
        "llm_model": config.model if llm_transport else "none",
    }
    _MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST_OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest written: {_MANIFEST_OUT}", flush=True)

    # Quick summary
    modality_dist = {}
    for r in results:
        m = r["prediction_fields"]["modality"]["value"] or "none"
        modality_dist[m] = modality_dist.get(m, 0) + 1
    print("\n  Predicted modality distribution:", flush=True)
    for m, count in sorted(modality_dist.items()):
        print(f"    {m}: {count}", flush=True)

    # Count non-empty fields
    field_counts = {"actor": 0, "action": 0, "condition": 0, "constraint": 0, "exception": 0}
    for r in results:
        for field_name in field_counts:
            if r["prediction_fields"][field_name]["value"]:
                field_counts[field_name] += 1
    print("\n  Non-empty field counts:", flush=True)
    for field_name, count in field_counts.items():
        print(f"    {field_name}: {count}/{len(results)}", flush=True)

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
