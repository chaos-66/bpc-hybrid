"""Check whether the imported Sun code can serve as the exact baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


FORMAL_ROOT = Path(__file__).resolve().parents[1]
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.sun_baseline import audit_sun_baseline, print_human


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human", action="store_true", help="Print a human-readable report")
    args = parser.parse_args()

    audit = audit_sun_baseline()
    if args.human:
        print_human(audit)
    else:
        print(json.dumps(audit, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
