# -*- coding: utf-8 -*-
"""Rebuild the Stage-3 binding/grounding/Table 3 closure in dependency order."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    "build_stage3_inference_view_v1.py",
    "build_stage3_binding_reference_v1.py",
    "build_stage3_binding_audit_v1.py",
    "build_stage3_paired_benchmark_eligibility_v1.py",
    "build_stage3_binding_final_human_approval_packet_v1.py",
    "run_stage3_ours_v1.py",
    "evaluate_stage3_automatic_grounding_v1.py",
    "evaluate_stage3_ours_v1.py",
    "build_stage3_table3_v1.py",
    "validate_stage3_binding_reference_v1.py",
    "build_stage3_repair_summary_v1.py",
]


def main() -> int:
    for step in STEPS:
        path = ROOT / "scripts" / step
        if not path.is_file():
            print(f"missing step: {path}", file=sys.stderr)
            return 2
        cmd = [sys.executable, str(path)]
        if step == "run_stage3_ours_v1.py":
            cmd += ["--nlp-model", "en_core_web_md"]
        print(f"==> {step}")
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode != 0:
            print(f"step failed ({result.returncode}): {step}", file=sys.stderr)
            return result.returncode
    print("Stage-3 repair closure complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
