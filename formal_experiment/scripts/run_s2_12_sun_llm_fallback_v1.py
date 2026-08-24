# -*- coding: utf-8 -*-
"""Run a locked S2.12 ``sun_llm_fallback`` stage (F-1/F-2/F-3) with the v2
real-execution safety contract.

* ZERO API by default: ``--transport fake`` (payload-locked fake transport).
* Real transport requires ``--allow-llm`` AND ``--auth-file`` (S2.12
  authorization v1.1.0).  Config is built with
  ``LLMConfig.from_env(project_root, load_project_env=False)`` — a project
  ``.env`` file is NEVER opened; only the process environment is used.
* Every call is payload-locked (final body SHA + sample/clause IDs + order),
  capped (input/output/USD), time-gated (off-peak per call), and recorded in
  an append-only hash-chained ledger with resume support.
* Stages F-1/F-2/F-3 partition the 27 locked fallback payloads (9/9/9).
  Rules+LLM-Repair remains comparison-only; triggers, prompts, and repair
  logic are NOT modified here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.s2_12_execution import (  # noqa: E402
    OUTPUT_DIRS,
    PREFLIGHT_LOCK,
    REQUIRED_MODEL,
    S212ExecutionError,
    StageExecutor,
    PayloadLock,
    PayloadLockedFakeTransport,
    PayloadLockedRealTransport,
    _sha,
    all_arm_payloads_called,
    arm_policy,
    load_and_validate_authorization,
    load_lock,
    load_report,
    publish_stage_capsule,
    rebuild_and_verify_payloads,
)
from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder  # noqa: E402
from run_s2_12_sun_rule_only_v1 import _resolve_records  # noqa: E402

ARM = "sun_llm_fallback"


def _runner_hash() -> str:
    return _sha(Path(__file__))


def _implementation_hashes() -> dict[str, str]:
    import importlib.util

    def module_file(name: str, rel: str) -> Path:
        spec = importlib.util.find_spec(name)
        if spec and spec.origin and Path(spec.origin).is_file():
            return Path(spec.origin)
        return ROOT / rel

    return {
        "s2_12_execution": _sha(ROOT / "src/bpc_hybrid/s2_12_execution.py"),
        "llm_client": _sha(module_file("bpc_hybrid.llm_client",
                                        "src/bpc_hybrid/llm_client.py")),
        "h1_transport": _sha(module_file("bpc_hybrid.h1_transport",
                                         "src/bpc_hybrid/h1_transport.py")),
    }


def _build_transport(args, payload_lock, lock):
    if not args.allow_llm:
        return PayloadLockedFakeTransport(payload_lock, ARM), True
    from bpc_hybrid.llm_config import LLMConfig
    config = LLMConfig.from_env(project_root=ROOT, load_project_env=False)
    if config.provider == "mock" or not config.enabled:
        raise S212ExecutionError("real provider is not enabled (process env only)")
    if config.model != REQUIRED_MODEL:
        raise S212ExecutionError(
            f"resolved model {config.model!r} != {REQUIRED_MODEL!r}"
        )
    return PayloadLockedRealTransport(
        payload_lock, config, timeout_seconds=args.transport_timeout
    ), False


def _synthetic_auth_for_fake(stage_id, rows_by_arm):
    price = {
        "schema_version": "s2_12_price_snapshot@1.0.0",
        "currency": "USD",
        "input_cache_hit_per_million": 0.044,
        "input_cache_miss_per_million": 1.32,
        "output_per_million": 3.96,
    }
    payloads = [row["request_body_sha256"] for row in rows_by_arm[ARM]]
    return {
        "schema_version": "s2_12_api_authorization@1.1.0",
        "authorization_sentence_utf8_sha256": "synthetic-fake",
        "authorization_event_file": "synthetic",
        "authorization_event_file_sha256": "synthetic",
        "model": REQUIRED_MODEL,
        "calls": {"direct_llm": 36, "sun_llm_fallback": 27},
        "stage_id": stage_id,
        "stage_payload_hashes": payloads,
        "stage_call_cap": len(payloads),
        "global_input_token_cap": 63000000,
        "global_output_token_cap": 258048,
        "global_usd_cost_cap": 84.18,
        "allowed_windows": "any_time",
        "price_snapshot": price,
        "price_checked_at_utc": "2026-08-22T00:00:00Z",
        "runner_implementation_hashes": {
            "run_s2_12_direct_llm_v1": "synthetic",
            "run_s2_12_sun_llm_fallback_v1": _runner_hash(),
            "s2_12_execution": _sha(ROOT / "src/bpc_hybrid/s2_12_execution.py"),
            "llm_client": _implementation_hashes()["llm_client"],
            "h1_transport": _implementation_hashes()["h1_transport"],
        },
        "input_config_prompt_hashes": {
            "input_sha256": "892d4284ea70c38f82a47f821c13622f1b07744253429e466038ddb5db96660e",
            "lock_sha256": _sha(PREFLIGHT_LOCK),
            "prompt_direct_sha256": "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895",
            "prompt_fallback_sha256": "00fe02996914e17f30962147d7a9f2c71a92d2479ba4eff343583a139bb1537b",
        },
        "prev_stage_ledger_hash": "",
        "final_63_payload_hashes": payloads,
        "retry": 0,
        "gold_isolation": {
            "api_arms_must_not_read_gold": True,
            "evaluation_only_after_predictions_are_locked": True,
        },
    }


def run(args) -> dict[str, Any]:
    lock = load_lock()
    report = load_report()
    rows_by_arm = rebuild_and_verify_payloads(lock, report, args.runtime_home)
    policy = arm_policy(ARM)
    builder = OpenAICompatibleRequestBuilder(_config_for_builder(lock))

    payload_lock = PayloadLock(ARM, rows_by_arm[ARM], builder, policy)

    input_doc = json.loads(_input_path().read_text(encoding="utf-8"))
    records, runtime_to_formal = _resolve_records(input_doc)
    runtime_text = {rec["sample_id"]: rec["approved_text_en"] for rec in records}
    source_by_id = {
        formal_id: runtime_text[runtime_id]
        for runtime_id, formal_id in runtime_to_formal.items()
    }

    output_dir = (args.output_dir or OUTPUT_DIRS[ARM]).resolve()
    fake = not args.allow_llm
    if fake and output_dir in {path.resolve() for path in OUTPUT_DIRS.values()}:
        raise S212ExecutionError(
            "fake transport must not publish to a formal prediction directory"
        )

    auth = None
    if args.allow_llm:
        if args.auth_file is None:
            raise S212ExecutionError(
                "real transport requires --allow-llm AND --auth-file"
            )
        if args.transport != "real":
            raise S212ExecutionError("--allow-llm requires --transport real")
        auth = load_and_validate_authorization(
            args.auth_file, lock, report, ARM, _runner_hash(),
            _implementation_hashes(),
        )
        if auth["stage_id"] != args.stage_id:
            raise S212ExecutionError(
                f"CLI stage {args.stage_id!r} != authorized stage {auth['stage_id']!r}"
            )

    transport, fake = _build_transport(args, payload_lock, lock)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir.parent / f"{output_dir.name}.ledger.jsonl"
    if args.resume_from_ledger is not None:
        if not args.resume_from_ledger.is_file():
            raise S212ExecutionError(
                f"resume ledger not found: {args.resume_from_ledger}"
            )
        if ledger_path.exists():
            raise S212ExecutionError(
                "refusing to overwrite an existing live ledger with a resume ledger"
            )
        ledger_path.write_bytes(args.resume_from_ledger.read_bytes())
    executor = StageExecutor(
        arm=ARM, stage_id=args.stage_id,
        auth=auth or _synthetic_auth_for_fake(args.stage_id, rows_by_arm),
        lock=lock, report=report, rows_by_arm=rows_by_arm,
        payload_lock=payload_lock, transport=transport,
        ledger_path=ledger_path, source_by_id=source_by_id,
    )
    result = executor.run()
    arm_complete = all_arm_payloads_called(
        executor.ledger, ARM, rows_by_arm
    )
    auth_for_capsule = auth or _synthetic_auth_for_fake(
        args.stage_id, rows_by_arm
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    manifest = publish_stage_capsule(
        arm=ARM, stage_id=args.stage_id, output_dir=output_dir,
        ledger=executor.ledger, state=result["state"],
        response_records=executor.response_records,
        auth=auth_for_capsule, fake=fake, arm_complete=arm_complete,
        lock=lock, report=report,
    )
    return {
        "executor": executor,
        "result": result,
        "output_dir": output_dir,
        "fake": fake,
        "auth": auth,
        "manifest": manifest,
        "arm_complete": arm_complete,
    }


def _config_for_builder(lock):
    from build_s2_12_api_preflight_v1 import _config
    return _config(lock)


def _input_path():
    from bpc_hybrid.s2_12_execution import INPUT
    return INPUT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-home", type=Path,
        default=Path("D:/environment/stanford-corenlp-4.5.10"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
    )
    parser.add_argument(
        "--transport", choices=("fake", "real"), default="fake",
    )
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--auth-file", type=Path)
    parser.add_argument(
        "--stage-id", choices=("F-1", "F-2", "F-3"), default="F-1",
        help="Pre-registered fallback stage (9/9/9 partition of the 27 "
             "locked payloads).",
    )
    parser.add_argument("--resume-from-ledger", type=Path, default=None)
    parser.add_argument("--transport-timeout", type=float, default=180.0)
    args = parser.parse_args()
    try:
        out = run(args)
    except S212ExecutionError as exc:
        print(f"S2.12 sun_llm_fallback refused: {exc}")
        return 2
    result = out["result"]
    status = "stage_complete" if result["status"] == "stage_complete" else "partial"
    print(f"S2.12 sun_llm_fallback stage {args.stage_id}: {status} (fake={out['fake']})")
    print(
        f"calls={result['state']['calls']} "
        f"input={result['state']['input_tokens']} "
        f"output={result['state']['output_tokens']} "
        f"cost_usd={result['state']['cost_usd']}"
    )
    print(f"arm_complete={out['arm_complete']} predictions_published="
          f"{out['manifest']['artifacts'].__contains__('predictions.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())