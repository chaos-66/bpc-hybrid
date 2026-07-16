"""Atomic promotion of a run_dir's layer_d_v2.jsonl into
data/development/human_review/estg_150_review_aids_zh_v2.jsonl
and atomic update of configs/estg150_layer_d.json to switch
active_path to the v2 file (2026-07-14 hardened, third iteration).

The promotion is fail-closed:

  * Pre-flight checks (all must pass BEFORE any file is touched):
      - mixed run_id / model / provider across the run
      - mixed base_url across the run
      - Layer A / B / C SHA-256 unchanged
      - Layer E SHA-256 unchanged (the FULL file hash, not just
        the per-record status counts; this catches
        approved_text_en edits, decision changes, review_state
        transitions, notes edits, and any other byte change)
      - run_config immutability: provider / model / base_url /
        base_url_sha256 / temperature / max_tokens / membership /
        Layer A/B/C / prompt A/B / layer_e_sha256 all match the
        on-disk file before any write
  * Strict validator (CLI invocation, 20+ checks).
  * Atomic copy (tmp + rename) of the v2 file.
  * Atomic config update (tmp + rename).
  * Transactional rollback: the pre-promotion bytes of BOTH the
    v2 file (if it existed) AND the config are snapshotted; on
    any failure they are byte-restored.

  * If the v2 file did NOT exist before promotion and the config
    update fails, the just-written v2 file is removed.
  * If the v2 file DID exist before promotion and any later step
    fails, the v2 file is restored to its exact pre-promotion
    bytes.
  * In every case, the v1 placeholder file is checked by SHA-256
    before and after; any drift is a hard error.

  * Idempotent: re-running the promoter on a fully-promoted run
    (same v2 file, same active_path) is a no-op.

Run from formal_experiment/:

    python scripts/promote_layer_d_v2.py \\
        --run-dir data/development/estg/llm_candidate_runs/run_20260714_layerd
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Shared Layer D validator + security modules (2026-07-14).
from formal_experiment.layer_d_validator import (  # noqa: E402
    check_layer_e_pristine,
    check_v1_placeholder_unchanged,
    compute_layer_e_progress,
    sha256_path,
    sha256_text,
)


LAYER_D_CONFIG = REPO / "configs" / "estg150_layer_d.json"
V1_PLACEHOLDER = REPO / "data" / "development" / "human_review" / "estg_150_review_aids_zh_v1.jsonl"
V2_FILLED = REPO / "data" / "development" / "human_review" / "estg_150_review_aids_zh_v2.jsonl"
LAYER_E_PATH = REPO / "data" / "development" / "human_review" / "estg_150_human_correction_v1.json"
VALIDATOR = REPO / "scripts" / "validate_layer_d_v2.py"

LAYER_A_PATH = REPO / "data" / "development" / "estg" / "estg_selected_150_de.jsonl"
LAYER_B_PATH = REPO / "data" / "development" / "human_review" / "estg_150_translation_en_v1.jsonl"
LAYER_C_PATH = REPO / "data" / "development" / "human_review" / "estg_150_llm_six_element_candidates_v1.jsonl"

# Fields locked into run_config.json (must match on first write / resume).
RUN_CONFIG_LOCKED_FIELDS = (
    "provider", "model", "base_url", "base_url_sha256", "temperature", "max_tokens",
    "membership_payload_sha256", "layer_a_sha256", "layer_b_sha256",
    "layer_c_sha256", "prompt_a_sha256", "prompt_b_sha256",
    "layer_e_sha256",
)


# ---------------------------------------------------------------------------
# Atomic write helpers
# ---------------------------------------------------------------------------

def atomic_write_text(path: Path, content: str) -> None:
    """Write `content` to `path` atomically (tmp + rename). The
    tmp file is created in the destination's directory so the
    final rename is on the same volume (Windows-safe)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.tmp.", suffix=".part", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_copy(src: Path, dst: Path) -> None:
    """Atomically copy `src` to `dst` via a tmp file in `dst`'s
    directory. Verifies byte-identity before the rename."""
    if not src.exists():
        raise SystemExit(f"source file missing: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{dst.name}.tmp.", suffix=".part", dir=str(dst.parent)
    )
    os.close(fd)
    try:
        shutil.copyfile(src, tmp_name)
        if sha256_path(Path(tmp_name)) != sha256_path(src):
            raise SystemExit(
                f"promotion: byte-identity check failed when copying "
                f"{src} -> {dst}"
            )
        os.replace(tmp_name, dst)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Call-out to the strict CLI validator
# ---------------------------------------------------------------------------

def call_validator(run_dir: Path) -> int:
    """Invoke the strict validator (no partial-pilot) and return
    its exit code. Output is forwarded to stdout."""
    cmd = [sys.executable, str(VALIDATOR), "--run-dir", str(run_dir)]
    completed = subprocess.run(
        cmd, cwd=str(REPO), text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    sys.stdout.write(completed.stdout)
    sys.stdout.flush()
    return completed.returncode


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def check_mixed_run_id_and_model(run_dir: Path) -> tuple[bool, str]:
    """Refuse promotion if the run has mixed run_ids, mixed
    models, or mixed providers across its manifest and v2 rows.
    """
    manifest = run_dir / "manifest.jsonl"
    v2 = run_dir / "layer_d_v2.jsonl"
    if not manifest.exists() or not v2.exists():
        return (False, f"manifest or v2 missing in {run_dir}")
    run_ids: set[str] = set()
    models: set[str] = set()
    providers: set[str] = set()
    base_urls: set[str] = set()
    with manifest.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("status") == "ok":
                if r.get("run_id"):
                    run_ids.add(r["run_id"])
                if r.get("model"):
                    models.add(r["model"])
                if r.get("provider"):
                    providers.add(r["provider"])
                if r.get("base_url"):
                    base_urls.add(r["base_url"])
    with v2.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("run_id"):
                run_ids.add(r["run_id"])
            if r.get("model"):
                models.add(r["model"])
            if r.get("provider"):
                providers.add(r["provider"])
    if len(run_ids) > 1:
        return (False, f"mixed run_ids: {sorted(run_ids)}")
    if len(models) > 1:
        return (False, f"mixed models: {sorted(models)}")
    if len(providers) > 1:
        return (False, f"mixed providers: {sorted(providers)}")
    if len(base_urls) > 1:
        return (False, f"mixed base_urls: {sorted(base_urls)}")
    return (True, "ok")


def check_layer_a_b_c_unchanged(run_dir: Path) -> tuple[bool, str]:
    """Compare run_dir/run_config.json SHA-256 of Layer A/B/C
    against the on-disk Layer A/B/C. Refuse promotion on any
    drift."""
    cfg_path = run_dir / "run_config.json"
    if not cfg_path.exists():
        return (False, f"run_config.json missing in {run_dir}")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    if sha256_path(LAYER_A_PATH) != cfg.get("layer_a_sha256"):
        return (False, "Layer A SHA-256 drifted vs run_config.json")
    if sha256_path(LAYER_B_PATH) != cfg.get("layer_b_sha256"):
        return (False, "Layer B SHA-256 drifted vs run_config.json")
    if sha256_path(LAYER_C_PATH) != cfg.get("layer_c_sha256"):
        return (False, "Layer C SHA-256 drifted vs run_config.json")
    return (True, "ok")


def check_layer_e_pristine_via_run_config(run_dir: Path) -> tuple[bool, str]:
    """Compare run_dir/run_config.json's layer_e_sha256 against
    the on-disk Layer E. Refuse promotion on any drift. This is
    the FULL file hash, not just the per-record status counts,
    so it catches approved_text_en edits, decision changes,
    review_state transitions, notes edits, and any other byte
    change."""
    cfg_path = run_dir / "run_config.json"
    if not cfg_path.exists():
        return (False, f"run_config.json missing in {run_dir}")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    expected_layer_e_sha = cfg.get("layer_e_sha256")
    if not expected_layer_e_sha:
        return (
            False,
            "run_config.json has no layer_e_sha256 field; the run "
            "was created by a pre-third-iteration runner and cannot "
            "be promoted with the new byte-level Layer E lock. "
            "Either rebuild the run_dir with the current runner, or "
            "record a manual waiver (forbidden by default).",
        )
    return check_layer_e_pristine(LAYER_E_PATH, expected_layer_e_sha)


def check_run_config_drift(run_dir: Path) -> tuple[bool, str]:
    """If a run_config.json exists in run_dir, every locked
    field must be present. A partial run_config (e.g. one
    without layer_e_sha256) is rejected so the promoter cannot
    silently skip a field."""
    cfg_path = run_dir / "run_config.json"
    if not cfg_path.exists():
        return (False, f"run_config.json missing in {run_dir}")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    missing: list[str] = []
    for fld in RUN_CONFIG_LOCKED_FIELDS:
        if fld not in cfg:
            missing.append(fld)
    if missing:
        return (
            False,
            f"run_config.json is missing locked field(s): {missing}. "
            f"Re-create the run_dir with the current runner "
            f"(which records every locked field on first write).",
        )
    return (True, "ok")


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def is_already_promoted(run_dir: Path) -> bool:
    """Return True if the v2 file is byte-identical to the
    run_dir's layer_d_v2.jsonl AND the config active_path is
    the v2 file."""
    if not V2_FILLED.exists():
        return False
    run_v2 = run_dir / "layer_d_v2.jsonl"
    if not run_v2.exists():
        return False
    if sha256_path(V2_FILLED) != sha256_path(run_v2):
        return False
    if not LAYER_D_CONFIG.exists():
        return False
    cfg = json.loads(LAYER_D_CONFIG.read_text(encoding="utf-8"))
    active_rel = cfg.get("active_path", "")
    if not active_rel:
        return False
    active_path = (REPO / active_rel).resolve()
    return active_path == V2_FILLED.resolve()


def is_already_active_for_different_run(run_dir: Path) -> bool:
    """If the current config active_path points to a v2 file
    that does NOT come from `run_dir`, refuse the promotion
    (silent overwrite would be a security/correctness bug)."""
    if not LAYER_D_CONFIG.exists():
        return False
    cfg = json.loads(LAYER_D_CONFIG.read_text(encoding="utf-8"))
    active_rel = cfg.get("active_path", "")
    if not active_rel:
        return False
    active_path = (REPO / active_rel).resolve()
    if active_path != V2_FILLED.resolve():
        return False
    if not V2_FILLED.exists():
        return False
    # Compare V2 file SHA to the current run_dir's V2 file
    run_v2 = run_dir / "layer_d_v2.jsonl"
    if not run_v2.exists():
        return True
    return sha256_path(V2_FILLED) != sha256_path(run_v2)


# ---------------------------------------------------------------------------
# Config update
# ---------------------------------------------------------------------------

def update_config_active_path(
    run_dir: Path, run_v2_sha: str, manifest_sha: str,
) -> None:
    """Atomically update configs/estg150_layer_d.json so that
    `active_path` points at the v2 file, AND so that the
    activation metadata is recorded (run_id, model, provider,
    v2 sha, manifest sha, base_url). v1 placeholder_path is
    left intact.
    """
    cfg = json.loads(LAYER_D_CONFIG.read_text(encoding="utf-8"))
    run_cfg_path = run_dir / "run_config.json"
    run_cfg = json.loads(run_cfg_path.read_text(encoding="utf-8"))
    cfg["active_path"] = "data/development/human_review/estg_150_review_aids_zh_v2.jsonl"
    cfg["active_filled_path_status"] = "active"
    cfg["active_run_dir"] = str(run_dir)
    cfg["active_run_id"] = run_cfg.get("run_id", "")
    cfg["active_model"] = run_cfg.get("model", "")
    cfg["active_provider"] = run_cfg.get("provider", "")
    cfg["active_base_url"] = run_cfg.get("base_url", "")
    cfg["active_v2_sha256"] = run_v2_sha
    cfg["active_manifest_sha256"] = manifest_sha
    cfg["active_filled_path_status_note"] = (
        "v2 was activated by scripts/promote_layer_d_v2.py at " +
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) +
        " UTC. v1 placeholder provenance is preserved. The activation "
        "is atomic and reversible only by re-running the promoter with "
        "a different run_dir; manual edit of active_path is FORBIDDEN."
    )
    atomic_write_text(LAYER_D_CONFIG, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--run-dir", type=Path, required=True,
        help="Path to the run_dir produced by run_llm_zh_aid.py. "
             "Must contain layer_d_v2.jsonl, manifest.jsonl, "
             "run_config.json, run_summary.json.",
    )
    ap.add_argument(
        "--yes", action="store_true",
        help="Skip the confirmation prompt.",
    )
    args = ap.parse_args()

    run_dir = args.run_dir.resolve()
    if not run_dir.exists():
        print(f"ERROR: run_dir does not exist: {run_dir}", file=sys.stderr)
        return 2
    for required in ("layer_d_v2.jsonl", "manifest.jsonl",
                     "run_config.json", "run_summary.json"):
        if not (run_dir / required).exists():
            print(f"ERROR: {run_dir}/{required} missing", file=sys.stderr)
            return 2
    if not V1_PLACEHOLDER.exists():
        print(f"ERROR: v1 placeholder missing: {V1_PLACEHOLDER}", file=sys.stderr)
        return 2
    if not LAYER_D_CONFIG.exists():
        print(f"ERROR: layer D config missing: {LAYER_D_CONFIG}", file=sys.stderr)
        return 2

    # --- 1. Idempotency check (no pre-state snapshot needed) ---
    if is_already_promoted(run_dir):
        print(f"[idempotent] v2 is already active and byte-identical to "
              f"{run_dir}/layer_d_v2.jsonl")
        print(f"  v2 file: {V2_FILLED}")
        print(f"  config:  {LAYER_D_CONFIG}")
        return 0

    # --- 2. Cross-run guard: refuse to silently overwrite a
    #        different run's v2 file ---
    if is_already_active_for_different_run(run_dir):
        print(
            f"ERROR: configs/estg150_layer_d.json already points at a v2 "
            f"file that does NOT come from {run_dir}. The promoter does "
            f"not silently overwrite a different run's activation. To "
            f"re-activate a different run, first demote by re-running the "
            f"promoter on the current active run (which is idempotent) and "
            f"then explicitly run the new run's promoter with a one-time "
            f"--force-promote flag (NOT YET IMPLEMENTED).",
            file=sys.stderr,
        )
        return 2

    # --- 3. Pre-flight checks ---
    pre_flight: list[tuple[str, bool, str]] = []
    for name, fn in (
        ("mixed_run_id_and_model", check_mixed_run_id_and_model),
        ("layer_a_b_c_unchanged", check_layer_a_b_c_unchanged),
        ("layer_e_pristine_via_sha256", check_layer_e_pristine_via_run_config),
        ("run_config_drift", check_run_config_drift),
    ):
        ok, msg = fn(run_dir)
        pre_flight.append((name, ok, msg))
    for name, ok, msg in pre_flight:
        if not ok:
            print(f"ERROR: pre-flight check {name!r} failed: {msg}", file=sys.stderr)
            return 2
    print(f"[pre-flight] all {len(pre_flight)} checks passed")

    # --- 4. Strict validator (no partial) ---
    print(f"[validator] running strict validator on {run_dir} ...")
    rc = call_validator(run_dir)
    if rc != 0:
        print(
            f"ERROR: strict validator returned non-zero (rc={rc}); "
            f"refusing to promote.",
            file=sys.stderr,
        )
        return 2
    print(f"[validator] strict validator returned 0")

    # --- 5. Pre-state snapshot for transactional rollback ---
    v1_pre_sha = sha256_path(V1_PLACEHOLDER)  # v1 is never written; this is a guard
    pre_v2_existed = V2_FILLED.exists()
    pre_v2_bytes: bytes | None = (
        V2_FILLED.read_bytes() if pre_v2_existed else None
    )
    pre_v2_sha = sha256_path(V2_FILLED) if pre_v2_existed else None
    pre_config_text = LAYER_D_CONFIG.read_text(encoding="utf-8")
    pre_config_sha = sha256_text(pre_config_text)
    print(
        f"[snapshot] v1 sha={v1_pre_sha[:16]}..., "
        f"v2 existed={pre_v2_existed} sha={pre_v2_sha[:16] if pre_v2_sha else '<n/a>'}, "
        f"config sha={pre_config_sha[:16]}..."
    )

    # --- 6. Confirmation prompt ---
    if not args.yes:
        print()
        print(f"ABOUT TO PROMOTE:")
        print(f"  source: {run_dir}/layer_d_v2.jsonl")
        print(f"  target: {V2_FILLED}")
        print(f"  config: {LAYER_D_CONFIG} (active_path -> v2)")
        print(f"  v1 placeholder is preserved (sha256={v1_pre_sha[:16]}...).")
        try:
            ans = input("Type 'yes' to proceed: ")
        except (EOFError, KeyboardInterrupt):
            print("ERROR: confirmation aborted", file=sys.stderr)
            return 2
        if ans.strip() != "yes":
            print("ERROR: confirmation failed; nothing was changed", file=sys.stderr)
            return 2

    # --- 7. Atomic copy of layer_d_v2.jsonl -> v2 file ---
    try:
        atomic_copy(run_dir / "layer_d_v2.jsonl", V2_FILLED)
    except Exception as e:
        print(
            f"ERROR: copy failed: {e!r}; nothing was changed",
            file=sys.stderr,
        )
        return 2

    # --- 8. Atomic config update ---
    new_v2_sha = sha256_path(V2_FILLED)
    manifest_sha = sha256_path(run_dir / "manifest.jsonl")
    try:
        update_config_active_path(run_dir, new_v2_sha, manifest_sha)
    except Exception as e:
        # Transactional rollback: restore pre-state on both v2 and config.
        try:
            if pre_v2_existed and pre_v2_bytes is not None:
                atomic_write_text(
                    V2_FILLED, pre_v2_bytes.decode("utf-8", errors="replace")
                )
            else:
                if V2_FILLED.exists():
                    V2_FILLED.unlink()
        except OSError as rb_e:
            print(
                f"ERROR: config update failed AND rollback of v2 failed: "
                f"original={e!r}; rollback={rb_e!r}; manual intervention "
                f"required",
                file=sys.stderr,
            )
            return 2
        try:
            atomic_write_text(LAYER_D_CONFIG, pre_config_text)
        except OSError as rb_e:
            print(
                f"ERROR: config update failed AND rollback of config "
                f"failed: original={e!r}; rollback={rb_e!r}; manual "
                f"intervention required",
                file=sys.stderr,
            )
            return 2
        print(
            f"ERROR: config update failed: {e!r}; rolled back "
            f"(v2 and config restored to pre-promotion state)",
            file=sys.stderr,
        )
        return 2

    # --- 9. Post-condition: v1 placeholder is unchanged ---
    if sha256_path(V1_PLACEHOLDER) != v1_pre_sha:
        # This should be impossible (we never write v1), but the
        # check is cheap and gives a clear error if it ever
        # happens.
        print(
            f"ERROR: v1 placeholder SHA-256 changed unexpectedly "
            f"(pre={v1_pre_sha[:16]}..., post={sha256_path(V1_PLACEHOLDER)[:16]}...)",
            file=sys.stderr,
        )
        return 2

    # --- 10. Post-condition: v1 placeholder invariant ---
    ok, detail = check_v1_placeholder_unchanged(V2_FILLED, V1_PLACEHOLDER)
    if not ok:
        print(f"ERROR: v1 placeholder invariant violated: {detail}",
              file=sys.stderr)
        return 2

    # --- 11. Post-condition: config active_path is v2 ---
    post_cfg = json.loads(LAYER_D_CONFIG.read_text(encoding="utf-8"))
    if post_cfg.get("active_path") != "data/development/human_review/estg_150_review_aids_zh_v2.jsonl":
        print(
            f"ERROR: post-promotion active_path is not v2: "
            f"{post_cfg.get('active_path')!r}",
            file=sys.stderr,
        )
        return 2

    # --- 12. Post-condition: active_run_id in config matches run_dir ---
    if post_cfg.get("active_run_id") != json.loads((run_dir / "run_config.json").read_text(encoding="utf-8")).get("run_id"):
        print(
            f"ERROR: post-promotion active_run_id does not match run_dir's run_config.json",
            file=sys.stderr,
        )
        return 2

    print()
    print(f"[done] v2 promoted to: {V2_FILLED}")
    print(f"  v2 sha256: {sha256_path(V2_FILLED)[:16]}...")
    print(f"  config:    {LAYER_D_CONFIG} (active_path -> v2)")
    print(f"  v1 placeholder preserved (sha256={sha256_path(V1_PLACEHOLDER)[:16]}...)")
    print()
    print("Next: re-run `python scripts/audit_project.py` to confirm "
          "the new `review_aids_zh_v2_active` pass; re-load the GUI "
          "via the in-app '重新加载中文辅助' button; do NOT edit Layer E "
          "manually — the review tool will write to it as you go.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
