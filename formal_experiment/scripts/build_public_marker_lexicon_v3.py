"""Build or verify the source-only public marker lexicon v3 freeze."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.sun_style.public_marker_lexicon_v3 import (  # noqa: E402
    PublicMarkerLexiconV3Error,
    materialize_or_check,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        report = materialize_or_check(ROOT, write=args.write)
    except PublicMarkerLexiconV3Error as exc:
        print(f"public marker lexicon v3 failed closed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
