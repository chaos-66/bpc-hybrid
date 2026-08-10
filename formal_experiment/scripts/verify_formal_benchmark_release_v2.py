# -*- coding: utf-8 -*-
"""Independent verifier for the formal benchmark release v2 (zero-API).

Re-reads every published artifact from disk and re-verifies them WITHOUT
trusting the publisher's in-memory payloads:

- release manifest artifact hashes / byte sizes / record counts
- v2 input schema shape, 150 unique sample_ids, membership payload
- v2 approved_text_en / raw_text_de byte-identical to frozen Layer E
- Stage 2 Gold decisions identical to frozen Layer E decisions, span text
  re-anchors into approved_text_en
- Stage 3 matching/violation Gold ids identical to frozen correction
- forbidden-field scan (no LLM drafts / candidate fields / review state /
  review evidence in any published artifact)
- modality restricted data did NOT enter the formal publication directories
- publisher/validator/schema/config implementation hashes match on disk
- git / versioned capsule state of the published artifacts

Exit code 0 when everything verifies, 1 otherwise.  Also importable:
    from scripts.verify_formal_benchmark_release_v2 import verify_release
Returns a dict {"verified": bool, "checks": [{name, ok, detail}]}.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

RELEASE_MANIFEST = ROOT / "outputs" / "reports" / "formal_benchmark_release_v2.manifest.json"
V2_INPUT = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
V1_INPUT = ROOT / "data" / "input" / "estg150_formal_input_v1.json"
LAYER_E = ROOT / "data" / "development" / "human_review" / "estg_150_human_correction_v1.json"
MEMBERSHIP_HASHES = ROOT / "data" / "development" / "estg" / "estg_150_membership_hashes.json"
GOLD_STAGE2 = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
GOLD_MATCHING = ROOT / "data" / "gold" / "stage3" / "stage3_matching_gold_v1.json"
GOLD_VIOLATION = ROOT / "data" / "gold" / "stage3" / "stage3_violation_gold_v1.json"
STAGE3_CORRECTION = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"
STAGE3_INFERENCE = ROOT / "data" / "development" / "human_review" / "stage3_gold_inference_v1.json"
STAGE2_SCHEMA = ROOT / "configs" / "schemas" / "stage2_formal_gold.schema.json"
STAGE3_SCHEMA = ROOT / "configs" / "schemas" / "stage3_formal_gold.schema.json"
PREDICTION_SCHEMA = ROOT / "configs" / "schemas" / "stage2_prediction.schema.json"
INPUT_V2_SCHEMA = ROOT / "configs" / "schemas" / "estg150_formal_inference_input_v2.schema.json"
METHODS_CONFIG = ROOT / "configs" / "methods.json"
EXPERIMENT_CONTRACT = ROOT / "configs" / "experiment_contract.json"
PUBLISHER = ROOT / "scripts" / "publish_formal_benchmark_v2.py"
VERIFIER = ROOT / "scripts" / "verify_formal_benchmark_release_v2.py"

# adjudication / evaluation content that must never appear in published artifacts
FORBIDDEN_GOLD_FIELDS = ("llm_candidate", "candidate_text_en",
                         "candidate_text_en_sha256", "approved_text_en_history",
                         "_stale", "notes", "review_state", "human_correction")
FORBIDDEN_V2_FIELDS = ("decisions", "human_correction", "llm_candidate",
                       "candidate_text_en", "candidate_text_en_sha256",
                       "approved_text_en_history", "review_state", "clauses",
                       "order_relations", "evidence", "notes")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _scan_forbidden(obj: Any, forbidden: tuple[str, ...], path: str = "",
                    hits: list[str] | None = None) -> list[str]:
    if hits is None:
        hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in forbidden:
                hits.append(f"{path}/{k}")
            _scan_forbidden(v, forbidden, f"{path}/{k}", hits)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _scan_forbidden(v, forbidden, f"{path}[{i}]", hits)
    return hits


def verify_release() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    manifest = _load_json(RELEASE_MANIFEST)
    check("release manifest exists", bool(manifest), str(RELEASE_MANIFEST))
    if not manifest:
        return {"verified": False, "checks": checks}

    check("release manifest schema", manifest.get("schema_version")
          == "formal_benchmark_release_manifest@2.0.0")
    check("release identity", manifest.get("release") == "formal_benchmark_release_v2")

    # --- 1. artifact hashes / sizes / counts re-read from disk
    artifacts = manifest.get("artifacts", {})
    required_artifacts = {
        "estg150_formal_input_v1.json": V1_INPUT,
        "estg150_formal_inference_input_v2.json": V2_INPUT,
        "stage2_gold": GOLD_STAGE2,
        "stage3_matching_gold": GOLD_MATCHING,
        "stage3_violation_gold": GOLD_VIOLATION,
    }
    for key, path in required_artifacts.items():
        info = artifacts.get(key, {})
        disk_sha = _sha256_file(path) if path.exists() else ""
        check(f"artifact exists: {key}", path.exists())
        check(f"artifact hash: {key}",
              disk_sha == info.get("sha256"),
              f"disk={disk_sha[:16]} manifest={str(info.get('sha256', ''))[:16]}")
        check(f"artifact size: {key}",
              path.stat().st_size == info.get("byte_size") if path.exists() else False)
        check(f"artifact schema recorded: {key}", bool(info.get("schema")))

    # --- 2. membership: 150 / 25 / 33
    v2 = _load_json(V2_INPUT)
    gold2 = _load_json(GOLD_STAGE2)
    matching = _load_json(GOLD_MATCHING)
    violation = _load_json(GOLD_VIOLATION)
    membership = _load_json(MEMBERSHIP_HASHES).get("selected_membership", {})
    check("v2 schema version",
          v2.get("schema_version") == "estg150_formal_inference_input@2.0.0",
          str(v2.get("schema_version")))
    check("v2 count == 150", v2.get("count") == 150 and len(v2.get("records", [])) == 150)
    check("v2 sample_ids unique",
          len({r["sample_id"] for r in v2.get("records", [])}) == 150)
    check("gold stage2 count == 150",
          len(gold2.get("records", [])) == 150)
    check("gold matching count == 25",
          matching.get("count") == 25 and len(matching.get("items", [])) == 25)
    check("gold violation count == 33",
          violation.get("count") == 33 and len(violation.get("items", [])) == 33)
    v2_membership = v2.get("membership_payload_sha256")
    check("v2 membership payload == frozen",
          v2_membership == membership.get("membership_payload_sha256"))
    check("gold stage2 membership == frozen",
          gold2.get("membership", {}).get("payload_sha256")
          == membership.get("membership_payload_sha256"))

    # --- 3. v2 text provenance vs frozen Layer E
    layer_e = _load_json(LAYER_E)
    le_by_id = {r["sample_id"]: r for r in layer_e.get("records", [])}
    text_mismatch = 0
    for rec in v2.get("records", []):
        le = le_by_id.get(rec["sample_id"])
        if le is None:
            text_mismatch += 1
            continue
        if le.get("approved_text_en") != rec.get("approved_text_en"):
            text_mismatch += 1
        if le.get("raw_text_de") != rec.get("raw_text_de"):
            text_mismatch += 1
        if _sha256_bytes(rec.get("approved_text_en", "").encode("utf-8")) \
                != rec.get("input_text_sha256"):
            text_mismatch += 1
    check("v2 text provenance vs Layer E (150/150)", text_mismatch == 0,
          f"{text_mismatch} mismatches")

    # --- 4. Gold decisions identical to frozen Layer E, spans re-anchor
    gold_sid = {r["sample_id"] for r in gold2.get("records", [])}
    check("gold ids == v2 ids",
          gold_sid == {r["sample_id"] for r in v2.get("records", [])})
    decision_mismatch = 0
    span_fail = 0
    for rec in gold2.get("records", []):
        le = le_by_id.get(rec["sample_id"], {})
        if le.get("decisions") != rec.get("decisions"):
            decision_mismatch += 1
        ate = rec.get("approved_text_en", "")
        for clause in rec.get("clauses", []):
            cs = clause.get("clause_span", {})
            if ate[cs.get("start", 0):cs.get("end", 0)] != cs.get("text"):
                span_fail += 1
            for field in ("actors", "actions", "conditions", "constraints",
                          "exceptions"):
                for item in clause.get(field, []):
                    if ate[item.get("start", 0):item.get("end", 0)] != item.get("text"):
                        span_fail += 1
    check("gold decisions == frozen Layer E decisions (150/150)",
          decision_mismatch == 0, f"{decision_mismatch} mismatches")
    check("gold spans re-anchor into approved_text_en", span_fail == 0,
          f"{span_fail} span failures")

    # --- 5. Stage 3 ids vs frozen correction
    corr = _load_json(STAGE3_CORRECTION)
    inf = _load_json(STAGE3_INFERENCE)
    corr_m = {i["item_id"] for i in corr.get("matching_items", [])}
    corr_v = {i["item_id"] for i in corr.get("violation_items", [])}
    gold_m = {i["item_id"] for i in matching.get("items", [])}
    gold_v = {i["item_id"] for i in violation.get("items", [])}
    check("stage3 matching ids == frozen correction", gold_m == corr_m)
    check("stage3 violation ids == frozen correction", gold_v == corr_v)
    inf_m = {i["item_id"] for i in inf.get("matching_items", [])}
    inf_v = {i["item_id"] for i in inf.get("violation_items", [])}
    check("stage3 ids == frozen inference pack", gold_m == inf_m and gold_v == inf_v)

    # --- 6. forbidden-field scan
    v2_hits = _scan_forbidden(v2, FORBIDDEN_V2_FIELDS)
    check("v2 free of adjudication/candidate fields", not v2_hits,
          str(v2_hits[:5]))
    gold_hits = _scan_forbidden(gold2, FORBIDDEN_GOLD_FIELDS)
    check("stage2 gold decision-only (no drafts/metadata)", not gold_hits,
          str(gold_hits[:5]))
    m3_hits = _scan_forbidden(matching, FORBIDDEN_GOLD_FIELDS)
    v3_hits = _scan_forbidden(violation, FORBIDDEN_GOLD_FIELDS)
    check("stage3 gold decision-only", not m3_hits and not v3_hits,
          str((m3_hits + v3_hits)[:5]))

    # --- 7. modality restricted data did NOT enter formal directories
    formal_dirs = [ROOT / "data" / "gold", ROOT / "data" / "input"]
    modality_leak = []
    for d in formal_dirs:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if f.is_file() and f.name != ".gitkeep":
                name = f.name.lower()
                if "modality" in name or "estg_sent_vec" in name:
                    modality_leak.append(str(f.relative_to(ROOT)))
    check("modality restricted data not in formal dirs", not modality_leak,
          str(modality_leak))

    # --- 8. implementation hashes match on disk
    impl = manifest.get("implementation_hashes", {})
    impl_disk = {
        "publisher": _sha256_file(PUBLISHER) if PUBLISHER.exists() else "",
        "validator": _sha256_file(VERIFIER) if VERIFIER.exists() else "",
        "input_v2_schema": _sha256_file(INPUT_V2_SCHEMA) if INPUT_V2_SCHEMA.exists() else "",
        "stage2_gold_schema": _sha256_file(STAGE2_SCHEMA) if STAGE2_SCHEMA.exists() else "",
        "stage3_gold_schema": _sha256_file(STAGE3_SCHEMA) if STAGE3_SCHEMA.exists() else "",
        "prediction_schema": _sha256_file(PREDICTION_SCHEMA) if PREDICTION_SCHEMA.exists() else "",
        "methods_config": _sha256_file(METHODS_CONFIG) if METHODS_CONFIG.exists() else "",
        "experiment_contract": _sha256_file(EXPERIMENT_CONTRACT) if EXPERIMENT_CONTRACT.exists() else "",
    }
    for key, expected in impl.items():
        check(f"implementation hash: {key}",
              impl_disk.get(key) == expected,
              f"disk={str(impl_disk.get(key, ''))[:16]} manifest={str(expected)[:16]}")

    # --- 9. git / versioned capsule state
    try:
        import subprocess
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "AGENTS.md"],
            cwd=ROOT, capture_output=True)
        capsule_tracked = tracked.returncode == 0
    except Exception:  # pragma: no cover
        capsule_tracked = False
    check("formal capsule git-tracked", capsule_tracked)
    check("release manifest git commit recorded", bool(manifest.get("git", {}).get("commit")))

    # --- 10. v1 limitation declared
    check("v1 limitation declared",
          "membership-only; not sufficient as executable model input"
          in json.dumps(manifest.get("v1_limitation", {}), ensure_ascii=False))

    verified = all(c["ok"] for c in checks)
    return {"verified": verified, "checks": checks}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print JSON result")
    args = parser.parse_args()
    result = verify_release()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        for c in result["checks"]:
            print(("PASS" if c["ok"] else "FAIL"), c["name"], c["detail"])
        print("VERIFIED" if result["verified"] else "NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
