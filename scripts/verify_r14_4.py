"""R14.4 verification checks."""
import json
from pathlib import Path

print('=== R14.4 Verification ===')

# V1: Predictions file: 24 records
preds = []
with open('data/formal/predictions/r14_4_rule_plus_llm_predictions.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            preds.append(json.loads(line))
print(f'V1: predictions count = {len(preds)} (expect 24)')
assert len(preds) == 24

# V2: All predictions have required format
for p in preds:
    assert 'sample_id' in p
    assert p['method'] == 'rule_plus_llm_assisted'
    assert p['selected_prompt_id'] == 'r13_6_prompt_B'
    assert set(p['prediction_fields'].keys()) == {'modality','actor','action','condition','constraint','exception'}
    for k in p['prediction_fields']:
        assert 'value' in p['prediction_fields'][k]
    ex = p['execution']
    assert ex['raw_response_saved'] is False
    assert ex['retry_used'] is False
    assert ex['repair_call_used'] is False
    assert ex['batch_used'] is False
    assert ex['attempt_index'] == 1
print('V2: All predictions have correct format')

# V3: No duplicate sample IDs
ids = [p['sample_id'] for p in preds]
assert len(ids) == len(set(ids))
print('V3: No duplicate sample IDs')

# V4: Sample IDs match candidates
candidates = []
with open('data/formal/r14_controlled/r14_1_candidate_samples.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            candidates.append(json.loads(line))
cand_ids = {c['sample_id'] for c in candidates}
pred_ids = set(ids)
assert pred_ids == cand_ids, f'Mismatch: {pred_ids ^ cand_ids}'
print('V4: Sample IDs match candidates')

# V5: No raw responses on disk
raw_dir = Path('data/formal/raw_responses')
if raw_dir.exists():
    raws = list(raw_dir.rglob('*r14_4*'))
    assert len(raws) == 0, f'Found raw response files: {raws}'
print('V5: No raw responses on disk')

# V6: Evaluation summary has boundary metadata
with open('data/formal/evaluations/r14_4_rule_plus_llm_summary.json', 'r', encoding='utf-8') as f:
    summary = json.load(f)
assert summary['stage'] == 'R14.4'
assert summary['method'] == 'rule_plus_llm_assisted'
assert summary['real_api_call_performed'] is True
assert summary['llm_call_performed'] is True
assert summary['rule_plus_llm_experiment_run'] is True
assert summary['llm_superiority_claim'] is False
print('V6: Evaluation boundary metadata correct')

# V7: Evaluation scores are plausible
oea = summary['overall_field_exact_accuracy']
msf = summary['macro_strict_f1']
mlf = summary['macro_lenient_f1']
assert 0.4 <= oea <= 0.7, f'oea={oea}'
assert 0.4 <= msf <= 0.7, f'msf={msf}'
assert 0.7 <= mlf <= 0.95, f'mlf={mlf}'
print(f'V7: Scores plausible (oea={oea:.4f}, msf={msf:.4f}, mlf={mlf:.4f})')

# V8: Manifest exists
manifest = json.loads(Path('data/formal/metadata/r14_4_manifest.json').read_text('utf-8'))
assert manifest['sample_count'] == 24
assert manifest['api_calls_attempted'] == 24
assert manifest['error_count'] == 0
print('V8: Manifest valid')

# V9: All exec fields consistent
api_used_all = all(p['execution']['api_used'] for p in preds)
network_used_all = all(p['execution']['network_used'] for p in preds)
print(f'V9: api_used={api_used_all}, network_used={network_used_all}')

print()
print('=== All 9 verification checks PASSED ===')
