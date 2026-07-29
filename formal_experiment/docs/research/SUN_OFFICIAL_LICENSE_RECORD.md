# Sun modality 数据许可证据记录

**任务**：S2.4-L（S2.4 派发前许可门禁单独收口）  
**检查时间**：2026-07-16T12:17:35Z  
**结论**：许可证据复核已完成；未发现明确数据集许可证或训练/评价授权，S2.4 继续
`blocked_license_unknown_training_evaluation_forbidden`。

## 1. 本记录回答什么

本记录只判断 `Decision_Logic_data.zip` / `EStG_sent_vec.csv` 是否已有足以解锁
BERT-TextCNN 本地训练和评价的权威许可。它不评价模型、不运行训练、不修改 Gold，
也不把“公开可下载”解释成“可自由复用”。机器可读证据位于
`configs/datasets/sun_modality_license_evidence.json`。

## 2. 权威证据

| 来源 | 2026-07-16 实际观察 | 许可含义 |
|---|---|---|
| Archive.org 官方元数据 `https://archive.org/metadata/input-2` | item=`input-2`；文件名、大小和 SHA-1 与本地 ZIP 一致；`licenseurl=null`，`rights=null` | 能确认来源身份，不能确认训练、评价或再分发许可 |
| Springer 正式论文页 `https://link.springer.com/article/10.1007/s11227-023-05626-0` | 数据可向通讯作者合理请求，notes 链接 Archive.org | 是数据可用性声明，不是数据集许可证 |
| 本地官方 ZIP | 仅有 `EStG_sent_vec.csv`、`EStG_raw.txt`、`estg.html` | 包内没有 LICENSE/RIGHTS 成员 |

Archive.org 的 `opensource_media` / `community` collection 标签只是条目分类；本项目
没有把 collection 名称当作许可证。论文页面自身的出版许可即使存在，也不能在没有
明确文字时自动外推到单独下载的数据包。

## 3. 门禁决定

- `rights_status=unknown_pending_confirmation`；
- `training_authorized=false`；
- `evaluation_authorized=false`；
- `formal_use_allowed=false`；
- `publication_allowed=false`；
- `redistribution_allowed=false`。

因此，S2.4-L 的“证据复核”可以 verified，但 S2.4 本体仍 blocked。S2.5 的完成不
改变这个判断，S2.6 也不能启动。

## 4. 怎样才能重新打开 S2.4

至少取得以下两类证据之一：

1. 明确适用于该数据包、且允许预期本地模型训练和评价的许可证全文；或
2. 作者/权利人书面许可，明确覆盖本项目拟进行的本地训练和评价。

如果将来需要公开原始或派生数据，还必须另有明确的发布/再分发授权；训练许可不能
自动推导出再分发许可。新证据必须保存来源、日期、适用资产、许可原文或不可变摘要、
hash 和适用范围，并重新更新合同、负测试、完整性检查与追加式实验日志。

## 5. 可发送的确认请求（本批次未发送）

可向论文通讯作者或数据权利人询问：该 Archive.org 数据包是否允许非商业学术研究中
的本地模型训练、开发集选择和测试集评价；能否发表不可逆聚合指标；能否发布训练后
权重；能否再分发原始或派生数据；适用的具体许可证名称和版本是什么。收到回复前，
当前 fail-closed 状态保持不变。

## 6. 本批次边界

没有训练、评价、生成预测、修改 Gold、进入 S2.6、调用真实 LLM/API，或把官方数据
上传/再分发。联网动作只有对 Archive.org 与 Springer 权威页面的只读许可核对。
