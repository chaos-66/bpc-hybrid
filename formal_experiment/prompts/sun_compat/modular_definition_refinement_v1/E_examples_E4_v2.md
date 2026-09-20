### E — Synthetic worked examples

These examples are synthetic and are not members of the formal evaluation set. They show representative semantic choices; use the common interface for the complete object.

Example E1 — unresolved subject pronoun:
Input: "It may cover a shorter period if a business is opened."
- clause_span: [0,54)
- modality: permission; evidence "may" [3,6)
- actor: "It" [0,2), normalized "it"; the unresolved actor is also recorded in unsupported_or_ambiguous
- action: "cover a shorter period" [7,29)
- condition: "if a business is opened" [30,53)
- constraints, exceptions: empty

Example E2 — passive clause with coordinated actions and two constraints:
Input: "The report must be filed within 72 hours and retained for 5 years."
- one clause over [0,66)
- modality: obligation; evidence "must" [11,15)
- actors: empty
- actions: "filed" [19,24), "retained" [45,53)
- constraints: "within 72 hours" [25,40), "for 5 years" [54,65)
- actor_action_map: actor_id null for both actions
- conditions, exceptions: empty

Example E3 — prohibition with an exception:
Input: "The controller may not disclose data unless the data subject consents."
- clause_span: [0,70)
- modality: prohibition; evidence "may not" [15,22)
- actor: "The controller" [0,14), normalized "controller"
- action: "disclose data" [23,36)
- exception: "unless the data subject consents" [37,69)
- conditions, constraints: empty

Example E4 — synthetic shall-definition (one clause):
Input: "A digitally signed copy shall be treated as an original document."
- clause span [0,64): definition; evidence "shall" [24,29); actors empty; action "be treated as an original document" [30,64); no other field populated

Example E5 — condition containing a nested constraint:
Input: "The tax office shall refund the amount if the application is filed within two years."
- clause_span: [0,84)
- modality: obligation; evidence "shall" [15,20)
- actor: "The tax office" [0,14), normalized "tax office"
- action: "refund the amount" [21,38)
- condition: "if the application is filed within two years" [39,83)
- constraint: "within two years" [67,83), also inside the condition span
- exceptions: empty