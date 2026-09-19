# Haque & Singh (COINE 2024 / arXiv 2404.02269): exact prompt

Source: A. Haque and M. P. Singh, "Extracting Norms from Contracts Via ChatGPT: Opportunities and Challenges", arXiv:2404.02269v1, Section 3.2, PDF p. 7. The published COINE/LNCS version may present this as Figure 1; the copy below was verified in the public arXiv PDF.

Extraction method: PyMuPDF text extraction from `.tmp/lit/pdf/haque_singh_2024_arxiv.pdf`.

Evidence level: Verified (arXiv PDF). The published Springer full text was not accessible; the public preprint is the verified source.

```text
ChatGPT Prompt to Extract Norms from Contracts
Given a sentence from a contract (between two parties), extract norms
for better contract understanding. A norm specifies the expectations from parties
involved in the contract in terms of their behavior and actions and is represented
by four elements subject, object, antecedent, and consequent. A norm is directed
from a subject (the party on whom the norm applies) to an object (the party
with respect to whom the norm applies) and is constructed as a conditional re-
lationship involving an antecedent (which brings the norm into force, i.e., the
condition on which the action of the subject depends) and a consequent (which
brings the norm to satisfaction, i.e., the outcomes of the action). A norm can
be one of the following four types:
(a) A commitment means that its subject commits to its object to ensure the
consequent if the antecedent holds.
(b) A prohibition means that its subject is forbidden by its object from bringing
about the consequent if the antecedent holds.
(c) An authorization means that its object authorizes its subject to bring about
the consequent if the antecedent holds.
(d) A power means that its subject is empowered by its object to bring about the
consequent if the antecedent holds.
The norm types of authorization and power are similar; however, some differ-
ences exist. Authorization allows the subject to bring about the consequent (pro-
vided it doesn’t violate some other norm), whereas power empowers the subject
to bring about the consequent when that causes a change in the existing norms.
In cases where more than one norm exists, extract all norms. Identify the fol-
lowing given a contract sentence.
1. Norm type: norm type can be ‘authorization,’ ‘power,’ ‘commitment,’ or ‘pro-
hibition’
2. Subject: the party on whom the norm applies
3. Object: the party with respect to whom the norm applies
4. Antecedent: which brings the norm into force
5. Consequent: which brings the norm to satisfaction
The contract sentence is as follows:
```

Prompt-design observations (not new prompt text):
- Zero-shot: no examples or negative cases are included in the prompt.
- Output format: a list, not JSON; no explicit instruction to return exact original spans.
- `object` is a counterparty/party, not our `action object`; `antecedent`/`consequent` are event-level norm elements, not span labels.
- The paper reports that adding explicit subject/object directionality to the prompt reduced role mismatches (Section 3.2, p. 7).
