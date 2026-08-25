# -*- coding: utf-8 -*-
"""Barrientos ablation suite v2 — orchestrator + D/E real-model executor.

Modes:
* ``--suite``            : run the offline suite (A renamed conditions +
                           B structural metrics + C + D/E readiness), write
                           outputs/development/barrientos_ablation_suite_v2/
                           and outputs/reports/barrientos_ablation_comparison_v2.*
* ``--dry-run``          : off-network wiring check of the D/E real-model arms
                           (zero API calls; prints per-arm sample counts and
                           prompt hashes).
* ``--execute-de``       : real-model execution of the D and E arms.  Requires
                           ``--auth-file`` (user API authorization).  Records
                           raw responses, canonical predictions, evaluation,
                           manifest, hashes, runtime, usage, cost and failed
                           samples per arm.  NEVER runs without authorization.

v2 fixes vs v1:
* A conditions renamed to full_locked / schema_only_approx / raw_approx and
  framed as an OFFLINE APPROXIMATION SENSITIVITY ANALYSIS (raw model JSON was
  not persisted in the locked s27 artifacts).
* E input contract v2: 36 unique versioned IDs derived from the frozen S2.12
  complex corpus (the flawed 38-record v1 contract is superseded).
* B: structural metrics (actor-action map gold resolvability, predicted map
  internal validity, map-change-vs-full samples, modality label macro-F1,
  per-field P/R/F1, valid/invalid counts, per-flag change cases).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

CONFIG = ROOT / "configs/ablations/barrientos_ablation_suite_v2.json"
E_CONTRACT = ROOT / "configs/ablations/e_same_data_input_contract_v2.json"
ESTG_INPUT = ROOT / "data/input/estg150_formal_inference_input_v2.json"
D1_REGISTRY = ROOT / "configs/models/estg150_d1_active_registry_v1.json"
OUT_DIR = ROOT / "outputs/development/barrientos_ablation_suite_v2"
REPORT_DIR = ROOT / "outputs/reports"
B_RESULTS = ROOT / "outputs/development/b0_module_removal_ablation_v1/results.json"

D_ARMS = ("D-full", "D-no-fewshot", "D-minimal", "D-barrientos-style")
E_ARMS = ("E-ours", "E-barrientos-faithful", "E-module-swapped")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {label}: {path}") from exc


def _write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


# ---------------------------------------------------------------------------
# Suite mode
# ---------------------------------------------------------------------------


def _run_a(config: Mapping[str, Any]) -> dict[str, Any]:
    from run_barrientos_ablation_suite_v1 import run_experiment_a
    a = run_experiment_a(config)
    old_to_new = {
        "full": "full_locked",
        "schema_only": "schema_only_approx",
        "raw_approximation": "raw_approx",
    }
    a["conditions"] = {old_to_new[k]: v for k, v in a["conditions"].items()}
    a["nature"] = (
        "OFFLINE APPROXIMATION SENSITIVITY ANALYSIS: full_locked is the locked "
        "D1-R3 canonical result; schema_only_approx and raw_approx are "
        "constructed from the post-canonical output by first-occurrence "
        "re-anchoring because the raw model JSON was not persisted. They are "
        "NOT exact raw-response ablations."
    )
    return a


def _run_b() -> dict[str, Any]:
    if not B_RESULTS.is_file():
        raise RuntimeError("B results missing; run run_b0_module_removal_ablation_v1 first")
    b = _load_json(B_RESULTS, "B results")
    return {
        "experiment": "B_rules_only_module_removal",
        "status": "executed",
        "full": {
            "overall_f1": b["full"]["metrics"]["overall"]["f1"],
            "per_field_f1": {k: v["f1"] for k, v in b["full"]["metrics"]["per_field"].items()},
            "modality_label_accuracy": b["full"]["modality_label_accuracy"],
            "modality_label_macro_f1": b["full"]["modality_label_macro_f1"],
            "actor_action_map_metrics": b["full"]["actor_action_map_metrics"],
            "valid_outputs": b["full"]["valid_outputs"],
        },
        "per_flag": {
            flag: {
                "overall_f1": b[flag]["metrics"]["overall"]["f1"],
                "delta_vs_full_f1": b[flag].get("delta_vs_full_f1"),
                "per_field_f1": b[flag]["per_field_f1"],
                "modality_label_accuracy": b[flag]["modality_label_accuracy"],
                "modality_label_macro_f1": b[flag]["modality_label_macro_f1"],
                "actor_action_map_metrics": b[flag]["actor_action_map_metrics"],
                "failed_samples": b[flag]["failed_samples"],
                "valid_outputs": b[flag]["valid_outputs"],
                "example_change_cases": b[flag].get("example_change_cases", []),
                "note": b[flag].get("note"),
            }
            for flag in ("no_lexicon_extensions", "no_modality_classifier",
                         "no_actor_action_ownership", "no_multi_match_guard",
                         "no_de_en_alignment_validation")
        },
        "note": (
            "span P/R/F1 does not cover the structural actor-action map; "
            "gold-vs-predicted exact ID matching is not computable (gold map "
            "uses unresolved short IDs); reported map metrics are gold "
            "resolvability, predicted internal validity and "
            "map-change-vs-full samples"
        ),
    }


def _run_c(config: Mapping[str, Any]) -> dict[str, Any]:
    from run_barrientos_ablation_suite_v1 import run_experiment_c
    return run_experiment_c(config)


def _run_de() -> dict[str, Any]:
    e = _load_json(E_CONTRACT, "E v2 contract")
    return {
        "experiment": "D_E_real_model_arms",
        "status": "ready_to_execute_not_executed",
        "blocker": (
            "real model API calls require explicit user authorization; this "
            "zero-API batch does not execute them"
        ),
        "D_arms": {
            "D-full": {"status": "reuse_locked_formal_result"},
            "D-no-fewshot": {"status": "ready_to_execute"},
            "D-minimal": {"status": "ready_to_execute"},
            "D-barrientos-style": {"status": "ready_to_execute"},
        },
        "E_arms": {
            "E-ours": {"status": "ready_to_execute"},
            "E-barrientos-faithful": {"status": "ready_to_execute"},
            "E-module-swapped": {"status": "ready_to_execute"},
            "stability": {
                "E-ours_runs": 5, "E-barrientos-faithful_runs": 5,
                "E-module-swapped_runs": 1,
                "note": "first main comparison run counts toward the five",
            },
        },
        "e_contract_v2": {
            "path": "configs/ablations/e_same_data_input_contract_v2.json",
            "sha256": _sha256_file(E_CONTRACT),
            "count": e["input_surface"]["count"],
            "unique_ids": e["input_surface"]["unique_ids"],
        },
        "real_execution_command": (
            "python scripts/run_barrientos_ablation_suite_v2.py --execute-de "
            "--auth-file <USER_AUTH> "
            "--runtime-home D:/environment/stanford-corenlp-4.5.10 "
            "(requires user API authorization)"
        ),
    }


def run_suite() -> int:
    config = _load_json(CONFIG, "suite v2 config")
    results: dict[str, Any] = {
        "schema_version": "barrientos_ablation_results@2.0.0",
        "zero_api_batch": True,
        "config_sha256": _sha256_file(CONFIG),
    }
    t0 = time.time()
    results["A"] = _run_a(config)
    results["B"] = _run_b()
    results["C"] = _run_c(config)
    results["D_E"] = _run_de()
    results["runtime_seconds"] = round(time.time() - t0, 3)

    if OUT_DIR.exists():
        raise RuntimeError(f"refusing to overwrite: {OUT_DIR}")
    OUT_DIR.mkdir(parents=True)
    (OUT_DIR / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "config_snapshot.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "A": {
            "nature": results["A"]["nature"],
            "condition_metrics": {
                k: {"overall": v["metrics"]["overall"],
                    "per_field_f1": {f: v["metrics"]["per_field"][f]["f1"]
                                     for f in v["metrics"]["per_field"]}}
                for k, v in results["A"]["conditions"].items()
            },
        },
        "B": results["B"],
        "C": results["C"],
        "D_E": results["D_E"],
    }
    report = {
        "schema_version": "barrientos_ablation_comparison@2.0.0",
        "generated_zero_api": True,
        "summary": summary,
        "full_results": str((OUT_DIR / "results.json").relative_to(ROOT)),
        "notes": {
            "A": "offline approximation sensitivity analysis (raw JSON not persisted)",
            "B": "with structural map + modality label metrics",
            "D_E": "ready_to_execute; real model calls require authorization",
        },
    }
    _write_json(REPORT_DIR / "barrientos_ablation_comparison_v2.json", report)

    md = ["# Barrientos Ablation Comparison v2 (zero API)", "",
          "## Experiment A (offline approximation sensitivity analysis)",
          "| condition | overall F1 | note |"]
    for k, v in results["A"]["conditions"].items():
        md.append("| {} | {:.4f} | {} |".format(k, v["metrics"]["overall"]["f1"],
                                                v["note"]))
    md += ["", "## Experiment B (Rules-Only module removal, structural metrics)",
           "| flag | ΔF1 | label acc | label macro-F1 | map change | "
           "pred map validity |"]
    for flag, v in results["B"]["per_flag"].items():
        m = v["actor_action_map_metrics"]
        md.append("| {} | {:+.4f} | {:.4f} | {:.4f} | {} | {:.4f} |".format(
            flag, v["delta_vs_full_f1"] or 0.0,
            v["modality_label_accuracy"]["clause_label_accuracy"],
            v["modality_label_macro_f1"]["macro_f1"],
            m.get("map_change_vs_full_samples", 0),
            m.get("predicted_map_internal_validity", 0.0)))
    c = results["C"]
    md += ["", "## Experiment C",
           "4-class: {}; 3-class shared: {}; definition excluded={} ({:.2f}%)".format(
               c["four_class_counts"], c["three_class_shared_counts"],
               c["definition_excluded_count"],
               c["definition_coverage_loss_ratio"] * 100)]
    de = results["D_E"]
    md += ["", "## Experiment D/E", "status: " + de["status"],
           "E contract v2: {} unique records (sha {})".format(
               de["e_contract_v2"]["count"],
               de["e_contract_v2"]["sha256"][:16])]
    (REPORT_DIR / "barrientos_ablation_comparison_v2.md").write_text(
        "\n".join(md) + "\n", encoding="utf-8")
    print(f"Barrientos suite v2 complete (zero API): {OUT_DIR.relative_to(ROOT)}")
    return 0


# ---------------------------------------------------------------------------
# D/E real-model executor (gated)
# ---------------------------------------------------------------------------


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path.relative_to(ROOT.parent))


def _prompt_for(arm: str) -> Path:
    prompts = {
        "D-full": ROOT / "prompts/sun_compat/direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md",
        "D-no-fewshot": ROOT / "prompts/sun_compat/ablation_v1/direct_llm_no_fewshot_prompt_v1.md",
        "D-minimal": ROOT / "prompts/sun_compat/ablation_v1/direct_llm_minimal_prompt_prompt_v1.md",
        "D-barrientos-style": ROOT / "prompts/sun_compat/ablation_v1/direct_llm_barrientos_style_prompt_v1.md",
        "E-ours": ROOT / "prompts/sun_compat/direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md",
        "E-barrientos-faithful": ROOT.parent / "references/barrientos_2026/artifact_input/prompts/formalize_requirements_prompt.txt",
        "E-module-swapped": ROOT / "prompts/sun_compat/ablation_v1/direct_llm_barrientos_style_prompt_v1.md",
    }
    return prompts[arm]


def dry_run() -> dict[str, Any]:
    estg = _load_json(ESTG_INPUT, "EStG-150 input v2")
    e = _load_json(E_CONTRACT, "E v2 contract")
    result: dict[str, Any] = {
        "schema_version": "barrientos_de_dry_run@1.0.0",
        "mode": "dry_run_off_network",
        "llm_api_calls": 0,
        "network_calls": 0,
        "d_arms": {},
        "e_arms": {},
        "hashes": {
            "estg_input_v2": _sha256_file(ESTG_INPUT),
            "e_contract_v2": _sha256_file(E_CONTRACT),
            "registry": _sha256_file(D1_REGISTRY),
        },
    }
    for arm in D_ARMS:
        p = _prompt_for(arm)
        result["d_arms"][arm] = {
            "prompt": _rel(p), "prompt_sha256": _sha256_file(p),
            "samples": len(estg["records"]), "status": "dry_run_ok",
        }
    for arm in E_ARMS:
        p = _prompt_for(arm)
        result["e_arms"][arm] = {
            "prompt": _rel(p), "prompt_sha256": _sha256_file(p),
            "samples": e["input_surface"]["count"], "status": "dry_run_ok",
        }
    print("D/E dry-run OK (zero network, zero calls)")
    return result


def execute_de(auth_file: Path) -> dict[str, Any]:
    if auth_file is None or not auth_file.is_file():
        raise RuntimeError("real execution requires --auth-file (user authorization)")
    estg = _load_json(ESTG_INPUT, "EStG-150 input v2")
    e = _load_json(E_CONTRACT, "E v2 contract")

    from bpc_hybrid.llm_client import (
        LLMRequest,
        OpenAICompatibleRequestBuilder,
        RealAPITransport,
    )
    from bpc_hybrid.h1_transport import DEEPSEEK_V4_PRO_H1_POLICY
    from bpc_hybrid.d1_schema_adapter import adapt_relay_record
    from bpc_hybrid.d1_span_canonicalizer import canonicalize_record_coordinates
    from bpc_hybrid.llm_config import LLMConfig

    llm_config = LLMConfig.from_env(project_root=ROOT, load_project_env=False)
    if llm_config.provider == "mock" or not llm_config.enabled:
        raise RuntimeError("real provider not enabled (process env only)")

    started = time.time()
    results: dict[str, Any] = {
        "schema_version": "barrientos_de_execution@1.0.0",
        "mode": "real_execution",
        "arms": {},
        "total_calls": 0,
        "total_cost_usd": 0.0,
        "runtime_seconds": 0.0,
        "auth_file": str(auth_file),
    }

    def _call(sid: str, text: str, prompt_text: str) -> tuple[dict, float, dict]:
        body = OpenAICompatibleRequestBuilder({}).build_body(prompt_text,
                                                             _user_prompt(sid, text))
        body = DEEPSEEK_V4_PRO_H1_POLICY.apply_to_body(body)
        transport = RealAPITransport(llm_config, timeout_seconds=180.0)
        response = transport.send(LLMRequest(
            source_id=sid, source_text=text,
            system_prompt=prompt_text, user_prompt=_user_prompt(sid, text)))
        usage = (transport.last_decode or {}).get("usage") or {}
        cost = (float(usage.get("prompt_tokens", 0)) * 1.32
                + float(usage.get("completion_tokens", 0)) * 3.96) / 1e6
        return {"content": response.content, "decode": transport.last_decode},\
            cost, body

    def _pipe(arm: str, sid: str, text: str, prompt_text: str):
        raw, cost, _body = _call(sid, text, prompt_text)
        try:
            payload = json.loads(raw["content"].strip().strip("`"))
            if arm == "E-barrientos-faithful":
                return {"id": sid, "request_status": "ok",
                        "barrientos_record": payload}, cost
            adapter_payload, _ = adapt_relay_record(payload, text)
            canonical, _ = canonicalize_record_coordinates(adapter_payload, text)
            return {"id": sid, "request_status": "ok", "record": canonical}, cost
        except Exception as exc:
            return {"id": sid, "request_status": "failed", "error": str(exc)},\
                cost

    for arm in ("D-no-fewshot", "D-minimal", "D-barrientos-style"):
        arm_out = OUT_DIR / "D" / arm
        if arm_out.exists():
            raise RuntimeError(f"refusing to overwrite: {arm_out}")
        arm_out.mkdir(parents=True)
        prompt_path = _prompt_for(arm)
        prompt_text = prompt_path.read_text(encoding="utf-8")
        raw_rows, pipe_rows, failed = [], [], []
        cost = 0.0
        for rec in estg["records"]:
            raw, c, _ = _call(rec["sample_id"], rec["approved_text_en"],
                              prompt_text)
            cost += c
            raw_rows.append({**raw, "sample_id": rec["sample_id"]})
            row, c2 = _pipe(arm, rec["sample_id"], rec["approved_text_en"],
                            prompt_text)
            cost += c2
            pipe_rows.append(row)
            if row["request_status"] != "ok":
                failed.append(row)
        _write_arm(arm_out, arm, prompt_path, len(estg["records"]),
                   raw_rows, pipe_rows, failed, cost)
        results["total_calls"] += len(estg["records"])
        results["total_cost_usd"] += cost
        results["arms"][arm] = {"status": "executed",
                                "samples": len(estg["records"]),
                                "failed": len(failed),
                                "cost_usd": round(cost, 8)}
        print(f"[{arm}] {len(estg['records'])} calls, {len(failed)} failed")

    for arm in E_ARMS:
        arm_out = OUT_DIR / "E" / arm
        if arm_out.exists():
            raise RuntimeError(f"refusing to overwrite: {arm_out}")
        arm_out.mkdir(parents=True)
        prompt_path = _prompt_for(arm)
        prompt_text = prompt_path.read_text(encoding="utf-8")
        raw_rows, pipe_rows, failed = [], [], []
        cost = 0.0
        for item in e["input_surface"]["items"]:
            raw, c, _ = _call(item["id"], item["text"], prompt_text)
            cost += c
            raw_rows.append({**raw, "id": item["id"]})
            row, c2 = _pipe(arm, item["id"], item["text"], prompt_text)
            cost += c2
            pipe_rows.append(row)
            if row["request_status"] != "ok":
                failed.append(row)
        _write_arm(arm_out, arm, prompt_path, len(e["input_surface"]["items"]),
                   raw_rows, pipe_rows, failed, cost)
        results["total_calls"] += len(e["input_surface"]["items"])
        results["total_cost_usd"] += cost
        results["arms"][arm] = {"status": "executed",
                                "samples": len(e["input_surface"]["items"]),
                                "failed": len(failed),
                                "cost_usd": round(cost, 8)}
        print(f"[{arm}] {len(e['input_surface']['items'])} calls, "
              f"{len(failed)} failed")

    results["runtime_seconds"] = round(time.time() - started, 3)
    results["total_cost_usd"] = round(results["total_cost_usd"], 8)
    summary_path = OUT_DIR / "execution_summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2)
                            + "\n", encoding="utf-8")
    print(f"D/E real execution complete: {_rel(summary_path)}")
    return results


def _user_prompt(sid: str, text: str) -> str:
    return json.dumps({"sample_id": sid, "source_text": text},
                      ensure_ascii=False, indent=2)


def _write_arm(arm_out: Path, arm: str, prompt_path: Path, sample_count: int,
               raw_rows, pipe_rows, failed, cost: float) -> None:
    (arm_out / "raw_responses.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in raw_rows),
        encoding="utf-8")
    (arm_out / "canonical_predictions.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in pipe_rows),
        encoding="utf-8")
    (arm_out / "failed_samples.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in failed),
        encoding="utf-8")
    (arm_out / "manifest.json").write_text(json.dumps({
        "run_id": arm, "prompt_sha256": _sha256_file(prompt_path),
        "sample_count": sample_count, "failed_count": len(failed),
        "cost_usd": round(cost, 8),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute-de", action="store_true")
    parser.add_argument("--auth-file", type=Path, default=None)
    args = parser.parse_args()
    try:
        if args.execute_de:
            result = execute_de(args.auth_file)
        elif args.dry_run:
            result = dry_run()
        elif args.suite:
            return run_suite()
        else:
            parser.error("choose --suite, --dry-run or --execute-de")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:1500])
        return 0
    except RuntimeError as exc:
        print(f"refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())