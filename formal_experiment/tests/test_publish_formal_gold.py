"""Focused tests for the deterministic Formal Gold publisher.

Verifies the pure extraction / construction functions of
``scripts/publish_formal_gold_v1.py`` against synthetic fixtures:

- Stage 2 Gold extraction from Layer E (flat six-element spans, decision-only
  output, per-record source hash).
- Fail-closed publication preconditions (membership hash, 150/150, gate
  whitelist, Stage 3 25+33 adjudication).
- Stage 2 formal input / gold symmetry.
- Stage 3 matching / violation Gold construction.

No real file is touched; all sources are synthetic tmp fixtures.
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

from scripts.publish_formal_gold_v1 import (  # noqa: E402
    _build_estg150_formal_input,
    _build_stage3_gold,
    _canonical_json,
    _check_preconditions,
    _extract_stage2_gold,
    _sha256_bytes,
)

REAL_CONTRACT = ROOT / "configs" / "experiment_contract.json"


# --------------------------------------------------------------------------- fixtures


def _layer_e_record(sample_id: str, legacy_id: int) -> dict:
    """Synthetic Layer E record with one clause carrying flat span items."""
    return {
        "sample_id": sample_id,
        "legacy_record_id": legacy_id,
        "approved_text_en": "A tenant must keep the rental property in good condition.",
        "approved_text_en_sha256": "x" * 64,
        "candidate_text_en": "A tenant must keep the rental property in good condition.",
        "candidate_text_en_sha256": "y" * 64,
        "raw_text_de": "Der Mieter muss die Mietsache in gutem Zustand halten.",
        "raw_text_de_sha256": "z" * 64,
        "review_state": {
            "status": "adjudicated", "reviewer": "user",
            "reviewed_at": "2026-08-10T00:00:00Z",
            "adjudicated_at": "2026-08-10T00:00:00Z", "notes": None,
        },
        "decisions": {
            "translation": {"decision": "accepted"},
            "modality": {"decision": "accepted"},
            "actor": {"decision": "accepted"},
            "action": {"decision": "accepted"},
            "condition": {"decision": "accepted"},
            "constraint": {"decision": "accepted"},
            "exception": {"decision": "accepted"},
        },
        "human_correction": {
            "approved_text_en": "A tenant must keep the rental property in good condition.",
            "approved_text_en_decision": "accepted",
            "translation_notes": None,
            "clauses": [
                {
                    "clause_id": f"{sample_id}_c01",
                    "clause_span": {
                        "text": "A tenant must keep the rental property in good condition.",
                        "start": 0, "end": 61,
                    },
                    "clause_span_status": "accepted",
                    "modality": {"value": "obligation", "decision": "accepted",
                                 "span": None, "notes": None},
                    "actors": [
                        {"id": f"{sample_id}_c01_sp001", "text": "A tenant",
                         "start": 0, "end": 8, "decision": "accepted"},
                    ],
                    "actions": [
                        {"id": f"{sample_id}_c01_sp002", "text": "must keep",
                         "start": 9, "end": 18, "decision": "accepted"},
                    ],
                    "conditions": [
                        {"id": f"{sample_id}_c01_sp003", "text": "in good condition",
                         "start": 31, "end": 49, "decision": "accepted"},
                    ],
                    "constraints": [],
                    "exceptions": [],
                    "actor_action_map": [[f"{sample_id}_c01_sp001",
                                          f"{sample_id}_c01_sp002"]],
                    "order_relations": [],
                    "_stale": False,
                }
            ],
        },
        "llm_candidate": {"draft": "candidate text", "immutable": True},
        "source_refs": {"german_source": f"estg_selected_150_de.jsonl#{legacy_id}"},
        "approved_text_en_history": [],
    }


def _layer_e_150() -> dict:
    records = [
        _layer_e_record(f"estg_syn_{i:03d}", i)
        for i in range(1, 151)
    ]
    return {"schema_version": "test", "records": records}


def _membership_hashes(records: list[dict]) -> dict:
    legacy_ids = sorted(int(r["legacy_record_id"]) for r in records)
    payload = ",".join(str(i) for i in legacy_ids)
    return {
        "dataset_id": "estg_selected_150_v1",
        "selected_membership": {
            "count": len(legacy_ids),
            "membership_payload_sha256": _sha256_bytes(payload.encode("utf-8")),
            "file_sha256": "a" * 64,
            "id_file_sha256": "b" * 64,
            "sorted_legacy_record_ids": legacy_ids,
        },
    }


def _contract() -> dict:
    real = json.loads(REAL_CONTRACT.read_text(encoding="utf-8"))
    return {
        "stage3": {"status": real["stage3"]["status"]},
        "stage2_dataset": {"status": real["stage2_dataset"]["status"]},
        "formal_gold_publication_gate": {
            "status": real["formal_gold_publication_gate"]["status"],
            "allowed_publication_statuses":
                real["formal_gold_publication_gate"]["allowed_publication_statuses"],
        },
    }


def _stage3_correction(n_match: int = 25, n_violation: int = 33,
                       all_adjudicated: bool = True) -> dict:
    matching = [
        {"item_id": f"m{i:03d}", "process_id": f"p{i % 7 + 1}",
         "rule_id": f"r{i % 12 + 1}", "decision_relevant": True,
         "review_state": "adjudicated" if all_adjudicated else "reviewed"}
        for i in range(n_match)
    ]
    violation = [
        {"item_id": f"v{i:03d}", "process_id": f"p{i % 7 + 1}",
         "rule_id": f"r{i % 12 + 1}",
         "decision_violation_type": "missing_action",
         "decision_evidence": "evidence text",
         "review_state": "adjudicated" if all_adjudicated else "reviewed"}
        for i in range(n_violation)
    ]
    return {"matching_items": matching, "violation_items": violation}


def _stage3_inference(corr: dict) -> dict:
    return {
        "matching_items": [{"item_id": i["item_id"]} for i in corr["matching_items"]],
        "violation_items": [
            {"item_id": i["item_id"], "check_type": "missing_action"}
            for i in corr["violation_items"]
        ],
    }


def _write(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return path


def _synthetic_paths(tmp_path: Path, layer_e: dict,
                     membership: dict) -> dict[str, Path]:
    return {
        "contract": _write(tmp_path, "contract.json", _contract()),
        "layer_e": _write(tmp_path, "layer_e.json", layer_e),
        "membership_hashes": _write(tmp_path, "membership_hashes.json", membership),
        "stage3_correction": _write(
            tmp_path, "stage3_correction.json", _stage3_correction()),
        "inference_pack": _write(
            tmp_path, "stage3_inference.json",
            _stage3_inference(_stage3_correction())),
    }


# --------------------------------------------------------------------------- stage 2 extraction


def test_extract_flat_span_items(monkeypatch, tmp_path: Path) -> None:
    layer_e = _layer_e_150()
    monkeypatch.setattr(
        "scripts.publish_formal_gold_v1.DEFAULT_PATHS",
        {"membership_hashes": _write(tmp_path, "mh.json",
                                     _membership_hashes(layer_e["records"]))},
    )
    gold = _extract_stage2_gold(layer_e)
    assert len(gold["records"]) == 150
    rec = gold["records"][0]
    clause = rec["clauses"][0]
    assert clause["actors"] == [{"id": "estg_syn_001_c01_sp001",
                                 "text": "A tenant", "start": 0, "end": 8}]
    assert clause["actions"][0]["text"] == "must keep"
    assert clause["conditions"][0]["text"] == "in good condition"
    assert clause["modality"] == "obligation"
    # decision-only: no LLM candidate fields, no decision metadata leaks out
    assert "decision" not in clause["actors"][0]
    assert "llm_candidate" not in rec
    assert rec["decisions"]["translation"]["decision"] == "accepted"


def test_extract_keeps_relations_and_clause_span(monkeypatch,
                                                 tmp_path: Path) -> None:
    layer_e = _layer_e_150()
    monkeypatch.setattr(
        "scripts.publish_formal_gold_v1.DEFAULT_PATHS",
        {"membership_hashes": _write(tmp_path, "mh.json",
                                     _membership_hashes(layer_e["records"]))},
    )
    gold = _extract_stage2_gold(layer_e)
    clause = gold["records"][0]["clauses"][0]
    assert clause["actor_action_map"] == [["estg_syn_001_c01_sp001",
                                           "estg_syn_001_c01_sp002"]]
    assert clause["clause_span"]["text"] == (
        "A tenant must keep the rental property in good condition.")
    assert clause["clause_span"]["start"] == 0
    assert clause["clause_span"]["end"] == 61


def test_extract_source_hash_stable_and_sensitive(monkeypatch,
                                                  tmp_path: Path) -> None:
    layer_e = _layer_e_150()
    monkeypatch.setattr(
        "scripts.publish_formal_gold_v1.DEFAULT_PATHS",
        {"membership_hashes": _write(tmp_path, "mh.json",
                                     _membership_hashes(layer_e["records"]))},
    )
    g1 = _extract_stage2_gold(layer_e)
    g2 = _extract_stage2_gold(layer_e)
    h1 = [r["source_hashes"]["layer_e_record_sha256"] for r in g1["records"]]
    h2 = [r["source_hashes"]["layer_e_record_sha256"] for r in g2["records"]]
    assert h1 == h2
    # the hash covers the full Layer E record including the immutable
    # llm_candidate copy, so a content change must change the hash
    layer_e["records"][0]["approved_text_en"] = "changed text"
    g3 = _extract_stage2_gold(layer_e)
    assert (g3["records"][0]["source_hashes"]["layer_e_record_sha256"]
            != h1[0])


def test_extract_duplicate_sample_id_raises(monkeypatch,
                                            tmp_path: Path) -> None:
    layer_e = _layer_e_150()
    layer_e["records"][1]["sample_id"] = layer_e["records"][0]["sample_id"]
    monkeypatch.setattr(
        "scripts.publish_formal_gold_v1.DEFAULT_PATHS",
        {"membership_hashes": _write(tmp_path, "mh.json",
                                     _membership_hashes(layer_e["records"]))},
    )
    with pytest.raises(RuntimeError, match="duplicate sample_id"):
        _extract_stage2_gold(layer_e)


def test_extract_invalid_clause_span_raises(monkeypatch,
                                            tmp_path: Path) -> None:
    layer_e = _layer_e_150()
    layer_e["records"][0]["human_correction"]["clauses"][0]["clause_span"] = {}
    monkeypatch.setattr(
        "scripts.publish_formal_gold_v1.DEFAULT_PATHS",
        {"membership_hashes": _write(tmp_path, "mh.json",
                                     _membership_hashes(layer_e["records"]))},
    )
    with pytest.raises(RuntimeError, match="invalid clause_span"):
        _extract_stage2_gold(layer_e)


def test_extract_requires_exactly_150(monkeypatch, tmp_path: Path) -> None:
    layer_e = {"records": [_layer_e_record("estg_syn_001", 1)]}
    monkeypatch.setattr(
        "scripts.publish_formal_gold_v1.DEFAULT_PATHS",
        {"membership_hashes": _write(tmp_path, "mh.json",
                                     _membership_hashes(layer_e["records"]))},
    )
    with pytest.raises(RuntimeError, match="exactly 150"):
        _extract_stage2_gold(layer_e)


# --------------------------------------------------------------------------- preconditions


def test_preconditions_pass_with_synthetic_sources(tmp_path: Path) -> None:
    layer_e = _layer_e_150()
    membership = _membership_hashes(layer_e["records"])
    paths = _synthetic_paths(tmp_path, layer_e, membership)
    checks = _check_preconditions(paths)
    assert all(checks.values())
    assert "membership payload hash match" in checks
    assert "layer_e 150/150 adjudicated" in checks


def test_preconditions_fail_on_membership_mismatch(tmp_path: Path) -> None:
    layer_e = _layer_e_150()
    membership = _membership_hashes(layer_e["records"])
    membership["selected_membership"]["membership_payload_sha256"] = "0" * 64
    paths = _synthetic_paths(tmp_path, layer_e, membership)
    with pytest.raises(RuntimeError, match="membership payload hash match"):
        _check_preconditions(paths)


def test_preconditions_fail_on_non_whitelisted_gate(tmp_path: Path) -> None:
    layer_e = _layer_e_150()
    paths = _synthetic_paths(tmp_path, layer_e,
                             _membership_hashes(layer_e["records"]))
    contract = json.loads(paths["contract"].read_text(encoding="utf-8"))
    contract["formal_gold_publication_gate"]["status"] = "paused"
    paths["contract"].write_text(json.dumps(contract, ensure_ascii=False),
                                 encoding="utf-8")
    with pytest.raises(RuntimeError,
                       match="publication gate exact whitelist match"):
        _check_preconditions(paths)


def test_preconditions_fail_on_stage3_counts(tmp_path: Path) -> None:
    layer_e = _layer_e_150()
    paths = _synthetic_paths(tmp_path, layer_e,
                             _membership_hashes(layer_e["records"]))
    corr = json.loads(paths["stage3_correction"].read_text(encoding="utf-8"))
    corr["matching_items"] = corr["matching_items"][:24]
    paths["stage3_correction"].write_text(json.dumps(corr, ensure_ascii=False),
                                          encoding="utf-8")
    with pytest.raises(RuntimeError, match="stage3 25\\+33 adjudicated"):
        _check_preconditions(paths)


def test_preconditions_fail_when_not_150(tmp_path: Path) -> None:
    layer_e = _layer_e_150()
    layer_e["records"] = layer_e["records"][:149]
    paths = _synthetic_paths(tmp_path, layer_e,
                             _membership_hashes(layer_e["records"]))
    with pytest.raises(RuntimeError, match="layer_e 150/150 adjudicated"):
        _check_preconditions(paths)


# --------------------------------------------------------------------------- formal input


def test_build_input_150_unique_and_aligned(monkeypatch,
                                            tmp_path: Path) -> None:
    layer_e = _layer_e_150()
    membership = _membership_hashes(layer_e["records"])
    monkeypatch.setattr(
        "scripts.publish_formal_gold_v1.DEFAULT_PATHS",
        {"membership_hashes": _write(tmp_path, "mh.json", membership)},
    )
    inp = _build_estg150_formal_input(layer_e, membership)
    assert inp["count"] == 150
    assert len(inp["sample_ids"]) == 150
    gold = _extract_stage2_gold(layer_e)
    assert inp["sample_ids"] == [r["sample_id"] for r in gold["records"]]
    assert (inp["membership_payload_sha256"]
            == membership["selected_membership"]["membership_payload_sha256"])


def test_build_input_requires_150_unique(tmp_path: Path) -> None:
    layer_e = {"records": [_layer_e_record("estg_syn_001", 1)]}
    with pytest.raises(RuntimeError, match="exactly 150 unique"):
        _build_estg150_formal_input(layer_e, _membership_hashes(layer_e["records"]))


# --------------------------------------------------------------------------- stage 3 gold


def test_build_stage3_gold_extracts_decisions(tmp_path: Path) -> None:
    corr = _stage3_correction()
    inf = _stage3_inference(corr)
    matching, violation = _build_stage3_gold(corr, inf)
    assert matching["count"] == 25
    assert violation["count"] == 33
    assert matching["items"][0]["decision_relevant"] is True
    assert all("decision_evidence" not in it for it in matching["items"])
    assert violation["items"][0]["check_type"] == "missing_action"
    assert violation["items"][0]["decision_violation_type"] == "missing_action"
    assert all("review_state" not in it for it in violation["items"])


def test_build_stage3_gold_rejects_unadjudicated(tmp_path: Path) -> None:
    corr = _stage3_correction(all_adjudicated=False)
    inf = _stage3_inference(corr)
    with pytest.raises(RuntimeError, match="not adjudicated"):
        _build_stage3_gold(corr, inf)


def test_build_stage3_gold_rejects_membership_mismatch(tmp_path: Path) -> None:
    corr = _stage3_correction()
    inf = _stage3_inference(corr)
    inf["matching_items"] = inf["matching_items"][:24]
    with pytest.raises(RuntimeError, match="matching membership must be exactly 25"):
        _build_stage3_gold(corr, inf)


# --------------------------------------------------------------------------- canonical json helper


def test_canonical_json_deterministic() -> None:
    # key order does not matter (sorted keys); list order is preserved
    a = _canonical_json({"b": 2, "a": [1, 3, 2]})
    b = _canonical_json({"a": [1, 3, 2], "b": 2})
    assert a == b
    c = _canonical_json({"a": [1, 2, 3], "b": 2})
    assert a != c
