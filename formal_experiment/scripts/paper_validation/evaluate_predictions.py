"""Phase 2: evaluate one (method, repeat) using token-IoU 0.3 (clause-level modality).

Reads the per-batch parsed_predictions.json files produced by
run_repeated_llm_experiment.py, aggregates them into a per-repeat
all_predictions.json, runs the gold-vs-prediction token-IoU 0.3
evaluation, and writes per_repeat + per_record + per_modality metrics.

Matching rules (frozen by task §4.4 / §4.5):
- token-IoU on the lowercased whitespace-tokenized clause_text
- IoU threshold = 0.3 (primary)
- one-to-one greedy: candidates sorted by descending IoU, then ascending
  pred_idx, ascending gold_idx
- TP requires modality match exactly
- Modality mismatch on a matched pair: BOTH FP+FN
- Unmatched predicted: FP; unmatched gold: FN
- Aggregation: micro TP/FP/FN
- F2 = 5*P*R / (4*P + R)
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MODALITY_SET = ('permission', 'obligation', 'prohibition', 'definition')


def text_iou(a: str, b: str) -> float:
    ta = set((a or '').lower().split())
    tb = set((b or '').lower().split())
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union)


def best_effort_align(predicted, gold, iou_threshold=0.3):
    """One-to-one greedy by descending IoU; ties broken by ascending pred_idx, gold_idx."""
    used_p = set()
    used_g = set()
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
        pairs.append({'pred_idx': pi, 'gold_idx': gi, 'iou': round(iou, 4)})
        used_p.add(pi)
        used_g.add(gi)
    unmatched_pred = [pc for pi, pc in enumerate(predicted) if pi not in used_p]
    unmatched_gold = [gc for gi, gc in enumerate(gold) if gi not in used_g]
    return pairs, unmatched_pred, unmatched_gold


def evaluate_record(predicted_clauses, gold_clauses, iou_threshold=0.3):
    if not gold_clauses:
        # Records with no gold clause: treat as 0 TP/FP/FN, exclude from aggregate
        return {
            'tp': 0, 'fp': len(predicted_clauses), 'fn': 0,
            'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'f2': 0.0,
            'n_pairs': 0, 'n_unmatched_pred': len(predicted_clauses),
            'n_unmatched_gold': 0, 'n_gold': 0, 'n_pred': len(predicted_clauses),
        }
    pairs, unmatched_pred, unmatched_gold = best_effort_align(
        predicted_clauses, gold_clauses, iou_threshold=iou_threshold)
    tp = fp = fn = 0
    for p in pairs:
        pred_mod = predicted_clauses[p['pred_idx']].get('modality')
        gold_mod = gold_clauses[p['gold_idx']].get('modality')
        if pred_mod == gold_mod:
            tp += 1
        else:
            fp += 1
            fn += 1
    fn += len(unmatched_gold)
    fp += len(unmatched_pred)
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    f2 = 5 * p * r / (4 * p + r) if (4 * p + r) > 0 else 0.0
    return {
        'tp': tp, 'fp': fp, 'fn': fn,
        'precision': round(p, 4), 'recall': round(r, 4),
        'f1': round(f1, 4), 'f2': round(f2, 4),
        'n_pairs': len(pairs),
        'n_unmatched_pred': len(unmatched_pred),
        'n_unmatched_gold': len(unmatched_gold),
        'n_gold': len(gold_clauses),
        'n_pred': len(predicted_clauses),
    }


def evaluate_repeat(gold, per_record_predictions, iou_threshold=0.3):
    """Returns (per_record_metrics, aggregate_metrics, per_modality_metrics)."""
    per_record = {}
    totals = {'tp': 0, 'fp': 0, 'fn': 0}
    per_modality_tp = Counter()
    per_modality_fp = Counter()
    per_modality_fn = Counter()
    for sid in sorted(gold.keys()):
        gold_clauses = gold[sid]['gold_clauses']
        pred = per_record_predictions.get(sid, [])
        m = evaluate_record(pred, gold_clauses, iou_threshold=iou_threshold)
        per_record[sid] = m
        totals['tp'] += m['tp']
        totals['fp'] += m['fp']
        totals['fn'] += m['fn']
        # Per-modality breakdown (from matched pairs only; we re-derive)
        pairs, unmatched_pred, unmatched_gold = best_effort_align(pred, gold_clauses, iou_threshold=iou_threshold)
        for pair in pairs:
            pred_mod = pred[pair['pred_idx']].get('modality')
            gold_mod = gold_clauses[pair['gold_idx']].get('modality')
            if pred_mod == gold_mod:
                per_modality_tp[gold_mod] += 1
            else:
                per_modality_fp[pred_mod] += 1
                per_modality_fn[gold_mod] += 1
        for pc in unmatched_pred:
            per_modality_fp[pc.get('modality', 'unknown')] += 1
        for gc in unmatched_gold:
            per_modality_fn[gc.get('modality', 'unknown')] += 1
    p = totals['tp'] / (totals['tp'] + totals['fp']) if (totals['tp'] + totals['fp']) > 0 else 0.0
    r = totals['tp'] / (totals['tp'] + totals['fn']) if (totals['tp'] + totals['fn']) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    f2 = 5 * p * r / (4 * p + r) if (4 * p + r) > 0 else 0.0
    aggregate = {
        **totals,
        'precision': round(p, 4),
        'recall': round(r, 4),
        'f1': round(f1, 4),
        'f2': round(f2, 4),
    }
    per_modality = {}
    for m in MODALITY_SET:
        tp = per_modality_tp.get(m, 0)
        fp = per_modality_fp.get(m, 0)
        fn = per_modality_fn.get(m, 0)
        mp = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        mr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        mf1 = 2 * mp * mr / (mp + mr) if (mp + mr) > 0 else 0.0
        per_modality[m] = {
            'tp': tp, 'fp': fp, 'fn': fn,
            'precision': round(mp, 4),
            'recall': round(mr, 4),
            'f1': round(mf1, 4),
            'support': sum(1 for sid in gold for gc in gold[sid]['gold_clauses'] if gc.get('modality') == m),
        }
    return per_record, aggregate, per_modality


def load_gold(gold_path: Path) -> dict:
    with open(gold_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    out = {}
    for r in data.get('records', []):
        hc = r.get('human_correction', {}) or {}
        text = hc.get('approved_text_en') or r.get('approved_text_en') or ''
        clauses = []
        for c in (hc.get('clauses') or []):
            mod = c.get('modality', {}) or {}
            if not isinstance(mod, dict):
                continue
            if mod.get('decision') not in ('accepted', 'edited'):
                continue
            mv = mod.get('value')
            if mv not in MODALITY_SET:
                continue
            cspan = c.get('clause_span', {}) or {}
            clauses.append({
                'clause_id': c.get('clause_id'),
                'clause_text': cspan.get('text', ''),
                'modality': mv,
            })
        out[r['sample_id']] = {
            'sample_id': r['sample_id'],
            'approved_text_en': text,
            'gold_clauses': clauses,
        }
    return out


def load_b0(b0_path: Path) -> dict[str, list[dict]]:
    with open(b0_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    out = {}
    for r in data:
        sid = r.get('sample_id')
        rec = r.get('record', {}) or {}
        clauses = []
        for c in (rec.get('clauses') or []):
            mod = (c.get('modality') or {}).get('label')
            if mod not in MODALITY_SET:
                continue
            cspan = c.get('clause_span', {}) or {}
            text = cspan.get('text', '')
            if not text:
                continue
            clauses.append({
                'clause_id': c.get('clause_id'),
                'clause_text': text,
                'modality': mod,
            })
        out[sid] = clauses
    return out


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--method', required=True,
                    choices=['d1_unprimed', 'h1_selective_primed', 'h1_selective_empty'])
    ap.add_argument('--repeat-id', required=True, type=int)
    ap.add_argument('--runs-root', required=True,
                    help='e.g. formal_experiment/outputs/paper_validation_r1_20260728/runs')
    ap.add_argument('--gold-path', default='formal_experiment/data/development/human_review/estg_150_human_correction_v1.json')
    ap.add_argument('--b0-path', default='formal_experiment/outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json')
    ap.add_argument('--iou-threshold', type=float, default=0.3)
    return ap.parse_args()


def atomic_write_json(path: Path, obj):
    tmp = path.with_suffix(path.suffix + '.tmp')
    if path.exists():
        raise FileExistsError(f'refusing to overwrite {path}')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main():
    args = parse_args()
    method = args.method
    rid = args.repeat_id
    runs_root = Path(args.runs_root)
    repeat_dir = runs_root / method / f'repeat_{rid:02d}'
    if not repeat_dir.exists():
        print(f'ERROR: {repeat_dir} does not exist')
        return 2

    # Aggregate per-batch parsed_predictions.json into per-record
    per_record_pred = defaultdict(list)
    per_record_pred_source = defaultdict(list)
    batches = sorted(repeat_dir.glob('batch_*'))
    parse_failures = 0
    invalid_batches = 0
    invalid_modality = 0
    for b in batches:
        pp = b / 'parsed_predictions.json'
        if not pp.exists():
            invalid_batches += 1
            continue
        try:
            with open(pp, 'r', encoding='utf-8') as f:
                pdata = json.load(f)
        except Exception:
            invalid_batches += 1
            continue
        if pdata.get('per_record'):
            for sid, lst in pdata['per_record'].items():
                per_record_pred[sid].extend(lst)
        # also count parse errors
        pe = b / 'parse_errors.jsonl'
        if pe.exists():
            with open(pe, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        parse_failures += 1
    # Save aggregated all_predictions.json
    all_pred = {
        'method': method,
        'repeat_id': rid,
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'per_record': {sid: lst for sid, lst in per_record_pred.items()},
        'n_records': len(per_record_pred),
        'n_total_clauses': sum(len(lst) for lst in per_record_pred.values()),
        'parse_failures': parse_failures,
        'invalid_batches': invalid_batches,
    }
    atomic_write_json(repeat_dir / 'all_predictions.json', all_pred)

    # Coverage check
    gold = load_gold(Path(args.gold_path))
    expected = set(gold.keys())
    covered = set(per_record_pred.keys())
    missing = sorted(expected - covered)
    extra = sorted(covered - expected)
    coverage = {
        'expected_count': len(expected),
        'covered_count': len(covered),
        'missing_count': len(missing),
        'missing': missing,
        'extra': extra,
    }

    # Quick validation
    n_with_pred = len(per_record_pred)
    coverage_ok = (len(covered) == 150 and len(missing) == 0 and len(extra) == 0 and invalid_batches == 0)

    # Evaluate
    per_record_metrics, aggregate, per_modality = evaluate_repeat(
        gold, {sid: per_record_pred[sid] for sid in gold}, iou_threshold=args.iou_threshold)

    # token usage (already written by executor)
    tu_path = repeat_dir / 'token_usage.json'
    token_usage = {}
    if tu_path.exists():
        with open(tu_path, 'r', encoding='utf-8') as f:
            token_usage = json.load(f)

    # cost estimate (heuristic, no live API)
    # We mark this as estimate; the task allows estimate pricing.
    in_tok = token_usage.get('input_tokens', 0)
    out_tok = token_usage.get('output_tokens', 0)
    cost = {
        'in_tokens': in_tok,
        'out_tokens': out_tok,
        'pricing_assumption': 'estimate based on project prior runs; USD per 1M tokens',
        'price_per_1m_input_usd_estimate': 2.0,
        'price_per_1m_output_usd_estimate': 8.0,
        'estimated_cost_usd': round((in_tok / 1_000_000) * 2.0 + (out_tok / 1_000_000) * 8.0, 4),
        'note': 'Estimate only. No live API cost data was used.',
    }

    # Per-record metrics (with per-record_iou_threshold)
    atomic_write_json(repeat_dir / f'per_record_metrics.json', per_record_metrics)
    atomic_write_json(repeat_dir / 'per_modality_metrics.json', per_modality)
    atomic_write_json(repeat_dir / f'metrics_token_iou_{args.iou_threshold}.json', {
        'method': method,
        'repeat_id': rid,
        'iou_threshold': args.iou_threshold,
        'aggregate': aggregate,
        'coverage': coverage,
        'coverage_ok': coverage_ok,
        'parse_failures': parse_failures,
        'invalid_batches': invalid_batches,
        'invalid_modality_count_in_parsed': invalid_modality,
    })
    atomic_write_json(repeat_dir / 'cost_estimate.json', cost)
    print(f'WROTE metrics for {method}/repeat_{rid:02d}; coverage_ok={coverage_ok}; F1={aggregate["f1"]:.4f}; P={aggregate["precision"]:.4f}; R={aggregate["recall"]:.4f}')
    if not coverage_ok:
        print(f'WARN: coverage issues: missing={len(missing)} extra={len(extra)} invalid_batches={invalid_batches}')
    return 0 if coverage_ok else 1


if __name__ == '__main__':
    sys.exit(main())
