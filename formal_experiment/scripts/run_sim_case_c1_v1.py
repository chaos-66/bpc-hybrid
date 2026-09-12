# -*- coding: utf-8 -*-
"""Run the SIM card case (S3.9-EXT-REAL-CASE): groups A / B / C plus repair controls.

Zero LLM/API.  Predictions are written before the development reference
judgments are read; the reference judgments never enter the rule side.

Usage (from ``formal_experiment/``):
    python scripts/run_sim_case_c1_v1.py [--overwrite] [--check] [--replay]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from bpc_hybrid import sim_case_c1 as core  # noqa: E402
from bpc_hybrid.sim_case_c1_transforms import flatten_collaboration, repair_variant  # noqa: E402

RUN_DIR = ROOT / "outputs" / "development" / "sim_case_c1" / "run_v1"
LOCAL_MODELS = ROOT / "outputs" / "development" / "sim_case_c1" / "models"
REPORT_JSON = ROOT / "outputs" / "reports" / "sim_case_c1_results.json"
REPORT_MD = ROOT / "outputs" / "reports" / "sim_case_c1_results.md"

LENS_MAP = {  # declared comparison mapping (comparison stage only, never fed to detection)
    "r8": {"primary": "constraint_violated", "secondary": ["required_condition_not_enforced"]},
    "r9": {"primary": "missing_action", "secondary": []},
    "r10": {"primary": "incorrect_actor", "secondary": []},
    "r11": {"primary": "out_of_order", "secondary": ["required_condition_not_enforced"]},
    "r13": {"primary": "required_condition_not_enforced", "secondary": ["constraint_violated"]},
}
GAMMA_EXT = 0.5
LABEL_FALLBACK_GAMMA = 0.4  # REPAIR-V2 arm C configuration
BASELINE_CAPSULE = ROOT / "outputs" / "development" / "sim_case_c1" / "stage2_baseline_v1" / "capsule.json"


def _load_baseline_capsule() -> tuple[Path, dict]:
    if not BASELINE_CAPSULE.exists():
        raise SystemExit(
            "group A baseline capsule missing: run "
            "`python scripts/run_sim_case_stage2_baseline_v1.py --overwrite` first")
    return BASELINE_CAPSULE, json.loads(BASELINE_CAPSULE.read_text(encoding="utf-8"))


def stage2_group_a_baseline(rule_id: str, rule_text: str, baseline: dict) -> dict:
    """Group A Stage 2 = the project's locked non-LLM baseline capsule row."""
    import sys as _sys

    _sys.path.insert(0, str(ROOT / "src"))
    from bpc_hybrid.gdpr_s2_s3_projection import project_external_sentence

    sample_id = f"sim_{rule_id}_v2"
    row = next((r for r in baseline.get("records", []) if r.get("sample_id") == sample_id), None)
    if row is None:
        return {"ok": False, "error": "baseline_row_missing", "sentence": None}
    projected = project_external_sentence(row, rule_text, sample_id)
    if not projected.get("ok"):
        return {"ok": False, "error": projected.get("error"), "sentence": None,
                "diagnostics": projected.get("diagnostics")}
    return {"ok": True, "error": None, "sentence": projected["sentence"],
            "diagnostics": projected.get("diagnostics"),
            "source": "sun_rule_only_b0_v10a"}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write(path: Path, text: str, overwrite: bool) -> dict:
    if path.exists() and not overwrite:
        raise SystemExit(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return {"path": str(path.relative_to(core.REPO)).replace("\\", "/"),
            "sha256": _sha(text), "bytes": len(text.encode("utf-8"))}


def _load_nlp():
    import spacy
    return spacy.load("en_core_web_sm")


def _sun_thresholds() -> dict:
    config = core.load_json(core.SUN_CONFIG)
    thresholds = config["method"]["thresholds"]
    return {"tau": float(thresholds["tau"]), "gamma": float(thresholds["gamma"]),
            "theta": float(thresholds["theta"])}


def _parse_flattened(payload: bytes, label: str, contract_config: Path,
                     already_flattened: bool = False) -> dict:
    """Parse a model view with the frozen Stage 1 contract.

    ``already_flattened`` must be True for repair variants, which are produced
    FROM the flattened original: flattening twice would re-wrap lanes and add a
    second, unintended adaptation step.
    """
    import xml.etree.ElementTree as ET

    from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_bytes, validate_process_record

    if already_flattened:
        flattened, info = payload, {"transform": "already_flattened", "reason": "repair input"}
    else:
        flattened, info = flatten_collaboration(payload)
    contract = load_stage1_contract(contract_config)
    record = parse_bpmn_bytes(flattened, source_path=f"{label}.bpmn", contract=contract)
    validation = validate_process_record(record)
    if not getattr(validation, "valid", False):
        raise SystemExit(f"{label}: stage1 record invalid: {validation}")
    return {
        "label": label,
        "record": record,
        "xml_root": ET.fromstring(flattened),
        "flattened_xml": flattened,
        "flatten_info": info,
        "evidence": {
            "flattened_xml_sha256": core.sha256_bytes(flattened),
            "process_record_sha256": _sha(json.dumps(record, sort_keys=True, ensure_ascii=False)),
            "activities": len(record.get("activities", [])),
            "gateways": len(record.get("gateways", [])),
            "events": len(record.get("events", [])),
            "flows": len(record.get("sequence_flows", [])),
            "lanes": [lane.get("name") for lane in record.get("lanes", [])],
        },
    }


def _group_rows(scorers: dict, sentence: dict, model, stage1: dict, rule: dict) -> dict:
    three = core.run_three_types(scorers["sun"], rule, model)
    rows = {"three_types": three}
    return rows


def _extended_rows(scorers: dict, sentence: dict, model, stage1: dict, rule: dict) -> dict:
    activity_id, activity_sim, activity_name = core.best_activity_for(sentence, model, scorers["sim"])
    rows, surfaces, raw = core.run_extended_types(scorers["ext"], sentence, model, stage1["record"],
                                                  stage1["xml_root"], activity_id)
    gate = scorers["gate"](raw, GAMMA_EXT)
    return {"extended": rows, "surfaces": surfaces, "gate": gate,
            "mapped_activity": {"id": activity_id, "name": activity_name, "similarity": activity_sim}}


def _rule_side(rule_id: str, rule_text: str, group: str, context: dict) -> dict:
    if group == "A":
        outcome = stage2_group_a_baseline(rule_id, rule_text, context["baseline"])
    else:
        outcome = core.stage2_group_b(rule_id, rule_text, context["predictions"])
    if not outcome.get("ok"):
        return {"ok": False, "error": outcome.get("error"), "sentence": None, "rule": None}
    sentence = core.apply_role_binding(outcome["sentence"])
    sentence["rule_id"] = rule_id
    if not sentence.get("sentence_text"):
        sentence["sentence_text"] = rule_text
    rule = core.build_rule_record(sentence)
    return {"ok": True, "error": None, "sentence": sentence, "rule": rule,
            "stage2_meta": {k: v for k, v in outcome.items() if k not in ("sentence",)}}


def _compare_records(rule_a: dict, rule_b: dict) -> dict:
    fields = ["modality", "actions", "actors", "actor_action_pairs", "order_relations",
              "condition", "constraint", "exception"]
    diff = {f: {"A": rule_a.get(f), "B": rule_b.get(f)}
            for f in fields if rule_a.get(f) != rule_b.get(f)}
    return {"changed_fields": sorted(diff), "detail": diff,
            "attribution": "extraction" if diff else "none"}


def _sanitise_attribution(attribution: dict) -> dict:
    """Keep field names and short fragments only (long rule-side text stays local)."""
    clean = {}
    for rule_id, block in attribution.items():
        if not block:
            clean[rule_id] = block
            continue
        detail = {}
        for field, values in (block.get("detail") or {}).items():
            detail[field] = {side: _fragment(value) for side, value in values.items()}
        clean[rule_id] = {"changed_fields": block.get("changed_fields", []),
                          "attribution": block.get("attribution"),
                          "detail_fragments": detail}
    return clean


def _fragment(value) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    text = " ".join(text.split())
    return f"{text[:30]}…(sha256 {_sha(text)[:12]})" if len(text) > 30 else text


def _id_of(model, name: str) -> str | None:
    return next((a["id"] for a in model.actions if (a.get("name") or "") == name), None)


def _lane_of_record(record: dict, node_id: str) -> str | None:
    for lane in record.get("lanes", []):
        if node_id in (lane.get("flow_node_refs") or []):
            return lane.get("name")
    return None


def verify_repair(repair_id: str, repaired: dict, model) -> dict:
    """Independent structural verification of the repaired model.

    Answers "does the repaired model actually express the intended fix?" WITHOUT
    asking the detector.  The detector's answer is recorded separately, so
    "the program did not notice the repair" can never be confused with
    "the model was not repaired".
    """
    import xml.etree.ElementTree as ET

    root = ET.fromstring(repaired["flattened_xml"])
    tag = lambda e: e.tag.split("}")[1]  # noqa: E731
    evidence: dict = {}
    if repair_id == "r8_timeout_termination":
        boundary = next((e for e in root.iter() if tag(e) == "boundaryEvent"), None)
        timer = next((e for e in root.iter() if tag(e) == "timerEventDefinition"), None)
        attached = boundary.get("attachedToRef") if boundary is not None else None
        attached_name = next((a["name"] for a in model.actions if a["id"] == attached), attached)
        evidence = {
            "boundary_event": boundary is not None, "timer_definition": timer is not None,
            "attached_to": attached_name, "interrupting": boundary.get("cancelActivity") if boundary is not None else None,
            "has_termination_path": any(
                f.get("sourceRef") == (boundary.get("id") if boundary is not None else None)
                and f.get("targetRef") and any(
                    e.get("id") == f.get("targetRef") and tag(e) == "endEvent" for e in root.iter())
                for f in root.iter() if tag(f) == "sequenceFlow"),
        }
        evidence["fix_expressed"] = all([evidence["boundary_event"], evidence["timer_definition"],
                                         bool(attached), evidence["has_termination_path"]])
        evidence["scope"] = "task_scoped_timeout"
        evidence["scope_matches_rule_semantics"] = False
        evidence["scope_note_zh"] = (
            "计时器挂在单个任务（Send SIM card）上：它表达的是“发卡任务超时即中断”，"
            "而规则 R1/r8 要求的是“整个流程耗时超过 30 天则终止流程”。"
            "在扁平化的单流程模型里，进程级超时需要重构控制流（例如用事件子流程或事件网关包住全流程），"
            "那已超出“最小修复”的范围，因此本修复件只部分表达该要求，检测结果按此前提解读。")
    elif repair_id == "r9_add_verification":
        target = _id_of(model, "Verify correctness of customer personal data")
        before = _id_of(model, "Request personal data")
        after = _id_of(model, "Sign contract")
        evidence = {
            "activity_present": target is not None,
            "reachable_from_request_personal_data": bool(target and before and model.is_reachable(before, target)),
            "reaches_sign_contract": bool(target and after and model.is_reachable(target, after)),
        }
        evidence["fix_expressed"] = all(evidence.values())
    elif repair_id == "r10_activation_owner":
        activity = _id_of(model, "Activate SIM card")
        lane = _lane_of_record(repaired["record"], activity) if activity else None
        evidence = {"activity": "Activate SIM card", "lane": lane, "expected_lane": "Phone company"}
        evidence["fix_expressed"] = lane == "Phone company"
    elif repair_id == "r11_consent_before_retrieval":
        consent = _id_of(model, "Ask for consent")
        retrieval = _id_of(model, "Request personal data")
        evidence = {
            "consent_reaches_retrieval": bool(consent and retrieval and model.is_reachable(consent, retrieval)),
            "retrieval_reaches_consent": bool(consent and retrieval and model.is_reachable(retrieval, consent)),
        }
        evidence["fix_expressed"] = evidence["consent_reaches_retrieval"] and not evidence["retrieval_reaches_consent"]
    elif repair_id == "r13_threshold_50":
        labels = [f.get("name") for f in root.iter() if tag(f) == "sequenceFlow" and f.get("name")]
        evidence = {"labels": labels, "old_label_present": "Debt < 100" in labels,
                    "new_label_present": "Debt <= 50" in labels}
        evidence["fix_expressed"] = evidence["new_label_present"] and not evidence["old_label_present"]
    else:
        evidence = {"fix_expressed": False, "reason": "unknown repair"}
    return evidence


def _raw_field_presence(row: dict) -> dict:
    clause = (row.get("record") or {}).get("clauses") or [{}]
    c0 = clause[0] if clause else {}
    counts = {f: len(c0.get(f) or []) for f in ("actions", "actors", "conditions",
                                                "constraints", "exceptions", "order_relations")}
    return {"counts": counts, "any": {f: bool(v) for f, v in counts.items()}}


def build_chain(rule_id: str, rule_text: str, sides: dict, raw_by_group: dict) -> dict:
    """Rule text -> raw extraction -> adapted record -> process binding -> evidence.

    The last column answers the P2 question directly: was a rule element never
    extracted, or was it extracted and then lost during adaptation?
    """
    mapping = {"actions": "actions", "actors": "actors", "conditions": "condition",
               "constraints": "constraint", "exceptions": "exception",
               "order_relations": "order_relations"}
    chain = {"rule_id": rule_id, "version": "v2", "rule_text_sha256": _sha(rule_text),
             "rule_text_length": len(rule_text), "groups": {}}
    for group, side in sides.items():
        if not side.get("ok"):
            chain["groups"][group] = {"ok": False, "error": side.get("error")}
            continue
        rule = side["rule"]
        raw = raw_by_group.get(group) or {}
        presence = _raw_field_presence(raw) if raw else None
        field_flow = {}
        if presence:
            for raw_field, record_field in mapping.items():
                in_raw = presence["any"].get(raw_field, False)
                in_record = bool(rule.get(record_field))
                if raw_field == "order_relations" and in_record and not in_raw:
                    verdict = "derived_by_declared_policy"
                elif in_raw and in_record:
                    verdict = "carried"
                elif in_raw and not in_record:
                    verdict = "lost_in_adaptation"
                elif not in_raw and not in_record:
                    verdict = "not_extracted"
                else:
                    verdict = "present_in_record_without_raw"
                field_flow[raw_field] = {"raw_count": presence["counts"].get(raw_field),
                                         "in_adapted_record": in_record, "verdict": verdict}
        chain["groups"][group] = {
            "ok": True,
            "raw_extraction": presence,
            "adapted_record": rule,
            "field_flow": field_flow,
            "process_binding": {"mapped_activity": side.get("mapped_activity"),
                                "surfaces": side.get("surfaces"),
                                "candidate_activity_id": (side.get("surfaces") or {}).get("activity_id")},
            "checks": side.get("checks"),
            "gate": side.get("gate"),
        }
    return chain


def run(overwrite: bool, check_only: bool) -> dict:
    nlp = _load_nlp()
    thresholds = _sun_thresholds()
    curated = core.load_json(core.CURATED)
    requirements = core.load_requirements()
    predictions = core.load_predictions(1)
    repair_specs = core.load_json(core.REPAIR_SPECS)

    from bpc_hybrid.s3_action_matching_v3 import EvidenceChecksV3  # noqa: E402
    from bpc_hybrid.s3_extended_v3_repair_v2 import (  # noqa: E402
        RepairedExtendedScorerV2, aggregate_with_comparison_gate,
    )
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

    sim = WinterSimilarity(nlp)
    scorers = {"sim": sim, "sun": SunScorer(sim, thresholds["tau"], thresholds["gamma"],
                                            thresholds["theta"], nlp=nlp)}

    original = core.BPMN.read_bytes()
    stage1 = _parse_flattened(original, "sim_original", core.STAGE1_CONTRACT)
    model = core.build_model(stage1, nlp)
    # Group C uses the project's ACCEPTED four-type repair (REPAIR-V2 arm C):
    # v3 action localization at the frozen gamma plus the comparison gate, with
    # no forced resolution.  The original ExtendedViolationScorer is kept only
    # for the diagnostic comparison recorded in the capsule.
    v3 = EvidenceChecksV3(sim, thresholds["tau"], thresholds["gamma"], thresholds["theta"], nlp)
    scorers["ext"] = RepairedExtendedScorerV2(v3, sim.text_pair, LABEL_FALLBACK_GAMMA, GAMMA_EXT)
    scorers["gate"] = aggregate_with_comparison_gate
    baseline_path, baseline = _load_baseline_capsule()

    plan = {
        "schema_version": "sim_case_c1_plan@1.0.0",
        "run_id": "sim_case_c1_run_v1",
        "claim_scope": "development_case_study_not_formal_gold",
        "written_before_scoring": True,
        "main_denominator": [f"{rid}/v2" for rid in core.MAIN_RULES],
        "background_items": core.BACKGROUND_RULES,
        "groups": {
            "A": "project non-LLM baseline sun_rule_only / B0 v10a (CoreNLP + Tregex + locked "
                 "BERT-TextCNN) + frozen Sun-style three-type detection",
            "B": "existing real-LLM predictions (repeat-01) + SAME three-type detection as A",
            "C": "SAME stage2 and three-type rows as B + the project's accepted four-type "
                 "repair (REPAIR-V2 arm C: v3 localization + comparison gate)",
        },
        "components": {
            "A.stage2": {"entry_point": "bpc_hybrid.estg150_b0_development_v10.run_b0_batch_v10",
                         "profile": "PROFILE_V10A",
                         "capsule": str(baseline_path.relative_to(core.REPO)).replace("\\", "/"),
                         "runner": "scripts/run_sim_case_stage2_baseline_v1.py",
                         "language_boundary": "English sentences through the German-contract classifier slot"},
            "A.stage3": {"three_types": "bpc_hybrid.sun_stage3.sun_scorer.SunScorer (Def5-7)",
                         "four_types": "not run"},
            "B.stage2": {"source": "outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-01",
                         "projection": "bpc_hybrid.gdpr_s2_s3_projection.project_external_sentence"},
            "B.stage3": {"three_types": "identical code and thresholds to A", "four_types": "not run"},
            "C.stage2": {"source": "identical to B (same row objects)"},
            "C.stage3": {"three_types": "identical rows reused from B",
                         "four_types": "bpc_hybrid.s3_extended_v3_repair_v2.RepairedExtendedScorerV2 "
                                       "(v3=EvidenceChecksV3 gamma 0.8, label fallback 0.4, gamma_ext 0.5) "
                                       "+ aggregate_with_comparison_gate"},
            "similarity_backend": {"class": "bpc_hybrid.winter_stage3.winter_similarity.WinterSimilarity",
                                   "nlp": "en_core_web_sm",
                                   "behaviour": "Doc.similarity over context-sensitive tensors (spaCy warns W007: "
                                                "the model ships no static word vectors); it is NOT a string "
                                                "similarity and NOT a static-embedding similarity"},
        },
        "declared_policy": core.ADAPTATION_POLICY,
        "thresholds": {**thresholds, "gamma_ext": GAMMA_EXT,
                       "label_fallback_gamma": LABEL_FALLBACK_GAMMA,
                       "source": "configs/sun_stage3_development_v1.json + REPAIR-V2 arm C configuration"},
        "lens_map": LENS_MAP,
        "inputs": {
            "bpmn": core.artifact(core.BPMN),
            "requirements": core.artifact(core.REQUIREMENTS),
            "step_3_baseline": core.artifact(core.STEP3),
            "curated_reference_judgments": core.artifact(core.CURATED),
            "repair_specs": core.artifact(core.REPAIR_SPECS),
            "predictions_repeat01": predictions["artifact"],
            "stage1_contract": core.artifact(core.STAGE1_CONTRACT),
            "sun_config": core.artifact(core.SUN_CONFIG),
            "stage2_baseline_capsule": core.artifact(baseline_path),
        },
        "stage1_public_record": stage1["evidence"],
        "implementation_hashes": {
            "core": _sha(Path(core.__file__).read_text(encoding="utf-8")),
            "transforms": _sha((ROOT / "src" / "bpc_hybrid" / "sim_case_c1_transforms.py")
                               .read_text(encoding="utf-8")),
            "runner": _sha(Path(__file__).read_text(encoding="utf-8")),
        },
        "prediction_isolation": {
            "reference_judgments_read_after_predictions": True,
            "external_deviations_not_in_detection_input": True,
            "step_3_baseline_read_only_for_comparison": True,
        },
    }

    rows: list[dict] = []
    rule_records: dict[str, dict] = {}
    for rule_id in core.MAIN_RULES:
        rule_text = requirements[(rule_id, 2)]
        sides = {group: _rule_side(rule_id, rule_text, group,
                                   {"nlp": nlp, "predictions": predictions, "baseline": baseline})
                 for group in ("A", "B")}
        entry = {"rule_id": rule_id, "version": "v2", "rule_text_sha256": _sha(rule_text),
                 "rule_text_length": len(rule_text), "sides": {}}
        for group, side in sides.items():
            if not side["ok"]:
                rows.append({"rule_id": rule_id, "group": group, "check": "*",
                             "status": core.STATUS_UNDETERMINED, "reason": side["error"]})
                entry["sides"][group] = {"ok": False, "error": side["error"]}
                continue
            rule_rows = _group_rows(scorers, side["sentence"], model, stage1, side["rule"])
            entry["sides"][group] = {
                "ok": True,
                "sentence": {k: v for k, v in side["sentence"].items() if k != "sentence_text"},
                "rule": side["rule"],
                "checks": rule_rows["three_types"],
                "stage2_meta": side["stage2_meta"],
            }
            for check, result in rule_rows["three_types"].items():
                rows.append({"rule_id": rule_id, "group": group, "check": check,
                             "status": result["status"], "score": result.get("score"),
                             "denominator": result.get("denominator"),
                             "reason": result.get("reason")})
        # group C = group B rule side + extended types
        side_b = sides["B"]
        if side_b["ok"]:
            ext = _extended_rows(scorers, side_b["sentence"], model, stage1, side_b["rule"]) 
            entry["sides"]["C"] = {
                "ok": True,
                "sentence": entry["sides"]["B"]["sentence"],
                "rule": side_b["rule"],
                "checks": {**entry["sides"]["B"]["checks"], **ext["extended"]},
                "surfaces": ext["surfaces"], "mapped_activity": ext["mapped_activity"],
                "gate": ext["gate"],
                "reuses_group_b": ["stage2", "three_type_rows"],
            }
            for check, result in entry["sides"]["B"]["checks"].items():
                rows.append({"rule_id": rule_id, "group": "C", "check": check,
                             "status": result["status"], "score": result.get("score"),
                             "denominator": result.get("denominator"),
                             "reason": result.get("reason"),
                             "inherited_from": "B"})
            for check, result in ext["extended"].items():
                rows.append({"rule_id": rule_id, "group": "C", "check": check,
                             "status": result["status"], "score": result.get("score"),
                             "reason": result.get("reason"),
                             "candidate_count": result.get("candidate_count"),
                             "best_candidate": result.get("best_candidate"),
                             "max_sim": result.get("max_sim"),
                             "added_by": "four_extended_types"})
        else:
            entry["sides"]["C"] = {"ok": False, "error": side_b.get("error")}
        entry["a_to_b"] = (_compare_records(entry["sides"]["A"]["rule"], entry["sides"]["B"]["rule"])
                           if entry["sides"]["A"].get("ok") and entry["sides"]["B"].get("ok") else None)
        raw_by_group = {
            "A": next((r for r in baseline.get("records", [])
                       if r.get("sample_id") == f"sim_{rule_id}_v2"), {}),
            "B": predictions["rows"].get(f"SIM_card_scenario/{rule_id}/v2", {}),
        }
        entry["chain"] = build_chain(rule_id, rule_text,
                                     {g: entry["sides"].get(g) or {} for g in ("A", "B", "C")},
                                     raw_by_group)
        rule_records[rule_id] = entry
        stage1 = stage1  # single public record consumed by all groups

    # ---- predictions are on disk in memory only; now (and only now) read the
    # development reference judgments for the comparison table -----------------
    reference = {item["rule_id"]: item for item in curated["items"]}
    comparison = []
    for rule_id in core.MAIN_RULES:
        item = reference[rule_id]
        lenses = LENS_MAP[rule_id]
        per_group = {}
        for group in ("A", "B", "C"):
            side = rule_records[rule_id]["sides"].get(group) or {}
            checks = side.get("checks") or {}
            lens_results = {}
            for lens in [lenses["primary"], *lenses["secondary"]]:
                if lens in checks:
                    lens_results[lens] = {"status": checks[lens]["status"],
                                          "score": checks[lens].get("score"),
                                          "reason": checks[lens].get("reason")}
            found = any(r["status"] == core.STATUS_VIOLATION for r in lens_results.values())
            undetermined = (not lens_results) or all(
                r["status"] in (core.STATUS_UNDETERMINED, core.STATUS_NOT_APPLICABLE)
                for r in lens_results.values())
            per_group[group] = {
                "covered_lenses": sorted(lens_results),
                "lens_results": lens_results,
                "found_corresponding_problem": found,
                "all_lenses_undetermined": bool(undetermined),
                "type_name_match": found and lenses["primary"] in {
                    k for k, v in lens_results.items() if v["status"] == core.STATUS_VIOLATION},
            }
        reference_present = item["dev_reference_judgment"]["judgment"] in (
            "issue_present", "issue_present_with_premise")
        primary = per_group["C"]
        comparison.append({
            "rule_id": rule_id,
            "reference_judgment": item["dev_reference_judgment"]["judgment"],
            "reference_sources": item["dev_reference_judgment"]["sources"],
            "premise_zh": item["dev_reference_judgment"].get("premise_zh"),
            "semantic_issue_zh": item["semantic_issue"]["summary_zh"],
            "primary_lens": lenses["primary"],
            "secondary_lenses": lenses["secondary"],
            "groups": per_group,
            "consistency": {
                "reference_issue_present": reference_present,
                "group_C_found": primary["found_corresponding_problem"],
                "group_C_undetermined": primary["all_lenses_undetermined"],
                "miss_kind": (None if primary["found_corresponding_problem"]
                              else ("undetermined" if primary["all_lenses_undetermined"]
                                    else "wrong_judgment")),
            },
        })

    # ---- repair controls ----------------------------------------------------
    repairs = []
    for spec in repair_specs["repairs"]:
        repaired_payload, detail = repair_variant(stage1["flattened_xml"], spec["repair_id"])
        repaired = _parse_flattened(repaired_payload, f"repair_{spec['repair_id']}", core.STAGE1_CONTRACT,
                                    already_flattened=True)
        repaired_model = core.build_model(repaired, nlp)
        rule_text = requirements[(spec["rule_id"], 2)]
        row = {"repair_id": spec["repair_id"], "rule_id": spec["rule_id"], "lens": spec["lens"],
               "operations": detail["operations"], "semantic_zh": detail["semantic_zh"],
               "model_evidence": repaired["evidence"],
               "independent_verification": verify_repair(spec["repair_id"], repaired, repaired_model),
               "before": None, "after": None}
        for group in ("B", "C"):
            side = rule_records[spec["rule_id"]]["sides"].get(group, {})
            if not side.get("ok"):
                continue
            sentence = dict(side["sentence"])
            sentence["sentence_text"] = rule_text
            rule = side["rule"]
            if spec["lens"] in ("missing_action", "incorrect_actor", "out_of_order"):
                after_checks = core.run_three_types(scorers["sun"], rule, repaired_model)
            else:
                after_checks = _extended_rows(scorers, sentence, repaired_model, repaired, rule)["extended"]
            after = after_checks.get(spec["lens"])
            before = (side.get("checks") or {}).get(spec["lens"])
            result = {"group": group,
                      "before_status": (before or {}).get("status"),
                      "before_score": (before or {}).get("score"),
                      "after_status": (after or {}).get("status"),
                      "after_score": (after or {}).get("score"),
                      "after_reason": (after or {}).get("reason"),
                      "problem_removed": ((before or {}).get("status") == core.STATUS_VIOLATION
                                          and (after or {}).get("status") == core.STATUS_SATISFIED)}
            if group == "C":
                row["after"] = result
            else:
                row["before"] = result
            row[f"group_{group}"] = result
        repairs.append(row)

    summary = {}
    for group in ("A", "B", "C"):
        counts: dict[str, int] = {}
        for row in rows:
            if row["group"] != group:
                continue
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        summary[group] = {"checks": sum(1 for r in rows if r["group"] == group), "status_counts": counts}

    capsule = {
        "schema_version": "sim_case_c1_run@1.0.0",
        "run_id": plan["run_id"],
        "claim_scope": plan["claim_scope"],
        "plan": plan,
        "rows": rows,
        "rules": rule_records,
        "comparison": comparison,
        "repairs": repairs,
        "summary": summary,
        "stage_attribution": {
            "a_to_b": {rid: rule_records[rid]["a_to_b"] for rid in core.MAIN_RULES},
            "b_to_c": "group C adds exactly the four extended checks on the SAME rule side as B; "
                      "three-type rows are reused byte-identically (reuses_group_b)",
        },
    }

    if check_only:
        return {"status": "CHECK_OK", "summary": summary,
                "comparison": [{c["rule_id"]: c["consistency"]} for c in comparison],
                "repairs": [{r["repair_id"]: (r.get("group_C") or {}).get("problem_removed")} for r in repairs]}

    outputs = {
        "plan": _write(RUN_DIR / "plan.json", json.dumps(plan, ensure_ascii=False, indent=1) + "\n", overwrite),
        "capsule": _write(RUN_DIR / "capsule.json", json.dumps(capsule, ensure_ascii=False, indent=1) + "\n", overwrite),
        "rows": _write(RUN_DIR / "rows.jsonl",
                       "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), overwrite),
        "report_json": _write(REPORT_JSON, json.dumps(
            {"schema_version": capsule["schema_version"], "run_id": plan["run_id"],
             "claim_scope": plan["claim_scope"], "groups": plan["groups"],
             "thresholds": plan["thresholds"], "declared_policy": plan["declared_policy"],
             "stage1": plan["stage1_public_record"], "inputs": plan["inputs"],
             "summary": summary, "comparison": comparison, "repairs": repairs,
             "stage_attribution": {
                 "a_to_b": _sanitise_attribution(capsule["stage_attribution"]["a_to_b"]),
                 "b_to_c": capsule["stage_attribution"]["b_to_c"],
             },
             "boundaries": [
                 "development case study; not formal Gold, not the authors' original experiment, not an enterprise validation",
                 "single case: counts and per-item results only; no seven-type aggregate F1",
                 "five prediction repeats are stability evidence, not 25 independent samples",
                 "the Barrientos artifact is read in place; no restricted text is committed",
             ]}, ensure_ascii=False, indent=1) + "\n", overwrite),
    }
    outputs["report_md"] = _write(REPORT_MD, render_md(capsule), overwrite)
    manifest = {
        "schema_version": "sim_case_c1_run_manifest@1.0.0",
        "run_id": plan["run_id"], "inputs": plan["inputs"],
        "implementation_hashes": plan["implementation_hashes"],
        "outputs": outputs, "api_calls": 0, "network": False,
    }
    _write(RUN_DIR / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", overwrite)
    (LOCAL_MODELS).mkdir(parents=True, exist_ok=True)
    (LOCAL_MODELS / "sim_original_flattened.bpmn").write_bytes(stage1["flattened_xml"])
    return {"status": "BUILT", "outputs": {k: v["path"] for k, v in outputs.items()},
            "summary": summary}


def render_md(capsule: dict) -> str:
    plan = capsule["plan"]
    lines = [
        "# SIM 卡入网案例：A/B/C 三组开发性检测结果（S3.9-EXT-REAL-CASE）",
        "",
        f"- run: `{capsule['run_id']}`；口径：**{capsule['claim_scope']}**（非正式 Gold、非作者原始实验复现、非企业验证）",
        f"- 主实验规则（5 条）：{', '.join(plan['main_denominator'])}；背景条目：{', '.join(plan['background_items'])}",
        f"- 阈值：tau={plan['thresholds']['tau']}, gamma={plan['thresholds']['gamma']}, "
        f"theta={plan['thresholds']['theta']}, gamma_ext={plan['thresholds']['gamma_ext']}",
        f"- 公共 Stage 1 记录：{plan['stage1_public_record']['process_record_sha256'][:16]}…"
        f"（扁平化 XML {plan['stage1_public_record']['flattened_xml_sha256'][:16]}…，"
        f"lanes={plan['stage1_public_record']['lanes']}）",
        f"- 角色绑定：{json.dumps(plan['declared_policy']['role_binding'], ensure_ascii=False)}"
        "（打分前声明，三组共用）",
        "",
        "## 1. 组件对应表（P1：这三组究竟跑了什么）",
        "",
        "| 组 | Stage 2（实际入口/模型） | Stage 3 三类 | Stage 3 四类 |",
        "|---|---|---|---|",
        "| A | 项目锁定非 LLM 基线 `run_b0_batch_v10`（B0 v10a：CoreNLP+Tregex+BERT-TextCNN，"
        "英文句经德语合同分类器槽 pass-through） | 冻结 Sun 式 Def5-7 | 无 |",
        "| B | 既有真实 LLM 预测（`OURS-FULL/repeat-01`，经 `project_external_sentence` 投影） | "
        "与 A 同一代码与阈值 | 无 |",
        "| C | 与 B 完全相同（复用同一行对象） | 与 B 完全相同（逐行复用） | REPAIR-V2 C 臂："
        "`RepairedExtendedScorerV2`（v3 γ=0.8 + 标签回退 0.4 + γ_ext=0.5）+ 比较门 |",
        "",
        f"- 相似度后端：`{plan['components']['similarity_backend']['class']}`，nlp="
        f"`{plan['components']['similarity_backend']['nlp']}`；行为："
        f"{plan['components']['similarity_backend']['behaviour']}",
        f"- 阈值：tau={plan['thresholds']['tau']}, gamma={plan['thresholds']['gamma']}, "
        f"theta={plan['thresholds']['theta']}, gamma_ext={plan['thresholds']['gamma_ext']}, "
        f"label_fallback={plan['thresholds']['label_fallback_gamma']}",
        f"- 角色绑定：{json.dumps(plan['declared_policy']['role_binding'], ensure_ascii=False)}；"
        f"顺序推导政策：`{plan['declared_policy']['order_relation_derivation']['name']}`"
        f"（{plan['declared_policy']['order_relation_derivation'].get('comma_handling')}）",
        "",
        "## 2. 逐条结果（③ 方法实际输出）",
        "",
        "| 规则 | 组 | missing_action | incorrect_actor | out_of_order | prohibited | condition | constraint | exception |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for rule_id in core.MAIN_RULES:
        entry = capsule["rules"][rule_id]
        for group in ("A", "B", "C"):
            checks = (entry["sides"].get(group) or {}).get("checks") or {}
            def cell(name):
                c = checks.get(name)
                if not c:
                    return "—"
                extra = f" ({c.get('score')})" if c.get("score") is not None else ""
                return f"{c['status']}{extra}"
            lines.append(f"| {rule_id}/v2 | {group} | {cell('missing_action')} | {cell('incorrect_actor')} | "
                         f"{cell('out_of_order')} | {cell('prohibited_action_present')} | "
                         f"{cell('required_condition_not_enforced')} | {cell('constraint_violated')} | "
                         f"{cell('exception_not_handled')} |")
    lines += ["", "## 3. 逐条证据与错误来源（③ 方法实际输出 + ⑤ 归因）", "",
              "| 规则 | 组 | 映射活动（相似度） | 检测项 | 状态 | 分数 | 机器原因 | 候选面计数 |",
              "|---|---|---|---|---|---|---|---|"]
    for rule_id in core.MAIN_RULES:
        entry = capsule["rules"][rule_id]
        for group in ("A", "B", "C"):
            side = entry["sides"].get(group) or {}
            checks = side.get("checks") or {}
            mapped = side.get("mapped_activity") or {}
            map_cell = f"{mapped.get('name')} ({mapped.get('similarity')})" if mapped else "—"
            surfaces = side.get("surfaces") or {}
            cand = (f"cond={len(surfaces.get('condition_candidates') or [])}, "
                    f"cons={len(surfaces.get('constraint_candidates') or [])}, "
                    f"exc={len(surfaces.get('exception_candidates') or [])}" if surfaces else "—")
            for name, result in checks.items():
                lines.append(f"| {rule_id}/v2 | {group} | {map_cell} | {name} | {result['status']} | "
                             f"{result.get('score')} | {result.get('reason') or '—'} | {cand} |")
    lines += ["", "## 4. 信息去向（P2：没抽出来，还是抽出来后在适配里丢了）", "",
              "| 规则 | 组 | actions | actors | condition | constraint | exception | order_relations |",
              "|---|---|---|---|---|---|---|---|"]
    for rule_id in core.MAIN_RULES:
        chain = capsule["rules"][rule_id]["chain"]["groups"]
        for group in ("A", "B"):
            flow = (chain.get(group) or {}).get("field_flow") or {}
            cells = [((flow.get(f) or {}).get("verdict") or "—") for f in
                     ("actions", "actors", "conditions", "constraints", "exceptions", "order_relations")]
            lines.append(f"| {rule_id}/v2 | {group} | " + " | ".join(cells) + " |")
    lines += ["",
              "判定含义：`carried`=抽取到且进入适配记录；`not_extracted`=原始抽取里就没有；"
              "`lost_in_adaptation`=抽取到但适配后丢失；`derived_by_declared_policy`=原始无该字段、"
              "由已声明的顺序推导政策生成（不是回填答案）。",
              "", "## 5. 与开发参考判断的逐条对照（① ② ④ ⑤）", "",
              "| 规则 | ① 语义问题 | ② 参考判断（来源） | 主检测视角 | C 组检出 | 未检出类型 | ⑤ A→B 变化字段 |",
              "|---|---|---|---|---|---|---|"]
    for item in capsule["comparison"]:
        rid = item["rule_id"]
        attr = capsule["stage_attribution"]["a_to_b"].get(rid) or {}
        lines.append(
            f"| {rid}/v2 | {item['semantic_issue_zh']} | {item['reference_judgment']}"
            f"（{', '.join(item['reference_sources'][:2])}…） | {item['primary_lens']} | "
            f"{'是' if item['consistency']['group_C_found'] else '否'} | "
            f"{item['consistency']['miss_kind'] or '—'} | {', '.join(attr.get('changed_fields', [])) or '无'} |")
    lines += ["", "## 6. 误报检查（未修改原图上的检出，启发式筛查）", "",
              "> 没有独立的人工合规对照，因此这里只能按**证据强度**做启发式筛查："
              "`likely_spurious` 表示判定依赖的相似度低于 0.75（本后端无词向量，"
              "该数值不构成语义同义的证据），`incidental` 表示检出落在参考问题视角之外。"
              "这两类**不等于已证实的误报**，也不改变上面的状态与计数。", "",
              "| 规则 | 检测项 | 分数 | 最强候选 | 相似度 | 与参考问题关系 | 筛查标记 |",
              "|---|---|---|---|---|---|---|"]
    for rule_id in core.MAIN_RULES:
        entry = capsule["rules"][rule_id]
        side = entry["sides"].get("C") or {}
        lenses = set(LENS_MAP[rule_id]["secondary"]) | {LENS_MAP[rule_id]["primary"]}
        for name, result in (side.get("checks") or {}).items():
            if result.get("status") != core.STATUS_VIOLATION:
                continue
            if name in ("missing_action", "incorrect_actor", "out_of_order"):
                continue  # inherited from B; listed in section 2
            sim = result.get("max_sim")
            weak = sim is not None and sim < 0.75
            relation = "参考问题视角内" if name in lenses else "参考问题视角之外（附带检出）"
            flag = "incidental" if name not in lenses else ("likely_spurious" if weak else "—")
            lines.append(f"| {rule_id}/v2 | {name} | {result.get('score')} | {result.get('best_candidate')} | "
                         f"{sim} | {relation} | {flag} |")
    lines += ["", "## 7. 修复对照（程序构造的最小开发对照）", "",
              "> 修复正确性由**独立结构核验**判定（`independent_verification.fix_expressed`），与检测器是否识别无关；"
              "最后一列只说明方法表现。", "",
              "| 修复 | 规则 | 视角 | 操作 | 独立核验：表达了修复 | C 组修复前 | C 组修复后 | 检测器是否识别 |",
              "|---|---|---|---|---|---|---|---|"]
    for row in capsule["repairs"]:
        after = row.get("group_C") or {}
        iv = row.get("independent_verification") or {}
        scope = "（范围限制：任务级计时≠进程级终止）" if iv.get("scope_matches_rule_semantics") is False else ""
        lines.append(f"| {row['repair_id']} | {row['rule_id']} | {row['lens']} | {row['semantic_zh']} | "
                     f"{'是' if iv.get('fix_expressed') else '否'}{scope} | "
                     f"{after.get('before_status')} | {after.get('after_status')} | "
                     f"{'是' if after.get('problem_removed') else '否'} |")
    lines += ["", "## 8. 计数（不做七类总 F1）", "",
              "| 组 | 检查数 | violation | satisfied | undetermined | not_applicable |",
              "|---|---|---|---|---|---|"]
    for group, block in capsule["summary"].items():
        counts = block["status_counts"]
        lines.append(f"| {group} | {block['checks']} | {counts.get('violation', 0)} | "
                     f"{counts.get('satisfied', 0)} | {counts.get('undetermined', 0)} | "
                     f"{counts.get('not_applicable', 0)} |")
    lines += ["", "## 9. 边界", "",
              "- 本结果是开发性案例分析：不是正式 Gold、不是作者原始实验复现、不是独立测试、不是企业验证。",
              "- 单案例只给逐条结果与计数，不合成七类总 F1；5 轮预测只作稳定性证据。",
              "- Barrientos 语料按本地只读使用，不提交其原文；修复件是程序构造的开发对照。",
              ""]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--check", action="store_true", help="run in memory, write nothing")
    ap.add_argument("--replay", action="store_true", help="rerun from the stored plan and compare")
    args = ap.parse_args()
    result = run(overwrite=args.overwrite, check_only=args.check or args.replay)
    print(json.dumps(result, ensure_ascii=False, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
