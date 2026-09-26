# Table 3：论文与 PPT 解释 v1

状态：`STAGE3_EXPERIMENT_PAUSED`；当前数据固定为 `PROVISIONAL_PAPER_FACING_TABLE3`。
本页是写作引用材料，完整证据与实时状态分别见
[closure](stage3_experiment_closure_v1.md) 与 [PROJECT_AUDIT](../../docs/PROJECT_AUDIT.md)。

## 1. Table 3 在测什么？

测量真实冻结 Stage2 抽取结果经过同一 Stage3 检测链后的三类违例 pooled P/R/F1；
Sun 为本地规则方法重建，不是原论文报告值。当前构造 benchmark 已用于 development / analysis，
不是 unseen、blind 或 independently held-out final test。

| Method | Precision | Recall | F1 |
|---|---:|---:|---:|
| Sun | 0.3814 | 0.5362 | 0.4458 |
| Ours | 0.4393 | 0.6812 | 0.5341 |

来源为 113 个既有案例及既有两案例 order supplement；每方法 201 个计分单元。
正例 unknown 计入 FN，负例 unknown 单列。F1 +8.83 个百分点，相对约 +19.8%。
沿用 [canonical LaTeX](stage3_table3_provisional_final_v1.tex)；
推荐 caption：**Performance comparison of downstream compliance checking.**

## 2. 为什么 F1 只有约 0.45–0.53？

法规动作先被抽取，再映射到较短的 BPMN activity labels，actor 与 order 又依赖这些映射和关系端点。
各环节的错误会传递成 FP、FN、unknown。既有 Missing 分析中，两方法合计 70 个 FP，
50 个（71.4%）归于语义映射；20 个（28.6%）与广义 scope / fragment 有关。
严格可安全过滤的 scope FP 仅 11 个（15.7%，为 20 个的子集），低于预注册 30% 门槛，
所以 action-scope proposal 被拒绝，没有为提分增加分母过滤。

## 3. 为什么这不等于 Stage2 抽取本身只有 50%？

Stage2 测要素抽取，Stage3 测经过动作表示、语义匹配、actor/order 构建和结构检查后的违例识别，
两者单位、分母和成功条件不同。Stage2 高分不能直接移作 Stage3 F1；
本表也不能反推 Stage2 只有约 50%。Missing 分析的 4 个 M10 extraction FN 只是“未产生 action”这一窄分类，
不能解释为所有其他错误都与抽取无关。

## 4. Ours 具体改善了什么？

总体 Recall 0.5362→0.6812，约 +14.5 个百分点；TP 37→47 / 69，coverage 0.6667→0.8905。
主要净 Recall 增益来自 Actor（TP 13→27），与较充分的下游法规信息一致，但不是单因素因果证明。
Missing F1 0.4554→0.4935、Actor F1 0.4262→0.5684，Order F1 同为 0.5000。
Missing Recall 实际从 0.6970 降至 0.5758；不可写成所有类型都改善。

## 5. 当前最大剩余瓶颈是什么？

主要证据指向 regulation-to-BPMN action semantic alignment；action-span fragmentation 与 temporal/action
endpoint 表示链也有限制。Ours Precision 仍为 0.4393。
主表 Order 仅 3 条 eligible requirements、8 个计分单元，coverage 0.2500，证据较少。
Bonus 的 Sun/Ours F1 0.4667/0.5474、Order F1 0.6667 使用 synthetic endpoint stubs，
仅作诊断，**不可替换 Table 3**。没有最终 unseen evaluation 或统计显著性证据。

## Paper-ready English

Table 3 reports pooled downstream compliance-checking performance for a locally reconstructed rule-based Sun baseline and our LLM-based regulatory information extraction approach under the same checking pipeline. On the constructed benchmark, our approach achieves precision, recall, and F1 of 0.4393, 0.6812, and 0.5341, compared with 0.3814, 0.5362, and 0.4458 for Sun. The F1 gain is 8.83 percentage points, or approximately 19.8% relative improvement. Recall shows the largest overall gain, with 47 rather than 37 of 69 positive cells detected. This gain is mainly associated with actor-related detection; it does not imply improved recall for every violation type.

These downstream scores should not be interpreted as element-level extraction performance. Regulatory actions must be extracted, represented and aligned with BPMN activity labels before actor associations, ordering relations and process structure can be checked. In the post-hoc analysis of frozen Missing signals, semantic mapping accounts for 50 of 70 false-positive method-case cells across the two methods. This supports action-to-activity alignment as a major remaining limitation, alongside action-span fragmentation and incomplete temporal endpoints. The benchmark has been used during development and analysis; the results do not constitute an independently held-out evaluation. The synthetic-endpoint bonus diagnostic is excluded from Table 3.

## 6. PPT 中文讲稿（约 30–40 秒）

“表三测的是最终合规检测，不是第二阶段抽取准确率。法规动作要先对齐 BPMN 短标签，
actor 和顺序判断还依赖前面的结果，所以错误会逐级传递。失败分析中，70 个 Missing 误报有 50 个与语义映射有关。
我们的 F1 从 44.58% 提高到 53.41%，Recall 从 53.62% 提高到 68.12%，主要增益来自 Actor 检测。
这说明抽取结果改善了当前基准上的下游检测；但该基准用于过开发，不能称为未见测试。”

讲稿配表即可，不把 bonus 数字放入主结果。
完整精度差值舍入为 Precision +0.0578、Recall +0.1449；表中四位小数相减得到 +0.0579/+0.1450，
二者仅舍入顺序不同。正文优先用约 +14.5 个百分点和 +8.83 个百分点。
若没有更强的正式 unseen evaluation，且导师接受当前设计，则沿用这组固定数值。

## Provenance

分支 `paper-final-repair`；生成时 HEAD / bonus source commit `6d22732d169abb17b03f0a9f1afb3bb5884dbf43`；
Table 3 freeze commit `292edb2d9b5b2960779ab3723c6b2e693079aa2a`。
来源：[canonical Table 3](stage3_table3_provisional_final_v1.json)、
[final convergence](stage3_final_convergence_report_v1.json)、
[Missing analysis](stage3_bonus_missing_analysis_v1.json)、
[bonus development](stage3_bonus_development_report_v1.json)。
完整源路径、源提交及 SHA256 见 [closure JSON](stage3_experiment_closure_v1.json) 的 `git_provenance`。
这里的 HEAD 指写入前状态；收束提交和 push 结果见任务交付。
