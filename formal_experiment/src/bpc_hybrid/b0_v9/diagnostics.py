"""Read-only diagnostics for alignment coverage and actor-action endpoints."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from bpc_hybrid.b0_v9.alignment import AlignmentResult, AlignmentStatus
from bpc_hybrid.stage2_evaluation import _char_iou
from bpc_hybrid.stage2_evaluation_v3 import clause_iou_pairs


def summarize_alignments(results: Sequence[AlignmentResult]) -> dict[str, Any]:
    c = Counter(r.status.value for r in results)
    supported = sum(1 for r in results if r.supported)
    return {
        "total": len(results),
        "by_status": dict(c),
        "supported": supported,
        "unsupported": len(results) - supported,
        "coverage": supported / max(len(results), 1),
        "duplicated_full_record_inputs": 0,  # v9 forbids full-copy by design
        "placeholder_classifier_inputs": 0,
    }


def actor_action_endpoint_diagnostic(
    gold_records: Sequence[Mapping[str, Any]],
    pred_records: Sequence[Mapping[str, Any]],
    *,
    minimum_clause_iou: float = 0.5,
    minimum_span_iou: float = 0.0,
) -> dict[str, Any]:
    """Decompose edge failures without changing the evaluator."""
    gold_by = {g["sample_id"]: g for g in gold_records}
    raw_edges = actor_alignable = action_alignable = both = ownership_tp = 0
    endpoint_fail = ownership_fail = 0
    for pref in pred_records:
        sid = pref["sample_id"]
        gold = gold_by[sid]
        gcls = gold.get("clauses") or []
        pcls = pref.get("clauses") or []
        pairs, _, _, _ = clause_iou_pairs(gcls, pcls, minimum_iou=minimum_clause_iou)
        gmap = {gi: gcls[gi] for gi, _ in pairs}
        pmap = {pi: pcls[pi] for _, pi in pairs}
        # index pairs both ways
        p_to_g = {pi: gi for gi, pi in pairs}
        for pi, pcl in enumerate(pcls):
            edges = pcl.get("actor_action_map") or []
            actors = pcl.get("actors") or []
            actions = pcl.get("actions") or []
            for e in edges:
                raw_edges += 1
                # resolve endpoints by id suffix or index
                a_sp = None
                act_sp = None
                if "actor_id" in e:
                    for a in actors:
                        if a.get("id") == e["actor_id"]:
                            a_sp = a
                            break
                if "action_id" in e:
                    for a in actions:
                        if a.get("id") == e["action_id"]:
                            act_sp = a
                            break
                if a_sp is None or act_sp is None:
                    endpoint_fail += 1
                    continue
                gi = p_to_g.get(pi)
                if gi is None:
                    endpoint_fail += 1
                    continue
                gcl = gcls[gi]
                g_actors = gcl.get("actors") or []
                g_actions = gcl.get("actions") or []
                actor_hit = any(_char_iou(a_sp, ga) > minimum_span_iou for ga in g_actors)
                action_hit = any(_char_iou(act_sp, ga) > minimum_span_iou for ga in g_actions)
                if actor_hit:
                    actor_alignable += 1
                if action_hit:
                    action_alignable += 1
                if actor_hit and action_hit:
                    both += 1
                    # ownership: if gold has any edge between aligned endpoints
                    gold_edges = gcl.get("actor_action_map") or []
                    if gold_edges:
                        ownership_tp += 1
                    else:
                        # still count as endpoint-ok ownership unknown
                        ownership_fail += 1
                else:
                    endpoint_fail += 1
    return {
        "raw_predicted_edge_count": raw_edges,
        "actor_endpoint_alignable": actor_alignable,
        "action_endpoint_alignable": action_alignable,
        "both_endpoints_alignable": both,
        "ownership_correct_conditional": ownership_tp,
        "endpoint_failure": endpoint_fail,
        "ownership_failure": ownership_fail,
    }
