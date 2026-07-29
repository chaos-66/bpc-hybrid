"""Read-only B2b prohibition↔permission diagnostic on immutable v10-A.

This script uses only the existing v10-A attempts/evaluation, the frozen
development Layer E, membership, and the unchanged v3 evaluator alignment.
It does not import any B2a/B2a2 implementation and does not run a model,
CoreNLP, Independent-82, S2.4 test, network, LLM, or API.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.b0_v10.alignment import align_de_to_en_units  # noqa: E402
from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    Estg150B0DevelopmentError,
    build_canonical_gold_records,
    load_object,
    sha256_file,
)
from bpc_hybrid.stage2_evaluation_v3 import (  # noqa: E402
    clause_iou_pairs,
    load_evaluator_contract,
)


RUN_ID = "s27_estg150_b0_b2b_prohibition_diagnostic_v1"
OUTPUT_DIR = ROOT / "outputs/development" / RUN_ID
V10_DIR = ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a"
V10_ATTEMPTS = V10_DIR / "b0_attempts.json"
V10_EVALUATION = V10_DIR / "evaluation_all150.json"
V10_MANIFEST = V10_DIR / "manifest.json"
LAYER_E = ROOT / "data/development/human_review/estg_150_human_correction_v1.json"
MEMBERSHIP = ROOT / "data/development/estg/estg_150_membership_hashes.json"
EVALUATOR = ROOT / "configs/stage2_evaluator_s210_v3.json"

EXPECTED_HASHES = {
    "v10_manifest": "88070fab4da3f7c708f055f6bc391b78cc888761c3d6fe117d17673c2c382315",
    "layer_e": "7fd55f98a7dd6aeef58a93be825465c767f00feeab84c6d4215afc434a135b1c",
    "membership": "0f9065523a57900b22a8a04ae9109d37c72abbe514f3cde60bcd7652cfa1417b",
    "evaluator": "28ce332564c5d10da08dea515aefe31cc2aacd91b6c6877aa1bfebe44f39ae7f",
}

EXCLUSION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("not_only", re.compile(r"\bnot\s+only\b", re.I)),
    ("not_merely", re.compile(r"\bnot\s+merely\b", re.I)),
    ("not_necessarily", re.compile(r"\bnot\s+necessarily\b", re.I)),
    ("may_or_may_not", re.compile(r"\bmay\s+or\s+may\s+not\b", re.I)),
    ("whether_or_not", re.compile(r"\bwhether\s+or\s+not\b", re.I)),
    ("notwithstanding", re.compile(r"\bnotwithstanding\b", re.I)),
)
DEFINITION_MENTION = re.compile(
    r"\b(?:shall\s+mean|means|is\s+defined\s+as|are\s+defined\s+as|refers\s+to|denotes)\b",
    re.I,
)
GERMAN_MUSS_NICHT = re.compile(r"\bm(?:u|ü)ss(?:en)?\b(?:\W+\w+){0,5}?\W+nicht\b", re.I)
GERMAN_CORROBORATION: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "german_darf_nicht",
        re.compile(r"\b(?:darf|dürfen|duerfen)\b(?:\W+\w+){0,8}?\W+nicht\b", re.I),
    ),
    (
        "german_not_permissible",
        re.compile(r"\b(?:ist|sind)\b(?:\W+\w+){0,4}?\W+nicht\s+zulässig\b", re.I),
    ),
    ("german_forbidden", re.compile(r"\b(?:ist|sind)\b(?:\W+\w+){0,4}?\W+verboten\b", re.I)),
    (
        "german_no_subject_may",
        re.compile(r"\b(?:kein|keine|keiner)\b(?:\W+\w+){1,8}?\W+(?:darf|dürfen|duerfen)\b", re.I),
    ),
)
ENGLISH_EVIDENCE: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "negated_passive_permission",
        "passive_not_permitted_allowed_authorized_entitled",
        re.compile(
            r"\b(?:is|are)\s+not\s+(?:permitted|allowed|authorized|entitled)\s+to\b",
            re.I,
        ),
    ),
    (
        "lexical_prohibited_forbidden",
        "passive_prohibited_forbidden_from",
        re.compile(r"\b(?:is|are)\s+(?:prohibited|forbidden)\s+from\b", re.I),
    ),
    (
        "no_subject_modal",
        "no_subject_may_shall",
        re.compile(r"\bno\s+(?:[A-Za-z][\w'-]*\s+){1,8}(?:may|shall)\b", re.I),
    ),
    (
        "direct_english_modal_negation",
        "modal_not_scope",
        re.compile(r"\b(?:may|shall|must)\s+not\b", re.I),
    ),
)


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def _inside_quote(text: str, start: int, end: int) -> bool:
    for left, right in (("\"", "\""), ("“", "”"), ("‘", "’")):
        opening = text.rfind(left, 0, start + 1)
        closing = text.find(right, end)
        if opening >= 0 and closing >= 0:
            return True
    return False


def _condition_or_exception_only(text: str, evidence_span: tuple[int, int]) -> bool:
    comma = text.find(",")
    if comma < 0 or evidence_span[0] > comma:
        return False
    prefix = text[:comma].lstrip().casefold()
    if not prefix.startswith(("if ", "when ", "unless ", "provided ", "where ", "except ")):
        return False
    tail = text[comma + 1 :]
    positive_tail = re.search(r"\b(?:may|is\s+permitted\s+to|is\s+allowed\s+to)\b", tail, re.I)
    return positive_tail is not None


def detect_strong_prohibition_scope(
    english_clause: str,
    german_clause: str | None,
) -> dict[str, Any]:
    """Classify fixed B2b evidence without Gold, IDs, positions, or learned scores."""

    if not isinstance(english_clause, str) or not english_clause.strip():
        raise Estg150B0DevelopmentError("B2b diagnostic requires real non-empty clause text")
    if english_clause.strip() == ".":
        raise Estg150B0DevelopmentError("B2b placeholder clause text is forbidden")
    german = german_clause or ""
    german_signal = next(
        (name for name, pattern in GERMAN_CORROBORATION if pattern.search(german)),
        None,
    )
    for name, pattern in EXCLUSION_PATTERNS:
        if pattern.search(english_clause):
            return {
                "strong": False,
                "signal_family": "excluded_ambiguous_negation",
                "evidence_type": None,
                "excluded_reason": name,
                "german_corroboration": german_signal,
            }
    if DEFINITION_MENTION.search(english_clause):
        return {
            "strong": False,
            "signal_family": "excluded_ambiguous_negation",
            "evidence_type": None,
            "excluded_reason": "definition_negation_mention",
            "german_corroboration": german_signal,
        }
    if GERMAN_MUSS_NICHT.search(german):
        return {
            "strong": False,
            "signal_family": "excluded_ambiguous_negation",
            "evidence_type": None,
            "excluded_reason": "german_muss_nicht",
            "german_corroboration": None,
        }
    for family, evidence_type, pattern in ENGLISH_EVIDENCE:
        match = pattern.search(english_clause)
        if match is None:
            continue
        span = (match.start(), match.end())
        if _inside_quote(english_clause, *span):
            return {
                "strong": False,
                "signal_family": "excluded_ambiguous_negation",
                "evidence_type": None,
                "excluded_reason": "quoted_or_mentioned_negation",
                "german_corroboration": german_signal,
            }
        if _condition_or_exception_only(english_clause, span):
            return {
                "strong": False,
                "signal_family": "excluded_ambiguous_negation",
                "evidence_type": None,
                "excluded_reason": "condition_or_exception_only_not_main_nucleus",
                "german_corroboration": german_signal,
            }
        return {
            "strong": True,
            "signal_family": family,
            "evidence_type": evidence_type,
            "excluded_reason": None,
            "evidence_span": [span[0], span[1]],
            "evidence_text": english_clause[span[0] : span[1]],
            "german_corroboration": german_signal,
        }
    if german_signal:
        family = "german_corroborating_negation"
    else:
        family = "no_usable_clause_local_negation_signal"
    return {
        "strong": False,
        "signal_family": family,
        "evidence_type": None,
        "excluded_reason": None,
        "german_corroboration": german_signal,
    }


def _load_attempts(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise Estg150B0DevelopmentError("v10-A attempts must be an object array")
    return value


def _sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items()))


def main() -> int:
    try:
        if OUTPUT_DIR.exists():
            raise Estg150B0DevelopmentError(f"refusing to overwrite: {OUTPUT_DIR}")
        for name, path in (
            ("v10_manifest", V10_MANIFEST),
            ("layer_e", LAYER_E),
            ("membership", MEMBERSHIP),
            ("evaluator", EVALUATOR),
        ):
            if sha256_file(path) != EXPECTED_HASHES[name]:
                raise Estg150B0DevelopmentError(f"fixed input hash mismatch: {name}")
        attempts = _load_attempts(V10_ATTEMPTS)
        report = load_object(V10_EVALUATION)
        v10_manifest = load_object(V10_MANIFEST)
        if (
            v10_manifest.get("run_id") != "s27_estg150_b0_enhanced_v10a"
            or report.get("method_id") != "sun_rule_only"
        ):
            raise Estg150B0DevelopmentError("v10-A identity mismatch")
        contract = load_evaluator_contract(EVALUATOR)
        minimum_iou = float(contract["alignment"]["clause_minimum_iou"])
        gold, source_records = build_canonical_gold_records(LAYER_E, MEMBERSHIP)
        gold_by_id = {row["sample_id"]: row for row in gold}
        source_by_id = {row["sample_id"]: row for row in source_records}
        if set(gold_by_id) != {row["sample_id"] for row in attempts}:
            raise Estg150B0DevelopmentError("attempt/Gold membership mismatch")

        aligned_confusion = Counter()
        signal_buckets = Counter()
        predicted_permission_total = 0
        firing_total = 0
        firing_by_evidence = Counter()
        firing_by_family = Counter()
        firing_by_route = Counter()
        firing_by_supported = Counter()
        firing_gold_distribution = Counter()

        for attempt in attempts:
            sample_id = attempt["sample_id"]
            predicted_record = attempt["record"]
            predicted = predicted_record.get("clauses") or []
            gold_clauses = gold_by_id[sample_id].get("clauses") or []
            pairs, unmatched_gold, unmatched_predicted, _ = clause_iou_pairs(
                gold_clauses,
                predicted,
                minimum_iou=minimum_iou,
            )
            pred_to_gold = {pred_i: gold_i for gold_i, pred_i in pairs}
            for gold_i, pred_i in pairs:
                gold_label = gold_clauses[gold_i]["modality"]["label"]
                pred_label = predicted[pred_i]["modality"]["label"]
                if gold_label == "prohibition" and pred_label == "permission":
                    aligned_confusion["gold_prohibition_to_pred_permission"] += 1
                if gold_label == "permission" and pred_label == "prohibition":
                    aligned_confusion["gold_permission_to_pred_prohibition"] += 1
                if gold_label == "prohibition" and pred_label == "obligation":
                    aligned_confusion["gold_prohibition_to_pred_obligation"] += 1
                if gold_label == "prohibition" and pred_label == "definition":
                    aligned_confusion["gold_prohibition_to_pred_definition"] += 1
                if pred_label == "prohibition" and gold_label != "prohibition":
                    aligned_confusion["extra_predicted_prohibition"] += 1
            aligned_confusion["unmatched_gold_prohibition"] += sum(
                gold_clauses[index]["modality"]["label"] == "prohibition"
                for index in unmatched_gold
            )
            aligned_confusion["extra_predicted_prohibition"] += sum(
                predicted[index]["modality"]["label"] == "prohibition"
                for index in unmatched_predicted
            )

            english_texts = [clause["clause_span"]["text"] for clause in predicted]
            alignments = align_de_to_en_units(
                source_by_id[sample_id]["raw_text_de"],
                english_texts,
            )
            if len(alignments) != len(predicted):
                raise Estg150B0DevelopmentError("reconstructed alignment count mismatch")
            for pred_i, (clause, alignment) in enumerate(
                zip(predicted, alignments, strict=True)
            ):
                stored_supported = bool(clause.get("alignment", {}).get("supported"))
                if stored_supported != alignment.heuristic_supported:
                    raise Estg150B0DevelopmentError("stored/reconstructed support mismatch")
                if clause["modality"]["label"] != "permission":
                    continue
                predicted_permission_total += 1
                evidence = detect_strong_prohibition_scope(
                    clause["clause_span"]["text"],
                    alignment.text if alignment.heuristic_supported else None,
                )
                gold_i = pred_to_gold.get(pred_i)
                gold_label = (
                    "unmatched"
                    if gold_i is None
                    else gold_clauses[gold_i]["modality"]["label"]
                )
                if gold_label == "prohibition":
                    signal_buckets[str(evidence["signal_family"])] += 1
                fires = stored_supported and bool(evidence["strong"])
                if not fires:
                    continue
                firing_total += 1
                firing_by_evidence[str(evidence["evidence_type"])] += 1
                firing_by_family[str(evidence["signal_family"])] += 1
                firing_by_route[str(clause["modality"]["route"])] += 1
                firing_by_supported["supported" if stored_supported else "unsupported"] += 1
                firing_gold_distribution[gold_label] += 1

        for key in (
            "gold_prohibition_to_pred_permission",
            "gold_permission_to_pred_prohibition",
            "gold_prohibition_to_pred_obligation",
            "gold_prohibition_to_pred_definition",
            "unmatched_gold_prohibition",
            "extra_predicted_prohibition",
        ):
            aligned_confusion.setdefault(key, 0)
        for key in (
            "direct_english_modal_negation",
            "negated_passive_permission",
            "no_subject_modal",
            "lexical_prohibited_forbidden",
            "german_corroborating_negation",
            "excluded_ambiguous_negation",
            "no_usable_clause_local_negation_signal",
        ):
            signal_buckets.setdefault(key, 0)

        recoverable = int(firing_gold_distribution["prohibition"])
        permission_loss = int(firing_gold_distribution["permission"])
        conditions = {
            "at_least_three_recoverable_errors": recoverable >= 3,
            "expected_total_triggers_at_most_twelve": 0 < firing_total <= 12,
            "no_sample_specific_exception_required": True,
            "no_lexicon_tregex_bert_change_required": True,
            "only_parent_permission_changes": True,
        }
        instantiated = all(conditions.values())
        summary = {
            "schema_version": "b2b_prohibition_diagnostic@1.0.0",
            "diagnostic_id": RUN_ID,
            "claim_scope": "development_diagnostic_only",
            "is_formal_result": False,
            "aligned_confusion": _sorted_counter(aligned_confusion),
            "gold_prohibition_to_pred_permission_signal_buckets": _sorted_counter(
                signal_buckets
            ),
            "predicted_permission_firing_audit": {
                "total_parent_permission_clauses": predicted_permission_total,
                "expected_trigger_total": firing_total,
                "by_evidence_type": _sorted_counter(firing_by_evidence),
                "by_signal_family": _sorted_counter(firing_by_family),
                "by_parent_route": _sorted_counter(firing_by_route),
                "by_support": _sorted_counter(firing_by_supported),
                "gold_distribution_development_diagnostic_only": _sorted_counter(
                    firing_gold_distribution
                ),
                "sample_id_list_persisted": False,
            },
            "estimated_effect": {
                "recoverable_prohibition_tp_upper_bound": recoverable,
                "possible_permission_tp_loss": permission_loss,
                "expected_trigger_total": firing_total,
                "at_least_three_errors_share_generic_rule_family": recoverable >= 3,
            },
            "instantiation": {
                "decision": "instantiated" if instantiated else "not_instantiated",
                "conditions": conditions,
                "single_hypothesis": "permission_to_prohibition_strong_negation_scope",
                "fixed_confidence_if_instantiated": 0.8,
            },
            "fixed_scope": {
                "english_evidence_types": [row[1] for row in ENGLISH_EVIDENCE],
                "german_is_auxiliary_only": True,
                "exclusions": [row[0] for row in EXCLUSION_PATTERNS]
                + [
                    "quoted_or_mentioned_negation",
                    "definition_negation_mention",
                    "condition_or_exception_only_not_main_nucleus",
                    "german_muss_nicht",
                    "factual_can_not_or_cannot",
                ],
                "record_classifier_used_for_override": False,
                "sample_specific_logic": False,
            },
            "safety": {
                "gold_read_only": True,
                "independent82_read_or_used": False,
                "s2_4_test_read": False,
                "network_called": False,
                "llm_api_called": False,
                "model_or_corenlp_run": False,
                "production_resolver_created_by_this_script": False,
            },
        }

        staging = OUTPUT_DIR.parent / f".{OUTPUT_DIR.name}.staging-{os.getpid()}"
        if staging.exists():
            raise Estg150B0DevelopmentError(f"staging path exists: {staging}")
        staging.mkdir(parents=True)
        try:
            summary_path = staging / "summary.json"
            _write_json(summary_path, summary)
            bindings = {
                "v10_attempts": V10_ATTEMPTS,
                "v10_evaluation": V10_EVALUATION,
                "v10_manifest": V10_MANIFEST,
                "layer_e": LAYER_E,
                "membership": MEMBERSHIP,
                "evaluator": EVALUATOR,
                "diagnostic_script": Path(__file__).resolve(),
            }
            manifest = {
                "schema_version": "b2b_prohibition_diagnostic_manifest@1.0.0",
                "diagnostic_id": RUN_ID,
                "status": "instantiation_conditions_met"
                if instantiated
                else "not_instantiated",
                "claim_scope": "development_diagnostic_only",
                "input_bindings": {
                    name: {
                        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "sha256": sha256_file(path),
                        "bytes": path.stat().st_size,
                    }
                    for name, path in bindings.items()
                },
                "artifacts": {
                    "summary": {
                        "path": "summary.json",
                        "sha256": sha256_file(summary_path),
                        "bytes": summary_path.stat().st_size,
                    }
                },
                "instantiation": summary["instantiation"],
                "safety": summary["safety"],
            }
            _write_json(staging / "manifest.json", manifest)
            staging.rename(OUTPUT_DIR)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    except (Estg150B0DevelopmentError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"B2b diagnostic failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
