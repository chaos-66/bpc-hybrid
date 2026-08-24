# -*- coding: utf-8 -*-
"""Offline builder for a future S2.12 authorization event (ZERO API).

This tool NEVER creates a real authorization event on its own: it requires
the user's authorization sentence verbatim (as a CLI argument or stdin),
refuses to run without it, defaults to a dry run that prints the event
draft, and only ``--apply`` writes the files — and apply is NOT allowed in
this round (no real user sentence is present).  It never reads ``.env`` or
API keys, never calls the network, and never touches Gold.

Files produced after a future real ``--apply`` (paths are fixed, no angle
brackets):

* ``configs/s2_12_api_authorization_<STAGE>.json`` — machine JSON (schema
  ``s2_12_api_authorization@1.1.0``)
* ``configs/s2_12_api_authorization_event_<STAGE>.json`` — user-sentence
  event file (sentence + UTF-8 SHA-256 + event file SHA-256 + timestamp)

The sentence hash and the event-file hash both go into the machine auth
JSON; runners verify them before any transport call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.s2_12_execution import (  # noqa: E402
    EXPECTED_INPUT_SHA,
    PREFLIGHT_LOCK,
    PREFLIGHT_REPORT,
    REQUIRED_MODEL,
    S212ExecutionError,
    _sha,
    load_lock,
    load_report,
    rebuild_and_verify_payloads,
)
from bpc_hybrid.s2_12_execution import stage_ordinals  # noqa: E402

STAGES = ("D-CAL", "D-REST", "F-1", "F-2", "F-3")

# Fixed output paths (no placeholders after real apply).
EVENT_DIR = ROOT / "configs"


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _runner_hash_for(script: str) -> str:
    return _sha(ROOT / "scripts" / script)


def build_draft(
    stage_id: str,
    sentence: str,
    runtime_home: Path,
    *,
    allowed_windows: str = "off_peak_only",
    global_input_token_cap: int = 63_000_000,
    global_output_token_cap: int = 258_048,
    global_usd_cost_cap: float = 84.18,
    price: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build (machine_auth, event_file) for one pre-registered stage.

    Raises if the sentence is empty; every hash is computed from the actual
    locked assets.
    """
    if not sentence or not sentence.strip():
        raise S212ExecutionError(
            "a real user authorization sentence is required (verbatim)"
        )
    lock = load_lock()
    report = load_report()
    rows_by_arm = rebuild_and_verify_payloads(lock, report, runtime_home)

    if stage_id in ("D-CAL", "D-REST"):
        arm = "direct_llm"
        runner_script = "run_s2_12_direct_llm_v1.py"
    else:
        arm = "sun_llm_fallback"
        runner_script = "run_s2_12_sun_llm_fallback_v1.py"

    ordinals = stage_ordinals(arm, stage_id)
    by_ordinal = {int(row["call_index"]): row for row in rows_by_arm[arm]}
    stage_rows = [by_ordinal[o] for o in ordinals]
    stage_hashes = [row["request_body_sha256"] for row in stage_rows]
    final_63 = [
        row["request_body_sha256"]
        for arm_name in ("direct_llm", "sun_llm_fallback")
        for row in rows_by_arm[arm_name]
    ]

    spent = {
        "schema_version": "s2_12_price_snapshot@1.0.0",
        "currency": "USD",
        "input_cache_hit_per_million": 0.044,
        "input_cache_miss_per_million": 1.32,
        "output_per_million": 3.96,
    }
    if price is not None:
        spent.update(price)

    sentence_hash = _sha_text(sentence)
    event = {
        "schema_version": "s2_12_authorization_event@1.0.0",
        "authorization_sentence": sentence,
        "authorization_sentence_utf8_sha256": sentence_hash,
        "model": REQUIRED_MODEL,
        "stage_id": stage_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "not_a_synthetic_fixture": True,
    }
    event_bytes = (json.dumps(event, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    event_hash = hashlib.sha256(event_bytes).hexdigest()

    auth = {
        "schema_version": "s2_12_api_authorization@1.1.0",
        "authorization_sentence_utf8_sha256": sentence_hash,
        "authorization_event_file": (
            f"configs/s2_12_api_authorization_event_{stage_id}.json"
        ),
        "authorization_event_file_sha256": event_hash,
        "model": REQUIRED_MODEL,
        "calls": {"direct_llm": 36, "sun_llm_fallback": 27},
        "stage_id": stage_id,
        "stage_payload_hashes": stage_hashes,
        "stage_call_cap": len(stage_hashes),
        "global_input_token_cap": global_input_token_cap,
        "global_output_token_cap": global_output_token_cap,
        "global_usd_cost_cap": global_usd_cost_cap,
        "allowed_windows": allowed_windows,
        "price_snapshot": spent,
        "price_checked_at_utc": "2026-08-22T00:00:00Z",
        "runner_implementation_hashes": {
            "run_s2_12_direct_llm_v1": _runner_hash_for(
                "run_s2_12_direct_llm_v1.py"),
            "run_s2_12_sun_llm_fallback_v1": _runner_hash_for(
                "run_s2_12_sun_llm_fallback_v1.py"),
            "s2_12_execution": _sha(ROOT / "src/bpc_hybrid/s2_12_execution.py"),
            "llm_client": _sha(ROOT / "src/bpc_hybrid/llm_client.py"),
            "h1_transport": _sha(ROOT / "src/bpc_hybrid/h1_transport.py"),
        },
        "input_config_prompt_hashes": {
            "input_sha256": EXPECTED_INPUT_SHA,
            "lock_sha256": _sha(PREFLIGHT_LOCK),
            "prompt_direct_sha256": lock["arms"]["direct_llm"]["prompt_sha256"],
            "prompt_fallback_sha256": lock["arms"]["sun_llm_fallback"]["prompt_sha256"],
        },
        "prev_stage_ledger_hash": "",
        "final_63_payload_hashes": final_63,
        "retry": 0,
        "gold_isolation": {
            "api_arms_must_not_read_gold": True,
            "evaluation_only_after_predictions_are_locked": True,
        },
    }
    return auth, event


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-home", type=Path,
        default=Path("D:/environment/stanford-corenlp-4.5.10"),
    )
    parser.add_argument("--stage-id", choices=STAGES, required=True)
    parser.add_argument(
        "--sentence", type=str, default=None,
        help="The user's authorization sentence VERBATIM. Required; without "
             "it the tool refuses to build anything (no synthetic sentence "
             "is ever accepted as a real authorization).",
    )
    parser.add_argument("--allowed-windows", choices=("any_time", "off_peak_only"),
                        default="off_peak_only")
    parser.add_argument("--usd-cap", type=float, default=84.18)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="Print the drafts and hashes only (default intent).")
    mode.add_argument("--apply", action="store_true",
                      help="Write the event + auth files. Forbidden this "
                           "round unless the user supplies a real sentence.")
    args = parser.parse_args()

    if args.stage_id in ("D-CAL", "D-REST") and args.allowed_windows != "off_peak_only":
        print("D-CAL is off-peak-only by stage contract; refusing any_time.")
        return 2
    if args.sentence and "D-CAL" == args.stage_id and args.usd_cap > 1.00:
        print("D-CAL USD cap must be <= 1.00 (calibration contract).")
        return 2

    try:
        auth, event = build_draft(
            args.stage_id, args.sentence or "", args.runtime_home,
            allowed_windows=args.allowed_windows,
            global_usd_cost_cap=args.usd_cap,
        )
    except S212ExecutionError as exc:
        print(f"S2.12 auth-event builder refused: {exc}")
        return 2

    auth_path = EVENT_DIR / f"s2_12_api_authorization_{args.stage_id}.json"
    event_path = EVENT_DIR / f"s2_12_api_authorization_event_{args.stage_id}.json"

    if args.dry_run:
        print("=== DRY RUN (no files written, no authorization created) ===")
        print(f"stage={args.stage_id} stage_call_cap={auth['stage_call_cap']}")
        print(f"sentence_sha256={auth['authorization_sentence_utf8_sha256']}")
        print(f"event_file={event_path.name} event_sha256="
              f"{auth['authorization_event_file_sha256']}")
        print(f"stage_payload_count={len(auth['stage_payload_hashes'])}")
        print(f"price_snapshot={json.dumps(auth['price_snapshot'])}")
        print("auth draft would be written to:", auth_path)
        print("event draft would be written to:", event_path)
        print("No authorization created; API remains NOT AUTHORIZED.")
        return 0

    # --apply path: only meaningful with a real user sentence in this round.
    if not args.sentence or not args.sentence.strip():
        print("Refusing --apply without a real user authorization sentence.")
        return 2
    if args.sentence.lower().startswith("synthetic"):
        print("Refusing --apply: synthetic sentences are not real authorization.")
        return 2
    for path in (auth_path, event_path):
        if path.exists():
            print(f"Refusing to overwrite: {path}")
            return 2
    event_path.write_bytes((json.dumps(event, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    auth_path.write_bytes((json.dumps(auth, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"Wrote {event_path}")
    print(f"Wrote {auth_path}")
    print("NOTE: real authorization event created — user-sentence bound.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())