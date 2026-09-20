# -*- coding: utf-8 -*-
"""Build and audit the non-active SEP-C3 definition-refinement candidate.

This script is zero-network.  It writes candidate-only prompt artifacts,
the E4 v2 record, and a precise prompt-diff report.  It never writes the
active A/B/C/D prompts, the active prompt manifest, the active registry,
Gold, or predictions.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import bpc_hybrid.modular_refinement_prompt as rp  # noqa: E402
import bpc_hybrid.sep_c3_definition_refinement_prompt as dr  # noqa: E402


REPORTS_DIR = ROOT / "outputs" / "reports"
E4_V2_PATH = REPORTS_DIR / "sep_c3_definition_candidate_E4_v2.json"
DIFF_PATH = REPORTS_DIR / "sep_c3_definition_candidate_prompt_diff_v1.md"
AUDIT_PATH = REPORTS_DIR / "sep_c3_definition_candidate_prompt_audit_v1.json"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sent_text(prompt) -> str:
    return (
        prompt.system_prompt
        + "\n\n<!--USER-->\n\n"
        + prompt.user_prompt_template
    )


def _unified(left: str, right: str, left_name: str, right_name: str) -> str:
    return "".join(
        difflib.unified_diff(
            left.splitlines(keepends=True),
            right.splitlines(keepends=True),
            fromfile=left_name,
            tofile=right_name,
            n=3,
        )
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: object) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def build_audit() -> dict:
    active_a = rp.render_refinement_prompt("A")
    active_b = rp.render_refinement_prompt("B")
    active_c = rp.render_refinement_prompt("C")
    active_d = rp.render_refinement_prompt("D")
    base = dr.render_definition_prompt("BASE")
    rdef = dr.render_definition_prompt("R_DEF")

    active_sent = _sent_text(active_a)
    base_sent = _sent_text(base)
    rdef_sent = _sent_text(rdef)

    old_e4_present_active = dr.OLD_E4_BLOCK in active_sent
    old_e4_present_base = dr.OLD_E4_BLOCK in base_sent
    new_e4_count_base = base_sent.count(dr.NEW_E4_BLOCK)
    rdef_count = rdef.system_prompt.count(dr.R_DEF_TEXT)
    forbidden = (
        "shall be deemed => definition",
        "shall apply => definition",
        "shall be treated => definition",
        "shall be deemed -> definition",
        "shall apply -> definition",
        "shall be treated -> definition",
    )
    shortcuts_present = [item for item in forbidden if item in rdef.system_prompt]
    active_unchanged_expected = {
        "A": {
            "system_sha256": _sha256_text(active_a.system_prompt),
            "user_sha256": _sha256_text(active_a.user_prompt_template),
            "composition_sha256": active_a.composition_sha256,
            "markdown_sha256": _sha256_text(active_a.to_markdown()),
        },
        "B": {
            "system_sha256": _sha256_text(active_b.system_prompt),
            "user_sha256": _sha256_text(active_b.user_prompt_template),
            "composition_sha256": active_b.composition_sha256,
            "markdown_sha256": _sha256_text(active_b.to_markdown()),
        },
        "C": {
            "system_sha256": _sha256_text(active_c.system_prompt),
            "user_sha256": _sha256_text(active_c.user_prompt_template),
            "composition_sha256": active_c.composition_sha256,
            "markdown_sha256": _sha256_text(active_c.to_markdown()),
        },
        "D": {
            "system_sha256": _sha256_text(active_d.system_prompt),
            "user_sha256": _sha256_text(active_d.user_prompt_template),
            "composition_sha256": active_d.composition_sha256,
            "markdown_sha256": _sha256_text(active_d.to_markdown()),
        },
    }
    checks = {
        "active_E4_removed_from_candidate": (
            old_e4_present_active and not old_e4_present_base
        ),
        "candidate_E4_v2_exactly_once": new_e4_count_base == 1,
        "R_DEF_exactly_once_in_R_DEF_arm": rdef_count == 1,
        "R_DEF_absent_from_BASE": dr.R_DEF_TEXT not in base.system_prompt,
        "lexical_shortcuts_absent_from_R_DEF": not shortcuts_present,
        "common_system_identical_to_active_A": (
            base.system_prompt == active_a.system_prompt
        ),
        "R_DEF_arm_is_base_plus_R_DEF": (
            rdef.system_prompt == base.system_prompt + "\n\n" + dr.R_DEF_TEXT
            and rdef.user_prompt_template == base.user_prompt_template
        ),
    }
    compatibility = {}
    for arm in dr.COMPATIBILITY_ARMS:
        prompt = dr.render_definition_prompt(arm)
        old_arm = dr.COMPAT_OLD_ARM[arm]
        old = rp.render_refinement_prompt(old_arm)
        compatibility[arm] = {
            "old_arm_equivalence": old_arm,
            "system_is_old_arm_plus_R_DEF": (
                prompt.system_prompt == old.system_prompt + "\n\n" + dr.R_DEF_TEXT
            ),
            "user_is_candidate_E4_v2": (
                prompt.user_prompt_template == base.user_prompt_template
            ),
            "system_sha256": _sha256_text(prompt.system_prompt),
            "user_sha256": _sha256_text(prompt.user_prompt_template),
            "composition_sha256": prompt.composition_sha256,
            "markdown_sha256": _sha256_text(prompt.to_markdown()),
        }
    return {
        "schema_version": "sep_c3_definition_candidate_prompt_audit@1.0.0",
        "status": "pass" if all(checks.values()) and all(
            all(v for k, v in row.items() if k != "old_arm_equivalence")
            for row in compatibility.values()
        ) else "fail",
        "api_calls": 0,
        "active_prompt_family": "direct_llm_refinement_v1",
        "candidate_family": "direct_llm_definition_refinement_candidate_v1",
        "checks": checks,
        "lexical_shortcuts_present": shortcuts_present,
        "active_prompt_hashes": active_unchanged_expected,
        "candidate_hashes": {
            "BASE": {
                "system_sha256": _sha256_text(base.system_prompt),
                "user_sha256": _sha256_text(base.user_prompt_template),
                "composition_sha256": base.composition_sha256,
                "markdown_sha256": _sha256_text(base.to_markdown()),
            },
            "R_DEF": {
                "system_sha256": _sha256_text(rdef.system_prompt),
                "user_sha256": _sha256_text(rdef.user_prompt_template),
                "composition_sha256": rdef.composition_sha256,
                "markdown_sha256": _sha256_text(rdef.to_markdown()),
            },
        },
        "compatibility": compatibility,
    }


def build_diff_report(audit: dict) -> str:
    active_a = rp.render_refinement_prompt("A")
    base = dr.render_definition_prompt("BASE")
    rdef = dr.render_definition_prompt("R_DEF")
    active_to_base = _unified(
        _sent_text(active_a),
        _sent_text(base),
        "active_arm_A_sent_prompt.txt",
        "candidate_BASE_sent_prompt.txt",
    )
    base_to_rdef = _unified(
        _sent_text(base),
        _sent_text(rdef),
        "candidate_BASE_sent_prompt.txt",
        "candidate_R_DEF_sent_prompt.txt",
    )
    lines = [
        "# SEP-C3 Definition Candidate Prompt Diff v1",
        "",
        "- Status: **candidate-only; not applied**",
        "- New API / LLM calls: **0**",
        "- Active prompt changes: **none**",
        "- Gold changes: **none**",
        "- Prediction changes: **none**",
        "",
        "The candidate is assembled by the existing modular/refinement mechanism:",
        "frozen common system + frozen existing E examples with only E4 replaced,",
        "plus the approved R_DEF paragraph(s) appended as an independent system",
        "paragraph.  S, J, R_A, and R_C are not activated in the candidate arms.",
        "",
        "## 1. Active arm A vs candidate BASE",
        "",
        "This diff should contain only the approved synthetic E4 replacement.",
        "",
        "```diff",
        active_to_base.rstrip("\n"),
        "```",
        "",
        "## 2. Candidate BASE vs candidate BASE + R_DEF",
        "",
        "This diff should contain only the approved definition guidance paragraph(s).",
        "",
        "```diff",
        base_to_rdef.rstrip("\n"),
        "```",
        "",
        "## 3. Candidate hashes",
        "",
        "| Render arm | System SHA-256 | User SHA-256 | Composition SHA-256 |",
        "|---|---|---|---|",
        f"| BASE | `{audit['candidate_hashes']['BASE']['system_sha256']}` | `{audit['candidate_hashes']['BASE']['user_sha256']}` | `{audit['candidate_hashes']['BASE']['composition_sha256']}` |",
        f"| R_DEF | `{audit['candidate_hashes']['R_DEF']['system_sha256']}` | `{audit['candidate_hashes']['R_DEF']['user_sha256']}` | `{audit['candidate_hashes']['R_DEF']['composition_sha256']}` |",
        "",
        "## 4. Compatibility inspection only",
        "",
        "These renderings are offline only and are not candidate arms for activation.",
        "",
        "| Compatibility arm | Old arm | System is old arm + R_DEF | User is candidate E4 v2 |",
        "|---|---|---|---|",
    ]
    for arm, row in audit["compatibility"].items():
        lines.append(
            f"| {arm} | {row['old_arm_equivalence']} | "
            f"{row['system_is_old_arm_plus_R_DEF']} | "
            f"{row['user_is_candidate_E4_v2']} |"
        )
    lines += [
        "",
        "## 5. Scope guard",
        "",
        "- No `R_A` or `R_C` text was modified.",
        "- No `S8` text was copied, reactivated, or modified.",
        "- `semantic_rules_S.md` was not edited.",
        "- `common_system.md`, `user_envelope.md`, and `output_format_J.md` were not edited.",
        "- The active prompt files and active prompt manifest were not overwritten.",
        "- No condition, constraint, or exception guidance was added or changed.",
        "- No model was invoked and no prediction was produced by this candidate.",
    ]
    return "\n".join(lines) + "\n"


def build(*, write: bool = True, overwrite: bool = True) -> dict:
    if write:
        dr.write_generated(overwrite=overwrite)
    else:
        dr.ensure_source_files(overwrite=False)
        for arm in dr.ALL_ARMS:
            path = dr.generated_path(arm)
            if not path.is_file():
                raise RuntimeError(f"missing generated candidate prompt: {path}")
            if path.read_text(encoding="utf-8") != dr.render_definition_prompt(
                arm
            ).to_markdown():
                raise RuntimeError(
                    f"generated candidate prompt differs from renderer: {path}"
                )
    audit = build_audit()
    if audit["status"] != "pass":
        raise RuntimeError(f"candidate audit failed: {audit}")
    if write:
        _write_json(E4_V2_PATH, dr.e4_v2_candidate_record())
        _write_text(DIFF_PATH, build_diff_report(audit))
        _write_json(AUDIT_PATH, audit)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        audit = build(write=False, overwrite=False)
        print(json.dumps(audit, ensure_ascii=False, indent=2))
        return 0 if audit["status"] == "pass" else 1
    audit = build(write=True, overwrite=args.overwrite)
    print(
        json.dumps(
            {
                "status": audit["status"],
                "api_calls": 0,
                "e4_v2_path": str(E4_V2_PATH.relative_to(ROOT)).replace("\\", "/"),
                "diff_path": str(DIFF_PATH.relative_to(ROOT)).replace("\\", "/"),
                "audit_path": str(AUDIT_PATH.relative_to(ROOT)).replace("\\", "/"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())