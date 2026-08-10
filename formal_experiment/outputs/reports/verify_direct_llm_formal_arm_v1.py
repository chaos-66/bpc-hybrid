# -*- coding: utf-8 -*-
"""Independent verifier for the direct_llm_formal_arm_v1 snapshot formal arm capsule."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "direct_llm_formal_arm_v1"
MANIFEST = ROOT / "outputs" / "reports" / f"{RUN_ID}.manifest.json"
PRED = ROOT / "data" / "predictions" / RUN_ID / "predictions.json"
INPUT_V2 = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
GOLD = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"

EXPECTED_MANIFEST_SHA = "f0f86318259de87c9557781b69d2573a13bb25469db194905cfc216fef94d133"
EXPECTED_PRED_SHA = "bbadb6834572e58fb8321204b3bc975c887d23d9ae60bd804bf91137bb46072b"
EXPECTED_INPUT_V2_SHA = "52a73aa1109970b6c4fbc17214b0828ed0dd64b330001e884cdc803b1ce81dc2"
EXPECTED_GOLD_SHA = "c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100"
EXPECTED_METHOD = "direct_llm"
EXPECTED_HIST_LLM_CALLS = 150


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    checks = []

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    check("manifest exists", MANIFEST.exists())
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    check("manifest schema", manifest.get("schema_version") == "snapshot_formal_arm_manifest@1.0.0")
    check("claim_scope formal", manifest.get("claim_scope") == "formal")
    check("is_formal_performance_result", manifest.get("is_formal_performance_result") is True)
    check("method", manifest.get("method_id") == EXPECTED_METHOD)
    check("zero new calls", manifest.get("zero_api", {}).get("new_llm_calls") == 0)
    check("historical calls", manifest.get("zero_api", {}).get("historical_llm_calls") == EXPECTED_HIST_LLM_CALLS)
    check("manifest hash", _sha(MANIFEST) == EXPECTED_MANIFEST_SHA)
    check("predictions hash", _sha(PRED) == EXPECTED_PRED_SHA)
    check("input v2 hash", _sha(INPUT_V2) == EXPECTED_INPUT_V2_SHA)
    check("gold hash", _sha(GOLD) == EXPECTED_GOLD_SHA)
    pred = json.loads(PRED.read_text(encoding="utf-8"))
    check("predictions 150", len(pred.get("records", [])) == 150)
    check("predictions timing-free",
          all("runtime" not in r and "latency" not in json.dumps(r)
              for r in pred.get("records", [])))
    res = ROOT / "data" / "results" / RUN_ID
    for f in ("evaluation_fine.json", "evaluation_coarse.json",
              "modality_labels.json", "g04_view_declaration.json",
              "cost.json", "config_snapshot.json"):
        check(f"result {f} exists", (res / f).exists())
    cost = json.loads((res / "cost.json").read_text(encoding="utf-8"))
    check("zero api cost", cost.get("llm_api_called") is False
          and cost.get("new_llm_api_calls") == 0)
    return {"verified": all(c["ok"] for c in checks), "checks": checks}


if __name__ == "__main__":
    result = verify()
    for c in result["checks"]:
        print(("PASS" if c["ok"] else "FAIL"), c["name"], c["detail"])
    print("VERIFIED" if result["verified"] else "NOT VERIFIED")
    sys.exit(0 if result["verified"] else 1)
