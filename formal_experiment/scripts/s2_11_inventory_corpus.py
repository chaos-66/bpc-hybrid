# -*- coding: utf-8 -*-
"""Deterministic S2.11 corpus INVENTORY (Checkpoint B, local read-only).

Reads ONLY the explicit Barrientos artifact requirement files (membership
list below), verifies their raw bytes, and emits a HASH-ONLY membership
manifest:
  outputs/reports/s2_11_corpus_membership_v1.json

The manifest contains file paths, raw-byte SHA-256, byte sizes, record IDs
and per-record TEXT SHA-256 — NEVER the raw third-party text (the artifact
license is unknown; local read-only non-redistributive use only).

Quarantine is record-level and never blocks the usable records: each
invalid record is listed with a stable error code.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

MEMBERSHIP_FILE_RELS = (
    "references/barrientos_2026/artifact_input/requirements/"
    "blood_donation_scenario/blood_donation_scenario.json",
    "references/barrientos_2026/artifact_input/requirements/"
    "emergencies_scenario/emergencies_scenario.json",
    "references/barrientos_2026/artifact_input/requirements/"
    "SIM_card_scenario/SIM_card_scenario.json",
)

OUT_REL = "outputs/reports/s2_11_corpus_membership_v1.json"

# Stable record-level error codes (quarantine).
ERR_UNREADABLE_FILE = "QUARANTINE_FILE_UNREADABLE"
ERR_BAD_RECORD_STRUCTURE = "QUARANTINE_BAD_RECORD_STRUCTURE"
ERR_DUPLICATE_RECORD_ID = "QUARANTINE_DUPLICATE_RECORD_ID"
ERR_EMPTY_TEXT = "QUARANTINE_EMPTY_TEXT"


class BuilderFail(Exception):
    """Fail-closed build abort."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _write(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() == data:
            return
        raise BuilderFail(
            f"refusing to overwrite different existing content: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def inventory() -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    records: dict[str, dict[str, Any]] = {}
    quarantine: list[dict[str, Any]] = []
    total_records = 0
    for rel in MEMBERSHIP_FILE_RELS:
        p = ROOT.parent / rel
        if not p.is_file():
            raise BuilderFail(f"fail-closed: membership file missing: {rel}")
        file_sha = _sha256_file(p)
        size = p.stat().st_size
        scenario = rel.split("/")[-2]
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            quarantine.append({"record_id": f"{scenario}/<file>",
                               "path": rel, "file_sha256": file_sha,
                               "code": ERR_UNREADABLE_FILE,
                               "detail": str(exc)[:120]})
            continue
        if not isinstance(doc, list):
            quarantine.append({"record_id": f"{scenario}/<file>",
                               "path": rel, "file_sha256": file_sha,
                               "code": ERR_BAD_RECORD_STRUCTURE,
                               "detail": "top-level JSON is not a list"})
            continue
        file_records: list[str] = []
        for idx, entry in enumerate(doc):
            if not isinstance(entry, dict) or not isinstance(
                    entry.get("ID"), str) or not isinstance(
                    entry.get("version"), int):
                quarantine.append({
                    "record_id": f"{scenario}/<row{idx}>",
                    "path": rel, "file_sha256": file_sha,
                    "code": ERR_BAD_RECORD_STRUCTURE,
                    "detail": f"row {idx} lacks ID/version"})
                continue
            record_id = f"{scenario}/{entry['ID']}/v{entry['version']}"
            total_records += 1
            if record_id in records:
                quarantine.append({"record_id": record_id, "path": rel,
                                   "file_sha256": file_sha,
                                   "code": ERR_DUPLICATE_RECORD_ID,
                                   "detail": "duplicate ID+version"})
                continue
            text = entry.get("text")
            text_ok = isinstance(text, str) and text.strip() and \
                text.strip() != "-"
            if not text_ok:
                quarantine.append({"record_id": record_id, "path": rel,
                                   "file_sha256": file_sha,
                                   "code": ERR_EMPTY_TEXT,
                                   "detail": "empty or placeholder text"})
                continue
            text_bytes = text.encode("utf-8")
            records[record_id] = {
                "path": rel,
                "file_sha256": file_sha,
                "text_sha256": _sha256_bytes(text_bytes),
                "text_byte_size": len(text_bytes),
            }
            file_records.append(record_id)
        files.append({
            "path": rel,
            "scenario": scenario,
            "sha256": file_sha,
            "byte_size": size,
            "record_count": len(file_records),
            "record_ids": file_records,
        })
    payload = {
        "schema_version": "s2_11_corpus_membership@1.0.0",
        "membership_id": "s2-11-barrientos-requirements-v1",
        "read_discipline": (
            "formal runs read ONLY these files, each verified by "
            "raw-byte SHA-256; the artifact license is unknown and raw "
            "third-party text is NEVER copied into committed assets"),
        "files": files,
        "records": records,
        "record_count": total_records,
        "quarantine": quarantine,
        "language": "en",
        "language_note": "declared English (artifact requirement texts)",
    }
    payload["manifest_sha256"] = _sha256_bytes(
        json.dumps({k: payload[k] for k in (
            "schema_version", "membership_id", "files", "records",
            "record_count", "quarantine", "language")},
            sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return payload


def main() -> int:
    try:
        doc = inventory()
        data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n") \
            .encode("utf-8")
        _write(ROOT / OUT_REL, data)
    except BuilderFail as exc:
        print(f"BUILD FAILED (fail-closed): {exc}", file=sys.stderr)
        return 2
    print(f"corpus membership written: {OUT_REL} "
          f"({doc['record_count']} records, "
          f"{len(doc['quarantine'])} quarantined)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
