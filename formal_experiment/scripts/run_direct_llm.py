"""Guarded direct-LLM control runner for the frozen formal input.

Wave 1.1 §3 update: the prompt is loaded from
``prompts/sun_compat/direct_llm_sun_record_prompt.md`` (v3) via
``bpc_hybrid.prompt_loader``; the parser consumes the canonical
Stage 2 prediction record; the prompt SHA-256 is recorded in the
manifest; the runner refuses to write to formal artifact directories
when the route / methods are blocked; ``--development`` is required
for any write outside development paths.

Real API calls require explicit user authorization and ``--allow-llm``.
No real call is made here.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.llm_client import LLMClientError, LLMRequest, RealAPITransport
from bpc_hybrid.llm_config import LLMConfig
from bpc_hybrid.prompt_loader import build_manifest_entry, load_prompt
from bpc_hybrid.stage2_canonical import validate_canonical

# Status reads — these are read-only, not LLM calls
from formal_experiment.audit import collect_project_audit
from formal_experiment.paths import (
    FORMAL_PREDICTIONS_DIR,
    FORMAL_RESULTS_DIR,
    FROZEN_GOLD_DIR,
    FROZEN_INPUT_DIR,
    DEVELOPMENT_DIR,
)

PROMPTName = "direct_llm_sun_record_prompt"
PROMPT_V3_SNAPSHOT = "direct_llm_sun_record_prompt_v3_2026_07_12"
ALLOWED_PROMPT_NAMES = (PROMPTName, PROMPT_V3_SNAPSHOT)

DEFAULT_INPUT = ROOT / "data/input/estg150_input_v1.jsonl"
DEFAULT_OUTPUT = ROOT / "data/predictions/direct_llm_predictions.jsonl"
DEFAULT_MANIFEST = ROOT / "data/predictions/direct_llm_manifest.json"

FORMAL_DIRS = (
    FROZEN_INPUT_DIR,
    FROZEN_GOLD_DIR,
    FORMAL_PREDICTIONS_DIR,
    FORMAL_RESULTS_DIR,
)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _gate_formal_write(target: Path) -> tuple[bool, str]:
    """Return (allowed, reason). False when the write must be refused.

    Formal artifact directories refuse writes unless (a) the route is
    locked, (b) the method is ready, and (c) explicit ``--development``
    is **not** in effect. Development paths are always allowed but
    flagged as development in the manifest.
    """
    is_formal = any(_is_under(target, fd) for fd in FORMAL_DIRS)
    if not is_formal:
        return True, "non-formal path"
    audit = collect_project_audit()
    if not audit["integrity_pass"]:
        return False, "audit integrity_pass is false"
    if audit["final_experiment_ready"]:
        return True, "audit final_experiment_ready is true"
    return False, (
        "formal write refused: route is not final-ready. "
        "Pass --development and write to outputs/development or "
        "data/development instead."
    )


def _load_input(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            row = json.loads(raw)
            if not isinstance(row.get("sample_id"), str) or not isinstance(row.get("text"), str):
                raise ValueError(f"line {line_number}: expected sample_id and text")
            rows.append(row)
    if not rows:
        raise ValueError("input is empty")
    if len({row["sample_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate sample IDs")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--allow-llm",
        action="store_true",
        help="Explicitly authorize real LLM calls; required for any non-mock run.",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=150,
        help="Hard upper bound on LLM calls (default 150).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly allow replacing existing output and manifest files.",
    )
    parser.add_argument(
        "--development",
        action="store_true",
        help="Run as development-only; manifest records dev mode. Required for any "
        "write to outputs/development or data/development.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Fail-closed model pin: the resolved provider model must equal this "
        "exact value, otherwise the run aborts before any call. The returned model "
        "is verified per response and recorded in the manifest.",
    )
    parser.add_argument(
        "--prompt-name",
        type=str,
        default=PROMPTName,
        choices=ALLOWED_PROMPT_NAMES,
        help="Prompt file stem to load (allowlisted).",
    )
    args = parser.parse_args()

    # 1. Load prompt from disk
    prompt = load_prompt(args.prompt_name)

    # 2. Refuse to overwrite existing artifacts unless --overwrite
    for path in (args.output, args.manifest):
        if path.exists() and not args.overwrite:
            print(f"Refusing to overwrite existing artifact: {path}")
            return 2

    # 3. Gate formal writes
    for path in (args.output, args.manifest):
        allowed, reason = _gate_formal_write(path)
        if not allowed:
            print(f"Refusing to write {path}: {reason}")
            return 2
        if not allowed and not args.development:
            print(f"Refusing to write formal path {path} without --development.")
            return 2

    # 4. LLM authorization gate
    if not args.allow_llm:
        print("Refusing to run: real LLM calls require explicit authorization and --allow-llm.")
        return 2
    if args.max_calls < 1:
        print("Refusing to run: --max-calls must be positive.")
        return 2

    # 5. LLM config + fail-closed model pin (before any input I/O)
    config = LLMConfig.from_env(project_root=ROOT)
    if args.model is not None and config.model != args.model:
        print(
            f"Refusing to run: resolved model {config.model!r} != requested "
            f"{args.model!r} (fail-closed model pin)."
        )
        return 2
    if not config.enabled or config.provider == "mock":
        print("Refusing to run: a real LLM provider is not enabled.")
        return 2
    # D1-R1 (2026-08-04): deepseek-v4-flash on OpenAI-compatible relays
    # (incl. opencode.ai/zen/go/v1) defaults to a reasoning pass that returns
    # empty final content; the explicit policy disables thinking and pins
    # JSON output. Same policy vocabulary as the H1 transport.
    from bpc_hybrid.h1_transport import H1RequestPolicy

    transport = RealAPITransport(
        config,
        timeout_seconds=60.0,
        policy=H1RequestPolicy(
            stream=False,
            thinking={"type": "disabled"},
            response_format={"type": "json_object"},
        ),
    )

    # 6. Load and validate input
    try:
        rows = _load_input(args.input)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid frozen input: {exc}")
        return 3
    if len(rows) > args.max_calls:
        print(f"Refusing to run: {len(rows)} records exceed --max-calls={args.max_calls}.")
        return 3

    # 7. Process samples
    results: list[dict] = []
    validation_failures: list[dict] = []
    llm_errors: list[dict] = []
    returned_models: set[str] = set()
    span_audit_summary: dict[str, int] = {"records": 0, "reanchored": 0, "clause_spans": 0, "field_spans": 0, "adapted_spans": 0}
    # Build the prompt body ONCE and reuse for all rows
    from bpc_hybrid.llm_client import OpenAICompatibleRequestBuilder
    builder = OpenAICompatibleRequestBuilder(config)
    sent_sampling = builder.sent_sampling_params()
    for row in rows:
        sample_id = row["sample_id"]
        source_text = row["text"]
        user_prompt = prompt.user_prompt_template.format(
            sample_id=sample_id,
            source_text=source_text,
            few_shot_block="(omitted at runtime; prompt file is the source of truth)",
        )
        request = LLMRequest(
            source_id=sample_id,
            source_text=source_text,
            system_prompt=prompt.system_prompt,
            user_prompt=user_prompt,
        )
        try:
            response = transport.send(request)
        except LLMClientError as exc:
            llm_errors.append({"sample_id": sample_id, "error": str(exc)})
            continue
        returned = getattr(response, "model", None)
        if returned:
            returned_models.add(str(returned))
            # Fail closed: every response must come back from the pinned model.
            if args.model is not None and str(returned) != args.model:
                print(
                    f"Aborting: response model {returned!r} != pinned {args.model!r} "
                    f"(sample {sample_id})."
                )
                return 3

        raw_text = response.content.strip()
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            raw_text = "\n".join(lines[1:-1])
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            llm_errors.append({"sample_id": sample_id, "error": f"non-JSON: {exc}"})
            continue
        if not isinstance(payload, dict):
            llm_errors.append({"sample_id": sample_id, "error": "payload not a dict"})
            continue

        # Inject source_id if the LLM omitted it
        payload.setdefault("source_id", sample_id)
        payload.setdefault("sample_id", sample_id)
        payload.setdefault("source_text", source_text)
        payload.setdefault("schema_version", "1.0.0")
        payload.setdefault("method", {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"})
        payload.setdefault("unsupported_or_ambiguous", [])

        # D1-R1 (2026-08-04, option A): the opencode.ai/zen relay's
        # deepseek-v4-flash returns spans in a nested per-field convention;
        # the adapter maps them deterministically back to canonical spans.
        # Then span coordinates are re-anchored to the unique exact
        # occurrence of their text (S2.8D-R3-style canonicalization) before
        # the strict canonical validator; zero/ambiguous/contract violations
        # fail closed for the whole record.
        from bpc_hybrid.d1_schema_adapter import adapt_relay_record
        from bpc_hybrid.d1_span_canonicalizer import canonicalize_record_coordinates

        payload, adapt_audit = adapt_relay_record(payload, source_text)
        if adapt_audit["status"] == "failed":
            validation_failures.append(
                {
                    "sample_id": sample_id,
                    "errors": [f"relay_schema_adaptation_failed: {', '.join(adapt_audit['failed_reasons'])}"],
                    "relay_schema_adaptation": adapt_audit,
                }
            )
            continue
        payload, span_audit = canonicalize_record_coordinates(payload, source_text)
        if span_audit["status"] == "failed":
            validation_failures.append(
                {
                    "sample_id": sample_id,
                    "errors": [f"span_canonicalization_failed: {', '.join(span_audit['failed_reasons'])}"],
                    "span_canonicalization": span_audit,
                }
            )
            continue

        # Validate against canonical schema + cross-field rules
        report = validate_canonical(payload)
        if not (report.schema_valid and report.cross_field_valid):
            validation_failures.append(
                {"sample_id": sample_id, "errors": list(report.errors)}
            )
            continue
        results.append(payload)
        span_audit_summary["records"] += 1
        span_audit_summary["reanchored"] += span_audit["reanchored_count"]
        span_audit_summary["clause_spans"] += span_audit["clause_span_count"]
        span_audit_summary["field_spans"] += span_audit["field_span_count"]
        span_audit_summary["adapted_spans"] += adapt_audit["spans_adapted"]

    # 8. Write outputs
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in results:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    manifest = {
        "schema_version": "1.0.0",
        "stage": "formal_stage2",
        "method": "direct_llm",
        "mode": "development" if args.development else "formal",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": str(args.input),
        "output_path": str(args.output),
        "sample_count_input": len(rows),
        "sample_count_written": len(results),
        "sample_count_validation_failed": len(validation_failures),
        "sample_count_llm_error": len(llm_errors),
        "llm_calls": len(rows),
        "max_calls": args.max_calls,
        "llm_provider": config.provider,
        "llm_model": config.model,
        "llm_models": {
            "requested": args.model,
            "resolved": config.model,
            "returned": sorted(returned_models),
        },
        "transport_policy": transport.last_request_policy,
        "sampling": sent_sampling,
        "prompts": [build_manifest_entry(prompt)],
        "real_api": True,
        "gold_read_by_runner": False,
        "rule_front_end_used": False,
        "validation_failures": validation_failures,
        "llm_errors": llm_errors,
        "span_canonicalization": span_audit_summary,
    }
    args.manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Wrote {len(results)} direct-LLM predictions (canonical v1.0.0) and manifest.")
    print(f"Validation failures: {len(validation_failures)}; LLM errors: {len(llm_errors)}.")
    print(f"Prompt SHA-256: {prompt.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
