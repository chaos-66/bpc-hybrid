"""Offline integrity check for the Sol-candidate semantics pilot prompt examples.

Verifies that every few-shot example embedded in
``direct_llm_sun_record_prompt_solcand_pilot_2026_08_07.md`` is:
  - parseable by the prompt loader;
  - schema-valid against stage2_prediction.schema.json@1.0.0 (when
    jsonschema is available; otherwise the structural fallback);
  - span-consistent: every text equals source_text[start:end] and every
    child span lies inside its clause_span;
  - synthetically declared (no real EStG sample_ids).

Zero LLM/API/network calls; read-only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from bpc_hybrid.stage2_canonical import validate_canonical  # noqa: E402

PROMPT_NAME = "direct_llm_sun_record_prompt_solcand_pilot_2026_08_07"
FORBIDDEN_PREFIXES = ("estg_", "synthetic_")  # real sample_ids start with estg_


def _check_span(span: dict, source_text: str, label: str, errors: list[str]) -> None:
    text = span.get("text")
    start = span.get("start")
    end = span.get("end")
    if not isinstance(text, str) or not isinstance(start, int) or not isinstance(end, int):
        errors.append(f"{label}: missing text/start/end")
        return
    if not (0 <= start < end <= len(source_text)):
        errors.append(f"{label}: bounds [{start},{end}) outside source len {len(source_text)}")
        return
    if source_text[start:end] != text:
        errors.append(f"{label}: text {text!r} != source[{start}:{end}]={source_text[start:end]!r}")
        return


def _check_clause(clause: dict, source_text: str, errors: list[str]) -> None:
    clause_span = clause.get("clause_span")
    if not isinstance(clause_span, dict):
        errors.append("clause: missing clause_span")
        return
    cs_text = clause_span.get("text")
    cs_start = clause_span.get("start")
    cs_end = clause_span.get("end")
    if not (isinstance(cs_text, str) and isinstance(cs_start, int) and isinstance(cs_end, int)):
        errors.append("clause_span: missing text/start/end")
        return
    if not (0 <= cs_start < cs_end <= len(source_text)):
        errors.append(f"clause_span: bounds outside source")
        return
    if source_text[cs_start:cs_end] != cs_text:
        errors.append("clause_span: text != source[start:end]")
        return

    modality = clause.get("modality") or {}
    for ei, ev in enumerate(modality.get("evidence") or []):
        if isinstance(ev, dict):
            _check_span(ev, source_text, f"modality.evidence[{ei}]", errors)
    for field in ("actors", "actions", "conditions", "constraints", "exceptions"):
        for si, span in enumerate(clause.get(field) or []):
            if isinstance(span, dict):
                _check_span(span, source_text, f"{field}[{si}]", errors)
                span_text = span.get("text")
                if isinstance(span_text, str) and span_text not in cs_text:
                    errors.append(f"{field}[{si}]: span text not inside clause_span text")


def main() -> int:
    prompt = load_prompt(PROMPT_NAME)
    examples = prompt.few_shot_examples
    print(f"prompt: {prompt.name}")
    print(f"sha256: {prompt.sha256}")
    print(f"examples parsed: {len(examples)}")
    if not examples:
        print("FAIL: no few-shot examples found")
        return 2

    errors: list[str] = []
    for index, ex in enumerate(examples):
        raw_input = ex.get("input")
        output = ex.get("output")
        if not isinstance(raw_input, str) or not raw_input:
            errors.append(f"example {index}: missing input text")
            continue
        # The loader keeps the literal "Input:" line content, which includes
        # the surrounding double quotes used in the prompt file.  Strip a
        # balanced pair of wrapping double quotes to recover the actual
        # source text the model sees (same convention as the v6 prompt).
        source_text = raw_input
        if len(source_text) >= 2 and source_text[0] == '"' and source_text[-1] == '"':
            source_text = source_text[1:-1]
        if not isinstance(output, dict):
            errors.append(f"example {index}: output not parsed as dict")
            continue
        sid = output.get("sample_id")
        if not isinstance(sid, str) or not sid.startswith("synthetic_"):
            errors.append(f"example {index}: sample_id must be synthetic_*, got {sid!r}")
        for clause in output.get("clauses") or []:
            if isinstance(clause, dict):
                _check_clause(clause, source_text, errors)
        report = validate_canonical(dict(output))
        if not (report.schema_valid and report.cross_field_valid):
            errors.append(f"example {index}: canonical invalid: {report.errors[:3]}")

    if errors:
        print("FAIL:")
        for err in errors[:20]:
            print("  -", err)
        return 1
    print("OK: all examples synthetic, span-consistent, and canonical-valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
