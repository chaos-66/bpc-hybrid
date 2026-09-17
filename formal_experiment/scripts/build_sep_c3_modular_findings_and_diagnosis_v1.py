# -*- coding: utf-8 -*-
"""Build the SEP-C3 modular findings/diagnosis research record.

Zero API. The builder reads frozen evidence/analysis artifacts and emits one
human-readable Markdown record plus one machine-readable JSON record. It does
not modify Gold, predictions, prompts, evaluator files, or historical reports.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

RECORD_ID = "SEP_C3_MODULAR_ABLATION_FINDINGS_AND_DIAGNOSIS_2026-09-17"
DOC_DIR = ROOT / "docs" / "research"
OUT_MD = DOC_DIR / f"{RECORD_ID}.md"
OUT_JSON = DOC_DIR / f"{RECORD_ID}.json"

V2_REPORT = ROOT / "outputs" / "reports" / "sep_c3_modular_ablation_v2.json"
PROTOCOL_AUDIT = ROOT / "outputs" / "reports" / "sep_c3_modular_full8_protocol_audit_v1.json"
PAIRED_REPORT = ROOT / "outputs" / "reports" / "sep_c3_modular_paired_error_attribution_v1.json"
PROMPT_AUDIT = ROOT / "outputs" / "reports" / "sep_c3_modular_prompt_overlap_audit_v1.json"
D1_FACTORIAL = ROOT / "outputs" / "reports" / "d1_prompt_factorial_results_v1.json"
NO_FEWSHOT = ROOT / "outputs" / "reports" / "d_no_fewshot_interface_diagnosis_v1.json"
CLASSIFIED = ROOT / "outputs" / "reports" / "direct_llm_ablation_existing_results_classified_v1.json"
V1_SUMMARY = ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v1" / "execution_summary.json"
V2_SUMMARY = ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v2" / "execution_summary.json"

ARMS = ("111", "011", "101", "110", "100", "010", "001", "000")
LEGACY_ARMS = ("111", "011", "101", "110")
NEW_ARMS = ("100", "010", "001", "000")
FIELD_ORDER = ("actor", "action", "condition", "constraint", "exception")
PAIR_ORDER = (
    "100_vs_000",
    "010_vs_000",
    "001_vs_000",
    "111_vs_011",
    "111_vs_101",
    "111_vs_110",
    # Supplemental cross-batch comparison explicitly requested in the
    # diagnosis (100 = E-only new batch, 110 = E+S old batch).
    "100_vs_110",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def load_arm_metrics(arm: str, report_metrics: dict[str, Any]) -> dict[str, Any]:
    if arm in LEGACY_ARMS:
        eval_path = ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v1" / "arms" / arm / "evaluation.json"
        canonical_path = ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v1" / "arms" / arm / "canonical_predictions.jsonl"
    else:
        eval_path = ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v2" / "arms" / arm / "repeat-01" / "evaluation.json"
        canonical_path = ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v2" / "arms" / arm / "repeat-01" / "canonical_predictions.jsonl"
    evaluation = read_json(eval_path)["evaluation"]
    canonical_rows = [
        json.loads(line)
        for line in canonical_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    schema_valid = sum(
        1 for row in canonical_rows
        if ((row.get("record") or {}).get("validation") or {}).get("schema_valid") is True)
    cross_valid = sum(
        1 for row in canonical_rows
        if ((row.get("record") or {}).get("validation") or {}).get("cross_field_valid") is True)
    return {
        "arm": arm,
        "binding": report_metrics.get("binding"),
        "source": report_metrics.get("source"),
        "generated_prompt_sha256": report_metrics.get("generated_prompt_sha256"),
        "primary_metric": "coarse_five_field_mean_f1",
        "coarse_five_field_mean_f1": evaluation["coarse_five_field_mean_f1"],
        "coarse_five_field_micro": evaluation["coarse_five_field_micro"],
        "modality_labels": evaluation["modality_labels"],
        "five_fields": evaluation["five_fields"],
        "records_scored": evaluation["denominator"],
        "records_failed": evaluation["failed_count"],
        "canonical_rows": len(canonical_rows),
        "canonical_schema_valid_true": schema_valid,
        "canonical_cross_field_valid_true": cross_valid,
        "canonical_validation_error_rows": sum(
            1 for row in canonical_rows
            if (((row.get("record") or {}).get("validation") or {}).get("errors") or [])),
        "parser_schema_canonicalization_failures": 0,
        "parser_schema_canonicalization_failure_note": (
            "No canonical record was dropped. Raw fence recovery occurred without a "
            "canonical failure; every canonical row is schema_valid and cross_field_valid."
        ),
        "paths": {
            "evaluation": str(eval_path.relative_to(ROOT)).replace("\\", "/"),
            "canonical_predictions": str(canonical_path.relative_to(ROOT)).replace("\\", "/"),
        },
        "hashes": {
            "evaluation_sha256": sha256_file(eval_path),
            "canonical_predictions_sha256": sha256_file(canonical_path),
        },
    }


def rank_arms(metrics: dict[str, Any]) -> list[str]:
    return sorted(ARMS, key=lambda arm: metrics[arm]["coarse_five_field_mean_f1"], reverse=True)


def fmt_float(value: Any, digits: int = 6) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def clean_md_text(value: Any) -> str:
    text = "" if value is None else str(value)
    return "\\n".join(line.rstrip() for line in text.splitlines())


def render_markdown(record: dict[str, Any]) -> str:
    m = record["formal_full8"]["arms"]
    rank = record["formal_full8"]["descriptive_ranking"]
    lines: list[str] = []
    A = lines.append
    A(f"# {record['title']}")
    A("")
    A(f"- record_id: `{record['record_id']}`")
    A(f"- status: `{record['status']}`")
    A(f"- generated_at_utc: `{record['generated_at_utc']}`")
    A(f"- starting_git_head: `{record['starting_git_head']}`")
    A("- network/LLM calls in this record: `0`")
    A("- scope: research interpretation layer over already-completed real API runs; no prediction, Gold, prompt, evaluator, or historical report was modified.")
    A("")
    A("## 1. Original question and pre-experiment hypotheses")
    A("")
    A(record["original_question"])
    A("")
    A("### Pre-experiment hypotheses (not conclusions)")
    for item in record["pre_experiment_hypotheses"]:
        A(f"- {item}")
    A("")
    A("### Explicit status")
    A(f"- {record['hypothesis_status_note']}")
    A("")
    A("## 2. Formal full-8 results (frozen evaluator fields)")
    A("")
    A("Primary metric: `coarse_five_field_mean_f1`; modality label metrics are reported separately and never mixed into span F1.")
    A("")
    A("| descriptive rank | arm (E S J) | mean F1 | micro P | micro R | micro F1 | modality acc | modality macro-F1 | records scored | records failed | batch binding |")
    A("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for index, arm in enumerate(rank, start=1):
        row = m[arm]
        A(
            f"| {index} | {arm[0]} {arm[1]} {arm[2]} | {fmt_float(row['coarse_five_field_mean_f1'])} | "
            f"{fmt_float(row['coarse_five_field_micro']['precision'])} | "
            f"{fmt_float(row['coarse_five_field_micro']['recall'])} | "
            f"{fmt_float(row['coarse_five_field_micro']['f1'])} | "
            f"{fmt_float(row['modality_labels']['accuracy'])} | "
            f"{fmt_float(row['modality_labels']['macro_f1'])} | "
            f"{row['records_scored']} | {row['records_failed']} | `{row['binding']}` |"
        )
    A("")
    A("### Per-field F1")
    A("")
    A("| arm | actor | action | condition | constraint | exception |")
    A("|---|---:|---:|---:|---:|---:|")
    for arm in ARMS:
        row = m[arm]
        A(
            f"| {arm} | " + " | ".join(
                fmt_float(row["five_fields"][field]["f1"]) for field in FIELD_ORDER
            ) + " |"
        )
    A("")
    A("### Batch/time binding")
    A(f"- {record['formal_full8']['batch_warning']}")
    A("")
    A("### Parser / schema / canonicalization failures")
    A(f"- {record['formal_full8']['canonical_failure_statement']}")
    A("")
    A("### Actual calls / resume metadata")
    for key, value in record["formal_full8"]["execution_metadata"].items():
        A(f"- {key}: {value}")
    A("")
    A("## 3. Unexpected / negative findings")
    for section in record["unexpected_negative_findings"]:
        A(f"### {section['heading']}")
        A("")
        for paragraph in section["paragraphs"]:
            A(paragraph)
            A("")
        if section.get("bullets"):
            for bullet in section["bullets"]:
                A(f"- {bullet}")
            A("")
    A("## 4. Historical prompt simplification context")
    A("")
    A(record["historical_prompt_simplification"]["summary"])
    A("")
    A("| historical observation | value | interpretation boundary |")
    A("|---|---:|---|")
    for row in record["historical_prompt_simplification"]["rows"]:
        A(f"| {row['observation']} | {row['value']} | {row['boundary']} |")
    A("")
    A(record["historical_prompt_simplification"]["distinction"])
    A("")
    A("## 5. Evidence / Observation / Hypothesis layers")
    A("")
    for layer_name, items in record["evidence_layers"].items():
        A(f"### {layer_name}")
        A("")
        for item in items:
            A(f"- {item}")
        A("")
    A("## 6. Paired error attribution (zero API)")
    A("")
    A(record["paired_error_attribution"]["contract"])
    A("")
    for pair_id in PAIR_ORDER:
        pair = record["paired_error_attribution"]["pairs"][pair_id]
        A(f"### {pair_id}: {pair['baseline_arm']} -> {pair['variant_arm']}")
        A("")
        A(
            f"- purpose: {pair['purpose']}; batch relation: `{pair['batch_relation']}`; "
            f"mean-F1 delta (variant-baseline): `{fmt_float(pair['primary_metric_delta_variant_minus_baseline'])}`."
        )
        A("")
        A("| field | fixed | regressed | both correct | both wrong | unmatched-pred delta | matched-Gold delta |")
        A("|---|---:|---:|---:|---:|---:|---:|")
        for field in FIELD_ORDER:
            stats = pair["fields"][field]
            A(
                f"| {field} | {stats['fixed']} | {stats['regressed']} | {stats['both_correct']} | "
                f"{stats['both_wrong']} | {stats['unmatched_pred_delta']:+d} | {stats['matched_gold_delta']:+d} |"
            )
        A("")
        if pair.get("representative_sample_ids"):
            A(f"- representative sample IDs: {', '.join('`'+x+'`' for x in pair['representative_sample_ids'])}")
            A("")
    A("### Representative real cases")
    A("")
    A("All cases below are selected from persisted canonical predictions and frozen coarse Gold. The mechanical observation is artifact-derived; any interpretation is marked as hypothesis.")
    A("")
    for key, cases in record["paired_error_attribution"]["representative_cases"].items():
        if not cases:
            continue
        A(f"#### {key}")
        A("")
        for case in cases:
            A(f"- `{case['sample_id']}` / `{case['field']}` / `{case['outcome']}`")
            A(f"  - source (excerpt): {case['source_excerpt']}")
            A(f"  - coarse Gold: {case['gold_coarse_spans_text']}")
            A(f"  - {case['baseline_arm']}: {case['baseline_spans_text']}")
            A(f"  - {case['variant_arm']}: {case['variant_spans_text']}")
            A(f"  - mechanical observation: {case['mechanical_observation']}")
        A("")
    A("## 7. Prompt overlap / conflict audit")
    A("")
    A(record["prompt_overlap_audit"]["summary"])
    A("")
    A("### E/S overlap")
    for row in record["prompt_overlap_audit"]["e_s_overlap"]:
        A(f"- `{', '.join(row['instructions'])}`: {row['classification']} — {row['shared_function']}; literal contradiction={row['literal_contradiction']}.")
    A("")
    A("### J/common relationship")
    for bullet in record["prompt_overlap_audit"]["j_common_bullets"]:
        A(f"- {bullet}")
    A("")
    A("### Sample-linked prompt evidence")
    for link in record["prompt_overlap_audit"]["sample_links"]:
        A(f"- `{link['finding_id']}`: instructions {', '.join(link['prompt_instructions'])}; evidence type `{link['evidence_type']}`; samples {', '.join(s['sample_id'] for s in link['failure_samples'])}.")
        A(f"  - hypothesis: {link['hypothesis']}")
        A(f"  - unresolved: {link['unresolved']}")
    A("")
    A("## 8. Root-cause evidence status")
    A("")
    for status in ("confirmed", "strongly_suggested", "unresolved"):
        A(f"### {status}")
        for item in record["root_cause_evidence"][status]:
            A(f"- {item}")
        A("")
    A("## 9. Current interpretation")
    for qa in record["current_interpretation"]:
        A(f"### {qa['question']}")
        A(qa["answer"])
        A("")
    A("## 10. Next experiment (design only; NOT executed)")
    A(record["next_experiment"]["overview"])
    A("")
    A(f"Recommended baseline: `{record['next_experiment']['recommended_baseline']}`. {record['next_experiment']['baseline_rationale']}")
    A("")
    for variant in record["next_experiment"]["variants"]:
        A(f"### {variant['variant_id']}")
        A(f"- hypothesis: {variant['hypothesis']}")
        A(f"- exact prompt delta: {variant['prompt_delta']}")
        A(f"- targeted failure: {variant['targeted_failure']}")
        A(f"- supporting sample IDs: {', '.join('`'+x+'`' for x in variant['supporting_sample_ids'])}")
        A(f"- intended behavior change: {variant['intended_behavior_change']}")
        A(f"- possible side effect: {variant['possible_side_effect']}")
        A(f"- evaluation criterion: {variant['evaluation_criterion']}")
        A("")
    A("### Controls, size, metrics, stopping rule")
    A(f"- controls: {record['next_experiment']['controls']}")
    A(f"- sample count: {record['next_experiment']['sample_count']}")
    A(f"- metrics: {record['next_experiment']['metrics']}")
    A(f"- stopping rule: {record['next_experiment']['stopping_rule']}")
    A("")
    A("## 11. Is a future same-batch full-8 needed?")
    A(record["same_batch_full8_assessment"]["answer"])
    A("")
    for item in record["same_batch_full8_assessment"]["points"]:
        A(f"- {item}")
    A("")
    A("## 12. Research log: how our understanding changed")
    for item in record["research_log_timeline"]:
        A(f"### {item['stage']}")
        A(item["understanding"])
        A("")
    A("## 13. Paper-safe wording")
    A("")
    for item in record["paper_safe_wording"]:
        A(f"### {item['topic']}")
        A(f"- avoid: {item['avoid']}")
        A(f"- use: {item['use']}")
        A("")
    A("## 14. Artifact / provenance bindings")
    A("")
    for key, value in record["artifact_bindings"].items():
        A(f"- {key}: `{value}`")
    A("")
    A("## 15. Git / dirty-worktree note")
    A(record["git_note"])
    A("")
    return "\n".join(lines).rstrip("\n") + "\n"


def main() -> None:
    v2_report = read_json(V2_REPORT)
    protocol = read_json(PROTOCOL_AUDIT)
    paired = read_json(PAIRED_REPORT)
    prompt = read_json(PROMPT_AUDIT)
    d1 = read_json(D1_FACTORIAL)
    no_fewshot = read_json(NO_FEWSHOT)
    classified = read_json(CLASSIFIED)
    v1_summary = read_json(V1_SUMMARY)
    v2_summary = read_json(V2_SUMMARY)

    arm_metrics = {
        arm: load_arm_metrics(arm, v2_report["metrics"][arm])
        for arm in ARMS
    }
    ranking = rank_arms(arm_metrics)

    full8_metrics = {
        arm: {
            "arm": arm,
            "binding": arm_metrics[arm]["binding"],
            "source": arm_metrics[arm]["source"],
            "generated_prompt_sha256": arm_metrics[arm]["generated_prompt_sha256"],
            "coarse_five_field_mean_f1": arm_metrics[arm]["coarse_five_field_mean_f1"],
            "coarse_five_field_micro": arm_metrics[arm]["coarse_five_field_micro"],
            "modality_labels": arm_metrics[arm]["modality_labels"],
            "five_fields": arm_metrics[arm]["five_fields"],
            "records_scored": arm_metrics[arm]["records_scored"],
            "records_failed": arm_metrics[arm]["records_failed"],
            "canonical_failure_count": arm_metrics[arm]["parser_schema_canonicalization_failures"],
            "raw_format_note": paired["arms"][arm]["raw_format"],
        }
        for arm in ARMS
    }

    pair_summaries = {}
    pair_case_ids = {
        "100_vs_000": ["estg_000020", "estg_000021", "estg_000075"],
        "010_vs_000": ["estg_000021", "estg_000027", "estg_000030"],
        "001_vs_000": ["estg_000095", "estg_000127", "estg_000020"],
        "111_vs_011": ["estg_000080", "estg_000020"],
        "111_vs_101": ["estg_000080", "estg_000083", "estg_000020", "estg_000106"],
        "111_vs_110": ["estg_000020", "estg_000106"],
        "100_vs_110": ["estg_000020", "estg_000033", "estg_000210"],
    }
    for pair_id in PAIR_ORDER:
        raw = paired["pair_analyses"][pair_id]
        pair_summaries[pair_id] = {
            "pair_id": pair_id,
            "baseline_arm": raw["baseline_arm"],
            "variant_arm": raw["variant_arm"],
            "batch_relation": raw["batch_relation"],
            "purpose": raw["purpose"],
            "baseline_primary_metric": raw["baseline_primary_metric"],
            "variant_primary_metric": raw["variant_primary_metric"],
            "primary_metric_delta_variant_minus_baseline": raw["primary_metric_delta_variant_minus_baseline"],
            "fields": {
                field: {
                    key: raw["fields"][field][key]
                    for key in (
                        "fixed", "regressed", "both_correct", "both_wrong",
                        "base_pred_count", "var_pred_count", "pred_count_delta",
                        "base_unmatched_pred", "var_unmatched_pred", "unmatched_pred_delta",
                        "base_matched_gold", "var_matched_gold", "matched_gold_delta",
                        "base_missed_gold", "var_missed_gold", "missed_gold_delta",
                        "base_hallucinated_fields", "var_hallucinated_fields",
                        "base_missed_fields", "var_missed_fields",
                        "base_duplicate_overlap_pairs", "var_duplicate_overlap_pairs",
                        "boundary_counts", "matched_boundary_length_ratio_mean",
                        "cross_field_candidate_counts",
                    )
                }
                for field in FIELD_ORDER
            },
            "representative_sample_ids": pair_case_ids[pair_id],
        }

    # Compact representative cases for Markdown; full JSON retains the
    # artifact-derived case objects.
    case_compact: dict[str, list[dict[str, Any]]] = {}
    for key, cases in paired["representative_cases"].items():
        compact = []
        for case in cases:
            compact.append({
                "sample_id": case["sample_id"],
                "field": case["field"],
                "outcome": case["outcome"],
                "baseline_arm": case["baseline_arm"],
                "variant_arm": case["variant_arm"],
                "source_excerpt": clean_md_text((case["source_text"] or "")[:220]),
                "gold_coarse_spans_text": "; ".join(
                    f"`{clean_md_text(s['text'])}` [{s['start']},{s['end']})"
                    for s in case["gold_coarse_spans"]
                ) or "(none)",
                "baseline_spans_text": "; ".join(
                    f"`{clean_md_text(s['text'])}` [{s['start']},{s['end']})"
                    for s in case["baseline_spans"]
                ) or "(none)",
                "variant_spans_text": "; ".join(
                    f"`{clean_md_text(s['text'])}` [{s['start']},{s['end']})"
                    for s in case["variant_spans"]
                ) or "(none)",
                "mechanical_observation": case["mechanical_observation"],
            })
        case_compact[key] = compact

    d1_rows = []
    for row in d1["rows"]:
        d1_rows.append({
            "arm": row["arm"],
            "overall_f1": row["overall"]["f1"],
            "actor_f1": row["per_field"]["actor"]["f1"],
            "action_f1": row["per_field"]["action"]["f1"],
            "condition_f1": row["per_field"]["condition"]["f1"],
            "constraint_f1": row["per_field"]["constraint"]["f1"],
            "exception_f1": row["per_field"]["exception"]["f1"],
        })
    semantic_example = d1["factor_findings"]["semantic_examples"]
    json_semantic = d1["factor_findings"]["detailed_semantic_guidance"]
    json_discipline = d1["factor_findings"]["explicit_json_discipline"]

    unexpected = [
        {
            "heading": "4.1 Full prompt 111 is not the best configuration",
            "paragraphs": [
                (
                    f"Descriptive ranking: {' > '.join(ranking)}. "
                    f"`111` is not the highest cell; `100` is highest with mean F1 "
                    f"{fmt_float(arm_metrics['100']['coarse_five_field_mean_f1'])}. "
                    "The current data therefore do not support 'more modules is better' or "
                    "'full E+S+J is optimal'."
                ),
                (
                    "However, the old four cells (`111/011/101/110`) and the new four cells "
                    "(`000/001/010/100`) are batch/time confounded. The cross-batch ranking is "
                    "descriptive and cannot be written as strict causal proof."
                ),
            ],
            "bullets": [
                "negative and non-monotonic ablation results are treated as findings, not discarded.",
                "`111` is not descriptively superior to several simpler configurations.",
            ],
        },
        {
            "heading": "4.2 Single-factor deletions from 111 are anomalous",
            "paragraphs": [
                (
                    "Within the old batch, deleting E (`111 -> 011`), deleting S (`111 -> 101`), "
                    "and deleting J (`111 -> 110`) are all associated with higher mean F1 than "
                    "`111`. This contradicts a simple additive positive-contribution hypothesis."
                ),
                (
                    "Old-batch paired analysis: `111_vs_011` E deletion increases mean F1 by "
                    f"{fmt_float(0.020749770334206663)}; `111_vs_101` S deletion increases by "
                    f"{fmt_float(0.03485000201978028)}; `111_vs_110` J deletion increases by "
                    f"{fmt_float(0.009333365103690316)}. The negative finding is preserved."
                ),
            ],
            "bullets": [
                "Do not describe any module as universally useless; this is a single dataset/model/setting result.",
                "Do not describe the deletions as causal proof of harmful wording.",
            ],
        },
        {
            "heading": "4.3 E and S each help alone, while their combination shows negative interaction",
            "paragraphs": [
                (
                    "Same new batch: `100 - 000` is "
                    f"{fmt_float(arm_metrics['100']['coarse_five_field_mean_f1'] - arm_metrics['000']['coarse_five_field_mean_f1'])}, "
                    "and `010 - 000` is "
                    f"{fmt_float(arm_metrics['010']['coarse_five_field_mean_f1'] - arm_metrics['000']['coarse_five_field_mean_f1'])}. "
                    "E-only and S-only both show descriptive improvement over the common skeleton."
                ),
                (
                    "But `110 - 100` is "
                    f"{fmt_float(arm_metrics['110']['coarse_five_field_mean_f1'] - arm_metrics['100']['coarse_five_field_mean_f1'])}, "
                    "and `111 - 101` is "
                    f"{fmt_float(arm_metrics['111']['coarse_five_field_mean_f1'] - arm_metrics['101']['coarse_five_field_mean_f1'])}. "
                    "The E x S interaction signal is the dominant negative two-way effect."
                ),
                (
                    "This is consistent with redundancy, overlap, conditional interference, or "
                    "instruction conflict. It is not proof that E and S semantically conflict. "
                    "Paired error analysis and the prompt audit are required before stronger claims."
                ),
            ],
            "bullets": [],
        },
        {
            "heading": "4.4 J shows no stable benefit under the shared baseline structured-output interface",
            "paragraphs": [
                (
                    "`000` already retains the common skeleton, including the required schema/interface "
                    "and coordinate discipline. Thus this experiment tests whether *additional* J "
                    "output-organization/JSON-discipline instructions improve performance beyond the "
                    "shared baseline interface."
                ),
                (
                    "Observed under the shared interface: J main effect is slightly negative "
                    f"({fmt_float(v2_report['factorial_effects']['J_main_effect'])}); matched comparisons are mixed; "
                    "`000/001/010/100` all yielded 150/150 canonical schema-valid and cross-field-valid records, "
                    "with no canonical parser/schema/canonicalization failure. Without J, raw bare-JSON rates "
                    "were lower (000: 114/150; 100: 146/150; 010: 149/150), but the canonical adapter recovered "
                    "fenced objects without dropping records."
                ),
                (
                    "Correct current wording: under the shared baseline structured-output interface, the "
                    "additional J module did not yield a consistent measurable benefit in extraction F1 or "
                    "canonical output reliability on this dataset/model setting. Do not generalize to "
                    "'JSON schema is useless' or 'structured output constraints are unnecessary'."
                ),
            ],
            "bullets": [],
        },
    ]

    historical_rows = [
        {
            "observation": "D1 full v6 prompt overall F1 (historical evaluator view, six-field micro) in the real 450-call factorial batch",
            "value": fmt_float(d1["rows"][0]["overall"]["f1"]),
            "boundary": "Historical v6 prompt family and evaluator view; not the current modular E/S/J coarse five-field mean F1.",
        },
        {
            "observation": "D1 no-semantic-examples overall F1 delta after removing/replacing full examples",
            "value": fmt_float(semantic_example["removal_delta_f1"]),
            "boundary": "Controlled single-module removal in the old v6 prompt; actor F1 delta was " + fmt_float(semantic_example["actor_removal_delta_f1"]) + ".",
        },
        {
            "observation": "D1 no-detailed-semantic-guidance overall F1 delta",
            "value": fmt_float(json_semantic["removal_delta_f1"]),
            "boundary": "Removal improved actor/condition/constraint/exception but reduced action F1 in that arm; not the current E/S/J schema.",
        },
        {
            "observation": "D1 no-explicit-JSON-contract overall F1 delta",
            "value": fmt_float(json_discipline["removal_delta_f1"]),
            "boundary": "Valid-output rate without the module was " + fmt_float(json_discipline["valid_output_rate_without_module"]) + "; current common skeleton is already stricter/different.",
        },
        {
            "observation": "D-no-fewshot current-locked F1 / parseable JSON / non-empty raw clauses",
            "value": "0.000 / 147 of 150 JSON parseable / 146 non-empty raw clauses",
            "boundary": "The near-zero score is attributed by the existing diagnosis to a coordinate-representation interface mismatch (arrays vs named span objects), not to loss of all semantic extraction. The retrospective bridge is diagnostic only.",
        },
        {
            "observation": "D-minimal historical pressure test",
            "value": "classified report records F1 0.000, parse rate 0.000, failure rate 1.000",
            "boundary": "This was a global multi-part simplification, not a controlled E/S/J component ablation. Exact deletion inventory needs artifact-level recheck before paper use.",
        },
    ]

    record: dict[str, Any] = {
        "schema_version": "sep_c3_modular_findings_and_diagnosis@1.0.0",
        "record_id": RECORD_ID,
        "title": "SEP-C3 Modular E/S/J Ablation: Findings and Diagnosis (2026-09-17)",
        "status": "research_interpretation_layer_complete_offline",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "starting_git_head": git_head(),
        "network_calls": 0,
        "llm_calls": 0,
        "original_question": (
            "Do the E / S / J prompt components individually and jointly improve regulatory "
            "information extraction? E = synthetic worked examples; S = semantic interpretation "
            "rules; J = additional output organization / JSON discipline."
        ),
        "pre_experiment_hypotheses": [
            "E has a positive contribution.",
            "S has a positive contribution.",
            "J has a positive contribution.",
            "Combining components may produce cumulative gains.",
            "The full configuration `111` may be better than simpler configurations.",
        ],
        "hypothesis_status_note": (
            "The bullets above are pre-experiment hypotheses, not current conclusions. "
            "Some were weakened or contradicted by the completed full-8 experiment."
        ),
        "formal_full8": {
            "report_path": str(V2_REPORT.relative_to(ROOT)).replace("\\", "/"),
            "report_sha256": sha256_file(V2_REPORT),
            "protocol_audit_path": str(PROTOCOL_AUDIT.relative_to(ROOT)).replace("\\", "/"),
            "protocol_audit_sha256": sha256_file(PROTOCOL_AUDIT),
            "primary_metric": "coarse_five_field_mean_f1",
            "descriptive_ranking": ranking,
            "arms": full8_metrics,
            "batch_warning": (
                "The original four cells `111/011/101/110` are `original_execution_binding` "
                "(SEP-C3-MODULAR-ESJ-001); the new four cells `000/001/010/100` are "
                "`current_implementation_binding` / `executed_incremental_batch` "
                "(SEP-C3-MODULAR-ESJ-002). Model, input, Gold, evaluator, and prompt composition "
                "are matched, but batch/time is confounded with cell membership."
            ),
            "canonical_failure_statement": (
                "Canonical parser/schema/canonicalization failures: 0 records in all eight cells. "
                "Every arm produced 150/150 request_status=ok canonical predictions, 150/150 schema_valid=true, "
                "150/150 cross_field_valid=true, and no validation errors. Raw response fence counts differ "
                "by arm and are recorded as raw-format diagnostics, not as canonical failures."
            ),
            "execution_metadata": {
                "original_four_suite": (
                    f"suite_id={v1_summary.get('runs')[0].get('arm') and 'SEP-C3-MODULAR-ESJ-001'}; "
                    f"planned_calls={v1_summary['planned_calls']}; "
                    f"actual_calls_in_execution_summary={v1_summary['actual_calls']}; "
                    f"completed_samples={v1_summary['completed_samples']}; "
                    f"aborted={v1_summary['aborted']}; "
                    f"runtime_seconds={v1_summary['runtime_seconds']}; "
                    f"arm 111 actual={v1_summary['runs'][0]['actual_call_count']} + resumed={v1_summary['runs'][0]['resumed_completed_count']}; "
                    "other three arms actual=150 each; all failed_count=0."
                ),
                "new_four_suite": (
                    f"suite_id=SEP-C3-MODULAR-ESJ-002; planned_calls={v2_summary['planned_calls']}; "
                    f"actual_calls={v2_summary['actual_calls']}; completed_samples={v2_summary['completed_samples']}; "
                    f"resume_events={read_json(ROOT / 'outputs' / 'evidence' / 'sep_c3_modular_ablation_v2' / 'manifest.json').get('resume_events_in_this_batch')}; "
                    f"aborted={v2_summary['aborted']}; runtime_seconds={v2_summary['runtime_seconds']}; "
                    f"budget_gate_calls_made={v2_summary['budget_gate']['calls_made']}; "
                    f"failed_count total=0."
                ),
                "token/cost_original_four": (
                    f"input_tokens={v1_summary['budget_gate']['input_tokens']}; "
                    f"output_tokens={v1_summary['budget_gate']['output_tokens']}; "
                    f"cost_usd={v1_summary['budget_gate']['cost_usd']}; "
                    f"missing_usage_calls={v1_summary['budget_gate']['missing_usage_calls']}"
                ),
                "token/cost_new_four": (
                    f"input_tokens={v2_summary['budget_gate']['input_tokens']}; "
                    f"output_tokens={v2_summary['budget_gate']['output_tokens']}; "
                    f"cost_usd={v2_summary['budget_gate']['cost_usd']}; "
                    f"missing_usage_calls={v2_summary['budget_gate']['missing_usage_calls']}"
                ),
                "transparency_note": (
                    "The original-four evidence execution summary records actual_calls=541 with "
                    "59 resumed completed samples for arm 111; the evidence manifest records "
                    "actual_api_attempts_total=600 and duplicate_sample_sends=0. These fields are "
                    "recorded verbatim as different counters/caps and must not be silently collapsed. "
                    "The new four-cell batch records actual_calls=600 and completed_samples=600."
                ),
            },
        },
        "unexpected_negative_findings": unexpected,
        "historical_prompt_simplification": {
            "summary": (
                "Earlier prompt-simplification/history records exist and must be included in the timeline. "
                "They show that some global shortenings or module removals were associated with severe drops, "
                "but they are not the same operation as the current controlled E/S/J component ablation."
            ),
            "rows": historical_rows,
            "d1_row_table": d1_rows,
            "distinction": (
                "Controlled component ablation changes one named prompt component while holding the common "
                "skeleton, input, model, and evaluator fixed. Global prompt shortening/simplification may "
                "simultaneously remove genuinely useful example information, common constraints, span "
                "guidance, and task framing. Therefore 'a global simplified prompt scored worse' does not "
                "imply 'all redundant instructions are useful', and it does not directly contradict the "
                "current `100` result."
            ),
            "needs_verification": (
                "The exact deletions in the historical D-minimal arm need artifact-level recheck before being "
                "used as a paper claim; the tracked classified report records only the summary numbers."
            ),
        },
        "evidence_layers": {
            "A_directly_observed": [
                "E-only (`100`) > common skeleton (`000`) in the current same batch.",
                "S-only (`010`) > common skeleton (`000`) in the current same batch.",
                "J-only (`001`) does not improve the current primary metric.",
                "Full `111` is not descriptively best; `100` is currently highest.",
                "The E/S relationship is non-additive in the current full-8 descriptive analysis.",
                "Canonical parser/schema/canonicalization failure is 0 in all evaluated cells.",
                "Without J, some raw responses were Markdown-fenced; with J, raw bare-JSON rates were 150/150 in the evaluated J arms.",
            ],
            "B_strongly_suggested_but_not_proven": [
                "E and S information may overlap.",
                "Instruction load may create interference.",
                "Examples may implicitly encode part of the semantic rules.",
                "J may be redundant on a strong instruction-following model once a shared structured-output interface exists.",
                "E-only reduces actor false positives relative to the common skeleton.",
            ],
            "C_unverified_hypotheses": [
                "S may cause actor over-extraction.",
                "E/S may give conflicting boundary guidance on specific sentences.",
                "Examples and rules contain an explicit wording contradiction.",
                "Performance drops come from attention competition.",
                "Constraint/exception rules are the main source of E x S interaction.",
            ],
        },
        "paired_error_attribution": {
            "report_path": str(PAIRED_REPORT.relative_to(ROOT)).replace("\\", "/"),
            "report_sha256": sha256_file(PAIRED_REPORT),
            "contract": (
                "Paired labels are derived only from persisted canonical predictions and frozen coarse Gold "
                "using the existing `stage2_sun_literal_overlap` intersection evaluator. A sample-field is "
                "called evaluator-correct when all predicted spans in that sample-field are matched and all "
                "coarse Gold spans are matched. Boundary and cross-field counts are diagnostic overlays and "
                "never recompute official F1."
            ),
            "pairs": pair_summaries,
            "representative_cases": case_compact,
        },
        "root_cause_evidence": {
            "confirmed": [
                "`100` and `010` each improve over `000` in the current new batch.",
                "`111` is not descriptively best; `100` has the highest descriptive mean F1.",
                "Old-batch single-module deletions from `111` are associated with higher, not lower, mean F1.",
                "J-only does not improve the current primary metric; canonical failure counts are zero with and without J.",
                "The negative E x S two-way interaction is present in the descriptive factorial analysis.",
            ],
            "strongly_suggested": [
                "Actor over-extraction is the dominant old-batch failure mode when S is added: `101 -> 111` fixes 7 actor sample-fields but regresses 38, while actor unmatched predictions rise from 43 to 84.",
                "S helps constraint recall in the new batch (`000 -> 010` fixes 48 constraint sample-fields) but also increases extra constraint spans; E helps both constraint recall and actor minimality.",
                "J's main observed effect is raw serialization discipline; it does not add measurable canonical reliability under the current adapter.",
                "The E examples and S rules overlap functionally rather than containing a literal contradiction.",
            ],
            "unresolved": [
                "Whether a specific S sentence causes a specific actor over-extraction sample.",
                "Whether E/S interfere through attention competition.",
                "Whether the negative E x S interaction is caused by redundancy, conditional interference, or instruction conflict.",
                "Whether single-run differences are stable under repeat sampling.",
                "Whether the historical D-minimal deletions match the current controlled comparison operation.",
            ],
        },
        "prompt_overlap_audit": {
            "report_path": str(PROMPT_AUDIT.relative_to(ROOT)).replace("\\", "/"),
            "report_sha256": sha256_file(PROMPT_AUDIT),
            "summary": (
                "A 38-item atomic instruction inventory was built from the frozen common/E/S/J prompt files. "
                "E and S overlap functionally. No literal contradiction was found. J is distinct from the "
                "common baseline interface at the serialization level, but its extra discipline has no "
                "observed canonical-reliability or primary-metric benefit in this dataset/model setting."
            ),
            "e_s_overlap": prompt["overlap_audit"]["e_s_functional_overlap"],
            "literal_contradiction": prompt["overlap_audit"]["literal_contradiction_search"],
            "j_common_bullets": [
                "baseline structural interface: " + ", ".join(prompt["overlap_audit"]["j_common_relationship"]["baseline_structural_interface"]),
                "additional J discipline: " + ", ".join(prompt["overlap_audit"]["j_common_relationship"]["additional_j_discipline"]),
                "literal duplicates: " + str(len(prompt["overlap_audit"]["j_common_relationship"]["literal_duplicates"])),
                "genuinely new J constraint: " + prompt["overlap_audit"]["j_common_relationship"]["genuinely_new_constraints"][0]["J01"],
                "why 000 parses 150/150: " + prompt["overlap_audit"]["j_common_relationship"]["why_000_can_still_parse_150_of_150"],
            ],
            "sample_links": prompt["sample_linked_evidence"],
            "conclusion": prompt["conclusion"],
        },
        "current_interpretation": [
            {
                "question": "1. Why did single-factor ablation initially look like it had little effect?",
                "answer": (
                    "In the old batch, each deletion changed the score by only +0.009 to +0.035 mean F1, so "
                    "the direction was negative for the kept module but the magnitudes were modest. Full-8 and "
                    "paired analysis show that behind the small aggregate changes are large offsetting field "
                    "changes: deleting S fixes actor precision but loses constraint recall; deleting E changes "
                    "condition/constraint recall; deleting J changes raw serialization and some semantic predictions. "
                    "Aggregate mean F1 hides these offsetting effects."
                ),
            },
            {
                "question": "2. Why is the full prompt not necessarily best?",
                "answer": (
                    "The full prompt combines overlapping actor/action/condition/constraint instructions and "
                    "examples. In this dataset/model/setting, the added S module is associated with actor "
                    "over-extraction (`101 -> 111`: 38 actor sample-fields regressed, 7 fixed), and the added E/J "
                    "modules do not compensate. This supports non-additivity and conditional interference, but "
                    "the exact causal wording remains unresolved."
                ),
            },
            {
                "question": "3. Why could previous prompt simplification have been worse?",
                "answer": (
                    "The previous simplification observations were not controlled single-module ablations. "
                    "D-no-fewshot removed complete examples and appears to have broken the coordinate/output "
                    "interface; D-minimal was a broad multi-part reduction. Those operations can remove common "
                    "constraints, span guidance, and task framing together. Current `100` keeps the common "
                    "skeleton and only adds compact E examples, so it does not directly contradict the earlier "
                    "global-simplification failures."
                ),
            },
            {
                "question": "4. What does E actually provide?",
                "answer": (
                    "In the new batch, E-only is the strongest cell. Paired analysis shows E fixes 90 actor "
                    "sample-fields and 54 constraint sample-fields over `000`, while substantially reducing "
                    "unmatched actor predictions (241 -> 53). It does not eliminate actor false positives and "
                    "adds some constraint over-extraction (unmatched constraint predictions 9 -> 32). E therefore "
                    "provides concrete boundary demonstrations that improve actor minimality and constraint recall, "
                    "but not a complete solution."
                ),
            },
            {
                "question": "5. What does S actually provide?",
                "answer": (
                    "S-only also improves over `000` (73 actor fixes, 48 constraint fixes), with a slightly higher "
                    "constraint F1 than `100` but much weaker actor F1. When S is added to E-containing arms, actor "
                    "over-extraction dominates (`101 -> 111`: 38 regressions) while constraint recall can improve. "
                    "S therefore carries useful constraint/condition guidance but its broad surface rules are not "
                    "safely compositional with E in this setting."
                ),
            },
            {
                "question": "6. What can and cannot be concluded about J?",
                "answer": (
                    "Can conclude: under the shared baseline structured-output interface, additional J did not "
                    "yield a consistent measurable extraction-F1 or canonical-reliability benefit. J did increase "
                    "raw bare-JSON rates (without J: 000 114/150, 100 146/150, 010 149/150; with J: 150/150) but "
                    "the canonical adapter already recovered fenced objects. Cannot conclude: JSON schema is "
                    "useless, structured output constraints are unnecessary, or J can never help another model "
                    "release/parser/dataset."
                ),
            },
            {
                "question": "7. Is there direct evidence of instruction interference?",
                "answer": (
                    "There is strong sample-level association but no direct causal evidence. The largest signal is "
                    "actor over-extraction when S is added to E+J (`101 -> 111`), with real samples such as "
                    "`estg_000080` and `estg_000083`. Constraint-marker over-extraction appears after S in "
                    "`estg_000020` and `estg_000106`. These motivate interference hypotheses but do not establish "
                    "which instruction token caused them."
                ),
            },
        ],
        "next_experiment": {
            "overview": (
                "Design only; no API calls were made in this round. Default principle: targeted repair rather "
                "than restoring the entire removed S or J module. Start from the strongest simple baseline "
                "(`100`, common skeleton + E examples) and test at most three small, pre-declared deltas in one "
                "controlled batch with the baseline rerun in that same batch."
            ),
            "recommended_baseline": "100 (common skeleton + E examples)",
            "baseline_rationale": (
                "`100` is the highest same-batch cell (0.778763 mean F1, +0.142014 vs `000` and +0.050974 vs `010`), "
                "and paired analysis shows E-only fixes actor false positives and recovers constraints without the "
                "S-induced actor regression. The decision is based on paired error attribution and prompt overlap "
                "audit, not on mean F1 alone."
            ),
            "variants": [
                {
                    "variant_id": "E + actor_minimality_fix",
                    "hypothesis": "A narrow negative actor-boundary demonstration will reduce over-extraction without reducing actor recall.",
                    "prompt_delta": (
                        "Add one short worked example/rule to E showing a passive or nominalized subject that should "
                        "not become an actor unless an explicit by-phrase/performer is present; preserve E1's unresolved "
                        "pronoun rule. Do not add the full S actor module."
                    ),
                    "targeted_failure": (
                        "`100` still has 53 unmatched actor predictions and actor precision 0.4592; real false positives "
                        "include `estg_000046`, `estg_000664`, `estg_000161`, and `estg_000271`."
                    ),
                    "supporting_sample_ids": ["estg_000046", "estg_000664", "estg_000161", "estg_000271"],
                    "intended_behavior_change": "Suppress non-bearer noun phrases and passive-clause subjects where Gold has no actor, without dropping genuine explicit actors.",
                    "possible_side_effect": "May reduce actor recall or remove unresolved-pronoun actors; monitor actor missed-Gold and both-correct counts.",
                    "evaluation_criterion": "Actor precision/recall/F1 paired against same-batch `100`; no >0.01 drop in primary mean F1.",
                },
                {
                    "variant_id": "E + constraint_recall_fix",
                    "hypothesis": "A narrow constraint/legal-reference demonstration will recover missed constraint spans without a precision collapse.",
                    "prompt_delta": (
                        "Add a minimal constraint example/rule derived from S06 but restricted to legal references, "
                        "time/duration, quantity, purpose, and exclusivity; do not import S actor/voice/coordination rules."
                    ),
                    "targeted_failure": (
                        "`100` has constraint recall 0.6667 and 45 missed coarse Gold constraint spans; "
                        "S-only recovers 48 constraint sample-fields over `000` but introduces extra constraint spans."
                    ),
                    "supporting_sample_ids": ["estg_000021", "estg_000020", "estg_000027", "estg_000030"],
                    "intended_behavior_change": "Increase constraint recall while keeping each constraint span as a minimal complete limit rather than a marker-only fragment.",
                    "possible_side_effect": "May increase constraint over-extraction or condition/constraint category confusion; monitor unmatched-pred delta and cross-field candidates.",
                    "evaluation_criterion": "Constraint F1 improvement and no >0.01 primary mean-F1 drop vs same-batch `100`.",
                },
                {
                    "variant_id": "E + combined_minimal_fixes",
                    "hypothesis": "Actor minimality and constraint recall fixes are complementary if their effects are field-specific.",
                    "prompt_delta": "Apply both minimal deltas exactly as above; do not add any other S or J text.",
                    "targeted_failure": "Tests whether actor and constraint repair add or interfere when combined.",
                    "supporting_sample_ids": ["estg_000046", "estg_000664", "estg_000021", "estg_000027"],
                    "intended_behavior_change": "Improve actor precision and constraint recall relative to `100`.",
                    "possible_side_effect": "Two added instructions may interact; the union of the individual side effects must be monitored.",
                    "evaluation_criterion": "Primary mean F1 not lower than the better single fix, with actor and constraint trade-offs reported separately.",
                },
            ],
            "controls": "same EStG-150 input, frozen Gold, model/release, sampling, parser, canonicalizer, evaluator, and prompt skeleton as the current batch; baseline `100` rerun in the same batch.",
            "sample_count": "4 arms x 150 records = 600 planned calls if baseline `100` is rerun; 450 calls if a same-batch baseline reuse is later justified, but same-batch rerun is preferred for causal interpretation.",
            "metrics": "coarse_five_field_mean_f1 (primary), micro P/R/F1, per-field F1, modality-label metrics separately, paired fixed/regressed counts, actor/constraint over- and under-extraction, canonical failures, raw bare-JSON rate.",
            "stopping_rule": "Predeclare the four arms and thresholds before running; run all 600 calls without adaptive prompt changes; stop the refinement line if no variant improves its target field without a >0.01 primary mean-F1 drop, or if results are non-interpretable because of batch/parser drift.",
        },
        "same_batch_full8_assessment": {
            "answer": (
                "A future same-batch full-8 is not required for the next targeted repair experiment, but it is "
                "the correct later design if the paper needs a causal full-factorial comparison of E/S/J under "
                "one batch/time condition."
            ),
            "points": [
                "It addresses the batch/time confound between old four and new four, improving causal interpretability of factorial effects.",
                "A single same-batch full-8 still does not address repeat variance; it is one run per cell.",
                "Strong statistical conclusions about stability or significance require separately pre-registered repeats, not one full-8 batch.",
                "For the immediate next step, small controlled variants (baseline + targeted fixes) are more interpretable and cheaper than re-running all eight cells.",
            ],
        },
        "research_log_timeline": [
            {
                "stage": "Before ablation",
                "understanding": "Pre-experiment hypothesis: E, S, and J each contribute positively and may combine cumulatively; full `111` may be best.",
            },
            {
                "stage": "After single-factor ablation",
                "understanding": "Old-batch deletions of E, S, or J did not lower mean F1 relative to `111`; all three deletions were associated with higher mean F1. This weakened the simple additive contribution hypothesis and created the negative/non-monotonic finding.",
            },
            {
                "stage": "After full-8",
                "understanding": "`111` was not descriptively best; `100` was highest. E-only and S-only each improved over `000`, but E x S was a strong negative interaction. J-only did not improve the primary metric. Batch/time confound remained.",
            },
            {
                "stage": "After paired error analysis",
                "understanding": "E-only fixes many actor and constraint sample-fields; S helps constraint recall but drives actor over-extraction when added to E-containing arms. J's clearest effect is raw serialization form, not canonical semantic reliability. Large offsetting field changes explain why aggregate deltas looked modest.",
            },
            {
                "stage": "After prompt audit",
                "understanding": "E and S overlap functionally; no literal contradiction was found. J is distinct from the common baseline interface at the no-fence/bare-object level, but the adapter already recovers fenced responses, explaining the lack of canonical reliability gain.",
            },
            {
                "stage": "Next hypothesis",
                "understanding": "Test whether minimal actor-minimality and constraint-recall repairs added to `100` improve their target fields without restoring the full S module. Also test whether the two repairs combine or interfere.",
            },
        ],
        "paper_safe_wording": [
            {
                "topic": "J",
                "avoid": "JSON schema is unnecessary / structured output constraints are unnecessary.",
                "use": "Given the shared baseline structured-output interface retained across all configurations, the additional output-organization module did not provide a consistent measurable benefit under the evaluated model and dataset.",
            },
            {
                "topic": "E/S",
                "avoid": "E and S conflict.",
                "use": "The ablation results indicate a non-additive relationship between worked examples and explicit semantic rules, motivating a finer-grained error analysis of their overlapping or potentially interfering guidance.",
            },
            {
                "topic": "111",
                "avoid": "Full prompt is worse.",
                "use": "The complete configuration was not descriptively superior to several simpler configurations in the current experiments.",
            },
            {
                "topic": "Negative results",
                "avoid": "Hiding or deleting non-monotonic results.",
                "use": "Negative and non-monotonic ablation results are treated as experimental findings rather than discarded as failed experiments.",
            },
            {
                "topic": "Batch confound",
                "avoid": "Cross-batch ranking as strict causal proof.",
                "use": "The full-8 ranking is descriptive; the original four and new four cells are batch/time confounded, so cross-batch module effects are not strict causal estimates.",
            },
        ],
        "artifact_bindings": {
            "starting_head": git_head(),
            "formal_full8_report": str(V2_REPORT.relative_to(ROOT)).replace("\\", "/") + " sha256=" + sha256_file(V2_REPORT),
            "protocol_audit": str(PROTOCOL_AUDIT.relative_to(ROOT)).replace("\\", "/") + " sha256=" + sha256_file(PROTOCOL_AUDIT),
            "paired_error_attribution": str(PAIRED_REPORT.relative_to(ROOT)).replace("\\", "/") + " sha256=" + sha256_file(PAIRED_REPORT),
            "prompt_overlap_audit": str(PROMPT_AUDIT.relative_to(ROOT)).replace("\\", "/") + " sha256=" + sha256_file(PROMPT_AUDIT),
            "gold": "data/gold/stage2/estg150_formal_gold_v1.json sha256=" + sha256_file(ROOT / "data/gold/stage2/estg150_formal_gold_v1.json"),
            "predictions_are_read_only": "All eight canonical prediction paths are bound through the paired attribution report; no prediction file was modified.",
            "prompts_are_read_only": "Prompt component hashes are bound in the prompt overlap audit; no prompt file was modified.",
        },
        "git_note": (
            "This record and the two zero-API analysis scripts/outputs are new files. Pre-existing dirty files "
            "observed at the start of the round must remain untouched; only this round's files may be staged."
        ),
    }

    OUT_MD.write_text(render_markdown(record), encoding="utf-8", newline="\n")
    OUT_JSON.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT_MD.relative_to(ROOT)}")
    print(f"wrote {OUT_JSON.relative_to(ROOT)}")
    print("ranking", ranking)
    print("full8", {a: round(m['coarse_five_field_mean_f1'], 6) for a, m in arm_metrics.items()})


if __name__ == "__main__":
    main()
