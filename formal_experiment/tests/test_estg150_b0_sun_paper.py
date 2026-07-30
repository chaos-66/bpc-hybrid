from __future__ import annotations

import json
from pathlib import Path

from bpc_hybrid.estg150_b0_sun_paper import (
    PAPER_ORDER,
    _actor_dependency_supported,
    load_marker_parameter,
    write_paper_rule_plan,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/models/estg150_b0_sun_paper_s27_v1.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_paper_rule_plan_uses_published_order_and_real_context_surgery(tmp_path: Path) -> None:
    config = _load(CONFIG)
    method = config["method"]
    registry = _load(ROOT / method["pattern_registry"]["path"])
    markers, _ = load_marker_parameter(
        ROOT, method["marker_parameter"]["category_files"]
    )
    target = tmp_path / "plan.tsv"
    count = write_paper_rule_plan(registry, markers, target)
    lines = [line.split("\t") for line in target.read_text(encoding="utf-8").splitlines()]

    assert tuple(registry["extraction_order"]) == PAPER_ORDER
    assert count == 247
    assert [line[0] for line in lines[:3]] == ["modality"] * 3
    assert lines[-1] == ["action", "VP=action", ""]
    assert all(line[2].startswith("prune ") for line in lines if line[0] in PAPER_ORDER[:4])
    assert all(line[2] == "" for line in lines if line[0] in {"actor", "action"})


def test_actor_requires_published_dependency_and_voice_gate() -> None:
    tokens = [
        {"pos": "DT"},
        {"pos": "NN"},
        {"pos": "MD"},
        {"pos": "VB"},
        {"pos": "IN"},
        {"pos": "NN"},
    ]
    subject_sentence = {
        "tokens": tokens,
        "basicDependencies": [{"dep": "nsubj", "dependent": 2}],
    }
    active_object_sentence = {
        "tokens": tokens,
        "basicDependencies": [{"dep": "obj", "dependent": 6}],
    }
    passive_object_sentence = {
        "tokens": tokens,
        "basicDependencies": [
            {"dep": "aux:pass", "dependent": 3},
            {"dep": "obl:agent", "dependent": 6},
        ],
    }
    unsupported_sentence = {
        "tokens": tokens,
        "basicDependencies": [{"dep": "compound", "dependent": 2}],
    }

    assert _actor_dependency_supported(subject_sentence, {"begin": 0, "end": 2})
    assert _actor_dependency_supported(active_object_sentence, {"begin": 5, "end": 6})
    assert _actor_dependency_supported(passive_object_sentence, {"begin": 5, "end": 6})
    assert not _actor_dependency_supported(unsupported_sentence, {"begin": 0, "end": 2})


def test_config_excludes_v10_extensions_and_preserves_reproduction_boundary() -> None:
    config = _load(CONFIG)
    method = config["method"]
    registry = _load(ROOT / method["pattern_registry"]["path"])

    assert method["paper_faithful_reconstruction"] is True
    assert method["exact_original_reproduction"] is False
    assert method["marker_parameter"]["is_original_sun_marker_inventory"] is False
    assert len(method["excluded_project_extensions"]) == 5
    assert registry["reproduction_boundary"]["custom_v10_scope_alignment_definition_resolvers_used"] is False
    assert registry["primary_source"]["pdf_pages"] == [10, 11, 12, 13]
