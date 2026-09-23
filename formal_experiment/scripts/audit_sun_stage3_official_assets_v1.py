"""Inventory inherited Sun/Winter Stage 3 assets without executing provenance code.

This is a file/source audit, not a compliance evaluator. Absence of a published
compliance certificate is not a judgment that a BPMN is non-compliant.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
NS = {"b": "http://www.omg.org/spec/BPMN/20100524/MODEL"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root: Path) -> dict[str, dict]:
    if not root.is_dir():
        raise FileNotFoundError(root)
    return {
        p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "sha256": sha(p)}
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name != ".DS_Store"
        and "__MACOSX" not in p.relative_to(root).parts
        and "__pycache__" not in p.relative_to(root).parts
    }


def compare(left: dict, right: dict) -> dict:
    common = set(left) & set(right)
    return {
        "left_count": len(left), "right_count": len(right),
        "identical_count": sum(left[k] == right[k] for k in common),
        "different": sorted(k for k in common if left[k] != right[k]),
        "left_only": sorted(set(left) - set(right)),
        "right_only": sorted(set(right) - set(left)),
    }


def build_report() -> dict:
    winter = WORKSPACE / "references/winter_2020_model_check/model_check/input"
    mentor = WORKSPACE / "references/合规性检查模型代码/model_check/input"
    files = inventory(winter)
    other = inventory(mentor)
    models = []
    for relative in sorted(k for k in files if k.endswith(".bpmn")):
        source = winter / relative
        active = ROOT / "data/input/stage1_stage3/gdpr7" / source.name
        tree = ET.parse(source)
        models.append({
            "filename": source.name,
            "source_sha256": sha(source),
            "active_exists": active.is_file(),
            "active_byte_identical": active.is_file() and sha(active) == sha(source),
            "process_count": len(tree.findall(".//b:process", NS)),
            "participant_names": [n.get("name") for n in tree.findall(".//b:participant", NS)],
            "published_fully_compliant_certificate": "not_present_in_audited_package",
            "semantic_compliance": "not_determined_by_file_inventory",
        })
    rule_gold_path = ROOT / "data/gold/stage3/gdpr7_gold_rule_records_v1.json"
    gold = json.loads(rule_gold_path.read_text(encoding="utf-8"))
    clauses = [c for r in gold["records"] for c in r["clauses"]]
    matching_path = ROOT / "data/gold/stage3/stage3_matching_gold_v1.json"
    matching = json.loads(matching_path.read_text(encoding="utf-8"))
    existing_pairs = {(x["process_id"], x["rule_id"]) for x in matching["items"]}
    process_ids = {Path(m["filename"]).stem for m in models}
    rule_ids = {r["rule_id"] for r in gold["records"]}
    all_pairs = {(p, r) for p in process_ids for r in rule_ids}
    paper = WORKSPACE / "references/papers/extracted/sun_2024_full_text.txt"
    return {
        "schema_version": "sun_stage3_official_asset_audit@1.0.0",
        "status": "audit_complete_reconstruction_required",
        "scope": "inherited public input package; no new performance evaluation",
        "official_source": {
            "publisher_url": "https://link.springer.com/article/10.1007/s11227-023-05626-0",
            "archive_url": "https://archive.org/details/input-2",
            "archive_sha1_historical": "a1a0ac8d57eb45698728722628a4c838c592c5bf",
            "official_zip_reacquired_this_task": False,
            "historical_official_identity_evidence": "docs/research/SUN_FINAL_VERSION_AND_DATA_AUDIT.md",
            "current_verification": "both local inherited copies and active BPMN bytes",
            "network_probe": "publisher links package; archive unavailable in web tool and local TLS verification failed; TLS verification not disabled",
        },
        "paper_basis": {
            "local_text_path": str(paper.relative_to(WORKSPACE)).replace("\\", "/"),
            "sha256": sha(paper),
            "version": "local_author_manuscript_not_verified_version_of_record",
            "sections": ["4.3 Definitions 4-7", "5.3.1", "5.3.2"],
            "component_similarity_tau": "explicit",
            "matching_score_greater_than_tau_outer_gate": "not_specified_in_available_text",
            "automatic_relevant_rule_selection": "underspecified",
            "checking_construction": "supplement base process to fully compliant, then introduce one error",
        },
        "files": files,
        "copy_comparison": compare(files, other),
        "file_counts": dict(Counter(Path(k).suffix for k in files)),
        "content_counts": {"bpmn": 7, "regulation_articles_5_to_50": 46, "configuration_and_lexicons": 4},
        "models": models,
        "not_present_in_audited_package": [
            "identified Sun four-model subset", "supplemented compliant BPMN versions",
            "single-error checking variants", "reference relevant-rule assignments",
            "per-case violation answers", "Sun Stage 2 Rule Records",
            "published automatic relevance-selection criterion",
        ],
        "existing_project_reference": {
            "rule_gold_sha256": sha(rule_gold_path),
            "rules": len(rule_ids), "sentences": len(gold["records"]), "clauses": len(clauses),
            "rule_order_relation_entries": sum(len(c["order_relations"]) for c in clauses),
            "matching_gold_sha256": sha(matching_path),
            "labeled_matching_pairs": len(existing_pairs), "full_matching_pairs": len(all_pairs),
            "unlabeled_matching_pairs": [list(p) for p in sorted(all_pairs - existing_pairs)],
            "unlabeled_is_negative": False,
            "old_binding_review": "complete; not reopened",
        },
        "methodological_conclusions": {
            "official_exact_checking_benchmark_recoverable_from_this_package": False,
            "v3_performance_publishable": False,
            "v3_reason": "unsupported outer gate plus unverified complete control compliance",
            "control_false_alarm_proves_actual_noncompliance": False,
            "zero_or_one_f1_alone_proves_bug": False,
            "new_benchmark_reference_may_use_method_predictions": False,
            "new_selection_cutoff_may_be_called_sun_original": False,
        },
        "safety": {"llm_api_calls": 0, "gold_modified": False, "provenance_modified": False,
                   "provenance_code_executed": False, "performance_evaluation": False},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_report()
    if args.output:
        output = args.output.resolve()
        output.relative_to(ROOT.resolve())
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "comparison": result["copy_comparison"],
                      "counts": result["content_counts"], "performance_run": False}))


if __name__ == "__main__":
    main()
