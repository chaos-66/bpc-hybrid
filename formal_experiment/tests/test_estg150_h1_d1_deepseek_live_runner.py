from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_estg150_h1_d1_deepseek_v4pro.py"


def _module():
    spec = importlib.util.spec_from_file_location("run_estg150_h1_d1_deepseek_v4pro", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_d1_validator_exception_is_retained_instead_of_stopping_batch(monkeypatch) -> None:
    module = _module()
    row = {
        "sample_id": "synthetic_live_d1",
        "source_id": "synthetic_live_d1",
        "source_text": "It may act.",
        "data_role": "development_input",
    }
    response_record = {
        "schema_version": "1.0.0",
        "sample_id": row["sample_id"],
        "source_id": row["source_id"],
        "source_text": row["source_text"],
        "clauses": [
            {
                "clause_id": "synthetic_live_d1.c1",
                "clause_span": {"text": row["source_text"], "start": 0, "end": 11},
                "modality": {"label": "permission", "evidence": [{"text": "may", "start": 3, "end": 6}]},
                "actors": [{"id": "a1", "text": "It", "start": 0, "end": 2}],
                "actions": [{"id": "p1", "text": "act", "start": 7, "end": 10, "normalized": "act"}],
                "conditions": [],
                "constraints": [],
                "exceptions": [],
                "actor_action_map": [{"actor_id": "a1", "action_id": "p1"}],
                "order_relations": [],
            }
        ],
        "method": {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
        "unsupported_or_ambiguous": [],
    }
    monkeypatch.setattr(
        module,
        "_call_api",
        lambda **_: {
            "ok": True,
            "content": json.dumps(response_record),
            "response_sha256": "a" * 64,
            "request_sha256": "b" * 64,
            "latency_ms": 1.0,
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2,
        },
    )
    config = module._json(module.CONFIG_PATH)
    protocol = module._json(ROOT / config["methods"]["D1"]["protocol_config"])
    result = module._d1_job(
        row,
        module.load_prompt("direct_llm_sun_record_prompt"),
        protocol,
        config["shared_runtime"],
        "not-a-real-key",
    )
    assert result["request_status"] == "ok"
    assert result["record"] is not None
    assert result["error_category"] == "canonical_validation_warning"
    assert result["canonical_validation"]["errors"] == ["validator_exception:KeyError"]


def test_h1_stored_patch_discards_only_nonsemantic_clause_span() -> None:
    module = _module()
    config = module._json(module.CONFIG_PATH)
    records = module._load_b0(config)
    selection = module._json(ROOT / config["inputs"]["h1_trigger_selection"])["selection"]["samples"][0]
    record = next(item for item in records if item["sample_id"] == selection["sample_id"])
    protocol = module._json(ROOT / config["methods"]["H1"]["protocol_config"])
    modality = record["clauses"][0]["modality"]
    response = {
        "sample_id": record["sample_id"],
        "parsed_patch": {
            "sample_id": record["sample_id"],
            "clause_id": record["clauses"][0]["clause_id"],
            "repair_fields": ["modality"],
            "patches": {"clause_span": None, "modality": modality},
            "unsupported_or_ambiguous": record.get("unsupported_or_ambiguous", []),
            "reason": "synthetic regression",
        },
        "postprocess": [],
    }
    adapted = module._adapt_stored_h1_response(
        response,
        record,
        float(selection["b0_confidence"]),
        protocol,
    )
    assert adapted["merge"]["status"] == "accepted"
    assert "clause_span" not in adapted["parsed_patch_after_adapter"]["patches"]
    assert adapted["postprocess"] == ["discarded_unrequested_nonsemantic_patch:clause_span"]
