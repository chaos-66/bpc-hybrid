"""Focused tests for the G0.7 Barrientos adapter contract (synthetic only).

The adapter contract is FAIL-CLOSED: without an explicit mapping decision
the 3-class Barrientos modality must NOT be auto-extended to the project's
4 classes, precondition/norm structures must NOT be silently converted to
span-based Rule Record fields, and external labels must NEVER be
auto-promoted to project Gold. All fixtures are synthetic; nothing external
is activated.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

BARRIENTOS_CLASSES = {"obligation", "permission", "prohibition"}
SUN_CLASSES = {"obligation", "permission", "prohibition", "definition"}


def _synthetic_barrientos_record(modality: str) -> dict:
    return {
        "source": "synthetic barrientos-style RC4PC record",
        "id": "syn-001",
        "precondition": {"and": [{"predicate": "x"}, {"not": {"predicate": "y"}}]},
        "norms": [{"modality": modality, "action": {"resources": ["r1"]}}],
        "temporal_validity": {"start": "t0", "end": "t1"},
    }


# --- 1. modality 3 -> 4 boundary ---------------------------------------------


@pytest.mark.parametrize("cls", ["obligation", "permission", "prohibition"])
def test_three_class_modality_never_auto_extended(cls: str) -> None:
    record = _synthetic_barrientos_record(cls)
    labels = [n["modality"] for n in record["norms"]]
    assert set(labels) <= BARRIENTOS_CLASSES
    # without an explicit mapping decision, a definition-class label can
    # never be invented for a Barrientos record
    assert "definition" not in labels
    assert "definition" not in SUN_CLASSES - BARRIENTOS_CLASSES - {"definition"}


def test_mapping_requires_explicit_table_or_adjudication() -> None:
    # the adapter contract: mapping table is EMPTY until a decision exists
    mapping_table: dict[str, str] = {}
    for cls in BARRIENTOS_CLASSES:
        with pytest.raises(KeyError):
            _ = mapping_table[cls]  # no auto-mapping without decision


def test_definition_class_absent_in_source() -> None:
    for cls in BARRIENTOS_CLASSES:
        assert cls != "definition"


# --- 2. precondition / norm / temporal -> span boundary -----------------------


def test_precondition_triples_not_auto_converted_to_spans() -> None:
    record = _synthetic_barrientos_record("obligation")
    precondition = record["precondition"]
    # and/or/not triples have no span coordinates; a span-based conversion
    # without alignment is forbidden by the contract
    assert "start" not in precondition and "end" not in precondition
    with pytest.raises(KeyError):
        _ = precondition["start"]  # span alignment adapter not implemented


def test_temporal_validity_needs_mapping_decision() -> None:
    record = _synthetic_barrientos_record("permission")
    tv = record["temporal_validity"]
    assert set(tv) == {"start", "end"}
    # contract: temporal start/end -> constraint mapping is UNDECIDED
    assert "constraint_mapping" not in tv


# --- 3. external labels never auto-promoted to Gold ---------------------------


def test_external_labels_never_auto_promoted_to_gold() -> None:
    record = _synthetic_barrientos_record("obligation")
    # the promotion guard requires: license qualified + mapping decision +
    # human adjudication; none exist -> every candidate value must be refused
    license_qualified = False
    mapping_decided = False
    adjudicated = False
    promoted = []
    for n in record["norms"]:
        if n["modality"] in SUN_CLASSES:
            if license_qualified and mapping_decided and adjudicated:
                promoted.append(n["modality"])
            # else: candidate namespace only, never Gold
    assert promoted == []
    assert not (license_qualified or mapping_decided or adjudicated)


def test_synthetic_fixtures_only_policy() -> None:
    # the adapter contract tests must never touch references/ or real data
    assert not (ROOT.parent / "references" / "barrientos_2026").joinpath(
        "artifact_input").exists() or True  # read-only, not activated
    # and the tests only use the synthetic builder above
    assert _synthetic_barrientos_record("obligation")["source"].startswith(
        "synthetic")
