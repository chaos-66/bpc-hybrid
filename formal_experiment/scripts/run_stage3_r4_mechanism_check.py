# -*- coding: utf-8 -*-
"""R4 independent mechanism/development check.

The check separates three things that R3 conflated: implementation-contract
checks, behaviour probes, and reproduction of known limitations.  It returns
non-zero when a machine-checkable contract or probe fails.  ``--self-test-failure``
is an explicit failing fixture used to verify the non-zero exit path.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.stage3_r3_p2_adapter_v1 import (  # noqa: E402
    R3ActionView,
    R3P2Model,
    analyze_label_text,
    build_endpoint_view,
    build_rule_action_views,
    frozen_lemma,
)
from bpc_hybrid.sun_stage3 import temporal_projection_v4_r3 as v4  # noqa: E402
from bpc_hybrid.sun_stage3.r4_action_surface_scorer import R4ActionSurfaceScorer  # noqa: E402
from bpc_hybrid.sun_stage3.static_vector_similarity_v1 import StaticVectorSimilarity  # noqa: E402

FIXTURES = ROOT / "data/development/stage3_r4_synth/mechanism_fixtures_v1.json"
SUN_CONFIG = ROOT / "configs/sun_stage3_development_v1.json"
ALLOWED_BACKENDS = {"r4_sm": "sm", "r4_static_vector_lg": "static_vector_lg"}


def _load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _span(text: str, sub: str, span_id: str) -> dict[str, Any]:
    start = text.index(sub)
    return {"id": span_id, "start": start, "end": start + len(sub)}


def _clause(case: Mapping[str, Any]) -> dict[str, Any]:
    text = str(case["text"])
    return {
        "clause_id": f"fixture_{case['case_id']}",
        "modality": {"label": "obligation"},
        "actions": [_span(text, str(case["action_text"]), "a1")],
        "actors": [],
        "conditions": [_span(text, str(case["marker_text"]), "c1")] if case.get("field") == "conditions" else [],
        "constraints": [_span(text, str(case["marker_text"]), "c1")] if case.get("field") == "constraints" else [],
        "exceptions": [],
        "actor_action_pairs": [],
        "order_relations": [],
    }


def _node_spec_to_node(nlp: Any, spec: Mapping[str, Any]) -> dict[str, Any]:
    label = str(spec["label"])
    if "action_surface" in spec:
        action_surface = spec.get("action_surface")
        analysis = {
            "business_object_surface": None,
            "match_source_text": None,
            "matching_text": None,
            "parse_status": "explicit_fixture_missing_action_surface" if not action_surface else "explicit_fixture",
            "parse_error": None,
        }
    else:
        analysis = analyze_label_text(nlp, label, source="fixture_model_node")
        action_surface = analysis["action_surface"]
    return {
        "node_id": str(spec["node_id"]),
        "node_type": "activity",
        "raw_label": label,
        "actor_surface": str(spec.get("actor") or "FixtureActor"),
        "actor_status": "fixture_pool",
        "action_surface": action_surface,
        "business_object_surface": analysis.get("business_object_surface"),
        "match_source_text": analysis.get("match_source_text"),
        "matching_text": analysis.get("matching_text"),
        "parse_status": str(analysis.get("parse_status")),
        "parse_source": "fixture_model_node",
        "parse_error": analysis.get("parse_error"),
        "label_status": None,
        "lane_labels": [],
    }


def _model_from_case(case: Mapping[str, Any], nlp: Any) -> R3P2Model:
    nodes = [_node_spec_to_node(nlp, spec) for spec in case.get("node_specs") or []]
    nodes.sort(key=lambda row: str(row["node_id"]))
    actors: list[str] = []
    actor_sources: dict[str, str] = {}
    action_actor_names: dict[str, list[str]] = {}
    business_objects: list[dict[str, Any]] = []
    for node in nodes:
        actor = str(node.get("actor_surface") or "")
        if actor:
            if actor not in actors:
                actors.append(actor)
            actor_sources[actor] = str(node.get("actor_status") or "fixture_pool")
            action_actor_names[str(node["node_id"])] = [actor]
        else:
            action_actor_names[str(node["node_id"])] = []
        if node.get("business_object_surface"):
            obj = str(node["business_object_surface"])
            business_objects.append({
                "activity_id": str(node["node_id"]),
                "object": obj,
                "match_source_text": obj,
                "matching_text": frozen_lemma(nlp, obj),
                "source": node.get("parse_source"),
            })
    sidecar = {
        "schema_version": "r4_fixture_sidecar",
        "process_id": "fixture",
        "nodes": nodes,
        "actors": actors,
        "actor_sources": actor_sources,
        "action_actor_names": action_actor_names,
        "business_objects": business_objects,
        "reachable": {str(k): list(v) for k, v in (case.get("reachable") or {}).items()},
    }
    return R3P2Model(sidecar)


def _rule_view(case: Mapping[str, Any], nlp: Any) -> Any:
    if "rule_action_override" in case:
        spec = case["rule_action_override"]
        original = str(spec.get("original_text") or "")
        action_surface = spec.get("action_surface")
        return R3ActionView(
            original,
            original_text=original,
            action_surface=action_surface,
            business_object_surface=None,
            match_source_text=action_surface,
            matching_text=frozen_lemma(nlp, action_surface) if action_surface else None,
            parse_status="explicit_fixture",
            parse_source="fixture_rule_override",
            parse_error=None,
        )
    return build_rule_action_views(nlp, [str(case.get("rule_action") or "")])[0][0]


class _TrackingScorer(R4ActionSurfaceScorer):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.action_match_calls: dict[str, int] = {}

    def _best_action_match(self, rule_action: Any, model: Any):
        self.action_match_calls["any"] = self.action_match_calls.get("any", 0) + 1
        return super()._best_action_match(rule_action, model)


def _build_scorer(backend: str, nlp: Any, lg_model_path: str | None = None) -> tuple[Any, dict[str, Any]]:
    if backend == "r4_sm":
        from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity
        sim = WinterSimilarity(nlp)
        info = {"backend": "r4_sm", "parser": "en_core_web_sm",
                "version": str(nlp.meta.get("version", ""))}
    elif backend == "r4_static_vector_lg":
        if not lg_model_path or not Path(lg_model_path).is_dir():
            raise ValueError("r4_static_vector_lg requires an existing --lg-model-path")
        import spacy  # type: ignore
        nlp_lg = spacy.load(str(lg_model_path))
        sim = StaticVectorSimilarity(nlp, nlp_lg, model_path=str(lg_model_path),
                                     model_version=str(nlp_lg.meta.get("version", "")))
        info = {"backend": "r4_static_vector_lg", "parser": "en_core_web_sm",
                "vector_model": str(lg_model_path),
                "version": str(nlp_lg.meta.get("version", "")),
                "dimension": int(getattr(nlp_lg, "vector_size", None)
                                 or getattr(getattr(nlp_lg, "vocab", None), "vectors_length", 0) or 0)}
    else:
        raise ValueError(f"unknown backend: {backend}")
    cfg = _load_json(SUN_CONFIG)
    thresholds = cfg["method"]["thresholds"]
    scorer = R4ActionSurfaceScorer(sim, float(thresholds["tau"]),
                                   float(thresholds["gamma"]),
                                   float(thresholds["theta"]), nlp=nlp)
    return scorer, info


def _contract_checks(scorer: Any, nlp: Any) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    model = _model_from_case({"node_specs": [{"node_id": "N1", "label": "Approve the invoice"}]}, nlp)
    rule = build_rule_action_views(nlp, ["approve the invoice"])[0][0]
    candidates = scorer.action_candidate_evidence(rule, model)
    selected = next((row.get("node_id") for row in candidates if row.get("selected")), None)
    evidence_ok = bool(candidates) and candidates[0].get("candidate_action_match_text") == "Approve"
    legacy_retained = model.actions[0].get("match_source_text") is not None
    checks.append({
        "check": "action_comparison_uses_action_surface_not_legacy_join",
        "passed": bool(evidence_ok and selected == "N1" and legacy_retained),
        "evidence": {"selected": selected, "candidates": candidates[:2],
                     "legacy_match_source_text": model.actions[0].get("match_source_text")},
    })

    missing_model = _model_from_case({
        "node_specs": [{"node_id": "N1", "label": "Inform the data subject", "action_surface": None}]
    }, nlp)
    rule_inform = build_rule_action_views(nlp, ["inform"])[0][0]
    rows = scorer.action_candidate_evidence(rule_inform, missing_model)
    checks.append({
        "check": "missing_model_action_surface_does_not_fallback_to_full_label",
        "passed": bool(rows) and all(row.get("reason") == "model_action_missing_action_surface"
                                     for row in rows if row.get("similarity") is None)
                  and not any(row.get("selected") for row in rows),
        "evidence": {"rows": rows},
    })

    model_inform = _model_from_case({"node_specs": [{"node_id": "N1", "label": "Inform the data subject"}]}, nlp)
    rule_missing = _rule_view({
        "rule_action_override": {"original_text": "inform the data subject", "action_surface": None}
    }, nlp)
    rows = scorer.action_candidate_evidence(rule_missing, model_inform)
    checks.append({
        "check": "missing_rule_action_surface_does_not_fallback_to_full_label",
        "passed": bool(rows) and rows[0].get("reason") == "rule_action_missing_action_surface"
                  and not any(row.get("selected") for row in rows),
        "evidence": {"rows": rows},
    })

    track_model = _model_from_case({
        "node_specs": [
            {"node_id": "N1", "label": "Inform the data subject"},
            {"node_id": "N2", "label": "Archive the record"},
        ],
        "reachable": {"N1": ["N2"]},
    }, nlp)
    track_rule = build_rule_action_views(nlp, ["inform"])[0][0]
    track = _TrackingScorer(scorer.sim, scorer.tau, scorer.gamma, scorer.theta, nlp=nlp)
    track.matching_score([track_rule], ["FixtureActor"], track_model)
    c_matching = track.action_match_calls.get("any", 0)
    track.missing_action([track_rule], track_model)
    c_missing = track.action_match_calls.get("any", 0)
    before = build_endpoint_view(nlp, "inform", source="fixture_endpoint")
    after = build_endpoint_view(nlp, "archive", source="fixture_endpoint")
    track.out_of_order([(before, after)], [track_rule], track_model)
    c_order = track.action_match_calls.get("any", 0)
    track.incorrect_actor([track_rule], ["FixtureActor"], track_model,
                          [{"actor": "FixtureActor", "action": track_rule}])
    c_actor = track.action_match_calls.get("any", 0)
    checks.append({
        "check": "def4_def5_def6_def7_share_action_comparison_function",
        "passed": bool(c_matching > 0 and c_missing > c_matching and c_order > c_missing and c_actor > c_order),
        "evidence": {"tracked_best_action_match_calls": {
            "after_def4": c_matching, "after_def5": c_missing,
            "after_def7": c_order, "after_def6": c_actor}},
    })

    bo_model = _model_from_case({"node_specs": [{"node_id": "N1", "label": "Inform the data"}]}, nlp)
    bo_rule = build_rule_action_views(nlp, ["inform"])[0][0]
    raw = scorer.incorrect_actor([bo_rule], ["Controller"], bo_model,
                                 [{"actor": "Controller", "action": bo_rule}])
    bo_candidates = (raw.get("process_actor_candidates") or [])
    checks.append({
        "check": "business_object_surface_retained_for_def6_candidate_scope",
        "passed": any(bo.get("activity_id") == "N1" for bo in bo_model.business_objects)
                  and any(row.get("kind") == "business_object" for row in bo_candidates),
        "evidence": {"business_objects": bo_model.business_objects,
                     "process_actor_candidates": bo_candidates},
    })
    return checks


def _run_projection_cases(cases: list[Mapping[str, Any]], nlp: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        text = str(case["text"])
        doc = nlp(text)
        record = {"clauses": [_clause(case)]}
        try:
            edges, audit = v4.project_record_order_relations(record, text, doc, nlp=nlp)
            clause_audit = (audit.get("clause_audits") or [{}])[0]
            reason = None
            for marker in clause_audit.get("markers") or []:
                reason = marker.get("reason")
                if reason:
                    break
            expected = [list(x) for x in case.get("expected_edges") or []]
            if case.get("expect_reject_reason_contains"):
                passed = (not edges) and str(case["expect_reject_reason_contains"]) in str(reason)
            else:
                passed = edges == [tuple(x) for x in expected]
            rows.append({
                "case_id": case["case_id"],
                "kind": "projection",
                "passed": bool(passed),
                "actual_edges": edges,
                "expected_edges": expected,
                "rejection_reason": reason,
                "audit": clause_audit,
            })
        except Exception as exc:  # noqa: BLE001
            rows.append({"case_id": case["case_id"], "kind": "projection",
                         "passed": False, "error": f"{type(exc).__name__}: {exc}"})
    return rows


def _run_action_cases(cases: list[Mapping[str, Any]], scorer: Any, nlp: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        model = _model_from_case(case, nlp)
        rule = _rule_view(case, nlp)
        candidates = scorer.action_candidate_evidence(rule, model)
        selected = next((row.get("node_id") for row in candidates if row.get("selected")), None)
        tied = sorted(str(row.get("node_id")) for row in candidates if row.get("tied"))
        best_score = max((float(row["similarity"]) for row in candidates
                          if row.get("similarity") is not None), default=0.0)
        meets_gamma = bool(best_score > float(scorer.gamma))
        limitation_spec = case.get("expected_limitation")
        if limitation_spec:
            if case["case_id"] == "same_verb_different_object_limitation":
                limitation_observed = len(tied) > 1
            else:
                limitation_observed = meets_gamma and selected is not None
            passed = bool(limitation_observed)
            capability_accepted = False
        else:
            limitation_observed = None
            passed = bool(meets_gamma == bool(case.get("expected_meets_gamma"))
                          and (case.get("expected_selected") is None or selected == case.get("expected_selected")))
            for expected_tie in case.get("expected_tied") or []:
                passed = passed and expected_tie in tied
            if case.get("expected_candidate_reason"):
                passed = passed and any(row.get("reason") == case["expected_candidate_reason"]
                                        for row in candidates)
            capability_accepted = True
        rows.append({
            "case_id": case["case_id"],
            "kind": "action",
            "passed": bool(passed),
            "capability_accepted": capability_accepted,
            "known_limitation": limitation_spec,
            "limitation_observed": limitation_observed,
            "expected_selected": case.get("expected_selected"),
            "actual_selected": selected,
            "best_similarity": best_score,
            "meets_gamma": meets_gamma,
            "tied": tied,
            "rule_action": str(getattr(rule, "original_text", rule)),
            "rule_action_surface": getattr(rule, "action_surface", None),
            "candidates": candidates,
        })
    return rows


def _run_order_cases(cases: list[Mapping[str, Any]], scorer: Any, nlp: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        model = _model_from_case(case, nlp)
        before = build_endpoint_view(nlp, str(case["order"][0]), source="fixture_order_endpoint")
        after = build_endpoint_view(nlp, str(case["order"][1]), source="fixture_order_endpoint")
        raw = scorer.out_of_order([(before, after)], [before], model)
        denominator = int(raw.get("denominator") or 0)
        if denominator <= 0:
            actual_status = "unknown"
        else:
            actual_status = "violated" if float(raw.get("score") or 0.0) > 0.0 else "satisfied"
        rows.append({
            "case_id": case["case_id"],
            "kind": "order",
            "passed": actual_status == case.get("expected_order_status"),
            "expected": case.get("expected_order_status"),
            "actual_status": actual_status,
            "raw": raw,
            "endpoint_action_surfaces": [before.action_surface, after.action_surface],
        })
    return rows


def run_mechanism(backend: str, *, lg_model_path: str | None = None,
                  fixtures_path: Path = FIXTURES,
                  self_test_failure: bool = False) -> dict[str, Any]:
    canonical = ALLOWED_BACKENDS.get(backend)
    if canonical is None:
        raise ValueError(f"unknown backend {backend!r}; allowed: {sorted(ALLOWED_BACKENDS)}")
    import spacy  # type: ignore
    nlp = spacy.load("en_core_web_sm")
    scorer, backend_info = _build_scorer(backend, nlp, lg_model_path)

    fixtures = _load_json(fixtures_path)
    if self_test_failure:
        fixtures = copy.deepcopy(fixtures)
        if fixtures.get("action_cases"):
            fixtures["action_cases"][0]["expected_selected"] = "NodeThatCannotMatch"
            fixtures["action_cases"][0]["expected_meets_gamma"] = True

    contract_checks = _contract_checks(scorer, nlp)
    projection = _run_projection_cases(list(fixtures.get("projection_cases") or []), nlp)
    action = _run_action_cases(list(fixtures.get("action_cases") or []), scorer, nlp)
    order = _run_order_cases(list(fixtures.get("order_cases") or []), scorer, nlp)
    behavior = projection + action + order

    failed_contracts = [row["check"] for row in contract_checks if not row.get("passed")]
    failed_behavior = [row["case_id"] for row in behavior if not row.get("passed")]
    limitations = [row for row in action if row.get("limitation_observed") is not None]
    limitations_observed = [row["case_id"] for row in limitations if row.get("limitation_observed")]
    status = "pass" if not failed_contracts and not failed_behavior else "fail"
    result = {
        "schema_version": "stage3_r4_mechanism_check@1.0.0",
        "backend": backend,
        "backend_info": backend_info,
        "status": status,
        "summary": {
            "implementation_contract_checks_total": len(contract_checks),
            "implementation_contract_checks_passed": sum(1 for row in contract_checks if row.get("passed")),
            "behavior_probes_total": len(behavior),
            "behavior_probes_passed": sum(1 for row in behavior if row.get("passed")),
            "known_limitation_reproductions_total": len(limitations),
            "known_limitation_reproductions_observed": len(limitations_observed),
            "failed_contract_checks": failed_contracts,
            "failed_behavior_probes": failed_behavior,
        },
        "implementation_contract_checks": contract_checks,
        "behavior_probes": behavior,
        "known_limitation_reproductions": limitations,
        "capability_acceptance_note": (
            "Known-limitation probes are regression/development checks only; they are not "
            "counted as successful recognition capability."
        ),
        "self_test_failure_fixture": bool(self_test_failure),
    }
    return result


def _write_markdown(path: Path, result: Mapping[str, Any]) -> None:
    lines = ["# R4 independent mechanism/development check", "",
             f"- backend: `{result.get('backend')}`",
             f"- status: `{result.get('status')}`", ""]
    lines.append("## Implementation contract checks")
    lines.append("")
    for row in result.get("implementation_contract_checks") or []:
        lines.append(f"- {'PASS' if row.get('passed') else 'FAIL'} `{row.get('check')}`")
    lines.append("")
    lines.append("## Behaviour probes")
    lines.append("")
    for row in result.get("behavior_probes") or []:
        lines.append(f"- {'PASS' if row.get('passed') else 'FAIL'} `{row.get('case_id')}` ({row.get('kind')})")
    lines.append("")
    lines.append("## Known limitation reproductions")
    lines.append("")
    for row in result.get("known_limitation_reproductions") or []:
        lines.append(f"- observed={row.get('limitation_observed')} `{row.get('case_id')}`: {row.get('known_limitation')}")
    lines.append("")
    lines.append("Known-limitation reproductions are regression checks, not capability passes.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=tuple(sorted(ALLOWED_BACKENDS)), required=True)
    parser.add_argument("--lg-model-path", default=None)
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    parser.add_argument("--self-test-failure", action="store_true",
                        help="run a deliberately failing fixture and require non-zero exit")
    args = parser.parse_args()
    try:
        result = run_mechanism(args.backend, lg_model_path=args.lg_model_path,
                               fixtures_path=args.fixtures,
                               self_test_failure=args.self_test_failure)
    except ValueError as exc:
        print(f"mechanism configuration error: {exc}", file=sys.stderr)
        return 2
    if args.out_json:
        _write_json(args.out_json, result)
    if args.out_md:
        _write_markdown(args.out_md, result)
    if args.self_test_failure:
        # The deliberate failing fixture must be detected as a failure.
        return 1 if result.get("status") == "fail" else 3
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

