"""Create the immutable GDPR7 Process Records, blank pack, and editable review copy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_formal_dataset import (  # noqa: E402
    Stage1FormalDatasetError,
    build_formal_blank_annotation_pack,
    build_formal_process_records,
    load_formal_membership_contract,
)


CONFIG = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"


def _write_new(path: Path, value: object) -> None:
    if path.exists():
        raise Stage1FormalDatasetError(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        contract = load_formal_membership_contract(args.config)
        records = build_formal_process_records(contract)
        blank = build_formal_blank_annotation_pack(records, contract)
        if not args.write:
            print(
                json.dumps(
                    {
                        "dataset_id": contract["dataset_id"],
                        "process_records": len(records),
                        "activities": sum(len(item["activities"]) for item in records),
                        "label_fields": blank["review_summary"]["label_fields"],
                        "freeze_ready": blank["review_summary"]["freeze_ready"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        annotation = contract["annotation_activation"]
        _write_new(ROOT / annotation["process_records_path"], {"dataset_id": contract["dataset_id"], "records": records})
        _write_new(ROOT / annotation["blank_template_path"], blank)
        _write_new(ROOT / annotation["editable_path"], blank)
        print(f"created 3 no-overwrite review artifacts for {len(records)} BPMN files")
        return 0
    except Stage1FormalDatasetError as exc:
        print(f"GDPR7 build failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

