# -*- coding: utf-8 -*-
"""Run the four existing Stage 3 similarity backends on the S3.9-EXT
development-only synthetic panel v2 (40 variants, four NEW violation types;
zero API, zero LLM).

Panel: ``data/development/stage3_synth/synthetic_controlled_error_extension_v2.json``
(locked before any method ran; ``--check`` replay-verifies).  Each variant has
a synthetic compliant CONTROL and one mutated VARIANT; only variants are
evaluated (control scores are recorded as diagnostics).

Per method, the SAME new-type formulas (``stage3_extended_violations.py``) run
with that method's OWN frozen similarity backend:

* Winter-style extension  (``winter_2020`` backend: WinterSimilarity/spaCy,
  gamma 0.4)   — the Winter et al. (2020) paper defines no such violation
  types; this is a project extension of the Winter backend.
* Sun-style extension     (Sun reconstruction dev backend: WinterSimilarity/
  spaCy, gamma 0.8) — the Sun et al. (2024) paper defines no such violation
  types; this is a project extension of the Sun development backend.
* BM25 extension          (S3.6-A v3 candidate-specific BM25, gamma 0.8).
* TF-IDF/SVD extension    (S3.6-B dense baseline, gamma 0.5, frozen fit corpus).

The shared evaluator ``evaluate_extended`` computes per-type P/R/F1, macro/
micro F1, exact type accuracy and unobservable counts for ALL four methods
(one evaluator; unobservable items keep predicted=None and count as FN in the
primary denominators; never hard-filled 0/1).

Outputs: per-method runs under ``outputs/development/s3_extended_violation_panel_v2_<method>/``
and the combined comparison under ``outputs/reports/s3_extended_violation_comparison_v2.json``
+ ``.md`` (synthetic only; NOT human Gold, NOT the formal Oracle).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import spacy  # noqa: E402

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_bytes,
)
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES,
    ExtendedViolationScorer,
    action_candidates,
    condition_candidates,
    constraint_candidates,
    evaluate_extended,
    exception_candidates,
    extract_six_element_sentences,
    sentence_matches_locked,
)
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
INFERENCE_PACK = ROOT / "data/development/human_review/stage3_gold_inference_v1.json"
BPMN_DIR = ROOT / "data/input/stage1_stage3/gdpr7"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
EXTENSION_CONFIG = ROOT / "configs/stage3_extended_violation_v2.json"
V1_COMPARE = ROOT / "outputs/development/s39_synthetic_panel_compare_v1/comparison.json"

OUT_ROOT = ROOT / "outputs/development"
REPORT_ROOT = ROOT / "outputs/reports"

WINTER_CONFIG = ROOT / "configs/winter_stage3_development_v1.json"
SUN_CONFIG = ROOT / "configs/sun_stage3_development_v1.json"
BM25_CONFIG = ROOT / "configs/bm25_stage3_development_v3.json"
TFIDF_CONFIG = ROOT / "configs/tfidf_svd_stage3_development_v1.json"

METHOD_IDS = {
    "winter": "winter_style_extension",
    "sun": "sun_style_extension",
    "bm25": "bm25_extension",
    "tfidf_svd": "tfidf_svd_extension",
}
METHOD_DISPLAY = {
    "winter": "Winter-style extension",
    "sun": "Sun-style extension",
    "bm25": "BM25 extension",
    "tfidf_svd": "TF-IDF/SVD extension",
}
SELECTION_RATIONALE = {
    "research_gap": (
        "The original Stage 3 taxonomy checks whether a required action is "
        "present, assigned to the correct actor, and ordered correctly. It "
        "does not consume four other parts of the six-element Rule Record: "
        "prohibition modality, condition, constraint, and exception. The "
        "extension therefore adds one operational violation family for each "
        "uncovered part instead of adding arbitrary labels."
    ),
    "selection_principles": [
        "field coverage: each new type gives an existing Stage 2 field a distinct Stage 3 consumer",
        "semantic non-redundancy: each type can occur even when action presence, actor, and order are all correct",
        "controlled testability: each type permits a single targeted BPMN mutation with the other activity, actor, label, and order properties held fixed",
        "BPMN observability: each type has an explicit process-model surface, while absent surfaces are reported as unobservable rather than fabricated",
    ],
    "type_reasons": {
        "prohibited_action_present": "Complements missing_action by covering commission rather than omission: a process may contain every required task yet still perform an action that the rule explicitly prohibits. It makes prohibition modality and action jointly usable downstream.",
        "required_condition_not_enforced": "Covers conditional applicability: the correct action, actor, and order are insufficient when the BPMN does not enforce the condition under which the action is permitted or required. It connects the condition field to gateways, condition expressions, and flow labels.",
        "constraint_violated": "Covers limits on otherwise correct conduct: an action may be present, correctly assigned, and correctly ordered but still breach a deadline, quantity, purpose, or usage restriction. It connects the constraint field to timer, data, annotation, and related BPMN evidence.",
        "exception_not_handled": "Covers defeasible rules and exceptional paths: a normal path may be compliant while the process has no branch or handler for a legally specified exception. It connects the exception field to boundary/error events, alternate branches, and handler activities.",
    },
    "scope_boundary": (
        "These four types are a minimal field-coverage extension, not an "
        "exhaustive legal-violation taxonomy. They are development-only "
        "controlled categories and do not convert the frozen three-type "
        "human Gold or the formal Oracle into a seven-type benchmark."
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} root must be an object")
    return value


def _git_state() -> dict[str, str]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
            text=True, check=True,
        ).stdout.strip()
        return {"commit": commit, "dirty_paths": dirty.splitlines()[:20]}
    except Exception:  # pragma: no cover
        return {"commit": "unknown", "dirty_paths": []}


def _rule_texts() -> dict[str, str]:
    inference = _load_json(INFERENCE_PACK, "inference pack")
    texts: dict[str, str] = {}
    for item in inference.get("matching_items", []) + inference.get("violation_items", []):
        texts.setdefault(item["rule_id"], item["rule_text"])
    return texts


def _variant_bpmn(vid: str, pid: str, side: str) -> Path:
    path = ROOT / "data/development/stage3_synth" / vid / side / f"{pid}.bpmn"
    if not path.is_file():
        raise RuntimeError(f"{side} bpmn missing: {path}")
    return path


def _gamma_for(method: str) -> float:
    config_path = {
        "winter": WINTER_CONFIG, "sun": SUN_CONFIG,
        "bm25": BM25_CONFIG, "tfidf_svd": TFIDF_CONFIG,
    }[method]
    config = _load_json(config_path, f"{method} config")
    if method == "winter":
        return float(config["method"]["gamma"])
    if method == "sun":
        return float(config["method"]["thresholds"]["gamma"])
    return float(config["thresholds"]["gamma"])


def _frozen_tfidf_corpus() -> list[str]:
    """Same frozen fit corpus as the S3.6-B development run: unlabeled rule
    texts + source-process activity labels (never variant labels)."""
    corpus: list[str] = []
    for text in _rule_texts().values():
        if text not in corpus:
            corpus.append(text)
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    for bpmn in sorted(BPMN_DIR.glob("*.bpmn")):
        record = parse_bpmn_bytes(bpmn.read_bytes(), source_path=str(bpmn),
                                  contract=contract)
        for act in record.get("activities", []):
            if act["name"] and act["name"] not in corpus:
                corpus.append(act["name"])
    return corpus


def _make_bm25_sims(nlp, config: dict[str, Any]):
    from bpc_hybrid.stage3_baselines.bm25 import BM25Index
    k1 = float(config["method"]["bm25"]["k1"])
    b = float(config["method"]["bm25"]["b"])

    def factory(record: dict[str, Any], xml_root: Any) -> dict[str, Callable]:
        action_docs = action_candidates(record)
        action_index = BM25Index(action_docs, k1=k1, b=b)
        text_docs: list[str] = []
        for cands in (action_docs,
                      condition_candidates(record, xml_root),
                      constraint_candidates(record, xml_root),
                      exception_candidates(record, xml_root)):
            for cand in cands:
                if cand not in text_docs:
                    text_docs.append(cand)
        text_index = BM25Index(text_docs, k1=k1, b=b)
        return {"action": action_index.score, "text": text_index.score}
    return factory


def _make_tfidf_sims(nlp, config: dict[str, Any], corpus: list[str]):
    from bpc_hybrid.stage3_baselines.tfidf_svd import TfidfSvd
    svd = TfidfSvd(
        seed=int(config["method"]["svd"]["seed"]),
        dim=int(config["method"]["svd"]["dim"]),
        word_ngram=int(config["method"]["features"]["word_ngram"]),
        char_ngram=int(config["method"]["features"]["char_ngram"]),
        sublinear_tf=bool(config["method"]["features"]["sublinear_tf"]),
    )
    svd.fit(corpus)
    return {"action": svd.similarity, "text": svd.similarity}


# ---------------------------------------------------------------------------
# Per-method per-variant scoring
# ---------------------------------------------------------------------------


def _locked_sentence(variant: dict[str, Any], rule_text: str, nlp) -> dict[str, Any]:
    sentences = extract_six_element_sentences(variant["rule_id"], rule_text, nlp)
    sentence = next(
        (s for s in sentences if s["sentence_idx"] == variant["rule_element"]["sentence_idx"]),
        None,
    )
    if sentence is None:
        raise RuntimeError(
            f"{variant['variant_id']}: locked sentence not found on re-extraction")
    if not sentence_matches_locked(sentence, variant["rule_element"]):
        raise RuntimeError(
            f"{variant['variant_id']}: re-extraction does not match the locked rule element")
    return sentence


def _score_variant(method: str, variant: dict[str, Any], sentence: dict[str, Any],
                   sims_factory, gamma: float, gamma_ext: float, nlp) -> dict[str, Any]:
    pid = variant["process_id"]
    vid = variant["variant_id"]
    record = parse_bpmn_bytes(
        _variant_bpmn(vid, pid, "variant").read_bytes(),
        source_path=f"data/development/stage3_synth/{vid}/variant/{pid}.bpmn",
        contract=load_stage1_contract(STRUCTURAL_CONTRACT),
    )
    model = SunProcessModel(pid, record, nlp)
    import xml.etree.ElementTree as ET
    xml_root = ET.fromstring(_variant_bpmn(vid, pid, "variant").read_bytes())
    sims = sims_factory(record, xml_root)
    scorer = ExtendedViolationScorer(sims["action"], sims["text"], gamma, gamma_ext)

    mapped_id = None
    if sentence.get("action"):
        _, _, mapped_id = scorer._best_action(sentence["action"], model)

    scores: dict[str, Any] = {}
    observability: dict[str, Any] = {}
    scores["prohibited_action_present"] = scorer.prohibited_action(sentence, model)
    scores["required_condition_not_enforced"] = scorer.required_condition(
        sentence, model, condition_candidates(record, xml_root, mapped_id))
    scores["constraint_violated"] = scorer.constraint_violated(
        sentence, model, constraint_candidates(record, xml_root, mapped_id))
    scores["exception_not_handled"] = scorer.exception_not_handled(
        sentence, model, exception_candidates(record, xml_root, mapped_id))
    for t in EXTENDED_TYPES:
        result = scores[t]
        observability[t] = {
            "observable": bool(result.get("observable", False)),
            "reason": result.get("reason"),
        }
    return {"scores": scores, "observability": observability, "model": model,
            "record": record, "xml_root": xml_root}


def run_method(method: str, variant: dict[str, Any], sentence: dict[str, Any],
               sims_factory, gamma: float, gamma_ext: float, nlp,
               panel: dict[str, Any]) -> dict[str, Any]:
    expected = variant["expected_violation"]
    variant_result = _score_variant(
        method, variant, sentence, sims_factory, gamma, gamma_ext, nlp)
    expected_result = variant_result["scores"][expected]
    observable = bool(expected_result.get("observable", False))
    violation = bool(expected_result.get("violation", False))
    pred = expected if (observable and violation) else None

    # diagnostic control scores (not used in evaluation)
    pid = variant["process_id"]
    vid = variant["variant_id"]
    import xml.etree.ElementTree as ET
    control_record = parse_bpmn_bytes(
        _variant_bpmn(vid, pid, "control").read_bytes(),
        source_path=f"data/development/stage3_synth/{vid}/control/{pid}.bpmn",
        contract=load_stage1_contract(STRUCTURAL_CONTRACT),
    )
    control_model = SunProcessModel(pid, control_record, nlp)
    control_xml_root = ET.fromstring(_variant_bpmn(vid, pid, "control").read_bytes())
    sims = sims_factory(control_record, control_xml_root)
    control_scorer = ExtendedViolationScorer(sims["action"], sims["text"], gamma, gamma_ext)
    control_mapped_id = None
    if sentence.get("action"):
        _, _, control_mapped_id = control_scorer._best_action(sentence["action"], control_model)
    control_scores = {
        "prohibited_action_present": control_scorer.prohibited_action(sentence, control_model),
        "required_condition_not_enforced": control_scorer.required_condition(
            sentence, control_model,
            condition_candidates(control_record, control_xml_root, control_mapped_id)),
        "constraint_violated": control_scorer.constraint_violated(
            sentence, control_model,
            constraint_candidates(control_record, control_xml_root, control_mapped_id)),
        "exception_not_handled": control_scorer.exception_not_handled(
            sentence, control_model,
            exception_candidates(control_record, control_xml_root, control_mapped_id)),
    }
    control_scores_clean = {
        t: {
            "score": (control_scores[t].get("score") if control_scores[t].get("observable") else None),
            "observable": bool(control_scores[t].get("observable", False)),
            "reason": control_scores[t].get("reason"),
            "exact_contradiction": control_scores[t].get("exact_contradiction"),
        }
        for t in EXTENDED_TYPES
    }

    return {
        "schema_version": "stage3_extended_prediction@1.0.0",
        "method_id": METHOD_IDS[method],
        "method_display_name": METHOD_DISPLAY[method],
        "run_id": f"s3_extended_violation_panel_v2_{method}",
        "task": "violation",
        "item_id": variant["variant_id"],
        "process_id": variant["process_id"],
        "rule_id": variant["rule_id"],
        "expected_violation": expected,
        "check_type": expected,
        "predicted_violation_type": pred,
        "scores": {
            t: (variant_result["scores"][t].get("score")
                if variant_result["scores"][t].get("observable") else None)
            for t in EXTENDED_TYPES
        },
        "scores_detail": {
            t: {k: v for k, v in variant_result["scores"][t].items()
                if k != "score"}
            for t in EXTENDED_TYPES
        },
        "observability": variant_result["observability"],
        "control_scores": control_scores_clean,
        "threshold": gamma_ext,
        "action_mapping_gamma": gamma,
        "gamma_ext": gamma_ext,
        "panel": "synthetic_controlled_error_extension_v2",
        "gold_visible": False,
        "source_hashes": {
            "variant": variant["variant_id"],
            "source_bpmn_sha256": variant["source_bpmn_sha256"],
            "variant_bpmn_sha256": variant["variant_bpmn_sha256"],
            "control_bpmn_sha256": variant["control_bpmn_sha256"],
        },
        "method_provenance": (
            f"{METHOD_DISPLAY[method]} gamma_ext={gamma_ext} "
            f"action_gamma={gamma} (synthetic panel v2; original papers define "
            "no such violation types)"
        ),
    }


def build_predictions(method: str, panel: dict[str, Any], rule_texts: dict[str, str],
                      sims_factory, gamma: float, gamma_ext: float, nlp) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant in panel["variants"]:
        sentence = _locked_sentence(variant, rule_texts[variant["rule_id"]], nlp)
        rows.append(run_method(method, variant, sentence, sims_factory, gamma,
                               gamma_ext, nlp, panel))
    return rows


# ---------------------------------------------------------------------------
# Comparison report
# ---------------------------------------------------------------------------


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _p_r_f1_row(t: str, per_type: dict[str, Any]) -> str:
    p = per_type[t]
    return f"{p['precision']:.3f}/{p['recall']:.3f}/{p['f1']:.3f}"


def _load_v1_summary() -> dict[str, Any]:
    data = _load_json(V1_COMPARE, "v1 comparison")
    summary: dict[str, Any] = {}
    for method, info in data["methods"].items():
        ev = info["evaluation"]
        summary[method] = {
            "per_type_f1": {t: ev["per_type"][t]["f1"] for t in ev["per_type"]},
            "macro_f1": ev["macro_f1"],
            "exact": ev["exact_type_accuracy"],
            "unobservable": ev["unobservable"],
            "support": ev["support"],
        }
    return summary


def build_comparison(panel: dict[str, Any], results: dict[str, Any]) -> dict[str, Any]:
    methods_out: dict[str, Any] = {}
    for method, r in results.items():
        ev = r["evaluation"]
        methods_out[method] = {
            "method_id": METHOD_IDS[method],
            "display_name": METHOD_DISPLAY[method],
            "run_dir": f"outputs/development/s3_extended_violation_panel_v2_{method}",
            "runtime_seconds": r["runtime_seconds"],
            "evaluation": ev,
            "failures": r["failures"],
            "unobservable_cases": r["unobservable_cases"],
        }
    return {
        "schema_version": "s3_extended_violation_comparison@1.0.0",
        "panel": "synthetic_controlled_error_extension_v2",
        "panel_manifest_sha256": _sha256(PANEL),
        "panel_counts": panel["counts"],
        "panel_counts_total": panel["counts_total"],
        "scope_note": (
            "development-only synthetic controlled extension; NOT human Gold; "
            "NOT the formal Oracle; Winter/Sun original papers define none of "
            "the four new violation types (Winter-style extension / Sun-style "
            "extension naming)"
        ),
        "selection_rationale": SELECTION_RATIONALE,
        "thresholds": {
            "gamma_ext": panel["config"]["gamma_ext"],
            "action_mapping_gamma": {
                m: _gamma_for(m) for m in ("winter", "sun", "bm25", "tfidf_svd")
            },
        },
        "methods": methods_out,
        "seven_class_synthetic_summary": {
            "note": (
                "synthetic-only 7-class overview combining the v1 three-type "
                "panel (30 items, stored comparison) and the v2 four-type panel "
                "(40 items); NEVER human Gold, NEVER the formal Oracle; the two "
                "panels use different formulas/backends, so cross-panel F1 "
                "comparison is descriptive only"
            ),
            "v1_three_types": _load_v1_summary(),
            "v2_four_types": {
                method: {
                    "per_type_f1": {
                        t: results[method]["evaluation"]["per_type"][t]["f1"]
                        for t in EXTENDED_TYPES
                    },
                    "macro_f1": results[method]["evaluation"]["macro_f1"],
                    "exact": results[method]["evaluation"]["exact_type_accuracy"],
                    "unobservable": results[method]["evaluation"]["unobservable"],
                    "support": results[method]["evaluation"]["support"],
                }
                for method in results
            },
        },
        "analysis": _analysis(results),
    }


def _case_rows(results: dict[str, Any], panel: dict[str, Any]) -> dict[str, Any]:
    """Per type: up to 2 detected and 2 missed cases (across methods)."""
    by_type: dict[str, dict[str, list[dict[str, Any]]]] = {
        t: {"detected": [], "missed": []} for t in EXTENDED_TYPES
    }
    for method, r in results.items():
        for row in r["predictions"]:
            t = row["expected_violation"]
            bucket = "detected" if row["predicted_violation_type"] == t else "missed"
            by_type[t][bucket].append({
                "method": method,
                "item_id": row["item_id"],
                "process_id": row["process_id"],
                "rule_id": row["rule_id"],
                "predicted": row["predicted_violation_type"],
                "scores": row["scores"],
                "observability": row["observability"][t],
            })
    out: dict[str, Any] = {}
    for t in EXTENDED_TYPES:
        out[t] = {
            "detected_cases": by_type[t]["detected"][:2],
            "missed_cases": by_type[t]["missed"][:2],
            "detected_total": len(by_type[t]["detected"]),
            "missed_total": len(by_type[t]["missed"]),
        }
    return out


def _analysis(results: dict[str, Any]) -> dict[str, Any]:
    per_type_f1_by_method: dict[str, dict[str, float]] = {}
    for method, r in results.items():
        per_type_f1_by_method[method] = {
            t: r["evaluation"]["per_type"][t]["f1"] for t in EXTENDED_TYPES
        }
    avg_f1 = {
        t: round(statistics.mean(per_type_f1_by_method[m][t] for m in results), 4)
        for t in EXTENDED_TYPES
    }
    easiest = max(avg_f1, key=avg_f1.get)
    hardest = min(avg_f1, key=avg_f1.get)
    macro_by_method = {
        m: r["evaluation"]["macro_f1"] for m, r in results.items()
    }
    best_method = max(macro_by_method, key=macro_by_method.get)
    unobservable_by_reason: dict[str, int] = {}
    for r in results.values():
        for reason, count in r["evaluation"]["denominator"]["unobservable_by_reason"].items():
            unobservable_by_reason[reason] = unobservable_by_reason.get(reason, 0) + count
    return {
        "average_per_type_f1": avg_f1,
        "easiest_type": easiest,
        "hardest_type": hardest,
        "macro_f1_by_method": macro_by_method,
        "best_macro_method": best_method,
        "stage2_field_dependencies": {
            "prohibited_action_present": ["modality (prohibition)", "action"],
            "required_condition_not_enforced": ["condition", "action"],
            "constraint_violated": ["constraint", "action"],
            "exception_not_handled": ["exception", "action"],
        },
        "rule_record_downstream_value": (
            "each new check consumes a DIFFERENT six-element Rule Record field "
            "(modality+action / condition / constraint / exception) against a "
            "DIFFERENT BPMN surface (action labels / gateway-condition-flow "
            "labels / data-annotation-timer labels / boundary-error-branch "
            "labels). The checks are therefore downstream consumers of Stage 2 "
            "element extraction, not merely extra labels on the old three "
            "scores: an empty or unextractable element makes the check "
            "unobservable by construction."
        ),
        "unobservable_by_reason": unobservable_by_reason,
        "expressiveness_limits": {
            "note": "unobservable reasons caused by BPMN expressiveness: "
                    "no_condition_candidates / no_constraint_candidates / "
                    "no_exception_candidates (no gateway/condition surface, no "
                    "data/annotation/timer surface, no boundary/error/branch "
                    "surface in the variant model), and action_mapping_below_"
                    "gamma (the variant's activity labels are not similar "
                    "enough to the rule action under the method's frozen gamma)",
        },
    }


def render_markdown(panel: dict[str, Any], comparison: dict[str, Any],
                    results: dict[str, Any]) -> str:
    methods = comparison["methods"]
    rows = []
    for method in ("winter", "sun", "bm25", "tfidf_svd"):
        ev = methods[method]["evaluation"]
        cells = [METHOD_DISPLAY[method]]
        for t in EXTENDED_TYPES:
            cells.append(_p_r_f1_row(t, ev["per_type"]))
        cells.append(f"{ev['macro_f1']:.3f}")
        cells.append(f"{ev['exact_type_accuracy']:.3f}")
        cells.append(str(ev["unobservable"]))
        cells.append(f"{methods[method]['runtime_seconds']:.1f}s")
        rows.append("| " + " | ".join(cells) + " |")
    header = ("| Method | prohibited P/R/F1 | condition P/R/F1 | constraint "
              "P/R/F1 | exception P/R/F1 | Macro-F1 | Exact | Unobservable | "
              "Runtime |")
    sep = "|---|---|---|---|---|---|---|---|---|"
    table = "\n".join([header, sep] + rows)

    cases = _case_rows(results, panel)
    rationale = comparison["selection_rationale"]
    lines = [
        "# S3.9-EXT synthetic extended-violation comparison v2 (development-only)",
        "",
        "**Scope**: 40 controlled synthetic variants over the frozen GDPR-7 "
        "BPMN membership (10 prohibited_action_present / 10 "
        "required_condition_not_enforced / 10 constraint_violated / 10 "
        "exception_not_handled). This panel is a **development-only synthetic "
        "controlled extension**: it is NOT human Gold and NOT the formal "
        "Oracle. Winter et al. (2020) and Sun et al. (2024) define none of the "
        "four new violation types — the methods below are project extensions "
        "(`Winter-style extension` / `Sun-style extension`) reusing each "
        "method's existing similarity backend and frozen action-mapping gamma; "
        "they share the SAME new-type formulas. Zero LLM/API.",
        "",
        "## Selection rationale",
        "",
        rationale["research_gap"],
        "",
        "The four categories were selected by four fixed principles:",
        "",
        *[f"- {principle}" for principle in rationale["selection_principles"]],
        "",
        "| New type | Why it is needed beyond action/actor/order |",
        "|---|---|",
        *[
            f"| {t} | {rationale['type_reasons'][t]} |"
            for t in EXTENDED_TYPES
        ],
        "",
        f"**Boundary**: {rationale['scope_boundary']}",
        "",
        "## 1. Four new types — per-method comparison",
        "",
        table,
        "",
        "## 2. Synthetic 7-class overview (descriptive only)",
        "",
        "Combines the v1 three-type panel (30 items, stored comparison) and "
        "the v2 four-type panel (40 items). **Synthetic only; never merged "
        "with the 33-item human-adjudicated Gold; not the formal Oracle.** "
        "The two panels use different formulas, so cross-panel numbers are "
        "descriptive, not comparable metrics.",
        "",
        "| Method | missing_action F1 | incorrect_actor F1 | out_of_order F1 | "
        "prohibited F1 | condition F1 | constraint F1 | exception F1 | "
        "Macro-F1 | Exact | Unobservable |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    v1 = comparison["seven_class_synthetic_summary"]["v1_three_types"]
    v2 = comparison["seven_class_synthetic_summary"]["v2_four_types"]
    for method in ("winter", "sun", "bm25", "tfidf_svd"):
        v1m = v1[method]
        v2m = v2[method]
        lines.append(
            "| " + " | ".join([
                METHOD_DISPLAY[method],
                f"{v1m['per_type_f1']['missing_action']:.3f}",
                f"{v1m['per_type_f1']['incorrect_actor']:.3f}",
                f"{v1m['per_type_f1']['out_of_order']:.3f}",
                f"{v2m['per_type_f1']['prohibited_action_present']:.3f}",
                f"{v2m['per_type_f1']['required_condition_not_enforced']:.3f}",
                f"{v2m['per_type_f1']['constraint_violated']:.3f}",
                f"{v2m['per_type_f1']['exception_not_handled']:.3f}",
                f"{v2m['macro_f1']:.3f}",
                f"{v2m['exact']:.3f}",
                str(v2m["unobservable"]),
            ]) + " |"
        )
    lines += [
        "",
        "## 3. Per-type success and failure cases (across methods)",
        "",
    ]
    for t in EXTENDED_TYPES:
        c = cases[t]
        lines.append(f"### {t}  (detected {c['detected_total']} / missed {c['missed_total']} across 40 method-variant pairs)")
        lines.append("")
        lines.append("Detected (up to 2):")
        for case in c["detected_cases"]:
            lines.append(
                f"- {case['method']} / {case['item_id']} ({case['process_id']} x "
                f"{case['rule_id']}): pred={case['predicted']} scores={case['scores']}")
        if not c["detected_cases"]:
            lines.append("- (none)")
        lines.append("")
        lines.append("Missed (up to 2):")
        for case in c["missed_cases"]:
            lines.append(
                f"- {case['method']} / {case['item_id']} ({case['process_id']} x "
                f"{case['rule_id']}): pred={case['predicted']} scores={case['scores']} "
                f"observability={case['observability']}")
        if not c["missed_cases"]:
            lines.append("- (none)")
        lines.append("")
    analysis = comparison["analysis"]
    lines += [
        "## 4. Analysis",
        "",
        f"- **Easiest type (average F1)**: `{analysis['easiest_type']}` "
        f"({_fmt(analysis['average_per_type_f1'][analysis['easiest_type']])}).",
        f"- **Hardest type (average F1)**: `{analysis['hardest_type']}` "
        f"({_fmt(analysis['average_per_type_f1'][analysis['hardest_type']])}).",
        f"- **Best macro-F1 method**: `{analysis['best_macro_method']}` "
        f"({_fmt(analysis['macro_f1_by_method'][analysis['best_macro_method']])}).",
        "",
        "### Stage 2 six-element Rule Record dependencies",
        "",
        "| New type | Rule Record fields consumed | BPMN surface examined |",
        "|---|---|---|",
        "| prohibited_action_present | modality (prohibition) + action | activity/event labels |",
        "| required_condition_not_enforced | condition + action | gateway labels, conditionExpression, sequence-flow labels, adjacent control nodes |",
        "| constraint_violated | constraint + action | activity/data-object/text-annotation/timer labels; explicit time-limit contradiction |",
        "| exception_not_handled | exception + action | boundary events, error/escalation events, alternate branches, handler labels |",
        "",
        "The four new checks are **downstream value of the six-element Rule "
        "Record**, not extra labels on the old three scores: each check "
        "consumes a different element (modality+action / condition / "
        "constraint / exception) and a different BPMN surface. When Stage 2 "
        "produces an empty element, or the variant model has no matching "
        "surface, the check is recorded unobservable (never hard 0/1).",
        "",
        "### Unobservable reasons (all methods combined)",
        "",
    ]
    for reason, count in sorted(analysis["unobservable_by_reason"].items()):
        lines.append(f"- `{reason}`: {count}")
    lines += [
        "",
        "### BPMN expressiveness limits",
        "",
        analysis["expressiveness_limits"]["note"],
        "",
        "Concrete findings on the frozen GDPR-7 files:",
        "",
        "- The frozen files contain **no conditionExpression and no boundary "
        "event**; every condition/exception compliant structure in this panel "
        "is a synthetic control added to a frozen copy. Removing it makes the "
        "variant byte-identical to the frozen process — the frozen process "
        "itself is the violated model.",
        "- The **named decision gateways** of gdpr_1 ('Are stolen data "
        "exploitable?', 'Does the data controller have high security "
        "standard?', 'The data subject has to be notified?') live **inside "
        "subProcesses**, which the canonical parser treats as opaque "
        "activities. The process-level record therefore exposes no named "
        "gateway / condition surface, and condition checks on those variants "
        "are `no_condition_candidates` unobservable (7 unobservables across "
        "methods).",
        "- The '72 hours' timer start event of gdpr_1 sits inside the 'Handle "
        "delay' subProcess: invisible to the record parser, observable only at "
        "the raw-XML level. The two timer-contradiction variants were still "
        "detected (exact contradiction) by every method, because the "
        "contradiction record is a direct observation independent of action "
        "mapping.",
        "- **Method-backend scale effects**: for BM25 an exact text match "
        "scores ~0.4-0.6 depending on label length (the S3.6-A v3 "
        "normalization), so long prohibited-action labels fall below "
        "`gamma_ext` (BM25 prohibited recall 0.4), while spaCy and TF-IDF "
        "exact matches score 1.0. This is a backend scale property of the "
        "frozen similarity functions, not a panel artifact.",
        "- **Action-mapping gate**: sun (gamma 0.8), BM25 (0.8) and TF-IDF "
        "(0.5) fail the action-mappable precondition on most condition/"
        "constraint/exception variants (92 `action_mapping_below_gamma` "
        "unobservables across methods). The new checks inherit the same "
        "action-mapping bottleneck as the original three violation types; "
        "only the Winter-style extension (gamma 0.4) maps most rule actions.",
        "",
        "## 5. Safety",
        "",
        "- `llm_api_calls = 0`, `network_calls = 0`, `gold_read = False`.",
        "- The 33-item human-adjudicated violation Gold, the formal Stage 3 "
        "schemas and the v1 three-type predictions/results are untouched "
        "(byte-unchanged; see the focused tests).",
        "- This panel is a synthetic controlled extension; results must not be "
        "cited as formal Oracle or human-Gold performance.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", choices=("winter", "sun", "bm25", "tfidf_svd", "all"),
                        default="all")
    args = parser.parse_args()

    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "build_s3_extended_violation_panel_v2.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT.parent,
    )
    if r.returncode != 0:
        print("panel replay check failed; refusing to run methods")
        return 2
    panel = _load_json(PANEL, "panel manifest")
    extension_cfg = _load_json(EXTENSION_CONFIG, "extension config")
    gamma_ext = float(extension_cfg["thresholds"]["gamma_ext"])
    rule_texts = _rule_texts()

    nlp = spacy.load("en_core_web_sm")
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity
    sim = WinterSimilarity(nlp)

    methods = ("winter", "sun", "bm25", "tfidf_svd") if args.method == "all" \
        else (args.method,)

    tfidf_config = _load_json(TFIDF_CONFIG, "tfidf config")
    tfidf_sims = _make_tfidf_sims(nlp, tfidf_config, _frozen_tfidf_corpus())
    bm25_config = _load_json(BM25_CONFIG, "bm25 config")
    bm25_factory = _make_bm25_sims(nlp, bm25_config)

    def sims_factory_for(method: str):
        if method in ("winter", "sun"):
            return lambda record, xml_root: {"action": sim.text_pair, "text": sim.text_pair}
        if method == "bm25":
            return bm25_factory
        return lambda record, xml_root: tfidf_sims

    gold_synthetic = {
        v["variant_id"]: {"expected_violation": v["expected_violation"]}
        for v in panel["variants"]
    }

    results: dict[str, Any] = {}
    for method in methods:
        t0 = time.time()
        gamma = _gamma_for(method)
        predictions = build_predictions(
            method, panel, rule_texts, sims_factory_for(method), gamma,
            gamma_ext, nlp,
        )
        elapsed = time.time() - t0
        evaluation = evaluate_extended(predictions, gold_synthetic)

        run_dir = OUT_ROOT / f"s3_extended_violation_panel_v2_{method}"
        if run_dir.exists():
            raise RuntimeError(f"refusing to overwrite existing run: {run_dir}")
        run_dir.mkdir(parents=True)
        (run_dir / "predictions.jsonl").write_text(
            "\n".join(json.dumps(p, ensure_ascii=False, sort_keys=True)
                      for p in predictions) + "\n",
            encoding="utf-8",
        )
        (run_dir / "evaluation.json").write_text(
            json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        failures = [
            {
                "item_id": p["item_id"], "process_id": p["process_id"],
                "rule_id": p["rule_id"], "expected": p["expected_violation"],
                "predicted": p["predicted_violation_type"],
                "scores": p["scores"], "observability": p["observability"][p["expected_violation"]],
            }
            for p in predictions if p["predicted_violation_type"] != p["expected_violation"]
        ]
        unobservable_cases = [
            {
                "item_id": p["item_id"], "process_id": p["process_id"],
                "rule_id": p["rule_id"], "expected": p["expected_violation"],
                "reason": p["observability"][p["expected_violation"]].get("reason"),
                "scores": p["scores"],
            }
            for p in predictions
            if p["observability"][p["expected_violation"]].get("observable") is False
        ]
        (run_dir / "failures.json").write_text(
            json.dumps(failures, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (run_dir / "unobservable_cases.json").write_text(
            json.dumps(unobservable_cases, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest = {
            "schema_version": "s3_extended_violation_panel_run@1.0.0",
            "run_id": f"s3_extended_violation_panel_v2_{method}",
            "method": method,
            "method_id": METHOD_IDS[method],
            "display_name": METHOD_DISPLAY[method],
            "panel": "synthetic_controlled_error_extension_v2",
            "panel_manifest_sha256": _sha256(PANEL),
            "panel_counts": panel["counts"],
            "thresholds": {"gamma_ext": gamma_ext, "action_mapping_gamma": gamma},
            "runtime_seconds": round(elapsed, 3),
            "git": _git_state(),
            "safety": {
                "llm_api_calls": 0,
                "network_calls": 0,
                "gold_read": False,
                "synthetic_panel_not_human_gold": True,
                "original_papers_define_no_new_types": True,
            },
        }
        (run_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        results[method] = {
            "predictions": predictions,
            "evaluation": evaluation,
            "runtime_seconds": round(elapsed, 3),
            "failures": failures,
            "unobservable_cases": unobservable_cases,
        }
        print(
            f"[{method}] macro_f1={evaluation['macro_f1']} "
            f"exact={evaluation['exact_type_accuracy']} "
            f"unobservable={evaluation['unobservable']} "
            f"({elapsed:.1f}s)"
        )

    comparison = build_comparison(panel, results)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_ROOT / "s3_extended_violation_comparison_v2.json"
    md_path = REPORT_ROOT / "s3_extended_violation_comparison_v2.md"
    if json_path.exists() or md_path.exists():
        raise RuntimeError("refusing to overwrite existing comparison report")
    json_path.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(panel, comparison, results), encoding="utf-8")
    print("S3.9-EXT comparison v2 written (zero API):",
          json_path.relative_to(ROOT), md_path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
