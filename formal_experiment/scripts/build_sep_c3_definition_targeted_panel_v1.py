# -*- coding: utf-8 -*-
"""Build and freeze the deterministic SEP-C3 definition targeted panel.

The panel is constructed only from frozen EStG-150 Gold and frozen input.  It
is a targeted prompt-development panel, not a new formal test set.  This script
is offline only and performs no network/API call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import bpc_hybrid.modular_refinement_prompt as rp  # noqa: E402
import bpc_hybrid.sep_c3_definition_refinement_prompt as dr  # noqa: E402


GOLD_PATH = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
INPUT_PATH = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
ACTIVE_REGISTRY_PATH = ROOT / "configs" / "models" / "estg150_d1_active_registry_v1.json"
ACTIVE_PROMPT_MANIFEST_PATH = (
    ROOT / "prompts" / "sun_compat" / "modular_refinement_v1" / "generated"
    / "manifest.json"
)
PANEL_PATH = ROOT / "configs" / "sep_c3_definition_targeted_panel_v1.json"
MANIFEST_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_panel_manifest_v1.json"
)
REPORT_MD_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_panel_v1.md"
)

SHALL_RE = re.compile(r"\bshall\b", re.IGNORECASE)
APPLY_RE = re.compile(r"\bapply\b|\bapplies\b", re.IGNORECASE)
SAMPLE_ID_RE = re.compile(r"\bestg_\d+\b", re.IGNORECASE)


class PanelBuildError(RuntimeError):
    """The frozen inputs do not satisfy the panel contract."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _contains_shall(text: str) -> bool:
    return SHALL_RE.search(text) is not None


def _contains_apply_or_applies(text: str) -> bool:
    return APPLY_RE.search(text) is not None


def _stable_key(clause: Mapping[str, Any]) -> str:
    payload = f"{clause['sample_id']}|{clause['clause_id']}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _flatten_gold(gold: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    records = gold.get("records")
    if not isinstance(records, list):
        raise PanelBuildError("Gold records must be a list")
    for record in records:
        sample_id = str(record["sample_id"])
        sample_text = str(record["approved_text_en"])
        clauses = record.get("clauses")
        if not isinstance(clauses, list):
            raise PanelBuildError(f"Gold record {sample_id} has no clause list")
        for clause in clauses:
            text = str(clause["clause_span"]["text"])
            rows.append(
                {
                    "sample_id": sample_id,
                    "clause_id": str(clause["clause_id"]),
                    "modality": str(clause["modality"]),
                    "text": text,
                    "sample_text": sample_text,
                    "clause_span_start": int(clause["clause_span"]["start"]),
                    "clause_span_end": int(clause["clause_span"]["end"]),
                }
            )
    return rows


def _select_slice_a(clauses: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        dict(row)
        for row in clauses
        if row["modality"] == "definition" and _contains_shall(str(row["text"]))
    ]
    return sorted(selected, key=lambda row: (row["sample_id"], row["clause_id"]))


def _select_slice_b(clauses: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    pool = [
        dict(row)
        for row in clauses
        if row["modality"] != "definition" and _contains_shall(str(row["text"]))
    ]
    rare = [
        row
        for row in pool
        if row["modality"] in ("prohibition", "permission")
    ]
    rare.sort(key=lambda row: (row["sample_id"], row["clause_id"]))
    obligations = [
        row for row in pool if row["modality"] == "obligation"
    ]
    obligations.sort(
        key=lambda row: (
            _stable_key(row),
            row["sample_id"],
            row["clause_id"],
        )
    )
    selected = rare + obligations[:6]
    return sorted(selected, key=lambda row: (row["sample_id"], row["clause_id"]))


def _select_slice_c(clauses: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        dict(row)
        for row in clauses
        if _contains_apply_or_applies(str(row["text"]))
    ]
    return sorted(selected, key=lambda row: (row["sample_id"], row["clause_id"]))


def _select_slice_d(clauses: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    pool = [
        dict(row)
        for row in clauses
        if row["modality"] == "definition"
        and not _contains_shall(str(row["text"]))
    ]
    pool.sort(
        key=lambda row: (
            _stable_key(row),
            row["sample_id"],
            row["clause_id"],
        )
    )
    return pool[:6]


def _prompt_hash_payload(prompt: Any) -> dict[str, str]:
    return {
        "system_sha256": _sha256_text(prompt.system_prompt),
        "user_sha256": _sha256_text(prompt.user_prompt_template),
        "composition_sha256": str(prompt.composition_sha256),
        "markdown_sha256": _sha256_text(prompt.to_markdown()),
    }


def _slice_summary(
    slices: Mapping[str, Sequence[Mapping[str, Any]]]
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for name, rows in slices.items():
        clause_keys = {
            (str(row["sample_id"]), str(row["clause_id"])) for row in rows
        }
        summary[name] = {
            "clause_count": len(rows),
            "unique_clause_count": len(clause_keys),
            "sample_count": len({str(row["sample_id"]) for row in rows}),
            "modality_counts": dict(
                sorted(Counter(str(row["modality"]) for row in rows).items())
            ),
        }
    return summary


def _pairwise_unique_clause_overlap(
    slices: Mapping[str, Sequence[Mapping[str, Any]]]
) -> dict[str, int]:
    clause_sets = {
        name.split("_", 1)[0]: {
            (str(row["sample_id"]), str(row["clause_id"])) for row in rows
        }
        for name, rows in slices.items()
    }
    names = list(clause_sets)
    overlap: dict[str, int] = {}
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            overlap[f"{left}&{right}"] = len(
                clause_sets[left] & clause_sets[right]
            )
    overlap["A&B&C&D"] = len(
        clause_sets["A"] & clause_sets["B"]
        & clause_sets["C"] & clause_sets["D"]
    )
    return dict(sorted(overlap.items()))


def _pairwise_sample_overlap(
    slices: Mapping[str, Sequence[Mapping[str, Any]]]
) -> dict[str, int]:
    sample_sets = {
        name.split("_", 1)[0]: {str(row["sample_id"]) for row in rows}
        for name, rows in slices.items()
    }
    names = list(sample_sets)
    overlap: dict[str, int] = {}
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            overlap[f"{left}&{right}"] = len(
                sample_sets[left] & sample_sets[right]
            )
    overlap["A&B&C&D"] = len(
        sample_sets["A"] & sample_sets["B"] & sample_sets["C"] & sample_sets["D"]
    )
    return dict(sorted(overlap.items()))


def build_panel(*, write: bool = False, overwrite: bool = True) -> dict[str, Any]:
    gold = _read_json(GOLD_PATH)
    input_doc = _read_json(INPUT_PATH)
    clauses = _flatten_gold(gold)

    if len(clauses) != 231:
        raise PanelBuildError(f"expected 231 Gold clauses, got {len(clauses)}")
    modality_counts = Counter(str(row["modality"]) for row in clauses)
    if modality_counts != Counter({
        "obligation": 97,
        "permission": 62,
        "definition": 39,
        "prohibition": 33,
    }):
        raise PanelBuildError(f"unexpected Gold modality counts: {modality_counts}")

    slices = {
        "A_shall_definition": _select_slice_a(clauses),
        "B_non_definition_shall_controls": _select_slice_b(clauses),
        "C_apply_applies_stress": _select_slice_c(clauses),
        "D_non_shall_definition_controls": _select_slice_d(clauses),
    }
    if len(slices["A_shall_definition"]) != 15:
        raise PanelBuildError("Slice A must contain exactly 15 clauses")
    if len(slices["B_non_definition_shall_controls"]) != 15:
        raise PanelBuildError("Slice B must contain exactly 15 clauses")
    if len(slices["C_apply_applies_stress"]) != 12:
        raise PanelBuildError("Slice C must contain exactly 12 clauses")
    if len(slices["D_non_shall_definition_controls"]) != 6:
        raise PanelBuildError("Slice D must contain exactly 6 clauses")

    clause_by_key = {
        (str(row["sample_id"]), str(row["clause_id"])): row for row in clauses
    }
    slice_names = {name.split("_", 1)[0]: name for name in slices}
    clause_slices: dict[tuple[str, str], set[str]] = defaultdict(set)
    for slice_name, rows in slices.items():
        short = slice_name.split("_", 1)[0]
        for row in rows:
            clause_slices[(str(row["sample_id"]), str(row["clause_id"]))].add(
                short
            )

    selected_clauses: list[dict[str, Any]] = []
    for key in sorted(clause_slices):
        row = clause_by_key[key]
        selected_clauses.append(
            {
                "sample_id": key[0],
                "clause_id": key[1],
                "modality": str(row["modality"]),
                "text": str(row["text"]),
                "slices": sorted(clause_slices[key]),
            }
        )

    selected_sample_ids = sorted({row["sample_id"] for row in selected_clauses})
    selected_sample_set = set(selected_sample_ids)
    all_clauses_in_selected_samples = [
        row for row in clauses if row["sample_id"] in selected_sample_set
    ]

    if len(selected_sample_ids) != 42:
        raise PanelBuildError(
            f"expected 42 unique selected samples, got {len(selected_sample_ids)}"
        )
    if len(selected_clauses) != 45:
        raise PanelBuildError(
            f"expected 45 unique selected clauses, got {len(selected_clauses)}"
        )

    unique_selected_modality = Counter(
        str(row["modality"]) for row in selected_clauses
    )
    all_sample_modality = Counter(
        str(row["modality"]) for row in all_clauses_in_selected_samples
    )

    gold_hash = _sha256_file(GOLD_PATH)
    input_hash = _sha256_file(INPUT_PATH)
    active_registry_hash = _sha256_file(ACTIVE_REGISTRY_PATH)
    active_manifest_hash = _sha256_file(ACTIVE_PROMPT_MANIFEST_PATH)

    active_a = rp.render_refinement_prompt("A")
    base = dr.render_definition_prompt("BASE")
    rdef = dr.render_definition_prompt("R_DEF")

    apply_rows = sorted(
        [
            {
                "sample_id": str(row["sample_id"]),
                "clause_id": str(row["clause_id"]),
                "modality": str(row["modality"]),
                "text": str(row["text"]),
                "status": "NEEDS_GOLD_ADJUDICATION",
            }
            for row in slices["C_apply_applies_stress"]
        ],
        key=lambda row: (row["sample_id"], row["clause_id"]),
    )

    gold_pairs = [
        {
            "sample_id": "estg_000505",
            "clause_id": "c2",
            "text": str(
                clause_by_key[("estg_000505", "c2")]["text"]
            ),
            "modality": str(
                clause_by_key[("estg_000505", "c2")]["modality"]
            ),
            "in_panel": ("estg_000505", "c2") in clause_slices,
            "status": "POTENTIAL_GOLD_INCONSISTENCY",
        },
        {
            "sample_id": "estg_000509",
            "clause_id": "c2",
            "text": str(
                clause_by_key[("estg_000509", "c2")]["text"]
            ),
            "modality": str(
                clause_by_key[("estg_000509", "c2")]["modality"]
            ),
            "in_panel": ("estg_000509", "c2") in clause_slices,
            "status": "POTENTIAL_GOLD_INCONSISTENCY",
        },
    ]

    panel_payload = {
        "schema_version": "sep_c3_definition_targeted_panel@1.0.0",
        "status": "FROZEN_BEFORE_NEW_API",
        "freeze_scope": "targeted_prompt_development_panel_not_formal_test_set",
        "purpose": [
            "Does replacing the conflicting E4 improve definition handling?",
            "Does R_DEF provide additional improvement beyond E4 replacement?",
            "Do either changes incorrectly convert ordinary deontic shall clauses into definitions?",
            "Does the refinement improve action presence for definition clauses?",
            "What happens on ambiguous apply/applies cases?",
        ],
        "source_bindings": {
            "gold_path": str(GOLD_PATH.relative_to(ROOT)).replace("\\", "/"),
            "gold_sha256": gold_hash,
            "input_path": str(INPUT_PATH.relative_to(ROOT)).replace("\\", "/"),
            "input_sha256": input_hash,
            "input_record_count": len(input_doc.get("records") or []),
            "gold_record_count": len(gold.get("records") or []),
            "active_registry_path": str(
                ACTIVE_REGISTRY_PATH.relative_to(ROOT)
            ).replace("\\", "/"),
            "active_registry_sha256": active_registry_hash,
            "active_prompt_manifest_path": str(
                ACTIVE_PROMPT_MANIFEST_PATH.relative_to(ROOT)
            ).replace("\\", "/"),
            "active_prompt_manifest_sha256": active_manifest_hash,
        },
        "api_input_unit": "sample_id",
        "deduplication": {
            "unit": "sample_id",
            "rule": (
                "A sample is included once if any selected target clause lies "
                "in it.  Slice tags are retained per unique clause.  The API "
                "request unit is the whole frozen input sample."
            ),
        },
        "selection_rules": {
            "A_shall_definition": (
                "ALL Gold clauses with modality=definition and clause_span.text "
                "matching the case-insensitive word-boundary regex "
                r"\\bshall\\b."
            ),
            "B_non_definition_shall_controls": (
                "Start from all Gold clauses with modality in "
                "{obligation,prohibition,permission} whose clause_span.text "
                "matches \\bshall\\b. Include ALL prohibition and permission "
                "controls. Fill the remaining 6 slots with obligation controls "
                "sorted by SHA-256 of the UTF-8 string "
                "'<sample_id>|<clause_id>' ascending, taking the first 6. "
                "Finally sort the selected controls by sample_id, clause_id."
            ),
            "C_apply_applies_stress": (
                "ALL Gold clauses with clause_span.text matching the "
                "case-insensitive regex \\bapply\\b|\\bapplies\\b."
            ),
            "D_non_shall_definition_controls": (
                "Start from all Gold definition clauses whose clause_span.text "
                "does not match \\bshall\\b. Sort by SHA-256 of the UTF-8 "
                "string '<sample_id>|<clause_id>' ascending; take the first 6."
            ),
        },
        "gold_total_counts": {
            "clauses": len(clauses),
            "samples": len(gold.get("records") or []),
            "modality_counts": dict(sorted(modality_counts.items())),
            "definition_clauses": modality_counts["definition"],
            "shall_definition_clauses": len(slices["A_shall_definition"]),
            "non_definition_shall_clauses": len(
                [
                    row
                    for row in clauses
                    if row["modality"] != "definition"
                    and _contains_shall(str(row["text"]))
                ]
            ),
        },
        "slice_summary": _slice_summary(slices),
        "pairwise_sample_overlap": _pairwise_sample_overlap(slices),
        "pairwise_unique_clause_overlap": _pairwise_unique_clause_overlap(
            slices
        ),
        "clause_keys_in_multiple_slices": sorted(
            [
                {
                    "sample_id": sample_id,
                    "clause_id": clause_id,
                    "slices": sorted(slice_set),
                }
                for (sample_id, clause_id), slice_set in clause_slices.items()
                if len(slice_set) > 1
            ],
            key=lambda row: (row["sample_id"], row["clause_id"]),
        ),
        "panel_accounting": {
            "unique_sample_count_N": len(selected_sample_ids),
            "unique_selected_clause_count": len(selected_clauses),
            "sum_of_slice_clause_counts_before_dedup": sum(
                len(rows) for rows in slices.values()
            ),
            "definition_case_count": int(
                unique_selected_modality["definition"]
            ),
            "non_definition_case_count": int(
                sum(
                    count
                    for modality, count in unique_selected_modality.items()
                    if modality != "definition"
                )
            ),
            "unique_selected_modality_distribution": dict(
                sorted(unique_selected_modality.items())
            ),
            "all_clauses_in_selected_samples": len(
                all_clauses_in_selected_samples
            ),
            "all_clauses_in_selected_samples_modality_distribution": dict(
                sorted(all_sample_modality.items())
            ),
            "expected_api_calls": {
                "A_existing_read_only": 0,
                "BASE": len(selected_sample_ids),
                "R_DEF": len(selected_sample_ids),
                "total_new": 2 * len(selected_sample_ids),
            },
        },
        "prompt_hashes": {
            "A": _prompt_hash_payload(active_a),
            "BASE": _prompt_hash_payload(base),
            "R_DEF": _prompt_hash_payload(rdef),
        },
        "selected_sample_ids": selected_sample_ids,
        "selected_clauses": selected_clauses,
        "selected_sample_clause_ids": {
            sample_id: [
                clause_id
                for clause_id in sorted(
                    {
                        str(row["clause_id"])
                        for row in all_clauses_in_selected_samples
                        if row["sample_id"] == sample_id
                    }
                )
            ]
            for sample_id in selected_sample_ids
        },
        "apply_applies_stress_cases": apply_rows,
        "gold_inconsistency_cases": gold_pairs,
    }

    if write:
        _write_json(PANEL_PATH, panel_payload)
        panel_sha = _sha256_file(PANEL_PATH)
        payload_sha = _sha256_text(_canonical_json(panel_payload))
        manifest = {
            "schema_version": (
                "sep_c3_definition_targeted_panel_manifest@1.0.0"
            ),
            "status": "FROZEN_BEFORE_NEW_API",
            "panel_path": str(PANEL_PATH.relative_to(ROOT)).replace("\\", "/"),
            "panel_sha256": panel_sha,
            "panel_canonical_payload_sha256": payload_sha,
            "panel_manifest_path": str(MANIFEST_PATH.relative_to(ROOT)).replace(
                "\\", "/"
            ),
            "api_calls": 0,
            "new_api_authorized": False,
            "source_bindings": panel_payload["source_bindings"],
            "prompt_hashes": panel_payload["prompt_hashes"],
            "panel_accounting": panel_payload["panel_accounting"],
            "selection_rules_sha256": _sha256_text(
                _canonical_json(panel_payload["selection_rules"])
            ),
            "selected_sample_ids_sha256": _sha256_text(
                _canonical_json(selected_sample_ids)
            ),
            "selected_clauses_sha256": _sha256_text(
                _canonical_json(selected_clauses)
            ),
        }
        _write_json(MANIFEST_PATH, manifest)
        _write_text(
            REPORT_MD_PATH,
            _render_markdown(panel_payload, manifest),
        )
        return {"panel": panel_payload, "manifest": manifest}

    return {"panel": panel_payload, "manifest": None}


def _render_markdown(
    panel: Mapping[str, Any], manifest: Mapping[str, Any]
) -> str:
    accounting = panel["panel_accounting"]
    lines = [
        "# SEP-C3 Definition Targeted Development Panel v1",
        "",
        "- Status: **frozen before new API output**",
        "- API calls during construction: **0**",
        "- Scope: targeted prompt-development panel, not a new formal test set",
        f"- Unique samples N: **{accounting['unique_sample_count_N']}**",
        f"- Unique selected clauses: **{accounting['unique_selected_clause_count']}**",
        f"- New API calls: **BASE={accounting['expected_api_calls']['BASE']}, "
        f"R_DEF={accounting['expected_api_calls']['R_DEF']}, "
        f"total={accounting['expected_api_calls']['total_new']}**",
        f"- Panel SHA-256: `{manifest.get('panel_sha256', '')}`",
        "",
        "## Slice summary",
        "",
        "| Slice | Clauses | Unique clauses | Samples | Modality counts |",
        "|---|---:|---:|---:|---|",
    ]
    for name, row in panel["slice_summary"].items():
        modality = ", ".join(
            f"{key}:{value}" for key, value in row["modality_counts"].items()
        )
        lines.append(
            f"| `{name}` | {row['clause_count']} | {row['unique_clause_count']} | "
            f"{row['sample_count']} | {modality} |"
        )
    lines += [
        "",
        "## Deduplication accounting",
        "",
        f"- Unique samples: {accounting['unique_sample_count_N']}",
        f"- Unique selected clauses: {accounting['unique_selected_clause_count']}",
        f"- Sum of slice clause counts before dedup: "
        f"{accounting['sum_of_slice_clause_counts_before_dedup']}",
        f"- Definition cases: {accounting['definition_case_count']}",
        f"- Non-definition cases: {accounting['non_definition_case_count']}",
        f"- Clauses in selected samples (all, for diagnostics): "
        f"{accounting['all_clauses_in_selected_samples']}",
        "",
        "## Modality distribution",
        "",
        "### Unique selected clauses",
        "",
    ]
    for key, value in accounting[
        "unique_selected_modality_distribution"
    ].items():
        lines.append(f"- {key}: {value}")
    lines += [
        "",
        "### All clauses in selected samples",
        "",
    ]
    for key, value in accounting[
        "all_clauses_in_selected_samples_modality_distribution"
    ].items():
        lines.append(f"- {key}: {value}")
    lines += [
        "",
        "## Prompt hashes",
        "",
        "| Arm | System | User template | Composition |",
        "|---|---|---|---|",
    ]
    for arm, row in panel["prompt_hashes"].items():
        lines.append(
            f"| {arm} | `{row['system_sha256']}` | `{row['user_sha256']}` | "
            f"`{row['composition_sha256']}` |"
        )
    lines += [
        "",
        "## Ambiguity diagnostics",
        "",
        f"- Apply/applies cases: {len(panel['apply_applies_stress_cases'])} "
        "retained with `NEEDS_GOLD_ADJUDICATION`; no lexical rule is inferred.",
        "- Gold inconsistency pair:",
    ]
    for row in panel["gold_inconsistency_cases"]:
        lines.append(
            f"  - `{row['sample_id']} {row['clause_id']}` "
            f"modality={row['modality']} in_panel={row['in_panel']} "
            f"status={row['status']}"
        )
    lines += [
        "",
        "## Freeze note",
        "",
        "This panel was frozen before any BASE/R_DEF model output was produced. "
        "Gold was used only for construction and later evaluation; no Gold "
        "labels or spans are included in the frozen inference request bodies.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    result = build_panel(write=args.write, overwrite=args.overwrite)
    if args.write:
        print(json.dumps({
            "status": result["panel"]["status"],
            "panel_path": str(PANEL_PATH.relative_to(ROOT)).replace("\\", "/"),
            "manifest_path": str(MANIFEST_PATH.relative_to(ROOT)).replace(
                "\\", "/"
            ),
            "panel_sha256": result["manifest"]["panel_sha256"],
            "N": result["panel"]["panel_accounting"]["unique_sample_count_N"],
            "new_calls": result["panel"]["panel_accounting"][
                "expected_api_calls"
            ]["total_new"],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result["panel"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())