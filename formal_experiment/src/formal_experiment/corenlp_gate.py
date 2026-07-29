"""Fail-closed machine gate for the verified S2.5 CoreNLP extractor."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.sun_style.corenlp_runtime import (
    CONFIG_REL,
    EXTRACTION_ORDER,
    FIXTURE_REL,
    CoreNLPContractError,
    load_runtime_contract,
    resolve_corenlp_runtime,
    validate_fixture_document,
)


PATTERNS_REL = "resources/corenlp/sun_phrase_patterns_v1.json"
LIVE_MANIFEST_REL = "resources/corenlp/s25b_runtime_verification_manifest.json"
SMOKE_INPUT_REL = "tests/fixtures/corenlp/s25b_smoke_input.txt"
LIVE_EXPECTED_REL = "tests/fixtures/corenlp/s25b_live_expected.json"
JAVA_BRIDGE_REL = "tools/corenlp/SunPhraseRuleBridge.java"
LIVE_VERIFIER_REL = "scripts/verify_corenlp_s25b.py"
CONTRACT_REL = "configs/experiment_contract.json"
RULE_SET_ID = "sun_phrase_patterns_en_v1"


@dataclass(frozen=True)
class CoreNLPContractExpectations:
    runtime_config_sha256: str = "30bddb43bdb6f5ec477d9445b413f5e0891675c3855226a5b04747178336e74c"
    pattern_registry_sha256: str = "7cd1f3d590871111724f9fbcc8bbbd34ea83a544226db35845d11602eae24d1c"
    fixture_sha256: str = "df5860316ad927e2513f40497c3793b965c627218872300fa080b53f2e65495b"
    live_manifest_sha256: str = "c3b1ee5a42c13cbc80447a62a957c3c1ef3e9ddd6ef46c36f8754d907f646aa3"
    smoke_input_sha256: str = "25f6cacb3e09ddfa7f380e5a9aa3657ea6c0db16baa23a0e62f35efc61ba1560"
    live_expected_sha256: str = "bd8576f7b41a3b6af70937da63c2062cd68089925c0cec2f569eece0dabdd857"
    java_bridge_sha256: str = "ff3cbd1cffbada086f36cb8238005578c5f19a9a971d25daa8da8613cbb32306"
    live_verifier_sha256: str = "35e1dfcffe355757be913dcc0b79177ad33b07c4f7c45afde89a4dd7c98c41c0"


CORENLP_CONTRACT_EXPECTATIONS = CoreNLPContractExpectations()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CoreNLPContractError(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise CoreNLPContractError(f"JSON root must be an object: {path}")
    return value


def verify_corenlp_contract(
    project_root: Path,
    *,
    expectations: CoreNLPContractExpectations = CORENLP_CONTRACT_EXPECTATIONS,
) -> dict[str, Any]:
    """Verify exact S2.5 bytes, ordering, live evidence, and safety boundaries."""

    root = Path(project_root).resolve()
    errors: list[dict[str, str]] = []

    def require(condition: bool, code: str, message: str) -> None:
        if not condition and code not in {item["code"] for item in errors}:
            errors.append({"code": code, "message": message})

    required = (
        CONFIG_REL,
        PATTERNS_REL,
        FIXTURE_REL,
        LIVE_MANIFEST_REL,
        SMOKE_INPUT_REL,
        LIVE_EXPECTED_REL,
        JAVA_BRIDGE_REL,
        LIVE_VERIFIER_REL,
        CONTRACT_REL,
    )
    for relative in required:
        require((root / relative).is_file(), "s2_5_contract_artifact_missing", f"Missing {relative}")
    if errors:
        return {
            "ready": False,
            "contract_ready": False,
            "runtime_ready": False,
            "errors": errors,
            "blockers": [item["code"] for item in errors],
        }

    config_sha = sha256_file(root / CONFIG_REL)
    patterns_sha = sha256_file(root / PATTERNS_REL)
    fixture_sha = sha256_file(root / FIXTURE_REL)
    live_manifest_sha = sha256_file(root / LIVE_MANIFEST_REL)
    smoke_input_sha = sha256_file(root / SMOKE_INPUT_REL)
    live_expected_sha = sha256_file(root / LIVE_EXPECTED_REL)
    java_bridge_sha = sha256_file(root / JAVA_BRIDGE_REL)
    live_verifier_sha = sha256_file(root / LIVE_VERIFIER_REL)
    require(
        config_sha == expectations.runtime_config_sha256,
        "s2_5_runtime_config_hash_mismatch",
        "S2.5 runtime config SHA-256 changed",
    )
    require(
        patterns_sha == expectations.pattern_registry_sha256,
        "s2_5_pattern_registry_hash_mismatch",
        "S2.5 pattern registry SHA-256 changed",
    )
    require(
        fixture_sha == expectations.fixture_sha256,
        "s2_5_fixture_hash_mismatch",
        "S2.5 fixture SHA-256 changed",
    )
    for actual, expected, code, label in (
        (live_manifest_sha, expectations.live_manifest_sha256, "s2_5_live_manifest_hash_mismatch", "live manifest"),
        (smoke_input_sha, expectations.smoke_input_sha256, "s2_5_smoke_input_hash_mismatch", "smoke input"),
        (live_expected_sha, expectations.live_expected_sha256, "s2_5_live_expected_hash_mismatch", "live expected"),
        (java_bridge_sha, expectations.java_bridge_sha256, "s2_5_java_bridge_hash_mismatch", "Java bridge"),
        (live_verifier_sha, expectations.live_verifier_sha256, "s2_5_live_verifier_hash_mismatch", "live verifier"),
    ):
        require(actual == expected, code, f"S2.5 {label} SHA-256 changed")

    fixture_summary: dict[str, int] = {}
    try:
        runtime_config = load_runtime_contract(root)
        pattern_registry = _load_object(root / PATTERNS_REL)
        fixture = _load_object(root / FIXTURE_REL)
        live_manifest = _load_object(root / LIVE_MANIFEST_REL)
        live_expected = _load_object(root / LIVE_EXPECTED_REL)
        fixture_summary = validate_fixture_document(fixture)
    except CoreNLPContractError as exc:
        require(False, "s2_5_contract_invalid", str(exc))
        runtime_config = {}
        pattern_registry = {}
        live_manifest = {}
        live_expected = {}

    fields = pattern_registry.get("fields")
    field_order = (
        tuple(item.get("field") for item in fields)
        if isinstance(fields, list) and all(isinstance(item, Mapping) for item in fields)
        else ()
    )
    numeric_order = (
        tuple(item.get("order") for item in fields)
        if isinstance(fields, list) and all(isinstance(item, Mapping) for item in fields)
        else ()
    )
    require(
        pattern_registry.get("schema_version") == "sun_tregex_rule_registry@1.0.0"
        and pattern_registry.get("rule_set_id") == RULE_SET_ID,
        "s2_5_pattern_registry_identity_mismatch",
        "S2.5 Tregex registry identity changed",
    )
    require(
        tuple(pattern_registry.get("extraction_order", ())) == EXTRACTION_ORDER
        and field_order == EXTRACTION_ORDER
        and numeric_order == tuple(range(1, 7)),
        "s2_5_extraction_order_mismatch",
        "Required order is modality, condition, constraint, exception, action, actor",
    )
    ordering_policy = pattern_registry.get("ordering_policy", {})
    require(
        isinstance(ordering_policy, Mapping)
        and tuple(ordering_policy.get("action_after_removed_context", ())) == EXTRACTION_ORDER[:4]
        and ordering_policy.get("actor_after_action") is True
        and ordering_policy.get("test_time_rule_edits_forbidden") is True,
        "s2_5_ordering_policy_relaxed",
        "Action/actor ordering or test-time edit policy changed",
    )
    require(
        pattern_registry.get("lexicon", {}).get("combined_payload_sha256")
        == "8c3a27b2aa62025ff266b4cb19a1c89984e967539188ccf96820836c2eef7b91",
        "s2_5_public_marker_binding_mismatch",
        "S2.5 rules no longer bind the verified S2.3 marker payload",
    )
    operations = {
        item.get("field"): item.get("tsurgeon_operations")
        for item in fields
    } if isinstance(fields, list) and all(isinstance(item, Mapping) for item in fields) else {}
    require(
        operations == {
            "modality": ["prune modality"],
            "condition": ["prune condition"],
            "constraint": ["prune constraint"],
            "exception": ["prune exception"],
            "action": [],
            "actor": [],
        },
        "s2_5_tsurgeon_operations_mismatch",
        "S2.5 Tsurgeon cleanup operations changed",
    )
    boundaries = pattern_registry.get("boundaries", {})
    require(
        isinstance(boundaries, Mapping)
        and pattern_registry.get("status") == "live_runtime_synthetic_fixtures_verified"
        and boundaries.get("live_java_tregex_executed") is True
        and boundaries.get("runtime_asset_present") is True
        and boundaries.get("live_verification_manifest") == LIVE_MANIFEST_REL
        and boundaries.get("training_or_evaluation_run") is False
        and boundaries.get("formal_gold_used") is False,
        "s2_5_rule_boundary_invalid",
        "Pattern registry live evidence or safety boundary is invalid",
    )

    raw_evidence = live_manifest.get("locked_evidence", {})
    evidence = raw_evidence if isinstance(raw_evidence, Mapping) else {}
    evidence_artifacts = evidence.get("artifacts", {}) if isinstance(evidence, Mapping) else {}
    evidence_runtime = evidence.get("runtime", {}) if isinstance(evidence, Mapping) else {}
    evidence_live = evidence.get("live_smoke", {}) if isinstance(evidence, Mapping) else {}
    evidence_boundaries = evidence.get("boundaries", {}) if isinstance(evidence, Mapping) else {}
    require(
        live_manifest.get("schema_version") == "s25b_runtime_verification_manifest@1.0.0"
        and live_manifest.get("task_id") == "S2.5-B"
        and evidence.get("schema_version") == "s25b_locked_evidence@1.0.0",
        "s2_5_live_manifest_identity_mismatch",
        "S2.5-B live manifest identity changed",
    )
    require(
        evidence_artifacts == {
            "java_bridge_sha256": java_bridge_sha,
            "live_expected_sha256": live_expected_sha,
            "rule_registry_sha256": patterns_sha,
            "smoke_input_sha256": smoke_input_sha,
        },
        "s2_5_live_manifest_artifact_mismatch",
        "S2.5-B live evidence does not bind the current artifacts",
    )
    runtime_archive = evidence_runtime.get("archive", {}) if isinstance(evidence_runtime, Mapping) else {}
    runtime_jars = evidence_runtime.get("jars", {}) if isinstance(evidence_runtime, Mapping) else {}
    require(
        evidence_runtime.get("corenlp_version") == "4.5.10"
        and runtime_archive.get("archive_sha256") == "76a04089069dad21176c02881f46e07c19ca148b71c8581de2b5b2e2855e042e"
        and runtime_archive.get("archive_bytes") == 508444875
        and runtime_archive.get("archive_entry_count") == 63
        and runtime_archive.get("unsafe_archive_entry_count") == 0
        and runtime_jars.get("code_jar", {}).get("sha256") == "f813ce4ed7319d79225f2a520d40733075c6b3500dd0b81ee069229e461aab43"
        and runtime_jars.get("models_jar", {}).get("sha256") == "a5da9f6feb35a0fd2ea2cbe8909bede3952965b238a68c833ae3e031ed9026a0",
        "s2_5_external_runtime_identity_mismatch",
        "S2.5-B external archive/JAR identity changed",
    )
    live_summary = evidence_live.get("observed", {}).get("summary", {}) if isinstance(evidence_live, Mapping) else {}
    require(
        evidence_live.get("observed") == live_expected
        and evidence_live.get("annotation_summary") == {"dependencies": 28, "sentences": 2, "tokens": 28}
        and live_summary == {"match_count": 11, "pattern_count": 12, "surgery_count": 7, "tree_count": 2},
        "s2_5_live_smoke_mismatch",
        "S2.5-B live observations disagree with the locked synthetic expected fixture",
    )
    require(
        evidence_boundaries == {
            "evaluation_run": False,
            "formal_gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called_by_verifier": False,
            "synthetic_fixture_only": True,
            "third_party_binary_vendored": False,
            "training_run": False,
        },
        "s2_5_live_boundary_mismatch",
        "S2.5-B live verification safety boundaries changed",
    )

    experiment_contract = _load_object(root / CONTRACT_REL)
    lock = experiment_contract.get("sun_stage2_method", {}).get("phrase_extractor_contract", {})
    require(isinstance(lock, Mapping), "s2_5_experiment_contract_missing", "S2.5 lock is absent")
    if isinstance(lock, Mapping):
        contract_values = (
            lock.get("task_id") == "S2.5",
            lock.get("status") == "verified_external_runtime_and_synthetic_live_fixtures",
            lock.get("runtime_config", {}).get("path") == CONFIG_REL,
            lock.get("runtime_config", {}).get("sha256") == config_sha,
            lock.get("pattern_registry", {}).get("path") == PATTERNS_REL,
            lock.get("pattern_registry", {}).get("sha256") == patterns_sha,
            lock.get("fixture", {}).get("path") == FIXTURE_REL,
            lock.get("fixture", {}).get("sha256") == fixture_sha,
            lock.get("runtime_verification_manifest", {}).get("path") == LIVE_MANIFEST_REL,
            lock.get("runtime_verification_manifest", {}).get("sha256") == live_manifest_sha,
            lock.get("live_smoke_input", {}).get("path") == SMOKE_INPUT_REL,
            lock.get("live_smoke_input", {}).get("sha256") == smoke_input_sha,
            lock.get("live_expected", {}).get("path") == LIVE_EXPECTED_REL,
            lock.get("live_expected", {}).get("sha256") == live_expected_sha,
            lock.get("java_bridge", {}).get("path") == JAVA_BRIDGE_REL,
            lock.get("java_bridge", {}).get("sha256") == java_bridge_sha,
            lock.get("live_verifier", {}).get("path") == LIVE_VERIFIER_REL,
            lock.get("live_verifier", {}).get("sha256") == live_verifier_sha,
            tuple(lock.get("extraction_order", ())) == EXTRACTION_ORDER,
            lock.get("contract_verified") is True,
            lock.get("runtime_ready") is True,
            lock.get("s2_5_verified") is True,
            lock.get("training_run") is False,
            lock.get("evaluation_run") is False,
            lock.get("formal_gold_modified") is False,
            lock.get("live_java_tregex_executed") is True,
            lock.get("live_tsurgeon_surgery_count") == 7,
            lock.get("external_binary_vendored") is False,
        )
        require(
            all(contract_values),
            "s2_5_experiment_contract_mismatch",
            "Experiment contract disagrees with S2.5 artifacts or boundaries",
        )

    runtime_probe = resolve_corenlp_runtime(root).to_dict() if runtime_config else {
        "ready": False,
        "home": None,
        "java_executable": None,
        "classpath_entries": [],
        "reasons": ["runtime_contract_invalid"],
    }
    activation_authorized = runtime_config.get("project_boundaries", {}).get(
        "activation_authorized"
    ) is True
    runtime_ready = bool(not errors and activation_authorized)
    contract_ready = not errors
    return {
        "ready": bool(contract_ready and runtime_ready),
        "contract_ready": contract_ready,
        "runtime_probe_ready": bool(runtime_probe.get("ready")),
        "runtime_ready": runtime_ready,
        "blockers": [item["code"] for item in errors],
        "errors": errors,
        "runtime_config_sha256": config_sha,
        "pattern_registry_sha256": patterns_sha,
        "fixture_sha256": fixture_sha,
        "live_manifest_sha256": live_manifest_sha,
        "smoke_input_sha256": smoke_input_sha,
        "live_expected_sha256": live_expected_sha,
        "java_bridge_sha256": java_bridge_sha,
        "live_verifier_sha256": live_verifier_sha,
        "fixture_summary": fixture_summary,
        "extraction_order": list(EXTRACTION_ORDER),
        "runtime_probe": runtime_probe,
        "corenlp_version": runtime_config.get("runtime", {}).get("corenlp_version"),
        "rule_set_id": pattern_registry.get("rule_set_id"),
        "live_summary": live_summary,
        "archive_sha256": runtime_archive.get("archive_sha256"),
    }


def _fingerprint(project_root: Path) -> tuple[tuple[str, int, int], ...]:
    root = Path(project_root).resolve()
    result: list[tuple[str, int, int]] = []
    for relative in (
        CONFIG_REL,
        PATTERNS_REL,
        FIXTURE_REL,
        LIVE_MANIFEST_REL,
        SMOKE_INPUT_REL,
        LIVE_EXPECTED_REL,
        JAVA_BRIDGE_REL,
        LIVE_VERIFIER_REL,
        CONTRACT_REL,
    ):
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
    return verify_corenlp_contract(Path(root))


def get_cached_corenlp_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached_verify(str(root), _fingerprint(root)))
