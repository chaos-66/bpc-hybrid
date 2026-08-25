# -*- coding: utf-8 -*-
"""Build the four Experiment D Direct-LLM prompt arms (prepared, zero API).

* full_v6_6shot        : the frozen v6 prompt (reused, never overwritten).
* no_fewshot           : v6 with the ``## Examples`` few-shot section removed
                         (identical field definitions; sampling policy kept).
* minimal_prompt       : task + JSON schema only (field definitions, counter-
                         examples and disambiguation rules removed).
* barrientos_style     : six-field output contract formatted with Barrientos
                         (2026) structure cues and example style: top-level
                         keys enumerated once, explicit controlled-vocabulary
                         rules, no reasoning text, no code fences, one JSON
                         object only (adapted to the six-field schema, NOT a
                         schema replacement).

All variants are stored read-only in prompts/sun_compat/ablation_v1/ with
SHA-256 pinned in the suite manifest.  NONE of them invoke the model.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT_DIR = ROOT / "prompts" / "sun_compat"
OUT_DIR = ROOT / "prompts" / "sun_compat" / "ablation_v1"

V6 = PROMPT_DIR / "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md"

BARRIENTOS_PROMPT = (
    ROOT.parent / "references" / "barrientos_2026" / "artifact_input" / "prompts"
    / "formalize_requirements_prompt.txt"
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _no_fewshot(v6: str) -> str:
    """Strip the ## Examples few-shot block (from '## Examples' to the next
    top-level '## ' heading), keeping field definitions and sampling."""
    marker = "## Examples"
    idx = v6.find(marker)
    if idx < 0:
        raise RuntimeError("v6 prompt has no ## Examples section")
    tail = v6.find("\n## ", idx + len(marker))
    if tail < 0:
        tail = len(v6)
    return v6[:idx] + v6[tail + 1:]


def _minimal_prompt(v6: str, schema_note: str) -> str:
    """Task + schema identity only; no field definitions/counter-examples."""
    header = (
        "# Direct LLM Stage 2 Extraction — Minimal Prompt (ablation)\n\n"
        "> Task and JSON output contract only; detailed field definitions, "
        "counter-examples and disambiguation rules are removed for the "
        "minimal-prompt ablation arm.\n\n"
        "## System Prompt\n\n```text\n"
        "You are a regulatory text formalization expert. Extract one "
        "Sun-compatible Stage 2 canonical prediction record from the target "
        "text. Return ONLY one valid JSON object. No Markdown, commentary or "
        "reasoning.\n"
        "The output MUST conform to the JSON object structure shown below.\n"
        "```\n\n"
        "## Output JSON Structure (contract-identical)\n\n```text\n"
        + schema_note +
        "\n```\n\n"
        "## User Input\n\n{user_prompt}\n"
    )
    return header


def _barrientos_style(v6: str, barrientos_text: str) -> str:
    """Six-field adapter modelled on Barrientos' prompt discipline."""
    barrientos_system = (
        "## System Prompt (Barrientos-style structure discipline)\n\n```text\n"
        "You are an expert in formalizing procedural and compliance "
        "requirements for business-process compliance verification.\n"
        "Do not include any explanation, commentary, reasoning steps, or "
        "thinking — only return the JSON object as valid JSON.\n"
        "Given a requirement in plain text, output a single JSON object that "
        "represents the requirement in the six-field Sun Stage 2 structure. "
        "Output only the JSON object — no code fences, explanations, or "
        "additional text.\n"
        "Use the controlled six-field vocabulary exactly: modality is one of "
        "obligation, permission, prohibition, definition; actor, action, "
        "condition, constraint, exception follow the field definitions below. "
        "Do not invent new values.\n"
        "```\n\n"
    )
    # Extract the v6 field definitions (keep them verbatim for the contract)
    s = v6.find("## System Prompt")
    e = v6.find("## Examples", s)
    fields = v6[s:e] if e > s else v6[s:]
    return (
        "# Direct LLM Stage 2 Extraction — Barrientos-style Prompt (ablation)\n\n"
        "> Six-field output contract formatted with Barrientos et al. (2026) "
        "prompt discipline (top-level key enumeration, controlled vocabulary, "
        "no-reasoning instruction); the six-field schema is NOT replaced.\n\n"
        + barrientos_system +
        fields +
        "\n## User Input\n\n{user_prompt}\n"
    )


def main() -> int:
    v6_text = V6.read_text(encoding="utf-8")
    v6_sha = _sha256_bytes(V6.read_bytes())
    barrientos_text = BARRIENTOS_PROMPT.read_text(encoding="utf-8")
    barrientos_sha = _sha256_bytes(BARRIENTOS_PROMPT.read_bytes())

    artifacts = {
        "no_fewshot": _no_fewshot(v6_text),
        "minimal_prompt": _minimal_prompt(
            v6_text,
            "top-level keys: schema_version, sample_id, source_id, source_text, "
            "clauses, method, validation, unsupported_or_ambiguous; per clause: "
            "clause_id, clause_span, modality, actors, actions, conditions, "
            "constraints, exceptions, actor_action_map",
        ),
        "barrientos_style": _barrientos_style(v6_text, barrientos_text),
    }

    if OUT_DIR.exists():
        raise RuntimeError(f"refusing to overwrite: {OUT_DIR}")
    OUT_DIR.mkdir(parents=True)
    hashes: dict[str, str] = {}
    for name, text in artifacts.items():
        path = OUT_DIR / f"direct_llm_{name}_prompt_v1.md"
        path.write_text(text, encoding="utf-8", newline="\n")
        hashes[name] = _sha256_bytes(text.encode("utf-8"))

    manifest = {
        "schema_version": "d1_prompt_ablation_arms@1.0.0",
        "created_offline": True,
        "status": {
            "full_v6_6shot": "reuse_locked_formal_result",
            "no_fewshot": "prepared_not_executed_no_api",
            "minimal_prompt": "prepared_not_executed_no_api",
            "barrientos_style": "prepared_not_executed_no_api",
        },
        "inputs": {
            "v6_prompt_sha256": v6_sha,
            "barrientos_prompt_sha256": barrientos_sha,
        },
        "artifacts": {
            name: {
                "path": f"prompts/sun_compat/ablation_v1/direct_llm_{name}_prompt_v1.md",
                "sha256": h,
            }
            for name, h in hashes.items()
        },
        "run_commands": {
            "no_fewshot": (
                "python scripts/run_direct_llm.py --input data/input/estg150_input_v1.jsonl "
                "--prompt prompts/sun_compat/ablation_v1/direct_llm_no_fewshot_prompt_v1.md "
                "--output <OUT> --manifest <MF> --allow-llm  (requires user API authorization)"
            ),
            "minimal_prompt": (
                "python scripts/run_direct_llm.py --input data/input/estg150_input_v1.jsonl "
                "--prompt prompts/sun_compat/ablation_v1/direct_llm_minimal_prompt_prompt_v1.md "
                "--output <OUT> --manifest <MF> --allow-llm  (requires user API authorization)"
            ),
            "barrientos_style": (
                "python scripts/run_direct_llm.py --input data/input/estg150_input_v1.jsonl "
                "--prompt prompts/sun_compat/ablation_v1/direct_llm_barrientos_style_prompt_v1.md "
                "--output <OUT> --manifest <MF> --allow-llm  (requires user API authorization)"
            ),
        },
        "safety": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "v6_prompt_unmodified": True,
        },
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("D prompt arms prepared (no model call):", OUT_DIR.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())