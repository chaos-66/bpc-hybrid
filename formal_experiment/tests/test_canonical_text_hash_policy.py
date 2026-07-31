"""G0-EOL-HASH-PORTABILITY: contract-declared controlled-text hash policy.

The S2.1-D gate verifies artifacts with raw-byte SHA-256 unless the
experiment contract explicitly declares ``hash_mode=canonical_lf_utf8_text``
for that artifact.  Only declared assets are verified on CRLF-to-LF
normalized UTF-8 text bytes, so LF and CRLF worktrees verify the same
controlled text (source_manifest.json).  Binary ZIP, JSONL records/splits,
and undeclared JSON aggregates remain raw-byte verified.

These tests cover:

1. LF and CRLF versions of the same controlled text produce the same
   canonical hash (and differ from each other on raw bytes).
2. A real one-character semantic change fails the gate closed.
3. Undeclared files are still verified on raw bytes (a CRLF/LF variation of
   an undeclared artifact fails the gate).
4. The source_manifest current Windows CRLF working tree passes.
5. Unknown declared hash modes and unnormalizable text fail closed.
6. Sun modality provenance and license boundaries are not relaxed.

The tests intentionally do NOT:
- read or print .env;
- call any LLM / API;
- mutate Gold, the human-review files, the route status, or any
  readiness / locked gates;
- modify any real artifact bytes on disk.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import formal_experiment.sun_modality_gate as gate  # noqa: E402
from formal_experiment.status import collect_status  # noqa: E402

CONTRACT_SOURCE_MANIFEST_SHA256 = (
    "cc7b4112c9fc0827a5227939a836c0e08ef68bc640fbf7d03ed91e8ce5b91982"
)


def _load_contract() -> dict:
    with (PROJECT_ROOT / gate.EXPERIMENT_CONTRACT_REL).open(
        "r", encoding="utf-8"
    ) as stream:
        return json.load(stream)


@pytest.fixture
def fast_zip(monkeypatch):
    """Avoid rehashing the 192 MB ZIP in every negative branch."""
    monkeypatch.setattr(
        gate,
        "_zip_hashes",
        lambda _path: (
            gate.SUN_MODALITY_EXPECTATIONS.zip_sha1,
            gate.SUN_MODALITY_EXPECTATIONS.zip_sha256,
        ),
    )


def _patch_read_bytes(monkeypatch, relative: str, transform) -> None:
    """Deterministically substitute the bytes a read sees for one artifact."""
    original = Path.read_bytes
    target = (PROJECT_ROOT / relative).resolve()

    def fake(path: Path, *args, **kwargs):
        if path.resolve() == target:
            return transform(original(path, *args, **kwargs))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", fake)


def _lf_variant(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n")


def _crlf_variant(raw: bytes) -> bytes:
    return _lf_variant(raw).replace(b"\n", b"\r\n")


# ---------------------------------------------------------------------------
# Unit: canonical LF digest semantics
# ---------------------------------------------------------------------------

class TestCanonicalLfDigestUnit:
    def test_lf_and_crlf_versions_hash_to_the_same_canonical_digest(self):
        lf = b'{\n  "a": 1,\n  "b": "x"\n}\n'
        crlf = b'{\r\n  "a": 1,\r\n  "b": "x"\r\n}\r\n'
        assert gate._canonical_lf_digest(lf) == gate._canonical_lf_digest(crlf)
        assert hashlib.sha256(lf).hexdigest() != hashlib.sha256(crlf).hexdigest()

    def test_one_character_change_changes_the_canonical_digest(self):
        base = b'{\n  "a": 1\n}\n'
        changed = b'{\n  "a": 2\n}\n'
        assert gate._canonical_lf_digest(base) != gate._canonical_lf_digest(changed)

    def test_invalid_utf8_fails_closed(self):
        with pytest.raises(ValueError):
            gate._canonical_lf_digest(b"\xff\xfe{\n}\n")

    def test_nul_byte_fails_closed(self):
        with pytest.raises(ValueError):
            gate._canonical_lf_digest(b"{\n\x00}\n")

    def test_bare_cr_fails_closed(self):
        with pytest.raises(ValueError):
            gate._canonical_lf_digest(b"{\r\n}\r x")  # trailing bare CR


# ---------------------------------------------------------------------------
# Contract declaration
# ---------------------------------------------------------------------------

class TestContractDeclaration:
    def test_source_manifest_declares_canonical_lf_mode(self):
        contract = _load_contract()
        modality = contract["stage2_dataset"]["modality_dataset"]
        assert modality["source_manifest"]["hash_mode"] == "canonical_lf_utf8_text"

    def test_expected_hash_value_is_unchanged(self):
        contract = _load_contract()
        modality = contract["stage2_dataset"]["modality_dataset"]
        assert modality["source_manifest"]["sha256"] == CONTRACT_SOURCE_MANIFEST_SHA256

    def test_policy_block_is_explicit_and_narrow(self):
        contract = _load_contract()
        policy = contract["stage2_dataset"]["modality_dataset"][
            "artifact_hash_policy"
        ]
        assert policy["default_mode"] == "raw_bytes"
        assert policy["declared_canonical_text_assets"] == [
            "data/development/sun_modality/source_manifest.json"
        ]
        assert "canonical_lf_utf8_text" in policy["policy"]

    def test_only_the_declared_asset_has_a_hash_mode(self):
        contract = _load_contract()
        modality = contract["stage2_dataset"]["modality_dataset"]
        declared = {
            "source_manifest": modality["source_manifest"].get("hash_mode"),
            "dataset_contract": modality["dataset_contract"].get("hash_mode"),
            "schema_audit": modality["schema_audit"].get("hash_mode"),
            "manifest": modality["manifest"].get("hash_mode"),
            "split_summary": modality["split_summary"].get("hash_mode"),
            "quarantine_manifest": modality["quarantine_manifest"].get("hash_mode"),
            "records": modality["records"].get("hash_mode"),
        }
        for name, mode in declared.items():
            if name == "source_manifest":
                assert mode == "canonical_lf_utf8_text"
            else:
                assert mode is None, f"{name} must stay raw-byte verified"

    def test_license_and_provenance_fields_are_unchanged(self):
        contract = _load_contract()
        modality = contract["stage2_dataset"]["modality_dataset"]
        assert modality["license"]["rights_status"] == "unknown_pending_confirmation"
        assert modality["license"]["redistribution_allowed"] is False
        assert modality["license"]["publication_allowed"] is False
        assert modality["formal_use"] == "development_only_not_formal_gold"
        assert modality["source"]["zip_sha1"] == gate.SUN_MODALITY_EXPECTATIONS.zip_sha1
        assert modality["machine_gate_status"] == "verified"


# ---------------------------------------------------------------------------
# Gate behavior on LF vs CRLF working trees
# ---------------------------------------------------------------------------

class TestGatePortableHashing:
    def test_forced_lf_and_forced_crlf_manifest_both_pass(self, fast_zip):
        manifest_relative = gate.SOURCE_MANIFEST_REL
        variants = (lambda raw: _lf_variant(raw), lambda raw: _crlf_variant(raw))
        for variant in variants:
            monkeypatch = pytest.MonkeyPatch()
            _patch_read_bytes(monkeypatch, manifest_relative, variant)
            try:
                result = gate.verify_sun_modality_development_data(PROJECT_ROOT)
            finally:
                monkeypatch.undo()
            assert result["ready"] is True, result["errors"]
            assert result["artifact_hashes_ok"] is True
            assert result["hash_policy"]["declared_canonical_text_assets"] == [
                "data/development/sun_modality/source_manifest.json"
            ]
        # The CRLF variant must NOT equal the raw LF digest (the test is real).
        raw = (PROJECT_ROOT / manifest_relative).read_bytes()
        assert hashlib.sha256(_crlf_variant(raw)).hexdigest() != hashlib.sha256(
            _lf_variant(raw)
        ).hexdigest()

    def test_current_working_tree_passes_through_cached_gate(self):
        # Runs the real production path (real ZIP hash, cached like the
        # existing S2.1-D positive test) against the current working tree,
        # which is CRLF under core.autocrlf=true on Windows.
        result = gate.get_cached_sun_modality_gate(PROJECT_ROOT)
        assert result["ready"] is True
        manifest_item = next(
            item
            for item in result["checked_artifacts"]
            if item["path"] == gate.SOURCE_MANIFEST_REL
        )
        assert manifest_item["hash_mode"] == "canonical_lf_utf8_text"
        assert manifest_item["sha256"] == CONTRACT_SOURCE_MANIFEST_SHA256
        assert "sha256_raw" in manifest_item

    def test_one_character_semantic_change_fails_closed(self, fast_zip):
        manifest_relative = gate.SOURCE_MANIFEST_REL

        def tamper(raw: bytes) -> bytes:
            lf = _lf_variant(raw)
            needle = b'"sun_modality_source_manifest@1.0.1"'
            assert needle in lf, "test precondition: version marker not found"
            return lf.replace(needle, b'"sun_modality_source_manifest@1.0.2"')

        _patch_read_bytes(monkeypatch := pytest.MonkeyPatch(), manifest_relative, tamper)
        try:
            result = gate.verify_sun_modality_development_data(PROJECT_ROOT)
        finally:
            monkeypatch.undo()
        assert result["ready"] is False
        assert result["artifact_hashes_ok"] is False
        assert (
            f"artifact_hash_mismatch:{manifest_relative}" in result["blockers"]
        )

    def test_undeclared_asset_is_still_raw_byte_verified(self, fast_zip):
        # A CRLF variant of an UNdeclared artifact must FAIL: the gate may
        # only normalize contract-declared canonical text assets.
        target = gate.DATASET_CONTRACT_REL
        original = gate._sha256
        real = (PROJECT_ROOT / target).read_bytes()
        crlf_digest = hashlib.sha256(_crlf_variant(real)).hexdigest()

        def fake_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
            if path.resolve() == (PROJECT_ROOT / target).resolve():
                return crlf_digest
            return original(path, chunk_size)

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(gate, "_sha256", fake_sha256)
        try:
            result = gate.verify_sun_modality_development_data(PROJECT_ROOT)
        finally:
            monkeypatch.undo()
        assert result["ready"] is False
        assert result["artifact_hashes_ok"] is False
        assert f"artifact_hash_mismatch:{target}" in result["blockers"]

    def test_unknown_declared_hash_mode_fails_closed(self, fast_zip):
        original = gate._load_json
        target = (PROJECT_ROOT / gate.EXPERIMENT_CONTRACT_REL).resolve()

        def fake(path: Path):
            value = original(path)
            if path.resolve() == target:
                value["stage2_dataset"]["modality_dataset"]["source_manifest"][
                    "hash_mode"
                ] = "guess_from_extension"
            return value

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(gate, "_load_json", fake)
        try:
            result = gate.verify_sun_modality_development_data(PROJECT_ROOT)
        finally:
            monkeypatch.undo()
        assert result["ready"] is False
        assert (
            f"unknown_hash_mode:{gate.SOURCE_MANIFEST_REL}" in result["blockers"]
        )

    def test_unnormalizable_declared_text_fails_closed(self, fast_zip):
        _patch_read_bytes(
            monkeypatch := pytest.MonkeyPatch(),
            gate.SOURCE_MANIFEST_REL,
            lambda raw: b"\xff\xfe\x00not utf-8 at all",
        )
        try:
            result = gate.verify_sun_modality_development_data(PROJECT_ROOT)
        finally:
            monkeypatch.undo()
        assert result["ready"] is False
        assert (
            f"canonical_text_invalid:{gate.SOURCE_MANIFEST_REL}" in result["blockers"]
        )


# ---------------------------------------------------------------------------
# Provenance / license boundaries stay intact
# ---------------------------------------------------------------------------

class TestBoundariesIntact:
    def test_sun_modality_verified_but_other_gates_stay_closed(self):
        status = collect_status()
        assert status["sun_modality_development_data_verified"] is True
        assert status["sun_modality_license_status"] == "unknown_pending_confirmation"
        assert status["sun_modality_formal_use_ready"] is False
        assert status["human_review_input_ready"] is True
        assert status["human_review_freeze_ready"] is False
        assert status["formal_gold_publication_ready"] is False
        assert status["final_experiment_ready"] is False
        assert status["route"]["status"] != "locked"

    def test_gate_license_and_claim_checks_still_pass(self, fast_zip):
        result = gate.verify_sun_modality_development_data(PROJECT_ROOT)
        assert result["license_boundary_ok"] is True
        assert result["source_identity_ok"] is True
        assert result["split_ok"] is True
