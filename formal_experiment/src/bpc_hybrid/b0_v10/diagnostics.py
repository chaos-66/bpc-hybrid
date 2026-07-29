"""Diagnostics: residual metrics split + any-overlap endpoint ownership."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from bpc_hybrid.stage2_evaluation import _char_iou
from bpc_hybrid.stage2_evaluation_v3 import clause_iou_pairs


def residual_metrics_split(
    *,
    supported_pairs: list[tuple[str, str]],
    abstained_gold: int,
    unmatched_gold: int,
    extra_pred: int,
) -> dict[str, Any]:
    """supported_pairs is list of (gold_label, pred_label) for supported only."""
    tp = sum(1 for g, p in supported_pairs if g == p)
    wrong = sum(1 for g, p in supported_pairs if g != p)
    supported_n = len(supported_pairs)
    # conditional-on-supported
    cond_p = tp / (tp + wrong) if tp + wrong else 0.0
    cond_r = tp / supported_n if supported_n else 0.0
    cond_f1 = 2 * cond_p * cond_r / (cond_p + cond_r) if cond_p + cond_r else 0.0
    # coverage-adjusted: abstain + unmatched count as miss
    denom = supported_n + abstained_gold + unmatched_gold
    cov_r = tp / denom if denom else 0.0
    cov_p = tp / (tp + wrong + extra_pred) if (tp + wrong + extra_pred) else 0.0
    cov_f1 = 2 * cov_p * cov_r / (cov_p + cov_r) if cov_p + cov_r else 0.0
    return {
        "conditional_on_supported": {
            "tp": tp,
            "wrong_label": wrong,
            "supported_n": supported_n,
            "precision": cond_p,
            "recall": cond_r,
            "f1": cond_f1,
        },
        "coverage_adjusted": {
            "tp": tp,
            "abstained_gold": abstained_gold,
            "unmatched_gold": unmatched_gold,
            "extra_pred": extra_pred,
            "precision": cov_p,
            "recall": cov_r,
            "f1": cov_f1,
        },
        "supported_coverage": supported_n / max(supported_n + abstained_gold, 1),
        "abstention_count": abstained_gold,
    }


def actor_action_any_overlap_endpoint_diagnostic(
    gold_records: Sequence[Mapping[str, Any]],
    pred_records: Sequence[Mapping[str, Any]],
    *,
    minimum_clause_iou: float = 0.5,
) -> dict[str, Any]:
    gold_by = {g["sample_id"]: g for g in gold_records}
    raw = actor_al = action_al = both = own_tp = end_fail = own_fail = 0

    def find_best(span, candidates):
        best_i, best_iou = None, 0.0
        for i, c in enumerate(candidates):
            iou = _char_iou(span, c)
            if iou > best_iou:
                best_iou, best_i = iou, i
        return best_i, best_iou

    for pref in pred_records:
        gold = gold_by[pref["sample_id"]]
        gcls = gold.get("clauses") or []
        pcls = pref.get("clauses") or []
        pairs, _, _, _ = clause_iou_pairs(gcls, pcls, minimum_iou=minimum_clause_iou)
        p_to_g = {pi: gi for gi, pi in pairs}
        for pi, pcl in enumerate(pcls):
            actors = pcl.get("actors") or []
            actions = pcl.get("actions") or []
            actor_by_id = {a.get("id"): a for a in actors}
            action_by_id = {a.get("id"): a for a in actions}
            for e in pcl.get("actor_action_map") or []:
                raw += 1
                a_sp = actor_by_id.get(e.get("actor_id"))
                act_sp = action_by_id.get(e.get("action_id"))
                if a_sp is None or act_sp is None:
                    end_fail += 1
                    continue
                gi = p_to_g.get(pi)
                if gi is None:
                    end_fail += 1
                    continue
                gcl = gcls[gi]
                g_actors = gcl.get("actors") or []
                g_actions = gcl.get("actions") or []
                ai, a_iou = find_best(a_sp, g_actors)
                bi, b_iou = find_best(act_sp, g_actions)
                if a_iou > 0:
                    actor_al += 1
                if b_iou > 0:
                    action_al += 1
                if a_iou > 0 and b_iou > 0 and ai is not None and bi is not None:
                    both += 1
                    g_actor_id = g_actors[ai].get("id")
                    g_action_id = g_actions[bi].get("id")
                    gold_edges = gcl.get("actor_action_map") or []
                    hit = any(
                        ge.get("actor_id") == g_actor_id and ge.get("action_id") == g_action_id
                        for ge in gold_edges
                    )
                    if hit:
                        own_tp += 1
                    else:
                        own_fail += 1
                else:
                    end_fail += 1
    return {
        "raw_predicted_edge_count": raw,
        "actor_endpoint_alignable": actor_al,
        "action_endpoint_alignable": action_al,
        "both_endpoints_alignable": both,
        "any_overlap_mapped_ownership_tp": own_tp,
        "exact_mapped_ownership_tp_DEPRECATED_NAME": own_tp,  # misnomer retained for compat
        "endpoint_failure": end_fail,
        "ownership_failure": own_fail,
        "note": "endpoint match uses any character-span overlap (IoU>0), not exact boundary; ownership still requires specific Gold actor_id+action_id pair",
        "match_rule": "any_overlap_endpoint_plus_exact_id_pair",
    }


def actor_action_exact_endpoint_diagnostic(*args, **kwargs):
    """Deprecated name; returns any-overlap endpoint diagnostic."""
    return actor_action_any_overlap_endpoint_diagnostic(*args, **kwargs)
