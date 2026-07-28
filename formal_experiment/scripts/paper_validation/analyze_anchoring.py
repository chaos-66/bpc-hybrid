"""Phase 6: B0 error inheritance and anchoring analysis.

Definitions (from task §9):
- B0-FP: a B0 candidate that has NO modality-matching Gold clause with
  token-IoU >= 0.3.
- B0-FP "survives" in H1-final: there exists an H1-final candidate with
  the same modality and token-IoU >= 0.5 vs the B0-FP (provenance
  threshold, not the main eval threshold).
- FPInheritanceRate = (B0-FP that survive in H1-primed) / (B0-FP total).

Outputs:
- b0_false_positives.json
- inheritance_by_repeat.csv
- error_provenance.json
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MODALITY_SET = ('permission', 'obligation', 'prohibition', 'definition')
EVAL_IOU = 0.3
PROV_IOU = 0.5


def text_iou(a, b):
    ta = set((a or '').lower().split())
    tb = set((b or '').lower().split())
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union)


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


def load_b0(b0_path):
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
            clauses.append({'clause_text': text, 'modality': mod})
        out[sid] = clauses
    return out


def find_b0_fps(b0, gold, iou_threshold=EVAL_IOU):
    """Return dict sample_id -> list of B0-FP dicts with full provenance."""
    fps = {}
    for sid, b0_clauses in b0.items():
        gold_clauses = gold.get(sid, {}).get('gold_clauses', [])
        fplist = []
        for b0c in b0_clauses:
            ok = False
            for gc in gold_clauses:
                if b0c['modality'] != gc['modality']:
                    continue
                if text_iou(b0c['clause_text'], gc['clause_text']) >= iou_threshold:
                    ok = True
                    break
            if not ok:
                fplist.append({
                    'sample_id': sid,
                    'b0_clause_text': b0c['clause_text'],
                    'b0_modality': b0c['modality'],
                })
        fps[sid] = fplist
    return fps


def load_h1_final(runs_root: Path, method: str, rid: int) -> dict[str, list[dict]]:
    """Return sample_id -> list of final H1 candidates ({clause_text, modality, decision?})."""
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
    ap.add_argument('--b0-path', default='formal_experiment/outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json')
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--repeats', nargs='+', type=int, default=[1, 2, 3])
    return ap.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_root = Path(args.runs_root)
    gold = load_gold(Path(args.gold_path))
    b0 = load_b0(Path(args.b0_path))
    b0_fps = find_b0_fps(b0, gold, iou_threshold=EVAL_IOU)

    # Flatten
    flat_b0_fps = []
    for sid, lst in b0_fps.items():
        flat_b0_fps.extend(lst)
    total_b0_fps = len(flat_b0_fps)

    # Save b0_false_positives.json
    with open(out_dir / 'b0_false_positives.json', 'w', encoding='utf-8') as f:
        json.dump({
            'total_b0_candidates': sum(len(v) for v in b0.values()),
            'total_b0_false_positives': total_b0_fps,
            'by_record': b0_fps,
        }, f, ensure_ascii=False, indent=2)

    # For each method/repeat, compute inheritance
    rows = []
    for rid in args.repeats:
        for method in ['d1_unprimed', 'h1_selective_primed', 'h1_selective_empty']:
            h1 = load_h1_final(runs_root, method, rid)
            survived = 0
            not_survived = 0
            survived_details = []
            for fp in flat_b0_fps:
                sid = fp['sample_id']
                h1_clauses = h1.get(sid, [])
                ok = False
                best_iou = 0.0
                for h1c in h1_clauses:
                    if h1c['modality'] != fp['b0_modality']:
                        continue
                    iou = text_iou(h1c['clause_text'], fp['b0_clause_text'])
                    best_iou = max(best_iou, iou)
                    if iou >= PROV_IOU:
                        ok = True
                        break
                if ok:
                    survived += 1
                    survived_details.append({'sample_id': sid, 'b0_modality': fp['b0_modality'],
                                              'b0_text': fp['b0_clause_text'][:200], 'best_h1_iou': round(best_iou, 4)})
                else:
                    not_survived += 1
            rate = survived / total_b0_fps if total_b0_fps > 0 else 0.0
            rows.append({
                'method': method,
                'repeat_id': rid,
                'b0_fp_total': total_b0_fps,
                'b0_fp_survived': survived,
                'b0_fp_not_survived': not_survived,
                'fp_inheritance_rate': round(rate, 4),
            })
    # Save CSV
    csv_path = out_dir / 'inheritance_by_repeat.csv'
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write('method,repeat_id,b0_fp_total,b0_fp_survived,b0_fp_not_survived,fp_inheritance_rate\n')
        for r in rows:
            f.write(f'{r["method"]},{r["repeat_id"]},{r["b0_fp_total"]},{r["b0_fp_survived"]},{r["b0_fp_not_survived"]},{r["fp_inheritance_rate"]}\n')

    # Compute cross-method counts: for each B0-FP, how many methods include a same-modality clause
    # matching it at >=PROV_IOU. This is the cross-method FP overlap.
    cross = []
    for rid in args.repeats:
        per_method = {}
        for method in ['d1_unprimed', 'h1_selective_primed', 'h1_selective_empty']:
            h1 = load_h1_final(runs_root, method, rid)
            cnt = 0
            for fp in flat_b0_fps:
                sid = fp['sample_id']
                for h1c in h1.get(sid, []):
                    if h1c['modality'] != fp['b0_modality']:
                        continue
                    if text_iou(h1c['clause_text'], fp['b0_clause_text']) >= PROV_IOU:
                        cnt += 1
                        break
            per_method[method] = cnt
        cross.append({'repeat_id': rid, 'b0_fp_overlap_with_each_method': per_method})

    with open(out_dir / 'error_provenance.json', 'w', encoding='utf-8') as f:
        json.dump({
            'experiment_id': 'paper_validation_r1_20260728',
            'eval_iou_threshold': EVAL_IOU,
            'provenance_iou_threshold': PROV_IOU,
            'b0_fp_total': total_b0_fps,
            'inheritance_by_repeat': rows,
            'cross_method_overlap': cross,
        }, f, ensure_ascii=False, indent=2)
    print(f'wrote {csv_path} and error_provenance.json; total b0-fp = {total_b0_fps}')


if __name__ == '__main__':
    sys.exit(main() or 0)
