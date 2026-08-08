"""Render the blank S1.5 annotation protocol on synthetic BPMN only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_human_annotation import (  # noqa: E402
    Stage1AnnotationError,
    build_blank_annotation_pack,
    load_annotation_contract,
)
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file  # noqa: E402


ANNOTATION_CONFIG = ROOT / "configs" / "stage1_annotation_protocol_s15.json"
STRUCTURAL_CONFIG = ROOT / "configs" / "stage1_structural_s11_s14.json"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "stage1"
DEFAULT_BPMN = FIXTURE_ROOT / "s13_label_edge_cases.bpmn"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bpmn", type=Path, default=DEFAULT_BPMN)
    args = parser.parse_args()
    source = args.bpmn.resolve()
    try:
        source.relative_to(FIXTURE_ROOT.resolve())
    except ValueError:
        parser.error("S1.5 protocol runner is restricted to synthetic Stage 1 fixtures")
    if source.suffix.lower() != ".bpmn" or not source.is_file():
        parser.error("S1.5 protocol runner requires an existing .bpmn fixture")
    contract = load_annotation_contract(ANNOTATION_CONFIG)
    structural_contract = load_stage1_contract(STRUCTURAL_CONFIG)
    process_record = parse_bpmn_file(source, contract=structural_contract)
    pack = build_blank_annotation_pack(
        [process_record],
        dataset_id="s15_synthetic_protocol_fixture_v1",
        contract=contract,
    )
    print(json.dumps(pack, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Stage1AnnotationError as exc:
        print(f"S1.5 contract failure: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
