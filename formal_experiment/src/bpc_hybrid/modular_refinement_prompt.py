"""Offline composer for the SEP-C3 targeted refinement prompts.

This module owns only the failure-driven refinement family.  It reuses the
frozen ``modular_v1`` common skeleton and E module byte-for-byte, then adds
the two frozen, independently switchable repair modules R_A and R_C.

No network access and no API call are performed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import hashlib
import json

import bpc_hybrid.modular_prompt as modular_v1
from bpc_hybrid.prompt_loader import load_prompt


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFINEMENT_DIR = (
    PROJECT_ROOT / "prompts" / "sun_compat" / "modular_refinement_v1"
)
GENERATED_DIR = REFINEMENT_DIR / "generated"

BASELINE_ARM = "100"
ARMS = ("A", "B", "C", "D")
REPAIR_ORDER = ("R_A", "R_C")
ARM_REPAIRS: Mapping[str, tuple[str, ...]] = {
    "A": (),
    "B": ("R_A",),
    "C": ("R_C",),
    "D": ("R_A", "R_C"),
}

REPAIR_SOURCE_FILES = {
    "R_A": REFINEMENT_DIR / "R_A_actor_minimality.md",
    "R_C": REFINEMENT_DIR / "R_C_constraint_recall.md",
}

# Frozen wording supplied by the research design.  The files in
# ``REPAIR_SOURCE_FILES`` are checked against these exact strings.
R_A_TEXT = (
    "Actor: extract only an explicitly stated entity that bears responsibility "
    "for performing, refraining from, or being subject to the regulated action. "
    "Do not label objects, resources, amounts, or other mentioned noun phrases "
    "as actors merely because they are salient in the sentence. If no "
    "responsible entity is explicitly stated, return no actor."
)
R_C_TEXT = (
    "Constraint: extract an explicit phrase when it directly restricts when, "
    "how, how much, for what purpose, under what legal reference, or with what "
    "exclusivity the regulated action applies. Extract the complete restrictive "
    "phrase rather than an isolated cue word such as \u2018only\u2019."
)
EXPECTED_REPAIR_TEXTS = {"R_A": R_A_TEXT, "R_C": R_C_TEXT}


class RefinementPromptError(RuntimeError):
    """The refinement prompt sources or generated files are inconsistent."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


def load_repair_texts() -> dict[str, str]:
    """Load the two frozen repair modules and fail closed on any drift."""
    texts: dict[str, str] = {}
    for key, path in REPAIR_SOURCE_FILES.items():
        if not path.is_file():
            raise RefinementPromptError(f"missing refinement source: {path}")
        text = _normalize_text(path.read_text(encoding="utf-8"))
        if text != EXPECTED_REPAIR_TEXTS[key]:
            raise RefinementPromptError(
                f"{key} source text does not match the frozen wording"
            )
        texts[key] = text
    return texts


def parse_arm(arm: str) -> tuple[str, ...]:
    value = str(arm).strip().upper()
    if value not in ARM_REPAIRS:
        raise RefinementPromptError(f"unknown refinement arm: {arm!r}")
    return ARM_REPAIRS[value]


@dataclass(frozen=True)
class RefinementPrompt:
    arm: str
    flags: Mapping[str, bool]
    system_prompt: str
    user_prompt_template: str
    source_hashes: Mapping[str, str]
    composition_sha256: str
    baseline_composition_sha256: str

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
            for key in REPAIR_ORDER
        )
        metadata = (
            "<!--\n"
            "generated_by: scripts/build_sep_c3_targeted_refinement_v1.py\n"
            f"arm: {self.arm}\n"
            f"{flag_lines}\n"
            f"baseline_100_composition_sha256: {self.baseline_composition_sha256}\n"
            f"{hash_lines}\n"
            f"composition_sha256: {self.composition_sha256}\n"
            "-->\n\n"
        )
        title = (
            f"# Direct LLM Targeted Refinement Prompt v1 "
            f"(arm {self.arm}: R_A={int(self.flags['R_A'])}, "
            f"R_C={int(self.flags['R_C'])})\n\n"
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


def render_refinement_prompt(
    arm: str, repair_texts: Mapping[str, str] | None = None
) -> RefinementPrompt:
    """Render one A/B/C/D arm while preserving the frozen 100 baseline."""
    enabled = set(parse_arm(arm))
    repairs = dict(repair_texts or load_repair_texts())
    for key in REPAIR_ORDER:
        if key not in repairs:
            raise RefinementPromptError(f"missing repair text: {key}")

    baseline = modular_v1.render_modular_prompt(BASELINE_ARM)
    system_parts = [baseline.system_prompt]
    for key in REPAIR_ORDER:
        if key in enabled:
            system_parts.append(repairs[key])
    system_prompt = "\n\n".join(
        part.strip() for part in system_parts if part.strip()
    )
    user_prompt_template = baseline.user_prompt_template

    source_hashes = {
        "common": baseline.source_hashes["common"],
        "E": baseline.source_hashes["E"],
        "R_A": _sha256_text(repairs["R_A"]),
        "R_C": _sha256_text(repairs["R_C"]),
    }
    composition_sha256 = _sha256_text(
        system_prompt + "\n\n<!--USER-->\n\n" + user_prompt_template
    )
    return RefinementPrompt(
        arm=str(arm).strip().upper(),
        flags={key: key in enabled for key in REPAIR_ORDER},
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
        source_hashes=source_hashes,
        composition_sha256=composition_sha256,
        baseline_composition_sha256=baseline.composition_sha256,
    )


def render_all(
    repair_texts: Mapping[str, str] | None = None,
) -> dict[str, RefinementPrompt]:
    loaded = dict(repair_texts or load_repair_texts())
    return {arm: render_refinement_prompt(arm, loaded) for arm in ARMS}


def generated_stem(arm: str) -> str:
    parse_arm(arm)
    return f"direct_llm_refinement_{str(arm).strip().upper()}_v1"


def generated_path(arm: str, directory: Path = GENERATED_DIR) -> Path:
    return directory / f"{generated_stem(arm)}.md"


def generated_manifest_path(directory: Path = GENERATED_DIR) -> Path:
    return directory / "manifest.json"


def loader_name(arm: str) -> str:
    return (
        Path("modular_refinement_v1") / "generated" / generated_stem(arm)
    ).as_posix()


def load_generated_prompt(arm: str):
    """Load one generated refinement prompt and verify composer parity."""
    composed = render_refinement_prompt(arm)
    loaded = load_prompt(loader_name(arm))
    if (
        loaded.system_prompt != composed.system_prompt
        or loaded.user_prompt_template != composed.user_prompt_template
    ):
        raise RefinementPromptError(
            f"generated prompt {arm} differs from composer"
        )
    return loaded


def _source_file_hash(path: Path) -> str:
    return _sha256_text(_normalize_text(path.read_text(encoding="utf-8")))


def _manifest(prompts: Mapping[str, RefinementPrompt]) -> dict:
    baseline = modular_v1.render_modular_prompt(BASELINE_ARM)
    baseline_texts = modular_v1.load_module_texts()
    source_files = {
        "common_system": {
            "path": str(
                modular_v1.SOURCE_FILES["common_system"].relative_to(PROJECT_ROOT)
            ).replace("\\", "/"),
            "sha256": _sha256_text(baseline_texts["common_system"]),
        },
        "common_user": {
            "path": str(
                modular_v1.SOURCE_FILES["common_user"].relative_to(PROJECT_ROOT)
            ).replace("\\", "/"),
            "sha256": _sha256_text(baseline_texts["common_user"]),
        },
        "examples_E": {
            "path": str(
                modular_v1.SOURCE_FILES["E"].relative_to(PROJECT_ROOT)
            ).replace("\\", "/"),
            "sha256": _sha256_text(baseline_texts["E"]),
        },
    }
    for key, path in REPAIR_SOURCE_FILES.items():
        source_files[key] = {
            "path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "sha256": _source_file_hash(path),
        }

    return {
        "schema_version": "direct_llm_targeted_refinement_manifest@1.0.0",
        "prompt_family": "direct_llm_refinement_v1",
        "baseline_prompt_family": "direct_llm_modular_v1",
        "baseline_arm": BASELINE_ARM,
        "arm_order": list(ARMS),
        "repair_order": list(REPAIR_ORDER),
        "arm_semantics": {
            "A": "common + E (frozen 100 baseline)",
            "B": "common + E + R_A",
            "C": "common + E + R_C",
            "D": "common + E + R_A + R_C",
        },
        "source_files": source_files,
        "baseline_100": {
            "system_sha256": _sha256_text(baseline.system_prompt),
            "user_sha256": _sha256_text(baseline.user_prompt_template),
            "composition_sha256": baseline.composition_sha256,
            "source_hashes": dict(baseline.source_hashes),
        },
        "arms": {
            arm: {
                "path": str(
                    generated_path(arm).relative_to(PROJECT_ROOT)
                ).replace("\\", "/"),
                "sha256": _sha256_text(prompt.to_markdown()),
                "composition_sha256": prompt.composition_sha256,
                "system_sha256": _sha256_text(prompt.system_prompt),
                "user_sha256": _sha256_text(prompt.user_prompt_template),
                "flags": dict(prompt.flags),
                "source_hashes": dict(prompt.source_hashes),
                "baseline_composition_sha256": (
                    prompt.baseline_composition_sha256
                ),
            }
            for arm, prompt in prompts.items()
        },
    }


def write_generated(
    directory: Path = GENERATED_DIR, *, overwrite: bool = False
) -> dict:
    prompts = render_all()
    directory.mkdir(parents=True, exist_ok=True)
    for arm, prompt in prompts.items():
        path = generated_path(arm, directory)
        if path.exists() and not overwrite:
            raise RefinementPromptError(
                f"refusing to overwrite existing prompt: {path}"
            )
    for arm, prompt in prompts.items():
        generated_path(arm, directory).write_text(
            prompt.to_markdown(), encoding="utf-8", newline="\n"
        )
    manifest = _manifest(prompts)
    generated_manifest_path(directory).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest
