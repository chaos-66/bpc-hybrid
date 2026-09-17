# -*- coding: utf-8 -*-
"""Zero-API prompt overlap/conflict audit for SEP-C3 modular prompt v1.

The audit reads the frozen prompt component files and the paired-error
attribution report. It never modifies prompts, Gold, predictions, or
evaluator code. Findings separate mechanical overlap from researcher
hypotheses; literal contradiction is only reported if the wording itself
contradicts another instruction.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROMPT_DIR = ROOT / "prompts" / "sun_compat" / "modular_v1"
OUT_JSON = ROOT / "outputs" / "reports" / "sep_c3_modular_prompt_overlap_audit_v1.json"
OUT_MD = ROOT / "outputs" / "reports" / "sep_c3_modular_prompt_overlap_audit_v1.md"
PAIRED_REPORT = ROOT / "outputs" / "reports" / "sep_c3_modular_paired_error_attribution_v1.json"

PROMPT_FILES = {
    "common_system": PROMPT_DIR / "common_system.md",
    "user_envelope": PROMPT_DIR / "user_envelope.md",
    "examples_E": PROMPT_DIR / "examples_E.md",
    "semantic_rules_S": PROMPT_DIR / "semantic_rules_S.md",
    "output_format_J": PROMPT_DIR / "output_format_J.md",
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_numbered_rules(text: str) -> list[tuple[int, str]]:
    matches = list(re.finditer(r"(?ms)^(\d+)\.\s+(.*?)(?=^\d+\.\s|\Z)", text))
    out = []
    for match in matches:
        number = int(match.group(1))
        body = " ".join(match.group(2).split())
        out.append((number, body))
    return out


def parse_example_blocks(text: str) -> list[tuple[int, str]]:
    matches = list(re.finditer(r"(?ms)^Example E(\d+).*?(?=^Example E\d+|\Z)", text))
    out = []
    for match in matches:
        number = int(match.group(1))
        body = match.group(0).strip()
        out.append((number, body))
    return out


def parse_bullets(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            out.append(stripped[2:].strip())
    return out


def build_common_inventory(common_text: str, user_text: str) -> list[dict[str, Any]]:
    # Atomic interface/task instructions, keyed to exact phrases retained in
    # common_system.md.  The list is deliberately conservative: it does not
    # claim to atomize every grammatical clause in the prose.
    items = [
        ("C01", "You are a regulatory text formalization expert. Extract one Stage 2 canonical prediction object from the target text.",
         "task definition and output target", ["all"]),
        ("C02", "Required fields (stage2_prediction.schema.json@1.0.0): Top level: schema_version, sample_id, source_id, source_text, clauses, method, validation, unsupported_or_ambiguous.",
         "top-level structural interface", ["all"]),
        ("C03", "Clause: clause_id, clause_span, modality, actors, actions, conditions, constraints, exceptions, actor_action_map, order_relations.",
         "clause structural interface", ["all"]),
        ("C04", "Span: text, start, end. Identified spans under actors, actions, conditions, constraints, and exceptions also carry id and normalized; modality evidence spans do not.",
         "span structural interface", ["actor", "action", "condition", "constraint", "exception", "modality"]),
        ("C05", "modality: label, evidence.", "modality structural interface", ["modality"]),
        ("C06", "actor_action_map edge: actor_id, action_id.", "relation structural interface", ["actor", "action"]),
        ("C07", "order_relations entry: before_action_id, after_action_id, evidence.", "relation structural interface", ["action"]),
        ("C08", "method: name, schema_source.", "method metadata interface", ["all"]),
        ("C09", "validation: schema_valid, cross_field_valid, errors.", "validation metadata interface", ["all"]),
        ("C10", "unsupported_or_ambiguous entry: field, reason.", "uncertainty metadata interface", ["all"]),
        ("C11", "Set schema_version to \"1.0.0\". Copy sample_id, source_id, and source_text exactly from the input.",
         "identity/schema binding", ["all"]),
        ("C12", "Use method = {\"name\": \"direct_llm\", \"schema_source\": \"stage2_prediction.schema.json@1.0.0\"} and validation = {\"schema_valid\": true, \"cross_field_valid\": true, \"errors\": []}; the runtime validator overwrites validation and is authoritative.",
         "fixed metadata binding", ["all"]),
        ("C13", "Always include unsupported_or_ambiguous, using [] when empty.", "completeness discipline", ["all"]),
        ("C14", "Use zero-based start and exclusive end for every span. For every span, text must equal source_text[start:end]; every child span must lie inside its clause_span.",
         "coordinate/boundary discipline", ["all"]),
        ("C15", "IDs are unique within the complete record. actor_action_map and order_relations entries may reference IDs only from the same clause.",
         "ID/reference discipline", ["all"]),
        ("C16", "Input mode: target_text_only; sample_id, source_id, source_text substitution envelope.",
         "input envelope", ["all"]),
    ]
    out = []
    for instruction_id, wording, summary, targets in items:
        # The wording field is a faithful compressed quote. Line wrapping and
        # bullet prefixes in the markdown source are normalized here; the
        # frozen source file hash remains the authoritative exact text.
        out.append({
            "instruction_id": instruction_id,
            "source_module": "common",
            "source_file": "common_system.md" if instruction_id != "C16" else "user_envelope.md",
            "source_sha256": sha256_text(common_text if instruction_id != "C16" else user_text),
            "original_wording": wording,
            "semantic_summary": summary,
            "target_fields": targets,
            "function": "baseline_structural_interface",
            "duplicate_with": [],
            "possibly_conflicts_with": [],
            "example_evidence": [],
            "related_failure_samples": [],
        })
    return out


def build_e_inventory(examples_text: str) -> list[dict[str, Any]]:
    summaries = {
        1: ("unresolved subject pronoun still kept as actor with unsupported_or_ambiguous", ["actor", "action", "condition", "modality"]),
        2: ("passive clause with coordinated actions and two constraints; actor_action_map actor_id null", ["action", "constraint", "modality"]),
        3: ("prohibition with an exception marker", ["actor", "action", "exception", "modality"]),
        4: ("definition clause followed by an obligation clause; clause split and empty fields", ["modality", "actor", "action"]),
        5: ("condition containing a nested constraint reported in both arrays", ["condition", "constraint", "modality"]),
    }
    out = []
    for number, body in parse_example_blocks(examples_text):
        summary, targets = summaries[number]
        out.append({
            "instruction_id": f"E{number:02d}",
            "source_module": "E",
            "source_file": "examples_E.md",
            "source_sha256": sha256_text(examples_text),
            "original_wording": body,
            "semantic_summary": summary,
            "target_fields": targets,
            "function": "worked_example_demonstration",
            "duplicate_with": [],
            "possibly_conflicts_with": [],
            "example_evidence": [f"Example E{number}"],
            "related_failure_samples": [],
        })
    return out


def build_s_inventory(semantic_text: str) -> list[dict[str, Any]]:
    summary = {
        1: ("source-only evidence boundary", ["all"], "evidence_grounding"),
        2: ("modality classes and smallest sufficient trigger", ["modality"], "semantic_interpretation / modality_extraction"),
        3: ("smallest explicit actor NP or pronominal mention; unresolved pronoun preserved", ["actor"], "actor_extraction / span_boundary"),
        4: ("smallest verb-centred action including necessary object/complement/particle", ["action"], "action_extraction / span_boundary"),
        5: ("condition as antecedent state/event including marker and governed proposition", ["condition"], "condition_extraction"),
        6: ("constraint as limitation or legal reference/time/quantity/purpose/exclusivity, including marker and smallest complete limit", ["constraint"], "constraint_extraction / span_boundary"),
        7: ("exception as removed/narrowing case including marker and governed proposition", ["exception"], "exception_extraction"),
        8: ("separate condition/constraint/exception arrays; action ends where phrase begins; nested constraint in condition appears in both", ["action", "condition", "constraint", "exception"], "field_partition / span_boundary"),
        9: ("empty means absent; uncertain mention preserved with controlled reason", ["all"], "uncertainty / evidence_grounding"),
        10: ("reference and voice rules for unresolved pronouns and passive clauses", ["actor", "action"], "actor_extraction / action_extraction"),
        11: ("definition/empty-record handling", ["modality", "actor", "action"], "task_definition / structured_output"),
        12: ("clause boundary rules for independent normative force/shared modality", ["all"], "clause_segmentation"),
        13: ("coordinated actors/actions stored separately; map edges only when licensed", ["actor", "action"], "coordination / relation"),
        14: ("order_relations only with exact evidence; ordinary and is not sequential", ["action"], "order_relation"),
        15: ("normalization may case-fold/whitespace/lemmatize/remove article; must not replace pronoun with absent antecedent", ["all"], "normalization / evidence_grounding"),
    }
    out = []
    for number, body in parse_numbered_rules(semantic_text):
        desc, targets, function = summary[number]
        out.append({
            "instruction_id": f"S{number:02d}",
            "source_module": "S",
            "source_file": "semantic_rules_S.md",
            "source_sha256": sha256_text(semantic_text),
            "original_wording": body,
            "semantic_summary": desc,
            "target_fields": targets,
            "function": function,
            "duplicate_with": [],
            "possibly_conflicts_with": [],
            "example_evidence": [],
            "related_failure_samples": [],
        })
    return out


def build_j_inventory(output_text: str) -> list[dict[str, Any]]:
    bullets = parse_bullets(output_text)
    out = []
    for index, body in enumerate(bullets, start=1):
        out.append({
            "instruction_id": f"J{index:02d}",
            "source_module": "J",
            "source_file": "output_format_J.md",
            "source_sha256": sha256_text(output_text),
            "original_wording": body,
            "semantic_summary": body,
            "target_fields": ["all"],
            "function": "serialization_discipline",
            "duplicate_with": [],
            "possibly_conflicts_with": [],
            "example_evidence": [],
            "related_failure_samples": [],
        })
    return out


def main() -> None:
    texts = {
        name: path.read_text(encoding="utf-8")
        for name, path in PROMPT_FILES.items()
    }
    paired = json.loads(PAIRED_REPORT.read_text(encoding="utf-8"))

    inventory = []
    inventory.extend(build_common_inventory(texts["common_system"], texts["user_envelope"]))
    inventory.extend(build_e_inventory(texts["examples_E"]))
    inventory.extend(build_s_inventory(texts["semantic_rules_S"]))
    inventory.extend(build_j_inventory(texts["output_format_J"]))
    inventory_by_id = {item["instruction_id"]: item for item in inventory}

    # Functional overlap map derived from line-by-line semantic comparison.
    e_s_overlap = [
        {
            "instructions": ["E01", "S03", "S10"],
            "classification": "functional_overlap",
            "shared_function": "actor surface preservation, including unresolved subject pronouns",
            "mechanical_evidence": "E01 demonstrates the same boundary behavior that S03/S10 state abstractly.",
            "literal_contradiction": False,
        },
        {
            "instructions": ["E02", "S04", "S06", "S10"],
            "classification": "functional_overlap",
            "shared_function": "passive action mapping plus constraint extraction",
            "mechanical_evidence": "E02 gives a boundary example for actions/constraints that S04/S06 define abstractly; S10 states the passive mapping rule.",
            "literal_contradiction": False,
        },
        {
            "instructions": ["E03", "S02", "S07"],
            "classification": "functional_overlap",
            "shared_function": "prohibition modality and exception extraction",
            "mechanical_evidence": "E03 demonstrates the exception pattern that S07 defines and the modality class that S02 defines.",
            "literal_contradiction": False,
        },
        {
            "instructions": ["E04", "S11", "S12"],
            "classification": "functional_overlap",
            "shared_function": "definition/obligation clause splitting",
            "mechanical_evidence": "E04 demonstrates the clause split and empty-record pattern governed by S11/S12.",
            "literal_contradiction": False,
        },
        {
            "instructions": ["E05", "S05", "S06", "S08"],
            "classification": "functional_overlap",
            "shared_function": "condition/constraint nesting and field partition",
            "mechanical_evidence": "E05 demonstrates the nested constraint behavior explicitly governed by S08; S05/S06 define the fields.",
            "literal_contradiction": False,
        },
    ]

    literal_contradiction_search = {
        "method": "line-by-line semantic comparison of the frozen common/E/S/J component files by instruction inventory",
        "result": "no_literal_contradiction_found",
        "boundary": "The absence of literal contradiction does not rule out overlapping guidance or conditional interference at generation time.",
    }

    j_common = {
        "baseline_structural_interface": [
            item["instruction_id"] for item in inventory_by_id.values()
            if item["source_module"] == "common"
        ],
        "additional_j_discipline": ["J01", "J02"],
        "literal_duplicates": [],
        "rewording_only": [
            {
                "J02": "still return the complete object rather than a prose refusal or apology",
                "common_overlap": ["C01", "C13"],
                "reason": "Common already defines a complete object and requires unsupported_or_ambiguous; J02 restates the completeness/no-refusal behavior rather than adding a new semantic field or schema constraint.",
            }
        ],
        "genuinely_new_constraints": [
            {
                "J01": "Return one bare JSON object. Do not wrap it in Markdown fences or add a prefix, explanation, comments, or trailing text.",
                "why_new": "The common interface specifies required fields but not the absence of Markdown fences or surrounding prose.",
            }
        ],
        "why_000_can_still_parse_150_of_150": (
            "The persisted canonical parser/adaptor accepts and canonicalizes fenced raw responses. "
            "000 raw responses included 36/150 Markdown-fenced objects, yet all 150 became canonical "
            "schema/cross-field-valid records."
        ),
    }

    sample_links = [
        {
            "finding_id": "actor_overextraction_after_S_addition",
            "prompt_instructions": ["S03", "S10", "S13"],
            "failure_samples": [
                {
                    "sample_id": "estg_000080",
                    "pair": "101_to_111",
                    "mechanical_observation": "101 predicted exactly the Gold actor; 111 additionally predicted 'Contributions', 'the assets', and a long amount phrase as actors.",
                },
                {
                    "sample_id": "estg_000083",
                    "pair": "101_to_111",
                    "mechanical_observation": "101 predicted no actors; 111 predicted 'the additional amounts' and 'the reduced amounts' although Gold has no actor.",
                },
            ],
            "evidence_type": "mechanically_observed_span_difference",
            "hypothesis": (
                "The broad actor-surface instructions in S may be over-applied to noun phrases in "
                "coordinated or passive contexts, while the passive-voice exception in S10 is not "
                "always followed. This is a plausible interference hypothesis, not a causal proof."
            ),
            "unresolved": (
                "No same-prompt repeat or token-level activation evidence is available to separate "
                "S wording effects from ordinary run-to-run generation variation."
            ),
        },
        {
            "finding_id": "constraint_marker_overextraction_after_S_addition",
            "prompt_instructions": ["S06", "S08"],
            "failure_samples": [
                {
                    "sample_id": "estg_000020",
                    "pair": "100_to_110",
                    "mechanical_observation": "100 predicted exactly the Gold constraint span; 110 additionally emitted 'only' as a separate constraint, creating one unmatched prediction.",
                },
                {
                    "sample_id": "estg_000106",
                    "pair": "101_to_111",
                    "mechanical_observation": "101 emitted one partial constraint; 111 emitted the full Gold-overlapping constraint plus an extra 'only' span.",
                },
            ],
            "evidence_type": "mechanically_observed_span_difference",
            "hypothesis": (
                "S06's marker-inclusion and smallest-complete-limit guidance can produce separate "
                "marker spans that the evaluator treats as unmatched. The wording does not explicitly "
                "require splitting a marker from its governed limit."
            ),
            "unresolved": (
                "The pair 100_to_110 is cross-batch confounded; the 101_to_111 pair is same-batch but "
                "single-run. Neither establishes causal wording attribution."
            ),
        },
        {
            "finding_id": "E_constraint_recovery",
            "prompt_instructions": ["E02", "E05"],
            "failure_samples": [
                {
                    "sample_id": "estg_000020",
                    "pair": "000_to_100",
                    "mechanical_observation": "000 missed the Gold constraint; 100 recovered the exact Gold span.",
                },
                {
                    "sample_id": "estg_000021",
                    "pair": "000_to_100",
                    "mechanical_observation": "000 missed the Gold constraint; 100 recovered a matching constraint span with the marker 'only'.",
                },
            ],
            "evidence_type": "mechanically_observed_span_difference",
            "hypothesis": (
                "E examples may supply concrete condition/constraint span patterns that reduce missed "
                "constraint spans in the common skeleton. This is consistent with E-only improvement "
                "but is not isolated from other prompt differences in this single run."
            ),
            "unresolved": "No controlled E-only wording variant or repeat is available yet.",
        },
        {
            "finding_id": "J_serialization_effect",
            "prompt_instructions": ["J01", "J02"],
            "failure_samples": [],
            "evidence_type": "raw_response_and_canonical_pipeline_counts",
            "mechanical_observation": (
                "Without J: 000 had 114/150 bare raw JSON objects (36 fenced); 100 had 146/150; "
                "010 had 149/150. With J: 001/011/101/111 each had 150/150 bare raw objects. "
                "All arms nevertheless produced 150/150 canonical schema-valid and cross-field-valid predictions."
            ),
            "hypothesis": (
                "J mainly adds a serialization/discipline constraint. It changes raw response form, "
                "but the current canonical parser already recovers fenced objects, so no F1 or "
                "canonical-failure benefit is observable."
            ),
            "unresolved": (
                "The canonical semantic predictions also differ across arms, but each arm is a "
                "single generation; those differences cannot be attributed to J alone."
            ),
        },
    ]

    audit = {
        "schema_version": "sep_c3_modular_prompt_overlap_audit@1.0.0",
        "status": "complete_zero_api",
        "network_calls": 0,
        "llm_calls": 0,
        "prompt_files": {
            name: {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256_file(path),
                "chars": len(texts[name]),
            }
            for name, path in PROMPT_FILES.items()
        },
        "instruction_inventory": inventory,
        "overlap_audit": {
            "e_s_functional_overlap": e_s_overlap,
            "literal_contradiction_search": literal_contradiction_search,
            "j_common_relationship": j_common,
        },
        "sample_linked_evidence": sample_links,
        "conclusion": {
            "e_s": (
                "The E examples and S rules overlap functionally; no literal contradiction was found. "
                "The paired failures motivate a narrower test of whether actor-surface and constraint-marker "
                "guidance causes conditional over-extraction."
            ),
            "j_common": (
                "J is not a pure duplicate of the common interface because bare-object/no-wrapper discipline "
                "is genuinely additional. Empirically, however, the shared canonicalizer already yields "
                "150/150 schema-valid records without J, so J's additional discipline has no measurable "
                "primary-metric or canonical-failure benefit in this dataset/model setting."
            ),
            "causal_status": (
                "Functional overlap and sample-level temporal associations are established. Causal wording-level "
                "attribution is unresolved and must not be written as proven."
            ),
        },
    }

    OUT_JSON.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    lines = [
        "# SEP-C3 modular prompt overlap / conflict audit v1 (zero API)",
        "",
        "- status: complete_zero_api",
        "- audit scope: frozen `common_system.md`, `user_envelope.md`, `examples_E.md`, `semantic_rules_S.md`, `output_format_J.md`",
        "- no prompt, Gold, prediction, evaluator, or formal report was modified.",
        "",
        "## Prompt hashes",
        "",
        "| component | SHA-256 | chars |",
        "|---|---:|---:|",
    ]
    for name, info in audit["prompt_files"].items():
        lines.append(f"| {name} | `{info['sha256']}` | {info['chars']} |")
    lines += [
        "",
        "## Instruction inventory",
        "",
        f"- atomic/auditable instructions recorded: {len(inventory)}",
        f"  - common: {sum(1 for x in inventory if x['source_module'] == 'common')}",
        f"  - E: {sum(1 for x in inventory if x['source_module'] == 'E')}",
        f"  - S: {sum(1 for x in inventory if x['source_module'] == 'S')}",
        f"  - J: {sum(1 for x in inventory if x['source_module'] == 'J')}",
        "",
        "## E/S functional overlap",
        "",
    ]
    for row in e_s_overlap:
        lines.append(
            f"- `{', '.join(row['instructions'])}`: {row['classification']} — "
            f"{row['shared_function']} ({row['mechanical_evidence']})"
        )
    lines += [
        "",
        "## E/S literal contradiction search",
        "",
        f"- result: `{literal_contradiction_search['result']}`",
        f"- method: {literal_contradiction_search['method']}",
        f"- boundary: {literal_contradiction_search['boundary']}",
        "",
        "## J vs common skeleton",
        "",
        "- baseline structural interface: " + ", ".join(j_common["baseline_structural_interface"]),
        "- additional J discipline: " + ", ".join(j_common["additional_j_discipline"]),
        f"- literal duplicates: {len(j_common['literal_duplicates'])}",
        f"- genuinely new constraint: {j_common['genuinely_new_constraints'][0]['J01']}",
        f"- why 000 parses 150/150: {j_common['why_000_can_still_parse_150_of_150']}",
        "",
        "## Sample-linked evidence",
        "",
    ]
    for link in sample_links:
        lines.append(f"### {link['finding_id']}")
        lines.append(f"- prompt instructions: {', '.join(link['prompt_instructions'])}")
        lines.append(f"- evidence type: `{link['evidence_type']}`")
        for sample in link["failure_samples"]:
            lines.append(f"- `{sample['sample_id']}` ({sample['pair']}): {sample['mechanical_observation']}")
        lines.append(f"- hypothesis: {link['hypothesis']}")
        lines.append(f"- unresolved: {link['unresolved']}")
        lines.append("")
    lines += [
        "## Conclusion",
        "",
        f"- E/S: {audit['conclusion']['e_s']}",
        f"- J/common: {audit['conclusion']['j_common']}",
        f"- causal status: {audit['conclusion']['causal_status']}",
        "",
    ]
    OUT_MD.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"wrote {OUT_MD.relative_to(ROOT)}")
    print(f"instructions={len(inventory)} literal_contradiction={literal_contradiction_search['result']}")


if __name__ == "__main__":
    main()
