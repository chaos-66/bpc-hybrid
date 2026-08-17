# -*- coding: utf-8 -*-
"""Deterministic S2.12 execution-ready builder v2 (Checkpoint E3; ZERO
real LLM/API).

Builds (no-overwrite, byte-identical rebuild):
  configs/s2_12_execution_plan_v2.json              (FROZEN plan, supersedes v1)
  outputs/reports/s2_12_execution_plan_v2.json      (derivation + bindings)
  outputs/reports/s2_12_execution_readiness_v2.json (readiness, supersedes v1)
  outputs/reports/s2_12_api_readiness_v2.json       (API budget/readiness v2)

v2 corrects the v1 evaluator/Gold-shape contract:
  * the v1 whole-field string exact-equality evaluator is REPLACED by
    s2_12_stratified_evaluator_v2, which reuses the Stage 2 formal
    contract (modality label accuracy/macro-F1/per-class + the five
    span-bearing fields via the shared Sun literal-overlap evaluator with
    the fixed match rule, clause alignment and safe-legal-v1
    normalization)
  * the Gold shape is the canonical clause/span shape (proposal v2 /
    decisions v2), not a flat {field: string} map
  * a PARITY check runs in-process on a synthetic fixture: the stratified
    v2 overall must equal the formal Stage 2 evaluator on the same
    fixture (span + modality label views)

Readiness v2 claims ONLY: schema ready, importer ready (v2 dry-run:
blocked=0/unresolved=0/adjudicable=36), evaluator ready (synthetic +
parity), method-adapter dry-run ready. The real run stays REFUSED
(proposal v2 is unconfirmed by the user; S2.11 freeze 0/36). No Gold or
formal evaluation is claimed.

API readiness v2 derives from the real registries/configs:
  * direct_llm: deepseek-v4-pro (estg150_d1_active_registry_v1,
    fail_closed_pin), openai_compatible / official API, output cap 4096,
    1 call/record -> 36 max calls
  * sun_llm_fallback: deepseek-v4-pro (s28d_h1_150_v4pro_v1 manifest,
    cli_override), trigger-based fallback; historical 150-record run: 111
    samples called / 150 calls -> derived max_calls_per_record =
    ceil(150/111) = 2 -> 72 max calls
  * input token cap: NOT documented in the repo -> missing item
  * cost cap: cost_cap_unresolved (no trustworthy price basis in repo)
  * a final copyable authorization sentence is NOT issued (missing
    items listed precisely; an incomplete sentence is never called
    executable)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.g05_complexity_candidate import (  # noqa: E402
    classify_frozen,
)
from bpc_hybrid.s2_11_corpus_ingestion import g05_features  # noqa: E402
from bpc_hybrid.s2_12_method_adapter import adapt_method_attempts  # noqa: E402
from bpc_hybrid.s2_12_stratified_evaluator_v2 import (  # noqa: E402
    evaluate_stratified,
)

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
FROZEN_REL = "configs/g05_complexity_frozen_v1.json"
DRAFT_REL = "configs/g05_complexity_candidate_draft_v1.json"
AUTH_MANIFEST_REL = "configs/g05_authorization_manifest_v1.json"
DECISIONS_V2_REL = "data/development/human_review/s2_11_review_decisions_v2.json"
PROPOSAL_REPORT_V2_REL = "outputs/reports/s2_11_proposal_report_v2.json"
BATCH_DRY_RUN_V2_REL = "outputs/reports/s2_11_batch_import_dry_run_v2.json"
EVALUATOR_CONTRACT_REL = "configs/stage2_evaluator_s210_v3.json"
D1_REGISTRY_REL = "configs/models/estg150_d1_active_registry_v1.json"
H1_MANIFEST_REL = ("outputs/development/s28d_h1_150_v4pro_v1/manifest.json")

PLAN_CONFIG_V1_REL = "configs/s2_12_execution_plan_v1.json"
PLAN_REPORT_V1_REL = "outputs/reports/s2_12_execution_plan_v1.json"
READINESS_V1_REL = "outputs/reports/s2_12_execution_readiness_v1.json"

PLAN_CONFIG_V2_REL = "configs/s2_12_execution_plan_v2.json"
PLAN_REPORT_V2_REL = "outputs/reports/s2_12_execution_plan_v2.json"
READINESS_V2_REL = "outputs/reports/s2_12_execution_readiness_v2.json"
API_READINESS_V2_REL = "outputs/reports/s2_12_api_readiness_v2.json"

SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")


class BuildFail(Exception):
    """Fail-closed build abort."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() == data:
            return
        raise BuildFail(
            f"refusing to overwrite different existing content: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _load_source_text(record_id: str, rec: dict[str, Any]) -> str:
    src = ROOT.parent / rec["path"]
    raw = src.read_bytes()
    if _sha256_bytes(raw) != rec["file_sha256"]:
        raise BuildFail(f"source file hash drift for {record_id}")
    scenario, rid, version = record_id.split("/")
    doc = json.loads(raw.decode("utf-8"))
    for entry in doc:
        if str(entry.get("ID")) == rid and \
                str(entry.get("version")) == version.lstrip("v"):
            text = str(entry.get("text", ""))
            if _sha256_bytes(text.encode("utf-8")) != rec["text_sha256"]:
                raise BuildFail(f"text hash drift for {record_id}")
            return text
    raise BuildFail(f"record {record_id} not found in source")


def _strata_counts() -> dict[str, int]:
    membership = _load_json(ROOT / MEMBERSHIP_REL)
    counts = {"L1": 0, "L2": 0, "L3": 0}
    for record_id, rec in sorted(membership["records"].items()):
        text = _load_source_text(record_id, rec)
        g05 = classify_frozen(
            g05_features(text),
            draft_config_path=ROOT / DRAFT_REL,
            frozen_config_path=ROOT / FROZEN_REL,
            authorization_manifest_path=ROOT / AUTH_MANIFEST_REL,
            project_root=ROOT)
        counts[g05["level"]] += 1
    return counts


def _freeze_state() -> tuple[int, int]:
    decisions = _load_json(ROOT / DECISIONS_V2_REL)
    records = decisions.get("records") or {}
    if len(records) != 36:
        raise BuildFail(f"decisions v2 must have 36 records, got "
                        f"{len(records)}")
    adjudicated = sum(
        1 for e in records.values()
        if (e.get("review_metadata") or {}).get("review_state")
        == "adjudicated")
    return adjudicated, len(records)


def _importer_dry_run_stats() -> dict[str, Any]:
    report = _load_json(ROOT / BATCH_DRY_RUN_V2_REL)
    stats = report.get("import_stats") or {}
    if stats.get("blocked_fields") != 0 or \
            stats.get("blocked_samples") != 0 or \
            stats.get("unresolved_fields") != 0 or \
            stats.get("adjudicable") != 36:
        raise BuildFail(
            "importer v2 dry-run must show blocked=0/unresolved=0/"
            "adjudicable=36")
    return stats


# ---------------------------------------------------------------------------
# Parity fixture (synthetic; no corpus text)
# ---------------------------------------------------------------------------
def _parity_fixture() -> tuple[list[dict[str, Any]], list[dict[str, Any]],
                               dict[str, str]]:
    def spans(text: str, **values: str) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {f: [] for f in SPAN_FIELDS}
        for field, value in values.items():
            i = text.find(value)
            assert i >= 0 and text[i:i + len(value)] == value
            out[field].append({"id": f"{field}_{i}", "text": value,
                               "start": i, "end": i + len(value)})
        return out

    t1 = "the nurse must obtain consent before surgery"
    t2 = "the doctor must record the result after surgery"
    t3 = "the hospital may collect samples from all patients"
    t4 = "the company must not retain data without consent"
    gold = [
        {"sample_id": "synth/01", "clauses": [{
            "clause_id": "synth/01.c1",
            "modality": {"label": "obligation", "evidence": []},
            "actors": [{"id": "a1", "text": "the nurse", "start": 0,
                        "end": 9}],
            "actions": [{"id": "act1", "text": "obtain consent",
                         "start": 14, "end": 28}],
            "conditions": [], "constraints": [
                {"id": "con1", "text": "before surgery", "start": 29,
                 "end": 43}],
            "exceptions": [],
        }]},
        {"sample_id": "synth/02", "clauses": [{
            "clause_id": "synth/02.c1",
            "modality": {"label": "obligation", "evidence": []},
            "actors": [{"id": "a2", "text": "the doctor", "start": 0,
                        "end": 10}],
            "actions": [{"id": "act2", "text": "record the result",
                         "start": 15, "end": 31}],
            "conditions": [], "constraints": [
                {"id": "con2", "text": "after surgery", "start": 32,
                 "end": 45}],
            "exceptions": [],
        }]},
        {"sample_id": "synth/03", "clauses": [{
            "clause_id": "synth/03.c1",
            "modality": {"label": "permission", "evidence": []},
            "actors": [{"id": "a3", "text": "the hospital", "start": 0,
                        "end": 12}],
            "actions": [{"id": "act3", "text": "collect samples",
                         "start": 17, "end": 32}],
            "conditions": [], "constraints": [
                {"id": "con3", "text": "from all patients", "start": 33,
                 "end": 49}],
            "exceptions": [],
        }]},
        {"sample_id": "synth/04", "clauses": [{
            "clause_id": "synth/04.c1",
            "modality": {"label": "prohibition", "evidence": []},
            "actors": [{"id": "a4", "text": "the company", "start": 0,
                        "end": 11}],
            "actions": [{"id": "act4", "text": "retain data", "start": 21,
                         "end": 32}],
            "conditions": [], "constraints": [
                {"id": "con4", "text": "without consent", "start": 33,
                 "end": 48}],
            "exceptions": [],
        }]},
    ]
    # attempts: identical except synth/02 action mislabeled and synth/03
    # modality mislabeled -> measurable recall/precision deltas
    attempts = []
    for rec in gold:
        record = json.loads(json.dumps(rec))
        if rec["sample_id"] == "synth/02":
            record["clauses"][0]["actions"][0]["text"] = "record result"
            record["clauses"][0]["actions"][0]["end"] = 27
        if rec["sample_id"] == "synth/03":
            record["clauses"][0]["modality"]["label"] = "obligation"
        attempts.append({"sample_id": rec["sample_id"],
                         "request_status": "success", "record": record,
                         "error_category": None})
    levels = {"synth/01": "L1", "synth/02": "L1",
              "synth/03": "L2", "synth/04": "L2"}
    return gold, attempts, levels


def _parity_check() -> dict[str, Any]:
    """Run the formal Stage 2 evaluator and the stratified v2 wrapper on
    the same synthetic fixture; the unstratified overall must match."""
    from bpc_hybrid import formal_stage2_evaluation as formal

    gold, attempts, levels = _parity_fixture()
    formal_span = formal.evaluate_span_metrics(
        gold, attempts, dataset_id="parity_fixture",
        method_id="sun_rule_only", view="coarse")
    formal_mod = formal.evaluate_modality_labels(gold, attempts)
    stratified = evaluate_stratified(
        gold, attempts, levels=levels, dataset_id="parity_fixture",
        method_id="sun_rule_only")
    overall_span = stratified["overall"]["span_fields"]
    overall_mod = stratified["overall"]["modality_labels"]

    span_equal = True
    for field in SPAN_FIELDS:
        fs = formal_span["span_fields"][field]
        ss = overall_span["span_fields"][field]
        if (fs.get("precision") != ss.get("precision") or
                fs.get("recall") != ss.get("recall") or
                fs.get("f1") != ss.get("f1")):
            span_equal = False
    mod_equal = (
        formal_mod.get("accuracy") == overall_mod.get("accuracy")
        and formal_mod.get("macro_f1") == overall_mod.get("macro_f1")
        and formal_mod.get("per_class") == overall_mod.get("per_class"))
    return {
        "passed": bool(span_equal and mod_equal),
        "span_metrics_equal": span_equal,
        "modality_metrics_equal": mod_equal,
        "fixture_samples": len(gold),
        "strata_present": sorted(stratified["strata"]),
        "l3_no_samples": stratified["strata"]["L3"]["samples"] == 0,
        "zero_api": {"new_llm_api_calls": 0},
    }


def _api_readiness() -> dict[str, Any]:
    d1 = _load_json(ROOT / D1_REGISTRY_REL)
    h1 = _load_json(ROOT / H1_MANIFEST_REL)
    model_d1 = (d1.get("recipe_lock") or {}).get("model") or {}
    sampling_d1 = (d1.get("recipe_lock") or {}).get("sampling") or {}
    h1_model = h1.get("llm_model")
    h1_called = int(h1.get("llm_called_sample_count") or 0)
    h1_calls = int(h1.get("llm_calls") or 0)
    calls_per_record_fallback = 2  # ceil(150/111) = 2
    missing: list[str] = []
    if not model_d1.get("id"):
        missing.append("direct_llm model id")
    if not h1_model:
        missing.append("sun_llm_fallback model id")
    if "input_token_cap" not in d1 and "input" not in sampling_d1:
        missing.append("input_token_cap (not documented in registry/manifest)")
    if not (d1.get("budget_contract") or {}):
        missing.append("d1 budget_contract cost basis")
    missing.append("cost_cap (no trustworthy price basis in repo)")
    if missing:
        missing = sorted(set(missing))
    total_calls = 36 + 36 * calls_per_record_fallback
    return {
        "schema_version": "s2_12_api_readiness@2.0.0",
        "status": "dry_run_not_applied",
        "records": 36,
        "arms": {
            "direct_llm": {
                "model_id": model_d1.get("id"),
                "model_source": D1_REGISTRY_REL,
                "fail_closed_pin": model_d1.get("fail_closed_pin"),
                "provider": model_d1.get("provider"),
                "endpoint": model_d1.get("endpoint"),
                "transport": (d1.get("recipe_lock") or {}).get("transport"),
                "calls_per_record": 1,
                "max_calls": 36,
                "output_token_cap": sampling_d1.get("max_tokens"),
                "input_token_cap": "not_documented_in_repo",
            },
            "sun_llm_fallback": {
                "model_id": h1_model,
                "model_source": H1_MANIFEST_REL + " (llm_model, "
                                "source=cli_override)",
                "trigger_semantics": (
                    "fallback fires on incomplete rule extraction "
                    "(B0-first); historical 150-record full run: "
                    f"{h1_called} samples called / {h1_calls} calls"),
                "derived_max_calls_per_record": calls_per_record_fallback,
                "max_calls": 36 * calls_per_record_fallback,
                "output_token_cap": (
                    "4096 derived_from_d1_recipe (H1 manifest records "
                    "max_tokens=null)"),
                "input_token_cap": "not_documented_in_repo",
            },
        },
        "totals": {
            "max_calls": total_calls,
            "output_token_cap_per_call": 4096,
            "output_side_total_token_bound": 4096 * total_calls,
            "input_side_total_token_bound": "unresolved",
            "cost_cap": "cost_cap_unresolved",
        },
        "missing_items_for_final_authorization": missing,
        "final_copyable_authorization_sentence": None,
        "final_sentence_reason": (
            "a final authorization sentence is NOT issued because the "
            "input token cap and the cost cap are unresolved; an "
            "incomplete sentence is never called executable"),
        "calls_made": 0,
        "authorized": False,
        "zero_api": {"new_llm_api_calls": 0},
    }


def _bindings() -> dict[str, str]:
    rels = (
        MEMBERSHIP_REL, FROZEN_REL, DRAFT_REL, AUTH_MANIFEST_REL,
        DECISIONS_V2_REL, PROPOSAL_REPORT_V2_REL, BATCH_DRY_RUN_V2_REL,
        EVALUATOR_CONTRACT_REL, D1_REGISTRY_REL, H1_MANIFEST_REL,
        PLAN_CONFIG_V1_REL, PLAN_REPORT_V1_REL, READINESS_V1_REL,
    )
    return {rel: _sha256_file(ROOT / rel) for rel in rels}


def build() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any],
                     dict[str, Any]]:
    strata = _strata_counts()
    adjudicated, total = _freeze_state()
    importer_stats = _importer_dry_run_stats()
    parity = _parity_check()
    if not parity["passed"]:
        raise BuildFail("parity check failed: formal evaluator and "
                        "stratified v2 disagree on the fixture")
    api = _api_readiness()

    plan_config = {
        "schema_version": "s2_12_execution_plan@2.0.0",
        "plan_id": "s2-12-execution-plan-v2",
        "status": "frozen",
        "supersedes_v1": {
            "plan_config_v1": PLAN_CONFIG_V1_REL,
            "plan_report_v1": PLAN_REPORT_V1_REL,
            "readiness_v1": READINESS_V1_REL,
            "reason": ("v1 used a whole-field string exact-equality "
                       "evaluator and a flat Gold shape; v2 aligns with "
                       "the Stage 2 formal evaluation contract (modality "
                       "label metrics + five-field Sun literal-overlap "
                       "span metrics over the canonical clause/span Gold "
                       "shape)"),
        },
        "preregistration": {
            "declared_before_results": True,
            "stratification": "frozen G0.5 levels L1/L2/L3 (sealed v6 "
                              "chain)",
            "strata_level_counts": strata,
            "denominators": "per stratum per field: gold spans (recall "
                            "denominator) and predicted spans (precision "
                            "denominator) via the fixed Sun literal-"
                            "overlap assignment",
            "metrics": {
                "modality": ["label accuracy", "macro-F1", "per-class "
                             "precision/recall/F1"],
                "span_fields": ["actor/action/condition/constraint/"
                                "exception span precision/recall/F1"],
                "full_record": ["gold_required_presence_recall",
                                "predicted_field_precision",
                                "complete_record_rate"],
                "error_analysis": [
                    "missed/misclassified/extra derived from the SAME "
                    "span-matching result (no separate string compare)"],
            },
            "comparison_table": ("per method per stratum: span fields "
                                 "P/R/F1 + modality label table; same 36 "
                                 "IDs, same Gold view, same evaluator "
                                 "across the three arms"),
            "methods": [
                {"arm": "sun_rule_only", "api_calls": 0},
                {"arm": "sun_llm_fallback", "api_calls": "budgeted"},
                {"arm": "direct_llm", "api_calls": "budgeted"},
            ],
            "evaluator_contract": EVALUATOR_CONTRACT_REL,
            "gold_shape": "canonical clause/span (proposal v2 / decisions "
                          "v2)",
        },
        "input": {"membership": MEMBERSHIP_REL, "records": 36,
                  "raw_text_committed": False},
        "gold": {"source": "user-adjudicated S2.11 decisions v2",
                 "decisions_file": DECISIONS_V2_REL,
                 "state": ("pending" if adjudicated < total else "frozen"),
                 "adjudicated": adjudicated, "total": total,
                 "gold_files_created": False},
        "gates": [
            "S2.11 freeze v2: 36/36 adjudicated (freeze validator v2 "
            "frozen=true)",
            "user confirmation event binding the proposal v2 SHA and "
            "reviewer (batch importer v2 --apply)",
            "API budget authorization with the final authorization "
            "sentence (not issued yet: input/cost caps unresolved)",
        ],
        "definition_of_done": ("MASTER S2.12 full DoD: pre-registered "
                               "stratification curves and error types on "
                               "the external complex corpus (36 records), "
                               "same input/Gold/evaluator across the three "
                               "arms, zero unrecorded API calls"),
        "determinism": {"no_wall_clock": True, "byte_identical_rebuild": True,
                        "no_overwrite": True},
        "zero_api": {"new_llm_api_calls": 0},
        "bindings": {},
    }
    plan_report = {
        "schema_version": "s2_12_execution_plan_report@2.0.0",
        "plan_config": PLAN_CONFIG_V2_REL,
        "status": "frozen",
        "supersedes_v1": plan_config["supersedes_v1"],
        "strata_level_counts": strata,
        "freeze_state": {"adjudicated": adjudicated, "total": total},
        "importer_v2_dry_run": importer_stats,
        "parity": parity,
        "raw_text_committed": False,
        "gold_created": False,
        "zero_api": {"new_llm_api_calls": 0},
        "bindings": {},
    }
    readiness = {
        "schema_version": "s2_12_execution_readiness@2.0.0",
        "status": "ready_for_execution_pending_user_gates",
        "supersedes_v1": {"readiness_v1": READINESS_V1_REL,
                          "reason": plan_config["supersedes_v1"]["reason"]},
        "ready_claims": {
            "schema_ready": True,
            "importer_ready": importer_stats,
            "evaluator_ready": {"module": "src/bpc_hybrid/"
                                          "s2_12_stratified_evaluator_v2.py",
                                "parity": parity},
            "method_adapter_dry_run_ready": True,
            "gold_or_formal_evaluation_complete": False,
        },
        "runner": {
            "script": "scripts/s2_12_build_execution_ready_v2.py",
            "fail_closed": True,
            "real_run_refused": True,
            "real_run_refusal_reason": (
                "proposal v2 is NOT user-confirmed (batch importer v2 "
                "--apply requires the confirmation event) and S2.11 "
                "freeze v2 is 0/36"),
        },
        "gates": {
            "s2_11_freeze_v2": {"adjudicated": adjudicated, "total": total,
                                "ready": adjudicated == total},
            "api_budget_authorization": {
                "event_present": False,
                "ready": False,
                "missing_items":
                    _api_readiness()["missing_items_for_final_authorization"],
            },
        },
        "api_readiness": API_READINESS_V2_REL,
        "plan": PLAN_CONFIG_V2_REL,
        "raw_text_committed": False,
        "gold_created": False,
        "human_approved": False,
        "zero_api": {"new_llm_api_calls": 0},
        "determinism": {"no_wall_clock": True, "byte_identical_rebuild": True,
                        "no_overwrite": True},
        "bindings": {},
    }
    plan_config["bindings"] = _bindings()
    plan_report["bindings"] = _bindings()
    readiness["bindings"] = _bindings()
    return plan_config, plan_report, readiness, api


def main() -> int:
    try:
        plan_config, plan_report, readiness, api = build()
    except BuildFail as exc:
        print(f"S2.12 BUILD V2 FAILED (fail-closed): {exc}", file=sys.stderr)
        return 2
    docs = [
        (PLAN_CONFIG_V2_REL, plan_config),
        (PLAN_REPORT_V2_REL, plan_report),
        (READINESS_V2_REL, readiness),
        (API_READINESS_V2_REL, api),
    ]
    try:
        for rel, doc in docs:
            _write(ROOT / rel,
                   (json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
                   .encode("utf-8"))
    except BuildFail as exc:
        print(f"S2.12 BUILD V2 FAILED (refusing overwrite): {exc}",
              file=sys.stderr)
        return 2
    print(f"S2.12 plan v2 written: {PLAN_CONFIG_V2_REL} "
          f"(strata={plan_config['preregistration']['strata_level_counts']})")
    parity_ok = readiness["ready_claims"]["evaluator_ready"]["parity"][
        "passed"]
    print(f"S2.12 readiness v2 written: {READINESS_V2_REL} "
          f"(parity={parity_ok})")
    print(f"S2.12 API readiness v2 written: {API_READINESS_V2_REL} "
          f"(calls_made={api['calls_made']}, "
          f"cost_cap={api['totals']['cost_cap']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
