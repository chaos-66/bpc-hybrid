"""Phase 2: record-level paired bootstrap for paper validation R1.

For each pair of methods (A, B) at a given repeat, resample 150 records
with replacement 10000 times (seed=20260728), recompute micro P/R/F1/F2
on the resampled records' clauses, and compute (A - B) summary stats.

Statistical unit: record_id (NOT individual clauses).
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MODALITY_SET = ('permission', 'obligation', 'prohibition', 'definition')

BOOTSTRAP_REPS = 10000
BOOTSTRAP_SEED = 20260728


def text_iou(a, b):
    ta = set((a or '').lower().split())
    tb = set((b or '').lower().split())
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union)


def best_effort_align(predicted, gold, iou_threshold=0.3):
    used_p = set(); used_g = set()
    pairs = []
    scored = []
    for pi, pc in enumerate(predicted):
        for gi, gc in enumerate(gold):
            iou = text_iou(pc.get('clause_text', ''), gc.get('clause_text', ''))
            scored.append((iou, pi, gi))
    scored.sort(key=lambda x: (-x[0], x[1], x[2]))
    for iou, pi, gi in scored:
        if pi in used_p or gi in used_g:
            continue
        if iou < iou_threshold:
            break
        pairs.append((pi, gi))
        used_p.add(pi); used_g.add(gi)
    return pairs, used_p, used_g


def metrics_for_records(record_ids, gold_by_sid, pred_by_sid, iou_threshold=0.3):
    """Compute aggregate micro P/R/F1/F2 over a (possibly repeated) set of records."""
    tp = fp = fn = 0
    for sid in record_ids:
        gc = gold_by_sid.get(sid, {}).get('gold_clauses', [])
        pc = pred_by_sid.get(sid, [])
        if not gc:
            fp += len(pc)
            continue
        pairs, used_p, used_g = best_effort_align(pc, gc, iou_threshold=iou_threshold)
        for pi, gi in pairs:
            if pc[pi].get('modality') == gc[gi].get('modality'):
                tp += 1
            else:
                fp += 1; fn += 1
        fn += len(gc) - len(used_g)
        fp += len(pc) - len(used_p)
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    f2 = 5 * p * r / (4 * p + r) if (4 * p + r) > 0 else 0.0
    return {'p': p, 'r': r, 'f1': f1, 'f2': f2, 'tp': tp, 'fp': fp, 'fn': fn}


def load_gold(gold_path):
    with open(gold_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    out = {}
    for r in data.get('records', []):
        hc = r.get('human_correction', {}) or {}
        text = hc.get('approved_text_en') or r.get('approved_text_en') or ''
        clauses = []
        for c in (hc.get('clauses') or []):
            mod = c.get('modality', {}) or {}
            if mod.get('decision') not in ('accepted', 'edited'):
                continue
            mv = mod.get('value')
            if mv not in MODALITY_SET:
                continue
            cspan = c.get('clause_span', {}) or {}
            clauses.append({'clause_text': cspan.get('text', ''), 'modality': mv})
        out[r['sample_id']] = {'sample_id': r['sample_id'], 'approved_text_en': text, 'gold_clauses': clauses}
    return out


def load_pred(runs_root: Path, method: str, rid: int) -> dict[str, list[dict]]:
    f = runs_root / method / f'repeat_{rid:02d}' / 'all_predictions.json'
    if not f.exists():
        return {}
    with open(f, 'r', encoding='utf-8') as fp:
        data = json.load(fp)
    out = {}
    for sid, lst in data.get('per_record', {}).items():
        out[sid] = [{'clause_text': c.get('clause_text', ''), 'modality': c.get('modality')} for c in lst]
    return out


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs-root', required=True)
    ap.add_argument('--gold-path', default='formal_experiment/data/development/human_review/estg_150_human_correction_v1.json')
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--iou-threshold', type=float, default=0.3)
    ap.add_argument('--methods', nargs='+',
                    default=['d1_unprimed', 'h1_selective_primed', 'h1_selective_empty'])
    ap.add_argument('--repeats', nargs='+', type=int, default=[1, 2, 3])
    return ap.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    gold = load_gold(Path(args.gold_path))
    record_ids = sorted(gold.keys())
    # Pre-load predictions for each method/repeat
    preds = {}
    for m in args.methods:
        preds[m] = {}
        for r in args.repeats:
            preds[m][r] = load_pred(Path(args.runs_root), m, r)

    summary = {
        'experiment_id': 'paper_validation_r1_20260728',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'iou_threshold': args.iou_threshold,
        'bootstrap_reps': BOOTSTRAP_REPS,
        'bootstrap_seed': BOOTSTRAP_SEED,
        'sampling_unit': 'record_id',
        'per_repeat': {},
    }

    # Pairs
    pairs = []
    for i in range(len(args.methods)):
        for j in range(len(args.methods)):
            if i < j:
                pairs.append((args.methods[i], args.methods[j]))

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    for rid in args.repeats:
        rep_summary = {
            'methods': {},
            'pairwise': {},
        }
        # Per-method base metrics (no bootstrap, deterministic)
        for m in args.methods:
            base = metrics_for_records(record_ids, gold, preds[m][rid], iou_threshold=args.iou_threshold)
            rep_summary['methods'][m] = {
                'base_p': round(base['p'], 4),
                'base_r': round(base['r'], 4),
                'base_f1': round(base['f1'], 4),
                'base_f2': round(base['f2'], 4),
            }
        # Pairwise bootstrap
        for a, b in pairs:
            deltas_p = np.empty(BOOTSTRAP_REPS)
            deltas_r = np.empty(BOOTSTRAP_REPS)
            deltas_f1 = np.empty(BOOTSTRAP_REPS)
            deltas_f2 = np.empty(BOOTSTRAP_REPS)
            for k in range(BOOTSTRAP_REPS):
                idx = rng.integers(0, len(record_ids), size=len(record_ids))
                sampled = [record_ids[i] for i in idx]
                ma = metrics_for_records(sampled, gold, preds[a][rid], iou_threshold=args.iou_threshold)
                mb = metrics_for_records(sampled, gold, preds[b][rid], iou_threshold=args.iou_threshold)
                deltas_p[k] = ma['p'] - mb['p']
                deltas_r[k] = ma['r'] - mb['r']
                deltas_f1[k] = ma['f1'] - mb['f1']
                deltas_f2[k] = ma['f2'] - mb['f2']
            def summary_for(arr):
                return {
                    'mean': round(float(np.mean(arr)), 4),
                    'std': round(float(np.std(arr, ddof=1)), 4),
                    'ci95_low': round(float(np.percentile(arr, 2.5)), 4),
                    'ci95_high': round(float(np.percentile(arr, 97.5)), 4),
                    'excludes_zero': bool(np.percentile(arr, 2.5) > 0) or bool(np.percentile(arr, 97.5) < 0),
                    'sign': ('positive' if np.percentile(arr, 2.5) > 0
                             else 'negative' if np.percentile(arr, 97.5) < 0
                             else 'crosses_zero'),
                }
            rep_summary['pairwise'][f'{a}__vs__{b}'] = {
                'delta_p': summary_for(deltas_p),
                'delta_r': summary_for(deltas_r),
                'delta_f1': summary_for(deltas_f1),
                'delta_f2': summary_for(deltas_f2),
            }
        # Save per-repeat file
        out_path = out_dir / f'bootstrap_repeat_{rid:02d}.json'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({'repeat_id': rid, **rep_summary}, f, ensure_ascii=False, indent=2)
        summary['per_repeat'][f'repeat_{rid:02d}'] = {
            'base_metrics': rep_summary['methods'],
            'pairwise_signs': {
                pair_name: {
                    'delta_p_sign': rep_summary['pairwise'][pair_name]['delta_p']['sign'],
                    'delta_f1_sign': rep_summary['pairwise'][pair_name]['delta_f1']['sign'],
                    'delta_r_sign': rep_summary['pairwise'][pair_name]['delta_r']['sign'],
                    'delta_f2_sign': rep_summary['pairwise'][pair_name]['delta_f2']['sign'],
                }
                for pair_name in rep_summary['pairwise']
            }
        }
        print(f'bootstrap repeat {rid}: wrote {out_path}')

    # Final summary
    with open(out_dir / 'bootstrap_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f'wrote bootstrap_summary.json')


if __name__ == '__main__':
    sys.exit(main() or 0)
