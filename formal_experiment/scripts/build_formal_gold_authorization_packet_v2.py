# -*- coding: utf-8 -*-
"""Build the formal Gold user authorization packet v2 (DRY-RUN ONLY, v1 kept).

v2 improvements over v1:
- exact JSON Pointer paths, FULL before values (no truncation) and FULL
  after values ready to land in the contract;
- the new freeze policy preserves the governance content (data, license,
  freeze scope, prohibitions) and only updates the now-satisfied
  pending/relock status;
- the proposed patch is applied to an in-memory copy and the same gate logic
  (the five required_preconditions) is re-run on that copy;
- the ACTIVE experiment_contract.json bytes are asserted unchanged;
- formal Gold publication and method correctness are explicitly separated:
  Stage 3 data/Gold lock can be satisfied, while the formal Oracle remains
  blocked by S1.7/S2.13 and the missing true Gold Rule/Process Records.

This script NEVER modifies the contract; the packet is not an authorization.

Usage:
    python scripts/build_formal_gold_authorization_packet_v2.py
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "experiment_contract.json"
OUTPUT_JSON = ROOT / "outputs" / "reports" / "formal_gold_authorization_packet_v2.json"
OUTPUT_MD = ROOT / "outputs" / "reports" / "formal_gold_authorization_packet_v2.md"

FROZEN_STAGE3_MANIFEST = ROOT / "outputs" / "reports" / "s32_s33_gold_annotation_freeze_v1.manifest.json"

# The full current freeze_policy text (verbatim from the contract).
CURRENT_FREEZE_POLICY = (
    "The Sun modality development schema, 2,831-row analysis population, quarantine policy, "
    "and project-reconstructed split are locked by the S2.1-D machine gate. Do not write formal "
    "input or Gold: the independently reconstructed phrase Gold still requires human freeze, and "
    "the route, Stage 3, freeze/publication policy, and exact publication-status whitelist must "
    "each be re-locked separately."
)

# Proposed full replacement, preserving governance content and prohibitions and
# only updating the now-satisfied status parts.
PROPOSED_FREEZE_POLICY = (
    "The Sun modality development schema, 2,831-row analysis population, quarantine policy, "
    "and project-reconstructed split are locked by the S2.1-D machine gate. The independently "
    "reconstructed phrase Gold is frozen (150/150 adjudicated, freeze_ready=True, restored "
    "2026-08-06). The route (locked 2026-08-06), Stage 3 (locked 2026-08-08 by user "
    "authorization), the freeze/publication policy (re-locked 2026-08-08) and the exact "
    "publication-status whitelist are all satisfied. Formal Gold publication is authorized by the "
    "user; formal Oracle and final experiments remain gated by S1.7/S2.13 and the missing true "
    "Gold Rule/Process Records (see s37_oracle_readiness_v1.json). Prohibitions are unchanged: "
    "do not write formal input or Gold outside the authorized publication action; predictions, "
    "manifests and results remain no-overwrite; the modality dataset stays development-only "
    "with redistribution/publication forbidden."
)

# JSON Pointer -> full before/after (path segments as lists).
PROPOSED_CHANGES = [
    {
        "pointer": "/stage3/status",
        "pointer_path": ["stage3", "status"],
        "before_full": None,  # filled from the live contract
        "after_full": "locked",
        "why_eligible": "S3.1-S3.3 data governance complete (7 BPMN byte-exact, matching/violation Gold 58/58 frozen, s32_s33_gold_annotation_freeze_v1.manifest.json); the contract notes the lock requires 'final subset configuration and violation Gold lock', which the frozen annotation provides",
    },
    {
        "pointer": "/formal_gold_publication_gate/status",
        "pointer_path": ["formal_gold_publication_gate", "status"],
        "before_full": None,
        "after_full": "ready_for_formal_gold_publication",
        "why_eligible": "Event 23 requires an exact match against allowed_publication_statuses; the flip is a user-authorized contract change recorded in the audit log",
    },
    {
        "pointer": "/stage2_dataset/freeze_policy",
        "pointer_path": ["stage2_dataset", "freeze_policy"],
        "before_full": CURRENT_FREEZE_POLICY,
        "after_full": PROPOSED_FREEZE_POLICY,
        "why_eligible": "required_preconditions demand the freeze policy be re-evaluated and explicitly re-locked with no 'reopened_pending_*' status anywhere on the formal Gold publication path; governance content and prohibitions are preserved",
    },
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _apply_patch(contract: dict[str, Any], changes: list[dict[str, Any]]) -> dict[str, Any]:
    patched = copy.deepcopy(contract)
    for ch in changes:
        node = patched
        for seg in ch["pointer_path"][:-1]:
            node = node[seg]
        node[ch["pointer_path"][-1]] = ch["after_full"]
    return patched


def _gate_check(contract: dict[str, Any]) -> dict[str, Any]:
    """Equivalent machine check of the formal Gold publication gate over a
    contract dict (the five required_preconditions)."""
    route = contract.get("route", {}).get("status") == "locked"
    stage2 = contract.get("stage2_dataset", {}).get("status") == "locked_for_human_review"
    stage3 = contract.get("stage3", {}).get("status") == "locked"
    freeze = contract.get("stage2_dataset", {}).get("freeze_policy", "")
    freeze_ok = "reopened_pending_" not in freeze
    gate_status = contract.get("formal_gold_publication_gate", {}).get("status")
    allowed = contract.get("formal_gold_publication_gate", {}).get("allowed_publication_statuses", [])
    whitelist_ok = gate_status in allowed
    ready = route and stage2 and stage3 and freeze_ok and whitelist_ok
    return {
        "formal_gold_publication_ready": ready,
        "preconditions": {
            "route.status==locked": route,
            "stage2_dataset.status==locked_for_human_review": stage2,
            "stage3.status==locked": stage3,
            "freeze_policy re-locked (no reopened_pending_*)": freeze_ok,
            "publication gate exact whitelist match": whitelist_ok,
        },
    }


def main() -> int:
    if OUTPUT_JSON.exists() or OUTPUT_MD.exists():
        raise RuntimeError("refusing to overwrite existing packet v2")
    contract = _load_json(CONTRACT)
    contract_bytes_before = CONTRACT.read_bytes()

    for ch in PROPOSED_CHANGES:
        node = contract
        for seg in ch["pointer_path"][:-1]:
            node = node[seg]
        ch["before_full"] = node[ch["pointer_path"][-1]]

    patched = _apply_patch(contract, PROPOSED_CHANGES)
    gate_before = _gate_check(contract)
    gate_after = _gate_check(patched)

    # assert the ACTIVE contract file is byte-identical (dry-run proof)
    contract_bytes_after = CONTRACT.read_bytes()
    assert contract_bytes_before == contract_bytes_after, "active contract changed during packet build"

    packet = {
        "schema_version": "formal_gold_authorization_packet@2.0.0",
        "packet_id": "formal_gold_authorization_packet_v2",
        "supersedes": "formal_gold_authorization_packet_v1 (retained)",
        "dry_run": True,
        "contract_not_modified": True,
        "contract_sha256_before": _sha256(CONTRACT),
        "current_audit": {
            "errors": 0,
            "blockers": [
                "formal_gold_publication_paused",
                "final_experiment_not_ready",
                "formal_methods_not_ready",
                "formal_capsule_not_frozen",
                "stage3_benchmark_not_locked",
            ],
        },
        "current_contract_state": {
            "route.status": contract["route"]["status"],
            "stage2_dataset.status": contract["stage2_dataset"]["status"],
            "stage3.status": contract["stage3"]["status"],
            "publication_gate.status": contract["formal_gold_publication_gate"]["status"],
            "allowed_publication_statuses": contract["formal_gold_publication_gate"]["allowed_publication_statuses"],
        },
        "frozen_credentials": {
            "stage2_150_150": "Layer E v2 150/150 adjudicated (2026-08-06 restore); audit human_review_freeze_ready=true",
            "stage3_58_58": {
                "manifest": str(FROZEN_STAGE3_MANIFEST.relative_to(ROOT).as_posix()),
                "sha256": _sha256(FROZEN_STAGE3_MANIFEST),
            },
        },
        "proposed_contract_changes": PROPOSED_CHANGES,
        "dry_run_gate_check": {
            "before": gate_before,
            "after": gate_after,
        },
        "expected_blocker_outcome": {
            "removed": [
                "formal_gold_publication_paused (publication gate enters whitelist)",
                "stage3_benchmark_not_locked (stage3.status becomes locked)",
            ],
            "remaining": [
                "final_experiment_not_ready",
                "formal_methods_not_ready",
                "formal_capsule_not_frozen",
            ],
        },
        "formal_gold_publication_vs_method_correctness": {
            "note": "formal Gold publication and method correctness are DIFFERENT gates: the Stage 3 data/Gold lock can be satisfied now, "
                    "while the formal Oracle remains blocked by S1.7/S2.13 and the missing true Gold Rule/Process Records "
                    "(s37_oracle_readiness_v1.json); publication does NOT imply method readiness",
        },
        "rollback": [
            "git revert the contract change commit or restore the previous contract blob",
            "re-run audit_project.py: the gate returns to the blocked state",
            "no experiment artifacts are touched by the contract flip itself",
        ],
        "authorization_sentence": (
            "I authorize the machine-contract change that sets /stage3/status to 'locked', replaces "
            "/stage2_dataset/freeze_policy with the re-locked policy (governance content preserved), and "
            "sets /formal_gold_publication_gate/status to 'ready_for_formal_gold_publication', thereby "
            "enabling formal Gold publication (dry-run packet formal_gold_authorization_packet_v2)."
        ),
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md_lines = [
        "# Formal Gold 用户授权包 v2（DRY-RUN，未修改任何合同）",
        "",
        f"- packet_id: {packet['packet_id']}；dry_run=true；contract_not_modified=true；contract sha256={packet['contract_sha256_before'][:16]}...",
        "",
        "## 拟议修改（JSON Pointer，完整 before/after）",
    ]
    for ch in PROPOSED_CHANGES:
        md_lines.append(f"- `{ch['pointer']}`")
        md_lines.append(f"  - before: `{ch['before_full']}`")
        md_lines.append(f"  - after : `{ch['after_full']}`")
        md_lines.append(f"  - 依据: {ch['why_eligible']}")
    md_lines += [
        "",
        "## 临时副本门禁校验（等价机器检查）",
        f"- before: formal_gold_publication_ready={gate_before['formal_gold_publication_ready']}",
        f"- after : formal_gold_publication_ready={gate_after['formal_gold_publication_ready']}",
        f"- preconditions(after): {json.dumps(gate_after['preconditions'], ensure_ascii=False)}",
        "",
        "## 预期 blocker",
        f"- 消除: {json.dumps(packet['expected_blocker_outcome']['removed'], ensure_ascii=False)}",
        f"- 保留: {json.dumps(packet['expected_blocker_outcome']['remaining'], ensure_ascii=False)}",
        "",
        "## formal Gold publication 与方法正确性是不同门禁",
        f"- {packet['formal_gold_publication_vs_method_correctness']['note']}",
        "",
        "## 回滚",
        "- git revert 合同变更 commit 或恢复合同 blob；重跑 audit 即回到 blocked",
        "",
        "## 授权句",
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
