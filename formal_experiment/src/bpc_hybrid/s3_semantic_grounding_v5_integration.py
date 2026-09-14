"""Bind the v5 executor to frozen inputs, program checks and paired evaluation.

This module performs no network calls and no new rule extraction/action search.
It reuses frozen candidates, reconstructs hash-bound BPMN context, and keeps
mock artifacts separate from real execution evidence.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.s3_semantic_grounding_llm_v1 import (
    LLMGroundingExecutionError, validate_semantic_grounding_response,
)
from bpc_hybrid.s3_semantic_grounding_v2 import input_identity, json_sha256
from bpc_hybrid.s3_semantic_grounding_v3 import (
    evaluate_target_paired, fallback_transition_metrics,
)
from bpc_hybrid.s3_semantic_grounding_v4 import (
    apply_llm_grounding, normalize_llm_status, strip_grounding_context,
)
from bpc_hybrid.s3_semantic_grounding_v5 import apply_action_anchor_guard, decide
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_bytes
from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES

REVISION = "s3_semantic_grounding_v5_integration_v1"
EVIDENCE = "outputs/evidence/s3_semantic_grounding_v5"
PREDICTIONS = f"{EVIDENCE}/predictions.jsonl"
PANEL = "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
CONTRACT = "configs/stage1_structural_s11_s14.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def prepare_inputs(root: Path, pack: Mapping[str, Any],
                   request_set: Mapping[str, Any]) -> dict[str, Any]:
    """Verify all fallback object identities before any request is sent."""
    bindings = read_json(root / EVIDENCE / "artifact_hashes.json")["artifacts"]
    if sha256(root / PREDICTIONS) != bindings[PREDICTIONS]:
        raise LLMGroundingExecutionError("v5_prediction_hash_mismatch")
    preflight = read_json(root / EVIDENCE / "llm_preflight_v2.json")
    if json_sha256(pack) != preflight["candidate_pack_sha256"]:
        raise LLMGroundingExecutionError("v5_frozen_pack_mismatch")
    if request_set["request_set_sha256"] != preflight["request_set_sha256"]:
        raise LLMGroundingExecutionError("v5_frozen_request_set_mismatch")
    if json_sha256([r["body"] for r in request_set["requests"]]) != request_set["request_set_sha256"]:
        raise LLMGroundingExecutionError("request_body_hash_mismatch")
    rows = [json.loads(line) for line in (root / PREDICTIONS).read_text(
        encoding="utf-8").splitlines() if line.strip()]
    keys = [(r["item_id"], r["side"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise LLMGroundingExecutionError("duplicate_prediction_object")
    source_manifest = read_json(root / "outputs/evidence/s3_semantic_grounding_v2/manifest.json")
    for path in (PANEL, CONTRACT):
        if sha256(root / path) != source_manifest["inputs"][path]:
            raise LLMGroundingExecutionError(f"frozen_context_input_changed:{path}")
    panel = read_json(root / PANEL)
    # Select only routing fields here. Expected labels are consumed after
    # predictions have been saved, exclusively in evaluate_rows().
    routes = {item["variant_id"]: {
        side: item[f"{side}_bpmn"] for side in ("variant", "control")
    } for item in panel["variants"]}
    contract = load_stage1_contract(root / CONTRACT)
    contexts: dict[int, Any] = {}
    bpmn_hashes: dict[str, str] = {}
    requests = {r["fallback_item_id"]: r for r in request_set["requests"]}
    if len(requests) != len(pack["items"]) or pack["item_count"] != len(pack["items"]):
        raise LLMGroundingExecutionError("fallback_request_membership_mismatch")
    for item in pack["items"]:
        index = item["source_index"]
        if type(index) is not int or not 0 <= index < len(rows) or index in contexts:
            raise LLMGroundingExecutionError("fallback_source_index_invalid")
        row = rows[index]
        request = requests.get(item["fallback_item_id"], {})
        if request.get("source_index") != index or request.get("side") != row["side"]:
            raise LLMGroundingExecutionError("fallback_request_source_mismatch")
        if request.get("input_payload") != item["llm_visible_payload"]:
            raise LLMGroundingExecutionError("fallback_request_payload_mismatch")
        if row["side"] != item["side"] or any(
                row[key] != item[key] for key in
                ("canonical_rule_input_hash", "canonical_process_input_hash")):
            raise LLMGroundingExecutionError("fallback_row_identity_mismatch")
        relative = routes[row["item_id"]][row["side"]]
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()):
            raise LLMGroundingExecutionError("bpmn_path_outside_experiment")
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != row["bpmn_sha256"]:
            raise LLMGroundingExecutionError("fallback_bpmn_hash_mismatch")
        record = parse_bpmn_bytes(payload, source_path="s3_semantic_grounding_v2_panel.bpmn",
                                  contract=contract)
        xml_root = ET.fromstring(payload)
        sentence = copy.deepcopy(row["model_visible_rule_input"])
        identity = input_identity(sentence, record, xml_root, digest)
        if any(identity[key] != row[key] for key in
               ("canonical_rule_input_hash", "canonical_process_input_hash")):
            raise LLMGroundingExecutionError("reconstructed_context_identity_mismatch")
        contexts[index] = {"sentence": sentence, "record": record, "xml_root": xml_root}
        bpmn_hashes[relative] = digest
    return {"rows": rows, "contexts": contexts, "panel": panel,
            "input_hashes": {PREDICTIONS: sha256(root / PREDICTIONS),
                             PANEL: sha256(root / PANEL), CONTRACT: sha256(root / CONTRACT),
                             **bpmn_hashes}}


def bind_execution_directory(output_root: Path, config: Mapping[str, Any], mode: str,
                             pack: Mapping[str, Any], request_set: Mapping[str, Any],
                             prediction_hash: str) -> Path:
    """Fail before execution if a directory belongs to another mode/input set."""
    if mode not in {"mock", "real"}:
        raise LLMGroundingExecutionError("invalid_execution_mode")
    run_root = (output_root / str(config["run_root_name"])).resolve()
    if not run_root.is_relative_to(output_root.resolve()) or run_root == output_root.resolve():
        raise LLMGroundingExecutionError("invalid_execution_directory")
    identity = {"schema_version": "s3_v5_run_identity@1.0.0", "mode": mode,
                "candidate_pack_sha256": json_sha256(pack),
                "request_set_sha256": request_set["request_set_sha256"],
                "prediction_sha256": prediction_hash}
    identity_path = run_root / "run_identity.json"
    if identity_path.exists():
        if read_json(identity_path) != identity:
            raise LLMGroundingExecutionError("execution_mode_or_inputs_mismatch")
    else:
        if run_root.exists() and any(run_root.iterdir()):
            raise LLMGroundingExecutionError("legacy_execution_directory_unbound")
        run_root.mkdir(parents=True, exist_ok=True)
        with identity_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(identity, sort_keys=True) + "\n")
    return run_root


def apply_execution(prepared: Mapping[str, Any], pack: Mapping[str, Any],
                    request_set: Mapping[str, Any], summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Revalidate stored responses, apply with real context, retain the v5 guard."""
    requests = {r["fallback_item_id"]: r for r in request_set["requests"]}
    valid_results = []
    seen = set()
    for result in summary["results"]:
        fallback_id = result.get("fallback_item_id")
        request = requests.get(fallback_id)
        if not request or fallback_id in seen:
            raise LLMGroundingExecutionError("execution_result_membership_mismatch")
        seen.add(fallback_id)
        if (result.get("source_index") != request["source_index"] or
                result.get("request_sha256") != request["request_sha256"]):
            raise LLMGroundingExecutionError("execution_result_binding_mismatch")
        if result.get("status") not in {"validated", "resolved", "ambiguous", "unknown"}:
            continue
        response = result.get("response")
        validated = validate_semantic_grounding_response(json.dumps(response), request)
        if validated["status"] != "valid":
            raise LLMGroundingExecutionError("saved_response_failed_revalidation")
        valid_results.append({**result, "status": normalize_llm_status(response)})
    before = prepared["rows"]
    after = apply_llm_grounding(before, valid_results, pack=pack,
                                contexts=prepared["contexts"])
    for result in valid_results:
        index = result["source_index"]
        row = after[index]
        if "llm_application" not in row:
            raise LLMGroundingExecutionError("validated_response_not_consumed")
        checks, changes = apply_action_anchor_guard(
            prepared["contexts"][index]["sentence"], row["action_grounding"], row["checks"])
        if changes:
            row["checks"] = checks
            row["post_llm_anchor_guard"] = changes
        row["decision"] = decide(row["checks"])
        row["predicted_violation_type"] = row["decision"].get("predicted")
        row["scores"] = {target: row["checks"].get(target, {}).get("score")
                         for target in EXTENDED_TYPES}
        row["observability"] = {target: row["checks"].get(target, {}).get("observable")
                                for target in EXTENDED_TYPES}
    return strip_grounding_context(after)


def evaluate_rows(before: list[dict], after: list[dict], panel: Mapping[str, Any]) -> dict[str, Any]:
    expected = {item["variant_id"]: item["expected_violation"] for item in panel["variants"]}
    metrics = {}
    for name, rows in (("before", before), ("after", after)):
        metrics[name] = evaluate_target_paired(
            [r for r in rows if r["side"] == "variant"],
            [r for r in rows if r["side"] == "control"], expected)
    metrics["transitions"] = fallback_transition_metrics(before, after, expected)
    metrics["changed_check_count"] = sum(
        (a["checks"].get(t, {}).get("observable"), a["checks"].get(t, {}).get("violation")) !=
        (b["checks"].get(t, {}).get("observable"), b["checks"].get(t, {}).get("violation"))
        for a, b in zip(before, after, strict=True) for t in EXTENDED_TYPES)
    return metrics


def publish_results(root: Path, prepared: Mapping[str, Any], pack: Mapping[str, Any],
                    request_set: Mapping[str, Any], summary: Mapping[str, Any],
                    run_root: Path, mode: str, *, publication_root: Path | None = None) -> dict[str, Any]:
    if summary["mode"] != mode:
        raise LLMGroundingExecutionError("execution_summary_mode_mismatch")
    after = apply_execution(prepared, pack, request_set, summary)
    base = publication_root or root / "outputs/evidence" / REVISION / mode
    base.mkdir(parents=True, exist_ok=True)
    serial = 1
    while (base / f"attempt_{serial:03d}").exists():
        serial += 1
    output = base / f"attempt_{serial:03d}"
    output.mkdir()
    _write_json(output / "execution_summary.json", summary)
    # Snapshot mutable execution stores so a later resume cannot invalidate
    # the already published evaluation manifest.
    for path in [run_root / "run_identity.json", Path(summary["ledger_path"]),
                 Path(summary["normalized_path"])]:
        if path.is_file():
            (output / path.name).write_bytes(path.read_bytes())
    raw_snapshots = output / "raw_responses"
    for path in sorted(Path(summary["raw_response_dir"]).glob("*.json")):
        raw_snapshots.mkdir(exist_ok=True)
        (raw_snapshots / path.name).write_bytes(path.read_bytes())
    prediction_path = output / "predictions.jsonl"
    prediction_path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True,
                                                 allow_nan=False) + "\n" for r in after),
                               encoding="utf-8", newline="\n")
    # Evaluation labels are consumed only after the complete prediction file exists.
    metrics = evaluate_rows(prepared["rows"], after, prepared["panel"])
    report = {"revision": REVISION, "mode": mode, "scope": "development_only",
              "mock_only_not_experimental": mode == "mock", "run_status": summary["run_status"],
              "object_count": len(after), "fallback_count": pack["item_count"],
              "response_object_count": sum("llm_application" in row for row in after),
              "unique_request_count": summary["unique_request_count"],
              "execution_counts": summary["counts"],
              "known_usage_complete": summary["known_usage_complete"], **metrics}
    _write_json(output / "comparison.json", report)
    (output / "comparison.md").write_text(
        f"# V5 fallback integration ({mode})\n\n"
        + ("Offline plumbing evidence only; no LLM performance claim.\n\n" if mode == "mock"
           else "Development panel only; no formal Oracle/generalization claim.\n\n")
        + f"Execution status: {summary['run_status']}; objects: {len(after)}.\n\n"
        + "| Measure | Before | After |\n|---|---|---|\n"
        + "".join(f"| {key} | {metrics['before'][key]} | {metrics['after'][key]} |\n"
                  for key in ("macro_f1_four_types", "pair_success_count",
                              "target_field_unknown_rate", "control_target_false_positive_rate")),
        encoding="utf-8", newline="\n")
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root,
                                         text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    code_paths = ["scripts/run_s3_semantic_grounding_llm_v2.py",
                  "src/bpc_hybrid/s3_semantic_grounding_v5_integration.py",
                  "src/bpc_hybrid/s3_semantic_grounding_llm_v1.py",
                  *[f"src/bpc_hybrid/s3_semantic_grounding_v{n}.py" for n in range(1, 6)],
                  "src/bpc_hybrid/stage1_process.py",
                  "configs/stage3_semantic_grounding_v5.json"]
    manifest = {"revision": REVISION, "mode": mode, "git_commit": commit,
                "git_commit_is_base_revision": True,
                "implementation_hash_basis": "working_tree_raw_bytes_at_publication",
                "run_status": summary["run_status"], "mock_only_not_experimental": mode == "mock",
                "object_count": len(after), "fallback_count": pack["item_count"],
                "input_hashes": prepared["input_hashes"],
                "candidate_pack_sha256": json_sha256(pack),
                "request_set_sha256": request_set["request_set_sha256"],
                "implementation_hashes": {p: sha256(root / p) for p in code_paths},
                "artifact_hashes": {p.relative_to(output).as_posix(): sha256(p)
                                    for p in output.rglob("*") if p.is_file()}}
    _write_json(output / "manifest.json", manifest)
    return {"output_directory": str(output), "manifest": str(output / "manifest.json"),
            "report": report}
