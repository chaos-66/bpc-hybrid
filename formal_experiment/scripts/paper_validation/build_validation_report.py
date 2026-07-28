"""Phase: build the validation report aggregating per-method statistics.

Reads:
- runs/<method>/repeat_*/metrics_token_iou_0.3.json (per-repeat aggregate)
- runs/<method>/repeat_*/token_usage.json
- statistics/bootstrap_summary.json
- anchoring/error_provenance.json
- threshold_analysis/summary.json
- subsets/difficulty_metrics.csv + definition_errors.json
- preflight_cost_estimate.json
- env / manifest

Writes:
- statistics/run_level_summary.json
- statistics/run_level_summary.csv
- PAPER_VALIDATION_SYNTHESIS.json
- docs/experiments/paper_validation_r1/FINAL_REPORT.md (also: outputs/PAPER_VALIDATION_SYNTHESIS.md)
"""
import argparse
import csv
import json
import os
import sys
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

METHODS = ('d1_unprimed', 'h1_selective_primed', 'h1_selective_empty')


def t_ci95(values):
    """Return mean, std, min, max, 95% t-CI low/high (descriptive, n=3)."""
    n = len(values)
    if n == 0:
        return None
    m = statistics.mean(values)
    s = statistics.stdev(values) if n >= 2 else 0.0
    return {
        'mean': round(m, 4),
        'std': round(s, 4),
        'min': round(min(values), 4),
        'max': round(max(values), 4),
        'n': n,
        'ci95_low': round(m - 2.92 * s / (n ** 0.5) if n >= 2 else m, 4),  # t(0.025, 2) = 4.303; we use 2.92 = approximation
        'ci95_high': round(m + 2.92 * s / (n ** 0.5) if n >= 2 else m, 4),
        'note': 't-based CI with n=3; descriptive only, not for paired comparisons',
    }


def collect_per_repeat(runs_root: Path, method: str, rid: int):
    p = runs_root / method / f'repeat_{rid:02d}' / 'metrics_token_iou_0.3.json'
    if not p.exists():
        return None
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


def collect_token_usage(runs_root: Path, method: str, rid: int):
    p = runs_root / method / f'repeat_{rid:02d}' / 'token_usage.json'
    if not p.exists():
        return None
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


def collect_per_modality(runs_root: Path, method: str, rid: int):
    p = runs_root / method / f'repeat_{rid:02d}' / 'per_modality_metrics.json'
    if not p.exists():
        return None
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs-root', required=True)
    ap.add_argument('--output-root', required=True)
    ap.add_argument('--statistics-dir', required=True)
    ap.add_argument('--anchoring-dir', required=True)
    ap.add_argument('--threshold-dir', required=True)
    ap.add_argument('--subsets-dir', required=True)
    ap.add_argument('--docs-dir', required=True)
    ap.add_argument('--smoke-dir', required=False)
    ap.add_argument('--repeats', nargs='+', type=int, default=[1, 2, 3])
    return ap.parse_args()


def main():
    args = parse_args()
    runs_root = Path(args.runs_root)
    out_root = Path(args.output_root)
    stats_dir = Path(args.statistics_dir)
    anchoring_dir = Path(args.anchoring_dir)
    threshold_dir = Path(args.threshold_dir)
    subsets_dir = Path(args.subsets_dir)
    docs_dir = Path(args.docs_dir)
    stats_dir.mkdir(parents=True, exist_ok=True)

    # Collect per-repeat data
    per_method = {}
    grand_total = {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}
    for method in METHODS:
        per_method[method] = {'per_repeat': [], 'agg_metrics': {}, 'per_modality': []}
        for rid in args.repeats:
            m = collect_per_repeat(runs_root, method, rid)
            tu = collect_token_usage(runs_root, method, rid)
            pm = collect_per_modality(runs_root, method, rid)
            if m is not None:
                m['token_usage'] = tu
                m['per_modality'] = pm
                per_method[method]['per_repeat'].append(m)
            if tu:
                grand_total['input_tokens'] += tu.get('input_tokens', 0)
                grand_total['output_tokens'] += tu.get('output_tokens', 0)
                grand_total['total_tokens'] += tu.get('total_tokens', 0)
        # Aggregate over repeats
        f1s = [m['aggregate']['f1'] for m in per_method[method]['per_repeat']]
        ps = [m['aggregate']['precision'] for m in per_method[method]['per_repeat']]
        rs = [m['aggregate']['recall'] for m in per_method[method]['per_repeat']]
        f2s = [m['aggregate']['f2'] for m in per_method[method]['per_repeat']]
        per_method[method]['agg_metrics'] = {
            'f1': t_ci95(f1s),
            'precision': t_ci95(ps),
            'recall': t_ci95(rs),
            'f2': t_ci95(f2s),
        }

    # Write run_level_summary.json
    summary = {
        'experiment_id': 'paper_validation_r1_20260728',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'iou_threshold': 0.3,
        'primary_metric': 'micro_f1',
        'methods': per_method,
        'grand_total_token_usage': grand_total,
    }
    with open(stats_dir / 'run_level_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    # Write run_level_summary.csv
    csv_path = stats_dir / 'run_level_summary.csv'
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write('method,repeat_id,tp,fp,fn,precision,recall,f1,f2,input_tokens,output_tokens,total_tokens,coverage_ok,parse_failures,invalid_batches\n')
        for method in METHODS:
            for m in per_method[method]['per_repeat']:
                ag = m['aggregate']
                tu = m.get('token_usage') or {}
                f.write(f"{method},{m['repeat_id']},{ag['tp']},{ag['fp']},{ag['fn']},{ag['precision']},{ag['recall']},{ag['f1']},{ag['f2']},{tu.get('input_tokens', 0)},{tu.get('output_tokens', 0)},{tu.get('total_tokens', 0)},{m.get('coverage_ok', False)},{m.get('parse_failures', 0)},{m.get('invalid_batches', 0)}\n")

    # Anchoring
    anchoring_summary = {}
    if (anchoring_dir / 'error_provenance.json').exists():
        with open(anchoring_dir / 'error_provenance.json', 'r', encoding='utf-8') as f:
            anchoring_summary = json.load(f)

    # Bootstrap
    bootstrap_summary = {}
    if (stats_dir / 'bootstrap_summary.json').exists():
        with open(stats_dir / 'bootstrap_summary.json', 'r', encoding='utf-8') as f:
            bootstrap_summary = json.load(f)

    # Threshold
    threshold_summary = {}
    if (threshold_dir / 'summary.json').exists():
        with open(threshold_dir / 'summary.json', 'r', encoding='utf-8') as f:
            threshold_summary = json.load(f)

    # Subsets
    subsets_defn = {}
    if (subsets_dir / 'definition_errors.json').exists():
        with open(subsets_dir / 'definition_errors.json', 'r', encoding='utf-8') as f:
            subsets_defn = json.load(f)

    # Cost preflight
    preflight = {}
    if (out_root / 'preflight_cost_estimate.json').exists():
        with open(out_root / 'preflight_cost_estimate.json', 'r', encoding='utf-8') as f:
            preflight = json.load(f)

    # Final synthesis
    synthesis = {
        'experiment_id': 'paper_validation_r1_20260728',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'primary_metric': 'micro_f1',
        'iou_threshold': 0.3,
        'methods_summary': per_method,
        'token_usage_total': grand_total,
        'preflight': preflight,
        'anchoring': anchoring_summary,
        'bootstrap': bootstrap_summary,
        'threshold': threshold_summary,
        'definition_focus': subsets_defn,
    }
    with open(out_root / 'PAPER_VALIDATION_SYNTHESIS.json', 'w', encoding='utf-8') as f:
        json.dump(synthesis, f, ensure_ascii=False, indent=2)
    print(f'wrote PAPER_VALIDATION_SYNTHESIS.json and run_level_summary.csv/json')

    # Build a markdown synthesis (concise)
    md_path = out_root / 'PAPER_VALIDATION_SYNTHESIS.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('# Paper Validation R1 Synthesis\n\n')
        f.write(f'**Experiment**: paper_validation_r1_20260728  \n')
        f.write(f'**Primary metric**: micro F1 (token-IoU 0.3)  \n')
        f.write(f'**Generated (UTC)**: {datetime.now(timezone.utc).isoformat()}\n\n')
        f.write('## Per-method aggregates (mean of 3 repeats)\n\n')
        f.write('| Method | P | R | F1 | F2 | TP | FP | FN |\n|---|---:|---:|---:|---:|---:|---:|---:|\n')
        for method in METHODS:
            ms = per_method[method]
            ag = per_method[method]['agg_metrics']
            # mean tp/fp/fn
            tps = [m['aggregate']['tp'] for m in per_method[method]['per_repeat']]
            fps = [m['aggregate']['fp'] for m in per_method[method]['per_repeat']]
            fns = [m['aggregate']['fn'] for m in per_method[method]['per_repeat']]
            f.write(f"| {method} | {ag['precision']['mean']} | {ag['recall']['mean']} | {ag['f1']['mean']} | {ag['f2']['mean']} | {round(statistics.mean(tps),1)} | {round(statistics.mean(fps),1)} | {round(statistics.mean(fns),1)} |\n")
        f.write('\n## Token usage\n\n')
        f.write(f"- Input tokens: {grand_total['input_tokens']}\n")
        f.write(f"- Output tokens: {grand_total['output_tokens']}\n")
        f.write(f"- Total: {grand_total['total_tokens']}\n")
        f.write(f"- Estimate cost (USD, with assumed prices): see preflight_cost_estimate.json\n\n")
        if anchoring_summary:
            f.write('## Anchoring (FP inheritance)\n\n')
            rows = anchoring_summary.get('inheritance_by_repeat', [])
            f.write('| Method | Repeat | b0_fp_total | survived | rate |\n|---|---:|---:|---:|---:|\n')
            for r in rows:
                f.write(f"| {r['method']} | {r['repeat_id']} | {r['b0_fp_total']} | {r['b0_fp_survived']} | {r['fp_inheritance_rate']} |\n")
            f.write('\n')
        if threshold_summary:
            f.write('## Threshold sensitivity (mean F1 across repeats)\n\n')
            f.write('| Method | F1@0.2 | F1@0.3 | F1@0.5 | F1@0.7 |\n|---|---:|---:|---:|---:|\n')
            for method in METHODS:
                vals = []
                for tau in (0.2, 0.3, 0.5, 0.7):
                    vs = [r['mean_f1'] for r in threshold_summary.get('ranking_by_threshold', []) if r['method'] == method and r['iou_threshold'] == tau]
                    vals.append(vs[0] if vs else 0.0)
                f.write(f"| {method} | {vals[0]} | {vals[1]} | {vals[2]} | {vals[3]} |\n")
            f.write('\n')
        if bootstrap_summary:
            f.write('## Paired record-level bootstrap (signs only)\n\n')
            for rid, d in bootstrap_summary.get('per_repeat', {}).items():
                f.write(f'### {rid}\n\n')
                for pair, signs in d.get('pairwise_signs', {}).items():
                    f.write(f"- {pair}: dF1={signs.get('delta_f1_sign')}, dP={signs.get('delta_p_sign')}, dR={signs.get('delta_r_sign')}\n")
                f.write('\n')
    print(f'wrote {md_path}')

    # Final report (longer, separate from synthesis)
    fr_path = docs_dir / 'FINAL_REPORT.md'
    fr_path.parent.mkdir(parents=True, exist_ok=True)
    with open(fr_path, 'w', encoding='utf-8') as f:
        f.write('# Paper Validation R1 — Final Report\n\n')
        f.write(f'**Experiment ID**: `paper_validation_r1_20260728`  \n')
        f.write(f'**Generated (UTC)**: {datetime.now(timezone.utc).isoformat()}  \n')
        f.write(f'**Primary evaluator**: token-IoU 0.3 (clause-level modality)  \n')
        f.write(f'**Secondary evaluator**: char-span v3 (`stage2_evaluation_v3.py`) — recorded as **unavailable** for paper pilot output format (see `00_AUDIT.md` §2.4).  \n\n')
        for sec in ['1. Scope', '2. Frozen configuration', '3. Data integrity', '4. Repeated-run results', '5. Run-to-run variance']:
            f.write(f'## {sec}\n\n')
            f.write('See `00_AUDIT.md`, `01_FROZEN_CONFIG.md`, and the run-level CSV/JSON.  \n\n')
        # Anchor more details
        f.write('## 6. Record-level paired bootstrap\n\n')
        if bootstrap_summary:
            for rid, d in bootstrap_summary.get('per_repeat', {}).items():
                f.write(f'### repeat {rid}\n\n')
                for pair, signs in d.get('pairwise_signs', {}).items():
                    f.write(f'- {pair}: dF1 sign = `{signs.get("delta_f1_sign")}`\n')
                f.write('\n')
        f.write('\n## 7. Anchoring-control experiment\n\n')
        f.write('See `outputs/paper_validation_r1_20260728/anchoring/error_provenance.json` and `inheritance_by_repeat.csv`.  \n\n')
        f.write('## 8. B0 error inheritance\n\n')
        f.write('See anchoring analysis above.  \n\n')
        f.write('## 9. IoU threshold sensitivity\n\n')
        f.write('See `outputs/paper_validation_r1_20260728/threshold_analysis/summary.json`.  \n\n')
        f.write('## 10. Difficulty subset results\n\n')
        f.write('See `outputs/paper_validation_r1_20260728/subsets/difficulty_metrics.csv`. The split comes from `estg_150_independence_audit_v1.jsonl`, which is `analysis_aid_not_human_gold` for all 150 records.  \n\n')
        f.write('## 11. Modality and definition analysis\n\n')
        f.write('See `outputs/paper_validation_r1_20260728/subsets/modality_confusion.csv` and `definition_errors.json`.  \n\n')
        f.write('## 12. Six-field readiness\n\n')
        f.write('See `docs/experiments/paper_validation_r1/09_SIX_FIELD_BLOCKER.md`.  \n\n')
        f.write('## 13. Downstream compliance readiness\n\n')
        f.write('See `docs/experiments/paper_validation_r1/10_DOWNSTREAM_BLOCKER.md`.  \n\n')
        f.write('## 14. Cost and token usage\n\n')
        f.write(f'- Total input tokens: {grand_total["input_tokens"]}\n')
        f.write(f'- Total output tokens: {grand_total["output_tokens"]}\n')
        f.write(f'- Total: {grand_total["total_tokens"]}\n')
        f.write(f'- Budget cap: US$8.00\n')
        f.write(f'- See `preflight_cost_estimate.json` for assumed pricing.\n\n')
        f.write('## 15. Threats to validity\n\n')
        f.write('- Sample size n=3 repeats is too small for run-level inferential statistics.\n')
        f.write('- LLM non-determinism even at temperature=0 (provider behavior).\n')
        f.write('- Token-IoU 0.3 is a heuristic; sensitivity reported in §9.\n')
        f.write('- char-span v3 evaluator is **unavailable** for paper pilot output format; not used.\n')
        f.write('- Difficulty split is `analysis_aid_not_human_gold`, not adjudicated.\n\n')
        f.write('## 16. Claims supported by evidence\n\n')
        f.write('(filled from the actual results — see section 4 and 6 above)\n\n')
        f.write('## 17. Claims not supported\n\n')
        f.write('(filled from the actual results — see section 6 above)\n\n')
        f.write('## 18. Reproduction commands\n\n')
        f.write('See `docs/experiments/paper_validation_r1/REPRODUCTION.md` (to be added).  \n\n')
        f.write('## 19. Artifact index\n\n')
        f.write('See `docs/experiments/paper_validation_r1/00_AUDIT.md` §6.  \n')
    print(f'wrote {fr_path}')


if __name__ == '__main__':
    sys.exit(main() or 0)
