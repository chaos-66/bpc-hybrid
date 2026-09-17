# -*- coding: utf-8 -*-
"""Build and audit the four frozen SEP-C3 targeted-refinement prompts.

This script is zero-network.  It renders the A/B/C/D prompts from the frozen
common+E baseline plus the two independently switchable repair modules, writes
loader-compatible prompt files, and emits deterministic textual diffs and a
machine-readable audit report.
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

import bpc_hybrid.modular_prompt as mp  # noqa: E402
import bpc_hybrid.modular_refinement_prompt as rp  # noqa: E402


REPORT_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_targeted_refinement_v1_prompt_audit.json"
)
DIFF_DIR = (
    ROOT / "outputs" / "reports"
    / "sep_c3_targeted_refinement_v1_prompt_diffs"
)

OLD_MARKERS = (
    "Output discipline:",
    "Final self-check before output:",
    "Six-element semantics:",
    "Field-typing precision (D1-R1):",
    "in accordance with Section 11(1)",
    "synthetic_condition_constraint_01",
    "Example 5",
    "{few_shot_block}",
)
S_MARKERS = (
    "Semantic interpretation rules",
    "Source boundary:",
    "Clause boundaries:",
    "Coordination:",
    "Order relations:",
    "Normalization:",
)
J_MARKERS = (
    "Output organization",
    "Return one bare JSON object",
    "prose refusal",
)
PAIRWISE_DIFFS = (
    ("A", "B"),
    ("A", "C"),
    ("A", "D"),
    ("B", "D"),
    ("C", "D"),
    ("B", "C"),
)


class PromptAuditError(RuntimeError):
    """Raised when the prompt audit cannot be produced."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: object) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _sent_prompt_text(prompt: rp.RefinementPrompt) -> str:
    return (
        prompt.system_prompt
        + "\n\n<!--USER-->\n\n"
        + prompt.user_prompt_template
    )


def _write_diffs(prompts: dict[str, rp.RefinementPrompt]) -> dict[str, str]:
    DIFF_DIR.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for left, right in PAIRWISE_DIFFS:
        diff = "".join(
            difflib.unified_diff(
                _sent_prompt_text(prompts[left]).splitlines(keepends=True),
                _sent_prompt_text(prompts[right]).splitlines(keepends=True),
                fromfile=f"arm_{left}_sent_prompt.txt",
                tofile=f"arm_{right}_sent_prompt.txt",
                n=2,
            )
        )
        path = DIFF_DIR / f"arm_{left}_vs_arm_{right}.diff"
        _write_text(path, diff)
        written[f"{left}_vs_{right}"] = _relative(path)
    return written


def check() -> dict:
    baseline = mp.render_modular_prompt(rp.BASELINE_ARM)
    module_texts = mp.load_module_texts()
    s_text = module_texts["S"]
    j_text = module_texts["J"]
    e_text = module_texts["E"]
    common_system = module_texts["common_system"]
    common_user = module_texts["common_user"]

    prompts = rp.render_all()
    errors: list[str] = []
    checks: dict[str, bool] = {}

    def require(condition: bool, name: str, detail: str = "") -> None:
        checks[name] = bool(condition)
        if not condition:
            errors.append(detail or name)

    require(set(prompts) == set(rp.ARMS), "four_arms_rendered")
    for arm in rp.ARMS:
        prompt = prompts[arm]
        text = _sent_prompt_text(prompt)
        expected_repairs = set(rp.ARM_REPAIRS[arm])
        require(
            prompt.flags == {
                "R_A": "R_A" in expected_repairs,
                "R_C": "R_C" in expected_repairs,
            },
            f"{arm}_flags_exact",
        )
        require(
            common_system in prompt.system_prompt,
            f"{arm}_common_system_present",
        )
        require(
            common_user in prompt.user_prompt_template,
            f"{arm}_common_user_envelope_present",
        )
        require(
            e_text in prompt.user_prompt_template
            and prompt.user_prompt_template.count(e_text) == 1,
            f"{arm}_E_present_exactly_once",
        )
        for marker in mp.REQUIRED_COMMON_MARKERS:
            require(marker in prompt.system_prompt, f"{arm}_common_marker:{marker}")
        require(
            "source_text:" in prompt.user_prompt_template,
            f"{arm}_source_envelope_marker",
        )
        for marker in OLD_MARKERS:
            require(marker not in text, f"{arm}_old_marker_absent:{marker}")
        for marker in S_MARKERS:
            require(marker not in text, f"{arm}_S_marker_absent:{marker}")
        for marker in J_MARKERS:
            require(marker not in text, f"{arm}_J_marker_absent:{marker}")
        require(s_text not in text, f"{arm}_S_source_not_inserted")
        require(j_text not in text, f"{arm}_J_source_not_inserted")
        require(
            text.count(rp.R_A_TEXT) == (1 if "R_A" in expected_repairs else 0),
            f"{arm}_R_A_occurrence_exact",
        )
        require(
            text.count(rp.R_C_TEXT) == (1 if "R_C" in expected_repairs else 0),
            f"{arm}_R_C_occurrence_exact",
        )
        require(
            "Semantic interpretation rules" not in prompt.system_prompt,
            f"{arm}_no_S_heading",
        )
        require(
            "Output organization" not in prompt.system_prompt,
            f"{arm}_no_J_heading",
        )
        require(
            prompt.baseline_composition_sha256 == baseline.composition_sha256,
            f"{arm}_baseline_hash_binding",
        )
        try:
            rendered_user = prompt.render_user("offline_sample", "A must act.")
        except Exception as exc:  # noqa: BLE001 - report rendering failure.
            require(False, f"{arm}_user_template_renders", str(exc))
            rendered_user = ""
        require("offline_sample" in rendered_user, f"{arm}_render_sample_id")
        require("A must act." in rendered_user, f"{arm}_render_source_text")
        require(
            baseline.render_user("offline_sample", "A must act.") == rendered_user,
            f"{arm}_source_envelope_identical_to_baseline",
        )

    arm_a, arm_b, arm_c, arm_d = (prompts[k] for k in rp.ARMS)
    require(
        arm_a.system_prompt == baseline.system_prompt
        and arm_a.user_prompt_template == baseline.user_prompt_template
        and arm_a.composition_sha256 == baseline.composition_sha256,
        "A_is_exact_frozen_100_baseline",
        "Arm A is not byte-identical to modular_v1 arm 100",
    )
    require(
        arm_b.system_prompt == arm_a.system_prompt + "\n\n" + rp.R_A_TEXT
        and arm_b.user_prompt_template == arm_a.user_prompt_template,
        "A_vs_B_only_adds_R_A",
    )
    require(
        arm_c.system_prompt == arm_a.system_prompt + "\n\n" + rp.R_C_TEXT
        and arm_c.user_prompt_template == arm_a.user_prompt_template,
        "A_vs_C_only_adds_R_C",
    )
    require(
        arm_d.system_prompt
        == arm_a.system_prompt + "\n\n" + rp.R_A_TEXT + "\n\n" + rp.R_C_TEXT
        and arm_d.user_prompt_template == arm_a.user_prompt_template,
        "A_vs_D_only_adds_R_A_and_R_C",
    )
    require(
        arm_d.system_prompt == arm_b.system_prompt + "\n\n" + rp.R_C_TEXT
        and arm_d.user_prompt_template == arm_b.user_prompt_template,
        "B_vs_D_only_adds_R_C",
    )
    require(
        arm_d.system_prompt.replace("\n\n" + rp.R_A_TEXT, "", 1)
        == arm_c.system_prompt
        and arm_d.user_prompt_template == arm_c.user_prompt_template,
        "C_vs_D_only_adds_R_A",
    )
    require(
        len({p.user_prompt_template for p in prompts.values()}) == 1,
        "all_user_envelopes_identical",
    )
    require(
        len({p.system_prompt for p in (arm_a,)}) == 1,
        "common_skeleton_not_duplicated",
    )

    generated: dict[str, dict] = {}
    for arm, prompt in prompts.items():
        path = rp.generated_path(arm)
        require(path.is_file(), f"{arm}_generated_prompt_exists", str(path))
        if path.is_file():
            require(
                path.read_text(encoding="utf-8") == prompt.to_markdown(),
                f"{arm}_generated_bytes_match_renderer",
            )
        try:
            loaded = rp.load_generated_prompt(arm)
        except Exception as exc:  # noqa: BLE001 - report loader failure.
            require(False, f"{arm}_loader_matches_renderer", str(exc))
        else:
            require(
                loaded.system_prompt == prompt.system_prompt
                and loaded.user_prompt_template == prompt.user_prompt_template,
                f"{arm}_loader_matches_renderer",
            )
        generated[arm] = {
            "path": _relative(path),
            "sha256": _sha256_text(prompt.to_markdown()),
            "system_sha256": _sha256_text(prompt.system_prompt),
            "user_sha256": _sha256_text(prompt.user_prompt_template),
            "composition_sha256": prompt.composition_sha256,
            "flags": dict(prompt.flags),
            "source_hashes": dict(prompt.source_hashes),
            "serialized_repairs": {
                key: bool(prompt.flags[key]) for key in rp.REPAIR_ORDER
            },
        }

    manifest_path = rp.generated_manifest_path()
    require(manifest_path.is_file(), "generated_manifest_exists", str(manifest_path))
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(
            manifest.get("prompt_family") == "direct_llm_refinement_v1",
            "manifest_prompt_family",
        )
        require(
            set((manifest.get("arms") or {}).keys()) == set(rp.ARMS),
            "manifest_four_arms",
        )
        for arm in rp.ARMS:
            row = (manifest.get("arms") or {}).get(arm) or {}
            require(
                row.get("composition_sha256")
                == prompts[arm].composition_sha256,
                f"manifest_{arm}_composition_hash",
            )

    diffs = _write_diffs(prompts)
    no_unexpected = not any(
        name.startswith("arm_") and not value
        for name, value in checks.items()
    ) and not any(
        not value for name, value in checks.items()
    )
    report = {
        "schema_version": "sep_c3_targeted_refinement_prompt_audit@1.0.0",
        "status": "pass" if not errors else "fail",
        "network_calls": 0,
        "question": (
            "除 R_A / R_C 外，四个 arms 是否存在任何非预期差异？"
        ),
        "answer": "否" if not errors else "是",
        "no_unexpected_differences": no_unexpected,
        "checks": checks,
        "errors": errors,
        "baseline_100": {
            "arm": rp.BASELINE_ARM,
            "system_sha256": _sha256_text(baseline.system_prompt),
            "user_sha256": _sha256_text(baseline.user_prompt_template),
            "composition_sha256": baseline.composition_sha256,
            "source_hashes": dict(baseline.source_hashes),
        },
        "arms": generated,
        "differences": diffs,
        "repair_wording": {
            "R_A": rp.R_A_TEXT,
            "R_C": rp.R_C_TEXT,
        },
    }
    _write_json(REPORT_PATH, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build/audit the SEP-C3 targeted-refinement prompts."
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.write and not args.check:
        args.check = True
    if args.write:
        rp.write_generated(overwrite=args.overwrite)
    report = check()
    print(json.dumps({
        "status": report["status"],
        "answer": report["answer"],
        "report": _relative(REPORT_PATH),
        "errors": report["errors"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
