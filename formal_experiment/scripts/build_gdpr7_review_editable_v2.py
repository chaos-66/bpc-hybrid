# -*- coding: utf-8 -*-
"""Build the GDPR7 six-element review EDITABLE document v2 (schema 1.1.0).

Purpose
-------
Same builder semantics as ``scripts/build_gdpr7_review_editable_v1.py`` but for
the v2 structured editing layer: the output is

``data/development/human_review/gdpr7_six_element_review_decisions_v2.json``
(schema ``gdpr7_six_element_review_editable@1.1.0``) — a deep copy of the blank
surface in which a human reviewer may later set review decisions (legacy six
blocks and/or the structured ``rule_items`` / ``actor_action_map`` /
``order_relations`` layer) through ``scripts/gdpr7_review_tool_v1.py`` or an
explicit import (``scripts/import_gdpr7_review_decisions_v1.py``).

Only the top level is re-laid on top of the blank:

* ``schema_version`` -> ``gdpr7_six_element_review_editable@1.1.0``;
* ``supersedes`` -> ``gdpr7_six_element_review_editable@1.0.0``;
* ``previous_editable_file`` -> ``gdpr7_six_element_review_decisions_v1.json``;
* ``dataset_id`` unchanged (the editing layer is still the same dataset);
* ``status`` -> ``editing_unreviewed``;
* ``source_blank_sha256`` -> raw-byte sha256 of the blank file;
* ``v1_editable_sha256`` -> raw-byte sha256 of the v1 decisions file (when it
  exists);  ``None`` when the v1 file is absent;
* ``created_at_utc`` -> ISO-8601 UTC timestamp of the build;
* ``counts`` and ``rules[]`` copied verbatim from the blank; every sentence
  ``review`` additionally gains the v2 structured keys
  (``rule_items`` / ``actor_action_map`` / ``order_relations``) all set to
  ``None``.

Guards (fail-closed, zero LLM/API/network):

1. the blank document must pass the shared blank-invariant validator
   (``bpc_hybrid.gdpr7_review_rules_v1.validate_blank_document``);
2. the v1 decisions file (when given) must be an all-empty editable v1
   document (no non-null decision anywhere, every sentence ``unreviewed``).
   The v1 content is NEVER migrated/copied into the v2 document — decisions
   are human-only and a non-empty v1 file fails loudly with a hint to perform
   the (human-supervised) migration first instead of auto-copying decisions;
3. the output file must not already exist — there is intentionally no
   ``--overwrite`` (exit code 2 when present);
4. the blank / v1 files are only ever read, never modified.

The output is written with the workflow's canonical byte layout (UTF-8, LF,
single trailing newline: ``json.dumps(ensure_ascii=False, indent=2) + "\\n"``).
"""

from __future__ import annotations

import argparse
import copy
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
    ALL_FIELDS,
    DEFAULT_BLANK_PATH,
    DEFAULT_EDITABLE_PATH,
    DEFAULT_EDITABLE_V2_PATH,
    PREVIOUS_EDITABLE_FILENAME,
    SCHEMA_EDITABLE,
    SCHEMA_EDITABLE_V2,
    STATUS_EDITING_UNREVIEWED,
    doc_json_bytes,
    iter_flat_sentences,
    sha256_bytes,
    validate_blank_document,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def v1_decisions_is_empty(v1_doc: Any) -> list[str]:
    """Problems preventing use of the v1 decisions file as a provenance input.

    Empty list == the v1 document holds no decisions at all (all six legacy
    decisions are null on every sentence and every sentence is unreviewed) so
    it is safe to record its sha256 as provenance without migrating content.
    """
    problems: list[str] = []
    if not isinstance(v1_doc, dict):
        return ["v1 editable document is not an object"]
    if v1_doc.get("schema_version") != SCHEMA_EDITABLE:
        problems.append(
            f"v1 schema_version {v1_doc.get('schema_version')!r} != "
            f"{SCHEMA_EDITABLE!r}"
        )
    for _rid, sentence in iter_flat_sentences(v1_doc):
        sid = sentence.get("sample_id")
        review = sentence.get("review")
        if not isinstance(review, dict):
            continue
        if review.get("review_state") not in (None, "unreviewed"):
            problems.append(
                f"v1 {sid}: review_state {review.get('review_state')!r} != "
                f"unreviewed（v1 非空，不能自动构建 v2；请先人工迁移）"
            )
        for field in ALL_FIELDS:
            entry = review.get(field)
            if isinstance(entry, dict) and entry.get("decision") is not None:
                problems.append(
                    f"v1 {sid}: review.{field}.decision 非空（v1 非空，不能"
                    f"自动构建 v2；请先人工迁移）"
                )
    return problems


def build_editable_v2(blank_path: Path,
                      output: Path,
                      v1_file: Optional[Path] = None,
                      created_at_utc: Optional[str] = None,
                      blank_bytes: Optional[bytes] = None) -> dict[str, Any]:
    """Build the v2 editable document and write it to ``output``.

    ``v1_file`` is optional: when present its raw-byte sha256 is recorded in
    ``v1_editable_sha256`` (the v1 content must be all-empty); when absent the
    field is ``None``.  ``blank_bytes`` lets offline tests inject a doctored
    blank copy whose bytes are already known without re-reading the file.
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

    v1_sha: Optional[str] = None
    if v1_file is not None:
        v1_path = Path(v1_file)
        if not v1_path.is_file():
            raise FileNotFoundError(f"v1 decisions file missing: {v1_path}")
        v1_bytes = v1_path.read_bytes()
        v1_sha = sha256_bytes(v1_bytes)
        v1_doc = json.loads(v1_bytes.decode("utf-8"))
        v1_problems = v1_decisions_is_empty(v1_doc)
        if v1_problems:
            raise ValueError(
                "v1 decisions file is not empty; refusing to build v2 without "
                "an explicit human migration:\n  " + "\n  ".join(v1_problems)
            )

    rules = copy.deepcopy(blank_doc.get("rules"))
    for _rid, sentence in iter_flat_sentences({"rules": rules}):
        review = sentence.get("review")
        if isinstance(review, dict):
            review.setdefault("rule_items", None)
            review.setdefault("actor_action_map", None)
            review.setdefault("order_relations", None)

    editable = {
        "schema_version": SCHEMA_EDITABLE_V2,
        "dataset_id": blank_doc.get("dataset_id"),
        "status": STATUS_EDITING_UNREVIEWED,
        "counts": copy.deepcopy(blank_doc.get("counts")),
        "source_blank_sha256": sha256_bytes(blank_bytes),
        "v1_editable_sha256": v1_sha,
        "created_at_utc": created_at_utc or _utc_now(),
        "supersedes": SCHEMA_EDITABLE,
        "previous_editable_file": PREVIOUS_EDITABLE_FILENAME,
        "rules": rules,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(doc_json_bytes(editable))
    return editable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blank", type=Path, default=DEFAULT_BLANK_PATH,
                        help="blank surface file to copy (read-only source)")
    parser.add_argument("--output", type=Path, default=DEFAULT_EDITABLE_V2_PATH,
                        help="v2 editable output file (must not exist yet)")
    parser.add_argument("--v1-file", type=Path, default=DEFAULT_EDITABLE_PATH,
                        help="v1 decisions file whose sha256 is recorded "
                             "(must be all-empty); pass an empty string to "
                             "skip the v1 provenance record")
    args = parser.parse_args()

    v1_file: Optional[Path] = None
    if str(args.v1_file):
        v1_file = args.v1_file

    try:
        editable = build_editable_v2(blank_path=args.blank, output=args.output,
                                     v1_file=v1_file)
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
        f"已创建 GDPR7 六要素裁决 editable v2 文件: {args.output} "
        f"(rules={counts.get('rules')} sentences={counts.get('sentences')} "
        f"status={editable['status']} schema={editable['schema_version']} "
        f"source_blank_sha256={editable['source_blank_sha256']} "
        f"v1_editable_sha256={editable['v1_editable_sha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
