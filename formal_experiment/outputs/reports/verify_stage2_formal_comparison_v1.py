# -*- coding: utf-8 -*-
"""Independent verifier for the formal three-method comparison v1."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "outputs" / "reports" / "stage2_formal_three_method_comparison_v1.json"
MANIFEST = ROOT / "outputs" / "reports" / "stage2_formal_three_method_comparison_v1.manifest.json"
INPUT_V2 = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
GOLD = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"

EXPECTED_REPORT_SHA = "c9d76544a36ca4c27939d8090a8bfafc6da690a2e5d2b5d09624b27b4f9cf740"
EXPECTED_MANIFEST_SHA = "dc41eb4bee6b1cd06afc184f27ae63dcd9e93b6e5b4869a2d3e6b876d47236c6"
EXPECTED_INPUT_SHA = "52a73aa1109970b6c4fbc17214b0828ed0dd64b330001e884cdc803b1ce81dc2"
EXPECTED_GOLD_SHA = "c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    checks = []

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    check("report exists", REPORT.exists())
    check("report hash", _sha(REPORT) == EXPECTED_REPORT_SHA)
    check("manifest exists", MANIFEST.exists())
    check("manifest hash", _sha(MANIFEST) == EXPECTED_MANIFEST_SHA)
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    check("schema", report.get("schema_version")
          == "stage2_formal_three_method_comparison@1.0.0")
    check("input v2 hash", report["input"]["sha256"] == EXPECTED_INPUT_SHA)
    check("gold hash", report["gold"]["sha256"] == EXPECTED_GOLD_SHA)
    check("three methods", set(report["methods"]) ==
          {"sun_rule_only", "direct_llm", "sun_llm_fallback"})
    check("zero new calls", report["zero_api"]["new_llm_api_calls"] == 0)
    check("main report five fields",
          all(set(m["main_view_coarse_five_fields"]) ==
              {"actor", "action", "condition", "constraint", "exception"}
              for m in report["methods"].values()))
    check("modality labels separate",
          all("accuracy" in m["modality_labels"]
              for m in report["methods"].values()))
    check("no historical six-field aggregate mixed in",
          "historical_six_field_aggregate" in
          report["evaluation_contract"] and
          "development provenance" in
          report["evaluation_contract"]["historical_six_field_aggregate"])
    check("h1 comparison-only declared",
          report["methods"]["sun_llm_fallback"]["role"]
          == "comparison_arm_only")
    check("conclusions present", bool(report["conclusions"]))
    return {"verified": all(c["ok"] for c in checks), "checks": checks}


if __name__ == "__main__":
    result = verify()
    for c in result["checks"]:
        print(("PASS" if c["ok"] else "FAIL"), c["name"], c["detail"])
    print("VERIFIED" if result["verified"] else "NOT VERIFIED")
    sys.exit(0 if result["verified"] else 1)
