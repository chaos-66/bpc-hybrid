"""Real-execution focused tests for the HARDENED G0.7 / S2.11 Barrientos
adapter core (synthetic/shadow implementation, v4 provenance model).

These tests CALL `src/bpc_hybrid/s2_11_barrientos_adapter.py` with synthetic
fixtures only; they never access, copy or execute real
`references/` data. Every fail-closed condition asserts a machine-decodable
error code; no assertion is ever vacuous (`or True` guards are forbidden).
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from bpc_hybrid.s2_11_barrientos_adapter import (
    ActivationNotAuthorizedError,
    ActivationState,
    BarrientosAdapterError,
    DefinitionNotProducibleError,
    ElementPathMismatchError,
    EvidenceBindingMissingError,
    EvidenceBindingSyntheticError,
    EvidenceBinding,
    FieldProvenanceMissingError,
    FieldSpanAmbiguousError,
    FieldSpanInvalidError,
    FieldValueMismatchError,
    InvalidMappedModalityError,
    InvalidStructureError,
    LicenseNotQualifiedError,
    LicenseState,
    MappingPolicy,
    MappingPolicyIncompleteError,
    MappingPolicyNotApprovedError,
    MissingSpanAlignmentError,
    MissingTextProvenanceError,
    NestedDictAsSpanFieldError,
    NonCanonicalTargetError,
    SyntheticPolicyInFormalModeError,
    TargetCollisionError,
    UnknownModalityError,
    UnresolvedCrossReferenceError,
    convert_to_candidate,
)

BARRIENTOS_CLASSES = ("obligation", "permission", "prohibition")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _element(value: Any, text: str, span: tuple[int, int],
             element: str = "norms[0].modality",
             path: str = "synthetic:rc4pc/syn-001") -> dict[str, Any]:
    start, end = span
    return {
        "value": value,
        "element": element,
        "path": path,
        "text_hash": _sha(text),
        "span": {"start": start, "end": end},
        "span_alignment_source": "approved_english_alignment",
    }


def _synthetic_policy(approved: bool = True,
                      synthetic_test_only: bool = True,
                      identity: dict[str, str] | None = None,
                      fields: dict[str, str] | None = None,
                      license_binding: EvidenceBinding | None = None,
                      auth_binding: EvidenceBinding | None = None
                      ) -> MappingPolicy:
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
        license_evidence_binding=license_binding,
        authorization_manifest_binding=auth_binding,
    )


def _synthetic_record(modality: str = "obligation", *,
                      text: str = "the data subject shall be notified "
                                  "without undue delay",
                      **overrides: Any) -> dict:
    record: dict[str, Any] = {
        "source_record_id": "syn-001",
        "source_path": "synthetic:rc4pc/syn-001",
        "modality": _element(modality, text, (0, len(text)),
                             element="norms[0].modality"),
        "text": text,
        "text_provenance": {"sha256": _sha(text), "language": "en"},
        "structure": {
            "precondition": _element("the data subject", text, (0, 16),
                                     element="precondition",
                                     path="synthetic:rc4pc/syn-001"),
            "norm": _element("shall be notified", text, (17, 34),
                             element="norm",
                             path="synthetic:rc4pc/syn-001"),
            "temporal_validity": _element("without undue delay", text,
                                          (35, len(text)),
                                          element="temporal_validity",
                                          path="synthetic:rc4pc/syn-001"),
        },
        "cross_references": [{"ref_id": "art-7", "resolved": True}],
    }
    record.update(overrides)
    return record


def _qualified_license() -> LicenseState:
    return LicenseState(qualified=True, license_status="qualified")


def _authorized_activation() -> ActivationState:
    return ActivationState(authorized=True)


def _synthetic_bindings() -> tuple[EvidenceBinding, EvidenceBinding]:
    return (EvidenceBinding(kind="license", evidence_id="syn-lic-1",
                            evidence_hash=_sha("lic"), synthetic=True),
            EvidenceBinding(kind="authorization", evidence_id="syn-auth-1",
                            evidence_hash=_sha("auth"), synthetic=True))


def _real_bindings() -> tuple[EvidenceBinding, EvidenceBinding]:
    # Test-only NON-synthetic bindings for the future formal path fixture.
    return (EvidenceBinding(kind="license", evidence_id="lic-1",
                            evidence_hash=_sha("lic")),
            EvidenceBinding(kind="authorization", evidence_id="auth-1",
                            evidence_hash=_sha("auth")))


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
    with pytest.raises(MappingPolicyNotApprovedError):
        _convert(_synthetic_record(modality=cls),
                 mapping_policy=_synthetic_policy(approved=False))
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


def test_modality_provenance_must_point_at_norm_element() -> None:
    record = _synthetic_record()
    record["modality"] = _element("obligation", record["text"],
                                  (0, len(record["text"])),
                                  element="structure.root")
    with pytest.raises(ElementPathMismatchError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "ELEMENT_PATH_MISMATCH"


# --- 3. text / record provenance ---------------------------------------------


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


# --- 4. field-level provenance and canonical targets -------------------------


def test_non_canonical_target_fails_closed() -> None:
    policy = _synthetic_policy(fields={"precondition": "modality"})
    with pytest.raises(NonCanonicalTargetError) as exc:
        _convert(mapping_policy=policy)
    assert _error_code(exc.value) == "NON_CANONICAL_TARGET"


def test_non_canonical_target_bogus_fails_closed() -> None:
    policy = _synthetic_policy(fields={"precondition": "bogus_field"})
    with pytest.raises(NonCanonicalTargetError) as exc:
        _convert(mapping_policy=policy)
    assert _error_code(exc.value) == "NON_CANONICAL_TARGET"


def test_duplicate_target_collision_fails_closed() -> None:
    policy = _synthetic_policy(fields={"precondition": "condition",
                                       "norm": "condition"})
    with pytest.raises(TargetCollisionError) as exc:
        _convert(mapping_policy=policy)
    assert _error_code(exc.value) == "TARGET_COLLISION"
    assert "condition" in exc.value.detail


def test_field_without_provenance_fails_closed() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"] = "bare value"
    with pytest.raises(FieldProvenanceMissingError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "FIELD_PROVENANCE_MISSING"


def test_field_missing_span_fails_closed() -> None:
    record = _synthetic_record()
    del record["structure"]["precondition"]["span"]
    with pytest.raises(FieldProvenanceMissingError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "FIELD_PROVENANCE_MISSING"


def test_field_span_out_of_bounds_fails_closed() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"]["span"] = {"start": 0, "end": 9999}
    with pytest.raises(FieldSpanInvalidError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "FIELD_SPAN_INVALID"


def test_field_span_empty_fails_closed() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"]["span"] = {"start": 16, "end": 16}
    with pytest.raises(FieldSpanInvalidError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "FIELD_SPAN_INVALID"


def test_field_span_ambiguous_fails_closed() -> None:
    text = "the data subject shall be notified, the data subject shall be"
    record = _synthetic_record(text=text)
    record["structure"]["precondition"] = _element(
        "the data subject", text, (0, 16), element="precondition")
    with pytest.raises(FieldSpanAmbiguousError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "FIELD_SPAN_AMBIGUOUS"


def test_field_value_mismatch_fails_closed() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"]["value"] = "the controller"
    with pytest.raises(FieldValueMismatchError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "FIELD_VALUE_MISMATCH"


def test_nested_dict_as_span_field_fails_closed() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"]["value"] = {
        "and": [{"predicate": "x"}]}
    with pytest.raises(NestedDictAsSpanFieldError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "NESTED_DICT_AS_SPAN_FIELD"


def test_element_path_hash_mismatch_fails_closed() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"]["text_hash"] = "00" * 64
    with pytest.raises(ElementPathMismatchError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "ELEMENT_PATH_MISMATCH"


def test_field_span_external_offsets_fail_closed() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"]["span_alignment_source"] = \
        "external_offsets"
    with pytest.raises(MissingSpanAlignmentError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "MISSING_SPAN_ALIGNMENT"


# --- 5. cross references -----------------------------------------------------


def test_unresolved_cross_reference_refuses() -> None:
    record = _synthetic_record(cross_references=[
        {"ref_id": "art-7", "resolved": True},
        {"ref_id": "art-22", "resolved": False}])
    with pytest.raises(UnresolvedCrossReferenceError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "UNRESOLVED_CROSS_REFERENCE"


# --- 6. synthetic policy / formal mode / evidence bindings -------------------


def test_synthetic_policy_never_enters_formal_mode() -> None:
    lic, auth = _synthetic_bindings()
    policy = _synthetic_policy(license_binding=lic, auth_binding=auth)
    with pytest.raises(SyntheticPolicyInFormalModeError) as exc:
        _convert(mode="formal", mapping_policy=policy)
    assert _error_code(exc.value) == "SYNTHETIC_POLICY_IN_FORMAL_MODE"


def test_formal_mode_requires_evidence_bindings() -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    with pytest.raises(EvidenceBindingMissingError) as exc:
        _convert(mode="formal", mapping_policy=policy)
    assert _error_code(exc.value) == "EVIDENCE_BINDING_MISSING"


def test_formal_mode_rejects_synthetic_bindings() -> None:
    lic, auth = _synthetic_bindings()
    policy = _synthetic_policy(synthetic_test_only=False,
                               license_binding=lic, auth_binding=auth)
    with pytest.raises(EvidenceBindingSyntheticError) as exc:
        _convert(mode="formal", mapping_policy=policy)
    assert _error_code(exc.value) == "EVIDENCE_BINDING_SYNTHETIC"


def test_formal_mode_accepts_nonsynthetic_bindings_fixture() -> None:
    # Future formal path fixture: non-synthetic test bindings + a real
    # non-synthetic policy allow conversion (this does NOT change the real
    # disk state; no such evidence exists in the project today).
    lic, auth = _real_bindings()
    policy = _synthetic_policy(synthetic_test_only=False,
                               license_binding=lic, auth_binding=auth)
    out = _convert(mode="formal", mapping_policy=policy)
    assert out["semantics"] == "candidate_only"
    assert out["is_gold"] is False


# --- 7. external labels never Gold -------------------------------------------


def test_external_labels_never_auto_promoted_to_gold() -> None:
    record = _synthetic_record(external_annotation={
        "modality": "obligation", "origin": "external ground truth"})
    out = _convert(record)
    assert out["is_gold"] is False
    assert out["promotion_guard"]["human_adjudicated"] is False
    assert out["promotion_guard"]["gold_promotion"] is False
    assert out["semantics"] == "candidate_only"
    assert "external_annotation" not in out["mapped_fields"]
    assert out["review_aids"] == [{"external_annotation": record[
        "external_annotation"]}]
    assert "external_annotation_review_aid_only" in out["warnings"]


# --- 8. legal synthetic conversion: field-level provenance -------------------


def test_legal_synthetic_candidate_keeps_field_level_provenance() -> None:
    out = _convert()
    assert out["status"] == "review_candidate"
    assert out["mapped_fields"]["modality"] == "obligation"
    assert out["mapped_fields"]["condition"] == "the data subject"
    # modality provenance points at the norm modality element
    mod_prov = out["field_provenance"]["modality"]
    assert mod_prov["source_element"] == "norms[0].modality"
    assert mod_prov["span"] == {"start": 0, "end": 54}
    # structural field provenance uses ITS OWN element/span, not the
    # modality/record-global span
    cond_prov = out["field_provenance"]["condition"]
    assert cond_prov["source_element"] == "precondition"
    assert cond_prov["source_path"] == "synthetic:rc4pc/syn-001"
    assert cond_prov["source_record_id"] == "syn-001"
    assert cond_prov["source_text_hash"] == _sha(
        "the data subject shall be notified without undue delay")
    assert cond_prov["span"] == {"start": 0, "end": 16}
    assert cond_prov["span_alignment_source"] == \
        "approved_english_alignment"
    assert cond_prov["mapping_policy_id"] == "syn-policy-v1"
    # the structural span must differ from the modality span (separate)
    assert cond_prov["span"] != mod_prov["span"]


def test_modality_only_mapping_when_no_field_policy() -> None:
    # M1 scope: without an approved field mapping policy the output
    # contains ONLY the modality candidate; structure stays blank.
    policy = _synthetic_policy(fields={})
    out = _convert(mapping_policy=policy)
    assert set(out["mapped_fields"]) == {"modality"}
    assert set(out["field_provenance"]) == {"modality"}
    assert "unmapped_structure_field:precondition" in out["warnings"]
    assert "unmapped_structure_field:norm" in out["warnings"]
    assert "unmapped_structure_field:temporal_validity" in out["warnings"]


def test_unmapped_structure_fields_never_silently_converted() -> None:
    out = _convert()
    assert "norm" not in out["mapped_fields"]
    assert "temporal_validity" not in out["mapped_fields"]
    assert "unmapped_structure_field:norm" in out["warnings"]
    assert "unmapped_structure_field:temporal_validity" in out["warnings"]


def test_input_order_does_not_affect_canonical_output() -> None:
    record_a = _synthetic_record()
    record_b = _synthetic_record()
    structure = record_b["structure"]
    record_b["structure"] = {
        "temporal_validity": structure["temporal_validity"],
        "norm": structure["norm"],
        "precondition": structure["precondition"],
    }
    assert _convert(record_a) == _convert(record_b)


# --- 9. structure / unknown fields -------------------------------------------


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


def test_modality_span_out_of_bounds_fails_closed() -> None:
    text = "the data subject shall be notified without undue delay"
    record = _synthetic_record(text=text)
    record["modality"] = _element("obligation", text, (0, 9999),
                                  element="norms[0].modality")
    with pytest.raises(FieldSpanInvalidError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "FIELD_SPAN_INVALID"


# --- 10. real-world default states refuse ------------------------------------


def test_current_real_world_states_refuse_everything() -> None:
    with pytest.raises(LicenseNotQualifiedError):
        _convert(license_state=LicenseState(),
                 activation_state=ActivationState(),
                 mapping_policy=_synthetic_policy(approved=False))
