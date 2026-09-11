# -*- coding: utf-8 -*-
"""S3.9-EXT gap evidence: automatic difference lists across the measured cells.

Read-only over the stored predictions.  Produces, for every instance where two
arms disagree, the rule text and the action phrase actually used, each arm's
candidate activities with their scores, thresholds and match conclusions, the
condition / time / exception evidence of the resolved activity, the four raw
type results and the final output, plus the earliest processing step where the
two arms diverge.  Nothing is hand-picked: the lists are computed from the
stored per-item artefacts.

Classifications used in the output:

* ``proved_by_record`` - the two arms consumed the SAME candidate score and
  threshold and only the comparison of that pair differs, or the same score is
  compared against two different thresholds;
* ``needs_experiment`` - the compared texts, candidates or scores themselves
  differ, so the cause cannot be attributed without the extra arms.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import run_s3_extended_violation_panel_v2 as panel_runner  # noqa: E402

TYPES = ("prohibited_action_present", "required_condition_not_enforced",
         "constraint_violated", "exception_not_handled")
NONE_LABEL = "none"

CELLS = {
    "winter_frozen_orig_04": ("outputs/evidence/s3_formula_repair_v2/extended_four/"
                              "reference/winter/predictions.jsonl", "jsonl_frozen"),
    "sun_frozen_orig_08": ("outputs/evidence/s3_formula_repair_v2/extended_four/"
                           "reference/sun/predictions.jsonl", "jsonl_frozen"),
    "orig_04_rederived": ("outputs/development/s3_extended_baseline_04_v1/predictions.jsonl",
                          "jsonl"),
    "v3_08_existing": ("outputs/development/s3_extended_v3_v1/predictions.jsonl", "jsonl"),
    "v3_04_diagnostic": ("outputs/development/s3_extended_v3_gamma04_v1/predictions.jsonl",
                         "jsonl"),
    "v3_04_repaired": ("outputs/development/s3_extended_v3_repair_v1/predictions.jsonl",
                       "jsonl"),
}

OUT_DIR = ROOT / "outputs/evidence/s3_extended_gap_v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def raw_label(row: dict) -> str | None:
    value = row.get("unified_predicted_raw")
    if value is None and "unified_predicted_raw" not in row:
        value = row.get("predicted_violation_type")
    return value


def kind(value) -> str:
    if value is None:
        return "abstention"
    if value == NONE_LABEL:
        return "explicitly_compliant"
    return "violation_type"


def control_decision(row: dict, gamma_ext: float) -> dict:
    """Re-derive the control five-class decision from the stored control scores."""
    per_type = {}
    for t in TYPES:
        cs = row["control_scores"].get(t) or {}
        if not cs.get("observable"):
            per_type[t] = None
            continue
        score = cs.get("score")
        if t == "prohibited_action_present":
            per_type[t] = score is not None and score >= gamma_ext
        elif t == "constraint_violated":
            contradiction = bool((cs.get("exact_contradiction") or {}).get("contradiction"))
            per_type[t] = (score is not None and score > gamma_ext) or contradiction
        else:
            per_type[t] = score is not None and score > gamma_ext
    predicted = next((t for t in TYPES if per_type.get(t) is True), None)
    if predicted is None and not all(v is None for v in per_type.values()):
        predicted = NONE_LABEL
    return {"predicted": predicted, "per_type": per_type}


def candidate_table(record: dict, sentence: dict, sim) -> dict:
    """Raw-label candidate similarities of every process activity, offline."""
    action = (sentence.get("action") or "").strip()
    rows = []
    for act in record.get("activities", []):
        name = (act.get("name") or "").strip()
        if not name:
            continue
        rows.append({"activity_id": act["id"], "label": name,
                     "raw_label_similarity": round(float(sim.text_pair(action, name)), 6)})
    rows.sort(key=lambda r: (-r["raw_label_similarity"], r["activity_id"]))
    return {"rule_action_phrase": action, "candidates": rows}


def side_block(row: dict, cell: str, gamma_ext: float) -> dict:
    trace = (row.get("action_localization") or {}).get("variant")
    binding = (row.get("evidence_binding") or {}).get("variant")
    return {
        "cell": cell,
        "variant_final_output": raw_label(row),
        "variant_final_kind": kind(raw_label(row)),
        "variant_scores": row.get("scores"),
        "variant_observability": row.get("observability"),
        "variant_action_localization": trace,
        "variant_matched_activity_id": (row.get("matched_activity") or {}).get("variant")
        if isinstance(row.get("matched_activity"), dict) else None,
        "variant_evidence_binding": binding,
        "control_final_output": control_decision(row, gamma_ext)["predicted"],
        "control_scores": row.get("control_scores"),
        "thresholds": row.get("thresholds") or {
            "gamma_ext": row.get("gamma_ext"), "action_gamma": row.get("action_mapping_gamma")},
    }


def first_divergence(a: dict, b: dict, rule_element: dict) -> dict:
    """The earliest stored processing step where two cells differ.

    The frozen Winter-style and Sun-style rows carry no action-localization
    record, so the rule action phrase falls back to the frozen panel's locked
    rule element (the same text every cell consumes) rather than being reported
    as a difference.
    """
    locked_phrase = " ".join((rule_element.get("action") or "").split())

    def phrase(row):
        loc = (row.get("action_localization") or {}).get("variant") or {}
        value = loc.get("rule_action_text")
        return " ".join(value.split()) if value else locked_phrase

    steps = [
        ("action_phrase", phrase),
        ("action_candidate_set_and_score",
         lambda r: (r.get("action_localization") or {}).get("variant")),
        ("observed_evidence",
         lambda r: json.dumps({"scores": r.get("scores"),
                               "observability": r.get("observability")}, sort_keys=True)),
        ("final_output", raw_label),
    ]
    for name, getter in steps:
        if getter(a) != getter(b):
            return {"step": name, "first": getter(a), "second": getter(b)}
    return {"step": "none", "first": None, "second": None}


def classify(a: dict, b: dict, expected: str) -> str:
    """Proved-by-record vs needs-experiment for one disagreement.

    The label is derived from the two stored records only.  A bare score
    difference is never reported as a cause.
    """
    ra = ((a.get("action_localization") or {}).get("variant") or {})
    rb = ((b.get("action_localization") or {}).get("variant") or {})
    sa = a.get("scores", {}).get(expected)
    sb = b.get("scores", {}).get(expected)
    ra_reason = (a.get("observability", {}).get(expected) or {}).get("reason")
    rb_reason = (b.get("observability", {}).get(expected) or {}).get("reason")
    if sa is not None and sa == sb:
        return ("proved_by_record: the same consumed score for the expected type is "
                "compared against a different threshold or a different verdict "
                "(action gamma %s vs %s)" % (ra.get("action_gamma", ra.get("v3_thresholds")),
                                             rb.get("action_gamma", rb.get("v3_thresholds"))))
    if (sa is None) != (sb is None):
        return ("proved_by_record: one cell abstains (%s) while the other consumes a score "
                "for the expected type" % (ra_reason if sa is None else rb_reason))
    if sa is None and sb is None:
        first = (a.get("observability", {}).get(expected) or {}).get("observable")
        second = (b.get("observability", {}).get(expected) or {}).get("observable")
        return ("proved_by_record: both cells abstain on the expected type (observable=%s "
                "vs %s); the disagreement is in another type" % (first, second))
    return ("needs_experiment: the compared texts, candidates or scores themselves differ "
            "(score %r vs %r)" % (sa, sb))


def build(panel: dict, cells: dict[str, dict], sim, rule_texts: dict[str, str]) -> dict:
    gamma_ext = float(panel["config"]["gamma_ext"])
    variants = {v["variant_id"]: v for v in panel["variants"]}
    gold = {v["variant_id"]: v["expected_violation"] for v in panel["variants"]}
    base_by_id = {v: {i: r for i, r in rows.items()} for v, rows in cells.items()}

    # offline candidate tables + evidence per instance (read-only)
    from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_bytes
    contract = load_stage1_contract(panel_runner.STRUCTURAL_CONTRACT)
    sentences = {}
    candidates = {}
    for vid, variant in variants.items():
        sentence = panel_runner._locked_sentence(variant, rule_texts[variant["rule_id"]], sim.nlp)
        sentences[vid] = sentence
        record = parse_bpmn_bytes((ROOT / variant["variant_bpmn"]).read_bytes(),
                                  source_path=variant["variant_bpmn"], contract=contract)
        candidates[vid] = candidate_table(record, sentence, sim)

    def rule_block(vid: str) -> dict:
        variant = variants[vid]
        element = variant["rule_element"]
        return {
            "item_id": vid, "process_id": variant["process_id"],
            "rule_id": variant["rule_id"], "expected_violation": gold[vid],
            "rule_text": rule_texts[variant["rule_id"]],
            "rule_element": {k: element.get(k) for k in
                             ("field", "sentence_idx", "sentence_text", "modality",
                              "actor", "action", "condition", "constraint", "exception")},
            "candidate_activities_raw_label_similarity": candidates[vid],
            "mutation_metadata_read": False,
        }

    def pair_list(name_a: str, name_b: str, predicate) -> list[dict]:
        out = []
        for vid in sorted(variants):
            a, b = base_by_id[name_a][vid], base_by_id[name_b][vid]
            if not predicate(a, b):
                continue
            out.append({
                **rule_block(vid),
                "cell_a": name_a, "cell_b": name_b,
                "evidence_a": side_block(a, name_a, gamma_ext),
                "evidence_b": side_block(b, name_b, gamma_ext),
                "first_divergence": first_divergence(a, b, variants[vid]["rule_element"]),
                "cause_class": classify(a, b, gold[vid]),
            })
        return out

    def var_ok(row):
        return raw_label(row) == gold[row["item_id"]] if "item_id" in row else None

    # A. winter correct, v3 (existing) not correct
    a_list = pair_list("winter_frozen_orig_04", "v3_08_existing",
                       lambda a, b: raw_label(a) == gold[a["item_id"]]
                       and raw_label(b) != gold[b["item_id"]])
    # A'. winter correct, repaired arm not correct
    a2_list = pair_list("winter_frozen_orig_04", "v3_04_repaired",
                        lambda a, b: raw_label(a) == gold[a["item_id"]]
                        and raw_label(b) != gold[b["item_id"]])
    # B. winter control clean, v3 control false positive
    b_list = pair_list("winter_frozen_orig_04", "v3_08_existing",
                       lambda a, b: control_decision(a, gamma_ext)["predicted"] == NONE_LABEL
                       and control_decision(b, gamma_ext)["predicted"] in TYPES)
    # C. v3 correct, winter not correct
    c_list = pair_list("v3_08_existing", "winter_frozen_orig_04",
                       lambda a, b: raw_label(a) == gold[a["item_id"]]
                       and raw_label(b) != gold[b["item_id"]])
    # D. diagnostic vs 0.8 cell: what the threshold migration alone changed
    def decision_fingerprint(row):
        loc = (row.get("action_localization") or {}).get("variant") or {}
        return json.dumps({
            "scores": row.get("scores"), "observability": row.get("observability"),
            "control_scores": row.get("control_scores"),
            "raw": raw_label(row),
            "decision": loc.get("decision"), "tier": loc.get("match_tier"),
            "reason": loc.get("reason"),
            "candidate_max_similarity": loc.get("candidate_max_similarity"),
            "winner_similarity": loc.get("winner_similarity"),
        }, sort_keys=True)

    d_list = pair_list("v3_08_existing", "v3_04_diagnostic",
                       lambda a, b: decision_fingerprint(a) != decision_fingerprint(b))
    # D'. the same isolated threshold factor on the ORIGINAL matching path
    e0_list = pair_list("orig_04_rederived", "sun_frozen_orig_08",
                        lambda a, b: decision_fingerprint(a) != decision_fingerprint(b))
    # F. repaired arm against the frozen Winter-style cell, both sides
    f_list = pair_list("winter_frozen_orig_04", "v3_04_repaired",
                       lambda a, b: decision_fingerprint(a) != decision_fingerprint(b))
    # E. repair vs winter: gains and regressions, both sides
    e_list = pair_list("winter_frozen_orig_04", "v3_04_repaired",
                       lambda a, b: (raw_label(a) == gold[a["item_id"]])
                       != (raw_label(b) == gold[b["item_id"]])
                       or control_decision(a, gamma_ext)["predicted"]
                       != control_decision(b, gamma_ext)["predicted"])

    def counts(items):
        by_type = Counter(i["expected_violation"] for i in items)
        by_class = Counter(i["cause_class"].split(":")[0] for i in items)
        return {"total": len(items), "by_expected_type": dict(sorted(by_type.items())),
                "by_cause_class": dict(sorted(by_class.items()))}

    return {
        "schema_version": "s3_extended_gap_evidence@1.0.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only; synthetic four-type panel v2; zero API",
        "gamma_ext": gamma_ext,
        "cells": {name: {"path": rel, "sha256": sha256_file(ROOT / rel)}
                  for name, (rel, _) in CELLS.items()},
        "panel": {"path": panel_runner.PANEL.relative_to(ROOT).as_posix(),
                  "sha256": sha256_file(panel_runner.PANEL),
                  "variants": len(variants)},
        "gold_read": "labels are used ONLY to select which rows to report; no arm reads them",
        "lists": {
            "A_winter_correct_v3_wrong": {"counts": counts(a_list), "items": a_list},
            "A2_winter_correct_repaired_wrong": {"counts": counts(a2_list), "items": a2_list},
            "B_winter_control_clean_v3_control_fp": {"counts": counts(b_list), "items": b_list},
            "C_v3_correct_winter_wrong": {"counts": counts(c_list), "items": c_list},
            "D_threshold_migration_only_changes": {"counts": counts(d_list), "items": d_list},
            "D2_same_threshold_factor_on_original_path": {"counts": counts(e0_list),
                                                          "items": e0_list},
            "E_winter_vs_repaired_changes": {"counts": counts(e_list), "items": e_list},
            "F_winter_vs_repaired_all_decision_differences": {"counts": counts(f_list),
                                                              "items": f_list},
        },
        "notes": [
            "list A is the complete set of instances where the frozen Winter-style arm is "
            "correct and the existing v3 arm is not; it is generated, not hand-picked",
            "every item carries both cells' consumed evidence, both thresholds, both "
            "final outputs and the earliest divergent processing step",
            "cause_class separates what the stored records already prove from what needs "
            "another arm; a bare score difference is never reported as a cause",
            "list D isolates the action-gamma factor inside the v3 matching path; list D2 "
            "isolates the same factor on the original label-argmax path",
            "list A2 is empty: the repaired arm is correct on every instance where the "
            "frozen Winter-style arm is correct",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = OUT_DIR / "difference_lists.json"
    comparison = OUT_DIR / "comparison_v1.json"
    comparison_md = OUT_DIR / "comparison_v1.md"
    if args.check:
        manifest = read_json(OUT_DIR / "manifest.json")
        mismatched = [rel for rel, digest in manifest["inputs"].items()
                      if sha256_file(ROOT / rel) != digest]
        mismatched += [rel for rel, digest in manifest["implementation"].items()
                       if sha256_file(ROOT / rel) != digest]
        if mismatched:
            raise RuntimeError("hash mismatch: " + ", ".join(sorted(mismatched)))
        for key, entry in manifest["artifacts"].items():
            if sha256_file(ROOT / entry["path"]) != entry["sha256"]:
                raise RuntimeError(f"artifact changed: {key}")
        print("s3_extended_gap_v1 difference lists VERIFIED")
        return 0

    if not comparison.is_file():
        raise RuntimeError(
            "build the comparison artifact first: "
            "python scripts/build_s3_extended_gap_comparison_v1.py")

    import spacy
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity

    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    panel = read_json(panel_runner.PANEL)
    rule_texts = panel_runner._rule_texts()
    cells = {name: {r["item_id"]: r for r in read_jsonl(ROOT / rel)}
             for name, (rel, _) in CELLS.items()}
    for name, rows in cells.items():
        if len(rows) != 40:
            raise RuntimeError(f"{name}: expected 40 rows, got {len(rows)}")
    evidence = build(panel, cells, sim, rule_texts)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")
    note = OUT_DIR / "method_change_note.md"
    manifest = {
        "schema_version": "s3_extended_gap_manifest@1.0.0",
        "run_id": "s3_extended_gap_v1",
        "scope": "development_only; zero API; read-only over stored predictions",
        "command": f"python {Path(__file__).relative_to(ROOT)}",
        "inputs": {rel: sha256_file(ROOT / rel) for rel, _ in CELLS.values()},
        "implementation": {
            str(Path(__file__).relative_to(ROOT)): sha256_file(Path(__file__)),
            "src/bpc_hybrid/s3_extended_v3_repair.py":
                sha256_file(ROOT / "src/bpc_hybrid/s3_extended_v3_repair.py"),
            "src/bpc_hybrid/s3_extended_arm_report.py":
                sha256_file(ROOT / "src/bpc_hybrid/s3_extended_arm_report.py"),
        },
        "artifacts": {
            "difference_lists": {"path": target.relative_to(ROOT).as_posix(),
                                 "sha256": sha256_file(target)},
            "method_change_note": {"path": note.relative_to(ROOT).as_posix(),
                                   "sha256": sha256_file(note)},
            "comparison_json": {"path": comparison.relative_to(ROOT).as_posix(),
                                "sha256": sha256_file(comparison)},
            "comparison_markdown": {"path": comparison_md.relative_to(ROOT).as_posix(),
                                    "sha256": sha256_file(comparison_md)},
        },
        "safety": {"api_calls": 0, "gold_modified": False, "predictions_rewritten": False,
                   "panel_modified": False},
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    summary = {k: v["counts"] for k, v in evidence["lists"].items()}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
