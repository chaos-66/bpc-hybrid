"""Fail-closed S2.1-D gate for the Sun modality development dataset.

The gate deliberately avoids reopening the 470 MB CSV member.  It streams the
official ZIP once for SHA-1/SHA-256, reads the ZIP central directory for member
size/CRC, scans the small local records/splits, and cross-checks every aggregate
artifact against the versioned experiment contract.

Artifact hashing follows the contract-declared controlled-text hash policy
(G0-EOL-HASH-PORTABILITY): every artifact is verified on raw bytes unless its
contract entry explicitly declares ``hash_mode == "canonical_lf_utf8_text"``.
Only such declared assets are verified on CRLF-to-LF normalized UTF-8 text
bytes, so the same controlled text verifies identically in LF and CRLF
worktrees.  Binary ZIP, JSONL records/splits, and undeclared JSON aggregates
remain raw-byte verified; the mode is never guessed from a file extension.

This module is stdlib-only, offline, and performs no training or evaluation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


DATASET_CONTRACT_REL = "configs/datasets/sun_modality_dataset.json"
SOURCE_MANIFEST_REL = "data/development/sun_modality/source_manifest.json"
SOURCE_ZIP_REL = "data/development/sun_modality/raw/Decision_Logic_data.zip"
DEVELOPMENT_DIR_REL = "data/development/modality/sun_estg_modality_v1"
SCHEMA_AUDIT_REL = f"{DEVELOPMENT_DIR_REL}/schema_audit.json"
MANIFEST_REL = f"{DEVELOPMENT_DIR_REL}/manifest.json"
SUMMARY_REL = f"{DEVELOPMENT_DIR_REL}/split_summary.json"
QUARANTINE_REL = f"{DEVELOPMENT_DIR_REL}/quarantine_manifest.json"
RECORDS_REL = f"{DEVELOPMENT_DIR_REL}/records.jsonl"
SPLIT_RELS = {
    "train": f"{DEVELOPMENT_DIR_REL}/splits/train.jsonl",
    "dev": f"{DEVELOPMENT_DIR_REL}/splits/dev.jsonl",
    "test": f"{DEVELOPMENT_DIR_REL}/splits/test.jsonl",
}
EXPERIMENT_CONTRACT_REL = "configs/experiment_contract.json"
LOCAL_IGNORE_REL = f"{DEVELOPMENT_DIR_REL}/.gitignore"

# Contract-declared artifact hash modes (G0-EOL-HASH-PORTABILITY).
# The keys are the contract subtrees that carry each artifact's hash_mode;
# an artifact without an entry here is verified on raw bytes.  Only the
# explicit canonical_lf_utf8_text mode triggers CRLF-to-LF normalization;
# no mode is ever inferred from a file extension.
CANONICAL_TEXT_MODE = "canonical_lf_utf8_text"
HASH_MODE_KEYS: dict[str, tuple[str, ...]] = {
    SOURCE_MANIFEST_REL: ("source_manifest", "hash_mode"),
}


@dataclass(frozen=True)
class SunModalityExpectations:
    """Canonical facts that a config file cannot silently redefine."""

    zip_size: int = 191_874_718
    zip_sha1: str = "0346f84a246b7049d5aef58bcb33471435bee106"
    zip_sha256: str = "ada231f092927813ba9f1cd32a44a3d30d96b57fc463d042dfd76c652b6d58f2"
    csv_name: str = "EStG_sent_vec.csv"
    csv_size: int = 470_740_514
    csv_sha256: str = "1e53eb1b7f88f57c63029385eafe5e6f269bb7878328c0c409c5e708250ad5c3"
    csv_crc32: str = "A9E74EF5"
    source_population: int = 2_833
    analysis_population: int = 2_831
    quarantined_groups: int = 1
    quarantined_records: int = 2
    train_size: int = 1_985
    dev_size: int = 420
    test_size: int = 426
    seed: int = 20_260_715
    policy_name: str = "pre_result_conflicting_label_group_quarantine"
    policy_version: str = "sun_modality_conflict_quarantine@1.0.0"
    split_origin: str = "project_reconstructed_deterministic_split"
    rights_status: str = "unknown_pending_confirmation"
    sensitivity_status: str = "planned_not_run"
    contract_version: str = "sun_modality_dataset_contract@1.3.1"
    manifest_schema_version: str = "1.3.1"
    importer_version: str = "sun_modality_official_importer@1.1.1"
    label_distribution: tuple[tuple[str, int], ...] = (
        ("definition", 1190),
        ("obligation", 1273),
        ("permission", 264),
        ("prohibition", 104),
    )
    source_label_distribution: tuple[tuple[str, int], ...] = (
        ("definition", 1190),
        ("obligation", 1274),
        ("permission", 265),
        ("prohibition", 104),
    )
    quarantine_rows: tuple[int, ...] = (616, 1221)
    normalized_text_sha256: str = (
        "df79964183f7abc85e0878ecd73ee4157f800699b42ce7c2ebf1923b4d438d95"
    )
    raw_text_sha256: str = (
        "0289f3ff1d31a392cacb39109df10267297e1d8a184b356227beea4716d8a8d6"
    )
    labels_by_row: tuple[tuple[str, str], ...] = (
        ("616", "permission"),
        ("1221", "obligation"),
    )
    section_hashes_by_row: tuple[tuple[str, str], ...] = (
        ("616", "9309f67fd6480663a48cf90236ec14c1db61583825ac210112e2abf19e47d95c"),
        ("1221", "879ce2257ab3468f65bd6d50a1e56f9af8e75a80035cbb1019eced7c3a47db5b"),
    )

    @property
    def labels(self) -> dict[str, int]:
        return dict(self.label_distribution)

    @property
    def source_labels(self) -> dict[str, int]:
        return dict(self.source_label_distribution)

    @property
    def locked_labels_by_row(self) -> dict[str, str]:
        return dict(self.labels_by_row)

    @property
    def locked_section_hashes_by_row(self) -> dict[str, str]:
        return dict(self.section_hashes_by_row)


SUN_MODALITY_EXPECTATIONS = SunModalityExpectations()


_CHECK_KEYS = (
    "source_identity_ok",
    "contract_ok",
    "schema_ok",
    "population_ok",
    "quarantine_ok",
    "label_distribution_ok",
    "split_ok",
    "membership_hash_ok",
    "artifact_hashes_ok",
    "paths_portable",
    "local_data_ignored",
    "license_boundary_ok",
)
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_lf_digest(raw: bytes) -> str:
    """SHA-256 of LF-canonical UTF-8 text bytes.

    CRLF pairs are replaced with LF before hashing so the same controlled
    text verifies identically in LF and CRLF worktrees.  Anything that is
    not clean LF-canonical UTF-8 text -- invalid UTF-8, a NUL byte, or a
    bare CR that is not part of a CRLF pair -- raises ``ValueError`` and
    the gate fails closed.
    """
    if b"\x00" in raw:
        raise ValueError("contains a NUL byte")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"not valid UTF-8 ({exc})") from exc
    normalized = raw.replace(b"\r\n", b"\n")
    if b"\r" in normalized:
        raise ValueError("contains a bare CR (CR not part of a CRLF pair)")
    return hashlib.sha256(normalized).hexdigest()


def _canonical_lf_sha256(path: Path) -> str:
    """Raw-byte read plus :func:`_canonical_lf_digest` for a declared asset."""
    return _canonical_lf_digest(path.read_bytes())


def _zip_hashes(path: Path, chunk_size: int = 1 << 20) -> tuple[str, str]:
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            sha1.update(chunk)
            sha256.update(chunk)
    return sha1.hexdigest(), sha256.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _nested(value: Any, *keys: str, default: Any = None) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return default
        current = current[key]
    return current


def _canonical_membership_hash(records: Iterable[Mapping[str, Any]]) -> str:
    pairs = sorted((str(row.get("sample_id")), str(row.get("label"))) for row in records)
    blob = json.dumps(pairs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.blake2b(blob.encode("utf-8"), digest_size=32).hexdigest()


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, raw in enumerate(stream, 1):
            if not raw.strip():
                errors.append(f"blank JSONL line {line_number}")
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                errors.append(f"invalid JSONL line {line_number}")
                continue
            if not isinstance(value, dict):
                errors.append(f"non-object JSONL line {line_number}")
                continue
            rows.append(value)
    return rows, errors


def _is_portable_string(value: str) -> bool:
    lowered = value.lower()
    if lowered.startswith("file://") or _WINDOWS_ABSOLUTE.match(value):
        return False
    if value.startswith("\\\\"):
        return False
    return True


def _portable_tree(value: Any) -> bool:
    if isinstance(value, str):
        return _is_portable_string(value)
    if isinstance(value, Mapping):
        return all(_portable_tree(item) for item in value.values())
    if isinstance(value, list):
        return all(_portable_tree(item) for item in value)
    return True


def _resolve_project_relative(project_root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value or not _is_portable_string(value):
        return None
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        return None
    resolved = (project_root / Path(*path.parts)).resolve()
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError:
        return None
    return resolved


def _find_git_root(path: Path) -> Path | None:
    for candidate in (path.resolve(), *path.resolve().parents):
        if (candidate / ".git").exists():
            return candidate
    return None


class _GateChecks:
    def __init__(self) -> None:
        self.values = {key: True for key in _CHECK_KEYS}
        self.errors: list[dict[str, str]] = []
        self.blockers: list[str] = []

    def require(
        self,
        condition: bool,
        check: str | tuple[str, ...],
        code: str,
        message: str,
    ) -> bool:
        if condition:
            return True
        checks = (check,) if isinstance(check, str) else check
        for name in checks:
            self.values[name] = False
        if code not in self.blockers:
            self.blockers.append(code)
            self.errors.append({"code": code, "message": message})
        return False


def _entry_map(entries: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(entries, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            result[str(entry["path"])] = entry
    return result


def verify_sun_modality_development_data(
    project_root: Path,
    *,
    expectations: SunModalityExpectations = SUN_MODALITY_EXPECTATIONS,
) -> dict[str, Any]:
    """Cross-validate the locked local development dataset.

    ``expectations`` exists only so tiny synthetic fixtures can test every
    negative branch without copying the 192 MB official ZIP.  Production calls
    always use :data:`SUN_MODALITY_EXPECTATIONS`.
    """
    root = Path(project_root).resolve()
    checks = _GateChecks()
    relative_paths = (
        EXPERIMENT_CONTRACT_REL,
        SOURCE_MANIFEST_REL,
        DATASET_CONTRACT_REL,
        SCHEMA_AUDIT_REL,
        MANIFEST_REL,
        SUMMARY_REL,
        QUARANTINE_REL,
        RECORDS_REL,
        *SPLIT_RELS.values(),
        SOURCE_ZIP_REL,
        LOCAL_IGNORE_REL,
    )
    paths = {relative: root / relative for relative in relative_paths}
    checked_artifacts: list[dict[str, Any]] = []
    artifact_items: dict[str, dict[str, Any]] = {}
    actual_sha256: dict[str, str] = {}
    zip_actual_sha1 = ""
    zip_actual_sha256 = ""

    for relative in relative_paths:
        path = paths[relative]
        exists = path.is_file()
        item: dict[str, Any] = {"path": relative, "exists": exists}
        if exists:
            item["size_bytes"] = path.stat().st_size
            try:
                if relative == SOURCE_ZIP_REL:
                    zip_actual_sha1, zip_actual_sha256 = _zip_hashes(path)
                    actual_sha256[relative] = zip_actual_sha256
                    item["sha1"] = zip_actual_sha1
                    item["sha256"] = zip_actual_sha256
                elif path.name != ".gitignore":
                    actual_sha256[relative] = _sha256(path)
                    item["sha256"] = actual_sha256[relative]
            except OSError:
                checks.require(False, "artifact_hashes_ok", "artifact_unreadable", f"Cannot hash {relative}.")
        else:
            checks.require(
                False,
                "artifact_hashes_ok",
                "required_artifact_missing",
                f"Required modality artifact is missing: {relative}.",
            )
        checked_artifacts.append(item)
        artifact_items[relative] = item

    json_artifacts: dict[str, dict[str, Any]] = {}
    for relative in (
        EXPERIMENT_CONTRACT_REL,
        SOURCE_MANIFEST_REL,
        DATASET_CONTRACT_REL,
        SCHEMA_AUDIT_REL,
        MANIFEST_REL,
        SUMMARY_REL,
        QUARANTINE_REL,
    ):
        if not paths[relative].is_file():
            json_artifacts[relative] = {}
            continue
        try:
            json_artifacts[relative] = _load_json(paths[relative])
        except (OSError, ValueError, json.JSONDecodeError):
            json_artifacts[relative] = {}
            checks.require(False, "artifact_hashes_ok", "artifact_json_invalid", f"Invalid JSON artifact: {relative}.")

    experiment = json_artifacts[EXPERIMENT_CONTRACT_REL]
    source_manifest = json_artifacts[SOURCE_MANIFEST_REL]
    dataset = json_artifacts[DATASET_CONTRACT_REL]
    schema = json_artifacts[SCHEMA_AUDIT_REL]
    manifest = json_artifacts[MANIFEST_REL]
    summary = json_artifacts[SUMMARY_REL]
    quarantine = json_artifacts[QUARANTINE_REL]
    modality = _nested(experiment, "stage2_dataset", "modality_dataset", default={})
    if not isinstance(modality, dict):
        modality = {}

    # Controlled-text hash policy: read the contract-declared hash_mode for
    # each artifact.  Only an explicit canonical_lf_utf8_text declaration
    # switches an artifact to CRLF-to-LF normalized hashing; everything else
    # stays raw-byte verified.  Unknown declared modes and unnormalizable
    # text fail closed.
    declared_modes: dict[str, str] = {}
    canonical_digests: dict[str, str] = {}
    for relative, mode_keys in HASH_MODE_KEYS.items():
        mode = _nested(modality, *mode_keys)
        if mode is None:
            continue
        declared_modes[relative] = str(mode)
        if mode == CANONICAL_TEXT_MODE:
            try:
                canonical_digests[relative] = _canonical_lf_sha256(paths[relative])
            except (OSError, ValueError) as exc:
                canonical_digests[relative] = ""
                checks.require(
                    False,
                    "artifact_hashes_ok",
                    f"canonical_text_invalid:{relative}",
                    f"Declared canonical LF UTF-8 text asset is not clean LF-canonical text: {relative} ({exc}).",
                )
        else:
            checks.require(
                False,
                "artifact_hashes_ok",
                f"unknown_hash_mode:{relative}",
                f"Artifact {relative} declares an unsupported hash_mode {mode!r}; the only supported text mode is {CANONICAL_TEXT_MODE!r}.",
            )
    for relative, item in artifact_items.items():
        mode = declared_modes.get(relative)
        item["hash_mode"] = mode if mode is not None else "raw_bytes"
        if item["hash_mode"] == CANONICAL_TEXT_MODE:
            item["sha256_raw"] = actual_sha256.get(relative, "")
            item["sha256"] = canonical_digests.get(relative, "")

    # Source identity: stream only the ZIP and inspect its central directory.
    checks.require(paths[SOURCE_ZIP_REL].is_file(), "source_identity_ok", "source_zip_missing", "The official source ZIP is missing.")
    if paths[SOURCE_ZIP_REL].is_file():
        checks.require(paths[SOURCE_ZIP_REL].stat().st_size == expectations.zip_size, "source_identity_ok", "source_zip_size_mismatch", "Source ZIP size does not match the locked value.")
        checks.require(zip_actual_sha1 == expectations.zip_sha1, "source_identity_ok", "source_zip_sha1_mismatch", "Source ZIP SHA-1 does not match the locked official value.")
        checks.require(zip_actual_sha256 == expectations.zip_sha256, "source_identity_ok", "source_zip_sha256_mismatch", "Source ZIP SHA-256 does not match the locked local value.")
        try:
            with zipfile.ZipFile(paths[SOURCE_ZIP_REL], "r") as archive:
                member = archive.getinfo(expectations.csv_name)
            member_size = int(member.file_size)
            member_crc = f"{member.CRC:08X}"
        except (OSError, KeyError, zipfile.BadZipFile):
            member_size = -1
            member_crc = ""
            checks.require(False, "source_identity_ok", "source_zip_central_directory_invalid", "The source ZIP central directory or CSV member is invalid.")
        checks.require(member_size == expectations.csv_size, "source_identity_ok", "csv_member_size_mismatch", "CSV central-directory size does not match the locked value.")
        checks.require(member_crc == expectations.csv_crc32, "source_identity_ok", "csv_member_crc32_mismatch", "CSV central-directory CRC32 does not match the locked value.")
    else:
        member_size, member_crc = -1, ""

    source_asset = _nested(source_manifest, "primary_modality_asset", default={})
    source_hashes = _nested(source_asset, "local_computed_hashes_2026_07_15", default={})
    source_local = _nested(source_asset, "local_state_2026_07_15", default={})
    source_expected = _nested(source_asset, "expected_class_distribution", default={})
    identity_values = (
        dataset.get("source_zip_size_bytes") == expectations.zip_size,
        dataset.get("source_zip_official_sha1") == expectations.zip_sha1,
        dataset.get("source_zip_local_sha256") == expectations.zip_sha256,
        dataset.get("csv_member_logical_name") == expectations.csv_name,
        dataset.get("csv_member_size_uncompressed_bytes") == expectations.csv_size,
        dataset.get("csv_member_local_sha256") == expectations.csv_sha256,
        str(dataset.get("csv_member_crc32", "")).upper() == expectations.csv_crc32,
        source_asset.get("logical_name") == "Decision_Logic_data.zip",
        source_asset.get("official_sha1") == expectations.zip_sha1,
        _nested(source_manifest, "official_landing_page", "archive_org_metadata_user_supplied_2026_07_15", "expected_size") == expectations.zip_size,
        source_hashes.get("Decision_Logic_data.zip_sha1") == expectations.zip_sha1,
        source_hashes.get("Decision_Logic_data.zip_sha256") == expectations.zip_sha256,
        source_hashes.get("EStG_sent_vec.csv_sha256") == expectations.csv_sha256,
        source_hashes.get("EStG_sent_vec.csv_size_uncompressed") == expectations.csv_size,
        str(source_hashes.get("EStG_sent_vec.csv_crc32", "")).upper() == expectations.csv_crc32,
        source_local.get("local_zip_path") == SOURCE_ZIP_REL,
        manifest.get("source_asset", {}).get("local_sha256") == expectations.zip_sha256,
        manifest.get("source_asset", {}).get("official_sha1") == expectations.zip_sha1,
        manifest.get("source_asset", {}).get("csv_member_sha256") == expectations.csv_sha256,
        manifest.get("source_asset", {}).get("csv_member_size_uncompressed_bytes") == expectations.csv_size,
        str(manifest.get("source_asset", {}).get("csv_member_crc32", "")).upper() == expectations.csv_crc32,
        _nested(schema, "source_identity", "csv_member_sha256_actual") == expectations.csv_sha256,
        _nested(quarantine, "source_asset", "csv_member_sha256") == expectations.csv_sha256,
        _nested(modality, "source", "zip_sha1") == expectations.zip_sha1,
        _nested(modality, "source", "zip_sha256") == expectations.zip_sha256,
        _nested(modality, "source", "csv_member_sha256") == expectations.csv_sha256,
    )
    checks.require(all(identity_values), "source_identity_ok", "source_identity_crosscheck_failed", "Source manifest, dataset contract, development manifest, and experiment contract disagree on source identity.")

    # Contract and artifact-hash cross-checks.
    contract_sha = actual_sha256.get(DATASET_CONTRACT_REL, "")
    checks.require(dataset.get("contract_version") == expectations.contract_version, "contract_ok", "dataset_contract_version_mismatch", "Dataset contract patch version is not locked.")
    checks.require(manifest.get("schema_version") == expectations.manifest_schema_version, "contract_ok", "manifest_schema_version_mismatch", "Development manifest schema patch version is not locked.")
    checks.require(manifest.get("importer_version") == expectations.importer_version, "contract_ok", "official_importer_version_mismatch", "Official importer patch version is not locked.")
    checks.require(manifest.get("contract_version") == expectations.contract_version and quarantine.get("contract_version") == expectations.contract_version, "contract_ok", "derived_contract_version_mismatch", "Derived aggregates disagree with the dataset contract version.")
    checks.require(manifest.get("contract_sha256") == contract_sha and quarantine.get("contract_sha256") == contract_sha and _nested(modality, "dataset_contract", "sha256") == contract_sha, ("contract_ok", "artifact_hashes_ok"), "dataset_contract_hash_mismatch", "Dataset contract SHA-256 does not match all recorded references.")
    checks.require(modality.get("status") == "verified_development_split_locked" and modality.get("machine_gate_status") == "verified" and modality.get("formal_use") == "development_only_not_formal_gold", "contract_ok", "modality_contract_status_invalid", "Experiment contract modality status is not the exact S2.1-D intermediate state.")
    checks.require(_nested(experiment, "stage2_dataset", "status") == "locked_for_human_review", "contract_ok", "stage2_dataset_intermediate_status_invalid", "Top-level Stage 2 dataset status is not the required locked intermediate state.")

    expected_hash_entries = {
        SOURCE_MANIFEST_REL: _nested(modality, "source_manifest", "sha256"),
        DATASET_CONTRACT_REL: _nested(modality, "dataset_contract", "sha256"),
        SCHEMA_AUDIT_REL: _nested(modality, "schema_audit", "sha256"),
        MANIFEST_REL: _nested(modality, "manifest", "sha256"),
        SUMMARY_REL: _nested(modality, "split_summary", "sha256"),
        QUARANTINE_REL: _nested(modality, "quarantine_manifest", "sha256"),
        RECORDS_REL: _nested(modality, "records", "sha256"),
        SPLIT_RELS["train"]: _nested(modality, "splits", "train", "sha256"),
        SPLIT_RELS["dev"]: _nested(modality, "splits", "dev", "sha256"),
        SPLIT_RELS["test"]: _nested(modality, "splits", "test", "sha256"),
    }
    for relative, expected_hash in expected_hash_entries.items():
        if declared_modes.get(relative) == CANONICAL_TEXT_MODE:
            actual = canonical_digests.get(relative)
        else:
            actual = actual_sha256.get(relative)
        checks.require(
            isinstance(expected_hash, str)
            and bool(_HEX64.fullmatch(expected_hash))
            and actual == expected_hash,
            "artifact_hashes_ok",
            f"artifact_hash_mismatch:{relative}",
            f"Artifact SHA-256 mismatch: {relative}.",
        )
    checks.require(_nested(modality, "source_manifest", "path") == SOURCE_MANIFEST_REL and _nested(modality, "dataset_contract", "path") == DATASET_CONTRACT_REL, "contract_ok", "contract_artifact_paths_invalid", "Experiment contract source/dataset contract paths are not canonical project-relative paths.")
    source_manifest_sha = (
        canonical_digests.get(SOURCE_MANIFEST_REL)
        if declared_modes.get(SOURCE_MANIFEST_REL) == CANONICAL_TEXT_MODE
        else actual_sha256.get(SOURCE_MANIFEST_REL, "")
    )
    checks.require(source_manifest_sha == _nested(modality, "source_manifest", "sha256"), "artifact_hashes_ok", "source_manifest_hash_mismatch", "Source manifest SHA-256 does not match the experiment contract.")

    # Schema audit is trusted only after cross-checking immutable source facts.
    schema_identity = schema.get("source_identity", {})
    checks.require(schema.get("status") == "verified_with_pre_result_quarantine" and schema.get("development_import_allowed") is True and schema.get("hard_blockers") == [], "schema_ok", "schema_audit_status_invalid", "Schema audit is not in the verified quarantine state.")
    checks.require(_nested(schema, "csv_schema", "row_count") == expectations.source_population and _nested(schema, "csv_schema", "field_count_distribution", str(10)) == expectations.source_population, "schema_ok", "schema_audit_population_invalid", "Schema audit row/field-count evidence is inconsistent.")
    checks.require(schema_identity.get("zip_actual_sha1") == expectations.zip_sha1 and schema_identity.get("zip_actual_sha256") == expectations.zip_sha256 and schema_identity.get("csv_member_sha256_actual") == expectations.csv_sha256 and str(schema_identity.get("csv_member_crc32_actual", "")).upper() == expectations.csv_crc32, "schema_ok", "schema_source_identity_invalid", "Schema audit source identity does not match the locked bytes.")

    # Parse the local records/splits.  No raw payload is returned in failures.
    records: list[dict[str, Any]] = []
    split_rows: dict[str, list[dict[str, Any]]] = {name: [] for name in SPLIT_RELS}
    if paths[RECORDS_REL].is_file():
        records, record_errors = _read_jsonl(paths[RECORDS_REL])
        checks.require(not record_errors, "population_ok", "records_jsonl_invalid", "records.jsonl is structurally invalid.")
    for name, relative in SPLIT_RELS.items():
        if paths[relative].is_file():
            split_rows[name], split_errors = _read_jsonl(paths[relative])
            checks.require(not split_errors, "split_ok", f"{name}_split_jsonl_invalid", f"{name} split JSONL is structurally invalid.")

    record_ids = [row.get("sample_id") for row in records]
    record_map = {
        str(row.get("sample_id")): row
        for row in records
        if isinstance(row.get("sample_id"), str) and row.get("sample_id")
    }
    checks.require(len(records) == expectations.analysis_population and len(record_map) == len(records) and len(set(record_ids)) == len(records), "population_ok", "records_population_or_id_uniqueness_invalid", "records.jsonl row count or sample-ID uniqueness is invalid.")
    expected_split_sizes = {
        "train": expectations.train_size,
        "dev": expectations.dev_size,
        "test": expectations.test_size,
    }
    split_ids: dict[str, set[str]] = {}
    for name, rows in split_rows.items():
        ids = [str(row.get("sample_id")) for row in rows]
        split_ids[name] = set(ids)
        checks.require(len(rows) == expected_split_sizes[name] and len(ids) == len(set(ids)), "split_ok", f"{name}_split_size_or_duplicates_invalid", f"{name} split size or ID uniqueness is invalid.")
        checks.require(all(record_map.get(sample_id) == row for sample_id, row in zip(ids, rows)), "split_ok", f"{name}_split_record_mismatch", f"{name} split contains a row that is not byte-semantically identical to records.jsonl.")
    pairwise_disjoint = (
        split_ids.get("train", set()).isdisjoint(split_ids.get("dev", set()))
        and split_ids.get("train", set()).isdisjoint(split_ids.get("test", set()))
        and split_ids.get("dev", set()).isdisjoint(split_ids.get("test", set()))
    )
    union_ids = set().union(*split_ids.values()) if split_ids else set()
    checks.require(pairwise_disjoint, "split_ok", "split_id_overlap", "Train/dev/test sample IDs are not pairwise disjoint.")
    checks.require(union_ids == set(record_map), "split_ok", "split_union_incomplete", "Train/dev/test union does not equal records.jsonl.")
    normalized_locations: dict[str, set[str]] = {}
    for name, rows in split_rows.items():
        for row in rows:
            normalized_locations.setdefault(str(row.get("normalized_text")), set()).add(name)
    checks.require(all(len(locations) == 1 for locations in normalized_locations.values()), "split_ok", "normalized_text_cross_split_leakage", "A normalized-text group crosses split boundaries.")

    quarantined_rows = set(expectations.quarantine_rows)
    observed_source_rows = {
        row.get("source_row_index") for row in records
    } | {
        row.get("source_row_index") for rows in split_rows.values() for row in rows
    }
    checks.require(observed_source_rows.isdisjoint(quarantined_rows), ("split_ok", "quarantine_ok"), "quarantined_row_present_in_analysis", "A locked quarantine row appears in records or a split.")

    observed_labels: dict[str, int] = {}
    for row in records:
        label = str(row.get("label"))
        observed_labels[label] = observed_labels.get(label, 0) + 1
    checks.require(observed_labels == expectations.labels, "label_distribution_ok", "analysis_label_distribution_mismatch", "Analysis label distribution does not match the locked values.")
    distribution_values = (
        manifest.get("label_distribution_valid") == expectations.labels,
        manifest.get("label_distribution_in") == expectations.source_labels,
        summary.get("analysis_label_distribution") == expectations.labels,
        summary.get("source_label_distribution") == expectations.source_labels,
        quarantine.get("analysis_label_distribution") == expectations.labels,
        quarantine.get("source_label_distribution") == expectations.source_labels,
        _nested(schema, "labels", "actual_class_distribution")
        == expectations.source_labels,
        _nested(schema, "quarantine_policy_evaluation", "analysis_label_distribution") == expectations.labels,
        modality.get("label_distribution") == expectations.labels,
        {
            key: source_expected.get(key) for key in expectations.source_labels
        }
        == expectations.source_labels,
    )
    checks.require(all(distribution_values), "label_distribution_ok", "label_distribution_crosscheck_failed", "Aggregate artifacts disagree on the locked label distribution.")

    membership = _canonical_membership_hash(records)
    membership_values = (
        _nested(manifest, "membership_hash", "value"),
        _nested(summary, "membership_hash", "value"),
        modality.get("membership_hash"),
    )
    checks.require(all(value == membership for value in membership_values), "membership_hash_ok", "membership_hash_mismatch", "The recomputed membership hash does not match every aggregate reference.")

    population_expected = {
        "source_population_size": expectations.source_population,
        "analysis_population_size": expectations.analysis_population,
        "quarantined_group_count": expectations.quarantined_groups,
        "quarantined_record_count": expectations.quarantined_records,
    }
    population_values = (
        manifest.get("population"),
        summary.get("population"),
        quarantine.get("population"),
        modality.get("population"),
    )
    checks.require(all(value == population_expected for value in population_values), "population_ok", "population_crosscheck_failed", "Source/analysis/quarantine populations disagree across artifacts.")
    checks.require(
        _nested(dataset, "conflict_quarantine", "source_population_size")
        == expectations.source_population
        and _nested(dataset, "conflict_quarantine", "analysis_population_size")
        == expectations.analysis_population
        and _nested(dataset, "conflict_quarantine", "quarantined_group_count")
        == expectations.quarantined_groups
        and _nested(dataset, "conflict_quarantine", "quarantined_record_count")
        == expectations.quarantined_records,
        "population_ok",
        "dataset_contract_population_invalid",
        "Dataset contract quarantine populations do not match the locked values.",
    )
    checks.require(manifest.get("total_samples_in") == expectations.source_population and manifest.get("total_samples_valid") == expectations.analysis_population and manifest.get("total_samples_quarantined") == expectations.quarantined_records, "population_ok", "manifest_population_totals_invalid", "Manifest population totals are invalid.")

    expected_labels_by_row = expectations.locked_labels_by_row
    expected_sections = expectations.locked_section_hashes_by_row
    contract_group = (_nested(dataset, "conflict_quarantine", "locked_groups", default=[]) or [{}])[0]
    schema_group = (_nested(schema, "text", "label_conflicts", default=[]) or [{}])[0]
    quarantine_group = (quarantine.get("quarantined_groups") or [{}])[0]
    quarantine_values = (
        _nested(dataset, "conflict_quarantine", "conflict_policy") == expectations.policy_name,
        _nested(dataset, "conflict_quarantine", "policy_version") == expectations.policy_version,
        _nested(dataset, "conflict_quarantine", "raw_source_labels_modified") is False,
        manifest.get("conflict_policy", {}).get("name") == expectations.policy_name,
        manifest.get("conflict_policy", {}).get("policy_version") == expectations.policy_version,
        manifest.get("conflict_policy", {}).get("raw_source_labels_modified") is False,
        manifest.get("conflict_policy", {}).get("sensitivity_variant_status") == expectations.sensitivity_status,
        quarantine.get("policy_version") == expectations.policy_version,
        quarantine.get("policy", {}).get("conflict_policy") == expectations.policy_name,
        quarantine.get("policy", {}).get("raw_source_labels_modified") is False,
        _nested(quarantine, "sensitivity_full_source_variant", "status") == expectations.sensitivity_status,
        summary.get("sensitivity_full_source_variant_status") == expectations.sensitivity_status,
        _nested(modality, "quarantine", "policy") == expectations.policy_name,
        _nested(modality, "quarantine", "policy_version") == expectations.policy_version,
        _nested(modality, "quarantine", "raw_source_labels_modified") is False,
        _nested(modality, "sensitivity_variant", "status") == expectations.sensitivity_status,
    )
    checks.require(all(quarantine_values), "quarantine_ok", "quarantine_policy_crosscheck_failed", "Quarantine policy/version/raw-label/sensitivity state is inconsistent.")
    for name, group, label_key in (
        ("dataset contract", contract_group, "labels_by_row"),
        ("schema audit", schema_group, "labels_by_row"),
        ("quarantine manifest", quarantine_group, "original_labels_by_row"),
    ):
        group_ok = (
            group.get("row_indices") == list(expectations.quarantine_rows)
            and group.get("normalized_text_sha256") == expectations.normalized_text_sha256
            and group.get("raw_text_sha256") == expectations.raw_text_sha256
            and group.get(label_key) == expected_labels_by_row
            and group.get("section_reference_sha256_by_row") == expected_sections
        )
        checks.require(group_ok, "quarantine_ok", f"quarantine_descriptor_mismatch:{name}", f"Locked quarantine descriptor mismatch in {name}.")
    experiment_group_ok = (
        _nested(modality, "quarantine", "row_indices")
        == list(expectations.quarantine_rows)
        and _nested(modality, "quarantine", "normalized_text_sha256")
        == expectations.normalized_text_sha256
        and _nested(modality, "quarantine", "raw_text_sha256")
        == expectations.raw_text_sha256
        and _nested(modality, "quarantine", "labels_by_row")
        == expected_labels_by_row
    )
    checks.require(
        experiment_group_ok,
        "quarantine_ok",
        "quarantine_descriptor_mismatch:experiment_contract",
        "Locked quarantine descriptor mismatch in experiment contract.",
    )

    # Output-file entries must agree with actual bytes, rows, and each other.
    manifest_entries = _entry_map(manifest.get("output_files"))
    summary_entries = _entry_map(summary.get("output_files"))
    dev_relative = {
        RECORDS_REL: "records.jsonl",
        SPLIT_RELS["train"]: "splits/train.jsonl",
        SPLIT_RELS["dev"]: "splits/dev.jsonl",
        SPLIT_RELS["test"]: "splits/test.jsonl",
        QUARANTINE_REL: "quarantine_manifest.json",
    }
    expected_rows = {
        RECORDS_REL: expectations.analysis_population,
        SPLIT_RELS["train"]: expectations.train_size,
        SPLIT_RELS["dev"]: expectations.dev_size,
        SPLIT_RELS["test"]: expectations.test_size,
        QUARANTINE_REL: expectations.quarantined_records,
    }
    for project_relative, output_relative in dev_relative.items():
        manifest_entry = manifest_entries.get(output_relative, {})
        summary_entry = summary_entries.get(output_relative, {})
        entry_ok = (
            manifest_entry.get("sha256") == actual_sha256.get(project_relative)
            and summary_entry.get("sha256") == actual_sha256.get(project_relative)
            and manifest_entry.get("size_bytes") == paths[project_relative].stat().st_size
            if paths[project_relative].is_file()
            else False
        )
        entry_ok = bool(entry_ok) and manifest_entry.get("row_count") == expected_rows[project_relative] and summary_entry.get("row_count") == expected_rows[project_relative]
        checks.require(entry_ok, "artifact_hashes_ok", f"output_file_entry_mismatch:{output_relative}", f"Manifest/summary output entry mismatch: {output_relative}.")
    summary_manifest = summary_entries.get("manifest.json", {})
    checks.require(summary.get("manifest_sha256") == actual_sha256.get(MANIFEST_REL) and summary_manifest.get("sha256") == actual_sha256.get(MANIFEST_REL), "artifact_hashes_ok", "summary_manifest_hash_mismatch", "Split summary does not reference the actual manifest SHA-256.")

    # Path portability applies to all modality JSON artifacts; explicit path
    # fields must also resolve inside the project root.
    portable_json = all(_portable_tree(value) for value in json_artifacts.values())
    explicit_paths = (
        (manifest.get("contract_path"), DATASET_CONTRACT_REL, root),
        (_nested(manifest, "source_asset", "local_path"), SOURCE_ZIP_REL, root),
        (_nested(source_local, "local_zip_path"), SOURCE_ZIP_REL, root),
    )
    explicit_ok = True
    for value, expected_relative, base in explicit_paths:
        resolved = _resolve_project_relative(base, value)
        explicit_ok = explicit_ok and value == expected_relative and resolved == paths[expected_relative].resolve()
    for entry in manifest_entries.values():
        resolved = _resolve_project_relative(
            root / DEVELOPMENT_DIR_REL, entry.get("path")
        )
        explicit_ok = explicit_ok and resolved is not None
    checks.require(portable_json and explicit_ok, "paths_portable", "nonportable_versioned_path", "A modality JSON artifact contains a non-portable or out-of-root path.")

    # Local-only data must remain ignored.  The directory rule is always
    # checked; git check-ignore is added when a repository is available.
    ignore_path = paths[LOCAL_IGNORE_REL]
    ignore_text = ignore_path.read_text(encoding="utf-8") if ignore_path.is_file() else ""
    ignored = "records.jsonl" in ignore_text and "splits/*.jsonl" in ignore_text
    git_root = _find_git_root(root)
    if ignored and git_root is not None:
        for relative in (RECORDS_REL, *SPLIT_RELS.values()):
            completed = subprocess.run(
                ["git", "check-ignore", "--no-index", str(paths[relative])],
                cwd=git_root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            ignored = ignored and completed.returncode == 0
    checks.require(ignored, "local_data_ignored", "local_data_not_ignored", "records.jsonl or a split is not protected by the local ignore policy.")

    # Aggregates must not contain raw sentences or vectors.  Hash descriptors
    # are allowed; actual record text/normalized text is not.
    aggregate_values = (schema, manifest, summary, quarantine)
    aggregate_blob = json.dumps(aggregate_values, ensure_ascii=False, sort_keys=True)
    privacy_flags = (
        schema.get("contains_raw_text") is False,
        schema.get("contains_vectors") is False,
        summary.get("contains_raw_text") is False,
        summary.get("contains_vectors") is False,
        quarantine.get("contains_raw_text") is False,
        quarantine.get("contains_vectors") is False,
    )
    leaked_record_text = any(
        isinstance(row.get(key), str)
        and row.get(key)
        and str(row[key]) in aggregate_blob
        for row in records
        for key in ("text", "normalized_text")
    )
    checks.require(all(privacy_flags) and not leaked_record_text, "schema_ok", "aggregate_payload_leak", "A versioned aggregate contains raw sentence/vector payload or lacks negative payload flags.")

    # License and claim boundaries are deliberately independent of data
    # integrity: development verification never means formal/publication ready.
    source_license = _nested(source_asset, "license", default={})
    license_values = (
        dataset.get("license", {}).get("rights_status") == expectations.rights_status,
        dataset.get("license", {}).get("redistribution_allowed") is False,
        dataset.get("license", {}).get("publication_in_paper_allowed") is False,
        manifest.get("license", {}).get("rights_status") == expectations.rights_status,
        manifest.get("license", {}).get("redistribution_allowed") is False,
        manifest.get("license", {}).get("publication_in_paper_allowed") is False,
        source_license.get("rights_status") == expectations.rights_status,
        _nested(modality, "license", "rights_status") == expectations.rights_status,
        _nested(modality, "license", "redistribution_allowed") is False,
        _nested(modality, "license", "publication_allowed") is False,
        modality.get("formal_use") == "development_only_not_formal_gold",
        manifest.get("lifecycle", {}).get("stage") == "development",
        manifest.get("lifecycle", {}).get("ready_for_training") is False,
        manifest.get("lifecycle", {}).get("ready_for_evaluation") is False,
        manifest.get("lifecycle", {}).get("ready_for_publication") is False,
    )
    checks.require(all(license_values), "license_boundary_ok", "license_or_formal_use_boundary_relaxed", "License, redistribution, publication, training, evaluation, or formal-use boundary was relaxed.")
    split_origin_values = (
        manifest.get("split_origin"),
        summary.get("split_origin"),
        _nested(dataset, "outputs", "split_origin"),
        _nested(modality, "split", "origin"),
    )
    checks.require(all(value == expectations.split_origin for value in split_origin_values) and _nested(dataset, "outputs", "sun_original_split_claim_forbidden") is True and _nested(experiment, "route", "exact_reproduction") is False, ("contract_ok", "split_ok"), "split_origin_or_claim_boundary_invalid", "Split origin or exact-reproduction claim boundary is invalid.")
    checks.require(manifest.get("seed") == expectations.seed and summary.get("seed") == expectations.seed and _nested(modality, "split", "seed") == expectations.seed, "split_ok", "split_seed_mismatch", "Split seed is inconsistent.")

    ready = all(checks.values.values()) and not checks.errors
    return {
        "ready": ready,
        **checks.values,
        "errors": checks.errors,
        "blockers": checks.blockers,
        "checked_artifacts": checked_artifacts,
        "hash_policy": {
            "default_mode": "raw_bytes",
            "canonical_text_mode": CANONICAL_TEXT_MODE,
            "declared_canonical_text_assets": sorted(
                relative
                for relative, mode in declared_modes.items()
                if mode == CANONICAL_TEXT_MODE
            ),
        },
    }


def _fingerprint(project_root: Path) -> tuple[tuple[str, int, int], ...]:
    root = Path(project_root).resolve()
    relatives = (
        EXPERIMENT_CONTRACT_REL,
        SOURCE_MANIFEST_REL,
        DATASET_CONTRACT_REL,
        SCHEMA_AUDIT_REL,
        MANIFEST_REL,
        SUMMARY_REL,
        QUARANTINE_REL,
        RECORDS_REL,
        *SPLIT_RELS.values(),
        SOURCE_ZIP_REL,
        LOCAL_IGNORE_REL,
    )
    values: list[tuple[str, int, int]] = []
    for relative in relatives:
        path = root / relative
        try:
            stat = path.stat()
            values.append((relative, stat.st_size, stat.st_mtime_ns))
        except OSError:
            values.append((relative, -1, -1))
    return tuple(values)


@lru_cache(maxsize=8)
def _cached_verify(root: str, fingerprint: tuple[tuple[str, int, int], ...]) -> dict[str, Any]:
    del fingerprint
    return verify_sun_modality_development_data(Path(root))


def get_cached_sun_modality_gate(project_root: Path) -> dict[str, Any]:
    """Return a cache-safe gate result keyed by all relevant file metadata."""
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached_verify(str(root), _fingerprint(root)))
