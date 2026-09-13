# -*- coding: utf-8 -*-
"""Final v5 fallback execution entry point (preflight/mock/real; zero API by default).

The real branch is fail-closed: it requires a scope-matching authorization file
and environment credentials, calls the resumable executor, and never retries a
request whose ledger state says it was sent.  No real call is made unless the
user explicitly supplies --real and a valid authorization.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.s3_semantic_grounding_llm_v1 import (  # noqa: E402
    build_request_set,
    execute_fallback,
    validate_authorization,
)

V5_DIR = ROOT / "outputs/evidence/s3_semantic_grounding_v5"
V5_PACK = V5_DIR / "llm_fallback_candidate_pack_v5.json"
V5_CONFIG = ROOT / "configs/stage3_semantic_grounding_v5.json"
REPORT_ROOT = ROOT / "outputs/reports"
OUT_ROOT = ROOT / "outputs/development/s3_semantic_grounding_v5"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def _build_preflight():
    script = SCRIPTS / "build_s3_semantic_grounding_v5_llm_preflight.py"
    spec = importlib.util.spec_from_file_location("v5_preflight_builder", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build()


def _llm_config() -> dict:
    config = read_json(V5_CONFIG)
    llm = dict(config.get("llm_fallback") or {})
    llm["run_root_name"] = llm.get("run_root_name") or \
        "s3_semantic_grounding_llm_v2_real_run"
    return llm


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--mock", action="store_true")
    group.add_argument("--real", action="store_true")
    parser.add_argument("--authorization", type=Path, default=None)
    args = parser.parse_args()

    pack = read_json(V5_PACK)
    llm = _llm_config()
    request_set = build_request_set(pack, llm)

    if args.preflight:
        result = _build_preflight()
        print(json.dumps({
            "status": result["preflight"]["status"],
            "scope": result["auth_request"]["scope"],
            "calls": result["auth_request"]["calls"],
            "request_set_sha256": result["auth_request"]["request_set_sha256"],
            "candidate_pack_sha256": result["auth_request"]["candidate_pack_sha256"],
            "matching_authorizations": len(
                result["auth_request"]["matching_authorizations"]),
            "real_api_calls": 0,
        }, ensure_ascii=False, indent=2))
        return 0

    if args.mock:
        mock_config = dict(llm)
        mock_config["off_peak_only"] = False
        summary = execute_fallback(
            pack=pack, request_set=request_set, config=mock_config,
            output_root=OUT_ROOT, mode="mock")
        write_json(REPORT_ROOT /
                   "s3_semantic_grounding_v5_llm_mock_execution.json", summary)
        print(json.dumps({
            "mode": "mock",
            "run_status": summary["run_status"],
            "counts": summary["counts"],
            "real_api_calls": 0,
        }, ensure_ascii=False, indent=2))
        return 0

    if args.authorization is None:
        raise SystemExit("--real requires --authorization path")
    authorization = read_json(args.authorization)
    validation = validate_authorization(authorization, pack, request_set, llm)
    if not validation["valid"]:
        raise SystemExit("authorization invalid: " + ",".join(validation["errors"]))
    summary = execute_fallback(
        pack=pack, request_set=request_set, config=llm,
        output_root=OUT_ROOT, mode="real", authorization=authorization)
    write_json(REPORT_ROOT /
               "s3_semantic_grounding_v5_llm_real_execution.json", summary)
    print(json.dumps({
        "run_status": summary["run_status"],
        "counts": summary["counts"],
        "no_double_send": summary["no_double_send"],
        "known_usage_complete": summary["known_usage_complete"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
