# -*- coding: utf-8 -*-
"""Build the GDPR7 six-element review EDITABLE document from the blank surface (v1).

Purpose
-------
The blank surface
``data/development/human_review/gdpr7_six_element_review_blank_v1.json``
(schema ``gdpr7_six_element_review_surface@1.0.0``) is a fail-closed,
decisions-all-null surface that must NEVER be written by an automated process.
This builder creates the *editing* layer on top of it:

``data/development/human_review/gdpr7_six_element_review_decisions_v1.json``
(schema ``gdpr7_six_element_review_editable@1.0.0``) — a deep copy of the blank
document in which a human reviewer (only a human) may later set review
decisions through ``scripts/gdpr7_review_tool_v1.py`` or an explicit import
(``scripts/import_gdpr7_review_decisions_v1.py``).

Only the top level is re-laid:

* ``schema_version`` -> ``gdpr7_six_element_review_editable@1.0.0``;
* ``dataset_id`` unchanged (the editing layer is still the same dataset);
* ``status`` -> ``editing_unreviewed``;
* ``source_blank_sha256`` -> raw-byte sha256 of the blank file;
* ``created_at_utc`` -> ISO-8601 UTC timestamp of the build;
* ``counts`` and ``rules[]`` are copied verbatim (deep copy) from the blank.

Guards (fail-closed, zero LLM/API/network):

1. the blank document must pass the shared blank-invariant validator
   (``bpc_hybrid.gdpr7_review_rules_v1.validate_blank_document``): all review
   decisions null, review_state unreviewed, notes null, schema exact;
2. the output file must not already exist — there is intentionally no
   ``--overwrite``: an existing editable file is live review state and is
   never clobbered (exit code 2 when present);
3. the blank file itself is only ever read, never modified.

The output is written with the workflow's canonical byte layout (UTF-8, LF,
single trailing newline: ``json.dumps(ensure_ascii=False, indent=2) + "\\n"``).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.gdpr7_review_rules_v1 import (  # noqa: E402
    DEFAULT_BLANK_PATH,
    DEFAULT_EDITABLE_PATH,
    SCHEMA_EDITABLE,
    STATUS_EDITING_UNREVIEWED,
    doc_json_bytes,
    sha256_bytes,
    validate_blank_document,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_editable(blank_path: Path,
                   output: Path,
                   created_at_utc: Optional[str] = None,
                   blank_bytes: Optional[bytes] = None) -> dict[str, Any]:
    """Build the editable document from ``blank_path`` and write it to ``output``.

    ``blank_bytes`` (optional) lets offline tests inject a doctored blank copy
    whose bytes are already known without re-reading the file. The CLI always
    reads ``blank_path`` itself.
    """
    blank_path = Path(blank_path)
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing editable file: {output}")
    if not blank_path.is_file():
        raise FileNotFoundError(f"blank surface file missing: {blank_path}")
    if blank_bytes is None:
        blank_bytes = blank_path.read_bytes()
    blank_doc = json.loads(blank_bytes.decode("utf-8"))

    blank_problems = validate_blank_document(blank_doc)
    if blank_problems:
        raise ValueError(
            "blank surface invariant violated; refusing to build an editable "
            "copy:\n  " + "\n  ".join(blank_problems)
        )

    editable = {
        "schema_version": SCHEMA_EDITABLE,
        "dataset_id": blank_doc.get("dataset_id"),
        "status": STATUS_EDITING_UNREVIEWED,
        "counts": copy.deepcopy(blank_doc.get("counts")),
        "source_blank_sha256": sha256_bytes(blank_bytes),
        "created_at_utc": created_at_utc or _utc_now(),
        "rules": copy.deepcopy(blank_doc.get("rules")),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(doc_json_bytes(editable))
    return editable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blank", type=Path, default=DEFAULT_BLANK_PATH,
                        help="blank surface file to copy (read-only source)")
    parser.add_argument("--output", type=Path, default=DEFAULT_EDITABLE_PATH,
                        help="editable output file (must not exist yet)")
    args = parser.parse_args()

    try:
        editable = build_editable(blank_path=args.blank, output=args.output)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    counts = editable.get("counts", {})
    print(
        f"已创建 GDPR7 六要素裁决 editable 文件: {args.output} "
        f"(rules={counts.get('rules')} sentences={counts.get('sentences')} "
        f"status={editable['status']} "
        f"source_blank_sha256={editable['source_blank_sha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
