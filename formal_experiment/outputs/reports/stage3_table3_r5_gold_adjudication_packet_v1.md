# S3-TABLE3-R5 Formal Gold Adjudication Packet v1

**Status:** `AWAITING_USER_GPT_APPROVAL`

**Gold derivation:** Gold derives from regulation semantics + controlled BPMN construction, not from any method prediction.

**Prediction-blind:** true (no Ours/Sun/Winter predictions or method scores were read).

## Summary

- Core requirements: 33
- Core cases: 113
- Baseline / missing_action / incorrect_actor / out_of_order: 33 / 33 / 33 / 14
- Reference-state counts: `{"not_applicable": 47, "not_scored": 57, "satisfied": 155, "violated": 80}`
- not_applicable / not_scored cells: 47 / 57
- Order types: `{"TYPE_A_explicit_action_precedence": 7, "TYPE_B_trigger_precedence": 6, "TYPE_C_deadline_arithmetic_only": 1}`

## Official provenance verification

| Requirement | Citation | Official URL | Verified | Official sentence SHA-256 | Local match |
|---|---|---|---|---|---|
| R5-S7-T1 | GDPR Article 40(7) | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32016R0679 | 2026-09-26 | `91d1a82e534e9695c90d73d905e741f0e191d9251cb4532f7ab7cd66a5f8f0c6` | True |
| R5-S8-T1 | GDPR Article 43(1) | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32016R0679 | 2026-09-26 | `367392f6e377363ce4164c015f075d716c2a1e23e71386161eeba4042f535e30` | True |

## HUMAN_REVIEW_REQUIRED

### OFFICIAL_SOURCE_IDENTITY_S7_S8

- Requirements: R5-S7-T1, R5-S8-T1
- Severity: `review_before_gold_freeze`
- Issue: R5-S7-T1 and R5-S8-T1 are new independent test rows. The local snapshot is a processed Winter file, but the two relevant sentences match the official EUR-Lex sentence SHA-256 exactly.
- Requested action: User/GPT confirms that the official EUR-Lex sentence is the experiment source identity before Gold freeze.
- Disposition: `APPROVED_FOR_GOLD`

### R5_S2_T1_SEMANTIC_SOURCE_MISMATCH

- Requirements: R5-S2-T1
- Severity: `candidate_asset_not_scored`
- Issue: The task-model action 'Verify that parental authorisation has been obtained where required' is not literal in the Article 8(1) excerpt; the verification duty appears in Article 8(2). The row is an excluded candidate/permission asset and is not scored in the three-class core F1.
- Requested action: Confirm that R5-S2-T1 remains excluded, or provide explicit semantic disposition. Do not silently convert this row into a core missing-action label.
- Status: `SEMANTIC_SOURCE_MISMATCH_REQUIRES_REVIEW`
- Disposition: `KEEP_EXCLUDED_CANDIDATE`

### CANDIDATE_PERMISSION_PROHIBITION_ASSETS

- Requirements: R5-S2-T1, R5-S2-T3, R5-S2-T4, R5-S3-T3, R5-S3-T4
- Severity: `candidate_assets_not_scored`
- Issue: Five permission/prohibition/cessation rows are retained as candidate semantic assets. Their task wording is a project adaptation for candidate BPMN construction, not a scored positive-duty Gold label.
- Requested action: Confirm the five candidate exclusions remain out of formal core F1.
- Disposition: `KEEP_ALL_FIVE_EXCLUDED_FROM_CORE_F1`

## Candidate exclusions

| Requirement | Case | Citation | Reason | Disposition |
|---|---|---|---|---|
| R5-S3-T4 | candidate_4464b4814fa1 | GDPR Article 21(3) | prohibition_cessation_modelled_as_missing_action; invented_cease_task | candidate_semantic_asset_not_scored |
| R5-S3-T3 | candidate_6ea5a10bb167 | GDPR Article 21(1) | prohibition_cessation_modelled_as_missing_action; invented_stop_task | candidate_semantic_asset_not_scored |
| R5-S2-T1 | candidate_74415d329801 | GDPR Article 8(1) | permission_modelled_as_positive_duty | candidate_semantic_asset_not_scored |
| R5-S2-T3 | candidate_b25297a0124d | GDPR Article 9(2)(a) | permission_modelled_as_positive_duty; condition_and_negated_condition_confused_with_exception | candidate_semantic_asset_not_scored |
| R5-S2-T4 | candidate_bfcf3406da11 | GDPR Article 9(2)(b) | permission_modelled_as_positive_duty; negated_condition_misstated_as_exception | candidate_semantic_asset_not_scored |

## Requirement index

| Requirement | Family | Split | Citation | Eligible types | Order type |
|---|---|---|---|---|---|
| R5-D-01 | gdpr_art13 | development | GDPR Article 13(3) | missing_action, incorrect_actor, out_of_order | TYPE_A_explicit_action_precedence |
| R5-D-02 | gdpr_art14 | development | GDPR Article 14(4) | missing_action, incorrect_actor, out_of_order | TYPE_A_explicit_action_precedence |
| R5-D-03 | gdpr_art18 | development | GDPR Article 18(3) | missing_action, incorrect_actor, out_of_order | TYPE_A_explicit_action_precedence |
| R5-D-04 | gdpr_art35 | development | GDPR Article 35(1), first sentence | missing_action, incorrect_actor, out_of_order | TYPE_A_explicit_action_precedence |
| R5-D-05 | gdpr_art36 | development | GDPR Article 36(1) | missing_action, incorrect_actor, out_of_order | TYPE_A_explicit_action_precedence |
| R5-D-06 | gdpr_art7 | development | GDPR Article 7(1) | missing_action, incorrect_actor | not_order_eligible |
| R5-D-07 | gdpr_art7 | development | GDPR Article 7(4) | missing_action, incorrect_actor | not_order_eligible |
| R5-D-08 | gdpr_art15 | development | GDPR Article 15(1) | missing_action, incorrect_actor | not_order_eligible |
| R5-D-09 | gdpr_art16 | development | GDPR Article 16 | missing_action, incorrect_actor | not_order_eligible |
| R5-D-10 | gdpr_art17 | development | GDPR Article 17(1) | missing_action, incorrect_actor | not_order_eligible |
| R5-D-11 | gdpr_art20 | development | GDPR Article 20(1) | missing_action, incorrect_actor | not_order_eligible |
| R5-D-12 | gdpr_art33 | development | GDPR Article 33(1) | missing_action, incorrect_actor, out_of_order | TYPE_B_trigger_precedence |
| R5-S1-T1 | gdpr_art13 | development | GDPR Article 13(1) | missing_action, incorrect_actor | not_order_eligible |
| R5-S1-T2 | gdpr_art13 | development | GDPR Article 13(2) | missing_action, incorrect_actor | not_order_eligible |
| R5-S1-T3 | gdpr_art14 | development | GDPR Article 14(1) | missing_action, incorrect_actor, out_of_order | TYPE_B_trigger_precedence |
| R5-S1-T4 | gdpr_art14 | development | GDPR Article 14(2) | missing_action, incorrect_actor, out_of_order | TYPE_B_trigger_precedence |
| R5-S2-T2 | gdpr_art8 | test | GDPR Article 8(2) | missing_action, incorrect_actor | not_order_eligible |
| R5-S3-T1 | gdpr_art12 | test | GDPR Article 12(3) | missing_action, incorrect_actor, out_of_order | TYPE_B_trigger_precedence |
| R5-S3-T2 | gdpr_art12 | test | GDPR Article 12(4) | missing_action, incorrect_actor, out_of_order | TYPE_B_trigger_precedence |
| R5-S4-T1 | gdpr_art24 | test | GDPR Article 24(1) | missing_action, incorrect_actor | not_order_eligible |
| R5-S4-T2 | gdpr_art25 | test | GDPR Article 25(1) | missing_action, incorrect_actor | not_order_eligible |
| R5-S4-T3 | gdpr_art28 | test | GDPR Article 28(3)(a) | missing_action, incorrect_actor | not_order_eligible |
| R5-S4-T4 | gdpr_art19 | test | GDPR Article 19 | missing_action, incorrect_actor | not_order_eligible |
| R5-S5-T1 | gdpr_art35 | development | GDPR Article 35(2) | missing_action, incorrect_actor | not_order_eligible |
| R5-S5-T2 | gdpr_art35 | development | GDPR Article 35(9) | missing_action, incorrect_actor | not_order_eligible |
| R5-S5-T3 | gdpr_art35 | development | GDPR Article 35(11) | missing_action, incorrect_actor | not_order_eligible |
| R5-S5-T4 | gdpr_art36 | development | GDPR Article 36(2) | missing_action, incorrect_actor, out_of_order | TYPE_C_deadline_arithmetic_only |
| R5-S6-T1 | gdpr_art32 | test | GDPR Article 32(1) | missing_action, incorrect_actor | not_order_eligible |
| R5-S6-T2 | gdpr_art32 | test | GDPR Article 32(4) | missing_action, incorrect_actor | not_order_eligible |
| R5-S6-T3 | gdpr_art33 | development | GDPR Article 33(2) | missing_action, incorrect_actor, out_of_order | TYPE_B_trigger_precedence |
| R5-S6-T4 | gdpr_art34 | development | GDPR Article 34(1) | missing_action, incorrect_actor | not_order_eligible |
| R5-S7-T1 | gdpr_art40 | test | GDPR Article 40(7) | missing_action, incorrect_actor, out_of_order | TYPE_A_explicit_action_precedence |
| R5-S8-T1 | gdpr_art43 | test | GDPR Article 43(1) | missing_action, incorrect_actor, out_of_order | TYPE_A_explicit_action_precedence |

## Case index (all core cases)

| Case | Requirement | Variant | Expected states | BPMN SHA-256 |
|---|---|---|---|---|
| case_9c6fcd32f03c | R5-D-01 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=satisfied | `585f5c5ee9cf96639e6ec2881c4e2363a6aefe9f7d770adf5266b77c5bf36a1f` |
| case_a9fd75331508 | R5-D-01 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=satisfied | `9c70f6a3d7fd37cc4d3a58fea4029d0a991fbb6ca93fd96fd7ae232cb334d811` |
| case_18d0d72c49e8 | R5-D-01 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_applicable | `a237b2d3eb9a898e7ada4a0a10ec865e8e2b8b3783483bbd0499c6c93fc3370c` |
| case_3b01b9c36d0f | R5-D-01 | out_of_order | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=violated | `0506e9eb45def984de8831335a2f153454039cd1c5391241849c9eb125dad398` |
| case_f7bb207445df | R5-D-02 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=satisfied | `63539b34ff8c5051adcfc7368133468c9b23e09022e4299b386382f9d2ef5b10` |
| case_648835a58615 | R5-D-02 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=satisfied | `c7bd9177f134128a869a0c8966e7139584c1f58c40fb25076d6a9aacb973ac41` |
| case_2a918b013dbb | R5-D-02 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_applicable | `e9420e89b48da0e3b27a92473dcea563fcef8d26958cd0b1b741dc07de7dddd8` |
| case_ff937cc4c24e | R5-D-02 | out_of_order | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=violated | `8d410d85fc32275c5317404bc6b668aa537ce616d194517d2a111d76f3a6e456` |
| case_a1712c670943 | R5-D-03 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=satisfied | `a919a6c22eae483b0fa2cdbfd92db30930ad494f54e047fc483ab86a8b16bdb6` |
| case_50f498770ae9 | R5-D-03 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=satisfied | `a46934edc7562390f067a48671702816969a0889a614b4c37ca8da934bcaec9a` |
| case_6fda0f20b097 | R5-D-03 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_applicable | `0cebbc40fe5c9213842ec05016b1a6d04de40c7228d76c3941346e248053d99a` |
| case_f6dc7b084b03 | R5-D-03 | out_of_order | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=violated | `7af02c6ef9b29175c6fd4bba7dba958df86f4687deb9ce8d8b0d4ea835c91d36` |
| case_ec2a9cc66fae | R5-D-04 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=satisfied | `d12dffe2d749e82d69eebb3423a095e53f3c8ec4a9e45e47986a2e2a41920518` |
| case_4aec33c00dc8 | R5-D-04 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=satisfied | `f65967233cf262df7a07a89ed62b6e2ed135b3c562950f9a610c55875c791625` |
| case_aae318ffa9f8 | R5-D-04 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_applicable | `0d57f364531420ac13b420cbefb42b216f4530af6f37d87551a9c37fc3166dbd` |
| case_a2f445c641d1 | R5-D-04 | out_of_order | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=violated | `bd7bdfa1959a837c1163ac01c39b73cc1309ad80100429cc447bf1a327b26632` |
| case_b15419d68b21 | R5-D-05 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=satisfied | `353cf7ec877a7e71a45ac993648b1874b339e8d72c1b29bae9bd2f90a71062c6` |
| case_35ae84dddc65 | R5-D-05 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=satisfied | `87b47aa0e9c07051104ff38c855a489ba9037423a875bc28f0799680025b2d91` |
| case_1d6ccfc9b95c | R5-D-05 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_applicable | `636c6c8c5dc34b84b2470e6639f7d32b225dfa1d1f54a484c38b937d690f8d8a` |
| case_d8029187c213 | R5-D-05 | out_of_order | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=violated | `caa1169abc16f433a85f549aee1b01603c0d82dbd2a4909544dfac95a68dae66` |
| case_65628736fcec | R5-D-06 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `e9c46a560bfed27295fb96397c3242f396d8839fc25c8d67c0829fd8398d86ac` |
| case_89f6d9e7047b | R5-D-06 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `2405399ce4555a76498ddc6c3725e1f7c07b1c1f1e66d27970c7a2e39d9828e4` |
| case_e382dcb7708b | R5-D-06 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `fe059e8d80912da51363efd2fb242a7adcbf3c55e0f83c7abe99a9c305da53aa` |
| case_1fafed22bfdd | R5-D-07 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `8ab1bdd260df20733b3b8a11566ad010ea371e8733cbe7993aa2e530ffe96751` |
| case_dbe5d0716353 | R5-D-07 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `762887dff011f0a55db3a55319e3c75bb83d3880a1146d1504d0e339c4615586` |
| case_6711c5a0dad8 | R5-D-07 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `d51a4f379fabd477b76c75ab077cfdffed2b46e342aa499b356f40f1e6bdf1ed` |
| case_19b2d6f1bfb0 | R5-D-08 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `f186a60037f6fc3a7fb8d270917e945c469f0437b32324e680a524b54e45fa53` |
| case_0164a880bf44 | R5-D-08 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `8048dc3e6229c00e3f159f5c32f30d694de58476dfc6654ca2ed0718d0d6f3dc` |
| case_591221684b9f | R5-D-08 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `dfa4aaac0bfc207559b118e79fe1762021d777b983af35ce7ea7cd720931d770` |
| case_72073c61be4c | R5-D-09 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `b75207972ea85b06a89a4744ea04a20b0c081819b69445e6f386bcf813189e7a` |
| case_d2f6fee80f4e | R5-D-09 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `1e331bfb76530c69d48a75cb0720819d773ad34bdec9f729a12985d32bcb95cc` |
| case_7396f1ecbaf2 | R5-D-09 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `3f63dfc3db81d0c255c067754856c76020e3a36d3e96c30a556aa36c4fcf1dd8` |
| case_26761c804689 | R5-D-10 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `42edee02e18f16a78465e771d59578db43fd01ffa8d26c483de6b4b3ca98d534` |
| case_d824876f7bf8 | R5-D-10 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `1b9b0ed4b3e5493c45d9702f15e099b437978a85df3a76aabb165b59138974d3` |
| case_b6bda7bca9ff | R5-D-10 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `11b16da5911e0dfd56876ed31f367d5d6e426600b9853ae7dfce2165f2178ce6` |
| case_436340192865 | R5-D-11 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `a0bc19b5dd8bc3fda1fe8c55bd82816abc71931768373e87ae180b0c58e36541` |
| case_026d89f057e8 | R5-D-11 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `a31f86d5e87ad6664931e967390d7f296aede7e3d42f3fb77ee953edd306eb95` |
| case_f2558cf5f53d | R5-D-11 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `458303fdaa90507801f297d511e51c5ac0f7a6bfa67bfa29aa70940bff6f097c` |
| case_1fd8d9be0c9d | R5-D-12 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=satisfied | `770140230d7b5c7e6e7627cb7351fc5c11df4ea0412b26008ef14b54f0670426` |
| case_2fbe69c72793 | R5-D-12 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=satisfied | `0b0683358e4d786a9d8d32b0b0e6a5fd894525bef869adbf16b1645cf8895eb2` |
| case_c5b585c4439f | R5-D-12 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_applicable | `404218770989b2e4f17c695d8a2c20902110bee8c63ff53d02bdc288fb52a1aa` |
| case_27553ad672b2 | R5-D-12 | out_of_order | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=violated | `6a4f16fc6fc743195402d3210b87c33c2db1f02c5e7795c55e67b9266a084820` |
| case_fe8ab9bca28a | R5-S1-T1 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `b3fa89c95ac29de4d525e7f272e0d51d6814ff71ef8c3b3c3fc489d49f2aaf25` |
| case_4c59fee89687 | R5-S1-T1 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `354a15b37deee6ff43a8edbb3b6cb4f81137b4ac630bd3bb6a186e9e4570c990` |
| case_9742238625a1 | R5-S1-T1 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `4139560018552cde193c629f9aa7611a0caa1ecf06661376a07c57ad44e94d06` |
| case_3db096abecec | R5-S1-T2 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `b1cfbf484edd4732a2fbfd93b6dae4192873df5273396af65a58d4e44a2ff7cf` |
| case_b72abd1e6b8b | R5-S1-T2 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `4556b7bd9c7215f8db044efa63436e92f9492a2ebfb32beef9f9feb25f66eb62` |
| case_64985e535fd0 | R5-S1-T2 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `fa9e42e755d11917fae0669e6272a7160a452b921d909db28fe06e26e1f4e331` |
| case_d7a85c641eb0 | R5-S1-T3 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=satisfied | `fc098f4da932592f2319605725455f91b3e84b1024c50ceccf84e6801c242e94` |
| case_27a05191cde1 | R5-S1-T3 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=satisfied | `d6ebbf51f433e3c4b663595c9192d37c444d9800ebbc7a9606cf9da8a4af5ca3` |
| case_806f7830225a | R5-S1-T3 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_applicable | `51c1a283746d409c2acf051f0a2570890e2643de0896e5bcc449842e20c16726` |
| case_250418025567 | R5-S1-T3 | out_of_order | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=violated | `21d3e5cc93acf69716aac6545511bdec83ae75825b0178cd7d31aa6d6138a8ea` |
| case_6209f221b20b | R5-S1-T4 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=satisfied | `8035c0f52da7f221ecdec2952e2884262965648f5e23ebd536e568be93ae351f` |
| case_8480429a9517 | R5-S1-T4 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=satisfied | `6fc0bd828c6b82c6c78f108f27f20ba886d02debe9af6ae23f83ca918e8b381f` |
| case_b91fc088d4c5 | R5-S1-T4 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_applicable | `94219b8f819375c010403fb06be06fc0018e5d85c5e52730c922872f65458942` |
| case_2e0630dc5be5 | R5-S1-T4 | out_of_order | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=violated | `8983ddc8c98fe584f86e938df2302f88dfbb7a6f88fa3cf96acbee44c209c050` |
| case_99b7bc6f1fc6 | R5-S2-T2 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `1f1f48073b95eea065d1867af79669acc9c87f35d5fe33dab37e79e622893b80` |
| case_47ac07c5ced4 | R5-S2-T2 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `e8caa123c6c3ce09ef800b7ab7c6d1f6cb25767c63ee7c56ea7594abbca9d2a2` |
| case_7c047344bd97 | R5-S2-T2 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `91687b705a62a36ef21a72ea4d52d490b5bbe9ac40b5fe669a77be36353022a8` |
| case_c20eeebe67dd | R5-S3-T1 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=satisfied | `30ecadffcd94eb346d05989ee2ecef0eadd45104c01548301e9fb830e01093cc` |
| case_293adf4880a6 | R5-S3-T1 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=satisfied | `6b2acade7f6828ce7c8222c958db401ad2cb17e47ffc0dc0b98de2c795277d89` |
| case_706168fa759f | R5-S3-T1 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_applicable | `3c889d895f32167dd516e793c86bd4f2a1421e584623440ed5a2be833d870508` |
| case_d391f7745e2d | R5-S3-T1 | out_of_order | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=violated | `b1130d4495855a84079519fa9bd46a39965aebc0644b162b866a13ffc57b2988` |
| case_8447fd35edc7 | R5-S3-T2 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=satisfied | `5ef50a7caa54d8dafae906c057458273f14dac0ed411b949c97d8ce90ec383d9` |
| case_f88b4ccdc713 | R5-S3-T2 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=satisfied | `99df94b521471f37c4582788728ef67cc020dc43fbcb4e89ddc705f99242c59d` |
| case_220918995d29 | R5-S3-T2 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_applicable | `a459ef3a9cc4acfd9b84a13cdf66e7bface1543257282be5b5331cf7d0105605` |
| case_ba895d210eaf | R5-S3-T2 | out_of_order | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=violated | `799292eddef6955038b949f7cfe36cd1d6494c64e26fc1048dee56abba86cbc8` |
| case_6d3b90db76ed | R5-S4-T1 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `ee49abbbb380169a372e8ba0057da12d536f4955562574968b5570053180bd92` |
| case_5751d20f4ed7 | R5-S4-T1 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `cc4d0b2cc78424035512d13c25f778494d11f00f2c2727823c0c400bfd86c3bd` |
| case_221218bba2d3 | R5-S4-T1 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `312d9860559f54f6e668fe1633e04daa732c102a32e8405c1a4cc38bf506259a` |
| case_11233dd30223 | R5-S4-T2 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `bf68296af9b4047d37514e649c11b71bdd15e70b5e73c9d8bd5b5626b21051d6` |
| case_66774ccb1348 | R5-S4-T2 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `528eae3517ff42899f93781f136a8bb998563ae50be2e48979908ec3275421c9` |
| case_156f3d39867e | R5-S4-T2 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `e2cea5a75fd869f5dcd1b8b603fca1328b8d5aad1f097739ec7ac23af6fca2a8` |
| case_f2e0ecd3abf8 | R5-S4-T3 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `5565deb10b28ba25bdf9761c51b710060ef130ea9c02499282c1db5b1f2e52b4` |
| case_0f67bfdd277b | R5-S4-T3 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `6edf8de890649e03f6c5000c307b002b9767ac269784686ae60272b8c9416d92` |
| case_de1137fcd3ae | R5-S4-T3 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `96b86d468037de4e133651647419474c1b6b35dd53f6fce387b3b9da1819f575` |
| case_88a2fd3f66cf | R5-S4-T4 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `1c2cd965791661518beeb5291246672b28cf68f14ec2577174c173d2c34689e5` |
| case_81af7889b5bb | R5-S4-T4 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `3eb0011827eb7fe893ac8caf3ddd86d0d99a52127c790874d21f34341cd337e1` |
| case_e29a5ec0bbbc | R5-S4-T4 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `b5bf6822f47967414626f43daf88b5700a0813b42c005454e6121eb15bab75c2` |
| case_a0f75080210f | R5-S5-T1 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `5faac2cbd4ee78fbe33c739018ea2017d24bff2215ac291f325ec8b809282a1f` |
| case_e1847c1c4ceb | R5-S5-T1 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `b9b28398c233409afddb8f319bb9822cd5b78378fc94bfe155d96c08a4a1adcf` |
| case_6f4087fc924f | R5-S5-T1 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `00d707008b43a0b67edce7c5c38e7b84c24275ef49389fb6b95a8f204550a260` |
| case_5bcf29af32f6 | R5-S5-T2 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `dc1afe186fd5dd560e3841627368ac143a0c68a5d4bcbc8b3564b5b7ee65d517` |
| case_bb81d68dc7f5 | R5-S5-T2 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `e65e8bcd16c0f24c205e4e95f68ff0d1f76816c463a792d2e026d04bd048ba96` |
| case_fb1fd0822200 | R5-S5-T2 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `dd53e0b188679a4f28fb5663bd7f0438bcfd0642d6eb008fbc008faa496f7c77` |
| case_c962e006a37d | R5-S5-T3 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `0575335827edc8b9aed34f6f80dc0ca7674ee162723cd3cbba5ba589cfbb4aed` |
| case_203f2134c0ec | R5-S5-T3 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `2d2ef8c15f7389c466a9e6ac4ed005f6c98bff3ac8fb69fc752bda599315ce12` |
| case_e85d2791c743 | R5-S5-T3 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `e8733e03bc3044a6cf8a7912235229889b3073caf50b48aea49aedddea6371b5` |
| case_d46c4dbbf7b8 | R5-S5-T4 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=satisfied | `fdce7acbf22b593f2b30fa37a1b10dd9103839606b790eae4b97cae0318461ec` |
| case_1a2d6abc026a | R5-S5-T4 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=satisfied | `ec54319ee7cd003095ca8fc289606d3549fdd601b3d8d8eebe1f055cf88f2f56` |
| case_25d20a4b486f | R5-S5-T4 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_applicable | `7a3f0782ea37281f0bdb6c74b38e7f0cbab748531f10faf0e631beededf27e93` |
| case_8c729ed572f4 | R5-S5-T4 | out_of_order | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=violated | `693b80930e411c6c655a42111920e00de171e985fa4b78e8b86a6d4136b29eb8` |
| case_8d21f4b6fb98 | R5-S6-T1 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `07f46009d4f27441582afe7ceb459fbecac790ba73c1534a0a73f67377c4a606` |
| case_5b249b3a462b | R5-S6-T1 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `5bcab56d328d26d71abbb7c97628c6ae5a78a1588c0cfd3893e887ebd8ee6aff` |
| case_b5a60700383d | R5-S6-T1 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `622c7574d36378ebfafcb1969aae007b21da086c708e38364716c07a69e7f8d4` |
| case_0ca6ea35f87e | R5-S6-T2 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `a25376e516f83b4750ab99bcfe93d08c5ee6d08009c19cf55fc0c7c53c293e0a` |
| case_5b5cc6e83173 | R5-S6-T2 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `c098ae17a6cf514e63bf1125d13fd64801e19162a09093c28d8f4d0b2eb2cd98` |
| case_f81de319913d | R5-S6-T2 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `d69a53e5061156e70ab6ec2fdb1d4be765705135389ef7625bf548b7b5e5ab00` |
| case_e44cf42b30f7 | R5-S6-T3 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=satisfied | `38f5e531c4d458ae83033ff436739ca110d3d8f1ab39febcfdfa5f2cfb8b30c7` |
| case_6cb0e57227f2 | R5-S6-T3 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=satisfied | `cbe2d2008167af378d762a6be0418bd5e88082abc1749a7e2f9cca307be6faff` |
| case_0697d9b84b86 | R5-S6-T3 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_applicable | `1d344921dbd5220b74b3aa5c9d043b865cd4da2f075a09f21d44cc7b1bf63773` |
| case_cecd14adb006 | R5-S6-T3 | out_of_order | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=violated | `95313f61a7d6f8ad4dd1239c87fe6aa1d90cc96a89ae23be234d96ed65893c44` |
| case_1f817e0b0d37 | R5-S6-T4 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=not_scored | `7bd6a57c0ac075dba35c125845d0f751196ffca6cf5246b3ed3c429327758648` |
| case_661cbff65102 | R5-S6-T4 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=not_scored | `5f1033308e7a8de1f08656015ca3a2605e9c79079c963f6a5450c835894a9df7` |
| case_36a5f51046f7 | R5-S6-T4 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_scored | `5517588e259d4176ed30fdc7bdbdc8cc1731cb5a5951138b45a1227a901f8f43` |
| case_1e5363aa87b5 | R5-S7-T1 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=satisfied | `387c1c413fc52c8211f9ef47775ba9c8f977d3a7445ed23d0b24813bb8552986` |
| case_c2c28cb239bc | R5-S7-T1 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=satisfied | `382da33a2c4eb8c0af769f9b2714b9a9e21b6c838027208eea658eeeac292800` |
| case_64e83d36bba3 | R5-S7-T1 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_applicable | `ff17860d321108bb74106716b1b33886936c3cbaba60f2731aa2f26c5f1af02a` |
| case_7dcc88ac3cf1 | R5-S7-T1 | out_of_order | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=violated | `35e3b1ebeac0eff33f22d270ecf66a2a382c15853ada912194ca6197e7f05f81` |
| case_83e2662c1457 | R5-S8-T1 | baseline | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=satisfied | `b81674f72cee0b5719cb39c32044ccb8c7906f6d622c05879dae8ad030fe7e00` |
| case_44ded3550ee5 | R5-S8-T1 | incorrect_actor | incorrect_actor=violated, missing_action=satisfied, out_of_order=satisfied | `6f9f3406b0bdb37a4d71b8a8bc1e00b13b1aee0b29527d78d5c61ec5aba0f909` |
| case_d1ab41696c03 | R5-S8-T1 | missing_action | incorrect_actor=not_applicable, missing_action=violated, out_of_order=not_applicable | `4a4695cfe09e8e68db6f44a6d1b3404f6eadce26286b15205237e22141928c68` |
| case_3af5fd62647b | R5-S8-T1 | out_of_order | incorrect_actor=satisfied, missing_action=satisfied, out_of_order=violated | `94827aef2fb42fa661fcbd4036808d14af9445d0957f22fc3c2572bbd2152ed9` |

The full exact source excerpts, six-element evidence bindings, mutation descriptions, target relations, and unsupported/NA reasons are in the JSON packet.
