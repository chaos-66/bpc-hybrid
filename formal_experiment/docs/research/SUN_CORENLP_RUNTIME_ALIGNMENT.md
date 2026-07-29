# S2.5 CoreNLP/Tregex/Tsurgeon 运行时与 live fixture 对齐

## 1. 当前结论

S2.5-A 和 S2.5-B 均已 verified，S2.5 整体 verified。项目已固定 Stanford
CoreNLP 4.5.10、六字段规则、抽取顺序、Java 8 兼容 bridge、synthetic live
fixtures、外部运行时身份和 fail-closed 机器门。

这个结论只证明独立重建的 phrase extractor 在 synthetic fixtures 上可重放，不是
Gold 评价，不是作者原始实现。本句记录的是 S2.5-B 当时的批次边界；2026-07-17 的
本地研究使用决定与 S2.4 运行已解除该历史阻塞，当前状态以主 Pipeline 和机器合同为准。

## 2. 外部软件身份

| 项目 | 已锁定证据 |
|---|---|
| CoreNLP | 4.5.10（2025-06-06），官方页 <https://stanfordnlp.github.io/CoreNLP/download.html> |
| 官方 ZIP | `stanford-corenlp-4.5.10.zip`，508,444,875 bytes，SHA-256 `76a04089069dad21176c02881f46e07c19ca148b71c8581de2b5b2e2855e042e` |
| ZIP 安全 | 63 entries，唯一顶层目录，0 unsafe entries |
| code JAR | 9,118,725 bytes，SHA-256 `f813ce4ed7319d79225f2a520d40733075c6b3500dd0b81ee069229e461aab43` |
| models JAR | 474,409,531 bytes，SHA-256 `a5da9f6feb35a0fd2ea2cbe8909bede3952965b238a68c833ae3e031ed9026a0` |
| Java live 环境 | OpenJDK 21.0.11；bridge 用 `javac --release 8` 编译 |
| CoreNLP 许可 | GNU GPL v3 or later；项目不再分发第三方二进制 |
| Tregex/Tsurgeon 许可 | GNU GPL v2 or later；项目不再分发第三方二进制 |

发行包和解包目录位于项目外的 `D:\environment\`，没有进入
`formal_experiment/`、Git 或公开产物。复现时必须通过显式 `--runtime-home` 或
`CORENLP_HOME` 提供运行时，并先核对上述 hash。

## 3. 六字段顺序与真实 surgery

`resources/corenlp/sun_phrase_patterns_v1.json` 固定顺序：

1. modality；
2. condition；
3. constraint；
4. exception；
5. action；
6. actor。

modality、condition、constraint、exception 命名节点依次通过 Tsurgeon `prune`
从工作树移除；action 随后从清理后的主句 VP 提取；actor 最后提取。规则继续绑定
S2.3 marker payload
`8c3a27b2aa62025ff266b4cb19a1c89984e967539188ccf96820836c2eef7b91`。

这些规则是项目的独立重建，不冒充 Sun 作者原始规则。任何后续规则修改都必须升版、
重跑 live fixtures 并重新锁定 manifest，禁止看 test/Gold 后临时改规则。

## 4. S2.5-B live smoke

`scripts/verify_corenlp_s25b.py` 在不联网的情况下完成：

- 校验外部 ZIP、code JAR 和 models JAR；
- 用真实 CoreNLP 跑 `tokenize,ssplit,pos,lemma,parse,depparse`；
- 用 Java 8 bridge 编译 12 条 Tregex pattern 和 Tsurgeon operation；
- 按固定顺序处理 2 条 synthetic 句子；
- 对照 token index、命名节点文本和 surgery 状态。

锁定结果：2 sentences、28 tokens、28 dependencies、12 patterns、11 field matches、
7 Tsurgeon surgeries，全部与 `s25b_live_expected.json` 一致。完整证据位于
`resources/corenlp/s25b_runtime_verification_manifest.json`。

## 5. 门禁与边界

机器状态现为：

- `s2_5_contract_verified=true`；
- `s2_5_runtime_ready=true`；
- `s2_5_verified=true`。

同时保持：

- 当次历史状态为 S2.4=`blocked_license_unknown_training_evaluation_forbidden`；
- 当次尚未训练 BERT-TextCNN，未运行 development/test 评价；
- 未读取或修改 formal Gold，未改 Layer E；
- 未调用真实 LLM/API；
- live verifier 本身不联网；只有 Agent 按用户继续 Pipeline 的指令从固定 Stanford
  官方 URL 下载过第三方发行包；
- 当次未进入 S2.6；该状态已由 2026-07-17 的 S2.4 verified 运行替代。
