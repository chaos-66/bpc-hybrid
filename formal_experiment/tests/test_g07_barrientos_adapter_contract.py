"""Real-execution focused tests for the G0.7 / S2.11 Barrientos adapter
core (synthetic/shadow implementation).

These tests CALL `src/bpc_hybrid/s2_11_barrientos_adapter.py` with synthetic
fixtures only. They never access, copy or execute real
`references/barrientos_2026` data. Every fail-closed condition asserts a
machine-decodable error code; no assertion is ever vacuous (`or True`
guards are forbidden here).
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from bpc_hybrid.s2_11_barrientos_adapter import (
    ActivationNotAuthorizedError,
    ActivationState,
    AmbiguousSpanError,
    BarrientosAdapterError,
    DefinitionNotProducibleError,
    InvalidMappedModalityError,
    InvalidSpanError,
    InvalidStructureError,
    LicenseNotQualifiedError,
    LicenseState,
    MappingPolicy,
    MappingPolicyIncompleteError,
    MappingPolicyNotApprovedError,
    MissingSpanAlignmentError,
    MissingTextProvenanceError,
    SyntheticPolicyInFormalModeError,
    UnknownModalityError,
    UnresolvedCrossReferenceError,
    convert_to_candidate,
)

BARRIENTOS_CLASSES = ("obligation", "permission", "prohibition")


def _synthetic_policy(approved: bool = True,
                      synthetic_test_only: bool = True,
                      identity: dict[str, str] | None = None,
                      fields: dict[str, str] | None = None) -> MappingPolicy:
    return MappingPolicy(
        policy_id="syn-policy-v1",
        approved=approved,
        synthetic_test_only=synthetic_test_only,
        modality_identity=identity if identity is not None else {
            "obligation": "obligation",
            "permission": "permission",
            "prohibition": "prohibition",
        },
        field_mapping=fields if fields is not None else {
            "precondition": "condition",
        },
    )


def _synthetic_record(modality: str = "obligation", **overrides: Any) -> dict:
    text = ("the data subject shall be notified without undue delay")
    record: dict[str, Any] = {
        "source_record_id": "syn-001",
        "source_element": "norms[0]",
        "source_path": "synthetic:rc4pc/syn-001",
        "modality": modality,
        "text": text,
        "text_provenance": {
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "language": "en",
        },
        "span": {"start": 0, "end": len(text)},
        "text_span_source": "approved_english_alignment",
        "cross_references": [{"ref_id": "art-7", "resolved": True}],
        "structure": {"precondition": {"predicate": "x"},
                      "norm": {"modality": modality},
                      "temporal_validity": {"start": "t0", "end": "t1"}},
    }
    record.update(overrides)
    return record


def _qualified_license() -> LicenseState:
    return LicenseState(qualified=True, license_status="qualified")


def _authorized_activation() -> ActivationState:
    return ActivationState(authorized=True)


def _convert(record: dict[str, Any] | None = None, **kwargs: Any) -> dict:
    return convert_to_candidate(
        record if record is not None else _synthetic_record(),
        license_state=kwargs.pop("license_state", _qualified_license()),
        activation_state=kwargs.pop("activation_state",
                                    _authorized_activation()),
        mapping_policy=kwargs.pop("mapping_policy", _synthetic_policy()),
        mode=kwargs.pop("mode", "synthetic_test_only"),
    )


def _error_code(exc: BarrientosAdapterError) -> str:
    return exc.code


# --- 1. license / activation / policy fail-closed ---------------------------


def test_license_not_qualified_refuses() -> None:
    with pytest.raises(LicenseNotQualifiedError) as exc:
        _convert(license_state=LicenseState(qualified=False))
    assert _error_code(exc.value) == "LICENSE_NOT_QUALIFIED"


def test_activation_not_authorized_refuses() -> None:
    with pytest.raises(ActivationNotAuthorizedError) as exc:
        _convert(activation_state=ActivationState(authorized=False))
    assert _error_code(exc.value) == "ACTIVATION_NOT_AUTHORIZED"


def test_mapping_policy_not_approved_refuses() -> None:
    with pytest.raises(MappingPolicyNotApprovedError) as exc:
        _convert(mapping_policy=_synthetic_policy(approved=False))
    assert _error_code(exc.value) == "MAPPING_POLICY_NOT_APPROVED"


# --- 2. modality 3 -> 4 boundary ---------------------------------------------


@pytest.mark.parametrize("cls", BARRIENTOS_CLASSES)
def test_shared_modalities_never_auto_mapped_without_policy(cls: str) -> None:
    # approved=False: even identity mapping must be refused
    with pytest.raises(MappingPolicyNotApprovedError):
        _convert(_synthetic_record(modality=cls),
                 mapping_policy=_synthetic_policy(approved=False))
    # approved=True but the policy has NO modality entry at all
    with pytest.raises(MappingPolicyIncompleteError) as exc:
        _convert(_synthetic_record(modality=cls),
                 mapping_policy=_synthetic_policy(identity={}))
    assert _error_code(exc.value) == "MAPPING_POLICY_INCOMPLETE"


def test_definition_never_invented() -> None:
    policy = _synthetic_policy(identity={
        "obligation": "definition", "permission": "permission",
        "prohibition": "prohibition"})
    with pytest.raises(DefinitionNotProducibleError) as exc:
        _convert(_synthetic_record(modality="obligation"),
                 mapping_policy=policy)
    assert _error_code(exc.value) == "DEFINITION_NOT_PRODUCIBLE"


def test_unknown_modality_fails_closed() -> None:
    with pytest.raises(UnknownModalityError) as exc:
        _convert(_synthetic_record(modality="definition"))
    assert _error_code(exc.value) == "UNKNOWN_MODALITY"


def test_invalid_mapped_modality_fails_closed() -> None:
    policy = _synthetic_policy(identity={
        "obligation": "bogus", "permission": "permission",
        "prohibition": "prohibition"})
    with pytest.raises(InvalidMappedModalityError) as exc:
        _convert(_synthetic_record(modality="obligation"),
                 mapping_policy=policy)
    assert _error_code(exc.value) == "INVALID_MAPPED_MODALITY"


# --- 3. text / span alignment ------------------------------------------------


def test_missing_text_refuses() -> None:
    with pytest.raises(MissingTextProvenanceError) as exc:
        _convert(_synthetic_record(text="   "))
    assert _error_code(exc.value) == "MISSING_TEXT_PROVENANCE"


def test_text_provenance_hash_mismatch_refuses() -> None:
    record = _synthetic_record()
    record["text_provenance"] = {"sha256": "00" * 64, "language": "en"}
    with pytest.raises(MissingTextProvenanceError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "MISSING_TEXT_PROVENANCE"


def test_missing_span_refuses() -> None:
    with pytest.raises(MissingSpanAlignmentError) as exc:
        _convert(_synthetic_record(span=None))
    assert _error_code(exc.value) == "MISSING_SPAN_ALIGNMENT"


def test_external_offsets_without_alignment_refuse() -> None:
    record = _synthetic_record(text_span_source="external_offsets")
    with pytest.raises(MissingSpanAlignmentError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "MISSING_SPAN_ALIGNMENT"


def test_span_out_of_bounds_refuses() -> None:
    with pytest.raises(InvalidSpanError) as exc:
        _convert(_synthetic_record(span={"start": 0, "end": 9999}))
    assert _error_code(exc.value) == "INVALID_SPAN"


def test_negative_span_refuses() -> None:
    with pytest.raises(InvalidSpanError) as exc:
        _convert(_synthetic_record(span={"start": -1, "end": 5}))
    assert _error_code(exc.value) == "INVALID_SPAN"


def test_ambiguous_span_refuses() -> None:
    text = "the data subject shall be notified, the data subject shall be"
    record = _synthetic_record(
        text=text,
        text_provenance={
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "language": "en"},
        span={"start": 0, "end": 16})  # "the data subject" appears twice
    with pytest.raises(AmbiguousSpanError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "AMBIGUOUS_SPAN"


# --- 4. cross references -----------------------------------------------------


def test_unresolved_cross_reference_refuses() -> None:
    record = _synthetic_record(cross_references=[
        {"ref_id": "art-7", "resolved": True},
        {"ref_id": "art-22", "resolved": False}])
    with pytest.raises(UnresolvedCrossReferenceError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "UNRESOLVED_CROSS_REFERENCE"


# --- 5. synthetic policy / formal mode ---------------------------------------


def test_synthetic_policy_never_enters_formal_mode() -> None:
    with pytest.raises(SyntheticPolicyInFormalModeError) as exc:
        _convert(mode="formal")
    assert _error_code(exc.value) == "SYNTHETIC_POLICY_IN_FORMAL_MODE"


# --- 6. external labels never Gold -------------------------------------------


def test_external_labels_never_auto_promoted_to_gold() -> None:
    record = _synthetic_record(external_annotation={
        "modality": "obligation", "origin": "external ground truth"})
    out = _convert(record)
    assert out["is_gold"] is False
    assert out["promotion_guard"]["human_adjudicated"] is False
    assert out["promotion_guard"]["gold_promotion"] is False
    assert out["semantics"] == "candidate_only"
    # the external annotation is a review aid, never a mapped field
    assert "external_annotation" not in out["mapped_fields"]
    assert out["review_aids"] == [{"external_annotation": record[
        "external_annotation"]}]
    assert "external_annotation_review_aid_only" in out["warnings"]


# --- 7. legal synthetic conversion keeps provenance --------------------------


def test_legal_synthetic_candidate_keeps_field_provenance() -> None:
    out = _convert()
    assert out["status"] == "review_candidate"
    assert out["semantics"] == "candidate_only"
    assert out["mapped_fields"]["modality"] == "obligation"
    assert out["mapped_fields"]["condition"] == {"predicate": "x"}
    for sun_field in out["mapped_fields"]:
        prov = out["field_provenance"][sun_field]
        assert prov["source_element"] == "norms[0]"
        assert prov["source_path"] == "synthetic:rc4pc/syn-001"
        assert prov["source_record_id"] == "syn-001"
        assert prov["span"] == {"start": 0, "end": len(
            "the data subject shall be notified without undue delay")}
        assert prov["mapping_policy_id"] == "syn-policy-v1"


def test_unmapped_structure_fields_never_silently_converted() -> None:
    out = _convert()
    # 'norm' and 'temporal_validity' are NOT in the field mapping
    assert "norm" not in out["mapped_fields"]
    assert "temporal_validity" not in out["mapped_fields"]
    assert "unmapped_structure_field:norm" in out["warnings"]
    assert "unmapped_structure_field:temporal_validity" in out["warnings"]


def test_input_order_does_not_affect_canonical_output() -> None:
    record_a = _synthetic_record()
    record_b = _synthetic_record()
    record_b["structure"] = {"temporal_validity": {"start": "t0", "end": "t1"},
                             "norm": {"modality": "obligation"},
                             "precondition": {"predicate": "x"}}
    out_a = _convert(record_a)
    out_b = _convert(record_b)
    assert out_a == out_b


# --- 8. structure / unknown fields -------------------------------------------


def test_unknown_record_field_fails_closed() -> None:
    record = _synthetic_record(bogus_field="x")
    with pytest.raises(InvalidStructureError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "INVALID_STRUCTURE"
    assert "bogus_field" in exc.value.detail


def test_missing_required_key_fails_closed() -> None:
    record = _synthetic_record()
    del record["text_provenance"]
    with pytest.raises(InvalidStructureError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "INVALID_STRUCTURE"


# --- 9. real-world default states refuse -------------------------------------


def test_current_real_world_states_refuse_everything() -> None:
    # license unknown, activation not authorized, policy not approved:
    # the exact current project states -> every conversion is refused
    with pytest.raises(LicenseNotQualifiedError):
        _convert(license_state=LicenseState(),
                 activation_state=ActivationState(),
                 mapping_policy=_synthetic_policy(approved=False))
