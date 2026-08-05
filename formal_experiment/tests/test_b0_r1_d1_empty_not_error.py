"""Empty-vs-error semantics tests (D1-R1, user decision 2026-08-05).

User decision: empty is not an error. The six semantic elements may be
partially empty, and Gold does not imply every element is present. This
module verifies (a) the canonical validator accepts empty modality.evidence
and empty order_relation evidence, and (b) the JSON schema allows empty
evidence arrays.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.stage2_canonical import validate_canonical  # noqa: E402

SRC = "The tax office shall refund the amount if the application is filed within two years."


def base_record():
    return {
        "schema_version": "1.0.0",
        "sample_id": "estg_demo",
        "source_id": "estg_demo",
        "source_text": SRC,
        "clauses": [
            {
                "clause_id": "c01",
                "clause_span": {"text": SRC, "start": 0, "end": len(SRC)},
                "modality": {"label": "obligation", "evidence": [{"text": "shall", "start": 15, "end": 20}]},
                "actors": [],
                "actions": [{"id": "p01", "text": "refund the amount", "start": 21, "end": 38, "normalized": "refund amount"}],
                "conditions": [],
                "constraints": [],
                "exceptions": [],
                "actor_action_map": [{"actor_id": None, "action_id": "p01"}],
                "order_relations": [],
            }
        ],
        "method": {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
        "unsupported_or_ambiguous": [],
    }


def test_empty_modality_evidence_is_valid() -> None:
    r = base_record()
    r["clauses"][0]["modality"]["evidence"] = []
    rep = validate_canonical(r)
    assert rep.schema_valid and rep.cross_field_valid
    assert rep.errors == []


def test_empty_order_relation_evidence_is_valid() -> None:
    r = base_record()
    r["clauses"][0]["actions"].append({"id": "p02", "text": "the application is filed within two years", "start": 42, "end": 83, "normalized": "the application is filed within two years"})
    r["clauses"][0]["order_relations"] = [
        {"before_action_id": "p01", "after_action_id": "p02", "evidence": []}
    ]
    rep = validate_canonical(r)
    assert rep.schema_valid and rep.cross_field_valid
    assert rep.errors == []


def test_evidence_non_list_still_rejected() -> None:
    r = base_record()
    r["clauses"][0]["modality"]["evidence"] = {"text": "shall"}
    rep = validate_canonical(r)
    assert not (rep.schema_valid and rep.cross_field_valid)
    assert any("evidence must be an array" in e for e in rep.errors)


def test_schema_allows_empty_evidence_arrays() -> None:
    schema = json.load(open(ROOT / "configs/schemas/stage2_prediction.schema.json", encoding="utf-8"))
    modality_evidence = schema["$defs"]["modality"]["properties"]["evidence"]
    order_evidence = schema["$defs"]["orderRelation"]["properties"]["evidence"]
    assert modality_evidence["type"] == "array"
    assert modality_evidence.get("minItems", 0) == 0
    assert order_evidence["type"] == "array"
    assert order_evidence.get("minItems", 0) == 0
    r = base_record()
    r["clauses"][0]["modality"]["evidence"] = []
    assert validate_canonical(r).errors == []
