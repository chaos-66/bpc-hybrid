"""Deterministic S2.3 public-source marker lexicon reconstruction.

The module is stdlib-only and offline.  It converts the versioned local source
snapshot into category resources, verifies exact bytes and hashes, and exposes
the locked entries for later S2.5 extraction work.  It performs no training,
evaluation, translation, Gold access, network access, or LLM/API call.
"""

from __future__ import annotations

import copy
import hashlib
import json
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


SOURCE_REL = "resources/lexicon/public_marker_sources_en_v1.json"
MANIFEST_REL = "resources/lexicon/public_marker_lexicon_en_v1.manifest.json"
EXTENSIONS_REL = "resources/lexicon/development_extensions_en_v1.json"
CONTRACT_REL = "configs/experiment_contract.json"
LEXICON_ID = "public_marker_lexicon_en_v1"
CATEGORY_FILES = {
    "modality": "resources/lexicon/modality_markers_en_v1.json",
    "condition": "resources/lexicon/condition_markers_en_v1.json",
    "constraint": "resources/lexicon/constraint_markers_en_v1.json",
    "exception": "resources/lexicon/exception_markers_en_v1.json",
    "actor": "resources/lexicon/actor_markers_en_v1.json",
}
CATEGORY_ORDER = tuple(CATEGORY_FILES)
EXPECTED_CATEGORY_COUNTS = {
    "modality": 7,
    "condition": 25,
    "constraint": 19,
    "exception": 5,
    "actor": 8,
}
ALLOWED_MODALITY_CLASSES = {"obligation", "prohibition", "permission", "definition"}
ALLOWED_AMBIGUITY = {"low", "medium", "high"}
AMBIGUITY_RANK = {"low": 0, "medium": 1, "high": 2}


class PublicMarkerLexiconError(ValueError):
    """Raised when the source snapshot or generated resources violate S2.3."""


@dataclass(frozen=True)
class PublicMarkerExpectations:
    """Hard lock for the verified production S2.3 artifact set."""

    source_file_sha256: str = "e40c85cf572c68278d8fa2db00a57f193c0c9352aee889096731b6e87e31e369"
    manifest_file_sha256: str = "5b9bafb268469acb33c3779ad4e0d8ce6a9984c4cf900855aeeafc0f332e2bf7"
    combined_payload_sha256: str = "8c3a27b2aa62025ff266b4cb19a1c89984e967539188ccf96820836c2eef7b91"


PUBLIC_MARKER_EXPECTATIONS = PublicMarkerExpectations()


def canonical_json_bytes(value: Any) -> bytes:
    """Return the project's deterministic, human-readable JSON encoding."""

    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _canonical_payload_bytes(value: Any) -> bytes:
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
    """Apply the frozen v1 marker normalization policy."""

    return " ".join(unicodedata.normalize("NFKC", value).strip().split()).casefold()


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicMarkerLexiconError(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise PublicMarkerLexiconError(f"JSON root must be an object: {path}")
    return value


def validate_source_snapshot(source: Mapping[str, Any]) -> None:
    """Validate the versioned, manually curated public-source snapshot."""

    if source.get("schema_version") != "public_marker_sources@1.0.0":
        raise PublicMarkerLexiconError("unexpected source schema_version")
    if source.get("snapshot_id") != "public_marker_sources_en_v1":
        raise PublicMarkerLexiconError("unexpected source snapshot_id")
    if source.get("language") != "en":
        raise PublicMarkerLexiconError("v1 source language must be en")
    if source.get("construction_mode") != "offline_from_preexisting_local_research_audit":
        raise PublicMarkerLexiconError("source construction_mode must remain offline")

    evidence = source.get("local_evidence_snapshot")
    if not isinstance(evidence, Mapping) or evidence.get("path") != (
        "docs/research/SUN_REFERENCE_SNOWBALL_AND_MARKER_AUDIT.md"
    ):
        raise PublicMarkerLexiconError("local evidence snapshot is not pinned")

    policy = source.get("policy")
    if not isinstance(policy, Mapping):
        raise PublicMarkerLexiconError("source policy must be an object")
    required_policy = {
        "artifact_scope": "development_only",
        "action_strategy": "syntax_only_no_action_marker_lexicon",
        "definition_modality_strategy": (
            "sentence_classifier_only_until_an_explicit_public_definition_marker_source_is_pinned"
        ),
    }
    for key, expected in required_policy.items():
        if policy.get(key) != expected:
            raise PublicMarkerLexiconError(f"policy {key} must remain {expected!r}")
    language_strategy = policy.get("language_strategy")
    if not isinstance(language_strategy, Mapping) or (
        language_strategy.get("lexicon_language") != "en"
        or language_strategy.get("machine_translation_in_s2_3") is not False
    ):
        raise PublicMarkerLexiconError("English-only/no-translation policy is invalid")
    extension = policy.get("development_extension_strategy")
    forbidden = set(extension.get("forbidden_evidence", [])) if isinstance(extension, Mapping) else set()
    if not isinstance(extension, Mapping) or (
        extension.get("included_in_v1") is not False
        or extension.get("test_time_additions_forbidden") is not True
        or {"test text", "test labels", "test predictions", "formal Gold", "evaluation results"} - forbidden
    ):
        raise PublicMarkerLexiconError("development extension policy is not fail-closed")
    rights = policy.get("rights_boundary")
    if not isinstance(rights, Mapping) or (
        rights.get("redistribution_allowed") is not False
        or rights.get("formal_use_allowed") is not False
        or rights.get("upstream_license_recheck_completed_in_s2_3") is not False
    ):
        raise PublicMarkerLexiconError("rights/formal-use boundary was relaxed")

    allowed_fields = set(policy.get("allowed_fields", []))
    if allowed_fields != set(CATEGORY_ORDER):
        raise PublicMarkerLexiconError("allowed_fields must equal the five marker categories")

    sources = source.get("sources")
    if not isinstance(sources, list) or not sources:
        raise PublicMarkerLexiconError("sources must be a non-empty array")
    seen_source_ids: set[str] = set()
    raw_markers = 0
    for source_item in sources:
        if not isinstance(source_item, Mapping):
            raise PublicMarkerLexiconError("source entry must be an object")
        source_id = source_item.get("source_id")
        if not isinstance(source_id, str) or not source_id or source_id in seen_source_ids:
            raise PublicMarkerLexiconError("source_id must be non-empty and unique")
        seen_source_ids.add(source_id)
        if source_item.get("license_status") != "not_rechecked_offline":
            raise PublicMarkerLexiconError("S2.3 must not invent an upstream license conclusion")
        if not source_item.get("public_locators") or not source_item.get("verification"):
            raise PublicMarkerLexiconError(f"source {source_id} lacks locator/verification")
        markers = source_item.get("markers")
        if not isinstance(markers, list) or not markers:
            raise PublicMarkerLexiconError(f"source {source_id} has no markers")
        for marker in markers:
            raw_markers += 1
            if not isinstance(marker, Mapping):
                raise PublicMarkerLexiconError("marker entry must be an object")
            field = marker.get("field")
            surface = marker.get("surface")
            if field not in allowed_fields:
                raise PublicMarkerLexiconError(f"unknown marker field: {field!r}")
            if not isinstance(surface, str) or not surface:
                raise PublicMarkerLexiconError("marker surface must be non-empty")
            if surface != normalize_surface(surface):
                raise PublicMarkerLexiconError(
                    f"marker surface must already be normalized: {surface!r}"
                )
            if marker.get("ambiguity") not in ALLOWED_AMBIGUITY:
                raise PublicMarkerLexiconError(f"invalid ambiguity for {surface!r}")
            modality_class = marker.get("modality_class")
            if field == "modality":
                if modality_class not in ALLOWED_MODALITY_CLASSES:
                    raise PublicMarkerLexiconError(
                        f"modality marker lacks a valid class: {surface!r}"
                    )
            elif modality_class is not None:
                raise PublicMarkerLexiconError(
                    f"non-modality marker has modality_class: {surface!r}"
                )
    if raw_markers != 66:
        raise PublicMarkerLexiconError(f"expected 66 transcribed source rows, got {raw_markers}")


def _entry_sort_key(entry: Mapping[str, Any]) -> tuple[int, int, str, str]:
    surface = str(entry["surface"])
    return (-len(surface.split()), -len(surface), surface, str(entry.get("modality_class", "")))


def _flatten_entries(source: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    validate_source_snapshot(source)
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for source_item in source["sources"]:
        source_id = source_item["source_id"]
        source_tier = source_item["source_tier"]
        for marker in source_item["markers"]:
            field = marker["field"]
            surface = normalize_surface(marker["surface"])
            modality_class = marker.get("modality_class", "")
            key = (field, modality_class, surface)
            current = merged.setdefault(
                key,
                {
                    "surface": surface,
                    "normalized": surface,
                    "source_ids": [],
                    "source_tiers": [],
                    "ambiguity": "low",
                },
            )
            current["source_ids"].append(source_id)
            current["source_tiers"].append(source_tier)
            if AMBIGUITY_RANK[marker["ambiguity"]] > AMBIGUITY_RANK[current["ambiguity"]]:
                current["ambiguity"] = marker["ambiguity"]
            if field == "modality":
                current["modality_class"] = modality_class

    result = {category: [] for category in CATEGORY_ORDER}
    for (field, _modality_class, _surface), entry in merged.items():
        entry["source_ids"] = sorted(set(entry["source_ids"]))
        entry["source_tiers"] = sorted(set(entry["source_tiers"]))
        result[field].append(entry)
    for category in CATEGORY_ORDER:
        result[category].sort(key=_entry_sort_key)
        expected = EXPECTED_CATEGORY_COUNTS[category]
        if len(result[category]) != expected:
            raise PublicMarkerLexiconError(
                f"{category} expected {expected} unique markers, got {len(result[category])}"
            )
    return result


def build_artifact_documents(source_path: Path) -> dict[str, dict[str, Any]]:
    """Build every deterministic versioned S2.3 document in memory."""

    source = _load_object(source_path)
    entries = _flatten_entries(source)
    source_file_sha = sha256_file(source_path)
    source_payload_sha = sha256_bytes(_canonical_payload_bytes(source))
    policy_sha = sha256_bytes(_canonical_payload_bytes(source["policy"]))
    combined_payload_sha = sha256_bytes(_canonical_payload_bytes(entries))
    docs: dict[str, dict[str, Any]] = {}

    for category in CATEGORY_ORDER:
        category_entries = entries[category]
        payload_sha = sha256_bytes(_canonical_payload_bytes(category_entries))
        class_counts: dict[str, int] = {}
        if category == "modality":
            for entry in category_entries:
                label = entry["modality_class"]
                class_counts[label] = class_counts.get(label, 0) + 1
            class_counts.setdefault("definition", 0)
        docs[CATEGORY_FILES[category]] = {
            "_meta": {
                "artifact_scope": "development_only",
                "category": category,
                "entry_payload_sha256": payload_sha,
                "generation_policy_sha256": policy_sha,
                "language": "en",
                "lexicon_id": LEXICON_ID,
                "source_file_sha256": source_file_sha,
                "source_payload_sha256": source_payload_sha,
                "source_snapshot_id": source["snapshot_id"],
                "source_table": SOURCE_REL,
            },
            "class_counts": class_counts,
            "entries": category_entries,
            "schema_version": "public_marker_category@1.0.0",
        }

    extension_doc = {
        "_meta": {
            "activation": "not_included_in_v1",
            "artifact_scope": "development_only",
            "language": "en",
            "lexicon_id": LEXICON_ID,
            "policy": source["policy"]["development_extension_strategy"],
            "source_file_sha256": source_file_sha,
        },
        "entries": [],
        "schema_version": "public_marker_extensions@1.0.0",
    }
    docs[EXTENSIONS_REL] = extension_doc

    file_records: dict[str, dict[str, Any]] = {}
    for category in CATEGORY_ORDER:
        relative = CATEGORY_FILES[category]
        file_records[category] = {
            "entry_count": len(entries[category]),
            "entry_payload_sha256": docs[relative]["_meta"]["entry_payload_sha256"],
            "path": relative,
            "sha256": sha256_bytes(canonical_json_bytes(docs[relative])),
        }
    extension_bytes = canonical_json_bytes(extension_doc)
    manifest = {
        "artifact_scope": "development_only",
        "boundaries": {
            "actor_wiktionary_dump_expansion_included": False,
            "evaluation_run": False,
            "formal_use_allowed": False,
            "gold_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "redistribution_allowed": False,
            "s2_4_or_later_activated": False,
            "training_run": False,
        },
        "category_files": file_records,
        "combined_payload_sha256": combined_payload_sha,
        "development_extensions": {
            "entry_count": 0,
            "path": EXTENSIONS_REL,
            "sha256": sha256_bytes(extension_bytes),
            "status": "empty_locked_template_not_included_in_v1",
        },
        "generation": {
            "duplicate_policy": source["policy"]["duplicate_policy"],
            "generation_policy_sha256": policy_sha,
            "normalization": source["policy"]["normalization"],
            "ordering": source["policy"]["ordering"],
        },
        "language": "en",
        "lexicon_id": LEXICON_ID,
        "schema_version": "public_marker_manifest@1.0.0",
        "source_snapshot": {
            "construction_mode": source["construction_mode"],
            "evidence_cutoff": source["evidence_cutoff"],
            "file_sha256": source_file_sha,
            "path": SOURCE_REL,
            "payload_sha256": source_payload_sha,
            "snapshot_id": source["snapshot_id"],
        },
    }
    docs[MANIFEST_REL] = manifest
    return docs


def expected_artifact_bytes(source_path: Path) -> dict[str, bytes]:
    return {
        relative: canonical_json_bytes(document)
        for relative, document in build_artifact_documents(source_path).items()
    }


def materialize_or_check(project_root: Path, *, write: bool) -> dict[str, Any]:
    """Write missing exact artifacts or check that the locked bytes match.

    Existing differing files are never overwritten.  A content change requires
    a new versioned filename and an explicit code/config update.
    """

    root = Path(project_root).resolve()
    source_path = root / SOURCE_REL
    artifacts = expected_artifact_bytes(source_path)
    written: list[str] = []
    checked: list[str] = []
    for relative, expected in artifacts.items():
        target = root / relative
        if target.exists():
            actual = target.read_bytes()
            if actual != expected:
                raise PublicMarkerLexiconError(
                    f"refusing to overwrite versioned artifact with different bytes: {relative}"
                )
            checked.append(relative)
            continue
        if not write:
            raise PublicMarkerLexiconError(f"missing generated artifact: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(expected)
        written.append(relative)
    return {
        "checked": checked,
        "manifest_sha256": sha256_file(root / MANIFEST_REL),
        "source_sha256": sha256_file(source_path),
        "written": written,
    }


def load_public_marker_entries(project_root: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """Load the exact generated entries after byte-for-byte verification."""

    root = Path(project_root).resolve() if project_root else Path(__file__).resolve().parents[3]
    materialize_or_check(root, write=False)
    result: dict[str, list[dict[str, Any]]] = {}
    for category, relative in CATEGORY_FILES.items():
        document = _load_object(root / relative)
        result[category] = copy.deepcopy(document["entries"])
    return result


def verify_public_marker_lexicon(
    project_root: Path,
    *,
    expectations: PublicMarkerExpectations = PUBLIC_MARKER_EXPECTATIONS,
) -> dict[str, Any]:
    """Fail closed unless the exact S2.3 resources and contract lock agree."""

    root = Path(project_root).resolve()
    errors: list[dict[str, str]] = []

    def require(condition: bool, code: str, message: str) -> None:
        if not condition and code not in {item["code"] for item in errors}:
            errors.append({"code": code, "message": message})

    required = [SOURCE_REL, MANIFEST_REL, EXTENSIONS_REL, CONTRACT_REL, *CATEGORY_FILES.values()]
    for relative in required:
        require((root / relative).is_file(), "public_marker_artifact_missing", f"Missing {relative}")
    if errors:
        return {"ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}

    try:
        expected_bytes = expected_artifact_bytes(root / SOURCE_REL)
    except PublicMarkerLexiconError as exc:
        require(False, "public_marker_source_invalid", str(exc))
        return {"ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}

    for relative, expected in expected_bytes.items():
        require(
            (root / relative).read_bytes() == expected,
            "public_marker_generated_bytes_mismatch",
            f"Generated bytes do not match source/policy: {relative}",
        )

    source_sha = sha256_file(root / SOURCE_REL)
    manifest_sha = sha256_file(root / MANIFEST_REL)
    manifest = _load_object(root / MANIFEST_REL)
    combined_sha = manifest.get("combined_payload_sha256")
    require(source_sha == expectations.source_file_sha256, "public_marker_source_hash_mismatch", "Source snapshot SHA-256 changed")
    require(manifest_sha == expectations.manifest_file_sha256, "public_marker_manifest_hash_mismatch", "Manifest SHA-256 changed")
    require(combined_sha == expectations.combined_payload_sha256, "public_marker_payload_hash_mismatch", "Combined marker payload SHA-256 changed")

    contract = _load_object(root / CONTRACT_REL)
    lock = contract.get("stage2_dataset", {}).get("public_marker_lexicon", {})
    require(isinstance(lock, Mapping), "public_marker_contract_missing", "Contract marker lock is missing")
    if isinstance(lock, Mapping):
        contract_values = (
            lock.get("status") == "verified_development_resource_locked",
            lock.get("lexicon_id") == LEXICON_ID,
            lock.get("language") == "en",
            lock.get("source_table", {}).get("path") == SOURCE_REL,
            lock.get("source_table", {}).get("sha256") == source_sha,
            lock.get("manifest", {}).get("path") == MANIFEST_REL,
            lock.get("manifest", {}).get("sha256") == manifest_sha,
            lock.get("combined_payload_sha256") == combined_sha,
            lock.get("category_counts") == EXPECTED_CATEGORY_COUNTS,
            lock.get("development_extension_count") == 0,
            lock.get("formal_use") == "development_only_not_formal",
            lock.get("redistribution_allowed") is False,
            lock.get("training_run") is False,
            lock.get("evaluation_run") is False,
            lock.get("s2_4_or_later_activated") is False,
        )
        require(all(contract_values), "public_marker_contract_mismatch", "Contract marker lock disagrees with exact S2.3 artifacts or boundaries")

    extension = _load_object(root / EXTENSIONS_REL)
    require(extension.get("entries") == [], "public_marker_extension_not_empty", "v1 development extension registry must remain empty")
    ready = not errors
    return {
        "ready": ready,
        "blockers": [item["code"] for item in errors],
        "category_counts": EXPECTED_CATEGORY_COUNTS,
        "combined_payload_sha256": combined_sha,
        "errors": errors,
        "language": "en",
        "lexicon_id": LEXICON_ID,
        "manifest_sha256": manifest_sha,
        "source_sha256": source_sha,
    }


def _fingerprint(project_root: Path) -> tuple[tuple[str, int, int], ...]:
    root = Path(project_root).resolve()
    relatives = [SOURCE_REL, MANIFEST_REL, EXTENSIONS_REL, CONTRACT_REL, *CATEGORY_FILES.values()]
    result: list[tuple[str, int, int]] = []
    for relative in relatives:
        path = root / relative
        try:
            stat = path.stat()
            result.append((relative, stat.st_size, stat.st_mtime_ns))
        except OSError:
            result.append((relative, -1, -1))
    return tuple(result)


@lru_cache(maxsize=8)
def _cached_verify(root: str, fingerprint: tuple[tuple[str, int, int], ...]) -> dict[str, Any]:
    del fingerprint
    return verify_public_marker_lexicon(Path(root))


def get_cached_public_marker_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached_verify(str(root), _fingerprint(root)))
