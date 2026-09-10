"""Evidence-preserving development successor for the three Stage-3 checks.

This is an explicitly separate method variant, not a rewrite of the frozen
Sun reconstruction or of human Gold. A temporal endpoint is not an additional
mandatory action. Missing evidence is unknown, not a zero violation score.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from bpc_hybrid.sun_stage3.sun_scorer import SunScorer

METHOD = "s3_evidence_checks@1.0.0"
TYPES = ("missing_action", "incorrect_actor", "out_of_order")


def project_confirmed_temporal_notes(records: dict, gold_doc: dict) -> tuple[dict, dict]:
    """Compile only explicit directions with two unique verbatim endpoints.

    Accepted human-note grammar: `A 在 B 之前` or `A 先于 B`. The endpoints
    must occur uniquely in the SAME confirmed sentence. No temporal NLP,
    pronoun resolution, new actor/action, or violation decision is inferred.
    The output is a runtime projection with its own provenance, never Gold.
    """
    out = copy.deepcopy(records)
    accepted, rejected = [], []
    for row in gold_doc["records"]:
        for note in row.get("temporal_suggestions", []):
            first = re.split(r"[；。]", note, maxsplit=1)[0].strip()
            match = (re.fullmatch(r"(.+?)\s+在\s+(.+?)\s+之前", first)
                     or re.fullmatch(r"(.+?)\s+先于\s+(.+)", first))
            base = {"sample_id": row["sample_id"], "rule_id": row["rule_id"], "note": note}
            if not match:
                rejected.append({**base, "reason": "unsupported_explicit_direction"})
                continue
            before, after = (s.strip() for s in match.groups())
            text = row["sentence_text"]
            if any(not s or text.count(s) != 1 for s in (before, after)):
                rejected.append({**base, "reason": "endpoint_not_unique_verbatim"})
                continue
            if before == after or row["rule_id"] not in out:
                rejected.append({**base, "reason": "invalid_relation"})
                continue
            anchors = {name: {"text": value, "start": text.index(value),
                              "end": text.index(value) + len(value)}
                       for name, value in (("before", before), ("after", after))}
            relation = (before, after)
            existing = out[row["rule_id"]].setdefault("order_relations", [])
            if relation not in [tuple(x) for x in existing]:
                existing.append(relation)
            accepted.append({**base, **anchors, "source": "confirmed_temporal_note",
                             "creates_mandatory_action": False})
    return out, {"accepted": accepted, "rejected": rejected,
                 "gold_modified": False, "projection_is_gold": False}


class EvidenceChecks(SunScorer):
    """Keep frozen thresholds, add traceable surface matching and check states.

    The action matcher first recognizes the same predicate plus a shared
    content word. Remaining cases retain the frozen similarity backend and
    gamma. Actor checks use the matched activity's executor labels, never its
    business objects, with lane ownership taking precedence over the pool.
    This executor policy is a development extension of the literal Sun rule.
    """

    def __init__(self, sim, tau, gamma, theta, nlp):
        super().__init__(sim, tau, gamma, theta, nlp=nlp)
        self._surface_cache = {}

    def _surface(self, text):
        if text not in self._surface_cache:
            doc = self.nlp(text)
            verbs = [t for t in doc if t.pos_ == "VERB" and t.dep_ == "ROOT"]
            if not verbs:
                verbs = [t for t in doc if t.pos_ == "VERB"][:1]
            head = verbs[0] if verbs else None
            content = {t.lemma_.casefold() for t in doc
                       if t.pos_ in {"NOUN", "PROPN", "NUM"} and not t.is_stop}
            negative = any(t.dep_ == "neg" for t in doc)
            self._surface_cache[text] = (head.lemma_.casefold() if head else None,
                                         content, negative)
        return self._surface_cache[text]

    def action_match(self, rule_action, model):
        candidates = []
        predicate, objects, negative = self._surface(rule_action)
        for activity in model.actions:
            label = activity.get("name", "")
            if not label:
                continue
            other, other_objects, other_negative = self._surface(label)
            shared = sorted(objects & other_objects)
            exact = self._lemma(rule_action).casefold() == self._lemma(label).casefold()
            surface = (predicate is not None and predicate == other and shared
                       and negative == other_negative)
            # Predicate-only matching would collapse different recipients or
            # objects (e.g. notify a customer vs notify an authority).
            strategy = "exact_lemma" if exact else "predicate_and_content" if surface else "frozen_similarity"
            score = 1.0 if exact or surface else self.sim.text_pair(self._lemma(rule_action), self._lemma(label))
            candidates.append({"activity_id": activity["id"], "label": label,
                               "score": float(score), "strategy": strategy,
                               "shared_content": shared})
        candidates.sort(key=lambda x: (-x["score"], x["activity_id"]))
        if not candidates:
            return {"mapped": False, "reason": "no_process_actions", "candidates": []}
        best = candidates[0]
        if best["score"] <= self.gamma:
            return {"mapped": False, "reason": "action_mapping_below_gamma", "best": best,
                    "candidates": candidates[:3]}
        ties = [c for c in candidates if abs(c["score"] - best["score"]) < 1e-10]
        if len(ties) > 1:
            return {"mapped": False, "reason": "ambiguous_action_mapping", "best": best,
                    "candidates": ties}
        return {"mapped": True, "reason": None, "best": best, "candidates": candidates[:3]}

    def _best_action_match(self, rule_action, model):
        result = self.action_match(rule_action, model)
        best = result.get("best")
        return (best["label"], best["score"]) if best else (None, 0.0)

    @staticmethod
    def _result(details, absent_reason):
        observed = [d for d in details if d["observable"]]
        unresolved = len(details) - len(observed)
        violated = sum(d.get("violated", False) for d in observed)
        if violated:
            status = "violation"
        elif unresolved or not observed:
            status = "unknown"
        else:
            status = "satisfied"
        return {"score": (violated / len(observed)) if status != "unknown" else None,
                "observable": bool(observed), "complete": bool(observed) and not unresolved,
                "status": status, "denominator": len(observed), "violations": violated,
                "unresolved": unresolved, "reason": absent_reason if not details else
                next((d.get("reason") for d in details if not d["observable"]), None),
                "details": details}

    def missing_action(self, rule_actions, model):
        details = []
        for action in rule_actions:
            match = self.action_match(action, model)
            ambiguous = match["reason"] == "ambiguous_action_mapping"
            details.append({"rule_action": action, "match": match,
                            "observable": not ambiguous, "reason": match["reason"],
                            "violated": not match["mapped"] and not ambiguous})
        return self._result(details, "empty_rule_action_set")

    def _executors(self, model, activity_id):
        record = getattr(model, "record", {})
        lanes = [x["name"].strip() for x in record.get("lanes", [])
                 if x.get("name", "").strip() and activity_id in x.get("flow_node_refs", [])]
        if lanes:
            return list(dict.fromkeys(lanes))
        return list(dict.fromkeys(model.action_actor_names.get(activity_id, [])))

    def _same_role(self, required, actual):
        def canonical(text):
            value = " ".join(t.lemma_.casefold() for t in self.nlp(text)
                             if not t.is_punct and not t.is_space and t.lower_ not in {"a", "an", "the"})
            # Explicit surface aliases, not per-item inferred actor decisions.
            return {"data controller": "controller", "data processor": "processor"}.get(value, value)
        if canonical(required) == canonical(actual):
            return True
        return self.sim.text_pair(self._lemma(required), self._lemma(actual)) >= self.theta

    def incorrect_actor(self, rule_actions, rule_actors, model, actor_action_pairs=None):
        pairs = actor_action_pairs
        if pairs is None and len(rule_actions) == len(rule_actors) == 1:
            pairs = [{"actor": rule_actors[0], "action": rule_actions[0]}]
        details = []
        seen = set()
        for pair in pairs or []:
            key = (pair.get("actor"), pair.get("action"))
            if key in seen:
                continue
            seen.add(key)
            if key[0] not in rule_actors or key[1] not in rule_actions:
                details.append({"pair": pair, "observable": False, "reason": "invalid_actor_action_link"})
                continue
            match = self.action_match(key[1], model)
            owners = self._executors(model, match["best"]["activity_id"]) if match["mapped"] else []
            details.append({"pair": pair, "match": match, "executors": owners,
                            "observable": bool(owners),
                            "reason": match["reason"] if not match["mapped"] else
                            (None if owners else "no_matching_process_executor"),
                            "violated": bool(owners) and not any(self._same_role(key[0], o) for o in owners)})
        linked = {p.get("actor") for p in pairs or []}
        for actor in sorted(set(rule_actors) - linked):
            details.append({"actor": actor, "observable": False, "reason": "missing_actor_action_link"})
        return self._result(details, "missing_rule_actor_action_map")

    def out_of_order(self, rule_order_relations, rule_actions, model):
        details = []
        for before, after in rule_order_relations:
            left, right = self.action_match(before, model), self.action_match(after, model)
            entry = {"constraint": [before, after], "before": left, "after": right}
            if not left["mapped"] or not right["mapped"]:
                details.append({**entry, "observable": False, "reason": "order_endpoint_unmapped"})
                continue
            a, b = left["best"]["activity_id"], right["best"]["activity_id"]
            if a == b:
                details.append({**entry, "observable": False, "reason": "order_endpoints_same_activity"})
                continue
            forward, backward = model.is_reachable(a, b), model.is_reachable(b, a)
            details.append({**entry, "observable": True, "reason": None,
                            "forward_reachable": forward, "backward_reachable": backward,
                            "violated": not (forward and not backward)})
        return self._result(details, "missing_rule_order_relations")


def score_items(items: list[dict], records: dict, models: dict, scorer: EvidenceChecks) -> list[dict]:
    """Input whitelist: labels, evidence and candidate fields never enter prediction."""
    out = []
    for item in sorted(items, key=lambda x: x["item_id"]):
        rid, pid, check = item["rule_id"], item["process_id"], item["check_type"]
        if check not in TYPES:
            raise ValueError(f"unsupported check: {check}")
        record, model = records[rid], models[pid]
        if record.get("failed"):
            result = scorer._result([], "external_rule_record_failure")
        elif check == "incorrect_actor":
            result = scorer.incorrect_actor(record["actions"], record["actors"], model,
                                             record.get("actor_action_pairs"))
        elif check == "out_of_order":
            result = scorer.out_of_order(record["order_relations"], record["actions"], model)
        else:
            result = scorer.missing_action(record["actions"], model)
        out.append({"item_id": item["item_id"], "process_id": pid, "rule_id": rid,
                    "check_type": check, "method": METHOD, "result": result,
                    "predicted_violation_type": check if result["status"] == "violation" else None})
    return out


def evaluate_items(rows: list[dict], gold_items: list[dict]) -> dict:
    """Retain every item, separate violation, satisfied and unknown outcomes.

    Diagnostic comparison against the OLD labels, not a new validated main
    table. This evaluator also supports real negative controls without treating
    an unknown response as a correct compliant answer.
    """
    gold = {x["item_id"]: x for x in gold_items}
    if len(gold) != len(gold_items) or len({r["item_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate evaluation item ids")
    if set(gold) != {r["item_id"] for r in rows}:
        raise ValueError("prediction / Gold membership mismatch")
    per_type = {}
    for check in TYPES:
        tp = fp = fn = tn = unknown = support = observed = 0
        for row in rows:
            g = gold[row["item_id"]]["decision_violation_type"]
            status = row["result"]["status"]
            pred = row["predicted_violation_type"]
            tp += g == check and pred == check
            fp += g != check and pred == check
            fn += g == check and pred != check
            if row["check_type"] == check:
                support += 1
                unknown += status == "unknown"
                observed += row["result"]["observable"]
                tn += g is None and status == "satisfied"
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        per_type[check] = {"support": support, "tp": tp, "fp": fp, "fn": fn,
                           "tn": tn, "unknown": unknown, "observable_checks": observed,
                           "precision": precision, "recall": recall,
                           "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
    return {"count": len(rows), "per_type": per_type,
            "macro_f1": sum(v["f1"] for v in per_type.values()) / len(TYPES),
            "unknown_total": sum(x["result"]["status"] == "unknown" for x in rows),
            "dropped_items": 0, "claim_scope": "diagnostic_old_labels_scope_unresolved"}
