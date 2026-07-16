# Sun 2024 / Winter 2020 代码身份审计（v2）

## 结论

导师说明 `references/合规性检查模型代码/` 由 Sun 论文作者提供；这是包的来源。
其中 `model_check/` 的文件内容是 Winter et al. (2020) prototype 的直接副本，
不是 Sun 最终版 Stage 2 源码。来源与内容必须同时保留，不能用其中一个否定另一个。

## 哈希证据

- 导师包：123 个文件；Winter 本地副本：112 个文件；
- 112 个相对路径与 SHA-256 全部相同；
- 导师包额外 11 个文件全部为 `__pycache__/*.pyc`；
- Sun 官方 `input 2.zip` 去掉 macOS metadata 后有 57 个有效输入文件；
- 官方、导师包、Winter 三者的 57 个输入文件路径与 SHA-256 差异为 0。

## 方法证据

包中有 spaCy、`Pair` fitness/cost、7 个 GDPR BPMN、Articles 5–50、
`gamma`/`delta`；没有最终 Sun Stage 2 所需的 BERT-TextCNN、CoreNLP、
Tregex/Tsurgeon Java pipeline、六概念完整实现或训练模型。

## 使用规则

- 该目录记录为 Sun-author-provided compliance-checking package，只作只读
  provenance、Stage 3 继承资产与 Winter 对照；
- 不得 import 到活动实现，不得写成 Sun original/exact；
- 不得写成“导师提供了错误代码”，也不得据此推断作者打包意图；
- `model_check` 的逐字节同一性只证明该子树内容来自/等同 Winter 原型，不证明
  Sun 与 Winter 的完整论文方法相同；
- Sun 官方输入可在用户批准后作为独立 provenance 引入，但不得覆盖导师/Winter 目录；
- 当前正式 baseline 仍需独立重建。
