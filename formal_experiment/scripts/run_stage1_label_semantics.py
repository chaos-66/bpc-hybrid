"""Run the offline S1.3 P0/P1 label baselines on synthetic BPMN fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_label_semantics import (  # noqa: E402
    Stage1LabelError,
    load_label_contract,
    render_label_semantics,
)
from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
)


LABEL_CONFIG = ROOT / "configs" / "stage1_label_semantics_s13.json"
STRUCTURAL_CONFIG = ROOT / "configs" / "stage1_structural_s11_s14.json"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "stage1"
DEFAULT_BPMN = FIXTURE_ROOT / "s13_label_edge_cases.bpmn"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bpmn", type=Path, default=DEFAULT_BPMN)
    parser.add_argument("--baseline", choices=("P0", "P1", "both"), default="both")
    args = parser.parse_args()
    source = args.bpmn.resolve()
    try:
        source.relative_to(FIXTURE_ROOT.resolve())
    except ValueError:
        parser.error("S1.3 runner is restricted to synthetic Stage 1 fixtures")
    if source.suffix.lower() != ".bpmn" or not source.is_file():
        parser.error("S1.3 runner requires an existing .bpmn fixture")
    label_contract = load_label_contract(LABEL_CONFIG)
    structural_contract = load_stage1_contract(STRUCTURAL_CONFIG)
    process_record = parse_bpmn_file(source, contract=structural_contract)
    baselines = ("P0", "P1") if args.baseline == "both" else (args.baseline,)
    output = {
        baseline: render_label_semantics(
            process_record,
            baseline=baseline,
            contract=label_contract,
        )
        for baseline in baselines
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Stage1LabelError as exc:
        print(f"S1.3 contract failure: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
