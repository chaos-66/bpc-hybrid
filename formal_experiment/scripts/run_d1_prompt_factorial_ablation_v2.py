# -*- coding: utf-8 -*-
"""Execute the three clean Direct-LLM prompt-factor ablations.

The historical 1140-call Barrientos D/E suite is immutable.  This runner owns
a separate 450-call plan: three prompt arms x the same EStG-150 input, one run
per arm.  Every arm is evaluated against the existing D-full-0813 result with
the same Gold and evaluator; the baseline is not called again.

Real execution is fail-closed behind a dedicated contract and a new explicit
authorization event.  ``--dry-run`` never reads an API key and never sends a
network request.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import run_barrientos_ablation_suite_v2 as base  # noqa: E402

from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402


ARMS = (
    "D-no-semantic-examples-0813",
    "D-no-semantic-guidance-0813",
    "D-no-explicit-json-contract-0813",
)
PROMPT_NAMES = {
    "D-no-semantic-examples-0813": (
        "ablation_v2/direct_llm_no_semantic_examples_prompt_v2"),
    "D-no-semantic-guidance-0813": (
        "ablation_v2/direct_llm_no_semantic_guidance_prompt_v2"),
    "D-no-explicit-json-contract-0813": (
        "ablation_v2/direct_llm_no_explicit_json_contract_prompt_v2"),
}
PROMPT_DIR = ROOT / "prompts" / "sun_compat" / "ablation_v2"
PROMPT_MANIFEST = PROMPT_DIR / "manifest.json"
ESTG_INPUT = (
    ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
)
CONTRACT_PATH = (
    ROOT / "configs" / "ablations"
    / "d1_prompt_factorial_execution_contract_v1.json"
)
CONTRACT_SCHEMA = (
    ROOT / "configs" / "schemas"
    / "d1_prompt_factorial_execution_contract_v1.schema.json"
)
EXECUTOR_FILE = ROOT / "scripts" / "run_d1_prompt_factorial_ablation_v2.py"
BUILDER_FILE = ROOT / "scripts" / "build_d1_prompt_factorial_arms_v2.py"
OUT_DIR = ROOT / "outputs" / "development" / "d1_prompt_factorial_ablation_v2"
SUMMARY_REPORT = ROOT / "outputs" / "reports" / "d1_prompt_factorial_ablation_v2.json"
MODEL_ALIAS = "deepseek-v4-pro"
MODEL_RELEASE = "DeepSeek-V4-Pro-0813"
PLANNED_CALLS = 450


class ContractError(RuntimeError):
    """The dedicated experiment contract failed closed."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError(f"expected JSON object: {path}")
    return value


def _git_head() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
        capture_output=True, text=True, check=False)
    if proc.returncode:
        raise ContractError("cannot resolve git HEAD")
    return proc.stdout.strip()


def _git_is_ancestor(commit: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    return proc.returncode == 0


def prompt_path(arm: str) -> Path:
    if arm not in PROMPT_NAMES:
        raise KeyError(f"unknown prompt-factor arm: {arm}")
    return ROOT / "prompts" / "sun_compat" / f"{PROMPT_NAMES[arm]}.md"


def samples() -> list[dict[str, str]]:
    doc = _read_json(ESTG_INPUT)
    rows = doc.get("records")
    if not isinstance(rows, list) or len(rows) != 150:
        raise ContractError("EStG input must contain exactly 150 records")
    result = [
        {"sample_id": str(row["sample_id"]),
         "text": str(row["approved_text_en"])}
        for row in rows
    ]
    if len({row["sample_id"] for row in result}) != 150:
        raise ContractError("EStG sample ids must be unique")
    return result


def build_execution_plan() -> list[dict[str, Any]]:
    return [
        {"arm": arm, "repeat_id": "repeat-01", "sample_count": 150,
         "calls": 150, "baseline_reused": "D-full-0813"}
        for arm in ARMS
    ]


def _few_shot_block(prompt: Any) -> str:
    raw = prompt.raw_text
    start = raw.find("## Examples")
    end = raw.find("## Notes", start)
    if start < 0 or end < 0:
        return ""
    return raw[start:end].strip()


def render_prompt(arm: str, sample_id: str, source_text: str) -> tuple[str, str]:
    prompt = load_prompt(PROMPT_NAMES[arm])
    user = prompt.user_prompt_template.format(
        sample_id=sample_id,
        source_id=sample_id,
        source_text=source_text,
        few_shot_block=_few_shot_block(prompt),
    )
    if not prompt.system_prompt or not user:
        raise ContractError(f"rendered prompt is empty: {arm}")
    return prompt.system_prompt, user


def request_body(arm: str, sample_id: str, source_text: str) -> dict[str, Any]:
    system, user = render_prompt(arm, sample_id, source_text)
    return {
        "model": MODEL_ALIAS,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 4096,
        "stream": False,
        "thinking": {"type": "disabled"},
    }


def estimate_rendered_input_tokens() -> tuple[int, dict[str, int]]:
    per_arm: dict[str, int] = {}
    rows = samples()
    for arm in ARMS:
        total = 0
        for row in rows:
            body = request_body(arm, row["sample_id"], row["text"])
            raw = json.dumps(
                body, ensure_ascii=False, sort_keys=True).encode("utf-8")
            total += math.ceil(len(raw) / 3)
        per_arm[arm] = total
    return sum(per_arm.values()), per_arm


def dry_run() -> dict[str, Any]:
    total, per_arm = estimate_rendered_input_tokens()
    result = {
        "schema_version": "d1_prompt_factorial_dry_run@1.0.0",
        "mode": "dry_run_off_network",
        "planned_calls": PLANNED_CALLS,
        "llm_api_calls": 0,
        "network_calls": 0,
        "input_sha256": _sha256_file(ESTG_INPUT),
        "prompt_manifest_sha256": _sha256_file(PROMPT_MANIFEST),
        "estimated_input_tokens": total,
        "arms": {
            arm: {
                "sample_count": 150,
                "prompt_sha256": _sha256_file(prompt_path(arm)),
                "estimated_input_tokens": per_arm[arm],
            }
            for arm in ARMS
        },
        "baseline": {
            "arm": "D-full-0813",
            "calls": 0,
            "reason": "reuse completed same-release baseline",
        },
    }
    return result


def _verify_authorization(contract: Mapping[str, Any]) -> None:
    auth = contract.get("authorization")
    if not isinstance(auth, Mapping):
        raise ContractError(
            "contract authorization is null; this new 450-call batch has "
            "not been explicitly authorized")
    event_path = Path(str(auth.get("authorization_event_file") or ""))
    if not event_path.is_absolute():
        event_path = ROOT / event_path
    resolved = event_path.resolve()
    allowed = (ROOT / "configs").resolve(), (ROOT / "outputs" / "reports").resolve()
    if not any(resolved.is_relative_to(folder) for folder in allowed):
        raise ContractError("authorization event is outside allowed directories")
    if not resolved.is_file():
        raise ContractError("authorization event file does not exist")
    if _sha256_file(resolved) != auth.get("authorization_event_file_sha256"):
        raise ContractError("authorization event file hash mismatch")
    event = _read_json(resolved)
    sentence = event.get("authorization_sentence")
    if not isinstance(sentence, str) or not sentence.strip():
        raise ContractError("authorization sentence missing")
    if _sha256_bytes(sentence.encode("utf-8")) != auth.get(
            "authorization_sentence_utf8_sha256"):
        raise ContractError("authorization sentence hash mismatch")
    cap = float((contract.get("budget") or {}).get("usd_cost_cap"))
    required = (
        "450", MODEL_ALIAS, MODEL_RELEASE, "temperature=0", "retry=0",
        f"{cap:.3f}",
    )
    for token in required:
        if token not in sentence:
            raise ContractError(
                f"authorization sentence does not name required token {token!r}")


def validate_contract(
    path: Path = CONTRACT_PATH, *, allow_unauthorized: bool = False
) -> dict[str, Any]:
    contract = _read_json(path)
    schema = _read_json(CONTRACT_SCHEMA)
    from bpc_hybrid.de_contract_schema import validate_with_jsonschema_if_available
    errors = validate_with_jsonschema_if_available(contract, schema)
    if errors:
        raise ContractError(
            "contract schema validation failed:\n  " + "\n  ".join(errors[:20]))

    bound = contract.get("bound_commit")
    if not isinstance(bound, str) or not _git_is_ancestor(bound):
        raise ContractError("bound commit is not an ancestor of HEAD")
    if contract.get("execution_plan", {}).get("arms") != build_execution_plan():
        raise ContractError("contract execution plan does not match fixed 450-call plan")
    if contract.get("execution_plan", {}).get("total_calls") != PLANNED_CALLS:
        raise ContractError("contract total must be exactly 450 calls")

    model = contract.get("model") or {}
    if model.get("id") != MODEL_ALIAS \
            or model.get("provider") != "openai_compatible" \
            or (model.get("documented_mapping") or {}).get("release") != MODEL_RELEASE:
        raise ContractError("model alias/release binding mismatch")
    sampling = contract.get("sampling") or {}
    expected_sampling = {
        "temperature": 0.0, "top_p": 1.0, "max_tokens": 4096,
        "retry": 0, "stream": False, "thinking": {"type": "disabled"},
    }
    if sampling != expected_sampling:
        raise ContractError("sampling policy mismatch")

    hashes = contract.get("hashes") or {}
    expected_hashes = {
        "estg_input_v2": _sha256_file(ESTG_INPUT),
        "executor": _sha256_file(EXECUTOR_FILE),
        "prompt_builder": _sha256_file(BUILDER_FILE),
        "prompt_manifest": _sha256_file(PROMPT_MANIFEST),
    }
    for key, expected in expected_hashes.items():
        if hashes.get(key) != expected:
            raise ContractError(f"contract hash drift: {key}")
    if (hashes.get("prompts") or {}) != {
            arm: _sha256_file(prompt_path(arm)) for arm in ARMS}:
        raise ContractError("contract prompt hashes drift")
    budget = contract.get("budget") or {}
    if budget.get("planned_calls") != PLANNED_CALLS:
        raise ContractError("budget call cap must be exactly 450")
    for name in ("input_token_cap", "output_token_cap", "usd_cost_cap"):
        if not isinstance(budget.get(name), (int, float)) or budget[name] <= 0:
            raise ContractError(f"invalid budget cap: {name}")
    if (contract.get("gold_isolation") or {}).get(
            "api_arms_must_not_read_gold") is not True:
        raise ContractError("Gold isolation declaration invalid")
    if not allow_unauthorized:
        _verify_authorization(contract)
    return contract


def _call_once(
    arm: str,
    sample: Mapping[str, str],
    transport: Any,
    cost_of: Callable[[Mapping[str, Any]], float],
    gate: Any,
) -> dict[str, Any]:
    sid, text = sample["sample_id"], sample["text"]
    system, user = render_prompt(arm, sid, text)
    body = request_body(arm, sid, text)
    body_bytes = json.dumps(
        body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    gate.check_before_send(
        projected_input_tokens=math.ceil(len(body_bytes) / 3),
        projected_max_output_tokens=4096,
    )
    request_id = f"{arm}:{sid}:{time.time_ns()}"
    try:
        from bpc_hybrid.llm_client import LLMRequest
        response = transport.send(LLMRequest(
            source_id=sid, source_text=text,
            system_prompt=system, user_prompt=user))
        content = response.content or ""
        decode = getattr(transport, "last_decode", None) or {}
        usage = dict(decode.get("usage") or {})
        status = "ok" if decode.get("status") in (
            None, "ok_message_content") else "error"
        error = None
    except Exception as exc:
        content, decode, usage, status, error = "", {}, {}, "error", str(exc)
    try:
        gate.record_after_response(
            usage if usage else None, returned_model=decode.get("model"))
    except base.ContractError:
        pass
    response_sha = _sha256_bytes(content.encode("utf-8"))
    return {
        "sample_id": sid,
        "arm": arm,
        "repeat_id": "repeat-01",
        "request_body_sha256": _sha256_bytes(body_bytes),
        "request_id": decode.get("request_id") or request_id,
        "raw_response_content": content,
        "response_sha256": response_sha,
        "usage": usage,
        "cost": cost_of(usage) if usage else "unknown",
        "request_status": status,
        "error": error,
        "returned_model": decode.get("model"),
        "network_call": 1,
    }


def _run_arm(
    arm: str,
    rows: Sequence[Mapping[str, str]],
    transport: Any,
    cost_of: Callable[[Mapping[str, Any]], float],
    gate: Any,
    *,
    before_send: Callable[[], None] | None,
) -> dict[str, Any]:
    run_dir = OUT_DIR / arm / "repeat-01"
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / "raw_responses.jsonl"
    ledger_path = run_dir / "calls_ledger.jsonl"
    persisted_raw = {
        row["sample_id"]: row for row in base._read_jsonl(raw_path)
    }
    persisted_ledger = {
        row["sample_id"]: row for row in base._read_jsonl(ledger_path)
    }
    raw_rows: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    new_sends = 0
    resumed = 0

    for sample in rows:
        sid = sample["sample_id"]
        if sid in persisted_raw:
            call = persisted_raw[sid]
            resumed += 1
        elif sid in persisted_ledger:
            raise ContractError(
                f"in_doubt sample requires manual resolution: {arm}/{sid}")
        else:
            if before_send:
                before_send()
            call = _call_once(arm, sample, transport, cost_of, gate)
            new_sends += 1
            if call["request_status"] == "error" and not call[
                    "raw_response_content"]:
                base._append_jsonl(ledger_path, {
                    "sample_id": sid, "arm": arm, "repeat_id": "repeat-01",
                    "state": "in_doubt", "error": call.get("error"),
                })
            else:
                base._append_jsonl(raw_path, call)
                base._append_jsonl(ledger_path, {
                    "sample_id": sid, "arm": arm, "repeat_id": "repeat-01",
                    "state": "completed",
                    "response_sha256": call["response_sha256"],
                })
            if gate.aborted:
                raise ContractError(str(gate.abort_reason))
        raw_rows.append(call)
        parsed = base.parse_same_response(call, arm, sample["text"])
        prediction = base._prediction_row(parsed, arm)
        predictions.append(prediction)
        if prediction["request_status"] != "ok":
            failed.append(prediction)

    evaluation = base._make_evaluator(arm)(predictions)
    raw_agg = base.aggregate_hash(raw_rows)
    pred_agg = base.aggregate_hash(predictions)
    (run_dir / "canonical_predictions.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n"
                for row in predictions), encoding="utf-8", newline="\n")
    (run_dir / "failed_samples.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in failed),
        encoding="utf-8", newline="\n")
    (run_dir / "evaluation.json").write_text(
        json.dumps({"arm": arm, "repeat_id": "repeat-01",
                    "denominator": len(predictions), "evaluation": evaluation},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    manifest = {
        "arm": arm,
        "repeat_id": "repeat-01",
        "sample_count": len(rows),
        "actual_call_count": new_sends,
        "resumed_completed_count": resumed,
        "failed_count": len(failed),
        "prompt_sha256": _sha256_file(prompt_path(arm)),
        "raw_responses_aggregate_sha256": raw_agg,
        "canonical_predictions_aggregate_sha256": pred_agg,
        "evaluation_denominator": len(predictions),
        "same_response_binding": all(
            raw.get("response_sha256") == pred.get("response_sha256")
            for raw, pred in zip(raw_rows, predictions)
            if pred["request_status"] == "ok"),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    return {"manifest": manifest, "evaluation": evaluation}


def _restore_global_gate(gate: Any) -> None:
    for row in build_execution_plan():
        run_dir = OUT_DIR / row["arm"] / row["repeat_id"]
        raw = base._read_jsonl(run_dir / "raw_responses.jsonl")
        ledger = base._read_jsonl(run_dir / "calls_ledger.jsonl")
        if raw or ledger:
            gate.restore_from_persisted(raw, ledger)


def execute(
    path: Path = CONTRACT_PATH,
    *,
    transport_factory: Callable[[], Any] | None = None,
    allow_unauthorized: bool = False,
) -> dict[str, Any]:
    contract = validate_contract(path, allow_unauthorized=allow_unauthorized)
    gate = base.DeBudgetGate(contract)
    from bpc_hybrid.llm_config import LLMConfig
    from bpc_hybrid.llm_client import RealAPITransport
    from bpc_hybrid.h1_transport import H1RequestPolicy
    llm_config = LLMConfig.from_env(project_root=ROOT, load_project_env=False)
    real = transport_factory is None
    if real:
        base._validate_runtime_config(llm_config, contract)

        def transport_factory() -> Any:
            return RealAPITransport(
                llm_config, timeout_seconds=180.0,
                policy=H1RequestPolicy(
                    stream=False, thinking={"type": "disabled"},
                    response_format=None))

    price = (contract["budget"]["price_snapshot"])

    def cost_of(usage: Mapping[str, Any]) -> float:
        return round(
            float(usage.get("prompt_tokens", 0))
            * float(price["input_cache_miss_per_million"]) / 1e6
            + float(usage.get("completion_tokens", 0))
            * float(price["output_per_million"]) / 1e6,
            8,
        )

    result: dict[str, Any] = {
        "schema_version": "d1_prompt_factorial_execution@1.0.0",
        "planned_calls": PLANNED_CALLS,
        "actual_calls": 0,
        "completed_samples": 0,
        "aborted": False,
        "runs": [],
    }
    started = time.time()
    try:
        _restore_global_gate(gate)
        for arm in ARMS:
            run = _run_arm(
                arm, samples(), transport_factory(), cost_of, gate,
                before_send=base._require_beijing_off_peak if real else None)
            manifest = run["manifest"]
            result["actual_calls"] += manifest["actual_call_count"]
            result["completed_samples"] += (
                manifest["actual_call_count"]
                + manifest["resumed_completed_count"])
            result["runs"].append({
                "arm": arm,
                "actual_call_count": manifest["actual_call_count"],
                "resumed_completed_count": manifest[
                    "resumed_completed_count"],
                "failed_count": manifest["failed_count"],
            })
    except (ContractError, base.ContractError, Exception) as exc:
        result["aborted"] = True
        result["abort_reason"] = f"{type(exc).__name__}: {exc}"
    result["budget_gate"] = gate.to_dict()
    result["runtime_seconds"] = round(time.time() - started, 3)
    result["complete"] = (
        not result["aborted"]
        and result["completed_samples"] == PLANNED_CALLS
        and gate.calls_made == PLANNED_CALLS
        and not gate.aborted
        and len(result["runs"]) == len(ARMS)
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "execution_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    if result["complete"]:
        SUMMARY_REPORT.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--contract-file", type=Path, default=CONTRACT_PATH)
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps(dry_run(), ensure_ascii=False, indent=2))
        return 0
    try:
        result = execute(args.contract_file)
    except ContractError as exc:
        print(f"INCOMPLETE/ABORTED: {exc}", file=sys.stderr)
        return 3
    if not result.get("complete"):
        print(
            "INCOMPLETE/ABORTED: " + str(result.get("abort_reason") or "incomplete"),
            file=sys.stderr)
        return 3
    print("D1 prompt-factor ablation complete: 450/450")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
