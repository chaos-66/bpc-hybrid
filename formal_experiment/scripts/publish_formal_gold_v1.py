# -*- coding: utf-8 -*-
"""Deterministic Formal Gold publisher (zero-API).

Publishes the user-authorized formal Gold artifacts into the canonical
directories:

- data/input/estg150_formal_input_v1.json          (Stage 2 membership/record reference)
- data/gold/stage2/estg150_formal_gold_v1.json     (Stage 2 decision-only canonical Gold)
- data/gold/stage3/stage3_matching_gold_v1.json    (25 matching decisions)
- data/gold/stage3/stage3_violation_gold_v1.json   (33 violation decisions)
- outputs/reports/formal_gold_publication_v1.manifest.json
- outputs/reports/formal_gold_publication_v1.md    (human report)

Preconditions (fail closed): stage3.status==locked, publication gate status in
the exact whitelist, Stage 2 v2 correction 150/150 adjudicated with matching
membership hash, Stage 3 correction 58/58 adjudicated with complete item ids,
and consistent source hashes. Every published value is decision-only and
derives exclusively from the frozen human adjudications; LLM candidate / draft
fields are excluded (only their source hashes are recorded in the manifest).
The modality dataset, Gold Rule Records and Gold Process Records are NOT
published. Deterministic: same frozen sources -> byte-identical outputs (fixed
ordering, no timestamps); no-overwrite with byte-identical replay allowed.

Usage:
    python scripts/publish_formal_gold_v1.py          # publish
    python scripts/publish_formal_gold_v1.py --dry-run
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

CONTRACT = ROOT / "configs" / "experiment_contract.json"
LAYER_E = ROOT / "data" / "development" / "human_review" / "estg_150_human_correction_v1.json"
MEMBERSHIP_HASHES = ROOT / "data" / "development" / "estg" / "estg_150_membership_hashes.json"
STAGE3_CORRECTION = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"
INFERENCE_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_inference_v1.json"
MEMBERSHIP_CONTRACT = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"

OUT_ESTG150_INPUT = ROOT / "data" / "input" / "estg150_formal_input_v1.json"
OUT_STAGE2_GOLD = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
OUT_MATCHING_GOLD = ROOT / "data" / "gold" / "stage3" / "stage3_matching_gold_v1.json"
OUT_VIOLATION_GOLD = ROOT / "data" / "gold" / "stage3" / "stage3_violation_gold_v1.json"
OUT_MANIFEST = ROOT / "outputs" / "reports" / "formal_gold_publication_v1.manifest.json"
OUT_REPORT = ROOT / "outputs" / "reports" / "formal_gold_publication_v1.md"

AUTHORIZATION_DATE = "2026-08-10"
AUTHORIZATION_COMMIT = "5d56f03"

ALLOWED_PUBLICATION_STATUSES = ("ready_for_formal_gold_publication",)
FORBIDDEN_GOLD_FIELDS = ("llm_candidate", "candidate_text_en", "candidate_text_en_sha256",
                         "approved_text_en_history", "_stale", "notes")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} root must be an object")
    return value


def _git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, check=True).stdout.strip()
    except Exception:  # pragma: no cover
        return "unknown"


def _git_dirty() -> list[str]:
    """Porcelain dirty entries, excluding this publisher's own output paths.

    The publisher's own outputs (input/gold/manifest/report) are created by
    this very run, so they must not count as unexpected dirty state; without
    this exclusion the manifest's git snapshot would differ between the first
    run and a byte-identical replay, breaking deterministic replay.
    """
    publisher_outputs = {str(p.relative_to(ROOT)).replace("\\", "/") for p in (
        OUT_ESTG150_INPUT, OUT_STAGE2_GOLD, OUT_MATCHING_GOLD,
        OUT_VIOLATION_GOLD, OUT_MANIFEST, OUT_REPORT)}
    # porcelain reports untracked files grouped by directory, so a freshly
    # created output directory may appear as "?? data/gold/stage2/" instead
    # of per-file entries; exclude those directory-level entries too.
    publisher_dirs = {str(p.parent.relative_to(ROOT)).replace("\\", "/") for p in (
        OUT_ESTG150_INPUT, OUT_STAGE2_GOLD, OUT_MATCHING_GOLD,
        OUT_VIOLATION_GOLD, OUT_MANIFEST, OUT_REPORT)}
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
            text=True, check=True).stdout.strip()
        entries = out.splitlines()
    except Exception:  # pragma: no cover
        return []
    filtered = []
    for entry in entries:
        path = entry[3:].strip().strip('"')
        norm = path.replace("\\", "/").rstrip("/")
        # porcelain may report paths relative to the repo root (e.g. with
        # status.relativePaths=false) instead of relative to ROOT
        if norm.startswith("formal_experiment/"):
            norm = norm[len("formal_experiment/"):]
        if norm in publisher_outputs or norm in publisher_dirs:
            continue
        filtered.append(entry)
    return filtered[:20]


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_no_overwrite(path: Path, payload: dict[str, Any]) -> str:
    """Deterministic write with no-overwrite; byte-identical replay allowed."""
    data = _canonical_json(payload)
    if path.exists():
        existing = path.read_bytes()
        if existing == data:
            return _sha256_bytes(data)
        raise RuntimeError(f"refusing to overwrite different content: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _sha256_bytes(data)


# --------------------------------------------------------------------------- stage 2
def _extract_stage2_gold(layer_e: dict[str, Any]) -> dict[str, Any]:
    records = []
    seen = set()
    for rec in sorted(layer_e["records"], key=lambda r: r["sample_id"]):
        sid = rec["sample_id"]
        if sid in seen:
            raise RuntimeError(f"duplicate sample_id in Layer E: {sid}")
        seen.add(sid)
        hc = rec.get("human_correction") or {}
        clauses = []
        for clause in sorted(hc.get("clauses", []), key=lambda c: c["clause_id"]):
            span = clause.get("clause_span") or {}
            if not (span.get("text") and isinstance(span.get("start"), int)
                    and isinstance(span.get("end"), int)):
                raise RuntimeError(f"invalid clause_span in {sid}/{clause.get('clause_id')}")

            def span_item(item: dict[str, Any] | None) -> dict[str, Any] | None:
                # Layer E six-element items are flat: {id, text, start, end, decision}
                if not item or item.get("text") is None:
                    return None
                return {"id": item["id"], "text": item["text"],
                        "start": item["start"], "end": item["end"]}

            modality = clause.get("modality") or {}
            clauses.append({
                "clause_id": clause["clause_id"],
                "clause_span": {"text": span["text"], "start": span["start"], "end": span["end"]},
                "modality": modality.get("value"),
                "actors": [s for s in (span_item(a) for a in clause.get("actors", [])) if s],
                "actions": [s for s in (span_item(a) for a in clause.get("actions", [])) if s],
                "conditions": [s for s in (span_item(a) for a in clause.get("conditions", [])) if s],
                "constraints": [s for s in (span_item(a) for a in clause.get("constraints", [])) if s],
                "exceptions": [s for s in (span_item(a) for a in clause.get("exceptions", [])) if s],
                "actor_action_map": clause.get("actor_action_map") or [],
                "order_relations": clause.get("order_relations") or [],
            })
        decisions = rec.get("decisions") or {}
        # Per-record provenance: sha256 of the FULL Layer E record (including
        # its immutable llm_candidate copy), so a published Gold record can be
        # verified byte-for-byte against the frozen Layer E source.
        record_sha = _sha256_bytes(_canonical_json(rec))
        records.append({
            "sample_id": sid,
            "approved_text_en": rec.get("approved_text_en"),
            "clauses": clauses,
            "decisions": decisions,
            "source_hashes": {"layer_e_record_sha256": record_sha},
        })
    membership_hashes = _load_json(DEFAULT_PATHS["membership_hashes"], "membership hashes")
    membership = membership_hashes.get("selected_membership", membership_hashes)
    payload_sha = membership.get("membership_payload_sha256")
    if len(seen) != 150 or payload_sha is None:
        raise RuntimeError("Stage 2 membership must be exactly 150 with a payload hash")
    return {
        "schema_version": "stage2_formal_gold@1.0.0",
        "dataset_id": "independently_reconstructed_estg_150_v1",
        "claim": "LLM-assisted, human-adjudicated Gold",
        "membership": {
            "count": 150,
            "payload_sha256": payload_sha,
            "source_membership_path": "data/development/estg/estg_selected_150_de.jsonl",
        },
        "records": records,
    }


def _build_estg150_formal_input(layer_e: dict[str, Any], membership_hashes: dict[str, Any]) -> dict[str, Any]:
    sample_ids = sorted(r["sample_id"] for r in layer_e["records"])
    if len(sample_ids) != 150 or len(set(sample_ids)) != 150:
        raise RuntimeError("formal input must contain exactly 150 unique sample_ids")
    membership = membership_hashes.get("selected_membership", membership_hashes)
    return {
        "schema_version": "stage2_formal_input@1.0.0",
        "dataset_id": "independently_reconstructed_estg_150_v1",
        "count": 150,
        "membership_payload_sha256": membership.get("membership_payload_sha256"),
        "source_german_path": "data/development/estg/estg_selected_150_de.jsonl",
        "sample_ids": sample_ids,
    }


# --------------------------------------------------------------------------- stage 3
def _build_stage3_gold(correction: dict[str, Any], inference: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    corr_m = {i["item_id"]: i for i in correction["matching_items"]}
    corr_v = {i["item_id"]: i for i in correction["violation_items"]}
    inf_m = {i["item_id"] for i in inference["matching_items"]}
    inf_v = {i["item_id"]: i for i in inference["violation_items"]}
    if sorted(inf_m) != sorted(corr_m) or len(corr_m) != 25:
        raise RuntimeError("Stage 3 matching membership must be exactly 25 and match the inference pack")
    if sorted(inf_v) != sorted(corr_v) or len(corr_v) != 33:
        raise RuntimeError("Stage 3 violation membership must be exactly 33 and match the inference pack")

    matching_items = []
    for item_id in sorted(corr_m):
        item = corr_m[item_id]
        if item.get("review_state") != "adjudicated" or item.get("decision_relevant") is None:
            raise RuntimeError(f"matching item {item_id} not adjudicated")
        matching_items.append({
            "item_id": item_id,
            "process_id": item["process_id"],
            "rule_id": item["rule_id"],
            "decision_relevant": item["decision_relevant"],
        })
    violation_items = []
    for item_id in sorted(corr_v):
        item = corr_v[item_id]
        check_type = inf_v[item_id]["check_type"]
        if item.get("review_state") != "adjudicated":
            raise RuntimeError(f"violation item {item_id} not adjudicated")
        violation_items.append({
            "item_id": item_id,
            "process_id": item["process_id"],
            "rule_id": item["rule_id"],
            "check_type": check_type,
            "decision_violation_type": item.get("decision_violation_type"),
            "decision_evidence": item.get("decision_evidence"),
        })
    sources = {
        "correction_pack_sha256": _sha256_file(STAGE3_CORRECTION),
        "inference_pack_sha256": _sha256_file(INFERENCE_PACK),
    }
    matching = {
        "schema_version": "stage3_formal_gold@1.0.0",
        "dataset_id": "stage3_matching_gold_v1",
        "count": 25,
        "items": matching_items,
        "sources": sources,
    }
    violation = {
        "schema_version": "stage3_formal_gold@1.0.0",
        "dataset_id": "stage3_violation_gold_v1",
        "count": 33,
        "items": violation_items,
        "sources": sources,
    }
    return matching, violation


# --------------------------------------------------------------------------- preconditions
# Default source paths; tests may inject synthetic equivalents.
DEFAULT_PATHS = {
    "contract": CONTRACT,
    "layer_e": LAYER_E,
    "membership_hashes": MEMBERSHIP_HASHES,
    "stage3_correction": STAGE3_CORRECTION,
    "inference_pack": INFERENCE_PACK,
}


def _check_preconditions(paths: dict[str, Path] | None = None) -> dict[str, Any]:
    p = paths or DEFAULT_PATHS
    contract = _load_json(p["contract"], "contract")
    gate = contract["formal_gold_publication_gate"]
    checks = {
        "stage3.status == locked": contract["stage3"]["status"] == "locked",
        "publication gate exact whitelist match": (
            gate["status"] in ALLOWED_PUBLICATION_STATUSES
            and gate["status"] in gate.get("allowed_publication_statuses", [])
        ),
        "stage2_dataset.status == locked_for_human_review": (
            contract["stage2_dataset"]["status"] == "locked_for_human_review"),
    }
    layer_e = _load_json(p["layer_e"], "Layer E")
    states = {r["review_state"]["status"] for r in layer_e["records"]}
    checks["layer_e 150/150 adjudicated"] = (
        len(layer_e["records"]) == 150 and states == {"adjudicated"})
    membership = _load_json(p["membership_hashes"], "membership hashes")
    membership = membership.get("selected_membership", membership)
    expected_payload = membership.get("membership_payload_sha256")
    # membership payload = comma-joined sorted legacy record ids (the format
    # produced by scripts/compute_estg_membership_hashes.py)
    legacy_ids = sorted(int(r["legacy_record_id"]) for r in layer_e["records"])
    payload_str = ",".join(str(i) for i in legacy_ids)
    checks["membership payload hash match"] = (
        _sha256_bytes(payload_str.encode("utf-8")) == expected_payload)
    correction = _load_json(p["stage3_correction"], "Stage 3 correction")
    m_ok = (len(correction["matching_items"]) == 25
            and all(i["review_state"] == "adjudicated" for i in correction["matching_items"]))
    v_ok = (len(correction["violation_items"]) == 33
            and all(i["review_state"] == "adjudicated" for i in correction["violation_items"]))
    checks["stage3 25+33 adjudicated"] = m_ok and v_ok
    inference = _load_json(p["inference_pack"], "inference pack")
    checks["inference membership aligned"] = (
        sorted(i["item_id"] for i in inference["matching_items"])
        == sorted(i["item_id"] for i in correction["matching_items"])
        and sorted(i["item_id"] for i in inference["violation_items"])
        == sorted(i["item_id"] for i in correction["violation_items"]))
    failed = [k for k, v in checks.items() if not v]
    if failed:
        raise RuntimeError(f"publication preconditions failed: {failed}")
    return checks


# --------------------------------------------------------------------------- manifest
def _build_manifest(preconditions: dict[str, Any], artifact_hashes: dict[str, str],
                    counts: dict[str, int], git: dict[str, Any],
                    layer_e_sha: str, stage3_corr_sha: str) -> dict[str, Any]:
    return {
        "schema_version": "formal_gold_publication_manifest@1.0.0",
        "publication_status": "artifacts_published_and_verified",
        "authorization": {
            "date": AUTHORIZATION_DATE,
            "contract_commit": AUTHORIZATION_COMMIT,
            "packet": "formal_gold_authorization_packet_v2",
        },
        "preconditions_verified": preconditions,
        "artifacts": {
            path: {"path": path, "sha256": digest,
                   "byte_size": (ROOT / path).stat().st_size if (ROOT / path).exists() else None}
            for path, digest in artifact_hashes.items()
        },
        "record_counts": counts,
        "sources": {
            "layer_e_v2_correction": {"path": "data/development/human_review/estg_150_human_correction_v1.json",
                                      "sha256": layer_e_sha},
            "stage3_correction": {"path": "data/development/human_review/stage3_gold_annotation_human_correction_v1.json",
                                  "sha256": stage3_corr_sha},
            "stage3_inference": {"path": "data/development/human_review/stage3_gold_inference_v1.json",
                                 "sha256": _sha256_file(INFERENCE_PACK)},
            "membership_contract": {"path": "configs/datasets/stage1_stage3_gdpr7_v1.json",
                                    "sha256": _sha256_file(MEMBERSHIP_CONTRACT)},
            "bpmn_dir_aggregate_sha256": _bpmn_aggregate(),
        },
        "gold_exposure": {
            "label": "LLM-assisted, human-adjudicated Gold",
            "note": "values derive exclusively from the user's adjudications; LLM candidate/draft fields are excluded (their layer-E source hash is recorded)",
        },
        "exclusions": {
            "modality_dataset": "not published (license unknown, redistribution/publication forbidden)",
            "gold_rule_records": "DO NOT EXIST (blocked on human adjudication + freeze)",
            "gold_process_records": "DO NOT EXIST (blocked on S1.7)",
            "development_rule_record_adapter_outputs": "not Gold; not published",
        },
        "oracle_status": {
            "s3_7": "blocked_on_s1_7_s2_13",
            "note": "formal Oracle requires true Gold Rule/Process Records (see s37_oracle_readiness_v1.json)",
        },
        "git": git,
        "states": {
            "gate_ready": True,
            "artifacts_published": True,
            "methods_ready": False,
            "formal_experiment_ready": False,
        },
    }


def _bpmn_aggregate() -> str:
    entries = {p.name: _sha256_file(p) for p in sorted(BPMN_DIR.glob("*.bpmn"))}
    return _sha256_bytes(_canonical_json(entries))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="verify preconditions and build payloads without writing")
    args = parser.parse_args()

    preconditions = _check_preconditions()
    layer_e = _load_json(LAYER_E, "Layer E")
    correction = _load_json(STAGE3_CORRECTION, "Stage 3 correction")
    inference = _load_json(INFERENCE_PACK, "inference pack")
    membership_hashes = _load_json(MEMBERSHIP_HASHES, "membership hashes")

    stage2_gold = _extract_stage2_gold(layer_e)
    estg150_input = _build_estg150_formal_input(layer_e, membership_hashes)
    matching_gold, violation_gold = _build_stage3_gold(correction, inference)

    # forbidden-field leak check (defensive, fail closed)
    for item in stage2_gold["records"]:
        for key in FORBIDDEN_GOLD_FIELDS:
            if key in item or any(key in (c or {}) for c in item["clauses"]):
                raise RuntimeError(f"forbidden field leaked into formal Gold: {key}")
    for item in matching_gold["items"] + violation_gold["items"]:
        for key in ("candidate_relevant", "candidate_violation_type", "candidate_evidence",
                    "candidate_location", "rule_text", "rule_ref", "evidence_activity", "review_state"):
            if key in item:
                raise RuntimeError(f"forbidden field leaked into Stage 3 Gold: {key}")

    if args.dry_run:
        print("dry-run: all preconditions verified; payloads built (not written)")
        print("  stage2 records:", len(stage2_gold["records"]))
        print("  matching items:", len(matching_gold["items"]))
        print("  violation items:", len(violation_gold["items"]))
        return 0

    artifact_hashes = {
        "data/input/estg150_formal_input_v1.json": _write_no_overwrite(OUT_ESTG150_INPUT, estg150_input),
        "data/gold/stage2/estg150_formal_gold_v1.json": _write_no_overwrite(OUT_STAGE2_GOLD, stage2_gold),
        "data/gold/stage3/stage3_matching_gold_v1.json": _write_no_overwrite(OUT_MATCHING_GOLD, matching_gold),
        "data/gold/stage3/stage3_violation_gold_v1.json": _write_no_overwrite(OUT_VIOLATION_GOLD, violation_gold),
    }
    counts = {
        "stage2_records": len(stage2_gold["records"]),
        "stage3_matching": len(matching_gold["items"]),
        "stage3_violation": len(violation_gold["items"]),
    }
    manifest = _build_manifest(
        preconditions, artifact_hashes, counts,
        {"commit": _git_head(), "dirty_paths": _git_dirty(),
         "note": "manifest records the publisher's git state at publication time; artifact bytes are commit-independent"},
        _sha256_file(LAYER_E), _sha256_file(STAGE3_CORRECTION),
    )
    manifest_sha = _write_no_overwrite(OUT_MANIFEST, manifest)
    artifact_hashes["outputs/reports/formal_gold_publication_v1.manifest.json"] = manifest_sha

    # human report
    report_lines = [
        "# Formal Gold Publication Report v1",
        "",
        f"- publication_status: {manifest['publication_status']}",
        f"- authorization date: {AUTHORIZATION_DATE} (contract commit {AUTHORIZATION_COMMIT})",
        f"- publisher git commit: {manifest['git']['commit'][:8] if manifest['git']['commit'] != 'unknown' else 'unknown'}",
        "",
        "## Record counts",
        f"- Stage 2 EStG-150 formal Gold: {counts['stage2_records']} records (membership payload "
        f"{stage2_gold['membership']['payload_sha256'][:12]}...)",
        f"- Stage 3 matching Gold: {counts['stage3_matching']}",
        f"- Stage 3 violation Gold: {counts['stage3_violation']}",
        "",
        "## Artifacts",
    ]
    # stable explicit artifact order (dict iteration order must not leak
    # into the human report; the manifest dict gains an entry after it is
    # written, so its insertion order differs between run 1 and replays)
    artifact_order = [
        "data/input/estg150_formal_input_v1.json",
        "data/gold/stage2/estg150_formal_gold_v1.json",
        "data/gold/stage3/stage3_matching_gold_v1.json",
        "data/gold/stage3/stage3_violation_gold_v1.json",
        "outputs/reports/formal_gold_publication_v1.manifest.json",
    ]
    for path in artifact_order:
        digest = artifact_hashes[path]
        report_lines.append(f"- `{path}` sha256={digest[:16]}...")
    report_lines += [
        "",
        "## States",
        "- gate ready: True",
        "- artifacts published: True",
        "- methods ready: False",
        "- formal experiment ready: False",
        "",
        "## Exclusions",
        "- Modality dataset: NOT published (license unknown, redistribution forbidden)",
        "- Gold Rule Records: DO NOT EXIST (blocked on human adjudication + freeze)",
        "- Gold Process Records: DO NOT EXIST (blocked on S1.7)",
        "- development adapter outputs: not Gold, not published",
        "",
        "## Oracle",
        "- S3.7: blocked_on_s1_7_s2_13 (requires true Gold Rule/Process Records)",
        "",
    ]
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    if OUT_REPORT.exists() and OUT_REPORT.read_text(encoding="utf-8") != "\n".join(report_lines) + "\n":
        raise RuntimeError(f"refusing to overwrite different report: {OUT_REPORT}")
    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"published formal Gold artifacts ({counts['stage2_records']} + "
          f"{counts['stage3_matching']} + {counts['stage3_violation']})")
    for path, digest in artifact_hashes.items():
        print(f"  {path}  {digest[:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
