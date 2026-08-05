"""Focused tests for the Layer E adjudication restore helper.

Verifies the pure merge function ``merge_layer_e_record`` used by
``scripts/restore_layer_e_adjudication_from_56d2b03.py``: user-entered
fields come from the historical snapshot, everything else is preserved from
the active file, and any mismatch fails closed.  No real file is touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.restore_layer_e_adjudication_from_56d2b03 import (  # noqa: E402
    RestoreError,
    USER_FIELDS,
    merge_layer_e_record,
)


def _record(sample_id: str = "estg_000002", **overrides) -> dict:
    record = {
        "sample_id": sample_id,
        "approved_text_en": "some approved english text",
        "approved_text_en_history": [],
        "approved_text_en_sha256": "abc",
        "decisions": {"translation": "accepted", "modality": "edited"},
        "human_correction": {"modality": {"label": "obligation"}},
        "review_state": {"status": "adjudicated", "reviewer": "user"},
        "llm_candidate": {"schema_version": "1.0.0", "clauses": []},
        "candidate_text_en": "candidate",
        "candidate_text_en_sha256": "def",
        "raw_text_de": "rohdeutsch",
        "raw_text_de_sha256": "ghi",
        "legacy_record_id": "legacy-2",
        "source_refs": [],
    }
    record.update(overrides)
    return record


def test_merge_takes_user_fields_from_history_and_preserves_rest() -> None:
    current = _record(
        approved_text_en=None,
        decisions={"translation": "unreviewed", "modality": "unreviewed"},
        review_state={"status": "needs_review", "reviewer": None},
    )
    historical = _record(
        approved_text_en="user approved text",
        decisions={"translation": "accepted", "modality": "edited"},
        review_state={"status": "adjudicated", "reviewer": "user"},
    )
    merged = merge_layer_e_record(current, historical)
    for field in USER_FIELDS:
        assert merged[field] == historical[field], field
    assert merged["llm_candidate"] == current["llm_candidate"]
    assert merged["candidate_text_en"] == current["candidate_text_en"]
    assert merged["raw_text_de"] == current["raw_text_de"]
    assert merged["legacy_record_id"] == current["legacy_record_id"]
    assert merged["sample_id"] == "estg_000002"


def test_merge_fails_closed_on_sample_id_mismatch() -> None:
    with pytest.raises(RestoreError, match="sample_id mismatch"):
        merge_layer_e_record(_record("estg_000002"), _record("estg_000003"))


def test_merge_fails_closed_on_missing_user_field() -> None:
    historical = _record()
    del historical["human_correction"]
    with pytest.raises(RestoreError, match="human_correction"):
        merge_layer_e_record(_record(), historical)
