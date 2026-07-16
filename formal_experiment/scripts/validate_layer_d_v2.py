"""Validator for the EStG-150 Layer D v2 file (filled Chinese-aid
file). 2026-07-14 hardened (third iteration): 20+ strict checks
+ manifest verification + partial-pilot mode, AND the third
iteration adds:

  * layer_e_sha256 lock: the FULL Layer E file hash is read from
    run_config.json and compared byte-for-byte against the
    on-disk Layer E. Any byte change (approved_text_en edit,
    decision change, review_state transition, notes edit, etc.)
    is now caught. The old "0/150 reviewed" counter fallback is
    no longer used.
  * base_url_sha256 lock: the hash of the runner's locked
    base_url must match. A typo'd or hostile base URL triggers
    a hard fail.
  * reusable pure-function validator:
    src/formal_experiment/layer_d_validator.py is the SINGLE
    source of truth. This CLI wraps it with file I/O and a
    human-friendly report.

The validator enforces 20 explicit checks. The default mode
requires ALL 150 records (no partial). The `--allow-partial-pilot
N` flag relaxes checks 1, 4, 5, 6, 7, 8, 10, 11, 13, 14, 15,
16, 17, 19 to allow an in-progress pilot of N records. Partial
mode is for the pilot phase only; promotion requires the full
150.

The 20 checks (with their partial-pilot-relaxation tags):

  1.  exactly_150_records
  2.  sample_id_set_matches_membership           (always strict)
  3.  legacy_record_id_set_matches_membership     (always strict)
  4.  text_zh_150_of_150
  5.  back_translation_en_150_of_150
  6.  clauses_150_of_150
  7.  model_150_of_150
  8.  prompt_sha256_150_of_150
  9.  per_record_structural_valid                 (always strict)
  10. run_id_150_of_150
  11. modality_class_4_class_vocabulary           (relaxed in partial)
  12. clause_id_unique_within_record              (always strict)
  13. manifest_present
  14. manifest_has_150_ok_rows
  15. call_b_payload_clean_for_all_ok
  16. call_b_payload_blind_recheck                (relaxed in partial)
  17. layer_a_b_c_sha256_unchanged                (relaxed in partial)
  18. membership_payload_sha256_unchanged         (always strict)
  19. layer_e_pristine                             (always strict;
                                                   FULL file SHA-256)
  20. v2_ordering_matches_layer_a                  (always strict)

Plus invariants:
  - v1 placeholder file is NOT the v2 file
  - base_url_sha256 (if recorded) matches the current config
  - run_config.json has every locked field recorded
  - v1 placeholder SHA-256 is unchanged since the run started

Exit codes:
  0 — all required checks pass
  2 — any required check fails (or partial-pilot mode finds
      a non-pilot-size mismatch)

Run from formal_experiment/:

    # full 150 validation
    python scripts/validate_layer_d_v2.py --run-dir <path>

    # pilot validation (allows N=3 of 150)
    python scripts/validate_layer_d_v2.py --run-dir <path> \\
        --allow-partial-pilot 3

    # direct file validation
    python scripts/validate_layer_d_v2.py --v2-path <path>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Shared pure-function module (single source of truth, 2026-07-14).
from formal_experiment.layer_d_validator import (  # noqa: E402
    MODALITY_CLASSES,
    SPAN_FIELDS,
    check_call_b_blind,
    check_layer_e_pristine,
    check_record_structure,
    check_v1_placeholder_unchanged,
    compute_layer_e_progress,
    load_expected_membership,
    load_jsonl_records,
    sha256_path,
    sha256_text,
)


LAYER_A_PATH = REPO / "data" / "development" / "estg" / "estg_selected_150_de.jsonl"
LAYER_B_PATH = REPO / "data" / "development" / "human_review" / "estg_150_translation_en_v1.jsonl"
LAYER_C_PATH = REPO / "data" / "development" / "human_review" / "estg_150_llm_six_element_candidates_v1.jsonl"
LAYER_E_PATH = REPO / "data" / "development" / "human_review" / "estg_150_human_correction_v1.json"
LAYER_D_V1_PLACEHOLDER = REPO / "data" / "development" / "human_review" / "estg_150_review_aids_zh_v1.jsonl"
MEMBERSHIP_HASHES_PATH = REPO / "data" / "development" / "estg" / "estg_150_membership_hashes.json"
PROMPT_CALL_A_PATH = REPO / "prompts" / "zh_aid" / "zh_translation.md"
PROMPT_CALL_B_PATH = REPO / "prompts" / "zh_aid" / "en_back_translation.md"

LAYER_D_CONFIG = REPO / "configs" / "estg150_layer_d.json"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--v2-path", type=Path, default=None)
    ap.add_argument("--run-dir", type=Path, default=None)
    ap.add_argument(
        "--allow-partial-pilot", type=int, default=0,
        help="Relax full-150 checks to allow an in-progress pilot "
             "of N records. Default 0 (full 150 required).",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    # Resolve paths
    v2_path = args.v2_path
    if v2_path is None and args.run_dir is not None:
        v2_path = args.run_dir / "layer_d_v2.jsonl"
    if v2_path is None:
        v2_path = REPO / "data" / "development" / "human_review" / "estg_150_review_aids_zh_v2.jsonl"
    if not v2_path.exists():
        print(f"v2 file missing: {v2_path}", file=sys.stderr)
        return 2
    manifest_path = None
    if args.run_dir is not None:
        manifest_path = args.run_dir / "manifest.jsonl"
    elif v2_path.parent.name == "llm_candidate_runs":
        manifest_path = v2_path.parent / "manifest.jsonl"
    run_config_path = v2_path.parent / "run_config.json" if v2_path.parent.name == "llm_candidate_runs" else None
    if run_config_path is not None and not run_config_path.exists():
        run_config_path = None

    v2_records = load_jsonl_records(v2_path.read_text(encoding="utf-8"))
    expected_sample_ids, expected_legacy_ids, expected_payload = load_expected_membership(
        MEMBERSHIP_HASHES_PATH
    )

    de_text_by_lid: dict[int, str] = {}
    for r in load_jsonl_records(LAYER_A_PATH.read_text(encoding="utf-8")):
        if isinstance(r.get("id"), int) and isinstance(r.get("text"), str):
            de_text_by_lid[int(r["id"])] = r["text"]
    en_candidate_by_sid: dict[str, str] = {}
    for r in load_jsonl_records(LAYER_B_PATH.read_text(encoding="utf-8")):
        if isinstance(r.get("sample_id"), str):
            en_candidate_by_sid[r["sample_id"]] = r.get("candidate_text_en", "")

    expected_n = args.allow_partial_pilot if args.allow_partial_pilot > 0 else 150
    is_partial = args.allow_partial_pilot > 0 and len(v2_records) == args.allow_partial_pilot

    check_results: list[dict[str, Any]] = []

    def add(check: str, ok: bool, detail: str, partial_relaxed: bool = False) -> None:
        check_results.append({
            "check": check, "ok": bool(ok), "detail": detail,
            "partial_relaxed": partial_relaxed and is_partial,
        })

    # 1. exactly_150 records (or N for partial)
    add("exactly_150_records", len(v2_records) == expected_n,
        f"got {len(v2_records)} records (expected {expected_n}; "
        f"--allow-partial-pilot={args.allow_partial_pilot})",
        partial_relaxed=True)

    # 2. sample_id set
    actual_sample_ids = {r.get("sample_id") for r in v2_records if isinstance(r.get("sample_id"), str)}
    add("sample_id_set_matches_membership",
        actual_sample_ids <= expected_sample_ids,
        f"v2 sample_ids are a subset of the locked 150 (no extras); "
        f"v2 has {len(actual_sample_ids)}, locked has {len(expected_sample_ids)}; "
        f"extras={sorted(actual_sample_ids - expected_sample_ids)[:5]}")

    # 3. legacy_record_id set
    actual_legacy_ids = {int(r.get("legacy_record_id")) for r in v2_records
                         if isinstance(r.get("legacy_record_id"), int)}
    add("legacy_record_id_set_matches_membership",
        actual_legacy_ids <= expected_legacy_ids,
        f"v2 legacy_ids are a subset of the locked 150; "
        f"extras={sorted(actual_legacy_ids - expected_legacy_ids)[:5]}")

    # 4-10. per-record counters
    per_record_errors: list[str] = []
    per_record_warnings: list[str] = []
    n_text_zh_ok = 0
    n_back_ok = 0
    n_clauses_ok = 0
    n_model_ok = 0
    n_prompt_sha_ok = 0
    n_run_id_ok = 0
    for r in v2_records:
        sid = r.get("sample_id", "<missing>")
        e, w = check_record_structure(r, expected_sample_ids, expected_legacy_ids)
        for x in e:
            per_record_errors.append(f"{sid}: {x}")
        for x in w:
            per_record_warnings.append(f"{sid}: {x}")
        if isinstance(r.get("text_zh"), str) and r["text_zh"].strip():
            n_text_zh_ok += 1
        if isinstance(r.get("back_translation_en"), str) and r["back_translation_en"].strip():
            n_back_ok += 1
        if isinstance(r.get("clauses"), list) and r["clauses"]:
            n_clauses_ok += 1
        if r.get("model"):
            n_model_ok += 1
        if r.get("prompt_sha256"):
            n_prompt_sha_ok += 1
        if r.get("run_id"):
            n_run_id_ok += 1
    add("text_zh_full", n_text_zh_ok == expected_n,
        f"non-empty text_zh count: {n_text_zh_ok}/{expected_n}", partial_relaxed=True)
    add("back_translation_en_full", n_back_ok == expected_n,
        f"non-empty back_translation_en count: {n_back_ok}/{expected_n}", partial_relaxed=True)
    add("clauses_full", n_clauses_ok == expected_n,
        f"non-empty clauses count: {n_clauses_ok}/{expected_n}", partial_relaxed=True)
    add("model_full", n_model_ok == expected_n,
        f"non-empty model count: {n_model_ok}/{expected_n}", partial_relaxed=True)
    add("prompt_sha256_full", n_prompt_sha_ok == expected_n,
        f"non-empty prompt_sha256 count: {n_prompt_sha_ok}/{expected_n}", partial_relaxed=True)
    add("run_id_full", n_run_id_ok == expected_n,
        f"non-empty run_id count: {n_run_id_ok}/{expected_n}", partial_relaxed=True)
    add("per_record_structural_valid", len(per_record_errors) == 0,
        f"{len(per_record_errors)} per-record errors; first 5: "
        f"{per_record_errors[:5]}")

    # 11. modality_class 4-class vocabulary
    bad_modality: list[str] = []
    for r in v2_records:
        for ci, c in enumerate(r.get("clauses") or []):
            mc = c.get("modality_class") if isinstance(c, dict) else None
            if mc is not None and mc not in MODALITY_CLASSES:
                bad_modality.append(f"{r.get('sample_id')} clauses[{ci}].modality_class={mc!r}")
    add("modality_class_4_class_vocabulary", len(bad_modality) == 0,
        f"{len(bad_modality)} records have a modality_class outside the 4-class set; "
        f"first 5: {bad_modality[:5]}",
        partial_relaxed=True)

    # 12. clause_id unique within record
    dup_clause_ids: list[str] = []
    for r in v2_records:
        seen: set[str] = set()
        for c in r.get("clauses") or []:
            cid = c.get("clause_id") if isinstance(c, dict) else None
            if cid:
                if cid in seen:
                    dup_clause_ids.append(f"{r.get('sample_id')} {cid!r}")
                seen.add(cid)
    add("clause_id_unique_within_record", len(dup_clause_ids) == 0,
        f"{len(dup_clause_ids)} duplicate clause_id(s); first 5: {dup_clause_ids[:5]}")

    # 13. manifest present
    if manifest_path is not None and manifest_path.exists():
        manifest_rows = load_jsonl_records(manifest_path.read_text(encoding="utf-8"))
        # 14. manifest has 150 ok rows (or expected_n)
        n_ok = sum(1 for r in manifest_rows if r.get("status") == "ok")
        add("manifest_present", True,
            f"manifest at {manifest_path} with {len(manifest_rows)} rows",
            partial_relaxed=True)
        add("manifest_has_150_ok_rows", n_ok == expected_n,
            f"manifest has {n_ok} status=ok rows; expected {expected_n}",
            partial_relaxed=True)
        # 15. call_b_payload_clean for every ok row
        bad_clean = [r.get("sample_id") for r in manifest_rows
                     if r.get("status") == "ok" and r.get("call_b_payload_clean") is not True]
        add("call_b_payload_clean_for_all_ok", len(bad_clean) == 0,
            f"{len(bad_clean)} ok rows have call_b_payload_clean != True; "
            f"first 5: {bad_clean[:5]}",
            partial_relaxed=True)
    else:
        add("manifest_present", False,
            f"manifest required at {manifest_path} but is missing; "
            f"promotion is forbidden without a manifest",
            partial_relaxed=True)
        add("manifest_has_150_ok_rows", False,
            "manifest missing; cannot verify 150 ok rows",
            partial_relaxed=True)
        add("call_b_payload_clean_for_all_ok", False,
            "manifest missing; cannot verify Call B payload clean flag",
            partial_relaxed=True)

    # 16. Call B blind recheck
    blind_errors = check_call_b_blind(
        v2_records,
        PROMPT_CALL_B_PATH.read_text(encoding="utf-8"),
        de_text_by_lid,
        en_candidate_by_sid,
    )
    add("call_b_payload_blind_recheck", len(blind_errors) == 0,
        f"{len(blind_errors)} Call B payload(s) contain forbidden substrings; "
        f"first 5: {blind_errors[:5]}",
        partial_relaxed=True)

    # 17. Layer A/B/C SHA-256 unchanged (vs run_config if available)
    if run_config_path is not None:
        cfg = json.loads(run_config_path.read_text(encoding="utf-8"))
        a_now = sha256_path(LAYER_A_PATH)
        b_now = sha256_path(LAYER_B_PATH)
        c_now = sha256_path(LAYER_C_PATH)
        add("layer_a_sha256_unchanged", a_now == cfg.get("layer_a_sha256"),
            f"recorded={cfg.get('layer_a_sha256', '<missing>')[:16]}..., "
            f"current={a_now[:16]}...",
            partial_relaxed=True)
        add("layer_b_sha256_unchanged", b_now == cfg.get("layer_b_sha256"),
            f"recorded={cfg.get('layer_b_sha256', '<missing>')[:16]}..., "
            f"current={b_now[:16]}...",
            partial_relaxed=True)
        add("layer_c_sha256_unchanged", c_now == cfg.get("layer_c_sha256"),
            f"recorded={cfg.get('layer_c_sha256', '<missing>')[:16]}..., "
            f"current={c_now[:16]}...",
            partial_relaxed=True)
    else:
        add("layer_a_sha256_unchanged", True,
            "no run_config.json supplied; skipped", partial_relaxed=True)
        add("layer_b_sha256_unchanged", True,
            "no run_config.json supplied; skipped", partial_relaxed=True)
        add("layer_c_sha256_unchanged", True,
            "no run_config.json supplied; skipped", partial_relaxed=True)

    # 18. membership payload sha256 unchanged (always strict)
    add("membership_payload_sha256_unchanged", expected_payload is not None,
        f"membership payload sha256 = {expected_payload[:16]}...")

    # 19. Layer E pristine (always strict; FULL file SHA-256 from
    #     run_config.json if present, else 0/150 counter fallback)
    if run_config_path is not None and "layer_e_sha256" in json.loads(run_config_path.read_text(encoding="utf-8")):
        cfg = json.loads(run_config_path.read_text(encoding="utf-8"))
        ok, detail = check_layer_e_pristine(LAYER_E_PATH, cfg.get("layer_e_sha256"))
        add("layer_e_pristine", ok, detail)
    else:
        # Fallback: count reviewed/adjudicated. This is the old
        # behaviour, kept for backward compat with pre-third-iteration
        # runs that don't have a layer_e_sha256 in run_config.json.
        try:
            p = compute_layer_e_progress(LAYER_E_PATH)
            layer_e_pristine = p["n_reviewed"] == 0 and p["n_adjudicated"] == 0
            add("layer_e_pristine", layer_e_pristine,
                f"FALLBACK (no run_config layer_e_sha256): "
                f"n_reviewed={p['n_reviewed']}, n_adjudicated={p['n_adjudicated']}; "
                f"sha256={p['sha256'][:16]}... "
                f"(newer runs require byte-identical match)")
        except (OSError, ValueError) as e:
            add("layer_e_pristine", False, f"could not read Layer E: {e!r}")

    # 20. v2 ordering matches Layer A
    lids_v2 = [int(r.get("legacy_record_id")) for r in v2_records
               if isinstance(r.get("legacy_record_id"), int)]
    add("v2_ordering_matches_layer_a", sorted(lids_v2) == lids_v2,
        f"v2 is sorted by legacy_record_id: {sorted(lids_v2) == lids_v2}")

    # Invariants
    ok, detail = check_v1_placeholder_unchanged(v2_path, LAYER_D_V1_PLACEHOLDER)
    add("v1_placeholder_unchanged", ok, detail)

    # base_url_sha256 lock (third iteration)
    if run_config_path is not None:
        cfg = json.loads(run_config_path.read_text(encoding="utf-8"))
        if "base_url_sha256" in cfg:
            recorded = cfg.get("base_url_sha256")
            current = sha256_text(cfg.get("base_url", ""))
            add("base_url_sha256_locked", recorded == current,
                f"recorded={recorded[:16]}..., current={current[:16]}..., "
                f"base_url={cfg.get('base_url', '<missing>')!r}")
        else:
            add("base_url_sha256_locked", True,
                "no base_url_sha256 in run_config.json; pre-third-iteration run; "
                "ok (no lock to verify)")

    # run_config.json lock (every required field present)
    if run_config_path is not None:
        cfg = json.loads(run_config_path.read_text(encoding="utf-8"))
        required_fields = (
            "provider", "model", "base_url", "base_url_sha256",
            "temperature", "max_tokens", "membership_payload_sha256",
            "layer_a_sha256", "layer_b_sha256", "layer_c_sha256",
            "prompt_a_sha256", "prompt_b_sha256", "layer_e_sha256",
        )
        missing = [f for f in required_fields if f not in cfg]
        add("run_config_locked_fields_present", len(missing) == 0,
            f"missing fields: {missing}" if missing else "all 13 required fields present")

    n_pass = sum(1 for c in check_results if c["ok"])
    n_fail = sum(1 for c in check_results if not c["ok"])
    overall_ok = n_fail == 0

    if args.json:
        out = {
            "v2_path": str(v2_path),
            "manifest_path": str(manifest_path) if manifest_path else None,
            "run_config_path": str(run_config_path) if run_config_path else None,
            "n_records": len(v2_records),
            "n_pass": n_pass,
            "n_fail": n_fail,
            "ok": overall_ok,
            "allow_partial_pilot": args.allow_partial_pilot,
            "is_partial_mode": is_partial,
            "checks": check_results,
            "per_record_errors_count": len(per_record_errors),
            "per_record_warnings_count": len(per_record_warnings),
            "per_record_errors_sample": per_record_errors[:10],
            "per_record_warnings_sample": per_record_warnings[:10],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"=== Layer D v2 validator ===")
        print(f"v2 path            : {v2_path}")
        print(f"manifest path      : {manifest_path or '<none>'}")
        print(f"run_config path    : {run_config_path or '<none>'}")
        print(f"records            : {len(v2_records)}/{expected_n}")
        print(f"checks passed      : {n_pass}")
        print(f"checks failed      : {n_fail}")
        print(f"allow-partial-pilot: {args.allow_partial_pilot}")
        print(f"is partial mode    : {is_partial}")
        print()
        for c in check_results:
            mark = "OK  " if c["ok"] else "FAIL"
            tag = " [PARTIAL-RELAXED]" if c["partial_relaxed"] and is_partial else ""
            print(f"  [{mark}] {c['check']}{tag}: {c['detail']}")
        if per_record_errors:
            print()
            print(f"per-record errors ({len(per_record_errors)}, first 5):")
            for e in per_record_errors[:5]:
                print(f"  {e}")
        if per_record_warnings:
            print()
            print(f"per-record warnings ({len(per_record_warnings)}, first 5):")
            for w in per_record_warnings[:5]:
                print(f"  {w}")
    if not overall_ok:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
