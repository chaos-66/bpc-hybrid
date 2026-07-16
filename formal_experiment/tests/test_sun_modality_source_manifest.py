"""S2.1-A: tests for the Sun modality source manifest + byte-level verification.

These are read-only / structural tests. They verify that:

1. The machine-readable source manifest is present, parses as JSON, and
   declares the expected provenance fields.
2. The official ZIP at data/development/sun_modality/raw/ matches the
   archive.org metadata (size + SHA-1) byte-for-byte.
3. All three required members (EStG_raw.txt, EStG_sent_vec.csv, estg.html)
   are present in the ZIP, with safe member names, and the EStG_raw.txt
   SHA-256 matches the value previously recorded in the 2026-07-11
   internal research audit.
4. License status is recorded honestly as `unknown_pending_confirmation`
   and the user authorization scope is preserved.
5. The "forbidden paths" of AGENTS.md (references/, data/{input,gold,
   predictions,results}/, outputs/, _retired/) are not polluted by the
   S2.1-A source work.
6. A directory-level .gitignore inside raw/ exists and the root .gitignore
   has matching belt-and-suspenders entries.
7. The byte-level verification script runs cleanly and returns the
   expected JSON report.

The tests intentionally do NOT:
- read or print .env;
- call any LLM / API;
- mutate Gold, the human-review files, the route status, or any
  readiness / locked gates.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST_PATH = _PROJECT_ROOT / "data" / "development" / "sun_modality" / "source_manifest.json"
_RAW_DIR = _PROJECT_ROOT / "data" / "development" / "sun_modality" / "raw"
_ZIP_PATH = _RAW_DIR / "Decision_Logic_data.zip"
_RAW_GITIGNORE = _RAW_DIR / ".gitignore"
_ROOT_GITIGNORE = _PROJECT_ROOT.parent / ".gitignore"
_INGESTION_DOC = _PROJECT_ROOT / "docs" / "research" / "SUN_MODALITY_DATASET_INGESTION.md"
_VERIFY_SCRIPT = _PROJECT_ROOT / "scripts" / "verify_sun_modality_zip.py"

# Frozen official / audit-recorded values.
EXPECTED_SIZE = 191_874_718
EXPECTED_SHA1 = "0346f84a246b7049d5aef58bcb33471435bee106"
EXPECTED_ZIP_SHA256 = "ada231f092927813ba9f1cd32a44a3d30d96b57fc463d042dfd76c652b6d58f2"
EXPECTED_RAW_TXT_SHA256 = "185385186533fcdb8156d094782e3a3976c85460312ee9d48b424f404817660f"
REQUIRED_MEMBERS = ("EStG_raw.txt", "EStG_sent_vec.csv", "estg.html")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_manifest() -> dict:
    assert _MANIFEST_PATH.is_file(), (
        f"missing S2.1-A source manifest: {_MANIFEST_PATH}"
    )
    with _MANIFEST_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _sha1_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def _sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def _sha256_stream(zf: zipfile.ZipFile, member: zipfile.ZipInfo) -> str:
    h = hashlib.sha256()
    with zf.open(member, "r") as f:
        while True:
            buf = f.read(1 << 20)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Manifest structural tests
# ---------------------------------------------------------------------------

class TestManifestShape:
    """The manifest must declare the expected top-level provenance keys."""

    def test_manifest_parses(self):
        manifest = _load_manifest()
        assert isinstance(manifest, dict)

    def test_manifest_version_pinned(self):
        manifest = _load_manifest()
        assert "manifest_version" in manifest
        assert manifest["manifest_version"].startswith(
            "sun_modality_source_manifest@"
        )

    def test_task_id_declared(self):
        manifest = _load_manifest()
        assert manifest.get("task_id") == "S2.1-A"

    def test_official_landing_page_recorded(self):
        manifest = _load_manifest()
        landing = manifest.get("official_landing_page", {})
        assert landing.get("url") == "https://archive.org/details/input-2"
        assert landing.get("archive_org_metadata_url") == "https://archive.org/metadata/input-2"
        assert "verification_basis" in landing

    def test_archive_org_metadata_recorded(self):
        manifest = _load_manifest()
        meta = manifest["official_landing_page"][
            "archive_org_metadata_user_supplied_2026_07_15"
        ]
        assert meta["identifier"] == "input-2"
        assert meta["filename"] == "Decision_Logic_data.zip"
        assert meta["expected_size"] == EXPECTED_SIZE
        assert meta["expected_sha1"] == EXPECTED_SHA1
        assert meta["licenseurl"] is None
        assert meta["rights"] is None

    def test_primary_modality_asset_block_present(self):
        manifest = _load_manifest()
        asset = manifest.get("primary_modality_asset", {})
        assert asset.get("logical_name") == "Decision_Logic_data.zip"
        for member in REQUIRED_MEMBERS:
            assert member in asset.get("expected_top_level_members", [])

    def test_official_hashes_recorded(self):
        manifest = _load_manifest()
        asset = manifest["primary_modality_asset"]
        # SHA-1 must be a 40-char lowercase hex.
        sha1 = asset["official_sha1"]
        assert len(sha1) == 40
        int(sha1, 16)  # raises if non-hex

        # EStG_raw.txt SHA-256 must be a 64-char hex (case-insensitive).
        raw_sha = asset["official_member_sha256_known"]["EStG_raw.txt"]
        assert len(raw_sha) == 64
        int(raw_sha, 16)

    def test_expected_class_distribution(self):
        manifest = _load_manifest()
        dist = manifest["primary_modality_asset"]["expected_class_distribution"]
        total = sum(dist[k] for k in ("definition", "obligation", "permission", "prohibition"))
        assert total == 2833, f"Michel et al. 2022 total must be 2833, got {total}"


# ---------------------------------------------------------------------------
# Local state tests
# ---------------------------------------------------------------------------

class TestLocalState:
    """raw/ must hold the official ZIP plus a directory-level .gitignore,
    and no other dev paths may contain official bytes."""

    def test_raw_dir_exists(self):
        assert _RAW_DIR.is_dir(), f"raw/ directory not created: {_RAW_DIR}"

    def test_official_zip_is_in_raw(self):
        assert _ZIP_PATH.is_file(), f"official ZIP missing: {_ZIP_PATH}"

    def test_raw_dir_contains_only_zip_and_gitignore(self):
        contents = sorted(p.name for p in _RAW_DIR.iterdir())
        assert contents == [".gitignore", "Decision_Logic_data.zip"], (
            "raw/ must contain only the official ZIP and the directory-level "
            f".gitignore; found: {contents}"
        )

    def test_official_zip_size_matches_archive_org(self):
        assert _ZIP_PATH.stat().st_size == EXPECTED_SIZE, (
            f"ZIP size { _ZIP_PATH.stat().st_size } != expected { EXPECTED_SIZE }"
        )

    def test_official_zip_sha1_matches_archive_org(self):
        sha1 = _sha1_of(_ZIP_PATH)
        assert sha1 == EXPECTED_SHA1, (
            f"ZIP SHA-1 {sha1} != expected {EXPECTED_SHA1}"
        )

    def test_official_zip_sha256_recorded_matches_local(self):
        sha256 = _sha256_of(_ZIP_PATH)
        manifest = _load_manifest()
        recorded = manifest["primary_modality_asset"][
            "local_computed_hashes_2026_07_15"
        ]["Decision_Logic_data.zip_sha256"]
        assert sha256 == EXPECTED_ZIP_SHA256, (
            f"locally computed ZIP SHA-256 {sha256} drifted from recorded "
            f"value {EXPECTED_ZIP_SHA256}"
        )
        assert sha256 == recorded, (
            f"manifest recorded value {recorded} drifted from current local "
            f"value {sha256}"
        )

    @pytest.mark.parametrize(
        "forbidden_path",
        [
            "data/input/Decision_Logic_data.zip",
            "data/gold/Decision_Logic_data.zip",
            "data/predictions/Decision_Logic_data.zip",
            "data/results/Decision_Logic_data.zip",
            "outputs/Decision_Logic_data.zip",
            "outputs/EStG_sent_vec.csv",
        ],
    )
    def test_no_official_bytes_in_formal_or_outputs(self, forbidden_path):
        path = _PROJECT_ROOT / forbidden_path
        assert not path.exists(), (
            f"Official bytes MUST NOT live in formal/references/outputs: {path}"
        )

    def test_local_state_records_acquired_and_byte_match(self):
        manifest = _load_manifest()
        state = manifest["primary_modality_asset"]["local_state_2026_07_15"]
        assert state.get("acquired") is True
        assert state.get("verified_byte_match") is True
        assert state.get("size_match") is True
        assert state.get("sha1_match") is True
        assert state.get("zip_integrity_testzip_clean") is True


# ---------------------------------------------------------------------------
# ZIP member tests
# ---------------------------------------------------------------------------

class TestZipMembers:
    """The ZIP must contain exactly the three expected members, all with
    safe POSIX-style relative names."""

    def test_zip_has_exactly_three_members(self):
        with zipfile.ZipFile(_ZIP_PATH, "r") as zf:
            names = zf.namelist()
        assert sorted(names) == sorted(REQUIRED_MEMBERS), (
            f"expected exactly {sorted(REQUIRED_MEMBERS)} in ZIP, got {sorted(names)}"
        )

    def test_zip_passes_testzip(self):
        with zipfile.ZipFile(_ZIP_PATH, "r") as zf:
            bad = zf.testzip()
        assert bad is None, f"ZIP testzip reported corruption in: {bad}"

    @pytest.mark.parametrize("name", REQUIRED_MEMBERS)
    def test_member_name_safe(self, name):
        # No backslashes, NUL, drive letters, absolute paths, or '..' segments.
        assert "\\" not in name, f"backslash in member name: {name!r}"
        assert "\x00" not in name, f"NUL byte in member name: {name!r}"
        assert not name.startswith("/"), f"absolute path: {name!r}"
        assert not re.match(r"^[A-Za-z]:", name), f"drive letter: {name!r}"
        for seg in name.split("/"):
            assert seg != "..", f"path traversal in: {name!r}"

    def test_estg_raw_txt_sha256_matches_audit(self):
        with zipfile.ZipFile(_ZIP_PATH, "r") as zf:
            sha = _sha256_stream(zf, "EStG_raw.txt")
        assert sha == EXPECTED_RAW_TXT_SHA256, (
            f"EStG_raw.txt SHA-256 {sha} != audit-recorded "
            f"{EXPECTED_RAW_TXT_SHA256}"
        )

    def test_local_computed_hashes_recorded_in_manifest(self):
        # Re-compute and confirm the manifest holds the same values.
        with zipfile.ZipFile(_ZIP_PATH, "r") as zf:
            csv_sha = _sha256_stream(zf, "EStG_sent_vec.csv")
            html_sha = _sha256_stream(zf, "estg.html")
            raw_sha = _sha256_stream(zf, "EStG_raw.txt")
        manifest = _load_manifest()
        recorded = manifest["primary_modality_asset"][
            "local_computed_hashes_2026_07_15"
        ]
        assert recorded["EStG_raw.txt_sha256"] == raw_sha
        assert recorded["EStG_sent_vec.csv_sha256"] == csv_sha
        assert recorded["estg.html_sha256"] == html_sha
        assert recorded["EStG_sent_vec.csv_size_uncompressed"] == 470_740_514


# ---------------------------------------------------------------------------
# License / rights tests
# ---------------------------------------------------------------------------

class TestLicenseHonesty:
    """License MUST remain `unknown_pending_confirmation` until a user/mentor
    files the archive.org rights statement. The local-use authorization
    scope MUST be recorded."""

    def test_decision_logic_license_unknown_pending(self):
        manifest = _load_manifest()
        lic = manifest["primary_modality_asset"]["license"]
        assert lic.get("rights_status") == "unknown_pending_confirmation"
        assert "rights_status_reason" in lic

    def test_stage3_supplement_license_unknown_pending(self):
        manifest = _load_manifest()
        lic = manifest["stage3_supplement_asset"]["license"]
        assert lic.get("rights_status") == "unknown_pending_confirmation"

    def test_local_use_authorization_recorded(self):
        manifest = _load_manifest()
        auth = manifest["primary_modality_asset"]["license"][
            "local_use_authorization_2026_07_15"
        ]
        assert auth["granted_by"] == "user (task prompt on 2026-07-15)"
        # The forbidden actions must include "no re-distribution" + "no LLM".
        joined = " | ".join(auth["forbidden_actions"]).lower()
        assert "重新发布" in joined or "re-publish" in joined or "redistribut" in joined or "upload" in joined or "releas" in joined
        assert "llm" in joined or "api" in joined


# ---------------------------------------------------------------------------
# .gitignore protection tests
# ---------------------------------------------------------------------------

class TestGitignorePolicy:
    """raw/ MUST be protected from accidental Git commits by both a
    directory-level ignore and a root-level belt-and-suspenders rule."""

    def test_raw_dir_gitignore_exists(self):
        assert _RAW_GITIGNORE.is_file(), (
            f"missing directory-level .gitignore in raw/: {_RAW_GITIGNORE}"
        )

    def test_raw_dir_gitignore_ignores_everything(self):
        text = _RAW_GITIGNORE.read_text(encoding="utf-8")
        assert "*" in text, "directory-level .gitignore must include '*'"
        assert "!.gitignore" in text, (
            "directory-level .gitignore must whitelist .gitignore itself"
        )

    def test_root_gitignore_mentions_raw_dir(self):
        text = _ROOT_GITIGNORE.read_text(encoding="utf-8")
        assert "sun_modality/raw" in text, (
            "root .gitignore must mention data/development/sun_modality/raw"
        )

    def test_root_gitignore_mentions_extract_target(self):
        text = _ROOT_GITIGNORE.read_text(encoding="utf-8")
        assert "_extract" in text, (
            "root .gitignore must mention the reserved _extract/ target"
        )


# ---------------------------------------------------------------------------
# S2.1-A completion / S2.1-B unblock guard
# ---------------------------------------------------------------------------

class TestCompletionGuard:
    """S2.1-A is verified; B1 (raw bytes) is resolved; B2 (license) is
    still open."""

    def test_s2_1_a_marked_verified(self):
        manifest = _load_manifest()
        check = manifest["s2_1_a_definition_of_done_check_2026_07_15"]
        assert check["s2_1_a_completed"] is True
        assert check["s2_1_a_completed_reason"]

    def test_b1_resolved_b2_open(self):
        manifest = _load_manifest()
        blockers = {b["id"]: b for b in manifest["blockers_2026_07_15"]}
        assert blockers["B1"]["status"] == "resolved"
        assert blockers["B2"]["status"] == "open"
        assert blockers["B3"]["status"] == "open"

    def test_status_field_reflects_byte_match(self):
        manifest = _load_manifest()
        assert manifest["status"] == "manifest_verified_and_assets_byte_matched"


# ---------------------------------------------------------------------------
# Ingestion doc cross-check
# ---------------------------------------------------------------------------

class TestIngestionDocCrossCheck:
    """The human-readable ingestion doc MUST exist and align with the manifest."""

    def test_ingestion_doc_present(self):
        assert _INGESTION_DOC.is_file(), (
            f"missing ingestion doc: {_INGESTION_DOC}"
        )

    def test_ingestion_doc_mentions_key_strings(self):
        text = _INGESTION_DOC.read_text(encoding="utf-8")
        for needle in [
            "S2.1-A",
            "Decision_Logic_data.zip",
            "EStG_sent_vec.csv",
            "unknown_pending_confirmation",
            "0346f84a246b7049d5aef58bcb33471435bee106",
            "data/development/sun_modality/raw/",
            "191874718",
            "185385186533FCDB8156D094782E3A3976C85460312EE9D48B424F404817660F",
            "1e53eb1b7f88f57c63029385eafe5e6f269bb7878328c0c409c5e708250ad5c3",
            "bc385ce9acee1fd9289d5c0dc9c273bf0c7392e11783b6043032066c7ce80eb0",
        ]:
            assert needle in text, f"ingestion doc missing string: {needle!r}"

    def test_ingestion_doc_marks_verified(self):
        text = _INGESTION_DOC.read_text(encoding="utf-8")
        assert "verified" in text.lower(), (
            "ingestion doc must reflect S2.1-A verified state"
        )


# ---------------------------------------------------------------------------
# Byte-level verification script smoke
# ---------------------------------------------------------------------------

class TestVerifyScript:
    """The verify_sun_modality_zip.py script must run cleanly and return
    a JSON report with status=='verified'."""

    def test_verify_script_present(self):
        assert _VERIFY_SCRIPT.is_file(), (
            f"missing verify script: {_VERIFY_SCRIPT}"
        )

    def test_verify_script_runs_clean(self):
        completed = subprocess.run(
            [sys.executable, str(_VERIFY_SCRIPT), "--zip", str(_ZIP_PATH)],
            cwd=_PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        assert completed.returncode == 0, (
            f"verify_sun_modality_zip.py exited {completed.returncode}:\n"
            f"{completed.stdout}"
        )
        report = json.loads(completed.stdout)
        assert report["status"] == "verified"
        assert report["size_match"] is True
        assert report["sha1_match"] is True
        assert report["estg_raw_txt_sha256_match"] is True
        assert report["required_member_sha256"]["EStG_raw.txt"] == EXPECTED_RAW_TXT_SHA256


# ---------------------------------------------------------------------------
# Sanity: do not read .env
# ---------------------------------------------------------------------------

class TestNoEnvLeakage:
    """The manifest must not embed secret-shaped tokens."""

    def test_manifest_does_not_embed_env_values(self):
        manifest_text = _MANIFEST_PATH.read_text(encoding="utf-8")
        for token in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "sk-", "API_KEY="):
            assert token not in manifest_text, (
                f"manifest appears to embed a secret-shaped token: {token!r}"
            )
