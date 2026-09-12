# -*- coding: utf-8 -*-
"""Create the v2 LLM fallback authorization event from the user's exact reply.

Usage:
  python scripts/build_s3_semantic_grounding_llm_authorization_v1.py \
    --sentence-file path/to/user_reply.txt --apply

The builder is offline; it only writes the authorization event after the
sentence exactly matches the preflight request hash.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.s3_semantic_grounding_llm_v1 import (  # noqa: E402
    build_authorization_event_from_sentence,
    build_request_set,
)
from bpc_hybrid.s3_semantic_grounding_v2 import REVISION as V2_REVISION  # noqa: E402

CONFIG = ROOT / "configs/stage3_semantic_grounding_v2.json"
PACK = ROOT / "outputs/evidence/s3_semantic_grounding_v2/llm_fallback_candidate_pack_v1.json"
OUTPUT = ROOT / "outputs/reports/s3_semantic_grounding_v2_llm_authorization.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sentence-file", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if OUTPUT.exists() and not args.overwrite:
        raise SystemExit(f"refusing to overwrite existing {OUTPUT}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))["llm_fallback"]
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    request_set = build_request_set(pack, config)
    sentence = args.sentence_file.read_text(encoding="utf-8").strip()
    event = build_authorization_event_from_sentence(sentence, request_set, pack, config)
    if args.apply:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(event, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8", newline="\n")
        print(f"authorization event written: {OUTPUT.relative_to(ROOT)}")
    else:
        print(json.dumps({
            "dry_run": True,
            "scope": event["scope"],
            "model": event["model"],
            "max_calls": event["max_calls"],
            "usd_cap": event["usd_cap"],
            "authorization_sentence_sha256": event["authorization_sentence_sha256"],
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
