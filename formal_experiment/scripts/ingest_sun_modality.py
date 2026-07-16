"""S2.1-B: CLI for the Sun modality importer.

This CLI is intentionally thin: it parses args, calls the importer, and
prints a JSON report. It does NOT call any LLM, does NOT read ``.env``,
and does NOT touch forbidden paths.

Usage examples (headered strict-one-hot synthetic fixture adapter only).
The verified headerless official positional schema is handled by
``audit_ingest_sun_modality_official.py``; do not pass the official CSV to
this named-column CLI:

    # Inspect the official ZIP without writing anything:
    python scripts/ingest_sun_modality.py \\
        --contract configs/datasets/sun_modality_dataset.json \\
        --project-root . \\
        --inspect-only \\
        --csv-path tests/fixtures/sun_modality/inspect_only_official_proxy.csv

    # Run a real ingestion on a synthetic CSV with explicit column mapping
    # (this is what S2.1-B tests use to verify the contract):
    python scripts/ingest_sun_modality.py \\
        --contract configs/datasets/sun_modality_dataset.json \\
        --project-root . \\
        --csv-path tests/fixtures/sun_modality/synthetic_normal.csv \\
        --text-column text \\
        --id-column source_id \\
        --label-columns label_definition,label_obligation,label_permission,label_prohibition \\
        --out-dir .tmp/ingest_smoke

    # Override the seed for an experiment, with explicit overwrite:
    python scripts/ingest_sun_modality.py \\
        --contract configs/datasets/sun_modality_dataset.json \\
        --project-root . \\
        --csv-path tests/fixtures/sun_modality/synthetic_normal.csv \\
        --text-column text \\
        --id-column source_id \\
        --label-columns label_definition,label_obligation,label_permission,label_prohibition \\
        --out-dir .tmp/ingest_smoke \\
        --seed 1234 --allow-overwrite
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path


# Make bpc_hybrid importable when this CLI is invoked from a checkout
# without installing the package.
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT_GUESS = _HERE.parent
_SRC = _PROJECT_ROOT_GUESS / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.datasets.sun_modality_importer import (  # noqa: E402
    IngestionError,
    OverwriteRefused,
    ZipSafetyError,
    SchemaError,
    CrossSplitLeakageError,
    OneHotError,
    inspect_only,
    ingest,
    load_contract,
)


# Force UTF-8 on stdout so non-ASCII characters (German umlauts in
# synthetic fixtures) print cleanly even on Windows consoles that
# default to GBK / CP1252.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="ingest_sun_modality",
        description=(
            "S2.1-B: streaming importer for the Sun 2024 EStG modality "
            "official supplement. Inspect-only mode never writes to disk."
        ),
    )
    p.add_argument(
        "--contract",
        type=Path,
        required=True,
        help="Path to configs/datasets/sun_modality_dataset.json",
    )
    p.add_argument(
        "--project-root",
        type=Path,
        default=_PROJECT_ROOT_GUESS,
        help="Project root for resolving contract-relative paths "
             "(default: parent of this script's directory).",
    )
    p.add_argument(
        "--csv-path",
        type=Path,
        default=None,
        help=(
            "Optional override: read a plain CSV instead of streaming "
            "from the official ZIP. Use this for synthetic fixtures and "
            "for the S2.1-C first-stream sniff."
        ),
    )
    p.add_argument(
        "--text-column",
        type=str,
        default="text",
        help="Name of the text column in the CSV (default: text).",
    )
    p.add_argument(
        "--id-column",
        type=str,
        default=None,
        help=(
            "Optional explicit source-ID column. When omitted, the importer "
            "uses the documented row-index fallback and records it in the "
            "manifest. When supplied, empty or duplicate IDs fail closed."
        ),
    )
    p.add_argument(
        "--label-columns",
        type=str,
        required=True,
        help=(
            "Comma-separated label column names in the order matching "
            "the contract's modality_classes_canonical."
        ),
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Required for non-inspect runs.",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Override the contract seed (rare; not for S2.1-B default).",
    )
    p.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="Allow overwriting existing output files.",
    )
    p.add_argument(
        "--encoding",
        type=str,
        default="utf-8",
        help="CSV text encoding (default: utf-8).",
    )
    p.add_argument(
        "--inspect-only",
        action="store_true",
        help=(
            "Open the ZIP, verify integrity, list members, and dump the "
            "first N rows. NEVER writes to disk."
        ),
    )
    p.add_argument(
        "--inspect-sample-n",
        type=int,
        default=5,
        help="Number of sample rows to dump in inspect-only mode (default: 5).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    project_root = args.project_root.resolve()
    contract = load_contract(args.contract, project_root=project_root)
    label_columns = [c.strip() for c in args.label_columns.split(",") if c.strip()]
    if not label_columns:
        print("ERROR: --label-columns must be non-empty", file=sys.stderr)
        return 2

    if args.seed is not None:
        # Build a shallow override of the contract (split seed only) for
        # this CLI invocation. We do not mutate the original contract.
        import dataclasses
        contract = dataclasses.replace(contract, seed=int(args.seed))

    if args.inspect_only:
        try:
            report = inspect_only(
                contract,
                text_column=args.text_column,
                label_columns=label_columns,
                id_column=args.id_column,
                csv_path_override=args.csv_path,
                sample_n=args.inspect_sample_n,
                encoding=args.encoding,
            )
        except OverwriteRefused as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 4
        except CrossSplitLeakageError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 5
        except OneHotError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 6
        except SchemaError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 7
        except ZipSafetyError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 8
        except IngestionError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 9
        # Inspect-only: NO files written. We emit a JSON report to stdout.
        out = report.as_dict()
        out["write_action"] = "none"
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        if not out["zip_official_sha1_match"]:
            print(
                "ERROR: actual ZIP SHA-1 does not match "
                "source_zip_official_sha1; refusing canonical identity.",
                file=sys.stderr,
            )
            return 3
        if not out["zip_local_sha256_match"]:
            print(
                "ERROR: actual ZIP SHA-256 does not match "
                "source_zip_local_sha256; refusing local identity.",
                file=sys.stderr,
            )
            return 3
        if not out["csv_member_sha256_match_expected"]:
            print(
                "WARNING: csv member SHA-256 does not match contract-recorded value; "
                "this is informational in inspect-only mode.",
                file=sys.stderr,
            )
        return 0

    if args.out_dir is None:
        print("ERROR: --out-dir is required for non-inspect runs", file=sys.stderr)
        return 2

    try:
        manifest = ingest(
            contract,
            text_column=args.text_column,
            label_columns=label_columns,
            id_column=args.id_column,
            out_dir=args.out_dir,
            allow_overwrite=args.allow_overwrite,
            encoding=args.encoding,
            csv_path_override=args.csv_path,
        )
    except OverwriteRefused as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 4
    except CrossSplitLeakageError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 5
    except OneHotError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 6
    except SchemaError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 7
    except ZipSafetyError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 8
    except IngestionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 9

    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
