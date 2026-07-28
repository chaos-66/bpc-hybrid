"""Phase 8: difficulty subset + definition focus analysis.

Inputs:
- All_predictions.json for each (method, repeat)
- Gold
- Difficulty mapping (sample_id -> 'independent' | 'needs_context' | 'not_independent')

Outputs:
- difficulty_metrics.csv
- modality_confusion.csv
- definition_errors.json
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


def load_difficulty(path: Path) -> dict[str, str]:
    out = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            out[d['sample_id']] = d.get('classification')
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


def metrics_for_subset(gold, pred_by_sid, subset_sids, iou_threshold=0.3):
    """Micro metrics for the records in subset_sids."""
    tp = fp = fn = 0
    for sid in subset_sids:
        gc = gold[sid]['gold_clauses']
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
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precision': round(p, 4), 'recall': round(r, 4), 'f1': round(f1, 4)}


def per_modality_f1(gold, pred_by_sid, sids, iou_threshold=0.3):
    out = {}
    for m in MODALITY_SET:
        out[m] = metrics_for_subset_subset(gold, pred_by_sid, sids, m, iou_threshold=iou_threshold)
    return out


def metrics_for_subset_subset(gold, pred_by_sid, sids, target_modality, iou_threshold=0.3):
    """Per-modality micro P/R/F1 restricted to clauses whose Gold is target_modality."""
    tp = fp = fn = 0
    for sid in sids:
        gc = [c for c in gold[sid]['gold_clauses'] if c['modality'] == target_modality]
        pc = pred_by_sid.get(sid, [])
        if not gc:
            # No gold for this modality in this record: any predicted matching-modality are FP
            for p in pc:
                if p.get('modality') == target_modality:
                    fp += 1
            continue
        pairs, used_p, used_g = best_effort_align(pc, gc, iou_threshold=iou_threshold)
        for pi, gi in pairs:
            if pc[pi].get('modality') == gc[gi].get('modality') == target_modality:
                tp += 1
            else:
                fp += 1; fn += 1
        for pi, p in enumerate(pc):
            if pi in used_p: continue
            if p.get('modality') == target_modality:
                fp += 1
        for gi, g in enumerate(gc):
            if gi in used_g: continue
            fn += 1
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precision': round(p, 4), 'recall': round(r, 4), 'f1': round(f1, 4)}


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs-root', required=True)
    ap.add_argument('--gold-path', default='formal_experiment/data/development/human_review/estg_150_human_correction_v1.json')
    ap.add_argument('--difficulty-path', default='formal_experiment/outputs/development/estg150_independence_audit_v1/estg_150_independence_audit_v1.jsonl')
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--methods', nargs='+',
                    default=['d1_unprimed', 'h1_selective_primed', 'h1_selective_empty'])
    ap.add_argument('--repeats', nargs='+', type=int, default=[1, 2, 3])
    ap.add_argument('--iou-threshold', type=float, default=0.3)
    return ap.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_root = Path(args.runs_root)
    gold = load_gold(Path(args.gold_path))
    diff = load_difficulty(Path(args.difficulty_path))
    # Validate
    subsets = {'independent': [], 'needs_context': [], 'not_independent': []}
    for sid, cls in diff.items():
        if cls in subsets:
            subsets[cls].append(sid)
    # Verify
    total = sum(len(v) for v in subsets.values())
    if total != 150:
        print(f'WARN: difficulty subset total = {total}, expected 150')

    # difficulty_metrics.csv
    csv_path = out_dir / 'difficulty_metrics.csv'
    rows = []
    for method in args.methods:
        for rid in args.repeats:
            pred = load_pred(runs_root, method, rid)
            for subset_name, sids in subsets.items():
                m = metrics_for_subset(gold, pred, sids, iou_threshold=args.iou_threshold)
                pm = per_modality_f1(gold, pred, sids, iou_threshold=args.iou_threshold)
                rows.append({
                    'method': method, 'repeat_id': rid, 'subset': subset_name,
                    'n_records': len(sids),
                    'tp': m['tp'], 'fp': m['fp'], 'fn': m['fn'],
                    'precision': m['precision'], 'recall': m['recall'], 'f1': m['f1'],
                    'permission_f1': pm['permission']['f1'],
                    'obligation_f1': pm['obligation']['f1'],
                    'prohibition_f1': pm['prohibition']['f1'],
                    'definition_f1': pm['definition']['f1'],
                })
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write('method,repeat_id,subset,n_records,tp,fp,fn,precision,recall,f1,permission_f1,obligation_f1,prohibition_f1,definition_f1\n')
        for r in rows:
            f.write(f"{r['method']},{r['repeat_id']},{r['subset']},{r['n_records']},{r['tp']},{r['fp']},{r['fn']},{r['precision']},{r['recall']},{r['f1']},{r['permission_f1']},{r['obligation_f1']},{r['prohibition_f1']},{r['definition_f1']}\n")

    # modality_confusion.csv (overall, summed across all repeats)
    confusion = {}
    for method in args.methods:
        confusion[method] = {}
        for rid in args.repeats:
            pred = load_pred(runs_root, method, rid)
            for sid, gc_list in [(sid, gold[sid]['gold_clauses']) for sid in gold]:
                pc = pred.get(sid, [])
                pairs, used_p, used_g = best_effort_align(pc, gc_list, iou_threshold=args.iou_threshold)
                for pi, gi in pairs:
                    if pc[pi].get('modality') != gc_list[gi].get('modality'):
                        key = (gc_list[gi]['modality'], pc[pi]['modality'])
                        confusion[method][key] = confusion[method].get(key, 0) + 1
    # Output
    conf_path = out_dir / 'modality_confusion.csv'
    with open(conf_path, 'w', encoding='utf-8') as f:
        f.write('method,gold_modality,pred_modality,count\n')
        for method, d in confusion.items():
            for (g, p), c in d.items():
                f.write(f'{method},{g},{p},{c}\n')

    # definition focus: per-method confusion for definition
    defn_report = {
        'gold_definition_count': sum(1 for sid in gold for c in gold[sid]['gold_clauses'] if c['modality'] == 'definition'),
        'per_method': {},
    }
    for method in args.methods:
        method_data = {'per_repeat': [], 'missing_definition_records': set(), 'confusion_as_other': Counter()}
        for rid in args.repeats:
            pred = load_pred(runs_root, method, rid)
            rep = {'repeat_id': rid, 'tp': 0, 'fp': 0, 'fn': 0, 'precision': 0, 'recall': 0, 'f1': 0}
            for sid, gc_list in gold.items():
                pc = pred.get(sid, [])
                g_def = [c for c in gc_list if c['modality'] == 'definition']
                p_def = [c for c in pc if c.get('modality') == 'definition']
                pairs, used_p, used_g = best_effort_align(p_def, g_def, iou_threshold=args.iou_threshold)
                tp = len(pairs)
                fn = len(g_def) - len(used_g)
                fp = len(p_def) - len(used_p)
                rep['tp'] += tp; rep['fp'] += fp; rep['fn'] += fn
                if g_def and not any(pi in used_p for pi in range(len(p_def)) for pi, gi in pairs if gc_list[gi]['modality']=='definition' and pc[pi]['modality']=='definition'):
                    pass
                if g_def and tp == 0:
                    method_data['missing_definition_records'].add(sid)
                # Confusion: definition predicted as something else
                for p in p_def:
                    if not any(p['clause_text'] == gc['clause_text'] for gc in g_def):
                        # This is either a definition FP or a mislabel
                        # We'll count in confusion_as_other if it's modality-mismatched to non-definition
                        pass
                # Counts: definition gold clauses predicted as non-definition
                for p in pc:
                    if p.get('modality') in ('permission', 'obligation', 'prohibition'):
                        # check if it matches a definition gold (token IoU >= 0.3)
                        for gi, gc in enumerate(gc_list):
                            if gc['modality'] == 'definition' and text_iou(p['clause_text'], gc['clause_text']) >= 0.3:
                                method_data['confusion_as_other'][p['modality']] += 1
                                break
            p_ = rep['tp'] / (rep['tp'] + rep['fp']) if (rep['tp'] + rep['fp']) > 0 else 0.0
            r_ = rep['tp'] / (rep['tp'] + rep['fn']) if (rep['tp'] + rep['fn']) > 0 else 0.0
            f_ = 2 * p_ * r_ / (p_ + r_) if (p_ + r_) > 0 else 0.0
            rep['precision'] = round(p_, 4); rep['recall'] = round(r_, 4); rep['f1'] = round(f_, 4)
            method_data['per_repeat'].append(rep)
        method_data['missing_definition_records'] = sorted(method_data['missing_definition_records'])
        method_data['confusion_as_other'] = dict(method_data['confusion_as_other'])
        defn_report['per_method'][method] = method_data
    with open(out_dir / 'definition_errors.json', 'w', encoding='utf-8') as f:
        json.dump(defn_report, f, ensure_ascii=False, indent=2)
    print(f'wrote {csv_path}, {conf_path}, definition_errors.json')


if __name__ == '__main__':
    sys.exit(main() or 0)
