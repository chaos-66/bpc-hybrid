# -*- coding: utf-8 -*-
"""Zero-network preparation for SEP-C3 condition-preservation validation.

This script does not read ``.env``, does not construct a transport, and never
performs an API call.  It renders the three frozen prompt arms, checks the two
old-arm equivalences and the single RC_KEEP addition, freezes a 450-entry
sample-level schedule, and writes an auditable request-body hash manifest.

The old targeted-refinement runner is intentionally NOT reused for execution.
This round only prepares materials; real execution requires a new explicit
user authorization and a separate reviewed runner entry.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import itertools
import json
import math
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_sep_c3_modular_ablation_v1 as core  # noqa: E402
import bpc_hybrid.sep_c3_condition_preservation_prompt as cp  # noqa: E402


SUITE_ID = "SEP-C3-CONDITION-PRESERVATION-001"
ARMS = cp.ARMS
SAMPLES_PER_ARM = 150
PLANNED_CALLS = 450
CALL_CAP = 450
REPEAT_ID = "repeat-01"
SCHEDULE_SEED = 20260919
BOOTSTRAP_SEED = 20260919
BOOTSTRAP_RESAMPLES = 10_000

MODEL_ALIAS = core.MODEL_ALIAS
MODEL_RELEASE = core.MODEL_RELEASE
TEMPERATURE = core.TEMPERATURE
TOP_P = core.TOP_P
MAX_TOKENS = core.MAX_TOKENS
EXPECTED_INFERENCE = {
    "temperature": TEMPERATURE,
    "top_p": TOP_P,
    "max_tokens": MAX_TOKENS,
    "retry": 0,
    "stream": False,
    "thinking": {"type": "disabled"},
    "response_format": None,
}

PROMPT_DIR = cp.PROMPT_DIR
GENERATED_DIR = cp.GENERATED_DIR
PROMPT_MANIFEST_PATH = cp.generated_manifest_path()
SCHEDULE_PATH = ROOT / "configs" / "sep_c3_condition_preservation_schedule_v1.json"
BUDGET_PATH = ROOT / "configs" / "sep_c3_condition_preservation_budget_v1.json"
REPORTS_DIR = ROOT / "outputs" / "reports"
EVIDENCE_DIR = ROOT / "outputs" / "evidence" / "sep_c3_condition_preservation_v1"
OFFLINE_REQUESTS_PATH = EVIDENCE_DIR / "offline_requests.jsonl"
PROMPT_AUDIT_PATH = REPORTS_DIR / "sep_c3_condition_preservation_v1_prompt_audit.json"
OFFLINE_AUDIT_PATH = REPORTS_DIR / "sep_c3_condition_preservation_v1_offline_render_audit.json"
PREPARE_AUDIT_PATH = REPORTS_DIR / "sep_c3_condition_preservation_v1_prepare_audit.json"
PREFLIGHT_JSON_PATH = REPORTS_DIR / "sep_c3_condition_preservation_v1_preflight.json"
PREFLIGHT_MD_PATH = REPORTS_DIR / "sep_c3_condition_preservation_v1_preflight.md"
RULES_PATH = REPORTS_DIR / "sep_c3_condition_preservation_v1_judgment_rules.json"
CONFIG_DIFF_PATH = REPORTS_DIR / "sep_c3_condition_preservation_v1_config_diff.json"
DIFF_DIR = REPORTS_DIR / "sep_c3_condition_preservation_v1_prompt_diffs"
OLD_TARGETED_EXECUTION = (
    REPORTS_DIR / "sep_c3_targeted_refinement_v1_execution.json"
)
BOOTSTRAP_SCRIPT_PATH = (
    ROOT / "scripts" / "analyze_sep_c3_condition_preservation_bootstrap_v1.py"
)

ADAPTER_PATH = ROOT / "src" / "bpc_hybrid" / "d1_schema_adapter.py"
CANONICALIZER_PATH = ROOT / "src" / "bpc_hybrid" / "d1_span_canonicalizer.py"
VALIDATOR_PATH = ROOT / "src" / "bpc_hybrid" / "stage2_canonical.py"
SCHEMA_PATH = ROOT / "configs" / "schemas" / "stage2_prediction.schema.json"
COARSE_EVALUATOR_PATH = ROOT / "src" / "bpc_hybrid" / "sep_c3_modular_evaluation.py"
FROZEN_EVALUATOR_PATH = ROOT / "src" / "bpc_hybrid" / "stage2_sun_literal_overlap.py"
COARSE_VIEW_PATH = ROOT / "src" / "bpc_hybrid" / "g04_coarse_view.py"

LOCKED_VALIDATION_BACKEND = "lightweight"
PROCESSING_PATH_VERSION = "sep_c3_condition_preservation_validation_path_v1"


class PrepareError(RuntimeError):
    """A zero-network preparation precondition failed."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PrepareError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [row for row in rows if isinstance(row, dict)]


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    _write_text(
        path,
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
    )


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request_body(arm: str, sample_id: str, source_text: str) -> dict[str, Any]:
    prompt = cp.render_condition_preservation_prompt(arm)
    return {
        "model": MODEL_ALIAS,
        "messages": prompt.request_messages(sample_id, source_text),
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
        "stream": False,
        "thinking": {"type": "disabled"},
    }


def _canonical_body_bytes(body: Mapping[str, Any]) -> bytes:
    return json.dumps(
        body, ensure_ascii=False, sort_keys=True
    ).encode("utf-8")


def _estimated_input_tokens(body: Mapping[str, Any]) -> int:
    # Matching the existing project budget convention: rough bytes / 3.
    return math.ceil(len(_canonical_body_bytes(body)) / 3)


def _sent_text(prompt: cp.ConditionPreservationPrompt) -> str:
    return (
        prompt.system_prompt
        + "\n\n<!--USER-->\n\n"
        + prompt.user_prompt_template
    )


def _detect_validation_backend() -> dict[str, Any]:
    try:
        import jsonschema  # type: ignore  # noqa: F401
    except ImportError:
        return {
            "detected_backend": "lightweight",
            "jsonschema_available": False,
            "locked_backend": LOCKED_VALIDATION_BACKEND,
            "locked_matches_detected": (
                LOCKED_VALIDATION_BACKEND == "lightweight"
            ),
            "detail": (
                "stage2_canonical.validate_canonical() uses the in-process "
                "structural + cross-field checks; jsonschema is not installed"
            ),
        }
    return {
        "detected_backend": "jsonschema",
        "jsonschema_available": True,
        "locked_backend": LOCKED_VALIDATION_BACKEND,
        "locked_matches_detected": (
            LOCKED_VALIDATION_BACKEND == "jsonschema"
        ),
        "detail": (
            "jsonschema is installed; the runtime validator would use the "
            "Draft202012 path unless the execution environment is pinned "
            "back to the lightweight backend"
        ),
    }


def _input_rows() -> list[dict[str, str]]:
    rows = core.samples(SAMPLES_PER_ARM)
    if len(rows) != SAMPLES_PER_ARM:
        raise PrepareError("frozen EStG input did not return 150 rows")
    if len({row["sample_id"] for row in rows}) != SAMPLES_PER_ARM:
        raise PrepareError("frozen EStG input sample ids are not unique")
    return rows


def _permutations() -> list[tuple[str, str, str]]:
    values = list(itertools.permutations(ARMS))
    if len(values) != 6:
        raise PrepareError("expected six arm permutations")
    return [(str(a), str(b), str(c)) for a, b, c in values]


def _permutation_key(permutation: Sequence[str]) -> str:
    return ">".join(permutation)


def build_schedule(input_rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    perms = _permutations()
    labels: list[tuple[str, str, str]] = []
    for permutation in perms:
        labels.extend([permutation] * 25)
    if len(labels) != SAMPLES_PER_ARM:
        raise PrepareError("schedule permutation labels must total 150")
    rng = random.Random(SCHEDULE_SEED)
    rng.shuffle(labels)

    permutation_counts = Counter(_permutation_key(p) for p in labels)
    if any(count != 25 for count in permutation_counts.values()):
        raise PrepareError("each of the six permutations must appear 25 times")

    entries: list[dict[str, Any]] = []
    for sample_order_index, row in enumerate(input_rows):
        sample_id = str(row["sample_id"])
        permutation = labels[sample_order_index]
        for arm_position, arm in enumerate(permutation):
            entries.append({
                "execution_index": len(entries),
                "sample_order_index": sample_order_index,
                "sample_id": sample_id,
                "arm": arm,
                "arm_order_within_sample": arm_position,
                "sample_permutation": _permutation_key(permutation),
            })

    canonical = json.dumps(
        entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    schedule_sha256 = _sha256_text(canonical)
    return {
        "schema_version": "sep_c3_condition_preservation_schedule@1.0.0",
        "suite_id": SUITE_ID,
        "scheme": "sample_level_six_permutations_25_each_seed_20260919",
        "runtime_seed": SCHEDULE_SEED,
        "rng": "python random.Random(seed).shuffle",
        "permutation_order": [_permutation_key(p) for p in perms],
        "permutation_counts": dict(sorted(permutation_counts.items())),
        "interleaving": {
            "level": "sample_level",
            "arms_per_block": len(ARMS),
            "block_count": len(input_rows),
            "arm_order_fixed_per_sample": True,
            "schedule_frozen_before_run": True,
        },
        "arms": list(ARMS),
        "samples_per_arm": len(input_rows),
        "planned_calls": len(entries),
        "input_path": _relative(core.ESTG_INPUT),
        "input_sha256": _sha256_file(core.ESTG_INPUT),
        "entries": entries,
        "schedule_sha256": schedule_sha256,
        "generated_at_utc": _utc_now(),
    }


def _offline_rows(
    schedule: Mapping[str, Any],
    input_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    sample_by_id = {str(row["sample_id"]): row for row in input_rows}
    rows: list[dict[str, Any]] = []
    for entry in schedule["entries"]:
        arm = str(entry["arm"])
        sid = str(entry["sample_id"])
        source_text = str(sample_by_id[sid]["text"])
        prompt = cp.render_condition_preservation_prompt(arm)
        user = prompt.render_user(sid, source_text)
        body = _request_body(arm, sid, source_text)
        body_bytes = _canonical_body_bytes(body)
        rows.append({
            "execution_index": int(entry["execution_index"]),
            "sample_order_index": int(entry["sample_order_index"]),
            "sample_id": sid,
            "arm": arm,
            "arm_order_within_sample": int(entry["arm_order_within_sample"]),
            "sample_permutation": str(entry["sample_permutation"]),
            "request_body": body,
            "request_body_sha256": _sha256_bytes(body_bytes),
            "system_prompt_sha256": _sha256_text(prompt.system_prompt),
            "user_prompt_sha256": _sha256_text(user),
            "prompt_composition_sha256": prompt.composition_sha256,
            "request_body_chars": len(body_bytes.decode("utf-8")),
            "estimated_input_tokens_bytes_div_3": math.ceil(
                len(body_bytes) / 3
            ),
            "max_tokens": MAX_TOKENS,
        })
    return rows


def _offline_audit(
    schedule: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    *,
    offline_requests_sha256: str,
) -> dict[str, Any]:
    arm_counts = Counter(str(row["arm"]) for row in rows)
    sample_counts = Counter(str(row["sample_id"]) for row in rows)
    permutation_by_sample: dict[str, str] = {}
    for row in rows:
        permutation_by_sample[str(row["sample_id"])] = str(
            row["sample_permutation"]
        )
    permutation_counts = Counter(permutation_by_sample.values())
    arm_tokens: dict[str, int] = {}
    for arm in ARMS:
        arm_tokens[arm] = sum(
            int(row["estimated_input_tokens_bytes_div_3"])
            for row in rows
            if str(row["arm"]) == arm
        )
    hashes = [str(row["request_body_sha256"]) for row in rows]
    errors: list[str] = []
    if len(rows) != PLANNED_CALLS:
        errors.append(f"offline request count {len(rows)} != {PLANNED_CALLS}")
    if set(arm_counts) != set(ARMS) or any(
        arm_counts[arm] != SAMPLES_PER_ARM for arm in ARMS
    ):
        errors.append("offline per-arm count is not 150")
    if len(sample_counts) != SAMPLES_PER_ARM or any(
        count != len(ARMS) for count in sample_counts.values()
    ):
        errors.append("offline sample blocks are not exactly three arms")
    if any(count != 25 for count in permutation_counts.values()):
        errors.append("offline schedule does not use each permutation 25 times")
    if len(set(hashes)) != len(hashes):
        errors.append("offline request body hashes are not unique")
    for row in rows:
        expected = _sha256_bytes(
            _canonical_body_bytes(row["request_body"])
        )
        if expected != row["request_body_sha256"]:
            errors.append(
                f"request body hash mismatch at index {row['execution_index']}"
            )
            break
    return {
        "schema_version": "sep_c3_condition_preservation_offline_render@1.0.0",
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "attempt_count": len(rows),
        "expected_attempts": PLANNED_CALLS,
        "sample_count": len(sample_counts),
        "arm_attempt_counts": {arm: arm_counts[arm] for arm in ARMS},
        "permutation_counts": dict(sorted(permutation_counts.items())),
        "unique_request_body_sha256_count": len(set(hashes)),
        "estimated_input_tokens_per_arm_bytes_div_3": arm_tokens,
        "estimated_input_tokens_total_bytes_div_3": sum(arm_tokens.values()),
        "max_tokens_per_call": MAX_TOKENS,
        "output_token_ceiling": len(rows) * MAX_TOKENS,
        "total_token_ceiling": (
            sum(arm_tokens.values()) + len(rows) * MAX_TOKENS
        ),
        "request_bodies_path": _relative(OFFLINE_REQUESTS_PATH),
        "request_bodies_sha256": offline_requests_sha256,
    }


def _prompt_audit(
    prompts: Mapping[str, cp.ConditionPreservationPrompt],
) -> dict[str, Any]:
    old_b, old_d = cp._frozen_old_prompts()
    checks: dict[str, bool] = {}
    errors: list[str] = []

    def require(condition: bool, name: str, detail: str = "") -> None:
        checks[name] = bool(condition)
        if not condition:
            errors.append(detail or name)

    require(set(prompts) == set(ARMS), "three_arms_rendered")
    require(
        prompts["BASE"].system_prompt == old_b.system_prompt,
        "BASE_system_equals_old_B",
    )
    require(
        prompts["BASE"].user_prompt_template == old_b.user_prompt_template,
        "BASE_user_equals_old_B",
    )
    require(
        prompts["BASE"].composition_sha256 == old_b.composition_sha256,
        "BASE_sent_composition_equals_old_B",
    )
    require(
        prompts["RC1"].system_prompt == old_d.system_prompt,
        "RC1_system_equals_old_D",
    )
    require(
        prompts["RC1"].user_prompt_template == old_d.user_prompt_template,
        "RC1_user_equals_old_D",
    )
    require(
        prompts["RC1"].composition_sha256 == old_d.composition_sha256,
        "RC1_sent_composition_equals_old_D",
    )
    require(
        prompts["RC_KEEP"].user_prompt_template
        == prompts["RC1"].user_prompt_template,
        "RC_KEEP_user_unchanged_from_RC1",
    )
    require(
        prompts["RC_KEEP"].system_prompt
        == prompts["RC1"].system_prompt
        + "\n\n"
        + cp.CONDITION_PRESERVATION_TEXT,
        "RC_KEEP_is_exactly_RC1_plus_one_sentence",
    )
    require(
        prompts["RC_KEEP"].system_prompt.count(
            cp.CONDITION_PRESERVATION_TEXT
        ) == 1,
        "one_sentence_occurrence",
    )
    base_vs_rc1 = "".join(
        difflib.unified_diff(
            _sent_text(prompts["BASE"]).splitlines(keepends=True),
            _sent_text(prompts["RC1"]).splitlines(keepends=True),
            fromfile="BASE_sent_prompt.txt",
            tofile="RC1_sent_prompt.txt",
            n=2,
        )
    )
    rc1_vs_keep = "".join(
        difflib.unified_diff(
            _sent_text(prompts["RC1"]).splitlines(keepends=True),
            _sent_text(prompts["RC_KEEP"]).splitlines(keepends=True),
            fromfile="RC1_sent_prompt.txt",
            tofile="RC_KEEP_sent_prompt.txt",
            n=2,
        )
    )
    added = [
        line
        for line in rc1_vs_keep.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    meaningful_added = [line for line in added if line.strip() != "+"]
    removed = [
        line
        for line in rc1_vs_keep.splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]
    require(
        meaningful_added == ["+" + cp.CONDITION_PRESERVATION_TEXT]
        and not removed,
        "RC1_vs_RC_KEEP_diff_only_one_sentence",
        "RC1 vs RC_KEEP diff is not exactly one added sentence",
    )
    for arm, prompt in prompts.items():
        text = _sent_text(prompt)
        require(
            "Semantic interpretation rules" not in text,
            f"{arm}_no_S_marker",
        )
        require(
            "Output organization" not in text
            and "Return one bare JSON object" not in text,
            f"{arm}_no_J_marker",
        )
    require(
        prompts["BASE"].source_hashes.get("R_A")
        == old_b.source_hashes.get("R_A"),
        "BASE_R_A_source_hash_unchanged",
    )
    require(
        prompts["RC1"].source_hashes.get("R_C")
        == old_b.source_hashes.get("R_C"),
        "RC1_old_R_C_source_hash_unchanged",
    )
    return {
        "schema_version": "sep_c3_condition_preservation_prompt_audit@1.0.0",
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "checks": checks,
        "base_vs_rc1_diff": base_vs_rc1,
        "rc1_vs_rc_keep_diff": rc1_vs_keep,
        "old_R_C_text": cp.rp.R_C_TEXT,
        "old_R_C_text_sha256": _sha256_text(cp.rp.R_C_TEXT),
        "new_sentence_text": cp.CONDITION_PRESERVATION_TEXT,
        "new_sentence_sha256": _sha256_text(cp.CONDITION_PRESERVATION_TEXT),
    }


def _runtime_estimate() -> dict[str, Any]:
    if not OLD_TARGETED_EXECUTION.is_file():
        return {
            "status": "unavailable",
            "reason": "old targeted execution summary not found",
        }
    old = _read_json(OLD_TARGETED_EXECUTION)
    calls = int(old.get("actual_calls") or 0)
    seconds = float(old.get("runtime_seconds") or 0.0)
    if calls <= 0 or seconds <= 0:
        return {
            "status": "unavailable",
            "reason": "old targeted execution summary lacks usable calls/seconds",
        }
    per_call = seconds / calls
    estimate = per_call * PLANNED_CALLS
    return {
        "status": "historical_throughput_reference_only",
        "basis_path": _relative(OLD_TARGETED_EXECUTION),
        "basis_sha256": _sha256_file(OLD_TARGETED_EXECUTION),
        "historical_calls": calls,
        "historical_runtime_seconds": round(seconds, 3),
        "historical_seconds_per_call": round(per_call, 6),
        "estimated_runtime_seconds": round(estimate, 3),
        "estimated_runtime_minutes": round(estimate / 60.0, 2),
        "estimated_runtime_minutes_with_15pct_contingency": round(
            estimate * 1.15 / 60.0, 2
        ),
        "note": (
            "Historical throughput from the old 600-call targeted run; this "
            "is not a service-level guarantee for the current channel."
        ),
    }


def _max_tokens_sensitivity() -> dict[str, Any]:
    return {
        "status": "historical_snapshot_not_current_quote",
        "currency": "USD",
        "input_cache_miss_per_million": 1.32,
        "output_per_million": 3.96,
        "snapshot_verified_at_utc": "2026-08-30T00:00:00Z",
        "snapshot_source_url": (
            "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/"
        ),
        "note": (
            "The old project price snapshot is reused only to show an upper-"
            "bound sensitivity for review. It is not a quote for the current "
            "channel and must not be treated as a confirmed spend forecast."
        ),
    }


def build_budget(
    schedule: Mapping[str, Any],
    offline_audit: Mapping[str, Any],
    prompt_manifest: Mapping[str, Any],
    *,
    prompt_manifest_sha256: str,
    offline_requests_sha256: str,
) -> dict[str, Any]:
    validation_backend = _detect_validation_backend()
    max_sensitivity = _max_tokens_sensitivity()
    input_tokens = int(offline_audit["estimated_input_tokens_total_bytes_div_3"])
    output_ceiling = int(offline_audit["output_token_ceiling"])
    sensitivity_usd = round(
        input_tokens * max_sensitivity["input_cache_miss_per_million"] / 1e6
        + output_ceiling * max_sensitivity["output_per_million"] / 1e6,
        2,
    )
    input_cap = int(math.ceil(input_tokens * 1.10))
    return {
        "schema_version": "sep_c3_condition_preservation_budget@1.0.0",
        "suite_id": SUITE_ID,
        "status": "prepared_not_run",
        "authorization": {
            "status": "not_authorized",
            "real_api_calls": 0,
            "requires_new_user_authorization": True,
            "do_not_reuse_old_runner_authorization": True,
        },
        "purpose": (
            "Zero-API preparation for a 3-arm condition-preservation "
            "comparison on the frozen EStG-150 development set."
        ),
        "arms": list(ARMS),
        "arm_definitions": {
            "BASE": "common + E + frozen R_A; actual request equals old B",
            "RC1": "BASE + frozen old R_C; actual request equals old D",
            "RC_KEEP": "RC1 plus exactly one condition-preservation sentence",
        },
        "samples_per_arm": SAMPLES_PER_ARM,
        "planned_calls": PLANNED_CALLS,
        "call_cap": CALL_CAP,
        "retry": 0,
        "repeat_strategy": {
            "repeat_id": REPEAT_ID,
            "one_repeat_per_arm": True,
            "one_call_per_sample_per_arm": True,
        },
        "model": {
            "id": MODEL_ALIAS,
            "documented_release": MODEL_RELEASE,
            "provider": "openai_compatible",
        },
        "inference": dict(EXPECTED_INFERENCE),
        "data_binding": {
            "input_path": _relative(core.ESTG_INPUT),
            "input_sha256": _sha256_file(core.ESTG_INPUT),
            "input_dataset_id": _read_json(core.ESTG_INPUT).get("dataset_id"),
            "input_record_count": SAMPLES_PER_ARM,
            "gold_path": _relative(core.FORMAL_GOLD),
            "gold_sha256": _sha256_file(core.FORMAL_GOLD),
            "gold_dataset_id": _read_json(core.FORMAL_GOLD).get("dataset_id"),
            "gold_record_count": SAMPLES_PER_ARM,
        },
        "prompt_binding": {
            "prompt_family": "direct_llm_condition_preservation_v1",
            "generated_manifest": _relative(PROMPT_MANIFEST_PATH),
            "generated_manifest_sha256": prompt_manifest_sha256,
            "old_arm_equivalence": {
                "BASE": "old B actual sent prompt",
                "RC1": "old D actual sent prompt",
                "RC_KEEP": "old D actual sent prompt plus one sentence",
            },
            "arm_composition_sha256": {
                arm: prompt_manifest["prompts"][arm]["composition_sha256"]
                for arm in ARMS
            },
            "new_design_sentence_sha256": _sha256_text(
                cp.CONDITION_PRESERVATION_TEXT
            ),
        },
        "schedule_binding": {
            "path": _relative(SCHEDULE_PATH),
            "sha256": schedule["schedule_sha256"],
            "scheme": schedule["scheme"],
            "runtime_seed": schedule["runtime_seed"],
            "level": schedule["interleaving"]["level"],
            "permutation_counts": schedule["permutation_counts"],
        },
        "parser_binding": {
            "schema_adapter_module": _relative(ADAPTER_PATH),
            "schema_adapter_sha256": _sha256_file(ADAPTER_PATH),
            "span_canonicalizer_module": _relative(CANONICALIZER_PATH),
            "span_canonicalizer_sha256": _sha256_file(CANONICALIZER_PATH),
        },
        "validator_binding": {
            "module": _relative(VALIDATOR_PATH),
            "module_sha256": _sha256_file(VALIDATOR_PATH),
            "schema": _relative(SCHEMA_PATH),
            "schema_sha256": _sha256_file(SCHEMA_PATH),
            "locked_backend": LOCKED_VALIDATION_BACKEND,
            "detected_backend": validation_backend["detected_backend"],
            "jsonschema_available": validation_backend[
                "jsonschema_available"
            ],
            "locked_matches_detected": validation_backend[
                "locked_matches_detected"
            ],
            "runtime_switch_forbidden": True,
        },
        "evaluator_binding": {
            "coarse_metric_module": _relative(COARSE_EVALUATOR_PATH),
            "coarse_metric_sha256": _sha256_file(COARSE_EVALUATOR_PATH),
            "frozen_evaluator_module": _relative(FROZEN_EVALUATOR_PATH),
            "frozen_evaluator_sha256": _sha256_file(FROZEN_EVALUATOR_PATH),
            "coarse_view_module": _relative(COARSE_VIEW_PATH),
            "coarse_view_sha256": _sha256_file(COARSE_VIEW_PATH),
            "primary_metric": "coarse_five_field_mean_f1",
            "micro_metric": "coarse_five_field_micro.f1",
            "method_id_prefix": "direct_llm_condition_preservation_",
        },
        "bootstrap_binding": {
            "script": _relative(BOOTSTRAP_SCRIPT_PATH),
            "script_sha256": _sha256_file(BOOTSTRAP_SCRIPT_PATH),
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
            "interval": "95% percentile",
            "paired_sample_ids": True,
            "aggregate_count_recompute": True,
        },
        "processing_binding": {
            "validation_path_version": PROCESSING_PATH_VERSION,
            "fixed_order": [
                "raw_response_saved",
                "json_parse",
                "input_identity_check",
                "existing_schema_adapter",
                "existing_span_canonicalizer",
                "runtime_structural_cross_field_validation",
                "persist_attempt_and_audit",
            ],
            "input_identity_source": _relative(core.ESTG_INPUT),
            "required_source_id_rule": (
                "payload.source_id must equal the request protocol source_id "
                "(composer renders source_id == sample_id)"
            ),
            "failed_attempts_remain_in_denominator": True,
            "result_dependent_retry_forbidden": True,
        },
        "offline_render_binding": {
            "path": _relative(OFFLINE_REQUESTS_PATH),
            "sha256": offline_requests_sha256,
            "attempt_count": offline_audit["attempt_count"],
            "request_body_hash_algorithm": "sha256 over canonical JSON sorted keys",
            "unique_request_body_sha256_count": offline_audit[
                "unique_request_body_sha256_count"
            ],
        },
        "token_estimate": {
            "method": "ceil(canonical request-body bytes / 3), same rough convention as old project budget",
            "estimated_input_tokens_total": input_tokens,
            "estimated_input_tokens_per_arm": offline_audit[
                "estimated_input_tokens_per_arm_bytes_div_3"
            ],
            "max_tokens_per_call": MAX_TOKENS,
            "output_token_ceiling": output_ceiling,
            "total_token_ceiling": input_tokens + output_ceiling,
            "suggested_input_token_hard_cap": input_cap,
            "suggested_output_token_hard_cap": output_ceiling,
            "hard_cap_note": (
                "Call cap is 450 and retry is 0. Token caps are resource "
                "guards, not predictions of actual usage."
            ),
        },
        "hard_caps": {
            "calls": CALL_CAP,
            "input_tokens": input_cap,
            "output_tokens": output_ceiling,
            "usd": None,
            "usd_status": "pending_unit_price_verification",
            "note": (
                "Resource caps are fixed now. The USD hard cap must be set "
                "only after the current channel unit price is verified."
            ),
        },
        "cost_estimate": {
            "historical_usage_reference": {
                "usd": 2.21,
                "source": "user-provided old B+D+D accounting",
                "status": "historical_reference_only_not_current_quote",
            },
            "max_tokens_ceiling_sensitivity": {
                **max_sensitivity,
                "estimated_input_tokens": input_tokens,
                "output_token_ceiling": output_ceiling,
                "projection_usd": sensitivity_usd,
            },
            "channel_unit_price": {
                "status": "pending_user_verification",
                "unit_price": None,
                "confirmed": False,
                "usd_cost_cap": None,
                "suggested_cap_rule": (
                    "After channel unit price is verified: "
                    "usd_cap = 1.10 * (estimated_input_tokens * input_price "
                    "+ output_token_ceiling * output_price). Do not authorize "
                    "against the historical old-snapshot sensitivity."
                ),
            },
        },
        "runtime_estimate": _runtime_estimate(),
        "failure_policy": (
            "Transport, parse, input-binding, and canonical-validation "
            "failures are recorded separately but retained in the fixed "
            "150-sample denominator. No result-dependent retry, prompt edit, "
            "or resend is allowed."
        ),
        "stop_rules": {
            "input_prompt_code_backend_drift": "stop_entire_run",
            "budget_breach": "stop_entire_run",
            "call_dedup_failure": "stop_entire_run",
            "no_early_stop_on_score": True,
            "infrastructure_incomplete": "report_incomplete_not_accept",
        },
        "generated_at_utc": _utc_now(),
    }


def build_rules() -> dict[str, Any]:
    return {
        "schema_version": "sep_c3_condition_preservation_rules@1.0.0",
        "suite_id": SUITE_ID,
        "primary_comparisons": [
            {
                "id": "RC_KEEP_vs_RC1",
                "question": "Does the added sentence improve condition extraction?",
                "primary_metric": "condition_f1",
                "paired_bootstrap": True,
            },
            {
                "id": "RC_KEEP_vs_BASE",
                "question": (
                    "After adding constraint guidance, is the overall gain "
                    "worth keeping?"
                ),
                "primary_metric": "coarse_five_field_mean_f1",
                "paired_bootstrap": True,
            },
        ],
        "reference_comparison": {
            "id": "RC1_vs_BASE",
            "reported_in_same_batch_only": True,
        },
        "bootstrap": {
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
            "interval": "95% percentile",
            "pairing": "same sampled sample_id multiset for all three arms",
            "metric_recompute": (
                "recompute aggregate evaluator counts, never average "
                "single-sample F1"
            ),
            "zero_in_interval_decision": "uncertain_no_clear_improvement",
        },
        "retention_criteria": [
            {
                "id": "condition_f1_improves_vs_RC1",
                "comparison": "RC_KEEP - RC1",
                "metric": "condition_f1",
                "operator": "> 0",
            },
            {
                "id": "condition_missed_decreases_vs_RC1",
                "comparison": "RC_KEEP - RC1",
                "metric": "condition_missed",
                "operator": "< 0",
            },
            {
                "id": "five_field_mean_f1_improves_vs_BASE",
                "comparison": "RC_KEEP - BASE",
                "metric": "coarse_five_field_mean_f1",
                "operator": "> 0",
            },
            {
                "id": "micro_f1_improves_vs_BASE",
                "comparison": "RC_KEEP - BASE",
                "metric": "coarse_five_field_micro_f1",
                "operator": "> 0",
            },
            {
                "id": "actor_f1_not_below_BASE",
                "comparison": "RC_KEEP - BASE",
                "metric": "actor_f1",
                "operator": ">= 0",
            },
            {
                "id": "actor_fp_not_above_BASE",
                "comparison": "RC_KEEP - BASE",
                "metric": "actor_fp",
                "operator": "<= 0",
            },
            {
                "id": "condition_fp_not_above_BASE",
                "comparison": "RC_KEEP - BASE",
                "metric": "condition_fp",
                "operator": "<= 0",
            },
            {
                "id": "constraint_recall_not_below_RC1",
                "comparison": "RC_KEEP - RC1",
                "metric": "constraint_recall",
                "operator": ">= 0",
            },
            {
                "id": "constraint_fp_not_above_RC1",
                "comparison": "RC_KEEP - RC1",
                "metric": "constraint_fp",
                "operator": "<= 0",
            },
            {
                "id": "output_processing_failures_not_above_each_control",
                "comparison": "RC_KEEP <= min(BASE, RC1)",
                "metric": "output_processing_failures",
                "operator": "<= 0",
            },
        ],
        "required_bootstrap_intervals": [
            "RC_KEEP - RC1 condition F1",
            "RC_KEEP - BASE coarse five-field mean F1",
        ],
        "reporting_requirements": {
            "separate_status_blocks": [
                "transport",
                "output_parse",
                "input_binding",
                "canonical_validation",
            ],
            "failed_rows_remain_in_denominator": True,
            "no_success_only_subset": True,
        },
        "additional_calls_forbidden": {
            "calibration": True,
            "replacement_sends": True,
            "exploratory_test_calls": True,
        },
        "decision_rule": (
            "List RC_KEEP as worth keeping only if every retention criterion "
            "passes and both required intervals exclude zero. Otherwise keep "
            "BASE and do not auto-change the prompt or rerun."
        ),
        "scope_warning": (
            "Exploratory development-set comparison only; not an independent "
            "blind test or stability validation. The percentile interval "
            "reflects sample composition sensitivity only, not server or "
            "repeat-run variance."
        ),
        "automatic_actions_forbidden": [
            "prompt_update",
            "rerun",
            "budget_expansion",
            "formal_v6_replacement",
        ],
    }


def build_config_diff(
    schedule: Mapping[str, Any],
    budget: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "sep_c3_condition_preservation_config_diff@1.0.0",
        "status": "pass",
        "baseline_reference": {
            "BASE": "old B actual sent prompt",
            "RC1": "old D actual sent prompt",
        },
        "only_prompt_difference": {
            "from": "RC1",
            "to": "RC_KEEP",
            "added_sentence": cp.CONDITION_PRESERVATION_TEXT,
            "added_sentence_sha256": _sha256_text(
                cp.CONDITION_PRESERVATION_TEXT
            ),
            "all_other_prompt_sources_unchanged": True,
        },
        "non_prompt_bindings": {
            "model": dict(budget["model"]),
            "inference": dict(budget["inference"]),
            "data_binding": dict(budget["data_binding"]),
            "parser_binding": dict(budget["parser_binding"]),
            "validator_binding": dict(budget["validator_binding"]),
            "evaluator_binding": dict(budget["evaluator_binding"]),
            "schedule_sha256": schedule["schedule_sha256"],
        },
        "checked_non_prompt_differences": [],
        "note": (
            "No existing default v6 prompt, old runner contract, Gold, "
            "prediction, manifest, or historical score was modified."
        ),
    }


def _validation_item(
    item_id: str,
    status: str,
    detail: str,
) -> dict[str, Any]:
    if status not in {"pass", "fail", "unresolved"}:
        raise PrepareError(f"invalid preflight status: {status}")
    return {"id": item_id, "status": status, "detail": detail}


def build_preflight(
    prompt_audit: Mapping[str, Any],
    offline_audit: Mapping[str, Any],
    budget: Mapping[str, Any],
    rules: Mapping[str, Any],
) -> dict[str, Any]:
    items = [
        _validation_item(
            "prompt_identity_and_unique_difference",
            "pass" if prompt_audit.get("status") == "pass" else "fail",
            "BASE == old B, RC1 == old D, RC_KEEP == RC1 plus exactly one sentence.",
        ),
        _validation_item(
            "offline_render_450_hashes",
            "pass" if offline_audit.get("status") == "pass" else "fail",
            "All 450 scheduled request bodies rendered and hashed offline.",
        ),
        _validation_item(
            "fixed_schedule",
            "pass",
            "150 sample blocks x 3 arms, six permutations each 25 times, seed=20260919, frozen before run.",
        ),
        _validation_item(
            "input_gold_binding",
            "pass",
            "Frozen EStG-150 input and formal Gold hashes are recorded in the budget.",
        ),
        _validation_item(
            "processing_validator_binding",
            "pass"
            if budget["validator_binding"]["locked_matches_detected"]
            else "fail",
            "Adapter, canonicalizer, validator, schema, and lightweight backend are bound; runtime dependency switching is forbidden.",
        ),
        _validation_item(
            "evaluator_binding",
            "pass",
            "Frozen coarse five-field evaluator and shared literal-overlap backend are hash-recorded.",
        ),
        _validation_item(
            "failure_and_denominator_policy",
            "pass",
            "Failures remain in the 150-sample denominator; retry=0; no result-dependent prompt change or resend.",
        ),
        _validation_item(
            "judgment_rules_and_bootstrap",
            "pass" if rules.get("retention_criteria") else "fail",
            "Retention criteria, stop rules, paired bootstrap seed/resamples, and zero-in-interval rule are fixed.",
        ),
        _validation_item(
            "real_api_calls_zero",
            "pass",
            "No transport was constructed and no .env was read in this preparation.",
        ),
        _validation_item(
            "authorization",
            "fail",
            "authorization status is not_authorized; a new explicit user authorization is required.",
        ),
        _validation_item(
            "channel_unit_price",
            "fail",
            "The actual channel unit price has not been verified; no confirmed USD cost or hard USD cap exists yet.",
        ),
        _validation_item(
            "execution_entrypoint",
            "fail",
            "No new execution runner/transport was implemented in this zero-API round; the old runner execute path must not be reused.",
        ),
    ]
    return {
        "schema_version": "sep_c3_condition_preservation_preflight@1.0.0",
        "suite_id": SUITE_ID,
        "overall_status": "FAIL_NOT_READY_FOR_RUN",
        "preparation_status": (
            "pass"
            if prompt_audit.get("status") == "pass"
            and offline_audit.get("status") == "pass"
            else "fail"
        ),
        "real_api_calls": 0,
        "authorization_status": "not_authorized",
        "ready_to_run": False,
        "items": items,
        "blocking_items": [
            item["id"]
            for item in items
            if item["status"] in {"fail", "unresolved"}
        ],
        "note": (
            "Materials are generated for review; this is not a declaration "
            "that the experiment can be run yet."
        ),
        "generated_at_utc": _utc_now(),
    }


def _render_preflight_md(preflight: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C3 condition-preservation v1 preflight",
        "",
        f"- overall_status: `{preflight['overall_status']}`",
        f"- preparation_status: `{preflight['preparation_status']}`",
        f"- authorization_status: `{preflight['authorization_status']}`",
        f"- real_api_calls: `{preflight['real_api_calls']}`",
        f"- ready_to_run: `{str(preflight['ready_to_run']).lower()}`",
        "",
        "| item | status | detail |",
        "|---|---|---|",
    ]
    for item in preflight["items"]:
        detail = str(item["detail"]).replace("|", "\\|")
        lines.append(
            f"| `{item['id']}` | `{item['status']}` | {detail} |"
        )
    lines.extend([
        "",
        f"Blocking items: {', '.join(preflight['blocking_items'])}",
        "",
        "This file records a zero-API preparation state. It must not be read "
        "as execution authorization.",
    ])
    return "\n".join(lines) + "\n"


def compute_bundle() -> dict[str, Any]:
    input_rows = _input_rows()
    prompts = cp.render_all()
    prompt_texts = {
        arm: prompt.to_markdown() for arm, prompt in prompts.items()
    }
    prompt_file_hashes = {
        arm: _sha256_text(text) for arm, text in prompt_texts.items()
    }
    prompt_manifest = cp._manifest(
        prompts, file_hashes=prompt_file_hashes
    )
    prompt_manifest_sha256 = _sha256_text(
        json.dumps(prompt_manifest, ensure_ascii=False, indent=2) + "\n"
    )
    schedule = build_schedule(input_rows)
    offline_rows = _offline_rows(schedule, input_rows)
    offline_text = "".join(
        json.dumps(row, ensure_ascii=False) + "\n" for row in offline_rows
    )
    offline_requests_sha256 = _sha256_text(offline_text)
    offline_audit = _offline_audit(
        schedule,
        offline_rows,
        offline_requests_sha256=offline_requests_sha256,
    )
    prompt_audit = _prompt_audit(prompts)
    budget = build_budget(
        schedule,
        offline_audit,
        prompt_manifest,
        prompt_manifest_sha256=prompt_manifest_sha256,
        offline_requests_sha256=offline_requests_sha256,
    )
    rules = build_rules()
    config_diff = build_config_diff(schedule, budget)
    preflight = build_preflight(prompt_audit, offline_audit, budget, rules)
    diffs = {
        "BASE_vs_RC1": "".join(
            difflib.unified_diff(
                _sent_text(prompts["BASE"]).splitlines(keepends=True),
                _sent_text(prompts["RC1"]).splitlines(keepends=True),
                fromfile="BASE_sent_prompt.txt",
                tofile="RC1_sent_prompt.txt",
                n=2,
            )
        ),
        "RC1_vs_RC_KEEP": "".join(
            difflib.unified_diff(
                _sent_text(prompts["RC1"]).splitlines(keepends=True),
                _sent_text(prompts["RC_KEEP"]).splitlines(keepends=True),
                fromfile="RC1_sent_prompt.txt",
                tofile="RC_KEEP_sent_prompt.txt",
                n=2,
            )
        ),
        "BASE_vs_RC_KEEP": "".join(
            difflib.unified_diff(
                _sent_text(prompts["BASE"]).splitlines(keepends=True),
                _sent_text(prompts["RC_KEEP"]).splitlines(keepends=True),
                fromfile="BASE_sent_prompt.txt",
                tofile="RC_KEEP_sent_prompt.txt",
                n=2,
            )
        ),
    }
    prepare_audit = {
        "schema_version": "sep_c3_condition_preservation_prepare_audit@1.0.0",
        "suite_id": SUITE_ID,
        "status": (
            "pass"
            if prompt_audit.get("status") == "pass"
            and offline_audit.get("status") == "pass"
            and config_diff.get("status") == "pass"
            else "fail"
        ),
        "real_api_calls": 0,
        "prompt_audit_path": _relative(PROMPT_AUDIT_PATH),
        "offline_render_audit_path": _relative(OFFLINE_AUDIT_PATH),
        "preflight_path": _relative(PREFLIGHT_JSON_PATH),
        "schedule_path": _relative(SCHEDULE_PATH),
        "schedule_sha256": schedule["schedule_sha256"],
        "budget_path": _relative(BUDGET_PATH),
        "generated_prompt_manifest": _relative(PROMPT_MANIFEST_PATH),
        "generated_prompt_manifest_sha256": prompt_manifest_sha256,
        "offline_requests_path": _relative(OFFLINE_REQUESTS_PATH),
        "offline_requests_sha256": offline_requests_sha256,
        "generated_at_utc": _utc_now(),
    }
    return {
        "input_rows": input_rows,
        "prompts": prompts,
        "prompt_texts": prompt_texts,
        "prompt_manifest": prompt_manifest,
        "prompt_manifest_text": (
            json.dumps(prompt_manifest, ensure_ascii=False, indent=2) + "\n"
        ),
        "schedule": schedule,
        "offline_rows": offline_rows,
        "offline_text": offline_text,
        "offline_audit": offline_audit,
        "prompt_audit": prompt_audit,
        "budget": budget,
        "rules": rules,
        "config_diff": config_diff,
        "preflight": preflight,
        "preflight_md": _render_preflight_md(preflight),
        "prompt_diffs": diffs,
        "prepare_audit": prepare_audit,
    }


def _stable(value: Any, *, drop_generated_at: bool = False) -> Any:
    if isinstance(value, dict):
        return {
            key: _stable(item, drop_generated_at=drop_generated_at)
            for key, item in value.items()
            if not (drop_generated_at and key == "generated_at_utc")
        }
    if isinstance(value, list):
        return [_stable(item, drop_generated_at=drop_generated_at) for item in value]
    return value


def _write_bundle(bundle: Mapping[str, Any], *, overwrite: bool) -> None:
    # Generated prompts and manifest: never touch the old families.
    cp.write_generated(GENERATED_DIR, overwrite=overwrite)
    _write_text(
        PROMPT_MANIFEST_PATH, bundle["prompt_manifest_text"]
    )
    _write_json(SCHEDULE_PATH, bundle["schedule"])
    _write_json(BUDGET_PATH, bundle["budget"])
    _write_json(PROMPT_AUDIT_PATH, bundle["prompt_audit"])
    _write_json(OFFLINE_AUDIT_PATH, bundle["offline_audit"])
    _write_json(RULES_PATH, bundle["rules"])
    _write_json(CONFIG_DIFF_PATH, bundle["config_diff"])
    _write_json(PREFLIGHT_JSON_PATH, bundle["preflight"])
    _write_text(PREFLIGHT_MD_PATH, bundle["preflight_md"])
    _write_json(PREPARE_AUDIT_PATH, bundle["prepare_audit"])
    _write_jsonl(OFFLINE_REQUESTS_PATH, bundle["offline_rows"])
    DIFF_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in bundle["prompt_diffs"].items():
        _write_text(DIFF_DIR / f"{name}.diff", text)


def _same_existing(path: Path, expected: Any, *, drop_generated_at: bool) -> bool:
    if not path.is_file():
        return False
    existing = _read_json(path)
    return _stable(existing, drop_generated_at=drop_generated_at) == _stable(
        expected, drop_generated_at=drop_generated_at
    )


def prepare(*, overwrite: bool = False) -> dict[str, Any]:
    bundle = compute_bundle()
    generated_paths = [cp.generated_path(arm, GENERATED_DIR) for arm in ARMS]
    watched_paths = [
        SCHEDULE_PATH,
        BUDGET_PATH,
        PROMPT_AUDIT_PATH,
        OFFLINE_AUDIT_PATH,
        RULES_PATH,
        CONFIG_DIFF_PATH,
        PREFLIGHT_JSON_PATH,
        PREPARE_AUDIT_PATH,
        OFFLINE_REQUESTS_PATH,
        PROMPT_MANIFEST_PATH,
        *generated_paths,
    ]
    if any(path.exists() for path in watched_paths) and not overwrite:
        # Allow an idempotent no-op only if every existing artifact matches.
        matches = [
            _same_existing(SCHEDULE_PATH, bundle["schedule"], drop_generated_at=True),
            _same_existing(BUDGET_PATH, bundle["budget"], drop_generated_at=True),
            _same_existing(
                PROMPT_AUDIT_PATH, bundle["prompt_audit"], drop_generated_at=False
            ),
            _same_existing(
                OFFLINE_AUDIT_PATH,
                bundle["offline_audit"],
                drop_generated_at=False,
            ),
            _same_existing(RULES_PATH, bundle["rules"], drop_generated_at=False),
            _same_existing(
                CONFIG_DIFF_PATH, bundle["config_diff"], drop_generated_at=False
            ),
            _same_existing(
                PREFLIGHT_JSON_PATH,
                bundle["preflight"],
                drop_generated_at=True,
            ),
            _same_existing(
                PREPARE_AUDIT_PATH,
                bundle["prepare_audit"],
                drop_generated_at=True,
            ),
            (
                OFFLINE_REQUESTS_PATH.is_file()
                and OFFLINE_REQUESTS_PATH.read_text(encoding="utf-8")
                == bundle["offline_text"]
            ),
            (
                PROMPT_MANIFEST_PATH.is_file()
                and PROMPT_MANIFEST_PATH.read_text(encoding="utf-8")
                == bundle["prompt_manifest_text"]
            ),
            *[
                (
                    cp.generated_path(arm, GENERATED_DIR).is_file()
                    and cp.generated_path(arm, GENERATED_DIR).read_text(
                        encoding="utf-8"
                    )
                    == bundle["prompt_texts"][arm]
                )
                for arm in ARMS
            ],
        ]
        if not all(matches):
            raise PrepareError(
                "prepared artifacts already exist with different contents; "
                "use --overwrite only before any real run has started"
            )
    _write_bundle(bundle, overwrite=True)
    return {
        "schema_version": "sep_c3_condition_preservation_prepare@1.0.0",
        "suite_id": SUITE_ID,
        "status": bundle["prepare_audit"]["status"],
        "real_api_calls": 0,
        "schedule_sha256": bundle["schedule"]["schedule_sha256"],
        "offline_requests_sha256": bundle["offline_audit"][
            "request_bodies_sha256"
        ],
        "preflight_overall_status": bundle["preflight"]["overall_status"],
        "preflight_path": _relative(PREFLIGHT_JSON_PATH),
    }


def check() -> dict[str, Any]:
    bundle = compute_bundle()
    errors: list[str] = []
    required = [
        PROMPT_MANIFEST_PATH,
        SCHEDULE_PATH,
        BUDGET_PATH,
        PROMPT_AUDIT_PATH,
        OFFLINE_AUDIT_PATH,
        RULES_PATH,
        CONFIG_DIFF_PATH,
        PREFLIGHT_JSON_PATH,
        PREFLIGHT_MD_PATH,
        PREPARE_AUDIT_PATH,
        OFFLINE_REQUESTS_PATH,
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"missing prepared artifact: {_relative(path)}")
    if errors:
        return {"status": "fail", "errors": errors}
    if not _same_existing(
        SCHEDULE_PATH, bundle["schedule"], drop_generated_at=True
    ):
        errors.append("schedule differs from recomputed frozen schedule")
    if not _same_existing(BUDGET_PATH, bundle["budget"], drop_generated_at=True):
        errors.append("budget differs from recomputed contract")
    if not _same_existing(
        PROMPT_AUDIT_PATH, bundle["prompt_audit"], drop_generated_at=False
    ):
        errors.append("prompt audit differs from recomputed audit")
    if not _same_existing(
        OFFLINE_AUDIT_PATH, bundle["offline_audit"], drop_generated_at=False
    ):
        errors.append("offline render audit differs from recomputed audit")
    if not _same_existing(RULES_PATH, bundle["rules"], drop_generated_at=False):
        errors.append("judgment rules differ from recomputed rules")
    if not _same_existing(
        CONFIG_DIFF_PATH, bundle["config_diff"], drop_generated_at=False
    ):
        errors.append("config diff differs from recomputed diff")
    if not _same_existing(
        PREFLIGHT_JSON_PATH,
        bundle["preflight"],
        drop_generated_at=True,
    ):
        errors.append("preflight JSON differs from recomputed preflight")
    if (
        PREFLIGHT_MD_PATH.read_text(encoding="utf-8")
        != bundle["preflight_md"]
    ):
        errors.append("preflight Markdown differs from recomputed preflight")
    if (
        OFFLINE_REQUESTS_PATH.read_text(encoding="utf-8")
        != bundle["offline_text"]
    ):
        errors.append("offline request lines differ from recomputed bodies")
    if (
        PROMPT_MANIFEST_PATH.read_text(encoding="utf-8")
        != bundle["prompt_manifest_text"]
    ):
        errors.append("prompt manifest differs from recomputed composer output")
    for arm in ARMS:
        path = cp.generated_path(arm, GENERATED_DIR)
        if not path.is_file():
            errors.append(f"missing generated prompt: {_relative(path)}")
            continue
        if path.read_text(encoding="utf-8") != bundle["prompt_texts"][arm]:
            errors.append(f"generated prompt differs: {_relative(path)}")
    for name, text in bundle["prompt_diffs"].items():
        path = DIFF_DIR / f"{name}.diff"
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            errors.append(f"prompt diff missing or stale: {_relative(path)}")
    return {
        "schema_version": "sep_c3_condition_preservation_check@1.0.0",
        "suite_id": SUITE_ID,
        "status": "pass" if not errors else "fail",
        "real_api_calls": 0,
        "errors": errors,
        "schedule_sha256": bundle["schedule"]["schedule_sha256"],
        "offline_attempt_count": bundle["offline_audit"]["attempt_count"],
        "preflight_overall_status": bundle["preflight"]["overall_status"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare or check the zero-API SEP-C3 condition-preservation "
            "materials. This command never calls an LLM/API."
        )
    )
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.prepare:
        result = prepare(overwrite=args.overwrite)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") == "pass" else 1
    if args.check:
        result = check()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") == "pass" else 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())