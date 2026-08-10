# -*- coding: utf-8 -*-
"""Deterministic formal benchmark input v2 publisher (zero-API, Gold-blind).

Publishes the executable Gold-blind inference input and the benchmark release
manifest v2:

- data/input/estg150_formal_inference_input_v2.json  (executable Gold-blind input)
- data/input/estg150_formal_input_v1.STATUS.md        (v1 limitation marker sidecar)
- outputs/reports/formal_benchmark_release_v2.manifest.json
- outputs/reports/formal_benchmark_release_v2.md
- outputs/reports/formal_benchmark_release_v2_export_index.json

Why v2: the v1 formal input (estg150_formal_input_v1.json) contains only the
150 sample IDs and the membership payload. That makes it a membership INDEX,
not an executable model input: B0/D1/H1 all analyse the approved English text
(and B0 additionally the raw German text for DE-EN alignment). v2 is published
from the frozen Layer E and carries exactly the text fields a Gold-blind
runner needs, while carrying NONE of the adjudication content (no six-element
Gold spans/labels, no accepted/edited/rejected decisions, no LLM candidate
drafts, no relation/order Gold, no review evidence or evaluation results).

v1 is preserved byte-for-byte and marked as membership-only via a sidecar
marker; it is NOT modified, overwritten, or deleted. The Gold files under
data/gold/ are NOT touched by this publisher.

Preconditions (fail closed): Layer E freeze_ready, membership payload hash
match, previously published Stage 2/Stage 3 Gold present and hash-verified
against the v1 publication manifest.

Deterministic: same frozen sources -> byte-identical outputs (fixed ordering,
no timestamps). No-overwrite: refuses to replace different content.

Usage:
    python scripts/publish_formal_benchmark_v2.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

LAYER_E = ROOT / "data" / "development" / "human_review" / "estg_150_human_correction_v1.json"
MEMBERSHIP_HASHES = ROOT / "data" / "development" / "estg" / "estg_150_membership_hashes.json"
V1_INPUT = ROOT / "data" / "input" / "estg150_formal_input_v1.json"
V1_PUBLICATION_MANIFEST = ROOT / "outputs" / "reports" / "formal_gold_publication_v1.manifest.json"
GOLD_STAGE2 = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
GOLD_MATCHING = ROOT / "data" / "gold" / "stage3" / "stage3_matching_gold_v1.json"
GOLD_VIOLATION = ROOT / "data" / "gold" / "stage3" / "stage3_violation_gold_v1.json"
STAGE3_CORRECTION = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"
STAGE3_INFERENCE = ROOT / "data" / "development" / "human_review" / "stage3_gold_inference_v1.json"
METHODS_CONFIG = ROOT / "configs" / "methods.json"
EXPERIMENT_CONTRACT = ROOT / "configs" / "experiment_contract.json"
STAGE2_SCHEMA = ROOT / "configs" / "schemas" / "stage2_formal_gold.schema.json"
STAGE3_SCHEMA = ROOT / "configs" / "schemas" / "stage3_formal_gold.schema.json"
PREDICTION_SCHEMA = ROOT / "configs" / "schemas" / "stage2_prediction.schema.json"
INPUT_V2_SCHEMA = ROOT / "configs" / "schemas" / "estg150_formal_inference_input_v2.schema.json"

OUT_V2 = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
OUT_V1_MARKER = ROOT / "data" / "input" / "estg150_formal_input_v1.STATUS.md"
OUT_MANIFEST = ROOT / "outputs" / "reports" / "formal_benchmark_release_v2.manifest.json"
OUT_REPORT = ROOT / "outputs" / "reports" / "formal_benchmark_release_v2.md"
OUT_EXPORT_INDEX = ROOT / "outputs" / "reports" / "formal_benchmark_release_v2_export_index.json"

# The user-authorized governance commit that moved the publication gate into
# the whitelist, plus the publication commits for the Gold artifacts.
AUTHORIZATION_COMMIT = "5d56f03"
PUBLICATION_COMMITS = ["8571dd5", "9f716f6", "956c771"]

# Fields that must never appear in v2 (adjudication / evaluation content).
FORBIDDEN_V2_FIELDS = ("decisions", "human_correction", "llm_candidate",
                       "candidate_text_en", "candidate_text_en_sha256",
                       "approved_text_en_history", "review_state", "clauses",
                       "relation", "order_relations", "evidence", "notes")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot load {label}: {path} ({exc})") from exc


def _git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, check=True).stdout.strip()
    except Exception:  # pragma: no cover
        return "unknown"


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_no_overwrite(path: Path, payload: dict[str, Any]) -> str:
    data = _canonical_json(payload)
    if path.exists():
        if path.read_bytes() == data:
            return _sha256_bytes(data)
        raise RuntimeError(f"refusing to overwrite different content: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _sha256_bytes(data)


def _write_text_no_overwrite(path: Path, text: str) -> str:
    data = text.encode("utf-8")
    if path.exists():
        if path.read_bytes() == data:
            return _sha256_bytes(data)
        raise RuntimeError(f"refusing to overwrite different content: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _sha256_bytes(data)


# --------------------------------------------------------------------------- v2 input


def build_v2_input(layer_e: dict[str, Any]) -> dict[str, Any]:
    """Build the Gold-blind executable input from frozen Layer E records.

    Each record carries ONLY: sample_id, approved_text_en, raw_text_de (Layer
    A original German, needed by B0's DE-EN alignment; not adjudication
    content), language, source reference, input text hash and fixed
    provenance.  Adjudication fields (decisions / human_correction /
    llm_candidate / drafts / spans / evidence) are strictly excluded.
    """
    records = []
    seen: set[str] = set()
    for rec in sorted(layer_e["records"], key=lambda r: r["sample_id"]):
        sid = rec["sample_id"]
        if sid in seen:
            raise RuntimeError(f"duplicate sample_id: {sid}")
        seen.add(sid)
        approved = rec.get("approved_text_en")
        raw_de = rec.get("raw_text_de")
        if not isinstance(approved, str) or not approved:
            raise RuntimeError(f"missing approved_text_en in {sid}")
        if not isinstance(raw_de, str) or not raw_de:
            raise RuntimeError(f"missing raw_text_de in {sid}")
        out_record = {
            "sample_id": sid,
            "approved_text_en": approved,
            "raw_text_de": raw_de,
            "language": "en_translated_from_de",
            "source_ref": {
                "german_source": "data/development/estg/estg_selected_150_de.jsonl",
                "legacy_record_id": rec["legacy_record_id"],
                "layer_e_record": "data/development/human_review/estg_150_human_correction_v1.json",
            },
            "input_text_sha256": _sha256_bytes(approved.encode("utf-8")),
            "provenance": {
                "source_layer": "A (raw German) + E approved English text",
                "gold_visible": False,
                "adjudication_fields_excluded": True,
            },
        }
        # defensive: the built record must never carry adjudication content
        for key in FORBIDDEN_V2_FIELDS:
            if key in out_record:
                raise RuntimeError(
                    f"forbidden field {key!r} leaked into v2 record {sid}")
        records.append(out_record)
    if len(records) != 150:
        raise RuntimeError(f"v2 input must contain exactly 150 records, got {len(records)}")
    return {
        "schema_version": "estg150_formal_inference_input@2.0.0",
        "dataset_id": "independently_reconstructed_estg_150_v1",
        "count": 150,
        "claim": "Gold-blind executable model input; NO adjudication content",
        "records": records,
    }


def verify_v2_against_sources(v2: dict[str, Any], layer_e: dict[str, Any],
                              membership_hashes: dict[str, Any],
                              gold_stage2: dict[str, Any]) -> list[str]:
    """Cross-check v2 against frozen sources; returns list of problems."""
    problems: list[str] = []
    le_by_id = {r["sample_id"]: r for r in layer_e["records"]}
    gold_ids = [r["sample_id"] for r in gold_stage2["records"]]
    if len(v2["records"]) != 150:
        problems.append("v2 count != 150")
    if len({r["sample_id"] for r in v2["records"]}) != 150:
        problems.append("v2 sample_ids not unique")
    if sorted(r["sample_id"] for r in v2["records"]) != sorted(gold_ids):
        problems.append("v2 sample_ids != Stage 2 Gold sample_ids")
    for rec in v2["records"]:
        le = le_by_id.get(rec["sample_id"])
        if le is None:
            problems.append(f"sample {rec['sample_id']} missing from Layer E")
            continue
        if le["approved_text_en"] != rec["approved_text_en"]:
            problems.append(f"sample {rec['sample_id']} approved_text_en mismatch")
        if le["raw_text_de"] != rec["raw_text_de"]:
            problems.append(f"sample {rec['sample_id']} raw_text_de mismatch")
        if _sha256_bytes(rec["approved_text_en"].encode("utf-8")) != rec["input_text_sha256"]:
            problems.append(f"sample {rec['sample_id']} input_text_sha256 inconsistent")
    membership = membership_hashes.get("selected_membership", membership_hashes)
    legacy_ids = sorted(int(r["legacy_record_id"]) for r in layer_e["records"])
    payload_str = ",".join(str(i) for i in legacy_ids)
    if _sha256_bytes(payload_str.encode("utf-8")) != membership.get("membership_payload_sha256"):
        problems.append("membership payload hash mismatch vs frozen membership")
    return problems


# --------------------------------------------------------------------------- manifest


def build_release_manifest(v2: dict[str, Any], v2_sha: str, git: dict[str, Any],
                           v1_info: dict[str, Any], gold_info: dict[str, Any],
                           v2_schema_sha: str) -> dict[str, Any]:
    return {
        "schema_version": "formal_benchmark_release_manifest@2.0.0",
        "release": "formal_benchmark_release_v2",
        "release_status": "input_v2_and_gold_published_and_verified",
        "gold_unchanged": True,
        "executable_input_ready": True,
        "formal_predictions_capsule_produced": False,
        "formal_results_capsule_produced": False,
        "final_experiment_ready": False,
        "authorization": {
            "governance_commit": AUTHORIZATION_COMMIT,
            "packet": "formal_gold_authorization_packet_v2",
            "gold_publication_commits": PUBLICATION_COMMITS,
        },
        "artifacts": {
            "estg150_formal_input_v1.json": v1_info,
            "estg150_formal_input_v1.STATUS.md": {
                "path": "data/input/estg150_formal_input_v1.STATUS.md",
                "sha256": v1_info["marker_sha256"],
                "byte_size": v1_info["marker_byte_size"],
                "record_count": 0,
                "schema": "markdown marker",
            },
            "estg150_formal_inference_input_v2.json": {
                "path": "data/input/estg150_formal_inference_input_v2.json",
                "sha256": v2_sha,
                "byte_size": _byte_size(OUT_V2),
                "record_count": len(v2["records"]),
                "schema": "estg150_formal_inference_input@2.0.0",
                "schema_file_sha256": v2_schema_sha,
            },
            "stage2_gold": gold_info["stage2"],
            "stage3_matching_gold": gold_info["matching"],
            "stage3_violation_gold": gold_info["violation"],
        },
        "v1_limitation": {
            "label": "membership-only; not sufficient as executable model input",
            "path": "data/input/estg150_formal_input_v1.json",
            "explanation": (
                "v1 carries only the 150 sample IDs and the membership payload "
                "(membership index). It does not carry the text fields a "
                "Gold-blind runner needs; the executable input is v2."),
        },
        "implementation_hashes": {
            "publisher": _sha256_file(Path(__file__)),
            "validator": _sha256_file(ROOT / "scripts" / "verify_formal_benchmark_release_v2.py")
            if (ROOT / "scripts" / "verify_formal_benchmark_release_v2.py").exists() else "missing",
            "input_v2_schema": v2_schema_sha,
            "stage2_gold_schema": _sha256_file(STAGE2_SCHEMA),
            "stage3_gold_schema": _sha256_file(STAGE3_SCHEMA),
            "prediction_schema": _sha256_file(PREDICTION_SCHEMA),
            "methods_config": _sha256_file(METHODS_CONFIG),
            "experiment_contract": _sha256_file(EXPERIMENT_CONTRACT),
        },
        "source_hashes": {
            "layer_e": _sha256_file(LAYER_E),
            "membership_hashes": _sha256_file(MEMBERSHIP_HASHES),
            "stage3_correction": _sha256_file(STAGE3_CORRECTION),
            "stage3_inference": _sha256_file(STAGE3_INFERENCE),
            "v1_input": v1_info["sha256"],
        },
        "membership": {
            "count": 150,
            "payload_sha256": v2["membership_payload_sha256"],
            "source_membership_path": "data/development/estg/estg_selected_150_de.jsonl",
        },
        "exclusions": {
            "modality_dataset": "not published (license unknown, redistribution/publication forbidden)",
            "gold_rule_records": "DO NOT EXIST (blocked on human adjudication + freeze)",
            "gold_process_records": "DO NOT EXIST (blocked on S1.7)",
        },
        "gold_exposure": {
            "label": "LLM-assisted, human-adjudicated Gold (unchanged from v1 publication)",
            "runner_must_not_read_gold": True,
        },
        "states": {
            "gold_capsule_published_verified": True,
            "executable_input_ready": True,
            "formal_predictions_capsule_produced": False,
            "formal_results_capsule_produced": False,
            "methods_ready": False,
            "final_experiment_ready": False,
        },
        "replay": {
            "no_overwrite": True,
            "deterministic_replay": True,
            "v1_preserved_byte_identical": True,
        },
        "git": git,
    }


def _byte_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


# --------------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="verify inputs and build payloads without writing")
    args = parser.parse_args()

    layer_e = _load_json(LAYER_E, "Layer E")
    membership_hashes = _load_json(MEMBERSHIP_HASHES, "membership hashes")
    gold_stage2 = _load_json(GOLD_STAGE2, "Stage 2 Gold")
    v1 = _load_json(V1_INPUT, "v1 input")
    v1_pub = _load_json(V1_PUBLICATION_MANIFEST, "v1 publication manifest")

    # fail-closed preconditions
    checks: dict[str, bool] = {}
    checks["layer_e freeze_ready"] = all(
        r.get("review_state", {}).get("status") == "adjudicated"
        for r in layer_e["records"]) and len(layer_e["records"]) == 150
    membership = membership_hashes.get("selected_membership", membership_hashes)
    expected_payload = membership.get("membership_payload_sha256")
    legacy_ids = sorted(int(r["legacy_record_id"]) for r in layer_e["records"])
    checks["membership payload hash"] = (
        _sha256_bytes(",".join(str(i) for i in legacy_ids).encode("utf-8"))
        == expected_payload)
    checks["v1 input is membership-only"] = (
        "sample_ids" in v1 and "records" not in v1
        and set(v1.get("sample_ids", [])) == {r["sample_id"] for r in layer_e["records"]})
    checks["v1 publication manifest present"] = v1_pub.get(
        "publication_status") == "artifacts_published_and_verified"
    # previously published Gold artifacts must still verify against v1 manifest
    v1_artifacts = v1_pub.get("artifacts", {})
    for rel, path in (
        ("data/gold/stage2/estg150_formal_gold_v1.json", GOLD_STAGE2),
        ("data/gold/stage3/stage3_matching_gold_v1.json", GOLD_MATCHING),
        ("data/gold/stage3/stage3_violation_gold_v1.json", GOLD_VIOLATION),
    ):
        expected = v1_artifacts.get(rel, {}).get("sha256")
        checks[f"gold unchanged: {rel}"] = expected is not None and _sha256_file(path) == expected

    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise RuntimeError(f"v2 publication preconditions failed: {failed}")

    v2 = build_v2_input(layer_e)
    v2["membership_payload_sha256"] = expected_payload
    problems = verify_v2_against_sources(v2, layer_e, membership_hashes, gold_stage2)
    if problems:
        raise RuntimeError(f"v2 verification against frozen sources failed: {problems}")

    schema_sha = _sha256_file(INPUT_V2_SCHEMA)
    git = {"commit": _git_head(),
           "dirty_paths": _git_dirty_excluding_own_outputs(),
           "note": "release manifest records publisher git state; artifact bytes are commit-independent"}

    v1_info = {
        "path": "data/input/estg150_formal_input_v1.json",
        "sha256": _sha256_file(V1_INPUT),
        "byte_size": _byte_size(V1_INPUT),
        "record_count": len(v1.get("sample_ids", [])),
        "schema": v1.get("schema_version", "unknown"),
        "role": "membership-only; not sufficient as executable model input",
    }
    v1_marker_text = (
        "# estg150_formal_input_v1.json status\n\n"
        "- role: **membership-only; not sufficient as executable model input**\n"
        "- content: 150 sample IDs + membership payload (membership index)\n"
        "- executable Gold-blind text input: `estg150_formal_inference_input_v2.json`\n"
        "- preserved byte-identical from the original publication; not overwritten\n"
    )
    v1_info["marker_sha256"] = _sha256_bytes(v1_marker_text.encode("utf-8"))
    v1_info["marker_byte_size"] = len(v1_marker_text.encode("utf-8"))

    gold_info = {
        "stage2": {"path": "data/gold/stage2/estg150_formal_gold_v1.json",
                   "sha256": _sha256_file(GOLD_STAGE2), "byte_size": _byte_size(GOLD_STAGE2),
                   "record_count": len(gold_stage2["records"]),
                   "schema": gold_stage2.get("schema_version", "unknown")},
        "matching": {"path": "data/gold/stage3/stage3_matching_gold_v1.json",
                     "sha256": _sha256_file(GOLD_MATCHING), "byte_size": _byte_size(GOLD_MATCHING),
                     "record_count": len(_load_json(GOLD_MATCHING, "matching gold").get("items", [])),
                     "schema": "stage3_formal_gold@1.0.0"},
        "violation": {"path": "data/gold/stage3/stage3_violation_gold_v1.json",
                      "sha256": _sha256_file(GOLD_VIOLATION), "byte_size": _byte_size(GOLD_VIOLATION),
                      "record_count": len(_load_json(GOLD_VIOLATION, "violation gold").get("items", [])),
                      "schema": "stage3_formal_gold@1.0.0"},
    }

    manifest = build_release_manifest(v2, _sha256_bytes(_canonical_json(v2)),
                                      git, v1_info, gold_info, schema_sha)

    if args.dry_run:
        print("dry-run: v2 input and release manifest built (not written)")
        print("  v2 records:", len(v2["records"]))
        return 0

    v2_sha = _write_no_overwrite(OUT_V2, v2)
    marker_sha = _write_text_no_overwrite(OUT_V1_MARKER, v1_marker_text)
    # refresh v1_info marker fields with the actually written marker hash
    v1_info["marker_sha256"] = marker_sha
    v1_info["marker_byte_size"] = len(v1_marker_text.encode("utf-8"))
    manifest = build_release_manifest(v2, v2_sha, git, v1_info, gold_info, schema_sha)
    manifest_sha = _write_no_overwrite(OUT_MANIFEST, manifest)

    export_index = {
        "schema_version": "formal_benchmark_release_export_index@1.0.0",
        "release": "formal_benchmark_release_v2",
        "artifacts": {
            "input_v1": {"path": v1_info["path"], "sha256": v1_info["sha256"],
                         "byte_size": v1_info["byte_size"]},
            "input_v1_status_marker": {"path": "data/input/estg150_formal_input_v1.STATUS.md",
                                       "sha256": marker_sha},
            "input_v2": {"path": "data/input/estg150_formal_inference_input_v2.json",
                         "sha256": v2_sha},
            "stage2_gold": {"path": gold_info["stage2"]["path"],
                            "sha256": gold_info["stage2"]["sha256"]},
            "stage3_matching_gold": {"path": gold_info["matching"]["path"],
                                     "sha256": gold_info["matching"]["sha256"]},
            "stage3_violation_gold": {"path": gold_info["violation"]["path"],
                                      "sha256": gold_info["violation"]["sha256"]},
            "release_manifest": {"path": "outputs/reports/formal_benchmark_release_v2.manifest.json",
                                 "sha256": manifest_sha},
        },
        "manifest": {"path": "outputs/reports/formal_benchmark_release_v2.manifest.json",
                     "sha256": manifest_sha},
    }
    _write_no_overwrite(OUT_EXPORT_INDEX, export_index)

    report_lines = [
        "# Formal Benchmark Release v2",
        "",
        f"- release status: input_v2_and_gold_published_and_verified",
        f"- executable input ready: True",
        f"- gold unchanged: True (Stage 2 / Stage 3 Gold byte-identical to v1 publication)",
        f"- formal predictions/results capsule: NOT produced",
        f"- final experiment ready: False",
        "",
        "## v1 input limitation",
        "- `data/input/estg150_formal_input_v1.json` is **membership-only; not sufficient as "
        "executable model input** (150 sample IDs + membership payload only).",
        "- Preserved byte-identical; sidecar marker: `data/input/estg150_formal_input_v1.STATUS.md`.",
        "",
        "## v2 executable Gold-blind input",
        f"- `data/input/estg150_formal_inference_input_v2.json` sha256={v2_sha[:16]}... "
        f"({len(v2['records'])} records)",
        "- fields: sample_id, approved_text_en, raw_text_de, language, source_ref, "
        "input_text_sha256, provenance",
        "- NO adjudication content: no Gold spans/labels, no decisions, no LLM drafts, "
        "no relation/order Gold, no review evidence",
        "",
        "## Artifacts",
    ]
    for path, info in manifest["artifacts"].items():
        report_lines.append(
            f"- `{info['path']}` sha256={info['sha256'][:16]}... "
            f"({info.get('record_count', 'n/a')} records)")
    report_lines += [
        "",
        "## States",
        "- Gold capsule published/verified: True",
        "- Executable formal input ready: True",
        "- Formal predictions/results capsule: NOT produced",
        "- Final experiment ready: False",
        "",
        "## Exclusions (unchanged)",
        "- Modality dataset: NOT published (license unknown, redistribution forbidden)",
        "- Gold Rule Records: DO NOT EXIST (blocked on human adjudication + freeze)",
        "- Gold Process Records: DO NOT EXIST (blocked on S1.7)",
    ]
    _write_text_no_overwrite(OUT_REPORT, "\n".join(report_lines) + "\n")

    print(f"published formal benchmark release v2 ({len(v2['records'])} records)")
    print(f"  data/input/estg150_formal_inference_input_v2.json  {v2_sha[:16]}...")
    print(f"  outputs/reports/formal_benchmark_release_v2.manifest.json  {manifest_sha[:16]}...")
    return 0


def _git_dirty_excluding_own_outputs() -> list[str]:
    outputs = {str(p.relative_to(ROOT)).replace("\\", "/") for p in (
        OUT_V2, OUT_V1_MARKER, OUT_MANIFEST, OUT_REPORT, OUT_EXPORT_INDEX)}
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
            text=True, check=True).stdout.strip()
        entries = out.splitlines()
    except Exception:  # pragma: no cover
        return []
    filtered = []
    for entry in entries:
        path = entry[3:].strip().strip('"').replace("\\", "/").rstrip("/")
        if path.startswith("formal_experiment/"):
            path = path[len("formal_experiment/"):]
        if path in outputs:
            continue
        filtered.append(entry)
    return filtered[:20]


if __name__ == "__main__":
    raise SystemExit(main())
