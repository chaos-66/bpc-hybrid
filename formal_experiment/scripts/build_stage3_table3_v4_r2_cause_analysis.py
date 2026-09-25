# -*- coding: utf-8 -*-
"""Build the R2 cause-analysis and corrected candidate evidence artifacts.

This is an offline diagnostic script.  It is run only after the independent R2
evaluation has been written and bound; it never feeds detector inputs.  It
reads D1 raw responses, R1/R2 frozen outputs, source regulation text, and BPMN
models to localize the five requested evidence groups.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import spacy  # noqa: E402

from bpc_hybrid.h1_transport import decode_chat_completion_envelope  # noqa: E402
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file  # noqa: E402
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402

RULE_IDS = ["article13p3", "article14p4", "article18p3", "article35p1", "article36p1"]


def load(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def read_repo(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    stage2 = load("data/development/stage3_reconstruction_v4/stage2_input.json")
    texts: dict[str, str] = {}
    samples: dict[str, dict[str, Any]] = {}
    for rule in stage2["rules"]:
        for sent in rule["sentences"]:
            texts[rule["rule_id"]] = sent["approved_text_en"]
            samples[rule["rule_id"]] = sent
    r2_report = load("outputs/reports/stage3_table3_v4_r2.json")
    r1_rr = load("outputs/development/stage3_table3_v4_r1/rule_records.json")
    r2_rr = load("outputs/development/stage3_table3_v4_r2/rule_records.json")
    d1 = load("data/predictions/stage3_v4_d1_frozen_v1/predictions.json")
    env_by_sample = {row["sample_id"]: row for row in d1["records"]}

    # ---------- requested evidence 1: actor loss in article13p3/14p4 ----------
    actor_loss: dict[str, Any] = {}
    for rid in ("article13p3", "article14p4"):
        sample_id = samples[rid]["sample_id"]
        env = env_by_sample[sample_id]
        raw_env = json.loads((ROOT / env["raw_response_path"]).read_text(encoding="utf-8"))
        body = base64.b64decode(raw_env["raw_response_body_base64"])
        raw_obj = json.loads(decode_chat_completion_envelope(body, raw_env["content_type"])["content"])
        raw_clause = raw_obj["clauses"][0]
        can_clause = ((env.get("record") or {}).get("clauses") or [{}])[0]
        source = texts[rid]
        raw_actors = raw_clause.get("actors") or []
        can_actors = can_clause.get("actors") or []
        raw_maps = raw_clause.get("actor_action_map") or []
        can_maps = can_clause.get("actor_action_map") or []
        raw_actor = raw_actors[0] if raw_actors else None
        raw_actor_evidence = None
        if raw_actor:
            rs, re_ = raw_actor.get("start"), raw_actor.get("end")
            rtext = raw_actor.get("text")
            source_at_raw = source[rs:re_] if isinstance(rs, int) and isinstance(re_, int) else None
            occurrences = [i for i in range(len(source)) if source.startswith(rtext, i)] if isinstance(rtext, str) else []
            if source_at_raw == rtext:
                outcome = "unchanged"
            elif not occurrences:
                outcome = "zero_occurrence"
            elif len(occurrences) > 1:
                outcome = "ambiguous_occurrence"
            else:
                outcome = "reanchored"
            raw_actor_evidence = {
                "id": raw_actor.get("id"),
                "normalized": raw_actor.get("normalized"),
                "text": rtext,
                "raw_start": rs,
                "raw_end": re_,
                "source_at_raw_offsets": source_at_raw,
                "source_occurrences": occurrences,
                "reanchor_outcome": outcome,
            }
        actor_loss[rid] = {
            "rule_id": rid,
            "sample_id": sample_id,
            "source_text_length": len(source),
            "canonicalizer_audit": env.get("canonicalizer_audit"),
            "raw_actor": raw_actor_evidence,
            "raw_actor_action_map": raw_maps,
            "canonical_actors": can_actors,
            "canonical_actor_action_map": can_maps,
            "raw_actions": [
                {"id": a.get("id"), "text": a.get("text"), "start": a.get("start"), "end": a.get("end")}
                for a in raw_clause.get("actions") or []
            ],
            "canonical_actions": [
                {"id": a.get("id"), "text": a.get("text"), "start": a.get("start"), "end": a.get("end")}
                for a in can_clause.get("actions") or []
            ],
            "explanation": (
                "Raw actor text occurs twice in the source and the raw offsets do not match it. "
                "The canonicalizer refuses the ambiguous occurrence, drops the actor span, and then "
                "drops actor_action_map edges that reference it. No actor was hand-added."
            ),
        }

    # ---------- requested evidence 3: relation generated vs endpoint mapping ----------
    relation_chain: dict[str, Any] = {}
    for method in ("sun", "ours"):
        relation_chain[method] = {}
        for rid in RULE_IDS:
            r1_rec = r1_rr[method]["records"][rid]
            r2_rec = r2_rr[method]["records"][rid]
            relation_chain[method][rid] = {
                "r1_order_relations": r1_rec.get("order_relations") or [],
                "r2_order_relations": r2_rec.get("order_relations") or [],
                "r2_projection_status": (r2_rec.get("order_relation_projection") or {}).get("status"),
                "r2_projection": r2_rec.get("order_relation_projection"),
            }

    cat_by_rule: dict[str, dict[str, int]] = {}
    examples: dict[tuple[str, str], dict[str, Any]] = {}
    for rec in r2_report["diagnostics"]["order_failure_category_records"]:
        key = (rec["method"], rec["rule_id"])
        cat_by_rule.setdefault(f"{key[0]}/{key[1]}", {})
        cat_by_rule[f"{key[0]}/{key[1]}"][rec["failure_category"]] = cat_by_rule[f"{key[0]}/{key[1]}"].get(rec["failure_category"], 0) + 1
        if key not in examples and rec.get("order_diagnostic"):
            examples[key] = rec

    def case_record(method: str, rid: str, case_id: str) -> dict[str, Any] | None:
        for rec in r2_report["diagnostics"]["order_failure_category_records"]:
            if rec["method"] == method and rec["rule_id"] == rid and rec["case_id"] == case_id:
                return rec
        return None

    # ---------- requested evidence 2: concrete similarity inputs ----------
    known: list[dict[str, Any]] = []
    for method in ("sun", "ours"):
        for rid, case_id in (
            ("article35p1", "case_06bacb820524"),
            ("article36p1", "case_7dc164f81677"),
            ("article36p1", "case_06bacb820524"),
        ):
            rec = case_record(method, rid, case_id)
            if not rec:
                continue
            ev = (rec.get("order_diagnostic") or {}).get("relation_evidence") or []
            if not ev:
                continue
            e = ev[0]
            known.append({
                "method": method,
                "rule_id": rid,
                "case_id": case_id,
                "constraint": e["constraint"],
                "before": e["before"],
                "after": e["after"],
                "denominator": rec.get("denominator"),
                "failure_category": rec.get("failure_category"),
                "both_endpoints_above_gamma": e.get("both_endpoints_mapped"),
            })

    endpoint_summary: dict[str, Any] = {}
    for method in ("sun", "ours"):
        endpoint_summary[method] = {}
        for rid in RULE_IDS:
            rels = relation_chain[method][rid]["r2_order_relations"]
            ex = examples.get((method, rid))
            endpoint_summary[method][rid] = {
                "relation_generated": bool(rels),
                "r1_relation": relation_chain[method][rid]["r1_order_relations"],
                "r2_relation": rels,
                "r2_failure_categories": cat_by_rule.get(f"{method}/{rid}", {}),
                "example": None if not ex else {
                    "case_id": ex.get("case_id"),
                    "failure_category": ex.get("failure_category"),
                    "denominator": ex.get("denominator"),
                    "relation_evidence": (ex.get("order_diagnostic") or {}).get("relation_evidence"),
                },
            }

    # ---------- requested evidence 4: action-representation contract ----------
    action_contract = {
        "paper_source": "references/papers/extracted/sun_2024_full_text.txt",
        "paper_line_ranges": {
            "Definition4": "approx. 523-548",
            "Definition5": "approx. 550-560",
            "Definition6": "approx. 562-585",
            "Definition7": "approx. 587-615",
        },
        "process_side": {
            "actions": "SunProcessModel.actions = full activity label and event name from the BPMN Process Record.",
            "action_match": "SunScorer._best_action_match compares rule action text to each full activity/event label using lemmatized spaCy text_pair.",
            "actors": "SunProcessModel.actors = non-empty pool names plus non-empty lane names.",
            "business_objects": "SunProcessModel.business_objects = deterministic head noun extracted from each activity label.",
            "reachability": "Fm from BPMN control_flow.reachable_pairs; is_reachable checks membership.",
        },
        "rule_side": {
            "actions": "canonical Stage-2 predicted action spans become rule-side actions.",
            "actors": "canonical Stage-2 predicted actor spans become rule-side actor candidates.",
            "order_relations": "native record.order_relations are preferred; derived supplements use temporal_projection_v3 under predicted condition/constraint spans.",
            "conditions_time_objects": "conditions/constraints/exceptions are not separate scorers; they bound/reject projected endpoints and are included only when inside an endpoint text.",
        },
        "specified_by_sun": [
            "Definition 4: matching uses rule actions Dr,m and rule actors/business objects Or,m against process actions and process actors/business objects.",
            "Definition 5: denominator is |Ar| (rule actions); missing action uses sim < gamma.",
            "Definition 6: existential/min condition over Rr,m,gamma and Cr,m,gamma; it is not a process-wide max and business objects remain candidates.",
            "Definition 7: denominator is Ur,m,gamma where both endpoints map with sim > gamma; satisfied requires forward reachability and not backward reachability.",
        ],
        "project_reconstruction": [
            "The exact action text used by SunScorer is the full activity/event label; no separate action decomposition is applied to the process label.",
            "Business objects are extracted from activity labels by a deterministic spaCy dobj/pobj rule; this is a project approximation to the paper business-object set.",
            "The temporal marker projection v3 is a shared Sun/Ours reconstruction supplement, not a Sun paper algorithm; derived endpoints may come from predicted constraints.",
            "Conditions, times, and exception text are not independent scored dimensions.",
        ],
        "actor_existential_policy": "The candidate set for Definition 6 is actors plus business_objects. The implementation keeps the paper existential/min condition; it must not replace min with max or delete business objects to reduce errors.",
    }

    # ---------- requested evidence 5: actor candidate sets ----------
    nlp = spacy.load("en_core_web_sm")
    contract = load_stage1_contract(ROOT / "configs/stage1_structural_s11_s14.json")
    view = load("data/development/stage3_reconstruction_v4/inference_view.json")
    actor_candidates: list[dict[str, Any]] = []
    for item in sorted(view["items"], key=lambda x: str(x["case_id"])):
        rec = parse_bpmn_file(ROOT / item["bpmn_path"], contract=contract)
        model = SunProcessModel(str(item["process_id"]), rec, nlp)
        actor_candidates.append({
            "case_id": item["case_id"],
            "bpmn_path": item["bpmn_path"],
            "process_id": item["process_id"],
            "actors": list(model.actors),
            "business_objects": list(model.business_objects),
            "action_labels": [a["name"] for a in model.actions],
            "candidate_set_for_def6": list(model.actors) + [b["object"] for b in model.business_objects],
            "existential_policy": "actors + business_objects retained; no max substitution and no business-object deletion",
        })

    # ---------- subsequent data correction: existing candidates only ----------
    r1_candidates = load("outputs/reports/stage3_temporal_scope_candidates_r1.json")
    cand = {c["candidate_id"]: c for c in r1_candidates["candidates"]}
    art43_path = "references/winter_2020_model_check/model_check/input/regulations/gdpr/article43.txt"
    art43_text = read_repo(art43_path)
    art43_end = 383  # includes final period, excludes following space + Member States obligations
    art43_excerpt = art43_text[:art43_end]
    c43 = json.loads(json.dumps(cand["article43_1"]))
    c43["source"]["char_span"] = [0, art43_end]
    c43["source"]["text"] = art43_excerpt
    c43["source"]["text_sha256"] = sha_text(art43_excerpt)
    c43["source"]["notes"] = "R2 correction: first sentence only; [0,869) included following Member States accreditation obligations."
    c43["source_extraction"] = {
        "kind": "single_exact_source_substring",
        "not_concatenated": True,
        "previous_r1_char_span": [0, 869],
        "correction_reason": "The task requires the first sentence; [0,869) incorrectly carried Member States obligations.",
        "member_states_obligation_excluded": True,
    }
    c43["provision"] = "Article43(1) first sentence"
    c43["conditions_time_limits"] = {
        "conditions": ["after informing the supervisory authority where necessary"],
        "time_limits": [],
        "exceptions": ["Without prejudice to Articles 57 and 58 competences; later paragraphs impose accreditation requirements."],
    }
    c43["status"] = "candidate_not_benchmark"

    c14 = json.loads(json.dumps(cand["article14_3_a"]))
    c14["source_extraction"] = {
        "kind": "single_exact_source_substring",
        "not_concatenated": True,
        "source_is_article14_3_lead_in_plus_point_a_as_formatted_in_source": True,
        "notes": "Exact source[2469:2731); it is the Article 14(3) lead-in and point (a) as written in the source file, not a project-assembled sentence.",
    }
    c14["conditions_time_limits"] = {
        "conditions": ["personal data not obtained from the data subject", "information referred to in paragraphs 1 and 2"],
        "time_limits": ["within a reasonable period after obtaining the personal data", "at the latest within one month", "having regard to the specific circumstances"],
        "exceptions": ["Article 14(5)(a)-(c) limits paragraphs 1-4, including (3)(a); this is an external applicability boundary."],
        "exception_boundary_preserved": True,
    }

    c33 = json.loads(json.dumps(cand["article33_2"]))
    c33["source_extraction"] = {
        "kind": "single_exact_source_substring",
        "not_concatenated": True,
        "notes": "Exact source[503:612); the without-undue-delay limitation is retained.",
    }
    c33["conditions_time_limits"] = {
        "conditions": ["processor has become aware of a personal data breach"],
        "time_limits": ["without undue delay"],
        "exceptions": ["No explicit exception in Article 33(2); paragraph 1 72-hour context and Article 34 boundary remain separate."],
        "limitation_preserved": True,
    }

    candidates_r2 = {
        "schema_version": "stage3_temporal_scope_candidates_r2@1.0.0",
        "status": "candidate_not_benchmark",
        "purpose": "R2 correction of existing after/temporal candidates only; no benchmark addition, no extraction, no API, no F1 selection.",
        "governance": {
            "added_to_current_benchmark": False,
            "used_for_api": False,
            "used_for_f1": False,
            "requires_new_input_design": True,
        },
        "candidates": [c14, c33, c43],
    }

    analysis = {
        "schema_version": "stage3_table3_v4_r2_cause_analysis@1.0.0",
        "status": "diagnostic_only_not_acceptance",
        "reference_boundary": "Reference is AI-constructed construction_reference, is_gold=false, human_adjudicated=false; metrics are given applicable-scope checking only.",
        "r2_metrics_summary": r2_report["summary"],
        "cause_categories": {
            "upstream_extraction_error": ["article13p3", "article14p4 (Ours actor text/offsets; action/exception boundary in Sun)"],
            "postprocessing_loss": ["article13p3", "article14p4 (Ours actor_action_map dropped with the dropped actor)"],
            "representation_or_interface": ["article13p3", "article14p4 (main-action/exception boundary differs between Sun and Ours records)"],
            "mapping_failure": ["article18p3", "article35p1", "article36p1 (endpoint mapping/similarity below gamma)"],
            "native_method_coverage_deficit": ["Winter: no native before/prior-to rule-side flow in this five-clause scope"],
            "reference_scope_limitation": ["Five-rule scoped reference; not full GDPR F1; reference is AI-constructed"],
        },
        "actor_loss_evidence": actor_loss,
        "order_relation_chain": relation_chain,
        "endpoint_failure_summary": endpoint_summary,
        "r2_failure_categories_by_method_rule": cat_by_rule,
        "known_similarity_evidence": known,
        "action_representation_contract": action_contract,
        "actor_candidate_sets": actor_candidates,
        "r1_r2_change_evidence": {
            "article18p3": {
                "sun_r1_relation": relation_chain["sun"]["article18p3"]["r1_order_relations"],
                "sun_r2_relation": relation_chain["sun"]["article18p3"]["r2_order_relations"],
                "ours_r1_relation": relation_chain["ours"]["article18p3"]["r1_order_relations"],
                "ours_r2_relation": relation_chain["ours"]["article18p3"]["r2_order_relations"],
                "reason": "R1 v2 scanned an extra advcl/ccomp predicate and selected lifted; R2 v3 finds no legal verbal complement and uses the bounded nominal branch, yielding the restriction of processing. The relation is still generated.",
            },
            "article13p3_article14p4": {
                "r1_reason": "no_rule_order_endpoints",
                "r2_reason_sun": "projection_rejected_range",
                "r2_reason_ours": "projection_rejected_syntax",
                "reason": "The relation is not generated in either version; R2 separates the rejection causes instead of returning a denominator-zero generic reason.",
            },
            "article35p1_article36p1": {
                "relation_generated_r1": True,
                "relation_generated_r2": True,
                "reason": "Both versions generate the derived relation, but R2 records endpoint_similarity_below_gamma instead of grouping all denominator-zero cells under no_rule_order_endpoints.",
            },
        },
        "candidate_correction_r2": candidates_r2,
        "unresolved_gaps": [
            "No order relation reaches denominator > 0 for Sun/Ours/Winter on the five frozen rules; all scored out_of_order cells are unknown.",
            "The five-rule reference remains applicable-scope checking, not full GDPR F1.",
            "Article13p3/article14p4 Ours actor loss is not repaired by hand; a future upstream extraction fix would be a new authorized experiment.",
            "The three after/temporal candidates are corrections only and are not benchmark inputs.",
        ],
    }

    out_json = ROOT / "outputs/reports/stage3_table3_v4_r2_cause_analysis.json"
    out_md = ROOT / "outputs/reports/stage3_table3_v4_r2_cause_analysis.md"
    cand_json = ROOT / "outputs/reports/stage3_temporal_scope_candidates_r2.json"
    cand_md = ROOT / "outputs/reports/stage3_temporal_scope_candidates_r2.md"
    write_json(out_json, analysis)
    write_json(cand_json, candidates_r2)

    md = [
        "# S3-TABLE3-V4-R2 cause analysis (diagnostic)",
        "",
        "Reference is AI-constructed `is_gold=false`; this is applicable-scope checking, not full GDPR F1.",
        "",
        "## Actor loss in Ours article13p3/article14p4",
        "",
    ]
    for rid, ev in actor_loss.items():
        raw = ev["raw_actor"] or {}
        md.append(f"- `{rid}`: raw actor text `{raw.get('text')}` at raw offsets {raw.get('raw_start')}..{raw.get('raw_end')}; "
                  f"source_at_raw={raw.get('source_at_raw_offsets')!r}; source occurrences {raw.get('source_occurrences')}; "
                  f"reanchor outcome `{raw.get('reanchor_outcome')}`. Canonical actors={ev['canonical_actors']}, "
                  f"actor_action_map={ev['canonical_actor_action_map']}.")
    md += ["", "## Order relation vs endpoint mapping", ""]
    for method in ("sun", "ours"):
        for rid in RULE_IDS:
            item = endpoint_summary[method][rid]
            md.append(f"- `{method}/{rid}`: relation_generated={item['relation_generated']}; "
                      f"r1={item['r1_relation']}; r2={item['r2_relation']}; categories={item['r2_failure_categories']}.")
    md += ["", "## Concrete similarity inputs", ""]
    for row in known:
        b, a = row["before"], row["after"]
        md.append(f"- `{row['method']}/{row['rule_id']}/{row['case_id']}`: "
                  f"before=`{b['rule_endpoint_text']}` -> task `{b['candidate_task_text']}` sim={b['similarity']:.4f} "
                  f"(above_gamma={b['similarity_above_gamma']}); after=`{a['rule_endpoint_text']}` -> task "
                  f"`{a['candidate_task_text']}` sim={a['similarity']:.4f} (above_gamma={a['similarity_above_gamma']}); "
                  f"denominator={row['denominator']}, category={row['failure_category']}.")
    md += ["", "## Actor candidate sets", ""]
    for row in actor_candidates:
        md.append(f"- `{row['case_id']}` actors={row['actors']}; business_objects={row['business_objects']}.")
    md += ["", "## R2 candidate corrections", ""]
    for c in candidates_r2["candidates"]:
        md.append(f"- `{c['candidate_id']}` source span {c['source']['char_span']}, SHA {c['source']['text_sha256']}; status={c['status']}.")
    write_text(out_md, "\n".join(md))

    cand_md_lines = [
        "# Stage 3 temporal-scope candidate corrections R2",
        "",
        "These are `candidate_not_benchmark` source records only; they are not in the 50-unit evaluation and no extraction or API was run.",
        "",
    ]
    for c in candidates_r2["candidates"]:
        cand_md_lines.append(f"## {c['provision']}")
        cand_md_lines.append("")
        cand_md_lines.append(f"- source: `{c['source']['path']}` span={c['source']['char_span']} sha256={c['source']['text_sha256']}")
        cand_md_lines.append(f"- exact excerpt: {c['source']['text']}")
        cand_md_lines.append(f"- limits: {c.get('conditions_time_limits')}")
        cand_md_lines.append("")
    write_text(cand_md, "\n".join(cand_md_lines))
    print("wrote", out_json)
    print("wrote", out_md)
    print("wrote", cand_json)
    print("wrote", cand_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
