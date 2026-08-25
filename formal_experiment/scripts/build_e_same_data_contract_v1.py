# -*- coding: utf-8 -*-
"""Build the Experiment E same-data input contract (prepared, zero API).

Locks the 38 non-empty Barrientos requirements (three scenarios) with their
texts' SHA-256 and the per-scenario counts, plus the Barrientos prompt and
format hashes.  This is the same-data surface for a future authorized run of
the three E arms; NO model call happens here.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQ_DIR = ROOT.parent / "references" / "barrientos_2026" / "artifact_input" / "requirements"
OUT = ROOT / "configs" / "ablations" / "e_same_data_input_contract_v1.json"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def main() -> int:
    scenarios = []
    items = []
    for name in ("blood_donation_scenario", "emergencies_scenario",
                 "SIM_card_scenario"):
        path = REQ_DIR / name / f"{name}.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        scenario_items = []
        for req in doc:
            text = (req.get("text") or "").strip()
            if not text:
                continue
            item = {
                "id": f"{name}/{req.get('ID')}",
                "text": text,
                "text_sha256": _sha256_bytes(text.encode("utf-8")),
            }
            scenario_items.append(item)
            items.append(item)
        scenarios.append({
            "scenario": name,
            "file": f"references/barrientos_2026/artifact_input/requirements/{name}/{name}.json",
            "file_sha256": _sha256_file(path),
            "nonempty_count": len(scenario_items),
        })

    if len(items) != 38:
        print(f"WARNING: expected 38 non-empty, got {len(items)}")

    contract = {
        "schema_version": "e_same_data_input_contract@1.0.0",
        "task_id": "S2-BARRIENTOS-E",
        "claim_scope": "development_only",
        "zero_api": True,
        "input_surface": {
            "note": (
                "same-data comparison surface: the 38 non-empty Barrientos "
                "requirements (artifact-verifiable; the S2.12 36-sample corpus "
                "is a versioned subset of the same files)"
            ),
            "nonempty_count": len(items),
            "scenarios": scenarios,
            "items": sorted(items, key=lambda i: i["id"]),
        },
        "arms": {
            "ours_six_field": {
                "prompt": "prompts/sun_compat/direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md",
                "status": "prepared_not_executed_no_api",
            },
            "barrientos_faithful": {
                "prompt": "references/barrientos_2026/artifact_input/prompts/formalize_requirements_prompt.txt",
                "format": "references/barrientos_2026/artifact_input/formats/compliance_requirements_format.json",
                "status": "prepared_not_executed_no_api",
            },
            "ours_with_barrientos_style_module": {
                "prompt": "prompts/sun_compat/ablation_v1/direct_llm_barrientos_style_prompt_v1.md",
                "status": "prepared_not_executed_no_api",
            },
        },
        "shared_metrics_protocol": [
            "obligation/permission/prohibition three-class modality",
            "JSON/structural validity rate",
            "output coverage",
            "failure rate",
            "runtime/cost",
            "five-run self-consistency (same 38 items, same model config, 5 independent full runs)",
            "sample-level output difference cases",
        ],
        "separate_metrics_protocol": {
            "ours_six_field": "six-field span P/R/F1 (project evaluator)",
            "barrientos": "44-pattern / change-impact metrics (Barrientos evaluator)",
            "note": "must be reported in separate tables; never merged into one F1",
        },
        "stability_protocol": {
            "runs": 5,
            "items": len(items),
            "per_item_metrics": [
                "consistency rate",
                "modality agreement",
                "field-span agreement (ours arms)",
                "JSON validity",
                "pairwise distance / self-consistency",
                "most/least stable cases",
            ],
        },
        "safety": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "references_read_only": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        raise RuntimeError(f"refusing to overwrite: {OUT}")
    OUT.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"E same-data input contract written: {OUT.relative_to(ROOT)} "
          f"({len(items)} non-empty)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())