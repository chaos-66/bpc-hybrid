"""S2.1-B-R1 contract-repair tests using synthetic bytes only.

The complete real ``EStG_sent_vec.csv`` is never opened by this module. Tiny
synthetic ZIPs cover streaming SHA-1/SHA-256 and inspect-only behavior.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CONTRACT_PATH = _PROJECT_ROOT / "configs" / "datasets" / "sun_modality_dataset.json"
_MANIFEST_SCHEMA_PATH = _PROJECT_ROOT / "configs" / "schemas" / "dataset_manifest.schema.json"
_CLI_PATH = _PROJECT_ROOT / "scripts" / "ingest_sun_modality.py"
_FIXTURE_DIR = _PROJECT_ROOT / "tests" / "fixtures" / "sun_modality"
_S2_1_A_MANIFEST = _PROJECT_ROOT / "data" / "development" / "sun_modality" / "source_manifest.json"
_S2_1_A_INGESTION_DOC = _PROJECT_ROOT / "docs" / "research" / "SUN_MODALITY_DATASET_INGESTION.md"
_OFFICIAL_ZIP = _PROJECT_ROOT / "data" / "development" / "sun_modality" / "raw" / "Decision_Logic_data.zip"
_RAW_GITIGNORE = _PROJECT_ROOT / "data" / "development" / "sun_modality" / "raw" / ".gitignore"
_ROOT_GITIGNORE = _PROJECT_ROOT.parent / ".gitignore"
_SRC = _PROJECT_ROOT / "src"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.datasets.sun_modality_importer import (  # noqa: E402
    DuplicateSourceIdError,
    IngestionError,
    LabelConflictError,
    MissingSourceIdError,
    OneHotError,
    OverwriteRefused,
    SchemaError,
    SplitParams,
    build_sample_id,
    check_cross_split_leakage,
    compute_file_sha1,
    compute_file_sha256,
    compute_membership_hash,
    compute_zip_member_sha256,
    default_normalize_for_dedup,
    deterministic_stratified_split,
    ingest,
    inspect_only,
    load_contract,
    stream_csv_rows_from_csv_path,
    stream_csv_rows_from_zip,
    strict_one_hot_label_adapter,
    validate_label,
)


ID_COLUMN = "source_id"
TEXT_COLUMN = "text"
LABEL_COLUMNS = [
    "label_definition",
    "label_obligation",
    "label_permission",
    "label_prohibition",
]
LABEL_CLASSES = ("definition", "obligation", "permission", "prohibition")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _fixture(name: str) -> Path:
    return _FIXTURE_DIR / name


def _load_records(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _load_manifest(out_dir: Path) -> dict:
    return json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))


def _ingest_with(
    fixture: Path,
    out_dir: Path,
    *,
    seed: int = 20260715,
    id_column: str | None = ID_COLUMN,
    allow_overwrite: bool = True,
) -> dict:
    contract = load_contract(_CONTRACT_PATH, project_root=_PROJECT_ROOT)
    contract = dataclasses.replace(contract, seed=seed)
    return ingest(
        contract,
        text_column=TEXT_COLUMN,
        label_columns=LABEL_COLUMNS,
        id_column=id_column,
        out_dir=out_dir,
        allow_overwrite=allow_overwrite,
        csv_path_override=fixture,
    )


def _write_tiny_zip(tmp_path: Path, csv_fixture: Path | None = None) -> tuple[Path, bytes]:
    csv_fixture = csv_fixture or _fixture("synthetic_normal.csv")
    csv_bytes = csv_fixture.read_bytes()
    zip_path = tmp_path / "tiny_synthetic.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("EStG_sent_vec.csv", csv_bytes)
        zf.writestr("EStG_raw.txt", b"SYNTHETIC_TEST_ONLY\n")
        zf.writestr("estg.html", b"<p>SYNTHETIC_TEST_ONLY</p>\n")
    return zip_path, csv_bytes


def _tiny_zip_contract(tmp_path: Path, csv_fixture: Path | None = None):
    zip_path, csv_bytes = _write_tiny_zip(tmp_path, csv_fixture)
    base = load_contract(_CONTRACT_PATH, project_root=_PROJECT_ROOT)
    with zipfile.ZipFile(zip_path, "r") as zf:
        info = zf.getinfo("EStG_sent_vec.csv")
    contract = dataclasses.replace(
        base,
        source_zip_path=zip_path,
        source_zip_sha256=compute_file_sha256(zip_path),
        source_zip_official_sha1=compute_file_sha1(zip_path),
        source_zip_size_bytes=zip_path.stat().st_size,
        csv_member_sha256=hashlib.sha256(csv_bytes).hexdigest(),
        csv_member_size_uncompressed_bytes=len(csv_bytes),
        csv_member_crc32=f"{info.CRC:08X}",
    )
    return contract


def _write_tiny_contract_json(tmp_path: Path) -> Path:
    contract = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
    zip_path, csv_bytes = _write_tiny_zip(tmp_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        info = zf.getinfo("EStG_sent_vec.csv")
    contract.update(
        {
            "source_zip_local_path": str(zip_path),
            "source_zip_official_sha1": compute_file_sha1(zip_path),
            "source_zip_local_sha256": compute_file_sha256(zip_path),
            "source_zip_size_bytes": zip_path.stat().st_size,
            "csv_member_local_sha256": hashlib.sha256(csv_bytes).hexdigest(),
            "csv_member_size_uncompressed_bytes": len(csv_bytes),
            "csv_member_crc32": f"{info.CRC:08X}",
        }
    )
    path = tmp_path / "tiny_contract.json"
    path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
    return path


def _normalized_text_locations(out_dir: Path) -> dict[str, set[str]]:
    locations: dict[str, set[str]] = {}
    for split_name in ("train", "dev", "test"):
        for record in _load_records(out_dir / "splits" / f"{split_name}.jsonl"):
            locations.setdefault(record["normalized_text"], set()).add(split_name)
    return locations


class TestContractAndSchema:
    def test_contract_keeps_synthetic_separate_from_verified_official_schema(self):
        raw = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
        assert raw["contract_version"] == "sun_modality_dataset_contract@1.3.1"
        assert raw["synthetic_fixture_adapter"]["adapter"] == "strict_one_hot"
        assert raw["synthetic_fixture_adapter"]["id_column"] == ID_COLUMN
        assert raw["official_csv_schema"]["status"] == "verified"
        assert raw["official_csv_schema"]["has_header"] is False
        assert raw["official_label_mode"] == "headerless_positional_strict_one_hot"
        assert raw["official_integer_code_mapping"]["status"] == (
            "not_applicable_verified_no_integer_modality_column"
        )
        assert raw["official_integer_code_mapping"]["mapping"] is None
        assert raw["official_integer_code_mapping"]["must_not_guess"] is True
        assert raw["official_positional_one_hot_mapping"]["mapping_evidence_level"] == (
            "inferred_by_exact_distribution_match"
        )
        assert "label_column_mode_expected" not in raw["label_taxonomy"]

    def test_contract_uses_one_exact_small_class_formula(self):
        split = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))["split"]
        assert split["small_class_group_threshold_formula"] == (
            "active_nonzero_splits * min_per_class_in_smallest_split"
        )
        assert split["small_class_group_threshold_current"] == 3
        assert split["allocation_unit"] == "normalized_text group"

    def test_contract_hashes_and_typed_loader(self):
        contract = load_contract(_CONTRACT_PATH, project_root=_PROJECT_ROOT)
        assert contract.label_classes == LABEL_CLASSES
        assert contract.seed == 20260715
        assert contract.source_zip_official_sha1 == (
            "0346f84a246b7049d5aef58bcb33471435bee106"
        )
        assert HEX64.fullmatch(contract.source_zip_sha256)
        assert HEX64.fullmatch(contract.contract_sha256)

    def test_manifest_schema_removes_time_and_self_reference_exceptions(self):
        schema_text = _MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8")
        schema = json.loads(schema_text)
        assert schema["$id"] == "dataset_manifest.schema.json@1.3.1"
        assert schema["properties"]["schema_version"]["const"] == "1.3.1"
        assert {"split_origin", "source_schema", "vector_policy"}.issubset(
            schema["required"]
        )
        assert "created_at" not in schema["required"]
        assert "created_at" not in schema["properties"]
        assert "compute_on_demand" not in schema_text
        roles = schema["properties"]["output_files"]["items"]["properties"]["role"]["enum"]
        assert "manifest" not in roles
        assert schema["properties"]["output_files"]["items"]["properties"]["sha256"]["pattern"] == "^[0-9a-f]{64}$"

    def test_label_adapter_seam_exists_and_integer_mapping_is_not_applicable(self):
        assert "label_adapter" in inspect.signature(ingest).parameters
        assert strict_one_hot_label_adapter.__doc__
        raw = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
        assert raw["official_integer_code_mapping"]["mapping"] is None
        assert raw["official_integer_code_mapping"]["must_not_guess"] is True


class TestSourceIdAndStableId:
    SOURCE_SHA = "a" * 64

    def test_sample_id_prefers_source_id_and_is_deterministic(self):
        first = build_sample_id(
            self.SOURCE_SHA,
            "hello world",
            source_id="source-7",
            row_index=1,
        )
        second = build_sample_id(
            self.SOURCE_SHA,
            "hello world",
            source_id="source-7",
            row_index=999,
        )
        assert first == second
        assert re.fullmatch(r"sun_modality_[0-9a-f]{16}", first)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"source_asset_sha256": "b" * 64, "source_id": "source-7"},
            {"source_asset_sha256": "a" * 64, "source_id": "source-8"},
        ],
    )
    def test_sample_id_changes_with_source_identity(self, kwargs):
        baseline = build_sample_id(self.SOURCE_SHA, "hello", source_id="source-7")
        changed = build_sample_id(
            kwargs["source_asset_sha256"],
            "hello",
            source_id=kwargs["source_id"],
        )
        assert baseline != changed

    def test_explicit_row_fallback_is_stable_and_row_sensitive(self):
        first = build_sample_id(self.SOURCE_SHA, "same", row_index=0)
        second = build_sample_id(self.SOURCE_SHA, "same", row_index=1)
        assert first != second
        with pytest.raises(IngestionError, match="explicitly provided"):
            build_sample_id(self.SOURCE_SHA, "same")

    def test_streamer_reads_real_source_id_column(self):
        rows = list(
            stream_csv_rows_from_csv_path(
                _fixture("synthetic_normal.csv"),
                text_column=TEXT_COLUMN,
                label_columns=LABEL_COLUMNS,
                id_column=ID_COLUMN,
            )
        )
        assert rows[0].source_id == "normal-001"
        assert len({row.source_id for row in rows}) == len(rows)

    def test_duplicate_source_id_fails_closed(self, tmp_path):
        out = tmp_path / "duplicate"
        with pytest.raises(DuplicateSourceIdError, match="duplicate_source_id") as exc:
            _ingest_with(_fixture("synthetic_duplicate_id.csv"), out)
        assert exc.value.stats["rejected_duplicate_id"] == 1
        assert not (out / "records.jsonl").exists()
        assert not (out / "manifest.json").exists()

    def test_configured_id_column_never_silently_falls_back(self, tmp_path):
        out = tmp_path / "missing_id_column"
        with pytest.raises(SchemaError, match="missing id column"):
            _ingest_with(_fixture("synthetic_no_source_id.csv"), out)
        assert not (out / "manifest.json").exists()

    def test_empty_configured_source_id_fails_closed(self, tmp_path):
        csv_path = tmp_path / "empty_source_id.csv"
        csv_path.write_text(
            "source_id,text,label_definition,label_obligation,label_permission,label_prohibition\n"
            ",Definition A,1,0,0,0\n",
            encoding="utf-8",
        )
        out = tmp_path / "empty_id_out"
        with pytest.raises(MissingSourceIdError, match="missing_source_id"):
            _ingest_with(csv_path, out)
        assert not (out / "manifest.json").exists()

    def test_no_id_column_uses_and_records_row_fallback(self, tmp_path):
        out = tmp_path / "fallback"
        manifest = _ingest_with(
            _fixture("synthetic_no_source_id.csv"), out, id_column=None
        )
        policy = manifest["sample_id_policy"]
        assert policy["source_id_column"] is None
        assert policy["source_id_mode"] == "row_index_fallback"
        assert policy["row_index_fallback_used"] is True
        records = _load_records(out / "records.jsonl")
        assert all(record["source_id"] is None for record in records)
        assert {record["sample_id_source"] for record in records} == {
            "row_index_fallback"
        }


class TestNormalizationAndLabels:
    def test_normalization_is_unicode_aware_and_punctuation_insensitive(self):
        assert default_normalize_for_dedup("Erklärung, A!") == (
            default_normalize_for_dedup("erklärung a")
        )
        assert default_normalize_for_dedup("alpha   beta\tgamma") == "alphabetagamma"

    @pytest.mark.parametrize(
        "cells,expected",
        [
            (["1", "0", "0", "0"], "definition"),
            (["0", "0", "1.0", "0"], "permission"),
        ],
    )
    def test_valid_synthetic_strict_one_hot(self, cells, expected):
        label, total, width = validate_label(
            cells,
            LABEL_CLASSES,
            reject_all_zero=True,
            reject_multi_hot=True,
            reject_non_binary=True,
        )
        assert (label, total, width) == (expected, 1, 4)

    @pytest.mark.parametrize(
        "cells",
        [
            ["0", "0", "0", "0"],
            ["1", "1", "0", "0"],
            ["0.5", "0", "0", "0"],
        ],
    )
    def test_invalid_synthetic_strict_one_hot(self, cells):
        with pytest.raises(OneHotError):
            validate_label(
                cells,
                LABEL_CLASSES,
                reject_all_zero=True,
                reject_multi_hot=True,
                reject_non_binary=True,
            )


class TestGroupAwareSplitAndConflicts:
    def test_same_text_same_label_group_never_crosses_split(self, tmp_path):
        out = tmp_path / "grouped"
        manifest = _ingest_with(
            _fixture("synthetic_duplicate_text_same_label.csv"), out
        )
        assert manifest["total_samples_valid"] == 24
        assert all(len(splits) == 1 for splits in _normalized_text_locations(out).values())

    @pytest.mark.parametrize("seed", [1, 2, 20260715, 99999])
    def test_different_seeds_still_have_no_cross_split_text_leakage(
        self, tmp_path, seed
    ):
        out = tmp_path / f"seed_{seed}"
        _ingest_with(
            _fixture("synthetic_duplicate_text_same_label.csv"),
            out,
            seed=seed,
        )
        assert all(len(splits) == 1 for splits in _normalized_text_locations(out).values())

    def test_conflicting_label_fails_closed_and_records_label_conflict(self, tmp_path):
        out = tmp_path / "conflict"
        with pytest.raises(LabelConflictError, match="label_conflict") as exc:
            _ingest_with(
                _fixture("synthetic_duplicate_text_conflicting_label.csv"), out
            )
        assert exc.value.stats["label_conflict"] == 1
        assert not (out / "records.jsonl").exists()
        assert not (out / "manifest.json").exists()

    def test_post_check_detects_an_artificial_leak(self):
        leaks = check_cross_split_leakage(
            {"train": [0], "dev": [1], "test": [2]},
            ["same", "same", "other"],
        )
        assert leaks == [("same", ("dev", "train"))]

    @pytest.mark.parametrize(
        "group_count,expected_sizes,expect_warning",
        [
            (2, (2, 0, 0), True),
            (3, (1, 1, 1), False),
            (4, (2, 1, 1), False),
        ],
    )
    def test_unique_small_class_threshold_before_at_after(
        self, group_count, expected_sizes, expect_warning, capsys
    ):
        labels = ["class-a"] * group_count
        groups = [f"group-{index}" for index in range(group_count)]
        train, dev, test = deterministic_stratified_split(
            labels,
            SplitParams(0.7, 0.15, 0.15, min_per_class_in_smallest_split=1),
            seed=20260715,
            group_keys=groups,
        )
        assert (len(train), len(dev), len(test)) == expected_sizes
        assert sorted(train + dev + test) == list(range(group_count))
        warning = capsys.readouterr().err
        if expect_warning:
            assert "active_nonzero_splits*min_per_class_in_smallest_split" in warning
            assert "threshold=3" in warning
            assert "no classes or samples dropped" in warning
        else:
            assert warning == ""

    def test_small_class_fixture_keeps_every_record(self, tmp_path, capsys):
        out = tmp_path / "small"
        manifest = _ingest_with(_fixture("synthetic_small_class.csv"), out)
        assert manifest["total_samples_valid"] == 19
        assert manifest["train_label_distribution"]["prohibition"] == 1
        assert "prohibition" not in manifest["dev_label_distribution"]
        assert "prohibition" not in manifest["test_label_distribution"]
        assert manifest["train_size"] + manifest["dev_size"] + manifest["test_size"] == 19
        assert "threshold=3" in capsys.readouterr().err


class TestDeterministicManifestAndOutputs:
    def test_same_input_contract_seed_makes_all_five_files_byte_identical(self, tmp_path):
        fixture = _fixture("synthetic_large_normal.csv")
        out_a = tmp_path / "run_a"
        out_b = tmp_path / "run_b"
        _ingest_with(fixture, out_a, seed=20260715)
        _ingest_with(fixture, out_b, seed=20260715)
        for relative in (
            "records.jsonl",
            "splits/train.jsonl",
            "splits/dev.jsonl",
            "splits/test.jsonl",
            "manifest.json",
        ):
            assert compute_file_sha256(out_a / relative) == compute_file_sha256(
                out_b / relative
            ), f"{relative} must be byte-identical"
        # Explicitly guard the previously missing manifest comparison.
        assert compute_file_sha256(out_a / "manifest.json") == compute_file_sha256(
            out_b / "manifest.json"
        )

    def test_manifest_has_no_runtime_time_or_self_child(self, tmp_path):
        out = tmp_path / "manifest"
        manifest = _ingest_with(_fixture("synthetic_normal.csv"), out)
        assert "created_at" not in manifest
        assert "timestamp" not in manifest
        assert {entry["role"] for entry in manifest["output_files"]} == {
            "records",
            "train_split",
            "dev_split",
            "test_split",
        }
        assert all(entry["role"] != "manifest" for entry in manifest["output_files"])

    def test_every_output_hash_and_size_is_actual_no_placeholder(self, tmp_path):
        out = tmp_path / "hashes"
        manifest = _ingest_with(_fixture("synthetic_normal.csv"), out)
        serialized = json.dumps(manifest, ensure_ascii=False)
        assert "compute_on_demand" not in serialized
        for entry in manifest["output_files"]:
            assert HEX64.fullmatch(entry["sha256"])
            assert isinstance(entry["size_bytes"], int)
            path = out / entry["path"]
            assert path.is_file()
            assert compute_file_sha256(path) == entry["sha256"]
            assert path.stat().st_size == entry["size_bytes"]

    def test_split_sets_are_disjoint_and_union_is_complete(self, tmp_path):
        out = tmp_path / "partition"
        _ingest_with(_fixture("synthetic_large_normal.csv"), out)
        split_ids = []
        for name in ("train", "dev", "test"):
            split_ids.append(
                {
                    record["sample_id"]
                    for record in _load_records(out / "splits" / f"{name}.jsonl")
                }
            )
        assert split_ids[0].isdisjoint(split_ids[1])
        assert split_ids[0].isdisjoint(split_ids[2])
        assert split_ids[1].isdisjoint(split_ids[2])
        all_records = _load_records(out / "records.jsonl")
        assert set.union(*split_ids) == {record["sample_id"] for record in all_records}

    def test_different_seed_changes_split_membership_not_dataset_membership(self, tmp_path):
        fixture = _fixture("synthetic_large_normal.csv")
        out_a = tmp_path / "seed_a"
        out_b = tmp_path / "seed_b"
        manifest_a = _ingest_with(fixture, out_a, seed=20260715)
        manifest_b = _ingest_with(fixture, out_b, seed=99999)
        assert manifest_a["membership_hash"] == manifest_b["membership_hash"]
        assert compute_file_sha256(out_a / "records.jsonl") == compute_file_sha256(
            out_b / "records.jsonl"
        )
        assert compute_file_sha256(out_a / "splits" / "train.jsonl") != (
            compute_file_sha256(out_b / "splits" / "train.jsonl")
        )

    def test_membership_hash_recomputes_from_persisted_records(self, tmp_path):
        out = tmp_path / "membership"
        manifest = _ingest_with(_fixture("synthetic_normal.csv"), out)
        records = _load_records(out / "records.jsonl")
        objects = [
            type("RecordIdentity", (), {"sample_id": row["sample_id"], "label": row["label"]})()
            for row in records
        ]
        assert compute_membership_hash(objects) == manifest["membership_hash"]["value"]


class TestIndependentZipHashVerification:
    def test_report_exposes_independent_sha1_and_sha256_fields(self, tmp_path):
        contract = _tiny_zip_contract(tmp_path)
        report = inspect_only(
            contract,
            text_column=TEXT_COLUMN,
            label_columns=LABEL_COLUMNS,
            id_column=ID_COLUMN,
            sample_n=2,
        ).as_dict()
        assert report["zip_actual_sha1"] == report["zip_expected_official_sha1"]
        assert report["zip_official_sha1_match"] is True
        assert report["zip_actual_sha256"] == report["zip_expected_local_sha256"]
        assert report["zip_local_sha256_match"] is True
        assert report["sample_rows"][0]["source_id"] == "normal-001"

    def test_intentionally_wrong_official_sha1_is_false_only_for_sha1(self, tmp_path):
        contract = _tiny_zip_contract(tmp_path)
        contract = dataclasses.replace(contract, source_zip_official_sha1="0" * 40)
        report = inspect_only(
            contract,
            text_column=TEXT_COLUMN,
            label_columns=LABEL_COLUMNS,
            id_column=ID_COLUMN,
            sample_n=0,
        )
        assert report.zip_official_sha1_match is False
        assert report.zip_local_sha256_match is True

    def test_intentionally_wrong_local_sha256_is_false_only_for_sha256(self, tmp_path):
        contract = _tiny_zip_contract(tmp_path)
        contract = dataclasses.replace(contract, source_zip_sha256="0" * 64)
        report = inspect_only(
            contract,
            text_column=TEXT_COLUMN,
            label_columns=LABEL_COLUMNS,
            id_column=ID_COLUMN,
            sample_n=0,
        )
        assert report.zip_official_sha1_match is True
        assert report.zip_local_sha256_match is False

    def test_inspect_only_writes_nothing(self, tmp_path):
        contract = _tiny_zip_contract(tmp_path)
        before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
        report = inspect_only(
            contract,
            text_column=TEXT_COLUMN,
            label_columns=LABEL_COLUMNS,
            id_column=ID_COLUMN,
            sample_n=1,
        )
        after = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
        assert before == after
        assert report.write_action == "none"

    def test_zip_member_stream_hash_and_rows_use_tiny_synthetic_zip(self, tmp_path):
        contract = _tiny_zip_contract(tmp_path)
        assert compute_zip_member_sha256(
            contract.source_zip_path, contract.csv_member_logical_name
        ) == contract.csv_member_sha256
        rows = list(
            stream_csv_rows_from_zip(
                contract.source_zip_path,
                contract.csv_member_logical_name,
                text_column=TEXT_COLUMN,
                label_columns=LABEL_COLUMNS,
                id_column=ID_COLUMN,
            )
        )
        assert rows[0].source_id == "normal-001"
        assert len(rows) == 10


class TestNegativeFixturesAndOverwrite:
    def test_empty_text_is_rejected_without_dropping_other_rows(self, tmp_path):
        manifest = _ingest_with(_fixture("synthetic_empty_text.csv"), tmp_path / "empty")
        assert manifest["total_samples_in"] == 3
        assert manifest["total_samples_valid"] == 2
        assert manifest["stats"]["rejected_empty_text"] == 1

    @pytest.mark.parametrize(
        "fixture_name,stat_key",
        [
            ("synthetic_unknown_label.csv", "rejected_one_hot_non_binary"),
            ("synthetic_one_hot_multi_hot.csv", "rejected_one_hot_multi_hot"),
            ("synthetic_one_hot_non_binary.csv", "rejected_one_hot_non_binary"),
        ],
    )
    def test_bad_one_hot_rows_use_exact_stats(self, tmp_path, fixture_name, stat_key):
        manifest = _ingest_with(_fixture(fixture_name), tmp_path / fixture_name)
        assert manifest["stats"][stat_key] == 1
        assert manifest["total_samples_valid"] == 1

    def test_all_zero_fixture_with_no_valid_rows_raises(self, tmp_path):
        with pytest.raises(IngestionError, match="no valid records"):
            _ingest_with(
                _fixture("synthetic_one_hot_all_zero.csv"), tmp_path / "all_zero"
            )

    def test_missing_label_column_raises_schema(self, tmp_path):
        with pytest.raises(SchemaError, match="missing label columns"):
            _ingest_with(
                _fixture("synthetic_missing_label_column.csv"), tmp_path / "missing"
            )

    def test_default_no_overwrite_refuses_existing_outputs(self, tmp_path):
        out = tmp_path / "overwrite"
        _ingest_with(_fixture("synthetic_normal.csv"), out)
        with pytest.raises(OverwriteRefused):
            _ingest_with(
                _fixture("synthetic_normal.csv"),
                out,
                allow_overwrite=False,
            )


class TestCliAndSafety:
    def test_cli_ingests_synthetic_with_explicit_id_column(self, tmp_path):
        out = tmp_path / "cli_out"
        result = subprocess.run(
            [
                sys.executable,
                str(_CLI_PATH),
                "--contract",
                str(_CONTRACT_PATH),
                "--project-root",
                str(_PROJECT_ROOT),
                "--csv-path",
                str(_fixture("synthetic_normal.csv")),
                "--text-column",
                TEXT_COLUMN,
                "--id-column",
                ID_COLUMN,
                "--label-columns",
                ",".join(LABEL_COLUMNS),
                "--out-dir",
                str(out),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["sample_id_policy"]["source_id_mode"] == (
            "explicit_source_id"
        )

    def test_cli_inspect_uses_tiny_zip_and_reports_both_hashes(self, tmp_path):
        contract_path = _write_tiny_contract_json(tmp_path)
        before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
        result = subprocess.run(
            [
                sys.executable,
                str(_CLI_PATH),
                "--contract",
                str(contract_path),
                "--project-root",
                str(_PROJECT_ROOT),
                "--inspect-only",
                "--text-column",
                TEXT_COLUMN,
                "--id-column",
                ID_COLUMN,
                "--label-columns",
                ",".join(LABEL_COLUMNS),
                "--inspect-sample-n",
                "1",
            ],
            cwd=tmp_path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert report["zip_official_sha1_match"] is True
        assert report["zip_local_sha256_match"] is True
        after = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
        assert before == after

    def test_importer_has_no_network_llm_env_or_data_stack_imports(self):
        source = (
            _PROJECT_ROOT / "src" / "bpc_hybrid" / "datasets" / "sun_modality_importer.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "import openai",
            "import anthropic",
            "import requests",
            "import urllib.request",
            "import pandas",
            "import numpy",
            "import sklearn",
            "import torch",
            "import tensorflow",
            "os.environ",
            "os.getenv",
            "load_dotenv",
        ):
            assert forbidden not in source

    def test_s2_1_a_artifacts_are_unchanged_by_synthetic_ingest(self, tmp_path):
        before_small_files = {
            _S2_1_A_MANIFEST: compute_file_sha256(_S2_1_A_MANIFEST),
            _S2_1_A_INGESTION_DOC: compute_file_sha256(_S2_1_A_INGESTION_DOC),
        }
        # Stat only: this repair never opens or hashes the complete official ZIP.
        before_zip_stat = (
            _OFFICIAL_ZIP.stat().st_size,
            _OFFICIAL_ZIP.stat().st_mtime_ns,
        )
        _ingest_with(_fixture("synthetic_normal.csv"), tmp_path / "safe")
        for path, digest in before_small_files.items():
            assert compute_file_sha256(path) == digest
        assert (_OFFICIAL_ZIP.stat().st_size, _OFFICIAL_ZIP.stat().st_mtime_ns) == (
            before_zip_stat
        )

    def test_official_raw_zip_remains_ignored_without_editing_root_gitignore(self):
        assert _RAW_GITIGNORE.is_file()
        assert "*" in _RAW_GITIGNORE.read_text(encoding="utf-8")
        assert _ROOT_GITIGNORE.is_file()
        assert "sun_modality/raw" in _ROOT_GITIGNORE.read_text(encoding="utf-8")
