# -*- coding: utf-8 -*-
"""Build and check the eight E/S/J modular Direct-LLM prompts offline.

This script never calls a model or the network.  ``--write`` renders the
source modules into standalone prompt files that ``bpc_hybrid.prompt_loader``
can load.  ``--check`` re-renders them in memory and verifies generated-file
bytes, minimum interface fields, module isolation, and loader compatibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.modular_prompt import (  # noqa: E402
    COMBINATION_ORDER,
    GENERATED_DIR,
    MODULE_DIR,
    ModularPromptError,
    generated_manifest_path,
    generated_path,
    load_module_texts,
    render_all,
    write_generated,
)

BASELINE_PROMPT = (
    ROOT / "prompts" / "sun_compat"
    / "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md"
)
REPORT_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_modular_prompt_v1_offline_check.json"
)

MODULE_MARKERS = {
    "S": "Semantic interpretation rules",
    "E": "Synthetic worked examples",
    "J": "Output organization",
}
COMMON_MARKERS = (
    "Common task and interface",
    "schema_version, sample_id, source_id, source_text, clauses, method, validation, unsupported_or_ambiguous",
    "clause_id, clause_span, modality, actors, actions, conditions, constraints, exceptions, actor_action_map, order_relations",
    '"name": "direct_llm"',
    "stage2_prediction.schema.json@1.0.0",
    "zero-based start and exclusive end",
    "IDs are unique within the complete record",
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _write_report(report: dict, path: Path = REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _check_prompt(code: str, prompt, loaded: object | None) -> dict:
    errors: list[str] = []
    system = prompt.system_prompt
    user = prompt.user_prompt_template

    for marker in COMMON_MARKERS:
        if marker not in system:
            errors.append(f"missing common marker: {marker}")
    for module in COMBINATION_ORDER:
        marker = MODULE_MARKERS[module]
        present = marker in (user if module == "E" else system)
        if prompt.flags[module] and not present:
            errors.append(f"enabled module {module} marker missing")
        if not prompt.flags[module] and present:
            errors.append(f"disabled module {module} marker still present")

    if "{few_shot_block}" in user:
        errors.append("dangling few_shot_block placeholder")
    if "use_E" in user and prompt.flags["E"] is False:
        errors.append("disabled E metadata leaked into user prompt")

    try:
        rendered_user = prompt.render_user("synthetic_sample", "A must act.")
    except Exception as exc:  # noqa: BLE001 - report the rendering failure.
        errors.append(f"user template failed to render: {type(exc).__name__}: {exc}")
        rendered_user = ""
    if "synthetic_sample" not in rendered_user:
        errors.append("sample_id missing after user render")
    if "A must act." not in rendered_user:
        errors.append("source_text missing after user render")

    loader_matches = False
    if loaded is not None:
        loader_matches = (
            getattr(loaded, "system_prompt", None) == system
            and getattr(loaded, "user_prompt_template", None) == user
        )
        if not loader_matches:
            errors.append("prompt_loader extraction differs from renderer")

    return {
        "flags": dict(prompt.flags),
        "system_chars": len(system),
        "user_chars": len(user),
        "total_chars": len(system) + len(user),
        "system_sha256": _sha256_text(system),
        "user_sha256": _sha256_text(user),
        "composition_sha256": prompt.composition_sha256,
        "loader_matches": loader_matches,
        "errors": errors,
    }


def check(*, require_generated: bool = True) -> dict:
    from bpc_hybrid.prompt_loader import load_prompt

    prompts = render_all()
    generated_files_match = True
    combination_results: dict[str, dict] = {}
    for code, prompt in prompts.items():
        path = generated_path(code)
        loader = None
        if path.is_file():
            expected = prompt.to_markdown()
            actual = path.read_text(encoding="utf-8")
            if actual != expected:
                generated_files_match = False
            prompts_root = ROOT / "prompts" / "sun_compat"
            loader_name = path.relative_to(prompts_root).with_suffix("").as_posix()
            loader = load_prompt(loader_name)
        elif require_generated:
            generated_files_match = False
        combination_results[code] = _check_prompt(code, prompt, loader)

    manifest_ok = True
    manifest_path = generated_manifest_path()
    if require_generated:
        if not manifest_path.is_file():
            manifest_ok = False
        else:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest_ok = (
                    manifest.get("prompt_family") == "direct_llm_modular_v1"
                    and set(manifest.get("combinations", {})) == set(prompts)
                )
            except (OSError, json.JSONDecodeError):
                manifest_ok = False

    all_errors = [
        f"{code}: {error}"
        for code, row in combination_results.items()
        for error in row["errors"]
    ]
    checks = {
        "eight_combinations_rendered": len(prompts) == 8,
        "all_required_interface_markers": not any(
            "missing common marker" in error for error in all_errors
        ),
        "disabled_module_text_absent": not any(
            "disabled module" in error for error in all_errors
        ),
        "loader_matches_renderer": all(
            row["loader_matches"] for row in combination_results.values()
        ) if require_generated else None,
        "generated_files_match_renderer": generated_files_match,
        "manifest_valid": manifest_ok,
        "user_template_renders": not any(
            "failed to render" in error for error in all_errors
        ),
        "no_dangling_template_placeholders": not any(
            "dangling" in error for error in all_errors
        ),
    }
    status = "pass" if all(value is True for value in checks.values()) else "fail"
    baseline_text = BASELINE_PROMPT.read_text(encoding="utf-8")
    module_texts = load_module_texts()
    return {
        "schema_version": "d1_modular_prompt_offline_check@1.0.0",
        "status": status,
        "combination_order": list(COMBINATION_ORDER),
        "module_lengths": {
            key: len(value) for key, value in module_texts.items()
        },
        "baseline_prompt": {
            "path": _relative(BASELINE_PROMPT),
            "chars": len(baseline_text),
            "sha256": _sha256_text(baseline_text),
        },
        "combinations": combination_results,
        "checks": checks,
        "errors": all_errors,
        "notes": [
            "Offline render only; no API/network call was made.",
            "Module lengths are Unicode character counts, not token counts.",
            "E remains partly visible as an output example; it does not own output-format rules but necessarily demonstrates a small amount of field shape.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write generated prompts and manifest")
    parser.add_argument("--check", action="store_true", help="check generated prompts and interface")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    if not args.write and not args.check:
        parser.error("choose --write and/or --check")
    try:
        if args.write:
            manifest = write_generated(overwrite=True)
            print(
                "wrote {} modular prompts to {}".format(
                    len(manifest["combinations"]), _relative(GENERATED_DIR)
                )
            )
        if args.check:
            report = check(require_generated=True)
            report_path = args.report if args.report else REPORT_PATH
            if not report_path.is_absolute():
                report_path = ROOT / report_path
            _write_report(report, report_path)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["status"] == "pass" else 1
        return 0
    except (ModularPromptError, OSError, ValueError) as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
