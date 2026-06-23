"""R15.0 Sun-style Rule-only Runner.

Reads R14.1 candidate samples and runs Sun-style semantic extraction
on each. Outputs Sun-style predictions and a manifest.

Usage::

    $env:BPC_HYBRID_DISABLE_PROJECT_ENV = "1"
    .venv/Scripts/python.exe scripts/run_r15_sun_style_rule_only.py

No LLM, no API, no external downloads.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure src/ is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.sun_style.semantic_extractor import SemanticExtractor

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_CANDIDATE_PATH = (
    _PROJECT_ROOT / "data" / "formal" / "r14_controlled"
    / "r14_1_candidate_samples.jsonl"
)
_PREDICTIONS_OUT = (
    _PROJECT_ROOT / "data" / "formal" / "predictions"
    / "r15_0_sun_style_rule_only_predictions.jsonl"
)
_MANIFEST_OUT = (
    _PROJECT_ROOT / "data" / "formal" / "metadata"
    / "r15_0_sun_style_rule_only_manifest.json"
)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== R15.0 Sun-style Rule-only Extraction ===")
    print(f"Input:  {_CANDIDATE_PATH}")
    print(f"Output: {_PREDICTIONS_OUT}")
    print(f"Manifest: {_MANIFEST_OUT}")
    print()

    # Load candidate samples
    samples: list[dict] = []
    with _CANDIDATE_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    print(f"Loaded {len(samples)} candidate samples")
    print()

    # Initialize extractor
    extractor = SemanticExtractor()

    # Extract
    results = []
    for i, sample in enumerate(samples):
        sid = sample["sample_id"]
        text = sample["text"]
        extraction = extractor.extract(sid, text)
        results.append(extraction)
        if (i + 1) % 8 == 0:
            print(f"  Processed {i + 1}/{len(samples)}...")

    print(f"  Processed {len(samples)}/{len(samples)}")
    print()

    # Write predictions JSONL
    _PREDICTIONS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with _PREDICTIONS_OUT.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
    print(f"Predictions written: {_PREDICTIONS_OUT}")

    # Write manifest
    manifest = {
        "stage": "R15.0",
        "method": "sun_style_rule_template",
        "sample_count": len(samples),
        "source": "r14_1_candidate_samples",
        "real_api_call_performed": False,
        "llm_call_performed": False,
        "external_download_performed": False,
        "bert_status": extractor.bert_status,
        "parser_status": extractor.parser_status,
        "sun_original_dataset_available": False,
        "exact_sun_reproduction": False,
        "claim_boundary": (
            "R15.0 improves method alignment with Sun et al. but does not "
            "constitute exact Sun reproduction because the original datasets, "
            "original trained BERT model, original full marker lexicon, and "
            "original BPMN evaluation data are not available."
        ),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    _MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST_OUT.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Manifest written: {_MANIFEST_OUT}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
