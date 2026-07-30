# S2.3 public marker lexicon 重建记录

**任务**：Pipeline S2.3  
**状态**：verified development resource  
**完成日期**：2026-07-16  
**正式名称**：`public_marker_lexicon_en_v1`  
**边界**：不是 Sun original marker lexicon，不是完整 Sleimi/LexNLP 词表，不代表
S2.4/S2.5 已启动，也不解锁训练、评价、formal Gold 或公开再分发。

## 1. 本轮实际固定的内容

本轮没有联网重新下载上游文件，而是把
`SUN_REFERENCE_SNOWBALL_AND_MARKER_AUDIT.md` 在 2026-07-12 已核验并明确转录的
公开 marker 例项冻结为可重建的本地来源快照。来源、规范化、合并、排序、语言和
扩展规则统一写入：

`resources/lexicon/public_marker_sources_en_v1.json`

来源快照 SHA-256：
`e40c85cf572c68278d8fa2db00a57f193c0c9352aee889096731b6e87e31e369`。

来源层分为：

| 来源 ID | 内容 | 本轮可确认 | 本轮不声称 |
|---|---|---|---|
| `paper_examples_local_audit_2026_07_12` | Sun/Sleimi 公开论文例项 | modality、condition、exception、actor 的显式例项 | 不把聚合转录拆成未经复核的逐论文精确归属；不称完整论文词表 |
| `lexnlp_conditions_local_audit_2026_07_12` | LexNLP condition 文档列表 | 本地审计已逐项转录的 20 行，和论文例项去重合并 | `latest` 上游 alias 未固定到 commit；本轮没有联网重核 |
| `lexnlp_constraints_local_audit_2026_07_12` | LexNLP constraint 文档摘录 | 本地审计明确枚举的 19 项 | 文档曾报告约 40 个模式，未转录部分不猜测、不补齐 |

上游 license 本轮没有联网重核，因此所有生成资源保持
`development_only`、`redistribution_allowed=false`、`formal_use_allowed=false`。
这不处理 Sun modality 许可与 S2.4 ready 的现有矛盾；该问题按用户要求留到 S2.4
单独派发前收口。

## 2. 生成规则

1. 语言固定为英语，只适用于未来经人工批准的英文 phrase-level working text；
   不应用于 2,831 行德文 modality 数据。
2. marker 规范化固定为 NFKC、首尾去空白、内部空白折叠、Unicode casefold。
3. 同一 field + modality class + normalized surface 的重复项合并，并保留全部
   `source_ids`；不同 field 的同形项未来仍分别保留，由句法和抽取顺序消歧。
4. 输出按 token 数降序、字符数降序、surface 和 modality class 排序；生成结果无
   运行时间等非确定字段。
5. action 不建 marker 词表，固定为 `syntax_only_no_action_marker_lexicon`。
6. 没有明确固定的 public definition marker 来源，因此 v1 的 definition marker
   数为 0；definition 只保留给后续 sentence classifier，不从旧启发式词表猜词。
7. actor 的 Wiktionary/Wiktextract dump 扩展未包含：本轮没有固定 dump、hash 和
   license。v1 只保留公开论文显式 actor examples。

## 3. 版本化产物与 hash

| 类别 | 数量 | 文件 SHA-256 |
|---|---:|---|
| modality | 7 | `f9b8543072154173e03e39ffad2c93461d27ac6d2bd6df04eeb24db5417b3e2a` |
| condition | 25 | `6e64811b94913d6251730dfcd70c723f69f8826da274e09c22a32f6662c8416a` |
| constraint | 19 | `320fa49eb3ad6d05e29e4ad4e47632705178c5c7c3002f1cd999d08dcb217781` |
| exception | 5 | `becfaa2c9358aea23cbaa627abac643300ce60a630267a6dc93324290ebbf2dd` |
| actor | 8 | `69a3f8ea6d7694b054db4700df8066cd2c4060a1c592b7c0e05463b129a466b8` |

五类合并 payload SHA-256：
`8c3a27b2aa62025ff266b4cb19a1c89984e967539188ccf96820836c2eef7b91`。

manifest：`resources/lexicon/public_marker_lexicon_en_v1.manifest.json`；SHA-256：
`5b9bafb268469acb33c3779ad4e0d8ce6a9984c4cf900855aeeafc0f332e2bf7`。

`resources/lexicon/development_extensions_en_v1.json` 是空的锁定模板，entry count=0。
现有 `resources/sun_marker_lexicon.json` 仅保留给旧 development heuristic 兼容，
不是本 S2.3 产物。

## 4. dev-only 扩展策略

- v1 不包含任何 corpus-mined 或人工补充扩展；
- 只能在 train/dev 上形成候选，并需单独记录接受/拒绝决定；
- 禁止使用 test text、test labels、test predictions、formal Gold 或评价结果补词；
- 接受任何扩展都必须新建版本化 source snapshot 和 lexicon 文件，重建 hash、增加
  tests 并追加变更事件；不得覆盖 v1；
- test-time 动态加词永久禁止。

## 5. 离线重建与验证

```powershell
python formal_experiment/scripts/build_public_marker_lexicon.py --check
python formal_experiment/scripts/audit_project.py
```

生成脚本的 `--write` 只会创建缺失文件；若同版本路径已有不同字节则 fail closed，
要求新版本，不提供强制覆盖开关。机器门禁同时交叉验证来源 hash、生成字节、各类别
hash、manifest、空扩展表、机器合同和未进入 S2.4+ 的边界。

代码为后续 S2.5 提供显式 `MarkerLexicon.from_public_v1()` 入口，但 S2.3 没有把它
静默设为现有 heuristic 的默认资源，也没有运行 extractor、训练或评价。

## 6. 2026-07-30 v2 溯源复核与 v3 负候选

v1 的原机器门禁与历史状态不变。本轮针对后续活动 B0 参数
`public_marker_lexicon_en_v2` 重新回到一手来源逐条复核，结论是：

- Sun Table 4 仅明示 Actor/Condition/Constraint/Exception 的初始例项；完整扩展未公开；
- Sleimi Section 5.1/Table 5 没有 Constraint 行，不能支持 v2 声称的 19 个 Constraint
  项；v2 另有多组 Actor/Condition/Exception/Modality 项并非表中逐字条目；
- LexNLP 固定到 2.3.0、commit
  `330b4e113c9bced0cc06f2c864c5015bb5ed2199` 后，保留文档与代码常量交集；
  `equal to`、`less than`、`no later than`、`not equal to` 不得截断，文档示例中额外
  自定义的 `smallest among` 不进入候选；
- 按新严格来源规则，v2 有 106/161 个 surface 不受支持；全部 161 条至少缺一个
  逐 marker provenance 必需字段。完整分组见
  `PUBLIC_MARKER_LEXICON_V3_PROVENANCE_AUDIT.md`。

新建 v3 时禁止读取 EStG-150、Gold、预测、FP/FN、评价结果和 LLM 建议，不做未记录
派生。评测前冻结六类计数为 7/8/0/26/41/5，总计 87，当前 B0 绑定 Actor/Condition/
Constraint/Exception 共 80；combined payload SHA-256 为
`4c6b7737f6d11b6405e5b5375fa35f452a81920782a789507b7756d3fa881846`。

冻结后执行完整 150-record v2/v3 paired B0，唯一变量为四个运行时 marker 文件。
Condition P 从 0.699482 升到 0.762963，但六字段 12 项 P/R 中 8 项下降，故严格门禁
决定 `reject_candidate_keep_active_v2`。v3 与完整负结果永久保留，不替换活动 v2，
也不回写 Gold、规则、parser、分类器或 evaluator。详见
`PUBLIC_MARKER_LEXICON_V3_PAIRED_EVALUATION.md` 与 RWI-0037。
