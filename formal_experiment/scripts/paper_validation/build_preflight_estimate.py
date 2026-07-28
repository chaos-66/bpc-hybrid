"""Phase 4: preflight cost estimate (calibrated to prior runs).

Per paper_synthesis/PAPER_DATA_SYNTHESIS.md:
- 3 prior paper-pilot runs (D1 150, H1-naive 150, H1-selective 150) used
  843,001 tokens total and cost ~US$2.0.
- Effective rate ≈ US$2.37 per 1M tokens.

For 9 full runs (3 methods × 3 repeats) at similar scale, the projected
total is ~3x = ~US$6.0. The task hard cap is US$8.0.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Calibrated cost per 1M tokens based on the prior 3 pilots
PRICE_PER_1M = 2.37

# Token usage from prior runs (per the paper synthesis report)
D1_150 = {'in': 54087, 'out': 253952, 'total': 308039}
H1_150 = {'in': 110162, 'out': 219493, 'total': 329655}  # H1-selective
H1_NAIVE_150 = {'in': 45537, 'out': 160770, 'total': 206307}
PRIOR_TOTAL = D1_150['total'] + H1_150['total'] + H1_NAIVE_150['total']  # 843,001
PRIOR_COST_USD = 2.0


def est_cost(in_tok: int, out_tok: int) -> float:
    return round(((in_tok + out_tok) / 1_000_000) * PRICE_PER_1M, 4)


def main():
    out = {
        'experiment_id': 'paper_validation_r1_20260728',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'pricing_assumption': {
            'price_per_1m_tokens_usd': PRICE_PER_1M,
            'source': 'calibrated against paper_synthesis/PAPER_DATA_SYNTHESIS.md: '
                      '3 prior pilots (D1 150, H1-naive 150, H1-selective 150) used '
                      '843001 tokens for ~$2.0; effective rate ~$2.37/1M tokens.',
            'note': 'The DeepSeek V4 Pro API on Aliyun MaaS does not provide '
                    'a public per-token price sheet; this is a backward-calibrated estimate '
                    'from the same project\'s prior runs. Actual cost will be re-derived '
                    'from per-batch token_usage.json after the run.',
        },
        'prior_run_token_usage': {
            'D1_150': D1_150,
            'H1_150': H1_150,
            'H1_naive_150': H1_NAIVE_150,
            'PRIOR_TOTAL': PRIOR_TOTAL,
            'PRIOR_COST_USD': PRIOR_COST_USD,
        },
        'per_method_per_repeat_estimates': {
            'd1_unprimed': {
                'in_per_run': D1_150['in'],
                'out_per_run': D1_150['out'],
                'total_per_run': D1_150['total'],
                'cost_per_run_estimate_usd': est_cost(D1_150['in'], D1_150['out']),
            },
            'h1_selective_primed': {
                'in_per_run': H1_150['in'],
                'out_per_run': H1_150['out'],
                'total_per_run': H1_150['total'],
                'cost_per_run_estimate_usd': est_cost(H1_150['in'], H1_150['out']),
            },
            'h1_selective_empty': {
                'in_per_run': D1_150['in'] + 5000,
                'out_per_run': D1_150['out'] + 5000,
                'total_per_run': D1_150['total'] + 10000,
                'cost_per_run_estimate_usd': est_cost(D1_150['in'] + 5000, D1_150['out'] + 5000),
            },
        },
        'totals_3_methods_x_3_repeats': {
            'd1_unprimed_3_repeats': {
                'in': D1_150['in'] * 3,
                'out': D1_150['out'] * 3,
                'cost_estimate_usd': round(est_cost(D1_150['in'], D1_150['out']) * 3, 4),
            },
            'h1_selective_primed_3_repeats': {
                'in': H1_150['in'] * 3,
                'out': H1_150['out'] * 3,
                'cost_estimate_usd': round(est_cost(H1_150['in'], H1_150['out']) * 3, 4),
            },
            'h1_selective_empty_3_repeats': {
                'in': (D1_150['in'] + 5000) * 3,
                'out': (D1_150['out'] + 5000) * 3,
                'cost_estimate_usd': round(est_cost(D1_150['in'] + 5000, D1_150['out'] + 5000) * 3, 4),
            },
        },
        'budget_cap_usd': 8.00,
        'budget_stop_threshold_usd': 7.20,
    }
    grand_in = sum(out['totals_3_methods_x_3_repeats'][k]['in'] for k in out['totals_3_methods_x_3_repeats'])
    grand_out = sum(out['totals_3_methods_x_3_repeats'][k]['out'] for k in out['totals_3_methods_x_3_repeats'])
    grand_cost = sum(out['totals_3_methods_x_3_repeats'][k]['cost_estimate_usd'] for k in out['totals_3_methods_x_3_repeats'])
    out['totals_3_methods_x_3_repeats']['TOTAL'] = {
        'in': grand_in, 'out': grand_out,
        'cost_estimate_usd': round(grand_cost, 4),
    }
    out['totals_3_methods_x_3_repeats']['3x_retry_worst_case_estimate'] = {
        'in': grand_in * 3, 'out': grand_out * 3,
        'cost_estimate_usd_3x': round(grand_cost * 3, 4),
        'note': 'Hypothetical 3x; in practice retry only happens for transient errors '
                '(timeouts, 429, 5xx, JSON parse). On 3 retries succeeding with the same '
                'token usage, this is the cost. The task says to STOP if cumulative cost '
                'reaches $7.20, which would prevent this worst case.',
    }
    out['decision'] = {
        'normal_total_within_budget': grand_cost < 8.0,
        'normal_total_estimate_usd': round(grand_cost, 4),
        'budget_cap_usd': 8.00,
        'budget_stop_threshold_usd': 7.20,
    }
    p = 'formal_experiment/outputs/paper_validation_r1_20260728/preflight_cost_estimate.json'
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'wrote {p}; normal total = ${grand_cost:.4f} (within $8 budget: {grand_cost < 8.0})')


if __name__ == '__main__':
    main()
