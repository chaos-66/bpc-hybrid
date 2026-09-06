# -*- coding: utf-8 -*-
"""Offline verification tests for the GDPR Direct-LLM (Stage-2 arm) executor.

Fully offline, zero network, zero API, zero ``.env`` reads.  All eight
scenarios requested for ``scripts/run_gdpr7_direct_llm_v1.py``:

(a) a full 74-call fake run succeeds deterministically and yields 74
    canonical rows (or explicit failures) plus a complete manifest with
    cost_usd == 0.0;
(b) without an authorization event the (real-run) executor refuses BEFORE
    the first send: non-zero exit and no files published;
(c) exceeding the USD budget rejects the NEXT send before transport
    (costs are scaled through fake usage);
(d) a mid-run failure produces an ``in_doubt`` ledger entry; a resume sends
    ONLY the remainder and never re-sends completed entries nor auto-resends
    the in_doubt entry;
(e) payload fingerprint drift (one mutated request body) fails closed before
    any send;
(f) a returned_model mismatch aborts;
(g) gold-blindness: outputs contain no decision / expected / Gold labels and
    no raw sentence text (only coordinates are committed);
(h) downstream compatibility: the fake-run predictions capsule loads with the
    linkage runner's schema check
    (``run_gdpr_s2_s3_linkage_v1.ARM_PREDICTION_SCHEMAS['direct_llm']``) and a
    dry arm-load of the capsule rows (first-valid-span projection) succeeds
    structurally.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_gdpr7_direct_llm_v1 as ex  # noqa: E402
import build_gdpr7_direct_llm_preflight_v1 as pre  # noqa: E402

CONTRACT_FILE = (
    ROOT / "configs/ablations/gdpr7_direct_llm_execution_contract_v1.json"
)
REPORT_FILE = ROOT / "outputs/reports/gdpr7_direct_llm_preflight_v1.json"

_ZERO_USAGE = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "reasoning_tokens": 0,
}


def _fake_ok(raw_dir: Path, capsule_dir: Path, **kwargs):
    """Run a full 74-call fake batch with defaults; returns the summary."""
    return ex.execute_batch(raw_dir=raw_dir, capsule_dir=capsule_dir,
                            fake=True, **kwargs)


def _ledger_lines(raw_dir: Path) -> list[dict]:
    path = raw_dir / "ledger.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _raw_lines(raw_dir: Path) -> list[dict]:
    path = raw_dir / "raw_responses.jsonl"
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# (a) full 74-call fake run: deterministic, complete, cost = 0
# ---------------------------------------------------------------------------


def test_fake_full_run_74_ok_complete_manifest(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    cap = tmp_path / "cap"
    summary = _fake_ok(raw, cap)

    assert summary["status"] == "complete"
    assert summary["per_call_status_counts"] == {
        "completed": 74, "in_doubt": 0, "failed": 0,
    }
    # Fake run never bills: cost is exactly zero.
    assert summary["state"]["cost_usd"] == 0.0
    assert summary["state"]["calls"] == 74

    pred = _load_json(cap / "predictions.json")
    assert pred["schema_version"] == ex.PREDICTION_SCHEMA
    assert pred["record_count"] == 74
    assert pred["gold_read_by_runner"] is False
    assert pred["raw_text_committed"] is False
    assert len(pred["records"]) == 74
    for row in pred["records"]:
        assert row["request_status"] == "ok"
        assert row["error_category"] is None
        rec = row["record"]
        assert rec is not None
        assert rec["sample_id"] == row["sample_id"]
        assert isinstance(rec["clauses"], list) and len(rec["clauses"]) >= 1
        for clause in rec["clauses"]:
            assert set(clause["clause_span"]) == {"start", "end"}
            assert "text" not in json.dumps(clause["clause_span"])
    # Sample-id self-keyed ordering equals the locked plan order.
    plan_order = [r["sample_id"] for r in
                  _load_json(REPORT_FILE)["arms"]["direct_llm"]["calls"]]
    assert [r["sample_id"] for r in pred["records"]] == plan_order

    telemetry = _load_json(cap / "telemetry.json")
    assert telemetry["completed_calls"] == 74
    assert telemetry["in_doubt_calls"] == 0
    assert telemetry["fake_run_program_verification_only"] is True
    cost = _load_json(cap / "cost.json")
    assert cost["actual_cost_usd"] == 0.0
    assert cost["network_calls"] == 0
    assert cost["transport"] == "fake_payload_locked"
    manifest = _load_json(cap / "manifest.json")
    assert manifest["schema_version"] == ex.MANIFEST_SCHEMA
    assert manifest["arm_capsule"]["schema"] == ex.PREDICTION_SCHEMA
    assert manifest["arm_capsule"]["path"] == "data/predictions/gdpr7_direct_llm_v1"
    assert manifest["per_call_status_counts"]["completed"] == 74
    assert manifest["cost_usd"] == 0.0
    # Explicit reproduce/verify commands must be recorded in the manifest.
    assert "--fake-transport" in manifest["reproduce_command_fake_verify"]
    assert "--contract-file" in manifest["reproduce_command_real"]
    assert "--resume" in manifest["resume_command_fake"]

    # Ledger: 74 hash-chained, append-only rows.
    ledger = _ledger_lines(raw)
    assert len(ledger) == 74
    assert len({rec["request_body_sha256"] for rec in ledger}) == 74
    assert all(rec["status"] == "completed" for rec in ledger)
    assert all(rec["cost_usd"] == 0.0 for rec in ledger)
    assert all(rec["schema_version"] == ex.LEDGER_SCHEMA for rec in ledger)
    # Deterministic reproducibility: two fresh runs produce byte-identical
    # predictions docs (only timing in the manifest differs).
    raw2 = tmp_path / "raw2"
    cap2 = tmp_path / "cap2"
    _fake_ok(raw2, cap2)
    pred2 = _load_json(cap2 / "predictions.json")
    assert json.dumps(pred, sort_keys=True) == json.dumps(pred2, sort_keys=True)


# ---------------------------------------------------------------------------
# (b) real-run refusal without an authorization event, before any send
# ---------------------------------------------------------------------------


def test_real_run_refuses_without_authorization_event(tmp_path: Path) -> None:
    assert CONTRACT_FILE.is_file()
    raw = tmp_path / "raw"
    cap = tmp_path / "cap"
    missing_event = tmp_path / "authorization_event_v1.json"  # does not exist

    rc = ex.main([
        "--contract-file", str(CONTRACT_FILE),
        "--authorization-file", str(missing_event),
        "--raw-dir", str(raw),
        "--capsule-dir", str(cap),
    ])
    assert rc != 0
    # Nothing may have been published: no raw dir, no capsule dir.
    assert not raw.exists()
    assert not cap.exists()


def test_real_run_refuses_without_contract_file(tmp_path: Path) -> None:
    rc = ex.main([
        "--raw-dir", str(tmp_path / "raw"),
        "--capsule-dir", str(tmp_path / "cap"),
    ])
    assert rc != 0
    assert not (tmp_path / "raw").exists()
    assert not (tmp_path / "cap").exists()


# ---------------------------------------------------------------------------
# (c) exceeding the USD budget rejects the NEXT send before transport
# ---------------------------------------------------------------------------


def test_usd_cap_rejects_next_send_before_transport(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    cap = tmp_path / "cap"
    # Fake usage costs ~$1.30 per call at the peak snapshot.  After two
    # responses cumulative cost (~$2.60) is below the 2.61 peak cap, so the
    # third call is refused in the PRE-send conservative-bound check (never
    # reaches the transport).
    price = ex.price_snapshot(off_peak=False)
    miss = float(price["input_cache_miss_per_million"])
    out_p = float(price["output_per_million"])
    target = 1.30
    prompt_x = int((target - 4096 * out_p / 1_000_000) * 1_000_000 / miss)

    def scaled_usage(_ordinal: int) -> dict:
        return {
            "prompt_tokens": prompt_x,
            "completion_tokens": 4096,
            "total_tokens": prompt_x + 4096,
        }

    with pytest.raises(ex.Gdpr7ExecutionError, match="USD"):
        ex.execute_batch(raw_dir=raw, capsule_dir=cap, fake=True,
                         usage_provider=scaled_usage)

    ledger = _ledger_lines(raw)
    assert len(ledger) == 2                      # two responses recorded
    assert all(r["status"] == "completed" for r in ledger)
    assert not cap.exists()                       # nothing published
    assert sum(r["cost_usd"] for r in ledger) < ex.USD_CAP_PEAK


# ---------------------------------------------------------------------------
# (d) mid-run failure -> in_doubt; resume sends only the remainder
# ---------------------------------------------------------------------------


def test_midrun_in_doubt_then_resume_sends_only_remainder(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    cap = tmp_path / "cap"

    def missing_usage_at_six(ordinal: int) -> dict:
        # ordinal 6 returns a response WITHOUT usage -> in_doubt
        return {} if ordinal == 6 else dict(_ZERO_USAGE)

    with pytest.raises(ex.Gdpr7ExecutionError, match="in_doubt"):
        ex.execute_batch(raw_dir=raw, capsule_dir=cap, fake=True,
                         usage_provider=missing_usage_at_six)

    ledger_after_abort = _ledger_lines(raw)
    assert len(ledger_after_abort) == 6
    assert [r["call_index"] for r in ledger_after_abort] == [1, 2, 3, 4, 5, 6]
    assert ledger_after_abort[-1]["status"] == "in_doubt"
    assert not cap.exists()                       # partial run: nothing published

    # Resume: re-sends ONLY never-attempted rows 7..74.
    summary = ex.execute_batch(raw_dir=raw, capsule_dir=cap, fake=True,
                               resume=True)
    assert summary["per_call_status_counts"] == {
        "completed": 73, "in_doubt": 1, "failed": 0,
    }
    assert summary["status"] == "complete_with_explicit_failures"

    ledger_final = _ledger_lines(raw)
    assert len(ledger_final) == 74
    # Append-only: no payload was ever recorded twice -> no re-send of
    # completed rows and no auto-resend of the in_doubt row.
    shas = [r["request_body_sha256"] for r in ledger_final]
    assert len(set(shas)) == 74
    assert [r["call_index"] for r in ledger_final] == list(range(1, 75))
    # The in_doubt entry survived untouched (never re-sent, never dropped).
    row6 = [r for r in ledger_final if r["call_index"] == 6]
    assert len(row6) == 1 and row6[0]["status"] == "in_doubt"
    # Every response line exists exactly once per call.
    raw_entries = _raw_lines(raw)
    assert sorted(e["call_index"] for e in raw_entries) == list(range(1, 75))

    # The capsule records the explicit failure row (never dropped).
    pred = _load_json(cap / "predictions.json")
    rows_by_sample = {r["sample_id"]: r for r in pred["records"]}
    assert len(rows_by_sample) == 74
    ok_count = sum(1 for r in pred["records"]
                   if r["request_status"] == "ok" and not r["error_category"])
    assert ok_count == 73
    bad = rows_by_sample["gdpr_article15_s006"]
    assert bad["request_status"] == "in_doubt"
    assert bad["error_category"]
    assert bad["record"] is None


# ---------------------------------------------------------------------------
# (e) payload fingerprint drift fails closed before send
# ---------------------------------------------------------------------------


def test_payload_fingerprint_drift_fails_closed_before_send(tmp_path: Path) -> None:
    report = _load_json(REPORT_FILE)
    calls = report["arms"]["direct_llm"]["calls"]
    calls[3]["request_body_sha256"] = "0" * 64        # mutate one locked body
    drifted = tmp_path / "drifted_report.json"
    drifted.write_bytes(
        (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )

    raw = tmp_path / "raw"
    cap = tmp_path / "cap"
    with pytest.raises(ex.Gdpr7ExecutionError, match="locked"):
        ex.execute_batch(raw_dir=raw, capsule_dir=cap, fake=True,
                         report_file=drifted)
    # Fail closed BEFORE any send: nothing at all was created.
    assert not raw.exists()
    assert not cap.exists()


# ---------------------------------------------------------------------------
# (f) returned_model mismatch aborts
# ---------------------------------------------------------------------------


def test_returned_model_mismatch_aborts(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    cap = tmp_path / "cap"
    with pytest.raises(ex.Gdpr7ExecutionError, match="returned model"):
        ex.execute_batch(raw_dir=raw, capsule_dir=cap, fake=True,
                         fake_model="deepseek-chat")
    # The mismatch aborts before any completed ledger row is recorded.
    assert not (raw / "ledger.jsonl").exists()
    assert not cap.exists()


# ---------------------------------------------------------------------------
# (g) gold-blindness: no decision / expected / Gold labels, no raw text
# ---------------------------------------------------------------------------


def test_outputs_are_gold_blind_and_text_free(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    cap = tmp_path / "cap"
    summary = _fake_ok(raw, cap)

    docs = {}
    for name in ("predictions.json", "telemetry.json", "cost.json",
                 "manifest.json"):
        docs[name] = _load_json(cap / name)

    # No raw-text keys anywhere in the committed capsule docs.
    for name, doc in docs.items():
        assert not ex._contains_keys(doc, ex._FORBIDDEN_TEXT_KEYS), name
        assert not ex._contains_keys(doc, ex._FORBIDDEN_DECISION_KEYS), name

    # Predictions: only coordinates are committed (no clause text, no
    # source text, no expected/Gold material).
    pred = docs["predictions.json"]
    blob_keys = json.dumps(pred)
    for term in ("expected_violation", "variant_id", "check_type",
                 "human_correction", "adjudicat", "gold_rule", "oracle"):
        assert term not in blob_keys
    for row in pred["records"]:
        if row["record"] is None:
            continue
        rec_blob = json.dumps(row["record"])
        assert '"source_text"' not in rec_blob
        assert '"text"' not in rec_blob
        assert '"normalized"' not in rec_blob
        # span objects carry only coordinates
        for clause in row["record"]["clauses"]:
            span = clause["clause_span"]
            assert set(span) <= {"start", "end"}
            modality = clause["modality"]
            for ev in modality["evidence"]:
                assert set(ev) <= {"start", "end"}

    # The ledger carries no raw content and no decision material.
    ledger = _ledger_lines(raw)
    assert all("content" not in rec for rec in ledger)
    assert not any(ex._contains_keys(rec, ex._FORBIDDEN_TEXT_KEYS)
                   for rec in ledger)
    assert summary["manifest"]["gold_isolation"]["gold_read_by_runner"] is False


# ---------------------------------------------------------------------------
# (h) downstream compatibility with the linkage runner (dry arm-load)
# ---------------------------------------------------------------------------


def test_predictions_capsule_loads_with_linkage_schema(tmp_path: Path) -> None:
    import run_gdpr_s2_s3_linkage_v1 as link
    from bpc_hybrid.gdpr_s2_s3_projection import project_external_sentence

    raw = tmp_path / "raw"
    cap = tmp_path / "cap"
    _fake_ok(raw, cap)

    # Linkage runner's expected direct_llm arm schema matches our capsule.
    assert link.ARM_PREDICTION_SCHEMAS["direct_llm"] == ex.PREDICTION_SCHEMA
    assert ex.PREDICTION_SCHEMA == "gdpr7_direct_llm_predictions@1.0.0"

    # Dry arm-load exactly as run_arm does: runner loader + schema check.
    pred_doc = link._load_json(cap / "predictions.json", "arm predictions")
    assert pred_doc.get("schema_version") == link.ARM_PREDICTION_SCHEMAS["direct_llm"]
    pred_by_sample = link._pred_by_sample(pred_doc)
    assert len(pred_by_sample) == 74

    input_doc = link._load_json(pre.INPUT, "GDPR Stage-2 input")
    texts_by_sample = link._sentence_text_by_sample(input_doc)
    assert len(texts_by_sample) == 74
    assert set(texts_by_sample) == set(pred_by_sample)

    # Structural projection of every capsule row (first-valid-span
    # projection) succeeds; no sample is missing or structurally broken.
    failures: list[str] = []
    empty = 0
    for sample_id, text in texts_by_sample.items():
        proj = project_external_sentence(pred_by_sample[sample_id], text,
                                         sample_id)
        if not proj["ok"]:
            failures.append(f"{sample_id}:{proj['error']}")
        if proj["ok"] and not (proj["sentence"].get("modality") or ""):
            empty += 1
    assert failures == []
    assert empty == 0
