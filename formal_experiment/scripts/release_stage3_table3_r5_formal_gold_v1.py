# -*- coding: utf-8 -*-
"""Release the user-approved formal Gold packet and record API authorization.

This script is offline: it does not read `.env` and does not call any API.
It creates the formal release marker, the authorization event, and the current
machine-readable readiness artifact for the frozen S3-TABLE3-R5 execution.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import build_stage3_table3_r5_api_payload_freeze_v2 as payload_freeze  # noqa: E402

BENCHMARK_ID = "stage3_table3_r5_benchmark_v2"
GOLD_JSON = ROOT / "outputs/reports/stage3_table3_r5_gold_adjudication_packet_v1.json"
GOLD_MD = ROOT / "outputs/reports/stage3_table3_r5_gold_adjudication_packet_v1.md"
PAYLOAD_JSON = ROOT / "outputs/reports/stage3_table3_r5_api_payload_freeze_v2.json"
RELEASE_JSON = ROOT / "outputs/reports/stage3_table3_r5_formal_gold_release_v1.json"
RELEASE_MD = ROOT / "outputs/reports/stage3_table3_r5_formal_gold_release_v1.md"
AUTH_JSON = ROOT / "configs/authorization/stage3_table3_r5_user_authorization_v1.json"
READINESS_JSON = ROOT / "outputs/reports/stage3_table3_r5_formal_readiness_v1.json"

EXPECTED_GOLD_JSON_SHA256 = "1e6de56fb3a934646816fe361873966acae1b0022e80c65f9eadf45d591c5884"
EXPECTED_GOLD_MD_SHA256 = "35ebcca62c5348f0720cf3f5d4a9e5df173d26cc622af2c243691c8f4c23791d"
EXPECTED_PAYLOAD_MANIFEST_SHA256 = "bd029e42ff6db8752e138827ad9861c660f1eda1b4b6dbaac8ee7715b30d3707"
EXPECTED_PROMPT_SHA256 = "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"
REQUEST_IDS = [
    "R5-S1-T1", "R5-S1-T2", "R5-S1-T3", "R5-S1-T4", "R5-S2-T2",
    "R5-S3-T1", "R5-S3-T2", "R5-S4-T1", "R5-S4-T2", "R5-S4-T3",
    "R5-S4-T4", "R5-S5-T1", "R5-S5-T2", "R5-S5-T3", "R5-S5-T4",
    "R5-S6-T1", "R5-S6-T2", "R5-S7-T1", "R5-S8-T1",
]
EXCLUDED_CANDIDATES = ["R5-S2-T1", "R5-S2-T3", "R5-S2-T4", "R5-S3-T3", "R5-S3-T4"]


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def main() -> int:
    gold_json_sha = sha_file(GOLD_JSON)
    gold_md_sha = sha_file(GOLD_MD)
    if gold_json_sha != EXPECTED_GOLD_JSON_SHA256:
        raise SystemExit(f"Gold JSON SHA drift: {gold_json_sha}")
    if gold_md_sha != EXPECTED_GOLD_MD_SHA256:
        raise SystemExit(f"Gold MD SHA drift: {gold_md_sha}")

    frozen = load_json(PAYLOAD_JSON)
    rebuilt = payload_freeze.build_payload_manifest()
    if rebuilt != frozen:
        raise SystemExit("frozen payload manifest is not reconstructible")
    if frozen["new_request_count"] != 19:
        raise SystemExit("frozen request count drift")
    if frozen["request_ids"] != REQUEST_IDS:
        raise SystemExit("frozen request-id list drift")
    if frozen["payload_manifest_sha256"] != EXPECTED_PAYLOAD_MANIFEST_SHA256:
        raise SystemExit("payload manifest internal SHA drift")
    if frozen["prompt"]["sha256_text_normalized"] != EXPECTED_PROMPT_SHA256:
        raise SystemExit("frozen prompt SHA drift")

    release = {
        "schema_version": "stage3_table3_r5_formal_gold_release@1.0.0",
        "benchmark_id": BENCHMARK_ID,
        "formal_gold_released": True,
        "gold_packet_json": {
            "path": "outputs/reports/stage3_table3_r5_gold_adjudication_packet_v1.json",
            "sha256": gold_json_sha,
        },
        "gold_packet_md": {
            "path": "outputs/reports/stage3_table3_r5_gold_adjudication_packet_v1.md",
            "sha256": gold_md_sha,
        },
        "core_requirement_count": 33,
        "core_case_count": 113,
        "violation_counts": {
            "baseline": 33,
            "missing_action": 33,
            "incorrect_actor": 33,
            "out_of_order": 14,
        },
        "excluded_candidate_requirement_ids": EXCLUDED_CANDIDATES,
        "approval_source": "explicit_user_authorization",
        "approval_date": "2026-09-26",
        "prediction_blind": True,
        "gold_packet_immutable": True,
        "gold_packet_semantic_flags_preserved": {
            "GOLD_ADJUDICATION_STATUS": "AWAITING_USER_GPT_APPROVAL",
            "human_adjudicated": False,
            "reference_is_gold": False,
            "formal_gold_released_in_packet": False,
        },
        "release_note": (
            "The user explicitly approved this exact frozen packet as Formal Gold for the current task. "
            "The packet file and labels are not modified; this marker is the formal release record."
        ),
        "payload_manifest_sha256": EXPECTED_PAYLOAD_MANIFEST_SHA256,
        "authorized_api_calls_max": 19,
        "authorized_cost_cap_usd": 0.91,
        "real_api_calls_made": 0,
    }
    write_json(RELEASE_JSON, release)

    auth = {
        "schema_version": "stage3_table3_r5_api_authorization_event@1.0.0",
        "status": "authorized",
        "authorized_by": "user",
        "authorization_date": "2026-09-26",
        "authorized_provider": "DeepSeek",
        "authorized_model": "deepseek-v4-pro",
        "resolved_alias": "DeepSeek-V4-Pro-0813",
        "authorized_call_count_max": 19,
        "authorized_retry_count": 0,
        "authorized_cost_cap_usd": 0.91,
        "payload_manifest_sha256": EXPECTED_PAYLOAD_MANIFEST_SHA256,
        "formal_gold_packet_sha256": EXPECTED_GOLD_JSON_SHA256,
        "prompt_sha256": EXPECTED_PROMPT_SHA256,
        "request_ids": REQUEST_IDS,
        "excluded_candidate_requirement_ids": EXCLUDED_CANDIDATES,
        "scope": "current S3-TABLE3-R5 formal execution only",
        "authorization_text": (
            "我批准当前 Formal Gold，并授权按冻结 payload 调用 DeepSeek API 19 次，最高费用 0.91 美元。"
        ),
        "no_reuse_of_past_authorizations": True,
        "real_api_calls_made": 0,
    }
    write_json(AUTH_JSON, auth)

    readiness = {
        "schema_version": "stage3_table3_r5_formal_readiness@1.0.0",
        "benchmark_id": BENCHMARK_ID,
        "flags": {
            "FORMAL_GOLD_RELEASED": True,
            "API_AUTHORIZATION_PENDING": False,
            "API_AUTHORIZED": True,
            "API_EXECUTED": False,
            "FORMAL_TABLE3_RUN": False,
            "FORMAL_TABLE3_RESULT_FROZEN": False,
        },
        "gold_release_path": "outputs/reports/stage3_table3_r5_formal_gold_release_v1.json",
        "gold_packet_sha256": gold_json_sha,
        "authorization_path": "configs/authorization/stage3_table3_r5_user_authorization_v1.json",
        "payload_manifest_sha256": EXPECTED_PAYLOAD_MANIFEST_SHA256,
        "prompt_sha256": EXPECTED_PROMPT_SHA256,
        "request_count": 19,
        "retry_cap": 0,
        "cost_cap_usd": 0.91,
        "real_api_calls_made": 0,
    }
    write_json(READINESS_JSON, readiness)

    md = [
        "# S3-TABLE3-R5 Formal Gold Release",
        "",
        f"- benchmark_id: `{BENCHMARK_ID}`",
        f"- formal_gold_released: `true`",
        f"- Gold packet JSON SHA-256: `{gold_json_sha}`",
        f"- Gold packet MD SHA-256: `{gold_md_sha}`",
        "- core requirement count: `33`",
        "- core case count: `113`",
        "- violation counts: baseline `33`, missing_action `33`, incorrect_actor `33`, out_of_order `14`",
        "- approval source: explicit user authorization",
        "- approval date: `2026-09-26`",
        "- prediction_blind: `true`",
        f"- payload manifest SHA-256: `{EXPECTED_PAYLOAD_MANIFEST_SHA256}`",
        f"- prompt SHA-256: `{EXPECTED_PROMPT_SHA256}`",
        "",
        "The frozen Gold packet is released as-is. Its internal pre-approval flags are preserved in the packet",
        "and are intentionally not rewritten; this separate marker is the release authority.",
        "",
    ]
    RELEASE_MD.write_text("\n".join(md), encoding="utf-8", newline="\n")

    print(json.dumps({
        "gold_release_json": str(RELEASE_JSON.relative_to(ROOT)).replace("\\", "/"),
        "gold_release_md": str(RELEASE_MD.relative_to(ROOT)).replace("\\", "/"),
        "authorization": str(AUTH_JSON.relative_to(ROOT)).replace("\\", "/"),
        "readiness": str(READINESS_JSON.relative_to(ROOT)).replace("\\", "/"),
        "gold_packet_sha256": gold_json_sha,
        "payload_manifest_sha256": EXPECTED_PAYLOAD_MANIFEST_SHA256,
        "request_count": 19,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
