# -*- coding: utf-8 -*-
"""Centralized capsule lifecycle semantics (v5).

A SUPERSEDED historical capsule (v3, v4, ...) keeps its core assets
(schema, builder, verifier, four published outputs) byte-exact forever.
Once the assets its manifest binds (adapter sources, tests, status
documents) legitimately evolve, the historical builder MUST fail closed
with a no-overwrite rejection and the historical verifier MUST reject
with a binding/state-drift diagnosis. This module centralizes those
checks so that every new capsule version does not have to re-implement
"why does the old verifier now fail" logic in three red tests.

Deliberately NOT used for the ACTIVE capsule: the active builder/verifier
must rebuild and verify from current disk successfully.

Usage (tests):
    from bpc_hybrid.capsule_lifecycle import (
        historical_core_assets_match_head,
        builder_rejects_with_no_overwrite_drift,
        verifier_rejection_is_binding_drift,
        HistoricalCapsule,
    )
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Verifier failure names that are legitimate binding/state drift for a
# superseded capsule whose bound assets evolved. Anything else (missing
# files, tracebacks, arbitrary exceptions) is NOT accepted as drift.
DRIFT_FAILURE_PATTERNS = (
    "manifest exact reconstruction",
    "manifest bindings match disk",
    "manifest implementation hashes",
    "manifest artifact hashes",
    "state matrix re-derived",
    "superseded",
    "S2.11",
    "S2.13",
)

NO_OVERWRITE_MARKER = "refusing to overwrite different existing content"


@dataclass(frozen=True)
class HistoricalCapsule:
    """Locations of one superseded capsule (relative to formal_experiment/)."""

    name: str
    schema_rel: str
    builder_rel: str
    verifier_rel: str
    outputs: tuple[str, ...]


def git_head_blob(repo_root: Path, rel: str) -> bytes | None:
    """Return the HEAD blob bytes for a repo-relative path, or None."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"HEAD:{rel}"],
        cwd=str(repo_root), capture_output=True, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout


def historical_core_assets_match_head(root: Path, capsule: HistoricalCapsule,
                                      ) -> tuple[bool, list[str]]:
    """The historical core assets must be byte-identical to HEAD."""
    repo_root = root.parent
    changed: list[str] = []
    for rel in (capsule.schema_rel, capsule.builder_rel,
                capsule.verifier_rel) + capsule.outputs:
        disk = root / rel
        head_blob = git_head_blob(repo_root, f"formal_experiment/{rel}")
        if head_blob is None:
            changed.append(f"{rel}:no-head-blob")
            continue
        if not disk.is_file() or disk.read_bytes() != head_blob:
            changed.append(rel)
    return (not changed, changed)


def builder_rejects_with_no_overwrite_drift(
        root: Path, capsule: HistoricalCapsule,
        ) -> tuple[bool, str]:
    """The historical builder must fail closed with a no-overwrite
    rejection (exit 2) and must NOT modify its own published outputs."""
    before = {}
    for rel in capsule.outputs:
        p = root / rel
        before[rel] = p.read_bytes() if p.is_file() else None
    proc = subprocess.run(
        [sys.executable, str(root / capsule.builder_rel)],
        cwd=str(root), capture_output=True, text=True, check=False)
    drift_ok = bool(
        proc.returncode == 2
        and NO_OVERWRITE_MARKER in (proc.stderr or "").lower())
    outputs_untouched = all(
        (root / rel).read_bytes() == data
        for rel, data in before.items() if data is not None)
    after_created = any(
        (root / rel).is_file() for rel, data in before.items()
        if data is None)
    ok = drift_ok and outputs_untouched and not after_created
    detail = (
        f"rc={proc.returncode} no_overwrite={drift_ok} "
        f"outputs_untouched={outputs_untouched} "
        f"unexpected_created={after_created}\n"
        f"stderr={proc.stderr[:400]}")
    return (ok, detail)


def verifier_rejection_is_binding_drift(
        root: Path, capsule: HistoricalCapsule,
        ) -> tuple[bool, str]:
    """The historical verifier must reject (exit 1) with failures that all
    belong to the declared binding/state-drift patterns and must not crash
    with a traceback or a missing-file failure."""
    proc = subprocess.run(
        [sys.executable, str(root / capsule.verifier_rel)],
        cwd=str(root), capture_output=True, text=True, check=False)
    if "Traceback" in (proc.stderr or ""):
        return (False, "verifier crashed with a traceback")
    if proc.returncode == 0:
        return (False, "historical verifier unexpectedly passed")
    failures = [
        line.split("FAIL", 1)[1].strip()
        for line in (proc.stdout or "").splitlines()
        if line.startswith("FAIL")]
    if not failures:
        return (False, "verifier failed without FAIL lines")
    unexpected = [
        name for name in failures
        if not any(p in name for p in DRIFT_FAILURE_PATTERNS)]
    if unexpected:
        return (False, f"non-drift failures: {unexpected}")
    return (True, "; ".join(failures))
