"""Historical two-pass GPT-5.6 Sol relay runner for EStG-150.

This is a development-only path. It never reads or writes Layer E and it never
sets a human review state. The default is a dry run. A real call additionally
requires explicit relay-risk, non-human-output, price-unit, budget, call-cap,
run-id, and pilot/full-batch confirmations. The API key is accepted only via a
hidden prompt or the value of a user-named environment variable. Real execution
is now retired in favor of ``run_estg150_candidate_protocol.py``; the helpers
remain only for historical provenance verification and offline regression.
"""
from __future__ import annotations

import argparse
import datetime as dt
import getpass
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "configs" / "estg150_ai_review_gpt56sol_v1.json"
LAYER_A_PATH = ROOT / "data" / "development" / "estg" / "estg_selected_150_de.jsonl"
LAYER_B_PATH = ROOT / "data" / "development" / "human_review" / "estg_150_translation_en_v1.jsonl"
LAYER_C_PATH = ROOT / "data" / "development" / "human_review" / "estg_150_llm_six_element_candidates_v1.jsonl"
MEMBERSHIP_PATH = ROOT / "data" / "development" / "estg" / "estg_150_membership_hashes.json"
OUTPUT_ROOT = ROOT / "data" / "development" / "estg" / "llm_candidate_runs"
EXPECTED_MEMBERSHIP_SHA256 = "8573e105d2bc167c6aa0a92c16f79a3aaf725baadfea86f0b5d2b1ea68b1e0d7"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


class CandidateValidationError(ValueError):
    """The provider returned JSON that is not a valid candidate."""


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise SystemExit(f"{path}:{line_number}: expected a JSON object")
            rows.append(value)
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def normalize_chat_completions_endpoint(value: str) -> str:
    """Accept the relay's /v1 base or full Chat Completions URL."""
    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme.lower() != "https":
        raise ValueError("the public relay endpoint must use https")
    if parsed.username or parsed.password:
        raise ValueError("endpoint userinfo is forbidden")
    if parsed.query or parsed.fragment:
        raise ValueError("endpoint query strings and fragments are forbidden")
    if (parsed.hostname or "").lower() != "api.chatanywhere.tech":
        raise ValueError("this locked runner accepts only api.chatanywhere.tech")
    if parsed.port not in (None, 443):
        raise ValueError("only the default HTTPS port is accepted")
    path = parsed.path.rstrip("/")
    if path == "/v1":
        path = "/v1/chat/completions"
    if path != "/v1/chat/completions":
        raise ValueError("endpoint path must be /v1 or /v1/chat/completions")
    return urllib.parse.urlunsplit(("https", "api.chatanywhere.tech", path, "", ""))


def load_contract() -> tuple[dict[str, Any], dict[str, Any], str, str]:
    contract = load_json(CONTRACT_PATH)
    schema_path = ROOT / contract["output_schema"]
    prompt_a_path = ROOT / contract["prompts"]["pass_a"]
    prompt_b_path = ROOT / contract["prompts"]["pass_b"]
    schema = load_json(schema_path)
    return (
        contract,
        schema,
        prompt_a_path.read_text(encoding="utf-8"),
        prompt_b_path.read_text(encoding="utf-8"),
    )


def load_fixed_inputs() -> list[dict[str, Any]]:
    membership = load_json(MEMBERSHIP_PATH)
    actual_membership_sha = membership["selected_membership"]["membership_payload_sha256"]
    if actual_membership_sha != EXPECTED_MEMBERSHIP_SHA256:
        raise SystemExit(
            "fixed EStG-150 membership hash drifted: "
            f"expected={EXPECTED_MEMBERSHIP_SHA256}, actual={actual_membership_sha}"
        )
    a_rows = load_jsonl(LAYER_A_PATH)
    b_rows = load_jsonl(LAYER_B_PATH)
    c_rows = load_jsonl(LAYER_C_PATH)
    b_index = {row["sample_id"]: row for row in b_rows}
    b_by_legacy_id = {str(row["legacy_record_id"]): row for row in b_rows}
    c_index = {row["sample_id"]: row for row in c_rows}
    a_legacy_ids = [str(row["id"]) for row in a_rows]
    if len(a_rows) != 150 or len(set(a_legacy_ids)) != 150:
        raise SystemExit("Layer A must contain exactly 150 unique legacy record ids")
    if set(a_legacy_ids) != set(b_by_legacy_id) or set(b_index) != set(c_index):
        raise SystemExit("Layer A/B/C membership mismatch; refusing to review")
    output: list[dict[str, Any]] = []
    for source in a_rows:
        candidate = b_by_legacy_id[str(source["id"])]
        sample_id = candidate["sample_id"]
        output.append(
            {
                "sample_id": sample_id,
                "legacy_record_id": source.get("legacy_record_id") or source.get("id") or sample_id,
                "raw_text_de": source["raw_text_de"] if "raw_text_de" in source else source["text"],
                "candidate_text_en": candidate["candidate_text_en"],
                "legacy_six_element_draft": compact_legacy_candidate(c_index[sample_id]),
            }
        )
    return output


def compact_legacy_candidate(row: dict[str, Any]) -> dict[str, Any]:
    clauses: list[dict[str, Any]] = []
    for clause in row.get("clauses") or []:
        compact: dict[str, Any] = {"clause_id": clause.get("clause_id")}
        for field in ("modality", "actor", "action", "condition", "constraint", "exception"):
            value = clause.get(field)
            compact[field] = value.get("value") if isinstance(value, dict) else value
        clauses.append(compact)
    return {"clauses": clauses}


def build_user_payload(sample: dict[str, Any], pass_name: str, pass_a: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {
        "sample_id": sample["sample_id"],
        "raw_text_de": sample["raw_text_de"],
        "frozen_candidate_text_en": sample["candidate_text_en"],
    }
    if pass_name == "pass_b":
        if pass_a is None:
            raise ValueError("pass_b requires pass_a")
        payload["pass_a_candidate"] = pass_a
        payload["legacy_six_element_draft"] = sample["legacy_six_element_draft"]
    elif pass_name != "pass_a":
        raise ValueError(f"unknown pass: {pass_name}")
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def build_request_body(
    *, model: str, reasoning_effort: str, max_completion_tokens: int,
    system_prompt: str, user_payload: str, schema: dict[str, Any],
) -> dict[str, Any]:
    provider_schema = json.loads(json.dumps(schema))
    # These document metadata keywords are unnecessary in the request and are
    # not part of every provider's supported Structured Outputs subset.
    provider_schema.pop("$schema", None)
    provider_schema.pop("$id", None)
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ],
        "reasoning_effort": reasoning_effort,
        "max_completion_tokens": max_completion_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "estg150_ai_review_candidate",
                "strict": True,
                "schema": provider_schema,
            },
        },
    }


def validate_candidate(
    value: dict[str, Any], *, expected_sample_id: str, frozen_candidate_text_en: str,
    schema: dict[str, Any],
) -> None:
    validate_schema_subset(value, schema, root_schema=schema, path="$model_output")
    if value["sample_id"] != expected_sample_id:
        raise CandidateValidationError(
            f"sample_id mismatch: expected={expected_sample_id!r}, actual={value['sample_id']!r}"
        )
    text = value["translation"]["proposed_text_en"]
    decision = value["translation"]["decision"]
    if decision == "accepted" and text != frozen_candidate_text_en:
        raise CandidateValidationError("translation decision=accepted but proposed text changed")
    if decision == "edited" and text == frozen_candidate_text_en:
        raise CandidateValidationError("translation decision=edited but proposed text is unchanged")
    if value["context_sufficiency"] == "insufficient" and not any(
        item["field"] == "context" for item in value["unsupported_or_ambiguous"]
    ):
        raise CandidateValidationError("insufficient context requires a context ambiguity record")

    clause_ids: set[str] = set()
    for clause_index, clause in enumerate(value["clauses"]):
        clause_path = f"clauses[{clause_index}]"
        clause_id = clause["clause_id"]
        if clause_id in clause_ids:
            raise CandidateValidationError(f"{clause_path}.clause_id is duplicated")
        clause_ids.add(clause_id)
        c_start, c_end = validate_span(clause["clause_span"], text, f"{clause_path}.clause_span")
        for evidence_index, span in enumerate(clause["modality"]["evidence"]):
            start, end = validate_span(span, text, f"{clause_path}.modality.evidence[{evidence_index}]")
            require_inside_clause(start, end, c_start, c_end, f"{clause_path}.modality.evidence[{evidence_index}]")
        ids_by_field: dict[str, set[str]] = {}
        all_ids: set[str] = set()
        for field in ("actors", "actions", "conditions", "constraints", "exceptions"):
            ids_by_field[field] = set()
            for item_index, span in enumerate(clause[field]):
                path = f"{clause_path}.{field}[{item_index}]"
                start, end = validate_span(span, text, path)
                require_inside_clause(start, end, c_start, c_end, path)
                span_id = span["id"]
                if span_id in all_ids:
                    raise CandidateValidationError(f"{path}.id is duplicated within the clause")
                all_ids.add(span_id)
                ids_by_field[field].add(span_id)
        for edge_index, edge in enumerate(clause["actor_action_map"]):
            path = f"{clause_path}.actor_action_map[{edge_index}]"
            if edge["actor_id"] is not None and edge["actor_id"] not in ids_by_field["actors"]:
                raise CandidateValidationError(f"{path}.actor_id references an unknown actor")
            if edge["action_id"] not in ids_by_field["actions"]:
                raise CandidateValidationError(f"{path}.action_id references an unknown action")
        for relation_index, relation in enumerate(clause["order_relations"]):
            path = f"{clause_path}.order_relations[{relation_index}]"
            if relation["before_action_id"] not in ids_by_field["actions"]:
                raise CandidateValidationError(f"{path}.before_action_id references an unknown action")
            if relation["after_action_id"] not in ids_by_field["actions"]:
                raise CandidateValidationError(f"{path}.after_action_id references an unknown action")
            for evidence_index, span in enumerate(relation["evidence"]):
                start, end = validate_span(span, text, f"{path}.evidence[{evidence_index}]")
                require_inside_clause(start, end, c_start, c_end, f"{path}.evidence[{evidence_index}]")


def validate_schema_subset(
    value: Any, schema: dict[str, Any], *, root_schema: dict[str, Any], path: str,
) -> None:
    """Validate the dependency-free JSON Schema subset used by this contract."""
    if "$ref" in schema:
        reference = schema["$ref"]
        prefix = "#/$defs/"
        if not reference.startswith(prefix):
            raise RuntimeError(f"unsupported local schema reference: {reference}")
        definition = root_schema["$defs"][reference[len(prefix):]]
        validate_schema_subset(value, definition, root_schema=root_schema, path=path)
        return
    if "const" in schema and value != schema["const"]:
        raise CandidateValidationError(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise CandidateValidationError(f"{path} must be one of {schema['enum']!r}")
    expected_type = schema.get("type")
    if expected_type is not None:
        allowed_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(json_type_matches(value, item) for item in allowed_types):
            raise CandidateValidationError(f"{path} must have JSON type {expected_type!r}")
    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            raise CandidateValidationError(f"{path} is missing required properties {missing!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            if extras:
                raise CandidateValidationError(f"{path} has additional properties {extras!r}")
        for key, child in value.items():
            if key in properties:
                validate_schema_subset(
                    child,
                    properties[key],
                    root_schema=root_schema,
                    path=f"{path}.{key}",
                )
    if isinstance(value, list):
        if len(value) < int(schema.get("minItems", 0)):
            raise CandidateValidationError(f"{path} has fewer than {schema['minItems']} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, child in enumerate(value):
                validate_schema_subset(
                    child,
                    item_schema,
                    root_schema=root_schema,
                    path=f"{path}[{index}]",
                )
    if isinstance(value, str) and len(value) < int(schema.get("minLength", 0)):
        raise CandidateValidationError(f"{path} is shorter than minLength={schema['minLength']}")
    if isinstance(value, int) and not isinstance(value, bool) and "minimum" in schema:
        if value < schema["minimum"]:
            raise CandidateValidationError(f"{path} is below minimum={schema['minimum']}")


def json_type_matches(value: Any, expected_type: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected_type, False)


def validate_span(span: dict[str, Any], source: str, path: str) -> tuple[int, int]:
    start, end = span["start"], span["end"]
    if not (0 <= start < end <= len(source)):
        raise CandidateValidationError(f"{path} is outside proposed_text_en")
    if source[start:end] != span["text"]:
        raise CandidateValidationError(f"{path}.text does not match proposed_text_en[start:end]")
    return start, end


def require_inside_clause(start: int, end: int, clause_start: int, clause_end: int, path: str) -> None:
    if start < clause_start or end > clause_end:
        raise CandidateValidationError(f"{path} is outside its clause_span")


def acquire_api_key(env_name: str | None) -> str:
    if env_name:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env_name):
            raise SystemExit("--api-key-env-name is not a valid environment-variable name")
        key = os.environ.get(env_name, "")
        if not key:
            raise SystemExit(f"environment variable {env_name!r} is empty or missing")
    else:
        key = getpass.getpass("ChatAnywhere API key (hidden; never stored): ")
    if not key.strip():
        raise SystemExit("API key is empty")
    return key


def call_chat_completions(
    *, endpoint: str, api_key: str, body: dict[str, Any], timeout_seconds: int,
) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        safe = raw.replace(api_key, "***")
        raise RuntimeError(f"HTTP {exc.code} from relay: {safe[:800]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"relay URL error: {exc.reason!r}") from exc
    if not isinstance(result, dict):
        raise RuntimeError("relay response is not a JSON object")
    return result


def parse_response(
    response: dict[str, Any], *, required_returned_models: list[str], expected_sample_id: str,
    frozen_candidate_text_en: str, schema: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    returned_model = response.get("model")
    if returned_model not in required_returned_models:
        raise RuntimeError(
            f"relay returned model {returned_model!r}; required one of {required_returned_models!r}"
        )
    try:
        choice = response["choices"][0]
        finish_reason = choice["finish_reason"]
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("relay response lacks choices[0].message.content") from exc
    if finish_reason != "stop":
        raise RuntimeError(f"finish_reason={finish_reason!r}; refusing partial or filtered output")
    if not isinstance(content, str):
        raise RuntimeError("assistant content is not a JSON string")
    try:
        candidate = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("strict structured-output response was not valid JSON") from exc
    if not isinstance(candidate, dict):
        raise RuntimeError("strict structured-output content is not an object")
    validate_candidate(
        candidate,
        expected_sample_id=expected_sample_id,
        frozen_candidate_text_en=frozen_candidate_text_en,
        schema=schema,
    )
    usage = response.get("usage")
    if not isinstance(usage, dict):
        raise RuntimeError("relay response omitted token usage; cost gate cannot continue")
    try:
        prompt_tokens = int(usage["prompt_tokens"])
        completion_tokens = int(usage["completion_tokens"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("relay token usage is incomplete") from exc
    metadata = {
        "returned_model": returned_model,
        "finish_reason": finish_reason,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "provider_response_id": response.get("id"),
        "provider_created": response.get("created"),
    }
    return candidate, metadata


def token_cost(prompt_tokens: int, completion_tokens: int, input_rate: Decimal, output_rate: Decimal) -> Decimal:
    return (Decimal(prompt_tokens) * input_rate + Decimal(completion_tokens) * output_rate) / Decimal(1000)


def conservative_request_reservation(
    body: dict[str, Any], *, max_completion_tokens: int, input_rate: Decimal, output_rate: Decimal,
) -> Decimal:
    # UTF-8 bytes are a conservative token proxy for these German/English/JSON payloads.
    prompt_token_reserve = len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
    return token_cost(prompt_token_reserve, max_completion_tokens, input_rate, output_rate)


def safe_run_dir(run_id: str) -> Path:
    if not RUN_ID_RE.fullmatch(run_id):
        raise SystemExit("--run-id must match [A-Za-z0-9][A-Za-z0-9._-]{0,79}")
    root = OUTPUT_ROOT.resolve()
    target = (OUTPUT_ROOT / run_id).resolve()
    if target.parent != root:
        raise SystemExit("unsafe run directory")
    return target


def build_run_config(
    *, contract: dict[str, Any], endpoint: str, run_id: str, price_unit: str,
    input_rate: Decimal, output_rate: Decimal,
) -> dict[str, Any]:
    return {
        "schema_version": "estg150_ai_review_execution@1.0.0",
        "run_id": run_id,
        "created_at_utc": now_utc(),
        "output_class": "development_ai_adjudication_candidate_not_human_gold",
        "endpoint": endpoint,
        "endpoint_sha256": hashlib.sha256(endpoint.encode("utf-8")).hexdigest(),
        "model": contract["model"],
        "price_unit_confirmed_by_user": price_unit,
        "input_price_per_1000_tokens_confirmed_by_user": str(input_rate),
        "output_price_per_1000_tokens_confirmed_by_user": str(output_rate),
        "membership_payload_sha256": EXPECTED_MEMBERSHIP_SHA256,
        "layer_a_sha256": sha256_path(LAYER_A_PATH),
        "layer_b_sha256": sha256_path(LAYER_B_PATH),
        "layer_c_sha256": sha256_path(LAYER_C_PATH),
        "contract_sha256": sha256_path(CONTRACT_PATH),
        "schema_sha256": sha256_path(ROOT / contract["output_schema"]),
        "pass_a_prompt_sha256": sha256_path(ROOT / contract["prompts"]["pass_a"]),
        "pass_b_prompt_sha256": sha256_path(ROOT / contract["prompts"]["pass_b"]),
        "deepseek_layer_d_used": False,
        "layer_e_read": False,
        "layer_e_write": False,
    }


def write_or_verify_run_config(run_dir: Path, proposed: dict[str, Any]) -> dict[str, Any]:
    path = run_dir / "run_config.json"
    if not path.exists():
        path.write_text(json.dumps(proposed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return proposed
    existing = load_json(path)
    comparable_existing = {key: value for key, value in existing.items() if key != "created_at_utc"}
    comparable_proposed = {key: value for key, value in proposed.items() if key != "created_at_utc"}
    if comparable_existing != comparable_proposed:
        raise SystemExit("run_config.json drifted; use a new --run-id")
    return existing


def latest_by_sample(path: Path, *, status: str | None = None) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    output: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(path):
        if status is None or row.get("status") == status:
            output[row["sample_id"]] = row
    return output


def select_subset(samples: list[dict[str, Any]], start: int, end: int, pilot: int) -> list[dict[str, Any]]:
    if not (0 <= start < end <= len(samples)):
        raise SystemExit(f"range must satisfy 0 <= start < end <= {len(samples)}")
    subset = samples[start:end]
    if pilot:
        if not (1 <= pilot <= 5):
            raise SystemExit("--pilot must be between 1 and 5")
        subset = subset[:pilot]
    return subset


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--confirm-third-party-relay-risk", action="store_true")
    parser.add_argument("--confirm-non-human-output", action="store_true")
    parser.add_argument("--authorize-full-batch", action="store_true")
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--end-index", type=int, default=3)
    parser.add_argument("--pilot", type=int, default=0)
    parser.add_argument("--run-id")
    parser.add_argument("--max-calls", type=int, default=0)
    parser.add_argument("--approved-max-cost", type=Decimal)
    parser.add_argument("--price-unit")
    parser.add_argument("--input-price-per-1000", type=Decimal)
    parser.add_argument("--output-price-per-1000", type=Decimal)
    parser.add_argument("--api-key-env-name")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()

    contract, schema, prompt_a, prompt_b = load_contract()
    endpoint = normalize_chat_completions_endpoint(
        args.endpoint or contract["provider"]["endpoint"]
    )
    samples = load_fixed_inputs()
    subset = select_subset(samples, args.start_index, args.end_index, args.pilot)
    calls_for_new_samples = len(subset) * contract["model"]["calls_per_new_sample"]
    max_completion_tokens = int(contract["model"]["max_completion_tokens_per_call"])
    displayed_input_rate = Decimal(str(contract["pricing_snapshot_from_user_screenshot"]["input_per_1000_tokens"]))
    displayed_output_rate = Decimal(str(contract["pricing_snapshot_from_user_screenshot"]["output_per_1000_tokens"]))
    output_only_reservation = token_cost(0, max_completion_tokens * calls_for_new_samples, displayed_input_rate, displayed_output_rate)

    if not args.allow_llm:
        print("[dry-run] no LLM/API call will be made; no API key requested.")
        print(f"  fixed membership: {len(samples)} records ({EXPECTED_MEMBERSHIP_SHA256[:16]}...)")
        print(f"  planned subset : [{args.start_index}, {args.end_index}) -> {len(subset)} records")
        print(f"  planned calls  : {calls_for_new_samples} (two passes per new record)")
        print(f"  model          : {contract['model']['request_model_id']}")
        print(f"  endpoint       : {endpoint}")
        print(f"  reasoning      : {contract['model']['reasoning_effort']}")
        print("  structured JSON: strict; no parameter downgrade allowed")
        print("  DeepSeek Layer D input: forbidden")
        print("  Layer E access : none")
        print(
            "  output-token reservation only: "
            f"{output_only_reservation:.4f} unverified provider display units; "
            "prompt cost is added at real-run preflight"
        )
        print("Real calls require explicit risk/budget flags and hidden key input.")
        return 0

    if not args.confirm_third_party_relay_risk:
        raise SystemExit("real run requires --confirm-third-party-relay-risk")
    if not args.confirm_non_human_output:
        raise SystemExit("real run requires --confirm-non-human-output")
    if args.pilot == 0:
        if not args.authorize_full_batch:
            raise SystemExit("non-pilot run requires --authorize-full-batch")
        if (args.start_index, args.end_index) != (0, 150):
            raise SystemExit("full-batch authorization requires the exact range [0, 150)")
    elif args.authorize_full_batch:
        raise SystemExit("do not combine --pilot with --authorize-full-batch")
    if not args.run_id:
        raise SystemExit("real run requires --run-id")
    if args.max_calls <= 0:
        raise SystemExit("real run requires --max-calls > 0")
    if calls_for_new_samples > args.max_calls:
        raise SystemExit(f"planned calls={calls_for_new_samples} exceeds --max-calls={args.max_calls}")
    if args.approved_max_cost is None or args.approved_max_cost <= 0:
        raise SystemExit("real run requires --approved-max-cost > 0")
    if not args.price_unit or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,15}", args.price_unit):
        raise SystemExit("real run requires a short --price-unit confirmed from the relay account")
    if args.input_price_per_1000 is None or args.input_price_per_1000 <= 0:
        raise SystemExit("real run requires --input-price-per-1000 confirmed from the relay account")
    if args.output_price_per_1000 is None or args.output_price_per_1000 <= 0:
        raise SystemExit("real run requires --output-price-per-1000 confirmed from the relay account")
    input_rate = args.input_price_per_1000
    output_rate = args.output_price_per_1000

    raise SystemExit(
        "legacy relay execution is retired; use scripts/run_estg150_candidate_protocol.py "
        "so every provider shares canonical external serializer v1"
    )

    run_dir = safe_run_dir(args.run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    run_config = build_run_config(
        contract=contract,
        endpoint=endpoint,
        run_id=args.run_id,
        price_unit=args.price_unit,
        input_rate=input_rate,
        output_rate=output_rate,
    )
    write_or_verify_run_config(run_dir, run_config)
    append_jsonl(
        run_dir / "authorizations.jsonl",
        {
            "timestamp_utc": now_utc(),
            "run_id": args.run_id,
            "scope": "full_batch" if args.authorize_full_batch else "pilot",
            "start_index": args.start_index,
            "end_index": args.end_index,
            "pilot": args.pilot,
            "max_calls": args.max_calls,
            "approved_max_cost": str(args.approved_max_cost),
            "price_unit": args.price_unit,
            "input_price_per_1000": str(input_rate),
            "output_price_per_1000": str(output_rate),
            "third_party_relay_risk_confirmed": True,
            "non_human_output_confirmed": True,
        },
    )
    pass_a_path = run_dir / "pass_a_candidates.jsonl"
    final_path = run_dir / "ai_review_candidates.jsonl"
    manifest_path = run_dir / "manifest.jsonl"
    pass_a_done = latest_by_sample(pass_a_path)
    final_done = latest_by_sample(final_path)
    prior_manifest = load_jsonl(manifest_path) if manifest_path.exists() else []
    spent = sum((Decimal(str(row.get("cost", "0"))) for row in prior_manifest), Decimal("0"))
    api_key = acquire_api_key(args.api_key_env_name)
    calls_made = 0

    def perform_pass(sample: dict[str, Any], pass_name: str, pass_a_value: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any], Decimal]:
        nonlocal calls_made, spent
        system_prompt = prompt_a if pass_name == "pass_a" else prompt_b
        body = build_request_body(
            model=contract["model"]["request_model_id"],
            reasoning_effort=contract["model"]["reasoning_effort"],
            max_completion_tokens=max_completion_tokens,
            system_prompt=system_prompt,
            user_payload=build_user_payload(sample, pass_name, pass_a_value),
            schema=schema,
        )
        reservation = conservative_request_reservation(
            body,
            max_completion_tokens=max_completion_tokens,
            input_rate=input_rate,
            output_rate=output_rate,
        )
        if spent + reservation > args.approved_max_cost:
            raise SystemExit(
                f"budget gate: spent={spent:.4f}, next-call reservation={reservation:.4f}, "
                f"approved={args.approved_max_cost} {args.price_unit}"
            )
        if calls_made >= args.max_calls:
            raise SystemExit(f"call cap reached: {args.max_calls}")
        calls_made += 1
        response: dict[str, Any] | None = None
        try:
            response = call_chat_completions(
                endpoint=endpoint,
                api_key=api_key,
                body=body,
                timeout_seconds=args.timeout_seconds,
            )
            candidate, metadata = parse_response(
                response,
                required_returned_models=contract["model"]["required_returned_model_ids"],
                expected_sample_id=sample["sample_id"],
                frozen_candidate_text_en=sample["candidate_text_en"],
                schema=schema,
            )
        except Exception as exc:
            failure_cost = reservation
            cost_basis = "conservative_request_reservation"
            usage = response.get("usage") if isinstance(response, dict) else None
            if isinstance(usage, dict):
                try:
                    failure_cost = token_cost(
                        int(usage["prompt_tokens"]),
                        int(usage["completion_tokens"]),
                        input_rate,
                        output_rate,
                    )
                    cost_basis = "provider_reported_usage"
                except (KeyError, TypeError, ValueError):
                    pass
            spent += failure_cost
            append_jsonl(
                manifest_path,
                {
                    "timestamp_utc": now_utc(),
                    "run_id": args.run_id,
                    "sample_id": sample["sample_id"],
                    "pass": pass_name,
                    "status": "failed",
                    "cost": str(failure_cost),
                    "cost_basis": cost_basis,
                    "price_unit": args.price_unit,
                    "error_type": type(exc).__name__,
                    "error": str(exc).replace(api_key, "***")[:1200],
                },
            )
            raise
        cost = token_cost(
            metadata["prompt_tokens"],
            metadata["completion_tokens"],
            input_rate,
            output_rate,
        )
        spent += cost
        append_jsonl(
            manifest_path,
            {
                "timestamp_utc": now_utc(),
                "run_id": args.run_id,
                "sample_id": sample["sample_id"],
                "pass": pass_name,
                "status": "ok",
                "cost": str(cost),
                "price_unit": args.price_unit,
                **metadata,
            },
        )
        return candidate, metadata, cost

    for position, sample in enumerate(subset, 1):
        sample_id = sample["sample_id"]
        if sample_id in final_done:
            print(f"[resume] {sample_id}: final candidate already exists")
            continue
        try:
            if sample_id in pass_a_done:
                pass_a_candidate = pass_a_done[sample_id]["candidate"]
                validate_candidate(
                    pass_a_candidate,
                    expected_sample_id=sample_id,
                    frozen_candidate_text_en=sample["candidate_text_en"],
                    schema=schema,
                )
                print(f"[resume] {sample_id}: reusing validated pass A")
            else:
                pass_a_candidate, pass_a_metadata, _ = perform_pass(sample, "pass_a", None)
                append_jsonl(
                    pass_a_path,
                    {
                        "schema_version": "estg150_ai_review_saved_pass@1.0.0",
                        "run_id": args.run_id,
                        "sample_id": sample_id,
                        "candidate": pass_a_candidate,
                        "response_metadata": pass_a_metadata,
                    },
                )
            final_candidate, final_metadata, _ = perform_pass(sample, "pass_b", pass_a_candidate)
            append_jsonl(
                final_path,
                {
                    "schema_version": "estg150_ai_review_saved_final@1.0.0",
                    "run_id": args.run_id,
                    "sample_id": sample_id,
                    "legacy_record_id": sample["legacy_record_id"],
                    "candidate": final_candidate,
                    "response_metadata": final_metadata,
                    "provenance": {
                        "output_class": "development_ai_adjudication_candidate_not_human_gold",
                        "model": contract["model"]["request_model_id"],
                        "provider": contract["provider"]["id"],
                        "deepseek_layer_d_used": False,
                        "layer_e_read": False,
                        "layer_e_write": False,
                    },
                },
            )
            print(f"[{position}/{len(subset)}] {sample_id}: two-pass candidate saved")
        except Exception as exc:
            safe_error = str(exc).replace(api_key, "***")
            append_jsonl(
                manifest_path,
                {
                    "timestamp_utc": now_utc(),
                    "run_id": args.run_id,
                    "sample_id": sample_id,
                    "pass": "unknown_or_current",
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": safe_error[:1200],
                },
            )
            raise SystemExit(f"provider/output failure at {sample_id}; stopped safely: {safe_error}") from exc

    summary = {
        "schema_version": "estg150_ai_review_summary@1.0.0",
        "run_id": args.run_id,
        "updated_at_utc": now_utc(),
        "candidate_count": len(latest_by_sample(final_path)),
        "calls_made_this_process": calls_made,
        "recorded_cost": str(spent),
        "price_unit": args.price_unit,
        "output_class": "development_ai_adjudication_candidate_not_human_gold",
        "full_batch_automatically_promoted": False,
    }
    (run_dir / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"complete: candidates={summary['candidate_count']}, calls_this_process={calls_made}, "
        f"recorded_cost={spent:.4f} {args.price_unit}"
    )
    print("No Layer E or human review state was read or written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
