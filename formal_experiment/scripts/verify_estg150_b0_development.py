"""Verify the exact EStG-150 B0 development result lock."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.s2_7_b0_development_gate import (  # noqa: E402
    verify_s2_7_b0_development_gate,
)


def main() -> int:
    result = verify_s2_7_b0_development_gate(ROOT)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
