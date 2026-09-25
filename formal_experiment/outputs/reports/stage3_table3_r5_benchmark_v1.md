# S3-TABLE3-R5 Benchmark and Readiness

- status: DATA_READY / METHODS_NOT_READY / API_AUTHORIZATION_PENDING / FORMAL_RELEASE_NOT_APPROVED
- independent requirements: 36
- core cases: 108 (36 baselines + 72 variants)
- variants per type: {'incorrect_actor': 24, 'missing_action': 24, 'out_of_order': 24}
- development / test requirements: 12 / 24
- test independent candidates: 22
- semantic challenge cases: 24 (kept separate from core F1)
- six-element presence: {'modality': {'present_records': 36}, 'actor': {'present_records': 36}, 'action': {'present_records': 36}, 'condition': {'present_records': 21}, 'constraint': {'present_records': 36}, 'exception': {'present_records': 20}}
- current support: {'action': {'implemented': 36}, 'actor': {'implemented': 36}, 'condition': {'unsupported': 36}, 'constraint': {'indirect_only': 36}, 'exception': {'unsupported': 36}, 'modality': {'implemented': 36}}
- reused Ours Stage2 inputs: 14
- new Ours API requests: 22
- API cost cap: USD 1.18
- known detector issues: ['PRE-01-actor-surface-equivalence', 'PRE-02-known-action-surface-mismatches', 'PRE-03-same-action-different-object', 'PRE-04-correct-actor-and-business-object', 'PRE-05-correct-and-reverse-order', 'PRE-06-missing-task-while-text-mentions-task', 'PRE-07-actor-lost-after-coordinate-postprocessing']

No real API call, old experiment rerun, or formal Gold publication was performed.
