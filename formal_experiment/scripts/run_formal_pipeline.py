"""Guarded entry point for the formal experiment.

This script is intentionally conservative. It does not run final metrics while
the human-reviewed gold file is incomplete.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

FORMAL_ROOT = Path(__file__).resolve().parents[1]
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.status import collect_status, print_human
from formal_experiment.paths import METHODS_CONFIG
from formal_experiment.audit import collect_project_audit


def _load_methods() -> list[dict]:
    data = json.loads(METHODS_CONFIG.read_text(encoding="utf-8"))
    return data.get("methods", [])


def _print_commands(methods: list[dict]) -> None:
    print("Formal candidate commands")
    print("=" * 32)
    for method in methods:
        command = method.get("current_command")
        print(f"{method['id']}:")
        print(f"  command: {command or '(not implemented)'}")
        if method.get("planned_command"):
            print(f"  planned command: {method['planned_command']}")
        print(f"  status: {method['formal_status']}")
        print(f"  notes: {method['notes']}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true", help="Print status and exit")
    parser.add_argument("--list-commands", action="store_true", help="List formal commands and exit")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute candidate commands only after the full readiness gate passes",
    )
    parser.add_argument(
        "--allow-llm",
        action="store_true",
        help="Explicitly authorize configured LLM methods after readiness passes",
    )
    args = parser.parse_args()

    status = collect_status()
    audit = collect_project_audit()
    methods = _load_methods()

    if args.status:
        print_human(status)
        return 0

    if args.list_commands or not args.execute:
        _print_commands(methods)
        if not audit["final_experiment_ready"]:
            print(
                "Guard: final execution is blocked. Run audit_project.py "
                "--require-final-ready for the canonical blocker list."
            )
        return 0

    if not audit["final_experiment_ready"]:
        print_human(status)
        print()
        print(
            "Refusing to execute final formal pipeline: the canonical "
            "final-readiness audit is blocked."
        )
        return 2

    if any(method.get("llm_used") for method in methods) and not args.allow_llm:
        print(
            "Refusing to execute LLM methods without the explicit --allow-llm gate. "
            "User authorization and the API call budget must also be recorded."
        )
        return 3

    for method in methods:
        configured_command = method.get("current_command")
        if not configured_command:
            print(f"Refusing to execute {method['id']}: no implemented command is configured.")
            return 4
        command = configured_command.split()
        # Wave 1.1 \u00a77: pass --allow-llm and a hard --max-calls budget
        # down to the runner, instead of only checking the outer gate.
        if method.get("llm_used"):
            command = list(command) + ["--allow-llm", "--max-calls", "50"]
        print(f"Running {method['id']}: {' '.join(command)}")
        completed = subprocess.run(command, cwd=FORMAL_ROOT, check=False)
        if completed.returncode != 0:
            print(f"Method failed: {method['id']} exit={completed.returncode}")
            return completed.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
