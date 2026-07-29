"""S2.1-C official headerless schema audit and fail-closed import tests.

All parser/import unit tests use tiny synthetic files.  The real 2,833-row
complete scan is an explicit S2.1-C validation command, not a pytest fixture.
"""

from __future__ import annotations

import csv
import copy
import dataclasses
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = PROJECT_ROOT / "configs" / "datasets" / "sun_modality_dataset.json"
MANIFEST_SCHEMA_PATH = PROJECT_ROOT / "configs" / "schemas" / "dataset_manifest.schema.json"
OUTPUT_DIR = (
    PROJECT_ROOT / "data" / "development" / "modality" / "sun_estg_modality_v1"
)
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "sun_modality"
SOURCE_MANIFEST = (
    PROJECT_ROOT / "data" / "development" / "sun_modality" / "source_manifest.json"
)
OFFICIAL_ZIP = (
    PROJECT_ROOT
    / "data"
    / "development"
    / "sun_modality"
    / "raw"
    / "Decision_Logic_data.zip"
)
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.datasets.sun_modality_importer import (  # noqa: E402
    LabelConflictError,
    OverwriteRefused,
    compute_file_sha256,
    load_contract,
)
from bpc_hybrid.datasets.sun_modality_official import (  # noqa: E402
    OfficialMappingError,
    OfficialSchemaError,
    OfficialVectorError,
    audit_official_csv,
    ingest_official_csv,
    load_official_schema,
    official_integer_code_label_adapter,
    parse_flat_vector,
    write_schema_audit,
)


LABELS = ("definition", "obligation", "permission", "prohibition")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _contract():
    return load_contract(CONTRACT_PATH, project_root=PROJECT_ROOT)


def _schema_for_counts(counts: dict[str, int], *, row_count: int):
    base = load_official_schema(_contract())
    return dataclasses.replace(
        base,
        vector_element_dimension=3,
        expected_row_count=row_count,
        expected_label_distribution=counts,
    )


def _vector(token_count: int = 2, element_dimension: int = 3) -> str:
    values = [f"{index / 100:.2f}" for index in range(token_count * element_dimension)]
    return "[" + ", ".join(values) + "]"


def _base_rows(per_class: int = 4) -> list[list[str]]:
    rows: list[list[str]] = []
    row_index = 0
    for label_index, _ in enumerate(LABELS):
        for class_index in range(per_class):
            bits = ["1" if position == label_index else "0" for position in range(4)]
            rows.append(
                [
                    f"sec-{row_index:03d}",
                    str(class_index),
                    str(row_index),
                    f"token{row_index} alpha",
                    *bits,
                    "0",
                    _vector(),
                ]
            )
            row_index += 1
    return rows


def _conflict_rows() -> list[list[str]]:
    rows = _base_rows()
    rows[1][3] = rows[0][3]
    rows[1][4:8] = ["0", "1", "0", "0"]
    return rows


def _write_rows(path: Path, rows: list[list[str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerows(rows)
    return path


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _label_for_row(row: list[str]) -> str:
    bits = [int(value) for value in row[4:8]]
    return LABELS[bits.index(1)]


def _contract_with_fixture_quarantine(
    csv_path: Path,
    rows: list[list[str]],
    *,
    conflict_indices: tuple[int, int] = (0, 1),
):
    contract = _contract()
    raw = copy.deepcopy(contract.raw)
    first, second = conflict_indices
    normalized = contract.normalize_for_dedup(rows[first][3])
    raw_hash = hashlib.sha256(rows[first][3].encode("utf-8")).hexdigest()
    source_distribution = {
        label: sum(_label_for_row(row) == label for row in rows) for label in LABELS
    }
    analysis_distribution = dict(source_distribution)
    for index in conflict_indices:
        analysis_distribution[_label_for_row(rows[index])] -= 1
    raw["conflict_quarantine"] = {
        "policy_version": "synthetic_conflict_quarantine@1.0.0",
        "status": "authorized_locked",
        "conflict_policy": "pre_result_conflicting_label_group_quarantine",
        "source_asset_sha256": compute_file_sha256(csv_path),
        "source_population_size": len(rows),
        "analysis_population_size": len(rows) - len(conflict_indices),
        "quarantined_group_count": 1,
        "quarantined_record_count": len(conflict_indices),
        "raw_source_labels_modified": False,
        "quarantine_decision_timing": "before_any_model_training_or_result",
        "main_experiment_uses_clean_population": True,
        "all_main_methods_must_share_analysis_population": True,
        "analysis_label_distribution": analysis_distribution,
        "locked_groups": [
            {
                "normalized_text_sha256": hashlib.sha256(
                    normalized.encode("utf-8")
                ).hexdigest(),
                "raw_text_sha256": raw_hash,
                "raw_text_hashes_equal": True,
                "row_indices": list(conflict_indices),
                "labels": sorted({_label_for_row(rows[index]) for index in conflict_indices}),
                "labels_by_row": {
                    str(index): _label_for_row(rows[index]) for index in conflict_indices
                },
                "section_reference_sha256_by_row": {
                    str(index): hashlib.sha256(
                        rows[index][0].encode("utf-8")
                    ).hexdigest()
                    for index in conflict_indices
                },
                "conflict_type": "identical_raw_text_conflicting_original_labels",
                "exclusion_reason": "synthetic exact locked group",
            }
        ],
        "sensitivity_full_source_variant": {
            "population": len(rows),
            "conflicting_group_preserved_with_original_labels": True,
            "conflicting_group_split_constraint": "forced_train_only",
            "conflicting_group_prohibited_from_dev_test": True,
            "purpose": "measure impact of source-label inconsistency",
            "status": "planned_not_run",
            "must_use_same_nonconflict_membership_as_main_where_possible": True,
            "sensitivity_variant_registered": True,
            "sensitivity_variant_executed": False,
        },
    }
    return dataclasses.replace(contract, raw=raw)


class TestVerifiedContractFacts:
    def test_official_schema_is_locked_to_observed_headerless_positions(self):
        contract = _contract()
        schema = load_official_schema(contract)
        assert contract.contract_version == "sun_modality_dataset_contract@1.3.1"
        assert schema.has_header is False
        assert schema.encoding == "utf-8"
        assert schema.delimiter == ","
        assert schema.expected_field_count == 10
        assert schema.expected_row_count == 2833
        assert schema.source_id_column is None
        assert schema.text_column == 3
        assert schema.label_columns == (4, 5, 6, 7)
        assert schema.label_classes == LABELS
        assert schema.vector_column == 9
        assert schema.vector_element_dimension == 300

    def test_integer_hypothesis_is_not_silently_converted_to_mapping(self):
        raw = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        mapping = raw["official_integer_code_mapping"]
        assert mapping["mapping"] is None
        assert mapping["status"] == "not_applicable_verified_no_integer_modality_column"
        assert raw["official_label_mode"] == "headerless_positional_strict_one_hot"
        assert raw["official_positional_one_hot_mapping"]["column_to_label"] == {
            "4": "definition",
            "5": "obligation",
            "6": "permission",
            "7": "prohibition",
        }

    def test_real_conflict_quarantine_policy_is_exact_and_pre_result(self):
        raw = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        policy = raw["conflict_quarantine"]
        assert policy["status"] == "authorized_locked"
        assert policy["conflict_policy"] == (
            "pre_result_conflicting_label_group_quarantine"
        )
        assert policy["source_population_size"] == 2833
        assert policy["analysis_population_size"] == 2831
        assert policy["quarantined_group_count"] == 1
        assert policy["quarantined_record_count"] == 2
        assert policy["raw_source_labels_modified"] is False
        assert policy["quarantine_decision_timing"] == (
            "before_any_model_training_or_result"
        )
        assert policy["analysis_label_distribution"] == {
            "definition": 1190,
            "obligation": 1273,
            "permission": 264,
            "prohibition": 104,
        }
        group = policy["locked_groups"][0]
        assert group["row_indices"] == [616, 1221]
        assert group["labels_by_row"] == {
            "616": "permission",
            "1221": "obligation",
        }
        assert HEX64.fullmatch(group["normalized_text_sha256"])
        assert HEX64.fullmatch(group["raw_text_sha256"])
        sensitivity = policy["sensitivity_full_source_variant"]
        assert sensitivity["status"] == "planned_not_run"
        assert sensitivity["sensitivity_variant_executed"] is False
        dod = raw["s2_1_c_r1_definition_of_done_check_2026_07_16"]
        assert dod["status"] == "verified"
        assert dod["s2_1_c_verified"] is True
        assert dod["s2_1_d_ready"] is True

    def test_manifest_schema_patch_requires_portable_paths_and_quarantine_fields(self):
        schema = json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        assert schema["$id"] == "dataset_manifest.schema.json@1.3.1"
        assert schema["properties"]["schema_version"]["const"] == "1.3.1"
        assert "pattern" in schema["properties"]["contract_path"]
        assert "pattern" in schema["properties"]["source_asset"]["properties"]["local_path"]
        assert {"split_origin", "source_schema", "vector_policy"}.issubset(
            schema["required"]
        )
        assert {"population", "conflict_policy", "total_samples_quarantined"}.issubset(
            schema["properties"]
        )


class TestExplicitIntegerAdapterSeam:
    def test_headerless_integer_fixture_is_explicitly_test_only(self):
        fixture = FIXTURE_DIR / "synthetic_headerless_integer.csv"
        rows = list(csv.reader(fixture.open("r", encoding="utf-8", newline="")))
        mapping = {
            "0": "definition",
            "1": "obligation",
            "2": "permission",
            "3": "prohibition",
        }
        assert [
            official_integer_code_label_adapter(row[1], mapping, LABELS)
            for row in rows
        ] == list(LABELS)

    def test_mapping_missing_fails_closed(self):
        with pytest.raises(OfficialMappingError, match="mapping_missing"):
            official_integer_code_label_adapter("0", None, LABELS)

    @pytest.mark.parametrize("value", ["4", "99", "unknown"])
    def test_unknown_or_noninteger_code_fails_closed(self, value):
        mapping = {"0": "definition"}
        with pytest.raises(OfficialMappingError):
            official_integer_code_label_adapter(value, mapping, LABELS)


class TestVectorValidation:
    def test_exact_768_vector_is_accepted_for_dimension_contract_test(self):
        vector = "[" + ",".join("0.0" for _ in range(768)) + "]"
        assert parse_flat_vector(vector, expected_flat_dimension=768) == (768, 768)

    @pytest.mark.parametrize("dimension", [767, 769])
    def test_767_or_769_vector_is_rejected_against_768_contract(self, dimension):
        vector = "[" + ",".join("0.0" for _ in range(dimension)) + "]"
        with pytest.raises(OfficialVectorError, match="unexpected_flat_vector_dimension"):
            parse_flat_vector(vector, expected_flat_dimension=768)

    @pytest.mark.parametrize("bad_value", ["NaN", "Inf", "-Inf", "not-a-number"])
    def test_nonfinite_and_nonnumeric_values_are_rejected(self, bad_value):
        with pytest.raises(OfficialVectorError):
            parse_flat_vector(f"[0.0,{bad_value},1.0]", element_dimension=3)

    def test_actual_word_vector_structure_requires_300_multiple_and_token_match(self):
        vector = "[" + ",".join("0.0" for _ in range(600)) + "]"
        assert parse_flat_vector(
            vector, element_dimension=300, expected_token_count=2
        ) == (600, 2)
        wrong = "[" + ",".join("0.0" for _ in range(601)) + "]"
        with pytest.raises(OfficialVectorError, match="not a multiple"):
            parse_flat_vector(wrong, element_dimension=300)


class TestHeaderlessAuditAndFailClosedImport:
    def test_headerless_positional_audit_has_no_raw_sentence_or_vector(self, tmp_path):
        rows = _base_rows()
        secret = "privatefixture alpha"
        rows[0][3] = secret
        csv_path = _write_rows(tmp_path / "official_like.csv", rows)
        counts = {label: 4 for label in LABELS}
        report = audit_official_csv(
            _contract(),
            csv_path_override=csv_path,
            schema_override=_schema_for_counts(counts, row_count=len(rows)),
        )
        assert report["status"] == "verified"
        assert report["csv_schema"]["has_header"] is False
        assert report["labels"]["actual_class_distribution"] == counts
        serialized = json.dumps(report, ensure_ascii=False)
        assert secret not in serialized
        assert rows[0][9] not in serialized
        assert report["contains_raw_text"] is False
        assert report["contains_vectors"] is False

    def test_short_row_is_reported_as_hard_blocker(self, tmp_path):
        rows = _base_rows()
        rows[-1] = rows[-1][:-1]
        csv_path = _write_rows(tmp_path / "short.csv", rows)
        counts = {label: 4 for label in LABELS}
        report = audit_official_csv(
            _contract(),
            csv_path_override=csv_path,
            schema_override=_schema_for_counts(counts, row_count=len(rows)),
        )
        assert report["csv_schema"]["short_rows"] == 1
        assert "invalid_official_rows" in {
            blocker["code"] for blocker in report["hard_blockers"]
        }

    def test_decode_error_fails_closed(self, tmp_path):
        path = tmp_path / "bad_encoding.csv"
        path.write_bytes(b"sec,0,0,text,1,0,0,0,0,\xff\n")
        schema = _schema_for_counts(
            {"definition": 1, "obligation": 0, "permission": 0, "prohibition": 0},
            row_count=1,
        )
        with pytest.raises(OfficialSchemaError, match="decode failed"):
            audit_official_csv(
                _contract(), csv_path_override=path, schema_override=schema
            )

    def test_duplicate_explicit_source_id_fails_before_output(self, tmp_path):
        rows = _base_rows()
        rows[1][0] = rows[0][0]
        csv_path = _write_rows(tmp_path / "duplicate_id.csv", rows)
        schema = dataclasses.replace(
            _schema_for_counts({label: 4 for label in LABELS}, row_count=len(rows)),
            source_id_column=0,
        )
        out = tmp_path / "out_duplicate"
        with pytest.raises(OfficialSchemaError, match="blocked before output write"):
            ingest_official_csv(
                _contract(),
                out_dir=out,
                csv_path_override=csv_path,
                schema_override=schema,
            )
        assert not (out / "records.jsonl").exists()
        assert not (out / "manifest.json").exists()

    def test_label_conflict_fails_before_output_and_records_hash_only(self, tmp_path):
        rows = _base_rows()
        rows[1][3] = rows[0][3]
        rows[1][4:8] = ["0", "1", "0", "0"]
        csv_path = _write_rows(tmp_path / "conflict.csv", rows)
        counts = {
            "definition": 3,
            "obligation": 5,
            "permission": 4,
            "prohibition": 4,
        }
        schema = _schema_for_counts(counts, row_count=len(rows))
        report = audit_official_csv(
            _contract(), csv_path_override=csv_path, schema_override=schema
        )
        assert report["text"]["label_conflict_group_count"] == 1
        descriptor = report["text"]["label_conflicts"][0]
        assert HEX64.fullmatch(descriptor["normalized_text_sha256"])
        assert "token0alpha" not in json.dumps(report)
        out = tmp_path / "out_conflict"
        with pytest.raises(LabelConflictError, match="label_conflict"):
            ingest_official_csv(
                _contract(),
                out_dir=out,
                csv_path_override=csv_path,
                schema_override=schema,
            )
        assert not (out / "records.jsonl").exists()
        assert not (out / "manifest.json").exists()


class TestExactConflictQuarantinePolicy:
    SOURCE_COUNTS = {
        "definition": 3,
        "obligation": 5,
        "permission": 4,
        "prohibition": 4,
    }
    ANALYSIS_COUNTS = {
        "definition": 2,
        "obligation": 4,
        "permission": 4,
        "prohibition": 4,
    }

    def _fixture(self, tmp_path: Path, name: str):
        rows = _conflict_rows()
        rows[3][3] = rows[2][3]
        csv_path = _write_rows(tmp_path / f"{name}.csv", rows)
        contract = _contract_with_fixture_quarantine(csv_path, rows)
        schema = _schema_for_counts(self.SOURCE_COUNTS, row_count=len(rows))
        return rows, csv_path, contract, schema

    def test_default_policy_still_fails_closed(self, tmp_path):
        rows, csv_path, contract, schema = self._fixture(tmp_path, "default")
        raw = copy.deepcopy(contract.raw)
        raw.pop("conflict_quarantine")
        contract = dataclasses.replace(contract, raw=raw)
        out = tmp_path / "default_out"
        with pytest.raises(LabelConflictError, match="label_conflict"):
            ingest_official_csv(
                contract,
                out_dir=out,
                csv_path_override=csv_path,
                schema_override=schema,
            )
        assert not out.exists()
        assert rows[0][3] == rows[1][3]

    def test_unlocked_arbitrary_conflict_cannot_be_skipped(self, tmp_path):
        rows = _conflict_rows()
        csv_path = _write_rows(tmp_path / "unlocked.csv", rows)
        out = tmp_path / "unlocked_out"
        with pytest.raises(LabelConflictError, match="label_conflict"):
            ingest_official_csv(
                _contract(),
                out_dir=out,
                csv_path_override=csv_path,
                schema_override=_schema_for_counts(
                    self.SOURCE_COUNTS, row_count=len(rows)
                ),
            )
        assert not (out / "records.jsonl").exists()

    @pytest.mark.parametrize("mismatch", ["hash", "row_indices", "labels"])
    def test_any_locked_group_descriptor_mismatch_fails_closed(
        self, tmp_path, mismatch
    ):
        _, csv_path, contract, schema = self._fixture(tmp_path, mismatch)
        raw = copy.deepcopy(contract.raw)
        locked = raw["conflict_quarantine"]["locked_groups"][0]
        if mismatch == "hash":
            locked["raw_text_sha256"] = "0" * 64
        elif mismatch == "row_indices":
            locked["row_indices"] = [0, 2]
        else:
            locked["labels"] = ["definition", "permission"]
        contract = dataclasses.replace(contract, raw=raw)
        out = tmp_path / f"{mismatch}_out"
        with pytest.raises(LabelConflictError, match="label_conflict"):
            ingest_official_csv(
                contract,
                out_dir=out,
                csv_path_override=csv_path,
                schema_override=schema,
            )
        assert not out.exists()

    def test_exact_group_is_quarantined_and_all_remaining_rows_are_split(self, tmp_path):
        rows, csv_path, contract, schema = self._fixture(tmp_path, "exact")
        out = tmp_path / "exact_out"
        manifest = ingest_official_csv(
            contract,
            out_dir=out,
            csv_path_override=csv_path,
            schema_override=schema,
        )
        records = _read_jsonl(out / "records.jsonl")
        split_rows = {
            name: _read_jsonl(out / "splits" / f"{name}.jsonl")
            for name in ("train", "dev", "test")
        }
        assert len(records) == 14
        assert {row["source_row_index"] for row in records}.isdisjoint({0, 1})
        for split in split_rows.values():
            assert {row["source_row_index"] for row in split}.isdisjoint({0, 1})
        split_ids = {
            name: {row["sample_id"] for row in split}
            for name, split in split_rows.items()
        }
        assert split_ids["train"].isdisjoint(split_ids["dev"])
        assert split_ids["train"].isdisjoint(split_ids["test"])
        assert split_ids["dev"].isdisjoint(split_ids["test"])
        assert set().union(*split_ids.values()) == {
            row["sample_id"] for row in records
        }
        locations: dict[str, set[str]] = {}
        for split_name, split in split_rows.items():
            for row in split:
                locations.setdefault(row["normalized_text"], set()).add(split_name)
        assert all(len(split_names) == 1 for split_names in locations.values())
        assert manifest["label_distribution_in"] == self.SOURCE_COUNTS
        assert manifest["label_distribution_valid"] == self.ANALYSIS_COUNTS
        assert manifest["population"] == {
            "source_population_size": 16,
            "analysis_population_size": 14,
            "quarantined_group_count": 1,
            "quarantined_record_count": 2,
        }
        assert manifest["conflict_policy"]["exact_locked_group_match"] is True

    def test_quarantine_aggregate_files_contain_no_raw_text_or_vectors(self, tmp_path):
        rows, csv_path, contract, schema = self._fixture(tmp_path, "private")
        out = tmp_path / "private_out"
        ingest_official_csv(
            contract,
            out_dir=out,
            csv_path_override=csv_path,
            schema_override=schema,
        )
        for filename in (
            "manifest.json",
            "split_summary.json",
            "quarantine_manifest.json",
        ):
            serialized = (out / filename).read_text(encoding="utf-8")
            assert rows[0][3] not in serialized
            assert rows[0][9] not in serialized
            assert "contains_raw_text\": true" not in serialized.lower()
        quarantine = json.loads(
            (out / "quarantine_manifest.json").read_text(encoding="utf-8")
        )
        assert quarantine["contains_raw_text"] is False
        assert quarantine["contains_vectors"] is False
        assert quarantine["quarantined_groups"][0]["row_indices"] == [0, 1]

    def test_exact_quarantine_outputs_are_byte_identical(self, tmp_path):
        _, csv_path, contract, schema = self._fixture(tmp_path, "replay")
        outputs = []
        for name in ("replay_a", "replay_b"):
            out = tmp_path / name
            ingest_official_csv(
                contract,
                out_dir=out,
                csv_path_override=csv_path,
                schema_override=schema,
            )
            outputs.append(out)
        for filename in (
            "records.jsonl",
            "splits/train.jsonl",
            "splits/dev.jsonl",
            "splits/test.jsonl",
            "manifest.json",
            "split_summary.json",
            "quarantine_manifest.json",
        ):
            assert compute_file_sha256(outputs[0] / filename) == compute_file_sha256(
                outputs[1] / filename
            )


class TestDeterministicDevelopmentOutputs:
    def _ingest(self, tmp_path: Path, name: str, *, seed: int = 20260715):
        rows = _base_rows()
        rows[1][3] = rows[0][3]
        csv_path = _write_rows(tmp_path / f"{name}.csv", rows)
        contract = dataclasses.replace(_contract(), seed=seed)
        schema = _schema_for_counts({label: 4 for label in LABELS}, row_count=len(rows))
        out = tmp_path / name
        manifest = ingest_official_csv(
            contract,
            out_dir=out,
            csv_path_override=csv_path,
            schema_override=schema,
        )
        return out, manifest

    def test_group_aware_split_is_disjoint_complete_and_leak_free(self, tmp_path):
        out, manifest = self._ingest(tmp_path, "grouped")
        split_rows = {
            name: _read_jsonl(out / "splits" / f"{name}.jsonl")
            for name in ("train", "dev", "test")
        }
        split_ids = {
            name: {row["sample_id"] for row in rows}
            for name, rows in split_rows.items()
        }
        assert split_ids["train"].isdisjoint(split_ids["dev"])
        assert split_ids["train"].isdisjoint(split_ids["test"])
        assert split_ids["dev"].isdisjoint(split_ids["test"])
        all_rows = _read_jsonl(out / "records.jsonl")
        assert set().union(*split_ids.values()) == {row["sample_id"] for row in all_rows}
        locations: dict[str, set[str]] = {}
        for split_name, rows in split_rows.items():
            for row in rows:
                locations.setdefault(row["normalized_text"], set()).add(split_name)
        assert all(len(values) == 1 for values in locations.values())
        assert manifest["split_origin"] == "project_reconstructed_deterministic_split"
        assert manifest["sample_id_policy"]["row_index_fallback_used"] is True

    def test_different_seeds_remain_leak_free(self, tmp_path):
        for seed in (1, 99999):
            out, _ = self._ingest(tmp_path, f"seed_{seed}", seed=seed)
            locations: dict[str, set[str]] = {}
            for split_name in ("train", "dev", "test"):
                for row in _read_jsonl(out / "splits" / f"{split_name}.jsonl"):
                    locations.setdefault(row["normalized_text"], set()).add(split_name)
            assert all(len(values) == 1 for values in locations.values())

    def test_same_input_contract_seed_makes_all_outputs_byte_identical(self, tmp_path):
        rows = _base_rows()
        csv_path = _write_rows(tmp_path / "same.csv", rows)
        schema = _schema_for_counts({label: 4 for label in LABELS}, row_count=len(rows))
        outputs = []
        for name in ("run_a", "run_b"):
            out = tmp_path / name
            ingest_official_csv(
                _contract(),
                out_dir=out,
                csv_path_override=csv_path,
                schema_override=schema,
            )
            outputs.append(out)
        for filename in (
            "records.jsonl",
            "splits/train.jsonl",
            "splits/dev.jsonl",
            "splits/test.jsonl",
            "manifest.json",
            "split_summary.json",
            "quarantine_manifest.json",
        ):
            assert compute_file_sha256(outputs[0] / filename) == compute_file_sha256(
                outputs[1] / filename
            )

    def test_manifest_is_portable_across_different_workspace_roots(self, tmp_path):
        rows = _base_rows()
        csv_path = _write_rows(tmp_path / "portable.csv", rows)
        schema = _schema_for_counts({label: 4 for label in LABELS}, row_count=len(rows))
        contract_bytes = CONTRACT_PATH.read_bytes()
        manifests: list[bytes] = []
        for root_name in ("workspace_alpha", "workspace_beta"):
            root = tmp_path / root_name
            contract_path = root / "configs" / "datasets" / "sun_modality_dataset.json"
            source_path = (
                root
                / "data"
                / "development"
                / "sun_modality"
                / "raw"
                / "Decision_Logic_data.zip"
            )
            contract_path.parent.mkdir(parents=True)
            source_path.parent.mkdir(parents=True)
            contract_path.write_bytes(contract_bytes)
            source_path.write_bytes(b"SYNTHETIC_PATH_SENTINEL")
            contract = load_contract(contract_path, project_root=root)
            out = root / "data" / "development" / "modality" / "sun_estg_modality_v1"
            manifest = ingest_official_csv(
                contract,
                out_dir=out,
                csv_path_override=csv_path,
                schema_override=schema,
            )
            assert manifest["contract_path"] == (
                "configs/datasets/sun_modality_dataset.json"
            )
            assert manifest["source_asset"]["local_path"] == (
                "data/development/sun_modality/raw/Decision_Logic_data.zip"
            )
            manifests.append((out / "manifest.json").read_bytes())
        assert manifests[0] == manifests[1]

    def test_no_overwrite_and_no_manifest_placeholders_or_raw_payload(self, tmp_path):
        out, manifest = self._ingest(tmp_path, "no_overwrite")
        with pytest.raises(OverwriteRefused):
            ingest_official_csv(
                _contract(),
                out_dir=out,
                csv_path_override=tmp_path / "no_overwrite.csv",
                schema_override=_schema_for_counts(
                    {label: 4 for label in LABELS}, row_count=16
                ),
            )
        serialized = (out / "manifest.json").read_text(encoding="utf-8")
        assert "compute_on_demand" not in serialized
        assert "token0 alpha" not in serialized
        assert "[0.00" not in serialized
        assert "manifest" not in {entry["role"] for entry in manifest["output_files"]}
        for entry in manifest["output_files"]:
            assert HEX64.fullmatch(entry["sha256"])
            assert isinstance(entry["size_bytes"], int)


class TestLocalOnlyAndSafety:
    def test_directory_gitignore_protects_records_and_splits(self):
        ignore = (OUTPUT_DIR / ".gitignore").read_text(encoding="utf-8")
        assert "records.jsonl" in ignore
        assert "splits/*.jsonl" in ignore
        for filename in (
            "records.jsonl",
            "splits/train.jsonl",
            "splits/dev.jsonl",
            "splits/test.jsonl",
        ):
            result = subprocess.run(
                ["git", "check-ignore", "--no-index", str(OUTPUT_DIR / filename)],
                cwd=PROJECT_ROOT.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            assert result.returncode == 0, result.stderr

    def test_schema_audit_writer_refuses_overwrite(self, tmp_path):
        path = tmp_path / "schema_audit.json"
        report = {"status": "verified", "contains_raw_text": False}
        write_schema_audit(report, path)
        with pytest.raises(OverwriteRefused):
            write_schema_audit(report, path)

    def test_official_module_has_no_network_llm_env_or_training_imports(self):
        source = (
            PROJECT_ROOT
            / "src"
            / "bpc_hybrid"
            / "datasets"
            / "sun_modality_official.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "import requests",
            "import urllib",
            "import openai",
            "import anthropic",
            "import torch",
            "import tensorflow",
            "import sklearn",
            "os.environ",
            "os.getenv",
            "load_dotenv",
        ):
            assert forbidden not in source

    def test_synthetic_import_does_not_modify_s2_1_a_or_official_zip(self, tmp_path):
        before = {
            SOURCE_MANIFEST: compute_file_sha256(SOURCE_MANIFEST),
            OFFICIAL_ZIP: (OFFICIAL_ZIP.stat().st_size, OFFICIAL_ZIP.stat().st_mtime_ns),
        }
        rows = _base_rows()
        csv_path = _write_rows(tmp_path / "safe.csv", rows)
        ingest_official_csv(
            _contract(),
            out_dir=tmp_path / "safe_out",
            csv_path_override=csv_path,
            schema_override=_schema_for_counts(
                {label: 4 for label in LABELS}, row_count=len(rows)
            ),
        )
        assert compute_file_sha256(SOURCE_MANIFEST) == before[SOURCE_MANIFEST]
        assert (OFFICIAL_ZIP.stat().st_size, OFFICIAL_ZIP.stat().st_mtime_ns) == before[
            OFFICIAL_ZIP
        ]
