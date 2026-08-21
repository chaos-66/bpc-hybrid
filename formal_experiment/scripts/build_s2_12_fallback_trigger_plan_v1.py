# -*- coding: utf-8 -*-
"""Build the S2.12 frozen Rules+LLM-Repair trigger plan (zero API).

Derivation contract (fail-closed):

* The ONLY allowed source is the already-locked preflight trigger set
  (``outputs/reports/s2_12_api_preflight_v1.json``,
  ``arms.sun_llm_fallback.calls`` = 27 clause-level entries selected by the
  locked risk-descending budget allocation).
* The plan records per-call: execution order, sample_id, clause_id,
  clause_index (from the locked payload plan derivation), and the locked
  request-body SHA-256.  It NEVER reads Gold/decisions/proposals, and it
  never touches H1 trigger rules, prompts, or repair logic.
* No third-party source text is committed: only sample IDs, clause IDs,
  coordinates, hashes, and audit metadata.
* Zero LLM/API; ``--check`` replays the derivation and requires byte-identity
  with the committed plan.

The builder re-runs the same preflight diagnostic B0 replay to re-derive the
27 triggered plans, then binds each to the locked report entry.  This makes
the frozen plan a genuine snapshot of the deterministic trigger selection.
"""

from __future__ import annotations

import argparse
import hashlib
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

from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder  # noqa: E402
from bpc_hybrid.h1_transport import DEEPSEEK_V4_PRO_H1_POLICY  # noqa: E402
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from build_s2_12_api_preflight_v1 import (  # noqa: E402
    _config,
    _rerun_b0,
    _verify_file_bindings,
)
from run_sun_llm_fallback import (  # noqa: E402
    _build_context_audit,
    _build_user_prompt,
    allocate_repair_calls,
    build_repair_plans,
)

REPORT = ROOT / "outputs/reports/s2_12_api_preflight_v1.json"
PREFLIGHT_LOCK = ROOT / "configs/s2_12_api_arms_preflight_v1.json"
INPUT = ROOT / "data/input/s2_12_complex_corpus_formal_input_v1.json"
OUTPUT = ROOT / "configs/s2_12_fallback_trigger_plan_v1.json"
EXPECTED_INPUT_SHA = "892d4284ea70c38f82a47f821c13622f1b07744253429e466038ddb5db96660e"


class TriggerPlanFail(ValueError):
    """Fail-closed trigger plan error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build(runtime_home: Path) -> dict[str, Any]:
    if _sha(INPUT) != EXPECTED_INPUT_SHA:
        raise TriggerPlanFail("Gold-blind input drift")
    lock = json.loads(PREFLIGHT_LOCK.read_text(encoding="utf-8"))
    if lock.get("status") != "locked_without_api_authorization":
        raise TriggerPlanFail("preflight lock status drift")
    _verify_file_bindings(lock["implementation_bindings"])
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    locked_calls = report["arms"]["sun_llm_fallback"]["calls"]
    if len(locked_calls) != 27:
        raise TriggerPlanFail(f"locked fallback call count != 27: {len(locked_calls)}")

    _adapted, batch = _rerun_b0(runtime_home)
    plans = allocate_repair_calls(
        build_repair_plans(batch), lock["arms"]["sun_llm_fallback"]["max_calls"]
    )
    if len(plans) != len(locked_calls):
        raise TriggerPlanFail(
            f"rebuild produced {len(plans)} plans != locked {len(locked_calls)}"
        )

    h1_prompt = load_prompt(lock["arms"]["sun_llm_fallback"]["prompt_name"])
    records = {item.record["sample_id"]: item.record for item in batch}
    config = _config(lock)
    builder = OpenAICompatibleRequestBuilder(config)

    entries: list[dict[str, Any]] = []
    for index, plan in enumerate(plans, 1):
        locked = locked_calls[index - 1]
        if (locked["sample_id"], locked.get("clause_id")) != (plan.sample_id, plan.clause_id):
            raise TriggerPlanFail(
                f"locked preflight call {index} ({locked['sample_id']}/"
                f"{locked.get('clause_id')}) != rebuilt plan "
                f"({plan.sample_id}/{plan.clause_id})"
            )
        record = records[plan.sample_id]
        clause = record["clauses"][plan.clause_index]
        context_clause, audit = _build_context_audit(clause, plan, "full_b0_v4")
        if not audit.get("original_record_unchanged"):
            raise TriggerPlanFail(
                f"context mutated B0 record: {plan.sample_id}/{plan.clause_id}"
            )
        user_prompt = _build_user_prompt(h1_prompt, record, plan, context_clause)
        body = DEEPSEEK_V4_PRO_H1_POLICY.apply_to_body(
            builder.build_body(h1_prompt.system_prompt, user_prompt)
        )
        body_bytes = json.dumps(body).encode("utf-8")
        body_sha = hashlib.sha256(body_bytes).hexdigest()
        if locked["request_body_sha256"] != body_sha:
            raise TriggerPlanFail(
                f"locked call {index} body sha mismatch: "
                f"{locked['request_body_sha256'][:12]} != {body_sha[:12]}"
            )
        entries.append({
            "execution_order": index,
            "sample_id": plan.sample_id,
            "clause_id": plan.clause_id,
            "clause_index": plan.clause_index,
            "repair_fields": list(plan.repair_fields),
            "reasons": list(plan.reasons),
            "risk_score": plan.risk_score,
            "request_body_sha256": body_sha,
            "request_body_utf8_bytes": len(body_bytes),
        })

    return {
        "schema_version": "s2_12_fallback_trigger_plan@1.0.0",
        "plan_id": "s2-12-fallback-trigger-plan-v1",
        "status": "frozen_locked_before_api_authorization",
        "dataset_id": "s2_11_barrientos_complex_corpus_36_v1",
        "method_id": "sun_llm_fallback",
        "role": "comparison_only_negative_result_control",
        "source": {
            "preflight_report": "outputs/reports/s2_12_api_preflight_v1.json",
            "preflight_report_sha256": _sha(REPORT),
            "locked_calls": len(locked_calls),
            "derivation": (
                "locked risk-descending budget allocation replayed by "
                "build_s2_12_api_preflight_v1.diagnostics; per-call "
                "request-body SHA must match the locked preflight report"
            ),
        },
        "input": {
            "path": "data/input/s2_12_complex_corpus_formal_input_v1.json",
            "sha256": EXPECTED_INPUT_SHA,
            "records": 36,
        },
        "prompt": {
            "name": lock["arms"]["sun_llm_fallback"]["prompt_name"],
            "sha256": lock["arms"]["sun_llm_fallback"]["prompt_sha256"],
        },
        "retry": 0,
        "gold_isolation": {
            "gold_read_by_derivation": False,
            "selected_from_locked_preflight_only": True,
            "post_result_selection_forbidden": True,
        },
        "selected_plans": entries,
        "safety": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "raw_text_committed": False,
            "h1_trigger_or_prompt_or_repair_logic_modified": False,
            "gold_rule_records_created": False,
            "oracle_started": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-home", type=Path,
        default=Path("D:/environment/stanford-corenlp-4.5.10"),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    try:
        plan = build(args.runtime_home)
        payload = _json_bytes(plan)
        if args.publish:
            if OUTPUT.exists():
                raise TriggerPlanFail(
                    f"refusing to overwrite existing plan: {OUTPUT}"
                )
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT.write_bytes(payload)
        else:
            if not OUTPUT.is_file() or OUTPUT.read_bytes() != payload:
                raise TriggerPlanFail("published trigger plan differs from replay")
    except (OSError, ValueError) as exc:
        print(f"S2.12 fallback trigger plan refused: {exc}")
        return 2
    print(
        f"S2.12 fallback trigger plan verified: {len(plan['selected_plans'])} "
        "locked calls, zero API"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())