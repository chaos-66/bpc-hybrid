"""Print the formal experiment status."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FORMAL_ROOT = Path(__file__).resolve().parents[1]
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.status import collect_status, print_human


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human", action="store_true", help="Print a human-readable report")
    args = parser.parse_args()

    status = collect_status()
    if args.human:
        print_human(status)
    else:
        print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
