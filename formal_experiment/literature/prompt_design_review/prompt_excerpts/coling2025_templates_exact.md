# Sun, Luo & Li (COLING 2025): exact templates from Appendix C

Source: J. Sun, Z. Luo, and Y. Li, "A Compliance Checking Framework Based on Retrieval Augmented Generation", COLING 2025, Appendix C, Figure 7 and Figure 8, printed p. 2614 (PDF page 12). PDF: https://aclanthology.org/2025.coling-main.178.pdf

Extraction method: PyMuPDF text extraction from `.tmp/lit/pdf/coling2025_178.pdf`; Chinese text layer was clean. The block below is the raw text of PDF page 12, which contains Figure 7 (agent extraction) and Figure 8 (deontic-word prediction). The page text also contains the tail of Figure 6, so the exact prompt portions are delimited by the figure captions.

Evidence level: Verified (publisher PDF text layer).

```text
2614
为了确保客户信息的安全性和保密性，我们实施数据最小化策略…这一策略要求企业在收集、处理、
存储和传输个人数据时，只收集实现特定目的所必需的最少量的个人数据。
(To ensure the security and confidentiality of customer information, we implemente the strategy of data 
minimization… This strategy requires companies to collect, process, store, and transmit only the minimum 
amount of personal data necessary to achieve specific purposes.)
𝑡1
𝑡2
𝑡3
𝑡4
𝑡5
…
𝑡𝑁−9
𝑡𝑁−8
𝑡𝑁−7
𝑡𝑁−6
𝑡𝑁−5
𝑡𝑁−4
𝑡𝑁−3
𝑡𝑁−2
𝑡𝑁−1
𝑡𝑁
0
1
2
3
4
…
8
9
10
11
12
13
14
15
16
17
Ԧ𝑒1
Ԧ𝑒2
Ԧ𝑒3
Ԧ𝑒4
Ԧ𝑒5
…
Ԧ𝑒𝑁−9
Ԧ𝑒𝑁−8
Ԧ𝑒𝑁−7
Ԧ𝑒𝑁−6
Ԧ𝑒𝑁−5
Ԧ𝑒𝑁−4
Ԧ𝑒𝑁−3
Ԧ𝑒𝑁−2
Ԧ𝑒𝑁−1
Ԧ𝑒𝑁
Transformer
Transformer
CRF
Tokens
Position embeddings
Token embeddings
Input
Transformer layers
ො𝑦1
ො𝑦2
ො𝑦3
ො𝑦4
ො𝑦5
…
ො𝑦𝑁_9
ො𝑦𝑁−8
ො𝑦𝑁−7
ො𝑦𝑁−6
ො𝑦𝑁−5
ො𝑦𝑁−4
ො𝑦𝑁−3
ො𝑦𝑁−2
ො𝑦𝑁−1
ො𝑦𝑁
Begin of a term
End of a term
Begin of the interpretation 
End of the interpretation
output
…
BigBird
Figure 6: Structure of the jointly extraction model for terms and explanations.
请仔细阅读附件中的监管文件，并从中识别出所有受道义约束的主体。这些主体可能包括但不限于组织、公司、政府部门、非营利组织以
及个人等。注意寻找文档中使用的词汇，如“必须遵守”、“有义务”、“应当”等，这些通常指示了某种形式的约束或责任。请将识别
出的主体及其相关的道义约束以清晰的列表形式返回。准确性和完整性非常重要，请确保不遗漏任何相关的信息。
例如，如果文档中有句子“公司必须保护客户的个人信息”，那么“公司”就是一个受约束的主体，其道义约束是“保护客户的个人信
息”。
[Regulatory document attachment]
请仔细阅读附件中的监管文件，并从中识别出所有受道义约束的主体。这些主体可能包括但不限于组织、公司、政府部门、非营利组织以
及个人等。注意寻找文档中使用的词汇，如“必须遵守”、“有义务”、“应当”等，这些通常指示了某种形式的约束或责任。请将识别
出的主体及其相关的道义约束以清晰的列表形式返回。准确性和完整性非常重要，请确保不遗漏任何相关的信息。
例如，如果文档中有句子“公司必须保护客户的个人信息”，那么“公司”就是一个受约束的主体，其道义约束是“保护客户的个人信
息”。
[Regulatory document attachment]
Figure 7: Template Tempt1 is used to guide the large model in extracting all agents from the given regulatory
document.
任务：请仔细阅读以下段落，识别出与受道义约束的主体相关的道义词，并为每个预测的道义词提供简短的解释。道义词是指表达某种道
德或法律义务、责任或规范的词汇，如“必须”、“应当”、“禁止”、“责任”等。
段落：
[Insert paragraph text]
受道义约束的主体：
[Insert agent name]
示例：段落文本：“医疗机构必须保护患者的隐私。”主体：“医疗机构”预测道义词：“必须”解释：在这个段落中，“必须”表达了
医疗机构有法律和道德上的义务来保护患者的隐私。
[Provide your prediction and explanation here]
任务：请仔细阅读以下段落，识别出与受道义约束的主体相关的道义词，并为每个预测的道义词提供简短的解释。道义词是指表达某种道
德或法律义务、责任或规范的词汇，如“必须”、“应当”、“禁止”、“责任”等。
段落：
[Insert paragraph text]
受道义约束的主体：
[Insert agent name]
示例：段落文本：“医疗机构必须保护患者的隐私。”主体：“医疗机构”预测道义词：“必须”解释：在这个段落中，“必须”表达了
医疗机构有法律和道德上的义务来保护患者的隐私。
[Provide your prediction and explanation here]
Figure 8: Template Tempt2 is used to guide the large model in predicting the moral words based on the current
paragraph and the subject it contains.
```

Prompt-design observations (not new prompt text):
- Figure 7 asks for "all subjects subject to deontic constraints"; it says these may include organizations, companies, government departments, non-profit organizations, and individuals; it asks to return a clear list and emphasizes accuracy/completeness and no omission.
- Figure 8 asks to identify deontic words related to the constrained subject and provide a short explanation; examples of deontic words are "must", "should", "prohibited", "responsibility".
- No JSON/schema, no constrained field list; output is a "clear list".
- No no-answer/absent handling.
- No explicit span/boundary rule and no overlap/nesting rule.
- The agent prompt does not explicitly exclude objects, resources, or amounts from the agent class.
