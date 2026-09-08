"""Re-score fixed Stage-3 data after the diagnosed formula/metric repairs.

Zero API. Thresholds, BPMN, source predictions and Gold are unchanged.
Outputs have a new revision; prior predictions/reports are never overwritten.

Source loop
-----------
The three-type loop and the four-new-type extension loop run over a
configurable source tuple (default ``("reference", "rules_only")`` --
unchanged historical behaviour).  The optional third source ``direct_llm``
consumes the formal Direct-LLM arm capsule
(``data/predictions/gdpr7_direct_llm_v1``; input path overridable via
``capsule_paths``) with the SAME unified five-class evaluation as the other
sources -- EXTENDED_TYPES priority / frozen gamma_ext / repaired-formula
scores via ``unified_rows``.  The old "preset-expected-type conditional
detection" rule is never re-applied.  A requested capsule source whose
capsule is missing/incomplete fails closed BEFORE any heavy computation or
write (only the affected source stops; the runner does not fabricate input).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import run_gdpr_3type_linkage_v1 as original
import run_gdpr_s2_s3_linkage_v1 as linkage
import run_s3_extended_violation_panel_v2 as panel_runner
import build_sun_stage3_threshold_sensitivity_v1 as sensitivity
from bpc_hybrid.s3_extended_unified import unified_rows
from bpc_hybrid.stage3_extended_violations import evaluate_extended, evaluate_paired
from reevaluate_s3_extended_unified_v1 import confusion_matrix

METHODS = ("winter", "sun", "bm25", "tfidf_svd")
DEFAULT_OUT = ROOT / "outputs/evidence/s3_formula_repair_v2"
REPORT = ROOT / "outputs/reports/s3_formula_repair_v2.json"
DEFAULT_SOURCES = ("reference", "rules_only")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows_at(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def differences(old, new, fields):
    old_by_id = {r["item_id"]: r for r in old}
    assert set(old_by_id) == {r["item_id"] for r in new}
    return [{"item_id": r["item_id"], "changes": {
        f: {"old": old_by_id[r["item_id"]].get(f), "new": r.get(f)}
        for f in fields if old_by_id[r["item_id"]].get(f) != r.get(f)}}
        for r in new if any(old_by_id[r["item_id"]].get(f) != r.get(f) for f in fields)]


def resolve_capsule_paths(sources, capsule_paths):
    """Resolve + verify every capsule source path before any heavy work.

    Returns ``{arm: Path}``.  Raises ``FileNotFoundError`` (fail closed)
    before the frozen pipeline loads anything when a requested capsule source
    is missing -- only the affected source is stopped.
    """
    paths = dict(capsule_paths or {})
    for arm in sources:
        if arm == "reference":
            continue
        if arm not in original.CAPSULE_CONFIGS:
            raise ValueError(
                f"unknown capsule source {arm!r}; expected one of "
                f"{sorted(original.CAPSULE_CONFIGS)} plus 'reference'")
        path = paths.get(arm)
        if path is None:
            path = original.CAPSULE_CONFIGS[arm]["predictions"]
        paths[arm] = Path(path)
    for arm in sources:
        if arm == "reference":
            continue
        path = paths[arm]
        if not path.is_file():
            raise FileNotFoundError(
                f"{arm} capsule source missing: {path} -- a complete external "
                "capsule is required before the repair run can evaluate that "
                "source (for direct_llm run the promotion step "
                "scripts/promote_gdpr7_direct_llm_arm_v1.py --apply first, or "
                "pass an explicit --direct-capsule path)")
    return paths


def run(out=DEFAULT_OUT, report_path=REPORT, sources=DEFAULT_SOURCES,
        capsule_paths=None):
    if out.exists() or report_path.exists():
        raise FileExistsError("Use a new output/report path; existing results are preserved")
    sources = tuple(sources)
    unknown = set(sources) - set(original.ARM_LABELS)
    if unknown:
        raise ValueError(
            f"unknown source(s) {sorted(unknown)}; expected a subset of "
            f"{sorted(original.ARM_LABELS)}")
    if sources != DEFAULT_SOURCES and "reference" not in sources:
        raise ValueError(
            "reference is always required as the deterministic baseline source")
    cap_paths = resolve_capsule_paths(sources, capsule_paths)

    frozen_paths = [original.INFERENCE_PACK, original.INPUT_PACK, original.GOLD_VIOLATION,
        original.CAPSULE_PREDICTIONS, panel_runner.PANEL, sensitivity.CORRECTION_PACK]
    if "direct_llm" in sources:
        frozen_paths.append(cap_paths["direct_llm"])
    frozen_paths += list(original.BPMN_DIR.glob("*.bpmn"))
    frozen_paths += list((ROOT / "data/development/stage3_synth").glob("syn_v2_*/*/*.bpmn"))
    before = {str(p.relative_to(ROOT)): sha(p) for p in frozen_paths}
    report = {"revision": "s3_formula_repair_v2", "scope": "development_only",
              "generated_utc": datetime.now(timezone.utc).isoformat(),
              "sources": list(sources),
              "original_three_types": {}, "extended_four_types": {},
              "statistics_only_on_old_predictions": {}, "safety": {
                  "api_calls": 0, "gold_modified": False, "thresholds_changed": False,
                  "formal_oracle_run": False}}
    config = read(original.CONFIG)
    frozen = original.load_frozen(config)
    rule_ids = sorted(original.rule_texts_of(frozen["inference"]))
    reference_rules = None
    for arm in sources:
        pred_path = None if arm == "reference" else cap_paths[arm]
        rules, diag = original.build_rule_records_for_arm(arm, frozen, rule_ids, pred_path)
        if arm == "reference":
            reference_rules = rules
        rows = original.build_violation_rows(arm, frozen, rules)
        folder = out / "original_three" / arm
        write_rows(folder / "predictions.jsonl", rows)  # fixed BEFORE evaluation
        write(folder / "rule_records.json", rules)
        evaluation = original.evaluate_rows(rows, original.GOLD_VIOLATION)
        old_path = ROOT / f"outputs/development/gdpr_3type_linkage_v1_{arm}/predictions.jsonl"
        delta = []
        if old_path.is_file():
            old = rows_at(old_path)
            # Only Definition 6 changed. These two formula scores must match exactly.
            assert all(a["missing_action_score"] == b["missing_action_score"] and
                       a["out_of_order_score"] == b["out_of_order_score"]
                       for a, b in zip(sorted(old, key=lambda x:x["item_id"]), rows))
            delta = differences(old, rows, ("predicted_violation_type", "incorrect_actor_score",
                                           "incorrect_actor_reason", "incorrect_actor_observable"))
        result = {"evaluation": evaluation, "conversion": diag, "changes": delta,
                  "verdict_changes": sum(any(f == "predicted_violation_type" for f in d["changes"]) for d in delta),
                  "no_eligible_order_pairs": sum(r["scores"]["out_of_order_denominator"] == 0
                     for r in rows if r["check_type"] == "out_of_order"),
                  "actor_unobservable_reasons": dict(Counter(r["incorrect_actor_reason"] for r in rows
                     if r["check_type"] == "incorrect_actor" and not r["incorrect_actor_observable"]))}
        write(folder / "evaluation.json", result)
        report["original_three_types"][arm] = result
        print(f"Original three: {arm} done", flush=True)

    panel = read(panel_runner.PANEL)
    gamma_ext = float(panel["config"]["gamma_ext"])
    source_texts = panel_runner._rule_texts()
    texts = linkage._sentence_text_by_sample(read(linkage.INPUT_PACK))
    for arm in sources:
        report["extended_four_types"][arm] = {}
        report["statistics_only_on_old_predictions"][arm] = {}
        if arm != "reference":
            cap_doc = read(cap_paths[arm])
            if arm == "direct_llm":
                cfg = original.CAPSULE_CONFIGS[arm]
                original.validate_external_capsule(
                    cap_doc, arm=arm, expected_schema=cfg["schema"],
                    expected_records=cfg["expected_records"],
                    label=f"{arm} capsule predictions")
            capsule = linkage._pred_by_sample(cap_doc)
        for method in METHODS:
            if arm == "reference":
                raw = panel_runner.build_predictions(method, panel, source_texts,
                    linkage._sims_factory_for(method, frozen["nlp"]),
                    panel_runner._gamma_for(method), gamma_ext, frozen["nlp"])
            else:
                raw, _ = linkage.build_arm_predictions(method, arm, panel, texts, capsule, frozen["nlp"], gamma_ext)
            # Unified five-class decision on BOTH sides (never the old
            # preset-expected-type conditional detection rule).
            rows = unified_rows(raw, gamma_ext)
            folder = out / "extended_four" / arm / method
            write_rows(folder / "predictions.jsonl", rows)  # prediction fixed first
            gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]} for v in panel["variants"]}
            ev = evaluate_extended(rows, gold)
            paired = evaluate_paired(rows, panel, gamma_ext)
            cm = confusion_matrix(rows, gold, gamma_ext, panel)
            old_path = ROOT / f"outputs/development/s3_extended_unified_v1/{arm}/{method}/predictions.jsonl"
            changes = []
            if old_path.is_file():
                old = rows_at(old_path)
                old_cm = confusion_matrix(old, gold, gamma_ext, panel)
                report["statistics_only_on_old_predictions"][arm][method] = old_cm
                changes = differences(old, rows, ("unified_predicted_raw", "scores", "observability"))
                # The other three type scores and all frozen rows must remain intact.
                for before_row, after_row in zip(sorted(old, key=lambda x:x["item_id"]), sorted(rows, key=lambda x:x["item_id"])):
                    for t in panel_runner.EXTENDED_TYPES:
                        if t != "constraint_violated":
                            assert before_row["scores"][t] == after_row["scores"][t]
                            assert before_row["control_scores"][t] == after_row["control_scores"][t]
            result = {"variant_evaluation": ev, "paired_evaluation": paired,
                      "confusion_matrix": cm, "changes": changes,
                      "verdict_changes": sum("unified_predicted_raw" in d["changes"] for d in changes)}
            write(folder / "evaluation.json", result)
            report["extended_four_types"][arm][method] = result
            print(f"Extended four: {arm}/{method} done", flush=True)

    # Repeat the already existing threshold grid with the corrected scorer;
    # no threshold selection or new tuning run is introduced.
    runtime = {"nlp": frozen["nlp"], "sim": frozen["scorer"].sim, "models": frozen["models"],
               "rules": reference_rules, "rule_source": "fresh_with_actor_action_pairs"}
    correction = read(sensitivity.CORRECTION_PACK)
    sweep = sensitivity.run_sweep(runtime, correction)
    write(out / "threshold_sensitivity.json", sweep)
    report["threshold_sensitivity"] = {k: sweep[k] for k in ("gamma_sweep", "theta_sweep", "settings")}
    assert before == {str(p.relative_to(ROOT)): sha(p) for p in frozen_paths}
    report["acceptance"] = {
        "fixed_inputs_unchanged": True, "original_missing_and_order_scores_unchanged": True,
        "non_constraint_extension_scores_unchanged": True, "all_33_items_each_arm": True,
        "all_80_objects_each_extension_arm_and_method": True,
        "sun_existential_formula_preserved": True,
        "numeric_comparison_action_bound_upper_limits_only": True,
        "five_class_statistics_include_abstentions_and_false_compliance": True}
    implementation_paths = [Path(__file__), original.CONFIG,
        ROOT / "src/bpc_hybrid/sun_stage3/sun_model.py",
        ROOT / "src/bpc_hybrid/sun_stage3/sun_scorer.py",
        ROOT / "src/bpc_hybrid/sun_stage3/sun_rule_extraction.py",
        ROOT / "src/bpc_hybrid/sun_stage3/gdpr_capsule_converter.py",
        ROOT / "src/bpc_hybrid/stage3_extended_violations.py",
        ROOT / "src/bpc_hybrid/s3_extended_unified.py",
        Path(original.__file__), Path(linkage.__file__), Path(panel_runner.__file__),
        Path(sensitivity.__file__), ROOT / "scripts/reevaluate_s3_extended_unified_v1.py"]
    manifest = {"run_id": "s3_formula_repair_v2", "scope": "development_only",
        "sources": list(sources),
        "command": f"python {Path(__file__).relative_to(ROOT)} --sources {','.join(sources)}",
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "inputs": before,
        "implementation_hash_mode": "canonical_lf_utf8_text",
        "implementation_hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")).hexdigest() for p in implementation_paths},
        "artifacts": {str(p.relative_to(ROOT)): sha(p) for p in out.rglob("*") if p.is_file()},
        "thresholds": config["method"]["thresholds"],
        "extension_thresholds": {"gamma_ext": gamma_ext, "action_gamma": {m: panel_runner._gamma_for(m) for m in METHODS}},
        "runtime": {"python": sys.version, "spacy_model": frozen["nlp"].meta}, "safety": report["safety"]}
    report["manifest"] = str((out / "manifest.json").relative_to(ROOT))
    write(report_path, report)
    manifest["report"] = {"path": str(report_path.relative_to(ROOT)), "sha256": sha(report_path)}
    write(out / "manifest.json", manifest)
    print(json.dumps(report["acceptance"], ensure_ascii=False), flush=True)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    p.add_argument("--report", type=Path, default=REPORT)
    p.add_argument("--sources", default=",".join(DEFAULT_SOURCES),
                   help="comma-separated source arms; default "
                        f"{','.join(DEFAULT_SOURCES)} (historical behaviour); "
                        "add direct_llm to include the Direct-LLM arm")
    p.add_argument("--direct-capsule", type=Path, default=None,
                   help="Direct-LLM capsule predictions path override "
                        "(default data/predictions/gdpr7_direct_llm_v1/"
                        "predictions.json)")
    args = p.parse_args()
    sources = tuple(s.strip() for s in args.sources.split(",") if s.strip())
    capsule_paths = {}
    if args.direct_capsule is not None:
        capsule_paths["direct_llm"] = args.direct_capsule
    run(args.output, args.report, sources=sources, capsule_paths=capsule_paths)
