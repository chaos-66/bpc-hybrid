# -*- coding: utf-8 -*-
"""Centralized capsule lifecycle semantics (v6).

A SUPERSEDED historical capsule (v3, v4, v5, ...) keeps its core assets
(schema, builder, verifier, four published outputs) byte-exact forever.
Once the assets its manifest binds (adapter sources, tests, status
documents) legitimately evolve, the historical builder MUST fail closed
with a no-overwrite rejection and the historical verifier MUST reject
with a binding/state-drift diagnosis. This module centralizes those
checks so that every new capsule version does not have to re-implement
"why does the old verifier now fail" logic in three red tests.

v6 FIXED ORIGIN ANCHORS: byte-exactness is anchored to the ORIGIN COMMIT
of each historical capsule, not to the current HEAD. The v5
`historical_core_assets_match_head` compared disk bytes to `HEAD:path`;
if a later commit modified the historical files in HEAD *and* on disk
together, disk would still equal HEAD and the check would pass. v6
hardcodes, for each version (v3/v4/v5), the origin commit SHA and the
SHA-256 of every core asset blob at that commit. The historical assets
must match BOTH the fixed SHA-256 map AND the origin-commit blob; a
simultaneous HEAD+disk rewrite to the same wrong bytes still fails
because the fixed map is independent of HEAD.

Deliberately NOT used for the ACTIVE capsule: the active builder/verifier
must rebuild and verify from current disk successfully.

Usage (tests):
    from bpc_hybrid.capsule_lifecycle import (
        fixed_core_asset_hashes,
        historical_core_assets_match_fixed_origin,
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
    # post-user-authorization lifecycle drift: the G0.5 contract moved
    # from draft_not_frozen to frozen_for_future_external_complex_corpora
    # and promotion readiness flipped accordingly
    "G0.5 promotion readiness",
    "G0.5 candidate",
)

NO_OVERWRITE_MARKER = "refusing to overwrite different existing content"
FAIL_CLOSED_MARKER = "BUILD FAILED (fail-closed)"

# ---------------------------------------------------------------------------
# v6 fixed origin anchors: origin commit per historical capsule version.
# ---------------------------------------------------------------------------
FIXED_ORIGIN_COMMITS: dict[str, str] = {
    "v3": "31ac757d821b7e451650edbd70b1899ed0104616",
    "v4": "8e8b488ea6d91ef0e6d0cf942ff9729e3e6776f6",
    "v5": "78837391167639da1bdef74faf67b817fa604813",
    "v6": "518047d4c97ab691fdf0edeeea27c6cf1674765e",
}

CORE_ASSET_REL_TEMPLATES: tuple[tuple[str, str], ...] = (
    ("schema", "configs/schemas/s2_11_g0_5_pre_authorization_{v}.schema.json"),
    ("builder", "scripts/build_s2_11_g0_5_pre_authorization_{v}.py"),
    ("verifier", "scripts/verify_s2_11_g0_5_pre_authorization_{v}.py"),
    ("json", "outputs/reports/s2_11_g0_5_pre_authorization_{v}.json"),
    ("md", "outputs/reports/s2_11_g0_5_pre_authorization_{v}.md"),
    ("manifest",
     "outputs/reports/s2_11_g0_5_pre_authorization_{v}.manifest.json"),
    ("export_index",
     "outputs/reports/s2_11_g0_5_pre_authorization_{v}_export_index.json"),
)

# Fixed SHA-256 of every historical core asset blob AT ITS ORIGIN COMMIT.
# These 21 hashes are the immovable anchor: disk bytes must match them,
# and the origin-commit git blobs must match them too. They were computed
# from `git show <origin-commit>:formal_experiment/<rel>` on 2026-08-15
# (all 21 blobs existed and matched the working tree at v6 start).
FIXED_CORE_ASSET_HASHES: dict[str, dict[str, str]] = {
    "v3": {
        "schema": "50d0efd0432f965b34c8d211ff5ef1d31b73fbf4479862d82618a2f33744e0a1",
        "builder": "89ce3684fddcf582c859b85547c367cc8a84038a9b5269f1cd7b8ceb1479b537",
        "verifier": "830f6aad3e3e597c10dd3bef9f5cc32e5b67d12e314d9e99b23f04a9b662c553",
        "json": "7c380a171423e2fd859166e0307be84d5455ed323c07caf387b1d453c266a72b",
        "md": "557f30b9253445a349311c1fe0a604f8171428ac2fa062df2c3d75d10e6dc27a",
        "manifest": "cf2b7b577d8f8d1dcfd956d3031bf7c9ccd82f2433a2a5b90b7625431b538018",
        "export_index": "72c41725bc8153c671c0a6b411cc443cc62f7dcd765ef44d5cdab18bff719de6",
    },
    "v4": {
        "schema": "4f52d45a530d23e1aef3cf6582bbbc511d67b7e7db4bfe2dec2482fba58f4794",
        "builder": "3dfc2bbcd85afab0fa818a314cdce3c2823ae1b490280be1015e810440098259",
        "verifier": "69ed77a734686a100a990e4426e54fe214d2d506ec5c9dc73fd8281ae632ddfd",
        "json": "e4bc4f7d799be61ef99a75a3e1de03601f3885545e9a8e4a93ebed5654907e3b",
        "md": "ac76e0f6a3282bb8cba4a0d205465e386836e9631dc04c6c49bc0f3d1edb3585",
        "manifest": "9d9098a4df77446c9c50bb9bfd932cb9a666ac40843f747ce22321be437762a2",
        "export_index": "424ea8ddac8a5e23c3de1938f030d79c1613e167160a7e4db4843bd251626111",
    },
    "v5": {
        "schema": "c5dc45d2e2a35fc202d7bc6f2271814d718df15a312b29135077ac3fa80f9dcb",
        "builder": "630be461ddb6a0ef2193e6fa12f4eb7586d6ccaec1b968bfb3225fa0c4cfd7c8",
        "verifier": "2ebc47f9af2cc1152ea123531281569080c538292e1a0e42668b1ce05d972c70",
        "json": "01334b80f22d28dcc9dbb3d9624441fb08eb0169209fd171227bd4d489835464",
        "md": "8aa3cd622f0e41d710382c0aebe1edd0aee518c74b9161e848f5ff3566f21d0a",
        "manifest": "e6aaf0bb65725e89cb437f84128c430032768976270686701af909be5e6c0ac6",
        "export_index": "7263df3015ee34e437df1c8d544ef26449cdebd2b507dc121e14593f32d1cf73",
    },
    "v6": {
        "schema": "a762ee55446ddc9f379b5ac941187cf29e42dc82af7ac0970a59044ba2be9575",
        "builder": "ac50855f0ee52e67ecb77d3de3221444110195f8a9caa79d97f2ac6940ae8b66",
        "verifier": "8d521a4c803a762477896e0a880418113069ecaaf3b600b2c6ffd3c61c584ae6",
        "json": "f36cb9a8be117f3ff1fb6d1341dc7ffe8d1049daeaec494080deb3262e6ef1df",
        "md": "d3540eb6b30074b7d38df741bc21f55ff19491c236e2d6946027761296694d79",
        "manifest": "d335296cb5819d7c6eb8c4e1ad8a00553fbe82761884a5bc15c49195ab1dd3cd",
        "export_index": "6e18749da7cdcdecc79e7a200ab14ec565cca79a1226258e32d1ec4aaf6f1ee9",
    },
}


@dataclass(frozen=True)
class HistoricalCapsule:
    """Locations of one superseded capsule (relative to formal_experiment/)."""

    name: str
    schema_rel: str
    builder_rel: str
    verifier_rel: str
    outputs: tuple[str, ...]


def core_asset_rels(version: str) -> tuple[str, ...]:
    """The 7 fixed core-asset relative paths of one historical version."""
    return tuple(t.format(v=version) for _, t in CORE_ASSET_REL_TEMPLATES)


def fixed_core_asset_hashes(version: str) -> dict[str, str]:
    """The fixed SHA-256 map of one historical version (immovable anchor)."""
    if version not in FIXED_CORE_ASSET_HASHES:
        raise ValueError(f"no fixed origin anchors for version {version!r}")
    return dict(FIXED_CORE_ASSET_HASHES[version])


def git_head_blob(repo_root: Path, rel: str) -> bytes | None:
    """Return the HEAD blob bytes for a repo-relative path, or None."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"HEAD:{rel}"],
        cwd=str(repo_root), capture_output=True, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout


def git_blob_at(repo_root: Path, commit: str, rel: str) -> bytes | None:
    """Return the blob bytes of `rel` at an explicit commit, or None."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{commit}:{rel}"],
        cwd=str(repo_root), capture_output=True, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout


def _fixed_rel_hash_map(version: str) -> dict[str, str]:
    """Map full relative path -> fixed SHA-256 for one version."""
    fixed = fixed_core_asset_hashes(version)
    return {t.format(v=version): fixed[key]
            for key, t in CORE_ASSET_REL_TEMPLATES}


def disk_matches_fixed_hashes(root: Path, version: str
                              ) -> tuple[bool, list[str]]:
    """The disk bytes of a historical capsule's core assets must match the
    FIXED SHA-256 map (independent of HEAD)."""
    fixed = _fixed_rel_hash_map(version)
    changed: list[str] = []
    for rel in core_asset_rels(version):
        p = root / rel
        if not p.is_file() or \
                hashlib.sha256(p.read_bytes()).hexdigest() != fixed[rel]:
            changed.append(rel)
    return (not changed, changed)


def origin_blobs_match_fixed_hashes(repo_root: Path, version: str
                                    ) -> tuple[bool, list[str]]:
    """The git blobs at the FIXED ORIGIN COMMIT must match the fixed
    SHA-256 map (self-consistency of the anchor against history)."""
    commit = FIXED_ORIGIN_COMMITS[version]
    fixed = _fixed_rel_hash_map(version)
    changed: list[str] = []
    for rel in core_asset_rels(version):
        blob = git_blob_at(repo_root, commit, f"formal_experiment/{rel}")
        if blob is None or hashlib.sha256(blob).hexdigest() != fixed[rel]:
            changed.append(rel)
    return (not changed, changed)


def historical_core_assets_match_fixed_origin(
        root: Path, version: str) -> tuple[bool, str]:
    """HISTORICAL byte-exactness anchored to the fixed origin commit.

    Requires BOTH:
      * disk bytes == fixed SHA-256 map;
      * origin-commit git blob == fixed SHA-256 map.

    Because the fixed map is hardcoded and independent of HEAD, a commit
    that rewrites a historical asset in HEAD *and* on disk with the same
    (wrong) bytes still fails this check — the old HEAD-relative check
    could not detect that scenario.
    """
    ok_disk, changed_disk = disk_matches_fixed_hashes(root, version)
    ok_origin, changed_origin = origin_blobs_match_fixed_hashes(
        root.parent, version)
    ok = ok_disk and ok_origin
    detail = (f"disk_mismatch={changed_disk} "
              f"origin_blob_mismatch={changed_origin}")
    return (ok, detail)


def historical_core_assets_match_head(root: Path, capsule: HistoricalCapsule,
                                      ) -> tuple[bool, list[str]]:
    """The historical core assets must be byte-identical to HEAD.

    NOTE (v6): this HEAD-relative check is retained for compatibility, but
    it is NO LONGER the immutability evidence for historical capsules —
    use :func:`historical_core_assets_match_fixed_origin` instead. A
    simultaneous HEAD+disk rewrite to the same wrong bytes passes this
    check by construction.
    """
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
    """The historical builder must fail closed (exit 2) with either a
    no-overwrite rejection or an earlier fail-closed derivation abort, and
    must NOT modify its own published outputs."""
    before = {}
    for rel in capsule.outputs:
        p = root / rel
        before[rel] = p.read_bytes() if p.is_file() else None
    proc = subprocess.run(
        [sys.executable, str(root / capsule.builder_rel)],
        cwd=str(root), capture_output=True, text=True, check=False)
    stderr_lower = (proc.stderr or "").lower()
    drift_ok = bool(
        proc.returncode == 2
        and (NO_OVERWRITE_MARKER in stderr_lower
             or FAIL_CLOSED_MARKER.lower() in stderr_lower))
    outputs_untouched = all(
        (root / rel).read_bytes() == data
        for rel, data in before.items() if data is not None)
    after_created = any(
        (root / rel).is_file() for rel, data in before.items()
        if data is None)
    ok = drift_ok and outputs_untouched and not after_created
    detail = (
        f"rc={proc.returncode} fail_closed={drift_ok} "
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
