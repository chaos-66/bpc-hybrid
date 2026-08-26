# -*- coding: utf-8 -*-
"""Barrientos ablation suite v2 — orchestrator + D/E real-model executor.

Modes:
* ``--suite``            : run the offline suite (A renamed conditions +
                           B structural metrics + C + D/E readiness), write
                           outputs/development/barrientos_ablation_suite_v2/
                           and outputs/reports/barrientos_ablation_comparison_v2.*
* ``--dry-run``          : off-network wiring check of the D/E real-model arms
                           (zero API calls; prints per-arm sample counts and
                           prompt hashes).
* ``--execute-de``       : real-model execution of the D and E arms.  Requires
                           ``--auth-file`` (user API authorization).  Records
                           raw responses, canonical predictions, evaluation,
                           manifest, hashes, runtime, usage, cost and failed
                           samples per arm.  NEVER runs without authorization.

v2 fixes vs v1:
* A conditions renamed to full_locked / schema_only_approx / raw_approx and
  framed as an OFFLINE APPROXIMATION SENSITIVITY ANALYSIS (raw model JSON was
  not persisted in the locked s27 artifacts).
* E input contract v2: 36 unique versioned IDs derived from the frozen S2.12
  complex corpus (the flawed 38-record v1 contract is superseded).
* B: structural metrics (actor-action map gold resolvability, predicted map
  internal validity, map-change-vs-full samples, modality label macro-F1,
  per-field P/R/F1, valid/invalid counts, per-flag change cases).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

CONFIG = ROOT / "configs/ablations/barrientos_ablation_suite_v2.json"
E_CONTRACT = ROOT / "configs/ablations/e_same_data_input_contract_v2.json"
ESTG_INPUT = ROOT / "data/input/estg150_formal_inference_input_v2.json"
D1_REGISTRY = ROOT / "configs/models/estg150_d1_active_registry_v1.json"
OUT_DIR = ROOT / "outputs/development/barrientos_ablation_suite_v2"
REPORT_DIR = ROOT / "outputs/reports"
B_RESULTS = ROOT / "outputs/development/b0_module_removal_ablation_v1/results.json"

D_ARMS = ("D-full", "D-no-fewshot", "D-minimal", "D-barrientos-style")
D_MAIN_ARMS = ("D-no-fewshot", "D-minimal", "D-barrientos-style")
# 36-requirement protocol arms (Barrientos Step-1 faithful + ours on the SAME
# 36 inputs, 5 independent runs each per the published protocol).
S36_ARMS = ("BARR-FULL", "BARR-NO-PATTERN", "OURS-FULL",
            "OURS-BARRIENTOS-MODULE")
S36_PAPER_ARMS = ("BARR-FULL", "OURS-FULL", "OURS-BARRIENTOS-MODULE")
S36_OPTIONAL_ABLATION_ARMS = ("BARR-NO-PATTERN",)  # artifact-supported only


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {label}: {path}") from exc


def _write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


# ---------------------------------------------------------------------------
# Suite mode
# ---------------------------------------------------------------------------


def _run_a(config: Mapping[str, Any]) -> dict[str, Any]:
    from run_barrientos_ablation_suite_v1 import run_experiment_a
    a = run_experiment_a(config)
    old_to_new = {
        "full": "full_locked",
        "schema_only": "schema_only_approx",
        "raw_approximation": "raw_approx",
    }
    a["conditions"] = {old_to_new[k]: v for k, v in a["conditions"].items()}
    a["nature"] = (
        "OFFLINE APPROXIMATION SENSITIVITY ANALYSIS: full_locked is the locked "
        "D1-R3 canonical result; schema_only_approx and raw_approx are "
        "constructed from the post-canonical output by first-occurrence "
        "re-anchoring because the raw model JSON was not persisted. They are "
        "NOT exact raw-response ablations."
    )
    return a


def _run_b() -> dict[str, Any]:
    if not B_RESULTS.is_file():
        raise RuntimeError("B results missing; run run_b0_module_removal_ablation_v1 first")
    b = _load_json(B_RESULTS, "B results")
    return {
        "experiment": "B_rules_only_module_removal",
        "status": "executed",
        "full": {
            "overall_f1": b["full"]["metrics"]["overall"]["f1"],
            "per_field_f1": {k: v["f1"] for k, v in b["full"]["metrics"]["per_field"].items()},
            "modality_label_accuracy": b["full"]["modality_label_accuracy"],
            "modality_label_macro_f1": b["full"]["modality_label_macro_f1"],
            "actor_action_map_metrics": b["full"]["actor_action_map_metrics"],
            "valid_outputs": b["full"]["valid_outputs"],
        },
        "per_flag": {
            flag: {
                "overall_f1": b[flag]["metrics"]["overall"]["f1"],
                "delta_vs_full_f1": b[flag].get("delta_vs_full_f1"),
                "per_field_f1": b[flag]["per_field_f1"],
                "modality_label_accuracy": b[flag]["modality_label_accuracy"],
                "modality_label_macro_f1": b[flag]["modality_label_macro_f1"],
                "actor_action_map_metrics": b[flag]["actor_action_map_metrics"],
                "failed_samples": b[flag]["failed_samples"],
                "valid_outputs": b[flag]["valid_outputs"],
                "example_change_cases": b[flag].get("example_change_cases", []),
                "note": b[flag].get("note"),
            }
            for flag in ("no_lexicon_extensions", "no_modality_classifier",
                         "no_actor_action_ownership", "no_multi_match_guard",
                         "no_de_en_alignment_validation")
        },
        "note": (
            "span P/R/F1 does not cover the structural actor-action map; "
            "gold-vs-predicted exact ID matching is not computable (gold map "
            "uses unresolved short IDs); reported map metrics are gold "
            "resolvability, predicted internal validity and "
            "map-change-vs-full samples"
        ),
    }


def _run_c(config: Mapping[str, Any]) -> dict[str, Any]:
    from run_barrientos_ablation_suite_v1 import run_experiment_c
    return run_experiment_c(config)


def _run_de() -> dict[str, Any]:
    e = _load_json(E_CONTRACT, "E v2 contract")
    return {
        "experiment": "D_E_real_model_arms",
        "status": "ready_to_execute_not_executed",
        "blocker": (
            "real model API calls require explicit user authorization; this "
            "zero-API batch does not execute them. Executor verification "
            "status: the D/E runner (one send per sample/repeat, raw+"
            "canonical same response hash, failed samples kept in the "
            "denominator, per-repeat evaluation.json, D-full reuse 0 calls, "
            "plan-derived call counts 990/1170) is verified end-to-end with "
            "a fake transport against the REAL per-arm evaluators (BARR "
            "native, OURS stratified, D literal-overlap); 39 focused tests "
            "pass."
        ),
        "D_arms": {
            "D-full": {"status": "reuse_locked_formal_result"},
            "D-no-fewshot": {"status": "ready_to_execute"},
            "D-minimal": {"status": "ready_to_execute"},
            "D-barrientos-style": {"status": "ready_to_execute"},
        },
        "E_arms": {
            "BARR-FULL": {"status": "ready_to_execute",
                          "protocol": "Barrientos published Step-1 "
                                      "(original prompt/schema/44-patterns, "
                                      "36x5)"},
            "BARR-NO-PATTERN": {"status": "ready_to_execute",
                                "protocol": "artifact-supported ablation "
                                            "(NOT a paper-table arm)",
                                "optional": True},
            "OURS-FULL": {"status": "ready_to_execute",
                          "protocol": "our six-field method on the SAME 36 "
                                      "inputs, 36x5"},
            "OURS-BARRIENTOS-MODULE": {"status": "ready_to_execute",
                                       "protocol": "our method with the "
                                                   "prompt/schema module "
                                                   "swapped to Barrientos "
                                                   "style, 36x5"},
            "stability": {
                "runs": 5,
                "note": "protocol mandates 5 independent runs per 36-requirement "
                        "arm; first main comparison run counts toward the five",
            },
        },
        "e_contract_v2": {
            "path": "configs/ablations/e_same_data_input_contract_v2.json",
            "sha256": _sha256_file(E_CONTRACT),
            "count": e["input_surface"]["count"],
            "unique_ids": e["input_surface"]["unique_ids"],
        },
        "real_execution_command": (
            "python scripts/run_barrientos_ablation_suite_v2.py --execute-de "
            "--auth-file <USER_AUTH> --stability-runs 5 "
            "[--include-no-pattern] "
            "--runtime-home D:/environment/stanford-corenlp-4.5.10 "
            "(990 calls without BARR-NO-PATTERN; 1170 with; requires user "
            "API authorization)"
        ),
    }


def run_suite() -> int:
    config = _load_json(CONFIG, "suite v2 config")
    results: dict[str, Any] = {
        "schema_version": "barrientos_ablation_results@2.0.0",
        "zero_api_batch": True,
        "config_sha256": _sha256_file(CONFIG),
    }
    t0 = time.time()
    results["A"] = _run_a(config)
    results["B"] = _run_b()
    results["C"] = _run_c(config)
    results["D_E"] = _run_de()
    results["runtime_seconds"] = round(time.time() - t0, 3)

    if OUT_DIR.exists():
        raise RuntimeError(f"refusing to overwrite: {OUT_DIR}")
    OUT_DIR.mkdir(parents=True)
    (OUT_DIR / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "config_snapshot.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "A": {
            "nature": results["A"]["nature"],
            "condition_metrics": {
                k: {"overall": v["metrics"]["overall"],
                    "per_field_f1": {f: v["metrics"]["per_field"][f]["f1"]
                                     for f in v["metrics"]["per_field"]}}
                for k, v in results["A"]["conditions"].items()
            },
        },
        "B": results["B"],
        "C": results["C"],
        "D_E": results["D_E"],
    }
    report = {
        "schema_version": "barrientos_ablation_comparison@2.0.0",
        "generated_zero_api": True,
        "summary": summary,
        "full_results": str((OUT_DIR / "results.json").relative_to(ROOT)),
        "notes": {
            "A": "offline approximation sensitivity analysis (raw JSON not persisted)",
            "B": "with structural map + modality label metrics",
            "D_E": "ready_to_execute_not_executed; real model calls require "
                   "authorization; executor verified end-to-end with a fake "
                   "transport against the real per-arm evaluators",
        },
    }
    _write_json(REPORT_DIR / "barrientos_ablation_comparison_v2.json", report)

    md = ["# Barrientos Ablation Comparison v2 (zero API)", "",
          "## Experiment A (offline approximation sensitivity analysis)",
          "| condition | overall F1 | note |"]
    for k, v in results["A"]["conditions"].items():
        md.append("| {} | {:.4f} | {} |".format(k, v["metrics"]["overall"]["f1"],
                                                v["note"]))
    md += ["", "## Experiment B (Rules-Only module removal, structural metrics)",
           "| flag | ΔF1 | label acc | label macro-F1 | map change | "
           "pred map validity |"]
    for flag, v in results["B"]["per_flag"].items():
        m = v["actor_action_map_metrics"]
        md.append("| {} | {:+.4f} | {:.4f} | {:.4f} | {} | {:.4f} |".format(
            flag, v["delta_vs_full_f1"] or 0.0,
            v["modality_label_accuracy"]["clause_label_accuracy"],
            v["modality_label_macro_f1"]["macro_f1"],
            m.get("map_change_vs_full_samples", 0),
            m.get("predicted_map_internal_validity", 0.0)))
    c = results["C"]
    md += ["", "## Experiment C",
           "4-class: {}; 3-class shared: {}; definition excluded={} ({:.2f}%)".format(
               c["four_class_counts"], c["three_class_shared_counts"],
               c["definition_excluded_count"],
               c["definition_coverage_loss_ratio"] * 100)]
    de = results["D_E"]
    md += ["", "## Experiment D/E", "status: " + de["status"],
           "E contract v2: {} unique records (sha {})".format(
               de["e_contract_v2"]["count"],
               de["e_contract_v2"]["sha256"][:16])]
    (REPORT_DIR / "barrientos_ablation_comparison_v2.md").write_text(
        "\n".join(md) + "\n", encoding="utf-8")
    print(f"Barrientos suite v2 complete (zero API): {OUT_DIR.relative_to(ROOT)}")
    return 0


# ---------------------------------------------------------------------------
# D/E real-model executor (gated)
# ---------------------------------------------------------------------------


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path.relative_to(ROOT.parent))


def _prompt_for(arm: str) -> Path:
    prompts = {
        "D-full": ROOT / "prompts/sun_compat/direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md",
        "D-no-fewshot": ROOT / "prompts/sun_compat/ablation_v1/direct_llm_no_fewshot_prompt_v1.md",
        "D-minimal": ROOT / "prompts/sun_compat/ablation_v1/direct_llm_minimal_prompt_prompt_v1.md",
        "D-barrientos-style": ROOT / "prompts/sun_compat/ablation_v1/direct_llm_barrientos_style_prompt_v1.md",
        "OURS-FULL": ROOT / "prompts/sun_compat/direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md",
        "OURS-BARRIENTOS-MODULE": ROOT / "prompts/sun_compat/ablation_v1/direct_llm_barrientos_style_prompt_v1.md",
        "BARR-FULL": ROOT.parent / "references/barrientos_2026/artifact_input/prompts/formalize_requirements_prompt.txt",
        "BARR-NO-PATTERN": ROOT.parent / "references/barrientos_2026/artifact_input/prompts/formalize_requirements_prompt_no_patterns.txt",
    }
    return prompts[arm]


def dry_run() -> dict[str, Any]:
    estg = _load_json(ESTG_INPUT, "EStG-150 input v2")
    e = _load_json(E_CONTRACT, "E v2 contract")
    result: dict[str, Any] = {
        "schema_version": "barrientos_de_dry_run@1.0.0",
        "mode": "dry_run_off_network",
        "llm_api_calls": 0,
        "network_calls": 0,
        "d_arms": {},
        "e_arms": {},
        "hashes": {
            "estg_input_v2": _sha256_file(ESTG_INPUT),
            "e_contract_v2": _sha256_file(E_CONTRACT),
            "registry": _sha256_file(D1_REGISTRY),
        },
    }
    for arm in D_ARMS:
        p = _prompt_for(arm)
        result["d_arms"][arm] = {
            "prompt": _rel(p), "prompt_sha256": _sha256_file(p),
            "samples": len(estg["records"]), "status": "dry_run_ok",
        }
    for arm in S36_PAPER_ARMS + S36_OPTIONAL_ABLATION_ARMS:
        p = _prompt_for(arm)
        result["e_arms"][arm] = {
            "prompt": _rel(p), "prompt_sha256": _sha256_file(p),
            "samples": e["input_surface"]["count"], "status": "dry_run_ok",
            "optional": arm in S36_OPTIONAL_ABLATION_ARMS,
        }
    print("D/E dry-run OK (zero network, zero calls)")
    return result


AUTH_SCHEMA_PATH = ROOT / "configs/schemas/s2_12_api_authorization_v1.schema.json"
D_FULL_LOCKED = ROOT / "data/predictions/direct_llm_formal_arm_v1/predictions.json"

STABILITY_CHOICES = (1, 5)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _req_body(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Deterministic request-body fingerprint (system+user messages, D1
    recipe sampling).  Used for request_body_sha256 attribution; the actual
    transport builds its own body from the same prompts via
    OpenAICompatibleRequestBuilder + the D1 request policy (stream=False,
    thinking disabled, response_format omitted)."""
    return {
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 4096,
        "stream": False,
        "thinking": {"type": "disabled"},
    }


def _fenced_blocks(raw: str, heading_prefix: str) -> list[str]:
    """Return the bodies of fenced ``` blocks whose nearest preceding
    ``## `` heading starts with ``heading_prefix`` (exact heading match on
    the heading line; the fenced block may carry a ``text`` info string)."""
    fence = re.compile(r"^```(?:text)?\s*$")
    lines = raw.splitlines()
    blocks: list[str] = []
    current_heading: str | None = None
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("## "):
            current_heading = line[3:].strip()
            i += 1
            continue
        if fence.match(line):
            j = i + 1
            body: list[str] = []
            while j < n and not fence.match(lines[j]):
                body.append(lines[j])
                j += 1
            if current_heading and current_heading.startswith(heading_prefix):
                blocks.append("\n".join(body))
            i = j + 1
            continue
        i += 1
    return blocks


def _render_prompt(arm: str, sid: str, text: str,
                   record: Mapping[str, Any] | None = None) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) faithful to each arm's protocol.

    * BARR-FULL / BARR-NO-PATTERN (Barrientos artifact protocol, verified in
      ``AnalyzeImpactRequirementChangesBusinessProcessCompliance.ipynb``):
      system = the FULL original prompt file text (as the artifact's
      ``load_prompt`` = ``f.read().strip()``); user = the JSON envelope
      ``{"ID": <record_id>, "version": <version>, "text": <text>}`` exactly
      as the artifact's ``process_formalization`` builds ``user_input``.
    * D-full / OURS-FULL: the locked D1 recipe (``run_direct_llm.py``):
      system = prompt's ``## System Prompt`` section; user = ``## User
      Prompt Template`` rendered with sample_id/source_id/source_text and the
      raw ``## Examples`` few-shot block.
    * D-no-fewshot: same recipe on the no-fewshot prompt (no Examples
      section -> empty few-shot block; field definitions unchanged).
    * D-minimal: task + JSON structure only (the ``## System Prompt`` and
      ``## Output JSON Structure`` blocks); user = the raw requirement text
      (most minimal input surface).
    * D-barrientos-style / OURS-BARRIENTOS-MODULE: the discipline preamble
      AND the v6 field definitions (both ``## System Prompt*`` blocks) as
      system; user = the v6 user template rendered with an empty few-shot
      block.
    """
    if arm in ("BARR-FULL", "BARR-NO-PATTERN"):
        system = _prompt_for(arm).read_text(encoding="utf-8").strip()
        rid = ""
        version = ""
        if record is not None:
            rid = str(record.get("record_id") or record.get("id") or "")
            version = str(record.get("version") or "")
        user = json.dumps({"ID": rid, "version": version, "text": text},
                          ensure_ascii=False)
        return system, user
    if arm in ("D-full", "OURS-FULL", "D-no-fewshot"):
        from bpc_hybrid.prompt_loader import load_prompt
        prompt = load_prompt(_prompt_name_for(arm))
        few_shot = _few_shot_block(prompt) if arm in ("D-full", "OURS-FULL") \
            else ""
        user = prompt.user_prompt_template.format(
            sample_id=sid, source_id=sid, source_text=text,
            few_shot_block=few_shot)
        return prompt.system_prompt, user
    if arm == "D-minimal":
        from bpc_hybrid.prompt_loader import load_prompt
        raw = _prompt_for(arm).read_text(encoding="utf-8")
        blocks = _fenced_blocks(raw, "System Prompt") \
            + _fenced_blocks(raw, "Output JSON Structure")
        # User prompt stays the standard D1 envelope (with empty few-shot
        # block) so the ablation isolates the SYSTEM content (task + field
        # names + JSON schema only), not the user message format.
        v6 = load_prompt("direct_llm_sun_record_prompt_v6_d1r1_2026_08_05")
        user = v6.user_prompt_template.format(
            sample_id=sid, source_id=sid, source_text=text,
            few_shot_block="")
        return "\n\n".join(blocks), user
    if arm in ("D-barrientos-style", "OURS-BARRIENTOS-MODULE"):
        from bpc_hybrid.prompt_loader import load_prompt
        raw = _prompt_for(arm).read_text(encoding="utf-8")
        system = "\n\n".join(_fenced_blocks(raw, "System Prompt"))
        prompt = load_prompt(_prompt_name_for(arm))
        user = prompt.user_prompt_template.format(
            sample_id=sid, source_id=sid, source_text=text,
            few_shot_block="")
        return system, user
    raise RuntimeError(f"no prompt rendering for {arm}")


def _prompt_name_for(arm: str) -> str:
    names = {
        "D-full": "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05",
        "OURS-FULL": "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05",
        "D-no-fewshot": "ablation_v1/direct_llm_no_fewshot_prompt_v1",
        "D-minimal": "ablation_v1/direct_llm_minimal_prompt_prompt_v1",
        "D-barrientos-style": "ablation_v1/direct_llm_barrientos_style_prompt_v1",
        "OURS-BARRIENTOS-MODULE": "ablation_v1/direct_llm_barrientos_style_prompt_v1",
    }
    return names[arm]


def _few_shot_block(prompt: Any) -> str:
    """Render the few-shot block exactly like the locked D1 runner
    (``run_direct_llm._few_shot_block``): the raw ``## Examples`` section of
    the prompt file, verbatim."""
    raw = getattr(prompt, "raw_text", "")
    start = raw.find("## Examples")
    end = raw.find("## Notes", start)
    if start == -1 or end == -1:
        return ""
    return raw[start:end].strip()


def call_once(
    arm: str,
    sample: Mapping[str, Any],
    prompt_text: str,
    transport: Any,
    cost_of: Callable[[Mapping[str, Any]], float],
) -> dict[str, Any]:
    """Send EXACTLY ONE request for one sample; return the CallResult.

    ``transport.send()`` is invoked only here.  Every invocation — success or
    error — counts as one actual call and its cost is recorded; usage missing
    is marked ``cost: unknown`` instead of a fake 0.
    """
    sid = sample.get("sample_id") or sample.get("id")
    text = sample.get("text") or sample.get("approved_text_en") or ""
    system_prompt, user_prompt = _render_prompt(arm, sid, text, sample)
    body = _req_body(system_prompt, user_prompt)
    body_bytes = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    body_sha = _sha256_bytes(body_bytes)
    request_id = f"{arm}:{sid}:{time.time_ns()}"

    try:
        from bpc_hybrid.llm_client import LLMRequest
        response = transport.send(LLMRequest(
            source_id=sid, source_text=text,
            system_prompt=system_prompt, user_prompt=user_prompt,
        ))
        content = response.content or ""
        decode = getattr(transport, "last_decode", None) or {}
        usage = dict(decode.get("usage") or {})
        status = "ok" if decode.get("status") in (None, "ok_message_content") else "error"
        error = None
    except Exception as exc:  # transport failure still counts as a call
        content = ""
        decode = {}
        usage = {}
        status = "error"
        error = str(exc)

    resp_sha = _sha256_bytes((content or "").encode("utf-8"))
    if usage:
        cost = cost_of(usage)
    else:
        cost = "unknown"

    return {
        "sample_id": sid,
        "arm": arm,
        "repeat_id": sample.get("_repeat_id", "repeat-01"),
        "request_body_sha256": body_sha,
        "request_id": decode.get("request_id") or request_id,
        "raw_response_content": content,
        "response_sha256": resp_sha,
        "usage": usage,
        "cost": cost,
        "request_status": status,
        "error": error,
        "network_call": 1,
    }


def call_once_n(
    arm: str,
    samples: Sequence[Mapping[str, Any]],
    prompt_text: str,
    transport: Any,
    cost_of: Callable[[Mapping[str, Any]], float],
) -> list[dict[str, Any]]:
    """One send per sample; returns the list of CallResults (raw rows)."""
    return [call_once(arm, s, prompt_text, transport, cost_of) for s in samples]


def parse_same_response(
    call_result: Mapping[str, Any],
    arm: str,
    source_text: str,
) -> dict[str, Any]:
    """PURE: parse CallResult.raw_response_content only.

    No transport creation, no network, no retry, no second request.  For our
    six-field arms the d1 adapter + span canonicalizer run on the SAME
    response; for E-barrientos-faithful the Barrientos tree is preserved
    verbatim.  The parsed outcome re-binds the exact response_sha256 and
    request_id so raw/canonical provenance provably match.
    """
    from bpc_hybrid.d1_schema_adapter import adapt_relay_record
    from bpc_hybrid.d1_span_canonicalizer import canonicalize_record_coordinates

    raw = (call_result.get("raw_response_content") or "").strip().strip("`")
    # mirror the artifact's safe_json_load: strip an optional leading
    # "json" marker left after code-fence removal
    raw = raw.strip()
    if raw.lower().startswith("json"):
        raw = raw[4:].strip()
    sid = call_result["sample_id"]
    resp_sha = call_result["response_sha256"]
    request_id = call_result["request_id"]

    try:
        payload = json.loads(raw)
    except Exception as exc:
        return {
            "sample_id": sid, "request_status": "failed",
            "error": f"non-json: {exc}", "response_sha256": resp_sha,
            "request_id": request_id, "canonical_record": None,
            "barrientos_record": None,
        }

    if arm in ("BARR-FULL", "BARR-NO-PATTERN"):
        return {
            "sample_id": sid, "request_status": "ok", "error": None,
            "response_sha256": resp_sha, "request_id": request_id,
            "canonical_record": None,
            "barrientos_record": {"record": payload,
                                  "response_sha256": resp_sha,
                                  "request_id": request_id},
        }

    try:
        adapter_payload, adapt_audit = adapt_relay_record(payload, source_text)
        if adapt_audit.get("status") == "failed":
            return {
                "sample_id": sid, "request_status": "failed",
                "error": "relay_schema_adaptation_failed: "
                         + "; ".join(adapt_audit.get("failed_reasons", [])),
                "response_sha256": resp_sha, "request_id": request_id,
                "canonical_record": None, "barrientos_record": None,
            }
        canonical, span_audit = canonicalize_record_coordinates(
            adapter_payload, source_text)
        if span_audit.get("status") == "failed":
            return {
                "sample_id": sid, "request_status": "failed",
                "error": "span_canonicalization_failed: "
                         + "; ".join(span_audit.get("failed_reasons", [])),
                "response_sha256": resp_sha, "request_id": request_id,
                "canonical_record": None, "barrientos_record": None,
            }
        # embed provenance on a deep copy so the persisted canonical row
        # provably shares this response's identity
        canonical = copy.deepcopy(canonical)
        canonical.setdefault("provenance", {})["response_sha256"] = resp_sha
        canonical["provenance"]["request_id"] = request_id
        return {
            "sample_id": sid, "request_status": "ok", "error": None,
            "response_sha256": resp_sha, "request_id": request_id,
            "canonical_record": canonical, "barrientos_record": None,
        }
    except Exception as exc:
        return {
            "sample_id": sid, "request_status": "failed",
            "error": f"canonicalization: {exc}", "response_sha256": resp_sha,
            "request_id": request_id, "canonical_record": None,
            "barrientos_record": None,
        }


def _prediction_row(parsed: Mapping[str, Any], arm: str) -> dict[str, Any]:
    """Success prediction or EMPTY failed prediction (denominator kept)."""
    if parsed["request_status"] == "ok":
        if arm in ("BARR-FULL", "BARR-NO-PATTERN"):
            return {
                "sample_id": parsed["sample_id"], "request_status": "ok",
                "response_sha256": parsed["response_sha256"],
                "request_id": parsed["request_id"],
                "barrientos_record": parsed["barrientos_record"],
            }
        return {
            "sample_id": parsed["sample_id"], "request_status": "ok",
            "response_sha256": parsed["response_sha256"],
            "request_id": parsed["request_id"],
            "record": parsed["canonical_record"],
        }
    return {
        "sample_id": parsed["sample_id"], "request_status": "failed",
        "error": parsed.get("error"), "record": {},
    }


def run_arm_once(
    arm: str,
    repeat_id: str,
    samples: Sequence[Mapping[str, Any]],
    prompt_text: str,
    transport: Any,
    cost_of: Callable[[Mapping[str, Any]], float],
    evaluator: Callable[[list[dict[str, Any]]], dict[str, Any]],
    *,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """One arm x one repeat: call -> save raw -> parse -> predict -> eval.

    The evaluator receives ALL predictions (success + empty failed), so
    failed samples stay in the denominator.  Writes (when out_dir given):
    raw_responses.jsonl / canonical_predictions.jsonl / failed_samples.jsonl /
    evaluation.json / manifest.json.  Returns the arm-run result dict."""
    calls: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    pred_rows: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    total_cost: float = 0.0
    cost_unknown = False

    for sample in samples:
        sample_with_repeat = dict(sample)
        sample_with_repeat["_repeat_id"] = repeat_id
        call = call_once(arm, sample_with_repeat, prompt_text, transport,
                         cost_of)
        calls.append(call)
        raw_rows.append({
            "sample_id": call["sample_id"],
            "arm": arm,
            "repeat_id": repeat_id,
            "request_body_sha256": call["request_body_sha256"],
            "request_id": call["request_id"],
            "raw_response_content": call["raw_response_content"],
            "response_sha256": call["response_sha256"],
            "usage": call["usage"],
            "cost": call["cost"],
            "request_status": call["request_status"],
            "error": call["error"],
        })
        if call["cost"] == "unknown":
            cost_unknown = True
        elif isinstance(call["cost"], (int, float)):
            total_cost += float(call["cost"])

        text = sample.get("text") or sample.get("approved_text_en") or ""
        parsed = parse_same_response(call, arm, text)
        row = _prediction_row(parsed, arm)
        pred_rows.append(row)
        if row["request_status"] != "ok":
            failed.append(row)

    evaluation = evaluator(pred_rows)

    actual_calls = len(calls)
    raw_agg = _sha256_bytes(
        b"".join(json.dumps(r, sort_keys=True).encode("utf-8") + b"\n"
                 for r in raw_rows))
    pred_agg = _sha256_bytes(
        b"".join(json.dumps(r, sort_keys=True).encode("utf-8") + b"\n"
                 for r in pred_rows))
    manifest = {
        "arm": arm,
        "repeat_id": repeat_id,
        "sample_count": len(samples),
        "actual_call_count": actual_calls,
        "failed_count": len(failed),
        "cost": "unknown" if cost_unknown else round(total_cost, 8),
        "raw_responses_aggregate_sha256": raw_agg,
        "canonical_predictions_aggregate_sha256": pred_agg,
        "per_sample_sha256_match": all(
            r["response_sha256"] == p.get("response_sha256")
            for r, p in zip(raw_rows, pred_rows)
            if r["request_status"] == "ok"
        ),
    }
    result = {
        "arm": arm,
        "repeat_id": repeat_id,
        "sample_count": len(samples),
        "actual_call_count": actual_calls,
        "failed_count": len(failed),
        "cost": "unknown" if cost_unknown else round(total_cost, 8),
        "evaluation": evaluation,
        "manifest": manifest,
        "raw_rows": raw_rows,
        "pred_rows": pred_rows,
        "failed": failed,
    }

    if out_dir is not None:
        if out_dir.exists():
            raise RuntimeError(f"refusing to overwrite: {out_dir}")
        out_dir.mkdir(parents=True)
        _write_arm_v2(
            out_dir, arm, repeat_id, samples, raw_rows, pred_rows, failed,
            evaluation, total_cost, cost_unknown,
        )
    return result


def _write_arm_v2(out_dir: Path, arm: str, repeat_id: str,
                  samples: Sequence[Mapping[str, Any]],
                  raw_rows, pred_rows, failed, evaluation,
                  total_cost: float, cost_unknown: bool) -> None:
    raw_agg = _sha256_bytes(
        b"".join(json.dumps(r, sort_keys=True).encode("utf-8") + b"\n"
                 for r in raw_rows))
    pred_agg = _sha256_bytes(
        b"".join(json.dumps(r, sort_keys=True).encode("utf-8") + b"\n"
                 for r in pred_rows))
    sample_ids = [s.get("sample_id") or s.get("id") for s in samples]

    (out_dir / "raw_responses.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in raw_rows),
        encoding="utf-8")
    (out_dir / "canonical_predictions.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in pred_rows),
        encoding="utf-8")
    (out_dir / "failed_samples.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in failed),
        encoding="utf-8")
    (out_dir / "evaluation.json").write_text(
        json.dumps({"arm": arm, "repeat_id": repeat_id,
                    "evaluation": evaluation,
                    "denominator": len(pred_rows)}, ensure_ascii=False,
                   indent=2) + "\n", encoding="utf-8")
    (out_dir / "manifest.json").write_text(
        json.dumps({
            "arm": arm,
            "repeat_id": repeat_id,
            "sample_count": len(samples),
            "actual_call_count": len(raw_rows),
            "sample_ids": sample_ids,
            "failed_count": len(failed),
            "cost": "unknown" if cost_unknown else round(total_cost, 8),
            "raw_responses_aggregate_sha256": raw_agg,
            "canonical_predictions_aggregate_sha256": pred_agg,
            "per_sample_sha256_match": all(
                r["response_sha256"] == p.get("response_sha256")
                for r, p in zip(raw_rows, pred_rows)
                if r["request_status"] == "ok"
            ),
            "prompt_sha256": _prompt_for(arm)
            and _sha256_file(_prompt_for(arm)),
            "evaluation_denominator": len(pred_rows),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Execution plan (pure)
# ---------------------------------------------------------------------------


def build_execution_plan(stability_runs: int = 5,
                         include_no_pattern: bool = False) -> list[dict[str, Any]]:
    """Protocol-aligned execution plan (derived, never hand-counted).

    * D prompt arms (EStG-150): D-full reused (0 calls); D-no-fewshot,
      D-minimal, D-barrientos-style each 150 calls once (repeat-01).
    * 36-requirement protocol arms (Barrientos published Step-1 protocol:
      36 inputs, 5 independent runs, temperature=0): each of
      BARR-FULL / OURS-FULL / OURS-BARRIENTOS-MODULE runs 36 x 5.
    * BARR-NO-PATTERN (artifact-supported ablation; NOT a paper-table arm)
      only when ``include_no_pattern=True``: 36 x 5.

    Totals: 990 (without BARR-NO-PATTERN) or 1170 (with).
    """
    if stability_runs not in STABILITY_CHOICES:
        raise ValueError(
            f"stability_runs must be one of {STABILITY_CHOICES}; got "
            f"{stability_runs}")
    if stability_runs != 5:
        raise ValueError(
            "the 36-requirement protocol mandates 5 independent runs; "
            "stability_runs must be 5 for this protocol")
    d_samples = 150
    e_samples = 36

    plan: list[dict[str, Any]] = []

    # D prompt arms (single run; no five-repeat)
    plan.append({"arm": "D-full", "repeat_id": "repeat-01",
                 "sample_count": d_samples, "reused": True,
                 "expected_calls": 0})
    for arm in D_MAIN_ARMS:
        plan.append({"arm": arm, "repeat_id": "repeat-01",
                     "sample_count": d_samples, "reused": False,
                     "expected_calls": d_samples})

    # 36-requirement protocol arms: 5 independent runs each
    for arm in S36_PAPER_ARMS:
        for repeat in range(1, 6):
            plan.append({"arm": arm, "repeat_id": f"repeat-{repeat:02d}",
                         "sample_count": e_samples, "reused": False,
                         "expected_calls": e_samples})

    # artifact-supported ablation (paper says nothing about it)
    if include_no_pattern:
        for repeat in range(1, 6):
            plan.append({"arm": "BARR-NO-PATTERN",
                         "repeat_id": f"repeat-{repeat:02d}",
                         "sample_count": e_samples, "reused": False,
                         "expected_calls": e_samples})
    return plan


def expected_total_calls(stability_runs: int = 5,
                         include_no_pattern: bool = False) -> int:
    return sum(r["expected_calls"] for r in build_execution_plan(
        stability_runs, include_no_pattern))


# ---------------------------------------------------------------------------
# Stability evaluation (repeat-level agreements)
# ---------------------------------------------------------------------------


def _tree_diff_count(a: Any, b: Any, path: str = "") -> int:
    """Count differing field paths between two comparable structures
    (Barrientos tree or canonical record slices).  Used for the paper's
    element distance<=2 pairwise stability definition.  ``provenance``
    (run-specific hashes/ids) is excluded so run-identity metadata never
    inflates the distance."""
    if type(a) is not type(b):
        return 1
    if isinstance(a, dict):
        keys = set(a) | set(b)
        keys = {k for k in keys if k != "provenance"}
        return sum(_tree_diff_count(a.get(k), b.get(k), f"{path}.{k}")
                   for k in sorted(keys))
    if isinstance(a, list):
        if len(a) != len(b):
            return 1
        return sum(_tree_diff_count(x, y, f"{path}[{i}]")
                   for i, (x, y) in enumerate(zip(a, b)))
    return 0 if a == b else 1


def barrientos_pairwise_le2_ratio(
    runs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Paper Step-1 self-consistency: for each requirement, pairwise element
    distance between the 5 iterations; report the ratio of pairwise
    comparisons (across all requirements) with distance<=2 (the paper metric),
    plus mean/std of per-requirement ratios."""
    from itertools import combinations
    per_req_ratios: dict[str, float] = {}
    raw_pairs = 0
    le2_pairs = 0
    by_sample: dict[str, list[Any]] = {}
    for run in runs:
        for row in run["pred_rows"]:
            sid = row.get("sample_id")
            if sid is None:
                continue
            tree = None
            if row.get("barrientos_record") is not None:
                tree = (row.get("barrientos_record") or {}).get("record")
            elif row.get("record") is not None:
                tree = row.get("record")
            by_sample.setdefault(sid, []).append(tree)
    for sid, trees in by_sample.items():
        pairs = list(combinations(trees, 2))
        if not pairs:
            continue
        dists = [_tree_diff_count(a, b) for a, b in pairs]
        raw_pairs += len(dists)
        le2_pairs += sum(1 for d in dists if d <= 2)
        per_req_ratios[sid] = sum(1 for d in dists if d <= 2) / len(dists)
    vals = list(per_req_ratios.values())
    mean = sum(vals) / len(vals) if vals else 0.0
    std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5 if vals else 0.0
    return {
        "pairwise_comparisons": raw_pairs,
        "distance_le2_pairwise_ratio": round(le2_pairs / raw_pairs, 6)
        if raw_pairs else 0.0,
        "per_requirement_mean_ratio": round(mean, 6),
        "per_requirement_std_ratio": round(std, 6),
    }


def compute_stability(
    runs_by_arm: Mapping[str, Sequence[Mapping[str, Any]]],
    sample_set: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Repeat-level agreements over the SAME sample set.

    ``runs_by_arm[arm]`` = list of arm-run result dicts (from run_arm_once).
    Computes JSON validity agreement, modality agreement, output presence
    agreement and (for our six-field arms) field-span agreement, plus the
    paper's pairwise distance<=2 self-consistency ratio, plus most/least
    stable samples.
    """
    final: dict[str, Any] = {}
    for arm, runs in runs_by_arm.items():
        out = _compute_agreements_one_arm(arm, runs)
        out["pairwise_distance_le2_ratio"] = barrientos_pairwise_le2_ratio(
            runs)["distance_le2_pairwise_ratio"]
        out["pairwise_le2_detail"] = barrientos_pairwise_le2_ratio(runs)
        final[arm] = out
    return final


def _compute_agreements_one_arm(arm: str,
                                runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Repeat-level agreements for one arm (JSON validity, modality,
    presence, and — for our six-field arms — field/span agreement)."""
    def tree_of(pred_row: Mapping[str, Any]) -> Mapping[str, Any] | None:
        if pred_row.get("barrientos_record") is not None:
            return (pred_row.get("barrientos_record") or {}).get("record")
        return pred_row.get("record")

    def modality_of(pred_row: Mapping[str, Any]) -> str | None:
        tree = tree_of(pred_row)
        if not isinstance(tree, Mapping):
            return None
        if pred_row.get("barrientos_record") is not None:
            # Barrientos tree: modality lives on norms[]
            for norm in tree.get("norms") or []:
                m = norm.get("modality") if isinstance(norm, Mapping) else None
                if isinstance(m, str) and m:
                    return m
            return None
        for clause in tree.get("clauses") or []:
            mod = clause.get("modality") if isinstance(clause, Mapping) else None
            label = mod.get("label") if isinstance(mod, Mapping) else mod
            if label:
                return label
        return None

    def span_signature(pred_row: Mapping[str, Any]) -> str | None:
        """Deterministic span signature of a six-field canonical record."""
        tree = tree_of(pred_row)
        if not isinstance(tree, Mapping):
            return None
        clauses = tree.get("clauses")
        if not isinstance(clauses, list):
            return None
        parts: list[str] = []
        for clause in clauses:
            if not isinstance(clause, Mapping):
                continue
            for field in ("actors", "actions", "conditions", "constraints",
                          "exceptions"):
                for span in clause.get(field) or []:
                    if isinstance(span, Mapping):
                        parts.append(f"{field}:{span.get('text')}:"
                                     f"{span.get('start')}:{span.get('end')}")
        return "|".join(sorted(parts))

    def field_signature(pred_row: Mapping[str, Any], field: str) -> str | None:
        """Per-field value signature (modality label or span texts)."""
        tree = tree_of(pred_row)
        if not isinstance(tree, Mapping):
            return None
        if pred_row.get("barrientos_record") is not None:
            return None  # field-level agreement is a six-field concept only
        clauses = tree.get("clauses")
        if not isinstance(clauses, list):
            return None
        out: list[str] = []
        for clause in clauses:
            if not isinstance(clause, Mapping):
                continue
            if field == "modality":
                mod = clause.get("modality")
                label = mod.get("label") if isinstance(mod, Mapping) else mod
                out.append(str(label))
            else:
                for span in clause.get(field) or []:
                    if isinstance(span, Mapping):
                        out.append(str(span.get("text")))
        return "|".join(out)

    if not runs:
        return {}
    # align by sample_id across repeats
    sample_ids = set()
    for run in runs:
        for row in run["pred_rows"]:
            sample_ids.add(row["sample_id"])
    sid_list = sorted(sample_ids)
    validity_agree = 0.0
    modality_agree = 0.0
    presence_agree = 0.0
    field_agree = 0.0
    span_agree = 0.0
    six_field_arm = arm not in ("BARR-FULL", "BARR-NO-PATTERN")
    fields = ("modality", "actor", "action", "condition", "constraint",
              "exception")
    counters = {s: {"n": 0, "ok": 0, "modality": [], "spans": 0,
                    "field_vals": {f: [] for f in fields},
                    "span_sigs": []} for s in sid_list}
    for run in runs:
        by_id = {r["sample_id"]: r for r in run["pred_rows"]}
        for sid in sid_list:
            row = by_id.get(sid)
            counters[sid]["n"] += 1
            if row and row["request_status"] == "ok":
                counters[sid]["ok"] += 1
                mod = modality_of(row)
                if mod:
                    counters[sid]["modality"].append(mod)
                if six_field_arm:
                    for f in fields:
                        sig = field_signature(row, f)
                        counters[sid]["field_vals"][f].append(sig)
                    span_sig = span_signature(row)
                    if span_sig is not None:
                        counters[sid]["span_sigs"].append(span_sig)
            else:
                counters[sid]["modality"].append(None)
                if six_field_arm:
                    for f in fields:
                        counters[sid]["field_vals"][f].append(None)
    n = len(sid_list)
    if n:
        for sid in sid_list:
            c = counters[sid]
            validity_agree += c["ok"] / c["n"] if c["n"] else 0.0
            mods = [m for m in c["modality"] if m is not None]
            if mods:
                modality_agree += max(mods.count(m) for m in set(mods)) / len(mods)
            presence_agree += (1 if c["ok"] == c["n"] else 0)
            if six_field_arm:
                # field agreement: for each field, majority value fraction
                field_ratios = []
                for f in fields:
                    vals = [v for v in c["field_vals"][f] if v is not None]
                    if vals:
                        field_ratios.append(
                            max(vals.count(v) for v in set(vals)) / len(vals))
                if field_ratios:
                    field_agree += sum(field_ratios) / len(field_ratios)
                # span agreement: majority span-signature fraction
                if c["span_sigs"]:
                    span_agree += (
                        max(c["span_sigs"].count(s)
                            for s in set(c["span_sigs"]))
                        / len(c["span_sigs"]))
        validity_agree /= n
        modality_agree /= n
        presence_agree /= n
        if six_field_arm:
            field_agree /= n
            span_agree /= n
    # least/most stable: lowest/highest ok ratio
    stable = sorted(sid_list,
                    key=lambda s: counters[s]["ok"] / counters[s]["n"]
                    if counters[s]["n"] else 0.0)
    out: dict[str, Any] = {
        "json_validity_agreement": round(validity_agree, 6),
        "modality_agreement": round(modality_agree, 6),
        "output_presence_agreement": round(presence_agree, 6),
        "most_stable_samples": stable[-3:] if stable else [],
        "least_stable_samples": stable[:3] if stable else [],
    }
    if six_field_arm:
        out["field_agreement"] = round(field_agree, 6)
        out["span_agreement"] = round(span_agree, 6)
    else:
        out["field_agreement"] = None  # Barrientos tree has no six fields
        out["span_agreement"] = None
    return out


# ---------------------------------------------------------------------------
# Authorization content validation (reuses the repo's S2.12 schema file)
# ---------------------------------------------------------------------------


def synthetic_de_auth_fixture() -> dict[str, Any]:
    """Schema-shaped fixture for fake-transport tests only (never real)."""
    return {
        "schema_version": "s2_12_api_authorization@1.1.0",
        "authorization_sentence_utf8_sha256": "ab" * 32,
        "authorization_event_file": "configs/synthetic.json",
        "authorization_event_file_sha256": "cd" * 32,
        "model": "deepseek-v4-pro",
        "calls": {"direct_llm": 36, "sun_llm_fallback": 27},
        "stage_id": "D-CAL",
        "stage_payload_hashes": ["ab" * 32],
        "stage_call_cap": 1,
        "global_input_token_cap": 63000000,
        "global_output_token_cap": 258048,
        "global_usd_cost_cap": 84.18,
        "allowed_windows": "any_time",
        "price_snapshot": {
            "schema_version": "s2_12_price_snapshot@1.0.0",
            "currency": "USD",
            "input_cache_hit_per_million": 0.044,
            "input_cache_miss_per_million": 1.32,
            "output_per_million": 3.96,
        },
        "price_checked_at_utc": "2026-08-22T00:00:00Z",
        "runner_implementation_hashes": {
            "run_s2_12_direct_llm_v1": "ab" * 32,
            "run_s2_12_sun_llm_fallback_v1": "ab" * 32,
            "s2_12_execution": "ab" * 32,
            "llm_client": "ab" * 32,
            "h1_transport": "ab" * 32,
        },
        "input_config_prompt_hashes": {
            "input_sha256": "892d4284ea70c38f82a47f821c13622f1b07744253429e466038ddb5db96660e",
            "lock_sha256": "ab" * 32,
            "prompt_direct_sha256": "ab" * 32,
            "prompt_fallback_sha256": "ab" * 32,
        },
        "prev_stage_ledger_hash": "",
        "final_63_payload_hashes": ["ab" * 32] * 63,
        "retry": 0,
        "gold_isolation": {
            "api_arms_must_not_read_gold": True,
            "evaluation_only_after_predictions_are_locked": True,
        },
        "synthetic_fixture": True,
    }


def validate_auth_for_de(auth_path: Path,
                         allow_fake_fixture: bool = False) -> bool:
    """Content-validate an authorization file for D/E execution.

    Reuses the repo's existing S2.12 authorization schema file; rejects a
    missing/empty/non-JSON/arbitrary file; rejects synthetic fixtures unless
    ``allow_fake_fixture`` (fake-transport tests only).
    """
    if auth_path is None or not auth_path.is_file():
        raise RuntimeError("auth file does not exist")
    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"auth file is not valid JSON: {exc}") from exc
    if not isinstance(auth, dict) or not auth:
        raise RuntimeError("auth file must be a non-empty JSON object")

    is_fixture = auth.get("synthetic_fixture") is True
    if is_fixture and not allow_fake_fixture:
        raise RuntimeError("synthetic authorization fixture cannot be used "
                           "for real transport")

    try:
        schema = json.loads(AUTH_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"repo auth schema unreadable: {exc}") from exc

    required = set(schema.get("required", []))
    missing = sorted(required - set(auth))
    if missing:
        raise RuntimeError(f"auth file missing required fields: {missing}")
    if auth.get("schema_version") != "s2_12_api_authorization@1.1.0":
        raise RuntimeError("auth schema_version drift")
    if auth.get("model") != "deepseek-v4-pro":
        raise RuntimeError("auth model mismatch")
    if auth.get("retry") != 0:
        raise RuntimeError("auth retry must be 0")
    for cap in ("global_input_token_cap", "global_output_token_cap",
                "global_usd_cost_cap"):
        if not isinstance(auth.get(cap), (int, float)) or auth[cap] <= 0:
            raise RuntimeError(f"auth {cap} must be positive")
    if auth.get("gold_isolation", {}).get(
            "api_arms_must_not_read_gold") is not True:
        raise RuntimeError("auth Gold isolation declaration invalid")
    return True


# ---------------------------------------------------------------------------
# Dummy evaluators used by tests
# ---------------------------------------------------------------------------


def dummy_evaluator(preds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"computed": True, "prediction_count": len(preds)}


def denominator_evaluator(preds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"denominator": len(preds),
            "success_count": sum(1 for p in preds
                                 if p.get("request_status") == "ok")}


def aggregate_hash(rows: Sequence[Mapping[str, Any]]) -> str:
    return _sha256_bytes(
        b"".join(json.dumps(r, sort_keys=True).encode("utf-8") + b"\n"
                 for r in rows))


# ---------------------------------------------------------------------------
# Real execution driver (plan-driven; gated by authorization)
# ---------------------------------------------------------------------------


def _estg_samples() -> list[dict[str, Any]]:
    estg = _load_json(ESTG_INPUT, "EStG-150 input v2")
    return [{"sample_id": r["sample_id"], "text": r["approved_text_en"]}
            for r in estg["records"]]


def _e_samples() -> list[dict[str, Any]]:
    e = _load_json(E_CONTRACT, "E v2 contract")
    return [{"sample_id": i["sample_id"], "id": i["id"], "text": i["text"],
             "record_id": i.get("record_id") or "",
             "version": i.get("version") or ""}
            for i in e["input_surface"]["items"]]


S211_GOLD = ROOT / "data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json"
S211_GOLD_SHA = "039ae8b2429826ae2b320667fb4a0dff96de6408b0a9637c1d9911565129c804"
S211_LEVELS = ROOT / "outputs/reports/s2_11_proposal_report_v3.json"
S211_LEVELS_SHA = "0cd725b4e7e14c88a97ca005ec10dac3f7fc77c2ebf3955eb746abdc9479616a"
S211_SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")


def _s211_gold_records() -> list[dict[str, Any]]:
    """Convert the frozen S2.11 gold document into evaluator-compatible
    records (same conversion as evaluate_s2_12_sun_rule_only_v1._gold_records):
    {sample_id, clauses: [{clause_id, modality:{label,evidence},
    actors/actions/conditions/constraints/exceptions: [spans]}]}."""
    if _sha256_file(S211_GOLD) != S211_GOLD_SHA:
        raise RuntimeError("frozen S2.11 Gold drift")
    doc = _load_json(S211_GOLD, "S2.11 gold")
    output: list[dict[str, Any]] = []
    for record in doc.get("records", []):
        clauses: list[dict[str, Any]] = []
        canonical = record.get("canonical") or {}
        for clause in canonical.get("clauses", []):
            converted: dict[str, Any] = {
                "clause_id": clause.get("clause_id"),
                "modality": {
                    "label": (clause.get("modality") or {}).get("label"),
                    "evidence": list((clause.get("modality") or {})
                                     .get("evidence") or []),
                },
            }
            for field in S211_SPAN_FIELDS:
                converted[field + "s"] = list(
                    (clause.get(field) or {}).get("spans") or [])
            clauses.append(converted)
        output.append({"sample_id": record.get("sample_id"),
                       "clauses": clauses})
    return output


def _s211_levels() -> dict[str, str]:
    """Frozen G0.5 stratum source: {sample_id: L1/L2/L3} (hash-locked)."""
    if _sha256_file(S211_LEVELS) != S211_LEVELS_SHA:
        raise RuntimeError("frozen stratum source drift")
    doc = _load_json(S211_LEVELS, "S2.11 levels")
    entries = doc.get("entries")
    if not isinstance(entries, dict):
        raise RuntimeError("frozen stratum source entries missing")
    return {sid: row["g0_5_level"] for sid, row in entries.items()}


def _make_evaluator(arm: str):
    """Return an evaluator fn (prediction rows -> metrics dict).

    D arms: Stage-2 literal-overlap + modality labels on the EStG-150 gold.
    E-ours / E-module-swapped: complex-corpus six-field evaluator (S2.12
    stratified evaluator v2) on the 36-record gold.
    E-barrientos-faithful: Barrientos-specific JSON validity / coverage /
    modality (shared 3-class) evaluation on its own tree.
    """
    if arm.startswith("D-"):

        def eval_d(preds):
            from bpc_hybrid.estg150_b0_development import (
                build_canonical_gold_records)
            from bpc_hybrid.stage2_sun_literal_overlap import (
                evaluate_sun_literal_overlap)
            import subprocess
            import tempfile
            gold_path = ROOT / "data/gold/stage2/estg150_formal_gold_v1.json"
            gold_file = _load_json(gold_path, "gold file")
            # build canonical gold from layer E @ 56d2b03 (same builder as
            # D1-R3): modality objects + clause structure expected by the
            # literal-overlap evaluator
            with tempfile.TemporaryDirectory(dir=ROOT / ".tmp") as td:
                work = Path(td)
                for key, path in (
                        ("layer_e",
                         "formal_experiment/data/development/human_review/"
                         "estg_150_human_correction_v1.json"),
                        ("membership",
                         "formal_experiment/data/development/estg/"
                         "estg_150_membership_hashes.json")):
                    blob = subprocess.run(
                        ["git", "show", f"56d2b03:{path}"], cwd=ROOT.parent,
                        capture_output=True, check=True).stdout
                    (work / key).write_bytes(blob)
                gold, _ = build_canonical_gold_records(work / "layer_e",
                                                       work / "membership")
            attempts = [{"sample_id": p["sample_id"],
                         "request_status": p["request_status"],
                         "record": p.get("record") or {}}
                        for p in preds]
            metrics = evaluate_sun_literal_overlap(
                gold, attempts,
                dataset_id="independently_reconstructed_estg_150_v1",
                method_id="direct_llm")
            return {
                "evaluator": "sun_literal_overlap@2.0.0",
                "metrics": metrics,
                "denominator": len(preds),
                "failed_count": sum(1 for p in preds
                                    if p["request_status"] != "ok"),
            }

        return eval_d

    if arm in ("OURS-FULL", "OURS-BARRIENTOS-MODULE"):

        def eval_e(preds):
            from bpc_hybrid.s2_12_stratified_evaluator_v2 import (
                evaluate_stratified)
            gold = _s211_gold_records()
            levels = _s211_levels()
            predictions = [{"sample_id": p["sample_id"],
                            "request_status": p["request_status"],
                            "record": p.get("record") or {}}
                           for p in preds]
            report = evaluate_stratified(
                gold, predictions, levels=levels,
                dataset_id="s2_11_barrientos_complex_corpus_36_v1",
                method_id="direct_llm"
                if arm == "OURS-FULL" else "direct_llm_barrientos_module")
            return {
                "evaluator": "s2_12_stratified_evaluator_v2",
                "metrics": report,
                "denominator": len(preds),
                "failed_count": sum(1 for p in preds
                                    if p["request_status"] != "ok"),
            }

        return eval_e

    if arm in ("BARR-FULL", "BARR-NO-PATTERN"):

        def eval_b(preds):
            """Barrientos-native Step-1 evaluator.

            Mirrors the artifact tool semantics (analysis_results_step_1.py):
            pooled TP/FP/FN per target (precondition / norm) across all
            requirements -> precision/recall/F1, plus strict JSON validity,
            output coverage, failed outputs, and shared 3-class modality
            agreement vs the S2.11 3-class gold.  The per-requirement gold is
            ``step_1_baseline.json`` (precondition count/action/operator and
            norm count/type).  NEVER uses the six-field evaluator on
            BARR-* arms.
            """
            baseline = _load_json(
                ROOT.parent / "references/barrientos_2026/evaluation/ground_truth"
                / "step_1_baseline.json", "Barrientos step-1 baseline")
            gold_by_id = {b["id"]: b for b in baseline}

            def gold_for(sample_id: str) -> dict[str, Any] | None:
                """Resolve the per-sample gold node from step_1_baseline.json.

                Sample ids are versioned (``SIM_card_scenario/r10/v1``):
                rid -> baseline id (``r10``), version -> ``v1``/``v2``.
                Entries with ``both_versions: true`` use the top-level
                precondition/norm; versioned entries resolve
                ``versions.version_1/version_2`` (nulls stay null).
                """
                rid = sample_id.split("/")[1] if "/" in sample_id \
                    else sample_id
                rid = re.sub(r"v\d+$", "", rid)
                entry = gold_by_id.get(rid)
                if entry is None:
                    return None
                if entry.get("both_versions") is True \
                        or not isinstance(entry.get("versions"), dict):
                    return entry
                version = sample_id.split("/")[2] if "/" in sample_id else ""
                key = {"v1": "version_1", "v2": "version_2"}.get(version)
                node = (entry.get("versions") or {}).get(key) if key else None
                return node if isinstance(node, dict) else entry

            def pool_count(target: str):
                tp = fp = fn = 0
                for p in preds:
                    sample_id = p.get("sample_id", "")
                    gold = gold_for(sample_id)
                    tree = (p.get("barrientos_record") or {}).get("record") or {}
                    if gold is None or not isinstance(tree, dict):
                        if gold is not None:
                            node = gold
                            fn += int((node.get(target) or {})
                                      .get("count", 0) or 0)
                        continue
                    if target == "precondition":
                        g_node = gold.get("precondition") or {}
                        g_count = int(g_node.get("count", 0) or 0)
                        gold_operator = (g_node.get("operator") or "AND").upper()
                        pre = tree.get("precondition", {}) or {}
                        # elements in the gold-operator bucket (AND/OR/NOT)
                        bucket = {
                            "AND": "and", "OR": "or", "NOT": "not",
                        }.get(gold_operator, "and")
                        bucket_actions = pre.get(bucket) or []
                        # fall back to all buckets if the gold operator
                        # bucket is empty but others are populated
                        other_keys = [k for k in ("and", "or", "not")
                                      if k != bucket]
                        if not bucket_actions:
                            bucket_actions = [a for k in other_keys
                                              for a in (pre.get(k) or [])]
                        p_count = len(bucket_actions)
                        c = min(p_count, g_count)  # type-correct count
                        tp += c
                        fp += max(0, p_count - g_count)
                        fn += max(0, g_count - c)
                    elif target == "norm":
                        g_node = gold.get("norm") or {}
                        g_count = int(g_node.get("count", 0) or 0)
                        norm_type = g_node.get("type")
                        norms = tree.get("norms", []) or []
                        p_count = len(norms)
                        type_ok = sum(
                            1 for n in norms
                            if norm_type is None
                            or str(n.get("modality")).lower()
                            == str(norm_type).lower())
                        tp += min(type_ok, g_count)
                        fp += max(0, p_count - type_ok)
                        fn += max(0, g_count - type_ok)
                precision = tp / (tp + fp) if (tp + fp) else 0.0
                recall = tp / (tp + fn) if (tp + fn) else 0.0
                f1 = (2 * precision * recall / (precision + recall)
                      if (precision + recall) else 0.0)
                return {"tp": tp, "fp": fp, "fn": fn,
                        "precision": round(precision, 6),
                        "recall": round(recall, 6), "f1": round(f1, 6)}

            def schema_valid_tree(tree: Any) -> bool:
                """Structural mirror of compliance_requirements_format.json
                (the artifact validates with jsonschema; jsonschema is not a
                repo dependency, so the same required structure is checked
                deterministically here)."""
                if not isinstance(tree, Mapping):
                    return False
                if not isinstance(tree.get("id"), str):
                    return False
                pre = tree.get("precondition")
                if not isinstance(pre, Mapping):
                    return False
                for key in ("and", "or", "not"):
                    if not isinstance(pre.get(key), list):
                        return False
                norms = tree.get("norms")
                if not isinstance(norms, list):
                    return False
                for norm in norms:
                    if not isinstance(norm, Mapping):
                        return False
                    if norm.get("modality") not in ("obligation", "permission",
                                                    "prohibition"):
                        return False
                    action = norm.get("action")
                    if not isinstance(action, Mapping):
                        return False
                    if action.get("dimension") not in ("control_flow", "data",
                                                       "resource", "time"):
                        return False
                    if not isinstance(action.get("compliance_pattern"), str):
                        return False
                tv = tree.get("temporal_validity")
                if not isinstance(tv, Mapping):
                    return False
                if not isinstance(tv.get("start"), str) \
                        or not isinstance(tv.get("end"), str):
                    return False
                return True

            valid = 0
            trees = []
            for p in preds:
                rec = p.get("barrientos_record") or {}
                if rec and isinstance(rec.get("record"), dict):
                    trees.append(rec["record"])
                    if schema_valid_tree(rec["record"]):
                        valid += 1
            modality = []
            for p in preds:
                rec = (p.get("barrientos_record") or {}).get("record") or {}
                norms = rec.get("norms") or []
                first = None
                for norm in norms:
                    m = norm.get("modality") if isinstance(norm, Mapping) \
                        else None
                    if m in ("obligation", "permission", "prohibition"):
                        first = m
                        break
                modality.append(first)
            gold = _s211_gold_records()
            gold_modalities = []
            for rec in gold:
                label = None
                for clause in rec.get("clauses", []):
                    candidate = (clause.get("modality") or {}).get("label")
                    if candidate in ("obligation", "permission",
                                     "prohibition"):
                        label = candidate
                        break
                gold_modalities.append(label)
            # per-sample first-norm vs first-gold-clause 3-class agreement
            # (same per-sample alignment as the OURS evaluator; unlabeled
            # predictions count as disagreement)
            n = len(modality)
            agree = sum(1 for a, b in zip(modality, gold_modalities)
                        if a == b)
            return {
                "evaluator": "barrientos_step1_artifact_evaluator",
                "precondition": pool_count("precondition"),
                "norm": pool_count("norm"),
                "strict_json_validity": round(valid / len(preds), 6)
                if preds else 0.0,
                "output_coverage": round(len(trees) / len(preds), 6)
                if preds else 0.0,
                "shared_3class_modality_agreement": round(agree / n, 6)
                if n else 0.0,                "denominator": len(preds),
                "failed_count": sum(1 for p in preds
                                    if p["request_status"] != "ok"),
                "note": (
                    "automated pooled-count reproduction of the paper's "
                    "Step-1 P/R/F1 semantics (analysis_results_step_1.py "
                    "pooled TP/FP/FN per target across requirements): "
                    "precondition elements counted in the gold-operator "
                    "bucket (and/or/not) vs step_1_baseline.json count; "
                    "norms counted by modality-type match vs baseline "
                    "norm.count/type; versioned gold resolved per sample "
                    "version (both_versions=false -> versions.version_N); "
                    "null precondition treated as count 0. strict "
                    "JSON/schema validity mirrors "
                    "compliance_requirements_format.json structurally "
                    "(jsonschema is not a repo dependency). The paper "
                    "scored semantic alignment via expert annotation; this "
                    "deterministic proxy is the closest artifact-code "
                    "reproduction and is NOT an expert judgement."),
            }

        return eval_b

    raise RuntimeError(f"no evaluator for {arm}")


def execute_de(auth_file: Path, stability_runs: int = 5,
               include_no_pattern: bool = False,
               transport_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    """Plan-driven real execution (auth-gated; fake in tests).

    ``transport_factory``: injectable for tests/fixtures only; the CLI path
    leaves it None and always builds the real transport (requires a real
    provider + real authorization, never a synthetic fixture).
    """
    validate_auth_for_de(auth_file, allow_fake_fixture=False)

    from bpc_hybrid.llm_client import RealAPITransport
    from bpc_hybrid.llm_config import LLMConfig
    from bpc_hybrid.h1_transport import H1RequestPolicy
    llm_config = LLMConfig.from_env(project_root=ROOT, load_project_env=False)
    if transport_factory is None:
        if llm_config.provider == "mock" or not llm_config.enabled:
            raise RuntimeError("real provider not enabled (process env only)")

        def _real_transport() -> Any:
            # D1 recipe: thinking-disabled WITHOUT json_object (the locked
            # July recipe; see run_direct_llm.py)
            return RealAPITransport(
                llm_config, timeout_seconds=180.0,
                policy=H1RequestPolicy(
                    stream=False, thinking={"type": "disabled"},
                    response_format=None))

        transport_factory = _real_transport

    plan = build_execution_plan(stability_runs,
                                include_no_pattern=include_no_pattern)
    samples_by_arm = {
        "D-full": _estg_samples(),
        "D-no-fewshot": _estg_samples(),
        "D-minimal": _estg_samples(),
        "D-barrientos-style": _estg_samples(),
        "OURS-FULL": _e_samples(),
        "BARR-FULL": _e_samples(),
        "BARR-NO-PATTERN": _e_samples(),
        "OURS-BARRIENTOS-MODULE": _e_samples(),
    }
    all_protocol_arms = list(S36_PAPER_ARMS)
    if include_no_pattern:
        all_protocol_arms.append("BARR-NO-PATTERN")

    def cost_of(usage):
        p = float(usage.get("prompt_tokens", 0))
        o = float(usage.get("completion_tokens", 0))
        return round(p * 1.32 / 1e6 + o * 3.96 / 1e6, 8)

    started = time.time()
    results: dict[str, Any] = {
        "schema_version": "barrientos_de_execution@1.1.0",
        "mode": "real_execution",
        "stability_runs": stability_runs,
        "planned_calls": sum(r["expected_calls"] for r in plan),
        "arms": {},
        "runs": [],
        "actual_calls": 0,
        "total_cost_usd": 0.0,
        "runtime_seconds": 0.0,
        "auth_file": str(auth_file),
    }

    runs_by_arm: dict[str, list[dict[str, Any]]] = {}
    for planned in plan:
        arm = planned["arm"]
        repeat_id = planned["repeat_id"]
        if planned["reused"]:
            # D-full: read the locked formal capsule; zero calls
            capsule = _load_json(D_FULL_LOCKED, "D-full locked capsule")
            results["runs"].append({
                "arm": arm, "repeat_id": repeat_id,
                "reused": True, "actual_call_count": 0,
                "sample_count": planned["sample_count"],
            })
            runs_by_arm.setdefault(arm, []).append({
                "arm": arm, "repeat_id": repeat_id, "reused": True,
                "pred_rows": [
                    {"sample_id": r["sample_id"], "request_status": "ok",
                     "record": r.get("record") or {}}
                    for r in capsule.get("records", [])
                ],
                "raw_rows": [], "failed": [],
            })
            continue
        run_dir = OUT_DIR / arm / repeat_id
        transport = transport_factory()
        run = run_arm_once(
            arm=arm, repeat_id=repeat_id,
            samples=samples_by_arm[arm],
            prompt_text="",  # rendered per-sample by call_once
            transport=transport,
            cost_of=cost_of,
            evaluator=_make_evaluator(arm),
            out_dir=run_dir,
        )
        results["actual_calls"] += run["actual_call_count"]
        if isinstance(run["cost"], (int, float)):
            results["total_cost_usd"] += run["cost"]
        results["arms"].setdefault(arm, {"repeats": []})
        results["arms"][arm]["repeats"].append({
            "repeat_id": repeat_id,
            "actual_call_count": run["actual_call_count"],
            "failed_count": run["failed_count"],
            "cost": run["cost"],
        })
        results["runs"].append({
            "arm": arm, "repeat_id": repeat_id, "reused": False,
            "actual_call_count": run["actual_call_count"],
            "failed_count": run["failed_count"],
            "sample_count": run["sample_count"],
        })
        runs_by_arm.setdefault(arm, []).append(run)
        print(f"[{arm}/{repeat_id}] calls={run['actual_call_count']} "
              f"failed={run['failed_count']}")

    if stability_runs == 5:
        stability_arms = ["OURS-FULL", "BARR-FULL",
                          "OURS-BARRIENTOS-MODULE"]
        if include_no_pattern:
            stability_arms.append("BARR-NO-PATTERN")
        e_stability = compute_stability(
            {a: rs for a, rs in runs_by_arm.items() if a in stability_arms},
            sample_set=_e_samples(),
        )
        results["stability"] = e_stability

    results["runtime_seconds"] = round(time.time() - started, 3)
    results["total_cost_usd"] = round(results["total_cost_usd"], 8)
    summary_path = OUT_DIR / "execution_summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2)
                            + "\n", encoding="utf-8")
    print(f"D/E real execution complete: {_rel(summary_path)}")
    return results


def _write_arm(arm_out: Path, arm: str, prompt_path: Path, sample_count: int,
               raw_rows, pipe_rows, failed, cost: float) -> None:
    """Deprecated v1 artifact writer — kept only for backward compatibility
    with callers that may still reference it; the v2 pipeline uses
    _write_arm_v2."""
    raise RuntimeError("_write_arm is deprecated; use _write_arm_v2")


def fixture_run(tmp_out: Path, stability_runs: int = 5,
                d_samples: int = 2, e_samples: int = 2) -> dict[str, Any]:
    """End-to-end fake-transport fixture (network calls = 0).

    Runs the FULL production plan wiring (plan -> run_arm_once -> REAL
    evaluator -> artifacts) with a counting deterministic fake transport on
    the REAL frozen sample sets (D-no-fewshot uses the real EStG-150 input;
    the 36-protocol arms use the real E-contract items), writing to
    ``tmp_out`` (never the production OUT_DIR).  Verifies actual send counts
    equal the sample counts (one call per sample/repeat), artifacts exist,
    and the REAL per-arm evaluators run (they load frozen gold/levels/
    baseline and compute metrics over the fake predictions).
    """
    from bpc_hybrid.llm_client import LLMResponse
    from bpc_hybrid.llm_client import LLMRequest

    class RecordingFake:
        """Deterministic fake transport.  BARR arms receive a minimal valid
        Barrientos tree; six-field arms receive a valid relay record."""

        def __init__(self, arm: str):
            self.arm = arm
            self.send_count = 0
            self.sent_ids: list[str] = []

        def _content(self, request) -> str:
            if self.arm in ("BARR-FULL", "BARR-NO-PATTERN"):
                return json.dumps({
                    "id": request.source_id,
                    "precondition": {"and": [], "or": [], "not": []},
                    "norms": [],
                    "temporal_validity": {
                        "start": "0000-01-01T00:00:00Z",
                        "end": "9999-12-31T23:59:59Z",
                    },
                }, ensure_ascii=False)
            return json.dumps({
                "schema_version": "1.0.0",
                "sample_id": request.source_id,
                "source_id": request.source_id,
                "source_text": request.source_text,
                "clauses": [],
                "method": {"name": "direct_llm",
                           "schema_source": "stage2_prediction.schema.json@1.0.0"},
                "validation": {"schema_valid": True,
                               "cross_field_valid": True, "errors": []},
            }, ensure_ascii=False)

        def send(self, request, *, ordinal=1, clause_id=None):
            self.send_count += 1
            self.sent_ids.append(request.source_id)
            self.last_decode = {
                "status": "ok_message_content", "model": "deepseek-v4-pro",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                          "total_tokens": 15},
                "request_id": f"req-{self.send_count}",
            }
            import hashlib
            content = self._content(request)
            self.last_decode["response_sha256"] = hashlib.sha256(
                content.encode("utf-8")).hexdigest()
            return LLMResponse(content=content, provider="fake",
                               model="deepseek-v4-pro", finish_reason="stop")

    plan = build_execution_plan(stability_runs, include_no_pattern=True)
    # D-no-fewshot (repeat-01) runs on the REAL EStG-150 input; the
    # 36-protocol arms run their full 5 repeats on the REAL contract items.
    subset: list[dict[str, Any]] = []
    for planned in plan:
        arm = planned["arm"]
        if planned["reused"]:
            continue
        if arm == "D-no-fewshot" and planned["repeat_id"] == "repeat-01":
            subset.append({**planned, "sample_count": 150})
        elif arm in ("BARR-FULL", "BARR-NO-PATTERN", "OURS-FULL",
                     "OURS-BARRIENTOS-MODULE"):
            subset.append({**planned, "sample_count": 36})

    samples_by_arm = {
        "D-no-fewshot": _estg_samples(),
        "OURS-FULL": _e_samples(),
        "OURS-BARRIENTOS-MODULE": _e_samples(),
        "BARR-FULL": _e_samples(),
        "BARR-NO-PATTERN": _e_samples(),
    }
    cost_of = lambda u: 0.001  # noqa: E731

    total_sends = 0
    runs_by_arm: dict[str, list[dict[str, Any]]] = {}
    reports: list[dict[str, Any]] = []
    for planned in subset:
        arm = planned["arm"]
        transport = RecordingFake(arm)
        run = run_arm_once(
            arm=arm, repeat_id=planned["repeat_id"],
            samples=samples_by_arm[arm],
            prompt_text="",  # rendered per-sample by call_once
            transport=transport,
            cost_of=cost_of,
            evaluator=_make_evaluator(arm),
            out_dir=tmp_out / arm / planned["repeat_id"],
        )
        total_sends += transport.send_count
        runs_by_arm.setdefault(arm, []).append(run)
        reports.append({
            "arm": arm, "repeat_id": planned["repeat_id"],
            "sample_count": run["sample_count"],
            "actual_call_count": run["actual_call_count"],
            "send_count": transport.send_count,
            "failed_count": run["failed_count"],
            "evaluation_keys": sorted((run.get("evaluation") or {}).keys()),
        })

    stability = compute_stability(runs_by_arm, sample_set=[]) \
        if stability_runs == 5 else {}
    summary = {
        "schema_version": "barrientos_fixture@1.0.0",
        "network_calls": total_sends,
        "reports": reports,
        "expected_send_count": sum(
            r["sample_count"] for r in subset
        ),
        "stability": stability,
        "artifacts_exist": all(
            (tmp_out / a["arm"] / a["repeat_id"] / f).is_file()
            for a in reports
            for f in ("raw_responses.jsonl", "canonical_predictions.jsonl",
                      "failed_samples.jsonl", "evaluation.json",
                      "manifest.json")
        ),
    }
    (tmp_out / "fixture_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fixture", type=Path, default=None,
                        help="run the fake-transport end-to-end fixture into "
                             "the given temp dir (zero network)")
    parser.add_argument("--execute-de", action="store_true")
    parser.add_argument("--auth-file", type=Path, default=None)
    parser.add_argument("--stability-runs", type=int, default=5,
                        choices=(5,),
                        help="protocol mandates 5 independent runs on the 36 "
                             "requirements (990 calls; 1170 with "
                             "--include-no-pattern)")
    parser.add_argument("--include-no-pattern", action="store_true",
                        help="also run BARR-NO-PATTERN (artifact-supported "
                             "ablation, NOT a paper-table arm): +180 calls")
    args = parser.parse_args()
    try:
        if args.fixture is not None:
            result = fixture_run(args.fixture,
                                 stability_runs=args.stability_runs)
        elif args.execute_de:
            result = execute_de(args.auth_file,
                                stability_runs=args.stability_runs,
                                include_no_pattern=args.include_no_pattern)
        elif args.dry_run:
            result = dry_run()
        elif args.suite:
            return run_suite()
        else:
            parser.error("choose --suite, --dry-run, --fixture or "
                         "--execute-de")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:1500])
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())