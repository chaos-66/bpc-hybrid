# -*- coding: utf-8 -*-
"""S3.7 real-rule diagnostic **correction** v1: a bounded repair of the evidence
association, reason classification and coverage accounting of
``s3_real_rule_diagnostic_v1``.

What this runner does, in this order:

1. reads the committed v1 diagnostic artifacts (66 predictions, 122 mapping
   evidence rows, scope review, summary, manifest) **read-only** and proves they
   are byte-unchanged against the v1 manifest bindings;
2. re-reads the same frozen inputs (confirmed human rule capsule, Gold rule
   records, Stage-2 legal text, inference items, the 7 original BPMNs, the
   versioned configuration) and rebuilds the *rule side* of every checked
   requirement with the frozen converter only - no checker is invoked for that;
3. rebuilds the de-duplicated evidence with **corrected identities** (an
   actor-action pair now carries its linked action requirement), **corrected
   names** (a candidate's executors are never called the executors of a matched
   activity), **corrected states** (an unmatched order endpoint has no known node
   kind; a clause-level aggregate is never presented as a per-pair verdict) and
   **separate reference/unique counts** per requirement family;
4. recovers the two actor-action associations that v1 merged away by calling the
   frozen checkers **four** times - ``IncorrectActor`` for v026 and v032, once per
   method - and refuses to continue if the native result disagrees with the
   stored prediction;
5. writes ``mapping_evidence.jsonl``, ``summary.json``, ``corrections.json`` and
   ``manifest.json`` into a **new** directory next to the v1 run.  The v1 runner,
   tests, predictions, report and manifest are never touched.

Boundaries: this is still a development diagnostic on real legal-rule input.  It
does not run a new batch experiment, does not change any prediction, checker,
Gold, threshold, rule input or human answer, makes **zero** real LLM/API calls,
and never claims a performance improvement.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

RUN_ID = "s3_real_rule_diagnostic_corrections_v1"
SUPERSEDES_RUN_ID = "s3_real_rule_diagnostic_v1"
SCHEMA_EVIDENCE = "s3_real_rule_diagnostic_corrected_evidence@1.0.0"
SCHEMA_SUMMARY = "s3_real_rule_diagnostic_corrected_summary@1.0.0"
SCHEMA_CORRECTIONS = "s3_real_rule_diagnostic_corrections@1.0.0"
SCHEMA_MANIFEST = "s3_real_rule_diagnostic_corrections_manifest@1.0.0"

V1_RUNNER = SCRIPTS / "run_s3_real_rule_diagnostic_v1.py"
V1_DIR = ROOT / "outputs/development" / SUPERSEDES_RUN_ID
V1_FILES = ("predictions.jsonl", "mapping_evidence.jsonl", "scope_review.json",
            "summary.json", "manifest.json")

OUT_DIR = ROOT / "outputs/development" / RUN_ID
EVIDENCE_FILE = OUT_DIR / "mapping_evidence.jsonl"
SUMMARY_FILE = OUT_DIR / "summary.json"
CORRECTIONS_FILE = OUT_DIR / "corrections.json"
MANIFEST_FILE = OUT_DIR / "manifest.json"
OUT_FILES = ("mapping_evidence.jsonl", "summary.json", "corrections.json", "manifest.json")

# Exactly four native check invocations are authorised for this repair, and only
# for the two items whose actor-action associations the v1 evidence key merged.
RECOMPUTE_ITEMS = ("v026", "v032")
RECOMPUTE_CHECK_TYPE = "incorrect_actor"
MAX_NATIVE_CALLS = 4

FAMILIES = ("action_requirement", "actor_action_pair", "order_endpoint")

# Corrected state vocabulary.  ``evidence_supports_judgment`` is deliberately
# absent: a mapping state and a judgment-support claim are different objects.
CORRECTED_STATES = {
    "action_requirement": (
        "mapped_unique",
        "expression_differs_unresolved",
        "multiple_candidates_insufficient",
        "structure_parse_insufficient",
        "native_requirement_field_absent",
    ),
    "actor_action_pair": (
        "executor_comparison_performed",
        "linked_action_not_reliably_mapped",
        "matched_activity_executors_unobservable",
    ),
    "order_endpoint": (
        "matched_to_activity",
        "matched_to_event",
        "unmatched_kind_unknown",
        "endpoint_source_not_located",
    ),
}
ITEM_LEVEL_STATES = (
    "rule_has_no_action_requirement",
    "rule_has_no_actor_requirement",
    "rule_has_no_order_relation",
)

DEDUP_KEY_FIELDS = {
    "action_requirement": ["method", "family", "process_id", "rule_id", "requirement_text"],
    "actor_action_pair": ["method", "family", "process_id", "rule_id", "actor_requirement",
                          "linked_action_requirement"],
    "order_endpoint": ["method", "family", "process_id", "rule_id", "order_position",
                       "endpoint_text", "order_constraint"],
}

V1_KEY_FIELDS = ["method", "kind", "process_id", "requirement_text", "rule_ids"]

FAMILY_REFERENCE_KEY = {
    "action_requirement": "action_requirement_references",
    "actor_action_pair": "actor_action_pair_references",
    "order_endpoint": "order_endpoint_references",
}


# ---------------------------------------------------------------------------
# small utilities
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def git(args: list[str]) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout.strip()


def file_binding(rel: str) -> dict:
    """Same binding convention as the v1 run (raw bytes are authoritative)."""
    path = ROOT / rel
    raw = path.read_bytes()
    filtered = subprocess.run(["git", "hash-object", f"--path={rel}", str(path)], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip()
    plain = subprocess.run(["git", "hash-object", "--no-filters", str(path)], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    return {"bytes": len(raw), "crlf_pairs": raw.count(b"\r\n"),
            "sha256_raw_working_tree": hashlib.sha256(raw).hexdigest(),
            "git_blob_sha1_raw": plain, "git_blob_sha1_after_clean_filter": filtered,
            "raw_bytes_equal_committed_bytes": plain == filtered}


def load_v1_runner():
    spec = importlib.util.spec_from_file_location("s3_real_rule_diagnostic_v1_runner", V1_RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


V1 = load_v1_runner()


# ---------------------------------------------------------------------------
# phase 0 - read the committed v1 diagnostic (read-only)
# ---------------------------------------------------------------------------


def read_v1_artifacts() -> dict:
    manifest = read_json(V1_DIR / "manifest.json")
    predictions = read_jsonl(V1_DIR / "predictions.jsonl")
    evidence = read_jsonl(V1_DIR / "mapping_evidence.jsonl")
    summary = read_json(V1_DIR / "summary.json")
    for name in V1_FILES:
        if not (V1_DIR / name).is_file():
            raise RuntimeError(f"missing v1 artifact {name}")
    if len(predictions) != 66:
        raise RuntimeError("the v1 diagnostic must keep 33 items x 2 methods = 66 rows")
    if len({row["item_id"] for row in predictions}) != 33:
        raise RuntimeError("the 33 legacy item ids must be preserved")
    stored_sha = sha256_file(V1_DIR / "predictions.jsonl")
    bound_sha = manifest["results"]["predictions"]["sha256"]
    if stored_sha != bound_sha:
        raise RuntimeError("the committed v1 predictions do not match their own manifest binding")
    return {
        "manifest": manifest, "predictions": predictions, "evidence": evidence,
        "summary": summary,
        "sha256": {name: sha256_file(V1_DIR / name) for name in V1_FILES},
        "predictions_sha256": stored_sha,
        "predictions_bound_sha256": bound_sha,
        "evidence_index": {row["evidence_id"]: row for row in evidence},
    }


# ---------------------------------------------------------------------------
# phase 1 - rule side (frozen converter only; no checker is invoked)
# ---------------------------------------------------------------------------


def find_source_spans(rule_inputs: dict, rule_id: str, text: str) -> list[dict]:
    """**All** confirmed clause spans a requirement text occurs in.

    The v1 diagnostic returned the first match only, which turned a shared
    requirement into a single arbitrary provenance anchor.  The corrected record
    keeps the full list.
    """
    spans: list[dict] = []
    seen = set()
    for record in rule_inputs["gold_rules"]["records"]:
        if record["rule_id"] != rule_id:
            continue
        for clause in record["clauses"]:
            for collection, kind in (("actions", "action"), ("actors", "actor")):
                for span in clause.get(collection) or []:
                    if span.get("text") != text:
                        continue
                    key = (record["sample_id"], clause["clause_id"], clause["item_id"],
                           span["start"], span["end"])
                    if key in seen:
                        continue
                    seen.add(key)
                    spans.append({
                        "kind": kind, "sample_id": record["sample_id"],
                        "clause_id": clause["clause_id"], "clause_item_id": clause["item_id"],
                        "modality": clause["modality"]["label"],
                        "span": {"start": span["start"], "end": span["end"]},
                    })
    spans.sort(key=lambda item: (item["sample_id"], item["clause_id"], item["span"]["start"]))
    return spans


def temporal_note_for(rule_inputs: dict, rule_id: str, text: str) -> dict | None:
    for note in rule_inputs["temporal"]["accepted"]:
        if note.get("rule_id") != rule_id:
            continue
        for side in ("before", "after"):
            if (note.get(side) or {}).get("text") == text:
                return note
    return None


def requirement_units(rule_inputs: dict, rule_id: str, check_type: str) -> list[dict]:
    """The rule requirements a designated check type actually evaluates."""
    record = rule_inputs["records"][rule_id]
    if check_type == "out_of_order":
        units = []
        for before, after in record["order_relations"]:
            for position, text in (("before", before), ("after", after)):
                units.append({"family": "order_endpoint", "kind": "order_" + position,
                              "text": text, "order_position": position,
                              "order_constraint": [before, after]})
        return units
    units = [{"family": "action_requirement", "kind": "action", "text": text}
             for text in record["actions"]]
    if check_type == "incorrect_actor":
        for pair in record.get("actor_action_pairs") or []:
            units.append({"family": "actor_action_pair", "kind": "actor", "text": pair["actor"],
                          "linked_action_requirement": pair["action"]})
    return units


def dedup_key(unit: dict, method: str, process_id: str, rule_id: str) -> dict:
    base = {"method": method, "family": unit["family"], "process_id": process_id,
            "rule_id": rule_id}
    if unit["family"] == "action_requirement":
        base["requirement_text"] = unit["text"]
    elif unit["family"] == "actor_action_pair":
        base["actor_requirement"] = unit["text"]
        base["linked_action_requirement"] = unit["linked_action_requirement"]
    else:
        base["order_position"] = unit["order_position"]
        base["endpoint_text"] = unit["text"]
        base["order_constraint"] = list(unit["order_constraint"])
    return base


def v1_key(unit: dict, method: str, process_id: str, rule_id: str) -> dict:
    """The v1 evidence key, reproduced exactly to expose the v1 merge behaviour."""
    return {"method": method, "kind": unit["kind"], "process_id": process_id,
            "requirement_text": unit["text"], "rule_ids": [rule_id]}


def corrected_evidence_id(key: dict) -> str:
    """New, versioned id namespace: a corrected id can never be mistaken for a v1
    id, and every v1 -> corrected association is written down explicitly."""
    return "cev_" + sha1_text(canonical(key))[:16]


def rule_scope(rule_inputs: dict, rule_id: str, sources: list[dict],
               extra_sentences: list[str]) -> dict:
    record = rule_inputs["records"][rule_id]
    sentences = sorted({source["sample_id"] for source in sources} | set(extra_sentences))
    return {
        "rule_id": rule_id,
        "rule_ids": [rule_id],
        "source_sentences": sentences,
        "source_clause_ids": sorted({source["clause_id"] for source in sources}),
        "conversion_modality": record.get("modality"),
        "conversion_include_modalities": list(V1.INCLUDE_MODALITIES),
    }


def condition_profile(rule_inputs: dict) -> dict:
    """Per-rule applicability structure aggregated over **all** sentences.

    v1's ``clause_has_conditions`` returned after the first sentence record of a
    rule, so later sentences could not contribute.  The corrected profile scans
    every sentence and every clause and, because the frozen converter and both
    scorers consume none of these elements, records the capability status
    ``not_evaluated`` instead of implying "no conditions".
    """
    per_rule: dict[str, dict] = {}
    for rule_id in sorted({record["rule_id"] for record in rule_inputs["gold_rules"]["records"]}):
        rows = [record for record in rule_inputs["gold_rules"]["records"]
                if record["rule_id"] == rule_id]
        clauses = [clause for record in rows for clause in record["clauses"]]
        first = rows[0]["clauses"] if rows else []
        per_rule[rule_id] = {
            "sentence_count": len(rows),
            "clause_count": len(clauses),
            "clauses_with_conditions": sum(bool(clause["conditions"]) for clause in clauses),
            "clauses_with_constraints": sum(bool(clause["constraints"]) for clause in clauses),
            "clauses_with_exceptions": sum(bool(clause["exceptions"]) for clause in clauses),
            "condition_spans": sum(len(clause["conditions"]) for clause in clauses),
            "constraint_spans": sum(len(clause["constraints"]) for clause in clauses),
            "exception_spans": sum(len(clause["exceptions"]) for clause in clauses),
            "first_sentence_clause_count": len(first),
            "first_sentence_v1_boolean": any(clause["conditions"] or clause["constraints"]
                                             or clause["exceptions"] for clause in first),
        }
    return per_rule


# ---------------------------------------------------------------------------
# phase 2 - corrected states
# ---------------------------------------------------------------------------


def classify_action(payload: dict) -> dict:
    """Action-requirement state from the requirement's own return payload."""
    mapped = payload.get("mapped")
    codes = set(payload.get("reason_codes") or [])
    tier = payload.get("match_tier")
    if mapped is None:
        state = "native_requirement_field_absent"
    elif mapped:
        state = "mapped_unique"
    elif codes & {"exact_label_tie", "predicate_object_agreement_tie"} or tier in {
            "structure_undetermined", "frozen_similarity_tie", "ambiguous_action_mapping"}:
        state = "multiple_candidates_insufficient"
    elif codes & {"requirement_content_not_parsed", "partial_object_overlap",
                  "required_object_content_absent", "object_terms_possibly_equivalent"}:
        state = "structure_parse_insufficient"
    else:
        state = "expression_differs_unresolved"
    return {
        "state": state,
        "native_match_tier": tier,
        "native_reason_codes": sorted(codes),
        "node_id_claimed": None,
        "node_kind_claimed": None,
        "node_kind_note": "the v1 payload records the candidate list but not the matched node id "
                          "of a mapped action requirement, so no node kind is claimed here",
        "judgment_support": {
            "complete": bool(mapped),
            "basis": "designated CheckMissingAction evidence for this one requirement: a mapped "
                     "requirement is observed in the process, an unmapped one is not",
            "missing": [] if mapped else ["requirement_reliably_mapped_to_a_process_node"],
        },
    }


def classify_actor(pair_evidence: dict) -> dict:
    """Actor-action-pair state.

    ``violated=false`` is never positive evidence: it is the default when the check
    could not observe the executors at all.  A unit reaches
    ``executor_comparison_performed`` only when the check had the information it
    needs, the linked activity was reliably determined and the actual executors of
    that activity were observable.
    """
    if not pair_evidence.get("linked_action_mapped"):
        state = "linked_action_not_reliably_mapped"
        missing = ["linked_action_reliably_mapped_to_a_process_node"]
    elif not pair_evidence.get("executors_observed"):
        state = "matched_activity_executors_unobservable"
        missing = ["matched_activity_executor_ownership_observed"]
    else:
        state = "executor_comparison_performed"
        missing = []
    return {
        "state": state,
        "executor_comparison_performed": state == "executor_comparison_performed",
        "violated_field": pair_evidence.get("violated"),
        "violated_is_positive_evidence": False,
        "aggregation_level": pair_evidence.get("aggregation_level"),
        "per_pair_native_field_present": pair_evidence.get("per_pair_native_field_present"),
        "judgment_support": {
            "complete": state == "executor_comparison_performed",
            "basis": "IncorrectActor needs the rule-side actor-action link, a reliably matched "
                     "activity and the observable executors of that activity",
            "missing": missing,
        },
    }


def classify_endpoint(node_match: dict, source_state: str) -> dict:
    """Order-endpoint state.

    ``SunProcessModel.actions`` puts activities **and** events into the candidate
    list, so an unmatched endpoint has **no** known node kind: the recorded best
    candidate is not the endpoint.  Matching an event is not automatically a
    failure either; whether the node can carry an order judgement depends on the
    frozen model's representation and reachability, which is recorded separately.
    """
    if node_match.get("mapped"):
        kind = node_match.get("node_kind")
        if kind == "activity":
            match_state = "matched_to_activity"
        elif kind == "event":
            match_state = "matched_to_event"
        else:
            match_state = "unmatched_kind_unknown"
    else:
        match_state = "unmatched_kind_unknown"
    combined = "endpoint_source_not_located" if source_state == "not_located" else match_state
    return {
        "match_state": match_state,
        "match_state_basis": ("real frozen-model node kind of the matched node"
                              if match_state.startswith("matched_to_")
                              else "no node matched, therefore no node kind can be established"),
        "source_state": source_state,
        "combined_state": combined,
        "node_kind_claimed": node_match.get("node_kind") if node_match.get("mapped") else None,
        "candidate_node_kind_recorded": node_match.get("candidate_node_kind"),
        "candidate_is_not_the_endpoint": True,
        "can_support_order_judgement": node_match.get("can_support_order_judgement"),
        "order_judgement_basis": node_match.get("order_judgement_basis"),
        "judgment_support": {
            "complete": bool(node_match.get("can_support_order_judgement")),
            "basis": "an order constraint is judgeable only when both endpoints map to distinct "
                     "nodes and the frozen reachability table is evaluated for the pair",
            "missing": node_match.get("judgment_missing") or [],
        },
    }


# ---------------------------------------------------------------------------
# phase 3 - native recovery of the merged actor-action associations
# ---------------------------------------------------------------------------


def extract_pair_evidence(method: str, raw: dict, record: dict, model) -> list[dict]:
    """Per actor-action pair native return information (no first-write-wins)."""
    out = []
    for pair in record.get("actor_action_pairs") or []:
        if method == V1.V3_METHOD:
            detail = None
            for candidate in raw.get("details", []):
                bound = candidate.get("pair")
                if isinstance(bound, dict) and bound.get("actor") == pair["actor"] \
                        and bound.get("action") == pair["action"]:
                    detail = candidate
                    break
            if detail is None:
                out.append({"actor": pair["actor"], "action": pair["action"],
                            "per_pair_native_field_present": False,
                            "linked_action_mapped": False, "executors_observed": False,
                            "executors": [], "violated": None,
                            "aggregation_level": "requirement_level",
                            "note": "the frozen evidence checker returned no detail for this pair"})
                continue
            match = detail.get("match") or {}
            best = match.get("best") or {}
            activity_id = best.get("activity_id")
            out.append({
                "actor": pair["actor"], "action": pair["action"],
                "per_pair_native_field_present": True,
                "linked_action_mapped": bool(match.get("mapped")),
                "match_tier": match.get("match_tier"), "reason": detail.get("reason"),
                "executors_observed": bool(detail.get("executors")),
                "executors": list(detail.get("executors") or []),
                "observable": detail.get("observable"), "violated": detail.get("violated"),
                "aggregation_level": "requirement_level",
                "candidate_best_activity_id": activity_id,
                "candidate_best_activity_label": best.get("label"),
                "candidate_best_activity_node_kind":
                    V1.activity_kind(model, activity_id) if activity_id else None,
                "candidate_best_activity_executors": list(
                    model.action_actor_names.get(activity_id, []) if activity_id else []),
                "candidate_activity_is_matched_activity": False,
            })
        else:
            out.append({
                "actor": pair["actor"], "action": pair["action"],
                "per_pair_native_field_present": False,
                "linked_action_mapped": False,
                "executors_observed": False, "executors": [], "violated": None,
                "aggregation_level": "clause_level",
                "native_reason": raw.get("reason"),
                "act_actor_scope_policy": raw.get("actor_scope_policy"),
                "process_actor_candidates": list(raw.get("process_actor_candidates") or []),
                "matched_process_action_ids": list(raw.get("matched_process_action_ids") or []),
                "note": "the frozen Definition 6 result carries one detail per matched rule actor "
                        "and a single process-actor candidate set; it returns no per-actor-action "
                        "field, so this unit must not be read as a per-pair verdict",
            })
    return out


def build_frozen_model_probe(models: dict) -> dict:
    """Read-only facts about the frozen process-model representation.

    Not a check invocation: it records what ``SunProcessModel`` exposes, which is
    the evidence the corrected order-endpoint states rely on.
    """
    per_process = {}
    node_facts = {}
    for process_id in sorted(models):
        model = models[process_id]
        kinds = Counter(action["kind"] for action in model.actions)
        targets = {target for values in model.reachable.values() for target in values}
        per_process[process_id] = {
            "candidate_list_size": len(model.actions),
            "activity_count": kinds.get("activity", 0),
            "event_count": kinds.get("event", 0),
            "event_node_ids": sorted(action["id"] for action in model.actions
                                     if action["kind"] == "event"),
            "reachability_source_nodes": len(model.reachable),
        }
        for action in model.actions:
            node_facts[f"{process_id}|{action['id']}"] = {
                "node_name": action["name"], "node_kind": action["kind"],
                "has_outgoing_reachability": action["id"] in model.reachable,
                "reachability_successors": len(model.reachable.get(action["id"], set())),
                "appears_as_reachability_target": action["id"] in targets,
            }
    return {
        "source": "src/bpc_hybrid/sun_stage3/sun_model.py",
        "declaration": "SunProcessModel.actions = record['activities'] + record['events']; "
                       "reachability comes from record['control_flow']['reachable_pairs']",
        "events_are_match_candidates": any(entry["event_count"] for entry in per_process.values()),
        "per_process": per_process,
        "node_facts": node_facts,
    }


def recompute_actor_pairs(stored: dict, rule_inputs: dict) -> dict:
    """Exactly four native ``IncorrectActor`` invocations: v026 and v032, one per method."""
    scorers = V1.build_scorers()
    index = {(row["item_id"], row["method"]): row for row in stored["predictions"]}
    calls = []
    pairs_by_item: dict[str, dict[str, list[dict]]] = defaultdict(dict)
    for item_id in RECOMPUTE_ITEMS:
        probe = index[(item_id, V1.SUN_METHOD)]
        if probe["check_type"] != RECOMPUTE_CHECK_TYPE:
            raise RuntimeError(f"{item_id} is not an IncorrectActor item")
        record = rule_inputs["records"][probe["rule_id"]]
        model = scorers["models"][probe["process_id"]]
        for method in V1.METHODS:
            started = time.time()
            raw = V1.run_designated_check(scorers[method], RECOMPUTE_CHECK_TYPE, record, model)
            state = V1.normalize(method, RECOMPUTE_CHECK_TYPE, raw)
            stored_row = index[(item_id, method)]
            agreed = (state["status"] == stored_row["status"]
                      and state.get("raw_score") == stored_row["score"]
                      and state.get("denominator") == stored_row["denominator"]
                      and state.get("reason") == stored_row["reason"])
            if not agreed:
                raise RuntimeError(
                    "the recomputed native result disagrees with the stored v1 prediction for "
                    f"{item_id}/{method}: recomputed status={state['status']} "
                    f"score={state.get('raw_score')} denominator={state.get('denominator')} "
                    f"reason={state.get('reason')} vs stored status={stored_row['status']} "
                    f"score={stored_row['score']} denominator={stored_row['denominator']} "
                    f"reason={stored_row['reason']}; the correction stops here and the original "
                    "results are kept untouched")
            pairs = extract_pair_evidence(method, raw, record, model)
            pairs_by_item[item_id][method] = pairs
            calls.append({
                "item_id": item_id, "method": method, "check_type": RECOMPUTE_CHECK_TYPE,
                "entry_point": ("SunScorer.incorrect_actor" if method == V1.SUN_METHOD
                                else "EvidenceChecksV3.incorrect_actor"),
                "rule_id": probe["rule_id"], "process_id": probe["process_id"],
                "seconds": round(time.time() - started, 3),
                "native_status": state["status"], "native_score": state.get("raw_score"),
                "native_denominator": state.get("denominator"),
                "native_reason": state.get("reason"),
                "matches_stored_prediction": agreed,
                "pairs_returned": len(pairs),
                "result_sha256": canonical_sha256(raw),
            })
    if len(calls) != MAX_NATIVE_CALLS:
        raise RuntimeError(f"expected exactly {MAX_NATIVE_CALLS} native calls, made {len(calls)}")
    return {
        "performed": True,
        "reason": "the v1 evidence key for an actor requirement (method, kind, process_id, actor "
                  "requirement_text, rule_ids) omitted the linked action, so v026 and v032 each "
                  "collapsed two actor-action pairs into one evidence row and the second pair's "
                  "return information was never stored",
        "recoverable_from_stored_artifacts": False,
        "call_count": len(calls),
        "max_allowed_calls": MAX_NATIVE_CALLS,
        "batch_rerun": False,
        "rows_reused_from_stored_predictions": 62,
        "new_evidence_label": "recomputed_native_repair",
        "new_evidence_note": "these four calls are a repair measurement made by the correction "
                             "run; they are not evidence the original v1 run saved",
        "calls": calls,
        "calls_signature": calls_signature(calls),
        "pairs_by_item": json.loads(json.dumps(pairs_by_item)),
        "frozen_model_probe": build_frozen_model_probe(scorers["models"]),
        "llm_api_calls": 0,
    }


def calls_signature(calls: list[dict]) -> list[dict]:
    """Timing-free signature of the native calls, used for replay comparison."""
    return [{key: value for key, value in call.items() if key != "seconds"} for call in calls]


# ---------------------------------------------------------------------------
# phase 4 - corrected evidence units
# ---------------------------------------------------------------------------


def stored_pair_evidence(stored_entry: dict, unit: dict, row: dict) -> dict:
    """Corrected actor-pair evidence assembled from the stored v1 payload.

    The v1 payload records the pair-level mapped/violated fields for the structured
    checker and only a clause-level note for the frozen similarity path.  It never
    records the native executor list, so the corrected record says so instead of
    presenting a reconstructed list as the executors of a matched activity.
    """
    mapping = stored_entry.get("mapping") or {}
    per_pair = mapping.get("mapped") is not None
    evidence = {
        "actor": unit["text"],
        "action": unit.get("linked_action_requirement"),
        "per_pair_native_field_present": per_pair,
        "aggregation_level": "requirement_level" if per_pair else "clause_level",
        "linked_action_mapped": bool(mapping.get("mapped")) if per_pair else False,
        "match_tier": mapping.get("match_tier"),
        "reason": mapping.get("reason") if per_pair else None,
        "native_reason": None if per_pair else row["reason"],
        "violated": mapping.get("violated") if per_pair else None,
        "executors": [],
        "executors_observed": None if per_pair else False,
        "candidate_best_activity_id": None,
        "candidate_best_activity_label": None,
        "candidate_best_activity_node_kind": None,
        "candidate_best_activity_executors": [],
        "executors_note": "the v1 payload does not record the native executor list; the frozen "
                          "checker reports executors only for a matched activity",
    }
    for node_id, entry in sorted((mapping.get("matched_activity_executors") or {}).items()):
        evidence["candidate_best_activity_id"] = node_id
        evidence["candidate_best_activity_label"] = entry.get("label")
        evidence["candidate_best_activity_node_kind"] = entry.get("kind")
        evidence["candidate_best_activity_executors"] = list(entry.get("executors") or [])
    if not per_pair:
        evidence["note"] = ("the frozen Definition 6 result is a clause-level aggregate for the "
                            "whole rule actor set; no per-pair field exists in this check context")
    return evidence


def family_payload(family: str, stored_entry: dict, pair_evidence: dict | None) -> dict:
    """Corrected native payload of one unit, with corrected field names."""
    mapping = stored_entry.get("mapping") or {}
    if family == "action_requirement":
        return {
            "requirement_text": stored_entry["requirement_text"],
            "mapped": mapping.get("mapped"),
            "match_tier": mapping.get("match_tier"),
            "tier_reason": mapping.get("tier_reason"),
            "reason_codes": sorted(mapping.get("reason_codes") or []),
            "candidates": [
                {"node_id": candidate["activity_id"], "label": candidate["label"],
                 "node_kind": candidate["kind"], "verdict": candidate["verdict"],
                 "raw_similarity": candidate["raw_similarity"],
                 "reason_codes": candidate["reason_codes"]}
                for candidate in mapping.get("candidates") or []],
            "best_model_action": mapping.get("best_model_action"),
            "similarity": mapping.get("similarity"),
            "field_note": "candidate node kinds are frozen-model facts; 'best_model_action' is the "
                          "frozen similarity path's chosen label",
        }
    if family == "actor_action_pair":
        evidence = pair_evidence or {}
        return {
            "actor_requirement": stored_entry["requirement_text"],
            "linked_action_requirement": (evidence.get("action")
                                          or stored_entry.get("linked_action")),
            "actor_action_pair": [stored_entry["requirement_text"],
                                  (evidence.get("action")
                                   or stored_entry.get("linked_action"))],
            "linked_action_mapped": evidence.get("linked_action_mapped"),
            "match_tier": evidence.get("match_tier"),
            "pair_reason": evidence.get("reason") or evidence.get("native_reason"),
            "violated_field": evidence.get("violated"),
            "executors_of_matched_activity": list(evidence.get("executors") or []),
            "executors_observed": evidence.get("executors_observed"),
            "aggregation_level": evidence.get("aggregation_level"),
            "per_pair_native_field_present": evidence.get("per_pair_native_field_present"),
            "candidate_best_activity_id": evidence.get("candidate_best_activity_id"),
            "candidate_best_activity_label": evidence.get("candidate_best_activity_label"),
            "candidate_best_activity_node_kind": evidence.get("candidate_best_activity_node_kind"),
            # renamed on purpose: the v1 payload called this "matched_activity_executors"
            "candidate_best_activity_executors": list(
                evidence.get("candidate_best_activity_executors") or []),
            "process_actor_candidates": list(evidence.get("process_actor_candidates")
                                             or mapping.get("process_actor_candidates") or []),
            "matched_process_action_ids": list(evidence.get("matched_process_action_ids") or []),
            "act_actor_scope_policy": evidence.get("act_actor_scope_policy"),
            "field_note": "a candidate's executors are never reported as the executors of a matched "
                          "activity, and a clause-level aggregate is never reported as a per-pair "
                          "verdict",
        }
    return {
        "endpoint_text": stored_entry["requirement_text"],
        "order_position": stored_entry["kind"].split("_", 1)[1],
        "mapped": mapping.get("mapped"),
        "match_tier": mapping.get("match_tier"),
        "tier_reason": mapping.get("tier_reason"),
        "matched_node_id": mapping.get("activity_id") if mapping.get("mapped") else None,
        "matched_node_kind": mapping.get("kind") if mapping.get("mapped") else None,
        "candidate_node_id": mapping.get("activity_id"),
        "candidate_node_label": mapping.get("label"),
        "candidate_node_kind": mapping.get("kind"),
        "candidate_is_not_the_endpoint": True,
        "raw_similarity": mapping.get("raw_similarity"),
        "before_activity": mapping.get("before_activity"),
        "after_activity": mapping.get("after_activity"),
        "forward_reachable": mapping.get("forward_reachable"),
        "backward_reachable": mapping.get("backward_reachable"),
        "native_reason": mapping.get("reason"),
        "node_kind_note": "an unmatched endpoint has no known node kind: the frozen candidate list "
                          "holds activities and events together and no node was selected",
    }


def endpoint_node_match(process_id: str, payload: dict, model_probe: dict,
                        constraint_state: dict) -> dict:
    mapped = bool(payload.get("mapped"))
    node_id = payload.get("candidate_node_id") if mapped else None
    facts = model_probe["node_facts"].get(f"{process_id}|{node_id}") if node_id else None
    both = bool(constraint_state.get("both_endpoints_matched"))
    distinct = bool(constraint_state.get("endpoints_distinct"))
    reachability = bool(constraint_state.get("reachability_evaluated"))
    can_support = bool(mapped and both and distinct and reachability)
    missing = []
    if not mapped:
        missing.append("endpoint_matched_to_a_process_node")
    if not both:
        missing.append("both_endpoints_of_the_order_constraint_matched")
    if not distinct:
        missing.append("the_two_endpoints_are_distinct_nodes")
    if not reachability:
        missing.append("frozen_reachability_evaluated_for_the_pair")
    return {
        "mapped": mapped, "node_id": node_id,
        "node_kind": facts["node_kind"] if facts else None,
        "candidate_node_kind": payload.get("candidate_node_kind"),
        "can_support_order_judgement": can_support,
        "order_judgement_basis": (
            "both endpoints of the constraint mapped to distinct nodes and the frozen reachability "
            "table was evaluated" if can_support else
            "not judgeable from the recorded evidence; see judgment_missing"),
        "judgment_missing": missing,
        "node_reachability_participation": (
            {"has_outgoing_reachability": facts["has_outgoing_reachability"],
             "reachability_successors": facts["reachability_successors"],
             "appears_as_reachability_target": facts["appears_as_reachability_target"]}
            if facts else None),
    }


def build_corrected(stored: dict, rule_inputs: dict, recomputation: dict,
                    model_probe: dict) -> dict:
    """Rebuild every requirement unit, its corrected state and its associations."""
    items = {row["item_id"]: row for row in rule_inputs["inference"]["violation_items"]}
    units: dict[str, dict] = {}
    associations: dict[tuple[str, str], dict] = {}
    item_states: list[dict] = []
    old_index = stored["evidence_index"]

    # the writer context of a v1 payload: the first row that reached the v1 key
    writer: dict[str, list[str]] = {}
    for row in stored["predictions"]:
        for unit in requirement_units(rule_inputs, row["rule_id"], row["check_type"]):
            fingerprint = canonical(v1_key(unit, row["method"], row["process_id"],
                                           row["rule_id"]))
            writer.setdefault(fingerprint, [row["item_id"], row["check_type"]])

    for row in stored["predictions"]:
        item = items[row["item_id"]]
        rule_id, process_id, method = row["rule_id"], row["process_id"], row["method"]
        check_type = row["check_type"]
        record = rule_inputs["records"][rule_id]
        requirements = requirement_units(rule_inputs, rule_id, check_type)
        if len(requirements) != len(row["evidence_ids"]):
            raise RuntimeError(f"{row['item_id']}/{method}: the requirement count does not match "
                               "the stored evidence references")
        pairs = ((recomputation.get("pairs_by_item") or {}).get(row["item_id"], {})
                 .get(method)) or []
        pair_by_pair = {(entry.get("actor"), entry.get("action")): entry for entry in pairs}
        row_corrected_ids = []
        row_pairs = []
        for position, (unit, v1_id) in enumerate(zip(requirements, row["evidence_ids"])):
            stored_entry = old_index[v1_id]
            if stored_entry["kind"] != unit["kind"] or \
                    stored_entry["requirement_text"] != unit["text"]:
                raise RuntimeError(f"{row['item_id']}/{method}: stored evidence {v1_id} does not "
                                   f"correspond to requirement {position}")
            key = dedup_key(unit, method, process_id, rule_id)
            eid = corrected_evidence_id(key)
            row_corrected_ids.append(eid)
            row_pairs.append({"position": position, "family": unit["family"],
                              "v1_evidence_id": v1_id, "corrected_evidence_id": eid})
            if eid in units:
                continue
            sources = find_source_spans(rule_inputs, rule_id, unit["text"])
            temporal = (temporal_note_for(rule_inputs, rule_id, unit["text"])
                        if unit["family"] == "order_endpoint" else None)
            if sources:
                source_state = "clause_span"
            elif temporal is not None:
                source_state = "projected_temporal_note"
            else:
                source_state = "not_located"
            capability_notes = []
            pair_evidence = None
            if unit["family"] == "actor_action_pair":
                pair_evidence = pair_by_pair.get(
                    (unit["text"], unit.get("linked_action_requirement")))
                if pair_evidence is None:
                    pair_evidence = stored_pair_evidence(stored_entry, unit, row)
                capability_notes.append(
                    "this unit is one declared actor-action pair; the v1 evidence key merged pairs "
                    "of the same rule actor, so the linked action requirement is now part of the "
                    "evidence identity")
            if temporal is not None:
                capability_notes.append(
                    "the endpoint is a projected order anchor taken from a confirmed temporal "
                    "statement, not a modelled process action; the awareness anchor must not be "
                    "read as the occurrence of the breach")
            payload = family_payload(unit["family"], stored_entry, pair_evidence)
            written_in = writer[canonical(v1_key(unit, method, process_id, rule_id))]
            unit_record = {
                "schema_version": SCHEMA_EVIDENCE,
                "run_id": RUN_ID,
                "supersedes_run_id": SUPERSEDES_RUN_ID,
                "evidence_id": eid,
                "family": unit["family"],
                "method": method,
                "process_id": process_id,
                "rule_scope": rule_scope(rule_inputs, rule_id, sources,
                                         [temporal["sample_id"]] if temporal else []),
                "dedup_key": key,
                "dedup_key_fields": DEDUP_KEY_FIELDS[unit["family"]],
                "dedup_key_sha1": sha1_text(canonical(key)),
                "dedup_key_change_vs_v1": {
                    "v1_key_fields": V1_KEY_FIELDS,
                    "v1_key_sha1": sha1_text(canonical(
                        v1_key(unit, method, process_id, rule_id))),
                    "changed": unit["family"] == "actor_action_pair",
                    "change": ("the linked action requirement is now part of the identity"
                               if unit["family"] == "actor_action_pair" else "unchanged"),
                },
                "requirement_text": unit["text"],
                "sources": sources,
                "source_state": source_state,
                "source_note": (
                    f"{len(sources)} confirmed clause spans carry this requirement text; the v1 "
                    "diagnostic kept the first one only" if len(sources) > 1 else
                    "one confirmed clause span carries this requirement text" if sources else
                    "the requirement text is not a confirmed clause span; its provenance is the "
                    "projected temporal statement" if temporal is not None else
                    "the requirement text is neither a confirmed clause span nor a projected "
                    "temporal statement"),
                "temporal_note": ({key: temporal[key] for key in
                                   ("sample_id", "note", "before", "after", "source",
                                    "creates_mandatory_action")} if temporal else None),
                "native_evidence": {
                    "basis": ("recomputed_native_repair"
                              if unit["family"] == "actor_action_pair" and pairs else
                              "stored_v1_payload"),
                    "payload": payload,
                },
                "check_context_returns": [],
                "v1_evidence_ids": [],
                "v1_payload_provenance": {
                    "written_in_context": {"item_id": written_in[0],
                                           "check_type": written_in[1]},
                    "first_write_wins": True,
                    "reused_in_check_contexts": [],
                    "note": "the v1 store kept one payload per key; when two check contexts "
                            "reached the same key the first write decided the payload, which this "
                            "correction records explicitly instead of hiding it",
                },
                "capability_notes": capability_notes,
            }
            if unit["family"] == "action_requirement":
                unit_record["representation"] = stored_entry.get("representation")
                unit_record["state"] = classify_action(payload)
            elif unit["family"] == "actor_action_pair":
                unit_record["linked_action_requirement"] = unit["linked_action_requirement"]
                unit_record["state"] = classify_actor(pair_evidence)
            else:
                unit_record["order_position"] = unit["order_position"]
                unit_record["order_constraint"] = list(unit["order_constraint"])
            units[eid] = unit_record
        for position, unit in enumerate(requirements):
            eid = row_corrected_ids[position]
            unit_record = units[eid]
            context = {
                "item_id": row["item_id"], "check_type": check_type,
                "requirement_index": position,
                "v1_evidence_id": row["evidence_ids"][position],
                "check_level_return": {"status": row["status"], "score": row["score"],
                                       "denominator": row["denominator"],
                                       "reason": row["reason"]},
                "requirement_level_return_available": None,
                "requirement_level_return_basis": None,
            }
            unit_record["check_context_returns"].append(context)
            if unit["family"] == "action_requirement":
                paired_actions = {pair["action"]
                                  for pair in record.get("actor_action_pairs") or []}
                if method == V1.V3_METHOD and check_type == "incorrect_actor" \
                        and unit["text"] not in paired_actions:
                    context["requirement_level_return_available"] = False
                    context["requirement_level_return_basis"] = \
                        "this action requirement is not part of any declared actor-action pair, " \
                        "so the IncorrectActor check never evaluates it"
                elif method == V1.V3_METHOD:
                    context["requirement_level_return_available"] = True
                    context["requirement_level_return_basis"] = \
                        "the structured matcher evaluates one action requirement at a time and " \
                        "reuses the identical match object in both check contexts"
                elif check_type == "missing_action":
                    context["requirement_level_return_available"] = True
                    context["requirement_level_return_basis"] = \
                        "frozen Definition 4 returns one detail per rule action"
                else:
                    context["requirement_level_return_available"] = False
                    context["requirement_level_return_basis"] = \
                        "frozen Definition 6 returns one detail per matched rule actor plus a single " \
                        "process-actor candidate set; it has no per-action field, so the stored " \
                        "Definition 4 payload does not describe this check context"
            elif unit["family"] == "actor_action_pair":
                available = unit_record["state"]["per_pair_native_field_present"] is True
                context["requirement_level_return_available"] = available
                context["requirement_level_return_basis"] = (
                    "the frozen evidence checker returns one detail per declared actor-action pair"
                    if available else
                    "the frozen Definition 6 result is a clause-level aggregate; no per-pair field "
                    "exists in this check context")
            else:
                context["requirement_level_return_available"] = True
                context["requirement_level_return_basis"] = \
                    "the frozen order check returns one endpoint match per order constraint"
            if unit_record["v1_evidence_ids"]:
                unit_record["v1_payload_provenance"]["reused_in_check_contexts"].append(
                    {"item_id": row["item_id"], "check_type": check_type,
                     "v1_evidence_id": row["evidence_ids"][position]})
        for unit, v1_id in zip(requirements, row["evidence_ids"]):
            eid = corrected_evidence_id(dedup_key(unit, method, process_id, rule_id))
            if v1_id not in units[eid]["v1_evidence_ids"]:
                units[eid]["v1_evidence_ids"].append(v1_id)
        associations[(row["item_id"], method)] = {
            "v1_evidence_ids": list(row["evidence_ids"]),
            "corrected_evidence_ids": row_corrected_ids,
            "pairs": row_pairs,
        }

        item_level = []
        if check_type == "missing_action" and not record["actions"]:
            item_level.append("rule_has_no_action_requirement")
        if check_type == "incorrect_actor" and not (record.get("actor_action_pairs") or []):
            item_level.append("rule_has_no_actor_requirement")
        if check_type == "out_of_order" and not record["order_relations"]:
            item_level.append("rule_has_no_order_relation")
        entry = {
            "item_id": row["item_id"], "method": method, "check_type": check_type,
            "process_id": process_id, "rule_id": rule_id,
            "requirement_units": len(requirements),
            "item_level_states": item_level,
            "check_level_return": {"status": row["status"], "score": row["score"],
                                   "denominator": row["denominator"], "reason": row["reason"]},
        }
        if check_type == "out_of_order":
            entry["order_judgement"] = {
                "constraints": [list(pair) for pair in record["order_relations"]],
                "reachability_evaluated": bool(row["denominator"]),
                "check_level_reason": row["reason"],
                "blocking_reason": ("rule_carries_no_order_relation" if not record["order_relations"]
                                    else "order_endpoint_unmatched_in_this_method"),
            }
        item_states.append(entry)

    # resolve per-constraint endpoint support with real model facts
    for item_state in item_states:
        if item_state["check_type"] != "out_of_order" or item_state["item_level_states"]:
            continue
        association = associations[(item_state["item_id"], item_state["method"])]
        by_constraint: dict[str, list[str]] = defaultdict(list)
        for eid in association["corrected_evidence_ids"]:
            by_constraint[canonical(units[eid]["order_constraint"])].append(eid)
        for eids in by_constraint.values():
            matched = [units[eid]["native_evidence"]["payload"]["matched_node_id"] for eid in eids]
            state = {
                "both_endpoints_matched": all(matched),
                "endpoints_distinct": len({value for value in matched if value}) == len(matched),
                "reachability_evaluated": item_state["order_judgement"]["reachability_evaluated"],
            }
            for eid in eids:
                unit = units[eid]
                node_match = endpoint_node_match(
                    unit["process_id"], unit["native_evidence"]["payload"], model_probe, state)
                unit["state"] = classify_endpoint(node_match, unit["source_state"])
                unit["model_support"] = {
                    "node_reachability_participation": node_match["node_reachability_participation"],
                    "frozen_model_probe_source": model_probe["source"],
                }

    # scope every judgment-support claim to the check contexts that actually
    # return requirement-level information
    for unit in units.values():
        support = unit["state"]["judgment_support"]
        available = sorted({context["check_type"] for context in unit["check_context_returns"]
                            if context["requirement_level_return_available"] is True})
        support["requirement_observed"] = support["complete"]
        support["complete_in_check_types"] = available if support["complete"] else []
        support["complete"] = bool(support["complete"] and available)
        support["scope_note"] = ("the support holds only in the check contexts that return "
                                 "requirement-level information; a context without such a return "
                                 "contributes no support")
    return {"units": units, "associations": associations, "item_states": item_states,
            "writer": writer}


# ---------------------------------------------------------------------------
# phase 5 - coverage accounting (reference counts vs unique counts)
# ---------------------------------------------------------------------------


def state_name(unit: dict) -> str:
    """The reported state of a unit (endpoints report a combined state)."""
    state = unit["state"]
    return state.get("state") or state.get("combined_state")


def build_coverage(stored: dict, corrected: dict, model_probe: dict) -> dict:
    units = corrected["units"]
    associations = corrected["associations"]
    row_index = {(row["item_id"], row["method"]): row for row in stored["predictions"]}
    families: dict[str, dict] = {}
    for family in FAMILIES:
        family_units = {eid: unit for eid, unit in units.items() if unit["family"] == family}
        block: dict[str, dict] = {}
        for method in V1.METHODS:
            method_units = {eid: unit for eid, unit in family_units.items()
                            if unit["method"] == method}
            refs = 0
            refs_by_check: Counter = Counter()
            for (item_id, row_method), association in associations.items():
                if row_method != method:
                    continue
                for pair in association["pairs"]:
                    if pair["family"] != family:
                        continue
                    refs += 1
                    refs_by_check[row_index[(item_id, method)]["check_type"]] += 1
            contexts_without_return = sum(
                1 for unit in method_units.values()
                for context in unit["check_context_returns"]
                if context["requirement_level_return_available"] is False)
            aggregation = Counter(unit["state"].get("aggregation_level")
                                  for unit in method_units.values()
                                  if unit["family"] == "actor_action_pair")
            block[method] = {
                "unique_units": len(method_units),
                "requirement_references": refs,
                "references_by_check_type": dict(sorted(refs_by_check.items())),
                "dedup_reduction": refs - len(method_units),
                "check_contexts_without_a_requirement_level_return": contexts_without_return,
                "clause_level_aggregate_units": aggregation.get("clause_level", 0),
                "per_pair_field_absent_units": sum(
                    1 for unit in method_units.values()
                    if unit["state"].get("per_pair_native_field_present") is False),
                "state_counts": dict(sorted(Counter(
                    state_name(unit) for unit in method_units.values()).items())),
                "judgment_support_complete_units": sum(
                    1 for unit in method_units.values()
                    if unit["state"]["judgment_support"]["complete"]),
            }
        families[family] = {
            "definition": {
                "action_requirement": "one required action of a rule, for one method and process",
                "actor_action_pair": "one declared actor-action pair of a rule, for one method and "
                                     "process",
                "order_endpoint": "one endpoint of one declared order relation, for one method and "
                                  "process",
            }[family],
            "dedup_key_fields": DEDUP_KEY_FIELDS[family],
            "per_method": block,
            "unique_units_total": len(family_units),
            "unit_total_note": "both methods keep their own unit population; a unit is never shared "
                               "across methods",
        }
    named = Counter()
    source_states = Counter()
    cross = Counter()
    for unit in units.values():
        if unit["family"] != "order_endpoint":
            continue
        named[(unit["method"], unit["state"]["combined_state"])] += 1
        source_states[(unit["method"], unit["state"]["source_state"])] += 1
        cross[(unit["method"], unit["state"]["match_state"], unit["state"]["source_state"])] += 1
    return {
        "note": "reference counts and unique counts are reported separately; the three requirement "
                "families are never merged into one overall mapping rate",
        "families": families,
        "order_endpoint_named_states": {f"{method}|{state}": count for (method, state), count
                                        in sorted(named.items())},
        "order_endpoint_source_states": {f"{method}|{state}": count for (method, state), count
                                         in sorted(source_states.items())},
        "order_endpoint_state_cross": {f"{method}|{match}|{source}": count
                                       for (method, match, source), count in sorted(cross.items())},
        "item_level_states": dict(sorted(Counter(
            state for item in corrected["item_states"] for state in item["item_level_states"]
        ).items())),
        "old_accounting_defects": {
            "counted_references_as_unique": True,
            "class_depended_on_the_referencing_check_type": True,
            "evidence_supports_judgment_included_unmapped_units": True,
        },
        "model_representation": {
            "events_are_match_candidates": model_probe["events_are_match_candidates"],
            "source": model_probe["source"],
            "declaration": model_probe["declaration"],
        },
    }


# ---------------------------------------------------------------------------
# phase 6 - corrections, summary, manifest
# ---------------------------------------------------------------------------


def old_reference_counts(stored: dict) -> dict:
    out = {}
    for method in V1.METHODS:
        kinds = Counter()
        for row in stored["predictions"]:
            if row["method"] != method:
                continue
            for eid in row["evidence_ids"]:
                kinds[stored["evidence_index"][eid]["kind"]] += 1
        out[method] = {
            "action_requirement_references": kinds["action"],
            "actor_action_pair_references": kinds["actor"],
            "order_endpoint_references": kinds["order_before"] + kinds["order_after"],
        }
    return out


def old_unique_counts(stored: dict) -> dict:
    out = {}
    for method in V1.METHODS:
        kinds = Counter()
        for entry in stored["evidence"]:
            if entry["method"] != method:
                continue
            kinds[entry["kind"]] += 1
        out[method] = {
            "action_requirement_units": kinds["action"],
            "actor_action_pair_units": kinds["actor"],
            "order_endpoint_units": kinds["order_before"] + kinds["order_after"],
        }
    return out


def build_corrections(stored: dict, rule_inputs: dict, corrected: dict, coverage: dict,
                      recomputation: dict, model_probe: dict, profile: dict) -> dict:
    units = corrected["units"]
    associations = corrected["associations"]
    new_unique = {method: {family: coverage["families"][family]["per_method"][method]["unique_units"]
                           for family in FAMILIES} for method in V1.METHODS}
    new_refs = {method: {family: coverage["families"][family]["per_method"][method]
                         ["requirement_references"] for family in FAMILIES}
                for method in V1.METHODS}
    new_states = {method: {family: coverage["families"][family]["per_method"][method]["state_counts"]
                           for family in FAMILIES} for method in V1.METHODS}
    data_side = {method: coverage["families"]["actor_action_pair"]["per_method"][method]
                 for method in V1.METHODS}

    merged = {}
    for item_id in RECOMPUTE_ITEMS:
        row = next(row for row in stored["predictions"]
                   if row["item_id"] == item_id and row["method"] == V1.V3_METHOD)
        merged[item_id] = {
            "duplicated_v1_evidence_ids": sorted(
                {eid for eid in row["evidence_ids"] if row["evidence_ids"].count(eid) > 1}),
            "references": len(row["evidence_ids"]),
            "unique_references": len(set(row["evidence_ids"])),
        }
    item_pair_units = {
        item_id: {method: len([unit for unit in units.values()
                               if unit["family"] == "actor_action_pair"
                               and unit["method"] == method
                               and any(context["item_id"] == item_id
                                       for context in unit["check_context_returns"])])
                  for method in V1.METHODS}
        for item_id in RECOMPUTE_ITEMS}

    per_unit_corrections = []
    for eid in sorted(units):
        unit = units[eid]
        fields = []
        if unit["family"] == "actor_action_pair":
            fields.append({
                "field": "dedup_key",
                "old": "method, kind, process_id, actor requirement_text, rule_ids",
                "new": "method, family, process_id, rule_id, actor_requirement, "
                       "linked_action_requirement",
                "reason": "without the linked action requirement two different actor-action pairs of "
                          "the same rule actor collapsed into one evidence row",
            })
            fields.append({
                "field": "mapping.matched_activity_executors",
                "old": "executors of the best candidate activity, recorded even when no activity was "
                       "matched and presented as the executors of a matched activity",
                "new": "candidate_best_activity_executors plus executors_of_matched_activity, which "
                       "is empty because no activity was matched",
                "reason": "a candidate's executors are not the executors of a matched activity",
            })
            fields.append({
                "field": "mapping_state",
                "old": "evidence_supports_judgment (v1 treated violated=false as support)",
                "new": unit["state"]["state"],
                "reason": "violated=false is the default when the executors could not be observed; "
                          "it is not positive evidence",
            })
        elif unit["family"] == "order_endpoint":
            fields.append({
                "field": "mapping_state",
                "old": ("order_endpoint_not_an_activity"
                        if not unit["native_evidence"]["payload"]["mapped"]
                        else "evidence_supports_judgment"),
                "new": unit["state"]["combined_state"],
                "reason": "an unmatched endpoint has no known node kind, and a matched endpoint is "
                          "typed only by the real kind of the matched node",
            })
        if len(unit["sources"]) > 1:
            fields.append({
                "field": "source",
                "old": "the first confirmed clause span carrying the requirement text",
                "new": f"{len(unit['sources'])} confirmed clause spans",
                "reason": "a shared requirement has several source sentences; the first one must not "
                          "be the only recorded provenance",
            })
        if fields:
            per_unit_corrections.append({
                "evidence_id": eid, "method": unit["method"], "family": unit["family"],
                "process_id": unit["process_id"],
                "requirement_text": unit["requirement_text"],
                "linked_action_requirement": unit.get("linked_action_requirement"),
                "v1_evidence_ids": sorted(unit["v1_evidence_ids"]),
                "state": state_name(unit),
                "corrections": fields,
            })

    prediction_map = []
    for row in stored["predictions"]:
        association = associations[(row["item_id"], row["method"])]
        split: dict[str, list[str]] = {}
        for pair in association["pairs"]:
            split.setdefault(pair["v1_evidence_id"], [])
            if pair["corrected_evidence_id"] not in split[pair["v1_evidence_id"]]:
                split[pair["v1_evidence_id"]].append(pair["corrected_evidence_id"])
        single = {eid for ids in split.values() if len(ids) == 1 for eid in ids}
        prediction_map.append({
            "item_id": row["item_id"], "method": row["method"], "check_type": row["check_type"],
            "process_id": row["process_id"], "rule_id": row["rule_id"],
            "status": row["status"], "score": row["score"], "denominator": row["denominator"],
            "reason": row["reason"],
            "v1_evidence_ids": association["v1_evidence_ids"],
            "corrected_evidence_ids": association["corrected_evidence_ids"],
            "v1_to_corrected": [{"v1_evidence_id": v1_id, "corrected_evidence_ids": ids}
                                for v1_id, ids in sorted(split.items())],
            "split_v1_evidence_ids": sorted(v1_id for v1_id, ids in split.items()
                                            if len(ids) > 1),
            "new_corrected_evidence_ids": sorted(eid for eid
                                                 in association["corrected_evidence_ids"]
                                                 if eid not in single),
            "row_sha256": canonical_sha256(row),
        })
    if len(prediction_map) != 66:
        raise RuntimeError("every original item and method must have an explicit correction mapping")

    items = sorted(item["item_id"] for item in rule_inputs["inference"]["violation_items"])
    old_condition_items = sorted({item["item_id"] for item in
                                  rule_inputs["inference"]["violation_items"]
                                  if profile[item["rule_id"]]["first_sentence_v1_boolean"]})
    totals = {
        "rules": len(profile),
        "sentences": sum(values["sentence_count"] for values in profile.values()),
        "clauses": sum(values["clause_count"] for values in profile.values()),
        "clauses_with_conditions": sum(values["clauses_with_conditions"]
                                       for values in profile.values()),
        "clauses_with_constraints": sum(values["clauses_with_constraints"]
                                        for values in profile.values()),
        "clauses_with_exceptions": sum(values["clauses_with_exceptions"]
                                       for values in profile.values()),
        "condition_spans": sum(values["condition_spans"] for values in profile.values()),
        "constraint_spans": sum(values["constraint_spans"] for values in profile.values()),
        "exception_spans": sum(values["exception_spans"] for values in profile.values()),
    }
    corrections = [
        {
            "correction_id": "C1_unmapped_is_not_evidence_support",
            "problem": "unmapped actor evidence was counted as evidence supporting the judgment",
            "target": "mapping state of every actor-action pair unit",
            "old_value": {
                "class": "evidence_supports_judgment",
                "v3_actor_units_counted": stored["summary"]["mapping_coverage"]["counts"][
                    V1.V3_METHOD]["evidence_supports_judgment"],
                "v3_actor_units_really_unmapped": old_unique_counts(stored)[V1.V3_METHOD][
                    "actor_action_pair_units"],
                "sun_actor_references_counted_as": "rule_lacks_required_information",
                "note": "every de-duplicated v3 actor unit had mapped=false and violated=false",
            },
            "new_value": {
                "state_counts": {method: new_states[method]["actor_action_pair"]
                                 for method in V1.METHODS},
                "classes": list(CORRECTED_STATES["actor_action_pair"]),
                "executor_comparison_performed": {
                    method: new_states[method]["actor_action_pair"].get(
                        "executor_comparison_performed", 0) for method in V1.METHODS},
                "clause_level_aggregate_units": {method: data_side[method][
                    "clause_level_aggregate_units"] for method in V1.METHODS},
                "per_pair_field_absent_units": {method: data_side[method][
                    "per_pair_field_absent_units"] for method in V1.METHODS},
                "rule_has_no_actor_requirement_items": sorted({
                    item["item_id"] for item in corrected["item_states"]
                    if "rule_has_no_actor_requirement" in item["item_level_states"]}),
                "renamed_fields": {
                    "v1": "mapping.matched_activity_executors",
                    "corrected": "candidate_best_activity_executors / "
                                 "executors_of_matched_activity",
                },
            },
            "reason": "a mapping state is not a judgment claim: evidence supports the judgment only "
                      "when the check has the information it needs, the activity was reliably "
                      "determined and the executors were observable; a missing native field is "
                      "recorded as native-evidence absence rather than as a rule defect",
            "affected_items": sorted({context["item_id"] for unit in units.values()
                                      if unit["family"] == "actor_action_pair"
                                      for context in unit["check_context_returns"]}),
            "affected_units": sorted(eid for eid, unit in units.items()
                                     if unit["family"] == "actor_action_pair"),
        },
        {
            "correction_id": "C2_actor_action_pair_identity",
            "problem": "two actor-action pairs of the same rule actor were merged into one evidence "
                       "row",
            "target": "actor-action pair evidence identity",
            "old_value": {
                "dedup_key": "method, kind, process_id, actor requirement_text, rule_ids",
                "v026": merged.get("v026"), "v032": merged.get("v032"),
                "unique_actor_units_per_method": old_unique_counts(stored)[V1.V3_METHOD][
                    "actor_action_pair_units"],
            },
            "new_value": {
                "dedup_key": DEDUP_KEY_FIELDS["actor_action_pair"],
                "unique_actor_units_per_method": {method: new_unique[method]["actor_action_pair"]
                                                  for method in V1.METHODS},
                "restored_pair_units": item_pair_units,
                "source_list_kept": True,
            },
            "reason": "the evidence identity must separate method, process, rule scope, actor "
                      "requirement and linked action requirement, and every pair must point back to "
                      "its own action evidence; one requirement can have several source sentences, "
                      "so the source is a list rather than the first match",
            "affected_items": sorted(RECOMPUTE_ITEMS),
            "affected_units": sorted(eid for eid, unit in units.items()
                                     if unit["family"] == "actor_action_pair"
                                     and any(context["item_id"] in RECOMPUTE_ITEMS
                                             for context in unit["check_context_returns"])),
        },
        {
            "correction_id": "C3_reference_vs_unique_counts",
            "problem": "requirement references in check instances were reported as de-duplicated "
                       "requirements",
            "target": "mapping coverage accounting",
            "old_value": {
                "reported_as_unique": stored["summary"]["mapping_coverage"]["counts"],
                "denominators": stored["summary"]["mapping_coverage"]["denominators"],
                "old_denominator_note": "required_actions_checked=84 per method is a reference count, "
                                        "not a de-duplicated requirement count",
                "reference_counts": old_reference_counts(stored),
                "unique_counts": old_unique_counts(stored),
            },
            "new_value": {
                "reference_counts": new_refs,
                "unique_counts": new_unique,
                "state_counts_on_unique_units": new_states,
                "class_depends_on_referencing_check_type": False,
                "mixed_overall_rate_reported": False,
                "per_context_returns_preserved": True,
            },
            "reason": "a requirement referenced by two check instances is one requirement and two "
                      "references; the two accounting bases must be reported separately per family, "
                      "and per-check return information must stay attached to its own check context",
            "affected_items": items,
            "affected_units": sorted(units),
        },
        {
            "correction_id": "C4_order_endpoint_states",
            "problem": "every unmapped order endpoint was classified as 'not an activity'",
            "target": "order-endpoint state classification",
            "old_value": {
                "class": "order_endpoint_not_an_activity",
                "counts": {method: stored["summary"]["mapping_coverage"]["counts"][method][
                    "order_endpoint_not_an_activity"] for method in V1.METHODS},
                "claim": "the endpoint is an event/state, not an activity",
                "conclusion": "because events are not supported the whole order check is unjudgeable",
            },
            "new_value": {
                "named_states": list(CORRECTED_STATES["order_endpoint"]),
                "state_counts": coverage["order_endpoint_named_states"],
                "source_state_counts": coverage["order_endpoint_source_states"],
                "state_cross": coverage["order_endpoint_state_cross"],
                "events_are_match_candidates": model_probe["events_are_match_candidates"],
                "event_counts_per_process": {process: values["event_count"] for process, values
                                             in model_probe["per_process"].items()},
                "blocking_reasons": {method: dict(sorted(Counter(
                    item["order_judgement"]["blocking_reason"] for item in corrected["item_states"]
                    if item["method"] == method and item["check_type"] == "out_of_order").items()))
                    for method in V1.METHODS},
            },
            "reason": "the frozen candidate list holds activities and events together, so a failed "
                      "match establishes no node kind; the real blocking reasons are the missing "
                      "rule-side order relation and the unmatched endpoints, not event support",
            "affected_items": sorted({item["item_id"] for item in corrected["item_states"]
                                      if item["check_type"] == "out_of_order"}),
            "affected_units": sorted(eid for eid, unit in units.items()
                                     if unit["family"] == "order_endpoint"),
        },
        {
            "correction_id": "C5_conditions_over_all_sentences",
            "problem": "the condition scan returned after the first sentence of a rule",
            "target": "applicability and condition accounting",
            "old_value": {
                "function": "clause_has_conditions",
                "old_behaviour": "the scan returned after the first sentence record of a rule, so "
                                 "later sentences could not contribute",
                "old_reported_items": old_condition_items,
                "boolean_unchanged_for_every_rule": True,
                "aggregate_counts_reported": False,
            },
            "new_value": {
                "evaluation": "not_evaluated",
                "aggregation": "all sentences and all clauses of the rule",
                "per_rule": profile,
                "totals": totals,
            },
            "reason": "the second and later sentences of a rule can carry conditions, constraints and "
                      "exceptions; the frozen converter consumes none of them, so applicability must "
                      "be recorded as not evaluated rather than as 'no conditions'",
            "affected_items": items,
            "affected_units": [],
        },
    ]
    return {
        "schema_version": SCHEMA_CORRECTIONS,
        "run_id": RUN_ID,
        "supersedes": {
            "run_id": SUPERSEDES_RUN_ID,
            "directory": V1_DIR.relative_to(ROOT).as_posix(),
            "files": {name: stored["sha256"][name] for name in V1_FILES},
            "note": "the v1 runner, tests, predictions, scope review, summary and manifest stay "
                    "byte-identical; this directory only references them by path and hash",
        },
        "declarations": {
            "diagnostic_correction_only": True,
            "new_batch_experiment": False,
            "predictions_modified": False,
            "checkers_modified": False,
            "gold_modified": False,
            "thresholds_modified": False,
            "rule_inputs_modified": False,
            "human_answers_modified": False,
            "new_llm_api_calls": 0,
            "formal_oracle_promotion": False,
            "performance_claim_ready": False,
        },
        "corrections": corrections,
        "per_unit_corrections": per_unit_corrections,
        "prediction_evidence_map": prediction_map,
        "associations_restored": {
            "items": list(RECOMPUTE_ITEMS),
            "restored": True,
            "detail": {
                "v026": {"rule_id": "article17", "process_id": "gdpr_5_right_to_withdraw",
                         "actor_action_pairs": 2, "distinct_actions": 2},
                "v032": {"rule_id": "article17", "process_id": "gdpr_7_right_to_be_forgotten",
                         "actor_action_pairs": 2, "distinct_actions": 2},
            },
            "restored_pair_units": item_pair_units,
            "native_calls_used": recomputation["call_count"],
            "native_calls_allowed": recomputation["max_allowed_calls"],
            "label": "recomputed_native_repair",
        },
        "recomputation": recomputation,
        "frozen_model_probe": model_probe,
        "count_table": {
            "old": {
                "reference_counts": old_reference_counts(stored),
                "unique_counts": old_unique_counts(stored),
                "class_counts": {method: dict(stored["summary"]["mapping_coverage"]["counts"][method])
                                 for method in V1.METHODS},
                "denominators": stored["summary"]["mapping_coverage"]["denominators"],
            },
            "new": {
                "reference_counts": new_refs,
                "unique_counts": new_unique,
                "state_counts": new_states,
            },
        },
        "prediction_status": {
            "rows": len(stored["predictions"]),
            "predictions_sha256": stored["predictions_sha256"],
            "v1_manifest_bound_sha256": stored["predictions_bound_sha256"],
            "byte_identical": stored["predictions_sha256"] == stored["predictions_bound_sha256"],
            "fields_preserved": ["item_id", "method", "process_id", "rule_id", "check_type",
                                 "status", "score", "denominator", "reason", "conversion",
                                 "evidence_ids", "rule_requirement_sha256", "model_bpmn_sha256",
                                 "shared_binding"],
            "rows_rewritten": 0,
            "note": "the corrected evidence uses a new versioned id namespace; no original "
                    "evidence_id is redefined in place",
        },
        "missing_evidence": [
            "the v1 payload for a mapped action requirement records the candidate list but not the "
            "matched node id, so the corrected report makes no node-kind claim for action matches",
            "outside v026/v032 the v1 payload does not record the native executor list of an "
            "actor-action pair; the corrected state is derived from the stored mapped/violated "
            "fields and the frozen source semantics, and the four recomputed pairs confirm that "
            "semantics",
        ],
        "capability_limits": [
            "the frozen converter consumes the obligation modality only; permission, prohibition and "
            "definition clauses are recorded but never checked",
            "the frozen converter does not consume conditions, constraints or exceptions, so rule "
            "applicability to a process is not evaluated by either method (recorded as "
            "not_evaluated)",
            "eight of the eleven order-checked items have no rule-side order relation at all; the "
            "frozen converter produced none for those articles and the confirmed temporal notes "
            "project only three statements",
            "an IncorrectActor check needs a rule-side actor-action mapping plus a reliably matched "
            "activity with observable executors; no actor-action pair of this diagnostic reached "
            "that state",
            "retracted: the earlier statement that events make the order check unjudgeable is not "
            "supported.  SunProcessModel puts activities and events into the same candidate list and "
            "the reachability table covers them, so no endpoint of this diagnostic was blocked by "
            "event representation",
        ],
    }


def build_summary(stored: dict, rule_inputs: dict, corrected: dict, coverage: dict,
                  profile: dict, corrections: dict) -> dict:
    units = corrected["units"]
    items = rule_inputs["inference"]["violation_items"]
    status_totals = {method: dict(Counter(row["status"] for row in stored["predictions"]
                                          if row["method"] == method))
                     for method in V1.METHODS}
    counts_per_check = {method: {check: dict(Counter(
        row["status"] for row in stored["predictions"]
        if row["method"] == method and row["check_type"] == check))
        for check in V1.CHECK_TYPES} for method in V1.METHODS}
    no_actions = sorted({item["item_id"] for item in items
                         if not rule_inputs["records"][item["rule_id"]]["actions"]})
    no_actors = sorted({item["item_id"] for item in items
                        if item["check_type"] == "incorrect_actor"
                        and not (rule_inputs["records"][item["rule_id"]]["actor_action_pairs"]
                                 or [])})
    no_orders = sorted({item["item_id"] for item in items
                        if item["check_type"] == "out_of_order"
                        and not rule_inputs["records"][item["rule_id"]]["order_relations"]})
    unconsumed = sorted({item["item_id"] for item in items
                         if profile[item["rule_id"]]["clauses_with_conditions"]
                         or profile[item["rule_id"]]["clauses_with_constraints"]
                         or profile[item["rule_id"]]["clauses_with_exceptions"]})
    return {
        "schema_version": SCHEMA_SUMMARY,
        "run_id": RUN_ID,
        "supersedes_run_id": SUPERSEDES_RUN_ID,
        "claim_scope": "development_diagnostic_correction_on_real_legal_rule_input",
        "performance_claim_ready": False,
        "formal_oracle_promotion": False,
        "predictions": {
            "modified": False,
            "rows": len(stored["predictions"]),
            "predictions_sha256": stored["predictions_sha256"],
            "v1_manifest_bound_sha256": stored["predictions_bound_sha256"],
            "byte_identical": stored["predictions_sha256"] == stored["predictions_bound_sha256"],
            "declaration": "all 66 original prediction rows are reused unchanged; this round only "
                           "corrects evidence association, reason classification and coverage "
                           "accounting",
        },
        "v1_reference": {
            "run_id": SUPERSEDES_RUN_ID,
            "directory": V1_DIR.relative_to(ROOT).as_posix(),
            "sha256": stored["sha256"],
            "copied": False,
            "note": "the v1 predictions and scope review are referenced by path and hash and are "
                    "never copied into this directory",
        },
        "status_totals": status_totals,
        "counts_per_method_and_check": counts_per_check,
        "method_differences_count": sum(
            1 for item_id in {row["item_id"] for row in stored["predictions"]}
            if len({row["status"] for row in stored["predictions"]
                    if row["item_id"] == item_id}) > 1),
        "coverage": coverage,
        "applicability": {
            "evaluation": "not_evaluated",
            "evaluated_by_checkers": False,
            "reason": "the frozen converter (gdpr_capsule_converter.build_rule_records) and both "
                      "scorers consume modality, actions, actors and order relations only; condition, "
                      "constraint and exception clauses are recorded in the confirmed rule records "
                      "but are never consumed, so rule applicability to a process is not evaluated",
            "old_diagnostic_defect": {
                "function": "clause_has_conditions",
                "old_behaviour": "the scan returned after the first sentence record of a rule",
                "boolean_unchanged_for_every_rule": True,
                "old_reported_items": corrections["corrections"][4]["old_value"][
                    "old_reported_items"],
                "aggregate_counts_reported": False,
            },
            "per_rule": profile,
            "totals": corrections["corrections"][4]["new_value"]["totals"],
            "items_with_unconsumed_condition_context": unconsumed,
            "per_item_evaluation": {item["item_id"]: "not_evaluated" for item in items},
        },
        "top_blockers": [
            {
                "blocker": "rule_side_requirements_absent_after_obligation_only_conversion",
                "items": sorted(set(no_actions) | set(no_actors)),
                "detail": "article16 carries no obligation clause with an action (v028/v029/v030) and "
                          "article20 carries none with an actor (v020/v029), so those items have an "
                          "empty requirement population instead of an unmatched one",
            },
            {
                "blocker": "order_check_without_rule_side_order_relation_or_unmatched_endpoints",
                "items": no_orders,
                "detail": "eight of the eleven order-checked items have no rule-side order relation; "
                           "for the remaining three items the rule endpoints do not map to process "
                           "nodes, so the frozen check keeps an empty denominator",
            },
            {
                "blocker": "conditions_constraints_exceptions_not_consumed",
                "items": unconsumed,
                "detail": "the confirmed clauses carry conditions, constraints and exceptions that the "
                          "frozen converter and scorers do not consume, so applicability is recorded "
                          "as not_evaluated",
            },
        ],
        "corrected_evidence": {
            "rows": len(units),
            "families": {family: coverage["families"][family]["unique_units_total"]
                         for family in FAMILIES},
            "dedup_keys": DEDUP_KEY_FIELDS,
            "id_namespace": "cev_<sha1-16 of the corrected de-dup key>",
            "v1_id_reuse_forbidden": True,
            "state_vocabulary": CORRECTED_STATES,
            "item_level_state_vocabulary": list(ITEM_LEVEL_STATES),
        },
        "native_recomputation": {
            "performed": True,
            "calls": corrections["recomputation"]["call_count"],
            "items": list(RECOMPUTE_ITEMS),
            "check_type": RECOMPUTE_CHECK_TYPE,
            "label": "recomputed_native_repair",
            "note": "the four recovered actor-action associations are new measurements of this "
                    "repair run; they are not evidence the original v1 run saved",
        },
        "separation_note": "the summary is derived from the stored v1 predictions, the frozen rule "
                           "structure and the four authorised native calls; no label and no human "
                           "answer is read",
    }


def input_paths() -> list[str]:
    return V1.input_paths()


def implementation_paths() -> list[str]:
    return V1.implementation_paths()


def new_implementation_paths() -> list[str]:
    return [
        "scripts/repair_s3_real_rule_diagnostics_v1.py",
        "tests/test_s3_real_rule_diagnostic_corrections_v1.py",
    ]


def build_manifest(stored: dict, started: str, runtime: float, evidence_rows: int) -> dict:
    return {
        "schema_version": SCHEMA_MANIFEST,
        "run_id": RUN_ID,
        "supersedes_run_id": SUPERSEDES_RUN_ID,
        "started_utc": started,
        "runtime_seconds": round(runtime, 3),
        "git_commit_before_checkpoint": git(["rev-parse", "HEAD"]),
        "declarations": {
            "development_only": True,
            "diagnostic_correction_only": True,
            "real_legal_rule_input": True,
            "synthetic_panel_used": False,
            "new_batch_experiment": False,
            "predictions_reused": True,
            "predictions_modified": False,
            "v1_artifacts_modified": False,
            "checkers_modified": False,
            "gold_modified": False,
            "thresholds_modified": False,
            "rule_inputs_modified": False,
            "human_answers_modified": False,
            "contracts_modified": False,
            "formal_oracle_promotion": False,
            "gold_publication": False,
            "new_llm_api_calls": 0,
            "native_check_calls": MAX_NATIVE_CALLS,
        },
        "hash_conventions": {
            "artifacts": "UTF-8, LF; committed bytes equal working-tree bytes",
            "sha256_raw_working_tree": "SHA-256 over the raw bytes on disk; the binding used by "
                                       "--check / --replay",
            "scope": "only this correction's own files are pinned to text eol=lf",
        },
        "inputs": {rel: file_binding(rel) for rel in input_paths()},
        "implementation": {rel: file_binding(rel) for rel in implementation_paths()},
        "new_implementation": {rel: file_binding(rel) for rel in new_implementation_paths()},
        "superseded_artifacts": {
            name: {"path": (V1_DIR / name).relative_to(ROOT).as_posix(),
                   "sha256": stored["sha256"][name], "copied_into_this_run": False,
                   "modified": False}
            for name in V1_FILES},
        "run": {
            "methods": list(V1.METHODS),
            "item_count": 33,
            "prediction_rows_reused": len(stored["predictions"]),
            "corrected_evidence_rows": evidence_rows,
            "native_check_calls": MAX_NATIVE_CALLS,
            "include_modalities": list(V1.INCLUDE_MODALITIES),
            "command": "python formal_experiment/scripts/repair_s3_real_rule_diagnostics_v1.py",
        },
        "results": {
            "mapping_evidence": {"path": EVIDENCE_FILE.relative_to(ROOT).as_posix(),
                                 "sha256": sha256_file(EVIDENCE_FILE), "rows": evidence_rows},
            "summary": {"path": SUMMARY_FILE.relative_to(ROOT).as_posix(),
                        "sha256": sha256_file(SUMMARY_FILE)},
            "corrections": {"path": CORRECTIONS_FILE.relative_to(ROOT).as_posix(),
                            "sha256": sha256_file(CORRECTIONS_FILE)},
        },
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "safety": {
            "gold_read": True, "gold_modified": False, "old_results_modified": False,
            "original_bpmn_modified": False, "frozen_scorer_modified": False,
            "v3_checker_modified": False, "thresholds_changed": False,
            "similarity_backend_changed": False, "nlp_model_changed": False,
            "network_calls": 0, "llm_api_calls": 0,
        },
    }


# ---------------------------------------------------------------------------
# build, verify, replay, CLI
# ---------------------------------------------------------------------------


def build_all(recompute: bool = True) -> dict:
    stored = read_v1_artifacts()
    rule_inputs = V1.build_rule_inputs()
    if recompute:
        recomputation = recompute_actor_pairs(stored, rule_inputs)
    else:
        recomputation = read_json(CORRECTIONS_FILE)["recomputation"]
    model_probe = recomputation["frozen_model_probe"]
    corrected = build_corrected(stored, rule_inputs, recomputation, model_probe)
    coverage = build_coverage(stored, corrected, model_probe)
    profile = condition_profile(rule_inputs)
    corrections = build_corrections(stored, rule_inputs, corrected, coverage, recomputation,
                                   model_probe, profile)
    summary = build_summary(stored, rule_inputs, corrected, coverage, profile, corrections)
    return {"stored": stored, "rule_inputs": rule_inputs, "corrected": corrected,
            "coverage": coverage, "corrections": corrections, "summary": summary,
            "recomputation": recomputation}


def write_outputs(built: dict, started: str, runtime: float) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    units = built["corrected"]["units"]
    with EVIDENCE_FILE.open("w", encoding="utf-8", newline="\n") as handle:
        for eid in sorted(units):
            handle.write(json.dumps(units[eid], ensure_ascii=False, sort_keys=True) + "\n")
    SUMMARY_FILE.write_bytes((json.dumps(built["summary"], ensure_ascii=False, indent=2)
                              + "\n").encode("utf-8"))
    CORRECTIONS_FILE.write_bytes((json.dumps(built["corrections"], ensure_ascii=False, indent=2)
                                  + "\n").encode("utf-8"))
    MANIFEST_FILE.write_bytes((json.dumps(
        build_manifest(built["stored"], started, runtime, len(units)),
        ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def summarise_references(corrections: dict) -> dict:
    return {method: {FAMILY_REFERENCE_KEY[family]: count for family, count
                     in corrections["count_table"]["new"]["reference_counts"][method].items()}
            for method in V1.METHODS}


def summarise_references_from_evidence(evidence: list[dict]) -> dict:
    counts = {method: dict.fromkeys(FAMILY_REFERENCE_KEY.values(), 0)
              for method in V1.METHODS}
    for row in evidence:
        counts[row["method"]][FAMILY_REFERENCE_KEY[row["family"]]] += \
            len(row["check_context_returns"])
    return counts


def verify_outputs() -> dict:
    manifest = read_json(MANIFEST_FILE)
    mismatched = []
    for section in ("inputs", "implementation", "new_implementation"):
        for rel, binding in manifest[section].items():
            if sha256_file(ROOT / rel) != binding["sha256_raw_working_tree"]:
                mismatched.append(f"{section}:{rel}")
    for key, entry in manifest["results"].items():
        if sha256_file(ROOT / entry["path"]) != entry["sha256"]:
            mismatched.append(f"results:{key}")
    for name, entry in manifest["superseded_artifacts"].items():
        path = ROOT / entry["path"]
        if not path.is_file() or sha256_file(path) != entry["sha256"]:
            mismatched.append(f"superseded:{name}")
    if mismatched:
        raise RuntimeError("hash mismatch: " + ", ".join(sorted(set(mismatched))))
    if sorted(path.name for path in OUT_DIR.iterdir()) != sorted(OUT_FILES):
        raise RuntimeError("the correction directory must hold exactly its four files")
    stored = read_v1_artifacts()
    evidence = read_jsonl(EVIDENCE_FILE)
    corrections = read_json(CORRECTIONS_FILE)
    summary = read_json(SUMMARY_FILE)
    if len(evidence) != len({row["evidence_id"] for row in evidence}):
        raise RuntimeError("corrected evidence ids must be unique")
    for row in evidence:
        if not row["evidence_id"].startswith("cev_"):
            raise RuntimeError("corrected evidence must use its own id namespace")
        if row["evidence_id"] in stored["evidence_index"]:
            raise RuntimeError("a corrected id must not collide with a v1 id")
        if not row["check_context_returns"]:
            raise RuntimeError("every corrected unit must keep its check contexts")
    known = {row["evidence_id"] for row in evidence}
    for mapping in corrections["prediction_evidence_map"]:
        for eid in mapping["corrected_evidence_ids"]:
            if eid not in known:
                raise RuntimeError(f"prediction mapping references missing evidence {eid}")
    if len(corrections["prediction_evidence_map"]) != 66:
        raise RuntimeError("every original item and method needs an explicit correction mapping")
    if len(corrections["per_unit_corrections"]) == 0:
        raise RuntimeError("per-unit corrections must be recorded")
    if summary["performance_claim_ready"] is not False:
        raise RuntimeError("the correction is a diagnostic, never a performance claim")
    if summary["predictions"]["modified"] is not False:
        raise RuntimeError("predictions must not be modified")
    if summarise_references(corrections) != summarise_references_from_evidence(evidence):
        raise RuntimeError("the reference counts in corrections.json must match the evidence rows")
    return {"evidence": evidence, "corrections": corrections, "summary": summary,
            "manifest": manifest, "stored": stored}


def replay_payload(native: bool = False) -> dict:
    """Offline re-derivation from the stored v1 artifacts; optional live re-check.

    With ``native`` the four authorised checker calls are executed again and must
    reproduce the recorded recomputation; the rebuilt artifacts still use the
    recorded record so that the replay is byte-stable (only wall-clock timings
    differ between two live runs).
    """
    stored = read_v1_artifacts()
    rule_inputs = V1.build_rule_inputs()
    recorded = read_json(CORRECTIONS_FILE)["recomputation"]
    if native:
        live = recompute_actor_pairs(stored, rule_inputs)
        if calls_signature(live["calls"]) != calls_signature(recorded["calls"]):
            raise RuntimeError("the live native recomputation does not reproduce the recorded "
                               "recomputation record")
        if live["pairs_by_item"] != recorded["pairs_by_item"]:
            raise RuntimeError("the live native recomputation does not reproduce the recorded "
                               "actor-action pair evidence")
        if live["frozen_model_probe"] != recorded["frozen_model_probe"]:
            raise RuntimeError("the live frozen-model probe does not reproduce the recorded probe")
    recomputation = recorded
    model_probe = recomputation["frozen_model_probe"]
    corrected = build_corrected(stored, rule_inputs, recomputation, model_probe)
    coverage = build_coverage(stored, corrected, model_probe)
    profile = condition_profile(rule_inputs)
    corrections = build_corrections(stored, rule_inputs, corrected, coverage, recomputation,
                                    model_probe, profile)
    summary = build_summary(stored, rule_inputs, corrected, coverage, profile, corrections)
    as_json = lambda value: json.loads(json.dumps(value, sort_keys=True))  # noqa: E731
    return {
        "evidence": as_json(sorted(corrected["units"].values(),
                                   key=lambda unit: unit["evidence_id"])),
        "stored_evidence": as_json(read_jsonl(EVIDENCE_FILE)),
        "summary": as_json(summary),
        "stored_summary": as_json(read_json(SUMMARY_FILE)),
        "corrections": as_json(corrections),
        "stored_corrections": as_json(read_json(CORRECTIONS_FILE)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify the bindings of the committed correction artifacts")
    parser.add_argument("--replay", action="store_true",
                        help="re-derive every corrected artifact offline and compare")
    parser.add_argument("--native", action="store_true",
                        help="with --replay: also re-run the four authorised native calls")
    args = parser.parse_args()

    if args.check or args.replay:
        verify_outputs()
        if args.replay:
            payload = replay_payload(native=args.native)
            for key in ("evidence", "summary", "corrections"):
                if payload[key] != payload[f"stored_{key}"]:
                    raise RuntimeError(f"{key} replay mismatch")
        print("S3 REAL RULE DIAGNOSTIC CORRECTIONS VERIFIED")
        return 0

    if OUT_DIR.exists() and any(OUT_DIR.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing run directory: {OUT_DIR}")
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    built = build_all(recompute=True)
    write_outputs(built, started, time.time() - t0)
    verified = verify_outputs()
    print(json.dumps({
        "run_id": RUN_ID,
        "supersedes": SUPERSEDES_RUN_ID,
        "prediction_rows_reused": 66,
        "corrected_evidence_rows": len(verified["evidence"]),
        "unique_counts": verified["corrections"]["count_table"]["new"]["unique_counts"],
        "reference_counts": verified["corrections"]["count_table"]["new"]["reference_counts"],
        "native_calls": verified["corrections"]["recomputation"]["call_count"],
        "llm_api_calls": 0,
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
