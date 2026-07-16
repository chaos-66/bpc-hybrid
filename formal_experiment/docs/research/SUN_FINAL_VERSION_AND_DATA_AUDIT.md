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
