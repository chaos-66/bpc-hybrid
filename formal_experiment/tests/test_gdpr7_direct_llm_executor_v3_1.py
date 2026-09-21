# -*- coding: utf-8 -*-
"""Focused offline tests for the v3.1 wire-body provenance instrumentation.

No network, no API, no .env.  The tests prove:
* the 74 frozen v3 request-body SHA-256 values are unchanged in v3.1;
* actual serialized bodies reconstructed through the real transport equal
  those frozen bodies and contain stream=false and thinking disabled;
* the planned/actual hashes are both persisted with a match flag;
* a mismatch is fail-closed: it is recorded as an execution-contract
  violation, the batch stops immediately, and the request is not retried.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import bpc_hybrid.llm_client as llm_client  # noqa: E402
import run_gdpr7_direct_llm_v3_1 as ex  # noqa: E402

REPORT_FILE = ROOT / "outputs/reports/gdpr7_direct_llm_preflight_v3.json"
CONTRACT_FILE = (
    ROOT / "configs/ablations/gdpr7_direct_llm_execution_contract_v3_1.json"
)
V3_FREEZE_FILE = ROOT / "outputs/reports/gdpr7_direct_llm_v3_payload_freeze.json"
V31_FREEZE_FILE = (
    ROOT / "outputs/reports/gdpr7_direct_llm_v3_1_payload_freeze.json"
)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_text(value: str) -> str:
    return _sha_bytes(value.encode("utf-8"))


@pytest.fixture(scope="module")
def plan_rows():
    report = ex.load_report(REPORT_FILE)
    input_doc = ex.load_input_doc()
    sentence_texts = ex.resolve_sentence_texts(input_doc)
    return ex.build_plan_rows(report, sentence_texts)


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")
        self.status = 200
        self.headers = {"Content-Type": "application/json"}

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_v31_freeze_preserves_all_74_v3_request_hashes(plan_rows) -> None:
    v3 = _load_json(V3_FREEZE_FILE)
    v31 = _load_json(V31_FREEZE_FILE)
    assert v31["schema_version"] == "gdpr7_direct_llm_payload_freeze@1.1.0"
    assert v31["call_count"] == 74
    assert v31["wire_body_provenance"]["planned_request_body_sha256_persisted"] is True
    assert v31["wire_body_provenance"]["actual_request_body_sha256_persisted"] is True
    assert v31["wire_body_provenance"]["equality_enforced_before_response_acceptance"] is True
    assert v31["wire_body_provenance"]["mismatch_aborts_batch"] is True
    assert v31["wire_body_provenance"]["mismatch_retry"] is False

    v3_hashes = [r["request_body_sha256"] for r in v3["request_body_hashes"]]
    v31_hashes = [r["request_body_sha256"] for r in v31["request_body_hashes"]]
    plan_hashes = [r["request_body_sha256"] for r in plan_rows]
    assert v31_hashes == v3_hashes == plan_hashes
    assert v31["first_request_body_sha256"] == v3_hashes[0]
    assert v31["last_request_body_sha256"] == v3_hashes[-1]

    for frozen, row in zip(v31["request_body_hashes"], plan_rows):
        body = row["body"]
        assert frozen["request_body_sha256"] == _sha_bytes(
            json.dumps(body).encode("utf-8")
        )
        assert frozen["actual_send_body_sha256_after_correction"] == frozen[
            "request_body_sha256"
        ]
        assert frozen["request_body_sha256_match"] is True
        assert frozen["stream"] is False
        assert frozen["thinking"] == {"type": "disabled"}
        assert frozen["max_tokens"] == 4096
        assert frozen["response_format"] is None
        assert body["stream"] is False
        assert body["thinking"] == {"type": "disabled"}
        assert body["max_tokens"] == 4096
        assert body.get("response_format") is None  # omitted in the actual body


def test_real_serialization_matches_freeze_and_wire_assertion_passes(
    monkeypatch, plan_rows
) -> None:
    captured_bodies: list[bytes] = []
    synthetic_response = {
        "id": "offline",
        "object": "chat.completion",
        "model": ex.REQUIRED_MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "{}"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2,
        },
    }

    def fake_urlopen(http_req, timeout=None):
        captured_bodies.append(http_req.data)
        return _FakeHTTPResponse(synthetic_response)

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)

    config = ex._config()
    builder = ex.OpenAICompatibleRequestBuilder(config)
    policy = ex._policy()
    lock = ex.PayloadLock(plan_rows, builder, policy)
    transport = ex.PayloadLockedRealTransport(lock, config)

    for row in plan_rows:
        request = ex.LLMRequest(
            source_id=row["sample_id"],
            source_text=row["source_text"],
            system_prompt=row["system_prompt"],
            user_prompt=row["user_prompt"],
        )
        response = transport.send(request, ordinal=int(row["call_index"]))
        assert response.content == "{}"
        assert transport.last_wire_verified is True
        assert transport.last_request_body_sha256 == row["request_body_sha256"]
        sent_body = captured_bodies[-1]
        assert _sha_bytes(sent_body) == row["request_body_sha256"]
        sent_json = json.loads(sent_body.decode("utf-8"))
        assert sent_json["stream"] is False
        assert sent_json["thinking"] == {"type": "disabled"}
        assert sent_json["max_tokens"] == 4096

    assert len(captured_bodies) == 74
    assert _sha_bytes(captured_bodies[0]) == plan_rows[0]["request_body_sha256"]
    assert _sha_bytes(captured_bodies[-1]) == plan_rows[-1]["request_body_sha256"]


def test_completed_ledger_persists_planned_and_actual_hashes(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    cap = tmp_path / "cap"
    summary = ex.execute_batch(raw_dir=raw, capsule_dir=cap, fake=True)
    assert summary["status"] == "complete"
    assert summary["per_call_status_counts"] == {
        "completed": 74,
        "in_doubt": 0,
        "failed": 0,
    }
    records = summary["ledger"].records
    assert len(records) == 74
    for rec in records:
        assert rec["schema_version"] == ex.LEDGER_SCHEMA
        assert rec["request_body_sha256"] == rec["planned_request_body_sha256"]
        assert rec["actual_request_body_sha256"] == rec["planned_request_body_sha256"]
        assert rec["request_body_sha256_match"] is True
        assert rec["decode_status"] == "ok_message_content"
    raw_lines = [json.loads(line) for line in
                 (raw / "raw_responses.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()]
    assert len(raw_lines) == 74
    assert all(line["request_body_sha256_match"] is True for line in raw_lines)
    assert all(
        line["actual_request_body_sha256"] == line["planned_request_body_sha256"]
        for line in raw_lines
    )
    assert all(line["decode_status"] == "ok_message_content" for line in raw_lines)


def test_wire_mismatch_persists_both_hashes_and_stops_without_retry(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    cap = tmp_path / "cap"
    with pytest.raises(ex.Gdpr7ExecutionError, match="execution-contract violation"):
        ex.execute_batch(
            raw_dir=raw,
            capsule_dir=cap,
            fake=True,
            fake_wire_hash_mismatch_at=2,
        )
    assert not cap.exists()

    ledger = [json.loads(line) for line in
              (raw / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
              if line.strip()]
    assert [r["status"] for r in ledger] == [
        "completed",
        "execution_contract_violation",
    ]
    violation = ledger[-1]
    assert violation["schema_version"] == ex.LEDGER_SCHEMA
    assert violation["sample_id"] == "gdpr_article15_s002"
    assert violation["planned_request_body_sha256"] == (
        "a2239fdf94baa97addecb54f658773bca006c49834fb1a7a707e9d579281d335"
    )
    assert violation["actual_request_body_sha256"] == "0" * 64
    assert violation["request_body_sha256_match"] is False
    assert violation["decode_status"] == "ok_message_content"
    # Legacy key still holds the planned/frozen hash, not the actual hash.
    assert violation["request_body_sha256"] == violation["planned_request_body_sha256"]

    raw_lines = [json.loads(line) for line in
                 (raw / "raw_responses.jsonl").read_text(encoding="utf-8").splitlines()
                 if line.strip()]
    assert len(raw_lines) == 2
    assert raw_lines[-1]["outcome"] == "execution_contract_violation"
    assert raw_lines[-1]["planned_request_body_sha256"] == violation[
        "planned_request_body_sha256"
    ]
    assert raw_lines[-1]["actual_request_body_sha256"] == "0" * 64
    assert raw_lines[-1]["request_body_sha256_match"] is False

    # Resume must refuse; the mismatched request is never retried.
    with pytest.raises(ex.Gdpr7ExecutionError, match="already recorded"):
        ex.execute_batch(raw_dir=raw, capsule_dir=cap, fake=True, resume=True)
    ledger_after = (raw / "ledger.jsonl").read_text(encoding="utf-8")
    assert ledger_after.count("execution_contract_violation") == 1


def test_real_wrapper_rejects_mismatch_before_response_acceptance(
    monkeypatch, plan_rows
) -> None:
    config = ex._config()
    builder = ex.OpenAICompatibleRequestBuilder(config)
    policy = ex._policy()
    lock = ex.PayloadLock(plan_rows, builder, policy)
    transport = ex.PayloadLockedRealTransport(lock, config)
    row = plan_rows[0]
    request = ex.LLMRequest(
        source_id=row["sample_id"],
        source_text=row["source_text"],
        system_prompt=row["system_prompt"],
        user_prompt=row["user_prompt"],
    )

    def fake_real_send(request):
        transport._real.last_request_body_sha256 = "f" * 64
        transport._real.last_decode = {
            "status": "ok_message_content",
            "model": ex.REQUIRED_MODEL,
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
            "finish_reason": "stop",
        }
        return ex.LLMResponse(
            content="{}", provider="fake", model=ex.REQUIRED_MODEL
        )

    monkeypatch.setattr(transport._real, "send", fake_real_send)
    with pytest.raises(ex.WireBodyHashMismatch) as excinfo:
        transport.send(request, ordinal=1)
    exc = excinfo.value
    assert exc.planned_request_body_sha256 == row["request_body_sha256"]
    assert exc.actual_request_body_sha256 == "f" * 64
    assert exc.actual_body_hash_available is True
    assert exc.decode["status"] == "ok_message_content"
    assert exc.response is not None
    assert transport.last_wire_verified is False


def test_contract_binds_v31_freeze_and_real_run_refuses_without_authorization(
    tmp_path: Path,
) -> None:
    contract = ex.validate_contract(CONTRACT_FILE, REPORT_FILE)
    assert contract["suite_id"] == "gdpr7_direct_llm_execution_v3_1"
    assert contract["authorization_scope"] == ex.AUTHORIZATION_SCOPE
    assert contract["payload_freeze"]["path"] == (
        "outputs/reports/gdpr7_direct_llm_v3_1_payload_freeze.json"
    )
    assert contract["payload_freeze"]["call_count"] == 74
    assert contract["wire_body_hash_assertion"]["equality_required"] is True

    raw = tmp_path / "raw"
    cap = tmp_path / "cap"
    missing_event = tmp_path / "no-authorization-event-v3_1.json"
    rc = ex.main([
        "--contract-file", str(CONTRACT_FILE),
        "--report-file", str(REPORT_FILE),
        "--authorization-file", str(missing_event),
        "--raw-dir", str(raw),
        "--capsule-dir", str(cap),
    ])
    assert rc != 0
    assert not raw.exists()
    assert not cap.exists()
