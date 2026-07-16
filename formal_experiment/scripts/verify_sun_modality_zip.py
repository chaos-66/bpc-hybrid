"""S2.1-A: verify the official Sun modality ZIP byte-for-byte.

Strictly local, offline verification. The script:
  1. Confirms the file exists, is a regular file, and matches the expected
     official size + SHA-1.
  2. Opens the ZIP and runs ``ZipFile.testzip()`` to detect archive corruption.
  3. Enumerates every member and refuses any path-traversal / absolute /
     drive-letter entry (``..`` segments, leading ``/``, Windows drive
     letters, NUL bytes, etc.).
  4. Streams each member through SHA-256 (does NOT extract to disk in this
     pass; the canonical extract target ``raw/_extract/`` is also asserted
     to be currently empty so a future S2.1-B extract cannot silently
     overwrite existing bytes).
  5. Cross-checks the EStG_raw.txt SHA-256 against the value previously
     recorded in the 2026-07-11 internal research audit.
  6. Emits a machine-readable JSON report to stdout.

The script never reads .env, never calls an LLM, never modifies Gold or
readiness gates, and never copies anything into references/ or formal data
directories.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants (frozen by 2026-07-11 internal research audit + user confirmation)
# ---------------------------------------------------------------------------

EXPECTED_SIZE = 191_874_718
EXPECTED_SHA1 = "0346f84a246b7049d5aef58bcb33471435bee106"
# Canonical lowercase hex; the audit-doc value is uppercase but byte-equal.
EXPECTED_RAW_TXT_SHA256 = (
    "185385186533fcdb8156d094782e3a3976c85460312ee9d48b424f404817660f"
)

REQUIRED_MEMBERS = {"EStG_raw.txt", "EStG_sent_vec.csv", "estg.html"}

# Path-traversal safety: a member name must be a relative POSIX path that
# does not escape its parent, contain drive letters, NUL bytes, or backslashes.
_DRIVE_LETTER_RE = re.compile(r"^[A-Za-z]:[\\/]")
_FORBIDDEN_NAME_RE = re.compile(r"[\x00]")
_FORBIDDEN_SEGMENT = {".."}


def _is_safe_member_name(name: str) -> tuple[bool, str]:
    if not name:
        return False, "empty member name"
    if _FORBIDDEN_NAME_RE.search(name):
        return False, "NUL byte in member name"
    if name.startswith("/") or name.startswith("\\"):
        return False, "absolute path"
    if _DRIVE_LETTER_RE.match(name):
        return False, "drive letter in member name"
    if "\\" in name:
        return False, "backslash in member name (force POSIX separators)"
    parts = name.split("/")
    for seg in parts:
        if seg in _FORBIDDEN_SEGMENT:
            return False, f"path traversal segment '..' in {name!r}"
    return True, ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
# Main verification
# ---------------------------------------------------------------------------

def verify(zip_path: Path, extract_target: Path) -> dict:
    report: dict = {
        "zip_path": str(zip_path),
        "expected_size": EXPECTED_SIZE,
        "expected_sha1": EXPECTED_SHA1,
        "expected_raw_txt_sha256": EXPECTED_RAW_TXT_SHA256,
    }

    # 1. Existence + size.
    if not zip_path.is_file():
        report["status"] = "missing_zip"
        return report
    actual_size = zip_path.stat().st_size
    report["actual_size"] = actual_size
    report["size_match"] = actual_size == EXPECTED_SIZE
    if not report["size_match"]:
        report["status"] = "size_mismatch"
        return report

    # 2. SHA-1.
    actual_sha1 = _sha1_of(zip_path)
    report["actual_sha1"] = actual_sha1
    report["sha1_match"] = actual_sha1 == EXPECTED_SHA1
    if not report["sha1_match"]:
        report["status"] = "sha1_mismatch"
        return report

    # 3. SHA-256 (recorded for downstream provenance).
    report["actual_sha256"] = _sha256_of(zip_path)

    # 4. ZIP integrity test.
    with zipfile.ZipFile(zip_path, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            report["status"] = "zip_corruption"
            report["corrupt_member"] = bad
            return report

        members: list[zipfile.ZipInfo] = zf.infolist()
        report["member_count"] = len(members)
        report["members"] = []
        names: set[str] = set()

        for m in members:
            entry = {
                "name": m.filename,
                "size_compressed": m.compress_size,
                "size_uncompressed": m.file_size,
                "crc32": f"{m.CRC:08X}",
            }
            safe, reason = _is_safe_member_name(m.filename)
            entry["safe"] = safe
            if not safe:
                entry["unsafe_reason"] = reason
            names.add(m.filename)
            report["members"].append(entry)

        # 5. Required members.
        report["required_members"] = sorted(REQUIRED_MEMBERS)
        report["missing_required_members"] = sorted(
            REQUIRED_MEMBERS - names
        )
        if report["missing_required_members"]:
            report["status"] = "missing_required_members"
            return report

        # 6. SHA-256 of every required member (streamed, no disk write).
        member_hashes: dict[str, str] = {}
        for m in members:
            if m.filename in REQUIRED_MEMBERS:
                # Skip path-traversal rejections silently here, but the
                # member is already flagged unsafe above.
                safe, _ = _is_safe_member_name(m.filename)
                if not safe:
                    continue
                member_hashes[m.filename] = _sha256_stream(zf, m)
        report["required_member_sha256"] = member_hashes

        # 7. EStG_raw.txt cross-check.
        raw_sha = member_hashes.get("EStG_raw.txt", "")
        report["estg_raw_txt_sha256_match"] = raw_sha == EXPECTED_RAW_TXT_SHA256
        if not report["estg_raw_txt_sha256_match"]:
            report["status"] = "estg_raw_txt_sha256_mismatch"
            return report

    # 8. Extract target safety (no silent overwrite).
    if extract_target.exists():
        if any(extract_target.iterdir()):
            report["status"] = "extract_target_not_empty"
            report["extract_target"] = str(extract_target)
            return report
    report["extract_target"] = str(extract_target)
    report["extract_target_empty_or_absent"] = True

    report["status"] = "verified"
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zip",
        type=Path,
        default=Path("formal_experiment/data/development/sun_modality/raw/Decision_Logic_data.zip"),
        help="path to the official Decision_Logic_data.zip",
    )
    parser.add_argument(
        "--extract-target",
        type=Path,
        default=Path("formal_experiment/data/development/sun_modality/raw/_extract"),
        help="reserved extract target (must be empty / absent for S2.1-B)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="optional path to also write the JSON report",
    )
    args = parser.parse_args()

    report = verify(args.zip, args.extract_target)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")

    if report.get("status") == "verified":
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
