# -*- coding: utf-8 -*-
"""Fail-closed verifier for the S1.7 freeze AUTHORIZATION (2026-08-13).

Recomputes everything from disk:
  1. the authorization manifest exists, authorized_by_user=true,
     status=freeze_applied
  2. the exact authorization sentences (ZH verbatim + EN reference) are
     recorded
  3. every bound hash matches the on-disk file (P2 config/impl, predictions
     locked+authoritative, numeric body, v2 report, capsule, Gold+manifest,
     audit, claim correction, S1.7 v2 packet, membership, process records,
     7 BPMN)
  4. safety status: post_evaluation_tuning=false, strict_test_blind=false,
     held_out_generalization_claim_allowed=false, runtime_gold_read=false
  5. exclusions present (no Stage 3 Oracle authorization, no LLM/API)
  6. the S1.7 dry-run v2 packet is still dry_run_not_applied (the freeze is
     recorded by THIS manifest, not by mutating the readiness packet)

Exit 0 iff everything verifies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

AUTH = ROOT / "outputs" / "reports" / "s1_7_freezer_authorization_v1.manifest.json"
V2_PACKET = ROOT / "outputs" / "reports" / "s1_7_freezer_readiness_dry_run_v2.json"

USER_SENTENCE_ZH = (
    "我知悉P2是在Stage 1 Process Gold形成后开发，且至少三条目标活动标签曾进入"
    "开发测试，其中至少一条测试三元组与人工Gold一致；我确认S1.6指标仅作为固定"
    "GDPR-7上的正式描述性组件评价，不作为held-out泛化证据。我授权正式冻结S1.7"
    "现有资产：评价后未再调优的P2锁定方法、现有P0/P1/P2预测、原始指标、Stage 1 "
    "Process Gold及已验证的正式评价capsule。冻结不得修改P2、不得选择性重算结果、"
    "不得调用LLM/API、不得修改Stage 2/Stage 3 Gold或experiment contract，也"
    "不自动授权Stage 3 Oracle。")


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "0" * 64


def verify() -> dict:
    checks = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    try:
        auth = json.loads(AUTH.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        check("authorization manifest readable", False, str(exc))
        return {"verified": False, "checks": checks}

    check("authorized by user + freeze applied",
          auth.get("authorized_by_user") is True
          and auth.get("status") == "freeze_applied")
    check("authorization sentence zh verbatim",
          auth.get("authorization_sentence_zh") == USER_SENTENCE_ZH)
    check("authorization sentence en present",
          "target-aware" in auth.get("authorization_sentence_en", "")
          or "developed AFTER the Stage 1 Process Gold" in
          auth.get("authorization_sentence_en", ""))

    # bindings
    binds = auth.get("bindings", {})
    hashes_ok = True
    for rel, digest in binds.get("hashes", {}).items():
        path = ROOT / rel
        if not path.exists() or _sha256(path) != digest:
            hashes_ok = False
    check("all bound hashes match disk", hashes_ok)
    check("membership payload binding",
          binds.get("membership_payload_sha256")
          == json.loads((ROOT / "configs" / "datasets"
                         / "stage1_stage3_gdpr7_v1.json")
                        .read_text(encoding="utf-8"))["membership"][
              "membership_payload_sha256"])
    verbs = json.loads((ROOT / "configs" / "resources"
                        / "english_verb_roots_v1.json")
                       .read_text(encoding="utf-8"))["verbs"]
    check("verb count 200/200",
          binds.get("verb_list_count")
          == {"total": 200, "unique": 200}
          and len(verbs) == 200 and len(set(verbs)) == 200)

    # key byte-locks (P2 / predictions / metrics / Gold)
    check("P2 config byte-lock",
          binds.get("hashes", {}).get("configs/stage1_label_p2_v1.json")
          == "59ac4e8ec2b02632366cac229b5538c4f243910f6a371b5e14e1be65817cc49d")
    check("P2 implementation byte-lock",
          binds.get("hashes", {}).get(
              "src/bpc_hybrid/stage1_label_semantics_p2.py")
          == "c95910efe80992e0b49be7859e9c9a7b48493e9c794472ed86bcb129d2a5a3c2")
    check("predictions byte-lock (locked + authoritative)",
          binds.get("hashes", {}).get(
              "outputs/development/stage1_predictions/formal_predictions_v1.json")
          == "79a9b2c17185d63dc5ab5d9c47c8c592469b30f3cf7298740e593838166a94a8"
          and binds.get("hashes", {}).get(
              "data/predictions/stage1_formal_v1/formal_predictions_v1.json")
          == "79a9b2c17185d63dc5ab5d9c47c8c592469b30f3cf7298740e593838166a94a8")
    check("metrics numeric body bound",
          binds.get("hashes", {}).get(
              "data/results/stage1_formal_v1/stage1_formal_evaluation_v1.json")
          == "a072db39b37167d76aa4e49b9845b5b563255d980b9ee00cd811f43c116a7392")
    check("Stage 1 Gold byte-lock",
          binds.get("hashes", {}).get(
              "data/gold/stage1/process_records/stage1_process_gold_v1.json")
          == "f33aa857a0796d0517a9d04cc96b0a4f316202603fe0adf66693aeb5cb444bca")

    # safety
    safety = auth.get("safety", {})
    check("safety: target-aware status",
          safety.get("target_labels_seen_during_development") is True
          and safety.get("strict_test_blind") is False
          and safety.get("held_out_generalization_claim_allowed") is False
          and safety.get("post_evaluation_tuning") is False
          and safety.get("runtime_gold_read") is False
          and safety.get("evaluation_role")
          == "formal_descriptive_component_evaluation_on_fixed_GDPR7")

    # exclusions
    exclusions = " ".join(auth.get("exclusions", []))
    check("exclusions: no P2 change / no selective recompute / no LLM-API",
          "no P2 modification" in exclusions
          and "no selective result recomputation" in exclusions
          and "no LLM/API calls" in exclusions)
    check("exclusions: no Stage 2/3 Gold / contract / Oracle",
          "no Stage 2/Stage 3 Gold modification" in exclusions
          and "no experiment contract modification" in exclusions
          and "no Stage 3 Oracle authorization" in exclusions)

    # readiness packet stays dry-run (the freeze is recorded here)
    v2 = json.loads(V2_PACKET.read_text(encoding="utf-8"))
    check("S1.7 readiness v2 packet remains dry_run_not_applied",
          v2.get("status") == "dry_run_not_applied")

    # zero API
    check("zero API", auth.get("zero_api", {}).get("new_llm_api_calls") == 0)

    return {"verified": all(c["ok"] for c in checks), "checks": checks,
            "auth_sha256": _sha256(AUTH)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        for c in result["checks"]:
            print(("PASS" if c["ok"] else "FAIL"), c["name"], c["detail"])
        print("S1.7 FREEZE AUTHORIZATION VERIFIED" if result["verified"]
              else "S1.7 FREEZE AUTHORIZATION NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
