# -*- coding: utf-8 -*-
"""Build three interpretable Direct-LLM prompt-factor ablation arms.

This builder is deliberately offline.  It derives every arm from the frozen
D1-R1 prompt and records the exact transformation, source hash and output
hash.  The arms are designed to answer three separate questions:

* no_semantic_examples: replace the six input/output demonstrations with a
  non-semantic JSON shape template, so formatting support remains while the
  semantic demonstrations are removed;
* no_semantic_guidance: remove only the detailed semantic rules (9--19 and
  25--27), while keeping the output contract and all six examples;
* no_explicit_json_contract: remove only the explicit schema/JSON-discipline
  instructions, while keeping semantic rules and all six examples.

No model, network, API key or Gold data is read by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "prompts" / "sun_compat"
    / "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md"
)
OUT_DIR = ROOT / "prompts" / "sun_compat" / "ablation_v2"


STRUCTURAL_TEMPLATE = r'''Structural output template (no semantic examples):
The six input-output demonstrations are intentionally absent in this arm.
Use this type-and-key template only to preserve the required interface;
angle-bracketed values are placeholders and are not semantic evidence.

{
  "schema_version": "1.0.0",
  "sample_id": "<copy from input>",
  "source_id": "<copy from input>",
  "source_text": "<copy from input>",
  "clauses": [
    {
      "clause_id": "<unique string>",
      "clause_span": {"text": "<exact substring>", "start": 0, "end": 0},
      "modality": {
        "label": "<obligation|prohibition|permission|definition>",
        "evidence": [
          {"text": "<exact substring>", "start": 0, "end": 0}
        ]
      },
      "actors": [
        {"id": "<id>", "text": "<exact substring>", "start": 0,
         "end": 0, "normalized": "<surface-preserving normalization>"}
      ],
      "actions": [],
      "conditions": [],
      "constraints": [],
      "exceptions": [],
      "actor_action_map": [
        {"actor_id": "<actor id or null>", "action_id": "<action id>"}
      ],
      "order_relations": []
    }
  ],
  "method": {
    "name": "direct_llm",
    "schema_source": "stage2_prediction.schema.json@1.0.0"
  },
  "validation": {
    "schema_valid": true,
    "cross_field_valid": true,
    "errors": []
  },
  "unsupported_or_ambiguous": []
}
'''


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(
            f"expected exactly one {label} block, found {text.count(old)}")
    return text.replace(old, new, 1)


def _section(text: str, start_heading: str, end_heading: str) -> str:
    start = text.find(start_heading)
    end = text.find(end_heading, start + len(start_heading))
    if start < 0 or end < 0:
        raise RuntimeError(f"missing section boundary: {start_heading!r}")
    return text[start:end]


def _system_body(text: str) -> str:
    match = re.search(
        r"^## System Prompt\s*\n\n```text\n(.*?)\n```",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise RuntimeError("source prompt System Prompt block not found")
    return match.group(1)


def _replace_system_body(text: str, old_body: str, new_body: str) -> str:
    return _replace_once(text, old_body, new_body, "system prompt")


def _remove_numbered_rules(body: str, rule_numbers: set[int]) -> str:
    lines = body.splitlines()
    starts: list[tuple[int, int]] = []
    for idx, line in enumerate(lines):
        match = re.match(r"^(\d+)\.\s", line)
        if match:
            starts.append((idx, int(match.group(1))))
    if not starts:
        raise RuntimeError("no numbered rules found")
    remove_lines: set[int] = set()
    for pos, (start, number) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        if number in rule_numbers:
            remove_lines.update(range(start, end))
    found = {number for _, number in starts if number in rule_numbers}
    if found != rule_numbers:
        raise RuntimeError(
            f"missing numbered rules: {sorted(rule_numbers - found)}")
    kept = [line for idx, line in enumerate(lines) if idx not in remove_lines]
    # Avoid runs of more than two blank lines after deterministic deletion.
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def _no_semantic_examples(source: str) -> str:
    examples = _section(source, "## Examples", "## Notes")
    out = _replace_once(source, examples, "", "examples")
    original_body = _system_body(out)
    out = _replace_system_body(
        out, original_body, original_body + "\n\n" + STRUCTURAL_TEMPLATE.strip())
    old_user = (
        "Return the complete canonical JSON record. Use these four synthetic examples\n"
        "only for contract behavior, span arithmetic, and JSON shape. They are not\n"
        "formal test-set samples:\n\n"
        "{few_shot_block}"
    )
    new_user = (
        "Return the complete canonical JSON record. There are no semantic input-output\n"
        "examples in this arm; follow the non-semantic structural template supplied\n"
        "with the prompt."
    )
    return _replace_once(out, old_user, new_user, "few-shot user instruction")


def _no_semantic_guidance(source: str) -> str:
    body = _system_body(source)
    # 9--19: field semantics + missing/reference/passive rules.
    # 25--27: D1-R1 field-typing precision rules.
    removed = set(range(9, 20)) | {25, 26, 27}
    reduced = _remove_numbered_rules(body, removed)
    for heading in (
        "Six-element semantics:",
        "Missing, uncertain, passive, and reference rules:",
        "Field-typing precision (D1-R1):",
    ):
        reduced = reduced.replace(heading, "", 1)
    reduced = re.sub(r"\n{3,}", "\n\n", reduced)
    return _replace_system_body(source, body, reduced)


def _no_explicit_json_contract(source: str) -> str:
    body = _system_body(source)
    intro = (
        "\nYou MUST follow stage2_extraction_contract@1.0.0 with contract SHA-256\n"
        "7f17ecba78cfa1acf1bbc488942f1c85c37d08ece7662c622bab4226bd2dbd46.\n"
        "The output MUST conform to stage2_prediction.schema.json@1.0.0.\n\n"
        "Output discipline:\n"
    )
    if intro not in body:
        raise RuntimeError("explicit contract introduction not found")
    body = body.replace(intro, "\n", 1)
    body = _remove_numbered_rules(body, {1, 2, 3, 4, 5})
    old_check = (
        "24. All required keys are present, no extra keys exist, all labels are from the\n"
        "    fixed enums, all spans are exact, all references resolve, and no forbidden\n"
        "    inference was used."
    )
    new_check = (
        "24. All spans are exact, all references resolve, and no forbidden inference\n"
        "    was used."
    )
    body = _replace_once(body, old_check, new_check, "semantic-only final check")
    out = _replace_system_body(source, _system_body(source), body)
    old_user = "Return the complete canonical JSON record. Use these four synthetic examples"
    new_user = "Return the extraction result. Use these four synthetic examples"
    return _replace_once(out, old_user, new_user, "explicit JSON user instruction")


def build(*, overwrite: bool = False) -> dict:
    source_bytes = SOURCE.read_bytes()
    source = source_bytes.decode("utf-8")
    if source.count("\nExample ") != 6:
        raise RuntimeError("frozen source prompt must contain exactly six examples")

    artifacts = {
        "D-no-semantic-examples-0813": {
            "filename": "direct_llm_no_semantic_examples_prompt_v2.md",
            "text": _no_semantic_examples(source),
            "factor": "semantic input-output demonstrations",
            "operation": (
                "replace all six semantic input-output examples with one "
                "non-semantic key/type template; keep the full semantic rules "
                "and explicit JSON discipline"
            ),
        },
        "D-no-semantic-guidance-0813": {
            "filename": "direct_llm_no_semantic_guidance_prompt_v2.md",
            "text": _no_semantic_guidance(source),
            "factor": "detailed six-field semantic guidance",
            "operation": (
                "remove the detailed semantic-guidance headings and numbered "
                "rules 9-19 and 25-27 only; keep rules 1-8 and 20-24, the "
                "user envelope and all six examples"
            ),
        },
        "D-no-explicit-json-contract-0813": {
            "filename": "direct_llm_no_explicit_json_contract_prompt_v2.md",
            "text": _no_explicit_json_contract(source),
            "factor": "explicit JSON/schema output discipline",
            "operation": (
                "remove the explicit contract introduction and numbered rules "
                "1-5, remove schema-only wording from rule 24 and the user "
                "instruction; keep all semantic rules and all six examples"
            ),
        },
    }

    if OUT_DIR.exists() and not overwrite:
        raise RuntimeError(f"refusing to overwrite: {OUT_DIR}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: dict[str, dict] = {}
    for arm, spec in artifacts.items():
        path = OUT_DIR / spec["filename"]
        path.write_text(spec["text"], encoding="utf-8", newline="\n")
        rows[arm] = {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256_bytes(path.read_bytes()),
            "factor": spec["factor"],
            "operation": spec["operation"],
            "semantic_example_count": spec["text"].count("\nExample "),
            "source_prompt_sha256": _sha256_bytes(source_bytes),
        }

    manifest = {
        "schema_version": "d1_prompt_factorial_arms@2.0.0",
        "status": "prepared_offline_not_executed",
        "llm_api_calls": 0,
        "network_calls": 0,
        "baseline": {
            "arm": "D-full-0813",
            "path": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256_bytes(source_bytes),
            "semantic_example_count": 6,
        },
        "comparison_rule": (
            "each arm is compared only with D-full-0813 under the same "
            "DeepSeek-V4-Pro-0813 release, EStG-150 input, Gold and evaluator"
        ),
        "arms": rows,
        "interpretation_limits": {
            "no_semantic_examples": (
                "a controlled substitution, not a pure deletion: the semantic "
                "demonstrations are replaced by a structure-only template to "
                "prevent output-interface collapse"
            ),
            "other_arms": "single textual factor removals from the frozen prompt",
        },
    }
    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    manifest = build(overwrite=args.overwrite)
    print(
        "Prepared 3 prompt-factor arms (zero API): "
        f"{OUT_DIR.relative_to(ROOT)}; baseline={manifest['baseline']['arm']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
