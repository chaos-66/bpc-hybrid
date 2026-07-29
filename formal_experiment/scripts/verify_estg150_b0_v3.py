"""Print the exact S2.10-E v3 and EStG-150 B0 re-evaluation gates."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.s2_10_evaluator_v3_gate import (  # noqa: E402
    verify_s2_10_evaluator_v3_gate,
    verify_s2_7_b0_v3_gate,
)


def main() -> int:
    result = {
        "evaluator_v3": verify_s2_10_evaluator_v3_gate(ROOT),
        "b0_v3_reevaluation": verify_s2_7_b0_v3_gate(ROOT),
    }
    result["ready"] = all(item["ready"] for item in result.values())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
