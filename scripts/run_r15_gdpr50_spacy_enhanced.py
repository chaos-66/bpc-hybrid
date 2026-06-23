"""R15.2 spaCy-enhanced Sun-style extraction on GDPR-50.

Uses spaCy dependency parsing for more accurate syntactic analysis.
Runs on the 50-sample GDPR dataset.

Usage:
    python scripts/run_r15_gdpr50_spacy_enhanced.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.sun_style.spacy_semantic_extractor import SpacySemanticExtractor

# Paths
_CANDIDATE_PATH = (
    _PROJECT_ROOT / "data" / "formal" / "r15_gdpr50"
    / "r15_gdpr50_candidate_samples.jsonl"
)
_PREDICTIONS_OUT = (
    _PROJECT_ROOT / "data" / "formal" / "predictions"
    / "r15_gdpr50_spacy_enhanced_predictions.jsonl"
)
_MANIFEST_OUT = (
    _PROJECT_ROOT / "data" / "formal" / "metadata"
    / "r15_gdpr50_spacy_enhanced_manifest.json"
)


def main() -> None:
    print("=== R15.2 spaCy-enhanced Sun-style on GDPR-50 ===")
    print(f"Input:  {_CANDIDATE_PATH}")
    print(f"Output: {_PREDICTIONS_OUT}")
    print()

    # Load samples
    samples: list[dict] = []
    with _CANDIDATE_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    print(f"Loaded {len(samples)} candidate samples")

    # Initialize spaCy-enhanced extractor
    print("Loading spaCy model and initializing extractor...")
    extractor = SpacySemanticExtractor()

    # Extract
    results = []
    for i, sample in enumerate(samples):
        sid = sample["sample_id"]
        text = sample["text"]
        extraction = extractor.extract(sid, text)
        results.append(extraction)
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(samples)}...")

    print(f"  Processed {len(samples)}/{len(samples)}")

    # Write predictions
    _PREDICTIONS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with _PREDICTIONS_OUT.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
    print(f"\nPredictions written: {_PREDICTIONS_OUT}")

    # Write manifest
    manifest = {
        "stage": "R15.2",
        "method": "spacy_enhanced_sun_style_gdpr50",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_path": str(_CANDIDATE_PATH),
        "output_path": str(_PREDICTIONS_OUT),
        "sample_count": len(samples),
        "real_api": False,
        "llm_used": False,
        "spacy_model": "en_core_web_sm",
    }
    _MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST_OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest written: {_MANIFEST_OUT}")

    # Quick summary
    modality_dist = {}
    for r in results:
        m = r.modality or "none"
        modality_dist[m] = modality_dist.get(m, 0) + 1
    print("\n  Predicted modality distribution:")
    for m, count in sorted(modality_dist.items()):
        print(f"    {m}: {count}")

    # Count non-empty fields
    field_counts = {"actor": 0, "action": 0, "condition": 0, "constraint": 0, "exception": 0}
    for r in results:
        if r.actor:
            field_counts["actor"] += 1
        if r.action:
            field_counts["action"] += 1
        if r.condition:
            field_counts["condition"] += 1
        if r.constraint:
            field_counts["constraint"] += 1
        if r.exception:
            field_counts["exception"] += 1
    print("\n  Non-empty field counts:")
    for field_name, count in field_counts.items():
        print(f"    {field_name}: {count}/{len(results)}")

    print("\nDone.")


if __name__ == "__main__":
    main()
