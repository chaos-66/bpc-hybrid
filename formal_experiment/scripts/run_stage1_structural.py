"""Run the offline S1.1/S1.2/S1.4 structural parser on synthetic BPMN."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_process import (  # noqa: E402
    Stage1ProcessError,
    load_stage1_contract,
    parse_bpmn_file,
)


DEFAULT_CONFIG = ROOT / "configs" / "stage1_structural_s11_s14.json"
DEFAULT_INPUT = ROOT / "tests" / "fixtures" / "stage1" / "s11_branch_parallel.bpmn"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "stage1"
DEVELOPMENT_ROOT = ROOT / "outputs" / "development"


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--bpmn", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--record-out", type=Path)
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    try:
        config_path = args.config.resolve()
        input_path = args.bpmn.resolve()
        if not _under(input_path, FIXTURE_ROOT):
            raise Stage1ProcessError(
                "the v1 structural runner is restricted to synthetic Stage 1 fixtures"
            )
        contract = load_stage1_contract(config_path)
        record = parse_bpmn_file(input_path, contract=contract)
        rendered = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
        if args.record_out:
            output = args.record_out.resolve()
            if not args.development:
                raise Stage1ProcessError("--development is required for --record-out")
            if not _under(output, DEVELOPMENT_ROOT):
                raise Stage1ProcessError("Process Record output must stay under outputs/development")
            if output.exists():
                raise Stage1ProcessError(f"refusing to overwrite: {output}")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
    except Stage1ProcessError as exc:
        print(f"Stage 1 structural run failed closed: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
