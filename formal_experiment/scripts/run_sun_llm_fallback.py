"""Plan S2.8 H1 fallback decisions from verified canonical B0 records.

This entry point is intentionally offline.  S2.8 freezes selection, field
closure, merge, failure, and budget behavior; it does not unlock a real LLM
transport.  Passing ``--allow-llm`` therefore fails closed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.prompt_loader import build_manifest_entry, load_prompt  # noqa: E402
from bpc_hybrid.stage2_canonical import validate_canonical  # noqa: E402
from bpc_hybrid.sun_style.h1_selective import (  # noqa: E402
    H1ContractError,
    RepairPlan,
    allocate_repair_calls,
    detect_repair_plan,
    load_s28_config,
    render_h1_request,
    sha256_file,
)


PromptName = "rule_first_llm_fallback_prompt"
DEFAULT_CONFIG = ROOT / "configs" / "models" / "sun_h1_s28.json"
DEVELOPMENT_ROOTS = (
    ROOT / "outputs" / "development",
    ROOT / "data" / "development",
)


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise H1ContractError(f"invalid JSON: {path}") from exc


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise H1ContractError(f"JSONL line {line_number} is not an object")
                records.append(value)
    except H1ContractError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise H1ContractError(f"invalid JSONL: {path}") from exc
    return records


def _load_locked_s26_record(config: dict[str, Any]) -> list[dict[str, Any]]:
    spec = config["baseline_binding"]["verification_manifest"]
    path = _project_path(spec["path"])
    if not path.is_file() or sha256_file(path) != spec["sha256"]:
        raise H1ContractError("locked S2.6 manifest is missing or hash-mismatched")
    manifest = _load_json(path)
    record = manifest.get("composition", {}).get("synthetic_canonical_record")
    if not isinstance(record, dict):
        raise H1ContractError("locked S2.6 manifest has no canonical record")
    return [record]


def _load_telemetry(path: Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    if path is None:
        return {}
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for item in _load_jsonl(path):
        sample_id = item.get("sample_id")
        clause_id = item.get("clause_id")
        telemetry = item.get("telemetry")
        if not isinstance(sample_id, str) or not isinstance(clause_id, str) or not isinstance(telemetry, dict):
            raise H1ContractError("telemetry rows require sample_id, clause_id, and telemetry object")
        key = (sample_id, clause_id)
        if key in result:
            raise H1ContractError(f"duplicate telemetry row: {key}")
        result[key] = telemetry
    return result


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def build_plans(
    records: list[dict[str, Any]],
    telemetry_by_clause: dict[tuple[str, str], dict[str, Any]],
    config: dict[str, Any],
) -> list[RepairPlan]:
    plans: list[RepairPlan] = []
    seen_sample_ids: set[str] = set()
    consumed_telemetry: set[tuple[str, str]] = set()
    for record in records:
        sample_id = record.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in seen_sample_ids:
            raise H1ContractError(f"invalid or duplicate B0 sample_id: {sample_id!r}")
        seen_sample_ids.add(sample_id)
        validation = validate_canonical(record)
        if not validation.schema_valid or not validation.cross_field_valid:
            raise H1ContractError(f"B0 record is not canonical-valid: {sample_id}")
        clauses = record.get("clauses", [])
        for clause_index, clause in enumerate(clauses):
            key = (sample_id, clause.get("clause_id"))
            if key in telemetry_by_clause:
                consumed_telemetry.add(key)
            plan = detect_repair_plan(
                record,
                telemetry_by_clause.get(key, {}),
                config,
                clause_index=clause_index,
            )
            plans.append(plan)
    unused = sorted(set(telemetry_by_clause) - consumed_telemetry)
    if unused:
        raise H1ContractError(f"telemetry references unknown B0 clauses: {unused}")
    return plans


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--b0-jsonl",
        type=Path,
        help="Canonical sun_rule_only JSONL. Defaults to the locked S2.6 synthetic record.",
    )
    parser.add_argument(
        "--telemetry-jsonl",
        type=Path,
        help="Optional inference-time telemetry JSONL; no Gold/test fields are accepted.",
    )
    parser.add_argument("--plan-out", type=Path, help="Optional development-only plan JSON path.")
    parser.add_argument("--development", action="store_true")
    parser.add_argument(
        "--allow-llm",
        action="store_true",
        help="Reserved for a later separately authorized task; S2.8 always refuses it.",
    )
    args = parser.parse_args()

    if args.allow_llm:
        print("Refusing real LLM use: S2.8 verifies only offline planning and mock merge behavior.")
        return 2
    try:
        config_path = args.config.resolve()
        config = load_s28_config(config_path)
        prompt = load_prompt(PromptName)
        if prompt.sha256 != config["prompt"]["sha256"]:
            raise H1ContractError("H1 prompt SHA-256 changed")
        baseline_config = config["baseline_binding"]["config"]
        baseline_path = _project_path(baseline_config["path"])
        if not baseline_path.is_file() or sha256_file(baseline_path) != baseline_config["sha256"]:
            raise H1ContractError("locked S2.6 config is missing or hash-mismatched")
        records = _load_jsonl(args.b0_jsonl.resolve()) if args.b0_jsonl else _load_locked_s26_record(config)
        telemetry = _load_telemetry(args.telemetry_jsonl.resolve() if args.telemetry_jsonl else None)
        plans = build_plans(records, telemetry, config)
        allocations = allocate_repair_calls(plans, config)
        records_by_id = {record["sample_id"]: record for record in records}
        plans_by_key = {(plan.sample_id, plan.clause_id): plan for plan in plans}
        requests: list[dict[str, Any]] = []
        for decision in allocations:
            if not decision["call_reserved"]:
                continue
            key = (decision["sample_id"], decision["clause_id"])
            request = render_h1_request(
                records_by_id[decision["sample_id"]],
                plans_by_key[key],
                prompt,
                config,
            )
            requests.append(
                {
                    "request_id": f"{decision['sample_id']}::{decision['clause_id']}",
                    "sample_id": decision["sample_id"],
                    "clause_id": decision["clause_id"],
                    **request,
                }
            )
        payload = {
            "schema_version": "sun_h1_s28_plan@1.1.0",
            "task_id": "S2.8",
            "mode": "offline_plan_only",
            "config": {
                "path": config_path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(config_path),
            },
            "prompt": build_manifest_entry(prompt, role="repair_patch"),
            "model": config["model"],
            "sampling": config["sampling"],
            "budget": config["budget"],
            "allocation_policy": config["allocation_policy"],
            "record_count": len(records),
            "clause_count": len(plans),
            "fallback_plan_count": sum(plan.fallback_triggered for plan in plans),
            "reserved_call_count": len(requests),
            "plans": [plan.to_dict() for plan in plans],
            "allocations": allocations,
            "requests": requests,
            "safety": {
                "gold_read_or_modified": False,
                "llm_api_called": False,
                "network_called": False,
                "formal_predictions_written": False,
            },
        }
        rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.plan_out:
            target = args.plan_out.resolve()
            if not args.development:
                raise H1ContractError("--development is required for --plan-out")
            if not any(_is_under(target, root) for root in DEVELOPMENT_ROOTS):
                raise H1ContractError("S2.8 plans may be written only under a development directory")
            if target.exists():
                raise H1ContractError(f"refusing to overwrite: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
    except H1ContractError as exc:
        print(f"S2.8 H1 plan failed closed: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
