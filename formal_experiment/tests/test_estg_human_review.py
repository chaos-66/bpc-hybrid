"""Tests for the EStG manual text-and-Gold review gate."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_estg_human_review_pack import build_pack
from validate_estg_human_review import validate_pack


def test_real_review_pack_is_blank_and_ready_for_human_review() -> None:
    path = ROOT / "data/development/human_review/estg150_review_pack_v1.jsonl"
    result = validate_pack(path)
    assert result["record_count"] == 150
    assert result["unique_ids"] == 150
    assert result["human_review_ready"] is True
    assert result["freeze_ready"] is False
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert all(row["clauses"] == [] for row in rows)
    assert all(row["text_review"]["status"] == "needs_review" for row in rows)
    assert all(row["annotation_review"]["status"] == "needs_review" for row in rows)


def test_builder_refuses_overwrite(tmp_path: Path) -> None:
    source = ROOT / "data/development/estg/estg_selected_150_en_llm_translated.jsonl"
    output = tmp_path / "pack.jsonl"
    assert build_pack(source, output) == 150
    try:
        build_pack(source, output)
    except FileExistsError:
        pass
    else:
        raise AssertionError("builder overwrote an existing review pack")


def test_validator_rejects_bad_span(tmp_path: Path) -> None:
    original = ROOT / "data/development/human_review/estg150_review_pack_v1.jsonl"
    rows = [json.loads(line) for line in original.read_text(encoding="utf-8").splitlines()]
    row = rows[0]
    text = row["source"]["candidate_text_en"]
    row["text_review"].update({"status": "approved", "reviewer": "human", "reviewed_at": "2026-07-11", "approved_text_en": text})
    row["clauses"] = [{
        "clause_id": f"{row['sample_id']}_c01",
        "clause_span": {"value": "WRONG", "start": 0, "end": 5},
        "modality": {"label": "obligation", "evidence": [{"value": text[0:1], "start": 0, "end": 1}]},
        "actors": [], "actions": [{"id": "p01", "value": text[0:1], "start": 0, "end": 1}],
        "conditions": [], "constraints": [], "exceptions": [],
        "actor_action_map": [{"actor_id": None, "action_id": "p01"}], "order_relations": []
    }]
    path = tmp_path / "bad.jsonl"
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in rows) + "\n", encoding="utf-8")
    result = validate_pack(path)
    assert result["format_valid"] is False
    assert any(issue["code"] == "span_text_mismatch" for issue in result["issues"])


def test_direct_llm_runner_is_guarded_and_rule_free() -> None:
    path = ROOT / "scripts/run_direct_llm.py"
    source = path.read_text(encoding="utf-8")
    assert "--allow-llm" in source
    assert "--max-calls" in source
    assert "gold_read_by_runner" in source
    assert "SemanticExtractor" not in source
    assert "data/gold" not in source.replace("\\", "/")


def test_review_tools_are_offline() -> None:
    for name in ("build_estg_human_review_pack.py", "validate_estg_human_review.py"):
        source = (SCRIPTS / name).read_text(encoding="utf-8")
        for token in ("import requests", "import httpx", "import openai", "RealAPITransport", "load_dotenv"):
            assert token not in source
