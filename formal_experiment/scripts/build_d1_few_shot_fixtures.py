"""Build a few-shot block for the D1 prompt with character offsets computed by Python.

This script writes a Markdown file fragment that the loader can verify.
It is intentionally a one-shot builder, not a runtime tool.

Run from ``formal_experiment/``:
    python scripts/build_d1_few_shot_fixtures.py
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "prompts" / "sun_compat" / "direct_llm_few_shot_fixtures.json"
OUT.write_text(json.dumps([
    {
        "description": "Example 1 \u2014 single obligation with actor + action + constraint",
        "input": "The controller shall notify the supervisory authority within 72 hours.",
        "build": {
            "sample_id": "estg_demo_1",
            "source_id": "estg_demo_1",
            "source_text": "The controller shall notify the supervisory authority within 72 hours.",
        },
    },
    {
        "description": "Example 2 \u2014 definition clause (no action)",
        "input": "'Personal data' means any information relating to an identified or identifiable natural person.",
        "build": {
            "sample_id": "estg_demo_2",
            "source_id": "estg_demo_2",
            "source_text": "'Personal data' means any information relating to an identified or identifiable natural person.",
        },
    },
    {
        "description": "Example 3 \u2014 prohibition with exception",
        "input": "Member States may not process personal data unless required by Union law.",
        "build": {
            "sample_id": "estg_demo_3",
            "source_id": "estg_demo_3",
            "source_text": "Member States may not process personal data unless required by Union law.",
        },
    },
    {
        "description": "Example 4 \u2014 multi-action with order relation",
        "input": "The controller shall first assess the risk, then notify the supervisory authority.",
        "build": {
            "sample_id": "estg_demo_4",
            "source_id": "estg_demo_4",
            "source_text": "The controller shall first assess the risk, then notify the supervisory authority.",
        },
    },
], indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {OUT}")
