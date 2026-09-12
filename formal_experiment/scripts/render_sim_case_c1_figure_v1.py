# -*- coding: utf-8 -*-
"""Publication SIM diagram. Presentation only; no scoring or experiment imports.

Every source node and sequence/message flow retains its ID. Original BPMN
supplies participant messages and event symbols. Data associations are omitted.
"""
from __future__ import annotations
import hashlib
import html
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPSULE = ROOT / "outputs/development/sim_case_c1/run_v1/capsule.json"
OUT = ROOT / "outputs/reports/sim_case_c1_result_figure.svg"
W, H = 2400, 1260
FONT = "Times New Roman, Liberation Serif, serif"
INK = "#202020"
COLORS = {"r9":("#367cc0","#eaf3fc"), "r10":("#c38b12","#fff5d9"),
          "r11":("#c8733e","#fff0e6"), "r13":("#827298","#f3eff8"), "r8":("#668580","#eef5f3")}
# Stable source ID prefix, alias, and page-only geometry.
LAYOUT_TEXT = """
F2A5FCC5 start 158 498 44 44
87D1789E request 250 482 124 76
4A5668DB data 405 498 44 44
B8D4B659 debt 483 498 44 44
4CAE720C portability 594 482 130 76
A0EC90A7 port_choice 762 498 44 44
B72CE851 assign 875 482 130 76
5DB79A16 merge 1060 498 44 44
6B3F7867 sign 1146 482 126 76
CD9A6475 split 1311 498 44 44
E5495E81 payment_request 1410 482 124 76
F34F5D97 payment 1588 498 44 44
2583945D join 1768 498 44 44
D73852AE send 1880 482 130 76
1D79CAD1 company_end 2088 498 44 44
B4921FBA old_number 728 650 120 72
2A9E6B0A third_company 888 650 150 72
0DA99902 granted 1060 664 44 44
9A553255 delete 1160 718 138 72
4ED76348 delete_end 1348 732 44 44
51BCFD18 debt_end 483 678 44 44
EC14C117 store 1420 650 124 72
9D265428 consent 1595 650 124 72
71D2A247 receive 1908 280 44 44
D80682C2 activate 2070 266 130 72
BB48C585 customer_end 2258 280 44 44
"""
LAYOUT = {p:(a,*map(int,xy)) for p,a,*xy in (line.split() for line in LAYOUT_TEXT.strip().splitlines())}
BREAKS = {
    "Request personal data":["Request","personal data"], "Ask portability":["Ask","portability"],
    "Assign new number":["Assign","new number"], "Sign contract":["Sign contract"],
    "Request payment":["Request","payment"], "Send SIM card":["Send","SIM card"],
    "Activate SIM card":["Activate","SIM card"], "Ask old number":["Ask","old number"],
    "Ask portability third company":["Ask portability","third company"],
    "Delete personal data":["Delete","personal data"], "Store Data":["Store Data"], "Ask for consent":["Ask for","consent"],
}
def esc(value):
    return html.escape(str(value),quote=True)

def local(e):
    return e.tag.rsplit("}",1)[-1]

class Svg:
    def __init__(self):
        self.parts=[]
    def group(self,identifier,kind,title=None,extra=""):
        self.parts.append(f'<g id="{esc(identifier)}" data-kind="{kind}" {extra}>')
        if title:
            self.parts.append(f"<title>{esc(title)}</title>")
    def end(self):
        self.parts.append("</g>")
    def rect(self,x,y,w,h,fill="white",stroke=INK,sw=1.8,rx=0,dash=None):
        ds=f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{ds}/>')
    def circle(self,x,y,r,fill="white",stroke=INK,sw=1.8):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
    def line(self,points,color=INK,sw=1.7,dash=None,arrow="sequence"):
        pts=" ".join(f"{x},{y}" for x,y in points)
        ds=f' stroke-dasharray="{dash}"' if dash else ""
        ma=f' marker-end="url(#{arrow})"' if arrow else ""
        self.parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linejoin="round"{ds}{ma}/>')
    def text(self,x,y,value,size=22,color=INK,bold=False,anchor="start",rotate=None):
        tr=f' transform="rotate({rotate} {x} {y})"' if rotate is not None else ""
        weight="bold" if bold else "normal"
        self.parts.append(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}"{tr}>{esc(value)}</text>')
    def lines(self,x,y,values,size=22,lh=25):
        top=y-(len(values)-1)*lh/2+size*.34
        for i,value in enumerate(values):
            self.text(x,top+i*lh,value,size=size,anchor="middle")

def ports(box):
    _,x,y,w,h=box
    return {"left":(x,y+h/2),"right":(x+w,y+h/2),"top":(x+w/2,y),"bottom":(x+w/2,y+h)}

def route(source,target,boxes):
    s,t=ports(boxes[source]),ports(boxes[target])
    paths={
        ("debt","debt_end"):[s["bottom"],t["top"]],
        ("port_choice","old_number"):[s["bottom"],(784,615),(788,615),t["top"]],
        ("granted","merge"):[s["top"],t["bottom"]],
        ("granted","delete"):[s["right"],(1125,686),(1125,754),t["left"]],
        ("split","store"):[s["bottom"],(1333,686),t["left"]],
        ("consent","join"):[s["right"],(1790,686),t["bottom"]],
    }
    return paths.get((source,target),[s["right"],t["left"]])

def callout(svg,assessment,rid,box,title,body):
    x,y,w,h=box
    supported=assessment["found_corresponding_problem"]
    color,fill=COLORS[rid]
    svg.group("annotation-"+rid,"annotation",extra=f'data-correspondence="{str(supported).lower()}"')
    svg.rect(x,y,w,h,fill=fill,stroke=color,sw=2,rx=18,dash=None if supported else "7 5")
    svg.text(x+18,y+35,f"{rid}/v2 | {title}",size=27,bold=True)
    for i,line in enumerate(body):
        svg.text(x+18,y+72+i*31,line,size=23)
    svg.end()

def render(cap,source_root):
    svg=Svg()
    p=cap["process_facts"]
    originals={e.get("id"):e for e in source_root.iter() if e.get("id")}
    nodes={n["id"]:n for field in ("activities","events","gateways") for n in p[field]}
    boxes,aliases,by_alias={},{},{}
    for nid in nodes:
        prefix=nid.removeprefix("sid-").split("-")[0]
        box=LAYOUT[prefix]
        boxes[box[0]],aliases[nid],by_alias[box[0]]=box,box[0],nid
    if len(nodes)!=len(LAYOUT):
        raise ValueError("Every saved Process Record node needs a page position")
    check=lambda rid,kind:cap["rules"][rid]["sides"]["C"]["checks"][kind]["status"]
    assessments={c["rule_id"]:c["groups"]["C"] for c in cap["comparison"]}
    match=lambda rid:"supported" if assessments[rid]["found_corresponding_problem"] else "not established"
    svg.rect(0,0,W,H,stroke="none")
    for name,y,height in (("Customer",250,125),("Phone company",430,410),("Another phone company",880,80)):
        svg.group("participant-"+name.replace(" ","-"),"participant",name)
        svg.rect(55,y,2290,height,sw=2)
        svg.line([(120,y),(120,y+height)],sw=1.8,arrow=None)
        if name=="Another phone company":
            svg.lines(87.5,y+height/2,["Another","phone","company"],size=16,lh=20)
        else:
            svg.text(95,y+height/2,name,size=24,rotate=-90,anchor="middle")
        svg.end()
    for rid,box in (("r9",(234,462,240,160)),("r10",(2054,251,162,103)),("r11",(1403,632,338,110)),("r13",(479,478,56,85))):
        svg.group("region-"+rid,"annotation-region")
        svg.rect(*box,fill="none",stroke=COLORS[rid][0],sw=2,dash="8 6")
        svg.end()
    drawn_flows=[]
    for f in p["sequence_flows"]:
        s,t=aliases[f["source_ref"]],aliases[f["target_ref"]]
        svg.group(f["id"],"sequence-flow",f.get("name"),extra=f'data-source="{f["source_ref"]}" data-target="{f["target_ref"]}"')
        svg.line(route(s,t,boxes))
        label=f.get("name") or ""
        if label:
            if "debt" in label.lower():
                svg.rect(528,446,133,28,stroke="none")
                svg.text(594.5,467,label,size=21,color=COLORS["r13"][0],anchor="middle")
            elif label=="Not requested":
                svg.lines(839,480,["Not","requested"],size=17,lh=20)
            elif label=="Requested":
                svg.text(798,603,label,size=18)
            elif label=="Granted":
                svg.text(1094,610,label,size=18)
            else:
                raise ValueError(f"New source flow label needs a page position: {label}")
        svg.end()
        drawn_flows.append(f["id"])
    participants={e.get("id"):e.get("name") for e in source_root.iter() if local(e)=="participant"}
    messages=[e for e in source_root.iter() if local(e)=="messageFlow"]
    pairs={(e.get("sourceRef"),e.get("targetRef")) for e in messages}
    for f in messages:
        s,t=f.get("sourceRef"),f.get("targetRef")
        node=s if s in aliases else t
        pool=t if t in participants else s
        if node not in aliases or pool not in participants:
            raise ValueError("Message flow needs an explicit source-preserving route")
        lower=participants[pool]=="Another phone company"
        port=ports(boxes[aliases[node]])["bottom" if lower else "top"]
        offset=(9 if s==node else -9) if (t,s) in pairs else 0
        np=(port[0]+offset,port[1])
        pp=(np[0],880 if lower else 375)
        points=[np,pp] if s==node else [pp,np]
        svg.group(f.get("id"),"message-flow",f.get("name"),extra=f'data-source="{s}" data-target="{t}"')
        svg.line(points,color="#515151",sw=1.25,dash="5 4",arrow="message")
        svg.circle(*points[0],2.6,sw=1.1)
        name=f.get("name") or ""
        if name:
            if aliases[node]=="request":
                svg.text(np[0]-12,408,name,size=17,anchor="end")
            elif aliases[node]=="data":
                svg.text(np[0]-12,402,"Send personal",size=17,anchor="end")
                svg.text(np[0]-12,422,"data",size=17,anchor="end")
            else:
                svg.text(np[0]+12,410,name,size=17)
        svg.end()
    for nid,item in nodes.items():
        alias=aliases[nid]
        _,x,y,w,h=boxes[alias]
        cx,cy=x+w/2,y+h/2
        typ=local(originals[nid])
        svg.group(nid,"process-node",item.get("name") or typ,extra=f'data-bpmn-type="{typ}"')
        if typ.endswith("Gateway"):
            svg.parts.append(f'<polygon points="{cx},{y} {x+w},{cy} {cx},{y+h} {x},{cy}" fill="white" stroke="{INK}" stroke-width="1.8"/>')
            if typ=="parallelGateway":
                svg.line([(cx-10,cy),(cx+10,cy)],sw=3,arrow=None)
                svg.line([(cx,cy-10),(cx,cy+10)],sw=3,arrow=None)
            else:
                svg.line([(cx-8,cy-8),(cx+8,cy+8)],sw=3,arrow=None)
                svg.line([(cx-8,cy+8),(cx+8,cy-8)],sw=3,arrow=None)
        elif typ.endswith("Event"):
            svg.circle(cx,cy,21,sw=4 if typ=="endEvent" else 1.8)
            if typ=="intermediateCatchEvent":
                svg.circle(cx,cy,17.2,sw=1.1)
            if any(local(e)=="messageEventDefinition" for e in originals[nid]):
                svg.rect(cx-12,cy-8,24,16,sw=1.2)
                svg.line([(cx-12,cy-8),(cx,cy+1),(cx+12,cy-8)],sw=1.1,arrow=None)
            labels={"start":["New client","acquired"],"data":["Personal data","received"],
                    "payment":["Payment","received"],"receive":["Receive","SIM card"]}.get(alias)
            if labels:
                svg.lines(cx-12 if alias=="data" else cx,cy+(66 if alias=="data" else 48),labels,size=19,lh=22)
        else:
            svg.rect(x,y,w,h,rx=12,sw=1.7)
            svg.lines(cx,cy,BREAKS[item["name"]],size=22,lh=25)
        svg.end()
    svg.group("missing-activity-r9","annotation-placeholder","缺失活动（模型中不存在）")
    svg.rect(252,632,215,72,rx=9,stroke=COLORS["r9"][0],fill=COLORS["r9"][1],sw=1.8,dash="7 5")
    svg.text(359.5,658,"Missing activity",size=22,bold=True,color=COLORS["r9"][0],anchor="middle")
    svg.text(359.5,686,"Verify personal data",size=21,anchor="middle")
    svg.line([(359.5,622),(359.5,632)],color=COLORS["r9"][0],sw=1.5,dash="4 4",arrow=None)
    svg.end()
    leaders={
        "r9":[(390,204),(390,229),(215,229),(215,490),(234,490)],
        "r13":[(920,204),(920,227),(505,227),(505,478)],
        "r10":[(2135,204),(2135,251)],
        "r11":[(1800,1000),(1800,980),(1752,980),(1752,755),(1670,755),(1670,742)],
        "r8":[(440,1000),(440,853)],
    }
    svg.group("scope-r8","annotation-scope")
    svg.line([(65,846),(65,853),(2335,853),(2335,846)],color=COLORS["r8"][0],sw=1.5,arrow=None)
    svg.end()
    for rid,points in leaders.items():
        svg.group("leader-"+rid,"annotation-leader")
        svg.line(points,color=COLORS[rid][0],sw=1.6,arrow="arrow-"+rid)
        svg.end()
    callout(svg,assessments["r9"],"r9",(130,32,520,172),"Missing action",[
        "Expected: verify personal-data correctness.",f'C alarm: {check("r9","missing_action")}.',
        f'Reference correspondence: {match("r9")}.'])
    debt_label=next(f["name"] for f in p["sequence_flows"] if "debt" in (f.get("name") or "").lower())
    callout(svg,assessments["r13"],"r13",(705,32,620,172),"Debt threshold",[
        f"Rule: debt > 50 EUR; model: {debt_label}.",
        f'C condition / constraint: {check("r13","required_condition_not_enforced")} / {check("r13","constraint_violated")}.',
        f'Reference correspondence: {match("r13")}.'])
    owner=", ".join(nodes[by_alias["activate"]]["lanes"])
    callout(svg,assessments["r10"],"r10",(1700,32,620,172),"Incorrect actor",[
        f"Required: Phone company; actual: {owner}.",f'C alarm: {check("r10","incorrect_actor")}.',
        f'Reference correspondence: {match("r10")}.'])
    callout(svg,assessments["r8"],"r8",(140,1000,710,172),"Process timeout",[
        "Rule: terminate the process after 30 days.",
        f'C alarms: {len(assessments["r8"]["machine_alarms"])}; reference correspondence: {match("r8")}.',
        "Scope: the entire phone-company process."])
    callout(svg,assessments["r11"],"r11",(1330,1000,990,172),"Out-of-order execution",[
        "Required: consent before personal-data retrieval.",
        f'C order: {check("r11","out_of_order")}; missing-action alarm: {check("r11","missing_action")}.',
        f'Reference correspondence: {match("r11")}.'])
    svg.group("figure-caption","caption")
    svg.text(55,1207,"Black arrows: sequence flow. Dashed black arrows: messages. Colored outlines and leaders: annotations. Data associations omitted.",size=21,color="#555555")
    summary=", ".join(f'{g}={cap["reference_assessment_summary"][g]["found_with_reference_evidence"]}' for g in "ABC")
    svg.text(55,1238,f"Group C shown (REPAIR-V2). Supported reference issues: {summary} of five rules. Development case; full A/B/C results in the accompanying table.",size=21,color="#555555")
    svg.end()
    metadata={"source_capsule_sha256":hashlib.sha256(CAPSULE.read_bytes()).hexdigest(),
              "claim_scope":cap["claim_scope"],"display_group":"C","layout_only":True,
              "data_associations_omitted":True,"process_nodes":list(nodes),"sequence_flows":drawn_flows,
              "message_flows":[e.get("id") for e in messages],
              "repair_comparison_in_accompanying_report":["C_original","C_repaired"]}
    defs=[
        '<marker id="sequence" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#202020"/></marker>',
        '<marker id="message" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M1 1 L9 5 L1 9" fill="white" stroke="#515151" stroke-width="1.2"/></marker>']
    for rid,(color,_) in COLORS.items():
        defs.append(f'<marker id="arrow-{rid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 1 L10 5 L0 9 Z" fill="{color}"/></marker>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img">\n'
            '<title>SIM onboarding: process annotations and development-case results</title>\n'
            '<desc>Source-preserving control-flow diagram styled for a research paper. Only r9 and r10 have supported reference correspondence. Other callouts describe unverified alarms or undetermined checks. The missing-activity box is an annotation, not a source process node.</desc>\n'
            f'<metadata>{esc(json.dumps(metadata,ensure_ascii=False))}</metadata>\n'
            '<defs>'+"".join(defs)+'</defs>\n'+"\n".join(svg.parts)+'\n</svg>\n')

def main():
    cap=json.loads(CAPSULE.read_text(encoding="utf-8"))
    source=cap["plan"]["inputs"]["bpmn"]
    payload=(ROOT.parent/source["path"]).read_bytes()
    if hashlib.sha256(payload).hexdigest()!=source["sha256"]:
        raise ValueError("Original BPMN does not match the saved run")
    OUT.write_text(render(cap,ET.fromstring(payload)),encoding="utf-8",newline="\n")
    print(f"Rendered {OUT.name}: {W} x {H}; 26 process nodes; 26 sequence flows.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
