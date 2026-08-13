# -*- coding: utf-8 -*-
"""Fail-closed verifier for the S1 target-overlap audit (2026-08-13).

Recomputes every audit fact from disk:
  - HISTORICAL test file (git blob c704bbc) for the historical overlap facts
  - CURRENT test file for the corrected zero-overlap state
  - GDPR-7 process records (45 instances / 41 unique raw labels)
  - Stage 1 Process Gold (expectation comparison)
  - verb list (200/200)

Enforces the tamper invariants: historical overlap counts/labels must match
the recomputation; current overlap must be zero; verb count must be 200/200;
conclusions must be target-aware (strict_test_blind=false, ...).

Exit 0 iff everything verifies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

AUDIT = ROOT / "outputs" / "reports" / "s1_p2_target_overlap_audit_v1.json"
TEST_FILE = ROOT / "tests" / "test_s1_3_p2_label_semantics.py"
RECORDS_FILE = (ROOT / "data" / "development" / "human_review"
                / "stage1_gdpr7_process_records_v1.json")
GOLD_FILE = (ROOT / "data" / "gold" / "stage1" / "process_records"
             / "stage1_process_gold_v1.json")
VERB_FILE = ROOT / "configs" / "resources" / "english_verb_roots_v1.json"
HISTORICAL_COMMIT = "c704bbc527a91e89f0a6da7cabbd637e5ccada12"

PUNCT = re.compile(r'[\s.,;:!?()\[\]{}<>"\'`~@#$%^&*+=|\\/_-]+')


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError:
        return "0" * 64


def _norm_ws(text: str) -> str:
    return " ".join(text.split())


def _casefold(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def _norm_punct(text: str) -> str:
    return PUNCT.sub(" ", _norm_ws(text)).strip().casefold()


def _historical_source() -> tuple[bytes, str]:
    blob = subprocess.run(
        ["git", "show", f"{HISTORICAL_COMMIT}:"
         "formal_experiment/tests/test_s1_3_p2_label_semantics.py"],
        capture_output=True, check=True).stdout
    return blob, blob.decode("utf-8")


def _extract_labels(source: str) -> list[str]:
    labels = set()
    for m in re.finditer(r'"act_\w+":\s*"([^"]*)"', source):
        labels.add(m.group(1))
    for m in re.finditer(r'_analyze_label\(\s*"([^"]+)"\s*,', source):
        labels.add(m.group(1))
    return sorted(labels)


def _overlaps(synthetic: list[str], gdpr: list[str]) -> dict:
    g = set(gdpr)
    return {
        "exact": sorted(set(synthetic) & g),
        "ws": sorted({_norm_ws(x) for x in synthetic}
                     & {_norm_ws(x) for x in gdpr}),
        "cf": sorted({_casefold(x) for x in synthetic}
                     & {_casefold(x) for x in gdpr}),
        "pn": sorted({_norm_punct(x) for x in synthetic}
                     & {_norm_punct(x) for x in gdpr}),
    }


def verify() -> dict:
    checks = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    hist_blob, hist_src = _historical_source()
    cur_src = TEST_FILE.read_text(encoding="utf-8")
    records = json.loads(RECORDS_FILE.read_text(encoding="utf-8"))["records"]
    instances = [a["name"] for r in records for a in r["activities"]]
    assert len(instances) == 45
    gdpr_unique = sorted(set(instances))

    # input bindings
    inputs = audit.get("input_files", {})
    check("historical test file bound to c704bbc blob",
          inputs.get("test_file_historical", {}).get("commit")
          == HISTORICAL_COMMIT
          and inputs.get("test_file_historical", {}).get("sha256")
          == _sha256_bytes(hist_blob))
    check("current test file binding",
          inputs.get("test_file_current", {}).get("sha256")
          == _sha256(TEST_FILE))
    check("process records / gold / verb bindings",
          inputs.get("process_records", {}).get("sha256")
          == _sha256(RECORDS_FILE)
          and inputs.get("gold", {}).get("sha256") == _sha256(GOLD_FILE)
          and inputs.get("verb_list", {}).get("sha256") == _sha256(VERB_FILE))

    # historical overlap (target-aware development fact)
    hist_overlap = _overlaps(_extract_labels(hist_src), gdpr_unique)
    stored_hist = audit.get("overlap_historical", {})
    check("historical exact overlap = 3 required labels",
          stored_hist.get("exact", {}).get("count") == 3
          and set(stored_hist.get("exact", {}).get("labels", []))
          == {"Communication with data subject", "Rectify data",
              "Retrieve data"}
          and stored_hist.get("exact", {}).get("labels")
          == hist_overlap["exact"])
    check("historical normalized overlaps match recomputation",
          stored_hist.get("whitespace_folded", {}).get("labels")
          == hist_overlap["ws"]
          and stored_hist.get("casefolded", {}).get("labels")
          == hist_overlap["cf"]
          and stored_hist.get("punctuation_normalized", {}).get("labels")
          == hist_overlap["pn"])

    # current overlap must be ZERO (corrected fixtures)
    cur_overlap = _overlaps(_extract_labels(cur_src), gdpr_unique)
    stored_cur = audit.get("overlap_current", {})
    check("current overlap is zero (corrected fixtures)",
          stored_cur.get("exact", {}).get("count") == 0
          and stored_cur.get("exact", {}).get("labels") == []
          and cur_overlap["exact"] == []
          and cur_overlap["ws"] == []
          and cur_overlap["cf"] == []
          and cur_overlap["pn"] == [])

    # expectations vs Gold (from the historical test file)
    gold = json.loads(GOLD_FILE.read_text(encoding="utf-8"))["records"]
    gold_label_values = {}
    for rec in gold:
        gpr = rec["structure_annotation"]["gold_process_record"]
        acts = {a["id"]: a["name"] for a in gpr["activities"]}
        for la in rec["label_annotations"]:
            label = acts.get(la["activity_id"])
            if label is None:
                continue
            gold_label_values.setdefault(label, []).append({
                "process_id": rec["process_id"],
                "activity_id": la["activity_id"],
                "actor": (la.get("actor", {}).get("value")
                          if la.get("actor", {}).get("status") == "present"
                          else None),
                "action": (la.get("action", {}).get("value")
                           if la.get("action", {}).get("status") == "present"
                           else None),
                "business_object": (la.get("business_object", {}).get("value")
                                    if la.get("business_object", {}).get(
                                        "status") == "present" else None),
            })
    rows_ok = True
    for item in audit.get("overlap_expectations", []):
        gold_rows = gold_label_values.get(item["label"], [])
        if len(item.get("gold_rows", [])) != len(gold_rows):
            rows_ok = False
            continue
        for stored, g in zip(item["gold_rows"], gold_rows):
            if (stored["gold_actor"] != g["actor"]
                    or stored["gold_action"] != g["action"]
                    or stored["gold_business_object"] != g["business_object"]):
                rows_ok = False
    check("overlap expectations consistent with Gold", rows_ok)
    any_triple = any(
        row.get("triple_match") for item
        in audit.get("overlap_expectations", [])
        for row in item.get("gold_rows", []))
    check("at least one overlapping assertion equals human Gold triple",
          any_triple)

    # verb list 200/200
    verbs = json.loads(VERB_FILE.read_text(encoding="utf-8"))["verbs"]
    verb = audit.get("verb_list", {})
    check("verb count 200/200 (not 199)",
          verb.get("total_entries") == 200
          and verb.get("unique_entries") == 200
          and len(verbs) == 200
          and len(set(verbs)) == 200)

    # conclusions target-aware
    concl = audit.get("conclusions", {})
    check("conclusions: target-aware development",
          concl.get("development_was_target_aware") is True)
    check("conclusions: strict test-blind false",
          concl.get("strict_test_blind_supported") is False)
    check("conclusions: developer-blind false",
          concl.get("developer_blind_supported") is False)
    check("conclusions: held-out generalization not allowed",
          concl.get("held_out_generalization_claim_allowed") is False)
    check("conclusions: runtime isolation + no tuning hold",
          concl.get("runtime_gold_isolation_holds") is True
          and concl.get("no_post_evaluation_tuning_holds") is True)
    check("conclusions: metrics valid as fixed-GDPR7 descriptive",
          concl.get("metrics_valid_as_fixed_gdpr7_descriptive_component_evaluation")
          is True)

    # runtime boundary + timeline
    check("runtime gold read false",
          audit.get("runtime_read_boundary", {}).get("runtime_gold_read")
          is False)
    tl = audit.get("timeline", {})
    check("timeline ordered",
          tl.get("stage1_gold_published_commit")
          == "661f20b3e9e7924ecac3831709bb680a35cb6817"
          and tl.get("p2_lock_commit") == HISTORICAL_COMMIT
          and tl.get("formal_scoring_commit")
          == "9372a5426c77c08aa4b3eee31ba2055899370eeb")

    return {"verified": all(c["ok"] for c in checks), "checks": checks,
            "audit_sha256": _sha256(AUDIT)}


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
        print("OVERLAP AUDIT VERIFIED" if result["verified"]
              else "OVERLAP AUDIT NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
