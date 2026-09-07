# -*- coding: utf-8 -*-
"""Active verifier for the created S2.12 API authorization files (2026-09-07).

Pre-authorization verifiers (``verify_s2_12_runner_safety_v2.py`` /
``verify_s2_12_runner_wiring.py``) assert the historical zero-call state in
which no authorization file exists; once real user-authorized event/auth
files exist their ``no_real_auth`` checks are intentionally superseded (they
remain as provenance of the pre-authorization state).  This verifier is the
active post-authorization entry: it loads each stage authorization file,
re-runs the same validation the runner performs before the first transport
call (schema, model, retry, caps, windows, payload hashes, runner and
implementation hashes against the CURRENT disk state, input/config/prompt
hashes, gold isolation), cross-checks the bound event-file bytes and the
recorded user-sentence hash, verifies the per-stage ledger and formal
prediction output paths are still absent (zero calls), and confirms the USD
caps match the 2026-09-07 user authorization (D-CAL <= 1.00, others 42.09,
off-peak only).  ZERO API / ZERO network / ZERO .env.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.s2_12_execution import (  # noqa: E402
    OUTPUT_DIRS,
    S212ExecutionError,
    _sha,
    load_and_validate_authorization,
    load_lock,
    load_report,
)

RECORDED_SENTENCE_SHA = "27426de7a03cc8c75eae5d57ebbd11860b2ce229f7afdd55bce4fa9a08bc0dd6"

STAGES = ("D-CAL", "D-REST", "F-1", "F-2", "F-3")
ARM_BY_STAGE = {
    "D-CAL": "direct_llm",
    "D-REST": "direct_llm",
    "F-1": "sun_llm_fallback",
    "F-2": "sun_llm_fallback",
    "F-3": "sun_llm_fallback",
}
USD_CAP_BY_STAGE = {
    "D-CAL": 1.00,
    "D-REST": 42.09,
    "F-1": 42.09,
    "F-2": 42.09,
    "F-3": 42.09,
}


def _runner_hash_for(arm: str) -> str:
    script = {
        "direct_llm": "run_s2_12_direct_llm_v1.py",
        "sun_llm_fallback": "run_s2_12_sun_llm_fallback_v1.py",
    }[arm]
    return _sha(ROOT / "scripts" / script)


def _implementation_hashes() -> dict[str, str]:
    return {
        "s2_12_execution": _sha(ROOT / "src/bpc_hybrid/s2_12_execution.py"),
        "llm_client": _sha(ROOT / "src/bpc_hybrid/llm_client.py"),
        "h1_transport": _sha(ROOT / "src/bpc_hybrid/h1_transport.py"),
    }


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_all() -> list[dict[str, str]]:
    """Validate every stage; return a list of {stage, check, ok} rows."""
    rows: list[dict[str, str]] = []
    lock = load_lock()
    report = load_report()

    def check(stage: str, name: str, ok: bool, detail: str = "") -> None:
        rows.append({
            "stage": stage, "check": name,
            "ok": "PASS" if ok else "FAIL",
            "detail": detail[:200],
        })

    for stage in STAGES:
        arm = ARM_BY_STAGE[stage]
        auth_path = ROOT / "configs" / f"s2_12_api_authorization_{stage}.json"
        event_path = ROOT / "configs" / f"s2_12_api_authorization_event_{stage}.json"
        if not auth_path.is_file():
            check(stage, "auth_file_present", False, str(auth_path))
            continue
        check(stage, "auth_file_present", True)
        try:
            auth = load_and_validate_authorization(
                auth_path, lock, report, arm,
                _runner_hash_for(arm), _implementation_hashes(),
            )
            check(stage, "runner_validate", True)
        except S212ExecutionError as exc:
            check(stage, "runner_validate", False, str(exc))
            continue
        check(stage, "model", auth["model"] == "deepseek-v4-pro")
        check(stage, "retry_zero", auth["retry"] == 0)
        check(stage, "allowed_windows",
              auth["allowed_windows"] == "off_peak_only")
        expected_usd = USD_CAP_BY_STAGE[stage]
        check(stage, "usd_cap",
              abs(float(auth["global_usd_cost_cap"]) - expected_usd) < 1e-9,
              f"auth={auth['global_usd_cost_cap']} expected={expected_usd}")
        check(stage, "global_caps",
              auth["global_input_token_cap"] == 63_000_000
              and auth["global_output_token_cap"] == 258_048)
        check(stage, "stage_call_cap_positive", auth["stage_call_cap"] > 0)
        check(stage, "sentence_hash",
              auth["authorization_sentence_utf8_sha256"]
              == RECORDED_SENTENCE_SHA)
        if event_path.is_file():
            event_sha = hashlib.sha256(event_path.read_bytes()).hexdigest()
            check(stage, "event_file_hash_matches",
                  event_sha == auth["authorization_event_file_sha256"])
            try:
                event = json.loads(event_path.read_text(encoding="utf-8"))
                check(stage, "event_sentence_hash",
                      _sha_text(event.get("authorization_sentence") or "")
                      == event.get("authorization_sentence_utf8_sha256")
                      == RECORDED_SENTENCE_SHA)
                check(stage, "event_not_synthetic",
                      event.get("not_a_synthetic_fixture") is True)
            except (OSError, json.JSONDecodeError) as exc:
                check(stage, "event_parses", False, str(exc))
        else:
            check(stage, "event_file_present", False)

        output_dir = OUTPUT_DIRS[arm]
        ledger = output_dir.parent / f"{output_dir.name}.ledger.jsonl"
        check(stage, "zero_calls_no_ledger", not ledger.exists())
        check(stage, "zero_calls_no_capsule", not output_dir.exists())
    return rows


def main() -> int:
    rows = validate_all()
    failed = 0
    for row in rows:
        print(f"{row['ok']} {row['stage']:<6} {row['check']} "
              f"{('(' + row['detail'] + ')') if row['detail'] else ''}")
        if row["ok"] != "PASS":
            failed += 1
    total = len(rows)
    if failed:
        print(f"S2.12 AUTHORIZATION FILES VERIFICATION FAILED "
              f"({total - failed}/{total} PASS)")
        return 1
    print(f"S2.12 AUTHORIZATION FILES VERIFIED ({total}/{total} PASS) / "
          f"ZERO CALLS / READY FOR AUTHORIZED REAL RUN (off-peak only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
