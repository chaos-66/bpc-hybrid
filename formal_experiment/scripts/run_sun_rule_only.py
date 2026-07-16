"""Sun rule-only development candidate (Wave 1.1 §7 clarification).

This is a **development heuristic candidate**, not a paper-faithful
Sun Stage 2 reconstruction. The current ``SemanticExtractor`` uses
keyword + spaCy heuristics; it does **not** contain the BERT-TextCNN
modality classifier nor the Stanford CoreNLP / Tregex / Tsurgeon
phrase extractor that Sun et al. (2024) describe. The formal
baseline must be rebuilt before this runner can be reported as a
paper-faithful reconstruction. See
``docs/B0_RECONSTRUCTION_DESIGN.md`` for the planned design.

Usage:
    python scripts/run_sun_rule_only.py --help
"""

from __future__ import annotations

import argparse
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
_DEFAULT_INPUT = _PROJECT_ROOT / "data" / "input" / "estg150_input_v1.jsonl"
_DEFAULT_OUTPUT = (
    _PROJECT_ROOT / "data" / "predictions" / "sun_rule_only_predictions.jsonl"
)
_DEFAULT_MANIFEST = (
    _PROJECT_ROOT / "data" / "predictions" / "sun_rule_only_manifest.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=_DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly allow replacing existing output and manifest files",
    )
    args = parser.parse_args()

    for path in (args.output, args.manifest):
        if path.exists() and not args.overwrite:
            print(f"Refusing to overwrite existing artifact: {path}")
            return 2

    print("=== Sun 2024 paper-faithful rule-only reconstruction ===")
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    print(f"Manifest: {args.manifest}")
    print()

    # Load samples
    samples: list[dict] = []
    with args.input.open("r", encoding="utf-8") as fh:
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
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
    print(f"\nPredictions written: {args.output}")

    # Write manifest
    manifest = {
        "stage": "formal_stage2",
        "method": "sun_rule_only",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_path": str(args.input),
        "gold_read_by_runner": False,
        "output_path": str(args.output),
        "sample_count": len(samples),
        "real_api": False,
        "llm_used": False,
        "sun_rule_record_definition": "r=(tr,Ar,Pr,Cr,Or,Er,Ur,fr)",
        "sun_paper_tuple_output": True,
        "exact_sun_reproduction": False,
        "claim_boundary": (
            "This is a local reconstruction aligned to Sun et al.'s Stage 2 "
            "rule-record definition. It is not the original Sun implementation "
            "because the trained BERT model and original CoreNLP/Tregex rules "
            "are unavailable."
        ),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Manifest written: {args.manifest}")

    # Quick summary
    modality_dist = {}
    for r in results:
        m = r.modality or "none"
        modality_dist[m] = modality_dist.get(m, 0) + 1
    print("\n  Predicted modality distribution:")
    for m, count in sorted(modality_dist.items()):
        print(f"    {m}: {count}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
