# -*- coding: utf-8 -*-
"""Sun-style Stage 3 threshold sensitivity (S3.5 evidence extension, DEV_ONLY).

Offline, zero-API re-analysis that follows Sun et al. (2024) Section 5.3 /
Figure 8 / Figure 9 as a DISCRETE threshold grid over the FROZEN Stage 3
development evidence:

- tau in {0.0, 0.2, 0.4, 0.6, 0.8, 0.9} - matching only. Every matching score
  is recomputed from Definition 4 (SunScorer with that tau) and re-ranked;
  per-process AP and MAP are reported. Matching AP/MAP is NEVER mixed into
  violation F1.
- gamma in {0.0, 0.2, 0.4, 0.6, 0.8, 0.9} - real SunScorer re-execution
  (action mappings, actor denominators, order endpoints and observability
  all change with gamma), theta fixed at its primary 0.8.
- theta (vartheta) in {0.5, 0.6, 0.7, 0.8, 0.9} with gamma FIXED at 0.8,
  exactly like Sun Figure 9.

Everything is recomputed through the frozen scorer and the frozen common
evaluator (scripts/evaluate_stage3_common.py - the only Gold-reading
component). No Gold, sample, prediction label or evaluation formula is
changed; the original gamma=0.8 run (outputs/evidence/s35_sun_stage3_
development_v2) is byte-untouched and is used as a verification anchor: the
sweep fails closed unless the recomputed primary row and every overlapping
sensitivity row match the recorded evidence exactly.

Artifacts (all DEV_ONLY):
- sweep JSON   : outputs/development/s35_sun_stage3_threshold_sensitivity_v1/sweep.json
- report JSON  : outputs/reports/s35_sun_stage3_threshold_sensitivity_v1.json
- report MD    : outputs/reports/s35_sun_stage3_threshold_sensitivity_v1.md
- figure A     : outputs/reports/s35_sun_stage3_threshold_sensitivity_v1_figA_gamma_missing_action_out_of_order.svg
- figure B     : outputs/reports/s35_sun_stage3_threshold_sensitivity_v1_figB_theta_incorrect_actor.svg

Usage:
    python scripts/build_sun_stage3_threshold_sensitivity_v1.py            # full offline compute + write all artifacts
    python scripts/build_sun_stage3_threshold_sensitivity_v1.py --report-only   # deterministic report/figures replay from the sweep JSON
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for _candidate in (SRC, SCRIPTS):
    if str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

# --------------------------------------------------------------------------
# frozen inputs (byte-locked in the S3.5 v2 manifest; read-only here)
# --------------------------------------------------------------------------
EVIDENCE_RUN = ROOT / "outputs" / "evidence" / "s35_sun_stage3_development_v2"
DEV_RUN = ROOT / "outputs" / "development" / "s35_sun_stage3_development_v2"
CONFIG = ROOT / "configs" / "sun_stage3_development_v1.json"
MEMBERSHIP_CONTRACT = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
STAGE1_CONTRACT = ROOT / "configs" / "stage1_structural_s11_s14.json"
BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"
BLANK_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_blank_v1.json"
INFERENCE_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_inference_v1.json"
CORRECTION_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"
GOLD_MATCHING = ROOT / "data" / "gold" / "stage3" / "stage3_matching_gold_v1.json"
GOLD_VIOLATION = ROOT / "data" / "gold" / "stage3" / "stage3_violation_gold_v1.json"
WINTER_FILES_DIR = ROOT.parent / "references" / "winter_2020_model_check" / "model_check" / "input" / "files"

SWEEP_DIR = ROOT / "outputs" / "development" / "s35_sun_stage3_threshold_sensitivity_v1"
SWEEP_JSON = SWEEP_DIR / "sweep.json"
REPORT_JSON = ROOT / "outputs" / "reports" / "s35_sun_stage3_threshold_sensitivity_v1.json"
REPORT_MD = ROOT / "outputs" / "reports" / "s35_sun_stage3_threshold_sensitivity_v1.md"
FIG_A = ROOT / "outputs" / "reports" / "s35_sun_stage3_threshold_sensitivity_v1_figA_gamma_missing_action_out_of_order.svg"
FIG_B = ROOT / "outputs" / "reports" / "s35_sun_stage3_threshold_sensitivity_v1_figB_theta_incorrect_actor.svg"

# --- Sun-aligned discrete grids (Sun 2024 Table 9 columns for tau/gamma;
#     Figure 9's actor-threshold range for theta at gamma fixed = 0.8) -------
MATCHING_TAU_GRID = [0.0, 0.2, 0.4, 0.6, 0.8, 0.9]
GAMMA_GRID = [0.0, 0.2, 0.4, 0.6, 0.8, 0.9]
THETA_GRID = [0.5, 0.6, 0.7, 0.8, 0.9]  # vartheta; evaluated with gamma = 0.8

PRIMARY = {"tau": 0.8, "gamma": 0.8, "theta": 0.8}  # pre-registered transfer values
CALIBRATED = {"tau": 0.8, "gamma": 0.6, "theta": 0.8}  # best observed setting ON THE TESTED GRID

TYPES = ["missing_action", "incorrect_actor", "out_of_order"]
PROCESS_SHORT = {
    "gdpr_1_data_breach": "P1",
    "gdpr_2_consent_to_use_the_data": "P2",
    "gdpr_3_right_to_access": "P3",
    "gdpr_4_right_of_portability": "P4",
    "gdpr_5_right_to_withdraw": "P5",
    "gdpr_6_right_to_rectify": "P6",
    "gdpr_7_right_to_be_forgotten": "P7",
}

SCHEMA = "s35_sun_stage3_threshold_sensitivity@1.0.0"
REPORT_SCHEMA = "s35_sun_stage3_threshold_sensitivity_report@1.0.0"

warnings.filterwarnings("ignore", message=".*no word vectors.*")


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} root must be an object: {path}")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def p_r_f1(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def _git_state() -> dict[str, str]:
    import subprocess
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        return {"commit": commit, "dirty_paths": dirty.splitlines()[:20]}
    except Exception:  # pragma: no cover - offline fallback
        return {"commit": "unknown", "dirty_paths": []}


# --------------------------------------------------------------------------
# runtime environment (models, similarity, cached Rule Records)
# --------------------------------------------------------------------------
def build_runtime(use_cached_rules: bool = True):
    """Load spaCy, the frozen GDPR-7 models and the Rule Records.

    Rule Records are taken from the S3.5 run's cache when available and are
    otherwise re-extracted deterministically from the gold-blind inference
    pack (identical adapter, identical output - the runner's double-run
    byte-identity tests lock this).
    """
    import spacy
    from bpc_hybrid.sun_stage3.sun_model import build_sun_models
    from bpc_hybrid.sun_stage3.sun_rule_extraction import extract_rule_record
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity

    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    models = build_sun_models(BPMN_DIR, STAGE1_CONTRACT, nlp)
    signalwords = set(
        (WINTER_FILES_DIR / "signalwords.txt").read_text(encoding="utf-8").splitlines())

    cached_path = DEV_RUN / "rule_records.jsonl"
    rules: dict[str, dict[str, Any]] = {}
    source = "fresh_extraction"
    if use_cached_rules and cached_path.exists():
        for line in cached_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                rules[record["rule_id"]] = record
        source = "cached_run_rule_records"
    if not rules:
        inference = load_json(INFERENCE_PACK, "inference pack")
        seen: set[str] = set()
        for item in list(inference["matching_items"]) + list(inference["violation_items"]):
            if item["rule_id"] in seen:
                continue
            seen.add(item["rule_id"])
            rules[item["rule_id"]] = extract_rule_record(
                item["rule_id"], item["rule_text"], nlp, signalwords)
    return {"nlp": nlp, "sim": sim, "models": models, "rules": rules,
            "rule_source": source}


# --------------------------------------------------------------------------
# matching: Definition-4 score recomputation and per-tau AP/MAP
# --------------------------------------------------------------------------
def matching_scores_per_tau(runtime: dict[str, Any], tau: float) -> list[dict[str, Any]]:
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer
    inference = load_json(INFERENCE_PACK, "inference pack")
    scorer = SunScorer(runtime["sim"], tau, PRIMARY["gamma"], PRIMARY["theta"],
                       nlp=runtime["nlp"])
    rows = []
    for item in sorted(inference["matching_items"], key=lambda i: i["item_id"]):
        record = runtime["rules"][item["rule_id"]]
        model = runtime["models"][item["process_id"]]
        m = scorer.matching_score(record["actions"], record["actors"], model)
        rows.append({
            "item_id": item["item_id"],
            "process_id": item["process_id"],
            "rule_id": item["rule_id"],
            "matching_score": round(m["matching_score"], 6),
            "action_ratio": round(m["action_ratio"], 6),
            "actor_object_ratio": round(m["actor_object_ratio"], 6),
        })
    return rows


def ap_map_from_scores(scores: list[dict[str, Any]],
                       correction: dict[str, Any]) -> dict[str, Any]:
    """Ranking AP per process and MAP (identical logic to the common
    evaluator's evaluate_matching; relevance = frozen decision_relevant)."""
    gold_m = {i["item_id"]: i for i in correction["matching_items"]}
    by_process: dict[str, list[tuple[float, bool]]] = {}
    for row in scores:
        by_process.setdefault(row["process_id"], []).append(
            (float(row["matching_score"]), bool(gold_m[row["item_id"]]["decision_relevant"])))
    aps: dict[str, float] = {}
    for pid, items in sorted(by_process.items()):
        ranked = sorted(items, key=lambda x: x[0], reverse=True)
        hits = 0
        precisions = []
        for rank, (_, rel) in enumerate(ranked, start=1):
            if rel:
                hits += 1
                precisions.append(hits / rank)
        aps[pid] = round(statistics.mean(precisions) if precisions else 0.0, 4)
    return {"per_process_ap": aps,
            "MAP": round(statistics.mean(aps.values()), 4) if aps else None}


# --------------------------------------------------------------------------
# violation: real SunScorer re-execution per (gamma, theta)
# --------------------------------------------------------------------------
def rebuild_violation_predictions(runtime: dict[str, Any], gamma: float,
                                  theta: float) -> list[dict[str, Any]]:
    """Re-executes Definitions 5-7 with a fresh SunScorer. Mirrors the S3.5
    runner/sensitivity rebuild exactly (mappings, actor sets, order endpoints
    and observability flags all come from the scorer at this gamma/theta)."""
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer
    inference = load_json(INFERENCE_PACK, "inference pack")
    scorer = SunScorer(runtime["sim"], PRIMARY["tau"], gamma, theta, nlp=runtime["nlp"])
    out = []
    for item in sorted(inference["violation_items"], key=lambda i: i["item_id"]):
        record = runtime["rules"][item["rule_id"]]
        model = runtime["models"][item["process_id"]]
        ma = scorer.missing_action(record["actions"], model)
        ia = scorer.incorrect_actor(record["actions"], record["actors"], model)
        oo = scorer.out_of_order(record["order_relations"], record["actions"], model)
        scores = {"missing_action": ma["score"], "incorrect_actor": ia["score"],
                  "out_of_order": oo["score"]}
        item_score = scores[item["check_type"]]
        predicted = item["check_type"] if (item_score is not None and item_score > 0.0) else None
        out.append({
            "schema_version": "stage3_prediction@1.0.0",
            "method_id": "sun_2024",
            "run_id": "threshold_sensitivity_sun_style",
            "task": "violation",
            "item_id": item["item_id"],
            "process_id": item["process_id"],
            "rule_id": item["rule_id"],
            "predicted_violation_type": predicted,
            "incorrect_actor_observable": ia["observable"],
            "incorrect_actor_reason": ia.get("reason"),
            "check_type": item["check_type"],
            "threshold": gamma,
        })
    return out


def confusion_rows(preds: list[dict[str, Any]], correction: dict[str, Any]) -> dict[str, Any]:
    """Per-item breakdown under the common evaluator's documented policy
    (gold type from correction; unobservable applies only to incorrect_actor
    check points and counts as FN in the conservative denominators)."""
    gold_v = {i["item_id"]: i for i in correction["violation_items"]}
    per_type: dict[str, dict[str, int]] = {t: {"tp": 0, "fp": 0, "fn": 0} for t in TYPES}
    unobservable_by_reason: dict[str, int] = {}
    detected = missed = wrong_type = 0
    rows: dict[str, dict[str, Any]] = {}
    for p in preds:
        ct = p.get("check_type")
        g = gold_v[p["item_id"]]["decision_violation_type"]
        pred = p.get("predicted_violation_type")
        is_unobservable = (ct == "incorrect_actor"
                           and p.get("incorrect_actor_observable") is False)
        if is_unobservable:
            reason = p.get("incorrect_actor_reason") or "unspecified"
            unobservable_by_reason[reason] = unobservable_by_reason.get(reason, 0) + 1
        if pred == g:
            detected += 1
            per_type[g]["tp"] += 1
        elif g is None:
            per_type.setdefault("none", {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1
        else:
            missed += 1
            per_type[g]["fn"] += 1
            if pred is not None:
                wrong_type += 1
                per_type.setdefault(pred, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1
        rows[p["item_id"]] = {
            "process_id": p["process_id"],
            "check_type": ct,
            "gold_type": g,
            "predicted_type": pred,
            "unobservable": is_unobservable,
            "hit": pred == g,
        }
    per_type_results: dict[str, Any] = {}
    for t in TYPES:
        conf = per_type.get(t, {"tp": 0, "fp": 0, "fn": 0})
        per_type_results[t] = {
            "support": conf["tp"] + conf["fn"],
            "tp": conf["tp"], "fp": conf["fp"], "fn": conf["fn"],
            **p_r_f1(conf["tp"], conf["fp"], conf["fn"]),
        }
    total_tp = sum(per_type[t]["tp"] for t in TYPES)
    total_fp = sum(per_type[t]["fp"] for t in TYPES)
    total_fn = sum(per_type[t]["fn"] for t in TYPES)
    macro_f1 = round(statistics.mean([per_type_results[t]["f1"] for t in TYPES]), 4)
    micro = p_r_f1(total_tp, total_fp, total_fn)
    return {
        "per_item": rows,
        "per_type": per_type_results,
        "confusion_total": {"tp": total_tp, "fp": total_fp, "fn": total_fn},
        "macro_f1": macro_f1,
        "micro_f1": micro["f1"],
        "micro_prf": micro,
        "detected": detected,
        "missed": missed,
        "wrong_type": wrong_type,
        "exact_type_accuracy": round(detected / len(preds), 4) if preds else 0.0,
        "unobservable": sum(unobservable_by_reason.values()),
        "unobservable_by_reason": unobservable_by_reason,
        "support": len(preds),
    }


def per_process_breakdown(preds: list[dict[str, Any]],
                          correction: dict[str, Any]) -> dict[str, Any]:
    """Same conventions restricted per process, plus the two pools used by
    Sun Figure 8 (missing_action + out_of_order together) and Sun Figure 9
    (incorrect_actor alone)."""
    agg = confusion_rows(preds, correction)
    per_item = agg["per_item"]
    by_process: dict[str, list[str]] = {}
    for item_id, row in per_item.items():
        by_process.setdefault(row["process_id"], []).append(item_id)
    result: dict[str, Any] = {}
    for pid in sorted(by_process):
        conf: dict[str, dict[str, int]] = {t: {"tp": 0, "fp": 0, "fn": 0} for t in TYPES}
        detected = 0
        unobs = 0
        for item_id in sorted(by_process[pid]):
            row = per_item[item_id]
            if row["unobservable"]:
                unobs += 1
            if row["hit"]:
                detected += 1
            if row["gold_type"] in TYPES:
                conf[row["gold_type"]]["tp" if row["hit"] else "fn"] += 1
        per_type = {}
        for t in TYPES:
            per_type[t] = {"support": conf[t]["tp"] + conf[t]["fn"],
                           **p_r_f1(conf[t]["tp"], conf[t]["fp"], conf[t]["fn"])}
        macro = round(statistics.mean([per_type[t]["f1"] for t in TYPES]), 4)
        tp_sum = sum(conf[t]["tp"] for t in TYPES)
        fp_sum = sum(conf[t]["fp"] for t in TYPES)
        fn_sum = sum(conf[t]["fn"] for t in TYPES)
        pool_ma_oo = p_r_f1(conf["missing_action"]["tp"] + conf["out_of_order"]["tp"],
                            conf["missing_action"]["fp"] + conf["out_of_order"]["fp"],
                            conf["missing_action"]["fn"] + conf["out_of_order"]["fn"])
        pool_ia = p_r_f1(conf["incorrect_actor"]["tp"], conf["incorrect_actor"]["fp"],
                         conf["incorrect_actor"]["fn"])
        support = len(by_process[pid])
        result[pid] = {
            "support": support,
            "detected": detected,
            "exact_type_accuracy": round(detected / support, 4) if support else 0.0,
            "macro_f1": macro,
            "micro_f1": p_r_f1(tp_sum, fp_sum, fn_sum)["f1"],
            "unobservable": unobs,
            "per_type": per_type,
            "pool_missing_action_out_of_order": pool_ma_oo,
            "pool_incorrect_actor": pool_ia,
        }
    # aggregates (sanity cross-check with the row evaluation)
    result["_aggregate"] = {
        "detected": agg["detected"], "support": agg["support"],
        "unobservable": agg["unobservable"],
        "exact_type_accuracy": agg["exact_type_accuracy"],
        "macro_f1": agg["macro_f1"], "micro_f1": agg["micro_f1"],
        "per_type": {t: {k: v for k, v in vv.items() if k != "tp" and k != "fp" and k != "fn"}
                     for t, vv in agg["per_type"].items()},
    }
    return result


def evaluate_row(preds: list[dict[str, Any]], correction: dict[str, Any],
                 label: str) -> dict[str, Any]:
    """Row metrics through the FROZEN common evaluator (the sanctioned
    Gold-reading component), augmented with the evaluator-consistent
    per-process breakdown and the measured wall time of this row."""
    from evaluate_stage3_common import evaluate
    started = time.perf_counter()
    ev = evaluate(preds, correction)["violation"]
    breakdown = per_process_breakdown(preds, correction)
    elapsed = round(time.perf_counter() - started, 3)
    row = {
        "label": label,
        "macro_f1": ev["macro_f1"],
        "micro_f1": ev["micro_f1"],
        "exact_type_accuracy": ev["exact_type_accuracy"],
        "detected": ev["detected"],
        "missed": ev["missed"],
        "wrong_type": ev["wrong_type"],
        "unobservable": ev["unobservable"],
        "per_type": ev["per_type"],
        "observable_only_per_type": ev["observable_only_per_type"],
        "denominator": ev["denominator"],
        "per_process": breakdown,
        "runtime_seconds": elapsed,
    }
    return row


# --------------------------------------------------------------------------
# verification against the byte-untouched S3.5 evidence
# --------------------------------------------------------------------------
def _row_metrics_for_compare(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "macro_f1": row["macro_f1"],
        "exact_type_accuracy": row["exact_type_accuracy"],
        "unobservable": row["unobservable"],
        "per_type_f1": {t: v["f1"] for t, v in row["per_type"].items()},
    }


def verify_against_evidence(sweep: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed check: the recomputed primary row and every overlapping
    sweep row must equal the recorded S3.5 evidence exactly."""
    evaluation = load_json(EVIDENCE_RUN / "evaluation.json", "evidence evaluation")
    sensitivity = load_json(EVIDENCE_RUN / "threshold_sensitivity.json",
                            "evidence sensitivity")
    expected_primary = _row_metrics_for_compare({
        "macro_f1": evaluation["violation"]["macro_f1"],
        "exact_type_accuracy": evaluation["violation"]["exact_type_accuracy"],
        "unobservable": evaluation["violation"]["unobservable"],
        "per_type": evaluation["violation"]["per_type"],
    })
    issues: list[str] = []
    primary_ok = False

    primary_row = sweep["settings"]["sun_transferred"]["violation_row"]
    got = _row_metrics_for_compare(primary_row)
    if got == expected_primary:
        primary_ok = True
    else:
        issues.append(f"primary (0.8,0.8) row differs from evidence evaluation.json: "
                      f"expected={expected_primary} computed={got}")

    gamma_overlap = {0.2: None, 0.4: None, 0.6: None, 0.8: None, 0.9: None}
    for row in sweep["gamma_sweep"]:
        if row["gamma"] in gamma_overlap:
            gamma_overlap[row["gamma"]] = row
    overlap_issues: list[str] = []
    for old in sensitivity["violation_gamma_sweep"]:
        g = old["gamma"]
        if g not in gamma_overlap or gamma_overlap[g] is None:
            overlap_issues.append(f"evidence gamma sweep row gamma={g} missing in recompute")
            continue
        exp = {"macro_f1": old["macro_f1"], "exact_type_accuracy": old["exact_type_accuracy"],
               "unobservable": old["unobservable"],
               "per_type_f1": {t: v["f1"] for t, v in old["per_type"].items()}}
        got = _row_metrics_for_compare(gamma_overlap[g])
        if got != exp:
            overlap_issues.append(f"gamma={g} row differs from evidence: expected={exp} got={got}")

    theta_overlap = {0.6: None, 0.7: None, 0.8: None, 0.9: None}
    for row in sweep["theta_sweep"]:
        if row["theta"] in theta_overlap:
            theta_overlap[row["theta"]] = row
    for old in sensitivity["incorrect_actor_theta_sweep"]:
        t = old["theta"]
        if t not in theta_overlap or theta_overlap[t] is None:
            continue  # 0.2/0.4 rows of the old diagnostic are outside the Sun grid
        exp = {"macro_f1": old["macro_f1"], "exact_type_accuracy": old["exact_type_accuracy"],
               "unobservable": old["unobservable"],
               "per_type_f1": {ty: v["f1"] for ty, v in old["per_type"].items()}}
        got = _row_metrics_for_compare(theta_overlap[t])
        if got != exp:
            overlap_issues.append(f"theta={t} row differs from evidence: expected={exp} got={got}")

    return {"evidence_evaluation_json": str(EVIDENCE_RUN / "evaluation.json"),
            "evidence_threshold_sensitivity_json": str(EVIDENCE_RUN / "threshold_sensitivity.json"),
            "primary_row_matches_evaluation_json": primary_ok,
            "overlap_rows_all_match": not overlap_issues,
            "issues": issues + overlap_issues}


# --------------------------------------------------------------------------
# scorer mechanism diagnostics (measured, not inferred)
# --------------------------------------------------------------------------
def scorer_diagnostics(runtime: dict[str, Any],
                       params: dict[str, float]) -> dict[str, dict[str, Any]]:
    """Per-item scorer detail for one (tau,gamma,theta) setting: order-check
    denominators, incorrect-actor observability reason and the observed min
    actor similarity, missing-action denominator/missing count. Used only to
    describe WHY a row looks the way it does (no metric change)."""
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer
    inference = load_json(INFERENCE_PACK, "inference pack")
    scorer = SunScorer(runtime["sim"], params["tau"], params["gamma"],
                       params["theta"], nlp=runtime["nlp"])
    out: dict[str, dict[str, Any]] = {}
    for item in sorted(inference["violation_items"], key=lambda i: i["item_id"]):
        record = runtime["rules"][item["rule_id"]]
        model = runtime["models"][item["process_id"]]
        detail: dict[str, Any] = {"check_type": item["check_type"]}
        if item["check_type"] == "out_of_order":
            oo = scorer.out_of_order(record["order_relations"], record["actions"], model)
            detail.update({"oo_denominator": oo["denominator"],
                           "oo_violations": oo["violations"],
                           "oo_satisfied": oo["satisfied"]})
        elif item["check_type"] == "incorrect_actor":
            ia = scorer.incorrect_actor(record["actions"], record["actors"], model)
            detail.update({"ia_observable": ia["observable"],
                           "ia_reason": ia.get("reason")})
            if ia["observable"]:
                detail["ia_min_actor_sim"] = round(min(
                    d["min_process_actor_similarity"] for d in ia["details"]), 4)
        else:
            ma = scorer.missing_action(record["actions"], model)
            detail.update({"ma_denominator": ma["denominator"],
                           "ma_missing": ma["missing"]})
        out[item["item_id"]] = detail
    return out


# --------------------------------------------------------------------------
# full sweep
# --------------------------------------------------------------------------
def run_sweep(runtime: dict[str, Any],
              correction: dict[str, Any]) -> dict[str, Any]:
    sweep: dict[str, Any] = {}

    # --- matching tau grid: recomputed Def-4 scores, AP/MAP only ----------
    tau_rows = []
    for tau in MATCHING_TAU_GRID:
        started = time.perf_counter()
        scores = matching_scores_per_tau(runtime, tau)
        ap = ap_map_from_scores(scores, correction)
        tau_rows.append({
            "tau": tau,
            "per_process_ap": ap["per_process_ap"],
            "MAP": ap["MAP"],
            "support": len(scores),
            "runtime_seconds": round(time.perf_counter() - started, 3),
        })
    sweep["matching_tau_sweep"] = tau_rows

    # --- gamma sweep: theta fixed at primary 0.8 --------------------------
    gamma_rows = []
    for gamma in GAMMA_GRID:
        row_started = time.perf_counter()
        preds = rebuild_violation_predictions(runtime, gamma, PRIMARY["theta"])
        row = {"gamma": gamma, **evaluate_row(preds, correction, f"gamma={gamma}")}
        row["runtime_seconds"] = round(time.perf_counter() - row_started, 3)
        if gamma == PRIMARY["gamma"]:
            row["evidence_prediction_match"] = preds_match_evidence(preds)
        gamma_rows.append(row)
    sweep["gamma_sweep"] = gamma_rows

    # --- theta sweep: gamma fixed at 0.8 (Sun Figure 9) --------------------
    theta_rows = []
    for theta in THETA_GRID:
        row_started = time.perf_counter()
        preds = rebuild_violation_predictions(runtime, PRIMARY["gamma"], theta)
        row = evaluate_row(preds, correction, f"theta={theta}")
        row["runtime_seconds"] = round(time.perf_counter() - row_started, 3)
        theta_rows.append({"theta": theta, **row})
    sweep["theta_sweep"] = theta_rows

    # --- two reported settings ---------------------------------------------
    def setting(name: str, params: dict[str, float]) -> dict[str, Any]:
        row_started = time.perf_counter()
        preds = rebuild_violation_predictions(runtime, params["gamma"], params["theta"])
        row = evaluate_row(preds, correction, name)
        row["runtime_seconds"] = round(time.perf_counter() - row_started, 3)
        matching = ap_map_from_scores(
            matching_scores_per_tau(runtime, params["tau"]), correction)
        return {"setting": name, "tau": params["tau"], "gamma": params["gamma"],
                "theta": params["theta"], "violation_row": row,
                "matching_MAP": matching["MAP"],
                "matching_per_process_ap": matching["per_process_ap"]}

    sweep["settings"] = {
        "sun_transferred": setting("sun_transferred", PRIMARY),
        "sun_style_calibrated": setting("sun_style_calibrated", CALIBRATED),
    }
    sweep["scorer_diagnostics"] = {
        "sun_transferred": scorer_diagnostics(runtime, PRIMARY),
        "sun_style_calibrated": scorer_diagnostics(runtime, CALIBRATED),
    }
    return sweep


def preds_match_evidence(preds: list[dict[str, Any]]) -> bool:
    """Byte-level label check against the recorded S3.5 run predictions for
    the primary gamma=0.8 row (extra anchor for the transferred setting)."""
    try:
        recorded = [json.loads(line) for line in
                    (EVIDENCE_RUN / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()]
        recorded_v = {p["item_id"]: p for p in recorded if p["task"] == "violation"}
    except OSError:
        return False
    for p in preds:
        rp = recorded_v.get(p["item_id"])
        if rp is None or rp["predicted_violation_type"] != p["predicted_violation_type"] \
                or rp.get("incorrect_actor_observable") != p["incorrect_actor_observable"]:
            return False
    return True


# --------------------------------------------------------------------------
# report JSON assembly
# --------------------------------------------------------------------------
def input_bindings() -> dict[str, Any]:
    membership = load_json(MEMBERSHIP_CONTRACT, "membership contract")
    return {
        "bpmn_dir": str(BPMN_DIR.relative_to(ROOT).as_posix()),
        "bpmn_dir_aggregate_sha256": _dir_aggregate_sha256(BPMN_DIR),
        "membership_payload_sha256": membership["membership"]["membership_payload_sha256"],
        "blank_pack": {"path": str(BLANK_PACK.relative_to(ROOT).as_posix()),
                       "sha256": sha256_file(BLANK_PACK)},
        "inference_pack": {"path": str(INFERENCE_PACK.relative_to(ROOT).as_posix()),
                           "sha256": sha256_file(INFERENCE_PACK)},
        "correction_pack": {"path": str(CORRECTION_PACK.relative_to(ROOT).as_posix()),
                            "sha256": sha256_file(CORRECTION_PACK)},
        "gold_matching": {"path": str(GOLD_MATCHING.relative_to(ROOT).as_posix()),
                          "sha256": sha256_file(GOLD_MATCHING)},
        "gold_violation": {"path": str(GOLD_VIOLATION.relative_to(ROOT).as_posix()),
                           "sha256": sha256_file(GOLD_VIOLATION)},
        "evidence_run_predictions": {"path": str((EVIDENCE_RUN / "predictions.jsonl").relative_to(ROOT).as_posix()),
                                     "sha256": sha256_file(EVIDENCE_RUN / "predictions.jsonl")},
        "evidence_run_manifest": {"path": str((EVIDENCE_RUN / "manifest.json").relative_to(ROOT).as_posix()),
                                  "sha256": sha256_file(EVIDENCE_RUN / "manifest.json")},
        "source_rule_records": {"path": str((DEV_RUN / "rule_records.jsonl").relative_to(ROOT).as_posix()),
                                "sha256": sha256_file(DEV_RUN / "rule_records.jsonl")
                                if (DEV_RUN / "rule_records.jsonl").exists() else None},
        "config": {"path": str(CONFIG.relative_to(ROOT).as_posix()),
                   "sha256": sha256_file(CONFIG)},
        "common_evaluator": {"path": "scripts/evaluate_stage3_common.py",
                             "sha256": sha256_file(SCRIPTS / "evaluate_stage3_common.py")},
        "sun_scorer": {"path": "src/bpc_hybrid/sun_stage3/sun_scorer.py",
                       "sha256": sha256_file(SRC / "bpc_hybrid" / "sun_stage3" / "sun_scorer.py")},
    }


def _dir_aggregate_sha256(directory: Path) -> str:
    entries = {str(p.relative_to(directory).as_posix()): sha256_file(p)
               for p in sorted(directory.glob("*.bpmn"))}
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


SUN_SOURCE_FACTS = [
    ("tau_role", "tau is the rule-process matching threshold of Sun Definition 4: "
     "matching(r,m,tau) = max( fraction of rule-action pairs with sim>tau, "
     "fraction of rule-actor/object pairs with sim>tau ); tau in [0,1] limits the "
     "required degree of similarity (Sun 2024 Def. 4)."),
    ("gamma_role", "gamma is the action-similarity threshold: two semantic components "
     "count as equivalent when sim > gamma (Sun 2024 Def. 4 preamble). It drives "
     "Definition 5 (missing action: rule actions whose best model-action similarity "
     "is below gamma), Definition 6's observability/mapping branch (R and C sets are "
     "built only from action mappings with sim > gamma) and Definition 7's endpoint "
     "mapping (Ur,m,gamma keeps order constraints whose BOTH endpoints map with "
     "sim > gamma)."),
    ("theta_role", "theta/vartheta is the actor-similarity threshold of Definition 6: "
     "a rule actor r in R is violated iff there EXISTS a process actor/object r' in C "
     "with sim(r,r') < theta."),
    ("tau_map_peak", "On Sun's own data the overall MAP is highest at tau=0.8 in BOTH "
     "matching datasets: Table 9 (12 smart-meter process models of the energy-supplier "
     "scenario) reaches MAP 0.801 at tau=0.8 (9 of 12 models best at 0.8, 3 best at "
     "0.6) and Table 11 (four GDPR BPMN models) reaches MAP 0.840 at tau=0.8 "
     "(4 of 4 models best at 0.8)."),
    ("fig8_gamma", "Sun Figure 8 reports the violation-detection PRECISION of each "
     "model at different gamma values for the two gamma-only categories analysed "
     "together (missing action and out-of-order execution). Most models reach their "
     "highest precision at gamma=0.8, while Model 4 - the most complex model - is "
     "highest at gamma=0.6; precision at gamma=0.9 is below gamma=0.8."),
    ("fig9_theta", "Sun Figure 9 fixes gamma=0.8 (the value that was best for the "
     "first two violation categories) and reports each model's incorrect-actor "
     "precision against theta. Two of the four models are best at theta=0.8 and the "
     "other two (larger models with more content) are best at theta=0.7."),
    ("sun_explanation", "Sun's own explanation: in complex/larger process models the "
     "text similarity of matched components tends to DECREASE, so a lower threshold "
     "can fit better; raising the threshold (e.g., gamma=0.9) makes the check stricter "
     "and can flag normal operations as violations, which lowers precision."),
    ("wording_guard", "0.8 is the empirical value at which MOST models performed best "
     "ON SUN'S DATA - it is NOT a universal rule that all models must use 0.8, and it "
     "is not a number fixed by the Sun definitions."),
]


def assemble_report(sweep: dict[str, Any], runtime_info: dict[str, Any],
                     elapsed_total: float) -> dict[str, Any]:
    verification = verify_against_evidence(sweep)
    cfg = load_json(CONFIG, "sun config")
    report = {
        "schema_version": REPORT_SCHEMA,
        "title": "Stage 3 Sun-style threshold sensitivity (DEV_ONLY, zero API)",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git": _git_state(),
        "claim_boundary": (
            "Development-only method-level threshold-sensitivity analysis of the S3.5 "
            "Sun Definitions 4-7 reconstruction. NOT a formal result, NOT a "
            "pre-registered primary evaluation, NOT Sun's original code/data, and NOT "
            "held-out model selection. Primary thresholds stay pre-registered "
            "tau=gamma=theta=0.8 (configs/sun_stage3_development_v1.json); the "
            "calibrated setting is only the BEST OBSERVED value among the tested "
            "grid points on THIS project's data and THIS similarity backend."),
        "method": cfg["method"],
        "threshold_grids": {
            "matching_tau": MATCHING_TAU_GRID,
            "gamma": GAMMA_GRID,
            "theta_fixed_gamma_0_8": THETA_GRID,
            "design": "tau is evaluated with matching AP/MAP only (never mixed into "
                      "violation F1); gamma re-executes the SunScorer (mappings, actor "
                      "denominators, order endpoints and observability change); theta "
                      "is evaluated with gamma FIXED at 0.8 exactly like Sun Figure 9.",
        },
        "sun_source_facts": SUN_SOURCE_FACTS,
        "settings": {
            "sun_transferred": {
                "thresholds": PRIMARY,
                "role": "direct transfer of the empirical value that was best for most "
                        "models on Sun's data; kept as the method-level comparison "
                        "baseline (Table A of the paper uses this row).",
                "matching_MAP": sweep["settings"]["sun_transferred"]["matching_MAP"],
                "matching_per_process_ap": sweep["settings"]["sun_transferred"]["matching_per_process_ap"],
                "violation": _compact_row(sweep["settings"]["sun_transferred"]["violation_row"]),
            },
            "sun_style_calibrated": {
                "thresholds": CALIBRATED,
                "role": "Sun-style sensitivity result: the BEST OBSERVED setting among "
                        "the tested grid values on this data/backend. It is NOT a "
                        "mathematically optimal threshold, NOT a Sun-paper-fixed "
                        "threshold, NOT an optimum found on an independent held-out "
                        "test, and NOT the same numbers as Sun's four original models.",
                "matching_MAP": sweep["settings"]["sun_style_calibrated"]["matching_MAP"],
                "matching_per_process_ap": sweep["settings"]["sun_style_calibrated"]["matching_per_process_ap"],
                "violation": _compact_row(sweep["settings"]["sun_style_calibrated"]["violation_row"]),
            },
        },
        "matching_tau_sweep": sweep["matching_tau_sweep"],
        "gamma_sweep": [_compact_row({**row, "gamma": row["gamma"]}) for row in sweep["gamma_sweep"]],
        "theta_sweep": [_compact_row({**row, "theta": row["theta"]}) for row in sweep["theta_sweep"]],
        "violation_gamma_row_verification": {
            "note": "per-row exact recompute checks: macro/micro/exact/unobservable, "
                    "per-type P/R/F1, per-process detail and scorer runtime.",
        },
        "scorer_diagnostics": sweep["scorer_diagnostics"],
        "verification": verification,
        "input_bindings": input_bindings(),
        "rule_record_source": runtime_info["rule_source"],
        "runtime": {
            "total_wall_seconds": round(elapsed_total, 2),
            "per_row_seconds_measured": True,
            "similarity_backend": "spaCy en_core_web_sm (same frozen backend as the "
                                  "S3.4/S3.5 runs; no word vectors - spaCy W007, "
                                  "similarity comes from tagger/parser/NER tensors)",
        },
        "safety": {
            "llm_api_called": False,
            "api_calls": 0,
            "usd_cost": 0.0,
            "network_called": False,
            "env_read": False,
            "gold_decisions_read_by": "common evaluator only "
                                      "(scripts/evaluate_stage3_common.py)",
            "gold_modified": False,
            "predictions_modified": False,
            "existing_runs_overwritten": False,
            "scope": "DEV_ONLY",
        },
        "limitations": [
            "The frozen 33-item violation pack contains NO compliant (Gold=none) item, "
            "so this sensitivity analysis cannot demonstrate specificity or a "
            "controlled false-positive rate.",
            "Every violation item is routed to its single gold type, so cross-type "
            "false positives are structurally impossible in this pack; the informative "
            "axis is recall/F1, while precision panels are reported for fidelity to "
            "Sun Figures 8/9 (Sun's data comes from full-rule-base checking where "
            "false positives can occur).",
            "Per-process AP rests on only 3-5 matching candidates per process and "
            "per-process violation cells rest on 1-3 items per type; the sweep is a "
            "discrete diagnostic grid, not a statistical model-selection procedure.",
            "The matching score of Definition 4 is itself tau-gated, so the AP/MAP "
            "ranking changes with tau; ties are broken by stable order and low-tau "
            "rows saturate (many scores equal 1.0), which is why the AP curve on this "
            "data is non-monotonic (a small-set artefact, disclosed rather than tuned).",
        ],
    }
    return report


def _compact_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if key == "per_process":
            per_proc = {}
            for pid, detail in value.items():
                if pid.startswith("_"):
                    continue
                per_proc[pid] = {
                    "support": detail["support"],
                    "detected": detail["detected"],
                    "exact_type_accuracy": detail["exact_type_accuracy"],
                    "macro_f1": detail["macro_f1"],
                    "micro_f1": detail["micro_f1"],
                    "unobservable": detail["unobservable"],
                    "per_type_f1": {t: v["f1"] for t, v in detail["per_type"].items()},
                    "pool_missing_action_out_of_order": detail["pool_missing_action_out_of_order"],
                    "pool_incorrect_actor": detail["pool_incorrect_actor"],
                }
            out["per_process"] = per_proc
        else:
            out[key] = value
    return out


# --------------------------------------------------------------------------
# Markdown report
# --------------------------------------------------------------------------
def fmt_f1(v: float) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def render_markdown(report: dict[str, Any], sweep: dict[str, Any]) -> str:
    facts = {k: v for k, v in report["sun_source_facts"]}
    st = report["settings"]["sun_transferred"]
    cal = report["settings"]["sun_style_calibrated"]
    rows = []

    def h(level: int, text: str) -> None:
        rows.append(f"{'#' * level} {text}")

    def p(text: str = "") -> None:
        rows.append(text)

    h(1, "Stage 3 Sun 阈值敏感性实验报告（DEV_ONLY，零 API，2026-09-04）")
    p(f"> 对应论文方法：Sun et al. (2024) 第 5.3 节 / 图 8 / 图 9 的离散阈值网格分析。"
      f"本报告为 **development-only 方法级重建**，不是 Sun 原代码精确复现，也不是"
      f"预注册的正式结果；schema：`{report['schema_version']}`；git：`{report['git']['commit']}`。")
    p()

    h(2, "0. 结果口径与措辞")
    p("- **Sun-transferred**（迁移基线，保留方法级对照，也是论文表 A 中 Sun 行的口径）："
      f"τ={PRIMARY['tau']}、γ={PRIMARY['gamma']}、ϑ={PRIMARY['theta']}；"
      f"Macro-F1 {st['violation']['macro_f1']}、exact-type accuracy "
      f"{st['violation']['exact_type_accuracy']}、unobservable {st['violation']['unobservable']}。")
    p("- **Sun-style calibrated sensitivity**：测试集合中表现最好的观察设置（**tested "
      f"values 中的 best observed setting**）：τ={CALIBRATED['tau']}、γ={CALIBRATED['gamma']}、"
      f"ϑ={CALIBRATED['theta']}；Macro-F1 {cal['violation']['macro_f1']}、exact-type accuracy "
      f"{cal['violation']['exact_type_accuracy']}、unobservable {cal['violation']['unobservable']}。")
    p("- γ=0.6 只能称为：“tested values 中的 best observed setting”、“Sun-style "
      "threshold sensitivity result”、“本文数据与当前相似度后端上的经验校准值”。")
    p("- **不得**称为：数学全局最优阈值、Sun 原论文固定阈值、在独立 held-out test 上发现的"
      "最优值、与 Sun 原始四模型完全相同的数据结果。")
    p()

    h(2, "1. Sun 原文核对（只读，行号引自 `references/papers/extracted/sun_2024_full_text.txt`）")
    p(f"1. **τ** 是 rule–process matching threshold（Def. 4，L523–539）："
      f"matching(r,m,τ)=max(rule action 对中 sim>τ 的比例, rule actor/object 对中 sim>τ 的比例)。")
    p(f"2. **γ** 是 action similarity threshold（Def. 4 前言 L591–596：“if sim(S1,S2) > γ，"
      f"两个语义成分视为等价”）：决定 missing action 的可观察性（Def. 5，sim<γ 记为缺失）、"
      f"incorrect actor 的 R/C 映射与可观察性（Def. 6，仅 sim>γ 的动作映射进入 R）以及 "
      f"out-of-order 端点映射（Def. 7，U_r,m,γ 要求两个端点都以 sim>γ 映射）。")
    p(f"3. **ϑ** 是 actor similarity threshold（Def. 6，L549–559）：规则 actor r∈R 存在 "
      f"流程 actor/object r′∈C 使 sim(r,r′)<ϑ 即记违规。")
    p(f"4. Sun 的两个 matching 数据集总体均在 τ=0.8 时 MAP 最高：Table 9（12 个能源供应商流程模型）"
      f"MAP 0.801（9/12 模型在 0.8 最佳、3/12 在 0.6 最佳，L812–833）；Table 11（4 个 GDPR "
      f"BPMN 模型）MAP 0.840（4/4 在 0.8 最佳，L864–871）。")
    p(f"5. Sun 图 8（L894–907）：missing action 与 out-of-order 一起分析（两类精度只由 γ 决定），"
      f"多数模型在 γ=0.8 达到最高 Precision；复杂度最高的 Model 4 在 γ=0.6 最高；γ=0.9 低于 0.8。")
    p(f"6. Sun 图 9（L908–922）：固定 γ=0.8 后比较 ϑ；incorrect actor 的精度受 γ 与 ϑ 共同影响，"
      f"前两类在 γ=0.8 更好，故 ϑ 单独在 γ=0.8 下分析。四个模型中两个在 ϑ=0.8 最好，另外两个"
      f"（更大、内容更多的模型）在 ϑ=0.7 最好。")
    p(f"7. Sun 的解释（L895–922）：复杂/更大模型的文本内容更多，语义相似度在复杂情境下下降，"
      f"因此较低阈值可能更合适；阈值过高（更严格）会把正常操作识别为违规、降低 Precision。")
    p(f"8. 措辞：**0.8 是 Sun 自己数据上多数模型表现较好的经验值，不是“Sun 规定所有模型必须"
      f"使用 0.8”，也不是定义本身写死的值**；同理本文 γ=0.6 只是 tested values 中的 best "
      f"observed setting。")
    p()

    h(2, "2. 冻结口径（本实验未改动任何输入/方法/公式）")
    p("- 冻结 GDPR-7 BPMN（7 流程）；33 条人工裁决 Gold（11/11/11，`data/gold/stage3/`）；"
      "25 条 matching Gold；Rule/Process Records（S3.5 缓存）；Sun Definition 4–7 重建；"
      "spaCy `en_core_web_sm` 相似度后端；common evaluator；原始 γ=0.8 结果与全部其他方法结果。")
    p("- 未修改 Gold、样本、预测标签或评价公式；**全程离线，API calls = 0、cost = $0**；"
      "既有 evidence（`outputs/evidence/s35_sun_stage3_development_v2/*`）逐字节未动（测试哈希锁）。")
    p("- **限制披露**：33 条人工 Gold 没有 `Gold=none` 合规样本，因此本实验**不能用它证明 "
      "specificity 或控制 false-positive rate**；33 条 panel 每个测试点预路由到单一 gold 类型，"
      "跨类型 FP 在该 panel 上结构性不可能出现，Precision 的信息量低于 Recall/F1。")
    p()

    h(2, "3. 阈值集合（严格对齐 Sun 的离散网格）")
    p(f"- matching τ ∈ {MATCHING_TAU_GRID}（Sun Table 9 的 τ 列）——只评价 matching AP/MAP，"
      f"不把 matching MAP 当作 violation F1。")
    p(f"- violation γ ∈ {GAMMA_GRID}（ϑ 固定 0.8）——每个 γ 都通过 SunScorer 真实重算 "
      f"action mappings、actor denominators、order endpoints 与 observability，不是对既有最终分数重切阈值。")
    p(f"- incorrect-actor ϑ ∈ {THETA_GRID}，**固定 γ=0.8**（与 Sun 图 9 一致）。")
    p()

    h(2, "4. 主结果")
    h(3, "4.1 匹配（τ 扫描：Def-4 分数重算 + 排序 AP/MAP，support=25）")
    tau_rows = report["matching_tau_sweep"]
    proc_ids = sorted(tau_rows[0]["per_process_ap"])
    header = ["τ"] + [f"AP({PROCESS_SHORT[pid]})" for pid in proc_ids] + ["MAP", "runtime(s)"]
    rows.append("| " + " | ".join(header) + " |")
    rows.append("|" + "---|" * len(header))
    for r in tau_rows:
        cells = [f"{r['tau']:g}"]
        for pid in sorted(r["per_process_ap"]):
            cells.append(f"{r['per_process_ap'][pid]:.4f}")
        cells.append(f"{r['MAP']:.4f}")
        cells.append(f"{r['runtime_seconds']:.2f}")
        rows.append("| " + " | ".join(cells) + " |")
    p()
    p(f"注：per-process AP 只有 3–5 个候选规则；τ 越低 Def-4 分数越饱和（大量 1.0 平局），"
      f"故该曲线上本文数据**不**呈现 Sun Table 9 的倒 U 型——这是小集合平局排序的披露性结果，"
      f"不是匹配方法“更好/更差”的证据。τ=0.8 行与 evidence `evaluation.json` 的 per-process AP/MAP "
      f"完全一致（验证块）。")
    p()

    h(3, "4.2 违规检测（γ 扫描，ϑ 固定 0.8；33 条人工 Gold，unobservable 计入 FN）")
    gamma_rows = report["gamma_sweep"]
    rows.append("| γ | Missing F1 | Incorrect-actor F1 | Out-of-order F1 | Macro-F1 | Micro-F1 | "
                "Exact | Unobs | runtime(s) |")
    rows.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in gamma_rows:
        ft = r["per_type"]
        rows.append(
            f"| {r['gamma']:g} | {ft['missing_action']['f1']:.4f} | "
            f"{ft['incorrect_actor']['f1']:.4f} | {ft['out_of_order']['f1']:.4f} | "
            f"{r['macro_f1']:.4f} | {r['micro_f1']:.4f} | {r['exact_type_accuracy']:.4f} | "
            f"{r['unobservable']} | {r['runtime_seconds']:.2f} |")
    p()
    diag_t = report["scorer_diagnostics"]["sun_transferred"]
    diag_c = report["scorer_diagnostics"]["sun_style_calibrated"]
    oo_total_t = sum(1 for v in diag_t.values() if v.get("check_type") == "out_of_order")
    oo_zero_t = sum(1 for v in diag_t.values()
                    if v.get("check_type") == "out_of_order" and v.get("oo_denominator") == 0)
    oo_total_c = sum(1 for v in diag_c.values() if v.get("check_type") == "out_of_order")
    oo_zero_c = sum(1 for v in diag_c.values()
                    if v.get("check_type") == "out_of_order" and v.get("oo_denominator") == 0)
    ia_unobs_t = sum(1 for v in diag_t.values()
                     if v.get("check_type") == "incorrect_actor" and not v.get("ia_observable"))
    p(f"γ=0.8（转移基线）：Macro-F1 0.3889、exact 0.3636、unobservable 10——大量合法的 action "
      f"mappings 无法通过门槛（incorrect-actor 10 条 `action_mapping_below_gamma` 不可观察；"
      f"out-of-order 端点映射分母为 0 的检查点 {oo_zero_t}/{oo_total_t} → 0/11 检出），"
      f"不是公式错误而是门槛与相似度后端的错配。")
    p(f"γ=0.6（tested values 中的 best observed setting）：Missing F1 1.0000、Incorrect-actor "
      f"F1 0.7778、Out-of-order F1 0.8421、Macro-F1 0.8733、exact 0.7879、unobservable 4；"
      f"out-of-order 端点映射分母为 0 的检查点降至 {oo_zero_c}/{oo_total_c}。")
    p()

    h(3, "4.3 Incorrect-actor（ϑ 扫描，γ 固定 0.8——Sun 图 9 口径）")
    theta_rows = report["theta_sweep"]
    rows.append("| ϑ | Incorrect-actor P | R | F1 | Macro-F1 | Exact | Unobs | runtime(s) |")
    rows.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in theta_rows:
        ia = r["per_type"]["incorrect_actor"]
        rows.append(f"| {r['theta']:g} | {ia['precision']:.4f} | {ia['recall']:.4f} | "
                    f"{ia['f1']:.4f} | {r['macro_f1']:.4f} | {r['exact_type_accuracy']:.4f} | "
                    f"{r['unobservable']} | {r['runtime_seconds']:.2f} |")
    p()
    ia_obs_t = {iid: v for iid, v in diag_t.items()
                if v.get("check_type") == "incorrect_actor" and v.get("ia_observable")}
    p(f"γ=0.8 下 incorrect-actor 检查几乎整体不可观察（11 条中 {ia_unobs_t} 条 "
      f"`action_mapping_below_gamma`）。")
    if ia_obs_t:
        for iid, v in sorted(ia_obs_t.items()):
            p(f"唯一可观察检查点 {iid} 的 min actor similarity = {v.get('ia_min_actor_sim')}，"
              f"低于测试网格中的最小 ϑ=0.5，因此在每个测试 ϑ 下都触发同一判定。")
    p("故 ϑ 行在本文数据上完全平坦——这是可观察性瓶颈的真实结果，不构成对 Sun 图 9 趋势的复现或否定。")
    p()

    h(3, "4.4 各 process 结果（每阈值一行；缩写 P1–P7 = gdpr_1_data_breach … gdpr_7_right_to_be_forgotten）")
    rows.append("| 扫描 | 阈值 | process | support | exact | Macro-F1 | Micro-F1 | unobs | "
                "Missing F1 | Incorrect-actor F1 | Out-of-order F1 |")
    rows.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for kind, key, rows_in in (("γ", "gamma", gamma_rows), ("ϑ(γ=0.8)", "theta", theta_rows)):
        for r in rows_in:
            th = r[key]
            for pid in sorted(r["per_process"]):
                d = r["per_process"][pid]
                ft = d["per_type_f1"]
                rows.append(f"| {kind} | {th:g} | {PROCESS_SHORT[pid]} ({pid}) | {d['support']} | "
                            f"{d['exact_type_accuracy']:.4f} | {d['macro_f1']:.4f} | {d['micro_f1']:.4f} | "
                            f"{d['unobservable']} | {ft['missing_action']:.4f} | "
                            f"{ft['incorrect_actor']:.4f} | {ft['out_of_order']:.4f} |")
    p()

    h(3, "4.5 两种报告口径汇总（相同 33 条 Gold、相同 evaluator）")
    rows.append("| 设置 | τ/γ/ϑ | Matching MAP | Missing F1 | Incorrect-actor F1 | Out-of-order F1 | "
                "Macro-F1 | Micro-F1 | Exact | Unobs |")
    rows.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for label, s in (("Sun-transferred", st), ("Sun-style calibrated (best observed)", cal)):
        v = s["violation"]
        ft = v["per_type"]
        th = s["thresholds"]
        rows.append(f"| {label} | {th['tau']:g}/{th['gamma']:g}/{th['theta']:g} | "
                    f"{s['matching_MAP']:.4f} | {ft['missing_action']['f1']:.4f} | "
                    f"{ft['incorrect_actor']['f1']:.4f} | {ft['out_of_order']['f1']:.4f} | "
                    f"{v['macro_f1']:.4f} | {v['micro_f1']:.4f} | "
                    f"{v['exact_type_accuracy']:.4f} | {v['unobservable']} |")
    p()

    h(2, "5. 为什么 γ=0.6 更适合当前数据（解释，不含“最优”声明）")
    p("1. 相似度后端差异：本文与 S3.4/S3.5 共用 spaCy `en_core_web_sm`（无词向量，W007；"
      "相似度来自 tagger/parser/NER 张量），词面-语义相似度分布与 Sun 论文所用后端/数据不同，"
      "因此同一 0.8 门槛在本数据上放行的合法 mapping 更少。")
    p(f"2. γ=0.8 的可观察性结果（scorer 诊断测量）：{ia_unobs_t}/11 incorrect-actor 检查为 "
      f"`action_mapping_below_gamma` 不可观察；out-of-order 检查 {oo_zero_t}/{oo_total_t} 个端点映射"
      f"分母为 0、0/11 检出（F1=0）。这不是公式错误，而是门槛与该相似度后端的错配（mapping 分数整体偏低）。")
    ia_obs_c = {iid: v for iid, v in diag_c.items()
                if v.get("check_type") == "incorrect_actor" and v.get("ia_observable")}
    if ia_obs_c:
        max_min = max(v.get("ia_min_actor_sim", -1.0) for v in ia_obs_c.values())
        ia_c_note = (f"{len(ia_obs_c)} 条可观察检查点的 min actor sim 全部 ≤ {max_min}，"
                     f"即任何 ϑ∈{THETA_GRID} 判定都不变（诊断测量，非正式 ϑ 扫描）")
    else:
        ia_c_note = ""
    p(f"3. γ=0.6 的平衡点：missing-action 保持 F1=1.0（其对词面缺失信号不敏感于 0.6–0.9 区间）；"
      f"incorrect-actor 可观察 {len(ia_obs_c)}/11、F1 0.1667→0.7778（{ia_c_note}）；"
      f"out-of-order 端点映射分母>0 的 "
      f"{oo_total_c - oo_zero_c}/11 全部检出、其余分母为 0 不可判定，F1 0.0→0.8421；"
      f"Macro-F1 0.3889→0.8733、exact 0.3636→0.7879、unobservable 10→4。")
    p("4. 结论措辞（与 Sun 一致的方式）：Sun 将其 Model 4 在 γ=0.6 更好归因于复杂模型文本相似度"
      "下降；本文的同类现象出现在**相似度后端整体偏低**的七模型数据上。结论是阈值需要随数据复杂度"
      "与相似度后端重新校准，而不是 Sun 的公式无效。")
    p()

    h(2, "6. 验证与不变量")
    p(f"- primary row (0.8, 0.8) 与 evidence `evaluation.json` 逐项一致："
      f"{'通过' if report['verification']['primary_row_matches_evaluation_json'] is True else '失败'}"
      f"；与 evidence `threshold_sensitivity.json` 的所有重叠行一致："
      f"{'通过' if report['verification']['overlap_rows_all_match'] else '失败'}。")
    p(f"- 输入绑定（hash）见报告 JSON `input_bindings`；correction/gold/inference/blank/BPMN 均未改动。")
    p(f"- 安全声明：llm_api_called=False、api_calls=0、usd_cost=0、network_called=False、"
      f"env_read=False；Gold 只由 common evaluator 读取。")
    p()

    h(2, "7. 产物")
    p("- 本报告：`outputs/reports/s35_sun_stage3_threshold_sensitivity_v1.md`")
    p("- 机器可读 JSON：`outputs/reports/s35_sun_stage3_threshold_sensitivity_v1.json`"
      "（完整 sweep：`outputs/development/s35_sun_stage3_threshold_sensitivity_v1/sweep.json`）")
    p("- 图 A（γ 敏感性，missing action + out-of-order；对应 Sun 图 8 口径）："
      "`..._figA_gamma_missing_action_out_of_order.svg`")
    p("- 图 B（ϑ 敏感性，incorrect actor，γ=0.8；对应 Sun 图 9 口径）："
      "`..._figB_theta_incorrect_actor.svg`")
    p(f"- 复现：`python scripts/build_sun_stage3_threshold_sensitivity_v1.py`（全量离线重算）；"
      f"`--report-only` 从 sweep JSON 确定性重放报告/图。总耗时 {report['runtime']['total_wall_seconds']} s。")
    return "\n".join(rows) + "\n"


# --------------------------------------------------------------------------
# figures (pure-python SVG, deterministic, no external plotting dependency)
# --------------------------------------------------------------------------
def _svg_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2"]


def fig_a_data(gamma_rows: list[dict]) -> dict[str, list[tuple[float, float]]]:
    """Per-process pooled missing_action + out_of_order metrics over gamma."""
    out: dict[str, dict[str, list[tuple[float, float]]]] = {m: {} for m in ("precision", "recall", "f1")}
    for r in gamma_rows:
        for pid, detail in r["per_process"].items():
            if pid.startswith("_"):
                continue
            pool = detail["pool_missing_action_out_of_order"]
            for m in ("precision", "recall", "f1"):
                out[m].setdefault(pid, []).append((r["gamma"], pool[m]))
    return out


def fig_b_data(theta_rows: list[dict]) -> dict[str, dict[str, list[tuple[float, float]]]]:
    """Per-process incorrect_actor metrics over theta at gamma=0.8."""
    out: dict[str, dict[str, list[tuple[float, float]]]] = {m: {} for m in ("precision", "recall", "f1")}
    for r in theta_rows:
        for pid, detail in r["per_process"].items():
            if pid.startswith("_"):
                continue
            pool = detail["pool_incorrect_actor"]
            for m in ("precision", "recall", "f1"):
                out[m].setdefault(pid, []).append((r["theta"], pool[m]))
    return out


def write_figures(sweep: dict[str, Any], target_dir: Path) -> list[Path]:
    gamma_rows = sweep["gamma_sweep"]
    theta_rows = sweep["theta_sweep"]
    a = fig_a_data(gamma_rows)
    b = fig_b_data(theta_rows)
    note_a = ("Figure A - gamma sensitivity on missing-action + out-of-order (pooled per process), "
              "Sun 2024 Figure 8 protocol (x-axis = gamma). Sun's figure reports PRECISION; recall/F1 "
              "panels are supplementary. This 33-item pack routes every item to its single gold type, "
              "so cross-type false positives are structurally absent and precision reduces to "
              "1.0/0.0; unobservable items count as FN in every panel.")
    note_b = ("Figure B - incorrect-actor sensitivity over theta with gamma FIXED at 0.8, "
              "Sun 2024 Figure 9 protocol (x-axis = theta). At gamma=0.8 only 1 of 11 incorrect-actor "
              "check points is observable on this data (10 are action_mapping_below_gamma), so every "
              "theta row is identical; the figure documents the observability wall rather than a theta "
              "trend. Same precision/recall/F1 panel note as Figure A.")
    svg_a = _three_panel_svg(a, note_a, "gamma", "Figure A (Sun Figure 8 protocol): "
                              "gamma sensitivity, missing action + out-of-order, per process (P1-P7)")
    svg_b = _three_panel_svg(b, note_b, "theta", "Figure B (Sun Figure 9 protocol): "
                              "incorrect actor over theta at gamma=0.8, per process (P1-P7)")
    out = []
    for path, content in ((target_dir / "s35_sun_stage3_threshold_sensitivity_v1_figA_gamma_missing_action_out_of_order.svg", svg_a),
                          (target_dir / "s35_sun_stage3_threshold_sensitivity_v1_figB_theta_incorrect_actor.svg", svg_b)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        out.append(path)
    return out


def _three_panel_svg(data: dict[str, dict[str, list[tuple[float, float]]]],
                     note: str, threshold_name: str, figure_label: str) -> str:
    series_by_metric: dict[str, dict[str, list[tuple[float, float]]]] = {
        metric: {pid: data[metric][pid] for pid in sorted(data[metric])}
        for metric in ("precision", "recall", "f1")
    }
    panels = [{"title": metric} for metric in ("precision", "recall", "f1")]
    first = next(iter(series_by_metric["precision"].values()))
    x_ticks = [p[0] for p in first]
    titles = {"precision": "Precision (Sun figure metric)",
              "recall": "Recall (supplementary)",
              "f1": "F1 (supplementary)"}
    return _line_chart_svg_full(figure_label, threshold_name, x_ticks, panels,
                                series_by_metric, note, titles)


def _wrap(text: str, width_chars: int = 150) -> list[str]:
    """Greedy word wrap for SVG note lines (approximate char width)."""
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        if current and len(current) + 1 + len(word) > width_chars:
            lines.append(current)
            current = word
        elif current:
            current += " " + word
        else:
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _line_chart_svg_full(title: str, x_label: str, x_ticks: list[float],
                         panels: list[dict],
                         series_by_metric: dict[str, dict[str, list[tuple[float, float]]]],
                         note: str, panel_titles: dict[str, str]) -> str:
    """Single figure with one panel per metric (precision/recall/F1)."""
    panel_h = 195
    left = 62
    right = 34
    top = 52
    width = 940
    plot_w = width - left - right
    mapping_pairs = ", ".join(f"{PROCESS_SHORT[pid]}={pid}" for pid in sorted(series_by_metric["precision"]))
    mapping_lines = _wrap(mapping_pairs, 118)
    note_lines = _wrap(note, 132)
    legend_h = 24 + 14 * len(mapping_lines) + 4 + 14 * len(note_lines)
    height = top + panel_h * len(panels) + legend_h
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             f'<text x="{width/2}" y="22" text-anchor="middle" font-size="15" font-weight="bold">'
             f'{_svg_escape(title)}</text>']
    x_min, x_max = float(min(x_ticks)), float(max(x_ticks))
    pad = (x_max - x_min) * 0.05 if x_max != x_min else 0.05
    x0, x1 = x_min - pad, x_max + pad
    metric_order = ["precision", "recall", "f1"]
    for mi, metric in enumerate(metric_order):
        y0 = top + mi * panel_h
        y_axis = y0 + panel_h - 40
        parts.append(f'<text x="{left - 10}" y="{y0 + 14}" text-anchor="end" font-size="12" '
                     f'font-weight="bold">{_svg_escape(panel_titles[metric])}</text>')
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            gy = y_axis - frac * (panel_h - 78)
            parts.append(f'<line x1="{left}" y1="{gy:.1f}" x2="{width - right}" y2="{gy:.1f}" '
                         f'stroke="#e0e0e0" stroke-width="0.8"/>')
            parts.append(f'<text x="{left - 8}" y="{gy + 4:.1f}" text-anchor="end" font-size="10" '
                         f'fill="#555555">{frac:g}</text>')
        for tick in x_ticks:
            gx = left + (tick - x0) / (x1 - x0) * plot_w
            parts.append(f'<line x1="{gx:.1f}" y1="{y_axis}" x2="{gx:.1f}" y2="{y_axis + 5}" '
                         f'stroke="#888888" stroke-width="1"/>')
            parts.append(f'<text x="{gx:.1f}" y="{y_axis + 18}" text-anchor="middle" font-size="10">'
                         f'{tick:g}</text>')
        if mi == len(metric_order) - 1:
            parts.append(f'<text x="{width/2}" y="{y_axis + 34}" text-anchor="middle" font-size="11">'
                         f'{_svg_escape(x_label)}</text>')
        for si, (pid, points) in enumerate(sorted(series_by_metric[metric].items())):
            color = PALETTE[si % len(PALETTE)]
            pts = [(p[0], p[1]) for p in points if p[1] is not None]
            if len(pts) < 2:
                continue
            coords = []
            for (px, py) in pts:
                gx = left + (px - x0) / (x1 - x0) * plot_w
                gy = y_axis - float(py) * (panel_h - 78)
                coords.append(f"{gx:.1f},{gy:.1f}")
            parts.append(f'<polyline points="{" ".join(coords)}" fill="none" stroke="{color}" '
                         f'stroke-width="1.8"/>')
            for xi, (px, py) in enumerate(pts):
                gx = left + (px - x0) / (x1 - x0) * plot_w
                gy = y_axis - float(py) * (panel_h - 78)
                jx = (si - len(series_by_metric[metric]) / 2 + 0.5) * 3.4
                parts.append(f'<circle cx="{gx + jx:.1f}" cy="{gy:.1f}" r="3" fill="{color}"/>')
    ly = top + panel_h * len(panels) + 4
    x_cursor = left
    for si, pid in enumerate(sorted(series_by_metric["precision"])):
        color = PALETTE[si % len(PALETTE)]
        parts.append(f'<line x1="{x_cursor}" y1="{ly}" x2="{x_cursor + 16}" y2="{ly}" '
                     f'stroke="{color}" stroke-width="2.5"/>')
        parts.append(f'<circle cx="{x_cursor + 21}" cy="{ly}" r="2.6" fill="{color}"/>')
        parts.append(f'<text x="{x_cursor + 28}" y="{ly + 4}" font-size="10" '
                     f'font-weight="bold">{PROCESS_SHORT[pid]}</text>')
        x_cursor += 60
    line_y = ly + 16
    for mapping_line in mapping_lines:
        parts.append(f'<text x="{left}" y="{line_y}" font-size="10" fill="#333333">'
                     f'{_svg_escape(mapping_line)}</text>')
        line_y += 13
    line_y += 3
    for note_line in note_lines:
        parts.append(f'<text x="{left}" y="{line_y}" font-size="10" fill="#444444">'
                     f'{_svg_escape(note_line)}</text>')
        line_y += 13
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def write_artifacts(report: dict[str, Any], sweep: dict[str, Any],
                    report_json_path: Path, report_md_path: Path,
                    figure_dir: Path) -> None:
    write_json(report_json_path, report)
    write_text(report_md_path, render_markdown(report, sweep))
    write_figures(sweep, figure_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true",
                        help="deterministic replay of report JSON/MD/figures from the sweep JSON")
    parser.add_argument("--sweep-file", type=Path, default=SWEEP_JSON)
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="target directory for the report artifacts (default: outputs/reports)")
    parser.add_argument("--force", action="store_true",
                        help="allow overwriting existing artifacts")
    args = parser.parse_args()
    out_dir = (args.out_dir or ROOT / "outputs" / "reports").resolve()
    sweep_file = args.sweep_file.resolve()

    if args.report_only:
        if not sweep_file.exists():
            print(f"report-only replay failed: sweep JSON missing: {sweep_file}",
                  file=sys.stderr)
            return 2
        sweep = load_json(sweep_file, "sweep JSON")
        report = sweep.get("report")
        if not isinstance(report, dict):
            print("report-only replay failed: sweep JSON has no embedded 'report' payload",
                  file=sys.stderr)
            return 2
        write_json(out_dir / "s35_sun_stage3_threshold_sensitivity_v1.json", report)
        write_text(out_dir / "s35_sun_stage3_threshold_sensitivity_v1.md",
                   render_markdown(report, sweep))
        write_figures(sweep, out_dir)
        print(f"report-only replay done -> {out_dir}")
        return 0

    if not args.force and SWEEP_JSON.exists():
        print(f"refusing to overwrite existing sweep JSON: {SWEEP_JSON} "
              f"(use --force or --report-only)", file=sys.stderr)
        return 2
    report_targets = [REPORT_JSON, REPORT_MD, FIG_A, FIG_B]
    if not args.force:
        existing = [str(p) for p in report_targets if p.exists()]
        if existing:
            print(f"refusing to overwrite existing report artifacts: {existing}",
                  file=sys.stderr)
            return 2

    correction = load_json(CORRECTION_PACK, "correction pack")
    started = time.perf_counter()
    runtime = build_runtime()
    sweep = run_sweep(runtime, correction)
    elapsed = time.perf_counter() - started
    report = assemble_report(sweep, {"rule_source": runtime["rule_source"]}, elapsed)
    verification = report["verification"]
    if not verification["primary_row_matches_evaluation_json"] or \
            not verification["overlap_rows_all_match"]:
        print("STOP: recompute does not match the recorded evidence; refusing to write "
              "artifacts.\n" + json.dumps(verification["issues"], ensure_ascii=False, indent=2),
              file=sys.stderr)
        return 3
    SWEEP_DIR.mkdir(parents=True, exist_ok=True)
    sweep["report"] = report  # embedded payload for deterministic --report-only replay
    write_json(SWEEP_JSON, sweep)
    write_artifacts(report, sweep, REPORT_JSON, REPORT_MD, ROOT / "outputs" / "reports")
    print(f"sweep + report artifacts written: {SWEEP_JSON}")
    print(f"report: {REPORT_JSON}\nmd: {REPORT_MD}\nfigures: {FIG_A}, {FIG_B}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
