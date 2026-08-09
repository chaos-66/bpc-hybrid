# -*- coding: utf-8 -*-
"""Build the formal Gold user authorization packet (DRY-RUN ONLY).

Lists the exact machine-contract fields that WOULD change if the user
authorizes formal Gold publication, with before/after values, evidence for
each flip condition, expected blocker outcome, rollback, and a ready-to-reply
authorization sentence. This script NEVER modifies the contract, the
publication gate, or any formal status; the packet is not itself an
authorization.

Usage:
    python scripts/build_formal_gold_authorization_packet.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "experiment_contract.json"
OUTPUT_JSON = ROOT / "outputs" / "reports" / "formal_gold_authorization_packet_v1.json"
OUTPUT_MD = ROOT / "outputs" / "reports" / "formal_gold_authorization_packet_v1.md"

FROZEN_STAGE2_MANIFESTS = [
    ROOT / "outputs" / "reports" / "s32_s33_gold_annotation_freeze_v1.manifest.json",  # Stage 3 58/58
]
FROZEN_STAGE3_MANIFEST = ROOT / "outputs" / "reports" / "s32_s33_gold_annotation_freeze_v1.manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if OUTPUT_JSON.exists() or OUTPUT_MD.exists():
        raise RuntimeError("refusing to overwrite existing authorization packet")
    contract = _load_json(CONTRACT)

    # current state (read-only)
    route_status = contract["route"]["status"]
    stage2_status = contract["stage2_dataset"]["status"]
    stage3_status = contract["stage3"]["status"]
    gate_status = contract["formal_gold_publication_gate"]["status"]
    allowed = contract["formal_gold_publication_gate"]["allowed_publication_statuses"]
    freeze_policy_note = contract["stage2_dataset"].get("freeze_policy", "")

    # proposed dry-run changes (NOT applied)
    proposed = [
        {
            "field": "stage3.status",
            "before": stage3_status,
            "after": "locked",
            "why_eligible": (
                "S3.1-S3.3 data governance complete (7 BPMN byte-exact + matching/violation Gold annotation frozen "
                "58/58, s32_s33_gold_annotation_freeze_v1.manifest.json); the contract notes the lock requires "
                "'final subset configuration and violation Gold lock', which the frozen annotation provides"
            ),
        },
        {
            "field": "formal_gold_publication_gate.status",
            "before": gate_status,
            "after": allowed[0],
            "why_eligible": (
                "exact whitelist match to allowed_publication_statuses is required by Event 23; the flip is a "
                "user-authorized contract change recorded in the audit log"
            ),
        },
        {
            "field": "stage2_dataset.freeze_policy",
            "before": freeze_policy_note[:80] + "...",
            "after": "re-evaluated and explicitly re-locked (no 'reopened_pending_*' status anywhere on the formal Gold publication path)",
            "why_eligible": "required_preconditions demand the freeze policy be re-evaluated and explicitly re-locked",
        },
    ]

    expected_after_blockers = {
        "removed": [
            "formal_gold_publication_paused (publication gate enters whitelist)",
            "stage3_benchmark_not_locked (stage3.status becomes locked)",
        ],
        "remaining": [
            "final_experiment_not_ready (three methods + Stage 3 formal run not done)",
            "formal_methods_not_ready (formal shared capsule not frozen)",
            "formal_capsule_not_frozen (shared comparison capsule pending)",
        ],
    }

    packet = {
        "schema_version": "formal_gold_authorization_packet@1.0.0",
        "packet_id": "formal_gold_authorization_packet_v1",
        "dry_run": True,
        "contract_not_modified": True,
        "current_audit": {
            "errors": 0,
            "blockers": [
                "formal_gold_publication_paused",
                "final_experiment_not_ready",
                "formal_methods_not_ready",
                "formal_capsule_not_frozen",
                "stage3_benchmark_not_locked",
            ],
            "note": "integrity_pass=true; human_review_freeze_ready=true (150/150); formal_gold_publication_ready=false; final_experiment_ready=false",
        },
        "current_contract_state": {
            "route.status": route_status,
            "route_evidence": "route re-locked 2026-08-06 by user-authorized governance decision (B0-R2 verified, method_conformance_status=verified_method_level_independent_reconstruction, official Sun supplement hash-matched)",
            "stage2_dataset.status": stage2_status,
            "stage2_evidence": "re-locked 2026-08-06: modality dataset verified (2,831 rows) + phrase Gold freeze 150/150 (restored from 56d2b03, freeze validator passed)",
            "stage3.status": stage3_status,
            "freeze_policy": freeze_policy_note[:100] + "...",
            "publication_gate.status": gate_status,
            "allowed_publication_statuses": allowed,
        },
        "frozen_credentials": {
            "stage2_150_150": {
                "evidence": "Layer E v2 file 150/150 adjudicated (2026-08-06 restore); human_review_freeze_ready=true in audit",
                "correction_pack": "data/development/human_review/estg_150_human_correction_v1.json",
            },
            "stage3_58_58": {
                "manifest": str(FROZEN_STAGE3_MANIFEST.relative_to(ROOT).as_posix()),
                "sha256": _sha256(FROZEN_STAGE3_MANIFEST),
                "summary": "25 matching (11 relevant / 14 not relevant) + 33 violation (3 types x 11), user adjudicated",
            },
        },
        "proposed_contract_changes": proposed,
        "expected_blocker_outcome": expected_after_blockers,
        "formal_oracle_still_blocked": {
            "s1_7": "S1.7 freeze formal Stage 1 NOT complete -> true Gold Process Records unavailable -> formal Oracle (S3.7) still blocked",
            "s2_13": "S2.13 freeze Stage 2 NOT complete (S2.10/S2.12 pending) -> formal shared capsule not frozen",
            "note": "formal Gold publication unlocks B0-R4/D1-R4/S2.10/S2.12 and zero-API Oracle preparation, but S3.7 formal Oracle itself still requires S1.7/S2.13 and true Gold Rule/Process Records (see s37_oracle_readiness_v1.json)",
        },
        "rollback": [
            "revert the contract change commit (git revert) or restore the previous contract blob",
            "re-run audit_project.py: gate returns to blocked state",
            "no experiment artifacts are touched by the contract flip itself",
        ],
        "authorization_sentence": (
            "I authorize the machine-contract change that sets stage3.status=locked, re-locks the freeze policy, "
            "and moves formal_gold_publication_gate.status into the allowed whitelist "
            "['ready_for_formal_gold_publication'], thereby enabling formal Gold publication (dry-run packet "
            "formal_gold_authorization_packet_v1)."
        ),
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md_lines = [
        "# Formal Gold 用户授权包（DRY-RUN，未修改任何合同）",
        "",
        f"- packet_id: {packet['packet_id']}；dry_run=true；contract_not_modified=true",
        "",
        "## 当前 audit",
        f"- errors=0；blockers={json.dumps(packet['current_audit']['blockers'], ensure_ascii=False)}",
        f"- integrity_pass=true；human_review_freeze_ready=true (150/150)；formal_gold_publication_ready=false；final_experiment_ready=false",
        "",
        "## 当前机器合同状态",
        f"- route.status = `{route_status}`（2026-08-06 用户授权重锁，B0-R2 verified + method_conformance 翻转 + supplement hash 匹配）",
        f"- stage2_dataset.status = `{stage2_status}`（modality 2,831 行 verified + phrase Gold 150/150 freeze）",
        f"- stage3.status = `{stage3_status}`",
        f"- freeze_policy = 尚未重锁（现状：{freeze_policy_note[:60]}...）",
        f"- formal_gold_publication_gate.status = `{gate_status}`；allowed={json.dumps(allowed, ensure_ascii=False)}",
        "",
        "## 冻结凭证",
        "- Stage 2：150/150 adjudicated（Layer E v2，2026-08-06 恢复，audit human_review_freeze_ready=true）",
        f"- Stage 3：58/58 冻结 manifest `{packet['frozen_credentials']['stage3_58_58']['manifest']}` (sha {packet['frozen_credentials']['stage3_58_58']['sha256'][:12]}...)",
        "",
        "## 拟议合同修改（before -> after）",
    ]
    for p in proposed:
        md_lines.append(f"- `{p['field']}`：`{p['before'][:60]}...` -> `{p['after']}`；依据：{p['why_eligible']}")
    md_lines += [
        "",
        "## 翻转后预期 blockers",
        f"- 消除：{json.dumps(expected_after_blockers['removed'], ensure_ascii=False)}",
        f"- 保留：{json.dumps(expected_after_blockers['remaining'], ensure_ascii=False)}",
        "",
        "## formal Oracle 仍被阻止",
        "- S1.7（Stage 1 冻结）未完成 -> 无真正 Gold Process Records；S2.13 未完成 -> formal capsule 未冻结",
        "- 详见 s37_oracle_readiness_v1.json：S3.7 formal Oracle blocked_on_s1_7_s2_13",
        "",
        "## 回滚",
        "- git revert 合同变更 commit 或恢复合同 blob；重跑 audit 即回到 blocked 状态",
        "",
        "## 授权句（用户可直接回复）",
        "",
        "> " + packet["authorization_sentence"],
        "",
    ]
    OUTPUT_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_JSON}")
    print(f"wrote {OUTPUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
