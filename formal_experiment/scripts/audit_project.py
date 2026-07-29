"""Run the mandatory offline integrity check for the formal experiment.

The filename is retained for compatibility.  This is an automated project
check, not a third-party or institutional audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


FORMAL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = FORMAL_ROOT
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.audit import collect_project_audit, print_human


TEST_TARGETS = ("tests",)
VERIFICATION_RECEIPT = PROJECT_ROOT / ".tmp" / "last_verified_tests.json"
_FINGERPRINT_SKIP_DIRS = {".tmp", ".pytest_cache", "__pycache__"}


def _state_fingerprint() -> str:
    """Hash the active capsule without reading secrets or generated caches."""

    digest = hashlib.sha256()
    for root, dirs, files in os.walk(PROJECT_ROOT, topdown=True, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in _FINGERPRINT_SKIP_DIRS)
        root_path = Path(root)
        for name in sorted(files):
            path = root_path / name
            relative = path.relative_to(PROJECT_ROOT).as_posix()
            if path.name == ".env":
                continue
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            if path.is_symlink():
                digest.update(b"SYMLINK\0")
                digest.update(os.readlink(path).encode("utf-8"))
            else:
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
            digest.update(b"\0")
    return digest.hexdigest()


def _test_summary(output: str) -> str:
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if any(word in stripped for word in ("passed", "failed", "error", "errors")):
            return stripped
    return "test summary unavailable"


def _clear_verification_receipt() -> None:
    VERIFICATION_RECEIPT.unlink(missing_ok=True)


def _write_verification_receipt(test_result: dict[str, object]) -> None:
    """Persist a passing test result bound to the exact active-file state."""

    if not test_result["passed"]:
        _clear_verification_receipt()
        return
    VERIFICATION_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "state_sha256": _state_fingerprint(),
        "returncode": int(test_result["returncode"]),
        "passed": bool(test_result["passed"]),
        "test_summary": _test_summary(str(test_result["output"])),
        "command": [str(part) for part in test_result["command"]],
    }
    temporary = VERIFICATION_RECEIPT.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(VERIFICATION_RECEIPT)


def load_matching_verification_receipt() -> dict[str, object] | None:
    """Return reusable test evidence only when the active state is unchanged."""

    try:
        payload = json.loads(VERIFICATION_RECEIPT.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if (
        payload.get("schema_version") != "1.0"
        or payload.get("passed") is not True
        or payload.get("returncode") != 0
        or payload.get("state_sha256") != _state_fingerprint()
    ):
        return None
    return {
        "command": payload.get("command", []),
        "returncode": 0,
        "passed": True,
        "output": str(payload.get("test_summary", "test summary unavailable")),
        "source": "verified_receipt",
        "receipt_created_at_utc": payload.get("created_at_utc"),
        "state_sha256": payload["state_sha256"],
    }


def _run_tests() -> dict[str, object]:
    (PROJECT_ROOT / ".tmp").mkdir(parents=True, exist_ok=True)
    base_temp = PROJECT_ROOT / ".tmp" / f"formal-audit-pytest-{os.getpid()}"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "--basetemp",
        str(base_temp),
        *TEST_TARGETS,
    ]
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            env=environment,
        )
        return {
            "command": command,
            "returncode": completed.returncode,
            "passed": completed.returncode == 0,
            "output": completed.stdout,
        }
    finally:
        shutil.rmtree(base_temp, ignore_errors=True)


def _console_safe(value: str) -> str:
    """Keep diagnostic output printable on Windows legacy code pages."""
    encoding = sys.stdout.encoding or "utf-8"
    return value.encode(encoding, errors="replace").decode(encoding)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument(
        "--with-tests",
        action="store_true",
        help="Run the focused offline regression suite after auditing",
    )
    parser.add_argument(
        "--require-human-review-ready",
        action="store_true",
        help="Return exit code 2 unless the blank manual-review package is ready",
    )
    parser.add_argument(
        "--require-final-ready",
        action="store_true",
        help="Return exit code 2 while final experiment readiness is blocked",
    )
    args = parser.parse_args()

    audit = collect_project_audit()
    if args.with_tests:
        _clear_verification_receipt()
        test_result = _run_tests()
        audit["test_result"] = test_result
        if not test_result["passed"]:
            audit["integrity_pass"] = False
            audit["findings"]["errors"].append(
                {
                    "code": "active_tests_failed",
                    "message": "The active offline regression suite failed.",
                }
            )
            audit["final_experiment_ready"] = False
        else:
            _write_verification_receipt(test_result)

    if args.json:
        print(json.dumps(audit, indent=2, ensure_ascii=False))
    else:
        print_human(audit)
        if args.with_tests:
            print()
            print("Active offline tests")
            print("=" * 40)
            print(_console_safe(audit["test_result"]["output"].rstrip()))

    if not audit["integrity_pass"]:
        return 1
    if args.require_human_review_ready and not audit["human_review_ready"]:
        return 2
    if args.require_final_ready and not audit["final_experiment_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
