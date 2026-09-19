# SEP-C3 condition-preservation v1 — INCOMPLETE observation

Status: **INCOMPLETE / NO CANDIDATE CONCLUSION**

- Planned calls: 450
- Attempts persisted before send: 96
- Completed responses saved: 95
- In-doubt (attempt without response): 1
- Unsent: 354
- Known cost (95 verifiable responses, off-peak, cache-aware): $0.17664568
- Uncertain-attempt peak/max-output reserve: $0.01861200
- Known + uncertain conservative bound: $0.19525768
- Known tokens: prompt 114835, completion 78983, cache-hit 87040, cache-miss 27795

## Reason

The executor was launched as a background process, but a later agent-side polling command exceeded the tool timeout and reset the persistent PowerShell shell. That terminated the child process while the per-arm attempt record for `RC1 / estg_000074` had already been persisted but before its response row was saved. Because usage for that request cannot be verified, the user-mandated rule stops all later sends. The request must not be resent.

## Per-arm counts

| arm | attempts | completed responses | in-doubt | unsent | conversion ok | conversion failed |
|---|---:|---:|---:|---:|---:|---:|
| BASE | 32 | 32 | 0 | 118 | 30 | 2 |
| RC1 | 32 | 31 | 1 | 118 | 30 | 1 |
| RC_KEEP | 32 | 32 | 0 | 118 | 31 | 1 |

## Stage failures among completed responses (95)

- canonical_validation_status: 4

Transport failures among completed responses: 0.
Parse failures among completed responses: 0.
Input-binding failures among completed responses: 0.
Adapter/canonicalizer failures among completed responses: 0.

## Decision

No paired bootstrap, per-field performance table, or retention decision is reported. Each arm has fewer than 150 complete samples, so the frozen analyzer would reject the files. This is engineering-incomplete evidence, not a method result.
