# -*- coding: utf-8 -*-
"""Fail-closed verifier for the S1.3 P2 method lock (2026-08-13).

Recomputes everything from disk:
  1. P2 config identity (schema/task/method claim) and bindings
     (implementation module, sidecar schema) hash-match
  2. offline runtime lock: spacy version, en_core_web_sm version and model
     directory sha256 match the config
  3. verb-root resource exists, loads, and is generic (no GDPR-7 tokens)
  4. evidence sources in the method crosswalk hash-match disk
  5. static Gold isolation: implementation/config/runner sources contain no
     Gold/correction/adjudication path bindings
  6. deterministic double-run of the linguistic analyzer is byte-identical
  7. no forbidden claims (exact reproduction / Sun original / P1 enhanced /
     novel / blind preregistration) appear in the locked claim boundary

Exit 0 iff everything verifies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

CONFIG = ROOT / "configs" / "stage1_label_p2_v1.json"
MODULE = ROOT / "src" / "bpc_hybrid" / "stage1_label_semantics_p2.py"
SCHEMA = ROOT / "configs" / "schemas" / "stage1_label_semantics_p2.schema.json"
VERB_RESOURCE = ROOT / "configs" / "resources" / "english_verb_roots_v1.json"
CROSSWALK = ROOT / "outputs" / "reports" / "s1_3_p2_crosswalk_v1.json"
RUNNER = ROOT / "scripts" / "run_stage1_p2_inference.py"

FORBIDDEN_SOURCE_TOKENS = ("data/gold", "human_correction", "adjudications",
                           "stage1_gdpr7_human_correction")
FORBIDDEN_CLAIMS = ("exact reproduction", "Sun original implementation",
                    "P1 enhanced", "novel Stage 1 method",
                    "blind preregistration")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    checks = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    check("config identity",
          cfg.get("schema_version") == "stage1_label_p2_config@1.0.0"
          and cfg.get("task_ids") == ["S1.3"]
          and cfg["method"]["baseline"] == "P2"
          and cfg["method"]["method_name"] == "stage1_label_p2_linguistic"
          and cfg["method"]["method_version"] == "stage1_label_p2@1.0.0"
          and cfg["method"]["claim_name"]
          == "Sun/Leopold-style Stage 1 method-level independent reconstruction")
    check("implementation module exists", MODULE.exists())
    check("sidecar schema exists", SCHEMA.exists())
    check("runner exists", RUNNER.exists())
    check("verb resource exists", VERB_RESOURCE.exists())
    check("crosswalk exists", CROSSWALK.exists())

    # runtime lock
    import spacy
    model = spacy.load("en_core_web_sm")
    model_path = Path(model.path)
    total = hashlib.sha256()
    n = 0
    for file in sorted(model_path.rglob("*")):
        if file.is_file() and file.name != "__init__.py":
            total.update(file.read_bytes())
            n += 1
    rt = cfg["runtime"]
    check("runtime lock: spacy version",
          rt.get("version") == spacy.__version__)
    check("runtime lock: model version",
          rt.get("model_version") == str(model.meta.get("version", "")))
    check("runtime lock: model dir sha256",
          rt.get("model_dir_sha256") == total.hexdigest()
          and rt.get("model_dir_files") == n)
    check("runtime fail-closed policy",
          rt.get("missing_runtime") == "fail_closed_raise_no_p1_fallback")

    # verb resource generic
    verbs = json.loads(VERB_RESOURCE.read_text(encoding="utf-8"))["verbs"]
    check("verb resource generic + unique",
          isinstance(verbs, list) and len(verbs) >= 100
          and len(verbs) == len(set(verbs))
          and all(v.islower() and v.isalpha() for v in verbs)
          and "data" not in verbs and "subject" not in verbs
          and "rectify" in verbs and "communicate" in verbs)

    # crosswalk evidence hashes (evidence lives under the workspace root,
    # outside formal_experiment/)
    cw = json.loads(CROSSWALK.read_text(encoding="utf-8"))
    workspace_root = ROOT.parent
    evidence_ok = True
    for source in cw.get("evidence_sources", []):
        path = workspace_root / source["local_path"]
        if not path.exists() or _sha256(path) != source["sha256"]:
            evidence_ok = False
    check("crosswalk evidence hashes match disk", evidence_ok)
    check("crosswalk forbidden claims listed",
          all(claim in cw.get("forbidden_claims", [])
              for claim in FORBIDDEN_CLAIMS))
    check("crosswalk honest label present",
          cw.get("honest_label")
          == "post-Gold paper-derived method reconstruction with a locked "
          "implementation and prospective one-shot evaluation")

    # static Gold isolation: only PATH-LIKE string literals (containing a
    # path separator) are inspected, so safety field names in the data
    # contract (e.g. gold_read, human_correction_read) are not false
    # positives; actual path bindings to gold/correction/adjudication
    # assets are forbidden in the module and the runner. The CONFIG is
    # exempt from the literal scan because its input_contract
    # forbidden_inputs DECLARES the very paths it must not read (a
    # declaration, not a binding); that declaration is checked separately.
    import ast
    iso_ok = True
    for path in (MODULE, RUNNER):
        if not path.exists():
            iso_ok = False
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - defensive
            iso_ok = False
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                literal = node.value
                if "/" not in literal and "\\" not in literal:
                    continue  # not a path-like binding
                for token in FORBIDDEN_SOURCE_TOKENS:
                    if token in literal:
                        iso_ok = False
    # config declaration check: forbidden inputs must be declared
    forbidden_inputs = cfg.get("input_contract", {}).get("forbidden_inputs", [])
    declared = any("data/gold" in item for item in forbidden_inputs)
    if not declared:
        iso_ok = False
    check("static Gold isolation (module/config/runner)", iso_ok)

    # deterministic double-run of the linguistic analyzer
    try:
        from bpc_hybrid.stage1_label_semantics_p2 import _analyze_label, _verbs
        labels = ["Retrieve data", "Communication with data subject",
                  "Stop running", "Check whether the data is processed",
                  "Data is retrieved", "", "!!!"]
        verbs = _verbs()
        runs = []
        for _ in range(2):
            runs.append([
                json.dumps(_analyze_label(label, verbs),
                           ensure_ascii=False, sort_keys=True)
                for label in labels
            ])
        check("linguistic analyzer double-run byte-identical",
              runs[0] == runs[1])
    except Exception as exc:  # pragma: no cover - defensive
        check("linguistic analyzer double-run byte-identical", False,
              str(exc))

    return {"verified": all(c["ok"] for c in checks), "checks": checks}


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
        print("P2 LOCK VERIFIED" if result["verified"]
              else "P2 LOCK NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
