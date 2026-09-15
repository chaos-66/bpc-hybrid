"""Offline composer for the simplified E/S/J Direct-LLM prompt.

The historical v6 prompt and the frozen ``ablation_v2`` arms remain
untouched.  This module owns only the new modular prompt family:

* common system text and user envelope;
* switchable S (semantic rules), E (synthetic examples), and J (output
  organization) blocks;
* deterministic rendering of the eight E/S/J combinations.

No network access and no API call are performed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import hashlib
import json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = PROJECT_ROOT / "prompts" / "sun_compat" / "modular_v1"
GENERATED_DIR = MODULE_DIR / "generated"

SOURCE_FILES = {
    "common_system": MODULE_DIR / "common_system.md",
    "common_user": MODULE_DIR / "user_envelope.md",
    "S": MODULE_DIR / "semantic_rules_S.md",
    "E": MODULE_DIR / "examples_E.md",
    "J": MODULE_DIR / "output_format_J.md",
}

COMBINATION_ORDER = ("E", "S", "J")
COMBINATIONS = tuple(
    f"{e}{s}{j}" for e in (0, 1) for s in (0, 1) for j in (0, 1)
)
# Sort to the documented 000..111 lexical order while keeping code obvious.
COMBINATIONS = tuple(sorted(COMBINATIONS))

REQUIRED_COMMON_MARKERS = (
    "Common task and interface",
    "schema_version, sample_id, source_id, source_text, clauses, method, validation, unsupported_or_ambiguous",
    "clause_id, clause_span, modality, actors, actions, conditions, constraints, exceptions, actor_action_map, order_relations",
    '"name": "direct_llm"',
    "stage2_prediction.schema.json@1.0.0",
    "unsupported_or_ambiguous",
)


class ModularPromptError(RuntimeError):
    """The modular prompt sources or generated files are inconsistent."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


def load_module_texts() -> dict[str, str]:
    """Read and normalize all source modules.

    Returning normalized text makes composition independent of the local
    checkout's line endings so generated prompt hashes are stable.
    """
    texts: dict[str, str] = {}
    for key, path in SOURCE_FILES.items():
        if not path.is_file():
            raise ModularPromptError(f"missing modular prompt source: {path}")
        texts[key] = _normalize_text(path.read_text(encoding="utf-8"))
        if not texts[key]:
            raise ModularPromptError(f"empty modular prompt source: {path}")
    return texts


def parse_combination(combination: str) -> dict[str, bool]:
    """Parse a three-character ESJ bit string such as ``101``."""
    value = str(combination).strip().upper()
    if len(value) != 3 or any(ch not in "01" for ch in value):
        raise ModularPromptError(
            f"combination must be a three-character ESJ bit string: {combination!r}"
        )
    flags = {
        "E": value[0] == "1",
        "S": value[1] == "1",
        "J": value[2] == "1",
    }
    return flags


@dataclass(frozen=True)
class ModularPrompt:
    combination: str
    flags: Mapping[str, bool]
    system_prompt: str
    user_prompt_template: str
    source_hashes: Mapping[str, str]
    composition_sha256: str

    def render_user(self, sample_id: str, source_text: str) -> str:
        """Render the user envelope for one sample."""
        return self.user_prompt_template.format(
            sample_id=sample_id,
            source_id=sample_id,
            source_text=source_text,
        )

    def request_messages(self, sample_id: str, source_text: str) -> list[dict]:
        """Return the exact system/user messages a runner should send."""
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.render_user(sample_id, source_text)},
        ]

    def to_markdown(self) -> str:
        """Render a standalone, prompt_loader-compatible Markdown file."""
        hash_lines = "\n".join(
            f"source_{key}_sha256: {value}"
            for key, value in sorted(self.source_hashes.items())
        )
        flag_lines = "\n".join(
            f"use_{key}: {str(self.flags[key]).lower()}"
            for key in COMBINATION_ORDER
        )
        metadata = (
            "<!--\n"
            "generated_by: scripts/build_modular_prompt_v1.py\n"
            f"combination_ESJ: {self.combination}\n"
            f"{flag_lines}\n"
            f"{hash_lines}\n"
            f"composition_sha256: {self.composition_sha256}\n"
            "-->\n\n"
        )
        title = (
            f"# Direct LLM Modular Prompt v1 "
            f"(E={int(self.flags['E'])},S={int(self.flags['S'])},J={int(self.flags['J'])})\n\n"
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


def render_modular_prompt(
    combination: str, texts: Mapping[str, str] | None = None
) -> ModularPrompt:
    """Render one E/S/J combination without writing anything to disk."""
    flags = parse_combination(combination)
    texts = dict(texts or load_module_texts())

    system_parts = [texts["common_system"]]
    if flags["S"]:
        system_parts.append(texts["S"])
    if flags["J"]:
        system_parts.append(texts["J"])
    system_prompt = "\n\n".join(part.strip() for part in system_parts if part.strip())

    user_parts = [texts["common_user"]]
    if flags["E"]:
        user_parts.append(texts["E"])
    user_prompt_template = "\n\n".join(
        part.strip() for part in user_parts if part.strip()
    )

    source_hashes = {
        "common": _sha256_text(
            texts["common_system"] + "\n\n" + texts["common_user"]
        ),
        "S": _sha256_text(texts["S"]),
        "E": _sha256_text(texts["E"]),
        "J": _sha256_text(texts["J"]),
    }
    composition_sha256 = _sha256_text(
        system_prompt + "\n\n<!--USER-->\n\n" + user_prompt_template
    )
    return ModularPrompt(
        combination=combination_code(flags),
        flags=flags,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
        source_hashes=source_hashes,
        composition_sha256=composition_sha256,
    )


def combination_code(flags: Mapping[str, bool]) -> str:
    return "".join("1" if flags[key] else "0" for key in COMBINATION_ORDER)


def render_all(texts: Mapping[str, str] | None = None) -> dict[str, ModularPrompt]:
    """Render all eight combinations, keyed by ``ESJ`` code."""
    loaded = dict(texts or load_module_texts())
    return {
        code: render_modular_prompt(code, loaded)
        for code in COMBINATIONS
    }


def generated_stem(combination: str) -> str:
    parse_combination(combination)
    return f"direct_llm_modular_{combination}_v1"


def generated_path(combination: str, directory: Path = GENERATED_DIR) -> Path:
    return directory / f"{generated_stem(combination)}.md"


def generated_manifest_path(directory: Path = GENERATED_DIR) -> Path:
    return directory / "manifest.json"


def _manifest(prompts: Mapping[str, ModularPrompt]) -> dict:
    texts = load_module_texts()
    source_hashes = {
        key: _sha256_text(texts[key])
        for key in SOURCE_FILES
    }
    return {
        "schema_version": "d1_modular_prompt_manifest@1.0.0",
        "prompt_family": "direct_llm_modular_v1",
        "combination_order": list(COMBINATION_ORDER),
        "combination_semantics": {
            "E": "synthetic worked examples",
            "S": "semantic interpretation rules",
            "J": "output organization",
        },
        "source_files": {
            key: {
                "path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "sha256": source_hashes[key],
            }
            for key, path in SOURCE_FILES.items()
        },
        "combinations": {
            code: {
                "path": str(generated_path(code).relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "sha256": _sha256_text(prompt.to_markdown()),
                "composition_sha256": prompt.composition_sha256,
                "source_hashes": dict(prompt.source_hashes),
                "flags": dict(prompt.flags),
            }
            for code, prompt in prompts.items()
        },
    }


def write_generated(
    directory: Path = GENERATED_DIR, *, overwrite: bool = False
) -> dict:
    """Write the eight prompt files and their manifest deterministically."""
    prompts = render_all()
    directory.mkdir(parents=True, exist_ok=True)
    for code, prompt in prompts.items():
        path = generated_path(code, directory)
        if path.exists() and not overwrite:
            raise ModularPromptError(f"refusing to overwrite existing prompt: {path}")
    for code, prompt in prompts.items():
        generated_path(code, directory).write_text(
            prompt.to_markdown(), encoding="utf-8", newline="\n"
        )
    manifest = _manifest(prompts)
    generated_manifest_path(directory).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest
