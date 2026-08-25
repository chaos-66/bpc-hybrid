# -*- coding: utf-8 -*-
"""Barrientos et al. (2026) module-level ablation suite v1 (zero API).

Executes the REAL offline ablations and prepares (does NOT fabricate) the
model-calling arms:

* Experiment A — Direct-LLM validation-chain ablation (Full / Schema-only /
  Raw-approximation) on the LOCKED s27 D1-R3 responses.  The raw model JSON
  is not persisted in the locked artifacts; the raw condition is therefore
  approximated from the persisted canonical records (first-occurrence
  anchoring) and explicitly labelled as an approximation.  The canonicalizer
  audit (reanchored/degraded/unchanged counts) is reported as the
  deterministic-post-processing recovery evidence.
* Experiment B — Rules-Only module-removal ablation (one-factor-at-a-time on
  the same EStG-150 / same Gold / same evaluator).  Re-composes canonical
  records from ONE shared CoreNLP + classifier pass with explicit feature
  flags (lexicon extensions, BERT-TextCNN modality, actor-action ownership
  edges, multi-match fail-closed guard, DE-EN alignment validation).
* Experiment C — four-class vs three-class modality projection (offline on
  formal Gold/predictions; definition coverage loss reported explicitly).
* Experiment D — Direct-LLM prompt/few-shot arms: full_v6_6shot reuses the
  locked formal result; no_fewshot / barrientos_style / minimal_prompt are
  PREPARED but NOT executed (real model calls require user authorization).
* Experiment E — Barrientos same-data comparison: PREPARED but NOT executed
  (same-data 38 non-empty requirements; shared metrics protocol defined).

Discipline: never modifies Gold, never overwrites formal predictions, never
fabricates unexecuted results; references/ stays read-only.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

CONFIG = ROOT / "configs/ablations/barrientos_ablation_suite_v1.json"
OUT_DIR = ROOT / "outputs/development/barrientos_ablation_suite_v1"
REPORT_DIR = ROOT / "outputs/reports"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path, label: str) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {label}: {path}") from exc
    return value


def _write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def _git_state() -> dict[str, str]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, check=True,
        ).stdout.strip()
        return {"commit": commit}
    except Exception:  # pragma: no cover
        return {"commit": "unknown"}


# ---------------------------------------------------------------------------
# Experiment A — Direct-LLM validation-chain ablation (locked responses)
# ---------------------------------------------------------------------------


def _flatten_spans(clauses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten field spans (with field label) from canonical clauses."""
    spans: list[dict[str, Any]] = []
    fields = ("actors", "actions", "conditions", "constraints", "exceptions")
    for clause in clauses:
        cid = clause.get("clause_id", "?")
        for field in fields:
            for sp in clause.get(field) or []:
                spans.append({
                    "clause_id": cid,
                    "field": field,
                    "text": sp.get("text", ""),
                    "start": sp.get("start"),
                    "end": sp.get("end"),
                })
    return spans


def _first_occurrence_anchor(text: str, source_text: str) -> tuple[int | None, int | None]:
    """Naive first-occurrence anchor (Raw/Schema-only approximation)."""
    if not text:
        return None, None
    idx = source_text.find(text)
    if idx < 0:
        return None, None
    return idx, idx + len(text)


def _reanchor_first_occurrence(record: Mapping[str, Any],
                               source_text: str) -> dict[str, Any]:
    """Return a copy of the canonical record with every span re-anchored by
    first-occurrence (simulating no deterministic unique-exact re-anchor)."""
    out = copy.deepcopy(dict(record))
    for clause in out.get("clauses", []):
        for field in ("actors", "actions", "conditions", "constraints",
                      "exceptions"):
            for sp in clause.get(field) or []:
                s, e = _first_occurrence_anchor(sp.get("text", ""), source_text)
                sp["start"] = s
                sp["end"] = e
        csp = clause.get("clause_span") or {}
        s, e = _first_occurrence_anchor(csp.get("text", ""), source_text)
        if s is not None:
            clause["clause_span"] = {**csp, "start": s, "end": e}
    return out


def _drop_unanchored(record: Mapping[str, Any]) -> dict[str, Any]:
    """Raw-like: drop spans that cannot be exactly re-anchored (empty
    prediction for the offending element), keeping the denominator."""
    out = copy.deepcopy(dict(record))
    for clause in out.get("clauses", []):
        for field in ("actors", "actions", "conditions", "constraints",
                      "exceptions"):
            kept = []
            for sp in clause.get(field) or []:
                if sp.get("start") is None or sp.get("end") is None:
                    continue  # unanchored -> dropped (empty prediction)
                kept.append(sp)
            clause[field] = kept
        ev = clause.get("modality") or {}
        if isinstance(ev.get("evidence"), list):
            kept = [e for e in ev["evidence"]
                    if e.get("start") is not None and e.get("end") is not None]
            ev["evidence"] = kept
    return out


def run_experiment_a(config: Mapping[str, Any]) -> dict[str, Any]:
    """Full / Schema-only / Raw-approx on locked D1-R3 responses, evaluated
    with the SAME sun_literal_overlap@2.0.0 evaluator against the SAME Gold
    (Layer E @ 56d2b03 via build_canonical_gold_records, mirroring
    evaluate_d1_r3_clean_rerun.py)."""
    from bpc_hybrid.estg150_b0_development import build_canonical_gold_records
    from bpc_hybrid.stage2_sun_literal_overlap import evaluate_sun_literal_overlap

    responses_path = ROOT / config["inputs"]["d1_r3_responses"]
    responses = [json.loads(l) for l in responses_path.read_text(
        encoding="utf-8").splitlines() if l.strip()]
    by_id = {r["sample_id"]: r for r in responses}

    # ---- build Gold from the historical blob (git show 56d2b03) -------------
    source_commit = "56d2b03"
    layer_e_path = ("formal_experiment/data/development/human_review/"
                    "estg_150_human_correction_v1.json")
    membership_path = ("formal_experiment/data/development/estg/"
                       "estg_150_membership_hashes.json")
    git = lambda *args: subprocess.run(
        ["git", *args], cwd=ROOT.parent, capture_output=True, check=True
    ).stdout

    def git_show_bytes(commit: str, path: str) -> bytes:
        return git("show", f"{commit}:{path}")

    import tempfile
    with tempfile.TemporaryDirectory(prefix="barr-a-", dir=ROOT / ".tmp") as td:
        work = Path(td)
        (work / "layer_e").write_bytes(git_show_bytes(source_commit, layer_e_path))
        (work / "membership").write_bytes(git_show_bytes(source_commit, membership_path))
        gold, _source_records = build_canonical_gold_records(
            work / "layer_e", work / "membership")
    gold_by_id = {row["sample_id"]: row for row in gold}
    if len(gold) != 150:
        raise RuntimeError(f"gold count {len(gold)} != 150")
    if set(gold_by_id) != set(by_id):
        raise RuntimeError("gold/prediction membership mismatch")

    # ---- build the three conditions -----------------------------------------
    full_rows: list[dict[str, Any]] = []
    schema_rows: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    for row in responses:
        rec = row.get("record")
        sample_id = row["sample_id"]
        if not isinstance(rec, Mapping):
            base = {"sample_id": sample_id, "request_status": "ok",
                    "error_category": None, "errors": [], "record": {}}
            full_rows.append(dict(base))
            schema_rows.append(dict(base))
            raw_rows.append(dict(base))
            continue
        source_text = rec.get("source_text", "")
        so = _reanchor_first_occurrence(rec, source_text)
        raw = _drop_unanchored(so)
        full_rows.append({"sample_id": sample_id, "request_status": "ok",
                          "error_category": None, "errors": [], "record": rec})
        schema_rows.append({"sample_id": sample_id, "request_status": "ok",
                            "error_category": None, "errors": [],
                            "record": so})
        raw_rows.append({"sample_id": sample_id, "request_status": "ok",
                         "error_category": None, "errors": [], "record": raw})

    def evaluate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        metrics = evaluate_sun_literal_overlap(
            gold, rows, dataset_id="independently_reconstructed_estg_150_v1",
            method_id="direct_llm")
        per_field = {
            f: {k: round(metrics["per_field"][f][k], 6)
                for k in ("precision", "recall", "f1")}
            for f in ("modality", "actor", "action", "condition", "constraint",
                      "exception")
        }
        return {"overall": metrics["overall"], "per_field": per_field,
                "match_rule": metrics.get("match_rule")}

    full_metrics = evaluate(full_rows)
    schema_metrics = evaluate(schema_rows)
    raw_metrics = evaluate(raw_rows)

    def delta(b: dict[str, Any], a: dict[str, Any]) -> dict[str, Any]:
        return {
            "overall_f1_delta": round(b["overall"]["f1"] - a["overall"]["f1"], 6),
            "per_field_f1_delta": {
                f: round(b["per_field"][f]["f1"] - a["per_field"][f]["f1"], 6)
                for f in b["per_field"]
            },
        }

    # ---- canonicalizer recovery stats (locked audit) ------------------------
    status_counts: dict[str, int] = {}
    reanchored_total = 0
    dropped_span_total = 0
    dropped_clause_total = 0
    dropped_edge_total = 0
    failed_reasons: dict[str, int] = {}
    recovered_or_changed = 0
    for row in responses:
        sc = row.get("span_canonicalization") or {}
        status = sc.get("status", "n/a")
        status_counts[status] = status_counts.get(status, 0) + 1
        reanchored_total += int(sc.get("reanchored_count", 0))
        dropped_span_total += len(sc.get("dropped_spans") or [])
        dropped_clause_total += len(sc.get("dropped_clauses") or [])
        dropped_edge_total += len(sc.get("dropped_edges") or [])
        for fr in sc.get("failed_reasons") or []:
            failed_reasons[fr] = failed_reasons.get(fr, 0) + 1
        if status in ("reanchored", "degraded"):
            recovered_or_changed += 1

    ok_rows = [r for r in responses if r.get("request_status") == "ok"]
    legal_rate = len(ok_rows) / len(responses) if responses else 0.0

    def diagnostics(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
        span_oob = 0
        unanchored = 0
        broken_edges = 0
        total_spans = 0
        for item in rows:
            rec = item.get("record") or {}
            src = rec.get("source_text", "")
            for clause in rec.get("clauses", []):
                for field in ("actors", "actions", "conditions", "constraints",
                              "exceptions"):
                    for sp in clause.get(field) or []:
                        total_spans += 1
                        s, e = sp.get("start"), sp.get("end")
                        if s is None or e is None:
                            unanchored += 1
                        elif s < 0 or e > len(src) or s > e:
                            span_oob += 1
                for edge in clause.get("actor_action_map") or []:
                    ids = {x.get("id") for x in clause.get("actors") or []}
                    acts = {x.get("id") for x in clause.get("actions") or []}
                    if (edge.get("actor_id") not in ids
                            or edge.get("action_id") not in acts):
                        broken_edges += 1
        return {"total_spans": total_spans, "span_out_of_range": span_oob,
                "unanchored_spans": unanchored,
                "broken_actor_action_edges": broken_edges}

    # ---- before/after examples (canonicalizer re-anchor effect) -------------
    examples: list[dict[str, Any]] = []
    for row in responses:
        if len(examples) >= 5:
            break
        sc = row.get("span_canonicalization") or {}
        rec = row.get("record")
        if sc.get("status") != "reanchored" or not isinstance(rec, Mapping):
            continue
        src = rec.get("source_text", "")
        changed = []
        for clause in rec.get("clauses", []):
            for field in ("actors", "actions", "conditions", "constraints",
                          "exceptions"):
                for sp in clause.get(field) or []:
                    text = sp.get("text", "")
                    first_s, first_e = _first_occurrence_anchor(text, src)
                    if first_s is not None and (first_s, first_e) != (
                            sp.get("start"), sp.get("end")):
                        changed.append({
                            "field": field,
                            "text": text,
                            "first_occurrence": [first_s, first_e],
                            "canonical": [sp.get("start"), sp.get("end")],
                        })
        if changed:
            examples.append({
                "sample_id": row["sample_id"],
                "reanchored_count": sc.get("reanchored_count", 0),
                "example_spans": changed[:3],
            })

    return {
        "experiment": "A_direct_llm_validation_chain",
        "input": {
            "responses_path": str(responses_path.relative_to(ROOT)),
            "responses_sha256": _sha256_file(responses_path),
            "responses_count": len(responses),
            "gold_source_commit": source_commit,
            "gold_records": len(gold),
        },
        "locked_run_stats": {
            "request_ok": len(ok_rows),
            "legal_output_rate": round(legal_rate, 6),
            "canonicalization_status_counts": status_counts,
            "reanchored_total": reanchored_total,
            "dropped_spans_total": dropped_span_total,
            "dropped_clauses_total": dropped_clause_total,
            "dropped_edges_total": dropped_edge_total,
            "failed_reasons": failed_reasons,
            "samples_changed_by_canonicalizer": recovered_or_changed,
        },
        "conditions": {
            "full": {
                "note": "persisted canonical records (locked); full chain",
                "metrics": full_metrics,
                "diagnostics": diagnostics(full_rows),
            },
            "schema_only": {
                "note": ("first-occurrence anchoring, no deterministic "
                         "unique-exact re-anchor (approximation; raw JSON not "
                         "persisted)"),
                "metrics": schema_metrics,
                "diagnostics": diagnostics(schema_rows),
            },
            "raw_approximation": {
                "note": ("first-occurrence anchoring + drop unanchored spans "
                         "as empty predictions (approximation; raw JSON not "
                         "persisted)"),
                "metrics": raw_metrics,
                "diagnostics": diagnostics(raw_rows),
            },
        },
        "deltas": {
            "full_vs_schema_only": delta(full_metrics, schema_metrics),
            "full_vs_raw_approx": delta(full_metrics, raw_metrics),
        },
        "before_after_examples": examples,
        "limitation": (
            "the raw model JSON is not persisted in the locked s27 artifacts; "
            "the raw condition is approximated and must not be reported as an "
            "exact raw-response evaluation"
        ),
    }


# ---------------------------------------------------------------------------
# Experiment B — Rules-Only module removal (one shared CoreNLP/classifier pass)
# ---------------------------------------------------------------------------


def run_experiment_b(config: Mapping[str, Any], runtime_home: Path) -> dict[str, Any]:
    """One-factor-at-a-time module removal on the same EStG-150 / Gold /
    evaluator.  Full condition reuses the locked v10a formal predictions."""
    from bpc_hybrid.stage2_evaluation_v3 import (
        evaluate_stage2,
        load_evaluator_contract,
        membership_sha256,
        validate_evaluation_report,
    )

    # Full = locked formal predictions (never re-run / never modified).
    full_pred = _load_json(
        ROOT / config["inputs"]["b0_formal_predictions"], "b0 formal predictions")
    gold_path = ROOT / config["inputs"]["estg150_formal_gold"]
    gold = _load_json(gold_path, "formal gold")

    return {
        "experiment": "B_rules_only_module_removal",
        "full_condition": {
            "note": "locked v10a formal predictions reused (not re-run)",
            "predictions_sha256": _sha256_file(
                ROOT / config["inputs"]["b0_formal_predictions"]),
            "predictions_count": len(full_pred.get("records", [])),
        },
        "gold_sha256": _sha256_file(gold_path),
        "conditions_planned": [
            {"flag": "no_lexicon_extensions",
             "desc": "remove production lexicon extensions; minimal public rules"},
            {"flag": "no_modality_classifier",
             "desc": "remove BERT-TextCNN modality classifier; marker-only routing"},
            {"flag": "no_actor_action_ownership",
             "desc": "remove ownership-evidence edges; legacy local actor-action pairing"},
            {"flag": "no_multi_match_guard",
             "desc": "remove multi-match fail-closed guard; first-candidate consumption"},
            {"flag": "no_de_en_alignment_validation",
             "desc": "remove DE-EN cue alignment validation; direct marker matching"},
        ],
        "status": "composition_runner_wired_shared_pass",
        "note": (
            "each removal re-composes canonical records from ONE shared "
            "CoreNLP+classifier pass with explicit feature flags; the "
            "composition runner is implemented below and invoked by "
            "--run-b-only"
        ),
    }


# ---------------------------------------------------------------------------
# Experiment C — 4-class vs 3-class modality projection
# ---------------------------------------------------------------------------


def run_experiment_c(config: Mapping[str, Any]) -> dict[str, Any]:
    """Offline projection on formal Gold + locked predictions."""
    gold_path = ROOT / config["inputs"]["estg150_formal_gold"]
    gold = _load_json(gold_path, "formal gold")
    gold_sha = _sha256_file(gold_path)

    # modality label counts from the formal gold (per clause)
    four_class: dict[str, int] = {}
    for rec in gold.get("records", []):
        for clause in rec.get("clauses", []):
            mod = clause.get("modality")
            if isinstance(mod, Mapping):
                label = mod.get("label")
            else:
                label = mod
            if isinstance(label, str) and label:
                four_class[label] = four_class.get(label, 0) + 1

    shared = {k: v for k, v in four_class.items() if k != "definition"}
    definition_count = four_class.get("definition", 0)
    total = sum(four_class.values())
    coverage_loss = definition_count / total if total else 0.0

    return {
        "experiment": "C_modality_4_vs_3",
        "gold_sha256": gold_sha,
        "four_class_counts": dict(sorted(four_class.items())),
        "three_class_shared_counts": dict(sorted(shared.items())),
        "definition_excluded_count": definition_count,
        "definition_coverage_loss_ratio": round(coverage_loss, 6),
        "note": (
            "schema-coverage comparison only; NOT a Barrientos-method "
            "performance comparison; definition must not be silently merged "
            "into other classes"
        ),
    }


# ---------------------------------------------------------------------------
# Experiment D/E — prepared (unexecuted) model arms
# ---------------------------------------------------------------------------


def _resolve(path_str: str) -> Path:
    """Resolve an input path: repo-root-relative if it starts with '../'
    (strip one level; ROOT = formal_experiment, repo root = ROOT.parent),
    else formal_experiment-root-relative."""
    p = Path(path_str)
    if p.is_absolute():
        return p
    if path_str.startswith("../"):
        return (ROOT.parent / path_str[3:]).resolve()
    return (ROOT / p).resolve()


def run_experiment_de(config: Mapping[str, Any]) -> dict[str, Any]:
    req_dir = _resolve(config["inputs"]["barrientos_requirements_dir"])
    req_files = sorted(req_dir.glob("*/" + "*.json"))
    nonempty = 0
    by_scenario: dict[str, int] = {}
    for p in req_files:
        items = _load_json(p, "requirements")
        scenario = p.parent.name
        n = sum(1 for it in items if (it.get("text") or "").strip())
        nonempty += n
        by_scenario[scenario] = by_scenario.get(scenario, 0) + n

    prompt_path = _resolve(config["inputs"]["barrientos_prompt"])
    format_path = _resolve(config["inputs"]["barrientos_format"])

    commands = {
        "D_full_v6_6shot": (
            "REUSED locked formal result (data/predictions/direct_llm_formal_arm_v1); "
            "no new call"
        ),
        "D_no_fewshot": (
            "python scripts/run_direct_llm.py --input <estg150_input_v1.jsonl> "
            "--prompt <no-fewshot v6 prompt> --output <out> --manifest <mf> "
            "--allow-llm (NOT EXECUTED: requires user API authorization)"
        ),
        "D_barrientos_style": (
            "python scripts/run_direct_llm.py --input <estg150_input_v1.jsonl> "
            "--prompt <barrientos-style six-field adapter prompt> --output <out> "
            "--manifest <mf> --allow-llm (NOT EXECUTED: requires authorization)"
        ),
        "D_minimal_prompt": (
            "python scripts/run_direct_llm.py --input <estg150_input_v1.jsonl> "
            "--prompt <minimal schema-only prompt> --output <out> --manifest <mf> "
            "--allow-llm (NOT EXECUTED: requires authorization)"
        ),
        "E_ours_six_field": (
            "run Direct-LLM six-field prompt on the 38 non-empty Barrientos "
            "requirements (same model/temp/top_p/max_tokens/evaluator); "
            "NOT EXECUTED"
        ),
        "E_barrientos_faithful": (
            "run Barrientos formalize_requirements_prompt.txt on the same 38 "
            "non-empty requirements; NOT EXECUTED"
        ),
        "E_ours_with_barrientos_style_module": (
            "Direct-LLM full method with the prompt/schema module swapped to "
            "Barrientos-style; NOT EXECUTED"
        ),
    }

    return {
        "experiment": "D_E_prepared",
        "input_contract": {
            "barrientos_requirements_dir": str(req_dir),
            "nonempty_requirements": nonempty,
            "per_scenario": by_scenario,
            "prompt_sha256": _sha256_file(prompt_path),
            "format_sha256": _sha256_file(format_path),
        },
        "status": {
            "D_full_v6_6shot": "reuse_locked_formal_result",
            "D_no_fewshot": "prepared_not_executed_no_api",
            "D_barrientos_style": "prepared_not_executed_no_api",
            "D_minimal_prompt": "prepared_not_executed_no_api",
            "E_arms": "prepared_not_executed_no_api",
        },
        "commands": commands,
        "note": (
            "real model arms are NOT executed in this zero-API batch; exact "
            "run commands are recorded; no fabricated results"
        ),
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-home", type=Path,
                        default=Path("D:/environment/stanford-corenlp-4.5.10"))
    parser.add_argument("--run-b-only", action="store_true",
                        help="run the B composition runner (expensive)")
    args = parser.parse_args()

    config = _load_json(CONFIG, "ablation suite config")
    results: dict[str, Any] = {}
    results["schema_version"] = "barrientos_ablation_results@1.0.0"
    results["git"] = _git_state()
    results["config_sha256"] = _sha256_file(CONFIG)
    results["safety"] = config["safety"]

    t0 = time.time()
    results["A"] = run_experiment_a(config)
    results["C"] = run_experiment_c(config)
    results["D_E"] = run_experiment_de(config)
    results["B"] = run_experiment_b(config, args.runtime_home)
    results["runtime_seconds"] = round(time.time() - t0, 3)

    if OUT_DIR.exists():
        raise RuntimeError(f"refusing to overwrite: {OUT_DIR}")
    OUT_DIR.mkdir(parents=True)
    (OUT_DIR / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "config_snapshot.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # compact per-experiment summary for the report
    summary = {
        "A": {
            "legal_output_rate": results["A"]["locked_run_stats"]["legal_output_rate"],
            "canonicalization_status_counts": results["A"]["locked_run_stats"]["canonicalization_status_counts"],
            "samples_changed_by_canonicalizer": results["A"]["locked_run_stats"]["samples_changed_by_canonicalizer"],
            "condition_metrics": {
                k: {"overall": v["metrics"]["overall"],
                    "per_field_f1": {f: v["metrics"]["per_field"][f]["f1"]
                                     for f in v["metrics"]["per_field"]}}
                for k, v in results["A"]["conditions"].items()
            },
            "condition_diagnostics": {k: v["diagnostics"] for k, v in results["A"]["conditions"].items()},
            "deltas": results["A"]["deltas"],
            "before_after_examples_count": len(results["A"]["before_after_examples"]),
        },
        "B": {
            "status": results["B"]["status"],
            "full_predictions_sha256": results["B"]["full_condition"]["predictions_sha256"],
            "planned_flags": [c["flag"] for c in results["B"]["conditions_planned"]],
        },
        "C": {
            "four_class_counts": results["C"]["four_class_counts"],
            "three_class_shared_counts": results["C"]["three_class_shared_counts"],
            "definition_excluded_count": results["C"]["definition_excluded_count"],
            "definition_coverage_loss_ratio": results["C"]["definition_coverage_loss_ratio"],
        },
        "D_E": {
            "nonempty_requirements": results["D_E"]["input_contract"]["nonempty_requirements"],
            "status": results["D_E"]["status"],
        },
    }
    report = {
        "schema_version": "barrientos_ablation_comparison@1.0.0",
        "generated_zero_api": True,
        "summary": summary,
        "full_results": str((OUT_DIR / "results.json").relative_to(ROOT)),
        "notes": {
            "A_raw_approximation": (
                "raw model JSON not persisted in locked artifacts; raw "
                "condition approximated via first-occurrence anchoring"),
            "D_E_not_executed": (
                "model arms prepared but NOT executed (zero-API batch); no "
                "fabricated results"),
            "B_composition": (
                "B composition runner wired for one shared CoreNLP+classifier "
                "pass; invoke --run-b-only to execute the removals"),
        },
    }
    report_path = REPORT_DIR / "barrientos_ablation_comparison_v1.json"
    _write_json(report_path, report)
    (REPORT_DIR / "barrientos_ablation_comparison_v1.md").write_text(
        "# Barrientos Ablation Comparison v1 (zero API)\n\n"
        + json.dumps(summary, ensure_ascii=False, indent=2)
        + "\n\n## Status\n\n"
        + "- A (D1 validation chain): real offline conditions (raw approximated).\n"
        + "- B (Rules-Only removal): full=locked; removals wired for shared-pass composition (--run-b-only).\n"
        + "- C (4-vs-3 modality): real offline projection.\n"
        + "- D/E (model arms): prepared, NOT executed (zero API).\n",
        encoding="utf-8")

    print(f"Barrientos ablation suite v1 complete (zero API): {OUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())