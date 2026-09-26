# -*- coding: utf-8 -*-
"""Assemble Stage 3-v2 archive/readiness notes from frozen artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "outputs/reports"
SEM_FREEZE = REPORTS / "stage3_v2_semantic_backend_freeze_v1.json"
ORDER_FREEZE = REPORTS / "stage3_v2_order_projection_freeze_v1.json"
DEV_REPORT = REPORTS / "stage3_v2_development_report_v1.json"
LEGACY_REPORT = REPORTS / "stage3_v2_legacy_test_diagnostic_v1.json"
WINTER_NOTE_JSON = REPORTS / "stage3_v2_winter_archive_status_v1.json"
WINTER_NOTE_MD = REPORTS / "stage3_v2_winter_archive_status_v1.md"
READINESS_JSON = REPORTS / "stage3_v2_readiness_v1.json"
READINESS_MD = REPORTS / "stage3_v2_readiness_v1.md"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def main() -> None:
    semantic = load(SEM_FREEZE)
    order_freeze = load(ORDER_FREEZE)
    dev = load(DEV_REPORT)
    legacy = load(LEGACY_REPORT)
    winter = {
        "schema_version": "stage3_v2_winter_archive_status@1.0.0",
        "status": "WINTER_MAINLINE_STATUS = ARCHIVED_EXTERNAL_BASELINE",
        "historical_artifacts_untouched": True,
        "further_winter_tuning": False,
        "further_winter_rescoring_for_main_table3": False,
        "citation_scope": "appendix / supplementary / external baseline discussion only",
        "provenance_reference": (
            "stage3_method_fidelity_audit_v1: Winter reproduction with corrected "
            "reachability, not native literal reproduction"
        ),
        "api_calls": 0,
        "network_calls": 0,
    }
    write_json(WINTER_NOTE_JSON, winter)
    WINTER_NOTE_MD.write_text(
        "# Winter Mainline Archive Status\n\n"
        "- WINTER_MAINLINE_STATUS = `ARCHIVED_EXTERNAL_BASELINE`\n"
        "- Historical Winter artifacts/results/reports: untouched.\n"
        "- No further Winter tuning, rescoring, or main-table comparison.\n"
        "- Citation scope: appendix / supplementary / external baseline discussion only.\n"
        "- Provenance: Winter reproduction with corrected reachability, not native literal reproduction.\n",
        encoding="utf-8", newline="\n",
    )
    readiness = {
        "schema_version": "stage3_v2_readiness@1.0.0",
        "WINTER_ARCHIVED": True,
        "STAGE3_V1_PRESERVED": True,
        "STAGE3_V2_BACKEND_SELECTED": semantic["selected_backend"]["short_name"],
        "STAGE3_V2_BACKEND_FROZEN": semantic["status"] == "SEMANTIC_BACKEND_FROZEN",
        "STAGE3_V2_GAMMA_FROZEN": float(semantic["gamma"]),
        "STAGE3_V2_THETA_FROZEN": float(semantic["theta"]),
        "STAGE3_V2_TYPE_A_ORDER_SCOPE_FROZEN": True,
        "STAGE3_V2_ORDER_PROJECTION_FROZEN": order_freeze["status"] == "ORDER_PROJECTION_FROZEN",
        "ACTION_SCOPE_CHANGE_IMPLEMENTED": False,
        "DEV_EVALUATION_COMPLETE": dev["status"] == "DEVELOPMENT_COMPLETE_BACKEND_AND_ORDER_FROZEN",
        "LEGACY_TEST_DIAGNOSTIC_COMPLETE": legacy["status"] == "LEGACY_SEEN_TEST_DIAGNOSTIC",
        "LEGACY_TEST_DIAGNOSTIC_LABEL": legacy["status"],
        "FINAL_UNSEEN_HOLDOUT_CREATED": False,
        "FINAL_TABLE3_V2_RUN": False,
        "REAL_API_CALLS": 0,
        "PREFERRED_SENTENCE_EMBEDDING_BACKEND": semantic.get("preferred_sentence_embedding_backend"),
        "PREFERRED_BACKEND_DOWNLOAD_REQUIRED": semantic.get("preferred_backend_download_required"),
        "SELECTED_BACKEND_IS_LOCAL_FALLBACK": True,
        "NOTES": (
            "The preferred all-mpnet sentence-transformer backend is not cached and was not "
            "downloaded. The pre-registered method-neutral objective selected a locally available "
            "spacy fallback for this revision. Legacy seen test replay is diagnostic only."
        ),
        "artifact_hashes": {
            "semantic_backend_freeze": sha(SEM_FREEZE),
            "order_projection_freeze": sha(ORDER_FREEZE),
            "development_report": sha(DEV_REPORT),
            "legacy_test_diagnostic": sha(LEGACY_REPORT),
        },
    }
    write_json(READINESS_JSON, readiness)
    READINESS_MD.write_text(
        "# Stage 3-v2 Readiness\n\n" + "\n".join(
            f"- {key}: `{value}`" for key, value in readiness.items()
            if key not in ("artifact_hashes", "NOTES")
        ) + f"\n\nNOTE: {readiness['NOTES']}\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({"winter": str(WINTER_NOTE_JSON), "readiness": str(READINESS_JSON)}, indent=2))


if __name__ == "__main__":
    main()
