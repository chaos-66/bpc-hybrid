from __future__ import annotations

import json
from pathlib import Path

from bpc_hybrid.estg150_b0_sun_paper_v2 import (
    actor_dependency_supported_by_clause_relation,
    write_semantics_v2_rule_plan,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "resources/corenlp/sun_phrase_patterns_semantics_v2.json"
MANIFEST = ROOT / "outputs/reports/s27_b0_sun_mini_semantics_v2.manifest.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v2_plan_preserves_published_immediate_and_descendant_relations(
    tmp_path: Path,
) -> None:
    markers = {
        "actor": ("taxpayer",),
        "condition": ("if",),
        "constraint": ("under section",),
        "exception": ("except for",),
    }
    target = tmp_path / "plan.tsv"
    count = write_semantics_v2_rule_plan(_load(REGISTRY), markers, target)
    lines = target.read_text(encoding="utf-8").splitlines()

    assert count == 12
    actor = next(line for line in lines if line.startswith("actor\t"))
    constraint = [line for line in lines if line.startswith("constraint\t")]
    exception_np = next(
        line for line in lines if line.startswith("exception\tNP=exception")
    )
    condition = next(line for line in lines if line.startswith("condition\tSBAR"))

    assert "NP=actor < (__ < /(?i)^taxpayer$/)" in actor
    assert "NP=actor <<" not in actor
    assert "NP=constraint < (__ < /(?i)^under$/)" in constraint[0]
    assert "PP=constraint < (IN < /(?i)^under$/) $ NP" in constraint[1]
    assert "NP=exception << (IN < /(?i)^except$/)" in exception_np
    assert "SBAR=condition << /(?i)^if$/" in condition


def test_actor_gate_uses_published_subject_object_and_local_voice_relations() -> None:
    tokens = [
        {"pos": "DT"},
        {"pos": "NN"},
        {"pos": "MD"},
        {"pos": "VB"},
        {"pos": "IN"},
        {"pos": "NN"},
        {"pos": "VB"},
    ]
    root_subject = {
        "tokens": tokens,
        "basicDependencies": [
            {"dep": "root", "governor": 0, "dependent": 4},
            {"dep": "nsubj", "governor": 4, "dependent": 2},
        ],
    }
    subordinate_subject = {
        "tokens": tokens,
        "basicDependencies": [
            {"dep": "root", "governor": 0, "dependent": 4},
            {"dep": "nsubj", "governor": 7, "dependent": 2},
        ],
    }
    passive_agent = {
        "tokens": tokens,
        "basicDependencies": [
            {"dep": "root", "governor": 0, "dependent": 4},
            {"dep": "aux:pass", "governor": 4, "dependent": 3},
            {"dep": "obl:agent", "governor": 4, "dependent": 6},
        ],
    }

    assert actor_dependency_supported_by_clause_relation(
        root_subject, {"begin": 0, "end": 2}
    )
    assert actor_dependency_supported_by_clause_relation(
        subordinate_subject, {"begin": 0, "end": 2}
    )
    assert actor_dependency_supported_by_clause_relation(
        passive_agent, {"begin": 5, "end": 6}
    )


def test_bridge_captures_context_before_action_only_pruning() -> None:
    source = (
        ROOT / "tools/corenlp/SunPaperIndependentContextBridge.java"
    ).read_text(encoding="utf-8")

    assert 'if (entry.getKey().equals("action")) continue;' in source
    assert 'new String[] {"modality", "condition", "constraint", "exception"}' in source
    assert 'capture(treeCount, "action", actionRules, working, workingIndexes)' in source
    assert "captureAndPrune(" in source
    assert "original.deepCopy()" in source


def test_mini_manifest_blocks_full_run_when_any_field_regresses() -> None:
    manifest = _load(MANIFEST)

    assert manifest["status"] == "blocked_field_regression"
    assert manifest["full_150_run_performed"] is False
    assert manifest["regressed_fields"] == ["constraint"]
    assert manifest["gates"]["full_150_not_run"] is True
    assert manifest["gates"]["no_llm"] is True
    assert manifest["regression_gates"]["actor"] == {
        "precision_not_lower": True,
        "recall_not_lower": True,
    }
    assert manifest["regression_gates"]["exception"] == {
        "precision_not_lower": True,
        "recall_not_lower": True,
    }
    assert manifest["regression_gates"]["constraint"] == {
        "precision_not_lower": False,
        "recall_not_lower": False,
    }
    assert manifest["safety"]["row_level_predictions_persisted"] is False
