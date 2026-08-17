# -*- coding: utf-8 -*-
"""Independent fail-closed verifier for S2.11 formal Gold v1."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
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

EVENT = ROOT / "configs" / "s2_11_batch_import_confirmation_event_v3.json"
REPORT = ROOT / "outputs" / "reports" / "s2_11_proposal_report_v3.json"
DECISIONS = ROOT / "data" / "development" / "human_review" \
    / "s2_11_review_decisions_v2.json"
MEMBERSHIP = ROOT / "outputs" / "reports" / "s2_11_corpus_membership_v1.json"
G05 = ROOT / "configs" / "g05_complexity_frozen_v1.json"
SCHEMA = ROOT / "configs" / "schemas" / "s2_11_formal_gold_v1.schema.json"
GOLD = ROOT / "data" / "gold" / "stage2" \
    / "s2_11_complex_corpus_formal_gold_v1.json"
CAPSULE = ROOT / "outputs" / "reports" \
    / "s2_11_freeze_publication_capsule_v1.json"
CAPSULE_MD = ROOT / "outputs" / "reports" \
    / "s2_11_freeze_publication_capsule_v1.md"
MANIFEST = ROOT / "outputs" / "reports" \
    / "s2_11_formal_gold_v1.manifest.json"
EXPORT = ROOT / "outputs" / "reports" \
    / "s2_11_formal_gold_v1_export_index.json"
FREEZE_VERIFIER = ROOT / "scripts" / "verify_s2_11_review_freeze_v3.py"
PUBLISHER = ROOT / "scripts" / "publish_s2_11_formal_gold_v1.py"

EXPECTED_PROPOSAL_SHA256 = (
    "9882ba45d8486235df7fc2411eb7a1c3e5977f87ade527898ff29e45396e6a3b")
EXPECTED_INSTRUCTION = (
    "我确认接受 S2.11 全部 36 条 canonical proposal v3 作为我的裁决（无 revisions），"
    "proposal 文件 SHA-256 = "
    "9882ba45d8486235df7fc2411eb7a1c3e5977f87ade527898ff29e45396e6a3b，"
    "reviewer 署名：hyc。")


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(value: str) -> str:
    return value.replace("\\", "/")


def _root_path(rel: str) -> Path:
    return ROOT / Path(_norm(rel))


def _strip(value: dict[str, Any]) -> dict[str, Any]:
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


def _source(sample_id: str, member: dict[str, Any]) -> str:
    path = ROOT.parent / Path(_norm(member["path"]))
    raw = path.read_bytes()
    if _sha_bytes(raw) != member.get("file_sha256"):
        raise ValueError("file drift")
    document = json.loads(raw.decode("utf-8"))
    _scenario, record_id, version = sample_id.split("/")
    for row in document:
        if str(row.get("ID")) == record_id and \
                str(row.get("version")) == version.lstrip("v"):
            text = str(row.get("text", ""))
            data = text.encode("utf-8")
            if _sha_bytes(data) != member.get("text_sha256") or \
                    len(data) != member.get("text_byte_size"):
                raise ValueError("text drift")
            return text
    raise ValueError("record missing")


def _freeze() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("s211_gold_freeze", FREEZE_VERIFIER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.verify()


def _strict_gold_problems(gold: dict[str, Any]) -> list[str]:
    """Dependency-free mirror of the committed schema's closed objects."""
    problems: list[str] = []

    def exact(label: str, value: Any, keys: set[str]) -> bool:
        if not isinstance(value, dict):
            problems.append(f"{label}: not an object")
            return False
        if set(value) != keys:
            problems.append(
                f"{label}: keys={sorted(value)} expected={sorted(keys)}")
            return False
        return True

    exact("gold", gold, {
        "schema_version", "dataset_id", "publication_status", "claim",
        "provenance", "bindings", "membership", "records", "containment",
        "zero_api"})
    exact("provenance", gold.get("provenance"), {
        "proposal_source", "adjudication", "reviewer", "revisions",
        "independent_from_scratch_expert_annotation", "derivation"})
    exact("bindings", gold.get("bindings"), {
        "confirmation_event", "proposal_report", "proposal_file",
        "decisions", "membership", "g0_5_frozen_config"})
    for name, binding in (gold.get("bindings") or {}).items():
        expected = {"path", "sha256", "user_instruction_utf8_sha256"} \
            if name == "confirmation_event" else {"path", "sha256"}
        exact(f"binding.{name}", binding, expected)
    exact("membership", gold.get("membership"), {
        "inventory", "objective_exclusions", "published_records",
        "sample_ids"})
    exact("containment", gold.get("containment"), {
        "raw_text_committed", "source_access", "redistribution"})
    exact("zero_api", gold.get("zero_api"), {"new_llm_api_calls"})
    records = gold.get("records")
    if not isinstance(records, list) or len(records) != 36:
        problems.append("records: expected list of 36")
        return problems
    for ri, record in enumerate(records):
        if not exact(f"record[{ri}]", record,
                     {"sample_id", "source", "canonical"}):
            continue
        exact(f"record[{ri}].source", record.get("source"), {
            "path", "file_sha256", "text_sha256", "text_byte_size"})
        canonical = record.get("canonical")
        if not exact(f"record[{ri}].canonical", canonical,
                     {"clauses", "actor_action_map", "order_relations"}):
            continue
        for ci, clause in enumerate(canonical.get("clauses") or []):
            prefix = f"record[{ri}].clause[{ci}]"
            if not exact(prefix, clause, {
                    "clause_id", "clause_span", "modality", "actor",
                    "action", "condition", "constraint", "exception"}):
                continue
            exact(prefix + ".clause_span", clause.get("clause_span"),
                  {"start", "end"})
            modality = clause.get("modality")
            exact(prefix + ".modality", modality,
                  {"status", "label", "evidence"})
            for si, span in enumerate((modality or {}).get("evidence") or []):
                exact(f"{prefix}.modality.evidence[{si}]", span,
                      {"id", "start", "end"})
            for field in ORDINARY_FIELDS:
                entry = clause.get(field)
                exact(prefix + "." + field, entry, {"status", "spans"})
                for si, span in enumerate((entry or {}).get("spans") or []):
                    exact(f"{prefix}.{field}.spans[{si}]", span,
                          {"id", "start", "end"})
        for mi, edge in enumerate(canonical.get("actor_action_map") or []):
            exact(f"record[{ri}].actor_action_map[{mi}]", edge,
                  {"actor_span_id", "action_span_id"})
        for oi, relation in enumerate(canonical.get("order_relations") or []):
            exact(f"record[{ri}].order_relations[{oi}]", relation,
                  {"before_span_id", "after_span_id"})
    return problems


def verify(*, run_replay: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    required = (EVENT, REPORT, DECISIONS, MEMBERSHIP, G05, SCHEMA, GOLD,
                CAPSULE, CAPSULE_MD, MANIFEST, EXPORT, PUBLISHER)
    check("all publication files exist", all(path.is_file() for path in required))
    if not all(path.is_file() for path in required):
        return {"verified": False, "checks": checks}

    try:
        event = _load(EVENT)
        report = _load(REPORT)
        decisions = _load(DECISIONS)
        membership = _load(MEMBERSHIP)
        g05 = _load(G05)
        gold = _load(GOLD)
        capsule = _load(CAPSULE)
        manifest = _load(MANIFEST)
        export = _load(EXPORT)
    except Exception as exc:  # noqa: BLE001
        check("all JSON readable", False, str(exc))
        return {"verified": False, "checks": checks}
    check("all JSON readable", True)

    schema = _load(SCHEMA)
    check("schema identity and closed-root contract",
          schema.get("$id") == "s2_11_formal_gold_v1.schema.json"
          and schema.get("additionalProperties") is False
          and schema.get("properties", {}).get("schema_version", {}).get(
              "const") == "s2_11_formal_gold@1.0.0")
    strict_problems = _strict_gold_problems(gold)
    check("Gold validates strict schema shape (no extra fields)",
          not strict_problems, "; ".join(strict_problems[:5]))

    instruction = event.get("user_instruction_utf8")
    instruction_sha = _sha_bytes(str(instruction).encode("utf-8"))
    check("confirmation instruction exact", instruction == EXPECTED_INSTRUCTION)
    check("confirmation instruction hash exact",
          instruction_sha == event.get("user_instruction_utf8_sha256"))
    check("confirmation proposal/reviewer/revisions binding",
          event.get("proposal_file_sha256") == EXPECTED_PROPOSAL_SHA256
          and event.get("proposal_source") == "deepseek_offline_proposal_v3"
          and event.get("reviewer") == "hyc"
          and event.get("revisions_file") is None
          and event.get("revisions_file_sha256") is None)

    bindings = gold.get("bindings") or {}
    event_binding = bindings.get("confirmation_event") or {}
    check("Gold binds confirmation event file + instruction separately",
          event_binding.get("sha256") == _sha(EVENT)
          and event_binding.get("user_instruction_utf8_sha256")
          == instruction_sha)
    bound_files_ok = True
    for name in ("proposal_report", "proposal_file", "decisions",
                 "membership", "g0_5_frozen_config"):
        info = bindings.get(name) or {}
        path = _root_path(info.get("path", ""))
        bound_files_ok = bound_files_ok and path.is_file() \
            and _sha(path) == info.get("sha256")
    check("all Gold source bindings match disk", bound_files_ok)
    check("Gold provenance disclosure exact",
          gold.get("provenance") == {
              "proposal_source": "deepseek_offline_proposal_v3",
              "adjudication": "user_batch_confirmation",
              "reviewer": "hyc",
              "revisions": "none",
              "independent_from_scratch_expert_annotation": False,
              "derivation": ("canonical decisions copied without adding, "
                             "inferring, or rewriting any label, span, "
                             "mapping, or relation"),
          })

    proposal_path = _root_path(report.get("proposal_file", ""))
    proposal_sha = _sha(proposal_path) if proposal_path.is_file() else "missing"
    check("proposal v3 file hash exact",
          proposal_sha == report.get("proposal_file_sha256")
          == EXPECTED_PROPOSAL_SHA256)
    proposals: dict[str, dict[str, Any]] = {}
    if proposal_path.is_file():
        try:
            proposals = {row["sample_id"]: row for row in
                         (json.loads(line) for line in
                          proposal_path.read_text(encoding="utf-8").splitlines()
                          if line)}
        except Exception as exc:  # noqa: BLE001
            check("proposal v3 parses", False, str(exc))
    check("proposal v3 parses 36 records", len(proposals) == 36)

    members = membership.get("records") or {}
    decision_records = decisions.get("records") or {}
    gold_records = {row.get("sample_id"): row for row in gold.get("records", [])}
    ids = sorted(members)
    check("membership closure 40/4/36",
          membership.get("record_count") == 40
          and len(membership.get("quarantine") or {}) == 4
          and len(ids) == 36)
    check("membership exactly shared by proposal/decisions/Gold",
          sorted(proposals) == sorted(decision_records)
          == sorted(gold_records) == ids)

    derivation_ok = True
    reviewer_ok = True
    source_ok = True
    source_texts: dict[str, str] = {}
    validation_records: dict[str, dict[str, Any]] = {}
    for sample_id in ids:
        try:
            member = members[sample_id]
            decision = decision_records[sample_id]
            gold_row = gold_records[sample_id]
            review = decision.get("review_metadata") or {}
            reviewer_ok = reviewer_ok and (
                review.get("review_state") == "adjudicated"
                and review.get("reviewer") == "hyc"
                and _norm(str(review.get("confirmation_event")))
                == "configs/s2_11_batch_import_confirmation_event_v3.json")
            expected_canonical = decision.get("canonical")
            derivation_ok = derivation_ok and (
                gold_row == {
                    "sample_id": sample_id,
                    "source": {
                        "path": _norm(member["path"]),
                        "file_sha256": member["file_sha256"],
                        "text_sha256": member["text_sha256"],
                        "text_byte_size": member["text_byte_size"],
                    },
                    "canonical": expected_canonical,
                }
                and _strip(proposals[sample_id]["canonical"])
                == expected_canonical)
            source_texts[sample_id] = _source(sample_id, member)
            validation_records[sample_id] = {"canonical": expected_canonical}
        except Exception:
            source_ok = False
    check("all reviewer/event bindings are hyc + confirmation event", reviewer_ok)
    check("Gold equals decisions and proposal-v3 containment transform", derivation_ok)
    check("all local sources match file/text hashes", source_ok)
    canonical = validate(validation_records, source_texts,
                         allow_unresolved=False, expected_ids=ids)
    check("canonical spans/mappings/relations validate against source",
          canonical.get("valid") is True,
          "; ".join(canonical.get("problems", [])[:5]))

    freeze = _freeze()
    check("freeze v3 independently reports frozen 36/36",
          freeze.get("verified") is True and freeze.get("frozen") is True
          and freeze.get("progress", {}).get("adjudicated") == 36)
    check("G0.5 remains frozen", g05.get("status") == "frozen")
    check("containment excludes third-party raw text",
          gold.get("containment", {}).get("raw_text_committed") is False
          and all("text" not in clause.get("clause_span", {})
                  and all("text" not in span
                          for field in ORDINARY_FIELDS
                          for span in (clause.get(field) or {}).get("spans", []))
                  for row in gold.get("records", [])
                  for clause in row.get("canonical", {}).get("clauses", [])))

    artifact_ok = True
    for info in (manifest.get("artifacts") or {}).values():
        path = _root_path(info.get("path", ""))
        artifact_ok = artifact_ok and path.is_file() \
            and _sha(path) == info.get("sha256") \
            and path.stat().st_size == info.get("byte_size")
    check("manifest artifact hashes and sizes match disk", artifact_ok)
    impl_ok = True
    for info in (manifest.get("implementation") or {}).values():
        path = _root_path(info.get("path", ""))
        impl_ok = impl_ok and path.is_file() and _sha(path) == info.get("sha256")
    check("manifest implementation hashes match disk", impl_ok)

    export_ok = True
    for info in (export.get("artifacts") or {}).values():
        path = _root_path(info.get("path", ""))
        export_ok = export_ok and path.is_file() \
            and _sha(path) == info.get("sha256") \
            and path.stat().st_size == info.get("byte_size")
    verifier_info = export.get("independent_verifier") or {}
    verifier_path = _root_path(verifier_info.get("path", ""))
    export_ok = export_ok and verifier_path.is_file() \
        and _sha(verifier_path) == verifier_info.get("sha256")
    check("export index artifacts and verifier match disk", export_ok)
    check("capsule status/hash/replay exact",
          capsule.get("status") == "verified_frozen_published"
          and capsule.get("gold", {}).get("sha256") == _sha(GOLD)
          and capsule.get("replay_command")
          == "python formal_experiment/scripts/"
             "publish_s2_11_formal_gold_v1.py --check")
    check("zero API / no Gold Rule Records / Oracle not started",
          gold.get("zero_api", {}).get("new_llm_api_calls") == 0
          and manifest.get("boundaries", {}).get("gold_rule_records_created")
          is False
          and manifest.get("boundaries", {}).get("stage3_oracle_started")
          is False)

    if run_replay:
        proc = subprocess.run(
            [sys.executable, str(PUBLISHER), "--check"], cwd=ROOT.parent,
            capture_output=True, text=True)
        check("publisher replay command succeeds byte-identically",
              proc.returncode == 0, (proc.stderr or proc.stdout)[-500:])

    return {"verified": all(item["ok"] for item in checks),
            "checks": checks}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skip-replay", action="store_true")
    args = parser.parse_args()
    result = verify(run_replay=not args.skip_replay)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        for item in result["checks"]:
            print(("PASS" if item["ok"] else "FAIL"), item["name"],
                  item["detail"])
        print("S2.11 FORMAL GOLD VERIFIED" if result["verified"]
              else "S2.11 FORMAL GOLD NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
