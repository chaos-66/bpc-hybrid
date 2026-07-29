"""Build the locked S2.9 direct-LLM request plan without calling an API.

This entry point is intentionally offline.  It renders the exact v4 prompt,
including all four few-shot examples, and emits only a request plan.  Passing
``--allow-llm`` fails closed; a real run needs a later explicit authorization
and a separately audited transport task.
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

from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from bpc_hybrid.sun_style.d1_direct import (  # noqa: E402
    D1ContractError,
    assert_input_path_allowed,
    build_request_plan,
    load_s29_config,
    sha256_file,
)


PromptName = "direct_llm_sun_record_prompt"
DEFAULT_CONFIG = ROOT / "configs" / "models" / "sun_d1_s29.json"
DEFAULT_INPUT = ROOT / "tests" / "fixtures" / "d1_s29" / "s29_offline_contract_fixture.json"
DEVELOPMENT_ROOTS = (
    ROOT / "outputs" / "development",
    ROOT / "data" / "development",
)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _load_rows(path: Path) -> list[dict[str, Any]]:
    try:
        if path.suffix.lower() == ".jsonl":
            rows: list[dict[str, Any]] = []
            with path.open("r", encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, start=1):
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise D1ContractError(f"input line {line_number} is not an object")
                    rows.append(value)
            return rows
        value = json.loads(path.read_text(encoding="utf-8"))
    except D1ContractError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise D1ContractError(f"invalid D1 input: {path}") from exc
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        return value["rows"]
    if isinstance(value, list):
        return value
    raise D1ContractError("D1 JSON input must be an array or an object containing rows")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--plan-out", type=Path)
    parser.add_argument(
        "--max-calls",
        type=int,
        default=750,
        help="Offline hard ceiling; must be in 1..750 and cover the rendered request plan.",
    )
    parser.add_argument("--development", action="store_true")
    parser.add_argument(
        "--allow-llm",
        action="store_true",
        help="Reserved for a later separately authorized task; S2.9 always refuses it.",
    )
    args = parser.parse_args()

    if args.allow_llm:
        print("Refusing real LLM use: S2.9 verifies only offline prompt and request planning.")
        return 2
    try:
        config_path = args.config.resolve()
        input_path = args.input.resolve()
        config = load_s29_config(config_path)
        assert_input_path_allowed(input_path, config)
        prompt = load_prompt(PromptName)
        if prompt.sha256 != config["prompt"]["sha256"]:
            raise D1ContractError("D1 prompt SHA-256 changed")
        rows = _load_rows(input_path)
        plan = build_request_plan(rows, prompt, config)
        plan["gold_read_by_runner"] = False
        if not 1 <= args.max_calls <= config["budget"]["absolute_max_calls"]:
            raise D1ContractError("--max-calls must be between 1 and the locked ceiling 750")
        if plan["request_count"] > args.max_calls:
            raise D1ContractError(
                f"request plan has {plan['request_count']} calls, exceeding --max-calls={args.max_calls}"
            )
        plan["config"] = {
            "path": config_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(config_path),
        }
        plan["prompt"] = {
            "path": prompt.path.relative_to(ROOT).as_posix(),
            "sha256": prompt.sha256,
            "few_shot_count": len(prompt.few_shot_examples),
        }
        rendered = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
        if args.plan_out:
            target = args.plan_out.resolve()
            if not args.development:
                raise D1ContractError("--development is required for --plan-out")
            if not any(_is_under(target, root) for root in DEVELOPMENT_ROOTS):
                raise D1ContractError("S2.9 plans may be written only under a development directory")
            if target.exists():
                raise D1ContractError(f"refusing to overwrite: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
            print(json.dumps({"status": "succeeded", "plan": str(target)}, ensure_ascii=False))
        else:
            print(rendered, end="")
    except (D1ContractError, ValueError) as exc:
        print(f"S2.9 D1 plan failed closed: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
