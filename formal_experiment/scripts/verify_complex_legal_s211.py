"""Verify and manifest the S2.11 official-source GDPR complex dataset freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.complex_legal import (  # noqa: E402
    ComplexLegalContractError,
    DATASET_ID,
    SELECTION_SEED,
    TARGET_COUNT,
    build_blank_review,
    membership_payload,
    membership_sha256,
    parse_article_units,
    select_coverage_seeded50,
    sha256_file,
    validate_human_gold_review,
)


DEFAULT_CONFIG = ROOT / "configs/datasets/gdpr_articles_5_50_s211.json"


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComplexLegalContractError(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise ComplexLegalContractError(f"JSON root must be an object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ComplexLegalContractError(f"invalid JSONL bytes: {path}") from exc
    for number, line in enumerate(lines, start=1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ComplexLegalContractError(f"invalid JSONL at {path}:{number}") from exc
        if not isinstance(value, dict):
            raise ComplexLegalContractError(f"JSONL row is not an object: {path}:{number}")
        result.append(value)
    return result


def _resolve_lock(config: Mapping[str, Any], *keys: str) -> tuple[Path, str]:
    value: Any = config
    for key in keys:
        value = value[key]
    path = ROOT / value["path"]
    expected = value["sha256"]
    if not path.is_file():
        raise ComplexLegalContractError(f"missing locked S2.11 artifact: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise ComplexLegalContractError(
            f"S2.11 artifact hash mismatch for {path}: {actual} != {expected}"
        )
    return path, actual


def _metadata_identity(path: Path) -> dict[str, Any]:
    try:
        root = ElementTree.fromstring(path.read_bytes())
    except ElementTree.ParseError as exc:
        raise ComplexLegalContractError("invalid Cellar metadata XML") from exc
    identity = {
        "product_id": root.findtext("./BIB.DOC/PROD.ID"),
        "document_number": root.findtext("./BIB.DOC/NO.DOC/NO.CURRENT"),
        "document_year": root.findtext("./BIB.DOC/NO.DOC/YEAR"),
        "document_community": root.findtext("./BIB.DOC/NO.DOC/COM"),
        "oj_number": root.findtext("./PUBLICATION.REF/NO.OJ"),
        "oj_date": root.findtext("./PUBLICATION.REF/DATE"),
        "oj_language": root.findtext("./PUBLICATION.REF/LG.OJ"),
        "body_ref": root.find("./FMX/DOC.MAIN.PUB/REF.PHYS").get("FILE"),
    }
    expected = {
        "product_id": "20160425012",
        "document_number": "679",
        "document_year": "2016",
        "document_community": "EU",
        "oj_number": "119",
        "oj_date": "20160504",
        "oj_language": "EN",
        "body_ref": "L_2016119EN.01000101.xml",
    }
    if identity != expected:
        raise ComplexLegalContractError(f"Cellar metadata identity changed: {identity}")
    return identity


def run(config_path: Path) -> dict[str, Any]:
    config = _load_object(config_path)
    if (
        config.get("schema_version") != "complex_legal_dataset_contract@1.0.0"
        or config.get("task_id") != "S2.11"
        or config.get("status") != "preregistered_source_membership_and_gold_protocol"
        or config.get("dataset_id") != DATASET_ID
    ):
        raise ComplexLegalContractError("S2.11 dataset config identity mismatch")
    selection = config.get("selection", {})
    if (
        selection.get("seed") != SELECTION_SEED
        or selection.get("target_count") != TARGET_COUNT
        or selection.get("method_outputs_used") is not False
        or selection.get("evaluation_results_used") is not False
        or "model prediction" not in selection.get("forbidden_inputs", [])
        or "evaluation result" not in selection.get("forbidden_inputs", [])
    ):
        raise ComplexLegalContractError("S2.11 pre-result selection boundary changed")

    locks = {
        "metadata": _resolve_lock(config, "source", "metadata"),
        "body": _resolve_lock(config, "source", "body"),
        "reuse_evidence": _resolve_lock(config, "source", "reuse_evidence"),
        "dataset": _resolve_lock(config, "artifacts", "dataset"),
        "membership": _resolve_lock(config, "artifacts", "membership"),
        "blank_human_gold": _resolve_lock(config, "artifacts", "blank_human_gold"),
        "human_gold_schema": _resolve_lock(config, "artifacts", "human_gold_schema"),
        "mapping_guide": _resolve_lock(config, "artifacts", "mapping_guide"),
        "implementation": _resolve_lock(config, "artifacts", "implementation"),
        "builder": _resolve_lock(config, "artifacts", "builder"),
        "g05_contract": _resolve_lock(config, "complexity", "g05_contract"),
    }
    metadata_identity = _metadata_identity(locks["metadata"][0])
    units = parse_article_units(locks["body"][0])
    expected_records = select_coverage_seeded50(units)
    actual_records = _load_jsonl(locks["dataset"][0])
    if actual_records != expected_records:
        raise ComplexLegalContractError("frozen S2.11 dataset differs from deterministic rebuild")

    digest = membership_sha256(actual_records)
    membership = _load_object(locks["membership"][0])
    if (
        digest != selection.get("membership_sha256")
        or membership.get("membership_sha256") != digest
        or membership.get("membership_payload") != membership_payload(actual_records)
        or membership.get("sample_ids") != [record["sample_id"] for record in actual_records]
        or membership.get("article_coverage") != list(range(5, 51))
        or membership.get("source_unit_count") != len(units)
        or membership.get("method_outputs_used") is not False
        or membership.get("evaluation_results_used") is not False
        or membership.get("legacy_gdpr50_used") is not False
    ):
        raise ComplexLegalContractError("S2.11 membership manifest mismatch")

    review = _load_object(locks["blank_human_gold"][0])
    if review != build_blank_review(actual_records):
        raise ComplexLegalContractError("blank human-Gold template is not the deterministic 0/50 state")
    review_report = validate_human_gold_review(
        review, actual_records, locks["human_gold_schema"][0]
    )
    if review_report != {
        "format_valid": True,
        "input_ready": True,
        "freeze_ready": False,
        "reviewed": 0,
        "adjudicated": 0,
        "canonical_rule_present": 0,
        "errors": [],
    }:
        raise ComplexLegalContractError(f"blank human-Gold gate changed: {review_report}")

    reuse = _load_object(locks["reuse_evidence"][0])
    if (
        reuse.get("source_id") != "celex_32016R0679_oj_en"
        or reuse.get("reuse_evidence", {}).get("special_restriction_found_for_celex_32016R0679")
        is not False
        or reuse.get("project_decision", {}).get("status")
        != "qualified_for_local_research_and_reproducible_dataset_derivation"
    ):
        raise ComplexLegalContractError("EUR-Lex reuse qualification changed")
    legacy = config.get("legacy_gdpr50", {})
    if (
        legacy.get("status")
        != "rejected_as_formal_input_and_gold_kept_as_development_provenance"
        or legacy.get("official_full_document_normalized_matches") != 44
        or legacy.get("official_article_5_50_matches") != 29
        or legacy.get("annotation_status") != "auto_annotated_rule_based_pending_review"
        or legacy.get("imported_into_s211") is not False
    ):
        raise ComplexLegalContractError("legacy gdpr50 exclusion boundary changed")

    token_counts = [len(record["source_text"].split()) for record in actual_records]
    artifact_paths = {
        "config": config_path,
        **{name: value[0] for name, value in locks.items()},
        "validator": ROOT / "scripts/validate_complex_legal_human_gold.py",
        "verifier": ROOT / "scripts/verify_complex_legal_s211.py",
    }
    return {
        "schema_version": "complex_legal_s211_verification_manifest@1.0.0",
        "task_id": "S2.11",
        "status": "succeeded",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": platform.python_version()},
        "dataset_id": DATASET_ID,
        "artifacts": {
            name: {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(path),
            }
            for name, path in artifact_paths.items()
        },
        "source": {
            "celex": "32016R0679",
            "cellar_work_uuid": "3e485e15-11bd-11e6-ba9a-01aa75ed71a1",
            "metadata_identity": metadata_identity,
            "reuse_qualified": True,
        },
        "verification": {
            "source_unit_count": len(units),
            "selected_count": len(actual_records),
            "unique_sample_ids": len({record["sample_id"] for record in actual_records}),
            "unique_source_text_hashes": len(
                {record["source_text_sha256"] for record in actual_records}
            ),
            "article_coverage": list(range(5, 51)),
            "article_coverage_count": 46,
            "coverage_supplement_count": 4,
            "membership_sha256": digest,
            "token_count_min": min(token_counts),
            "token_count_max": max(token_counts),
            "token_count_mean": round(statistics.mean(token_counts), 2),
            "human_review": review_report,
            "legacy_gdpr50_imported": False,
            "g05_contract_bound": True,
            "formal_complexity_profiles_generated": False,
        },
        "safety": {
            "method_outputs_read": False,
            "test_results_read": False,
            "formal_gold_created": False,
            "human_gold_modified": False,
            "source_acquisition_network_used": True,
            "offline_verification_network_called": False,
            "llm_api_called": False,
            "performance_evaluation": False,
        },
        "claim_boundary": config["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest-out", type=Path, required=True)
    args = parser.parse_args()
    target = args.manifest_out.resolve()
    if target.exists():
        raise ComplexLegalContractError(f"refusing to overwrite: {target}")
    manifest = run(args.config.resolve())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "succeeded", "manifest": str(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
