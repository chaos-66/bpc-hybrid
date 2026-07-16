#!/usr/bin/env python3
"""Offline S2.1-C complete audit / guarded import for the official CSV."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.datasets.sun_modality_importer import (  # noqa: E402
    IngestionError,
    load_contract,
)
from bpc_hybrid.datasets.sun_modality_official import (  # noqa: E402
    audit_official_csv,
    ingest_official_csv,
    write_schema_audit,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stream the complete official EStG_sent_vec.csv without extraction. "
            "Audit mode writes aggregate-only schema_audit.json; import mode "
            "fails closed before outputs for any schema/group blocker except an "
            "exact contract-locked pre-result conflict quarantine."
        )
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=PROJECT_ROOT / "configs" / "datasets" / "sun_modality_dataset.json",
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=(
            PROJECT_ROOT
            / "data"
            / "development"
            / "modality"
            / "sun_estg_modality_v1"
        ),
    )
    parser.add_argument("--mode", choices=("audit", "import"), default="audit")
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = load_contract(args.contract, project_root=args.project_root)
    try:
        if args.mode == "audit":
            report = audit_official_csv(contract)
            write_schema_audit(
                report,
                args.out_dir / "schema_audit.json",
                allow_overwrite=args.allow_overwrite,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        manifest = ingest_official_csv(
            contract,
            out_dir=args.out_dir,
            allow_overwrite=args.allow_overwrite,
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except IngestionError as exc:
        payload = {
            "status": "blocked",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        audit_report = getattr(exc, "audit_report", None)
        if isinstance(audit_report, dict):
            payload["hard_blockers"] = audit_report.get("hard_blockers", [])
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
