# -*- coding: utf-8 -*-
"""Freeze the four D1 Actor-refinement prompt variants.

The baseline is a byte-for-byte copy of the current frozen full prompt.
Each non-baseline arm changes exactly one pre-specified conceptual factor:
Role eligibility (R), unresolved-pronoun policy (P), or condition actor
projection (C).  This builder is offline and Gold-blind.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_PROMPT = (
    ROOT / "prompts" / "sun_compat"
    / "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md"
)
OUT_DIR = ROOT / "prompts" / "sun_compat" / "actor_refinement_v1"
PROMPT_MANIFEST = OUT_DIR / "manifest.json"
DIFF_MANIFEST = OUT_DIR / "prompt_diff_manifest.json"
EXPERIMENT_MANIFEST = (
    ROOT / "outputs" / "development" / "d1_actor_refinement_v1"
    / "experiment_manifest.json"
)
EXPECTED_BASE_SHA = (
    "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"
)

ARMS: tuple[dict[str, str], ...] = (
    {
        "arm": "B0",
        "filename": "direct_llm_actor_baseline_v1",
        "conceptual_factor": "fresh_unchanged_baseline",
        "description": "Byte-for-byte copy of the frozen full prompt.",
    },
    {
        "arm": "R",
        "filename": "direct_llm_actor_role_eligibility_v1",
        "conceptual_factor": "actor_role_eligibility_only",
        "description": (
            "Tighten actor noun-phrase eligibility while preserving the "
            "pronoun policy and condition projection exactly."
        ),
    },
    {
        "arm": "P",
        "filename": "direct_llm_actor_pronoun_policy_v1",
        "conceptual_factor": "unresolved_pronoun_policy_only",
        "description": (
            "Abstain on unresolved actor pronouns; synchronize Rule 16/17 "
            "and Synthetic Example 1 only."
        ),
    },
    {
        "arm": "C",
        "filename": "direct_llm_actor_condition_projection_v1",
        "conceptual_factor": "condition_actor_projection_only",
        "description": (
            "Project an explicit actor-eligible participant out of a "
            "condition into actors; no eligibility or pronoun change."
        ),
    },
)

RULE_10_OLD = (
    "10. actor is the smallest explicit noun phrase or pronominal mention that bears\n"
    "    or performs the norm. A subject pronoun it/they/this/these/such is a real\n"
    "    actor mention. Extract the pronoun exact span even when its reference is\n"
    "    unresolved. If this/these/such modifies a noun, extract the complete minimal\n"
    "    noun phrase instead of the determiner alone."
)

RULE_10_R = (
    "10. actor is the smallest explicit noun phrase or pronominal mention that\n"
    "    denotes a participant that explicitly performs or bears an action or state\n"
    "    relevant to the rule.\n"
    "    Grammatical subjecthood alone is not sufficient for actor status.\n"
    "    Do not extract an expression as an actor when it functions only as the\n"
    "    regulated object, legal provision, amount, asset, proposition, event/state,\n"
    "    or another non-participant in the described action or normative relation.\n"
    "    A subject pronoun it/they/this/these/such is a real actor mention. Extract\n"
    "    the pronoun exact span even when its reference is unresolved. If\n"
    "    this/these/such modifies a noun, extract the complete minimal noun phrase\n"
    "    instead of the determiner alone."
)

RULE_10_P = (
    "10. actor is the smallest explicit noun phrase or pronominal mention that bears\n"
    "    or performs the norm. A subject pronoun such as it/they/this/these/such may\n"
    "    be emitted as an actor only when its antecedent is explicitly recoverable\n"
    "    within source_text and that antecedent denotes an actor-eligible participant.\n"
    "    If the antecedent is not explicitly recoverable within source_text, do not\n"
    "    emit the unresolved pronoun in actors. Do not replace the pronoun with an\n"
    "    antecedent inferred from outside source_text. If this/these/such modifies a\n"
    "    noun, extract the complete minimal noun phrase instead of the determiner\n"
    "    alone."
)

RULE_16_OLD = (
    "16. If a defensible surface mention exists but its reference or scope is\n"
    "    uncertain, preserve the exact span and add an unsupported_or_ambiguous\n"
    "    entry. Use only these reason strings:"
)
RULE_16_P = (
    "16. If a defensible surface mention exists but its reference or scope is\n"
    "    uncertain, preserve the exact span and add an unsupported_or_ambiguous\n"
    "    entry. Preserve uncertain surface mentions as usual, except for unresolved\n"
    "    actor pronouns governed by Rule 17. Use only these reason strings:"
)

RULE_17_OLD = (
    "17. For an unresolved subject pronoun, keep normalized surface-preserving\n"
    "    (for example \"it\"), and add:\n"
    "    {\"field\":\"actor\",\"reason\":\"reference_status=unresolved_coreference;independence_status=context_required\"}."
)
RULE_17_P = (
    "17. For an unresolved subject pronoun whose antecedent is not explicitly\n"
    "    recoverable within source_text, do not emit that pronoun in actors.\n"
    "    Add:\n"
    "    {\"field\":\"actor\",\n"
    "     \"reason\":\"reference_status=unresolved_coreference;independence_status=context_required\"}."
)

EXAMPLE1_TITLE_OLD = (
    "Example 1 \u2014 unresolved subject pronoun remains an exact actor mention:"
)
EXAMPLE1_TITLE_P = (
    "Example 1 \u2014 unresolved subject pronoun is not promoted to actor:"
)
EXAMPLE1_ACTORS_OLD = (
    '      "actors": [{"id": "a01", "text": "It", "start": 0, "end": 2, "normalized": "it"}],'
)
EXAMPLE1_ACTORS_P = '      "actors": [],'
EXAMPLE1_MAP_OLD = (
    '      "actor_action_map": [{"actor_id": "a01", "action_id": "p01"}],'
)
EXAMPLE1_MAP_P = (
    '      "actor_action_map": [{"actor_id": null, "action_id": "p01"}],'
)

RULE_27_OLD = (
    "27. condition covers if/when/where/unless/provided that/in the event of/to the\n"
    "    extent that/insofar as clauses. Condition and constraint are separate\n"
    "    fields: a constraint inside a condition (for example \"within two years\"\n"
    "    inside \"if ... within two years\") is reported in BOTH arrays. Never merge\n"
    "    condition or constraint content into the action span."
)
RULE_28_C = (
    "\n\n28. Actor and condition spans may overlap. When a condition contains an\n"
    "    explicit actor-eligible mention that itself performs or bears an action or\n"
    "    state stated inside that condition, emit the smallest exact actor mention\n"
    "    independently in actors as well as preserving the complete condition span.\n"
    "    Do not infer an unstated actor. Do not promote every noun phrase inside a\n"
    "    condition; the mention must itself be the explicit participant in the\n"
    "    condition's action or state."
)


class PromptConstructionError(RuntimeError):
    """A frozen prompt cannot be constructed under the approved semantics."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise PromptConstructionError(
            f"expected exactly one {label} block, found {count}"
        )
    return text.replace(old, new, 1)


def _build_variant_text(arm: str, base_text: str) -> str:
    if arm == "B0":
        return base_text
    if arm == "R":
        return _replace_once(base_text, RULE_10_OLD, RULE_10_R, "Rule 10")
    if arm == "P":
        text = _replace_once(base_text, RULE_10_OLD, RULE_10_P, "Rule 10")
        text = _replace_once(text, RULE_16_OLD, RULE_16_P, "Rule 16")
        text = _replace_once(text, RULE_17_OLD, RULE_17_P, "Rule 17")
        start = text.index(EXAMPLE1_TITLE_OLD)
        end = text.index("Example 2 ", start)
        section = text[start:end]
        section = _replace_once(
            section, EXAMPLE1_TITLE_OLD, EXAMPLE1_TITLE_P, "Example 1 title")
        section = _replace_once(
            section, EXAMPLE1_ACTORS_OLD, EXAMPLE1_ACTORS_P, "Example 1 actors")
        section = _replace_once(
            section, EXAMPLE1_MAP_OLD, EXAMPLE1_MAP_P, "Example 1 actor_action_map")
        return text[:start] + section + text[end:]
    if arm == "C":
        return _replace_once(base_text, RULE_27_OLD, RULE_27_OLD + RULE_28_C, "Rule 27")
    raise PromptConstructionError(f"unknown arm: {arm}")


def _region_indexes(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Return half-open line regions for the known changing sections."""
    def find(prefix: str, start: int = 0) -> int:
        for index in range(start, len(lines)):
            if lines[index].startswith(prefix):
                return index
        raise PromptConstructionError(f"line anchor not found: {prefix!r}")

    regions: dict[str, tuple[int, int]] = {}
    regions["rule10"] = find("10. actor"), find("11. action")
    regions["rule1617"] = find("16. If a defensible"), find("18. In a passive")
    regions["example1"] = find("Example 1 "), find("Example 2 ")
    rule27 = find("27. condition covers")
    close = rule27
    while close < len(lines) and lines[close].strip() != "```":
        close += 1
    if close >= len(lines):
        raise PromptConstructionError("system-prompt closing fence not found")
    regions["rule2728"] = rule27, close
    return regions


def _region_for_line(
    index: int, regions: dict[str, tuple[int, int]]
) -> str | None:
    for name, (start, end) in regions.items():
        if start <= index < end:
            return name
    return None


def _line_diff(base_text: str, variant_text: str) -> list[dict[str, Any]]:
    base_lines = base_text.splitlines()
    variant_lines = variant_text.splitlines()
    base_regions = _region_indexes(base_lines)
    variant_regions = _region_indexes(variant_lines)
    matcher = difflib.SequenceMatcher(
        a=base_lines, b=variant_lines, autojunk=False
    )
    hunks: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        base_affected = list(range(i1, i2))
        variant_affected = list(range(j1, j2))
        base_region_names = sorted({
            name for idx in base_affected
            for name in [_region_for_line(idx, base_regions)]
            if name is not None
        })
        variant_region_names = sorted({
            name for idx in variant_affected
            for name in [_region_for_line(idx, variant_regions)]
            if name is not None
        })
        hunks.append({
            "opcode": tag,
            "baseline_line_range": (
                [i1 + 1, i2] if i2 > i1 else []
            ),
            "variant_line_range": (
                [j1 + 1, j2] if j2 > j1 else []
            ),
            "baseline_regions": base_region_names,
            "variant_regions": variant_region_names,
            "baseline_changed_lines": base_lines[i1:i2],
            "variant_changed_lines": variant_lines[j1:j2],
        })
    return hunks


def _allowed_regions(arm: str) -> set[str]:
    return {
        "B0": set(),
        "R": {"rule10"},
        "P": {"rule10", "rule1617", "example1"},
        "C": {"rule2728"},
    }[arm]


def _classify_hunks(arm: str, hunks: list[dict[str, Any]]) -> None:
    allowed = _allowed_regions(arm)
    unexpected = 0
    for hunk in hunks:
        base_ok = all(
            region in allowed
            for region in hunk["baseline_regions"]
        )
        var_ok = all(
            region in allowed
            for region in hunk["variant_regions"]
        )
        if not base_ok or not var_ok:
            possible_regions = set(hunk["baseline_regions"]) | set(hunk["variant_regions"])
            if not possible_regions.issubset(allowed):
                unexpected += 1
        hunk["allowed_by_arm"] = bool(base_ok and var_ok)
    if unexpected:
        raise PromptConstructionError(
            f"arm {arm} contains {unexpected} unexpected diff hunks"
        )


def build() -> dict[str, Any]:
    base_bytes = BASE_PROMPT.read_bytes()
    base_sha = _sha256_bytes(base_bytes)
    if base_sha != EXPECTED_BASE_SHA:
        raise PromptConstructionError(
            f"base prompt SHA drift: {base_sha} != {EXPECTED_BASE_SHA}"
        )
    base_text = base_bytes.decode("utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EXPERIMENT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    arm_entries: list[dict[str, Any]] = []
    diff_entries: list[dict[str, Any]] = []
    for spec in ARMS:
        arm = spec["arm"]
        variant_text = _build_variant_text(arm, base_text)
        variant_bytes = variant_text.encode("utf-8")
        out_path = OUT_DIR / f"{spec['filename']}.md"
        out_path.write_bytes(variant_bytes)
        variant_sha = _sha256_bytes(variant_bytes)
        hunks = _line_diff(base_text, variant_text)
        _classify_hunks(arm, hunks)
        changed_ranges = [
            {
                "baseline": hunk["baseline_line_range"],
                "variant": hunk["variant_line_range"],
                "regions": sorted(
                    set(hunk["baseline_regions"]) | set(hunk["variant_regions"])
                ),
            }
            for hunk in hunks
        ]
        unexpected = 0 if all(h["allowed_by_arm"] for h in hunks) else len(hunks)
        arm_entries.append({
            **spec,
            "path": str(out_path.relative_to(ROOT)),
            "sha256": variant_sha,
            "unexpected_diff_count": unexpected,
            "changed_line_ranges": changed_ranges,
        })
        diff_entries.append({
            "arm": arm,
            "base_prompt_sha": base_sha,
            "variant_prompt_sha": variant_sha,
            "changed_line_ranges": changed_ranges,
            "conceptual_factor": spec["conceptual_factor"],
            "unexpected_diff_count": unexpected,
            "diff_hunks": hunks,
        })

    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    manifest = {
        "schema_version": "actor_refinement_prompt_variants@1.0.0",
        "created_at_utc": created,
        "base_prompt": {
            "path": str(BASE_PROMPT.relative_to(ROOT)),
            "sha256": base_sha,
        },
        "construction": {
            "script": str(Path(__file__).resolve().relative_to(ROOT)),
            "script_sha256": _sha256_file(Path(__file__).resolve()),
            "gold_used": False,
            "benchmark_lexicon_added": False,
            "iterative_search": False,
        },
        "arms": arm_entries,
    }
    PROMPT_MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    diff_manifest = {
        "schema_version": "actor_refinement_prompt_diff@1.0.0",
        "created_at_utc": created,
        "base_prompt_sha": base_sha,
        "expected_unexpected_diff_count": 0,
        "unexpected_diff_count": sum(
            entry["unexpected_diff_count"] for entry in diff_entries
        ),
        "arms": diff_entries,
    }
    DIFF_MANIFEST.write_text(
        json.dumps(diff_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )

    # Pre-execution manifest. Prompt hashes and planned calls are frozen here
    # before any evaluation score exists.
    experiment_manifest = {
        "schema_version": "d1_actor_refinement_experiment@1.0.0",
        "experiment_id": "d1_actor_refinement_v1",
        "created_at_utc": created,
        "status": "frozen_pre_execution",
        "scope": "development_screening_only",
        "design": {
            "arms": [entry["arm"] for entry in arm_entries],
            "planned_calls": 600,
            "samples_per_arm": 150,
            "repeat_count": 0,
            "fresh_baseline": True,
            "one_factor_per_arm": True,
            "combined_arm_allowed": False,
        },
        "prompts": {
            entry["arm"]: {
                "path": entry["path"],
                "sha256": entry["sha256"],
                "conceptual_factor": entry["conceptual_factor"],
            }
            for entry in arm_entries
        },
        "model": {
            "id": "deepseek-v4-pro",
            "provider": "openai_compatible",
            "documented_release": "DeepSeek-V4-Pro-0813",
        },
        "sampling": {
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 4096,
            "retry": 0,
            "stream": False,
            "thinking": {"type": "disabled"},
            "response_format": None,
        },
        "dataset": {
            "path": "data/input/estg150_formal_inference_input_v2.json",
            "sample_count": 150,
            "first_sample_id": "estg_000002",
        },
        "canonicalizer": {
            "policy": "repair_v1",
            "explicit_pin": True,
        },
        "evaluator": {
            "id": "sun_literal_overlap_evaluation@2.0.0",
            "same_for_all_arms": True,
        },
        "gold_isolation": {
            "used_during_prompt_construction": False,
            "used_during_api_execution": False,
            "evaluation_after_predictions_locked": True,
        },
    }
    EXPERIMENT_MANIFEST.write_text(
        json.dumps(experiment_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    return {
        "manifest": manifest,
        "diff_manifest": diff_manifest,
        "experiment_manifest": experiment_manifest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="build and print hashes without writing")
    args = parser.parse_args()
    if args.check:
        base_bytes = BASE_PROMPT.read_bytes()
        if _sha256_bytes(base_bytes) != EXPECTED_BASE_SHA:
            raise SystemExit("base prompt SHA drift")
        base_text = base_bytes.decode("utf-8")
        for spec in ARMS:
            text = _build_variant_text(spec["arm"], base_text)
            hunks = _line_diff(base_text, text)
            _classify_hunks(spec["arm"], hunks)
            print(spec["arm"], _sha256_bytes(text.encode("utf-8")),
                  len(hunks))
        return 0
    result = build()
    print(json.dumps({
        "prompt_manifest": str(PROMPT_MANIFEST.relative_to(ROOT)),
        "diff_manifest": str(DIFF_MANIFEST.relative_to(ROOT)),
        "experiment_manifest": str(EXPERIMENT_MANIFEST.relative_to(ROOT)),
        "unexpected_diff_count": result["diff_manifest"]["unexpected_diff_count"],
        "arms": [
            {"arm": entry["arm"], "sha256": entry["sha256"]}
            for entry in result["manifest"]["arms"]
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())