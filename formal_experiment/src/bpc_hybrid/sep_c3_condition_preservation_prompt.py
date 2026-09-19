# -*- coding: utf-8 -*-
"""Offline composer for the SEP-C3 condition-preservation prompt family.

The family is deliberately separate from the frozen formal default v6 and from
the historical targeted-refinement arms.  It reuses the frozen common + E
skeleton and the frozen R_A / old R_C modules byte-for-byte:

* BASE    = common + E + R_A                    (same actual request as old B)
* RC1     = BASE + frozen old R_C               (same actual request as old D)
* RC_KEEP = RC1 + the one fixed preservation sentence

No network access and no API call are performed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import hashlib
import json

import bpc_hybrid.modular_refinement_prompt as rp


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = PROJECT_ROOT / "prompts" / "sun_compat" / "modular_condition_preservation_v1"
GENERATED_DIR = PROMPT_DIR / "generated"

ARMS = ("BASE", "RC1", "RC_KEEP")
OLD_ARM_FOR = {
    "BASE": "B",
    "RC1": "D",
    "RC_KEEP": "D",
}

# The only new design sentence for RC_KEEP.  It must be byte-for-byte the
# wording supplied by the research design.
CONDITION_PRESERVATION_TEXT = (
    "Keep each applicability condition as a complete proposition in conditions; "
    "extracting an overlapping or nested constraint must not replace or remove "
    "that condition."
)


class ConditionPreservationPromptError(RuntimeError):
    """The condition-preservation prompt contract is inconsistent."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sent_prompt_text(
    system_prompt: str, user_prompt_template: str
) -> str:
    """Canonical sent-prompt text used by the existing runner convention."""
    return system_prompt + "\n\n<!--USER-->\n\n" + user_prompt_template


def _canonical_arm(arm: str) -> str:
    value = str(arm).strip().upper()
    if value not in ARMS:
        raise ConditionPreservationPromptError(
            f"unknown condition-preservation arm: {arm!r}"
        )
    return value


@dataclass(frozen=True)
class ConditionPreservationPrompt:
    arm: str
    old_arm: str
    system_prompt: str
    user_prompt_template: str
    source_hashes: Mapping[str, str]
    composition_sha256: str
    appended_sentence: str | None

    @property
    def flags(self) -> dict[str, bool]:
        return {
            "R_A": True,
            "R_C": True,
            "condition_preservation_sentence": bool(self.appended_sentence),
        }

    def render_user(self, sample_id: str, source_text: str) -> str:
        return self.user_prompt_template.format(
            sample_id=sample_id,
            source_id=sample_id,
            source_text=source_text,
        )

    def request_messages(self, sample_id: str, source_text: str) -> list[dict]:
        return [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": self.render_user(sample_id, source_text),
            },
        ]

    def to_markdown(self) -> str:
        hash_lines = "\n".join(
            f"source_{key}_sha256: {value}"
            for key, value in sorted(self.source_hashes.items())
        )
        sentence_line = (
            "appended_sentence: none"
            if self.appended_sentence is None
            else f"appended_sentence_sha256: {_sha256_text(self.appended_sentence)}"
        )
        metadata = (
            "<!--\n"
            "generated_by: scripts/prepare_sep_c3_condition_preservation_v1.py\n"
            f"arm: {self.arm}\n"
            f"old_arm_equivalence: {self.old_arm}\n"
            f"use_R_A: true\n"
            f"use_R_C: true\n"
            f"use_condition_preservation_sentence: "
            f"{str(bool(self.appended_sentence)).lower()}\n"
            f"{sentence_line}\n"
            f"{hash_lines}\n"
            f"composition_sha256: {self.composition_sha256}\n"
            "-->\n\n"
        )
        title = (
            f"# SEP-C3 Condition Preservation Prompt v1 (arm {self.arm})\n\n"
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


def _frozen_old_prompts() -> tuple[rp.RefinementPrompt, rp.RefinementPrompt]:
    """Return old B and D, fail closed on any old source drift."""
    old_b = rp.render_refinement_prompt("B")
    old_d = rp.render_refinement_prompt("D")
    expected_rc1 = old_b.system_prompt + "\n\n" + rp.R_C_TEXT
    if old_d.system_prompt != expected_rc1:
        raise ConditionPreservationPromptError(
            "old D is not exactly old B plus frozen R_C"
        )
    if old_b.user_prompt_template != old_d.user_prompt_template:
        raise ConditionPreservationPromptError(
            "old B and old D user envelopes differ"
        )
    return old_b, old_d


def render_condition_preservation_prompt(
    arm: str,
) -> ConditionPreservationPrompt:
    """Render one BASE / RC1 / RC_KEEP prompt without writing anything."""
    arm = _canonical_arm(arm)
    old_b, old_d = _frozen_old_prompts()
    old = old_b if arm == "BASE" else old_d
    sentence = CONDITION_PRESERVATION_TEXT if arm == "RC_KEEP" else None
    system_prompt = old.system_prompt
    if sentence is not None:
        system_prompt = system_prompt + "\n\n" + sentence
    composition_sha256 = _sha256_text(
        _sent_prompt_text(system_prompt, old.user_prompt_template)
    )
    source_hashes = dict(old.source_hashes)
    source_hashes["old_B_composition_sha256"] = old_b.composition_sha256
    source_hashes["old_D_composition_sha256"] = old_d.composition_sha256
    if sentence is not None:
        source_hashes["condition_preservation_sentence"] = _sha256_text(
            sentence
        )
    return ConditionPreservationPrompt(
        arm=arm,
        old_arm=OLD_ARM_FOR[arm],
        system_prompt=system_prompt,
        user_prompt_template=old.user_prompt_template,
        source_hashes=source_hashes,
        composition_sha256=composition_sha256,
        appended_sentence=sentence,
    )


def render_all() -> dict[str, ConditionPreservationPrompt]:
    return {arm: render_condition_preservation_prompt(arm) for arm in ARMS}


def generated_stem(arm: str) -> str:
    return f"direct_llm_condition_preservation_{_canonical_arm(arm)}_v1"


def generated_path(
    arm: str, directory: Path = GENERATED_DIR
) -> Path:
    return directory / f"{generated_stem(arm)}.md"


def generated_manifest_path(directory: Path = GENERATED_DIR) -> Path:
    return directory / "manifest.json"


def _manifest(
    prompts: Mapping[str, ConditionPreservationPrompt],
    *,
    file_hashes: Mapping[str, str],
) -> dict:
    old_b, old_d = _frozen_old_prompts()
    return {
        "schema_version": "sep_c3_condition_preservation_prompt_manifest@1.0.0",
        "prompt_family": "direct_llm_condition_preservation_v1",
        "arms": list(ARMS),
        "old_arm_equivalence": {
            "BASE": "frozen old B actual sent prompt",
            "RC1": "frozen old D actual sent prompt",
            "RC_KEEP": "RC1 plus exactly one appended sentence",
        },
        "frozen_sources": {
            "old_R_A_text_sha256": _sha256_text(rp.R_A_TEXT),
            "old_R_C_text_sha256": _sha256_text(rp.R_C_TEXT),
            "old_B_system_sha256": _sha256_text(old_b.system_prompt),
            "old_B_user_sha256": _sha256_text(old_b.user_prompt_template),
            "old_B_composition_sha256": old_b.composition_sha256,
            "old_D_system_sha256": _sha256_text(old_d.system_prompt),
            "old_D_user_sha256": _sha256_text(old_d.user_prompt_template),
            "old_D_composition_sha256": old_d.composition_sha256,
        },
        "new_design_sentence": {
            "text": CONDITION_PRESERVATION_TEXT,
            "sha256": _sha256_text(CONDITION_PRESERVATION_TEXT),
            "appended_after": "frozen old R_C, as a separate system-prompt paragraph",
        },
        "prompts": {
            arm: {
                "path": str(generated_path(arm).relative_to(PROJECT_ROOT)).replace(
                    "\\", "/"
                ),
                "markdown_sha256": file_hashes[arm],
                "system_sha256": _sha256_text(prompt.system_prompt),
                "user_sha256": _sha256_text(prompt.user_prompt_template),
                "composition_sha256": prompt.composition_sha256,
                "source_hashes": dict(prompt.source_hashes),
                "appended_sentence": prompt.appended_sentence,
            }
            for arm, prompt in prompts.items()
        },
    }


def write_generated(
    directory: Path = GENERATED_DIR, *, overwrite: bool = False
) -> dict:
    prompts = render_all()
    directory.mkdir(parents=True, exist_ok=True)
    for arm in ARMS:
        path = generated_path(arm, directory)
        if path.exists() and not overwrite:
            raise ConditionPreservationPromptError(
                f"refusing to overwrite existing prompt: {path}"
            )
    file_hashes: dict[str, str] = {}
    for arm, prompt in prompts.items():
        path = generated_path(arm, directory)
        text = prompt.to_markdown()
        path.write_text(text, encoding="utf-8", newline="\n")
        file_hashes[arm] = _sha256_text(text)
    manifest = _manifest(prompts, file_hashes=file_hashes)
    generated_manifest_path(directory).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest