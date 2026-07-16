"""Offline prompt loader and renderer (Wave 1.1 §3).

Prompts live as Markdown files under ``prompts/sun_compat/`` and are
the **runtime source of truth** — no hardcoded ``SYSTEM_PROMPT``
constants in runner scripts. This module loads the prompt file,
extracts the system + user + few-shot sections, and records the
prompt's SHA-256 so a runner manifest can verify which prompt text
actually drove a real call.

Sampling parameters (temperature, top_p, seed, max_tokens) are **not**
part of the prompt. They are controlled by ``bpc_hybrid.llm_config``
and recorded in the manifest. The prompt file may document the
intended sampling policy in plain text for human readers but the
runtime never trusts it.

No network. No ``.env``. No API keys. No LLM call.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = PROJECT_ROOT / "prompts" / "sun_compat"


@dataclass
class LoadedPrompt:
    """Result of loading a prompt file.

    Attributes
    ----------
    name : str
        File stem (e.g. ``"direct_llm_sun_record_prompt"``).
    path : Path
        Absolute path to the source file.
    sha256 : str
        Hex SHA-256 of the file contents.
    system_prompt : str
        Text inside the first `````text ... ``` `` block whose first
        line starts with ``## System Prompt``. Empty if absent.
    user_prompt_template : str
        Text inside the `````text ... ``` `` block whose first line
        starts with ``## User Prompt Template``. Empty if absent.
    few_shot_examples : list[dict]
        JSON examples in fenced code blocks marked
        `````json ... ``` `` under a "Examples" section. Each example
        is a dict with ``input``, ``output``, and the original text
        ``raw``. The list is empty if no examples are found.
    raw_text : str
        Full original file text.
    extras : dict
        Free-form key/value pairs parsed from ``<!-- key: value -->``
        comments. Used to attach a ``sampling_policy`` description
        that documents the intended temperature / top_p / seed.
    """

    name: str
    path: Path
    sha256: str
    system_prompt: str = ""
    user_prompt_template: str = ""
    few_shot_examples: list[dict] = field(default_factory=list)
    raw_text: str = ""
    extras: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "sha256": self.sha256,
            "system_prompt": self.system_prompt,
            "user_prompt_template": self.user_prompt_template,
            "few_shot_example_count": len(self.few_shot_examples),
            "extras": dict(self.extras),
        }


# ---------------------------------------------------------------------------
# Block parsing helpers
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^```([A-Za-z0-9_+\-]*)\s*$", re.MULTILINE)
_HTML_COMMENT_RE = re.compile(r"<!--\s*(.*?)\s*-->", re.DOTALL)


def _extract_blocks(text: str) -> list[tuple[str, list[str]]]:
    """Return ``[(language, [line, ...]), ...]`` for every fenced code block.

    Plain ``````` `` and ```````text `` are tracked; ```````json `` is
    tracked separately so the caller can parse examples.
    """
    blocks: list[tuple[str, list[str]]] = []
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        m = _FENCE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        lang = m.group(1) or ""
        i += 1
        body: list[str] = []
        while i < n and not _FENCE_RE.match(lines[i]):
            body.append(lines[i])
            i += 1
        # skip closing fence
        if i < n:
            i += 1
        blocks.append((lang, body))
    return blocks


def _extract_extras(text: str) -> dict[str, str]:
    """Parse ``<!-- key: value -->`` style comments.

    Multi-line comments are allowed (one key per comment). Values are
    stripped of leading/trailing whitespace. Comment keys that
    already exist are not overwritten (first wins).
    """
    extras: dict[str, str] = {}
    for match in _HTML_COMMENT_RE.finditer(text):
        body = match.group(1)
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if key and key not in extras:
                extras[key] = value
    return extras


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------


def _find_section(blocks: list[tuple[str, list[str]]], header: str) -> tuple[str, list[str]] | None:
    """Find the first code block following a ``## <header>`` heading.

    Returns ``(language, body_lines)`` or ``None`` if not found.
    """
    next_block_idx = 0
    pending_header: str | None = None
    in_target = False
    for lang, body in blocks:
        if pending_header is not None:
            yield_lang, yield_body = lang, body
            pending_header = None
            if in_target:
                return (yield_lang, yield_body)
            continue
        # check first line of the block for a header
        if body and body[0].lstrip().startswith("## "):
            heading = body[0].lstrip()[3:].strip()
            if heading.lower() == header.lower():
                in_target = True
                # body after the heading line
                rest = body[1:]
                # find the next code block
                return (lang, rest)
    return None


def _find_section_after_heading(text: str, header: str) -> tuple[str, list[str]] | None:
    """Walk the document and return the first fenced block after ``## <header>``.

    The block may immediately follow the heading (with a blank line)
    or be preceded by markdown text. We return the closest subsequent
    fenced block.
    """
    lines = text.splitlines()
    n = len(lines)
    header_re = re.compile(r"^##\s+" + re.escape(header) + r"\s*$", re.IGNORECASE)
    for i, line in enumerate(lines):
        if not header_re.match(line):
            continue
        # find the next fence
        j = i + 1
        while j < n and not _FENCE_RE.match(lines[j]):
            j += 1
        if j >= n:
            return None
        lang = _FENCE_RE.match(lines[j]).group(1) or ""
        # collect body
        body: list[str] = []
        j += 1
        while j < n and not _FENCE_RE.match(lines[j]):
            body.append(lines[j])
            j += 1
        return (lang, body)
    return None


# ---------------------------------------------------------------------------
# Few-shot extraction
# ---------------------------------------------------------------------------


def _extract_few_shot(text: str) -> list[dict]:
    """Find ``## Examples`` (or ``## Few-shot Examples``) section, parse JSON examples.

    Each example is expected to look like::

        Example N — <description>:
        Input: "<text>"
        Output:
        ```json
        { ... }
        ```

    We extract a structured ``{"description", "input", "output"}`` triple
    for each example. Output is parsed as JSON when possible.
    """
    examples: list[dict] = []
    lines = text.splitlines()
    n = len(lines)
    # find the Examples section
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+(Examples|Few-shot Examples|Few-shot examples)\s*$", line, re.IGNORECASE):
            start = i
            break
    if start is None:
        return examples

    # find fenced json blocks
    blocks: list[tuple[str, int, int]] = []
    for k in range(start, n):
        m = _FENCE_RE.match(lines[k])
        if not m:
            continue
        lang = m.group(1) or ""
        if lang.lower() != "json":
            continue
        body_start = k + 1
        body_end = body_start
        while body_end < n and not _FENCE_RE.match(lines[body_end]):
            body_end += 1
        blocks.append((lang, body_start, body_end))
        k = body_end  # skip past this block

    for (lang, bs, be) in blocks:
        body = "\n".join(lines[bs:be])
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            # Not valid JSON; skip — a malformed example should not
            # bring down the loader, but the runner manifest will
            # record the parse failure when it tries to use it.
            continue
        # Look for the surrounding description and input (best effort)
        # Walk backward to find the nearest "Example N" / "Input:" header
        descr = ""
        inp = ""
        for j in range(bs - 1, max(start, bs - 30), -1):
            text_above = lines[j].strip()
            if text_above.startswith("Input:"):
                inp = text_above[len("Input:"):].strip()
            if text_above.startswith("Example"):
                descr = text_above
                break
        examples.append({
            "description": descr,
            "input": inp,
            "output": parsed,
            "raw": body,
        })
    return examples


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------


def load_prompt(name: str) -> LoadedPrompt:
    """Load a prompt file by stem name.

    Looks under ``prompts/sun_compat/<name>.md``. Raises ``FileNotFoundError``
    if the file does not exist. The SHA-256 is computed over the raw
    file bytes (not the parsed view), so any whitespace change in the
    source file shows up as a different hash.
    """
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    system_section = _find_section_after_heading(raw, "System Prompt")
    user_section = _find_section_after_heading(raw, "User Prompt Template")
    examples = _extract_few_shot(raw)
    extras = _extract_extras(raw)

    return LoadedPrompt(
        name=path.stem,
        path=path,
        sha256=h,
        system_prompt="\n".join(system_section[1]) if system_section else "",
        user_prompt_template="\n".join(user_section[1]) if user_section else "",
        few_shot_examples=examples,
        raw_text=raw,
        extras=extras,
    )


def render_user_prompt(template: str, **kwargs: Any) -> str:
    """Render a user-prompt template by ``str.format`` substitution.

    Raises ``KeyError`` for missing keys so the runner fails loudly
    rather than emitting a half-rendered prompt.
    """
    return template.format(**kwargs)


# ---------------------------------------------------------------------------
# Manifest helper
# ---------------------------------------------------------------------------


def build_manifest_entry(prompt: LoadedPrompt, *, role: str = "primary") -> dict[str, Any]:
    """Return a manifest entry recording which prompt was used.

    The runner copies this into the prediction manifest so an external
    reader can verify the exact prompt text that drove a call.
    """
    return {
        "role": role,
        "name": prompt.name,
        "path": str(prompt.path),
        "sha256": prompt.sha256,
        "sampling_policy": prompt.extras.get("sampling_policy", ""),
    }
