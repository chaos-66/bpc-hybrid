# -*- coding: utf-8 -*-
"""Offline builder for the GDPR Direct-LLM 74-call authorization event.

This tool NEVER creates a real authorization event on its own: it requires the
user's authorization sentence verbatim (CLI argument), refuses to run without
it, defaults to a dry run that prints the event draft, and only ``--apply``
writes the file.  It never reads ``.env`` or API keys, never calls the
network, and never touches Gold.

File produced after a future real ``--apply`` (fixed path):

* ``configs/gdpr7_direct_llm_authorization_event_v1.json`` — user-sentence
  authorization event (schema ``gdpr7_direct_llm_authorization_event@1.0.0``,
  scope ``gdpr7_direct_llm_v1:74``, off-peak-only price snapshot, caps equal
  to the executor in-code hard limits, hash_set bound to current disk state
  plus the execution-contract file SHA).

The executor (``run_gdpr7_direct_llm_v1.py``) validates every field of this
event before the first send; missing/mismatched fields hard-refuse.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# Reuse the exact constants, schema identities and validation helpers of the
# executor so the generated event can never drift from the run contract.
from run_gdpr7_direct_llm_v1 import (  # noqa: E402
    AUTHORIZATION_EVENT_SCHEMA,
    AUTHORIZATION_SCOPE,
    EXPECTED_SENTENCE_COUNT,
    INPUT_TOKEN_CAP,
    MAX_CALLS,
    MAX_OUTPUT_TOKENS_PER_CALL,
    OUTPUT_TOKEN_TOTAL_CAP,
    PRICE_SNAPSHOT_SCHEMA,
    PUBLISHED_ALIAS,
    REQUIRED_MODEL,
    USD_CAP_OFF_PEAK,
    _current_bindings,
    _sha,
    _sha_text,
    price_snapshot,
)

DEFAULT_CONTRACT = ROOT / "configs/ablations/gdpr7_direct_llm_execution_contract_v1.json"
DEFAULT_REPORT = ROOT / "outputs/reports/gdpr7_direct_llm_preflight_v1.json"
EVENT_PATH = ROOT / "configs/gdpr7_direct_llm_authorization_event_v1.json"


class Gdpr7AuthBuilderError(ValueError):
    """Fail-closed authorization-event builder error."""


def build_event(
    *,
    sentence: str,
    contract_path: Path,
    report_path: Path,
    official_price_reverified_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build the authorization event draft (no writes).

    Raises when the sentence is empty or when the current disk state cannot
    be bound (report missing / contract missing).
    """
    if not sentence or not sentence.strip():
        raise Gdpr7AuthBuilderError(
            "a real user authorization sentence is required (verbatim)"
        )
    contract_path = Path(contract_path)
    report_path = Path(report_path)
    if not contract_path.is_file():
        raise Gdpr7AuthBuilderError(f"execution contract not found: {contract_path}")
    if not report_path.is_file():
        raise Gdpr7AuthBuilderError(f"preflight report not found: {report_path}")

    hash_set = dict(_current_bindings(report_path))
    hash_set["contract_sha256"] = _sha(contract_path)

    reverified = official_price_reverified_at_utc or (
        datetime.now(timezone.utc).isoformat()
    )
    event = {
        "schema_version": AUTHORIZATION_EVENT_SCHEMA,
        "scope": AUTHORIZATION_SCOPE,
        "authorization_sentence": sentence,
        "authorization_sentence_utf8_sha256": _sha_text(sentence),
        "model": REQUIRED_MODEL,
        "published_alias": PUBLISHED_ALIAS,
        "calls": EXPECTED_SENTENCE_COUNT,
        "retry": 0,
        "allowed_windows": "off_peak_only",
        "price_snapshot": price_snapshot(off_peak=True),
        "official_price_reverified_at_utc": reverified,
        "caps": {
            "max_calls": MAX_CALLS,
            "global_input_token_cap": INPUT_TOKEN_CAP,
            "global_output_token_cap": OUTPUT_TOKEN_TOTAL_CAP,
            "max_output_tokens_per_call": MAX_OUTPUT_TOKENS_PER_CALL,
            "global_usd_cost_cap": USD_CAP_OFF_PEAK,
        },
        "hash_set": hash_set,
        "gold_isolation": {
            "api_arms_must_not_read_gold": True,
            "evaluation_only_after_predictions_are_locked": True,
        },
        "statement": (
            "User-authorized GDPR Stage-2->Stage-3 linkage Direct-LLM arm "
            "(scope gdpr7_direct_llm_v1:74): 74 real deepseek-v4-pro calls, "
            "one per approved_text_en sentence of "
            "data/input/gdpr7_stage2_input_v1.json, retry=0, off-peak only "
            "(Beijing 09:00-12:00 / 14:00-18:00 weekday peaks checked before "
            "every call); input limited to the 74 locked request bodies of "
            "outputs/reports/gdpr7_direct_llm_preflight_v1.json; global input "
            "<=74,000,000, output <=303,104 (per call <=4,096), USD <=1.31 "
            "(off-peak planning price + 20% margin; never above 2.61); "
            "official prices re-verified before the run; in-doubt entries are "
            "never auto-resent; partial runs keep their ledgers; no .env read, "
            "no Oracle."
        ),
    }
    return event


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sentence", type=str, default=None,
        help="The user's authorization sentence VERBATIM. Required; without "
             "it the tool refuses to build anything.",
    )
    parser.add_argument(
        "--contract-file", type=Path, default=DEFAULT_CONTRACT,
        help="Path to the locked GDPR execution contract.",
    )
    parser.add_argument(
        "--report-file", type=Path, default=DEFAULT_REPORT,
        help="Path to the locked preflight report.",
    )
    parser.add_argument(
        "--official-price-reverified-at-utc", type=str, default=None,
        help="ISO-8601 UTC timestamp of the official-price re-verification "
             "(default: now).",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="Print the draft and hashes only (default intent).")
    mode.add_argument("--apply", action="store_true",
                      help="Write the event file. Refuses when the fixed path "
                           "already exists or the sentence looks synthetic.")
    args = parser.parse_args()

    try:
        event = build_event(
            sentence=args.sentence or "",
            contract_path=args.contract_file,
            report_path=args.report_file,
            official_price_reverified_at_utc=args.official_price_reverified_at_utc,
        )
    except Gdpr7AuthBuilderError as exc:
        print(f"GDPR auth-event builder refused: {exc}")
        return 2

    if args.dry_run:
        print("=== DRY RUN (no files written, no authorization created) ===")
        print(f"scope={event['scope']} calls={event['calls']}")
        print(f"sentence_sha256={event['authorization_sentence_utf8_sha256']}")
        print(f"event_file={EVENT_PATH.name} event_sha256="
              f"{hashlib.sha256(_json_bytes(event)).hexdigest()}")
        print(f"allowed_windows={event['allowed_windows']} "
              f"usd_cap={event['caps']['global_usd_cost_cap']}")
        print(f"price_snapshot={json.dumps(event['price_snapshot'])}")
        print("event draft would be written to:", EVENT_PATH)
        print("No authorization created; API remains NOT AUTHORIZED.")
        return 0

    # --apply path: real user sentence required.
    if not args.sentence or not args.sentence.strip():
        print("Refusing --apply without a real user authorization sentence.")
        return 2
    if args.sentence.lower().startswith("synthetic"):
        print("Refusing --apply: synthetic sentences are not real authorization.")
        return 2
    if EVENT_PATH.exists():
        print(f"Refusing to overwrite: {EVENT_PATH}")
        return 2
    EVENT_PATH.write_bytes(_json_bytes(event))
    print(f"Wrote {EVENT_PATH}")
    print("NOTE: real authorization event created — user-sentence bound.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
