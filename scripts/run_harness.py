# scripts/run_harness.py
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


def run_cmd(name: str, cmd: list[str], required: bool = True) -> dict:
    print(f"\n=== RUN: {name} ===")
    print("CMD:", " ".join(str(x) for x in cmd))

    result = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    record = {
        "name": name,
        "cmd": [str(x) for x in cmd],
        "returncode": result.returncode,
        "stdout": result.stdout[-8000:],
        "stderr": result.stderr[-8000:],
        "required": required,
    }

    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if required and result.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {result.returncode}")

    return record


def check_file_exists(path: Path, required: bool = True) -> dict:
    ok = path.exists()
    print(f"[CHECK] {path.relative_to(ROOT)}: {'OK' if ok else 'MISSING'}")

    if required and not ok:
        raise FileNotFoundError(f"Required file missing: {path}")

    return {
        "check": "file_exists",
        "path": str(path.relative_to(ROOT)),
        "ok": ok,
        "required": required,
    }


def main() -> int:
    started = datetime.now().isoformat(timespec="seconds")
    records = []

    try:
        records.append(check_file_exists(ROOT / "docs" / "AGENT_CONTRACT.md"))
        records.append(check_file_exists(ROOT / "docs" / "EXPERIMENT_GOAL.md"))
        records.append(check_file_exists(ROOT / "docs" / "METHOD_ALIGNMENT.md"))
        records.append(check_file_exists(ROOT / "docs" / "AUDIT_RULES.md"))
        records.append(check_file_exists(ROOT / "docs" / "CHECKPOINT_PROTOCOL.md"))
        records.append(check_file_exists(ROOT / "docs" / "RUN_LOG.md"))
        records.append(check_file_exists(ROOT / "docs" / "FAILURE_LOG.md"))
        records.append(check_file_exists(ROOT / "scripts" / "run_harness.py"))

        records.append(run_cmd("pytest", [sys.executable, "-m", "pytest", "-q"], required=True))

        records.append(run_cmd("run_rule_baseline", [sys.executable, "scripts/run_rule_baseline.py", "--input", "data/prototype/legal_sentences.jsonl"], required=False))
        records.append(run_cmd("evaluate_multi_clause", [sys.executable, "scripts/evaluate_multi_clause.py", "--gold", "data/prototype/gold_multiclause.jsonl", "--input", "data/prototype/legal_sentences.jsonl"], required=False))
        records.append(run_cmd("run_r15_sun_style_rule_only", [sys.executable, "scripts/run_r15_sun_style_rule_only.py"], required=False))

        status = "PASS"

    except Exception as e:
        status = "FAIL"
        records.append({
            "error": type(e).__name__,
            "message": str(e),
        })

    ended = datetime.now().isoformat(timespec="seconds")

    summary = {
        "status": status,
        "started": started,
        "ended": ended,
        "records": records,
    }

    out = LOG_DIR / "harness_last_run.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== HARNESS {status} ===")
    print(f"Log written to: {out.relative_to(ROOT)}")

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
