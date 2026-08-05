"""Restore the user's completed Layer E adjudication from the 56d2b03
historical snapshot into the active v2 human_correction file.

Background (2026-08-06, user-authorized data restoration):
    The user completed the full 150-record Layer E adjudication on
    2026-07-18 (review_state=adjudicated, reviewer=user).  When the v2
    five-layer workflow was introduced (commit bfb0b8a), the active editing
    file was rebuilt as an empty surface and the adjudicated content was NOT
    migrated; it survived only in the 56d2b03 historical blob.  The audit
    gate 2 (freeze_ready) therefore reads 0/150 on the active file.

    This script restores the USER-ENTERED fields only:
      approved_text_en, approved_text_en_history, approved_text_en_sha256,
      decisions, human_correction, review_state
    from the 56d2b03 snapshot into the active file, matched by sample_id.
    Non-user fields of the active file are preserved verbatim:
      llm_candidate (immutable Layer C copy), candidate_text_en*,
      raw_text_de*, legacy_record_id, source_refs.

Safeguards:
    * the active file is backed up (no-overwrite) before any change;
    * the historical blob is read read-only via ``git show`` raw bytes;
    * the merge is staged and validated with the same
      ``estg150_validator.validate_global`` used by the audit gate;
      any record-level problem or a non-passing validation result aborts
      before the active file is touched;
    * the active file is replaced atomically (staging rename) only after
      format_valid AND freeze_ready pass on the staged file.

No LLM/API call, no Gold bytes fabricated, no network.  The restored
content is the user's own previously entered adjudication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.estg150_validator import validate_global  # noqa: E402

SOURCE_COMMIT = "56d2b03"
HISTORICAL_REL_PATH = (
    "formal_experiment/data/development/human_review/estg_150_human_correction_v1.json"
)
DEFAULT_TARGET = (
    ROOT / "data" / "development" / "human_review" / "estg_150_human_correction_v1.json"
)
DEFAULT_BACKUP_DIR = ROOT / "outputs" / "development" / "human_review" / "review_backups"
DEFAULT_REPORT_PATH = (
    ROOT
    / "outputs"
    / "development"
    / "human_review"
    / "restore_layer_e_56d2b03_20260806.manifest.json"
)

USER_FIELDS = (
    "approved_text_en",
    "approved_text_en_history",
    "approved_text_en_sha256",
    "decisions",
    "human_correction",
    "review_state",
)


class RestoreError(ValueError):
    """Raised when the Layer E restoration cannot proceed safely."""


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=_git_root(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


_GIT_ROOT: Path | None = None


def _git_root() -> Path:
    global _GIT_ROOT
    if _GIT_ROOT is None:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        _GIT_ROOT = Path(completed.stdout.decode("utf-8").strip())
    return _GIT_ROOT


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json_file(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RestoreError(f"{label} is not loadable JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise RestoreError(f"{label} must be a JSON object")
    return value


def records_of(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = document.get("records")
    if not isinstance(records, list):
        raise RestoreError("document has no 'records' array")
    return records


def merge_layer_e_record(
    current: Mapping[str, Any], historical: Mapping[str, Any]
) -> dict[str, Any]:
    """Return a new record dict: historical user fields + current rest.

    Raises RestoreError when a user field is missing from the historical
    record or when sample_ids disagree.
    """
    if current.get("sample_id") != historical.get("sample_id"):
        raise RestoreError(
            f"sample_id mismatch: {current.get('sample_id')!r} vs "
            f"{historical.get('sample_id')!r}"
        )
    merged = dict(current)
    for field in USER_FIELDS:
        if field not in historical:
            raise RestoreError(
                f"{current.get('sample_id')}: historical record lacks {field!r}"
            )
        merged[field] = historical[field]
    return merged


def run(
    target_path: Path,
    backup_dir: Path,
    report_path: Path,
    source_commit: str,
) -> int:
    target_path = target_path.resolve()
    backup_dir = backup_dir.resolve()
    report_path = report_path.resolve()
    if not target_path.exists():
        raise RestoreError(f"active file not found: {target_path}")
    if report_path.exists():
        raise RestoreError(f"refusing to overwrite report: {report_path}")

    commit_sha = _git("rev-parse", source_commit).stdout.decode("ascii").strip()
    blob_oid_line = _git("ls-tree", source_commit, "--", HISTORICAL_REL_PATH).stdout
    blob_bytes = _git("show", f"{source_commit}:{HISTORICAL_REL_PATH}").stdout
    if not blob_oid_line.strip():
        raise RestoreError(f"{HISTORICAL_REL_PATH} not present in {source_commit}")
    historical_doc = json.loads(blob_bytes.decode("utf-8"))
    historical = records_of(historical_doc)
    if len(historical) != 150:
        raise RestoreError(f"historical records = {len(historical)}, expected 150")

    current_doc = load_json_file(target_path, label="active file")
    current = records_of(current_doc)
    if len(current) != 150:
        raise RestoreError(f"active records = {len(current)}, expected 150")
    current_by_id = {r["sample_id"]: r for r in current}
    if len(current_by_id) != 150:
        raise RestoreError("active sample_ids are not unique")
    hist_by_id = {r["sample_id"]: r for r in historical}
    if set(current_by_id) != set(hist_by_id):
        raise RestoreError("active and historical sample_id sets differ")

    staged_records: list[dict[str, Any]] = []
    for sample_id in sorted(current_by_id):
        staged_records.append(
            merge_layer_e_record(current_by_id[sample_id], hist_by_id[sample_id])
        )
    staged_doc = dict(current_doc)
    staged_doc["records"] = staged_records

    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_name = f"estg_150_human_correction_v1.pre_restore_56d2b03_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    backup_path = backup_dir / backup_name
    if backup_path.exists():
        raise RestoreError(f"backup already exists: {backup_path}")
    shutil.copy2(target_path, backup_path)

    staging = target_path.parent / f".{target_path.name}.staging-{os.getpid()}"
    if staging.exists():
        raise RestoreError(f"staging path already exists: {staging}")
    try:
        with staging.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(staged_doc, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        validation = validate_global(staging)
        if not validation.get("format_valid"):
            raise RestoreError(
                f"staged file not format-valid: {validation.get('format_errors', [])[:5]}"
            )
        if not validation.get("freeze_ready"):
            raise RestoreError(
                f"staged file not freeze-ready: {validation.get('freeze_blockers', [])[:5]}"
            )
        staging.replace(target_path)
    except Exception:
        staging.unlink(missing_ok=True)
        raise

    report = {
        "schema_version": "estg150_layer_e_restore_manifest@1.0.0",
        "purpose": (
            "restore the user's completed 2026-07-18 Layer E adjudication from "
            f"{source_commit} into the active v2 file (user-authorized 2026-08-06)"
        ),
        "source_commit": commit_sha,
        "source_blob_path": HISTORICAL_REL_PATH,
        "source_blob_sha256": sha256_bytes(blob_bytes),
        "user_fields_restored": list(USER_FIELDS),
        "fields_preserved_from_active": [
            "llm_candidate",
            "candidate_text_en",
            "candidate_text_en_sha256",
            "raw_text_de",
            "raw_text_de_sha256",
            "legacy_record_id",
            "source_refs",
        ],
        "records": {
            "active_before": len(current),
            "historical": len(historical),
            "merged": len(staged_records),
            "sample_id_sets_match": True,
        },
        "backup": {
            "path": str(backup_path),
            "sha256": sha256_file(backup_path),
        },
        "validation": {
            "format_valid": validation.get("format_valid"),
            "review_ready": validation.get("review_ready"),
            "freeze_ready": validation.get("freeze_ready"),
            "n_approved_en": validation.get("n_approved_en"),
            "n_field_decisions_resolved": validation.get("n_field_decisions_resolved"),
            "n_field_decisions_total": validation.get("n_field_decisions_total"),
            "review_state_counts": validation.get("review_state_counts"),
        },
        "target": {
            "path": str(target_path),
            "sha256": sha256_file(target_path),
        },
        "safety": {
            "gold": "restored_user_entered_adjudication",
            "llm_api": "not_called",
            "network": "not_called",
            "backup_created": True,
            "atomic_replace": True,
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "target": str(target_path),
                "merged": len(staged_records),
                "format_valid": validation.get("format_valid"),
                "freeze_ready": validation.get("freeze_ready"),
                "review_state_counts": validation.get("review_state_counts"),
                "backup": str(backup_path),
                "report": str(report_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--source-commit", default=SOURCE_COMMIT)
    args = parser.parse_args()
    try:
        return run(args.target, args.backup_dir, args.report, args.source_commit)
    except (RestoreError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"Layer E restore failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
