# Stage 3 实验收束 v1

**STAGE3_EXPERIMENT_PAUSED / PAPER-FACING RESULT FROZEN**

当前优先级：**PAPER WRITING + PPT PREPARATION**。本次仅整理已有证据，作为 canonical status pointer。
历史报告不重写；历史“下一步”、API packet 和 deferred fix 不再是活动任务。只有用户明确要求才重开实验。

## 当前论文 / PPT 唯一 Table 3

状态：`PROVISIONAL_PAPER_FACING_TABLE3`；源文件状态名保留为 `PROVISIONAL_FINAL_PAPER_FACING_RESULT`。
若没有完成方法学更强的正式 unseen evaluation，且导师接受当前设置，则采用下列固定数值作为投稿 Table 3；
不预先声称导师已批准。

| Method | Precision | Recall | F1 |
|---|---:|---:|---:|
| Sun et al. | 0.3814 | 0.5362 | 0.4458 |
| Ours | 0.4393 | 0.6812 | 0.5341 |

| Method | Missing F1 | Actor F1 | Order F1 | Macro-F1 | Coverage | Unknown rate |
|---|---:|---:|---:|---:|---:|---:|
| Sun | 0.4554 | 0.4262 | 0.5000 | 0.4606 | 0.6667 | 0.3333 |
| Ours | 0.4935 | 0.5684 | 0.5000 | 0.5206 | 0.8905 | 0.1095 |

按源 JSON 完整精度计算：Precision +0.0578，Recall +0.1449，F1 +0.0883；
F1 **+8.83 个百分点，相对约 +19.8%**，Recall 约 **+14.5 个百分点**。
四位展示值相减得到 Precision +0.0579、Recall +0.1450，这是舍入顺序差异。
[closure JSON](stage3_experiment_closure_v1.json) 保留完整精度，不改 canonical 数值或历史来源。

既有 [canonical LaTeX](stage3_table3_provisional_final_v1.tex) 已核验，原样保留。
建议 caption：**Performance comparison of downstream compliance checking.**
既有 LaTeX caption 使用 “on downstream compliance checking”，保留原文。

## 测量范围与分母

本表测量三类下游违例检测的 pooled P/R/F1，不是 Stage2 要素抽取分数。
比较本地重建的 Sun Rules-Only 与 Ours 已冻结的真实 Stage2 预测，经同一 Stage3 检测链得到的结果；
不称 Sun 原论文报告值或完整原实现复现。

来源包含 33 条 requirements 的 113 个既有 development cases，以及既有 R5-S4-T3 两个顺序补充案例，
合计 115 个 case records。每方法计分 201 个 method-case-type cells：
Missing 113、Actor 80、Order 8，positive support 69、negative support 132。
其余类型不适用或不计分；这不是 115 × 3 的全类型准确率。
正例 unknown 计入 FN，负例 unknown 单列而不充当 TN；coverage 报告可观察计分单元比例。

| Method | TP | FP | FN | TN | Unknown positive（已含于 FN） | Unknown negative |
|---|---:|---:|---:|---:|---:|---:|
| Sun | 37 | 60 | 32 | 31 | 26 | 41 |
| Ours | 47 | 60 | 22 | 58 | 8 | 14 |

所有现有案例均经历 development / analysis。它们不是 unseen test、blind test 或 independently held-out final test；
`FINAL_UNSEEN_EVALUATION_COMPLETED=false`。已有两案例 supplement 使用真实冻结 Stage2 endpoints，
与下文 bonus 的 synthetic endpoint stubs 不同，但它本身也属于 development。

## 为什么 F1 约为 0.45–0.53

真实链路：法规文本 → Stage2 抽取 → regulatory action representation → 法规动作与 BPMN activity 对齐
→ actor association / U_r → BPMN 结构检查 → violation prediction。
抽取、动作边界、语义对齐或关系端点的错误都可能传递成 FP、FN 或 unknown。
因此 Stage2 抽取分数较高，不保证 Stage3 保持同等 F1。

[Missing failure analysis](stage3_bonus_missing_analysis_v1.json) 分析的是冻结主结果的信号。
以下为 **Sun 与 Ours 合计的 method-case cells**，不是独立法规数，也不是全部 Stage3 错误的百分比分解：

| Missing 证据 | 单元数 | 占 70 个 Missing FP |
|---|---:|---:|
| mapping-related FP | 50（Sun 35 / Ours 15） | 71.4% |
| broad scope-related FP（含 fragments） | 20（10 / 10） | 28.6% |
| strict gate-eligible scope FP（上行子集） | 11（6 / 5） | 15.7% |

24 个 Missing FN 中，20 个归于 mapping，4 个为 `M10_STAGE2_MISSING_ACTION`（Sun 4 / Ours 0）。
M10 仅指 Stage2 没有产生 action，不代表只有这 4 个错误与抽取质量有关。
FP 分类按 primary cell 互斥计数；action-level 分类可能重叠，不混用分母。

主要证据指向 **required-action semantic mapping failure / BPMN label paraphrase mismatch**。
例如既有 `case_0164a880bf44` 的 Sun action 为 “have the right to obtain from the controller confirmation as to whether or not”，
BPMN 标签为 “The data subject has a right of access and confirmation.”；保存的 similarity 为 0.4923，低于 gamma 0.55。
这是既有失败记录的引用，本轮没有重新计算相似度。

condition、constraint、exception、temporal expression 与 subordinate clause 中的 action-like span
未必是应独立对应 BPMN activity 的 mandatory action。碎片化确实存在，但严格可安全过滤的 scope 污染仅 11/70，
低于预注册 30% gate；即便计入 fragments，20/70 也未达到门槛。
因此 `ACTION_SCOPE_PROPOSAL=REJECTED`，没有采用额外 obligation-scope projection，也没有为提分改分母。

## Ours 改善了什么

总体 Recall 0.5362→0.6812，是 P/R/F1 中最大的绝对增量。
同样 69 个正例下，TP 37→47、FN 32→22，整体 FP 仍为 60。
Actor TP 13→27，Missing TP 23→19，Order TP 均为 1：净增 10 个 TP 主要来自 Actor。
Missing F1 上升同时伴随 Recall 0.6970→0.5758、FP 45→25；Actor precision 0.4643→0.4355 也没有提高。
不能解释为每类 Recall 或每项指标都提高。

这些观察与更充分的下游法规信息、尤其 actor-related 可观察性一致：
总体 coverage 0.6667→0.8905。不过这不是对“表示完整性”的独立因果验证。
Ours precision 仍为 0.4393，动作与短 BPMN 标签之间的语义对齐仍留下误报。

## Order 的正确解释

早期 native `order_relations` 为空，无法提供 `U_r ⊆ A_r × A_r`，是 Order F1 为 0 的主要原因之一。
冻结的 `SharedRuleOrderAdapterV3` 使用 source text、各方法已有 Stage2 actions、general syntax 和 shared matcher，
不读取 Gold、mutation type、BPMN target 或 reference order pair，也不虚构不存在的 action endpoint。

当前主表两方法 Order F1 均为 0.5000。只有 3 条主计分 requirements、8 个计分 cells、3 个正例，
每方法 TP=1、FP=0、FN=2、TN=1，coverage=0.2500。
Sun 在三条上生成 U_r，Ours 仅在 R5-S4-T3 上生成；生成规则边不保证能映射到 BPMN。
Ours 在 R5-D-01/02 缺独立 process endpoint；两方法在 R5-S7-T1/S8-T1 缺另一端点，限制保留。
早期 0→0.5 同时涉及 adapter、eligibility 与既有 supplement，不能作为单独 adapter 的可隔离增益。
详见 [improvement attribution](stage3_final_improvement_attribution_v1.json)。

## Bonus：保留但仅诊断

| Method | Precision | Recall | F1 | Missing F1 | Actor F1 | Order F1 | Macro-F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Sun | 0.4118 | 0.5385 | 0.4667 | 0.4554 | 0.4262 | 0.6667 | 0.5161 |
| Ours | 0.4643 | 0.6667 | 0.5474 | 0.4935 | 0.5684 | 0.6667 | 0.5762 |

`DIAGNOSTIC_ONLY`；`DO_NOT_USE_AS_TABLE3=true`；`BONUS_RESULT_METHOD_VALID=false`；
`CANDIDATE_FOR_FUTURE_TABLE3_METHOD=false`。

9 条 bonus requirements / 18 个 order cells 使用
`DEV_ONLY_SYNTHETIC_ENDPOINT_STUB_NOT_A_STAGE2_PREDICTION`；
BPMN labels 又刻意等于 endpoint surfaces，以隔离 projection / reachability。
它不能作为真实 Sun/Ours Stage2→Stage3 比较，也不能证明真实 endpoint 抽取或语义映射稳定。

9 条中 5 条正确生成边并识别 baseline/mutant，另 4 条失败（3 temporal-marker、1 endpoint binding），均保留。
0.6667 是既有与 bonus 合并的 order 诊断分数，包含 strict 与 borderline requirements，
不是仅对新 9 条或仅 strict 子集的成绩。
它表明 adapter/checker 在已给定端点的部分场景能检测顺序；
完整 “natural-language temporal relation → Stage2 action endpoints → U_r → BPMN actions” 链仍有限制。
详见 [bonus order](stage3_bonus_order_generalization_v1.json) 与 [bonus report](stage3_bonus_development_report_v1.json)。

## 方法冻结与结论边界

| 项目 | 冻结值 / 状态 |
|---|---|
| Semantic backend | sentence-transformers/all-mpnet-base-v2 |
| gamma / theta / tau | 0.55 / 0.45 / 0.8 |
| Order adapter | SharedRuleOrderAdapterV3 |
| Actor method | frozen；Definition 6 未改 |
| Missing scope | no additional obligation-scope projection adopted |
| Action scope proposal | REJECTED；strict 11/70 < 30% |

可支持的结论：在相同 downstream checking pipeline 与当前构造评价 benchmark 上，
Ours 的总体 Precision、Recall 与 F1 高于本地重建的 Sun baseline。
不证明未见数据泛化、生产可用性、统计显著性或所有类型均改进。
不使用 state-of-the-art、near-perfect、highly accurate、production-ready、
statistically significant 或 significantly outperforms。
映射瓶颈的量化依据来自 Missing FP，不能扩写成全部 F1 损失的精确归因。

## 历史保留与停止状态

- [Table3-v1](stage3_table3_v1.json)、[Winter historical baseline](stage3_v2_winter_archive_status_v1.json) 保留。
- [Stage3-v2](stage3_v2_development_report_v1.json)、[v2 revision 2](stage3_v2_revision2_development_report_v1.json)、[R1](stage3_table3_v4_r1.json)、[R2](stage3_table3_v4_r2.json) 保留。
- [历史 formal run](stage3_table3_formal_results_v1.json)、[final convergence](stage3_final_convergence_report_v1.json)、[bonus development](stage3_bonus_development_report_v1.json) 保留。

本次 REAL_LLM_API_CALLS / NEW_STAGE2_CALLS / NEW_MODEL_DOWNLOADS / NEW_THRESHOLD_SWEEPS /
NEW_BENCHMARK_CASES / NEW_HOLDOUT_CASES 全为 0；未读 `.env`，未运行实验、项目 audit 或测试套件。
只检查既有源数据、计数算术、SHA256、文档链接及 Git 范围，由单个 S3-CLOSE commit 记录。
历史文件、Stage2 predictions、Gold、benchmark、代码、配置和 prompt 均未修改。

`STAGE3_EXPERIMENT_STATUS=PAUSED`；`CURRENT_PAPER_TABLE3_FROZEN=true`；
`BONUS_RESULT_IS_PAPER_FACING=false`；`FINAL_UNSEEN_EVALUATION_COMPLETED=false`；
`NO_FURTHER_STAGE3_DEVELOPMENT_PLANNED=true`。本轮不新增实验待办。
只有用户以后明确要求继续 Stage3、重做 Table3、做 final unseen benchmark 或因导师要求提升结果，才重新开启实验。

## Provenance

分支 `paper-final-repair`；生成时 / 起始 HEAD `6d22732d169abb17b03f0a9f1afb3bb5884dbf43`。
Table 3 freeze commit `292edb2d9b5b2960779ab3723c6b2e693079aa2a`；
bonus source commit `6d22732d169abb17b03f0a9f1afb3bb5884dbf43`。
数值来源：[canonical Table 3](stage3_table3_provisional_final_v1.json)、
[final convergence](stage3_final_convergence_report_v1.json)；
诊断来源：[Missing analysis](stage3_bonus_missing_analysis_v1.json)、[bonus report](stage3_bonus_development_report_v1.json)。
完整源路径、28 个源文件 SHA256 与各自最后修改提交见
[closure JSON](stage3_experiment_closure_v1.json) 的 `git_provenance`。
这里的 HEAD 指写入前状态，收束提交及 push 结果在任务交付中记录，未在提交前预称远程备份完成。
