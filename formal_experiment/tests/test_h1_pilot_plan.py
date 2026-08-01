"""S2.8D-R5: frozen Gold-blind small H1 pilot plan + early-stop contract tests.

Covers the 30 required acceptance items:

* structural frozen-plan validation (count/order/samples/history/budget);
* runner binding fail-closed checks (B0 hashes, prompt, model, risk,
  repair_fields, reasons, clause_index, max-calls, exclude conflict);
* plan-only verification (0 calls, H1 == B0, byte-identical rerun);
* default behavior unchanged without ``--frozen-plan``;
* early-stop contract (model mismatch, capture failure, 3 consecutive
  failures, patch-level rejection does NOT stop, no replacement plans,
  remaining plans marked ``pilot_early_stop_not_called``, call caps);
* sanitization (no source/prompt/Gold/credential in the plan/report).

All tests are offline: they never read ``.env``, never call any LLM/API,
and never touch Gold or Layer E.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from bpc_hybrid import h1_pilot_plan as hpp
from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, SCHEMA_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SPEC = importlib.util.spec_from_file_location(
    "h1_pilot_plan_runner_module",
    PROJECT_ROOT / "scripts" / "run_sun_llm_fallback.py",
)
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)

SOURCE_TEXT = "The controller shall notify the authority within 72 hours."
SHALL_START = SOURCE_TEXT.index("shall")
SHALL_END = SHALL_START + len("shall")


def _clause(clause_id: str, *, with_actors: bool = True, with_actions: bool = True, disagreement: bool = False) -> dict:
    actors = (
        [{"id": f"{clause_id}.actor.1", "text": "The controller", "start": 0, "end": len("The controller"), "normalized": "controller"}]
        if with_actors
        else []
    )
    actions = (
        [{"id": f"{clause_id}.action.1", "text": "notify the authority", "start": SOURCE_TEXT.index("notify the authority"), "end": SOURCE_TEXT.index("notify the authority") + len("notify the authority"), "normalized": "notify authority"}]
        if with_actions
        else []
    )
    return {
        "clause_id": clause_id,
        "clause_span": {"text": SOURCE_TEXT, "start": 0, "end": len(SOURCE_TEXT)},
        "modality": {
            "label": "obligation",
            "evidence": [{"text": "shall", "start": SHALL_START, "end": SHALL_END}],
            "route": "marker_obligation",
            "diagnostic": {
                "clause_classifier_label": "definition" if disagreement else "obligation",
                "marker_label": "permission" if disagreement else "obligation",
                "marker_surface": "shall",
                "record_classifier_label": "obligation",
            },
        },
        "actors": actors,
        "actions": actions,
        "conditions": [],
        "constraints": [],
        "exceptions": [],
        "actor_action_map": (
            [{"actor_id": f"{clause_id}.actor.1", "action_id": f"{clause_id}.action.1"}]
            if (with_actors and with_actions)
            else []
        ),
        "order_relations": [],
        "alignment": {"confidence": 0.9, "status": "validated_split", "supported": True},
        "scope_stats": {"scope_accepted": 1, "scope_rejected": 0},
    }


def _attempt(sample_id: str, clause: dict) -> dict:
    return {
        "request_status": "ok",
        "sample_id": sample_id,
        "record": {
            "schema_version": SCHEMA_VERSION,
            "sample_id": sample_id,
            "source_id": sample_id,
            "source_text": SOURCE_TEXT,
            "clauses": [clause],
            "method": {"name": "sun_rule_only", "schema_source": SCHEMA_SOURCE},
            "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
        },
    }


def _pilot_attempts(n: int = 12) -> list[dict]:
    return [
        _attempt(f"sample_{i:03d}", _clause(f"sample_{i:03d}.c1", with_actors=False, disagreement=True))
        for i in range(1, n + 1)
    ]


def _b0_bundle(tmp_path: Path, attempts: list[dict]) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    b0_path = tmp_path / "b0_attempts.json"
    b0_path.write_text(json.dumps(attempts), encoding="utf-8")
    digest = hashlib.sha256(b0_path.read_bytes()).hexdigest()
    manifest_path = tmp_path / "b0_manifest.json"
    manifest_path.write_text(
        json.dumps({"run_id": "fixture_b0", "method_variant": "b0_fixture", "claim_scope": "test", "artifacts": {"attempts": {"sha256": digest}}}),
        encoding="utf-8",
    )
    return b0_path, manifest_path


def _prompt_sha(variant: str) -> str:
    return RUNNER.load_prompt(RUNNER._PROMPT_NAME_BY_VARIANT[variant]).sha256


def _select_frozen(b0_path: Path, historical: set[str] = set(), n: int = 10) -> list:
    batch = RUNNER.load_b0_predictions(b0_path)
    plans = RUNNER.build_repair_plans(batch)
    ranked = sorted(plans, key=lambda p: (-p.risk_score, p.sample_id, p.clause_index))
    selected = []
    seen = set()
    for plan in ranked:
        key = f"{plan.sample_id}/{plan.clause_id}"
        if key in historical or plan.sample_id in seen:
            continue
        seen.add(plan.sample_id)
        selected.append(plan)
        if len(selected) == n:
            break
    if len(selected) != n or len({p.sample_id for p in selected}) != n:
        raise AssertionError("fixture cannot produce enough distinct-sample plans")
    return batch, selected


def _build_frozen_config(
    tmp_path: Path,
    attempts: list[dict],
    *,
    variant: str = "masked_selected_v5",
    historical: set[str] | None = None,
    n: int = 10,
) -> tuple[dict, Path, Path]:
    historical = historical or set()
    b0_path, b0_manifest = _b0_bundle(tmp_path, attempts)
    batch, selected = _select_frozen(b0_path, historical, n)
    records = {item.record["sample_id"]: item.record for item in batch}
    prompt_sha = _prompt_sha(variant)
    entries = []
    for order, plan in enumerate(selected, start=1):
        record = records[plan.sample_id]
        clause = record["clauses"][plan.clause_index]
        _, audit = RUNNER._build_context_audit(clause, plan, variant)
        entries.append({
            "execution_order": order,
            "sample_id": plan.sample_id,
            "clause_id": plan.clause_id,
            "clause_index": plan.clause_index,
            "risk_score": plan.risk_score,
            "repair_fields": list(plan.repair_fields),
            "reasons": list(plan.reasons),
            "b0_prediction_sha256": RUNNER._prediction_hash(record),
            "clause_identity_hash": RUNNER._json_hash({"clause_id": clause.get("clause_id"), "clause_span": clause.get("clause_span")}),
            "rendered_masked_context_hash": audit["masked_context_sha256"],
            "prompt_sha256": prompt_sha,
            "historical_called": False,
        })
    config = {
        "schema_version": hpp.SCHEMA_VERSION,
        "task_id": hpp.TASK_ID,
        "start_commit": "test",
        "development_only": True,
        "gold_visible": False,
        "model": hpp.REQUIRED_MODEL,
        "prompt_variant": variant,
        "prompt_sha256": prompt_sha,
        "b0": {
            "attempts_path": str(b0_path),
            "attempts_sha256": hashlib.sha256(b0_path.read_bytes()).hexdigest(),
            "manifest_path": str(b0_manifest),
            "manifest_sha256": hashlib.sha256(b0_manifest.read_bytes()).hexdigest(),
        },
        "selection_policy": {
            "ranking": "existing risk_score descending, sample_id, clause_index",
            "exclude_any_historical_real_call": True,
            "max_one_plan_per_sample": True,
            "selected_plan_count": n,
        },
        "budget": {
            "hard_api_call_cap": 10,
            "retry_per_plan": 0,
            "max_calls_per_plan": 1,
            "pilot_only": True,
            "full_pilot": False,
        },
        "early_stop_policy": dict(hpp.DEFAULT_EARLY_STOP_POLICY),
        "historical_calls": {
            "real_call_count": 0,
            "unique_plan_key_count": len(historical),
            "plan_keys_sha256": hpp.historical_plan_keys_sha256(sorted(historical)),
            "plan_keys": sorted(historical),
        },
        "selected_plans": entries,
    }
    return config, b0_path, b0_manifest


def _write_config(tmp_path: Path, config: dict, name: str = "frozen_plan.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return path


def _run(tmp_path, config_path, b0_path, b0_manifest, *, extra=None, max_calls=10, mode=None):
    out_dir = tmp_path / "out"
    args = [
        "--b0-predictions", str(b0_path),
        "--b0-manifest", str(b0_manifest),
        "--output", str(out_dir / "h1_predictions.jsonl"),
        "--telemetry", str(out_dir / "h1_telemetry.jsonl"),
        "--manifest", str(out_dir / "h1_manifest.json"),
        "--prompt-variant", "masked_selected_v5",
        "--max-calls", str(max_calls),
        "--development",
    ]
    if mode == "allow_llm":
        args += [
            "--allow-llm",
            "--model", "deepseek-v4-flash",
            "--transport-capture", str(out_dir / "transport_capture.jsonl"),
            "--frozen-plan", str(config_path),
            "--inter-call-delay", "0",
        ]
    else:
        args += ["--plan-only", "--frozen-plan", str(config_path)]
    if extra:
        args += extra
    return RUNNER.main(args), out_dir


class TestFrozenPlanStructure:
    def test_01_valid_config_selects_exactly_10(self, tmp_path):
        config, _, _ = _build_frozen_config(tmp_path, _pilot_attempts())
        assert hpp.validate_structure(config) == []
        assert len(config["selected_plans"]) == 10
        assert len({e["sample_id"] for e in config["selected_plans"]}) == 10

    def test_02_execution_order_1_to_10(self, tmp_path):
        config, _, _ = _build_frozen_config(tmp_path, _pilot_attempts())
        orders = [e["execution_order"] for e in config["selected_plans"]]
        assert orders == list(range(1, 11))

    def test_03_one_plan_per_sample(self, tmp_path):
        config, _, _ = _build_frozen_config(tmp_path, _pilot_attempts())
        assert len({e["sample_id"] for e in config["selected_plans"]}) == 10

    def test_04_historical_called_plan_rejected(self, tmp_path):
        config, _, _ = _build_frozen_config(tmp_path, _pilot_attempts())
        key = f"{config['selected_plans'][0]['sample_id']}/{config['selected_plans'][0]['clause_id']}"
        config["historical_calls"]["plan_keys"] = sorted(set(config["historical_calls"]["plan_keys"]) | {key})
        config["historical_calls"]["plan_keys_sha256"] = hpp.historical_plan_keys_sha256(config["historical_calls"]["plan_keys"])
        errs = hpp.validate_structure(config)
        assert any("overlap historical" in e for e in errs)

    def test_05_duplicate_plan_rejected(self, tmp_path):
        config, _, _ = _build_frozen_config(tmp_path, _pilot_attempts())
        config["selected_plans"].append(dict(config["selected_plans"][0]))
        errs = hpp.validate_structure(config)
        assert any("duplicate selected plan keys" in e or "exactly 10" in e for e in errs)

    def test_06_duplicate_sample_rejected(self, tmp_path):
        config, _, _ = _build_frozen_config(tmp_path, _pilot_attempts())
        config["selected_plans"][1] = dict(config["selected_plans"][0])
        config["selected_plans"][1]["clause_id"] = "sample_001.cX"
        errs = hpp.validate_structure(config)
        assert any("duplicate sample" in e for e in errs)

    def test_07_plan_count_not_10_rejected(self, tmp_path):
        config, _, _ = _build_frozen_config(tmp_path, _pilot_attempts())
        config["selected_plans"] = config["selected_plans"][:9]
        assert any("exactly 10" in e for e in hpp.validate_structure(config))
        config["selected_plans"] = config["selected_plans"] + config["selected_plans"][:2]
        assert any("exactly 10" in e for e in hpp.validate_structure(config))

    def test_11_model_mismatch_rejected(self, tmp_path):
        config, _, _ = _build_frozen_config(tmp_path, _pilot_attempts())
        config["model"] = "deepseek-v4-pro"
        assert any("model" in e for e in hpp.validate_structure(config))


class TestFrozenPlanBinding:
    def _valid(self, tmp_path):
        config, b0_path, b0_manifest = _build_frozen_config(tmp_path, _pilot_attempts())
        return config, b0_path, b0_manifest

    def test_08_b0_attempts_hash_mismatch_rejected(self, tmp_path):
        config, b0_path, b0_manifest = self._valid(tmp_path)
        config["b0"]["attempts_sha256"] = "0" * 64
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_09_b0_manifest_hash_mismatch_rejected(self, tmp_path):
        config, b0_path, b0_manifest = self._valid(tmp_path)
        config["b0"]["manifest_sha256"] = "0" * 64
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_10_prompt_variant_mismatch_rejected(self, tmp_path):
        config, b0_path, b0_manifest = self._valid(tmp_path)
        config["prompt_variant"] = "full_b0_v4"
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_11b_prompt_sha_mismatch_rejected(self, tmp_path):
        config, b0_path, b0_manifest = self._valid(tmp_path)
        config["prompt_sha256"] = "0" * 64
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_13_risk_score_mismatch_rejected(self, tmp_path):
        config, b0_path, b0_manifest = self._valid(tmp_path)
        config["selected_plans"][0]["risk_score"] = config["selected_plans"][0]["risk_score"] + 1
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_14_repair_fields_mismatch_rejected(self, tmp_path):
        config, b0_path, b0_manifest = self._valid(tmp_path)
        config["selected_plans"][0]["repair_fields"] = ["modality"]
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_15_reasons_mismatch_rejected(self, tmp_path):
        config, b0_path, b0_manifest = self._valid(tmp_path)
        config["selected_plans"][0]["reasons"] = ["non_definition_missing_actor"]
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_16_clause_index_mismatch_rejected(self, tmp_path):
        config, b0_path, b0_manifest = self._valid(tmp_path)
        config["selected_plans"][0]["clause_index"] = 5
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_17_max_calls_not_10_rejected(self, tmp_path):
        config, b0_path, b0_manifest = self._valid(tmp_path)
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest, max_calls=5)
        assert rc == 2

    def test_18_frozen_with_exclude_conflict_rejected(self, tmp_path):
        config, b0_path, b0_manifest = self._valid(tmp_path)
        cp = _write_config(tmp_path, config)
        key = f"{config['selected_plans'][0]['sample_id']}/{config['selected_plans'][0]['clause_id']}"
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest, extra=["--exclude-plan", key])
        assert rc == 2


class TestPlanOnlyVerification:
    def test_19_plan_only_zero_api_calls_and_identity(self, tmp_path):
        config, b0_path, b0_manifest = _build_frozen_config(tmp_path, _pilot_attempts())
        cp = _write_config(tmp_path, config)
        rc, out_dir = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["selected_plan_count"] == 10
        assert manifest["selected_sample_count"] == 10
        assert manifest["llm_calls"] == 0
        assert manifest["real_api"] is False
        assert manifest["patch_proposed_count"] == 0
        assert manifest["patch_accepted_count"] == 0
        assert manifest["prediction_changed_sample_count"] == 0
        assert manifest["h1_non_identity_gate"] is False
        assert manifest["frozen_plan"]["hard_api_call_cap"] == 10
        # H1 == B0 for every sample (against the runner's cleaned B0 records)
        h1 = [json.loads(l) for l in (out_dir / "h1_predictions.jsonl").read_text(encoding="utf-8").splitlines()]
        loaded = RUNNER.load_b0_predictions(b0_path)
        b0_hash = {item.record["sample_id"]: RUNNER._prediction_hash(item.record) for item in loaded}
        assert len(h1) == len(loaded)
        for row in h1:
            assert RUNNER._prediction_hash(row) == b0_hash[row["sample_id"]]

    def test_02b_execution_order_matches_frozen(self, tmp_path):
        config, b0_path, b0_manifest = _build_frozen_config(tmp_path, _pilot_attempts())
        cp = _write_config(tmp_path, config)
        rc, out_dir = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 0
        expected = [(e["sample_id"], e["clause_id"]) for e in sorted(config["selected_plans"], key=lambda e: e["execution_order"])]
        telemetry = [json.loads(l) for l in (out_dir / "h1_telemetry.jsonl").read_text(encoding="utf-8").splitlines()]
        actual = [(t["sample_id"], t["patch_events"][0]["clause_id"]) for t in telemetry if t["selected_for_call"]]
        assert actual == expected

    def test_29_plan_only_byte_identical_rerun(self, tmp_path):
        config, b0_path, b0_manifest = _build_frozen_config(tmp_path, _pilot_attempts())
        cp = _write_config(tmp_path, config)
        rc, out_dir = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 0
        first = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out_dir.iterdir() if p.is_file()}
        rc, out_dir = _run(tmp_path, cp, b0_path, b0_manifest, extra=["--overwrite"])
        assert rc == 0
        second = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out_dir.iterdir() if p.is_file()}
        assert first == second

    def test_20_default_behavior_unchanged_without_frozen_plan(self, tmp_path):
        attempts = _pilot_attempts()
        b0_path, b0_manifest = _b0_bundle(tmp_path, attempts)
        out_dir = tmp_path / "plain"
        rc = RUNNER.main([
            "--b0-predictions", str(b0_path),
            "--b0-manifest", str(b0_manifest),
            "--output", str(out_dir / "h1_predictions.jsonl"),
            "--telemetry", str(out_dir / "h1_telemetry.jsonl"),
            "--manifest", str(out_dir / "h1_manifest.json"),
            "--prompt-variant", "masked_selected_v5",
            "--plan-only",
            "--max-calls", "10",
            "--development",
        ])
        assert rc == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["frozen_plan"] is None
        assert manifest["llm_calls"] == 0
        assert manifest["selected_plan_count"] == 10


class TestEarlyStop:
    def _transport(self, monkeypatch, model="deepseek-v4-flash", capture_sha="1" * 64, content="", patch_model=None):
        from bpc_hybrid.llm_client import LLMResponse

        class FakeTransport:
            total_calls = 0
            sent_requests = []

            def __init__(self, config, timeout_seconds=60.0, policy=None):
                self.config = config
                self.policy = policy
                self.sent = []
                self.last_request_body_sha256 = capture_sha
                self.last_request_policy = policy.to_dict() if policy is not None else None
                self.last_endpoint_descriptor = {"scheme": "https", "host": "api.test.invalid", "port": None, "path": "/v1/chat/completions"}
                self.last_decode = {
                    "status": "ok_message_content" if content else "empty_final_content",
                    "content": content,
                    "model": patch_model if patch_model is not None else model,
                    "response_id": "chatcmpl-test",
                    "response_object": "chat.completion",
                    "finish_reason": "stop",
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    "response_body_sha256": None,
                    "response_content_sha256": None,
                    "body_utf8_length": len(content),
                    "content_type_normalized": "application/json",
                    "extraction_source": "message.content",
                    "reasoning_present": False,
                    "reasoning_utf8_length": None,
                    "reasoning_sha256": None,
                    "tool_call_count": 0,
                    "tool_call_summaries": [],
                    "transport_audit": {},
                    "error_detail": None,
                }

            def send(self, request):
                type(self).total_calls += 1
                type(self).sent_requests.append(request)
                self.sent.append(request)
                return LLMResponse(content=content, provider="openai_compatible", model=patch_model if patch_model is not None else model, finish_reason="stop")

        monkeypatch.setattr(RUNNER, "RealAPITransport", FakeTransport)
        return FakeTransport

    def _early_stop_run(self, tmp_path, fake_cls, attempts=None):
        attempts = attempts or _pilot_attempts()
        config, b0_path, b0_manifest = _build_frozen_config(tmp_path, attempts)
        cp = _write_config(tmp_path, config)
        rc, out_dir = _run(tmp_path, cp, b0_path, b0_manifest, mode="allow_llm")
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        telemetry = [json.loads(l) for l in (out_dir / "h1_telemetry.jsonl").read_text(encoding="utf-8").splitlines()]
        return rc, out_dir, manifest, telemetry, fake_cls

    def test_21_provider_model_mismatch_triggers_early_stop(self, tmp_path, monkeypatch):
        fake = self._transport(monkeypatch, patch_model="deepseek-v4-pro", content=json.dumps({"sample_id": "x", "clause_id": "x.c1", "repair_fields": [], "patches": {}}))
        rc, _, manifest, telemetry, f = self._early_stop_run(tmp_path, fake)
        assert rc == 0
        assert manifest["llm_calls"] == 1
        assert manifest["early_stop"]["triggered"] is True
        assert manifest["early_stop"]["reason"] == "provider_model_mismatch"
        assert len(manifest["early_stop"]["not_called_plan_keys"]) == 9
        statuses = {e.get("status") for row in telemetry for e in row["patch_events"] if e.get("selected_for_call")}
        assert hpp.EARLY_STOP_NOT_CALLED in statuses

    def test_22_capture_binding_failure_triggers_early_stop(self, tmp_path, monkeypatch):
        fake = self._transport(monkeypatch, capture_sha=None, content=json.dumps({"sample_id": "x", "clause_id": "x.c1", "repair_fields": [], "patches": {}}))
        rc, _, manifest, telemetry, f = self._early_stop_run(tmp_path, fake)
        assert rc == 0
        assert manifest["llm_calls"] == 1
        assert manifest["early_stop"]["reason"] == "capture_binding_failure"

    def test_23_three_consecutive_failures_trigger_early_stop(self, tmp_path, monkeypatch):
        fake = self._transport(monkeypatch, content="")
        rc, _, manifest, telemetry, f = self._early_stop_run(tmp_path, fake)
        assert rc == 0
        assert manifest["llm_calls"] == 3
        assert manifest["early_stop"]["reason"] == "consecutive_transport_or_extraction_failures"
        assert len(manifest["early_stop"]["not_called_plan_keys"]) == 7

    def test_24_patch_rejection_does_not_stop(self, tmp_path, monkeypatch):
        # Valid JSON envelope with an invented span text -> canonicalizer
        # zero-match rejection per plan; no global early stop; all 10 called.
        attempts = _pilot_attempts()
        plan0 = None
        config0, b0_path, b0_manifest = _build_frozen_config(tmp_path, attempts)
        first = config0["selected_plans"][0]
        fake = self._transport(
            monkeypatch,
            content=json.dumps({
                "sample_id": first["sample_id"],
                "clause_id": first["clause_id"],
                "repair_fields": first["repair_fields"],
                "patches": {"modality": {"label": "obligation", "evidence": [{"text": "zzz not in source", "start": 0, "end": 3}]}},
            }),
        )
        rc, _, manifest, telemetry, f = self._early_stop_run(tmp_path, fake, attempts=attempts)
        assert rc == 0
        assert manifest["llm_calls"] == 10
        assert manifest["early_stop"]["triggered"] is False
        assert manifest["patch_rejected_count"] == 10

    def test_25_26_no_replacement_and_not_called_marked(self, tmp_path, monkeypatch):
        fake = self._transport(monkeypatch, patch_model="deepseek-v4-pro", content=json.dumps({"sample_id": "x", "clause_id": "x.c1", "repair_fields": [], "patches": {}}))
        rc, out_dir, manifest, telemetry, f = self._early_stop_run(tmp_path, fake)
        assert rc == 0
        # not_called keys must be a subset of the frozen plan keys and no
        # replacement plan keys appear.
        frozen_keys = set()
        for row in telemetry:
            for ev in row["patch_events"]:
                if ev.get("selected_for_call"):
                    frozen_keys.add(f"{row['sample_id']}/{ev['clause_id']}")
        assert set(manifest["early_stop"]["not_called_plan_keys"]) <= frozen_keys
        not_called_rows = [row for row in telemetry for ev in row["patch_events"] if ev.get("status") == hpp.EARLY_STOP_NOT_CALLED]
        assert len(not_called_rows) == 9

    def test_27_28_call_caps_never_exceeded(self, tmp_path, monkeypatch):
        fake = self._transport(monkeypatch, content=json.dumps({"sample_id": "x", "clause_id": "x.c1", "repair_fields": [], "patches": {}}))
        rc, _, manifest, telemetry, f = self._early_stop_run(tmp_path, fake)
        assert rc == 0
        assert manifest["llm_calls"] == 10
        assert f.total_calls == 10
        source_ids = [r.source_id for r in f.sent_requests]
        assert len(source_ids) == len(set(source_ids))


def _patch_for_plan(plan, valid: bool) -> str:
    clause_id = plan.clause_id
    if not valid:
        return json.dumps({
            "sample_id": plan.sample_id,
            "clause_id": clause_id,
            "repair_fields": ["modality", "actors", "actor_action_map"],
            "patches": {"modality": {"label": "prohibition", "evidence": [{"text": "zzz not in source", "start": 0, "end": 3}]}},
            "reason": "synthetic invalid",
        })
    return json.dumps({
        "sample_id": plan.sample_id,
        "clause_id": clause_id,
        "repair_fields": ["modality", "actors", "actor_action_map"],
        "patches": {
            "modality": {"label": "prohibition", "evidence": [{"text": "shall", "start": SHALL_START, "end": SHALL_END}]},
            "actors": [{"id": f"{clause_id}.actor.1", "text": "The controller", "start": 0, "end": len("The controller"), "normalized": "controller"}],
            "actor_action_map": [{"actor_id": f"{clause_id}.actor.1", "action_id": f"{clause_id}.action.1"}],
        },
        "reason": "synthetic valid",
    })


class TestEarlyStopRegression:
    """S2.8D-R6 regression: the frozen-order cursor must not drift when a
    coordinate-canonicalization failure short-circuits mid-pilot, and the
    frozen pilot replay must preserve the real run's early-stop state."""

    def _seq_transport(self, monkeypatch, plan_by_sample, valid_for):
        from bpc_hybrid.llm_client import LLMResponse

        class SeqTransport:
            total_calls = 0
            sent_requests = []

            def __init__(self, config, timeout_seconds=60.0, policy=None):
                self.config = config
                self.policy = policy
                self.last_request_body_sha256 = "1" * 64
                self.last_request_policy = policy.to_dict() if policy is not None else None
                self.last_endpoint_descriptor = {"scheme": "https", "host": "api.test.invalid", "port": None, "path": "/v1/chat/completions"}

            def send(self, request):
                type(self).total_calls += 1
                type(self).sent_requests.append(request)
                plan = plan_by_sample[request.source_id]
                content = _patch_for_plan(plan, valid=valid_for(plan))
                self.last_decode = {
                    "status": "ok_message_content", "content": content, "model": "deepseek-v4-flash",
                    "response_id": "chatcmpl-seq", "response_object": "chat.completion", "finish_reason": "stop",
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    "response_body_sha256": None, "response_content_sha256": None, "body_utf8_length": len(content),
                    "content_type_normalized": "application/json", "extraction_source": "message.content",
                    "reasoning_present": False, "reasoning_utf8_length": None, "reasoning_sha256": None,
                    "tool_call_count": 0, "tool_call_summaries": [], "transport_audit": {}, "error_detail": None,
                }
                return LLMResponse(content=content, provider="openai_compatible", model="deepseek-v4-flash", finish_reason="stop")

        monkeypatch.setattr(RUNNER, "RealAPITransport", SeqTransport)
        return SeqTransport

    def test_early_stop_no_false_plan_key_mismatch_on_canonicalization_failure(self, tmp_path, monkeypatch):
        # Reproduces the S2.8D-R6 scenario: plan #4 returns a patch that fails
        # coordinate canonicalization (zero match) while later plans succeed.
        # The frozen-order cursor must not drift; all 10 plans must be called
        # and no early stop may trigger.
        attempts = _pilot_attempts()
        config, b0_path, b0_manifest = _build_frozen_config(tmp_path, attempts)
        cp = _write_config(tmp_path, config)
        batch = RUNNER.load_b0_predictions(b0_path)
        plans = RUNNER.build_repair_plans(batch)
        plan_by_sample = {p.sample_id: p for p in plans}
        frozen = sorted(config["selected_plans"], key=lambda e: e["execution_order"])
        bad = frozen[3]["sample_id"]  # 4th frozen plan fails canonicalization

        def valid_for(plan):
            return plan.sample_id != bad

        fake = self._seq_transport(monkeypatch, plan_by_sample, valid_for)
        rc, out_dir = _run(tmp_path, cp, b0_path, b0_manifest, mode="allow_llm")
        assert rc == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["llm_calls"] == 10
        assert manifest["early_stop"]["triggered"] is False
        assert fake.total_calls == 10
        # The plan that failed canonicalization is recorded as a rejection,
        # and later plans still run.
        assert manifest["patch_rejected_count"] == 1
        assert manifest["patch_accepted_count"] == 9

    def _replay_row(self, plan, record, variant, content_dict):
        body = json.dumps({
            "id": "chatcmpl-replay", "object": "chat.completion", "model": "deepseek-v4-flash",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": json.dumps(content_dict)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })
        return {
            "request_id": f"{plan.sample_id}/{plan.clause_id}",
            "sample_id": plan.sample_id,
            "clause_id": plan.clause_id,
            "clause_index": plan.clause_index,
            "prompt_sha256": _prompt_sha(variant),
            "prompt_variant": variant,
            "b0_prediction_sha256": RUNNER._prediction_hash(record),
            "response_body": body,
            "content_type": "application/json",
            "http_status": 200,
        }

    def test_frozen_replay_partial_rows_preserves_early_stop(self, tmp_path):
        attempts = _pilot_attempts()
        config, b0_path, b0_manifest = _build_frozen_config(tmp_path, attempts)
        cp = _write_config(tmp_path, config)
        batch = RUNNER.load_b0_predictions(b0_path)
        records = {item.record["sample_id"]: item.record for item in batch}
        entries = sorted(config["selected_plans"], key=lambda e: e["execution_order"])
        # rows for the first 5 plans only (the "called" subset)
        rows = []
        for e in entries[:5]:
            plan = RUNNER.build_repair_plans(batch)
            p = next(x for x in RUNNER.build_repair_plans(batch) if x.sample_id == e["sample_id"])
            content = {
                "sample_id": p.sample_id, "clause_id": p.clause_id,
                "repair_fields": p.repair_fields,
                "patches": {"modality": {"label": "prohibition", "evidence": [{"text": "shall", "start": SHALL_START, "end": SHALL_END}]}},
                "reason": "synthetic valid",
            }
            rows.append(self._replay_row(p, records[p.sample_id], "masked_selected_v5", content))
        rows_path = tmp_path / "replay_rows.jsonl"
        rows_path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        out_dir = tmp_path / "replay_out"
        rc = RUNNER.main([
            "--b0-predictions", str(b0_path),
            "--b0-manifest", str(b0_manifest),
            "--frozen-plan", str(cp),
            "--output", str(out_dir / "h1_predictions.jsonl"),
            "--telemetry", str(out_dir / "h1_telemetry.jsonl"),
            "--manifest", str(out_dir / "h1_manifest.json"),
            "--prompt-variant", "masked_selected_v5",
            "--offline-transport-replay",
            "--transport-responses-jsonl", str(rows_path),
            "--max-calls", "10",
            "--development",
        ])
        assert rc == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["llm_calls"] == 5
        assert manifest["real_api"] is False
        assert manifest["early_stop"]["triggered"] is False
        assert sorted(manifest["early_stop"]["replay_preserved_not_called_plan_keys"]) == sorted(
            f"{e['sample_id']}/{e['clause_id']}" for e in entries[5:]
        )
        telemetry = [json.loads(l) for l in (out_dir / "h1_telemetry.jsonl").read_text(encoding="utf-8").splitlines()]
        not_called = [t for t in telemetry if any(ev.get("status") == hpp.EARLY_STOP_NOT_CALLED for ev in t["patch_events"])]
        assert len(not_called) == 5

    def test_frozen_replay_byte_identical_rerun(self, tmp_path):
        attempts = _pilot_attempts()
        config, b0_path, b0_manifest = _build_frozen_config(tmp_path, attempts)
        cp = _write_config(tmp_path, config)
        batch = RUNNER.load_b0_predictions(b0_path)
        records = {item.record["sample_id"]: item.record for item in batch}
        entries = sorted(config["selected_plans"], key=lambda e: e["execution_order"])
        rows = []
        for e in entries[:5]:
            p = next(x for x in RUNNER.build_repair_plans(batch) if x.sample_id == e["sample_id"])
            content = {"sample_id": p.sample_id, "clause_id": p.clause_id, "repair_fields": p.repair_fields, "patches": {}, "reason": "synthetic valid"}
            rows.append(self._replay_row(p, records[p.sample_id], "masked_selected_v5", content))
        rows_path = tmp_path / "replay_rows.jsonl"
        rows_path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        out_dir = tmp_path / "replay_out"
        base_args = [
            "--b0-predictions", str(b0_path), "--b0-manifest", str(b0_manifest),
            "--frozen-plan", str(cp),
            "--output", str(out_dir / "h1_predictions.jsonl"),
            "--telemetry", str(out_dir / "h1_telemetry.jsonl"),
            "--manifest", str(out_dir / "h1_manifest.json"),
            "--prompt-variant", "masked_selected_v5",
            "--offline-transport-replay", "--transport-responses-jsonl", str(rows_path),
            "--max-calls", "10", "--development",
        ]
        assert RUNNER.main(list(base_args)) == 0
        first = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out_dir.iterdir() if p.is_file()}
        assert RUNNER.main(list(base_args) + ["--overwrite"]) == 0
        second = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out_dir.iterdir() if p.is_file()}
        assert first == second


class TestSanitization:
    def test_30_plan_contains_no_source_prompt_gold_credential(self, tmp_path):
        config, _, _ = _build_frozen_config(tmp_path, _pilot_attempts())
        blob = json.dumps(config, ensure_ascii=False)
        for forbidden in (SOURCE_TEXT, "shall notify", "api_key", "bearer ", "reasoning_content", "approved_text_en", "six_element_decisions", "request_status"):
            assert forbidden.lower() not in blob.lower(), forbidden
