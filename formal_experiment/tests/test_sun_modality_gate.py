"""S2.1-D fail-closed machine-gate and isolation tests.

The positive test hashes the real local ZIP once.  Negative tests monkeypatch
only the observed view of one artifact/hash at a time, so they exercise the
same production gate without copying or reopening the 470 MB CSV member.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import formal_experiment.sun_modality_gate as gate  # noqa: E402
from formal_experiment.audit import collect_project_audit  # noqa: E402
from formal_experiment.status import collect_status  # noqa: E402


def _run_failed() -> dict:
    result = gate.verify_sun_modality_development_data(PROJECT_ROOT)
    assert result["ready"] is False
    assert result["errors"]
    assert result["blockers"]
    return result


@pytest.fixture
def fast_zip(monkeypatch):
    """Avoid rehashing 192 MB in every negative branch."""
    monkeypatch.setattr(
        gate,
        "_zip_hashes",
        lambda _path: (
            gate.SUN_MODALITY_EXPECTATIONS.zip_sha1,
            gate.SUN_MODALITY_EXPECTATIONS.zip_sha256,
        ),
    )


def _mutate_loaded_json(monkeypatch, relative: str, mutate) -> None:
    original = gate._load_json
    target = (PROJECT_ROOT / relative).resolve()

    def fake(path: Path):
        value = original(path)
        if path.resolve() == target:
            mutate(value)
        return value

    monkeypatch.setattr(gate, "_load_json", fake)


def _mutate_jsonl(monkeypatch, relative: str, mutate) -> None:
    original = gate._read_jsonl
    target = (PROJECT_ROOT / relative).resolve()

    def fake(path: Path):
        rows, errors = original(path)
        if path.resolve() == target:
            rows = mutate(copy.deepcopy(rows))
        return rows, errors

    monkeypatch.setattr(gate, "_read_jsonl", fake)


class TestRealGatePositive:
    def test_current_real_artifacts_pass_and_output_is_complete(self):
        result = gate.get_cached_sun_modality_gate(PROJECT_ROOT)
        assert result["ready"] is True
        for key in (
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
        ):
            assert result[key] is True
        assert result["errors"] == []
        assert result["blockers"] == []
        checked = {item["path"] for item in result["checked_artifacts"]}
        assert {
            gate.SOURCE_ZIP_REL,
            gate.SOURCE_MANIFEST_REL,
            gate.DATASET_CONTRACT_REL,
            gate.SCHEMA_AUDIT_REL,
            gate.MANIFEST_REL,
            gate.SUMMARY_REL,
            gate.QUARANTINE_REL,
            gate.RECORDS_REL,
            *gate.SPLIT_RELS.values(),
        }.issubset(checked)


class TestSourceAndArtifactHashFailures:
    def test_zip_size_mismatch_fails_closed(self, fast_zip):
        wrong = dataclasses.replace(
            gate.SUN_MODALITY_EXPECTATIONS,
            zip_size=gate.SUN_MODALITY_EXPECTATIONS.zip_size + 1,
        )
        result = gate.verify_sun_modality_development_data(
            PROJECT_ROOT, expectations=wrong
        )
        assert result["ready"] is False
        assert result["source_identity_ok"] is False

    @pytest.mark.parametrize("algorithm", ["sha1", "sha256"])
    def test_zip_hash_mismatch_fails_closed(self, monkeypatch, algorithm):
        expected = gate.SUN_MODALITY_EXPECTATIONS
        actual = (
            "0" * 40 if algorithm == "sha1" else expected.zip_sha1,
            "0" * 64 if algorithm == "sha256" else expected.zip_sha256,
        )
        monkeypatch.setattr(gate, "_zip_hashes", lambda _path: actual)
        result = _run_failed()
        assert result["source_identity_ok"] is False

    def test_dataset_contract_recorded_hash_mismatch(self, monkeypatch, fast_zip):
        _mutate_loaded_json(
            monkeypatch,
            gate.MANIFEST_REL,
            lambda doc: doc.__setitem__("contract_sha256", "0" * 64),
        )
        result = _run_failed()
        assert result["contract_ok"] is False

    @pytest.mark.parametrize(
        ("relative", "keys"),
        [
            (gate.MANIFEST_REL, ("manifest", "sha256")),
            (gate.SCHEMA_AUDIT_REL, ("schema_audit", "sha256")),
            (gate.SUMMARY_REL, ("split_summary", "sha256")),
            (gate.QUARANTINE_REL, ("quarantine_manifest", "sha256")),
            (gate.RECORDS_REL, ("records", "sha256")),
            (gate.SPLIT_RELS["train"], ("splits", "train", "sha256")),
            (gate.SPLIT_RELS["dev"], ("splits", "dev", "sha256")),
            (gate.SPLIT_RELS["test"], ("splits", "test", "sha256")),
        ],
    )
    def test_each_artifact_hash_mismatch_fails_closed(
        self, monkeypatch, fast_zip, relative, keys
    ):
        def mutate(doc):
            node = doc["stage2_dataset"]["modality_dataset"]
            for key in keys[:-1]:
                node = node[key]
            node[keys[-1]] = "0" * 64

        _mutate_loaded_json(
            monkeypatch, gate.EXPERIMENT_CONTRACT_REL, mutate
        )
        result = _run_failed()
        assert result["artifact_hashes_ok"] is False


class TestSemanticFailures:
    @pytest.mark.parametrize("field", ["source_population_size", "analysis_population_size"])
    def test_population_mismatch(self, monkeypatch, fast_zip, field):
        _mutate_loaded_json(
            monkeypatch,
            gate.MANIFEST_REL,
            lambda doc: doc["population"].__setitem__(
                field, doc["population"][field] + 1
            ),
        )
        result = _run_failed()
        assert result["population_ok"] is False

    def test_quarantine_count_mismatch(self, monkeypatch, fast_zip):
        _mutate_loaded_json(
            monkeypatch,
            gate.QUARANTINE_REL,
            lambda doc: doc["population"].__setitem__(
                "quarantined_record_count", 3
            ),
        )
        assert _run_failed()["population_ok"] is False

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("row_indices", [616, 1222]),
            ("normalized_text_sha256", "0" * 64),
            ("raw_text_sha256", "0" * 64),
            ("original_labels_by_row", {"616": "obligation", "1221": "obligation"}),
        ],
    )
    def test_quarantine_descriptor_mismatch(
        self, monkeypatch, fast_zip, field, value
    ):
        _mutate_loaded_json(
            monkeypatch,
            gate.QUARANTINE_REL,
            lambda doc: doc["quarantined_groups"][0].__setitem__(field, value),
        )
        assert _run_failed()["quarantine_ok"] is False

    def test_raw_source_labels_modified_true_fails(self, monkeypatch, fast_zip):
        _mutate_loaded_json(
            monkeypatch,
            gate.QUARANTINE_REL,
            lambda doc: doc["policy"].__setitem__(
                "raw_source_labels_modified", True
            ),
        )
        assert _run_failed()["quarantine_ok"] is False

    def test_sensitivity_status_change_fails(self, monkeypatch, fast_zip):
        _mutate_loaded_json(
            monkeypatch,
            gate.QUARANTINE_REL,
            lambda doc: doc["sensitivity_full_source_variant"].__setitem__(
                "status", "executed"
            ),
        )
        assert _run_failed()["quarantine_ok"] is False

    def test_label_distribution_mismatch(self, monkeypatch, fast_zip):
        _mutate_loaded_json(
            monkeypatch,
            gate.MANIFEST_REL,
            lambda doc: doc["label_distribution_valid"].__setitem__(
                "definition", 1189
            ),
        )
        assert _run_failed()["label_distribution_ok"] is False

    def test_split_size_mismatch(self, monkeypatch, fast_zip):
        _mutate_jsonl(
            monkeypatch, gate.SPLIT_RELS["test"], lambda rows: rows[:-1]
        )
        result = _run_failed()
        assert result["split_ok"] is False

    def test_split_overlap(self, monkeypatch, fast_zip):
        train_rows, _ = gate._read_jsonl(PROJECT_ROOT / gate.SPLIT_RELS["train"])
        _mutate_jsonl(
            monkeypatch,
            gate.SPLIT_RELS["dev"],
            lambda rows: [train_rows[0], *rows],
        )
        assert _run_failed()["split_ok"] is False

    def test_split_union_incomplete(self, monkeypatch, fast_zip):
        _mutate_jsonl(
            monkeypatch, gate.SPLIT_RELS["dev"], lambda rows: rows[:-1]
        )
        assert _run_failed()["split_ok"] is False

    def test_normalized_text_cross_split(self, monkeypatch, fast_zip):
        train_rows, _ = gate._read_jsonl(PROJECT_ROOT / gate.SPLIT_RELS["train"])

        def leak(rows):
            rows[0]["normalized_text"] = train_rows[0]["normalized_text"]
            return rows

        _mutate_jsonl(monkeypatch, gate.SPLIT_RELS["dev"], leak)
        assert _run_failed()["split_ok"] is False

    def test_quarantine_row_enters_records(self, monkeypatch, fast_zip):
        def mutate(rows):
            rows[0]["source_row_index"] = 616
            return rows

        _mutate_jsonl(monkeypatch, gate.RECORDS_REL, mutate)
        result = _run_failed()
        assert result["quarantine_ok"] is False

    def test_membership_hash_mismatch(self, monkeypatch, fast_zip):
        _mutate_loaded_json(
            monkeypatch,
            gate.MANIFEST_REL,
            lambda doc: doc["membership_hash"].__setitem__("value", "0" * 64),
        )
        assert _run_failed()["membership_hash_ok"] is False

    def test_license_cannot_be_relaxed(self, monkeypatch, fast_zip):
        _mutate_loaded_json(
            monkeypatch,
            gate.MANIFEST_REL,
            lambda doc: doc["license"].__setitem__(
                "redistribution_allowed", True
            ),
        )
        assert _run_failed()["license_boundary_ok"] is False

    def test_formal_use_cannot_be_promoted(self, monkeypatch, fast_zip):
        def mutate(doc):
            doc["stage2_dataset"]["modality_dataset"]["formal_use"] = "formal"

        _mutate_loaded_json(
            monkeypatch, gate.EXPERIMENT_CONTRACT_REL, mutate
        )
        result = _run_failed()
        assert result["license_boundary_ok"] is False
        assert result["contract_ok"] is False

    def test_sun_original_split_claim_fails(self, monkeypatch, fast_zip):
        _mutate_loaded_json(
            monkeypatch,
            gate.MANIFEST_REL,
            lambda doc: doc.__setitem__("split_origin", "sun_original_split"),
        )
        result = _run_failed()
        assert result["split_ok"] is False
        assert result["contract_ok"] is False

    def test_absolute_manifest_path_fails(self, monkeypatch, fast_zip):
        _mutate_loaded_json(
            monkeypatch,
            gate.MANIFEST_REL,
            lambda doc: doc.__setitem__(
                "contract_path", "D:/machine/configs/dataset.json"
            ),
        )
        assert _run_failed()["paths_portable"] is False

    def test_records_and_splits_must_be_ignored(self, monkeypatch, fast_zip):
        original = Path.read_text
        target = (PROJECT_ROOT / gate.LOCAL_IGNORE_REL).resolve()

        def fake(path: Path, *args, **kwargs):
            if path.resolve() == target:
                return "# deliberately missing rules\n"
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", fake)
        assert _run_failed()["local_data_ignored"] is False

    def test_missing_required_artifact_fails(self, monkeypatch, fast_zip):
        original = Path.is_file
        target = (PROJECT_ROOT / gate.SCHEMA_AUDIT_REL).resolve()

        def fake(path: Path):
            if path.resolve() == target:
                return False
            return original(path)

        monkeypatch.setattr(Path, "is_file", fake)
        result = _run_failed()
        assert result["artifact_hashes_ok"] is False

    def test_one_mismatch_cannot_be_overridden_by_true_booleans(
        self, monkeypatch, fast_zip
    ):
        def mutate(doc):
            doc["stage2_dataset"]["modality_dataset"]["manifest"]["sha256"] = (
                "0" * 64
            )

        _mutate_loaded_json(
            monkeypatch, gate.EXPERIMENT_CONTRACT_REL, mutate
        )
        result = _run_failed()
        assert result["artifact_hashes_ok"] is False
        assert result["source_identity_ok"] is True
        assert result["population_ok"] is True


class TestGateIsolation:
    def test_modality_verified_does_not_unlock_other_gates_or_methods(self):
        status = collect_status()
        assert status["sun_modality_development_data_verified"] is True
        assert status["human_review_input_ready"] is True
        assert status["human_review_freeze_ready"] is False
        assert status["formal_gold_publication_ready"] is False
        assert status["final_experiment_ready"] is False
        assert status["route"]["status"] != "locked"
        contract = json.loads(
            (PROJECT_ROOT / gate.EXPERIMENT_CONTRACT_REL).read_text(encoding="utf-8")
        )
        assert contract["stage3"]["status"] != "locked"
        publication_gate = contract["formal_gold_publication_gate"]
        assert publication_gate["status"] not in publication_gate[
            "allowed_publication_statuses"
        ]
        assert all(
            method["formal_status"] != "ready" for method in status["methods"]
        )
        assert next(
            method for method in status["methods"] if method["id"] == "sun_rule_only"
        )["formal_status"] == "blocked_final_sun_stage2_reimplementation_required"
        manifest = json.loads(
            (PROJECT_ROOT / gate.MANIFEST_REL).read_text(encoding="utf-8")
        )
        assert manifest["lifecycle"]["ready_for_training"] is False
        assert manifest["lifecycle"]["ready_for_evaluation"] is False
        assert contract["stage2_dataset"]["modality_dataset"]["claim_boundaries"][
            "training_or_evaluation_run"
        ] is False

    def test_audit_replaces_stale_blocker_and_reports_precise_pass(self):
        audit = collect_project_audit()
        assert audit["integrity_pass"] is True
        assert audit["sun_modality_development_data_verified"] is True
        passes = {item["code"] for item in audit["findings"]["passes"]}
        blockers = {item["code"] for item in audit["findings"]["blockers"]}
        assert "sun_modality_dataset_verified" in passes
        assert "stage2_dataset_route_relock_pending" in blockers
        assert "stage2_dataset_alignment_pending" not in blockers
        assert audit["human_review_freeze_ready"] is False
        assert audit["formal_gold_publication_ready"] is False
        assert audit["final_experiment_ready"] is False

