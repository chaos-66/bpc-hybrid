# -*- coding: utf-8 -*-
"""Sun-compatible Stage 2 to Stage 3 harness.

One-click runnable harness that:
1. Loads 6-field extractions from our pipeline
2. Converts to Sun-compatible records via ClauseAdapter
3. Validates JSON/JSONL output
4. Runs Stage 3 compliance checking with test fixtures
5. Generates a report

Usage:
    python scripts/run_stage3_fixture_harness.py
    python scripts/run_stage3_fixture_harness.py --input data/development/predictions/sun_rule_only.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from bpc_hybrid.sun_compat.clause_adapter import ClauseAdapter
from bpc_hybrid.sun_compat.similarity_engine import SimilarityEngine
from bpc_hybrid.sun_compat.stage3_adapter import Stage3Adapter
from bpc_hybrid.sun_compat.schema import SunRuleRecord

DEFAULT_INPUT = _PROJECT_ROOT / "data" / "development" / "predictions" / "sun_rule_only.jsonl"
FIXTURES_DIR = _PROJECT_ROOT / "tests" / "fixtures"
OUTPUT_DIR = _PROJECT_ROOT / "outputs" / "development" / "sun_compat"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_predictions(path: Path) -> list[dict]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  [WARN] Invalid JSON at line {i+1}: {e}")
    return records


def load_fixtures(fixture_type: str) -> list[dict]:
    path = FIXTURES_DIR / f"sun_compat_{fixture_type}.json"
    if not path.exists():
        print(f"  [WARN] Fixture file not found: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_sun_record(record: SunRuleRecord) -> dict[str, bool]:
    flags = {
        "has_rule_id": bool(record.rule_id),
        "has_source_text": bool(record.source_text),
        "has_modality_type": bool(record.modality_type),
        "has_obligations": len(record.obligations) > 0,
        "json_serializable": True,
    }
    try:
        json.dumps(record.to_dict())
    except (TypeError, ValueError):
        flags["json_serializable"] = False

    if record.obligations:
        obl = record.obligations[0]
        flags["has_obligation_lemmatized"] = bool(obl.obligation_lemmatized)
        flags["has_actor"] = bool(obl.actor)
        flags["has_action"] = bool(obl.action)
        flags["action_not_empty"] = bool(obl.action and obl.action.strip())
        flags["actor_not_empty"] = bool(obl.actor and obl.actor.strip())
    else:
        flags["has_obligation_lemmatized"] = False
        flags["has_actor"] = False
        flags["has_action"] = False
        flags["action_not_empty"] = False
        flags["actor_not_empty"] = False
    return flags


def run_conversion_check(adapter: ClauseAdapter, predictions: list[dict]) -> dict:
    print("\n" + "=" * 60)
    print("PHASE 1: Conversion Check")
    print("=" * 60)

    results = {
        "total": len(predictions),
        "converted": 0,
        "valid_json": 0,
        "has_action": 0,
        "has_actor": 0,
        "has_obligation_lemmatized": 0,
        "has_actor_action_map": 0,
        "has_order_relation": 0,
        "errors": [],
    }

    sun_records = []
    for pred in predictions:
        try:
            record = adapter.convert(
                rule_id=pred.get("sample_id", f"R{results['converted']:04d}"),
                source_text=pred.get("source_text", pred.get("text", "")),
                modality=pred.get("prediction_fields", {}).get("modality", {}).get("value", "unknown"),
                actor=pred.get("prediction_fields", {}).get("actor", {}).get("value", ""),
                action=pred.get("prediction_fields", {}).get("action", {}).get("value", ""),
                condition=pred.get("prediction_fields", {}).get("condition", {}).get("value", ""),
                constraint=pred.get("prediction_fields", {}).get("constraint", {}).get("value", ""),
                exception=pred.get("prediction_fields", {}).get("exception", {}).get("value", ""),
                provenance=pred.get("method", "rule"),
            )

            flags = validate_sun_record(record)
            results["converted"] += 1
            if flags["json_serializable"]:
                results["valid_json"] += 1
            if flags["has_action"]:
                results["has_action"] += 1
            if flags["has_actor"]:
                results["has_actor"] += 1
            if flags["has_obligation_lemmatized"]:
                results["has_obligation_lemmatized"] += 1
            if record.actor_action_maps:
                results["has_actor_action_map"] += 1
            if record.order_relations:
                results["has_order_relation"] += 1
            sun_records.append(record)
        except Exception as e:
            results["errors"].append({
                "sample_id": pred.get("sample_id", "unknown"),
                "error": str(e),
            })

    print(f"  Total predictions: {results['total']}")
    print(f"  Successfully converted: {results['converted']}")
    print(f"  Valid JSON: {results['valid_json']}")
    print(f"  Has action: {results['has_action']}")
    print(f"  Has actor: {results['has_actor']}")
    print(f"  Has obligation_lemmatized: {results['has_obligation_lemmatized']}")
    print(f"  Has actor_action_map: {results['has_actor_action_map']}")
    print(f"  Has order_relation: {results['has_order_relation']}")
    print(f"  Errors: {len(results['errors'])}")
    if results["errors"]:
        print("\n  First 3 errors:")
        for err in results["errors"][:3]:
            print(f"    - {err['sample_id']}: {err['error']}")
    return {"results": results, "records": sun_records}


def run_jsonl_output_check(records: list[SunRuleRecord]) -> dict:
    print("\n" + "=" * 60)
    print("PHASE 2: JSONL Output Check")
    print("=" * 60)

    output_path = OUTPUT_DIR / "sun_compat_output.jsonl"
    valid_count = 0
    invalid_count = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for record in records:
            try:
                line = json.dumps(record.to_dict(), ensure_ascii=False)
                f.write(line + "\n")
                valid_count += 1
            except Exception as e:
                invalid_count += 1
                print(f"  [ERROR] Failed to serialize {record.rule_id}: {e}")

    round_trip_ok = 0
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line.strip())
                SunRuleRecord.from_dict(d)
                round_trip_ok += 1
            except Exception as e:
                print(f"  [ERROR] Round-trip failed: {e}")

    print(f"  Output file: {output_path}")
    print(f"  Valid lines: {valid_count}")
    print(f"  Invalid lines: {invalid_count}")
    print(f"  Round-trip OK: {round_trip_ok}")

    return {
        "output_path": str(output_path),
        "valid_lines": valid_count,
        "invalid_lines": invalid_count,
        "round_trip_ok": round_trip_ok,
    }


def run_fixture_check(
    adapter: ClauseAdapter,
    stage3: Stage3Adapter,
    fixture_type: str,
) -> dict:
    print("\n" + "=" * 60)
    print(f"PHASE 3: Fixture Check -- {fixture_type}")
    print("=" * 60)

    fixtures = load_fixtures(fixture_type)
    if not fixtures:
        return {"fixture_type": fixture_type, "status": "no_fixtures", "results": []}

    results = []
    correct = 0
    total = len(fixtures)

    for fixture in fixtures:
        fixture_id = fixture["fixture_id"]
        expected = fixture["expected_detection"]

        record = adapter.convert(
            rule_id=fixture_id,
            source_text=fixture["source_text"],
            modality=fixture["modality"],
            actor=fixture["actor"],
            action=fixture["action"],
            condition=fixture.get("condition", ""),
            constraint=fixture.get("constraint", ""),
            exception=fixture.get("exception", ""),
        )

        bpmn_tasks = fixture["bpmn_tasks"]
        check_result = stage3.check_fixture(
            rules=[record],
            model_obligations=bpmn_tasks,
            fixture_type=fixture_type,
        )

        detected = check_result["detected"]
        is_correct = detected == expected
        if is_correct:
            correct += 1

        status = "[OK]" if is_correct else "[FAIL]"
        print(f"  {status} {fixture_id}: detected={detected}, expected={expected}")
        if not is_correct:
            print(f"    Description: {fixture['description']}")
            print(f"    Fitness: {check_result['fitness_score']:.3f}")
            print(f"    Obligation cost: {check_result['obligation_cost']:.3f}")
            print(f"    Resource cost: {check_result['resource_cost']:.3f}")

        results.append({
            "fixture_id": fixture_id,
            "detected": detected,
            "expected": expected,
            "correct": is_correct,
            "fitness_score": check_result["fitness_score"],
            "obligation_cost": check_result["obligation_cost"],
            "resource_cost": check_result["resource_cost"],
            "violations": check_result["violation_details"],
        })

    accuracy = correct / total if total > 0 else 0.0
    print(f"\n  Accuracy: {correct}/{total} = {accuracy:.1%}")
    return {
        "fixture_type": fixture_type,
        "status": "completed",
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "results": results,
    }


def generate_report(
    conversion_results: dict,
    jsonl_results: dict,
    fixture_results: list[dict],
) -> dict:
    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "conversion": conversion_results["results"],
        "jsonl_output": jsonl_results,
        "fixtures": fixture_results,
    }

    all_passed = True
    checks = []

    conv_rate = conversion_results["results"]["converted"] / max(conversion_results["results"]["total"], 1)
    check1 = conv_rate >= 0.95
    checks.append(("conversion_rate >= 95%", check1, f"{conv_rate:.1%}"))
    if not check1:
        all_passed = False

    json_rate = jsonl_results["valid_lines"] / max(conversion_results["results"]["converted"], 1)
    check2 = json_rate >= 0.99
    checks.append(("json_validity >= 99%", check2, f"{json_rate:.1%}"))
    if not check2:
        all_passed = False

    rt_rate = jsonl_results["round_trip_ok"] / max(jsonl_results["valid_lines"], 1)
    check3 = rt_rate >= 0.99
    checks.append(("round_trip >= 99%", check3, f"{rt_rate:.1%}"))
    if not check3:
        all_passed = False

    for fix in fixture_results:
        if fix["status"] == "completed":
            check_fix = fix["accuracy"] >= 0.6
            checks.append((f"fixture_{fix['fixture_type']} >= 60%", check_fix, f"{fix['accuracy']:.1%}"))
            if not check_fix:
                all_passed = False

    print(f"\n  Overall: {'PASS' if all_passed else 'FAIL'}")
    print(f"\n  Checks:")
    for name, passed, value in checks:
        status = "[OK]" if passed else "[FAIL]"
        print(f"    {status} {name}: {value}")

    report["overall_pass"] = all_passed
    report["checks"] = [{"name": n, "passed": p, "value": v} for n, p, v in checks]

    report_path = OUTPUT_DIR / "sun_compat_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  Report saved to: {report_path}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Sun-compatible Stage 2 to Stage 3 harness")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--fixtures", type=Path, default=FIXTURES_DIR)
    parser.add_argument("--gamma", type=float, default=0.4)
    parser.add_argument("--delta", type=float, default=0.8)
    args = parser.parse_args()

    print("=" * 60)
    print("Sun-Compatible Stage 2 to Stage 3 Harness")
    print("=" * 60)
    print(f"  Input: {args.input}")
    print(f"  Fixtures: {args.fixtures}")
    print(f"  Gamma: {args.gamma}")
    print(f"  Delta: {args.delta}")

    predictions = load_predictions(args.input)
    print(f"\n  Loaded {len(predictions)} predictions")

    if not predictions:
        print("  [ERROR] No predictions loaded. Exiting.")
        return 1

    print("\n  Initializing spaCy...")
    adapter = ClauseAdapter()
    engine = SimilarityEngine()
    stage3 = Stage3Adapter(engine, gamma=args.gamma, delta=args.delta)

    conversion = run_conversion_check(adapter, predictions)
    records = conversion["records"]

    jsonl = run_jsonl_output_check(records)

    fixture_types = ["missing_action", "incorrect_actor", "out_of_order"]
    fixture_results = []
    for ft in fixture_types:
        result = run_fixture_check(adapter, stage3, ft)
        fixture_results.append(result)

    report = generate_report(conversion, jsonl, fixture_results)
    engine.save_cache()

    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
