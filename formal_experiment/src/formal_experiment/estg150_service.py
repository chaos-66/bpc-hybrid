"""Service layer for the EStG-150 v2 human_correction workflow (Layer E).

This module is the **single source of truth** for any data mutation on
the human_correction file. The Tk GUI in
`scripts/estg150_review_tool.py` is a thin shell that calls into this
service; the offline tests in
`tests/test_estg_150_review_tool.py` call the service directly.

The service enforces the workflow invariants:

  1. Validation never writes to the production file. The pure
     `validate_record_for_review(record, ctx)` function is the **only**
     eligibility check used by `mark_reviewed` and `mark_adjudicated`.
     It only looks at the current record. The first record can be
     marked `reviewed` while the other 149 are still `needs_review`.

  2. `save_draft()` is the single point that touches the disk. It
     (a) creates a uniquely-named backup of the on-disk file,
     (b) atomically writes the in-memory doc,
     (c) returns the backup path. Validation of the saved file is a
     separate explicit call to `validate_global()` so the caller can
     show the result in the status bar.

  3. Every mutator method (accept / edit / reject / mark) pushes a
     snapshot of the affected record onto an in-memory undo stack
     (max 50) and appends to the action log. The GUI's
     "撤销最近一次操作" button calls `undo()` and then `save_draft()`.

  4. Backups use UTC microsecond timestamps **plus** a monotonic
     counter, so two `save_draft()` calls in the same second still
     produce two different backup filenames.

  5. `mark_reviewed` / `mark_adjudicated` use the per-record
     eligibility check, NOT the global `review_ready` /
     `freeze_ready`. The global aggregator is only used for the
     status-bar report and for the audit.
"""
from __future__ import annotations

import copy
import datetime
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional

from formal_experiment.estg150_validator import (
    DECISION_OK_FOR_REVIEW,
    DECISION_OK_FOR_FREEZE,
    SPAN_FIELDS,
    _resolve_hashes_path,
    sha256_text,
    validate_doc_dict,
    validate_global,
    validate_record_for_review,
    validate_record_format,
)


# ---------------------------------------------------------------------------
# Time + backup naming
# ---------------------------------------------------------------------------

def now_utc_iso() -> str:
    """UTC ISO-8601 timestamp with microsecond precision, 'Z' suffix."""
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


# Per-backup-dir monotonic counter so two saves in the same microsecond
# still produce two different backup filenames. This is module-level
# state; tests use unique backup dirs to keep their own counters.
_BACKUP_COUNTERS: dict[str, int] = {}


def next_backup_path(backup_dir: Path, stem: str) -> Path:
    """Generate a unique backup filename.

    Format: ``{stem}_{YYYYMMDDTHHMMSSffffffZ}_n{counter:04d}.json``

    The counter is keyed by `backup_dir` (resolved as a string) so two
    different workspaces never collide. A monotonic integer is
    appended so two saves in the same microsecond still produce two
    different filenames.
    """
    key = str(Path(backup_dir).resolve())
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    n = _BACKUP_COUNTERS.get(key, 0) + 1
    _BACKUP_COUNTERS[key] = n
    return Path(backup_dir) / f"{stem}_{ts}_n{n:04d}.json"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class HumanCorrectionService:
    """Service-layer wrapper for editing the EStG-150 human_correction file.

    Parameters
    ----------
    path:
        Path to the JSON file (Layer E, only file the user edits).
    backup_dir:
        Directory where pre-save backups are written. Created on first
        backup. Counter is keyed on this path.
    action_log:
        Append-only JSONL action log path. Created on first write.
    reviewer:
        Reviewer identifier written into each action log entry.
    max_undo:
        Maximum number of per-record undo snapshots kept in memory.
    """

    def __init__(
        self,
        path: Path,
        backup_dir: Path,
        action_log: Path,
        reviewer: str = "user",
        max_undo: int = 50,
    ):
        self.path = Path(path)
        self.backup_dir = Path(backup_dir)
        self.action_log = Path(action_log)
        self.reviewer = reviewer
        self.max_undo = max_undo
        self._doc: Optional[dict] = None
        self._undo_stack: list[dict] = []
        self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        self._doc = json.loads(self.path.read_text(encoding="utf-8"))
        self._undo_stack.clear()

    def reload(self) -> None:
        self._load()

    @property
    def doc(self) -> dict:
        if self._doc is None:
            raise RuntimeError("service not loaded")
        return self._doc

    @property
    def records(self) -> list:
        return self.doc["records"]

    def get_record(self, sample_id: str) -> Optional[dict]:
        for r in self.records:
            if isinstance(r, dict) and r.get("sample_id") == sample_id:
                return r
        return None

    def get_record_by_index(self, idx: int) -> dict:
        return self.records[idx]

    # ------------------------------------------------------------------
    # Save / backup
    # ------------------------------------------------------------------
    def _atomic_write(self, doc: dict) -> None:
        # Per-process unique tmp file in the same directory so Windows
        # rename is atomic on the same volume.
        suffix = self.path.suffix or ".json"
        tmp = self.path.with_suffix(
            suffix + f".{uuid.uuid4().hex[:8]}.tmp"
        )
        tmp.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        shutil.move(str(tmp), str(self.path))

    def create_backup(self) -> Path:
        """Backup the on-disk file to a uniquely-named file. Returns the
        backup path. Raises FileNotFoundError if the production file
        is missing."""
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        target = next_backup_path(self.backup_dir, self.path.stem)
        # write-then-rename so we never leave a half-written backup
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(
            self.path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        shutil.move(str(tmp), str(target))
        return target

    def save_draft(self) -> dict:
        """The single on-disk write point. Backs up the current
        on-disk file (if any), then atomically writes the in-memory
        doc to the production path. Returns ``{saved, backup, path,
        validation}``.

        The on-disk file is **never** overwritten without a backup
        first. Validation runs against the in-memory doc using the
        pure-Python ``validate_doc_dict`` validator BEFORE any
        disk write, so the production file is never replaced by an
        invalid state. An incomplete or format-invalid draft can
        still be saved — the validation result is returned for the
        caller to display in the status bar.
        """
        # 1. Validate the in-memory doc using the pure-Python
        #    validator. This does NOT touch the production file; it
        #    only reads the membership hashes file. If validation
        #    fails, the save still proceeds (草稿可保存) but the
        #    result is included in the return value.
        try:
            hashes_path = _resolve_hashes_path(self.path)
            validation = validate_doc_dict(self._doc, hashes_path)
        except Exception as exc:
            validation = {
                "format_valid": False,
                "error": f"validator exception: {exc!r}",
            }
        # 2. Back up the on-disk file (if any). create_backup()
        #    uses a unique name so two saves in the same microsecond
        #    do not collide.
        backup_path: Optional[Path] = None
        if self.path.exists():
            backup_path = self.create_backup()
        # 3. Atomic write of the in-memory doc to the production path.
        self._atomic_write(self._doc)
        return {
            "saved": True,
            "backup": str(backup_path) if backup_path else None,
            "path": str(self.path),
            "validation": validation,
        }

    def validate_current_record(self, sample_id: str) -> dict:
        """Pure per-record eligibility check on the in-memory doc. Does
        NOT touch the on-disk file."""
        record = self.get_record(sample_id)
        if record is None:
            return {
                "format_valid": False,
                "eligible_for_reviewed": False,
                "eligible_for_adjudicated": False,
                "format_errors": [],
                "errors": [f"sample_id {sample_id!r} not found"],
                "review_state_status": None,
            }
        return validate_record_for_review(record, {"service": self})

    def validate_global(self) -> dict:
        """Run the global aggregator against the on-disk file. Use
        after ``save_draft()`` to populate the status bar."""
        return validate_global(self.path)

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------
    def _snapshot_for_undo(self, sample_id: str) -> None:
        record = self.get_record(sample_id)
        if record is None:
            return
        self._undo_stack.append({
            "sample_id": sample_id,
            "record": copy.deepcopy(record),
        })
        while len(self._undo_stack) > self.max_undo:
            self._undo_stack.pop(0)

    def undo(self) -> Optional[dict]:
        """Pop the most recent per-record snapshot and restore it in
        the in-memory doc. Caller is responsible for ``save_draft()``
        to persist. Returns the popped snapshot (or None if stack is
        empty)."""
        if not self._undo_stack:
            return None
        snap = self._undo_stack.pop()
        for i, r in enumerate(self.records):
            if isinstance(r, dict) and r.get("sample_id") == snap["sample_id"]:
                self.records[i] = snap["record"]
                return snap
        return snap

    def undo_stack_size(self) -> int:
        return len(self._undo_stack)

    # ------------------------------------------------------------------
    # Action log
    # ------------------------------------------------------------------
    def append_action_log(
        self,
        sample_id: str,
        field: str,
        action: str,
        old_value,
        new_value,
    ) -> None:
        """Append one action log entry. ``old_value`` / ``new_value``
        are stringified deterministically before SHA-256."""
        self.action_log.parent.mkdir(parents=True, exist_ok=True)
        old_sha = sha256_text(
            json.dumps(old_value, ensure_ascii=False, sort_keys=True)
            if not isinstance(old_value, str) else old_value
        )
        new_sha = sha256_text(
            json.dumps(new_value, ensure_ascii=False, sort_keys=True)
            if not isinstance(new_value, str) else new_value
        )
        entry = {
            "timestamp": now_utc_iso(),
            "sample_id": sample_id,
            "field": field,
            "action": action,
            "old_sha256": old_sha,
            "new_sha256": new_sha,
            "reviewer": self.reviewer,
        }
        with self.action_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------
    def accept_translation(
        self, sample_id: str, candidate_text: str | None = None
    ) -> dict:
        """Set the record's approved_text_en to the LLM English
        candidate (or to ``candidate_text`` if provided) and mark
        translation decision as `accepted`."""
        r = self.get_record(sample_id)
        if r is None:
            return {"ok": False, "errors": [f"sample_id {sample_id!r} not found"]}
        new_text = candidate_text if candidate_text is not None else r.get("candidate_text_en")
        if not new_text:
            return {"ok": False, "errors": ["no English candidate available"]}
        self._snapshot_for_undo(sample_id)
        old_ap = r.get("approved_text_en")
        if old_ap != new_text:
            if old_ap is not None:
                r.setdefault("approved_text_en_history", []).append({
                    "approved_text_en": old_ap,
                    "approved_text_en_sha256": r.get("approved_text_en_sha256"),
                    "superseded_at": now_utc_iso(),
                    "reason": "user accepted English candidate",
                })
            r["approved_text_en"] = new_text
            r["approved_text_en_sha256"] = sha256_text(new_text)
            for c in r["human_correction"]["clauses"]:
                c["_stale"] = True
        r["decisions"]["translation"] = "accepted"
        r["human_correction"]["approved_text_en_decision"] = "accepted"
        if r["review_state"]["status"] == "needs_review":
            r["review_state"]["status"] = "in_progress"
            r["review_state"]["reviewer"] = self.reviewer
        self.append_action_log(
            sample_id, "decisions.translation", "accept_candidate", None, "accepted"
        )
        return {"ok": True}

    def edit_translation(self, sample_id: str, new_text: str | None) -> dict:
        """Replace approved_text_en with ``new_text`` and reset the
        translation decision + clauses to `unreviewed` (modifying the
        approved English invalidates all existing span offsets)."""
        r = self.get_record(sample_id)
        if r is None:
            return {"ok": False, "errors": [f"sample_id {sample_id!r} not found"]}
        self._snapshot_for_undo(sample_id)
        old_ap = r.get("approved_text_en")
        if old_ap != new_text:
            if old_ap is not None:
                r.setdefault("approved_text_en_history", []).append({
                    "approved_text_en": old_ap,
                    "approved_text_en_sha256": r.get("approved_text_en_sha256"),
                    "superseded_at": now_utc_iso(),
                    "reason": "user edited approved_text_en",
                })
            r["approved_text_en"] = new_text
            r["approved_text_en_sha256"] = sha256_text(new_text)
            for c in r["human_correction"]["clauses"]:
                c["_stale"] = True
        r["decisions"]["translation"] = "unreviewed"
        r["human_correction"]["approved_text_en_decision"] = "unreviewed"
        r["review_state"]["status"] = "needs_review"
        r["review_state"]["reviewer"] = None
        r["review_state"]["reviewed_at"] = None
        r["review_state"]["adjudicated_at"] = None
        self.append_action_log(
            sample_id, "approved_text_en", "edit", old_ap, new_text
        )
        return {"ok": True}

    def reject_translation(self, sample_id: str) -> dict:
        """Mark the English candidate as rejected. Does NOT modify
        approved_text_en."""
        r = self.get_record(sample_id)
        if r is None:
            return {"ok": False, "errors": [f"sample_id {sample_id!r} not found"]}
        self._snapshot_for_undo(sample_id)
        old = r["decisions"].get("translation")
        r["decisions"]["translation"] = "rejected"
        r["human_correction"]["approved_text_en_decision"] = "rejected"
        if r["review_state"]["status"] == "needs_review":
            r["review_state"]["status"] = "in_progress"
            r["review_state"]["reviewer"] = self.reviewer
        self.append_action_log(
            sample_id, "decisions.translation", "reject_candidate", old, "rejected"
        )
        return {"ok": True}

    # ------------------------------------------------------------------
    # Six-element field operations
    # ------------------------------------------------------------------
    def accept_field(self, sample_id: str, clause_id: str, field: str) -> dict:
        return self._set_field_decision(sample_id, clause_id, field, "accepted")

    def reject_field(self, sample_id: str, clause_id: str, field: str) -> dict:
        return self._set_field_decision(sample_id, clause_id, field, "rejected")

    def edit_field(
        self, sample_id: str, clause_id: str, field: str, new_value
    ) -> dict:
        r = self.get_record(sample_id)
        if r is None:
            return {"ok": False, "errors": [f"sample_id {sample_id!r} not found"]}
        if field not in ("modality", "actor", "action", "condition", "constraint", "exception"):
            return {"ok": False, "errors": [f"field {field!r} invalid"]}
        clause = next(
            (c for c in r["human_correction"]["clauses"] if c.get("clause_id") == clause_id),
            None,
        )
        if clause is None:
            return {"ok": False, "errors": [f"clause_id {clause_id!r} not found"]}
        self._snapshot_for_undo(sample_id)
        if field == "modality":
            old = clause["modality"].get("value")
            clause["modality"]["value"] = new_value
            ap = r.get("approved_text_en")
            if ap and new_value:
                s = ap.find(new_value)
                e = ap.find(new_value, s + 1) if s >= 0 else -1
                if s >= 0 and e < 0:
                    clause["modality"]["span"] = {
                        "text": new_value, "start": s, "end": s + len(new_value)
                    }
            r["decisions"][field] = "edited"
            self.append_action_log(
                sample_id,
                f"clauses.{clause_id}.{field}.value",
                "edit", old, new_value,
            )
        else:
            arr = clause.get(field, [])
            if arr:
                old = arr[0].get("text")
                arr[0]["text"] = new_value
            else:
                old = None
                clause.setdefault(field, []).append({
                    "id": self._next_span_id(clause, field),
                    "text": new_value,
                    "decision": "edited",
                })
            r["decisions"][field] = "edited"
            self.append_action_log(
                sample_id,
                f"clauses.{clause_id}.{field}[0].text",
                "edit", old, new_value,
            )
        if r["review_state"]["status"] == "needs_review":
            r["review_state"]["status"] = "in_progress"
            r["review_state"]["reviewer"] = self.reviewer
        return {"ok": True}

    def _set_field_decision(
        self, sample_id: str, clause_id: str, field: str, decision: str
    ) -> dict:
        r = self.get_record(sample_id)
        if r is None:
            return {"ok": False, "errors": [f"sample_id {sample_id!r} not found"]}
        if field not in ("modality", "actor", "action", "condition", "constraint", "exception"):
            return {"ok": False, "errors": [f"field {field!r} invalid"]}
        if decision not in ("accepted", "edited", "rejected"):
            return {"ok": False, "errors": [f"decision {decision!r} invalid"]}
        clause = next(
            (c for c in r["human_correction"]["clauses"] if c.get("clause_id") == clause_id),
            None,
        )
        if clause is None:
            return {"ok": False, "errors": [f"clause_id {clause_id!r} not found"]}
        self._snapshot_for_undo(sample_id)
        if field == "modality":
            old = clause["modality"].get("decision")
            clause["modality"]["decision"] = decision
            self.append_action_log(
                sample_id,
                f"clauses.{clause_id}.{field}.decision",
                "set", old, decision,
            )
        else:
            arr = clause.get(field, [])
            if not arr:
                arr.append({
                    "id": self._next_span_id(clause, field),
                    "text": None,
                    "decision": decision,
                })
                clause[field] = arr
            else:
                arr[0]["decision"] = decision
            self.append_action_log(
                sample_id,
                f"clauses.{clause_id}.{field}[0].decision",
                "set", None, decision,
            )
        r["decisions"][field] = decision
        if r["review_state"]["status"] == "needs_review":
            r["review_state"]["status"] = "in_progress"
            r["review_state"]["reviewer"] = self.reviewer
        return {"ok": True}

    def _next_span_id(self, clause: dict, fld: str) -> str:
        used: set[str] = set()
        for f in SPAN_FIELDS:
            for s in clause.get(f, []):
                used.add(s.get("id"))
        n = 1
        while f"{clause['clause_id']}_sp{n:03d}" in used:
            n += 1
        return f"{clause['clause_id']}_sp{n:03d}"

    # ------------------------------------------------------------------
    # Mark reviewed / adjudicated
    # ------------------------------------------------------------------
    def mark_reviewed(self, sample_id: str) -> dict:
        r = self.get_record(sample_id)
        if r is None:
            return {"ok": False, "errors": [f"sample_id {sample_id!r} not found"]}
        eligibility = self.validate_current_record(sample_id)
        if not eligibility["eligible_for_reviewed"]:
            return {
                "ok": False,
                "errors": eligibility["errors"],
                "eligibility": eligibility,
            }
        self._snapshot_for_undo(sample_id)
        old = r["review_state"].get("status")
        r["review_state"]["status"] = "reviewed"
        r["review_state"]["reviewer"] = self.reviewer
        r["review_state"]["reviewed_at"] = now_utc_iso()
        self.append_action_log(
            sample_id, "review_state.status", "mark_reviewed", old, "reviewed"
        )
        return {"ok": True, "eligibility": eligibility}

    def mark_adjudicated(self, sample_id: str) -> dict:
        r = self.get_record(sample_id)
        if r is None:
            return {"ok": False, "errors": [f"sample_id {sample_id!r} not found"]}
        eligibility = self.validate_current_record(sample_id)
        if not eligibility["eligible_for_adjudicated"]:
            return {
                "ok": False,
                "errors": eligibility["errors"],
                "eligibility": eligibility,
            }
        self._snapshot_for_undo(sample_id)
        old = r["review_state"].get("status")
        r["review_state"]["status"] = "adjudicated"
        r["review_state"]["reviewer"] = self.reviewer
        r["review_state"]["adjudicated_at"] = now_utc_iso()
        self.append_action_log(
            sample_id, "review_state.status", "mark_adjudicated", old, "adjudicated"
        )
        return {"ok": True, "eligibility": eligibility}

    # ------------------------------------------------------------------
    # Convenience: count per-record stats (no file read)
    # ------------------------------------------------------------------
    def count_progress(self) -> dict:
        n_reviewed = 0
        n_adjudicated = 0
        n_approved_en = 0
        n_field_decisions_total = 0
        n_field_decisions_unreviewed = 0
        n_records_incomplete = 0
        for r in self.records:
            if not isinstance(r, dict):
                continue
            rs = (r.get("review_state") or {}).get("status", "needs_review")
            if rs == "reviewed":
                n_reviewed += 1
            elif rs == "adjudicated":
                n_adjudicated += 1
            if r.get("approved_text_en"):
                n_approved_en += 1
            decisions = r.get("decisions") or {}
            any_unreviewed = decisions.get("translation") == "unreviewed"
            for k in ("modality", "actor", "action", "condition", "constraint", "exception"):
                n_field_decisions_total += 1
                if decisions.get(k) == "unreviewed":
                    n_field_decisions_unreviewed += 1
                    any_unreviewed = True
            if any_unreviewed:
                n_records_incomplete += 1
        return {
            "n_records": len(self.records),
            "n_approved_en": n_approved_en,
            "n_field_decisions_total": n_field_decisions_total,
            "n_field_decisions_unreviewed": n_field_decisions_unreviewed,
            "n_records_incomplete": n_records_incomplete,
            "n_reviewed": n_reviewed,
            "n_adjudicated": n_adjudicated,
        }


__all__ = [
    "HumanCorrectionService",
    "now_utc_iso",
    "next_backup_path",
]
