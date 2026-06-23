"""R15.1 Sun-style Rule-only on GDPR-50 dataset.

Runs Sun-style semantic extraction on the 50-sample GDPR dataset.
Outputs predictions for evaluation.

Usage:
    python scripts/run_r15_gdpr50_sun_style.py
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

from bpc_hybrid.sun_style.semantic_extractor import SemanticExtractor

# Paths
_CANDIDATE_PATH = (
    _PROJECT_ROOT / "data" / "formal" / "r15_gdpr50"
    / "r15_gdpr50_candidate_samples.jsonl"
)
_GOLD_PATH = (
    _PROJECT_ROOT / "data" / "formal" / "r15_gdpr50"
    / "r15_gdpr50_gold.jsonl"
)
_PREDICTIONS_OUT = (
    _PROJECT_ROOT / "data" / "formal" / "predictions"
    / "r15_gdpr50_sun_style_predictions.jsonl"
)
_MANIFEST_OUT = (
    _PROJECT_ROOT / "data" / "formal" / "metadata"
    / "r15_gdpr50_sun_style_manifest.json"
)


def main() -> None:
    print("=== R15.1 Sun-style Rule-only on GDPR-50 ===")
    print(f"Input:  {_CANDIDATE_PATH}")
    print(f"Gold:   {_GOLD_PATH}")
    print(f"Output: {_PREDICTIONS_OUT}")
    print(f"Manifest: {_MANIFEST_OUT}")
    print()

    # Load samples
    samples: list[dict] = []
    with _CANDIDATE_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    print(f"Loaded {len(samples)} candidate samples")

    # Initialize extractor
    extractor = SemanticExtractor()

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
        "stage": "R15.1",
        "method": "sun_style_rule_only_gdpr50",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_path": str(_CANDIDATE_PATH),
        "gold_path": str(_GOLD_PATH),
        "output_path": str(_PREDICTIONS_OUT),
        "sample_count": len(samples),
        "real_api": False,
        "llm_used": False,
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

    print("\nDone.")


if __name__ == "__main__":
    main()
