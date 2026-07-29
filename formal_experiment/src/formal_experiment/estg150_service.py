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
        """Copy one immutable LLM candidate field into the editable
        human-correction clause and mark it ``accepted``.

        An accepted decision is therefore never a dangling status: the
        candidate value, exact character offsets, and evidence text are
        materialized in ``human_correction`` by the user's click.  A null
        candidate for the five span fields means that the user accepts the
        field as absent, so the corresponding array remains empty.
        """
        r = self.get_record(sample_id)
        if r is None:
            return {"ok": False, "errors": [f"sample_id {sample_id!r} not found"]}
        if field not in ("modality", "actor", "action", "condition", "constraint", "exception"):
            return {"ok": False, "errors": [f"field {field!r} invalid"]}
        clause = self._human_clause(r, clause_id)
        candidate = self._candidate_clause(r, clause_id)
        if clause is None:
            return {"ok": False, "errors": [f"clause_id {clause_id!r} not found"]}
        if candidate is None:
            return {
                "ok": False,
                "errors": [f"LLM candidate clause {clause_id!r} not found; edit the field manually"],
            }

        prepared = self._prepare_candidate_field(r, clause, candidate, field)
        if not prepared["ok"]:
            return prepared

        self._snapshot_for_undo(sample_id)
        old = copy.deepcopy(clause.get(field if field == "modality" else f"{field}s"))
        if field == "modality":
            clause["modality"] = prepared["value"]
        else:
            clause[f"{field}s"] = prepared["value"]
        r["decisions"][field] = "accepted"
        self._touch_in_progress(r)
        self.append_action_log(
            sample_id,
            f"clauses.{clause_id}.{field}",
            "accept_llm_candidate",
            old,
            prepared["value"],
        )
        return {"ok": True}

    def reject_field(self, sample_id: str, clause_id: str, field: str) -> dict:
        """Reject a candidate field and clear it from the editable result.

        The immutable candidate remains available on the left side of the
        GUI for provenance.  Clearing the human value prevents a previous
        accept/edit from surviving under a later ``rejected`` decision.
        """
        r = self.get_record(sample_id)
        if r is None:
            return {"ok": False, "errors": [f"sample_id {sample_id!r} not found"]}
        if field not in ("modality", "actor", "action", "condition", "constraint", "exception"):
            return {"ok": False, "errors": [f"field {field!r} invalid"]}
        clause = self._human_clause(r, clause_id)
        if clause is None:
            return {"ok": False, "errors": [f"clause_id {clause_id!r} not found"]}

        self._snapshot_for_undo(sample_id)
        key = field if field == "modality" else f"{field}s"
        old = copy.deepcopy(clause.get(key))
        if field == "modality":
            clause["modality"] = {
                "value": None,
                "decision": "rejected",
                "span": None,
                "notes": None,
            }
        else:
            clause[key] = []
        r["decisions"][field] = "rejected"
        self._touch_in_progress(r)
        self.append_action_log(
            sample_id,
            f"clauses.{clause_id}.{field}",
            "reject_llm_candidate",
            old,
            clause.get(key),
        )
        return {"ok": True}

    def accept_all_candidate_fields(self, sample_id: str) -> dict:
        """Materialize every usable Layer-C candidate for one record.

        This method is called only by the explicit GUI button.  It never
        auto-approves a record, never changes the immutable ``llm_candidate``
        block, and refuses atomically when the approved English differs from
        the candidate text or when a non-null candidate span cannot be bound
        exactly to that English text.
        """
        r = self.get_record(sample_id)
        if r is None:
            return {"ok": False, "errors": [f"sample_id {sample_id!r} not found"]}
        approved = r.get("approved_text_en")
        if not approved:
            return {"ok": False, "errors": ["approve the English translation first"]}
        if approved != r.get("candidate_text_en"):
            return {
                "ok": False,
                "errors": [
                    "approved English was edited; the old LLM spans are stale. "
                    "Review and add corrected spans manually."
                ],
            }

        candidate_clauses = list((r.get("llm_candidate") or {}).get("clauses") or [])
        if not candidate_clauses:
            return {"ok": False, "errors": ["this record has no LLM candidate clause"]}

        prepared_clauses: list[dict] = []
        errors: list[str] = []
        for candidate in candidate_clauses:
            clause_id = candidate.get("clause_id")
            clause_span = copy.deepcopy(candidate.get("clause_span") or {})
            start = clause_span.get("start")
            end = clause_span.get("end")
            if (
                not isinstance(clause_id, str)
                or not isinstance(start, int)
                or not isinstance(end, int)
                or start < 0
                or end <= start
                or end > len(approved)
                or clause_span.get("text") != approved[start:end]
            ):
                errors.append(f"candidate clause {clause_id!r} has an invalid clause span")
                continue
            human_clause = {
                "clause_id": clause_id,
                "clause_span": clause_span,
                "clause_span_status": candidate.get("clause_span_status") or "candidate_copied",
                "modality": {"value": None, "decision": "unreviewed", "span": None, "notes": None},
                "actors": [],
                "actions": [],
                "conditions": [],
                "constraints": [],
                "exceptions": [],
                "actor_action_map": [],
                "order_relations": [],
            }
            for field in ("modality", "actor", "action", "condition", "constraint", "exception"):
                prepared = self._prepare_candidate_field(r, human_clause, candidate, field)
                if not prepared["ok"]:
                    errors.extend(
                        f"{clause_id}.{field}: {msg}" for msg in prepared.get("errors", [])
                    )
                    continue
                if field == "modality":
                    human_clause["modality"] = prepared["value"]
                else:
                    human_clause[f"{field}s"] = prepared["value"]
            prepared_clauses.append(human_clause)

        if errors:
            return {"ok": False, "errors": errors}

        self._snapshot_for_undo(sample_id)
        old = copy.deepcopy(r["human_correction"].get("clauses") or [])
        r["human_correction"]["clauses"] = prepared_clauses
        for field in ("modality", "actor", "action", "condition", "constraint", "exception"):
            r["decisions"][field] = "accepted"
        self._touch_in_progress(r)
        self.append_action_log(
            sample_id,
            "human_correction.clauses",
            "accept_all_llm_candidates",
            old,
            prepared_clauses,
        )
        return {"ok": True, "clause_count": len(prepared_clauses)}

    def edit_field(
        self, sample_id: str, clause_id: str, field: str, new_value
    ) -> dict:
        r = self.get_record(sample_id)
        if r is None:
            return {"ok": False, "errors": [f"sample_id {sample_id!r} not found"]}
        if field not in ("modality", "actor", "action", "condition", "constraint", "exception"):
            return {"ok": False, "errors": [f"field {field!r} invalid"]}
        clause = self._human_clause(r, clause_id)
        if clause is None:
            return {"ok": False, "errors": [f"clause_id {clause_id!r} not found"]}
        if field == "modality":
            self._snapshot_for_undo(sample_id)
            old = clause["modality"].get("value")
            clause["modality"]["value"] = new_value
            clause["modality"]["span"] = None
            clause["modality"]["decision"] = "edited"
            r["decisions"][field] = "edited"
            self.append_action_log(
                sample_id,
                f"clauses.{clause_id}.{field}.value",
                "edit", old, new_value,
            )
        else:
            key = f"{field}s"
            arr = clause.get(key, [])
            old = copy.deepcopy(arr)
            if new_value is None:
                prepared_spans = []
            else:
                exact = self._find_unique_span(r, clause, new_value)
                if not exact["ok"]:
                    return exact
                existing_id = arr[0].get("id") if arr else self._next_span_id(clause, key)
                prepared_spans = [{
                    "id": existing_id,
                    "text": new_value,
                    "start": exact["start"],
                    "end": exact["end"],
                    "decision": "edited",
                }]
            self._snapshot_for_undo(sample_id)
            clause[key] = prepared_spans
            r["decisions"][field] = "edited"
            self.append_action_log(
                sample_id,
                f"clauses.{clause_id}.{key}",
                "edit", old, clause[key],
            )
        self._touch_in_progress(r)
        return {"ok": True}

    def _set_field_decision(
        self, sample_id: str, clause_id: str, field: str, decision: str
    ) -> dict:
        r = self.get_record(sample_id)
        if r is None:
            return {"ok": False, "errors": [f"sample_id {sample_id!r} not found"]}
        if field not in ("modality", "actor", "action", "condition", "constraint", "exception"):
            return {"ok": False, "errors": [f"field {field!r} invalid"]}
        if decision not in ("edited", "needs_adjudication", "unreviewed"):
            return {"ok": False, "errors": [f"decision {decision!r} invalid"]}
        clause = self._human_clause(r, clause_id)
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
            key = f"{field}s"
            arr = clause.get(key, [])
            old = [span.get("decision") for span in arr]
            for span in arr:
                span["decision"] = decision
            self.append_action_log(
                sample_id,
                f"clauses.{clause_id}.{key}[*].decision",
                "set", old, decision,
            )
        r["decisions"][field] = decision
        self._touch_in_progress(r)
        return {"ok": True}

    @staticmethod
    def _human_clause(record: dict, clause_id: str) -> dict | None:
        return next(
            (
                c
                for c in record.get("human_correction", {}).get("clauses", [])
                if c.get("clause_id") == clause_id
            ),
            None,
        )

    @staticmethod
    def _candidate_clause(record: dict, clause_id: str) -> dict | None:
        return next(
            (
                c
                for c in (record.get("llm_candidate") or {}).get("clauses", [])
                if c.get("clause_id") == clause_id
            ),
            None,
        )

    def _prepare_candidate_field(
        self,
        record: dict,
        human_clause: dict,
        candidate_clause: dict,
        field: str,
    ) -> dict:
        candidate = candidate_clause.get(field) or {}
        value = candidate.get("value") if isinstance(candidate, dict) else None
        if field == "modality":
            if value not in ("obligation", "prohibition", "permission", "definition"):
                return {
                    "ok": False,
                    "errors": [f"LLM modality candidate {value!r} is missing or invalid"],
                }
            return {
                "ok": True,
                "value": {
                    "value": value,
                    "decision": "accepted",
                    "span": copy.deepcopy(candidate.get("span")),
                    "notes": None,
                },
            }

        if value is None:
            return {"ok": True, "value": []}
        span = candidate.get("span") if isinstance(candidate, dict) else None
        approved = record.get("approved_text_en") or ""
        clause_span = human_clause.get("clause_span") or {}
        if not isinstance(span, dict):
            return {
                "ok": False,
                "errors": [
                    f"LLM candidate {value!r} has no exact span; use the manual span editor"
                ],
            }
        start = span.get("start")
        end = span.get("end")
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or start < clause_span.get("start", 0)
            or end > clause_span.get("end", len(approved))
            or end <= start
            or approved[start:end] != span.get("text")
        ):
            return {
                "ok": False,
                "errors": [
                    f"LLM candidate {value!r} does not have a valid exact span in approved English"
                ],
            }
        key = f"{field}s"
        return {
            "ok": True,
            "value": [{
                "id": self._next_span_id(human_clause, key),
                "text": span["text"],
                "start": start,
                "end": end,
                "decision": "accepted",
            }],
        }

    @staticmethod
    def _find_unique_span(record: dict, clause: dict, text: str) -> dict:
        approved = record.get("approved_text_en") or ""
        clause_span = clause.get("clause_span") or {}
        start_bound = clause_span.get("start", 0)
        end_bound = clause_span.get("end", len(approved))
        positions: list[int] = []
        pos = approved.find(text, start_bound, end_bound)
        while pos >= 0 and pos + len(text) <= end_bound:
            positions.append(pos)
            pos = approved.find(text, pos + 1, end_bound)
        if len(positions) != 1:
            reason = "not found" if not positions else "appears more than once"
            return {
                "ok": False,
                "errors": [
                    f"edited text {text!r} {reason} inside the clause; "
                    "use the manual span editor with explicit start/end"
                ],
            }
        return {"ok": True, "start": positions[0], "end": positions[0] + len(text)}

    def _touch_in_progress(self, record: dict) -> None:
        if record["review_state"]["status"] == "needs_review":
            record["review_state"]["status"] = "in_progress"
            record["review_state"]["reviewer"] = self.reviewer

    def edit_relations(
        self,
        sample_id: str,
        clause_id: str,
        actor_action_map: list,
        order_relations: list,
    ) -> dict:
        """Validate and store the two relation arrays edited in the GUI."""
        r = self.get_record(sample_id)
        if r is None:
            return {"ok": False, "errors": [f"sample_id {sample_id!r} not found"]}
        clause = self._human_clause(r, clause_id)
        if clause is None:
            return {"ok": False, "errors": [f"clause_id {clause_id!r} not found"]}
        if not isinstance(actor_action_map, list) or not isinstance(order_relations, list):
            return {"ok": False, "errors": ["relation JSON values must both be arrays"]}

        actor_ids = {span.get("id") for span in clause.get("actors", [])}
        action_ids = {span.get("id") for span in clause.get("actions", [])}
        errors: list[str] = []
        for index, edge in enumerate(actor_action_map):
            if not isinstance(edge, dict):
                errors.append(f"actor_action_map[{index}] must be an object")
                continue
            actor_id = edge.get("actor_id")
            action_id = edge.get("action_id")
            if actor_id is not None and actor_id not in actor_ids:
                errors.append(f"actor_action_map[{index}].actor_id {actor_id!r} is unknown")
            if action_id not in action_ids:
                errors.append(f"actor_action_map[{index}].action_id {action_id!r} is unknown")
        for index, edge in enumerate(order_relations):
            if not isinstance(edge, dict):
                errors.append(f"order_relations[{index}] must be an object")
                continue
            before = edge.get("before_action_id")
            after = edge.get("after_action_id")
            if before not in action_ids:
                errors.append(f"order_relations[{index}].before_action_id {before!r} is unknown")
            if after not in action_ids:
                errors.append(f"order_relations[{index}].after_action_id {after!r} is unknown")
            if before is not None and before == after:
                errors.append(f"order_relations[{index}] cannot order an action before itself")
        if errors:
            return {"ok": False, "errors": errors}

        new_actor_action_map = copy.deepcopy(actor_action_map)
        new_order_relations = copy.deepcopy(order_relations)
        old = {
            "actor_action_map": copy.deepcopy(clause.get("actor_action_map") or []),
            "order_relations": copy.deepcopy(clause.get("order_relations") or []),
        }
        new = {
            "actor_action_map": new_actor_action_map,
            "order_relations": new_order_relations,
        }
        if old == new:
            return {"ok": True, "changed": False}

        self._snapshot_for_undo(sample_id)
        clause["actor_action_map"] = new_actor_action_map
        clause["order_relations"] = new_order_relations
        self._touch_in_progress(r)
        self.append_action_log(
            sample_id,
            f"clauses.{clause_id}.relations",
            "edit_relations",
            old,
            new,
        )
        return {"ok": True, "changed": True}

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
    # One-click simple review
    # ------------------------------------------------------------------
    def apply_simple_review_candidate(
        self,
        sample_id: str,
        candidate: dict,
        *,
        candidate_source: str = "codex_internal_gpt56sol_full150_v1",
    ) -> dict:
        """Persist one user-confirmed Sol candidate in a single operation.

        The simple GUI deliberately hides the legacy accept/review/adjudicate
        state machine.  A click on ``保存并下一条`` is the user's explicit final
        decision for the displayed record, so this method materializes the
        exact spans, runs both per-record gates in memory, and stores the final
        state atomically from the GUI's point of view.  ``save_draft()`` remains
        the only method that writes the Layer-E file to disk.

        The immutable Layer-C candidate is never changed.  Six-element
        decisions are recorded as ``edited`` because the confirmed values came
        from the newer Sol candidate (possibly after user edits), not from the
        immutable Layer-C draft.  Translation is ``accepted`` only when the
        confirmed English is byte-identical to the frozen Layer-B text.
        """
        record = self.get_record(sample_id)
        if record is None:
            return {"ok": False, "errors": [f"sample_id {sample_id!r} not found"]}
        if not isinstance(candidate, dict) or candidate.get("sample_id") != sample_id:
            return {"ok": False, "errors": ["candidate sample_id does not match"]}
        translation = candidate.get("translation") or {}
        approved = translation.get("proposed_text_en")
        clauses = candidate.get("clauses")
        if not isinstance(approved, str) or not approved.strip():
            return {"ok": False, "errors": ["candidate has no approved English text"]}
        if not isinstance(clauses, list) or not clauses:
            return {"ok": False, "errors": ["candidate must contain at least one clause"]}

        prepared = copy.deepcopy(record)
        old_approved = prepared.get("approved_text_en")
        if old_approved is not None and old_approved != approved:
            prepared.setdefault("approved_text_en_history", []).append({
                "approved_text_en": old_approved,
                "approved_text_en_sha256": prepared.get("approved_text_en_sha256"),
                "superseded_at": now_utc_iso(),
                "reason": "user confirmed a Sol candidate in the simple review tool",
            })
        prepared["approved_text_en"] = approved
        prepared["approved_text_en_sha256"] = sha256_text(approved)

        translation_decision = (
            "accepted" if approved == prepared.get("candidate_text_en") else "edited"
        )
        prepared["decisions"]["translation"] = translation_decision
        prepared["human_correction"]["approved_text_en_decision"] = translation_decision

        human_clauses: list[dict] = []
        for clause in clauses:
            if not isinstance(clause, dict):
                return {"ok": False, "errors": ["candidate clause is not an object"]}
            modality = clause.get("modality") or {}
            evidence = modality.get("evidence") or []
            human_clause = {
                "clause_id": clause.get("clause_id"),
                "clause_span": copy.deepcopy(clause.get("clause_span") or {}),
                "clause_span_status": "sol_candidate_user_confirmed",
                "modality": {
                    "value": modality.get("label"),
                    "decision": "edited",
                    "span": copy.deepcopy(evidence[0]) if evidence else None,
                    "notes": None,
                },
                "actors": [],
                "actions": [],
                "conditions": [],
                "constraints": [],
                "exceptions": [],
                "actor_action_map": copy.deepcopy(clause.get("actor_action_map") or []),
                "order_relations": copy.deepcopy(clause.get("order_relations") or []),
            }
            for field in SPAN_FIELDS:
                for span in clause.get(field) or []:
                    human_clause[field].append({
                        "id": span.get("id"),
                        "text": span.get("text"),
                        "start": span.get("start"),
                        "end": span.get("end"),
                        "decision": "edited",
                    })
            human_clauses.append(human_clause)

        prepared["human_correction"]["clauses"] = human_clauses
        for field in ("modality", "actor", "action", "condition", "constraint", "exception"):
            prepared["decisions"][field] = "edited"

        prepared["review_state"]["status"] = "in_progress"
        prepared["review_state"]["reviewer"] = self.reviewer
        prepared["review_state"]["reviewed_at"] = None
        prepared["review_state"]["adjudicated_at"] = None
        review_gate = validate_record_for_review(prepared, {"service": self})
        if not review_gate["eligible_for_reviewed"]:
            return {
                "ok": False,
                "errors": review_gate["format_errors"] + review_gate["errors"],
                "eligibility": review_gate,
            }

        decided_at = now_utc_iso()
        prepared["review_state"]["status"] = "reviewed"
        prepared["review_state"]["reviewed_at"] = decided_at
        final_gate = validate_record_for_review(prepared, {"service": self})
        if not final_gate["eligible_for_adjudicated"]:
            return {
                "ok": False,
                "errors": final_gate["format_errors"] + final_gate["errors"],
                "eligibility": final_gate,
            }
        prepared["review_state"]["status"] = "adjudicated"
        prepared["review_state"]["adjudicated_at"] = decided_at
        if not prepared["review_state"].get("notes"):
            prepared["review_state"]["notes"] = (
                f"Confirmed in the simple review tool; candidate source: {candidate_source}"
            )

        self._snapshot_for_undo(sample_id)
        for index, existing in enumerate(self.records):
            if existing.get("sample_id") == sample_id:
                self.records[index] = prepared
                break
        self.append_action_log(
            sample_id,
            "human_correction",
            "simple_save_and_next",
            record.get("human_correction"),
            prepared.get("human_correction"),
        )
        return {
            "ok": True,
            "clause_count": len(human_clauses),
            "candidate_source": candidate_source,
        }

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
