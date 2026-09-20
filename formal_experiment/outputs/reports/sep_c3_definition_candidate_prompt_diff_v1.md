# SEP-C3 Definition Candidate Prompt Diff v1

- Status: **candidate-only; not applied**
- New API / LLM calls: **0**
- Active prompt changes: **none**
- Gold changes: **none**
- Prediction changes: **none**

The candidate is assembled by the existing modular/refinement mechanism:
frozen common system + frozen existing E examples with only E4 replaced,
plus the approved R_DEF paragraph(s) appended as an independent system
paragraph.  S, J, R_A, and R_C are not activated in the candidate arms.

## 1. Active arm A vs candidate BASE

This diff should contain only the approved synthetic E4 replacement.

```diff
--- active_arm_A_sent_prompt.txt
+++ candidate_BASE_sent_prompt.txt
@@ -59,11 +59,9 @@
 - exception: "unless the data subject consents" [37,69)
 - conditions, constraints: empty
 
-Example E4 — definition clause followed by an obligation clause:
-Input: "'Personal data' means information about a person; the controller must protect it."
-- clause 1 span [0,48): definition; evidence "means" [16,21); actors and actions empty
-- clause 2 span [50,81): obligation; evidence "must" [65,69); actor "the controller" [50,64), normalized "controller"; action "protect it" [70,80)
-- conditions, constraints, exceptions: empty in both clauses
+Example E4 — synthetic shall-definition (one clause):
+Input: "A digitally signed copy shall be treated as an original document."
+- clause span [0,64): definition; evidence "shall" [24,29); actors empty; action "be treated as an original document" [30,64); no other field populated
 
 Example E5 — condition containing a nested constraint:
 Input: "The tax office shall refund the amount if the application is filed within two years."
```

## 2. Candidate BASE vs candidate BASE + R_DEF

This diff should contain only the approved definition guidance paragraph(s).

```diff
--- candidate_BASE_sent_prompt.txt
+++ candidate_R_DEF_sent_prompt.txt
@@ -18,6 +18,10 @@
 Basic output conventions (always required, independent of any optional semantic guidance):
 - Use zero-based start and exclusive end for every span. For every span, text must equal source_text[start:end]; every child span must lie inside its clause_span.
 - IDs are unique within the complete record. actor_action_map and order_relations entries may reference IDs only from the same clause.
+
+Definition is semantic rather than lexical. A clause may establish legal status, identity, classification or membership, legal fiction, or a scope/applicability characterization even without an explicit definition marker. "Shall" does not by itself make a clause an obligation, and "shall" plus a verb does not by itself determine modality. Classify from the semantic function of the clause in context. An obligation imposes required conduct or a required method on a duty bearer or regulated subject, whereas a definition characterizes what something is or how it is legally treated.
+
+A definition clause should still contain an action representing its definitional predicate. Do not omit the action merely because the clause is classificatory, stative, relational, or copular. Extract the predicate supported by the source evidence. This is an action-presence principle only and does not define a universal exact action-span boundary.
 
 <!--USER-->
 
```

## 3. Candidate hashes

| Render arm | System SHA-256 | User SHA-256 | Composition SHA-256 |
|---|---|---|---|
| BASE | `9db8893c75af4c306f5f5142ea77b6c93b6a2bae79a72ba8dd0f2b3ca1985d4f` | `ff181879858f08641b40a3e8799fa32e16235f70544b809cac7fddf9962797f5` | `3100c8521f3ad4a0a313293d4facdd37c92dccf8661e6021875750c58926da11` |
| R_DEF | `95c234ab44357411fb493f7b3ed46a29e76ada91f02ce3d2c1cd6b7af0496843` | `ff181879858f08641b40a3e8799fa32e16235f70544b809cac7fddf9962797f5` | `585d9a81116d8fb1b1cf1858b55e4a67457ca9886dbd0487f7f0d7474f5e8b07` |

## 4. Compatibility inspection only

These renderings are offline only and are not candidate arms for activation.

| Compatibility arm | Old arm | System is old arm + R_DEF | User is candidate E4 v2 |
|---|---|---|---|
| COMPAT_R_A_R_DEF | B | True | True |
| COMPAT_R_C_R_DEF | C | True | True |
| COMPAT_R_A_R_C_R_DEF | D | True | True |

## 5. Scope guard

- No `R_A` or `R_C` text was modified.
- No `S8` text was copied, reactivated, or modified.
- `semantic_rules_S.md` was not edited.
- `common_system.md`, `user_envelope.md`, and `output_format_J.md` were not edited.
- The active prompt files and active prompt manifest were not overwritten.
- No condition, constraint, or exception guidance was added or changed.
- No model was invoked and no prediction was produced by this candidate.
