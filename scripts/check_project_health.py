"""Project health check script.

Does not read .env, call network, call real APIs, or read paths outside
the project root.
"""

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from bpc_hybrid.smoke import project_health  # noqa: E402


def main() -> None:
    print(json.dumps(project_health(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
