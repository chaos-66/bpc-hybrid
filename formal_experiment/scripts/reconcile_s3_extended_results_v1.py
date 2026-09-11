"""Reconcile existing S3 scores offline; never run inference or overwrite history."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bpc_hybrid.s3_extended_prediction_accounting_v1 import (  # noqa: E402
    POLICIES, attach_expected, evaluate_instances, materialize_decisions,
)

RUN_ID = "s3_extended_prediction_accounting_v1"
SOURCE = ROOT / "outputs/development/s3_extended_repair_v2_v1"
OUTPUT = ROOT / "outputs/development" / RUN_ID
IMPLEMENTATION = [
    Path(__file__).resolve(),
    ROOT / "src/bpc_hybrid/s3_extended_prediction_accounting_v1.py",
    ROOT / "tests/test_s3_extended_prediction_accounting_v1.py",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def local_path(relative: str) -> Path:
    path = (ROOT / relative.replace("\\", "/")).resolve()
    if not path.is_relative_to(ROOT) or path.name.lower() == ".env":
        raise ValueError("binding outside permitted experiment files")
    return path


def verify_source() -> dict:
    manifest = read(SOURCE / "manifest.json")
    bindings = {}
    for kind in ("inputs", "implementation"):
        bindings.update(manifest[kind])
    for binding in [manifest["plan"], *manifest["results"].values()]:
        bindings[binding["path"]] = binding["sha256"]
    for path, expected in bindings.items():
        if sha(local_path(path)) != expected:
            raise ValueError(f"source binding mismatch: {path}")
    return {p.replace("\\", "/"): digest for p, digest in bindings.items()}


def payloads() -> tuple[dict[str, bytes], dict]:
    verify_source()
    rows = [json.loads(line) for line in (SOURCE / "predictions.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 120:
        raise ValueError("expected the 120 saved source rows")
    decisions = materialize_decisions(rows)
    instances = attach_expected(decisions, rows)
    arms = evaluate_instances(instances)
    previous = read(SOURCE / "metrics.json")["arms"]
    changes = {}
    for arm, metrics in arms.items():
        old = previous[arm]
        changes[arm] = {
            "control_before": old["B_control_40"],
            "control_after": metrics["B_control_40"],
            "paired_before": old["C_paired_40"]["both_sides_correct"],
            "paired_after": metrics["C_paired_40"]["both_sides_correct"],
            "merged_accuracy_before": old["D_merged_80"]["five_class_accuracy"],
            "merged_accuracy_after": metrics["D_merged_80"]["accuracy"],
        }
    report = {
        "schema_version": "s3_extended_prediction_accounting@1.0.0",
        "run_id": RUN_ID, "scope": "development_synthetic_offline_accounting_only",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_rows": 120, "instances": len(instances), "arms": arms,
        "corrections": changes,
        "interpretation": {
            "cause": "control_partition used a new gate for A/B, while paired/merged evaluation re-decided controls using the old policy, including for C",
            "replacement": "one declared policy per arm applied to both sides; all metrics consume the resulting immutable final labels",
            "A_B_policy": "frozen native aggregation; the C comparison gate is not silently applied",
            "C_policy": "existing declared comparison gate on both sides",
            "scope_of_none": "method output for this controlled check, not proof of whole-process legal compliance",
            "not_claimed": "no new method improvement, causal attribution or formal Oracle result",
        },
        "safety": {"new_inference_calls": 0, "new_llm_api_calls": 0,
                   "source_predictions_rewritten": 0, "variant_decisions_changed": 0},
    }
    final_bytes = b"".join((json.dumps(r, ensure_ascii=False, sort_keys=True,
                                    allow_nan=False) + "\n").encode("utf-8") for r in instances)
    metric_bytes = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2,
                              allow_nan=False) + "\n").encode("utf-8")
    return {"final_predictions.jsonl": final_bytes, "metrics.json": metric_bytes}, report


def verify_output(replay: bool = True) -> dict:
    manifest = read(OUTPUT / "manifest.json")
    for group in ("sources", "implementation", "artifacts"):
        for relative, expected in manifest[group].items():
            if sha(local_path(relative)) != expected:
                raise ValueError(f"binding mismatch: {relative}")
    expected, report = payloads()
    if replay:
        for name, content in expected.items():
            if (OUTPUT / name).read_bytes() != content:
                raise ValueError(f"offline reconciliation differs: {name}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    if args.check or args.replay:
        report = verify_output()
        print("S3 ACCOUNTING VERIFIED (offline; inference=0)")
    else:
        names = ("final_predictions.jsonl", "metrics.json", "manifest.json")
        if any((OUTPUT / name).exists() for name in names):
            raise ValueError("output exists; use --check/--replay, no overwrite")
        content, report = payloads()
        sources = {str((SOURCE / name).relative_to(ROOT)).replace("\\", "/"): sha(SOURCE / name)
                   for name in ("manifest.json", "plan.json", "predictions.jsonl", "metrics.json")}
        implementation = {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p)
                          for p in IMPLEMENTATION}
        # Native decision implementations are transitively locked by the source
        # manifest and rechecked by verify_source(), not reimplemented here.
        manifest = {
            "schema_version": "s3_extended_accounting_manifest@1.0.0",
            "run_id": RUN_ID, "git_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8").strip(),
            "command": "python scripts/reconcile_s3_extended_results_v1.py",
            "scope": report["scope"], "policies": POLICIES,
            "sources": sources, "implementation": implementation,
            "artifacts": {str((OUTPUT / n).relative_to(ROOT)).replace("\\", "/"):
                          hashlib.sha256(b).hexdigest() for n, b in content.items()},
            "safety": report["safety"],
        }
        content["manifest.json"] = (json.dumps(manifest, ensure_ascii=False,
                                              indent=2, sort_keys=True) + "\n").encode("utf-8")
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for name, value in content.items():
            with (OUTPUT / name).open("xb") as stream:
                stream.write(value)
    for arm, value in report["arms"].items():
        print(arm, json.dumps({"control": value["B_control_40"],
              "paired": value["C_paired_40"]["both_sides_correct"],
              "merged_accuracy": value["D_merged_80"]["accuracy"],
              "merged_macro_f1": value["D_merged_80"]["macro_f1"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
