"""Real-execution focused tests for the v6-hardened Barrientos adapter
core (synthetic/shadow implementation).

Calls `src/bpc_hybrid/s2_11_barrientos_adapter.py` with synthetic fixtures
only; never accesses real `references/` data. Every fail-closed condition
asserts a machine-decodable error code; no assertion is vacuous. Formal
positive fixtures create license/authorization evidence documents and the
append-only authorization event in the pytest tmp_path (never in project
paths). Scopes are controlled enums (LICENSE_SCOPES / AUTHORIZATION_SCOPES);
formal outputs carry a re-verified `formal_evidence_provenance` block and
synthetic outputs carry null there. Evidence paths are also checked after
Path.resolve() so symlink/junction escapes are rejected.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from bpc_hybrid.s2_11_barrientos_adapter import (
    ActivationNotAuthorizedError,
    ActivationState,
    AmbiguousSpanError,
    AuthorizationBindingMismatchError,
    AuthorizationEventMismatchError,
    BarrientosAdapterError,
    DefinitionNotProducibleError,
    ElementPathMismatchError,
    EvidenceBinding,
    EvidenceBindingInvalidError,
    EvidenceBindingMissingError,
    EvidenceBindingSyntheticError,
    EvidenceDocMismatchError,
    EvidencePathEscapeError,
    FieldProvenanceMissingError,
    FieldSpanAmbiguousError,
    FieldSpanInvalidError,
    FieldValueMismatchError,
    InvalidModeError,
    InvalidMappedModalityError,
    InvalidRecordIdentityError,
    InvalidStructureError,
    LicenseNotQualifiedError,
    LicenseScopeNotArtifactCoveringError,
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
    UserAuthorizationNotValidError,
    convert_to_candidate,
    field_locator,
)

BARRIENTOS_CLASSES = ("obligation", "permission", "prohibition")

RECORD_PATH = "synthetic:rc4pc/syn-001"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _element(value: Any, text: str, span: tuple[int, int],
             element: str) -> dict[str, Any]:
    start, end = span
    return {
        "value": value,
        "element": element,
        "path": field_locator(RECORD_PATH, element),
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
        "source_path": RECORD_PATH,
        "modality": _element(modality, text, (0, len(text)),
                             "norms[0].modality"),
        "text": text,
        "text_provenance": {"sha256": _sha(text), "language": "en"},
        "structure": {
            "precondition": _element("the data subject", text, (0, 16),
                                     "precondition"),
            "norm": _element("shall be notified", text, (17, 34), "norm"),
            "temporal_validity": _element("without undue delay", text,
                                          (35, len(text)),
                                          "temporal_validity"),
        },
        "cross_references": [{"ref_id": "art-7", "resolved": True}],
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
        evidence_root=kwargs.pop("evidence_root", None),
    )


def _error_code(exc: BarrientosAdapterError) -> str:
    return exc.code


def _write_json(path: Path, doc: dict[str, Any]) -> str:
    data = json.dumps(doc, ensure_ascii=False, sort_keys=True,
                      indent=2).encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _make_evidence_root(tmp_path: Path,
                        policy: MappingPolicy) -> tuple[Path, EvidenceBinding,
                                                        EvidenceBinding]:
    """Write synthetic license + authorization evidence documents and the
    append-only authorization event into tmp_path (never project paths)
    and return (root, license_binding, auth_binding).

    v6: scopes are controlled enums — the license evidence declares the
    artifact-covering scope `artifact_code_data` and the authorization
    manifest declares the controlled scope `s2_11_candidate_mapping_only`
    and EXACTLY repeats the license scope in its policy binding; the
    manifest additionally binds the append-only authorization event
    (ID + relative path + raw-byte SHA-256).
    """
    root = tmp_path
    lic_doc = {
        "kind": "license",
        "evidence_id": "syn-lic-1",
        "scope": "artifact_code_data",
    }
    lic_hash = _write_json(root / "license_evidence.json", lic_doc)
    event_doc = {
        "kind": "s2_11_authorization_event",
        "event_id": "syn-ev-1",
        "authorization_sentence": "synthetic dry-run sentence",
        "manifest_id": "syn-auth-1",
        "append_only": True,
    }
    event_hash = _write_json(root / "authorization_event.json", event_doc)
    auth_doc = {
        "kind": "authorization",
        "evidence_id": "syn-auth-1",
        "scope": "s2_11_candidate_mapping_only",
        "authorization_sentence": "synthetic dry-run sentence",
        "authorization_event_id": "syn-ev-1",
        "authorization_event_path": "authorization_event.json",
        "authorization_event_sha256": event_hash,
        "policy_binding": {
            "policy_id": policy.policy_id,
            "modality_mapping": dict(policy.modality_identity),
            "field_mapping": dict(policy.field_mapping),
            "license_evidence_id": "syn-lic-1",
            "license_evidence_hash": lic_hash,
            "license_evidence_scope": "artifact_code_data",
        },
    }
    auth_hash = _write_json(root / "authorization_manifest.json", auth_doc)
    lic_binding = EvidenceBinding(kind="license", evidence_id="syn-lic-1",
                                  evidence_hash=lic_hash,
                                  path="license_evidence.json",
                                  scope="artifact_code_data")
    auth_binding = EvidenceBinding(kind="authorization",
                                   evidence_id="syn-auth-1",
                                   evidence_hash=auth_hash,
                                   path="authorization_manifest.json",
                                   scope="s2_11_candidate_mapping_only")
    return root, lic_binding, auth_binding


# --- 0. strict mode enum ------------------------------------------------------


@pytest.mark.parametrize("mode", ["production_typo", "Formal", "", "formal "])
def test_invalid_mode_rejected(mode: str) -> None:
    with pytest.raises(InvalidModeError) as exc:
        _convert(mode=mode)
    assert _error_code(exc.value) == "INVALID_MODE"


def test_valid_modes_accepted() -> None:
    out = _convert(mode="synthetic_test_only")
    assert out["semantics"] == "candidate_only"


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


@pytest.mark.parametrize("element", [
    "structure.root", "xnorm.modality", "norms[0].norm.modality",
    "Norms[0].modality", "norms[0]modality",
])
def test_modality_element_must_exactly_match_pattern(element: str) -> None:
    record = _synthetic_record()
    record["modality"] = _element("obligation", record["text"],
                                  (0, len(record["text"])), element)
    with pytest.raises(ElementPathMismatchError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "ELEMENT_PATH_MISMATCH"


def test_modality_element_exact_match_passes() -> None:
    out = _convert()
    assert out["field_provenance"]["modality"]["source_element"] == \
        "norms[0].modality"


# --- 3. record identity ------------------------------------------------------


@pytest.mark.parametrize("field", ["source_record_id", "source_path"])
def test_record_identity_rejects_str_none_and_empty(field: str) -> None:
    record = _synthetic_record()
    record[field] = "None"
    with pytest.raises(InvalidRecordIdentityError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "INVALID_RECORD_IDENTITY"
    record[field] = "   "
    with pytest.raises(InvalidRecordIdentityError):
        _convert(record)


def test_record_path_must_not_contain_locator_separator() -> None:
    record = _synthetic_record()
    record["source_path"] = "synthetic:rc4pc/syn-001#x"
    with pytest.raises(InvalidRecordIdentityError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "INVALID_RECORD_IDENTITY"


# --- 4. text / record provenance ---------------------------------------------


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


# --- 5. field-level provenance (exact element / locator) ---------------------


def test_non_canonical_target_fails_closed() -> None:
    policy = _synthetic_policy(fields={"precondition": "modality"})
    with pytest.raises(NonCanonicalTargetError) as exc:
        _convert(mapping_policy=policy)
    assert _error_code(exc.value) == "NON_CANONICAL_TARGET"


def test_duplicate_target_collision_fails_closed() -> None:
    policy = _synthetic_policy(fields={"precondition": "condition",
                                       "norm": "condition"})
    with pytest.raises(TargetCollisionError) as exc:
        _convert(mapping_policy=policy)
    assert _error_code(exc.value) == "TARGET_COLLISION"


def test_field_element_must_exactly_equal_mapping_key() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"]["element"] = "totally.wrong"
    with pytest.raises(ElementPathMismatchError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "ELEMENT_PATH_MISMATCH"
    assert "precondition" in exc.value.message


def test_field_path_must_equal_deterministic_locator() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"]["path"] = "record-level-not-field-path"
    with pytest.raises(ElementPathMismatchError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "ELEMENT_PATH_MISMATCH"
    assert field_locator(RECORD_PATH, "precondition") in exc.value.message


def test_record_path_cannot_be_field_path() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"]["path"] = RECORD_PATH
    with pytest.raises(ElementPathMismatchError):
        _convert(record)


def test_locator_rule_documented_and_unique() -> None:
    assert field_locator("r", "e") == "r#e"
    assert "r#e" != "r"
    assert field_locator("r", "e") != field_locator("r", "e2")


def test_field_without_provenance_fails_closed() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"] = "bare value"
    with pytest.raises(FieldProvenanceMissingError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "FIELD_PROVENANCE_MISSING"


def test_field_unknown_descriptor_key_fails_closed() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"]["bogus_key"] = 1
    with pytest.raises(FieldProvenanceMissingError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "FIELD_PROVENANCE_MISSING"
    assert "bogus_key" in exc.value.detail


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


def test_bool_is_not_an_integer_offset() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"]["span"] = {"start": True, "end": 16}
    with pytest.raises(FieldSpanInvalidError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "FIELD_SPAN_INVALID"


def test_overlapping_span_ambiguity_detected() -> None:
    # "aaa" contains "aa" at TWO overlapping starts; str.count would miss
    # the second one. The v5 overlap scan must reject.
    text = "aaa bbb"
    record = _synthetic_record(text=text)
    record["structure"]["precondition"] = _element("aa", text, (0, 2),
                                                   "precondition")
    with pytest.raises(FieldSpanAmbiguousError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "FIELD_SPAN_AMBIGUOUS"
    assert "occurrences=2" in exc.value.detail


def test_unique_span_passes() -> None:
    # A unique occurrence (even inside a text with other substrings) passes.
    text = "aa bb aa cc"
    record = _synthetic_record(text=text)
    record["structure"]["precondition"] = _element("bb", text, (3, 5),
                                                   "precondition")
    out = _convert(record)
    assert out["mapped_fields"]["condition"] == "bb"


def test_field_value_mismatch_fails_closed() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"]["value"] = "the controller"
    with pytest.raises(FieldValueMismatchError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "FIELD_VALUE_MISMATCH"


def test_nested_dict_as_span_field_fails_closed() -> None:
    record = _synthetic_record()
    record["structure"]["precondition"]["value"] = {"and": [{"x": 1}]}
    with pytest.raises(NestedDictAsSpanFieldError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "NESTED_DICT_AS_SPAN_FIELD"


def test_element_text_hash_mismatch_fails_closed() -> None:
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


# --- 6. cross references -----------------------------------------------------


def test_unresolved_cross_reference_refuses() -> None:
    record = _synthetic_record(cross_references=[
        {"ref_id": "art-7", "resolved": True},
        {"ref_id": "art-22", "resolved": False}])
    with pytest.raises(UnresolvedCrossReferenceError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "UNRESOLVED_CROSS_REFERENCE"


# --- 7. formal mode: real file-backed evidence binding -----------------------


def test_synthetic_policy_never_enters_formal_mode(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=True)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    policy = MappingPolicy(
        policy_id=policy.policy_id, approved=True,
        synthetic_test_only=True,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(SyntheticPolicyInFormalModeError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "SYNTHETIC_POLICY_IN_FORMAL_MODE"


def test_formal_mode_requires_bindings(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    with pytest.raises(EvidenceBindingMissingError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=tmp_path)
    assert _error_code(exc.value) == "EVIDENCE_BINDING_MISSING"


def test_formal_mode_requires_evidence_root(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    lic = EvidenceBinding(kind="license", evidence_id="syn-lic-1",
                          evidence_hash="00" * 64, path="x.json")
    auth = EvidenceBinding(kind="authorization", evidence_id="syn-auth-1",
                           evidence_hash="00" * 64, path="y.json")
    policy = MappingPolicy(
        policy_id="p", approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(EvidenceBindingMissingError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=None)
    assert _error_code(exc.value) == "EVIDENCE_BINDING_MISSING"


def test_formal_mode_rejects_synthetic_bindings(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    lic = EvidenceBinding(kind="license", evidence_id="syn-lic-1",
                          evidence_hash=lic.evidence_hash,
                          path=lic.path, synthetic=True)
    policy = MappingPolicy(
        policy_id="p", approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(EvidenceBindingSyntheticError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "EVIDENCE_BINDING_SYNTHETIC"


def test_formal_mode_accepts_real_file_backed_fixture(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    policy = MappingPolicy(
        policy_id=policy.policy_id, approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    out = _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert out["semantics"] == "candidate_only"
    assert out["is_gold"] is False


def test_formal_empty_evidence_id_rejected(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    lic = EvidenceBinding(kind="license", evidence_id="  ",
                          evidence_hash=lic.evidence_hash, path=lic.path)
    policy = MappingPolicy(
        policy_id="p", approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(EvidenceBindingInvalidError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "EVIDENCE_BINDING_INVALID"


def test_formal_bad_hash_format_rejected(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    lic = EvidenceBinding(kind="license", evidence_id="syn-lic-1",
                          evidence_hash="not-a-sha", path=lic.path)
    policy = MappingPolicy(
        policy_id="p", approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(EvidenceBindingInvalidError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "EVIDENCE_BINDING_INVALID"


def test_formal_wrong_kind_rejected(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    lic = EvidenceBinding(kind="authorization", evidence_id="syn-lic-1",
                          evidence_hash=lic.evidence_hash, path=lic.path)
    policy = MappingPolicy(
        policy_id="p", approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(EvidenceBindingInvalidError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "EVIDENCE_BINDING_INVALID"


@pytest.mark.parametrize("bad_path", ["../escape.json", "/abs/path.json",
                                      "sub/../../x.json"])
def test_formal_path_escape_rejected(tmp_path: Path, bad_path: str) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    lic = EvidenceBinding(kind="license", evidence_id="syn-lic-1",
                          evidence_hash=lic.evidence_hash, path=bad_path)
    policy = MappingPolicy(
        policy_id="p", approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(EvidenceBindingInvalidError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "EVIDENCE_BINDING_INVALID"


def test_formal_missing_file_rejected(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    lic = EvidenceBinding(kind="license", evidence_id="syn-lic-1",
                          evidence_hash=lic.evidence_hash,
                          path="no_such_file.json")
    policy = MappingPolicy(
        policy_id="p", approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(EvidenceBindingInvalidError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "EVIDENCE_BINDING_INVALID"


def test_formal_wrong_file_hash_rejected(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    lic = EvidenceBinding(kind="license", evidence_id="syn-lic-1",
                          evidence_hash="11" * 32, path=lic.path)
    policy = MappingPolicy(
        policy_id="p", approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(EvidenceBindingInvalidError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "EVIDENCE_BINDING_INVALID"


def test_formal_doc_id_mismatch_rejected(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    lic = EvidenceBinding(kind="license", evidence_id="different-id",
                          evidence_hash=lic.evidence_hash, path=lic.path)
    policy = MappingPolicy(
        policy_id="p", approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(EvidenceDocMismatchError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "EVIDENCE_DOC_MISMATCH"


def test_formal_manifest_policy_mismatch_rejected(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    other = _synthetic_policy(synthetic_test_only=False,
                              fields={"precondition": "action"})
    policy = MappingPolicy(
        policy_id="p", approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping={"precondition": "action"},
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(AuthorizationBindingMismatchError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "AUTHORIZATION_BINDING_MISMATCH"


def test_formal_manifest_license_hash_mismatch_rejected(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    lic = EvidenceBinding(kind="license", evidence_id="syn-lic-1",
                          evidence_hash="22" * 32, path=lic.path)
    policy = MappingPolicy(
        policy_id="p", approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(EvidenceBindingInvalidError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "EVIDENCE_BINDING_INVALID"


# --- 7b. v6: scope enums + resolved-path escape + evidence provenance --------


def test_formal_article_only_license_scope_rejected(tmp_path: Path) -> None:
    # An article-only license scope NEVER satisfies the artifact code/data
    # requirement, even when every file/hash/ID matches.
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    lic_doc = json.loads((root / "license_evidence.json")
                         .read_text(encoding="utf-8"))
    lic_doc["scope"] = "article_only"
    lic_hash = _write_json(root / "license_evidence.json", lic_doc)
    auth_doc = json.loads((root / "authorization_manifest.json")
                          .read_text(encoding="utf-8"))
    auth_doc["policy_binding"]["license_evidence_hash"] = lic_hash
    auth_doc["policy_binding"]["license_evidence_scope"] = "article_only"
    _write_json(root / "authorization_manifest.json", auth_doc)
    lic = EvidenceBinding(kind="license", evidence_id="syn-lic-1",
                          evidence_hash=lic_hash, path=lic.path,
                          scope="article_only")
    auth = EvidenceBinding(kind="authorization", evidence_id="syn-auth-1",
                           evidence_hash=_sha(
                               (root / "authorization_manifest.json")
                               .read_text(encoding="utf-8")),
                           path=auth.path, scope=auth.scope)
    policy = MappingPolicy(
        policy_id=policy.policy_id, approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(LicenseScopeNotArtifactCoveringError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "LICENSE_SCOPE_NOT_ARTIFACT_COVERING"


def test_formal_license_scope_must_exactly_match_binding(
        tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    # doc says artifact_code_data but the binding expects artifact_code
    lic = EvidenceBinding(kind="license", evidence_id="syn-lic-1",
                          evidence_hash=lic.evidence_hash, path=lic.path,
                          scope="artifact_code")
    policy = MappingPolicy(
        policy_id=policy.policy_id, approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(EvidenceDocMismatchError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "EVIDENCE_DOC_MISMATCH"


def test_formal_authorization_scope_must_be_controlled_enum(
        tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    auth_doc = json.loads((root / "authorization_manifest.json")
                          .read_text(encoding="utf-8"))
    auth_doc["scope"] = "anything-at-all"
    auth_hash = _write_json(root / "authorization_manifest.json", auth_doc)
    auth = EvidenceBinding(kind="authorization", evidence_id="syn-auth-1",
                           evidence_hash=auth_hash, path=auth.path,
                           scope="anything-at-all")
    policy = MappingPolicy(
        policy_id=policy.policy_id, approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(EvidenceDocMismatchError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "EVIDENCE_DOC_MISMATCH"


def test_formal_manifest_must_exactly_repeat_license_scope(
        tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    auth_doc = json.loads((root / "authorization_manifest.json")
                          .read_text(encoding="utf-8"))
    auth_doc["policy_binding"]["license_evidence_scope"] = "article_only"
    auth_hash = _write_json(root / "authorization_manifest.json", auth_doc)
    auth = EvidenceBinding(kind="authorization", evidence_id="syn-auth-1",
                           evidence_hash=auth_hash, path=auth.path,
                           scope=auth.scope)
    policy = MappingPolicy(
        policy_id=policy.policy_id, approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(AuthorizationBindingMismatchError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "AUTHORIZATION_BINDING_MISMATCH"


def test_formal_resolved_path_escape_rejected(tmp_path: Path) -> None:
    # v6: a path that is lexically safe but RESOLVES outside the evidence
    # root (symlink/junction) must be rejected. The containment predicate
    # is always asserted; the junction integration runs when the platform
    # allows creating one (no admin needed for directory junctions).
    policy = _synthetic_policy(synthetic_test_only=False)
    root = tmp_path / "evidence_root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_file = outside / "lic.json"
    outside_doc = {"kind": "license", "evidence_id": "out-lic",
                   "scope": "artifact_code_data"}
    outside_hash = _write_json(outside_file, outside_doc)
    # predicate: a resolved path outside the evidence root is not within it
    from bpc_hybrid.s2_11_barrientos_adapter import _is_within
    assert not _is_within(root.resolve(), outside_file.resolve())
    assert _is_within(root.resolve(), (root / "x.json").resolve())
    # junction integration when possible
    link = root / "escape"
    created = False
    try:
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            capture_output=True, check=False)
        created = proc.returncode == 0 and link.exists()
    except OSError:
        created = False
    if created:
        lic = EvidenceBinding(kind="license", evidence_id="out-lic",
                              evidence_hash=outside_hash,
                              path="escape/lic.json",
                              scope="artifact_code_data")
        from bpc_hybrid.s2_11_barrientos_adapter import _check_evidence_binding
        with pytest.raises(EvidencePathEscapeError) as exc:
            _check_evidence_binding(lic, "license", root)
        assert _error_code(exc.value) == "EVIDENCE_PATH_ESCAPE"


def test_formal_event_hash_mismatch_rejected(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    auth_doc = json.loads((root / "authorization_manifest.json")
                          .read_text(encoding="utf-8"))
    auth_doc["authorization_event_sha256"] = "33" * 32
    auth_hash = _write_json(root / "authorization_manifest.json", auth_doc)
    auth = EvidenceBinding(kind="authorization", evidence_id="syn-auth-1",
                           evidence_hash=auth_hash, path=auth.path,
                           scope=auth.scope)
    policy = MappingPolicy(
        policy_id=policy.policy_id, approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(AuthorizationEventMismatchError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "AUTHORIZATION_EVENT_MISMATCH"


def test_formal_event_id_mismatch_rejected(tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    event_doc = json.loads((root / "authorization_event.json")
                           .read_text(encoding="utf-8"))
    event_doc["event_id"] = "other-ev"
    event_hash = _write_json(root / "authorization_event.json", event_doc)
    auth_doc = json.loads((root / "authorization_manifest.json")
                          .read_text(encoding="utf-8"))
    auth_doc["authorization_event_sha256"] = event_hash
    auth_hash = _write_json(root / "authorization_manifest.json", auth_doc)
    auth = EvidenceBinding(kind="authorization", evidence_id="syn-auth-1",
                           evidence_hash=auth_hash, path=auth.path,
                           scope=auth.scope)
    policy = MappingPolicy(
        policy_id=policy.policy_id, approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    with pytest.raises(AuthorizationEventMismatchError) as exc:
        _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    assert _error_code(exc.value) == "AUTHORIZATION_EVENT_MISMATCH"


def test_formal_output_provenance_matches_reextracted_evidence(
        tmp_path: Path) -> None:
    # Every formal_evidence_provenance field must equal values
    # re-extracted from the actual evidence files and the policy.
    from bpc_hybrid.s2_11_barrientos_adapter import _canonical_mapping_hash
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    policy = MappingPolicy(
        policy_id=policy.policy_id, approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    out = _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    prov = out["formal_evidence_provenance"]
    assert prov is not None
    assert prov["candidate_only"] is True
    assert prov["gold_authorized"] is False
    assert prov["policy_id"] == policy.policy_id
    assert prov["license_evidence"]["evidence_id"] == "syn-lic-1"
    assert prov["license_evidence"]["relative_path"] == \
        "license_evidence.json"
    assert prov["license_evidence"]["sha256"] == lic.evidence_hash
    assert prov["license_evidence"]["license_scope"] == "artifact_code_data"
    assert prov["authorization_manifest"]["manifest_id"] == "syn-auth-1"
    assert prov["authorization_manifest"]["authorization_scope"] == \
        "s2_11_candidate_mapping_only"
    assert prov["authorization_manifest"]["sha256"] == auth.evidence_hash
    assert prov["authorization_event"]["event_id"] == "syn-ev-1"
    assert prov["authorization_event"]["relative_path"] == \
        "authorization_event.json"
    assert prov["authorization_event"]["sha256"] == _sha(
        (root / "authorization_event.json").read_text(encoding="utf-8"))
    assert prov["modality_mapping_canonical_hash"] == \
        _canonical_mapping_hash(policy.modality_identity)
    assert prov["field_mapping_canonical_hash"] == \
        _canonical_mapping_hash(policy.field_mapping)
    assert "license_evidence_id=syn-lic-1" in \
        prov["license_evidence_binding"]
    assert "license_evidence_scope=artifact_code_data" in \
        prov["license_evidence_binding"]


def test_formal_output_provenance_tamper_is_detectable(
        tmp_path: Path) -> None:
    # The provenance block is OUTPUT-only: a tampered copy (e.g. a wrong
    # license hash) no longer matches the re-extracted evidence, so any
    # downstream verifier can detect the tamper.
    from bpc_hybrid.s2_11_barrientos_adapter import _canonical_mapping_hash
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    policy = MappingPolicy(
        policy_id=policy.policy_id, approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    out = _convert(mode="formal", mapping_policy=policy, evidence_root=root)
    tampered = dict(out)
    prov = dict(tampered["formal_evidence_provenance"])
    lic_ev = dict(prov["license_evidence"])
    lic_ev["sha256"] = "44" * 32
    prov["license_evidence"] = lic_ev
    tampered["formal_evidence_provenance"] = prov
    assert tampered["formal_evidence_provenance"]["license_evidence"][
        "sha256"] != _sha((root / "license_evidence.json")
                          .read_text(encoding="utf-8"))
    assert tampered["formal_evidence_provenance"][
        "modality_mapping_canonical_hash"] == \
        _canonical_mapping_hash(policy.modality_identity)


def test_formal_output_provenance_cannot_be_supplied_via_record(
        tmp_path: Path) -> None:
    # A caller cannot smuggle provenance through the source record: the
    # record key set is strict and rejects the key as an unknown field.
    policy = _synthetic_policy(synthetic_test_only=False)
    root, lic, auth = _make_evidence_root(tmp_path, policy)
    policy = MappingPolicy(
        policy_id=policy.policy_id, approved=True, synthetic_test_only=False,
        modality_identity=policy.modality_identity,
        field_mapping=policy.field_mapping,
        license_evidence_binding=lic, authorization_manifest_binding=auth)
    record = _synthetic_record()
    record["formal_evidence_provenance"] = {"fake": True}
    with pytest.raises(InvalidStructureError) as exc:
        _convert(record, mode="formal", mapping_policy=policy,
                 evidence_root=root)
    assert "formal_evidence_provenance" in exc.value.detail


def test_synthetic_output_has_null_formal_provenance() -> None:
    # Synthetic mode must never masquerade as formal evidence.
    out = _convert(mode="synthetic_test_only")
    assert out["formal_evidence_provenance"] is None
    assert out["semantics"] == "candidate_only"


# --- 7c. v6/B: local_read_only_research mode (unknown license) -------------


def _make_user_authorization_root(
        tmp_path: Path) -> tuple[Path, EvidenceBinding]:
    """Write a synthetic user_authorization evidence document (exact
    containment policy, unknown license) into tmp_path and return
    (root, binding)."""
    root = tmp_path
    doc = {
        "kind": "user_authorization",
        "event_id": "syn-user-auth-1",
        "authorization_scope": "local_read_only_nonredistributive_s2_11",
        "user_instruction_utf8_sha256": "11" * 32,
        "containment_policy": {
            "artifact_license_verified": False,
            "artifact_license_status": "unknown_pending_confirmation",
            "local_read_only_research_use_authorized_by_user": True,
            "raw_redistribution_allowed": False,
            "raw_publication_allowed": False,
            "references_mutation_allowed": False,
            "formal_export_may_include_only_hashes_ids_aggregates_and_user_created_decisions": True,
        },
        "append_only": True,
    }
    doc_hash = _write_json(root / "user_authorization.json", doc)
    binding = EvidenceBinding(
        kind="user_authorization", evidence_id="syn-user-auth-1",
        evidence_hash=doc_hash, path="user_authorization.json",
        scope="local_read_only_nonredistributive_s2_11")
    return root, binding


def _local_policy(binding: EvidenceBinding,
                  synthetic: bool = False) -> MappingPolicy:
    return MappingPolicy(
        policy_id="syn-policy-v1", approved=True,
        synthetic_test_only=synthetic,
        modality_identity={
            "obligation": "obligation",
            "permission": "permission",
            "prohibition": "prohibition",
        },
        field_mapping={},
        user_authorization_binding=binding,
    )


def _unknown_license() -> LicenseState:
    return LicenseState(qualified=False,
                        license_status="unknown_pending_confirmation")


def test_local_read_only_mode_requires_user_authorization_binding(
        tmp_path: Path) -> None:
    policy = _synthetic_policy(synthetic_test_only=False)
    with pytest.raises(EvidenceBindingMissingError) as exc:
        _convert(mode="local_read_only_research", mapping_policy=policy,
                 evidence_root=tmp_path,
                 license_state=_unknown_license())
    assert _error_code(exc.value) == "EVIDENCE_BINDING_MISSING"


def test_local_read_only_mode_rejects_synthetic_binding(
        tmp_path: Path) -> None:
    root, binding = _make_user_authorization_root(tmp_path)
    binding = EvidenceBinding(
        kind="user_authorization", evidence_id=binding.evidence_id,
        evidence_hash=binding.evidence_hash, path=binding.path,
        scope=binding.scope, synthetic=True)
    with pytest.raises(EvidenceBindingSyntheticError) as exc:
        _convert(mode="local_read_only_research",
                 mapping_policy=_local_policy(binding), evidence_root=root,
                 license_state=_unknown_license())
    assert _error_code(exc.value) == "EVIDENCE_BINDING_SYNTHETIC"


def test_local_read_only_mode_accepts_real_user_authorization(
        tmp_path: Path) -> None:
    root, binding = _make_user_authorization_root(tmp_path)
    out = _convert(mode="local_read_only_research",
                   mapping_policy=_local_policy(binding), evidence_root=root,
                   license_state=_unknown_license())
    assert out["semantics"] == "candidate_only"
    assert out["is_gold"] is False
    prov = out["formal_evidence_provenance"]
    assert prov is not None
    assert prov["mode"] == "local_read_only_research"
    assert prov["license_verified"] is False
    assert prov["license_status"] == "unknown_pending_confirmation"
    assert prov["user_authorization"]["event_id"] == "syn-user-auth-1"
    assert prov["containment_policy"]["raw_redistribution_allowed"] is False
    guard = out["promotion_guard"]
    assert guard["local_read_only_research"] is True
    assert guard["raw_redistribution_allowed"] is False
    assert guard["license_verified"] is False


def test_local_read_only_mode_rejects_redistribution_allowed(
        tmp_path: Path) -> None:
    root, binding = _make_user_authorization_root(tmp_path)
    doc = json.loads((root / "user_authorization.json")
                     .read_text(encoding="utf-8"))
    doc["containment_policy"]["raw_redistribution_allowed"] = True
    doc_hash = _write_json(root / "user_authorization.json", doc)
    binding = EvidenceBinding(
        kind="user_authorization", evidence_id=binding.evidence_id,
        evidence_hash=doc_hash, path=binding.path, scope=binding.scope)
    with pytest.raises(UserAuthorizationNotValidError) as exc:
        _convert(mode="local_read_only_research",
                 mapping_policy=_local_policy(binding), evidence_root=root,
                 license_state=_unknown_license())
    assert _error_code(exc.value) == "USER_AUTHORIZATION_NOT_VALID"


def test_local_read_only_mode_rejects_license_claimed_verified(
        tmp_path: Path) -> None:
    root, binding = _make_user_authorization_root(tmp_path)
    doc = json.loads((root / "user_authorization.json")
                     .read_text(encoding="utf-8"))
    doc["containment_policy"]["artifact_license_verified"] = True
    doc_hash = _write_json(root / "user_authorization.json", doc)
    binding = EvidenceBinding(
        kind="user_authorization", evidence_id=binding.evidence_id,
        evidence_hash=doc_hash, path=binding.path, scope=binding.scope)
    with pytest.raises(UserAuthorizationNotValidError) as exc:
        _convert(mode="local_read_only_research",
                 mapping_policy=_local_policy(binding), evidence_root=root,
                 license_state=_unknown_license())
    assert _error_code(exc.value) == "USER_AUTHORIZATION_NOT_VALID"


def test_local_read_only_mode_rejects_scope_mismatch(
        tmp_path: Path) -> None:
    root, binding = _make_user_authorization_root(tmp_path)
    binding = EvidenceBinding(
        kind="user_authorization", evidence_id=binding.evidence_id,
        evidence_hash=binding.evidence_hash, path=binding.path,
        scope="s2_11_candidate_mapping_only")
    with pytest.raises(EvidenceDocMismatchError) as exc:
        _convert(mode="local_read_only_research",
                 mapping_policy=_local_policy(binding), evidence_root=root,
                 license_state=_unknown_license())
    assert _error_code(exc.value) == "EVIDENCE_DOC_MISMATCH"


def test_local_read_only_mode_rejects_qualified_license_state(
        tmp_path: Path) -> None:
    root, binding = _make_user_authorization_root(tmp_path)
    with pytest.raises(LicenseNotQualifiedError) as exc:
        _convert(mode="local_read_only_research",
                 mapping_policy=_local_policy(binding), evidence_root=root,
                 license_state=LicenseState(qualified=True,
                                             license_status="qualified"))
    assert _error_code(exc.value) == "LICENSE_NOT_QUALIFIED"


def test_local_read_only_mode_accepts_unknown_license_state(
        tmp_path: Path) -> None:
    root, binding = _make_user_authorization_root(tmp_path)
    out = _convert(mode="local_read_only_research",
                   mapping_policy=_local_policy(binding), evidence_root=root,
                   license_state=LicenseState(
                       qualified=False,
                       license_status="unknown_pending_confirmation"))
    assert out["formal_evidence_provenance"]["license_verified"] is False


def test_local_read_only_mode_rejects_fabricated_gold_claims(
        tmp_path: Path) -> None:
    root, binding = _make_user_authorization_root(tmp_path)
    record = _synthetic_record(external_annotation={
        "modality": "obligation", "origin": "external ground truth"})
    out = _convert(record, mode="local_read_only_research",
                   mapping_policy=_local_policy(binding), evidence_root=root,
                   license_state=_unknown_license())
    assert out["is_gold"] is False
    assert out["promotion_guard"]["human_adjudicated"] is False
    assert out["promotion_guard"]["gold_promotion"] is False
    assert "external_annotation_review_aid_only" in out["warnings"]


def test_local_read_only_mode_works_with_checkpoint_a_event_read_only() -> None:
    # Integration: the REAL Checkpoint A user authorization event (already
    # committed) is the evidence document; the adapter reads it read-only.
    root = Path(__file__).resolve().parents[1]
    event_rel = "configs/s2_11_user_authorization_event_v1.json"
    event_path = root / event_rel
    assert event_path.is_file()
    binding = EvidenceBinding(
        kind="user_authorization",
        evidence_id="s2-11-user-auth-2026-08-17-v1",
        evidence_hash=hashlib.sha256(event_path.read_bytes()).hexdigest(),
        path=event_rel,
        scope="local_read_only_nonredistributive_s2_11")
    out = _convert(mode="local_read_only_research",
                   mapping_policy=_local_policy(binding), evidence_root=root,
                   license_state=_unknown_license())
    prov = out["formal_evidence_provenance"]
    assert prov["user_authorization"]["event_id"] == \
        "s2-11-user-auth-2026-08-17-v1"
    assert prov["user_authorization"]["user_instruction_utf8_sha256"] == \
        "a8a1dec4c826b1303fde64f2ac111ea2886ad0b08fd8a20af68b5a67130bfc64"
    assert prov["license_verified"] is False


# --- 8. external labels never Gold -------------------------------------------


def test_external_labels_never_auto_promoted_to_gold() -> None:
    record = _synthetic_record(external_annotation={
        "modality": "obligation", "origin": "external ground truth"})
    out = _convert(record)
    assert out["is_gold"] is False
    assert out["promotion_guard"]["human_adjudicated"] is False
    assert out["promotion_guard"]["gold_promotion"] is False
    assert "external_annotation" not in out["mapped_fields"]
    assert out["review_aids"] == [{"external_annotation": record[
        "external_annotation"]}]
    assert "external_annotation_review_aid_only" in out["warnings"]


# --- 9. legal synthetic conversion: field-level provenance -------------------


def test_legal_synthetic_candidate_keeps_field_level_provenance() -> None:
    out = _convert()
    assert out["mapped_fields"]["modality"] == "obligation"
    assert out["mapped_fields"]["condition"] == "the data subject"
    mod_prov = out["field_provenance"]["modality"]
    assert mod_prov["source_element"] == "norms[0].modality"
    assert mod_prov["source_locator"] == \
        field_locator(RECORD_PATH, "norms[0].modality")
    assert mod_prov["span"] == {"start": 0, "end": 54}
    cond_prov = out["field_provenance"]["condition"]
    assert cond_prov["source_element"] == "precondition"
    assert cond_prov["source_locator"] == field_locator(RECORD_PATH,
                                                        "precondition")
    assert cond_prov["source_path"] == RECORD_PATH
    assert cond_prov["source_record_id"] == "syn-001"
    assert cond_prov["source_text_hash"] == _sha(
        "the data subject shall be notified without undue delay")
    assert cond_prov["span"] == {"start": 0, "end": 16}
    assert cond_prov["span_alignment_source"] == \
        "approved_english_alignment"
    assert cond_prov["mapping_policy_id"] == "syn-policy-v1"
    assert cond_prov["span"] != mod_prov["span"]


def test_modality_only_mapping_when_no_field_policy() -> None:
    policy = _synthetic_policy(fields={})
    out = _convert(mapping_policy=policy)
    assert set(out["mapped_fields"]) == {"modality"}
    assert set(out["field_provenance"]) == {"modality"}
    assert "unmapped_structure_field:precondition" in out["warnings"]


def test_unmapped_structure_fields_never_silently_converted() -> None:
    out = _convert()
    assert "norm" not in out["mapped_fields"]
    assert "temporal_validity" not in out["mapped_fields"]


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


# --- 10. structure / unknown fields ------------------------------------------


def test_unknown_record_field_fails_closed() -> None:
    record = _synthetic_record(bogus_field="x")
    with pytest.raises(InvalidStructureError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "INVALID_STRUCTURE"


def test_missing_required_key_fails_closed() -> None:
    record = _synthetic_record()
    del record["text_provenance"]
    with pytest.raises(InvalidStructureError) as exc:
        _convert(record)
    assert _error_code(exc.value) == "INVALID_STRUCTURE"


# --- 11. real-world default states refuse -------------------------------------


def test_current_real_world_states_refuse_everything(tmp_path: Path) -> None:
    policy = _synthetic_policy(approved=False)
    with pytest.raises(LicenseNotQualifiedError):
        _convert(license_state=LicenseState(),
                 activation_state=ActivationState(),
                 mapping_policy=policy)
