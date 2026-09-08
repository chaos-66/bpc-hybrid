"""Render source-bound AI suggestions for human review; never write decisions/Gold.

All substantive annotations below are authored suggestions, not extractor output.
Offsets are calculated against the unchanged 74-sentence input. This deliberately
uses a proposal schema: the current editable v2 requires decided rule_items and
its exporter collapses mixed modalities. Neither behavior is suitable for an
unconfirmed multi-clause draft. No prediction, outcome label, .env or API is read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/input/gdpr7_stage2_input_v1.json"
BLANK = ROOT / "data/development/human_review/gdpr7_six_element_review_blank_v1.json"
DEST = ROOT / "data/development/human_review/gdpr7_ai_prefill_v1"
ATTRIBUTES = ("# Exact byte preservation for this AI review draft only.\n"
              ".gitattributes -text\nproposals.json text eol=lf\nmanifest.json text eol=lf\n"
              "请检查并修改这份预填稿.md text eol=lf\n").encode("utf-8")
FIELDS = ("actor", "action", "condition", "constraint", "exception")
ZH = {"modality": "规范类型", "actor": "谁执行", "action": "做什么",
      "condition": "什么情况下", "constraint": "时间／数量／方式限制", "exception": "例外"}
MOD = {"obligation": "义务：必须", "permission": "许可／权利：可以、有权",
       "prohibition": "禁止：不得", "definition": "定义／适用说明：不单独命令执行动作"}
SPEC: dict[str, dict] = {}


def item(m, a=None, x=None, c=None, k=None, e=None, evidence=None):
    return dict(modality=m, actor=a, action=x, condition=c, constraint=k,
                exception=e, modality_evidence=evidence)


def add(r, n, meaning, items, note="", flags=(), links=(), temporal=()):
    sid = f"gdpr_article{r}_s{n:03d}"
    assert sid not in SPEC, sid
    SPEC[sid] = dict(meaning_zh=meaning, items=items, review_note_zh=note,
                     focus_flags=list(flags), context_links=list(links),
                     temporal_suggestions=list(temporal))


def populate(sentences):
    # Article 15: the shared opening grants TWO distinct rights. The listed
    # information is the object of access, not seven new controller actions.
    info = ["处理目的", "个人数据类别", "接收方及接收方类别，尤其境外接收方",
            "预计保存期限；无法确定时，给出确定期限的标准",
            "更正、删除、限制处理及反对处理的权利是否存在",
            "向监管机构投诉的权利", "并非向本人收集时，可取得的数据来源信息",
            "自动决策是否存在，以及有关逻辑、意义和预计后果的信息"]
    for n, obj in enumerate(info, 1):
        t = sentences[f"gdpr_article15_s{n:03d}"]["sentence_text"]
        access = t[t.index("access to the personal data"):].rstrip(".")
        constraints = None
        extra_condition = []
        if n == 4:
            extra_condition = ["where possible", "if not possible"]
        if n == 7:
            extra_condition = ["where the personal data are not collected from the data subject"]
        if n == 8:
            constraints = "at least in those cases"
        add(15, n, f"数据主体有权先确认是否处理其数据；若正在处理，还可访问数据，并获知{obj}。", [
            item("permission", "The data subject", "obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed", evidence="shall have the right"),
            item("permission", "The data subject", access,
                 ["where that is the case"] + extra_condition, constraints, evidence="shall have the right")],
            "确认是否处理不以‘确实正在处理’为前提；该条件只约束第二项访问权。控制者是提供方，不能把数据主体有权访问写成数据主体必须访问。列举的信息保留在访问对象内。"
            + ("本句的两种期限信息是可选分支，不能把 where possible 与 if not possible 当成同时成立。" if n == 4 else ""),
            ("rights_vs_duties", "multiple_items") + (("alternative_conditions",) if n == 4 else ()))
    add(15,9,"数据转往第三国或国际组织时，数据主体有权获知该转移的适当保障。",[
        item("permission","the data subject","be informed of the appropriate safeguards pursuant to Article 46 relating to the transfer",
             "Where personal data are transferred to a third country or to an international organisation",evidence="shall have the right")],
        "主体是权利人；动作采用原句被动表达，不补写句中没有的通知者。",("rights_vs_duties",))
    add(15,10,"控制者必须提供正在处理的个人数据的副本。",[
        item("obligation","The controller","provide a copy of the personal data undergoing processing",evidence="shall")])
    add(15,11,"数据主体要求更多副本时，控制者可以按行政成本收取合理费用。",[
        item("permission","the controller","charge a reasonable fee","For any further copies requested by the data subject",
             ["reasonable fee","based on administrative costs"],evidence="may")])
    add(15,12,"通过电子方式请求的，原则上须以常用电子格式提供信息；本人另有要求的除外。",[
        item("obligation",None,"be provided","Where the data subject makes the request by electronic means",
             "in a commonly used electronic form","unless otherwise requested by the data subject",evidence="shall")],
        "本句没明写提供方。控制者可从条款上下文理解，但不把条件从句中的 the data subject 错接为信息提供者。",("implicit_actor",),["gdpr_article15_s010"])
    add(15,13,"取得副本的权利不得损害他人的权利和自由。",[
        item("prohibition",None,"adversely affect the rights and freedoms of others",evidence="shall not")],
        "句法主语是权利而非执行者；保留为权利行使的禁止性边界。",("implicit_actor",))
    add(16,1,"数据主体有权要求控制者及时更正有关自己的不准确个人数据。",[
        item("permission","The data subject","obtain from the controller",k="without undue delay",evidence="shall have the right")],
        "更正对象为 the rectification of inaccurate personal data concerning him or her。动作被时限短语打断，另列该原文片段为第二动作证据，不能拼接成不存在的连续原文。",("rights_vs_duties","discontinuous_phrase"))
    SPEC["gdpr_article16_s001"]["items"][0]["action"] = ["obtain from the controller","the rectification of inaccurate personal data concerning him or her"]
    add(16,2,"考虑处理目的后，数据主体有权补全不完整的数据，包括提供补充声明。",[
        item("permission","the data subject","have incomplete personal data completed",k=["Taking into account the purposes of the processing","including by means of providing a supplementary statement"],evidence="shall have the right")],
        "补充声明是补全数据的方式，不额外制造一条必须提交声明的义务。",("rights_vs_duties",))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def spans(value, text, sid, field):
    if value is None:
        return []
    if isinstance(value, str) or isinstance(value, tuple):
        value = [value]
    out = []
    for v in value:
        phrase, occurrence = v if isinstance(v, tuple) else (v, None)
        starts, pos = [], 0
        while (pos := text.find(phrase, pos)) >= 0:
            starts.append(pos)
            pos += 1
        if not starts:
            raise ValueError(f"{sid} {field}: not verbatim: {phrase!r}")
        if len(starts) > 1 and occurrence is None:
            raise ValueError(f"{sid} {field}: ambiguous ({len(starts)}); choose occurrence: {phrase!r}")
        start = starts[(occurrence or 1)-1]
        out.append(dict(text=phrase,start=start,end=start+len(phrase)))
    return out


def build():
    blank_bytes = BLANK.read_bytes()
    blank = json.loads(blank_bytes)
    sentences = {s["sample_id"]:s for r in blank["rules"] for s in r["sentences"]}
    inp = json.loads(SOURCE.read_bytes())
    source_sentences = {s["sample_id"]:s for r in inp["rules"] for s in r["sentences"]}
    assert len(sentences) == len(source_sentences) == 74
    assert set(sentences) == set(source_sentences)
    for sid, sentence in sentences.items():
        original = source_sentences[sid]
        assert sentence["sentence_text"] == original["approved_text_en"], sid
        assert all(sentence[k] == original[k] for k in ("sentence_idx","char_span","text_sha256")), sid
    populate(sentences)
    populate_rest(sentences)
    if set(SPEC) != set(sentences):
        raise ValueError(f"coverage mismatch: missing={set(sentences)-set(SPEC)}, extra={set(SPEC)-set(sentences)}")
    records = []
    for r in blank["rules"]:
        for s in r["sentences"]:
            sid, t = s["sample_id"], s["sentence_text"]
            spec = SPEC[sid]
            row = {k:s[k] for k in ("sample_id","sentence_idx","char_span","text_sha256","sentence_text")}
            row.update(rule_id=r["rule_id"],rule_text_sha256=r["rule_text_sha256"],
                       meaning_zh=spec["meaning_zh"],suggested_rule_items=[],
                       review_note_zh=spec["review_note_zh"],focus_flags=spec["focus_flags"],
                       context_links=spec["context_links"],temporal_suggestions=spec["temporal_suggestions"],
                       human_review={"decision":None,"correction":None,"comment":None,"reviewer":None},
                       review_state="unreviewed",is_gold=False)
            assert sha(t.encode()) == s["text_sha256"]
            for i, it in enumerate(spec["items"],1):
                ri = dict(item_id=f"{sid}.p{i}",modality=it["modality"],
                          modality_evidence=spans(it["modality_evidence"],t,sid,"modality_evidence"))
                assert ri["modality"] in MOD
                for f in FIELDS:
                    ri[f] = spans(it[f],t,sid,f)
                # A discontinuous object fragment is not a second action.
                # Associate actors with the whole proposed item, never each
                # individual evidence fragment as a separate action node.
                ri["action_structure"] = (
                    "comparison_operands_not_sequence" if sid == "gdpr_article7_s007" else
                    "alternative_predicates_shared_object" if sid == "gdpr_article6_s004" else
                    "single_predicate_multiple_evidence_fragments" if len(ri["action"]) > 1 else
                    "single_evidence_span" if ri["action"] else "no_explicit_action")
                ri["actor_action_map"] = [dict(actor_span_index=a,action_item_id=ri["item_id"])
                    for a in range(len(ri["actor"])) if ri["action"]]
                row["suggested_rule_items"].append(ri)
            for linked in row["context_links"]:
                assert linked in sentences, (sid, linked)
            records.append(row)
    return dict(schema_version="gdpr7_ai_annotation_proposals@1.0.0",
        status="ai_prefilled_awaiting_human_review",is_gold=False,human_confirmed=False,
        provenance={"author":"Codex assistant; authored in this conversation",
          "user_request":"人工的部分，你按照要求，认真预填好，我进行文件的检查与修改后然后跟你进行确认",
          "source_blank":str(BLANK.relative_to(ROOT)).replace("\\","/"),
          "source_blank_sha256":sha(blank_bytes),"source_input_sha256":sha(SOURCE.read_bytes()),
          "prediction_files_read_by_builder":False,"outcome_labels_read_by_builder":False,
          "independent_blind_annotator":False,
          "disclosure":"作者已参与项目讨论；本稿是AI辅助候选，不得宣称独立盲标、纯人工或已确认Gold。",
          "external_experimental_api_calls":0,
          "interpretation_sources":["https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679",
              "https://commission.europa.eu/law/law-topic/data-protection/information-individuals_en"]},
        annotation_policy={"span_unit":"zero-based, half-open Unicode character offsets in frozen sentence_text",
            "empty_field":"未见本句可直接支持的片段，不等于整条法律没有该要求",
            "context":"上下文链接与隐含主体单独说明，不伪造成当前句逐字span",
            "multiple_items":"不同情态分别保留；同一动作不连续的原文证据可以多片段",
            "action_structure":"action数组是证据片段；action_structure区分同一行为的断续片段、共享宾语的选择行为和比较对象，不能一片段当一个流程活动",
            "import":"确认前不导入现有decisions或Gold；当前v2的单情态/唯一出现定位不能无损容纳全部候选，确认后应逐条保留条目、坐标与关系，不能取首项静默降级。"},
        counts={"rules":9,"sentences":len(records),"items":sum(len(r["suggested_rule_items"]) for r in records),
                "anchored_spans":sum(len(it[f]) for r in records for it in r["suggested_rule_items"] for f in (*FIELDS,"modality_evidence")),
                "human_confirmed":0},records=records)


def render(doc):
    lines = ["# GDPR 74句人工核对预填稿", "",
        "**这份文件供你直接检查和修改。74句均有AI建议；人工确认仍为0/74，不是Gold。**", "",
        "每句先读‘大白话’，再看六要素。正确的内容不用重抄；有问题就在该句的‘你的修改’填写字段和正确内容。全部检查后，告诉我确认的是这份文件，我再核对修改、生成供你确认的正式导入内容。", "",
        "本 Markdown 是本轮人工修改入口；旁边 JSON 是生成时的机器底稿。修改 Markdown 不会自动改 JSON，后续导入必须先对账，不能用旧底稿覆盖你的修改。", "",
        "**重点规则**：有权≠必须；不要求≠禁止；条文/通知/数据等句法主语未必是执行者。空字段表示本句未明示，不能补造原文。条件、例外的跨句继承单独写在备注中。", "",
        "**阅读顺序建议**：先看33、34、22条（23句，覆盖论文案例），然后6、7、15、16、17、20条（51句）。每句都需检查，重点提示只是帮助分配注意力。", "",
        "标注对象是项目冻结的改写/展开英文句子，而不是把网上法条重新分句。中文是辅助释义，不取代英文。", "",
        "规范类型中的 definition 在此作为定义/描述/适用范围说明的四分类容器，不代表每一句都在给术语下定义。复合句保留多条规范，不能导入时只取第一条。", "",
        "来源：[GDPR官方条文](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679)。第22条一般性禁止的解释另参考[欧盟委员会说明](https://commission.europa.eu/law/law-topic/data-protection/information-individuals_en)；具体实验标签仍待人工裁决。", "",
        "## 需优先统一的标注口径", "",
        "1. 第15、16、17、20条的明确权利建议标 permission；第17条同句的控制者删除义务另标 obligation。",
        "2. 第22条第1句建议按一般性禁止标 prohibition，但被保护的数据主体不是实施自动决策的违规执行者。",
        "3. shall not apply / shall not be required 通常是适用排除或义务豁免，不机械标成禁止。",
        "4. 条件、例外与列举项被分句切开时，保留链接；不能丢掉，也不能伪造当前句中的主体和动作。", ""]
    order = ["article33","article34","article22","article6","article7","article15","article16","article17","article20"]
    for rid in order:
        rows = [r for r in doc["records"] if r["rule_id"] == rid]
        lines += [f"## {rid}（{len(rows)}句）", ""]
        for r in rows:
            lines += [f"### {r['sample_id']}", "", "**英文原句**", "", r["sentence_text"], "",
                      "**大白话**："+r["meaning_zh"], ""]
            for it in r["suggested_rule_items"]:
                lines += [f"**建议条目 {it['item_id'].split('.')[-1]}**", "", "| 字段 | 预填建议 |", "|---|---|"]
                lines += [f"| 规范类型 | {it['modality']}：{MOD[it['modality']]} |"]
                for f in FIELDS:
                    vals = "；<br>".join(v["text"].replace("|","\\|") for v in it[f]) or "∅（本句未明示或不适用；详见备注）"
                    lines += [f"| {ZH[f]} | {vals} |"]
                lines += [""]
            if r["review_note_zh"]:
                lines += ["**核对提示**："+r["review_note_zh"], ""]
            if r["context_links"]:
                lines += ["**上下文关联**："+"、".join(r["context_links"]), ""]
            if r["temporal_suggestions"]:
                lines += ["**顺序建议**："+"；".join(r["temporal_suggestions"]), ""]
            lines += ["**你的修改**：", "", "**你的确认**：待确认", "", "---", ""]
    lines += ["## 确认后如何接入", "",
              "先汇总本文件中的修改并与机器底稿对账，再把你明确确认的值导入人工裁决层。确认前不改变人工进度、冻结状态或实验结果。",
              "重复出现的短语已记录具体字符位置；复合句的不同情态、多个片段和跨句解释会保留，不能因当前导入器的限制静默丢弃。",
              "流程级‘正常/违规’案例标准答案属于另一层，本文件的句子级预填不能替它作确认。", ""]
    return "\n".join(lines)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--check",action="store_true")
    args=ap.parse_args()
    doc=build()
    assert all(r["review_state"] == "unreviewed" and r["is_gold"] is False
               and all(v is None for v in r["human_review"].values()) for r in doc["records"])
    jb=(json.dumps(doc,ensure_ascii=False,indent=2)+"\n").encode()
    mb=render(doc).encode()
    files={"proposals.json":jb,"请检查并修改这份预填稿.md":mb,".gitattributes":ATTRIBUTES}
    manifest={"schema_version":"gdpr7_ai_prefill_manifest@1.0.0","status":doc["status"],
              "counts":doc["counts"],"source":doc["provenance"],
              "checks":{"coverage_74":True,"verbatim_spans":True,"human_decisions_all_empty":True,
                        "no_gold_promotion":True},
              "artifacts":{k:{"sha256":sha(v),"bytes":len(v)} for k,v in files.items()}}
    files["manifest.json"]=(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n").encode()
    for name, data in files.items():
        p=DEST/name
        if args.check:
            if not p.is_file() or p.read_bytes()!=data:
                raise ValueError(f"artifact differs from authored source: {p}; preserve any human edits")
        else:
            if p.exists():
                raise FileExistsError(f"refusing to overwrite: {p}")
    if not args.check:
        DEST.mkdir(parents=True,exist_ok=True)
        for name,data in files.items():
            with (DEST/name).open("xb") as f:
                f.write(data)
    print(json.dumps({"checked":args.check,"counts":doc["counts"],"directory":str(DEST)},ensure_ascii=False))


def populate_17_20_22(ss):
    add(17,1,"数据主体有权请求及时删除；控制者也有及时删除的义务，但须满足后面列举的至少一种理由。",[
        item("permission","The data subject","obtain from the controller the erasure of personal data concerning him or her",
             "where one of the following grounds applies",("without undue delay",1),evidence="shall have the right"),
        item("obligation",("the controller",2),"erase personal data","where one of the following grounds applies",
             ("without undue delay",2),evidence="shall have the obligation")],
        "同一句同时包含权利和义务，必须保留两个情态。两个 the controller、两个时限均按各自出现位置定位。后六句是可选删除理由，不能作为六项同时必须满足的条件。",
        ("mixed_modalities","alternative_conditions","repeated_phrase"),[f"gdpr_article17_s{i:03d}" for i in range(2,8)])
    meanings={2:"删除理由之一：数据已不再是实现原收集或处理目的所必需的。",
        3:"删除理由之一：本人撤回处理所依据的同意，而且没有其他处理依据。",
        4:"删除理由之一：本人反对处理且无优先的正当理由，或本人依第21条第2款反对处理。",
        5:"删除理由之一：数据曾被违法处理。",6:"删除理由之一：控制者受约束的欧盟法或成员国法要求删除数据。",
        7:"删除理由之一：数据系在向儿童提供第8条所述信息社会服务时收集。"}
    for n,meaning in meanings.items():
        t=ss[f"gdpr_article17_s{n:03d}"]["sentence_text"]
        add(17,n,meaning,[item("definition",c=t.rstrip("."))],
            "本句属于第1款删除理由列表，主要功能是限定前句适用条件；不把这些事实陈述改写为新的处理义务。第6句虽然含 have to be erased，仍处在删除依据的列举中，请核对是否采用条件片段口径。"
            if n==6 else "本句是上一句的可选触发理由，未复写完整删除规范；六要素中的条件保留全文，主体/删除动作通过上下文关联表达。",
            ("context_fragment","alternative_conditions"),["gdpr_article17_s001"])
    add(17,8,"控制者已公开数据且负有删除义务时，须考虑技术和成本，合理通知其他处理这些数据的控制者删除相关链接或副本。",[
        item("obligation",("the controller",2),[
            "take reasonable steps","inform controllers which are processing the personal data that the data subject has requested the erasure by such controllers of any links to, or copy or replication of, those personal data"],
            "Where the controller has made the personal data public and is obliged pursuant to paragraph 1 to erase the personal data",
            ["taking account of available technology and the cost of implementation","reasonable steps","including technical measures"],evidence="shall")],
        "主执行者是主句第二次出现的控制者；第一处在条件中。通知内容不另外变成对收件人的独立命令。",("repeated_phrase","discontinuous_phrase"),["gdpr_article17_s001"])
    grounds={9:"表达与信息自由",10:"法定义务、公共利益任务或行使公权力",11:"公共卫生方面的公共利益",
             12:"符合第89条保障要求的公共利益存档、科研、历史研究或统计，且删除会使目标无法实现或严重受损",13:"提出、行使或抗辩法律请求"}
    for n,g in grounds.items():
        t=ss[f"gdpr_article17_s{n:03d}"]["sentence_text"]
        e=t[t.index("to the extent that"):].rstrip(".")
        add(17,n,f"为{g}确有必要处理数据的范围内，第1、2款删除要求不适用。",[
            item("definition",e=e,evidence="shall not apply")],
            "这是删除义务的适用排除，不是禁止删除，也不是无条件允许任意保留。例外应关联第1、2款，不能只从本句空动作得出无法解释整条规则。",
            ("exemption_not_prohibition","context_exception"),["gdpr_article17_s001","gdpr_article17_s008"])
    add(20,1,"满足处理依据和自动处理条件时，本人有权取得机器可读的数据，也有权不受阻碍地把这些数据传给另一控制者。",[
        item("permission","The data subject","receive the personal data concerning him or her",
             ["which he or she has provided to a controller","where the processing is based on consent pursuant to point (a) of Article 6(1) or point (a) of Article 9(2) or on a contract pursuant to point (b) of Article 6(1)","the processing is carried out by automated means"],
             "in a structured, commonly used and machine-readable format",evidence="shall have the right"),
        item("permission","The data subject","transmit those data to another controller",
             ["where the processing is based on consent pursuant to point (a) of Article 6(1) or point (a) of Article 9(2) or on a contract pursuant to point (b) of Article 6(1)","the processing is carried out by automated means"],
             "without hindrance from the controller to which the personal data have been provided",evidence=("have the right",2))],
        "接收与转移是两项权利；同意或合同为可选处理依据，它们再与自动处理条件共同适用。提供过数据是对象限定，不是本句新命令。",("multiple_items","rights_vs_duties","alternative_conditions"))
    add(20,2,"行使数据可携权时，在技术可行的情况下，本人有权要求控制者之间直接传输数据。",[
        item("permission","the data subject","have the personal data transmitted directly from one controller to another",
             ["In exercising his or her right to data portability pursuant to paragraph 1","where technically feasible"],evidence="shall have the right")],
        "where technically feasible 建议作为权利适用条件，不机械改成 unless 型例外。是否可行需要流程外证据。",("rights_vs_duties","condition_vs_exception"),["gdpr_article20_s001"])
    add(20,3,"行使数据可携权不得影响第17条规定的权利和义务。",[
        item("obligation",None,"be without prejudice to Article 17",evidence="shall")],
        "这是权利行使的保留条款。原文用肯定形式 shall be without prejudice，建议义务标签；若项目统一把不损害语义标 prohibition，需要人工统一口径。不能造一个实际流程动作。",("scope_clause","modality_policy"),["gdpr_article17_s001"])
    add(20,4,"为执行公共利益任务或行使公权力所必需的处理，不适用该数据可携权。",[
        item("definition",e="processing necessary for the performance of a task carried out in the public interest or in the exercise of official authority vested in the controller",evidence="shall not apply")],
        "是数据可携权的适用排除，不是禁止数据传输。",("exemption_not_prohibition",),["gdpr_article20_s001"])
    add(20,5,"行使数据可携权不得损害其他人的权利和自由。",[
        item("prohibition",None,"adversely affect the rights and freedoms of others",evidence="shall not")],
        "权利是句法主语，不能映射为业务执行者；本句是该权利的边界。",("implicit_actor",),["gdpr_article20_s001"])
    add(22,1,"原则上不得让个人承受完全由自动处理作出、并产生法律效果或类似重大影响的决定。",[
        item("prohibition",None,"be subject to a decision based solely on automated processing",
             "which produces legal effects concerning him or her or similarly significantly affects him or her",
             "based solely on automated processing, including profiling",evidence="shall have the right not to")],
        "优先建议 prohibition，依据欧盟委员会对第22条一般性禁止的解释。The data subject 是受保护者，不能标成违法决策执行者；本句没有明写 controller，actor 留空并提示上下文主体。若采用严格句法的权利人编码，可讨论 permission，但不能机械判 obligation，也不能为迎合任何方法结果选择标签。",
        ("priority_adjudication","implicit_actor","rights_vs_duties"),["gdpr_article22_s002","gdpr_article22_s003","gdpr_article22_s004"])
    for n,meaning in {2:"决定为与本人订立或履行合同所必需时，第1款的限制存在例外。",
        3:"欧盟法或成员国法授权该决定且规定适当保障措施时，第1款的限制存在例外。",
        4:"决定以本人的明确同意为基础时，第1款的限制存在例外。"}.items():
        t=ss[f"gdpr_article22_s{n:03d}"]["sentence_text"]
        add(22,n,meaning,[item("definition",e=t[t.index("if the decision"):].rstrip("."),evidence="shall not apply")],
            "这是第1款一般性禁止的例外，不能标成新的禁止。例外彼此可选；第4句开头的 or 是冻结文本中的衔接词，原样保留。",
            ("context_exception","exemption_not_prohibition"),["gdpr_article22_s001"])
    add(22,5,"使用合同必要或明确同意这两类例外时，控制者必须采取保障措施，至少保障人工介入、表达观点和质疑决定的权利。",[
        item("obligation","the data controller","implement suitable measures to safeguard the data subject's rights and freedoms and legitimate interests",
             "In the cases referred to in points (a) and (c) of paragraph 2",
             "at least the right to obtain human intervention on the part of the controller, to express his or her point of view and to contest the decision",evidence="shall")],
        "列举的是保障措施至少覆盖的权利，不等于本人必须表达意见、必须提出异议。",("rights_vs_duties",),["gdpr_article22_s002","gdpr_article22_s004"])
    add(22,6,"第2款所涉决定原则上不能以敏感个人数据为基础；满足第9条指定依据且有适当保障时例外。",[
        item("prohibition",None,"be based on special categories of personal data referred to in Article 9(1)",
             "Decisions referred to in paragraph 2",e="unless point (a) or (g) of Article 9(2) applies and suitable measures to safeguard the data subject's rights and freedoms and legitimate interests are in place",evidence="shall not")],
        "Decisions 是被约束对象，不是执行者。例外内部必须同时满足合法依据与适当保障，不能拆成二选一。",("implicit_actor","conjunctive_exception"),["gdpr_article22_s002","gdpr_article22_s003","gdpr_article22_s004"])


def populate_33_34_7(ss):
    add(33,1,"发生个人数据泄露时，控制者须及时通知主管监管机构；可行时应在知悉后72小时内通知。若泄露不大可能产生权利自由风险，则可不通知。",[
        item("obligation","the controller","notify the personal data breach to the supervisory authority competent in accordance with Article 55",
             "In the case of a personal data breach",
             ["without undue delay","where feasible, not later than 72 hours after having become aware of it"],
             "unless the personal data breach is unlikely to result in a risk to the rights and freedoms of natural persons",evidence="shall")],
        "72小时从知悉泄露起算；where feasible 只修饰72小时时限，不免除整体通知义务。保留及时性与量化时限两个片段，不丢低风险例外。",
        ("priority_case","constraint_scope"),temporal=["having become aware of it 在 notify the personal data breach 之前；起点是知悉，不能改成泄露发生时刻。"])
    add(33,2,"向监管机构的通知没有在72小时内作出时，通知须附上延误理由。",[
        item("obligation",None,"be accompanied by reasons for the delay",
             "Where the notification to the supervisory authority is not made within 72 hours",evidence="shall")],
        "it 指通知，而不是通知执行者。within 72 hours 属于‘延误’触发条件，不能解释为允许再等72小时。",("priority_case","implicit_actor","constraint_scope"),["gdpr_article33_s001"])
    add(33,3,"处理者一旦知悉个人数据泄露，须及时通知控制者。",[
        item("obligation","The processor","notify the controller","after becoming aware of a personal data breach",
             "without undue delay",evidence="shall")],
        "本句执行者是 processor，接收者是 controller；本句没有72小时数字，不能从第1句移植给处理者。",
        ("priority_case",),temporal=["becoming aware of a personal data breach 先于 notify the controller；原句 after 提供顺序证据。"])
    for n,meaning in {4:"通知至少描述泄露性质，并在可能时给出涉及人员和数据记录的类别及约数。",
         5:"通知至少给出数据保护官或其他联络点的姓名及联系方式。",6:"通知至少描述泄露可能造成的后果。",
         7:"通知至少描述控制者已采取或拟采取的应对措施，适当时包括减轻不利影响的措施。"}.items():
        t=ss[f"gdpr_article33_s{n:03d}"]["sentence_text"]
        verb="communicate" if n==5 else "describe"
        x=t[t.index(verb):].rstrip(".")
        ks=["at least"]
        if n==4:ks.append("where possible")
        if n==7:ks.append("where appropriate")
        add(33,n,meaning,[item("obligation",None,x,k=ks,evidence="shall")],
            "通知是承载要求的文书，不是业务执行者；不要把 notification 当成泳道。实际提供方可联系第1款控制者，在备注中保留而不伪造本句主句actor。内容列举仍是同一通知要求。",
            ("implicit_actor","document_subject"),["gdpr_article33_s001"])
    add(33,8,"无法一次提供全部信息时，可以分阶段提供，但不得造成不当的进一步延迟。",[
        item("permission",None,"be provided","Where, and in so far as, it is not possible to provide the information at the same time",
             ["in phases","without undue further delay"],evidence="may")],
        "允许分阶段不是免除提供信息；句中没有明示提供者，the information 是内容对象。",("implicit_actor",),["gdpr_article33_s001"])
    add(33,9,"控制者必须记录所有个人数据泄露，包括事实、影响和补救行动。",[
        item("obligation","The controller","document any personal data breaches",
             k="comprising the facts relating to the personal data breach, its effects and the remedial action taken",evidence="shall")],
        "记录义务覆盖 any breaches，不能把第1句低风险免通知例外自动迁移到记录义务。",("priority_case",))
    add(33,10,"上述记录应使监管机构能够核实本条的遵守情况。",[
        item("obligation",None,"enable the supervisory authority to verify compliance with this Article",evidence="shall")],
        "监管机构是验证者，但本句没有命令其必须验证；主要求是记录具备可供核实的功能。documentation 不是执行者。",("document_subject","implicit_actor"),["gdpr_article33_s009"])
    add(34,1,"泄露可能对个人权利自由造成高风险时，控制者必须及时告知数据主体。",[
        item("obligation","the controller","communicate the personal data breach to the data subject",
             "When the personal data breach is likely to result in a high risk to the rights and freedoms of natural persons",
             "without undue delay",evidence="shall")],
        "告知对象是 data subject，不是监管机构；本条为高风险触发，本句没有72小时期限。后续第3款给出通知豁免。",
        ("priority_case",),["gdpr_article34_s003","gdpr_article34_s004","gdpr_article34_s005"])
    add(34,2,"给本人的告知须用清楚、简单的语言描述泄露性质，并至少包含第33条第3款指定的信息和措施。",[
        item("obligation",None,["describe","the nature of the personal data breach"],k="in clear and plain language",evidence="shall"),
        item("obligation",None,"contain at least the information and measures referred to in points (b), (c) and (d) of Article 33(3)",k="at least",evidence="shall")],
        "两项内容义务并列，无先后要求。动作 describe 与对象被方式短语隔开，所以保留多个原文证据片段。communication 是文书，不当作主体。",
        ("multiple_items","implicit_actor","discontinuous_phrase"),["gdpr_article34_s001","gdpr_article33_s005","gdpr_article33_s006","gdpr_article33_s007"])
    for n,meaning in {3:"已实施并应用适当保护措施，尤其使未经授权者无法读懂数据的措施（如加密）时，可免于逐一告知。",
         4:"已采取后续措施，确保高风险不再可能发生时，可免于逐一告知。",5:"逐一告知会造成不成比例的工作量时，可免于逐一告知，但须注意下一句的替代公告要求。"}.items():
        t=ss[f"gdpr_article34_s{n:03d}"]["sentence_text"]
        add(34,n,meaning,[item("definition",e=t[t.index("if "):].rstrip("."),evidence="shall not be required")],
            "这是对前面通知义务的豁免，不是禁止沟通，也不是一条新的无条件许可；例外必须关联第1款，不能只凭本句无动作就丢掉豁免内容。",
            ("priority_case","exemption_not_prohibition","context_exception"),["gdpr_article34_s001"] + (["gdpr_article34_s006"] if n==5 else []))
    add(34,6,"在上述工作量不成比例的情况下，应改用公开沟通或同等有效的类似措施，让本人得知情况。",[
        item("obligation",None,"be a public communication or similar measure","In such a case",
             ["instead","whereby the data subjects are informed in an equally effective manner"],evidence="shall")],
        "such a case 特指上一句工作量不成比例，不把公开沟通要求扩展到加密或消除风险两种豁免。执行者在本句省略。",
        ("priority_case","context_reference","implicit_actor"),["gdpr_article34_s005"])
    add(34,7,"若控制者尚未告知本人，监管机构考虑高风险可能性后，可以要求其告知，也可以认定第3款某项豁免成立。",[
        item("permission","the supervisory authority","require it to do so",
             "If the controller has not already communicated the personal data breach to the data subject",
             "having considered the likelihood of the personal data breach resulting in a high risk",evidence=("may",1)),
        item("permission","the supervisory authority","decide that any of the conditions referred to in paragraph 3 are met",
             "If the controller has not already communicated the personal data breach to the data subject",
             "having considered the likelihood of the personal data breach resulting in a high risk",evidence=("may",2))],
        "两条权限是 or 分支；it 指控制者，do so 指告知，不把监管机构错接成向本人发送告知的执行者。原文代理指称保留供你检查。",
        ("priority_case","multiple_items","coreference","alternative_actions"),["gdpr_article34_s001","gdpr_article34_s003","gdpr_article34_s004","gdpr_article34_s005"])
    add(7,1,"以同意为处理依据时，控制者必须能证明本人已同意处理其个人数据。",[
        item("obligation","the controller","be able to demonstrate that the data subject has consented to processing of his or her personal data",
             "Where processing is based on consent",evidence="shall")],
        "has consented 是证明内容，不另设成数据主体必须同意的义务。")
    add(7,2,"书面声明同时涉及其他事项时，同意请求须与其他内容清晰区分，并易懂、易获取、语言清楚。",[
        item("obligation",None,"be presented","If the data subject's consent is given in the context of a written declaration which also concerns other matters",
             ["in a manner which is clearly distinguishable from the other matters","in an intelligible and easily accessible form","using clear and plain language"],evidence="shall")],
        "request 是呈现对象；实际请求方未明写，不把条件中的 data subject 当作提出同意请求的主体。",("implicit_actor","document_subject"))
    add(7,3,"该声明中违反本条例的部分不具有约束力。",[
        item("definition",c="which constitutes an infringement of this Regulation",k="shall not be binding",evidence="shall not be binding")],
        "这是法律效力的说明，不是禁止本人作出声明或要求控制者执行某动作。",("scope_clause","exemption_not_prohibition"))
    add(7,4,"本人有权随时撤回同意。",[
        item("permission","The data subject","withdraw his or her consent",k="at any time",evidence="shall have the right")],
        "有权撤回不等于必须撤回。",("rights_vs_duties",))
    add(7,5,"撤回同意不会追溯影响撤回前基于同意进行处理的合法性。",[
        item("definition",k="shall not affect the lawfulness of processing based on consent before its withdrawal",evidence="shall not affect")],
        "这是撤回同意的时间效力规则，不机械解释为禁止执行某个流程动作。before its withdrawal 限定既往处理；本句不授权继续处理。",("scope_clause",),["gdpr_article7_s004"])
    add(7,6,"在本人给出同意之前，应先让其知晓可撤回同意这件事。",[
        item("obligation",None,"be informed thereof","Prior to giving consent",evidence="shall")],
        "data subject 是被告知者，通知者省略；thereof 回指撤回权。不能抽成数据主体必须通知他人。",
        ("implicit_actor","coreference"),["gdpr_article7_s004"],
        ["be informed thereof 在 giving consent 之前。前者是本句义务动作；后者只是顺序锚点，不构造必须同意的义务。"])
    add(7,7,"撤回同意应当与给出同意一样容易。",[
        item("obligation",None,["withdraw","give consent"],k="as easy to withdraw as to give consent",evidence="shall")],
        "这是易用程度比较，不是先撤回再同意的流程顺序，也不是要求本人必须完成两项动作。两片段记录比较对象。",("comparative_constraint","implicit_actor"),["gdpr_article7_s004"])
    add(7,8,"判断同意是否自愿时，要特别考虑合同或服务是否以同意不必要的数据处理为条件。",[
        item("obligation",None,"be taken of whether, inter alia, the performance of a contract, including the provision of a service, is conditional on consent to the processing of personal data that is not necessary for the performance of that contract",
             "When assessing whether consent is freely given","utmost account",evidence="shall")],
        "被动表达省略评估者；句子要求评估捆绑同意这一因素，并非直接宣布所有合同同意无效。",("implicit_actor",))


def populate_6(ss):
    add(6,1,"只有在本人已就一个或多个特定目的同意处理其数据的相应范围内，处理才具备本项合法依据。",[
        item("permission",None,"Processing",
             "only if and to the extent that the data subject has given consent to the processing of his or her personal data for one or more specific purposes",evidence="shall be lawful only if")],
        "建议按有条件允许处理标 permission；shall be lawful 不是命令数据主体给出同意。本句是项目展开的第6(1)(a)项，必须与其他可选依据合看，不能推出所有处理都必须取得同意。Processing 是原文名词化行为；控制者未作主句执行者明示。",
        ("alternative_conditions","implicit_actor","modality_policy"),["gdpr_article6_s002"])
    t=ss["gdpr_article6_s002"]["sentence_text"]
    parts=t.rstrip(".").split("; Processing")
    assert len(parts)==5
    its=[]
    for i,p in enumerate(parts,1):
        if i>1:p="Processing"+p
        condition=p[p.index("only if"):]
        exc=None
        if "except where" in condition:
            condition,exc=condition.split(", except where",1)
            exc="except where"+exc
        its.append(item("permission",None,("Processing",i),condition,e=exc,evidence=("shall be lawful only if",i)))
    add(6,2,"另外五种处理依据分别是：合同或订约措施所必需、履行法定义务、保护重大利益、公共任务或公权力、正当利益；最后一种受本人权益优先的限制。",its,
        "冻结分句把五个可选依据放在一句里。拆成五条建议，条目之间是 OR，不是要求公司同时满足五种依据。第5项的 except 仅约束正当利益依据。各处 Processing 用显式出现序号定位，不能全取第一处。",
        ("multiple_items","alternative_conditions","repeated_phrase","exception_scope"),["gdpr_article6_s001"])
    add(6,3,"公共机关执行其任务时进行的数据处理，不能以第1款(f)项正当利益作为依据。",[
        item("definition",e="processing carried out by public authorities in the performance of their tasks",evidence="shall not apply")],
        "排除的是某一处理依据，不是禁止公共机关处理任何数据。public authorities 出现在例外范围中，不生成独立操作命令。",
        ("exemption_not_prohibition","context_exception"),["gdpr_article6_s002"])
    add(6,4,"成员国可以保留或制定更具体的规定，使本条例适用于法定义务和公共任务等处理情况。",[
        item("permission","Member States",["maintain","introduce more specific provisions to adapt the application of the rules of this Regulation"],
             "with regard to processing for compliance with points (c) and (e) of paragraph 1",
             "by determining more precisely specific requirements for the processing and other measures to ensure lawful and fair processing including for other specific processing situations as provided for in Chapter IX",evidence="may")],
        "maintain 与 introduce 是可选立法行为，共享 provisions 对象；不能把它们转成企业必须先后执行的两个活动。",("alternative_actions","discontinuous_phrase"))
    add(6,5,"基于第1款(c)、(e)项的处理，其依据必须由欧盟法或约束控制者的成员国法规定。",[
        item("obligation",None,"be laid down",
             "The basis for the processing referred to in point (c) and (e) of paragraph 1",
             "by Union law or Member State law to which the controller is subject",evidence="shall")],
        "规定的是法律依据的来源，不应将法律当作企业流程执行者；controller 只是受该法约束的主体。",("implicit_actor","scope_clause"))
    add(6,6,"处理目的应在法律依据中确定；就公共任务或公权力依据而言，目的应为执行该任务或权力所必需。",[
        item("obligation",None,"be determined",k="in that legal basis",evidence=("shall",1)),
        item("obligation",None,"be necessary for the performance of a task carried out in the public interest or in the exercise of official authority vested in the controller",
             "as regards the processing referred to in point (e) of paragraph 1",evidence=("shall",2))],
        "两种目的约束按 or 及限定条件保留，不是两个活动的先后顺序。目的不是流程执行者。",("multiple_items","scope_clause","alternative_conditions"),["gdpr_article6_s005"])
    add(6,7,"该法律依据可以进一步规定处理条件、数据类型、涉及人员、接收实体和目的、保存期限及保障措施等事项。",[
        item("permission",None,"contain specific provisions to adapt the application of rules of this Regulation",
             k="inter alia: the general conditions governing the lawfulness of processing by the controller; the types of data which are subject to the processing; the data subjects concerned; the entities to, and the purposes for which, the personal data may be disclosed; the purpose limitation; storage periods; and processing operations and processing procedures, including measures to ensure lawful and fair processing such as those for other specific processing situations as provided for in Chapter IX",
             evidence=("may",1))],
        "这是授权法律规定的内容范围，不是要求流程逐项执行列举内容。内层 personal data may be disclosed 位于接收方/目的描述中，不独立生成为许可披露数据的规则。",("scope_clause","implicit_actor"),["gdpr_article6_s005"])
    add(6,8,"该欧盟法或成员国法必须服务于公共利益，并与追求的合法目的相称。",[
        item("obligation",None,"meet an objective of public interest",evidence="shall"),
        item("obligation",None,"be proportionate to the legitimate aim pursued",evidence="shall")],
        "两个并列要求针对法律本身；不把 law 当作公司流程泳道，不凭 and 添加活动顺序。",("multiple_items","scope_clause","implicit_actor"))
    add(6,9,"拟将数据用于不同目的，且没有本人同意或特定法律授权时，控制者必须评估新旧目的是否相容，并考虑下句列出的因素。",[
        item("obligation","the controller","take into account, inter alia",
             "Where the processing for a purpose other than that for which the personal data have been collected is not based on the data subject's consent or on a Union or Member State law which constitutes a necessary and proportionate measure in a democratic society to safeguard the objectives referred to in Article 23(1)",
             "in order to ascertain whether processing for another purpose is compatible with the purpose for which the personal data are initially collected",evidence="shall")],
        "原句以冒号结束，列举对象在s010。这里将评估目的保留为方式/目的限定；不能把句末缺对象当成该法规没有需考虑的内容。",("context_fragment",),["gdpr_article6_s010"])
    add(6,10,"需要考虑：新旧目的关联、收集背景和双方关系、数据性质、继续处理的后果，以及加密或假名化等保障措施。",[
        item("definition",k=ss["gdpr_article6_s010"]["sentence_text"].rstrip("."))],
        "这不是新的完整命令，而是上一句 take into account 的五类宾语列表。没有独立主体/动作，不从列表里随意挑一个动词作主动作。",
        ("context_fragment",),["gdpr_article6_s009"])


def populate_rest(sentences):
    populate_17_20_22(sentences)
    populate_33_34_7(sentences)
    populate_6(sentences)


if __name__ == "__main__":
    main()
