# -*- coding: utf-8 -*-
"""Deterministic sentence-level coarse view derivation from the published
formal Stage 2 Gold (zero-API, G0.4 evaluation-views contract).

Input:  data/gold/stage2/estg150_formal_gold_v1.json  (published formal Gold)
Output: outputs/evidence/g04_formal_coarse_view_v1/coarse_view_derived.json
        outputs/evidence/g04_formal_coarse_view_v1/manifest.json

The transform lives in src/bpc_hybrid/g04_coarse_view.py (shared with the
B0 formal arm and the D1/H1 zero-API re-evaluations).

Consistency proof (required by the G0.4 contract): the derived coarse view
must hash- and record-level match the historical sentence-level coarse gold
(semantic sha256 6e19cf3c..., the user-confirmed 2026-08-07 main view). If it
does NOT match, primary formal metrics MUST NOT be published; the exact
per-record diffs are reported instead. Known result (2026-08-10): modality
evidence differs on 147/150 records (published Gold carries modality as a
plain string), so the coarse view is evidence/diagnostic only and the formal
coarse MAIN-view metrics are not published.

No development coarse files are copied; the historical file is only READ for
the consistency comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.g04_coarse_view import (  # noqa: E402
    HISTORICAL_COARSE_SEMANTIC_SHA,
    build_coarse_view,
    semantic_hash_json,
)

FORMAL_GOLD = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
CONTRACT = ROOT / "configs" / "evaluation" / "g04_evaluation_views_contract_v1.json"
HISTORICAL_COARSE = (ROOT / "outputs" / "development"
                     / "s27_b0_coarse_gold_sentence_granularity_v1"
                     / "coarse_gold_sentence_level.json")
OUT_DIR = ROOT / "outputs" / "evidence" / "g04_formal_coarse_view_v1"
OUT_COARSE = OUT_DIR / "coarse_view_derived.json"
OUT_REPORT = OUT_DIR / "manifest.json"


def compare_with_historical(derived: list[dict[str, Any]]) -> dict[str, Any]:
    """Record-level consistency proof against the historical coarse gold.

    Reports exact field-level differences; the caller must NOT publish the
    derived view as the formal main view when the historical semantic hash
    does not match (published Gold carries modality as a plain string, so
    the local modality evidence spans of the historical coarse gold are not
    reproducible from it).
    """
    if not HISTORICAL_COARSE.exists():
        return {"comparable": False,
                "reason": f"historical coarse gold missing: {HISTORICAL_COARSE}"}
    historical = json.loads(HISTORICAL_COARSE.read_text(encoding="utf-8"))
    h_by_id = {r["sample_id"]: r for r in historical}
    diffs: list[str] = []
    field_diff_counts: dict[str, int] = {}
    for rec in derived:
        h = h_by_id.get(rec["sample_id"])
        if h is None:
            diffs.append(f"{rec['sample_id']}: missing in historical")
            continue
        if h != rec:
            d = _record_diff_fields(h, rec)
            diffs.append(f"{rec['sample_id']}: {d}")
            for f in d:
                field_diff_counts[f] = field_diff_counts.get(f, 0) + 1
    extra = [sid for sid in h_by_id if sid not in {r["sample_id"] for r in derived}]
    if extra:
        diffs.append(f"historical-only ids: {extra[:5]}")
    return {
        "comparable": True,
        "historical_path": str(HISTORICAL_COARSE.relative_to(ROOT)),
        "record_level_identical": not diffs,
        "diff_count": len(diffs),
        "diff_fields": field_diff_counts,
        "first_diffs": diffs[:10],
    }


def _record_diff_fields(hist: dict[str, Any], derived: dict[str, Any]) -> list[str]:
    """Which coarse-view fields differ between historical and derived records."""
    fields = []
    hc = (hist.get("clauses") or [{}])[0]
    dc = (derived.get("clauses") or [{}])[0]
    if hc.get("modality") != dc.get("modality"):
        fields.append("modality")
    for plural in ("actors", "actions", "conditions", "constraints", "exceptions"):
        if hc.get(plural) != dc.get(plural):
            fields.append(plural)
    if hc.get("clause_span") != dc.get("clause_span"):
        fields.append("clause_span")
    if hist.get("source_id") != derived.get("source_id"):
        fields.append("source_id")
    if hist.get("source_text") != derived.get("source_text"):
        fields.append("source_text")
    return fields


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="derive and verify without writing")
    args = parser.parse_args()

    gold = json.loads(FORMAL_GOLD.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    derived = build_coarse_view(gold)
    semantic_sha = semantic_hash_json(derived)
    comparison = compare_with_historical(derived)

    report = {
        "schema_version": "g04_formal_coarse_view_manifest@1.0.0",
        "contract": {"path": "configs/evaluation/g04_evaluation_views_contract_v1.json",
                     "sha256": hashlib.sha256(CONTRACT.read_bytes()).hexdigest()},
        "input": {"path": "data/gold/stage2/estg150_formal_gold_v1.json",
                  "sha256": hashlib.sha256(FORMAL_GOLD.read_bytes()).hexdigest()},
        "derived_view": {
            "path": "outputs/evidence/g04_formal_coarse_view_v1/coarse_view_derived.json",
            "records": len(derived),
            "semantic_sha256": semantic_sha,
            "historical_semantic_sha256": HISTORICAL_COARSE_SEMANTIC_SHA,
            "semantic_hash_matches_historical": semantic_sha == HISTORICAL_COARSE_SEMANTIC_SHA,
        },
        "consistency_with_historical": comparison,
        # REQUIRED by the G0.4 contract: when the derived view does not match
        # the historical sentence-level coarse gold, the formal MAIN view
        # metrics MUST NOT be published.
        "main_view_publishable": (
            semantic_sha == HISTORICAL_COARSE_SEMANTIC_SHA
            and comparison.get("record_level_identical", False)),
        "not_publishable_reason": (
            "modality evidence spans of the historical coarse view are not "
            "reproducible from the published formal Gold (modality published "
            "as plain string; Layer E modality.span local evidence dropped). "
            "147/150 records differ in modality evidence only; all other "
            "fields (actors/actions/conditions/constraints/exceptions, "
            "source_text, clause_span, source_id) are identical. Historical "
            "coarse numbers remain development-side provenance, NOT formal.")
        if (semantic_sha != HISTORICAL_COARSE_SEMANTIC_SHA
            or not comparison.get("record_level_identical", False)) else None,
        "granularity_rule": contract["views"]["coarse_sentence_level"]["transform"]["rule"],
        "generated_zero_api": True,
        "no_development_file_copied": True,
    }

    if args.dry_run:
        print("dry-run: coarse view derived (not written)")
        print(f"  semantic sha: {semantic_sha[:16]}... "
              f"match historical: {semantic_sha == HISTORICAL_COARSE_SEMANTIC_SHA}")
        print(f"  record-level identical: {comparison.get('record_level_identical')}")
        return 0

    data = (json.dumps(derived, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    if OUT_COARSE.exists() and OUT_COARSE.read_bytes() != data:
        raise RuntimeError(f"refusing to overwrite different content: {OUT_COARSE}")
    OUT_COARSE.parent.mkdir(parents=True, exist_ok=True)
    OUT_COARSE.write_bytes(data)
    rep = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT_REPORT.exists() and OUT_REPORT.read_bytes() != rep:
        raise RuntimeError(f"refusing to overwrite different content: {OUT_REPORT}")
    OUT_REPORT.write_bytes(rep)

    print(f"coarse view written: {OUT_COARSE.relative_to(ROOT)}")
    print(f"  semantic sha: {semantic_sha[:16]}... "
          f"match historical: {semantic_sha == HISTORICAL_COARSE_SEMANTIC_SHA}")
    print(f"  record-level identical: {comparison.get('record_level_identical')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
