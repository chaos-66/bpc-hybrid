"""S2.8D-R6C1: frozen-pilot continuation mode tests.

Covers the 30 required acceptance items: continuation selection is EXACTLY
original orders 6..10; fail-closed binding against parent frozen plan + prior
R6 evidence; plan-only 0 calls; early-stop cursor correctness; call caps; no
replacement; default behavior unchanged; sanitization.

All tests are offline: never read .env, never call any LLM/API, never touch
Gold or Layer E.
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
    "h1_continuation_runner_module",
    PROJECT_ROOT / "scripts" / "run_sun_llm_fallback.py",
)
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)

SOURCE_TEXT = "The controller shall notify the authority within 72 hours."
SHALL_START = SOURCE_TEXT.index("shall")
SHALL_END = SHALL_START + len("shall")


def _clause(clause_id, *, with_actors=True, with_actions=True, disagreement=False):
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


def _attempt(sample_id, clause):
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


def _pilot_attempts(n=12):
    return [
        _attempt(f"sample_{i:03d}", _clause(f"sample_{i:03d}.c1", with_actors=False, disagreement=True))
        for i in range(1, n + 1)
    ]
def _b0_bundle(tmp_path, attempts):
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


def _prompt_sha(variant):
    return RUNNER.load_prompt(RUNNER._PROMPT_NAME_BY_VARIANT[variant]).sha256


def _build_parent_config(tmp_path, attempts, variant="masked_selected_v5"):
    b0_path, b0_manifest = _b0_bundle(tmp_path, attempts)
    batch = RUNNER.load_b0_predictions(b0_path)
    plans = RUNNER.build_repair_plans(batch)
    ranked = sorted(plans, key=lambda p: (-p.risk_score, p.sample_id, p.clause_index))
    selected = []
    seen = set()
    for plan in ranked:
        if plan.sample_id in seen:
            continue
        seen.add(plan.sample_id)
        selected.append(plan)
        if len(selected) == 10:
            break
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
        "selection_policy": {"ranking": "existing risk_score descending, sample_id, clause_index",
                             "exclude_any_historical_real_call": True, "max_one_plan_per_sample": True, "selected_plan_count": 10},
        "budget": {"hard_api_call_cap": 10, "retry_per_plan": 0, "max_calls_per_plan": 1, "pilot_only": True, "full_pilot": False},
        "early_stop_policy": dict(hpp.DEFAULT_EARLY_STOP_POLICY),
        "historical_calls": {"real_call_count": 0, "unique_plan_key_count": 0, "plan_keys_sha256": hpp.historical_plan_keys_sha256([]), "plan_keys": []},
        "selected_plans": entries,
        "selected_plan_keys_sha256": hpp.selected_plan_keys_sha256(entries),
    }
    return config, b0_path, b0_manifest


def _write_prior_run(tmp_path, parent_config, called_orders=None):
    called_orders = called_orders if called_orders is not None else [1, 2, 3, 4, 5]
    entries = {e["execution_order"]: e for e in parent_config["selected_plans"]}
    prior_dir = tmp_path / "prior_run"
    prior_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"run_id": "fixture_prior", "llm_calls": len(called_orders), "real_api": True}
    (prior_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    caps = []
    for order in sorted(called_orders):
        e = entries[order]
        caps.append({"request_id": f"{e['sample_id']}/{e['clause_id']}", "sample_id": e["sample_id"], "clause_id": e["clause_id"]})
    (prior_dir / "transport_capture.jsonl").write_text("".join(json.dumps(c) + "\n" for c in caps), encoding="utf-8")
    tel_rows = []
    called_keys = set()
    for order in sorted(called_orders):
        e = entries[order]
        tel_rows.append({"sample_id": e["sample_id"], "llm_called": True, "patch_events": [{"clause_id": e["clause_id"], "llm_call_performed": True}]})
        called_keys.add(f"{e['sample_id']}/{e['clause_id']}")
    for e in parent_config["selected_plans"]:
        key = f"{e['sample_id']}/{e['clause_id']}"
        if key not in called_keys:
            tel_rows.append({"sample_id": e["sample_id"], "llm_called": False, "patch_events": []})
    (prior_dir / "h1_telemetry.jsonl").write_text("".join(json.dumps(r) + "\n" for r in tel_rows), encoding="utf-8")
    called_key_list = sorted(called_keys)
    return {
        "run_id": "fixture_prior",
        "manifest_path": str(prior_dir / "manifest.json"),
        "manifest_sha256": hashlib.sha256((prior_dir / "manifest.json").read_bytes()).hexdigest(),
        "transport_capture_path": str(prior_dir / "transport_capture.jsonl"),
        "transport_capture_sha256": hashlib.sha256((prior_dir / "transport_capture.jsonl").read_bytes()).hexdigest(),
        "telemetry_path": str(prior_dir / "h1_telemetry.jsonl"),
        "actual_api_calls": len(called_orders),
        "called_original_orders": sorted(called_orders),
        "called_plan_keys_sha256": hashlib.sha256("\n".join(called_key_list).encode("utf-8")).hexdigest(),
    }
def _build_continuation(tmp_path, attempts):
    parent, b0_path, b0_manifest = _build_parent_config(tmp_path, attempts)
    parent_path = tmp_path / "parent_frozen_plan.json"
    parent_path.write_text(json.dumps(parent, ensure_ascii=False), encoding="utf-8")
    prior = _write_prior_run(tmp_path, parent, called_orders=[1, 2, 3, 4, 5])
    remaining = sorted([e for e in parent["selected_plans"] if e["execution_order"] >= 6], key=lambda e: e["execution_order"])
    entries = []
    for cont_order, pe in enumerate(remaining, start=1):
        entries.append({
            "original_execution_order": pe["execution_order"],
            "continuation_execution_order": cont_order,
            "sample_id": pe["sample_id"],
            "clause_id": pe["clause_id"],
            "clause_index": pe["clause_index"],
            "risk_score": pe["risk_score"],
            "repair_fields": list(pe["repair_fields"]),
            "reasons": list(pe["reasons"]),
            "b0_prediction_sha256": pe["b0_prediction_sha256"],
            "clause_identity_hash": pe["clause_identity_hash"],
            "rendered_masked_context_hash": pe["rendered_masked_context_hash"],
            "prompt_sha256": pe["prompt_sha256"],
            "prior_called": False,
        })
    config = {
        "schema_version": hpp.CONTINUATION_SCHEMA_VERSION,
        "task_id": "S2.8D-R6C1",
        "start_commit": "test",
        "parent_frozen_plan_path": str(parent_path),
        "parent_frozen_plan_sha256": hashlib.sha256(parent_path.read_bytes()).hexdigest(),
        "parent_selected_plan_keys_sha256": parent["selected_plan_keys_sha256"],
        "prior_run": prior,
        "remaining_original_orders": [6, 7, 8, 9, 10],
        "remaining_plan_keys_sha256": hpp.continuation_plan_keys_sha256(entries),
        "model": parent["model"],
        "prompt_variant": parent["prompt_variant"],
        "prompt_sha256": parent["prompt_sha256"],
        "b0": dict(parent["b0"]),
        "budget": {"hard_api_call_cap": 5, "retry_per_plan": 0, "max_calls_per_plan": 1},
        "early_stop_policy": dict(hpp.DEFAULT_EARLY_STOP_POLICY),
        "selected_plans": entries,
    }
    return config, parent_path, b0_path, b0_manifest


def _write_config(tmp_path, config, name="continuation_plan.json"):
    path = tmp_path / name
    path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return path


def _run(tmp_path, config_path, b0_path, b0_manifest, *, max_calls=5, extra=None, mode=None):
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
        args += ["--allow-llm", "--model", "deepseek-v4-pro",
                 "--transport-capture", str(out_dir / "transport_capture.jsonl"),
                 "--continuation-plan", str(config_path), "--inter-call-delay", "0"]
    else:
        args += ["--plan-only", "--continuation-plan", str(config_path)]
    if extra:
        args += extra
    return RUNNER.main(args), out_dir


class TestContinuationStructure:
    def test_01_legal_continuation_selects_orders_6_to_10(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = _build_continuation(tmp_path, _pilot_attempts())
        cp = _write_config(tmp_path, config)
        rc, out_dir = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["selected_plan_count"] == 5
        telemetry = [json.loads(l) for l in (out_dir / "h1_telemetry.jsonl").read_text(encoding="utf-8").splitlines()]
        selected = [(t["sample_id"], t["patch_events"][0]["clause_id"]) for t in telemetry if t["selected_for_call"]]
        entries = {e["sample_id"]: e for e in config["selected_plans"]}
        assert [entries[s]["original_execution_order"] for s, c in selected] == [6, 7, 8, 9, 10]

    def test_02_orders_1_to_5_never_enter_call_list(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = _build_continuation(tmp_path, _pilot_attempts())
        cp = _write_config(tmp_path, config)
        rc, out_dir = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 0
        telemetry = [json.loads(l) for l in (out_dir / "h1_telemetry.jsonl").read_text(encoding="utf-8").splitlines()]
        called = [t["sample_id"] for t in telemetry if t.get("llm_called")]
        selected = [t["sample_id"] for t in telemetry if t["selected_for_call"]]
        assert called == []
        assert len(selected) == 5
        assert all(t["sample_id"] not in {"sample_001", "sample_002", "sample_003", "sample_004", "sample_005"} for t in telemetry if t["selected_for_call"])


class TestContinuationBinding:
    def _valid(self, tmp_path):
        return _build_continuation(tmp_path, _pilot_attempts())

    def test_03_prior_evidence_missing_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        config["prior_run"]["manifest_path"] = str(tmp_path / "missing_manifest.json")
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_04_prior_manifest_hash_mismatch_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        config["prior_run"]["manifest_sha256"] = "0" * 64
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_05_prior_capture_hash_mismatch_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        config["prior_run"]["transport_capture_sha256"] = "0" * 64
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_06_parent_frozen_plan_hash_mismatch_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        config["parent_frozen_plan_sha256"] = "0" * 64
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_07_prior_called_orders_not_1_to_5_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        config["prior_run"]["called_original_orders"] = [1, 2, 3, 4, 6]
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_08_prior_evidence_shows_orders_6_10_called_rejected(self, tmp_path):
        parent, b0_path, b0_manifest = _build_parent_config(tmp_path, _pilot_attempts())
        parent_path = tmp_path / "parent_frozen_plan.json"
        parent_path.write_text(json.dumps(parent, ensure_ascii=False), encoding="utf-8")
        prior = _write_prior_run(tmp_path, parent, called_orders=[1, 2, 3, 4, 6])
        remaining = sorted([e for e in parent["selected_plans"] if e["execution_order"] >= 6], key=lambda e: e["execution_order"])
        entries = [{
            "original_execution_order": pe["execution_order"],
            "continuation_execution_order": i + 1,
            "sample_id": pe["sample_id"], "clause_id": pe["clause_id"], "clause_index": pe["clause_index"],
            "risk_score": pe["risk_score"], "repair_fields": list(pe["repair_fields"]), "reasons": list(pe["reasons"]),
            "b0_prediction_sha256": pe["b0_prediction_sha256"], "clause_identity_hash": pe["clause_identity_hash"],
            "rendered_masked_context_hash": pe["rendered_masked_context_hash"], "prompt_sha256": pe["prompt_sha256"],
            "prior_called": False,
        } for i, pe in enumerate(remaining)]
        config = {
            "schema_version": hpp.CONTINUATION_SCHEMA_VERSION, "task_id": "S2.8D-R6C1", "start_commit": "test",
            "parent_frozen_plan_path": str(parent_path), "parent_frozen_plan_sha256": hashlib.sha256(parent_path.read_bytes()).hexdigest(),
            "parent_selected_plan_keys_sha256": parent["selected_plan_keys_sha256"], "prior_run": prior,
            "remaining_original_orders": [6, 7, 8, 9, 10], "remaining_plan_keys_sha256": hpp.continuation_plan_keys_sha256(entries),
            "model": parent["model"], "prompt_variant": parent["prompt_variant"], "prompt_sha256": parent["prompt_sha256"],
            "b0": dict(parent["b0"]), "budget": {"hard_api_call_cap": 5, "retry_per_plan": 0, "max_calls_per_plan": 1},
            "early_stop_policy": dict(hpp.DEFAULT_EARLY_STOP_POLICY), "selected_plans": entries,
        }
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_09_continuation_overlaps_prior_called_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        config["prior_run"]["called_original_orders"] = [1, 2, 3, 4]
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_10_union_not_parent_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        config["prior_run"]["called_original_orders"] = [1, 2, 3, 4]
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_11_remaining_count_not_5_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        config["selected_plans"] = config["selected_plans"][:4]
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_12_remaining_order_not_6_10_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        config["selected_plans"][0]["original_execution_order"] = 5
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_13_model_mismatch_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        config["model"] = "deepseek-v4-flash"
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_14_prompt_hash_mismatch_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        config["prompt_sha256"] = "0" * 64
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_15_b0_hash_mismatch_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        config["b0"]["attempts_sha256"] = "0" * 64
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_16_risk_repair_reasons_mismatch_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        config["selected_plans"][0]["risk_score"] = config["selected_plans"][0]["risk_score"] + 1
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 2

    def test_17_max_calls_not_5_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest, max_calls=4)
        assert rc == 2

    def test_18_continuation_with_frozen_plan_conflict_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        cp = _write_config(tmp_path, config)
        frozen_path = tmp_path / "frozen.json"
        frozen_path.write_text("{}", encoding="utf-8")
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest, extra=["--frozen-plan", str(frozen_path)])
        assert rc == 2

    def test_19_continuation_with_exclude_plan_conflict_rejected(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = self._valid(tmp_path)
        cp = _write_config(tmp_path, config)
        rc, _ = _run(tmp_path, cp, b0_path, b0_manifest, extra=["--exclude-plan", "sample_006/sample_006.c1"])
        assert rc == 2
class TestContinuationPlanOnly:
    def test_20_21_plan_only_zero_calls_selection_5(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = _build_continuation(tmp_path, _pilot_attempts())
        cp = _write_config(tmp_path, config)
        rc, out_dir = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["selected_plan_count"] == 5
        assert manifest["llm_calls"] == 0
        assert manifest["real_api"] is False
        assert manifest["patch_proposed_count"] == 0
        assert manifest["prediction_changed_sample_count"] == 0
        assert manifest["h1_non_identity_gate"] is False

    def test_30_plan_only_byte_identical_rerun(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = _build_continuation(tmp_path, _pilot_attempts())
        cp = _write_config(tmp_path, config)
        rc, out_dir = _run(tmp_path, cp, b0_path, b0_manifest)
        assert rc == 0
        first = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out_dir.iterdir() if p.is_file()}
        rc, out_dir = _run(tmp_path, cp, b0_path, b0_manifest, extra=["--overwrite"])
        assert rc == 0
        second = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out_dir.iterdir() if p.is_file()}
        assert first == second

    def test_28_default_behavior_unchanged_without_continuation(self, tmp_path):
        attempts = _pilot_attempts()
        b0_path, b0_manifest = _b0_bundle(tmp_path, attempts)
        out_dir = tmp_path / "plain"
        rc = RUNNER.main([
            "--b0-predictions", str(b0_path), "--b0-manifest", str(b0_manifest),
            "--output", str(out_dir / "h1_predictions.jsonl"),
            "--telemetry", str(out_dir / "h1_telemetry.jsonl"),
            "--manifest", str(out_dir / "h1_manifest.json"),
            "--prompt-variant", "masked_selected_v5", "--plan-only", "--max-calls", "10", "--development",
        ])
        assert rc == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["continuation_plan"] is None
        assert manifest["llm_calls"] == 0


class TestContinuationEarlyStop:
    def _transport(self, monkeypatch, plan_by_sample, content_for):
        from bpc_hybrid.llm_client import LLMResponse

        class FakeTransport:
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
                content = content_for(plan)
                self.last_decode = {
                    "status": "ok_message_content", "content": content, "model": "deepseek-v4-pro",
                    "response_id": "chatcmpl-cont", "response_object": "chat.completion", "finish_reason": "stop",
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    "response_body_sha256": None, "response_content_sha256": None, "body_utf8_length": len(content),
                    "content_type_normalized": "application/json", "extraction_source": "message.content",
                    "reasoning_present": False, "reasoning_utf8_length": None, "reasoning_sha256": None,
                    "tool_call_count": 0, "tool_call_summaries": [], "transport_audit": {}, "error_detail": None,
                }
                return LLMResponse(content=content, provider="openai_compatible", model="deepseek-v4-pro", finish_reason="stop")

        monkeypatch.setattr(RUNNER, "RealAPITransport", FakeTransport)
        return FakeTransport

    def _run_real(self, tmp_path, monkeypatch, content_for):
        config, parent_path, b0_path, b0_manifest = _build_continuation(tmp_path, _pilot_attempts())
        cp = _write_config(tmp_path, config)
        batch = RUNNER.load_b0_predictions(b0_path)
        plan_by_sample = {p.sample_id: p for p in RUNNER.build_repair_plans(batch)}
        fake = self._transport(monkeypatch, plan_by_sample, content_for)
        rc, out_dir = _run(tmp_path, cp, b0_path, b0_manifest, mode="allow_llm")
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        return rc, out_dir, manifest, fake

    def test_22_zero_match_branch_cursor_advances(self, tmp_path, monkeypatch):
        def content_for(plan):
            if plan.sample_id == "sample_006":
                return json.dumps({"sample_id": plan.sample_id, "clause_id": plan.clause_id, "repair_fields": list(plan.repair_fields), "patches": {"modality": {"label": "prohibition", "evidence": [{"text": "zzz", "start": 0, "end": 3}]}}, "reason": "x"})
            return json.dumps({"sample_id": plan.sample_id, "clause_id": plan.clause_id, "repair_fields": list(plan.repair_fields), "patches": {"modality": {"label": "prohibition", "evidence": [{"text": "shall", "start": SHALL_START, "end": SHALL_END}]}}, "reason": "x"})
        rc, out_dir, manifest, fake = self._run_real(tmp_path, monkeypatch, content_for)
        assert rc == 0
        assert manifest["llm_calls"] == 5
        assert manifest["early_stop"]["triggered"] is False
        assert fake.total_calls == 5

    def test_23_canonical_invalid_branch_cursor_advances(self, tmp_path, monkeypatch):
        def content_for(plan):
            if plan.sample_id == "sample_006":
                return json.dumps({
                    "sample_id": plan.sample_id, "clause_id": plan.clause_id,
                    "repair_fields": list(plan.repair_fields),
                    "patches": {
                        "modality": {"label": "prohibition", "evidence": [{"text": "shall", "start": SHALL_START, "end": SHALL_END}]},
                        "actors": [{"id": f"{plan.clause_id}.action.1", "text": "The controller", "start": 0, "end": len("The controller"), "normalized": "controller"}],
                        "actor_action_map": [],
                    },
                    "reason": "x",
                })
            return json.dumps({"sample_id": plan.sample_id, "clause_id": plan.clause_id, "repair_fields": list(plan.repair_fields), "patches": {"modality": {"label": "prohibition", "evidence": [{"text": "shall", "start": SHALL_START, "end": SHALL_END}]}}, "reason": "x"})
        rc, out_dir, manifest, fake = self._run_real(tmp_path, monkeypatch, content_for)
        assert rc == 0
        assert manifest["llm_calls"] == 5
        assert manifest["early_stop"]["triggered"] is False
        assert fake.total_calls == 5

    def test_24_true_plan_key_mismatch_still_early_stops(self, tmp_path, monkeypatch):
        reason = hpp.evaluate_early_stop(
            calls_made=1, consecutive_failures=0, provider_returned_model="deepseek-v4-pro",
            required_model="deepseek-v4-pro", capture_bound=True, plan_key_ok=False, hard_call_cap=5,
        )
        assert reason == "plan_key_mismatch"

    def test_25_26_27_call_caps_and_no_replacement(self, tmp_path, monkeypatch):
        def content_for(plan):
            return json.dumps({"sample_id": plan.sample_id, "clause_id": plan.clause_id, "repair_fields": list(plan.repair_fields), "patches": {"modality": {"label": "prohibition", "evidence": [{"text": "shall", "start": SHALL_START, "end": SHALL_END}]}}, "reason": "x"})
        rc, out_dir, manifest, fake = self._run_real(tmp_path, monkeypatch, content_for)
        assert rc == 0
        assert manifest["llm_calls"] == 5
        assert fake.total_calls == 5
        source_ids = [r.source_id for r in fake.sent_requests]
        assert len(source_ids) == len(set(source_ids))
        assert manifest["early_stop"]["triggered"] is False


class TestContinuationSanitization:
    def test_29_config_has_no_source_prompt_credential(self, tmp_path):
        config, parent_path, b0_path, b0_manifest = _build_continuation(tmp_path, _pilot_attempts())
        blob = json.dumps(config, ensure_ascii=False)
        for forbidden in (SOURCE_TEXT, "shall notify", "api_key", "bearer ", "reasoning_content", "approved_text_en", "six_element_decisions"):
            assert forbidden.lower() not in blob.lower(), forbidden



class TestCombineRuns:
    """S2.8D-R6C1: the complete-capsule combine is deterministic and verifies
    disjoint coverage of the parent 10 plans."""

    def _make_run_dir(self, tmp_path, name, parent_config, b0_path, b0_manifest, called_orders):
        import importlib.util as _i
        d = tmp_path / name
        d.mkdir(parents=True, exist_ok=True)
        manifest = {
            "run_id": name, "llm_calls": len(called_orders), "real_api": True,
            "llm_model": "deepseek-v4-pro", "execution_mode": "real_llm",
            "patch_accepted_count": 0, "patch_rejected_count": 0,
            "prediction_changed_sample_count": 0,
            "effective_patch": {"accepted_effective_patch_count": 0},
            "b0_binding": {"sha256": hashlib.sha256(b0_path.read_bytes()).hexdigest()},
        }
        (d / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        batch = RUNNER.load_b0_predictions(b0_path)
        records = {item.record["sample_id"]: item.record for item in batch}
        entries = {e["execution_order"]: e for e in parent_config["selected_plans"]}
        caps, tel, pred = [], [], []
        for order in called_orders:
            e = entries[order]
            caps.append({"request_id": f"{e['sample_id']}/{e['clause_id']}", "sample_id": e["sample_id"], "clause_id": e["clause_id"]})
            tel.append({"sample_id": e["sample_id"], "llm_called": True, "patch_events": [{"clause_id": e["clause_id"], "llm_call_performed": True}]})
        called_set = {f"{entries[o]['sample_id']}/{entries[o]['clause_id']}" for o in called_orders}
        for e in parent_config["selected_plans"]:
            key = f"{e['sample_id']}/{e['clause_id']}"
            if key not in called_set:
                tel.append({"sample_id": e["sample_id"], "llm_called": False, "patch_events": []})
        for sample_id in sorted(records):
            rec = dict(records[sample_id])
            rec["method"] = {"name": "sun_llm_fallback", "schema_source": "test"}
            pred.append(rec)
        (d / "transport_capture.jsonl").write_text("".join(json.dumps(c) + "\n" for c in caps), encoding="utf-8")
        (d / "h1_telemetry.jsonl").write_text("".join(json.dumps(t) + "\n" for t in tel), encoding="utf-8")
        (d / "h1_predictions.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in pred), encoding="utf-8")
        return d

    def test_combine_10_of_10_and_byte_identical(self, tmp_path):
        parent, b0_path, b0_manifest = _build_parent_config(tmp_path, _pilot_attempts())
        parent_path = tmp_path / "parent_frozen_plan.json"
        parent_path.write_text(json.dumps(parent, ensure_ascii=False), encoding="utf-8")
        prior = self._make_run_dir(tmp_path, "prior", parent, b0_path, b0_manifest, [1, 2, 3, 4, 5])
        cont = self._make_run_dir(tmp_path, "cont", parent, b0_path, b0_manifest, [6, 7, 8, 9, 10])
        out_dir = tmp_path / "capsule"
        manifest_path = out_dir / "manifest.json"
        spec = importlib.util.spec_from_file_location("combine_h1_pilot_runs_module", PROJECT_ROOT / "scripts" / "combine_h1_pilot_runs.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        rc = mod.main([
            "--prior-run", str(prior), "--continuation-run", str(cont),
            "--parent-plan", str(parent_path),
            "--b0-predictions", str(b0_path), "--b0-manifest", str(b0_manifest),
            "--output", str(out_dir), "--manifest", str(manifest_path),
        ])
        assert rc == 0
        capsule = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert capsule["coverage"]["complete_10_of_10"] is True
        assert capsule["coverage"]["called_plan_count"] == 10
        assert capsule["coverage"]["distinct_sample_count"] == 10
        assert capsule["coverage"]["status"] == "complete"
        # byte-identical rerun
        first = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out_dir.iterdir() if p.is_file()}
        rc = mod.main([
            "--prior-run", str(prior), "--continuation-run", str(cont),
            "--parent-plan", str(parent_path),
            "--b0-predictions", str(b0_path), "--b0-manifest", str(b0_manifest),
            "--output", str(out_dir), "--manifest", str(manifest_path),
        ])
        assert rc == 0
        second = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out_dir.iterdir() if p.is_file()}
        assert first == second

    def test_combine_rejects_missing_orders(self, tmp_path):
        parent, b0_path, b0_manifest = _build_parent_config(tmp_path, _pilot_attempts())
        parent_path = tmp_path / "parent_frozen_plan.json"
        parent_path.write_text(json.dumps(parent, ensure_ascii=False), encoding="utf-8")
        prior = self._make_run_dir(tmp_path, "prior_bad", parent, b0_path, b0_manifest, [1, 2, 3, 4, 6])
        cont = self._make_run_dir(tmp_path, "cont2", parent, b0_path, b0_manifest, [6, 7, 8, 9, 10])
        spec = importlib.util.spec_from_file_location("combine_h1_pilot_runs_module2", PROJECT_ROOT / "scripts" / "combine_h1_pilot_runs.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        rc = mod.main([
            "--prior-run", str(prior), "--continuation-run", str(cont),
            "--parent-plan", str(parent_path),
            "--b0-predictions", str(b0_path), "--b0-manifest", str(b0_manifest),
            "--output", str(tmp_path / "cap2"), "--manifest", str(tmp_path / "cap2" / "manifest.json"),
        ])
        assert rc == 2
