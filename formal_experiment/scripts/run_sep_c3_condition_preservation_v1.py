# -*- coding: utf-8 -*-
"""Dedicated interlaced executor for the SEP-C3 condition-preservation arms.

This is a new entry point for ``SEP-C3-CONDITION-PRESERVATION-001``.  It does
not call the old targeted-refinement ``execute`` path.  The three arms are
rendered by the frozen ``sep_c3_condition_preservation_prompt`` family and the
450-entry schedule is loaded from the frozen preparation artifacts.

Safety contract
---------------
* Zero network by default; real sends require ``--execute --allow-llm`` plus a
  valid new authorization event and execution contract.
* Every request is bound to the prepared offline request body before sending.
* An attempt row is appended before the HTTP call; a response row is appended
  afterwards.  An attempt without a response is ``in_doubt`` and permanently
  blocks automatic resend.
* Missing/unverifiable provider usage stops all later sends.
* Failures stay in the fixed 150-per-arm denominator.  No result-dependent
  retry, prompt edit, or replacement call is possible.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import bpc_hybrid.sep_c3_condition_preservation_prompt as cp  # noqa: E402
import run_barrientos_ablation_suite_v2 as base  # noqa: E402
import run_sep_c3_modular_ablation_v1 as core  # noqa: E402
import run_sep_c3_targeted_refinement_v1 as shared  # noqa: E402
from bpc_hybrid.h1_transport import H1RequestPolicy  # noqa: E402
from bpc_hybrid.llm_client import LLMRequest, RealAPITransport  # noqa: E402
from bpc_hybrid.llm_config import LLMConfig  # noqa: E402
from bpc_hybrid.sep_c3_modular_evaluation import (  # noqa: E402
    attempt_rows,
    evaluate_coarse,
)
from bpc_hybrid.stage2_canonical import validate_canonical  # noqa: E402


SUITE_ID = "SEP-C3-CONDITION-PRESERVATION-001"
ARMS = tuple(cp.ARMS)
SAMPLES_PER_ARM = 150
PLANNED_CALLS = 450
CALL_CAP = 450
REPEAT_ID = "repeat-01"
MODEL_ALIAS = core.MODEL_ALIAS
MODEL_RELEASE = core.MODEL_RELEASE
TEMPERATURE = core.TEMPERATURE
TOP_P = core.TOP_P
MAX_TOKENS = core.MAX_TOKENS
RETRY = 0

PREPARED_BUDGET_PATH = (
    ROOT / "configs" / "sep_c3_condition_preservation_budget_v1.json"
)
SCHEDULE_PATH = (
    ROOT / "configs" / "sep_c3_condition_preservation_schedule_v1.json"
)
AUTHORIZATION_PATH = (
    ROOT / "configs" / "sep_c3_condition_preservation_authorization_event_v1.json"
)
EXECUTION_CONTRACT_PATH = (
    ROOT / "configs" / "sep_c3_condition_preservation_execution_contract_v1.json"
)
OFFLINE_REQUESTS_PATH = (
    ROOT
    / "outputs"
    / "evidence"
    / "sep_c3_condition_preservation_v1"
    / "offline_requests.jsonl"
)
OUT_DIR = ROOT / "outputs" / "development" / "sep_c3_condition_preservation_v1"
RESULT_REPORT = (
    ROOT
    / "outputs"
    / "reports"
    / "sep_c3_condition_preservation_v1_execution.json"
)

PEAK_PRICE = {
    "input_cache_hit_per_million": 0.044,
    "input_cache_miss_per_million": 1.32,
    "output_per_million": 3.96,
}
OFF_PEAK_PRICE = {
    "input_cache_hit_per_million": 0.022,
    "input_cache_miss_per_million": 0.66,
    "output_per_million": 1.98,
}
PRICE_SOURCE_URL = "https://api-docs.deepseek.com/quick_start/pricing/"
OUTPUT_VALIDATION_PATH_VERSION = (
    "sep_c3_condition_preservation_validation_path_v1"
)


class ConditionPreservationRunError(RuntimeError):
    """A fail-closed precondition or runtime budget/identity check failed."""


class RunLock:
    """Atomic same-directory lock preventing concurrent duplicate batches."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.acquired = False

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            existing = ""
            try:
                existing = self.path.read_text(encoding="utf-8").strip()
            except OSError:
                pass
            raise ConditionPreservationRunError(
                f"run lock already exists: {_relative(self.path)}; "
                f"another batch may be running or the lock is stale. "
                f"Lock content: {existing!r}"
            ) from exc
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "suite_id": SUITE_ID,
                "pid": os.getpid(),
                "started_at_utc": _utc_now(),
                "planned_calls": PLANNED_CALLS,
                "arms": list(ARMS),
            }, ensure_ascii=False) + "\n")
        self.acquired = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.acquired:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
        self.acquired = False


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ConditionPreservationRunError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False) + "\n")


def _arm_dir(arm: str, out_dir: Path) -> Path:
    return out_dir / arm / REPEAT_ID


def _input_rows() -> list[dict[str, str]]:
    rows = core.samples(SAMPLES_PER_ARM)
    ids = [str(row["sample_id"]) for row in rows]
    if len(rows) != SAMPLES_PER_ARM or len(set(ids)) != SAMPLES_PER_ARM:
        raise ConditionPreservationRunError(
            "frozen EStG input does not contain 150 unique sample_ids"
        )
    return rows


def _prompt(arm: str) -> cp.ConditionPreservationPrompt:
    return cp.render_condition_preservation_prompt(arm)


def _request_body(arm: str, sample_id: str, source_text: str) -> dict[str, Any]:
    prompt = _prompt(arm)
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
    return json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _body_sha256(body: Mapping[str, Any]) -> str:
    return _sha256_bytes(_canonical_body_bytes(body))


def _estimated_input_tokens(body: Mapping[str, Any]) -> int:
    return math.ceil(len(_canonical_body_bytes(body)) / 3)


def _sent_text(prompt: cp.ConditionPreservationPrompt) -> str:
    return (
        prompt.system_prompt
        + "\n\n<!--USER-->\n\n"
        + prompt.user_prompt_template
    )


def _detect_validation_backend() -> dict[str, Any]:
    available = importlib.util.find_spec("jsonschema") is not None
    return {
        "backend": "jsonschema" if available else "lightweight",
        "jsonschema_available": available,
        "detail": (
            "stage2_canonical.validate_canonical() with the installed "
            "jsonschema Draft202012 validator plus cross-field checks"
            if available
            else "stage2_canonical.validate_canonical() using the existing "
            "in-process structural + cross-field checks; jsonschema is not "
            "installed"
        ),
    }


def _output_validation_path_metadata() -> dict[str, Any]:
    backend = _detect_validation_backend()
    return {
        "version": OUTPUT_VALIDATION_PATH_VERSION,
        "validation_backend": backend["backend"],
        "validation_backend_detail": backend["detail"],
        "jsonschema_available": backend["jsonschema_available"],
        "processing_order": [
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
            "(condition-preservation composer renders source_id == sample_id)"
        ),
    }


def _load_schedule(path: Path) -> dict[str, Any]:
    schedule = _read_json(path)
    entries = schedule.get("entries")
    if not isinstance(entries, list):
        raise ConditionPreservationRunError("schedule entries missing")
    canonical = json.dumps(
        entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    if schedule.get("schedule_sha256") != _sha256_text(canonical):
        raise ConditionPreservationRunError("schedule hash mismatch")
    if len(entries) != PLANNED_CALLS:
        raise ConditionPreservationRunError(
            f"schedule must contain exactly {PLANNED_CALLS} entries"
        )
    if schedule.get("arms") != list(ARMS):
        raise ConditionPreservationRunError("schedule arms mismatch")
    if int(schedule.get("samples_per_arm", 0)) != SAMPLES_PER_ARM:
        raise ConditionPreservationRunError("schedule samples_per_arm mismatch")
    counts = {arm: 0 for arm in ARMS}
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        arm = str(entry.get("arm"))
        sid = str(entry.get("sample_id") or "")
        if arm not in counts:
            raise ConditionPreservationRunError(f"unknown schedule arm: {arm!r}")
        if not sid:
            raise ConditionPreservationRunError("schedule entry missing sample_id")
        key = (arm, sid)
        if key in seen:
            raise ConditionPreservationRunError(f"duplicate schedule entry: {key}")
        seen.add(key)
        counts[arm] += 1
    if any(value != SAMPLES_PER_ARM for value in counts.values()):
        raise ConditionPreservationRunError(
            "schedule does not contain 150 entries per arm"
        )
    return schedule


def _load_prepared_budget(path: Path) -> dict[str, Any]:
    budget = _read_json(path)
    if int(budget.get("planned_calls", 0)) != PLANNED_CALLS:
        raise ConditionPreservationRunError("prepared budget planned_calls mismatch")
    if int(budget.get("call_cap", 0)) != CALL_CAP:
        raise ConditionPreservationRunError("prepared budget call_cap mismatch")
    if budget.get("arms") != list(ARMS):
        raise ConditionPreservationRunError("prepared budget arms mismatch")
    model = budget.get("model") or {}
    if model.get("id") != MODEL_ALIAS:
        raise ConditionPreservationRunError("prepared budget model mismatch")
    if model.get("documented_release") != MODEL_RELEASE:
        raise ConditionPreservationRunError("prepared budget release mismatch")
    inference = budget.get("inference") or {}
    expected_inference = {
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
        "retry": RETRY,
        "stream": False,
        "thinking": {"type": "disabled"},
        "response_format": None,
    }
    if inference != expected_inference:
        raise ConditionPreservationRunError("prepared budget inference mismatch")
    return budget


def _load_execution_contract(path: Path) -> dict[str, Any]:
    contract = _read_json(path)
    if contract.get("suite_id") != SUITE_ID:
        raise ConditionPreservationRunError("execution contract suite mismatch")
    if contract.get("status") not in {"authorized_not_run", "authorized"}:
        raise ConditionPreservationRunError("execution contract is not authorized")
    if int(contract.get("planned_calls", 0)) != PLANNED_CALLS:
        raise ConditionPreservationRunError("execution contract planned_calls mismatch")
    if int(contract.get("call_cap", 0)) != CALL_CAP:
        raise ConditionPreservationRunError("execution contract call_cap mismatch")
    if int(contract.get("retry", -1)) != RETRY:
        raise ConditionPreservationRunError("execution contract retry mismatch")
    if int(contract.get("max_tokens", 0)) != MAX_TOKENS:
        raise ConditionPreservationRunError("execution contract max_tokens mismatch")
    if contract.get("model", {}).get("id") != MODEL_ALIAS:
        raise ConditionPreservationRunError("execution contract model mismatch")
    for key in ("input_token_cap", "output_token_cap", "usd_cost_cap"):
        if not isinstance(contract.get(key), (int, float)) or contract[key] <= 0:
            raise ConditionPreservationRunError(
                f"execution contract invalid cap: {key}"
            )
    return contract


def _load_authorization(path: Path) -> dict[str, Any]:
    auth = _read_json(path)
    if auth.get("status") != "authorized":
        raise ConditionPreservationRunError("authorization event is not authorized")
    text = auth.get("authorization_text")
    if not isinstance(text, str) or not text.strip():
        raise ConditionPreservationRunError("authorization event text missing")
    if auth.get("authorization_text_sha256") != _sha256_text(text):
        raise ConditionPreservationRunError("authorization text hash mismatch")
    if auth.get("model") != MODEL_ALIAS:
        raise ConditionPreservationRunError("authorization model mismatch")
    if auth.get("provider") != "openai_compatible":
        raise ConditionPreservationRunError("authorization provider mismatch")
    if auth.get("service") != "DeepSeek official API":
        raise ConditionPreservationRunError("authorization service mismatch")
    if int(auth.get("planned_calls", 0)) != PLANNED_CALLS:
        raise ConditionPreservationRunError("authorization planned_calls mismatch")
    if int(auth.get("call_cap", 0)) != CALL_CAP:
        raise ConditionPreservationRunError("authorization call_cap mismatch")
    if int(auth.get("retry", -1)) != RETRY:
        raise ConditionPreservationRunError("authorization retry mismatch")
    if int(auth.get("max_tokens", 0)) != MAX_TOKENS:
        raise ConditionPreservationRunError("authorization max_tokens mismatch")
    if float(auth.get("usd_budget_cap", -1.0)) > 10.0:
        raise ConditionPreservationRunError("authorization USD budget exceeds 10 USD")
    return auth


def _load_offline_rows(path: Path) -> list[dict[str, Any]]:
    rows = _read_jsonl(path)
    if len(rows) != PLANNED_CALLS:
        raise ConditionPreservationRunError(
            f"offline request count {len(rows)} != {PLANNED_CALLS}"
        )
    hashes = [str(row.get("request_body_sha256") or "") for row in rows]
    if any(not value for value in hashes) or len(set(hashes)) != len(hashes):
        raise ConditionPreservationRunError("offline request body hashes invalid")
    return rows


def _check_module_hash(
    errors: list[str],
    *,
    label: str,
    module_path: str,
    expected_sha256: str,
) -> None:
    path = ROOT / str(module_path)
    if not path.is_file():
        errors.append(f"{label}: missing module {module_path}")
        return
    actual = _sha256_file(path)
    if actual != expected_sha256:
        errors.append(
            f"{label}: hash mismatch for {module_path}: {actual} != {expected_sha256}"
        )


def validate_contracts(
    *,
    contract_path: Path | None = None,
    auth_path: Path | None = None,
    prepared_budget_path: Path | None = None,
    schedule_path: Path | None = None,
    offline_path: Path | None = None,
) -> dict[str, Any]:
    """Fail-closed binding check for authorization, budget, prompts and data."""
    contract_path = Path(contract_path or EXECUTION_CONTRACT_PATH)
    auth_path = Path(auth_path or AUTHORIZATION_PATH)
    prepared_budget_path = Path(prepared_budget_path or PREPARED_BUDGET_PATH)
    schedule_path = Path(schedule_path or SCHEDULE_PATH)
    offline_path = Path(offline_path or OFFLINE_REQUESTS_PATH)
    errors: list[str] = []
    checks: list[dict[str, Any]] = []

    def fail(item_id: str, detail: str) -> None:
        errors.append(f"{item_id}: {detail}")
        checks.append({"id": item_id, "status": "fail", "detail": detail})

    def pass_check(item_id: str, detail: str) -> None:
        checks.append({"id": item_id, "status": "pass", "detail": detail})

    auth: dict[str, Any] | None = None
    contract: dict[str, Any] | None = None
    budget: dict[str, Any] | None = None
    schedule: dict[str, Any] | None = None
    offline_rows: list[dict[str, Any]] = []
    input_rows: list[dict[str, str]] = []

    try:
        auth = _load_authorization(auth_path)
        pass_check("authorization_event", _relative(auth_path))
    except Exception as exc:  # noqa: BLE001 - report every fail-closed reason.
        fail("authorization_event", f"{type(exc).__name__}: {exc}")

    try:
        contract = _load_execution_contract(contract_path)
        pass_check("execution_contract", _relative(contract_path))
    except Exception as exc:  # noqa: BLE001
        fail("execution_contract", f"{type(exc).__name__}: {exc}")

    try:
        budget = _load_prepared_budget(prepared_budget_path)
        pass_check("prepared_budget", _relative(prepared_budget_path))
    except Exception as exc:  # noqa: BLE001
        fail("prepared_budget", f"{type(exc).__name__}: {exc}")

    try:
        schedule = _load_schedule(schedule_path)
        pass_check("schedule", _relative(schedule_path))
    except Exception as exc:  # noqa: BLE001
        fail("schedule", f"{type(exc).__name__}: {exc}")

    try:
        offline_rows = _load_offline_rows(offline_path)
        if _sha256_file(offline_path) != str(
            (budget or {}).get("offline_render_binding", {}).get("sha256", "")
        ):
            raise ConditionPreservationRunError("offline request file hash mismatch")
        pass_check("offline_render_binding", _relative(offline_path))
    except Exception as exc:  # noqa: BLE001
        fail("offline_render_binding", f"{type(exc).__name__}: {exc}")
        offline_rows = []

    try:
        input_rows = _input_rows()
        missing = set()
        # core.samples() already validates the input, but retain a membership check.
        if len(input_rows) != SAMPLES_PER_ARM:
            missing.add("record_count")
        if missing:
            raise ConditionPreservationRunError(f"input membership: {sorted(missing)}")
        pass_check("input_rows", _relative(core.ESTG_INPUT))
    except Exception as exc:  # noqa: BLE001
        fail("input_rows", f"{type(exc).__name__}: {exc}")
        input_rows = []

    if contract is not None and auth is not None:
        if str(contract.get("authorization_path") or "") != _relative(auth_path):
            fail(
                "authorization_binding",
                f"contract authorization_path={contract.get('authorization_path')!r} "
                f"!= {_relative(auth_path)!r}",
            )
        elif contract.get("authorization_sha256") != _sha256_file(auth_path):
            fail("authorization_binding", "authorization file hash mismatch")
        else:
            pass_check("authorization_binding", _relative(auth_path))

    if contract is not None and budget is not None:
        if str(contract.get("prepared_budget_path") or "") != _relative(
            prepared_budget_path
        ):
            fail(
                "prepared_budget_binding",
                f"contract prepared_budget_path={contract.get('prepared_budget_path')!r} "
                f"!= {_relative(prepared_budget_path)!r}",
            )
        elif contract.get("prepared_budget_sha256") != _sha256_file(
            prepared_budget_path
        ):
            fail("prepared_budget_binding", "prepared budget file hash mismatch")
        else:
            pass_check("prepared_budget_binding", _relative(prepared_budget_path))

    if contract is not None and budget is not None:
        hard_caps = budget.get("hard_caps") or {}
        if int(contract["input_token_cap"]) != int(hard_caps.get("input_tokens", -1)):
            fail("token_cap_binding", "input token cap differs from prepared budget")
        if int(contract["output_token_cap"]) != int(hard_caps.get("output_tokens", -1)):
            fail("token_cap_binding", "output token cap differs from prepared budget")
        if float(contract["usd_cost_cap"]) > 10.0:
            fail("usd_cap", "USD cap is above the 10 USD user ceiling")
        if contract.get("model", {}).get("id") != budget.get("model", {}).get("id"):
            fail("model_binding", "model differs from prepared budget")
        if int(contract.get("max_tokens", 0)) != int(
            (budget.get("inference") or {}).get("max_tokens", -1)
        ):
            fail("inference_binding", "max_tokens differs from prepared budget")
        if int(contract.get("retry", -1)) != int(
            (budget.get("inference") or {}).get("retry", -1)
        ):
            fail("inference_binding", "retry differs from prepared budget")
        if not errors or all(not e.startswith("token_cap_binding") for e in errors):
            pass_check("token_cap_binding", "input/output caps inherited from prepared budget")
        if not any(e.startswith("usd_cap") for e in errors):
            pass_check("usd_cap", f"{contract['usd_cost_cap']} USD")
        # Price snapshot must match the official peak/off-peak table supplied
        # in the user instruction.  We never probe a model to check prices.
        price = (contract.get("price_snapshot") or {})
        if price.get("peak") != PEAK_PRICE:
            fail("price_snapshot_peak", "peak price snapshot mismatch")
        if price.get("off_peak") != OFF_PEAK_PRICE:
            fail("price_snapshot_off_peak", "off-peak price snapshot mismatch")
        if price.get("source_url") != PRICE_SOURCE_URL:
            fail("price_snapshot_source", "price source URL mismatch")
        if (
            price.get("peak") == PEAK_PRICE
            and price.get("off_peak") == OFF_PEAK_PRICE
            and price.get("source_url") == PRICE_SOURCE_URL
        ):
            pass_check("price_snapshot", "official DeepSeek peak/off-peak values recorded")

    if budget is not None:
        data = budget.get("data_binding") or {}
        if data.get("input_sha256") != _sha256_file(core.ESTG_INPUT):
            fail("input_binding", "input hash mismatch")
        else:
            pass_check("input_binding", data.get("input_sha256"))
        if data.get("gold_sha256") != _sha256_file(core.FORMAL_GOLD):
            fail("gold_binding", "Gold hash mismatch")
        else:
            pass_check("gold_binding", data.get("gold_sha256"))
        prompt_binding = budget.get("prompt_binding") or {}
        manifest_path = cp.generated_manifest_path()
        if prompt_binding.get("generated_manifest_sha256") != _sha256_file(
            manifest_path
        ):
            fail("prompt_manifest_binding", "prompt manifest hash mismatch")
        else:
            pass_check("prompt_manifest_binding", _relative(manifest_path))
        try:
            prompt_manifest = _read_json(manifest_path)
        except Exception as exc:  # noqa: BLE001
            fail("prompt_manifest_binding", f"cannot read manifest: {exc}")
            prompt_manifest = {}
        for arm in ARMS:
            expected_comp = (prompt_binding.get("arm_composition_sha256") or {}).get(arm)
            actual_comp = (
                (prompt_manifest.get("prompts") or {}).get(arm) or {}
            ).get("composition_sha256")
            if expected_comp != actual_comp:
                fail("prompt_arm_binding", f"{arm}: composition mismatch")
                continue
            generated_path = cp.generated_path(arm)
            if not generated_path.is_file():
                fail("prompt_file_binding", f"{arm}: missing generated prompt")
                continue
            expected_file_sha = (
                (prompt_manifest.get("prompts") or {}).get(arm) or {}
            ).get("markdown_sha256")
            if expected_file_sha != _sha256_file(generated_path):
                fail("prompt_file_binding", f"{arm}: generated prompt hash mismatch")
                continue
            pass_check(f"prompt_arm_binding_{arm}", expected_comp)
        parser = budget.get("parser_binding") or {}
        _check_module_hash(
            errors,
            label="adapter_binding",
            module_path=parser.get("schema_adapter_module", ""),
            expected_sha256=parser.get("schema_adapter_sha256", ""),
        )
        _check_module_hash(
            errors,
            label="canonicalizer_binding",
            module_path=parser.get("span_canonicalizer_module", ""),
            expected_sha256=parser.get("span_canonicalizer_sha256", ""),
        )
        validator = budget.get("validator_binding") or {}
        _check_module_hash(
            errors,
            label="validator_binding",
            module_path=validator.get("module", ""),
            expected_sha256=validator.get("module_sha256", ""),
        )
        schema_path = ROOT / str(validator.get("schema", ""))
        if not schema_path.is_file() or validator.get("schema_sha256") != _sha256_file(
            schema_path
        ):
            errors.append("validator_schema_binding: schema hash mismatch")
        detected_backend = _detect_validation_backend()["backend"]
        if validator.get("locked_backend") != "lightweight":
            errors.append("validator_backend_binding: locked backend is not lightweight")
        if detected_backend != "lightweight":
            errors.append(
                "validator_backend_binding: runtime backend "
                f"{detected_backend!r} differs from locked lightweight"
            )
        if detected_backend == "lightweight" and validator.get("locked_backend") == "lightweight":
            pass_check("validator_backend_binding", "lightweight backend")
        evaluator = budget.get("evaluator_binding") or {}
        _check_module_hash(
            errors,
            label="coarse_evaluator_binding",
            module_path=evaluator.get("coarse_metric_module", ""),
            expected_sha256=evaluator.get("coarse_metric_sha256", ""),
        )
        _check_module_hash(
            errors,
            label="frozen_evaluator_binding",
            module_path=evaluator.get("frozen_evaluator_module", ""),
            expected_sha256=evaluator.get("frozen_evaluator_sha256", ""),
        )
        _check_module_hash(
            errors,
            label="coarse_view_binding",
            module_path=evaluator.get("coarse_view_module", ""),
            expected_sha256=evaluator.get("coarse_view_sha256", ""),
        )
        schedule_binding = budget.get("schedule_binding") or {}
        if schedule is not None and schedule_binding.get("sha256") != schedule.get(
            "schedule_sha256"
        ):
            fail("schedule_binding", "schedule hash differs from prepared budget")

    if (
        contract is not None
        and schedule is not None
        and schedule.get("schedule_sha256") != contract.get("schedule_sha256")
    ):
        fail("schedule_contract_binding", "schedule hash differs from execution contract")

    if schedule is not None and input_rows:
        input_ids = {str(row["sample_id"]) for row in input_rows}
        sample_arms: dict[str, set[str]] = {}
        for entry in schedule.get("entries", []):
            sid = str(entry.get("sample_id") or "")
            if sid not in input_ids:
                fail("schedule_membership", f"unknown sample_id {sid}")
                break
            sample_arms.setdefault(sid, set()).add(str(entry.get("arm")))
        else:
            if len(sample_arms) != SAMPLES_PER_ARM or any(
                arms != set(ARMS) for arms in sample_arms.values()
            ):
                fail("schedule_membership", "not every sample has exactly three arms")
            else:
                pass_check("schedule_membership", "150 samples x 3 arms")

    if schedule is not None and offline_rows:
        try:
            input_by_id = {
                str(row["sample_id"]): str(row["text"]) for row in input_rows
            }
            offline_by_key: dict[tuple[str, str], dict[str, Any]] = {}
            for row in offline_rows:
                key = (str(row.get("arm")), str(row.get("sample_id")))
                if key in offline_by_key:
                    raise ConditionPreservationRunError(f"duplicate offline key {key}")
                offline_by_key[key] = row
            for entry in schedule.get("entries", []):
                arm = str(entry["arm"])
                sid = str(entry["sample_id"])
                row = offline_by_key.get((arm, sid))
                if row is None:
                    raise ConditionPreservationRunError(
                        f"missing offline request for {(arm, sid)}"
                    )
                body = _request_body(arm, sid, input_by_id[sid])
                if row.get("request_body") != body:
                    raise ConditionPreservationRunError(
                        f"offline request body mismatch for {(arm, sid)}"
                    )
                if row.get("request_body_sha256") != _body_sha256(body):
                    raise ConditionPreservationRunError(
                        f"offline body hash mismatch for {(arm, sid)}"
                    )
                prompt = _prompt(arm)
                user = prompt.render_user(sid, input_by_id[sid])
                if row.get("system_prompt_sha256") != _sha256_text(
                    prompt.system_prompt
                ):
                    raise ConditionPreservationRunError(
                        f"offline system prompt hash mismatch for {(arm, sid)}"
                    )
                if row.get("user_prompt_sha256") != _sha256_text(user):
                    raise ConditionPreservationRunError(
                        f"offline user prompt hash mismatch for {(arm, sid)}"
                    )
                if row.get("prompt_composition_sha256") != prompt.composition_sha256:
                    raise ConditionPreservationRunError(
                        f"offline composition hash mismatch for {(arm, sid)}"
                    )
            pass_check("offline_body_binding", "450 scheduled request bodies match")
        except Exception as exc:  # noqa: BLE001
            fail("offline_body_binding", f"{type(exc).__name__}: {exc}")

    status = "pass" if not errors else "fail"
    return {
        "schema_version": "sep_c3_condition_preservation_contract_validation@1.0.0",
        "suite_id": SUITE_ID,
        "status": status,
        "errors": errors,
        "checks": checks,
        "authorization_path": _relative(auth_path),
        "execution_contract_path": _relative(contract_path),
        "prepared_budget_path": _relative(prepared_budget_path),
        "schedule_path": _relative(schedule_path),
        "offline_requests_path": _relative(offline_path),
    }


def _usage_int(usage: Mapping[str, Any] | None, key: str) -> int | None:
    if not isinstance(usage, Mapping):
        return None
    value = usage.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if float(value) < 0:
        return None
    return int(value)


def _usage_verifiable(usage: Mapping[str, Any] | None) -> bool:
    return _usage_int(usage, "prompt_tokens") is not None and _usage_int(
        usage, "completion_tokens"
    ) is not None


def _per_call_cost(
    usage: Mapping[str, Any],
    price: Mapping[str, Any],
) -> dict[str, Any]:
    prompt = _usage_int(usage, "prompt_tokens")
    completion = _usage_int(usage, "completion_tokens")
    if prompt is None or completion is None:
        return {
            "input_tokens": None,
            "output_tokens": None,
            "cache_hit_tokens": None,
            "cache_miss_tokens": None,
            "cost_usd": "unknown",
            "basis": "usage_unverifiable",
        }
    cache_hit = _usage_int(usage, "prompt_cache_hit_tokens")
    cache_miss = _usage_int(usage, "prompt_cache_miss_tokens")
    if cache_hit is None or cache_miss is None:
        cache_hit, cache_miss = 0, prompt
        basis = "conservative_all_input_cache_miss"
    elif cache_hit + cache_miss != prompt:
        cache_hit, cache_miss = 0, prompt
        basis = "cache_split_inconsistent_conservative_all_input_cache_miss"
    else:
        basis = "provider_cache_hit_miss_split"
    cost = (
        float(cache_miss) * float(price["input_cache_miss_per_million"]) / 1_000_000.0
        + float(cache_hit) * float(price["input_cache_hit_per_million"]) / 1_000_000.0
        + float(completion) * float(price["output_per_million"]) / 1_000_000.0
    )
    return {
        "input_tokens": int(prompt),
        "output_tokens": int(completion),
        "cache_hit_tokens": int(cache_hit),
        "cache_miss_tokens": int(cache_miss),
        "cost_usd": round(cost, 8),
        "basis": basis,
    }


class ReservationBudgetGate:
    """Pre-send conservative reservation and post-response usage accounting."""

    def __init__(self, contract: Mapping[str, Any]) -> None:
        self.model_id = str(contract.get("model", {}).get("id") or MODEL_ALIAS)
        self.call_cap = int(contract["call_cap"])
        self.input_token_cap = int(contract["input_token_cap"])
        self.output_token_cap = int(contract["output_token_cap"])
        self.usd_cost_cap = float(contract["usd_cost_cap"])
        price = contract.get("price_snapshot") or {}
        self.peak = dict(price.get("peak") or PEAK_PRICE)
        self.off_peak = dict(price.get("off_peak") or OFF_PEAK_PRICE)
        self.attempts_made = 0
        self.reserved_input_tokens = 0
        self.reserved_output_tokens = 0
        self.reserved_cost_usd = 0.0
        self.actual_input_tokens = 0
        self.actual_output_tokens = 0
        self.actual_cache_hit_tokens = 0
        self.actual_cache_miss_tokens = 0
        self.actual_cost_usd = 0.0
        self.missing_usage_calls = 0
        self.aborted = False
        self.abort_reason: str | None = None

    def abort(self, reason: str) -> None:
        self.aborted = True
        self.abort_reason = reason

    def _reserve_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * float(self.peak["input_cache_miss_per_million"])
            + output_tokens * float(self.peak["output_per_million"])
        ) / 1_000_000.0

    def check_before_send(self, projected_input_tokens: int) -> None:
        if self.aborted:
            raise ConditionPreservationRunError(
                f"budget gate already stopped: {self.abort_reason}"
            )
        if self.attempts_made + 1 > self.call_cap:
            self.abort(
                f"next send would exceed call cap "
                f"({self.attempts_made} made, cap {self.call_cap})"
            )
            raise ConditionPreservationRunError(str(self.abort_reason))
        projected_input = self.reserved_input_tokens + int(projected_input_tokens)
        projected_output = self.reserved_output_tokens + MAX_TOKENS
        projected_cost = self.reserved_cost_usd + self._reserve_cost(
            int(projected_input_tokens), MAX_TOKENS
        )
        if projected_input > self.input_token_cap:
            self.abort(
                f"next send would exceed input token cap ({projected_input})"
            )
            raise ConditionPreservationRunError(str(self.abort_reason))
        if projected_output > self.output_token_cap:
            self.abort(
                f"next send would exceed output token cap ({projected_output})"
            )
            raise ConditionPreservationRunError(str(self.abort_reason))
        if projected_cost > self.usd_cost_cap + 1e-12:
            self.abort(
                f"next send would exceed USD cap ({projected_cost:.6f})"
            )
            raise ConditionPreservationRunError(str(self.abort_reason))

    def register_attempt(self, projected_input_tokens: int) -> None:
        self.attempts_made += 1
        self.reserved_input_tokens += int(projected_input_tokens)
        self.reserved_output_tokens += MAX_TOKENS
        self.reserved_cost_usd += self._reserve_cost(
            int(projected_input_tokens), MAX_TOKENS
        )

    def restore_attempt(self, projected_input_tokens: int) -> None:
        if self.attempts_made + 1 > self.call_cap:
            self.abort("restored history exceeds call cap")
            raise ConditionPreservationRunError(str(self.abort_reason))
        self.register_attempt(projected_input_tokens)

    def _rate_for_window(self, rate_window: str) -> Mapping[str, Any]:
        return self.peak if rate_window == "peak" else self.off_peak

    def record_response(
        self,
        usage: Mapping[str, Any] | None,
        returned_model: str | None,
        *,
        rate_window: str,
    ) -> dict[str, Any] | None:
        if returned_model and self.model_id and returned_model != self.model_id:
            self.abort(
                f"returned model {returned_model!r} != contract model "
                f"{self.model_id!r}"
            )
        if not _usage_verifiable(usage):
            self.missing_usage_calls += 1
            self.abort("usage missing or unverifiable; no further sends")
            return None
        rate = self._rate_for_window(rate_window)
        cost = _per_call_cost(dict(usage), rate)
        if cost["cost_usd"] == "unknown":
            self.missing_usage_calls += 1
            self.abort("usage cost could not be computed; no further sends")
            return cost
        self.actual_input_tokens += int(cost["input_tokens"])
        self.actual_output_tokens += int(cost["output_tokens"])
        self.actual_cache_hit_tokens += int(cost["cache_hit_tokens"])
        self.actual_cache_miss_tokens += int(cost["cache_miss_tokens"])
        self.actual_cost_usd += float(cost["cost_usd"])
        if self.actual_input_tokens > self.input_token_cap:
            self.abort("actual input token cap exceeded")
        if self.actual_output_tokens > self.output_token_cap:
            self.abort("actual output token cap exceeded")
        if self.actual_cost_usd > self.usd_cost_cap + 1e-12:
            self.abort("actual USD cap exceeded")
        return cost

    def snapshot(self) -> dict[str, Any]:
        return {
            "calls_attempted": self.attempts_made,
            "reserved_input_tokens": self.reserved_input_tokens,
            "reserved_output_tokens": self.reserved_output_tokens,
            "reserved_cost_usd_peak_all_input_cache_miss": round(
                self.reserved_cost_usd, 8
            ),
            "actual_input_tokens": self.actual_input_tokens,
            "actual_output_tokens": self.actual_output_tokens,
            "actual_cache_hit_tokens": self.actual_cache_hit_tokens,
            "actual_cache_miss_tokens": self.actual_cache_miss_tokens,
            "actual_cost_usd": round(self.actual_cost_usd, 8),
            "missing_usage_calls": self.missing_usage_calls,
            "call_cap": self.call_cap,
            "input_token_cap": self.input_token_cap,
            "output_token_cap": self.output_token_cap,
            "usd_cost_cap": self.usd_cost_cap,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
        }


def _load_persisted_state(out_dir: Path) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        run_dir = _arm_dir(arm, out_dir)
        attempt_rows = _read_jsonl(run_dir / "attempts.jsonl")
        raw_rows = _read_jsonl(run_dir / "raw_responses.jsonl")
        attempts_by_sid: dict[str, dict[str, Any]] = {}
        raw_by_sid: dict[str, dict[str, Any]] = {}
        for row in attempt_rows:
            sid = str(row.get("sample_id") or "")
            if not sid or sid in attempts_by_sid:
                raise ConditionPreservationRunError(
                    f"duplicate/missing attempt sample: {arm}/{sid}"
                )
            attempts_by_sid[sid] = row
        for row in raw_rows:
            sid = str(row.get("sample_id") or "")
            if not sid or sid in raw_by_sid:
                raise ConditionPreservationRunError(
                    f"duplicate/missing raw sample: {arm}/{sid}"
                )
            raw_by_sid[sid] = row
        for sid in raw_by_sid:
            if sid not in attempts_by_sid:
                raise ConditionPreservationRunError(
                    f"raw response without pre-send attempt record: {arm}/{sid}"
                )
        state[arm] = {
            "attempt_rows": attempt_rows,
            "raw_rows": raw_rows,
            "attempts_by_sid": attempts_by_sid,
            "raw_by_sid": raw_by_sid,
        }
    return state


def _check_in_doubt(state: Mapping[str, Mapping[str, Any]]) -> None:
    for arm in ARMS:
        attempts = state[arm]["attempts_by_sid"]
        raw = state[arm]["raw_by_sid"]
        for sid in attempts:
            if sid not in raw:
                raise ConditionPreservationRunError(
                    f"in_doubt sample requires manual resolution and must not "
                    f"be resent: {arm}/{sid}"
                )


def _restore_gate(
    gate: ReservationBudgetGate,
    state: Mapping[str, Mapping[str, Any]],
) -> None:
    for arm in ARMS:
        for row in state[arm]["attempt_rows"]:
            projected = int(
                row.get("estimated_input_tokens_bytes_div_3")
                or row.get("projected_input_tokens")
                or 0
            )
            if projected <= 0:
                raise ConditionPreservationRunError(
                    f"persisted attempt lacks projected token count: {arm}"
                )
            gate.restore_attempt(projected)
        for row in state[arm]["raw_rows"]:
            usage = row.get("usage") if isinstance(row, Mapping) else None
            if not _usage_verifiable(usage):
                raise ConditionPreservationRunError(
                    f"persisted response has missing/unverifiable usage; "
                    f"no further sends: {arm}/{row.get('sample_id')}"
                )
            returned_model = row.get("returned_model")
            rate_window = str(row.get("rate_window") or "peak")
            gate.record_response(
                usage if isinstance(usage, Mapping) else None,
                returned_model,
                rate_window=rate_window,
            )
    if gate.aborted:
        raise ConditionPreservationRunError(
            f"restored budget gate aborted: {gate.abort_reason}"
        )


def _rate_window_for(timestamp_utc: datetime) -> str:
    return "peak" if base._is_beijing_peak(timestamp_utc) else "off_peak"


def _prediction_base(call: Mapping[str, Any], sample_id: str) -> dict[str, Any]:
    backend = _detect_validation_backend()
    raw_content = str(call.get("raw_response_content") or "")
    return {
        "suite_id": SUITE_ID,
        "sample_id": sample_id,
        "request_id": call.get("request_id"),
        "response_sha256": (
            call.get("response_sha256") or _sha256_text(raw_content)
        ),
        "api_call_status": str(call.get("api_call_status") or "unknown"),
        "transport_status": call.get("transport_status"),
        "decode_status": call.get("decode_status"),
        "transport_error": call.get("error"),
        "output_parse_status": "not_attempted",
        "input_binding_status": "not_attempted",
        "adapter_status": "not_attempted",
        "canonicalizer_status": "not_attempted",
        "canonical_validation_status": "not_attempted",
        "validation_backend": backend["backend"],
        "validation_backend_detail": backend["detail"],
        "validation_backend_jsonschema_available": backend["jsonschema_available"],
        "output_validation_path_version": OUTPUT_VALIDATION_PATH_VERSION,
    }


def _failed_prediction(
    row: dict[str, Any],
    *,
    stage: str,
    message: str,
    status_field: str,
) -> dict[str, Any]:
    row[status_field] = "failed"
    row.update({
        "request_status": "failed",
        "error": message,
        "failure_stage": stage,
        "failure_reason": message,
        "record": {},
    })
    return row


def _adapt_and_canonicalize_payload(
    payload: Any,
    source_text: str,
) -> tuple[
    Any,
    Mapping[str, Any] | None,
    Mapping[str, Any] | None,
    str | None,
    str | None,
]:
    return shared._adapt_and_canonicalize_payload(payload, source_text)


def _convert_call_to_prediction(
    call: Mapping[str, Any],
    *,
    arm: str,
    expected_sample_id: str,
    expected_source_id: str,
    expected_source_text: str,
) -> dict[str, Any]:
    row = _prediction_base(call, expected_sample_id)
    row["arm"] = arm
    raw = str(
        call.get("raw_response_content")
        or call.get("raw_model_output")
        or ""
    )
    try:
        payload = json.loads(shared._strip_json_content(raw))
    except Exception as exc:  # noqa: BLE001
        return _failed_prediction(
            row,
            stage="output_parse",
            message=f"output_parse_failed: {type(exc).__name__}: {exc}",
            status_field="output_parse_status",
        )
    row["output_parse_status"] = "passed"
    row["parsed_output"] = copy.deepcopy(payload)

    binding = shared.check_input_binding(
        payload,
        expected_sample_id=expected_sample_id,
        expected_source_id=expected_source_id,
        expected_source_text=expected_source_text,
    )
    row["input_binding"] = binding
    if binding["status"] != "passed":
        row["input_binding_status"] = "failed"
        return _failed_prediction(
            row,
            stage="input_binding",
            message="input_binding_failed: " + "; ".join(binding["errors"]),
            status_field="input_binding_status",
        )
    row["input_binding_status"] = "passed"

    canonical, adapt_audit, span_audit, failure_stage, failure_reason = (
        shared._adapt_and_canonicalize_payload(payload, expected_source_text)
    )
    row["parser_audit"] = adapt_audit
    row["canonicalizer_audit"] = span_audit
    if failure_stage == "adapter":
        row["adapter_status"] = "failed"
        return _failed_prediction(
            row,
            stage="adapter",
            message=failure_reason or "adapter_failed",
            status_field="adapter_status",
        )
    if failure_stage == "canonicalizer":
        row["adapter_status"] = "passed"
        row["canonicalizer_status"] = "failed"
        return _failed_prediction(
            row,
            stage="canonicalizer",
            message=failure_reason or "canonicalizer_failed",
            status_field="canonicalizer_status",
        )
    row["adapter_status"] = "passed"
    row["canonicalizer_status"] = "passed"

    report, validation_error = shared._runtime_validate_canonical(canonical)
    row["runtime_validation"] = report.to_dict() if report is not None else None
    if validation_error is not None:
        return _failed_prediction(
            row,
            stage="canonical_validation",
            message=validation_error,
            status_field="canonical_validation_status",
        )
    if not (report.schema_valid and report.cross_field_valid):
        return _failed_prediction(
            row,
            stage="canonical_validation",
            message="canonical_validation_failed: " + "; ".join(report.errors),
            status_field="canonical_validation_status",
        )
    row["canonical_validation_status"] = "passed"
    row.update({
        "request_status": "ok",
        "error": None,
        "failure_stage": None,
        "failure_reason": None,
        "record": canonical,
        "canonical_output": canonical,
    })
    return row


def _processing_status_counts(
    predictions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    fields = (
        "transport_status",
        "api_call_status",
        "output_parse_status",
        "input_binding_status",
        "adapter_status",
        "canonicalizer_status",
        "canonical_validation_status",
        "request_status",
    )
    counts: dict[str, dict[str, int]] = {field: {} for field in fields}
    for prediction in predictions:
        for field in fields:
            value = str(prediction.get(field) or "missing")
            counts[field][value] = counts[field].get(value, 0) + 1
    return counts


def _build_arm_outputs(
    arm: str,
    raw_by_sid: Mapping[str, Mapping[str, Any]],
    input_rows: Sequence[Mapping[str, str]],
    gold_doc: Mapping[str, Any],
    out_dir: Path,
    schedule_sha256: str,
    *,
    actual_call_count: int,
    resumed_completed_count: int,
) -> dict[str, Any]:
    run_dir = _arm_dir(arm, out_dir)
    predictions: list[dict[str, Any]] = []
    input_text = {str(row["sample_id"]): str(row["text"]) for row in input_rows}
    for row in input_rows:
        sid = str(row["sample_id"])
        if sid not in raw_by_sid:
            raise ConditionPreservationRunError(f"arm {arm} missing raw sample {sid}")
        call = raw_by_sid[sid]
        prediction = _convert_call_to_prediction(
            call,
            arm=arm,
            expected_sample_id=sid,
            expected_source_id=sid,
            expected_source_text=input_text[sid],
        )
        prediction.update({
            "execution_index": call.get("execution_index"),
            "arm_order_within_sample": call.get("arm_order_within_sample"),
            "timestamp_utc": call.get("timestamp_utc"),
            "rendered_prompt_version_hash": call.get("rendered_prompt_version_hash"),
            "model": call.get("model"),
            "documented_release": call.get("documented_release"),
            "sampling_parameters": call.get("sampling_parameters"),
            "raw_model_output": call.get("raw_model_output"),
            "raw_output_sha256": call.get("raw_output_sha256") or prediction.get(
                "response_sha256"
            ),
            "bare_json_status": call.get("bare_json_status"),
            "provenance": {
                "response_sha256": prediction.get("response_sha256"),
                "request_id": prediction.get("request_id"),
                "output_validation_path_version": OUTPUT_VALIDATION_PATH_VERSION,
                "validation_backend": prediction.get("validation_backend"),
            },
        })
        predictions.append(prediction)

    failed = [row for row in predictions if row.get("request_status") != "ok"]
    evaluation = evaluate_coarse(
        gold_doc,
        attempt_rows(predictions),
        method_id=f"direct_llm_condition_preservation_{arm}",
    )
    evaluation_rel = _relative(run_dir / "evaluation.json")
    evaluation_result = {
        "artifact": evaluation_rel,
        "method_id": evaluation["method_id"],
        "view": evaluation["view"],
        "primary_metric": evaluation["primary_metric"],
        "coarse_five_field_mean_f1": evaluation["coarse_five_field_mean_f1"],
        "coarse_five_field_micro_f1": evaluation["coarse_five_field_micro"]["f1"],
    }
    for prediction in predictions:
        prediction["evaluation_artifact"] = evaluation_rel
        prediction["evaluation_result"] = dict(evaluation_result)

    output_validation_path = _output_validation_path_metadata()
    status_counts = _processing_status_counts(predictions)
    _write_json(run_dir / "evaluation.json", {
        "suite_id": SUITE_ID,
        "arm": arm,
        "repeat_id": REPEAT_ID,
        "denominator": len(predictions),
        "output_validation_path": output_validation_path,
        "processing_status_counts": status_counts,
        "evaluation": evaluation,
    })
    (run_dir / "canonical_predictions.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False) + "\n" for row in predictions
        ),
        encoding="utf-8",
        newline="\n",
    )
    (run_dir / "failed_samples.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in failed),
        encoding="utf-8",
        newline="\n",
    )
    raw_rows = [raw_by_sid[str(row["sample_id"])] for row in input_rows]
    manifest = {
        "schema_version": "sep_c3_condition_preservation_manifest@1.0.0",
        "suite_id": SUITE_ID,
        "arm": arm,
        "arm_definition": (
            "BASE = common + E + frozen R_A"
            if arm == "BASE"
            else (
                "RC1 = BASE + frozen old R_C"
                if arm == "RC1"
                else "RC_KEEP = RC1 + one condition-preservation sentence"
            )
        ),
        "repeat_id": REPEAT_ID,
        "prompt_family": "direct_llm_condition_preservation_v1",
        "sample_count": len(input_rows),
        "actual_call_count": actual_call_count,
        "resumed_completed_count": resumed_completed_count,
        "failed_count": len(failed),
        "evaluation_denominator": len(predictions),
        "output_validation_path": output_validation_path,
        "processing_status_counts": status_counts,
        "schedule_sha256": schedule_sha256,
        "source_hashes": dict(_prompt(arm).source_hashes),
        "prompt_hashes": {
            "system_sha256": _sha256_text(_prompt(arm).system_prompt),
            "user_sha256": _sha256_text(_prompt(arm).user_prompt_template),
            "composition_sha256": _prompt(arm).composition_sha256,
            "generated_prompt_path": _relative(cp.generated_path(arm)),
            "generated_prompt_sha256": _sha256_file(cp.generated_path(arm)),
        },
        "raw_responses_aggregate_sha256": shared.base.aggregate_hash(raw_rows),
        "canonical_predictions_aggregate_sha256": shared.base.aggregate_hash(
            predictions
        ),
        "same_response_binding": all(
            raw.get("response_sha256") == pred.get("response_sha256")
            for raw, pred in zip(raw_rows, predictions)
        ),
    }
    _write_json(run_dir / "manifest.json", manifest)
    return {
        "arm": arm,
        "manifest": manifest,
        "evaluation": evaluation,
        "failed": failed,
        "predictions": predictions,
    }


def _validate_runtime_config(config: LLMConfig, contract: Mapping[str, Any]) -> None:
    if not config.enabled or config.provider != "openai_compatible":
        raise ConditionPreservationRunError("real provider is not enabled")
    if config.model != MODEL_ALIAS:
        raise ConditionPreservationRunError(
            f"runtime model {config.model!r} != {MODEL_ALIAS!r}"
        )
    if config.temperature != TEMPERATURE:
        raise ConditionPreservationRunError("runtime temperature != 0.0")
    if config.top_p != TOP_P:
        raise ConditionPreservationRunError("runtime top_p != 1.0")
    if int(config.max_tokens) != MAX_TOKENS:
        raise ConditionPreservationRunError("runtime max_tokens != 4096")
    if config.seed is not None or config.seed_supported:
        raise ConditionPreservationRunError(
            "runtime seed configuration would change the prepared request body"
        )
    if not config.api_key:
        raise ConditionPreservationRunError("runtime API key missing")
    parsed = urlparse(config.base_url or "")
    if parsed.scheme != "https" or parsed.hostname != "api.deepseek.com":
        raise ConditionPreservationRunError(
            "runtime base URL is not the official https://api.deepseek.com endpoint"
        )
    if contract.get("model", {}).get("id") != config.model:
        raise ConditionPreservationRunError("runtime model differs from contract")


def _expected_transport_body(
    config: LLMConfig,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
    }
    if config.top_p is not None:
        body["top_p"] = config.top_p
    if config.seed_supported and config.seed is not None:
        body["seed"] = config.seed
    body["stream"] = False
    body["thinking"] = {"type": "disabled"}
    return body


def _send_one(
    *,
    arm: str,
    sample: Mapping[str, str],
    transport: Any,
    gate: ReservationBudgetGate,
    out_dir: Path,
    execution_index: int,
    arm_order_within_sample: int,
    real_run: bool,
    config: LLMConfig | None = None,
) -> dict[str, Any]:
    sid = str(sample["sample_id"])
    text = str(sample["text"])
    prompt = _prompt(arm)
    system = prompt.system_prompt
    user = prompt.render_user(sid, text)
    body = _request_body(arm, sid, text)
    body_sha256 = _body_sha256(body)
    projected = _estimated_input_tokens(body)
    gate.check_before_send(projected)

    declared_transport_sha = ""
    if real_run:
        if config is None:
            raise ConditionPreservationRunError("real send requires runtime config")
        expected_body = _expected_transport_body(config, system, user)
        declared_transport_sha = _sha256_bytes(
            json.dumps(expected_body).encode("utf-8")
        )

    attempt_index = gate.attempts_made + 1
    attempt = {
        "suite_id": SUITE_ID,
        "sample_id": sid,
        "arm": arm,
        "repeat_id": REPEAT_ID,
        "execution_index": int(execution_index),
        "arm_order_within_sample": int(arm_order_within_sample),
        "attempt_index": attempt_index,
        "state": "attempt_started",
        "timestamp_utc": _utc_now(),
        "request_body_sha256": body_sha256,
        "expected_transport_request_body_sha256": declared_transport_sha or None,
        "system_prompt_sha256": _sha256_text(system),
        "user_prompt_sha256": _sha256_text(user),
        "prompt_composition_sha256": prompt.composition_sha256,
        "estimated_input_tokens_bytes_div_3": projected,
        "max_tokens": MAX_TOKENS,
        "model": MODEL_ALIAS,
        "documented_release": MODEL_RELEASE,
    }
    _append_jsonl(_arm_dir(arm, out_dir) / "attempts.jsonl", attempt)
    _append_jsonl(out_dir / "attempts.jsonl", attempt)
    gate.register_attempt(projected)

    started_at = _utc_now()
    request_id = f"{arm}:{sid}:{time.time_ns()}"
    content = ""
    decode: dict[str, Any] = {}
    usage: dict[str, Any] = {}
    returned_model: str | None = None
    response_id: str | None = None
    finish_reason: str | None = None
    transport_status = "ok"
    transport_error: str | None = None
    decode_status: str | None = None

    try:
        response = transport.send(LLMRequest(
            source_id=sid,
            source_text=text,
            system_prompt=system,
            user_prompt=user,
        ))
        content = response.content or ""
        decode = getattr(transport, "last_decode", None) or {}
        usage = dict(decode.get("usage") or {})
        decode_status = decode.get("status")
        returned_model = decode.get("model") or getattr(response, "model", None)
        response_id = decode.get("response_id") or request_id
        finish_reason = decode.get("finish_reason") or getattr(
            response, "finish_reason", None
        )
    except Exception as exc:  # noqa: BLE001 - persist transport failure.
        transport_status = "error"
        transport_error = f"{type(exc).__name__}: {exc}"
        returned_model = None

    api_call_status = (
        "ok"
        if transport_status == "ok" and decode_status in (None, "ok_message_content")
        else "error"
    )

    sent_body_sha = getattr(transport, "last_request_body_sha256", None)
    if real_run and sent_body_sha and declared_transport_sha and sent_body_sha != declared_transport_sha:
        gate.abort(
            "actual sent transport body hash differs from the prepared contract body"
        )
    if real_run and not sent_body_sha:
        gate.abort("real transport did not expose the sent request body hash")

    rate_window = _rate_window_for(datetime.now(timezone.utc))
    cost_info = gate.record_response(
        usage if _usage_verifiable(usage) else None,
        returned_model,
        rate_window=rate_window,
    )
    if gate.aborted:
        gate_error = gate.abort_reason
    else:
        gate_error = None

    call = {
        "suite_id": SUITE_ID,
        "sample_id": sid,
        "arm": arm,
        "repeat_id": REPEAT_ID,
        "execution_index": int(execution_index),
        "arm_order_within_sample": int(arm_order_within_sample),
        "attempt_index": attempt_index,
        "estimated_input_tokens_bytes_div_3": projected,
        "timestamp_utc": started_at,
        "completed_at_utc": _utc_now(),
        "request_id": response_id or request_id,
        "request_body_sha256": body_sha256,
        "transport_request_body_sha256": sent_body_sha,
        "raw_response_content": content,
        "raw_model_output": content,
        "response_sha256": _sha256_text(content),
        "raw_output_sha256": _sha256_text(content),
        "bare_json_status": shared._bare_json_status(content),
        "usage": usage,
        "cost": cost_info or {
            "cost_usd": "unknown",
            "basis": "usage_unverifiable",
        },
        "cost_usd": (
            cost_info["cost_usd"] if cost_info and cost_info.get("cost_usd") != "unknown" else "unknown"
        ),
        "rate_window": rate_window,
        "transport_status": transport_status,
        "api_call_status": api_call_status,
        "request_status": transport_status,
        "decode_status": decode_status,
        "finish_reason": finish_reason,
        "returned_model": returned_model,
        "model": MODEL_ALIAS,
        "documented_release": MODEL_RELEASE,
        "sampling_parameters": {
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "max_tokens": MAX_TOKENS,
            "retry": RETRY,
            "stream": False,
            "thinking": {"type": "disabled"},
        },
        "error": transport_error,
        "gate_error": gate_error,
        "network_call": 1,
    }
    _append_jsonl(_arm_dir(arm, out_dir) / "raw_responses.jsonl", call)
    _append_jsonl(out_dir / "raw_responses.jsonl", call)
    return call


def execute(
    *,
    transport_factory: Any = None,
    out_dir: Path | None = None,
    contract_path: Path | None = None,
    auth_path: Path | None = None,
    prepared_budget_path: Path | None = None,
    schedule_path: Path | None = None,
    offline_path: Path | None = None,
    result_writer: Any = None,
    project_env: bool = False,
    enforce_off_peak: bool = False,
) -> dict[str, Any]:
    validation = validate_contracts(
        contract_path=contract_path,
        auth_path=auth_path,
        prepared_budget_path=prepared_budget_path,
        schedule_path=schedule_path,
        offline_path=offline_path,
    )
    if validation["status"] != "pass":
        raise ConditionPreservationRunError(
            "contract validation failed: " + "; ".join(validation["errors"])
        )
    contract = _load_execution_contract(Path(contract_path or EXECUTION_CONTRACT_PATH))
    schedule = _load_schedule(Path(schedule_path or SCHEDULE_PATH))
    input_rows = _input_rows()
    sample_by_id = {str(row["sample_id"]): row for row in input_rows}
    gold_doc = _read_json(core.FORMAL_GOLD)
    run_out_dir = Path(out_dir or OUT_DIR)
    entries = schedule["entries"]

    result: dict[str, Any] = {
        "schema_version": "sep_c3_condition_preservation_execution@1.0.0",
        "suite_id": SUITE_ID,
        "planned_calls": PLANNED_CALLS,
        "call_cap": CALL_CAP,
        "actual_calls": 0,
        "completed_samples": 0,
        "aborted": False,
        "complete": False,
        "runs": [],
        "arms": list(ARMS),
        "output_validation_path": _output_validation_path_metadata(),
        "schedule_sha256": schedule["schedule_sha256"],
        "contract_validation": validation,
        "model": {
            "id": MODEL_ALIAS,
            "documented_release": MODEL_RELEASE,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "max_tokens": MAX_TOKENS,
            "retry": RETRY,
            "stream": False,
            "thinking": {"type": "disabled"},
        },
    }
    started = time.time()
    with RunLock(run_out_dir / ".run.lock"):
        state = _load_persisted_state(run_out_dir)
        _check_in_doubt(state)
        gate = ReservationBudgetGate(contract)
        _restore_gate(gate, state)

        real_run = transport_factory is None
        config: LLMConfig | None = None
        if real_run:
            config = LLMConfig.from_env(project_root=ROOT, load_project_env=bool(project_env))
            _validate_runtime_config(config, contract)
            transport = RealAPITransport(
                config,
                timeout_seconds=180.0,
                policy=H1RequestPolicy(
                    stream=False,
                    thinking={"type": "disabled"},
                    response_format=None,
                ),
            )
        else:
            transport = transport_factory()

        initial_attempt_counts = {
            arm: len(state[arm]["attempts_by_sid"]) for arm in ARMS
        }
        initial_raw_counts = {
            arm: len(state[arm]["raw_by_sid"]) for arm in ARMS
        }
        new_sends = {arm: 0 for arm in ARMS}
        try:
            for entry in entries:
                arm = str(entry["arm"])
                sid = str(entry["sample_id"])
                if sid in state[arm]["raw_by_sid"]:
                    continue
                if sid in state[arm]["attempts_by_sid"]:
                    raise ConditionPreservationRunError(
                        f"in_doubt sample requires manual resolution and must "
                        f"not be resent: {arm}/{sid}"
                    )
                sample = sample_by_id.get(sid)
                if sample is None:
                    raise ConditionPreservationRunError(
                        f"schedule references unknown sample: {sid}"
                    )
                if real_run and enforce_off_peak:
                    base._require_beijing_off_peak()
                call = _send_one(
                    arm=arm,
                    sample=sample,
                    transport=transport,
                    gate=gate,
                    out_dir=run_out_dir,
                    execution_index=int(entry["execution_index"]),
                    arm_order_within_sample=int(entry["arm_order_within_sample"]),
                    real_run=real_run,
                    config=config,
                )
                state[arm]["raw_by_sid"][sid] = call
                state[arm]["raw_rows"].append(call)
                state[arm]["attempts_by_sid"][sid] = {
                    "sample_id": sid,
                    "attempt_index": call.get("attempt_index"),
                    "estimated_input_tokens_bytes_div_3": call.get(
                        "estimated_input_tokens_bytes_div_3"
                    ),
                }
                new_sends[arm] += 1
                if gate.aborted or call.get("gate_error"):
                    raise ConditionPreservationRunError(
                        f"arm {arm} stopped after sample {sid}: "
                        f"{call.get('gate_error') or gate.abort_reason}"
                    )
            if any(
                len(state[arm]["raw_by_sid"]) != SAMPLES_PER_ARM for arm in ARMS
            ):
                raise ConditionPreservationRunError(
                    "schedule completed without 150 persisted responses per arm"
                )
            for arm in ARMS:
                run = _build_arm_outputs(
                    arm,
                    state[arm]["raw_by_sid"],
                    input_rows,
                    gold_doc,
                    run_out_dir,
                    schedule["schedule_sha256"],
                    actual_call_count=new_sends[arm],
                    resumed_completed_count=initial_raw_counts[arm],
                )
                result["runs"].append({
                    "arm": arm,
                    "actual_call_count": new_sends[arm],
                    "resumed_completed_count": initial_raw_counts[arm],
                    "attempt_count": len(state[arm]["attempts_by_sid"]),
                    "failed_count": run["manifest"]["failed_count"],
                    "output_validation_path_version": OUTPUT_VALIDATION_PATH_VERSION,
                    "validation_backend": run["manifest"]["output_validation_path"][
                        "validation_backend"
                    ],
                    "primary_metric": run["evaluation"]["primary_metric"],
                    "coarse_five_field_mean_f1": run["evaluation"][
                        "coarse_five_field_mean_f1"
                    ],
                    "coarse_five_field_micro_f1": run["evaluation"][
                        "coarse_five_field_micro"
                    ]["f1"],
                    "modality_label_macro_f1": run["evaluation"]["modality_labels"].get(
                        "macro_f1"
                    ),
                })
            result["actual_calls"] = sum(
                len(state[arm]["attempts_by_sid"]) for arm in ARMS
            )
            result["completed_samples"] = sum(
                len(state[arm]["raw_by_sid"]) for arm in ARMS
            )
            result["complete"] = (
                result["aborted"] is False
                and result["completed_samples"] == PLANNED_CALLS
                and gate.attempts_made == PLANNED_CALLS
                and not gate.aborted
                and len(result["runs"]) == len(ARMS)
            )
        except Exception as exc:  # noqa: BLE001 - persist partial state.
            result["aborted"] = True
            result["abort_reason"] = f"{type(exc).__name__}: {exc}"
            result["actual_calls"] = sum(
                len(state[arm]["attempts_by_sid"]) for arm in ARMS
            )
            result["completed_samples"] = sum(
                len(state[arm]["raw_by_sid"]) for arm in ARMS
            )
        result["budget_gate"] = gate.snapshot()
        result["runtime_seconds"] = round(time.time() - started, 3)
        result["attempt_counts_per_arm"] = {
            arm: len(state[arm]["attempts_by_sid"]) for arm in ARMS
        }
        result["raw_counts_per_arm"] = {
            arm: len(state[arm]["raw_by_sid"]) for arm in ARMS
        }
        result["new_sends_per_arm"] = dict(new_sends)

    run_out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(run_out_dir / "execution_summary.json", result)
    if result["complete"]:
        if result_writer is not None:
            result_writer(result)
        else:
            _write_json(RESULT_REPORT, result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check or execute the SEP-C3 condition-preservation arms. "
            "No transport is created without --execute --allow-llm and valid "
            "authorization/budget/binding contracts."
        )
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--project-env", action="store_true")
    parser.add_argument("--enforce-off-peak", action="store_true")
    parser.add_argument("--contract", type=Path, default=EXECUTION_CONTRACT_PATH)
    parser.add_argument("--authorization", type=Path, default=AUTHORIZATION_PATH)
    parser.add_argument("--budget", type=Path, default=PREPARED_BUDGET_PATH)
    parser.add_argument("--schedule", type=Path, default=SCHEDULE_PATH)
    parser.add_argument("--offline", type=Path, default=OFFLINE_REQUESTS_PATH)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args(argv)

    if args.check:
        report = validate_contracts(
            contract_path=args.contract,
            auth_path=args.authorization,
            prepared_budget_path=args.budget,
            schedule_path=args.schedule,
            offline_path=args.offline,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "pass" else 1
    if args.execute:
        if not args.allow_llm:
            print(json.dumps({
                "status": "refused",
                "reason": "--execute requires --allow-llm and valid contracts",
            }, ensure_ascii=False, indent=2))
            return 2
        result = execute(
            out_dir=args.out_dir,
            contract_path=args.contract,
            auth_path=args.authorization,
            prepared_budget_path=args.budget,
            schedule_path=args.schedule,
            offline_path=args.offline,
            project_env=args.project_env,
            enforce_off_peak=args.enforce_off_peak,
        )
        summary = {
            "status": "complete" if result.get("complete") else "incomplete",
            "actual_calls": result.get("actual_calls"),
            "completed_samples": result.get("completed_samples"),
            "abort_reason": result.get("abort_reason"),
            "summary_path": _relative(
                Path(args.out_dir or OUT_DIR) / "execution_summary.json"
            ),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if result.get("complete") else 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())