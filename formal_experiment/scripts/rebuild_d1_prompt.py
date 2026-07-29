"""Validate the frozen D1 v5 prompt and its generated few-shot records.

The historical version of this command rebuilt the prompt from a v3/v4
template.  Stage 2 extraction-contract v1 makes the prompt a hash-locked
artifact, so this compatibility entry point is deliberately read-only.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from bpc_hybrid.stage2_canonical import validate_canonical  # noqa: E402


CONTRACT_ID = "stage2_extraction_contract@1.0.0"
CONTRACT_SHA256 = "7f17ecba78cfa1acf1bbc488942f1c85c37d08ece7662c622bab4226bd2dbd46"
PROMPT_SHA256 = "79f6f76fc9779abb87fc919e4384386ac812d40fcedaf73df0ea8ea1377af62e"


def main() -> int:
    prompt = load_prompt("direct_llm_sun_record_prompt")
    if prompt.sha256 != PROMPT_SHA256:
        raise SystemExit("D1 v5 prompt hash mismatch; refusing to rebuild a frozen artifact")
    if (
        prompt.extras.get("version") != "5"
        or prompt.extras.get("contract_id") != CONTRACT_ID
        or prompt.extras.get("contract_sha256") != CONTRACT_SHA256
    ):
        raise SystemExit("D1 v5 extraction-contract binding mismatch")
    if len(prompt.few_shot_examples) != 4:
        raise SystemExit("D1 v5 must contain exactly four synthetic examples")
    for example in prompt.few_shot_examples:
        report = validate_canonical(example["output"])
        if not (report.schema_valid and report.cross_field_valid):
            raise SystemExit(f"invalid D1 v5 example: {report.errors}")
    print(f"Validated frozen D1 v5 prompt: {prompt.path}")
    print("Few-shot examples validated: 4; no file was written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
