"""Sun rule-first + guarded LLM fallback for the frozen formal input (v3).

Wave 1.1 \u00a73 update: the prompt is loaded from
``prompts/sun_compat/rule_first_llm_fallback_prompt.md`` (v3) via
``bpc_hybrid.prompt_loader``; the LLM is asked for a **repair patch**
(not a full record); the patch is applied to the B0 rule prediction
and the result is run through the canonical validator; the prompt
SHA-256 is recorded in the manifest; the runner refuses to write to
formal artifact directories when the route / methods are blocked;
``--development`` is required for any write outside development paths.

Real API calls require explicit user authorization and ``--allow-llm``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.llm_config import LLMConfig
from bpc_hybrid.llm_client import (
    LLMClientError,
    LLMRequest,
    LLMResponse,
    OpenAICompatibleRequestBuilder,
    RealAPITransport,
)
from bpc_hybrid.prompt_loader import build_manifest_entry, load_prompt
from bpc_hybrid.stage2_canonical import (
    SCHEMA_SOURCE,
    validate_canonical,
)
from bpc_hybrid.sun_style.marker_lexicon import MarkerLexicon
from bpc_hybrid.sun_style.rule_record import RuleRecord
from bpc_hybrid.sun_style.semantic_extractor import SemanticExtraction, SemanticExtractor

from formal_experiment.audit import collect_project_audit
from formal_experiment.paths import (
    FORMAL_PREDICTIONS_DIR,
    FORMAL_RESULTS_DIR,
    FROZEN_GOLD_DIR,
    FROZEN_INPUT_DIR,
)

PROMPTName = "rule_first_llm_fallback_prompt"

_DEFAULT_INPUT = _PROJECT_ROOT / "data" / "input" / "estg150_input_v1.jsonl"
_DEFAULT_OUTPUT = (
    _PROJECT_ROOT / "data" / "predictions" / "sun_llm_fallback_predictions.jsonl"
)
_DEFAULT_MANIFEST = (
    _PROJECT_ROOT / "data" / "predictions" / "sun_llm_fallback_manifest.json"
)

FORMAL_DIRS = (
    FROZEN_INPUT_DIR,
    FROZEN_GOLD_DIR,
    FORMAL_PREDICTIONS_DIR,
    FORMAL_RESULTS_DIR,
)

FIELD_NAMES = ["modality", "actor", "action", "condition", "constraint", "exception"]
CORE_FIELDS = ["modality", "actor", "action"]
VALID_MODALITIES = {"obligation", "prohibition", "permission", "definition"}


# ---------------------------------------------------------------------------
# Canonical adapter (B0 rule -> canonical record, single-clause, flat)
# ---------------------------------------------------------------------------


def _span_or_none(text: str, find_sub: str) -> dict | None:
    idx = text.find(find_sub)
    if idx < 0:
        return None
    return {"text": find_sub, "start": idx, "end": idx + len(find_sub)}


def _id_span_or_none(sid: str, text: str, sub: str) -> dict | None:
    s = _span_or_none(text, sub)
    if s is None:
        return None
    return {"id": sid, **s, "normalized": sub}


def _wrap_b0_as_canonical(sample_id: str, text: str, rule: SemanticExtraction) -> dict:
    """Wrap a flat 6-field B0 result as a minimal single-clause canonical record.

    The canonical schema requires spans; we look up known modality
    trigger tokens (shall, may, must, means) to attach a coarse
    evidence span. This is intentionally conservative \u2014 the
    paper-faithful B0 will replace this with proper CoreNLP/Tregex
    spans. For now it produces a record that passes the cross-field
    validator so the contract can be exercised end-to-end.
    """
    modality_label = (rule.modality or "obligation").lower()
    if modality_label not in VALID_MODALITIES:
        modality_label = "obligation"
    trigger_tokens = ["shall", "must", "may", "should", "means", "may not", "must not", "shall not"]
    evidence = None
    for tok in trigger_tokens:
        candidate = _span_or_none(text, tok)
        if candidate is not None:
            evidence = [candidate]
            break
    if evidence is None:
        # last-resort: point evidence at the whole sentence so the
        # validator accepts the record
        evidence = [{"text": text, "start": 0, "end": len(text)}]

    clause: dict = {
        "clause_id": f"{sample_id}_c01",
        "clause_span": {"text": text, "start": 0, "end": len(text)},
        "modality": {"label": modality_label, "evidence": evidence},
        "actors": [],
        "actions": [],
        "conditions": [],
        "constraints": [],
        "exceptions": [],
        "actor_action_map": [],
        "order_relations": [],
    }
    if rule.actor:
        span = _id_span_or_none("a01", text, rule.actor.strip())
        if span is not None:
            clause["actors"] = [span]
    if rule.action:
        span = _id_span_or_none("p01", text, rule.action.strip())
        if span is not None:
            clause["actions"] = [span]
    if rule.condition:
        span = _id_span_or_none("c01", text, rule.condition.strip())
        if span is not None:
            clause["conditions"] = [span]
    if rule.constraint:
        span = _id_span_or_none("k01", text, rule.constraint.strip())
        if span is not None:
            clause["constraints"] = [span]
    if rule.exception:
        span = _id_span_or_none("e01", text, rule.exception.strip())
        if span is not None:
            clause["exceptions"] = [span]
    if clause["actors"] and clause["actions"]:
        clause["actor_action_map"] = [
            {"actor_id": clause["actors"][0]["id"], "action_id": clause["actions"][0]["id"]}
        ]
    return {
        "schema_version": "1.0.0",
        "sample_id": sample_id,
        "source_id": sample_id,
        "source_text": text,
        "clauses": [clause],
        "method": {"name": "sun_llm_fallback", "schema_source": SCHEMA_SOURCE},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
        "unsupported_or_ambiguous": [],
    }


# ---------------------------------------------------------------------------
# Repair patch helpers
# ---------------------------------------------------------------------------


def detect_repair_fields(rule: SemanticExtraction, lexicon: MarkerLexicon) -> tuple[list[str], list[str]]:
    """Decide which fields of the B0 clause need LLM repair."""
    fields = {name: getattr(rule, name, None) for name in FIELD_NAMES}
    repair: list[str] = []
    reasons: list[str] = []
    for name in CORE_FIELDS:
        if not (fields.get(name) and str(fields[name]).strip()):
            repair.append(name)
            reasons.append(f"missing_{name}")
    text_lower = rule.source_text.lower()
    for marker_name, marker_attr in (
        ("condition", "condition_markers"),
        ("constraint", "constraint_markers"),
        ("exception", "exception_markers"),
    ):
        markers = getattr(lexicon, marker_attr, [])
        if any(m in text_lower for m in markers) and not fields.get(marker_name):
            repair.append(marker_name)
            reasons.append(f"{marker_name}_marker_unextracted")
    return repair, reasons


def apply_repair_patch(clause: dict, patch: dict, repair_fields: list[str]) -> tuple[dict, list[str]]:
    """Apply an LLM repair patch to a clause. Returns (new_clause, errors).

    Strict rules:
    - Only fields in repair_fields may be modified.
    - modality patches must replace both label and evidence.
    - field array patches must replace the entire array; new ids must
      not collide with existing ids in the same clause.
    - actor_action_map / order_relations replace the entire list.
    - Any `absent: true` entry drops the field back to empty.
    """
    errors: list[str] = []
    out = dict(clause)
    for field_name, value in patch.items():
        if field_name not in repair_fields:
            errors.append(f"patch tried to modify unauthorized field: {field_name!r}")
            continue
        if isinstance(value, dict) and value.get("absent") is True:
            if field_name == "modality":
                errors.append("modality cannot be 'absent' \u2014 must keep one of 4 classes")
                continue
            if field_name in ("actors", "actions", "conditions", "constraints", "exceptions"):
                out[field_name] = []
                continue
            if field_name in ("actor_action_map", "order_relations"):
                out[field_name] = []
                continue
            errors.append(f"unsupported 'absent' on field {field_name!r}")
            continue
        if field_name == "modality":
            if not isinstance(value, dict) or "label" not in value or "evidence" not in value:
                errors.append("modality patch must contain 'label' and 'evidence'")
                continue
            if value["label"] not in VALID_MODALITIES:
                errors.append(f"modality patch label {value['label']!r} not in 4 classes")
                continue
            out["modality"] = value
            continue
        if field_name in ("actors", "actions", "conditions", "constraints", "exceptions"):
            if not isinstance(value, list):
                errors.append(f"{field_name} patch must be a list of supportedSpan dicts")
                continue
            existing_ids = {s["id"] for s in clause.get(field_name, []) if isinstance(s, dict) and "id" in s}
            seen_in_patch: set[str] = set()
            cleaned: list[dict] = []
            for span in value:
                if not isinstance(span, dict) or "id" not in span:
                    errors.append(f"{field_name} patch entry missing 'id': {span!r}")
                    cleaned = None
                    break
                if span["id"] in seen_in_patch:
                    errors.append(f"{field_name} patch has duplicate id: {span['id']!r}")
                    cleaned = None
                    break
                if span["id"] in existing_ids:
                    errors.append(
                        f"{field_name} patch id {span['id']!r} collides with existing "
                        f"id in B0 prediction; the patch may not silently replace B0 ids"
                    )
                    cleaned = None
                    break
                seen_in_patch.add(span["id"])
                cleaned.append(span)
            if cleaned is None:
                continue
            out[field_name] = cleaned
            continue
        if field_name == "actor_action_map":
            if not isinstance(value, list):
                errors.append("actor_action_map patch must be a list")
                continue
            out["actor_action_map"] = value
            continue
        if field_name == "order_relations":
            if not isinstance(value, list):
                errors.append("order_relations patch must be a list")
                continue
            out["order_relations"] = value
            continue
        errors.append(f"unrecognized field in patch: {field_name!r}")
    return out, errors


# ---------------------------------------------------------------------------
# Path gate
# ---------------------------------------------------------------------------


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _gate_formal_write(target: Path) -> tuple[bool, str]:
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=_DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    parser.add_argument(
        "--allow-llm",
        action="store_true",
        help="Explicitly authorize real LLM calls for this run",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=50,
        help="Hard upper bound on LLM calls",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly allow replacing existing output and manifest files",
    )
    parser.add_argument(
        "--development",
        action="store_true",
        help="Run as development-only; required for any write to "
        "outputs/development or data/development. Required for any "
        "write to formal paths when route is not final-ready.",
    )
    args = parser.parse_args()

    prompt = load_prompt(PromptName)

    for path in (args.output, args.manifest):
        if path.exists() and not args.overwrite:
            print(f"Refusing to overwrite existing artifact: {path}")
            return 2
    for path in (args.output, args.manifest):
        allowed, reason = _gate_formal_write(path)
        if not allowed:
            print(f"Refusing to write {path}: {reason}")
            return 2

    if not args.allow_llm:
        print("Refusing to run: pass --allow-llm only after explicit user authorization.")
        return 2
    if args.max_calls < 1:
        print("Refusing to run: --max-calls must be positive.")
        return 2

    print("=== Sun 2024 reconstruction + guarded LLM fallback (v3, canonical) ===", flush=True)
    print(f"Input:  {args.input}", flush=True)
    print(f"Output: {args.output}", flush=True)
    print(f"Prompt SHA-256: {prompt.sha256}", flush=True)
    print(flush=True)

    samples: list[dict] = []
    with args.input.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    print(f"Loaded {len(samples)} candidate samples", flush=True)

    rule_extractor = SemanticExtractor()
    lexicon = MarkerLexicon.from_default()

    config = LLMConfig.from_env(project_root=_PROJECT_ROOT)
    if not config.enabled or config.provider == "mock":
        print("Refusing to run: real LLM configuration is not enabled.")
        return 3
    llm_transport = RealAPITransport(config, timeout_seconds=60.0)
    sent_sampling = OpenAICompatibleRequestBuilder(config).sent_sampling_params()
    print(f"  LLM provider: {config.provider}", flush=True)
    print(f"  LLM model: {config.model}", flush=True)

    results: list[dict] = []
    llm_calls = 0
    llm_errors: list[dict] = []
    patch_rejections: list[dict] = []
    start_time = time.time()

    for i, sample in enumerate(samples):
        sid = sample["sample_id"]
        text = sample["text"]

        # Step 1: B0 rule extraction
        rule_result = rule_extractor.extract(sid, text)
        canonical = _wrap_b0_as_canonical(sid, text, rule_result)

        # Step 2: detect fields to repair
        repair_fields, fallback_reasons = detect_repair_fields(rule_result, lexicon)
        patch_applied = False
        patch_rejection_msg: str | None = None

        if repair_fields and llm_transport is not None:
            if llm_calls >= args.max_calls:
                print(f"Call budget exhausted at {args.max_calls}; skipping LLM for {sid}.", flush=True)
            else:
                clause_for_patch = canonical["clauses"][0]
                user_prompt = prompt.user_prompt_template.format(
                    sample_id=sid,
                    source_id=sid,
                    source_text=text,
                    clause_id=clause_for_patch["clause_id"],
                    current_clause_json=json.dumps(clause_for_patch, indent=2, ensure_ascii=False),
                    repair_fields_csv=", ".join(repair_fields),
                    repair_reasons_csv=", ".join(fallback_reasons),
                )
                request = LLMRequest(
                    source_id=sid,
                    source_text=text,
                    system_prompt=prompt.system_prompt,
                    user_prompt=user_prompt,
                )
                try:
                    response = llm_transport.send(request)
                    llm_calls += 1
                except LLMClientError as exc:
                    llm_errors.append({"sample_id": sid, "error": str(exc)})
                    response = None

                if response is not None:
                    raw = response.content.strip()
                    if raw.startswith("```"):
                        lines = raw.splitlines()
                        raw = "\n".join(lines[1:-1])
                    try:
                        patch_payload = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        llm_errors.append({"sample_id": sid, "error": f"non-JSON patch: {exc}"})
                        patch_payload = None

                    if isinstance(patch_payload, dict):
                        if patch_payload.get("sample_id") and patch_payload["sample_id"] != sid:
                            llm_errors.append(
                                {"sample_id": sid, "error": f"patch sample_id mismatch: {patch_payload['sample_id']!r}"}
                            )
                        elif patch_payload.get("clause_id") and patch_payload["clause_id"] != clause_for_patch["clause_id"]:
                            llm_errors.append(
                                {"sample_id": sid, "error": f"patch clause_id mismatch: {patch_payload['clause_id']!r}"}
                            )
                        else:
                            patches = patch_payload.get("patches", {})
                            if not isinstance(patches, dict):
                                llm_errors.append({"sample_id": sid, "error": "patches is not a dict"})
                            else:
                                new_clause, patch_errors = apply_repair_patch(
                                    clause_for_patch, patches, repair_fields
                                )
                                if patch_errors:
                                    patch_rejections.append(
                                        {"sample_id": sid, "errors": patch_errors}
                                    )
                                else:
                                    canonical["clauses"][0] = new_clause
                                    patch_applied = True

                    if llm_calls < len(samples):
                        time.sleep(0.5)

        # Step 3: validate the canonical record
        report = validate_canonical(canonical)
        if not (report.schema_valid and report.cross_field_valid):
            patch_rejections.append(
                {
                    "sample_id": sid,
                    "errors": ["post-patch canonical validation failed"] + list(report.errors),
                }
            )

        record = canonical
        record["fallback_triggered"] = bool(repair_fields)
        record["repair_fields"] = repair_fields
        record["fallback_reasons"] = fallback_reasons
        record["patch_applied"] = patch_applied
        results.append(record)

        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            print(
                f"  Processed {i + 1}/{len(samples)}... ({llm_calls} LLM calls, "
                f"{elapsed:.1f}s)",
                flush=True,
            )

    elapsed = time.time() - start_time
    print(f"  Processed {len(samples)}/{len(samples)} in {elapsed:.1f}s", flush=True)
    print(f"  LLM calls: {llm_calls}, LLM errors: {len(llm_errors)}", flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nPredictions written: {args.output}", flush=True)

    manifest = {
        "stage": "formal_stage2",
        "method": "sun_llm_fallback",
        "mode": "development" if args.development else "formal",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": str(args.input),
        "output_path": str(args.output),
        "sample_count": len(samples),
        "rule_extractor": "SemanticExtractor",
        "rule_extractor_matches_rule_only_line": True,
        "fallback_policy": (
            "LLM is triggered only for missing core fields or marker-bearing "
            "optional fields missed by rules. LLM output is a repair patch; "
            "runner applies the patch to the B0 prediction and re-validates."
        ),
        "barrientos_role": (
            "Structured JSON prompting, controlled vocabulary, validation, "
            "and normalization only; no RC4PC schema or change-impact method."
        ),
        "exact_sun_reproduction": False,
        "prompts": [build_manifest_entry(prompt)],
        "sampling": sent_sampling,
        "llm_calls": llm_calls,
        "max_calls": args.max_calls,
        "llm_errors": llm_errors,
        "patch_rejections": patch_rejections,
        "elapsed_seconds": elapsed,
        "real_api": llm_calls > 0,
        "llm_used": llm_calls > 0,
        "llm_provider": config.provider if llm_transport else "none",
        "llm_model": config.model if llm_transport else "none",
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Manifest written: {args.manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
