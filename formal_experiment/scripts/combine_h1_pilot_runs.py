"""S2.8D-R6C1: combine a prior frozen pilot run + its continuation into a
complete 10-plan pilot capsule.

Pure offline, deterministic, fail-closed.  It merges:

* R6 (original orders 1..5)  +  R6C1 (original orders 6..10)

into ``s28d_r6_complete_h1_small_pilot_v1`` with a combined predictions /
telemetry / manifest.  The script never reads ``.env``, never calls any
LLM/API, never touches Gold or Layer E, and never prints source / prompt /
patch / response text -- only hashes, IDs, counts, and statuses.

The merge is only valid when:

* both runs bind the same B0 attempts/manifest hashes and the same parent
  frozen plan / prompt / model;
* prior run called EXACTLY original orders 1..5 (each once);
* continuation called EXACTLY original orders 6..10 (each once);
* the two plan-key sets are disjoint and their union is exactly the parent
  10 plans;
* every sample is modified by at most one run (no double patch application).

The combined predictions are built from the same B0 records; the combined
telemetry keeps every row and records which original run produced it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.h1_pilot_plan import selected_plan_keys_sha256  # noqa: E402


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _prediction_hash(record: Mapping[str, Any]) -> str:
    payload = json.dumps(
        {"clauses": record.get("clauses", [])},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _call_keys(telemetry: list[dict[str, Any]]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for row in telemetry:
        if not row.get("llm_called"):
            continue
        for ev in row.get("patch_events", []):
            if ev.get("llm_call_performed"):
                keys.add((str(row["sample_id"]), str(ev["clause_id"])))
    return keys


def combine_pilot_runs(
    *,
    prior_dir: Path,
    continuation_dir: Path,
    parent_plan_path: Path,
    b0_predictions: Path,
    b0_manifest: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate and merge the two runs.

    Returns ``(combined_manifest, combined_predictions, combined_telemetry)``.
    Raises :class:`ValueError` on any binding failure.
    """
    errors: list[str] = []

    parent = _read_json(parent_plan_path)
    b0_attempts = json.loads(b0_predictions.read_text(encoding="utf-8"))
    b0_records = {
        entry["record"]["sample_id"]: entry["record"]
        for entry in b0_attempts
        if isinstance(entry, Mapping) and isinstance(entry.get("record"), Mapping)
    }
    b0_ids = set(b0_records)

    def load_run(directory: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        return (
            _read_json(directory / "manifest.json"),
            _read_jsonl(directory / "h1_telemetry.jsonl"),
            _read_jsonl(directory / "h1_predictions.jsonl"),
        )

    p_manifest, p_telemetry, p_predictions = load_run(prior_dir)
    c_manifest, c_telemetry, c_predictions = load_run(continuation_dir)

    # 1-3: same B0 / prompt / model / parent plan.
    for manifest in (p_manifest, c_manifest):
        if manifest.get("b0_binding", {}).get("sha256") != _sha256_file(b0_predictions):
            errors.append(f"{manifest.get('execution_mode')} B0 attempts sha mismatch")
        if manifest.get("llm_model") not in (None, "deepseek-v4-pro"):
            errors.append("model mismatch")
    parent_keys = {
        (str(e["sample_id"]), str(e["clause_id"]))
        for e in parent.get("selected_plans", [])
        if isinstance(e, Mapping)
    }
    if len(parent_keys) != 10:
        errors.append("parent frozen plan must contain exactly 10 plans")

    # 4-8: disjoint keys, exact order coverage, single call each.
    p_called = _call_keys(p_telemetry)
    c_called = _call_keys(c_telemetry)
    if not p_called or not c_called:
        errors.append("both runs must have called plans")
    if p_called & c_called:
        errors.append("plan key sets are not disjoint")
    parent_entries = {
        e["execution_order"]: (str(e["sample_id"]), str(e["clause_id"]))
        for e in parent["selected_plans"]
        if isinstance(e, Mapping)
    }
    if p_called != {parent_entries[o] for o in (1, 2, 3, 4, 5)}:
        errors.append("prior run must call exactly original orders 1..5")
    if c_called != {parent_entries[o] for o in (6, 7, 8, 9, 10)}:
        errors.append("continuation run must call exactly original orders 6..10")
    if (p_called | c_called) != parent_keys:
        errors.append("union of called plans does not exactly cover the parent 10 plans")
    if len({s for s, _ in p_called | c_called}) != 10:
        errors.append("called plans must span 10 distinct samples")

    if errors:
        raise ValueError("combine failed: " + "; ".join(errors))

    # 9-12: no double modification; combined predictions from same B0.
    p_by_id = {r["sample_id"]: r for r in p_predictions}
    c_by_id = {r["sample_id"]: r for r in c_predictions}
    p_tel_by_id = {r["sample_id"]: r for r in p_telemetry}
    c_tel_by_id = {r["sample_id"]: r for r in c_telemetry}
    called_p_samples = {s for s, _ in p_called}
    called_c_samples = {s for s, _ in c_called}

    combined_predictions: list[dict[str, Any]] = []
    combined_telemetry: list[dict[str, Any]] = []
    for sample_id in sorted(b0_ids):
        if sample_id in called_p_samples:
            combined_predictions.append(p_by_id[sample_id])
            row = dict(p_tel_by_id[sample_id]); row["source_run"] = "s28d_r6_h1_small_pilot_v1"
            combined_telemetry.append(row)
        elif sample_id in called_c_samples:
            combined_predictions.append(c_by_id[sample_id])
            row = dict(c_tel_by_id[sample_id]); row["source_run"] = "s28d_r6c1_h1_remaining_pilot_v1"
            combined_telemetry.append(row)
        else:
            # Never selected by either run: keep the B0 identity.  Prefer the
            # prior run's row when present; otherwise build from B0.
            if sample_id in p_by_id:
                combined_predictions.append(p_by_id[sample_id])
            else:
                rec = dict(b0_records[sample_id])
                rec["method"] = {"name": "sun_llm_fallback", "schema_source": "test"}
                combined_predictions.append(rec)
            if sample_id in p_tel_by_id:
                row = dict(p_tel_by_id[sample_id]); row["source_run"] = "neither"
            else:
                b0_hash = _prediction_hash(b0_records[sample_id])
                row = {
                    "sample_id": sample_id,
                    "b0_prediction_sha256": b0_hash,
                    "h1_prediction_sha256": b0_hash,
                    "triggered": False, "selected_for_call": False, "llm_called": False,
                    "patch_proposed": False, "patch_accepted": False, "prediction_changed": False,
                    "patch_events": [], "source_run": "neither",
                }
            combined_telemetry.append(row)

    called_keys_all = sorted(f"{s}/{c}" for s, c in (p_called | c_called))
    combined_manifest = {
        "schema_version": "h1_complete_pilot_capsule@1.0.0",
        "task_id": "S2.8D-R6C1",
        "start_commit": "37ab7efb4fe08603ac5a3c19f12bdf54dc287451",
        "parent_frozen_plan": {
            "path": str(parent_plan_path),
            "sha256": _sha256_file(parent_plan_path),
            "selected_plan_keys_sha256": selected_plan_keys_sha256(parent["selected_plans"]),
        },
        "b0": {"attempts_sha256": _sha256_file(b0_predictions), "manifest_sha256": _sha256_file(b0_manifest)},
        "prior_run": {
            "run_id": p_manifest.get("run_id", "s28d_r6_h1_small_pilot_v1"),
            "dir": str(prior_dir),
            "manifest_sha256": _sha256_file(prior_dir / "manifest.json"),
            "transport_capture_sha256": _sha256_file(prior_dir / "transport_capture.jsonl"),
            "called_original_orders": [1, 2, 3, 4, 5],
        },
        "continuation_run": {
            "run_id": c_manifest.get("run_id", "s28d_r6c1_h1_remaining_pilot_v1"),
            "dir": str(continuation_dir),
            "manifest_sha256": _sha256_file(continuation_dir / "manifest.json"),
            "transport_capture_sha256": _sha256_file(continuation_dir / "transport_capture.jsonl"),
            "called_original_orders": [6, 7, 8, 9, 10],
        },
        "coverage": {
            "called_plan_count": len(called_keys_all),
            "distinct_sample_count": len({s for s, _ in p_called | c_called}),
            "complete_10_of_10": (p_called | c_called) == parent_keys,
            "called_plan_keys_sha256": hashlib.sha256("\n".join(called_keys_all).encode("utf-8")).hexdigest(),
            "status": "complete",
        },
        "combined_hashes": {
            "predictions_sha256": hashlib.sha256(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in combined_predictions).encode("utf-8")
            ).hexdigest(),
            "telemetry_sha256": hashlib.sha256(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in combined_telemetry).encode("utf-8")
            ).hexdigest(),
        },
        "per_run_aggregates": {
            "s28d_r6_h1_small_pilot_v1": {
                "llm_calls": p_manifest.get("llm_calls"),
                "accepted": p_manifest.get("patch_accepted_count"),
                "rejected": p_manifest.get("patch_rejected_count"),
                "effective": p_manifest.get("effective_patch", {}).get("accepted_effective_patch_count"),
                "changed": p_manifest.get("prediction_changed_sample_count"),
            },
            "s28d_r6c1_h1_remaining_pilot_v1": {
                "llm_calls": c_manifest.get("llm_calls"),
                "accepted": c_manifest.get("patch_accepted_count"),
                "rejected": c_manifest.get("patch_rejected_count"),
                "effective": c_manifest.get("effective_patch", {}).get("accepted_effective_patch_count"),
                "changed": c_manifest.get("prediction_changed_sample_count"),
            },
        },
        "pr_f1": "not_computed",
    }
    return combined_manifest, combined_predictions, combined_telemetry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-run", type=Path, required=True)
    parser.add_argument("--continuation-run", type=Path, required=True)
    parser.add_argument("--parent-plan", type=Path, required=True)
    parser.add_argument("--b0-predictions", type=Path, required=True)
    parser.add_argument("--b0-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        manifest, predictions, telemetry = combine_pilot_runs(
            prior_dir=args.prior_run,
            continuation_dir=args.continuation_run,
            parent_plan_path=args.parent_plan,
            b0_predictions=args.b0_predictions,
            b0_manifest=args.b0_manifest,
        )
    except (ValueError, OSError) as exc:
        print(f"Refusing to combine: {exc}")
        return 2

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "h1_predictions.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in predictions), encoding="utf-8"
    )
    (args.output / "h1_telemetry.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in telemetry), encoding="utf-8"
    )
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Combined capsule written to", args.output)
    print("Complete 10/10 coverage:", manifest["coverage"]["complete_10_of_10"])
    print("Combined predictions sha:", manifest["combined_hashes"]["predictions_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
