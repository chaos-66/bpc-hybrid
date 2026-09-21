# -*- coding: utf-8 -*-
"""Offline leakage audit for the SEP-C3 definition targeted panel.

The audit never calls a model.  It checks the frozen prompt assets, panel
membership, and (when present) the rendered offline request capsules.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import bpc_hybrid.sep_c3_definition_refinement_prompt as dr  # noqa: E402


PANEL_PATH = ROOT / "configs" / "sep_c3_definition_targeted_panel_v1.json"
GOLD_PATH = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
INPUT_PATH = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
OFFLINE_REQUESTS_PATH = (
    ROOT / "outputs" / "evidence"
    / "sep_c3_definition_targeted_refinement_v1" / "offline_requests.jsonl"
)
LEAKAGE_AUDIT_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_leakage_audit_v1.json"
)
LEAKAGE_AUDIT_MD_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_leakage_audit_v1.md"
)
EVALUATION_CONTRACT_PATH = (
    ROOT / "configs"
    / "sep_c3_definition_targeted_evaluation_contract_v1.json"
)

SAMPLE_ID_RE = re.compile(r"\bestg_\d+\b", re.IGNORECASE)
CLAUSE_ID_RE = re.compile(r"\bestg_\d+_c\d+\b", re.IGNORECASE)
SPAN_ID_RE = re.compile(r"\bestg_\d+_sp\d+\b", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z0-9]+")
REQUEST_KEYS = {
    "model",
    "messages",
    "temperature",
    "top_p",
    "max_tokens",
    "stream",
    "thinking",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(_normalise(text))


def _shingles(text: str, size: int) -> set[tuple[str, ...]]:
    tokens = _tokens(text)
    return {
        tuple(tokens[index:index + size])
        for index in range(max(0, len(tokens) - size + 1))
    }


def _max_shared_shingle(
    left: str, right_texts: Sequence[str], size: int
) -> dict[str, Any]:
    left_shingles = _shingles(left, size)
    best = 0
    best_sample = None
    for text in right_texts:
        shared = left_shingles & _shingles(text, size)
        if len(shared) > best:
            best = len(shared)
            best_sample = text
    return {
        "shingle_size_words": size,
        "shared_shingle_count": best,
        "sample_id": None,
        "status": "pass" if best == 0 else "warn",
    }


def _gold_texts(gold: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(record["sample_id"]): str(record["approved_text_en"])
        for record in gold.get("records") or []
    }


def _gold_clause_texts(gold: Mapping[str, Any]) -> list[str]:
    return [
        str(clause["clause_span"]["text"])
        for record in gold.get("records") or []
        for clause in record.get("clauses") or []
    ]


def _request_payload_text(request: Mapping[str, Any]) -> str:
    return json.dumps(request.get("request_body") or {}, ensure_ascii=False)


def run_audit(
    *,
    panel_path: Path = PANEL_PATH,
    gold_path: Path = GOLD_PATH,
    input_path: Path = INPUT_PATH,
    offline_requests_path: Path = OFFLINE_REQUESTS_PATH,
    write: bool = True,
) -> dict[str, Any]:
    panel = _read_json(panel_path)
    gold = _read_json(gold_path)
    input_doc = _read_json(input_path)
    sample_texts = [str(row.get("approved_text_en") or "") for row in input_doc.get("records") or []]
    sample_texts += [str(row.get("raw_text_de") or "") for row in input_doc.get("records") or []]
    clause_texts = _gold_clause_texts(gold)

    r_def_text = dr.R_DEF_TEXT
    e4_sentence = dr.E4_V2_SENTENCE
    base = dr.render_definition_prompt("BASE")
    rdef = dr.render_definition_prompt("R_DEF")

    checks: dict[str, dict[str, Any]] = {}

    # 1. R_DEF must not contain an EStG sample or full clause text.
    rdef_norm = _normalise(r_def_text)
    full_text_hits = [
        text for text in sample_texts + clause_texts
        if text and _normalise(text) in rdef_norm
    ]
    checks["r_def_no_full_estg_sample_or_clause_text"] = {
        "status": "pass" if not full_text_hits else "fail",
        "hit_count": len(full_text_hits),
        "hits": full_text_hits[:10],
    }

    # 2. R_DEF must not share a long exact word shingle with EStG text.
    rdef_clause_overlap = _max_shared_shingle(r_def_text, clause_texts, 10)
    rdef_sample_overlap = _max_shared_shingle(r_def_text, sample_texts, 12)
    checks["r_def_no_long_estg_shingles"] = {
        "status": (
            "pass"
            if rdef_clause_overlap["shared_shingle_count"] == 0
            and rdef_sample_overlap["shared_shingle_count"] == 0
            else "fail"
        ),
        "clause_10gram_overlap": rdef_clause_overlap,
        "sample_12gram_overlap": rdef_sample_overlap,
    }

    # 3. Synthetic E4 must not be copied from EStG.
    e4_in_sample = [
        sample_id for sample_id, text in _gold_texts(gold).items()
        if _normalise(e4_sentence) in _normalise(text)
    ]
    e4_overlap = _max_shared_shingle(e4_sentence, clause_texts, 8)
    checks["synthetic_e4_not_copied_from_estg"] = {
        "status": (
            "pass"
            if not e4_in_sample and e4_overlap["shared_shingle_count"] == 0
            else "fail"
        ),
        "exact_sample_hits": e4_in_sample,
        "clause_8gram_overlap": e4_overlap,
    }

    # 4. No concrete EStG sample id inside the prompt templates.
    template_blob = "\n".join(
        [
            base.system_prompt,
            base.user_prompt_template,
            rdef.system_prompt,
            rdef.user_prompt_template,
        ]
    )
    checks["no_concrete_sample_id_in_prompt_templates"] = {
        "status": "pass" if not SAMPLE_ID_RE.search(template_blob) else "fail",
        "matches": sorted(set(SAMPLE_ID_RE.findall(template_blob))),
    }

    # 5. Offline request capsules: no Gold ids/labels and exact request schema.
    if offline_requests_path.is_file():
        requests = _read_jsonl(offline_requests_path)
        request_blob = "\n".join(_request_payload_text(row) for row in requests)
        sample_id_matches = sorted(set(SAMPLE_ID_RE.findall(request_blob)))
        clause_id_matches = sorted(set(CLAUSE_ID_RE.findall(request_blob)))
        span_id_matches = sorted(set(SPAN_ID_RE.findall(request_blob)))
        request_key_errors = []
        strict_violations = []
        allowed_interface_occurrence_count = 0
        non_exempt_sample_id_matches = []
        required_sample_id = None
        for index, row in enumerate(requests):
            body = row.get("request_body")
            if not isinstance(body, dict):
                request_key_errors.append({"index": index, "error": "body_not_object"})
                continue
            if set(body) != REQUEST_KEYS:
                request_key_errors.append(
                    {
                        "index": index,
                        "unexpected_keys": sorted(set(body) - REQUEST_KEYS),
                        "missing_keys": sorted(REQUEST_KEYS - set(body)),
                    }
                )
            messages = body.get("messages")
            if not isinstance(messages, list) or len(messages) != 2:
                request_key_errors.append(
                    {"index": index, "error": "messages_shape"}
                )
                continue
            if not all(isinstance(message, dict) for message in messages):
                request_key_errors.append(
                    {"index": index, "error": "messages_not_objects"}
                )
                continue
            expected_sample_id = str(row.get("sample_id") or "")
            required_sample_id = expected_sample_id
            system_content = str(messages[0].get("content") or "")
            user_content = str(messages[1].get("content") or "")
            user_without_interface_ids = user_content
            for field_name in ("sample_id", "source_id"):
                pattern = re.compile(
                    rf"(?m)^[ \t]*{field_name}:[ \t]*"
                    rf"{re.escape(expected_sample_id)}[ \t]*$"
                )
                allowed_interface_occurrence_count += len(
                    pattern.findall(user_without_interface_ids)
                )
                user_without_interface_ids = pattern.sub(
                    "", user_without_interface_ids
                )
            strict_matches = sorted(set(
                SAMPLE_ID_RE.findall(system_content)
                + SAMPLE_ID_RE.findall(user_without_interface_ids)
            ))
            if strict_matches:
                strict_violations.append({
                    "execution_index": row.get("execution_index"),
                    "arm": row.get("arm"),
                    "sample_id": expected_sample_id,
                    "non_exempt_sample_id_matches": strict_matches,
                })
                non_exempt_sample_id_matches.extend(strict_matches)
        checks["offline_requests_no_gold_ids_or_annotations"] = {
            "status": (
                "pass"
                if not clause_id_matches
                and not span_id_matches
                and not request_key_errors
                else "fail"
            ),
            "request_count": len(requests),
            "concrete_sample_id_match_count": len(sample_id_matches),
            "concrete_sample_id_examples": sample_id_matches[:10],
            "concrete_sample_id_policy": (
                "ALLOWED_EXEMPTION_SCHEMA_REQUIRED_INTERFACE_IDENTIFIER_ECHO"
            ),
            "gold_clause_id_match_count": len(clause_id_matches),
            "gold_span_id_match_count": len(span_id_matches),
            "request_schema_errors": request_key_errors[:10],
            "note": (
                "The request bodies necessarily contain the frozen input "
                "source_text; this check looks for Gold annotation identifiers "
                "and schema escapes, not for the input text itself.  Concrete "
                "sample/source IDs are audited separately under the explicit "
                "schema-required interface-identifier exemption."
            ),
        }
        checks["strict_no_concrete_sample_id_in_rendered_model_prompt"] = {
            "status": "pass" if not strict_violations else "fail",
            "detail": (
                "The only concrete sample identifiers allowed in a rendered "
                "model prompt are the exact sample_id/source_id values echoed "
                "on their schema-required interface lines.  All other concrete "
                "sample identifiers are substantive leakage and fail."
            ),
            "sample_id_match_count": len(sample_id_matches),
            "sample_id_examples": sample_id_matches[:10],
            "allowed_exemption": {
                "name": "schema_required_interface_identifier_echo",
                "fields": ["sample_id", "source_id"],
                "scope": (
                    "Existing stage2 output-schema identity echo only; these "
                    "opaque interface values carry no Gold label, span, "
                    "modality, or evaluator information."
                ),
                "required_sample_id": required_sample_id,
                "allowed_identifier_occurrence_count": (
                    allowed_interface_occurrence_count
                ),
                "non_exempt_sample_id_match_count": len(
                    non_exempt_sample_id_matches
                ),
                "non_exempt_sample_id_examples": sorted(set(
                    non_exempt_sample_id_matches
                ))[:10],
                "violations": strict_violations[:10],
            },
        }
    else:
        checks["offline_requests_no_gold_ids_or_annotations"] = {
            "status": "warn",
            "detail": "offline_requests.jsonl not present; render capsule before final authorization",
        }
        checks["strict_no_concrete_sample_id_in_rendered_model_prompt"] = {
            "status": "warn",
            "detail": "no rendered request capsule available to audit",
        }

    # 6. Panel frozen before model output.
    output_dir = (
        ROOT / "outputs" / "development"
        / "sep_c3_definition_targeted_refinement_v1"
    )
    existing_prediction_files = sorted(
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path in output_dir.rglob("canonical_predictions.jsonl")
    ) if output_dir.exists() else []
    checks["panel_frozen_before_model_output"] = {
        "status": "pass" if not existing_prediction_files else "fail",
        "panel_status": panel.get("status"),
        "existing_prediction_files": existing_prediction_files,
    }

    # 7. Evaluation contract must declare post-prediction Gold reading.
    evaluation_contract_ok = False
    if EVALUATION_CONTRACT_PATH.is_file():
        contract = _read_json(EVALUATION_CONTRACT_PATH)
        evaluation_contract_ok = (
            contract.get("gold_read_timing")
            == "after_predictions_are_frozen_and_hashed"
        )
    checks["evaluation_reads_gold_after_predictions_frozen"] = {
        "status": "pass" if evaluation_contract_ok else "warn",
        "detail": (
            "Evaluation contract not yet present"
            if not EVALUATION_CONTRACT_PATH.is_file()
            else "declared" if evaluation_contract_ok else "missing declaration"
        ),
    }

    blocking = [
        key for key, value in checks.items()
        if value.get("status") == "fail"
    ]
    warnings = [
        key for key, value in checks.items()
        if value.get("status") == "warn"
    ]
    if blocking:
        status = "BLOCKED_STRICT_LEAKAGE_CHECK"
    elif warnings:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"

    audit = {
        "schema_version": (
            "sep_c3_definition_targeted_leakage_audit@1.0.0"
        ),
        "status": status,
        "api_calls": 0,
        "panel_status": panel.get("status"),
        "checked_assets": {
            "panel_path": str(panel_path.relative_to(ROOT)).replace("\\", "/"),
            "gold_path": str(gold_path.relative_to(ROOT)).replace("\\", "/"),
            "input_path": str(input_path.relative_to(ROOT)).replace("\\", "/"),
            "offline_requests_path": str(
                offline_requests_path.relative_to(ROOT)
            ).replace("\\", "/"),
            "r_def_sha256": dr.R_DEF_TEXT and __import__("hashlib").sha256(
                dr.R_DEF_TEXT.encode("utf-8")
            ).hexdigest(),
            "candidate_e4_v2_sentence": e4_sentence,
        },
        "checks": checks,
        "blocking_checks": blocking,
        "warnings": warnings,
        "allowed_exemptions": [
            {
                "name": "schema_required_interface_identifier_echo",
                "fields": ["sample_id", "source_id"],
                "policy": (
                    "Concrete sample_id/source_id values are exempt from the "
                    "strict no-concrete-sample-id rule only when they appear as "
                    "the exact, schema-required interface echo in the rendered "
                    "user prompt.  They remain non-semantic opaque identifiers."
                ),
                "substantive_leakage_still_enforced": True,
            }
        ],
        "authorization_implication": (
            "All substantive leakage checks are enforced.  The schema-required "
            "sample_id/source_id interface echo is an explicitly allowed "
            "non-semantic exemption.  Real calls may proceed once all checks pass "
            "and a matching authorization event exists."
            if not blocking
            else "Do not authorize real calls while any check has status fail.  "
            "Inspect blocking_checks; the interface-identifier exemption does "
            "not apply to substantive failures."
        ),
    }

    if write:
        _write_json(LEAKAGE_AUDIT_PATH, audit)
        _write_text(
            LEAKAGE_AUDIT_MD_PATH,
            _render_markdown(audit),
        )
    return audit


def _render_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C3 Definition Targeted Leakage Audit v1",
        "",
        f"- Status: **{audit['status']}**",
        "- API calls: **0**",
        f"- Panel status: `{audit['panel_status']}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "|---|---|",
    ]
    for key, value in audit["checks"].items():
        lines.append(f"| `{key}` | `{value.get('status')}` |")
    lines += [
        "",
        "## Blocking checks",
        "",
    ]
    if audit["blocking_checks"]:
        for key in audit["blocking_checks"]:
            lines.append(f"- `{key}`")
    else:
        lines.append("- none")
    lines += [
        "",
        "## Warnings",
        "",
    ]
    if audit["warnings"]:
        for key in audit["warnings"]:
            lines.append(f"- `{key}`")
    else:
        lines.append("- none")
    if audit.get("allowed_exemptions"):
        lines += [
            "",
            "## Allowed exemptions",
            "",
        ]
        for exemption in audit["allowed_exemptions"]:
            fields = ", ".join(f"`{field}`" for field in exemption["fields"])
            lines.append(
                f"- `{exemption['name']}` ({fields}): {exemption['policy']}"
            )
    lines += [
        "",
        "## Authorization implication",
        "",
        audit["authorization_implication"],
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--panel", type=Path, default=PANEL_PATH)
    parser.add_argument(
        "--offline-requests", type=Path, default=OFFLINE_REQUESTS_PATH
    )
    args = parser.parse_args()
    audit = run_audit(
        panel_path=args.panel,
        offline_requests_path=args.offline_requests,
        write=not args.no_write,
    )
    print(json.dumps({
        "status": audit["status"],
        "blocking_checks": audit["blocking_checks"],
        "warnings": audit["warnings"],
    }, ensure_ascii=False, indent=2))
    return 0 if audit["status"] != "BLOCKED_STRICT_LEAKAGE_CHECK" else 1


if __name__ == "__main__":
    raise SystemExit(main())