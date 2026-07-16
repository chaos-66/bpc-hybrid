"""S2.1-C official Sun modality CSV audit and guarded development import.

The official CSV is headerless and about 470 MB uncompressed.  Every scan in
this module is streamed directly from ``ZipFile.open``; the CSV and its vector
payload are never extracted or materialised as one in-memory byte string.

The complete 2026-07-15 scan disproved two earlier head-only hypotheses:

* positional column 1 is not a 0--3 modality code (its values are 0--13);
* positional column 9 is not one 768-dimensional BERT vector.  It is a flat
  sequence of 300-dimensional word vectors, one vector per whitespace token.

The four modality labels are positional one-hot columns 4--7.  Their counts
uniquely match Michel et al. (2022), Table 1.  This is a project inference by
exact distribution match, not an author-supplied codebook.  A separate,
explicit integer-code adapter remains available and fails closed when its
mapping is missing or an unknown code is encountered.

S2.1-C-R1 retains fail-closed conflict handling by default.  The only allowed
exception is the user's pre-result policy for one contract-locked group: its
source, normalized/raw-text hashes, row indices, original labels, counts, and
post-quarantine distribution must all match exactly before both rows are
excluded from the main analysis population.  Neither raw label is modified.

This module is offline, stdlib-only, does not read environment variables, and
does not call a network service or LLM/API.
"""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import io
import json
import math
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import BinaryIO, Iterator, Mapping, Optional, Sequence, TextIO

from .sun_modality_importer import (
    IngestContract,
    IngestionError,
    LabelConflictError,
    OneHotError,
    OverwriteRefused,
    SchemaError,
    build_sample_id,
    check_cross_split_leakage,
    compute_file_sha1,
    compute_file_sha256,
    compute_membership_hash,
    compute_zip_member_sha256,
    deterministic_stratified_split,
    validate_label,
)


SCANNER_VERSION = "sun_modality_official_schema_audit@1.1.0"
IMPORTER_VERSION = "sun_modality_official_importer@1.1.1"
QUARANTINE_POLICY_NAME = "pre_result_conflicting_label_group_quarantine"


class OfficialSchemaError(IngestionError):
    """The headerless positional official schema is structurally invalid."""


class OfficialMappingError(IngestionError):
    """An explicit integer-code mapping is missing or cannot map a value."""

    code = "official_integer_mapping_error"


class OfficialVectorError(IngestionError):
    """An official vector field is malformed, non-finite, or wrong-sized."""


@dataclasses.dataclass(frozen=True)
class OfficialCsvSchema:
    encoding: str
    delimiter: str
    has_header: bool
    expected_field_count: int
    section_reference_column: int
    ordinal_column: int
    auxiliary_integer_column: int
    text_column: int
    label_columns: tuple[int, ...]
    label_classes: tuple[str, ...]
    auxiliary_binary_column: int
    vector_column: int
    vector_structure: str
    vector_element_dimension: int
    expected_row_count: int
    expected_label_distribution: Mapping[str, int]
    source_id_column: Optional[int] = None
    require_vector_token_count_match: bool = True

    def __post_init__(self) -> None:
        if self.has_header:
            raise OfficialSchemaError("official CSV must be configured as headerless")
        if self.delimiter != ",":
            raise OfficialSchemaError("official CSV delimiter must be an explicit comma")
        if len(self.label_columns) != len(self.label_classes):
            raise OfficialSchemaError("official label column/class lengths differ")
        positions = (
            self.section_reference_column,
            self.ordinal_column,
            self.auxiliary_integer_column,
            self.text_column,
            *self.label_columns,
            self.auxiliary_binary_column,
            self.vector_column,
        )
        if len(set(positions)) != len(positions):
            raise OfficialSchemaError("official positional columns overlap")
        if min(positions) < 0 or max(positions) >= self.expected_field_count:
            raise OfficialSchemaError("official positional column is out of range")
        if self.vector_element_dimension <= 0:
            raise OfficialSchemaError("vector_element_dimension must be positive")


@dataclasses.dataclass(frozen=True)
class OfficialParsedRow:
    row_index: int
    section_reference: str
    ordinal: int
    auxiliary_integer: int
    text: str
    normalized_text: str
    label: str
    label_one_hot: tuple[int, ...]
    auxiliary_binary: int
    vector_flat_length: int
    vector_token_count: int


@dataclasses.dataclass(frozen=True)
class OfficialRecordIdentity:
    sample_id: str
    label: str


def load_official_schema(contract: IngestContract) -> OfficialCsvSchema:
    """Load only explicitly locked positional fields from the data contract."""
    raw = contract.raw
    schema = raw.get("official_csv_schema")
    if not isinstance(schema, dict) or schema.get("status") != "verified":
        raise OfficialSchemaError(
            "official_csv_schema.status must be verified before official scanning"
        )
    vector = raw.get("official_vector_contract")
    if not isinstance(vector, dict) or vector.get("status") != "verified":
        raise OfficialSchemaError(
            "official_vector_contract.status must be verified before official scanning"
        )
    one_hot = raw.get("official_positional_one_hot_mapping")
    if not isinstance(one_hot, dict) or one_hot.get("status") != "verified":
        raise OfficialSchemaError(
            "official positional one-hot mapping must be verified before scanning"
        )
    columns = schema.get("columns")
    if not isinstance(columns, dict):
        raise OfficialSchemaError("official_csv_schema.columns must be an object")
    label_columns = one_hot.get("column_to_label")
    if not isinstance(label_columns, dict):
        raise OfficialSchemaError("official one-hot column_to_label must be an object")
    ordered_positions = tuple(sorted(int(position) for position in label_columns))
    ordered_labels = tuple(str(label_columns[str(position)]) for position in ordered_positions)
    return OfficialCsvSchema(
        encoding=str(schema["encoding"]),
        delimiter=str(schema["delimiter"]),
        has_header=bool(schema["has_header"]),
        expected_field_count=int(schema["field_count"]),
        section_reference_column=int(columns["section_reference_candidate"]),
        ordinal_column=int(columns["ordinal_candidate"]),
        auxiliary_integer_column=int(columns["auxiliary_integer_metadata"]),
        text_column=int(columns["text_de"]),
        label_columns=ordered_positions,
        label_classes=ordered_labels,
        auxiliary_binary_column=int(columns["auxiliary_binary_metadata"]),
        vector_column=int(columns["flattened_word_vectors"]),
        vector_structure=str(vector["vector_structure"]),
        vector_element_dimension=int(vector["vector_element_dimension"]),
        expected_row_count=int(schema["row_count"]),
        expected_label_distribution={
            str(key): int(value)
            for key, value in raw["label_taxonomy"][
                "expected_class_distribution_from_paper"
            ].items()
        },
        source_id_column=(
            None if schema.get("source_id_column") is None
            else int(schema["source_id_column"])
        ),
        require_vector_token_count_match=bool(
            vector.get("require_whitespace_token_count_match", True)
        ),
    )


def official_integer_code_label_adapter(
    raw_code: str,
    mapping: Optional[Mapping[str, str]],
    canonical_labels: Sequence[str],
) -> str:
    """Map an integer code only through a caller-supplied explicit mapping.

    This seam is deliberately fail-closed.  It is not used for the verified
    official CSV because the complete scan found no integer modality column.
    """
    if not mapping:
        raise OfficialMappingError(
            "mapping_missing: official integer-code mapping is null or empty"
        )
    value = (raw_code or "").strip()
    try:
        int(value)
    except ValueError as exc:
        raise OfficialMappingError(
            f"invalid_integer_code: {raw_code!r} is not an integer"
        ) from exc
    if value not in mapping:
        raise OfficialMappingError(f"unknown_integer_code: {value!r}")
    label = str(mapping[value])
    if label not in canonical_labels:
        raise OfficialMappingError(
            f"mapped_unknown_label: code {value!r} maps to {label!r}"
        )
    return label


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _evaluate_quarantine_policy(
    contract: IngestContract,
    *,
    source_asset_sha256: str,
    source_population_size: int,
    source_label_distribution: Mapping[str, int],
    conflict_descriptors: Sequence[Mapping[str, object]],
) -> dict:
    """Evaluate an exact, contract-locked conflict quarantine policy.

    A policy never means "skip conflicts".  Every observed descriptor must
    exactly equal the versioned locked descriptor, and the source hash,
    population sizes, group/record counts, and post-quarantine distribution
    must all match.  Any discrepancy leaves the conflict fail-closed.
    """
    raw_policy = contract.raw.get("conflict_quarantine")
    configured = (
        isinstance(raw_policy, dict)
        and raw_policy.get("status") == "authorized_locked"
        and raw_policy.get("conflict_policy") == QUARANTINE_POLICY_NAME
    )
    observed_record_count = sum(
        len(descriptor.get("row_indices", [])) for descriptor in conflict_descriptors
    )
    result = {
        "policy": (
            QUARANTINE_POLICY_NAME if configured else "fail_closed"
        ),
        "policy_version": (
            str(raw_policy.get("policy_version")) if configured else None
        ),
        "configured": configured,
        "authorized": False,
        "status": "not_needed" if not conflict_descriptors else "fail_closed",
        "mismatch_reasons": [],
        "source_population_size": source_population_size,
        "analysis_population_size": source_population_size,
        "quarantined_group_count": 0,
        "quarantined_record_count": 0,
        "quarantined_row_indices": [],
        "analysis_label_distribution": {
            str(label): int(count)
            for label, count in sorted(source_label_distribution.items())
        },
    }
    if not conflict_descriptors:
        return result
    if not configured:
        result["mismatch_reasons"] = ["authorized_locked_policy_missing"]
        return result

    assert isinstance(raw_policy, dict)
    mismatches: list[str] = []
    if str(raw_policy.get("source_asset_sha256", "")) != source_asset_sha256:
        mismatches.append("source_asset_sha256_mismatch")
    if int(raw_policy.get("source_population_size", -1)) != source_population_size:
        mismatches.append("source_population_size_mismatch")
    if int(raw_policy.get("quarantined_group_count", -1)) != len(
        conflict_descriptors
    ):
        mismatches.append("quarantined_group_count_mismatch")
    if int(raw_policy.get("quarantined_record_count", -1)) != observed_record_count:
        mismatches.append("quarantined_record_count_mismatch")

    locked_groups = raw_policy.get("locked_groups")
    if not isinstance(locked_groups, list):
        locked_groups = []
        mismatches.append("locked_groups_missing")

    def exact_group_view(group: Mapping[str, object]) -> dict:
        labels_by_row = group.get("labels_by_row", {})
        section_hashes = group.get("section_reference_sha256_by_row", {})
        return {
            "normalized_text_sha256": group.get("normalized_text_sha256"),
            "raw_text_sha256": group.get("raw_text_sha256"),
            "raw_text_hashes_equal": group.get("raw_text_hashes_equal"),
            "row_indices": sorted(int(value) for value in group.get("row_indices", [])),
            "labels": sorted(str(value) for value in group.get("labels", [])),
            "labels_by_row": {
                str(key): str(value)
                for key, value in sorted(
                    dict(labels_by_row).items(), key=lambda item: int(item[0])
                )
            },
            "section_reference_sha256_by_row": {
                str(key): str(value)
                for key, value in sorted(
                    dict(section_hashes).items(), key=lambda item: int(item[0])
                )
            },
        }

    observed_views = sorted(
        (exact_group_view(group) for group in conflict_descriptors),
        key=lambda group: str(group["normalized_text_sha256"]),
    )
    locked_views = sorted(
        (exact_group_view(group) for group in locked_groups),
        key=lambda group: str(group["normalized_text_sha256"]),
    )
    if observed_views != locked_views:
        mismatches.append("locked_group_descriptor_mismatch")

    analysis_distribution = Counter(
        {str(label): int(count) for label, count in source_label_distribution.items()}
    )
    quarantined_rows: list[int] = []
    for descriptor in conflict_descriptors:
        quarantined_rows.extend(int(value) for value in descriptor["row_indices"])
        for label in dict(descriptor["labels_by_row"]).values():
            analysis_distribution[str(label)] -= 1
    computed_analysis_distribution = {
        label: int(analysis_distribution.get(label, 0))
        for label in contract.label_classes
    }
    expected_analysis_distribution = {
        str(label): int(count)
        for label, count in dict(
            raw_policy.get("analysis_label_distribution", {})
        ).items()
    }
    if computed_analysis_distribution != expected_analysis_distribution:
        mismatches.append("analysis_label_distribution_mismatch")
    computed_analysis_size = source_population_size - observed_record_count
    if int(raw_policy.get("analysis_population_size", -1)) != computed_analysis_size:
        mismatches.append("analysis_population_size_mismatch")
    if raw_policy.get("raw_source_labels_modified") is not False:
        mismatches.append("raw_source_labels_modified_must_be_false")
    if raw_policy.get("quarantine_decision_timing") != (
        "before_any_model_training_or_result"
    ):
        mismatches.append("quarantine_decision_timing_mismatch")

    result.update(
        {
            "mismatch_reasons": mismatches,
            "analysis_population_size": computed_analysis_size,
            "quarantined_group_count": len(conflict_descriptors),
            "quarantined_record_count": observed_record_count,
            "quarantined_row_indices": sorted(quarantined_rows),
            "analysis_label_distribution": computed_analysis_distribution,
        }
    )
    if not mismatches:
        result["authorized"] = True
        result["status"] = "exact_locked_group_match"
    else:
        result["status"] = "contract_mismatch_fail_closed"
    return result


def parse_flat_vector(
    raw_vector: str,
    *,
    element_dimension: Optional[int] = None,
    expected_flat_dimension: Optional[int] = None,
    expected_token_count: Optional[int] = None,
) -> tuple[int, int]:
    """Validate a bracketed comma-separated vector without retaining values.

    Returns ``(flat_length, element_count)``.  ``element_count`` is the number
    of fixed-width elements when ``element_dimension`` is supplied, otherwise
    it equals ``flat_length``.
    """
    value = (raw_vector or "").strip()
    if not value:
        raise OfficialVectorError("missing_vector")
    if not (value.startswith("[") and value.endswith("]")):
        raise OfficialVectorError("vector must be enclosed in square brackets")
    body = value[1:-1].strip()
    if not body:
        raise OfficialVectorError("empty_vector")
    cells = [cell.strip() for cell in body.split(",")]
    if any(not cell for cell in cells):
        raise OfficialVectorError("vector contains an empty numeric cell")
    for cell in cells:
        try:
            number = float(cell)
        except ValueError as exc:
            raise OfficialVectorError(
                f"non_numeric_vector_value: {cell!r}"
            ) from exc
        if not math.isfinite(number):
            raise OfficialVectorError(f"non_finite_vector_value: {cell!r}")
    flat_length = len(cells)
    if expected_flat_dimension is not None and flat_length != expected_flat_dimension:
        raise OfficialVectorError(
            f"unexpected_flat_vector_dimension: {flat_length}; "
            f"expected {expected_flat_dimension}"
        )
    if element_dimension is None:
        element_count = flat_length
    else:
        if element_dimension <= 0:
            raise OfficialVectorError("element_dimension must be positive")
        if flat_length % element_dimension:
            raise OfficialVectorError(
                f"flat vector length {flat_length} is not a multiple of "
                f"element_dimension {element_dimension}"
            )
        element_count = flat_length // element_dimension
    if expected_token_count is not None and element_count != expected_token_count:
        raise OfficialVectorError(
            f"vector_token_count_mismatch: {element_count}; "
            f"expected {expected_token_count}"
        )
    return flat_length, element_count


def _source_identity_report(contract: IngestContract) -> dict:
    zip_path = contract.source_zip_path
    actual_sha1 = compute_file_sha1(zip_path)
    actual_sha256 = compute_file_sha256(zip_path)
    with zipfile.ZipFile(zip_path, "r") as archive:
        corrupt_member = archive.testzip()
        try:
            info = archive.getinfo(contract.csv_member_logical_name)
        except KeyError as exc:
            raise OfficialSchemaError(
                f"missing CSV member {contract.csv_member_logical_name!r}"
            ) from exc
    member_sha256 = compute_zip_member_sha256(
        zip_path, contract.csv_member_logical_name
    )
    report = {
        "zip_size_actual": zip_path.stat().st_size,
        "zip_size_expected": contract.source_zip_size_bytes,
        "zip_size_match": zip_path.stat().st_size == contract.source_zip_size_bytes,
        "zip_actual_sha1": actual_sha1,
        "zip_expected_official_sha1": contract.source_zip_official_sha1,
        "zip_official_sha1_match": actual_sha1 == contract.source_zip_official_sha1,
        "zip_actual_sha256": actual_sha256,
        "zip_expected_local_sha256": contract.source_zip_sha256,
        "zip_local_sha256_match": actual_sha256 == contract.source_zip_sha256,
        "zip_testzip_clean": corrupt_member is None,
        "csv_member": contract.csv_member_logical_name,
        "csv_member_sha256_actual": member_sha256,
        "csv_member_sha256_expected": contract.csv_member_sha256,
        "csv_member_sha256_match": member_sha256 == contract.csv_member_sha256,
        "csv_member_size_actual": info.file_size,
        "csv_member_size_expected": contract.csv_member_size_uncompressed_bytes,
        "csv_member_size_match": (
            info.file_size == contract.csv_member_size_uncompressed_bytes
        ),
        "csv_member_crc32_actual": f"{info.CRC:08X}",
        "csv_member_crc32_expected": contract.csv_member_crc32,
        "csv_member_crc32_match": (
            f"{info.CRC:08X}" == contract.csv_member_crc32.upper()
        ),
    }
    if not all(
        report[key]
        for key in (
            "zip_size_match",
            "zip_official_sha1_match",
            "zip_local_sha256_match",
            "zip_testzip_clean",
            "csv_member_sha256_match",
            "csv_member_size_match",
            "csv_member_crc32_match",
        )
    ):
        raise OfficialSchemaError(f"official source identity mismatch: {report}")
    return report


def _scan_text_stream(
    stream: TextIO,
    *,
    schema: OfficialCsvSchema,
    contract: IngestContract,
    source_asset_sha256: str,
) -> tuple[dict, list[OfficialParsedRow]]:
    csv.field_size_limit(sys.maxsize)
    reader = csv.reader(stream, delimiter=schema.delimiter)
    field_counts: Counter[int] = Counter()
    source_candidate_counts: Counter[str] = Counter()
    ordinal_values: Counter[int] = Counter()
    auxiliary_integer_values: Counter[int] = Counter()
    auxiliary_binary_values: Counter[int] = Counter()
    label_distribution: Counter[str] = Counter()
    one_hot_distribution: Counter[tuple[int, ...]] = Counter()
    flat_lengths: Counter[int] = Counter()
    normalized_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    records: list[OfficialParsedRow] = []
    row_count = 0
    empty_rows = 0
    short_rows = 0
    long_rows = 0
    empty_text_rows = 0
    metadata_parse_errors = 0
    label_errors = 0
    vector_errors = 0
    nonfinite_vector_rows = 0
    vector_token_mismatch_rows = 0

    for row_index, row in enumerate(reader):
        row_count += 1
        field_counts[len(row)] += 1
        if not row:
            empty_rows += 1
            continue
        if len(row) < schema.expected_field_count:
            short_rows += 1
            continue
        if len(row) > schema.expected_field_count:
            long_rows += 1
            continue

        section_reference = row[schema.section_reference_column].strip()
        source_candidate_counts[section_reference] += 1
        try:
            ordinal = int(row[schema.ordinal_column].strip())
            auxiliary_integer = int(row[schema.auxiliary_integer_column].strip())
            auxiliary_binary = int(row[schema.auxiliary_binary_column].strip())
        except ValueError:
            metadata_parse_errors += 1
            continue
        ordinal_values[ordinal] += 1
        auxiliary_integer_values[auxiliary_integer] += 1
        auxiliary_binary_values[auxiliary_binary] += 1

        text = row[schema.text_column].strip()
        normalized_text = contract.normalize_for_dedup(text)
        if not text or not normalized_text:
            empty_text_rows += 1
            continue

        label_cells = [row[position].strip() for position in schema.label_columns]
        try:
            label, _, _ = validate_label(
                label_cells,
                schema.label_classes,
                reject_all_zero=True,
                reject_multi_hot=True,
                reject_non_binary=True,
            )
        except (OneHotError, SchemaError):
            label_errors += 1
            continue
        bits = tuple(int(float(cell)) for cell in label_cells)
        label_distribution[label] += 1
        one_hot_distribution[bits] += 1
        normalized_groups[normalized_text].append(
            {
                "row_index": row_index,
                "label": label,
                "raw_text_sha256": _sha256_text(text),
                "section_reference_sha256": _sha256_text(section_reference),
            }
        )

        token_count = len(text.split())
        try:
            flat_length, vector_token_count = parse_flat_vector(
                row[schema.vector_column],
                element_dimension=schema.vector_element_dimension,
                expected_token_count=(
                    token_count if schema.require_vector_token_count_match else None
                ),
            )
        except OfficialVectorError as exc:
            vector_errors += 1
            message = str(exc)
            if "non_finite" in message:
                nonfinite_vector_rows += 1
            if "token_count_mismatch" in message:
                vector_token_mismatch_rows += 1
            continue
        flat_lengths[flat_length] += 1
        records.append(
            OfficialParsedRow(
                row_index=row_index,
                section_reference=section_reference,
                ordinal=ordinal,
                auxiliary_integer=auxiliary_integer,
                text=text,
                normalized_text=normalized_text,
                label=label,
                label_one_hot=bits,
                auxiliary_binary=auxiliary_binary,
                vector_flat_length=flat_length,
                vector_token_count=vector_token_count,
            )
        )

    duplicate_groups = {
        normalized: values
        for normalized, values in normalized_groups.items()
        if len(values) > 1
    }
    conflicts = {
        normalized: values
        for normalized, values in duplicate_groups.items()
        if len({str(value["label"]) for value in values}) > 1
    }
    conflict_descriptors = [
        {
            "normalized_text_sha256": _sha256_text(normalized),
            "raw_text_sha256": (
                next(iter({str(value["raw_text_sha256"]) for value in values}))
                if len({str(value["raw_text_sha256"]) for value in values}) == 1
                else None
            ),
            "raw_text_hashes_equal": (
                len({str(value["raw_text_sha256"]) for value in values}) == 1
            ),
            "row_indices": sorted(int(value["row_index"]) for value in values),
            "labels": sorted({str(value["label"]) for value in values}),
            "labels_by_row": {
                str(value["row_index"]): str(value["label"])
                for value in sorted(values, key=lambda item: int(item["row_index"]))
            },
            "section_reference_sha256_by_row": {
                str(value["row_index"]): str(value["section_reference_sha256"])
                for value in sorted(values, key=lambda item: int(item["row_index"]))
            },
            "section_reference_hashes_distinct": (
                len(
                    {
                        str(value["section_reference_sha256"])
                        for value in values
                    }
                )
                == len(values)
            ),
        }
        for normalized, values in sorted(conflicts.items())
    ]
    expected_distribution = {
        label: int(schema.expected_label_distribution[label])
        for label in schema.label_classes
    }
    actual_distribution = {
        label: int(label_distribution.get(label, 0))
        for label in schema.label_classes
    }
    hard_blockers: list[dict] = []
    if row_count != schema.expected_row_count:
        hard_blockers.append(
            {
                "code": "row_count_mismatch",
                "actual": row_count,
                "expected": schema.expected_row_count,
            }
        )
    structural_errors = (
        empty_rows
        + short_rows
        + long_rows
        + empty_text_rows
        + metadata_parse_errors
        + label_errors
        + vector_errors
    )
    if structural_errors:
        hard_blockers.append(
            {"code": "invalid_official_rows", "count": structural_errors}
        )
    if actual_distribution != expected_distribution:
        hard_blockers.append(
            {
                "code": "class_distribution_mismatch",
                "actual": actual_distribution,
                "expected": expected_distribution,
            }
        )
    quarantine_evaluation = _evaluate_quarantine_policy(
        contract,
        source_asset_sha256=source_asset_sha256,
        source_population_size=row_count,
        source_label_distribution=actual_distribution,
        conflict_descriptors=conflict_descriptors,
    )
    if conflicts and not quarantine_evaluation["authorized"]:
        hard_blockers.append(
            {
                "code": "normalized_text_label_conflict",
                "group_count": len(conflicts),
                "row_count": sum(len(values) for values in conflicts.values()),
            }
        )
        if quarantine_evaluation["configured"]:
            hard_blockers.append(
                {
                    "code": "quarantine_policy_mismatch",
                    "mismatch_reasons": quarantine_evaluation[
                        "mismatch_reasons"
                    ],
                }
            )

    source_unique_count = len(source_candidate_counts)
    source_duplicate_rows = sum(
        count - 1 for count in source_candidate_counts.values() if count > 1
    )
    if schema.source_id_column is not None:
        if schema.source_id_column != schema.section_reference_column:
            hard_blockers.append(
                {
                    "code": "unsupported_explicit_source_id_position",
                    "position": schema.source_id_column,
                }
            )
        if source_candidate_counts.get("", 0):
            hard_blockers.append(
                {
                    "code": "missing_explicit_source_id",
                    "count": int(source_candidate_counts[""]),
                }
            )
        if source_duplicate_rows:
            hard_blockers.append(
                {
                    "code": "duplicate_explicit_source_id",
                    "duplicate_rows_beyond_first": source_duplicate_rows,
                }
            )
    ordinal_set = sorted(ordinal_values)
    flat_dimension_768_rows = int(flat_lengths.get(768, 0))
    report = {
        "schema_audit_version": SCANNER_VERSION,
        "task_id": "S2.1-C",
        "status": (
            "verified_with_pre_result_quarantine"
            if not hard_blockers and quarantine_evaluation["authorized"]
            else ("verified" if not hard_blockers else "blocked")
        ),
        "deterministic": True,
        "contains_raw_text": False,
        "contains_vectors": False,
        "source_asset_sha256": contract.source_zip_sha256,
        "csv_member_sha256": contract.csv_member_sha256,
        "csv_schema": {
            "encoding": schema.encoding,
            "decode_errors": 0,
            "delimiter": schema.delimiter,
            "has_header": schema.has_header,
            "row_count": row_count,
            "expected_row_count": schema.expected_row_count,
            "field_count_distribution": {
                str(width): int(count) for width, count in sorted(field_counts.items())
            },
            "empty_rows": empty_rows,
            "short_rows": short_rows,
            "long_rows": long_rows,
        },
        "columns": [
            {"position": schema.section_reference_column, "meaning": "section_reference_candidate", "type": "nonempty alphanumeric string", "author_field_name_available": False},
            {"position": schema.ordinal_column, "meaning": "ordinal_candidate_not_modality", "type": "integer", "minimum": min(ordinal_set) if ordinal_set else None, "maximum": max(ordinal_set) if ordinal_set else None, "author_field_name_available": False},
            {"position": schema.auxiliary_integer_column, "meaning": "auxiliary_integer_metadata", "type": "integer", "minimum": min(auxiliary_integer_values) if auxiliary_integer_values else None, "maximum": max(auxiliary_integer_values) if auxiliary_integer_values else None, "author_field_name_available": False},
            {"position": schema.text_column, "meaning": "sentence_text_de", "type": "nonempty string"},
            *[
                {"position": position, "meaning": f"label_{label}_bit", "type": "binary integer"}
                for position, label in zip(schema.label_columns, schema.label_classes)
            ],
            {"position": schema.auxiliary_binary_column, "meaning": "auxiliary_binary_metadata_unknown", "type": "binary integer", "author_field_name_available": False},
            {"position": schema.vector_column, "meaning": "flattened_word_vectors", "type": "bracketed finite float list"},
        ],
        "source_id": {
            "explicit_source_id_column": schema.source_id_column,
            "candidate_column": schema.section_reference_column,
            "candidate_nonempty_count": row_count - source_candidate_counts.get("", 0),
            "candidate_unique_count": source_unique_count,
            "candidate_duplicate_rows_beyond_first": source_duplicate_rows,
            "candidate_is_unique": source_unique_count == row_count,
            "sample_id_source": (
                "explicit_source_id"
                if schema.source_id_column is not None
                else "row_index_fallback"
            ),
            "fallback_required": schema.source_id_column is None,
        },
        "integer_modality_code_hypothesis": {
            "candidate_column": schema.ordinal_column,
            "actual_integer_values": ordinal_set,
            "actual_integer_value_counts": {
                str(value): int(ordinal_values[value]) for value in ordinal_set
            },
            "expected_if_modality_code": [0, 1, 2, 3],
            "is_integer_modality_code": ordinal_set == [0, 1, 2, 3],
            "mapping": None,
            "status": "not_applicable_verified_no_integer_modality_column",
        },
        "labels": {
            "mode": "headerless_positional_strict_one_hot",
            "column_to_label": {
                str(position): label
                for position, label in zip(schema.label_columns, schema.label_classes)
            },
            "one_hot_pattern_counts": {
                "".join(str(bit) for bit in bits): int(count)
                for bits, count in sorted(one_hot_distribution.items())
            },
            "actual_class_distribution": actual_distribution,
            "paper_class_distribution": expected_distribution,
            "exact_distribution_match": actual_distribution == expected_distribution,
            "mapping_evidence_level": "inferred_by_exact_distribution_match",
            "author_codebook_found": False,
            "project_inference_not_original_codebook": True,
            "evidence": [
                "references/papers/Michel_2022_Decision_rules.pdf p.5 Table 1",
                "references/papers/Sun_2024_Design_time_BPC.pdf p.15 section 5.1.1 (class names only; not a positional codebook)",
            ],
            "semantic_sanity_check": {
                "performed_local_only": True,
                "samples_stored_in_versioned_artifacts": False,
                "result": "consistent_with_distribution_inference",
            },
        },
        "text": {
            "empty_rows": empty_text_rows,
            "normalized_text_group_count": len(normalized_groups),
            "normalized_text_duplicate_group_count": len(duplicate_groups),
            "normalized_text_duplicate_rows_beyond_first": sum(
                len(values) - 1 for values in duplicate_groups.values()
            ),
            "same_label_duplicate_group_count": sum(
                len({str(value["label"]) for value in values}) == 1
                for values in duplicate_groups.values()
            ),
            "label_conflict_group_count": len(conflicts),
            "label_conflict_row_count": sum(
                len(values) for values in conflicts.values()
            ),
            "label_conflicts": conflict_descriptors,
        },
        "quarantine_policy_evaluation": quarantine_evaluation,
        "vectors": {
            "vector_structure": schema.vector_structure,
            "vector_element_dimension": schema.vector_element_dimension,
            "flat_length_distinct_count": len(flat_lengths),
            "flat_length_minimum": min(flat_lengths) if flat_lengths else None,
            "flat_length_maximum": max(flat_lengths) if flat_lengths else None,
            "rows_with_flat_dimension_768": flat_dimension_768_rows,
            "all_rows_exactly_768": flat_dimension_768_rows == row_count,
            "all_flat_lengths_multiple_of_element_dimension": vector_errors == 0,
            "whitespace_token_count_mismatch_rows": vector_token_mismatch_rows,
            "missing_or_malformed_vector_rows": vector_errors,
            "nonfinite_vector_rows": nonfinite_vector_rows,
            "use_for_training": "pending_stage2_4",
            "evidence": "Michel_2022_Decision_rules.pdf p.5 and section 3.3.2 describe 300-dimensional word vectors",
        },
        "auxiliary_metadata": {
            "ordinal_unique_count": len(ordinal_values),
            "auxiliary_integer_unique_count": len(auxiliary_integer_values),
            "auxiliary_binary_counts": {
                str(value): int(count)
                for value, count in sorted(auxiliary_binary_values.items())
            },
            "unresolved_author_field_names": [0, 1, 2, 8],
        },
        "hard_blockers": hard_blockers,
        "warnings": [
            "column_0_is_not_a_unique_source_id_row_index_fallback_required",
            "column_1_is_not_a_0_3_modality_code",
            "column_9_is_variable_length_300_dimensional_word_vectors_not_one_768_dimensional_vector",
            "column_8_author_field_name_unknown_and_excluded_from_labels",
        ],
        "valid_record_count_if_no_group_conflict": len(records),
        "development_import_allowed": not hard_blockers,
    }
    return report, records


def _scan_binary_stream(
    raw: BinaryIO,
    *,
    schema: OfficialCsvSchema,
    contract: IngestContract,
    source_asset_sha256: str,
) -> tuple[dict, list[OfficialParsedRow]]:
    text_stream = io.TextIOWrapper(
        raw, encoding=schema.encoding, errors="strict", newline=""
    )
    try:
        return _scan_text_stream(
            text_stream,
            schema=schema,
            contract=contract,
            source_asset_sha256=source_asset_sha256,
        )
    except UnicodeDecodeError as exc:
        raise OfficialSchemaError(
            f"official CSV decode failed under locked encoding {schema.encoding!r}"
        ) from exc


def audit_official_csv(
    contract: IngestContract,
    *,
    csv_path_override: Optional[Path] = None,
    schema_override: Optional[OfficialCsvSchema] = None,
) -> dict:
    """Return a deterministic, aggregate-only complete schema audit."""
    schema = schema_override or load_official_schema(contract)
    if csv_path_override is None:
        source_identity = _source_identity_report(contract)
        with zipfile.ZipFile(contract.source_zip_path, "r") as archive:
            with archive.open(contract.csv_member_logical_name, "r") as raw:
                report, _ = _scan_binary_stream(
                    raw,
                    schema=schema,
                    contract=contract,
                    source_asset_sha256=contract.source_zip_sha256,
                )
        report["source_identity"] = source_identity
    else:
        override = Path(csv_path_override)
        override_sha256 = compute_file_sha256(override)
        with override.open("rb") as raw:
            report, _ = _scan_binary_stream(
                raw,
                schema=schema,
                contract=contract,
                source_asset_sha256=override_sha256,
            )
        report["source_identity"] = {
            "synthetic_override": True,
            "sha256": override_sha256,
            "size_bytes": override.stat().st_size,
        }
    return report


def write_schema_audit(
    report: Mapping[str, object],
    path: Path,
    *,
    allow_overwrite: bool = False,
) -> None:
    path = Path(path)
    if path.exists() and not allow_overwrite:
        raise OverwriteRefused(f"refuse overwrite of schema audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _records_from_source(
    contract: IngestContract,
    *,
    schema: OfficialCsvSchema,
    csv_path_override: Optional[Path],
) -> tuple[dict, list[OfficialParsedRow]]:
    if csv_path_override is None:
        source_identity = _source_identity_report(contract)
        with zipfile.ZipFile(contract.source_zip_path, "r") as archive:
            with archive.open(contract.csv_member_logical_name, "r") as raw:
                report, records = _scan_binary_stream(
                    raw,
                    schema=schema,
                    contract=contract,
                    source_asset_sha256=contract.source_zip_sha256,
                )
        report["source_identity"] = source_identity
        return report, records
    path = Path(csv_path_override)
    override_sha256 = compute_file_sha256(path)
    with path.open("rb") as raw:
        report, records = _scan_binary_stream(
            raw,
            schema=schema,
            contract=contract,
            source_asset_sha256=override_sha256,
        )
    report["source_identity"] = {
        "synthetic_override": True,
        "sha256": override_sha256,
        "size_bytes": path.stat().st_size,
    }
    return report, records


def _write_jsonl(path: Path, rows: Sequence[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            )


def _line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as stream:
        return sum(1 for _ in stream)


def ingest_official_csv(
    contract: IngestContract,
    *,
    out_dir: Path,
    allow_overwrite: bool = False,
    csv_path_override: Optional[Path] = None,
    schema_override: Optional[OfficialCsvSchema] = None,
) -> dict:
    """Attempt the guarded official development import.

    All source rows, vectors, label groups, quarantine evidence, and output
    paths are validated before a single records/split byte is written.  The
    default conflict policy remains fail-closed; only the exact contract-locked
    pre-result group may be quarantined as a whole.
    """
    schema = schema_override or load_official_schema(contract)
    out_dir = Path(out_dir)
    records_path = out_dir / "records.jsonl"
    splits_dir = out_dir / "splits"
    train_path = splits_dir / "train.jsonl"
    dev_path = splits_dir / "dev.jsonl"
    test_path = splits_dir / "test.jsonl"
    manifest_path = out_dir / "manifest.json"
    summary_path = out_dir / "split_summary.json"
    quarantine_manifest_path = out_dir / "quarantine_manifest.json"
    output_paths = (
        records_path,
        train_path,
        dev_path,
        test_path,
        manifest_path,
        summary_path,
        quarantine_manifest_path,
    )
    existing = [path for path in output_paths if path.exists()]
    if existing and not allow_overwrite:
        raise OverwriteRefused(
            "refuse overwrite of official derived outputs: "
            + ", ".join(str(path) for path in existing)
        )

    report, parsed_rows = _records_from_source(
        contract,
        schema=schema,
        csv_path_override=csv_path_override,
    )
    if report["hard_blockers"]:
        blocker_codes = {
            str(blocker["code"]) for blocker in report["hard_blockers"]
        }
        if "normalized_text_label_conflict" in blocker_codes:
            error = LabelConflictError(
                "label_conflict: official import blocked before output write; "
                f"details={report['text']['label_conflicts']}"
            )
        else:
            error = OfficialSchemaError(
                "official import blocked before output write: "
                f"{report['hard_blockers']}"
            )
        error.audit_report = report  # type: ignore[attr-defined]
        raise error

    quarantine_evaluation = report.get("quarantine_policy_evaluation", {})
    if not isinstance(quarantine_evaluation, dict):
        raise OfficialSchemaError("missing quarantine policy evaluation")
    observed_conflicts = report["text"]["label_conflicts"]
    if observed_conflicts and not quarantine_evaluation.get("authorized"):
        raise LabelConflictError(
            "label_conflict: conflict exists without an exact authorized quarantine"
        )
    quarantined_row_indices = {
        int(value)
        for value in quarantine_evaluation.get("quarantined_row_indices", [])
    }
    analysis_rows = [
        parsed
        for parsed in parsed_rows
        if parsed.row_index not in quarantined_row_indices
    ]
    if len(parsed_rows) != int(quarantine_evaluation["source_population_size"]):
        raise OfficialSchemaError("quarantine source population invariant failed")
    if len(analysis_rows) != int(quarantine_evaluation["analysis_population_size"]):
        raise OfficialSchemaError("quarantine analysis population invariant failed")
    observed_analysis_distribution = {
        label: int(count)
        for label, count in sorted(
            Counter(parsed.label for parsed in analysis_rows).items()
        )
    }
    expected_analysis_distribution = {
        str(label): int(count)
        for label, count in dict(
            quarantine_evaluation["analysis_label_distribution"]
        ).items()
    }
    if observed_analysis_distribution != expected_analysis_distribution:
        raise OfficialSchemaError(
            "computed post-quarantine label distribution does not match the "
            "exact contract evaluation"
        )

    source_asset_sha256 = (
        contract.source_zip_sha256
        if csv_path_override is None
        else compute_file_sha256(Path(csv_path_override))
    )
    local_rows: list[dict] = []
    identities: list[OfficialRecordIdentity] = []
    seen_sample_ids: set[str] = set()
    for parsed in analysis_rows:
        source_id = (
            parsed.section_reference
            if schema.source_id_column == schema.section_reference_column
            else None
        )
        sample_id = build_sample_id(
            source_asset_sha256,
            parsed.normalized_text,
            source_id=source_id,
            row_index=parsed.row_index if source_id is None else None,
            namespace=contract.id_namespace,
        )
        if sample_id in seen_sample_ids:
            raise OfficialSchemaError(f"duplicate derived sample_id: {sample_id}")
        seen_sample_ids.add(sample_id)
        identities.append(OfficialRecordIdentity(sample_id=sample_id, label=parsed.label))
        local_rows.append(
            {
                "sample_id": sample_id,
                "source_row_id": source_id,
                "source_section_reference": parsed.section_reference,
                "source_row_index": parsed.row_index,
                "text": parsed.text,
                "normalized_text": parsed.normalized_text,
                "integer_code": None,
                "label_encoding": "headerless_positional_strict_one_hot",
                "label_one_hot": list(parsed.label_one_hot),
                "label": parsed.label,
                "vector_present": True,
                "vector_dimension": schema.vector_element_dimension,
                "vector_flat_length": parsed.vector_flat_length,
                "vector_token_count": parsed.vector_token_count,
                "vector_source_reference": (
                    f"{contract.csv_member_logical_name}:column_{schema.vector_column}"
                ),
            }
        )

    train_idx, dev_idx, test_idx = deterministic_stratified_split(
        [row["label"] for row in local_rows],
        contract.split,
        contract.seed,
        group_keys=[row["normalized_text"] for row in local_rows],
    )
    splits = {"train": train_idx, "dev": dev_idx, "test": test_idx}
    leaks = check_cross_split_leakage(
        splits, [row["normalized_text"] for row in local_rows]
    )
    if leaks:
        raise OfficialSchemaError(
            f"group-aware split invariant failed with {len(leaks)} leak(s)"
        )
    all_indices = train_idx + dev_idx + test_idx
    if sorted(all_indices) != list(range(len(local_rows))):
        raise OfficialSchemaError("split union/disjointness invariant failed")

    def distribution(indices: Sequence[int]) -> dict[str, int]:
        counts = Counter(str(local_rows[index]["label"]) for index in indices)
        return {key: int(value) for key, value in sorted(counts.items())}

    all_distribution = distribution(list(range(len(local_rows))))
    source_distribution = {
        str(label): int(count)
        for label, count in dict(
            report["labels"]["actual_class_distribution"]
        ).items()
    }
    raw_policy = contract.raw.get("conflict_quarantine", {})
    if not isinstance(raw_policy, dict):
        raw_policy = {}
    locked_by_normalized_hash = {
        str(group.get("normalized_text_sha256")): group
        for group in raw_policy.get("locked_groups", [])
        if isinstance(group, dict)
    }
    quarantined_groups: list[dict] = []
    for descriptor in observed_conflicts:
        normalized_hash = str(descriptor["normalized_text_sha256"])
        locked = locked_by_normalized_hash.get(normalized_hash, {})
        quarantined_groups.append(
            {
                "normalized_text_sha256": normalized_hash,
                "raw_text_sha256": descriptor["raw_text_sha256"],
                "raw_text_hashes_equal": bool(
                    descriptor["raw_text_hashes_equal"]
                ),
                "row_indices": list(descriptor["row_indices"]),
                "original_labels": list(descriptor["labels"]),
                "original_labels_by_row": dict(descriptor["labels_by_row"]),
                "section_reference_sha256_by_row": dict(
                    descriptor["section_reference_sha256_by_row"]
                ),
                "section_reference_hashes_distinct": bool(
                    descriptor["section_reference_hashes_distinct"]
                ),
                "conflict_type": str(
                    locked.get(
                        "conflict_type",
                        "identical_raw_text_conflicting_original_labels",
                    )
                ),
                "exclusion_reason": str(
                    locked.get(
                        "exclusion_reason",
                        "exact contract-locked pre-result conflicting-label group quarantine",
                    )
                ),
            }
        )
    sensitivity_variant = raw_policy.get("sensitivity_full_source_variant", {})
    quarantine_manifest = {
        "schema_version": "1.0.0",
        "policy_version": quarantine_evaluation.get("policy_version"),
        "dataset_id": contract.dataset_id,
        "contract_version": contract.contract_version,
        "contract_sha256": contract.contract_sha256,
        "source_asset": {
            "source_asset_sha256": source_asset_sha256,
            "csv_member_sha256": (
                contract.csv_member_sha256
                if csv_path_override is None
                else source_asset_sha256
            ),
        },
        "policy": {
            "conflict_policy": quarantine_evaluation["policy"],
            "match_status": quarantine_evaluation["status"],
            "exact_locked_group_match": bool(
                quarantine_evaluation["authorized"]
            ),
            "raw_source_labels_modified": False,
            "quarantine_decision_timing": raw_policy.get(
                "quarantine_decision_timing",
                "before_any_model_training_or_result",
            ),
            "main_experiment_uses_clean_population": bool(
                raw_policy.get("main_experiment_uses_clean_population", True)
            ),
            "all_main_methods_must_share_analysis_population": bool(
                raw_policy.get(
                    "all_main_methods_must_share_analysis_population", True
                )
            ),
        },
        "population": {
            "source_population_size": len(parsed_rows),
            "analysis_population_size": len(local_rows),
            "quarantined_group_count": len(quarantined_groups),
            "quarantined_record_count": len(quarantined_row_indices),
        },
        "source_label_distribution": source_distribution,
        "analysis_label_distribution": all_distribution,
        "quarantined_groups": quarantined_groups,
        "sensitivity_full_source_variant": dict(sensitivity_variant),
        "contains_raw_text": False,
        "contains_vectors": False,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    splits_dir.mkdir(parents=True, exist_ok=True)
    if allow_overwrite:
        for path in output_paths:
            if path.exists():
                path.unlink()
    _write_jsonl(records_path, local_rows)
    _write_jsonl(train_path, [local_rows[index] for index in train_idx])
    _write_jsonl(dev_path, [local_rows[index] for index in dev_idx])
    _write_jsonl(test_path, [local_rows[index] for index in test_idx])
    quarantine_manifest_path.write_text(
        json.dumps(
            quarantine_manifest, ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    paths_roles_and_counts = (
        (records_path, "records", len(local_rows)),
        (train_path, "train_split", len(train_idx)),
        (dev_path, "dev_split", len(dev_idx)),
        (test_path, "test_split", len(test_idx)),
        (
            quarantine_manifest_path,
            "quarantine_manifest",
            len(quarantined_row_indices),
        ),
    )
    output_files = [
        {
            "role": role,
            "path": path.relative_to(out_dir).as_posix(),
            "sha256": compute_file_sha256(path),
            "size_bytes": path.stat().st_size,
            "row_count": row_count,
        }
        for path, role, row_count in paths_roles_and_counts
    ]

    manifest = {
        "schema_version": "1.3.1",
        "manifest_id": f"{contract.dataset_id}@{contract.contract_version}",
        "dataset_id": contract.dataset_id,
        "contract_version": contract.contract_version,
        "contract_path": contract.project_relative_path(
            contract.contract_path, field_name="contract_path"
        ),
        "contract_sha256": contract.contract_sha256,
        "importer_version": IMPORTER_VERSION,
        "importer_module": "bpc_hybrid.datasets.sun_modality_official",
        "label_adapter": "official_positional_strict_one_hot",
        "split_origin": "project_reconstructed_deterministic_split",
        "source_schema": {
            "mode": "headerless_positional",
            "encoding": schema.encoding,
            "delimiter": schema.delimiter,
            "has_header": schema.has_header,
            "text_column": schema.text_column,
            "source_id_column": schema.source_id_column,
            "label_mode": "headerless_positional_strict_one_hot",
            "label_columns": list(schema.label_columns),
            "vector_column": schema.vector_column,
        },
        "vector_policy": {
            "present": True,
            "structure": schema.vector_structure,
            "element_dimension": schema.vector_element_dimension,
            "validation_status": "all_present_finite_and_token_aligned",
            "use_for_training": "pending_stage2_4",
        },
        "source_asset": {
            "logical_name": "Decision_Logic_data.zip",
            "local_path": contract.project_relative_path(
                contract.source_zip_path, field_name="source_asset.local_path"
            ),
            "official_sha1": contract.source_zip_official_sha1,
            "local_sha256": contract.source_zip_sha256,
            "size_bytes": contract.source_zip_size_bytes,
            "csv_member_logical_name": contract.csv_member_logical_name,
            "csv_member_sha256": contract.csv_member_sha256,
            "csv_member_size_uncompressed_bytes": contract.csv_member_size_uncompressed_bytes,
            "csv_member_crc32": contract.csv_member_crc32,
        },
        "seed": contract.seed,
        "sample_id_policy": {
            "algorithm": "blake2b-64 over canonical JSON of [source_asset_sha256, source_key_type, source_key, normalized_text]",
            "source_asset_sha256": source_asset_sha256,
            "source_id_column": schema.source_id_column,
            "source_id_mode": (
                "explicit_source_id"
                if schema.source_id_column is not None
                else "row_index_fallback"
            ),
            "row_index_fallback_used": schema.source_id_column is None,
        },
        "split_params": {
            "train_ratio": contract.split.train_ratio,
            "dev_ratio": contract.split.dev_ratio,
            "test_ratio": contract.split.test_ratio,
            "stratified": contract.split.stratified,
            "shuffle": contract.split.shuffle,
            "min_per_class_in_smallest_split": contract.split.min_per_class_in_smallest_split,
        },
        "population": {
            "source_population_size": len(parsed_rows),
            "analysis_population_size": len(local_rows),
            "quarantined_group_count": len(quarantined_groups),
            "quarantined_record_count": len(quarantined_row_indices),
        },
        "conflict_policy": {
            "policy_version": quarantine_evaluation.get("policy_version"),
            "name": quarantine_evaluation["policy"],
            "exact_locked_group_match": bool(
                quarantine_evaluation["authorized"]
            ),
            "raw_source_labels_modified": False,
            "decision_timing": raw_policy.get(
                "quarantine_decision_timing",
                "before_any_model_training_or_result",
            ),
            "sensitivity_variant_status": dict(sensitivity_variant).get(
                "status", "not_applicable"
            ),
        },
        "total_samples_in": len(parsed_rows),
        "total_samples_valid": len(local_rows),
        "total_samples_rejected": 0,
        "total_samples_quarantined": len(quarantined_row_indices),
        "label_distribution_in": source_distribution,
        "label_distribution_valid": all_distribution,
        "train_size": len(train_idx),
        "dev_size": len(dev_idx),
        "test_size": len(test_idx),
        "train_label_distribution": distribution(train_idx),
        "dev_label_distribution": distribution(dev_idx),
        "test_label_distribution": distribution(test_idx),
        "membership_hash": {
            "algorithm": "blake2b-256 over sorted JSON of [(sample_id, label)]",
            "value": compute_membership_hash(identities),
        },
        "output_files": output_files,
        "stats": {
            "rejected_empty_text": 0,
            "rejected_duplicate_id": 0,
            "rejected_missing_source_id": 0,
            "rejected_unknown_label": 0,
            "rejected_missing_label": 0,
            "rejected_one_hot_all_zero": 0,
            "rejected_one_hot_multi_hot": 0,
            "rejected_one_hot_non_binary": 0,
            "rejected_cross_split_text_leakage": 0,
            "label_conflict": len(quarantined_groups),
            "quarantined_conflict_groups": len(quarantined_groups),
            "quarantined_conflict_records": len(quarantined_row_indices),
            "rejected_other": 0,
        },
        "lifecycle": {
            "stage": "development",
            "ready_for_training": False,
            "ready_for_evaluation": False,
            "ready_for_publication": False,
            "notes": "Project-reconstructed deterministic split over the 2,831-row pre-result clean analysis population; not a Sun original split. The exact two-row source-label conflict group is quarantined without changing either raw label. Rights remain unknown_pending_confirmation. No training or evaluation was run by S2.1-C-R1.",
        },
        "license": {
            "rights_status": contract.rights_status,
            "redistribution_allowed": contract.redistribution_allowed,
            "publication_in_paper_allowed": contract.publication_in_paper_allowed,
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_entry = {
        "role": "manifest",
        "path": manifest_path.relative_to(out_dir).as_posix(),
        "sha256": compute_file_sha256(manifest_path),
        "size_bytes": manifest_path.stat().st_size,
    }
    summary = {
        "split_origin": "project_reconstructed_deterministic_split",
        "seed": contract.seed,
        "ratios": {
            "train": contract.split.train_ratio,
            "dev": contract.split.dev_ratio,
            "test": contract.split.test_ratio,
        },
        "population": manifest["population"],
        "conflict_policy": manifest["conflict_policy"],
        "source_label_distribution": source_distribution,
        "analysis_label_distribution": all_distribution,
        "membership_hash": manifest["membership_hash"],
        "manifest_sha256": manifest_entry["sha256"],
        "output_files": [*output_files, manifest_entry],
        "split_sizes": {
            "train": len(train_idx),
            "dev": len(dev_idx),
            "test": len(test_idx),
        },
        "split_label_distribution": {
            "train": distribution(train_idx),
            "dev": distribution(dev_idx),
            "test": distribution(test_idx),
        },
        "cross_split_normalized_text_leakage_count": 0,
        "split_sets_pairwise_disjoint": True,
        "split_union_complete": True,
        "quarantined_rows_absent_from_records_and_splits": True,
        "sensitivity_full_source_variant_status": dict(
            sensitivity_variant
        ).get("status", "not_applicable"),
        "contains_raw_text": False,
        "contains_vectors": False,
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest
