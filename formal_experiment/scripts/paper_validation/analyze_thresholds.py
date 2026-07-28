"""Phase 7: IoU threshold sensitivity analysis.

Re-evaluates each (method, repeat) at IoU thresholds 0.2, 0.3, 0.5, 0.7
without re-running any LLM. Reads all_predictions.json for each
(method, repeat) and the Gold, and recomputes per-modality + aggregate
metrics.
"""
import argparse
import json
import os
import sys
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MODALITY_SET = ('permission', 'obligation', 'prohibition', 'definition')
THRESHOLDS = (0.2, 0.3, 0.5, 0.7)


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


def evaluate_threshold(gold, pred_by_sid, iou_threshold):
    tp = fp = fn = 0
    per_modality = {m: {'tp': 0, 'fp': 0, 'fn': 0} for m in MODALITY_SET}
    for sid, g in gold.items():
        gc = g['gold_clauses']
        pc = pred_by_sid.get(sid, [])
        if not gc:
            fp += len(pc)
            continue
        pairs, used_p, used_g = best_effort_align(pc, gc, iou_threshold=iou_threshold)
        for pi, gi in pairs:
            if pc[pi].get('modality') == gc[gi].get('modality'):
                tp += 1
                per_modality[gc[gi]['modality']]['tp'] += 1
            else:
                fp += 1
                fn += 1
                per_modality[pc[pi]['modality']]['fp'] += 1
                per_modality[gc[gi]['modality']]['fn'] += 1
        for p in pc:
            if used_p is not None and p is not None:
                pass
        for pi, p in enumerate(pc):
            if pi in used_p:
                continue
            fp += 1
            per_modality[p.get('modality', 'unknown')]['fp'] += 1
        for gi, g in enumerate(gc):
            if gi in used_g:
                continue
            fn += 1
            per_modality[g.get('modality', 'unknown')]['fn'] += 1
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    per_mod_f1 = {}
    for m, v in per_modality.items():
        mp = v['tp'] / (v['tp'] + v['fp']) if (v['tp'] + v['fp']) > 0 else 0.0
        mr = v['tp'] / (v['tp'] + v['fn']) if (v['tp'] + v['fn']) > 0 else 0.0
        mf = 2 * mp * mr / (mp + mr) if (mp + mr) > 0 else 0.0
        per_mod_f1[m] = round(mf, 4)
    return {
        'tp': tp, 'fp': fp, 'fn': fn,
        'precision': round(p, 4),
        'recall': round(r, 4),
        'f1': round(f1, 4),
        'per_modality_f1': per_mod_f1,
    }


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs-root', required=True)
    ap.add_argument('--gold-path', default='formal_experiment/data/development/human_review/estg_150_human_correction_v1.json')
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--methods', nargs='+',
                    default=['d1_unprimed', 'h1_selective_primed', 'h1_selective_empty'])
    ap.add_argument('--repeats', nargs='+', type=int, default=[1, 2, 3])
    return ap.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    gold = load_gold(Path(args.gold_path))
    all_rows = []
    ranking = []
    for method in args.methods:
        for rid in args.repeats:
            pred = load_pred(Path(args.runs_root), method, rid)
            for tau in THRESHOLDS:
                m = evaluate_threshold(gold, pred, iou_threshold=tau)
                all_rows.append({
                    'method': method,
                    'repeat_id': rid,
                    'iou_threshold': tau,
                    'tp': m['tp'], 'fp': m['fp'], 'fn': m['fn'],
                    'precision': m['precision'],
                    'recall': m['recall'],
                    'f1': m['f1'],
                    'definition_f1': m['per_modality_f1']['definition'],
                    'permission_f1': m['per_modality_f1']['permission'],
                    'obligation_f1': m['per_modality_f1']['obligation'],
                    'prohibition_f1': m['per_modality_f1']['prohibition'],
                })
    # Save CSV
    csv_path = out_dir / 'all_metrics.csv'
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write('method,repeat_id,iou_threshold,tp,fp,fn,precision,recall,f1,definition_f1,permission_f1,obligation_f1,prohibition_f1\n')
        for r in all_rows:
            f.write(f"{r['method']},{r['repeat_id']},{r['iou_threshold']},{r['tp']},{r['fp']},{r['fn']},{r['precision']},{r['recall']},{r['f1']},{r['definition_f1']},{r['permission_f1']},{r['obligation_f1']},{r['prohibition_f1']}\n")
    # Ranking by threshold (mean F1 across repeats)
    rank_rows = []
    for tau in THRESHOLDS:
        for method in args.methods:
            f1s = [r['f1'] for r in all_rows if r['method'] == method and r['iou_threshold'] == tau]
            f1_mean = sum(f1s) / len(f1s) if f1s else 0.0
            rank_rows.append({
                'iou_threshold': tau,
                'method': method,
                'mean_f1': round(f1_mean, 4),
            })
    rank_path = out_dir / 'ranking_by_threshold.csv'
    with open(rank_path, 'w', encoding='utf-8') as f:
        f.write('iou_threshold,method,mean_f1\n')
        for r in rank_rows:
            f.write(f"{r['iou_threshold']},{r['method']},{r['mean_f1']}\n")
    # Save summary.json
    with open(out_dir / 'summary.json', 'w', encoding='utf-8') as f:
        json.dump({
            'experiment_id': 'paper_validation_r1_20260728',
            'created_at_utc': datetime.now(timezone.utc).isoformat(),
            'thresholds': list(THRESHOLDS),
            'ranking_by_threshold': rank_rows,
        }, f, ensure_ascii=False, indent=2)
    print(f'wrote {csv_path}, {rank_path}, summary.json')


if __name__ == '__main__':
    sys.exit(main() or 0)
