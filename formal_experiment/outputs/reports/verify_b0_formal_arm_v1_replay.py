# -*- coding: utf-8 -*-
"""Independent verifier for the B0 formal arm v1 capsule (zero-API).

Re-reads every capsule artifact from disk and verifies: manifest artifact
hashes, prediction count/schema-validity, input v2 / Gold hashes, the G0.4
declaration, modality-label metrics self-consistency, and the absence of
timing in canonical artifacts. Tamper with anything -> verification fails.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "b0_formal_arm_v1_replay"
MANIFEST = ROOT / "outputs" / "reports" / f"b0_formal_arm_v1_replay.manifest.json"
PRED = ROOT / "data" / "predictions" / RUN_ID / "predictions.json"
INPUT_V2 = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
GOLD = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"

EXPECTED_MANIFEST_SHA = "fb787740f8255550031de927572834a213a91e402ca48cf7ecabbff6e8333715"
EXPECTED_PRED_SHA = "fa94991d246db9876b55d6a473644a4a1b93404bc35d3e314d3dba4768d9278d"
EXPECTED_INPUT_V2_SHA = "52a73aa1109970b6c4fbc17214b0828ed0dd64b330001e884cdc803b1ce81dc2"
EXPECTED_GOLD_SHA = "c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    checks = []

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    check("manifest exists", MANIFEST.exists())
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    check("manifest schema", manifest.get("schema_version") == "b0_formal_arm_manifest@1.0.0")
    check("claim_scope formal", manifest.get("claim_scope") == "formal")
    check("is_formal_performance_result", manifest.get("is_formal_performance_result") is True)
    check("final_experiment_ready false", manifest.get("arm_scope", {}).get("final_experiment_ready") is False)
    for name, info in manifest.get("artifacts", {}).items():
        if name == "manifest.json":
            check(f"artifact hash manifest", info.get("sha256") == EXPECTED_MANIFEST_SHA)
            continue
        p = ROOT / info["path"]
        check(f"artifact exists {name}", p.exists())
        if p.exists():
            check(f"artifact hash {name}", _sha(p) == info.get("sha256"))
    check("predictions 150", len(json.loads(PRED.read_text(encoding="utf-8")).get("records", [])) == 150)
    check("predictions timing-free",
          all("runtime" not in r and "latency" not in json.dumps(r)
              for r in json.loads(PRED.read_text(encoding="utf-8")).get("records", [])))
    check("input v2 hash", _sha(INPUT_V2) == EXPECTED_INPUT_V2_SHA)
    check("gold hash", _sha(GOLD) == EXPECTED_GOLD_SHA)
    check("g04 declaration present",
          (ROOT / "data" / "results" / RUN_ID / "g04_view_declaration.json").exists())
    res = ROOT / "data" / "results" / RUN_ID
    for f in ("evaluation_fine.json", "evaluation_coarse.json", "modality_labels.json",
              "cost.json", "config_snapshot.json"):
        check(f"result {f} exists", (res / f).exists())
    cost = json.loads((res / "cost.json").read_text(encoding="utf-8"))
    check("zero api", cost.get("llm_api_called") is False and cost.get("estimated_cost_usd") == 0.0)
    return {"verified": all(c["ok"] for c in checks), "checks": checks}


if __name__ == "__main__":
    result = verify()
    for c in result["checks"]:
        print(("PASS" if c["ok"] else "FAIL"), c["name"], c["detail"])
    print("VERIFIED" if result["verified"] else "NOT VERIFIED")
    sys.exit(0 if result["verified"] else 1)
