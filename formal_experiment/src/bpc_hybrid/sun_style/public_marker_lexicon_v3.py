"""Build and verify the source-reconstructed six-field marker lexicon v3.

This module is intentionally offline and stdlib-only. It materializes a
pre-evaluation candidate from the manually transcribed, pinned primary-source
snapshot. It never reads the corpus, Gold, predictions, or evaluation output.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any


SOURCE_REL = "resources/lexicon/public_marker_sources_en_v3.json"
MANIFEST_REL = "resources/lexicon/public_marker_lexicon_en_v3.manifest.json"
REPORT_REL = "docs/research/PUBLIC_MARKER_LEXICON_V3_PROVENANCE_AUDIT.md"
LEXICON_ID = "public_marker_lexicon_en_v3"
CATEGORY_ORDER = (
    "modality",
    "actor",
    "action",
    "condition",
    "constraint",
    "exception",
)
CATEGORY_FILES = {
    field: f"resources/lexicon/{field}_markers_en_v3.json"
    for field in CATEGORY_ORDER
}
RUNTIME_FIELDS = ("actor", "condition", "constraint", "exception")
EXPECTED_COUNTS = {
    "modality": 7,
    "actor": 8,
    "action": 0,
    "condition": 26,
    "constraint": 41,
    "exception": 5,
}
ALLOWED_MODALITY_CLASSES = {"obligation", "prohibition", "permission"}
REQUIRED_SOURCE_FIELDS = {
    "source_id",
    "source_type",
    "title_or_project",
    "url",
    "source_version",
    "source_sha256",
    "access_date",
    "license_status",
    "redistribution_status",
    "exact_location",
    "raw_evidence_text",
    "markers",
}
REQUIRED_MARKER_FIELDS = {"field", "surface", "item_location", "entry_kind"}


class PublicMarkerLexiconV3Error(ValueError):
    """Raised when the v3 evidence or generated freeze is invalid."""


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def canonical_payload_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_surface(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().split()).casefold()


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicMarkerLexiconV3Error(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise PublicMarkerLexiconV3Error(f"JSON root must be an object: {path}")
    return value


def _validate_hash_value(value: Any, label: str) -> None:
    hashes = value.values() if isinstance(value, Mapping) else (value,)
    if not hashes:
        raise PublicMarkerLexiconV3Error(f"{label} has no source hashes")
    for digest in hashes:
        if not isinstance(digest, str) or len(digest) != 64:
            raise PublicMarkerLexiconV3Error(f"{label} has an invalid SHA-256")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise PublicMarkerLexiconV3Error(f"{label} has an invalid SHA-256") from exc


def validate_source_snapshot(source: Mapping[str, Any]) -> None:
    if source.get("schema_version") != "public_marker_sources@2.0.0":
        raise PublicMarkerLexiconV3Error("unexpected source schema_version")
    if source.get("snapshot_id") != "public_marker_sources_en_v3":
        raise PublicMarkerLexiconV3Error("unexpected source snapshot_id")
    if source.get("language") != "en":
        raise PublicMarkerLexiconV3Error("source language must be en")
    policy = source.get("construction_policy")
    if not isinstance(policy, Mapping):
        raise PublicMarkerLexiconV3Error("construction_policy must be an object")
    if policy.get("derived_markers_included") is not False:
        raise PublicMarkerLexiconV3Error("derived markers must remain excluded")
    if policy.get("action_strategy") != "syntax_only_no_action_marker_lexicon":
        raise PublicMarkerLexiconV3Error("Action must remain syntax-only")
    forbidden = set(policy.get("forbidden_inputs", ()))
    required_forbidden = {
        "EStG-150 text",
        "Gold annotations",
        "predictions",
        "FP/FN or evaluation results",
        "LLM synonym suggestions",
    }
    if not required_forbidden.issubset(forbidden):
        raise PublicMarkerLexiconV3Error("forbidden-input boundary was relaxed")

    sources = source.get("sources")
    if not isinstance(sources, list) or not sources:
        raise PublicMarkerLexiconV3Error("sources must be a non-empty array")
    seen_sources: set[str] = set()
    for source_item in sources:
        if not isinstance(source_item, Mapping):
            raise PublicMarkerLexiconV3Error("source entry must be an object")
        missing = REQUIRED_SOURCE_FIELDS - set(source_item)
        if missing:
            raise PublicMarkerLexiconV3Error(
                f"source lacks required fields: {sorted(missing)}"
            )
        source_id = source_item["source_id"]
        if not isinstance(source_id, str) or not source_id or source_id in seen_sources:
            raise PublicMarkerLexiconV3Error("source_id must be non-empty and unique")
        seen_sources.add(source_id)
        for key in (
            "source_type",
            "title_or_project",
            "url",
            "source_version",
            "access_date",
            "license_status",
            "redistribution_status",
            "exact_location",
        ):
            if not isinstance(source_item[key], str) or not source_item[key].strip():
                raise PublicMarkerLexiconV3Error(f"source {source_id} lacks {key}")
        _validate_hash_value(source_item["source_sha256"], str(source_id))
        evidence = source_item["raw_evidence_text"]
        if not isinstance(evidence, (str, Mapping)) or not evidence:
            raise PublicMarkerLexiconV3Error(f"source {source_id} lacks raw evidence")
        markers = source_item["markers"]
        if not isinstance(markers, list) or not markers:
            raise PublicMarkerLexiconV3Error(f"source {source_id} has no markers")
        for marker in markers:
            if not isinstance(marker, Mapping):
                raise PublicMarkerLexiconV3Error("marker must be an object")
            missing_marker = REQUIRED_MARKER_FIELDS - set(marker)
            if missing_marker:
                raise PublicMarkerLexiconV3Error(
                    f"marker lacks required fields: {sorted(missing_marker)}"
                )
            field = marker["field"]
            surface = marker["surface"]
            if field not in CATEGORY_ORDER:
                raise PublicMarkerLexiconV3Error(f"unknown field: {field!r}")
            if not isinstance(surface, str) or not surface.strip():
                raise PublicMarkerLexiconV3Error("marker surface must be non-empty")
            if normalize_surface(surface) != surface:
                raise PublicMarkerLexiconV3Error(
                    f"marker surface must already be normalized: {surface!r}"
                )
            if marker["entry_kind"] not in {
                "verbatim",
                "verbatim_normalized_whitespace",
            }:
                raise PublicMarkerLexiconV3Error(f"invalid entry kind: {surface!r}")
            if not isinstance(marker["item_location"], str) or not marker[
                "item_location"
            ].strip():
                raise PublicMarkerLexiconV3Error(f"marker lacks item location: {surface!r}")
            modality_class = marker.get("modality_class")
            if field == "modality":
                if modality_class not in ALLOWED_MODALITY_CLASSES:
                    raise PublicMarkerLexiconV3Error(
                        f"invalid modality class: {surface!r}"
                    )
            elif modality_class is not None:
                raise PublicMarkerLexiconV3Error(
                    f"non-modality marker has modality_class: {surface!r}"
                )

    defects = source.get("known_v2_provenance_defects")
    if not isinstance(defects, Mapping):
        raise PublicMarkerLexiconV3Error("v2 defect audit is missing")
    groups = defects.get("groups")
    if not isinstance(groups, list):
        raise PublicMarkerLexiconV3Error("v2 defect groups are missing")
    defect_count = sum(len(group.get("markers", ())) for group in groups)
    if defect_count != 106 or defects.get(
        "v2_entries_not_supported_by_the_v3_source_rule"
    ) != 106:
        raise PublicMarkerLexiconV3Error("v2 defect count must remain exactly 106")


def _entry_sort_key(entry: Mapping[str, Any]) -> tuple[int, int, str, str]:
    surface = str(entry["surface"])
    return (
        -len(surface.split()),
        -len(surface),
        surface,
        str(entry.get("modality_class", "")),
    )


def _raw_evidence(source_item: Mapping[str, Any], field: str) -> Any:
    evidence = source_item["raw_evidence_text"]
    if isinstance(evidence, Mapping):
        return evidence.get(field, evidence)
    return evidence


def _provenance(source_item: Mapping[str, Any], marker: Mapping[str, Any]) -> dict[str, Any]:
    record = {
        "source_id": source_item["source_id"],
        "source_type": source_item["source_type"],
        "title_or_project": source_item["title_or_project"],
        "doi": source_item.get("doi"),
        "url": source_item["url"],
        "source_version": source_item["source_version"],
        "source_sha256": source_item["source_sha256"],
        "access_date": source_item["access_date"],
        "license_status": source_item["license_status"],
        "redistribution_status": source_item["redistribution_status"],
        "exact_location": source_item["exact_location"],
        "item_location": marker["item_location"],
        "raw_evidence_text": _raw_evidence(source_item, str(marker["field"])),
    }
    for key in (
        "institutional_mirror_url",
        "institutional_mirror_sha256",
        "official_repository_url",
        "local_primary_source_path",
    ):
        if key in source_item:
            record[key] = source_item[key]
    if "raw_source_surface" in marker:
        record["raw_source_surface"] = marker["raw_source_surface"]
    return record


def flatten_entries(source: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    validate_source_snapshot(source)
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for source_item in source["sources"]:
        for marker in source_item["markers"]:
            field = str(marker["field"])
            surface = normalize_surface(str(marker["surface"]))
            modality_class = str(marker.get("modality_class", ""))
            key = (field, modality_class, surface)
            current = merged.setdefault(
                key,
                {
                    "field": field,
                    "surface": surface,
                    "normalized": surface,
                    "entry_kind": marker["entry_kind"],
                    "is_derived": False,
                    "derivation": None,
                    "provenance": [],
                },
            )
            if marker["entry_kind"] == "verbatim_normalized_whitespace":
                current["entry_kind"] = "verbatim_normalized_whitespace"
            if field == "modality":
                current["modality_class"] = modality_class
            current["provenance"].append(_provenance(source_item, marker))

    result = {field: [] for field in CATEGORY_ORDER}
    for (field, _modality_class, _surface), entry in merged.items():
        entry["provenance"].sort(key=lambda item: str(item["source_id"]))
        result[field].append(entry)
    for field in CATEGORY_ORDER:
        result[field].sort(key=_entry_sort_key)
        if len(result[field]) != EXPECTED_COUNTS[field]:
            raise PublicMarkerLexiconV3Error(
                f"{field} expected {EXPECTED_COUNTS[field]} markers, got {len(result[field])}"
            )
    if sum(map(len, result.values())) != 87:
        raise PublicMarkerLexiconV3Error("candidate must contain exactly 87 entries")
    required_constraints = {
        "equal to",
        "less than",
        "no later than",
        "not equal to",
    }
    constraint_surfaces = {entry["surface"] for entry in result["constraint"]}
    if not required_constraints.issubset(constraint_surfaces):
        raise PublicMarkerLexiconV3Error("full LexNLP constraint phrases are missing")
    if "smallest among" in constraint_surfaces:
        raise PublicMarkerLexiconV3Error("docs-only LexNLP customization leaked into v3")
    return result


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def build_report(
    source: Mapping[str, Any],
    source_sha: str,
    entries: Mapping[str, list[dict[str, Any]]],
    manifest: Mapping[str, Any],
) -> bytes:
    lines = [
        "# Public Marker Lexicon v3 Provenance Audit",
        "",
        "> Status: source-only candidate frozen before evaluation; development use only.",
        "",
        "## Construction boundary",
        "",
        f"- Source snapshot: `{SOURCE_REL}` (`{source_sha}`)",
        "- Selection: verbatim public-paper table items, or the intersection of pinned official LexNLP documentation and code.",
        "- Forbidden during construction: EStG-150 text, Gold, predictions, FP/FN, evaluation metrics, LLM suggestions, and unrecorded derivation.",
        "- Runtime boundary: Actor, Condition, Constraint, and Exception are bound by B0; Modality remains the fixed MD rule; Action remains syntax-only.",
        "- Freeze: the manifest and all category hashes below were generated before paired evaluation.",
        "",
        "## Verified primary sources",
        "",
        "| Source | Type/version | Exact location | Hash | Rights/redistribution |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in source["sources"]:
        hashes = item["source_sha256"]
        if isinstance(hashes, Mapping):
            hash_text = "; ".join(f"{path}: {digest}" for path, digest in hashes.items())
        else:
            hash_text = str(hashes)
        lines.append(
            "| {source} | {kind}; {version} | {location} | {hashes} | {rights}; {redistribution} |".format(
                source=_escape_table(item["source_id"]),
                kind=_escape_table(item["source_type"]),
                version=_escape_table(item["source_version"]),
                location=_escape_table(item["exact_location"]),
                hashes=_escape_table(hash_text),
                rights=_escape_table(item["license_status"]),
                redistribution=_escape_table(item["redistribution_status"]),
            )
        )

    defects = source["known_v2_provenance_defects"]
    lines.extend(
        [
            "",
            "## v2 provenance defects",
            "",
            f"All {defects['v2_total_entries']} v2 records fail at least one new per-marker provenance requirement. Of those, exactly {defects['v2_entries_not_supported_by_the_v3_source_rule']} surfaces are not supported by the v3 source-only selection rule; the remaining 55 surfaces were independently reverified as new v3 records.",
            "",
            "| Field | Finding | Count | Exact v2 surfaces |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for group in defects["groups"]:
        surfaces = ", ".join(f"`{item}`" for item in group["markers"])
        lines.append(
            f"| {_escape_table(group['field'])} | {_escape_table(group['finding'])} | {len(group['markers'])} | {surfaces} |"
        )

    lines.extend(
        [
            "",
            "## Frozen candidate inventory",
            "",
            "| Field | Count | Category SHA-256 |",
            "| --- | ---: | --- |",
        ]
    )
    for field in CATEGORY_ORDER:
        spec = manifest["category_files"][field]
        lines.append(f"| {field} | {spec['entry_count']} | `{spec['sha256']}` |")
    lines.extend(
        [
            f"| **total** | **{sum(EXPECTED_COUNTS.values())}** | combined payload `{manifest['combined_payload_sha256']}` |",
            "",
            "## Per-marker evidence",
            "",
            "| Field | Surface | Class | Source ID(s) | Exact item location(s) | Derived |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for field in CATEGORY_ORDER:
        for entry in entries[field]:
            provenance = entry["provenance"]
            source_ids = "; ".join(item["source_id"] for item in provenance)
            locations = "; ".join(item["item_location"] for item in provenance)
            lines.append(
                "| {field} | `{surface}` | {label} | {sources} | {locations} | no |".format(
                    field=field,
                    surface=_escape_table(entry["surface"]),
                    label=_escape_table(entry.get("modality_class", "—")),
                    sources=_escape_table(source_ids),
                    locations=_escape_table(locations),
                )
            )
    lines.extend(
        [
            "",
            "The report records selection and provenance only. It contains no corpus-derived or evaluation-derived marker decision.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def build_artifact_bytes(source_path: Path) -> dict[str, bytes]:
    source = load_object(source_path)
    entries = flatten_entries(source)
    source_sha = sha256_file(source_path)
    source_payload_sha = sha256_bytes(canonical_payload_bytes(source))
    policy_sha = sha256_bytes(canonical_payload_bytes(source["construction_policy"]))
    artifacts: dict[str, bytes] = {}
    category_records: dict[str, dict[str, Any]] = {}
    for field in CATEGORY_ORDER:
        category_entries = entries[field]
        payload_sha = sha256_bytes(canonical_payload_bytes(category_entries))
        class_counts: dict[str, int] = {}
        if field == "modality":
            for entry in category_entries:
                label = str(entry["modality_class"])
                class_counts[label] = class_counts.get(label, 0) + 1
        document = {
            "_meta": {
                "artifact_scope": "development_parameter_candidate",
                "category": field,
                "entry_payload_sha256": payload_sha,
                "generation_policy_sha256": policy_sha,
                "language": "en",
                "lexicon_id": LEXICON_ID,
                "parent_lexicon_id": "public_marker_lexicon_en_v2",
                "source_file_sha256": source_sha,
                "source_payload_sha256": source_payload_sha,
                "source_snapshot_id": source["snapshot_id"],
                "source_table": SOURCE_REL,
            },
            "class_counts": dict(sorted(class_counts.items())),
            "entries": category_entries,
            "schema_version": "public_marker_category@2.0.0",
        }
        relative = CATEGORY_FILES[field]
        encoded = canonical_json_bytes(document)
        artifacts[relative] = encoded
        category_records[field] = {
            "entry_count": len(category_entries),
            "entry_payload_sha256": payload_sha,
            "path": relative,
            "sha256": sha256_bytes(encoded),
        }
    manifest = {
        "artifact_scope": "development_parameter_candidate",
        "candidate_status": "frozen_pre_evaluation",
        "boundaries": {
            "corpus_or_gold_used_for_construction": False,
            "derived_markers_included": False,
            "evaluation_run_during_construction": False,
            "formal_use_allowed": False,
            "gold_modified": False,
            "llm_api_called": False,
            "source_files_redistributed": False,
            "training_run": False,
        },
        "category_files": category_records,
        "combined_payload_sha256": sha256_bytes(canonical_payload_bytes(entries)),
        "generation": {
            "duplicate_policy": source["construction_policy"]["duplicate_policy"],
            "generation_policy_sha256": policy_sha,
            "normalization": source["construction_policy"]["normalization"],
            "ordering": "descending token count, descending character count, normalized surface, modality class",
            "selection_rule": source["construction_policy"]["selection_rule"],
        },
        "language": "en",
        "lexicon_id": LEXICON_ID,
        "parent_lexicon_id": "public_marker_lexicon_en_v2",
        "runtime_binding": {
            "bound_fields": list(RUNTIME_FIELDS),
            "bound_entry_count": sum(len(entries[field]) for field in RUNTIME_FIELDS),
            "modality": source["construction_policy"]["modality_runtime_strategy"],
            "action": source["construction_policy"]["action_strategy"],
        },
        "schema_version": "public_marker_manifest@2.0.0",
        "source_snapshot": {
            "evidence_cutoff": source["evidence_cutoff"],
            "file_sha256": source_sha,
            "path": SOURCE_REL,
            "payload_sha256": source_payload_sha,
            "snapshot_id": source["snapshot_id"],
        },
    }
    artifacts[MANIFEST_REL] = canonical_json_bytes(manifest)
    artifacts[REPORT_REL] = build_report(source, source_sha, entries, manifest)
    return artifacts


def _validate_v2_defect_surfaces(root: Path, source: Mapping[str, Any]) -> None:
    defects = source["known_v2_provenance_defects"]
    for group in defects["groups"]:
        field = group["field"]
        path = root / f"resources/lexicon/{field}_markers_en_v2.json"
        payload = load_object(path)
        actual = {normalize_surface(str(item["surface"])) for item in payload["entries"]}
        missing = set(group["markers"]) - actual
        if missing:
            raise PublicMarkerLexiconV3Error(
                f"v2 defect audit names missing {field} entries: {sorted(missing)}"
            )


def materialize_or_check(project_root: Path, *, write: bool) -> dict[str, Any]:
    root = Path(project_root).resolve()
    source_path = root / SOURCE_REL
    source = load_object(source_path)
    validate_source_snapshot(source)
    _validate_v2_defect_surfaces(root, source)
    expected = build_artifact_bytes(source_path)
    written: list[str] = []
    checked: list[str] = []
    for relative, content in expected.items():
        target = root / relative
        if target.exists():
            if target.read_bytes() != content:
                raise PublicMarkerLexiconV3Error(
                    f"refusing to overwrite differing versioned artifact: {relative}"
                )
            checked.append(relative)
            continue
        if not write:
            raise PublicMarkerLexiconV3Error(f"missing generated artifact: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        written.append(relative)
    manifest = load_object(root / MANIFEST_REL)
    return {
        "checked": checked,
        "written": written,
        "source_sha256": sha256_file(source_path),
        "manifest_sha256": sha256_file(root / MANIFEST_REL),
        "report_sha256": sha256_file(root / REPORT_REL),
        "combined_payload_sha256": manifest["combined_payload_sha256"],
        "category_files": manifest["category_files"],
    }
