# Sun 最终版、引用链与官方数据审计

**审计日期**：2026-07-11  
**结论状态**：已找到官方补充数据；Stage 2 完整源码与 150 句 phrase Gold 仍缺失；
正式路线已重新打开，不可继续旧人工审核。

## 1. 最关键结论

1. 本地 `references/papers/Sun_2024_Design_time_BPC.pdf` 是较早作者稿。Springer
   最终版标题为 *Design-time business process compliance assessment based on
   multi-granularity semantic information*，DOI 为
   `10.1007/s11227-023-05626-0`。最终版图 3 明确写作 BERT-TextCNN；旧稿图 5
   仅画 BERT + softmax。正式复现必须以最终版为准。
2. 最终版 Springer 页面公开了 Archive.org 数据脚注：
   `https://archive.org/details/input-2`。之前“Sun 数据全部未公开”的判断错误。
3. 官方 `Decision_Logic_data.zip` 含 `EStG_raw.txt`、`EStG_sent_vec.csv`、
   `estg.html`。2026-07-15 S2.1-C 完整流式扫描确认 CSV 为无 header 的 10 列：
   第 4–7 列是 positional one-hot modality，第 9 列是可变长度 300 维词向量序列；
   早期“第 1 列为 0–3 code / 第 9 列为 768 维 BERT 向量”假设均已被真实字节推翻。
   真实数据还含 1 个 normalized-text label conflict，development import 因而 fail closed。
4. 官方 `input 2.zip` 含 57 个有效 Stage 3 输入文件。逐文件 SHA-256 比较表明，
   57/57 与导师包及 Winter 本地副本完全一致。
5. 导师包 `model_check` 与 Winter 副本的 112 个非缓存文件完全一致；唯一额外的
   11 个文件是 `__pycache__/*.pyc`。它不是 Sun 的 BERT-TextCNN 或
   CoreNLP/Tregex/Tsurgeon Stage 2 实现。
6. Sun 的原始 150 句 ID、443 个 phrase spans、完整 marker lexicon、训练后模型
   和完整 Stage 2 源码仍未在官方包中出现。因此只能做 final-paper-faithful
   reconstruction，不能声称 exact/original reproduction。

## 2. 论文与引用链

### Sun 最终版

- Springer：`https://link.springer.com/article/10.1007/s11227-023-05626-0`
- 最终版页面注明数据可向通讯作者索取，同时给出 Archive.org 数据包和原型网站
  `https://bpcchecking.emoryhuang.cn/`。
- 原型网站在本次审计时 HTTPS 连接失败、HTTP 返回 502；不能视为可用源码。

### Michel et al. (2022)

- 论文：*Identification of Decision Rules from Legislative Documents Using Machine
  Learning and Natural Language Processing*。
- 公开记录：`https://research.wu.ac.at/de/publications/identification-of-decision-rules-from-legislative-documents-using-4/`
- 数据来自 EStG 1988，经人工句子修复和人工四类标注；报告总计 2,833 句：
  definition 1,190、obligation 1,274、permission 265、prohibition 104。
- 该论文自身没有给出数据下载链接，但 Sun 的 Archive.org 包补上了原文和带标签/
  向量 CSV。

### Winter et al. (2020)

- 论文：`https://eprints.cs.univie.ac.at/6508/1/compliance_assessment_paper_ER2020.pdf`
- Winter 使用 spaCy、signal words、clause splitting、fitness/cost、`gamma`/`delta`，
  并公开 GDPR prototype/input；智能电表 12 模型属于 proprietary case study。
- Sun 的思想和 Stage 3 对比继承了 Winter，但 Sun Stage 2 增加句子级深度分类和
  六概念短语解析。Winter 源码不能冒充 Sun Stage 2。

### Agostinelli et al. (2019)

提供 7 个 GDPR BPMN privacy patterns。官方 Sun `input 2.zip`、导师包与 Winter
prototype 都使用同一组文件。Sun 检查实验报告四个模型；当前作者稿没有把
BPMN1–4 映射到七个文件名。

### Böhmer / 智能电表引用链

Sun/Winter matching 实验使用 12 个智能电表 process-model/paragraph pairs。
Winter 明确称该案例数据为 proprietary；公开引用和失效的法规 PDF 链接不能恢复
12 个专家验证 BPMN。该数据不可用于 exact 复现，本研究不应伪造能源 BPMN。

## 3. 哈希与文件证据

| 资产 | 官方 SHA-1 | 本次额外核对 |
|---|---|---|
| `Decision_Logic_data.zip` | `0346f84a246b7049d5aef58bcb33471435bee106` | `EStG_raw.txt` SHA-256 `185385186533FCDB8156D094782E3A3976C85460312EE9D48B424F404817660F` |
| `input 2.zip` | `a1a0ac8d57eb45698728722628a4c838c592c5bf` | ZIP SHA-256 `A4E12BDBF1631F201A06BD6DDAA30C6423AA33F3BE99338ABFA6E39CFA786FE3` |

`input 2.zip` 去除 `.DS_Store` 与 `__MACOSX` 后为 57 个有效文件；相对路径和
SHA-256 在官方解包、导师包、Winter 副本三者之间差异数为 0。

| 项目 | 导师包 | Winter 副本 | 差异 |
|---|---:|---:|---:|
| `model_check` 文件总数 | 123 | 112 | 11 |
| 非缓存有效文件 | 112 | 112 | 0 |
| 导师包独有 | 11 | 0 | 全部为 `__pycache__/*.pyc` |

## 4. 正确的 Stage 2 实验定义

正式 baseline 不是“关键词 rule-only”，而是最终发表版完整 Stage 2：句子级
BERT-TextCNN 四分类；CoreNLP preprocessing；Tregex/Tsurgeon + domain markers
六概念抽取；按论文顺序构造 rule record。

Hybrid 必须先运行同一个完整 baseline；trigger 只能基于推理时可见信息，例如
schema invalid、parser failure、必需字段缺失、低置信度/小 margin、规则冲突。
不得用 Gold、全数据分布或测试结果事后决定是否调用 LLM。

Direct LLM 不接收 baseline 预测，不运行 Sun 规则，不读 Gold；输入同一文本并
输出同一 schema。prompt、model、temperature、重试、预算和 invalid outputs
全部记录。

## 5. 数据使用决定

1. modality：优先官方 `EStG_sent_vec.csv`；schema 与标签顺序已完成全量审计，
   但必须先以权威或人工决定解决唯一 normalized-text label conflict，才能生成
   project-reconstructed deterministic split。不得称为 Sun original split。
2. phrase Gold：先请导师再次向作者索取原 150 ID + spans + marker lexicon。
3. 若作者仍不给：从官方 `EStG_raw.txt` 按论文标准构造新的 150 句，人工双标；
   明确称 reconstructed phrase benchmark，不追求复刻论文绝对数值。
4. Stage 3：复用已核实的官方/Winter 57 个输入文件；四模型 subset 未确认前，
   七模型结果只能作为扩展实验单独报告。

## 6. 仍需的外部材料

- 最终发表版 PDF 全文（本地只有较早稿；Springer 当前为订阅内容）；
- 作者原 150 句 ID 与 phrase-level Gold；
- 最终版 BERT-TextCNN 超参数、训练 seed/split 或训练后权重；
- 完整 Tregex/Tsurgeon 规则文件和 marker lexicon；
- 若要复现 matching AP/MAP：12 个 proprietary 智能电表 pairs。

## 7. 下一步顺序

1. 由用户/导师通过机构访问获取最终版 PDF，并在用户批准后放入独立只读 provenance。
2. 经用户批准，把两个官方 Archive.org 包作为独立 provenance 资产引入，保留
   官方哈希，不覆盖导师/Winter 目录。
3. 审计 `EStG_sent_vec.csv` schema 与许可，重建句子级 train/test protocol。
4. 再次向作者请求 150 句 phrase Gold；若失败，书面锁定 reconstruction 方案。
5. 实现并测试完整 Sun Stage 2 baseline。
6. 预注册 fallback trigger 与 direct-LLM prompt；之后才申请真实 LLM 调用授权。
7. 锁定 Stage 3 subset、阈值与 violation Gold，再进入正式运行。

---

## 8. 2026-09-17 来源缺口复核：Sun 最终版、Winter 三类范围、bert-legal-cased

**本轮性质**：只读来源与文件内容核对，技术证据整理；0 LLM/API、0 训练/推理、0 比较重跑。
**网络条件**：2026-09-17 在本环境重新取回 `https://link.springer.com/article/10.1007/s11227-023-05626-0` 失败（`Invoke-WebRequest`：基础连接已经关闭；`curl`：exit 35 SSL connect error）。因此，本轮凡未在本机原文/官方补充包中直接看到的 final 正文字段，均不能登记为本轮原文已复核。

### 8.1 事实总表

| 来源/方法版本 | 原生任务与输出 | 项目已完成的对应比较 | 本轮新核实的证据 | 精确页码/表号/官方链接 | 剩余缺口及原因 |
|---|---|---|---|---|---|
| Sun et al. (2024) final published version | 句子级四类 modality 分类；六要素抽取；规则—流程匹配；三类违规检测 | SEP-C2 的 9 个 Sun 前人分类配置；Winter 属于下游违规检测比较 | final 正文未在本轮取得；项目记录 2026-09-15 称 Section 4.2.1 / Fig. 3 为 BERT-TextCNN；本轮网络失败，无法重取 final 正文 | DOI：`https://link.springer.com/article/10.1007/s11227-023-05626-0`；项目记录引文见 `configs/sep_c2_sun_predecessors_v1/method_roster_v1.json` | final 表号、页码、与本地作者稿数字是否一致本轮未复核；不能把本地作者稿 Table 6/7 称为 final 已核 |
| Sun 本地作者稿 local author manuscript | modality 分类；六要素抽取；匹配；违规检测 | 当前 SEP-C2 分类 roster 的实际文字来源 | 直接读取本地 PDF：`references/papers/Sun_2024_Design_time_BPC.pdf`，SHA-256 `08a26b7d4e6716eb2e07fce4f2a96420562a9eab6ecb12d8fb8ee351b297fcb2`；提取文本 `references/papers/extracted/sun_2024_full_text.txt`，SHA-256 `947140c3b7e350b4d35b9b6848c275dd265dc060f517da7a1dcfce43a55eec47` | PDF p.9-10 Fig. 5：BERT + softmax；p.16 Table 6：6 个 BERT 变体；p.17 Table 7：CF_KW/CF_RNN/CF_CNN + 本方法；p.17-18 Table 8：六要素抽取自评；p.19 Table 9：匹配 AP/MAP 自评；p.20-21 Tables 10-12：违规检测与 Winter 比较 | 本地稿不是 final；其 Table 6/7 不能替代 final 表号/数字复核；架构与项目记录的 final Fig. 3 不同 |
| Winter et al. (2020) | 段落—流程模型成对匹配；输出 fitness 与 cost；三类违规检测；不做六要素抽取、不做 modality 分类 | SEP-C2 Stage 2B：Winter native clause-region 适配到 EStG-150；S3.4：Winter Stage 3 development wrapper | 直接读取本地 PDF：`archive/historical_project/data/formal/raw/winter_2020_keyword_baseline/winter_2020_compliance_assessment.pdf`，SHA-256 `3125a9a297aa53c705e7a2fb906bb730f6ac4c17856a469360c0204ac95f3b42` | 公开 eprint：`https://eprints.cs.univie.ac.at/6508/1/compliance_assessment_paper_ER2020.pdf`；三类违规 p.4；cost 三分量 p.7-9；范围与 future work p.2/p.12/p.13 | 作者未明确解释为何恰好选三类；但明确把 optional、prohibitive、data/time 列为 future work。原始 12 个智能电表 BPMN 为 proprietary，原表数字不能完整复现 |
| `bert-legal-cased` | Sun Table 6 的 cased legal-domain pre-trained encoder 配置 | v2 分类表第 11 行；target consistency diagnosis 记为 source-pending，不进入 10 方法性能分母（v2 artifact 仍保留 legacy machine status code `blocked_exact_public_checkpoint_unavailable`） | Sun 本地稿只给名称、预训练数据 Documents of EU legislation、12 层/768/110M，无引用、URL、版本、tokenizer card；官方 Archive.org supplement 只有数据；本地官方模型缓存有 `nlpaueb/legal-bert-base-uncased`，没有 cased legal-BERT | Sun 本地稿 p.15-16 Table 5/6；Archive：`https://archive.org/details/input-2`；`Decision_Logic_data.zip`；本地 uncased 缓存 revision `15b570cbf88259610b082a167dacc190124f60f6` | 名称歧义，不能对应唯一模型；在已核查官方来源中未定位到精确公开 checkpoint。本轮网络失败，不能重复在线检索。不得写成模型不存在或公开权重绝对不存在 |

### 8.2 Sun final 与本地作者稿：方法、表号、任务

- **方法不一致（有本地/项目记录证据）**：本地作者稿 p.9-10 的 Fig. 5 明确是 `BERT -> softmax`；本地 PDF 中检索不到 `TextCNN`。项目记录 2026-09-15 则记 final Section 4.2.1 / Fig. 3 为 BERT-TextCNN，并给出短引文：For each encoding layer, the vector of its first token (i.e., [CLS]) is extracted, and these vectors are concatenated together as the input of the TextCNN layer.
- **本轮可核的本地作者稿表号**：Table 5（p.16）列 6 个预训练模型的层数/隐层/参数量；Table 6（p.16）列 6 个 BERT 变体的 P/R/F1；Table 7（p.17）列 `CF_KW`、`CF_RNN`（正文说明为 bidirectional LSTM）、`CF_CNN` 与本方法；Table 8（p.18）仅六要素抽取自评；Table 9（p.19）仅本方法匹配 AP/MAP；Tables 10-12（p.20-21）为违规检测与 Winter 比较。
- **final 表号与数字**：本轮未取得 final 正文；现有项目文字中的 final Table 6/7 只能登记为项目记录，不能作为本轮原文复核结论。最终版是否仍用相同表号、数字是否完全一致，均为 `TODO-SOURCE`。晚间写作若引用 final 表号/数字，应先重新取得 final 正文并逐表核对。
- **任务层级**：本地作者稿及 final 项目记录都把 Winter 放在 Section 5.3.2 / Table 12 的**下游违规检测**比较，而不是六要素抽取比较。Winter 不能移植成原生六字段抽取比较。
- **六要素抽取**：本地作者稿 Section 5.2 / Table 8 只有作者自己的规则抽取自评，没有外部六要素抽取基线；本轮未发现 final 正文中有不同外部抽取对照的证据。
- **匹配**：本地作者稿 Section 5.3.1 / Table 9 只有本方法 AP/MAP 随阈值变化，没有外部方法比较；本轮未发现 final 正文中有不同匹配 baseline 的证据。
- **违规检测**：本地作者稿 Section 5.3.2 / Tables 10-12。Table 12 中 Winter 0.58/0.89/0.70，本方法 0.77/0.83/0.80（P/R/F1），这是违规检测层比较。

### 8.3 Winter 三类违规的原文依据

- **原生任务/输出**：输入是流程模型仓库与法规段落；输出是段落—模型 pair 的 fitness 与 cost。fitness 是段落与模型相关性的平均相似度（Eq. 1）；cost 是三个违规 cost 分量的加权和（Eq. 2）。Winter 不输出六要素规则记录，也不做四类 modality 分类。
- **三类违规 V1-V3**：p.4 明确列出 `(V1)` 义务活动缺失、`(V2)` 活动顺序错误、`(V3)` 资源执行者错误。它们是 control-flow/resource 视角的三种违规。
- **三个 cost 分量**：p.7-9 的 `cost(P,M) = wo*costo + wso*costso + wr*costr`。`costo` 对应 V1，`costso` 对应 V2，`costr` 对应 V3。**三类违规与三个 cost 分量是同一组划分**，不是另外的三类 modality。
- **modality 区分**：Winter 只用 `must/should/shall/has to` 等 signal words 识别义务句，再做 clause splitting；原文没有 definition/obligation/prohibition/permission 四类分类器，也没有三类 modality 这一说法。
- **范围选择的作者表述**（短引文）：
  - p.2：Our work particularly targets the detection of violations in terms of mandatory activities that are missing in a process, as well as activities that are performed in the wrong order. Furthermore, we detect resource-related violations...
  - p.12：By now, our approach focuses on mandatory tasks but there might be optional constraints within a paragraph, e.g., indicated by can. As future work we plan to adapt the cost score such that compliance violations caused by optional constraints are considered as well.
  - p.13：The approach can be expanded to incorporate additional types of compliance violations, such as those stemming from prohibitive rather than obligatory statements in regulatory documents, as well as those covering the data and time perspectives of processes.
- **本轮结论**：已确认 Winter 的研究范围就是三类 control-flow/resource 违规。**未找到作者明确解释为何恰好选择这三类**。作者明确承认 optional constraints、prohibitive statements、data/time perspectives 尚未覆盖，并列为 future work；因此不能写成其他类型无法处理，也不能泛称所有前人都只研究三类。
- **项目已完成的对应该比较**：
  - `outputs/reports/sep_c2_stage2b_predecessor_baseline_v1.md`：Winter native clause-region baseline 适配到 EStG-150；该子任务不是 Winter 原生 match/cost，也不是 Sun Table 12 的直接可比结果。
  - `outputs/reports/s34_winter_stage3_development_v1.manifest.json` 与 `outputs/evidence/s34_winter_stage3_development_v3_clean/evaluation.json`：GDPR-7 固定 panel 上的 development wrapper；MAP 0.6429、binary F1 0.6111、violation macro F1 0.373；这是 DEV_ONLY，且披露了原型 reachability bug 修复，不是 Winter 原论文数字。
  - 原 12 个智能电表 BPMN 为 proprietary，不能恢复；因此不能声称已复现 Winter 原 Table 1/2 或原始 match/cost 数字。

### 8.4 `bert-legal-cased` 精确来源核对

- **Sun 本地作者稿给了什么**：p.15 提到 domain pre-trained models bert-legal-cased 与 bert-legal-uncased；p.16 Table 5 给 `bert-legal-cased` 的预训练数据为 Documents of EU legislation，12 layers、768 hidden、110M parameters；Table 6 给 P/R/F1 91.3/93.3/88.5。**没有引用、模型 repo、revision、license、tokenizer card、checkpoint URL 或语言说明**。
- **Sun 参考文献**：本地作者稿引用表只出现 `[27] Devlin et al., BERT`；没有 Chalkidis/Legal-BERT、nlpaueb 或精确 legal checkpoint 的引用。
- **官方补充材料**：`https://archive.org/details/input-2` / `Decision_Logic_data.zip`。本地 zip 路径 `formal_experiment/data/development/sun_modality/raw/Decision_Logic_data.zip`，SHA-256 `ada231f092927813ba9f1cd32a44a3d30d96b57fc463d042dfd76c652b6d58f2`。2026-09-17 重新列成员仅 3 项：`EStG_sent_vec.csv`、`EStG_raw.txt`、`estg.html`；没有 `config.json`、tokenizer、`pytorch_model.bin`、`model.safetensors`、checkpoint 或训练代码。
- **公开模型发布者/本地官方缓存**：本地官方缓存只有 `nlpaueb/legal-bert-base-uncased`（revision `15b570cbf88259610b082a167dacc190124f60f6`，`tokenizer_config.json` 的 `do_lower_case=true`）。本地没有名为 `legal-bert-base-cased` 或 `bert-legal-cased` 的官方 checkpoint。
- **项目记录的在线检查**：项目记录称 `https://huggingface.co/nlpaueb/legal-bert-base-cased` 返回 404，Hugging Face 搜索、GitHub 仓库 title-match 和 Archive.org 都未定位到精确 cased EU-legislation legal-BERT。本轮无法重新在线核验（SSL connect error），只能登记为项目记录。
- **结论分类**：不是第 1 类找到精确公开 checkpoint；也不是第 4 类原项目名称解读已被证明错误。当前证据最接近 **第 2 类：名称存在歧义，尚不能对应唯一模型** 加 **第 3 类：论文提到该配置，但在已核查官方来源中未找到公开权重/版本**。该行继续为 source-pending；不能用 `bert-base-cased` 或 `nlpaueb/legal-bert-base-uncased` 替代。不得写成模型不存在或公开权重绝对不存在。

### 8.5 本轮修正与晚间写作待改位置

本轮已直接修正：
- `configs/sep_c2_sun_predecessors_v1/method_roster_v1.json`：`bert_legal_cased` 的 source wording、final-version caveat。
- `outputs/reports/sep_c2_sun_predecessors_comparison_v2.md/.json` 与 `outputs/evidence/sep_c2_sun_predecessors_v1/comparison_v2/{report.json,manifest.json}`：把 not published / no such model 绝对表述改为在已核查官方来源中未定位。
- `scripts/build_sep_c2_sun_predecessor_comparison_v2.py` 与 `scripts/build_sep_c2_target_consistency_diagnosis_v1.py`：同步修正生成文本，避免下次重生成时回退。
- `docs/MASTER_PIPELINE.md`、`docs/PROJECT_AUDIT.md`：把公开精确 checkpoint 不存在/仍阻塞等绝对状态改为名称歧义、已核查来源未定位、source-pending。
- `outputs/reports/sep_c2_target_consistency_diagnosis_v1.json` 及 evidence 副本：source-pending reason 改为未在已核查官方来源中定位。

晚间 V4 Pro 写作需注意的位置：
- `paper/THESIS_DRAFT.md` 第 135、140-141、735 行：把 `bert-legal-cased` 的精确公开权重不存在改为名称歧义、已核查公开来源未定位到精确 checkpoint；source-pending，不替代。
- `paper/THESIS_DRAFT.md` 第 153、162、172 行：Winter 原方法描述应写三类 control-flow/resource 违规 + 三个 cost 分量；无 modality 分类器；future work 明确提到 optional/prohibitive/data/time，不得写成其他类型无法处理。
- `paper/CLAIM_EVIDENCE_MATRIX.md` C44/C51：把 final 表号/数字与 final 正文复核状态分开；C51 已有 source-pending 结论可复用。
- `configs/sep_c2_sun_predecessors_v1/bert_full_v1/*.json` 中的 `sun_source` 仍写 final article Table 6/7。若晚间沿用这些配置描述 final 表号，应先重新取得 final 正文；否则改写为 local author manuscript Table 6/7 + project-record final Fig. 3 architecture。
