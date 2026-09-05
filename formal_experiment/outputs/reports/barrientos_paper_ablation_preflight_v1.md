# S2-BARR-4：按 Barrientos 原文准备的两条件消融

状态：离线准备完成；真实 API 调用 0；独立调用预算尚未授权；没有新性能数字。

## 原文实际怎么做

已直接检查 `references/papers/Barrientos_2026_Impact_analysis.pdf` 第8–11页。
第9页 §5.1 报告去掉允许模式限制后出现不存在的模式和不一致命名；§5.3 比较
流程图 PDF 与原始 BPMN XML，描述前者较少受到无关标识符干扰。第10–11页给出
36条主评价、五次独立运行与Table 5；这些不是独立消融数值表，未单独披露消融
的完整样本/重复次数。不能把本项目的十项消融说成原作者方案。

逐行检查随附提示与 notebook（仅作只读来源，未导入/运行其代码）得到：

| 对照 | 随附实现的精确变化 | 解释边界 |
|---|---|---|
| FULL / NO-PATTERNS | 删除44项 Allowed Compliance Patterns 和 Control-Flow Exclusivity Rule；剩余规则编号3/4/5改1/2/3；其余正文相同 | 是原 artifact 两提示对照，不能称为只删词表的单因素；无词表版仍保留“不得编造”及指向下方列表的文字 |
| PDF / XML | notebook cell6上传PDF，cell7把XML写入user text；同时修改MIGHT violate等语气及若干输出描述 | 原代码不完全隔离媒介因素；需保持其差异披露，不能伪称纯输入格式实验 |

原 `compliance_requirements_format.json` 的 `compliance_pattern` 仅为string，
没有44项enum。JSON结构合法与模式属于允许清单是两件事；新评价分别统计。
旧1140调用脚本中“paper says nothing about it”注释与原文不符，但它被历史hash
锁定，本轮没有修改；以本报告和研究来源页的复核为准。

## 本轮准备的实验

- 两条件：原始 FULL 与原始 NO-PATTERNS 提示，不把 Barrientos 输出硬转六字段。
- 同一已冻结36条版本化输入，原始ID/version/text信封，逐条调用。
- 每条件五次，共360次新调用；按sample/repeat成对交错；不复用较早的FULL结果。
- 五次重复沿用论文主评价，是本项目补足的实验计划，不声称论文单独披露了消融五次。
- 沿用本项目 DeepSeek-V4-Pro-0813：temperature=0、top_p=1、max_tokens=4096、
  非thinking、非stream、retry=0。原论文使用GPT-4.1；明确模型替换，非精确复现。
- 原始输入、回答、逐条案例仅在本地受限目录中保存。公开报告只含聚合及hash。
- 没有读改Gold来生成请求；没有运行Stage3；没有修改正式预测、既有结果或150条成员。

## 看什么变化

主表并列报告两条件的名单外模式比例、模式与维度错配比例、至少一个词汇错误的
记录比例、严格JSON合法率、原schema合法率、非空且模式合法的可用率。
动作级指标同时报告动作数量，记录级指标保留全部请求（含空输出和解析失败）；
零动作的错误比例为null，不能写成“0错误”。

另给同一参数对象对应不同pattern的数量（明确是自动proxy，并非人工判定同义）
及五次非空合法JSON精确一致比例（每条件36×C(5,2)=360对；不是论文distance≤2）。
模型输出的名单外名称不自动等同于语义错误；语义对错与代表性例子保留人工复核。
不将原生计数代理或本文六字段F1冒充这项实验的语义准确率。

## 预算和运行

| 项目 | 上限 |
|---|---:|
| API请求 | 360 |
| 输入tokens保守预算 | 1,699,050 |
| 输出tokens | 1,474,560 |
| USD费用硬上限 | 9.70 |
| 自动重试 | 0 |

按2026-09-05核验的官方peak价格（输入cache-miss $1.32/M、输出$3.96/M）加20%
费用余量计算。输入按请求UTF-8字节数+1024预留；使用量未知、超预算、模型异常时
停止。断线/不确定请求留在账本中，禁止自动重发。价格来源：
https://api-docs.deepseek.com/quick_start/pricing/

离线检查：

```powershell
python formal_experiment/scripts/run_barrientos_paper_ablation_v1.py --dry-run
```

真实执行（先取得下面这份独立授权；历史1140/450预算不适用）：

```powershell
python formal_experiment/scripts/run_barrientos_paper_ablation_v1.py --execute --authorization-file formal_experiment/configs/ablations/barrientos_paper_ablation_authorization_v1.json
```

授权文件必须逐项匹配预检JSON中的 `authorization_template`，包括合同SHA-256和
用户明确提供的原句；本轮未创建授权文件。密钥只从进程环境获取，绝不读取`.env`。
这里提供模板不构成用户已经授权：

> 我授权 S2-BARR-4 Barrientos 原始 FULL/NO-PATTERNS 消融：36条×2条件×5次，360次 deepseek-v4-pro API 调用，费用上限 USD 9.70，retry=0，允许发送该36条输入。

## PDF/XML项的准备边界

已定位原notebook完整两版代码及三套PDF/BPMN。该实验还需要两版自然语言要求、
两版形式化结果与同一delta；本地来源树没有可直接冻结使用的完整Step1/2运行输出。
当前DeepSeek文字调用入口不能冒充原GPT-4.1 PDF文件输入。后续需准备成对上游资产、
支持PDF的独立模型与文件上传预算，并按当前Stage3门禁推进。本轮没有调用文件API、
没有另建Gold、没有把当前确定性Stage3更换成LLM。

## 离线验证

22项focused测试通过，含完整360次假响应流程（只用合成输出，不接触真实API）、
未授权拒绝、账本篡改与in-doubt拒绝、失败分母、空输出不获得满分稳定性，以及
“不存在的模式也能通过原schema”的关键回归。上述假响应数值不是实验结果。
