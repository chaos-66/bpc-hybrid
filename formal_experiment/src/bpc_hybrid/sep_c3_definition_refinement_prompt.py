# -*- coding: utf-8 -*-
"""Offline composer for the non-active SEP-C3 definition-refinement candidate.

The module follows the existing targeted-refinement assembly mechanism:
it reuses the frozen ``modular_v1`` common skeleton and all existing E
examples byte-for-byte except for the approved synthetic replacement of E4.
It then appends the approved ``R_DEF`` definition guidance as a separate
system-prompt paragraph.  It does not modify R_A, R_C, S, J, the active prompt
family, or the active prompt registry.

No network access and no API call are performed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import hashlib
import json

import bpc_hybrid.modular_prompt as mp
import bpc_hybrid.modular_refinement_prompt as rp


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFINEMENT_DIR = (
    PROJECT_ROOT / "prompts" / "sun_compat" / "modular_refinement_v1"
)
PROMPT_DIR = (
    PROJECT_ROOT
    / "prompts"
    / "sun_compat"
    / "modular_definition_refinement_v1"
)
GENERATED_DIR = PROMPT_DIR / "generated"
COMPATIBILITY_DIR = GENERATED_DIR / "compatibility"

R_DEF_PATH = REFINEMENT_DIR / "R_DEF_definition_guidance.md"
CANDIDATE_E_PATH = PROMPT_DIR / "E_examples_E4_v2.md"

CANDIDATE_ARMS = ("BASE", "R_DEF")
COMPATIBILITY_ARMS = (
    "COMPAT_R_A_R_DEF",
    "COMPAT_R_C_R_DEF",
    "COMPAT_R_A_R_C_R_DEF",
)
ALL_ARMS = CANDIDATE_ARMS + COMPATIBILITY_ARMS

COMPAT_OLD_ARM = {
    "COMPAT_R_A_R_DEF": "B",
    "COMPAT_R_C_R_DEF": "C",
    "COMPAT_R_A_R_C_R_DEF": "D",
}

# The approved R_DEF wording, supplied by the research design.  Only the
# paragraph boundary is formatting; the semantic content is otherwise exact.
R_DEF_TEXT = (
    "Definition is semantic rather than lexical. A clause may establish legal "
    "status, identity, classification or membership, legal fiction, or a "
    "scope/applicability characterization even without an explicit definition "
    "marker. \"Shall\" does not by itself make a clause an obligation, and "
    "\"shall\" plus a verb does not by itself determine modality. Classify "
    "from the semantic function of the clause in context. An obligation "
    "imposes required conduct or a required method on a duty bearer or "
    "regulated subject, whereas a definition characterizes what something is "
    "or how it is legally treated.\n\n"
    "A definition clause should still contain an action representing its "
    "definitional predicate. Do not omit the action merely because the clause "
    "is classificatory, stative, relational, or copular. Extract the "
    "predicate supported by the source evidence. This is an action-presence "
    "principle only and does not define a universal exact action-span "
    "boundary."
)

OLD_E4_BLOCK = (
    "Example E4 \u2014 definition clause followed by an obligation clause:\n"
    "Input: \"'Personal data' means information about a person; the controller "
    "must protect it.\"\n"
    "- clause 1 span [0,48): definition; evidence \"means\" [16,21); actors "
    "and actions empty\n"
    "- clause 2 span [50,81): obligation; evidence \"must\" [65,69); actor "
    "\"the controller\" [50,64), normalized \"controller\"; action \"protect "
    "it\" [70,80)\n"
    "- conditions, constraints, exceptions: empty in both clauses\n\n"
)

NEW_E4_BLOCK = (
    "Example E4 \u2014 synthetic shall-definition (one clause):\n"
    "Input: \"A digitally signed copy shall be treated as an original "
    "document.\"\n"
    "- clause span [0,64): definition; evidence \"shall\" [24,29); actors "
    "empty; action \"be treated as an original document\" [30,64); "
    "no other field populated\n\n"
)

E4_V2_SENTENCE = (
    "A digitally signed copy shall be treated as an original document."
)
E4_V2_EVIDENCE_TEXT = "shall"
E4_V2_ACTION_TEXT = "be treated as an original document"


class DefinitionRefinementPromptError(RuntimeError):
    """The definition-refinement candidate sources are inconsistent."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


def _canonical_arm(arm: str) -> str:
    value = str(arm).strip().upper()
    if value not in ALL_ARMS:
        raise DefinitionRefinementPromptError(
            f"unknown definition-refinement arm: {arm!r}"
        )
    return value


def expected_candidate_e_text() -> str:
    """Return active E with exactly the approved E4 block replaced."""
    source = mp.load_module_texts()["E"]
    if source.count(OLD_E4_BLOCK) != 1:
        raise DefinitionRefinementPromptError(
            "active E module does not contain the expected E4 block exactly once"
        )
    candidate = source.replace(OLD_E4_BLOCK, NEW_E4_BLOCK, 1)
    if candidate.count(NEW_E4_BLOCK) != 1 or OLD_E4_BLOCK in candidate:
        raise DefinitionRefinementPromptError(
            "candidate E module replacement is not exact"
        )
    # Only E4 may differ.
    if source.replace(OLD_E4_BLOCK, "", 1) != candidate.replace(
        NEW_E4_BLOCK, "", 1
    ):
        raise DefinitionRefinementPromptError(
            "candidate E module changed content outside E4"
        )
    return candidate


def expected_r_def_text() -> str:
    return R_DEF_TEXT


def ensure_source_files(*, overwrite: bool = False) -> None:
    """Write the two candidate-only source files if needed."""
    for path, expected in (
        (CANDIDATE_E_PATH, expected_candidate_e_text()),
        (R_DEF_PATH, expected_r_def_text()),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = _normalize_text(path.read_text(encoding="utf-8"))
            if existing == _normalize_text(expected):
                continue
            if not overwrite:
                raise DefinitionRefinementPromptError(
                    f"refusing to overwrite candidate source: {path}"
                )
        path.write_text(expected, encoding="utf-8", newline="\n")


def load_definition_guidance_text() -> str:
    if not R_DEF_PATH.is_file():
        raise DefinitionRefinementPromptError(
            f"missing definition guidance source: {R_DEF_PATH}"
        )
    text = _normalize_text(R_DEF_PATH.read_text(encoding="utf-8"))
    if text != R_DEF_TEXT:
        raise DefinitionRefinementPromptError(
            "R_DEF source text does not match the approved wording"
        )
    return text


def load_candidate_e_text() -> str:
    expected = expected_candidate_e_text()
    if not CANDIDATE_E_PATH.is_file():
        raise DefinitionRefinementPromptError(
            f"missing candidate E source: {CANDIDATE_E_PATH}"
        )
    text = _normalize_text(CANDIDATE_E_PATH.read_text(encoding="utf-8"))
    if text != expected:
        raise DefinitionRefinementPromptError(
            "candidate E source differs from the deterministic E4 replacement"
        )
    return text


def candidate_module_texts() -> dict[str, str]:
    texts = mp.load_module_texts()
    texts["E"] = expected_candidate_e_text()
    return texts


def candidate_e4_span_record() -> dict:
    """Derive the E4 v2 offsets deterministically from the synthetic string."""
    sentence = E4_V2_SENTENCE
    evidence_start = sentence.index(E4_V2_EVIDENCE_TEXT)
    evidence_end = evidence_start + len(E4_V2_EVIDENCE_TEXT)
    action_start = sentence.index(E4_V2_ACTION_TEXT)
    action_end = action_start + len(E4_V2_ACTION_TEXT)
    clause_text = sentence[:-1]  # existing examples exclude terminal period
    clause_start = 0
    clause_end = len(clause_text)

    spans = {
        "clause_span": (clause_text, clause_start, clause_end),
        "modality_evidence": (
            E4_V2_EVIDENCE_TEXT,
            evidence_start,
            evidence_end,
        ),
        "action": (E4_V2_ACTION_TEXT, action_start, action_end),
    }
    for name, (text, start, end) in spans.items():
        if sentence[start:end] != text:
            raise DefinitionRefinementPromptError(
                f"derived E4 v2 {name} offset mismatch"
            )
        if not (clause_start <= start <= end <= clause_end):
            raise DefinitionRefinementPromptError(
                f"derived E4 v2 {name} is outside clause_span"
            )
    if action_end != clause_end:
        raise DefinitionRefinementPromptError(
            "E4 v2 action must end at the clause boundary"
        )
    if action_start < evidence_end:
        raise DefinitionRefinementPromptError(
            "E4 v2 action overlaps the modality evidence"
        )
    return {
        "sentence": sentence,
        "clause_span": {
            "text": clause_text,
            "start": clause_start,
            "end": clause_end,
        },
        "modality_evidence": {
            "text": E4_V2_EVIDENCE_TEXT,
            "start": evidence_start,
            "end": evidence_end,
        },
        "action": {
            "text": E4_V2_ACTION_TEXT,
            "start": action_start,
            "end": action_end,
            "normalized": E4_V2_ACTION_TEXT,
        },
    }


def e4_v2_candidate_record() -> dict:
    derived = candidate_e4_span_record()
    sentence = derived["sentence"]
    clause = derived["clause_span"]
    evidence = derived["modality_evidence"]
    action = derived["action"]
    record = {
        "schema_version": "1.0.0",
        "sample_id": "synthetic_definition_e4_v2",
        "source_id": "synthetic_definition_e4_v2",
        "source_text": sentence,
        "clauses": [
            {
                "clause_id": "c1",
                "clause_span": dict(clause),
                "modality": {
                    "label": "definition",
                    "evidence": [dict(evidence)],
                },
                "actors": [],
                "actions": [
                    {
                        "id": "c1_action_1",
                        "text": action["text"],
                        "start": action["start"],
                        "end": action["end"],
                        "normalized": action["normalized"],
                    }
                ],
                "conditions": [],
                "constraints": [],
                "exceptions": [],
                "actor_action_map": [],
                "order_relations": [],
            }
        ],
        "method": {
            "name": "direct_llm",
            "schema_source": "stage2_prediction.schema.json@1.0.0",
        },
        "validation": {
            "schema_valid": True,
            "cross_field_valid": True,
            "errors": [],
        },
        "unsupported_or_ambiguous": [],
    }
    return {
        "schema_version": "sep_c3_definition_candidate_e4@2.0.0",
        "status": "DESIGN_CANDIDATE_NOT_APPLIED",
        "candidate_id": "definition_shall_definition_e4_v2",
        "replaces_component": {
            "file": "prompts/sun_compat/modular_v1/examples_E.md",
            "example_id": "E4",
            "current_heading": (
                "Example E4 \u2014 definition clause followed by an obligation "
                "clause"
            ),
        },
        "synthetic_sentence": sentence,
        "example_block_markdown": NEW_E4_BLOCK.rstrip("\n"),
        "expected_rule_record": record,
        "required_semantic_intent": {
            "modality": "definition",
            "actor": "empty",
            "action": "non-empty definitional predicate",
            "condition": "empty",
            "constraint": "empty",
            "exception": "empty",
        },
        "teaches_only": [
            '"shall" can occur in a definition',
            "a definition can have no actor",
            "a definition still receives an action",
        ],
        "does_not_teach": [
            "No lexical shortcut such as shall be deemed => definition",
            "No lexical shortcut such as shall apply => definition",
            "No lexical shortcut such as shall be treated => definition",
            "No condition, constraint, or exception supervision",
            "No exact universal action-span rule",
        ],
    }


@dataclass(frozen=True)
class DefinitionPrompt:
    arm: str
    system_prompt: str
    user_prompt_template: str
    source_hashes: Mapping[str, str]
    composition_sha256: str
    flags: Mapping[str, bool]
    baseline_active_arm: str

    def render_user(self, sample_id: str, source_text: str) -> str:
        return self.user_prompt_template.format(
            sample_id=sample_id,
            source_id=sample_id,
            source_text=source_text,
        )

    def request_messages(self, sample_id: str, source_text: str) -> list[dict]:
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.render_user(sample_id, source_text)},
        ]

    def to_markdown(self) -> str:
        hash_lines = "\n".join(
            f"source_{key}_sha256: {value}"
            for key, value in sorted(self.source_hashes.items())
        )
        flag_lines = "\n".join(
            f"use_{key}: {str(self.flags[key]).lower()}"
            for key in ("R_A", "R_C", "R_DEF")
        )
        metadata = (
            "<!--\n"
            "generated_by: scripts/build_sep_c3_definition_refinement_v1.py\n"
            "candidate_only: true\n"
            "active_prompt: false\n"
            f"arm: {self.arm}\n"
            "e4_revision: v2\n"
            f"baseline_active_arm: {self.baseline_active_arm}\n"
            f"{flag_lines}\n"
            f"{hash_lines}\n"
            f"composition_sha256: {self.composition_sha256}\n"
            "-->\n\n"
        )
        title = (
            "# SEP-C3 Definition Refinement Candidate v1 "
            f"(arm {self.arm}: R_A={int(self.flags['R_A'])}, "
            f"R_C={int(self.flags['R_C'])}, "
            f"R_DEF={int(self.flags['R_DEF'])})\n\n"
        )
        return (
            metadata
            + title
            + "## System Prompt\n\n```text\n"
            + self.system_prompt
            + "\n```\n\n## User Prompt Template\n\n```text\n"
            + self.user_prompt_template
            + "\n```\n"
        )


def _base_prompt():
    return mp.render_modular_prompt("100", candidate_module_texts())


def render_definition_prompt(arm: str, *, r_def_text: str | None = None) -> DefinitionPrompt:
    arm = _canonical_arm(arm)
    guidance = _normalize_text(r_def_text or load_definition_guidance_text())
    if guidance != R_DEF_TEXT:
        raise DefinitionRefinementPromptError(
            "provided R_DEF text does not match the approved wording"
        )
    base = _base_prompt()
    if arm in CANDIDATE_ARMS:
        system_prompt = base.system_prompt
        if arm == "R_DEF":
            system_prompt = system_prompt + "\n\n" + guidance
        flags = {
            "R_A": False,
            "R_C": False,
            "R_DEF": arm == "R_DEF",
        }
        baseline_active_arm = "A"
        repair_source_hashes = {}
    else:
        old_arm = COMPAT_OLD_ARM[arm]
        old = rp.render_refinement_prompt(old_arm)
        system_prompt = old.system_prompt + "\n\n" + guidance
        flags = {
            "R_A": old_arm in ("B", "D"),
            "R_C": old_arm in ("C", "D"),
            "R_DEF": True,
        }
        baseline_active_arm = old_arm
        repair_source_hashes = {
            "R_A": old.source_hashes["R_A"],
            "R_C": old.source_hashes["R_C"],
        }

    user_prompt_template = base.user_prompt_template
    source_hashes = {
        "common": base.source_hashes["common"],
        "E_v2": _sha256_text(expected_candidate_e_text()),
        "R_DEF": _sha256_text(guidance),
    }
    source_hashes.update(repair_source_hashes)
    composition_sha256 = _sha256_text(
        system_prompt + "\n\n<!--USER-->\n\n" + user_prompt_template
    )
    return DefinitionPrompt(
        arm=arm,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
        source_hashes=source_hashes,
        composition_sha256=composition_sha256,
        flags=flags,
        baseline_active_arm=baseline_active_arm,
    )


def render_all() -> dict[str, DefinitionPrompt]:
    return {arm: render_definition_prompt(arm) for arm in ALL_ARMS}


def render_candidate_arms() -> dict[str, DefinitionPrompt]:
    return {arm: render_definition_prompt(arm) for arm in CANDIDATE_ARMS}


def generated_stem(arm: str) -> str:
    return f"direct_llm_definition_{_canonical_arm(arm)}_v1"


def generated_path(arm: str, directory: Path | None = None) -> Path:
    arm = _canonical_arm(arm)
    if directory is not None:
        return directory / f"{generated_stem(arm)}.md"
    if arm in COMPATIBILITY_ARMS:
        return COMPATIBILITY_DIR / f"{generated_stem(arm)}.md"
    return GENERATED_DIR / f"{generated_stem(arm)}.md"


def generated_manifest_path(directory: Path | None = None) -> Path:
    return (directory or GENERATED_DIR) / "manifest.json"


def loader_name(arm: str) -> str:
    arm = _canonical_arm(arm)
    rel = generated_path(arm).relative_to(PROJECT_ROOT / "prompts" / "sun_compat")
    return rel.with_suffix("").as_posix()


def _manifest(prompts: Mapping[str, DefinitionPrompt]) -> dict:
    active_a = rp.render_refinement_prompt("A")
    return {
        "schema_version": "sep_c3_definition_refinement_candidate_manifest@1.0.0",
        "candidate_family": "direct_llm_definition_refinement_candidate_v1",
        "status": "candidate_only_not_active",
        "active_prompt_family": "direct_llm_refinement_v1",
        "active_registry_unchanged": True,
        "candidate_arms": list(CANDIDATE_ARMS),
        "compatibility_arms": list(COMPATIBILITY_ARMS),
        "e4_revision": "v2",
        "e4_replacement": {
            "old_text": OLD_E4_BLOCK.rstrip("\n"),
            "new_text": NEW_E4_BLOCK.rstrip("\n"),
            "new_text_sha256": _sha256_text(NEW_E4_BLOCK.rstrip("\n")),
            "synthetic_sentence": E4_V2_SENTENCE,
            "expected_rule_record": e4_v2_candidate_record()[
                "expected_rule_record"
            ],
        },
        "source_files": {
            "common_system": {
                "path": "prompts/sun_compat/modular_v1/common_system.md",
                "sha256": _sha256_text(mp.load_module_texts()["common_system"]),
            },
            "common_user": {
                "path": "prompts/sun_compat/modular_v1/user_envelope.md",
                "sha256": _sha256_text(mp.load_module_texts()["common_user"]),
            },
            "examples_E_active": {
                "path": "prompts/sun_compat/modular_v1/examples_E.md",
                "sha256": _sha256_text(mp.load_module_texts()["E"]),
            },
            "candidate_E_v2": {
                "path": str(CANDIDATE_E_PATH.relative_to(PROJECT_ROOT)).replace(
                    "\\", "/"
                ),
                "sha256": _sha256_text(expected_candidate_e_text()),
            },
            "R_DEF": {
                "path": str(R_DEF_PATH.relative_to(PROJECT_ROOT)).replace(
                    "\\", "/"
                ),
                "sha256": _sha256_text(R_DEF_TEXT),
            },
        },
        "active_baseline": {
            "arm_A_system_sha256": _sha256_text(active_a.system_prompt),
            "arm_A_user_sha256": _sha256_text(active_a.user_prompt_template),
            "arm_A_composition_sha256": active_a.composition_sha256,
        },
        "prompts": {
            arm: {
                "path": str(generated_path(arm).relative_to(PROJECT_ROOT)).replace(
                    "\\", "/"
                ),
                "markdown_sha256": _sha256_text(prompt.to_markdown()),
                "system_sha256": _sha256_text(prompt.system_prompt),
                "user_sha256": _sha256_text(prompt.user_prompt_template),
                "composition_sha256": prompt.composition_sha256,
                "flags": dict(prompt.flags),
                "source_hashes": dict(prompt.source_hashes),
            }
            for arm, prompt in prompts.items()
        },
    }


def write_generated(*, overwrite: bool = False) -> dict:
    ensure_source_files(overwrite=overwrite)
    prompts = render_all()
    for arm in ALL_ARMS:
        path = generated_path(arm)
        if path.exists() and not overwrite:
            raise DefinitionRefinementPromptError(
                f"refusing to overwrite existing candidate prompt: {path}"
            )
    for arm, prompt in prompts.items():
        path = generated_path(arm)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(prompt.to_markdown(), encoding="utf-8", newline="\n")
    manifest = _manifest(prompts)
    manifest_path = generated_manifest_path()
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest