# -*- coding: utf-8 -*-
"""Publish the frozen S2.11 complex-corpus Gold (zero API, fail closed).

The publisher accepts only the already-applied proposal-v3 confirmation chain.
It copies each adjudicated canonical payload without semantic rewriting and
commits coordinates/hashes/labels only; the third-party source text remains
local-only.  ``--publish`` creates missing artifacts without overwriting
different bytes.  ``--check`` reconstructs every byte and is the replay
command recorded in the publication manifest.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.s2_11_canonical_v3 import (  # noqa: E402
    ORDINARY_FIELDS,
    validate,
)

EVENT_REL = "configs/s2_11_batch_import_confirmation_event_v3.json"
PROPOSAL_REPORT_REL = "outputs/reports/s2_11_proposal_report_v3.json"
DECISIONS_REL = "data/development/human_review/s2_11_review_decisions_v2.json"
MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
G05_REL = "configs/g05_complexity_frozen_v1.json"
SCHEMA_REL = "configs/schemas/s2_11_formal_gold_v1.schema.json"
PUBLISHER_REL = "scripts/publish_s2_11_formal_gold_v1.py"
VERIFIER_REL = "scripts/verify_s2_11_formal_gold_v1.py"
FREEZE_VERIFIER_REL = "scripts/verify_s2_11_review_freeze_v3.py"
CANONICAL_VALIDATOR_REL = "src/bpc_hybrid/s2_11_canonical_v3.py"

GOLD_REL = "data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json"
CAPSULE_REL = "outputs/reports/s2_11_freeze_publication_capsule_v1.json"
CAPSULE_MD_REL = "outputs/reports/s2_11_freeze_publication_capsule_v1.md"
MANIFEST_REL = "outputs/reports/s2_11_formal_gold_v1.manifest.json"
EXPORT_REL = "outputs/reports/s2_11_formal_gold_v1_export_index.json"

EXPECTED_PROPOSAL_SHA256 = (
    "9882ba45d8486235df7fc2411eb7a1c3e5977f87ade527898ff29e45396e6a3b")
EXPECTED_INSTRUCTION = (
    "我确认接受 S2.11 全部 36 条 canonical proposal v3 作为我的裁决（无 revisions），"
    "proposal 文件 SHA-256 = "
    "9882ba45d8486235df7fc2411eb7a1c3e5977f87ade527898ff29e45396e6a3b，"
    "reviewer 署名：hyc。")
REPLAY_COMMAND = (
    "python formal_experiment/scripts/publish_s2_11_formal_gold_v1.py --check")


class PublishFail(RuntimeError):
    """Fail-closed publication error."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublishFail(f"invalid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise PublishFail(f"JSON root is not an object: {path}")
    return value


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8")


def norm_rel(value: str) -> str:
    return value.replace("\\", "/")


def root_path(rel: str) -> Path:
    return ROOT / Path(norm_rel(rel))


def _source_text(sample_id: str, rec: dict[str, Any]) -> str:
    source_path = ROOT.parent / Path(norm_rel(str(rec["path"])))
    if not source_path.is_file():
        raise PublishFail(f"source missing for {sample_id}: {rec['path']}")
    raw = source_path.read_bytes()
    if sha256_bytes(raw) != rec.get("file_sha256"):
        raise PublishFail(f"source file drift for {sample_id}")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublishFail(f"source JSON invalid for {sample_id}") from exc
    _scenario, record_id, version = sample_id.split("/")
    for row in document:
        if str(row.get("ID")) == record_id and \
                str(row.get("version")) == version.lstrip("v"):
            text = str(row.get("text", ""))
            text_bytes = text.encode("utf-8")
            if sha256_bytes(text_bytes) != rec.get("text_sha256"):
                raise PublishFail(f"source text drift for {sample_id}")
            if len(text_bytes) != int(rec.get("text_byte_size", -1)):
                raise PublishFail(f"source text byte-size drift for {sample_id}")
            return text
    raise PublishFail(f"source record not found for {sample_id}")


def strip_proposal_canonical(value: dict[str, Any]) -> dict[str, Any]:
    """Mirror the importer containment transform without importing it."""
    out = copy.deepcopy(value)
    for clause in out.get("clauses", []):
        (clause.get("clause_span") or {}).pop("text", None)
        for span in (clause.get("modality") or {}).get("evidence", []):
            span.pop("text", None)
            span.pop("confidence", None)
        for field in ORDINARY_FIELDS:
            for span in (clause.get(field) or {}).get("spans", []):
                span.pop("text", None)
                span.pop("confidence", None)
                span.pop("normalized", None)
    return out


def _load_freeze_verifier() -> object:
    path = root_path(FREEZE_VERIFIER_REL)
    spec = importlib.util.spec_from_file_location("s211_freeze_for_publish", path)
    if spec is None or spec.loader is None:
        raise PublishFail("cannot load freeze verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def derive() -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the exact Gold payload plus verified derivation evidence."""
    event = load_json(root_path(EVENT_REL))
    report = load_json(root_path(PROPOSAL_REPORT_REL))
    decisions = load_json(root_path(DECISIONS_REL))
    membership = load_json(root_path(MEMBERSHIP_REL))
    g05 = load_json(root_path(G05_REL))

    instruction = event.get("user_instruction_utf8")
    instruction_sha = sha256_bytes(str(instruction).encode("utf-8"))
    checks = {
        "confirmation_kind": event.get("kind")
        == "s2_11_batch_import_confirmation",
        "confirmation_instruction_exact": instruction == EXPECTED_INSTRUCTION,
        "confirmation_instruction_hash": instruction_sha
        == event.get("user_instruction_utf8_sha256"),
        "confirmation_proposal_binding": event.get("proposal_file_sha256")
        == EXPECTED_PROPOSAL_SHA256,
        "confirmation_proposal_source": event.get("proposal_source")
        == "deepseek_offline_proposal_v3",
        "confirmation_reviewer": event.get("reviewer") == "hyc",
        "confirmation_no_revisions": event.get("revisions_file") is None
        and event.get("revisions_file_sha256") is None,
        "confirmation_target": norm_rel(str(event.get("decisions_target")))
        == DECISIONS_REL,
        "proposal_report_source": report.get("proposal_source")
        == "deepseek_offline_proposal_v3",
        "proposal_report_count": report.get("proposal_count") == 36
        and report.get("coverage") == "36/36",
        "proposal_report_binding": report.get("proposal_file_sha256")
        == EXPECTED_PROPOSAL_SHA256,
        "membership_closure": membership.get("record_count") == 40
        and len(membership.get("quarantine") or {}) == 4
        and len(membership.get("records") or {}) == 36,
        "decisions_applied": decisions.get("applied") is True
        and decisions.get("adjudication_pending_user_confirmation") is False,
        "decisions_confirmation_binding": norm_rel(
            str(decisions.get("confirmation_event"))) == EVENT_REL,
        "g0_5_frozen": g05.get("status") == "frozen",
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise PublishFail(f"publication preconditions failed: {failed}")

    proposal_path = root_path(str(report["proposal_file"]))
    proposal_bytes = proposal_path.read_bytes()
    if sha256_bytes(proposal_bytes) != EXPECTED_PROPOSAL_SHA256:
        raise PublishFail("proposal v3 byte drift")
    proposal_lines = [line for line in proposal_bytes.decode("utf-8").splitlines()
                      if line]
    if len(proposal_lines) != 36:
        raise PublishFail("proposal v3 must contain exactly 36 lines")
    proposals = {row["sample_id"]: row for row in
                 (json.loads(line) for line in proposal_lines)}

    members = membership.get("records") or {}
    decision_records = decisions.get("records") or {}
    expected_ids = sorted(members)
    if sorted(proposals) != expected_ids or sorted(decision_records) != expected_ids:
        raise PublishFail("membership/proposal/decisions sample-set mismatch")

    source_texts: dict[str, str] = {}
    validation_records: dict[str, dict[str, Any]] = {}
    gold_records: list[dict[str, Any]] = []
    for sample_id in expected_ids:
        member = members[sample_id]
        source_texts[sample_id] = _source_text(sample_id, member)
        decision = decision_records[sample_id]
        review = decision.get("review_metadata") or {}
        if review.get("review_state") != "adjudicated" or \
                review.get("reviewer") != event.get("reviewer") or \
                norm_rel(str(review.get("confirmation_event"))) != EVENT_REL:
            raise PublishFail(f"reviewer/event mismatch for {sample_id}")
        canonical = decision.get("canonical")
        if not isinstance(canonical, dict):
            raise PublishFail(f"missing canonical decision for {sample_id}")
        proposal_canonical = strip_proposal_canonical(
            proposals[sample_id].get("canonical") or {})
        if canonical != proposal_canonical:
            raise PublishFail(
                f"decision/proposal canonical drift for {sample_id}")
        validation_records[sample_id] = {"canonical": canonical}
        gold_records.append({
            "sample_id": sample_id,
            "source": {
                "path": norm_rel(str(member["path"])),
                "file_sha256": member["file_sha256"],
                "text_sha256": member["text_sha256"],
                "text_byte_size": member["text_byte_size"],
            },
            "canonical": copy.deepcopy(canonical),
        })

    canonical_result = validate(
        validation_records, source_texts, allow_unresolved=False,
        expected_ids=expected_ids)
    if not canonical_result.get("valid"):
        raise PublishFail("canonical/source validation failed: "
                          + "; ".join(canonical_result.get("problems", [])[:10]))
    freeze_result = _load_freeze_verifier().verify()
    if freeze_result.get("verified") is not True or \
            freeze_result.get("frozen") is not True or \
            freeze_result.get("progress", {}).get("adjudicated") != 36:
        raise PublishFail("freeze v3 is not verified frozen 36/36")

    bindings = {
        "confirmation_event": {
            "path": EVENT_REL,
            "sha256": sha256_file(root_path(EVENT_REL)),
            "user_instruction_utf8_sha256": instruction_sha,
        },
        "proposal_report": {
            "path": PROPOSAL_REPORT_REL,
            "sha256": sha256_file(root_path(PROPOSAL_REPORT_REL)),
        },
        "proposal_file": {
            "path": norm_rel(str(report["proposal_file"])),
            "sha256": EXPECTED_PROPOSAL_SHA256,
        },
        "decisions": {
            "path": DECISIONS_REL,
            "sha256": sha256_file(root_path(DECISIONS_REL)),
        },
        "membership": {
            "path": MEMBERSHIP_REL,
            "sha256": sha256_file(root_path(MEMBERSHIP_REL)),
        },
        "g0_5_frozen_config": {
            "path": G05_REL,
            "sha256": sha256_file(root_path(G05_REL)),
        },
    }
    gold = {
        "schema_version": "s2_11_formal_gold@1.0.0",
        "dataset_id": "s2_11_barrientos_complex_corpus_36_v1",
        "publication_status": "formal_frozen_published",
        "claim": "LLM-assisted, user-adjudicated Gold",
        "provenance": {
            "proposal_source": "deepseek_offline_proposal_v3",
            "adjudication": "user_batch_confirmation",
            "reviewer": "hyc",
            "revisions": "none",
            "independent_from_scratch_expert_annotation": False,
            "derivation": ("canonical decisions copied without adding, "
                           "inferring, or rewriting any label, span, "
                           "mapping, or relation"),
        },
        "bindings": bindings,
        "membership": {
            "inventory": 40,
            "objective_exclusions": 4,
            "published_records": 36,
            "sample_ids": expected_ids,
        },
        "records": gold_records,
        "containment": {
            "raw_text_committed": False,
            "source_access": "local_read_only_hash_bound",
            "redistribution": "forbidden_license_unknown",
        },
        "zero_api": {"new_llm_api_calls": 0},
    }
    evidence = {
        "preconditions": checks,
        "bindings": bindings,
        "canonical_validation": canonical_result,
        "freeze": {
            "verified": True,
            "frozen": True,
            "adjudicated": 36,
            "unresolved": 0,
        },
    }
    return gold, evidence


def render_markdown(capsule: dict[str, Any]) -> str:
    return (
        "# S2.11 freeze and formal Gold publication capsule v1\n\n"
        "- Status: **verified / frozen / formally published**\n"
        "- Membership: 36/36 adjudicated; 0 unresolved; 0 blocked\n"
        "- Provenance: `deepseek_offline_proposal_v3` followed by the "
        "user batch confirmation signed `hyc` (no revisions)\n"
        "- Claim boundary: LLM-assisted, user-adjudicated Gold; not an "
        "independent expert annotation from scratch\n"
        "- Containment: committed Gold contains coordinates, source hashes, "
        "labels, actor-action mappings and order relations; no third-party "
        "raw text\n"
        f"- Gold SHA-256: `{capsule['gold']['sha256']}`\n"
        f"- Replay: `{capsule['replay_command']}`\n"
        "- New LLM/API calls: 0\n"
    )


def build_documents() -> dict[str, bytes]:
    gold, evidence = derive()
    gold_data = json_bytes(gold)
    capsule = {
        "schema_version": "s2_11_freeze_publication_capsule@1.0.0",
        "status": "verified_frozen_published",
        "task": "S2.11",
        "freeze": evidence["freeze"],
        "gold": {"path": GOLD_REL, "sha256": sha256_bytes(gold_data),
                 "records": 36},
        "provenance": gold["provenance"],
        "bindings": gold["bindings"],
        "containment": gold["containment"],
        "replay_command": REPLAY_COMMAND,
        "independent_verifier": VERIFIER_REL,
        "zero_api": {"new_llm_api_calls": 0},
    }
    capsule_data = json_bytes(capsule)
    md_data = render_markdown(capsule).encode("utf-8")
    artifacts = {
        GOLD_REL: gold_data,
        CAPSULE_REL: capsule_data,
        CAPSULE_MD_REL: md_data,
    }
    manifest = {
        "schema_version": "s2_11_formal_gold_manifest@1.0.0",
        "publication_status": "verified_frozen_published",
        "dataset_id": gold["dataset_id"],
        "record_count": 36,
        "source_provenance": gold["provenance"],
        "bindings": gold["bindings"],
        "freeze": evidence["freeze"],
        "artifacts": {
            rel: {"path": rel, "sha256": sha256_bytes(data),
                  "byte_size": len(data)}
            for rel, data in artifacts.items()
        },
        "implementation": {
            rel: {"path": rel, "sha256": sha256_file(root_path(rel))}
            for rel in (SCHEMA_REL, PUBLISHER_REL, VERIFIER_REL,
                        FREEZE_VERIFIER_REL, CANONICAL_VALIDATOR_REL)
        },
        "replay_command": REPLAY_COMMAND,
        "verification_command": (
            "python formal_experiment/scripts/verify_s2_11_formal_gold_v1.py"),
        "boundaries": {
            "raw_text_committed": False,
            "gold_rule_records_created": False,
            "stage3_oracle_started": False,
        },
        "zero_api": {"new_llm_api_calls": 0},
    }
    manifest_data = json_bytes(manifest)
    export = {
        "schema_version": "s2_11_formal_gold_export_index@1.0.0",
        "dataset_id": gold["dataset_id"],
        "artifacts": {
            **manifest["artifacts"],
            MANIFEST_REL: {"path": MANIFEST_REL,
                           "sha256": sha256_bytes(manifest_data),
                           "byte_size": len(manifest_data)},
        },
        "schema": {"path": SCHEMA_REL,
                   "sha256": sha256_file(root_path(SCHEMA_REL))},
        "independent_verifier": {
            "path": VERIFIER_REL,
            "sha256": sha256_file(root_path(VERIFIER_REL)),
        },
        "replay_command": REPLAY_COMMAND,
    }
    return {
        **artifacts,
        MANIFEST_REL: manifest_data,
        EXPORT_REL: json_bytes(export),
    }


def publish(documents: dict[str, bytes]) -> None:
    for rel, data in documents.items():
        path = root_path(rel)
        if path.exists():
            if path.read_bytes() != data:
                raise PublishFail(f"refusing to overwrite different content: {rel}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def check(documents: dict[str, bytes]) -> list[str]:
    problems = []
    for rel, expected in documents.items():
        path = root_path(rel)
        if not path.is_file():
            problems.append(f"missing: {rel}")
        elif path.read_bytes() != expected:
            problems.append(f"byte drift: {rel}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        documents = build_documents()
        if args.publish:
            publish(documents)
        problems = check(documents)
        if problems:
            raise PublishFail("; ".join(problems))
    except (PublishFail, OSError, ValueError) as exc:
        print(f"S2.11 FORMAL GOLD PUBLICATION FAILED: {exc}", file=sys.stderr)
        return 2
    print("S2.11 FORMAL GOLD PUBLISHED AND REPLAY-VERIFIED"
          if args.publish else "S2.11 FORMAL GOLD REPLAY VERIFIED")
    print(f"records=36 gold_sha256={sha256_bytes(documents[GOLD_REL])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
