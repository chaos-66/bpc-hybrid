# -*- coding: utf-8 -*-
"""Independent verifier for an S2.12 API-arm evaluation result. Replays the
evaluator's build_report()/build_manifest() byte-identically and checks the
report hashes/bindings. Prints VERIFIED or FAIL; exit 0/1."""
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ARM_DIRS = {"direct_llm": "s2_12_direct_llm_v1",
            "sun_llm_fallback": "s2_12_sun_llm_fallback_v1"}
EVAL = ROOT / "scripts/evaluate_s2_12_api_arm_v1.py"
TEXT_KEYS = {"text", "source_text", "approved_text_en", "normalized",
             "marker_surface"}
_sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: E731
def _load_evaluator():
    spec = importlib.util.spec_from_file_location("s212_api_eval_replay", EVAL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
def _text_free(value) -> bool:
    if isinstance(value, dict):
        return all(k not in TEXT_KEYS and _text_free(v) for k, v in value.items())
    return all(_text_free(item) for item in value) if isinstance(value, list) else True
def verify(arm: str) -> dict:
    p = ROOT / "data/predictions" / ARM_DIRS[arm]
    r = ROOT / "data/results" / ARM_DIRS[arm]
    checks: list[dict] = []
    def ck(name: str, cond: bool) -> None:
        checks.append({"name": name, "ok": bool(cond)})
    paths = [p / n for n in ("predictions.json", "telemetry.json", "cost.json",
                             "manifest.json")] + \
        [r / n for n in ("evaluation.json", "manifest.json")]
    ck("all files exist", all(x.is_file() for x in paths))
    if not all(x.is_file() for x in paths):
        return {"verified": False, "checks": checks}
    pd = json.loads((p / "predictions.json").read_text(encoding="utf-8"))
    rm = json.loads((p / "manifest.json").read_text(encoding="utf-8"))
    rep = json.loads((r / "evaluation.json").read_text(encoding="utf-8"))
    man = json.loads((r / "manifest.json").read_text(encoding="utf-8"))
    rows = pd.get("records", [])
    ck("capsule locked, complete, 36 ok, text-free",
       rm.get("status") == "predictions_locked_before_gold_evaluation"
       and rm.get("capsule_status") == "complete"
       and rm.get("safety", {}).get("raw_text_committed") is False
       and pd.get("record_count") == 36 and len(rows) == 36
       and all(x.get("request_status") == "ok" for x in rows)
       and _text_free(pd))
    ck("evaluation literal", rep.get("status") == f"verified_{arm}_arm_complete"
       and rep.get("arm") == arm)
    for name, info in rm.get("artifacts", {}).items():
        path = p / name
        ck(f"capsule artifact {name} hash/size", path.is_file()
           and _sha(path) == info.get("sha256")
           and path.stat().st_size == info.get("byte_size"))
    info = man.get("report", {})
    rp = ROOT / str(info.get("path", ""))
    ck("report hash/size", rp.is_file() and _sha(rp) == info.get("sha256")
       and rp.stat().st_size == info.get("byte_size"))
    for name, binding in man.get("bindings", {}).items():
        path = ROOT / str(binding.get("path", ""))
        ck(f"binding {name}", path.is_file() and _sha(path) == binding.get("sha256"))
    for rel, expected in man.get("implementation", {}).items():
        path = ROOT / rel
        ck(f"implementation {rel}", path.is_file() and _sha(path) == expected)
    module = _load_evaluator()
    er = module._json_bytes(module.build_report(arm))
    em = module._json_bytes(module.build_manifest(arm, er))
    ck("replay byte-identical", (r / "evaluation.json").read_bytes() == er
       and (r / "manifest.json").read_bytes() == em)
    ck("no Gold Rule Records / Oracle",
       man.get("safety", {}).get("gold_rule_records_created") is False
       and man.get("safety", {}).get("oracle_started") is False)
    return {"verified": all(c["ok"] for c in checks), "checks": checks}
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("direct_llm", "sun_llm_fallback"),
                        required=True)
    args = parser.parse_args()
    result = verify(args.arm)
    for item in result["checks"]:
        print(("PASS" if item["ok"] else "FAIL"), item["name"])
    print(f"S2.12 {args.arm} VERIFIED" if result["verified"]
          else f"S2.12 {args.arm} NOT VERIFIED")
    return 0 if result["verified"] else 1
if __name__ == "__main__":
    raise SystemExit(main())
