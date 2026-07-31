"""Shared B0 prediction artifact binding for H1 tooling.

Both ``scripts/run_sun_llm_fallback.py`` (the field-level selective repair
runner) and ``scripts/build_h1_trigger_diagnostics.py`` (the Gold-blind
diagnostic table generator) consume the *same persisted B0 predictions*
used by the B0 arm; neither may recreate B0 with a second extractor.  This
module is the single shared implementation of that binding.

The loader guarantees:

* the persisted B0 attempts file is bound to its manifest by SHA-256
  (``verify_b0_manifest``), otherwise the run fails closed;
* every attempt is a successful ``sun_rule_only`` record with a canonical
  output (schema + cross-field valid) once the inference-visible
  diagnostic fields are removed into telemetry;
* duplicate ``sample_id`` values fail closed;
* loaded records carry ``LoadedB0.telemetry``: per-clause alignment,
  scope stats, modality route, and modality diagnostics -- the only
  inference-visible signals an H1 trigger may consume.

This module is stdlib-only plus ``bpc_hybrid.stage2_canonical``.  It never
touches Gold, Layer E, evaluators, paper_validation, or any LLM/API, and it
never reads ``.env``.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, validate_canonical


class B0ArtifactError(ValueError):
    """Raised for a fail-closed B0 input or binding violation."""


@dataclass
class LoadedB0:
    record: dict[str, Any]
    telemetry: dict[str, Any]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_hash(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return sha256_bytes(payload.encode("utf-8"))


def prediction_hash(record: Mapping[str, Any]) -> str:
    """Hash semantic prediction content, deliberately excluding method metadata."""
    return json_hash({"clauses": record.get("clauses", [])})


def read_json_values(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise B0ArtifactError(f"input file does not exist: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise B0ArtifactError(f"input file is empty: {path}")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        rows: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise B0ArtifactError(
                    f"invalid JSONL at {path}:{line_number}: {exc}"
                ) from exc
            if not isinstance(item, dict):
                raise B0ArtifactError(f"JSONL row {line_number} is not an object")
            rows.append(item)
        return rows

    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        for key in ("attempts", "predictions", "records"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
        else:
            rows = [payload]
    else:
        raise B0ArtifactError(f"JSON input must be an object or array: {path}")
    if not all(isinstance(item, dict) for item in rows):
        raise B0ArtifactError(f"all input rows must be JSON objects: {path}")
    return list(rows)


def _clean_modality(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "label": raw.get("label"),
        "evidence": copy.deepcopy(raw.get("evidence", [])),
    }


def clean_b0_entry(entry: Mapping[str, Any]) -> LoadedB0:
    request_status = entry.get("request_status")
    if request_status not in (None, "ok"):
        raise B0ArtifactError(
            f"B0 attempt {entry.get('sample_id', '?')!r} is not successful: {request_status!r}"
        )
    raw = entry.get("record", entry)
    if not isinstance(raw, Mapping):
        raise B0ArtifactError("B0 entry does not contain a record object")
    method = raw.get("method")
    if not isinstance(method, Mapping) or method.get("name") != "sun_rule_only":
        raise B0ArtifactError(
            f"B0 record {raw.get('sample_id', '?')!r} method must be 'sun_rule_only'"
        )

    clauses: list[dict[str, Any]] = []
    clause_telemetry: list[dict[str, Any]] = []
    for index, raw_clause in enumerate(raw.get("clauses", [])):
        if not isinstance(raw_clause, Mapping):
            raise B0ArtifactError(f"B0 clause {index} is not an object")
        modality = raw_clause.get("modality")
        if not isinstance(modality, Mapping):
            raise B0ArtifactError(f"B0 clause {index} has no modality object")
        clause = {
            "clause_id": raw_clause.get("clause_id"),
            "clause_span": copy.deepcopy(raw_clause.get("clause_span")),
            "modality": _clean_modality(modality),
            "actors": copy.deepcopy(raw_clause.get("actors", [])),
            "actions": copy.deepcopy(raw_clause.get("actions", [])),
            "conditions": copy.deepcopy(raw_clause.get("conditions", [])),
            "constraints": copy.deepcopy(raw_clause.get("constraints", [])),
            "exceptions": copy.deepcopy(raw_clause.get("exceptions", [])),
            "actor_action_map": copy.deepcopy(raw_clause.get("actor_action_map", [])),
            "order_relations": copy.deepcopy(raw_clause.get("order_relations", [])),
        }
        clauses.append(clause)
        clause_telemetry.append(
            {
                "clause_id": clause["clause_id"],
                "alignment": copy.deepcopy(raw_clause.get("alignment", {})),
                "scope_stats": copy.deepcopy(raw_clause.get("scope_stats", {})),
                "modality_route": modality.get("route"),
                "modality_diagnostic": copy.deepcopy(modality.get("diagnostic", {})),
            }
        )

    record = {
        "schema_version": raw.get("schema_version"),
        "sample_id": raw.get("sample_id"),
        "source_id": raw.get("source_id"),
        "source_text": raw.get("source_text"),
        "clauses": clauses,
        "method": {"name": "sun_rule_only", "schema_source": SCHEMA_SOURCE},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
    }
    if "unsupported_or_ambiguous" in raw:
        record["unsupported_or_ambiguous"] = copy.deepcopy(raw["unsupported_or_ambiguous"])
    report = validate_canonical(record)
    if not (report.schema_valid and report.cross_field_valid):
        raise B0ArtifactError(
            f"B0 record {record.get('sample_id', '?')!r} is not canonical after diagnostic "
            f"fields are removed: {report.errors}"
        )
    return LoadedB0(
        record=record,
        telemetry={
            "attempt_runtime": copy.deepcopy(entry.get("runtime", {})),
            "clauses": clause_telemetry,
        },
    )


def load_b0_predictions(path: Path) -> list[LoadedB0]:
    loaded = [clean_b0_entry(item) for item in read_json_values(path)]
    if not loaded:
        raise B0ArtifactError("B0 prediction batch contains no records")
    sample_ids = [item.record["sample_id"] for item in loaded]
    duplicates = sorted({sid for sid in sample_ids if sample_ids.count(sid) > 1})
    if duplicates:
        raise B0ArtifactError(f"duplicate B0 sample_id values: {duplicates}")
    return loaded


def verify_b0_manifest(b0_path: Path, manifest_path: Path | None) -> dict[str, Any]:
    if manifest_path is None:
        candidate = b0_path.parent / "manifest.json"
        manifest_path = candidate if candidate.exists() else None
    if manifest_path is None:
        raise B0ArtifactError(
            "a B0 manifest is required (pass --b0-manifest or place manifest.json beside B0)"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = (((manifest.get("artifacts") or {}).get("attempts") or {}).get("sha256"))
    actual = sha256_file(b0_path)
    if not isinstance(expected, str):
        raise B0ArtifactError(f"B0 manifest has no artifacts.attempts.sha256: {manifest_path}")
    if actual.lower() != expected.lower():
        raise B0ArtifactError(
            f"B0 prediction hash mismatch: manifest={expected.lower()} actual={actual.lower()}"
        )
    return {
        "verified": True,
        "path": str(manifest_path),
        "sha256": sha256_file(manifest_path),
        "run_id": manifest.get("run_id"),
        "method_variant": manifest.get("method_variant"),
        "claim_scope": manifest.get("claim_scope"),
    }
