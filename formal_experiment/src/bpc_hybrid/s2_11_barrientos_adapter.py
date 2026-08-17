# -*- coding: utf-8 -*-
"""Fail-closed Barrientos-style -> candidate Rule Record adapter (S2.11 /
S2-BARR-2) — v6 hardening.

STATUS: SYNTHETIC / SHADOW implementation only. It is importable and fully
tested against synthetic fixtures, but it is NOT a formal adapter:
  * no real `references/` data is ever scanned, loaded or executed;
  * license qualification, data activation, mapping policies and evidence
    bindings are caller-supplied; the current real states are article
    license CC BY 4.0 (article only — does NOT cover the artifact), artifact
    code/data license=unknown_pending_confirmation, activation=NOT
    authorized, mapping policy=NOT approved, so every real conversion is
    REFUSED today;
  * mode is a STRICT enum: only "synthetic_test_only" and "formal" are
    valid; any other value is rejected with INVALID_MODE;
  * FORMAL mode additionally requires versioned, FILE-BACKED evidence
    bindings: a license evidence document and an authorization manifest
    whose relative paths exist under the evidence root, whose raw bytes
    hash to the declared 64-hex SHA-256, whose internal kind/ID/scope match
    the binding, and (for the authorization manifest) whose policy binding
    exactly matches the mapping policy (policy ID, modality mapping, field
    mapping, license evidence ID/hash/scope) and whose append-only
    authorization event (ID + raw-byte SHA-256) is verified from disk. No
    such assets exist on disk today, and synthetic bindings never enter
    formal mode;
  * output is `candidate_only` / `review_candidate` semantics only and can
    never claim project Gold.

v6 additions:
  * the evidence verifier returns a re-verified structured EvidenceContext
    (not None), and every FORMAL output carries an explicit
    `formal_evidence_provenance` block (license evidence ID/relative
    path/raw-byte SHA-256/exact license scope; authorization manifest
    ID/relative path/raw-byte SHA-256/exact authorization scope;
    authorization event ID/relative path/raw-byte SHA-256; policy ID;
    canonical modality/field mapping hashes; how the manifest binds the
    license evidence; candidate_only=true; gold_authorized=false).
    Synthetic mode never masquerades as formal evidence: the block is
    null there.
  * scopes are controlled enums: license scope must be one of
    LICENSE_SCOPES and the authorization manifest must EXACTLY repeat the
    license evidence scope in its policy binding; the authorization scope
    must be one of AUTHORIZATION_SCOPES (e.g. s2_11_candidate_mapping_only).
    An article-only license scope NEVER satisfies the artifact code/data
    requirement (LICENSE_SCOPE_NOT_ARTIFACT_COVERING).
  * evidence paths are additionally checked after Path.resolve(): the
    resolved file must still live inside the resolved evidence root, so a
    symlink/junction escape is rejected (EVIDENCE_PATH_ESCAPE).

Provenance model (v5, verifiable): every mappable source element carries
its own element/key, field-level locator, source record ID, source text
hash, start/end span, span alignment source and mapping policy ID. The
locator is the deterministic rule `record_source_path + "#" + element`;
record-level paths never pass as field-level paths. The structural element
must EXACTLY equal the mapping source key; the modality element must
EXACTLY match the allowed norm-modality pattern `norms[<idx>].modality`.
Overlapping-span ambiguity is detected (str.count non-overlap semantics
cannot miss "aa" in "aaa").

Fail-closed error codes (BarrientosAdapterError subclasses):
  INVALID_MODE / LICENSE_NOT_QUALIFIED / ACTIVATION_NOT_AUTHORIZED /
  MAPPING_POLICY_NOT_APPROVED / SYNTHETIC_POLICY_IN_FORMAL_MODE /
  EVIDENCE_BINDING_MISSING / EVIDENCE_BINDING_SYNTHETIC /
  EVIDENCE_BINDING_INVALID / EVIDENCE_DOC_MISMATCH /
  EVIDENCE_PATH_ESCAPE / LICENSE_SCOPE_NOT_ARTIFACT_COVERING /
  AUTHORIZATION_BINDING_MISMATCH / AUTHORIZATION_EVENT_MISMATCH /
  INVALID_STRUCTURE / UNKNOWN_MODALITY /
  DEFINITION_NOT_PRODUCIBLE / MAPPING_POLICY_INCOMPLETE /
  INVALID_MAPPED_MODALITY / MISSING_TEXT_PROVENANCE /
  MISSING_SPAN_ALIGNMENT / INVALID_SPAN / AMBIGUOUS_SPAN /
  UNRESOLVED_CROSS_REFERENCE / NON_CANONICAL_TARGET / TARGET_COLLISION /
  FIELD_PROVENANCE_MISSING / FIELD_SPAN_INVALID / FIELD_SPAN_AMBIGUOUS /
  FIELD_VALUE_MISMATCH / NESTED_DICT_AS_SPAN_FIELD /
  ELEMENT_PATH_MISMATCH / INVALID_RECORD_IDENTITY
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

BARRIENTOS_MODALITY_CLASSES = frozenset(
    {"obligation", "permission", "prohibition"})
SUN_MODALITY_CLASSES = frozenset(
    {"obligation", "permission", "prohibition", "definition"})

# Canonical Sun span fields allowed as structural mapping targets.
CANONICAL_SPAN_FIELDS = frozenset(
    {"actor", "action", "condition", "constraint", "exception"})

# Strict mode enum (v5; extended in the user-authorized activation round):
# anything else is INVALID_MODE.
VALID_MODES = frozenset({
    "synthetic_test_only", "formal",
    # user-authorized local read-only research path (Checkpoint A/B):
    # the artifact license is UNKNOWN (never claimed verified), the user
    # authorized local read-only non-redistributive research use, and a
    # file-backed user_authorization evidence document (containment
    # policy) is required instead of license qualification.
    "local_read_only_research",
})

# Controlled scope enums (v6): scopes are never free-form strings.
# A license scope must be one of LICENSE_SCOPES; only the artifact-covering
# scopes may satisfy the artifact code/data requirement. An authorization
# manifest scope must be one of AUTHORIZATION_SCOPES.
LICENSE_SCOPES = frozenset({
    "article_only", "artifact_code", "artifact_code_data",
    "synthetic_test_only"})
AUTHORIZATION_SCOPES = frozenset({
    "s2_11_candidate_mapping_only", "synthetic_test_only",
    "local_read_only_nonredistributive_s2_11"})
ARTIFACT_COVERING_LICENSE_SCOPES = frozenset({
    "artifact_code", "artifact_code_data"})

AUTHORIZATION_EVENT_KIND = "s2_11_authorization_event"
USER_AUTHORIZATION_KIND = "user_authorization"
LOCAL_READ_ONLY_SCOPE = "local_read_only_nonredistributive_s2_11"

# The containment policy a user_authorization evidence document must carry
# EXACTLY (unknown license, user-authorized local read-only research use,
# redistribution/publication/references mutation forbidden).
REQUIRED_CONTAINMENT_POLICY: dict[str, Any] = {
    "artifact_license_verified": False,
    "artifact_license_status": "unknown_pending_confirmation",
    "local_read_only_research_use_authorized_by_user": True,
    "raw_redistribution_allowed": False,
    "raw_publication_allowed": False,
    "references_mutation_allowed": False,
    "formal_export_may_include_only_hashes_ids_aggregates_and_user_created_decisions": True,
}

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

# Exact allowed norm-modality element pattern (v5): "norms.modality" or
# "norms[<idx>].modality". A substring "norm" is NOT sufficient.
MODALITY_ELEMENT_RE = re.compile(r"^norms(?:\[\d+\])?\.modality$")

# Stable evidence ID format (v5): alnum start, then alnum/._- .
EVIDENCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

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


class InvalidModeError(BarrientosAdapterError):
    code = "INVALID_MODE"


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


class EvidenceBindingInvalidError(BarrientosAdapterError):
    code = "EVIDENCE_BINDING_INVALID"


class EvidenceDocMismatchError(BarrientosAdapterError):
    code = "EVIDENCE_DOC_MISMATCH"


class AuthorizationBindingMismatchError(BarrientosAdapterError):
    code = "AUTHORIZATION_BINDING_MISMATCH"


class EvidencePathEscapeError(BarrientosAdapterError):
    code = "EVIDENCE_PATH_ESCAPE"


class LicenseScopeNotArtifactCoveringError(BarrientosAdapterError):
    code = "LICENSE_SCOPE_NOT_ARTIFACT_COVERING"


class AuthorizationEventMismatchError(BarrientosAdapterError):
    code = "AUTHORIZATION_EVENT_MISMATCH"


class UserAuthorizationNotValidError(BarrientosAdapterError):
    code = "USER_AUTHORIZATION_NOT_VALID"


class InvalidStructureError(BarrientosAdapterError):
    code = "INVALID_STRUCTURE"


class InvalidRecordIdentityError(BarrientosAdapterError):
    code = "INVALID_RECORD_IDENTITY"


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
    qualified=False / artifact license unknown_pending_confirmation."""

    qualified: bool = False
    license_status: str = "unknown_pending_confirmation"


@dataclass(frozen=True)
class ActivationState:
    """Caller-supplied data-activation state. Current real state:
    authorized=False."""

    authorized: bool = False


@dataclass(frozen=True)
class EvidenceBinding:
    """Versioned, FILE-BACKED evidence binding required by FORMAL mode.

    `path` is a RELATIVE path under the evidence root (no absolute paths,
    no ".." traversal; after resolve() the file must still live inside the
    evidence root — symlink/junction escapes are rejected). The file must
    exist, its raw bytes must hash to `evidence_hash` (64 lowercase hex),
    and its JSON content must match kind/ID/scope (authorization manifests
    additionally bind the mapping policy exactly and an append-only
    authorization event). `scope` is the CONTROLLED scope the document
    must carry exactly: a LICENSE_SCOPES value for kind="license" and an
    AUTHORIZATION_SCOPES value for kind="authorization". `synthetic=True`
    marks a test fixture binding; synthetic bindings are never accepted in
    formal mode.
    """

    kind: str
    evidence_id: str
    evidence_hash: str
    path: str | None = None
    synthetic: bool = False
    scope: str | None = None


@dataclass(frozen=True)
class EvidenceContext:
    """Structured, RE-VERIFIED evidence context returned by the formal
    evidence verifier (v6). Built only from files re-read during the
    conversion; callers cannot supply or forge it."""

    license_doc: dict[str, Any]
    license_relative_path: str
    license_sha256: str
    authorization_doc: dict[str, Any]
    authorization_relative_path: str
    authorization_sha256: str
    authorization_event_doc: dict[str, Any]
    authorization_event_relative_path: str
    authorization_event_sha256: str
    modality_mapping_canonical_hash: str
    field_mapping_canonical_hash: str


@dataclass(frozen=True)
class LocalReadOnlyEvidenceContext:
    """Re-verified evidence context for the local_read_only_research mode:
    the artifact license is UNKNOWN and the USER AUTHORIZATION event (with
    the containment policy) is the authority for local non-redistributive
    research use."""

    user_authorization_doc: dict[str, Any]
    user_authorization_relative_path: str
    user_authorization_sha256: str
    modality_mapping_canonical_hash: str
    field_mapping_canonical_hash: str


@dataclass(frozen=True)
class MappingPolicy:
    """Caller-supplied, user-approved mapping policy.

    `modality_identity` maps a Barrientos 3-class modality to a Sun 4-class
    modality. `field_mapping` maps a source structure element key to a
    canonical Sun span field; it stays empty until a separate user decision
    exists (M1 never implies structural mapping).
    `license_evidence_binding` / `authorization_manifest_binding` are
    required in formal mode, must not be synthetic, and must be verified
    against real files under the evidence root.
    """

    policy_id: str
    approved: bool = False
    synthetic_test_only: bool = False
    modality_identity: Mapping[str, str] = field(default_factory=dict)
    field_mapping: Mapping[str, str] = field(default_factory=dict)
    license_evidence_binding: EvidenceBinding | None = None
    authorization_manifest_binding: EvidenceBinding | None = None
    user_authorization_binding: EvidenceBinding | None = None


def field_locator(record_source_path: str, element: str) -> str:
    """Deterministic field-level locator rule (v5): the record source path
    plus the element, joined with '#'. A record-level path can never equal
    a field-level locator because the locator always contains '#'."""
    return f"{record_source_path}#{element}"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _overlap_occurrences(text: str, sub: str) -> int:
    """Count occurrences of `sub` in `text` INCLUDING overlapping starts
    (str.count is non-overlapping and would miss 'aa' inside 'aaa')."""
    if not sub:
        return 0
    return sum(1 for i in range(len(text) - len(sub) + 1)
               if text.startswith(sub, i))


def _check_mode(mode: str) -> None:
    if mode not in VALID_MODES:
        raise InvalidModeError(
            f"mode {mode!r} is not a valid adapter mode",
            detail=f"valid_modes={sorted(VALID_MODES)}")


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


def _canonical_mapping_hash(mapping: Mapping[str, str]) -> str:
    """Deterministic canonical SHA-256 of a mapping (sorted keys)."""
    payload = json.dumps(dict(sorted(mapping.items())), sort_keys=True,
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_within(root_resolved: Path, candidate_resolved: Path) -> bool:
    """True iff the RESOLVED candidate path is inside the RESOLVED root
    (symlink/junction escape detection; v6)."""
    try:
        return candidate_resolved.is_relative_to(root_resolved)
    except ValueError:  # pragma: no cover - different drive edge
        return False


def _resolve_evidence_path(root: Path, path: str) -> Path:
    """Lexically safe evidence path + resolved containment check.

    Rejects absolute paths, '..' traversal and backslash separators, then
    requires that the path RESOLVES (following symlinks/junctions) to a
    file still inside the resolved evidence root.
    """
    posix = PurePosixPath(path)
    if posix.is_absolute() or ".." in posix.parts or "\\" in path:
        raise EvidenceBindingInvalidError(
            "evidence path must be relative and must not traverse '..'",
            detail=f"path={path!r}")
    file_path = root / path
    resolved = file_path.resolve()
    root_resolved = root.resolve()
    if not _is_within(root_resolved, resolved):
        raise EvidencePathEscapeError(
            "evidence path resolves OUTSIDE the evidence root "
            "(symlink/junction escape)",
            detail=f"path={path!r} resolved={resolved}")
    return file_path


def _check_evidence_binding(binding: EvidenceBinding, expected_kind: str,
                            root: Path) -> dict[str, Any]:
    """Verify one FILE-BACKED evidence binding (formal mode) and return the
    re-verified evidence document."""
    if binding.kind != expected_kind:
        raise EvidenceBindingInvalidError(
            f"evidence binding kind {binding.kind!r} does not match "
            f"expected {expected_kind!r}",
            detail=f"kind={binding.kind!r}")
    if not isinstance(binding.evidence_id, str) or \
            not EVIDENCE_ID_RE.fullmatch(binding.evidence_id):
        raise EvidenceBindingInvalidError(
            "evidence ID must be a stable alnum identifier",
            detail=f"evidence_id={binding.evidence_id!r}")
    if not isinstance(binding.evidence_hash, str) or \
            not SHA256_RE.fullmatch(binding.evidence_hash):
        raise EvidenceBindingInvalidError(
            "evidence hash must be a 64-char lowercase hex SHA-256",
            detail=f"evidence_hash={binding.evidence_hash!r}")
    path = binding.path
    if not isinstance(path, str) or not path.strip():
        raise EvidenceBindingInvalidError(
            "evidence binding requires a relative evidence path",
            detail=f"path={path!r}")
    file_path = _resolve_evidence_path(root, path)
    if not file_path.is_file():
        raise EvidenceBindingInvalidError(
            "evidence file does not exist under the evidence root",
            detail=f"path={path!r}")
    actual = _sha256_file(file_path)
    if actual != binding.evidence_hash:
        raise EvidenceBindingInvalidError(
            "evidence file raw bytes do not hash to the declared SHA-256",
            detail=f"declared={binding.evidence_hash[:12]}... "
                   f"actual={actual[:12]}...")
    try:
        doc = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceBindingInvalidError(
            "evidence file is not readable JSON",
            detail=f"error={exc!r}")
    if not isinstance(doc, dict):
        raise EvidenceBindingInvalidError(
            "evidence document must be a JSON object",
            detail=f"type={type(doc).__name__}")
    if doc.get("kind") != expected_kind:
        raise EvidenceDocMismatchError(
            "evidence document internal kind does not match the binding",
            detail=f"doc_kind={doc.get('kind')!r} expected={expected_kind!r}")
    doc_id = doc.get("event_id" if expected_kind == USER_AUTHORIZATION_KIND
                     else "evidence_id")
    if doc_id != binding.evidence_id:
        raise EvidenceDocMismatchError(
            "evidence document internal ID does not match the binding",
            detail=f"doc_id={doc_id!r} "
                   f"binding_id={binding.evidence_id!r}")
    # Controlled scope enum + EXACT scope match (v6).
    if expected_kind == "license":
        scope = doc.get("scope")
        if not isinstance(scope, str) or scope not in LICENSE_SCOPES:
            raise EvidenceDocMismatchError(
                "license evidence scope must be one of the controlled "
                "LICENSE_SCOPES",
                detail=f"scope={scope!r} allowed={sorted(LICENSE_SCOPES)}")
        if scope != binding.scope:
            raise EvidenceDocMismatchError(
                "license evidence scope does not EXACTLY match the binding",
                detail=f"doc_scope={scope!r} binding_scope={binding.scope!r}")
    elif expected_kind == USER_AUTHORIZATION_KIND:
        scope = doc.get("authorization_scope")
        if not isinstance(scope, str) or scope not in AUTHORIZATION_SCOPES:
            raise EvidenceDocMismatchError(
                "user authorization scope must be one of the controlled "
                "AUTHORIZATION_SCOPES",
                detail=f"authorization_scope={scope!r} "
                       f"allowed={sorted(AUTHORIZATION_SCOPES)}")
        if scope != binding.scope:
            raise EvidenceDocMismatchError(
                "user authorization scope does not EXACTLY match the "
                "binding",
                detail=f"doc_scope={scope!r} binding_scope={binding.scope!r}")
    else:
        scope = doc.get("scope")
        if not isinstance(scope, str) or scope not in AUTHORIZATION_SCOPES:
            raise EvidenceDocMismatchError(
                "authorization scope must be one of the controlled "
                "AUTHORIZATION_SCOPES",
                detail=f"scope={scope!r} "
                       f"allowed={sorted(AUTHORIZATION_SCOPES)}")
        if scope != binding.scope:
            raise EvidenceDocMismatchError(
                "authorization scope does not EXACTLY match the binding",
                detail=f"doc_scope={scope!r} binding_scope={binding.scope!r}")
    return doc


def _check_authorization_event(doc: dict[str, Any],
                               binding: EvidenceBinding,
                               root: Path) -> dict[str, Any]:
    """Verify the append-only authorization event bound by the manifest
    (v6) and return the re-verified event document."""
    event_id = doc.get("authorization_event_id")
    event_sha = doc.get("authorization_event_sha256")
    event_path_raw = doc.get("authorization_event_path")
    if not isinstance(event_id, str) or not EVIDENCE_ID_RE.fullmatch(event_id):
        raise AuthorizationEventMismatchError(
            "authorization manifest must bind a stable authorization "
            "event ID",
            detail=f"event_id={event_id!r}")
    if not isinstance(event_sha, str) or not SHA256_RE.fullmatch(event_sha):
        raise AuthorizationEventMismatchError(
            "authorization manifest must bind the authorization event "
            "raw-byte SHA-256",
            detail=f"event_sha256={event_sha!r}")
    if not isinstance(event_path_raw, str) or not event_path_raw.strip():
        raise AuthorizationEventMismatchError(
            "authorization manifest must bind an authorization event "
            "relative path",
            detail=f"event_path={event_path_raw!r}")
    event_path = _resolve_evidence_path(root, event_path_raw)
    if not event_path.is_file():
        raise AuthorizationEventMismatchError(
            "authorization event file does not exist under the evidence "
            "root",
            detail=f"path={event_path_raw!r}")
    actual_sha = _sha256_file(event_path)
    if actual_sha != event_sha:
        raise AuthorizationEventMismatchError(
            "authorization event raw bytes do not hash to the manifest "
            "binding",
            detail=f"declared={event_sha[:12]}... actual={actual_sha[:12]}...")
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthorizationEventMismatchError(
            "authorization event is not readable JSON",
            detail=f"error={exc!r}")
    if not isinstance(event, dict):
        raise AuthorizationEventMismatchError(
            "authorization event must be a JSON object",
            detail=f"type={type(event).__name__}")
    if event.get("kind") != AUTHORIZATION_EVENT_KIND:
        raise AuthorizationEventMismatchError(
            "authorization event internal kind does not match the "
            "approved event kind",
            detail=f"kind={event.get('kind')!r}")
    if event.get("event_id") != event_id:
        raise AuthorizationEventMismatchError(
            "authorization event internal ID does not match the manifest "
            "binding",
            detail=f"event_id={event.get('event_id')!r} bound={event_id!r}")
    if event.get("authorization_sentence") != doc.get(
            "authorization_sentence"):
        raise AuthorizationEventMismatchError(
            "authorization event must carry the EXACT authorization "
            "sentence of the manifest",
            detail="event sentence differs from the manifest sentence")
    if event.get("manifest_id") != doc.get("evidence_id"):
        raise AuthorizationEventMismatchError(
            "authorization event must reference the authorizing manifest "
            "ID",
            detail=f"event_manifest={event.get('manifest_id')!r} "
                   f"manifest={doc.get('evidence_id')!r}")
    if event.get("append_only") is not True:
        raise AuthorizationEventMismatchError(
            "authorization event must be append-only",
            detail=f"append_only={event.get('append_only')!r}")
    return event


def _check_authorization_manifest(doc: dict[str, Any],
                                  binding: EvidenceBinding,
                                  mapping_policy: MappingPolicy,
                                  license_binding: EvidenceBinding,
                                  license_doc: dict[str, Any],
                                  root: Path) -> dict[str, Any]:
    policy_binding = doc.get("policy_binding")
    if not isinstance(policy_binding, dict):
        raise AuthorizationBindingMismatchError(
            "authorization manifest must carry a policy_binding object",
            detail=f"policy_binding={policy_binding!r}")
    if policy_binding.get("policy_id") != mapping_policy.policy_id:
        raise AuthorizationBindingMismatchError(
            "authorization manifest policy_id does not match the mapping "
            "policy",
            detail=f"manifest={policy_binding.get('policy_id')!r} "
                   f"policy={mapping_policy.policy_id!r}")
    manifest_modality = policy_binding.get("modality_mapping")
    if manifest_modality != dict(mapping_policy.modality_identity):
        raise AuthorizationBindingMismatchError(
            "authorization manifest modality mapping does not match the "
            "mapping policy",
            detail=f"manifest={manifest_modality!r} "
                   f"policy={dict(mapping_policy.modality_identity)!r}")
    manifest_fields = policy_binding.get("field_mapping")
    if manifest_fields != dict(mapping_policy.field_mapping):
        raise AuthorizationBindingMismatchError(
            "authorization manifest field mapping does not match the "
            "mapping policy",
            detail=f"manifest={manifest_fields!r} "
                   f"policy={dict(mapping_policy.field_mapping)!r}")
    if policy_binding.get("license_evidence_hash") != \
            license_binding.evidence_hash:
        raise AuthorizationBindingMismatchError(
            "authorization manifest does not bind the license evidence "
            "hash",
            detail=f"manifest="
                   f"{policy_binding.get('license_evidence_hash')!r} "
                   f"license={license_binding.evidence_hash[:12]}...")
    if policy_binding.get("license_evidence_id") != \
            license_binding.evidence_id:
        raise AuthorizationBindingMismatchError(
            "authorization manifest does not bind the license evidence ID",
            detail=f"manifest="
                   f"{policy_binding.get('license_evidence_id')!r} "
                   f"license={license_binding.evidence_id!r}")
    # The manifest must EXACTLY repeat the license evidence scope (v6).
    if policy_binding.get("license_evidence_scope") != \
            license_doc.get("scope"):
        raise AuthorizationBindingMismatchError(
            "authorization manifest must EXACTLY repeat the license "
            "evidence scope",
            detail=f"manifest="
                   f"{policy_binding.get('license_evidence_scope')!r} "
                   f"license={license_doc.get('scope')!r}")
    if not isinstance(doc.get("scope"), str) or \
            doc["scope"] not in AUTHORIZATION_SCOPES:
        raise AuthorizationBindingMismatchError(
            "authorization manifest scope must be one of the controlled "
            "AUTHORIZATION_SCOPES",
            detail=f"scope={doc.get('scope')!r} "
                   f"allowed={sorted(AUTHORIZATION_SCOPES)}")
    if not isinstance(doc.get("authorization_sentence"), str) or \
            not doc["authorization_sentence"].strip():
        raise AuthorizationBindingMismatchError(
            "authorization manifest must carry an authorization sentence",
            detail="authorization_sentence missing or empty")
    event = _check_authorization_event(doc, binding, root)
    return event


def _check_user_authorization(doc: dict[str, Any],
                              binding: EvidenceBinding) -> None:
    """Verify the user_authorization evidence document (local_read_only_
    research mode, Checkpoint A/B): the containment policy must match the
    required values EXACTLY — an unknown license is never claimed
    verified, raw redistribution/publication and references mutation stay
    forbidden, and only local read-only research use is authorized."""
    if doc.get("authorization_scope") != LOCAL_READ_ONLY_SCOPE:
        raise UserAuthorizationNotValidError(
            "user authorization scope must EXACTLY equal the controlled "
            "local_read_only_nonredistributive_s2_11 scope",
            detail=f"scope={doc.get('authorization_scope')!r}")
    cp = doc.get("containment_policy")
    if not isinstance(cp, dict):
        raise UserAuthorizationNotValidError(
            "user authorization must carry a containment_policy object",
            detail=f"containment_policy={cp!r}")
    for key, want in sorted(REQUIRED_CONTAINMENT_POLICY.items()):
        if cp.get(key) != want:
            raise UserAuthorizationNotValidError(
                f"containment policy field {key!r} does not match the "
                "required value",
                detail=f"declared={cp.get(key)!r} required={want!r}")
    instruction_hash = doc.get("user_instruction_utf8_sha256")
    if not isinstance(instruction_hash, str) or \
            not SHA256_RE.fullmatch(instruction_hash):
        raise UserAuthorizationNotValidError(
            "user authorization must bind a 64-hex user-instruction "
            "SHA-256",
            detail=f"user_instruction_utf8_sha256={instruction_hash!r}")
    if doc.get("append_only") is not True:
        raise UserAuthorizationNotValidError(
            "user authorization event must be append-only",
            detail=f"append_only={doc.get('append_only')!r}")


def _check_policy(mapping_policy: MappingPolicy, mode: str,
                  evidence_root: Path | None) -> Any:
    _check_mode(mode)
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
        if evidence_root is None:
            raise EvidenceBindingMissingError(
                "formal mode requires an evidence_root directory",
                detail="evidence_root=None")
        if license_binding.synthetic or auth_binding.synthetic:
            raise EvidenceBindingSyntheticError(
                "synthetic evidence bindings must never enter formal mode",
                detail=f"license_synthetic={license_binding.synthetic}, "
                       f"auth_synthetic={auth_binding.synthetic}")
        license_doc = _check_evidence_binding(license_binding, "license",
                                              evidence_root)
        # An article-only license scope NEVER satisfies the artifact
        # code/data requirement (v6).
        license_scope = license_doc.get("scope")
        if license_scope not in ARTIFACT_COVERING_LICENSE_SCOPES:
            raise LicenseScopeNotArtifactCoveringError(
                "formal mode requires an artifact-covering license scope; "
                "an article-only scope does NOT cover the artifact "
                "code/data",
                detail=f"license_scope={license_scope!r} "
                       f"allowed={sorted(ARTIFACT_COVERING_LICENSE_SCOPES)}")
        auth_doc = _check_evidence_binding(
            auth_binding, "authorization", evidence_root)
        event_doc = _check_authorization_manifest(
            auth_doc, auth_binding, mapping_policy, license_binding,
            license_doc, evidence_root)
        return EvidenceContext(
            license_doc=license_doc,
            license_relative_path=str(license_binding.path),
            license_sha256=license_binding.evidence_hash,
            authorization_doc=auth_doc,
            authorization_relative_path=str(auth_binding.path),
            authorization_sha256=auth_binding.evidence_hash,
            authorization_event_doc=event_doc,
            authorization_event_relative_path=str(
                auth_doc.get("authorization_event_path")),
            authorization_event_sha256=str(
                auth_doc.get("authorization_event_sha256")),
            modality_mapping_canonical_hash=_canonical_mapping_hash(
                mapping_policy.modality_identity),
            field_mapping_canonical_hash=_canonical_mapping_hash(
                mapping_policy.field_mapping),
        )
    if mode == "local_read_only_research":
        user_binding = mapping_policy.user_authorization_binding
        if user_binding is None:
            raise EvidenceBindingMissingError(
                "local_read_only_research mode requires the file-backed "
                "user authorization binding (the artifact license is "
                "unknown and is NOT claimed verified)",
                detail="user_authorization_binding=None")
        if evidence_root is None:
            raise EvidenceBindingMissingError(
                "local_read_only_research mode requires an evidence_root "
                "directory",
                detail="evidence_root=None")
        if user_binding.synthetic:
            raise EvidenceBindingSyntheticError(
                "synthetic evidence bindings must never enter a real "
                "activation mode",
                detail="user_authorization_binding.synthetic=True")
        user_doc = _check_evidence_binding(
            user_binding, USER_AUTHORIZATION_KIND, evidence_root)
        _check_user_authorization(user_doc, user_binding)
        return LocalReadOnlyEvidenceContext(
            user_authorization_doc=user_doc,
            user_authorization_relative_path=str(user_binding.path),
            user_authorization_sha256=user_binding.evidence_hash,
            modality_mapping_canonical_hash=_canonical_mapping_hash(
                mapping_policy.modality_identity),
            field_mapping_canonical_hash=_canonical_mapping_hash(
                mapping_policy.field_mapping),
        )
    return None


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


def _check_record_identity(record: Mapping[str, Any]) -> None:
    record_id = record.get("source_record_id")
    source_path = record.get("source_path")
    if not isinstance(record_id, str) or not record_id.strip() or \
            record_id == "None":
        raise InvalidRecordIdentityError(
            "source_record_id must be a non-empty legal string",
            detail=f"source_record_id={record_id!r}")
    if not isinstance(source_path, str) or not source_path.strip() or \
            source_path == "None":
        raise InvalidRecordIdentityError(
            "record-level source_path must be a non-empty legal string",
            detail=f"source_path={source_path!r}")
    if "#" in source_path:
        raise InvalidRecordIdentityError(
            "record-level source_path must not contain the locator "
            "separator '#'",
            detail=f"source_path={source_path!r}")


def _validate_element_descriptor(descriptor: Any, where: str,
                                 record: Mapping[str, Any],
                                 expected_element: str,
                                 require_value_match: bool = True,
                                 ) -> dict[str, Any]:
    """Validate one source-element descriptor (field-level provenance).

    `expected_element` must EXACTLY equal the descriptor element (the
    mapping source key for structural fields, or the allowed norm-modality
    element for modality). The descriptor path must equal the deterministic
    field locator `record_source_path#element`.
    """
    if not isinstance(descriptor, Mapping):
        raise FieldProvenanceMissingError(
            f"{where} has no provenance descriptor",
            detail=f"descriptor={descriptor!r}")
    if set(descriptor) != REQUIRED_ELEMENT_KEYS:
        unknown = sorted(set(descriptor) - REQUIRED_ELEMENT_KEYS)
        missing = sorted(REQUIRED_ELEMENT_KEYS - set(descriptor))
        raise FieldProvenanceMissingError(
            f"{where} descriptor keys are not exactly the required set",
            detail=f"missing={missing} unknown={unknown}")
    element = descriptor.get("element")
    if element != expected_element:
        raise ElementPathMismatchError(
            f"{where} element must exactly equal {expected_element!r}",
            detail=f"element={element!r}")
    path = descriptor.get("path")
    record_path = record.get("source_path")
    expected_locator = field_locator(str(record_path), str(element))
    if path != expected_locator:
        raise ElementPathMismatchError(
            f"{where} path must equal the deterministic field locator "
            f"{expected_locator!r}",
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
    if not isinstance(span, Mapping):
        raise FieldSpanInvalidError(
            f"{where} span must be a mapping",
            detail=f"span={span!r}")
    start, end = span.get("start"), span.get("end")
    if not isinstance(start, int) or isinstance(start, bool) or \
            not isinstance(end, int) or isinstance(end, bool):
        raise FieldSpanInvalidError(
            f"{where} span start/end must be integers (bool is not an "
            "offset)",
            detail=f"start={start!r} end={end!r}")
    text = str(record.get("text", ""))
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
    if _overlap_occurrences(text, span_text) != 1:
        raise FieldSpanAmbiguousError(
            f"{where} aligned span text is not unique (overlapping "
            "occurrences included)",
            detail=f"span_text={span_text!r} "
                   f"occurrences={_overlap_occurrences(text, span_text)}")
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
    if not isinstance(element, str) or \
            not MODALITY_ELEMENT_RE.fullmatch(element):
        raise ElementPathMismatchError(
            "modality element must exactly match the allowed norm-modality "
            "pattern norms[<idx>].modality",
            detail=f"modality.element={element!r}")
    prov = _validate_element_descriptor(modality, "modality", record,
                                        expected_element=element,
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
                          mapping_policy: MappingPolicy) -> tuple[
                              dict[str, Any], dict[str, Any], list[str]]:
    """Map ONLY the structure elements listed in the approved field
    mapping, each with its OWN field-level provenance. The descriptor
    element must EXACTLY equal the mapping source key."""
    mapped: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    warnings: list[str] = []
    structure = record.get("structure", {})
    declared = set(structure)
    for src_key, target in sorted(mapping_policy.field_mapping.items()):
        if src_key not in declared:
            continue
        descriptor = structure[src_key]
        prov = _validate_element_descriptor(
            descriptor, src_key, record, expected_element=src_key)
        mapped[target] = descriptor["value"]
        provenance[target] = {
            "source_element": prov["element"],
            "source_locator": prov["path"],
            "source_path": str(record["source_path"]),
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
        mode: str = "synthetic_test_only",
        evidence_root: Path | None = None) -> dict[str, Any]:
    """Convert one Barrientos-style source record into a CANDIDATE Rule
    Record (candidate_only / review_candidate semantics, never Gold).

    Deterministic: mapped fields, provenance entries and warnings are
    emitted in sorted order. Raises a typed :class:`BarrientosAdapterError`
    with a machine-decodable code on any fail-closed condition.
    """
    _check_mode(mode)
    if mode == "local_read_only_research":
        # The artifact license is UNKNOWN by design in this mode; the
        # user authorization + containment policy is the authority.
        if license_state.license_status != "unknown_pending_confirmation":
            raise LicenseNotQualifiedError(
                "local_read_only_research mode requires the license to be "
                "unknown_pending_confirmation (never claimed verified)",
                detail=f"license_status={license_state.license_status!r}")
    else:
        _check_license(license_state)
    _check_activation(activation_state)
    evidence_context = _check_policy(mapping_policy, mode, evidence_root)
    _check_structure(record)
    _check_record_identity(record)
    _check_field_policy(mapping_policy)
    _check_text_provenance(record)
    mapped_modality, modality_prov = _check_modality(record, mapping_policy)
    resolved_refs = _check_cross_references(record)
    mapped_fields, field_provenance, warnings = _map_structure_fields(
        record, mapping_policy)

    ordered_fields: dict[str, Any] = {"modality": mapped_modality}
    for target in sorted(mapped_fields):
        ordered_fields[target] = mapped_fields[target]

    full_provenance: dict[str, Any] = {
        "modality": {
            "source_element": modality_prov["element"],
            "source_locator": modality_prov["path"],
            "source_path": str(record["source_path"]),
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

    formal_evidence_provenance: dict[str, Any] | None = None
    if evidence_context is not None:
        if isinstance(evidence_context, LocalReadOnlyEvidenceContext):
            ua = evidence_context.user_authorization_doc
            cp = ua.get("containment_policy") or {}
            formal_evidence_provenance = {
                "mode": "local_read_only_research",
                "user_authorization": {
                    "event_id": ua["event_id"],
                    "relative_path":
                        evidence_context.user_authorization_relative_path,
                    "sha256": evidence_context.user_authorization_sha256,
                    "authorization_scope": ua["authorization_scope"],
                    "user_instruction_utf8_sha256":
                        ua["user_instruction_utf8_sha256"],
                },
                "containment_policy": dict(cp),
                "license_verified": False,
                "license_status": "unknown_pending_confirmation",
                "policy_id": mapping_policy.policy_id,
                "modality_mapping_canonical_hash":
                    evidence_context.modality_mapping_canonical_hash,
                "field_mapping_canonical_hash":
                    evidence_context.field_mapping_canonical_hash,
                "candidate_only": True,
                "gold_authorized": False,
            }
        else:
            lic = evidence_context.license_doc
            auth = evidence_context.authorization_doc
            ev = evidence_context.authorization_event_doc
            formal_evidence_provenance = {
            "license_evidence": {
                "evidence_id": lic["evidence_id"],
                "relative_path": evidence_context.license_relative_path,
                "sha256": evidence_context.license_sha256,
                "license_scope": lic["scope"],
            },
            "authorization_manifest": {
                "manifest_id": auth["evidence_id"],
                "relative_path": evidence_context.authorization_relative_path,
                "sha256": evidence_context.authorization_sha256,
                "authorization_scope": auth["scope"],
            },
            "authorization_event": {
                "event_id": ev["event_id"],
                "relative_path":
                    evidence_context.authorization_event_relative_path,
                "sha256": evidence_context.authorization_event_sha256,
            },
            "policy_id": mapping_policy.policy_id,
            "modality_mapping_canonical_hash":
                evidence_context.modality_mapping_canonical_hash,
            "field_mapping_canonical_hash":
                evidence_context.field_mapping_canonical_hash,
            "license_evidence_binding": (
                f"authorization manifest policy_binding binds "
                f"license_evidence_id={lic['evidence_id']} and "
                f"license_evidence_hash={evidence_context.license_sha256} "
                f"and license_evidence_scope={lic['scope']}"),
            "candidate_only": True,
            "gold_authorized": False,
        }

    return {
        "status": OUTPUT_STATUS,
        "semantics": OUTPUT_SEMANTICS,
        "source_record_id": str(record["source_record_id"]),
        "source_path": str(record["source_path"]),
        "mapped_fields": ordered_fields,
        "field_provenance": full_provenance,
        "mapping_policy_id": mapping_policy.policy_id,
        "formal_evidence_provenance": formal_evidence_provenance,
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
            "local_read_only_research": mode == "local_read_only_research",
            "raw_redistribution_allowed": False,
            "license_verified": False,
        },
    }
