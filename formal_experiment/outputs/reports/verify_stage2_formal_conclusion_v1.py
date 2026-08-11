# -*- coding: utf-8 -*-
"""Independent verifier for the Stage 2 formal conclusion v1."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONCLUSION = ROOT / "outputs" / "reports" / "stage2_formal_conclusion_v1.json"
MANIFEST = ROOT / "outputs" / "reports" / "stage2_formal_conclusion_v1.manifest.json"
REPORT = ROOT / "outputs" / "reports" / "stage2_formal_three_method_comparison_v1.json"

EXPECTED_CONCLUSION_SHA = "d882a5e24913db3a679c77d253f4e54db2abd38c2aac0151706df141ef4a27d5"
EXPECTED_MANIFEST_SHA = "6d2cf84dde4124d4e9e49c6be5224972d574560e1f09ef368cb24e54ec5533c3"
EXPECTED_REPORT_SHA = "c9d76544a36ca4c27939d8090a8bfafc6da690a2e5d2b5d09624b27b4f9cf740"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    checks = []

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    check("conclusion exists", CONCLUSION.exists())
    check("conclusion hash", _sha(CONCLUSION) == EXPECTED_CONCLUSION_SHA)
    check("manifest exists", MANIFEST.exists())
    check("manifest hash", _sha(MANIFEST) == EXPECTED_MANIFEST_SHA)
    check("report hash bound", _sha(REPORT) == EXPECTED_REPORT_SHA)
    c = json.loads(CONCLUSION.read_text(encoding="utf-8"))
    check("schema", c.get("schema_version") == "stage2_formal_conclusion@1.0.0")
    check("project date", c.get("project_date") == "2026-08-11")
    check("conclusions non-empty", bool(c.get("conclusions")))
    check("all supported", all(x.get("supported") for x in c.get("conclusions", [])))
    check("disclosures", c.get("disclosures", {}).get("no_statistical_significance_inference") is not None)
    check("not exact reproduction",
          "NOT an exact reproduction" in c.get("reconstruction_disclosure", ""))
    check("B0-R5 verified", c.get("task_status", {}).get("B0-R5", "").startswith("verified"))
    check("D1-R5 verified", c.get("task_status", {}).get("D1-R5", "").startswith("verified"))
    check("H1 comparison-only", "comparison-only" in c.get("task_status", {}).get("H1", ""))
    check("zero new calls", c.get("zero_api", {}).get("new_llm_api_calls") == 0)
    return {"verified": all(c["ok"] for c in checks), "checks": checks}


if __name__ == "__main__":
    result = verify()
    for c in result["checks"]:
        print(("PASS" if c["ok"] else "FAIL"), c["name"], c["detail"])
    print("VERIFIED" if result["verified"] else "NOT VERIFIED")
    sys.exit(0 if result["verified"] else 1)
