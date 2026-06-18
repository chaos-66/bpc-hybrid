"""R12.1 Synthetic Prototype Pilot Runner.

Executes a bounded single-call-per-sample real API pilot over
``data/prototype/legal_sentences.jsonl``.

This is a synthetic prototype pilot — NOT a benchmark, NOT a formal
dataset experiment, NOT method validation.

Usage (offline mock verification)::

    .\\.venv\\Scripts\\python.exe scripts\\run_synthetic_prototype_pilot.py \\
        --input data/prototype/legal_sentences.jsonl \\
        --max-samples 14 \\
        --output-dir outputs/r12_1_synthetic_prototype_pilot

Usage (real API, R12.1, ONE authorized run)::

    $env:BPC_HYBRID_DISABLE_PROJECT_ENV = ""
    .\\.venv\\Scripts\\python.exe scripts\\run_synthetic_prototype_pilot.py \\
        --execute-real-api \\
        --input data/prototype/legal_sentences.jsonl \\
        --max-samples 14 \\
        --output-dir outputs/r12_1_synthetic_prototype_pilot

Safety constraints (R12.1):

* At most 14 real API calls (1 per sample).
* Sequential execution only — no concurrency, no batching.
* No retry, no repair call.
* No raw model response saved to disk.
* No benchmark claim, no accuracy claim, no method-validation claim.
* Provider config read via safe ``LLMConfig.from_env()`` — never echoed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
_SCRIPTS_ROOT = _PROJECT_ROOT / "scripts"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from run_single_call_schema_smoke import run_single_call

# ---------------------------------------------------------------------------
# JSON-safe ArgumentParser
# ---------------------------------------------------------------------------


class _JsonArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that emits JSON error envelopes."""

    def error(self, message: str) -> None:
        print(
            json.dumps(
                {"error": f"CLI argument error: {message}", "stage": "R12.1"},
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)


# ---------------------------------------------------------------------------
# JSONL reader
# ---------------------------------------------------------------------------


def _read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file, returning list of parsed dicts."""
    samples: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            samples.append(json.loads(stripped))
    return samples


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------


def _build_summary(
    results: list[dict],
    input_file: str,
    sample_count: int,
    started_at: str,
    ended_at: str,
) -> dict:
    """Build the summary.json dict from per-sample results."""
    attempted = sum(r.get("attempted_call_count", 0) for r in results)
    successful = sum(r.get("successful_call_count", 0) for r in results)

    schema_valid = 0
    schema_invalid = 0
    api_error = 0
    config_blocked = 0

    for r in results:
        status = r.get("status", "unknown")
        if status == "schema_valid":
            schema_valid += 1
        elif status == "schema_invalid":
            schema_invalid += 1
        elif status == "api_error":
            api_error += 1
        elif status == "config_blocked":
            config_blocked += 1

    return {
        "stage": "R12.1",
        "dataset_type": "synthetic_prototype",
        "formal_benchmark": False,
        "method_validation": False,
        "input_file": input_file,
        "sample_count": sample_count,
        "attempted_call_count_total": attempted,
        "successful_call_count_total": successful,
        "schema_valid_count": schema_valid,
        "schema_invalid_count": schema_invalid,
        "api_error_count": api_error,
        "config_blocked_count": config_blocked,
        "raw_response_saved": False,
        "batch": False,
        "retry": False,
        "repair_call": False,
        "started_at": started_at,
        "ended_at": ended_at,
    }


# ---------------------------------------------------------------------------
# Per-sample status classifier
# ---------------------------------------------------------------------------


def _classify_status(meta: dict) -> str:
    """Classify a per-sample result into one of four statuses.

    Priority order:

    1. config_blocked — no real API call was attempted (config guard).
    2. api_error      — transport/network failure; LLM call was attempted
                        but the adapter threw a transport-level exception.
    3. schema_invalid — LLM responded, but normalizer or schema gate rejected
                        the output (successful_call_count may be 0 or >0).
    4. schema_valid   — LLM responded and schema gate accepted the output.
    """
    error = meta.get("error")
    attempted = meta.get("attempted_call_count", 0)
    successful = meta.get("successful_call_count", 0)
    schema_valid = meta.get("schema_valid", False)
    real_api = meta.get("real_api_call_performed", False)

    # ---- config_blocked: no API call was attempted ---------------------
    if not real_api and attempted == 0:
        return "config_blocked"

    # ---- Attempted but LLM did not return a schema-valid response ------
    if attempted > 0 and not schema_valid:
        # Transport-level failure (adapter threw, connection error, etc.)
        if error:
            err_lower = str(error).lower()
            transport_keywords = (
                "execution failed",
                "connection",
                "timeout",
                "dns",
                "refused",
                "network",
                "transport",
            )
            if any(kw in err_lower for kw in transport_keywords):
                return "api_error"
        # Normalizer rejected or schema gate didn't pass → schema_invalid
        return "schema_invalid"

    # ---- Schema gate passed --------------------------------------------
    if schema_valid:
        return "schema_valid"

    return "schema_invalid"


# ---------------------------------------------------------------------------
# Core pilot runner
# ---------------------------------------------------------------------------


def run_pilot(
    input_file: str,
    max_samples: int = 14,
    output_dir: str = "outputs/r12_1_synthetic_prototype_pilot",
    execute_real_api: bool = False,
    provider: str = "openai_compatible",
) -> tuple[list[dict], dict]:
    """Run the synthetic prototype pilot.

    Parameters
    ----------
    input_file : str
        Path to JSONL input file.
    max_samples : int
        Maximum number of samples to process (default 14).
    output_dir : str
        Directory for results.jsonl and summary.json.
    execute_real_api : bool
        When True, each sample triggers exactly ONE real API call.
    provider : str
        Provider name for real API calls.

    Returns
    -------
    tuple
        (results_list, summary_dict)
    """
    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    samples = _read_jsonl(input_path)[:max_samples]
    actual_count = len(samples)

    started_at = datetime.now(timezone.utc).isoformat()

    results: list[dict] = []
    for idx, sample in enumerate(samples):
        source_id = sample.get("id", f"unknown_{idx}")
        text = sample.get("text", "")

        print(
            f"[pilot] {idx + 1}/{actual_count} source_id={source_id} "
            f"text_len={len(text)}",
            flush=True,
        )

        meta = run_single_call(
            source_id=source_id,
            text=text,
            provider=provider,
            execute_real_api=execute_real_api,
        )

        # Add pilot-specific metadata
        status = _classify_status(meta)
        meta["status"] = status
        meta["pilot_stage"] = "R12.1"
        meta["dataset_type"] = "synthetic_prototype"
        meta["retry"] = False
        meta["repair_call"] = False

        results.append(meta)

        # Print progress
        print(
            f"  -> status={status} "
            f"schema_valid={meta.get('schema_valid', False)} "
            f"attempted={meta.get('attempted_call_count', 0)} "
            f"successful={meta.get('successful_call_count', 0)}",
            flush=True,
        )

    ended_at = datetime.now(timezone.utc).isoformat()

    summary = _build_summary(
        results=results,
        input_file=input_file,
        sample_count=actual_count,
        started_at=started_at,
        ended_at=ended_at,
    )

    # Write outputs
    results_path = output_path / "results.jsonl"
    with results_path.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary_path = output_path / "summary.json"
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)

    print(f"\n[pilot] Results written to {results_path}")
    print(f"[pilot] Summary written to {summary_path}")
    print(f"[pilot] Summary: {json.dumps(summary, indent=2, ensure_ascii=False)}")

    return results, summary


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = _JsonArgumentParser(
        description="R12.1 synthetic prototype pilot runner",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to JSONL input file (e.g., data/prototype/legal_sentences.jsonl).",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=14,
        help="Maximum number of samples (default: 14).",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/r12_1_synthetic_prototype_pilot",
        help="Output directory for results.jsonl and summary.json.",
    )
    parser.add_argument(
        "--execute-real-api",
        action="store_true",
        default=False,
        help=(
            "Execute at most 14 real API calls (1 per sample). "
            "No retry, no batch, no raw response saved."
        ),
    )
    parser.add_argument(
        "--provider",
        default="openai_compatible",
        help="LLM provider (default: openai_compatible).",
    )

    args = parser.parse_args(argv)

    try:
        results, summary = run_pilot(
            input_file=args.input,
            max_samples=args.max_samples,
            output_dir=args.output_dir,
            execute_real_api=args.execute_real_api,
            provider=args.provider,
        )
    except FileNotFoundError as exc:
        print(
            json.dumps({"error": str(exc), "stage": "R12.1"}, indent=2),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            json.dumps({"error": f"Pilot error: {exc}", "stage": "R12.1"}, indent=2),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
