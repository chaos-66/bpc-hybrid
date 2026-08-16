# -*- coding: utf-8 -*-
"""Fail-closed Barrientos-style -> candidate Rule Record adapter (S2.11 /
S2-BARR-2) — HARDENED v4 provenance model.

STATUS: SYNTHETIC / SHADOW implementation only (hardened). It is importable
and fully tested against synthetic fixtures, but it is NOT a formal adapter:
  * no real `references/` data is ever scanned, loaded or executed;
  * license qualification, data activation, mapping policies and formal
    evidence bindings are caller-supplied; the current real states are
    article license CC BY 4.0 (article only — does NOT cover the artifact),
    artifact code/data license=unknown_pending_confirmation,
    activation=NOT authorized, mapping policy=NOT approved, so every real
    conversion is REFUSED today;
  * FORMAL mode additionally requires versioned evidence bindings
    (license evidence ID/hash + authorization manifest ID/hash); no such
    assets exist on disk today, and synthetic bindings never enter formal
    mode;
  * output is `candidate_only` / `review_candidate` semantics only and can
    never claim project Gold.

Provenance model (v4): record-level provenance (record text hash) and
field-level provenance are SEPARATED. Every mappable source element carries
its own source element/key, source path, source record ID, source text
hash, start/end span, span alignment source and mapping policy ID. The
modality element points at the actual norm modality element. Structural
fields never reuse the modality/record-global span.

Canonical target whitelist (v4): only actor, action, condition,
constraint, exception may receive a structural mapping; modality is handled
by the separate identity mapping. Non-canonical targets, duplicate-target
collisions, missing field provenance, invalid/ambiguous/mismatched field
spans, nested-dict values and inconsistent element/path references fail
closed with machine-decodable codes.

Fail-closed error codes (BarrientosAdapterError subclasses):
  LICENSE_NOT_QUALIFIED / ACTIVATION_NOT_AUTHORIZED /
  MAPPING_POLICY_NOT_APPROVED / SYNTHETIC_POLICY_IN_FORMAL_MODE /
  EVIDENCE_BINDING_MISSING / EVIDENCE_BINDING_SYNTHETIC /
  INVALID_STRUCTURE / UNKNOWN_MODALITY / DEFINITION_NOT_PRODUCIBLE /
  MAPPING_POLICY_INCOMPLETE / INVALID_MAPPED_MODALITY /
  MISSING_TEXT_PROVENANCE / MISSING_SPAN_ALIGNMENT / INVALID_SPAN /
  AMBIGUOUS_SPAN / UNRESOLVED_CROSS_REFERENCE /
  NON_CANONICAL_TARGET / TARGET_COLLISION / FIELD_PROVENANCE_MISSING /
  FIELD_SPAN_INVALID / FIELD_SPAN_AMBIGUOUS / FIELD_VALUE_MISMATCH /
  NESTED_DICT_AS_SPAN_FIELD / ELEMENT_PATH_MISMATCH
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping

BARRIENTOS_MODALITY_CLASSES = frozenset(
    {"obligation", "permission", "prohibition"})
SUN_MODALITY_CLASSES = frozenset(
    {"obligation", "permission", "prohibition", "definition"})

# Canonical Sun span fields allowed as structural mapping targets (v4).
CANONICAL_SPAN_FIELDS = frozenset(
    {"actor", "action", "condition", "constraint", "exception"})

REQUIRED_RECORD_KEYS = frozenset({
    "source_record_id", "source_path", "modality", "text",
    "text_provenance", "structure", "cross_references",
})
OPTIONAL_RECORD_KEYS = frozenset({"external_annotation"})

TEXT_SPAN_SOURCES = frozenset(
    {"approved_english_alignment", "external_offsets"})

REQUIRED_ELEMENT_KEYS = frozenset({
    "value", "element", "path", "text_hash", "span", "span_alignment_source",
})

OUTPUT_SEMANTICS = "candidate_only"
OUTPUT_STATUS = "review_candidate"


class BarrientosAdapterError(Exception):
    """Base class for all adapter rejections; carries a machine-decodable
    error code."""

    code = "BARRIENTOS_ADAPTER_ERROR"

    def __init__(self, message: str, *, detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message,
                "detail": self.detail}


class LicenseNotQualifiedError(BarrientosAdapterError):
    code = "LICENSE_NOT_QUALIFIED"


class ActivationNotAuthorizedError(BarrientosAdapterError):
    code = "ACTIVATION_NOT_AUTHORIZED"


class MappingPolicyNotApprovedError(BarrientosAdapterError):
    code = "MAPPING_POLICY_NOT_APPROVED"


class SyntheticPolicyInFormalModeError(BarrientosAdapterError):
    code = "SYNTHETIC_POLICY_IN_FORMAL_MODE"


class EvidenceBindingMissingError(BarrientosAdapterError):
    code = "EVIDENCE_BINDING_MISSING"


class EvidenceBindingSyntheticError(BarrientosAdapterError):
    code = "EVIDENCE_BINDING_SYNTHETIC"


class InvalidStructureError(BarrientosAdapterError):
    code = "INVALID_STRUCTURE"


class UnknownModalityError(BarrientosAdapterError):
    code = "UNKNOWN_MODALITY"


class DefinitionNotProducibleError(BarrientosAdapterError):
    code = "DEFINITION_NOT_PRODUCIBLE"


class MappingPolicyIncompleteError(BarrientosAdapterError):
    code = "MAPPING_POLICY_INCOMPLETE"


class InvalidMappedModalityError(BarrientosAdapterError):
    code = "INVALID_MAPPED_MODALITY"


class MissingTextProvenanceError(BarrientosAdapterError):
    code = "MISSING_TEXT_PROVENANCE"


class MissingSpanAlignmentError(BarrientosAdapterError):
    code = "MISSING_SPAN_ALIGNMENT"


class InvalidSpanError(BarrientosAdapterError):
    code = "INVALID_SPAN"


class AmbiguousSpanError(BarrientosAdapterError):
    code = "AMBIGUOUS_SPAN"


class UnresolvedCrossReferenceError(BarrientosAdapterError):
    code = "UNRESOLVED_CROSS_REFERENCE"


class NonCanonicalTargetError(BarrientosAdapterError):
    code = "NON_CANONICAL_TARGET"


class TargetCollisionError(BarrientosAdapterError):
    code = "TARGET_COLLISION"


class FieldProvenanceMissingError(BarrientosAdapterError):
    code = "FIELD_PROVENANCE_MISSING"


class FieldSpanInvalidError(BarrientosAdapterError):
    code = "FIELD_SPAN_INVALID"


class FieldSpanAmbiguousError(BarrientosAdapterError):
    code = "FIELD_SPAN_AMBIGUOUS"


class FieldValueMismatchError(BarrientosAdapterError):
    code = "FIELD_VALUE_MISMATCH"


class NestedDictAsSpanFieldError(BarrientosAdapterError):
    code = "NESTED_DICT_AS_SPAN_FIELD"


class ElementPathMismatchError(BarrientosAdapterError):
    code = "ELEMENT_PATH_MISMATCH"


@dataclass(frozen=True)
class LicenseState:
    """Caller-supplied license qualification state. Current real state:
    qualified=False / artifact license unknown_pending_confirmation (the
    article CC BY 4.0 does NOT auto-cover the artifact)."""

    qualified: bool = False
    license_status: str = "unknown_pending_confirmation"


@dataclass(frozen=True)
class ActivationState:
    """Caller-supplied data-activation state. Current real state:
    authorized=False."""

    authorized: bool = False


@dataclass(frozen=True)
class EvidenceBinding:
    """Versioned evidence binding required by FORMAL mode.

    `kind` is "license" (license evidence) or "authorization" (user
    authorization manifest). `synthetic=True` marks a test fixture binding;
    synthetic bindings are never accepted in formal mode.
    """

    kind: str
    evidence_id: str
    evidence_hash: str
    synthetic: bool = False


@dataclass(frozen=True)
class MappingPolicy:
    """Caller-supplied, user-approved mapping policy.

    `modality_identity` maps a Barrientos 3-class modality to a Sun 4-class
    modality. `field_mapping` maps a source structure element key to a
    canonical Sun span field (actor/action/condition/constraint/exception);
    it stays empty until a separate user decision exists (M1 never implies
    structural mapping). `license_evidence_binding` /
    `authorization_manifest_binding` are required in formal mode and must
    not be synthetic.
    """

    policy_id: str
    approved: bool = False
    synthetic_test_only: bool = False
    modality_identity: Mapping[str, str] = field(default_factory=dict)
    field_mapping: Mapping[str, str] = field(default_factory=dict)
    license_evidence_binding: EvidenceBinding | None = None
    authorization_manifest_binding: EvidenceBinding | None = None


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check_license(license_state: LicenseState) -> None:
    if not license_state.qualified:
        raise LicenseNotQualifiedError(
            "license not qualified; Barrientos artifact code/data stay "
            "unknown_pending_confirmation until authoritative artifact "
            "license evidence exists (the article CC BY 4.0 does NOT "
            "auto-cover the artifact)",
            detail=f"license_status={license_state.license_status!r}")


def _check_activation(activation_state: ActivationState) -> None:
    if not activation_state.authorized:
        raise ActivationNotAuthorizedError(
            "external data activation NOT authorized",
            detail="activation_state.authorized=False")


def _check_policy(mapping_policy: MappingPolicy, mode: str) -> None:
    if not mapping_policy.approved:
        raise MappingPolicyNotApprovedError(
            f"mapping policy {mapping_policy.policy_id!r} is not approved; "
            "no modality/field mapping may run without a user decision",
            detail=f"approved={mapping_policy.approved}")
    if mapping_policy.synthetic_test_only and mode == "formal":
        raise SyntheticPolicyInFormalModeError(
            f"synthetic test-only policy {mapping_policy.policy_id!r} must "
            "never enter formal mode",
            detail=f"mode={mode!r}")
    if mode == "formal":
        license_binding = mapping_policy.license_evidence_binding
        auth_binding = mapping_policy.authorization_manifest_binding
        if license_binding is None or auth_binding is None:
            raise EvidenceBindingMissingError(
                "formal mode requires versioned license evidence binding "
                "AND authorization manifest binding; no such assets exist "
                "on disk today",
                detail=f"license_binding={license_binding is not None}, "
                       f"authorization_binding={auth_binding is not None}")
        if license_binding.synthetic or auth_binding.synthetic:
            raise EvidenceBindingSyntheticError(
                "synthetic evidence bindings must never enter formal mode",
                detail=f"license_synthetic={license_binding.synthetic}, "
                       f"auth_synthetic={auth_binding.synthetic}")
        if license_binding.kind != "license" or \
                auth_binding.kind != "authorization":
            raise EvidenceBindingMissingError(
                "formal-mode evidence bindings have wrong kinds",
                detail=f"license_kind={license_binding.kind!r}, "
                       f"auth_kind={auth_binding.kind!r}")


def _check_structure(record: Mapping[str, Any]) -> None:
    missing = sorted(REQUIRED_RECORD_KEYS - set(record))
    if missing:
        raise InvalidStructureError(
            "record is missing required keys",
            detail=f"missing={missing}")
    unknown = sorted(set(record) - REQUIRED_RECORD_KEYS - OPTIONAL_RECORD_KEYS)
    if unknown:
        raise InvalidStructureError(
            "record contains unknown fields (fail-closed)",
            detail=f"unknown={unknown}")
    if not isinstance(record.get("structure"), Mapping):
        raise InvalidStructureError(
            "structure must be a mapping",
            detail=f"structure={record.get('structure')!r}")


def _validate_element_descriptor(descriptor: Any, where: str,
                                 record: Mapping[str, Any],
                                 require_value_match: bool = True
                                 ) -> dict[str, Any]:
    """Validate one source-element descriptor (field-level provenance).

    `require_value_match=True` (structural span fields): the descriptor
    value must equal the aligned span text. `require_value_match=False`
    (modality element): the value is a canonical label; the span still has
    to be valid (in-bounds, non-empty, unique) but no label==span-text
    equality is required.
    """
    if not isinstance(descriptor, Mapping):
        raise FieldProvenanceMissingError(
            f"{where} has no provenance descriptor",
            detail=f"descriptor={descriptor!r}")
    missing_keys = sorted(REQUIRED_ELEMENT_KEYS - set(descriptor))
    if missing_keys:
        raise FieldProvenanceMissingError(
            f"{where} descriptor is missing provenance fields",
            detail=f"missing={missing_keys}")
    element = descriptor.get("element")
    path = descriptor.get("path")
    if not isinstance(element, str) or not element.strip():
        raise ElementPathMismatchError(
            f"{where} descriptor has no source element/key",
            detail=f"element={element!r}")
    if not isinstance(path, str) or not path.strip():
        raise ElementPathMismatchError(
            f"{where} descriptor has no source path",
            detail=f"path={path!r}")
    text_hash = descriptor.get("text_hash")
    if not isinstance(text_hash, str) or text_hash != _sha256_text(
            str(record.get("text", ""))):
        raise ElementPathMismatchError(
            f"{where} descriptor text hash does not match the record text",
            detail=f"text_hash={text_hash!r}")
    value = descriptor.get("value")
    if isinstance(value, (dict, list)):
        raise NestedDictAsSpanFieldError(
            f"{where} value must be a leaf value, not a nested structure",
            detail=f"value_type={type(value).__name__}")
    span_source = descriptor.get("span_alignment_source")
    if span_source not in TEXT_SPAN_SOURCES:
        raise MissingSpanAlignmentError(
            f"{where} has no reliable span alignment source",
            detail=f"span_alignment_source={span_source!r}")
    span = descriptor.get("span")
    if not isinstance(span, Mapping) or not isinstance(
            span.get("start"), int) or not isinstance(span.get("end"), int):
        raise FieldSpanInvalidError(
            f"{where} span must be start/end integers",
            detail=f"span={span!r}")
    text = str(record.get("text", ""))
    start, end = span["start"], span["end"]
    if start < 0 or end < start or end > len(text):
        raise FieldSpanInvalidError(
            f"{where} span is out of bounds",
            detail=f"span=[{start},{end}) text_len={len(text)}")
    if span_source == "external_offsets":
        raise MissingSpanAlignmentError(
            f"{where} uses external offsets without approved alignment",
            detail=f"span=[{start},{end})")
    span_text = text[start:end]
    if not span_text.strip():
        raise FieldSpanInvalidError(
            f"{where} aligned span text is empty",
            detail=f"span=[{start},{end})")
    if text.count(span_text) != 1:
        raise FieldSpanAmbiguousError(
            f"{where} aligned span text is not unique",
            detail=f"span_text={span_text!r}")
    if not isinstance(value, str) or (
            require_value_match and value != span_text):
        raise FieldValueMismatchError(
            f"{where} value does not match the aligned span text",
            detail=f"value={value!r} span_text={span_text!r}")
    return {"element": element, "path": path, "span": {"start": start,
                                                       "end": end}}


def _check_modality(record: Mapping[str, Any],
                    mapping_policy: MappingPolicy) -> tuple[str, dict[str, Any]]:
    modality = record.get("modality")
    if not isinstance(modality, Mapping) or "value" not in modality:
        raise InvalidStructureError(
            "modality must be an element descriptor with a value",
            detail=f"modality={modality!r}")
    src = str(modality["value"])
    if src not in BARRIENTOS_MODALITY_CLASSES:
        raise UnknownModalityError(
            f"source modality {src!r} is not a Barrientos 3-class modality",
            detail=sorted(BARRIENTOS_MODALITY_CLASSES))
    element = modality.get("element")
    if not isinstance(element, str) or "norm" not in element.lower():
        raise ElementPathMismatchError(
            "modality provenance must point at the actual norm modality "
            "element",
            detail=f"modality.element={element!r}")
    prov = _validate_element_descriptor(modality, "modality", record,
                                        require_value_match=False)
    if src not in mapping_policy.modality_identity:
        raise MappingPolicyIncompleteError(
            f"approved mapping policy {mapping_policy.policy_id!r} has no "
            f"entry for source modality {src!r}",
            detail=f"modality_identity={sorted(mapping_policy.modality_identity)}")
    target = str(mapping_policy.modality_identity[src])
    if target == "definition":
        raise DefinitionNotProducibleError(
            "'definition' is absent in the Barrientos source and is never "
            "invented; definition-class records require separate human "
            "adjudication",
            detail=f"source={src!r} target={target!r}")
    if target not in SUN_MODALITY_CLASSES:
        raise InvalidMappedModalityError(
            f"mapped modality {target!r} is not a Sun 4-class modality",
            detail=sorted(SUN_MODALITY_CLASSES))
    return target, prov


def _check_field_policy(mapping_policy: MappingPolicy) -> None:
    targets: dict[str, str] = {}
    for src_key, target in sorted(mapping_policy.field_mapping.items()):
        if not isinstance(src_key, str) or not src_key.strip():
            raise InvalidStructureError(
                "field mapping source key must be a non-empty string",
                detail=f"src_key={src_key!r}")
        if not isinstance(target, str):
            raise NonCanonicalTargetError(
                "field mapping target must be a string",
                detail=f"{src_key!r} -> {target!r}")
        if target not in CANONICAL_SPAN_FIELDS:
            raise NonCanonicalTargetError(
                f"field mapping target {target!r} is not a canonical Sun "
                f"span field",
                detail=f"allowed={sorted(CANONICAL_SPAN_FIELDS)}")
        if target in targets:
            raise TargetCollisionError(
                f"two source fields map to the same canonical target "
                f"{target!r}: {targets[target]!r} and {src_key!r}",
                detail=f"target={target!r}")
        targets[target] = src_key


def _check_text_provenance(record: Mapping[str, Any]) -> str:
    text = record.get("text")
    if not isinstance(text, str) or not text.strip():
        raise MissingTextProvenanceError(
            "record has no usable source text",
            detail="text missing or empty")
    prov = record.get("text_provenance")
    if not isinstance(prov, Mapping) or not isinstance(
            prov.get("sha256"), str):
        raise MissingTextProvenanceError(
            "record has no text provenance sha256",
            detail=f"text_provenance={prov!r}")
    if prov["sha256"] != _sha256_text(text):
        raise MissingTextProvenanceError(
            "text provenance sha256 does not match the source text",
            detail=f"declared={prov['sha256'][:12]}... "
                   f"computed={_sha256_text(text)[:12]}...")
    return text


def _check_cross_references(record: Mapping[str, Any]) -> list[dict[str, str]]:
    refs = record.get("cross_references")
    if not isinstance(refs, list):
        raise InvalidStructureError(
            "cross_references must be a list",
            detail=f"cross_references={refs!r}")
    resolved: list[dict[str, str]] = []
    for ref in refs:
        if not isinstance(ref, Mapping) or not isinstance(
                ref.get("ref_id"), str):
            raise InvalidStructureError(
                "cross-reference entry must be a mapping with ref_id",
                detail=f"ref={ref!r}")
        if ref.get("resolved") is not True:
            raise UnresolvedCrossReferenceError(
                f"cross-reference {ref.get('ref_id')!r} is unresolved; "
                "provenance is incomplete",
                detail=f"resolved={ref.get('resolved')!r}")
        resolved.append({"ref_id": str(ref["ref_id"]), "resolved": True})
    return sorted(resolved, key=lambda r: r["ref_id"])


def _map_structure_fields(record: Mapping[str, Any],
                          mapping_policy: MappingPolicy,
                          record_provenance: dict[str, Any]) -> tuple[
                              dict[str, Any], dict[str, Any], list[str]]:
    """Map ONLY the structure elements listed in the approved field
    mapping, each with its OWN field-level provenance. Everything else is
    left untouched (never silently converted)."""
    mapped: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    warnings: list[str] = []
    structure = record.get("structure", {})
    declared = set(structure)
    for src_key, target in sorted(mapping_policy.field_mapping.items()):
        if src_key not in declared:
            continue
        descriptor = structure[src_key]
        prov = _validate_element_descriptor(descriptor, src_key, record)
        mapped[target] = descriptor["value"]
        provenance[target] = {
            "source_element": prov["element"],
            "source_path": prov["path"],
            "source_record_id": str(record["source_record_id"]),
            "source_text_hash": str(descriptor["text_hash"]),
            "span": prov["span"],
            "span_alignment_source": str(
                descriptor["span_alignment_source"]),
            "mapping_policy_id": mapping_policy.policy_id,
        }
    for src_key in sorted(declared - set(mapping_policy.field_mapping)):
        warnings.append(f"unmapped_structure_field:{src_key}")
    return mapped, provenance, warnings


def convert_to_candidate(
        record: Mapping[str, Any], *,
        license_state: LicenseState,
        activation_state: ActivationState,
        mapping_policy: MappingPolicy,
        mode: str = "synthetic_test_only") -> dict[str, Any]:
    """Convert one Barrientos-style source record into a CANDIDATE Rule
    Record (candidate_only / review_candidate semantics, never Gold).

    Deterministic: mapped fields, provenance entries and warnings are
    emitted in sorted order. Raises a typed :class:`BarrientosAdapterError`
    with a machine-decodable code on any fail-closed condition.
    """
    _check_license(license_state)
    _check_activation(activation_state)
    _check_policy(mapping_policy, mode)
    _check_structure(record)
    _check_field_policy(mapping_policy)
    _check_text_provenance(record)
    mapped_modality, modality_prov = _check_modality(record, mapping_policy)
    resolved_refs = _check_cross_references(record)
    mapped_fields, field_provenance, warnings = _map_structure_fields(
        record, mapping_policy, modality_prov)

    ordered_fields: dict[str, Any] = {"modality": mapped_modality}
    for target in sorted(mapped_fields):
        ordered_fields[target] = mapped_fields[target]

    full_provenance: dict[str, Any] = {
        "modality": {
            "source_element": modality_prov["element"],
            "source_path": modality_prov["path"],
            "source_record_id": str(record["source_record_id"]),
            "source_text_hash": str(record["modality"]["text_hash"]),
            "span": modality_prov["span"],
            "span_alignment_source": str(
                record["modality"]["span_alignment_source"]),
            "mapping_policy_id": mapping_policy.policy_id,
        },
    }
    for target in sorted(field_provenance):
        full_provenance[target] = field_provenance[target]

    review_aids: list[dict[str, Any]] = []
    annotation = record.get("external_annotation")
    if annotation is not None:
        review_aids.append({"external_annotation": annotation})
        warnings.append("external_annotation_review_aid_only")

    return {
        "status": OUTPUT_STATUS,
        "semantics": OUTPUT_SEMANTICS,
        "source_record_id": str(record["source_record_id"]),
        "source_path": str(record["source_path"]),
        "mapped_fields": ordered_fields,
        "field_provenance": full_provenance,
        "mapping_policy_id": mapping_policy.policy_id,
        "resolved_cross_references": resolved_refs,
        "review_aids": review_aids,
        "warnings": sorted(set(warnings)),
        "is_gold": False,
        "promotion_guard": {
            "license_qualified": bool(license_state.qualified),
            "activation_authorized": bool(activation_state.authorized),
            "mapping_policy_approved": bool(mapping_policy.approved),
            "human_adjudicated": False,
            "gold_promotion": False,
        },
    }
