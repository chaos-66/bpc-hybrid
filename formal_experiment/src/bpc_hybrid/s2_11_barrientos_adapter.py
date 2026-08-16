# -*- coding: utf-8 -*-
"""Fail-closed Barrientos-style -> candidate Rule Record adapter (S2.11 /
S2-BARR-2).

STATUS: SYNTHETIC / SHADOW implementation only. It is importable and fully
tested against synthetic fixtures, but it is NOT a formal adapter:
  * no real `references/barrientos_2026` data is ever scanned, loaded or
    executed by this module;
  * license qualification, data activation, a 3->4 modality mapping policy
    and a field mapping policy are all caller-supplied states; the current
    real states are license=unknown_pending_confirmation,
    activation=NOT authorized, mapping policy=NOT approved, so every real
    conversion is REFUSED today;
  * the only usable policy today is `synthetic_test_only` and it can never
    enter formal mode;
  * output is `candidate_only` / `review_candidate` semantics only and can
    never claim project Gold.

Fail-closed behaviour (machine-decodable error codes on
:class:`BarrientosAdapterError` subclasses):
  LICENSE_NOT_QUALIFIED            license_state.qualified is not True
  ACTIVATION_NOT_AUTHORIZED        activation_state.authorized is not True
  MAPPING_POLICY_NOT_APPROVED      mapping_policy.approved is not True
  SYNTHETIC_POLICY_IN_FORMAL_MODE  synthetic_test_only policy used with
                                   mode="formal"
  INVALID_STRUCTURE                missing required key / unknown key
  UNKNOWN_MODALITY                 source modality not in the Barrientos
                                   3-class set
  DEFINITION_NOT_PRODUCIBLE        mapping target is "definition" (the
                                   source has no definition class; it is
                                   never invented)
  MAPPING_POLICY_INCOMPLETE        approved policy lacks the source
                                   modality entry
  INVALID_MAPPED_MODALITY          mapping target not in the Sun 4-class set
  MISSING_TEXT_PROVENANCE          text missing or sha256 does not match
  MISSING_SPAN_ALIGNMENT           no span, or span uses external offsets
                                   without an approved alignment
  INVALID_SPAN                     span out of bounds / empty / wrong types
  AMBIGUOUS_SPAN                   aligned span text is not unique in the
                                   aligned text
  UNRESOLVED_CROSS_REFERENCE       any cross_references[].resolved is False
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping

BARRIENTOS_MODALITY_CLASSES = frozenset(
    {"obligation", "permission", "prohibition"})
SUN_MODALITY_CLASSES = frozenset(
    {"obligation", "permission", "prohibition", "definition"})

REQUIRED_RECORD_KEYS = frozenset({
    "source_record_id", "source_element", "source_path", "modality", "text",
    "text_provenance", "span", "text_span_source", "cross_references",
    "structure",
})
OPTIONAL_RECORD_KEYS = frozenset({"external_annotation"})

TEXT_SPAN_SOURCES = frozenset(
    {"approved_english_alignment", "external_offsets"})

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


@dataclass(frozen=True)
class LicenseState:
    """Caller-supplied license qualification state. The current real state
    is qualified=False / status=unknown_pending_confirmation; this module
    never infers a qualification by itself."""

    qualified: bool = False
    license_status: str = "unknown_pending_confirmation"


@dataclass(frozen=True)
class ActivationState:
    """Caller-supplied data-activation state. The current real state is
    authorized=False; this module never activates anything."""

    authorized: bool = False


@dataclass(frozen=True)
class MappingPolicy:
    """Caller-supplied, user-approved mapping policy.

    `modality_identity` maps a Barrientos 3-class modality to a Sun 4-class
    modality. `field_mapping` maps a Barrientos structure element name to a
    Sun span field name. Both stay empty until a user decision exists.
    `synthetic_test_only=True` policies are rejected in formal mode.
    """

    policy_id: str
    approved: bool = False
    synthetic_test_only: bool = False
    modality_identity: Mapping[str, str] = field(default_factory=dict)
    field_mapping: Mapping[str, str] = field(default_factory=dict)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check_license(license_state: LicenseState) -> None:
    if not license_state.qualified:
        raise LicenseNotQualifiedError(
            "license not qualified; Barrientos assets stay "
            "unknown_pending_confirmation until authoritative evidence "
            "exists",
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


def _check_modality(record: Mapping[str, Any],
                    mapping_policy: MappingPolicy) -> str:
    src = str(record["modality"])
    if src not in BARRIENTOS_MODALITY_CLASSES:
        raise UnknownModalityError(
            f"source modality {src!r} is not a Barrientos 3-class modality",
            detail=sorted(BARRIENTOS_MODALITY_CLASSES))
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
    return target


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


def _check_span(record: Mapping[str, Any], text: str) -> dict[str, Any]:
    span_source = record.get("text_span_source")
    if span_source not in TEXT_SPAN_SOURCES:
        raise MissingSpanAlignmentError(
            "no reliable text/span alignment source declared",
            detail=f"text_span_source={span_source!r}")
    span = record.get("span")
    if span is None:
        raise MissingSpanAlignmentError(
            "mapping requires span provenance but the record has no span",
            detail="span=None")
    if not isinstance(span, Mapping):
        raise InvalidSpanError("span must be a mapping",
                               detail=f"span={span!r}")
    start, end = span.get("start"), span.get("end")
    if not isinstance(start, int) or not isinstance(end, int):
        raise InvalidSpanError("span start/end must be integers",
                               detail=f"span={span!r}")
    if start < 0 or end < start or end > len(text):
        raise InvalidSpanError(
            "span is out of bounds for the source text",
            detail=f"span=[{start},{end}) text_len={len(text)}")
    if span_source == "external_offsets":
        raise MissingSpanAlignmentError(
            "external offsets are NOT aligned to approved English text; "
            "alignment must be established before any span may be mapped",
            detail=f"span=[{start},{end}) text_span_source=external_offsets")
    # approved_english_alignment: the aligned span text must be unique.
    span_text = text[start:end]
    if not span_text.strip():
        raise InvalidSpanError("aligned span text is empty",
                               detail=f"span=[{start},{end})")
    occurrences = text.count(span_text)
    if occurrences != 1:
        raise AmbiguousSpanError(
            "aligned span text is not unique in the aligned text; cannot "
            "re-anchor deterministically",
            detail=f"span_text={span_text!r} occurrences={occurrences}")
    return {"start": start, "end": end}


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
        resolved.append({"ref_id": str(ref["ref_id"]),
                         "resolved": True})
    return sorted(resolved, key=lambda r: r["ref_id"])


def _map_structure_fields(record: Mapping[str, Any],
                          mapping_policy: MappingPolicy) -> tuple[
                              dict[str, Any], list[str]]:
    """Map ONLY the structure elements listed in the approved field mapping.
    Everything else is left untouched (never silently converted)."""
    mapped: dict[str, Any] = {}
    warnings: list[str] = []
    structure = record.get("structure")
    if not isinstance(structure, Mapping):
        raise InvalidStructureError("structure must be a mapping",
                                    detail=f"structure={structure!r}")
    declared = set(structure)
    configured = set(mapping_policy.field_mapping)
    for src_key, sun_field in sorted(mapping_policy.field_mapping.items()):
        if src_key not in declared:
            continue
        value = structure[src_key]
        if not isinstance(sun_field, str) or not sun_field.strip():
            raise InvalidStructureError(
                "field mapping target must be a non-empty string",
                detail=f"{src_key!r} -> {sun_field!r}")
        mapped[sun_field] = value
    for src_key in sorted(declared - configured):
        warnings.append(f"unmapped_structure_field:{src_key}")
    return mapped, warnings


def convert_to_candidate(
        record: Mapping[str, Any], *,
        license_state: LicenseState,
        activation_state: ActivationState,
        mapping_policy: MappingPolicy,
        mode: str = "synthetic_test_only") -> dict[str, Any]:
    """Convert one Barrientos-style source record into a CANDIDATE Rule
    Record (candidate_only / review_candidate semantics, never Gold).

    Deterministic: mapped fields, provenance entries and warnings are
    emitted in sorted order, so input order changes do not affect the
    canonical output. Raises a typed :class:`BarrientosAdapterError` with a
    machine-decodable code on any fail-closed condition.
    """
    _check_license(license_state)
    _check_activation(activation_state)
    _check_policy(mapping_policy, mode)
    _check_structure(record)
    mapped_modality = _check_modality(record, mapping_policy)
    text = _check_text_provenance(record)
    _check_span(record, text)
    resolved_refs = _check_cross_references(record)
    mapped_fields, warnings = _map_structure_fields(record, mapping_policy)

    ordered_fields: dict[str, Any] = {}
    ordered_fields["modality"] = mapped_modality
    for sun_field in sorted(mapped_fields):
        ordered_fields[sun_field] = mapped_fields[sun_field]

    span = record["span"]
    provenance: dict[str, Any] = {}
    for sun_field in sorted(ordered_fields):
        provenance[sun_field] = {
            "source_element": str(record["source_element"]),
            "source_path": str(record["source_path"]),
            "source_record_id": str(record["source_record_id"]),
            "span": {"start": span["start"], "end": span["end"]},
            "mapping_policy_id": mapping_policy.policy_id,
        }

    review_aids: list[dict[str, Any]] = []
    annotation = record.get("external_annotation")
    if annotation is not None:
        review_aids.append({"external_annotation": annotation})
        warnings.append("external_annotation_review_aid_only")

    return {
        "status": OUTPUT_STATUS,
        "semantics": OUTPUT_SEMANTICS,
        "source_record_id": str(record["source_record_id"]),
        "source_element": str(record["source_element"]),
        "source_path": str(record["source_path"]),
        "mapped_fields": ordered_fields,
        "field_provenance": provenance,
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
