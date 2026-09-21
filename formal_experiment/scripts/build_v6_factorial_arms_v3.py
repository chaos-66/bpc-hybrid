# -*- coding: utf-8 -*-
"""Build the v6 prompt-family 2^3 factorial by direct chunk assembly.

The committed E/S/J prompt arms are cut into named, non-overlapping chunks at
boundaries that exist verbatim in the frozen v6 prompt.  Every factorial cell is
then assembled directly from those chunks; no diffing, splicing, or reverse
patching is used.

Factor semantics
----------------
E  semantic examples:
   E=1 -> six synthetic examples + example-oriented user envelope
   E=0 -> structural key/type template + template-oriented user envelope
S  semantic interpretation rules:
   S=1 -> "Six-element semantics" rules 9-19 and "Field-typing precision"
          rules 25-27
   S=0 -> both rule blocks removed
J  JSON/output contract:
   J=1 -> contract introduction + Output discipline rules 1-5 + JSON wording
   J=0 -> those removed, rule 24 reduced, user instruction rewritten

The four committed historical arms are reproduced for audit:
  111 and 110 byte-identically;
  101 and 011 are checked and their byte delta is recorded.  The direct
  assembly is allowed to canonicalise historical whitespace, provided the
  factor content is identical.

Usage
-----
    python scripts/build_v6_factorial_arms_v3.py --verify-only
    python scripts/build_v6_factorial_arms_v3.py
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V6 = ROOT / "prompts" / "sun_compat" / (
    "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md")
ABL = ROOT / "prompts" / "sun_compat" / "ablation_v2"
OUT_DIR = ROOT / "prompts" / "sun_compat" / "ablation_v2_factorial"

COMMITTED = {
    "111": V6,
    "011": ABL / "direct_llm_no_semantic_examples_prompt_v2.md",
    "101": ABL / "direct_llm_no_semantic_guidance_prompt_v2.md",
    "110": ABL / "direct_llm_no_explicit_json_contract_prompt_v2.md",
}
ALL_CELLS = ("000", "001", "010", "011", "100", "101", "110", "111")
NEW_CELLS = ("000", "001", "010", "100")

# ordered boundary list: (chunk name, start marker, end marker)
BOUNDARIES = [
    ("header", None, "## System Prompt"),
    ("system_open", "## System Prompt", "You MUST follow stage2_extraction"),
    ("J_rules", "You MUST follow stage2_extraction",
     "Input and inference boundary:"),
    ("base_rules_1", "Input and inference boundary:",
     "Six-element semantics:"),
    ("S1_rules", "Six-element semantics:",
     "Clause, coordination, and relation rules:"),
    ("base_rules_2", "Clause, coordination, and relation rules:",
     "Field-typing precision (D1-R1):"),
    ("S2_rules", "Field-typing precision (D1-R1):",
     "```\n\n## User Prompt Template"),
    ("system_close", "```\n\n## User Prompt Template",
     "## User Prompt Template"),
    ("user_envelope", "## User Prompt Template", "## Examples"),
    ("examples", "## Examples", "## Notes"),
    ("notes", "## Notes", None),
]


def _read(path: Path) -> str:
    return io.open(path, encoding="utf-8").read()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _norm_ws(text: str) -> str:
    return " ".join(text.split())


def cut_v6(text: str) -> dict[str, str]:
    """Cut the frozen v6 prompt into named, exactly tiling chunks."""
    chunks: dict[str, str] = {}
    pos = 0
    for name, start_marker, end_marker in BOUNDARIES:
        start = pos
        if start_marker is not None:
            found = text.find(start_marker, pos)
            if found < 0:
                raise SystemExit(f"[v6/{name}] start marker not found")
            start = found
        if end_marker is None:
            end = len(text)
        else:
            end = text.find(end_marker, start)
            if end < 0:
                raise SystemExit(f"[v6/{name}] end marker not found")
        chunks[name] = text[start:end]
        pos = end
    if pos != len(text):
        raise SystemExit(f"[v6] chunks stop at {pos}, text is {len(text)}")
    if "".join(chunks[n] for n, _, _ in BOUNDARIES) != text:
        raise SystemExit("[v6] chunk reassembly is not identity")
    return chunks


def _variant_parts(base: dict[str, str], a011: str, a110: str) -> dict[str, str]:
    """Recover factor-owned text from the committed arms, read-only."""
    # structural template used by every E=0 arm
    t_start = a011.find("Structural output template")
    t_end = a011.find("## User Prompt Template", t_start)
    if t_start < 0 or t_end < 0:
        raise SystemExit("cannot locate the E=0 structural template in 011")
    template_body = a011[t_start:t_end]

    # E=0/J=1 and E=0/J=0 user envelopes
    u_start = a011.find("## User Prompt Template")
    n_start = a011.find("## Notes", u_start)
    if u_start < 0 or n_start < 0:
        raise SystemExit("cannot locate the 011 user envelope")
    env_e0_j1 = a011[u_start:n_start]
    env_e0_j0 = env_e0_j1.replace(
        "Return the complete canonical JSON record.",
        "Return the extraction result.", 1)
    if env_e0_j0 == env_e0_j1:
        raise SystemExit("cannot rewrite the E=0/J=0 user instruction")

    # E=1/J=1 and E=1/J=0 user envelopes
    env_e1_j1 = base["user_envelope"]
    env_e1_j0 = env_e1_j1.replace(
        "Return the complete canonical JSON record.",
        "Return the extraction result.", 1)
    if env_e1_j0 == env_e1_j1:
        raise SystemExit("cannot rewrite the E=1/J=0 user instruction")

    # rule 24 wording used when the JSON contract is off
    i = a110.find("24. All spans are exact")
    k = a110.find("\n\n", i)
    if i < 0 or k < 0:
        raise SystemExit("cannot recover the J=0 rule 24 wording")
    rule24_off = a110[i:k]

    return {
        "template_e0_body": template_body,
        "user_envelope_e0_j1": env_e0_j1,
        "user_envelope_e0_j0": env_e0_j0,
        "user_envelope_e1_j1": env_e1_j1,
        "user_envelope_e1_j0": env_e1_j0,
        "examples_e1": base["examples"],
        "rule24_off": rule24_off,
    }


def _base_rules_1(base: dict[str, str], j: int) -> str:
    text = base["base_rules_1"]
    if not j:
        text = text.replace("Input and inference boundary:\n", "", 1)
    return text


def _base_rules_2(base: dict[str, str], variant: dict[str, str], s: int,
                  j: int) -> str:
    text = base["base_rules_2"]
    if not s:
        text = text.replace(
            "Clause, coordination, and relation rules:\n", "", 1)
    if not j:
        j0 = text.find("24. All required keys are present")
        k0 = text.find("\n\n", j0)
        if j0 < 0 or k0 < 0:
            raise SystemExit("cannot locate rule 24 in the J=1 chunk")
        text = text[:j0] + variant["rule24_off"] + text[k0:]
    return text


def assemble(e: int, s: int, j: int, base: dict[str, str],
             variant: dict[str, str]) -> str:
    """Assemble one factorial arm directly from named chunks."""
    parts: list[str] = [
        base["header"],
        base["system_open"],
        base["J_rules"] if j else "",
        _base_rules_1(base, j),
        base["S1_rules"] if s else "",
        _base_rules_2(base, variant, s, j),
    ]

    if s:
        parts.append(base["S2_rules"])
        if e:
            parts.append(base["system_close"])
        else:
            # one blank line between rule 27 and the structural template
            parts.append("\n")
            parts.append(variant["template_e0_body"])
    else:
        if e:
            # preserve the committed 101 separator layout byte-identically
            parts.append("\n")
            parts.append(base["system_close"])
        else:
            # base_rules_2 already ends with a blank line
            parts.append(variant["template_e0_body"])

    if e:
        env = (variant["user_envelope_e1_j1"] if j
               else variant["user_envelope_e1_j0"])
        parts.append(env)
        parts.append(variant["examples_e1"])
    else:
        env = (variant["user_envelope_e0_j1"] if j
               else variant["user_envelope_e0_j0"])
        parts.append(env)

    parts.append(base["notes"])
    return "".join(parts)


def _chunk_plan(e: int, s: int, j: int) -> dict[str, list[str]]:
    included = ["header", "system_open", "base_rules_1", "base_rules_2",
                "notes"]
    excluded: list[str] = []
    if j:
        included.append("J_rules")
    else:
        excluded.append("J_rules")
    if s:
        included += ["S1_rules", "S2_rules"]
    else:
        excluded += ["S1_rules", "S2_rules"]
    if e:
        included += ["user_envelope_e1", "examples_e1", "system_close"]
        excluded += ["user_envelope_e0", "template_e0"]
    else:
        included += ["user_envelope_e0", "template_e0"]
        excluded += ["user_envelope_e1", "examples_e1", "system_close"]
    return {"included_chunks": included, "excluded_chunks": excluded}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    texts = {k: _read(p) for k, p in COMMITTED.items()}
    for key in sorted(texts):
        print(f"  committed {key}: chars={len(texts[key]):>6} "
              f"sha256={_sha(texts[key])[:16]}")

    base = cut_v6(texts["111"])
    variant = _variant_parts(base, texts["011"], texts["110"])

    built: dict[str, str] = {}
    for key in ALL_CELLS:
        e, s, j = (int(c) for c in key)
        built[key] = assemble(e, s, j, base, variant)

    print("\nHistorical arm reconstruction:")
    historical: dict[str, Any] = {}
    historical_ok = True
    for key in ("111", "110", "101", "011"):
        got = built[key]
        want = texts[key]
        byte_identical = got == want
        normalized_equivalent = _norm_ws(got) == _norm_ws(want)
        byte_delta = len(got) - len(want)
        status = ("byte-identical" if byte_identical
                  else "normalized-equivalent" if normalized_equivalent
                  else "MISMATCH")
        historical[key] = {
            "source_prompt": str(COMMITTED[key].relative_to(ROOT)).replace(
                "\\", "/"),
            "source_sha256": _sha(want),
            "byte_identical": byte_identical,
            "byte_delta": byte_delta,
            "normalized_equivalent": normalized_equivalent,
            "status": status,
        }
        print(f"  {key}: built={len(got):>6} source={len(want):>6} "
              f"delta={byte_delta:+d} -> {status}")
        if not normalized_equivalent:
            historical_ok = False

    if not historical_ok:
        print("\nGATE1 FAILED: historical chunk content mismatch. "
              "Nothing written.")
        return 1
    print("\nGATE1 PASSED: all historical chunks are content-equivalent; "
          "byte deltas recorded.")

    print("\nFactor-semantics gate:")
    sem_ok = True
    for key in ALL_CELLS:
        e, s, j = (int(c) for c in key)
        text = built[key]
        problems: list[str] = []
        if e == 0:
            if "Structural output template" not in text:
                problems.append("E=0 lacks structural template")
            if "## Examples" in text:
                problems.append("E=0 contains '## Examples'")
        else:
            if "## Examples" not in text:
                problems.append("E=1 lacks '## Examples'")
            if "Structural output template" in text:
                problems.append("E=1 contains structural template")
        for marker in ("Six-element semantics:",
                       "Field-typing precision (D1-R1):"):
            if s == 0 and marker in text:
                problems.append(f"S=0 contains {marker!r}")
            if s == 1 and marker not in text:
                problems.append(f"S=1 lacks {marker!r}")
        for marker in ("You MUST follow stage2_extraction", "Output discipline:"):
            if j == 0 and marker in text:
                problems.append(f"J=0 contains {marker!r}")
            if j == 1 and marker not in text:
                problems.append(f"J=1 lacks {marker!r}")
        if problems:
            sem_ok = False
        print(f"  {key}: E={e} S={s} J={j} -> "
              f"{'PASS' if not problems else 'FAIL'}")
        for problem in problems:
            print(f"        {problem}")
    if not sem_ok:
        print("\nGATE2 FAILED. Nothing written.")
        return 1
    print("GATE2 PASSED.")

    hashes = {key: _sha(text) for key, text in built.items()}
    if len(set(hashes.values())) != len(hashes):
        print("GATE3 FAILED: duplicate prompt hashes.")
        return 1
    print("GATE3 PASSED: eight distinct arm hashes.")

    if args.verify_only:
        print("\n--verify-only: no files written.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema_version": "v6_factorial_arms@3.0.0",
        "builder": "scripts/build_v6_factorial_arms_v3.py",
        "status": "generated_not_executed",
        "design": "2^3 factorial over E x S x J by direct chunk assembly",
        "method": ("cut frozen v6 and the committed arms into named chunks; "
                   "emit each cell directly from its required chunks"),
        "source_prompt": str(V6.relative_to(ROOT)).replace("\\", "/"),
        "source_prompt_sha256": _sha(texts["111"]),
        "factor_meaning": {
            "E": "semantic examples vs structural key/type template",
            "S": "semantic interpretation rules 9-19 and 25-27",
            "J": "JSON/output contract intro + rules 1-5",
        },
        "historical_equivalence": {
            "111": "byte-identical",
            "110": "byte-identical",
            "101": historical["101"]["status"],
            "011": historical["011"]["status"],
        },
        "gates": {
            "gate1_historical_chunk_content": True,
            "gate2_factor_semantics": True,
            "gate3_eight_distinct_hashes": True,
        },
        "arms": {},
    }

    for key in ALL_CELLS:
        e, s, j = (int(c) for c in key)
        name = f"direct_llm_v6_{key}.md"
        path = OUT_DIR / name
        path.write_text(built[key], encoding="utf-8", newline="")
        plan = _chunk_plan(e, s, j)
        entry: dict[str, Any] = {
            "arm": key,
            "factors": {"E": e, "S": s, "J": j},
            "included_chunks": plan["included_chunks"],
            "excluded_chunks": plan["excluded_chunks"],
            "prompt_file": (
                f"prompts/sun_compat/ablation_v2_factorial/{name}"),
            "prompt_sha256": hashes[key],
            "chars": len(built[key]),
            "kind": "new" if key in NEW_CELLS else "historical_anchor",
        }
        if key in historical:
            entry["historical_reference"] = historical[key]
        manifest["arms"][key] = entry
        print(f"  wrote {name}  sha256={hashes[key][:16]}")

    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n", encoding="utf-8", newline="\n")
    print(f"\nwrote {manifest_path}")
    print("factorial manifest:")
    for key in ALL_CELLS:
        a = manifest["arms"][key]
        f = a["factors"]
        print(f"  {key}: E={f['E']} S={f['S']} J={f['J']} "
              f"kind={a['kind']:<17} chars={a['chars']:>6} "
              f"sha256={a['prompt_sha256'][:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
