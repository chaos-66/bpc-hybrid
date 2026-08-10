# D1/H1 zero-API candidate re-evaluation + shared comparison

- claim scopes: D1 candidate / formal-gate-blocked; H1 candidate / comparison-only / formal-gate-blocked
- new LLM/API calls: 0

## Methods
### sun_rule_only (formal)
- gate: ready (user-authorized 2026-08-10)
- fine 5-field F1: {'actor': 0.8039, 'action': 0.8554, 'condition': 0.7054, 'constraint': 0.4913, 'exception': 0.8148}
- coarse 5-field F1: {'actor': 0.8203, 'action': 0.8927, 'condition': 0.7738, 'constraint': 0.6182, 'exception': 0.88}
- modality label acc: 0.74

### direct_llm (formal)
- gate: ready (user-authorized 2026-08-11; zero-API snapshot publication)
- fine 5-field F1: {'actor': 0.7222, 'action': 0.88, 'condition': 0.7863, 'constraint': 0.5482, 'exception': 0.6957}
- coarse 5-field F1: {'actor': 0.7579, 'action': 0.9437, 'condition': 0.838, 'constraint': 0.7427, 'exception': 0.7619}
- modality label acc: 0.8333333333333334

### sun_llm_fallback (formal)
- gate: ready / comparison_arm_only (user-authorized 2026-08-11; zero-API snapshot publication)
- fine 5-field F1: {'actor': 0.4206, 'action': 0.8583, 'condition': 0.7086, 'constraint': 0.4931, 'exception': 0.8148}
- coarse 5-field F1: {'actor': 0.4296, 'action': 0.8945, 'condition': 0.7774, 'constraint': 0.62, 'exception': 0.88}
- modality label acc: 0.82

## Zero-API declaration
- new LLM/API calls: 0
- historical recorded calls: 300
